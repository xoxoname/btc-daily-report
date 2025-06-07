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
    """🔥🔥🔥 미러 트레이딩 유틸리티 클래스 - 게이트 예약주문 보호 강화"""
    
    def __init__(self, config, bitget_client, gate_client):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.logger = logging.getLogger('mirror_trading_utils')
        
        # 상수 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.MIN_MARGIN = 1.0
        
        # 🔥🔥🔥 모든 가격 차이 허용 - 처리 차단 없음
        self.MAX_PRICE_DIFF_PERCENT = 100.0  # 100%까지 허용 (모든 가격 허용)
        self.TRIGGER_PRICE_MIN_DIFF_PERCENT = 0.0  # 최소 차이 없음
        self.ALLOW_VERY_CLOSE_PRICES = True  # 매우 가까운 가격 허용
        
        # 🔥🔥🔥 시세 차이 관리 완전히 관대하게 - 처리 차단 절대 없음
        self.PRICE_SYNC_THRESHOLD = 10000.0  # 10,000달러까지 허용
        self.PRICE_ADJUSTMENT_ENABLED = True
        self.ABNORMAL_PRICE_DIFF_THRESHOLD = 50000.0  # 50,000달러까지 허용
        
        # 🔥🔥🔥 게이트 예약주문 보호 설정
        self.GATE_ORDER_CANCEL_PROTECTION = True  # 게이트 주문 취소 보호 활성화
        self.PROTECT_ALL_GATE_ORDERS = True  # 모든 게이트 주문 보호
        self.DELETION_SAFETY_CHECKS = 5  # 삭제 전 안전 확인 횟수
        
        self.logger.info("🔥🔥🔥 미러 트레이딩 유틸리티 초기화 완료 - 게이트 예약주문 보호 강화")
    
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
            sl_fields = ['presetStopLossPrice', 'stopLossPrice', 'stopLoss', 'slPrice']
            
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
    
    async def adjust_price_for_gate_exchange(self, price: float, bitget_current_price: float = 0, gate_current_price: float = 0) -> float:
        """🔥🔥🔥 게이트 거래소용 가격 조정 - 모든 가격 허용"""
        try:
            if price is None or price <= 0:
                self.logger.warning("유효하지 않은 가격으로 조정 불가")
                return price or 0
            
            # 🔥🔥🔥 모든 가격 그대로 허용 - 조정하지 않음
            if bitget_current_price > 0 and gate_current_price > 0:
                price_diff_abs = abs(bitget_current_price - gate_current_price)
                
                if price_diff_abs <= self.PRICE_SYNC_THRESHOLD:
                    # 시세 차이가 허용 범위 내이면 그대로 사용
                    return price
                else:
                    # 🔥🔥🔥 시세 차이가 크더라도 원본 가격 사용 (조정 없음)
                    self.logger.info(f"시세 차이가 크지만 원본 가격으로 처리: ${price:.2f} (차이: ${price_diff_abs:.2f})")
                    return price
            else:
                # 시세 조회 실패 시에도 원본 가격 사용
                self.logger.debug("시세 조회 실패하지만 원본 가격으로 처리")
                return price
            
        except Exception as e:
            self.logger.error(f"가격 조정 실패하지만 원본 가격 사용: {e}")
            return price or 0
    
    async def validate_trigger_price(self, trigger_price: float, side: str, current_price: float = 0) -> Tuple[bool, str]:
        """🔥🔥🔥 트리거 가격 유효성 검증 - 모든 가격 무조건 허용"""
        try:
            if trigger_price is None or trigger_price <= 0:
                return False, "트리거 가격이 None이거나 0 이하입니다"
            
            # 🔥🔥🔥 모든 가격 무조건 허용 - 검증 통과
            if current_price <= 0:
                self.logger.debug("현재가 조회 실패하지만 모든 트리거 가격 허용")
                return True, "현재가 조회 실패하지만 모든 가격 허용"
            
            # 가격 차이 계산 (로그용)
            price_diff_percent = abs(trigger_price - current_price) / current_price * 100
            price_diff_abs = abs(trigger_price - current_price)
            
            # 🔥🔥🔥 모든 가격 차이 무조건 허용
            self.logger.debug(f"트리거 가격 검증: ${trigger_price:.2f}, 현재가: ${current_price:.2f}, 차이: {price_diff_percent:.4f}% - 모든 가격 허용")
            
            return True, f"모든 트리거 가격 허용 (차이: {price_diff_percent:.4f}%)"
            
        except Exception as e:
            self.logger.error(f"트리거 가격 검증 실패하지만 모든 가격 허용: {e}")
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
            
            if not is_close_order:
                return {
                    'is_close_order': False,
                    'reason': 'Not a close order'
                }
            
            # 포지션 방향과 주문 방향 결정
            if 'close_long' in side or (side == 'sell' and is_close_order):
                position_side = 'long'
                order_direction = 'sell'
            elif 'close_short' in side or (side == 'buy' and is_close_order):
                position_side = 'short'
                order_direction = 'buy'
            else:
                # 애매한 경우 side 기반으로 추정
                if side in ['sell', 'close_long']:
                    position_side = 'long'
                    order_direction = 'sell'
                elif side in ['buy', 'close_short']:
                    position_side = 'short'
                    order_direction = 'buy'
                else:
                    return {
                        'is_close_order': False,
                        'reason': f'Cannot determine position side from side: {side}'
                    }
            
            return {
                'is_close_order': True,
                'position_side': position_side,
                'order_direction': order_direction,
                'original_side': side
            }
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 세부 사항 분석 실패: {e}")
            return {
                'is_close_order': False,
                'reason': f'Analysis error: {str(e)}'
            }
    
    async def calculate_gate_order_size_for_close(self, bitget_order: Dict, close_order_details: Dict, current_gate_position_size: int) -> Tuple[int, bool]:
        """🔥🔥🔥 클로즈 주문을 위한 게이트 주문 크기 계산 - 현재 포지션 크기 기반"""
        try:
            position_side = close_order_details['position_side']  # 'long' 또는 'short'
            order_direction = close_order_details['order_direction']  # 'buy' 또는 'sell'
            
            self.logger.info(f"🎯 클로즈 주문 크기 계산: 현재 게이트 포지션={current_gate_position_size}, 포지션={position_side}, 방향={order_direction}")
            
            # 현재 포지션이 0이면 클로즈 주문 불가
            if current_gate_position_size == 0:
                self.logger.warning(f"⚠️ 현재 포지션이 0이므로 클로즈 주문 불가")
                return 0, True
            
            # 현재 포지션 방향 확인
            current_position_side = 'long' if current_gate_position_size > 0 else 'short'
            current_position_abs_size = abs(current_gate_position_size)
            
            # 포지션 방향과 클로즈 주문 방향이 일치하는지 확인
            if current_position_side != position_side:
                self.logger.warning(f"⚠️ 포지션 방향 불일치: 현재={current_position_side}, 예상={position_side}")
                # 현재 포지션에 맞게 조정
                actual_position_side = current_position_side
            else:
                actual_position_side = position_side
            
            # 🔥🔥🔥 비트겟 클로즈 주문에서 부분 청산 비율 확인
            bitget_size = float(bitget_order.get('size', 0))
            
            # 비트겟에서 현재 포지션 조회하여 부분 청산 비율 계산
            try:
                bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                bitget_current_position = None
                
                for pos in bitget_positions:
                    pos_side = pos.get('holdSide', '').lower()
                    if pos_side == actual_position_side and float(pos.get('total', 0)) > 0:
                        bitget_current_position = pos
                        break
                
                if bitget_current_position:
                    bitget_position_size = float(bitget_current_position.get('total', 0))
                    
                    # 부분 청산 비율 계산
                    if bitget_position_size > 0:
                        close_ratio = min(bitget_size / bitget_position_size, 1.0)
                        self.logger.info(f"🔍 부분 청산 비율: {close_ratio*100:.1f}% (비트겟 포지션: {bitget_position_size}, 클로즈 크기: {bitget_size})")
                    else:
                        close_ratio = 1.0
                        self.logger.warning(f"⚠️ 비트겟 포지션 크기가 0, 전체 청산으로 처리")
                else:
                    # 비트겟 포지션을 찾을 수 없으면 전체 청산
                    close_ratio = 1.0
                    self.logger.warning(f"⚠️ 비트겟에서 해당 포지션을 찾을 수 없음, 전체 청산으로 처리")
                    
            except Exception as e:
                # 비트겟 포지션 조회 실패 시 전체 청산
                close_ratio = 1.0
                self.logger.warning(f"⚠️ 비트겟 포지션 조회 실패: {e}, 전체 청산으로 처리")
            
            # 게이트 클로즈 주문 크기 계산
            gate_close_size = int(current_position_abs_size * close_ratio)
            gate_close_size = max(1, gate_close_size)  # 최소 1
            gate_close_size = min(gate_close_size, current_position_abs_size)  # 최대 현재 포지션 크기
            
            self.logger.info(f"✅ 게이트 클로즈 주문 크기 계산 완료: {gate_close_size} (비율: {close_ratio*100:.1f}%)")
            
            return gate_close_size, True
            
        except Exception as e:
            self.logger.error(f"게이트 클로즈 주문 크기 계산 실패: {e}")
            return 0, False
    
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
    
    async def validate_close_order_against_position(self, close_order_details: Dict, current_gate_position_size: int) -> Tuple[bool, str]:
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
        """🔥🔥🔥 실제 달러 마진 비율 동적 계산 - 모든 계산 허용"""
        try:
            if size is None or trigger_price is None:
                return {
                    'success': False,
                    'error': 'size 또는 trigger_price가 None입니다.'
                }
            
            # 레버리지 정보 추출 - 강화된 로직
            bitget_leverage = 10  # 기본값
            
            # 1. 주문에서 레버리지 추출 시도
            leverage_fields = ['leverage', 'lever', 'marginMode']
            for field in leverage_fields:
                value = bitget_order.get(field)
                if value:
                    try:
                        if isinstance(value, str) and value.isdigit():
                            bitget_leverage = int(value)
                            break
                        elif isinstance(value, (int, float)):
                            bitget_leverage = int(value)
                            break
                    except:
                        continue
            
            # 2. 포지션에서 레버리지 조회 시도
            if bitget_leverage == 10:  # 기본값이면 포지션에서 조회
                try:
                    positions = await self.bitget.get_positions(self.SYMBOL)
                    for pos in positions:
                        pos_leverage = pos.get('leverage', pos.get('lever'))
                        if pos_leverage:
                            try:
                                bitget_leverage = int(float(pos_leverage))
                                break
                            except:
                                continue
                except:
                    pass
            
            # 🔥🔥🔥 달러 가치 계산 - 모든 값 허용
            notional_value = size * trigger_price  # 달러 가치
            required_margin = notional_value / bitget_leverage  # 필요 마진
            
            self.logger.info(f"💰 달러 마진 계산: 크기={size}, 가격=${trigger_price:.2f}, 레버리지={bitget_leverage}x")
            self.logger.info(f"   → 명목가치=${notional_value:,.2f}, 필요마진=${required_margin:,.2f}")
            
            return {
                'success': True,
                'notional_value': notional_value,
                'required_margin': required_margin,
                'leverage': bitget_leverage,
                'size': size,
                'trigger_price': trigger_price
            }
            
        except Exception as e:
            self.logger.error(f"달러 마진 비율 계산 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def format_exchange_name(self, exchange: str) -> str:
        """거래소 이름 포맷팅"""
        exchange_names = {
            'bitget': 'Bitget',
            'gate': 'Gate.io',
            'gateio': 'Gate.io',
            'gate_io': 'Gate.io'
        }
        return exchange_names.get(exchange.lower(), exchange)
    
    def get_order_type_description(self, order_type: str) -> str:
        """주문 타입 설명"""
        type_descriptions = {
            'market': '시장가',
            'limit': '지정가', 
            'stop': '스톱',
            'stop_limit': '스톱 지정가',
            'take_profit': '이익실현',
            'take_profit_limit': '이익실현 지정가',
            'plan': '예약주문',
            'trigger': '트리거'
        }
        return type_descriptions.get(order_type.lower(), order_type)
    
    def calculate_price_difference_percentage(self, price1: float, price2: float) -> float:
        """가격 차이 퍼센트 계산"""
        try:
            if price1 <= 0 or price2 <= 0:
                return 0.0
            return abs(price1 - price2) / min(price1, price2) * 100
        except:
            return 0.0
    
    def is_similar_price(self, price1: float, price2: float, tolerance_percent: float = 1.0) -> bool:
        """🔥🔥🔥 가격 유사성 판단 - 매우 관대한 기준"""
        try:
            if price1 <= 0 or price2 <= 0:
                return False
            
            diff_percent = self.calculate_price_difference_percentage(price1, price2)
            
            # 🔥🔥🔥 매우 관대한 허용 기준 (기본 1% → 최대 10%까지 허용)
            tolerance = max(tolerance_percent, 10.0)  # 최소 10% 허용
            
            return diff_percent <= tolerance
            
        except:
            return False
    
    def is_similar_size(self, size1: float, size2: float, tolerance_percent: float = 5.0) -> bool:
        """🔥🔥🔥 크기 유사성 판단 - 매우 관대한 기준"""
        try:
            if size1 <= 0 or size2 <= 0:
                return False
            
            diff_percent = abs(size1 - size2) / min(size1, size2) * 100
            
            # 🔥🔥🔥 매우 관대한 허용 기준 (기본 5% → 최대 30%까지 허용)
            tolerance = max(tolerance_percent, 30.0)  # 최소 30% 허용
            
            return diff_percent <= tolerance
            
        except:
            return False
    
    async def safe_cancel_gate_order(self, gate_order_id: str, reason: str = "") -> Dict:
        """🔥🔥🔥 안전한 게이트 주문 취소 - 보호 로직 포함"""
        try:
            # 🔥🔥🔥 게이트 주문 취소 보호가 활성화된 경우 취소 거부
            if self.GATE_ORDER_CANCEL_PROTECTION:
                self.logger.warning(f"🛡️ 게이트 주문 취소 보호 활성화로 취소 거부: {gate_order_id}")
                return {
                    'success': False,
                    'cancelled': False,
                    'error': 'Gate order cancellation is protected',
                    'protection_enabled': True
                }
            
            # 🔥🔥🔥 모든 게이트 주문 보호가 활성화된 경우
            if self.PROTECT_ALL_GATE_ORDERS:
                self.logger.warning(f"🛡️ 모든 게이트 주문 보호 활성화로 취소 거부: {gate_order_id}")
                return {
                    'success': False,
                    'cancelled': False,
                    'error': 'All gate orders are protected',
                    'protection_enabled': True
                }
            
            # 삭제 안전 확인 (여러 번 확인)
            for check_count in range(self.DELETION_SAFETY_CHECKS):
                self.logger.info(f"🔍 삭제 안전 확인 {check_count + 1}/{self.DELETION_SAFETY_CHECKS}: {gate_order_id}")
                
                # 게이트 주문이 여전히 존재하는지 확인
                gate_orders = await self.gate.get_all_price_triggered_orders()
                order_exists = any(order.get('id') == gate_order_id for order in gate_orders)
                
                if not order_exists:
                    self.logger.info(f"게이트 주문이 이미 없음: {gate_order_id}")
                    return {
                        'success': True,
                        'cancelled': False,
                        'already_cancelled': True,
                        'reason': 'Order does not exist'
                    }
                
                # 잠시 대기
                import asyncio
                await asyncio.sleep(1)
            
            # 실제 취소 수행 (보호가 비활성화된 경우에만)
            result = await self.gate.cancel_price_triggered_order(gate_order_id)
            
            if result.get('success'):
                self.logger.info(f"✅ 게이트 주문 취소 완료: {gate_order_id} (이유: {reason})")
                return {
                    'success': True,
                    'cancelled': True,
                    'order_id': gate_order_id,
                    'reason': reason
                }
            else:
                self.logger.error(f"❌ 게이트 주문 취소 실패: {gate_order_id} - {result.get('error')}")
                return {
                    'success': False,
                    'cancelled': False,
                    'error': result.get('error', 'Unknown error')
                }
            
        except Exception as e:
            self.logger.error(f"안전한 게이트 주문 취소 실패: {gate_order_id} - {e}")
            return {
                'success': False,
                'cancelled': False,
                'error': str(e)
            }
    
    def get_protection_status(self) -> Dict:
        """🔥🔥🔥 보호 상태 반환"""
        return {
            'gate_order_cancel_protection': self.GATE_ORDER_CANCEL_PROTECTION,
            'protect_all_gate_orders': self.PROTECT_ALL_GATE_ORDERS,
            'deletion_safety_checks': self.DELETION_SAFETY_CHECKS,
            'price_sync_threshold': self.PRICE_SYNC_THRESHOLD,
            'abnormal_price_threshold': self.ABNORMAL_PRICE_DIFF_THRESHOLD,
            'max_price_diff_percent': self.MAX_PRICE_DIFF_PERCENT
        }
