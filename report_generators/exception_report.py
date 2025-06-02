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
            
            # 상세 요약 생성 (2-3문장)
            if summary:
                detail_summary = summary[:300]
            elif description:
                # description에서 핵심 정보 추출해서 요약 생성
                detail_summary = self._extract_key_details(description, title_ko)
            else:
                detail_summary = "상세 정보를 수집 중입니다."
            
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
    
    def _extract_key_details(self, description: str, title: str) -> str:
        """설명에서 핵심 정보 추출 (2-3문장 요약)"""
        try:
            # 주요 정보 패턴 찾기
            patterns = [
                r'\$[\d,]+(?:\.\d+)?\s*(?:billion|million)',  # 금액
                r'\d+(?:,\d+)*\s*(?:bitcoin|btc)',           # BTC 수량
                r'(?:announced|launched|approved|bought|purchased|adds)',  # 행동
                r'(?:tesla|microstrategy|sberbank|blackrock|sec|etf)',     # 주요 엔티티
            ]
            
            key_info = []
            content = description.lower()
            
            # 금액 정보
            amount_match = re.search(r'\$?([\d,]+(?:\.\d+)?)\s*(billion|million)', content)
            if amount_match:
                amount = amount_match.group(1)
                unit = amount_match.group(2)
                key_info.append(f"{amount}{unit[0].upper()}")
            
            # BTC 수량
            btc_match = re.search(r'([\d,]+)\s*(?:bitcoin|btc)', content)
            if btc_match:
                btc_amount = btc_match.group(1)
                key_info.append(f"BTC {btc_amount}개")
            
            # 기본 요약 생성
            sentences = description.split('.')[:3]  # 처음 3문장
            clean_sentences = []
            
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 20 and not sentence.startswith('http'):
                    clean_sentences.append(sentence)
                if len(clean_sentences) >= 2:  # 2문장으로 제한
                    break
            
            if clean_sentences:
                summary = '. '.join(clean_sentences)
                if key_info:
                    summary += f" (규모: {', '.join(key_info)})"
                return summary + "."
            else:
                return "중요한 비트코인 관련 발표가 있었습니다. 시장 반응을 주시하세요."
                
        except Exception as e:
            self.logger.error(f"핵심 정보 추출 실패: {e}")
            return description[:200] + "..." if len(description) > 200 else description
