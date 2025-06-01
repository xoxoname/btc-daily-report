# report_generators/__init__.py
"""
리포트 생성기 통합 모듈

사용법:
from report_generators import ReportGeneratorManager

manager = ReportGeneratorManager(config, data_collector, indicator_system)
manager.set_bitget_client(bitget_client)
manager.set_gateio_client(gateio_client)  # 새로 추가

# 각종 리포트 생성
regular_report = await manager.generate_regular_report()
profit_report = await manager.generate_profit_report()
forecast_report = await manager.generate_forecast_report()
schedule_report = await manager.generate_schedule_report()
exception_report = await manager.generate_exception_report(event_data)
"""

from .base_generator import BaseReportGenerator
from .regular_report import RegularReportGenerator
from .profit_report import ProfitReportGenerator
from .forecast_report import ForecastReportGenerator
from .schedule_report import ScheduleReportGenerator
from .exception_report import ExceptionReportGenerator
from .mental_care import MentalCareGenerator

class ReportGeneratorManager:
    """모든 리포트 생성기를 관리하는 통합 클래스"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        self.config = config
        self.data_collector = data_collector
        self.indicator_system = indicator_system
        self.bitget_client = bitget_client
        self.gateio_client = None  # Gate.io 클라이언트 추가
        
        # 각 리포트 생성기 초기화
        self.regular_generator = RegularReportGenerator(
            config, data_collector, indicator_system, bitget_client
        )
        self.profit_generator = ProfitReportGenerator(
            config, data_collector, indicator_system, bitget_client
        )
        self.forecast_generator = ForecastReportGenerator(
            config, data_collector, indicator_system, bitget_client
        )
        self.schedule_generator = ScheduleReportGenerator(
            config, data_collector, indicator_system, bitget_client
        )
        self.exception_generator = ExceptionReportGenerator(
            config, data_collector, indicator_system, bitget_client
        )
        
        # 멘탈 케어 독립 사용
        self.mental_care = MentalCareGenerator(
            self._get_openai_client()
        )
    
    def _get_openai_client(self):
        """OpenAI 클라이언트 반환"""
        if hasattr(self.config, 'OPENAI_API_KEY') and self.config.OPENAI_API_KEY:
            import openai
            return openai.AsyncOpenAI(api_key=self.config.OPENAI_API_KEY)
        return None
    
    def set_bitget_client(self, bitget_client):
        """모든 생성기에 Bitget 클라이언트 설정"""
        self.bitget_client = bitget_client
        
        generators = [
            self.regular_generator,
            self.profit_generator,
            self.forecast_generator,
            self.schedule_generator,
            self.exception_generator
        ]
        
        for generator in generators:
            generator.set_bitget_client(bitget_client)
    
    def set_gateio_client(self, gateio_client):
        """Gate.io 클라이언트 설정"""
        self.gateio_client = gateio_client
        # profit_generator에 Gate.io 클라이언트 설정
        if hasattr(self.profit_generator, 'set_gateio_client'):
            self.profit_generator.set_gateio_client(gateio_client)
            import logging
            logger = logging.getLogger(__name__)
            logger.info("✅ ProfitReportGenerator에 Gate.io 클라이언트 설정 완료")
        else:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("⚠️ ProfitReportGenerator에 set_gateio_client 메서드가 없음")
    
    async def generate_regular_report(self) -> str:
        """🧾 정기 리포트 생성 (/report)"""
        return await self.regular_generator.generate_report()
    
    async def generate_profit_report(self) -> str:
        """💰 수익 리포트 생성 (/profit)"""
        return await self.profit_generator.generate_report()
    
    async def generate_forecast_report(self) -> str:
        """📈 예측 리포트 생성 (/forecast)"""
        return await self.forecast_generator.generate_report()
    
    async def generate_schedule_report(self) -> str:
        """📅 일정 리포트 생성 (/schedule)"""
        return await self.schedule_generator.generate_report()
    
    async def generate_exception_report(self, event_data: dict) -> str:
        """🚨 예외 리포트 생성 (자동 감지)"""
        return await self.exception_generator.generate_report(event_data)
    
    async def generate_custom_mental_care(self, account_info: dict, position_info: dict, 
                                        today_pnl: float, weekly_profit: dict) -> str:
        """🧠 독립적인 멘탈 케어 메시지 생성"""
        return await self.mental_care.generate_profit_mental_care(
            account_info, position_info, today_pnl, weekly_profit
        )

# 하위 호환성을 위한 기존 클래스명 유지
EnhancedReportGenerator = ReportGeneratorManager

__all__ = [
    'ReportGeneratorManager',
    'EnhancedReportGenerator',  # 하위 호환성
    'BaseReportGenerator',
    'RegularReportGenerator',
    'ProfitReportGenerator', 
    'ForecastReportGenerator',
    'ScheduleReportGenerator',
    'ExceptionReportGenerator',
    'MentalCareGenerator'
]
