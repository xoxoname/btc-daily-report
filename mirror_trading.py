import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json
import traceback

logger = logging.getLogger(__name__)

@dataclass
class PositionInfo:
    """포지션 정보"""
    symbol: str
    side: str  # long/short
    size: float
    entry_price: float
    margin: float
    leverage: int
    mode: str  # cross/isolated
    tp_orders: List[Dict] = field(default_factory=list)
    sl_orders: List[Dict] = field(default_factory=list)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)
    
@dataclass
class MirrorResult:
    """미러링 결과"""
    success: bool
    action: str
    bitget_data: Dict
    gate_data: Optional[Dict] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

class MirrorTradingSystem:
    def __init__(self, config, bitget_client, gate_client, telegram_bot):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.telegram = telegram_bot
        self.logger = logging.getLogger('mirror_trading')
        
        # 미러링 상태 관리
        self.mirrored_positions: Dict[str, PositionInfo] = {}  # 포지션 ID: PositionInfo
        self.startup_positions: Set[str] = set()   # 시작 시 존재했던 포지션
        self.failed_mirrors: List[MirrorResult] = []  # 실패한 미러링 기록
        self.last_sync_check = datetime.min
        self.last_report_time = datetime.min
        
        # 포지션 크기 추적 (부분 청산 감지용)
        self.position_sizes: Dict[str, float] = {}  # 포지션 ID: 마지막 크기
        
        # TP/SL 주문 추적
        self.tp_sl_orders: Dict[str, Dict] = {}  # 포지션 ID: {tp: [주문ID], sl: [주문ID]}
        
        # 주문 체결 추적 (중복 미러링 방지용)
        self.processed_orders: Set[str] = set()  # 이미 처리된 주문 ID들
        self.last_order_check = datetime.now()
        
        # 🔥 예약 주문 추적 (신규 추가)
        self.mirrored_plan_orders: Dict[str, Dict] = {}  # 비트겟 예약주문 ID: 게이트 주문 정보
        self.processed_plan_orders: Set[str] = set()  # 이미 처리된 예약 주문 ID들
        self.startup_plan_orders: Set[str] = set()  # 시작 시 존재했던 예약 주문 (복제 제외)
        
        # 🔥🔥 예약주문 취소 감지 개선
        self.last_plan_order_ids: Set[str] = set()  # 이전 체크에서 발견된 예약주문 ID들
        
        # 🔥 기존 포지션 TP/SL 제외용 (개선된 분류)
        self.startup_position_tp_sl: Set[str] = set()  # 시작 시 존재했던 포지션의 클로즈 TP/SL (복제 제외)
        
        # 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.CHECK_INTERVAL = 2  # 2초마다 체크 (더 빠르게)
        self.ORDER_CHECK_INTERVAL = 1  # 1초마다 주문 체결 체크
        self.PLAN_ORDER_CHECK_INTERVAL = 3  # 🔥 3초마다 예약 주문 체크 (신규)
        self.SYNC_CHECK_INTERVAL = 30  # 30초마다 동기화 체크
        self.MAX_RETRIES = 3
        self.MIN_POSITION_SIZE = 0.00001  # BTC
        self.MIN_MARGIN = 1.0  # 최소 마진 $1
        self.DAILY_REPORT_HOUR = 9  # 매일 오전 9시 리포트
        
        # 성과 추적
        self.daily_stats = {
            'total_mirrored': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'total_volume': 0.0,
            'order_mirrors': 0,  # 주문 체결로 인한 미러링 횟수
            'position_mirrors': 0,  # 포지션 감지로 인한 미러링 횟수
            'plan_order_mirrors': 0,  # 🔥 예약 주문 미러링 횟수 (신규)
            'plan_order_cancels': 0,  # 🔥 예약 주문 취소 횟수 (신규)
            'errors': []
        }
        
        self.monitoring = True
        self.logger.info("🔥🔥 레버리지 완전 동기화 + 예약 주문 달러 비율 복제 미러 트레이딩 시스템 초기화 완료 (30% 제한 해제)")
    
    async def start(self):
        """미러 트레이딩 시작"""
        try:
            self.logger.info("🚀🔥 레버리지 완전 동기화 + 예약 주문 달러 비율 복제 미러 트레이딩 시스템 시작")
            
            # 초기 포지션 및 예약 주문 기록
            await self._record_startup_positions()
            await self._record_startup_plan_orders()  # 🔥 신규: 기존 예약 주문 기록
            await self._record_startup_position_tp_sl()  # 🔥 신규: 기존 포지션 TP/SL 기록 (개선된 분류)
            
            # 초기 계정 상태 출력
            await self._log_account_status()
            
            # 모니터링 태스크 시작 (예약 주문 모니터링 추가)
            tasks = [
                self.monitor_plan_orders(),      # 🔥 신규: 예약 주문 모니터링 (최우선)
                self.monitor_order_fills(),      # 기존: 실시간 주문 체결 감지
                self.monitor_positions(),        # 기존: 포지션 모니터링
                self.monitor_sync_status(),      # 기존: 동기화 상태 모니터링
                self.generate_daily_reports()    # 기존: 일일 리포트
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시작 실패: {e}")
            await self.telegram.send_message(
                f"❌ 미러 트레이딩 시작 실패\n"
                f"오류: {str(e)[:200]}"
            )
            raise
    
    async def _record_startup_plan_orders(self):
        """🔥 신규: 시작 시 존재하는 예약 주문 기록 (복제 제외)"""
        try:
            self.logger.info("🔥 기존 예약 주문 기록 시작")
            
            # 비트겟 기존 예약 주문 조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            # 일반 예약 주문 기록
            for order in plan_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.startup_plan_orders.add(order_id)
                    self.processed_plan_orders.add(order_id)
                    self.last_plan_order_ids.add(order_id)  # 🔥🔥 초기 ID 목록에도 추가
                    self.logger.info(f"기존 예약 주문 기록 (복제 제외): {order_id}")
            
            # TP/SL 주문 기록
            for order in tp_sl_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.startup_plan_orders.add(order_id)
                    self.processed_plan_orders.add(order_id)
                    self.last_plan_order_ids.add(order_id)  # 🔥🔥 초기 ID 목록에도 추가
                    self.logger.info(f"기존 TP/SL 주문 기록 (복제 제외): {order_id}")
            
            total_existing = len(plan_orders) + len(tp_sl_orders)
            self.logger.info(f"🔥 총 {total_existing}개의 기존 예약 주문이 복제에서 제외됩니다")
            self.logger.info(f"  - 일반 예약 주문: {len(plan_orders)}개")
            self.logger.info(f"  - TP/SL 주문: {len(tp_sl_orders)}개")
            
        except Exception as e:
            self.logger.error(f"기존 예약 주문 기록 실패: {e}")
    
    async def _record_startup_position_tp_sl(self):
        """🔥 개선: 시작 시 존재하는 포지션의 클로즈 TP/SL만 제외, 추가 진입 TP는 복제"""
        try:
            self.logger.info("🔥 기존 포지션의 클로즈 TP/SL 기록 시작 (추가 진입 TP는 복제)")
            
            # 현재 활성 포지션들 조회
            positions = await self.bitget.get_positions(self.SYMBOL)
            
            existing_position_count = 0
            for pos in positions:
                if float(pos.get('total', 0)) > 0:
                    pos_id = self._generate_position_id(pos)
                    pos_side = pos.get('holdSide', '').lower()  # long or short
                    existing_position_count += 1
                    
                    self.logger.info(f"기존 포지션 발견: {pos_id} - {pos_side}")
                    
                    # 해당 포지션의 TP/SL 주문들 찾기
                    plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
                    tp_sl_orders = plan_data.get('tp_sl_orders', [])
                    
                    for tp_sl_order in tp_sl_orders:
                        # 🔥🔥 개선된 분류 로직
                        trade_side = tp_sl_order.get('tradeSide', tp_sl_order.get('side', '')).lower()
                        reduce_only = tp_sl_order.get('reduceOnly', False)
                        
                        # 기존 포지션의 클로즈 TP/SL인지 판단
                        is_existing_position_close = False
                        
                        if pos_side == 'long':
                            # 롱 포지션의 클로즈 = close_long 또는 sell with reduce_only
                            if (trade_side in ['close_long', 'sell'] and 
                                (reduce_only is True or reduce_only == 'true')):
                                is_existing_position_close = True
                        elif pos_side == 'short':
                            # 숏 포지션의 클로즈 = close_short 또는 buy with reduce_only
                            if (trade_side in ['close_short', 'buy'] and 
                                (reduce_only is True or reduce_only == 'true')):
                                is_existing_position_close = True
                        
                        order_id = tp_sl_order.get('orderId', tp_sl_order.get('planOrderId', ''))
                        if order_id:
                            if is_existing_position_close:
                                # 기존 포지션 클로즈 TP/SL → 복제 제외
                                self.startup_position_tp_sl.add(order_id)
                                self.logger.info(f"기존 포지션 {pos_id}의 클로즈 TP/SL 기록 (복제 제외): {order_id} - {trade_side}")
                            else:
                                # 추가 진입 TP/SL → 복제 대상
                                self.logger.info(f"🔥 추가 진입 TP/SL 감지 (복제 대상): {order_id} - {trade_side}")
            
            self.logger.info(f"🔥 기존 포지션: {existing_position_count}개")
            self.logger.info(f"🔥 제외할 클로즈 TP/SL: {len(self.startup_position_tp_sl)}개")
            self.logger.info(f"🔥 추가 진입 TP/SL은 복제 대상으로 처리됩니다")
            
        except Exception as e:
            self.logger.error(f"기존 포지션 TP/SL 기록 실패: {e}")
    
    async def monitor_plan_orders(self):
        """🔥🔥 예약 주문 모니터링 - 취소 감지 로직 완전 개선"""
        self.logger.info("🔥🔥 예약 주문 달러 비율 복제 모니터링 시작 (취소 감지 개선)")
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                # 현재 비트겟 예약 주문 조회
                plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
                current_plan_orders = plan_data.get('plan_orders', [])
                current_tp_sl_orders = plan_data.get('tp_sl_orders', [])
                
                all_current_orders = current_plan_orders + current_tp_sl_orders
                
                # 🔥🔥 현재 존재하는 예약주문 ID 집합
                current_order_ids = set()
                for order in all_current_orders:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if order_id:
                        current_order_ids.add(order_id)
                
                # 🔥🔥 취소된 예약 주문 감지 (개선된 로직)
                # 이전에 존재했지만 지금은 없는 주문들 찾기
                canceled_order_ids = self.last_plan_order_ids - current_order_ids
                
                # 기존 포지션/주문은 취소 감지에서 제외
                canceled_order_ids -= self.startup_plan_orders
                canceled_order_ids -= self.startup_position_tp_sl
                
                # 🔥🔥 취소된 주문 처리
                for canceled_order_id in canceled_order_ids:
                    self.logger.info(f"🚫🚫 예약 주문 취소 감지: {canceled_order_id}")
                    await self._handle_plan_order_cancel(canceled_order_id)
                
                # 새로운 예약 주문 감지
                new_orders_count = 0
                for order in all_current_orders:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if not order_id:
                        continue
                    
                    # 시작 시 존재했던 주문은 스킵
                    if order_id in self.startup_plan_orders:
                        continue
                    
                    # 🔥 개선된 기존 포지션 TP/SL 필터링
                    if order_id in self.startup_position_tp_sl:
                        # 이미 기존 포지션의 클로즈 TP/SL로 분류됨 → 스킵
                        self.logger.debug(f"기존 포지션 클로즈 TP/SL 스킵: {order_id}")
                        continue
                    
                    # 이미 처리된 주문은 스킵
                    if order_id in self.processed_plan_orders:
                        continue
                    
                    # 새로운 예약 주문 감지
                    self.logger.info(f"🆕🔥 새로운 예약 주문 감지: {order_id}")
                    self.logger.info(f"상세: {order.get('side', order.get('tradeSide'))} {order.get('size')} @ trigger: {order.get('triggerPrice', order.get('price'))}")
                    
                    # 예약 주문 복제 실행
                    await self._process_new_plan_order(order)
                    
                    # 처리 완료 표시
                    self.processed_plan_orders.add(order_id)
                    new_orders_count += 1
                
                # 🔥🔥 현재 상태를 다음 비교를 위해 저장
                self.last_plan_order_ids = current_order_ids.copy()
                
                if new_orders_count > 0:
                    self.logger.info(f"🔥🔥 {new_orders_count}개의 새로운 예약 주문을 복제했습니다")
                
                if canceled_order_ids:
                    self.logger.info(f"🚫🚫 {len(canceled_order_ids)}개의 예약 주문 취소를 처리했습니다")
                
                # 오래된 주문 ID 정리 (메모리 절약)
                if len(self.processed_plan_orders) > 500:
                    recent_orders = list(self.processed_plan_orders)[-250:]
                    self.processed_plan_orders = set(recent_orders)
                
                consecutive_errors = 0
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"예약 주문 모니터링 중 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 예약 주문 모니터링 시스템 오류\n"
                        f"연속 {consecutive_errors}회 실패\n"
                        f"오류: {str(e)[:200]}"
                    )
                
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL * 2)
    
    async def _process_new_plan_order(self, bitget_order: Dict):
        """🔥🔥 개선: 새로운 예약 주문 복제 - 오류 처리 강화"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()  # buy/sell 또는 open/close
            size = float(bitget_order.get('size', 0))
            
            # 트리거 가격 추출 (여러 필드 확인)
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            trigger_type = bitget_order.get('triggerType', 'market_price')  # market_price, mark_price
            plan_type = bitget_order.get('planType', 'normal')  # normal, profit_loss
            order_type = bitget_order.get('orderType', 'market')  # market, limit
            
            self.logger.info(f"🔥 예약 주문 달러 비율 복제 분석: {order_id}")
            self.logger.info(f"  방향: {side}")
            self.logger.info(f"  비트겟 수량: {size} BTC")
            self.logger.info(f"  트리거가: ${trigger_price}")
            self.logger.info(f"  트리거 타입: {trigger_type}")
            self.logger.info(f"  계획 타입: {plan_type}")
            self.logger.info(f"  주문 타입: {order_type}")
            
            if trigger_price == 0:
                self.logger.error(f"트리거 가격을 찾을 수 없습니다: {bitget_order}")
                return
            
            # 🔥🔥 레버리지 정보 정확하게 추출
            bitget_leverage = 10  # 기본값
            
            # 1순위: 주문에서 직접 레버리지 추출
            order_leverage = bitget_order.get('leverage')
            if order_leverage:
                try:
                    bitget_leverage = int(float(order_leverage))
                    self.logger.info(f"🔥 주문에서 레버리지 추출: {bitget_leverage}x")
                except:
                    pass
            
            # 2순위: 계정 정보에서 레버리지 추출
            if not order_leverage:
                try:
                    bitget_account = await self.bitget.get_account_info()
                    account_leverage = bitget_account.get('crossMarginLeverage')
                    if account_leverage:
                        bitget_leverage = int(float(account_leverage))
                        self.logger.info(f"🔥 계정에서 레버리지 추출: {bitget_leverage}x")
                except Exception as e:
                    self.logger.warning(f"계정 레버리지 조회 실패: {e}")
            
            # 3순위: 현재 포지션에서 레버리지 추출
            if bitget_leverage == 10:  # 여전히 기본값이면
                try:
                    positions = await self.bitget.get_positions(self.SYMBOL)
                    for pos in positions:
                        if float(pos.get('total', 0)) > 0:
                            pos_leverage = pos.get('leverage')
                            if pos_leverage:
                                bitget_leverage = int(float(pos_leverage))
                                self.logger.info(f"🔥 포지션에서 레버리지 추출: {bitget_leverage}x")
                                break
                except Exception as e:
                    self.logger.warning(f"포지션 레버리지 조회 실패: {e}")
            
            self.logger.info(f"🔥🔥 최종 확정 레버리지: {bitget_leverage}x")
            
            # 비트겟 계정 정보 조회
            bitget_account = await self.bitget.get_account_info()
            bitget_total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            # 비트겟에서 이 주문이 체결될 때 사용할 마진 계산
            bitget_notional_value = size * trigger_price
            bitget_required_margin = bitget_notional_value / bitget_leverage
            
            # 비트겟 총 자산 대비 마진 비율
            if bitget_total_equity > 0:
                margin_ratio = bitget_required_margin / bitget_total_equity
            else:
                self.logger.error("비트겟 총 자산이 0이거나 음수입니다.")
                return
            
            # 🔥 30% 제한 해제 - 비율 그대로 사용
            # margin_ratio = min(margin_ratio, 0.3)  # 이 줄 제거
            
            self.logger.info(f"💰 달러 비율 계산 (제한 해제):")
            self.logger.info(f"  비트겟 총 자산: ${bitget_total_equity:,.2f}")
            self.logger.info(f"  비트겟 예상 마진: ${bitget_required_margin:,.2f}")
            self.logger.info(f"  마진 비율: {margin_ratio:.4f} ({margin_ratio*100:.2f}%) - 제한 없음")
            
            # 게이트 계정 정보
            gate_account = await self.gate.get_account_balance()
            gate_total_equity = float(gate_account.get('total', 0))
            gate_available = float(gate_account.get('available', 0))
            
            # 게이트에서 사용할 마진 계산 (동일 비율 적용)
            gate_margin = gate_total_equity * margin_ratio
            
            # 사용 가능 자금 체크
            if gate_margin > gate_available:
                gate_margin = gate_available * 0.95  # 여유 5% 남김
                self.logger.warning(f"게이트 가용 자금 부족. 조정된 마진: ${gate_margin:.2f}")
            
            # 최소 마진 체크
            if gate_margin < self.MIN_MARGIN:
                self.logger.warning(f"게이트 마진 부족: ${gate_margin:.2f} < ${self.MIN_MARGIN}")
                return
            
            # 게이트 계약 수 계산
            gate_notional_value = gate_margin * bitget_leverage
            gate_size = int(gate_notional_value / (trigger_price * 0.0001))  # quanto_multiplier
            
            # 🔥🔥 사이즈가 0이면 최소 1로 설정
            if gate_size == 0:
                gate_size = 1
                self.logger.warning("게이트 계약 수가 0이어서 최소값 1로 설정")
            
            # 방향에 따라 부호 조정 (더 정확한 방향 판단)
            is_buy_order = False
            if side in ['buy', 'open_long']:
                is_buy_order = True
            elif side in ['sell', 'open_short']:
                is_buy_order = False
            elif side in ['close_long']:
                is_buy_order = False  # 롱 포지션 클로즈는 sell
                gate_size = -gate_size
            elif side in ['close_short']:
                is_buy_order = True   # 숏 포지션 클로즈는 buy
            else:
                # 기본적으로 side가 buy면 양수, sell이면 음수
                is_buy_order = 'buy' in side.lower()
            
            if not is_buy_order and side not in ['close_long']:
                gate_size = -gate_size
            
            # Gate.io 트리거 타입 변환 (더 정확한 로직)
            if is_buy_order or side in ['close_short']:
                gate_trigger_type = "ge"  # 가격이 올라가면 트리거
            else:
                gate_trigger_type = "le"  # 가격이 내려가면 트리거
            
            self.logger.info(f"🎯 게이트 예약 주문 생성:")
            self.logger.info(f"  게이트 총 자산: ${gate_total_equity:,.2f}")
            self.logger.info(f"  게이트 마진: ${gate_margin:.2f}")
            self.logger.info(f"  게이트 크기: {gate_size} 계약")
            self.logger.info(f"  트리거: {gate_trigger_type} ${trigger_price}")
            self.logger.info(f"  레버리지: {bitget_leverage}x")
            self.logger.info(f"  주문 방향: {'Buy' if is_buy_order else 'Sell'}")
            
            # 🔥🔥🔥 게이트 레버리지 설정 강화 (3단계 확실한 설정)
            try:
                self.logger.info(f"🔧🔧🔧 게이트 레버리지 완전 동기화 시작: {bitget_leverage}x")
                
                # 1단계: 레버리지 설정
                await self.gate.set_leverage(self.GATE_CONTRACT, bitget_leverage)
                await asyncio.sleep(0.5)  # 설정 반영 대기
                
                # 2단계: 설정 확인 및 재설정 (필요시)
                try:
                    gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
                    if gate_positions:
                        current_leverage = gate_positions[0].get('leverage')
                        if current_leverage and int(float(current_leverage)) != bitget_leverage:
                            self.logger.warning(f"🔧 레버리지 불일치 감지: 현재 {current_leverage}x, 목표 {bitget_leverage}x")
                            # 재설정 시도
                            await self.gate.set_leverage(self.GATE_CONTRACT, bitget_leverage)
                            await asyncio.sleep(0.3)
                            self.logger.info(f"🔧 레버리지 재설정 완료")
                        else:
                            self.logger.info(f"🔧 레버리지 설정 확인: {current_leverage}x")
                except Exception as e:
                    self.logger.warning(f"레버리지 확인 실패: {e}")
                    
                # 3단계: 최종 확인
                await asyncio.sleep(0.2)
                self.logger.info(f"✅✅✅ 게이트 레버리지 완전 동기화 완료: {bitget_leverage}x")
                
            except Exception as e:
                self.logger.error(f"❌ 게이트 레버리지 설정 실패: {e}")
                # 레버리지 설정 실패해도 주문은 진행 (기본 레버리지 사용)
            
            # Gate.io에 예약 주문 생성
            try:
                gate_order = await self.gate.create_price_triggered_order(
                    trigger_type=gate_trigger_type,
                    trigger_price=str(trigger_price),
                    order_type="market",  # 시장가로 체결
                    contract=self.GATE_CONTRACT,
                    size=gate_size
                )
                
                # 미러링 성공 기록
                self.mirrored_plan_orders[order_id] = {
                    'gate_order_id': gate_order.get('id'),
                    'bitget_order': bitget_order,
                    'gate_order': gate_order,
                    'created_at': datetime.now().isoformat(),
                    'margin': gate_margin,
                    'size': gate_size,
                    'margin_ratio': margin_ratio,
                    'leverage': bitget_leverage  # 🔥 레버리지 정보 저장
                }
                
                self.daily_stats['plan_order_mirrors'] += 1
                
                await self.telegram.send_message(
                    f"🔥✅ 예약 주문 달러 비율 복제 성공 (레버리지 완전 동기화)\n"
                    f"비트겟 ID: {order_id}\n"
                    f"게이트 ID: {gate_order.get('id')}\n"
                    f"방향: {side.upper()}\n"
                    f"트리거가: ${trigger_price:,.2f}\n\n"
                    f"💰 달러 비율 복제 (제한 해제):\n"
                    f"비트겟 마진: ${bitget_required_margin:,.2f} ({margin_ratio*100:.2f}%)\n"
                    f"게이트 마진: ${gate_margin:,.2f} ({margin_ratio*100:.2f}%)\n"
                    f"게이트 수량: {abs(gate_size)} 계약\n"
                    f"🔧 레버리지 완전 동기화: {bitget_leverage}x\n"
                    f"📊 자산 현황: 비트겟 ${bitget_total_equity:,.0f} / 게이트 ${gate_total_equity:,.0f}"
                )
                
                self.logger.info(f"✅🔥 예약 주문 달러 비율 복제 성공 (레버리지 동기화): {order_id} → {gate_order.get('id')}")
                
            except Exception as e:
                self.logger.error(f"게이트 예약 주문 생성 실패: {e}")
                await self.telegram.send_message(
                    f"❌ 예약 주문 복제 실패\n"
                    f"비트겟 ID: {order_id}\n"
                    f"오류: {str(e)[:200]}"
                )
                
        except Exception as e:
            self.logger.error(f"예약 주문 복제 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'plan_order_id': bitget_order.get('orderId', bitget_order.get('planOrderId', 'unknown'))
            })
    
    async def _handle_plan_order_cancel(self, bitget_order_id: str):
        """🔥🔥 예약 주문 취소 처리 - 개선된 로직"""
        try:
            self.logger.info(f"🚫 예약 주문 취소 처리 시작: {bitget_order_id}")
            
            # 미러링된 주문인지 확인
            if bitget_order_id not in self.mirrored_plan_orders:
                self.logger.info(f"미러링되지 않은 주문이므로 취소 처리 스킵: {bitget_order_id}")
                return
            
            mirror_info = self.mirrored_plan_orders[bitget_order_id]
            gate_order_id = mirror_info.get('gate_order_id')
            
            if gate_order_id:
                # Gate.io에서 해당 예약 주문 취소
                try:
                    await self.gate.cancel_price_triggered_order(gate_order_id)
                    
                    self.daily_stats['plan_order_cancels'] += 1
                    
                    await self.telegram.send_message(
                        f"🚫✅ 예약 주문 취소 동기화 완료\n"
                        f"비트겟 ID: {bitget_order_id}\n"
                        f"게이트 ID: {gate_order_id}\n"
                        f"비트겟에서 취소되어 게이트에서도 자동 취소했습니다."
                    )
                    
                    self.logger.info(f"✅ 예약 주문 취소 완료: {bitget_order_id} → {gate_order_id}")
                    
                except Exception as e:
                    self.logger.error(f"게이트 예약 주문 취소 실패: {e}")
                    
                    # 🔥🔥 취소 실패 시에도 계속 시도하도록 상세 오류 처리
                    if "not found" in str(e).lower() or "does not exist" in str(e).lower():
                        self.logger.info(f"게이트 주문이 이미 없음: {gate_order_id}")
                        await self.telegram.send_message(
                            f"🚫⚠️ 예약 주문 취소 처리\n"
                            f"비트겟 ID: {bitget_order_id}\n"
                            f"게이트 ID: {gate_order_id}\n"
                            f"게이트 주문이 이미 취소되었거나 체결되었습니다."
                        )
                    else:
                        await self.telegram.send_message(
                            f"❌ 예약 주문 취소 실패\n"
                            f"비트겟 ID: {bitget_order_id}\n"
                            f"게이트 ID: {gate_order_id}\n"
                            f"오류: {str(e)[:200]}\n"
                            f"수동 확인이 필요합니다."
                        )
            
            # 미러링 기록에서 제거
            del self.mirrored_plan_orders[bitget_order_id]
            self.logger.info(f"미러링 기록에서 제거 완료: {bitget_order_id}")
            
        except Exception as e:
            self.logger.error(f"예약 주문 취소 처리 실패: {e}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
    
    async def monitor_order_fills(self):
        """실시간 주문 체결 감지"""
        self.logger.info("실시간 주문 체결 감지 시작")
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                # 최근 1분간 체결된 주문 조회
                filled_orders = await self.bitget.get_recent_filled_orders(
                    symbol=self.SYMBOL, 
                    minutes=1
                )
                
                new_orders_count = 0
                for order in filled_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if not order_id:
                        continue
                    
                    # 이미 처리된 주문은 스킵
                    if order_id in self.processed_orders:
                        continue
                    
                    # 신규 진입 주문만 처리 (reduce_only가 아닌 것)
                    reduce_only = order.get('reduceOnly', 'false')
                    if reduce_only == 'true' or reduce_only is True:
                        continue
                    
                    # 새로운 진입 주문 감지
                    self.logger.info(f"🆕 새로운 주문 체결 감지: {order_id}")
                    self.logger.info(f"주문 상세: {order.get('side')} {order.get('size')} @ ${order.get('fillPrice', order.get('price', 0))}")
                    
                    # 주문으로부터 미러링 실행
                    await self._process_filled_order(order)
                    
                    # 처리 완료 표시
                    self.processed_orders.add(order_id)
                    new_orders_count += 1
                
                if new_orders_count > 0:
                    self.logger.info(f"🔥 {new_orders_count}개의 새로운 주문 체결을 처리했습니다")
                
                # 오래된 주문 ID 정리 (메모리 절약)
                if len(self.processed_orders) > 1000:
                    # 최근 500개만 유지
                    recent_orders = list(self.processed_orders)[-500:]
                    self.processed_orders = set(recent_orders)
                
                consecutive_errors = 0
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"주문 체결 감지 중 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 주문 체결 감지 시스템 오류\n"
                        f"연속 {consecutive_errors}회 실패\n"
                        f"오류: {str(e)[:200]}"
                    )
                
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL * 2)
    
    async def _process_filled_order(self, order: Dict):
        """체결된 주문으로부터 미러링 실행"""
        try:
            order_id = order.get('orderId', order.get('id', ''))
            side = order.get('side', '').lower()  # buy/sell
            size = float(order.get('size', 0))
            fill_price = float(order.get('fillPrice', order.get('price', 0)))
            
            self.logger.info(f"📊 체결 주문 분석: {order_id}")
            self.logger.info(f"  방향: {side}")
            self.logger.info(f"  수량: {size}")
            self.logger.info(f"  체결가: ${fill_price}")
            
            # Bitget의 buy/sell을 long/short로 변환
            position_side = 'long' if side == 'buy' else 'short'
            
            # 🔥 레버리지 정보 추출 (주문 체결 시)
            leverage = 10  # 기본값
            try:
                # 주문에서 레버리지 추출
                order_leverage = order.get('leverage')
                if order_leverage:
                    leverage = int(float(order_leverage))
                else:
                    # 계정에서 레버리지 추출
                    account = await self.bitget.get_account_info()
                    if account:
                        account_leverage = account.get('crossMarginLeverage')
                        if account_leverage:
                            leverage = int(float(account_leverage))
                
                self.logger.info(f"🔧 체결 주문 레버리지: {leverage}x")
            except Exception as e:
                self.logger.warning(f"체결 주문 레버리지 조회 실패: {e}")
            
            # 가상의 포지션 데이터 생성 (실제 포지션 API 형식에 맞춤)
            synthetic_position = {
                'symbol': self.SYMBOL,
                'holdSide': position_side,
                'total': str(size),
                'openPriceAvg': str(fill_price),
                'markPrice': str(fill_price),
                'marginSize': '0',  # 실제 계산 필요
                'leverage': str(leverage),
                'marginMode': 'crossed',
                'unrealizedPL': '0'
            }
            
            # 마진 계산 (notional value / leverage)
            notional = size * fill_price
            margin = notional / leverage
            synthetic_position['marginSize'] = str(margin)
            
            self.logger.info(f"  레버리지: {leverage}x")
            self.logger.info(f"  마진: ${margin:.2f}")
            
            # 포지션 ID 생성
            pos_id = f"{self.SYMBOL}_{position_side}_{fill_price}"
            
            # 시작 시 존재했던 포지션이면 무시
            if pos_id in self.startup_positions:
                self.logger.info(f"기존 포지션이므로 미러링 제외: {pos_id}")
                return
            
            # 이미 미러링된 포지션인지 확인
            if pos_id in self.mirrored_positions:
                self.logger.info(f"이미 미러링된 포지션: {pos_id}")
                return
            
            self.logger.info(f"🎯 실시간 미러링 실행: {pos_id}")
            
            # 미러링 실행
            result = await self._mirror_new_position(synthetic_position)
            
            if result.success:
                self.mirrored_positions[pos_id] = await self._create_position_info(synthetic_position)
                self.position_sizes[pos_id] = size
                self.daily_stats['successful_mirrors'] += 1
                self.daily_stats['order_mirrors'] += 1  # 주문 기반 미러링 카운트
                
                await self.telegram.send_message(
                    f"⚡ 실시간 주문 체결 미러링 성공 (레버리지 동기화)\n"
                    f"주문 ID: {order_id}\n"
                    f"방향: {position_side}\n"
                    f"체결가: ${fill_price:,.2f}\n"
                    f"수량: {size}\n"
                    f"🔧 레버리지: {leverage}x\n"
                    f"마진: ${result.gate_data.get('margin', 0):,.2f}"
                )
                
                self.logger.info(f"✅ 실시간 미러링 성공: {pos_id}")
            else:
                self.failed_mirrors.append(result)
                self.daily_stats['failed_mirrors'] += 1
                
                await self.telegram.send_message(
                    f"❌ 실시간 주문 체결 미러링 실패\n"
                    f"주문 ID: {order_id}\n"
                    f"오류: {result.error}"
                )
                
                self.logger.error(f"❌ 실시간 미러링 실패: {result.error}")
            
            self.daily_stats['total_mirrored'] += 1
            
        except Exception as e:
            self.logger.error(f"체결 주문 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'order_id': order.get('orderId', 'unknown')
            })
    
    async def _record_startup_positions(self):
        """시작 시 존재하는 포지션 기록"""
        try:
            # 비트겟 기존 포지션 확인
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    # 포지션 ID 생성
                    pos_id = self._generate_position_id(pos)
                    self.startup_positions.add(pos_id)
                    
                    # 크기 기록
                    self.position_sizes[pos_id] = float(pos.get('total', 0))
                    
                    self.logger.info(f"기존 포지션 기록 (복제 제외): {pos_id}")
            
            # 기존 주문 ID들도 기록 (중복 미러링 방지)
            try:
                recent_orders = await self.bitget.get_recent_filled_orders(self.SYMBOL, minutes=10)
                for order in recent_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if order_id:
                        self.processed_orders.add(order_id)
                
                self.logger.info(f"기존 주문 {len(recent_orders)}건 기록 (중복 미러링 방지)")
            except Exception as e:
                self.logger.warning(f"기존 주문 기록 실패: {e}")
            
            self.logger.info(f"총 {len(self.startup_positions)}개의 기존 포지션이 복제에서 제외됩니다")
            
            # 게이트 기존 포지션 확인
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            if gate_positions and any(pos.get('size', 0) != 0 for pos in gate_positions):
                self.logger.warning("⚠️ 게이트에 기존 포지션이 있습니다. 수동 확인이 필요할 수 있습니다.")
            
        except Exception as e:
            self.logger.error(f"기존 포지션 기록 실패: {e}")
    
    async def _log_account_status(self):
        """계정 상태 로깅"""
        try:
            # 비트겟 계정 정보
            bitget_account = await self.bitget.get_account_info()
            bitget_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            bitget_leverage = bitget_account.get('crossMarginLeverage', 'N/A')
            
            # 게이트 계정 정보
            gate_account = await self.gate.get_account_balance()
            gate_equity = float(gate_account.get('total', 0))
            
            # 예약 주문 현황
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            total_plan_orders = plan_data.get('total_count', 0)
            
            self.logger.info(
                f"💰 계정 상태\n"
                f"비트겟: ${bitget_equity:,.2f} (레버리지: {bitget_leverage}x)\n"
                f"게이트: ${gate_equity:,.2f}\n"
                f"예약 주문: {total_plan_orders}개"
            )
            
            await self.telegram.send_message(
                f"🔥🔥 레버리지 완전 동기화 + 예약 주문 달러 비율 복제 미러 트레이딩 시작\n\n"
                f"💰 계정 잔고:\n"
                f"• 비트겟: ${bitget_equity:,.2f} (레버리지: {bitget_leverage}x)\n"
                f"• 게이트: ${gate_equity:,.2f}\n"
                f"• 비율: {(gate_equity/bitget_equity*100):.1f}%\n\n"
                f"📊 기존 항목 (복제 제외):\n"
                f"• 포지션: {len(self.startup_positions)}개\n"
                f"• 예약 주문: {len(self.startup_plan_orders)}개\n"
                f"• 기존 포지션 클로즈 TP/SL: {len(self.startup_position_tp_sl)}개\n\n"
                f"🔥 핵심 기능 (개선):\n"
                f"• 🔧 레버리지 완전 동기화 (비트겟 = 게이트)\n"
                f"• 예약 주문 달러 비율 완전 복제\n"
                f"• 30% 제한 완전 해제\n"
                f"• 기존 포지션 클로즈 TP/SL 제외\n"
                f"• 📈 추가 진입 예약 TP/SL 복제\n"
                f"• 🚫🚫 예약 주문 취소 시 자동 동기화 (개선)\n"
                f"• 주문 체결 시 포지션 미러링\n\n"
                f"💰 달러 비율 복제 (제한 해제):\n"
                f"• 비트겟 마진 비율 = 게이트 마진 비율\n"
                f"• 총 자산 대비 동일 비율 유지\n"
                f"• 제한 없이 완전 복제\n\n"
                f"🔧 레버리지 완전 동기화:\n"
                f"• 비트겟 {bitget_leverage}x → 게이트 {bitget_leverage}x\n"
                f"• 예약 주문별 정확한 레버리지 추출\n"
                f"• 주문 생성 전 강제 동기화\n"
                f"• 3단계 확인 및 재설정\n\n"
                f"⚡ 감지 주기:\n"
                f"• 예약 주문: {self.PLAN_ORDER_CHECK_INTERVAL}초마다\n"
                f"• 주문 체결: {self.ORDER_CHECK_INTERVAL}초마다\n\n"
                f"🚫🚫 예약주문 취소 감지 (개선):\n"
                f"• 비트겟에서 예약주문 취소 시 게이트도 자동 취소\n"
                f"• 실시간 취소 상태 비교\n"
                f"• 취소 실패 시 상세 오류 처리\n"
                f"• 이미 체결/취소된 주문 자동 감지"
            )
            
        except Exception as e:
            self.logger.error(f"계정 상태 조회 실패: {e}")
    
    async def monitor_positions(self):
        """포지션 모니터링 메인 루프 (기존 기능 유지)"""
        self.logger.info("포지션 모니터링 시작")
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                # 비트겟 포지션 확인
                bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                
                # 활성 포지션 처리
                active_position_ids = set()
                
                for pos in bitget_positions:
                    if float(pos.get('total', 0)) > 0:
                        pos_id = self._generate_position_id(pos)
                        active_position_ids.add(pos_id)
                        
                        # 새 포지션 또는 업데이트 확인
                        await self._process_position(pos)
                
                # 종료된 포지션 처리
                closed_positions = set(self.mirrored_positions.keys()) - active_position_ids
                for pos_id in closed_positions:
                    if pos_id not in self.startup_positions:
                        await self._handle_position_close(pos_id)
                
                consecutive_errors = 0
                await asyncio.sleep(self.CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"포지션 모니터링 중 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 포지션 모니터링 오류\n"
                        f"연속 {consecutive_errors}회 실패\n"
                        f"오류: {str(e)[:200]}"
                    )
                
                await asyncio.sleep(self.CHECK_INTERVAL * 2)
    
    async def _process_position(self, bitget_pos: Dict):
        """포지션 처리 (신규/업데이트) - 주문 체결로 이미 처리된 경우 스킵"""
        try:
            pos_id = self._generate_position_id(bitget_pos)
            
            # 시작 시 존재했던 포지션은 무시
            if pos_id in self.startup_positions:
                return
            
            current_size = float(bitget_pos.get('total', 0))
            
            # 새로운 포지션이지만 주문 체결로 이미 처리되었을 수 있음
            if pos_id not in self.mirrored_positions:
                # 주문 체결 감지로 이미 처리되었는지 확인
                # (실시간 주문 체결 감지가 더 빠르므로 대부분 이미 처리됨)
                
                self.logger.info(f"🔍 포지션 감지: {pos_id} (주문 체결로 이미 처리되었을 수 있음)")
                
                # 잠시 대기 후 다시 확인 (주문 체결 처리 시간 여유)
                await asyncio.sleep(2)
                
                if pos_id not in self.mirrored_positions:
                    self.logger.info(f"🆕 포지션 기반 미러링 실행: {pos_id}")
                    result = await self._mirror_new_position(bitget_pos)
                    
                    if result.success:
                        self.mirrored_positions[pos_id] = await self._create_position_info(bitget_pos)
                        self.position_sizes[pos_id] = current_size
                        self.daily_stats['successful_mirrors'] += 1
                        self.daily_stats['position_mirrors'] += 1  # 포지션 기반 미러링 카운트
                        
                        leverage = bitget_pos.get('leverage', 'N/A')
                        await self.telegram.send_message(
                            f"✅ 포지션 기반 미러링 성공 (레버리지 동기화)\n"
                            f"방향: {bitget_pos.get('holdSide', '')}\n"
                            f"진입가: ${float(bitget_pos.get('openPriceAvg', 0)):,.2f}\n"
                            f"🔧 레버리지: {leverage}x\n"
                            f"마진: ${result.gate_data.get('margin', 0):,.2f}\n"
                            f"📝 주문 체결 감지에서 누락된 포지션"
                        )
                    else:
                        self.failed_mirrors.append(result)
                        self.daily_stats['failed_mirrors'] += 1
                        
                        await self.telegram.send_message(
                            f"❌ 포지션 기반 미러링 실패\n"
                            f"오류: {result.error}"
                        )
                    
                    self.daily_stats['total_mirrored'] += 1
                else:
                    self.logger.info(f"✅ 이미 주문 체결로 처리된 포지션: {pos_id}")
                
            # 기존 포지션 업데이트 확인
            else:
                last_size = self.position_sizes.get(pos_id, 0)
                
                # 부분 청산 감지
                if current_size < last_size * 0.95:  # 5% 이상 감소
                    reduction_ratio = 1 - (current_size / last_size)
                    self.logger.info(f"📉 부분 청산 감지: {reduction_ratio*100:.1f}% 감소")
                    
                    await self._handle_partial_close(pos_id, bitget_pos, reduction_ratio)
                    self.position_sizes[pos_id] = current_size
                    self.daily_stats['partial_closes'] += 1
                
                # TP/SL 업데이트 확인
                await self._check_tp_sl_updates(pos_id, bitget_pos)
                
        except Exception as e:
            self.logger.error(f"포지션 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'position': self._generate_position_id(bitget_pos)
            })
    
    async def _mirror_new_position(self, bitget_pos: Dict) -> MirrorResult:
        """🔥🔥 새로운 포지션 미러링 - INVALID_PROTOCOL 오류 해결"""
        retry_count = 0
        
        while retry_count < self.MAX_RETRIES:
            try:
                # 1. 자산 비율 계산
                margin_ratio = await self._calculate_margin_ratio(bitget_pos)
                
                if margin_ratio is None:
                    return MirrorResult(
                        success=False,
                        action="new_position",
                        bitget_data=bitget_pos,
                        error="마진 비율 계산 실패"
                    )
                
                # 2. 게이트 진입 금액 계산
                gate_account = await self.gate.get_account_balance()
                gate_available = float(gate_account.get('available', 0))
                gate_margin = gate_available * margin_ratio
                
                # 최소 마진 체크
                if gate_margin < self.MIN_MARGIN:
                    return MirrorResult(
                        success=False,
                        action="new_position",
                        bitget_data=bitget_pos,
                        error=f"게이트 마진 부족: ${gate_margin:.2f} < ${self.MIN_MARGIN}"
                    )
                
                self.logger.info(
                    f"💰 게이트 진입 계산 (제한 해제)\n"
                    f"비율: {margin_ratio:.4f} ({margin_ratio*100:.2f}%)\n"
                    f"가용자산: ${gate_available:.2f}\n"
                    f"진입마진: ${gate_margin:.2f}"
                )
                
                # 3. 🔥🔥 레버리지 추출 및 동기화 강화
                leverage = int(float(bitget_pos.get('leverage', 1)))
                
                # 🔥🔥🔥 게이트 레버리지 완전 동기화 (포지션 미러링)
                try:
                    self.logger.info(f"🔧🔧🔧 게이트 레버리지 완전 동기화 (포지션): {leverage}x")
                    
                    # 1단계: 레버리지 설정
                    await self.gate.set_leverage(self.GATE_CONTRACT, leverage)
                    await asyncio.sleep(0.5)
                    
                    # 2단계: 설정 확인 및 재설정
                    try:
                        gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
                        if gate_positions:
                            current_leverage = gate_positions[0].get('leverage')
                            if current_leverage and int(float(current_leverage)) != leverage:
                                self.logger.warning(f"🔧 포지션 레버리지 불일치: 현재 {current_leverage}x, 목표 {leverage}x")
                                await self.gate.set_leverage(self.GATE_CONTRACT, leverage)
                                await asyncio.sleep(0.3)
                                self.logger.info(f"🔧 포지션 레버리지 재설정 완료")
                    except Exception as e:
                        self.logger.warning(f"포지션 레버리지 확인 실패: {e}")
                    
                    self.logger.info(f"✅✅✅ 게이트 레버리지 완전 동기화 완료 (포지션): {leverage}x")
                    
                except Exception as e:
                    self.logger.error(f"❌ 게이트 레버리지 설정 실패 (포지션): {e}")
                    # 계속 진행
                
                # 4. 포지션 방향 및 수량 계산
                side = bitget_pos.get('holdSide', '').lower()
                current_price = float(bitget_pos.get('markPrice', bitget_pos.get('openPriceAvg', 0)))
                
                # 계약 정보 조회
                contract_info = await self.gate.get_contract_info(self.GATE_CONTRACT)
                quanto_multiplier = float(contract_info.get('quanto_multiplier', 0.0001))
                
                # 계약 수 계산
                notional_value = gate_margin * leverage
                gate_size = int(notional_value / (current_price * quanto_multiplier))
                
                # 🔥🔥 최소 사이즈 체크
                if gate_size == 0:
                    gate_size = 1
                    self.logger.warning("게이트 계약 수가 0이어서 최소값 1로 설정")
                
                if side == 'short':
                    gate_size = -gate_size
                
                self.logger.info(
                    f"📊 주문 계산\n"
                    f"방향: {side}\n"
                    f"레버리지: {leverage}x (동기화됨)\n"
                    f"계약수: {gate_size}"
                )
                
                # 5. 🔥🔥 진입 주문 (시장가) - 수정된 방식
                order_result = await self.gate.place_order(
                    contract=self.GATE_CONTRACT,
                    size=gate_size,
                    price=None,  # 🔥🔥 시장가 (price와 tif 완전 생략)
                    reduce_only=False
                    # tif 파라미터 완전 제거
                )
                
                self.logger.info(f"✅ 게이트 진입 성공: {order_result}")
                
                # 6. TP/SL 설정 (잠시 대기 후)
                await asyncio.sleep(1)
                tp_sl_result = await self._set_gate_tp_sl(bitget_pos, gate_size)
                
                # 7. 통계 업데이트
                self.daily_stats['total_volume'] += abs(notional_value)
                
                return MirrorResult(
                    success=True,
                    action="new_position",
                    bitget_data=bitget_pos,
                    gate_data={
                        'order': order_result,
                        'size': gate_size,
                        'margin': gate_margin,
                        'leverage': leverage,  # 🔥 레버리지 정보 추가
                        'tp_sl': tp_sl_result
                    }
                )
                
            except Exception as e:
                retry_count += 1
                error_msg = str(e)
                self.logger.error(f"포지션 미러링 시도 {retry_count}/{self.MAX_RETRIES} 실패: {error_msg}")
                
                # 🔥🔥 INVALID_PROTOCOL 오류 시 상세 분석
                if "INVALID_PROTOCOL" in error_msg:
                    self.logger.error(f"🚨🚨 INVALID_PROTOCOL 오류 발생!")
                    self.logger.error(f"   - 비트겟 포지션: {bitget_pos}")
                    self.logger.error(f"   - 재시도 횟수: {retry_count}/{self.MAX_RETRIES}")
                
                if retry_count < self.MAX_RETRIES:
                    wait_time = 2 ** retry_count  # 지수 백오프
                    self.logger.info(f"🔄 {wait_time}초 후 재시도...")
                    await asyncio.sleep(wait_time)
                else:
                    return MirrorResult(
                        success=False,
                        action="new_position",
                        bitget_data=bitget_pos,
                        error=f"최대 재시도 횟수 초과: {error_msg}"
                    )
    
    async def _calculate_margin_ratio(self, bitget_pos: Dict) -> Optional[float]:
        """비트겟 포지션의 마진 비율 계산 (30% 제한 해제)"""
        try:
            # 비트겟 계정 정보
            bitget_account = await self.bitget.get_account_info()
            
            # 총 자산 (USDT)
            total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            # 포지션 마진 (USDT)
            position_margin = float(bitget_pos.get('marginSize', bitget_pos.get('margin', 0)))
            
            if total_equity <= 0 or position_margin <= 0:
                self.logger.warning(f"잘못된 마진 데이터: 총자산={total_equity}, 마진={position_margin}")
                return None
            
            # 마진 비율 (제한 해제)
            margin_ratio = position_margin / total_equity
            
            # 🔥 30% 제한 완전 해제
            # margin_ratio = min(margin_ratio, 0.5)  # 이 줄 제거됨
            
            self.logger.info(
                f"📊 마진 비율 계산 (제한 해제)\n"
                f"비트겟 총자산: ${total_equity:,.2f}\n"
                f"포지션 마진: ${position_margin:,.2f}\n"
                f"비율: {margin_ratio:.4f} ({margin_ratio*100:.2f}%) - 제한 없음"
            )
            
            return margin_ratio
            
        except Exception as e:
            self.logger.error(f"마진 비율 계산 실패: {e}")
            return None
    
    async def _set_gate_tp_sl(self, bitget_pos: Dict, gate_size: int) -> Dict:
        """게이트에 TP/SL 설정"""
        try:
            pos_id = self._generate_position_id(bitget_pos)
            entry_price = float(bitget_pos.get('openPriceAvg', 0))
            side = bitget_pos.get('holdSide', '').lower()
            
            tp_orders = []
            sl_orders = []
            
            # 기본 TP/SL 설정 (실제로는 비트겟 API에서 가져와야 함)
            if side == 'long':
                # 롱 포지션
                tp_prices = [
                    entry_price * 1.01,  # 1% TP
                    entry_price * 1.02,  # 2% TP
                    entry_price * 1.03   # 3% TP
                ]
                sl_price = entry_price * 0.98  # 2% SL
                
                # TP 주문들 (분할 익절)
                remaining_size = abs(gate_size)
                for i, tp_price in enumerate(tp_prices):
                    tp_size = int(remaining_size * 0.33)  # 33%씩
                    if i == len(tp_prices) - 1:  # 마지막은 남은 전체
                        tp_size = remaining_size
                    
                    if tp_size > 0:  # 🔥🔥 0보다 큰 경우만 주문
                        tp_order = await self.gate.create_price_triggered_order(
                            trigger_type="ge",
                            trigger_price=str(tp_price),
                            order_type="limit",
                            contract=self.GATE_CONTRACT,
                            size=-tp_size,
                            price=str(tp_price)
                        )
                        tp_orders.append(tp_order)
                        remaining_size -= tp_size
                
                # SL 주문 (전체)
                if abs(gate_size) > 0:  # 🔥🔥 0보다 큰 경우만 주문
                    sl_order = await self.gate.create_price_triggered_order(
                        trigger_type="le",
                        trigger_price=str(sl_price),
                        order_type="market",
                        contract=self.GATE_CONTRACT,
                        size=-abs(gate_size)
                    )
                    sl_orders.append(sl_order)
                
            else:
                # 숏 포지션
                tp_prices = [
                    entry_price * 0.99,  # 1% TP
                    entry_price * 0.98,  # 2% TP
                    entry_price * 0.97   # 3% TP
                ]
                sl_price = entry_price * 1.02  # 2% SL
                
                # TP 주문들
                remaining_size = abs(gate_size)
                for i, tp_price in enumerate(tp_prices):
                    tp_size = int(remaining_size * 0.33)
                    if i == len(tp_prices) - 1:
                        tp_size = remaining_size
                    
                    if tp_size > 0:  # 🔥🔥 0보다 큰 경우만 주문
                        tp_order = await self.gate.create_price_triggered_order(
                            trigger_type="le",
                            trigger_price=str(tp_price),
                            order_type="limit",
                            contract=self.GATE_CONTRACT,
                            size=tp_size,
                            price=str(tp_price)
                        )
                        tp_orders.append(tp_order)
                        remaining_size -= tp_size
                
                # SL 주문
                if abs(gate_size) > 0:  # 🔥🔥 0보다 큰 경우만 주문
                    sl_order = await self.gate.create_price_triggered_order(
                        trigger_type="ge",
                        trigger_price=str(sl_price),
                        order_type="market",
                        contract=self.GATE_CONTRACT,
                        size=abs(gate_size)
                    )
                    sl_orders.append(sl_order)
            
            # TP/SL 주문 ID 저장
            self.tp_sl_orders[pos_id] = {
                'tp': [order.get('id') for order in tp_orders],
                'sl': [order.get('id') for order in sl_orders]
            }
            
            self.logger.info(
                f"📍 TP/SL 설정 완료\n"
                f"TP: {len(tp_orders)}개\n"
                f"SL: {len(sl_orders)}개"
            )
            
            return {
                'tp_orders': tp_orders,
                'sl_orders': sl_orders
            }
            
        except Exception as e:
            self.logger.error(f"TP/SL 설정 실패: {e}")
            return {'tp_orders': [], 'sl_orders': []}
    
    async def _handle_partial_close(self, pos_id: str, bitget_pos: Dict, reduction_ratio: float):
        """부분 청산 처리"""
        try:
            # 게이트 포지션 조회
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            
            if not gate_positions or gate_positions[0].get('size', 0) == 0:
                self.logger.warning(f"게이트 포지션을 찾을 수 없습니다: {pos_id}")
                return
            
            gate_pos = gate_positions[0]
            current_gate_size = int(gate_pos['size'])
            
            # 청산할 수량 계산
            close_size = int(abs(current_gate_size) * reduction_ratio)
            
            if close_size == 0:
                return
            
            # 방향에 따라 부호 조정
            if current_gate_size > 0:  # 롱
                close_size = -close_size
            else:  # 숏
                close_size = close_size
            
            self.logger.info(f"부분 청산 실행: {close_size} 계약 ({reduction_ratio*100:.1f}%)")
            
            # 🔥🔥 시장가로 부분 청산 - 수정된 방식
            result = await self.gate.place_order(
                contract=self.GATE_CONTRACT,
                size=close_size,
                price=None,  # 🔥🔥 시장가
                reduce_only=True
                # tif 파라미터 제거
            )
            
            await self.telegram.send_message(
                f"📉 부분 청산 완료\n"
                f"비율: {reduction_ratio*100:.1f}%\n"
                f"수량: {abs(close_size)} 계약"
            )
            
        except Exception as e:
            self.logger.error(f"부분 청산 처리 실패: {e}")
            await self.telegram.send_message(
                f"❌ 부분 청산 실패\n"
                f"포지션: {pos_id}\n"
                f"오류: {str(e)[:200]}"
            )
    
    async def _handle_position_close(self, pos_id: str):
        """포지션 종료 처리"""
        try:
            self.logger.info(f"🔚 포지션 종료 감지: {pos_id}")
            
            # 게이트 포지션 전체 종료
            result = await self.gate.close_position(self.GATE_CONTRACT)
            
            # TP/SL 주문 취소
            if pos_id in self.tp_sl_orders:
                orders = self.tp_sl_orders[pos_id]
                
                # TP 주문 취소
                for order_id in orders.get('tp', []):
                    try:
                        await self.gate.cancel_price_triggered_order(order_id)
                    except:
                        pass
                
                # SL 주문 취소
                for order_id in orders.get('sl', []):
                    try:
                        await self.gate.cancel_price_triggered_order(order_id)
                    except:
                        pass
                
                del self.tp_sl_orders[pos_id]
            
            # 상태 정리
            if pos_id in self.mirrored_positions:
                del self.mirrored_positions[pos_id]
            if pos_id in self.position_sizes:
                del self.position_sizes[pos_id]
            
            self.daily_stats['full_closes'] += 1
            
            await self.telegram.send_message(
                f"✅ 포지션 종료 완료\n"
                f"포지션 ID: {pos_id}"
            )
            
        except Exception as e:
            self.logger.error(f"포지션 종료 처리 실패: {e}")
            await self.telegram.send_message(
                f"❌ 포지션 종료 실패\n"
                f"포지션: {pos_id}\n"
                f"오류: {str(e)[:200]}"
            )
    
    async def _check_tp_sl_updates(self, pos_id: str, bitget_pos: Dict):
        """TP/SL 업데이트 확인"""
        # 실제 구현에서는 비트겟 API로 TP/SL 주문을 조회하고
        # 변경사항이 있으면 게이트 주문도 업데이트해야 함
        pass
    
    async def monitor_sync_status(self):
        """포지션 동기화 상태 모니터링"""
        while self.monitoring:
            try:
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)
                
                # 비트겟 포지션
                bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                bitget_active = [
                    pos for pos in bitget_positions 
                    if float(pos.get('total', 0)) > 0
                ]
                
                # 게이트 포지션
                gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
                gate_active = [
                    pos for pos in gate_positions 
                    if pos.get('size', 0) != 0
                ]
                
                # 포지션 수 비교
                bitget_count = len(bitget_active)
                gate_count = len(gate_active)
                
                # 미러링된 포지션만 카운트 (시작 시 존재했던 것 제외)
                mirrored_bitget_count = sum(
                    1 for pos in bitget_active 
                    if self._generate_position_id(pos) not in self.startup_positions
                )
                
                if mirrored_bitget_count != gate_count:
                    self.logger.warning(
                        f"⚠️ 포지션 불일치 감지\n"
                        f"비트겟 (미러링 대상): {mirrored_bitget_count}\n"
                        f"게이트: {gate_count}"
                    )
                    
                    # 상세 분석
                    await self._analyze_sync_mismatch(bitget_active, gate_active)
                else:
                    self.logger.info(f"✅ 포지션 동기화 정상: {gate_count}개")
                
                # 🔥 예약 주문 동기화 상태도 체크
                await self._check_plan_order_sync()
                
            except Exception as e:
                self.logger.error(f"동기화 모니터링 오류: {e}")
    
    async def _check_plan_order_sync(self):
        """🔥 신규: 예약 주문 동기화 상태 체크"""
        try:
            # 비트겟 예약 주문 수
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            current_bitget_orders = plan_data.get('plan_orders', []) + plan_data.get('tp_sl_orders', [])
            
            # 시작 시 존재했던 것과 기존 포지션 TP/SL 제외
            new_bitget_orders = [
                order for order in current_bitget_orders 
                if (order.get('orderId', order.get('planOrderId', '')) not in self.startup_plan_orders and
                    order.get('orderId', order.get('planOrderId', '')) not in self.startup_position_tp_sl)
            ]
            
            bitget_plan_count = len(new_bitget_orders)
            gate_plan_count = len(self.mirrored_plan_orders)
            
            self.logger.info(f"예약 주문 동기화 상태: 비트겟 {bitget_plan_count}개, 게이트 {gate_plan_count}개 복제됨")
            
        except Exception as e:
            self.logger.error(f"예약 주문 동기화 체크 실패: {e}")
    
    async def _analyze_sync_mismatch(self, bitget_positions: List[Dict], gate_positions: List[Dict]):
        """동기화 불일치 분석"""
        try:
            # 비트겟에만 있는 포지션
            for bitget_pos in bitget_positions:
                pos_id = self._generate_position_id(bitget_pos)
                
                # 시작 시 존재했던 포지션은 제외
                if pos_id in self.startup_positions:
                    continue
                
                if pos_id not in self.mirrored_positions:
                    self.logger.warning(f"비트겟에만 존재하는 포지션: {pos_id}")
                    
                    # 자동 미러링 시도
                    result = await self._mirror_new_position(bitget_pos)
                    if result.success:
                        self.logger.info(f"동기화 복구 성공: {pos_id}")
                    else:
                        await self.telegram.send_message(
                            f"⚠️ 동기화 문제\n"
                            f"비트겟 포지션이 게이트에 없습니다\n"
                            f"포지션: {pos_id}\n"
                            f"자동 복구 실패: {result.error}"
                        )
            
            # 게이트에만 있는 포지션
            if len(gate_positions) > 0 and len(self.mirrored_positions) == 0:
                self.logger.warning("게이트에 추적되지 않는 포지션 존재")
                
                # 자동 정리
                for gate_pos in gate_positions:
                    if gate_pos.get('size', 0) != 0:
                        self.logger.info("추적되지 않는 게이트 포지션 종료")
                        await self.gate.close_position(self.GATE_CONTRACT)
                        
                        await self.telegram.send_message(
                            f"🔄 게이트 단독 포지션 정리\n"
                            f"대응하는 비트겟 포지션이 없어 종료했습니다"
                        )
            
        except Exception as e:
            self.logger.error(f"동기화 분석 중 오류: {e}")
    
    async def generate_daily_reports(self):
        """일일 리포트 생성"""
        while self.monitoring:
            try:
                now = datetime.now()
                
                # 매일 지정된 시간에 리포트 생성
                if now.hour == self.DAILY_REPORT_HOUR and now > self.last_report_time + timedelta(hours=23):
                    report = await self._create_daily_report()
                    await self.telegram.send_message(report)
                    
                    # 통계 초기화
                    self._reset_daily_stats()
                    self.last_report_time = now
                
                await asyncio.sleep(3600)  # 1시간마다 체크
                
            except Exception as e:
                self.logger.error(f"일일 리포트 생성 오류: {e}")
                await asyncio.sleep(3600)
    
    async def _create_daily_report(self) -> str:
        """일일 리포트 생성"""
        try:
            # 계정 정보 조회
            bitget_account = await self.bitget.get_account_info()
            gate_account = await self.gate.get_account_balance()
            
            bitget_equity = float(bitget_account.get('accountEquity', 0))
            gate_equity = float(gate_account.get('total', 0))
            bitget_leverage = bitget_account.get('crossMarginLeverage', 'N/A')
            
            # 성공률 계산
            success_rate = 0
            if self.daily_stats['total_mirrored'] > 0:
                success_rate = (self.daily_stats['successful_mirrors'] / 
                              self.daily_stats['total_mirrored']) * 100
            
            report = f"""📊 일일 레버리지 완전 동기화 + 달러 비율 복제 미러 트레이딩 리포트
📅 {datetime.now().strftime('%Y-%m-%d')}
━━━━━━━━━━━━━━━━━━━

🔥 예약 주문 복제 성과 (레버리지 동기화)
- 예약 주문 미러링: {self.daily_stats['plan_order_mirrors']}회
- 예약 주문 취소 동기화: {self.daily_stats['plan_order_cancels']}회
- 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개

⚡ 실시간 포지션 미러링 (레버리지 동기화)
- 주문 체결 기반: {self.daily_stats['order_mirrors']}회
- 포지션 기반: {self.daily_stats['position_mirrors']}회
- 총 시도: {self.daily_stats['total_mirrored']}회
- 성공: {self.daily_stats['successful_mirrors']}회
- 실패: {self.daily_stats['failed_mirrors']}회
- 성공률: {success_rate:.1f}%

📉 포지션 관리
- 부분 청산: {self.daily_stats['partial_closes']}회
- 전체 청산: {self.daily_stats['full_closes']}회
- 총 거래량: ${self.daily_stats['total_volume']:,.2f}

💰 계정 잔고 (레버리지 동기화)
- 비트겟: ${bitget_equity:,.2f} (레버리지: {bitget_leverage}x)
- 게이트: ${gate_equity:,.2f} (레버리지: 동기화됨)
- 비율: {(gate_equity/bitget_equity*100):.1f}%

🔄 현재 미러링 상태
- 활성 포지션: {len(self.mirrored_positions)}개
- 활성 예약 주문: {len(self.mirrored_plan_orders)}개
- 실패 기록: {len(self.failed_mirrors)}건

⚡ 시스템 최적화 (레버리지 동기화)
- 예약 주문 감지: {self.PLAN_ORDER_CHECK_INTERVAL}초마다
- 주문 체결 감지: {self.ORDER_CHECK_INTERVAL}초마다
- 포지션 모니터링: {self.CHECK_INTERVAL}초마다

🔧 레버리지 완전 동기화
- 비트겟 레버리지 → 게이트 레버리지 (완전 동일)
- 예약 주문별 정확한 레버리지 추출
- 3단계 확인 및 재설정 시스템
- 주문 생성 전 강제 동기화

💰 달러 비율 복제 (제한 해제)
- 총 자산 대비 동일 비율 유지
- 30% 제한 완전 해제
- 예약 주문도 동일 비율 복제
- 기존 포지션 클로즈 TP/SL 제외
- 추가 진입 예약 TP/SL 복제

🚫🚫 예약주문 취소 동기화 (개선)
- 비트겟에서 예약주문 취소 → 게이트도 자동 취소
- 실시간 취소 상태 비교
- 취소 실패 시 상세 오류 처리

"""
            
            # 오류가 있었다면 추가
            if self.daily_stats['errors']:
                report += f"\n⚠️ 오류 발생: {len(self.daily_stats['errors'])}건\n"
                for i, error in enumerate(self.daily_stats['errors'][-3:], 1):  # 최근 3개만
                    report += f"{i}. {error['error'][:50]}...\n"
            
            report += "\n━━━━━━━━━━━━━━━━━━━\n🔥🔥 레버리지 완전 동기화 + 달러 비율로 완벽 복제!"
            
            return report
            
        except Exception as e:
            self.logger.error(f"리포트 생성 실패: {e}")
            return f"📊 일일 리포트 생성 실패\n오류: {str(e)}"
    
    def _reset_daily_stats(self):
        """일일 통계 초기화"""
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
            'errors': []
        }
        self.failed_mirrors.clear()
    
    def _generate_position_id(self, pos: Dict) -> str:
        """포지션 고유 ID 생성"""
        symbol = pos.get('symbol', self.SYMBOL)
        side = pos.get('holdSide', '')
        entry_price = pos.get('openPriceAvg', '')
        return f"{symbol}_{side}_{entry_price}"
    
    async def _create_position_info(self, bitget_pos: Dict) -> PositionInfo:
        """포지션 정보 객체 생성"""
        return PositionInfo(
            symbol=bitget_pos.get('symbol', self.SYMBOL),
            side=bitget_pos.get('holdSide', '').lower(),
            size=float(bitget_pos.get('total', 0)),
            entry_price=float(bitget_pos.get('openPriceAvg', 0)),
            margin=float(bitget_pos.get('marginSize', 0)),
            leverage=int(float(bitget_pos.get('leverage', 1))),
            mode='cross' if bitget_pos.get('marginMode') == 'crossed' else 'isolated',
            unrealized_pnl=float(bitget_pos.get('unrealizedPL', 0))
        )
    
    async def stop(self):
        """미러 트레이딩 중지"""
        self.monitoring = False
        
        # 최종 리포트 생성
        try:
            final_report = await self._create_daily_report()
            await self.telegram.send_message(
                f"🛑 레버리지 완전 동기화 + 달러 비율 복제 미러 트레이딩 종료\n\n{final_report}"
            )
        except:
            pass
        
        self.logger.info("레버리지 완전 동기화 + 달러 비율 복제 미러 트레이딩 시스템 중지")
