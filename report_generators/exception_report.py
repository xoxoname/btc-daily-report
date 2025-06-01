# report_generators/exception_report.py
from .base_generator import BaseReportGenerator
from typing import Dict
from datetime import datetime
import pytz
import re

class ExceptionReportGenerator(BaseReportGenerator):
    """예외 상황 리포트 전담 생성기"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
    
    async def generate_report(self, event: Dict) -> str:
        """🚨 긴급 예외 리포트 생성"""
        current_time = self._get_current_time_kst()
        
        # 원인 요약
        cause_summary = self._format_exception_cause(event)
        
        # GPT 분석 (변동률 포함)
        gpt_analysis = await self._generate_exception_analysis(event)
        
        # 리스크 대응 - 동적 생성
        risk_strategy = await self._format_dynamic_risk_strategy(event)
        
        # 탐지 조건
        detection_conditions = self._format_detection_conditions(event)
        
        report = f"""🚨 <b>BTC 긴급 예외 리포트</b>
📅 {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

<b>❗ 급변 원인</b>
{cause_summary}

━━━━━━━━━━━━━━━━━━━

<b>📊 AI 분석</b>
{gpt_analysis}

━━━━━━━━━━━━━━━━━━━

<b>🛡️ 대응 전략</b>
{risk_strategy}

━━━━━━━━━━━━━━━━━━━

<b>📌 탐지 사유</b>
{detection_conditions}

━━━━━━━━━━━━━━━━━━━
⚡ 실시간 자동 생성 리포트"""
        
        return report
    
    def _format_exception_cause(self, event: Dict) -> str:
        """예외 원인 포맷팅 - 시간 추가"""
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
        
        if event_type == 'price_anomaly':
            change = event.get('change_24h', 0) * 100
            price = event.get('current_price', 0)
            return f"""• {time_str} - 가격 {abs(change):.1f}% {'급등' if change > 0 else '급락'}
• 현재가: ${price:,.0f}
• {'매수' if change > 0 else '매도'}세 급증"""
        
        elif event_type == 'volume_anomaly':
            volume = event.get('volume_24h', 0)
            ratio = event.get('ratio', 0)
            return f"""• {time_str} - 거래량 폭증 감지
• 24시간 거래량: {volume:,.0f} BTC
• 평균 대비 {ratio:.1f}배 증가
• 대규모 거래 발생 중"""
        
        elif event_type == 'funding_rate_anomaly':
            rate = event.get('funding_rate', 0)
            annual = event.get('annual_rate', 0) * 100
            return f"""• {time_str} - 펀딩비 이상 급등
• 현재 펀딩비: {rate:.4f}%
• 연환산 {annual:+.1f}%
• {'롱' if rate > 0 else '숏'} 포지션 과열"""
        
        elif event_type == 'critical_news':
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
            
            # 뉴스 내용 요약 추가
            summary = self._summarize_news_content(title, description, impact)
            
            return f"""• {time_str} - {impact_emoji} {title}
• 요약: {summary}
• 영향: {impact}"""
        
        else:
            # 기본 포맷
            return f"""• {time_str} - {event.get('description', '이상 징후 감지')}
• {event.get('impact', '시장 영향 분석 중')}"""
    
    def _summarize_news_content(self, title: str, description: str, impact: str) -> str:
        """뉴스 내용을 간단히 요약"""
        content = (title + ' ' + description).lower()
        
        # 비트코인 우세 관련
        if 'dominance' in content or '우세' in content or '점유율' in content:
            return "BTC 시장 점유율 상승, 알트코인 자금 이동"
        
        # 기업 매수 관련
        if any(word in content for word in ['bought', 'purchase', '구매', '매입']):
            # 기업명 찾기
            companies = ['tesla', 'microstrategy', 'gamestop', 'square']
            for company in companies:
                if company in content:
                    return f"{company.capitalize()}의 BTC 추가 매입 확인"
            return "기업의 BTC 매입 소식"
        
        # 규제 관련
        if any(word in content for word in ['sec', 'regulation', '규제', 'ban', '금지']):
            if '호재' in impact:
                return "규제 완화 또는 긍정적 정책 발표"
            else:
                return "규제 강화 우려 또는 부정적 정책"
        
        # ETF 관련
        if 'etf' in content:
            if 'approved' in content or '승인' in content:
                return "비트코인 ETF 승인 소식"
            elif 'reject' in content or '거부' in content:
                return "비트코인 ETF 거부 소식"
            else:
                return "비트코인 ETF 관련 진전"
        
        # 기본 요약
        if '호재' in impact:
            return "긍정적 시장 소식"
        elif '악재' in impact:
            return "부정적 시장 소식"
        else:
            return "시장 변동 요인 발생"
    
    async def _generate_exception_analysis(self, event: Dict) -> str:
        """예외 분석 생성 - 현실적인 분석"""
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
                    return """• <b>뉴스 요약</b>: 비트코인과 간접적 관련
• <b>시장 영향력</b>: <b>5%</b> 미만
• <b>예상 변동률</b>: <b>무영향</b>
• <b>추천 포지션</b>: <b>기존 전략 유지</b>
• <b>예상 시간대</b>: 영향 없음"""
                
                prompt = f"""
비트코인 시장에서 다음 예외 상황이 발생했습니다:

이벤트: {event_info['title'] or event_info['type']}
심각도: {event_info['severity']}
영향: {event_info['impact']}
설명: {event_info['description']}

다음 형식으로 현실적이고 정확한 분석을 제공하세요:

1. 뉴스 요약: (핵심 내용을 20자 이내로)
2. 시장 영향력: X% (이 뉴스가 비트코인 가격에 미칠 영향을 0-100%로 평가)
3. 예상 변동률: ±X% (실제 예상되는 가격 변동 범위)
4. 추천 포지션: 롱/숏/관망 (명확한 근거와 함께)
5. 예상 시간대: (영향이 나타날 시간대)

중요: 
- 이미 시장에 반영된 뉴스인지 확인
- 과장하지 말고 현실적으로 평가
- "비트코인 우세"같은 경우는 이미 진행중인 상황이므로 추가 상승 여력은 제한적
- 시장 영향력은 대부분 20% 미만이며, 50%를 넘는 경우는 극히 드물다
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "당신은 보수적이고 현실적인 암호화폐 분석가입니다. 과장하지 않고 정확한 분석을 제공합니다."},
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
                                match = re.search(r'([\d.]+%)', value)
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
            return """• <b>뉴스 요약</b>: BTC 시장 점유율 상승 지속
• <b>시장 영향력</b>: <b>15%</b> (단기 모멘텀 강화)
• <b>예상 변동률</b>: <b>±0.5%</b> 내외
• <b>추천 포지션</b>: <b>관망</b> (이미 반영된 움직임)
• <b>예상 시간대</b>: 4-6시간 내 횡보"""
        
        # 기업 매수 뉴스
        if any(word in title.lower() for word in ['bought', 'purchase', '구매', '매입']):
            return """• <b>뉴스 요약</b>: 기업의 BTC 추가 매입
• <b>시장 영향력</b>: <b>25%</b> (긍정적 신호)
• <b>예상 변동률</b>: <b>+0.5~1.5%</b>
• <b>추천 포지션</b>: <b>소량 롱</b> (단기 상승 가능)
• <b>예상 시간대</b>: 1-2시간 내 반응"""
        
        # 일반적인 경우
        if event_type == 'critical_news':
            if '호재' in impact:
                return """• <b>뉴스 요약</b>: 긍정적 시장 소식
• <b>시장 영향력</b>: <b>20%</b>
• <b>예상 변동률</b>: <b>+0.3~1%</b>
• <b>추천 포지션</b>: <b>소량 롱</b> 고려
• <b>예상 시간대</b>: 2-4시간 내 반응"""
            elif '악재' in impact:
                return """• <b>뉴스 요약</b>: 부정적 시장 소식
• <b>시장 영향력</b>: <b>25%</b>
• <b>예상 변동률</b>: <b>-0.5~1.5%</b>
• <b>추천 포지션</b>: <b>리스크 관리</b> 우선
• <b>예상 시간대</b>: 즉시~2시간"""
            else:
                return """• <b>뉴스 요약</b>: 중립적 시장 소식
• <b>시장 영향력</b>: <b>10%</b> 미만
• <b>예상 변동률</b>: <b>±0.3%</b> 내외
• <b>추천 포지션</b>: <b>관망</b>
• <b>예상 시간대</b>: 불확실"""
        
        elif event_type == 'price_anomaly':
            change = event.get('change_24h', 0)
            if abs(change) > 0.03:  # 3% 이상
                return f"""• <b>가격 변동</b>: {change*100:+.1f}% 급변
• <b>시장 영향력</b>: <b>이미 100% 반영</b>
• <b>예상 변동률</b>: <b>{'+0.5~1%' if change > 0 else '-0.5~1%'}</b> 추가
• <b>추천 포지션</b>: <b>{'역추세 숏' if change > 0 else '반등 롱'}</b> 준비
• <b>예상 시간대</b>: 30분~1시간 내 조정"""
            else:
                return f"""• <b>가격 변동</b>: {change*100:+.1f}% 변동
• <b>시장 영향력</b>: <b>50% 반영</b>
• <b>예상 변동률</b>: <b>±0.5%</b> 내외
• <b>추천 포지션</b>: <b>관망</b>
• <b>예상 시간대</b>: 1-2시간 관찰"""
        
        else:
            return """• <b>이벤트 유형</b>: 일반 시장 변동
• <b>시장 영향력</b>: <b>15%</b> 미만
• <b>예상 변동률</b>: <b>±0.3%</b> 내외
• <b>추천 포지션</b>: <b>기존 전략 유지</b>
• <b>예상 시간대</b>: 점진적 반영"""
    
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
