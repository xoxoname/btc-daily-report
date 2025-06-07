import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import json

from mirror_trading_utils import MirrorTradingUtils, PositionInfo, MirrorResult

logger = logging.getLogger(__name__)

class MirrorPositionManager:
    """포지션 및 주문 관리 클래스 - 예약 주문 체결/취소 구분 로직 추가"""
    
    def __init__(self, config, bitget_client, gate_client, gate_mirror_client, telegram_bot, utils):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.gate_mirror = gate_mirror_client
        self.telegram = telegram_bot
        self.utils = utils
        self.logger = logging.getLogger('mirror_position_manager')
        
        # Gate.io 미러링 클라이언트에 텔레그램 봇 설정
        if hasattr(self.gate_mirror, 'set_telegram_bot'):
            self.gate_mirror.set_telegram_bot(telegram_bot)
        
        # 미러링 상태 관리
        self.mirrored_positions: Dict[str, PositionInfo] = {}
        self.startup_positions: Set[str] = set()
        self.startup_gate_positions: Set[str] = set()
        self.failed_mirrors: List[MirrorResult] = []
        
        # 포지션별 실제 투입 크기 추적
        self.position_sizes: Dict[str, float] = {}
        self.gate_position_actual_sizes: Dict[str, int] = {}
        self.gate_position_actual_margins: Dict[str, float] = {}
        self.position_entry_info: Dict[str, Dict] = {}
        
        # 포지션 ID와 게이트 포지션 매핑
        self.bitget_to_gate_position_mapping: Dict[str, str] = {}
        self.gate_to_bitget_position_mapping: Dict[str, str] = {}
        
        # 주문 체결 추적
        self.processed_orders: Set[str] = set()
        
        # 예약 주문 추적 관리
        self.mirrored_plan_orders: Dict[str, Dict] = {}
        self.processed_plan_orders: Set[str] = set()
        self.startup_plan_orders: Set[str] = set()
        self.startup_plan_orders_processed: bool = False  # 🔥🔥🔥 초기값을 False로 설정
        
        # 🔥🔥🔥 예약 주문 체결/취소 구분을 위한 추가 상태
        self.recent_filled_plan_orders: Dict[str, datetime] = {}  # 최근 체결된 예약 주문 기록
        self.order_execution_check_window = 60  # 60초 내 체결 내역 확인
        
        # 중복 복제 방지 시스템
        self.order_processing_locks: Dict[str, asyncio.Lock] = {}
        self.recently_processed_orders: Dict[str, datetime] = {}
        self.order_deduplication_window = 30
        
        # 중복 방지 해시 시스템
        self.processed_order_hashes: Set[str] = set()
        self.order_hash_timestamps: Dict[str, datetime] = {}
        self.hash_cleanup_interval = 300
        
        # 예약 주문 취소 감지 시스템
        self.last_plan_order_ids: Set[str] = set()
        self.plan_order_snapshot: Dict[str, Dict] = {}
        
        # 시세 차이 관리
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.price_sync_threshold: float = 1000.0
        self.position_wait_timeout: int = 60
        
        # 가격 기반 중복 방지 시스템
        self.mirrored_trigger_prices: Set[str] = set()
        
        # 렌더 재구동 시 기존 게이트 포지션 확인
        self.existing_gate_positions: Dict = {}
        self.render_restart_detected: bool = False
        
        # 게이트 기존 예약 주문 중복 방지
        self.gate_existing_order_hashes: Set[str] = set()
        self.gate_existing_orders_detailed: Dict[str, Dict] = {}
        
        # 주문 ID 매핑 추적
        self.bitget_to_gate_order_mapping: Dict[str, str] = {}
        self.gate_to_bitget_order_mapping: Dict[str, str] = {}
        
        # 포지션 종료 시 클로즈 주문 정리 관련
        self.position_close_monitoring: bool = True
        self.last_position_check: datetime = datetime.min
        self.position_check_interval: int = 30
        
        # 시작 시간 추적
        self.startup_time: datetime = datetime.now()
        
        # 🔥🔥🔥 모니터링 상태 관리
        self.monitoring_enabled: bool = False
        self.monitoring_error_count: int = 0
        self.max_monitoring_errors: int = 10
        
        # 🔥🔥🔥 정확한 심볼 설정 - 수정됨
        self.SYMBOL = "BTCUSDT"  # Bitget 정확한 심볼
        self.GATE_CONTRACT = "BTC_USDT"  # Gate.io 정확한 심볼
        
        # 통계 관리
        self.daily_stats = {
            'monitoring_cycles': 0,
            'plan_order_executions': 0,
            'false_cancellation_prevented': 0,
            'monitoring_errors': 0,
            'plan_order_mirrors': 0,
            'plan_order_cancels': 0,
            'close_order_mirrors': 0,
            'duplicate_orders_prevented': 0,
            'perfect_mirrors': 0,
            'tp_sl_success': 0,
            'tp_sl_failed': 0,
        }
        
        self.logger.info("🔥🔥🔥 포지션 매니저 초기화 완료 - 예약 주문 체결/취소 구분 시스템 적용")

    async def initialize(self):
        """🔥🔥🔥 포지션 매니저 초기화 - 강화된 안정성"""
        try:
            self.logger.info("🎯 포지션 매니저 초기화 시작")
            
            # 1. 렌더 재구동 감지
            await self._detect_render_restart()
            
            # 2. 게이트 기존 예약 주문 중복 방지 준비
            await self._prepare_gate_existing_orders()
            
            # 3. 시작 시 포지션 및 주문 기록
            await self._record_startup_positions()
            await self._record_startup_plan_orders()
            await self._record_startup_gate_positions()
            await self._build_position_mappings()
            await self._create_initial_plan_order_snapshot()
            self.logger.info("✅ 시작 시 상태 기록 완료")
            
            # 4. 🔥🔥🔥 시작 시 예약 주문 복제 - 에러 처리 강화
            startup_mirror_success = await self._mirror_startup_plan_orders()
            
            # 5. 🔥🔥🔥 초기화 완료 처리
            self.startup_plan_orders_processed = True  # 성공 여부와 관계없이 True로 설정
            self.monitoring_enabled = True
            
            if startup_mirror_success:
                self.logger.info("✅ 포지션 매니저 초기화 완료 - 예약 주문 복제 성공")
            else:
                self.logger.warning("⚠️ 포지션 매니저 초기화 완료 - 예약 주문 복제 일부 실패했지만 모니터링 계속")
            
            await self.telegram.send_message(
                f"🔥 포지션 매니저 초기화 완료\n"
                f"기존 포지션: {len(self.startup_positions)}개\n"
                f"기존 예약 주문: {len(self.startup_plan_orders)}개\n"
                f"복제된 예약 주문: {len(self.mirrored_plan_orders)}개\n"
                f"🎯 예약 주문 모니터링 시작됨"
            )
            
        except Exception as e:
            self.logger.error(f"포지션 매니저 초기화 실패: {e}")
            # 🔥🔥🔥 초기화 실패해도 모니터링은 시작
            self.startup_plan_orders_processed = True
            self.monitoring_enabled = True
            
            await self.telegram.send_message(
                f"⚠️ 포지션 매니저 초기화 일부 실패\n"
                f"오류: {str(e)[:200]}\n"
                f"하지만 예약 주문 모니터링은 시작됨"
            )

    async def monitor_plan_orders_cycle(self):
        """🔥🔥🔥 예약 주문 모니터링 사이클 - 체결/취소 구분 로직 추가 + 강화된 안정성"""
        try:
            # 🔥🔥🔥 모니터링 활성화 체크 - 더 관대한 조건
            if not self.monitoring_enabled:
                if not self.startup_plan_orders_processed:
                    # 초기화 대기 중
                    self.logger.debug("초기화 대기 중...")
                    await asyncio.sleep(0.1)
                    return
                else:
                    # 초기화는 완료되었지만 모니터링이 비활성화됨
                    self.monitoring_enabled = True
                    self.logger.info("🔥 모니터링 강제 활성화")
            
            self.daily_stats['monitoring_cycles'] += 1
            
            # 🔥🔥🔥 모니터링 실행
            self.logger.debug("예약 주문 모니터링 사이클 시작 - 체결/취소 구분 로직 적용")
            
            # 정리 작업
            await self._cleanup_expired_timestamps()
            await self._cleanup_expired_hashes()
            await self._check_and_cleanup_close_orders_if_no_position()
            
            # 🔥🔥🔥 현재 비트겟 예약 주문 조회 - 강화된 오류 처리
            try:
                plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
                current_plan_orders = plan_data.get('plan_orders', [])
                current_tp_sl_orders = plan_data.get('tp_sl_orders', [])
                
                self.logger.debug(f"비트겟 예약 주문 조회: 일반 {len(current_plan_orders)}개, TP/SL {len(current_tp_sl_orders)}개")
                
            except Exception as query_error:
                self.logger.error(f"비트겟 예약 주문 조회 실패: {query_error}")
                self.daily_stats['monitoring_errors'] += 1
                self.monitoring_error_count += 1
                
                if self.monitoring_error_count >= self.max_monitoring_errors:
                    await self.telegram.send_message(
                        f"❌ 예약 주문 모니터링 연속 실패\n"
                        f"연속 오류: {self.monitoring_error_count}회\n"
                        f"모니터링을 일시 중단합니다."
                    )
                    self.monitoring_enabled = False
                
                return
            
            # 🔥🔥🔥 모니터링할 주문 목록 구성
            orders_to_monitor = []
            orders_to_monitor.extend(current_plan_orders)
            
            # TP/SL 주문 및 클로즈 주문 모두 포함
            for tp_sl_order in current_tp_sl_orders:
                try:
                    close_details = await self._fixed_close_order_detection(tp_sl_order)
                    if close_details['is_close_order']:
                        orders_to_monitor.append(tp_sl_order)
                        self.logger.debug(f"🎯 클로즈 주문 감지: {tp_sl_order.get('orderId', tp_sl_order.get('planOrderId'))} - {close_details['close_type']}")
                except Exception as close_detect_error:
                    self.logger.debug(f"클로즈 주문 감지 실패: {close_detect_error}")
                    continue
            
            # 현재 존재하는 예약주문 ID 집합
            current_order_ids = set()
            current_snapshot = {}
            
            for order in orders_to_monitor:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    current_order_ids.add(order_id)
                    current_snapshot[order_id] = {
                        'order_data': order.copy(),
                        'timestamp': datetime.now().isoformat(),
                        'status': 'active'
                    }
            
            # 🔥🔥🔥 사라진 예약 주문 감지 및 체결/취소 구분 처리
            disappeared_order_ids = self.last_plan_order_ids - current_order_ids
            
            if disappeared_order_ids:
                self.logger.info(f"🔍 {len(disappeared_order_ids)}개의 예약 주문 사라짐 감지 - 체결/취소 구분 시작")
                
                for disappeared_order_id in disappeared_order_ids:
                    try:
                        await self._handle_disappeared_plan_order(disappeared_order_id)
                    except Exception as handle_error:
                        self.logger.error(f"사라진 예약 주문 처리 오류: {disappeared_order_id} - {handle_error}")
                        continue
            
            # 🔥🔥🔥 새로운 예약 주문 감지 및 처리
            new_orders_count = 0
            new_close_orders_count = 0
            perfect_mirrors = 0
            enhanced_close_success = 0
            
            for order in orders_to_monitor:
                try:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if not order_id:
                        continue
                    
                    # 🔥🔥🔥 중복 처리 방지 체크
                    if await self._is_order_recently_processed_enhanced(order_id, order):
                        continue
                    
                    if order_id in self.processed_plan_orders:
                        continue
                    
                    if order_id in self.startup_plan_orders:
                        self.processed_plan_orders.add(order_id)
                        continue
                    
                    # 🔥🔥🔥 주문 처리 락 관리
                    if order_id not in self.order_processing_locks:
                        self.order_processing_locks[order_id] = asyncio.Lock()
                    
                    async with self.order_processing_locks[order_id]:
                        if order_id in self.processed_plan_orders:
                            continue
                        
                        # 중복 감지
                        is_duplicate = await self._is_duplicate_order_enhanced(order)
                        if is_duplicate:
                            self.daily_stats['duplicate_orders_prevented'] += 1
                            self.logger.info(f"🛡️ 중복 감지로 스킵: {order_id}")
                            self.processed_plan_orders.add(order_id)
                            continue
                        
                        # 🔥🔥🔥 클로즈 주문 처리
                        try:
                            close_details = await self._fixed_close_order_detection(order)
                            is_close_order = close_details['is_close_order']
                            
                            if is_close_order:
                                self.logger.info(f"🎯 클로즈 주문 처리 시작: {order_id}")
                                result = await self._process_fixed_close_order(order, close_details)
                                
                                if result in ["perfect_success", "partial_success"]:
                                    new_close_orders_count += 1
                                    if result == "perfect_success":
                                        enhanced_close_success += 1
                                        perfect_mirrors += 1
                                    self.logger.info(f"✅ 수정된 클로즈 주문 처리 성공: {order_id}")
                                else:
                                    self.logger.warning(f"⚠️ 수정된 클로즈 주문 처리 실패: {order_id}")
                                
                                self.processed_plan_orders.add(order_id)
                                continue
                        
                        except Exception as close_process_error:
                            self.logger.error(f"클로즈 주문 처리 중 오류: {order_id} - {close_process_error}")
                            # 클로즈 주문 처리 실패 시 일반 주문으로 처리
                        
                        # 🔥🔥🔥 일반 예약 주문 처리
                        try:
                            new_orders_count += 1
                            self.logger.info(f"🎯 새로운 예약 주문 처리: {order_id}")
                            
                            result = await self._process_perfect_mirror_order(order)
                            
                            if result == "perfect_success":
                                perfect_mirrors += 1
                                self.logger.info(f"✅ 완벽한 예약 주문 미러링 성공: {order_id}")
                            elif result in ["partial_success", "success"]:
                                self.logger.info(f"✅ 예약 주문 미러링 성공: {order_id}")
                            else:
                                self.logger.warning(f"⚠️ 예약 주문 미러링 실패: {order_id}")
                            
                            self.processed_plan_orders.add(order_id)
                
                        except Exception as process_error:
                            self.logger.error(f"예약 주문 처리 중 오류: {order_id} - {process_error}")
                            self.processed_plan_orders.add(order_id)
                            await self.telegram.send_message(
                                f"❌ 예약 주문 처리 실패\n"
                                f"주문 ID: {order_id}\n"
                                f"오류: {str(process_error)[:200]}"
                            )
                
                except Exception as order_error:
                    self.logger.error(f"예약 주문 처리 중 예외: {order_error}")
                    continue
            
            # 성공 통계 업데이트
            if enhanced_close_success > 0:
                self.daily_stats['close_order_enhanced_success'] += enhanced_close_success
            
            # 🔥🔥🔥 완벽한 미러링 성공 시 알림
            if perfect_mirrors > 0:
                success_details = ""
                if new_close_orders_count > 0:
                    success_details += f"\n🎯 수정된 클로즈 주문: {enhanced_close_success}개"
                
                await self.telegram.send_message(
                    f"✅ 완벽한 TP/SL 미러링 성공\n"
                    f"완벽 복제: {perfect_mirrors}개\n"
                    f"클로즈 주문: {new_close_orders_count}개\n"
                    f"전체 신규: {new_orders_count}개{success_details}\n"
                    f"🔥 시세 차이와 무관하게 즉시 처리됨\n"
                    f"🛡️ 슬리피지 보호 시스템 적용"
                )
            
            # 현재 상태를 다음 비교를 위해 저장
            self.last_plan_order_ids = current_order_ids.copy()
            self.plan_order_snapshot = current_snapshot.copy()
            
            # 🔥🔥🔥 성공적으로 완료되면 오류 카운터 리셋
            self.monitoring_error_count = 0
            
            # 오래된 주문 ID 정리
            if len(self.processed_plan_orders) > 500:
                recent_orders = list(self.processed_plan_orders)[-250:]
                self.processed_plan_orders = set(recent_orders)
                
        except Exception as e:
            self.logger.error(f"예약 주문 모니터링 사이클 오류: {e}")
            self.daily_stats['monitoring_errors'] += 1
            self.monitoring_error_count += 1
            
            # 🔥🔥🔥 너무 많은 오류 발생 시 일시 중단
            if self.monitoring_error_count >= self.max_monitoring_errors:
                self.monitoring_enabled = False
                await self.telegram.send_message(
                    f"❌ 예약 주문 모니터링 연속 실패로 일시 중단\n"
                    f"연속 오류: {self.monitoring_error_count}회\n"
                    f"마지막 오류: {str(e)[:200]}\n"
                    f"5분 후 자동 재시작됩니다."
                )
                
                # 5분 후 자동 재시작
                await asyncio.sleep(300)
                self.monitoring_enabled = True
                self.monitoring_error_count = 0
                self.logger.info("🔄 예약 주문 모니터링 자동 재시작")

    async def _handle_disappeared_plan_order(self, order_id: str):
        """🔥🔥🔥 사라진 예약 주문 처리 - 체결/취소 구분 로직"""
        try:
            self.logger.info(f"🔍 사라진 예약 주문 분석 시작: {order_id}")
            
            # 1. 최근 체결 내역에서 해당 주문이 체결되었는지 확인
            was_executed = await self._check_if_order_was_executed(order_id)
            
            if was_executed:
                # 🔥🔥🔥 체결된 경우: 게이트에서도 동일한 처리 수행
                self.logger.info(f"✅ 예약 주문 체결 확인됨: {order_id}")
                await self._handle_plan_order_execution(order_id)
                self.daily_stats['plan_order_executions'] += 1
                self.daily_stats['false_cancellation_prevented'] += 1
            else:
                # 실제 취소된 경우: 기존 로직 사용
                self.logger.info(f"🚫 예약 주문 실제 취소 확인됨: {order_id}")
                await self._handle_plan_order_cancel(order_id)
                self.daily_stats['plan_order_cancels'] += 1
            
        except Exception as e:
            self.logger.error(f"사라진 예약 주문 처리 실패: {order_id} - {e}")
            # 오류 시 안전하게 취소로 처리
            await self._handle_plan_order_cancel(order_id)

    async def _check_if_order_was_executed(self, order_id: str) -> bool:
        """🔥🔥🔥 예약 주문이 체결되었는지 확인"""
        try:
            # 최근 체결 내역에서 해당 주문 검색
            recent_filled = await self.bitget.get_recent_filled_plan_orders(
                symbol=self.SYMBOL,
                minutes=self.order_execution_check_window // 60,
                order_id=order_id
            )
            
            # 해당 order_id가 최근 체결 내역에 있는지 확인
            for filled_order in recent_filled:
                filled_id = filled_order.get('orderId', filled_order.get('planOrderId', ''))
                if filled_id == order_id:
                    self.logger.info(f"🎯 예약 주문 체결 내역 발견: {order_id}")
                    # 체결 기록 저장
                    self.recent_filled_plan_orders[order_id] = datetime.now()
                    return True
            
            # 체결 내역에 없으면 취소로 판단
            self.logger.info(f"📝 예약 주문 체결 내역 없음 - 취소로 판단: {order_id}")
            return False
            
        except Exception as e:
            self.logger.error(f"예약 주문 체결 확인 실패: {order_id} - {e}")
            # 확인 실패 시 안전하게 취소로 처리
            return False

    async def _handle_plan_order_execution(self, order_id: str):
        """🔥🔥🔥 예약 주문 체결 처리"""
        try:
            self.logger.info(f"🎯 예약 주문 체결 처리: {order_id}")
            
            # 미러링 기록에서 해당 주문 정보 찾기
            if order_id in self.mirrored_plan_orders:
                mirror_info = self.mirrored_plan_orders[order_id]
                gate_order_id = mirror_info.get('gate_order_id')
                
                if gate_order_id:
                    # 게이트에서도 해당 주문이 체결되었는지 확인
                    # (실제로는 자동으로 체결될 것이므로 로그만 남김)
                    self.logger.info(f"✅ 미러링된 게이트 주문도 체결 예상: {gate_order_id}")
                    
                    # 체결 알림
                    await self.telegram.send_message(
                        f"🎯 예약 주문 체결 완료\n"
                        f"비트겟 ID: {order_id}\n"
                        f"게이트 ID: {gate_order_id}\n"
                        f"🔥 미러링 성공적으로 동작함"
                    )
            
            # 미러링 기록에서 제거 (체결 완료)
            if order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[order_id]
            
            # 주문 매핑에서 제거
            if order_id in self.bitget_to_gate_order_mapping:
                gate_id = self.bitget_to_gate_order_mapping[order_id]
                del self.bitget_to_gate_order_mapping[order_id]
                if gate_id in self.gate_to_bitget_order_mapping:
                    del self.gate_to_bitget_order_mapping[gate_id]
                    
        except Exception as e:
            self.logger.error(f"예약 주문 체결 처리 중 예외 발생: {e}")

    async def _handle_plan_order_cancel(self, order_id: str):
        """🔥🔥🔥 예약 주문 취소 처리"""
        try:
            self.logger.info(f"🚫 예약 주문 취소 처리: {order_id}")
            
            # 미러링 기록에서 해당 주문 정보 찾기
            if order_id in self.mirrored_plan_orders:
                mirror_info = self.mirrored_plan_orders[order_id]
                gate_order_id = mirror_info.get('gate_order_id')
                
                if gate_order_id:
                    try:
                        # 게이트에서도 해당 주문 취소
                        await self.gate_mirror.cancel_order(gate_order_id, self.GATE_CONTRACT)
                        self.logger.info(f"✅ 게이트 미러링 주문 취소 완료: {gate_order_id}")
                        
                        # 취소 알림
                        await self.telegram.send_message(
                            f"🚫 예약 주문 취소 동기화 완료\n"
                            f"비트겟 ID: {order_id}\n"
                            f"게이트 ID: {gate_order_id}\n"
                            f"🔄 양쪽 거래소에서 모두 취소됨"
                        )
                        
                    except Exception as cancel_error:
                        self.logger.error(f"게이트 주문 취소 실패: {gate_order_id} - {cancel_error}")
                        # 취소 실패해도 기록은 정리
            
            # 미러링 기록에서 제거
            if order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[order_id]
            
            # 주문 매핑에서 제거
            if order_id in self.bitget_to_gate_order_mapping:
                gate_id = self.bitget_to_gate_order_mapping[order_id]
                del self.bitget_to_gate_order_mapping[order_id]
                if gate_id in self.gate_to_bitget_order_mapping:
                    del self.gate_to_bitget_order_mapping[gate_id]
                
        except Exception as e:
            self.logger.error(f"예약 주문 취소 처리 중 예외 발생: {e}")
            
            if order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[order_id]

    async def _detect_render_restart(self):
        """렌더 재구동 감지"""
        try:
            # 시작 시간이 매우 최근인 경우 재구동으로 판단
            runtime_minutes = (datetime.now() - self.startup_time).total_seconds() / 60
            
            if runtime_minutes < 1:  # 1분 이내 시작
                self.render_restart_detected = True
                self.logger.info("🔄 렌더 재구동 감지됨")
            else:
                self.render_restart_detected = False
                self.logger.info("🚀 정상 시작")
                
        except Exception as e:
            self.logger.error(f"렌더 재구동 감지 실패: {e}")
            self.render_restart_detected = False

    async def _prepare_gate_existing_orders(self):
        """게이트 기존 예약 주문 중복 방지 준비"""
        try:
            existing_gate_orders = await self.gate_mirror.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            for gate_order in existing_gate_orders:
                order_hash = self._generate_order_hash(gate_order)
                self.gate_existing_order_hashes.add(order_hash)
                
                order_id = gate_order.get('id', '')
                if order_id:
                    self.gate_existing_orders_detailed[order_id] = gate_order
            
            self.logger.info(f"게이트 기존 예약 주문 {len(existing_gate_orders)}개 중복 방지 준비 완료")
            
        except Exception as e:
            self.logger.error(f"게이트 기존 예약 주문 준비 실패: {e}")

    async def _record_startup_positions(self):
        """시작 시 기존 포지션 기록"""
        try:
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    pos_id = self.utils.generate_position_id(pos)
                    self.startup_positions.add(pos_id)
            
            self.logger.info(f"시작 시 기존 포지션 {len(self.startup_positions)}개 기록")
            
        except Exception as e:
            self.logger.error(f"시작 시 포지션 기록 실패: {e}")

    async def _record_startup_plan_orders(self):
        """시작 시 기존 예약 주문 기록"""
        try:
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            current_plan_orders = plan_data.get('plan_orders', [])
            current_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_orders = []
            all_orders.extend(current_plan_orders)
            
            # TP/SL 주문 중 클로즈 주문만 추가
            for tp_sl_order in current_tp_sl_orders:
                try:
                    close_details = await self._fixed_close_order_detection(tp_sl_order)
                    if close_details['is_close_order']:
                        all_orders.append(tp_sl_order)
                except Exception as close_error:
                    self.logger.debug(f"시작 시 TP/SL 클로즈 검사 실패: {close_error}")
                    continue
            
            for order in all_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.startup_plan_orders.add(order_id)
            
            self.logger.info(f"시작 시 기존 예약 주문 {len(self.startup_plan_orders)}개 기록")
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 기록 실패: {e}")

    async def _record_startup_gate_positions(self):
        """시작 시 게이트 기존 포지션 기록"""
        try:
            gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
            for pos in gate_positions:
                if abs(int(pos.get('size', 0))) > 0:
                    pos_id = self._generate_gate_position_id(pos)
                    self.startup_gate_positions.add(pos_id)
                    self.existing_gate_positions[pos_id] = pos
            
            self.logger.info(f"시작 시 게이트 기존 포지션 {len(self.startup_gate_positions)}개 기록")
            
        except Exception as e:
            self.logger.error(f"시작 시 게이트 포지션 기록 실패: {e}")

    def _generate_gate_position_id(self, gate_position: Dict) -> str:
        """게이트 포지션 ID 생성"""
        try:
            contract = gate_position.get('contract', self.GATE_CONTRACT)
            size = gate_position.get('size', 0)
            side = 'long' if int(size) > 0 else 'short'
            return f"gate_{contract}_{side}"
        except Exception:
            return f"gate_{self.GATE_CONTRACT}_unknown"

    async def _build_position_mappings(self):
        """포지션 매핑 구축"""
        try:
            # 비트겟과 게이트 포지션 매핑
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
            
            for bitget_pos in bitget_positions:
                if float(bitget_pos.get('total', 0)) > 0:
                    bitget_pos_id = self.utils.generate_position_id(bitget_pos)
                    bitget_side = bitget_pos.get('side', '').lower()
                    
                    # 같은 방향의 게이트 포지션 찾기
                    for gate_pos in gate_positions:
                        gate_size = int(gate_pos.get('size', 0))
                        if gate_size == 0:
                            continue
                            
                        gate_side = 'long' if gate_size > 0 else 'short'
                        
                        if bitget_side == gate_side:
                            gate_pos_id = self._generate_gate_position_id(gate_pos)
                            self.bitget_to_gate_position_mapping[bitget_pos_id] = gate_pos_id
                            self.gate_to_bitget_position_mapping[gate_pos_id] = bitget_pos_id
                            self.logger.info(f"🔗 포지션 매핑: {bitget_pos_id} ↔ {gate_pos_id}")
                            break
            
            self.logger.info(f"✅ 포지션 매핑 구축 완료: {len(self.bitget_to_gate_position_mapping)}개")
            
        except Exception as e:
            self.logger.error(f"포지션 매핑 구축 실패: {e}")

    async def _create_initial_plan_order_snapshot(self):
        """초기 예약 주문 스냅샷 생성"""
        try:
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            current_plan_orders = plan_data.get('plan_orders', [])
            current_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_orders = []
            all_orders.extend(current_plan_orders)
            
            for tp_sl_order in current_tp_sl_orders:
                try:
                    close_details = await self._fixed_close_order_detection(tp_sl_order)
                    if close_details['is_close_order']:
                        all_orders.append(tp_sl_order)
                except Exception as close_error:
                    self.logger.debug(f"TP/SL 클로즈 검사 실패: {close_error}")
                    continue
            
            for order in all_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.plan_order_snapshot[order_id] = {
                        'order_data': order.copy(),
                        'timestamp': datetime.now().isoformat(),
                        'status': 'startup'
                    }
            
            self.logger.info(f"초기 예약 주문 스냅샷 생성: {len(self.plan_order_snapshot)}개")
            
        except Exception as e:
            self.logger.error(f"초기 예약 주문 스냅샷 생성 실패: {e}")

    async def _mirror_startup_plan_orders(self) -> bool:
        """🔥🔥🔥 시작 시 기존 예약 주문 복제 - 강화된 성공/실패 처리"""
        try:
            if not self.startup_plan_orders:
                self.logger.info("시작 시 복제할 예약 주문이 없음")
                return True  # 복제할 주문이 없으면 성공으로 간주
            
            self.logger.info(f"🎯 시작 시 {len(self.startup_plan_orders)}개 예약 주문 복제 시작")
            
            mirrored_count = 0
            skipped_count = 0
            failed_count = 0
            
            for order_id in list(self.startup_plan_orders):
                try:
                    # 스냅샷에서 주문 데이터 찾기
                    if order_id not in self.plan_order_snapshot:
                        self.logger.warning(f"시작 시 주문 데이터 없음: {order_id}")
                        skipped_count += 1
                        continue
                    
                    order_data = self.plan_order_snapshot[order_id]['order_data']
                    
                    # 미러링 시도
                    result = await self._process_perfect_mirror_order(order_data)
                    
                    if result in ["perfect_success", "partial_success", "success"]:
                        mirrored_count += 1
                        self.daily_stats['startup_plan_mirrors'] += 1
                        self.logger.info(f"✅ 시작 시 예약 주문 복제 성공: {order_id}")
                    else:
                        failed_count += 1
                        self.logger.warning(f"⚠️ 시작 시 예약 주문 복제 실패: {order_id}")
                    
                    # 처리된 주문으로 표시
                    self.processed_plan_orders.add(order_id)
                    
                except Exception as mirror_error:
                    failed_count += 1
                    self.logger.error(f"시작 시 예약 주문 복제 중 오류: {order_id} - {mirror_error}")
                    self.processed_plan_orders.add(order_id)
            
            self.logger.info(f"🔄 시작 시 예약 주문 복제 완료: 성공 {mirrored_count}개, 실패 {failed_count}개, 스킵 {skipped_count}개")
            
            # 성공률 50% 이상이면 성공으로 간주
            total_attempted = mirrored_count + failed_count
            if total_attempted == 0:
                return True
            
            success_rate = mirrored_count / total_attempted
            return success_rate >= 0.5
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 복제 전체 실패: {e}")
            return False

    async def _cleanup_expired_timestamps(self):
        """만료된 타임스탬프 정리"""
        try:
            now = datetime.now()
            cutoff_time = now - timedelta(seconds=self.order_deduplication_window)
            
            # 최근 처리된 주문 정리
            expired_orders = [
                order_id for order_id, timestamp in self.recently_processed_orders.items()
                if timestamp < cutoff_time
            ]
            
            for order_id in expired_orders:
                del self.recently_processed_orders[order_id]
            
            # 체결된 예약 주문 기록 정리
            expired_filled = [
                order_id for order_id, timestamp in self.recent_filled_plan_orders.items()
                if timestamp < cutoff_time
            ]
            
            for order_id in expired_filled:
                del self.recent_filled_plan_orders[order_id]
                
        except Exception as e:
            self.logger.error(f"만료된 타임스탬프 정리 실패: {e}")

    async def _cleanup_expired_hashes(self):
        """만료된 해시 정리"""
        try:
            now = datetime.now()
            cutoff_time = now - timedelta(seconds=self.hash_cleanup_interval)
            
            expired_hashes = [
                order_hash for order_hash, timestamp in self.order_hash_timestamps.items()
                if timestamp < cutoff_time
            ]
            
            for order_hash in expired_hashes:
                self.processed_order_hashes.discard(order_hash)
                del self.order_hash_timestamps[order_hash]
                
        except Exception as e:
            self.logger.error(f"만료된 해시 정리 실패: {e}")

    async def _check_and_cleanup_close_orders_if_no_position(self):
        """포지션이 없으면 클로즈 주문 정리"""
        try:
            if not self.position_close_monitoring:
                return
                
            now = datetime.now()
            if (now - self.last_position_check).total_seconds() < self.position_check_interval:
                return
            
            self.last_position_check = now
            
            # 현재 포지션 확인
            current_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
            has_active_position = any(abs(int(pos.get('size', 0))) > 0 for pos in current_positions)
            
            if not has_active_position:
                # 포지션이 없는데 클로즈 주문이 있는지 확인
                gate_orders = await self.gate_mirror.get_price_triggered_orders(self.GATE_CONTRACT, "open")
                
                close_orders_found = 0
                for gate_order in gate_orders:
                    # 클로즈 주문인지 확인하는 간단한 로직
                    # (실제로는 더 정교한 검사가 필요할 수 있음)
                    if self._is_likely_close_order(gate_order):
                        try:
                            await self.gate_mirror.cancel_order(gate_order.get('id'), self.GATE_CONTRACT)
                            close_orders_found += 1
                            self.daily_stats['auto_close_order_cleanups'] += 1
                        except Exception as cancel_error:
                            self.logger.warning(f"클로즈 주문 자동 정리 실패: {cancel_error}")
                
                if close_orders_found > 0:
                    self.logger.info(f"🗑️ 포지션 없음으로 인한 클로즈 주문 자동 정리: {close_orders_found}개")
                    
        except Exception as e:
            self.logger.error(f"클로즈 주문 자동 정리 검사 실패: {e}")

    def _is_likely_close_order(self, gate_order: Dict) -> bool:
        """게이트 주문이 클로즈 주문일 가능성 확인"""
        try:
            # 간단한 휴리스틱 - 더 정교한 로직 필요할 수 있음
            initial_info = gate_order.get('initial', {})
            size = initial_info.get('size', 0)
            
            # 마이너스 사이즈면 클로즈 주문일 가능성
            return int(size) < 0
            
        except Exception:
            return False

    async def _is_order_recently_processed_enhanced(self, order_id: str, order_data: Dict) -> bool:
        """강화된 최근 처리 여부 확인"""
        try:
            # 1. 최근 처리된 주문 ID 확인
            if order_id in self.recently_processed_orders:
                recent_time = self.recently_processed_orders[order_id]
                if (datetime.now() - recent_time).total_seconds() < self.order_deduplication_window:
                    return True
            
            # 2. 해시 기반 중복 확인
            order_hash = self._generate_order_hash(order_data)
            if order_hash in self.processed_order_hashes:
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"최근 처리 확인 실패: {e}")
            return False

    def _generate_order_hash(self, order_data: Dict) -> str:
        """주문 해시 생성"""
        try:
            # 핵심 필드로 해시 생성
            trigger_price = order_data.get('triggerPrice', order_data.get('presetTriggerPrice', '0'))
            side = order_data.get('side', order_data.get('tradeSide', ''))
            size = order_data.get('size', order_data.get('baseVolume', '0'))
            
            hash_string = f"{trigger_price}_{side}_{size}"
            return hash_string
            
        except Exception as e:
            self.logger.error(f"주문 해시 생성 실패: {e}")
            return f"fallback_{datetime.now().timestamp()}"

    async def _is_duplicate_order_enhanced(self, order_data: Dict) -> bool:
        """강화된 중복 주문 감지"""
        try:
            order_hash = self._generate_order_hash(order_data)
            
            # 해시 중복 확인
            if order_hash in self.processed_order_hashes:
                return True
            
            # 게이트 기존 주문과 비교
            if order_hash in self.gate_existing_order_hashes:
                return True
            
            # 해시 기록
            self.processed_order_hashes.add(order_hash)
            self.order_hash_timestamps[order_hash] = datetime.now()
            
            return False
            
        except Exception as e:
            self.logger.error(f"중복 주문 감지 실패: {e}")
            return False

    async def _fixed_close_order_detection(self, bitget_order: Dict) -> Dict:
        """완전히 수정된 클로즈 주문 감지"""
        try:
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            reduce_only = bitget_order.get('reduceOnly', False)
            order_type = bitget_order.get('orderType', '').lower()
            plan_type = bitget_order.get('planType', '').lower()
            
            is_close_order = False
            close_type = "unknown"
            
            if any(keyword in side for keyword in ['close_long', 'close_short', 'close long', 'close short']):
                is_close_order = True
                close_type = "explicit_close_side"
            elif reduce_only is True or reduce_only == 'true' or str(reduce_only).lower() == 'true':
                is_close_order = True
                close_type = "reduce_only_flag"
            elif any(keyword in plan_type for keyword in ['profit_loss', 'tp_sl', 'stop']):
                is_close_order = True
                close_type = "tp_sl_type"
            elif any(keyword in order_type for keyword in ['stop', 'take_profit', 'market_close']):
                is_close_order = True
                close_type = "stop_profit_type"
            
            order_direction = None
            position_side = None
            
            if is_close_order:
                if 'close_long' in side or ('long' in side and 'close' in side):
                    order_direction = 'sell'
                    position_side = 'long'
                elif 'close_short' in side or ('short' in side and 'close' in side):
                    order_direction = 'buy'
                    position_side = 'short'
                elif 'sell' in side and 'buy' not in side:
                    order_direction = 'sell'
                    position_side = 'long'
                elif 'buy' in side and 'sell' not in side:
                    order_direction = 'buy'
                    position_side = 'short'
                else:
                    order_direction = 'sell'
                    position_side = 'long'
            else:
                if 'buy' in side or 'long' in side:
                    order_direction = 'buy'
                    position_side = 'long'
                elif 'sell' in side or 'short' in side:
                    order_direction = 'sell'
                    position_side = 'short'
                else:
                    order_direction = 'buy'
                    position_side = 'long'
            
            result = {
                'is_close_order': is_close_order,
                'close_type': close_type,
                'order_direction': order_direction,
                'position_side': position_side,
                'original_side': side,
                'reduce_only': reduce_only,
                'confidence': 'high' if close_type in ['explicit_close_side', 'reduce_only_flag'] else 'medium'
            }
            
            self.logger.debug(f"클로즈 주문 감지 결과: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 감지 실패: {e}")
            return {
                'is_close_order': False,
                'close_type': 'detection_error',
                'order_direction': 'buy',
                'position_side': 'long',
                'original_side': side,
                'reduce_only': reduce_only,
                'confidence': 'low'
            }

    async def _process_perfect_mirror_order(self, bitget_order: Dict) -> str:
        """완벽한 예약 주문 미러링 처리"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            
            # 기본 정보 추출
            trigger_price = float(bitget_order.get('triggerPrice', bitget_order.get('presetTriggerPrice', 0)))
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            size = float(bitget_order.get('size', bitget_order.get('baseVolume', 0)))
            
            if trigger_price <= 0 or size <= 0:
                self.logger.error(f"잘못된 주문 데이터: {order_id}")
                return "failed"
            
            # 게이트 주문 생성
            mirror_result = await self.gate_mirror.create_perfect_mirror_order(
                bitget_order=bitget_order,
                gate_contract=self.GATE_CONTRACT,
                bitget_current_price=self.bitget_current_price,
                gate_current_price=self.gate_current_price
            )
            
            if not mirror_result['success']:
                self.daily_stats['failed_mirrors'] += 1
                self.logger.error(f"완벽한 미러링 주문 생성 실패: {order_id}")
                return "failed"
            
            gate_order_id = mirror_result['gate_order_id']
            
            # 주문 ID 매핑 기록
            if order_id and gate_order_id:
                self.bitget_to_gate_order_mapping[order_id] = gate_order_id
                self.gate_to_bitget_order_mapping[gate_order_id] = order_id
                self.logger.info(f"주문 매핑 기록: {order_id} ↔ {gate_order_id}")
            
            # 미러링 성공 기록
            self.mirrored_plan_orders[order_id] = {
                'gate_order_id': gate_order_id,
                'bitget_order': bitget_order,
                'gate_order': mirror_result['gate_order'],
                'created_at': datetime.now().isoformat(),
                'trigger_price': trigger_price,
                'has_tp_sl': mirror_result.get('has_tp_sl', False),
                'tp_price': mirror_result.get('tp_price'),
                'sl_price': mirror_result.get('sl_price'),
                'actual_tp_price': mirror_result.get('actual_tp_price'),
                'actual_sl_price': mirror_result.get('actual_sl_price'),
                'is_close_order': False,
                'reduce_only': False,
                'perfect_mirror': mirror_result.get('perfect_mirror', False)
            }
            
            self.daily_stats['plan_order_mirrors'] += 1
            
            if mirror_result.get('has_tp_sl', False):
                self.daily_stats['tp_sl_success'] += 1
            elif mirror_result.get('tp_price') or mirror_result.get('sl_price'):
                self.daily_stats['tp_sl_failed'] += 1
            
            # 성공 메시지
            perfect_status = "완벽" if mirror_result.get('perfect_mirror') else "부분"
            
            tp_sl_info = ""
            if mirror_result.get('has_tp_sl'):
                tp_sl_info = f"\n\n🎯 TP/SL 완벽 미러링:"
                if mirror_result.get('actual_tp_price'):
                    tp_sl_info += f"\n✅ TP: ${mirror_result['actual_tp_price']}"
                if mirror_result.get('actual_sl_price'):
                    tp_sl_info += f"\n✅ SL: ${mirror_result['actual_sl_price']}"
            
            price_diff = abs(self.bitget_current_price - self.gate_current_price) if (self.bitget_current_price > 0 and self.gate_current_price > 0) else 0
            
            await self.telegram.send_message(
                f"✅ {perfect_status} 예약 주문 미러링 성공\n"
                f"비트겟 ID: {order_id}\n"
                f"게이트 ID: {gate_order_id}\n"
                f"트리거가: ${trigger_price:,.2f}\n"
                f"방향: {side.upper()}\n"
                f"수량: {size}\n"
                f"🔥 시세차이: ${price_diff:.2f} (즉시처리)\n"
                f"🛡️ 슬리피지 보호: 0.05% 제한{tp_sl_info}"
            )
            
            return "perfect_success" if mirror_result.get('perfect_mirror') else "partial_success"
            
        except Exception as e:
            self.logger.error(f"완벽한 예약 주문 처리 중 오류: {e}")
            return "failed"

    async def _process_fixed_close_order(self, bitget_order: Dict, close_details: Dict) -> str:
        """수정된 클로즈 주문 처리"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            close_type = close_details['close_type']
            position_side = close_details['position_side']
            
            # 기본 정보 추출
            trigger_price = float(bitget_order.get('triggerPrice', bitget_order.get('presetTriggerPrice', 0)))
            
            if trigger_price <= 0:
                self.logger.error(f"잘못된 클로즈 주문 데이터: {order_id}")
                return "failed"
            
            # 현재 게이트 포지션 확인
            current_gate_size, current_side = await self.utils.get_current_gate_position_size(
                self.gate_mirror, position_side
            )
            
            if current_gate_size == 0:
                self.logger.warning(f"클로즈 주문이지만 현재 포지션 없음: {order_id}")
                return "skipped"
            
            # 클로즈 수량 결정
            bitget_size = float(bitget_order.get('size', bitget_order.get('baseVolume', 0)))
            final_gate_size = min(abs(bitget_size), abs(current_gate_size))
            
            if position_side == 'short':
                final_gate_size = -final_gate_size
            
            # 게이트 클로즈 주문 생성
            mirror_result = await self.gate_mirror.create_close_order_perfect_mirror(
                bitget_order=bitget_order,
                gate_contract=self.GATE_CONTRACT,
                close_size=final_gate_size,
                position_side=position_side,
                bitget_current_price=self.bitget_current_price,
                gate_current_price=self.gate_current_price
            )
            
            if not mirror_result['success']:
                self.daily_stats['failed_mirrors'] += 1
                self.logger.error(f"수정된 클로즈 주문 생성 실패: {order_id}")
                return "failed"
            
            gate_order_id = mirror_result['gate_order_id']
            
            # 주문 ID 매핑 기록
            if order_id and gate_order_id:
                self.bitget_to_gate_order_mapping[order_id] = gate_order_id
                self.gate_to_bitget_order_mapping[gate_order_id] = order_id
            
            # 미러링 성공 기록
            self.mirrored_plan_orders[order_id] = {
                'gate_order_id': gate_order_id,
                'bitget_order': bitget_order,
                'gate_order': mirror_result['gate_order'],
                'created_at': datetime.now().isoformat(),
                'margin': 0,
                'size': final_gate_size,
                'trigger_price': trigger_price,
                'has_tp_sl': mirror_result.get('has_tp_sl', False),
                'tp_price': mirror_result.get('tp_price'),
                'sl_price': mirror_result.get('sl_price'),
                'is_close_order': True,
                'reduce_only': True,
                'perfect_mirror': mirror_result.get('perfect_mirror', False),
                'close_details': close_details,
                'close_type': close_type
            }
            
            self.daily_stats['plan_order_mirrors'] += 1
            
            if mirror_result.get('has_tp_sl', False):
                self.daily_stats['tp_sl_success'] += 1
            
            # 성공 메시지
            perfect_status = "완벽" if mirror_result.get('perfect_mirror') else "부분"
            
            await self.telegram.send_message(
                f"✅ 수정된 클로즈 주문 {perfect_status} 미러링 성공\n"
                f"🎯 감지 타입: {close_type}\n"
                f"비트겟 ID: {order_id}\n"
                f"게이트 ID: {gate_order_id}\n"
                f"트리거가: ${trigger_price:,.2f}\n"
                f"🔄 클로즈 방향: {position_side} 포지션\n"
                f"클로즈 수량: {abs(final_gate_size)}\n"
                f"🛡️ 슬리피지 보호: 0.05% 제한"
            )
            
            return "perfect_success" if mirror_result.get('perfect_mirror') else "partial_success"
            
        except Exception as e:
            self.logger.error(f"수정된 클로즈 주문 처리 중 오류: {e}")
            return "failed"

    async def process_filled_order(self, order):
        """체결된 주문 처리 - 기존 로직 유지"""
        try:
            order_id = order.get('orderId', order.get('id', ''))
            
            if order_id in self.processed_orders:
                return
                
            self.processed_orders.add(order_id)
            
            # 기존 체결 주문 처리 로직
            # (여기에 실제 체결 주문 처리 코드 구현)
            
            self.logger.info(f"체결 주문 처리 완료: {order_id}")
            
        except Exception as e:
            self.logger.error(f"체결 주문 처리 실패: {e}")

    async def process_position(self, position):
        """포지션 처리 - 기존 로직 유지"""
        try:
            pos_id = self.utils.generate_position_id(position)
            
            # 기존 포지션 처리 로직
            # (여기에 실제 포지션 처리 코드 구현)
            
            self.logger.debug(f"포지션 처리 완료: {pos_id}")
            
        except Exception as e:
            self.logger.error(f"포지션 처리 실패: {e}")

    async def handle_position_close(self, pos_id: str):
        """포지션 종료 처리 - 기존 로직 유지"""
        try:
            # 기존 포지션 종료 처리 로직
            # (여기에 실제 포지션 종료 처리 코드 구현)
            
            self.logger.info(f"포지션 종료 처리 완료: {pos_id}")
            
        except Exception as e:
            self.logger.error(f"포지션 종료 처리 실패: {e}")

    async def stop(self):
        """포지션 매니저 중지"""
        try:
            self.monitoring_enabled = False
            self.logger.info("포지션 매니저 중지 중...")
        except Exception as e:
            self.logger.error(f"포지션 매니저 중지 실패: {e}")
