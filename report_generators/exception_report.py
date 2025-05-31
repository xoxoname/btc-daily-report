# report_generators/exception_report.py
from .base_generator import BaseReportGenerator
from typing import Dict
from datetime import datetime
import pytz

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
            
            return f"""• {time_str} - {impact_emoji} {title}
• 영향: {impact}"""
        
        else:
            # 기본 포맷
            return f"""• {time_str} - {event.get('description', '이상 징후 감지')}
• {event.get('impact', '시장 영향 분석 중')}"""
    
    async def _generate_exception_analysis(self, event: Dict) -> str:
        """예외 분석 생성 - 변동률 예측 추가"""
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
                    return "• 비트코인과 직접적 관련성이 낮은 이벤트입니다."
                
                prompt = f"""
비트코인 시장에서 다음 예외 상황이 발생했습니다:

이벤트: {event_info['title'] or event_info['type']}
심각도: {event_info['severity']}
영향: {event_info['impact']}
설명: {event_info['description']}

이 상황에 대한 전문적인 분석을 제공해주세요:
1. 예상 변동률: 이 이벤트로 인한 비트코인 가격 변동 예상률을 +X% 또는 -X% 형태로 제시
2. 방향성: 롱/숏 중 명확한 추천
3. 시간대: 향후 몇 시간 내 예상 시나리오

간결하고 명확하게 한국어로 3-4줄로 작성하세요.
첫 줄에 반드시 예상 변동률을 포함하세요.
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "당신은 정확한 수치를 제시하는 암호화폐 분석가입니다. 반드시 구체적인 변동률(%)을 제시하세요."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.5
                )
                
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                self.logger.error(f"GPT 예외 분석 생성 실패: {e}")
        
        # 폴백 분석 (변동률 포함)
        event_type = event.get('type', 'unknown')
        impact = event.get('impact', '')
        
        if event_type == 'critical_news':
            if '호재' in impact:
                return """• 예상 변동률: <b>+2~5%</b>
• 롱 포지션 권장 (단기 상승 압력)
• 향후 4시간 내 추가 상승 예상
• 과열 구간 진입 시 분할 익절"""
            elif '악재' in impact:
                return """• 예상 변동률: <b>-3~7%</b>
• 숏 포지션 권장 (단기 하락 압력)
• 향후 4시간 내 추가 하락 예상
• 과매도 구간 진입 시 분할 익절"""
            else:
                return """• 예상 변동률: <b>±2%</b> 내외
• 관망 권장 (방향성 불명확)
• 변동성 확대 예상
• 명확한 방향 확인 후 진입"""
        
        elif event_type == 'price_anomaly':
            change = event.get('change_24h', 0)
            if change > 0:
                return """• 예상 변동률: <b>+1~3%</b> 추가 상승
• 롱 우세 (모멘텀 지속)
• FOMO 매수세 유입 중
• 고점 매수 리스크 주의"""
            else:
                return """• 예상 변동률: <b>-2~4%</b> 추가 하락
• 숏 우세 (패닉 매도)
• 단기 과매도 가능성
• 반등 타이밍 주시"""
        
        elif event_type == 'volume_anomaly':
            return """• 예상 변동률: <b>±3~5%</b> 급변동
• 대량 거래로 변동성 급증
• 방향성은 차트 확인 필요
• 손절선 타이트하게 설정"""
        
        else:
            return """• 예상 변동률: <b>±2%</b> 내외
• 불확실성 증가로 관망
• 포지션 축소 권장
• 리스크 관리 최우선"""
    
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
                            return f"""✅ {side} 포지션 유리 (수익 ${unrealized_pnl:.2f})
• 일부 익절로 원금 확보
• 나머지는 추세 따라가기
• 레버리지 {leverage}배 유지/축소"""
                        else:
                            return f"""⚠️ {side} 방향 맞음 (손실 ${abs(unrealized_pnl):.2f})
• 홀딩 권장 (방향 일치)
• 평단가 개선은 신중히
• 기존 손절선 유지"""
                    else:
                        # 불리한 방향
                        return f"""🚨 {side} 포지션 위험!
• 즉시 50% 이상 정리
• 손절선 현재가 -2%로 조정
• 반대 포지션 준비"""
                else:
                    # 포지션 없을 때
                    if total_equity > 0:
                        if '호재' in event.get('impact', ''):
                            recommended_size = min(total_equity * 0.3, 1000)  # 최대 30% 또는 $1000
                            return f"""📈 롱 진입 기회
• 추천 규모: ${recommended_size:.0f} ({recommended_size/total_equity*100:.0f}%)
• 레버리지: 3배 이하
• 분할 진입 필수"""
                        elif '악재' in event.get('impact', ''):
                            recommended_size = min(total_equity * 0.3, 1000)
                            return f"""📉 숏 진입 기회
• 추천 규모: ${recommended_size:.0f} ({recommended_size/total_equity*100:.0f}%)
• 레버리지: 3배 이하
• 분할 진입 필수"""
                        else:
                            return f"""⏸️ 관망 권장
• 자산 ${total_equity:.0f} 보존
• 방향 확인 후 진입
• 최대 15% 이내 사용"""
                    else:
                        return self._get_fallback_risk_strategy(severity, event_type)
            else:
                # severity가 critical이 아닌 경우
                if has_position:
                    return f"""📊 포지션 점검
• 손절선 재확인
• 추가 진입 보류
• 증거금 여유 확보"""
                else:
                    return f"""⚠️ 신중한 접근
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
                return """🚨 긴급 대응 필요
• 레버리지 즉시 축소
• 반대 포지션은 청산
• 뉴스 방향 따라가기"""
            else:
                return """⚠️ 포지션 정리
• 레버리지 포지션 축소
• 현물은 일부 매도
• 재진입 준비"""
        else:
            return """📊 일반 대응
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
