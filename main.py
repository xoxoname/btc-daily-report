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
    from mirror_trading import MirrorTradingSystem
    from mirror_trading_utils import MirrorTradingUtils
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

class BitcoinPredictionSystem:
    """비트코인 예측 및 분석 시스템 - 렌더 최적화 + 미러 트레이딩 통합 강화"""
    
    def __init__(self):
        # 기본 설정
        self.config = Config()
        self.logger = self._setup_logging()
        
        # 시스템 상태
        self.is_running = False
        self.startup_time = None
        self.last_heartbeat = datetime.now()
        
        # 🔥🔥🔥 미러 트레이딩 모드 확인 - 강화된 로직
        self.mirror_mode = (
            self.config.MIRROR_TRADING_MODE or 
            self.config.ENABLE_MIRROR_TRADING
        ) and MIRROR_TRADING_AVAILABLE
        
        # ML 모드 확인
        self.ml_mode = ML_PREDICTOR_AVAILABLE and bool(self.config.OPENAI_API_KEY)
        
        # 통계
        self.command_stats = {
            'report': 0, 'forecast': 0, 'profit': 0, 'schedule': 0, 
            'stats': 0, 'mirror': 0, 'natural_language': 0, 'errors': 0
        }
        
        self.exception_stats = {
            'news_alerts': 0, 'price_alerts': 0, 'volume_alerts': 0,
            'funding_alerts': 0, 'short_term_alerts': 0
        }
        
        # 클라이언트 초기화
        self._initialize_clients()
        
        # 컴포넌트 초기화
        self._initialize_components()
        
        # 스케줄러 초기화
        self._initialize_scheduler()
        
        # 미러 트레이딩 시스템 (초기화 단계에서는 None으로 설정)
        self.mirror_trading = None
        
        # ML 예측기
        self.ml_predictor = None
        
        self.logger.info("=" * 50)
        self.logger.info("🚀 비트코인 예측 시스템 초기화 완료")
        if self.mirror_mode:
            self.logger.info("🔥🔥🔥 미러 트레이딩 모드 활성화 (강화된 버전)")
        if self.ml_mode:
            self.logger.info("🤖 ML 예측 모드 활성화")
        self.logger.info("=" * 50)
    
    def _setup_logging(self):
        """로깅 설정"""
        # 기본 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
            ]
        )
        
        # 외부 라이브러리 로그 레벨 조정 (Render 환경 최적화)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        logging.getLogger('telegram').setLevel(logging.WARNING)
        logging.getLogger('aiohttp').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)

    def _initialize_clients(self):
        """클라이언트 초기화"""
        try:
            # Bitget 클라이언트
            self.bitget_client = BitgetClient(self.config)
            self.logger.info("✅ Bitget 클라이언트 생성 완료")
            
            # 텔레그램 봇
            self.telegram_bot = TelegramBot(self.config)
            self.logger.info("✅ 텔레그램 봇 생성 완료")
            
            # Gate.io 클라이언트 (미러 트레이딩용)
            if self.mirror_mode and MIRROR_TRADING_AVAILABLE:
                try:
                    # 미러 트레이딩 모드에서 Gate.io 클라이언트 생성
                    self.gate_client = GateClient(self.config)
                    self.logger.info("✅ Gate.io 미러링 클라이언트 생성 완료")
                except Exception as e:
                    self.logger.error(f"Gate.io 미러링 클라이언트 생성 실패: {e}")
                    self.logger.warning("미러 트레이딩 없이 계속 진행")
                    self.mirror_mode = False
            else:
                # 분석용 Gate.io 클라이언트 (선택적)
                try:
                    if os.getenv('GATE_API_KEY') and os.getenv('GATE_API_SECRET'):
                        self.gate_client = GateClient(self.config)
                        self.logger.info("✅ 분석용 Gate.io 클라이언트 생성 완료")
                    else:
                        self.logger.info("Gate.io API 키가 없어 Bitget 전용으로 실행")
                        self.gate_client = None
                except Exception as e:
                    self.logger.warning(f"분석용 Gate.io 클라이언트 초기화 실패: {e}")
                    self.gate_client = None
            
        except Exception as e:
            self.logger.error(f"클라이언트 초기화 실패: {e}")
            raise

    def _initialize_components(self):
        """컴포넌트 초기화"""
        try:
            # 데이터 수집기
            self.data_collector = RealTimeDataCollector(self.config, self.bitget_client)
            self.logger.info("✅ 데이터 수집기 초기화 완료")
            
            # 고급 지표 시스템
            self.indicator_system = AdvancedTradingIndicators(self.data_collector)
            self.logger.info("✅ 고급 지표 시스템 초기화 완료")
            
            # 분석 엔진
            self.analysis_engine = AnalysisEngine(self.config, self.data_collector)
            self.logger.info("✅ 분석 엔진 초기화 완료")
            
            # 🔥🔥 예외 감지기 - 올바른 인자로 수정
            self.exception_detector = ExceptionDetector(
                bitget_client=self.bitget_client,
                gate_client=self.gate_client,
                config=self.config,
                data_collector=self.data_collector,
                telegram_bot=self.telegram_bot
            )
            self.logger.info("✅ 예외 감지기 초기화 완료")
            
            # 리포트 생성기
            self.report_manager = ReportGeneratorManager(
                self.config, 
                self.bitget_client, 
                self.analysis_engine,
                self.indicator_system
            )
            self.logger.info("✅ 리포트 생성기 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"컴포넌트 초기화 실패: {e}")
            raise

    def _initialize_scheduler(self):
        """스케줄러 초기화"""
        try:
            # KST 타임존 설정
            kst = pytz.timezone('Asia/Seoul')
            
            self.scheduler = AsyncIOScheduler(timezone=kst)
            
            # 🔥🔥🔥 분석 작업 (빈도 조정)
            self.scheduler.add_job(
                self.periodic_analysis, 'interval', minutes=30,
                id='periodic_analysis', replace_existing=True
            )
            
            # 예외 감지 (빈도 증가)
            self.scheduler.add_job(
                self.check_anomalies, 'interval', minutes=5,
                id='anomaly_check', replace_existing=True
            )
            
            # 급속 변동 감지 (고빈도)
            self.scheduler.add_job(
                self.check_rapid_changes, 'interval', minutes=2,
                id='rapid_change_check', replace_existing=True
            )
            
            # 일일 리포트 (오전 9시)
            self.scheduler.add_job(
                self.daily_report, 'cron', hour=9, minute=0,
                id='daily_report', replace_existing=True
            )
            
            # 시간별 업데이트 (매시 정각)
            self.scheduler.add_job(
                self.hourly_update, 'cron', minute=0,
                id='hourly_update', replace_existing=True
            )
            
            # 6시간마다 종합 리포트
            self.scheduler.add_job(
                self.handle_report_command, 'interval', hours=6,
                id='comprehensive_report', replace_existing=True
            )
            
            # 🔥🔥🔥 미러 트레이딩 작업 (미러 모드일 때만)
            if self.mirror_mode:
                # 미러 트레이딩 일일 리포트 (오전 9시 30분)
                self.scheduler.add_job(
                    self.mirror_daily_report, 'cron', hour=9, minute=30,
                    id='mirror_daily_report', replace_existing=True
                )
                
                # 미러 트레이딩 시세 리포트 (6시간마다)
                self.scheduler.add_job(
                    self.mirror_price_report, 'interval', hours=6,
                    id='mirror_price_report', replace_existing=True
                )
            
            # 시스템 상태 체크 (30분마다)
            self.scheduler.add_job(
                self.system_health_check, 'interval', minutes=30,
                id='health_check', replace_existing=True
            )
            
            # 하트비트
            self.scheduler.add_job(
                self.update_heartbeat, 'interval', minutes=5,
                id='heartbeat', replace_existing=True
            )
            
            self.logger.info("✅ 스케줄러 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"스케줄러 초기화 실패: {e}")
            raise

    async def update_heartbeat(self):
        """하트비트 업데이트"""
        self.last_heartbeat = datetime.now()
        self.logger.debug("💓 하트비트 업데이트")

    async def periodic_analysis(self):
        """주기적 분석"""
        try:
            self.logger.info("📊 주기적 분석 시작")
            
            # 기본 분석 실행
            await self.analysis_engine.update_analysis()
            
            # ML 예측 (있는 경우)
            if self.ml_mode and self.ml_predictor:
                try:
                    await self.ml_predictor.update_predictions()
                except Exception as e:
                    self.logger.warning(f"ML 예측 업데이트 실패: {e}")
            
            self.logger.info("✅ 주기적 분석 완료")
            
        except Exception as e:
            self.logger.error(f"주기적 분석 실패: {e}")

    async def check_anomalies(self):
        """이상 징후 체크"""
        try:
            anomalies = await self.exception_detector.detect_exceptions()
            
            for anomaly in anomalies:
                await self.handle_anomaly_notification(anomaly)
                
        except Exception as e:
            self.logger.error(f"이상 징후 체크 실패: {e}")

    async def check_rapid_changes(self):
        """급속 변동 체크"""
        try:
            changes = await self.exception_detector.detect_rapid_changes()
            
            for change in changes:
                await self.handle_anomaly_notification(change)
                
        except Exception as e:
            self.logger.error(f"급속 변동 체크 실패: {e}")

    async def daily_report(self):
        """일일 리포트"""
        try:
            self.logger.info("📊 일일 리포트 생성 중...")
            
            report = await self.report_manager.generate_daily_report()
            if report:
                await self.telegram_bot.send_message_safe(f"📊 일일 리포트\n\n{report}")
                
        except Exception as e:
            self.logger.error(f"일일 리포트 실패: {e}")

    async def hourly_update(self):
        """시간별 업데이트"""
        try:
            self.logger.debug("⏰ 시간별 업데이트 실행")
            
            # 데이터 정리 및 업데이트
            await self.data_collector.cleanup_old_data()
            
        except Exception as e:
            self.logger.error(f"시간별 업데이트 실패: {e}")

    async def handle_anomaly_notification(self, anomaly):
        """이상 징후 알림 처리"""
        try:
            anomaly_type = anomaly.get('type', 'unknown')
            
            # 통계 업데이트
            if 'news' in anomaly_type:
                self.exception_stats['news_alerts'] += 1
            elif 'price' in anomaly_type:
                self.exception_stats['price_alerts'] += 1
            elif 'volume' in anomaly_type:
                self.exception_stats['volume_alerts'] += 1
            elif 'funding' in anomaly_type:
                self.exception_stats['funding_alerts'] += 1
            elif 'short_term' in anomaly_type:
                self.exception_stats['short_term_alerts'] += 1
            
            # 리포트 생성 및 전송
            if self.report_manager and hasattr(self.report_manager, 'generate_exception_report'):
                report = await self.report_manager.generate_exception_report(anomaly)
                if report:
                    await self.telegram_bot.send_message_safe(report)
                    
        except Exception as e:
            self.logger.error(f"이상 징후 알림 처리 실패: {e}")

    async def system_health_check(self):
        """시스템 상태 체크"""
        try:
            now = datetime.now()
            
            # 하트비트 체크
            if (now - self.last_heartbeat).total_seconds() > 600:  # 10분
                self.logger.warning("시스템 하트비트 이상 감지")
                await self.telegram_bot.send_message_safe("⚠️ 시스템 하트비트 이상 감지")
            
            # 메모리 체크
            try:
                import psutil
                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / 1024 / 1024
                
                if memory_mb > 500:  # 500MB 이상
                    self.logger.warning(f"높은 메모리 사용량: {memory_mb:.1f}MB")
                    
            except ImportError:
                pass
            
            self.logger.debug("시스템 상태 체크 완료")
            
        except Exception as e:
            self.logger.error(f"시스템 상태 체크 실패: {e}")

    async def mirror_daily_report(self):
        """🔥🔥🔥 미러 트레이딩 일일 리포트 - 강화"""
        try:
            if not self.mirror_mode or not self.mirror_trading:
                return
            
            report = await self.mirror_trading.generate_daily_report()
            if report:
                await self.telegram_bot.send_message_safe(f"📊 미러 트레이딩 일일 리포트\n\n{report}")
                
        except Exception as e:
            self.logger.error(f"미러 트레이딩 일일 리포트 실패: {e}")

    async def mirror_price_report(self):
        """🔥🔥🔥 미러 트레이딩 시세 리포트 - 강화"""
        try:
            if not self.mirror_mode or not self.mirror_trading:
                return
            
            report = await self.mirror_trading.generate_price_report()
            if report:
                await self.telegram_bot.send_message_safe(f"💰 시세 차이 현황\n\n{report}")
                
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시세 리포트 실패: {e}")

    async def send_startup_notification(self):
        """시작 알림 전송"""
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            uptime = str(datetime.now() - self.startup_time).split('.')[0]
            
            message = f"""🚀 비트코인 분석 시스템 시작

⏰ 시작 시간: {current_time}
🔄 부팅 시간: {uptime}
📊 모드: {'🔥 미러 트레이딩 + 분석' if self.mirror_mode else '📈 분석 전용'}
🤖 AI 예측: {'활성화' if self.ml_mode else '비활성화'}

✅ 모든 시스템이 정상 작동 중입니다!
📈"""
            
            await self.telegram_bot.send_message_safe(message)
            
        except Exception as e:
            self.logger.error(f"시작 알림 전송 실패: {e}")

    def register_handlers(self):
        """텔레그램 핸들러 등록"""
        try:
            application = self.telegram_bot.application
            
            # 기본 명령어 핸들러들
            from telegram.ext import CommandHandler
            
            application.add_handler(CommandHandler("start", self.handle_start_command))
            application.add_handler(CommandHandler("report", self.handle_report_command))
            application.add_handler(CommandHandler("forecast", self.handle_forecast_command))
            application.add_handler(CommandHandler("profit", self.handle_profit_command))
            application.add_handler(CommandHandler("schedule", self.handle_schedule_command))
            application.add_handler(CommandHandler("stats", self.handle_stats_command))
            
            if self.mirror_mode:
                application.add_handler(CommandHandler("mirror", self.handle_mirror_command))
            
            # 자연어 처리 핸들러
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_natural_language))
            
            self.logger.info("✅ 텔레그램 핸들러 등록 완료")
            
        except Exception as e:
            self.logger.error(f"핸들러 등록 실패: {e}")
            raise

    async def handle_report_command(self, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None):
        """종합 분석 리포트 명령"""
        try:
            self.command_stats['report'] += 1
            
            if update:
                await update.message.reply_text("📊 종합 분석 리포트 생성 중...", parse_mode='HTML')
            
            report = await self.report_manager.generate_regular_report()
            
            if update:
                await self.send_split_message(update.message.reply_text, report)
            else:
                await self.telegram_bot.send_message_safe(report)
                
        except Exception as e:
            self.logger.error(f"리포트 생성 실패: {e}")
            self.command_stats['errors'] += 1
            
            error_msg = "❌ 리포트 생성 중 오류가 발생했습니다."
            if update:
                await update.message.reply_text(error_msg, parse_mode='HTML')

    async def handle_forecast_command(self, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None):
        """예측 리포트 명령"""
        try:
            self.command_stats['forecast'] += 1
            
            if update:
                await update.message.reply_text("🎯 단기 예측 분석 중...", parse_mode='HTML')
            
            forecast = await self.report_manager.generate_forecast_report()
            
            if update:
                await self.send_split_message(update.message.reply_text, forecast)
            else:
                await self.telegram_bot.send_message_safe(forecast)
                
        except Exception as e:
            self.logger.error(f"예측 리포트 생성 실패: {e}")
            self.command_stats['errors'] += 1
            
            error_msg = "❌ 예측 리포트 생성 중 오류가 발생했습니다."
            if update:
                await update.message.reply_text(error_msg, parse_mode='HTML')

    async def handle_profit_command(self, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None):
        """손익 현황 명령"""
        try:
            self.command_stats['profit'] += 1
            
            if update:
                await update.message.reply_text("💰 손익 현황 조회 중...", parse_mode='HTML')
            
            profit_report = await self.report_manager.generate_profit_report()
            
            if update:
                await self.send_split_message(update.message.reply_text, profit_report)
            else:
                await self.telegram_bot.send_message_safe(profit_report)
                
        except Exception as e:
            self.logger.error(f"손익 리포트 생성 실패: {e}")
            self.command_stats['errors'] += 1
            
            error_msg = "❌ 손익 현황 조회 중 오류가 발생했습니다."
            if update:
                await update.message.reply_text(error_msg, parse_mode='HTML')

    async def handle_schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """일정 안내 명령"""
        try:
            self.command_stats['schedule'] += 1
            
            schedule = await self.report_manager.generate_schedule_report()
            await update.message.reply_text(schedule, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"일정 안내 생성 실패: {e}")
            self.command_stats['errors'] += 1
            await update.message.reply_text("❌ 일정 안내 생성 중 오류가 발생했습니다.", parse_mode='HTML')

    async def handle_mirror_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """미러 트레이딩 상태 조회"""
        try:
            self.command_stats['mirror'] += 1
            
            if not self.mirror_mode or not self.mirror_trading:
                await update.message.reply_text("❌ 미러 트레이딩이 비활성화되어 있습니다.", parse_mode='HTML')
                return
            
            status = await self.mirror_trading.get_status_report()
            await self.send_split_message(update.message.reply_text, status)
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 상태 조회 실패: {e}")
            self.command_stats['errors'] += 1
            await update.message.reply_text("❌ 미러 트레이딩 상태 조회 중 오류가 발생했습니다.", parse_mode='HTML')

    async def handle_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시스템 통계 명령"""
        try:
            self.command_stats['stats'] += 1
            
            uptime = str(datetime.now() - self.startup_time).split('.')[0] if self.startup_time else "측정 불가"
            total_exceptions = sum(self.exception_stats.values())
            
            report = f"""📊 <b>시스템 통계</b>

<b>⏱️ 시스템 정보:</b>
- 가동 시간: {uptime}
- 시작 시간: {self.startup_time.strftime('%m/%d %H:%M') if self.startup_time else '측정 불가'}
- 모드: {'🔥 미러 트레이딩' if self.mirror_mode else '📈 분석 전용'}
- ML 예측: {'🤖 활성화' if self.ml_mode else '❌ 비활성화'}
- 현재 시간: {datetime.now().strftime('%H:%M:%S')}
- Python 버전: {'.'.join(map(str, sys.version_info[:3]))}
- 프로세스 PID: {os.getpid()}
- 마지막 하트비트: {self.last_heartbeat.strftime('%H:%M:%S')}

<b>📱 명령어 사용 통계:</b>
- 종합 리포트: {self.command_stats['report']}회
- 예측 분석: {self.command_stats['forecast']}회
- 손익 현황: {self.command_stats['profit']}회
- 일정 안내: {self.command_stats['schedule']}회
- 시스템 통계: {self.command_stats['stats']}회"""
            
            if self.mirror_mode:
                report += f"\n- 미러 트레이딩: {self.command_stats['mirror']}회"
            
            report += f"""
- 자연어 질문: {self.command_stats['natural_language']}회
- 오류 발생: {self.command_stats['errors']}회

<b>🚨 예외 감지 통계:</b>
- 총 감지: {total_exceptions}건
- 뉴스 알림: {self.exception_stats['news_alerts']}건
- 가격 급변: {self.exception_stats['price_alerts']}건
- 거래량 급증: {self.exception_stats['volume_alerts']}건
- 펀딩비 이상: {self.exception_stats['funding_alerts']}건
- 단기 변동: {self.exception_stats['short_term_alerts']}건

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
            
            # 🔥🔥🔥 미러 트레이딩 통계 추가 - 강화된 정보
            if self.mirror_mode and self.mirror_trading:
                mirror_stats = self.mirror_trading.daily_stats
                report += f"""

<b>🔄 미러 트레이딩 통계 (강화):</b>
- 총 시도: {mirror_stats['total_mirrored']}회
- 성공: {mirror_stats['successful_mirrors']}회
- 실패: {mirror_stats['failed_mirrors']}회
- 예약 주문 미러링: {mirror_stats['plan_order_mirrors']}회
- 예약 주문 취소: {mirror_stats['plan_order_cancels']}회
- 클로즈 주문: {mirror_stats['close_order_mirrors']}회
- 강제 동기화: {mirror_stats.get('force_sync_count', 0)}회
- 부분 청산: {mirror_stats['partial_closes']}회
- 전체 청산: {mirror_stats['full_closes']}회
- 총 거래량: ${mirror_stats['total_volume']:,.2f}"""
            
            report += f"""

<b>🔧 시스템 설정:</b>
- 예외 감지: 5분마다
- 급속 변동: 2분마다
- 뉴스 수집: 15초마다
- 가격 임계값: {self.exception_detector.PRICE_CHANGE_THRESHOLD}%
- 거래량 임계값: {self.exception_detector.VOLUME_SPIKE_THRESHOLD}배"""

            if self.mirror_mode:
                report += f"""
- 미러 체크: 5초마다 (강화)
- 강제 동기화: 15초마다 (강화)
- 스타트업 제외: 10분 (단축)"""

            report += f"""

━━━━━━━━━━━━━━━━━━━
⚡ 비트코인 전용 시스템이 완벽히 작동 중입니다!"""
            
            await self.send_split_message(update.message.reply_text, report)
            
        except Exception as e:
            self.logger.error(f"통계 생성 실패: {e}")
            self.command_stats['errors'] += 1
            await update.message.reply_text("❌ 통계 생성 중 오류가 발생했습니다.", parse_mode='HTML')

    async def send_split_message(self, send_func, text, max_length=4000):
        """긴 메시지 분할 전송"""
        try:
            if len(text) <= max_length:
                await send_func(text, parse_mode='HTML')
                return
            
            # 메시지 분할
            parts = []
            current_part = ""
            
            lines = text.split('\n')
            for line in lines:
                if len(current_part + line + '\n') > max_length:
                    if current_part:
                        parts.append(current_part.strip())
                        current_part = line + '\n'
                    else:
                        # 한 줄이 너무 긴 경우
                        parts.append(line[:max_length-3] + '...')
                else:
                    current_part += line + '\n'
            
            if current_part:
                parts.append(current_part.strip())
            
            # 분할 전송
            for i, part in enumerate(parts):
                if i > 0:
                    await asyncio.sleep(1)  # 분할 전송 간 지연
                await send_func(f"{part}", parse_mode='HTML')
                
        except Exception as e:
            self.logger.error(f"분할 메시지 전송 실패: {e}")
            await send_func("❌ 메시지가 너무 길어 전송에 실패했습니다.", parse_mode='HTML')

    async def handle_natural_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """자연어 처리"""
        try:
            self.command_stats['natural_language'] += 1
            
            user_message = update.message.text.lower()
            
            # 키워드 기반 응답
            if any(keyword in user_message for keyword in ['안녕', '시작', '헬로', 'hello', 'hi']):
                response = "안녕하세요! 👋 비트코인 분석 시스템입니다.\n\n사용 가능한 명령어:\n"
                response += "• /report - 종합 분석 리포트\n"
                response += "• /forecast - 단기 예측\n"
                response += "• /profit - 손익 현황\n"
                response += "• /stats - 시스템 통계"
                if self.mirror_mode:
                    response += "\n• /mirror - 미러 트레이딩 상태"
                
            elif any(keyword in user_message for keyword in ['리포트', 'report', '분석', '현황']):
                await update.message.reply_text("📊 종합 분석 리포트를 생성하겠습니다...", parse_mode='HTML')
                await self.handle_report_command(update, context)
                return
                
            elif any(keyword in user_message for keyword in ['예측', 'forecast', '전망']):
                await update.message.reply_text("🎯 예측 분석을 시작하겠습니다...", parse_mode='HTML')
                await self.handle_forecast_command(update, context)
                return
                
            elif any(keyword in user_message for keyword in ['손익', 'profit', '수익', 'pnl']):
                await update.message.reply_text("💰 손익 현황을 조회하겠습니다...", parse_mode='HTML')
                await self.handle_profit_command(update, context)
                return
                
            elif any(keyword in user_message for keyword in ['통계', 'stats', '상태', 'status']):
                await self.handle_stats_command(update, context)
                return
                
            elif self.mirror_mode and any(keyword in user_message for keyword in ['미러', 'mirror', '복사']):
                await self.handle_mirror_status(update, context)
                return
                
            elif any(keyword in user_message for keyword in ['매수', 'buy', '살까', '사도 될까']):
                response = "🤔 투자 결정은 신중히 내리세요!\n\n"
                response += "현재 시장 분석을 위해 /report 명령어를 사용해보세요.\n"
                response += "단기 예측은 /forecast 명령어로 확인 가능합니다."
                
            elif any(keyword in user_message for keyword in ['시장', 'market', '상황']):
                response = "📈 실시간 시장 분석을 위해 다음 명령어를 사용해보세요:\n\n"
                response += "• /report - 현재 시장 종합 분석\n"
                response += "• /forecast - 단기 시장 전망"
                
            else:
                response = f"죄송하지만 '{user_message[:50]}...' 질문을 이해하지 못했습니다.\n\n"
                response += "다음 명령어를 사용해보세요:\n"
                response += "• /report - 종합 분석\n"
                response += "• /forecast - 예측 분석\n"
                response += "• /profit - 손익 현황\n"
                response += "• /stats - 시스템 통계\n\n"
                response += "또는 다음과 같이 질문해보세요:\n"
                response += "- \"지금 매수해도 돼?\"\n"
                response += "- \"시장 상황 어때?\"\n"
                response += "- \"다음 리포트 언제?\"\n"
                response += "- \"시스템 통계 보여줘\""
                
                if self.mirror_mode:
                    response += '\n• "미러 트레이딩 상태는?"\n'
                
                response += "\n도움이 필요하시면 언제든 질문해주세요! 😊"
                
            await update.message.reply_text(response, parse_mode='HTML')
                
        except Exception as e:
            self.logger.error(f"자연어 처리 실패: {e}")
            self.command_stats['errors'] += 1
            await update.message.reply_text("❌ 질문 처리 중 오류가 발생했습니다.", parse_mode='HTML')

    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시작 명령 처리"""
        try:
            self.command_stats['stats'] += 1
            
            welcome_message = f"""🚀 <b>비트코인 분석 시스템</b>

안녕하세요! 비트코인 전용 분석 및 예측 시스템입니다.

<b>📊 주요 기능:</b>
• 실시간 가격 분석 및 예측
• 이상 징후 자동 감지
• 정기 리포트 생성
• 손익 현황 추적"""

            if self.mirror_mode:
                welcome_message += '\n• 🔥 미러 트레이딩 (비트겟 → 게이트)'
            
            if self.ml_mode:
                welcome_message += '\n• 🤖 AI 기반 예측'

            welcome_message += f"""

<b>💬 사용 가능한 명령어:</b>
• /report - 종합 분석 리포트
• /forecast - 단기 예측 분석  
• /profit - 손익 현황
• /schedule - 자동 리포트 일정
• /stats - 시스템 통계

<b>🗣️ 자연어로도 대화 가능:</b>
- "지금 매수해도 돼?"
- "시장 상황 어때?"
- "다음 리포트 언제?"
- "시스템 통계 보여줘"
"""
            
            if self.mirror_mode:
                welcome_message += '• "미러 트레이딩 상태는?"\n'
            
            welcome_message += "\n도움이 필요하시면 언제든 질문해주세요! 😊"
            
            await update.message.reply_text(welcome_message, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"시작 명령 처리 실패: {e}")
            await update.message.reply_text("❌ 도움말 생성 중 오류가 발생했습니다.", parse_mode='HTML')
    
    async def handle_mirror_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """미러 트레이딩 상태 명령"""
        await self.handle_mirror_status(update, context)
    
    async def start(self):
        """시스템 시작"""
        try:
            self.logger.info("=" * 50)
            self.logger.info("시스템 시작 프로세스 개시 - 비트코인 전용")
            self.logger.info("=" * 50)
            
            self.is_running = True
            self.startup_time = datetime.now()
            
            # Bitget 클라이언트 초기화
            self.logger.info("Bitget 클라이언트 초기화 중...")
            await self.bitget_client.initialize()
            
            # Gate.io 클라이언트 초기화 (있는 경우)
            if self.gate_client:
                self.logger.info("Gate.io 클라이언트 초기화 중...")
                await self.gate_client.initialize()
            
            # 데이터 수집기 시작
            self.logger.info("데이터 수집기 시작 중...")
            asyncio.create_task(self.data_collector.start())
            
            # 🔥🔥🔥 미러 트레이딩 시작 (미러 모드일 때만) - 강화된 초기화
            if self.mirror_mode and self.mirror_trading:
                self.logger.info("🔥🔥🔥 미러 트레이딩 시스템 시작 중... (강화된 버전)")
                await self.mirror_trading.start()
                self.logger.info("✅ 미러 트레이딩 시스템 시작 완료")
            elif self.mirror_mode:
                self.logger.warning("미러 트레이딩 모드이지만 시스템이 초기화되지 않았습니다")
            
            # ML 예측기 초기화
            if self.ml_mode and ML_PREDICTOR_AVAILABLE:
                try:
                    self.ml_predictor = MLPredictor()
                    self.logger.info("✅ ML 예측기 초기화 완료")
                except Exception as e:
                    self.logger.error(f"ML 예측기 초기화 실패: {e}")
                    self.ml_mode = False
            
            # 텔레그램 봇 시작
            self.logger.info("텔레그램 봇 시작 중...")
            await self.telegram_bot.start()
            
            # 핸들러 등록
            self.register_handlers()
            
            # 스케줄러 시작
            self.logger.info("스케줄러 시작 중...")
            if not self.scheduler.running:
                self.scheduler.start()
            
            # 시작 알림
            await self.send_startup_notification()
            
            self.logger.info("=" * 50)
            self.logger.info("✅ 시스템 시작 완료!")
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"시스템 시작 실패: {e}")
            self.logger.error(traceback.format_exc())
            raise

    async def stop(self):
        """시스템 종료"""
        try:
            self.logger.info("시스템 종료 프로세스 시작...")
            
            self.is_running = False
            
            # 스케줄러 종료
            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                self.logger.info("✅ 스케줄러 종료 완료")
            
            # 미러 트레이딩 종료
            if self.mirror_trading:
                await self.mirror_trading.stop()
                self.logger.info("✅ 미러 트레이딩 시스템 종료 완료")
            
            # 데이터 수집기 종료
            if self.data_collector:
                await self.data_collector.stop()
                self.logger.info("✅ 데이터 수집기 종료 완료")
            
            # 텔레그램 봇 종료
            if self.telegram_bot:
                await self.telegram_bot.stop()
                self.logger.info("✅ 텔레그램 봇 종료 완료")
            
            # 클라이언트 세션 종료
            if self.bitget_client:
                await self.bitget_client.close()
                self.logger.info("✅ Bitget 클라이언트 종료 완료")
            
            if self.gate_client:
                await self.gate_client.close()
                self.logger.info("✅ Gate.io 클라이언트 종료 완료")
            
            self.logger.info("시스템 종료 완료")
            
        except Exception as e:
            self.logger.error(f"시스템 종료 중 오류: {e}")

    def setup_signal_handlers(self):
        """시그널 핸들러 설정"""
        def signal_handler(signum, frame):
            self.logger.info(f"시그널 {signum} 수신, 종료 프로세스 시작...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """메인 함수"""
    system = None
    try:
        # 🔥🔥🔥 미러 트레이딩 시스템 생성 및 시작 - 강화된 초기화
        system = BitcoinPredictionSystem()
        
        # 미러 트레이딩 시스템 초기화 (미러 모드일 때만)
        if system.mirror_mode and MIRROR_TRADING_AVAILABLE:
            try:
                # 🔥🔥🔥 누락된 인자들 추가: bitget_mirror, gate_mirror, utils
                
                # BitgetClient를 미러링 클라이언트로 사용 (bitget_mirror)
                bitget_mirror = system.bitget_client
                
                # GateClient를 미러링 클라이언트로 사용 (gate_mirror)  
                gate_mirror = system.gate_client
                
                # MirrorTradingUtils 인스턴스 생성 (utils)
                utils = MirrorTradingUtils(system.config, system.bitget_client, system.gate_client)
                
                # 모든 필요한 인자로 MirrorTradingSystem 생성
                system.mirror_trading = MirrorTradingSystem(
                    system.config,
                    system.bitget_client,
                    system.gate_client,
                    bitget_mirror,
                    gate_mirror,
                    system.telegram_bot,
                    utils
                )
                system.logger.info("✅ 미러 트레이딩 시스템 생성 완료")
            except Exception as e:
                system.logger.error(f"미러 트레이딩 시스템 생성 실패: {e}")
                system.mirror_mode = False
        
        # 시그널 핸들러 설정
        system.setup_signal_handlers()
        
        # 시스템 시작
        await system.start()
        
        # 무한 실행
        while system.is_running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"시스템 오류: {e}")
        print(traceback.format_exc())
    finally:
        if system:
            try:
                await system.stop()
            except Exception as e:
                print(f"종료 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())
