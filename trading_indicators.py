import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging
import asyncio

logger = logging.getLogger(__name__)

class AdvancedTradingIndicators:
    """선물 거래 특화 고급 지표 시스템"""
    
    def __init__(self):
        self.logger = logging.getLogger('trading_indicators')
        self.bitget_client = None
        
    def set_bitget_client(self, bitget_client):
        """Bitget 클라이언트 설정"""
        self.bitget_client = bitget_client
        
    async def calculate_all_indicators(self, market_data: Dict) -> Dict:
        """모든 지표 계산 및 종합 분석"""
        try:
            # 병렬로 지표 계산
            tasks = [
                self.analyze_funding_rate(market_data),
                self.analyze_open_interest(market_data),
                self.calculate_volume_delta(market_data),
                self.analyze_liquidations(market_data),
                self.calculate_futures_basis(market_data),
                self.analyze_long_short_ratio(market_data),
                self.calculate_market_profile(market_data),
                self.analyze_smart_money(market_data),
                self.calculate_technical_indicators(market_data),
                self.assess_risk_metrics(market_data)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 통합
            indicators = {}
            names = ['funding_analysis', 'oi_analysis', 'volume_delta', 'liquidation_analysis',
                    'futures_metrics', 'long_short_ratio', 'market_profile', 'smart_money',
                    'technical', 'risk_metrics']
            
            for name, result in zip(names, results):
                if not isinstance(result, Exception):
                    indicators[name] = result
                else:
                    self.logger.error(f"{name} 계산 오류: {result}")
                    indicators[name] = {}
            
            # 종합 신호 생성
            indicators['composite_signal'] = self.generate_composite_signal(indicators)
            
            return indicators
            
        except Exception as e:
            self.logger.error(f"지표 계산 오류: {e}")
            return {}
    
    async def analyze_funding_rate(self, market_data: Dict) -> Dict:
        """펀딩비 분석"""
        try:
            funding_rate = market_data.get('funding_rate', 0)
            
            # 연환산 펀딩비
            annual_rate = funding_rate * 365 * 3  # 8시간마다 3번
            
            # 펀딩비 추세 판단
            if funding_rate > 0.001:  # 0.1% 이상
                signal = "롱 과열 (숏 유리)"
                trade_bias = "숏 진입 고려"
            elif funding_rate < -0.001:  # -0.1% 이하
                signal = "숏 과열 (롱 유리)"
                trade_bias = "롱 진입 고려"
            else:
                signal = "중립"
                trade_bias = "양방향 가능"
            
            return {
                'current_rate': funding_rate,
                'annual_rate': annual_rate,
                'signal': signal,
                'trade_bias': trade_bias,
                'is_extreme': abs(funding_rate) > 0.01
            }
            
        except Exception as e:
            self.logger.error(f"펀딩비 분석 오류: {e}")
            return {}
    
    async def analyze_open_interest(self, market_data: Dict) -> Dict:
        """미결제약정(OI) 분석"""
        try:
            # 실제로는 Bitget API에서 OI 데이터를 가져와야 함
            # 여기서는 시뮬레이션
            oi_change = np.random.uniform(-5, 5)  # 실제로는 API 데이터
            price_change = market_data.get('change_24h', 0) * 100
            
            # OI와 가격 관계 분석
            if oi_change > 2 and price_change > 1:
                signal = "강세 (롱 축적)"
                divergence = "일치"
            elif oi_change > 2 and price_change < -1:
                signal = "약세 경고 (숏 축적)"
                divergence = "다이버전스"
            elif oi_change < -2:
                signal = "포지션 청산 진행"
                divergence = "청산"
            else:
                signal = "안정적"
                divergence = "중립"
            
            return {
                'oi_change_percent': oi_change,
                'price_change_percent': price_change,
                'signal': signal,
                'price_divergence': divergence,
                'strength': abs(oi_change)
            }
            
        except Exception as e:
            self.logger.error(f"OI 분석 오류: {e}")
            return {}
    
    async def calculate_volume_delta(self, market_data: Dict) -> Dict:
        """누적 거래량 델타(CVD) 계산"""
        try:
            # 실제로는 틱 데이터에서 계산
            # 여기서는 간단한 추정
            volume = market_data.get('volume_24h', 0)
            price_change = market_data.get('change_24h', 0)
            
            # 매수/매도 거래량 추정
            if price_change > 0:
                buy_ratio = 0.5 + min(0.3, abs(price_change))
            else:
                buy_ratio = 0.5 - min(0.3, abs(price_change))
            
            buy_volume = volume * buy_ratio
            sell_volume = volume * (1 - buy_ratio)
            cvd = buy_volume - sell_volume
            cvd_ratio = (cvd / volume * 100) if volume > 0 else 0
            
            # CVD 신호
            if cvd_ratio > 20:
                signal = "강한 매수 압력"
            elif cvd_ratio > 10:
                signal = "매수 우세"
            elif cvd_ratio < -20:
                signal = "강한 매도 압력"
            elif cvd_ratio < -10:
                signal = "매도 우세"
            else:
                signal = "균형"
            
            return {
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'cvd': cvd,
                'cvd_ratio': cvd_ratio,
                'signal': signal
            }
            
        except Exception as e:
            self.logger.error(f"CVD 계산 오류: {e}")
            return {}
    
    async def analyze_liquidations(self, market_data: Dict) -> Dict:
        """청산 데이터 분석"""
        try:
            current_price = market_data.get('current_price', 0)
            
            # 주요 청산 레벨 계산 (레버리지별)
            liquidation_levels = {
                'long': [],
                'short': []
            }
            
            # 롱 청산 레벨 (가격 하락 시)
            for leverage in [3, 5, 10, 20]:
                liq_price = current_price * (1 - 0.8/leverage)
                liquidation_levels['long'].append(liq_price)
            
            # 숏 청산 레벨 (가격 상승 시)
            for leverage in [3, 5, 10, 20]:
                liq_price = current_price * (1 + 0.8/leverage)
                liquidation_levels['short'].append(liq_price)
            
            # 가장 가까운 청산 레벨
            nearest_long_liq = max(liquidation_levels['long'])
            nearest_short_liq = min(liquidation_levels['short'])
            
            # 청산 압력 평가
            long_distance = (current_price - nearest_long_liq) / current_price
            short_distance = (nearest_short_liq - current_price) / current_price
            
            if long_distance < 0.03:  # 3% 이내
                liquidation_pressure = "롱 청산 임박"
            elif short_distance < 0.03:  # 3% 이내
                liquidation_pressure = "숏 청산 임박"
            else:
                liquidation_pressure = "안전 구간"
            
            return {
                'long_liquidation_levels': liquidation_levels['long'],
                'short_liquidation_levels': liquidation_levels['short'],
                'nearest_long_liq': nearest_long_liq,
                'nearest_short_liq': nearest_short_liq,
                'long_distance_percent': long_distance * 100,
                'short_distance_percent': short_distance * 100,
                'liquidation_pressure': liquidation_pressure
            }
            
        except Exception as e:
            self.logger.error(f"청산 분석 오류: {e}")
            return {}
    
    async def calculate_futures_basis(self, market_data: Dict) -> Dict:
        """선물 베이시스 계산"""
        try:
            # 실제로는 현물과 선물 가격 차이 계산
            # 여기서는 펀딩비 기반 추정
            funding_rate = market_data.get('funding_rate', 0)
            
            # 베이시스 추정 (연환산)
            basis_annual = funding_rate * 365 * 3
            
            if basis_annual > 15:
                signal = "콘탱고 과열 (숏 유리)"
            elif basis_annual > 5:
                signal = "정상 콘탱고"
            elif basis_annual < -5:
                signal = "백워데이션 (롱 유리)"
            else:
                signal = "중립"
            
            return {
                'basis': {
                    'rate': funding_rate * 100,
                    'annual': basis_annual,
                    'signal': signal
                }
            }
            
        except Exception as e:
            self.logger.error(f"베이시스 계산 오류: {e}")
            return {}
    
    async def analyze_long_short_ratio(self, market_data: Dict) -> Dict:
        """롱/숏 비율 분석"""
        try:
            # 실제로는 거래소 API에서 데이터 조회
            # 여기서는 시뮬레이션
            long_ratio = np.random.uniform(45, 55)
            short_ratio = 100 - long_ratio
            
            if long_ratio > 60:
                signal = "롱 과밀 (조정 주의)"
            elif long_ratio < 40:
                signal = "숏 과밀 (반등 주의)"
            else:
                signal = "균형 상태"
            
            return {
                'long_ratio': long_ratio,
                'short_ratio': short_ratio,
                'ratio': long_ratio / short_ratio,
                'signal': signal
            }
            
        except Exception as e:
            self.logger.error(f"롱숏 비율 분석 오류: {e}")
            return {}
    
    async def calculate_market_profile(self, market_data: Dict) -> Dict:
        """마켓 프로파일 분석"""
        try:
            current_price = market_data.get('current_price', 0)
            high_24h = market_data.get('high_24h', 0)
            low_24h = market_data.get('low_24h', 0)
            
            # POC (Point of Control) - 가장 많이 거래된 가격
            # 실제로는 거래량 프로파일 데이터 필요
            poc = (high_24h + low_24h) / 2
            
            # Value Area (거래량의 70%가 발생한 구간)
            range_24h = high_24h - low_24h
            value_area_high = poc + range_24h * 0.35
            value_area_low = poc - range_24h * 0.35
            
            # 현재 가격 위치
            if current_price > value_area_high:
                price_position = "Value Area 상단 (과매수 구간)"
            elif current_price < value_area_low:
                price_position = "Value Area 하단 (과매도 구간)"
            else:
                price_position = "Value Area 내 (정상 구간)"
            
            return {
                'poc': poc,
                'value_area_high': value_area_high,
                'value_area_low': value_area_low,
                'price_position': price_position,
                'range_24h': range_24h
            }
            
        except Exception as e:
            self.logger.error(f"마켓 프로파일 계산 오류: {e}")
            return {}
    
    async def analyze_smart_money(self, market_data: Dict) -> Dict:
        """스마트머니 플로우 분석"""
        try:
            # 대형 거래 감지 (실제로는 거래 데이터 분석)
            volume = market_data.get('volume_24h', 0)
            
            # 대형 거래 시뮬레이션
            large_buy_count = np.random.randint(5, 15)
            large_sell_count = np.random.randint(5, 15)
            
            net_flow = large_buy_count - large_sell_count
            
            if net_flow > 5:
                signal = "스마트머니 매수 진입"
            elif net_flow < -5:
                signal = "스마트머니 매도 진행"
            else:
                signal = "중립"
            
            return {
                'large_buy_count': large_buy_count,
                'large_sell_count': large_sell_count,
                'net_flow': net_flow,
                'signal': signal
            }
            
        except Exception as e:
            self.logger.error(f"스마트머니 분석 오류: {e}")
            return {}
    
    async def calculate_technical_indicators(self, market_data: Dict) -> Dict:
        """기술적 지표 계산"""
        try:
            # RSI 계산 (간단한 버전)
            change_24h = market_data.get('change_24h', 0)
            
            # RSI 추정 (실제로는 14일 데이터 필요)
            if change_24h > 0.02:
                rsi = 60 + change_24h * 500
            elif change_24h < -0.02:
                rsi = 40 + change_24h * 500
            else:
                rsi = 50 + change_24h * 250
            
            rsi = max(0, min(100, rsi))
            
            # RSI 신호
            if rsi > 70:
                rsi_signal = "과매수"
            elif rsi < 30:
                rsi_signal = "과매도"
            else:
                rsi_signal = "중립"
            
            return {
                'rsi': {
                    'value': rsi,
                    'signal': rsi_signal
                }
            }
            
        except Exception as e:
            self.logger.error(f"기술 지표 계산 오류: {e}")
            return {}
    
    async def assess_risk_metrics(self, market_data: Dict) -> Dict:
        """리스크 메트릭 평가"""
        try:
            volatility = market_data.get('volatility', 0)
            funding_rate = abs(market_data.get('funding_rate', 0))
            
            # 리스크 점수 계산
            risk_score = 0
            
            # 변동성 리스크
            if volatility > 5:
                risk_score += 3
                volatility_risk = "높음"
            elif volatility > 3:
                risk_score += 2
                volatility_risk = "보통"
            else:
                risk_score += 1
                volatility_risk = "낮음"
            
            # 펀딩비 리스크
            if funding_rate > 0.01:
                risk_score += 3
                funding_risk = "높음"
            elif funding_rate > 0.005:
                risk_score += 2
                funding_risk = "보통"
            else:
                risk_score += 1
                funding_risk = "낮음"
            
            # 종합 리스크 레벨
            if risk_score >= 5:
                risk_level = "높음"
                position_sizing = "포지션 축소 권장"
            elif risk_score >= 3:
                risk_level = "보통"
                position_sizing = "표준 포지션"
            else:
                risk_level = "낮음"
                position_sizing = "포지션 확대 가능"
            
            return {
                'risk_score': risk_score,
                'risk_level': risk_level,
                'volatility_risk': volatility_risk,
                'funding_risk': funding_risk,
                'position_sizing': position_sizing
            }
            
        except Exception as e:
            self.logger.error(f"리스크 평가 오류: {e}")
            return {}
    
    def generate_composite_signal(self, indicators: Dict) -> Dict:
        """종합 신호 생성"""
        try:
            scores = {}
            total_score = 0
            
            # 펀딩비 점수
            funding = indicators.get('funding_analysis', {})
            if '숏 유리' in funding.get('signal', ''):
                scores['funding'] = -3
            elif '롱 유리' in funding.get('signal', ''):
                scores['funding'] = 3
            else:
                scores['funding'] = 0
            
            # OI 점수
            oi = indicators.get('oi_analysis', {})
            if '강세' in oi.get('signal', ''):
                scores['oi'] = 2
            elif '약세' in oi.get('signal', ''):
                scores['oi'] = -2
            else:
                scores['oi'] = 0
            
            # CVD 점수
            cvd = indicators.get('volume_delta', {})
            cvd_ratio = cvd.get('cvd_ratio', 0)
            scores['cvd'] = max(-3, min(3, cvd_ratio / 10))
            
            # 기술적 지표 점수
            tech = indicators.get('technical', {})
            rsi = tech.get('rsi', {})
            if rsi.get('signal') == '과매수':
                scores['technical'] = -2
            elif rsi.get('signal') == '과매도':
                scores['technical'] = 2
            else:
                scores['technical'] = 0
            
            # 총점 계산
            total_score = sum(scores.values())
            
            # 신호 결정
            if total_score >= 5:
                signal = "강한 롱 신호"
                confidence = min(90, 50 + total_score * 5)
                action = "롱 진입"
            elif total_score >= 2:
                signal = "약한 롱 신호"
                confidence = 60
                action = "소량 롱"
            elif total_score <= -5:
                signal = "강한 숏 신호"
                confidence = min(90, 50 + abs(total_score) * 5)
                action = "숏 진입"
            elif total_score <= -2:
                signal = "약한 숏 신호"
                confidence = 60
                action = "소량 숏"
            else:
                signal = "중립"
                confidence = 40
                action = "관망"
            
            # 리스크 조정
            risk = indicators.get('risk_metrics', {})
            if risk.get('risk_level') == '높음':
                confidence *= 0.8
                if '소량' not in action and action != '관망':
                    action = f"소량 {action}"
            
            return {
                'scores': scores,
                'total_score': total_score,
                'signal': signal,
                'confidence': confidence,
                'action': action,
                'position_size': risk.get('position_sizing', '표준')
            }
            
        except Exception as e:
            self.logger.error(f"종합 신호 생성 오류: {e}")
            return {
                'signal': '오류',
                'confidence': 0,
                'action': '관망'
            }
