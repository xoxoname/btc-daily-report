# ml_predictor.py
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import asyncio
import logging
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)

class MLPredictor:
    """머신러닝 기반 예측 시스템"""
    
    def __init__(self):
        self.predictions_file = 'ml_predictions.json'
        self.predictions = []
        self.verified_predictions = []
        
        # 카테고리별 가중치 (학습을 통해 조정됨)
        self.category_weights = {
            'etf_approval': 2.0,
            'company_purchase': 1.5,
            'regulatory_action': -1.5,
            'security_breach': -2.0,
            'funding_rate': 0.5,
            'security_improvement': 0.3,  # 새로운 카테고리
            'fraud_scam': -0.5  # 새로운 카테고리
        }
        
        # 시장 상황별 가중치
        self.market_condition_multipliers = {
            'bullish': 1.2,
            'bearish': 0.8,
            'neutral': 1.0
        }
        
        # 신뢰도 요소
        self.confidence_factors = {
            'source_reliability': {
                'Cointelegraph': 0.9,
                'CoinDesk': 0.9,
                'Bloomberg': 0.95,
                'Reuters': 0.95,
                'Reddit': 0.6,
                'Unknown': 0.5
            },
            'time_decay': 0.95,  # 시간이 지날수록 영향력 감소
            'market_volatility_impact': 1.5  # 변동성이 클수록 예측 불확실성 증가
        }
        
        # 성능 통계
        self.stats = {
            'total_predictions': 0,
            'verified_predictions': 0,
            'direction_accuracy': 0.0,
            'magnitude_accuracy': 0.0,
            'category_accuracy': defaultdict(float),
            'category_count': defaultdict(int)
        }
        
        # 기존 예측 데이터 로드
        self.load_predictions()
        
        # 초기 정확도 계산
        self.calculate_accuracy()
        
        logger.info(f"ML 예측기 초기화 - 기존 예측: {len(self.predictions)}개, 검증됨: {len(self.verified_predictions)}개")
    
    def load_predictions(self):
        """저장된 예측 데이터 로드"""
        try:
            if os.path.exists(self.predictions_file):
                with open(self.predictions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.predictions = data.get('predictions', [])
                    self.verified_predictions = data.get('verified_predictions', [])
                    
                    # 저장된 가중치 로드
                    if 'category_weights' in data:
                        self.category_weights.update(data['category_weights'])
                    
                    # 통계 로드
                    if 'stats' in data:
                        self.stats.update(data['stats'])
                        # defaultdict 복원
                        self.stats['category_accuracy'] = defaultdict(float, self.stats.get('category_accuracy', {}))
                        self.stats['category_count'] = defaultdict(int, self.stats.get('category_count', {}))
                    
                logger.info("예측 데이터 로드 완료")
        except Exception as e:
            logger.error(f"예측 데이터 로드 실패: {e}")
    
    def save_predictions(self):
        """예측 데이터 저장"""
        try:
            data = {
                'predictions': self.predictions[-1000:],  # 최근 1000개만 저장
                'verified_predictions': self.verified_predictions[-500:],  # 최근 500개만 저장
                'category_weights': self.category_weights,
                'stats': {
                    'total_predictions': self.stats['total_predictions'],
                    'verified_predictions': self.stats['verified_predictions'],
                    'direction_accuracy': self.stats['direction_accuracy'],
                    'magnitude_accuracy': self.stats['magnitude_accuracy'],
                    'category_accuracy': dict(self.stats['category_accuracy']),
                    'category_count': dict(self.stats['category_count'])
                },
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.predictions_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.info("예측 데이터 저장 완료")
        except Exception as e:
            logger.error(f"예측 데이터 저장 실패: {e}")
    
    def categorize_event(self, event: Dict) -> str:
        """이벤트를 카테고리로 분류"""
        title = event.get('title', '').lower()
        description = event.get('description', '').lower()
        content = title + ' ' + description
        
        # 카테고리 매핑
        if any(word in content for word in ['etf', 'approval', 'approved']):
            return 'etf_approval'
        elif any(word in content for word in ['bought', 'purchased', 'buys', 'acquisition']):
            return 'company_purchase'
        elif any(word in content for word in ['ban', 'regulation', 'restrict', 'lawsuit']):
            return 'regulatory_action'
        elif any(word in content for word in ['hack', 'breach', 'stolen']):
            if 'decrease' in content or 'down' in content:
                return 'security_improvement'
            else:
                return 'security_breach'
        elif any(word in content for word in ['funding rate', 'funding']):
            return 'funding_rate'
        elif any(word in content for word in ['scam', 'fraud']):
            return 'fraud_scam'
        else:
            return 'other'
    
    async def predict_impact(self, event: Dict, market_data: Dict) -> Dict:
        """이벤트의 영향 예측"""
        try:
            # 이벤트 카테고리 분류
            category = self.categorize_event(event)
            
            # 기본 영향력 계산
            base_impact = self.category_weights.get(category, 0.1)
            
            # 시장 상황 반영
            market_trend = market_data.get('trend', 'neutral')
            market_multiplier = self.market_condition_multipliers.get(market_trend, 1.0)
            
            # 변동성 반영
            volatility = market_data.get('volatility', 0.02)
            volatility_factor = 1 + (volatility - 0.02) * 10  # 변동성이 높을수록 영향 증가
            
            # 최종 예상 변동률
            magnitude = base_impact * market_multiplier * volatility_factor
            
            # 방향 결정
            direction = 'up' if magnitude > 0 else 'down' if magnitude < 0 else 'neutral'
            magnitude = abs(magnitude)
            
            # 신뢰도 계산
            source = event.get('source', 'Unknown')
            source_reliability = self.confidence_factors['source_reliability'].get(source, 0.5)
            
            # 유사 과거 사례 검색
            similar_cases = self.find_similar_cases(event, category)
            
            # 신뢰도 종합
            confidence = source_reliability
            if similar_cases:
                # 과거 사례의 정확도를 신뢰도에 반영
                avg_accuracy = np.mean([case.get('accuracy', 50) for case in similar_cases[:5]]) / 100
                confidence = (confidence + avg_accuracy) / 2
            
            # 시간대 예측
            timeframe = self.predict_timeframe(category, magnitude)
            
            # 리스크 수준 평가
            risk_level = self.assess_risk_level(magnitude, volatility, confidence)
            
            # 추천 생성
            recommendation = self.generate_recommendation(
                direction, magnitude, confidence, risk_level, market_data
            )
            
            # 상세 분석 생성
            detailed_analysis = await self.generate_detailed_analysis(
                event, category, similar_cases, market_data, magnitude, direction
            )
            
            # 시장 영향력 계산 (0-100%)
            market_influence = min(magnitude * 20, 100)  # 최대 100%
            
            prediction = {
                'event_id': event.get('id', datetime.now().isoformat()),
                'category': category,
                'direction': direction,
                'magnitude': round(magnitude, 2),
                'confidence': round(confidence, 2),
                'timeframe': timeframe,
                'risk_level': risk_level,
                'recommendation': recommendation,
                'similar_cases_count': len(similar_cases),
                'market_influence': round(market_influence, 1),
                'detailed_analysis': detailed_analysis,
                'timestamp': datetime.now().isoformat()
            }
            
            return prediction
            
        except Exception as e:
            logger.error(f"예측 생성 실패: {e}")
            # 폴백 예측
            return {
                'direction': 'neutral',
                'magnitude': 0.5,
                'confidence': 0.3,
                'timeframe': '불확실',
                'risk_level': '높음',
                'recommendation': '관망',
                'market_influence': 10,
                'detailed_analysis': '예측 생성 중 오류가 발생했습니다.'
            }
    
    def find_similar_cases(self, event: Dict, category: str) -> List[Dict]:
        """유사한 과거 사례 검색"""
        similar_cases = []
        
        event_keywords = set(event.get('title', '').lower().split())
        
        for verified in self.verified_predictions:
            if verified.get('category') == category:
                # 키워드 유사도 체크
                past_keywords = set(verified.get('event', {}).get('title', '').lower().split())
                
                if event_keywords and past_keywords:
                    similarity = len(event_keywords & past_keywords) / len(event_keywords | past_keywords)
                    
                    if similarity > 0.3:  # 30% 이상 유사
                        similar_cases.append({
                            'event': verified['event'],
                            'prediction': verified['prediction'],
                            'actual_change': verified['actual_change'],
                            'accuracy': verified.get('accuracy', 50),
                            'similarity': similarity
                        })
        
        # 유사도 순으로 정렬
        similar_cases.sort(key=lambda x: x['similarity'], reverse=True)
        
        return similar_cases[:10]  # 상위 10개만 반환
    
    def predict_timeframe(self, category: str, magnitude: float) -> str:
        """영향이 나타날 시간대 예측"""
        # 카테고리별 기본 시간대
        timeframes = {
            'etf_approval': '즉시~30분',
            'company_purchase': '1-2시간',
            'regulatory_action': '즉시~1시간',
            'security_breach': '즉시',
            'funding_rate': '4-8시간',
            'security_improvement': '2-4시간',
            'fraud_scam': '1-3시간',
            'other': '2-6시간'
        }
        
        base_timeframe = timeframes.get(category, '2-6시간')
        
        # 영향력이 클수록 더 빠르게 반응
        if magnitude > 3:
            return '즉시~30분'
        elif magnitude > 2:
            return '30분~1시간'
        elif magnitude > 1:
            return '1-2시간'
        else:
            return base_timeframe
    
    def assess_risk_level(self, magnitude: float, volatility: float, confidence: float) -> str:
        """리스크 수준 평가"""
        # 리스크 점수 계산
        risk_score = (magnitude * volatility) / confidence
        
        if risk_score > 3:
            return '매우 높음'
        elif risk_score > 2:
            return '높음'
        elif risk_score > 1:
            return '중간'
        elif risk_score > 0.5:
            return '낮음'
        else:
            return '매우 낮음'
    
    def generate_recommendation(self, direction: str, magnitude: float, 
                              confidence: float, risk_level: str, market_data: Dict) -> str:
        """투자 추천 생성"""
        rsi = market_data.get('rsi', 50)
        
        # 신뢰도가 낮으면 관망
        if confidence < 0.5:
            return '관망'
        
        # 리스크가 높으면 신중
        if risk_level in ['높음', '매우 높음']:
            if direction == 'up':
                return '소량 롱 (리스크 관리 필수)'
            elif direction == 'down':
                return '소량 숏 (리스크 관리 필수)'
            else:
                return '관망'
        
        # RSI 고려
        if direction == 'up':
            if rsi > 70:
                return '관망 (과매수 구간)'
            elif magnitude > 2:
                return '적극 롱'
            elif magnitude > 1:
                return '롱'
            else:
                return '소량 롱'
        elif direction == 'down':
            if rsi < 30:
                return '관망 (과매도 구간)'
            elif magnitude > 2:
                return '적극 숏'
            elif magnitude > 1:
                return '숏'
            else:
                return '소량 숏'
        else:
            return '관망'
    
    async def generate_detailed_analysis(self, event: Dict, category: str, 
                                       similar_cases: List[Dict], market_data: Dict,
                                       magnitude: float, direction: str) -> str:
        """상세 분석 생성"""
        analysis = ""
        
        # 핵심 정보
        analysis += "<b>핵심 정보:</b>\n"
        
        # 금액 정보 추출
        import re
        content = event.get('title', '') + ' ' + event.get('description', '')
        money_match = re.search(r'\$?([\d,]+(?:\.\d+)?)\s*(million|billion)', content, re.IGNORECASE)
        if money_match:
            amount = money_match.group(1)
            unit = money_match.group(2)
            analysis += f"• 금액: ${amount} {unit}\n"
        
        # 관련 주체
        entities = []
        important_entities = ['Tesla', 'MicroStrategy', 'GameStop', 'Trump', 'SEC', 'Fed']
        for entity in important_entities:
            if entity.lower() in content.lower():
                entities.append(entity)
        
        if entities:
            analysis += f"• 관련 주체: {', '.join(entities)}\n"
        
        # 행동/결정
        if 'bought' in content.lower() or 'purchase' in content.lower():
            analysis += "• 행동: 구매\n"
        elif 'approved' in content.lower():
            analysis += "• 행동: 승인\n"
        elif 'rejected' in content.lower():
            analysis += "• 행동: 거부\n"
        
        # 과거 유사 사례
        if similar_cases:
            analysis += f"\n<b>과거 유사 사례:</b>\n"
            analysis += f"• 유사 이벤트 {len(similar_cases)}건 발견\n"
            
            # 평균 변동률 계산
            actual_changes = [case['actual_change'] for case in similar_cases[:5]]
            if actual_changes:
                avg_change = np.mean(actual_changes)
                analysis += f"• 평균 변동률: {avg_change:+.1f}%\n"
            
            # 예측 정확도
            accuracies = [case.get('accuracy', 50) for case in similar_cases[:5]]
            if accuracies:
                avg_accuracy = np.mean(accuracies)
                analysis += f"• 예측 정확도: {avg_accuracy:.1f}%\n"
        
        # 시장 상황
        analysis += f"\n<b>시장 상황:</b>\n"
        analysis += f"• 현재 트렌드: {'상승세' if market_data['trend'] == 'bullish' else '하락세' if market_data['trend'] == 'bearish' else '중립'}\n"
        analysis += f"• 변동성: {'높음' if market_data['volatility'] > 0.03 else '보통' if market_data['volatility'] > 0.015 else '낮음'} ({market_data['volatility']*100:.1f}%)\n"
        analysis += f"• RSI: {market_data['rsi']} ({'과매수' if market_data['rsi'] > 70 else '과매도' if market_data['rsi'] < 30 else '중립'})\n"
        analysis += f"• 시장 심리: {'탐욕' if market_data['fear_greed'] > 60 else '공포' if market_data['fear_greed'] < 40 else '중립'} ({market_data['fear_greed']})\n"
        
        # 영향 메커니즘
        analysis += f"\n<b>영향 메커니즘:</b>\n"
        
        if category == 'company_purchase':
            analysis += f"기업 매수로 공급 감소 + 신뢰도 상승 → {magnitude:.1f}% {'상승' if direction == 'up' else '하락'} 가능\n"
        elif category == 'regulatory_action':
            analysis += f"규제 불확실성 {'해소' if direction == 'up' else '증가'} → {magnitude:.1f}% {'상승' if direction == 'up' else '하락'} 압력\n"
        elif category == 'security_breach':
            analysis += f"보안 우려로 투자심리 위축 → {magnitude:.1f}% 하락 가능\n"
        elif category == 'fraud_scam':
            analysis += f"사기 피해로 단기 투자심리 위축 → {magnitude:.1f}% 조정 후 회복\n"
        else:
            analysis += f"{'긍정적' if direction == 'up' else '부정적'} 뉴스로 {magnitude:.1f}% {'상승' if direction == 'up' else '하락'} 예상\n"
        
        # 리스크 요인
        analysis += f"\n<b>리스크 요인:</b>\n"
        
        if market_data['rsi'] > 70 and direction == 'up':
            analysis += "• 과매수 구간 접근 주의\n"
        elif market_data['rsi'] < 30 and direction == 'down':
            analysis += "• 과매도 구간에서 반등 가능성\n"
        
        if market_data['volatility'] > 0.03:
            analysis += "• 높은 변동성으로 예측 불확실성 증가\n"
        
        return analysis
    
    async def record_prediction(self, event: Dict, prediction: Dict, initial_price: float):
        """예측 기록"""
        try:
            record = {
                'id': f"{datetime.now().isoformat()}_{event.get('type', 'unknown')}",
                'event': {
                    'title': event.get('title', ''),
                    'type': event.get('type', ''),
                    'severity': event.get('severity', ''),
                    'impact': event.get('impact', ''),
                    'timestamp': event.get('timestamp', datetime.now()).isoformat() if isinstance(event.get('timestamp'), datetime) else event.get('timestamp', '')
                },
                'prediction': prediction,
                'initial_price': initial_price,
                'recorded_at': datetime.now().isoformat(),
                'category': prediction.get('category', 'other')
            }
            
            self.predictions.append(record)
            self.stats['total_predictions'] += 1
            
            # 자동 저장 (10개마다)
            if len(self.predictions) % 10 == 0:
                self.save_predictions()
            
            logger.info(f"예측 기록 완료: {event.get('title', '')[:30]}... - 예상: {prediction['magnitude']:.1f}%")
            
        except Exception as e:
            logger.error(f"예측 기록 실패: {e}")
    
    async def verify_predictions(self, current_prices: Optional[Dict] = None) -> List[Dict]:
        """예측 검증 - 30분 경과한 예측들"""
        verifications = []
        now = datetime.now()
        
        for prediction_record in self.predictions:
            try:
                # 이미 검증된 예측은 스킵
                if any(v['id'] == prediction_record['id'] for v in self.verified_predictions):
                    continue
                
                # 예측 시간 확인
                recorded_at = datetime.fromisoformat(prediction_record['recorded_at'])
                time_elapsed = (now - recorded_at).total_seconds() / 60  # 분 단위
                
                # 30분 이상 경과한 예측만 검증
                if time_elapsed >= 30:
                    initial_price = prediction_record['initial_price']
                    
                    # 현재 가격 가져오기 (실제 구현시 API 호출)
                    if current_prices:
                        current_price = current_prices.get('BTCUSDT', initial_price)
                    else:
                        # 테스트용 랜덤 가격 (실제로는 API 호출)
                        import random
                        change = random.uniform(-3, 3)
                        current_price = initial_price * (1 + change / 100)
                    
                    # 실제 변동률 계산
                    actual_change = ((current_price - initial_price) / initial_price) * 100
                    predicted_change = prediction_record['prediction']['magnitude']
                    
                    if prediction_record['prediction']['direction'] == 'down':
                        predicted_change = -predicted_change
                    
                    # 방향 정확도
                    direction_correct = (
                        (actual_change > 0 and prediction_record['prediction']['direction'] == 'up') or
                        (actual_change < 0 and prediction_record['prediction']['direction'] == 'down') or
                        (abs(actual_change) < 0.1 and prediction_record['prediction']['direction'] == 'neutral')
                    )
                    
                    # 크기 정확도 (오차율 기반)
                    if abs(predicted_change) > 0:
                        magnitude_accuracy = max(0, 100 - abs((actual_change - predicted_change) / predicted_change * 100))
                    else:
                        magnitude_accuracy = 100 if abs(actual_change) < 0.1 else 0
                    
                    verification = {
                        'id': prediction_record['id'],
                        'event': prediction_record['event'],
                        'prediction': prediction_record['prediction'],
                        'initial_price': initial_price,
                        'current_price': current_price,
                        'predicted_change': predicted_change,
                        'actual_change': actual_change,
                        'direction_correct': direction_correct,
                        'accuracy': magnitude_accuracy,
                        'time_elapsed': time_elapsed,
                        'verified_at': now.isoformat(),
                        'category': prediction_record.get('category', 'other'),
                        'prediction_time': recorded_at.strftime('%Y-%m-%d %H:%M')
                    }
                    
                    # 검증 결과 저장
                    self.verified_predictions.append(verification)
                    verifications.append(verification)
                    
                    # 카테고리별 정확도 업데이트
                    category = prediction_record.get('category', 'other')
                    self.stats['category_accuracy'][category] = (
                        self.stats['category_accuracy'][category] * self.stats['category_count'][category] + magnitude_accuracy
                    ) / (self.stats['category_count'][category] + 1)
                    self.stats['category_count'][category] += 1
                    
                    # 카테고리 가중치 조정 (학습)
                    self.adjust_category_weight(category, direction_correct, magnitude_accuracy)
                    
                    logger.info(f"예측 검증 완료: {prediction_record['event']['title'][:30]}... - 정확도: {magnitude_accuracy:.1f}%")
            
            except Exception as e:
                logger.error(f"예측 검증 실패: {e}")
                continue
        
        # 통계 업데이트
        if verifications:
            self.stats['verified_predictions'] += len(verifications)
            self.calculate_accuracy()
            self.save_predictions()
        
        return verifications
    
    def adjust_category_weight(self, category: str, direction_correct: bool, accuracy: float):
        """카테고리 가중치 조정 (학습)"""
        if category not in self.category_weights:
            return
        
        # 학습률
        learning_rate = 0.1
        
        # 정확도에 따른 조정
        if direction_correct and accuracy > 70:
            # 잘 맞춘 경우 가중치 증가
            adjustment = learning_rate * (accuracy / 100)
        else:
            # 틀린 경우 가중치 감소
            adjustment = -learning_rate * (1 - accuracy / 100)
        
        # 가중치 업데이트
        old_weight = self.category_weights[category]
        self.category_weights[category] = max(-3, min(3, old_weight + adjustment))
        
        logger.debug(f"카테고리 가중치 조정: {category} {old_weight:.2f} → {self.category_weights[category]:.2f}")
    
    def calculate_accuracy(self):
        """전체 정확도 계산"""
        if not self.verified_predictions:
            return
        
        # 방향 정확도
        direction_correct_count = sum(1 for v in self.verified_predictions if v['direction_correct'])
        self.direction_accuracy = direction_correct_count / len(self.verified_predictions)
        
        # 크기 정확도
        magnitude_accuracies = [v['accuracy'] for v in self.verified_predictions]
        self.magnitude_accuracy = np.mean(magnitude_accuracies) if magnitude_accuracies else 0
        
        # 통계 업데이트
        self.stats['direction_accuracy'] = f"{self.direction_accuracy:.1%}"
        self.stats['magnitude_accuracy'] = f"{self.magnitude_accuracy:.1f}%"
    
    def get_stats(self) -> Dict:
        """통계 반환"""
        return {
            'total_predictions': self.stats['total_predictions'],
            'verified_predictions': self.stats['verified_predictions'],
            'direction_accuracy': self.stats['direction_accuracy'],
            'magnitude_accuracy': self.stats['magnitude_accuracy'],
            'category_accuracy': {
                'etf_approval': f"{self.stats['category_accuracy'].get('etf_approval', 0):.1f}%",
                'company_purchase': f"{self.stats['category_accuracy'].get('company_purchase', 0):.1f}%",
                'regulatory_action': f"{self.stats['category_accuracy'].get('regulatory_action', 0):.1f}%",
                'security_breach': f"{self.stats['category_accuracy'].get('security_breach', 0):.1f}%",
                'funding_rate': f"{self.stats['category_accuracy'].get('funding_rate', 0):.1f}%",
                'security_improvement': f"{self.stats['category_accuracy'].get('security_improvement', 0):.1f}%",
                'fraud_scam': f"{self.stats['category_accuracy'].get('fraud_scam', 0):.1f}%"
            }
        }
    
    @property
    def direction_accuracy(self) -> float:
        """방향 정확도 속성"""
        if isinstance(self.stats.get('direction_accuracy'), str):
            return float(self.stats['direction_accuracy'].rstrip('%')) / 100
        return self.stats.get('direction_accuracy', 0.0)
