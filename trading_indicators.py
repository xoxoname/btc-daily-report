import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging
import asyncio

logger = logging.getLogger(__name__)

class AdvancedTradingIndicators:
    """선물 거래 특화 고급 지표 시스템"""
    
    def __init__(self, data_collector=None):
        self.logger = logging.getLogger('trading_indicators')
        self.data_collector = data_collector
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
            
            # 펀딩비 방향성 분석
            direction = "중립"
            strength = "보통"
            
            if funding_rate > 0.01:  # 1% 이상
                direction = "강력 매수"
                strength = "높음"
            elif funding_rate > 0.005:  # 0.5% 이상
                direction = "매수"
                strength = "보통"
            elif funding_rate < -0.01:  # -1% 이하
                direction = "강력 매도"
                strength = "높음"
            elif funding_rate < -0.005:  # -0.5% 이하
                direction = "매도"
                strength = "보통"
            
            return {
                'current_rate': funding_rate,
                'annual_rate': annual_rate,
                'direction': direction,
                'strength': strength,
                'signal_score': self._calculate_funding_score(funding_rate)
            }
            
        except Exception as e:
            self.logger.error(f"펀딩비 분석 오류: {e}")
            return {}
    
    def _calculate_funding_score(self, funding_rate: float) -> int:
        """펀딩비 점수 계산 (-5 ~ +5)"""
        try:
            if funding_rate > 0.015:
                return -5  # 매우 부정적 (롱 포지션 과도)
            elif funding_rate > 0.01:
                return -3
            elif funding_rate > 0.005:
                return -1
            elif funding_rate < -0.015:
                return 5  # 매우 긍정적 (숏 포지션 과도)
            elif funding_rate < -0.01:
                return 3
            elif funding_rate < -0.005:
                return 1
            else:
                return 0  # 중립
        except:
            return 0
    
    async def analyze_open_interest(self, market_data: Dict) -> Dict:
        """미결제약정 분석"""
        try:
            oi_current = market_data.get('open_interest', 0)
            oi_change = market_data.get('oi_change_24h', 0)
            price_change = market_data.get('change_24h', 0)
            
            # OI와 가격 관계 분석
            oi_price_signal = self._analyze_oi_price_relationship(oi_change, price_change)
            
            return {
                'current_oi': oi_current,
                'oi_change_24h': oi_change,
                'oi_trend': "증가" if oi_change > 0 else "감소" if oi_change < 0 else "변화없음",
                'oi_price_signal': oi_price_signal,
                'signal_score': self._calculate_oi_score(oi_change, price_change)
            }
            
        except Exception as e:
            self.logger.error(f"OI 분석 오류: {e}")
            return {}
    
    def _analyze_oi_price_relationship(self, oi_change: float, price_change: float) -> str:
        """OI와 가격 관계 분석"""
        try:
            if oi_change > 0.02 and price_change > 0.02:
                return "강한 상승 추세"
            elif oi_change > 0.02 and price_change < -0.02:
                return "분산 패턴 (조정 신호)"
            elif oi_change < -0.02 and price_change > 0.02:
                return "약한 상승 (반등 한계)"
            elif oi_change < -0.02 and price_change < -0.02:
                return "강한 하락 추세"
            else:
                return "중립적 움직임"
        except:
            return "분석 불가"
    
    def _calculate_oi_score(self, oi_change: float, price_change: float) -> int:
        """OI 점수 계산"""
        try:
            # OI 증가 + 가격 상승 = 긍정적
            if oi_change > 0.03 and price_change > 0.03:
                return 3
            elif oi_change > 0.02 and price_change > 0.02:
                return 2
            # OI 감소 + 가격 하락 = 부정적
            elif oi_change < -0.03 and price_change < -0.03:
                return -3
            elif oi_change < -0.02 and price_change < -0.02:
                return -2
            # 분산 패턴
            elif oi_change > 0.02 and price_change < -0.02:
                return -1
            elif oi_change < -0.02 and price_change > 0.02:
                return -1
            else:
                return 0
        except:
            return 0
    
    async def calculate_volume_delta(self, market_data: Dict) -> Dict:
        """거래량 델타 (CVD) 계산"""
        try:
            volume_24h = market_data.get('volume_24h', 0)
            avg_volume = market_data.get('avg_volume_7d', volume_24h)
            
            volume_ratio = volume_24h / avg_volume if avg_volume > 0 else 1
            
            # 매수/매도 압력 추정 (가격 변동과 거래량 관계)
            price_change = market_data.get('change_24h', 0)
            
            buy_pressure = 0
            sell_pressure = 0
            
            if price_change > 0 and volume_ratio > 1.2:
                buy_pressure = min(volume_ratio * abs(price_change) * 100, 10)
            elif price_change < 0 and volume_ratio > 1.2:
                sell_pressure = min(volume_ratio * abs(price_change) * 100, 10)
            
            net_delta = buy_pressure - sell_pressure
            
            return {
                'volume_24h': volume_24h,
                'volume_ratio': volume_ratio,
                'buy_pressure': buy_pressure,
                'sell_pressure': sell_pressure,
                'net_delta': net_delta,
                'signal_score': self._calculate_volume_score(net_delta, volume_ratio)
            }
            
        except Exception as e:
            self.logger.error(f"거래량 델타 계산 오류: {e}")
            return {}
    
    def _calculate_volume_score(self, net_delta: float, volume_ratio: float) -> int:
        """거래량 점수 계산"""
        try:
            base_score = 0
            
            # 순 델타 기반 점수
            if net_delta > 5:
                base_score = 3
            elif net_delta > 2:
                base_score = 2
            elif net_delta > 0:
                base_score = 1
            elif net_delta < -5:
                base_score = -3
            elif net_delta < -2:
                base_score = -2
            elif net_delta < 0:
                base_score = -1
            
            # 거래량 배율 보정
            if volume_ratio > 2:
                base_score = int(base_score * 1.5)
            elif volume_ratio < 0.5:
                base_score = int(base_score * 0.5)
            
            return max(-5, min(5, base_score))
        except:
            return 0
    
    async def analyze_liquidations(self, market_data: Dict) -> Dict:
        """청산 분석"""
        try:
            # 청산 데이터는 외부 API에서 가져와야 하므로 기본 추정값 사용
            price_change = market_data.get('change_24h', 0)
            volume_ratio = market_data.get('volume_ratio', 1)
            
            # 급격한 가격 변동 시 청산 추정
            liquidation_estimate = 0
            liquidation_side = "중립"
            
            if abs(price_change) > 0.05 and volume_ratio > 1.5:
                liquidation_estimate = abs(price_change) * volume_ratio * 1000000  # 추정 청산량
                liquidation_side = "롱 청산" if price_change < 0 else "숏 청산"
            
            return {
                'estimated_liquidations': liquidation_estimate,
                'liquidation_side': liquidation_side,
                'liquidation_risk': "높음" if abs(price_change) > 0.08 else "보통" if abs(price_change) > 0.03 else "낮음",
                'signal_score': self._calculate_liquidation_score(price_change, volume_ratio)
            }
            
        except Exception as e:
            self.logger.error(f"청산 분석 오류: {e}")
            return {}
    
    def _calculate_liquidation_score(self, price_change: float, volume_ratio: float) -> int:
        """청산 점수 계산"""
        try:
            if abs(price_change) > 0.1 and volume_ratio > 2:
                return -4 if price_change < 0 else 4
            elif abs(price_change) > 0.05 and volume_ratio > 1.5:
                return -2 if price_change < 0 else 2
            else:
                return 0
        except:
            return 0
    
    async def calculate_futures_basis(self, market_data: Dict) -> Dict:
        """선물 베이시스 계산"""
        try:
            spot_price = market_data.get('spot_price', market_data.get('current_price', 0))
            futures_price = market_data.get('current_price', 0)
            
            basis = (futures_price - spot_price) / spot_price if spot_price > 0 else 0
            basis_annual = basis * 365 / 30  # 월간 베이시스를 연환산
            
            # 베이시스 해석
            basis_signal = "중립"
            if basis > 0.02:
                basis_signal = "강한 콘탱고 (과열)"
            elif basis > 0.01:
                basis_signal = "콘탱고 (낙관적)"
            elif basis < -0.02:
                basis_signal = "강한 백워데이션 (비관적)"
            elif basis < -0.01:
                basis_signal = "백워데이션 (조정 가능성)"
            
            return {
                'basis': basis,
                'basis_annual': basis_annual,
                'basis_signal': basis_signal,
                'signal_score': self._calculate_basis_score(basis)
            }
            
        except Exception as e:
            self.logger.error(f"선물 베이시스 계산 오류: {e}")
            return {}
    
    def _calculate_basis_score(self, basis: float) -> int:
        """베이시스 점수 계산"""
        try:
            if basis > 0.03:
                return -3  # 과열 신호
            elif basis > 0.015:
                return -1
            elif basis < -0.03:
                return 3  # 과매도 신호
            elif basis < -0.015:
                return 1
            else:
                return 0
        except:
            return 0
    
    async def analyze_long_short_ratio(self, market_data: Dict) -> Dict:
        """롱/숏 비율 분석"""
        try:
            # 기본값 설정 (실제로는 거래소 API에서 가져와야 함)
            long_ratio = market_data.get('long_ratio', 0.5)
            short_ratio = 1 - long_ratio
            
            # 롱/숏 신호 분석
            ls_signal = "중립"
            if long_ratio > 0.75:
                ls_signal = "롱 과다 (조정 위험)"
            elif long_ratio > 0.65:
                ls_signal = "롱 우세 (주의)"
            elif long_ratio < 0.25:
                ls_signal = "숏 과다 (반등 가능성)"
            elif long_ratio < 0.35:
                ls_signal = "숏 우세 (매수 기회)"
            
            return {
                'long_ratio': long_ratio,
                'short_ratio': short_ratio,
                'ls_signal': ls_signal,
                'signal_score': self._calculate_ls_score(long_ratio)
            }
            
        except Exception as e:
            self.logger.error(f"롱/숏 비율 분석 오류: {e}")
            return {}
    
    def _calculate_ls_score(self, long_ratio: float) -> int:
        """롱/숏 점수 계산 (역행 지표)"""
        try:
            if long_ratio > 0.8:
                return -3  # 롱 과다 = 조정 위험
            elif long_ratio > 0.7:
                return -1
            elif long_ratio < 0.2:
                return 3  # 숏 과다 = 반등 가능성
            elif long_ratio < 0.3:
                return 1
            else:
                return 0
        except:
            return 0
    
    async def calculate_market_profile(self, market_data: Dict) -> Dict:
        """마켓 프로파일 분석"""
        try:
            current_price = market_data.get('current_price', 0)
            high_24h = market_data.get('high_24h', current_price)
            low_24h = market_data.get('low_24h', current_price)
            
            # 가격 위치 분석
            price_range = high_24h - low_24h
            if price_range > 0:
                price_position = (current_price - low_24h) / price_range
            else:
                price_position = 0.5
            
            # 포지션 해석
            position_signal = "중간"
            if price_position > 0.8:
                position_signal = "고점 근처 (저항선)"
            elif price_position > 0.6:
                position_signal = "상단 (주의)"
            elif price_position < 0.2:
                position_signal = "저점 근처 (지지선)"
            elif price_position < 0.4:
                position_signal = "하단 (매수 기회)"
            
            return {
                'price_position': price_position,
                'position_signal': position_signal,
                'high_24h': high_24h,
                'low_24h': low_24h,
                'signal_score': self._calculate_position_score(price_position)
            }
            
        except Exception as e:
            self.logger.error(f"마켓 프로파일 계산 오류: {e}")
            return {}
    
    def _calculate_position_score(self, price_position: float) -> int:
        """포지션 점수 계산"""
        try:
            if price_position > 0.9:
                return -2  # 고점 근처
            elif price_position > 0.7:
                return -1
            elif price_position < 0.1:
                return 2  # 저점 근처
            elif price_position < 0.3:
                return 1
            else:
                return 0
        except:
            return 0
    
    async def analyze_smart_money(self, market_data: Dict) -> Dict:
        """스마트머니 플로우 분석"""
        try:
            # 대형 거래 감지 (거래량과 가격 변동 관계)
            volume_24h = market_data.get('volume_24h', 0)
            avg_volume = market_data.get('avg_volume_7d', volume_24h)
            price_change = market_data.get('change_24h', 0)
            
            volume_ratio = volume_24h / avg_volume if avg_volume > 0 else 1
            
            # 스마트머니 신호 감지
            smart_signal = "일반"
            flow_direction = "중립"
            
            if volume_ratio > 2 and abs(price_change) > 0.03:
                if price_change > 0:
                    smart_signal = "대형 매수 유입"
                    flow_direction = "매수"
                else:
                    smart_signal = "대형 매도 유출"
                    flow_direction = "매도"
            elif volume_ratio > 1.5 and abs(price_change) < 0.01:
                smart_signal = "횡보 중 대량 거래 (축적)"
                flow_direction = "축적"
            
            return {
                'smart_signal': smart_signal,
                'flow_direction': flow_direction,
                'volume_ratio': volume_ratio,
                'signal_score': self._calculate_smart_score(flow_direction, volume_ratio)
            }
            
        except Exception as e:
            self.logger.error(f"스마트머니 분석 오류: {e}")
            return {}
    
    def _calculate_smart_score(self, flow_direction: str, volume_ratio: float) -> int:
        """스마트머니 점수 계산"""
        try:
            base_score = 0
            
            if flow_direction == "매수":
                base_score = 2
            elif flow_direction == "매도":
                base_score = -2
            elif flow_direction == "축적":
                base_score = 1
            
            # 거래량 배율로 가중치 적용
            if volume_ratio > 3:
                base_score = int(base_score * 1.5)
            
            return max(-3, min(3, base_score))
        except:
            return 0
    
    async def calculate_technical_indicators(self, market_data: Dict) -> Dict:
        """기술적 지표 계산"""
        try:
            # 기본 데이터
            current_price = market_data.get('current_price', 0)
            high_24h = market_data.get('high_24h', current_price)
            low_24h = market_data.get('low_24h', current_price)
            
            # RSI 추정 (가격 변동 기반)
            price_change = market_data.get('change_24h', 0)
            rsi_estimate = 50 + (price_change * 100)  # 간단한 RSI 추정
            rsi_estimate = max(0, min(100, rsi_estimate))
            
            # 볼린저 밴드 추정
            volatility = market_data.get('volatility', 0.02)
            bb_upper = current_price * (1 + volatility * 2)
            bb_lower = current_price * (1 - volatility * 2)
            bb_position = 0.5  # 중간값으로 설정
            
            return {
                'rsi': rsi_estimate,
                'bb_upper': bb_upper,
                'bb_lower': bb_lower,
                'bb_position': bb_position,
                'signal_score': self._calculate_technical_score(rsi_estimate, bb_position)
            }
            
        except Exception as e:
            self.logger.error(f"기술적 지표 계산 오류: {e}")
            return {}
    
    def _calculate_technical_score(self, rsi: float, bb_position: float) -> int:
        """기술적 지표 점수 계산"""
        try:
            score = 0
            
            # RSI 기반 점수
            if rsi > 80:
                score -= 2  # 과매수
            elif rsi > 70:
                score -= 1
            elif rsi < 20:
                score += 2  # 과매도
            elif rsi < 30:
                score += 1
            
            # 볼린저 밴드 기반 점수
            if bb_position > 0.8:
                score -= 1  # 상단 근처
            elif bb_position < 0.2:
                score += 1  # 하단 근처
            
            return max(-3, min(3, score))
        except:
            return 0
    
    async def assess_risk_metrics(self, market_data: Dict) -> Dict:
        """리스크 메트릭 평가"""
        try:
            volatility = market_data.get('volatility', 0.02)
            volume_ratio = market_data.get('volume_ratio', 1)
            price_change = market_data.get('change_24h', 0)
            
            # 리스크 레벨 계산
            risk_level = "보통"
            risk_score = 0
            
            # 변동성 기반 리스크
            if volatility > 0.08:
                risk_level = "매우 높음"
                risk_score = 4
            elif volatility > 0.05:
                risk_level = "높음"
                risk_score = 3
            elif volatility > 0.03:
                risk_level = "보통"
                risk_score = 2
            else:
                risk_level = "낮음"
                risk_score = 1
            
            # 급격한 가격 변동 리스크
            if abs(price_change) > 0.1:
                risk_score += 2
            elif abs(price_change) > 0.05:
                risk_score += 1
            
            return {
                'volatility': volatility,
                'risk_level': risk_level,
                'risk_score': min(5, risk_score),
                'recommendation': self._get_risk_recommendation(risk_score)
            }
            
        except Exception as e:
            self.logger.error(f"리스크 메트릭 계산 오류: {e}")
            return {}
    
    def _get_risk_recommendation(self, risk_score: int) -> str:
        """리스크 기반 권장사항"""
        try:
            if risk_score >= 5:
                return "매우 위험 - 포지션 크기 최소화"
            elif risk_score >= 4:
                return "고위험 - 신중한 진입"
            elif risk_score >= 3:
                return "중위험 - 적정 포지션"
            elif risk_score >= 2:
                return "저위험 - 일반적 거래"
            else:
                return "매우 안전 - 적극적 거래 가능"
        except:
            return "리스크 평가 불가"
    
    def generate_composite_signal(self, indicators: Dict) -> Dict:
        """종합 신호 생성"""
        try:
            total_score = 0
            indicator_count = 0
            
            # 각 지표별 점수 합산
            for indicator_name, indicator_data in indicators.items():
                if isinstance(indicator_data, dict) and 'signal_score' in indicator_data:
                    score = indicator_data['signal_score']
                    if isinstance(score, (int, float)):
                        total_score += score
                        indicator_count += 1
            
            # 평균 점수 계산
            avg_score = total_score / indicator_count if indicator_count > 0 else 0
            
            # 신호 해석
            if avg_score >= 3:
                signal = "강한 매수"
                confidence = "높음"
            elif avg_score >= 1:
                signal = "매수"
                confidence = "보통"
            elif avg_score <= -3:
                signal = "강한 매도"
                confidence = "높음"
            elif avg_score <= -1:
                signal = "매도"
                confidence = "보통"
            else:
                signal = "중립"
                confidence = "낮음"
            
            return {
                'total_score': total_score,
                'avg_score': avg_score,
                'signal': signal,
                'confidence': confidence,
                'indicator_count': indicator_count
            }
            
        except Exception as e:
            self.logger.error(f"종합 신호 생성 오류: {e}")
            return {
                'total_score': 0,
                'avg_score': 0,
                'signal': '분석 불가',
                'confidence': '낮음',
                'indicator_count': 0
            }
