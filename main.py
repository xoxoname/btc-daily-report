import os
import asyncio
import logging
from datetime import datetime, timedelta
import traceback
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
import signal
import sys
import json
from typing import Optional, Dict, List

from config import Config
from telegram_bot import TelegramBot
from bitget_client import BitgetClient
from analysis_engine import AnalysisEngine
from exception_detector import ExceptionDetector
from data_collector import RealTimeDataCollector
from trading_indicators import AdvancedTradingIndicators
from report_generators import ReportGeneratorManager

# 미러 트레이딩 관련 임포트 - 수정된 부분
try:
    from gateio_client import GateioMirrorClient as GateClient
    from mirror_trading import MirrorTradingSystem  # 🔥 수정된 클래스명
    MIRROR_TRADING_AVAILABLE = True
    print("✅ 미러 트레이딩 모듈 import 성공")
except ImportError as e:
    MIRROR_TRADING_AVAILABLE = False
    print(f"⚠️ 미러 트레이딩 모듈을 찾을 수 없습니다: {e}")
    print("분석 전용 모드로 실행됩니다.")

# ML 예측기 임포트
try:
    from ml_predictor import MLPredictor
    ML_PREDICTOR_AVAILABLE = True
except ImportError:
    ML_PREDICTOR_AVAILABLE = False
    print("⚠️ ML 예측기 모듈을 찾을 수 없습니다. 기본 분석을 사용합니다.")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bitcoin_prediction.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class BitcoinPredictionSystem:
    """비트코인 예측 시스템 메인 클래스 - v2.3"""
    
    def __init__(self):
        self.config = Config()
        self.is_running = False
        self.startup_time = datetime.now()
        
        # 환경변수 검증을 통한 모드 설정
        # 🔥🔥🔥 ENABLE_MIRROR_TRADING과 MIRROR_TRADING_MODE 두 환경변수 모두 지원
        enable_mirror = os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true'
        mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'false').lower() == 'true'
        self.mirror_mode = enable_mirror or mirror_mode  # 둘 중 하나라도 true면 활성화
        
        self.ml_mode = ML_PREDICTOR_AVAILABLE and os.getenv('ENABLE_ML_PREDICTION', 'false').lower() == 'true'
        
        # 🔥🔥🔥 미러 트레이딩 관련 환경변수들 (사용자 요구사항 대로 유지)
        # ALPHA_VANTAGE_KEY, BITGET_APIKEY, BITGET_APISECRET, BITGET_PASSPHRASE,
        # COINGECKO_API_KEY, CRYPTOCOMPARE_API_KEY, ENABLE_MIRROR_TRADING,
        # GATE_API_KEY, GATE_API_SECRET, MIRROR_CHECK_INTERVAL, MIRROR_TRADING_MODE,
        # NEWSAPI_KEY, SDATA_KEY, OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        
        # 컴포넌트 초기화
        self.bitget_client = None
        self.gate_client = None
        self.telegram_bot = None
        self.analysis_engine = None
        self.exception_detector = None
        self.data_collector = None
        self.indicator_system = None
        self.report_manager = None
        self.mirror_trading = None
        self.ml_predictor = None
        
        # 명령어 통계
        self.command_stats = {
            'report': 0,
            'forecast': 0,
            'profit': 0,
            'schedule': 0,
            'stats': 0,
            'mirror': 0,
            'natural_language': 0,
            'errors': 0
        }
        
        # 클라이언트 초기화
        self._initialize_clients()
        
        # 컴포넌트 초기화
        self._initialize_components()
        
        # 스케줄러 초기화
        self.scheduler = AsyncIOScheduler()
        self._setup_scheduler()
        
        # 시그널 핸들러 설정
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"시스템 초기화 완료 (미러: {'활성' if self.mirror_mode else '비활성'}, ML: {'활성' if self.ml_mode else '비활성'})")
    
    def _initialize_clients(self):
        """클라이언트 초기화 - 개선된 버전"""
        try:
            # Bitget 클라이언트
            self.bitget_client = BitgetClient(self.config)
            logger.info("✅ Bitget 클라이언트 초기화 완료")
            
            # Telegram 봇
            self.telegram_bot = TelegramBot(self.config)
            logger.info("✅ Telegram 봇 초기화 완료")
            
            # Gate.io 클라이언트 (미러 모드일 때만) - 개선된 로직
            self.gate_client = None
            self.mirror_trading = None
            
            # 미러 트레이딩 활성화 조건 체크
            if self.mirror_mode:
                logger.info("🔄 미러 트레이딩 모드가 활성화됨, Gate.io 클라이언트 초기화 시작...")
                
                if not MIRROR_TRADING_AVAILABLE:
                    logger.error("❌ 미러 트레이딩 모듈을 찾을 수 없음")
                    self.mirror_mode = False
                    return
                
                # Gate.io API 키 확인
                gate_api_key = os.getenv('GATE_API_KEY', '')
                gate_api_secret = os.getenv('GATE_API_SECRET', '')
                
                if not gate_api_key or not gate_api_secret:
                    logger.error("❌ Gate.io API 키가 설정되지 않음")
                    logger.error("GATE_API_KEY와 GATE_API_SECRET 환경변수를 설정해주세요")
                    self.mirror_mode = False
                    return
                
                try:
                    logger.info("🔄 Gate.io 클라이언트 생성 중...")
                    self.gate_client = GateClient(self.config)
                    logger.info("✅ Gate.io 클라이언트 생성 완료")
                    
                    logger.info("🔄 미러 트레이딩 시스템 생성 중...")
                    # 🔥🔥🔥 수정된 클래스명 사용
                    self.mirror_trading = MirrorTradingSystem(
                        self.config,
                        self.bitget_client,
                        self.gate_client,
                        self.telegram_bot
                    )
                    logger.info("✅ 미러 트레이딩 시스템 생성 완료 - 게이트 예약주문 보호 강화")
                    
                except Exception as e:
                    logger.error(f"❌ 미러 트레이딩 시스템 초기화 실패: {e}")
                    logger.error(traceback.format_exc())
                    self.mirror_mode = False
                    self.gate_client = None
                    self.mirror_trading = None
            
            # ML 예측기 초기화
            if self.ml_mode:
                try:
                    self.ml_predictor = MLPredictor()
                    logger.info("✅ ML 예측기 초기화 완료")
                except Exception as e:
                    logger.error(f"❌ ML 예측기 초기화 실패: {e}")
                    self.ml_mode = False
                    self.ml_predictor = None
                    
        except Exception as e:
            logger.error(f"클라이언트 초기화 실패: {e}")
            raise
    
    def _initialize_components(self):
        """컴포넌트 초기화"""
        try:
            # 분석 엔진
            self.analysis_engine = AnalysisEngine(self.config)
            
            # 예외 감지기
            self.exception_detector = ExceptionDetector(self.config, self.bitget_client)
            
            # 데이터 수집기
            self.data_collector = RealTimeDataCollector(self.config)
            self.data_collector.bitget_client = self.bitget_client
            
            # 지표 시스템
            self.indicator_system = AdvancedTradingIndicators(self.config)
            
            # 리포트 매니저
            self.report_manager = ReportGeneratorManager(
                self.config, 
                self.data_collector, 
                self.indicator_system,
                self.bitget_client
            )
            
            # Gate.io 클라이언트가 있으면 리포트 매니저에 추가
            if self.gate_client:
                self.report_manager.set_gateio_client(self.gate_client)
            
            logger.info("✅ 모든 컴포넌트 초기화 완료")
            
        except Exception as e:
            logger.error(f"컴포넌트 초기화 실패: {e}")
            raise
    
    def _setup_scheduler(self):
        """스케줄러 설정"""
        try:
            # KST 타임존
            kst = pytz.timezone('Asia/Seoul')
            
            # 정규 리포트 (4회)
            self.scheduler.add_job(
                self.generate_scheduled_report,
                'cron', hour=9, minute=0, timezone=kst,
                id='morning_report'
            )
            self.scheduler.add_job(
                self.generate_scheduled_report,
                'cron', hour=13, minute=0, timezone=kst,
                id='afternoon_report'
            )
            self.scheduler.add_job(
                self.generate_scheduled_report,
                'cron', hour=17, minute=0, timezone=kst,
                id='evening_report'
            )
            self.scheduler.add_job(
                self.generate_scheduled_report,
                'cron', hour=22, minute=0, timezone=kst,
                id='night_report'
            )
            
            # 예외 감지 (5분마다)
            self.scheduler.add_job(
                self.check_exceptions,
                'interval', minutes=5,
                id='exception_check'
            )
            
            # 급속 변동 감지 (2분마다)
            self.scheduler.add_job(
                self.check_rapid_changes,
                'interval', minutes=2,
                id='rapid_change_check'
            )
            
            logger.info("✅ 스케줄러 설정 완료")
            
        except Exception as e:
            logger.error(f"스케줄러 설정 실패: {e}")
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        logger.info(f"종료 시그널 수신: {signum}")
        self.is_running = False
        
        # 스케줄러 종료
        try:
            self.scheduler.shutdown()
        except:
            pass
        
        sys.exit(0)
    
    async def generate_scheduled_report(self):
        """정규 리포트 생성"""
        if not self.is_running:
            return
            
        try:
            self.command_stats['report'] += 1
            
            # 정규 리포트 생성
            report = await self.report_manager.generate_regular_report()
            
            if report:
                await self.telegram_bot.send_message(report, parse_mode='HTML')
                logger.info("정규 리포트 발송 완료")
            
        except Exception as e:
            self.command_stats['errors'] += 1
            logger.error(f"정규 리포트 생성 실패: {e}")
            logger.debug(traceback.format_exc())
    
    async def check_exceptions(self):
        """예외 상황 체크"""
        if not self.is_running:
            return
            
        try:
            exceptions = await self.exception_detector.check_all()
            
            if exceptions:
                for exception in exceptions:
                    report = await self.report_manager.generate_exception_report(exception)
                    if report:
                        await self.telegram_bot.send_message(report, parse_mode='HTML')
                
                logger.info(f"예외 상황 {len(exceptions)}건 처리 완료")
        
        except Exception as e:
            logger.error(f"예외 상황 체크 실패: {e}")
    
    async def check_rapid_changes(self):
        """급속 변동 체크"""
        if not self.is_running:
            return
            
        try:
            rapid_changes = await self.exception_detector.check_rapid_price_change()
            
            if rapid_changes:
                for change in rapid_changes:
                    report = await self.report_manager.generate_exception_report(change)
                    if report:
                        await self.telegram_bot.send_message(report, parse_mode='HTML')
                
                logger.info(f"급속 변동 {len(rapid_changes)}건 처리 완료")
        
        except Exception as e:
            logger.error(f"급속 변동 체크 실패: {e}")
    
    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시작 명령 처리"""
        try:
            user_name = update.effective_user.first_name or "사용자"
            
            welcome_message = f"""안녕하세요 {user_name}님! 👋

🔥 <b>비트코인 전용 예측 시스템 v2.3</b>

💡 <b>주요 기능:</b>
• 📊 실시간 선물 시장 분석
• 🎯 롱/숏 진입점 예측
• 📈 펀딩비 & 미결제약정 추적
• 🔍 CVD(누적거래량델타) 분석
• 📰 AI 뉴스 영향도 분석
• 🧠 멘탈 케어 & 리스크 관리"""

            if self.mirror_mode:
                welcome_message += f"""

🔄 <b>미러 트레이딩 시스템 활성화</b>
• 🛡️ 게이트 예약주문 보호 강화
• 🔒 비트겟 취소 시에만 게이트 취소
• 🔍 삼중 검증으로 오취소 방지
• 📊 실시간 동기화"""

            welcome_message += f"""

📋 <b>명령어:</b>
• /report - 종합 분석 리포트
• /forecast - 12시간 예측
• /profit - 손익 현황 (개인화)
• /schedule - 일정 안내"""

            if self.mirror_mode:
                welcome_message += "\n• /mirror - 미러 트레이딩 상태"

            welcome_message += f"""
• /stats - 시스템 통계

🗣️ <b>자연어 지원:</b>
"지금 매수해도 돼?", "시장 상황 어때?", "수익률은?" 등 자연스럽게 질문하세요!

도움이 필요하시면 언제든 질문해주세요! 😊"""
            
            await update.message.reply_text(welcome_message, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"시작 명령 처리 실패: {e}")
            await update.message.reply_text("❌ 도움말 생성 중 오류가 발생했습니다.", parse_mode='HTML')
    
    async def handle_mirror_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """미러 트레이딩 상태 명령"""
        await self.handle_mirror_status(update, context)
    
    async def handle_mirror_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔥🔥🔥 미러 트레이딩 상태 확인 - 강화된 버전"""
        try:
            self.command_stats['mirror'] += 1
            
            if not self.mirror_mode or not self.mirror_trading:
                # 상세한 비활성화 이유 제공
                reasons = []
                
                if not self.mirror_mode:
                    reasons.append("ENABLE_MIRROR_TRADING 또는 MIRROR_TRADING_MODE 환경변수가 'true'로 설정되지 않음")
                
                if not MIRROR_TRADING_AVAILABLE:
                    reasons.append("미러 트레이딩 모듈을 찾을 수 없음")
                
                gate_api_key = os.getenv('GATE_API_KEY', '')
                gate_api_secret = os.getenv('GATE_API_SECRET', '')
                if not gate_api_key or not gate_api_secret:
                    reasons.append("Gate.io API 키가 설정되지 않음")
                
                await update.message.reply_text(
                    f"📊 현재 분석 전용 모드로 실행 중입니다.\n\n"
                    f"🔍 비활성화 이유:\n" + 
                    "\n".join(f"• {reason}" for reason in reasons) +
                    f"\n\n📋 활성화 방법:\n"
                    f"1. ENABLE_MIRROR_TRADING=true 또는 MIRROR_TRADING_MODE=true 환경변수 설정\n"
                    f"2. GATE_API_KEY 환경변수 설정 {'✓' if gate_api_key else '❌'}\n"
                    f"3. GATE_API_SECRET 환경변수 설정 {'✓' if gate_api_secret else '❌'}\n"
                    f"4. 시스템 재시작",
                    parse_mode='HTML'
                )
                return
            
            # 미러 트레이딩 시스템이 활성화된 경우
            try:
                # 시스템 헬스체크
                health_status = await self.mirror_trading.health_check()
                health_icon = "✅" if health_status else "❌"
                
                # 통계 정보
                stats = self.mirror_trading.daily_stats
                total_attempts = stats['total_mirrored']
                success_rate = (stats['successful_mirrors'] / total_attempts * 100) if total_attempts > 0 else 0
                failed_count = stats['failed_mirrors']
                
                status_msg = f"""🔄 <b>미러 트레이딩 시스템 상태</b>

{health_icon} <b>시스템 상태:</b> {'정상 작동' if health_status else '문제 감지'}

📊 <b>오늘 성과:</b>
- 총 시도: {stats['total_mirrored']}회
- 성공: {stats['successful_mirrors']}회
- 실패: {stats['failed_mirrors']}회
- 성공률: {success_rate:.1f}%
- 예약 주문 미러링: {stats['plan_order_mirrors']}회
- 예약 주문 취소: {stats['plan_order_cancels']}회
- 부분청산: {stats['partial_closes']}회
- 전체청산: {stats['full_closes']}회
- 총 거래량: ${stats['total_volume']:,.2f}

🔥 <b>보호 기능 강화:</b>
- 게이트 예약주문 10분간 보호
- 비트겟 취소 삼중 검증
- 삭제 방지: {stats.get('deletion_prevented', 0)}회
- 중복 방지: {stats['duplicate_orders_prevented']}회

💰 <b>달러 비율 복제:</b>
- 총 자산 대비 동일 비율 유지
- 예약 주문도 동일 비율 복제
- 실시간 가격 조정

⚠️ <b>최근 오류:</b>
- 실패 기록: {failed_count}건"""
            
            # 최근 실패 내역 추가
            if failed_count > 0 and hasattr(self.mirror_trading, 'failed_mirrors') and self.mirror_trading.failed_mirrors:
                recent_fail = self.mirror_trading.failed_mirrors[-1]
                if hasattr(recent_fail, 'error'):
                    status_msg += f"\n• 마지막 실패: {recent_fail.error[:50]}..."
            
            status_msg += "\n\n✅ 게이트 예약주문 자동취소 방지 시스템 강화 완료"
            
            # 시스템 가동 시간
            uptime = datetime.now() - self.startup_time
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            status_msg += f"\n⏱️ 가동 시간: {hours}시간 {minutes}분"
            
            await update.message.reply_text(status_msg, parse_mode='HTML')
            
            except Exception as health_error:
                logger.error(f"미러 트레이딩 상태 체크 실패: {health_error}")
                await update.message.reply_text(
                    f"🔄 <b>미러 트레이딩 시스템</b>\n\n"
                    f"❌ 상태 확인 중 오류 발생\n"
                    f"오류: {str(health_error)[:100]}\n\n"
                    f"시스템이 작동 중이지만 상태 조회에 문제가 있습니다.",
                    parse_mode='HTML'
                )
            
        except Exception as e:
            self.command_stats['errors'] += 1
            logger.error(f"미러 상태 조회 실패: {str(e)}")
            logger.debug(traceback.format_exc())
            await update.message.reply_text(
                f"❌ 미러 트레이딩 상태 조회 중 오류가 발생했습니다.\n"
                f"오류: {str(e)[:100]}",
                parse_mode='HTML'
            )
    
    async def handle_report_command(self, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None):
        """리포트 명령 처리"""
        try:
            self.command_stats['report'] += 1
            
            if update:
                user_name = update.effective_user.first_name or "사용자"
                await update.message.reply_text(f"📊 {user_name}님을 위한 맞춤 리포트 생성 중...", parse_mode='HTML')
            
            report = await self.report_manager.generate_regular_report()
            
            if report:
                if update:
                    await update.message.reply_text(report, parse_mode='HTML')
                else:
                    await self.telegram_bot.send_message(report, parse_mode='HTML')
            else:
                error_msg = "❌ 리포트 생성에 실패했습니다."
                if update:
                    await update.message.reply_text(error_msg)
                else:
                    await self.telegram_bot.send_message(error_msg)
            
        except Exception as e:
            self.command_stats['errors'] += 1
            logger.error(f"리포트 생성 실패: {e}")
            logger.debug(traceback.format_exc())
            
            error_msg = f"❌ 리포트 생성 중 오류가 발생했습니다.\n오류: {str(e)[:100]}"
            if update:
                await update.message.reply_text(error_msg)
            else:
                await self.telegram_bot.send_message(error_msg)
    
    async def handle_forecast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """예측 리포트 명령 처리"""
        try:
            self.command_stats['forecast'] += 1
            
            user_name = update.effective_user.first_name or "사용자"
            await update.message.reply_text(f"🔮 {user_name}님을 위한 12시간 예측 생성 중...", parse_mode='HTML')
            
            report = await self.report_manager.generate_forecast_report()
            
            if report:
                await update.message.reply_text(report, parse_mode='HTML')
            else:
                await update.message.reply_text("❌ 예측 리포트 생성에 실패했습니다.")
            
        except Exception as e:
            self.command_stats['errors'] += 1
            logger.error(f"예측 리포트 생성 실패: {e}")
            logger.debug(traceback.format_exc())
            await update.message.reply_text(f"❌ 예측 리포트 생성 중 오류가 발생했습니다.\n오류: {str(e)[:100]}")
    
    async def handle_profit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """손익 리포트 명령 처리"""
        try:
            self.command_stats['profit'] += 1
            
            user_name = update.effective_user.first_name or "사용자"
            await update.message.reply_text(f"💰 {user_name}님의 손익 현황 분석 중...", parse_mode='HTML')
            
            report = await self.report_manager.generate_profit_report()
            
            if report:
                await update.message.reply_text(report, parse_mode='HTML')
            else:
                await update.message.reply_text("❌ 손익 리포트 생성에 실패했습니다.")
            
        except Exception as e:
            self.command_stats['errors'] += 1
            logger.error(f"손익 리포트 생성 실패: {e}")
            logger.debug(traceback.format_exc())
            await update.message.reply_text(f"❌ 손익 리포트 생성 중 오류가 발생했습니다.\n오류: {str(e)[:100]}")
    
    async def handle_schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """일정 리포트 명령 처리"""
        try:
            self.command_stats['schedule'] += 1
            
            report = await self.report_manager.generate_schedule_report()
            
            if report:
                await update.message.reply_text(report, parse_mode='HTML')
            else:
                await update.message.reply_text("❌ 일정 리포트 생성에 실패했습니다.")
            
        except Exception as e:
            self.command_stats['errors'] += 1
            logger.error(f"일정 리포트 생성 실패: {e}")
            logger.debug(traceback.format_exc())
            await update.message.reply_text(f"❌ 일정 리포트 생성 중 오류가 발생했습니다.\n오류: {str(e)[:100]}")
    
    async def handle_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """통계 명령 처리"""
        try:
            self.command_stats['stats'] += 1
            
            uptime = datetime.now() - self.startup_time
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            
            report = f"""📊 <b>시스템 통계</b>

⏱️ <b>가동 시간:</b> {hours}시간 {minutes}분

📋 <b>명령어 사용 통계:</b>
- 리포트: {self.command_stats['report']}회
- 예측: {self.command_stats['forecast']}회
- 손익: {self.command_stats['profit']}회
- 일정: {self.command_stats['schedule']}회"""

            if self.mirror_mode:
                report += f"\n- 미러 상태: {self.command_stats['mirror']}회"

            report += f"""
- 자연어 질문: {self.command_stats['natural_language']}회
- 오류 발생: {self.command_stats['errors']}회

<b>💾 메모리 사용량:</b> """
            
            try:
                import psutil
                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / 1024 / 1024
                report += f"{memory_mb:.1f} MB"
            except:
                report += "측정 불가"
            
            # ML 예측 통계 추가
            if self.ml_mode and self.ml_predictor:
                stats = self.ml_predictor.get_stats()
                report += f"""

<b>🤖 AI 예측 성능:</b>
- 총 예측: {stats['total_predictions']}건
- 검증 완료: {stats['verified_predictions']}건
- 방향 정확도: {stats['direction_accuracy']}
- 크기 정확도: {stats['magnitude_accuracy']}"""
            
            # 미러 트레이딩 통계 추가
            if self.mirror_mode and self.mirror_trading:
                mirror_stats = self.mirror_trading.daily_stats
                report += f"""

<b>🔄 미러 트레이딩 통계:</b>
- 총 시도: {mirror_stats['total_mirrored']}회
- 성공: {mirror_stats['successful_mirrors']}회
- 실패: {mirror_stats['failed_mirrors']}회
- 예약 주문 미러링: {mirror_stats['plan_order_mirrors']}회
- 예약 주문 취소: {mirror_stats['plan_order_cancels']}회
- 부분 청산: {mirror_stats['partial_closes']}회
- 전체 청산: {mirror_stats['full_closes']}회
- 총 거래량: ${mirror_stats['total_volume']:,.2f}
- 🔥 삭제 방지: {mirror_stats.get('deletion_prevented', 0)}회"""
            
            report += f"""

<b>🔧 시스템 설정:</b>
- 예외 감지: 5분마다
- 급속 변동: 2분마다
- 뉴스 수집: 15초마다
- 가격 임계값: {self.exception_detector.PRICE_CHANGE_THRESHOLD}%
- 거래량 임계값: {self.exception_detector.VOLUME_SPIKE_THRESHOLD}배

━━━━━━━━━━━━━━━━━━━
⚡ 비트코인 전용 시스템이 완벽히 작동했습니다!"""

            if self.mirror_mode:
                report += "\n🔥 게이트 예약주문 자동취소 방지 시스템 강화 완료!"
            
            await update.message.reply_text(report, parse_mode='HTML')
            
        except Exception as e:
            self.command_stats['errors'] += 1
            logger.error(f"통계 조회 실패: {e}")
            logger.debug(traceback.format_exc())
            await update.message.reply_text(f"❌ 통계 조회 중 오류가 발생했습니다.\n오류: {str(e)[:100]}")
    
    async def handle_natural_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """자연어 메시지 처리"""
        try:
            self.command_stats['natural_language'] += 1
            
            message_text = update.message.text.lower()
            user_name = update.effective_user.first_name or "사용자"
            
            # 간단한 패턴 매칭
            if any(keyword in message_text for keyword in ['리포트', '분석', '상황', '어때', '어떠', '현재']):
                await self.handle_report_command()
                return
                
            if any(keyword in message_text for keyword in ['예측', '전망', '앞으로', '미래', '내일']):
                await self.handle_forecast_command(update, context)
                return
                
            if any(keyword in message_text for keyword in ['수익', '손익', '돈', '벌었', '잃었', '포지션']):
                await self.handle_profit_command(update, context)
                return
                
            if any(keyword in message_text for keyword in ['일정', '스케줄', '언제', '시간']):
                await self.handle_schedule_command(update, context)
                return
                
            if any(keyword in message_text for keyword in ['통계', '사용량', '성능', 'stats']):
                await self.handle_stats_command(update, context)
                return
            
            if self.mirror_mode and any(keyword in message_text for keyword in ['미러', 'mirror', '복사', '동기화']):
                await self.handle_mirror_status(update, context)
                return
            
            # 매수/매도 관련
            if any(keyword in message_text for keyword in ['매수', '살까', '사도', '진입', '들어가', 'buy']):
                await update.message.reply_text(
                    f"🤔 {user_name}님, 매수 타이밍이 궁금하시군요!\n\n"
                    f"정확한 분석을 위해 /forecast 명령어로 12시간 예측을 확인해보세요.\n"
                    f"또는 /report로 현재 시장 상황을 종합적으로 분석받으실 수 있어요! 📊"
                )
                return
                
            if any(keyword in message_text for keyword in ['매도', '팔까', 'sell', '청산', '정리']):
                await update.message.reply_text(
                    f"🤔 {user_name}님, 매도 타이밍을 고민하고 계시는군요!\n\n"
                    f"/profit 명령어로 현재 손익 상황을 확인하고,\n"
                    f"/forecast로 향후 전망을 체크해보세요! 💰"
                )
                return
            
            # 기본 응답
            await update.message.reply_text(self._generate_default_response(message_text), parse_mode='HTML')
            
        except Exception as e:
            self.command_stats['errors'] += 1
            logger.error(f"자연어 처리 실패: {e}")
            await update.message.reply_text("❌ 메시지 처리 중 오류가 발생했습니다.", parse_mode='HTML')
    
    def _generate_default_response(self, message: str) -> str:
        """기본 응답 생성"""
        responses = [
            "죄송합니다. 이해하지 못했습니다. 🤔",
            "무엇을 도와드릴까요? 🤔",
            "더 구체적으로 말씀해주시겠어요? 🤔"
        ]
        
        import random
        response = random.choice(responses)
        
        commands = [
            "• '오늘 수익은?'", "• '지금 매수해도 돼?'", "• '시장 상황 어때?'",
            "• '다음 리포트 언제?'", "• '시스템 통계 보여줘'"
        ]
        
        if self.mirror_mode:
            commands.append("• '미러 트레이딩 상태는?'")
        
        command_text = "\n".join(commands)
        
        return f"{response}\n\n다음과 같이 질문해보세요:\n{command_text}\n\n또는 /help 명령어로 전체 기능을 확인하세요."
    
    async def start(self):
        """시스템 시작"""
        try:
            logger.info("=" * 50)
            logger.info("시스템 시작 프로세스 개시 - 비트코인 전용")
            logger.info("=" * 50)
            
            self.is_running = True
            self.startup_time = datetime.now()
            
            # Bitget 클라이언트 초기화
            logger.info("Bitget 클라이언트 초기화 중...")
            await self.bitget_client.initialize()
            
            # Gate.io 클라이언트 초기화 (미러 모드일 때만)
            if self.mirror_mode and self.gate_client:
                logger.info("Gate.io 클라이언트 초기화 중...")
                await self.gate_client.initialize()
            
            # 데이터 수집기 시작
            logger.info("데이터 수집기 시작 중...")
            asyncio.create_task(self.data_collector.start())
            
            # 미러 트레이딩 시작 (미러 모드일 때만)
            if self.mirror_mode and self.mirror_trading:
                logger.info("🔥 미러 트레이딩 시스템 시작 중... (게이트 예약주문 보호 강화)")
                asyncio.create_task(self.mirror_trading.start())
            
            # 스케줄러 시작
            logger.info("스케줄러 시작 중...")
            self.scheduler.start()
            
            # 텔레그램 봇 핸들러 등록
            logger.info("텔레그램 봇 핸들러 등록 중...")
            self.telegram_bot.add_handler('start', self.handle_start_command)
            self.telegram_bot.add_handler('report', self.handle_report_command)
            self.telegram_bot.add_handler('forecast', self.handle_forecast_command)
            self.telegram_bot.add_handler('profit', self.handle_profit_command)
            self.telegram_bot.add_handler('schedule', self.handle_schedule_command)
            self.telegram_bot.add_handler('stats', self.handle_stats_command)
            
            if self.mirror_mode:
                self.telegram_bot.add_handler('mirror', self.handle_mirror_command)
            
            # 자연어 메시지 핸들러 추가
            self.telegram_bot.add_message_handler(self.handle_natural_language)
            
            # 텔레그램 봇 시작
            logger.info("텔레그램 봇 시작 중...")
            await self.telegram_bot.start()
            
            mode_text = "미러 트레이딩" if self.mirror_mode else "분석 전용"
            ml_text = " + ML 예측" if self.ml_mode else ""
            
            # 시작 메시지 발송
            start_message = f"""🚀 <b>비트코인 전용 시스템 v2.3 시작!</b>

🔧 <b>작동 모드:</b> {mode_text}{ml_text}
📅 <b>시작 시간:</b> {self.startup_time.strftime('%Y-%m-%d %H:%M:%S')}

⚡ <b>주요 기능:</b>
• 📊 실시간 선물 시장 분석
• 🎯 롱/숏 진입점 예측  
• 📈 펀딩비 & CVD 추적
• 📰 AI 뉴스 영향도 분석"""

            if self.mirror_mode:
                start_message += f"""

🔥 <b>미러 트레이딩 시스템 강화:</b>
• 🛡️ 게이트 예약주문 10분간 보호
• 🔒 비트겟 취소 시에만 게이트 취소
• 🔍 삼중 검증으로 오취소 방지
• 📊 실시간 동기화"""
            
            start_message += f"""

📋 <b>리포트 일정:</b>
• 09:00, 13:00, 17:00, 22:00 (자동)
• 예외 상황 즉시 알림
• 급속 변동 2분마다 체크

✅ 모든 시스템이 정상 작동 중입니다!"""

            await self.telegram_bot.send_message(start_message, parse_mode='HTML')
            
            logger.info("=" * 50)
            logger.info(f"✅ 비트코인 전용 시스템 시작 완료 ({mode_text}{ml_text})")
            if self.mirror_mode:
                logger.info("🔥 게이트 예약주문 자동취소 방지 시스템 강화 완료")
            logger.info("=" * 50)
            
            # 메인 루프 실행
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"시스템 시작 실패: {e}")
            logger.debug(traceback.format_exc())
            raise
    
    async def shutdown(self):
        """시스템 종료"""
        try:
            logger.info("=" * 50)
            logger.info("시스템 종료 프로세스 시작")
            logger.info("=" * 50)
            
            self.is_running = False
            
            # 종료 메시지 발송
            try:
                shutdown_msg = "🛑 <b>비트코인 전용 시스템 종료</b>\n\n시스템이 안전하게 종료됩니다."
                if self.mirror_mode:
                    shutdown_msg += "\n🔥 미러 트레이딩도 함께 종료됩니다."
                
                await self.telegram_bot.send_message(shutdown_msg, parse_mode='HTML')
            except:
                pass
            
            # 스케줄러 종료
            logger.info("스케줄러 종료 중...")
            self.scheduler.shutdown()
            
            # 텔레그램 봇 종료
            logger.info("텔레그램 봇 종료 중...")
            await self.telegram_bot.stop()
            
            # 미러 트레이딩 종료
            if self.mirror_mode and self.mirror_trading:
                logger.info("🔥 미러 트레이딩 종료 중... (게이트 예약주문 보호 유지)")
                await self.mirror_trading.stop()
            
            # 데이터 수집기 종료
            logger.info("데이터 수집기 종료 중...")
            if self.data_collector.session:
                await self.data_collector.close()
            
            # Bitget 클라이언트 종료
            logger.info("Bitget 클라이언트 종료 중...")
            if self.bitget_client.session:
                await self.bitget_client.close()
            
            # Gate.io 클라이언트 종료
            if self.gate_client and self.gate_client.session:
                logger.info("Gate.io 클라이언트 종료 중...")
                await self.gate_client.close()
            
            # ML 예측기 데이터 저장
            if self.ml_mode and self.ml_predictor:
                logger.info("ML 예측 데이터 저장 중...")
                self.ml_predictor.save_predictions()
            
            logger.info("=" * 50)
            logger.info("✅ 비트코인 전용 시스템이 안전하게 종료되었습니다")
            if self.mirror_mode:
                logger.info("🔥 게이트 예약주문 보호 시스템이 안전하게 종료되었습니다")
            logger.info("=" * 50)
            
        except Exception as e:
            logger.error(f"시스템 종료 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())

async def main():
    """메인 함수"""
    try:
        print("\n" + "=" * 50)
        print("🚀 비트코인 예측 시스템 v2.3 - 비트코인 전용")
        print("🔥 게이트 예약주문 자동취소 방지 시스템 강화")
        print("=" * 50 + "\n")
        
        system = BitcoinPredictionSystem()
        await system.start()
        
    except Exception as e:
        print(f"\n❌ 치명적 오류 발생: {e}")
        logger.error(f"치명적 오류: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n\n치명적 오류: {e}")
        logger.error(f"프로그램 실행 실패: {e}")
        logger.debug(traceback.format_exc())
