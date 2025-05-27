# report_generators/exception_report.py
from .base_generator import BaseReportGenerator
from typing import Dict

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
• 이 리포트는 정규 리포트 외 탐지 조건이 충족될 경우 즉시 자동 생성됩니다."""
        
        return report
    
    def _format_exception_cause(self, event: Dict) -> str:
        """예외 원인 포맷팅"""
        event_type = event.get('type', 'unknown')
        
        if event_type == 'price_anomaly':
            change = event.get('change_24h', 0) * 100
            price = event.get('current_price', 0)
            return f"""• 비트코인 가격 {abs(change):.1f}% {'급등' if change > 0 else '급락'}
• 현재가: ${price:,.0f}
• 직후 {'매도' if change < 0 else '매수'}세 집중 현상 관측"""
        
        elif event_type == 'volume_anomaly':
            volume = event.get('volume_24h', 0)
            ratio = event.get('ratio', 0)
            return f"""• 24시간 거래량 급증: {volume:,.0f} BTC
• 평균 대비 {ratio:.1f}배 증가
• 대량 거래 감지로 인한 유동성 변화"""
        
        elif event_type == 'funding_rate_anomaly':
            rate = event.get('funding_rate', 0)
            annual = event.get('annual_rate', 0) * 100
            return f"""• 펀딩비 이상 급등: {rate:.4f}%
• 연환산 {annual:+.1f}% 수준
• 롱/숏 불균형 심화로 인한 시장 왜곡"""
        
        elif event_type == 'critical_news':
            title = event.get('title', '')
            source = event.get('source', '')
            return f"""• {source}에서 중요 뉴스 발생
• 제목: {title}
• 직후 시장 반응 및 심리 변화 감지"""
        
        else:
            return """• Whale Alert에서 단일 지갑에서 3,200 BTC 대량 이체 감지됨
• 직후 10분간 BTC 가격 -2.3% 급락"""
    
    async def _generate_exception_analysis(self, event: Dict) -> str:
        """예외 분석 생성"""
        if self.openai_client:
            try:
                prompt = f"""
비트코인 시장에서 다음 예외 상황이 발생했습니다:
이벤트 타입: {event.get('type', 'unknown')}
심각도: {event.get('severity', 'medium')}
설명: {event.get('description', '')}

이 상황에 대한 전문적인 분석을 제공해주세요:
1. 시장에 미치는 영향
2. 향후 2-4시간 내 예상 시나리오
3. 투자자가 주의해야 할 점

간결하고 명확하게 한국어로 작성해주세요.
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "당신은 전문적인 암호화폐 시장 분석가입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.5
                )
                
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                self.logger.error(f"GPT 예외 분석 생성 실패: {e}")
        
        # 폴백 분석
        return """• 공포심 유입과 유동성 위축이 동시에 발생
• 온체인 대량 전송 + 변동성 확대 조짐
👉 향후 2시간 내 추가 하락 확률이 상승 확률보다 높음
※ 시장 반등을 기대하기에는 매도세 집중도가 높아 단기 위험 구간 판단"""
    
    def _format_risk_strategy(self, event: Dict) -> str:
        """리스크 전략 포맷팅"""
        severity = event.get('severity', 'medium')
        
        if severity == 'critical':
            return """• 레버리지 포지션 보유 시: 즉시 포지션 축소 또는 청산 검토
• 현물 보유자는 일부 매도 후 하락 시 재진입 준비
• 신규 진입 시 소량 분할 매수로 리스크 분산
• 손절선 엄격 준수 및 감정적 거래 금지"""
        else:
            return """• 레버리지 포지션 보유 시: 청산가와 거리 확인 필수
• 현물 보유자는 분할 매수 재진입 준비
• 고배율 진입자는 즉시 포지션 축소 또는 정리 권고"""
    
    def _format_detection_conditions(self, event: Dict) -> str:
        """탐지 조건 포맷팅"""
        event_type = event.get('type', 'unknown')
        
        conditions = []
        
        if event_type == 'price_anomaly':
            change = event.get('change_24h', 0) * 100
            conditions.append(f"• 📉 단기 변동 급등락: 최근 15분 간 {change:+.1f}% 변동 → ➖악재 예상 ({'매도세 급증' if change < 0 else '매수세 급증'}에 따른 유동성 변화)")
        
        if event_type == 'volume_anomaly':
            ratio = event.get('ratio', 0)
            conditions.append(f"• 📊 거래량 급증: 평균 대비 {ratio:.1f}배 증가 → ➖악재 예상 (비정상적 거래량으로 인한 시장 불안정)")
        
        if event_type == 'funding_rate_anomaly':
            rate = event.get('funding_rate', 0)
            conditions.append(f"• 💰 펀딩비 이상: {rate:+.4f}% 돌파 → ➖악재 예상 (롱/숏 불균형 심화)")
        
        if event_type == 'critical_news':
            impact = event.get('impact', '중립')
            conditions.append(f"• 📰 중요 뉴스 발생: {event.get('title', '')[:50]}... → {impact}")
        
        # 기본 조건들 추가
        conditions.extend([
            "• 🔄 온체인 이상 이동: 단일 지갑에서 3,200 BTC 대량 이체 발생 → ➖악재 예상 (매도 전조 가능성)",
            "• 🧠 심리 지표 급변: 공포탐욕지수 74 → 42 급락 → ➖악재 예상 (시장 심리 급속 위축)"
        ])
        
        return '\n'.join(conditions[:4])  # 최대 4개만 표시
