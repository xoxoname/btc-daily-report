import os
import asyncio
import logging
from datetime import datetime
import traceback
from telegram import Update
from telegram.ext import ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

from config import Config
from telegram_bot import TelegramBot
from bitget_client import BitgetClient
from analysis_engine import AnalysisEngine
from exception_detector import ExceptionDetector
from data_collector import RealTimeDataCollector
from trading_indicators import AdvancedTradingIndicators
from report_generator import EnhancedReportGenerator

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class BitcoinPredictionSystem:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 설정 로드
        self.config = Config()
        
        # 클라이언트 초기화
        self.bitget_client = BitgetClient(self.config)
        self.telegram_bot = TelegramBot(self.config)
        
        # 새로운 컴포넌트 추가
        self.data_collector = RealTimeDataCollector(self.config)
        self.data_collector.set_bitget_client(self.bitget_client)
        
        self.indicator_system = AdvancedTradingIndicators()
        self.report_generator = EnhancedReportGenerator(
            self.config,
            self.data_collector,
            self.indicator_system
        )
        
        # 기존 엔진
        self.analysis_engine = AnalysisEngine(
            bitget_client=self.bitget_client,
            openai_client=None
        )
        
        self.exception_detector = ExceptionDetector(
            bitget_client=self.bitget_client,
            telegram_bot=self.telegram_bot
        )
        
        # 스케줄러 초기화
        self.scheduler = AsyncIOScheduler()
        self._setup_scheduler()
        
        self.logger.info("시스템 초기화 완료")
    
    def _setup_scheduler(self):
        """스케줄러 작업 설정"""
        timezone = pytz.timezone('Asia/Seoul')
        
        # 정기 리포트 스케줄
        self.scheduler.add_job(
            func=self.handle_report_command,
            trigger="cron",
            hour=9,
            minute=0,
            timezone=timezone,
            id="morning_report"
        )
        
        self.scheduler.add_job(
            func=self.handle_report_command,
            trigger="cron",
            hour=13,
            minute=0,
            timezone=timezone,
            id="lunch_report"
        )
        
        self.scheduler.add_job(
            func=self.handle_report_command,
            trigger="cron",
            hour=18,
            minute=0,
            timezone=timezone,
            id="evening_report"
        )
        
        self.scheduler.add_job(
            func=self.handle_report_command,
            trigger="cron",
            hour=22,
            minute=0,
            timezone=timezone,
            id="night_report"
        )
        
        # 예외 감지 (5분마다)
        self.scheduler.add_job(
            func=self.check_exceptions,
            trigger="interval",
            minutes=5,
            timezone=timezone,
            id="exception_check"
        )
    
    async def handle_report_command(self, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None):
        """리포트 명령 처리"""
        try:
            if update:
                await update.message.reply_text("📊 비트코인 분석 리포트를 생성중입니다...")
            else:
                await self.telegram_bot.send_message("📊 정기 비트코인 분석 리포트를 생성중입니다...")
            
            self.logger.info("리포트 생성 시작")
            
            # 새로운 리포트 생성기 사용
            report = await self.report_generator.generate_regular_report()
            
            # 메시지 전송 (Markdown 형식)
            if update:
                await update.message.reply_text(report, parse_mode='Markdown')
            else:
                await self.telegram_bot.send_message(report, parse_mode='Markdown')
            
            self.logger.info("리포트 전송 완료")
            
        except Exception as e:
            error_message = f"❌ 리포트 생성 중 오류가 발생했습니다: {str(e)}"
            self.logger.error(f"리포트 생성 실패: {str(e)}")
            self.logger.debug(f"리포트 생성 오류 상세: {traceback.format_exc()}")
            
            try:
                if update:
                    await update.message.reply_text(error_message)
                else:
                    await self.telegram_bot.send_message(error_message)
            except Exception as send_error:
                self.logger.error(f"오류 메시지 전송 실패: {str(send_error)}")
    
    async def handle_forecast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """예측 명령 처리"""
        try:
            await update.message.reply_text("🔮 단기 예측 분석 중...")
            
            # 예측 리포트 생성
            report = await self.report_generator.generate_forecast_report()
            
            await update.message.reply_text(report, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"예측 명령 처리 실패: {str(e)}")
            await update.message.reply_text("❌ 예측 분석 중 오류가 발생했습니다.")
    
    async def check_exceptions(self):
        """예외 상황 감지"""
        try:
            # 기존 예외 감지
            anomalies = await self.exception_detector.detect_all_anomalies()
            
            for anomaly in anomalies:
                await self.exception_detector.send_alert(anomaly)
            
            # 데이터 수집기의 이벤트 확인
            for event in self.data_collector.events_buffer:
                if event.severity.value in ['high', 'critical']:
                    # 예외 리포트 생성
                    report = await self.report_generator.generate_exception_report(event.__dict__)
                    await self.telegram_bot.send_message(report, parse_mode='Markdown')
            
            # 버퍼 클리어
            self.data_collector.events_buffer = []
                
        except Exception as e:
            self.logger.error(f"예외 감지 실패: {str(e)}")
    
    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시작 명령 처리"""
        welcome_message = """
🚀 <b>비트코인 예측 시스템에 오신 것을 환영합니다!</b>

📊 <b>이용 가능한 명령어:</b>
/report - 전체 분석 리포트
/forecast - 단기 예측 리포트
/start - 도움말 표시

🔔 <b>자동 리포트 시간:</b>
- 오전 9시
- 오후 1시  
- 오후 6시
- 오후 10시

⚡ <b>실시간 알림:</b>
- 급격한 가격 변동
- 펀딩비 이상
- 거래량 급증

📈 정확하고 신뢰할 수 있는 비트코인 분석을 제공합니다.
"""
        
        await update.message.reply_text(welcome_message, parse_mode='HTML')
    
    async def start(self):
        """시스템 시작"""
        try:
            # 데이터 수집기 시작
            asyncio.create_task(self.data_collector.start())
            
            # 스케줄러 시작
            self.scheduler.start()
            
            # 텔레그램 봇 핸들러 등록
            self.telegram_bot.add_handler('start', self.handle_start_command)
            self.telegram_bot.add_handler('report', self.handle_report_command)
            self.telegram_bot.add_handler('forecast', self.handle_forecast_command)
            
            # 텔레그램 봇 시작
            await self.telegram_bot.start()
            
            self.logger.info("비트코인 예측 시스템 시작됨")
            
            # 시작 메시지
            await self.telegram_bot.send_message("🚀 비트코인 자동 매매 봇이 시작되었습니다!")
            
            # 프로그램이 종료되지 않도록 유지
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                self.logger.info("시스템 종료 요청 받음")
                await self.stop()
                
        except Exception as e:
            self.logger.error(f"시스템 시작 실패: {str(e)}")
            self.logger.debug(f"시작 오류 상세: {traceback.format_exc()}")
            raise
    
    async def stop(self):
        """시스템 종료"""
        try:
            self.scheduler.shutdown()
            await self.telegram_bot.stop()
            
            # 데이터 수집기 종료
            if self.data_collector.session:
                await self.data_collector.close()
            
            self.logger.info("시스템이 안전하게 종료되었습니다")
        except Exception as e:
            self.logger.error(f"시스템 종료 중 오류: {str(e)}")

async def main():
    """메인 함수"""
    system = BitcoinPredictionSystem()
    await system.start()

if __name__ == "__main__":
    asyncio.run(main())
