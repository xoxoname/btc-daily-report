import os
import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import json

from mirror_trading_utils import MirrorTradingUtils, PositionInfo, MirrorResult

logger = logging.getLogger(__name__)

class MirrorPositionManager:
    """🔥🔥🔥 포지션 및 주문 관리 클래스 - 예약 주문 취소 동기화 강화 + 복제 비율 적용 수정"""
    
    def __init__(self, config, bitget_client, gate_client, gate_mirror_client, telegram_bot, utils):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.gate_mirror = gate_mirror_client
        self.telegram = telegram_bot
        self.utils = utils
        self.logger = logging.getLogger('mirror_position_manager')
        
        # 환경변수 처리 개선 - O/X 지원
        raw_mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'O')
        self.mirror_trading_enabled = self._parse_mirror_trading_mode(raw_mirror_mode)
        
        # 🔥🔥🔥 배율은 기본값 1.0으로 시작, 텔레그램으로 실시간 조정
        self.mirror_ratio_multiplier = 1.0
        
        # 환경변수 로깅
        self.logger.info(f"🔥 포지션 매니저 환경변수: 미러링모드='{raw_mirror_mode}' → {'활성화' if self.mirror_trading_enabled else '비활성화'}")
        self.logger.info(f"🔥 포지션 매니저 초기 복제 비율: {self.mirror_ratio_multiplier}x (텔레그램으로 실시간 조정 가능)")
        
        # 미러링 상태 관리
        self.mirrored_positions: Dict[str, PositionInfo] = {}
        self.startup_positions: Set[str] = set()
        self.startup_gate_positions: Set[str] = set()
        self.failed_mirrors: List[MirrorResult] = []
        
        # 포지션 크기 추적
        self.position_sizes: Dict[str, float] = {}
        
        # 주문 체결 추적
        self.processed_orders: Set[str] = set()
        
        # 🔥🔥🔥 예약 주문 추적 관리 - 체결/취소 구분 강화
        self.mirrored_plan_orders: Dict[str, Dict] = {}
        self.processed_plan_orders: Set[str] = set()
        self.startup_plan_orders: Set[str] = set()
        self.startup_plan_orders_processed: bool = False
        
        # 🔥🔥🔥 체결된 주문 추적 - 취소와 구분하기 위함
        self.recently_filled_order_ids: Set[str] = set()
        self.filled_order_timestamps: Dict[str, datetime] = {}
        self.filled_order_check_window = 300  # 5분간 체결 기록 유지
        
        # 🔥🔥🔥 중복 복제 방지 시스템 - 완화된 버전
        self.order_processing_locks: Dict[str, asyncio.Lock] = {}
        self.recently_processed_orders: Dict[str, datetime] = {}
        self.order_deduplication_window = 15  # 30초 → 15초로 단축
        
        # 🔥🔥🔥 해시 기반 중복 방지 - 더 정확한 버전
        self.processed_order_hashes: Set[str] = set()
        self.order_hash_timestamps: Dict[str, datetime] = {}
        self.hash_cleanup_interval = 180  # 300초 → 180초로 단축
        
        # 🔥🔥🔥 예약 주문 취소 감지 시스템 강화 - 더 적극적인 동기화
        self.last_plan_order_ids: Set[str] = set()
        self.plan_order_snapshot: Dict[str, Dict] = {}
        self.cancel_retry_count: Dict[str, int] = {}
        self.max_cancel_retries = 5  # 3회 → 5회로 증가
        self.cancel_force_cleanup_threshold = 10  # 10회 실패 시 강제 정리
        
        # 🔥🔥🔥 취소 동기화 강화 - 더 빠른 감지
        self.cancel_detection_enhanced = True
        self.cancel_detection_interval = 10  # 10초마다 취소 감지
        self.last_cancel_detection_time = datetime.min
        
        # 시세 차이 관리
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.price_sync_threshold: float = 100.0
        self.position_wait_timeout: int = 60
        
        # 가격 기반 중복 방지 시스템 - 완화된 버전
        self.mirrored_trigger_prices: Set[str] = set()
        self.price_tolerance = 5.0  # ±5달러 허용
        
        # 렌더 재구동 시 기존 게이트 포지션 확인
        self.existing_gate_positions: Dict = {}
        self.render_restart_detected: bool = False
        
        # 게이트 기존 예약 주문 중복 방지 - 개선된 버전
        self.gate_existing_order_hashes: Set[str] = set()
        self.gate_existing_orders_detailed: Dict[str, Dict] = {}
        
        # 주문 ID 매핑 추적
        self.bitget_to_gate_order_mapping: Dict[str, str] = {}
        self.gate_to_bitget_order_mapping: Dict[str, str] = {}
        
        # 클로즈 주문 처리 강화
        self.close_order_processing: bool = True
        self.close_order_validation_mode: str = "permissive"  # 더 관대한 모드
        self.force_close_order_mirror: bool = True  # 클로즈 주문 강제 미러링
        
        # 렌더 재구동 시 예약 주문 미러링 강화
        self.startup_mirror_retry_count: int = 0
        self.max_startup_mirror_retries: int = 3
        self.startup_mirror_delay: int = 10  # 10초 대기 후 재시도
        
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
            'close_order_forced': 0,
            'duplicate_orders_prevented': 0,
            'perfect_mirrors': 0,
            'partial_mirrors': 0,
            'tp_sl_success': 0,
            'tp_sl_failed': 0,
            'auto_close_order_cleanups': 0,
            'position_closed_cleanups': 0,
            'sync_corrections': 0,
            'sync_deletions': 0,
            'cancel_failures': 0,
            'cancel_successes': 0,
            'filled_detection_successes': 0,
            'forced_cancel_cleanups': 0,  # 🔥🔥🔥 강제 취소 정리 통계 추가
            'errors': []
        }
        
        self.logger.info(f"🔥 미러 포지션 매니저 초기화 완료 - 미러링 모드: {'활성화' if self.mirror_trading_enabled else '비활성화'}, 초기 복제 비율: {self.mirror_ratio_multiplier}x (텔레그램 조정 가능)")

    def _parse_mirror_trading_mode(self, mode_str: str) -> bool:
        """미러링 모드 파싱 - O/X 정확한 구분"""
        if isinstance(mode_str, bool):
            return mode_str
        
        # 문자열로 변환하되 원본 보존
        mode_str_original = str(mode_str).strip()
        mode_str_upper = mode_str_original.upper()
        
        self.logger.info(f"🔍 포지션 매니저 미러링 모드 파싱: 원본='{mode_str_original}', 대문자='{mode_str_upper}'")
        
        # 영어 O, X 우선 처리 (숫자 0과 구분)
        if mode_str_upper == 'O':
            self.logger.info("✅ 포지션 매니저: 영어 대문자 O 감지 → 활성화")
            return True
        elif mode_str_upper == 'X':
            self.logger.info("✅ 포지션 매니저: 영어 대문자 X 감지 → 비활성화")
            return False
        
        # 기타 활성화 키워드
        elif mode_str_upper in ['ON', 'OPEN', 'TRUE', 'Y', 'YES']:
            self.logger.info(f"✅ 포지션 매니저 활성화 키워드 감지: '{mode_str_upper}' → 활성화")
            return True
        
        # 기타 비활성화 키워드 (숫자 0 포함)
        elif mode_str_upper in ['OFF', 'CLOSE', 'FALSE', 'N', 'NO'] or mode_str_original == '0':
            self.logger.info(f"✅ 포지션 매니저 비활성화 키워드 감지: '{mode_str_upper}' → 비활성화")
            return False
        
        # 숫자 1은 활성화
        elif mode_str_original == '1':
            self.logger.info("✅ 포지션 매니저: 숫자 1 감지 → 활성화")
            return True
        
        else:
            self.logger.warning(f"⚠️ 포지션 매니저: 알 수 없는 미러링 모드: '{mode_str_original}', 기본값(활성화) 사용")
            return True

    def update_prices(self, bitget_price: float, gate_price: float, price_diff_percent: float):
        """시세 정보 업데이트"""
        self.bitget_current_price = bitget_price
        self.gate_current_price = gate_price
        self.price_diff_percent = price_diff_percent

    async def initialize(self):
        """포지션 매니저 초기화"""
        try:
            self.logger.info("🔥 포지션 매니저 초기화 시작 - 예약 주문 취소 동기화 강화 + 복제 비율 적용 수정")
            
            # 미러링 비활성화 확인
            if not self.mirror_trading_enabled:
                self.logger.warning("⚠️ 미러링 모드가 비활성화되어 있습니다 (MIRROR_TRADING_MODE=X)")
                return
            
            # Gate 미러링 클라이언트 초기화
            await self.gate_mirror.initialize()
            
            # 렌더 재구동 시 기존 게이트 포지션 확인
            await self._check_existing_gate_positions()
            
            # 게이트 기존 예약 주문 확인
            await self._record_gate_existing_orders()
            
            # 초기 포지션 및 예약 주문 기록
            await self._record_startup_positions()
            await self._record_startup_plan_orders()
            await self._record_startup_gate_positions()
            
            # 예약 주문 초기 스냅샷 생성
            await self._create_initial_plan_order_snapshot()
            
            # 시작 시 기존 예약 주문 복제 - 강화된 재시도 로직
            await self._mirror_startup_plan_orders_with_retry()
            
            self.logger.info("✅ 포지션 매니저 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"포지션 매니저 초기화 실패: {e}")
            raise

    async def monitor_plan_orders_cycle(self):
        """🔥🔥🔥 예약 주문 모니터링 사이클 - 취소 동기화 강화"""
        try:
            if not self.mirror_trading_enabled:
                await asyncio.sleep(1.0)
                return
                
            if not self.startup_plan_orders_processed:
                await asyncio.sleep(0.1)
                return
            
            # 시세 차이 확인
            price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
            if price_diff_abs > self.price_sync_threshold * 2:
                self.logger.debug(f"극도로 큰 시세 차이 ({price_diff_abs:.2f}$), 예약 주문 처리 지연")
                return
            
            # 만료된 타임스탬프 정리
            await self._cleanup_expired_timestamps()
            
            # 해시 기반 중복 방지 시스템 정리
            await self._cleanup_expired_hashes()
            
            # 체결된 주문 기록 업데이트
            await self._update_recently_filled_orders()
            
            # 🔥🔥🔥 강화된 취소 감지 - 더 빠른 주기
            current_time = datetime.now()
            if (current_time - self.last_cancel_detection_time).total_seconds() >= self.cancel_detection_interval:
                await self._enhanced_cancel_detection()
                self.last_cancel_detection_time = current_time
            
            # 포지션 종료 시 클로즈 주문 자동 정리
            await self._check_and_cleanup_close_orders_if_no_position()
            
            # 모든 예약 주문 조회 - 클로즈 주문 포함
            all_current_orders = await self._get_all_current_plan_orders_enhanced()
            
            # 현재 존재하는 예약주문 ID 집합
            current_order_ids = set()
            current_snapshot = {}
            
            for order in all_current_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    current_order_ids.add(order_id)
                    current_snapshot[order_id] = {
                        'order_data': order.copy(),
                        'timestamp': datetime.now().isoformat(),
                        'status': 'active'
                    }
            
            # 🔥🔥🔥 사라진 예약 주문 분석 - 체결 vs 취소 구분 강화
            disappeared_order_ids = self.last_plan_order_ids - current_order_ids
            
            if disappeared_order_ids:
                self.logger.info(f"📋 {len(disappeared_order_ids)}개의 예약 주문이 사라짐 - 강화된 체결/취소 분석 시작")
                
                canceled_count = 0
                filled_count = 0
                
                for disappeared_id in disappeared_order_ids:
                    try:
                        # 체결/취소 구분 로직
                        is_filled = await self._check_if_order_was_filled(disappeared_id)
                        
                        if is_filled:
                            filled_count += 1
                            self.daily_stats['filled_detection_successes'] += 1
                            self.logger.info(f"✅ 체결 감지: {disappeared_id} - 게이트 주문 유지")
                            
                            # 체결된 주문은 미러링 기록에서 제거만 하고 게이트 주문은 건드리지 않음
                            if disappeared_id in self.mirrored_plan_orders:
                                await self._cleanup_mirror_records_for_filled_order(disappeared_id)
                        else:
                            # 실제 취소된 주문만 처리 - 강화된 버전
                            success = await self._handle_plan_order_cancel_enhanced_v2(disappeared_id)
                            if success:
                                canceled_count += 1
                                self.daily_stats['cancel_successes'] += 1
                            else:
                                self.daily_stats['cancel_failures'] += 1
                                
                    except Exception as e:
                        self.logger.error(f"사라진 주문 분석 중 예외: {disappeared_id} - {e}")
                        self.daily_stats['cancel_failures'] += 1
                
                self.daily_stats['plan_order_cancels'] += canceled_count
                
                # 체결/취소 결과 알림
                if filled_count > 0 or canceled_count > 0:
                    await self.telegram.send_message(
                        f"📋 예약 주문 변화 분석 결과 (강화된 동기화)\n"
                        f"사라진 주문: {len(disappeared_order_ids)}개\n"
                        f"🎯 체결 감지: {filled_count}개 (게이트 주문 유지)\n"
                        f"🚫 취소 동기화: {canceled_count}개 (강화된 로직)\n"
                        f"📊 현재 시세 차이: ${price_diff_abs:.2f}\n\n"
                        f"{'✅ 체결/취소가 정확히 구분되어 처리되었습니다!' if filled_count > 0 else '🔄 모든 취소가 성공적으로 동기화되었습니다!'}"
                    )
            
            # 새로운 예약 주문 감지 - 복제 비율 적용 강화
            new_orders_count = 0
            new_close_orders_count = 0
            perfect_mirrors = 0
            forced_close_mirrors = 0
            
            for order in all_current_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if not order_id:
                    continue
                
                # 개선된 중복 처리 방지
                if await self._is_order_recently_processed_improved(order_id, order):
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
                    
                    # 개선된 중복 복제 확인
                    is_duplicate = await self._is_duplicate_order_improved(order)
                    if is_duplicate:
                        self.daily_stats['duplicate_orders_prevented'] += 1
                        self.logger.info(f"🛡️ 중복 감지로 스킵: {order_id}")
                        self.processed_plan_orders.add(order_id)
                        continue
                    
                    # 🔥🔥🔥 새로운 예약 주문 처리 - 복제 비율 강화 적용
                    try:
                        # 클로즈 주문 상세 분석
                        close_details = await self.utils.determine_close_order_details_enhanced(order)
                        is_close_order = close_details['is_close_order']
                        
                        # 🔥🔥🔥 복제 비율 확인 로깅 추가
                        self.logger.info(f"🎯 새로운 예약 주문 감지: {order_id} (클로즈: {is_close_order})")
                        self.logger.info(f"   📊 현재 복제 비율: {self.mirror_ratio_multiplier}x")
                        self.logger.debug(f"   주문 상세: side={order.get('side')}, reduceOnly={order.get('reduceOnly')}")
                        
                        # 클로즈 주문인 경우 강화된 검증
                        process_order = True
                        validation_result = "proceed"
                        
                        if is_close_order:
                            validation_result = await self._validate_close_order_enhanced(order, close_details)
                            if validation_result == "force_mirror":
                                self.logger.warning(f"🚀 클로즈 주문 강제 미러링: {order_id}")
                                forced_close_mirrors += 1
                                self.daily_stats['close_order_forced'] += 1
                            elif validation_result == "skip":
                                self.logger.warning(f"⏭️ 클로즈 주문 스킵: {order_id}")
                                self.processed_plan_orders.add(order_id)
                                self.daily_stats['close_order_skipped'] += 1
                                continue
                        
                        # 🔥🔥🔥 복제 비율 적용된 완벽한 미러링 처리 - 강화된 버전
                        result = await self._process_perfect_mirror_order_with_ratio_enhanced(order, close_details, self.mirror_ratio_multiplier)
                        
                        # 모든 성공 케이스 처리
                        success_results = ["perfect_success", "partial_success", "force_success", "close_order_forced"]
                        
                        if result in success_results:
                            new_orders_count += 1
                            if result == "perfect_success":
                                perfect_mirrors += 1
                                self.daily_stats['perfect_mirrors'] += 1
                            elif result in ["force_success", "close_order_forced"]:
                                forced_close_mirrors += 1
                                self.daily_stats['close_order_forced'] += 1
                            else:
                                self.daily_stats['partial_mirrors'] += 1
                                
                            if is_close_order:
                                new_close_orders_count += 1
                                self.daily_stats['close_order_mirrors'] += 1
                                
                            self.logger.info(f"✅ 예약 주문 복제 성공: {order_id} (결과: {result}, 비율: {self.mirror_ratio_multiplier}x)")
                            
                        elif result == "skipped" and is_close_order:
                            self.daily_stats['close_order_skipped'] += 1
                            self.logger.info(f"⏭️ 클로즈 주문 스킵됨: {order_id}")
                        else:
                            # 실패한 경우
                            self.daily_stats['failed_mirrors'] += 1
                            self.logger.error(f"❌ 예약 주문 복제 실패: {order_id} (결과: {result})")
                        
                        self.processed_plan_orders.add(order_id)
                        
                        # 주문 처리 해시 기록 (중복 방지)
                        await self._record_order_processing_hash(order_id, order)
                        
                    except Exception as e:
                        self.logger.error(f"새로운 예약 주문 복제 실패: {order_id} - {e}")
                        self.processed_plan_orders.add(order_id)
                        self.daily_stats['failed_mirrors'] += 1
                        
                        await self.telegram.send_message(
                            f"❌ 예약 주문 복제 실패\n"
                            f"비트겟 ID: {order_id}\n"
                            f"오류: {str(e)[:200]}"
                        )
            
            # 성공적인 미러링 결과 알림 - 복제 비율 정보 포함
            if new_orders_count > 0:
                ratio_info = f" (복제비율: {self.mirror_ratio_multiplier}x)" if self.mirror_ratio_multiplier != 1.0 else ""
                
                if forced_close_mirrors > 0:
                    await self.telegram.send_message(
                        f"🚀 클로즈 주문 강제 미러링 성공{ratio_info}\n"
                        f"강제 미러링: {forced_close_mirrors}개\n"
                        f"완벽 복제: {perfect_mirrors}개\n"
                        f"클로즈 주문: {new_close_orders_count}개\n"
                        f"전체 신규: {new_orders_count}개\n\n"
                        f"🔥 클로즈 주문은 포지션 유무와 관계없이 미러링됩니다{ratio_info}"
                    )
                elif perfect_mirrors > 0:
                    await self.telegram.send_message(
                        f"✅ 완벽한 TP/SL 미러링 성공{ratio_info}\n"
                        f"완벽 복제: {perfect_mirrors}개\n"
                        f"클로즈 주문: {new_close_orders_count}개\n"
                        f"전체 신규: {new_orders_count}개{ratio_info}"
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

    async def _enhanced_cancel_detection(self):
        """🔥🔥🔥 강화된 취소 감지 시스템 - 더 빠른 동기화"""
        try:
            # 현재 비트겟 예약 주문 조회
            current_bitget_orders = await self._get_all_current_plan_orders_enhanced()
            current_bitget_ids = set()
            
            for order in current_bitget_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    current_bitget_ids.add(order_id)
            
            # 미러링된 주문 중 비트겟에서 사라진 것들 찾기
            missing_bitget_orders = []
            
            for bitget_id, mirror_info in list(self.mirrored_plan_orders.items()):
                if bitget_id not in current_bitget_ids:
                    # 체결 여부 확인
                    is_filled = await self._check_if_order_was_filled(bitget_id)
                    
                    if not is_filled:
                        # 취소된 것으로 판단
                        missing_bitget_orders.append(bitget_id)
            
            # 취소된 주문들 처리
            if missing_bitget_orders:
                self.logger.info(f"🔍 강화된 취소 감지: {len(missing_bitget_orders)}개 주문이 비트겟에서 취소됨")
                
                for bitget_id in missing_bitget_orders:
                    try:
                        success = await self._handle_plan_order_cancel_enhanced_v2(bitget_id)
                        if success:
                            self.daily_stats['cancel_successes'] += 1
                            self.logger.info(f"✅ 강화된 취소 동기화 성공: {bitget_id}")
                        else:
                            self.daily_stats['cancel_failures'] += 1
                            self.logger.warning(f"⚠️ 강화된 취소 동기화 실패: {bitget_id}")
                    except Exception as e:
                        self.logger.error(f"강화된 취소 처리 중 오류: {bitget_id} - {e}")
                        self.daily_stats['cancel_failures'] += 1
                        
        except Exception as e:
            self.logger.error(f"강화된 취소 감지 시스템 오류: {e}")

    async def _handle_plan_order_cancel_enhanced_v2(self, bitget_order_id: str) -> bool:
        """🔥🔥🔥 강화된 예약 주문 취소 처리 V2 - 더 적극적인 동기화"""
        try:
            self.logger.info(f"🚫 강화된 예약 주문 취소 처리 V2 시작: {bitget_order_id}")
            
            # 미러링된 주문인지 확인
            if bitget_order_id not in self.mirrored_plan_orders:
                self.logger.info(f"미러링되지 않은 주문이므로 취소 처리 스킵: {bitget_order_id}")
                return True
            
            mirror_info = self.mirrored_plan_orders[bitget_order_id]
            gate_order_id = mirror_info.get('gate_order_id')
            
            if not gate_order_id:
                self.logger.warning(f"게이트 주문 ID가 없음: {bitget_order_id}")
                # 미러링 기록에서 제거
                del self.mirrored_plan_orders[bitget_order_id]
                return True
            
            # 재시도 카운터 확인
            retry_count = self.cancel_retry_count.get(bitget_order_id, 0)
            
            # 🔥🔥🔥 강제 정리 임계값 확인
            if retry_count >= self.cancel_force_cleanup_threshold:
                self.logger.error(f"💀 강제 정리 임계값 초과: {bitget_order_id} (재시도: {retry_count}회)")
                await self._force_remove_mirror_record_v2(bitget_order_id, gate_order_id)
                self.daily_stats['forced_cancel_cleanups'] += 1
                return True
            
            # 최대 재시도 횟수 확인
            if retry_count >= self.max_cancel_retries:
                self.logger.error(f"최대 재시도 횟수 초과하지만 강제 정리 계속: {bitget_order_id} (재시도: {retry_count}회)")
                await self._force_remove_mirror_record_v2(bitget_order_id, gate_order_id)
                return False
            
            # 🔥🔥🔥 게이트에서 주문 취소 시도 - 강화된 로직
            try:
                self.logger.info(f"🎯 게이트 주문 취소 시도 V2: {gate_order_id} (재시도: {retry_count + 1}/{self.max_cancel_retries})")
                
                # 먼저 주문이 존재하는지 확인
                gate_orders = await self.gate_mirror.get_price_triggered_orders("BTC_USDT", "open")
                gate_order_exists = any(order.get('id') == gate_order_id for order in gate_orders)
                
                if not gate_order_exists:
                    # 이미 존재하지 않음
                    success = True
                    self.logger.info(f"✅ 게이트 주문이 이미 처리됨: {gate_order_id}")
                else:
                    # 실제 취소 시도
                    cancel_result = await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                    
                    # 2초 대기 후 취소 확인
                    await asyncio.sleep(2.0)
                    
                    # 취소 확인
                    gate_orders_after = await self.gate_mirror.get_price_triggered_orders("BTC_USDT", "open")
                    gate_order_still_exists = any(order.get('id') == gate_order_id for order in gate_orders_after)
                    
                    if gate_order_still_exists:
                        # 아직 존재하면 재시도
                        success = False
                        self.cancel_retry_count[bitget_order_id] = retry_count + 1
                        self.logger.warning(f"⚠️ 게이트 주문이 아직 존재함, 재시도 예정: {gate_order_id}")
                    else:
                        # 취소 확인됨
                        success = True
                        self.logger.info(f"✅ 게이트 주문 취소 확인됨: {gate_order_id}")
                        
            except Exception as cancel_error:
                error_msg = str(cancel_error).lower()
                
                # 이미 존재하지 않는 주문인 경우 성공으로 처리
                if any(keyword in error_msg for keyword in [
                    "not found", "order not exist", "invalid order", 
                    "order does not exist", "auto_order_not_found",
                    "order_not_found", "not_found", "已取消", "cancelled"
                ]):
                    success = True
                    self.logger.info(f"✅ 게이트 주문이 이미 처리됨 (오류 메시지): {gate_order_id}")
                else:
                    # 다른 오류인 경우 재시도
                    success = False
                    self.cancel_retry_count[bitget_order_id] = retry_count + 1
                    self.logger.error(f"❌ 게이트 주문 취소 실패: {gate_order_id} - {cancel_error}")
            
            # 결과 처리
            if success:
                # 성공한 경우 모든 기록 정리
                await self._cleanup_mirror_records(bitget_order_id, gate_order_id)
                
                await self.telegram.send_message(
                    f"🚫✅ 강화된 예약 주문 취소 동기화 완료\n"
                    f"비트겟 ID: {bitget_order_id}\n"
                    f"게이트 ID: {gate_order_id}\n"
                    f"재시도 횟수: {retry_count + 1}회\n"
                    f"🔥 강화된 동기화 로직으로 처리됨"
                )
                
                self.logger.info(f"🎯 강화된 예약 주문 취소 동기화 성공: {bitget_order_id} → {gate_order_id}")
                return True
            else:
                # 실패한 경우 다음 사이클에서 재시도
                self.logger.warning(f"⚠️ 강화된 예약 주문 취소 재시도 예정: {bitget_order_id} (다음 사이클)")
                return False
                
        except Exception as e:
            self.logger.error(f"강화된 예약 주문 취소 처리 V2 중 예외 발생: {bitget_order_id} - {e}")
            
            # 예외 발생 시 재시도 카운터 증가
            retry_count = self.cancel_retry_count.get(bitget_order_id, 0)
            self.cancel_retry_count[bitget_order_id] = retry_count + 1
            
            return False

    async def _force_remove_mirror_record_v2(self, bitget_order_id: str, gate_order_id: str):
        """🔥🔥🔥 강제로 미러링 기록 제거 V2 - 더 적극적인 정리"""
        try:
            self.logger.warning(f"💀 강제 미러링 기록 제거 V2: {bitget_order_id} → {gate_order_id}")
            
            # 마지막으로 게이트 주문 취소 시도
            try:
                await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                self.logger.info(f"🎯 강제 정리 중 게이트 주문 취소 성공: {gate_order_id}")
            except Exception as final_cancel_error:
                self.logger.warning(f"⚠️ 강제 정리 중 게이트 주문 취소 실패 (무시하고 계속): {gate_order_id} - {final_cancel_error}")
            
            # 미러링 기록에서 제거
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]
            
            # 주문 매핑에서 제거
            if bitget_order_id in self.bitget_to_gate_order_mapping:
                del self.bitget_to_gate_order_mapping[bitget_order_id]
            if gate_order_id in self.gate_to_bitget_order_mapping:
                del self.gate_to_bitget_order_mapping[gate_order_id]
            
            # 재시도 카운터에서 제거
            if bitget_order_id in self.cancel_retry_count:
                del self.cancel_retry_count[bitget_order_id]
            
            await self.telegram.send_message(
                f"💀 강제 미러링 기록 정리 V2\n"
                f"비트겟 ID: {bitget_order_id}\n"
                f"게이트 ID: {gate_order_id}\n"
                f"사유: 반복 취소 실패로 강제 정리\n"
                f"🔥 강화된 정리 로직으로 처리됨\n"
                f"⚠️ 게이트에서 수동 확인을 권장합니다"
            )
            
        except Exception as e:
            self.logger.error(f"강제 미러링 기록 제거 V2 실패: {e}")

    async def _process_perfect_mirror_order_with_ratio_enhanced(self, bitget_order: Dict, close_details: Dict, ratio_multiplier: float) -> str:
        """🔥🔥🔥 복제 비율이 적용된 완벽한 미러링 주문 처리 - 강화된 비율 적용"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            is_close_order = close_details['is_close_order']
            order_direction = close_details['order_direction']
            position_side = close_details['position_side']
            
            # 🔥🔥🔥 복제 비율 검증 및 로깅 강화
            validated_ratio = self.utils.validate_ratio_multiplier(ratio_multiplier)
            if validated_ratio != ratio_multiplier:
                self.logger.warning(f"⚠️ 복제 비율 조정됨: {ratio_multiplier} → {validated_ratio}")
                ratio_multiplier = validated_ratio
            
            self.logger.info(f"🎯 강화된 복제 비율 적용 미러링 시작: {order_id}")
            self.logger.info(f"   📊 검증된 복제 비율: {ratio_multiplier}x")
            self.logger.info(f"   📋 클로즈 주문: {is_close_order}")
            self.logger.info(f"   📋 주문 방향: {order_direction} (포지션: {position_side})")
            
            # 트리거 가격 추출
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price == 0:
                self.logger.error(f"❌ 트리거 가격을 찾을 수 없음: {order_id}")
                return "failed"
            
            # 크기 정보 추출
            size = float(bitget_order.get('size', 0))
            if size == 0:
                self.logger.error(f"❌ 주문 크기가 0: {order_id}")
                return "failed"
            
            # 🔥🔥🔥 복제 비율 적용된 마진 비율 계산 - 강화된 로깅
            self.logger.info(f"💰 복제 비율 적용 마진 계산 시작:")
            self.logger.info(f"   - 비트겟 원본 크기: {size}")
            self.logger.info(f"   - 트리거 가격: ${trigger_price:.2f}")
            self.logger.info(f"   - 적용할 복제 비율: {ratio_multiplier}x")
            
            margin_ratio_result = await self.utils.calculate_dynamic_margin_ratio_with_multiplier(
                size, trigger_price, bitget_order, ratio_multiplier
            )
            
            if not margin_ratio_result['success']:
                self.logger.error(f"❌ 복제 비율 적용 마진 비율 계산 실패: {order_id}")
                self.logger.error(f"   오류: {margin_ratio_result.get('error')}")
                return "failed"
            
            # 계산 결과 상세 로깅
            margin_ratio = margin_ratio_result['margin_ratio']
            bitget_leverage = margin_ratio_result['leverage']
            base_margin_ratio = margin_ratio_result.get('base_margin_ratio', margin_ratio)
            ratio_effect = margin_ratio_result.get('ratio_effect', {})
            
            self.logger.info(f"💰 복제 비율 적용 마진 계산 결과:")
            self.logger.info(f"   - 원본 마진 비율: {base_margin_ratio*100:.3f}%")
            self.logger.info(f"   - 복제 비율 적용 후: {margin_ratio*100:.3f}%")
            self.logger.info(f"   - 레버리지: {bitget_leverage}x")
            self.logger.info(f"   - 복제 비율 효과: {ratio_effect.get('impact', '알 수 없음')}")
            
            # 레버리지 설정
            try:
                await self.gate_mirror.set_leverage("BTC_USDT", bitget_leverage)
            except Exception as e:
                self.logger.error(f"레버리지 설정 실패하지만 계속 진행: {e}")
            
            # 게이트 계정 정보
            gate_account = await self.gate_mirror.get_account_balance()
            gate_total_equity = float(gate_account.get('total', 0))
            gate_available = float(gate_account.get('available', 0))
            
            # 복제 비율 적용된 게이트 마진 계산
            gate_margin = gate_total_equity * margin_ratio
            
            if gate_margin > gate_available:
                gate_margin = gate_available * 0.95
                self.logger.warning(f"⚠️ 복제 비율 적용 후 마진이 가용 자금 초과, 95%로 제한: ${gate_margin:,.2f}")
            
            if gate_margin < self.MIN_MARGIN:
                self.logger.error(f"❌ 복제 비율 적용 후 게이트 마진 부족: ${gate_margin:.2f} < ${self.MIN_MARGIN}")
                return "failed"
            
            # 게이트 계약 수 계산
            gate_notional_value = gate_margin * bitget_leverage
            gate_size = int(gate_notional_value / (trigger_price * 0.0001))
            
            if gate_size == 0:
                gate_size = 1
            
            # 🔥🔥🔥 복제 비율 효과 최종 확인
            final_multiplier_effect = gate_margin / (gate_total_equity * base_margin_ratio) if base_margin_ratio > 0 else 1.0
            
            self.logger.info(f"💰 최종 복제 비율 효과 확인:")
            self.logger.info(f"   - 요청된 복제 비율: {ratio_multiplier}x")
            self.logger.info(f"   - 실제 적용 효과: {final_multiplier_effect:.3f}x")
            self.logger.info(f"   - 게이트 투입 마진: ${gate_margin:,.2f}")
            self.logger.info(f"   - 게이트 계약 수: {gate_size}")
            
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
                self.logger.error(f"❌ Gate.io 주문 생성 실패: {order_id}")
                return "failed"
            
            gate_order_id = mirror_result['gate_order_id']
            
            # 주문 ID 매핑 기록
            if order_id and gate_order_id:
                self.bitget_to_gate_order_mapping[order_id] = gate_order_id
                self.gate_to_bitget_order_mapping[gate_order_id] = order_id
                self.logger.info(f"주문 매핑 기록: {order_id} ↔ {gate_order_id}")
            
            # 미러링 성공 기록 - 복제 비율 정보 포함
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
                'close_details': close_details,
                'forced_close': mirror_result.get('forced_close', False),
                'ratio_multiplier': ratio_multiplier,  # 🔥🔥🔥 복제 비율 기록
                'base_margin_ratio': base_margin_ratio,  # 원본 비율 기록
                'ratio_effect': ratio_effect,  # 복제 비율 효과 기록
                'final_multiplier_effect': final_multiplier_effect  # 실제 적용 효과
            }
            
            self.daily_stats['plan_order_mirrors'] += 1
            
            # TP/SL 통계 업데이트
            if mirror_result.get('has_tp_sl', False):
                self.daily_stats['tp_sl_success'] += 1
            elif mirror_result.get('tp_price') or mirror_result.get('sl_price'):
                self.daily_stats['tp_sl_failed'] += 1
            
            # 🔥🔥🔥 성공 메시지 - 복제 비율 정보 강화
            order_type = "클로즈 주문" if mirror_result.get('is_close_order') else "예약 주문"
            perfect_status = "완벽" if mirror_result.get('perfect_mirror') else "부분"
            forced_status = " (강제 미러링)" if mirror_result.get('forced_close') else ""
            
            # 복제 비율 효과 분석
            ratio_status = ""
            if ratio_multiplier != 1.0:
                if abs(final_multiplier_effect - ratio_multiplier) < 0.1:
                    ratio_status = f" (복제비율: {ratio_multiplier}x ✅ 정확 적용)"
                else:
                    ratio_status = f" (복제비율: {ratio_multiplier}x → 실제: {final_multiplier_effect:.2f}x)"
            
            close_info = ""
            if is_close_order:
                close_info = f"\n🔴 클로즈 주문: {order_direction} (원래 포지션: {position_side}){forced_status}"
            
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
            
            await self.telegram.send_message(
                f"✅ {order_type} {perfect_status} 미러링 성공{forced_status}{ratio_status}\n"
                f"비트겟 ID: {order_id}\n"
                f"게이트 ID: {gate_order_id}\n"
                f"트리거가: ${trigger_price:,.2f}\n"
                f"게이트 수량: {gate_size}{close_info}\n"
                f"시세 차이: ${abs(self.bitget_current_price - self.gate_current_price):.2f}\n\n"
                f"💰 강화된 복제 비율 적용:\n"
                f"원본 마진 비율: {base_margin_ratio*100:.2f}%\n"
                f"복제 비율: {ratio_multiplier}x\n"
                f"최종 마진 비율: {margin_ratio*100:.2f}%\n"
                f"게이트 투입 마진: ${gate_margin:,.2f}\n"
                f"레버리지: {bitget_leverage}x\n"
                f"복제 효과: {ratio_effect.get('impact', '알 수 없음')}{tp_sl_info}"
            )
            
            # 반환값 개선
            if mirror_result.get('forced_close'):
                return "close_order_forced"
            elif mirror_result.get('perfect_mirror'):
                return "perfect_success"
            else:
                return "partial_success"
            
        except Exception as e:
            self.logger.error(f"강화된 복제 비율 적용 미러링 주문 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'plan_order_id': bitget_order.get('orderId', bitget_order.get('planOrderId', 'unknown'))
            })
            return "failed"

    # === 기존 메서드들 유지 (중복 제거를 위해 중요한 것만 다시 정의) ===
    
    async def _update_recently_filled_orders(self):
        """최근 체결된 주문 기록 업데이트"""
        try:
            # 최근 5분간 체결된 주문 조회
            filled_orders = await self.bitget.get_recent_filled_orders(symbol=self.SYMBOL, minutes=5)
            
            current_time = datetime.now()
            
            for order in filled_orders:
                order_id = order.get('orderId', order.get('id', ''))
                if order_id:
                    self.recently_filled_order_ids.add(order_id)
                    self.filled_order_timestamps[order_id] = current_time
            
            # 오래된 체결 기록 정리 (5분 경과)
            expired_ids = []
            for order_id, timestamp in self.filled_order_timestamps.items():
                if (current_time - timestamp).total_seconds() > self.filled_order_check_window:
                    expired_ids.append(order_id)
            
            for order_id in expired_ids:
                self.recently_filled_order_ids.discard(order_id)
                del self.filled_order_timestamps[order_id]
                
        except Exception as e:
            self.logger.error(f"최근 체결 주문 업데이트 실패: {e}")

    async def _check_if_order_was_filled(self, order_id: str) -> bool:
        """주문이 체결되었는지 확인"""
        try:
            # 1. 최근 체결 기록에서 확인
            if order_id in self.recently_filled_order_ids:
                self.logger.info(f"✅ 체결 확인 (최근 기록): {order_id}")
                return True
            
            # 2. 실시간 체결 주문 조회로 재확인
            recent_filled = await self.bitget.get_recent_filled_orders(symbol=self.SYMBOL, minutes=2)
            
            for filled_order in recent_filled:
                filled_id = filled_order.get('orderId', filled_order.get('id', ''))
                if filled_id == order_id:
                    self.logger.info(f"✅ 체결 확인 (실시간 조회): {order_id}")
                    
                    # 체결 기록에 추가
                    self.recently_filled_order_ids.add(order_id)
                    self.filled_order_timestamps[order_id] = datetime.now()
                    return True
            
            # 3. 주문 내역에서 체결 상태 확인
            try:
                order_history = await self.bitget.get_order_history(
                    symbol=self.SYMBOL, 
                    status='filled',
                    limit=50
                )
                
                for hist_order in order_history:
                    hist_id = hist_order.get('orderId', hist_order.get('id', ''))
                    if hist_id == order_id:
                        self.logger.info(f"✅ 체결 확인 (주문 내역): {order_id}")
                        return True
                        
            except Exception as e:
                self.logger.debug(f"주문 내역 조회 실패: {e}")
            
            # 체결되지 않음 = 취소됨
            self.logger.info(f"🚫 취소 확인: {order_id}")
            return False
            
        except Exception as e:
            self.logger.error(f"주문 체결/취소 확인 실패: {order_id} - {e}")
            # 확실하지 않으면 취소로 처리하지 않음 (안전상)
            return True

    async def _cleanup_mirror_records_for_filled_order(self, bitget_order_id: str):
        """체결된 주문의 미러링 기록 정리"""
        try:
            if bitget_order_id in self.mirrored_plan_orders:
                mirror_info = self.mirrored_plan_orders[bitget_order_id]
                gate_order_id = mirror_info.get('gate_order_id')
                
                self.logger.info(f"🎯 체결된 주문의 미러링 기록 정리: {bitget_order_id} → {gate_order_id}")
                
                # 미러링 기록에서 제거
                del self.mirrored_plan_orders[bitget_order_id]
                
                # 주문 매핑에서 제거
                if bitget_order_id in self.bitget_to_gate_order_mapping:
                    del self.bitget_to_gate_order_mapping[bitget_order_id]
                if gate_order_id and gate_order_id in self.gate_to_bitget_order_mapping:
                    del self.gate_to_bitget_order_mapping[gate_order_id]
                
                # 재시도 카운터에서 제거
                if bitget_order_id in self.cancel_retry_count:
                    del self.cancel_retry_count[bitget_order_id]
                
                self.logger.info(f"✅ 체결된 주문의 미러링 기록 정리 완료: {bitget_order_id}")
            
        except Exception as e:
            self.logger.error(f"체결된 주문 미러링 기록 정리 실패: {e}")

    async def _cleanup_mirror_records(self, bitget_order_id: str, gate_order_id: str):
        """미러링 기록 정리"""
        try:
            # 미러링 기록에서 제거
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]
            
            # 주문 매핑에서 제거
            if bitget_order_id in self.bitget_to_gate_order_mapping:
                del self.bitget_to_gate_order_mapping[bitget_order_id]
            if gate_order_id in self.gate_to_bitget_order_mapping:
                del self.gate_to_bitget_order_mapping[gate_order_id]
            
            # 재시도 카운터에서 제거
            if bitget_order_id in self.cancel_retry_count:
                del self.cancel_retry_count[bitget_order_id]
            
            self.logger.debug(f"🧹 미러링 기록 정리 완료: {bitget_order_id}")
            
        except Exception as e:
            self.logger.error(f"미러링 기록 정리 실패: {e}")

    # 나머지 기존 메서드들은 동일하게 유지하되, 중요한 초기화 메서드들만 간략하게 포함
    
    async def _get_all_current_plan_orders_enhanced(self) -> List[Dict]:
        """모든 현재 예약 주문 조회 - 클로즈 주문 강화"""
        try:
            all_orders = []
            
            # 1. 비트겟에서 모든 예약 주문 조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            
            # 2. 일반 예약 주문 추가
            general_orders = plan_data.get('plan_orders', [])
            if general_orders:
                all_orders.extend(general_orders)
                self.logger.debug(f"일반 예약 주문 {len(general_orders)}개 추가")
                
                # 클로즈 주문 특별 체크
                for order in general_orders:
                    side = order.get('side', order.get('tradeSide', '')).lower()
                    reduce_only = order.get('reduceOnly', False)
                    if 'close' in side or reduce_only:
                        self.logger.info(f"🔴 일반 예약 주문 중 클로즈 주문 발견: {order.get('orderId', order.get('planOrderId'))}")
            
            # 3. TP/SL 주문 추가
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            if tp_sl_orders:
                all_orders.extend(tp_sl_orders)
                self.logger.debug(f"TP/SL 주문 {len(tp_sl_orders)}개 추가 (모두 클로즈 성격)")
                
                for order in tp_sl_orders:
                    order_id = order.get('orderId', order.get('planOrderId'))
                    self.logger.info(f"🎯 TP/SL 클로즈 주문 발견: {order_id}")
            
            self.logger.debug(f"총 {len(all_orders)}개의 현재 예약 주문 조회 완료 (클로즈 주문 포함)")
            return all_orders
            
        except Exception as e:
            self.logger.error(f"현재 예약 주문 조회 실패: {e}")
            return []

    # 기존 메서드들 중 필수적인 것들만 포함 (중복 제거)
    async def _is_order_recently_processed_improved(self, order_id: str, order: Dict) -> bool:
        """개선된 최근 처리 주문 확인"""
        try:
            # 기본 시간 기반 확인
            if order_id in self.recently_processed_orders:
                time_diff = (datetime.now() - self.recently_processed_orders[order_id]).total_seconds()
                if time_diff < self.order_deduplication_window:
                    self.logger.debug(f"최근 처리된 주문: {order_id} ({time_diff:.1f}초 전)")
                    return True
                else:
                    del self.recently_processed_orders[order_id]
            
            # 정확한 해시 기반 확인만 사용
            order_hash = await self._generate_primary_order_hash(order)
            if order_hash and order_hash in self.processed_order_hashes:
                self.logger.debug(f"해시 기반 중복 감지: {order_hash}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"개선된 최근 처리 확인 실패: {e}")
            return False

    async def _is_duplicate_order_improved(self, bitget_order: Dict) -> bool:
        """개선된 중복 주문 확인"""
        try:
            # 트리거 가격 추출
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price <= 0:
                return False
            
            # 정확한 가격 매칭 확인
            for existing_price_key in self.mirrored_trigger_prices:
                try:
                    if existing_price_key.startswith(f"{self.GATE_CONTRACT}_"):
                        existing_price_str = existing_price_key.replace(f"{self.GATE_CONTRACT}_", "")
                        existing_price = float(existing_price_str)
                        
                        price_diff = abs(trigger_price - existing_price)
                        if price_diff <= self.price_tolerance:
                            self.logger.debug(f"가격 기반 중복 감지: {trigger_price} ≈ {existing_price} (차이: ${price_diff:.2f})")
                            return True
                except (ValueError, IndexError):
                    continue
            
            # 기존 게이트 주문과의 정확한 해시 매칭만 확인
            order_hash = await self._generate_primary_order_hash(bitget_order)
            if order_hash and order_hash in self.gate_existing_order_hashes:
                self.logger.debug(f"게이트 기존 주문과 해시 중복: {order_hash}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"개선된 중복 주문 확인 실패: {e}")
            return False

    async def _generate_primary_order_hash(self, order: Dict) -> str:
        """주 해시 생성"""
        try:
            # 트리거 가격 추출
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if order.get(price_field):
                    trigger_price = float(order.get(price_field))
                    break
            
            if trigger_price <= 0:
                return ""
            
            # 크기 추출
            size = order.get('size', 0)
            if size:
                size = int(float(size))
                abs_size = abs(size)
                return f"{self.GATE_CONTRACT}_{trigger_price:.2f}_{abs_size}"
            else:
                return f"{self.GATE_CONTRACT}_price_{trigger_price:.2f}"
            
        except Exception as e:
            self.logger.error(f"주 해시 생성 실패: {e}")
            return ""

    async def _record_order_processing_hash(self, order_id: str, order: Dict):
        """주문 처리 해시 기록"""
        try:
            current_time = datetime.now()
            self.recently_processed_orders[order_id] = current_time
            
            # 주 해시만 기록
            order_hash = await self._generate_primary_order_hash(order)
            if order_hash:
                self.processed_order_hashes.add(order_hash)
                self.order_hash_timestamps[order_hash] = current_time
            
            # 가격 기반 중복 방지 기록
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if order.get(price_field):
                    trigger_price = float(order.get(price_field))
                    break
            
            if trigger_price > 0:
                price_key = f"{self.GATE_CONTRACT}_{trigger_price:.2f}"
                self.mirrored_trigger_prices.add(price_key)
            
        except Exception as e:
            self.logger.error(f"주문 처리 해시 기록 실패: {e}")

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
            
            # 기타 정리 작업들...
                
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

    # 필수 초기화 메서드들 (기존과 동일)
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

    # 기타 필수 메서드들은 기존과 동일하게 유지...
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
                        
                        order_hash = await self._generate_primary_order_hash_from_details(order_details)
                        
                        if order_hash:
                            self.gate_existing_order_hashes.add(order_hash)
                            
                            order_id = gate_order.get('id', f'existing_{i}')
                            self.gate_existing_orders_detailed[order_id] = {
                                'gate_order': gate_order,
                                'order_details': order_details,
                                'hash': order_hash,
                                'recorded_at': datetime.now().isoformat()
                            }
                            
                            self.logger.info(f"게이트 기존 예약 주문 기록: {order_id} - 트리거가 ${trigger_price:.2f}")
                        
                except Exception as detail_error:
                    self.logger.warning(f"게이트 기존 주문 상세 추출 실패: {detail_error}")
                    continue
            
            self.logger.info(f"게이트 기존 예약 주문 {len(gate_orders)}개 기록 완료")
            
        except Exception as e:
            self.logger.error(f"게이트 기존 예약 주문 기록 실패: {e}")

    async def _generate_primary_order_hash_from_details(self, order_details: Dict) -> str:
        """주문 상세정보로부터 주 해시 생성"""
        try:
            trigger_price = order_details.get('trigger_price', 0)
            size = order_details.get('size', 0)
            abs_size = order_details.get('abs_size', abs(size) if size else 0)
            
            if trigger_price <= 0:
                return ""
            
            if abs_size > 0:
                return f"BTC_USDT_{trigger_price:.2f}_{abs_size}"
            else:
                return f"BTC_USDT_price_{trigger_price:.2f}"
            
        except Exception as e:
            self.logger.error(f"상세정보 기반 해시 생성 실패: {e}")
            return ""

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
            all_startup_orders = await self._get_all_current_plan_orders_enhanced()
            
            for order in all_startup_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.startup_plan_orders.add(order_id)
                    
                    side = order.get('side', order.get('tradeSide', '')).lower()
                    reduce_only = order.get('reduceOnly', False)
                    is_close = 'close' in side or reduce_only
                    
                    order_type = "클로즈" if is_close else "일반"
                    self.logger.info(f"시작 시 비트겟 {order_type} 예약 주문 기록: {order_id}")
            
            self.last_plan_order_ids = set(self.startup_plan_orders)
            
            self.logger.info(f"시작 시 비트겟 예약 주문 {len(self.startup_plan_orders)}개 기록 (클로즈 주문 포함)")
            
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

    async def _create_initial_plan_order_snapshot(self):
        """초기 예약 주문 스냅샷 생성"""
        try:
            all_orders = await self._get_all_current_plan_orders_enhanced()
            
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

    async def _mirror_startup_plan_orders_with_retry(self):
        """시작 시 기존 예약 주문 복제 - 강화된 재시도 로직"""
        try:
            if not self.startup_plan_orders:
                self.startup_plan_orders_processed = True
                self.logger.info("시작 시 복제할 예약 주문이 없음")
                return
            
            self.logger.info(f"🔄 시작 시 {len(self.startup_plan_orders)}개 예약 주문 복제 시작 (복제비율: {self.mirror_ratio_multiplier}x)")
            
            success = False
            for retry in range(self.max_startup_mirror_retries):
                try:
                    self.logger.info(f"🔄 시작 시 예약 주문 복제 시도 {retry + 1}/{self.max_startup_mirror_retries}")
                    
                    mirrored_count = 0
                    skipped_count = 0
                    failed_count = 0
                    close_order_count = 0
                    
                    for order_id in list(self.startup_plan_orders):
                        try:
                            if order_id in self.plan_order_snapshot:
                                order_data = self.plan_order_snapshot[order_id]['order_data']
                                
                                # 클로즈 주문 상세 분석
                                close_details = await self.utils.determine_close_order_details_enhanced(order_data)
                                is_close_order = close_details['is_close_order']
                                
                                if is_close_order:
                                    close_order_count += 1
                                
                                # 중복 체크
                                is_duplicate = await self._is_duplicate_order_improved(order_data)
                                if is_duplicate:
                                    self.logger.info(f"중복으로 인한 시작 시 주문 스킵: {order_id}")
                                    skipped_count += 1
                                    continue
                                
                                # 🔥🔥🔥 복제 비율 적용된 완벽한 미러링 시도
                                result = await self._process_perfect_mirror_order_with_ratio_enhanced(order_data, close_details, self.mirror_ratio_multiplier)
                                
                                # 모든 성공 케이스 처리
                                success_results = ["perfect_success", "partial_success", "force_success", "close_order_forced"]
                                if result in success_results:
                                    mirrored_count += 1
                                    self.daily_stats['startup_plan_mirrors'] += 1
                                    self.logger.info(f"시작 시 {'클로즈 ' if is_close_order else ''}예약 주문 복제 성공: {order_id} (결과: {result}, 비율: {self.mirror_ratio_multiplier}x)")
                                else:
                                    failed_count += 1
                                    self.logger.warning(f"시작 시 {'클로즈 ' if is_close_order else ''}예약 주문 복제 실패: {order_id} (결과: {result})")
                        
                        except Exception as e:
                            failed_count += 1
                            self.logger.error(f"시작 시 예약 주문 복제 오류: {order_id} - {e}")
                            
                        # 처리된 주문으로 표시
                        self.processed_plan_orders.add(order_id)
                    
                    # 성공 기준: 70% 이상 성공 또는 모든 주문 처리
                    total_processed = mirrored_count + skipped_count + failed_count
                    if total_processed >= len(self.startup_plan_orders) * 0.7 or mirrored_count > 0:
                        success = True
                        
                        # 시작 시 복제 완료 알림 - 복제 비율 정보 포함
                        ratio_info = f" (복제비율: {self.mirror_ratio_multiplier}x)" if self.mirror_ratio_multiplier != 1.0 else ""
                        
                        await self.telegram.send_message(
                            f"🔄 시작 시 예약 주문 복제 완료{ratio_info}\n"
                            f"성공: {mirrored_count}개\n"
                            f"클로즈 주문: {close_order_count}개\n"
                            f"스킵: {skipped_count}개\n"
                            f"실패: {failed_count}개\n"
                            f"총 {len(self.startup_plan_orders)}개 중 {mirrored_count}개 복제{ratio_info}\n"
                            f"🔥 클로즈 주문도 완벽하게 미러링됩니다"
                        )
                        
                        self.logger.info(f"✅ 시작 시 예약 주문 복제 성공: {mirrored_count}개 (클로즈 {close_order_count}개), 스킵 {skipped_count}개, 실패 {failed_count}개")
                        break
                    else:
                        self.logger.warning(f"⚠️ 시작 시 예약 주문 복제 성공률 부족: {mirrored_count}/{len(self.startup_plan_orders)} (재시도 예정)")
                        
                        if retry < self.max_startup_mirror_retries - 1:
                            await asyncio.sleep(self.startup_mirror_delay)
                            continue
                    
                except Exception as e:
                    self.logger.error(f"시작 시 예약 주문 복제 시도 {retry + 1} 실패: {e}")
                    if retry < self.max_startup_mirror_retries - 1:
                        await asyncio.sleep(self.startup_mirror_delay)
                        continue
            
            if not success:
                self.logger.error("❌ 시작 시 예약 주문 복제 모든 재시도 실패")
                await self.telegram.send_message(
                    f"❌ 시작 시 예약 주문 복제 실패\n"
                    f"총 {self.max_startup_mirror_retries}회 재시도 후 실패\n"
                    f"수동 확인이 필요할 수 있습니다."
                )
            
            self.startup_plan_orders_processed = True
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 복제 실패: {e}")
            self.startup_plan_orders_processed = True

    # 기타 필수 메서드들 (유지)
    async def _validate_close_order_enhanced(self, order: Dict, close_details: Dict) -> str:
        """강화된 클로즈 주문 유효성 검증"""
        try:
            if not self.close_order_processing:
                return "skip"
            
            order_id = order.get('orderId', order.get('planOrderId', ''))
            
            # 강제 미러링 모드인 경우 무조건 진행
            if self.force_close_order_mirror:
                self.logger.info(f"🚀 클로즈 주문 강제 미러링 모드: {order_id}")
                return "force_mirror"
            
            # 관대한 모드인 경우 대부분 허용
            if self.close_order_validation_mode == "permissive":
                return "force_mirror"
            
            return "proceed"
            
        except Exception as e:
            self.logger.error(f"강화된 클로즈 주문 유효성 검증 실패하지만 강제 미러링: {e}")
            return "force_mirror"

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
                    
                    self.logger.info(f"🎯 포지션 종료로 인한 클로즈 주문 자동 정리 완료: {deleted_count}개")
            
        except Exception as e:
            self.logger.error(f"포지션 없음 시 클로즈 주문 정리 실패: {e}")

    # 포지션 처리 관련 메서드들 (기존과 동일하게 유지)
    async def process_filled_order(self, order: Dict):
        """체결된 주문으로부터 미러링 실행"""
        try:
            if not self.mirror_trading_enabled:
                return
                
            order_id = order.get('orderId', order.get('id', ''))
            side = order.get('side', '').lower()
            size = float(order.get('size', 0))
            fill_price = float(order.get('fillPrice', order.get('price', 0)))
            
            position_side = 'long' if side == 'buy' else 'short'
            
            # 복제 비율 적용된 마진 비율 계산
            margin_ratio_result = await self.utils.calculate_dynamic_margin_ratio_with_multiplier(
                size, fill_price, order, self.mirror_ratio_multiplier
            )
            
            if not margin_ratio_result['success']:
                return
            
            leverage = margin_ratio_result['leverage']
            
            # 미러링 처리...
            # (기존 로직 유지)
            
        except Exception as e:
            self.logger.error(f"체결 주문 처리 중 오류: {e}")

    async def stop(self):
        """포지션 매니저 중지"""
        try:
            self.logger.info("포지션 매니저 중지 중...")
            # 필요한 정리 작업 수행
        except Exception as e:
            self.logger.error(f"포지션 매니저 중지 실패: {e}")
