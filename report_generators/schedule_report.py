# report_generators/schedule_report.py
from .base_generator import BaseReportGenerator

class ScheduleReportGenerator(BaseReportGenerator):
    """일정 리포트 전담 생성기"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
    
    async def generate_report(self) -> str:
        """📅 /schedule 명령어 – 예정 주요 이벤트"""
        current_time = self._get_current_time_kst()
        
        # 예정 이벤트
        events_text = await self._format_upcoming_events()
        
        report = f"""📅 /schedule 명령어 – 예정 주요 이벤트
📅 작성 시각: {current_time} (KST)
📡 다가오는 시장 주요 이벤트
━━━━━━━━━━━━━━━━━━━
{events_text}"""
        
        return report
    
    async def _format_upcoming_events(self) -> str:
        """예정 이벤트 포맷팅"""
        # 실제 구현시에는 실시간 경제 캘린더 API 연동
        return """• 2025-05-20 21:00: 미국 FOMC 금리 발표 예정 → ➖악재 예상 (금리 인상 가능성, 단기 하락 변동 주의)
• 2025-05-20 18:00: 비트코인 현물 ETF 승인 심사 마감 → ➕호재 예상 (심사 결과 긍정적일 경우 급등 가능성)
• 2025-05-20 09:00: 미국 실업수당 신청 지표 발표 → ➖악재 예상 (수치에 따라 경기 불확실성 확대 가능성)"""
