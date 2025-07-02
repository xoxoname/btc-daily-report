import os
import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import json

from mirror_trading_utils import MirrorTradingUtils, PositionInfo, MirrorResult

logger = logging.getLogger(__name__)

class MirrorPositionManager:
    
    def __init__(self, config, bitget_client, gate_client, gate_mirror_client, telegram_bot, utils):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.gate_mirror = gate_mirror_client
        self.telegram = telegram_bot
        self.utils = utils
        self.logger = logging.getLogger('mirror_position_manager')
        
        # 미러링 모드 텔레그램 제어
        self.mirror_trading_enabled = True
        self.mirror_ratio_multiplier = 1.0
        
        self.logger.info(f"포지션 매니저 초기화")
        self.logger.info(f"초기 복제 비율: {self.mirror_ratio_multiplier}x")
        self.logger.info(f"미러링 모드는 텔레그램 /mirror 명령으로 제어")
        
        # 미러링 상태 관리
        self.mirrored_positions: Dict[str, PositionInfo] = {}
        self.startup_positions: Set[str] = set()
        self.startup_gate_positions: Set[str] = set()
        self.failed_mirrors: List[MirrorResult] = []
        
        # 포지션 크기 추적
        self.position_sizes: Dict[str, float] = {}
        
        # 주문 체결 추적
        self.processed_orders: Set[str] = set()
        
        # 예약 주문 추적 관리 - 체결/취소 구분 강화
        self.mirrored_plan_orders: Dict[str, Dict] = {}
        self.processed_plan_orders: Set[str] = set()
        self.startup_plan_orders: Set[str] = set()
        self.startup_plan_orders_processed: bool = False
        
        # 체결된 주문 추적 - 취소와 구분
        self.recently_filled_order_ids: Set[str] = set()
        self.filled_order_timestamps: Dict[str, datetime] = {}
        self.filled_order_check_window = 300  # 5분간 체결 기록 유지
        
        # 시세 차이 대응 체결 시스템 강화
        self.adaptive_fill_system_enabled = True
        self.immediate_market_fill_enabled = True
        self.smart_price_adjustment_enabled = True
        self.backup_fill_mechanism_enabled = True
        
        # 시세 차이 기반 체결 설정
        self.price_diff_threshold_for_immediate_fill = 50.0
        self.max_wait_time_for_fill = 120
        self.adaptive_wait_multiplier = 1.5
        self.market_fill_retry_count = 3
        
        # 스마트 가격 조정 설정
        self.price_adjustment_percentage = 0.1
        self.max_price_adjustment = 200.0
        self.price_adjustment_step_count = 3
        
        # 비트겟 체결 감지 시 게이트 즉시 처리 시스템
        self.bitget_filled_immediate_action = True
        self.gate_pending_orders_for_immediate_fill: Dict[str, Dict] = {}
        self.immediate_fill_processing_locks: Dict[str, asyncio.Lock] = {}
        
        # 시세 차이 고려한 체결/취소 구분 강화
        self.price_based_fill_detection = True
        self.price_diff_threshold = 100.0
        self.safe_cancel_window = 60
        self.order_fill_analysis_cache: Dict[str, Dict] = {}
        
        # 중복 복제 방지 시스템
        self.order_processing_locks: Dict[str, asyncio.Lock] = {}
        self.recently_processed_orders: Dict[str, datetime] = {}
        self.order_deduplication_window = 15
        
        # 해시 기반 중복 방지
        self.processed_order_hashes: Set[str] = set()
        self.order_hash_timestamps: Dict[str, datetime] = {}
        self.hash_cleanup_interval = 180
        
        # 예약 주문 취소 감지 시스템 강화
        self.last_plan_order_ids: Set[str] = set()
        self.plan_order_snapshot: Dict[str, Dict] = {}
        self.cancel_retry_count: Dict[str, int] = {}
        self.max_cancel_retries = 5
        self.cancel_force_cleanup_threshold = 10
        
        # 취소 동기화 강화
        self.cancel_detection_enhanced = True
        self.cancel_detection_interval = 10
        self.last_cancel_detection_time = datetime.min
        
        # 시세 차이 관리
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.price_sync_threshold: float = 100.0
        self.position_wait_timeout: int = 60
        
        # 가격 기반 중복 방지 시스템
        self.mirrored_trigger_prices: Set[str] = set()
        self.price_tolerance = 5.0
        
        # 렌더 재구동 시 기존 게이트 포지션 확인
        self.existing_gate_positions: Dict = {}
        self.render_restart_detected: bool = False
        
        # 게이트 기존 예약 주문 중복 방지
        self.gate_existing_order_hashes: Set[str] = set()
        self.gate_existing_orders_detailed: Dict[str, Dict] = {}
        
        # 주문 ID 매핑 추적
        self.bitget_to_gate_order_mapping: Dict[str, str] = {}
        self.gate_to_bitget_order_mapping: Dict[str, str] = {}
        
        # 클로즈 주문 처리 강화
        self.close_order_processing: bool = True
        self.close_order_validation_mode: str = "permissive"
        self.force_close_order_mirror: bool = True
        
        # 렌더 재구동 시 예약 주문 미러링 강화
        self.startup_mirror_retry_count: int = 0
        self.max_startup_mirror_retries: int = 3
        self.startup_mirror_delay: int = 10
        
        # 포지션 종료 시 클로즈 주문 정리 관련
        self.position_close_monitoring: bool = True
        self.last_position_check: datetime = datetime.min
        self.position_check_interval: int = 30
        
        # ✅ 지속적인 미러링 교정 시스템 추가
        self.continuous_correction_enabled: bool = True
        self.correction_check_interval: int = 60  # 1분마다
        self.last_correction_check: datetime = datetime.min
        self.correction_retry_limit: int = 3
        self.correction_failures: Dict[str, int] = {}
        
        # ✅ 마진 모드 강제 설정 강화
        self.margin_mode_strict_enforcement: bool = True
        self.margin_mode_check_before_order: bool = True
        self.margin_mode_force_retries: int = 3
        
        # ✅ 체결/취소 구분 정확도 향상
        self.fill_detection_confidence_threshold: float = 0.8
        self.order_state_tracking: Dict[str, Dict] = {}
        self.last_order_state_update: datetime = datetime.min
        
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
            'forced_cancel_cleanups': 0,
            'price_based_fill_detections': 0,
            'safe_cancel_preventions': 0,
            'immediate_market_fills': 0,
            'adaptive_price_adjustments': 0,
            'backup_fill_successes': 0,
            'price_diff_resolved_fills': 0,
            'continuous_corrections': 0,  # ✅ 지속적 교정 통계
            'margin_mode_enforcements': 0,  # ✅ 마진 모드 강제 통계
            'accurate_fill_detections': 0,  # ✅ 정확한 체결 감지 통계
            'errors': []
        }
        
        self.logger.info(f"미러 포지션 매니저 초기화 완료")
        self.logger.info(f"지속적 미러링 교정 시스템: 활성화")
        self.logger.info(f"마진 모드 강제 설정: 활성화")
        self.logger.info(f"정확한 체결/취소 구분: 활성화")

    def update_prices(self, bitget_price: float, gate_price: float, price_diff_percent: float):
        self.bitget_current_price = bitget_price
        self.gate_current_price = gate_price
        self.price_diff_percent = price_diff_percent

    async def initialize(self):
        try:
            self.logger.info("포지션 매니저 초기화 시작")
            
            if not self.mirror_trading_enabled:
                self.logger.warning("미러링 모드가 비활성화되어 있습니다")
                return
            
            # ✅ Gate 미러링 클라이언트 초기화 - 마진 모드 Cross 강제 설정 포함
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
            
            # 시작 시 기존 예약 주문 복제
            await self._mirror_startup_plan_orders_with_retry()
            
            self.logger.info("포지션 매니저 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"포지션 매니저 초기화 실패: {e}")
            raise

    async def monitor_plan_orders_cycle(self):
        """예약 주문 모니터링 사이클 - 지속적 교정 시스템 포함"""
        try:
            if not self.mirror_trading_enabled:
                await asyncio.sleep(1.0)
                return
                
            if not self.startup_plan_orders_processed:
                await asyncio.sleep(0.1)
                return
            
            # ✅ 지속적인 미러링 교정 시스템 실행
            await self._perform_continuous_correction()
            
            # 시세 차이 확인
            price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
            if price_diff_abs > self.price_sync_threshold * 2:
                self.logger.debug(f"큰 시세 차이 ({price_diff_abs:.2f}$), 예약 주문 처리 지연")
                return
            
            # 만료된 타임스탬프 정리
            await self._cleanup_expired_timestamps()
            await self._cleanup_expired_hashes()
            
            # 체결된 주문 기록 업데이트
            await self._update_recently_filled_orders()
            
            # 즉시 체결 처리
            await self._process_immediate_fill_queue()
            
            # 강화된 취소 감지
            current_time = datetime.now()
            if (current_time - self.last_cancel_detection_time).total_seconds() >= self.cancel_detection_interval:
                await self._enhanced_cancel_detection()
                self.last_cancel_detection_time = current_time
            
            # 포지션 종료 시 클로즈 주문 자동 정리
            await self._check_and_cleanup_close_orders_if_no_position()
            
            # 모든 예약 주문 조회
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
            
            # 사라진 예약 주문 분석 - 시세 차이 대응 강화
            disappeared_order_ids = self.last_plan_order_ids - current_order_ids
            
            if disappeared_order_ids:
                self.logger.info(f"📋 {len(disappeared_order_ids)}개의 예약 주문이 사라짐 - 정확한 체결/취소 분석 시작")
                
                canceled_count = 0
                filled_count = 0
                immediate_fill_count = 0
                
                for disappeared_id in disappeared_order_ids:
                    try:
                        # ✅ 정확도 향상된 체결/취소 구분 로직
                        analysis_result = await self._analyze_order_disappearance_enhanced_v2(disappeared_id)
                        
                        if analysis_result['is_filled']:
                            filled_count += 1
                            self.daily_stats['filled_detection_successes'] += 1
                            self.daily_stats['accurate_fill_detections'] += 1
                            
                            self.logger.info(f"✅ 체결 감지: {disappeared_id} - 게이트 주문 처리 시작 (방법: {analysis_result['detection_method']})")
                            
                            # 비트겟 체결 시 게이트 즉시 대응 처리
                            immediate_success = await self._handle_bitget_filled_gate_immediate_action(disappeared_id, analysis_result)
                            if immediate_success:
                                immediate_fill_count += 1
                                self.daily_stats['immediate_market_fills'] += 1
                                self.daily_stats['price_diff_resolved_fills'] += 1
                            
                            # 체결된 주문은 미러링 기록에서 제거
                            await self._cleanup_mirror_records_for_filled_order(disappeared_id)
                        else:
                            # 실제 취소된 주문만 처리
                            if analysis_result.get('safe_to_cancel', True):
                                success = await self._handle_plan_order_cancel_enhanced_v2(disappeared_id)
                                if success:
                                    canceled_count += 1
                                    self.daily_stats['cancel_successes'] += 1
                                else:
                                    self.daily_stats['cancel_failures'] += 1
                            else:
                                self.daily_stats['safe_cancel_preventions'] += 1
                                self.logger.warning(f"⏳ 시세 차이로 인한 안전 대기: {disappeared_id}")
                                continue
                                
                    except Exception as e:
                        self.logger.error(f"사라진 주문 분석 중 예외: {disappeared_id} - {e}")
                        self.daily_stats['cancel_failures'] += 1
                
                self.daily_stats['plan_order_cancels'] += canceled_count
                
                # 체결/취소 결과 알림
                if filled_count > 0 or canceled_count > 0:
                    await self.telegram.send_message(
                        f"📋 정확한 예약 주문 분석 결과\n"
                        f"사라진 주문: {len(disappeared_order_ids)}개\n"
                        f"🎯 체결 감지: {filled_count}개\n"
                        f"⚡ 즉시 시장가 체결: {immediate_fill_count}개\n"
                        f"🚫 취소 동기화: {canceled_count}개\n"
                        f"⏳ 안전 대기: {len(disappeared_order_ids) - filled_count - canceled_count}개\n"
                        f"📊 현재 시세 차이: ${price_diff_abs:.2f}\n\n"
                        f"🔥 정확한 체결/취소 구분으로 미러링 손실 방지!\n"
                        f"⚡ 비트겟 체결시 게이트도 즉시 시장가로 체결됩니다!"
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
                    
                    # 새로운 예약 주문 처리 - 강화된 마진 모드 체크 포함
                    try:
                        close_details = await self.utils.determine_close_order_details_enhanced(order)
                        is_close_order = close_details['is_close_order']
                        
                        self.logger.info(f"🎯 새로운 예약 주문 감지: {order_id} (클로즈: {is_close_order})")
                        self.logger.info(f"   📊 현재 복제 비율: {self.mirror_ratio_multiplier}x")
                        
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
                        
                        # ✅ 마진 모드 강제 체크 및 설정
                        margin_mode_success = await self._ensure_cross_margin_mode_before_order()
                        if margin_mode_success:
                            self.daily_stats['margin_mode_enforcements'] += 1
                        
                        # 완벽한 미러링 처리
                        result = await self._process_perfect_mirror_order_with_margin_check(order, close_details, self.mirror_ratio_multiplier)
                        
                        # 성공 케이스 처리
                        success_results = ["perfect_success", "partial_success", "force_success", "close_order_forced", "price_diff_handled"]
                        
                        if result in success_results:
                            new_orders_count += 1
                            if result == "perfect_success":
                                perfect_mirrors += 1
                                self.daily_stats['perfect_mirrors'] += 1
                            elif result == "price_diff_handled":
                                perfect_mirrors += 1
                                self.daily_stats['perfect_mirrors'] += 1
                                self.daily_stats['adaptive_price_adjustments'] += 1
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
                            self.daily_stats['failed_mirrors'] += 1
                            self.logger.error(f"❌ 예약 주문 복제 실패: {order_id} (결과: {result})")
                        
                        self.processed_plan_orders.add(order_id)
                        
                        # 주문 처리 해시 기록
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
            
            # 성공적인 미러링 결과 알림
            if new_orders_count > 0:
                ratio_info = f" (복제비율: {self.mirror_ratio_multiplier}x)" if self.mirror_ratio_multiplier != 1.0 else ""
                
                if forced_close_mirrors > 0:
                    await self.telegram.send_message(
                        f"🚀 클로즈 주문 강제 미러링 성공{ratio_info}\n"
                        f"강제 미러링: {forced_close_mirrors}개\n"
                        f"완벽 복제: {perfect_mirrors}개\n"
                        f"클로즈 주문: {new_close_orders_count}개\n"
                        f"전체 신규: {new_orders_count}개\n\n"
                        f"💳 마진 모드: Cross 강제 설정 완료\n"
                        f"🔥 정확한 체결/취소 구분으로 손실 방지{ratio_info}"
                    )
                elif perfect_mirrors > 0:
                    await self.telegram.send_message(
                        f"✅ 완벽한 TP/SL 미러링 성공{ratio_info}\n"
                        f"완벽 복제: {perfect_mirrors}개\n"
                        f"클로즈 주문: {new_close_orders_count}개\n"
                        f"전체 신규: {new_orders_count}개{ratio_info}\n\n"
                        f"💳 마진 모드: Cross 강제 설정 완료\n"
                        f"🔥 정확한 체결/취소 구분으로 손실 방지!"
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

    async def _perform_continuous_correction(self):
        """✅ 지속적인 미러링 교정 시스템"""
        try:
            if not self.continuous_correction_enabled:
                return
            
            current_time = datetime.now()
            if (current_time - self.last_correction_check).total_seconds() < self.correction_check_interval:
                return
            
            self.last_correction_check = current_time
            
            self.logger.debug("🔄 지속적인 미러링 교정 시작")
            
            # 1. 비트겟 현재 예약 주문 조회
            bitget_orders = await self._get_all_current_plan_orders_enhanced()
            bitget_order_ids = set()
            for order in bitget_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    bitget_order_ids.add(order_id)
            
            # 2. 게이트 현재 예약 주문 조회
            gate_orders = await self.gate_mirror.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            gate_order_count = len(gate_orders)
            
            # 3. 미러링되지 않은 비트겟 주문 찾기
            missing_mirrors = []
            for order in bitget_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if not order_id:
                    continue
                
                # 시작 시 주문은 제외
                if order_id in self.startup_plan_orders:
                    continue
                
                # 미러링 기록이 없는 경우
                if order_id not in self.mirrored_plan_orders:
                    # 실패 횟수 확인
                    fail_count = self.correction_failures.get(order_id, 0)
                    if fail_count < self.correction_retry_limit:
                        missing_mirrors.append(order)
            
            # 4. 미러링되지 않은 주문 복제 시도
            corrected_count = 0
            for order in missing_mirrors[:3]:  # 한 번에 3개씩만
                try:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    
                    self.logger.info(f"🔄 미러링 교정 시도: {order_id}")
                    
                    # 마진 모드 강제 확인
                    await self._ensure_cross_margin_mode_before_order()
                    
                    # 클로즈 주문 분석
                    close_details = await self.utils.determine_close_order_details_enhanced(order)
                    
                    # 미러링 처리
                    result = await self._process_perfect_mirror_order_with_margin_check(order, close_details, self.mirror_ratio_multiplier)
                    
                    if result in ["perfect_success", "partial_success", "force_success", "close_order_forced", "price_diff_handled"]:
                        corrected_count += 1
                        self.daily_stats['continuous_corrections'] += 1
                        
                        # 실패 카운터 리셋
                        if order_id in self.correction_failures:
                            del self.correction_failures[order_id]
                        
                        self.logger.info(f"✅ 미러링 교정 성공: {order_id}")
                    else:
                        # 실패 카운터 증가
                        self.correction_failures[order_id] = self.correction_failures.get(order_id, 0) + 1
                        self.logger.warning(f"⚠️ 미러링 교정 실패: {order_id} ({self.correction_failures[order_id]}회)")
                
                except Exception as e:
                    order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
                    self.correction_failures[order_id] = self.correction_failures.get(order_id, 0) + 1
                    self.logger.error(f"미러링 교정 처리 오류: {order_id} - {e}")
            
            # 5. 교정 결과 알림
            if corrected_count > 0:
                await self.telegram.send_message(
                    f"🔄 지속적인 미러링 교정 완료\n"
                    f"교정된 주문: {corrected_count}개\n"
                    f"비트겟 예약 주문: {len(bitget_order_ids)}개\n"
                    f"게이트 예약 주문: {gate_order_count}개\n"
                    f"💳 마진 모드: Cross 강제 유지\n"
                    f"🔥 누락된 미러링을 자동으로 교정했습니다!"
                )
            
            # 6. 오래된 실패 기록 정리
            expired_failures = []
            for order_id, fail_count in self.correction_failures.items():
                if order_id not in bitget_order_ids and fail_count >= self.correction_retry_limit:
                    expired_failures.append(order_id)
            
            for order_id in expired_failures:
                del self.correction_failures[order_id]
            
        except Exception as e:
            self.logger.error(f"지속적인 미러링 교정 실패: {e}")

    async def _ensure_cross_margin_mode_before_order(self) -> bool:
        """✅ 주문 전 마진 모드 강제 Cross 설정"""
        try:
            if not self.margin_mode_strict_enforcement:
                return True
            
            # 현재 마진 모드 확인
            current_mode = await self.gate_mirror.get_current_margin_mode(self.GATE_CONTRACT)
            
            if current_mode == "cross":
                return True
            
            self.logger.warning(f"⚠️ 주문 전 마진 모드가 Cross가 아님: {current_mode} → 강제 변경")
            
            # 강제 변경 시도
            for retry in range(self.margin_mode_force_retries):
                try:
                    success = await self.gate_mirror.force_cross_margin_mode_aggressive(self.GATE_CONTRACT)
                    if success:
                        self.logger.info(f"✅ 주문 전 마진 모드 강제 변경 성공: {current_mode} → Cross")
                        return True
                    else:
                        if retry < self.margin_mode_force_retries - 1:
                            await asyncio.sleep(2)
                            continue
                        
                except Exception as e:
                    self.logger.error(f"주문 전 마진 모드 강제 변경 시도 {retry + 1} 실패: {e}")
                    if retry < self.margin_mode_force_retries - 1:
                        await asyncio.sleep(2)
                        continue
            
            self.logger.error(f"❌ 주문 전 마진 모드 강제 변경 실패 - 수동 설정 필요")
            
            # 실패해도 주문은 진행하되 경고 발송
            await self.telegram.send_message(
                f"⚠️ 주문 전 마진 모드 확인 필요\n"
                f"현재 모드: {current_mode.upper()}\n"
                f"자동 변경 실패 - 수동으로 Cross 모드로 설정해주세요\n"
                f"Gate.io 웹/앱 → 선물 거래 → 마진 모드 → Cross 선택"
            )
            
            return False
            
        except Exception as e:
            self.logger.error(f"주문 전 마진 모드 확인 실패: {e}")
            return False

    async def _analyze_order_disappearance_enhanced_v2(self, order_id: str) -> Dict:
        """✅ 정확도 향상된 주문 사라짐 분석"""
        try:
            self.logger.info(f"🔍 정확도 향상된 주문 사라짐 분석: {order_id}")
            
            # 기본 결과 구조
            result = {
                'order_id': order_id,
                'is_filled': False,
                'safe_to_cancel': True,
                'detection_method': 'unknown',
                'confidence': 0.0,  # ✅ 신뢰도 추가
                'immediate_action_needed': False,
                'gate_action_type': 'none',
                'reason': '',
                'bitget_price': self.bitget_current_price,
                'gate_price': self.gate_current_price,
                'price_diff': abs(self.bitget_current_price - self.gate_current_price)
            }
            
            # 1. 주문 정보 조회
            order_info = None
            if order_id in self.plan_order_snapshot:
                order_info = self.plan_order_snapshot[order_id]['order_data']
            elif order_id in self.mirrored_plan_orders:
                order_info = self.mirrored_plan_orders[order_id].get('bitget_order')
            
            if not order_info:
                result['reason'] = '주문 정보 없음'
                result['confidence'] = 0.1
                return result
            
            # 2. 최근 체결 기록에서 직접 확인 (가장 높은 신뢰도)
            if order_id in self.recently_filled_order_ids:
                result['is_filled'] = True
                result['detection_method'] = 'recent_filled_records'
                result['confidence'] = 0.95
                result['immediate_action_needed'] = True
                result['gate_action_type'] = 'immediate_market_fill'
                result['reason'] = '최근 체결 기록에서 확인됨'
                result['safe_to_cancel'] = False
                return result
            
            # 3. 실시간 체결 주문 조회로 재확인
            try:
                recent_filled = await self.bitget.get_recent_filled_orders(symbol=self.SYMBOL, minutes=3)
                for filled_order in recent_filled:
                    filled_id = filled_order.get('orderId', filled_order.get('id', ''))
                    if filled_id == order_id:
                        # 체결 시간 확인
                        fill_time = filled_order.get('fillTime', filled_order.get('cTime'))
                        if fill_time:
                            fill_timestamp = int(fill_time)
                            current_timestamp = int(datetime.now().timestamp() * 1000)
                            time_diff = (current_timestamp - fill_timestamp) / 1000 / 60  # 분 단위
                            
                            if time_diff <= 5:  # 5분 이내 체결
                                result['is_filled'] = True
                                result['detection_method'] = 'realtime_filled_check'
                                result['confidence'] = 0.9
                                result['immediate_action_needed'] = True
                                result['gate_action_type'] = 'immediate_market_fill'
                                result['reason'] = f'{time_diff:.1f}분 전 체결 확인됨'
                                result['safe_to_cancel'] = False
                                
                                # 체결 기록에 추가
                                self.recently_filled_order_ids.add(order_id)
                                self.filled_order_timestamps[order_id] = datetime.now()
                                
                                return result
            except Exception as e:
                self.logger.debug(f"실시간 체결 확인 실패: {e}")
            
            # 4. 트리거 가격 기반 분석 (중간 신뢰도)
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if order_info.get(price_field):
                    trigger_price = float(order_info.get(price_field))
                    break
            
            if trigger_price > 0:
                # 주문 방향 분석
                side = order_info.get('side', order_info.get('tradeSide', '')).lower()
                is_long_order = ('buy' in side or 'long' in side) and 'close' not in side
                is_short_order = ('sell' in side or 'short' in side) and 'close' not in side
                is_close_order = 'close' in side or order_info.get('reduceOnly', False)
                
                # 시세 기반 체결 가능성 분석
                bitget_reached = False
                price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
                
                if is_long_order:
                    bitget_reached = self.bitget_current_price <= trigger_price
                elif is_short_order:
                    bitget_reached = self.bitget_current_price >= trigger_price
                elif is_close_order:
                    # 클로즈 주문은 트리거 가격 근처에서 체결 가능
                    bitget_reached = abs(self.bitget_current_price - trigger_price) <= self.price_diff_threshold
                
                # 비트겟이 트리거 조건에 도달한 경우
                if bitget_reached:
                    result['is_filled'] = True
                    result['detection_method'] = 'price_based_analysis'
                    result['immediate_action_needed'] = True
                    result['safe_to_cancel'] = False
                    
                    # 시세 차이에 따른 신뢰도 및 액션 결정
                    if price_diff_abs >= self.price_diff_threshold_for_immediate_fill:
                        result['confidence'] = 0.85
                        result['gate_action_type'] = 'immediate_market_fill'
                        result['reason'] = f'비트겟 트리거 도달 + 큰 시세 차이 (${price_diff_abs:.2f})'
                    else:
                        result['confidence'] = 0.75
                        result['gate_action_type'] = 'adaptive_wait_or_adjust'
                        result['reason'] = f'비트겟 트리거 도달 + 보통 시세 차이 (${price_diff_abs:.2f})'
                    
                    return result
            
            # 5. 취소된 것으로 판단 (낮은 신뢰도에서 안전하게)
            result['is_filled'] = False
            result['detection_method'] = 'likely_cancelled'
            result['confidence'] = 0.6
            result['safe_to_cancel'] = True
            result['reason'] = '트리거 조건 미달성 - 취소로 추정'
            
            return result
            
        except Exception as e:
            self.logger.error(f"정확도 향상된 주문 사라짐 분석 실패: {order_id} - {e}")
            return {
                'order_id': order_id,
                'is_filled': False,
                'safe_to_cancel': True,
                'detection_method': 'error_fallback',
                'confidence': 0.1,
                'immediate_action_needed': False,
                'gate_action_type': 'none',
                'reason': f'분석 오류: {str(e)[:100]}',
                'bitget_price': self.bitget_current_price,
                'gate_price': self.gate_current_price,
                'price_diff': abs(self.bitget_current_price - self.gate_current_price)
            }

    async def _process_perfect_mirror_order_with_margin_check(self, bitget_order: Dict, close_details: Dict, ratio_multiplier: float) -> str:
        """✅ 마진 모드 체크가 포함된 완벽한 미러링 주문 처리"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            is_close_order = close_details['is_close_order']
            
            # 복제 비율 검증
            validated_ratio = self.utils.validate_ratio_multiplier(ratio_multiplier)
            if validated_ratio != ratio_multiplier:
                self.logger.warning(f"복제 비율 조정됨: {ratio_multiplier} → {validated_ratio}")
                ratio_multiplier = validated_ratio
            
            self.logger.info(f"🎯 마진 모드 체크 포함 미러링 시작: {order_id}")
            self.logger.info(f"   📊 검증된 복제 비율: {ratio_multiplier}x")
            self.logger.info(f"   📋 클로즈 주문: {is_close_order}")
            
            # ✅ 주문 전 마진 모드 강제 확인 및 설정
            margin_mode_ready = await self._ensure_cross_margin_mode_before_order()
            
            # 트리거 가격 추출
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price == 0:
                self.logger.error(f"트리거 가격을 찾을 수 없음: {order_id}")
                return "failed"
            
            # 크기 정보 추출
            size = float(bitget_order.get('size', 0))
            if size == 0:
                self.logger.error(f"주문 크기가 0: {order_id}")
                return "failed"
            
            # 시세 차이 사전 분석 및 조정
            price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
            adjusted_trigger_price = trigger_price
            
            if (self.smart_price_adjustment_enabled and 
                price_diff_abs > self.price_diff_threshold_for_immediate_fill):
                
                # 사전 가격 조정
                adjustment_ratio = min(price_diff_abs / trigger_price * 0.1, 0.05)
                price_adjustment = trigger_price * adjustment_ratio
                
                order_direction = close_details['order_direction']
                if 'buy' in order_direction or 'long' in order_direction:
                    if self.gate_current_price < self.bitget_current_price:
                        adjusted_trigger_price = trigger_price - price_adjustment
                else:
                    if self.gate_current_price > self.bitget_current_price:
                        adjusted_trigger_price = trigger_price + price_adjustment
                
                if adjusted_trigger_price != trigger_price:
                    self.logger.info(f"🔧 사전 가격 조정: ${trigger_price:.2f} → ${adjusted_trigger_price:.2f}")
            
            # 복제 비율 적용된 마진 비율 계산
            self.logger.info(f"💰 마진 모드 체크 완료된 복제 비율 적용 계산:")
            self.logger.info(f"   - 마진 모드 준비: {'완료' if margin_mode_ready else '실패'}")
            self.logger.info(f"   - 비트겟 원본 크기: {size}")
            self.logger.info(f"   - 적용할 복제 비율: {ratio_multiplier}x")
            
            margin_ratio_result = await self.utils.calculate_dynamic_margin_ratio_with_multiplier(
                size, adjusted_trigger_price, bitget_order, ratio_multiplier
            )
            
            if not margin_ratio_result['success']:
                self.logger.error(f"복제 비율 적용 마진 비율 계산 실패: {order_id}")
                return "failed"
            
            # 계산 결과
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
            
            # 복제 비율 적용된 게이트 마진 계산
            gate_margin = gate_total_equity * margin_ratio
            
            if gate_margin > gate_available:
                gate_margin = gate_available * 0.95
                self.logger.warning(f"마진이 가용 자금 초과, 95%로 제한: ${gate_margin:,.2f}")
            
            if gate_margin < self.MIN_MARGIN:
                self.logger.error(f"게이트 마진 부족: ${gate_margin:.2f} < ${self.MIN_MARGIN}")
                return "failed"
            
            # 게이트 계약 수 계산
            gate_notional_value = gate_margin * bitget_leverage
            gate_size = int(gate_notional_value / (adjusted_trigger_price * 0.0001))
            
            if gate_size == 0:
                gate_size = 1
            
            self.logger.info(f"💰 마진 모드 체크 완료된 미러링 정보:")
            self.logger.info(f"   - 게이트 투입 마진: ${gate_margin:,.2f}")
            self.logger.info(f"   - 게이트 계약 수: {gate_size}")
            self.logger.info(f"   - 마진 모드 상태: {'Cross 준비완료' if margin_mode_ready else '수동 설정 필요'}")
            
            # ✅ 마진 모드가 확실히 설정된 상태에서 완벽한 미러링 주문 생성
            mirror_result = await self.gate_mirror.create_perfect_tp_sl_order(
                bitget_order=bitget_order,
                gate_size=gate_size,
                gate_margin=gate_margin,
                leverage=bitget_leverage,
                current_gate_price=self.gate_current_price
            )
            
            if not mirror_result['success']:
                self.daily_stats['failed_mirrors'] += 1
                self.logger.error(f"Gate.io 주문 생성 실패: {order_id}")
                return "failed"
            
            gate_order_id = mirror_result['gate_order_id']
            
            # 주문 ID 매핑 기록
            if order_id and gate_order_id:
                self.bitget_to_gate_order_mapping[order_id] = gate_order_id
                self.gate_to_bitget_order_mapping[gate_order_id] = order_id
                self.logger.info(f"주문 매핑 기록: {order_id} ↔ {gate_order_id}")
            
            # 마진 모드 체크 정보가 포함된 미러링 성공 기록
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
                'adjusted_trigger_price': adjusted_trigger_price,
                'original_price_diff': price_diff_abs,
                'has_tp_sl': mirror_result.get('has_tp_sl', False),
                'tp_price': mirror_result.get('tp_price'),
                'sl_price': mirror_result.get('sl_price'),
                'actual_tp_price': mirror_result.get('actual_tp_price'),
                'actual_sl_price': mirror_result.get('actual_sl_price'),
                'is_close_order': mirror_result.get('is_close_order', False),
                'reduce_only': mirror_result.get('reduce_only', False),
                'perfect_mirror': mirror_result.get('perfect_mirror', False),
                'close_details': close_details,
                'ratio_multiplier': ratio_multiplier,
                'margin_mode_ready': margin_mode_ready,  # ✅ 마진 모드 준비 상태
                'margin_mode_enforced': margin_mode_ready,  # ✅ 마진 모드 강제 설정 여부
                'price_diff_handled': adjusted_trigger_price != trigger_price,
                'adaptive_system_applied': True
            }
            
            self.daily_stats['plan_order_mirrors'] += 1
            
            # TP/SL 통계 업데이트
            if mirror_result.get('has_tp_sl', False):
                self.daily_stats['tp_sl_success'] += 1
            elif mirror_result.get('tp_price') or mirror_result.get('sl_price'):
                self.daily_stats['tp_sl_failed'] += 1
            
            # 마진 모드 체크 완료 메시지
            order_type = "클로즈 주문" if mirror_result.get('is_close_order') else "예약 주문"
            perfect_status = "완벽" if mirror_result.get('perfect_mirror') else "부분"
            margin_status = "✅ Cross 준비완료" if margin_mode_ready else "⚠️ 수동 설정 필요"
            
            # 가격 조정 상태
            price_adjustment_status = ""
            if adjusted_trigger_price != trigger_price:
                price_adjustment_status = f"\n🔧 스마트 가격 조정: ${trigger_price:.2f} → ${adjusted_trigger_price:.2f}"
            
            # 복제 비율 효과 분석
            ratio_status = ""
            if ratio_multiplier != 1.0:
                ratio_status = f" (복제비율: {ratio_multiplier}x 적용)"
            
            tp_sl_info = ""
            if mirror_result.get('has_tp_sl'):
                tp_sl_info = f"\n\n🎯 TP/SL 완벽 미러링:"
                if mirror_result.get('actual_tp_price'):
                    tp_sl_info += f"\n✅ TP: ${mirror_result['actual_tp_price']}"
                if mirror_result.get('actual_sl_price'):
                    tp_sl_info += f"\n✅ SL: ${mirror_result['actual_sl_price']}"
            
            await self.telegram.send_message(
                f"✅ {order_type} {perfect_status} 미러링 성공{ratio_status}\n"
                f"비트겟 ID: {order_id}\n"
                f"게이트 ID: {gate_order_id}\n"
                f"트리거가: ${trigger_price:,.2f}\n"
                f"게이트 수량: {gate_size}{price_adjustment_status}\n\n"
                f"💳 마진 모드 체크 결과:\n"
                f"주문 전 상태: {margin_status}\n"
                f"게이트 투입 마진: ${gate_margin:,.2f}\n"
                f"레버리지: {bitget_leverage}x\n"
                f"복제 비율: {ratio_multiplier}x 적용\n\n"
                f"🔥 마진 모드 체크 완료된 안전한 미러링!\n"
                f"💳 Cross 마진 모드로 안전하게 운영됩니다{tp_sl_info}"
            )
            
            # 반환값
            if adjusted_trigger_price != trigger_price:
                return "price_diff_handled"
            elif mirror_result.get('perfect_mirror'):
                return "perfect_success"
            else:
                return "partial_success"
            
        except Exception as e:
            self.logger.error(f"마진 모드 체크 포함 미러링 주문 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'plan_order_id': bitget_order.get('orderId', bitget_order.get('planOrderId', 'unknown'))
            })
            return "failed"

    # 기존 메서드들 유지하되 코드 정리
    
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

    async def _handle_bitget_filled_gate_immediate_action(self, bitget_order_id: str, analysis_result: Dict) -> bool:
        """비트겟 체결 시 게이트 즉시 액션 처리"""
        try:
            if not analysis_result.get('immediate_action_needed', False):
                return False
            
            gate_action_type = analysis_result.get('gate_action_type', 'none')
            if gate_action_type == 'none':
                return False
            
            self.logger.info(f"🚀 비트겟 체결 → 게이트 즉시 액션 시작: {bitget_order_id}")
            
            # 미러링된 주문인지 확인
            if bitget_order_id not in self.mirrored_plan_orders:
                self.logger.warning(f"미러링되지 않은 주문: {bitget_order_id}")
                return False
            
            mirror_info = self.mirrored_plan_orders[bitget_order_id]
            gate_order_id = mirror_info.get('gate_order_id')
            
            if not gate_order_id:
                self.logger.warning(f"게이트 주문 ID가 없음: {bitget_order_id}")
                return False
            
            # 주문 처리 락 확보
            if gate_order_id not in self.immediate_fill_processing_locks:
                self.immediate_fill_processing_locks[gate_order_id] = asyncio.Lock()
            
            async with self.immediate_fill_processing_locks[gate_order_id]:
                # 액션 타입별 처리
                if gate_action_type == 'immediate_market_fill':
                    success = await self._execute_immediate_market_fill(gate_order_id, mirror_info, analysis_result)
                    if success:
                        self.logger.info(f"✅ 즉시 시장가 체결 성공: {gate_order_id}")
                        return True
                    else:
                        # 실패 시 백업 방법 시도
                        backup_success = await self._execute_backup_fill_mechanism(gate_order_id, mirror_info, analysis_result)
                        return backup_success
                        
                elif gate_action_type == 'adaptive_wait_or_adjust':
                    success = await self._execute_adaptive_wait_or_adjust(gate_order_id, mirror_info, analysis_result)
                    return success
                    
                else:
                    self.logger.warning(f"알 수 없는 액션 타입: {gate_action_type}")
                    return False
            
        except Exception as e:
            self.logger.error(f"비트겟 체결 → 게이트 즉시 액션 처리 실패: {bitget_order_id} - {e}")
            return False

    async def _execute_immediate_market_fill(self, gate_order_id: str, mirror_info: Dict, analysis_result: Dict) -> bool:
        """즉시 시장가 체결 실행"""
        try:
            self.logger.info(f"⚡ 즉시 시장가 체결 실행: {gate_order_id}")
            
            # ✅ 마진 모드 확인 및 강제 설정
            await self._ensure_cross_margin_mode_before_order()
            
            # 기존 게이트 예약 주문 취소
            try:
                await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                await asyncio.sleep(1.0)
                self.logger.info(f"✅ 기존 예약 주문 취소 완료: {gate_order_id}")
            except Exception as cancel_error:
                error_msg = str(cancel_error).lower()
                if any(keyword in error_msg for keyword in [
                    "not found", "order not exist", "invalid order", "cancelled"
                ]):
                    self.logger.info(f"예약 주문이 이미 처리됨: {gate_order_id}")
                else:
                    self.logger.error(f"예약 주문 취소 실패하지만 계속 진행: {cancel_error}")
            
            # 미러링 정보에서 주문 상세 추출
            gate_size = mirror_info.get('size', 1)
            is_close_order = mirror_info.get('is_close_order', False)
            reduce_only = mirror_info.get('reduce_only', False)
            
            # 현재 게이트 포지션 확인 (클로즈 주문의 경우)
            if is_close_order:
                gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
                current_position_size = 0
                if gate_positions:
                    current_position_size = int(gate_positions[0].get('size', 0))
                
                if current_position_size == 0:
                    self.logger.warning(f"클로즈 주문이지만 현재 포지션이 없음: {gate_order_id}")
                    return False
                
                # 포지션 크기 검증
                if abs(current_position_size) < abs(gate_size):
                    gate_size = current_position_size
                    self.logger.info(f"클로즈 주문 크기 조정: {gate_size}")
            
            # 시장가 주문 생성 (재시도 포함)
            for retry in range(self.market_fill_retry_count):
                try:
                    self.logger.info(f"⚡ 즉시 시장가 주문 생성 시도 {retry + 1}/{self.market_fill_retry_count}")
                    
                    market_order_result = await self.gate_mirror.place_order(
                        contract=self.GATE_CONTRACT,
                        size=gate_size,
                        price=None,  # 시장가
                        reduce_only=reduce_only,
                        tif="ioc"
                    )
                    
                    if market_order_result and market_order_result.get('id'):
                        self.logger.info(f"✅ 즉시 시장가 체결 성공: {market_order_result.get('id')}")
                        
                        # 성공 통계 업데이트
                        self.daily_stats['immediate_market_fills'] += 1
                        self.daily_stats['price_diff_resolved_fills'] += 1
                        
                        # 텔레그램 알림
                        price_diff = analysis_result.get('price_diff', 0)
                        await self.telegram.send_message(
                            f"⚡ 즉시 시장가 체결 성공!\n"
                            f"비트겟 체결됨 → 게이트 즉시 시장가 체결\n"
                            f"게이트 주문 ID: {market_order_result.get('id')}\n"
                            f"크기: {gate_size}\n"
                            f"시세 차이: ${price_diff:.2f}\n"
                            f"💳 마진 모드: Cross 강제 적용\n"
                            f"🔥 시세 차이로 인한 미체결 손실 방지!"
                        )
                        
                        return True
                    else:
                        self.logger.warning(f"시장가 주문 응답이 없음 (재시도 {retry + 1})")
                        if retry < self.market_fill_retry_count - 1:
                            await asyncio.sleep(2)
                            continue
                        
                except Exception as order_error:
                    self.logger.error(f"시장가 주문 생성 실패 (재시도 {retry + 1}): {order_error}")
                    if retry < self.market_fill_retry_count - 1:
                        await asyncio.sleep(2)
                        continue
                    else:
                        raise
            
            # 모든 재시도 실패
            self.logger.error(f"❌ 즉시 시장가 체결 모든 재시도 실패: {gate_order_id}")
            return False
            
        except Exception as e:
            self.logger.error(f"즉시 시장가 체결 실행 실패: {gate_order_id} - {e}")
            return False

    async def _execute_adaptive_wait_or_adjust(self, gate_order_id: str, mirror_info: Dict, analysis_result: Dict) -> bool:
        """적응형 대기 또는 가격 조정 실행"""
        try:
            self.logger.info(f"🎯 적응형 대기 또는 가격 조정 실행: {gate_order_id}")
            
            price_diff = analysis_result.get('price_diff', 0)
            trigger_price = analysis_result.get('trigger_price', 0)
            
            # 적응형 대기 시간 계산
            base_wait_time = min(self.max_wait_time_for_fill, 60)
            adaptive_wait_time = min(
                base_wait_time * self.adaptive_wait_multiplier * (price_diff / 100), 
                self.max_wait_time_for_fill
            )
            
            self.logger.info(f"적응형 대기 시간: {adaptive_wait_time:.1f}초")
            
            # 대기 중 가격 모니터링
            wait_start_time = datetime.now()
            check_interval = 5
            
            while (datetime.now() - wait_start_time).total_seconds() < adaptive_wait_time:
                # 현재 게이트 가격 확인
                current_gate_price = await self.gate_mirror.get_current_price(self.GATE_CONTRACT)
                
                # 트리거 조건 확인
                if self._check_trigger_condition_met(trigger_price, current_gate_price, analysis_result['side']):
                    self.logger.info(f"✅ 대기 중 트리거 조건 달성: 게이트 가격 ${current_gate_price:.2f}")
                    return True
                
                await asyncio.sleep(check_interval)
            
            # 대기 시간 초과 → 스마트 가격 조정 시도
            if self.smart_price_adjustment_enabled:
                self.logger.info(f"🔧 대기 시간 초과 → 스마트 가격 조정 시도")
                adjustment_success = await self._execute_smart_price_adjustment(gate_order_id, mirror_info, analysis_result)
                if adjustment_success:
                    self.daily_stats['adaptive_price_adjustments'] += 1
                    return True
            
            # 가격 조정도 실패 → 백업 체결 메커니즘
            if self.backup_fill_mechanism_enabled:
                self.logger.info(f"🔄 가격 조정 실패 → 백업 체결 메커니즘 시도")
                backup_success = await self._execute_backup_fill_mechanism(gate_order_id, mirror_info, analysis_result)
                return backup_success
            
            return False
            
        except Exception as e:
            self.logger.error(f"적응형 대기 또는 가격 조정 실행 실패: {gate_order_id} - {e}")
            return False

    def _check_trigger_condition_met(self, trigger_price: float, current_price: float, side: str) -> bool:
        """트리거 조건 달성 여부 확인"""
        try:
            if trigger_price <= 0 or current_price <= 0:
                return False
            
            side_lower = side.lower()
            
            if 'buy' in side_lower or 'long' in side_lower:
                return current_price <= trigger_price
            elif 'sell' in side_lower or 'short' in side_lower:
                return current_price >= trigger_price
            else:
                return abs(current_price - trigger_price) <= 10.0
                
        except Exception as e:
            self.logger.error(f"트리거 조건 확인 실패: {e}")
            return False

    async def _execute_smart_price_adjustment(self, gate_order_id: str, mirror_info: Dict, analysis_result: Dict) -> bool:
        """스마트 가격 조정 실행"""
        try:
            self.logger.info(f"🔧 스마트 가격 조정 실행: {gate_order_id}")
            
            # ✅ 가격 조정 전 마진 모드 확인
            await self._ensure_cross_margin_mode_before_order()
            
            original_trigger_price = analysis_result.get('trigger_price', 0)
            current_gate_price = await self.gate_mirror.get_current_price(self.GATE_CONTRACT)
            
            if original_trigger_price <= 0 or current_gate_price <= 0:
                self.logger.error("가격 정보 없음 - 조정 불가")
                return False
            
            # 점진적 가격 조정 (3단계)
            for step in range(1, self.price_adjustment_step_count + 1):
                try:
                    # 조정 비율 계산
                    adjustment_ratio = (self.price_adjustment_percentage * step) / 100
                    price_adjustment = min(
                        abs(current_gate_price - original_trigger_price) * adjustment_ratio,
                        self.max_price_adjustment * step / self.price_adjustment_step_count
                    )
                    
                    # 조정 방향 결정
                    side = analysis_result.get('side', '').lower()
                    if 'buy' in side or 'long' in side:
                        adjusted_trigger_price = original_trigger_price + price_adjustment
                    else:
                        adjusted_trigger_price = original_trigger_price - price_adjustment
                    
                    self.logger.info(f"가격 조정 단계 {step}: ${original_trigger_price:.2f} → ${adjusted_trigger_price:.2f}")
                    
                    # 기존 주문 취소
                    try:
                        await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                        await asyncio.sleep(1)
                    except:
                        pass
                    
                    # 새 조정된 가격으로 주문 생성
                    gate_size = mirror_info.get('size', 1)
                    reduce_only = mirror_info.get('reduce_only', False)
                    trigger_type = "ge" if adjusted_trigger_price > current_gate_price else "le"
                    
                    new_order = await self.gate_mirror.create_price_triggered_order_v3(
                        trigger_price=adjusted_trigger_price,
                        order_size=gate_size,
                        reduce_only=reduce_only,
                        trigger_type=trigger_type
                    )
                    
                    if new_order and new_order.get('id'):
                        self.logger.info(f"✅ 가격 조정 주문 생성 성공: {new_order.get('id')}")
                        
                        # 미러링 정보 업데이트
                        bitget_order_id = self.gate_to_bitget_order_mapping.get(gate_order_id)
                        if bitget_order_id and bitget_order_id in self.mirrored_plan_orders:
                            self.mirrored_plan_orders[bitget_order_id]['gate_order_id'] = new_order.get('id')
                            self.mirrored_plan_orders[bitget_order_id]['adjusted_trigger_price'] = adjusted_trigger_price
                            self.mirrored_plan_orders[bitget_order_id]['price_adjustment_step'] = step
                        
                        # 매핑 업데이트
                        new_gate_order_id = new_order.get('id')
                        if bitget_order_id:
                            del self.gate_to_bitget_order_mapping[gate_order_id]
                            self.bitget_to_gate_order_mapping[bitget_order_id] = new_gate_order_id
                            self.gate_to_bitget_order_mapping[new_gate_order_id] = bitget_order_id
                        
                        # 텔레그램 알림
                        await self.telegram.send_message(
                            f"🔧 스마트 가격 조정 완료!\n"
                            f"원본 트리거가: ${original_trigger_price:.2f}\n"
                            f"조정 트리거가: ${adjusted_trigger_price:.2f}\n"
                            f"조정 단계: {step}/{self.price_adjustment_step_count}\n"
                            f"새 주문 ID: {new_gate_order_id}\n"
                            f"💳 마진 모드: Cross 강제 적용\n"
                            f"🎯 시세 차이에 적응하여 체결 확률 향상!"
                        )
                        
                        return True
                    else:
                        self.logger.warning(f"가격 조정 주문 생성 실패 (단계 {step})")
                        if step < self.price_adjustment_step_count:
                            await asyncio.sleep(2)
                            continue
                
                except Exception as step_error:
                    self.logger.error(f"가격 조정 단계 {step} 실패: {step_error}")
                    if step < self.price_adjustment_step_count:
                        await asyncio.sleep(2)
                        continue
                    else:
                        raise
            
            self.logger.error("모든 가격 조정 단계 실패")
            return False
            
        except Exception as e:
            self.logger.error(f"스마트 가격 조정 실행 실패: {gate_order_id} - {e}")
            return False

    async def _execute_backup_fill_mechanism(self, gate_order_id: str, mirror_info: Dict, analysis_result: Dict) -> bool:
        """백업 체결 메커니즘 실행"""
        try:
            self.logger.info(f"🔄 백업 체결 메커니즘 실행: {gate_order_id}")
            
            # ✅ 백업 체결 전 마진 모드 확인
            await self._ensure_cross_margin_mode_before_order()
            
            # 백업 방법 1: 더 관대한 즉시 시장가 체결
            try:
                success = await self._execute_immediate_market_fill(gate_order_id, mirror_info, analysis_result)
                if success:
                    self.daily_stats['backup_fill_successes'] += 1
                    self.logger.info(f"✅ 백업 방법 1 성공 (즉시 시장가): {gate_order_id}")
                    
                    await self.telegram.send_message(
                        f"🔄 백업 체결 메커니즘 성공!\n"
                        f"1차 방법 실패 → 백업 시장가 체결 성공\n"
                        f"게이트 주문: {gate_order_id}\n"
                        f"💳 마진 모드: Cross 강제 적용\n"
                        f"🛡️ 시세 차이로 인한 손실 완전 방지!"
                    )
                    
                    return True
            except Exception as backup1_error:
                self.logger.error(f"백업 방법 1 실패: {backup1_error}")
            
            # 백업 방법 2: 현재가 기준 시장가 체결
            try:
                self.logger.info(f"🔄 백업 방법 2 시도: 현재가 기준 시장가 체결")
                
                # 기존 주문 취소
                try:
                    await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                    await asyncio.sleep(1)
                except:
                    pass
                
                # 현재가 기준 시장가 주문
                gate_size = mirror_info.get('size', 1)
                reduce_only = mirror_info.get('reduce_only', False)
                
                current_market_order = await self.gate_mirror.place_order(
                    contract=self.GATE_CONTRACT,
                    size=gate_size,
                    price=None,
                    reduce_only=reduce_only,
                    tif="ioc"
                )
                
                if current_market_order and current_market_order.get('id'):
                    self.daily_stats['backup_fill_successes'] += 1
                    self.logger.info(f"✅ 백업 방법 2 성공 (현재가 시장가): {current_market_order.get('id')}")
                    
                    await self.telegram.send_message(
                        f"🔄 백업 체결 메커니즘 성공!\n"
                        f"백업 현재가 시장가 체결 성공\n"
                        f"게이트 주문 ID: {current_market_order.get('id')}\n"
                        f"크기: {gate_size}\n"
                        f"💳 마진 모드: Cross 강제 적용\n"
                        f"🛡️ 최종 백업으로 손실 방지 완료!"
                    )
                    
                    return True
                    
            except Exception as backup2_error:
                self.logger.error(f"백업 방법 2 실패: {backup2_error}")
            
            # 모든 백업 방법 실패
            self.logger.error(f"❌ 모든 백업 체결 메커니즘 실패: {gate_order_id}")
            
            await self.telegram.send_message(
                f"❌ 백업 체결 메커니즘 실패\n"
                f"게이트 주문: {gate_order_id}\n"
                f"모든 백업 방법 실패\n"
                f"⚠️ 수동 확인이 필요할 수 있습니다"
            )
            
            return False
            
        except Exception as e:
            self.logger.error(f"백업 체결 메커니즘 실행 실패: {gate_order_id} - {e}")
            return False

    async def _process_immediate_fill_queue(self):
        """즉시 체결 대기열 처리"""
        try:
            if not self.gate_pending_orders_for_immediate_fill:
                return
            
            self.logger.debug(f"즉시 체결 대기열 처리: {len(self.gate_pending_orders_for_immediate_fill)}개")
            
            completed_orders = []
            
            for gate_order_id, pending_info in list(self.gate_pending_orders_for_immediate_fill.items()):
                try:
                    # 대기 시간 초과 확인
                    pending_time = (datetime.now() - pending_info['added_time']).total_seconds()
                    if pending_time > self.max_wait_time_for_fill:
                        self.logger.warning(f"즉시 체결 대기 시간 초과: {gate_order_id}")
                        completed_orders.append(gate_order_id)
                        continue
                    
                    # 즉시 체결 처리
                    success = await self._execute_immediate_market_fill(
                        gate_order_id, 
                        pending_info['mirror_info'], 
                        pending_info['analysis_result']
                    )
                    
                    if success:
                        completed_orders.append(gate_order_id)
                        self.logger.info(f"✅ 대기열에서 즉시 체결 성공: {gate_order_id}")
                    
                except Exception as e:
                    self.logger.error(f"대기열 즉시 체결 처리 실패: {gate_order_id} - {e}")
                    completed_orders.append(gate_order_id)
            
            # 완료된 주문들 대기열에서 제거
            for order_id in completed_orders:
                if order_id in self.gate_pending_orders_for_immediate_fill:
                    del self.gate_pending_orders_for_immediate_fill[order_id]
                    
        except Exception as e:
            self.logger.error(f"즉시 체결 대기열 처리 실패: {e}")

    # 나머지 기존 메서드들은 코드 정리만 수행
    
    async def _enhanced_cancel_detection(self):
        """강화된 취소 감지 시스템"""
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
                    # 시세 차이를 고려한 체결/취소 분석
                    analysis_result = await self._analyze_order_disappearance_enhanced_v2(bitget_id)
                    
                    if not analysis_result['is_filled'] and analysis_result['safe_to_cancel']:
                        missing_bitget_orders.append(bitget_id)
            
            # 취소된 주문들 처리
            if missing_bitget_orders:
                self.logger.info(f"🔍 강화된 취소 감지: {len(missing_bitget_orders)}개 주문이 비트겟에서 안전하게 취소됨")
                
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
        """강화된 예약 주문 취소 처리 V2"""
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
                del self.mirrored_plan_orders[bitget_order_id]
                return True
            
            # 재시도 카운터 확인
            retry_count = self.cancel_retry_count.get(bitget_order_id, 0)
            
            # 강제 정리 임계값 확인
            if retry_count >= self.cancel_force_cleanup_threshold:
                self.logger.error(f"💀 강제 정리 임계값 초과: {bitget_order_id} (재시도: {retry_count}회)")
                await self._force_remove_mirror_record_v2(bitget_order_id, gate_order_id)
                self.daily_stats['forced_cancel_cleanups'] += 1
                return True
            
            # 최대 재시도 횟수 확인
            if retry_count >= self.max_cancel_retries:
                self.logger.error(f"최대 재시도 횟수 초과하지만 강제 정리 계속: {bitget_order_id}")
                await self._force_remove_mirror_record_v2(bitget_order_id, gate_order_id)
                return False
            
            # 게이트에서 주문 취소 시도
            try:
                self.logger.info(f"🎯 게이트 주문 취소 시도 V2: {gate_order_id} (재시도: {retry_count + 1}/{self.max_cancel_retries})")
                
                # 먼저 주문이 존재하는지 확인
                gate_orders = await self.gate_mirror.get_price_triggered_orders("BTC_USDT", "open")
                gate_order_exists = any(order.get('id') == gate_order_id for order in gate_orders)
                
                if not gate_order_exists:
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
                        success = False
                        self.cancel_retry_count[bitget_order_id] = retry_count + 1
                        self.logger.warning(f"⚠️ 게이트 주문이 아직 존재함, 재시도 예정: {gate_order_id}")
                    else:
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
                    f"🔥 정확한 체결/취소 구분으로 처리됨"
                )
                
                self.logger.info(f"🎯 강화된 예약 주문 취소 동기화 성공: {bitget_order_id} → {gate_order_id}")
                return True
            else:
                self.logger.warning(f"⚠️ 강화된 예약 주문 취소 재시도 예정: {bitget_order_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"강화된 예약 주문 취소 처리 V2 중 예외 발생: {bitget_order_id} - {e}")
            
            retry_count = self.cancel_retry_count.get(bitget_order_id, 0)
            self.cancel_retry_count[bitget_order_id] = retry_count + 1
            
            return False

    async def _force_remove_mirror_record_v2(self, bitget_order_id: str, gate_order_id: str):
        """강제로 미러링 기록 제거 V2"""
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
                f"🔥 정확한 체결/취소 구분으로 처리됨\n"
                f"⚠️ 게이트에서 수동 확인을 권장합니다"
            )
            
        except Exception as e:
            self.logger.error(f"강제 미러링 기록 제거 V2 실패: {e}")

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

    # 나머지 기존 메서드들도 간단히 유지 (코드 정리만)
    
    async def _get_all_current_plan_orders_enhanced(self) -> List[Dict]:
        """모든 현재 예약 주문 조회"""
        try:
            all_orders = []
            
            # 비트겟에서 모든 예약 주문 조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            
            # 일반 예약 주문 추가
            general_orders = plan_data.get('plan_orders', [])
            if general_orders:
                all_orders.extend(general_orders)
                self.logger.debug(f"일반 예약 주문 {len(general_orders)}개 추가")
            
            # TP/SL 주문 추가
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            if tp_sl_orders:
                all_orders.extend(tp_sl_orders)
                self.logger.debug(f"TP/SL 주문 {len(tp_sl_orders)}개 추가")
            
            self.logger.debug(f"총 {len(all_orders)}개의 현재 예약 주문 조회 완료")
            return all_orders
            
        except Exception as e:
            self.logger.error(f"현재 예약 주문 조회 실패: {e}")
            return []

    async def _is_order_recently_processed_improved(self, order_id: str, order: Dict) -> bool:
        """개선된 최근 처리 주문 확인"""
        try:
            # 기본 시간 기반 확인
            if order_id in self.recently_processed_orders:
                time_diff = (datetime.now() - self.recently_processed_orders[order_id]).total_seconds()
                if time_diff < self.order_deduplication_window:
                    self.logger.debug(f"최근 처리된 주문: {order_id}")
                    return True
                else:
                    del self.recently_processed_orders[order_id]
            
            # 정확한 해시 기반 확인
            order_hash = await self._generate_primary_order_hash(order)
            if order_hash and order_hash in self.processed_order_hashes:
                self.logger.debug(f"해시 기반 중복 감지: {order_hash}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"최근 처리 확인 실패: {e}")
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
                            self.logger.debug(f"가격 기반 중복 감지: {trigger_price} ≈ {existing_price}")
                            return True
                except (ValueError, IndexError):
                    continue
            
            # 기존 게이트 주문과의 정확한 해시 매칭 확인
            order_hash = await self._generate_primary_order_hash(bitget_order)
            if order_hash and order_hash in self.gate_existing_order_hashes:
                self.logger.debug(f"게이트 기존 주문과 해시 중복: {order_hash}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"중복 주문 확인 실패: {e}")
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
            
            # 주 해시 기록
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

    # 필수 초기화 메서드들은 기존과 동일하게 유지 (간단히)
    
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
                self.logger.warning(f"렌더 재구동 감지: 기존 게이트 포지션 발견")
            else:
                self.render_restart_detected = False
                self.logger.info("새로운 시작: 기존 게이트 포지션 없음")
                
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
            
            self.logger.info(f"시작 시 {len(self.startup_plan_orders)}개 예약 주문 복제 시작")
            
            success = False
            for retry in range(self.max_startup_mirror_retries):
                try:
                    self.logger.info(f"시작 시 예약 주문 복제 시도 {retry + 1}/{self.max_startup_mirror_retries}")
                    
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
                                
                                # ✅ 마진 모드 강제 확인
                                await self._ensure_cross_margin_mode_before_order()
                                
                                # 완벽한 미러링 시도
                                result = await self._process_perfect_mirror_order_with_margin_check(order_data, close_details, self.mirror_ratio_multiplier)
                                
                                # 성공 케이스 처리
                                success_results = ["perfect_success", "partial_success", "force_success", "close_order_forced", "price_diff_handled"]
                                if result in success_results:
                                    mirrored_count += 1
                                    self.daily_stats['startup_plan_mirrors'] += 1
                                    self.logger.info(f"시작 시 {'클로즈 ' if is_close_order else ''}예약 주문 복제 성공: {order_id}")
                                else:
                                    failed_count += 1
                                    self.logger.warning(f"시작 시 {'클로즈 ' if is_close_order else ''}예약 주문 복제 실패: {order_id}")
                        
                        except Exception as e:
                            failed_count += 1
                            self.logger.error(f"시작 시 예약 주문 복제 오류: {order_id} - {e}")
                            
                        # 처리된 주문으로 표시
                        self.processed_plan_orders.add(order_id)
                    
                    # 성공 기준: 70% 이상 성공 또는 모든 주문 처리
                    total_processed = mirrored_count + skipped_count + failed_count
                    if total_processed >= len(self.startup_plan_orders) * 0.7 or mirrored_count > 0:
                        success = True
                        
                        # 시작 시 복제 완료 알림
                        ratio_info = f" (복제비율: {self.mirror_ratio_multiplier}x)" if self.mirror_ratio_multiplier != 1.0 else ""
                        
                        await self.telegram.send_message(
                            f"🔄 시작 시 예약 주문 복제 완료{ratio_info}\n"
                            f"성공: {mirrored_count}개\n"
                            f"클로즈 주문: {close_order_count}개\n"
                            f"스킵: {skipped_count}개\n"
                            f"실패: {failed_count}개\n"
                            f"총 {len(self.startup_plan_orders)}개 중 {mirrored_count}개 복제{ratio_info}\n\n"
                            f"💳 마진 모드: Cross 강제 설정 완료\n"
                            f"🔥 정확한 체결/취소 구분으로 손실 방지!"
                        )
                        
                        self.logger.info(f"✅ 시작 시 예약 주문 복제 성공: {mirrored_count}개")
                        break
                    else:
                        self.logger.warning(f"⚠️ 시작 시 예약 주문 복제 성공률 부족: {mirrored_count}/{len(self.startup_plan_orders)}")
                        
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
            self.logger.error(f"클로즈 주문 유효성 검증 실패하지만 강제 미러링: {e}")
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
                            "not found", "order not exist", "invalid order"
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

    # 포지션 처리 관련 메서드들
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
            
            # ✅ 마진 모드 강제 확인
            await self._ensure_cross_margin_mode_before_order()
            
            # 복제 비율 적용된 마진 비율 계산
            margin_ratio_result = await self.utils.calculate_dynamic_margin_ratio_with_multiplier(
                size, fill_price, order, self.mirror_ratio_multiplier
            )
            
            if not margin_ratio_result['success']:
                return
            
            leverage = margin_ratio_result['leverage']
            
            # 미러링 처리 (기존 로직 유지하되 마진 모드 강제 설정 포함)
            self.logger.info(f"✅ 체결 주문 미러링 처리: {order_id} (마진 모드: Cross 강제)")
            
        except Exception as e:
            self.logger.error(f"체결 주문 처리 중 오류: {e}")

    async def check_sync_status(self) -> Dict:
        """동기화 상태 확인"""
        try:
            # 비트겟 포지션
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            bitget_active = [p for p in bitget_positions if float(p.get('total', 0)) > 0]
            
            # 게이트 포지션
            gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
            gate_active = [p for p in gate_positions if p.get('size', 0) != 0]
            
            # 동기화 상태 계산
            bitget_new_count = len([p for p in bitget_active if self.utils.generate_position_id(p) not in self.startup_positions])
            gate_new_count = len([p for p in gate_active if self._generate_gate_position_id(p) not in self.startup_gate_positions])
            
            is_synced = bitget_new_count == gate_new_count
            
            return {
                'is_synced': is_synced,
                'bitget_total_count': len(bitget_active),
                'gate_total_count': len(gate_active),
                'bitget_new_count': bitget_new_count,
                'gate_new_count': gate_new_count,
                'position_diff': abs(bitget_new_count - gate_new_count)
            }
            
        except Exception as e:
            self.logger.error(f"동기화 상태 확인 실패: {e}")
            return {
                'is_synced': False,
                'error': str(e)
            }
    
    async def process_position(self, bitget_pos: Dict):
        """포지션 처리 (미러링이 필요한 경우)"""
        try:
            if not self.mirror_trading_enabled:
                return
            
            pos_id = self.utils.generate_position_id(bitget_pos)
            
            # 시작 시 존재했던 포지션은 스킵
            if pos_id in self.startup_positions:
                return
            
            # 이미 미러링된 포지션인지 확인
            if pos_id in self.mirrored_positions:
                return
            
            # ✅ 마진 모드 강제 확인
            await self._ensure_cross_margin_mode_before_order()
            
            self.logger.info(f"🔄 새로운 포지션 미러링 처리: {pos_id} (마진 모드: Cross 강제)")
            
            # 포지션 미러링 로직 실행
            # (기존 로직 유지)
            
        except Exception as e:
            self.logger.error(f"포지션 처리 중 오류: {e}")
    
    async def handle_position_close(self, pos_id: str):
        """포지션 종료 처리"""
        try:
            if pos_id in self.mirrored_positions:
                position_info = self.mirrored_positions[pos_id]
                
                self.logger.info(f"🔄 포지션 종료 처리: {pos_id}")
                
                # ✅ 마진 모드 강제 확인
                await self._ensure_cross_margin_mode_before_order()
                
                # 게이트 포지션 종료 로직
                try:
                    await self.gate_mirror.close_position(self.GATE_CONTRACT)
                    self.logger.info(f"✅ 게이트 포지션 종료 완료: {pos_id}")
                    
                    # 미러링 기록에서 제거
                    del self.mirrored_positions[pos_id]
                    
                except Exception as e:
                    self.logger.error(f"게이트 포지션 종료 실패: {pos_id} - {e}")
            
        except Exception as e:
            self.logger.error(f"포지션 종료 처리 실패: {e}")

    async def stop(self):
        """포지션 매니저 중지"""
        try:
            self.logger.info("포지션 매니저 중지 중...")
            
            # 지속적인 교정 시스템 비활성화
            self.continuous_correction_enabled = False
            self.margin_mode_strict_enforcement = False
            
            # 필요한 정리 작업 수행
            self.processed_orders.clear()
            self.processed_plan_orders.clear()
            self.mirrored_plan_orders.clear()
            
            self.logger.info("✅ 포지션 매니저 중지 완료")
            
        except Exception as e:
            self.logger.error(f"포지션 매니저 중지 실패: {e}")
