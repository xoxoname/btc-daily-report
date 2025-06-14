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
    """🔥🔥🔥 미러 트레이딩 유틸리티 클래스 - 복제 비율 조정 기능 강화"""
    
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
        
        # 🔥🔥🔥 레버리지 설정 강화
        self.DEFAULT_LEVERAGE = 30  # 기본 레버리지 30배
        self.MAX_LEVERAGE = 100
        self.MIN_LEVERAGE = 1
        self.leverage_cache = {}  # 레버리지 캐시
        
        # 🔥🔥🔥 복제 비율 조정 설정 - 강화된 버전
        self.DEFAULT_RATIO_MULTIPLIER = 1.0  # 기본 복제 비율 1배
        self.MAX_RATIO_MULTIPLIER = 10.0     # 최대 복제 비율 10배
        self.MIN_RATIO_MULTIPLIER = 0.1      # 최소 복제 비율 0.1배
        
        # 🔥🔥🔥 복제 비율 설명 템플릿
        self.RATIO_DESCRIPTIONS = {
            0.1: "원본의 10% 크기로 대폭 축소",
            0.2: "원본의 20% 크기로 축소",
            0.3: "원본의 30% 크기로 축소",
            0.4: "원본의 40% 크기로 축소",
            0.5: "원본의 절반 크기로 축소",
            0.6: "원본의 60% 크기로 축소",
            0.7: "원본의 70% 크기로 축소",
            0.8: "원본의 80% 크기로 축소",
            0.9: "원본의 90% 크기로 축소",
            1.0: "원본 비율 그대로 복제",
            1.1: "원본의 1.1배로 10% 확대",
            1.2: "원본의 1.2배로 20% 확대",
            1.3: "원본의 1.3배로 30% 확대",
            1.4: "원본의 1.4배로 40% 확대",
            1.5: "원본의 1.5배로 50% 확대",
            2.0: "원본의 2배로 확대",
            2.5: "원본의 2.5배로 확대",
            3.0: "원본의 3배로 확대",
            5.0: "원본의 5배로 확대",
            10.0: "원본의 10배로 최대 확대"
        }
        
        # 🔥🔥🔥 트리거 가격 검증 완전히 제거 - 모든 가격 허용
        self.TRIGGER_PRICE_MIN_DIFF_PERCENT = 0.0
        self.ALLOW_VERY_CLOSE_PRICES = True
        
        # 🔥🔥🔥 시세 차이 관리 매우 관대하게 - 처리 차단 없음
        self.PRICE_SYNC_THRESHOLD = 1000.0  # 100달러 → 1000달러로 대폭 상향
        self.PRICE_ADJUSTMENT_ENABLED = True
        
        # 🔥🔥🔥 비정상적인 시세 차이 감지 임계값도 매우 관대하게
        self.ABNORMAL_PRICE_DIFF_THRESHOLD = 10000.0  # 2000달러 → 10000달러로 대폭 상향
        
        # 🔥🔥🔥 클로즈 주문 판단 강화 - 수정된 키워드
        self.CLOSE_ORDER_KEYWORDS = [
            'close', 'close_long', 'close_short', 'close long', 'close short',
            'exit', 'exit_long', 'exit_short', 'exit long', 'exit short',
            'reduce'  # TP/SL 관련 키워드는 제거 - 오분류 방지
        ]
        
        # 🔥🔥🔥 TP/SL 전용 주문 타입 (클로즈 주문으로 분류)
        self.TP_SL_ONLY_ORDER_TYPES = [
            'profit_loss',  # 비트겟의 TP/SL 전용 주문 타입
            'stop_loss_only',
            'take_profit_only'
        ]
        
        self.CLOSE_ORDER_STRICT_MODE = False  # 더 관대한 클로즈 주문 감지
        
        self.logger.info("🔥🔥🔥 미러 트레이딩 유틸리티 초기화 완료 - 복제 비율 조정 기능 강화")
    
    async def calculate_dynamic_margin_ratio_with_multiplier(self, size: float, trigger_price: float, 
                                                           bitget_order: Dict, ratio_multiplier: float = 1.0) -> Dict:
        """🔥🔥🔥 복제 비율이 적용된 실제 달러 마진 비율 동적 계산 - 강화된 버전"""
        try:
            # 유효성 검증
            if size is None or trigger_price is None:
                return {
                    'success': False,
                    'error': 'size 또는 trigger_price가 None입니다.'
                }
            
            # 🔥🔥🔥 복제 비율 유효성 검증 및 정규화
            validated_ratio = self.validate_ratio_multiplier(ratio_multiplier)
            if validated_ratio != ratio_multiplier:
                self.logger.warning(f"복제 비율 조정됨: {ratio_multiplier} → {validated_ratio}")
                ratio_multiplier = validated_ratio
            
            self.logger.info(f"💰 복제 비율 적용 마진 계산: 기본 크기={size}, 복제 비율={ratio_multiplier}x")
            
            # 🔥🔥🔥 강화된 레버리지 추출
            bitget_account = await self.bitget.get_account_info()
            
            # 강화된 레버리지 추출 사용
            extracted_leverage = await self.extract_bitget_leverage_enhanced(
                order_data=bitget_order,
                position_data=None,  # 포지션 데이터는 별도 조회
                account_data=bitget_account
            )
            
            self.logger.info(f"💪 추출된 레버리지: {extracted_leverage}x")
            
            # 비트겟 계정 정보에서 총 자산 추출
            bitget_total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            if bitget_total_equity <= 0:
                return {
                    'success': False,
                    'error': '비트겟 총 자산이 0이거나 조회 실패'
                }
            
            # 비트겟에서 이 주문이 체결될 때 사용할 실제 마진 계산
            bitget_notional_value = size * trigger_price
            bitget_required_margin = bitget_notional_value / extracted_leverage
            
            # 비트겟 총 자산 대비 실제 마진 투입 비율 계산
            base_margin_ratio = bitget_required_margin / bitget_total_equity
            
            # 🔥🔥🔥 복제 비율 적용 - 마진 비율에 multiplier 적용
            adjusted_margin_ratio = base_margin_ratio * ratio_multiplier
            
            # 🔥🔥🔥 마진 비율 유효성 검증 및 안전 조치 (복제 비율 적용 후)
            if adjusted_margin_ratio <= 0:
                return {
                    'success': False,
                    'error': f'복제 비율 적용 후 마진 비율이 0 이하: {adjusted_margin_ratio:.4f}'
                }
            elif adjusted_margin_ratio > 1:
                # 1을 초과하는 경우 가용 자금의 95%로 제한
                original_ratio = adjusted_margin_ratio
                adjusted_margin_ratio = 0.95
                self.logger.warning(f"복제 비율 적용 후 마진 비율이 100% 초과하여 95%로 제한: {original_ratio:.4f} → {adjusted_margin_ratio:.4f}")
                self.logger.warning(f"요청된 복제 비율 {ratio_multiplier}x가 너무 높습니다. 안전상 95%로 제한합니다.")
            
            # 🔥🔥🔥 조정된 마진으로 필요한 수치들 재계산
            adjusted_required_margin = bitget_total_equity * adjusted_margin_ratio
            adjusted_notional_value = adjusted_required_margin * extracted_leverage
            
            # 🔥🔥🔥 복제 비율 효과 분석
            ratio_effect = self.analyze_ratio_multiplier_effect(ratio_multiplier, base_margin_ratio, adjusted_margin_ratio)
            
            result = {
                'success': True,
                'margin_ratio': adjusted_margin_ratio,  # 복제 비율이 적용된 마진 비율
                'leverage': extracted_leverage,
                'required_margin': adjusted_required_margin,  # 복제 비율이 적용된 마진
                'total_equity': bitget_total_equity,
                'notional_value': adjusted_notional_value,  # 복제 비율이 적용된 거래 규모
                'ratio_multiplier': ratio_multiplier,  # 적용된 복제 비율
                'base_margin_ratio': base_margin_ratio,  # 원본 마진 비율 (참고용)
                'base_required_margin': bitget_required_margin,  # 원본 마진 (참고용)
                'base_notional_value': bitget_notional_value,  # 원본 거래 규모 (참고용)
                'ratio_effect': ratio_effect,  # 복제 비율 효과 분석
                'ratio_description': self.get_ratio_multiplier_description(ratio_multiplier)  # 복제 비율 설명
            }
            
            self.logger.info(f"💰 복제 비율 적용 마진 계산 성공:")
            self.logger.info(f"   - 원본 마진 비율: {base_margin_ratio*100:.3f}%")
            self.logger.info(f"   - 복제 비율: {ratio_multiplier}x ({ratio_effect['description']})")
            self.logger.info(f"   - 최종 마진 비율: {adjusted_margin_ratio*100:.3f}%")
            self.logger.info(f"   - 레버리지: {extracted_leverage}x")
            self.logger.info(f"   - 효과: {ratio_effect['impact']}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"복제 비율 적용 마진 비율 계산 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def calculate_dynamic_margin_ratio(self, size: float, trigger_price: float, bitget_order: Dict) -> Dict:
        """🔥🔥🔥 기존 메서드 호환성 유지 - 복제 비율 1.0 적용"""
        return await self.calculate_dynamic_margin_ratio_with_multiplier(size, trigger_price, bitget_order, 1.0)
    
    def validate_ratio_multiplier(self, ratio_multiplier: float) -> float:
        """🔥🔥🔥 복제 비율 유효성 검증 - 강화된 버전"""
        try:
            if ratio_multiplier is None:
                self.logger.warning("복제 비율이 None, 기본값 사용: 1.0")
                return self.DEFAULT_RATIO_MULTIPLIER
            
            ratio_multiplier = float(ratio_multiplier)
            
            if ratio_multiplier < self.MIN_RATIO_MULTIPLIER:
                self.logger.warning(f"복제 비율이 최소값보다 작음 ({ratio_multiplier}), 최소값 사용: {self.MIN_RATIO_MULTIPLIER}")
                return self.MIN_RATIO_MULTIPLIER
            
            if ratio_multiplier > self.MAX_RATIO_MULTIPLIER:
                self.logger.warning(f"복제 비율이 최대값보다 큼 ({ratio_multiplier}), 최대값 사용: {self.MAX_RATIO_MULTIPLIER}")
                return self.MAX_RATIO_MULTIPLIER
            
            # 🔥🔥🔥 권장 범위 확인 (경고만 출력)
            if ratio_multiplier > 5.0:
                self.logger.warning(f"복제 비율이 매우 높습니다 ({ratio_multiplier}x). 리스크 관리에 주의하세요.")
            elif ratio_multiplier < 0.5:
                self.logger.info(f"복제 비율이 낮습니다 ({ratio_multiplier}x). 보수적인 설정입니다.")
            
            return ratio_multiplier
            
        except (ValueError, TypeError):
            self.logger.error(f"복제 비율 변환 실패 ({ratio_multiplier}), 기본값 사용: {self.DEFAULT_RATIO_MULTIPLIER}")
            return self.DEFAULT_RATIO_MULTIPLIER
    
    def get_ratio_multiplier_description(self, ratio_multiplier: float) -> str:
        """🔥🔥🔥 복제 비율 설명 텍스트 생성 - 상세한 버전"""
        try:
            # 정확한 매칭 확인
            if ratio_multiplier in self.RATIO_DESCRIPTIONS:
                return self.RATIO_DESCRIPTIONS[ratio_multiplier]
            
            # 가장 가까운 값 찾기
            closest_ratio = min(self.RATIO_DESCRIPTIONS.keys(), 
                               key=lambda x: abs(x - ratio_multiplier))
            
            if abs(closest_ratio - ratio_multiplier) < 0.05:  # 0.05 이내면 동일하게 처리
                return self.RATIO_DESCRIPTIONS[closest_ratio]
            
            # 사용자 정의 비율 설명 생성
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
        """🔥🔥🔥 복제 비율 효과 분석"""
        try:
            effect_analysis = {
                'multiplier': ratio_multiplier,
                'base_percentage': base_ratio * 100,
                'adjusted_percentage': adjusted_ratio * 100,
                'absolute_increase': (adjusted_ratio - base_ratio) * 100,
                'relative_increase_percent': ((adjusted_ratio / base_ratio) - 1) * 100 if base_ratio > 0 else 0,
                'description': self.get_ratio_multiplier_description(ratio_multiplier),
                'impact': '',
                'risk_level': '',
                'recommendation': ''
            }
            
            # 🔥🔥🔥 영향도 분석
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
                'multiplier': ratio_multiplier,
                'description': "분석 실패",
                'impact': "알 수 없음",
                'risk_level': "불명",
                'recommendation': "신중한 검토 필요"
            }
    
    async def extract_bitget_leverage_enhanced(self, order_data: Dict = None, position_data: Dict = None, account_data: Dict = None) -> int:
        """🔥🔥🔥 비트겟 레버리지 추출 - 다중 소스 강화"""
        try:
            extracted_leverage = self.DEFAULT_LEVERAGE
            source = "기본값"
            
            # 🔥 1순위: 주문 데이터에서 레버리지 추출
            if order_data:
                for leverage_field in ['leverage', 'marginLeverage', 'leverageRatio']:
                    order_leverage = order_data.get(leverage_field)
                    if order_leverage:
                        try:
                            lev_value = int(float(order_leverage))
                            if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                extracted_leverage = lev_value
                                source = f"주문({leverage_field})"
                                self.logger.info(f"✅ 주문에서 레버리지 추출: {extracted_leverage}x ({source})")
                                return extracted_leverage
                        except (ValueError, TypeError):
                            continue
            
            # 🔥 2순위: 포지션 데이터에서 레버리지 추출
            if position_data:
                for leverage_field in ['leverage', 'marginLeverage', 'leverageRatio']:
                    pos_leverage = position_data.get(leverage_field)
                    if pos_leverage:
                        try:
                            lev_value = int(float(pos_leverage))
                            if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                extracted_leverage = lev_value
                                source = f"포지션({leverage_field})"
                                self.logger.info(f"✅ 포지션에서 레버리지 추출: {extracted_leverage}x ({source})")
                                return extracted_leverage
                        except (ValueError, TypeError):
                            continue
            
            # 🔥 3순위: 계정 데이터에서 레버리지 추출
            if account_data:
                for leverage_field in ['crossMarginLeverage', 'leverage', 'defaultLeverage', 'marginLeverage']:
                    account_leverage = account_data.get(leverage_field)
                    if account_leverage:
                        try:
                            lev_value = int(float(account_leverage))
                            if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                extracted_leverage = lev_value
                                source = f"계정({leverage_field})"
                                self.logger.info(f"✅ 계정에서 레버리지 추출: {extracted_leverage}x ({source})")
                                return extracted_leverage
                        except (ValueError, TypeError):
                            continue
            
            # 🔥 4순위: 실시간 비트겟 계정 조회
            try:
                fresh_account = await self.bitget.get_account_info()
                for leverage_field in ['crossMarginLeverage', 'leverage', 'defaultLeverage', 'marginLeverage']:
                    account_leverage = fresh_account.get(leverage_field)
                    if account_leverage:
                        try:
                            lev_value = int(float(account_leverage))
                            if self.MIN_LEVERAGE <= lev_value <= self.MAX_LEVERAGE:
                                extracted_leverage = lev_value
                                source = f"실시간계정({leverage_field})"
                                self.logger.info(f"✅ 실시간 계정에서 레버리지 추출: {extracted_leverage}x ({source})")
                                
                                # 캐시 저장
                                self.leverage_cache['bitget_default'] = {
                                    'leverage': extracted_leverage,
                                    'timestamp': datetime.now(),
                                    'source': source
                                }
                                return extracted_leverage
                        except (ValueError, TypeError):
                            continue
            except Exception as e:
                self.logger.warning(f"실시간 계정 조회 실패: {e}")
            
            # 🔥 5순위: 실시간 비트겟 포지션 조회
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
                                    source = "실시간포지션"
                                    self.logger.info(f"✅ 실시간 포지션에서 레버리지 추출: {extracted_leverage}x ({source})")
                                    return extracted_leverage
                            except (ValueError, TypeError):
                                continue
            except Exception as e:
                self.logger.warning(f"실시간 포지션 조회 실패: {e}")
            
            # 🔥 6순위: 캐시에서 가져오기
            if 'bitget_default' in self.leverage_cache:
                cache_data = self.leverage_cache['bitget_default']
                cache_time = cache_data['timestamp']
                if (datetime.now() - cache_time).total_seconds() < 3600:  # 1시간 캐시
                    extracted_leverage = cache_data['leverage']
                    source = f"캐시({cache_data['source']})"
                    self.logger.info(f"✅ 캐시에서 레버리지 사용: {extracted_leverage}x ({source})")
                    return extracted_leverage
            
            # 🔥 최종: 기본값 사용
            self.logger.warning(f"⚠️ 레버리지 추출 실패, 기본값 사용: {extracted_leverage}x")
            return extracted_leverage
            
        except Exception as e:
            self.logger.error(f"레버리지 추출 오류: {e}")
            return self.DEFAULT_LEVERAGE
    
    async def determine_close_order_details_enhanced(self, bitget_order: Dict) -> Dict:
        """🔥🔥🔥 강화된 클로즈 주문 세부 사항 정확하게 판단 - TP 설정된 오픈 주문 오분류 방지"""
        try:
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            reduce_only = bitget_order.get('reduceOnly', False)
            order_type = bitget_order.get('orderType', bitget_order.get('planType', '')).lower()
            
            self.logger.info(f"🔍 주문 분석 시작: side='{side}', reduce_only={reduce_only}, order_type='{order_type}'")
            
            # 🔥🔥🔥 강화된 클로즈 주문 판단 로직 - 우선순위 기반
            is_close_order = False
            detection_method = "none"
            
            # 🔥 1순위: reduce_only 플래그 확인 (가장 확실한 방법)
            if reduce_only is True or reduce_only == 'true' or str(reduce_only).lower() == 'true':
                is_close_order = True
                detection_method = "reduce_only_flag"
                self.logger.info(f"🔴 1순위: reduce_only=True로 클로즈 주문 확인")
            
            # 🔥 2순위: 명시적인 클로즈 키워드 확인
            elif not is_close_order:
                for keyword in self.CLOSE_ORDER_KEYWORDS:
                    if keyword in side:
                        is_close_order = True
                        detection_method = f"side_keyword_{keyword}"
                        self.logger.info(f"🔴 2순위: side 키워드로 클로즈 주문 확인: '{side}' 포함 '{keyword}'")
                        break
            
            # 🔥 3순위: TP/SL 전용 주문 타입 확인 (기존 포지션에 대한 TP/SL만 설정)
            elif not is_close_order:
                for tp_sl_type in self.TP_SL_ONLY_ORDER_TYPES:
                    if tp_sl_type in order_type:
                        is_close_order = True
                        detection_method = f"tp_sl_only_type_{tp_sl_type}"
                        self.logger.info(f"🎯 3순위: TP/SL 전용 타입으로 클로즈 주문 확인: '{order_type}' 포함 '{tp_sl_type}'")
                        break
            
            # 🔥🔥🔥 4순위: TP/SL이 설정된 것은 오픈 주문으로 유지 - 오분류 방지
            if not is_close_order:
                # TP/SL 가격 확인
                tp_price, sl_price = await self.extract_tp_sl_from_bitget_order(bitget_order)
                
                if tp_price or sl_price:
                    # 🔥🔥🔥 중요: TP/SL이 설정되어 있어도 오픈 주문으로 처리
                    is_close_order = False
                    detection_method = "tp_sl_set_but_open_order"
                    self.logger.info(f"🟢 4순위: TP/SL 설정된 오픈 주문으로 판단 (TP={tp_price}, SL={sl_price})")
                    self.logger.info(f"       → 새로운 포지션 생성 + TP/SL 함께 설정하는 주문")
            
            # 🔥 5순위: 특별한 클로즈 패턴 확인 (매우 보수적으로)
            if not is_close_order:
                special_patterns = ['exit', 'liquidat']  # 'stop', 'profit' 제거 - 오분류 방지
                for pattern in special_patterns:
                    if pattern in side or pattern in order_type:
                        is_close_order = True
                        detection_method = f"special_pattern_{pattern}"
                        self.logger.info(f"🔴 5순위: 특별 패턴으로 클로즈 주문 확인: '{pattern}'")
                        break
            
            # 🔥🔥🔥 최종 확인: 오픈 주문으로 기본 처리
            if not is_close_order:
                detection_method = "default_open_order"
                self.logger.info(f"🟢 최종: 오픈 주문으로 판단 (새로운 포지션 생성 주문)")
            
            self.logger.info(f"✅ 강화된 클로즈 주문 분석 결과: is_close_order={is_close_order}, method={detection_method}")
            
            # 🔥🔥🔥 주문 방향과 포지션 방향 정확한 매핑
            order_direction = None
            position_side = None
            
            if is_close_order:
                # 클로즈 주문인 경우
                if 'close_long' in side or 'exit_long' in side:
                    order_direction = 'sell'  # 롱 포지션을 종료하려면 매도
                    position_side = 'long'
                elif 'close_short' in side or 'exit_short' in side:
                    order_direction = 'buy'   # 숏 포지션을 종료하려면 매수
                    position_side = 'short'
                elif 'sell' in side and 'buy' not in side:
                    # 매도로 클로즈 = 롱 포지션 종료
                    order_direction = 'sell'
                    position_side = 'long'
                elif 'buy' in side and 'sell' not in side:
                    # 매수로 클로즈 = 숏 포지션 종료
                    order_direction = 'buy'
                    position_side = 'short'
                else:
                    # 🔥🔥🔥 기본값 설정 개선 - 현재 포지션 조회하여 판단
                    try:
                        bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                        active_positions = [pos for pos in bitget_positions if float(pos.get('total', 0)) > 0]
                        
                        if active_positions:
                            # 활성 포지션 기준으로 클로즈 방향 추정
                            main_position = active_positions[0]
                            current_side = main_position.get('holdSide', '').lower()
                            
                            if current_side == 'long':
                                order_direction = 'sell'
                                position_side = 'long'
                                self.logger.info(f"🔍 현재 롱 포지션 기준으로 클로즈 방향 추정: 매도")
                            elif current_side == 'short':
                                order_direction = 'buy'
                                position_side = 'short'
                                self.logger.info(f"🔍 현재 숏 포지션 기준으로 클로즈 방향 추정: 매수")
                            else:
                                # 기본값
                                order_direction = 'sell'
                                position_side = 'long'
                        else:
                            # 포지션이 없으면 기본값
                            order_direction = 'sell'
                            position_side = 'long'
                            self.logger.warning(f"⚠️ 활성 포지션이 없어 기본값 사용: 롱→매도")
                            
                    except Exception as e:
                        self.logger.error(f"포지션 조회 실패, 기본값 사용: {e}")
                        order_direction = 'sell'
                        position_side = 'long'
            else:
                # 🔥🔥🔥 오픈 주문인 경우 (TP/SL 설정된 오픈 주문 포함)
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
                'reduce_only': reduce_only,
                'order_type': order_type,
                'detection_method': detection_method  # 강화된 분석 방법 사용
            }
            
            self.logger.info(f"✅ 강화된 클로즈 주문 분석 결과: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"강화된 클로즈 주문 세부 사항 판단 실패: {e}")
            return {
                'is_close_order': False,
                'order_direction': 'buy',
                'position_side': 'long',
                'original_side': side if 'side' in locals() else '',
                'reduce_only': False,
                'order_type': order_type if 'order_type' in locals() else '',
                'detection_method': 'fallback'
            }
    
    async def determine_close_order_details(self, bitget_order: Dict) -> Dict:
        """기존 호환성을 위한 래퍼 메서드"""
        return await self.determine_close_order_details_enhanced(bitget_order)
    
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
            
            # 🔥🔥🔥 더 관대한 가격 범위 해시 (±500달러)
            try:
                # 500달러 단위로 반올림한 가격 해시
                price_range_500 = round(trigger_price / 500) * 500
                range_hash_500 = f"{contract}_range500_{price_range_500:.0f}"
                hashes.append(range_hash_500)
                
                # 100달러 단위로 반올림한 가격 해시
                price_range_100 = round(trigger_price / 100) * 100
                range_hash_100 = f"{contract}_range100_{price_range_100:.0f}"
                hashes.append(range_hash_100)
                
                # 🔥🔥🔥 매우 넓은 시세 차이를 고려한 가격 범위 해시 (±200달러)
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
        """🔥🔥🔥 게이트 기준으로 가격 조정 - 매우 관대한 버전 (처리 차단 없음)"""
        try:
            if price is None or price <= 0:
                return price or 0
            
            # 🔥🔥🔥 시세 차이가 있어도 항상 처리 진행, 조정만 선택적 적용
            if (bitget_current_price > 0 and gate_current_price > 0):
                price_diff_abs = abs(bitget_current_price - gate_current_price)
                
                # 매우 높은 임계값으로 비정상적인 시세 차이 판단 (10000달러 이상)
                if price_diff_abs > self.ABNORMAL_PRICE_DIFF_THRESHOLD:
                    self.logger.info(f"극도로 큰 시세 차이이지만 처리 계속 진행 (${price_diff_abs:.2f})")
                    return price  # 조정하지 않고 원본 가격 사용
                
                # 🔥🔥🔥 시세 차이가 있어도 항상 처리하되, 조정만 선택적 적용
                if (self.PRICE_ADJUSTMENT_ENABLED and 
                    price_diff_abs > self.PRICE_SYNC_THRESHOLD and
                    price_diff_abs <= self.ABNORMAL_PRICE_DIFF_THRESHOLD):
                    
                    # 가격 비율 계산
                    price_ratio = gate_current_price / bitget_current_price
                    adjusted_price = price * price_ratio
                    
                    # 조정 폭 검증 (매우 관대하게 50% 이하 조정 허용)
                    adjustment_percent = abs(adjusted_price - price) / price * 100
                    
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
    
    async def calculate_gate_order_size_for_close_order_enhanced(self, current_gate_position_size: int, 
                                                               close_order_details: Dict, 
                                                               bitget_order: Dict) -> Tuple[int, bool]:
        """🔥🔥🔥 강화된 클로즈 주문을 위한 게이트 주문 크기 계산 - 포지션이 없어도 처리"""
        try:
            position_side = close_order_details['position_side']  # 'long' 또는 'short'
            order_direction = close_order_details['order_direction']  # 'buy' 또는 'sell'
            
            self.logger.info(f"🎯 강화된 클로즈 주문 크기 계산: 현재 게이트 포지션={current_gate_position_size}, 포지션={position_side}, 방향={order_direction}")
            
            # 🔥🔥🔥 현재 포지션이 0이어도 클로즈 주문 생성 허용
            if current_gate_position_size == 0:
                self.logger.warning(f"⚠️ 현재 포지션이 0이지만 클로즈 주문 강제 생성")
                
                # 비트겟 주문 크기 기반으로 기본 크기 계산
                bitget_size = float(bitget_order.get('size', 1))
                if bitget_size <= 0:
                    bitget_size = 1
                
                # 최소 크기로 클로즈 주문 생성
                base_gate_size = max(int(bitget_size * 10000), 1)  # BTC를 계약 수로 변환
                
                # 포지션 방향에 따라 클로즈 방향 결정
                if position_side == 'long':
                    final_gate_size = -base_gate_size  # 롱 포지션 클로즈 → 매도
                else:
                    final_gate_size = base_gate_size   # 숏 포지션 클로즈 → 매수
                
                self.logger.info(f"🚀 포지션 없지만 클로즈 주문 강제 생성: {final_gate_size}")
                return final_gate_size, True
            
            # 현재 포지션 방향 확인
            current_position_side = 'long' if current_gate_position_size > 0 else 'short'
            current_position_abs_size = abs(current_gate_position_size)
            
            # 포지션 방향과 클로즈 주문 방향이 일치하는지 확인
            if current_position_side != position_side:
                self.logger.warning(f"⚠️ 포지션 방향 불일치: 현재={current_position_side}, 예상={position_side}")
                # 🔥🔥🔥 강화: 현재 포지션에 맞게 조정하여 처리
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
            
            self.logger.info(f"✅ 강화된 클로즈 주문 크기 계산 완료: 현재 포지션={current_gate_position_size} → 클로즈 크기={final_gate_size} (비율: {close_ratio*100:.1f}%)")
            
            return final_gate_size, True  # reduce_only=True
            
        except Exception as e:
            self.logger.error(f"강화된 클로즈 주문 크기 계산 실패: {e}")
            # 🔥🔥🔥 실패해도 기본 크기로 클로즈 주문 생성
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
        """기존 호환성을 위한 래퍼 메서드"""
        return await self.calculate_gate_order_size_for_close_order_enhanced(
            current_gate_position_size, close_order_details, bitget_order
        )
    
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
        """🔥🔥🔥 클로즈 주문과 현재 포지션 간의 유효성 검증 - 더 관대한 버전"""
        try:
            # 🔥🔥🔥 포지션이 없어도 클로즈 주문 허용
            if current_gate_position_size == 0:
                return True, "현재 포지션이 없지만 클로즈 주문 강제 허용 (포지션 생성될 수 있음)"
            
            # 현재 포지션 방향
            current_position_side = 'long' if current_gate_position_size > 0 else 'short'
            
            # 클로즈 주문에서 예상하는 포지션 방향
            expected_position_side = close_order_details['position_side']
            
            if current_position_side != expected_position_side:
                return True, f"포지션 방향 불일치하지만 현재 포지션({current_position_side})에 맞게 조정하여 허용"
            
            return True, f"클로즈 주문 유효: {current_position_side} 포지션 → {close_order_details['order_direction']} 주문"
            
        except Exception as e:
            self.logger.error(f"클로즈 주문 유효성 검증 실패하지만 허용: {e}")
            return True, f"검증 오류이지만 클로즈 주문 허용: {str(e)}"
    
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
