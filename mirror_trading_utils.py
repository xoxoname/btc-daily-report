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
    """🔥🔥🔥 미러 트레이딩 유틸리티 클래스 - 포지션 크기 기반 클로즈 주문 처리 강화"""
    
    def __init__(self, config, bitget_client, gate_client):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.logger = logging.getLogger('mirror_trading_utils')
        
        # 상수 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.MIN_MARGIN = 1.0
        self.MAX_PRICE_DIFF_PERCENT = 2.0  # 1.0% → 2.0%로 더 관대하게
        
        # 🔥🔥🔥 트리거 가격 검증 완전히 제거 - 거의 모든 가격 허용
        self.TRIGGER_PRICE_MIN_DIFF_PERCENT = 0.0
        self.ALLOW_VERY_CLOSE_PRICES = True
        
        # 🔥🔥🔥 시세 차이 관리 더욱 관대하게
        self.PRICE_SYNC_THRESHOLD = 100.0  # 15달러 → 100달러로 대폭 상향
        self.PRICE_ADJUSTMENT_ENABLED = True
        
        # 🔥🔥🔥 비정상적인 시세 차이 감지 임계값도 상향
        self.ABNORMAL_PRICE_DIFF_THRESHOLD = 2000.0  # 1000달러 → 2000달러로 상향
        
        self.logger.info("🔥🔥🔥 미러 트레이딩 유틸리티 초기화 완료 - 포지션 크기 기반 클로즈 주문 처리 강화")
    
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
            
            if trigger_price <= 0:
                self.logger.debug(f"유효하지 않은 트리거가: {trigger_price}")
                return None
            
            return {
                'order_id': order_id,
                'contract': contract,
                'trigger_price': trigger_price,
                'size': size,
                'abs_size': abs(size),
                'tp_price': tp_price,
                'sl_price': sl_price,
                'has_tp_sl': bool(tp_price or sl_price),
                'gate_order_raw': gate_order
            }
            
        except Exception as e:
            self.logger.error(f"게이트 주문 상세 정보 추출 실패: {e}")
            return None
    
    async def generate_multiple_order_hashes(self, order_details: Dict) -> List[str]:
        """🔥🔥🔥 다양한 방식으로 주문 해시 생성 - 더 관대한 가격 범위 및 size 0 처리"""
        try:
            # None 체크 및 기본값 설정
            contract = order_details.get('contract') or self.GATE_CONTRACT
            trigger_price = order_details.get('trigger_price')
            size = order_details.get('size', 0)
            abs_size = order_details.get('abs_size', abs(size) if size else 0)
            
            if trigger_price is None:
                self.logger.debug(f"필수 값이 None - trigger_price: {trigger_price}")
                return []
            
            try:
                trigger_price = float(trigger_price)
                size = int(size) if size is not None else 0
                abs_size = abs(size) if size != 0 else 0
            except (ValueError, TypeError) as e:
                self.logger.debug(f"값 변환 실패 - trigger_price: {trigger_price}, size: {size}, error: {e}")
                return []
            
            if trigger_price <= 0:
                self.logger.debug(f"유효하지 않은 트리거 가격 - trigger_price: {trigger_price}")
                return []
            
            hashes = []
            
            # 🔥🔥🔥 가격 기반 해시 (중복 방지 핵심) - 더 관대한 범위
            try:
                # 기본 가격 해시들 (size와 무관하게 항상 생성)
                price_only_hash = f"{contract}_price_{trigger_price:.2f}"
                hashes.append(price_only_hash)
                
                precise_price_hash = f"{contract}_price_{trigger_price:.8f}"
                hashes.append(precise_price_hash)
                
                # 반올림된 가격 해시들
                rounded_price_1 = round(trigger_price, 1)
                rounded_price_hash_1 = f"{contract}_price_{rounded_price_1:.1f}"
                hashes.append(rounded_price_hash_1)
                
                rounded_price_0 = round(trigger_price, 0)
                rounded_price_hash_0 = f"{contract}_price_{rounded_price_0:.0f}"
                hashes.append(rounded_price_hash_0)
                
            except Exception as e:
                self.logger.debug(f"가격 기반 해시 생성 실패: {e}")
            
            # 🔥🔥🔥 size가 0이 아닌 경우에만 size 포함 해시 생성
            if abs_size > 0:
                try:
                    # 기본 해시
                    basic_hash = f"{contract}_{trigger_price:.2f}_{abs_size}"
                    hashes.append(basic_hash)
                    
                    # 정확한 가격 해시
                    exact_price_hash = f"{contract}_{trigger_price:.8f}_{abs_size}"
                    hashes.append(exact_price_hash)
                    
                    # 부호 포함 해시
                    signed_hash = f"{contract}_{trigger_price:.2f}_{size}"
                    hashes.append(signed_hash)
                    
                    # 반올림된 가격 해시
                    rounded_price_1 = round(trigger_price, 1)
                    rounded_hash_1 = f"{contract}_{rounded_price_1:.1f}_{abs_size}"
                    hashes.append(rounded_hash_1)
                    
                    rounded_price_0 = round(trigger_price, 0)
                    rounded_hash_0 = f"{contract}_{rounded_price_0:.0f}_{abs_size}"
                    hashes.append(rounded_hash_0)
                    
                except Exception as e:
                    self.logger.debug(f"size 포함 해시 생성 실패: {e}")
            else:
                # size가 0인 경우 로그 레벨을 debug로 변경
                self.logger.debug(f"size가 0이므로 가격 기반 해시만 생성 - trigger_price: {trigger_price}")
            
            # TP/SL 포함 해시
            try:
                if order_details.get('has_tp_sl'):
                    tp_price = order_details.get('tp_price', 0) or 0
                    sl_price = order_details.get('sl_price', 0) or 0
                    
                    # TP/SL 가격 기반 해시 (size 무관)
                    tp_sl_price_hash = f"{contract}_price_{trigger_price:.2f}_withTPSL"
                    hashes.append(tp_sl_price_hash)
                    
                    # size가 있을 때만 TP/SL + size 해시 생성
                    if abs_size > 0:
                        tp_sl_hash = f"{contract}_{trigger_price:.2f}_{abs_size}_tp{tp_price:.2f}_sl{sl_price:.2f}"
                        hashes.append(tp_sl_hash)
                        
            except Exception as e:
                self.logger.debug(f"TP/SL 해시 생성 실패: {e}")
            
            # 🔥🔥🔥 더 관대한 가격 범위 해시 (±100달러)
            try:
                # 100달러 단위로 반올림한 가격 해시
                price_range_100 = round(trigger_price / 100) * 100
                range_hash_100 = f"{contract}_range100_{price_range_100:.0f}"
                hashes.append(range_hash_100)
                
                # 50달러 단위로 반올림한 가격 해시
                price_range_50 = round(trigger_price / 50) * 50
                range_hash_50 = f"{contract}_range50_{price_range_50:.0f}"
                hashes.append(range_hash_50)
                
                # 🔥🔥🔥 더 넓은 시세 차이를 고려한 가격 범위 해시 (±50달러)
                for offset in [-50, -30, -20, -10, 0, 10, 20, 30, 50]:
                    adjusted_price = trigger_price + offset
                    if adjusted_price > 0:
                        offset_hash = f"{contract}_offset_{adjusted_price:.0f}"
                        hashes.append(offset_hash)
                        
            except Exception as e:
                self.logger.debug(f"가격 범위 해시 생성 실패: {e}")
            
            # 중복 제거
            unique_hashes = list(set(hashes))
            
            if unique_hashes:
                self.logger.debug(f"주문 해시 {len(unique_hashes)}개 생성: 트리거=${trigger_price:.2f}, 크기={size}")
            else:
                self.logger.debug(f"해시 생성 실패 - 빈 리스트 반환")
            
            return unique_hashes
            
        except Exception as e:
            self.logger.error(f"다중 해시 생성 실패: {e}")
            try:
                trigger_price = order_details.get('trigger_price')
                size = order_details.get('size', 0)
                contract = order_details.get('contract', self.GATE_CONTRACT)
                
                if trigger_price is not None:
                    trigger_price = float(trigger_price)
                    # size가 0이어도 가격 기반 해시는 생성
                    basic_hash = f"{contract}_{trigger_price:.2f}_fallback"
                    price_hash = f"{contract}_price_{trigger_price:.2f}"
                    return [basic_hash, price_hash]
            except Exception as fallback_error:
                self.logger.error(f"폴백 해시 생성도 실패: {fallback_error}")
            
            return []
    
    def generate_order_hash(self, trigger_price: float, size: int, contract: str = None) -> str:
        """주문 특성으로 해시 생성 (중복 방지용)"""
        try:
            contract = contract or self.GATE_CONTRACT
            
            if trigger_price is None or trigger_price <= 0:
                return f"{contract}_unknown_unknown"
            
            trigger_price = float(trigger_price)
            size = int(size) if size is not None else 0
            
            # size가 0이어도 가격 기반 해시 생성
            if size == 0:
                return f"{contract}_price_{trigger_price:.2f}"
            else:
                return f"{contract}_{trigger_price:.2f}_{abs(size)}"
            
        except (ValueError, TypeError) as e:
            self.logger.debug(f"해시 생성 시 변환 실패: {e}")
            return f"{contract or self.GATE_CONTRACT}_error_error"
    
    def generate_price_based_hash(self, trigger_price: float, contract: str = None) -> str:
        """가격 기반 해시 생성 (수량 무관 중복 방지)"""
        try:
            contract = contract or self.GATE_CONTRACT
            
            if trigger_price is None or trigger_price <= 0:
                return f"{contract}_price_invalid"
            
            trigger_price = float(trigger_price)
            return f"{contract}_price_{trigger_price:.2f}"
            
        except (ValueError, TypeError) as e:
            self.logger.debug(f"가격 기반 해시 생성 실패: {e}")
            return f"{contract or self.GATE_CONTRACT}_price_error"
    
    async def adjust_price_for_gate(self, price: float, bitget_current_price: float = 0, 
                                   gate_current_price: float = 0, price_diff_percent: float = 0) -> float:
        """🔥🔥🔥 게이트 기준으로 가격 조정 - 더욱 관대한 버전"""
        try:
            if price is None or price <= 0:
                return price or 0
            
            # 🔥🔥🔥 더욱 관대한 비정상적인 시세 차이 감지
            if (bitget_current_price > 0 and gate_current_price > 0):
                price_diff_abs = abs(bitget_current_price - gate_current_price)
                
                # 더 높은 임계값으로 비정상적인 시세 차이 판단 (2000달러 이상)
                if price_diff_abs > self.ABNORMAL_PRICE_DIFF_THRESHOLD:
                    self.logger.warning(f"비정상적인 시세 차이 감지 (${price_diff_abs:.2f}), 가격 조정 건너뜀")
                    return price
                
                # 더 관대한 정상 범위 내에서만 조정 (100달러 이상)
                if (self.PRICE_ADJUSTMENT_ENABLED and 
                    price_diff_abs > self.PRICE_SYNC_THRESHOLD and
                    price_diff_abs <= self.ABNORMAL_PRICE_DIFF_THRESHOLD):
                    
                    # 가격 비율 계산
                    price_ratio = gate_current_price / bitget_current_price
                    adjusted_price = price * price_ratio
                    
                    # 조정 폭 검증 (더 관대하게 10% 이하 조정 허용)
                    adjustment_percent = abs(adjusted_price - price) / price * 100
                    
                    if adjustment_percent <= 10.0:  # 5% → 10%로 더 관대하게
                        self.logger.info(f"🔧 가격 조정: ${price:.2f} → ${adjusted_price:.2f} (차이: ${price_diff_abs:.2f})")
                        return adjusted_price
                    else:
                        self.logger.warning(f"⚠️ 조정 폭이 너무 큼 ({adjustment_percent:.1f}%), 원본 가격 사용")
                        return price
                else:
                    return price
            elif bitget_current_price <= 0 or gate_current_price <= 0:
                self.logger.debug("시세 조회 실패로 가격 조정 건너뜀")
                return price
            
            return price
            
        except Exception as e:
            self.logger.error(f"가격 조정 실패: {e}")
            return price or 0
    
    async def validate_trigger_price(self, trigger_price: float, side: str, current_price: float = 0) -> Tuple[bool, str]:
        """🔥🔥🔥 트리거 가격 유효성 검증 - 더욱 관대한 설정"""
        try:
            if trigger_price is None or trigger_price <= 0:
                return False, "트리거 가격이 None이거나 0 이하입니다"
            
            if current_price <= 0:
                self.logger.info("현재가 조회 실패하지만 트리거 가격 허용")
                return True, "현재가 조회 실패하지만 허용"
            
            # 🔥🔥🔥 더욱 관대한 가격 차이 허용
            price_diff_percent = abs(trigger_price - current_price) / current_price * 100
            price_diff_abs = abs(trigger_price - current_price)
            
            # 🔥🔥🔥 더 높은 임계값으로 비정상적인 가격 차이 감지 (2000달러)
            if price_diff_abs > self.ABNORMAL_PRICE_DIFF_THRESHOLD:
                self.logger.warning(f"비정상적인 가격 차이 감지: ${price_diff_abs:.2f}")
                return False, f"트리거가와 현재가 차이가 비정상적 (${price_diff_abs:.2f})"
            
            # 🔥🔥🔥 극도로 관대한 검증 - 거의 모든 가격 허용
            if self.ALLOW_VERY_CLOSE_PRICES:
                # 시장가와 완전히 동일한 경우에만 경고하되 허용
                if price_diff_percent == 0.0:
                    self.logger.info(f"트리거가와 현재가가 완전히 동일하지만 허용: {trigger_price}")
                    return True, f"동일한 가격이지만 허용 (차이: {price_diff_percent:.8f}%)"
                
                # 매우 근접한 가격도 모두 허용
                if price_diff_percent < 0.001:  # 0.001% 미만
                    self.logger.info(f"매우 근접한 트리거가 허용: 차이 {price_diff_percent:.8f}%")
                    return True, f"매우 근접한 트리거가 허용 (차이: {price_diff_percent:.8f}%)"
                
                # 🔥🔥🔥 일반적인 가격 차이도 더욱 관대하게 허용 (80% 미만)
                if price_diff_percent < 80:  # 50% → 80%로 더 관대하게 조정
                    return True, f"관대한 설정으로 허용 가능한 트리거 가격 (차이: {price_diff_percent:.4f}%)"
                
                # 극단적인 가격 차이만 차단 (80% 이상)
                if price_diff_percent >= 80:
                    self.logger.warning(f"극단적인 가격 차이: {price_diff_percent:.1f}%")
                    return False, f"트리거가와 현재가 차이가 너무 극단적 ({price_diff_percent:.1f}%)"
            
            # 기본적으로 모든 가격 허용
            return True, f"관대한 설정으로 모든 트리거 가격 허용 (차이: {price_diff_percent:.4f}%)"
            
        except Exception as e:
            self.logger.error(f"트리거 가격 검증 실패하지만 허용: {e}")
            return True, f"검증 오류이지만 관대한 설정으로 허용: {str(e)[:100]}"
    
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
            
            order_direction = None
            position_side = None
            
            if is_close_order:
                # 클로즈 주문인 경우
                if 'close_long' in side or side == 'close long':
                    order_direction = 'sell'  # 롱 포지션을 종료하려면 매도
                    position_side = 'long'
                elif 'close_short' in side or side == 'close short':
                    order_direction = 'buy'   # 숏 포지션을 종료하려면 매수
                    position_side = 'short'
                elif 'sell' in side:
                    order_direction = 'sell'
                    position_side = 'long'   # 매도로 클로즈하면 원래 롱 포지션
                elif 'buy' in side:
                    order_direction = 'buy'
                    position_side = 'short'  # 매수로 클로즈하면 원래 숏 포지션
                else:
                    # 기본값 - side에서 추정
                    if 'long' in side:
                        order_direction = 'sell'
                        position_side = 'long'
                    elif 'short' in side:
                        order_direction = 'buy'
                        position_side = 'short'
                    else:
                        order_direction = 'sell'  # 기본값
                        position_side = 'long'
            else:
                # 오픈 주문인 경우
                if 'buy' in side or 'long' in side:
                    order_direction = 'buy'
                    position_side = 'long'
                elif 'sell' in side or 'short' in side:
                    order_direction = 'sell'
                    position_side = 'short'
                else:
                    order_direction = 'buy'  # 기본값
                    position_side = 'long'
            
            result = {
                'is_close_order': is_close_order,
                'order_direction': order_direction,  # buy 또는 sell
                'position_side': position_side,      # long 또는 short
                'original_side': side,
                'reduce_only': reduce_only
            }
            
            self.logger.info(f"✅ 클로즈 주문 분석 결과: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 세부 사항 판단 실패: {e}")
            return {
                'is_close_order': False,
                'order_direction': 'buy',
                'position_side': 'long',
                'original_side': side,
                'reduce_only': False
            }
    
    async def calculate_gate_order_size_for_close_order(self, current_gate_position_size: int, 
                                                       close_order_details: Dict, 
                                                       bitget_order: Dict) -> Tuple[int, bool]:
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
                self.logger.error(f"비트겟 포지션 조회 실패, 전체 청산으로 처리: {e}")
            
            # 🔥🔥🔥 게이트 클로즈 주문 크기 계산
            gate_close_size = int(current_position_abs_size * close_ratio)
            
            # 최소 1개는 클로즈
            if gate_close_size == 0:
                gate_close_size = 1
            
            # 현재 포지션보다 클 수 없음
            if gate_close_size > current_position_abs_size:
                gate_close_size = current_position_abs_size
            
            # 🔥🔥🔥 클로즈 주문 방향 결정 (포지션과 반대 방향)
            if actual_position_side == 'long':
                # 롱 포지션 클로즈 → 매도 (음수)
                final_gate_size = -gate_close_size
                self.logger.info(f"🔴 롱 포지션 클로즈: {gate_close_size} → 매도 주문 (음수: {final_gate_size})")
            else:
                # 숏 포지션 클로즈 → 매수 (양수)
                final_gate_size = gate_close_size
                self.logger.info(f"🟢 숏 포지션 클로즈: {gate_close_size} → 매수 주문 (양수: {final_gate_size})")
            
            self.logger.info(f"✅ 클로즈 주문 크기 계산 완료: 현재 포지션={current_gate_position_size} → 클로즈 크기={final_gate_size} (비율: {close_ratio*100:.1f}%)")
            
            return final_gate_size, True  # reduce_only=True
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 크기 계산 실패: {e}")
            return current_gate_position_size, True
    
    async def calculate_gate_order_size_fixed(self, side: str, base_size: int, is_close_order: bool = False) -> Tuple[int, bool]:
        """🔥🔥🔥 게이트 주문 수량 계산 - 클로즈 주문 방향 완전 수정"""
        try:
            side_lower = side.lower()
            reduce_only = False
            
            self.logger.info(f"🔍 주문 타입 분석: side='{side}', is_close_order={is_close_order}")
            
            # 🔥🔥🔥 클로즈 주문 처리 - 완전히 수정된 로직
            if is_close_order or 'close' in side_lower:
                reduce_only = True
                
                # 클로즈 주문: 포지션을 종료하는 방향으로 주문
                if 'close_long' in side_lower or side_lower == 'close long':
                    # 롱 포지션 종료 → 매도 주문 (음수)
                    gate_size = -abs(base_size)
                    self.logger.info(f"🔴 클로즈 롱: 롱 포지션 종료 → 게이트 매도 주문 (음수: {gate_size})")
                    
                elif 'close_short' in side_lower or side_lower == 'close short':
                    # 숏 포지션 종료 → 매수 주문 (양수)
                    gate_size = abs(base_size)
                    self.logger.info(f"🟢 클로즈 숏: 숏 포지션 종료 → 게이트 매수 주문 (양수: {gate_size})")
                    
                elif 'sell' in side_lower and 'buy' not in side_lower:
                    # 매도로 클로즈 → 롱 포지션을 종료하는 것
                    gate_size = -abs(base_size)
                    self.logger.info(f"🔴 클로즈 매도: 롱 포지션 종료 → 게이트 매도 주문 (음수: {gate_size})")
                    
                elif 'buy' in side_lower and 'sell' not in side_lower:
                    # 매수로 클로즈 → 숏 포지션을 종료하는 것
                    gate_size = abs(base_size)
                    self.logger.info(f"🟢 클로즈 매수: 숏 포지션 종료 → 게이트 매수 주문 (양수: {gate_size})")
                    
                else:
                    # 기타 클로즈 주문 - 기본적으로 매도로 처리
                    gate_size = -abs(base_size)
                    self.logger.warning(f"⚠️ 알 수 없는 클로즈 주문 유형: {side}, 매도로 처리 (음수: {gate_size})")
                        
            # 오픈 주문 처리
            else:
                reduce_only = False
                
                if 'open_long' in side_lower or ('buy' in side_lower and 'sell' not in side_lower):
                    # 롱 포지션 생성 → 매수 주문 (양수)
                    gate_size = abs(base_size)
                    self.logger.info(f"🟢 오픈 롱: 새 롱 포지션 생성 → 게이트 매수 주문 (양수: {gate_size})")
                    
                elif 'open_short' in side_lower or 'sell' in side_lower:
                    # 숏 포지션 생성 → 매도 주문 (음수)
                    gate_size = -abs(base_size)
                    self.logger.info(f"🔴 오픈 숏: 새 숏 포지션 생성 → 게이트 매도 주문 (음수: {gate_size})")
                    
                else:
                    # 기타 오픈 주문 - 원본 사이즈 유지
                    gate_size = base_size
                    self.logger.warning(f"⚠️ 알 수 없는 오픈 주문 유형: {side}, 원본 사이즈 유지: {gate_size}")
            
            self.logger.info(f"✅ 최종 변환 결과: {side} → 게이트 사이즈={gate_size}, reduce_only={reduce_only}")
            return gate_size, reduce_only
            
        except Exception as e:
            self.logger.error(f"게이트 주문 수량 계산 실패: {e}")
            return base_size, False
    
    async def calculate_gate_order_size(self, side: str, base_size: int) -> int:
        """기존 호환성을 위한 래퍼 메서드"""
        try:
            is_close_order = 'close' in side.lower()
            gate_size, _ = await self.calculate_gate_order_size_fixed(side, base_size, is_close_order)
            return gate_size
        except Exception as e:
            self.logger.error(f"게이트 주문 수량 계산 래퍼 실패: {e}")
            return base_size
    
    async def determine_gate_trigger_type(self, trigger_price: float, current_price: float = 0) -> str:
        """Gate.io 트리거 타입 결정"""
        try:
            if current_price <= 0 or trigger_price is None:
                return "ge"
            
            if trigger_price > current_price:
                return "ge"  # greater than or equal
            else:
                return "le"  # less than or equal
                
        except Exception as e:
            self.logger.error(f"Gate.io 트리거 타입 결정 실패: {e}")
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
            
            # 1. 주문에서 레버리지 추출
            order_leverage = bitget_order.get('leverage')
            if order_leverage:
                try:
                    bitget_leverage = int(float(order_leverage))
                    self.logger.info(f"주문에서 레버리지 추출: {bitget_leverage}x")
                except Exception as lev_error:
                    self.logger.warning(f"주문 레버리지 변환 실패: {lev_error}")
            
            # 2. 계정 정보에서 레버리지 추출 (폴백)
            if not order_leverage or bitget_leverage == 10:
                try:
                    bitget_account = await self.bitget.get_account_info()
                    
                    # 여러 레버리지 필드 확인
                    for lev_field in ['crossMarginLeverage', 'leverage', 'defaultLeverage']:
                        account_leverage = bitget_account.get(lev_field)
                        if account_leverage:
                            try:
                                extracted_lev = int(float(account_leverage))
                                if extracted_lev > 1:  # 유효한 레버리지인 경우
                                    bitget_leverage = extracted_lev
                                    self.logger.info(f"계정에서 레버리지 추출: {lev_field} = {bitget_leverage}x")
                                    break
                            except:
                                continue
                                
                except Exception as account_error:
                    self.logger.warning(f"계정 레버리지 조회 실패: {account_error}")
            
            # 3. 비트겟 계정 정보 조회
            bitget_account = await self.bitget.get_account_info()
            bitget_total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            if bitget_total_equity <= 0:
                return {
                    'success': False,
                    'error': '비트겟 총 자산이 0이거나 조회 실패'
                }
            
            # 4. 비트겟에서 이 주문이 체결될 때 사용할 실제 마진 계산
            bitget_notional_value = size * trigger_price
            bitget_required_margin = bitget_notional_value / bitget_leverage
            
            # 5. 비트겟 총 자산 대비 실제 마진 투입 비율 계산
            margin_ratio = bitget_required_margin / bitget_total_equity
            
            # 6. 마진 비율 유효성 검증
            if margin_ratio <= 0 or margin_ratio > 1:
                return {
                    'success': False,
                    'error': f'마진 비율이 유효하지 않음: {margin_ratio:.4f}'
                }
            
            result = {
                'success': True,
                'margin_ratio': margin_ratio,
                'leverage': bitget_leverage,
                'required_margin': bitget_required_margin,
                'total_equity': bitget_total_equity,
                'notional_value': bitget_notional_value
            }
            
            self.logger.info(f"💰 마진 비율 계산 성공: {margin_ratio*100:.3f}% (레버리지: {bitget_leverage}x)")
            
            return result
            
        except Exception as e:
            self.logger.error(f"실제 달러 마진 비율 동적 계산 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_position_id(self, pos: Dict) -> str:
        """포지션 고유 ID 생성"""
        symbol = pos.get('symbol', self.SYMBOL)
        side = pos.get('holdSide', '')
        entry_price = pos.get('openPriceAvg', '')
        return f"{symbol}_{side}_{entry_price}"
    
    async def create_position_info(self, bitget_pos: Dict) -> PositionInfo:
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
    
    async def get_price_difference_info(self, bitget_price: float, gate_price: float) -> Dict:
        """시세 차이 정보 제공"""
        try:
            if bitget_price <= 0 or gate_price <= 0:
                return {
                    'price_diff_abs': 0,
                    'price_diff_percent': 0,
                    'exceeds_threshold': False,
                    'status': 'invalid_prices',
                    'is_abnormal': True
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
                'gate_price': gate_price
            }
            
        except Exception as e:
            self.logger.error(f"시세 차이 정보 계산 실패: {e}")
            return {
                'price_diff_abs': 0,
                'price_diff_percent': 0,
                'exceeds_threshold': False,
                'status': 'error',
                'is_abnormal': True
            }
    
    async def should_delay_processing(self, bitget_price: float, gate_price: float) -> Tuple[bool, str]:
        """시세 차이로 인한 처리 지연 여부 판단"""
        try:
            price_info = await self.get_price_difference_info(bitget_price, gate_price)
            
            # 비정상적인 시세 차이는 처리 지연
            if price_info['is_abnormal']:
                delay_reason = (f"비정상적인 시세 차이: ${price_info['price_diff_abs']:.2f} "
                              f"(비정상 임계값: ${self.ABNORMAL_PRICE_DIFF_THRESHOLD})")
                return True, delay_reason
            
            # 정상 범위 내의 높은 시세 차이
            if price_info['exceeds_threshold']:
                delay_reason = (f"정상 범위 내 높은 시세 차이: ${price_info['price_diff_abs']:.2f} "
                              f"(임계값: ${self.PRICE_SYNC_THRESHOLD})")
                return False, delay_reason  # 지연하지 않고 계속 진행
            
            return False, "정상 처리 가능"
            
        except Exception as e:
            self.logger.error(f"처리 지연 판단 실패: {e}")
            return False, "판단 오류, 정상 처리"
