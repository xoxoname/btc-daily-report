import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import json

from mirror_trading_utils import MirrorTradingUtils, PositionInfo, MirrorResult

logger = logging.getLogger(__name__)

class MirrorPositionManager:
    """포지션 및 주문 관리 클래스 - 클로징 주문 처리 강화 + 정확한 복제 주문 개수 표시"""
    
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
        
        # 🔥🔥🔥 클로징 주문 처리 강화 설정
        self.CLOSE_ORDER_DETECTION_ENHANCED = True
        self.CLOSE_ORDER_POSITION_MATCHING = True
        self.CLOSE_ORDER_SIZE_VALIDATION = True
        
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
            'market_order_alerts': 0,  # 시장가 체결 알림 통계
            'close_order_enhanced_success': 0,  # 강화된 클로징 주문 성공
            'errors': []
        }
        
        self.logger.info("🔥🔥🔥 미러 포지션 매니저 초기화 완료 - 강화된 클로즈 주문 처리")

    async def initialize_clients(self):
        """클라이언트 초기화"""
        try:
            # 미러링 유틸리티 초기화
            self.utils = MirrorTradingUtils(self.config, self.bitget, self.gate)
            
            self.logger.info("✅ 미러링 클라이언트 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"클라이언트 초기화 실패: {e}")
            raise

    async def record_startup_state(self):
        """시작 시 상태 기록"""
        try:
            self.logger.info("📊 시작 시 상태 기록 중...")
            
            # 비트겟 기존 포지션 기록
            await self._record_startup_positions()
            
            # 게이트 기존 포지션 기록 
            await self._record_existing_gate_positions()
            
            # 기존 예약 주문 기록
            await self._record_startup_plan_orders()
            
            # 🔥🔥🔥 시작 시 예약 주문 복제 - 조건 완화
            await self._mirror_startup_plan_orders()
            
            self.logger.info("✅ 시작 시 상태 기록 완료")
            
        except Exception as e:
            self.logger.error(f"시작 시 상태 기록 실패: {e}")
            raise

    async def _record_startup_positions(self):
        """시작 시 비트겟 포지션 기록"""
        try:
            positions = await self.bitget.get_positions(self.SYMBOL)
            
            for pos in positions:
                total = float(pos.get('total', 0))
                if total > 0:
                    position_id = f"{self.SYMBOL}_{pos.get('holdSide', 'unknown')}"
                    self.startup_positions.add(position_id)
                    
                    self.logger.info(f"📍 시작 시 포지션 기록: {position_id} (크기: {total})")
            
            self.logger.info(f"📍 시작 시 비트겟 포지션: {len(self.startup_positions)}개")
            
        except Exception as e:
            self.logger.error(f"시작 시 포지션 기록 실패: {e}")

    async def _record_existing_gate_positions(self):
        """게이트 기존 포지션 기록"""
        try:
            gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
            
            self.existing_gate_positions = {
                'has_long': False,
                'has_short': False,
                'long_size': 0,
                'short_size': 0
            }
            
            for pos in gate_positions:
                size = int(pos.get('size', 0))
                if size != 0:
                    position_id = f"{self.GATE_CONTRACT}_{size}"
                    self.startup_gate_positions.add(position_id)
                    
                    if size > 0:
                        self.existing_gate_positions['has_long'] = True
                        self.existing_gate_positions['long_size'] = size
                        self.logger.info(f"📍 기존 게이트 롱 포지션: {size}")
                    else:
                        self.existing_gate_positions['has_short'] = True
                        self.existing_gate_positions['short_size'] = abs(size)
                        self.logger.info(f"📍 기존 게이트 숏 포지션: {abs(size)}")
            
            if self.existing_gate_positions['has_long'] or self.existing_gate_positions['has_short']:
                self.render_restart_detected = True
                self.logger.info("🔄 렌더 재구동 감지됨 (기존 게이트 포지션 존재)")
            
        except Exception as e:
            self.logger.error(f"기존 게이트 포지션 기록 실패: {e}")

    async def _record_startup_plan_orders(self):
        """시작 시 예약 주문 기록"""
        try:
            # 비트겟 예약 주문 조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            bitget_plan_orders = plan_data.get('plan_orders', [])
            bitget_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_startup_orders = bitget_plan_orders + bitget_tp_sl_orders
            
            for order in all_startup_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.startup_plan_orders.add(order_id)
                    
                    order_type = order.get('orderType', order.get('planType', 'unknown'))
                    side = order.get('side', order.get('tradeSide', 'unknown'))
                    trigger_price = order.get('triggerPrice', order.get('executePrice', 0))
                    
                    self.logger.debug(f"📍 시작 시 예약 주문: {order_id} - {order_type} - {side} - ${trigger_price}")
            
            self.logger.info(f"📍 시작 시 예약 주문: {len(self.startup_plan_orders)}개")
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 기록 실패: {e}")

    async def check_and_mirror_positions(self):
        """포지션 체크 및 미러링"""
        try:
            current_positions = await self.bitget.get_positions(self.SYMBOL)
            
            for pos in current_positions:
                total = float(pos.get('total', 0))
                if total > 0:
                    position_id = f"{self.SYMBOL}_{pos.get('holdSide', 'unknown')}"
                    
                    # 시작 시 존재했던 포지션은 제외
                    if position_id not in self.startup_positions:
                        # 새로운 포지션 발견
                        if position_id not in self.mirrored_positions:
                            result = await self._mirror_new_position(pos)
                            if result.success:
                                self.daily_stats['position_mirrors'] += 1
                                self.daily_stats['successful_mirrors'] += 1
                            else:
                                self.daily_stats['failed_mirrors'] += 1
                                self.failed_mirrors.append(result)
            
        except Exception as e:
            self.logger.error(f"포지션 체크 및 미러링 실패: {e}")

    async def check_and_mirror_plan_orders(self):
        """🔥🔥🔥 예약 주문 체크 및 미러링 - 강화된 클로즈 주문 처리"""
        try:
            # 1. 비트겟 예약 주문 조회 (더 적극적으로)
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            bitget_plan_orders = plan_data.get('plan_orders', [])
            bitget_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_orders = bitget_plan_orders + bitget_tp_sl_orders
            current_order_ids = set()
            new_orders_count = 0
            new_close_orders_count = 0
            perfect_mirrors = 0
            enhanced_close_success = 0
            
            # 2. 현재 주문 ID 수집 및 처리
            for order in all_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if not order_id:
                    continue
                
                current_order_ids.add(order_id)
                
                # 🔥🔥🔥 스타트업 주문 제외 조건 완화 (10분으로 단축)
                if order_id in self.startup_plan_orders:
                    order_time = order.get('cTime', 0)
                    current_time = datetime.now().timestamp() * 1000
                    
                    # 10분 이상 된 주문은 스타트업 제외에서 해제 (기존 1시간에서 대폭 단축)
                    if (current_time - order_time) <= 600000:  # 10분 이내만 제외
                        continue
                    else:
                        self.logger.info(f"🕐 10분 이상 된 스타트업 주문 포함: {order_id}")
                
                # 이미 처리된 주문은 스킵
                if order_id in self.processed_plan_orders:
                    continue
                
                # 새로운 예약 주문 처리
                try:
                    # 🔥🔥🔥 강화된 클로즈 주문 상세 분석
                    close_details = await self._enhanced_close_order_detection(order)
                    is_close_order = close_details['is_close_order']
                    
                    # 클로즈 주문인 경우 현재 포지션 상태 확인
                    if is_close_order:
                        position_check_result = await self._enhanced_close_order_validity_check(order, close_details)
                        if position_check_result == "skip_no_position":
                            self.logger.warning(f"⏭️ 클로즈 주문이지만 해당 포지션 없음, 스킵: {order_id}")
                            self.processed_plan_orders.add(order_id)
                            self.daily_stats['close_order_skipped'] += 1
                            continue
                    
                    # 🔥🔥🔥 클로즈 주문과 오픈 주문을 구분하여 처리
                    if is_close_order:
                        result = await self._process_enhanced_close_order(order, close_details)
                        if result in ["perfect_success", "partial_success"]:
                            enhanced_close_success += 1
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
                    order_hash = self._generate_order_hash(order)
                    self.processed_order_hashes.add(order_hash)
                    self.order_hash_timestamps[order_hash] = datetime.now()
                    
                except Exception as e:
                    self.logger.error(f"예약 주문 처리 중 오류 {order_id}: {e}")
                    continue
            
            # 3. 취소된 주문 감지
            cancelled_orders = self.last_plan_order_ids - current_order_ids
            if cancelled_orders:
                await self._handle_cancelled_plan_orders(cancelled_orders)
            
            self.last_plan_order_ids = current_order_ids
            
            # 4. 포지션 없음 시 클로즈 주문 자동 정리
            await self._check_and_cleanup_close_orders_if_no_position()
            
            # 5. 통계 업데이트
            self.daily_stats['close_order_enhanced_success'] += enhanced_close_success
            
            # 6. 성과 로깅
            if new_orders_count > 0:
                self.logger.info(f"🔄 예약 주문 처리 완료: 신규 {new_orders_count}개 (클로즈 {new_close_orders_count}개, 완벽 {perfect_mirrors}개)")
            
        except Exception as e:
            self.logger.error(f"예약 주문 체크 및 미러링 실패: {e}")

    async def _enhanced_close_order_detection(self, order: Dict) -> Dict:
        """🔥🔥🔥 강화된 클로즈 주문 감지"""
        try:
            side = order.get('side', order.get('tradeSide', '')).lower()
            reduce_only = order.get('reduceOnly', False)
            order_type = order.get('orderType', order.get('planType', ''))
            
            # 클로즈 주문 여부 기본 판단
            is_close_order = (
                'close' in side or 
                reduce_only is True or 
                reduce_only == 'true' or
                str(reduce_only).lower() == 'true'
            )
            
            # 클로즈 타입 세분화
            close_type = 'none'
            order_direction = side
            position_side = 'long'  # 기본값
            
            if is_close_order:
                if 'close_long' in side or side == 'sell':
                    close_type = 'close_long'
                    order_direction = 'sell'
                    position_side = 'long'
                elif 'close_short' in side or side == 'buy':
                    close_type = 'close_short'
                    order_direction = 'buy'
                    position_side = 'short'
                else:
                    # reduce_only가 True인 경우
                    if side == 'sell':
                        close_type = 'close_long'
                        order_direction = 'sell'
                        position_side = 'long'
                    elif side == 'buy':
                        close_type = 'close_short'
                        order_direction = 'buy'
                        position_side = 'short'
            
            confidence = 'high' if 'close' in side else ('medium' if reduce_only else 'low')
            
            result = {
                'is_close_order': is_close_order,
                'close_type': close_type,
                'order_direction': order_direction,
                'position_side': position_side,
                'original_side': side,
                'reduce_only': reduce_only,
                'confidence': confidence
            }
            
            self.logger.debug(f"🔍 클로즈 주문 감지 결과: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 감지 실패: {e}")
            return {
                'is_close_order': False,
                'close_type': 'detection_error',
                'order_direction': 'buy',
                'position_side': 'long',
                'original_side': side,
                'reduce_only': False,
                'confidence': 'low'
            }

    async def _enhanced_close_order_validity_check(self, order: Dict, close_details: Dict) -> str:
        """🔥🔥🔥 강화된 클로즈 주문 유효성 검사"""
        try:
            if not self.CLOSE_ORDER_POSITION_MATCHING:
                return "proceed"  # 검사 비활성화된 경우 진행
            
            order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
            position_side = close_details.get('position_side', '')
            
            # 현재 게이트 포지션 조회
            gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
            
            if not gate_positions:
                self.logger.warning(f"🔍 게이트에 포지션이 전혀 없음 - 클로즈 주문 스킵: {order_id}")
                return "skip_no_position"
            
            position = gate_positions[0]
            current_gate_size = int(position.get('size', 0))
            
            if current_gate_size == 0:
                self.logger.warning(f"🔍 게이트 포지션 크기가 0 - 클로즈 주문 스킵: {order_id}")
                return "skip_no_position"
            
            # 현재 포지션 방향 확인
            current_position_side = 'long' if current_gate_size > 0 else 'short'
            current_position_abs_size = abs(current_gate_size)
            
            # 포지션 방향 매칭 검사
            if position_side and current_position_side != position_side:
                self.logger.warning(f"🔍 포지션 방향 불일치: 현재={current_position_side}, 예상={position_side}")
                self.logger.info(f"🔄 현재 포지션({current_position_side})에 맞게 클로즈 주문 조정하여 진행")
            
            # 포지션 크기 검증
            if self.CLOSE_ORDER_SIZE_VALIDATION:
                if current_position_abs_size < 10:  # 매우 작은 포지션 (10 계약 미만)
                    self.logger.warning(f"🔍 매우 작은 포지션이지만 클로즈 진행: {current_position_abs_size}")
            
            self.logger.info(f"✅ 강화된 클로즈 주문 유효성 확인: 포지션={current_position_side}, 크기={current_position_abs_size}")
            return "proceed"
            
        except Exception as e:
            self.logger.error(f"강화된 클로즈 주문 유효성 확인 실패: {e}")
            return "proceed"  # 오류 시에도 진행

    async def _process_enhanced_close_order(self, bitget_order: Dict, close_details: Dict) -> str:
        """🔥🔥🔥 강화된 클로즈 주문 처리"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            position_side = close_details['position_side']
            close_type = close_details['close_type']
            
            self.logger.info(f"🎯 강화된 클로즈 주문 처리: {order_id} (타입: {close_type}, 포지션: {position_side})")
            
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
            
            # 현재 포지션 방향 및 크기 확인
            current_position_side = 'long' if current_gate_size > 0 else 'short'
            current_position_abs_size = abs(current_gate_size)
            
            # 포지션 방향 불일치 시 조정
            if current_position_side != position_side:
                self.logger.warning(f"⚠️ 포지션 방향 불일치: 현재={current_position_side}, 예상={position_side}")
                actual_position_side = current_position_side
                actual_gate_size = current_position_abs_size
            else:
                actual_position_side = position_side
                actual_gate_size = current_position_abs_size
            
            # 트리거 가격 추출
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price == 0:
                self.logger.error(f"클로즈 주문 트리거 가격을 찾을 수 없음: {order_id}")
                return "failed"
            
            # 클로즈 주문 방향 결정
            if actual_position_side == 'long':
                gate_side = 'sell'  # 롱 포지션 클로즈는 매도
            else:
                gate_side = 'buy'   # 숏 포지션 클로즈는 매수
            
            # 게이트에 클로즈 주문 생성
            gate_order_data = {
                'symbol': self.GATE_CONTRACT,
                'side': gate_side,
                'size': actual_gate_size,
                'trigger_price': trigger_price,
                'reduce_only': True,  # 클로즈 주문은 항상 reduce_only
                'order_type': 'limit'
            }
            
            # 🔥🔥🔥 TP/SL 정보 추출
            tp_price, sl_price = await self.utils.extract_tp_sl_from_bitget_order(bitget_order)
            
            # 게이트 주문 생성
            mirror_result = await self.gate_mirror.create_price_triggered_order_with_tp_sl(
                gate_order_data, tp_price, sl_price
            )
            
            if mirror_result.get('success', False):
                gate_order_id = mirror_result.get('order_id', '')
                
                # 미러링 기록 저장
                self.mirrored_plan_orders[order_id] = {
                    'gate_order_id': gate_order_id,
                    'bitget_order': bitget_order,
                    'gate_order': gate_order_data,
                    'timestamp': datetime.now().isoformat(),
                    'side': gate_side,
                    'size': actual_gate_size,
                    'trigger_price': trigger_price,
                    'has_tp_sl': mirror_result.get('has_tp_sl', False),
                    'tp_price': mirror_result.get('tp_price'),
                    'sl_price': mirror_result.get('sl_price'),
                    'actual_tp_price': mirror_result.get('actual_tp_price'),
                    'actual_sl_price': mirror_result.get('actual_sl_price'),
                    'is_close_order': True,
                    'reduce_only': True,
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
                order_type = "클로즈 주문"
                perfect_status = "완벽" if mirror_result.get('perfect_mirror') else "부분"
                
                close_info = f"\n🔴 클로즈 주문: {gate_side} (포지션: {actual_position_side})"
                
                tp_sl_info = ""
                if mirror_result.get('has_tp_sl'):
                    tp_sl_info = f"\n\n🎯 TP/SL 완벽 미러링:"
                    if mirror_result.get('actual_tp_price'):
                        tp_sl_info += f"\n✅ TP: ${mirror_result['actual_tp_price']}"
                    if mirror_result.get('actual_sl_price'):
                        tp_sl_info += f"\n✅ SL: ${mirror_result['actual_sl_price']}"
                elif mirror_result.get('tp_price') or mirror_result.get('sl_price'):
                    tp_sl_info = f"\n\n⚠️ TP/SL 부분 미러링:"
                    if mirror_result.get('tp_price'):
                        tp_sl_info += f"\n❌ TP 실패: ${mirror_result['tp_price']}"
                    if mirror_result.get('sl_price'):
                        tp_sl_info += f"\n❌ SL 실패: ${mirror_result['sl_price']}"
                
                await self.telegram.send_message(
                    f"🔄 {perfect_status} {order_type} 미러링 성공\n\n"
                    f"📊 비트겟 → 게이트 복제\n"
                    f"🆔 주문 ID: {order_id[:8]}...→{gate_order_id[:8]}...\n"
                    f"📈 방향: {gate_side.upper()}\n"
                    f"📊 크기: {actual_gate_size:,} 계약\n"
                    f"💰 트리거: ${trigger_price:,.2f}{close_info}\n"
                    f"🛡️ 슬리피지 보호: 0.05% 제한{tp_sl_info}"
                )
                
                return "perfect_success" if mirror_result.get('perfect_mirror') else "partial_success"
            else:
                error_msg = mirror_result.get('error', '알 수 없는 오류')
                self.logger.error(f"강화된 클로즈 주문 생성 실패: {error_msg}")
                return "failed"
            
        except Exception as e:
            self.logger.error(f"강화된 클로즈 주문 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'plan_order_id': bitget_order.get('orderId', bitget_order.get('planOrderId', 'unknown')),
                'type': 'enhanced_close_order_processing'
            })
            return "failed"

    async def _process_perfect_mirror_order(self, bitget_order: Dict) -> str:
        """완벽한 미러링 주문 처리 (오픈 주문용)"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            
            # 클로즈 주문 상세 분석
            close_details = await self._enhanced_close_order_detection(bitget_order)
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
                self.logger.error(f"주문 트리거 가격을 찾을 수 없음: {order_id}")
                return "failed"
            
            # 사이즈 및 마진 계산
            size = float(bitget_order.get('size', 0))
            if size == 0:
                self.logger.error(f"주문 크기가 0: {order_id}")
                return "failed"
            
            # 마진 비율 계산
            margin_calc = await self.utils.calculate_dynamic_margin_ratio(size, trigger_price, bitget_order)
            if not margin_calc['success']:
                self.logger.error(f"마진 계산 실패: {margin_calc['error']}")
                return "failed"
            
            gate_size = margin_calc['gate_size']
            margin_ratio = margin_calc['margin_ratio']
            
            # 게이트 주문 데이터 준비
            gate_order_data = {
                'symbol': self.GATE_CONTRACT,
                'side': order_direction,
                'size': gate_size,
                'trigger_price': trigger_price,
                'reduce_only': is_close_order,
                'order_type': 'limit'
            }
            
            # 🔥🔥🔥 TP/SL 정보 추출
            tp_price, sl_price = await self.utils.extract_tp_sl_from_bitget_order(bitget_order)
            
            # 게이트 주문 생성
            mirror_result = await self.gate_mirror.create_price_triggered_order_with_tp_sl(
                gate_order_data, tp_price, sl_price
            )
            
            if mirror_result.get('success', False):
                gate_order_id = mirror_result.get('order_id', '')
                
                # 미러링 기록 저장
                self.mirrored_plan_orders[order_id] = {
                    'gate_order_id': gate_order_id,
                    'bitget_order': bitget_order,
                    'gate_order': gate_order_data,
                    'timestamp': datetime.now().isoformat(),
                    'side': order_direction,
                    'size': gate_size,
                    'margin_ratio': margin_ratio,
                    'trigger_price': trigger_price,
                    'has_tp_sl': mirror_result.get('has_tp_sl', False),
                    'tp_price': mirror_result.get('tp_price'),
                    'sl_price': mirror_result.get('sl_price'),
                    'actual_tp_price': mirror_result.get('actual_tp_price'),
                    'actual_sl_price': mirror_result.get('actual_sl_price'),
                    'is_close_order': is_close_order,
                    'reduce_only': is_close_order,
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
                order_type = "클로즈 주문" if is_close_order else "예약 주문"
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
                    tp_sl_info = f"\n\n⚠️ TP/SL 부분 미러링:"
                    if mirror_result.get('tp_price'):
                        tp_sl_info += f"\n❌ TP 실패: ${mirror_result['tp_price']}"
                    if mirror_result.get('sl_price'):
                        tp_sl_info += f"\n❌ SL 실패: ${mirror_result['sl_price']}"
                
                await self.telegram.send_message(
                    f"🔄 {perfect_status} {order_type} 미러링 성공\n\n"
                    f"📊 비트겟 → 게이트 복제\n"
                    f"🆔 주문 ID: {order_id[:8]}...→{gate_order_id[:8]}...\n"
                    f"📈 방향: {order_direction.upper()}\n"
                    f"📊 크기: {gate_size:,} 계약 ({margin_ratio:.1f}% 비율)\n"
                    f"💰 트리거: ${trigger_price:,.2f}{close_info}\n"
                    f"🛡️ 슬리피지 보호: 0.05% 제한{tp_sl_info}"
                )
                
                return "perfect_success" if mirror_result.get('perfect_mirror') else "partial_success"
            else:
                error_msg = mirror_result.get('error', '알 수 없는 오류')
                self.logger.error(f"예약 주문 생성 실패: {error_msg}")
                return "failed"
            
        except Exception as e:
            self.logger.error(f"완벽한 미러링 주문 처리 중 오류: {e}")
            return "failed"

    async def _handle_cancelled_plan_orders(self, cancelled_order_ids: Set[str]):
        """취소된 예약 주문 처리"""
        try:
            for order_id in cancelled_order_ids:
                if order_id in self.mirrored_plan_orders:
                    mirror_info = self.mirrored_plan_orders[order_id]
                    gate_order_id = mirror_info.get('gate_order_id')
                    
                    if gate_order_id:
                        # 게이트에서도 주문 취소
                        cancel_result = await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                        if cancel_result.get('success', False):
                            self.logger.info(f"🗑️ 취소된 예약 주문 동기화: {order_id} → {gate_order_id}")
                            self.daily_stats['plan_order_cancels'] += 1
                    
                    # 미러링 기록에서 제거
                    del self.mirrored_plan_orders[order_id]
                
                # 처리된 주문에서도 제거
                if order_id in self.processed_plan_orders:
                    self.processed_plan_orders.remove(order_id)
            
            if cancelled_order_ids:
                self.logger.info(f"🗑️ 취소된 예약 주문 처리 완료: {len(cancelled_order_ids)}개")
            
        except Exception as e:
            self.logger.error(f"취소된 예약 주문 처리 실패: {e}")

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
                for order in close_orders_to_delete:
                    try:
                        order_id = order.get('id')
                        if order_id:
                            delete_result = await self.gate_mirror.cancel_price_triggered_order(order_id)
                            if delete_result.get('success', False):
                                deleted_count += 1
                                self.logger.info(f"🗑️ 클로즈 주문 삭제: {order_id}")
                    except Exception as e:
                        self.logger.error(f"클로즈 주문 삭제 실패: {e}")
                
                self.daily_stats['auto_close_order_cleanups'] += deleted_count
                
                if deleted_count > 0:
                    await self.telegram.send_message(
                        f"🗑️ 자동 클로즈 주문 정리\n\n"
                        f"포지션이 없어 {deleted_count}개의 클로즈 주문을 자동 삭제했습니다.\n"
                        f"🎯 시스템이 불필요한 주문을 자동으로 정리했습니다. ✨"
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

    async def _mirror_startup_plan_orders(self):
        """🔥🔥🔥 시작 시 예약 주문 복제 - 조건 완화"""
        try:
            if self.startup_plan_orders_processed:
                return
            
            self.logger.info("🔄 시작 시 예약 주문 복제 시작 (조건 완화)")
            
            # 현재 비트겟 예약 주문 재조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            bitget_plan_orders = plan_data.get('plan_orders', [])
            bitget_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_orders = bitget_plan_orders + bitget_tp_sl_orders
            
            mirrored_count = 0
            skipped_count = 0
            failed_count = 0
            
            for order in all_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if not order_id:
                    continue
                
                # 🔥🔥🔥 시작 시 복제 조건 완화 - 5분 이상 된 주문만 복제
                order_time = order.get('cTime', 0)
                current_time = datetime.now().timestamp() * 1000
                
                # 5분 이상 된 주문만 복제 (기존 1시간에서 대폭 단축)
                if (current_time - order_time) <= 300000:  # 5분 이내 주문은 신규로 간주
                    skipped_count += 1
                    continue
                
                try:
                    # 🔥🔥🔥 강화된 클로즈 주문 감지
                    close_details = await self._enhanced_close_order_detection(order)
                    
                    if close_details['is_close_order']:
                        result = await self._process_enhanced_close_order(order, close_details)
                    else:
                        result = await self._process_perfect_mirror_order(order)
                    
                    if result in ["perfect_success", "partial_success"]:
                        mirrored_count += 1
                        self.daily_stats['startup_plan_mirrors'] += 1
                        self.processed_plan_orders.add(order_id)
                    else:
                        failed_count += 1
                
                except Exception as e:
                    self.logger.error(f"시작 시 예약 주문 복제 실패 {order_id}: {e}")
                    failed_count += 1
            
            # 성과 리포트
            total_startup_orders = len(self.startup_plan_orders)
            if mirrored_count > 0:
                await self.telegram.send_message(
                    f"🔄 시작 시 예약 주문 복제 완료\n\n"
                    f"📊 총 시작 시 주문: {total_startup_orders}개\n"
                    f"✅ 복제 성공: {mirrored_count}개\n"
                    f"⏭️ 신규 주문 스킵: {skipped_count}개 (5분 이내)\n"
                    f"❌ 복제 실패: {failed_count}개\n\n"
                    f"🎯 조건 완화: 5분 이상 된 주문만 복제\n"
                    f"🎯 강화된 클로징 주문 처리 적용\n"
                    f"🔰 포지션 크기 매칭 기능 적용됨\n"
                    f"🛡️ 슬리피지 보호: 0.05% 제한\n"
                    f"🔥 시세 차이와 무관하게 즉시 처리됨"
                )
            
            self.startup_plan_orders_processed = True
            self.logger.info(f"시작 시 예약 주문 복제 완료: 성공 {mirrored_count}개, 스킵 {skipped_count}개, 실패 {failed_count}개")
            self.logger.info(f"현재 복제된 예약 주문 개수: {len(self.mirrored_plan_orders)}개")
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 복제 실패: {e}")
            self.startup_plan_orders_processed = True

    def _generate_order_hash(self, order: Dict) -> str:
        """주문 해시 생성 (중복 방지용)"""
        try:
            trigger_price = order.get('triggerPrice', order.get('executePrice', 0))
            side = order.get('side', order.get('tradeSide', 'unknown'))
            size = order.get('size', 0)
            
            hash_string = f"{self.SYMBOL}_{side}_{trigger_price}_{size}"
            return hash(hash_string)
            
        except Exception as e:
            self.logger.error(f"주문 해시 생성 실패: {e}")
            return str(hash(str(order)))

    async def _mirror_new_position(self, bitget_pos: Dict) -> MirrorResult:
        """새로운 포지션 미러링"""
        try:
            # 포지션 정보 추출
            side = bitget_pos.get('holdSide', '').lower()
            total = float(bitget_pos.get('total', 0))
            
            if total <= 0:
                return MirrorResult(
                    success=False,
                    action="skip_zero_position",
                    bitget_data=bitget_pos,
                    error="포지션 크기가 0"
                )
            
            # 마진 비율 계산
            current_price = await self._get_current_price()
            margin_calc = await self.utils.calculate_dynamic_margin_ratio(total, current_price, bitget_pos)
            
            if not margin_calc['success']:
                return MirrorResult(
                    success=False,
                    action="margin_calculation_failed",
                    bitget_data=bitget_pos,
                    error=margin_calc['error']
                )
            
            gate_size = margin_calc['gate_size']
            
            # 게이트에 포지션 생성
            gate_result = await self.gate_mirror.create_position(
                symbol=self.GATE_CONTRACT,
                side=side,
                size=gate_size
            )
            
            if gate_result.get('success', False):
                position_id = f"{self.SYMBOL}_{side}"
                self.mirrored_positions[position_id] = PositionInfo(
                    symbol=self.SYMBOL,
                    side=side,
                    size=total,
                    entry_price=current_price,
                    margin=margin_calc['margin_amount'],
                    leverage=margin_calc['leverage'],
                    mode='cross'
                )
                
                return MirrorResult(
                    success=True,
                    action="position_mirrored",
                    bitget_data=bitget_pos,
                    gate_data=gate_result
                )
            else:
                return MirrorResult(
                    success=False,
                    action="gate_position_creation_failed",
                    bitget_data=bitget_pos,
                    error=gate_result.get('error', '알 수 없는 오류')
                )
            
        except Exception as e:
            return MirrorResult(
                success=False,
                action="mirror_position_error",
                bitget_data=bitget_pos,
                error=str(e)
            )

    async def _get_current_price(self) -> float:
        """현재 가격 조회"""
        try:
            ticker = await self.bitget.get_ticker(self.SYMBOL)
            return float(ticker.get('last', 0))
        except:
            return 0.0

    async def stop(self):
        """포지션 매니저 중지"""
        try:
            self.logger.info("포지션 매니저 중지 중...")
            
            # 해시 정리
            self.processed_order_hashes.clear()
            self.order_hash_timestamps.clear()
            
            self.logger.info("포지션 매니저 중지 완료")
            
        except Exception as e:
            self.logger.error(f"포지션 매니저 중지 중 오류: {e}")
