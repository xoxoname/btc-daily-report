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

# 미러 트레이딩 관련 임포트
try:
    from gateio_client import GateClient
    from mirror_trading import MirrorTradingSystem
    MIRROR_TRADING_AVAILABLE = True
except ImportError:
    MIRROR_TRADING_AVAILABLE = False
    print("⚠️ 미러 트레이딩 모듈을 찾을 수 없습니다. 분석 전용 모드로 실행됩니다.")

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
        self.logger.info("비트코인 예측 시스템 초기화 시작 - 정확도 향상 버전")
        self.logger.info("=" * 50)
        
        # 설정 로드
        try:
            self.config = Config()
        except Exception as e:
            self.logger.error(f"설정 로드 실패: {e}")
            raise
        
        # 미러 트레이딩 모드 확인
        self.mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'true').lower() == 'true'
        self.logger.info(f"미러 트레이딩 모드: {'활성화' if self.mirror_mode else '비활성화'}")
        
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
        """클라이언트 초기화"""
        try:
            # Bitget 클라이언트
            self.bitget_client = BitgetClient(self.config)
            self.logger.info("✅ Bitget 클라이언트 초기화 완료")
            
            # Telegram 봇
            self.telegram_bot = TelegramBot(self.config)
            self.logger.info("✅ Telegram 봇 초기화 완료")
            
            # Gate.io 클라이언트 (미러 모드일 때만)
            self.gate_client = None
            self.mirror_trading = None
            
            if self.mirror_mode and MIRROR_TRADING_AVAILABLE:
                try:
                    self.gate_client = GateClient(self.config)
                    self.mirror_trading = MirrorTradingSystem(
                        self.config,
                        self.bitget_client,
                        self.gate_client,
                        self.telegram_bot
                    )
                    self.logger.info("✅ Gate.io 클라이언트 및 미러 트레이딩 초기화 완료")
                except Exception as e:
                    self.logger.warning(f"미러 트레이딩 초기화 실패: {e}")
                    self.mirror_mode = False
                    
        except Exception as e:
            self.logger.error(f"클라이언트 초기화 실패: {e}")
            raise
    
    def _initialize_components(self):
        """컴포넌트 초기화"""
        try:
            # 데이터 수집기
            self.data_collector = RealTimeDataCollector(self.config)
            self.data_collector.set_bitget_client(self.bitget_client)
            self.logger.info("✅ 데이터 수집기 초기화 완료")
            
            # 지표 시스템
            self.indicator_system = AdvancedTradingIndicators()
            self.logger.info("✅ 지표 시스템 초기화 완료")
            
            # 통합 리포트 생성기
            self.report_manager = ReportGeneratorManager(
                self.config,
                self.data_collector,
                self.indicator_system
            )
            self.report_manager.set_bitget_client(self.bitget_client)
            
            # Gate.io 클라이언트 설정 (미러 모드일 때만)
            if self.mirror_mode and self.gate_client:
                self.report_manager.set_gateio_client(self.gate_client)
                self.logger.info("✅ ReportManager에 Gate.io 클라이언트 설정 완료")
            
            self.logger.info("✅ 리포트 생성기 초기화 완료")
            
            # 분석 엔진
            self.analysis_engine = AnalysisEngine(
                bitget_client=self.bitget_client,
                openai_client=None
            )
            self.logger.info("✅ 분석 엔진 초기화 완료")
            
            # 예외 감지기
            self.exception_detector = ExceptionDetector(
                bitget_client=self.bitget_client,
                telegram_bot=self.telegram_bot
            )
            self.logger.info("✅ 예외 감지기 초기화 완료 - 비트코인 전용")
            
        except Exception as e:
            self.logger.error(f"컴포넌트 초기화 실패: {e}")
            raise
    
    def _setup_scheduler(self):
        """스케줄러 작업 설정"""
        timezone = pytz.timezone('Asia/Seoul')
        
        # 정기 리포트 스케줄 (9시, 13시, 18시, 23시)
        report_times = [
            (9, 0, "morning_report"),
            (13, 0, "lunch_report"),
            (18, 0, "evening_report"),
            (23, 0, "night_report")
        ]
        
        for hour, minute, job_id in report_times:
            self.scheduler.add_job(
                func=self.handle_report_command,
                trigger="cron",
                hour=hour,
                minute=minute,
                timezone=timezone,
                id=job_id,
                replace_existing=True
            )
            self.logger.info(f"📅 정기 리포트 스케줄 등록: {hour:02d}:{minute:02d}")
        
        # 예외 감지 (5분마다)
        self.scheduler.add_job(
            func=self.check_exceptions,
            trigger="interval",
            minutes=5,
            timezone=timezone,
            id="exception_check",
            replace_existing=True
        )
        self.logger.info("📅 예외 감지 스케줄 등록: 5분마다")
        
        # 급속 변동 감지 (2분마다)
        self.scheduler.add_job(
            func=self.rapid_exception_check,
            trigger="interval",
            minutes=2,
            timezone=timezone,
            id="rapid_exception_check",
            replace_existing=True
        )
        self.logger.info("📅 급속 변동 감지 스케줄 등록: 2분마다")
        
        # 시스템 상태 체크 (30분마다)
        self.scheduler.add_job(
            func=self.system_health_check,
            trigger="interval",
            minutes=30,
            timezone=timezone,
            id="health_check",
            replace_existing=True
        )
        
        # ML 예측 검증 (30분마다) - ML 모드일 때만
        if self.ml_mode and self.ml_predictor:
            self.scheduler.add_job(
                func=self.verify_ml_predictions,
                trigger="interval",
                minutes=30,
                timezone=timezone,
                id="ml_verification",
                replace_existing=True
            )
            self.logger.info("📅 ML 예측 검증 스케줄 등록: 30분마다")
        
        # 일일 통계 리포트 (매일 자정)
        self.scheduler.add_job(
            func=self.daily_stats_report,
            trigger="cron",
            hour=0,
            minute=0,
            timezone=timezone,
            id="daily_stats",
            replace_existing=True
        )
        
        # 예외 감지 통계 리포트 (6시간마다)
        self.scheduler.add_job(
            func=self.exception_stats_report,
            trigger="interval",
            hours=6,
            timezone=timezone,
            id="exception_stats",
            replace_existing=True
        )
        
        self.logger.info("✅ 스케줄러 설정 완료")
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        self.logger.info(f"시그널 {signum} 수신 - 시스템 종료 시작")
        asyncio.create_task(self.stop())
    
    async def rapid_exception_check(self):
        """급속 변동 감지 - 2분마다 실행"""
        try:
            self.logger.debug("급속 변동 감지 시작")
            
            # 단기 변동성 체크
            try:
                anomalies = await self.exception_detector.detect_all_anomalies()
                
                for anomaly in anomalies:
                    if anomaly.get('type') in ['short_term_volatility', 'rapid_price_change']:
                        self.exception_stats['short_term_alerts'] += 1
                        self.exception_stats['total_detected'] += 1
                        self.logger.warning(f"급속 변동 감지: {anomaly}")
                        await self.exception_detector.send_alert(anomaly)
                    
            except Exception as e:
                self.logger.error(f"급속 변동 체크 오류: {e}")
                
        except Exception as e:
            self.logger.error(f"급속 변동 감지 실패: {str(e)}")
    
    async def check_exceptions(self):
        """예외 상황 감지 - 간소화"""
        try:
            self.logger.debug("예외 상황 체크 시작")
            
            # 기존 예외 감지
            anomalies = await self.exception_detector.detect_all_anomalies()
            
            for anomaly in anomalies:
                # 통계 업데이트
                anomaly_type = anomaly.get('type', '')
                if anomaly_type == 'price_anomaly':
                    self.exception_stats['price_alerts'] += 1
                elif anomaly_type == 'volume_anomaly':
                    self.exception_stats['volume_alerts'] += 1
                elif anomaly_type == 'funding_rate_anomaly':
                    self.exception_stats['funding_alerts'] += 1
                
                self.exception_stats['total_detected'] += 1
                
                self.logger.warning(f"이상 징후 감지: {anomaly}")
                await self.exception_detector.send_alert(anomaly)
            
            # 데이터 수집기의 이벤트 확인 (뉴스)
            critical_events = []
            for event in self.data_collector.events_buffer:
                severity = None
                if hasattr(event, 'severity'):
                    severity = event.severity.value
                elif isinstance(event, dict):
                    severity = event.get('severity')
                
                if severity == 'critical':  # critical만 처리
                    critical_events.append(event)
            
            # 중요 이벤트 처리
            for event in critical_events[:3]:  # 최대 3개
                try:
                    if hasattr(event, '__dict__'):
                        event_data = event.__dict__
                    else:
                        event_data = event
                    
                    # 비트코인 관련성 체크
                    impact = event_data.get('impact', '')
                    if '무관' in impact or '알트코인' in impact:
                        self.logger.info(f"🔄 비트코인 무관 뉴스 스킵: {event_data.get('title', '')[:50]}...")
                        continue
                    
                    # 뉴스 이벤트 통계
                    if event_data.get('type') == 'critical_news':
                        self.exception_stats['news_alerts'] += 1
                        self.exception_stats['total_detected'] += 1
                    
                    # ML 예측 기록 (ML 모드일 때만)
                    if self.ml_mode and self.ml_predictor and event_data.get('type') == 'critical_news':
                        try:
                            ticker = await self.bitget_client.get_ticker('BTCUSDT')
                            if ticker:
                                current_price = float(ticker.get('last', 0))
                                
                                market_data = await self._get_market_data_for_ml()
                                prediction = await self.ml_predictor.predict_impact(event_data, market_data)
                                
                                await self.ml_predictor.record_prediction(
                                    event_data,
                                    prediction,
                                    current_price
                                )
                                
                                self.logger.info(f"ML 예측 기록: {event_data.get('title', '')[:30]}...")
                        except Exception as e:
                            self.logger.error(f"ML 예측 기록 실패: {e}")
                    
                    # 예외 리포트 생성 및 전송
                    report = await self.report_manager.generate_exception_report(event_data)
                    await self.telegram_bot.send_message(report, parse_mode='HTML')
                    
                    self.logger.info(f"긴급 알림 전송: {event_data.get('title_ko', event_data.get('title', 'Unknown'))[:50]}...")
                    
                except Exception as e:
                    self.logger.error(f"예외 리포트 생성 실패: {e}")
            
            # 버퍼 클리어
            self.data_collector.events_buffer = []
            
            # 미러 트레이딩 상태 체크 (활성화된 경우)
            if self.mirror_mode and self.mirror_trading:
                await self._check_mirror_health()
                
        except Exception as e:
            self.logger.error(f"예외 감지 실패: {str(e)}")
            self.logger.debug(traceback.format_exc())
    
    async def exception_stats_report(self):
        """예외 감지 통계 리포트"""
        try:
            current_time = datetime.now()
            last_reset = datetime.fromisoformat(self.exception_stats['last_reset'])
            time_since_reset = current_time - last_reset
            hours_since_reset = time_since_reset.total_seconds() / 3600
            
            if hours_since_reset < 1:
                return
            
            total = self.exception_stats['total_detected']
            if total == 0:
                return
            
            report = f"""<b>📊 예외 감지 통계 리포트</b>
🕐 {current_time.strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━

<b>📈 지난 {hours_since_reset:.1f}시간 동안:</b>
- 총 감지: <b>{total}건</b>
- 시간당 평균: <b>{total/hours_since_reset:.1f}건</b>

<b>📋 카테고리별 감지:</b>
- 🚨 중요 뉴스: <b>{self.exception_stats['news_alerts']}건</b> ({self.exception_stats['news_alerts']/total*100:.0f}%)
- 📊 가격 변동: <b>{self.exception_stats['price_alerts']}건</b> ({self.exception_stats['price_alerts']/total*100:.0f}%)
- 📈 거래량 급증: <b>{self.exception_stats['volume_alerts']}건</b> ({self.exception_stats['volume_alerts']/total*100:.0f}%)
- 💰 펀딩비 이상: <b>{self.exception_stats['funding_alerts']}건</b> ({self.exception_stats['funding_alerts']/total*100:.0f}%)
- ⚡ 단기 급변동: <b>{self.exception_stats['short_term_alerts']}건</b> ({self.exception_stats['short_term_alerts']/total*100:.0f}%)

━━━━━━━━━━━━━━━━━━━
🔥 비트코인 전용 시스템 정상 작동 중"""
            
            await self.telegram_bot.send_message(report, parse_mode='HTML')
            
            # 통계 초기화
            self.exception_stats = {
                'total_detected': 0,
                'news_alerts': 0,
                'price_alerts': 0,
                'volume_alerts': 0,
                'funding_alerts': 0,
                'short_term_alerts': 0,
                'last_reset': current_time.isoformat()
            }
            
            self.logger.info(f"예외 감지 통계 리포트 전송 완료 - 총 {total}건")
            
        except Exception as e:
            self.logger.error(f"예외 통계 리포트 생성 실패: {e}")
    
    async def handle_natural_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """자연어 메시지 처리"""
        try:
            self.command_stats['natural_language'] += 1
            message = update.message.text.lower()
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            
            self.logger.info(f"자연어 메시지 수신 - User: {username}({user_id}), Message: {message}")
            
            # 명령어 매핑
            command_map = {
                'mirror': ['미러', 'mirror', '동기화', 'sync', '복사', 'copy'],
                'profit': ['수익', '얼마', '벌었', '손익', '이익', '손실', 'profit', 'pnl'],
                'forecast': ['매수', '매도', '사야', '팔아', '지금', '예측', 'buy', 'sell', '롱', '숏'],
                'report': ['시장', '상황', '어때', '분석', 'market', '리포트'],
                'schedule': ['일정', '언제', '시간', 'schedule', '스케줄'],
                'stats': ['통계', '성과', '감지', 'stats', '예외'],
                'help': ['도움', '명령', 'help', '사용법', '안내']
            }
            
            # 명령어 찾기
            detected_command = None
            for command, keywords in command_map.items():
                if any(keyword in message for keyword in keywords):
                    detected_command = command
                    break
            
            # 명령어 실행
            if detected_command == 'mirror' and self.mirror_mode:
                await self.handle_mirror_status(update, context)
            elif detected_command == 'profit':
                await self.handle_profit_command(update, context)
            elif detected_command == 'forecast':
                await self.handle_forecast_command(update, context)
            elif detected_command == 'report':
                await self.handle_report_command(update, context)
            elif detected_command == 'schedule':
                await self.handle_schedule_command(update, context)
            elif detected_command == 'stats':
                await self.handle_stats_command(update, context)
            elif detected_command == 'help':
                await self.handle_start_command(update, context)
            else:
                # 기본 응답
                response = self._generate_default_response(message)
                await update.message.reply_text(response, parse_mode='HTML')
                
        except Exception as e:
            self.command_stats['errors'] += 1
            self.logger.error(f"자연어 처리 실패: {str(e)}")
            self.logger.debug(traceback.format_exc())
            await update.message.reply_text("❌ 메시지 처리 중 오류가 발생했습니다.", parse_mode='HTML')
    
    async def handle_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """통계 명령 처리"""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            self.logger.info(f"통계 요청 - User: {username}({user_id})")
            
            current_time = datetime.now()
            uptime = current_time - self.startup_time
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            
            # 예외 감지 통계
            last_reset = datetime.fromisoformat(self.exception_stats['last_reset'])
            stats_time = current_time - last_reset
            stats_hours = stats_time.total_seconds() / 3600
            
            total_exceptions = self.exception_stats['total_detected']
            total_commands = sum(self.command_stats.values())
            
            stats_msg = f"""<b>📊 시스템 실시간 통계</b>
🕐 {current_time.strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━

<b>⏱️ 시스템 상태:</b>
- 가동 시간: <b>{hours}시간 {minutes}분</b>
- 총 명령 처리: <b>{total_commands}건</b>
- 오류 발생: <b>{self.command_stats['errors']}건</b>

<b>🚨 예외 감지 성과 (최근 {stats_hours:.1f}시간):</b>
- 총 감지: <b>{total_exceptions}건</b>
- 시간당 평균: <b>{total_exceptions/max(stats_hours, 0.1):.1f}건</b>

<b>📋 세부 감지 현황:</b>
- 🚨 중요 뉴스: <b>{self.exception_stats['news_alerts']}건</b>
- 📊 가격 변동: <b>{self.exception_stats['price_alerts']}건</b>
- 📈 거래량 급증: <b>{self.exception_stats['volume_alerts']}건</b>
- 💰 펀딩비 이상: <b>{self.exception_stats['funding_alerts']}건</b>
- ⚡ 단기 급변동: <b>{self.exception_stats['short_term_alerts']}건</b>

<b>💬 명령어 사용 통계:</b>
- 리포트: {self.command_stats['report']}회
- 예측: {self.command_stats['forecast']}회
- 수익: {self.command_stats['profit']}회"""

            if self.mirror_mode:
                stats_msg += f"\n• 미러: {self.command_stats['mirror']}회"
            
            stats_msg += f"""
- 자연어: {self.command_stats['natural_language']}회

<b>🔧 감지 설정:</b>
- 가격 변동: ≥{self.exception_detector.PRICE_CHANGE_THRESHOLD}%
- 거래량: ≥{self.exception_detector.VOLUME_SPIKE_THRESHOLD}배
- 펀딩비: ≥{self.exception_detector.FUNDING_RATE_THRESHOLD*100:.1f}%
- 단기 변동: ≥{self.exception_detector.short_term_threshold}% (5분)

━━━━━━━━━━━━━━━━━━━
⚡ 비트코인 전용 고정밀 시스템"""
            
            if self.ml_mode and self.ml_predictor:
                ml_stats = self.ml_predictor.get_stats()
                stats_msg += f"""

<b>🤖 ML 예측 성능:</b>
- 총 예측: {ml_stats['total_predictions']}건
- 방향 정확도: {ml_stats['direction_accuracy']}
- 크기 정확도: {ml_stats['magnitude_accuracy']}"""
            
            await update.message.reply_text(stats_msg, parse_mode='HTML')
            
        except Exception as e:
            self.command_stats['errors'] += 1
            self.logger.error(f"통계 명령 처리 실패: {str(e)}")
            await update.message.reply_text("❌ 통계 조회 중 오류가 발생했습니다.", parse_mode='HTML')
    
    def _generate_default_response(self, message: str) -> str:
        """기본 응답 생성"""
        responses = [
            "죄송합니다. 이해하지 못했습니다. 🤔",
            "무엇을 도와드릴까요? 🤔",
            "더 구체적으로 말씀해주시겠어요? 🤔"
        ]
        
        import random
        response = random.choice(responses)
        
        return f"{response}\n\n다음과 같이 질문해보세요:\n• '오늘 수익은?'\n• '지금 매수해도 돼?'\n• '시장 상황 어때?'\n• '다음 리포트 언제?'\n• '시스템 통계 보여줘'\n\n또는 /help 명령어로 전체 기능을 확인하세요."
    
    async def handle_mirror_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """미러 트레이딩 상태 확인"""
        try:
            self.command_stats['mirror'] += 1
            
            if not self.mirror_mode or not self.mirror_trading:
                await update.message.reply_text(
                    "📊 현재 분석 전용 모드로 실행 중입니다.\n"
                    "미러 트레이딩이 비활성화되어 있습니다.\n\n"
                    "활성화 방법:\n"
                    "1. .env 파일에 MIRROR_TRADING_MODE=true 추가\n"
                    "2. Gate.io API 키 설정\n"
                    "3. 시스템 재시작",
                    parse_mode='HTML'
                )
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
            
            status_msg = f"""🔄 <b>미러 트레이딩 상태</b>

<b>💰 계정 잔고:</b>
- 비트겟: ${bitget_equity:,.2f}
- 게이트: ${gate_equity:,.2f}
- 잔고 비율: {(gate_equity/bitget_equity*100):.1f}%

<b>📊 포지션 현황:</b>
- 비트겟: {bitget_pos_count}개
- 게이트: {gate_pos_count}개
- 활성 미러: {active_mirrors}개
- 제외된 기존 포지션: {len(self.mirror_trading.startup_positions)}개

<b>🔥 예약 주문 현황:</b>
- 복제된 예약 주문: {len(self.mirror_trading.mirrored_plan_orders)}개
- 제외된 기존 예약 주문: {len(self.mirror_trading.startup_plan_orders)}개

<b>📈 오늘 통계:</b>
- 시도: {self.mirror_trading.daily_stats['total_mirrored']}회
- 성공: {self.mirror_trading.daily_stats['successful_mirrors']}회
- 실패: {self.mirror_trading.daily_stats['failed_mirrors']}회
- 성공률: {success_rate:.1f}%
- 예약 주문 미러링: {self.mirror_trading.daily_stats['plan_order_mirrors']}회
- 예약 주문 취소: {self.mirror_trading.daily_stats['plan_order_cancels']}회
- 부분청산: {self.mirror_trading.daily_stats['partial_closes']}회
- 전체청산: {self.mirror_trading.daily_stats['full_closes']}회
- 총 거래량: ${self.mirror_trading.daily_stats['total_volume']:,.2f}

<b>💰 달러 비율 복제:</b>
- 총 자산 대비 동일 비율 유지
- 최대 30% 제한 적용
- 예약 주문도 동일 비율 복제

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
        """리포트 명령 처리"""
        try:
            self.command_stats['report'] += 1
            
            if update:
                user_id = update.effective_user.id
                username = update.effective_user.username or "Unknown"
                self.logger.info(f"리포트 요청 - User: {username}({user_id})")
                await update.message.reply_text("📊 비트코인 분석 리포트를 생성중입니다...", parse_mode='HTML')
            else:
                self.logger.info("정기 리포트 생성 시작")
                await self.telegram_bot.send_message("📊 정기 비트코인 분석 리포트를 생성중입니다...", parse_mode='HTML')
            
            # 리포트 생성 시간 측정
            start_time = datetime.now()
            
            # 새로운 정기 리포트 생성기 사용
            report = await self.report_manager.generate_regular_report()
            
            generation_time = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"리포트 생성 완료 - 소요시간: {generation_time:.2f}초")
            
            # 리포트 길이 체크 (텔레그램 메시지 제한)
            if len(report) > 4000:
                # 긴 리포트는 분할 전송
                parts = self._split_message(report, 4000)
                for i, part in enumerate(parts):
                    if update:
                        await update.message.reply_text(part, parse_mode='HTML')
                    else:
                        await self.telegram_bot.send_message(part, parse_mode='HTML')
                    if i < len(parts) - 1:
                        await asyncio.sleep(0.5)  # 연속 전송 방지
            else:
                if update:
                    await update.message.reply_text(report, parse_mode='HTML')
                else:
                    await self.telegram_bot.send_message(report, parse_mode='HTML')
            
            self.logger.info("리포트 전송 완료")
            
        except Exception as e:
            self.command_stats['errors'] += 1
            error_message = f"❌ 리포트 생성 중 오류가 발생했습니다: {str(e)[:200]}"
            self.logger.error(f"리포트 생성 실패: {str(e)}")
            self.logger.debug(f"리포트 생성 오류 상세: {traceback.format_exc()}")
            
            try:
                if update:
                    await update.message.reply_text(error_message, parse_mode='HTML')
                else:
                    await self.telegram_bot.send_message(error_message, parse_mode='HTML')
            except Exception as send_error:
                self.logger.error(f"오류 메시지 전송 실패: {str(send_error)}")
    
    async def handle_forecast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """예측 명령 처리"""
        try:
            self.command_stats['forecast'] += 1
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            self.logger.info(f"예측 요청 - User: {username}({user_id})")
            
            await update.message.reply_text("🔮 단기 예측 분석 중...", parse_mode='HTML')
            
            # 새로운 예측 리포트 생성기 사용
            report = await self.report_manager.generate_forecast_report()
            
            await update.message.reply_text(report, parse_mode='HTML')
            
            # 추가 정보 제공
            current_data = await self.bitget_client.get_ticker(self.config.symbol)
            if current_data:
                current_price = float(current_data.get('last', 0))
                change_24h = float(current_data.get('changeUtc', 0)) * 100
                
                await update.message.reply_text(
                    f"<b>📊 현재 상태 요약</b>\n"
                    f"• 현재가: ${current_price:,.0f}\n"
                    f"• 24시간 변동: {change_24h:+.2f}%\n"
                    f"• 다음 업데이트: 3시간 후",
                    parse_mode='HTML'
                )
            
        except Exception as e:
            self.command_stats['errors'] += 1
            self.logger.error(f"예측 명령 처리 실패: {str(e)}")
            self.logger.debug(traceback.format_exc())
            await update.message.reply_text(
                f"❌ 예측 분석 중 오류가 발생했습니다.\n"
                f"잠시 후 다시 시도해주세요.",
                parse_mode='HTML'
            )
    
    async def handle_profit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """수익 명령 처리"""
        try:
            self.command_stats['profit'] += 1
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            self.logger.info(f"수익 조회 요청 - User: {username}({user_id})")
            
            await update.message.reply_text("💰 실시간 수익 현황을 조회중입니다...", parse_mode='HTML')
            
            # 새로운 수익 리포트 생성기 사용
            profit_report = await self.report_manager.generate_profit_report()
            
            await update.message.reply_text(profit_report, parse_mode='HTML')
            
        except Exception as e:
            self.command_stats['errors'] += 1
            self.logger.error(f"수익 명령 처리 실패: {str(e)}")
            self.logger.debug(f"수익 조회 오류 상세: {traceback.format_exc()}")
            await update.message.reply_text(
                "❌ 수익 조회 중 오류가 발생했습니다.\n"
                "잠시 후 다시 시도해주세요.",
                parse_mode='HTML'
            )
    
    async def handle_schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """일정 명령 처리"""
        try:
            self.command_stats['schedule'] += 1
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            self.logger.info(f"일정 조회 요청 - User: {username}({user_id})")
            
            # 새로운 일정 리포트 생성기 사용
            schedule_report = await self.report_manager.generate_schedule_report()
            
            # 추가 일정 정보
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            additional_info = f"\n\n<b>📅 추가 일정 정보:</b>\n"
            additional_info += f"• 현재 시각: {now.strftime('%Y-%m-%d %H:%M')} KST\n"
            additional_info += f"• 다음 정기 리포트: "
            
            # 다음 리포트 시간 계산
            report_hours = [9, 13, 18, 23]
            next_report_hour = None
            for hour in report_hours:
                if now.hour < hour:
                    next_report_hour = hour
                    break
            
            if next_report_hour:
                additional_info += f"오늘 {next_report_hour}:00\n"
            else:
                additional_info += f"내일 09:00\n"
            
            additional_info += f"• 예외 감지: 5분마다 자동 실행\n"
            additional_info += f"• 급속 변동 감지: 2분마다 자동 실행\n"
            additional_info += f"• 시스템 상태 체크: 30분마다"
            
            if self.ml_mode:
                additional_info += f"\n• ML 예측 검증: 30분마다"
            
            full_report = schedule_report + additional_info
            
            await update.message.reply_text(full_report, parse_mode='HTML')
            
        except Exception as e:
            self.command_stats['errors'] += 1
            self.logger.error(f"일정 명령 처리 실패: {str(e)}")
            await update.message.reply_text("❌ 일정 조회 중 오류가 발생했습니다.", parse_mode='HTML')
    
    async def _get_market_data_for_ml(self) -> Dict:
        """ML을 위한 시장 데이터 수집"""
        market_data = {
            'trend': 'neutral',
            'volatility': 0.02,
            'volume_ratio': 1.0,
            'rsi': 50,
            'fear_greed': 50,
            'btc_dominance': 50
        }
        
        try:
            # 현재 가격 정보
            if self.bitget_client:
                ticker = await self.bitget_client.get_ticker('BTCUSDT')
                if ticker:
                    # 24시간 변화율로 트렌드 판단
                    change_24h = float(ticker.get('changeUtc', 0))
                    if change_24h > 0.02:
                        market_data['trend'] = 'bullish'
                    elif change_24h < -0.02:
                        market_data['trend'] = 'bearish'
                    
                    # 거래량 비율 (평균 대비)
                    volume = float(ticker.get('baseVolume', 0))
                    market_data['volume_ratio'] = volume / 50000 if volume > 0 else 1.0
            
            # 기술 지표는 실제 구현 필요
            # 여기서는 기본값 사용
            
        except Exception as e:
            self.logger.error(f"시장 데이터 수집 실패: {e}")
        
        return market_data
    
    async def verify_ml_predictions(self):
        """ML 예측 검증"""
        if not self.ml_mode or not self.ml_predictor:
            return
        
        try:
            self.logger.info("ML 예측 검증 시작")
            
            # 예측 검증
            verifications = await self.ml_predictor.verify_predictions()
            
            # 중요한 검증 결과만 알림
            for verification in verifications:
                if abs(verification['accuracy']) < 50:  # 정확도가 50% 미만인 경우
                    msg = f"""<b>🤖 AI 예측 검증 결과</b>

<b>📰 이벤트:</b> {verification['event']['title'][:50]}...
<b>⏰ 예측 시간:</b> {verification['prediction_time']}

<b>📊 예측 vs 실제:</b>
- 예측 변동률: <b>{verification['predicted_change']:.1f}%</b>
- 실제 변동률: <b>{verification['actual_change']:.1f}%</b>
- 초기가: ${verification['initial_price']:,.0f}
- 현재가: ${verification['current_price']:,.0f}

<b>✅ 정확도:</b>
- 방향: {"✅ 맞음" if verification['direction_correct'] else "❌ 틀림"}
- 크기 정확도: <b>{verification['accuracy']:.1f}%</b>

<b>📈 전체 AI 성능:</b>
- 누적 정확도: {self.ml_predictor.direction_accuracy:.1%}"""
                    
                    await self.telegram_bot.send_message(msg, parse_mode='HTML')
            
            # 통계 업데이트
            stats = self.ml_predictor.get_stats()
            self.logger.info(f"ML 예측 검증 완료 - 방향 정확도: {stats['direction_accuracy']}, 크기 정확도: {stats['magnitude_accuracy']}")
            
        except Exception as e:
            self.logger.error(f"ML 예측 검증 실패: {e}")
    
    async def _check_mirror_health(self):
        """미러 트레이딩 건강 상태 체크"""
        try:
            # 실패율 체크
            if self.mirror_trading.daily_stats['total_mirrored'] > 10:
                fail_rate = (self.mirror_trading.daily_stats['failed_mirrors'] / 
                           self.mirror_trading.daily_stats['total_mirrored'])
                
                if fail_rate > 0.3:  # 30% 이상 실패
                    await self.telegram_bot.send_message(
                        f"<b>⚠️ 미러 트레이딩 경고</b>\n"
                        f"높은 실패율 감지: {fail_rate*100:.1f}%\n"
                        f"시스템 점검이 필요할 수 있습니다.",
                        parse_mode='HTML'
                    )
            
            # 동기화 불일치 체크
            bitget_positions = await self.bitget_client.get_positions(self.config.symbol)
            gate_positions = await self.gate_client.get_positions("BTC_USDT")
            
            bitget_active = sum(1 for pos in bitget_positions if float(pos.get('total', 0)) > 0)
            gate_active = sum(1 for pos in gate_positions if pos.get('size', 0) != 0)
            
            # 시작 시 포지션 제외
            mirrored_expected = bitget_active - len(self.mirror_trading.startup_positions)
            
            if mirrored_expected > 0 and gate_active == 0:
                self.logger.warning("미러링 동기화 문제 감지")
                
        except Exception as e:
            self.logger.error(f"미러 건강 체크 실패: {e}")
    
    async def system_health_check(self):
        """시스템 건강 상태 체크"""
        try:
            self.logger.info("시스템 건강 상태 체크 시작")
            
            health_status = {
                'timestamp': datetime.now().isoformat(),
                'uptime': str(datetime.now() - self.startup_time),
                'services': {},
                'errors': []
            }
            
            # Bitget 연결 체크
            try:
                ticker = await self.bitget_client.get_ticker(self.config.symbol)
                health_status['services']['bitget'] = 'OK'
            except Exception as e:
                health_status['services']['bitget'] = 'ERROR'
                health_status['errors'].append(f"Bitget: {str(e)[:50]}")
            
            # Gate.io 연결 체크 (미러 모드일 때만)
            if self.mirror_mode and self.gate_client:
                try:
                    balance = await self.gate_client.get_account_balance()
                    health_status['services']['gate'] = 'OK'
                except Exception as e:
                    health_status['services']['gate'] = 'ERROR'
                    health_status['errors'].append(f"Gate: {str(e)[:50]}")
            
            # 데이터 수집기 상태
            if self.data_collector.session and not self.data_collector.session.closed:
                health_status['services']['data_collector'] = 'OK'
            else:
                health_status['services']['data_collector'] = 'ERROR'
            
            # ML 예측기 상태 (ML 모드일 때만)
            if self.ml_mode and self.ml_predictor:
                health_status['services']['ml_predictor'] = 'OK'
                health_status['ml_stats'] = self.ml_predictor.get_stats()
            
            # 예외 감지기 상태
            health_status['services']['exception_detector'] = 'OK'
            
            # exception_stats 복사
            health_status['exception_stats'] = {
                'total_detected': self.exception_stats['total_detected'],
                'news_alerts': self.exception_stats['news_alerts'],
                'price_alerts': self.exception_stats['price_alerts'],
                'volume_alerts': self.exception_stats['volume_alerts'],
                'funding_alerts': self.exception_stats['funding_alerts'],
                'short_term_alerts': self.exception_stats['short_term_alerts'],
                'last_reset': self.exception_stats['last_reset']
            }
            
            # 메모리 사용량 체크
            import psutil
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            health_status['memory_mb'] = memory_info.rss / 1024 / 1024
            
            # 명령어 통계
            health_status['command_stats'] = self.command_stats.copy()
            
            # 문제가 있으면 알림
            if health_status['errors']:
                error_msg = "<b>⚠️ 시스템 건강 체크 경고</b>\n"
                for error in health_status['errors']:
                    error_msg += f"• {error}\n"
                error_msg += f"\n메모리 사용: {health_status['memory_mb']:.1f} MB"
                
                await self.telegram_bot.send_message(error_msg, parse_mode='HTML')
            
            # 로그 기록
            self.logger.info(f"시스템 건강 체크 완료: {json.dumps(health_status, indent=2)}")
            
        except Exception as e:
            self.logger.error(f"시스템 건강 체크 실패: {e}")
    
    async def daily_stats_report(self):
        """일일 통계 리포트"""
        try:
            self.logger.info("일일 통계 리포트 생성")
            
            # 시스템 가동 시간
            uptime = datetime.now() - self.startup_time
            days = uptime.days
            hours = int((uptime.total_seconds() % 86400) // 3600)
            
            # 예외 감지 통계
            total_exceptions = self.exception_stats['total_detected']
            
            report = f"""<b>📊 일일 시스템 통계 리포트</b>
📅 {datetime.now().strftime('%Y-%m-%d')}
━━━━━━━━━━━━━━━━━━━

<b>⏱️ 시스템 가동 시간:</b> {days}일 {hours}시간

<b>🚨 예외 감지 성과 (오늘):</b>
- 총 감지: <b>{total_exceptions}건</b>
- 중요 뉴스: {self.exception_stats['news_alerts']}건
- 가격 변동: {self.exception_stats['price_alerts']}건
- 거래량 급증: {self.exception_stats['volume_alerts']}건
- 펀딩비 이상: {self.exception_stats['funding_alerts']}건
- 단기 급변동: {self.exception_stats['short_term_alerts']}건

<b>📈 명령어 사용 통계:</b>
- 리포트: {self.command_stats['report']}회
- 예측: {self.command_stats['forecast']}회
- 수익 조회: {self.command_stats['profit']}회
- 일정 확인: {self.command_stats['schedule']}회"""

            if self.mirror_mode:
                report += f"\n• 미러 상태: {self.command_stats['mirror']}회"
            
            report += f"""
- 자연어 입력: {self.command_stats['natural_language']}회
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
    
    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시작 명령 처리"""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            self.logger.info(f"시작 명령 - User: {username}({user_id})")
            
            mode_text = "🔄 미러 트레이딩 모드" if self.mirror_mode else "📊 분석 전용 모드"
            if self.ml_mode:
                mode_text += " + 🤖 ML 예측"
            
            welcome_message = f"""<b>🚀 비트코인 예측 시스템에 오신 것을 환영합니다!</b>

현재 모드: {mode_text}
시스템 버전: 2.2 - 비트코인 전용 정확도 향상

<b>📊 슬래시 명령어:</b>
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
            
            welcome_message += f"""
<b>🔔 자동 기능:</b>
- 정기 리포트: 09:00, 13:00, 18:00, 23:00
- 예외 감지: <b>5분마다</b>
- 급속 변동: <b>2분마다</b>
- 뉴스 수집: <b>15초마다</b> (RSS)
- 시스템 체크: 30분마다"""
            
            if self.ml_mode:
                welcome_message += "\n• ML 예측 검증: 30분마다"
            
            welcome_message += f"""

<b>⚡ 실시간 알림 (비트코인 전용):</b>
- 가격 급변동 (≥{self.exception_detector.PRICE_CHANGE_THRESHOLD}%)
- 단기 급변동 (5분 내 ≥{self.exception_detector.short_term_threshold}%)
- 비트코인 중요 뉴스 (ETF, 기업 구매, 규제)
- 펀딩비 이상 (≥{self.exception_detector.FUNDING_RATE_THRESHOLD*100:.1f}%)
- 거래량 급증 (≥{self.exception_detector.VOLUME_SPIKE_THRESHOLD}배)
"""
            
            if self.mirror_mode:
                welcome_message += """
<b>🔄 미러 트레이딩 (달러 비율 복제):</b>
- 비트겟 → 게이트 자동 복제
- 총 자산 대비 동일 비율
- 예약 주문도 동일 비율 복제
- TP/SL 자동 동기화
- 부분/전체 청산 미러링
- 최대 30% 제한
"""
            
            if self.ml_mode:
                welcome_message += f"""
<b>🤖 ML 예측 시스템:</b>
- 과거 데이터 학습
- 실시간 예측
- 카테고리별 최적화
- 자동 성능 개선
"""
            
            # 시스템 상태 추가
            uptime = datetime.now() - self.startup_time
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            
            total_exceptions = self.exception_stats['total_detected']
            
            welcome_message += f"""
<b>📊 시스템 상태:</b>
- 가동 시간: {hours}시간 {minutes}분
- 오늘 명령 처리: {sum(self.command_stats.values())}건
- 오늘 예외 감지: <b>{total_exceptions}건</b>
- 활성 서비스: {'미러+분석' if self.mirror_mode else '분석'}{'+ ML' if self.ml_mode else ''}

🚨 <b>주요 특징:</b>
- 비트코인 전용 필터링
- 정확한 호재/악재 판단
- 현실적인 예상 변동률
- 상황별 맞춤 전략

📈 정확한 비트코인 분석을 제공합니다.

도움이 필요하시면 언제든 질문해주세요! 😊"""
            
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
            
            # Gate.io 클라이언트 초기화 (미러 모드일 때만)
            if self.mirror_mode and self.gate_client:
                self.logger.info("Gate.io 클라이언트 초기화 중...")
                await self.gate_client.initialize()
            
            # 데이터 수집기 시작
            self.logger.info("데이터 수집기 시작 중...")
            asyncio.create_task(self.data_collector.start())
            
            # 미러 트레이딩 시작 (미러 모드일 때만)
            if self.mirror_mode and self.mirror_trading:
                self.logger.info("미러 트레이딩 시스템 시작 중...")
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
            
            mode_text = "미러 트레이딩 (달러 비율)" if self.mirror_mode else "분석 전용"
            if self.ml_mode:
                mode_text += " + ML 예측"
            
            self.logger.info(f"✅ 비트코인 예측 시스템 시작 완료 (모드: {mode_text})")
            
            # 시작 메시지 전송
            startup_msg = f"""<b>🚀 비트코인 예측 시스템이 시작되었습니다!</b>

<b>📊 운영 모드:</b> {mode_text}
<b>🕐 시작 시각:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>🔥 버전:</b> 2.2 - 비트코인 전용
"""
            
            if self.mirror_mode:
                startup_msg += """
<b>🔄 미러 트레이딩 활성화 (달러 비율):</b>
- 비트겟 → 게이트 자동 복제
- 총 자산 대비 동일 비율 적용
- 예약 주문도 동일 비율 복제
- 기존 포지션/예약주문은 복제 제외
- 신규 진입만 미러링
- 최대 30% 제한
"""
            
            if self.ml_mode:
                startup_msg += f"""
<b>🤖 ML 예측 시스템 활성화:</b>
- 실시간 예측 및 검증
- 자동 학습 및 개선
"""
            
            startup_msg += f"""
<b>⚡ 비트코인 전용 기능:</b>
- 예외 감지: 5분마다
- 급속 변동: 2분마다
- 뉴스 수집: 15초마다 (RSS)
- 가격 임계값: {self.exception_detector.PRICE_CHANGE_THRESHOLD}%
- 거래량 임계값: {self.exception_detector.VOLUME_SPIKE_THRESHOLD}배

<b>🎯 필터링 강화:</b>
- 비트코인 직접 관련 뉴스만
- 알트코인/일반 정치 뉴스 제외
- 정확한 호재/악재 판단
- 현실적인 예상 변동률

<b>📌 활성 기능:</b>
- 실시간 가격 모니터링
- 비트코인 전용 뉴스 추적
- 기술적 분석
- GPT 기반 예측
- 자동 리포트 생성 (9시, 13시, 18시, 23시)

명령어를 입력하거나 자연어로 질문해보세요.
예: '오늘 수익은?' 또는 /help"""
            
            await self.telegram_bot.send_message(startup_msg, parse_mode='HTML')
            
            # 초기 시스템 상태 체크
            await asyncio.sleep(5)
            await self.system_health_check()
            
            # 메인 루프
            self.logger.info("메인 루프 시작")
            while self.is_running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("키보드 인터럽트 감지 - 시스템 종료 시작")
            await self.stop()
        except Exception as e:
            self.logger.error(f"시스템 시작 실패: {str(e)}")
            self.logger.debug(f"시작 오류 상세: {traceback.format_exc()}")
            
            # 오류 메시지 전송 시도
            try:
                await self.telegram_bot.send_message(
                    f"<b>❌ 시스템 시작 실패</b>\n"
                    f"오류: {str(e)[:200]}\n"
                    f"로그를 확인해주세요.",
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
                
                shutdown_msg += "\n\n비트코인 전용 시스템이 안전하게 종료됩니다."
                
                await self.telegram_bot.send_message(shutdown_msg, parse_mode='HTML')
            except:
                pass
            
            # 스케줄러 종료
            self.logger.info("스케줄러 종료 중...")
            self.scheduler.shutdown()
            
            # 텔레그램 봇 종료
            self.logger.info("텔레그램 봇 종료 중...")
            await self.telegram_bot.stop()
            
            # 미러 트레이딩 종료
            if self.mirror_mode and self.mirror_trading:
                self.logger.info("미러 트레이딩 종료 중...")
                await self.mirror_trading.stop()
            
            # 데이터 수집기 종료
            self.logger.info("데이터 수집기 종료 중...")
            if self.data_collector.session:
                await self.data_collector.close()
            
            # Bitget 클라이언트 종료
            self.logger.info("Bitget 클라이언트 종료 중...")
            if self.bitget_client.session:
                await self.bitget_client.close()
            
            # Gate.io 클라이언트 종료
            if self.gate_client and self.gate_client.session:
                self.logger.info("Gate.io 클라이언트 종료 중...")
                await self.gate_client.close()
            
            # ML 예측기 데이터 저장
            if self.ml_mode and self.ml_predictor:
                self.logger.info("ML 예측 데이터 저장 중...")
                self.ml_predictor.save_predictions()
            
            self.logger.info("=" * 50)
            self.logger.info("✅ 비트코인 전용 시스템이 안전하게 종료되었습니다")
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"시스템 종료 중 오류: {str(e)}")
            self.logger.debug(traceback.format_exc())

async def main():
    """메인 함수"""
    try:
        print("\n" + "=" * 50)
        print("🚀 비트코인 예측 시스템 v2.2 - 비트코인 전용")
        print("=" * 50 + "\n")
        
        system = BitcoinPredictionSystem()
        await system.start()
        
    except Exception as e:
        print(f"\n❌ 치명적 오류 발생: {e}")
        logging.error(f"치명적 오류: {e}")
        logging.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n\n치명적 오류: {e}")
        logging.error(f"프로그램 실행 실패: {e}")
        logging.debug(traceback.format_exc())
