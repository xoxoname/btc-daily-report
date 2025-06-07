import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import json

from mirror_trading_utils import MirrorTradingUtils, PositionInfo, MirrorResult

logger = logging.getLogger(__name__)

class MirrorPositionManager:
    """포지션 및 주문 관리 클래스 - 시세 차이 제한 완전 제거"""
    
    def __init__(self, config, bitget_client, gate_client, gate_mirror_client, telegram_bot, utils):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.gate_mirror = gate_mirror_client
        self.telegram = telegram_bot
        self.utils = utils
        self.logger = logging.getLogger('mirror_position_manager')
        
        # 미러링 상태 관리
        self.mirrored_positions: Dict[str, PositionInfo] = {}
        self.startup_positions: Set[str] = set()
        self.startup_gate_positions: Set[str] = set()
        self.failed_mirrors: List[MirrorResult] = []
        
        # 🔥🔥🔥 포지션별 실제 투입 크기 추적 강화
        self.position_sizes: Dict[str, float] = {}
        self.gate_position_actual_sizes: Dict[str, int] = {}  # 게이트 실제 계약 수
        self.gate_position_actual_margins: Dict[str, float] = {}  # 게이트 실제 투입 마진
        self.position_entry_info: Dict[str, Dict] = {}  # 포지션 진입 정보 상세 기록
        
        # 주문 체결 추적
        self.processed_orders: Set[str] = set()
        
        # 예약 주문 추적 관리
        self.mirrored_plan_orders: Dict[str, Dict] = {}
        self.processed_plan_orders: Set[str] = set()
        self.startup_plan_orders: Set[str] = set()
        self.startup_plan_orders_processed: bool = False
        
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
        self.price_sync_threshold: float = 1000.0  # 🔥🔥🔥 매우 관대하게 설정
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
        
        # 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.MIN_POSITION_SIZE = 0.00001
        self.MIN_MARGIN = 1.0
        self.MAX_RETRIES = 3
        
        # 성과 추적
        self.daily_stats = {
            'total_mirrored': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'total_volume': 0.0,
            'order_mirrors': 0,
            'position_mirrors': 0,
            'plan_order_mirrors': 0,
            'plan_order_cancels': 0,
            'startup_plan_mirrors': 0,
            'close_order_mirrors': 0,
            'close_order_skipped': 0,
            'duplicate_orders_prevented': 0,
            'perfect_mirrors': 0,
            'partial_mirrors': 0,
            'tp_sl_success': 0,
            'tp_sl_failed': 0,
            'auto_close_order_cleanups': 0,
            'position_closed_cleanups': 0,
            'sync_corrections': 0,
            'sync_deletions': 0,
            'position_size_corrections': 0,  # 포지션 크기 보정 통계
            'errors': []
        }
        
        self.logger.info("🔥 미러 포지션 매니저 초기화 완료 - 시세 차이 제한 완전 제거")

    def update_prices(self, bitget_price: float, gate_price: float, price_diff_percent: float):
        """시세 정보 업데이트"""
        self.bitget_current_price = bitget_price
        self.gate_current_price = gate_price
        self.price_diff_percent = price_diff_percent

    async def initialize(self):
        """포지션 매니저 초기화"""
        try:
            self.logger.info("🔥 포지션 매니저 초기화 시작")
            
            # Gate 미러링 클라이언트 초기화
            await self.gate_mirror.initialize()
            
            # 렌더 재구동 시 기존 게이트 포지션 확인
            await self._check_existing_gate_positions()
            
            # 🔥🔥🔥 기존 게이트 포지션의 실제 크기 기록
            await self._record_existing_gate_position_sizes()
            
            # 게이트 기존 예약 주문 확인
            await self._record_gate_existing_orders()
            
            # 초기 포지션 및 예약 주문 기록
            await self._record_startup_positions()
            await self._record_startup_plan_orders()
            await self._record_startup_gate_positions()
            
            # 예약 주문 초기 스냅샷 생성
            await self._create_initial_plan_order_snapshot()
            
            # 시작 시 기존 예약 주문 복제
            await self._mirror_startup_plan_orders()
            
            self.logger.info("✅ 포지션 매니저 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"포지션 매니저 초기화 실패: {e}")
            raise

    async def _record_existing_gate_position_sizes(self):
        """🔥🔥🔥 기존 게이트 포지션의 실제 크기 기록"""
        try:
            gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
            
            for pos in gate_positions:
                size = int(pos.get('size', 0))
                if size == 0:
                    continue
                
                # 포지션 ID 생성
                gate_pos_id = self._generate_gate_position_id(pos)
                
                # 실제 크기 기록
                self.gate_position_actual_sizes[gate_pos_id] = size
                
                # 마진 정보 기록 (추정)
                entry_price = float(pos.get('entry_price', self.gate_current_price or 50000))
                estimated_margin = abs(size) * entry_price * 0.0001 / 10  # 10배 레버리지 가정
                self.gate_position_actual_margins[gate_pos_id] = estimated_margin
                
                # 상세 정보 기록
                self.position_entry_info[gate_pos_id] = {
                    'gate_size': size,
                    'gate_margin': estimated_margin,
                    'entry_price': entry_price,
                    'side': 'long' if size > 0 else 'short',
                    'created_at': datetime.now().isoformat(),
                    'is_existing': True
                }
                
                self.logger.info(f"🔍 기존 게이트 포지션 크기 기록: {gate_pos_id} → 크기={size}, 마진=${estimated_margin:.2f}")
            
        except Exception as e:
            self.logger.error(f"기존 게이트 포지션 크기 기록 실패: {e}")

    async def monitor_plan_orders_cycle(self):
        """🔥🔥🔥 예약 주문 모니터링 사이클 - 시세 차이 지연 제거"""
        try:
            if not self.startup_plan_orders_processed:
                await asyncio.sleep(0.1)
                return
            
            # 🔥🔥🔥 시세 차이 체크 제거 - 모든 상황에서 즉시 처리
            self.logger.debug("예약 주문 모니터링 - 시세 차이와 무관하게 즉시 처리")
            
            # 만료된 타임스탬프 정리
            await self._cleanup_expired_timestamps()
            
            # 해시 기반 중복 방지 시스템 정리
            await self._cleanup_expired_hashes()
            
            # 포지션 종료 시 클로즈 주문 자동 정리
            await self._check_and_cleanup_close_orders_if_no_position()
            
            # 현재 비트겟 예약 주문 조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            current_plan_orders = plan_data.get('plan_orders', [])
            current_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            # 클로즈 주문 정확하게 필터링
            orders_to_monitor = []
            orders_to_monitor.extend(current_plan_orders)
            
            # TP/SL 주문 중에서 클로즈 주문만 추가
            for tp_sl_order in current_tp_sl_orders:
                close_details = await self.utils.determine_close_order_details(tp_sl_order)
                if close_details['is_close_order']:
                    orders_to_monitor.append(tp_sl_order)
            
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
            
            # 취소된 예약 주문 감지 및 처리
            canceled_order_ids = self.last_plan_order_ids - current_order_ids
            
            if canceled_order_ids:
                self.logger.info(f"{len(canceled_order_ids)}개의 예약 주문 취소 감지")
                
                for canceled_order_id in canceled_order_ids:
                    await self._handle_plan_order_cancel(canceled_order_id)
                
                self.daily_stats['plan_order_cancels'] += len(canceled_order_ids)
            
            # 새로운 예약 주문 감지
            new_orders_count = 0
            new_close_orders_count = 0
            perfect_mirrors = 0
            
            for order in orders_to_monitor:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if not order_id:
                    continue
                
                # 강화된 중복 처리 방지
                if await self._is_order_recently_processed_enhanced(order_id, order):
                    continue
                
                # 이미 처리된 주문은 스킵
                if order_id in self.processed_plan_orders:
                    continue
                
                # 시작 시 존재했던 주문인지 확인
                if order_id in self.startup_plan_orders:
                    self.processed_plan_orders.add(order_id)
                    continue
                
                # 주문 처리 락 확보
                if order_id not in self.order_processing_locks:
                    self.order_processing_locks[order_id] = asyncio.Lock()
                
                async with self.order_processing_locks[order_id]:
                    # 락 내에서 다시 중복 체크
                    if order_id in self.processed_plan_orders:
                        continue
                    
                    # 강화된 중복 복제 확인
                    is_duplicate = await self._is_duplicate_order_enhanced(order)
                    if is_duplicate:
                        self.daily_stats['duplicate_orders_prevented'] += 1
                        self.logger.info(f"🛡️ 중복 감지로 스킵: {order_id}")
                        self.processed_plan_orders.add(order_id)
                        continue
                    
                    # 새로운 예약 주문 처리
                    try:
                        # 클로즈 주문 상세 분석
                        close_details = await self.utils.determine_close_order_details(order)
                        is_close_order = close_details['is_close_order']
                        
                        # 클로즈 주문인 경우 현재 포지션 상태 확인
                        if is_close_order:
                            position_check_result = await self._check_close_order_validity_enhanced(order, close_details)
                            if position_check_result == "skip_no_position":
                                self.logger.warning(f"⏭️ 클로즈 주문이지만 해당 포지션 없음, 스킵: {order_id}")
                                self.processed_plan_orders.add(order_id)
                                continue
                        
                        # 🔥🔥🔥 클로즈 주문과 오픈 주문을 구분하여 처리
                        if is_close_order:
                            result = await self._process_close_order_with_position_matching(order, close_details)
                        else:
                            result = await self._process_perfect_mirror_order(order)
                        
                        if result == "perfect_success":
                            new_orders_count += 1
                            perfect_mirrors += 1
                            self.daily_stats['perfect_mirrors'] += 1
                            if is_close_order:
                                new_close_orders_count += 1
                                self.daily_stats['close_order_mirrors'] += 1
                        elif result == "partial_success":
                            new_orders_count += 1
                            self.daily_stats['partial_mirrors'] += 1
                            if is_close_order:
                                new_close_orders_count += 1
                                self.daily_stats['close_order_mirrors'] += 1
                        elif result == "skipped" and is_close_order:
                            self.daily_stats['close_order_skipped'] += 1
                        
                        self.processed_plan_orders.add(order_id)
                        
                        # 주문 처리 해시 기록 (중복 방지)
                        await self._record_order_processing_hash(order_id, order)
                        
                    except Exception as e:
                        self.logger.error(f"새로운 예약 주문 복제 실패: {order_id} - {e}")
                        self.processed_plan_orders.add(order_id)
                        
                        await self.telegram.send_message(
                            f"❌ 예약 주문 복제 실패\n"
                            f"비트겟 ID: {order_id}\n"
                            f"오류: {str(e)[:200]}"
                        )
            
            # 완벽한 미러링 성공 시 알림
            if perfect_mirrors > 0:
                await self.telegram.send_message(
                    f"✅ 완벽한 TP/SL 미러링 성공\n"
                    f"완벽 복제: {perfect_mirrors}개\n"
                    f"클로즈 주문: {new_close_orders_count}개\n"
                    f"전체 신규: {new_orders_count}개\n"
                    f"🔥 시세 차이와 무관하게 즉시 처리됨"
                )
            
            # 현재 상태를 다음 비교를 위해 저장
            self.last_plan_order_ids = current_order_ids.copy()
            self.plan_order_snapshot = current_snapshot.copy()
            
            # 오래된 주문 ID 정리
            if len(self.processed_plan_orders) > 500:
                recent_orders = list(self.processed_plan_orders)[-250:]
                self.processed_plan_orders = set(recent_orders)
                
        except Exception as e:
            self.logger.error(f"예약 주문 모니터링 사이클 오류: {e}")

    async def _process_close_order_with_position_matching(self, bitget_order: Dict, close_details: Dict) -> str:
        """🔥🔥🔥 포지션 크기 매칭을 통한 클로즈 주문 처리"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            position_side = close_details['position_side']  # 'long' 또는 'short'
            
            self.logger.info(f"🎯 포지션 매칭 클로즈 주문 처리: {order_id} (포지션: {position_side})")
            
            # 현재 게이트 포지션 조회
            gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
            
            if not gate_positions:
                self.logger.warning(f"⚠️ 게이트에 포지션이 없어 클로즈 주문 스킵: {order_id}")
                return "skipped"
            
            gate_position = gate_positions[0]
            current_gate_size = int(gate_position.get('size', 0))
            
            if current_gate_size == 0:
                self.logger.warning(f"⚠️ 게이트 포지션 크기가 0이어 클로즈 주문 스킵: {order_id}")
                return "skipped"
            
            # 포지션 방향 확인
            current_position_side = 'long' if current_gate_size > 0 else 'short'
            
            if current_position_side != position_side:
                self.logger.warning(f"⚠️ 포지션 방향 불일치: 현재={current_position_side}, 예상={position_side}")
                # 방향이 다르더라도 현재 포지션에 맞게 클로즈 주문 생성
                actual_position_side = current_position_side
                actual_gate_size = abs(current_gate_size)
            else:
                actual_position_side = position_side
                actual_gate_size = abs(current_gate_size)
            
            # 🔥🔥🔥 현재 게이트 포지션 크기를 기준으로 클로즈 주문 생성
            self.logger.info(f"🎯 현재 게이트 포지션 기준 클로즈 주문 생성: 크기={actual_gate_size}, 포지션={actual_position_side}")
            
            # 트리거 가격 추출
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price == 0:
                return "failed"
            
            # 비트겟 레버리지 정보 추출
            bitget_leverage = 10  # 기본값
            order_leverage = bitget_order.get('leverage')
            if order_leverage:
                try:
                    bitget_leverage = int(float(order_leverage))
                except:
                    pass
            
            # 레버리지 설정
            try:
                await self.gate_mirror.set_leverage(self.GATE_CONTRACT, bitget_leverage)
            except Exception as e:
                self.logger.error(f"레버리지 설정 실패하지만 계속 진행: {e}")
            
            # Gate 미러링 클라이언트로 포지션 크기 기반 클로즈 주문 생성
            mirror_result = await self.gate_mirror.create_perfect_tp_sl_order(
                bitget_order=bitget_order,
                gate_size=actual_gate_size,  # 🔥🔥🔥 현재 포지션 크기 사용
                gate_margin=0,  # 클로즈 주문이므로 마진 불필요
                leverage=bitget_leverage,
                current_gate_price=self.gate_current_price
            )
            
            if not mirror_result['success']:
                self.daily_stats['failed_mirrors'] += 1
                return "failed"
            
            gate_order_id = mirror_result['gate_order_id']
            
            # 주문 ID 매핑 기록
            if order_id and gate_order_id:
                self.bitget_to_gate_order_mapping[order_id] = gate_order_id
                self.gate_to_bitget_order_mapping[gate_order_id] = order_id
                self.logger.info(f"클로즈 주문 매핑 기록: {order_id} ↔ {gate_order_id}")
            
            # 미러링 성공 기록
            self.mirrored_plan_orders[order_id] = {
                'gate_order_id': gate_order_id,
                'bitget_order': bitget_order,
                'gate_order': mirror_result['gate_order'],
                'created_at': datetime.now().isoformat(),
                'margin': 0,  # 클로즈 주문
                'size': actual_gate_size,
                'margin_ratio': 0,  # 클로즈 주문
                'leverage': bitget_leverage,
                'trigger_price': trigger_price,
                'has_tp_sl': mirror_result.get('has_tp_sl', False),
                'tp_price': mirror_result.get('tp_price'),
                'sl_price': mirror_result.get('sl_price'),
                'actual_tp_price': mirror_result.get('actual_tp_price'),
                'actual_sl_price': mirror_result.get('actual_sl_price'),
                'is_close_order': True,
                'reduce_only': True,
                'perfect_mirror': mirror_result.get('perfect_mirror', False),
                'close_details': close_details,
                'position_matched': True,  # 포지션 매칭 표시
                'original_position_size': current_gate_size  # 원본 포지션 크기 기록
            }
            
            self.daily_stats['plan_order_mirrors'] += 1
            self.daily_stats['position_size_corrections'] += 1
            
            # TP/SL 통계 업데이트
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
            
            # 🔥🔥🔥 시세 차이 정보도 포함하되 처리에는 영향 없음을 명시
            price_diff = abs(self.bitget_current_price - self.gate_current_price)
            
            await self.telegram.send_message(
                f"✅ 포지션 매칭 클로즈 주문 {perfect_status} 미러링 성공\n"
                f"비트겟 ID: {order_id}\n"
                f"게이트 ID: {gate_order_id}\n"
                f"트리거가: ${trigger_price:,.2f}\n"
                f"🔄 포지션 기반 크기 조정:\n"
                f"현재 게이트 포지션: {current_gate_size} ({actual_position_side})\n"
                f"클로즈 주문 크기: {actual_gate_size}\n"
                f"시세 차이: ${price_diff:.2f} (처리 완료){tp_sl_info}"
            )
            
            return "perfect_success" if mirror_result.get('perfect_mirror') else "partial_success"
            
        except Exception as e:
            self.logger.error(f"포지션 매칭 클로즈 주문 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'plan_order_id': bitget_order.get('orderId', bitget_order.get('planOrderId', 'unknown')),
                'type': 'close_order_position_matching'
            })
            return "failed"

    async def _check_and_cleanup_close_orders_if_no_position(self):
        """포지션이 없으면 게이트의 클로즈 주문들을 자동 정리"""
        try:
            current_time = datetime.now()
            
            # 30초마다만 체크
            if (current_time - self.last_position_check).total_seconds() < self.position_check_interval:
                return
            
            self.last_position_check = current_time
            
            if not self.position_close_monitoring:
                return
            
            # 현재 게이트 포지션 상태 확인
            gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
            has_position = any(pos.get('size', 0) != 0 for pos in gate_positions)
            
            if has_position:
                return
            
            # 포지션이 없으면 게이트의 클로즈 주문들 찾기
            gate_orders = await self.gate_mirror.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            close_orders_to_delete = []
            
            for gate_order in gate_orders:
                try:
                    initial_info = gate_order.get('initial', {})
                    reduce_only = initial_info.get('reduce_only', False)
                    
                    if reduce_only:
                        close_orders_to_delete.append(gate_order)
                        
                except Exception as e:
                    self.logger.debug(f"게이트 주문 분석 중 오류: {e}")
                    continue
            
            if close_orders_to_delete:
                self.logger.info(f"🗑️ 포지션 없음 → {len(close_orders_to_delete)}개 클로즈 주문 자동 정리 시작")
                
                deleted_count = 0
                for close_order in close_orders_to_delete:
                    try:
                        gate_order_id = close_order.get('id')
                        if gate_order_id:
                            await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                            deleted_count += 1
                            
                            # 미러링 기록에서도 제거
                            bitget_order_id = self.gate_to_bitget_order_mapping.get(gate_order_id)
                            if bitget_order_id:
                                if bitget_order_id in self.mirrored_plan_orders:
                                    del self.mirrored_plan_orders[bitget_order_id]
                                del self.gate_to_bitget_order_mapping[gate_order_id]
                                if bitget_order_id in self.bitget_to_gate_order_mapping:
                                    del self.bitget_to_gate_order_mapping[bitget_order_id]
                            
                            self.logger.info(f"✅ 클로즈 주문 삭제 완료: {gate_order_id}")
                            
                    except Exception as e:
                        error_msg = str(e).lower()
                        if any(keyword in error_msg for keyword in [
                            "not found", "order not exist", "invalid order",
                            "order does not exist", "auto_order_not_found"
                        ]):
                            deleted_count += 1
                            self.logger.info(f"클로즈 주문이 이미 처리됨: {gate_order_id}")
                        else:
                            self.logger.error(f"클로즈 주문 삭제 실패: {gate_order_id} - {e}")
                
                if deleted_count > 0:
                    self.daily_stats['auto_close_order_cleanups'] += deleted_count
                    self.daily_stats['position_closed_cleanups'] += 1
                    
                    await self.telegram.send_message(
                        f"🗑️ 자동 클로즈 주문 정리 완료\n"
                        f"포지션 상태: 없음 (모두 익절/손절됨)\n"
                        f"정리된 클로즈 주문: {deleted_count}개\n"
                        f"게이트가 깔끔하게 정리되었습니다! ✨"
                    )
                    
                    # 🔥🔥🔥 포지션 종료 시 관련 기록도 정리
                    await self._cleanup_position_records_after_close()
                    
                    self.logger.info(f"🎯 포지션 종료로 인한 클로즈 주문 자동 정리 완료: {deleted_count}개")
            
        except Exception as e:
            self.logger.error(f"포지션 없음 시 클로즈 주문 정리 실패: {e}")

    async def _cleanup_position_records_after_close(self):
        """🔥🔥🔥 포지션 종료 후 관련 기록 정리"""
        try:
            # 게이트 포지션 크기 기록 정리
            keys_to_remove = list(self.gate_position_actual_sizes.keys())
            for key in keys_to_remove:
                del self.gate_position_actual_sizes[key]
                if key in self.gate_position_actual_margins:
                    del self.gate_position_actual_margins[key]
                if key in self.position_entry_info:
                    del self.position_entry_info[key]
            
            self.logger.info(f"🧹 포지션 종료 후 기록 정리 완료: {len(keys_to_remove)}개 기록 제거")
            
        except Exception as e:
            self.logger.error(f"포지션 종료 후 기록 정리 실패: {e}")

    async def _process_perfect_mirror_order(self, bitget_order: Dict) -> str:
        """완벽한 미러링 주문 처리 (오픈 주문용)"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            
            # 클로즈 주문 상세 분석
            close_details = await self.utils.determine_close_order_details(bitget_order)
            is_close_order = close_details['is_close_order']
            order_direction = close_details['order_direction']
            position_side = close_details['position_side']
            
            self.logger.info(f"🎯 완벽한 미러링 시작: {order_id}")
            self.logger.info(f"   클로즈 주문: {is_close_order}")
            self.logger.info(f"   주문 방향: {order_direction} (포지션: {position_side})")
            
            # 트리거 가격 추출
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price == 0:
                return "failed"
            
            # 크기 정보 추출
            size = float(bitget_order.get('size', 0))
            if size == 0:
                return "failed"
            
            # 실제 달러 마진 비율 계산
            margin_ratio_result = await self.utils.calculate_dynamic_margin_ratio(
                size, trigger_price, bitget_order
            )
            
            if not margin_ratio_result['success']:
                return "failed"
            
            margin_ratio = margin_ratio_result['margin_ratio']
            bitget_leverage = margin_ratio_result['leverage']
            
            # 레버리지 설정
            try:
                await self.gate_mirror.set_leverage("BTC_USDT", bitget_leverage)
            except Exception as e:
                self.logger.error(f"레버리지 설정 실패하지만 계속 진행: {e}")
            
            # 게이트 계정 정보
            gate_account = await self.gate_mirror.get_account_balance()
            gate_total_equity = float(gate_account.get('total', 0))
            gate_available = float(gate_account.get('available', 0))
            
            # 게이트에서 동일한 마진 비율로 투입할 실제 달러 금액 계산
            gate_margin = gate_total_equity * margin_ratio
            
            if gate_margin > gate_available:
                gate_margin = gate_available * 0.95
            
            if gate_margin < self.MIN_MARGIN:
                return "failed"
            
            # 게이트 계약 수 계산
            gate_notional_value = gate_margin * bitget_leverage
            gate_size = int(gate_notional_value / (trigger_price * 0.0001))
            
            if gate_size == 0:
                gate_size = 1
            
            # Gate 미러링 클라이언트로 완벽한 미러링 주문 생성
            mirror_result = await self.gate_mirror.create_perfect_tp_sl_order(
                bitget_order=bitget_order,
                gate_size=gate_size,
                gate_margin=gate_margin,
                leverage=bitget_leverage,
                current_gate_price=self.gate_current_price
            )
            
            if not mirror_result['success']:
                self.daily_stats['failed_mirrors'] += 1
                return "failed"
            
            gate_order_id = mirror_result['gate_order_id']
            
            # 주문 ID 매핑 기록
            if order_id and gate_order_id:
                self.bitget_to_gate_order_mapping[order_id] = gate_order_id
                self.gate_to_bitget_order_mapping[gate_order_id] = order_id
                self.logger.info(f"주문 매핑 기록: {order_id} ↔ {gate_order_id}")
            
            # 🔥🔥🔥 오픈 주문인 경우 포지션 진입 정보 기록
            if not is_close_order:
                position_id = f"{self.GATE_CONTRACT}_{position_side}_{trigger_price}"
                self.gate_position_actual_sizes[position_id] = gate_size
                self.gate_position_actual_margins[position_id] = gate_margin
                self.position_entry_info[position_id] = {
                    'gate_size': gate_size,
                    'gate_margin': gate_margin,
                    'entry_price': trigger_price,
                    'side': position_side,
                    'bitget_order_id': order_id,
                    'gate_order_id': gate_order_id,
                    'leverage': bitget_leverage,
                    'margin_ratio': margin_ratio,
                    'created_at': datetime.now().isoformat(),
                    'is_existing': False
                }
                self.logger.info(f"🔰 오픈 주문 포지션 진입 정보 기록: {position_id}")
            
            # 미러링 성공 기록
            self.mirrored_plan_orders[order_id] = {
                'gate_order_id': gate_order_id,
                'bitget_order': bitget_order,
                'gate_order': mirror_result['gate_order'],
                'created_at': datetime.now().isoformat(),
                'margin': gate_margin,
                'size': gate_size,
                'margin_ratio': margin_ratio,
                'leverage': bitget_leverage,
                'trigger_price': trigger_price,
                'has_tp_sl': mirror_result.get('has_tp_sl', False),
                'tp_price': mirror_result.get('tp_price'),
                'sl_price': mirror_result.get('sl_price'),
                'actual_tp_price': mirror_result.get('actual_tp_price'),
                'actual_sl_price': mirror_result.get('actual_sl_price'),
                'is_close_order': mirror_result.get('is_close_order', False),
                'reduce_only': mirror_result.get('reduce_only', False),
                'perfect_mirror': mirror_result.get('perfect_mirror', False),
                'close_details': close_details
            }
            
            self.daily_stats['plan_order_mirrors'] += 1
            
            # TP/SL 통계 업데이트
            if mirror_result.get('has_tp_sl', False):
                self.daily_stats['tp_sl_success'] += 1
            elif mirror_result.get('tp_price') or mirror_result.get('sl_price'):
                self.daily_stats['tp_sl_failed'] += 1
            
            # 성공 메시지
            order_type = "클로즈 주문" if mirror_result.get('is_close_order') else "예약 주문"
            perfect_status = "완벽" if mirror_result.get('perfect_mirror') else "부분"
            
            close_info = ""
            if is_close_order:
                close_info = f"\n🔴 클로즈 주문: {order_direction} (원래 포지션: {position_side})"
            
            tp_sl_info = ""
            if mirror_result.get('has_tp_sl'):
                tp_sl_info = f"\n\n🎯 TP/SL 완벽 미러링:"
                if mirror_result.get('actual_tp_price'):
                    tp_sl_info += f"\n✅ TP: ${mirror_result['actual_tp_price']}"
                if mirror_result.get('actual_sl_price'):
                    tp_sl_info += f"\n✅ SL: ${mirror_result['actual_sl_price']}"
            elif mirror_result.get('tp_price') or mirror_result.get('sl_price'):
                tp_sl_info = f"\n\n⚠️ TP/SL 설정 실패:"
                if mirror_result.get('tp_price'):
                    tp_sl_info += f"\n❌ TP 요청: ${mirror_result['tp_price']:.2f}"
                if mirror_result.get('sl_price'):
                    tp_sl_info += f"\n❌ SL 요청: ${mirror_result['sl_price']:.2f}"
            
            # 🔥🔥🔥 시세 차이 정보도 포함하되 처리에는 영향 없음을 명시
            price_diff = abs(self.bitget_current_price - self.gate_current_price)
            
            await self.telegram.send_message(
                f"✅ {order_type} {perfect_status} 미러링 성공\n"
                f"비트겟 ID: {order_id}\n"
                f"게이트 ID: {gate_order_id}\n"
                f"트리거가: ${trigger_price:,.2f}\n"
                f"게이트 수량: {gate_size}{close_info}\n"
                f"시세 차이: ${price_diff:.2f} (처리 완료)\n\n"
                f"💰 마진 비율 복제:\n"
                f"마진 비율: {margin_ratio*100:.2f}%\n"
                f"게이트 투입 마진: ${gate_margin:,.2f}\n"
                f"레버리지: {bitget_leverage}x{tp_sl_info}"
            )
            
            return "perfect_success" if mirror_result.get('perfect_mirror') else "partial_success"
            
        except Exception as e:
            self.logger.error(f"완벽한 미러링 주문 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'plan_order_id': bitget_order.get('orderId', bitget_order.get('planOrderId', 'unknown'))
            })
            return "failed"

    async def _handle_plan_order_cancel(self, bitget_order_id: str):
        """예약 주문 취소 처리"""
        try:
            self.logger.info(f"🚫 예약 주문 취소 처리 시작: {bitget_order_id}")
            
            # 미러링된 주문인지 확인
            if bitget_order_id not in self.mirrored_plan_orders:
                self.logger.info(f"미러링되지 않은 주문이므로 취소 처리 스킵: {bitget_order_id}")
                return
            
            mirror_info = self.mirrored_plan_orders[bitget_order_id]
            gate_order_id = mirror_info.get('gate_order_id')
            
            if not gate_order_id:
                self.logger.warning(f"게이트 주문 ID가 없음: {bitget_order_id}")
                del self.mirrored_plan_orders[bitget_order_id]
                return
            
            # 게이트에서 주문 상태 먼저 확인
            try:
                gate_orders = await self.gate_mirror.get_price_triggered_orders("BTC_USDT", "open")
                gate_order_exists = any(order.get('id') == gate_order_id for order in gate_orders)
                
                if not gate_order_exists:
                    self.logger.info(f"게이트 주문이 이미 없음 (체결되었거나 취소됨): {gate_order_id}")
                    success = True
                else:
                    # 게이트에서 예약 주문 취소
                    await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                    success = True
                    
            except Exception as cancel_error:
                error_msg = str(cancel_error).lower()
                
                if any(keyword in error_msg for keyword in [
                    "not found", "order not exist", "invalid order", 
                    "order does not exist", "auto_order_not_found",
                    "order_not_found", "not_found"
                ]):
                    success = True
                    self.logger.info(f"게이트 주문이 이미 처리됨: {gate_order_id}")
                else:
                    success = False
                    self.logger.error(f"게이트 주문 취소 실패: {cancel_error}")
            
            # 결과 처리
            if success:
                await self.telegram.send_message(
                    f"🚫✅ 예약 주문 취소 동기화 완료\n"
                    f"비트겟 ID: {bitget_order_id}\n"
                    f"게이트 ID: {gate_order_id}"
                )
            else:
                await self.telegram.send_message(
                    f"❌ 예약 주문 취소 실패\n"
                    f"비트겟 ID: {bitget_order_id}\n"
                    f"게이트 ID: {gate_order_id}\n"
                    f"재시도가 필요할 수 있습니다."
                )
            
            # 미러링 기록에서 제거
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]
            
            # 주문 매핑에서 제거
            if bitget_order_id in self.bitget_to_gate_order_mapping:
                gate_id = self.bitget_to_gate_order_mapping[bitget_order_id]
                del self.bitget_to_gate_order_mapping[bitget_order_id]
                if gate_id in self.gate_to_bitget_order_mapping:
                    del self.gate_to_bitget_order_mapping[gate_id]
                
        except Exception as e:
            self.logger.error(f"예약 주문 취소 처리 중 예외 발생: {e}")
            
            # 오류 발생 시에도 미러링 기록에서 제거
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]

    # === 강화된 중복 방지 헬퍼 메서드들 ===
    
    async def _cleanup_expired_timestamps(self):
        """만료된 타임스탬프 정리"""
        try:
            current_time = datetime.now()
            
            expired_orders = []
            for order_id, timestamp in self.recently_processed_orders.items():
                if (current_time - timestamp).total_seconds() > self.order_deduplication_window:
                    expired_orders.append(order_id)
            
            for order_id in expired_orders:
                del self.recently_processed_orders[order_id]
                if order_id in self.order_processing_locks:
                    del self.order_processing_locks[order_id]
            
            # 게이트 기존 주문 상세 정보도 정리
            expired_gate_orders = []
            for order_id, details in self.gate_existing_orders_detailed.items():
                recorded_at_str = details.get('recorded_at', '')
                if recorded_at_str:
                    try:
                        recorded_at = datetime.fromisoformat(recorded_at_str)
                        if (current_time - recorded_at).total_seconds() > 600:  # 10분 후 만료
                            expired_gate_orders.append(order_id)
                    except:
                        expired_gate_orders.append(order_id)
                else:
                    expired_gate_orders.append(order_id)
            
            for order_id in expired_gate_orders:
                del self.gate_existing_orders_detailed[order_id]
                
        except Exception as e:
            self.logger.error(f"타임스탬프 정리 실패: {e}")

    async def _cleanup_expired_hashes(self):
        """만료된 해시 정리"""
        try:
            current_time = datetime.now()
            
            expired_hashes = []
            for order_hash, timestamp in self.order_hash_timestamps.items():
                if (current_time - timestamp).total_seconds() > self.hash_cleanup_interval:
                    expired_hashes.append(order_hash)
            
            for order_hash in expired_hashes:
                del self.order_hash_timestamps[order_hash]
                if order_hash in self.processed_order_hashes:
                    self.processed_order_hashes.remove(order_hash)
                    
        except Exception as e:
            self.logger.error(f"해시 정리 실패: {e}")

    async def _is_order_recently_processed_enhanced(self, order_id: str, order: Dict) -> bool:
        """강화된 최근 처리 주문 확인"""
        try:
            # 1. 기본 시간 기반 확인
            if order_id in self.recently_processed_orders:
                time_diff = (datetime.now() - self.recently_processed_orders[order_id]).total_seconds()
                if time_diff < self.order_deduplication_window:
                    return True
                else:
                    del self.recently_processed_orders[order_id]
            
            # 2. 해시 기반 확인
            order_hashes = await self._generate_order_hashes(order)
            for order_hash in order_hashes:
                if order_hash in self.processed_order_hashes:
                    self.logger.debug(f"해시 기반 중복 감지: {order_hash}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"강화된 최근 처리 확인 실패: {e}")
            return False

    async def _is_duplicate_order_enhanced(self, bitget_order: Dict) -> bool:
        """강화된 중복 주문 확인"""
        try:
            # 1. 기본 중복 체크 로직
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            # 2. 가격 기반 중복 확인 - 더 관대한 범위로 수정
            if trigger_price > 0:
                price_key = f"BTC_USDT_{trigger_price:.2f}"
                if price_key in self.mirrored_trigger_prices:
                    return True
                
                # 🔥🔥🔥 더 관대한 가격 범위 확인 (±5달러)
                for offset in [-5, -2, -1, -0.5, 0.5, 1, 2, 5]:
                    adjusted_price = trigger_price + offset
                    adjusted_key = f"BTC_USDT_{adjusted_price:.2f}"
                    if adjusted_key in self.mirrored_trigger_prices:
                        return True
            
            # 3. 해시 기반 고급 중복 확인
            order_hashes = await self._generate_order_hashes(bitget_order)
            for order_hash in order_hashes:
                if order_hash in self.gate_existing_order_hashes:
                    self.logger.debug(f"게이트 기존 주문 해시와 중복: {order_hash}")
                    return True
                if order_hash in self.processed_order_hashes:
                    self.logger.debug(f"처리된 주문 해시와 중복: {order_hash}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"강화된 중복 주문 확인 실패: {e}")
            return False

    async def _generate_order_hashes(self, order: Dict) -> List[str]:
        """주문 해시 생성"""
        try:
            # utils 클래스의 해시 생성 기능 활용
            order_details = {
                'contract': self.GATE_CONTRACT,
                'trigger_price': 0,
                'size': 0,
                'abs_size': 0
            }
            
            # 트리거 가격 추출
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if order.get(price_field):
                    order_details['trigger_price'] = float(order.get(price_field))
                    break
            
            # 크기 추출
            size = order.get('size', 0)
            if size:
                order_details['size'] = int(float(size))
                order_details['abs_size'] = abs(int(float(size)))
            
            # TP/SL 정보 추출
            tp_price, sl_price = await self.utils.extract_tp_sl_from_bitget_order(order)
            if tp_price or sl_price:
                order_details['has_tp_sl'] = True
                order_details['tp_price'] = tp_price
                order_details['sl_price'] = sl_price
            
            return await self.utils.generate_multiple_order_hashes(order_details)
            
        except Exception as e:
            self.logger.error(f"주문 해시 생성 실패: {e}")
            return []

    async def _record_order_processing_hash(self, order_id: str, order: Dict):
        """주문 처리 해시 기록"""
        try:
            current_time = datetime.now()
            self.recently_processed_orders[order_id] = current_time
            
            # 해시 기록
            order_hashes = await self._generate_order_hashes(order)
            for order_hash in order_hashes:
                self.processed_order_hashes.add(order_hash)
                self.order_hash_timestamps[order_hash] = current_time
            
            # 가격 기반 중복 방지 기록
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if order.get(price_field):
                    trigger_price = float(order.get(price_field))
                    break
            
            if trigger_price > 0:
                price_key = f"BTC_USDT_{trigger_price:.2f}"
                self.mirrored_trigger_prices.add(price_key)
            
        except Exception as e:
            self.logger.error(f"주문 처리 해시 기록 실패: {e}")

    async def _check_close_order_validity_enhanced(self, order: Dict, close_details: Dict) -> str:
        """강화된 클로즈 주문 유효성 확인"""
        try:
            # 현재 게이트 포지션 확인
            gate_positions = await self.gate_mirror.get_positions("BTC_USDT")
            
            if not gate_positions:
                self.logger.warning(f"🔍 게이트에 포지션이 전혀 없음")
                return "skip_no_position"
            
            position = gate_positions[0]
            position_size = int(position.get('size', 0))
            
            if position_size == 0:
                self.logger.warning(f"🔍 게이트 포지션 크기가 0")
                return "skip_no_position"
            
            # 클로즈 주문과 포지션 방향 매칭 확인
            current_position_side = 'long' if position_size > 0 else 'short'
            expected_position_side = close_details.get('position_side', '')
            
            if current_position_side != expected_position_side:
                self.logger.warning(f"🔍 포지션 방향 불일치: 현재={current_position_side}, 예상={expected_position_side}")
            
            self.logger.info(f"✅ 클로즈 주문 유효성 확인 완료: 포지션={current_position_side}, 크기={position_size}")
            return "proceed"
            
        except Exception as e:
            self.logger.error(f"강화된 클로즈 주문 유효성 확인 실패: {e}")
            return "proceed"

    # === 기존 헬퍼 메서드들 (시세 차이 지연 제거) ===

    async def process_filled_order(self, order: Dict):
        """🔥🔥🔥 체결된 주문으로부터 미러링 실행 - 시세 차이 대기 제거"""
        try:
            order_id = order.get('orderId', order.get('id', ''))
            side = order.get('side', '').lower()
            size = float(order.get('size', 0))
            fill_price = float(order.get('fillPrice', order.get('price', 0)))
            
            position_side = 'long' if side == 'buy' else 'short'
            
            # 렌더 재구동 시 기존 포지션 중복 방지
            synthetic_position = {
                'symbol': self.SYMBOL,
                'holdSide': position_side,
                'total': str(size),
                'openPriceAvg': str(fill_price),
                'markPrice': str(fill_price),
                'marginSize': '0',
                'leverage': '10',
                'marginMode': 'crossed',
                'unrealizedPL': '0'
            }
            
            if await self._should_skip_position_due_to_existing(synthetic_position):
                self.logger.info(f"🔄 렌더 재구동: 동일 포지션 존재로 주문 체결 미러링 스킵 - {order_id}")
                return
            
            # 🔥🔥🔥 시세 차이 확인 및 대기 로직 완전 제거 - 즉시 처리
            price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
            self.logger.info(f"주문 체결 미러링 즉시 처리: {order_id}, 시세 차이: ${price_diff_abs:.2f}")
            
            margin_ratio_result = await self.utils.calculate_dynamic_margin_ratio(
                size, fill_price, order
            )
            
            if not margin_ratio_result['success']:
                return
            
            leverage = margin_ratio_result['leverage']
            
            synthetic_position.update({
                'marginSize': str(margin_ratio_result['required_margin']),
                'leverage': str(leverage)
            })
            
            pos_id = f"{self.SYMBOL}_{position_side}_{fill_price}"
            
            if pos_id in self.startup_positions or pos_id in self.mirrored_positions:
                return
            
            result = await self._mirror_new_position(synthetic_position)
            
            if result.success:
                self.mirrored_positions[pos_id] = await self.utils.create_position_info(synthetic_position)
                self.position_sizes[pos_id] = size
                
                # 🔥🔥🔥 게이트 포지션 크기 기록
                gate_pos_id = f"{self.GATE_CONTRACT}_{position_side}_{fill_price}"
                gate_size = int(size * 10000)
                if position_side == 'short':
                    gate_size = -gate_size
                
                self.gate_position_actual_sizes[gate_pos_id] = gate_size
                self.gate_position_actual_margins[gate_pos_id] = margin_ratio_result['required_margin']
                self.position_entry_info[gate_pos_id] = {
                    'gate_size': gate_size,
                    'gate_margin': margin_ratio_result['required_margin'],
                    'entry_price': fill_price,
                    'side': position_side,
                    'leverage': leverage,
                    'created_at': datetime.now().isoformat(),
                    'is_existing': False,
                    'from_filled_order': True,
                    'bitget_order_id': order_id
                }
                
                self.daily_stats['successful_mirrors'] += 1
                self.daily_stats['order_mirrors'] += 1
                
                await self.telegram.send_message(
                    f"⚡ 실시간 주문 체결 미러링 성공\n"
                    f"주문 ID: {order_id}\n"
                    f"방향: {position_side}\n"
                    f"체결가: ${fill_price:,.2f}\n"
                    f"수량: {size}\n"
                    f"레버리지: {leverage}x\n"
                    f"시세 차이: ${price_diff_abs:.2f} (즉시 처리됨)\n"
                    f"실제 마진 비율: {margin_ratio_result['margin_ratio']*100:.2f}%\n"
                    f"🔰 게이트 포지션 기록: {gate_size}"
                )
            else:
                self.failed_mirrors.append(result)
                self.daily_stats['failed_mirrors'] += 1
                
                await self.telegram.send_message(
                    f"❌ 실시간 주문 체결 미러링 실패\n"
                    f"주문 ID: {order_id}\n"
                    f"오류: {result.error}"
                )
            
            self.daily_stats['total_mirrored'] += 1
            
        except Exception as e:
            self.logger.error(f"체결 주문 처리 중 오류: {e}")

    async def process_position(self, bitget_pos: Dict):
        """포지션 처리"""
        try:
            pos_id = self.utils.generate_position_id(bitget_pos)
            
            if pos_id in self.startup_positions:
                return
            
            if await self._should_skip_position_due_to_existing(bitget_pos):
                return
            
            current_size = float(bitget_pos.get('total', 0))
            
            if pos_id not in self.mirrored_positions:
                await asyncio.sleep(2)
                
                if pos_id not in self.mirrored_positions:
                    result = await self._mirror_new_position(bitget_pos)
                    
                    if result.success:
                        self.mirrored_positions[pos_id] = await self.utils.create_position_info(bitget_pos)
                        self.position_sizes[pos_id] = current_size
                        
                        # 🔥🔥🔥 게이트 포지션 크기 기록
                        position_side = bitget_pos.get('holdSide', '').lower()
                        entry_price = float(bitget_pos.get('openPriceAvg', 0))
                        gate_pos_id = f"{self.GATE_CONTRACT}_{position_side}_{entry_price}"
                        
                        gate_size = int(current_size * 10000)
                        if position_side == 'short':
                            gate_size = -gate_size
                        
                        margin_size = float(bitget_pos.get('marginSize', 0))
                        
                        self.gate_position_actual_sizes[gate_pos_id] = gate_size
                        self.gate_position_actual_margins[gate_pos_id] = margin_size
                        self.position_entry_info[gate_pos_id] = {
                            'gate_size': gate_size,
                            'gate_margin': margin_size,
                            'entry_price': entry_price,
                            'side': position_side,
                            'leverage': int(float(bitget_pos.get('leverage', 10))),
                            'created_at': datetime.now().isoformat(),
                            'is_existing': False,
                            'from_position': True
                        }
                        
                        self.daily_stats['successful_mirrors'] += 1
                        self.daily_stats['position_mirrors'] += 1
                        
                        leverage = bitget_pos.get('leverage', 'N/A')
                        await self.telegram.send_message(
                            f"✅ 포지션 기반 미러링 성공\n"
                            f"방향: {bitget_pos.get('holdSide', '')}\n"
                            f"진입가: ${float(bitget_pos.get('openPriceAvg', 0)):,.2f}\n"
                            f"레버리지: {leverage}x\n"
                            f"🔰 게이트 포지션 기록: {gate_size}"
                        )
                    else:
                        self.failed_mirrors.append(result)
                        self.daily_stats['failed_mirrors'] += 1
                    
                    self.daily_stats['total_mirrored'] += 1
            else:
                last_size = self.position_sizes.get(pos_id, 0)
                
                if current_size < last_size * 0.95:
                    reduction_ratio = 1 - (current_size / last_size)
                    await self._handle_partial_close(pos_id, bitget_pos, reduction_ratio)
                    self.position_sizes[pos_id] = current_size
                    self.daily_stats['partial_closes'] += 1
                
        except Exception as e:
            self.logger.error(f"포지션 처리 중 오류: {e}")

    async def handle_position_close(self, pos_id: str):
        """포지션 종료 처리"""
        try:
            result = await self.gate_mirror.close_position("BTC_USDT")
            
            # 상태 정리
            if pos_id in self.mirrored_positions:
                del self.mirrored_positions[pos_id]
            if pos_id in self.position_sizes:
                del self.position_sizes[pos_id]
            
            self.daily_stats['full_closes'] += 1
            
            await self.telegram.send_message(
                f"✅ 포지션 종료 완료\n포지션 ID: {pos_id}"
            )
            
        except Exception as e:
            self.logger.error(f"포지션 종료 처리 실패: {e}")

    async def check_sync_status(self) -> Dict:
        """동기화 상태 확인"""
        try:
            # 비트겟 포지션 조회
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            bitget_active = [
                pos for pos in bitget_positions 
                if float(pos.get('total', 0)) > 0
            ]
            
            # 게이트 포지션 조회
            gate_positions = await self.gate_mirror.get_positions("BTC_USDT")
            gate_active = [
                pos for pos in gate_positions 
                if pos.get('size', 0) != 0
            ]
            
            # 신규 포지션만 정확하게 카운팅
            new_bitget_positions = []
            for pos in bitget_active:
                pos_id = self.utils.generate_position_id(pos)
                if pos_id not in self.startup_positions:
                    new_bitget_positions.append(pos)
            
            # 게이트도 startup positions를 고려하여 계산
            new_gate_positions = []
            for pos in gate_active:
                gate_pos_id = self._generate_gate_position_id(pos)
                
                if gate_pos_id not in self.startup_gate_positions:
                    is_startup_match = await self._is_startup_position_match(pos)
                    if not is_startup_match:
                        new_gate_positions.append(pos)
            
            new_bitget_count = len(new_bitget_positions)
            new_gate_count = len(new_gate_positions)
            position_diff = new_bitget_count - new_gate_count
            
            return {
                'is_synced': position_diff == 0,
                'bitget_new_count': new_bitget_count,
                'gate_new_count': new_gate_count,
                'position_diff': position_diff,
                'bitget_total_count': len(bitget_active),
                'gate_total_count': len(gate_active),
                'price_diff': abs(self.bitget_current_price - self.gate_current_price)
            }
            
        except Exception as e:
            self.logger.error(f"동기화 상태 확인 실패: {e}")
            return {
                'is_synced': True,
                'bitget_new_count': 0,
                'gate_new_count': 0,
                'position_diff': 0,
                'bitget_total_count': 0,
                'gate_total_count': 0,
                'price_diff': 0
            }

    def _generate_gate_position_id(self, gate_pos: Dict) -> str:
        """게이트 포지션 ID 생성"""
        try:
            contract = gate_pos.get('contract', "BTC_USDT")
            size = gate_pos.get('size', 0)
            
            if isinstance(size, (int, float)) and size != 0:
                side = 'long' if size > 0 else 'short'
            else:
                side = 'unknown'
            
            entry_price = gate_pos.get('entry_price', self.gate_current_price or 0)
            
            return f"{contract}_{side}_{entry_price}"
            
        except Exception as e:
            self.logger.error(f"게이트 포지션 ID 생성 실패: {e}")
            return f"BTC_USDT_unknown_unknown"

    # === 초기화 헬퍼 메서드들 ===
    
    async def _check_existing_gate_positions(self):
        """렌더 재구동 시 기존 게이트 포지션 확인"""
        try:
            gate_positions = await self.gate_mirror.get_positions("BTC_USDT")
            
            self.existing_gate_positions = {
                'has_long': False,
                'has_short': False,
                'long_size': 0,
                'short_size': 0,
                'positions': gate_positions
            }
            
            for pos in gate_positions:
                size = int(pos.get('size', 0))
                if size > 0:
                    self.existing_gate_positions['has_long'] = True
                    self.existing_gate_positions['long_size'] = size
                elif size < 0:
                    self.existing_gate_positions['has_short'] = True
                    self.existing_gate_positions['short_size'] = abs(size)
            
            if self.existing_gate_positions['has_long'] or self.existing_gate_positions['has_short']:
                self.render_restart_detected = True
                self.logger.warning(f"🔄 렌더 재구동 감지: 기존 게이트 포지션 발견")
            else:
                self.render_restart_detected = False
                self.logger.info("✅ 새로운 시작: 기존 게이트 포지션 없음")
                
        except Exception as e:
            self.logger.error(f"기존 게이트 포지션 확인 실패: {e}")
            self.existing_gate_positions = {
                'has_long': False, 'has_short': False, 'long_size': 0, 'short_size': 0, 'positions': []
            }
            self.render_restart_detected = False

    async def _record_gate_existing_orders(self):
        """게이트 기존 예약 주문 기록"""
        try:
            gate_orders = await self.gate_mirror.get_price_triggered_orders("BTC_USDT", "open")
            
            for i, gate_order in enumerate(gate_orders):
                try:
                    order_details = await self.utils.extract_gate_order_details(gate_order)
                    
                    if order_details:
                        trigger_price = order_details['trigger_price']
                        price_key = f"BTC_USDT_{trigger_price:.2f}"
                        self.mirrored_trigger_prices.add(price_key)
                        
                        hashes = await self.utils.generate_multiple_order_hashes(order_details)
                        
                        if hashes:
                            for hash_key in hashes:
                                self.gate_existing_order_hashes.add(hash_key)
                            
                            order_id = gate_order.get('id', f'existing_{i}')
                            self.gate_existing_orders_detailed[order_id] = {
                                'gate_order': gate_order,
                                'order_details': order_details,
                                'hashes': hashes,
                                'recorded_at': datetime.now().isoformat()
                            }
                            
                            self.logger.info(f"게이트 기존 예약 주문 기록: {order_id} - 트리거가 ${trigger_price:.2f}")
                        
                except Exception as detail_error:
                    self.logger.warning(f"게이트 기존 주문 상세 추출 실패: {detail_error}")
                    continue
            
            self.logger.info(f"게이트 기존 예약 주문 {len(gate_orders)}개 기록 완료")
            
        except Exception as e:
            self.logger.error(f"게이트 기존 예약 주문 기록 실패: {e}")

    async def _record_startup_positions(self):
        """시작 시 비트겟 포지션 기록"""
        try:
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    pos_id = self.utils.generate_position_id(pos)
                    self.startup_positions.add(pos_id)
                    self.logger.info(f"시작 시 비트겟 포지션 기록: {pos_id}")
            
            self.logger.info(f"시작 시 비트겟 포지션 {len(self.startup_positions)}개 기록")
            
        except Exception as e:
            self.logger.error(f"시작 시 포지션 기록 실패: {e}")

    async def _record_startup_plan_orders(self):
        """시작 시 비트겟 예약 주문 기록"""
        try:
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            current_plan_orders = plan_data.get('plan_orders', [])
            current_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_startup_orders = []
            all_startup_orders.extend(current_plan_orders)
            
            # TP/SL 주문 중에서 클로즈 주문만 추가
            for tp_sl_order in current_tp_sl_orders:
                close_details = await self.utils.determine_close_order_details(tp_sl_order)
                if close_details['is_close_order']:
                    all_startup_orders.append(tp_sl_order)
            
            for order in all_startup_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.startup_plan_orders.add(order_id)
                    self.logger.info(f"시작 시 비트겟 예약 주문 기록: {order_id}")
            
            self.last_plan_order_ids = set(self.startup_plan_orders)
            
            self.logger.info(f"시작 시 비트겟 예약 주문 {len(self.startup_plan_orders)}개 기록")
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 기록 실패: {e}")

    async def _record_startup_gate_positions(self):
        """시작 시 게이트 포지션 기록"""
        try:
            gate_positions = await self.gate_mirror.get_positions("BTC_USDT")
            
            for pos in gate_positions:
                if pos.get('size', 0) != 0:
                    gate_pos_id = self._generate_gate_position_id(pos)
                    self.startup_gate_positions.add(gate_pos_id)
                    self.logger.info(f"시작 시 게이트 포지션 기록: {gate_pos_id}")
            
            self.logger.info(f"시작 시 게이트 포지션 {len(self.startup_gate_positions)}개 기록")
            
        except Exception as e:
            self.logger.error(f"시작 시 게이트 포지션 기록 실패: {e}")

    async def _create_initial_plan_order_snapshot(self):
        """초기 예약 주문 스냅샷 생성"""
        try:
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            current_plan_orders = plan_data.get('plan_orders', [])
            current_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_orders = []
            all_orders.extend(current_plan_orders)
            
            for tp_sl_order in current_tp_sl_orders:
                close_details = await self.utils.determine_close_order_details(tp_sl_order)
                if close_details['is_close_order']:
                    all_orders.append(tp_sl_order)
            
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

    async def _mirror_startup_plan_orders(self):
        """시작 시 기존 예약 주문 복제"""
        try:
            if not self.startup_plan_orders:
                self.startup_plan_orders_processed = True
                self.logger.info("시작 시 복제할 예약 주문이 없음")
                return
            
            self.logger.info(f"시작 시 {len(self.startup_plan_orders)}개 예약 주문 복제 시작")
            
            mirrored_count = 0
            skipped_count = 0
            failed_count = 0
            
            for order_id in list(self.startup_plan_orders):
                try:
                    if order_id in self.plan_order_snapshot:
                        order_data = self.plan_order_snapshot[order_id]['order_data']
                        
                        # 중복 체크
                        is_duplicate = await self._is_duplicate_order_enhanced(order_data)
                        if is_duplicate:
                            self.logger.info(f"중복으로 인한 시작 시 주문 스킵: {order_id}")
                            skipped_count += 1
                            continue
                        
                        # 클로즈 주문 여부 확인
                        close_details = await self.utils.determine_close_order_details(order_data)
                        is_close_order = close_details['is_close_order']
                        
                        # 🔥🔥🔥 클로즈 주문과 오픈 주문을 구분하여 처리
                        if is_close_order:
                            result = await self._process_close_order_with_position_matching(order_data, close_details)
                        else:
                            result = await self._process_perfect_mirror_order(order_data)
                        
                        if result in ["perfect_success", "partial_success"]:
                            mirrored_count += 1
                            self.daily_stats['startup_plan_mirrors'] += 1
                            self.logger.info(f"시작 시 예약 주문 복제 성공: {order_id}")
                        else:
                            failed_count += 1
                            self.logger.warning(f"시작 시 예약 주문 복제 실패: {order_id}")
                    
                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"시작 시 예약 주문 복제 오류: {order_id} - {e}")
                    
                # 처리된 주문으로 표시
                self.processed_plan_orders.add(order_id)
            
            # 시작 시 복제 완료 알림
            if mirrored_count > 0:
                await self.telegram.send_message(
                    f"🔄 시작 시 예약 주문 복제 완료\n"
                    f"성공: {mirrored_count}개\n"
                    f"스킵: {skipped_count}개\n"
                    f"실패: {failed_count}개\n"
                    f"총 {len(self.startup_plan_orders)}개 중 {mirrored_count}개 복제\n"
                    f"🔰 포지션 크기 매칭 기능 적용됨\n"
                    f"🔥 시세 차이와 무관하게 즉시 처리됨"
                )
            
            self.startup_plan_orders_processed = True
            self.logger.info(f"시작 시 예약 주문 복제 완료: 성공 {mirrored_count}개, 스킵 {skipped_count}개, 실패 {failed_count}개")
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 복제 실패: {e}")
            self.startup_plan_orders_processed = True

    # === 추가 헬퍼 메서드들 ===

    async def _should_skip_position_due_to_existing(self, bitget_pos: Dict) -> bool:
        """기존 게이트 포지션으로 인한 스킵 여부 판단"""
        try:
            if not self.render_restart_detected:
                return False
            
            holdSide = bitget_pos.get('holdSide', '').lower()
            
            if holdSide == 'long' and self.existing_gate_positions['has_long']:
                self.logger.info("🔄 렌더 재구동: 기존 게이트 롱 포지션 존재로 스킵")
                return True
            elif holdSide == 'short' and self.existing_gate_positions['has_short']:
                self.logger.info("🔄 렌더 재구동: 기존 게이트 숏 포지션 존재로 스킵")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"기존 포지션 스킵 판단 실패: {e}")
            return False

    async def _is_startup_position_match(self, gate_pos: Dict) -> bool:
        """게이트 포지션이 시작 시 존재했던 것인지 확인"""
        try:
            if not self.render_restart_detected:
                return False
            
            size = int(gate_pos.get('size', 0))
            if size == 0:
                return False
            
            current_side = 'long' if size > 0 else 'short'
            
            if current_side == 'long' and self.existing_gate_positions['has_long']:
                return abs(size - self.existing_gate_positions['long_size']) < 10
            elif current_side == 'short' and self.existing_gate_positions['has_short']:
                return abs(abs(size) - self.existing_gate_positions['short_size']) < 10
            
            return False
            
        except Exception as e:
            self.logger.error(f"시작 시 포지션 매칭 확인 실패: {e}")
            return False

    async def _mirror_new_position(self, bitget_pos: Dict) -> MirrorResult:
        """새로운 포지션 미러링"""
        try:
            # 포지션 정보 추출
            side = bitget_pos.get('holdSide', '').lower()
            size = float(bitget_pos.get('total', 0))
            entry_price = float(bitget_pos.get('openPriceAvg', 0))
            leverage = int(float(bitget_pos.get('leverage', 10)))
            
            # 게이트 주문 크기 계산
            gate_size = int(size * 10000)  # BTC를 계약 수로 변환
            
            if side == 'short':
                gate_size = -gate_size
            
            # 레버리지 설정
            await self.gate_mirror.set_leverage("BTC_USDT", leverage)
            
            # 포지션 생성 (시장가 주문)
            result = await self.gate_mirror.place_order(
                contract="BTC_USDT",
                size=gate_size,
                price=None
            )
            
            return MirrorResult(
                success=True,
                action="position_mirror",
                bitget_data=bitget_pos,
                gate_data=result
            )
            
        except Exception as e:
            return MirrorResult(
                success=False,
                action="position_mirror",
                bitget_data=bitget_pos,
                error=str(e)
            )

    async def _handle_partial_close(self, pos_id: str, bitget_pos: Dict, reduction_ratio: float):
        """부분 청산 처리"""
        try:
            gate_positions = await self.gate_mirror.get_positions("BTC_USDT")
            
            if gate_positions:
                gate_pos = gate_positions[0]
                current_gate_size = int(gate_pos.get('size', 0))
                close_size = int(abs(current_gate_size) * reduction_ratio)
                
                if current_gate_size > 0:
                    close_size = -close_size
                else:
                    close_size = abs(close_size)
                
                await self.gate_mirror.place_order(
                    contract="BTC_USDT",
                    size=close_size,
                    reduce_only=True
                )
                
                await self.telegram.send_message(
                    f"📊 부분 청산 완료\n"
                    f"포지션 ID: {pos_id}\n"
                    f"청산 비율: {reduction_ratio*100:.1f}%"
                )
            
        except Exception as e:
            self.logger.error(f"부분 청산 처리 실패: {e}")

    async def stop(self):
        """포지션 매니저 중지"""
        try:
            self.logger.info("포지션 매니저 중지 중...")
            # 필요한 정리 작업 수행
        except Exception as e:
            self.logger.error(f"포지션 매니저 중지 실패: {e}")
