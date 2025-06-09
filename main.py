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
        self.logger.info("비트코인 예측 시스템 초기화 시작 - 크리티컬 뉴스 필터링 강화")
        self.logger.info("=" * 50)
        
        # 설정 로드
        try:
            self.config = Config()
        except Exception as e:
            self.logger.error(f"설정 로드 실패: {e}")
            raise
        
        # 미러 트레이딩 모드 확인 - 개선된 버전
        self.mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'false').lower() == 'true'
        self.logger.info(f"환경변수 MIRROR_TRADING_MODE: {os.getenv('MIRROR_TRADING_MODE', 'not_set')}")
        self.logger.info(f"미러 트레이딩 모드: {'활성화' if self.mirror_mode else '비활성화'}")
        self.logger.info(f"미러 트레이딩 모듈 가용성: {'사용 가능' if MIRROR_TRADING_AVAILABLE else '사용 불가'}")
        
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
            'critical_news_processed': 0,  # 🔥🔥 추가: 크리티컬 뉴스 처리 통계
            'critical_news_filtered': 0,   # 🔥🔥 추가: 필터링된 뉴스 통계
            'forced_alerts': 0,
            'last_reset': datetime.now().isoformat()
        }
        
        # 🔥🔥 예외 감지 강화 변수
        self.last_successful_alert = datetime.now()
        self.min_alert_interval = timedelta(minutes=15)  # 최소 15분마다 하나는 알림
        self.emergency_alert_enabled = True
        
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
        """클라이언트 초기화 - 개선된 버전"""
        try:
            # Bitget 클라이언트
            self.bitget_client = BitgetClient(self.config)
            self.logger.info("✅ Bitget 클라이언트 초기화 완료")
            
            # Telegram 봇
            self.telegram_bot = TelegramBot(self.config)
            self.logger.info("✅ Telegram 봇 초기화 완료")
            
            # Gate.io 클라이언트 (미러 모드일 때만) - 개선된 로직
            self.gate_client = None
            self.mirror_trading = None
            
            # 미러 트레이딩 활성화 조건 체크
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
                    
                    self.logger.info("🔄 미러 트레이딩 시스템 생성 중...")
                    self.mirror_trading = MirrorTradingSystem(
                        self.config,
                        self.bitget_client,
                        self.gate_client,
                        self.telegram_bot
                    )
                    self.logger.info("✅ Gate.io 클라이언트 및 미러 트레이딩 초기화 완료")
                    
                except Exception as e:
                    self.logger.error(f"❌ 미러 트레이딩 초기화 실패: {e}")
                    self.logger.error(f"상세 오류: {traceback.format_exc()}")
                    self.mirror_mode = False
            else:
                self.logger.info("📊 분석 전용 모드로 실행")
                    
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
            
            # 🔥🔥 예외 감지기 - 강화된 필터링 적용
            self.exception_detector = ExceptionDetector(
                bitget_client=self.bitget_client,
                telegram_bot=self.telegram_bot
            )
            self.logger.info("✅ 예외 감지기 초기화 완료 - 크리티컬 뉴스 필터링 강화")
            
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
        
        # 🔥🔥 예외 감지 (3분마다로 단축)
        self.scheduler.add_job(
            func=self.check_exceptions,
            trigger="interval",
            minutes=3,
            timezone=timezone,
            id="exception_check",
            replace_existing=True
        )
        self.logger.info("📅 예외 감지 스케줄 등록: 3분마다")
        
        # 🔥🔥 급속 변동 감지 (1분마다로 단축)
        self.scheduler.add_job(
            func=self.rapid_exception_check,
            trigger="interval",
            minutes=1,
            timezone=timezone,
            id="rapid_exception_check",
            replace_existing=True
        )
        self.logger.info("📅 급속 변동 감지 스케줄 등록: 1분마다")
        
        # 🔥🔥 강제 예외 체크 (10분마다)
        self.scheduler.add_job(
            func=self.force_exception_check,
            trigger="interval",
            minutes=10,
            timezone=timezone,
            id="force_exception_check",
            replace_existing=True
        )
        self.logger.info("📅 강제 예외 체크 스케줄 등록: 10분마다")
        
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
    
    async def force_exception_check(self):
        """🔥🔥 강제 예외 체크 - 너무 오랫동안 알림이 없으면 강제 생성"""
        try:
            current_time = datetime.now()
            time_since_last = current_time - self.last_successful_alert
            
            # 30분 이상 알림이 없으면 강제로 체크
            if time_since_last > timedelta(minutes=30):
                self.logger.warning(f"⚠️ {time_since_last}동안 예외 알림이 없음 - 강제 체크 시작")
                
                # 1. 데이터 수집기 버퍼 강제 체크
                await self.force_check_data_collector()
                
                # 2. 시장 데이터 기반 예외 생성
                await self.force_generate_market_exception()
                
                # 3. 뉴스 기반 예외 생성
                await self.force_generate_news_exception()
                
                self.last_successful_alert = current_time
                self.exception_stats['forced_alerts'] += 1
                
                self.logger.info("🔥 강제 예외 체크 완료")
            
        except Exception as e:
            self.logger.error(f"❌ 강제 예외 체크 실패: {e}")
    
    async def force_check_data_collector(self):
        """🔥🔥 데이터 수집기 버퍼 강제 체크"""
        try:
            if not self.data_collector:
                return
            
            # 이벤트 버퍼에 뭔가 있는지 확인
            buffer_size = len(self.data_collector.events_buffer)
            self.logger.info(f"📊 데이터 수집기 이벤트 버퍼: {buffer_size}개")
            
            # 버퍼가 비어있으면 강제로 이벤트 생성 시도
            if buffer_size == 0:
                # 가격 데이터 기반 이벤트 생성
                if self.bitget_client:
                    ticker = await self.bitget_client.get_ticker('BTCUSDT')
                    if ticker:
                        current_price = float(ticker.get('last', 0))
                        change_24h = float(ticker.get('changeUtc', 0))
                        
                        if current_price > 0:
                            # 시장 상태 이벤트 생성
                            event = {
                                'type': 'market_status',
                                'title': f'Bitcoin Market Status Update',
                                'title_ko': f'비트코인 시장 상태 업데이트',
                                'description': f'현재 가격: ${current_price:,.0f}, 24시간 변동: {change_24h*100:+.2f}%',
                                'timestamp': datetime.now(),
                                'severity': 'medium',
                                'impact': '📊 시장 현황',
                                'expected_change': '지속적인 모니터링 중',
                                'source': 'Market Monitor',
                                'category': 'market_update',
                                'weight': 6
                            }
                            
                            self.data_collector.events_buffer.append(event)
                            self.logger.info(f"🔥 강제 시장 상태 이벤트 생성: ${current_price:,.0f}")
            
            # 뉴스 수집기 상태 체크
            if hasattr(self.data_collector, 'news_core') and self.data_collector.news_core:
                news_buffer_size = len(self.data_collector.news_core.news_buffer) if self.data_collector.news_core.news_buffer else 0
                self.logger.info(f"📰 뉴스 버퍼: {news_buffer_size}개")
                
                # 뉴스가 충분히 수집되고 있는지 체크
                if news_buffer_size < 5:
                    self.logger.warning("⚠️ 뉴스 수집이 부족함")
            
        except Exception as e:
            self.logger.error(f"❌ 데이터 수집기 강제 체크 실패: {e}")
    
    async def force_generate_market_exception(self):
        """🔥🔥 시장 데이터 기반 강제 예외 생성"""
        try:
            if not self.bitget_client:
                return
            
            # 현재 시장 데이터 조회
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            if not ticker:
                return
            
            current_price = float(ticker.get('last', 0))
            change_24h = float(ticker.get('changeUtc', 0))
            volume_24h = float(ticker.get('baseVolume', 0))
            
            if current_price <= 0:
                return
            
            # 강제로 이벤트 생성 (낮은 임계값 사용)
            if abs(change_24h) >= 0.005:  # 0.5% 이상이면 알림
                event = {
                    'type': 'forced_price_alert',
                    'title': f"BTC Price Movement Alert",
                    'title_ko': f"비트코인 가격 움직임 알림",
                    'description': f"24시간 내 {abs(change_24h*100):.2f}% {'상승' if change_24h > 0 else '하락'} (${current_price:,.0f})",
                    'timestamp': datetime.now(),
                    'severity': 'medium',
                    'impact': f"{'📈 상승세' if change_24h > 0 else '📉 하락세'}",
                    'expected_change': f"단기 {'상승' if change_24h > 0 else '하락'} 모멘텀",
                    'source': 'Forced Market Check',
                    'category': 'forced_alert',
                    'weight': 7,
                    'metadata': {
                        'price': current_price,
                        'change_24h': change_24h,
                        'volume_24h': volume_24h
                    }
                }
                
                self.data_collector.events_buffer.append(event)
                self.logger.warning(f"🔥 강제 가격 알림 생성: {abs(change_24h*100):.2f}% (${current_price:,.0f})")
            
        except Exception as e:
            self.logger.error(f"❌ 강제 시장 예외 생성 실패: {e}")
    
    async def force_generate_news_exception(self):
        """🔥🔥 뉴스 기반 강제 예외 생성"""
        try:
            if not hasattr(self.data_collector, 'news_core') or not self.data_collector.news_core:
                return
            
            # 최근 뉴스에서 비트코인 관련 뉴스 찾기
            recent_news = self.data_collector.news_core.news_buffer[-20:] if self.data_collector.news_core.news_buffer else []
            
            if not recent_news:
                # 뉴스가 없으면 기본 이벤트 생성
                event = {
                    'type': 'system_monitoring',
                    'title': 'Bitcoin News Monitoring Active',
                    'title_ko': '비트코인 뉴스 모니터링 활성화',
                    'description': '시스템이 실시간으로 비트코인 관련 뉴스를 모니터링하고 있습니다.',
                    'timestamp': datetime.now(),
                    'severity': 'low',
                    'impact': '📊 모니터링 중',
                    'expected_change': '지속적인 뉴스 추적',
                    'source': 'News Monitor',
                    'category': 'system_status',
                    'weight': 5
                }
                
                self.data_collector.events_buffer.append(event)
                self.logger.info("📊 뉴스 모니터링 상태 이벤트 생성")
                return
            
            # 비트코인 관련 뉴스 필터링
            bitcoin_news = []
            for article in recent_news:
                content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
                if any(word in content for word in ['bitcoin', 'btc', 'crypto', 'fed', 'rate', 'etf', 'regulation']):
                    bitcoin_news.append(article)
            
            if bitcoin_news:
                # 가장 최근 또는 가중치가 높은 뉴스 선택
                best_news = max(bitcoin_news, key=lambda x: (x.get('weight', 0), x.get('published_at', '')))
                
                event = {
                    'type': 'forced_news_alert',
                    'title': best_news.get('title', ''),
                    'title_ko': best_news.get('title', ''),
                    'description': best_news.get('description', '')[:800],
                    'timestamp': datetime.now(),
                    'severity': 'medium',
                    'impact': '📰 뉴스 주목',
                    'expected_change': '시장 반응 관찰 필요',
                    'source': f"Forced News ({best_news.get('source', 'Unknown')})",
                    'category': 'forced_news',
                    'weight': min(best_news.get('weight', 5) + 2, 9),  # 강제 생성이므로 가중치 약간 상승
                    'url': best_news.get('url', '')
                }
                
                self.data_collector.events_buffer.append(event)
                self.logger.warning(f"🔥 강제 뉴스 알림 생성: {event['title'][:50]}...")
            
        except Exception as e:
            self.logger.error(f"❌ 강제 뉴스 예외 생성 실패: {e}")
    
    async def rapid_exception_check(self):
        """급속 변동 감지 - 1분마다 실행"""
        try:
            self.logger.debug("급속 변동 감지 시작")
            
            # 단기 변동성 체크
            try:
                anomalies = await self.exception_detector.detect_all_anomalies()
                
                for anomaly in anomalies:
                    if anomaly.get('type') in ['short_term_volatility', 'rapid_price_change']:
                        self.exception_stats['short_term_alerts'] += 1
                        self.exception_stats['total_detected'] += 1
                        self.last_successful_alert = datetime.now()  # 🔥🔥 마지막 성공 시간 업데이트
                        self.logger.warning(f"급속 변동 감지: {anomaly}")
                        await self.exception_detector.send_alert(anomaly)
                    
            except Exception as e:
                self.logger.error(f"급속 변동 체크 오류: {e}")
                
        except Exception as e:
            self.logger.error(f"급속 변동 감지 실패: {str(e)}")
    
    async def check_exceptions(self):
        """🔥🔥 예외 상황 감지 - 크리티컬 뉴스 필터링 강화"""
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
                self.last_successful_alert = datetime.now()  # 🔥🔥 마지막 성공 시간 업데이트
                
                self.logger.warning(f"이상 징후 감지: {anomaly}")
                await self.exception_detector.send_alert(anomaly)
            
            # 🔥🔥 데이터 수집기의 이벤트 확인 (뉴스) - 크리티컬 필터링 강화
            try:
                critical_events = []
                important_events = []
                
                # 모든 이벤트 수집 (critical과 important 모두)
                for event in self.data_collector.events_buffer:
                    try:
                        severity = None
                        if hasattr(event, 'severity'):
                            severity = event.severity.value if hasattr(event.severity, 'value') else event.severity
                        elif isinstance(event, dict):
                            severity = event.get('severity')
                        
                        if severity in ['critical', 'high']:
                            critical_events.append(event)
                        elif severity in ['medium', 'important']:
                            important_events.append(event)
                    except Exception as e:
                        self.logger.error(f"이벤트 처리 오류: {e}")
                        continue
                
                # 🔥🔥 크리티컬 이벤트 처리 (강화된 필터링)
                for event in critical_events[:5]:
                    await self._process_critical_event_with_filtering(event)
                
                # 크리티컬 이벤트가 없으면 중요 이벤트도 처리 (최대 3개)
                if not critical_events and important_events:
                    for event in important_events[:3]:
                        await self._process_important_event(event)
                
                # 전혀 이벤트가 없으면 강제로 상태 확인
                if not critical_events and not important_events:
                    current_time = datetime.now()
                    time_since_last = current_time - self.last_successful_alert
                    
                    # 20분 이상 알림이 없으면 강제 체크
                    if time_since_last > timedelta(minutes=20):
                        self.logger.warning(f"⚠️ {time_since_last}동안 이벤트가 없음 - 시스템 상태 확인")
                        await self.force_check_data_collector()
                
                # 버퍼 클리어 (처리된 이벤트 제거)
                self.data_collector.events_buffer = []
                
            except Exception as e:
                self.logger.error(f"이벤트 처리 중 오류: {e}")
            
            # 미러 트레이딩 상태 체크 (활성화된 경우)
            if self.mirror_mode and self.mirror_trading:
                await self._check_mirror_health()
                
        except Exception as e:
            self.logger.error(f"예외 감지 실패: {str(e)}")
            self.logger.debug(traceback.format_exc())
    
    async def _process_critical_event_with_filtering(self, event):
        """🔥🔥 크리티컬 이벤트 처리 - 강화된 필터링 적용"""
        try:
            if hasattr(event, '__dict__'):
                event_data = event.__dict__
            else:
                event_data = event
            
            # 🔥🔥 크리티컬 뉴스 여부 재검증
            if event_data.get('type') in ['critical_news', 'forced_news_alert']:
                # ExceptionDetector의 강화된 필터링 적용
                if not self.exception_detector._is_critical_bitcoin_news(event_data):
                    self.logger.info(f"🔄 크리티컬 뉴스 기준 미달로 처리 취소: {event_data.get('title', '')[:50]}...")
                    self.exception_stats['critical_news_filtered'] += 1
                    return
                
                # 예상 가격 영향도 검증
                expected_impact = self.exception_detector._calculate_expected_price_impact(event_data)
                if expected_impact < 0.3:  # 0.3% 미만이면 제외
                    self.logger.info(f"🔄 예상 가격 영향도 미달로 처리 취소: {expected_impact:.1f}%")
                    self.exception_stats['critical_news_filtered'] += 1
                    return
                
                # 검증 통과한 크리티컬 뉴스
                self.exception_stats['critical_news_processed'] += 1
                event_data['expected_impact'] = expected_impact
            
            # 비트코인 관련성 체크
            impact = event_data.get('impact', '')
            if '무관' in impact or '알트코인' in impact:
                self.logger.info(f"🔄 비트코인 무관 뉴스 스킵: {event_data.get('title', '')[:50]}...")
                return
            
            # 뉴스 이벤트 통계
            if event_data.get('type') in ['critical_news', 'forced_news_alert', 'forced_price_alert']:
                self.exception_stats['news_alerts'] += 1
                self.exception_stats['total_detected'] += 1
                self.last_successful_alert = datetime.now()  # 🔥🔥 마지막 성공 시간 업데이트
            
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
            if report and len(report.strip()) > 10:  # 빈 리포트 방지
                await self.telegram_bot.send_message(report, parse_mode='HTML')
                self.logger.info(f"✅ 크리티컬 알림 전송: {event_data.get('title_ko', event_data.get('title', 'Unknown'))[:50]}...")
            else:
                self.logger.warning(f"❌ 빈 리포트 생성으로 전송 취소: {event_data.get('title', '')[:50]}...")
            
        except Exception as e:
            self.logger.error(f"크리티컬 이벤트 처리 실패: {e}")
    
    async def _process_important_event(self, event):
        """중요 이벤트 처리 (크리티컬보다 간소화)"""
        try:
            if hasattr(event, '__dict__'):
                event_data = event.__dict__
            else:
                event_data = event
            
            # 간단한 알림 메시지 생성
            title = event_data.get('title_ko', event_data.get('title', ''))
            description = event_data.get('description', '')
            impact = event_data.get('impact', '📊 시장 현황')
            
            simple_message = f"""<b>📊 중요 알림</b>

<b>제목:</b> {title[:100]}

<b>내용:</b> {description[:300]}

<b>영향:</b> {impact}

<b>시간:</b> {datetime.now().strftime('%H:%M')}"""
            
            await self.telegram_bot.send_message(simple_message, parse_mode='HTML')
            
            # 통계 업데이트
            self.exception_stats['news_alerts'] += 1
            self.exception_stats['total_detected'] += 1
            self.last_successful_alert = datetime.now()
            
            self.logger.info(f"📊 중요 알림 전송: {title[:50]}...")
            
        except Exception as e:
            self.logger.error(f"중요 이벤트 처리 실패: {e}")
    
    async def exception_stats_report(self):
        """예외 감지 통계 리포트 - 크리티컬 뉴스 필터링 통계 포함"""
        try:
            current_time = datetime.now()
            last_reset = datetime.fromisoformat(self.exception_stats['last_reset'])
            time_since_reset = current_time - last_reset
            hours_since_reset = time_since_reset.total_seconds() / 3600
            
            if hours_since_reset < 1:
                return
            
            total = self.exception_stats['total_detected']
            forced = self.exception_stats['forced_alerts']
            critical_processed = self.exception_stats['critical_news_processed']
            critical_filtered = self.exception_stats['critical_news_filtered']
            
            # 시간당 평균 계산
            hourly_avg = total / hours_since_reset if hours_since_reset > 0 else 0
            
            # 필터링 효율성 계산
            total_critical_attempts = critical_processed + critical_filtered
            filter_efficiency = (critical_filtered / total_critical_attempts * 100) if total_critical_attempts > 0 else 0
            
            report = f"""<b>📊 예외 감지 통계 리포트</b>
🕐 {current_time.strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━

<b>📈 지난 {hours_since_reset:.1f}시간 동안:</b>
- 총 감지: <b>{total}건</b>
- 시간당 평균: <b>{hourly_avg:.1f}건</b>
- 강제 생성: <b>{forced}건</b> ({forced/max(total,1)*100:.0f}%)

<b>🔥 크리티컬 뉴스 필터링:</b>
- 처리됨: <b>{critical_processed}건</b>
- 필터됨: <b>{critical_filtered}건</b>
- 필터 효율: <b>{filter_efficiency:.0f}%</b>
- 총 시도: <b>{total_critical_attempts}건</b>

<b>📋 카테고리별 감지:</b>
- 🚨 중요 뉴스: <b>{self.exception_stats['news_alerts']}건</b> ({self.exception_stats['news_alerts']/max(total,1)*100:.0f}%)
- 📊 가격 변동: <b>{self.exception_stats['price_alerts']}건</b> ({self.exception_stats['price_alerts']/max(total,1)*100:.0f}%)
- 📈 거래량 급증: <b>{self.exception_stats['volume_alerts']}건</b> ({self.exception_stats['volume_alerts']/max(total,1)*100:.0f}%)
- 💰 펀딩비 이상: <b>{self.exception_stats['funding_alerts']}건</b> ({self.exception_stats['funding_alerts']/max(total,1)*100:.0f}%)
- ⚡ 단기 급변동: <b>{self.exception_stats['short_term_alerts']}건</b> ({self.exception_stats['short_term_alerts']/max(total,1)*100:.0f}%)

<b>🔧 시스템 상태:</b>
- 마지막 알림: {(current_time - self.last_successful_alert).total_seconds() / 60:.0f}분 전
- 감지 임계값: 높음 (정확성 우선)
- 뉴스 필터링: 강화됨
- 강제 체크: 활성화

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
                'critical_news_processed': 0,
                'critical_news_filtered': 0,
                'forced_alerts': 0,
                'last_reset': current_time.isoformat()
            }
            
            self.logger.info(f"예외 감지 통계 리포트 전송 완료 - 총 {total}건 (필터링 {filter_efficiency:.0f}%)")
            
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
        """통계 명령 처리 - 크리티컬 뉴스 필터링 통계 포함"""
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
            
            # 🔥🔥 마지막 알림 시간 계산
            time_since_last_alert = current_time - self.last_successful_alert
            minutes_since_alert = int(time_since_last_alert.total_seconds() / 60)
            
            # 🔥🔥 크리티컬 뉴스 필터링 통계
            critical_processed = self.exception_stats['critical_news_processed']
            critical_filtered = self.exception_stats['critical_news_filtered']
            total_critical_attempts = critical_processed + critical_filtered
            filter_efficiency = (critical_filtered / total_critical_attempts * 100) if total_critical_attempts > 0 else 0
            
            stats_msg = f"""<b>📊 시스템 실시간 통계</b>
🕐 {current_time.strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━

<b>⏱️ 시스템 상태:</b>
- 가동 시간: <b>{hours}시간 {minutes}분</b>
- 총 명령 처리: <b>{total_commands}건</b>
- 오류 발생: <b>{self.command_stats['errors']}건</b>
- 마지막 알림: <b>{minutes_since_alert}분 전</b>

<b>🚨 예외 감지 성과 (최근 {stats_hours:.1f}시간):</b>
- 총 감지: <b>{total_exceptions}건</b>
- 시간당 평균: <b>{total_exceptions/max(stats_hours, 0.1):.1f}건</b>
- 강제 생성: <b>{self.exception_stats['forced_alerts']}건</b>

<b>🔥 크리티컬 뉴스 필터링:</b>
- 처리됨: <b>{critical_processed}건</b>
- 필터됨: <b>{critical_filtered}건</b>
- 필터 효율: <b>{filter_efficiency:.0f}%</b>
- 정확도 우선 모드 활성화

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
- 뉴스 필터링: 강화됨 (정확성 우선)
- 강제 체크: 10분마다

━━━━━━━━━━━━━━━━━━━
⚡ 비트코인 전용 고정밀 필터링 시스템"""
            
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
        """미러 트레이딩 상태 확인 - 개선된 버전"""
        try:
            self.command_stats['mirror'] += 1
            
            if not self.mirror_mode or not self.mirror_trading:
                # 상세한 비활성화 이유 제공
                reasons = []
                
                if not self.mirror_mode:
                    reasons.append("MIRROR_TRADING_MODE 환경변수가 'true'로 설정되지 않음")
                
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
                    f"1. MIRROR_TRADING_MODE=true 환경변수 설정 ✓\n"
                    f"2. GATE_API_KEY 환경변수 설정 {'✓' if gate_api_key else '❌'}\n"
                    f"3. GATE_API_SECRET 환경변수 설정 {'✓' if gate_api_secret else '❌'}\n"
                    f"4. 시스템 재시작\n\n"
                    f"🔧 현재 환경변수 상태:\n"
                    f"• MIRROR_TRADING_MODE: {os.getenv('MIRROR_TRADING_MODE', 'not_set')}\n"
                    f"• 미러 트레이딩 모듈: {'사용 가능' if MIRROR_TRADING_AVAILABLE else '사용 불가'}",
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
- 예약 주문도 동일 비율 복제
- 실시간 가격 조정

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
            
            additional_info += f"• 예외 감지: 3분마다 자동 실행\n"
            additional_info += f"• 급속 변동 감지: 1분마다 자동 실행\n"
            additional_info += f"• 강제 예외 체크: 10분마다\n"
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
                'critical_news_processed': self.exception_stats['critical_news_processed'],
                'critical_news_filtered': self.exception_stats['critical_news_filtered'],
                'forced_alerts': self.exception_stats['forced_alerts'],
                'last_reset': self.exception_stats['last_reset']
            }
            
            # 메모리 사용량 체크
            import psutil
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            health_status['memory_mb'] = memory_info.rss / 1024 / 1024
            
            # 명령어 통계
            health_status['command_stats'] = self.command_stats.copy()
            
            # 🔥🔥 마지막 알림 시간 체크
            time_since_last_alert = datetime.now() - self.last_successful_alert
            health_status['minutes_since_last_alert'] = int(time_since_last_alert.total_seconds() / 60)
            
            # 문제가 있으면 알림
            if health_status['errors'] or health_status['minutes_since_last_alert'] > 60:
                error_msg = "<b>⚠️ 시스템 건강 체크 경고</b>\n"
                
                if health_status['errors']:
                    for error in health_status['errors']:
                        error_msg += f"• {error}\n"
                
                if health_status['minutes_since_last_alert'] > 60:
                    error_msg += f"• 마지막 알림: {health_status['minutes_since_last_alert']}분 전\n"
                
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
            critical_processed = self.exception_stats['critical_news_processed']
            critical_filtered = self.exception_stats['critical_news_filtered']
            total_critical_attempts = critical_processed + critical_filtered
            filter_efficiency = (critical_filtered / total_critical_attempts * 100) if total_critical_attempts > 0 else 0
            
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
- 강제 생성: {self.exception_stats['forced_alerts']}건

<b>🔥 크리티컬 뉴스 필터링 성과:</b>
- 처리됨: <b>{critical_processed}건</b>
- 필터됨: <b>{critical_filtered}건</b>
- 필터 효율: <b>{filter_efficiency:.0f}%</b>
- 정확도 우선 모드로 노이즈 제거

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
- 예외 감지: 3분마다
- 급속 변동: 1분마다
- 강제 체크: 10분마다
- 뉴스 수집: 15초마다
- 가격 임계값: {self.exception_detector.PRICE_CHANGE_THRESHOLD}%
- 거래량 임계값: {self.exception_detector.VOLUME_SPIKE_THRESHOLD}배
- 뉴스 필터링: 강화됨 (크리티컬 전용)

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
                'critical_news_processed': 0,
                'critical_news_filtered': 0,
                'forced_alerts': 0,
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
            
            welcome_message += f"""
<b>🔔 자동 기능:</b>
- 정기 리포트: 09:00, 13:00, 18:00, 23:00
- 예외 감지: 3분마다
- 급속 변동: 1분마다
- 강제 체크: 10분마다
- 뉴스 수집: 15초마다 (RSS)
- 시스템 체크: 30분마다"""
            
            if self.ml_mode:
                welcome_message += "\n• ML 예측 검증: 30분마다"
            
            welcome_message += f"""

<b>⚡ 실시간 알림 (비트코인 전용):</b>
- 가격 급변동 (≥{self.exception_detector.PRICE_CHANGE_THRESHOLD}%)
- 단기 급변동 (1분 내 ≥{self.exception_detector.short_term_threshold}%)
- 비트코인 크리티컬 뉴스 (강화된 필터링)
- 펀딩비 이상 (≥{self.exception_detector.FUNDING_RATE_THRESHOLD*100:.1f}%)
- 거래량 급증 (≥{self.exception_detector.VOLUME_SPIKE_THRESHOLD}배)
- 강제 알림 (무응답 방지)
"""
            
            if self.mirror_mode:
                welcome_message += """
<b>🔄 미러 트레이딩:</b>
- 비트겟 → 게이트 자동 복제
- 총 자산 대비 동일 비율
- 예약 주문도 동일 비율 복제
- 실시간 가격 조정
"""
            
            if self.ml_mode:
                welcome_message += f"""
<b>🤖 ML 예측 시스템:</b>
- 과거 데이터 학습
- 실시간 예측
- 자동 성능 개선
"""
            
            # 시스템 상태 추가
            uptime = datetime.now() - self.startup_time
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            
            total_exceptions = self.exception_stats['total_detected']
            minutes_since_alert = int((datetime.now() - self.last_successful_alert).total_seconds() / 60)
            
            # 🔥🔥 크리티컬 뉴스 필터링 통계 추가
            critical_processed = self.exception_stats['critical_news_processed']
            critical_filtered = self.exception_stats['critical_news_filtered']
            total_critical_attempts = critical_processed + critical_filtered
            filter_efficiency = (critical_filtered / total_critical_attempts * 100) if total_critical_attempts > 0 else 0
            
            welcome_message += f"""
<b>📊 시스템 상태:</b>
- 가동 시간: {hours}시간 {minutes}분
- 오늘 명령 처리: {sum(self.command_stats.values())}건
- 오늘 예외 감지: <b>{total_exceptions}건</b>
- 마지막 알림: {minutes_since_alert}분 전
- 크리티컬 뉴스 필터링: <b>{filter_efficiency:.0f}%</b> 효율
- 활성 서비스: {'미러+분석' if self.mirror_mode else '분석'}{'+ ML' if self.ml_mode else ''}

📈 정확한 비트코인 분석을 제공합니다.
🔥 크리티컬 뉴스만 엄선하여 전달합니다.

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
            self.logger.info("시스템 시작 프로세스 개시 - 비트코인 전용 + 크리티컬 뉴스 필터링 강화")
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
            
            mode_text = "미러 트레이딩" if self.mirror_mode else "분석 전용"
            if self.ml_mode:
                mode_text += " + ML 예측"
            
            self.logger.info(f"✅ 비트코인 예측 시스템 시작 완료 (모드: {mode_text})")
            
            # 시작 메시지 전송 - 간소화
            startup_msg = f"""<b>🚀 비트코인 예측 시스템이 시작되었습니다!</b>

<b>📊 운영 모드:</b> {mode_text}
<b>🕐 시작 시각:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>🔥 버전:</b> 2.5 - 비트코인 전용 (크리티컬 뉴스 필터링 강화)
"""
            
            if self.mirror_mode:
                startup_msg += """
<b>🔄 미러 트레이딩 활성화:</b>
- 비트겟 → 게이트 자동 복제
- 총 자산 대비 동일 비율 적용
- 예약 주문도 동일 비율 복제
- 실시간 가격 조정
"""
            
            if self.ml_mode:
                startup_msg += f"""
<b>🤖 ML 예측 시스템 활성화:</b>
- 실시간 예측 및 검증
- 자동 학습 및 개선
"""
            
            startup_msg += f"""
<b>⚡ 비트코인 전용 기능 (강화):</b>
- 예외 감지: 3분마다
- 급속 변동: 1분마다
- 강제 체크: 10분마다 (무응답 방지)
- 뉴스 수집: 15초마다 (RSS)
- 크리티컬 뉴스 필터링: 강화됨 ✨
- 가격 임계값: {self.exception_detector.PRICE_CHANGE_THRESHOLD}%
- 거래량 임계값: {self.exception_detector.VOLUME_SPIKE_THRESHOLD}배

<b>🔥 크리티컬 뉴스 필터링 시스템:</b>
- ETF, Fed 금리, 기업 직접 투자만 엄선
- 구조화 상품, 의견/예측 글 자동 제외
- 비트코인 직접 영향 뉴스만 전달
- 가격 영향도 0.3% 이상만 처리

<b>📌 활성 기능:</b>
- 실시간 가격 모니터링
- 비트코인 전용 뉴스 추적 (엄격한 필터링)
- 기술적 분석
- GPT 기반 예측
- 자동 리포트 생성 (9시, 13시, 18시, 23시)
- 강제 알림 시스템 (30분 무응답 시)"""

            if self.mirror_mode:
                startup_msg += """
- 완전한 달러 비율 복제
- 예약 주문 실시간 복제"""

            startup_msg += """

이제 정말 중요한 비트코인 뉴스만 받아보실 수 있습니다!
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
                critical_processed = self.exception_stats['critical_news_processed']
                critical_filtered = self.exception_stats['critical_news_filtered']
                filter_efficiency = (critical_filtered / (critical_processed + critical_filtered) * 100) if (critical_processed + critical_filtered) > 0 else 0
                
                shutdown_msg = f"""<b>🛑 시스템 종료 중...</b>

<b>⏱️ 총 가동 시간:</b> {hours}시간 {minutes}분
<b>📊 처리된 명령:</b> {sum(self.command_stats.values())}건
<b>🚨 감지된 예외:</b> {total_exceptions}건
<b>🔥 크리티컬 뉴스:</b> 처리 {critical_processed}건, 필터링 {critical_filtered}건
<b>📈 필터링 효율:</b> {filter_efficiency:.0f}% (노이즈 제거)
<b>🔥 강제 생성:</b> {self.exception_stats['forced_alerts']}건
<b>❌ 발생한 오류:</b> {self.command_stats['errors']}건"""
                
                if self.ml_mode and self.ml_predictor:
                    stats = self.ml_predictor.get_stats()
                    shutdown_msg += f"""
<b>🤖 ML 예측 성능:</b>
- 총 예측: {stats['total_predictions']}건
- 정확도: {stats['direction_accuracy']}"""
                
                shutdown_msg += "\n\n크리티컬 뉴스 필터링 시스템이 안전하게 종료됩니다."
                
                if self.mirror_mode:
                    shutdown_msg += "\n미러 트레이딩도 함께 종료됩니다."
                
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
            self.logger.info("✅ 비트코인 전용 + 크리티컬 뉴스 필터링 시스템이 안전하게 종료되었습니다")
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"시스템 종료 중 오류: {str(e)}")
            self.logger.debug(traceback.format_exc())

async def main():
    """메인 함수"""
    try:
        print("\n" + "=" * 50)
        print("🚀 비트코인 예측 시스템 v2.5 - 크리티컬 뉴스 필터링 강화")
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
