import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class PositionInfo:
    """포지션 정보"""
    symbol: str
    side: str
    size: float
    entry_price: float
    margin: float
    leverage: int
    mode: str
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

class MirrorTradingUtils:
    """🔥🔥🔥 미러 트레이딩 유틸리티 클래스 - 정확한 심볼 사용"""
    
    def __init__(self, config, bitget_client, gate_client):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.logger = logging.getLogger('mirror_trading_utils')
        
        # 🔥🔥🔥 정확한 심볼 설정
        self.SYMBOL = "BTCUSDT"  # Bitget 정확한 심볼
        self.GATE_CONTRACT = "BTC_USDT"
        self.MIN_MARGIN = 1.0
        self.MAX_PRICE_DIFF_PERCENT = 50.0  # 🔥🔥🔥 매우 관대하게 설정 (50%)
        
        # 🔥🔥🔥 트리거 가격 검증 완전히 제거 - 모든 가격 허용
        self.TRIGGER_PRICE_MIN_DIFF_PERCENT = 0.0
        self.ALLOW_VERY_CLOSE_PRICES = True
        
        # 🔥🔥🔥 시세 차이 관리 매우 관대하게 - 처리 차단 없음
        self.PRICE_SYNC_THRESHOLD = 1000.0  # 100달러 → 1000달러로 대폭 상향
        self.PRICE_ADJUSTMENT_ENABLED = True
        
        # 🔥🔥🔥 비정상적인 시세 차이 감지 임계값도 매우 관대하게
        self.ABNORMAL_PRICE_DIFF_THRESHOLD = 10000.0  # 2000달러 → 10000달러로 대폭 상향
        
        self.logger.info("🔥🔥🔥 미러 트레이딩 유틸리티 초기화 완료 - 정확한 심볼 사용")
    
    async def extract_tp_sl_from_bitget_order(self, bitget_order: Dict) -> Tuple[Optional[float], Optional[float]]:
        """비트겟 예약 주문에서 TP/SL 정보 추출"""
        try:
            tp_price = None
            sl_price = None
            
            # TP 가격 추출
            tp_fields = ['presetStopSurplusPrice', 'stopSurplusPrice', 'takeProfitPrice', 'tpPrice']
            
            for field in tp_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        tp_price = float(value)
                        if tp_price > 0:
                            self.logger.info(f"🎯 TP 가격 추출: {field} = {tp_price}")
                            break
                    except:
                        continue
            
            # SL 가격 추출
            sl_fields = ['presetStopLossPrice', 'stopLossPrice', 'stopPrice', 'slPrice']
            
            for field in sl_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        sl_price = float(value)
                        if sl_price > 0:
                            self.logger.info(f"🛡️ SL 가격 추출: {field} = {sl_price}")
                            break
                    except:
                        continue
            
            return tp_price, sl_price
            
        except Exception as e:
            self.logger.error(f"TP/SL 정보 추출 실패: {e}")
            return None, None
    
    async def extract_gate_order_details(self, gate_order: Dict) -> Optional[Dict]:
        """게이트 주문에서 상세 정보 추출 - 더 관대한 처리"""
        try:
            # 기본 정보 추출 - None 체크 강화
            order_id = gate_order.get('id', '') or ''
            contract = gate_order.get('contract', self.GATE_CONTRACT) or self.GATE_CONTRACT
            
            # 트리거 정보 추출 - None 체크
            trigger_info = gate_order.get('trigger', {}) or {}
            trigger_price_raw = trigger_info.get('price')
            
            if trigger_price_raw is None or trigger_price_raw == '':
                self.logger.debug(f"트리거 가격이 None 또는 빈 값: {gate_order}")
                return None
            
            try:
                trigger_price = float(trigger_price_raw)
            except (ValueError, TypeError):
                self.logger.debug(f"트리거 가격 변환 실패: {trigger_price_raw}")
                return None
            
            # 초기 주문 정보 추출 - None 체크 및 더 관대한 처리
            initial_info = gate_order.get('initial', {}) or {}
            size_raw = initial_info.get('size')
            
            # 🔥🔥🔥 수정: size가 없거나 0이어도 기본값 사용
            size = 1  # 기본값
            if size_raw is not None:
                try:
                    size = int(size_raw)
                except (ValueError, TypeError):
                    self.logger.debug(f"사이즈 변환 실패, 기본값 사용: {size_raw}")
                    size = 1
            else:
                self.logger.debug(f"사이즈가 None, 기본값 사용: {gate_order}")
            
            # TP/SL 정보 추출 - None 체크 강화
            tp_price = None
            sl_price = None
            
            for tp_field in ['stop_profit_price', 'stopProfitPrice', 'takeProfitPrice']:
                tp_value = gate_order.get(tp_field)
                if tp_value and tp_value != '' and str(tp_value) != '0':
                    try:
                        tp_price = float(tp_value)
                        if tp_price > 0:
                            break
                    except (ValueError, TypeError):
                        continue
            
            for sl_field in ['stop_loss_price', 'stopLossPrice', 'stopPrice']:
                sl_value = gate_order.get(sl_field)
                if sl_value and sl_value != '' and str(sl_value) != '0':
                    try:
                        sl_price = float(sl_value)
                        if sl_price > 0:
                            break
                    except (ValueError, TypeError):
                        continue
            
            return {
                'order_id': order_id,
                'contract': contract,
                'trigger_price': trigger_price,
                'size': size,
                'tp_price': tp_price,
                'sl_price': sl_price,
                'has_tp_sl': tp_price is not None or sl_price is not None,
                'raw_order': gate_order
            }
            
        except Exception as e:
            self.logger.error(f"게이트 주문 상세 정보 추출 실패: {e}")
            return None
    
    async def adjust_price_for_sync(self, price: float, bitget_current_price: float = 0, gate_current_price: float = 0) -> float:
        """🔥🔥🔥 가격 동기화 조정 - 매우 관대한 처리"""
        try:
            if price is None or price <= 0:
                return price or 0
            
            # 🔥🔥🔥 시세 조회가 성공한 경우에만 조정 고려
            if bitget_current_price > 0 and gate_current_price > 0:
                price_diff_abs = abs(bitget_current_price - gate_current_price)
                
                # 🔥🔥🔥 매우 큰 차이(1000달러 이상)에서만 조정 고려
                if price_diff_abs > self.PRICE_SYNC_THRESHOLD:
                    # 게이트 기준으로 조정
                    price_diff_percent = price_diff_abs / bitget_current_price * 100
                    
                    if gate_current_price > bitget_current_price:
                        # 게이트가 더 높은 경우
                        adjusted_price = price * (gate_current_price / bitget_current_price)
                    else:
                        # 비트겟이 더 높은 경우
                        adjusted_price = price * (gate_current_price / bitget_current_price)
                    
                    adjustment_percent = abs(adjusted_price - price) / price * 100
                    
                    # 🔥🔥🔥 조정 폭이 50% 이하인 경우에만 적용
                    if adjustment_percent <= 50.0:  # 10% → 50%로 매우 관대하게
                        self.logger.info(f"🔧 가격 조정: ${price:.2f} → ${adjusted_price:.2f} (차이: ${price_diff_abs:.2f})")
                        return adjusted_price
                    else:
                        self.logger.info(f"조정 폭이 크지만 원본 가격으로 처리 진행 ({adjustment_percent:.1f}%)")
                        return price  # 조정하지 않고 처리 계속
                else:
                    return price
            elif bitget_current_price <= 0 or gate_current_price <= 0:
                self.logger.debug("시세 조회 실패이지만 처리 계속 진행")
                return price
            
            return price
            
        except Exception as e:
            self.logger.error(f"가격 조정 실패하지만 처리 계속 진행: {e}")
            return price or 0
    
    async def validate_trigger_price(self, trigger_price: float, side: str, current_price: float = 0) -> Tuple[bool, str]:
        """🔥🔥🔥 트리거 가격 유효성 검증 - 모든 가격 허용 (처리 차단 없음)"""
        try:
            if trigger_price is None or trigger_price <= 0:
                return False, "트리거 가격이 None이거나 0 이하입니다"
            
            if current_price <= 0:
                self.logger.info("현재가 조회 실패하지만 모든 트리거 가격 허용")
                return True, "현재가 조회 실패하지만 허용"
            
            # 🔥🔥🔥 모든 가격 차이 허용 - 처리 차단 없음
            price_diff_percent = abs(trigger_price - current_price) / current_price * 100
            price_diff_abs = abs(trigger_price - current_price)
            
            # 🔥🔥🔥 극도로 높은 임계값으로 비정상적인 가격 차이 감지 (10000달러)
            if price_diff_abs > self.ABNORMAL_PRICE_DIFF_THRESHOLD:
                self.logger.info(f"매우 큰 가격 차이이지만 처리 허용: ${price_diff_abs:.2f}")
                return True, f"큰 가격 차이이지만 허용 (${price_diff_abs:.2f})"
            
            # 🔥🔥🔥 모든 가격 무조건 허용
            return True, f"모든 트리거 가격 허용 (차이: {price_diff_percent:.4f}%)"
            
        except Exception as e:
            self.logger.error(f"트리거 가격 검증 실패하지만 허용: {e}")
            return True, f"검증 오류이지만 모든 가격 허용: {str(e)[:100]}"
    
    async def determine_close_order_details(self, bitget_order: Dict) -> Dict:
        """🔥🔥🔥 클로즈 주문 세부 사항 정확하게 판단"""
        try:
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            reduce_only = bitget_order.get('reduceOnly', False)
            
            # 클로즈 주문 여부 판단
            is_close_order = (
                'close' in side or 
                reduce_only is True or 
                reduce_only == 'true' or
                str(reduce_only).lower() == 'true'
            )
            
            self.logger.info(f"🔍 클로즈 주문 분석: side='{side}', reduce_only={reduce_only}, is_close_order={is_close_order}")
            
            # 포지션 방향 결정
            if 'long' in side or 'buy' in side:
                if is_close_order:
                    return {
                        'is_close_order': True,
                        'position_side': 'long',
                        'order_direction': 'sell',
                        'close_type': 'long_close'
                    }
                else:
                    return {
                        'is_close_order': False,
                        'position_side': 'long',
                        'order_direction': 'buy',
                        'close_type': 'none'
                    }
            elif 'short' in side or 'sell' in side:
                if is_close_order:
                    return {
                        'is_close_order': True,
                        'position_side': 'short',
                        'order_direction': 'buy',
                        'close_type': 'short_close'
                    }
                else:
                    return {
                        'is_close_order': False,
                        'position_side': 'short',
                        'order_direction': 'sell',
                        'close_type': 'none'
                    }
            else:
                # 기본값
                return {
                    'is_close_order': is_close_order,
                    'position_side': 'long',
                    'order_direction': 'buy',
                    'close_type': 'unknown'
                }
                
        except Exception as e:
            self.logger.error(f"클로즈 주문 세부사항 판단 실패: {e}")
            return {
                'is_close_order': False,
                'position_side': 'long',
                'order_direction': 'buy',
                'close_type': 'error'
            }
    
    def determine_gate_order_type(self, side: str, is_close_order: bool = False) -> str:
        """게이트 주문 타입 결정"""
        try:
            if is_close_order:
                # 클로즈 주문인 경우
                if 'buy' in side.lower() or 'long' in side.lower():
                    return "gc"  # gate close (buy to close short)
                else:
                    return "gc"  # gate close (sell to close long)
            else:
                # 일반 주문인 경우
                if 'buy' in side.lower() or 'long' in side.lower():
                    return "ge"  # gate entry (buy/long)
                else:
                    return "ge"  # gate entry (sell/short)
        except Exception as e:
            self.logger.error(f"게이트 주문 타입 결정 실패: {e}")
            return "ge"
    
    async def get_current_gate_position_size(self, gate_mirror_client, position_side: str = None) -> Tuple[int, str]:
        """🔥🔥🔥 현재 게이트 포지션 크기 조회"""
        try:
            gate_positions = await gate_mirror_client.get_positions(self.GATE_CONTRACT)
            
            if not gate_positions:
                self.logger.info("🔍 게이트에 포지션이 없음")
                return 0, 'none'
            
            position = gate_positions[0]
            current_size = int(position.get('size', 0))
            
            if current_size == 0:
                self.logger.info("🔍 게이트 포지션 크기가 0")
                return 0, 'none'
            
            # 포지션 방향 확인
            current_side = 'long' if current_size > 0 else 'short'
            
            # 특정 방향이 요청된 경우 매칭 확인
            if position_side and current_side != position_side:
                self.logger.warning(f"⚠️ 요청된 포지션 방향({position_side})과 현재 포지션 방향({current_side})이 다름")
                return current_size, current_side  # 실제 정보 반환
            
            self.logger.info(f"✅ 현재 게이트 포지션: {current_size} ({current_side})")
            return current_size, current_side
            
        except Exception as e:
            self.logger.error(f"현재 게이트 포지션 크기 조회 실패: {e}")
            return 0, 'error'
    
    async def validate_close_order_against_position(self, close_order_details: Dict, 
                                                   current_gate_position_size: int) -> Tuple[bool, str]:
        """🔥🔥🔥 클로즈 주문과 현재 포지션 간의 유효성 검증"""
        try:
            if current_gate_position_size == 0:
                return False, "현재 포지션이 없어 클로즈 주문 불가"
            
            # 현재 포지션 방향
            current_position_side = 'long' if current_gate_position_size > 0 else 'short'
            
            # 클로즈 주문에서 예상하는 포지션 방향
            expected_position_side = close_order_details['position_side']
            
            if current_position_side != expected_position_side:
                return True, f"포지션 방향 불일치하지만 현재 포지션({current_position_side})에 맞게 조정 가능"
            
            return True, f"클로즈 주문 유효: {current_position_side} 포지션 → {close_order_details['order_direction']} 주문"
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 유효성 검증 실패: {e}")
            return False, f"검증 오류: {str(e)}"
    
    async def calculate_dynamic_margin_ratio(self, size: float, trigger_price: float, bitget_order: Dict) -> Dict:
        """실제 달러 마진 비율 동적 계산"""
        try:
            if size is None or trigger_price is None:
                return {
                    'success': False,
                    'error': 'size 또는 trigger_price가 None입니다.'
                }
            
            # 레버리지 정보 추출 - 강화된 로직
            bitget_leverage = 10  # 기본값
            
            # 1. 직접 leverage 필드에서 추출
            if 'leverage' in bitget_order:
                try:
                    bitget_leverage = int(float(bitget_order['leverage']))
                except:
                    pass
            
            # 2. 마진 정보에서 역산
            elif 'marginSize' in bitget_order and bitget_order['marginSize']:
                try:
                    margin_size = float(bitget_order['marginSize'])
                    notional = size * trigger_price
                    if margin_size > 0 and notional > 0:
                        calculated_leverage = notional / margin_size
                        if 1 <= calculated_leverage <= 125:  # 합리적 범위
                            bitget_leverage = int(calculated_leverage)
                except:
                    pass
            
            # 3. 기타 필드들에서 추출 시도
            leverage_fields = ['presetLeverage', 'setLeverage', 'positionLeverage']
            for field in leverage_fields:
                if field in bitget_order and bitget_order[field]:
                    try:
                        bitget_leverage = int(float(bitget_order[field]))
                        break
                    except:
                        continue
            
            # 게이트 기본 마진 계산
            notional_value = size * trigger_price
            base_margin = notional_value / bitget_leverage
            
            # 최소 마진 확보
            final_margin = max(base_margin, self.MIN_MARGIN)
            
            # 실제 레버리지 계산
            actual_leverage = notional_value / final_margin
            
            return {
                'success': True,
                'gate_margin': final_margin,
                'gate_size': int(size),
                'margin_ratio': final_margin / notional_value,
                'bitget_leverage': bitget_leverage,
                'actual_leverage': actual_leverage,
                'notional_value': notional_value
            }
            
        except Exception as e:
            self.logger.error(f"동적 마진 비율 계산 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'gate_margin': self.MIN_MARGIN,
                'gate_size': int(size) if size else 1,
                'margin_ratio': 0.1,
                'bitget_leverage': 10,
                'actual_leverage': 10,
                'notional_value': size * trigger_price if size and trigger_price else 0
            }
    
    def generate_position_id(self, bitget_pos: Dict) -> str:
        """비트겟 포지션 ID 생성"""
        try:
            symbol = bitget_pos.get('symbol', self.SYMBOL)
            side = bitget_pos.get('side', 'long')
            return f"{symbol}_{side}"
        except Exception as e:
            self.logger.error(f"포지션 ID 생성 실패: {e}")
            return f"{self.SYMBOL}_unknown"
    
    def convert_to_position_info(self, bitget_pos: Dict) -> PositionInfo:
        """비트겟 포지션을 PositionInfo로 변환"""
        return PositionInfo(
            symbol=bitget_pos.get('symbol', self.SYMBOL),
            side=bitget_pos.get('side', 'long'),
            size=float(bitget_pos.get('total', 0)),
            entry_price=float(bitget_pos.get('openPriceAvg', 0)),
            margin=float(bitget_pos.get('marginSize', 0)),
            leverage=int(float(bitget_pos.get('leverage', 1))),
            mode='cross' if bitget_pos.get('marginMode') == 'crossed' else 'isolated',
            unrealized_pnl=float(bitget_pos.get('unrealizedPL', 0))
        )
    
    async def get_price_difference_info(self, bitget_price: float, gate_price: float) -> Dict:
        """시세 차이 정보 제공 - 정보 목적으로만 사용"""
        try:
            if bitget_price <= 0 or gate_price <= 0:
                return {
                    'price_diff_abs': 0,
                    'price_diff_percent': 0,
                    'exceeds_threshold': False,
                    'status': 'invalid_prices',
                    'is_abnormal': False,  # 🔥🔥🔥 처리 차단하지 않음
                    'should_process': True  # 🔥🔥🔥 항상 처리 진행
                }
            
            price_diff_abs = abs(bitget_price - gate_price)
            price_diff_percent = price_diff_abs / bitget_price * 100
            exceeds_threshold = price_diff_abs > self.PRICE_SYNC_THRESHOLD
            is_abnormal = price_diff_abs > self.ABNORMAL_PRICE_DIFF_THRESHOLD
            
            if is_abnormal:
                status = 'abnormal_difference'
            elif exceeds_threshold:
                status = 'high_difference'
            elif price_diff_abs > self.PRICE_SYNC_THRESHOLD * 0.5:
                status = 'moderate_difference'
            else:
                status = 'normal'
            
            return {
                'price_diff_abs': price_diff_abs,
                'price_diff_percent': price_diff_percent,
                'exceeds_threshold': exceeds_threshold,
                'threshold': self.PRICE_SYNC_THRESHOLD,
                'abnormal_threshold': self.ABNORMAL_PRICE_DIFF_THRESHOLD,
                'is_abnormal': is_abnormal,
                'status': status,
                'bitget_price': bitget_price,
                'gate_price': gate_price,
                'should_process': True  # 🔥🔥🔥 항상 처리 진행
            }
            
        except Exception as e:
            self.logger.error(f"시세 차이 정보 계산 실패: {e}")
            return {
                'price_diff_abs': 0,
                'price_diff_percent': 0,
                'exceeds_threshold': False,
                'status': 'error',
                'is_abnormal': False,
                'should_process': True  # 🔥🔥🔥 오류여도 처리 진행
            }
    
    async def should_delay_processing(self, bitget_price: float, gate_price: float) -> Tuple[bool, str]:
        """🔥🔥🔥 시세 차이로 인한 처리 지연 여부 판단 - 항상 처리 진행"""
        try:
            price_info = await self.get_price_difference_info(bitget_price, gate_price)
            
            # 🔥🔥🔥 모든 상황에서 처리 진행 - 지연 없음
            return False, "시세 차이와 무관하게 모든 주문 즉시 처리"
            
        except Exception as e:
            self.logger.error(f"처리 지연 판단 실패하지만 처리 진행: {e}")
            return False, "판단 오류여도 처리 진행"
