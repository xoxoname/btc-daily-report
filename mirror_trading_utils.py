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
    """🔥🔥🔥 미러 트레이딩 유틸리티 클래스 - 시세 차이 제한 완전 제거"""
    
    def __init__(self, config, bitget_client, gate_client):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.logger = logging.getLogger('mirror_trading_utils')
        
        # 상수 설정
        self.SYMBOL = "BTCUSDT"
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
        
        self.logger.info("🔥🔥🔥 미러 트레이딩 유틸리티 초기화 완료 - 시세 차이 제한 완전 제거")
    
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
            sl_fields = ['presetStopLossPrice', 'stopLossPrice', 'slPrice']
            
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
            
            if tp_price or sl_price:
                self.logger.info(f"🎯 TP/SL 정보 추출 완료: TP={tp_price}, SL={sl_price}")
            
            return tp_price, sl_price
            
        except Exception as e:
            self.logger.error(f"TP/SL 정보 추출 실패: {e}")
            return None, None
    
    async def adjust_price_for_gate_market(self, price: float, bitget_current_price: float = 0, gate_current_price: float = 0) -> float:
        """🔥🔥🔥 게이트 시장에 맞는 가격 조정 - 모든 가격 허용"""
        try:
            if price <= 0:
                self.logger.warning("가격이 0 이하입니다")
                return price
            
            # 🔥🔥🔥 시세 차이와 무관하게 모든 가격 허용
            if bitget_current_price > 0 and gate_current_price > 0:
                price_diff_abs = abs(bitget_current_price - gate_current_price)
                
                # 🔥🔥🔥 매우 큰 가격 차이도 허용 (10000달러까지)
                if price_diff_abs <= self.ABNORMAL_PRICE_DIFF_THRESHOLD:
                    # 가격 조정 계산
                    price_diff = gate_current_price - bitget_current_price
                    adjusted_price = price + price_diff
                    
                    if adjusted_price > 0:
                        adjustment_percent = abs(adjusted_price - price) / price * 100
                        
                        # 🔥🔥🔥 50% 이내 조정은 허용 (기존 10%에서 대폭 완화)
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
            
            # 포지션 방향 및 주문 방향 결정
            if 'close_long' in side or (side == 'sell' and is_close_order):
                close_type = 'close_long'
                position_side = 'long'
                order_direction = 'sell'
            elif 'close_short' in side or (side == 'buy' and is_close_order):
                close_type = 'close_short'
                position_side = 'short'
                order_direction = 'buy'
            elif side == 'sell':
                close_type = 'open_short' if not is_close_order else 'close_long'
                position_side = 'long' if is_close_order else 'short'
                order_direction = 'sell'
            elif side == 'buy':
                close_type = 'open_long' if not is_close_order else 'close_short'
                position_side = 'short' if is_close_order else 'long'
                order_direction = 'buy'
            else:
                close_type = 'unknown'
                position_side = 'unknown'
                order_direction = side
            
            return {
                'is_close_order': is_close_order,
                'close_type': close_type,
                'position_side': position_side,
                'order_direction': order_direction,
                'original_side': side,
                'reduce_only': reduce_only
            }
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 세부 분석 실패: {e}")
            return {
                'is_close_order': False,
                'close_type': 'unknown',
                'position_side': 'unknown',
                'order_direction': 'buy',
                'original_side': side,
                'reduce_only': False
            }
    
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
            
            # 1. 주문에서 레버리지 정보 추출 시도
            leverage_fields = ['leverage', 'lever', 'marginCoin']
            for field in leverage_fields:
                if bitget_order.get(field):
                    try:
                        extracted_leverage = float(bitget_order.get(field))
                        if 1 <= extracted_leverage <= 150:  # 합리적인 레버리지 범위
                            bitget_leverage = int(extracted_leverage)
                            self.logger.info(f"📊 주문에서 레버리지 추출: {bitget_leverage}x")
                            break
                    except:
                        continue
            
            # 2. 비트겟 계정 정보에서 총 자산 조회
            try:
                bitget_account = await self.bitget.get_account_info()
                total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
                
                if total_equity <= 0:
                    return {
                        'success': False,
                        'error': '비트겟 총 자산을 조회할 수 없습니다.'
                    }
                
                self.logger.info(f"💰 비트겟 총 자산: ${total_equity:,.2f}")
                
            except Exception as e:
                self.logger.error(f"비트겟 계정 정보 조회 실패: {e}")
                return {
                    'success': False,
                    'error': f'계정 정보 조회 실패: {str(e)}'
                }
            
            # 3. 실제 달러 마진 계산
            notional_value = size * trigger_price  # 포지션의 명목 가치
            margin_amount = notional_value / bitget_leverage  # 실제 마진 투입액
            
            # 4. 총 자산 대비 마진 비율 계산
            margin_ratio = (margin_amount / total_equity) * 100
            
            # 5. 게이트 계정 정보 조회
            try:
                gate_account = await self.gate.get_account_balance()
                gate_total_equity = float(gate_account.get('total', 0))
                
                if gate_total_equity <= 0:
                    return {
                        'success': False,
                        'error': '게이트 총 자산을 조회할 수 없습니다.'
                    }
                
                self.logger.info(f"💰 게이트 총 자산: ${gate_total_equity:,.2f}")
                
            except Exception as e:
                self.logger.error(f"게이트 계정 정보 조회 실패: {e}")
                return {
                    'success': False,
                    'error': f'게이트 계정 정보 조회 실패: {str(e)}'
                }
            
            # 6. 게이트에서 동일한 비율로 마진 계산
            gate_margin_amount = gate_total_equity * (margin_ratio / 100)
            gate_notional_value = gate_margin_amount * bitget_leverage
            gate_size = int(gate_notional_value / 10)  # 게이트는 1 BTC = 10 계약
            
            # 최소 계약 수 보장
            if gate_size < 1:
                gate_size = 1
                actual_margin_ratio = (gate_size * 10 * bitget_leverage) / gate_total_equity * 100
                self.logger.warning(f"⚠️ 최소 계약 수 조정: {gate_size} 계약 (실제 비율: {actual_margin_ratio:.4f}%)")
            
            result = {
                'success': True,
                'bitget_size': size,
                'gate_size': gate_size,
                'margin_ratio': margin_ratio,
                'margin_amount': margin_amount,
                'gate_margin_amount': gate_margin_amount,
                'leverage': bitget_leverage,
                'trigger_price': trigger_price,
                'notional_value': notional_value,
                'gate_notional_value': gate_notional_value,
                'bitget_equity': total_equity,
                'gate_equity': gate_total_equity
            }
            
            self.logger.info(f"📊 마진 비율 계산 완료:")
            self.logger.info(f"   비트겟 크기: {size} BTC")
            self.logger.info(f"   게이트 크기: {gate_size} 계약")
            self.logger.info(f"   마진 비율: {margin_ratio:.4f}%")
            self.logger.info(f"   레버리지: {bitget_leverage}x")
            
            return result
            
        except Exception as e:
            self.logger.error(f"마진 비율 계산 실패: {e}")
            return {
                'success': False,
                'error': f'계산 오류: {str(e)}'
            }
    
    async def get_gate_contract_size_from_btc(self, btc_size: float) -> int:
        """BTC 크기를 게이트 계약 수로 변환"""
        try:
            # Gate.io에서 1 BTC = 10,000 계약
            contract_size = int(btc_size * 10000)
            
            # 최소 계약 수 보장
            if contract_size < 1:
                contract_size = 1
                self.logger.warning(f"⚠️ 최소 계약 수 조정: {contract_size}")
            
            self.logger.info(f"📊 BTC → 게이트 계약 변환: {btc_size} BTC → {contract_size} 계약")
            return contract_size
            
        except Exception as e:
            self.logger.error(f"계약 크기 변환 실패: {e}")
            return 1
    
    async def format_price_for_gate(self, price: float) -> str:
        """게이트에 맞는 가격 포맷"""
        try:
            # 게이트는 소수점 1자리까지 지원
            formatted_price = f"{price:.1f}"
            self.logger.debug(f"가격 포맷: {price} → {formatted_price}")
            return formatted_price
            
        except Exception as e:
            self.logger.error(f"가격 포맷 실패: {e}")
            return str(price)
    
    def get_mirror_order_type(self, bitget_order_type: str) -> str:
        """비트겟 주문 타입을 게이트 주문 타입으로 변환"""
        try:
            type_mapping = {
                'limit': 'limit',
                'market': 'market', 
                'trigger': 'limit',  # 트리거 주문은 지정가로
                'plan': 'limit',     # 예약 주문은 지정가로
                'stop': 'limit',     # 스탑 주문은 지정가로
                'conditional': 'limit'
            }
            
            gate_type = type_mapping.get(bitget_order_type.lower(), 'limit')
            self.logger.debug(f"주문 타입 변환: {bitget_order_type} → {gate_type}")
            return gate_type
            
        except Exception as e:
            self.logger.error(f"주문 타입 변환 실패: {e}")
            return "limit"
    
    async def validate_order_before_mirror(self, bitget_order: Dict) -> Tuple[bool, str]:
        """미러링 전 주문 유효성 종합 검증"""
        try:
            # 1. 기본 필드 검증
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            if not order_id:
                return False, "주문 ID가 없습니다"
            
            # 2. 크기 검증
            size = bitget_order.get('size', 0)
            if not size or float(size) <= 0:
                return False, "주문 크기가 0 이하입니다"
            
            # 3. 트리거 가격 검증
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price <= 0:
                return False, "트리거 가격을 찾을 수 없습니다"
            
            # 4. 🔥🔥🔥 모든 주문 허용 - 검증 완화
            self.logger.info(f"✅ 주문 검증 통과: {order_id}")
            return True, "모든 주문 유효성 검사 통과"
            
        except Exception as e:
            self.logger.error(f"주문 유효성 검증 실패: {e}")
            return False, f"검증 오류: {str(e)}"
    
    def generate_mirror_order_hash(self, bitget_order: Dict) -> str:
        """미러 주문 해시 생성 (중복 방지용)"""
        try:
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            side = bitget_order.get('side', bitget_order.get('tradeSide', 'unknown'))
            size = bitget_order.get('size', 0)
            
            hash_string = f"{self.SYMBOL}_{side}_{trigger_price}_{size}_{datetime.now().timestamp()}"
            return str(hash(hash_string))
            
        except Exception as e:
            self.logger.error(f"주문 해시 생성 실패: {e}")
            return str(hash(str(bitget_order)))
    
    def is_duplicate_order(self, bitget_order: Dict, existing_orders: List[Dict]) -> bool:
        """중복 주문 검사"""
        try:
            if not existing_orders:
                return False
            
            current_trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    current_trigger_price = float(bitget_order.get(price_field))
                    break
            
            current_side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            current_size = float(bitget_order.get('size', 0))
            
            for existing_order in existing_orders:
                existing_trigger_price = existing_order.get('trigger_price', 0)
                existing_side = existing_order.get('side', '').lower()
                existing_size = float(existing_order.get('size', 0))
                
                # 🔥🔥🔥 중복 검사 조건 완화 - 매우 유사한 주문만 중복으로 판단
                price_diff_percent = abs(current_trigger_price - existing_trigger_price) / max(current_trigger_price, existing_trigger_price) * 100
                size_diff_percent = abs(current_size - existing_size) / max(current_size, existing_size) * 100
                
                if (current_side == existing_side and 
                    price_diff_percent < 0.01 and  # 0.01% 미만 가격 차이
                    size_diff_percent < 0.01):     # 0.01% 미만 크기 차이
                    
                    self.logger.warning(f"🔄 중복 주문 감지: 기존 주문과 매우 유사함")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"중복 주문 검사 실패: {e}")
            return False
    
    async def log_mirror_operation(self, operation: str, bitget_order: Dict, gate_result: Dict = None, success: bool = True):
        """미러링 작업 로깅"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', 'unknown'))
            
            log_msg = f"🔄 {operation}: {order_id}"
            
            if gate_result:
                gate_order_id = gate_result.get('order_id', 'unknown')
                log_msg += f" → {gate_order_id}"
            
            if success:
                self.logger.info(f"✅ {log_msg}")
            else:
                error = gate_result.get('error', 'unknown error') if gate_result else 'unknown error'
                self.logger.error(f"❌ {log_msg} - 실패: {error}")
            
        except Exception as e:
            self.logger.error(f"미러링 작업 로깅 실패: {e}")
    
    def __str__(self):
        return f"MirrorTradingUtils(symbol={self.SYMBOL}, gate_contract={self.GATE_CONTRACT})"
    
    def __repr__(self):
        return self.__str__()
