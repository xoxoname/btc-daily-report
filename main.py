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
        logging.FileHandler('bitcoin_analysis.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class BitcoinAnalysisBot:
    """🔥🔥🔥 비트코인 전용 분석 봇 - 미러 트레이딩 통합"""
    
    def __init__(self):
        self.config = Config()
        
        # 기본 컴포넌트 초기화
        self.telegram_bot = TelegramBot(self.config)
        self.bitget_client = BitgetClient(self.config)
        self.data_collector = RealTimeDataCollector(self.config)
        self.indicator_system = AdvancedTradingIndicators()
        
        # 🔥🔥🔥 수정: AnalysisEngine은 bitget_client만 필요
        self.analysis_engine = AnalysisEngine(self.bitget_client)
        
        # 🔥🔥🔥 수정: ExceptionDetector는 config, data_collector, indicator_system 필요
        self.exception_detector = ExceptionDetector(self.config, self.data_collector, self.indicator_system)
        
        # 🔥🔥🔥 미러 트레이딩 시스템 초기화 (사용 가능한 경우)
        self.mirror_trading = None
        self.mirror_mode = False
        self.gate_client = None
        
        if MIRROR_TRADING_AVAILABLE and self._check_mirror_trading_config():
            try:
                self.gate_client = GateClient(self.config)
                self.mirror_trading = MirrorTradingSystem(
                    self.config, 
                    self.bitget_client, 
                    self.gate_client, 
                    self.telegram_bot
                )
                self.mirror_mode = True
                logger.info("🔥 미러 트레이딩 시스템 초기화 완료")
            except Exception as e:
                logger.error(f"미러 트레이딩 초기화 실패: {e}")
                self.mirror_mode = False
        else:
            logger.info("미러 트레이딩 비활성화 - 분석 전용 모드")
        
        # ML 예측기 초기화 (사용 가능한 경우)
        self.ml_predictor = None
        self.ml_mode = False
        
        if ML_PREDICTOR_AVAILABLE:
            try:
                self.ml_predictor = MLPredictor()
                self.ml_mode = True
                logger.info("🤖 ML 예측기 초기화 완료")
            except Exception as e:
                logger.error(f"ML 예측기 초기화 실패: {e}")
                self.ml_mode = False
        
        # 리포트 생성기
        self.report_generator = ReportGeneratorManager(
            self.config, 
            self.data_collector, 
            self.indicator_system,
            self.bitget_client
        )
        
        # 스케줄러
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Seoul'))
        
        # 상태 관리
        self.running = False
        self.last_price = 0
        self.last_volume = 0
        self.start_time = datetime.now()
        
        # 통계 관리
        self.command_stats = {
            'analysis': 0,
            'exception': 0,
            'news': 0,
            'prediction': 0,
            'mirror_status': 0,
            'help': 0,
            'natural_language': 0,
            'errors': 0
        }
        
        logger.info("🔥 비트코인 분석 봇 초기화 완료")
        
    def _check_mirror_trading_config(self) -> bool:
        """미러 트레이딩 설정 확인"""
        try:
            required_vars = [
                'BITGET_APIKEY', 'BITGET_APISECRET', 'BITGET_PASSPHRASE',
                'GATE_API_KEY', 'GATE_API_SECRET'
            ]
            
            missing_vars = [var for var in required_vars if not getattr(self.config, var, None)]
            
            if missing_vars:
                logger.warning(f"미러 트레이딩 필수 환경변수 누락: {missing_vars}")
                return False
                
            # ENABLE_MIRROR_TRADING 환경변수 확인
            enable_mirror = getattr(self.config, 'ENABLE_MIRROR_TRADING', 'false').lower()
            if enable_mirror not in ['true', '1', 'yes', 'on']:
                logger.info("ENABLE_MIRROR_TRADING이 비활성화됨")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"미러 트레이딩 설정 확인 실패: {e}")
            return False
    
    async def start(self):
        """봇 시작"""
        try:
            self.running = True
            logger.info("🚀 비트코인 분석 봇 시작")
            
            # 컴포넌트 초기화
            await self._initialize_components()
            
            # 스케줄 설정
            self._setup_schedules()
            
            # 🔥🔥🔥 미러 트레이딩 시작 (활성화된 경우)
            mirror_task = None
            if self.mirror_mode and self.mirror_trading:
                try:
                    mirror_task = asyncio.create_task(self.mirror_trading.start())
                    logger.info("🔥 미러 트레이딩 시스템 시작됨")
                except Exception as e:
                    logger.error(f"미러 트레이딩 시작 실패: {e}")
            
            # 시작 메시지
            await self._send_startup_message()
            
            # 메인 루프
            tasks = [
                self._run_exception_detector(),
                self._run_news_monitor(),
                self._run_telegram_bot()
            ]
            
            if mirror_task:
                tasks.append(mirror_task)
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"봇 시작 실패: {e}")
            await self.telegram_bot.send_message(f"❌ 시스템 시작 실패\n오류: {str(e)}")
            
    async def _initialize_components(self):
        """컴포넌트 초기화"""
        try:
            # Bitget 클라이언트 초기화
            if hasattr(self.bitget_client, 'initialize'):
                await self.bitget_client.initialize()
            
            # Gate 클라이언트 초기화 (미러 트레이딩이 활성화된 경우)
            if self.mirror_mode and self.gate_client and hasattr(self.gate_client, 'initialize'):
                await self.gate_client.initialize()
            
            # 데이터 수집기 초기화
            if hasattr(self.data_collector, 'initialize'):
                await self.data_collector.initialize()
            
            # 텔레그램 봇 초기화
            await self.telegram_bot.initialize()
            
            logger.info("✅ 모든 컴포넌트 초기화 완료")
            
        except Exception as e:
            logger.error(f"컴포넌트 초기화 실패: {e}")
            raise
    
    def _setup_schedules(self):
        """스케줄 설정"""
        try:
            # 정기 분석 리포트 (매시 정각)
            self.scheduler.add_job(
                self._generate_regular_report,
                'cron',
                minute=0,
                id='regular_report'
            )
            
            # 일일 성과 리포트 (매일 오전 9시)
            self.scheduler.add_job(
                self._generate_daily_performance_report,
                'cron',
                hour=9,
                minute=0,
                id='daily_performance'
            )
            
            # 시스템 상태 체크 (5분마다)
            self.scheduler.add_job(
                self._system_health_check,
                'interval',
                minutes=5,
                id='health_check'
            )
            
            self.scheduler.start()
            logger.info("✅ 스케줄러 시작됨")
            
        except Exception as e:
            logger.error(f"스케줄 설정 실패: {e}")
    
    async def _send_startup_message(self):
        """시작 메시지 전송"""
        try:
            mirror_status = "🔥 활성화" if self.mirror_mode else "⚠️ 비활성화"
            ml_status = "🤖 활성화" if self.ml_mode else "📊 기본 분석"
            
            message = f"""🚀 비트코인 분석 봇 시작됨

🎯 <b>전용 분석 대상:</b> 비트코인 (BTC/USDT)

🔧 <b>활성화된 기능:</b>
• 📊 실시간 시장 분석
• 🚨 예외 상황 감지
• 📰 뉴스 기반 이벤트 분석
• 🎯 기술적 지표 분석
• 📈 가격 예측 시스템
• 💬 자연어 질문 처리
• 🔥 미러 트레이딩: {mirror_status}
• 🤖 AI 예측: {ml_status}

💡 <b>사용법:</b>
/help - 전체 명령어 보기
"비트코인 어때?" - 자연어 질문
/analysis - 현재 분석
/exception - 예외 상황 체크
/news - 최신 뉴스 분석
/prediction - AI 예측
/mirror - 미러 트레이딩 상태
/status - 시스템 상태

🔥 시스템이 정상적으로 시작되었습니다!"""
            
            await self.telegram_bot.send_message(message, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"시작 메시지 전송 실패: {e}")
    
    async def _run_exception_detector(self):
        """예외 감지 실행"""
        while self.running:
            try:
                await self.exception_detector.run_detection()
                await asyncio.sleep(300)  # 5분마다
            except Exception as e:
                logger.error(f"예외 감지 실행 오류: {e}")
                await asyncio.sleep(600)  # 오류 시 10분 대기
    
    async def _run_news_monitor(self):
        """뉴스 모니터링 실행"""
        while self.running:
            try:
                await self.data_collector.collect_news_events()
                await asyncio.sleep(15)  # 15초마다
            except Exception as e:
                logger.error(f"뉴스 모니터링 오류: {e}")
                await asyncio.sleep(60)  # 오류 시 1분 대기
    
    async def _run_telegram_bot(self):
        """텔레그램 봇 실행"""
        try:
            # 메시지 핸들러 등록
            self.telegram_bot.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )
            
            # 명령어 핸들러들 등록
            await self.telegram_bot.setup_handlers()
            
            # 커스텀 명령어 추가
            self.telegram_bot.add_command_handler('analysis', self.cmd_analysis)
            self.telegram_bot.add_command_handler('exception', self.cmd_exception)
            self.telegram_bot.add_command_handler('news', self.cmd_news)
            self.telegram_bot.add_command_handler('prediction', self.cmd_prediction)
            self.telegram_bot.add_command_handler('mirror', self.cmd_mirror_status)
            self.telegram_bot.add_command_handler('status', self.cmd_system_status)
            
            # 봇 실행
            await self.telegram_bot.run()
            
        except Exception as e:
            logger.error(f"텔레그램 봇 실행 오류: {e}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """메시지 처리"""
        try:
            message_text = update.message.text.lower()
            
            # 비트코인 관련 자연어 질문 처리
            bitcoin_keywords = ['비트코인', 'btc', '코인', '가격', '분석', '예측', '어때', '상황']
            
            if any(keyword in message_text for keyword in bitcoin_keywords):
                self.command_stats['natural_language'] += 1
                await self._handle_natural_language_query(update, message_text)
            else:
                await update.message.reply_text(
                    "🔥 비트코인 전용 분석 봇입니다!\n"
                    "비트코인 관련 질문을 해주세요.\n"
                    "예: '비트코인 어때?', '현재 분석은?'\n"
                    "/help로 사용법을 확인하세요."
                )
                
        except Exception as e:
            logger.error(f"메시지 처리 오류: {e}")
            self.command_stats['errors'] += 1
            await update.message.reply_text("오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
    
    async def _handle_natural_language_query(self, update: Update, message_text: str):
        """자연어 질문 처리"""
        try:
            if '분석' in message_text or '어때' in message_text:
                await self.cmd_analysis(update, None)
            elif '뉴스' in message_text or '소식' in message_text:
                await self.cmd_news(update, None)
            elif '예측' in message_text or '전망' in message_text:
                await self.cmd_prediction(update, None)
            elif '미러' in message_text or '트레이딩' in message_text:
                await self.cmd_mirror_status(update, None)
            elif '상태' in message_text or '시스템' in message_text:
                await self.cmd_system_status(update, None)
            else:
                # 기본 분석 제공
                await self.cmd_analysis(update, None)
                
        except Exception as e:
            logger.error(f"자연어 질문 처리 오류: {e}")
            await update.message.reply_text("분석 중 오류가 발생했습니다.")
    
    async def cmd_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """현재 분석 명령어"""
        try:
            self.command_stats['analysis'] += 1
            await update.message.reply_text("📊 비트코인 분석 중...")
            
            report = await self.report_generator.generate_regular_report()
            await update.message.reply_text(report, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"분석 명령어 오류: {e}")
            self.command_stats['errors'] += 1
            await update.message.reply_text("분석 생성 중 오류가 발생했습니다.")
    
    async def cmd_exception(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """예외 상황 체크 명령어"""
        try:
            self.command_stats['exception'] += 1
            await update.message.reply_text("🚨 예외 상황 확인 중...")
            
            report = await self.report_generator.generate_exception_report()
            await update.message.reply_text(report, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"예외 체크 명령어 오류: {e}")
            self.command_stats['errors'] += 1
            await update.message.reply_text("예외 상황 확인 중 오류가 발생했습니다.")
    
    async def cmd_news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """뉴스 분석 명령어"""
        try:
            self.command_stats['news'] += 1
            await update.message.reply_text("📰 최신 뉴스 분석 중...")
            
            # 뉴스 기반 분석 생성
            news_data = await self.data_collector.get_recent_news(hours=24)
            if news_data:
                report = await self.report_generator.generate_news_analysis_report(news_data)
                await update.message.reply_text(report, parse_mode='HTML')
            else:
                await update.message.reply_text("최근 24시간 내 주요 뉴스가 없습니다.")
                
        except Exception as e:
            logger.error(f"뉴스 명령어 오류: {e}")
            self.command_stats['errors'] += 1
            await update.message.reply_text("뉴스 분석 중 오류가 발생했습니다.")
    
    async def cmd_prediction(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """예측 명령어"""
        try:
            self.command_stats['prediction'] += 1
            await update.message.reply_text("🔮 AI 예측 분석 중...")
            
            if self.ml_mode and self.ml_predictor:
                # ML 기반 예측
                prediction = await self.ml_predictor.generate_prediction()
                await update.message.reply_text(prediction, parse_mode='HTML')
            else:
                # 기본 기술적 분석 기반 예측
                report = await self.report_generator.generate_prediction_report()
                await update.message.reply_text(report, parse_mode='HTML')
                
        except Exception as e:
            logger.error(f"예측 명령어 오류: {e}")
            self.command_stats['errors'] += 1
            await update.message.reply_text("예측 분석 중 오류가 발생했습니다.")
    
    async def cmd_mirror_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """미러 트레이딩 상태 명령어"""
        try:
            self.command_stats['mirror_status'] += 1
            
            if not self.mirror_mode:
                await update.message.reply_text(
                    "⚠️ 미러 트레이딩이 비활성화되어 있습니다.\n"
                    "환경변수를 확인하고 ENABLE_MIRROR_TRADING=true로 설정하세요."
                )
                return
            
            if not self.mirror_trading:
                await update.message.reply_text("❌ 미러 트레이딩 시스템이 초기화되지 않았습니다.")
                return
            
            # 미러 트레이딩 상태 조회
            try:
                await update.message.reply_text("🔄 미러 트레이딩 상태 확인 중...")
                
                # 기본 상태 정보
                status_info = f"""🔥 미러 트레이딩 상태

🎯 <b>시스템 상태:</b> {'🟢 활성화' if self.mirror_trading.monitoring else '🔴 비활성화'}
📊 <b>복제된 포지션:</b> {len(self.mirror_trading.mirrored_positions)}개
📋 <b>복제된 예약주문:</b> {len(self.mirror_trading.position_manager.mirrored_plan_orders)}개
❌ <b>실패 기록:</b> {len(self.mirror_trading.failed_mirrors)}건

📈 <b>오늘 통계:</b>
• 총 미러링: {self.mirror_trading.daily_stats['total_mirrored']}회
• 성공: {self.mirror_trading.daily_stats['successful_mirrors']}회
• 실패: {self.mirror_trading.daily_stats['failed_mirrors']}회
• 예약주문 처리: {self.mirror_trading.daily_stats['plan_order_mirrors']}회"""

                # 현재 시세 차이 정보
                if self.mirror_trading.bitget_current_price > 0 and self.mirror_trading.gate_current_price > 0:
                    price_diff = abs(self.mirror_trading.bitget_current_price - self.mirror_trading.gate_current_price)
                    status_info += f"""

💰 <b>현재 시세:</b>
• 비트겟: ${self.mirror_trading.bitget_current_price:,.2f}
• 게이트: ${self.mirror_trading.gate_current_price:,.2f}
• 차이: ${price_diff:.2f}
• 🔥 처리: 시세 차이와 무관하게 즉시 처리"""

                status_info += f"""

🛡️ <b>보호 시스템:</b>
• 슬리피지 보호: 0.05% (약 $50)
• 중복 방지: 활성화
• 자동 동기화: 15초마다
• 예약주문 체결/취소 구분: 활성화"""
                
                await update.message.reply_text(status_info, parse_mode='HTML')
                
            except Exception as status_error:
                logger.error(f"미러 트레이딩 상태 조회 오류: {status_error}")
                await update.message.reply_text("미러 트레이딩 상태 조회 중 오류가 발생했습니다.")
                
        except Exception as e:
            logger.error(f"미러 상태 명령어 오류: {e}")
            self.command_stats['errors'] += 1
            await update.message.reply_text("미러 트레이딩 상태 확인 중 오류가 발생했습니다.")
    
    async def cmd_system_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시스템 상태 명령어"""
        try:
            uptime = datetime.now() - self.start_time
            uptime_str = str(uptime).split('.')[0]  # 소수점 제거
            
            report = f"""🔧 시스템 상태 리포트

⏰ <b>가동 시간:</b> {uptime_str}
🎯 <b>분석 대상:</b> 비트코인 (BTC/USDT)

🔧 <b>모듈 상태:</b>
• 📊 분석 엔진: {'🟢 정상' if self.analysis_engine else '🔴 오류'}
• 🚨 예외 감지: {'🟢 정상' if self.exception_detector else '🔴 오류'}
• 📰 뉴스 수집: {'🟢 정상' if self.data_collector else '🔴 오류'}
• 💬 텔레그램 봇: {'🟢 정상' if self.telegram_bot else '🔴 오류'}
• 🔥 미러 트레이딩: {'🟢 활성화' if self.mirror_mode else '⚠️ 비활성화'}
• 🤖 AI 예측: {'🟢 활성화' if self.ml_mode else '📊 기본 분석'}

📊 <b>명령어 사용 통계:</b>
- 분석 요청: {self.command_stats['analysis']}회
- 예외 체크: {self.command_stats['exception']}회
- 뉴스 분석: {self.command_stats['news']}회
- 예측 요청: {self.command_stats['prediction']}회
- 미러 상태: {self.command_stats['mirror_status']}회
- 도움말: {self.command_stats['help']}회
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
- 총 거래량: ${mirror_stats['total_volume']:,.2f}"""
            
            report += f"""

<b>🔧 시스템 설정:</b>
- 예외 감지: 5분마다
- 급속 변동: 2분마다
- 뉴스 수집: 15초마다
- 가격 임계값: {self.exception_detector.PRICE_CHANGE_THRESHOLD}%
- 거래량 임계값: {self.exception_detector.VOLUME_SPIKE_THRESHOLD}배

━━━━━━━━━━━━━━━━━━━
⚡ 비트코인 전용 시스템이 완벽히 작동했습니다!"""
            
            await update.message.reply_text(report, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"시스템 상태 명령어 오류: {e}")
            self.command_stats['errors'] += 1
            await update.message.reply_text("시스템 상태 확인 중 오류가 발생했습니다.")
    
    async def _generate_regular_report(self):
        """정기 리포트 생성"""
        try:
            logger.info("정기 리포트 생성 중...")
            report = await self.report_generator.generate_regular_report()
            await self.telegram_bot.send_message(report, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"정기 리포트 생성 오류: {e}")
    
    async def _generate_daily_performance_report(self):
        """일일 성과 리포트 생성"""
        try:
            logger.info("일일 성과 리포트 생성 중...")
            
            # 기본 성과 리포트
            performance_report = await self.report_generator.generate_performance_report()
            await self.telegram_bot.send_message(performance_report, parse_mode='HTML')
            
            # 미러 트레이딩 리포트 (활성화된 경우)
            if self.mirror_mode and self.mirror_trading:
                mirror_report = await self.mirror_trading._create_daily_report()
                await self.telegram_bot.send_message(f"🔥 미러 트레이딩 일일 리포트\n\n{mirror_report}", parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"일일 성과 리포트 생성 오류: {e}")
    
    async def _system_health_check(self):
        """시스템 상태 체크"""
        try:
            # 기본 상태 체크
            components_status = {
                'data_collector': self.data_collector is not None,
                'analysis_engine': self.analysis_engine is not None,
                'exception_detector': self.exception_detector is not None,
                'telegram_bot': self.telegram_bot is not None
            }
            
            # 미러 트레이딩 상태 체크
            if self.mirror_mode and self.mirror_trading:
                components_status['mirror_trading'] = self.mirror_trading.monitoring
            
            failed_components = [name for name, status in components_status.items() if not status]
            
            if failed_components:
                await self.telegram_bot.send_message(
                    f"⚠️ 시스템 구성요소 문제 감지\n실패: {', '.join(failed_components)}"
                )
                
        except Exception as e:
            logger.error(f"시스템 상태 체크 오류: {e}")
    
    async def stop(self):
        """봇 중지"""
        try:
            self.running = False
            logger.info("🛑 비트코인 분석 봇 중지 중...")
            
            # 미러 트레이딩 중지
            if self.mirror_mode and self.mirror_trading:
                await self.mirror_trading.stop()
                logger.info("🔥 미러 트레이딩 시스템 중지됨")
            
            # 스케줄러 중지
            if self.scheduler.running:
                self.scheduler.shutdown()
                
            # 텔레그램 봇 중지
            await self.telegram_bot.stop()
            
            # 클라이언트들 정리
            if hasattr(self.bitget_client, 'close'):
                await self.bitget_client.close()
                
            if self.gate_client and hasattr(self.gate_client, 'close'):
                await self.gate_client.close()
            
            await self.telegram_bot.send_message("🛑 비트코인 분석 봇이 안전하게 종료되었습니다.")
            logger.info("✅ 모든 구성요소가 안전하게 종료됨")
            
        except Exception as e:
            logger.error(f"봇 중지 오류: {e}")

def signal_handler(signum, frame):
    """시그널 핸들러"""
    logger.info(f"신호 수신: {signum}")
    sys.exit(0)

async def main():
    """메인 함수"""
    try:
        # 시그널 핸들러 설정
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 봇 인스턴스 생성 및 시작
        bot = BitcoinAnalysisBot()
        
        try:
            await bot.start()
        except KeyboardInterrupt:
            logger.info("키보드 인터럽트 감지")
        except Exception as e:
            logger.error(f"봇 실행 중 오류: {e}")
        finally:
            await bot.stop()
            
    except Exception as e:
        logger.error(f"메인 함수 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("프로그램이 사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"프로그램 실행 오류: {e}")
        sys.exit(1)
