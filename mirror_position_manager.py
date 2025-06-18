import os
import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import json

from mirror_trading_utils import MirrorTradingUtils, PositionInfo, MirrorResult

logger = logging.getLogger(__name__)

class MirrorPositionManager:
    """포지션 및 주문 관리 클래스 - 복제 비율 고려한 정확한 체결/취소 구분 + 부분 진입/익절 추적 강화"""
    
    def __init__(self, config, bitget_client, gate_client, gate_mirror_client, telegram_bot, utils):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.gate_mirror = gate_mirror_client
        self.telegram = telegram_bot
        self.utils = utils
        self.logger = logging.getLogger('mirror_position_manager')
        
        # 🔥🔥🔥 환경변수 처리 개선 - O/X 지원 (직접 환경변수 읽기)
        raw_mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'O')
        self.mirror_trading_enabled = self._parse_mirror_trading_mode(raw_mirror_mode)
        
        # 🔥🔥🔥 배율은 기본값 1.0으로 시작, 텔레그램으로 실시간 조정 (환경변수 제거)
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
        
        # 🔥🔥🔥 예약 주문 추적 관리 - 체결/취소 구분 강화 + 복제 비율 고려
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
        
        # 🔥🔥🔥 예약 주문 취소 감지 시스템 - 체결/취소 구분 강화 + 복제 비율 고려
        self.last_plan_order_ids: Set[str] = set()
        self.plan_order_snapshot: Dict[str, Dict] = {}
        self.cancel_retry_count: Dict[str, int] = {}  # 취소 재시도 카운터
        self.max_cancel_retries = 3  # 최대 취소 재시도 횟수
        
        # 🔥🔥🔥 부분 진입/부분 익절 추적 시스템 - 새로 추가
        self.partial_entry_tracking: Dict[str, Dict] = {}  # 부분 진입 추적
        self.partial_exit_tracking: Dict[str, Dict] = {}   # 부분 익절 추적
        self.position_entry_history: Dict[str, List[Dict]] = {}  # 포지션별 진입 내역
        self.position_exit_history: Dict[str, List[Dict]] = {}   # 포지션별 익절 내역
        
        # 🔥🔥🔥 렌더 중단 시 누락된 오픈 주문 감지 및 보상 시스템
        self.missed_open_orders: Dict[str, Dict] = {}  # 누락된 오픈 주문
        self.open_close_matching: Dict[str, Dict] = {}  # 오픈-클로징 매칭
        self.position_based_validation: bool = True  # 포지션 기반 검증 활성화
        
        # 🔥🔥🔥 복제 비율 고려한 정확한 비교 시스템
        self.ratio_aware_comparison: bool = True  # 복제 비율 고려 비교 활성화
        self.margin_tolerance_percent: float = 5.0  # 마진 차이 허용 오차 (5%)
        self.size_tolerance_percent: float = 10.0   # 크기 차이 허용 오차 (10%)
        
        # 시세 차이 관리
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.price_sync_threshold: float = 100.0
        self.position_wait_timeout: int = 60
        
        # 시세 조회 실패 관리 강화
        self.last_valid_bitget_price: float = 0.0
        self.last_valid_gate_price: float = 0.0
        self.bitget_price_failures: int = 0
        self.gate_price_failures: int = 0
        self.max_price_failures: int = 10
        
        # 🔥🔥🔥 예약 주문 동기화 강화 설정 - 개선된 버전
        self.order_sync_enabled: bool = True
        self.order_sync_interval: int = 60  # 45초 → 60초로 변경 (더 신중하게)
        self.last_order_sync_time: datetime = datetime.min
        
        # 🔥🔥🔥 체결된 주문 추적 강화 - 취소와 구분하기 위함
        self.filled_order_tracking_enabled: bool = True
        self.filled_order_check_interval: int = 5  # 5초마다 체결된 주문 확인
        self.last_filled_order_check: datetime = datetime.min
        
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
            'cancel_failures': 0,  # 🔥🔥🔥 취소 실패 통계 추가
            'cancel_successes': 0,  # 🔥🔥🔥 취소 성공 통계 추가
            'filled_detection_successes': 0,  # 🔥🔥🔥 체결 감지 성공 통계
            'partial_entry_matches': 0,  # 🔥🔥🔥 부분 진입 매칭 성공
            'partial_exit_matches': 0,   # 🔥🔥🔥 부분 익절 매칭 성공
            'missed_open_detections': 0, # 🔥🔥🔥 누락 오픈 주문 감지
            'false_cancel_preventions': 0, # 🔥🔥🔥 잘못된 취소 방지
            'ratio_aware_validations': 0,  # 🔥🔥🔥 복제 비율 고려 검증
            'errors': []
        }
        
        # 🔥🔥🔥 클로즈 주문 처리 강화
        self.close_order_processing: bool = True
        self.close_order_validation_mode: str = "enhanced"  # "permissive" → "enhanced"로 변경
        self.force_close_order_mirror: bool = True  # 클로즈 주문 강제 미러링
        
        # 🔥🔥🔥 렌더 재구동 시 예약 주문 미러링 강화
        self.startup_mirror_retry_count: int = 0
        self.max_startup_mirror_retries: int = 3
        self.startup_mirror_delay: int = 10  # 10초 대기 후 재시도
        
        # 포지션 종료 시 클로즈 주문 정리 관련
        self.position_close_monitoring: bool = True
        self.last_position_check: datetime = datetime.min
        self.position_check_interval: int = 30
        
        # 시작 시간 추적
        self.startup_time: datetime = datetime.now()
        
        # 렌더 재구동 시 기존 게이트 포지션 확인
        self.existing_gate_positions: Dict = {}
        self.render_restart_detected: bool = False
        
        # 🔥🔥🔥 게이트 기존 예약 주문 중복 방지 - 개선된 버전
        self.gate_existing_order_hashes: Set[str] = set()
        self.gate_existing_orders_detailed: Dict[str, Dict] = {}
        
        # 주문 ID 매핑 추적
        self.bitget_to_gate_order_mapping: Dict[str, str] = {}
        self.gate_to_bitget_order_mapping: Dict[str, str] = {}
        
        # 🔥🔥🔥 가격 기반 중복 방지 시스템 - 완화된 버전
        self.mirrored_trigger_prices: Set[str] = set()
        self.price_tolerance = 5.0  # ±5달러 허용
        
        self.logger.info(f"🔥 미러 포지션 매니저 초기화 완료 - 복제 비율 고려 정확한 매칭 + 부분 진입/익절 추적 + 누락 감지")

    def _parse_mirror_trading_mode(self, mode_str: str) -> bool:
        """🔥🔥🔥 미러링 모드 파싱 - O/X 정확한 구분"""
        if isinstance(mode_str, bool):
            return mode_str
        
        # 문자열로 변환하되 원본 보존
        mode_str_original = str(mode_str).strip()
        mode_str_upper = mode_str_original.upper()
        
        self.logger.info(f"🔍 포지션 매니저 미러링 모드 파싱: 원본='{mode_str_original}', 대문자='{mode_str_upper}'")
        
        # 🔥🔥🔥 영어 O, X 우선 처리 (숫자 0과 구분)
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
            self.logger.info("🔥 포지션 매니저 초기화 시작 - 복제 비율 고려 정확한 매칭 + 부분 진입/익절 추적 + 누락 감지")
            
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
            
            # 🔥🔥🔥 부분 진입/부분 익절 초기 분석
            await self._analyze_existing_partial_entries_exits()
            
            # 🔥🔥🔥 시작 시 기존 예약 주문 복제 - 강화된 재시도 로직
            await self._mirror_startup_plan_orders_with_retry()
            
            self.logger.info("✅ 포지션 매니저 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"포지션 매니저 초기화 실패: {e}")
            raise

    async def _analyze_existing_partial_entries_exits(self):
        """🔥🔥🔥 기존 부분 진입/부분 익절 상황 분석"""
        try:
            self.logger.info("🔍 기존 부분 진입/부분 익절 상황 분석 시작")
            
            # 1. 비트겟 현재 포지션 조회
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            active_positions = [pos for pos in bitget_positions if float(pos.get('total', 0)) > 0]
            
            # 2. 게이트 현재 포지션 조회
            gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
            active_gate_positions = [pos for pos in gate_positions if pos.get('size', 0) != 0]
            
            # 3. 현재 예약 주문들 분석
            all_plan_orders = await self._get_all_current_plan_orders_enhanced()
            
            # 4. 부분 진입/익절 상황 분석
            for bitget_pos in active_positions:
                pos_side = bitget_pos.get('holdSide', '').lower()
                pos_size = float(bitget_pos.get('total', 0))
                entry_price = float(bitget_pos.get('openPriceAvg', 0))
                
                # 5. 해당 포지션과 관련된 클로징 주문들 찾기
                related_close_orders = []
                for order in all_plan_orders:
                    order_side = order.get('side', order.get('tradeSide', '')).lower()
                    reduce_only = order.get('reduceOnly', False)
                    
                    # 클로징 주문 판별
                    if (reduce_only or 'close' in order_side or 
                        (pos_side == 'long' and 'sell' in order_side) or
                        (pos_side == 'short' and 'buy' in order_side)):
                        related_close_orders.append(order)
                
                if related_close_orders:
                    # 6. 부분 익절 추적 정보 저장
                    pos_key = f"{pos_side}_{entry_price:.2f}"
                    self.partial_exit_tracking[pos_key] = {
                        'bitget_position': bitget_pos,
                        'related_close_orders': related_close_orders,
                        'total_close_size': sum(float(o.get('size', 0)) for o in related_close_orders),
                        'created_at': datetime.now().isoformat(),
                        'position_size': pos_size
                    }
                    
                    self.logger.info(f"📊 부분 익절 추적 설정: {pos_key} - 포지션 크기: {pos_size}, 클로징 주문: {len(related_close_orders)}개")
            
            # 7. 게이트 포지션과 비교하여 불일치 감지
            for gate_pos in active_gate_positions:
                gate_size = int(gate_pos.get('size', 0))
                gate_side = 'long' if gate_size > 0 else 'short'
                
                # 해당하는 비트겟 포지션 찾기
                matching_bitget_pos = None
                for bitget_pos in active_positions:
                    if bitget_pos.get('holdSide', '').lower() == gate_side:
                        matching_bitget_pos = bitget_pos
                        break
                
                if not matching_bitget_pos:
                    self.logger.warning(f"⚠️ 게이트에만 존재하는 포지션 감지: {gate_side} {abs(gate_size)}개")
                    # 렌더 중단 시 누락된 오픈 주문 가능성
                    self.missed_open_orders[f"gate_only_{gate_side}"] = {
                        'gate_position': gate_pos,
                        'detected_at': datetime.now().isoformat(),
                        'status': 'analysis_needed'
                    }
            
            self.logger.info(f"✅ 부분 진입/익절 분석 완료: 부분 익절 추적 {len(self.partial_exit_tracking)}건, 누락 감지 {len(self.missed_open_orders)}건")
            
        except Exception as e:
            self.logger.error(f"부분 진입/익절 분석 실패: {e}")

    async def monitor_plan_orders_cycle(self):
        """🔥🔥🔥 예약 주문 모니터링 사이클 - 복제 비율 고려한 정확한 체결/취소 구분 강화"""
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
            
            # 🔥🔥🔥 체결된 주문 기록 업데이트
            await self._update_recently_filled_orders()
            
            # 포지션 종료 시 클로즈 주문 자동 정리
            await self._check_and_cleanup_close_orders_if_no_position()
            
            # 🔥🔥🔥 모든 예약 주문 조회 - 클로즈 주문 포함
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
            
            # 🔥🔥🔥 사라진 예약 주문 분석 - 복제 비율 고려한 정확한 체결 vs 취소 구분
            disappeared_order_ids = self.last_plan_order_ids - current_order_ids
            
            if disappeared_order_ids:
                self.logger.info(f"📋 {len(disappeared_order_ids)}개의 예약 주문이 사라짐 - 복제 비율 고려한 정확한 체결/취소 분석 시작")
                
                canceled_count = 0
                filled_count = 0
                
                for disappeared_id in disappeared_order_ids:
                    try:
                        # 🔥🔥🔥 복제 비율 고려한 정확한 체결/취소 구분 로직
                        analysis_result = await self._analyze_order_disappearance_with_ratio_awareness(disappeared_id)
                        
                        if analysis_result['is_filled']:
                            filled_count += 1
                            self.daily_stats['filled_detection_successes'] += 1
                            self.logger.info(f"✅ 복제 비율 고려 체결 감지: {disappeared_id} - 게이트 주문 유지")
                            
                            # 체결된 주문은 미러링 기록에서 제거만 하고 게이트 주문은 건드리지 않음
                            if disappeared_id in self.mirrored_plan_orders:
                                mirror_info = self.mirrored_plan_orders[disappeared_id]
                                gate_order_id = mirror_info.get('gate_order_id')
                                self.logger.info(f"🎯 체결된 주문의 미러링 기록 정리: {disappeared_id} → {gate_order_id}")
                                
                                # 🔥🔥🔥 부분 진입/부분 익절 추적 업데이트
                                await self._update_partial_tracking_on_fill(disappeared_id, mirror_info)
                                
                                # 게이트 주문은 자동으로 체결될 것이므로 건드리지 않음
                                await self._cleanup_mirror_records_for_filled_order(disappeared_id, gate_order_id)
                        else:
                            # 🔥🔥🔥 복제 비율 고려한 정확한 취소 처리
                            cancel_result = await self._handle_plan_order_cancel_with_ratio_awareness(disappeared_id, analysis_result)
                            if cancel_result['success']:
                                canceled_count += 1
                                self.daily_stats['cancel_successes'] += 1
                                if cancel_result.get('false_cancel_prevented'):
                                    self.daily_stats['false_cancel_preventions'] += 1
                            else:
                                self.daily_stats['cancel_failures'] += 1
                                
                    except Exception as e:
                        self.logger.error(f"사라진 주문 분석 중 예외: {disappeared_id} - {e}")
                        self.daily_stats['cancel_failures'] += 1
                
                self.daily_stats['plan_order_cancels'] += canceled_count
                
                # 🔥🔥🔥 체결/취소 결과 알림 - 복제 비율 정보 포함
                if filled_count > 0 or canceled_count > 0:
                    ratio_info = f" (복제비율: {self.mirror_ratio_multiplier}x)" if self.mirror_ratio_multiplier != 1.0 else ""
                    
                    await self.telegram.send_message(
                        f"📋 예약 주문 변화 분석 결과{ratio_info}\n"
                        f"사라진 주문: {len(disappeared_order_ids)}개\n"
                        f"🎯 체결 감지: {filled_count}개 (게이트 주문 유지)\n"
                        f"🚫 취소 동기화: {canceled_count}개\n"
                        f"📊 현재 시세 차이: ${price_diff_abs:.2f}\n"
                        f"📈 복제 비율: {self.mirror_ratio_multiplier}x\n\n"
                        f"{'✅ 복제 비율을 고려하여 체결/취소가 정확히 구분되어 처리되었습니다!' if filled_count > 0 else '🔄 모든 취소가 성공적으로 동기화되었습니다!'}"
                    )
            
            # 🔥🔥🔥 새로운 예약 주문 감지 - 복제 비율 적용 + 부분 진입/익절 고려
            new_orders_count = 0
            new_close_orders_count = 0
            perfect_mirrors = 0
            forced_close_mirrors = 0
            
            for order in all_current_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if not order_id:
                    continue
                
                # 🔥🔥🔥 개선된 중복 처리 방지
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
                    
                    # 🔥🔥🔥 개선된 중복 복제 확인
                    is_duplicate = await self._is_duplicate_order_improved(order)
                    if is_duplicate:
                        self.daily_stats['duplicate_orders_prevented'] += 1
                        self.logger.info(f"🛡️ 중복 감지로 스킵: {order_id}")
                        self.processed_plan_orders.add(order_id)
                        continue
                    
                    # 🔥🔥🔥 새로운 예약 주문 처리 - 복제 비율 적용 + 부분 진입/익절 검증
                    try:
                        # 클로즈 주문 상세 분석
                        close_details = await self.utils.determine_close_order_details_enhanced(order)
                        is_close_order = close_details['is_close_order']
                        
                        self.logger.info(f"🎯 새로운 예약 주문 감지: {order_id} (클로즈: {is_close_order}, 복제비율: {self.mirror_ratio_multiplier}x)")
                        self.logger.debug(f"   주문 상세: side={order.get('side')}, reduceOnly={order.get('reduceOnly')}")
                        
                        # 🔥🔥🔥 클로즈 주문인 경우 부분 진입/익절 검증 강화
                        validation_result = "proceed"
                        
                        if is_close_order:
                            validation_result = await self._validate_close_order_with_partial_tracking(order, close_details)
                            
                            if validation_result == "skip_no_matching_position":
                                self.logger.warning(f"⏭️ 매칭되는 포지션이 없어 클로즈 주문 스킵: {order_id}")
                                self.processed_plan_orders.add(order_id)
                                self.daily_stats['close_order_skipped'] += 1
                                continue
                            elif validation_result == "skip_partial_mismatch":
                                self.logger.warning(f"⏭️ 부분 진입/익절 불일치로 클로즈 주문 스킵: {order_id}")
                                self.processed_plan_orders.add(order_id)
                                self.daily_stats['close_order_skipped'] += 1
                                continue
                            elif validation_result == "force_mirror":
                                self.logger.warning(f"🚀 클로즈 주문 강제 미러링: {order_id}")
                                forced_close_mirrors += 1
                                self.daily_stats['close_order_forced'] += 1
                        
                        # 🔥🔥🔥 복제 비율 적용된 완벽한 미러링 처리
                        result = await self._process_perfect_mirror_order_with_ratio(order, close_details, self.mirror_ratio_multiplier)
                        
                        # 🔥🔥🔥 모든 성공 케이스 처리
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
                                
                                # 🔥🔥🔥 부분 익절 추적 업데이트
                                await self._update_partial_exit_tracking(order, close_details)
                                
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
            
            # 🔥🔥🔥 성공적인 미러링 결과 알림 - 복제 비율 정보 포함
            if new_orders_count > 0:
                ratio_info = f" (복제비율: {self.mirror_ratio_multiplier}x)" if self.mirror_ratio_multiplier != 1.0 else ""
                
                if forced_close_mirrors > 0:
                    await self.telegram.send_message(
                        f"🚀 클로즈 주문 강제 미러링 성공{ratio_info}\n"
                        f"강제 미러링: {forced_close_mirrors}개\n"
                        f"완벽 복제: {perfect_mirrors}개\n"
                        f"클로즈 주문: {new_close_orders_count}개\n"
                        f"전체 신규: {new_orders_count}개\n\n"
                        f"🔥 클로즈 주문은 부분 진입/익절을 고려하여 정확히 미러링됩니다{ratio_info}"
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

    async def _analyze_order_disappearance_with_ratio_awareness(self, disappeared_order_id: str) -> Dict:
        """🔥🔥🔥 복제 비율을 고려한 정확한 주문 사라짐 분석"""
        try:
            self.logger.info(f"🔍 복제 비율 고려 주문 사라짐 분석: {disappeared_order_id}")
            
            # 1. 기본 체결 여부 확인 (기존 로직)
            basic_filled_check = await self._check_if_order_was_filled(disappeared_order_id)
            
            # 2. 미러링 정보 확인
            mirror_info = self.mirrored_plan_orders.get(disappeared_order_id)
            
            if not mirror_info:
                # 미러링되지 않은 주문은 단순히 체결/취소 구분
                return {
                    'is_filled': basic_filled_check,
                    'confidence': 'medium',
                    'method': 'basic_check_no_mirror',
                    'reason': '미러링되지 않은 주문',
                    'gate_order_id': None
                }
            
            gate_order_id = mirror_info.get('gate_order_id')
            ratio_multiplier = mirror_info.get('ratio_multiplier', 1.0)
            
            # 3. 게이트 주문 상태 확인
            gate_order_exists = False
            gate_order_status = 'unknown'
            
            try:
                gate_orders = await self.gate_mirror.get_price_triggered_orders(self.GATE_CONTRACT, "open")
                gate_order_found = None
                
                for gate_order in gate_orders:
                    if gate_order.get('id') == gate_order_id:
                        gate_order_exists = True
                        gate_order_found = gate_order
                        gate_order_status = 'active'
                        break
                
                if not gate_order_exists:
                    # 게이트 주문도 사라짐 - 체결되었을 가능성 높음
                    gate_order_status = 'disappeared'
                    
            except Exception as e:
                self.logger.warning(f"게이트 주문 상태 확인 실패: {e}")
            
            # 4. 🔥🔥🔥 복제 비율을 고려한 종합 분석
            analysis_result = {
                'is_filled': False,
                'confidence': 'low',
                'method': 'comprehensive_ratio_aware',
                'gate_order_id': gate_order_id,
                'gate_order_exists': gate_order_exists,
                'gate_order_status': gate_order_status,
                'ratio_multiplier': ratio_multiplier,
                'basic_filled_check': basic_filled_check,
                'detailed_analysis': {}
            }
            
            # 🔥🔥🔥 분석 로직 우선순위
            if basic_filled_check and not gate_order_exists:
                # 비트겟 체결 + 게이트 주문 사라짐 = 높은 확률로 체결
                analysis_result.update({
                    'is_filled': True,
                    'confidence': 'very_high',
                    'reason': '비트겟 체결 확인 + 게이트 주문도 사라짐'
                })
                
            elif basic_filled_check and gate_order_exists:
                # 비트겟은 체결됐지만 게이트 주문은 아직 존재 - 복제 비율 차이로 인한 미체결
                analysis_result.update({
                    'is_filled': True,
                    'confidence': 'high',
                    'reason': f'비트겟 체결 확인 (복제비율 {ratio_multiplier}x로 인한 게이트 미체결 가능)'
                })
                
            elif not basic_filled_check and not gate_order_exists:
                # 둘 다 사라짐 - 동시 취소 가능성 또는 시스템 오류
                # 🔥🔥🔥 복제 비율 고려하여 정확한 판단
                recent_bitget_orders = await self.bitget.get_recent_filled_orders(symbol=self.SYMBOL, minutes=2)
                recent_filled_ids = [o.get('orderId', o.get('id', '')) for o in recent_bitget_orders]
                
                if disappeared_order_id in recent_filled_ids:
                    analysis_result.update({
                        'is_filled': True,
                        'confidence': 'high',
                        'reason': '최근 체결 기록에서 발견'
                    })
                else:
                    analysis_result.update({
                        'is_filled': False,
                        'confidence': 'medium',
                        'reason': '동시 취소로 판단 (체결 기록 없음)'
                    })
                    
            elif not basic_filled_check and gate_order_exists:
                # 비트겟만 취소, 게이트는 여전히 존재 - 명확한 취소
                analysis_result.update({
                    'is_filled': False,
                    'confidence': 'very_high',
                    'reason': '비트겟만 취소됨 (게이트 주문 여전히 존재)'
                })
            
            # 5. 🔥🔥🔥 추가 검증 - 포지션 변화 분석
            if analysis_result['confidence'] in ['low', 'medium']:
                position_analysis = await self._analyze_position_changes_for_order(disappeared_order_id, mirror_info)
                if position_analysis['position_changed']:
                    analysis_result.update({
                        'is_filled': True,
                        'confidence': 'high',
                        'reason': f"포지션 변화 감지: {position_analysis['description']}"
                    })
            
            self.daily_stats['ratio_aware_validations'] += 1
            
            self.logger.info(f"✅ 복제 비율 고려 분석 완료: {disappeared_order_id}")
            self.logger.info(f"   결과: {'체결' if analysis_result['is_filled'] else '취소'} (신뢰도: {analysis_result['confidence']})")
            self.logger.info(f"   이유: {analysis_result['reason']}")
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"복제 비율 고려 주문 분석 실패: {disappeared_order_id} - {e}")
            return {
                'is_filled': basic_filled_check if 'basic_filled_check' in locals() else False,
                'confidence': 'low',
                'method': 'fallback',
                'reason': f'분석 오류: {str(e)}',
                'gate_order_id': None
            }

    async def _analyze_position_changes_for_order(self, order_id: str, mirror_info: Dict) -> Dict:
        """🔥🔥🔥 주문과 관련된 포지션 변화 분석"""
        try:
            # 현재 비트겟 포지션 조회
            current_positions = await self.bitget.get_positions(self.SYMBOL)
            active_positions = [pos for pos in current_positions if float(pos.get('total', 0)) > 0]
            
            # 미러링 정보에서 예상 변화 계산
            original_order = mirror_info.get('bitget_order', {})
            order_side = original_order.get('side', original_order.get('tradeSide', '')).lower()
            order_size = float(original_order.get('size', 0))
            
            # 포지션 변화 감지 로직
            position_changed = False
            description = "변화 없음"
            
            # 간단한 포지션 크기 변화 감지
            if active_positions:
                current_total_size = sum(float(pos.get('total', 0)) for pos in active_positions)
                
                # 이전 포지션 크기와 비교 (간접적 추정)
                if hasattr(self, '_last_position_size'):
                    size_diff = abs(current_total_size - self._last_position_size)
                    if size_diff >= order_size * 0.8:  # 80% 이상 매칭되면 변화로 판단
                        position_changed = True
                        description = f"포지션 크기 변화: {size_diff:.4f} (주문 크기: {order_size:.4f})"
                
                # 현재 크기 저장
                self._last_position_size = current_total_size
            
            return {
                'position_changed': position_changed,
                'description': description,
                'current_positions': len(active_positions),
                'order_side': order_side,
                'order_size': order_size
            }
            
        except Exception as e:
            self.logger.error(f"포지션 변화 분석 실패: {e}")
            return {
                'position_changed': False,
                'description': f'분석 오류: {str(e)}',
                'current_positions': 0
            }

    async def _handle_plan_order_cancel_with_ratio_awareness(self, bitget_order_id: str, analysis_result: Dict) -> Dict:
        """🔥🔥🔥 복제 비율을 고려한 정확한 예약 주문 취소 처리"""
        try:
            self.logger.info(f"🚫 복제 비율 고려 예약 주문 취소 처리: {bitget_order_id}")
            
            # 미러링된 주문인지 확인
            if bitget_order_id not in self.mirrored_plan_orders:
                self.logger.info(f"미러링되지 않은 주문이므로 취소 처리 스킵: {bitget_order_id}")
                return {'success': True, 'reason': 'not_mirrored'}
            
            mirror_info = self.mirrored_plan_orders[bitget_order_id]
            gate_order_id = mirror_info.get('gate_order_id')
            ratio_multiplier = mirror_info.get('ratio_multiplier', 1.0)
            
            if not gate_order_id:
                self.logger.warning(f"게이트 주문 ID가 없음: {bitget_order_id}")
                del self.mirrored_plan_orders[bitget_order_id]
                return {'success': True, 'reason': 'no_gate_order_id'}
            
            # 🔥🔥🔥 복제 비율을 고려한 잘못된 취소 방지 검증
            false_cancel_check = await self._check_false_cancel_with_ratio(bitget_order_id, gate_order_id, analysis_result, ratio_multiplier)
            
            if false_cancel_check['prevent_cancel']:
                self.logger.warning(f"🛡️ 잘못된 취소 방지: {bitget_order_id} - {false_cancel_check['reason']}")
                return {
                    'success': False, 
                    'reason': 'false_cancel_prevented',
                    'false_cancel_prevented': True,
                    'prevention_reason': false_cancel_check['reason']
                }
            
            # 🔥🔥🔥 재시도 카운터 확인
            retry_count = self.cancel_retry_count.get(bitget_order_id, 0)
            
            if retry_count >= self.max_cancel_retries:
                self.logger.error(f"최대 재시도 횟수 초과: {bitget_order_id} (재시도: {retry_count}회)")
                await self._force_remove_mirror_record(bitget_order_id, gate_order_id)
                return {'success': False, 'reason': 'max_retries_exceeded'}
            
            # 🔥🔥🔥 게이트에서 주문 취소 시도
            try:
                self.logger.info(f"🎯 게이트 주문 취소 시도: {gate_order_id} (복제비율: {ratio_multiplier}x, 재시도: {retry_count + 1}/{self.max_cancel_retries})")
                
                cancel_result = await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                
                # 취소 성공
                self.logger.info(f"✅ 게이트 주문 취소 성공: {gate_order_id}")
                
                # 1초 대기 후 취소 확인
                await asyncio.sleep(1.0)
                
                # 취소 확인
                gate_orders = await self.gate_mirror.get_price_triggered_orders("BTC_USDT", "open")
                gate_order_exists = any(order.get('id') == gate_order_id for order in gate_orders)
                
                if gate_order_exists:
                    # 아직 존재하면 재시도
                    self.cancel_retry_count[bitget_order_id] = retry_count + 1
                    self.logger.warning(f"⚠️ 게이트 주문이 아직 존재함, 재시도 예정: {gate_order_id}")
                    return {'success': False, 'reason': 'still_exists_retry_needed'}
                else:
                    # 취소 확인됨
                    success = True
                    
            except Exception as cancel_error:
                error_msg = str(cancel_error).lower()
                
                # 🔥🔥🔥 이미 존재하지 않는 주문인 경우 성공으로 처리
                if any(keyword in error_msg for keyword in [
                    "not found", "order not exist", "invalid order", 
                    "order does not exist", "auto_order_not_found",
                    "order_not_found", "not_found", "已取消", "cancelled"
                ]):
                    success = True
                    self.logger.info(f"✅ 게이트 주문이 이미 처리됨: {gate_order_id}")
                else:
                    # 다른 오류인 경우 재시도
                    success = False
                    self.cancel_retry_count[bitget_order_id] = retry_count + 1
                    self.logger.error(f"❌ 게이트 주문 취소 실패: {gate_order_id} - {cancel_error}")
            
            # 🔥🔥🔥 결과 처리
            if success:
                # 성공한 경우 모든 기록 정리
                await self._cleanup_mirror_records(bitget_order_id, gate_order_id)
                
                ratio_info = f" (복제비율: {ratio_multiplier}x)" if ratio_multiplier != 1.0 else ""
                
                await self.telegram.send_message(
                    f"🚫✅ 예약 주문 취소 동기화 완료{ratio_info}\n"
                    f"비트겟 ID: {bitget_order_id}\n"
                    f"게이트 ID: {gate_order_id}\n"
                    f"재시도 횟수: {retry_count + 1}회\n"
                    f"분석 신뢰도: {analysis_result.get('confidence', 'unknown')}"
                )
                
                self.logger.info(f"🎯 복제 비율 고려 예약 주문 취소 동기화 성공: {bitget_order_id} → {gate_order_id}")
                return {'success': True, 'reason': 'cancel_completed'}
            else:
                # 실패한 경우 다음 사이클에서 재시도
                self.logger.warning(f"⚠️ 복제 비율 고려 예약 주문 취소 재시도 예정: {bitget_order_id} (다음 사이클)")
                return {'success': False, 'reason': 'retry_scheduled'}
                
        except Exception as e:
            self.logger.error(f"복제 비율 고려 예약 주문 취소 처리 중 예외 발생: {bitget_order_id} - {e}")
            
            # 예외 발생 시 재시도 카운터 증가
            retry_count = self.cancel_retry_count.get(bitget_order_id, 0)
            self.cancel_retry_count[bitget_order_id] = retry_count + 1
            
            return {'success': False, 'reason': f'exception: {str(e)}'}

    async def _check_false_cancel_with_ratio(self, bitget_order_id: str, gate_order_id: str, 
                                           analysis_result: Dict, ratio_multiplier: float) -> Dict:
        """🔥🔥🔥 복제 비율을 고려한 잘못된 취소 방지 검증"""
        try:
            # 신뢰도가 매우 높으면 잘못된 취소가 아님
            if analysis_result.get('confidence') == 'very_high':
                return {'prevent_cancel': False, 'reason': 'high_confidence_analysis'}
            
            # 🔥🔥🔥 복제 비율로 인한 진입금/마진 차이가 취소로 잘못 감지되는 경우 방지
            mirror_info = self.mirrored_plan_orders.get(bitget_order_id, {})
            
            # 1. 복제 비율이 1.0이 아닌 경우 더 신중하게 검증
            if ratio_multiplier != 1.0:
                # 게이트 주문이 여전히 존재하는지 다시 확인
                try:
                    gate_orders = await self.gate_mirror.get_price_triggered_orders(self.GATE_CONTRACT, "open")
                    gate_order_still_exists = any(order.get('id') == gate_order_id for order in gate_orders)
                    
                    if gate_order_still_exists:
                        # 게이트 주문이 여전히 존재 - 복제 비율 차이로 인한 가격/크기 차이일 수 있음
                        original_order = mirror_info.get('bitget_order', {})
                        trigger_price = None
                        
                        for price_field in ['triggerPrice', 'price', 'executePrice']:
                            if original_order.get(price_field):
                                trigger_price = float(original_order.get(price_field))
                                break
                        
                        if trigger_price:
                            # 현재 시세와 트리거 가격 차이 확인
                            price_diff_from_current = abs(trigger_price - self.bitget_current_price)
                            
                            # 복제 비율로 인한 차이가 클 경우 잘못된 취소일 가능성
                            if ratio_multiplier > 1.5 or ratio_multiplier < 0.7:
                                return {
                                    'prevent_cancel': True,
                                    'reason': f'복제 비율 {ratio_multiplier}x로 인한 진입금 차이 - 잘못된 취소 방지'
                                }
                            
                            # 트리거 가격이 현재가와 매우 가까운 경우 체결 가능성 높음
                            if price_diff_from_current < self.bitget_current_price * 0.001:  # 0.1% 이내
                                return {
                                    'prevent_cancel': True,
                                    'reason': f'트리거 가격이 현재가와 매우 가까움 (차이: ${price_diff_from_current:.2f}) - 체결 대기'
                                }
                    
                except Exception as e:
                    self.logger.warning(f"게이트 주문 재확인 실패: {e}")
            
            # 2. 최근 체결 주문에서 재확인
            try:
                recent_filled = await self.bitget.get_recent_filled_orders(symbol=self.SYMBOL, minutes=1)
                for filled_order in recent_filled:
                    filled_id = filled_order.get('orderId', filled_order.get('id', ''))
                    if filled_id == bitget_order_id:
                        return {
                            'prevent_cancel': True,
                            'reason': '최근 1분 내 체결 기록 발견 - 취소가 아닌 체결'
                        }
            except Exception as e:
                self.logger.warning(f"최근 체결 주문 재확인 실패: {e}")
            
            # 3. 부분 진입/익절 상황에서의 추가 검증
            if mirror_info.get('is_close_order'):
                # 클로즈 주문의 경우 포지션 상태 확인
                try:
                    current_positions = await self.bitget.get_positions(self.SYMBOL)
                    active_positions = [pos for pos in current_positions if float(pos.get('total', 0)) > 0]
                    
                    if active_positions:
                        # 포지션이 여전히 존재하면 부분 익절일 가능성
                        return {
                            'prevent_cancel': True,
                            'reason': '포지션이 여전히 존재 - 부분 익절 가능성으로 취소 방지'
                        }
                except Exception as e:
                    self.logger.warning(f"포지션 상태 확인 실패: {e}")
            
            # 기본적으로 취소 진행
            return {'prevent_cancel': False, 'reason': 'no_false_cancel_indicators'}
            
        except Exception as e:
            self.logger.error(f"잘못된 취소 방지 검증 실패: {e}")
            # 오류 시에는 안전상 취소 방지
            return {'prevent_cancel': True, 'reason': f'검증 오류로 안전상 방지: {str(e)}'}

    async def _validate_close_order_with_partial_tracking(self, order: Dict, close_details: Dict) -> str:
        """🔥🔥🔥 부분 진입/익절 추적을 고려한 클로즈 주문 검증"""
        try:
            if not self.close_order_processing:
                return "skip_disabled"
            
            order_id = order.get('orderId', order.get('planOrderId', ''))
            position_side = close_details['position_side']  # 'long' 또는 'short'
            
            self.logger.info(f"🔍 부분 추적 고려 클로즈 주문 검증: {order_id} (예상 포지션: {position_side})")
            
            # 1. 현재 게이트 포지션 상태 확인
            try:
                gate_positions = await self.gate_mirror.get_positions("BTC_USDT")
                current_gate_position = None
                
                if gate_positions:
                    for pos in gate_positions:
                        pos_size = int(pos.get('size', 0))
                        if pos_size != 0:
                            current_gate_position = pos
                            break
                
                if not current_gate_position:
                    self.logger.warning(f"🔍 게이트에 포지션이 없음")
                    
                    # 2. 비트겟 포지션 확인하여 렌더 중단 시 누락 감지
                    bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                    active_bitget_positions = [pos for pos in bitget_positions if float(pos.get('total', 0)) > 0]
                    
                    if active_bitget_positions:
                        # 비트겟에는 포지션이 있지만 게이트에는 없음 - 렌더 중단 시 누락된 오픈 주문
                        for bitget_pos in active_bitget_positions:
                            bitget_side = bitget_pos.get('holdSide', '').lower()
                            if bitget_side == position_side:
                                self.logger.warning(f"🔴 렌더 중단 시 누락된 오픈 주문 감지: {position_side} 포지션")
                                
                                # 누락된 오픈 주문 기록
                                missed_key = f"missed_{position_side}_{order_id}"
                                self.missed_open_orders[missed_key] = {
                                    'bitget_position': bitget_pos,
                                    'close_order': order,
                                    'detected_at': datetime.now().isoformat(),
                                    'reason': '렌더 중단 시 누락된 오픈 주문으로 추정'
                                }
                                self.daily_stats['missed_open_detections'] += 1
                                
                                # 🔥🔥🔥 클로즈 주문 스킵 (오픈 주문이 없으므로 의미 없음)
                                return "skip_no_matching_position"
                    
                    # 🔥🔥🔥 강제 미러링 모드가 활성화된 경우
                    if self.force_close_order_mirror:
                        self.logger.warning(f"🚀 포지션 없지만 클로즈 주문 강제 미러링: {order_id}")
                        return "force_mirror"
                    else:
                        return "skip_no_matching_position"
                
                # 3. 포지션 방향 매칭 확인
                current_size = int(current_gate_position.get('size', 0))
                current_side = 'long' if current_size > 0 else 'short'
                
                if current_side != position_side:
                    self.logger.warning(f"⚠️ 포지션 방향 불일치: 현재={current_side}, 예상={position_side}")
                    
                    # 🔥🔥🔥 부분 진입/익절 추적에서 허용 가능한 불일치인지 확인
                    mismatch_allowed = await self._check_if_mismatch_allowed_by_partial_tracking(
                        current_side, position_side, order
                    )
                    
                    if mismatch_allowed:
                        self.logger.info(f"✅ 부분 추적으로 인한 허용 가능한 불일치: {current_side} → {position_side}")
                        return "proceed"
                    else:
                        return "skip_partial_mismatch"
                
                # 4. 부분 익절 크기 검증
                order_size = float(order.get('size', 0))
                current_abs_size = abs(current_size)
                
                if order_size > current_abs_size * 1.1:  # 10% 오차 허용
                    self.logger.warning(f"⚠️ 클로즈 주문 크기가 현재 포지션보다 큼: {order_size} > {current_abs_size}")
                    
                    # 🔥🔥🔥 부분 진입으로 인한 차이인지 확인
                    partial_difference_explanation = await self._explain_size_difference_by_partial_tracking(
                        order_size, current_abs_size, position_side
                    )
                    
                    if partial_difference_explanation['explained']:
                        self.logger.info(f"✅ 부분 진입으로 인한 크기 차이 설명됨: {partial_difference_explanation['reason']}")
                        return "proceed"
                    else:
                        return "skip_partial_mismatch"
                
                # 5. 모든 검증 통과
                self.logger.info(f"✅ 부분 추적 고려 클로즈 주문 검증 통과: {order_id}")
                return "proceed"
                
            except Exception as e:
                self.logger.error(f"게이트 포지션 확인 실패하지만 강제 미러링: {order_id} - {e}")
                return "force_mirror"
            
        except Exception as e:
            self.logger.error(f"부분 추적 고려 클로즈 주문 검증 실패하지만 강제 미러링: {e}")
            return "force_mirror"

    async def _check_if_mismatch_allowed_by_partial_tracking(self, current_side: str, expected_side: str, order: Dict) -> bool:
        """🔥🔥🔥 부분 진입/익절 추적에 의해 허용되는 불일치인지 확인"""
        try:
            # 부분 진입/익절 추적 정보에서 허용 가능한 시나리오 확인
            
            # 1. 부분 익절 추적에서 크로스 매칭 허용 여부 확인
            for pos_key, tracking_info in self.partial_exit_tracking.items():
                tracking_side = pos_key.split('_')[0]  # 'long' 또는 'short'
                
                if tracking_side == expected_side:
                    # 부분 익절 중인 포지션과 매칭
                    self.logger.info(f"📊 부분 익절 추적 매칭: {pos_key}")
                    return True
            
            # 2. 누락된 오픈 주문으로 인한 불일치 허용
            for missed_key, missed_info in self.missed_open_orders.items():
                if expected_side in missed_key:
                    self.logger.info(f"🔴 누락된 오픈 주문으로 인한 불일치 허용: {missed_key}")
                    return True
            
            # 3. 복제 비율로 인한 포지션 크기 차이가 방향 전환을 일으켰을 가능성
            if self.mirror_ratio_multiplier != 1.0:
                self.logger.info(f"🔄 복제 비율 {self.mirror_ratio_multiplier}x로 인한 포지션 차이 허용")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"부분 추적 불일치 확인 실패: {e}")
            return False

    async def _explain_size_difference_by_partial_tracking(self, order_size: float, current_size: float, position_side: str) -> Dict:
        """🔥🔥🔥 부분 진입/익절 추적으로 크기 차이 설명"""
        try:
            explanation = {
                'explained': False,
                'reason': '설명 없음',
                'confidence': 'low'
            }
            
            # 1. 부분 진입 기록에서 설명 찾기
            for entry_key, entry_info in self.partial_entry_tracking.items():
                if position_side in entry_key:
                    entry_history = entry_info.get('entry_history', [])
                    total_entered = sum(float(h.get('size', 0)) for h in entry_history)
                    
                    # 부분 진입으로 인한 차이 설명
                    if abs(total_entered - order_size) < order_size * 0.1:  # 10% 오차 허용
                        explanation.update({
                            'explained': True,
                            'reason': f'부분 진입 총합 {total_entered:.4f}과 클로즈 크기 {order_size:.4f} 매칭',
                            'confidence': 'high'
                        })
                        return explanation
            
            # 2. 복제 비율로 인한 차이 설명
            if self.mirror_ratio_multiplier != 1.0:
                expected_gate_size = order_size * self.mirror_ratio_multiplier
                if abs(current_size - expected_gate_size) < expected_gate_size * 0.15:  # 15% 오차 허용
                    explanation.update({
                        'explained': True,
                        'reason': f'복제 비율 {self.mirror_ratio_multiplier}x 적용 시 예상 크기와 유사',
                        'confidence': 'medium'
                    })
                    return explanation
            
            # 3. 렌더 중단으로 인한 부분 누락 설명
            size_diff_percent = abs(order_size - current_size) / max(order_size, current_size) * 100
            if size_diff_percent > 20:  # 20% 이상 차이
                explanation.update({
                    'explained': True,
                    'reason': f'렌더 중단으로 인한 부분 누락 가능성 ({size_diff_percent:.1f}% 차이)',
                    'confidence': 'medium'
                })
                return explanation
            
            return explanation
            
        except Exception as e:
            self.logger.error(f"크기 차이 설명 실패: {e}")
            return {
                'explained': False,
                'reason': f'설명 실패: {str(e)}',
                'confidence': 'low'
            }

    async def _update_partial_tracking_on_fill(self, order_id: str, mirror_info: Dict):
        """🔥🔥🔥 주문 체결 시 부분 진입/익절 추적 업데이트"""
        try:
            original_order = mirror_info.get('bitget_order', {})
            is_close_order = mirror_info.get('is_close_order', False)
            order_size = float(original_order.get('size', 0))
            order_side = original_order.get('side', original_order.get('tradeSide', '')).lower()
            
            if is_close_order:
                # 부분 익절 추적 업데이트
                await self._update_partial_exit_tracking_on_fill(order_id, original_order, mirror_info)
                self.daily_stats['partial_exit_matches'] += 1
            else:
                # 부분 진입 추적 업데이트
                await self._update_partial_entry_tracking_on_fill(order_id, original_order, mirror_info)
                self.daily_stats['partial_entry_matches'] += 1
            
            self.logger.info(f"📊 부분 추적 업데이트 완료: {order_id} ({'익절' if is_close_order else '진입'})")
            
        except Exception as e:
            self.logger.error(f"부분 추적 업데이트 실패: {order_id} - {e}")

    async def _update_partial_exit_tracking_on_fill(self, order_id: str, original_order: Dict, mirror_info: Dict):
        """🔥🔥🔥 부분 익절 추적 업데이트"""
        try:
            order_size = float(original_order.get('size', 0))
            trigger_price = None
            
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if original_order.get(price_field):
                    trigger_price = float(original_order.get(price_field))
                    break
            
            # 관련 포지션 키 찾기
            side = original_order.get('side', original_order.get('tradeSide', '')).lower()
            position_side = 'long' if 'short' not in side else 'short'
            
            # 부분 익절 기록 추가
            exit_record = {
                'order_id': order_id,
                'size': order_size,
                'price': trigger_price,
                'filled_at': datetime.now().isoformat(),
                'mirror_info': mirror_info
            }
            
            # 해당 포지션의 익절 기록에 추가
            pos_key = f"{position_side}_exit"
            if pos_key not in self.position_exit_history:
                self.position_exit_history[pos_key] = []
            
            self.position_exit_history[pos_key].append(exit_record)
            
            # 최근 10개 기록만 유지
            if len(self.position_exit_history[pos_key]) > 10:
                self.position_exit_history[pos_key] = self.position_exit_history[pos_key][-10:]
            
            self.logger.info(f"📊 부분 익절 기록 추가: {pos_key} - 크기: {order_size}, 가격: {trigger_price}")
            
        except Exception as e:
            self.logger.error(f"부분 익절 추적 업데이트 실패: {e}")

    async def _update_partial_entry_tracking_on_fill(self, order_id: str, original_order: Dict, mirror_info: Dict):
        """🔥🔥🔥 부분 진입 추적 업데이트"""
        try:
            order_size = float(original_order.get('size', 0))
            trigger_price = None
            
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if original_order.get(price_field):
                    trigger_price = float(original_order.get(price_field))
                    break
            
            # 포지션 방향 결정
            side = original_order.get('side', original_order.get('tradeSide', '')).lower()
            position_side = 'long' if 'buy' in side or 'long' in side else 'short'
            
            # 부분 진입 기록 추가
            entry_record = {
                'order_id': order_id,
                'size': order_size,
                'price': trigger_price,
                'filled_at': datetime.now().isoformat(),
                'mirror_info': mirror_info
            }
            
            # 해당 포지션의 진입 기록에 추가
            pos_key = f"{position_side}_entry"
            if pos_key not in self.position_entry_history:
                self.position_entry_history[pos_key] = []
            
            self.position_entry_history[pos_key].append(entry_record)
            
            # 최근 10개 기록만 유지
            if len(self.position_entry_history[pos_key]) > 10:
                self.position_entry_history[pos_key] = self.position_entry_history[pos_key][-10:]
            
            self.logger.info(f"📊 부분 진입 기록 추가: {pos_key} - 크기: {order_size}, 가격: {trigger_price}")
            
        except Exception as e:
            self.logger.error(f"부분 진입 추적 업데이트 실패: {e}")

    async def _update_partial_exit_tracking(self, order: Dict, close_details: Dict):
        """🔥🔥🔥 새로운 클로즈 주문에 대한 부분 익절 추적 설정"""
        try:
            order_id = order.get('orderId', order.get('planOrderId', ''))
            position_side = close_details['position_side']
            order_size = float(order.get('size', 0))
            
            # 부분 익절 추적 키
            pos_key = f"{position_side}_exit_tracking"
            
            if pos_key not in self.partial_exit_tracking:
                self.partial_exit_tracking[pos_key] = {
                    'orders': [],
                    'total_size': 0.0,
                    'created_at': datetime.now().isoformat()
                }
            
            # 새로운 클로즈 주문 추가
            self.partial_exit_tracking[pos_key]['orders'].append({
                'order_id': order_id,
                'order_data': order,
                'size': order_size,
                'close_details': close_details,
                'added_at': datetime.now().isoformat()
            })
            
            self.partial_exit_tracking[pos_key]['total_size'] += order_size
            
            self.logger.info(f"📊 부분 익절 추적 설정: {pos_key} - 누적 크기: {self.partial_exit_tracking[pos_key]['total_size']}")
            
        except Exception as e:
            self.logger.error(f"부분 익절 추적 설정 실패: {e}")

    async def _process_perfect_mirror_order_with_ratio(self, bitget_order: Dict, close_details: Dict, ratio_multiplier: float) -> str:
        """🔥🔥🔥 복제 비율이 적용된 완벽한 미러링 주문 처리 - 기존 로직 유지"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            is_close_order = close_details['is_close_order']
            order_direction = close_details['order_direction']
            position_side = close_details['position_side']
            
            self.logger.info(f"🎯 복제 비율 적용 미러링 시작: {order_id} (비율: {ratio_multiplier}x)")
            self.logger.info(f"   클로즈 주문: {is_close_order}")
            self.logger.info(f"   주문 방향: {order_direction} (포지션: {position_side})")
            
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
            
            # 🔥🔥🔥 복제 비율 적용된 마진 비율 계산
            margin_ratio_result = await self.utils.calculate_dynamic_margin_ratio_with_multiplier(
                size, trigger_price, bitget_order, ratio_multiplier
            )
            
            if not margin_ratio_result['success']:
                self.logger.error(f"❌ 마진 비율 계산 실패: {order_id} - {margin_ratio_result.get('error')}")
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
            
            # 🔥🔥🔥 복제 비율 적용된 게이트 마진 계산
            gate_margin = gate_total_equity * margin_ratio
            
            if gate_margin > gate_available:
                gate_margin = gate_available * 0.95
            
            if gate_margin < self.MIN_MARGIN:
                self.logger.error(f"❌ 게이트 마진 부족: {gate_margin} < {self.MIN_MARGIN}")
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
                self.logger.error(f"❌ Gate.io 주문 생성 실패: {order_id}")
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
                'ratio_multiplier': ratio_multiplier  # 🔥🔥🔥 복제 비율 기록
            }
            
            self.daily_stats['plan_order_mirrors'] += 1
            
            # TP/SL 통계 업데이트
            if mirror_result.get('has_tp_sl', False):
                self.daily_stats['tp_sl_success'] += 1
            elif mirror_result.get('tp_price') or mirror_result.get('sl_price'):
                self.daily_stats['tp_sl_failed'] += 1
            
            # 🔥🔥🔥 성공 메시지 - 복제 비율 정보 포함
            order_type = "클로즈 주문" if mirror_result.get('is_close_order') else "예약 주문"
            perfect_status = "완벽" if mirror_result.get('perfect_mirror') else "부분"
            forced_status = " (강제 미러링)" if mirror_result.get('forced_close') else ""
            ratio_status = f" (복제비율: {ratio_multiplier}x)" if ratio_multiplier != 1.0 else ""
            
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
                f"💰 마진 비율 복제 (x{ratio_multiplier}):\n"
                f"마진 비율: {margin_ratio*100:.2f}%\n"
                f"게이트 투입 마진: ${gate_margin:,.2f}\n"
                f"레버리지: {bitget_leverage}x{tp_sl_info}"
            )
            
            # 🔥🔥🔥 반환값 개선 - close_order_forced는 실제로 성공임
            if mirror_result.get('forced_close'):
                return "close_order_forced"  # 이것도 성공 케이스
            elif mirror_result.get('perfect_mirror'):
                return "perfect_success"
            else:
                return "partial_success"
            
        except Exception as e:
            self.logger.error(f"복제 비율 적용 미러링 주문 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'plan_order_id': bitget_order.get('orderId', bitget_order.get('planOrderId', 'unknown'))
            })
            return "failed"

    # === 기존 메서드들 유지 (수정 없음) ===
    
    async def _update_recently_filled_orders(self):
        """🔥🔥🔥 최근 체결된 주문 기록 업데이트"""
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
        """🔥🔥🔥 주문이 체결되었는지 확인"""
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

    async def _cleanup_mirror_records_for_filled_order(self, bitget_order_id: str, gate_order_id: str):
        """체결된 주문의 미러링 기록 정리 (게이트 주문은 건드리지 않음)"""
        try:
            self.logger.info(f"🎯 체결된 주문의 미러링 기록 정리: {bitget_order_id} → {gate_order_id}")
            
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
            
            self.logger.info(f"✅ 체결된 주문의 미러링 기록 정리 완료: {bitget_order_id}")
            
        except Exception as e:
            self.logger.error(f"체결된 주문 미러링 기록 정리 실패: {e}")

    # === 나머지 기존 메서드들은 그대로 유지 ===
    # (코드가 너무 길어지므로 핵심 수정 부분만 포함하고 나머지는 기존과 동일)
    
    async def _get_all_current_plan_orders_enhanced(self) -> List[Dict]:
        """🔥🔥🔥 모든 현재 예약 주문 조회 - 클로즈 주문 강화"""
        try:
            all_orders = []
            
            # 1. 비트겟에서 모든 예약 주문 조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            
            # 2. 일반 예약 주문 추가
            general_orders = plan_data.get('plan_orders', [])
            if general_orders:
                all_orders.extend(general_orders)
                self.logger.debug(f"일반 예약 주문 {len(general_orders)}개 추가")
                
                # 🔥🔥🔥 클로즈 주문 특별 체크
                for order in general_orders:
                    side = order.get('side', order.get('tradeSide', '')).lower()
                    reduce_only = order.get('reduceOnly', False)
                    if 'close' in side or reduce_only:
                        self.logger.info(f"🔴 일반 예약 주문 중 클로즈 주문 발견: {order.get('orderId', order.get('planOrderId'))}")
            
            # 3. TP/SL 주문 추가 (모든 TP/SL은 기본적으로 클로즈 성격)
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            if tp_sl_orders:
                all_orders.extend(tp_sl_orders)
                self.logger.debug(f"TP/SL 주문 {len(tp_sl_orders)}개 추가 (모두 클로즈 성격)")
                
                # 🔥🔥🔥 TP/SL 주문은 모두 클로즈 주문으로 간주
                for order in tp_sl_orders:
                    order_id = order.get('orderId', order.get('planOrderId'))
                    self.logger.info(f"🎯 TP/SL 클로즈 주문 발견: {order_id}")
            
            self.logger.debug(f"총 {len(all_orders)}개의 현재 예약 주문 조회 완료 (클로즈 주문 포함)")
            return all_orders
            
        except Exception as e:
            self.logger.error(f"현재 예약 주문 조회 실패: {e}")
            return []

    async def _is_order_recently_processed_improved(self, order_id: str, order: Dict) -> bool:
        """🔥🔥🔥 개선된 최근 처리 주문 확인 - 완화된 버전"""
        try:
            # 1. 기본 시간 기반 확인 (단축된 시간)
            if order_id in self.recently_processed_orders:
                time_diff = (datetime.now() - self.recently_processed_orders[order_id]).total_seconds()
                if time_diff < self.order_deduplication_window:
                    self.logger.debug(f"최근 처리된 주문: {order_id} ({time_diff:.1f}초 전)")
                    return True
                else:
                    del self.recently_processed_orders[order_id]
            
            # 2. 정확한 해시 기반 확인만 사용
            order_hash = await self._generate_primary_order_hash(order)
            if order_hash and order_hash in self.processed_order_hashes:
                self.logger.debug(f"해시 기반 중복 감지: {order_hash}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"개선된 최근 처리 확인 실패: {e}")
            return False

    async def _is_duplicate_order_improved(self, bitget_order: Dict) -> bool:
        """🔥🔥🔥 개선된 중복 주문 확인 - 더 정확한 판단"""
        try:
            # 1. 트리거 가격 추출
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price <= 0:
                return False
            
            # 2. 정확한 가격 매칭 확인 (±5달러 허용)
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
            
            # 3. 기존 게이트 주문과의 정확한 해시 매칭만 확인
            order_hash = await self._generate_primary_order_hash(bitget_order)
            if order_hash and order_hash in self.gate_existing_order_hashes:
                self.logger.debug(f"게이트 기존 주문과 해시 중복: {order_hash}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"개선된 중복 주문 확인 실패: {e}")
            return False

    async def _generate_primary_order_hash(self, order: Dict) -> str:
        """🔥🔥🔥 주 해시 생성 - 정확한 매칭용"""
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
                # 정확한 해시: 계약_트리거가격_절대크기
                return f"{self.GATE_CONTRACT}_{trigger_price:.2f}_{abs_size}"
            else:
                # 크기가 없으면 가격 기반 해시
                return f"{self.GATE_CONTRACT}_price_{trigger_price:.2f}"
            
        except Exception as e:
            self.logger.error(f"주 해시 생성 실패: {e}")
            return ""

    async def _record_order_processing_hash(self, order_id: str, order: Dict):
        """주문 처리 해시 기록 - 단순화된 버전"""
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
                
            # 🔥🔥🔥 취소 재시도 카운터도 정리 (1시간 후 만료)
            expired_cancel_retries = []
            for order_id in list(self.cancel_retry_count.keys()):
                if order_id not in self.mirrored_plan_orders:
                    expired_cancel_retries.append(order_id)
            
            for order_id in expired_cancel_retries:
                del self.cancel_retry_count[order_id]
                
            # 🔥🔥🔥 체결된 주문 기록도 정리
            expired_filled_orders = []
            for order_id, timestamp in self.filled_order_timestamps.items():
                if (current_time - timestamp).total_seconds() > self.filled_order_check_window:
                    expired_filled_orders.append(order_id)
            
            for order_id in expired_filled_orders:
                self.recently_filled_order_ids.discard(order_id)
                del self.filled_order_timestamps[order_id]
                
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

    async def _force_remove_mirror_record(self, bitget_order_id: str, gate_order_id: str):
        """강제로 미러링 기록 제거"""
        try:
            self.logger.warning(f"🗑️ 강제 미러링 기록 제거: {bitget_order_id} → {gate_order_id}")
            
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
                f"🗑️ 강제 미러링 기록 정리\n"
                f"비트겟 ID: {bitget_order_id}\n"
                f"게이트 ID: {gate_order_id}\n"
                f"사유: 최대 재시도 횟수 초과\n"
                f"⚠️ 게이트에서 수동 확인을 권장합니다"
            )
            
        except Exception as e:
            self.logger.error(f"강제 미러링 기록 제거 실패: {e}")

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

    # ===
