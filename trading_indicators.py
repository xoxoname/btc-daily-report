import numpy as np
from typing import Dict, List, Tuple
import pandas as pd
from datetime import datetime, timedelta

class AdvancedTradingIndicators:
    """비트코인 선물 매매 정확도 향상을 위한 고급 지표"""
    
    def __init__(self):
        self.indicators = {}
        
    async def calculate_all_indicators(self, market_data: Dict) -> Dict:
        """모든 지표 계산 및 매매 신호 생성"""
        
        indicators = {
            # 1. 시장 구조 분석
            'market_structure': await self.analyze_market_structure(market_data),
            
            # 2. 파생상품 지표
            'derivatives': await self.analyze_derivatives(market_data),
            
            # 3. 온체인 지표
            'onchain': await self.analyze_onchain_metrics(market_data),
            
            # 4. 거래소 플로우
            'exchange_flow': await self.analyze_exchange_flows(market_data),
            
            # 5. 시장 미시구조
            'microstructure': await self.analyze_microstructure(market_data),
            
            # 6. 멀티 타임프레임 분석
            'multi_timeframe': await self.analyze_multi_timeframe(market_data),
            
            # 7. AI 예측 모델
            'ai_prediction': await self.run_ai_prediction(market_data)
        }
        
        # 종합 점수 계산
        indicators['composite_score'] = self.calculate_composite_score(indicators)
        
        return indicators
    
    async def analyze_market_structure(self, data: Dict) -> Dict:
        """시장 구조 분석"""
        return {
            # 1. 선물-현물 베이시스
            'basis': {
                'value': data.get('futures_price', 0) - data.get('spot_price', 0),
                'signal': self._interpret_basis(data.get('futures_price', 0) - data.get('spot_price', 0)),
                'description': "선물 프리미엄/디스카운트 상태"
            },
            
            # 2. 기간 구조 (Term Structure)
            'term_structure': {
                'contango': data.get('next_month_futures', 0) > data.get('current_month_futures', 0),
                'signal': "➕호재" if data.get('next_month_futures', 0) > data.get('current_month_futures', 0) else "➖악재",
                'description': "선물 만기별 가격 구조"
            },
            
            # 3. 변동성 스큐
            'volatility_skew': {
                'put_call_skew': data.get('put_iv', 0) - data.get('call_iv', 0),
                'signal': self._interpret_skew(data.get('put_iv', 0) - data.get('call_iv', 0)),
                'description': "옵션 변동성 비대칭"
            }
        }
    
    async def analyze_derivatives(self, data: Dict) -> Dict:
        """파생상품 지표 분석"""
        return {
            # 1. 미결제약정 분석
            'open_interest': {
                'total_oi': data.get('total_oi', 0),
                'oi_change_24h': data.get('oi_change_24h', 0),
                'oi_weighted_funding': data.get('oi_weighted_funding', 0),
                'signal': self._interpret_oi_change(data.get('oi_change_24h', 0)),
                'description': "미결제약정 변화와 펀딩 가중치"
            },
            
            # 2. 청산 데이터
            'liquidations': {
                'long_liquidations_24h': data.get('long_liq_24h', 0),
                'short_liquidations_24h': data.get('short_liq_24h', 0),
                'liquidation_ratio': self._calculate_liq_ratio(data),
                'signal': self._interpret_liquidations(data),
                'description': "롱/숏 청산 비율"
            },
            
            # 3. 옵션 플로우
            'options_flow': {
                'put_call_ratio': data.get('put_call_ratio', 0),
                'gamma_exposure': data.get('gamma_exposure', 0),
                'max_pain': data.get('max_pain_price', 0),
                'signal': self._interpret_options_flow(data),
                'description': "옵션 시장 포지셔닝"
            }
        }
    
    async def analyze_onchain_metrics(self, data: Dict) -> Dict:
        """온체인 지표 분석"""
        return {
            # 1. SOPR (Spent Output Profit Ratio)
            'sopr': {
                'value': data.get('sopr', 1),
                'adjusted_sopr': data.get('adjusted_sopr', 1),
                'signal': "➕호재" if data.get('sopr', 1) > 1 else "➖악재",
                'description': "실현 손익 비율"
            },
            
            # 2. NUPL (Net Unrealized Profit/Loss)
            'nupl': {
                'value': data.get('nupl', 0),
                'market_phase': self._determine_market_phase(data.get('nupl', 0)),
                'signal': self._interpret_nupl(data.get('nupl', 0)),
                'description': "미실현 손익 상태"
            },
            
            # 3. 거래소 보유량
            'exchange_reserves': {
                'total_reserves': data.get('exchange_reserves', 0),
                'net_flow_7d': data.get('exchange_netflow_7d', 0),
                'signal': "➕호재" if data.get('exchange_netflow_7d', 0) < 0 else "➖악재",
                'description': "거래소 BTC 순유출입"
            },
            
            # 4. 고래 활동
            'whale_activity': {
                'whale_transactions': data.get('whale_tx_count', 0),
                'whale_accumulation': data.get('whale_accumulation_trend', 0),
                'signal': self._interpret_whale_activity(data),
                'description': "대형 홀더 활동"
            }
        }
    
    async def analyze_exchange_flows(self, data: Dict) -> Dict:
        """거래소별 자금 흐름 분석"""
        return {
            # 1. 스테이블코인 흐름
            'stablecoin_flow': {
                'exchange_stablecoin_ratio': data.get('stablecoin_ratio', 0),
                'usdt_premium': data.get('usdt_premium', 0),
                'signal': "➕호재" if data.get('stablecoin_ratio', 0) > 1.5 else "중립",
                'description': "거래소 스테이블코인 비율"
            },
            
            # 2. 거래소간 차익거래
            'arbitrage': {
                'korea_premium': data.get('korea_premium', 0),
                'exchange_spread': data.get('max_exchange_spread', 0),
                'signal': self._interpret_arbitrage(data),
                'description': "거래소간 가격 차이"
            },
            
            # 3. 거래량 분석
            'volume_analysis': {
                'spot_volume': data.get('spot_volume_24h', 0),
                'futures_volume': data.get('futures_volume_24h', 0),
                'volume_ratio': data.get('futures_volume_24h', 1) / max(data.get('spot_volume_24h', 1), 1),
                'signal': self._interpret_volume_ratio(data),
                'description': "현물/선물 거래량 비율"
            }
        }
    
    async def analyze_microstructure(self, data: Dict) -> Dict:
        """시장 미시구조 분석"""
        return {
            # 1. 주문장 분석
            'orderbook': {
                'bid_ask_spread': data.get('spread', 0),
                'orderbook_imbalance': data.get('orderbook_imbalance', 0),
                'depth_ratio': data.get('bid_depth', 0) / max(data.get('ask_depth', 1), 1),
                'signal': self._interpret_orderbook(data),
                'description': "매수/매도 주문장 균형"
            },
            
            # 2. 거래 플로우
            'trade_flow': {
                'buy_sell_ratio': data.get('buy_volume', 0) / max(data.get('sell_volume', 1), 1),
                'large_trades': data.get('large_trade_count', 0),
                'aggressive_buyers': data.get('aggressive_buy_ratio', 0),
                'signal': self._interpret_trade_flow(data),
                'description': "실거래 매수/매도 압력"
            },
            
            # 3. 시장 효율성
            'market_efficiency': {
                'price_discovery': data.get('futures_lead_spot', True),
                'correlation_breakdown': data.get('correlation_breakdown', False),
                'signal': "주의" if data.get('correlation_breakdown', False) else "정상",
                'description': "시장 효율성 지표"
            }
        }
    
    async def analyze_multi_timeframe(self, data: Dict) -> Dict:
        """멀티 타임프레임 분석"""
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        signals = {}
        
        for tf in timeframes:
            tf_data = data.get(f'tf_{tf}', {})
            signals[tf] = {
                'trend': self._determine_trend(tf_data),
                'momentum': self._calculate_momentum(tf_data),
                'support_resistance': self._find_sr_levels(tf_data)
            }
        
        return {
            'signals': signals,
            'alignment': self._check_timeframe_alignment(signals),
            'strength': self._calculate_signal_strength(signals),
            'description': "다중 시간대 신호 정렬도"
        }
    
    async def run_ai_prediction(self, data: Dict) -> Dict:
        """AI 기반 예측 모델"""
        # 실제 구현시에는 훈련된 모델 사용
        features = self._prepare_features(data)
        
        return {
            'price_prediction': {
                '1h': data.get('current_price', 0) * 1.001,  # 예시
                '4h': data.get('current_price', 0) * 1.002,
                '24h': data.get('current_price', 0) * 1.005,
                'confidence': 0.75
            },
            'direction_probability': {
                'up': 0.62,
                'down': 0.38
            },
            'volatility_forecast': {
                'expected_volatility': 2.5,
                'volatility_regime': "medium"
            },
            'signal': "➕호재",
            'description': "머신러닝 기반 예측"
        }
    
    def calculate_composite_score(self, indicators: Dict) -> Dict:
        """종합 점수 계산"""
        weights = {
            'market_structure': 0.15,
            'derivatives': 0.20,
            'onchain': 0.15,
            'exchange_flow': 0.15,
            'microstructure': 0.20,
            'multi_timeframe': 0.10,
            'ai_prediction': 0.05
        }
        
        bullish_score = 0
        bearish_score = 0
        
        # 각 지표별 점수 계산 (실제 구현시 상세 로직 필요)
        for category, weight in weights.items():
            if category in indicators:
                # 호재/악재 신호에 따라 점수 부여
                category_score = self._calculate_category_score(indicators[category])
                if category_score > 0:
                    bullish_score += category_score * weight
                else:
                    bearish_score += abs(category_score) * weight
        
        total_score = bullish_score - bearish_score
        
        return {
            'bullish_score': round(bullish_score * 100, 1),
            'bearish_score': round(bearish_score * 100, 1),
            'composite_score': round(total_score * 100, 1),
            'signal': self._determine_signal(total_score),
            'confidence': self._calculate_confidence(indicators),
            'recommended_action': self._recommend_action(total_score, indicators)
        }
    
    # 보조 함수들
    def _interpret_basis(self, basis: float) -> str:
        if basis > 100:
            return "➕강한 호재"
        elif basis > 0:
            return "➕호재"
        elif basis < -100:
            return "➖강한 악재"
        else:
            return "➖악재"
    
    def _interpret_skew(self, skew: float) -> str:
        if skew > 5:
            return "➖악재 (하방 헤지 증가)"
        elif skew < -5:
            return "➕호재 (상방 기대 증가)"
        else:
            return "중립"
    
    def _interpret_oi_change(self, change: float) -> str:
        if change > 10:
            return "➕호재 (관심 증가)"
        elif change < -10:
            return "➖악재 (포지션 정리)"
        else:
            return "중립"
    
    def _calculate_liq_ratio(self, data: Dict) -> float:
        long_liq = data.get('long_liq_24h', 0)
        short_liq = data.get('short_liq_24h', 0)
        total = long_liq + short_liq
        return long_liq / total if total > 0 else 0.5
    
    def _interpret_liquidations(self, data: Dict) -> str:
        ratio = self._calculate_liq_ratio(data)
        if ratio > 0.7:
            return "➕호재 (롱 청산 우세)"
        elif ratio < 0.3:
            return "➖악재 (숏 청산 우세)"
        else:
            return "중립"
    
    def _interpret_options_flow(self, data: Dict) -> str:
        pcr = data.get('put_call_ratio', 1)
        if pcr > 1.5:
            return "➖악재 (풋 우세)"
        elif pcr < 0.7:
            return "➕호재 (콜 우세)"
        else:
            return "중립"
    
    def _determine_market_phase(self, nupl: float) -> str:
        if nupl < 0:
            return "Capitulation"
        elif nupl < 0.25:
            return "Hope/Fear"
        elif nupl < 0.5:
            return "Optimism/Anxiety"
        elif nupl < 0.75:
            return "Belief/Denial"
        else:
            return "Euphoria/Greed"
    
    def _interpret_nupl(self, nupl: float) -> str:
        if nupl < 0:
            return "➕강한 호재 (바닥 신호)"
        elif nupl > 0.75:
            return "➖강한 악재 (과열 신호)"
        else:
            return "중립"
    
    def _interpret_whale_activity(self, data: Dict) -> str:
        accumulation = data.get('whale_accumulation_trend', 0)
        if accumulation > 0.1:
            return "➕호재 (고래 매집)"
        elif accumulation < -0.1:
            return "➖악재 (고래 매도)"
        else:
            return "중립"
    
    def _interpret_arbitrage(self, data: Dict) -> str:
        premium = data.get('korea_premium', 0)
        if abs(premium) > 2:
            return "거래 기회"
        else:
            return "정상"
    
    def _interpret_volume_ratio(self, data: Dict) -> str:
        ratio = data.get('futures_volume_24h', 1) / max(data.get('spot_volume_24h', 1), 1)
        if ratio > 3:
            return "➖악재 (투기 과열)"
        elif ratio < 0.5:
            return "➕호재 (현물 주도)"
        else:
            return "중립"
    
    def _interpret_orderbook(self, data: Dict) -> str:
        imbalance = data.get('orderbook_imbalance', 0)
        if imbalance > 0.2:
            return "➕호재 (매수 우세)"
        elif imbalance < -0.2:
            return "➖악재 (매도 우세)"
        else:
            return "균형"
    
    def _interpret_trade_flow(self, data: Dict) -> str:
        ratio = data.get('buy_volume', 0) / max(data.get('sell_volume', 1), 1)
        if ratio > 1.2:
            return "➕호재 (매수 압력)"
        elif ratio < 0.8:
            return "➖악재 (매도 압력)"
        else:
            return "균형"
    
    def _determine_trend(self, data: Dict) -> str:
        # 추세 판단 로직
        return "상승" if data.get('trend_score', 0) > 0 else "하락"
    
    def _calculate_momentum(self, data: Dict) -> float:
        # 모멘텀 계산 로직
        return data.get('momentum', 0)
    
    def _find_sr_levels(self, data: Dict) -> Dict:
        # 지지/저항 레벨 찾기
        return {
            'support': data.get('support_levels', []),
            'resistance': data.get('resistance_levels', [])
        }
    
    def _check_timeframe_alignment(self, signals: Dict) -> float:
        # 타임프레임 정렬도 체크
        aligned = sum(1 for tf, signal in signals.items() if signal.get('trend') == '상승')
        return aligned / len(signals)
    
    def _calculate_signal_strength(self, signals: Dict) -> str:
        alignment = self._check_timeframe_alignment(signals)
        if alignment > 0.8:
            return "매우 강함"
        elif alignment > 0.6:
            return "강함"
        elif alignment > 0.4:
            return "보통"
        else:
            return "약함"
    
    def _prepare_features(self, data: Dict) -> np.ndarray:
        # ML 모델용 특징 준비
        features = []
        # 실제 구현시 필요한 특징들 추출
        return np.array(features)
    
    def _calculate_category_score(self, category_data: Dict) -> float:
        # 카테고리별 점수 계산
        score = 0
        for key, value in category_data.items():
            if isinstance(value, dict) and 'signal' in value:
                signal = value['signal']
                if '강한 호재' in signal:
                    score += 2
                elif '호재' in signal:
                    score += 1
                elif '강한 악재' in signal:
                    score -= 2
                elif '악재' in signal:
                    score -= 1
        return score
    
    def _determine_signal(self, score: float) -> str:
        if score > 0.3:
            return "➕강한 매수"
        elif score > 0.1:
            return "➕매수"
        elif score < -0.3:
            return "➖강한 매도"
        elif score < -0.1:
            return "➖매도"
        else:
            return "중립/관망"
    
    def _calculate_confidence(self, indicators: Dict) -> float:
        # 신호 신뢰도 계산
        # 여러 지표가 일치할수록 높은 신뢰도
        return 0.75  # 예시
    
    def _recommend_action(self, score: float, indicators: Dict) -> str:
        """구체적인 매매 전략 추천"""
        if score > 0.3:
            return "즉시 롱 진입, 레버리지 3-5배, 손절 -2%"
        elif score > 0.1:
            return "분할 롱 진입, 레버리지 2-3배, 손절 -3%"
        elif score < -0.3:
            return "즉시 숏 진입, 레버리지 3-5배, 손절 -2%"
        elif score < -0.1:
            return "분할 숏 진입, 레버리지 2-3배, 손절 -3%"
        else:
            return "포지션 유지 또는 관망, 변동성 돌파 대기"
