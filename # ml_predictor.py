# ml_predictor.py
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import numpy as np
from collections import defaultdict
import hashlib
import asyncio

logger = logging.getLogger(__name__)

class MLPredictor:
    """머신러닝 기반 비트코인 가격 예측 시스템"""
    
    def __init__(self, data_file: str = "ml_predictions.json"):
        self.data_file = data_file
        self.predictions_history = []
        self.accuracy_scores = defaultdict(list)
        self.feature_weights = self._initialize_weights()
        self.load_data()
        
        # 예측 정확도 추적
        self.total_predictions = 0
        self.correct_predictions = 0
        self.direction_accuracy = 0.5  # 초기값 50%
        self.magnitude_accuracy = 0.5  # 초기값 50%
        
        # 뉴스 카테고리별 영향력 학습
        self.news_impact_history = defaultdict(list)
        
        # 실시간 학습을 위한 버퍼
        self.pending_predictions = []
        
        logger.info(f"ML 예측기 초기화 완료 - 과거 예측: {len(self.predictions_history)}개")
    
    def _initialize_weights(self) -> Dict[str, float]:
        """초기 가중치 설정"""
        return {
            # 뉴스 타입별 가중치
            'etf_approval': 1.5,
            'etf_rejection': -1.5,
            'company_purchase': 0.8,
            'regulation_positive': 0.6,
            'regulation_negative': -1.2,
            'hack_security': -2.0,
            'adoption_news': 0.7,
            'market_dominance': 0.1,  # 낮은 가중치
            'whale_movement': 0.4,
            'funding_rate': 0.3,
            
            # 시장 상황별 가중치
            'bull_market': 1.2,
            'bear_market': 0.8,
            'high_volatility': 1.5,
            'low_volatility': 0.7,
            
            # 시간대별 가중치
            'asia_session': 0.9,
            'europe_session': 1.0,
            'us_session': 1.1,
            'weekend': 0.8,
        }
    
    def load_data(self):
        """저장된 데이터 로드"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.predictions_history = data.get('predictions', [])
                    self.feature_weights = data.get('weights', self.feature_weights)
                    self.news_impact_history = defaultdict(list, data.get('news_impacts', {}))
                    
                    # 정확도 계산
                    self._calculate_accuracy()
                    logger.info(f"데이터 로드 완료 - 예측 정확도: {self.direction_accuracy:.1%}")
        except Exception as e:
            logger.error(f"데이터 로드 실패: {e}")
    
    def save_data(self):
        """데이터 저장"""
        try:
            data = {
                'predictions': self.predictions_history[-1000:],  # 최근 1000개만 저장
                'weights': self.feature_weights,
                'news_impacts': dict(self.news_impact_history),
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"데이터 저장 실패: {e}")
    
    async def predict_impact(self, event: Dict, market_data: Dict) -> Dict:
        """이벤트의 영향 예측 - 머신러닝 기반"""
        try:
            # 특징 추출
            features = self._extract_features(event, market_data)
            
            # 예측 수행
            direction, magnitude, confidence = self._make_prediction(features)
            
            # 상세 분석 생성
            detailed_analysis = self._generate_detailed_analysis(event, features, direction, magnitude)
            
            # 예측 기록
            prediction_id = self._record_prediction(event, features, direction, magnitude, confidence)
            
            return {
                'prediction_id': prediction_id,
                'direction': direction,  # 'up', 'down', 'neutral'
                'magnitude': magnitude,  # 예상 변동률
                'confidence': confidence,  # 신뢰도 0-1
                'timeframe': self._estimate_timeframe(features),
                'detailed_analysis': detailed_analysis,
                'market_influence': self._calculate_market_influence(features),
                'risk_level': self._assess_risk_level(features, magnitude),
                'recommendation': self._generate_recommendation(direction, magnitude, confidence)
            }
            
        except Exception as e:
            logger.error(f"예측 실패: {e}")
            return self._get_fallback_prediction(event)
    
    def _extract_features(self, event: Dict, market_data: Dict) -> Dict:
        """이벤트와 시장 데이터에서 특징 추출"""
        features = {
            'event_type': event.get('type', 'unknown'),
            'severity': event.get('severity', 'medium'),
            'news_category': self._categorize_news(event),
            'market_trend': market_data.get('trend', 'neutral'),
            'volatility': market_data.get('volatility', 0.02),
            'volume_ratio': market_data.get('volume_ratio', 1.0),
            'rsi': market_data.get('rsi', 50),
            'fear_greed_index': market_data.get('fear_greed', 50),
            'btc_dominance': market_data.get('btc_dominance', 50),
            'time_of_day': datetime.now().hour,
            'day_of_week': datetime.now().weekday(),
            'similar_events_impact': self._get_similar_events_impact(event)
        }
        
        # 뉴스 내용 분석
        if event.get('type') == 'critical_news':
            content = (event.get('title', '') + ' ' + event.get('description', '')).lower()
            features.update({
                'has_price_target': any(word in content for word in ['$', 'dollar', 'price', '달러']),
                'has_timeline': any(word in content for word in ['soon', 'tomorrow', 'week', 'month', '곧', '내일']),
                'sentiment_score': self._calculate_sentiment_score(content),
                'entity_importance': self._calculate_entity_importance(event)
            })
        
        return features
    
    def _categorize_news(self, event: Dict) -> str:
        """뉴스를 카테고리로 분류"""
        content = (event.get('title', '') + ' ' + event.get('description', '')).lower()
        
        if any(word in content for word in ['etf', 'approved', '승인']):
            return 'etf_approval'
        elif any(word in content for word in ['etf', 'rejected', 'denied', '거부']):
            return 'etf_rejection'
        elif any(word in content for word in ['bought', 'purchased', 'buys', '구매', '매입']):
            return 'company_purchase'
        elif any(word in content for word in ['regulation', 'sec', 'government', '규제', '정부']):
            if any(word in content for word in ['positive', 'support', '긍정', '지원']):
                return 'regulation_positive'
            else:
                return 'regulation_negative'
        elif any(word in content for word in ['hack', 'breach', 'stolen', '해킹', '도난']):
            return 'hack_security'
        elif any(word in content for word in ['adoption', 'accept', 'integrate', '채택', '도입']):
            return 'adoption_news'
        elif any(word in content for word in ['dominance', '우세', '점유율']):
            return 'market_dominance'
        elif any(word in content for word in ['whale', 'large transfer', '고래', '대량']):
            return 'whale_movement'
        else:
            return 'general_news'
    
    def _make_prediction(self, features: Dict) -> Tuple[str, float, float]:
        """특징을 기반으로 예측 수행"""
        # 기본 점수 계산
        base_score = 0.0
        
        # 뉴스 카테고리 가중치 적용
        news_category = features.get('news_category', 'general_news')
        category_weight = self.feature_weights.get(news_category, 0.3)
        base_score += category_weight
        
        # 시장 상황 고려
        if features.get('market_trend') == 'bullish':
            base_score *= self.feature_weights.get('bull_market', 1.2)
        elif features.get('market_trend') == 'bearish':
            base_score *= self.feature_weights.get('bear_market', 0.8)
        
        # 변동성 고려
        volatility = features.get('volatility', 0.02)
        if volatility > 0.03:
            base_score *= self.feature_weights.get('high_volatility', 1.5)
        else:
            base_score *= self.feature_weights.get('low_volatility', 0.7)
        
        # 시간대 가중치
        hour = features.get('time_of_day', 12)
        if 0 <= hour < 8:  # 아시아 세션
            base_score *= self.feature_weights.get('asia_session', 0.9)
        elif 8 <= hour < 16:  # 유럽 세션
            base_score *= self.feature_weights.get('europe_session', 1.0)
        else:  # 미국 세션
            base_score *= self.feature_weights.get('us_session', 1.1)
        
        # 유사 이벤트 영향 반영
        similar_impact = features.get('similar_events_impact', 0)
        base_score = 0.7 * base_score + 0.3 * similar_impact
        
        # 방향과 크기 결정
        if base_score > 0.1:
            direction = 'up'
            magnitude = min(abs(base_score) * 2, 5.0)  # 최대 5%
        elif base_score < -0.1:
            direction = 'down'
            magnitude = min(abs(base_score) * 2, 5.0)  # 최대 -5%
        else:
            direction = 'neutral'
            magnitude = abs(base_score) * 0.5  # 중립일 때는 작은 변동
        
        # 신뢰도 계산
        confidence = self._calculate_confidence(features, base_score)
        
        return direction, magnitude, confidence
    
    def _calculate_confidence(self, features: Dict, score: float) -> float:
        """예측 신뢰도 계산"""
        confidence = 0.5  # 기본값
        
        # 과거 정확도 반영
        confidence += self.direction_accuracy * 0.2
        
        # 유사 이벤트 수 고려
        similar_count = len(self._get_similar_events(features))
        if similar_count > 10:
            confidence += 0.2
        elif similar_count > 5:
            confidence += 0.1
        
        # 뉴스 카테고리별 정확도 반영
        category = features.get('news_category')
        if category in self.accuracy_scores:
            category_accuracy = np.mean(self.accuracy_scores[category][-10:]) if self.accuracy_scores[category] else 0.5
            confidence += category_accuracy * 0.1
        
        # 시장 상황 명확성
        if features.get('market_trend') in ['bullish', 'bearish']:
            confidence += 0.1
        
        return min(confidence, 0.95)  # 최대 95%
    
    def _generate_detailed_analysis(self, event: Dict, features: Dict, direction: str, magnitude: float) -> str:
        """상세한 분석 생성"""
        analysis_parts = []
        
        # 1. 뉴스 핵심 내용 상세 요약
        if event.get('type') == 'critical_news':
            title = event.get('title', '')
            description = event.get('description', '')
            
            # 핵심 정보 추출
            key_facts = self._extract_key_facts(title, description)
            if key_facts:
                analysis_parts.append(f"<b>핵심 정보:</b>\n{key_facts}")
        
        # 2. 과거 유사 사례 분석
        similar_events = self._get_similar_events(features)
        if similar_events:
            past_impacts = [e.get('actual_change', 0) for e in similar_events[-5:]]
            avg_impact = np.mean(past_impacts) if past_impacts else 0
            
            analysis_parts.append(
                f"<b>과거 유사 사례:</b>\n"
                f"• 유사 이벤트 {len(similar_events)}건 발견\n"
                f"• 평균 변동률: {avg_impact:+.2f}%\n"
                f"• 예측 정확도: {self._get_category_accuracy(features.get('news_category')):.1%}"
            )
        
        # 3. 시장 상황 분석
        market_context = self._analyze_market_context(features)
        analysis_parts.append(f"<b>시장 상황:</b>\n{market_context}")
        
        # 4. 영향 메커니즘 설명
        impact_mechanism = self._explain_impact_mechanism(event, features, direction, magnitude)
        analysis_parts.append(f"<b>영향 메커니즘:</b>\n{impact_mechanism}")
        
        # 5. 리스크 요인
        risk_factors = self._identify_risk_factors(features)
        if risk_factors:
            analysis_parts.append(f"<b>리스크 요인:</b>\n{risk_factors}")
        
        return "\n\n".join(analysis_parts)
    
    def _extract_key_facts(self, title: str, description: str) -> str:
        """뉴스에서 핵심 사실 추출"""
        facts = []
        content = (title + ' ' + description).lower()
        
        # 금액 정보 추출
        import re
        money_pattern = r'\$?([\d,]+\.?\d*)\s*(billion|million|만|억)?'
        money_matches = re.findall(money_pattern, content)
        if money_matches:
            for match in money_matches[:2]:  # 최대 2개
                amount, unit = match
                facts.append(f"• 금액: ${amount} {unit if unit else ''}")
        
        # 회사/기관 추출
        companies = ['tesla', 'microstrategy', 'square', 'paypal', 'gamestop', 'trump', 'sec', 'fed']
        mentioned_companies = [c for c in companies if c in content]
        if mentioned_companies:
            facts.append(f"• 관련 주체: {', '.join(mentioned_companies[:3]).title()}")
        
        # 시간 정보 추출
        time_keywords = ['today', 'yesterday', 'tomorrow', 'this week', 'next month', '오늘', '어제', '내일']
        time_info = [t for t in time_keywords if t in content]
        if time_info:
            facts.append(f"• 시기: {time_info[0]}")
        
        # 행동/결정 추출
        action_keywords = {
            'approved': '승인',
            'rejected': '거부',
            'bought': '구매',
            'sold': '매도',
            'announced': '발표',
            'launched': '출시'
        }
        for eng, kor in action_keywords.items():
            if eng in content:
                facts.append(f"• 행동: {kor}")
                break
        
        return '\n'.join(facts) if facts else "• 구체적인 세부사항 없음"
    
    def _analyze_market_context(self, features: Dict) -> str:
        """시장 상황 분석"""
        context_parts = []
        
        # 트렌드
        trend = features.get('market_trend', 'neutral')
        trend_text = {'bullish': '상승세', 'bearish': '하락세', 'neutral': '횡보'}
        context_parts.append(f"• 현재 트렌드: {trend_text.get(trend, '불명')}")
        
        # 변동성
        volatility = features.get('volatility', 0.02)
        vol_level = '높음' if volatility > 0.03 else '보통' if volatility > 0.015 else '낮음'
        context_parts.append(f"• 변동성: {vol_level} ({volatility*100:.1f}%)")
        
        # RSI
        rsi = features.get('rsi', 50)
        if rsi > 70:
            context_parts.append(f"• RSI: {rsi} (과매수)")
        elif rsi < 30:
            context_parts.append(f"• RSI: {rsi} (과매도)")
        else:
            context_parts.append(f"• RSI: {rsi} (중립)")
        
        # 공포탐욕지수
        fear_greed = features.get('fear_greed_index', 50)
        if fear_greed > 75:
            context_parts.append(f"• 시장 심리: 극도의 탐욕 ({fear_greed})")
        elif fear_greed > 55:
            context_parts.append(f"• 시장 심리: 탐욕 ({fear_greed})")
        elif fear_greed < 25:
            context_parts.append(f"• 시장 심리: 극도의 공포 ({fear_greed})")
        elif fear_greed < 45:
            context_parts.append(f"• 시장 심리: 공포 ({fear_greed})")
        else:
            context_parts.append(f"• 시장 심리: 중립 ({fear_greed})")
        
        return '\n'.join(context_parts)
    
    def _explain_impact_mechanism(self, event: Dict, features: Dict, direction: str, magnitude: float) -> str:
        """영향 메커니즘 설명"""
        category = features.get('news_category', 'general_news')
        
        mechanisms = {
            'etf_approval': f"ETF 승인으로 기관 자금 유입 예상 → 수요 증가 → 가격 {magnitude:.1f}% 상승 압력",
            'etf_rejection': f"ETF 거부로 기관 진입 지연 → 실망 매도 → 가격 {magnitude:.1f}% 하락 압력",
            'company_purchase': f"기업 매수로 공급 감소 + 신뢰도 상승 → {magnitude:.1f}% 상승 가능",
            'regulation_positive': f"우호적 규제로 불확실성 감소 → 투자 심리 개선 → {magnitude:.1f}% 상승",
            'regulation_negative': f"규제 강화 우려 → 리스크 회피 → {magnitude:.1f}% 하락 압력",
            'hack_security': f"보안 사고로 신뢰 하락 → 패닉 매도 → {magnitude:.1f}% 급락 위험",
            'adoption_news': f"실사용 증가 → 장기 가치 상승 → 점진적 {magnitude:.1f}% 상승",
            'market_dominance': f"시장 점유율 변화 → 자금 흐름 조정 → 제한적 {magnitude:.1f}% 변동",
            'whale_movement': f"대량 거래 감지 → 단기 수급 변화 → {magnitude:.1f}% 변동 가능"
        }
        
        base_mechanism = mechanisms.get(category, f"시장 반응 → {magnitude:.1f}% 변동 예상")
        
        # 시장 상황에 따른 추가 설명
        if features.get('market_trend') == 'bullish' and direction == 'up':
            base_mechanism += "\n• 상승 트렌드와 동조하여 영향 증폭 가능"
        elif features.get('market_trend') == 'bearish' and direction == 'down':
            base_mechanism += "\n• 하락 트렌드와 맞물려 낙폭 확대 위험"
        
        return base_mechanism
    
    def _identify_risk_factors(self, features: Dict) -> str:
        """리스크 요인 식별"""
        risks = []
        
        # 과열/과냉 리스크
        rsi = features.get('rsi', 50)
        if rsi > 70:
            risks.append("• 과매수 구간 - 조정 리스크 높음")
        elif rsi < 30:
            risks.append("• 과매도 구간 - 추가 하락 가능")
        
        # 변동성 리스크
        if features.get('volatility', 0.02) > 0.03:
            risks.append("• 높은 변동성 - 예측 신뢰도 하락")
        
        # 시간대 리스크
        if features.get('day_of_week') in [5, 6]:  # 주말
            risks.append("• 주말 - 유동성 부족으로 급변동 가능")
        
        # 반대 포지션 리스크
        fear_greed = features.get('fear_greed_index', 50)
        if fear_greed > 80 or fear_greed < 20:
            risks.append("• 극단적 시장 심리 - 반전 가능성")
        
        return '\n'.join(risks) if risks else "• 특별한 리스크 요인 없음"
    
    def _estimate_timeframe(self, features: Dict) -> str:
        """영향이 나타날 시간대 추정"""
        category = features.get('news_category', 'general_news')
        
        # 카테고리별 기본 시간대
        timeframes = {
            'etf_approval': "즉시~2시간 (초기 반응), 1-3일 (지속 효과)",
            'etf_rejection': "즉시~1시간 (급락), 4-8시간 (회복)",
            'company_purchase': "1-4시간 (인지 확산), 1-2일 (추가 상승)",
            'regulation_positive': "2-6시간 (점진적 반영)",
            'regulation_negative': "즉시~2시간 (패닉), 1일 (안정화)",
            'hack_security': "즉시 반응, 1-3일 회복",
            'adoption_news': "6-24시간 (느린 반영)",
            'market_dominance': "이미 반영 중, 추가 영향 미미",
            'whale_movement': "30분~2시간 (단기 영향)"
        }
        
        base_timeframe = timeframes.get(category, "2-6시간")
        
        # 시장 상황에 따른 조정
        if features.get('volatility', 0.02) > 0.03:
            base_timeframe = "더 빠른 반응 예상 - " + base_timeframe
        
        return base_timeframe
    
    def _calculate_market_influence(self, features: Dict) -> float:
        """시장 영향력 계산 (0-100%)"""
        influence = 10.0  # 기본값 10%
        
        category = features.get('news_category', 'general_news')
        
        # 카테고리별 기본 영향력
        category_influence = {
            'etf_approval': 40,
            'etf_rejection': 35,
            'company_purchase': 20,
            'regulation_positive': 25,
            'regulation_negative': 30,
            'hack_security': 25,
            'adoption_news': 15,
            'market_dominance': 5,
            'whale_movement': 10
        }
        
        influence = category_influence.get(category, 10)
        
        # 시장 상황에 따른 조정
        if features.get('volatility', 0.02) > 0.03:
            influence *= 1.2
        
        # 심리 지표에 따른 조정
        fear_greed = features.get('fear_greed_index', 50)
        if fear_greed > 80 or fear_greed < 20:
            influence *= 0.8  # 극단적일 때는 영향력 감소
        
        return min(influence, 60)  # 최대 60%
    
    def _assess_risk_level(self, features: Dict, magnitude: float) -> str:
        """리스크 수준 평가"""
        risk_score = 0
        
        # 변동 크기에 따른 리스크
        if magnitude > 3:
            risk_score += 3
        elif magnitude > 2:
            risk_score += 2
        elif magnitude > 1:
            risk_score += 1
        
        # 변동성에 따른 리스크
        if features.get('volatility', 0.02) > 0.03:
            risk_score += 2
        
        # RSI 극단값
        rsi = features.get('rsi', 50)
        if rsi > 80 or rsi < 20:
            risk_score += 2
        
        # 리스크 레벨 결정
        if risk_score >= 5:
            return "매우 높음"
        elif risk_score >= 3:
            return "높음"
        elif risk_score >= 2:
            return "중간"
        else:
            return "낮음"
    
    def _generate_recommendation(self, direction: str, magnitude: float, confidence: float) -> str:
        """투자 추천 생성"""
        if confidence < 0.6:
            return "관망 (신뢰도 부족)"
        
        if direction == 'up':
            if magnitude > 2 and confidence > 0.8:
                return "적극 롱 (높은 상승 예상)"
            elif magnitude > 1:
                return "소량 롱 (점진적 상승 예상)"
            else:
                return "관망 (미미한 상승)"
        elif direction == 'down':
            if magnitude > 2 and confidence > 0.8:
                return "적극 숏 또는 매도 (급락 예상)"
            elif magnitude > 1:
                return "일부 매도 또는 헤지"
            else:
                return "홀딩 (일시적 조정)"
        else:
            return "관망 (방향성 불명확)"
    
    def _get_similar_events(self, features: Dict) -> List[Dict]:
        """유사한 과거 이벤트 찾기"""
        similar_events = []
        category = features.get('news_category')
        
        for prediction in self.predictions_history:
            if prediction.get('features', {}).get('news_category') == category:
                # 시장 상황도 유사한지 체크
                past_trend = prediction.get('features', {}).get('market_trend')
                if past_trend == features.get('market_trend'):
                    similar_events.append(prediction)
        
        return similar_events
    
    def _get_similar_events_impact(self, event: Dict) -> float:
        """유사 이벤트들의 평균 영향"""
        similar_events = self._get_similar_events({'news_category': self._categorize_news(event)})
        
        if not similar_events:
            return 0.0
        
        impacts = [e.get('actual_change', 0) for e in similar_events if 'actual_change' in e]
        return np.mean(impacts) if impacts else 0.0
    
    def _calculate_sentiment_score(self, content: str) -> float:
        """감정 점수 계산"""
        positive_words = ['positive', 'bullish', 'approval', 'growth', 'surge', 'rally', '상승', '호재', '긍정']
        negative_words = ['negative', 'bearish', 'rejection', 'crash', 'plunge', 'fall', '하락', '악재', '부정']
        
        positive_count = sum(1 for word in positive_words if word in content)
        negative_count = sum(1 for word in negative_words if word in content)
        
        if positive_count + negative_count == 0:
            return 0.0
        
        return (positive_count - negative_count) / (positive_count + negative_count)
    
    def _calculate_entity_importance(self, event: Dict) -> float:
        """언급된 엔티티의 중요도"""
        content = (event.get('title', '') + ' ' + event.get('description', '')).lower()
        
        high_importance = ['tesla', 'microstrategy', 'sec', 'fed', 'trump', 'biden']
        medium_importance = ['square', 'paypal', 'visa', 'mastercard']
        
        importance_score = 0.5  # 기본값
        
        for entity in high_importance:
            if entity in content:
                importance_score = max(importance_score, 1.0)
        
        for entity in medium_importance:
            if entity in content:
                importance_score = max(importance_score, 0.75)
        
        return importance_score
    
    def _get_category_accuracy(self, category: str) -> float:
        """특정 카테고리의 예측 정확도"""
        if category not in self.accuracy_scores or not self.accuracy_scores[category]:
            return 0.5  # 기본값 50%
        
        recent_scores = self.accuracy_scores[category][-20:]  # 최근 20개
        return np.mean(recent_scores)
    
    def _record_prediction(self, event: Dict, features: Dict, direction: str, magnitude: float, confidence: float) -> str:
        """예측 기록"""
        prediction_id = hashlib.md5(f"{datetime.now().isoformat()}{event.get('title', '')}".encode()).hexdigest()[:12]
        
        prediction_record = {
            'id': prediction_id,
            'timestamp': datetime.now().isoformat(),
            'event': {
                'title': event.get('title', ''),
                'type': event.get('type', ''),
                'severity': event.get('severity', '')
            },
            'features': features,
            'prediction': {
                'direction': direction,
                'magnitude': magnitude,
                'confidence': confidence
            },
            'status': 'pending'  # pending, verified, failed
        }
        
        self.predictions_history.append(prediction_record)
        self.pending_predictions.append(prediction_id)
        
        # 비동기로 저장
        asyncio.create_task(self._async_save())
        
        return prediction_id
    
    async def _async_save(self):
        """비동기 저장"""
        try:
            self.save_data()
        except Exception as e:
            logger.error(f"비동기 저장 실패: {e}")
    
    async def verify_prediction(self, prediction_id: str, actual_change: float) -> Dict:
        """예측 검증 및 학습"""
        try:
            # 예측 찾기
            prediction = None
            for p in self.predictions_history:
                if p['id'] == prediction_id:
                    prediction = p
                    break
            
            if not prediction:
                return {'error': 'Prediction not found'}
            
            # 실제 결과 기록
            prediction['actual_change'] = actual_change
            prediction['status'] = 'verified'
            prediction['verified_at'] = datetime.now().isoformat()
            
            # 정확도 계산
            predicted_direction = prediction['prediction']['direction']
            predicted_magnitude = prediction['prediction']['magnitude']
            
            # 방향 정확도
            actual_direction = 'up' if actual_change > 0.1 else 'down' if actual_change < -0.1 else 'neutral'
            direction_correct = predicted_direction == actual_direction
            
            # 크기 정확도 (오차율)
            magnitude_error = abs(predicted_magnitude - abs(actual_change))
            magnitude_accuracy = max(0, 1 - magnitude_error / max(predicted_magnitude, abs(actual_change)))
            
            # 카테고리별 정확도 업데이트
            category = prediction['features'].get('news_category', 'general_news')
            self.accuracy_scores[category].append(1.0 if direction_correct else 0.0)
            
            # 가중치 업데이트 (학습)
            await self._update_weights(prediction, actual_change, direction_correct, magnitude_accuracy)
            
            # 전체 정확도 업데이트
            self._calculate_accuracy()
            
            # 저장
            await self._async_save()
            
            return {
                'prediction_id': prediction_id,
                'direction_correct': direction_correct,
                'magnitude_accuracy': magnitude_accuracy,
                'predicted': predicted_magnitude,
                'actual': actual_change,
                'new_accuracy': self.direction_accuracy
            }
            
        except Exception as e:
            logger.error(f"예측 검증 실패: {e}")
            return {'error': str(e)}
    
    async def _update_weights(self, prediction: Dict, actual_change: float, direction_correct: bool, magnitude_accuracy: float):
        """가중치 업데이트 (머신러닝)"""
        features = prediction['features']
        category = features.get('news_category', 'general_news')
        
        # 학습률
        learning_rate = 0.1
        
        # 방향이 맞았으면 가중치 증가, 틀렸으면 감소
        if category in self.feature_weights:
            if direction_correct:
                self.feature_weights[category] *= (1 + learning_rate * magnitude_accuracy)
            else:
                self.feature_weights[category] *= (1 - learning_rate * 0.5)
            
            # 가중치 범위 제한
            self.feature_weights[category] = max(-3, min(3, self.feature_weights[category]))
        
        # 시장 상황별 가중치도 업데이트
        market_trend = features.get('market_trend')
        if market_trend == 'bullish':
            key = 'bull_market'
        elif market_trend == 'bearish':
            key = 'bear_market'
        else:
            key = None
        
        if key and key in self.feature_weights:
            if magnitude_accuracy > 0.7:
                self.feature_weights[key] *= 1.05
            elif magnitude_accuracy < 0.3:
                self.feature_weights[key] *= 0.95
    
    def _calculate_accuracy(self):
        """전체 정확도 계산"""
        verified_predictions = [p for p in self.predictions_history if p.get('status') == 'verified']
        
        if not verified_predictions:
            return
        
        # 방향 정확도
        direction_correct_count = 0
        magnitude_errors = []
        
        for p in verified_predictions[-100:]:  # 최근 100개
            predicted = p['prediction']['direction']
            actual_change = p.get('actual_change', 0)
            actual_direction = 'up' if actual_change > 0.1 else 'down' if actual_change < -0.1 else 'neutral'
            
            if predicted == actual_direction:
                direction_correct_count += 1
            
            # 크기 오차
            predicted_magnitude = p['prediction']['magnitude']
            magnitude_errors.append(abs(predicted_magnitude - abs(actual_change)))
        
        self.direction_accuracy = direction_correct_count / len(verified_predictions[-100:])
        self.magnitude_accuracy = 1 - (np.mean(magnitude_errors) / 2) if magnitude_errors else 0.5
        
        self.total_predictions = len(self.predictions_history)
        self.correct_predictions = sum(1 for p in verified_predictions if p.get('direction_correct', False))
    
    def _get_fallback_prediction(self, event: Dict) -> Dict:
        """폴백 예측 (ML 실패시)"""
        return {
            'prediction_id': 'fallback',
            'direction': 'neutral',
            'magnitude': 0.5,
            'confidence': 0.3,
            'timeframe': '2-6시간',
            'detailed_analysis': '예측 시스템 오류로 기본 분석 제공',
            'market_influence': 10,
            'risk_level': '중간',
            'recommendation': '관망'
        }
    
    def get_stats(self) -> Dict:
        """통계 정보 반환"""
        return {
            'total_predictions': self.total_predictions,
            'verified_predictions': len([p for p in self.predictions_history if p.get('status') == 'verified']),
            'pending_predictions': len(self.pending_predictions),
            'direction_accuracy': f"{self.direction_accuracy:.1%}",
            'magnitude_accuracy': f"{self.magnitude_accuracy:.1%}",
            'category_accuracies': {
                cat: f"{self._get_category_accuracy(cat):.1%}"
                for cat in ['etf_approval', 'company_purchase', 'regulation_negative', 'hack_security']
            },
            'last_updated': datetime.now().isoformat()
        }
