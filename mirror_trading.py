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
        self.mirrored_positions: Dict[str, PositionInfo] = {}
        self.startup_positions: Set[str] = set()
        self.failed_mirrors: List[MirrorResult] = []
        self.last_sync_check = datetime.min
        self.last_report_time = datetime.min
        
        # 포지션 크기 추적
        self.position_sizes: Dict[str, float] = {}
        
        # TP/SL 주문 추적
        self.tp_sl_orders: Dict[str, Dict] = {}
        
        # 주문 체결 추적
        self.processed_orders: Set[str] = set()
        self.last_order_check = datetime.now()
        
        # 예약 주문 추적 - 개선된 관리
        self.mirrored_plan_orders: Dict[str, Dict] = {}
        self.processed_plan_orders: Set[str] = set()
        self.startup_plan_orders: Set[str] = set()
        self.startup_plan_orders_processed: bool = False
        self.already_mirrored_plan_orders: Set[str] = set()  # 🔥 이미 복제된 예약 주문 추적
        
        # 예약주문 취소 감지
        self.last_plan_order_ids: Set[str] = set()
        
        # 포지션 유무에 따른 예약 주문 복제 관리
        self.startup_position_tp_sl: Set[str] = set()
        self.has_startup_positions: bool = False
        
        # 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.CHECK_INTERVAL = 2
        self.ORDER_CHECK_INTERVAL = 1
        self.PLAN_ORDER_CHECK_INTERVAL = 3
        self.SYNC_CHECK_INTERVAL = 30
        self.MAX_RETRIES = 3
        self.MIN_POSITION_SIZE = 0.00001
        self.MIN_MARGIN = 1.0
        self.DAILY_REPORT_HOUR = 9
        
        # 성과 추적 - 개선된 통계
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
            'plan_order_skipped_already_mirrored': 0,  # 🔥 이미 복제된 주문 스킵
            'plan_order_skipped_trigger_price': 0,     # 🔥 트리거 가격 문제로 스킵
            'errors': []
        }
        
        self.monitoring = True
        self.logger.info("🔥 실제 달러 마진 비율 동적 계산 + 예약 주문 완전 복제 미러 트레이딩 시스템 초기화 완료")
    
    async def start(self):
        """미러 트레이딩 시작"""
        try:
            self.logger.info("🚀 실제 달러 마진 비율 동적 계산 + 예약 주문 완전 복제 미러 트레이딩 시스템 시작")
            
            # 초기 포지션 및 예약 주문 기록
            await self._record_startup_positions()
            await self._record_startup_plan_orders()
            await self._record_startup_position_tp_sl()
            
            # 🔥 게이트에 이미 복제된 예약 주문 확인
            await self._check_already_mirrored_plan_orders()
            
            # 시작 시 기존 예약 주문 복제
            await self._mirror_startup_plan_orders()
            
            # 초기 계정 상태 출력
            await self._log_account_status()
            
            # 모니터링 태스크 시작
            tasks = [
                self.monitor_plan_orders(),
                self.monitor_order_fills(),
                self.monitor_positions(),
                self.monitor_sync_status(),
                self.generate_daily_reports()
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시작 실패: {e}")
            await self.telegram.send_message(
                f"❌ 미러 트레이딩 시작 실패\n"
                f"오류: {str(e)[:200]}"
            )
            raise
    
    async def _check_already_mirrored_plan_orders(self):
        """🔥 게이트에 이미 복제된 예약 주문 확인"""
        try:
            self.logger.info("🔥 게이트에 이미 복제된 예약 주문 확인 시작")
            
            # 게이트의 현재 예약 주문 조회
            gate_plan_orders = await self.gate.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            self.logger.info(f"게이트 현재 예약 주문: {len(gate_plan_orders)}개")
            
            for gate_order in gate_plan_orders:
                gate_order_id = gate_order.get('id', '')
                trigger_price = gate_order.get('trigger', {}).get('price', '')
                
                if gate_order_id and trigger_price:
                    # 이미 복제된 주문으로 기록
                    # 실제로는 비트겟 주문 ID를 모르므로, 트리거 가격을 기준으로 매칭
                    self.already_mirrored_plan_orders.add(f"gate_{gate_order_id}")
                    self.logger.info(f"이미 복제된 예약 주문 발견: Gate ID {gate_order_id}, 트리거가 ${trigger_price}")
            
            if gate_plan_orders:
                self.logger.info(f"✅ 총 {len(gate_plan_orders)}개의 이미 복제된 예약 주문 확인")
            else:
                self.logger.info("📝 게이트에 복제된 예약 주문이 없음")
                
        except Exception as e:
            self.logger.error(f"이미 복제된 예약 주문 확인 실패: {e}")
    
    async def _record_startup_plan_orders(self):
        """시작 시 존재하는 예약 주문 기록"""
        try:
            self.logger.info("🔥 기존 예약 주문 기록 시작")
            
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            for order in plan_orders + tp_sl_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.startup_plan_orders.add(order_id)
                    self.last_plan_order_ids.add(order_id)
            
            total_existing = len(plan_orders) + len(tp_sl_orders)
            self.logger.info(f"🔥 총 {total_existing}개의 기존 예약 주문을 기록했습니다")
            
        except Exception as e:
            self.logger.error(f"기존 예약 주문 기록 실패: {e}")
    
    async def _mirror_startup_plan_orders(self):
        """시작 시 기존 예약 주문 복제 - 개선된 스킵 로직"""
        try:
            self.logger.info("🔥 시작 시 기존 예약 주문 복제 시작")
            
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_orders = plan_orders + tp_sl_orders
            
            if not all_orders:
                self.startup_plan_orders_processed = True
                return
            
            mirrored_count = 0
            failed_count = 0
            skipped_already_mirrored_count = 0
            skipped_trigger_price_count = 0
            
            for order in all_orders:
                try:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if not order_id:
                        continue
                    
                    # 포지션이 있을 때만 기존 포지션의 클로즈 TP/SL 제외
                    if self.has_startup_positions and order_id in self.startup_position_tp_sl:
                        continue
                    
                    # 🔥 이미 복제된 예약 주문인지 확인 (트리거 가격 매칭)
                    result = await self._check_if_already_mirrored(order)
                    
                    if result == "already_mirrored":
                        skipped_already_mirrored_count += 1
                        self.logger.info(f"⏭️ 이미 복제된 예약 주문 스킵: {order_id}")
                        continue
                    
                    # 예약 주문 복제 실행
                    result = await self._process_startup_plan_order(order)
                    
                    if result == "skipped_trigger_price":
                        skipped_trigger_price_count += 1
                    elif result == "success":
                        mirrored_count += 1
                    else:
                        failed_count += 1
                    
                    self.processed_plan_orders.add(order_id)
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"기존 예약 주문 복제 실패: {order.get('orderId', 'unknown')} - {e}")
                    continue
            
            self.daily_stats['startup_plan_mirrors'] = mirrored_count
            self.daily_stats['plan_order_skipped_already_mirrored'] = skipped_already_mirrored_count
            self.daily_stats['plan_order_skipped_trigger_price'] = skipped_trigger_price_count
            self.startup_plan_orders_processed = True
            
            position_mode_text = "포지션 없음 - 모든 예약 주문 복제" if not self.has_startup_positions else "포지션 있음 - 클로즈 TP/SL 제외하고 복제"
            
            await self.telegram.send_message(
                f"🔥✅ 시작 시 기존 예약 주문 복제 완료\n"
                f"성공: {mirrored_count}개\n"
                f"이미 복제됨: {skipped_already_mirrored_count}개\n"
                f"트리거 가격 문제: {skipped_trigger_price_count}개\n"
                f"실패: {failed_count}개\n"
                f"🔥 모드: {position_mode_text}"
            )
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 복제 실패: {e}")
            self.startup_plan_orders_processed = True
    
    async def _check_if_already_mirrored(self, bitget_order: Dict) -> str:
        """🔥 예약 주문이 이미 복제되었는지 확인"""
        try:
            # 트리거 가격 추출
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price == 0:
                return "unknown"
            
            # 게이트의 현재 예약 주문 조회
            gate_plan_orders = await self.gate.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            # 트리거 가격이 유사한 주문이 있는지 확인 (±1% 오차 허용)
            for gate_order in gate_plan_orders:
                gate_trigger_price = 0
                trigger_info = gate_order.get('trigger', {})
                if trigger_info and 'price' in trigger_info:
                    try:
                        gate_trigger_price = float(trigger_info['price'])
                    except:
                        continue
                
                if gate_trigger_price > 0:
                    price_diff_percent = abs(trigger_price - gate_trigger_price) / trigger_price * 100
                    if price_diff_percent <= 1.0:  # 1% 오차 허용
                        return "already_mirrored"
            
            return "not_mirrored"
            
        except Exception as e:
            self.logger.error(f"예약 주문 복제 확인 실패: {e}")
            return "unknown"
    
    async def _process_startup_plan_order(self, bitget_order: Dict):
        """시작 시 예약 주문 복제 처리 - 개선된 스킵 로직"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            size = float(bitget_order.get('size', 0))
            
            # 트리거 가격 추출
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price == 0:
                return "failed"
            
            # 트리거 가격 유효성 검증
            is_valid, skip_reason = await self._validate_trigger_price(trigger_price, side)
            if not is_valid:
                self.logger.warning(f"⏭️ 시작 시 예약 주문 스킵됨 (트리거 가격 문제): {order_id} - {skip_reason}")
                return "skipped_trigger_price"
            
            # 실제 달러 마진 비율 동적 계산
            margin_ratio_result = await self._calculate_dynamic_margin_ratio(
                size, trigger_price, bitget_order
            )
            
            if not margin_ratio_result['success']:
                return "failed"
            
            margin_ratio = margin_ratio_result['margin_ratio']
            bitget_leverage = margin_ratio_result['leverage']
            
            # 게이트 계정 정보
            gate_account = await self.gate.get_account_balance()
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
            
            # 방향에 따라 부호 조정
            is_buy_order = False
            if side in ['buy', 'open_long']:
                is_buy_order = True
            elif side in ['sell', 'open_short']:
                is_buy_order = False
            elif side in ['close_long']:
                is_buy_order = False
                gate_size = -gate_size
            elif side in ['close_short']:
                is_buy_order = True
            else:
                is_buy_order = 'buy' in side.lower()
            
            if not is_buy_order and side not in ['close_long']:
                gate_size = -gate_size
            
            # 🔥🔥 수정된 Gate.io 트리거 타입 변환 - 트리거가와 현재가 관계로 결정
            gate_trigger_type = await self._determine_gate_trigger_type(trigger_price)
            
            # 게이트 레버리지 설정
            try:
                await self.gate.set_leverage(self.GATE_CONTRACT, bitget_leverage)
                await asyncio.sleep(0.3)
            except Exception as e:
                self.logger.error(f"시작 시 레버리지 설정 실패: {e}")
            
            # Gate.io에 예약 주문 생성
            gate_order = await self.gate.create_price_triggered_order(
                trigger_type=gate_trigger_type,
                trigger_price=str(trigger_price),
                order_type="market",
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
                'leverage': bitget_leverage,
                'is_startup_order': True
            }
            
            return "success"
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 복제 처리 실패: {e}")
            return "failed"
    
    async def _determine_gate_trigger_type(self, trigger_price: float) -> str:
        """🔥🔥 수정된 Gate.io 트리거 타입 결정 - 트리거가와 현재가 관계로 판단"""
        try:
            # 게이트 현재 시장가 조회
            current_price = None
            try:
                contract_info = await self.gate.get_contract_info(self.GATE_CONTRACT)
                if 'last_price' in contract_info:
                    current_price = float(contract_info['last_price'])
                elif 'mark_price' in contract_info:
                    current_price = float(contract_info['mark_price'])
            except:
                pass
            
            # 현재가를 찾을 수 없으면 비트겟 현재가 사용
            if current_price is None:
                try:
                    bitget_ticker = await self.bitget.get_ticker(self.SYMBOL)
                    if bitget_ticker:
                        current_price = float(bitget_ticker.get('last', 0))
                except:
                    pass
            
            if current_price is None or current_price == 0:
                # 폴백: 기본값으로 ge 사용
                return "ge"
            
            # 🔥🔥 핵심 수정: 트리거가와 현재가 관계로만 판단
            if trigger_price > current_price:
                return "ge"  # 트리거가가 더 높으면 ge (>=)
            else:
                return "le"  # 트리거가가 더 낮으면 le (<=)
                
        except Exception as e:
            self.logger.error(f"Gate.io 트리거 타입 결정 실패: {e}")
            return "ge"  # 기본값
    
    async def _validate_trigger_price(self, trigger_price: float, side: str) -> Tuple[bool, str]:
        """🔥🔥 수정된 트리거 가격 유효성 검증 - 단순화"""
        try:
            # 게이트 현재 시장가 조회
            contract_info = await self.gate.get_contract_info(self.GATE_CONTRACT)
            
            current_price = None
            if 'last_price' in contract_info:
                current_price = float(contract_info['last_price'])
            elif 'mark_price' in contract_info:
                current_price = float(contract_info['mark_price'])
            
            # 현재가를 찾을 수 없으면 비트겟 현재가 사용
            if current_price is None:
                bitget_ticker = await self.bitget.get_ticker(self.SYMBOL)
                if bitget_ticker:
                    current_price = float(bitget_ticker.get('last', 0))
            
            if current_price is None or current_price == 0:
                return False, "현재 시장가를 조회할 수 없음"
            
            # 🔥🔥 핵심 수정: 단순한 검증 로직
            # 트리거가와 현재가가 너무 근접하면 스킵 (최소 0.1% 차이 필요)
            price_diff_percent = abs(trigger_price - current_price) / current_price * 100
            if price_diff_percent < 0.1:
                return False, f"트리거가와 현재가 차이가 너무 작음 ({price_diff_percent:.4f}%)"
            
            # 🔥🔥 기본적인 유효성만 검증 - 모든 트리거 가격을 허용
            if trigger_price <= 0:
                return False, "트리거 가격이 0 이하입니다"
            
            # 극단적인 가격 차이 검증 (현재가 대비 50% 이상 차이나면 경고)
            if price_diff_percent > 50:
                return False, f"트리거가와 현재가 차이가 너무 큼 ({price_diff_percent:.1f}%)"
            
            return True, "유효한 트리거 가격"
            
        except Exception as e:
            self.logger.error(f"트리거 가격 검증 실패: {e}")
            return False, f"검증 오류: {str(e)}"
    
    async def _record_startup_position_tp_sl(self):
        """포지션 유무에 따른 개선된 TP/SL 분류"""
        try:
            self.logger.info("🔥 포지션 유무에 따른 예약 주문 복제 정책 설정 시작")
            
            # 현재 활성 포지션들 조회
            positions = await self.bitget.get_positions(self.SYMBOL)
            
            active_positions = []
            for pos in positions:
                if float(pos.get('total', 0)) > 0:
                    active_positions.append(pos)
            
            self.has_startup_positions = len(active_positions) > 0
            
            if not self.has_startup_positions:
                # 포지션이 없으면 모든 예약 주문을 복제
                self.startup_position_tp_sl.clear()
            else:
                # 포지션이 있으면 기존 로직대로 클로즈 TP/SL만 제외
                for pos in active_positions:
                    pos_side = pos.get('holdSide', '').lower()
                    
                    # 해당 포지션의 TP/SL 주문들 찾기
                    plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
                    tp_sl_orders = plan_data.get('tp_sl_orders', [])
                    
                    for tp_sl_order in tp_sl_orders:
                        trade_side = tp_sl_order.get('tradeSide', tp_sl_order.get('side', '')).lower()
                        reduce_only = tp_sl_order.get('reduceOnly', False)
                        
                        # 기존 포지션의 클로즈 TP/SL인지 판단
                        is_existing_position_close = False
                        
                        if pos_side == 'long':
                            if (trade_side in ['close_long', 'sell'] and 
                                (reduce_only is True or reduce_only == 'true')):
                                is_existing_position_close = True
                        elif pos_side == 'short':
                            if (trade_side in ['close_short', 'buy'] and 
                                (reduce_only is True or reduce_only == 'true')):
                                is_existing_position_close = True
                        
                        order_id = tp_sl_order.get('orderId', tp_sl_order.get('planOrderId', ''))
                        if order_id and is_existing_position_close:
                            self.startup_position_tp_sl.add(order_id)
            
        except Exception as e:
            self.logger.error(f"포지션 유무에 따른 예약 주문 정책 설정 실패: {e}")
            self.has_startup_positions = False
            self.startup_position_tp_sl.clear()
    
    async def monitor_plan_orders(self):
        """예약 주문 모니터링"""
        self.logger.info("🔥 예약 주문 실제 달러 마진 비율 동적 계산 복제 모니터링 시작")
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                if not self.startup_plan_orders_processed:
                    await asyncio.sleep(1)
                    continue
                
                # 현재 비트겟 예약 주문 조회
                plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
                current_plan_orders = plan_data.get('plan_orders', [])
                current_tp_sl_orders = plan_data.get('tp_sl_orders', [])
                
                all_current_orders = current_plan_orders + current_tp_sl_orders
                
                # 현재 존재하는 예약주문 ID 집합
                current_order_ids = set()
                for order in all_current_orders:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if order_id:
                        current_order_ids.add(order_id)
                
                # 취소된 예약 주문 감지
                canceled_order_ids = self.last_plan_order_ids - current_order_ids
                
                # 취소된 주문 처리
                for canceled_order_id in canceled_order_ids:
                    await self._handle_plan_order_cancel(canceled_order_id)
                
                # 새로운 예약 주문 감지
                new_orders_count = 0
                skipped_orders_count = 0
                for order in all_current_orders:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if not order_id:
                        continue
                    
                    # 포지션 유무에 따른 필터링
                    if self.has_startup_positions and order_id in self.startup_position_tp_sl:
                        continue
                    
                    # 이미 처리된 주문은 스킵
                    if order_id in self.processed_plan_orders:
                        continue
                    
                    # 시작 시 존재했던 주문인지 확인
                    if order_id in self.startup_plan_orders:
                        self.processed_plan_orders.add(order_id)
                        continue
                    
                    # 새로운 예약 주문 감지
                    try:
                        result = await self._process_new_plan_order(order)
                        
                        if result == "skipped":
                            skipped_orders_count += 1
                        else:
                            new_orders_count += 1
                        
                        self.processed_plan_orders.add(order_id)
                        
                    except Exception as e:
                        self.logger.error(f"❌ 새로운 예약 주문 복제 실패: {order_id} - {e}")
                        self.processed_plan_orders.add(order_id)
                        
                        await self.telegram.send_message(
                            f"❌ 예약 주문 복제 실패\n"
                            f"비트겟 ID: {order_id}\n"
                            f"오류: {str(e)[:200]}"
                        )
                
                # 현재 상태를 다음 비교를 위해 저장
                self.last_plan_order_ids = current_order_ids.copy()
                
                # 통계 업데이트
                if skipped_orders_count > 0:
                    self.daily_stats['plan_order_skipped_trigger_price'] += skipped_orders_count
                
                # 오래된 주문 ID 정리
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
        """새로운 예약 주문 복제 - 실제 달러 마진 비율 동적 계산"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            size = float(bitget_order.get('size', 0))
            
            # 트리거 가격 추출
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price == 0:
                return "failed"
            
            # 트리거 가격 유효성 검증
            is_valid, skip_reason = await self._validate_trigger_price(trigger_price, side)
            if not is_valid:
                await self.telegram.send_message(
                    f"⏭️ 예약 주문 스킵됨 (트리거 가격 문제)\n"
                    f"비트겟 ID: {order_id}\n"
                    f"방향: {side.upper()}\n"
                    f"트리거가: ${trigger_price:,.2f}\n"
                    f"스킵 사유: {skip_reason}"
                )
                return "skipped"
            
            # 실제 달러 마진 비율 동적 계산
            margin_ratio_result = await self._calculate_dynamic_margin_ratio(
                size, trigger_price, bitget_order
            )
            
            if not margin_ratio_result['success']:
                return "failed"
            
            margin_ratio = margin_ratio_result['margin_ratio']
            bitget_leverage = margin_ratio_result['leverage']
            bitget_required_margin = margin_ratio_result['required_margin']
            bitget_total_equity = margin_ratio_result['total_equity']
            
            # 게이트 계정 정보
            gate_account = await self.gate.get_account_balance()
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
            
            # 방향에 따라 부호 조정
            is_buy_order = False
            if side in ['buy', 'open_long']:
                is_buy_order = True
            elif side in ['sell', 'open_short']:
                is_buy_order = False
            elif side in ['close_long']:
                is_buy_order = False
                gate_size = -gate_size
            elif side in ['close_short']:
                is_buy_order = True
            else:
                is_buy_order = 'buy' in side.lower()
            
            if not is_buy_order and side not in ['close_long']:
                gate_size = -gate_size
            
            # 🔥🔥 수정된 Gate.io 트리거 타입 변환 - 트리거가와 현재가 관계로 결정
            gate_trigger_type = await self._determine_gate_trigger_type(trigger_price)
            
            # 게이트 레버리지 설정
            try:
                await self.gate.set_leverage(self.GATE_CONTRACT, bitget_leverage)
                await asyncio.sleep(0.3)
            except Exception as e:
                self.logger.error(f"❌ 게이트 레버리지 설정 실패: {e}")
            
            # Gate.io에 예약 주문 생성
            try:
                gate_order = await self.gate.create_price_triggered_order(
                    trigger_type=gate_trigger_type,
                    trigger_price=str(trigger_price),
                    order_type="market",
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
                    'leverage': bitget_leverage,
                    'bitget_required_margin': bitget_required_margin,
                    'gate_total_equity': gate_total_equity,
                    'bitget_total_equity': bitget_total_equity
                }
                
                self.daily_stats['plan_order_mirrors'] += 1
                
                await self.telegram.send_message(
                    f"🔥✅ 예약 주문 실제 달러 마진 비율 동적 계산 복제 성공\n"
                    f"비트겟 ID: {order_id}\n"
                    f"게이트 ID: {gate_order.get('id')}\n"
                    f"방향: {side.upper()}\n"
                    f"트리거가: ${trigger_price:,.2f}\n"
                    f"트리거 타입: {gate_trigger_type.upper()}\n\n"
                    f"💰 실제 달러 마진 동적 비율 복제:\n"
                    f"비트겟 실제 마진: ${bitget_required_margin:,.2f}\n"
                    f"실제 마진 비율: {margin_ratio*100:.2f}%\n"
                    f"게이트 투입 마진: ${gate_margin:,.2f} (동일 {margin_ratio*100:.2f}%)\n"
                    f"🔧 레버리지 완전 동기화: {bitget_leverage}x"
                )
                
                return "success"
                
            except Exception as e:
                self.logger.error(f"게이트 예약 주문 생성 실패: {e}")
                return "failed"
                
        except Exception as e:
            self.logger.error(f"예약 주문 복제 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'plan_order_id': bitget_order.get('orderId', bitget_order.get('planOrderId', 'unknown'))
            })
            return "failed"
    
    async def _calculate_dynamic_margin_ratio(self, size: float, trigger_price: float, bitget_order: Dict) -> Dict:
        """실제 달러 마진 비율 동적 계산"""
        try:
            # 레버리지 정보 정확하게 추출
            bitget_leverage = 10  # 기본값
            
            # 주문에서 직접 레버리지 추출
            order_leverage = bitget_order.get('leverage')
            if order_leverage:
                try:
                    bitget_leverage = int(float(order_leverage))
                except:
                    pass
            
            # 계정 정보에서 레버리지 추출
            if not order_leverage:
                try:
                    bitget_account = await self.bitget.get_account_info()
                    account_leverage = bitget_account.get('crossMarginLeverage')
                    if account_leverage:
                        bitget_leverage = int(float(account_leverage))
                except Exception as e:
                    self.logger.warning(f"계정 레버리지 조회 실패: {e}")
            
            # 비트겟 계정 정보 조회
            bitget_account = await self.bitget.get_account_info()
            bitget_total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            # 비트겟에서 이 주문이 체결될 때 사용할 실제 마진 계산
            bitget_notional_value = size * trigger_price
            bitget_required_margin = bitget_notional_value / bitget_leverage
            
            # 비트겟 총 자산 대비 실제 마진 투입 비율 계산
            if bitget_total_equity > 0:
                margin_ratio = bitget_required_margin / bitget_total_equity
            else:
                return {
                    'success': False,
                    'error': '비트겟 총 자산이 0이거나 음수입니다.'
                }
            
            return {
                'success': True,
                'margin_ratio': margin_ratio,
                'leverage': bitget_leverage,
                'required_margin': bitget_required_margin,
                'total_equity': bitget_total_equity,
                'notional_value': bitget_notional_value
            }
            
        except Exception as e:
            self.logger.error(f"실제 달러 마진 비율 동적 계산 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _handle_plan_order_cancel(self, bitget_order_id: str):
        """예약 주문 취소 처리"""
        try:
            # 미러링된 주문인지 확인
            if bitget_order_id not in self.mirrored_plan_orders:
                return
            
            mirror_info = self.mirrored_plan_orders[bitget_order_id]
            gate_order_id = mirror_info.get('gate_order_id')
            
            if gate_order_id:
                try:
                    await self.gate.cancel_price_triggered_order(gate_order_id)
                    
                    self.daily_stats['plan_order_cancels'] += 1
                    
                    await self.telegram.send_message(
                        f"🚫✅ 예약 주문 취소 동기화 완료\n"
                        f"비트겟 ID: {bitget_order_id}\n"
                        f"게이트 ID: {gate_order_id}"
                    )
                    
                except Exception as e:
                    self.logger.error(f"게이트 예약 주문 취소 실패: {e}")
                    
                    if "not found" in str(e).lower():
                        await self.telegram.send_message(
                            f"🚫⚠️ 예약 주문 취소 처리\n"
                            f"비트겟 ID: {bitget_order_id}\n"
                            f"게이트 주문이 이미 취소되었거나 체결되었습니다."
                        )
                    else:
                        await self.telegram.send_message(
                            f"❌ 예약 주문 취소 실패\n"
                            f"비트겟 ID: {bitget_order_id}\n"
                            f"오류: {str(e)[:200]}"
                        )
            
            # 미러링 기록에서 제거
            del self.mirrored_plan_orders[bitget_order_id]
            
        except Exception as e:
            self.logger.error(f"예약 주문 취소 처리 실패: {e}")
    
    async def monitor_order_fills(self):
        """실시간 주문 체결 감지"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                filled_orders = await self.bitget.get_recent_filled_orders(
                    symbol=self.SYMBOL, 
                    minutes=1
                )
                
                new_orders_count = 0
                for order in filled_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if not order_id:
                        continue
                    
                    if order_id in self.processed_orders:
                        continue
                    
                    reduce_only = order.get('reduceOnly', 'false')
                    if reduce_only == 'true' or reduce_only is True:
                        continue
                    
                    await self._process_filled_order(order)
                    self.processed_orders.add(order_id)
                    new_orders_count += 1
                
                # 오래된 주문 ID 정리
                if len(self.processed_orders) > 1000:
                    recent_orders = list(self.processed_orders)[-500:]
                    self.processed_orders = set(recent_orders)
                
                consecutive_errors = 0
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"주문 체결 감지 중 오류: {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 주문 체결 감지 시스템 오류\n"
                        f"연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL * 2)
    
    async def _process_filled_order(self, order: Dict):
        """체결된 주문으로부터 미러링 실행"""
        try:
            order_id = order.get('orderId', order.get('id', ''))
            side = order.get('side', '').lower()
            size = float(order.get('size', 0))
            fill_price = float(order.get('fillPrice', order.get('price', 0)))
            
            position_side = 'long' if side == 'buy' else 'short'
            
            # 체결된 주문의 실제 달러 마진 비율 동적 계산
            margin_ratio_result = await self._calculate_dynamic_margin_ratio_for_filled_order(
                size, fill_price, order
            )
            
            if not margin_ratio_result['success']:
                return
            
            leverage = margin_ratio_result['leverage']
            
            # 가상의 포지션 데이터 생성
            synthetic_position = {
                'symbol': self.SYMBOL,
                'holdSide': position_side,
                'total': str(size),
                'openPriceAvg': str(fill_price),
                'markPrice': str(fill_price),
                'marginSize': str(margin_ratio_result['required_margin']),
                'leverage': str(leverage),
                'marginMode': 'crossed',
                'unrealizedPL': '0'
            }
            
            pos_id = f"{self.SYMBOL}_{position_side}_{fill_price}"
            
            if pos_id in self.startup_positions:
                return
            
            if pos_id in self.mirrored_positions:
                return
            
            # 미러링 실행
            result = await self._mirror_new_position(synthetic_position)
            
            if result.success:
                self.mirrored_positions[pos_id] = await self._create_position_info(synthetic_position)
                self.position_sizes[pos_id] = size
                self.daily_stats['successful_mirrors'] += 1
                self.daily_stats['order_mirrors'] += 1
                
                await self.telegram.send_message(
                    f"⚡ 실시간 주문 체결 미러링 성공\n"
                    f"주문 ID: {order_id}\n"
                    f"방향: {position_side}\n"
                    f"체결가: ${fill_price:,.2f}\n"
                    f"수량: {size}\n"
                    f"🔧 레버리지: {leverage}x\n"
                    f"💰 실제 마진 비율: {margin_ratio_result['margin_ratio']*100:.2f}%"
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
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'order_id': order.get('orderId', 'unknown')
            })
    
    async def _calculate_dynamic_margin_ratio_for_filled_order(self, size: float, fill_price: float, order: Dict) -> Dict:
        """체결된 주문의 실제 달러 마진 비율 동적 계산"""
        try:
            leverage = 10
            try:
                order_leverage = order.get('leverage')
                if order_leverage:
                    leverage = int(float(order_leverage))
                else:
                    account = await self.bitget.get_account_info()
                    if account:
                        account_leverage = account.get('crossMarginLeverage')
                        if account_leverage:
                            leverage = int(float(account_leverage))
            except Exception as e:
                self.logger.warning(f"체결 주문 레버리지 조회 실패: {e}")
            
            bitget_account = await self.bitget.get_account_info()
            bitget_total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            notional = size * fill_price
            required_margin = notional / leverage
            margin_ratio = required_margin / bitget_total_equity if bitget_total_equity > 0 else 0
            
            return {
                'success': True,
                'margin_ratio': margin_ratio,
                'leverage': leverage,
                'required_margin': required_margin,
                'total_equity': bitget_total_equity,
                'notional_value': notional
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _record_startup_positions(self):
        """시작 시 존재하는 포지션 기록"""
        try:
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    pos_id = self._generate_position_id(pos)
                    self.startup_positions.add(pos_id)
                    self.position_sizes[pos_id] = float(pos.get('total', 0))
            
            # 기존 주문 ID들도 기록
            try:
                recent_orders = await self.bitget.get_recent_filled_orders(self.SYMBOL, minutes=10)
                for order in recent_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if order_id:
                        self.processed_orders.add(order_id)
            except Exception as e:
                self.logger.warning(f"기존 주문 기록 실패: {e}")
            
        except Exception as e:
            self.logger.error(f"기존 포지션 기록 실패: {e}")
    
    async def _log_account_status(self):
        """계정 상태 로깅 - 개선된 메시지"""
        try:
            bitget_account = await self.bitget.get_account_info()
            bitget_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            bitget_leverage = bitget_account.get('crossMarginLeverage', 'N/A')
            
            gate_account = await self.gate.get_account_balance()
            gate_equity = float(gate_account.get('total', 0))
            
            position_mode_text = "포지션 없음 - 모든 예약 주문 복제" if not self.has_startup_positions else "포지션 있음 - 클로즈 TP/SL 제외하고 복제"
            
            await self.telegram.send_message(
                f"🔥🔥🔥 실제 달러 마진 비율 동적 계산 + 예약 주문 완전 복제 미러 트레이딩 시작\n\n"
                f"💰 계정 잔고:\n"
                f"• 비트겟: ${bitget_equity:,.2f} (레버리지: {bitget_leverage}x)\n"
                f"• 게이트: ${gate_equity:,.2f}\n\n"
                f"🔥🔥🔥 핵심 원리:\n"
                f"매 주문/포지션마다 실제 달러 투입금 비율을 새로 계산!\n\n"
                f"💰💰💰 실제 달러 마진 비율 동적 계산 원리:\n"
                f"1️⃣ 비트겟에서 주문 체결 또는 예약 주문 생성\n"
                f"2️⃣ 해당 주문의 실제 마진 = (수량 × 가격) ÷ 레버리지\n"
                f"3️⃣ 실제 마진 비율 = 실제 마진 ÷ 비트겟 총 자산\n"
                f"4️⃣ 게이트 투입 마진 = 게이트 총 자산 × 동일 비율\n"
                f"5️⃣ 매 거래마다 실시간으로 비율을 새로 계산\n\n"
                f"🔥🔥🔥 개선된 트리거 가격 검증:\n"
                f"• 트리거가 > 현재가 → ge 트리거 (상승 돌파)\n"
                f"• 트리거가 < 현재가 → le 트리거 (하락 돌파)\n"
                f"• 주문 방향과 무관하게 가격 관계로만 판단\n\n"
                f"📊 기존 항목:\n"
                f"• 기존 포지션: {len(self.startup_positions)}개 (복제 제외)\n"
                f"• 기존 예약 주문: {len(self.startup_plan_orders)}개 (시작 시 복제)\n"
                f"• 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개\n\n"
                f"🔥🔥🔥 예약 주문 복제 정책:\n"
                f"• {position_mode_text}\n"
                f"• 보유 포지션: {len(self.startup_positions)}개\n"
                f"• 제외할 클로즈 TP/SL: {len(self.startup_position_tp_sl)}개\n\n"
                f"⚡ 감지 주기:\n"
                f"• 예약 주문: {self.PLAN_ORDER_CHECK_INTERVAL}초마다\n"
                f"• 주문 체결: {self.ORDER_CHECK_INTERVAL}초마다\n\n"
                f"💡 예시:\n"
                f"비트겟 총 자산 $10,000에서 $200 마진 투입 (2%)\n"
                f"→ 게이트 총 자산 $1,000에서 $20 마진 투입 (동일 2%)\n"
                f"→ 매 거래마다 실시간으로 이 비율을 새로 계산!"
            )
            
        except Exception as e:
            self.logger.error(f"계정 상태 조회 실패: {e}")
    
    async def monitor_positions(self):
        """포지션 모니터링"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                
                active_position_ids = set()
                
                for pos in bitget_positions:
                    if float(pos.get('total', 0)) > 0:
                        pos_id = self._generate_position_id(pos)
                        active_position_ids.add(pos_id)
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
                self.logger.error(f"포지션 모니터링 중 오류: {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 포지션 모니터링 오류\n"
                        f"연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(self.CHECK_INTERVAL * 2)
    
    async def _process_position(self, bitget_pos: Dict):
        """포지션 처리"""
        try:
            pos_id = self._generate_position_id(bitget_pos)
            
            if pos_id in self.startup_positions:
                return
            
            current_size = float(bitget_pos.get('total', 0))
            
            if pos_id not in self.mirrored_positions:
                await asyncio.sleep(2)
                
                if pos_id not in self.mirrored_positions:
                    result = await self._mirror_new_position(bitget_pos)
                    
                    if result.success:
                        self.mirrored_positions[pos_id] = await self._create_position_info(bitget_pos)
                        self.position_sizes[pos_id] = current_size
                        self.daily_stats['successful_mirrors'] += 1
                        self.daily_stats['position_mirrors'] += 1
                        
                        leverage = bitget_pos.get('leverage', 'N/A')
                        await self.telegram.send_message(
                            f"✅ 포지션 기반 미러링 성공\n"
                            f"방향: {bitget_pos.get('holdSide', '')}\n"
                            f"진입가: ${float(bitget_pos.get('openPriceAvg', 0)):,.2f}\n"
                            f"🔧 레버리지: {leverage}x"
                        )
                    else:
                        self.failed_mirrors.append(result)
                        self.daily_stats['failed_mirrors'] += 1
                    
                    self.daily_stats['total_mirrored'] += 1
            else:
                last_size = self.position_sizes.get(pos_id, 0)
                
                # 부분 청산 감지
                if current_size < last_size * 0.95:
                    reduction_ratio = 1 - (current_size / last_size)
                    await self._handle_partial_close(pos_id, bitget_pos, reduction_ratio)
                    self.position_sizes[pos_id] = current_size
                    self.daily_stats['partial_closes'] += 1
                
        except Exception as e:
            self.logger.error(f"포지션 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'position': self._generate_position_id(bitget_pos)
            })
    
    async def _mirror_new_position(self, bitget_pos: Dict) -> MirrorResult:
        """새로운 포지션 미러링"""
        retry_count = 0
        
        while retry_count < self.MAX_RETRIES:
            try:
                margin_ratio = await self._calculate_margin_ratio(bitget_pos)
                
                if margin_ratio is None:
                    return MirrorResult(
                        success=False,
                        action="new_position",
                        bitget_data=bitget_pos,
                        error="마진 비율 계산 실패"
                    )
                
                gate_account = await self.gate.get_account_balance()
                gate_available = float(gate_account.get('available', 0))
                gate_margin = gate_available * margin_ratio
                
                if gate_margin < self.MIN_MARGIN:
                    return MirrorResult(
                        success=False,
                        action="new_position",
                        bitget_data=bitget_pos,
                        error=f"게이트 마진 부족: ${gate_margin:.2f}"
                    )
                
                leverage = int(float(bitget_pos.get('leverage', 1)))
                
                # 게이트 레버리지 설정
                try:
                    await self.gate.set_leverage(self.GATE_CONTRACT, leverage)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    self.logger.error(f"❌ 게이트 레버리지 설정 실패: {e}")
                
                side = bitget_pos.get('holdSide', '').lower()
                current_price = float(bitget_pos.get('markPrice', bitget_pos.get('openPriceAvg', 0)))
                
                contract_info = await self.gate.get_contract_info(self.GATE_CONTRACT)
                quanto_multiplier = float(contract_info.get('quanto_multiplier', 0.0001))
                
                notional_value = gate_margin * leverage
                gate_size = int(notional_value / (current_price * quanto_multiplier))
                
                if gate_size == 0:
                    gate_size = 1
                
                if side == 'short':
                    gate_size = -gate_size
                
                # 진입 주문
                order_result = await self.gate.place_order(
                    contract=self.GATE_CONTRACT,
                    size=gate_size,
                    price=None,
                    reduce_only=False
                )
                
                await asyncio.sleep(1)
                tp_sl_result = await self._set_gate_tp_sl(bitget_pos, gate_size)
                
                self.daily_stats['total_volume'] += abs(notional_value)
                
                return MirrorResult(
                    success=True,
                    action="new_position",
                    bitget_data=bitget_pos,
                    gate_data={
                        'order': order_result,
                        'size': gate_size,
                        'margin': gate_margin,
                        'leverage': leverage,
                        'tp_sl': tp_sl_result
                    }
                )
                
            except Exception as e:
                retry_count += 1
                error_msg = str(e)
                
                if retry_count < self.MAX_RETRIES:
                    wait_time = 2 ** retry_count
                    await asyncio.sleep(wait_time)
                else:
                    return MirrorResult(
                        success=False,
                        action="new_position",
                        bitget_data=bitget_pos,
                        error=f"최대 재시도 횟수 초과: {error_msg}"
                    )
    
    async def _calculate_margin_ratio(self, bitget_pos: Dict) -> Optional[float]:
        """비트겟 포지션의 마진 비율 계산"""
        try:
            bitget_account = await self.bitget.get_account_info()
            total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            position_margin = float(bitget_pos.get('marginSize', bitget_pos.get('margin', 0)))
            
            if total_equity <= 0 or position_margin <= 0:
                return None
            
            margin_ratio = position_margin / total_equity
            
            return margin_ratio
            
        except Exception as e:
            self.logger.error(f"마진 비율 계산 실패: {e}")
            return None
    
    async def _set_gate_tp_sl(self, bitget_pos: Dict, gate_size: int) -> Dict:
        """게이트에 TP/SL 설정 - 간소화"""
        try:
            # 기본 TP/SL만 설정
            entry_price = float(bitget_pos.get('openPriceAvg', 0))
            side = bitget_pos.get('holdSide', '').lower()
            
            tp_orders = []
            sl_orders = []
            
            if side == 'long':
                tp_price = entry_price * 1.02  # 2% TP
                sl_price = entry_price * 0.98  # 2% SL
                
                if abs(gate_size) > 0:
                    tp_order = await self.gate.create_price_triggered_order(
                        trigger_type="ge",
                        trigger_price=str(tp_price),
                        order_type="market",
                        contract=self.GATE_CONTRACT,
                        size=-abs(gate_size)
                    )
                    tp_orders.append(tp_order)
                    
                    sl_order = await self.gate.create_price_triggered_order(
                        trigger_type="le",
                        trigger_price=str(sl_price),
                        order_type="market",
                        contract=self.GATE_CONTRACT,
                        size=-abs(gate_size)
                    )
                    sl_orders.append(sl_order)
            else:
                tp_price = entry_price * 0.98  # 2% TP
                sl_price = entry_price * 1.02  # 2% SL
                
                if abs(gate_size) > 0:
                    tp_order = await self.gate.create_price_triggered_order(
                        trigger_type="le",
                        trigger_price=str(tp_price),
                        order_type="market",
                        contract=self.GATE_CONTRACT,
                        size=abs(gate_size)
                    )
                    tp_orders.append(tp_order)
                    
                    sl_order = await self.gate.create_price_triggered_order(
                        trigger_type="ge",
                        trigger_price=str(sl_price),
                        order_type="market",
                        contract=self.GATE_CONTRACT,
                        size=abs(gate_size)
                    )
                    sl_orders.append(sl_order)
            
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
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            
            if not gate_positions or gate_positions[0].get('size', 0) == 0:
                return
            
            gate_pos = gate_positions[0]
            current_gate_size = int(gate_pos['size'])
            close_size = int(abs(current_gate_size) * reduction_ratio)
            
            if close_size == 0:
                return
            
            if current_gate_size > 0:
                close_size = -close_size
            else:
                close_size = close_size
            
            result = await self.gate.place_order(
                contract=self.GATE_CONTRACT,
                size=close_size,
                price=None,
                reduce_only=True
            )
            
            await self.telegram.send_message(
                f"📉 부분 청산 완료\n"
                f"비율: {reduction_ratio*100:.1f}%\n"
                f"수량: {abs(close_size)} 계약"
            )
            
        except Exception as e:
            self.logger.error(f"부분 청산 처리 실패: {e}")
    
    async def _handle_position_close(self, pos_id: str):
        """포지션 종료 처리"""
        try:
            result = await self.gate.close_position(self.GATE_CONTRACT)
            
            # TP/SL 주문 취소
            if pos_id in self.tp_sl_orders:
                orders = self.tp_sl_orders[pos_id]
                
                for order_id in orders.get('tp', []):
                    try:
                        await self.gate.cancel_price_triggered_order(order_id)
                    except:
                        pass
                
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
    
    async def monitor_sync_status(self):
        """포지션 동기화 상태 모니터링 - 개선된 메시지"""
        while self.monitoring:
            try:
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)
                
                bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                bitget_active = [
                    pos for pos in bitget_positions 
                    if float(pos.get('total', 0)) > 0
                ]
                
                gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
                gate_active = [
                    pos for pos in gate_positions 
                    if pos.get('size', 0) != 0
                ]
                
                mirrored_bitget_count = sum(
                    1 for pos in bitget_active 
                    if self._generate_position_id(pos) not in self.startup_positions
                )
                
                # 🔥 개선된 상태 표시
                current_mirrored_plan_orders = len(self.mirrored_plan_orders)
                
                if mirrored_bitget_count != len(gate_active):
                    self.logger.warning(
                        f"⚠️ 포지션 불일치 감지\n"
                        f"비트겟: {mirrored_bitget_count}\n"
                        f"게이트: {len(gate_active)}\n"
                        f"현재 복제된 예약 주문: {current_mirrored_plan_orders}개"
                    )
                
            except Exception as e:
                self.logger.error(f"동기화 모니터링 오류: {e}")
    
    async def generate_daily_reports(self):
        """일일 리포트 생성"""
        while self.monitoring:
            try:
                now = datetime.now()
                
                if now.hour == self.DAILY_REPORT_HOUR and now > self.last_report_time + timedelta(hours=23):
                    report = await self._create_daily_report()
                    await self.telegram.send_message(report)
                    
                    self._reset_daily_stats()
                    self.last_report_time = now
                
                await asyncio.sleep(3600)
                
            except Exception as e:
                self.logger.error(f"일일 리포트 생성 오류: {e}")
                await asyncio.sleep(3600)
    
    async def _create_daily_report(self) -> str:
        """일일 리포트 생성 - 개선된 통계"""
        try:
            bitget_account = await self.bitget.get_account_info()
            gate_account = await self.gate.get_account_balance()
            
            bitget_equity = float(bitget_account.get('accountEquity', 0))
            gate_equity = float(gate_account.get('total', 0))
            bitget_leverage = bitget_account.get('crossMarginLeverage', 'N/A')
            
            success_rate = 0
            if self.daily_stats['total_mirrored'] > 0:
                success_rate = (self.daily_stats['successful_mirrors'] / 
                              self.daily_stats['total_mirrored']) * 100
            
            report = f"""📊 일일 실제 달러 마진 비율 동적 계산 + 완전 복제 미러 트레이딩 리포트
📅 {datetime.now().strftime('%Y-%m-%d')}
━━━━━━━━━━━━━━━━━━━

🔥 예약 주문 실제 달러 마진 비율 동적 계산 성과
- 시작 시 예약 주문 복제: {self.daily_stats['startup_plan_mirrors']}회
- 신규 예약 주문 미러링: {self.daily_stats['plan_order_mirrors']}회
- 예약 주문 취소 동기화: {self.daily_stats['plan_order_cancels']}회
- 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개
- 이미 복제됨으로 스킵: {self.daily_stats['plan_order_skipped_already_mirrored']}개
- 트리거 가격 문제로 스킵: {self.daily_stats['plan_order_skipped_trigger_price']}개

⚡ 실시간 포지션 미러링
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

💰 계정 잔고
- 비트겟: ${bitget_equity:,.2f} (레버리지: {bitget_leverage}x)
- 게이트: ${gate_equity:,.2f}

🔄 현재 미러링 상태
- 활성 포지션: {len(self.mirrored_positions)}개
- 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개
- 실패 기록: {len(self.failed_mirrors)}건

💰💰💰 실제 달러 마진 비율 동적 계산 (핵심)
- 매 예약주문마다 실제 마진 비율을 새로 계산
- 미리 정해진 비율 없음 - 완전 동적 계산

🔥🔥🔥 개선된 트리거 검증 (핵심)
- 트리거가 > 현재가 → ge 트리거 (상승 돌파)
- 트리거가 < 현재가 → le 트리거 (하락 돌파)
- 주문 방향과 무관하게 가격 관계로만 판단
"""
            
            if self.daily_stats['errors']:
                report += f"\n⚠️ 오류 발생: {len(self.daily_stats['errors'])}건"
            
            report += "\n━━━━━━━━━━━━━━━━━━━\n🔥 완전한 실제 달러 마진 비율 동적 계산!"
            
            return report
            
        except Exception as e:
            self.logger.error(f"리포트 생성 실패: {e}")
            return f"📊 일일 리포트 생성 실패\n오류: {str(e)}"
    
    def _reset_daily_stats(self):
        """일일 통계 초기화 - 개선된 통계"""
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
            'plan_order_skipped_already_mirrored': 0,
            'plan_order_skipped_trigger_price': 0,
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
        
        try:
            final_report = await self._create_daily_report()
            await self.telegram.send_message(
                f"🛑 실제 달러 마진 비율 동적 계산 + 완전 복제 미러 트레이딩 종료\n\n{final_report}"
            )
        except:
            pass
        
        self.logger.info("실제 달러 마진 비율 동적 계산 + 완전 복제 미러 트레이딩 시스템 중지")
