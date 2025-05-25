#!/usr/bin/env python3
# main.py - 메인 애플리케이션 (진행 상황 안내 포함)
import os
import asyncio
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import Config
from telegram_bot import TelegramBot
from analysis_engine import AnalysisEngine
from bitget_client import BitgetClient
from exception_detector import ExceptionDetector

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BitcoinPredictionSystem:
    def __init__(self):
        self.config = Config()
        self.telegram_bot = TelegramBot(self.config)
        self.bitget_client = BitgetClient(self.config)
        self.analysis_engine = AnalysisEngine(self.config, self.bitget_client)
        self.exception_detector = ExceptionDetector(self.config, self.bitget_client)
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Seoul'))
        
    async def initialize(self):
        """시스템 초기화"""
        try:
            await self.telegram_bot.initialize()
            await self.bitget_client.initialize()
            logger.info("시스템 초기화 완료")
        except Exception as e:
            logger.error(f"초기화 실패: {e}")
            raise

    async def handle_report_command(self, update=None, context=None):
        """정규 리포트 생성 및 전송"""
        try:
            # 진행 상황 안내
            await self.telegram_bot.send_message("📊 전체 분석 리포트를 생성 중입니다... (예상 소요 시간: 30-60초)")
            
            logger.info("정규 리포트 생성 시작")
            report = await self.analysis_engine.generate_full_report()
            await self.telegram_bot.send_message(report)
            logger.info("정규 리포트 전송 완료")
        except Exception as e:
            logger.error(f"리포트 생성 실패: {e}")
            error_msg = f"⚠️ [분석 실패 알림] {datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M')}\n\n"
            error_msg += f"GPT 응답을 받아오지 못했습니다.\n"
            error_msg += f"예측 분석 리포트는 생성되지 않았으며, 다음 회차에 자동 재시도됩니다.\n\n"
            error_msg += f"📌 원인: {str(e)}\n"
            error_msg += f"📌 조치: 5분 후 자동 재분석 예정"
            await self.telegram_bot.send_message(error_msg)

    async def handle_forecast_command(self, update=None, context=None):
        """단기 예측 리포트 생성"""
        try:
            # 진행 상황 안내
            await self.telegram_bot.send_message("📈 단기 예측 분석을 수행 중입니다... (예상 소요 시간: 20-40초)")
            
            logger.info("단기 예측 리포트 생성 시작")
            forecast = await self.analysis_engine.generate_forecast_report()
            await self.telegram_bot.send_message(forecast)
            logger.info("단기 예측 리포트 전송 완료")
        except Exception as e:
            logger.error(f"예측 리포트 생성 실패: {e}")
            await self.telegram_bot.send_message(f"예측 분석 실패: {str(e)}")

    async def handle_profit_command(self, update=None, context=None):
        """수익 현황 리포트 생성"""
        try:
            # 진행 상황 안내
            await self.telegram_bot.send_message("💰 수익 현황을 분석하고 개인화된 조언을 준비 중입니다... (예상 소요 시간: 15-30초)")
            
            logger.info("수익 현황 리포트 생성 시작")
            profit_report = await self.analysis_engine.generate_profit_report()
            await self.telegram_bot.send_message(profit_report)
            logger.info("수익 현황 리포트 전송 완료")
        except Exception as e:
            logger.error(f"수익 리포트 생성 실패: {e}")
            await self.telegram_bot.send_message(f"수익 분석 실패: {str(e)}")

    async def handle_schedule_command(self, update=None, context=None):
        """일정 안내 리포트 생성"""
        try:
            # 진행 상황 안내
            await self.telegram_bot.send_message("📅 일정 정보를 수집 중입니다... (예상 소요 시간: 10-15초)")
            
            logger.info("일정 안내 리포트 생성 시작")
            schedule_report = await self.analysis_engine.generate_schedule_report()
            await self.telegram_bot.send_message(schedule_report)
            logger.info("일정 안내 리포트 전송 완료")
        except Exception as e:
            logger.error(f"일정 리포트 생성 실패: {e}")
            await self.telegram_bot.send_message(f"일정 분석 실패: {str(e)}")

    async def check_exceptions(self):
        """예외 상황 감지 및 처리"""
        try:
            exceptions = await self.exception_detector.detect_exceptions()
            if exceptions:
                logger.info(f"예외 상황 감지: {len(exceptions)}건")
                emergency_report = await self.analysis_engine.generate_emergency_report(exceptions)
                await self.telegram_bot.send_message(emergency_report)
        except Exception as e:
            logger.error(f"예외 감지 실패: {e}")

    def setup_scheduler(self):
        """스케줄러 설정"""
        # 정규 리포트 스케줄 (09:00, 13:00, 17:00, 23:00 KST)
        self.scheduler.add_job(
            self.handle_report_command,
            CronTrigger(hour=9, minute=0, timezone=pytz.timezone('Asia/Seoul')),
            id='report_09'
        )
        self.scheduler.add_job(
            self.handle_report_command,
            CronTrigger(hour=13, minute=0, timezone=pytz.timezone('Asia/Seoul')),
            id='report_13'
        )
        self.scheduler.add_job(
            self.handle_report_command,
            CronTrigger(hour=17, minute=0, timezone=pytz.timezone('Asia/Seoul')),
            id='report_17'
        )
        self.scheduler.add_job(
            self.handle_report_command,
            CronTrigger(hour=23, minute=0, timezone=pytz.timezone('Asia/Seoul')),
            id='report_23'
        )
        
        # 예외 상황 감지 (5분마다)
        self.scheduler.add_job(
            self.check_exceptions,
            'interval',
            minutes=5,
            id='exception_check'
        )

    async def run(self):
        """메인 실행 함수"""
        try:
            await self.initialize()
            
            # 텔레그램 봇 명령어 핸들러 등록
            self.telegram_bot.add_handler('report', self.handle_report_command)
            self.telegram_bot.add_handler('forecast', self.handle_forecast_command)
            self.telegram_bot.add_handler('profit', self.handle_profit_command)
            self.telegram_bot.add_handler('schedule', self.handle_schedule_command)
            
            # 스케줄러 설정 및 시작
            self.setup_scheduler()
            self.scheduler.start()
            
            # 텔레그램 봇 시작
            await self.telegram_bot.start()
            
            logger.info("비트코인 예측 시스템 시작됨")
            
            # 무한 대기
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("시스템 종료 요청")
        except Exception as e:
            logger.error(f"시스템 오류: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """시스템 종료"""
        try:
            self.scheduler.shutdown()
            await self.telegram_bot.stop()
            logger.info("시스템 정상 종료")
        except Exception as e:
            logger.error(f"종료 중 오류: {e}")

async def main():
    system = BitcoinPredictionSystem()
    await system.run()

if __name__ == "__main__":
    asyncio.run(main())
