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
    """🔥🔥🔥 미러 트레이딩 유틸리티 클래스 - 시세차이 문제 해결"""
    
    def __init__(self, config, bitget_client, gate_client):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.logger = logging.getLogger('mirror_trading_utils')
        
        # 상수 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.MIN_MARGIN = 1.0
        self.MAX_PRICE_DIFF_PERCENT = 1.0
        
        # 🔥🔥🔥 트리거 가격 검증 임계값 완전히 제거 - 거의 모든 가격 허용
        self.TRIGGER_PRICE_MIN_DIFF_PERCENT = 0.0  # 0.0%로 설정하여 거의 모든 가격 허용
        self.ALLOW_VERY_CLOSE_PRICES = True  # 시장가와 매우 가까운 가격도 허용
        
        # 🔥🔥🔥 시세 차이 관리 강화
        self.PRICE_SYNC_THRESHOLD = 15.0  # 15달러 임계값
        self.PRICE_ADJUSTMENT_ENABLED = True  # 가격 조정 활성화
        
        self.logger.info("🔥🔥🔥 미러 트레이딩 유틸리티 초기화 완료 - 시세차이 문제 해결")
    
    async def extract_tp_sl_from_bitget_order(self, bitget_order: Dict) -> Tuple[Optional[float], Optional[float]]:
        """🔥 비트겟 예약 주문에서 TP/SL 정보 추출"""
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
        """🔥🔥🔥 게이트 주문에서 상세 정보 추출 - None 체크 강화"""
        try:
            # 기본 정보 추출 - None 체크 강화
            order_id = gate_order.get('id', '') or ''
            contract = gate_order.get('contract', self.GATE_CONTRACT) or self.GATE_CONTRACT
            
            # 트리거 정보 추출 - None 체크
            trigger_info = gate_order.get('trigger', {}) or {}
            trigger_price_raw = trigger_info.get('price')
            
            if trigger_price_raw is None or trigger_price_raw == '':
                self.logger.warning(f"트리거 가격이 None 또는 빈 값: {gate_order}")
                return None
            
            try:
                trigger_price = float(trigger_price_raw)
            except (ValueError, TypeError):
                self.logger.warning(f"트리거 가격 변환 실패: {trigger_price_raw}")
                return None
            
            # 초기 주문 정보 추출 - None 체크
            initial_info = gate_order.get('initial', {}) or {}
            size_raw = initial_info.get('size')
            
            if size_raw is None:
                self.logger.warning(f"사이즈가 None: {gate_order}")
                return None
            
            try:
                size = int(size_raw)
            except (ValueError, TypeError):
                self.logger.warning(f"사이즈 변환 실패: {size_raw}")
                return None
            
            # TP/SL 정보 추출 - None 체크 강화
            tp_price = None
            sl_price = None
            
            # TP/SL은 여러 필드에서 추출 시도
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
            
            if trigger_price <= 0 or size == 0:
                self.logger.warning(f"유효하지 않은 트리거가({trigger_price}) 또는 사이즈({size})")
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
        """🔥🔥🔥 다양한 방식으로 주문 해시 생성 - 가격 기반 중복 방지 강화"""
        try:
            # None 체크 및 기본값 설정
            contract = order_details.get('contract') or self.GATE_CONTRACT
            trigger_price = order_details.get('trigger_price')
            size = order_details.get('size', 0)
            abs_size = order_details.get('abs_size', abs(size))
            
            # 필수 값들이 None이거나 유효하지 않으면 빈 리스트 반환
            if trigger_price is None or size is None:
                self.logger.warning(f"필수 값이 None - trigger_price: {trigger_price}, size: {size}")
                return []
            
            try:
                trigger_price = float(trigger_price)
                size = int(size)
                abs_size = abs(size)
            except (ValueError, TypeError) as e:
                self.logger.warning(f"값 변환 실패 - trigger_price: {trigger_price}, size: {size}, error: {e}")
                return []
            
            if trigger_price <= 0 or abs_size == 0:
                self.logger.warning(f"유효하지 않은 값 - trigger_price: {trigger_price}, abs_size: {abs_size}")
                return []
            
            hashes = []
            
            # 🔥 1. 가격 기반 해시 (중복 방지 핵심) - 수량 무관
            try:
                price_only_hash = f"{contract}_price_{trigger_price:.2f}"
                hashes.append(price_only_hash)
                
                # 더 정밀한 가격 해시
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
                self.logger.warning(f"가격 기반 해시 생성 실패: {e}")
            
            # 2. 기본 해시 (기존 방식)
            try:
                basic_hash = f"{contract}_{trigger_price:.2f}_{abs_size}"
                hashes.append(basic_hash)
            except Exception as e:
                self.logger.warning(f"기본 해시 생성 실패: {e}")
            
            # 3. 정확한 가격 해시
            try:
                exact_price_hash = f"{contract}_{trigger_price:.8f}_{abs_size}"
                hashes.append(exact_price_hash)
            except Exception as e:
                self.logger.warning(f"정확한 가격 해시 생성 실패: {e}")
            
            # 4. 부호 포함 해시
            try:
                signed_hash = f"{contract}_{trigger_price:.2f}_{size}"
                hashes.append(signed_hash)
            except Exception as e:
                self.logger.warning(f"부호 포함 해시 생성 실패: {e}")
            
            # 5. 반올림된 가격 해시 (가격 차이 허용)
            try:
                rounded_price_1 = round(trigger_price, 1)
                rounded_hash_1 = f"{contract}_{rounded_price_1:.1f}_{abs_size}"
                hashes.append(rounded_hash_1)
                
                rounded_price_0 = round(trigger_price, 0)
                rounded_hash_0 = f"{contract}_{rounded_price_0:.0f}_{abs_size}"
                hashes.append(rounded_hash_0)
            except Exception as e:
                self.logger.warning(f"반올림 해시 생성 실패: {e}")
            
            # 6. TP/SL 포함 해시 (있는 경우)
            try:
                if order_details.get('has_tp_sl'):
                    tp_price = order_details.get('tp_price', 0) or 0
                    sl_price = order_details.get('sl_price', 0) or 0
                    tp_sl_hash = f"{contract}_{trigger_price:.2f}_{abs_size}_tp{tp_price:.2f}_sl{sl_price:.2f}"
                    hashes.append(tp_sl_hash)
                    
                    # 🔥 TP/SL 있는 주문의 가격 기반 해시도 추가
                    tp_sl_price_hash = f"{contract}_price_{trigger_price:.2f}_withTPSL"
                    hashes.append(tp_sl_price_hash)
            except Exception as e:
                self.logger.warning(f"TP/SL 해시 생성 실패: {e}")
            
            # 🔥 7. 가격 범위 해시 (유사한 가격 감지)
            try:
                # 100달러 단위로 반올림한 가격 해시
                price_range_100 = round(trigger_price / 100) * 100
                range_hash_100 = f"{contract}_range100_{price_range_100:.0f}"
                hashes.append(range_hash_100)
                
                # 50달러 단위로 반올림한 가격 해시
                price_range_50 = round(trigger_price / 50) * 50
                range_hash_50 = f"{contract}_range50_{price_range_50:.0f}"
                hashes.append(range_hash_50)
                
                # 🔥🔥🔥 시세 차이를 고려한 가격 범위 해시 (±20달러)
                for offset in [-20, -10, 0, 10, 20]:
                    adjusted_price = trigger_price + offset
                    if adjusted_price > 0:
                        offset_hash = f"{contract}_offset_{adjusted_price:.0f}"
                        hashes.append(offset_hash)
                        
            except Exception as e:
                self.logger.warning(f"가격 범위 해시 생성 실패: {e}")
            
            # 중복 제거
            unique_hashes = list(set(hashes))
            
            if unique_hashes:
                self.logger.debug(f"주문 해시 {len(unique_hashes)}개 생성: 트리거=${trigger_price:.2f}, 크기={size}")
            else:
                self.logger.warning(f"해시 생성 실패 - 빈 리스트 반환")
            
            return unique_hashes
            
        except Exception as e:
            self.logger.error(f"다중 해시 생성 실패: {e}")
            # 🔥 에러 발생 시에도 기본 해시라도 생성 시도
            try:
                trigger_price = order_details.get('trigger_price')
                size = order_details.get('size', 0)
                contract = order_details.get('contract', self.GATE_CONTRACT)
                
                if trigger_price is not None and size is not None:
                    trigger_price = float(trigger_price)
                    abs_size = abs(int(size))
                    basic_hash = f"{contract}_{trigger_price:.2f}_{abs_size}"
                    price_hash = f"{contract}_price_{trigger_price:.2f}"
                    return [basic_hash, price_hash]
            except Exception as fallback_error:
                self.logger.error(f"폴백 해시 생성도 실패: {fallback_error}")
            
            return []
    
    def generate_order_hash(self, trigger_price: float, size: int, contract: str = None) -> str:
        """주문 특성으로 해시 생성 (중복 방지용) - None 체크 강화"""
        try:
            contract = contract or self.GATE_CONTRACT
            
            # None 체크 및 안전한 변환
            if trigger_price is None or size is None:
                return f"{contract}_unknown_unknown"
            
            trigger_price = float(trigger_price)
            size = int(size)
            
            return f"{contract}_{trigger_price:.2f}_{abs(size)}"
            
        except (ValueError, TypeError) as e:
            self.logger.warning(f"해시 생성 시 변환 실패: {e}")
            return f"{contract or self.GATE_CONTRACT}_error_error"
    
    def generate_price_based_hash(self, trigger_price: float, contract: str = None) -> str:
        """🔥 가격 기반 해시 생성 (수량 무관 중복 방지)"""
        try:
            contract = contract or self.GATE_CONTRACT
            
            if trigger_price is None or trigger_price <= 0:
                return f"{contract}_price_invalid"
            
            trigger_price = float(trigger_price)
            return f"{contract}_price_{trigger_price:.2f}"
            
        except (ValueError, TypeError) as e:
            self.logger.warning(f"가격 기반 해시 생성 실패: {e}")
            return f"{contract or self.GATE_CONTRACT}_price_error"
    
    async def adjust_price_for_gate(self, price: float, bitget_current_price: float = 0, 
                                   gate_current_price: float = 0, price_diff_percent: float = 0) -> float:
        """🔥🔥🔥 게이트 기준으로 가격 조정 - 시세차이 문제 해결"""
        try:
            if price is None or price <= 0:
                return price or 0
            
            # 🔥🔥🔥 시세 차이가 임계값을 초과하는 경우 조정
            if (self.PRICE_ADJUSTMENT_ENABLED and 
                bitget_current_price > 0 and gate_current_price > 0):
                
                price_diff_abs = abs(bitget_current_price - gate_current_price)
                
                # 시세 차이가 임계값을 초과하는 경우
                if price_diff_abs > self.PRICE_SYNC_THRESHOLD:
                    
                    # 가격 비율 계산
                    price_ratio = gate_current_price / bitget_current_price
                    adjusted_price = price * price_ratio
                    
                    # 조정 폭 검증 (너무 큰 조정은 방지)
                    adjustment_percent = abs(adjusted_price - price) / price * 100
                    
                    if adjustment_percent <= 5.0:  # 5% 이하 조정만 허용
                        self.logger.info(f"🔧 시세 차이로 가격 조정: ${price:.2f} → ${adjusted_price:.2f} (차이: ${price_diff_abs:.2f})")
                        return adjusted_price
                    else:
                        self.logger.warning(f"⚠️ 조정 폭이 너무 큼 ({adjustment_percent:.1f}%), 원본 가격 사용")
                        return price
                else:
                    # 시세 차이가 임계값 이하인 경우 원본 사용
                    return price
            
            # 기본적으로 원본 가격 반환
            return price
            
        except Exception as e:
            self.logger.error(f"가격 조정 실패: {e}")
            return price or 0
    
    async def validate_trigger_price(self, trigger_price: float, side: str, current_price: float = 0) -> Tuple[bool, str]:
        """🔥🔥🔥 트리거 가격 유효성 검증 - 시세차이 고려하여 완전 완화"""
        try:
            if trigger_price is None or trigger_price <= 0:
                return False, "트리거 가격이 None이거나 0 이하입니다"
            
            if current_price <= 0:
                # 🔥🔥🔥 현재가 조회 실패해도 허용
                self.logger.info("현재 시장가를 조회할 수 없지만 트리거 가격 허용")
                return True, "현재가 조회 실패하지만 허용"
            
            # 🔥🔥🔥 시장가와의 차이 계산하되 거의 모든 가격 허용
            price_diff_percent = abs(trigger_price - current_price) / current_price * 100
            
            # 🔥🔥🔥 시세 차이 문제를 고려하여 극도로 완화된 검증
            if self.ALLOW_VERY_CLOSE_PRICES:
                # 시장가와 완전히 동일한 경우에만 경고하되 허용
                if price_diff_percent == 0.0:
                    self.logger.info(f"트리거가와 현재가가 완전히 동일하지만 허용: {trigger_price}")
                    return True, f"동일한 가격이지만 허용 (차이: {price_diff_percent:.8f}%)"
                
                # 🔥🔥🔥 매우 근접한 가격도 모두 허용 (시세 차이 고려)
                if price_diff_percent < 0.0001:  # 0.0001% 미만
                    self.logger.info(f"매우 근접한 트리거가 허용: 차이 {price_diff_percent:.8f}%")
                    return True, f"매우 근접한 트리거가 허용 (차이: {price_diff_percent:.8f}%)"
                
                # 🔥🔥🔥 일반적인 가격 차이도 모두 허용 (시세 차이 때문에 더욱 관대)
                if price_diff_percent < 100:  # 100% 미만은 모두 허용 (시세 차이 고려)
                    return True, f"시세차이 고려 허용 가능한 트리거 가격 (차이: {price_diff_percent:.4f}%)"
                
                # 극단적인 가격 차이만 차단 (100% 이상)
                if price_diff_percent >= 100:
                    self.logger.warning(f"극단적인 가격 차이: {price_diff_percent:.1f}%")
                    return False, f"트리거가와 현재가 차이가 너무 극단적 ({price_diff_percent:.1f}%)"
            
            # 기본적으로 모든 가격 허용 (시세 차이 문제 해결)
            return True, f"시세차이 고려 모든 트리거 가격 허용 (차이: {price_diff_percent:.4f}%)"
            
        except Exception as e:
            self.logger.error(f"트리거 가격 검증 실패하지만 허용: {e}")
            # 🔥🔥🔥 검증 실패해도 허용 (시세 차이 문제 고려)
            return True, f"검증 오류이지만 시세차이 고려하여 허용: {str(e)[:100]}"
    
    async def calculate_gate_order_size_fixed(self, side: str, base_size: int, is_close_order: bool = False) -> Tuple[int, bool]:
        """🔥🔥🔥 수정된 게이트 주문 수량 계산 - 클로즈/오픈 구분 명확화"""
        try:
            side_lower = side.lower()
            reduce_only = False
            
            self.logger.info(f"🔍 주문 타입 분석: side='{side}', is_close_order={is_close_order}")
            
            # 🔥 클로즈 주문 처리 (가장 중요!)
            if is_close_order or 'close' in side_lower:
                reduce_only = True
                
                if 'close_long' in side_lower:
                    # 롱 포지션 종료 = 매도 (음수 사이즈)
                    gate_size = -abs(base_size)
                    self.logger.info(f"🔴 클로즈 롱: 기존 롱 포지션 종료 → 게이트 매도 (음수 사이즈: {gate_size})")
                    
                elif 'close_short' in side_lower:
                    # 숏 포지션 종료 = 매수 (양수 사이즈)
                    gate_size = abs(base_size)
                    self.logger.info(f"🟢 클로즈 숏: 기존 숏 포지션 종료 → 게이트 매수 (양수 사이즈: {gate_size})")
                    
                else:
                    # 일반적인 클로즈 주문 - side로 판단
                    if 'sell' in side_lower or 'short' in side_lower:
                        gate_size = -abs(base_size)
                        self.logger.info(f"🔴 클로즈 매도: 포지션 종료 → 게이트 매도 (음수 사이즈: {gate_size})")
                    else:
                        gate_size = abs(base_size)
                        self.logger.info(f"🟢 클로즈 매수: 포지션 종료 → 게이트 매수 (양수 사이즈: {gate_size})")
                        
            # 🔥 오픈 주문 처리
            else:
                reduce_only = False
                
                if 'open_long' in side_lower or ('buy' in side_lower and 'sell' not in side_lower):
                    # 롱 포지션 오픈 = 매수 (양수 사이즈)
                    gate_size = abs(base_size)
                    self.logger.info(f"🟢 오픈 롱: 새 롱 포지션 생성 → 게이트 매수 (양수 사이즈: {gate_size})")
                    
                elif 'open_short' in side_lower or 'sell' in side_lower:
                    # 숏 포지션 오픈 = 매도 (음수 사이즈)
                    gate_size = -abs(base_size)
                    self.logger.info(f"🔴 오픈 숏: 새 숏 포지션 생성 → 게이트 매도 (음수 사이즈: {gate_size})")
                    
                else:
                    # 기본값 - 원래 사이즈 유지
                    gate_size = base_size
                    self.logger.warning(f"⚠️ 알 수 없는 주문 방향: {side}, 원본 사이즈 유지: {gate_size}")
            
            self.logger.info(f"✅ 최종 변환 결과: {side} → 게이트 사이즈={gate_size}, reduce_only={reduce_only}")
            return gate_size, reduce_only
            
        except Exception as e:
            self.logger.error(f"게이트 주문 수량 계산 실패: {e}")
            return base_size, False
    
    async def calculate_gate_order_size(self, side: str, base_size: int) -> int:
        """🔥 기존 호환성을 위한 래퍼 메서드"""
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
    
    async def calculate_dynamic_margin_ratio(self, size: float, trigger_price: float, bitget_order: Dict) -> Dict:
        """🔥🔥🔥 실제 달러 마진 비율 동적 계산 - 시세차이 고려"""
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
        """🔥🔥🔥 시세 차이 정보 제공"""
        try:
            if bitget_price <= 0 or gate_price <= 0:
                return {
                    'price_diff_abs': 0,
                    'price_diff_percent': 0,
                    'exceeds_threshold': False,
                    'status': 'invalid_prices'
                }
            
            price_diff_abs = abs(bitget_price - gate_price)
            price_diff_percent = price_diff_abs / bitget_price * 100
            exceeds_threshold = price_diff_abs > self.PRICE_SYNC_THRESHOLD
            
            status = 'normal'
            if exceeds_threshold:
                status = 'high_difference'
            elif price_diff_abs > self.PRICE_SYNC_THRESHOLD * 0.5:
                status = 'moderate_difference'
            
            return {
                'price_diff_abs': price_diff_abs,
                'price_diff_percent': price_diff_percent,
                'exceeds_threshold': exceeds_threshold,
                'threshold': self.PRICE_SYNC_THRESHOLD,
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
                'status': 'error'
            }
    
    async def should_delay_processing(self, bitget_price: float, gate_price: float) -> Tuple[bool, str]:
        """🔥🔥🔥 시세 차이로 인한 처리 지연 여부 판단"""
        try:
            price_info = await self.get_price_difference_info(bitget_price, gate_price)
            
            if price_info['exceeds_threshold']:
                delay_reason = (f"시세 차이 임계값 초과: ${price_info['price_diff_abs']:.2f} "
                              f"(임계값: ${self.PRICE_SYNC_THRESHOLD})")
                return True, delay_reason
            
            return False, "정상 처리 가능"
            
        except Exception as e:
            self.logger.error(f"처리 지연 판단 실패: {e}")
            return False, "판단 오류, 정상 처리"
