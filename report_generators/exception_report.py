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
    print("⚠️ ML 예측기를 찾을 수 없습니다. 기본 분석을 사용합니다.")

class ExceptionReportGenerator(BaseReportGenerator):
    """예외 상황 리포트 전담 생성기"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        
        # ML 예측기 초기화
        self.ml_predictor = None
        if ML_AVAILABLE:
            try:
                self.ml_predictor = MLPredictor()
                self.logger.info(f"ML 예측기 초기화 완료 - 정확도: {self.ml_predictor.direction_accuracy:.1%}")
            except Exception as e:
                self.logger.error(f"ML 예측기 초기화 실패: {e}")
    
    async def generate_report(self, event: Dict) -> str:
        """🚨 긴급 예외 리포트 생성"""
        current_time = self._get_current_time_kst()
        
        # 원인 요약 (더 자세하게)
        cause_summary = await self._format_detailed_exception_cause(event)
        
        # ML 기반 예측 또는 GPT 분석
        if self.ml_predictor:
            analysis = await self._generate_ml_analysis(event)
        else:
            analysis = await self._generate_exception_analysis(event)
        
        # 리스크 대응 - 동적 생성
        risk_strategy = await self._format_dynamic_risk_strategy(event)
        
        # 탐지 조건
        detection_conditions = self._format_detection_conditions(event)
        
        # ML 통계 (있을 경우)
        ml_stats = ""
        if self.ml_predictor:
            stats = self.ml_predictor.get_stats()
            ml_stats = f"\n\n<b>🤖 AI 예측 정확도</b>\n• 방향: {stats['direction_accuracy']}\n• 크기: {stats['magnitude_accuracy']}"
        
        report = f"""🚨 <b>BTC 긴급 예외 리포트</b>
📅 {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

<b>❗ 급변 원인</b>
{cause_summary}

━━━━━━━━━━━━━━━━━━━

<b>📊 AI 분석</b>
{analysis}

━━━━━━━━━━━━━━━━━━━

<b>🛡️ 대응 전략</b>
{risk_strategy}

━━━━━━━━━━━━━━━━━━━

<b>📌 탐지 사유</b>
{detection_conditions}{ml_stats}

━━━━━━━━━━━━━━━━━━━
⚡ 실시간 자동 생성 리포트"""
        
        return report
    
    async def _format_detailed_exception_cause(self, event: Dict) -> str:
        """상세한 예외 원인 포맷팅"""
        event_type = event.get('type', 'unknown')
        kst = pytz.timezone('Asia/Seoul')
        
        # 이벤트 시간 처리
        try:
            if isinstance(event.get('timestamp'), datetime):
                event_time = event['timestamp'].astimezone(kst)
            elif event.get('published_at'):
                from dateutil import parser
                event_time = parser.parse(event['published_at']).astimezone(kst)
            else:
                event_time = datetime.now(kst)
            
            time_str = event_time.strftime('%H:%M')
        except:
            time_str = datetime.now(kst).strftime('%H:%M')
        
        if event_type == 'critical_news':
            title = event.get('title', '')
            impact = event.get('impact', '')
            description = event.get('description', '')
            
            # 한글 제목 우선 사용
            if 'title_ko' in event:
                title = event['title_ko']
            
            # 이모지 추가
            impact_emoji = ""
            if '호재' in impact:
                impact_emoji = "📈"
            elif '악재' in impact:
                impact_emoji = "📉"
            else:
                impact_emoji = "⚠️"
            
            # 상세 뉴스 내용 분석
            detailed_summary = await self._extract_detailed_news_info(title, description, impact)
            
            # 뉴스 내용 요약
            news_summary = await self._summarize_news_content(title, description)
            
            return f"""• {time_str} - {impact_emoji} {news_summary}
{detailed_summary}
• 영향: {impact}"""
        
        elif event_type == 'price_anomaly':
            change = event.get('change_24h', 0) * 100
            price = event.get('current_price', 0)
            volume_change = event.get('volume_ratio', 1.0)
            
            return f"""• {time_str} - <b>가격 {abs(change):.1f}% {'급등' if change > 0 else '급락'}</b>
• 현재가: ${price:,.0f}
• {'매수' if change > 0 else '매도'}세 급증 (거래량 {volume_change:.1f}배)
• 청산 규모: ${event.get('liquidation_volume', 0):,.0f}"""
        
        elif event_type == 'volume_anomaly':
            volume = event.get('volume_24h', 0)
            ratio = event.get('ratio', 0)
            dominant_side = event.get('dominant_side', '알수없음')
            
            return f"""• {time_str} - <b>거래량 폭증 감지</b>
• 24시간 거래량: {volume:,.0f} BTC
• 평균 대비 {ratio:.1f}배 증가
• 주도 세력: {dominant_side}
• 대규모 거래 발생 중"""
        
        elif event_type == 'funding_rate_anomaly':
            rate = event.get('funding_rate', 0)
            annual = event.get('annual_rate', 0) * 100
            oi_change = event.get('open_interest_change', 0)
            
            return f"""• {time_str} - <b>펀딩비 이상 급등</b>
• 현재 펀딩비: {rate:.4f}%
• 연환산 {annual:+.1f}%
• {'롱' if rate > 0 else '숏'} 포지션 과열
• 미결제약정 변화: {oi_change:+.1f}%"""
        
        else:
            # 기본 포맷
            return f"""• {time_str} - <b>{event.get('description', '이상 징후 감지')}</b>
• {event.get('details', '세부 정보 분석 중')}
• {event.get('impact', '시장 영향 평가 중')}"""
    
    async def _summarize_news_content(self, title: str, description: str) -> str:
        """뉴스 내용을 간단히 요약"""
        content = title + ' ' + description
        
        # 암호화폐 사기 관련
        if any(word in content.lower() for word in ['scammer', 'fraud', 'scam', '사기']):
            # 금액 추출
            import re
            amount_match = re.search(r'\$?([\d,]+(?:\.\d+)?)\s*(million|billion|백만|억)', content)
            if amount_match:
                amount = amount_match.group(1).replace(',', '')
                unit = amount_match.group(2)
                
                # 해킹 손실 감소 여부 확인
                if 'decrease' in content or 'down' in content or '감소' in content or '줄어' in content:
                    return f"암호화폐 사기 피해 ${amount}{unit}, 해킹 손실은 감소 (보안 개선)"
                else:
                    return f"사기꾼들이 ${amount}{unit} 규모 암호화폐 사기 시도"
            else:
                return "암호화폐 사기 사건 발생"
        
        # 기업 비트코인 구매
        elif any(word in content.lower() for word in ['bought', 'purchase', 'buys', '구매', '매입']):
            # 회사명 추출
            companies = ['tesla', 'microstrategy', 'gamestop', 'metaplanet', '테슬라', '마이크로스트래티지', '게임스탑', '메타플래닛']
            for company in companies:
                if company.lower() in content.lower():
                    # 금액 추출
                    amount_match = re.search(r'\$?([\d,]+(?:\.\d+)?)\s*(million|billion|백만|억)', content)
                    if amount_match:
                        amount = amount_match.group(1).replace(',', '')
                        unit = amount_match.group(2)
                        return f"{company.title()}이 ${amount}{unit} 규모 비트코인 구매"
                    else:
                        return f"{company.title()}이 비트코인 추가 구매"
            return "기업의 비트코인 구매 소식"
        
        # 규제 관련
        elif any(word in content.lower() for word in ['regulation', 'sec', 'government', '규제', '정부']):
            if 'approve' in content or '승인' in content:
                return "규제 당국의 승인 소식"
            elif 'reject' in content or 'ban' in content or '거부' in content or '금지' in content:
                return "규제 당국의 제한 조치"
            else:
                return "규제 관련 소식"
        
        # 기본 요약
        else:
            # 제목이 너무 길면 축약
            if len(title) > 50:
                return title[:47] + "..."
            else:
                return title
    
    async def _extract_detailed_news_info(self, title: str, description: str, impact: str) -> str:
        """뉴스에서 상세 정보 추출"""
        details = []
        content = (title + ' ' + description).lower()
        
        # 1. 금액 정보 추출
        import re
        money_patterns = [
            (r'\$?([\d,]+\.?\d*)\s*billion', 'billion'),
            (r'\$?([\d,]+\.?\d*)\s*million', 'million'),
            (r'([\d,]+\.?\d*)\s*억\s*달러', '억 달러'),
            (r'([\d,]+\.?\d*)\s*억', '억원')
        ]
        
        for pattern, unit in money_patterns:
            matches = re.findall(pattern, content)
            if matches:
                amount = matches[0].replace(',', '')
                details.append(f"• 💰 규모: ${amount} {unit}")
                break
        
        # 2. 주요 인물/기관 추출
        key_entities = {
            'tesla': 'Tesla',
            'elon musk': 'Elon Musk',
            'microstrategy': 'MicroStrategy',
            'michael saylor': 'Michael Saylor',
            'gamestop': 'GameStop',
            'trump': 'Trump',
            'sec': 'SEC',
            'fed': '연준',
            'powell': 'Powell',
            'gensler': 'Gensler'
        }
        
        mentioned_entities = []
        for entity, display_name in key_entities.items():
            if entity in content:
                mentioned_entities.append(display_name)
        
        if mentioned_entities:
            details.append(f"• 👤 관련: {', '.join(mentioned_entities[:3])}")
        
        # 3. 시간/일정 정보
        time_indicators = {
            'today': '오늘',
            'yesterday': '어제',
            'tomorrow': '내일',
            'this week': '이번 주',
            'next week': '다음 주',
            'this month': '이번 달',
            'immediately': '즉시',
            'soon': '곧'
        }
        
        for eng, kor in time_indicators.items():
            if eng in content:
                details.append(f"• ⏰ 시기: {kor}")
                break
        
        # 4. 구체적 행동/결정
        actions = {
            'approved': '✅ 승인됨',
            'rejected': '❌ 거부됨',
            'announced': '📢 발표',
            'bought': '💵 구매',
            'sold': '💸 매도',
            'filed': '📄 신청',
            'launched': '🚀 출시',
            'partnered': '🤝 제휴',
            'invested': '💰 투자'
        }
        
        for action, emoji_text in actions.items():
            if action in content:
                details.append(f"• {emoji_text}")
                break
        
        # 5. 비트코인 관련 구체적 내용
        if 'etf' in content:
            if 'spot' in content:
                details.append("• 📊 유형: 현물 ETF")
            elif 'futures' in content:
                details.append("• 📊 유형: 선물 ETF")
        
        if any(word in content for word in ['ban', 'prohibit', '금지']):
            details.append("• ⛔ 규제: 금지/제한 조치")
        elif any(word in content for word in ['allow', 'permit', '허용']):
            details.append("• ✅ 규제: 허용/완화 조치")
        
        # 6. 시장 반응 예상
        if '호재' in impact:
            if any(word in content for word in ['major', 'significant', 'massive', '대규모']):
                details.append("• 📊 예상: 강한 상승 압력")
            else:
                details.append("• 📊 예상: 점진적 상승")
        elif '악재' in impact:
            if any(word in content for word in ['crash', 'plunge', 'collapse', '폭락']):
                details.append("• 📊 예상: 급락 위험")
            else:
                details.append("• 📊 예상: 하락 압력")
        
        # 7. 예상 시나리오 추가
        expected_scenario = self._generate_expected_scenario(content, impact)
        if expected_scenario:
            details.append(f"• 📊 예상: {expected_scenario}")
        
        return '\n'.join(details) if details else "• 📋 추가 세부사항 분석 중"
    
    def _generate_expected_scenario(self, content: str, impact: str) -> str:
        """예상 시나리오 생성"""
        content_lower = content.lower()
        
        # 사기/해킹 관련
        if any(word in content_lower for word in ['scam', 'fraud', 'hack', '사기', '해킹']):
            if 'decrease' in content_lower or '감소' in content_lower:
                return "보안 개선으로 투자 심리 회복, 단기 횡보 후 상승 가능"
            else:
                return "투자 심리 위축, 1-2일 내 -0.3~0.5% 하락 후 회복"
        
        # 기업 구매
        elif any(word in content_lower for word in ['bought', 'purchase', '구매']):
            return "기관 매수세 유입, 2-4시간 내 +0.5~1.5% 상승"
        
        # 규제 승인
        elif 'approve' in content_lower or '승인' in content_lower:
            return "규제 불확실성 해소, 점진적 상승세 지속"
        
        # 규제 거부/금지
        elif any(word in content_lower for word in ['reject', 'ban', '거부', '금지']):
            return "규제 리스크 확대, 단기 조정 후 바닥 확인"
        
        # 기본
        elif '호재' in impact:
            return "긍정적 모멘텀 형성, 단기 상승 가능"
        elif '악재' in impact:
            return "부정적 압력 증가, 지지선 테스트 예상"
        else:
            return "시장 관망세, 추가 재료 대기"
    
    async def _generate_ml_analysis(self, event: Dict) -> str:
        """ML 기반 예측 분석"""
        try:
            # 시장 데이터 수집
            market_data = await self._get_market_data_for_ml()
            
            # ML 예측 수행
            prediction = await self.ml_predictor.predict_impact(event, market_data)
            
            # 포맷팅
            direction_text = {
                'up': '📈 <b>상승</b>',
                'down': '📉 <b>하락</b>',
                'neutral': '➡️ <b>횡보</b>'
            }
            
            analysis = f"""• <b>예측 방향</b>: {direction_text.get(prediction['direction'], '불명')}
• <b>예상 변동률</b>: <b>{prediction['magnitude']:.1f}%</b>
• <b>신뢰도</b>: <b>{prediction['confidence']*100:.0f}%</b>
• <b>시장 영향력</b>: <b>{prediction['market_influence']:.0f}%</b>
• <b>예상 시간대</b>: {prediction['timeframe']}
• <b>리스크 수준</b>: {prediction['risk_level']}
• <b>추천</b>: <b>{prediction['recommendation']}</b>

━━━━━━━━━━━━━━━━━━━

<b>📋 상세 분석</b>
{prediction['detailed_analysis']}"""
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"ML 분석 실패: {e}")
            # 폴백으로 기존 분석 사용
            return await self._generate_exception_analysis(event)
    
    async def _get_market_data_for_ml(self) -> Dict:
        """ML을 위한 시장 데이터 수집"""
        market_data = {
            'trend': 'neutral',
            'volatility': 0.02,
            'volume_ratio': 1.0,
            'rsi': 50,
            'fear_greed': 50,
            'btc_dominance': 50
        }
        
        try:
            # 현재 가격 정보
            if self.bitget_client:
                ticker = await self.bitget_client.get_ticker('BTCUSDT')
                if ticker:
                    # 24시간 변화율로 트렌드 판단
                    change_24h = float(ticker.get('changeUtc', 0))
                    if change_24h > 0.02:
                        market_data['trend'] = 'bullish'
                    elif change_24h < -0.02:
                        market_data['trend'] = 'bearish'
                    
                    # 거래량 비율 (평균 대비)
                    volume = float(ticker.get('baseVolume', 0))
                    market_data['volume_ratio'] = volume / 50000 if volume > 0 else 1.0
            
            # 기술 지표
            if self.indicator_system:
                # RSI
                rsi_data = await self.indicator_system.calculate_rsi()
                if rsi_data:
                    market_data['rsi'] = rsi_data.get('value', 50)
                
                # 변동성
                volatility_data = await self.indicator_system.calculate_volatility()
                if volatility_data:
                    market_data['volatility'] = volatility_data.get('value', 0.02)
            
            # Fear & Greed Index (실제 API 연동 필요)
            # 여기서는 RSI 기반으로 대략 추정
            if market_data['rsi'] > 70:
                market_data['fear_greed'] = 80  # Greed
            elif market_data['rsi'] < 30:
                market_data['fear_greed'] = 20  # Fear
            else:
                market_data['fear_greed'] = 50  # Neutral
            
        except Exception as e:
            self.logger.error(f"시장 데이터 수집 실패: {e}")
        
        return market_data
    
    async def _generate_exception_analysis(self, event: Dict) -> str:
        """예외 분석 생성 - 현실적인 분석 (ML 없을 때)"""
        if self.openai_client:
            try:
                # 이벤트 정보 정리
                event_info = {
                    'type': event.get('type', 'unknown'),
                    'severity': event.get('severity', 'medium'),
                    'title': event.get('title', ''),
                    'impact': event.get('impact', ''),
                    'description': event.get('description', '')
                }
                
                # 비트코인 관련성 확인
                is_bitcoin_related = any(
                    keyword in str(event_info).lower() 
                    for keyword in ['bitcoin', 'btc', '비트코인', 'crypto', '암호화폐']
                )
                
                if not is_bitcoin_related and event_info['type'] != 'critical_news':
                    return """• <b>뉴스 해석</b>: 비트코인과 간접적 관련
• <b>시장 영향력</b>: <b>5%</b> 미만
• <b>예상 변동률</b>: <b>무영향</b>
• <b>추천 포지션</b>: <b>기존 전략 유지</b>
• <b>예상 시나리오</b>: 영향 없음"""
                
                prompt = f"""
비트코인 시장에서 다음 예외 상황이 발생했습니다:

이벤트: {event_info['title'] or event_info['type']}
심각도: {event_info['severity']}
영향: {event_info['impact']}
설명: {event_info['description']}

다음 형식으로 현실적이고 정확한 분석을 제공하세요:

뉴스 해석: (핵심 내용을 한국인이 이해하기 쉽게 30자 이내로 설명)
시장 영향력: X% (이 뉴스가 비트코인 가격에 미칠 영향을 0-100%로 평가)
예상 변동률: ±X% (실제 예상되는 가격 변동 범위)
추천 포지션: 롱/숏/관망 (명확한 근거와 함께)
예상 시나리오: (구체적인 시간대와 함께 예상되는 시장 움직임 설명)

중요: 
- 이미 시장에 반영된 뉴스인지 확인
- 과장하지 말고 현실적으로 평가
- "비트코인 우세"같은 경우는 이미 진행중인 상황이므로 추가 상승 여력은 제한적
- 시장 영향력은 대부분 20% 미만이며, 50%를 넘는 경우는 극히 드물다
- 암호화폐 사기나 해킹 관련 뉴스는 정확히 해석하여 설명
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "당신은 보수적이고 현실적인 암호화폐 분석가입니다. 과장하지 않고 정확한 분석을 제공합니다. 한국인이 이해하기 쉽게 설명합니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=400,
                    temperature=0.3
                )
                
                analysis = response.choices[0].message.content.strip()
                
                # 포맷팅
                lines = analysis.split('\n')
                formatted_analysis = ""
                for line in lines:
                    if ':' in line:
                        parts = line.split(':', 1)
                        key = parts[0].strip()
                        value = parts[1].strip()
                        
                        # 핵심 값들을 굵게 표시
                        if any(k in key for k in ['시장 영향력', '예상 변동률', '추천 포지션']):
                            # 값 부분만 굵게
                            if '%' in value:
                                # 퍼센트 값 찾기
                                import re
                                match = re.search(r'([\d.±-]+%)', value)
                                if match:
                                    value = value.replace(match.group(1), f"<b>{match.group(1)}</b>")
                            elif any(pos in value for pos in ['롱', '숏', '관망']):
                                # 포지션 추천 굵게
                                for pos in ['롱', '숏', '관망']:
                                    if pos in value:
                                        value = value.replace(pos, f"<b>{pos}</b>")
                        
                        formatted_analysis += f"• <b>{key}</b>: {value}\n"
                
                return formatted_analysis.strip()
                
            except Exception as e:
                self.logger.error(f"GPT 예외 분석 생성 실패: {e}")
        
        # 폴백 분석 (더 현실적으로)
        return self._get_realistic_fallback_analysis(event)
    
    def _get_realistic_fallback_analysis(self, event: Dict) -> str:
        """현실적인 폴백 분석"""
        event_type = event.get('type', 'unknown')
        impact = event.get('impact', '')
        title = event.get('title', '')
        
        # 비트코인 우세 관련
        if '우세' in title or 'dominance' in title.lower():
            return """• <b>뉴스 해석</b>: BTC 시장 점유율 상승 지속
• <b>시장 영향력</b>: <b>15%</b> (단기 모멘텀 강화)
• <b>예상 변동률</b>: <b>±0.5%</b> 내외
• <b>추천 포지션</b>: <b>관망</b> (이미 반영된 움직임)
• <b>예상 시나리오</b>: 4-6시간 내 횡보 후 방향 결정"""
        
        # 사기/해킹 관련
        if any(word in title.lower() for word in ['scam', 'fraud', 'hack', '사기', '해킹']):
            if 'decrease' in title.lower() or '감소' in title:
                return """• <b>뉴스 해석</b>: 암호화폐 보안 개선 신호
• <b>시장 영향력</b>: <b>10%</b> (간접적 호재)
• <b>예상 변동률</b>: <b>±0.3%</b> 내외
• <b>추천 포지션</b>: <b>기존 유지</b>
• <b>예상 시나리오</b>: 투자 심리 점진적 회복"""
            else:
                return """• <b>뉴스 해석</b>: 암호화폐 사기 피해 발생
• <b>시장 영향력</b>: <b>15%</b> (투자 심리 위축)
• <b>예상 변동률</b>: <b>-0.3~0.5%</b>
• <b>추천 포지션</b>: <b>관망</b> (과도한 공포 시 매수 고려)
• <b>예상 시나리오</b>: 단기 매도압력 후 1-2일 내 회복"""
        
        # 기업 매수 뉴스
        if any(word in title.lower() for word in ['bought', 'purchase', '구매', '매입']):
            return """• <b>뉴스 해석</b>: 기업의 BTC 추가 매입
• <b>시장 영향력</b>: <b>25%</b> (긍정적 신호)
• <b>예상 변동률</b>: <b>+0.5~1.5%</b>
• <b>추천 포지션</b>: <b>소량 롱</b> (단기 상승 가능)
• <b>예상 시나리오</b>: 1-2시간 내 반응, 기관 매수세 유입"""
        
        # 일반적인 경우
        if event_type == 'critical_news':
            if '호재' in impact:
                return """• <b>뉴스 해석</b>: 긍정적 시장 소식
• <b>시장 영향력</b>: <b>20%</b>
• <b>예상 변동률</b>: <b>+0.3~1%</b>
• <b>추천 포지션</b>: <b>소량 롱</b> 고려
• <b>예상 시나리오</b>: 2-4시간 내 점진적 상승"""
            elif '악재' in impact:
                return """• <b>뉴스 해석</b>: 부정적 시장 소식
• <b>시장 영향력</b>: <b>25%</b>
• <b>예상 변동률</b>: <b>-0.5~1.5%</b>
• <b>추천 포지션</b>: <b>리스크 관리</b> 우선
• <b>예상 시나리오</b>: 즉시~2시간 내 하락 압력"""
            else:
                return """• <b>뉴스 해석</b>: 중립적 시장 소식
• <b>시장 영향력</b>: <b>10%</b> 미만
• <b>예상 변동률</b>: <b>±0.3%</b> 내외
• <b>추천 포지션</b>: <b>관망</b>
• <b>예상 시나리오</b>: 추가 재료 대기"""
        
        elif event_type == 'price_anomaly':
            change = event.get('change_24h', 0)
            if abs(change) > 0.03:  # 3% 이상
                return f"""• <b>가격 변동</b>: {change*100:+.1f}% 급변
• <b>시장 영향력</b>: <b>이미 100% 반영</b>
• <b>예상 변동률</b>: <b>{'+0.5~1%' if change > 0 else '-0.5~1%'}</b> 추가
• <b>추천 포지션</b>: <b>{'역추세 숏' if change > 0 else '반등 롱'}</b> 준비
• <b>예상 시나리오</b>: 30분~1시간 내 조정"""
            else:
                return f"""• <b>가격 변동</b>: {change*100:+.1f}% 변동
• <b>시장 영향력</b>: <b>50% 반영</b>
• <b>예상 변동률</b>: <b>±0.5%</b> 내외
• <b>추천 포지션</b>: <b>관망</b>
• <b>예상 시나리오</b>: 1-2시간 관찰 필요"""
        
        else:
            return """• <b>이벤트 유형</b>: 일반 시장 변동
• <b>시장 영향력</b>: <b>15%</b> 미만
• <b>예상 변동률</b>: <b>±0.3%</b> 내외
• <b>추천 포지션</b>: <b>기존 전략 유지</b>
• <b>예상 시나리오</b>: 점진적 반영"""
    
    async def _format_dynamic_risk_strategy(self, event: Dict) -> str:
        """동적 리스크 전략 생성"""
        severity = event.get('severity', 'medium')
        event_type = event.get('type', 'unknown')
        
        # 계정 정보 가져오기
        try:
            position_info = await self._get_position_info()
            account_info = await self._get_account_info()
            
            has_position = position_info.get('has_position', False)
            total_equity = account_info.get('total_equity', 0)
            
            if severity == 'critical':
                if has_position:
                    side = position_info.get('side', '')
                    unrealized_pnl = position_info.get('unrealized_pnl', 0)
                    leverage = position_info.get('leverage', 1)
                    
                    # 포지션 방향과 이벤트 영향 분석
                    event_impact = event.get('impact', '')
                    
                    if ('호재' in event_impact and side == '롱') or ('악재' in event_impact and side == '숏'):
                        # 유리한 방향
                        if unrealized_pnl > 0:
                            return f"""✅ <b>{side} 포지션 유리</b> (수익 ${unrealized_pnl:.2f})
• 일부 익절로 원금 확보
• 나머지는 추세 따라가기
• 레버리지 {leverage}배 유지/축소"""
                        else:
                            return f"""⚠️ <b>{side} 방향 맞음</b> (손실 ${abs(unrealized_pnl):.2f})
• 홀딩 권장 (방향 일치)
• 평단가 개선은 신중히
• 기존 손절선 유지"""
                    else:
                        # 불리한 방향
                        return f"""🚨 <b>{side} 포지션 위험!</b>
• 즉시 50% 이상 정리
• 손절선 현재가 -2%로 조정
• 반대 포지션 준비"""
                else:
                    # 포지션 없을 때
                    if total_equity > 0:
                        if '호재' in event.get('impact', ''):
                            recommended_size = min(total_equity * 0.3, 1000)  # 최대 30% 또는 $1000
                            return f"""📈 <b>롱 진입 기회</b>
• 추천 규모: ${recommended_size:.0f} ({recommended_size/total_equity*100:.0f}%)
• 레버리지: 3배 이하
• 분할 진입 필수"""
                        elif '악재' in event.get('impact', ''):
                            recommended_size = min(total_equity * 0.3, 1000)
                            return f"""📉 <b>숏 진입 기회</b>
• 추천 규모: ${recommended_size:.0f} ({recommended_size/total_equity*100:.0f}%)
• 레버리지: 3배 이하
• 분할 진입 필수"""
                        else:
                            return f"""⏸️ <b>관망 권장</b>
• 자산 ${total_equity:.0f} 보존
• 방향 확인 후 진입
• 최대 15% 이내 사용"""
                    else:
                        return self._get_fallback_risk_strategy(severity, event_type)
            else:
                # severity가 critical이 아닌 경우
                if has_position:
                    return f"""📊 <b>포지션 점검</b>
• 손절선 재확인
• 추가 진입 보류
• 증거금 여유 확보"""
                else:
                    return f"""⚠️ <b>신중한 접근</b>
• 소량 테스트만
• 방향성 확인 대기
• 리스크 관리 우선"""
                    
        except Exception as e:
            self.logger.error(f"동적 리스크 전략 생성 실패: {e}")
            return self._get_fallback_risk_strategy(severity, event_type)
    
    def _get_fallback_risk_strategy(self, severity: str, event_type: str) -> str:
        """폴백 리스크 전략"""
        if severity == 'critical':
            if event_type == 'critical_news':
                return """🚨 <b>긴급 대응 필요</b>
• 레버리지 즉시 축소
• 반대 포지션은 청산
• 뉴스 방향 따라가기"""
            else:
                return """⚠️ <b>포지션 정리</b>
• 레버리지 포지션 축소
• 현물은 일부 매도
• 재진입 준비"""
        else:
            return """📊 <b>일반 대응</b>
• 현재 포지션 유지
• 추가 진입 보류
• 시장 관찰 지속"""
    
    def _format_detection_conditions(self, event: Dict) -> str:
        """탐지 조건 포맷팅 - 더 이해하기 쉽게"""
        event_type = event.get('type', 'unknown')
        
        conditions = []
        
        if event_type == 'price_anomaly':
            change = event.get('change_24h', 0) * 100
            conditions.append(f"• 가격 {abs(change):.1f}% {'급등' if change > 0 else '급락'} 감지")
        
        elif event_type == 'volume_anomaly':
            ratio = event.get('ratio', 0)
            volume = event.get('volume_24h', 0)
            conditions.append(f"• 거래량 {ratio:.1f}배 폭증 ({volume:,.0f} BTC)")
        
        elif event_type == 'funding_rate_anomaly':
            rate = event.get('funding_rate', 0)
            conditions.append(f"• 펀딩비 {abs(rate):.4f}% {'상승' if rate > 0 else '하락'}")
        
        elif event_type == 'critical_news':
            conditions.append(f"• 중요 뉴스 발생")
        
        # 추가 조건들을 더 이해하기 쉽게
        if event.get('smart_money_alert'):
            conditions.append("• 고래 움직임 포착")
        
        if event.get('liquidation_alert'):
            conditions.append("• 대량 청산 발생")
        
        if len(conditions) == 0:
            conditions.append("• AI 이상 징후 감지")
        
        return '\n'.join(conditions[:3])  # 최대 3개만 표시
