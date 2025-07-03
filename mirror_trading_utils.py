import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class PositionInfo:
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
    success: bool
    action: str
    bitget_data: Dict
    gate_data: Optional[Dict] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

class MirrorTradingUtils:
    def __init__(self, config, bitget_client, gate_client):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.logger = logging.getLogger('mirror_trading_utils')
        
        # 기본 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.MIN_MARGIN = 1.0
        self.MAX_PRICE_DIFF_PERCENT = 50.0
        
        # 레버리지 설정
        self.DEFAULT_LEVERAGE = 30
        self.MAX_LEVERAGE = 100
        self.MIN_LEVERAGE = 1
        self.leverage_cache = {}
        
        # 복제 비율 설정
        self.DEFAULT_RATIO_MULTIPLIER = 1.0
        self.MAX_RATIO_MULTIPLIER = 10.0
        self.MIN_RATIO_MULTIPLIER = 0.1
        self.current_ratio_multiplier = 1.0
        
        # 복제 비율 설명
        self.RATIO_DESCRIPTIONS = {
            0.1: "원본의 10% 크기로 대폭 축소", 0.2: "원본의 20% 크기로 축소", 0.3: "원본의 30% 크기로 축소",
            0.4: "원본의 40% 크기로 축소", 0.5: "원본의 절반 크기로 축소", 0.6: "원본의 60% 크기로 축소",
            0.7: "원본의 70% 크기로 축소", 0.8: "원본의 80% 크기로 축소", 0.9: "원본의 90% 크기로 축소",
            1.0: "원본 비율 그대로 복제", 1.1: "원본의 1.1배로 10% 확대", 1.2: "원본의 1.2배로 20% 확대",
            1.3: "원본의 1.3배로 30% 확대", 1.4: "원본의 1.4배로 40% 확대", 1.5: "원본의 1.5배로 50% 확대",
            2.0: "원본의 2배로 확대", 2.5: "원본의 2.5배로 확대", 3.0: "원본의 3배로 확대",
            5.0: "원본의 5배로 확대", 10.0: "원본의 10배로 최대 확대"
        }
        
        # 가격 검증 설정
        self.TRIGGER_PRICE_MIN_DIFF_PERCENT = 0.0
        self.ALLOW_VERY_CLOSE_PRICES = True
        self.PRICE_SYNC_THRESHOLD = 1000.0
        self.PRICE_ADJUSTMENT_ENABLED = True
        self.ABNORMAL_PRICE_DIFF_THRESHOLD = 10000.0
        
        # 클로즈 주문 감지
        self.CLOSE_ORDER_KEYWORDS = [
            'close', 'close_long', 'close_short', 'close long', 'close short',
            'exit', 'exit_long', 'exit_short', 'exit long', 'exit short', 'reduce'
        ]
        
        self.TP_SL_ONLY_ORDER_TYPES = ['profit_loss', 'stop_loss_only', 'take_profit_only']
        self.CLOSE_ORDER_STRICT_MODE = False
        
        self.logger.info("미러 트레이딩 유틸리티 초기화 완료 - 복제 비율 지원")
    
    async def calculate_dynamic_margin_ratio_with_multiplier(self, size: float, trigger_price: float, 
                                                           bitget_order: Dict, ratio_multiplier: float = 1.0) -> Dict:
        try:
            if size is None or trigger_price is None:
                return {'success': False, 'error': 'size나 trigger_price가 None입니다'}
            
            # 복제 비율 검증
            validated_ratio = self.validate_ratio_multiplier(ratio_multiplier)
            if validated_ratio != ratio_multiplier:
                self.logger.warning(f"복제 비율 조정됨: {ratio_multiplier} → {validated_ratio}")
                ratio_multiplier = validated_ratio
            
            self.logger.info(f"복제 비율 적용 마진 계산: size={size}, ratio={ratio_multiplier}x")
            
            # 레버리지 추출
            bitget_account = await self.bitget.get_account_info()
            extracted_leverage = await self.extract_bitget_leverage_enhanced(
                order_data=bitget_order, position_data=None, account_data=bitget_account
            )
            
            self.logger.info(f"추출된 레버리지: {extracted_leverage}x")
            
            # 비트겟 총 자산 조회
            bitget_total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            if bitget_total_equity <= 0:
                return {'success': False, 'error': '비트겟 총 자산이 0이거나 조회 실패'}
            
            # 비트겟 마진 사용량 계산
            bitget_notional_value = size * trigger_price
            bitget_required_margin = bitget_notional_value / extracted_leverage
            
            # 기본 마진 비율 계산
            base_margin_ratio = bitget_required_margin / bitget_total_equity
            
            # 복제 비율 적용
            adjusted_margin_ratio = base_margin_ratio * ratio_multiplier
            
            # 안전 검사
            if adjusted_margin_ratio <= 0:
                return {'success': False, 'error': f'조정된 마진 비율이 0 이하입니다: {adjusted_margin_ratio:.4f}'}
            elif adjusted_margin_ratio > 1:
                original_ratio = adjusted_margin_ratio
                adjusted_margin_ratio = 0.95
                self.logger.warning(f"마진 비율 95%로 제한: {original_ratio:.4f} → {adjusted_margin_ratio:.4f}")
            
            # 조정된 마진으로 재계산
            adjusted_required_margin = bitget_total_equity * adjusted_margin_ratio
            adjusted_notional_value = adjusted_required_margin * extracted_leverage
            
            # 복제 비율 효과 분석
            ratio_effect = self.analyze_ratio_multiplier_effect(ratio_multiplier, base_margin_ratio, adjusted_margin_ratio)
            
            result = {
                'success': True, 'margin_ratio': adjusted_margin_ratio, 'leverage': extracted_leverage,
                'required_margin': adjusted_required_margin, 'total_equity': bitget_total_equity,
                'notional_value': adjusted_notional_value, 'ratio_multiplier': ratio_multiplier,
                'base_margin_ratio': base_margin_ratio, 'base_required_margin': bitget_required_margin,
                'base_notional_value': bitget_notional_value, 'ratio_effect': ratio_effect,
                'ratio_description': self.get_ratio_multiplier_description(ratio_multiplier)
            }
            
            self.logger.info(f"마진 계산 성공: 기본 {base_margin_ratio*100:.3f}% → 최종 {adjusted_margin_ratio*100:.3f}% (비율: {ratio_multiplier}x, 레버리지: {extracted_leverage}x)")
            
            return result
            
        except Exception as e:
            self.logger.error(f"복제 비율 적용 마진 계산 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    async def calculate_dynamic_margin_ratio(self, size: float, trigger_price: float, bitget_order: Dict) -> Dict:
        return await self.calculate_dynamic_margin_ratio_with_multiplier(size, trigger_price, bitget_order, 1.0)
    
    def validate_ratio_multiplier(self, ratio_multiplier: float) -> float:
        try:
            if ratio_multiplier is None:
                self.logger.warning(f"복제 비율이 None이므로 기본값 사용: 1.0")
                return self.DEFAULT_RATIO_MULTIPLIER
            
            ratio_multiplier = float(ratio_multiplier)
            
            if ratio_multiplier < self.MIN_RATIO_MULTIPLIER:
                self.logger.warning(f"복제 비율이 너무 작음 ({ratio_multiplier}), 최소값 사용: {self.MIN_RATIO_MULTIPLIER}")
                return self.MIN_RATIO_MULTIPLIER
            
            if ratio_multiplier > self.MAX_RATIO_MULTIPLIER:
                self.logger.warning(f"복제 비율이 너무 큼 ({ratio_multiplier}), 최대값 사용: {self.MAX_RATIO_MULTIPLIER}")
                return self.MAX_RATIO_MULTIPLIER
            
            # 리스크 경고
            if ratio_multiplier > 5.0:
                self.logger.warning(f"매우 높은 복제 비율 ({ratio_multiplier}x). 리스크 관리 필요.")
            elif ratio_multiplier < 0.5:
                self.logger.info(f"보수적인 복제 비율 ({ratio_multiplier}x). 안전한 설정.")
            
            return ratio_multiplier
            
        except (ValueError, TypeError):
            self.logger.error(f"복제 비율 변환 실패 ({ratio_multiplier}), 기본값 사용: {self.DEFAULT_RATIO_MULTIPLIER}")
            return self.DEFAULT_RATIO_MULTIPLIER
    
    def get_ratio_multiplier_description(self, ratio_multiplier: float) -> str:
        try:
            # 정확한 매칭
            if ratio_multiplier in self.RATIO_DESCRIPTIONS:
                return self.RATIO_DESCRIPTIONS[ratio_multiplier]
            
            # 가장 가까운 값 찾기
            closest_ratio = min(self.RATIO_DESCRIPTIONS.keys(), key=lambda x: abs(x - ratio_multiplier))
            
            if abs(closest_ratio - ratio_multiplier) < 0.05:
                return self.RATIO_DESCRIPTIONS[closest_ratio]
            
            # 커스텀 설명
            if ratio_multiplier == 1.0:
                return "원본 비율 그대로"
            elif ratio_multiplier < 1.0:
                percentage = ratio_multiplier * 100
                return f"원본의 {percentage:.1f}% 크기로 축소"
            else:
                return f"원본의 {ratio_multiplier:.1f}배 크기로 확대"
                
        except Exception as e:
            self.logger.error(f"복제 비율 설명 생성 실패: {e}")
            return "비율 정보 없음"
    
    def analyze_ratio_multiplier_effect(self, ratio_multiplier: float, base_ratio: float, adjusted_ratio: float) -> Dict:
        try:
            effect_analysis = {
                'multiplier': ratio_multiplier, 'base_percentage': base_ratio * 100,
                'adjusted_percentage': adjusted_ratio * 100, 'absolute_increase': (adjusted_ratio - base_ratio) * 100,
                'relative_increase_percent': ((adjusted_ratio / base_ratio) - 1) * 100 if base_ratio > 0 else 0,
                'description': self.get_ratio_multiplier_description(ratio_multiplier),
                'impact': '', 'risk_level': '', 'recommendation': ''
            }
            
            # 영향 분석
            if ratio_multiplier == 1.0:
                effect_analysis['impact'] = "원본과 동일한 리스크"
                effect_analysis['risk_level'] = "기본"
                effect_analysis['recommendation'] = "표준 미러링"
            elif ratio_multiplier < 0.5:
                effect_analysis['impact'] = f"리스크 대폭 감소 ({effect_analysis['relative_increase_percent']:.1f}%)"
                effect_analysis['risk_level'] = "매우 낮음"
                effect_analysis['recommendation'] = "매우 보수적 - 테스트나 안전 운영에 적합"
            elif ratio_multiplier < 1.0:
                effect_analysis['impact'] = f"리스크 감소 ({effect_analysis['relative_increase_percent']:.1f}%)"
                effect_analysis['risk_level'] = "낮음"
                effect_analysis['recommendation'] = "보수적 - 안정적인 운영"
            elif ratio_multiplier <= 1.5:
                effect_analysis['impact'] = f"리스크 소폭 증가 (+{effect_analysis['relative_increase_percent']:.1f}%)"
                effect_analysis['risk_level'] = "보통"
                effect_analysis['recommendation'] = "적극적 - 수익 확대 시도"
            elif ratio_multiplier <= 3.0:
                effect_analysis['impact'] = f"리스크 상당 증가 (+{effect_analysis['relative_increase_percent']:.1f}%)"
                effect_analysis['risk_level'] = "높음"
                effect_analysis['recommendation'] = "공격적 - 리스크 관리 필수"
            else:
                effect_analysis['impact'] = f"리스크 대폭 증가 (+{effect_analysis['relative_increase_percent']:.1f}%)"
                effect_analysis['risk_level'] = "매우 높음"
                effect_analysis['recommendation'] = "매우 공격적 - 극도로 신중한 관리 필요"
            
            return effect_analysis
            
        except Exception as e:
            self.logger.error(f"복제 비율 효과 분석 실패: {e}")
            return {
                'multiplier': ratio_multiplier, 'description': "분석 실패", 'impact': "알 수 없음",
                'risk_level': "불명", 'recommendation': "신중한 검토 필요"
            }
    
    async def extract_bitget_leverage_enhanced(self, order_data: Dict = None, position_data: Dict = None, account_data: Dict = None) -> int:
        try:
            extracted_leverage = self.DEFAULT_LEVERAGE
            source = "default"
            
            # 1. 주문 데이터에서 추출
            if order_data:
                for leverage_field in ['leverage', 'marginLeverage', 'leverageRatio']:
                    order_leverage = order_data.get(leverage_field)
                    if order_leverage:
                        try:
                            lev_value = int(float(order_leverage))
                            if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                extracted_leverage = lev_value
                                source = f"order({leverage_field})"
                                self.logger.info(f"주문에서 레버리지 추출: {extracted_leverage}x ({source})")
                                return extracted_leverage
                        except (ValueError, TypeError):
                            continue
            
            # 2. 포지션 데이터에서 추출
            if position_data:
                for leverage_field in ['leverage', 'marginLeverage', 'leverageRatio']:
                    pos_leverage = position_data.get(leverage_field)
                    if pos_leverage:
                        try:
                            lev_value = int(float(pos_leverage))
                            if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                extracted_leverage = lev_value
                                source = f"position({leverage_field})"
                                self.logger.info(f"포지션에서 레버리지 추출: {extracted_leverage}x ({source})")
                                return extracted_leverage
                        except (ValueError, TypeError):
                            continue
            
            # 3. 계정 데이터에서 추출
            if account_data:
                for leverage_field in ['crossMarginLeverage', 'leverage', 'defaultLeverage', 'marginLeverage']:
                    account_leverage = account_data.get(leverage_field)
                    if account_leverage:
                        try:
                            lev_value = int(float(account_leverage))
                            if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                extracted_leverage = lev_value
                                source = f"account({leverage_field})"
                                self.logger.info(f"계정에서 레버리지 추출: {extracted_leverage}x ({source})")
                                return extracted_leverage
                        except (ValueError, TypeError):
                            continue
            
            # 4. 실시간 계정 조회
            try:
                fresh_account = await self.bitget.get_account_info()
                for leverage_field in ['crossMarginLeverage', 'leverage', 'defaultLeverage', 'marginLeverage']:
                    account_leverage = fresh_account.get(leverage_field)
                    if account_leverage:
                        try:
                            lev_value = int(float(account_leverage))
                            if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                extracted_leverage = lev_value
                                source = f"fresh_account({leverage_field})"
                                self.logger.info(f"실시간 계정에서 레버리지 추출: {extracted_leverage}x ({source})")
                                
                                # 결과 캐시
                                self.leverage_cache['bitget_default'] = {
                                    'leverage': extracted_leverage, 'timestamp': datetime.now(), 'source': source
                                }
                                return extracted_leverage
                        except (ValueError, TypeError):
                            continue
            except Exception as e:
                self.logger.warning(f"실시간 계정 조회 실패: {e}")
            
            # 5. 실시간 포지션 조회
            try:
                positions = await self.bitget.get_positions(self.SYMBOL)
                for position in positions:
                    if float(position.get('total', 0)) > 0:
                        pos_leverage = position.get('leverage')
                        if pos_leverage:
                            try:
                                lev_value = int(float(pos_leverage))
                                if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                    extracted_leverage = lev_value
                                    source = "live_position"
                                    self.logger.info(f"실시간 포지션에서 레버리지 추출: {extracted_leverage}x ({source})")
                                    return extracted_leverage
                            except (ValueError, TypeError):
                                continue
            except Exception as e:
                self.logger.warning(f"실시간 포지션 조회 실패: {e}")
            
            # 6. 캐시에서 조회
            if 'bitget_default' in self.leverage_cache:
                cache_data = self.leverage_cache['bitget_default']
                cache_time = cache_data['timestamp']
                if (datetime.now() - cache_time).total_seconds() < 3600:  # 1시간 캐시
                    extracted_leverage = cache_data['leverage']
                    source = f"cache({cache_data['source']})"
                    self.logger.info(f"캐시에서 레버리지 추출: {extracted_leverage}x ({source})")
                    return extracted_leverage
            
            # 기본값 사용
            self.logger.warning(f"레버리지 추출 실패, 기본값 사용: {extracted_leverage}x")
            return extracted_leverage
            
        except Exception as e:
            self.logger.error(f"레버리지 추출 오류: {e}")
            return self.DEFAULT_LEVERAGE
    
    async def determine_close_order_details_enhanced(self, bitget_order: Dict) -> Dict:
        try:
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            reduce_only = bitget_order.get('reduceOnly', False)
            order_type = bitget_order.get('orderType', bitget_order.get('planType', '')).lower()
            
            self.logger.info(f"주문 분석: side='{side}', reduce_only={reduce_only}, order_type='{order_type}'")
            
            # 강화된 클로즈 주문 감지
            is_close_order = False
            detection_method = "none"
            
            # 1. reduce_only 플래그 (가장 신뢰할 수 있음)
            if reduce_only is True or reduce_only == 'true' or str(reduce_only).lower() == 'true':
                is_close_order = True
                detection_method = "reduce_only_flag"
                self.logger.info(f"reduce_only=True로 클로즈 주문 확인")
            
            # 2. 명시적 클로즈 키워드
            elif not is_close_order:
                for keyword in self.CLOSE_ORDER_KEYWORDS:
                    if keyword in side:
                        is_close_order = True
                        detection_method = f"side_keyword_{keyword}"
                        self.logger.info(f"사이드 키워드로 클로즈 주문 확인: '{side}'에 '{keyword}' 포함")
                        break
            
            # 3. TP/SL 전용 주문 타입
            elif not is_close_order:
                for tp_sl_type in self.TP_SL_ONLY_ORDER_TYPES:
                    if tp_sl_type in order_type:
                        is_close_order = True
                        detection_method = f"tp_sl_only_type_{tp_sl_type}"
                        self.logger.info(f"TP/SL 타입으로 클로즈 주문 확인: '{order_type}'에 '{tp_sl_type}' 포함")
                        break
            
            # 4. TP/SL이 설정된 주문은 오픈 주문으로 처리 (잘못된 분류 방지)
            if not is_close_order:
                tp_price, sl_price = await self.extract_tp_sl_from_bitget_order(bitget_order)
                
                if tp_price or sl_price:
                    is_close_order = False
                    detection_method = "tp_sl_set_but_open_order"
                    self.logger.info(f"TP/SL 설정된 오픈 주문 (TP={tp_price}, SL={sl_price}) → TP/SL이 포함된 신규 포지션 생성")
            
            # 5. 특수 클로즈 패턴
            if not is_close_order:
                special_patterns = ['exit', 'liquidat']
                for pattern in special_patterns:
                    if pattern in side or pattern in order_type:
                        is_close_order = True
                        detection_method = f"special_pattern_{pattern}"
                        self.logger.info(f"특수 패턴으로 클로즈 주문 확인: '{pattern}'")
                        break
            
            # 최종 확인
            if not is_close_order:
                detection_method = "default_open_order"
                self.logger.info(f"오픈 주문으로 확인 (신규 포지션 생성)")
            
            self.logger.info(f"클로즈 주문 분석 결과: is_close_order={is_close_order}, method={detection_method}")
            
            # 주문 방향 및 포지션 사이드 결정
            order_direction = None
            position_side = None
            
            if is_close_order:
                # 클로즈 주문
                if 'close_long' in side or 'exit_long' in side:
                    order_direction = 'sell'  # 롱 포지션을 매도로 청산
                    position_side = 'long'
                elif 'close_short' in side or 'exit_short' in side:
                    order_direction = 'buy'   # 숏 포지션을 매수로 청산
                    position_side = 'short'
                elif 'sell' in side and 'buy' not in side:
                    order_direction = 'sell'
                    position_side = 'long'
                elif 'buy' in side and 'sell' not in side:
                    order_direction = 'buy'
                    position_side = 'short'
                else:
                    # 현재 포지션을 조회하여 방향 결정
                    try:
                        bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                        active_positions = [pos for pos in bitget_positions if float(pos.get('total', 0)) > 0]
                        
                        if active_positions:
                            main_position = active_positions[0]
                            current_side = main_position.get('holdSide', '').lower()
                            
                            if current_side == 'long':
                                order_direction = 'sell'
                                position_side = 'long'
                                self.logger.info(f"현재 롱 포지션 기준: 매도로 청산")
                            elif current_side == 'short':
                                order_direction = 'buy'
                                position_side = 'short'
                                self.logger.info(f"현재 숏 포지션 기준: 매수로 청산")
                            else:
                                order_direction = 'sell'
                                position_side = 'long'
                        else:
                            order_direction = 'sell'
                            position_side = 'long'
                            self.logger.warning(f"활성 포지션 없음, 기본값 사용: long→sell")
                            
                    except Exception as e:
                        self.logger.error(f"포지션 조회 실패, 기본값 사용: {e}")
                        order_direction = 'sell'
                        position_side = 'long'
            else:
                # 오픈 주문 (TP/SL 설정 포함)
                if 'buy' in side or 'long' in side:
                    order_direction = 'buy'
                    position_side = 'long'
                elif 'sell' in side or 'short' in side:
                    order_direction = 'sell'
                    position_side = 'short'
                else:
                    order_direction = 'buy'
                    position_side = 'long'
            
            result = {
                'is_close_order': is_close_order, 'order_direction': order_direction, 'position_side': position_side,
                'original_side': side, 'reduce_only': reduce_only, 'order_type': order_type,
                'detection_method': detection_method
            }
            
            self.logger.info(f"강화된 클로즈 주문 분석 결과: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"강화된 클로즈 주문 상세 판단 실패: {e}")
            return {
                'is_close_order': False, 'order_direction': 'buy', 'position_side': 'long',
                'original_side': side if 'side' in locals() else '', 'reduce_only': False,
                'order_type': order_type if 'order_type' in locals() else '', 'detection_method': 'fallback'
            }
    
    async def determine_close_order_details(self, bitget_order: Dict) -> Dict:
        return await self.determine_close_order_details_enhanced(bitget_order)
    
    async def extract_tp_sl_from_bitget_order(self, bitget_order: Dict) -> Tuple[Optional[float], Optional[float]]:
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
                            self.logger.info(f"TP 가격 추출: {field} = {tp_price}")
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
                            self.logger.info(f"SL 가격 추출: {field} = {sl_price}")
                            break
                    except:
                        continue
            
            return tp_price, sl_price
            
        except Exception as e:
            self.logger.error(f"TP/SL 추출 실패: {e}")
            return None, None
    
    async def extract_gate_order_details(self, gate_order: Dict) -> Optional[Dict]:
        try:
            order_id = gate_order.get('id', '') or ''
            contract = gate_order.get('contract', self.GATE_CONTRACT) or self.GATE_CONTRACT
            
            # 트리거 정보 추출
            trigger_info = gate_order.get('trigger', {}) or {}
            trigger_price_raw = trigger_info.get('price')
            
            if trigger_price_raw is None or trigger_price_raw == '':
                self.logger.debug(f"트리거 가격이 None이거나 비어있음: {gate_order}")
                return None
            
            try:
                trigger_price = float(trigger_price_raw)
            except (ValueError, TypeError):
                self.logger.debug(f"트리거 가격 변환 실패: {trigger_price_raw}")
                return None
            
            # 초기 주문 정보 추출
            initial_info = gate_order.get('initial', {}) or {}
            size_raw = initial_info.get('size')
            
            # 누락되거나 0인 크기 처리
            size = 1  # 기본값
            if size_raw is not None:
                try:
                    size = int(size_raw)
                except (ValueError, TypeError):
                    self.logger.debug(f"크기 변환 실패, 기본값 사용: {size_raw}")
                    size = 1
            else:
                self.logger.debug(f"크기가 None, 기본값 사용: {gate_order}")
            
            # TP/SL 정보 추출
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
                self.logger.debug(f"유효하지 않은 트리거 가격: {trigger_price}")
                return None
            
            return {
                'order_id': order_id, 'contract': contract, 'trigger_price': trigger_price,
                'size': size, 'abs_size': abs(size), 'tp_price': tp_price, 'sl_price': sl_price,
                'has_tp_sl': bool(tp_price or sl_price), 'gate_order_raw': gate_order
            }
            
        except Exception as e:
            self.logger.error(f"게이트 주문 상세 추출 실패: {e}")
            return None
    
    async def generate_multiple_order_hashes(self, order_details: Dict) -> List[str]:
        try:
            # 필수 필드 검증
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
                self.logger.debug(f"값 변환 실패 - trigger_price: {trigger_price}, size: {size}, 오류: {e}")
                return []
            
            if trigger_price <= 0:
                self.logger.debug(f"유효하지 않은 트리거 가격 - trigger_price: {trigger_price}")
                return []
            
            hashes = []
            
            # 가격 기반 해시 (핵심 중복 제거)
            try:
                # 기본 가격 해시 (크기와 무관하게 항상 생성)
                price_only_hash = f"{contract}_price_{trigger_price:.2f}"
                hashes.append(price_only_hash)
                
                precise_price_hash = f"{contract}_price_{trigger_price:.8f}"
                hashes.append(precise_price_hash)
                
                # 반올림된 가격 해시
                rounded_price_1 = round(trigger_price, 1)
                rounded_price_hash_1 = f"{contract}_price_{rounded_price_1:.1f}"
                hashes.append(rounded_price_hash_1)
                
                rounded_price_0 = round(trigger_price, 0)
                rounded_price_hash_0 = f"{contract}_price_{rounded_price_0:.0f}"
                hashes.append(rounded_price_hash_0)
                
            except Exception as e:
                self.logger.debug(f"가격 기반 해시 생성 실패: {e}")
            
            # 크기 포함 해시 (크기가 0보다 클 때만)
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
                    self.logger.debug(f"크기 포함 해시 생성 실패: {e}")
            else:
                self.logger.debug(f"크기가 0이므로 가격 기반 해시만 생성 - trigger_price: {trigger_price}")
            
            # TP/SL 포함 해시
            try:
                if order_details.get('has_tp_sl'):
                    tp_price = order_details.get('tp_price', 0) or 0
                    sl_price = order_details.get('sl_price', 0) or 0
                    
                    # TP/SL 가격 기반 해시 (크기 무관)
                    tp_sl_price_hash = f"{contract}_price_{trigger_price:.2f}_withTPSL"
                    hashes.append(tp_sl_price_hash)
                    
                    # TP/SL + 크기 해시 (크기가 0보다 클 때만)
                    if abs_size > 0:
                        tp_sl_hash = f"{contract}_{trigger_price:.2f}_{abs_size}_tp{tp_price:.2f}_sl{sl_price:.2f}"
                        hashes.append(tp_sl_hash)
                        
            except Exception as e:
                self.logger.debug(f"TP/SL 해시 생성 실패: {e}")
            
            # 관대한 가격 범위 해시 (±500달러)
            try:
                # 500달러 범위
                price_range_500 = round(trigger_price / 500) * 500
                range_hash_500 = f"{contract}_range500_{price_range_500:.0f}"
                hashes.append(range_hash_500)
                
                # 100달러 범위
                price_range_100 = round(trigger_price / 100) * 100
                range_hash_100 = f"{contract}_range100_{price_range_100:.0f}"
                hashes.append(range_hash_100)
                
                # 매우 넓은 가격 차이 고려 (±200달러)
                for offset in [-200, -100, -50, -20, 0, 20, 50, 100, 200]:
                    adjusted_price = trigger_price + offset
                    if adjusted_price > 0:
                        offset_hash = f"{contract}_offset_{adjusted_price:.0f}"
                        hashes.append(offset_hash)
                        
            except Exception as e:
                self.logger.debug(f"가격 범위 해시 생성 실패: {e}")
            
            # 중복 제거
            unique_hashes = list(set(hashes))
            
            if unique_hashes:
                self.logger.debug(f"{len(unique_hashes)}개 주문 해시 생성: trigger=${trigger_price:.2f}, size={size}")
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
                    # 크기가 0이어도 폴백 해시 생성
                    basic_hash = f"{contract}_{trigger_price:.2f}_fallback"
                    price_hash = f"{contract}_price_{trigger_price:.2f}"
                    return [basic_hash, price_hash]
            except Exception as fallback_error:
                self.logger.error(f"폴백 해시 생성도 실패: {fallback_error}")
            
            return []
    
    def generate_order_hash(self, trigger_price: float, size: int, contract: str = None) -> str:
        try:
            contract = contract or self.GATE_CONTRACT
            
            if trigger_price is None or trigger_price <= 0:
                return f"{contract}_unknown_unknown"
            
            trigger_price = float(trigger_price)
            size = int(size) if size is not None else 0
            
            # 크기가 0이어도 가격 기반 해시 생성
            if size == 0:
                return f"{contract}_price_{trigger_price:.2f}"
            else:
                return f"{contract}_{trigger_price:.2f}_{abs(size)}"
            
        except (ValueError, TypeError) as e:
            self.logger.debug(f"해시 생성 변환 실패: {e}")
            return f"{contract or self.GATE_CONTRACT}_error_error"
    
    def generate_price_based_hash(self, trigger_price: float, contract: str = None) -> str:
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
        try:
            if price is None or price <= 0:
                return price or 0
            
            # 항상 처리 진행, 조정은 선택적
            if (bitget_current_price > 0 and gate_current_price > 0):
                price_diff_abs = abs(bitget_current_price - gate_current_price)
                
                # 비정상적인 가격 차이에 대한 매우 높은 임계값 (10000달러 이상)
                if price_diff_abs > self.ABNORMAL_PRICE_DIFF_THRESHOLD:
                    self.logger.info(f"극도로 큰 시세 차이지만 처리 계속 (${price_diff_abs:.2f})")
                    return price  # 조정 없이 원본 가격 사용
                
                # 시세 차이와 무관하게 항상 처리하되, 선택적으로 조정 적용
                if (self.PRICE_ADJUSTMENT_ENABLED and 
                    price_diff_abs > self.PRICE_SYNC_THRESHOLD and
                    price_diff_abs <= self.ABNORMAL_PRICE_DIFF_THRESHOLD):
                    
                    # 가격 비율 계산
                    price_ratio = gate_current_price / bitget_current_price
                    adjusted_price = price * price_ratio
                    
                    # 조정 폭 검증 (매우 관대하게: 최대 50% 조정 허용)
                    adjustment_percent = abs(adjusted_price - price) / price * 100
                    
                    if adjustment_percent <= 50.0:  # 10% → 50%로 훨씬 관대하게
                        self.logger.info(f"가격 조정됨: ${price:.2f} → ${adjusted_price:.2f} (차이: ${price_diff_abs:.2f})")
                        return adjusted_price
                    else:
                        self.logger.info(f"큰 조정이지만 원본 가격으로 계속 ({adjustment_percent:.1f}%)")
                        return price  # 조정 없이 처리 계속
                else:
                    return price
            elif bitget_current_price <= 0 or gate_current_price <= 0:
                self.logger.debug("가격 조회 실패하지만 처리 계속")
                return price
            
            return price
            
        except Exception as e:
            self.logger.error(f"가격 조정 실패하지만 처리 계속: {e}")
            return price or 0
    
    async def validate_trigger_price(self, trigger_price: float, side: str, current_price: float = 0) -> Tuple[bool, str]:
        try:
            if trigger_price is None or trigger_price <= 0:
                return False, "트리거 가격이 None이거나 0 이하"
            
            if current_price <= 0:
                self.logger.info("현재가 조회 실패하지만 모든 트리거 가격 허용")
                return True, "현재가 조회 실패하지만 허용됨"
            
            # 모든 가격 차이 허용 - 처리 블록 없음
            price_diff_percent = abs(trigger_price - current_price) / current_price * 100
            price_diff_abs = abs(trigger_price - current_price)
            
            # 비정상적인 가격 차이 감지를 위한 극도로 높은 임계값 (10000달러)
            if price_diff_abs > self.ABNORMAL_PRICE_DIFF_THRESHOLD:
                self.logger.info(f"매우 큰 가격 차이지만 처리 허용: ${price_diff_abs:.2f}")
                return True, f"큰 가격 차이지만 허용됨 (${price_diff_abs:.2f})"
            
            # 모든 가격 무조건 허용
            return True, f"모든 트리거 가격 허용 (차이: {price_diff_percent:.4f}%)"
            
        except Exception as e:
            self.logger.error(f"트리거 가격 검증 실패하지만 허용: {e}")
            return True, f"검증 오류하지만 모든 가격 허용: {str(e)[:100]}"
    
    async def calculate_gate_order_size_for_close_order_enhanced(self, current_gate_position_size: int, 
                                                               close_order_details: Dict, 
                                                               bitget_order: Dict) -> Tuple[int, bool]:
        try:
            position_side = close_order_details['position_side']  # 'long' 또는 'short'
            order_direction = close_order_details['order_direction']  # 'buy' 또는 'sell'
            
            self.logger.info(f"강화된 클로즈 주문 크기 계산: current_gate_position={current_gate_position_size}, position={position_side}, direction={order_direction}")
            
            # 현재 포지션이 0이어도 클로즈 주문 생성 허용
            if current_gate_position_size == 0:
                self.logger.warning(f"현재 포지션이 0이지만 클로즈 주문 강제 생성")
                
                # 비트겟 주문 기준으로 기본 크기 계산
                bitget_size = float(bitget_order.get('size', 1))
                if bitget_size <= 0:
                    bitget_size = 1
                
                # 최소 크기로 클로즈 주문 생성
                base_gate_size = max(int(bitget_size * 10000), 1)  # BTC를 계약으로 변환
                
                # 포지션 사이드에 따라 클로즈 방향 결정
                if position_side == 'long':
                    final_gate_size = -base_gate_size  # 롱 포지션 클로즈 → 매도
                else:
                    final_gate_size = base_gate_size   # 숏 포지션 클로즈 → 매수
                
                self.logger.info(f"포지션 없이 강제 클로즈 주문 생성: {final_gate_size}")
                return final_gate_size, True
            
            # 현재 포지션 방향 확인
            current_position_side = 'long' if current_gate_position_size > 0 else 'short'
            current_position_abs_size = abs(current_gate_position_size)
            
            # 포지션 방향 일치성 확인
            if current_position_side != position_side:
                self.logger.warning(f"포지션 방향 불일치: current={current_position_side}, expected={position_side}")
                # 강화됨: 현재 포지션에 맞춰 조정
                actual_position_side = current_position_side
            else:
                actual_position_side = position_side
            
            # 비트겟 클로즈 주문에서 부분 청산 비율 계산
            bitget_size = float(bitget_order.get('size', 0))
            
            # 부분 청산 비율 계산을 위해 비트겟 현재 포지션 조회
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
                        self.logger.info(f"부분 청산 비율: {close_ratio*100:.1f}% (비트겟 포지션: {bitget_position_size}, 청산 크기: {bitget_size})")
                    else:
                        close_ratio = 1.0
                        self.logger.warning(f"비트겟 포지션 크기가 0, 전체 청산으로 처리")
                else:
                    # 비트겟 포지션을 찾을 수 없음, 전체 청산 사용
                    close_ratio = 1.0
                    self.logger.warning(f"해당하는 비트겟 포지션을 찾을 수 없음, 전체 청산으로 처리")
                    
            except Exception as e:
                # 비트겟 포지션 조회 실패, 전체 청산 사용
                close_ratio = 1.0
                self.logger.error(f"비트겟 포지션 조회 실패, 전체 청산으로 처리: {e}")
            
            # 게이트 클로즈 주문 크기 계산
            gate_close_size = int(current_position_abs_size * close_ratio)
            
            # 최소 1개는 청산
            if gate_close_size == 0:
                gate_close_size = 1
            
            # 현재 포지션을 초과할 수 없음
            if gate_close_size > current_position_abs_size:
                gate_close_size = current_position_abs_size
            
            # 클로즈 주문 방향 결정 (포지션과 반대)
            if actual_position_side == 'long':
                # 롱 포지션 클로즈 → 매도 (음수)
                final_gate_size = -gate_close_size
                self.logger.info(f"롱 포지션 클로즈: {gate_close_size} → 매도 주문 (음수: {final_gate_size})")
            else:
                # 숏 포지션 클로즈 → 매수 (양수)
                final_gate_size = gate_close_size
                self.logger.info(f"숏 포지션 클로즈: {gate_close_size} → 매수 주문 (양수: {final_gate_size})")
            
            self.logger.info(f"강화된 클로즈 주문 크기 계산 완료: 현재 포지션={current_gate_position_size} → 클로즈 크기={final_gate_size} (비율: {close_ratio*100:.1f}%)")
            
            return final_gate_size, True  # reduce_only=True
            
        except Exception as e:
            self.logger.error(f"강화된 클로즈 주문 크기 계산 실패: {e}")
            # 실패 시에도 기본 크기로 클로즈 주문 생성
            bitget_size = float(bitget_order.get('size', 1))
            base_size = max(int(bitget_size * 10000), 1)
            
            position_side = close_order_details.get('position_side', 'long')
            if position_side == 'long':
                return -base_size, True  # 롱 포지션 클로즈 → 매도
            else:
                return base_size, True   # 숏 포지션 클로즈 → 매수
    
    async def calculate_gate_order_size_for_close_order(self, current_gate_position_size: int, 
                                                       close_order_details: Dict, 
                                                       bitget_order: Dict) -> Tuple[int, bool]:
        return await self.calculate_gate_order_size_for_close_order_enhanced(
            current_gate_position_size, close_order_details, bitget_order
        )
    
    async def calculate_gate_order_size_fixed(self, side: str, base_size: int, is_close_order: bool = False) -> Tuple[int, bool]:
        try:
            side_lower = side.lower()
            reduce_only = False
            
            self.logger.info(f"주문 타입 분석: side='{side}', is_close_order={is_close_order}")
            
            # 클로즈 주문 처리 - 완전히 개정된 로직
            if is_close_order or 'close' in side_lower:
                reduce_only = True
                
                # 클로즈 주문: 포지션을 청산하는 방향으로 주문
                if 'close_long' in side_lower or side_lower == 'close long':
                    # 롱 포지션 클로즈 → 매도 주문 (음수)
                    gate_size = -abs(base_size)
                    self.logger.info(f"롱 클로즈: 롱 포지션 클로즈 → 게이트 매도 주문 (음수: {gate_size})")
                    
                elif 'close_short' in side_lower or side_lower == 'close short':
                    # 숏 포지션 클로즈 → 매수 주문 (양수)
                    gate_size = abs(base_size)
                    self.logger.info(f"숏 클로즈: 숏 포지션 클로즈 → 게이트 매수 주문 (양수: {gate_size})")
                    
                elif 'sell' in side_lower and 'buy' not in side_lower:
                    # 매도로 클로즈 → 롱 포지션 청산
                    gate_size = -abs(base_size)
                    self.logger.info(f"매도 클로즈: 롱 포지션 클로즈 → 게이트 매도 주문 (음수: {gate_size})")
                    
                elif 'buy' in side_lower and 'sell' not in side_lower:
                    # 매수로 클로즈 → 숏 포지션 청산
                    gate_size = abs(base_size)
                    self.logger.info(f"매수 클로즈: 숏 포지션 클로즈 → 게이트 매수 주문 (양수: {gate_size})")
                    
                else:
                    # 기타 클로즈 주문 - 기본값으로 매도
                    gate_size = -abs(base_size)
                    self.logger.warning(f"알 수 없는 클로즈 주문 타입: {side}, 매도로 처리 (음수: {gate_size})")
                        
            # 오픈 주문 처리
            else:
                reduce_only = False
                
                if 'open_long' in side_lower or ('buy' in side_lower and 'sell' not in side_lower):
                    # 롱 포지션 생성 → 매수 주문 (양수)
                    gate_size = abs(base_size)
                    self.logger.info(f"롱 오픈: 새로운 롱 포지션 생성 → 게이트 매수 주문 (양수: {gate_size})")
                    
                elif 'open_short' in side_lower or 'sell' in side_lower:
                    # 숏 포지션 생성 → 매도 주문 (음수)
                    gate_size = -abs(base_size)
                    self.logger.info(f"숏 오픈: 새로운 숏 포지션 생성 → 게이트 매도 주문 (음수: {gate_size})")
                    
                else:
                    # 기타 오픈 주문 - 원본 크기 유지
                    gate_size = base_size
                    self.logger.warning(f"알 수 없는 오픈 주문 타입: {side}, 원본 크기 유지: {gate_size}")
            
            self.logger.info(f"최종 변환 결과: {side} → 게이트 크기={gate_size}, reduce_only={reduce_only}")
            return gate_size, reduce_only
            
        except Exception as e:
            self.logger.error(f"게이트 주문 크기 계산 실패: {e}")
            return base_size, False
    
    async def calculate_gate_order_size(self, side: str, base_size: int) -> int:
        try:
            is_close_order = 'close' in side.lower()
            gate_size, _ = await self.calculate_gate_order_size_fixed(side, base_size, is_close_order)
            return gate_size
        except Exception as e:
            self.logger.error(f"게이트 주문 크기 계산 래퍼 실패: {e}")
            return base_size
    
    async def determine_gate_trigger_type(self, trigger_price: float, current_price: float = 0) -> str:
        try:
            if current_price <= 0 or trigger_price is None:
                return "ge"
            
            if trigger_price > current_price:
                return "ge"  # 이상
            else:
                return "le"  # 이하
                
        except Exception as e:
            self.logger.error(f"게이트 트리거 타입 결정 실패: {e}")
            return "ge"
    
    async def get_current_gate_position_size(self, gate_mirror_client, position_side: str = None) -> Tuple[int, str]:
        try:
            gate_positions = await gate_mirror_client.get_positions(self.GATE_CONTRACT)
            
            if not gate_positions:
                self.logger.info("게이트 포지션 없음")
                return 0, 'none'
            
            position = gate_positions[0]
            current_size = int(position.get('size', 0))
            
            if current_size == 0:
                self.logger.info("게이트 포지션 크기 0")
                return 0, 'none'
            
            # 포지션 방향 확인
            current_side = 'long' if current_size > 0 else 'short'
            
            # 요청된 방향이 지정된 경우 검증
            if position_side and current_side != position_side:
                self.logger.warning(f"요청된 포지션 방향 ({position_side})이 현재 포지션 방향 ({current_side})과 다름")
                return current_size, current_side  # 실제 정보 반환
            
            self.logger.info(f"현재 게이트 포지션: {current_size} ({current_side})")
            return current_size, current_side
            
        except Exception as e:
            self.logger.error(f"현재 게이트 포지션 크기 조회 실패: {e}")
            return 0, 'error'
    
    async def validate_close_order_against_position(self, close_order_details: Dict, 
                                                   current_gate_position_size: int) -> Tuple[bool, str]:
        try:
            # 포지션이 없어도 클로즈 주문 허용
            if current_gate_position_size == 0:
                return True, "현재 포지션 없지만 클로즈 주문 강제 허용 (포지션이 생성될 수 있음)"
            
            # 현재 포지션 방향
            current_position_side = 'long' if current_gate_position_size > 0 else 'short'
            
            # 클로즈 주문에서 예상하는 포지션 방향
            expected_position_side = close_order_details['position_side']
            
            if current_position_side != expected_position_side:
                return True, f"포지션 방향 불일치지만 현재 포지션에 맞춰 조정 허용 ({current_position_side})"
            
            return True, f"클로즈 주문 유효: {current_position_side} 포지션 → {close_order_details['order_direction']} 주문"
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 검증 실패하지만 허용: {e}")
            return True, f"검증 오류하지만 클로즈 주문 허용: {str(e)}"
    
    def generate_position_id(self, pos: Dict) -> str:
        symbol = pos.get('symbol', self.SYMBOL)
        side = pos.get('holdSide', '')
        entry_price = pos.get('openPriceAvg', '')
        return f"{symbol}_{side}_{entry_price}"
    
    async def create_position_info(self, bitget_pos: Dict) -> PositionInfo:
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
        try:
            if bitget_price <= 0 or gate_price <= 0:
                return {
                    'price_diff_abs': 0, 'price_diff_percent': 0, 'exceeds_threshold': False,
                    'status': 'invalid_prices', 'is_abnormal': False, 'should_process': True  # 항상 처리 진행
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
                'price_diff_abs': price_diff_abs, 'price_diff_percent': price_diff_percent,
                'exceeds_threshold': exceeds_threshold, 'threshold': self.PRICE_SYNC_THRESHOLD,
                'abnormal_threshold': self.ABNORMAL_PRICE_DIFF_THRESHOLD, 'is_abnormal': is_abnormal,
                'status': status, 'bitget_price': bitget_price, 'gate_price': gate_price,
                'should_process': True  # 항상 처리 진행
            }
            
        except Exception as e:
            self.logger.error(f"시세 차이 정보 계산 실패: {e}")
            return {
                'price_diff_abs': 0, 'price_diff_percent': 0, 'exceeds_threshold': False,
                'status': 'error', 'is_abnormal': False, 'should_process': True  # 오류 시에도 처리 진행
            }
    
    async def should_delay_processing(self, bitget_price: float, gate_price: float) -> Tuple[bool, str]:
        try:
            price_info = await self.get_price_difference_info(bitget_price, gate_price)
            
            # 항상 처리 진행 - 지연 없음
            return False, "시세 차이와 무관하게 모든 주문 즉시 처리"
            
        except Exception as e:
            self.logger.error(f"처리 지연 판단 실패하지만 계속 진행: {e}")
            return False, "판단 오류하지만 계속 진행"
