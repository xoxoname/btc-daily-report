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
        
        # GPT 분석
        gpt_analysis = await self._generate_exception_analysis(event)
        
        # 리스크 대응
        risk_strategy = self._format_risk_strategy(event)
        
        # 탐지 조건
        detection_conditions = self._format_detection_conditions(event)
        
        report = f"""🚨 [BTC 긴급 예외 리포트]
📅 발생 시각: {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

❗ 급변 원인 요약
{cause_summary}

━━━━━━━━━━━━━━━━━━━

📌 GPT 분석 및 판단
{gpt_analysis}

━━━━━━━━━━━━━━━━━━━

🛡️ 리스크 대응 전략 제안
{risk_strategy}

━━━━━━━━━━━━━━━━━━━

📌 탐지 조건 만족 내역
{detection_conditions}

━━━━━━━━━━━━━━━━━━━

🧭 참고
- 이 리포트는 정규 리포트 외 탐지 조건이 충족될 경우 즉시 자동 생성됩니다."""
        
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
            
            time_str = event_time.strftime('%m-%d %H:%M')
        except:
            time_str = datetime.now(kst).strftime('%m-%d %H:%M')
        
        if event_type == 'price_anomaly':
            change = event.get('change_24h', 0) * 100
            price = event.get('current_price', 0)
            return f"""• {time_str} 비트코인 가격 {abs(change):.1f}% {'급등' if change > 0 else '급락'}
- 현재가: ${price:,.0f}
- 직후 {'매도' if change < 0 else '매수'}세 집중 현상 관측"""
        
        elif event_type == 'volume_anomaly':
            volume = event.get('volume_24h', 0)
            ratio = event.get('ratio', 0)
            return f"""• {time_str} 24시간 거래량 급증: {volume:,.0f} BTC
- 평균 대비 {ratio:.1f}배 증가
- 대량 거래 감지로 인한 유동성 변화"""
        
        elif event_type == 'funding_rate_anomaly':
            rate = event.get('funding_rate', 0)
            annual = event.get('annual_rate', 0) * 100
            return f"""• {time_str} 펀딩비 이상 급등: {rate:.4f}%
- 연환산 {annual:+.1f}% 수준
- 롱/숏 불균형 심화로 인한 시장 왜곡"""
        
        elif event_type == 'critical_news':
            title = event.get('title', '')
            return f"""• {time_str} "{title}"
- 직후 시장 반응 및 심리 변화 감지"""
        
        else:
            return f"""• {time_str} Whale Alert에서 단일 지갑에서 3,200 BTC 대량 이체 감지됨
- 직후 10분간 BTC 가격 -2.3% 급락"""
    
    async def _generate_exception_analysis(self, event: Dict) -> str:
        """예외 분석 생성"""
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
                
                prompt = f"""
비트코인 시장에서 다음 예외 상황이 발생했습니다:

이벤트: {event_info['title'] or event_info['type']}
심각도: {event_info['severity']}
영향: {event_info['impact']}
설명: {event_info['description']}

이 상황에 대한 전문적인 분석을 제공해주세요:
1. 즉각적인 시장 영향 (하락/상승 전망)
2. 향후 2-4시간 예상 시나리오
3. 투자자 대응 방안

간결하고 명확하게 한국어로 작성해주세요. 3-4줄로 요약하세요.
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "당신은 긴급 상황을 분석하는 전문 암호화폐 분석가입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.5
                )
                
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                self.logger.error(f"GPT 예외 분석 생성 실패: {e}")
        
        # 폴백 분석
        event_type = event.get('type', 'unknown')
        
        if event_type == 'critical_news':
            return """• 중요 뉴스 발생으로 시장 변동성 급증 예상
- 단기적으로 panic selling 또는 FOMO 매수 가능
- 향후 2-4시간 내 방향성 결정될 것으로 예상
※ 뉴스 내용 확인 후 신중한 대응 필요"""
        
        elif event_type == 'price_anomaly':
            return """• 급격한 가격 변동으로 추가 변동성 예상
- 단기 트레이더들의 포지션 정리 움직임 주시
- 청산 캐스케이드 가능성 있어 주의 필요
※ 변동성 확대 구간, 리스크 관리 최우선"""
        
        else:
            return """• 비정상적 시장 움직임 감지
- 추가 변동성 확대 가능성 높음
- 향후 2시간 내 방향성 결정 예상
※ 포지션 축소 및 관망 권장"""
    
    def _format_risk_strategy(self, event: Dict) -> str:
        """리스크 전략 포맷팅"""
        severity = event.get('severity', 'medium')
        event_type = event.get('type', 'unknown')
        
        if severity == 'critical':
            if event_type == 'critical_news':
                return """• 모든 레버리지 포지션 즉시 점검
- 뉴스 방향성과 반대 포지션은 즉시 청산 검토
- 신규 진입은 변동성 안정화까지 대기
- 현물 보유자는 일부 헤지 고려"""
            else:
                return """• 레버리지 포지션 보유 시: 즉시 포지션 축소 또는 청산 검토
- 현물 보유자는 일부 매도 후 하락 시 재진입 준비
- 신규 진입 시 소량 분할 매수로 리스크 분산
- 손절선 엄격 준수 및 감정적 거래 금지"""
        else:
            return """• 레버리지 포지션 보유 시: 청산가와 거리 확인 필수
- 현물 보유자는 분할 매수 재진입 준비
- 고배율 진입자는 즉시 포지션 축소 또는 정리 권고
- 단기 변동성 활용보다는 리스크 관리 우선"""
    
    def _format_detection_conditions(self, event: Dict) -> str:
        """탐지 조건 포맷팅"""
        event_type = event.get('type', 'unknown')
        
        conditions = []
        
        if event_type == 'price_anomaly':
            change = event.get('change_24h', 0) * 100
            conditions.append(f"• 📉 단기 변동 급등락: 최근 15분 간 {change:+.1f}% 변동 → {'➖악재 예상 (매도세 급증)' if change < 0 else '➕호재 예상 (매수세 급증)'}")
        
        if event_type == 'volume_anomaly':
            ratio = event.get('ratio', 0)
            conditions.append(f"• 📊 거래량 급증: 평균 대비 {ratio:.1f}배 증가 → ➖악재 예상 (비정상적 거래량으로 인한 시장 불안정)")
        
        if event_type == 'funding_rate_anomaly':
            rate = event.get('funding_rate', 0)
            conditions.append(f"• 💰 펀딩비 이상: {rate:+.4f}% 돌파 → ➖악재 예상 (롱/숏 불균형 심화)")
        
        if event_type == 'critical_news':
            impact = event.get('impact', '중립')
            conditions.append(f"• 📰 중요 뉴스 발생: {event.get('title', '')[:50]}... → {impact}")
        
        # 추가 일반 조건들
        if len(conditions) < 3:
            conditions.extend([
                "• 🔄 온체인 이상 이동: 대량 거래소 유입/유출 감지",
                "• 🧠 심리 지표 급변: 시장 센티먼트 급속 변화"
            ])
        
        return '\n'.join(conditions[:4])  # 최대 4개만 표시
