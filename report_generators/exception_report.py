# report_generators/exception_report.py
from .base_generator import BaseReportGenerator
from typing import Dict
from datetime import datetime
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
    """예외 상황 리포트 전담 생성기 - 강화된 분석"""
    
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
        
        # 과거 뉴스 반응 패턴 데이터
        self.news_reaction_patterns = {
            'etf_approval': {
                'immediate': '+1~3%',
                'pattern': '즉시 상승 후 2-4시간 내 조정',
                'duration': '24-48시간',
                'strategy': '발표 직후 진입, 과열 시 부분 익절'
            },
            'corporate_purchase': {
                'immediate': '+0.3~1%',
                'pattern': '점진적 상승, 며칠간 지속',
                'duration': '3-7일',
                'strategy': '분할 매수, 장기 보유 고려'
            },
            'regulation_positive': {
                'immediate': '+0.5~2%',
                'pattern': '초기 급등 후 안정화',
                'duration': '1-3일',
                'strategy': '단기 스윙, 과열 구간 주의'
            },
            'regulation_negative': {
                'immediate': '-1~3%',
                'pattern': '급락 후 반등, V자 회복',
                'duration': '12-24시간',
                'strategy': '급락 시 분할 매수, 반등 대기'
            },
            'banking_adoption': {
                'immediate': '+0.2~0.8%',
                'pattern': '완만한 상승, 기관 매수 지속',
                'duration': '1주일+',
                'strategy': '장기 관점 매수, 하락 시 추가 매수'
            },
            'hack_incident': {
                'immediate': '-0.5~2%',
                'pattern': '즉시 하락 후 빠른 회복',
                'duration': '2-6시간',
                'strategy': '공포 매도 시 역매매, 단기 반등 노려'
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
        """뉴스 타입 분류"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        if 'etf' in content and any(word in content for word in ['approved', 'approval', 'launch']):
            return 'etf_approval'
        elif 'etf' in content and any(word in content for word in ['rejected', 'rejection', 'delay']):
            return 'regulation_negative'
        elif any(company in content for company in ['tesla', 'microstrategy', 'blackrock', 'gamestop']) and \
             any(word in content for word in ['bought', 'purchased', 'buys', 'adds']):
            return 'corporate_purchase'
        elif any(bank in content for bank in ['sberbank', 'bank', 'central bank']) and \
             any(word in content for word in ['bitcoin', 'btc', 'bonds', 'launches']):
            return 'banking_adoption'
        elif any(word in content for word in ['regulation', 'legal', 'court']) and \
             any(word in content for word in ['positive', 'approved', 'favorable']):
            return 'regulation_positive'
        elif any(word in content for word in ['ban', 'prohibited', 'lawsuit', 'illegal']):
            return 'regulation_negative'
        elif any(word in content for word in ['hack', 'stolen', 'breach', 'exploit']):
            return 'hack_incident'
        else:
            return 'general'
    
    def _get_ml_impact_prediction(self, article: Dict) -> Dict:
        """ML 기반 영향 예측"""
        try:
            if not self.ml_predictor:
                return self._get_fallback_prediction(article)
            
            # 뉴스 특성 추출
            features = self._extract_news_features(article)
            
            # ML 예측 실행
            prediction = self.ml_predictor.predict_price_impact(features)
            
            return {
                'direction': prediction.get('direction', 'neutral'),
                'magnitude': prediction.get('magnitude', 0.5),
                'confidence': prediction.get('confidence', 0.6),
                'timeframe': prediction.get('timeframe', '1-6시간'),
                'risk_level': prediction.get('risk_level', 'medium')
            }
            
        except Exception as e:
            self.logger.error(f"ML 예측 실패: {e}")
            return self._get_fallback_prediction(article)
    
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
            'positive_keywords': len(re.findall(r'approved|launch|bought|partnership|adoption', content))
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
        """ML 사용 불가 시 폴백 예측"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 키워드 기반 간단 예측
        if any(word in content for word in ['approved', 'etf', 'bought billion']):
            return {
                'direction': 'bullish',
                'magnitude': 1.5,
                'confidence': 0.7,
                'timeframe': '1-6시간',
                'risk_level': 'medium'
            }
        elif any(word in content for word in ['banned', 'prohibited', 'hack']):
            return {
                'direction': 'bearish',
                'magnitude': 1.2,
                'confidence': 0.6,
                'timeframe': '즉시-2시간',
                'risk_level': 'high'
            }
        else:
            return {
                'direction': 'neutral',
                'magnitude': 0.5,
                'confidence': 0.5,
                'timeframe': '1-4시간',
                'risk_level': 'low'
            }
    
    def _format_smart_strategy(self, news_type: str, ml_prediction: Dict, article: Dict) -> str:
        """지능형 전략 제안"""
        direction = ml_prediction.get('direction', 'neutral')
        magnitude = ml_prediction.get('magnitude', 0.5)
        confidence = ml_prediction.get('confidence', 0.5)
        
        # 기본 패턴 정보
        pattern_info = self.news_reaction_patterns.get(news_type, {})
        
        strategy_lines = []
        
        # 방향성에 따른 기본 전략
        if direction == 'bullish' and confidence > 0.6:
            if magnitude > 1.0:
                strategy_lines.append("🎯 <b>적극 매수 시나리오</b>")
                strategy_lines.append("• 즉시 진입 후 분할 매수")
                strategy_lines.append(f"• 예상 반응: {pattern_info.get('immediate', '+0.5~1.5%')}")
            else:
                strategy_lines.append("🎯 <b>신중 매수 시나리오</b>")
                strategy_lines.append("• 소량 테스트 후 추가 진입")
                strategy_lines.append(f"• 예상 반응: {pattern_info.get('immediate', '+0.2~0.8%')}")
        elif direction == 'bearish' and confidence > 0.6:
            if magnitude > 1.0:
                strategy_lines.append("🎯 <b>방어 및 역매매 시나리오</b>")
                strategy_lines.append("• 기존 포지션 부분 청산")
                strategy_lines.append("• 과매도 시 역매매 준비")
            else:
                strategy_lines.append("🎯 <b>관망 및 리스크 관리</b>")
                strategy_lines.append("• 신규 진입 보류")
                strategy_lines.append("• 기존 포지션 모니터링")
        else:
            strategy_lines.append("🎯 <b>중립 관망</b>")
            strategy_lines.append("• 추가 신호 대기")
            strategy_lines.append("• 소량 양방향 헷지 고려")
        
        # 타이밍 정보
        if pattern_info.get('pattern'):
            strategy_lines.append(f"⏱️ <b>반응 패턴</b>: {pattern_info['pattern']}")
        
        # 지속 기간
        if pattern_info.get('duration'):
            strategy_lines.append(f"📅 <b>영향 지속</b>: {pattern_info['duration']}")
        
        # 신뢰도 정보
        confidence_text = "높음" if confidence > 0.7 else "보통" if confidence > 0.5 else "낮음"
        strategy_lines.append(f"🎲 <b>예측 신뢰도</b>: {confidence_text} ({confidence:.0%})")
        
        return "\n".join(strategy_lines)
    
    def _generate_smart_summary(self, title: str, description: str, company: str = "") -> str:
        """AI 없이 스마트 요약 생성 - 투자 관점에서 핵심 정보 추출"""
        try:
            content = (title + " " + description).lower()
            summary_parts = []
            
            # 기업명과 행동 매칭
            if company:
                company_lower = company.lower()
                
                # 스베르방크 특별 처리
                if company_lower == 'sberbank':
                    if 'bonds' in content or 'launch' in content:
                        summary_parts.append("러시아 최대 은행 스베르방크가 비트코인 연계 구조화 채권을 출시했습니다.")
                        summary_parts.append("이는 러시아 금융권의 비트코인 채택 확산을 의미하며, 전통 금융기관의 암호화폐 진입 가속화를 시사합니다.")
                    
                # 마이크로스트래티지 처리
                elif company_lower == 'microstrategy':
                    if 'bought' in content or 'purchase' in content:
                        # BTC 수량 추출
                        btc_amounts = re.findall(r'(\d+(?:,\d+)*)\s*(?:btc|bitcoin)', content)
                        if btc_amounts:
                            amount = btc_amounts[0].replace(',', '')
                            summary_parts.append(f"마이크로스트래티지가 비트코인 {btc_amounts[0]}개를 추가 매입했습니다.")
                        else:
                            summary_parts.append("마이크로스트래티지가 비트코인을 추가 매입했습니다.")
                        
                        summary_parts.append("기업의 지속적인 비트코인 매입은 장기 강세 신호로 해석되며, 다른 기업들의 유사한 움직임을 유도할 가능성이 높습니다.")
                
                # 테슬라 처리
                elif company_lower == 'tesla':
                    if 'bought' in content or 'purchase' in content:
                        summary_parts.append("테슬라가 비트코인 매입을 재개했습니다.")
                        summary_parts.append("일론 머스크의 영향력을 고려할 때 상당한 시장 임팩트가 예상되며, 기관 투자자들의 FOMO를 자극할 수 있습니다.")
                
                # 블랙록 처리
                elif company_lower == 'blackrock':
                    if 'etf' in content:
                        if 'approved' in content:
                            summary_parts.append("세계 최대 자산운용사 블랙록의 비트코인 ETF가 승인되었습니다.")
                            summary_parts.append("이는 비트코인의 주류 금융 편입을 의미하며, 기관 자금 유입의 물꼬를 트는 역사적 사건입니다.")
                        else:
                            summary_parts.append("블랙록의 비트코인 ETF 관련 중요한 발표가 있었습니다.")
                            summary_parts.append("세계 최대 자산운용사의 움직임은 시장에 강력한 신호로 작용할 것입니다.")
            
            # 일반적인 패턴 처리
            if not summary_parts:
                # ETF 관련
                if 'etf' in content:
                    if 'approved' in content or 'approval' in content:
                        summary_parts.append("비트코인 현물 ETF 승인 소식이 전해졌습니다.")
                        summary_parts.append("ETF 승인은 기관 투자자들의 비트코인 접근성을 대폭 향상시키며, 대규모 자금 유입의 계기가 될 것으로 예상됩니다.")
                    elif 'rejected' in content or 'delay' in content:
                        summary_parts.append("비트코인 ETF 승인이 지연되거나 거부되었습니다.")
                        summary_parts.append("단기적 실망감은 있으나, 지속적인 승인 신청은 장기적으로 긍정적 신호로 평가됩니다.")
                    else:
                        summary_parts.append("비트코인 ETF 관련 중요한 발표가 있었습니다.")
                        summary_parts.append("ETF는 비트코인의 제도권 편입을 위한 핵심 수단으로 주목받고 있습니다.")
                
                # 규제 관련
                elif 'sec' in content or 'regulation' in content:
                    if any(word in content for word in ['approved', 'positive', 'favorable']):
                        summary_parts.append("미국 SEC의 비트코인 관련 긍정적 발표가 있었습니다.")
                        summary_parts.append("규제 명확성 확보는 기관 투자자들의 진입 장벽을 낮추는 핵심 요소입니다.")
                    elif any(word in content for word in ['lawsuit', 'action', 'enforcement']):
                        summary_parts.append("SEC의 암호화폐 관련 규제 조치가 발표되었습니다.")
                        summary_parts.append("단기적 불확실성은 있으나, 명확한 규제 프레임워크 구축의 과정으로 해석됩니다.")
                
                # Fed 금리 관련
                elif 'fed' in content or 'rate' in content:
                    if 'cut' in content or 'lower' in content:
                        summary_parts.append("연준의 금리 인하 결정이 발표되었습니다.")
                        summary_parts.append("금리 인하는 유동성 증가를 통해 리스크 자산인 비트코인에 긍정적 영향을 미칠 것으로 예상됩니다.")
                    elif 'hike' in content or 'increase' in content:
                        summary_parts.append("연준의 금리 인상 결정이 발표되었습니다.")
                        summary_parts.append("금리 인상은 단기적으로 비트코인에 부담이 되나, 인플레이션 헤지 수요는 지속될 것으로 보입니다.")
                
                # 해킹/보안 사건
                elif 'hack' in content or 'stolen' in content:
                    summary_parts.append("암호화폐 거래소 또는 서비스에서 보안 사건이 발생했습니다.")
                    summary_parts.append("단기적 매도 압력은 있으나, 비트코인 네트워크 자체의 보안성과는 별개의 문제로 구분해야 합니다.")
                
                # 기본 케이스
                else:
                    # 제목에서 핵심 키워드 추출
                    if any(word in content for word in ['bought', 'purchase', 'investment']):
                        summary_parts.append("대형 기관 또는 기업의 비트코인 투자 소식이 전해졌습니다.")
                        summary_parts.append("기관들의 지속적인 비트코인 채택은 장기적 가격 상승의 근본적 동력으로 작용하고 있습니다.")
                    elif any(word in content for word in ['launch', 'service', 'platform']):
                        summary_parts.append("비트코인 관련 새로운 서비스나 상품이 출시되었습니다.")
                        summary_parts.append("생태계 확장은 비트코인의 실용성과 접근성을 높여 채택률 증가에 기여할 것으로 예상됩니다.")
                    else:
                        summary_parts.append("비트코인 시장에 영향을 미칠 수 있는 중요한 발표가 있었습니다.")
                        summary_parts.append("시장 참여자들은 이번 소식이 비트코인 가격과 시장 동향에 미칠 영향을 면밀히 분석하고 있습니다.")
            
            # 금액 정보 추가
            amount_match = re.search(r'\$?([\d,]+(?:\.\d+)?)\s*(billion|million)', content)
            if amount_match and len(summary_parts) == 2:
                amount = amount_match.group(1)
                unit = amount_match.group(2)
                if 'billion' in unit:
                    summary_parts.append(f"관련 규모는 약 {amount}억 달러로 추정됩니다.")
                elif 'million' in unit:
                    summary_parts.append(f"관련 규모는 약 {amount}백만 달러로 추정됩니다.")
            
            return " ".join(summary_parts) if summary_parts else "비트코인 관련 중요한 발표가 있었습니다. 투자자들은 시장 반응을 주의 깊게 모니터링하고 있습니다."
            
        except Exception as e:
            self.logger.error(f"스마트 요약 생성 실패: {e}")
            return "비트코인 시장에 영향을 미칠 수 있는 중요한 소식이 발표되었습니다. 자세한 내용은 원문을 확인하시기 바랍니다."
    
    async def generate_report(self, event: Dict) -> str:
        """🚨 강화된 긴급 예외 리포트 생성"""
        current_time = self._get_current_time_kst()
        event_type = event.get('type', 'unknown')
        
        if event_type == 'critical_news':
            # 뉴스 정보
            title_ko = event.get('title_ko', event.get('title', ''))
            summary = event.get('summary', '')
            description = event.get('description', '')
            company = event.get('company', '')
            published_at = event.get('published_at', '')
            
            # 발행 시각 포맷팅
            pub_time_str = ""
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
                    pub_time_str = kst_time.strftime('%Y-%m-%d %H:%M')
                except:
                    pub_time_str = "시간 정보 없음"
            else:
                pub_time_str = "시간 정보 없음"
            
            # 기업명이 있으면 제목에 포함
            if company and company.lower() not in title_ko.lower():
                title_ko = f"{company} - {title_ko}"
            
            # 뉴스 타입 분류
            news_type = self._classify_news_type(event)
            
            # ML 기반 영향 예측
            ml_prediction = self._get_ml_impact_prediction(event)
            
            # 예상 변동 계산
            direction = ml_prediction.get('direction', 'neutral')
            magnitude = ml_prediction.get('magnitude', 0.5)
            
            if direction == 'bullish':
                if magnitude > 1.5:
                    impact_text = "📈 강한 호재"
                    expected_change = f"📈 상승 +{magnitude:.1f}~{magnitude+1:.1f}%"
                elif magnitude > 0.8:
                    impact_text = "📈 호재"
                    expected_change = f"📈 상승 +{magnitude:.1f}~{magnitude+0.5:.1f}%"
                else:
                    impact_text = "📈 약한 호재"
                    expected_change = f"📈 상승 +{magnitude:.1f}~{magnitude+0.3:.1f}%"
            elif direction == 'bearish':
                if magnitude > 1.5:
                    impact_text = "📉 강한 악재"
                    expected_change = f"📉 하락 -{magnitude:.1f}~{magnitude+1:.1f}%"
                elif magnitude > 0.8:
                    impact_text = "📉 악재"
                    expected_change = f"📉 하락 -{magnitude:.1f}~{magnitude+0.5:.1f}%"
                else:
                    impact_text = "📉 약한 악재"
                    expected_change = f"📉 하락 -{magnitude:.1f}~{magnitude+0.3:.1f}%"
            else:
                impact_text = "⚡ 변동성"
                expected_change = f"⚡ 변동 ±{magnitude:.1f}~{magnitude+0.5:.1f}%"
            
            # 스마트 전략 생성
            smart_strategy = self._format_smart_strategy(news_type, ml_prediction, event)
            
            # 상세 요약 생성
            detail_summary = ""
            if summary and len(summary.strip()) > 10:
                # 이미 좋은 요약이 있는 경우
                detail_summary = summary[:300]
            elif description and len(description.strip()) > 20:
                # description이 있는 경우 스마트 요약 생성
                detail_summary = self._generate_smart_summary(
                    event.get('title', ''), 
                    description, 
                    company
                )
            else:
                # title만으로도 스마트 요약 생성
                detail_summary = self._generate_smart_summary(
                    event.get('title', ''), 
                    "", 
                    company
                )
            
            # 빈 요약 방지
            if not detail_summary or len(detail_summary.strip()) < 10:
                detail_summary = "비트코인 시장에 중요한 영향을 미칠 수 있는 발표가 있었습니다. 투자자들은 시장 반응을 주의 깊게 모니터링하고 있으며, 향후 가격 동향에 주목하고 있습니다."
            
            # 리포트 생성
            report = f"""🚨 <b>BTC 긴급 예외 리포트</b>
📅 발행: {pub_time_str}
━━━━━━━━━━━━━━━

📰 <b>{title_ko}</b>

📊 <b>영향 분석</b>: {impact_text}
💹 <b>예상 변동</b>: {expected_change}
⏱️ <b>반응 시점</b>: {ml_prediction.get('timeframe', '1-6시간')}

<b>📋 핵심 내용:</b>
{detail_summary}

━━━━━━━━━━━━━━━

{smart_strategy}

━━━━━━━━━━━━━━━
⏰ {current_time}"""
            
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
            elif change < -0.03:
                recommendation = "반등 대기"
                strategy = "• 분할 매수 준비\n• 지지선 확인\n• 패닉 셀링 자제"
            else:
                recommendation = "추세 관찰"
                strategy = "• 거래량 확인\n• 지표 점검\n• 신중한 접근"
            
            report = f"""🚨 <b>BTC 가격 {severity}</b>
━━━━━━━━━━━━━━━

{emoji} <b>{abs(change*100):.1f}% {direction}</b>

💰 현재가: <b>${current_price:,.0f}</b>
📊 24시간: <b>{change*100:+.1f}%</b>

━━━━━━━━━━━━━━━

🎯 <b>추천</b>: {recommendation}

{strategy}

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
            elif ratio >= 3:
                severity = "급증"
                emoji = "📈"
                recommendation = "추세 전환 가능"
                strategy = "• 방향성 확인\n• 분할 진입\n• 거래량 지속성 확인"
            else:
                severity = "증가"
                emoji = "📊"
                recommendation = "관심 필요"
                strategy = "• 시장 모니터링\n• 소량 테스트\n• 추가 신호 대기"
            
            report = f"""🚨 <b>BTC 거래량 {severity}</b>
━━━━━━━━━━━━━━━

{emoji} 평균 대비 <b>{ratio:.1f}배</b>

📊 24시간: <b>{volume:,.0f} BTC</b>
💹 시장 관심 급증

━━━━━━━━━━━━━━━

🎯 <b>추천</b>: {recommendation}

{strategy}

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

- 포지션 점검
- 리스크 관리
- 추가 정보 수집

━━━━━━━━━━━━━━━
⏰ {current_time}"""
        
        return report
