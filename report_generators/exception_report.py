# report_generators/exception_report.py
from .base_generator import BaseReportGenerator
from typing import Dict
from datetime import datetime, timedelta
import pytz
import re
import sys
import os

# ML 예측기 임포트
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from ml_predictor import MLPredictor
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

class ExceptionReportGenerator(BaseReportGenerator):
    """예외 상황 리포트 전담 생성기 - 현실적 시장 반응 반영"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        
        # ML 예측기 초기화
        self.ml_predictor = None
        if ML_AVAILABLE:
            try:
                self.ml_predictor = MLPredictor()
                self.logger.info(f"ML 예측기 초기화 완료")
            except Exception as e:
                self.logger.error(f"ML 예측기 초기화 실패: {e}")
        
        # 뉴스 발표 시점 기록 저장소
        self.news_initial_data = {}  # 뉴스별 초기 데이터 저장
        
        # 현실적인 뉴스 반응 패턴 데이터 (실제 과거 데이터 기반)
        self.news_reaction_patterns = {
            'etf_approval': {
                'immediate': '+1.5~3%',
                'pattern': '즉시 급등 후 2-4시간 내 수익 실현',
                'duration': '12-24시간',
                'strategy': '발표 직후 진입, 과열 시 빠른 익절',
                'actual_impact': 'high',
                'typical_range': (1.5, 3.0)
            },
            'etf_rejection': {
                'immediate': '-0.8~2%',
                'pattern': '즉시 하락 후 6-12시간 내 회복',
                'duration': '6-12시간',
                'strategy': '급락 시 분할 매수, 빠른 회복 기대',
                'actual_impact': 'medium',
                'typical_range': (-2.0, -0.8)
            },
            'corporate_purchase_direct': {  # 실제 BTC 매입
                'immediate': '+0.3~1.2%',
                'pattern': '점진적 상승, 며칠간 지속 가능',
                'duration': '1-3일',
                'strategy': '분할 매수, 중기 보유 고려',
                'actual_impact': 'medium',
                'typical_range': (0.3, 1.2)
            },
            'corporate_structured_product': {  # 구조화 상품 (스베르방크 타입)
                'immediate': '+0.05~0.2%',
                'pattern': '미미한 반응, 수 시간 내 소멸',
                'duration': '2-6시간',
                'strategy': '단기 스캘핑만 고려, 장기 영향 없음',
                'actual_impact': 'minimal',
                'typical_range': (0.05, 0.2)
            },
            'regulation_positive': {
                'immediate': '+0.3~0.8%',
                'pattern': '초기 상승 후 안정화',
                'duration': '6-24시간',
                'strategy': '단기 스윙, 과열 구간 주의',
                'actual_impact': 'medium',
                'typical_range': (0.3, 0.8)
            },
            'regulation_negative': {
                'immediate': '-0.8~2.5%',
                'pattern': '급락 후 반등, V자 회복 패턴',
                'duration': '6-18시간',
                'strategy': '급락 시 분할 매수, 반등 타이밍 포착',
                'actual_impact': 'medium',
                'typical_range': (-2.5, -0.8)
            },
            'banking_adoption': {
                'immediate': '+0.1~0.5%',
                'pattern': '완만한 상승, 기관 관심 지속',
                'duration': '1-2일',
                'strategy': '장기 관점 매수, 하락 시 추가 매수',
                'actual_impact': 'low',
                'typical_range': (0.1, 0.5)
            },
            'hack_incident': {
                'immediate': '-0.3~1.5%',
                'pattern': '즉시 하락 후 4-8시간 내 회복',
                'duration': '4-12시간',
                'strategy': '공포 매도 시 역매매, 단기 반등 기대',
                'actual_impact': 'low',
                'typical_range': (-1.5, -0.3)
            },
            'fed_rate_decision': {
                'immediate': '±0.8~2%',
                'pattern': '방향성 뚜렷, 하루 내 추세 확정',
                'duration': '12-48시간',
                'strategy': '방향성 확인 후 추세 추종',
                'actual_impact': 'high',
                'typical_range': (-2.0, 2.0)
            },
            'trade_tariffs': {  # 새로 추가
                'immediate': '-0.3~0.8%',
                'pattern': '즉시 하락 후 수 시간 내 안정화',
                'duration': '6-12시간',
                'strategy': '단기 하락 시 매수 기회, 장기 영향 제한적',
                'actual_impact': 'medium',
                'typical_range': (-0.8, -0.3)
            },
            'inflation_data': {  # 새로 추가
                'immediate': '+0.2~0.8%',
                'pattern': '인플레이션 헤지 수요로 완만한 상승',
                'duration': '12-24시간',
                'strategy': '헤지 수요 지속 시 추가 매수',
                'actual_impact': 'medium',
                'typical_range': (0.2, 0.8)
            },
            'macro_economic_general': {  # 일반 거시경제
                'immediate': '+0.1~0.4%',
                'pattern': '제한적 반응, 단기간 영향',
                'duration': '2-8시간',
                'strategy': '신중한 관망',
                'actual_impact': 'low',
                'typical_range': (-0.4, 0.4)
            }
        }
        
        # 중요 기업 리스트 (비트코인 보유/관련)
        self.important_companies = [
            'tesla', 'microstrategy', 'square', 'block', 'paypal', 'mastercard',
            'gamestop', 'gme', 'blackrock', 'fidelity', 'ark invest',
            'coinbase', 'binance', 'kraken', 'bitget',
            'metaplanet', '메타플래닛', '테슬라', '마이크로스트래티지',
            'sberbank', '스베르방크', 'jpmorgan', 'goldman sachs'
        ]
    
    def _classify_news_type(self, article: Dict) -> str:
        """뉴스 타입 분류 - 구조화 상품 vs 직접 투자 + 거시경제 구분"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # ETF 관련
        if 'etf' in content:
            if any(word in content for word in ['approved', 'approval', 'launch']):
                return 'etf_approval'
            elif any(word in content for word in ['rejected', 'rejection', 'delay']):
                return 'etf_rejection'
        
        # 기업 투자 - 직접 vs 구조화 상품 구분
        if any(company in content for company in ['tesla', 'microstrategy', 'blackrock', 'gamestop']) and \
           any(word in content for word in ['bought', 'purchased', 'buys', 'adds']):
            return 'corporate_purchase_direct'
        
        # 구조화 상품 (비트코인 직접 매수 아님)
        if any(word in content for word in ['structured', 'bonds', 'linked', 'tracking', 'exposure']) and \
           any(word in content for word in ['bitcoin', 'btc']):
            return 'corporate_structured_product'
        
        # 은행/기관 채택
        if any(bank in content for bank in ['sberbank', 'bank', 'central bank']) and \
           any(word in content for word in ['bitcoin', 'btc', 'bonds', 'launches']):
            # 구조화 상품인지 직접 투자인지 구분
            if any(word in content for word in ['structured', 'bonds', 'linked', 'exposure']):
                return 'corporate_structured_product'
            else:
                return 'banking_adoption'
        
        # 규제 관련
        if any(word in content for word in ['regulation', 'legal', 'court']) and \
           any(word in content for word in ['positive', 'approved', 'favorable']):
            return 'regulation_positive'
        elif any(word in content for word in ['ban', 'prohibited', 'lawsuit', 'illegal']):
            return 'regulation_negative'
        
        # Fed 금리 및 거시경제
        if any(word in content for word in ['fed', 'fomc', 'federal reserve', 'interest rate']):
            return 'fed_rate_decision'
        elif any(word in content for word in ['trump', 'tariffs', 'trade war', 'china tariffs']):
            return 'trade_tariffs'
        elif any(word in content for word in ['inflation', 'cpi', 'pce']):
            return 'inflation_data'
        
        # 해킹/보안
        elif any(word in content for word in ['hack', 'stolen', 'breach', 'exploit']):
            return 'hack_incident'
        
        else:
            return 'macro_economic_general'
    
    def _get_ml_impact_prediction(self, article: Dict) -> Dict:
        """ML 기반 영향 예측 - 현실적 조정"""
        try:
            if not self.ml_predictor:
                return self._get_fallback_prediction(article)
            
            # 뉴스 특성 추출
            features = self._extract_news_features(article)
            
            # ML 예측 실행
            prediction = self.ml_predictor.predict_price_impact(features)
            
            # 현실적 조정 (과도한 예측 방지)
            magnitude = min(prediction.get('magnitude', 0.5), 1.5)  # 최대 1.5% 제한
            confidence = prediction.get('confidence', 0.6)
            
            return {
                'direction': prediction.get('direction', 'neutral'),
                'magnitude': magnitude,
                'confidence': confidence,
                'timeframe': self._get_realistic_timeframe(article),
                'risk_level': prediction.get('risk_level', 'medium')
            }
            
        except Exception as e:
            self.logger.error(f"ML 예측 실패: {e}")
            return self._get_fallback_prediction(article)
    
    def _get_realistic_timeframe(self, article: Dict) -> str:
        """현실적인 반응 시점 계산"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 즉시 반응 (고영향)
        if any(word in content for word in ['etf approved', 'etf rejected', 'fed rate']):
            return '즉시-30분'
        
        # 빠른 반응 (중영향)
        elif any(word in content for word in ['bought billion', 'lawsuit', 'ban']):
            return '30분-2시간'
        
        # 지연 반응 (저영향)
        elif any(word in content for word in ['structured', 'bonds', 'linked']):
            return '1-4시간 (미미)'
        
        # 일반
        else:
            return '1-6시간'
    
    def _extract_news_features(self, article: Dict) -> Dict:
        """뉴스에서 ML 특성 추출"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        features = {
            'has_bitcoin_keyword': any(word in content for word in ['bitcoin', 'btc']),
            'has_amount': bool(re.search(r'\$?\d+(?:,\d+)*(?:\.\d+)?\s*(?:billion|million|thousand)', content)),
            'sentiment_score': self._calculate_sentiment_score(content),
            'source_weight': article.get('weight', 5),
            'company_involved': any(company in content for company in ['tesla', 'microstrategy', 'blackrock']),
            'regulatory_keyword': any(word in content for word in ['sec', 'etf', 'regulation', 'court']),
            'urgency_indicators': len(re.findall(r'breaking|urgent|alert|immediate', content)),
            'negative_keywords': len(re.findall(r'ban|prohibited|hack|stolen|crash|plunge', content)),
            'positive_keywords': len(re.findall(r'approved|launch|bought|partnership|adoption', content)),
            'is_structured_product': any(word in content for word in ['structured', 'bonds', 'linked', 'exposure']),  
            'is_direct_investment': any(word in content for word in ['bought', 'purchased', 'acquired']) and not any(word in content for word in ['structured', 'bonds', 'linked']),
            'is_macro_economic': any(word in content for word in ['fed', 'tariffs', 'inflation', 'trade']),  # 새로 추가
        }
        
        return features
    
    def _calculate_sentiment_score(self, content: str) -> float:
        """간단한 감정 점수 계산"""
        positive_words = ['approved', 'launched', 'bought', 'partnership', 'adoption', 'positive', 'surge', 'rally']
        negative_words = ['banned', 'rejected', 'hack', 'stolen', 'crash', 'plunge', 'lawsuit', 'prohibited']
        
        pos_count = sum(1 for word in positive_words if word in content)
        neg_count = sum(1 for word in negative_words if word in content)
        
        if pos_count + neg_count == 0:
            return 0.0
        
        return (pos_count - neg_count) / (pos_count + neg_count)
    
    def _get_fallback_prediction(self, article: Dict) -> Dict:
        """ML 사용 불가 시 현실적 폴백 예측"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 뉴스 타입 분류
        news_type = self._classify_news_type(article)
        pattern_info = self.news_reaction_patterns.get(news_type, self.news_reaction_patterns['macro_economic_general'])
        
        # 패턴 기반 예측 범위
        min_impact, max_impact = pattern_info['typical_range']
        
        # 중간값 계산
        avg_impact = (min_impact + max_impact) / 2
        magnitude = abs(avg_impact)
        direction = 'bullish' if avg_impact > 0 else 'bearish' if avg_impact < 0 else 'neutral'
        
        return {
            'direction': direction,
            'magnitude': magnitude,
            'confidence': 0.7,
            'timeframe': self._get_realistic_timeframe(article),
            'risk_level': pattern_info['actual_impact']
        }
    
    def _format_smart_strategy(self, news_type: str, ml_prediction: Dict, article: Dict) -> str:
        """현실적 전략 제안"""
        direction = ml_prediction.get('direction', 'neutral')
        magnitude = ml_prediction.get('magnitude', 0.5)
        confidence = ml_prediction.get('confidence', 0.5)
        
        # 기본 패턴 정보
        pattern_info = self.news_reaction_patterns.get(news_type, {})
        
        strategy_lines = []
        
        # 뉴스 타입별 특화 전략
        if news_type == 'corporate_structured_product':
            strategy_lines.append("🎯 <b>구조화 상품 - 미미한 영향</b>")
            strategy_lines.append("• 직접적인 BTC 수요 창출 없음")
            strategy_lines.append("• 단기 스캘핑만 고려")
            strategy_lines.append("• 장기 투자 의사결정에 영향 없음")
            
        elif news_type == 'corporate_purchase_direct':
            if magnitude > 0.8:
                strategy_lines.append("🎯 <b>직접 매입 - 적극 매수 시나리오</b>")
                strategy_lines.append("• 실제 BTC 수요 증가")
                strategy_lines.append("• 분할 매수 후 중기 보유")
            else:
                strategy_lines.append("🎯 <b>직접 매입 - 신중 매수 시나리오</b>")
                strategy_lines.append("• 소량 테스트 후 추가 진입")
                
        elif news_type == 'etf_approval':
            strategy_lines.append("🎯 <b>ETF 승인 - 즉시 대응 필요</b>")
            strategy_lines.append("• 발표 직후 빠른 진입")
            strategy_lines.append("• 2-4시간 내 수익 실현 고려")
            
        elif news_type == 'etf_rejection':
            strategy_lines.append("🎯 <b>ETF 거부 - 역매매 기회</b>")
            strategy_lines.append("• 급락 시 분할 매수")
            strategy_lines.append("• 6-12시간 내 회복 기대")
            
        elif news_type == 'trade_tariffs':
            strategy_lines.append("🎯 <b>관세 정책 - 단기 하락 후 회복</b>")
            strategy_lines.append("• 초기 매도 압박 후 안정화")
            strategy_lines.append("• 하락 시 분할 매수 기회")
            
        elif news_type == 'inflation_data':
            strategy_lines.append("🎯 <b>인플레이션 헤지 - 완만한 상승</b>")
            strategy_lines.append("• 헤지 수요로 점진적 상승")
            strategy_lines.append("• 장기 보유 관점에서 유리")
            
        elif direction == 'bearish' and confidence > 0.6:
            strategy_lines.append("🎯 <b>방어 및 역매매 시나리오</b>")
            strategy_lines.append("• 기존 포지션 부분 청산")
            strategy_lines.append("• 과매도 시 역매매 준비")
        else:
            strategy_lines.append("🎯 <b>중립 관망</b>")
            strategy_lines.append("• 추가 신호 대기")
            strategy_lines.append("• 소량 양방향 헷지 고려")
        
        # 현실적인 타이밍 정보
        if pattern_info.get('pattern'):
            strategy_lines.append(f"⏱️ <b>반응 패턴</b>: {pattern_info['pattern']}")
        
        # 현실적인 지속 기간
        if pattern_info.get('duration'):
            strategy_lines.append(f"📅 <b>영향 지속</b>: {pattern_info['duration']}")
        else:
            # 기본값 - 뉴스 타입에 따라
            if news_type == 'corporate_structured_product':
                strategy_lines.append(f"📅 <b>영향 지속</b>: 2-6시간 (미미)")
            elif news_type in ['etf_approval', 'etf_rejection']:
                strategy_lines.append(f"📅 <b>영향 지속</b>: 12-24시간")
            else:
                strategy_lines.append(f"📅 <b>영향 지속</b>: 6-12시간")
        
        # 실제 영향도 표시
        actual_impact = pattern_info.get('actual_impact', 'medium')
        impact_text = {
            'high': '높음 ⚡',
            'medium': '보통 📊', 
            'low': '낮음 📉',
            'minimal': '미미 💭'
        }.get(actual_impact, '보통 📊')
        
        strategy_lines.append(f"🎲 <b>실제 영향도</b>: {impact_text} (신뢰도: {confidence:.0%})")
        
        return "\n".join(strategy_lines)
    
    def _generate_smart_summary(self, title: str, description: str, company: str = "") -> str:
        """AI 없이 3문장 요약 생성 - 투자 관점에서 핵심 정보 추출"""
        try:
            content = (title + " " + description).lower()
            summary_parts = []
            
            # 구조화 상품 특별 처리
            if any(word in content for word in ['structured', 'bonds', 'linked', 'exposure']):
                if 'sberbank' in content:
                    summary_parts.append("러시아 최대 은행 스베르방크가 비트코인 가격에 연동된 구조화 채권을 출시했다.")
                    summary_parts.append("이는 직접적인 비트코인 매수가 아닌 가격 추적 상품으로, 실제 BTC 수요 창출 효과는 제한적이다.")
                    summary_parts.append("러시아 제재 상황과 OTC 거래로 인해 글로벌 시장에 미치는 즉각적 영향은 미미할 것으로 예상된다.")
                else:
                    summary_parts.append("새로운 비트코인 연계 구조화 상품이 출시되었다.")
                    summary_parts.append("직접적인 비트코인 수요보다는 간접적 노출 제공에 중점을 둔 상품으로 평가된다.")
                    summary_parts.append("시장에 미치는 실질적 영향은 제한적일 것으로 전망된다.")
                
                return " ".join(summary_parts)
            
            # 기업명과 행동 매칭
            if company:
                company_lower = company.lower()
                
                # 마이크로스트래티지 처리
                if company_lower == 'microstrategy':
                    if 'bought' in content or 'purchase' in content:
                        btc_amounts = re.findall(r'(\d+(?:,\d+)*)\s*(?:btc|bitcoin)', content)
                        if btc_amounts:
                            summary_parts.append(f"마이크로스트래티지가 비트코인 {btc_amounts[0]}개를 직접 매입했다.")
                        else:
                            summary_parts.append("마이크로스트래티지가 비트코인을 추가 매입했다.")
                        
                        summary_parts.append("이는 실제 BTC 수요 증가를 의미하며, 기업 재무 전략의 일환으로 시장에 긍정적 신호를 보낸다.")
                        summary_parts.append("대형 기업의 지속적인 비트코인 매입은 시장 신뢰도 향상에 기여할 것으로 예상된다.")
                
                # 테슬라 처리
                elif company_lower == 'tesla':
                    if 'bought' in content or 'purchase' in content:
                        summary_parts.append("테슬라가 비트코인 직접 매입을 재개했다.")
                        summary_parts.append("일론 머스크의 영향력과 함께 시장에 상당한 관심을 불러일으킬 것으로 예상된다.")
                        summary_parts.append("기업의 비트코인 채택 확산에 긍정적 영향을 미칠 전망이다.")
                
                # 블랙록 처리
                elif company_lower == 'blackrock':
                    if 'etf' in content:
                        if 'approved' in content:
                            summary_parts.append("세계 최대 자산운용사 블랙록의 비트코인 ETF가 승인되었다.")
                            summary_parts.append("이는 기관 자금의 대규모 유입 가능성을 열어주는 획기적 사건이다.")
                            summary_parts.append("비트코인 시장의 제도화와 주류 채택에 중요한 이정표가 될 것으로 보인다.")
                        else:
                            summary_parts.append("블랙록의 비트코인 ETF 관련 중요한 발표가 있었다.")
                            summary_parts.append("세계 최대 자산운용사의 움직임이 시장에 주목받고 있다.")
                            summary_parts.append("기관 투자자들의 비트코인 관심도가 높아지고 있음을 시사한다.")
            
            # 거시경제 패턴 처리 (새로 추가)
            if not summary_parts:
                # 관세 관련
                if any(word in content for word in ['trump', 'tariffs', 'trade war']):
                    summary_parts.append("미국의 새로운 관세 정책이 발표되었다.")
                    summary_parts.append("무역 분쟁 우려로 인해 단기적으로 리스크 자산에 부담이 될 수 있다.")
                    summary_parts.append("하지만 달러 약세 요인이 비트코인에는 중장기적으로 유리할 것으로 분석된다.")
                
                # 인플레이션 관련
                elif any(word in content for word in ['inflation', 'cpi']):
                    summary_parts.append("최신 인플레이션 데이터가 발표되었다.")
                    summary_parts.append("인플레이션 헤지 자산으로서 비트코인에 대한 관심이 높아지고 있다.")
                    summary_parts.append("실물 자산 대비 우월한 성과를 보이며 투자자들의 주목을 받고 있다.")
                
                # ETF 관련
                elif 'etf' in content:
                    if 'approved' in content or 'approval' in content:
                        summary_parts.append("비트코인 현물 ETF 승인 소식이 전해졌다.")
                        summary_parts.append("ETF 승인은 기관 투자자들의 대규모 자금 유입을 가능하게 하는 중요한 이정표다.")
                        summary_parts.append("비트코인 시장의 성숙도와 제도적 인정을 보여주는 상징적 사건으로 평가된다.")
                    elif 'rejected' in content or 'delay' in content:
                        summary_parts.append("비트코인 ETF 승인이 지연되거나 거부되었다.")
                        summary_parts.append("단기적 실망감은 있으나, 지속적인 신청은 결국 승인 가능성을 높이고 있다.")
                        summary_parts.append("시장은 이미 ETF 승인을 기정사실로 받아들이고 있어 장기 전망은 긍정적이다.")
                
                # Fed 금리 관련
                elif 'fed' in content or 'rate' in content:
                    if 'cut' in content or 'lower' in content:
                        summary_parts.append("연준의 금리 인하 결정이 발표되었다.")
                        summary_parts.append("금리 인하는 유동성 증가를 통해 비트코인과 같은 리스크 자산에 긍정적 영향을 미친다.")
                        summary_parts.append("저금리 환경에서 대안 투자처로서 비트코인의 매력도가 더욱 부각될 전망이다.")
                    elif 'hike' in content or 'increase' in content:
                        summary_parts.append("연준의 금리 인상 결정이 발표되었다.")
                        summary_parts.append("단기적으로는 부담이지만 인플레이션 헤지 자산으로서의 비트코인 가치는 지속될 것이다.")
                        summary_parts.append("고금리 환경에서도 디지털 금으로서의 역할은 변함없을 것으로 예상된다.")
                
                # 기본 케이스
                else:
                    summary_parts.append("비트코인 시장에 영향을 미칠 수 있는 발표가 있었다.")
                    summary_parts.append("투자자들은 이번 소식의 실제 시장 영향을 면밀히 분석하고 있다.")
                    summary_parts.append("단기 변동성은 있겠지만 장기 트렌드에는 큰 변화가 없을 것으로 전망된다.")
            
            return " ".join(summary_parts[:3]) if summary_parts else "비트코인 관련 소식이 발표되었다. 시장 반응을 지켜볼 필요가 있다. 투자자들은 신중한 접근이 필요하다."
            
        except Exception as e:
            self.logger.error(f"스마트 요약 생성 실패: {e}")
            return "비트코인 시장 관련 소식이 발표되었다. 자세한 내용은 원문을 확인하시기 바란다. 실제 시장 반응을 면밀히 분석할 필요가 있다."
    
    async def _get_current_market_status(self, news_time: datetime = None) -> str:
        """현재 시장 상황 조회 - 실제 API 데이터 사용 및 뉴스 후 변동률 계산"""
        try:
            if not self.bitget_client:
                return ""
            
            # 현재 시장 데이터 조회
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            if not ticker:
                return ""
            
            current_price = float(ticker.get('last', 0))
            change_24h = float(ticker.get('changeUtc', 0)) * 100
            volume_24h = float(ticker.get('baseVolume', 0))
            
            # 현재가 0 문제 해결
            if current_price <= 0:
                self.logger.warning(f"현재가 데이터 오류: {current_price}")
                return ""
            
            # 뉴스 발표 후 변동률 계산
            if news_time:
                news_hash = f"news_{news_time.timestamp()}"
                
                # 뉴스 발표 시점의 가격 데이터가 있는지 확인
                if news_hash in self.news_initial_data:
                    initial_data = self.news_initial_data[news_hash]
                    initial_price = initial_data['price']
                    initial_volume = initial_data['volume']
                    
                    # 실제 변동률 계산
                    price_change_since_news = ((current_price - initial_price) / initial_price) * 100
                    volume_change_since_news = ((volume_24h - initial_volume) / initial_volume) * 100 if initial_volume > 0 else 0
                    
                    # 시간 경과 계산
                    time_elapsed = datetime.now() - news_time
                    minutes_elapsed = int(time_elapsed.total_seconds() / 60)
                    
                    # 시장 반응 분석
                    reaction_analysis = self._analyze_market_reaction(price_change_since_news, volume_change_since_news, minutes_elapsed)
                    
                else:
                    # 뉴스 발표 시점 데이터 없음 - 현재 데이터로 초기화
                    self.news_initial_data[news_hash] = {
                        'price': current_price,
                        'volume': volume_24h,
                        'time': datetime.now()
                    }
                    price_change_since_news = 0
                    volume_change_since_news = 0
                    minutes_elapsed = 0
                    reaction_analysis = "데이터 수집 중"
            else:
                price_change_since_news = 0
                volume_change_since_news = 0
                minutes_elapsed = 0
                reaction_analysis = "실시간 모니터링"
            
            # 현재 상태 분석
            if abs(change_24h) >= 3.0:
                price_trend = "급등세" if change_24h > 0 else "급락세"
            elif abs(change_24h) >= 1.0:
                price_trend = "상승세" if change_24h > 0 else "하락세"
            elif abs(change_24h) >= 0.3:
                price_trend = "약한 상승" if change_24h > 0 else "약한 하락"
            else:
                price_trend = "횡보"
            
            volume_status = "매우 높음" if volume_24h > 80000 else "높음" if volume_24h > 60000 else "보통" if volume_24h > 40000 else "낮음"
            
            market_status = f"""
<b>📊 현재 시장 상황 (실시간 API 데이터):</b>
• 현재가: <b>${current_price:,.0f}</b> (24시간: {change_24h:+.2f}%)
• 시장 추세: <b>{price_trend}</b>
• 거래량: <b>{volume_24h:,.0f} BTC</b> ({volume_status})"""
            
            if minutes_elapsed > 0:
                market_status += f"""
• 뉴스 후 변동: <b>{price_change_since_news:+.2f}%</b> ({minutes_elapsed}분 경과)
• 뉴스 후 거래량: <b>{volume_change_since_news:+.1f}%</b> 변화
• 시장 반응: <b>{reaction_analysis}</b>"""
            
            return market_status
            
        except Exception as e:
            self.logger.error(f"현재 시장 상황 조회 실패: {e}")
            return ""
    
    def _analyze_market_reaction(self, price_change: float, volume_change: float, minutes_elapsed: int) -> str:
        """시장 반응 분석"""
        abs_price_change = abs(price_change)
        
        # 시간대별 반응 분석
        if minutes_elapsed <= 30:  # 30분 이내
            if abs_price_change >= 2.0:
                return "즉각 강한 반응" if price_change > 0 else "즉각 강한 매도"
            elif abs_price_change >= 1.0:
                return "즉각 중간 반응" if price_change > 0 else "즉각 중간 매도"
            elif abs_price_change >= 0.3:
                return "약간 반응" if price_change > 0 else "약간 매도"
            else:
                return "반응 미미"
        
        elif minutes_elapsed <= 120:  # 2시간 이내
            if abs_price_change >= 1.5:
                return "지속적 강한 반응" if price_change > 0 else "지속적 강한 매도"
            elif abs_price_change >= 0.8:
                return "지속적 반응" if price_change > 0 else "지속적 매도"
            elif abs_price_change >= 0.3:
                return "완만한 반응" if price_change > 0 else "완만한 매도"
            else:
                return "제한적 반응"
        
        else:  # 2시간 이후
            if abs_price_change >= 1.0:
                return "장기간 영향" if price_change > 0 else "장기간 부정적"
            elif abs_price_change >= 0.5:
                return "일부 영향 지속" if price_change > 0 else "일부 부정적 지속"
            else:
                return "영향 소멸"
    
    async def generate_report(self, event: Dict) -> str:
        """🚨 현실적인 긴급 예외 리포트 생성 - 즉시 감지 표시"""
        current_time = self._get_current_time_kst()
        event_type = event.get('type', 'unknown')
        
        if event_type == 'critical_news':
            # 뉴스 정보
            title_ko = event.get('title_ko', event.get('title', ''))
            summary = event.get('summary', '')
            description = event.get('description', '')
            company = event.get('company', '')
            published_at = event.get('published_at', '')
            
            # 🔥🔥 발행 시간을 즉시 감지로 변경
            detection_time = "즉시 감지"
            if published_at:
                try:
                    if 'T' in published_at:
                        pub_time = datetime.fromisoformat(published_at.replace('Z', ''))
                    else:
                        from dateutil import parser
                        pub_time = parser.parse(published_at)
                    
                    if pub_time.tzinfo is None:
                        pub_time = pytz.UTC.localize(pub_time)
                    
                    kst_time = pub_time.astimezone(pytz.timezone('Asia/Seoul'))
                    
                    # 발행 시간과 현재 시간의 차이 계산
                    current_kst = datetime.now(pytz.timezone('Asia/Seoul'))
                    time_diff = current_kst - kst_time
                    minutes_diff = int(time_diff.total_seconds() / 60)
                    
                    if minutes_diff < 5:
                        detection_time = "즉시 감지"
                    elif minutes_diff < 60:
                        detection_time = f"{minutes_diff}분 전 발행 → 즉시 감지"
                    else:
                        hours_diff = int(minutes_diff / 60)
                        detection_time = f"{hours_diff}시간 전 발행 → 즉시 감지"
                        
                except:
                    detection_time = "즉시 감지"
            
            # 기업명이 있으면 제목에 포함
            if company and company.lower() not in title_ko.lower():
                title_ko = f"{company} - {title_ko}"
            
            # 뉴스 타입 분류 (구조화 상품 vs 직접 투자 + 거시경제 구분)
            news_type = self._classify_news_type(event)
            
            # ML 기반 영향 예측 (현실적 조정)
            ml_prediction = self._get_ml_impact_prediction(event)
            
            # 예상 변동 계산 (현실적 범위)
            direction = ml_prediction.get('direction', 'neutral')
            magnitude = ml_prediction.get('magnitude', 0.5)
            
            # 패턴 기반 현실적 범위 조정
            pattern_info = self.news_reaction_patterns.get(news_type, self.news_reaction_patterns['macro_economic_general'])
            min_impact, max_impact = pattern_info['typical_range']
            
            # ML 예측과 패턴 정보 결합
            if direction == 'bullish':
                adjusted_min = max(min_impact, 0.05)  # 최소 0.05%
                adjusted_max = min(max_impact, magnitude + 0.3)
                impact_text = "📈 호재" if adjusted_max > 0.8 else "📈 약한 호재" if adjusted_max > 0.3 else "📈 미미한 호재"
                expected_change = f"📈 상승 +{adjusted_min:.2f}~{adjusted_max:.2f}%"
            elif direction == 'bearish':
                adjusted_min = max(abs(max_impact), 0.05)  # 최소 0.05%
                adjusted_max = min(abs(min_impact), magnitude + 0.3)
                impact_text = "📉 악재" if adjusted_max > 0.8 else "📉 약한 악재" if adjusted_max > 0.3 else "📉 미미한 악재"
                expected_change = f"📉 하락 -{adjusted_min:.2f}~{adjusted_max:.2f}%"
            else:
                adjusted_range = min(magnitude, 0.4)
                impact_text = "⚡ 미미한 변동" if adjusted_range < 0.2 else "⚡ 변동성"
                expected_change = f"⚡ 변동 ±{adjusted_range/2:.2f}~{adjusted_range:.2f}%"
            
            # 현실적 전략 생성
            smart_strategy = self._format_smart_strategy(news_type, ml_prediction, event)
            
            # 3문장 요약 생성
            if summary and len(summary.strip()) > 10:
                detail_summary = summary[:200]  # 200자로 제한
            elif description and len(description.strip()) > 20:
                detail_summary = self._generate_smart_summary(
                    event.get('title', ''), 
                    description, 
                    company
                )
            else:
                detail_summary = self._generate_smart_summary(
                    event.get('title', ''), 
                    "", 
                    company
                )
            
            # 빈 요약 방지
            if not detail_summary or len(detail_summary.strip()) < 10:
                detail_summary = "비트코인 관련 발표가 있었다. 실제 시장 영향을 주의깊게 모니터링하고 있다. 투자자들은 신중한 접근이 필요하다."
            
            # 현재 시장 상황 조회 (실제 뉴스 후 변동률 포함)
            pub_time = None
            try:
                if published_at and 'T' in published_at:
                    pub_time = datetime.fromisoformat(published_at.replace('Z', ''))
                elif published_at:
                    from dateutil import parser
                    pub_time = parser.parse(published_at)
            except:
                pass
            
            market_status = await self._get_current_market_status(pub_time)
            
            # 리포트 생성
            report = f"""🚨 <b>BTC 긴급 예외 리포트</b>
📅 감지: {detection_time}
━━━━━━━━━━━━━━━

📰 <b>{title_ko}</b>

📊 <b>영향 분석</b>: {impact_text}
💹 <b>예상 변동</b>: {expected_change}
⏱️ <b>반응 시점</b>: {ml_prediction.get('timeframe', '1-6시간')}

<b>📋 핵심 내용:</b>
{detail_summary}
{market_status}

━━━━━━━━━━━━━━━

{smart_strategy}

━━━━━━━━━━━━━━━
⏰ {current_time}

<i>💡 이 예측은 과거 유사 뉴스의 실제 시장 반응을 기반으로 생성되었습니다.</i>"""
            
        elif event_type == 'price_anomaly':
            # 가격 이상 징후
            change = event.get('change_24h', 0)
            current_price = event.get('current_price', 0)
            
            if abs(change) >= 0.05:  # 5% 이상
                severity = "급변동"
                emoji = "🚨"
            elif abs(change) >= 0.03:  # 3% 이상
                severity = "주의"
                emoji = "⚠️"
            else:
                severity = "변동"
                emoji = "📊"
            
            direction = "상승" if change > 0 else "하락"
            
            # 추천 전략
            if change > 0.03:
                recommendation = "과열 주의"
                strategy = "• 분할 익절 고려\n• 추격 매수 자제\n• 조정 대기"
                duration = "2-6시간"
            elif change < -0.03:
                recommendation = "반등 대기"
                strategy = "• 분할 매수 준비\n• 지지선 확인\n• 패닉 셀링 자제"
                duration = "4-12시간"
            else:
                recommendation = "추세 관찰"
                strategy = "• 거래량 확인\n• 지표 점검\n• 신중한 접근"
                duration = "1-3시간"
            
            report = f"""🚨 <b>BTC 가격 {severity}</b>
━━━━━━━━━━━━━━━

{emoji} <b>{abs(change*100):.1f}% {direction}</b>

💰 현재가: <b>${current_price:,.0f}</b>
📊 24시간: <b>{change*100:+.1f}%</b>

━━━━━━━━━━━━━━━

🎯 <b>추천</b>: {recommendation}

{strategy}

📅 <b>영향 지속</b>: {duration}

━━━━━━━━━━━━━━━
⏰ {current_time}"""
            
        elif event_type == 'volume_anomaly':
            # 거래량 이상
            ratio = event.get('ratio', 0)
            volume = event.get('volume_24h', 0)
            
            if ratio >= 5:
                severity = "폭증"
                emoji = "🔥"
                recommendation = "중요 변동 예상"
                strategy = "• 뉴스 확인 필수\n• 포지션 점검\n• 높은 변동성 대비"
                duration = "6-24시간"
            elif ratio >= 3:
                severity = "급증"
                emoji = "📈"
                recommendation = "추세 전환 가능"
                strategy = "• 방향성 확인\n• 분할 진입\n• 거래량 지속성 확인"
                duration = "4-12시간"
            else:
                severity = "증가"
                emoji = "📊"
                recommendation = "관심 필요"
                strategy = "• 시장 모니터링\n• 소량 테스트\n• 추가 신호 대기"
                duration = "2-6시간"
            
            report = f"""🚨 <b>BTC 거래량 {severity}</b>
━━━━━━━━━━━━━━━

{emoji} 평균 대비 <b>{ratio:.1f}배</b>

📊 24시간: <b>{volume:,.0f} BTC</b>
💹 시장 관심 급증

━━━━━━━━━━━━━━━

🎯 <b>추천</b>: {recommendation}

{strategy}

📅 <b>영향 지속</b>: {duration}

━━━━━━━━━━━━━━━
⏰ {current_time}"""
            
        else:
            # 기타 이벤트
            description = event.get('description', '이상 신호 감지')
            
            report = f"""🚨 <b>BTC 이상 신호</b>
━━━━━━━━━━━━━━━

⚠️ {description}

━━━━━━━━━━━━━━━

🎯 <b>추천</b>: 주의 관찰

• 포지션 점검
• 리스크 관리
• 추가 정보 수집

📅 <b>영향 지속</b>: 1-6시간

━━━━━━━━━━━━━━━
⏰ {current_time}"""
        
        return report
