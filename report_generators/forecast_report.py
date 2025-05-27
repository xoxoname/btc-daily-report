# report_generators/forecast_report.py
from .base_generator import BaseReportGenerator
from .mental_care import MentalCareGenerator

class ForecastReportGenerator(BaseReportGenerator):
    """예측 리포트 전담 생성기"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        self.mental_care = MentalCareGenerator(self.openai_client)
    
    async def generate_report(self) -> str:
        """📈 /forecast 명령어 – 단기 매매 요약"""
        try:
            current_time = self._get_current_time_kst()
            
            # 데이터 수집
            market_data = await self._collect_all_data()
            indicators = await self.indicator_system.calculate_all_indicators(market_data)
            
            # 섹션별 포맷
            events_text = await self._format_upcoming_events()
            analysis_text = self._format_core_analysis_summary(indicators, market_data)
            prediction_text = self._format_short_predictions(indicators)
            pnl_summary = await self._format_profit_summary()
            mental_text = await self._generate_short_mental_message()
            
            report = f"""📈 /forecast 명령어 – 단기 매매 요약
📈 단기 비트코인 가격 예측
📅 작성 시각: {current_time} (KST)
📡 다가오는 시장 주요 이벤트
━━━━━━━━━━━━━━━━━━━
{events_text}
━━━━━━━━━━━━━━━━━━━

📊 핵심 분석 요약
{analysis_text}

━━━━━━━━━━━━━━━━━━━

🔮 향후 12시간 가격 흐름 예측
{prediction_text}

━━━━━━━━━━━━━━━━━━━

💰 금일 손익 요약
{pnl_summary}

━━━━━━━━━━━━━━━━━━━

🧠 멘탈 관리 코멘트
{mental_text}"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"예측 리포트 생성 실패: {str(e)}")
            return "❌ 예측 분석 중 오류가 발생했습니다."
    
    async def _format_upcoming_events(self) -> str:
        """예정 이벤트 포맷팅"""
        return """• 2025-05-20 21:00: 미국 FOMC 금리 발표 예정 → ➖악재 예상 (금리 인상 가능성, 단기 하락 변동 주의)
• 2025-05-20 18:00: 비트코인 현물 ETF 승인 심사 마감 → ➕호재 예상 (심사 결과 긍정적일 경우 급등 가능성)
• 2025-05-20 09:00: 미국 실업수당 신청 지표 발표 → ➖악재 예상 (수치에 따라 경기 불확실성 확대 가능성)"""
    
    def _format_core_analysis_summary(self, indicators: dict, market_data: dict) -> str:
        """핵심 분석 요약"""
        return """• 기술 분석: 저항선 돌파 시도 중 → ➕호재 예상 (상승세 지속 가능성)
• 심리 분석: 롱 포지션 우세 / 펀딩비 상승 → ➖악재 예상 (과열 경고)
• 구조 분석: 미결제약정 증가 / 숏 청산 발생 → ➕호재 예상 (롱 강세 구조)"""
    
    def _format_short_predictions(self, indicators: dict) -> str:
        """단기 예측"""
        composite = indicators.get('composite_score', {})
        score = composite.get('composite_score', 0)
        
        # 점수 기반 확률 계산
        if score > 20:
            up_prob = 58
            side_prob = 30
            down_prob = 12
        elif score > 0:
            up_prob = 52
            side_prob = 32
            down_prob = 16
        else:
            up_prob = 45
            side_prob = 30
            down_prob = 25
        
        return f"""• 상승 확률: {up_prob}%
• 횡보 확률: {side_prob}%
• 하락 확률: {down_prob}%

📌 전략 제안:
• 저항 돌파 가능성 있으므로 분할 진입 전략 유효
• 레버리지는 낮게 유지하고 익절 구간 확실히 설정"""
    
    async def _format_profit_summary(self) -> str:
        """손익 요약"""
        try:
            position_info = await self._get_position_info()
            today_pnl = await self._get_today_realized_pnl()
            
            unrealized = position_info.get('unrealized_pnl', 0) if position_info else 0
            total = today_pnl + unrealized
            
            return f"""• 실현 손익: {self._format_currency(today_pnl, False)} ({today_pnl * 1350 / 10000:.1f}만원)
• 미실현 손익: {self._format_currency(unrealized, False)} ({unrealized * 1350 / 10000:.1f}만원)
• 총 수익: {self._format_currency(total, False)} ({total * 1350 / 10000:.1f}만원)"""
            
        except Exception as e:
            self.logger.error(f"손익 요약 실패: {e}")
            return "• 손익 정보 조회 중 오류 발생"
    
    async def _generate_short_mental_message(self) -> str:
        """짧은 멘탈 메시지"""
        try:
            account_info = await self._get_account_info()
            today_pnl = await self._get_today_realized_pnl()
            
            if today_pnl > 100:
                return f'"오늘 ${today_pnl:.0f}을 벌어들였군요! 편의점 알바 {int(today_pnl/15):.0f}시간치 벌었네요. 시장에 감사하고, 다음 기회를 차분히 기다려 보세요."'
            elif today_pnl > 0:
                return f'"${today_pnl:.0f} 수익, 작지만 꾸준한 성과입니다. 이런 안정적인 수익이 복리의 힘을 만들어냅니다."'
            else:
                return '"시장은 항상 변동성이 있습니다. 차분한 마음으로 전략에 따라 접근하시길 바랍니다."'
                
        except Exception as e:
            self.logger.error(f"짧은 멘탈 메시지 생성 실패: {e}")
            return '"차분하게 전략에 따라 매매하시길 바랍니다. 감정적 거래보다는 전략적 접근이 중요합니다."'
