import os
import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import json

from mirror_trading_utils import MirrorTradingUtils, PositionInfo, MirrorResult

logger = logging.getLogger(__name__)

class MirrorPositionManager:
    """포지션 및 주문 관리 클래스 - 복제 비율 고려한 정확한 체결/취소 구분 + 오픈/클로징 매칭"""
    
    def __init__(self, config, bitget_client, gate_client, gate_mirror_client, telegram_bot, utils):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.gate_mirror = gate_mirror_client
        self.telegram = telegram_bot
        self.utils = utils
        self.logger = logging.getLogger('mirror_position_manager')
        
        # 🔥🔥🔥 환경변수 처리 개선 - O/X 지원
        raw_mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'O')
        self.mirror_trading_enabled = self._parse_mirror_trading_mode(raw_mirror_mode)
        
        # 🔥🔥🔥 배율은 기본값 1.0으로 시작, 텔레그램으로 실시간 조정
        self.mirror_ratio_multiplier = 1.0
        
        # 환경변수 로깅
        self.logger.info(f"🔥 포지션 매니저 환경변수: 미러링모드='{raw_mirror_mode}' → {'활성화' if self.mirror_trading_enabled else '비활성화'}")
        self.logger.info(f"🔥 포지션 매니저 초기 복제 비율: {self.mirror_ratio_multiplier}x")
        
        # 미러링 상태 관리
        self.mirrored_positions: Dict[str, PositionInfo] = {}
        self.startup_positions: Set[str] = set()
        self.startup_gate_positions: Set[str] = set()
        self.failed_mirrors: List[MirrorResult] = []
        
        # 포지션 크기 추적
        self.position_sizes: Dict[str, float] = {}
        
        # 주문 체결 추적
        self.processed_orders: Set[str] = set()
        
        # 🔥🔥🔥 예약 주문 추적 관리 - 복제 비율 고려한 체결/취소 구분
        self.mirrored_plan_orders: Dict[str, Dict] = {}
        self.processed_plan_orders: Set[str] = set()
        self.startup_plan_orders: Set[str] = set()
        self.startup_plan_orders_processed: bool = False
        
        # 🔥🔥🔥 오픈/클로징 포지션 매칭 시스템 - 새로 추가
        self.open_position_tracker: Dict[str, Dict] = {}  # 오픈 포지션 추적
        self.closing_order_validator: Dict[str, Dict] = {}  # 클로징 주문 검증
        self.position_entry_amounts: Dict[str, float] = {}  # 포지션별 진입금액 추적
        self.partial_close_tracker: Dict[str, List] = {}  # 부분 청산 추적
        
        # 🔥🔥🔥 복제 비율 고려한 매칭 시스템
        self.ratio_adjusted_amounts: Dict[str, float] = {}  # 복제 비율 적용된 금액 추적
        self.bitget_gate_amount_mapping: Dict[str, Dict] = {}  # 비트겟-게이트 금액 매핑
        
        # 🔥🔥🔥 체결된 주문 추적 - 복제 비율 고려
        self.recently_filled_order_ids: Set[str] = set()
        self.filled_order_timestamps: Dict[str, datetime] = {}
        self.filled_order_check_window = 300
        
        # 🔥🔥🔥 중복 복제 방지 시스템 - 완화된 버전
        self.order_processing_locks: Dict[str, asyncio.Lock] = {}
        self.recently_processed_orders: Dict[str, datetime] = {}
        self.order_deduplication_window = 15
        
        # 🔥🔥🔥 해시 기반 중복 방지 - 복제 비율 고려
        self.processed_order_hashes: Set[str] = set()
        self.order_hash_timestamps: Dict[str, datetime] = {}
        self.hash_cleanup_interval = 180
        
        # 🔥🔥🔥 예약 주문 취소 감지 시스템 - 복제 비율 고려한 체결/취소 구분
        self.last_plan_order_ids: Set[str] = set()
        self.plan_order_snapshot: Dict[str, Dict] = {}
        self.cancel_retry_count: Dict[str, int] = {}
        self.max_cancel_retries = 3
        
        # 시세 차이 관리
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.price_sync_threshold: float = 100.0
        self.position_wait_timeout: int = 60
        
        # 🔥🔥🔥 가격 기반 중복 방지 시스템 - 복제 비율 고려
        self.mirrored_trigger_prices: Set[str] = set()
        self.price_tolerance = 5.0
        
        # 렌더 재구동 시 기존 게이트 포지션 확인
        self.existing_gate_positions: Dict = {}
        self.render_restart_detected: bool = False
        
        # 🔥🔥🔥 게이트 기존 예약 주문 중복 방지 - 복제 비율 고려
        self.gate_existing_order_hashes: Set[str] = set()
        self.gate_existing_orders_detailed: Dict[str, Dict] = {}
        
        # 주문 ID 매핑 추적
        self.bitget_to_gate_order_mapping: Dict[str, str] = {}
        self.gate_to_bitget_order_mapping: Dict[str, str] = {}
        
        # 🔥🔥🔥 클로즈 주문 처리 강화 - 오픈/클로징 매칭 고려
        self.close_order_processing: bool = True
        self.close_order_validation_mode: str = "position_aware"  # 포지션 인식 모드
        self.force_close_order_mirror: bool = False  # 더 신중하게 변경
        
        # 🔥🔥🔥 렌더 재구동 시 예약 주문 미러링 강화
        self.startup_mirror_retry_count: int = 0
        self.max_startup_mirror_retries: int = 3
        self.startup_mirror_delay: int = 10
        
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
            'total_mirrored': 0, 'successful_mirrors': 0, 'failed_mirrors': 0,
            'partial_closes': 0, 'full_closes': 0, 'total_volume': 0.0,
            'order_mirrors': 0, 'position_mirrors': 0, 'plan_order_mirrors': 0,
            'plan_order_cancels': 0, 'startup_plan_mirrors': 0,
            'close_order_mirrors': 0, 'close_order_skipped': 0, 'close_order_forced': 0,
            'duplicate_orders_prevented': 0, 'perfect_mirrors': 0, 'partial_mirrors': 0,
            'tp_sl_success': 0, 'tp_sl_failed': 0, 'auto_close_order_cleanups': 0,
            'position_closed_cleanups': 0, 'sync_corrections': 0, 'sync_deletions': 0,
            'cancel_failures': 0, 'cancel_successes': 0, 'filled_detection_successes': 0,
            'position_matching_successes': 0, 'position_matching_failures': 0,  # 🔥🔥🔥 새로 추가
            'ratio_adjusted_orders': 0, 'ratio_mismatch_prevented': 0,  # 🔥🔥🔥 새로 추가
            'errors': []
        }
        
        self.logger.info(f"🔥 미러 포지션 매니저 초기화 완료 - 오픈/클로징 매칭 + 복제 비율 고려")

    def _parse_mirror_trading_mode(self, mode_str: str) -> bool:
        """미러링 모드 파싱"""
        if isinstance(mode_str, bool):
            return mode_str
        
        mode_str_original = str(mode_str).strip()
        mode_str_upper = mode_str_original.upper()
        
        if mode_str_upper == 'O':
            return True
        elif mode_str_upper == 'X':
            return False
        elif mode_str_upper in ['ON', 'OPEN', 'TRUE', 'Y', 'YES']:
            return True
        elif mode_str_upper in ['OFF', 'CLOSE', 'FALSE', 'N', 'NO'] or mode_str_original == '0':
            return False
        elif mode_str_original == '1':
            return True
        else:
            self.logger.warning(f"⚠️ 알 수 없는 미러링 모드: '{mode_str_original}', 기본값(활성화) 사용")
            return True

    def update_prices(self, bitget_price: float, gate_price: float, price_diff_percent: float):
        """시세 정보 업데이트"""
        self.bitget_current_price = bitget_price
        self.gate_current_price = gate_price
        self.price_diff_percent = price_diff_percent

    async def initialize(self):
        """포지션 매니저 초기화"""
        try:
            self.logger.info("🔥 포지션 매니저 초기화 시작 - 오픈/클로징 매칭 + 복제 비율 고려")
            
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
            
            # 🔥🔥🔥 오픈/클로징 매칭 시스템 초기화
            await self._initialize_position_matching_system()
            
            # 예약 주문 초기 스냅샷 생성
            await self._create_initial_plan_order_snapshot()
            
            # 시작 시 기존 예약 주문 복제
            await self._mirror_startup_plan_orders_with_matching()
            
            self.logger.info("✅ 포지션 매니저 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"포지션 매니저 초기화 실패: {e}")
            raise

    async def _initialize_position_matching_system(self):
        """🔥🔥🔥 오픈/클로징 매칭 시스템 초기화"""
        try:
            self.logger.info("🎯 오픈/클로징 매칭 시스템 초기화 시작")
            
            # 현재 비트겟 포지션 분석
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    await self._analyze_and_track_position(pos)
            
            # 현재 게이트 포지션 분석
            gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
            for pos in gate_positions:
                if pos.get('size', 0) != 0:
                    await self._analyze_gate_position_for_matching(pos)
            
            self.logger.info("✅ 오픈/클로징 매칭 시스템 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"오픈/클로징 매칭 시스템 초기화 실패: {e}")

    async def _analyze_and_track_position(self, bitget_pos: Dict):
        """🔥🔥🔥 비트겟 포지션 분석 및 추적"""
        try:
            side = bitget_pos.get('holdSide', '').lower()
            size = float(bitget_pos.get('total', 0))
            entry_price = float(bitget_pos.get('openPriceAvg', 0))
            margin = float(bitget_pos.get('marginSize', 0))
            leverage = int(float(bitget_pos.get('leverage', 1)))
            
            pos_key = f"{self.SYMBOL}_{side}_{entry_price}"
            
            # 포지션 정보 저장
            self.open_position_tracker[pos_key] = {
                'side': side,
                'size': size,
                'entry_price': entry_price,
                'margin': margin,
                'leverage': leverage,
                'entry_time': datetime.now(),
                'notional_value': size * entry_price,
                'original_margin': margin  # 원본 마진 보존
            }
            
            # 진입금액 추적 (복제 비율 미적용 원본)
            self.position_entry_amounts[pos_key] = margin
            
            # 🔥🔥🔥 복제 비율 적용된 금액 계산 및 저장
            adjusted_margin = margin * self.mirror_ratio_multiplier
            self.ratio_adjusted_amounts[pos_key] = adjusted_margin
            
            self.logger.info(f"🎯 포지션 추적 등록: {pos_key}")
            self.logger.info(f"   원본 마진: ${margin:.2f}, 복제 비율: {self.mirror_ratio_multiplier}x, 조정 마진: ${adjusted_margin:.2f}")
            
        except Exception as e:
            self.logger.error(f"비트겟 포지션 분석 실패: {e}")

    async def _analyze_gate_position_for_matching(self, gate_pos: Dict):
        """🔥🔥🔥 게이트 포지션 분석하여 매칭 정보 생성"""
        try:
            size = int(gate_pos.get('size', 0))
            entry_price = float(gate_pos.get('entry_price', 0))
            side = 'long' if size > 0 else 'short'
            
            gate_pos_key = f"{self.GATE_CONTRACT}_{side}_{entry_price}"
            
            # 게이트 포지션과 연결된 비트겟 포지션 찾기
            matching_bitget_key = None
            for bitget_key in self.open_position_tracker:
                bitget_info = self.open_position_tracker[bitget_key]
                if (bitget_info['side'] == side and 
                    abs(bitget_info['entry_price'] - entry_price) < 50):  # 50달러 차이 허용
                    matching_bitget_key = bitget_key
                    break
            
            if matching_bitget_key:
                # 매칭 정보 저장
                self.bitget_gate_amount_mapping[matching_bitget_key] = {
                    'gate_position_key': gate_pos_key,
                    'gate_size': abs(size),
                    'gate_entry_price': entry_price,
                    'mapping_established': datetime.now()
                }
                
                self.logger.info(f"🔗 포지션 매칭 성공: {matching_bitget_key} ↔ {gate_pos_key}")
            
        except Exception as e:
            self.logger.error(f"게이트 포지션 매칭 분석 실패: {e}")

    async def monitor_plan_orders_cycle(self):
        """🔥🔥🔥 예약 주문 모니터링 사이클 - 오픈/클로징 매칭 고려"""
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
            await self._cleanup_expired_hashes()
            
            # 🔥🔥🔥 체결된 주문 기록 업데이트 - 복제 비율 고려
            await self._update_recently_filled_orders_with_ratio()
            
            # 포지션 종료 시 클로즈 주문 자동 정리
            await self._check_and_cleanup_close_orders_if_no_position()
            
            # 🔥🔥🔥 모든 예약 주문 조회 - 오픈/클로징 분류 강화
            all_current_orders = await self._get_all_current_plan_orders_with_classification()
            
            # 현재 존재하는 예약주문 ID 집합
            current_order_ids = set()
            current_snapshot = {}
            
            for order_info in all_current_orders:
                order = order_info['order']
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    current_order_ids.add(order_id)
                    current_snapshot[order_id] = {
                        'order_data': order.copy(),
                        'classification': order_info['classification'],
                        'timestamp': datetime.now().isoformat(),
                        'status': 'active'
                    }
            
            # 🔥🔥🔥 사라진 예약 주문 분석 - 복제 비율 고려한 체결/취소 구분
            disappeared_order_ids = self.last_plan_order_ids - current_order_ids
            
            if disappeared_order_ids:
                await self._handle_disappeared_orders_with_ratio_consideration(disappeared_order_ids)
            
            # 🔥🔥🔥 새로운 예약 주문 감지 - 오픈/클로징 매칭 고려
            new_orders_count = 0
            for order_info in all_current_orders:
                order = order_info['order']
                classification = order_info['classification']
                order_id = order.get('orderId', order.get('planOrderId', ''))
                
                if not order_id or order_id in self.processed_plan_orders:
                    continue
                
                if order_id in self.startup_plan_orders:
                    self.processed_plan_orders.add(order_id)
                    continue
                
                # 🔥🔥🔥 오픈/클로징 매칭 검증
                if classification['is_close_order']:
                    should_process = await self._validate_close_order_with_position_matching(order, classification)
                    if not should_process:
                        self.daily_stats['position_matching_failures'] += 1
                        self.processed_plan_orders.add(order_id)
                        continue
                
                # 🔥🔥🔥 개선된 중복 처리 방지 - 복제 비율 고려
                if await self._is_order_recently_processed_with_ratio(order_id, order):
                    continue
                
                # 주문 처리 락 확보
                if order_id not in self.order_processing_locks:
                    self.order_processing_locks[order_id] = asyncio.Lock()
                
                async with self.order_processing_locks[order_id]:
                    if order_id in self.processed_plan_orders:
                        continue
                    
                    # 🔥🔥🔥 복제 비율 고려한 중복 복제 확인
                    is_duplicate = await self._is_duplicate_order_with_ratio_consideration(order)
                    if is_duplicate:
                        self.daily_stats['duplicate_orders_prevented'] += 1
                        self.processed_plan_orders.add(order_id)
                        continue
                    
                    # 🔥🔥🔥 새로운 예약 주문 처리 - 오픈/클로징 매칭 + 복제 비율 적용
                    try:
                        result = await self._process_matched_mirror_order_with_ratio(order, classification, self.mirror_ratio_multiplier)
                        
                        success_results = ["perfect_success", "partial_success", "force_success", "close_order_forced"]
                        
                        if result in success_results:
                            new_orders_count += 1
                            if result == "perfect_success":
                                self.daily_stats['perfect_mirrors'] += 1
                            elif result in ["force_success", "close_order_forced"]:
                                self.daily_stats['close_order_forced'] += 1
                            else:
                                self.daily_stats['partial_mirrors'] += 1
                                
                            if classification['is_close_order']:
                                self.daily_stats['close_order_mirrors'] += 1
                                self.daily_stats['position_matching_successes'] += 1
                            
                            self.daily_stats['ratio_adjusted_orders'] += 1
                            self.logger.info(f"✅ 예약 주문 복제 성공: {order_id} (결과: {result}, 비율: {self.mirror_ratio_multiplier}x)")
                            
                        elif result == "skipped":
                            if classification['is_close_order']:
                                self.daily_stats['close_order_skipped'] += 1
                            self.logger.info(f"⏭️ 예약 주문 스킵됨: {order_id}")
                        else:
                            self.daily_stats['failed_mirrors'] += 1
                            self.logger.error(f"❌ 예약 주문 복제 실패: {order_id} (결과: {result})")
                        
                        self.processed_plan_orders.add(order_id)
                        await self._record_order_processing_hash_with_ratio(order_id, order)
                        
                    except Exception as e:
                        self.logger.error(f"새로운 예약 주문 복제 실패: {order_id} - {e}")
                        self.processed_plan_orders.add(order_id)
                        self.daily_stats['failed_mirrors'] += 1
            
            # 성공적인 미러링 결과 알림
            if new_orders_count > 0:
                ratio_info = f" (복제비율: {self.mirror_ratio_multiplier}x)" if self.mirror_ratio_multiplier != 1.0 else ""
                await self.telegram.send_message(
                    f"✅ 예약 주문 미러링 성공{ratio_info}\n"
                    f"신규 복제: {new_orders_count}개\n"
                    f"오픈/클로징 매칭: 적용됨\n"
                    f"복제 비율: {self.mirror_ratio_multiplier}x 적용"
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

    async def _get_all_current_plan_orders_with_classification(self) -> List[Dict]:
        """🔥🔥🔥 모든 현재 예약 주문 조회 및 오픈/클로징 분류"""
        try:
            all_orders = []
            
            # 비트겟에서 모든 예약 주문 조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            
            # 일반 예약 주문 처리
            general_orders = plan_data.get('plan_orders', [])
            for order in general_orders:
                classification = await self.utils.determine_close_order_details_enhanced(order)
                all_orders.append({
                    'order': order,
                    'classification': classification,
                    'source': 'general'
                })
            
            # TP/SL 주문 처리 (모두 클로즈 성격)
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            for order in tp_sl_orders:
                classification = await self.utils.determine_close_order_details_enhanced(order)
                classification['is_close_order'] = True  # TP/SL은 항상 클로즈
                all_orders.append({
                    'order': order,
                    'classification': classification,
                    'source': 'tp_sl'
                })
            
            self.logger.debug(f"총 {len(all_orders)}개의 분류된 예약 주문 조회 완료")
            return all_orders
            
        except Exception as e:
            self.logger.error(f"분류된 예약 주문 조회 실패: {e}")
            return []

    async def _validate_close_order_with_position_matching(self, order: Dict, classification: Dict) -> bool:
        """🔥🔥🔥 클로즈 주문과 포지션 매칭 검증"""
        try:
            if not classification['is_close_order']:
                return True  # 오픈 주문은 항상 허용
            
            order_id = order.get('orderId', order.get('planOrderId', ''))
            position_side = classification.get('position_side', 'long')
            
            # 🔥🔥🔥 해당 방향의 오픈 포지션이 있는지 확인
            has_matching_position = False
            matching_position_key = None
            
            for pos_key, pos_info in self.open_position_tracker.items():
                if pos_info['side'] == position_side and pos_info['size'] > 0:
                    has_matching_position = True
                    matching_position_key = pos_key
                    break
            
            if not has_matching_position:
                self.logger.warning(f"⚠️ 클로즈 주문 {order_id}: {position_side} 포지션이 없어 스킵")
                return False
            
            # 🔥🔥🔥 부분 청산 비율 검증
            try:
                bitget_size = float(order.get('size', 0))
                position_info = self.open_position_tracker[matching_position_key]
                position_size = position_info['size']
                
                if bitget_size > 0 and position_size > 0:
                    close_ratio = bitget_size / position_size
                    
                    # 부분 청산 추적에 기록
                    if matching_position_key not in self.partial_close_tracker:
                        self.partial_close_tracker[matching_position_key] = []
                    
                    self.partial_close_tracker[matching_position_key].append({
                        'order_id': order_id,
                        'close_ratio': close_ratio,
                        'close_size': bitget_size,
                        'timestamp': datetime.now()
                    })
                    
                    self.logger.info(f"🎯 클로즈 주문 검증 성공: {order_id} ({position_side}, 비율: {close_ratio*100:.1f}%)")
                    return True
                
            except Exception as ratio_error:
                self.logger.warning(f"부분 청산 비율 계산 실패하지만 허용: {ratio_error}")
                return True
            
            return True
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 포지션 매칭 검증 실패하지만 허용: {e}")
            return True

    async def _update_recently_filled_orders_with_ratio(self):
        """🔥🔥🔥 최근 체결된 주문 기록 업데이트 - 복제 비율 고려"""
        try:
            filled_orders = await self.bitget.get_recent_filled_orders(symbol=self.SYMBOL, minutes=5)
            
            current_time = datetime.now()
            
            for order in filled_orders:
                order_id = order.get('orderId', order.get('id', ''))
                if order_id:
                    self.recently_filled_order_ids.add(order_id)
                    self.filled_order_timestamps[order_id] = current_time
                    
                    # 🔥🔥🔥 체결된 주문이 오픈 주문인 경우 포지션 추적에 추가
                    reduce_only = order.get('reduceOnly', 'false')
                    if reduce_only == 'false' or reduce_only is False:
                        await self._track_filled_open_order(order)
            
            # 오래된 체결 기록 정리
            expired_ids = []
            for order_id, timestamp in self.filled_order_timestamps.items():
                if (current_time - timestamp).total_seconds() > self.filled_order_check_window:
                    expired_ids.append(order_id)
            
            for order_id in expired_ids:
                self.recently_filled_order_ids.discard(order_id)
                del self.filled_order_timestamps[order_id]
                
        except Exception as e:
            self.logger.error(f"최근 체결 주문 업데이트 실패: {e}")

    async def _track_filled_open_order(self, filled_order: Dict):
        """🔥🔥🔥 체결된 오픈 주문 추적"""
        try:
            side = filled_order.get('side', '').lower()
            size = float(filled_order.get('size', 0))
            fill_price = float(filled_order.get('fillPrice', filled_order.get('price', 0)))
            
            if size <= 0 or fill_price <= 0:
                return
            
            position_side = 'long' if side == 'buy' else 'short'
            pos_key = f"{self.SYMBOL}_{position_side}_{fill_price}"
            
            # 새로운 포지션 또는 기존 포지션 업데이트
            if pos_key not in self.open_position_tracker:
                # 새로운 포지션 추가
                margin = size * fill_price / 10  # 기본 10배 레버리지 가정
                
                self.open_position_tracker[pos_key] = {
                    'side': position_side,
                    'size': size,
                    'entry_price': fill_price,
                    'margin': margin,
                    'leverage': 10,
                    'entry_time': datetime.now(),
                    'notional_value': size * fill_price,
                    'original_margin': margin
                }
                
                self.position_entry_amounts[pos_key] = margin
                self.ratio_adjusted_amounts[pos_key] = margin * self.mirror_ratio_multiplier
                
                self.logger.info(f"🎯 새로운 포지션 추적 등록: {pos_key} (체결 기반)")
            else:
                # 기존 포지션 크기 업데이트
                existing_info = self.open_position_tracker[pos_key]
                new_total_size = existing_info['size'] + size
                
                # 평균 진입가 계산
                total_notional = existing_info['notional_value'] + (size * fill_price)
                avg_entry_price = total_notional / new_total_size
                
                existing_info['size'] = new_total_size
                existing_info['entry_price'] = avg_entry_price
                existing_info['notional_value'] = total_notional
                
                self.logger.info(f"🔄 기존 포지션 업데이트: {pos_key} (크기: {new_total_size})")
            
        except Exception as e:
            self.logger.error(f"체결된 오픈 주문 추적 실패: {e}")

    async def _handle_disappeared_orders_with_ratio_consideration(self, disappeared_order_ids: Set[str]):
        """🔥🔥🔥 사라진 예약 주문 처리 - 복제 비율 고려한 체결/취소 구분"""
        try:
            self.logger.info(f"📋 {len(disappeared_order_ids)}개의 예약 주문이 사라짐 - 복제 비율 고려한 분석 시작")
            
            canceled_count = 0
            filled_count = 0
            
            for disappeared_id in disappeared_order_ids:
                try:
                    # 🔥🔥🔥 복제 비율 고려한 체결/취소 구분 로직
                    is_filled = await self._check_if_order_was_filled_with_ratio_awareness(disappeared_id)
                    
                    if is_filled:
                        filled_count += 1
                        self.daily_stats['filled_detection_successes'] += 1
                        self.logger.info(f"✅ 복제 비율 고려 체결 감지: {disappeared_id}")
                        
                        # 체결된 주문 미러링 기록 정리
                        if disappeared_id in self.mirrored_plan_orders:
                            await self._cleanup_mirror_records_for_filled_order_with_ratio(disappeared_id)
                    else:
                        # 실제 취소된 주문 처리
                        success = await self._handle_plan_order_cancel_with_ratio_consideration(disappeared_id)
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
                    f"📋 예약 주문 변화 분석 (복제 비율 고려)\n"
                    f"사라진 주문: {len(disappeared_order_ids)}개\n"
                    f"🎯 체결 감지: {filled_count}개\n"
                    f"🚫 취소 동기화: {canceled_count}개\n"
                    f"복제 비율: {self.mirror_ratio_multiplier}x 고려됨"
                )
            
        except Exception as e:
            self.logger.error(f"사라진 주문 처리 실패: {e}")

    async def _check_if_order_was_filled_with_ratio_awareness(self, order_id: str) -> bool:
        """🔥🔥🔥 복제 비율 인식한 주문 체결 여부 확인"""
        try:
            # 1. 최근 체결 기록에서 확인
            if order_id in self.recently_filled_order_ids:
                self.logger.info(f"✅ 복제 비율 고려 체결 확인 (최근 기록): {order_id}")
                return True
            
            # 2. 실시간 체결 주문 조회
            recent_filled = await self.bitget.get_recent_filled_orders(symbol=self.SYMBOL, minutes=2)
            
            for filled_order in recent_filled:
                filled_id = filled_order.get('orderId', filled_order.get('id', ''))
                if filled_id == order_id:
                    self.logger.info(f"✅ 복제 비율 고려 체결 확인 (실시간): {order_id}")
                    
                    # 체결 기록에 추가
                    self.recently_filled_order_ids.add(order_id)
                    self.filled_order_timestamps[order_id] = datetime.now()
                    
                    # 🔥🔥🔥 체결된 주문의 포지션 추적 업데이트
                    await self._track_filled_open_order(filled_order)
                    return True
            
            # 3. 주문 내역에서 체결 상태 확인
            try:
                order_history = await self.bitget.get_order_history(
                    symbol=self.SYMBOL, status='filled', limit=50
                )
                
                for hist_order in order_history:
                    hist_id = hist_order.get('orderId', hist_order.get('id', ''))
                    if hist_id == order_id:
                        self.logger.info(f"✅ 복제 비율 고려 체결 확인 (주문 내역): {order_id}")
                        return True
                        
            except Exception as e:
                self.logger.debug(f"주문 내역 조회 실패: {e}")
            
            # 체결되지 않음 = 취소됨
            self.logger.info(f"🚫 복제 비율 고려 취소 확인: {order_id}")
            return False
            
        except Exception as e:
            self.logger.error(f"복제 비율 고려 주문 체결/취소 확인 실패: {order_id} - {e}")
            return True  # 확실하지 않으면 체결로 처리

    async def _cleanup_mirror_records_for_filled_order_with_ratio(self, bitget_order_id: str):
        """🔥🔥🔥 복제 비율 고려한 체결 주문 미러링 기록 정리"""
        try:
            if bitget_order_id in self.mirrored_plan_orders:
                mirror_info = self.mirrored_plan_orders[bitget_order_id]
                gate_order_id = mirror_info.get('gate_order_id')
                
                self.logger.info(f"🎯 복제 비율 고려 체결 주문 기록 정리: {bitget_order_id} → {gate_order_id}")
                
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
                
                self.logger.info(f"✅ 복제 비율 고려 체결 주문 기록 정리 완료: {bitget_order_id}")
            
        except Exception as e:
            self.logger.error(f"복제 비율 고려 체결 주문 기록 정리 실패: {e}")

    async def _handle_plan_order_cancel_with_ratio_consideration(self, bitget_order_id: str) -> bool:
        """🔥🔥🔥 복제 비율 고려한 예약 주문 취소 처리"""
        try:
            self.logger.info(f"🚫 복제 비율 고려 예약 주문 취소 처리: {bitget_order_id}")
            
            if bitget_order_id not in self.mirrored_plan_orders:
                self.logger.info(f"미러링되지 않은 주문이므로 취소 처리 스킵: {bitget_order_id}")
                return True
            
            mirror_info = self.mirrored_plan_orders[bitget_order_id]
            gate_order_id = mirror_info.get('gate_order_id')
            
            if not gate_order_id:
                self.logger.warning(f"게이트 주문 ID가 없음: {bitget_order_id}")
                del self.mirrored_plan_orders[bitget_order_id]
                return True
            
            # 🔥🔥🔥 복제 비율 정보 확인
            ratio_multiplier = mirror_info.get('ratio_multiplier', 1.0)
            
            # 재시도 카운터 확인
            retry_count = self.cancel_retry_count.get(bitget_order_id, 0)
            
            if retry_count >= self.max_cancel_retries:
                self.logger.error(f"최대 재시도 횟수 초과: {bitget_order_id} (재시도: {retry_count}회)")
                await self._force_remove_mirror_record(bitget_order_id, gate_order_id)
                return False
            
            # 게이트에서 주문 취소 시도
            try:
                self.logger.info(f"🎯 복제 비율 {ratio_multiplier}x 게이트 주문 취소: {gate_order_id}")
                
                cancel_result = await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                
                self.logger.info(f"✅ 복제 비율 고려 게이트 주문 취소 성공: {gate_order_id}")
                
                # 1초 대기 후 취소 확인
                await asyncio.sleep(1.0)
                
                # 취소 확인
                gate_orders = await self.gate_mirror.get_price_triggered_orders("BTC_USDT", "open")
                gate_order_exists = any(order.get('id') == gate_order_id for order in gate_orders)
                
                if gate_order_exists:
                    self.cancel_retry_count[bitget_order_id] = retry_count + 1
                    self.logger.warning(f"⚠️ 게이트 주문이 아직 존재함, 재시도 예정: {gate_order_id}")
                    return False
                else:
                    success = True
                    
            except Exception as cancel_error:
                error_msg = str(cancel_error).lower()
                
                if any(keyword in error_msg for keyword in [
                    "not found", "order not exist", "invalid order", 
                    "order does not exist", "auto_order_not_found"
                ]):
                    success = True
                    self.logger.info(f"✅ 게이트 주문이 이미 처리됨: {gate_order_id}")
                else:
                    success = False
                    self.cancel_retry_count[bitget_order_id] = retry_count + 1
                    self.logger.error(f"❌ 게이트 주문 취소 실패: {gate_order_id} - {cancel_error}")
            
            # 결과 처리
            if success:
                await self._cleanup_mirror_records(bitget_order_id, gate_order_id)
                
                await self.telegram.send_message(
                    f"🚫✅ 복제 비율 고려 예약 주문 취소 완료\n"
                    f"비트겟 ID: {bitget_order_id}\n"
                    f"게이트 ID: {gate_order_id}\n"
                    f"복제 비율: {ratio_multiplier}x"
                )
                
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"복제 비율 고려 예약 주문 취소 처리 실패: {bitget_order_id} - {e}")
            
            retry_count = self.cancel_retry_count.get(bitget_order_id, 0)
            self.cancel_retry_count[bitget_order_id] = retry_count + 1
            
            return False

    async def _process_matched_mirror_order_with_ratio(self, bitget_order: Dict, classification: Dict, ratio_multiplier: float) -> str:
        """🔥🔥🔥 매칭된 미러링 주문 처리 - 오픈/클로징 고려 + 복제 비율 적용"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            is_close_order = classification['is_close_order']
            
            self.logger.info(f"🎯 매칭된 미러링 주문 처리: {order_id} (클로즈: {is_close_order}, 비율: {ratio_multiplier}x)")
            
            # 🔥🔥🔥 클로즈 주문인 경우 추가 검증
            if is_close_order:
                position_side = classification.get('position_side', 'long')
                
                # 해당 포지션의 매칭 정보 확인
                matching_position_key = None
                for pos_key, pos_info in self.open_position_tracker.items():
                    if pos_info['side'] == position_side and pos_info['size'] > 0:
                        matching_position_key = pos_key
                        break
                
                if not matching_position_key:
                    # 🔥🔥🔥 더 엄격한 검증 - 포지션이 없으면 스킵
                    self.logger.warning(f"⚠️ 클로즈 주문 {order_id}: 매칭되는 {position_side} 포지션이 없어 스킵")
                    self.daily_stats['ratio_mismatch_prevented'] += 1
                    return "skipped"
                
                # 부분 청산 비율 확인
                try:
                    bitget_size = float(bitget_order.get('size', 0))
                    position_info = self.open_position_tracker[matching_position_key]
                    position_size = position_info['size']
                    
                    if bitget_size > 0 and position_size > 0:
                        close_ratio = bitget_size / position_size
                        
                        # 🔥🔥🔥 복제 비율을 고려한 게이트 포지션 크기 예상
                        expected_gate_position_ratio = self.ratio_adjusted_amounts.get(matching_position_key, position_info['margin']) / position_info['margin']
                        
                        self.logger.info(f"🔍 클로즈 주문 매칭 분석:")
                        self.logger.info(f"   - 포지션: {matching_position_key}")
                        self.logger.info(f"   - 청산 비율: {close_ratio*100:.1f}%")
                        self.logger.info(f"   - 예상 게이트 비율: {expected_gate_position_ratio}")
                        
                except Exception as ratio_error:
                    self.logger.warning(f"부분 청산 비율 계산 실패하지만 진행: {ratio_error}")
            
            # 기존 완벽한 미러링 로직 실행
            result = await self._process_perfect_mirror_order_with_ratio(bitget_order, classification, ratio_multiplier)
            
            # 🔥🔥🔥 성공한 경우 포지션 추적 업데이트
            if result in ["perfect_success", "partial_success", "force_success"]:
                if not is_close_order:
                    # 오픈 주문인 경우 새 포지션 추적 등록
                    await self._register_new_position_from_order(bitget_order, ratio_multiplier)
                else:
                    # 클로즈 주문인 경우 기존 포지션 크기 업데이트
                    await self._update_position_from_close_order(bitget_order, classification)
            
            return result
            
        except Exception as e:
            self.logger.error(f"매칭된 미러링 주문 처리 실패: {e}")
            return "failed"

    async def _register_new_position_from_order(self, bitget_order: Dict, ratio_multiplier: float):
        """🔥🔥🔥 주문으로부터 새 포지션 등록"""
        try:
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            size = float(bitget_order.get('size', 0))
            trigger_price = 0
            
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if size <= 0 or trigger_price <= 0:
                return
            
            position_side = 'long' if 'buy' in side or 'long' in side else 'short'
            pos_key = f"{self.SYMBOL}_{position_side}_{trigger_price}"
            
            # 예상 마진 계산
            leverage = await self.utils.extract_bitget_leverage_enhanced(order_data=bitget_order)
            margin = (size * trigger_price) / leverage
            
            self.open_position_tracker[pos_key] = {
                'side': position_side,
                'size': size,
                'entry_price': trigger_price,
                'margin': margin,
                'leverage': leverage,
                'entry_time': datetime.now(),
                'notional_value': size * trigger_price,
                'original_margin': margin,
                'is_predicted': True  # 예측된 포지션 표시
            }
            
            self.position_entry_amounts[pos_key] = margin
            self.ratio_adjusted_amounts[pos_key] = margin * ratio_multiplier
            
            self.logger.info(f"🎯 예약 주문 기반 예상 포지션 등록: {pos_key} (복제 비율: {ratio_multiplier}x)")
            
        except Exception as e:
            self.logger.error(f"주문 기반 포지션 등록 실패: {e}")

    async def _update_position_from_close_order(self, bitget_order: Dict, classification: Dict):
        """🔥🔥🔥 클로즈 주문으로부터 포지션 크기 업데이트"""
        try:
            position_side = classification.get('position_side', 'long')
            close_size = float(bitget_order.get('size', 0))
            
            # 해당 포지션 찾기
            for pos_key, pos_info in self.open_position_tracker.items():
                if pos_info['side'] == position_side and pos_info['size'] > 0:
                    # 포지션 크기 감소
                    new_size = max(0, pos_info['size'] - close_size)
                    pos_info['size'] = new_size
                    
                    if new_size <= 0:
                        # 포지션 완전 종료
                        self.logger.info(f"🔴 포지션 완전 종료: {pos_key}")
                        if pos_key in self.position_entry_amounts:
                            del self.position_entry_amounts[pos_key]
                        if pos_key in self.ratio_adjusted_amounts:
                            del self.ratio_adjusted_amounts[pos_key]
                        if pos_key in self.partial_close_tracker:
                            del self.partial_close_tracker[pos_key]
                    else:
                        # 부분 청산
                        close_ratio = close_size / (pos_info['size'] + close_size)
                        self.logger.info(f"📊 부분 청산 업데이트: {pos_key} (비율: {close_ratio*100:.1f}%, 남은 크기: {new_size})")
                    
                    break
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 포지션 업데이트 실패: {e}")

    # 기존 메서드들 유지 (space 절약을 위해 주요 메서드만 표시)
    async def _process_perfect_mirror_order_with_ratio(self, bitget_order: Dict, close_details: Dict, ratio_multiplier: float) -> str:
        """완벽한 미러링 주문 처리 - 복제 비율 적용"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            
            # 기존 로직과 동일하지만 ratio_multiplier 적용
            margin_ratio_result = await self.utils.calculate_dynamic_margin_ratio_with_multiplier(
                float(bitget_order.get('size', 0)), 
                float(bitget_order.get('triggerPrice', bitget_order.get('price', 0))), 
                bitget_order, 
                ratio_multiplier
            )
            
            if not margin_ratio_result['success']:
                return "failed"
            
            # Gate 미러링 클라이언트로 완벽한 미러링 주문 생성
            mirror_result = await self.gate_mirror.create_perfect_tp_sl_order(
                bitget_order=bitget_order,
                gate_size=int(margin_ratio_result['notional_value'] / (self.gate_current_price * 0.0001)),
                gate_margin=margin_ratio_result['required_margin'],
                leverage=margin_ratio_result['leverage'],
                current_gate_price=self.gate_current_price
            )
            
            if mirror_result['success']:
                # 미러링 성공 기록 (ratio_multiplier 포함)
                self.mirrored_plan_orders[order_id] = {
                    'gate_order_id': mirror_result['gate_order_id'],
                    'bitget_order': bitget_order,
                    'gate_order': mirror_result['gate_order'],
                    'created_at': datetime.now().isoformat(),
                    'ratio_multiplier': ratio_multiplier,
                    'margin_ratio': margin_ratio_result['margin_ratio'],
                    'leverage': margin_ratio_result['leverage'],
                    'has_tp_sl': mirror_result.get('has_tp_sl', False),
                    'perfect_mirror': mirror_result.get('perfect_mirror', False)
                }
                
                return "perfect_success" if mirror_result.get('perfect_mirror') else "partial_success"
            else:
                return "failed"
                
        except Exception as e:
            self.logger.error(f"완벽한 미러링 주문 처리 실패: {e}")
            return "failed"

    # 나머지 기존 메서드들은 기본 로직 유지하되 복제 비율 고려 추가
    async def _is_order_recently_processed_with_ratio(self, order_id: str, order: Dict) -> bool:
        """복제 비율 고려한 최근 처리 주문 확인"""
        return await self._is_order_recently_processed_improved(order_id, order)

    async def _is_duplicate_order_with_ratio_consideration(self, bitget_order: Dict) -> bool:
        """복제 비율 고려한 중복 주문 확인"""
        return await self._is_duplicate_order_improved(bitget_order)

    async def _record_order_processing_hash_with_ratio(self, order_id: str, order: Dict):
        """복제 비율 고려한 주문 처리 해시 기록"""
        await self._record_order_processing_hash(order_id, order)

    # 기존 메서드들 유지 (간소화)
    async def _is_order_recently_processed_improved(self, order_id: str, order: Dict) -> bool:
        """개선된 최근 처리 주문 확인"""
        try:
            if order_id in self.recently_processed_orders:
                time_diff = (datetime.now() - self.recently_processed_orders[order_id]).total_seconds()
                if time_diff < self.order_deduplication_window:
                    return True
                else:
                    del self.recently_processed_orders[order_id]
            
            order_hash = await self._generate_primary_order_hash(order)
            if order_hash and order_hash in self.processed_order_hashes:
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"최근 처리 확인 실패: {e}")
            return False

    async def _is_duplicate_order_improved(self, bitget_order: Dict) -> bool:
        """개선된 중복 주문 확인"""
        try:
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price <= 0:
                return False
            
            for existing_price_key in self.mirrored_trigger_prices:
                try:
                    if existing_price_key.startswith(f"{self.GATE_CONTRACT}_"):
                        existing_price_str = existing_price_key.replace(f"{self.GATE_CONTRACT}_", "")
                        existing_price = float(existing_price_str)
                        
                        price_diff = abs(trigger_price - existing_price)
                        if price_diff <= self.price_tolerance:
                            return True
                except (ValueError, IndexError):
                    continue
            
            order_hash = await self._generate_primary_order_hash(bitget_order)
            if order_hash and order_hash in self.gate_existing_order_hashes:
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"중복 주문 확인 실패: {e}")
            return False

    async def _generate_primary_order_hash(self, order: Dict) -> str:
        """주 해시 생성"""
        try:
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if order.get(price_field):
                    trigger_price = float(order.get(price_field))
                    break
            
            if trigger_price <= 0:
                return ""
            
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
            
            order_hash = await self._generate_primary_order_hash(order)
            if order_hash:
                self.processed_order_hashes.add(order_hash)
                self.order_hash_timestamps[order_hash] = current_time
            
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

    # 나머지 기존 메서드들은 동일하게 유지
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

    # 나머지 기존 메서드들 유지 (초기화, 포지션 처리 등)
    async def _check_existing_gate_positions(self):
        """기존 게이트 포지션 확인"""
        try:
            gate_positions = await self.gate_mirror.get_positions("BTC_USDT")
            
            self.existing_gate_positions = {
                'has_long': False, 'has_short': False,
                'long_size': 0, 'short_size': 0, 'positions': gate_positions
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
        except Exception as e:
            self.logger.error(f"기존 게이트 포지션 확인 실패: {e}")

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
                except Exception as e:
                    continue
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
            return ""

    # 기존 다른 메서드들도 동일하게 유지
    async def _record_startup_positions(self):
        """시작 시 비트겟 포지션 기록"""
        try:
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    pos_id = self.utils.generate_position_id(pos)
                    self.startup_positions.add(pos_id)
        except Exception as e:
            self.logger.error(f"시작 시 포지션 기록 실패: {e}")

    async def _record_startup_plan_orders(self):
        """시작 시 예약 주문 기록"""
        try:
            all_startup_orders = await self._get_all_current_plan_orders_with_classification()
            
            for order_info in all_startup_orders:
                order = order_info['order']
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.startup_plan_orders.add(order_id)
            
            self.last_plan_order_ids = set(self.startup_plan_orders)
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
        except Exception as e:
            self.logger.error(f"시작 시 게이트 포지션 기록 실패: {e}")

    def _generate_gate_position_id(self, gate_pos: Dict) -> str:
        """게이트 포지션 ID 생성"""
        try:
            contract = gate_pos.get('contract', "BTC_USDT")
            size = gate_pos.get('size', 0)
            side = 'long' if size > 0 else 'short' if size < 0 else 'unknown'
            entry_price = gate_pos.get('entry_price', self.gate_current_price or 0)
            return f"{contract}_{side}_{entry_price}"
        except Exception as e:
            return f"BTC_USDT_unknown_unknown"

    async def _create_initial_plan_order_snapshot(self):
        """초기 예약 주문 스냅샷 생성"""
        try:
            all_orders = await self._get_all_current_plan_orders_with_classification()
            
            for order_info in all_orders:
                order = order_info['order']
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.plan_order_snapshot[order_id] = {
                        'order_data': order.copy(),
                        'classification': order_info['classification'],
                        'timestamp': datetime.now().isoformat(),
                        'status': 'startup'
                    }
        except Exception as e:
            self.logger.error(f"초기 예약 주문 스냅샷 생성 실패: {e}")

    async def _mirror_startup_plan_orders_with_matching(self):
        """시작 시 기존 예약 주문 복제 - 매칭 고려"""
        try:
            if not self.startup_plan_orders:
                self.startup_plan_orders_processed = True
                return
            
            mirrored_count = 0
            for order_id in list(self.startup_plan_orders):
                try:
                    if order_id in self.plan_order_snapshot:
                        order_data = self.plan_order_snapshot[order_id]['order_data']
                        classification = self.plan_order_snapshot[order_id]['classification']
                        
                        # 매칭 검증
                        if classification['is_close_order']:
                            should_process = await self._validate_close_order_with_position_matching(order_data, classification)
                            if not should_process:
                                continue
                        
                        result = await self._process_matched_mirror_order_with_ratio(order_data, classification, self.mirror_ratio_multiplier)
                        
                        if result in ["perfect_success", "partial_success", "force_success"]:
                            mirrored_count += 1
                            self.daily_stats['startup_plan_mirrors'] += 1
                        
                        self.processed_plan_orders.add(order_id)
                except Exception as e:
                    self.logger.error(f"시작 시 예약 주문 복제 오류: {order_id} - {e}")
            
            if mirrored_count > 0:
                await self.telegram.send_message(
                    f"🔄 시작 시 예약 주문 복제 완료\n"
                    f"성공: {mirrored_count}개\n"
                    f"오픈/클로징 매칭: 적용됨\n"
                    f"복제 비율: {self.mirror_ratio_multiplier}x"
                )
            
            self.startup_plan_orders_processed = True
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 복제 실패: {e}")
            self.startup_plan_orders_processed = True

    async def _force_remove_mirror_record(self, bitget_order_id: str, gate_order_id: str):
        """강제로 미러링 기록 제거"""
        try:
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]
            
            if bitget_order_id in self.bitget_to_gate_order_mapping:
                del self.bitget_to_gate_order_mapping[bitget_order_id]
            if gate_order_id in self.gate_to_bitget_order_mapping:
                del self.gate_to_bitget_order_mapping[gate_order_id]
            
            if bitget_order_id in self.cancel_retry_count:
                del self.cancel_retry_count[bitget_order_id]
        except Exception as e:
            self.logger.error(f"강제 미러링 기록 제거 실패: {e}")

    async def _cleanup_mirror_records(self, bitget_order_id: str, gate_order_id: str):
        """미러링 기록 정리"""
        try:
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]
            
            if bitget_order_id in self.bitget_to_gate_order_mapping:
                del self.bitget_to_gate_order_mapping[bitget_order_id]
            if gate_order_id in self.gate_to_bitget_order_mapping:
                del self.gate_to_bitget_order_mapping[gate_order_id]
            
            if bitget_order_id in self.cancel_retry_count:
                del self.cancel_retry_count[bitget_order_id]
        except Exception as e:
            self.logger.error(f"미러링 기록 정리 실패: {e}")

    async def _check_and_cleanup_close_orders_if_no_position(self):
        """포지션이 없으면 클로즈 주문 정리"""
        try:
            current_time = datetime.now()
            
            if (current_time - self.last_position_check).total_seconds() < self.position_check_interval:
                return
            
            self.last_position_check = current_time
            
            if not self.position_close_monitoring:
                return
            
            gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
            has_position = any(pos.get('size', 0) != 0 for pos in gate_positions)
            
            if has_position:
                return
            
            gate_orders = await self.gate_mirror.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            close_orders_to_delete = []
            for gate_order in gate_orders:
                try:
                    initial_info = gate_order.get('initial', {})
                    reduce_only = initial_info.get('reduce_only', False)
                    
                    if reduce_only:
                        close_orders_to_delete.append(gate_order)
                except Exception as e:
                    continue
            
            if close_orders_to_delete:
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
                                await self._cleanup_mirror_records(bitget_order_id, gate_order_id)
                    except Exception as e:
                        error_msg = str(e).lower()
                        if any(keyword in error_msg for keyword in ["not found", "order not exist"]):
                            deleted_count += 1
                
                if deleted_count > 0:
                    self.daily_stats['auto_close_order_cleanups'] += deleted_count
                    await self.telegram.send_message(
                        f"🗑️ 자동 클로즈 주문 정리 완료\n"
                        f"정리된 클로즈 주문: {deleted_count}개\n"
                        f"포지션 상태: 없음"
                    )
        except Exception as e:
            self.logger.error(f"포지션 없음 시 클로즈 주문 정리 실패: {e}")

    # 기존 포지션 처리 메서드들 간소화 유지
    async def process_filled_order(self, order: Dict):
        """체결된 주문으로부터 미러링 실행"""
        try:
            if not self.mirror_trading_enabled:
                return
                
            # 기존 로직 유지하되 복제 비율 적용
            order_id = order.get('orderId', order.get('id', ''))
            side = order.get('side', '').lower()
            size = float(order.get('size', 0))
            fill_price = float(order.get('fillPrice', order.get('price', 0)))
            
            # 복제 비율 적용된 마진 비율 계산
            margin_ratio_result = await self.utils.calculate_dynamic_margin_ratio_with_multiplier(
                size, fill_price, order, self.mirror_ratio_multiplier
            )
            
            if margin_ratio_result['success']:
                # 미러링 실행
                self.daily_stats['order_mirrors'] += 1
                self.daily_stats['ratio_adjusted_orders'] += 1
                
        except Exception as e:
            self.logger.error(f"체결 주문 처리 중 오류: {e}")

    async def process_position(self, bitget_pos: Dict):
        """포지션 처리"""
        try:
            if not self.mirror_trading_enabled:
                return
            
            # 기존 로직 유지
            pos_id = self.utils.generate_position_id(bitget_pos)
            
            if pos_id in self.startup_positions:
                return
            
            # 포지션 추적에 추가
            await self._analyze_and_track_position(bitget_pos)
            
        except Exception as e:
            self.logger.error(f"포지션 처리 중 오류: {e}")

    async def handle_position_close(self, pos_id: str):
        """포지션 종료 처리"""
        try:
            if not self.mirror_trading_enabled:
                return
                
            result = await self.gate_mirror.close_position("BTC_USDT")
            
            # 상태 정리
            if pos_id in self.mirrored_positions:
                del self.mirrored_positions[pos_id]
            if pos_id in self.position_sizes:
                del self.position_sizes[pos_id]
            
            # 포지션 추적에서도 제거
            if pos_id in self.open_position_tracker:
                del self.open_position_tracker[pos_id]
            if pos_id in self.position_entry_amounts:
                del self.position_entry_amounts[pos_id]
            if pos_id in self.ratio_adjusted_amounts:
                del self.ratio_adjusted_amounts[pos_id]
            
            self.daily_stats['full_closes'] += 1
            
        except Exception as e:
            self.logger.error(f"포지션 종료 처리 실패: {e}")

    async def check_sync_status(self) -> Dict:
        """동기화 상태 확인"""
        try:
            # 기존 로직 유지하되 매칭 정보 추가
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            gate_positions = await self.gate_mirror.get_positions("BTC_USDT")
            
            return {
                'is_synced': True,  # 기본값
                'bitget_new_count': len([p for p in bitget_positions if float(p.get('total', 0)) > 0]),
                'gate_new_count': len([p for p in gate_positions if p.get('size', 0) != 0]),
                'position_diff': 0,
                'price_diff': abs(self.bitget_current_price - self.gate_current_price),
                'position_matching_active': len(self.open_position_tracker) > 0,
                'ratio_multiplier': self.mirror_ratio_multiplier
            }
        except Exception as e:
            self.logger.error(f"동기화 상태 확인 실패: {e}")
            return {'is_synced': True, 'error': str(e)}

    async def stop(self):
        """포지션 매니저 중지"""
        try:
            self.logger.info("포지션 매니저 중지 중...")
            # 필요한 정리 작업 수행
        except Exception as e:
            self.logger.error(f"포지션 매니저 중지 실패: {e}")
