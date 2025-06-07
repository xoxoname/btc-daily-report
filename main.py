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

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bitcoin_system.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# 컬러 로깅 설정
try:
    import coloredlogs
    coloredlogs.install(
        level='INFO',
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
except ImportError:
    pass

class BitcoinPredictionSystem:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 50)
        self.logger.info("비트코인 예측 시스템 초기화 시작")
        self.logger.info("=" * 50)
        
        # 설정 로드
        try:
            self.config = Config()
        except Exception as e:
            self.logger.error(f"설정 로드 실패: {e}")
            raise
        
        # 🔥🔥🔥 미러 트레이딩 모드 확인 - 강화된 버전
        self.mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'false').lower() == 'true'
        self.logger.info(f"환경변수 MIRROR_TRADING_MODE: {os.getenv('MIRROR_TRADING_MODE', 'not_set')}")
        self.logger.info(f"미러 트레이딩 모드: {'활성화' if self.mirror_mode else '비활성화'}")
        self.logger.info(f"미러 트레이딩 모듈 가용성: {'사용 가능' if MIRROR_TRADING_AVAILABLE else '사용 불가'}")
        
        # 🔥🔥🔥 환경변수 키 이름 유지 - 사용자 요청사항
        required_env_vars = [
            'ALPHA_VANTAGE_KEY',
            'BITGET_APIKEY', 
            'BITGET_APISECRET',
            'BITGET_PASSPHRASE',
            'COINGECKO_API_KEY',
            'CRYPTOCOMPARE_API_KEY',
            'ENABLE_MIRROR_TRADING',
            'GATE_API_KEY',
            'GATE_API_SECRET', 
            'MIRROR_CHECK_INTERVAL',
            'MIRROR_TRADING_MODE',
            'NEWSAPI_KEY',
            'SDATA_KEY',
            'OPENAI_API_KEY',
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHAT_ID'
        ]
        
        # Gate.io API 키 확인
        gate_api_key = os.getenv('GATE_API_KEY', '')
        gate_api_secret = os.getenv('GATE_API_SECRET', '')
        self.logger.info(f"Gate.io API 키 설정 상태: {'설정됨' if gate_api_key and gate_api_secret else '미설정'}")
        
        # ML 예측기 모드 확인
        self.ml_mode = ML_PREDICTOR_AVAILABLE
        self.logger.info(f"ML 예측기 모드: {'활성화' if self.ml_mode else '비활성화'}")
        
        # ML 예측기 초기화
        self.ml_predictor = None
        if self.ml_mode:
            try:
                self.ml_predictor = MLPredictor()
                self.logger.info(f"✅ ML 예측기 초기화 완료")
            except Exception as e:
                self.logger.error(f"ML 예측기 초기화 실패: {e}")
                self.ml_mode = False
        
        # 시스템 상태 관리
        self.is_running = False
        self.startup_time = datetime.now()
        self.command_stats = {
            'report': 0,
            'forecast': 0,
            'profit': 0,
            'schedule': 0,
            'mirror': 0,
            'natural_language': 0,
            'errors': 0
        }
        
        # 예외 감지 통계
        self.exception_stats = {
            'total_detected': 0,
            'news_alerts': 0,
            'price_alerts': 0,
            'volume_alerts': 0,
            'funding_alerts': 0,
            'short_term_alerts': 0,
            'last_reset': datetime.now().isoformat()
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
        
        self.logger.info(f"시스템 초기화 완료 (미러: {'활성' if self.mirror_mode else '비활성'}, ML: {'활성' if self.ml_mode else '비활성'})")
    
    def _initialize_clients(self):
        """클라이언트 초기화 - 강화된 미러 트레이딩 지원"""
        try:
            # Bitget 클라이언트
            self.bitget_client = BitgetClient(self.config)
            self.logger.info("✅ Bitget 클라이언트 초기화 완료")
            
            # Telegram 봇
            self.telegram_bot = TelegramBot(self.config)
            self.logger.info("✅ Telegram 봇 초기화 완료")
            
            # Gate.io 클라이언트 (미러 모드일 때만) - 강화된 로직
            self.gate_client = None
            self.mirror_trading = None
            
            # 🔥🔥🔥 미러 트레이딩 활성화 조건 체크 강화
            if self.mirror_mode:
                self.logger.info("🔄 미러 트레이딩 모드가 활성화됨, Gate.io 클라이언트 초기화 시작...")
                
                if not MIRROR_TRADING_AVAILABLE:
                    self.logger.error("❌ 미러 트레이딩 모듈을 찾을 수 없음")
                    self.mirror_mode = False
                    return
                
                # Gate.io API 키 확인
                gate_api_key = os.getenv('GATE_API_KEY', '')
                gate_api_secret = os.getenv('GATE_API_SECRET', '')
                
                if not gate_api_key or not gate_api_secret:
                    self.logger.error("❌ Gate.io API 키가 설정되지 않음")
                    self.logger.error("GATE_API_KEY와 GATE_API_SECRET 환경변수를 설정해주세요")
                    self.mirror_mode = False
                    return
                
                try:
                    self.logger.info("🔄 Gate.io 클라이언트 생성 중...")
                    self.gate_client = GateClient(self.config)
                    self.logger.info("✅ Gate.io 클라이언트 생성 완료")
                    
                    # 🔥🔥🔥 미러 트레이딩 유틸리티 초기화
                    self.logger.info("🔄 미러 트레이딩 유틸리티 초기화 중...")
                    self.mirror_utils = MirrorTradingUtils(self.config, self.bitget_client, self.gate_client)
                    
                    self.logger.info("🔄 미러 트레이딩 시스템 생성 중...")
                    self.mirror_trading = MirrorTradingSystem(
                        self.config,
                        self.bitget_client,
                        self.gate_client,
                        self.bitget_client,  # bitget_mirror
                        self.gate_client,    # gate_mirror
                        self.telegram_bot,
                        self.mirror_utils
                    )
                    self.logger.info("✅ Gate.io 클라이언트 및 미러 트레이딩 초기화 완료")
                    
                except Exception as e:
                    self.logger.error(f"❌ Gate.io 클라이언트 초기화 실패: {e}")
                    self.logger.error(traceback.format_exc())
                    self.mirror_mode = False
            else:
                # 🔥🔥🔥 분석 전용 모드에서도 Gate.io 클라이언트 초기화 시도 (수익 조회용)
                gate_api_key = os.getenv('GATE_API_KEY', '')
                gate_api_secret = os.getenv('GATE_API_SECRET', '')
                
                if gate_api_key and gate_api_secret:
                    try:
                        self.logger.info("📊 분석용 Gate.io 클라이언트 초기화 중...")
                        self.gate_client = GateClient(self.config)
                        self.logger.info("✅ 분석용 Gate.io 클라이언트 초기화 완료")
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
            
            # 예외 감지기
            self.exception_detector = ExceptionDetector(
                self.config, 
                self.data_collector, 
                self.indicator_system, 
                self.telegram_bot
            )
            self.logger.info("✅ 예외 감지기 초기화 완료")
            
            # 리포트 생성기 매니저
            self.report_manager = ReportGeneratorManager(
                self.config, 
                self.data_collector, 
                self.indicator_system, 
                self.bitget_client
            )
            
            # Gate.io 클라이언트가 있으면 리포트 매니저에 설정
            if self.gate_client:
                self.report_manager.set_gateio_client(self.gate_client)
            
            self.logger.info("✅ 리포트 생성기 매니저 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"컴포넌트 초기화 실패: {e}")
            raise

    def _setup_scheduler(self):
        """스케줄러 설정 - 미러 트레이딩 강화 반영"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            
            # 정기 리포트 (1일 4회)
            self.scheduler.add_job(
                self.handle_report_command,
                'cron',
                hour='9,13,17,22',
                minute=0,
                timezone=kst,
                id='regular_report'
            )
            
            # 예측 리포트 (1일 2회)
            self.scheduler.add_job(
                self.handle_forecast_command,
                'cron',
                hour='6,18',
                minute=30,
                timezone=kst,
                id='forecast_report'
            )
            
            # 예외 감지 (5분마다)
            self.scheduler.add_job(
                self.exception_detector.check_exceptions,
                'interval',
                minutes=5,
                id='exception_check'
            )
            
            # 급속 변동 감지 (2분마다)
            self.scheduler.add_job(
                self.exception_detector.check_rapid_changes,
                'interval',
                minutes=2,
                id='rapid_change_check'
            )
            
            # 일일 통계 리포트 (오전 9시)
            self.scheduler.add_job(
                self.send_daily_stats_report,
                'cron',
                hour=9,
                minute=5,
                timezone=kst,
                id='daily_stats'
            )
            
            # 🔥🔥🔥 미러 트레이딩 관련 스케줄 강화
            if self.mirror_mode and self.mirror_trading:
                # 미러 트레이딩 일일 리포트 (오전 9시 10분)
                self.scheduler.add_job(
                    self._send_mirror_daily_report,
                    'cron',
                    hour=9,
                    minute=10,
                    timezone=kst,
                    id='mirror_daily_report'
                )
                
                # 🔥🔥🔥 미러 트레이딩 시세 현황 (6시간마다) - 강화
                self.scheduler.add_job(
                    self._send_mirror_price_status,
                    'cron',
                    hour='0,6,12,18',
                    minute=15,
                    timezone=kst,
                    id='mirror_price_status'
                )
            
            self.logger.info("✅ 스케줄러 설정 완료")
            
        except Exception as e:
            self.logger.error(f"스케줄러 설정 실패: {e}")
            raise

    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        self.logger.info(f"시그널 {signum} 수신, 정상 종료 시작...")
        asyncio.create_task(self.stop())

    async def handle_natural_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """자연어 메시지 처리 - 미러 트레이딩 명령 추가"""
        try:
            if not update.message or not update.message.text:
                return
            
            message = update.message.text.lower().strip()
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            
            self.logger.info(f"자연어 처리 - User: {username}({user_id}), 메시지: {message}")
            self.command_stats['natural_language'] += 1
            
            # 미러 트레이딩 관련 키워드 강화
            mirror_keywords = [
                '미러', 'mirror', '트레이딩', 'trading', '복제', '동기화', 'sync',
                '게이트', 'gate', '비트겟', 'bitget', '포지션', 'position', 
                '예약', 'plan', '주문', 'order', '클로즈', 'close'
            ]
            
            # 수익 관련 키워드
            profit_keywords = ['수익', '손익', '현황', 'profit', 'pnl', '잔고', 'balance']
            
            # 예측 관련 키워드
            forecast_keywords = ['예측', '전망', 'forecast', '분석', 'analysis', '시장', 'market']
            
            # 상태 관련 키워드
            status_keywords = ['상태', 'status', '통계', 'stats', '현재', 'current']
            
            # 리포트 관련 키워드
            report_keywords = ['리포트', 'report', '보고서', '종합', '전체']
            
            # 일정 관련 키워드  
            schedule_keywords = ['일정', 'schedule', '스케줄', '언제', 'when', '시간', 'time']
            
            # 키워드 매칭 및 명령 실행
            if any(keyword in message for keyword in mirror_keywords) and self.mirror_mode:
                await self.handle_mirror_status(update, context)
            elif any(keyword in message for keyword in profit_keywords):
                await self.handle_profit_command(update, context)
            elif any(keyword in message for keyword in forecast_keywords):
                await self.handle_forecast_command(update, context)
            elif any(keyword in message for keyword in status_keywords):
                await self.handle_stats_command(update, context)
            elif any(keyword in message for keyword in report_keywords):
                await self.handle_report_command(update, context)
            elif any(keyword in message for keyword in schedule_keywords):
                await self.handle_schedule_command(update, context)
            else:
                # 일반적인 인사말이나 기타 메시지
                greetings = ['안녕', 'hello', 'hi', '안녕하세요', '좋은', '감사']
                if any(greeting in message for greeting in greetings):
                    mode_text = "미러 트레이딩" if self.mirror_mode else "분석 전용"
                    await update.message.reply_text(
                        f"안녕하세요! 비트코인 예측 시스템입니다. 🚀\n"
                        f"현재 모드: {mode_text}\n\n"
                        f"명령어를 입력하거나 자연어로 질문해주세요!\n"
                        f"예: '수익은?', '시장 상황 어때?', '다음 리포트 언제?'"
                    )
                else:
                    await update.message.reply_text(
                        "🤔 죄송합니다. 이해하지 못했습니다.\n\n"
                        "다음과 같이 질문해보세요:\n"
                        "• '오늘 수익은?'\n"
                        "• '시장 상황 어때?'\n"
                        "• '예측 보여줘'\n"
                        "• '시스템 통계는?'"
                        + ("\n• '미러 트레이딩 상태는?'" if self.mirror_mode else "")
                    )
        
        except Exception as e:
            self.command_stats['errors'] += 1
            self.logger.error(f"자연어 처리 실패: {e}")
            await update.message.reply_text("❌ 메시지 처리 중 오류가 발생했습니다.")

    async def handle_mirror_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔥🔥🔥 미러 트레이딩 상태 조회 - 강화된 정보 제공"""
        try:
            self.command_stats['mirror'] += 1
            
            if not self.mirror_mode:
                # 미러 모드가 비활성화된 경우
                gate_api_key = os.getenv('GATE_API_KEY', '')
                gate_api_secret = os.getenv('GATE_API_SECRET', '')
                
                status_text = f"""<b>🔄 미러 트레이딩 상태</b>

<b>❌ 현재 상태:</b> 비활성화

<b>🔧 활성화 방법:</b>
1. MIRROR_TRADING_MODE=true 환경변수 설정 ✓\n"""
                status_text += f"2. GATE_API_KEY 환경변수 설정 {'✓' if gate_api_key else '❌'}\n"
                status_text += f"3. GATE_API_SECRET 환경변수 설정 {'✓' if gate_api_secret else '❌'}\n"
                status_text += f"4. 시스템 재시작\n\n"
                status_text += f"🔧 현재 환경변수 상태:\n"
                status_text += f"• MIRROR_TRADING_MODE: {os.getenv('MIRROR_TRADING_MODE', 'not_set')}\n"
                status_text += f"• 미러 트레이딩 모듈: {'사용 가능' if MIRROR_TRADING_AVAILABLE else '사용 불가'}"
                
                # Gate.io 분석용 클라이언트 상태 추가
                if self.gate_client:
                    status_text += f"\n\n✅ Gate.io 분석용 클라이언트는 정상 작동 중"
                    status_text += f"\n💰 수익 조회 기능 사용 가능"
                
                await update.message.reply_text(status_text, parse_mode='HTML')
                return
            
            await update.message.reply_text("🔄 미러 트레이딩 상태를 조회중입니다...", parse_mode='HTML')
            
            # 미러링 상태 정보
            active_mirrors = len(self.mirror_trading.mirrored_positions)
            failed_count = len(self.mirror_trading.failed_mirrors)
            
            # 계정 정보
            bitget_account = await self.bitget_client.get_account_info()
            gate_account = await self.gate_client.get_account_balance()
            
            bitget_equity = float(bitget_account.get('accountEquity', 0))
            gate_equity = float(gate_account.get('total', 0))
            
            # 포지션 정보
            bitget_positions = await self.bitget_client.get_positions(self.config.symbol)
            gate_positions = await self.gate_client.get_positions("BTC_USDT")
            
            bitget_pos_count = sum(1 for pos in bitget_positions if float(pos.get('total', 0)) > 0)
            gate_pos_count = sum(1 for pos in gate_positions if pos.get('size', 0) != 0)
            
            # 성공률 계산
            success_rate = 0
            if self.mirror_trading.daily_stats['total_mirrored'] > 0:
                success_rate = (self.mirror_trading.daily_stats['successful_mirrors'] / 
                              self.mirror_trading.daily_stats['total_mirrored']) * 100
            
            # 🔥🔥🔥 강화된 상태 메시지
            status_msg = f"""🔄 <b>미러 트레이딩 상태</b>

<b>💰 계정 잔고:</b>
- 비트겟: ${bitget_equity:,.2f}
- 게이트: ${gate_equity:,.2f}
- 잔고 비율: {(gate_equity/bitget_equity*100):.1f}%

<b>📊 포지션 현황:</b>
- 비트겟: {bitget_pos_count}개
- 게이트: {gate_pos_count}개
- 활성 미러: {active_mirrors}개

<b>📈 오늘 통계 (강화):</b>
- 시도: {self.mirror_trading.daily_stats['total_mirrored']}회
- 성공: {self.mirror_trading.daily_stats['successful_mirrors']}회
- 실패: {self.mirror_trading.daily_stats['failed_mirrors']}회
- 성공률: {success_rate:.1f}%
- 예약 주문 미러링: {self.mirror_trading.daily_stats['plan_order_mirrors']}회
- 예약 주문 취소: {self.mirror_trading.daily_stats['plan_order_cancels']}회
- 클로즈 주문: {self.mirror_trading.daily_stats['close_order_mirrors']}회
- 강제 동기화: {self.mirror_trading.daily_stats.get('force_sync_count', 0)}회
- 부분청산: {self.mirror_trading.daily_stats['partial_closes']}회
- 전체청산: {self.mirror_trading.daily_stats['full_closes']}회
- 총 거래량: ${self.mirror_trading.daily_stats['total_volume']:,.2f}

<b>💰 달러 비율 복제:</b>
- 총 자산 대비 동일 비율 유지
- 예약 주문도 동일 비율 복제
- 실시간 가격 조정

<b>🔥 강화된 기능:</b>
- 예약 주문 체크: 5초마다
- 강제 동기화: 15초마다 (강화)
- 스타트업 제외: 10분으로 단축
- 클로즈 주문 즉시 감지
- 포지션 없음 시 자동 정리

<b>⚠️ 최근 오류:</b>
- 실패 기록: {failed_count}건"""
            
            # 최근 실패 내역 추가
            if failed_count > 0 and self.mirror_trading.failed_mirrors:
                recent_fail = self.mirror_trading.failed_mirrors[-1]
                status_msg += f"\n• 마지막 실패: {recent_fail.error[:50]}..."
            
            status_msg += "\n\n✅ 시스템 정상 작동 중"
            
            # 시스템 가동 시간
            uptime = datetime.now() - self.startup_time
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            status_msg += f"\n⏱️ 가동 시간: {hours}시간 {minutes}분"
            
            await update.message.reply_text(status_msg, parse_mode='HTML')
            
        except Exception as e:
            self.command_stats['errors'] += 1
            self.logger.error(f"미러 상태 조회 실패: {str(e)}")
            self.logger.debug(traceback.format_exc())
            await update.message.reply_text(
                f"❌ 미러 트레이딩 상태 조회 중 오류가 발생했습니다.\n"
                f"오류: {str(e)[:100]}",
                parse_mode='HTML'
            )

    async def handle_report_command(self, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None):
        """종합 분석 리포트 생성"""
        try:
            self.command_stats['report'] += 1
            
            if update:
                await update.message.reply_text("📊 종합 분석 리포트를 생성중입니다...", parse_mode='HTML')
            
            # 리포트 생성
            report = await self.report_manager.generate_regular_report()
            
            # 메시지 분할 및 전송
            if update:
                await self._send_split_message(update.message.reply_text, report)
            else:
                await self._send_split_message(self.telegram_bot.send_message, report)
            
        except Exception as e:
            self.command_stats['errors'] += 1
            self.logger.error(f"리포트 생성 실패: {e}")
            error_msg = f"❌ 리포트 생성 중 오류가 발생했습니다.\n오류: {str(e)[:100]}"
            
            if update:
                await update.message.reply_text(error_msg, parse_mode='HTML')
            else:
                await self.telegram_bot.send_message(error_msg)

    async def handle_forecast_command(self, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None):
        """단기 예측 리포트 생성"""
        try:
            self.command_stats['forecast'] += 1
            
            if update:
                await update.message.reply_text("🔮 단기 예측 리포트를 생성중입니다...", parse_mode='HTML')
            
            # 예측 리포트 생성
            forecast = await self.report_manager.generate_forecast_report()
            
            # ML 예측 추가 (가능한 경우)
            if self.ml_mode and self.ml_predictor:
                try:
                    ml_prediction = await self.ml_predictor.get_prediction()
                    forecast += f"\n\n{ml_prediction}"
                except Exception as e:
                    self.logger.error(f"ML 예측 추가 실패: {e}")
            
            # 메시지 분할 및 전송
            if update:
                await self._send_split_message(update.message.reply_text, forecast)
            else:
                await self._send_split_message(self.telegram_bot.send_message, forecast)
            
        except Exception as e:
            self.command_stats['errors'] += 1
            self.logger.error(f"예측 리포트 생성 실패: {e}")
            error_msg = f"❌ 예측 리포트 생성 중 오류가 발생했습니다.\n오류: {str(e)[:100]}"
            
            if update:
                await update.message.reply_text(error_msg, parse_mode='HTML')
            else:
                await self.telegram_bot.send_message(error_msg)

    async def handle_profit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """실시간 수익 현황 조회"""
        try:
            self.command_stats['profit'] += 1
            
            await update.message.reply_text("💰 실시간 수익 현황을 조회중입니다...", parse_mode='HTML')
            
            # 수익 리포트 생성
            profit_report = await self.report_manager.generate_profit_report()
            
            # 메시지 분할 및 전송
            await self._send_split_message(update.message.reply_text, profit_report)
            
        except Exception as e:
            self.command_stats['errors'] += 1
            self.logger.error(f"수익 현황 조회 실패: {e}")
            await update.message.reply_text(
                f"❌ 수익 현황 조회 중 오류가 발생했습니다.\n오류: {str(e)[:100]}",
                parse_mode='HTML'
            )

    async def handle_schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """자동 일정 안내"""
        try:
            self.command_stats['schedule'] += 1
            
            # 일정 리포트 생성
            schedule_report = await self.report_manager.generate_schedule_report()
            
            await update.message.reply_text(schedule_report, parse_mode='HTML')
            
        except Exception as e:
            self.command_stats['errors'] += 1
            self.logger.error(f"일정 안내 실패: {e}")
            await update.message.reply_text(
                f"❌ 일정 안내 생성 중 오류가 발생했습니다.\n오류: {str(e)[:100]}",
                parse_mode='HTML'
            )

    async def handle_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시스템 통계 조회"""
        try:
            # 업타임 계산
            uptime = datetime.now() - self.startup_time
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            
            total_exceptions = self.exception_stats['total_detected']
            
            report = f"""<b>📊 시스템 통계</b>

<b>⏱️ 시스템 가동 시간:</b> {hours}시간 {minutes}분

<b>📈 명령 사용 통계:</b>
- 리포트 생성: {self.command_stats['report']}회
- 예측 요청: {self.command_stats['forecast']}회
- 수익 조회: {self.command_stats['profit']}회
- 일정 확인: {self.command_stats['schedule']}회"""
            
            if self.mirror_mode:
                report += f"\n- 미러 상태 조회: {self.command_stats['mirror']}회"
            
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
            
            await update.message.reply_text(report, parse_mode='HTML')
            
        except Exception as e:
            self.command_stats['errors'] += 1
            self.logger.error(f"통계 조회 실패: {e}")
            await update.message.reply_text(
                f"❌ 시스템 통계 조회 중 오류가 발생했습니다.\n오류: {str(e)[:100]}",
                parse_mode='HTML'
            )

    async def send_daily_stats_report(self):
        """일일 통계 리포트 전송"""
        try:
            uptime = datetime.now() - self.startup_time
            hours = int(uptime.total_seconds() // 3600)
            total_commands = sum(self.command_stats.values())
            total_exceptions = self.exception_stats['total_detected']
            
            report = f"""<b>📊 일일 시스템 통계</b>

<b>⏱️ 총 가동 시간:</b> {hours}시간
<b>📱 총 명령 처리:</b> {total_commands}건
<b>🚨 예외 감지:</b> {total_exceptions}건

<b>📈 명령 분석:</b>
- 리포트: {self.command_stats['report']}회
- 예측: {self.command_stats['forecast']}회
- 수익: {self.command_stats['profit']}회
- 자연어: {self.command_stats['natural_language']}회
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
            
            # 🔥🔥🔥 미러 트레이딩 통계 추가
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
            
            await self.telegram_bot.send_message(report, parse_mode='HTML')
            
            # 통계 초기화
            self.command_stats = {k: 0 if k != 'errors' else v for k, v in self.command_stats.items()}
            
            # 예외 통계 초기화
            self.exception_stats = {
                'total_detected': 0,
                'news_alerts': 0,
                'price_alerts': 0,
                'volume_alerts': 0,
                'funding_alerts': 0,
                'short_term_alerts': 0,
                'last_reset': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"일일 통계 리포트 생성 실패: {e}")

    async def _send_mirror_daily_report(self):
        """🔥🔥🔥 미러 트레이딩 일일 리포트 전송"""
        try:
            if not self.mirror_mode or not self.mirror_trading:
                return
            
            daily_report = await self.mirror_trading.get_daily_report()
            await self.telegram_bot.send_message(daily_report, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 일일 리포트 전송 실패: {e}")

    async def _send_mirror_price_status(self):
        """🔥🔥🔥 미러 트레이딩 시세 현황 전송"""
        try:
            if not self.mirror_mode or not self.mirror_trading:
                return
            
            await self.mirror_trading._send_price_status_report()
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시세 현황 전송 실패: {e}")

    def _split_message(self, message: str, max_length: int = 4000) -> List[str]:
        """긴 메시지 분할"""
        if len(message) <= max_length:
            return [message]
        
        parts = []
        lines = message.split('\n')
        current_part = ""
        
        for line in lines:
            if len(current_part) + len(line) + 1 > max_length:
                if current_part:
                    parts.append(current_part.strip())
                current_part = line + '\n'
            else:
                current_part += line + '\n'
        
        if current_part:
            parts.append(current_part.strip())
        
        return parts

    async def _send_split_message(self, send_func, message: str):
        """메시지 분할 및 전송"""
        parts = self._split_message(message)
        
        for i, part in enumerate(parts):
            if i > 0:
                await asyncio.sleep(1)  # 메시지 간 간격
            await send_func(part, parse_mode='HTML')

    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시작 명령 처리 - 간소화된 도움말"""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            self.logger.info(f"시작 명령 - User: {username}({user_id})")
            
            mode_text = "🔄 미러 트레이딩 모드" if self.mirror_mode else "📊 분석 전용 모드"
            if self.ml_mode:
                mode_text += " + 🤖 ML 예측"
            
            welcome_message = f"""<b>🚀 비트코인 예측 시스템에 오신 것을 환영합니다!</b>

현재 모드: {mode_text}

<b>📊 주요 명령어:</b>
- /report - 전체 분석 리포트
- /forecast - 단기 예측 요약
- /profit - 실시간 수익 현황
- /schedule - 자동 일정 안내
- /stats - 시스템 통계"""
            
            if self.mirror_mode:
                welcome_message += "\n• /mirror - 미러 트레이딩 상태"
            
            welcome_message += """

<b>💬 자연어 질문 예시:</b>
- "오늘 수익은?"
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
                self.logger.info("🔄 미러 트레이딩 시스템 시작 중... (강화된 동기화)")
                asyncio.create_task(self.mirror_trading.start())
            
            # 스케줄러 시작
            self.logger.info("스케줄러 시작 중...")
            self.scheduler.start()
            
            # 텔레그램 봇 핸들러 등록
            self.logger.info("텔레그램 봇 핸들러 등록 중...")
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
            self.logger.info("텔레그램 봇 시작 중...")
            await self.telegram_bot.start()
            
            mode_text = "미러 트레이딩" if self.mirror_mode else "분석 전용"
            if self.ml_mode:
                mode_text += " + ML 예측"
            
            self.logger.info(f"✅ 비트코인 예측 시스템 시작 완료 (모드: {mode_text})")
            
            # 🔥🔥🔥 시작 메시지 전송 - 강화된 정보
            startup_msg = f"""🚀 <b>비트코인 예측 시스템 시작</b>

<b>🔧 현재 모드:</b> {mode_text}
<b>📅 시작 시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<b>⚡ 활성화된 기능:</b>
• 실시간 가격 모니터링
• 기술적 분석 및 예측
• 예외 상황 자동 감지 (5분마다)
• 급속 변동 감지 (2분마다)
• 정기 리포트 (1일 4회)
• 예측 리포트 (1일 2회)"""

            if self.mirror_mode:
                startup_msg += f"""
• 🔄 미러 트레이딩 (강화됨)
• 📊 예약 주문 동기화 (5초마다)
• 🔥 강제 동기화 (15초마다)
• 🎯 클로즈 주문 즉시 감지
• 🗑️ 고아 주문 자동 정리"""

            if self.ml_mode:
                startup_msg += f"""
• 🤖 AI 기반 예측"""

            startup_msg += f"""

<b>📱 명령어:</b>
/report - 종합 분석
/forecast - 단기 예측
/profit - 수익 현황
/schedule - 자동 일정"""

            if self.mirror_mode:
                startup_msg += f"""
/mirror - 미러 트레이딩 상태"""

            startup_msg += f"""

시스템이 정상적으로 시작되었습니다! 🎯"""
            
            await self.telegram_bot.send_message(startup_msg, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"시스템 시작 실패: {e}")
            self.logger.error(traceback.format_exc())
            
            # 실패 시 텔레그램 알림 시도
            try:
                await self.telegram_bot.send_message(
                    f"❌ 시스템 시작 실패\n\n"
                    f"오류: {str(e)[:200]}\n\n"
                    f"시스템을 재시작해주세요.",
                    parse_mode='HTML'
                )
            except:
                pass
            
            raise
    
    async def stop(self):
        """시스템 종료"""
        try:
            self.logger.info("=" * 50)
            self.logger.info("시스템 종료 프로세스 시작")
            self.logger.info("=" * 50)
            
            self.is_running = False
            
            # 종료 메시지 전송 시도
            try:
                uptime = datetime.now() - self.startup_time
                hours = int(uptime.total_seconds() // 3600)
                minutes = int((uptime.total_seconds() % 3600) // 60)
                
                total_exceptions = self.exception_stats['total_detected']
                
                shutdown_msg = f"""<b>🛑 시스템 종료 중...</b>

<b>⏱️ 총 가동 시간:</b> {hours}시간 {minutes}분
<b>📊 처리된 명령:</b> {sum(self.command_stats.values())}건
<b>🚨 감지된 예외:</b> {total_exceptions}건
<b>❌ 발생한 오류:</b> {self.command_stats['errors']}건"""
                
                if self.ml_mode and self.ml_predictor:
                    stats = self.ml_predictor.get_stats()
                    shutdown_msg += f"""
<b>🤖 ML 예측 성능:</b>
- 총 예측: {stats['total_predictions']}건
- 정확도: {stats['direction_accuracy']}"""
                
                if self.mirror_mode and self.mirror_trading:
                    mirror_stats = self.mirror_trading.daily_stats
                    shutdown_msg += f"""
<b>🔄 미러 트레이딩 성과:</b>
- 총 시도: {mirror_stats['total_mirrored']}회
- 성공: {mirror_stats['successful_mirrors']}회
- 성공률: {(mirror_stats['successful_mirrors'] / max(mirror_stats['total_mirrored'], 1) * 100):.1f}%"""
                
                shutdown_msg += "\n\n비트코인 전용 시스템이 안전하게 종료됩니다."
                
                await self.telegram_bot.send_message(shutdown_msg, parse_mode='HTML')
                
            except Exception as e:
                self.logger.error(f"종료 메시지 전송 실패: {e}")
            
            # 🔥🔥🔥 미러 트레이딩 중지
            if self.mirror_mode and self.mirror_trading:
                self.logger.info("미러 트레이딩 시스템 중지 중...")
                try:
                    await self.mirror_trading.stop()
                    self.logger.info("✅ 미러 트레이딩 시스템 중지 완료")
                except Exception as e:
                    self.logger.error(f"미러 트레이딩 중지 실패: {e}")
            
            # 스케줄러 중지
            if self.scheduler.running:
                self.logger.info("스케줄러 중지 중...")
                self.scheduler.shutdown(wait=False)
                self.logger.info("✅ 스케줄러 중지 완료")
            
            # 데이터 수집기 중지
            try:
                await self.data_collector.stop()
                self.logger.info("✅ 데이터 수집기 중지 완료")
            except Exception as e:
                self.logger.error(f"데이터 수집기 중지 실패: {e}")
            
            # 텔레그램 봇 중지
            try:
                await self.telegram_bot.stop()
                self.logger.info("✅ 텔레그램 봇 중지 완료")
            except Exception as e:
                self.logger.error(f"텔레그램 봇 중지 실패: {e}")
            
            # 클라이언트 정리
            try:
                await self.bitget_client.close()
                self.logger.info("✅ Bitget 클라이언트 정리 완료")
            except Exception as e:
                self.logger.error(f"Bitget 클라이언트 정리 실패: {e}")
            
            if self.gate_client:
                try:
                    await self.gate_client.close()
                    self.logger.info("✅ Gate.io 클라이언트 정리 완료")
                except Exception as e:
                    self.logger.error(f"Gate.io 클라이언트 정리 실패: {e}")
            
            self.logger.info("=" * 50)
            self.logger.info("시스템 종료 완료")
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"시스템 종료 중 오류: {e}")
            self.logger.error(traceback.format_exc())

    async def run(self):
        """시스템 실행"""
        try:
            await self.start()
            
            # 시스템 실행 유지
            while self.is_running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("키보드 인터럽트 감지, 시스템 종료 중...")
        except Exception as e:
            self.logger.error(f"시스템 실행 중 오류: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            await self.stop()

async def main():
    """메인 함수"""
    system = None
    try:
        system = BitcoinPredictionSystem()
        await system.run()
        
    except KeyboardInterrupt:
        print("\n키보드 인터럽트로 종료됩니다.")
    except Exception as e:
        print(f"시스템 실행 중 치명적 오류: {e}")
        traceback.print_exc()
    finally:
        if system:
            try:
                await system.stop()
            except:
                pass

if __name__ == "__main__":
    # 시스템 정보 출력
    print("=" * 60)
    print("🚀 비트코인 선물 예측 시스템 v2.0")
    print("=" * 60)
    print(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐍 Python 버전: {sys.version}")
    print(f"💻 플랫폼: {sys.platform}")
    
    # 환경변수 상태 체크
    required_vars = ['TELEGRAM_BOT_TOKEN', 'BITGET_APIKEY', 'BITGET_APISECRET', 'BITGET_PASSPHRASE']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"\n❌ 필수 환경변수 누락: {', '.join(missing_vars)}")
        print("환경변수를 설정한 후 다시 실행해주세요.")
        sys.exit(1)
    
    # 미러 트레이딩 모드 체크
    mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'false').lower() == 'true'
    if mirror_mode:
        gate_vars = ['GATE_API_KEY', 'GATE_API_SECRET']
        missing_gate_vars = [var for var in gate_vars if not os.getenv(var)]
        if missing_gate_vars:
            print(f"\n⚠️ 미러 트레이딩 모드이지만 Gate.io API 키 누락: {', '.join(missing_gate_vars)}")
            print("분석 전용 모드로 실행됩니다.")
    
    print("\n✅ 환경변수 검증 완료")
    print("🚀 시스템 시작 중...")
    print("=" * 60)
    
    # 비동기 메인 실행
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n프로그램 실행 중 오류 발생: {e}")
        sys.exit(1)
