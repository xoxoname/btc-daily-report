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
        
        # 엔진 초기화 - 올바른 클라이언트 전달
        self.analysis_engine = AnalysisEngine(
            bitget_client=self.bitget_client,  # Config가 아닌 BitgetClient 전달
            openai_client=None  # OpenAI 클라이언트는 AnalysisEngine 내부에서 초기화
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
            
            self.logger.info("수익 현황 리포트 생성 시작")
            
            # 수익 리포트 생성
            report = await self.analysis_engine.generate_profit_report()
            
            if 'error' in report:
                error_message = f"❌ 리포트 생성 실패\n\n오류: {report['error']}"
                if update:
                    await update.message.reply_text(error_message)
                else:
                    await self.telegram_bot.send_message(error_message)
                return
            
            # 리포트 메시지 포맷팅
            message = self._format_report_message(report)
            
            # 메시지 전송
            if update:
                await update.message.reply_text(message, parse_mode='HTML')
            else:
                await self.telegram_bot.send_message(message, parse_mode='HTML')
            
            self.logger.info("수익 현황 리포트 전송 완료")
            
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
    
    def _format_report_message(self, report: dict) -> str:
        """리포트 메시지 포맷팅"""
        try:
            current_price = report.get('current_price', 0)
            market_info = report.get('market_info', {})
            performance = report.get('performance_summary', {})
            ai_summary = report.get('ai_summary', '분석을 생성할 수 없습니다.')
            
            # 기본 정보
            message = f"""
🔔 <b>비트코인 분석 리포트</b>
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}

💰 <b>현재 가격</b>
${current_price:,.2f}

📈 <b>24시간 성과</b>
"""
            
            # 시장 정보 추가
            if not market_info.get('error'):
                change_24h = market_info.get('change_24h_percent', 0)
                volatility = market_info.get('volatility', 0)
                
                change_emoji = "🟢" if change_24h > 0 else "🔴" if change_24h < 0 else "⚪"
                
                message += f"""
{change_emoji} 변동률: {change_24h:+.2f}%
📊 변동성: {volatility:.2f}%
📊 고가: ${market_info.get('high_24h', 0):,.2f}
📊 저가: ${market_info.get('low_24h', 0):,.2f}
"""
            
            # 성과 요약 추가
            if not performance.get('error'):
                grade = performance.get('performance_grade', '알 수 없음')
                trend = performance.get('trend', '알 수 없음')
                
                message += f"""
📊 성과 등급: {grade}
📈 트렌드: {trend}
"""
            
            # AI 분석 추가
            message += f"""
🤖 <b>AI 분석</b>
{ai_summary}

⏰ <i>다음 리포트: 4시간 후</i>
"""
            
            return message
            
        except Exception as e:
            self.logger.error(f"메시지 포맷팅 실패: {str(e)}")
            return f"""
❌ <b>리포트 표시 오류</b>

원시 데이터:
{str(report)[:500]}...

시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    
    async def check_exceptions(self):
        """예외 상황 감지"""
        try:
            anomalies = await self.exception_detector.detect_all_anomalies()
            
            for anomaly in anomalies:
                await self.exception_detector.send_alert(anomaly)
                
        except Exception as e:
            self.logger.error(f"예외 감지 실패: {str(e)}")
    
    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시작 명령 처리"""
        welcome_message = """
🚀 <b>비트코인 예측 시스템에 오신 것을 환영합니다!</b>

📊 <b>이용 가능한 명령어:</b>
/report - 현재 분석 리포트 생성
/start - 도움말 표시

🔔 <b>자동 리포트 시간:</b>
• 오전 9시
• 오후 1시  
• 오후 6시
• 오후 10시

⚡ <b>실시간 알림:</b>
• 급격한 가격 변동
• 펀딩비 이상
• 거래량 급증

📈 정확하고 신뢰할 수 있는 비트코인 분석을 제공합니다.
"""
        
        await update.message.reply_text(welcome_message, parse_mode='HTML')
    
    async def start(self):
        """시스템 시작"""
        try:
            # 텔레그램 봇 핸들러 등록
            self.telegram_bot.add_handler('start', self.handle_start_command)
            self.telegram_bot.add_handler('report', self.handle_report_command)
            
            # 스케줄러 시작
            self.scheduler.start()
            
            # 텔레그램 봇 시작
            await self.telegram_bot.start()
            
            self.logger.info("비트코인 예측 시스템 시작됨")
            
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
            self.logger.info("시스템이 안전하게 종료되었습니다")
        except Exception as e:
            self.logger.error(f"시스템 종료 중 오류: {str(e)}")

async def main():
    """메인 함수"""
    system = BitcoinPredictionSystem()
    await system.start()

if __name__ == "__main__":
    asyncio.run(main())
