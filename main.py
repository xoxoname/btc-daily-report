import os
import asyncio
import logging
from datetime import datetime
import traceback
from typing import Dict  # 추가된 import
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
import hashlib
import re

from config import Config
from telegram_bot import TelegramBot
from bitget_client import BitgetClient
from analysis_engine import AnalysisEngine
from exception_detector import ExceptionDetector
from data_collector import RealTimeDataCollector
from trading_indicators import AdvancedTradingIndicators
from report_generators import ReportGeneratorManager  # 🆕 통합 리포트 생성기
from gateio_client import GateioClient  # 새로 추가
from mirror_trading import MirrorTradingSystem  # 새로 추가

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
        
        # Gate.io 클라이언트 (미러 트레이딩 활성화 시)
        self.gateio_client = None
        self.mirror_trading = None
        if self.config.ENABLE_MIRROR_TRADING:
            self.gateio_client = GateioClient(self.config)
            self.mirror_trading = MirrorTradingSystem(
                self.bitget_client, 
                self.gateio_client, 
                self.config
            )
            self.logger.info("🔄 미러 트레이딩 시스템 초기화 완료")
        
        # 새로운 컴포넌트 추가
        self.data_collector = RealTimeDataCollector(self.config)
        self.data_collector.set_bitget_client(self.bitget_client)
        
        self.indicator_system = AdvancedTradingIndicators()
        
        # 🆕 새로운 통합 리포트 생성기
        self.report_manager = ReportGeneratorManager(
            self.config,
            self.data_collector,
            self.indicator_system
        )
        # Bitget 클라이언트를 리포트 매니저에 설정
        self.report_manager.set_bitget_client(self.bitget_client)
        
        # 기존 엔진 (분석용)
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
        
        # 처리된 예외 이벤트 해시 저장 (중복 방지)
        self.processed_exception_hashes = set()
        self.sent_exception_reports = {}  # 전송된 예외 리포트 추적
        self.exception_report_cooldown = 300  # 5분 쿨다운 (초)
        
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
    
    async def handle_natural_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """자연어 메시지 처리"""
        try:
            message = update.message.text.lower()
            
            # 수익 관련 질문
            if any(word in message for word in ['수익', '얼마', '벌었', '손익', '이익', '손실', 'profit']):
                await self.handle_profit_command(update, context)
            
            # 매수/매도 관련 질문
            elif any(word in message for word in ['매수', '매도', '사야', '팔아', '지금', '예측', 'buy', 'sell']):
                await self.handle_forecast_command(update, context)
            
            # 시장 상황 질문
            elif any(word in message for word in ['시장', '상황', '어때', '분석', 'market']):
                await self.handle_report_command(update, context)
            
            # 일정 관련 질문
            elif any(word in message for word in ['일정', '언제', '시간', 'schedule']):
                await self.handle_schedule_command(update, context)
            
            # 미러 트레이딩 관련
            elif any(word in message for word in ['미러', '동기화', 'mirror', 'sync']):
                await self.handle_mirror_status(update, context)
            
            # 도움말
            elif any(word in message for word in ['도움', '명령', 'help']):
                await self.handle_start_command(update, context)
            
            else:
                await update.message.reply_text(
                    "죄송합니다. 이해하지 못했습니다. 🤔\n"
                    "다음과 같이 질문해보세요:\n"
                    "• '오늘 수익은?'\n"
                    "• '지금 매수해도 돼?'\n"
                    "• '시장 상황 어때?'\n"
                    "• '다음 리포트 언제?'\n"
                    "• '미러 트레이딩 상태'\n\n"
                    "또는 /help 명령어로 전체 기능을 확인하세요."
                )
                
        except Exception as e:
            self.logger.error(f"자연어 처리 실패: {str(e)}")
            await update.message.reply_text("❌ 메시지 처리 중 오류가 발생했습니다.")
    
    async def handle_mirror_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """미러 트레이딩 상태 확인"""
        try:
            if not self.config.ENABLE_MIRROR_TRADING:
                await update.message.reply_text("⚠️ 미러 트레이딩이 비활성화되어 있습니다.")
                return
            
            # 현재 포지션 상태 확인
            bitget_positions = await self.bitget_client.get_positions('BTCUSDT')
            gateio_positions = await self.gateio_client.get_positions('usdt')
            
            status_message = "🔄 **미러 트레이딩 상태**\n\n"
            
            # Bitget 포지션
            status_message += "**Bitget 포지션:**\n"
            bitget_active = False
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    bitget_active = True
                    side = pos.get('holdSide', '')
                    size = float(pos.get('total', 0))
                    entry = float(pos.get('openPriceAvg', 0))
                    pnl = float(pos.get('unrealizedPL', 0))
                    status_message += f"• {side} {size:.4f} BTC @ ${entry:,.2f} (PnL: ${pnl:+,.2f})\n"
                    break
            
            if not bitget_active:
                status_message += "• 포지션 없음\n"
            
            # Gate.io 포지션
            status_message += "\n**Gate.io 포지션:**\n"
            gateio_active = False
            for pos in gateio_positions:
                if pos.get('contract') == 'BTC_USDT' and float(pos.get('size', 0)) != 0:
                    gateio_active = True
                    size = float(pos.get('size', 0))
                    side = 'LONG' if size > 0 else 'SHORT'
                    entry = float(pos.get('entry_price', 0))
                    pnl = float(pos.get('unrealised_pnl', 0))
                    status_message += f"• {side} {abs(size)}계약 @ ${entry:,.2f} (PnL: ${pnl:+,.2f})\n"
                    break
            
            if not gateio_active:
                status_message += "• 포지션 없음\n"
            
            # 동기화 상태
            status_message += f"\n**동기화 상태:** {'✅ 동기화됨' if (bitget_active == gateio_active) else '⚠️ 동기화 필요'}"
            status_message += f"\n**체크 간격:** {self.config.MIRROR_CHECK_INTERVAL}초"
            
            await update.message.reply_text(status_message, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"미러 상태 확인 실패: {str(e)}")
            await update.message.reply_text("❌ 미러 트레이딩 상태 확인 중 오류가 발생했습니다.")
    
    # 🆕 각 리포트 핸들러들이 이제 전담 생성기를 사용
    async def handle_report_command(self, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None):
        """리포트 명령 처리"""
        try:
            if update:
                await update.message.reply_text("📊 비트코인 분석 리포트를 생성중입니다...")
            else:
                await self.telegram_bot.send_message("📊 정기 비트코인 분석 리포트를 생성중입니다...")
            
            self.logger.info("정기 리포트 생성 시작")
            
            # 🆕 새로운 정기 리포트 생성기 사용
            report = await self.report_manager.generate_regular_report()
            
            # 메시지 전송
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
            
            # 🆕 새로운 예측 리포트 생성기 사용
            report = await self.report_manager.generate_forecast_report()
            
            await update.message.reply_text(report, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"예측 명령 처리 실패: {str(e)}")
            await update.message.reply_text("❌ 예측 분석 중 오류가 발생했습니다.")
    
    async def handle_profit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """수익 명령 처리"""
        try:
            await update.message.reply_text("💰 실시간 수익 현황을 조회중입니다...")
            
            # 🆕 새로운 수익 리포트 생성기 사용
            profit_report = await self.report_manager.generate_profit_report()
            
            # HTML 파싱 모드로 전송
            await update.message.reply_text(profit_report, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"수익 명령 처리 실패: {str(e)}")
            self.logger.debug(f"수익 조회 오류 상세: {traceback.format_exc()}")
            await update.message.reply_text("❌ 수익 조회 중 오류가 발생했습니다.")
    
    async def handle_schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """일정 명령 처리"""
        try:
            # 🆕 새로운 일정 리포트 생성기 사용
            schedule_report = await self.report_manager.generate_schedule_report()
            
            await update.message.reply_text(schedule_report, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"일정 명령 처리 실패: {str(e)}")
            await update.message.reply_text("❌ 일정 조회 중 오류가 발생했습니다.")
    
    def _is_critical_news(self, article: Dict) -> bool:
        """크리티컬 뉴스 판단 - 트럼프 관세 뉴스 포함"""
        # 제목과 설명 모두 체크
        content = (article.get('title', '') + ' ' + article.get('description', '') + ' ' + article.get('title_ko', '')).lower()
        
        # 제외 키워드 먼저 체크 (골드, 금 등)
        exclude_keywords = [
            'gold price', 'gold rises', 'gold falls', 'gold market',
            'oil price', 'oil market', 'commodity',
            'mining at home', '집에서 채굴', 'how to mine',
            'crypto news today', '오늘의 암호화폐 소식',
            'price prediction', '가격 예측'
        ]
        
        for exclude in exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 비트코인 관련성 체크
        bitcoin_related = ['bitcoin', 'btc', 'crypto', '비트코인', '암호화폐']
        has_bitcoin = any(keyword in content for keyword in bitcoin_related)
        
        # 트럼프 관세 뉴스는 비트코인 언급 없어도 중요
        if any(word in content for word in ['trump', '트럼프']):
            if any(word in content for word in ['tariff', 'court', 'blocks', '관세', '법원', '차단', 'federal']):
                return True
        
        # 나머지는 비트코인 관련성 필수
        if not has_bitcoin:
            return False
        
        # 기업 비트코인 구매 감지
        important_companies = [
            'tesla', 'microstrategy', 'square', 'block', 'paypal', 'mastercard', 'visa',
            'apple', 'google', 'amazon', 'meta', 'facebook', 'microsoft', 'netflix',
            'gamestop', 'gme', 'amc', 'blackrock', 'fidelity', 'jpmorgan', 'goldman',
            'samsung', 'lg', 'sk', 'kakao', 'naver', '삼성', '카카오', '네이버',
            'metaplanet', '메타플래닛'
        ]
        
        for company in important_companies:
            if company.lower() in content:
                # 비트코인 구매 관련 키워드 체크
                purchase_keywords = ['bought', 'buys', 'purchased', 'bitcoin purchase', 'bitcoin acquisition',
                                   '비트코인 구매', '비트코인 매입', '비트코인 투자', 'bitcoin', 'btc']
                if any(keyword in content for keyword in purchase_keywords):
                    # 금액이 포함된 경우 더 높은 신뢰도
                    if any(char in content for char in ['$', '달러', 'dollar', 'million', 'billion']):
                        return True
        
        # 기존 크리티컬 키워드 체크
        critical_keywords = [
            # 트럼프 추가
            'trump bitcoin', 'trump crypto', 'trump ban', 'trump announces', 'trump says bitcoin',
            'trump tariff', 'trump executive order', 'trump policy', 'trump federal',
            '트럼프 비트코인', '트럼프 암호화폐', '트럼프 규제', '트럼프 관세', '트럼프 정책',
            # 연준/금리
            'fed rate decision', 'fed raises', 'fed cuts', 'powell says', 'fomc decides', 'fed meeting',
            'interest rate hike', 'interest rate cut', 'monetary policy',
            '연준 금리', 'FOMC 결정', '파월 발언', '금리 인상', '금리 인하',
            # SEC
            'sec lawsuit bitcoin', 'sec sues', 'sec enforcement', 'sec charges bitcoin',
            'sec approves', 'sec rejects', 'sec bitcoin etf',
            'SEC 소송', 'SEC 규제', 'SEC 비트코인', 'SEC 승인', 'SEC 거부',
            # 규제/금지
            'china bans bitcoin', 'china crypto ban', 'government bans crypto', 'regulatory ban',
            'court blocks', 'federal court', 'supreme court crypto',
            '중국 비트코인 금지', '정부 규제', '암호화폐 금지', '법원 판결',
            # 시장 급변동
            'bitcoin crash', 'crypto crash', 'market crash', 'flash crash', 'bitcoin plunge',
            'bitcoin surge', 'bitcoin rally', 'bitcoin breaks',
            '비트코인 폭락', '암호화폐 급락', '시장 붕괴', '비트코인 급등',
            # ETF
            'bitcoin etf approved', 'bitcoin etf rejected', 'etf decision', 'etf filing',
            'ETF 승인', 'ETF 거부', 'ETF 결정',
            # 기업 구매
            'bought bitcoin', 'buys bitcoin', 'purchased bitcoin', 'bitcoin purchase', 'bitcoin acquisition',
            '비트코인 구매', '비트코인 매입', '비트코인 투자', '비트코인 보유',
            # 대량 거래
            'whale alert', 'large bitcoin transfer', 'bitcoin moved', 'btc transferred',
            'exchange inflow', 'exchange outflow',
            '고래 이동', '대량 이체', '비트코인 이동', '거래소 유입', '거래소 유출',
            # 해킹/보안
            'exchange hacked', 'bitcoin stolen', 'crypto hack', 'security breach',
            '거래소 해킹', '비트코인 도난', '보안 사고'
        ]
        
        for keyword in critical_keywords:
            if keyword.lower() in content:
                return True
        
        return False
    
    def _generate_event_hash(self, event: dict) -> str:
        """이벤트의 고유 해시 생성 - 더 강력한 중복 체크"""
        event_type = event.get('type', '')
        
        if event_type == 'critical_news':
            # 뉴스는 제목으로 해시 생성
            title = event.get('title', '').lower()
            # 숫자와 특수문자 제거
            clean_title = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title)
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()
            
            # 회사명 추출
            companies = ['gamestop', 'tesla', 'microstrategy', 'metaplanet', '게임스탑', '테슬라', '메타플래닛']
            found_companies = [c for c in companies if c in clean_title]
            
            # 키워드 추출
            keywords = ['bitcoin', 'btc', 'purchase', 'bought', 'buys', '구매', '매입', 'first', '첫']
            found_keywords = [k for k in keywords if k in clean_title]
            
            # 회사명과 키워드로 해시 생성
            if found_companies and found_keywords:
                hash_content = f"{','.join(sorted(found_companies))}_{','.join(sorted(found_keywords))}"
            else:
                hash_content = clean_title
            
            return hashlib.md5(f"event_{hash_content}".encode()).hexdigest()
        
        else:
            # 기타 이벤트는 전체 내용으로 해시
            content = f"{event_type}_{event.get('description', '')}_{event.get('severity', '')}"
            return hashlib.md5(content.encode()).hexdigest()
    
    def _is_duplicate_exception_report(self, event_hash: str) -> bool:
        """예외 리포트가 중복인지 확인 (시간 기반 쿨다운)"""
        current_time = datetime.now()
        
        # 오래된 리포트 정리
        for hash_key in list(self.sent_exception_reports.keys()):
            if (current_time - self.sent_exception_reports[hash_key]).total_seconds() > self.exception_report_cooldown:
                del self.sent_exception_reports[hash_key]
        
        # 중복 체크
        if event_hash in self.sent_exception_reports:
            time_diff = (current_time - self.sent_exception_reports[event_hash]).total_seconds()
            if time_diff < self.exception_report_cooldown:
                self.logger.info(f"🔄 예외 리포트 쿨다운 중: {event_hash} ({int(self.exception_report_cooldown - time_diff)}초 남음)")
                return True
        
        return False
    
    async def check_exceptions(self):
        """예외 상황 감지 - 강화된 중복 방지"""
        try:
            # 기존 예외 감지
            anomalies = await self.exception_detector.detect_all_anomalies()
            
            for anomaly in anomalies:
                # exception_detector의 send_alert가 이미 중복 체크를 하므로 그대로 사용
                await self.exception_detector.send_alert(anomaly)
            
            # 데이터 수집기의 이벤트 확인
            if self.data_collector and hasattr(self.data_collector, 'events_buffer'):
                # 이벤트 버퍼 복사본 생성 (동시성 문제 방지)
                events_to_process = list(self.data_collector.events_buffer)
                
                # 이벤트별로 그룹화 (유사한 이벤트 한번만 처리)
                event_groups = {}
                
                for event in events_to_process:
                    try:
                        # 비트코인 관련성 체크 - 트럼프 관세 뉴스도 포함
                        if hasattr(event, 'type') and event.type == 'critical_news':
                            if not self._is_critical_news(event.__dict__ if hasattr(event, '__dict__') else event):
                                continue
                        
                        # 이벤트 해시 생성
                        event_hash = self._generate_event_hash(event if isinstance(event, dict) else event.__dict__)
                        
                        # 이미 처리된 이벤트인지 확인
                        if event_hash in self.processed_exception_hashes:
                            continue
                        
                        # 예외 리포트 쿨다운 체크
                        if self._is_duplicate_exception_report(event_hash):
                            continue
                        
                        # 이벤트 심각도 확인
                        severity = None
                        if hasattr(event, 'severity'):
                            severity = event.severity.value if hasattr(event.severity, 'value') else str(event.severity)
                        elif isinstance(event, dict):
                            severity = event.get('severity', '')
                        
                        # 높은 심각도 이벤트만 처리
                        if severity in ['high', 'critical']:
                            # 이벤트 그룹에 추가
                            event_groups[event_hash] = event
                    
                    except Exception as e:
                        self.logger.error(f"이벤트 전처리 중 오류: {e}")
                        continue
                
                # 그룹화된 이벤트 처리 (한 번에 하나씩만)
                processed_count = 0
                max_reports_per_check = 2  # 한 번에 최대 2개까지만 처리
                
                for event_hash, event in event_groups.items():
                    if processed_count >= max_reports_per_check:
                        break
                    
                    try:
                        # 🆕 새로운 예외 리포트 생성기 사용
                        event_dict = event.__dict__ if hasattr(event, '__dict__') else event
                        
                        # 예외 리포트 생성 및 전송
                        report = await self.report_manager.generate_exception_report(event_dict)
                        
                        # 텔레그램 전송
                        success = await self._send_exception_report(report)
                        
                        if success:
                            # 성공적으로 전송된 경우만 처리된 것으로 기록
                            self.processed_exception_hashes.add(event_hash)
                            self.sent_exception_reports[event_hash] = datetime.now()
                            self.logger.info(f"✅ 예외 리포트 전송 완료: {event_hash}")
                            processed_count += 1
                        
                    except Exception as e:
                        self.logger.error(f"예외 리포트 처리 중 오류: {e}")
                        continue
                
                # 해시 세트가 너무 커지면 정리
                if len(self.processed_exception_hashes) > 1000:
                    # 가장 오래된 500개 제거
                    self.processed_exception_hashes = set(list(self.processed_exception_hashes)[-500:])
                
                # 처리된 이벤트 버퍼에서 제거
                processed_hashes = set()
                for event in self.data_collector.events_buffer:
                    event_hash = self._generate_event_hash(event if isinstance(event, dict) else event.__dict__)
                    if event_hash in self.processed_exception_hashes:
                        processed_hashes.add(event_hash)
                
                # 처리된 이벤트만 제거
                self.data_collector.events_buffer = [
                    event for event in self.data_collector.events_buffer
                    if self._generate_event_hash(event if isinstance(event, dict) else event.__dict__) 
                    not in processed_hashes
                ]
                
        except Exception as e:
            self.logger.error(f"예외 감지 실패: {str(e)}")
    
    async def _send_exception_report(self, report: str) -> bool:
        """예외 리포트 전송 (중복 체크 포함)"""
        try:
            # 리포트 내용으로 해시 생성
            report_lines = report.split('\n')
            
            # 제목과 원인에서 해시 생성
            cause_lines = []
            
            for i, line in enumerate(report_lines):
                if '급변 원인 요약' in line and i + 1 < len(report_lines):
                    # 원인 요약 부분 추출
                    j = i + 1
                    while j < len(report_lines) and not line.strip().startswith('━'):
                        if report_lines[j].strip():
                            cause_lines.append(report_lines[j].strip())
                        j += 1
                    break
            
            if cause_lines:
                # 원인 내용으로 해시 생성
                cause_text = ' '.join(cause_lines)
                # 숫자와 시간 제거하여 유사한 내용 감지
                clean_text = re.sub(r'[0-9:\-\s]+', ' ', cause_text)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                
                report_hash = hashlib.md5(clean_text.encode()).hexdigest()
                
                # 쿨다운 체크
                if self._is_duplicate_exception_report(report_hash):
                    return False
                
                # 전송
                await self.telegram_bot.send_message(report, parse_mode='Markdown')
                
                # 성공 시 해시 저장
                self.processed_exception_hashes.add(report_hash)
                self.sent_exception_reports[report_hash] = datetime.now()
                return True
            else:
                # 해시 생성 실패 시 그냥 전송
                await self.telegram_bot.send_message(report, parse_mode='Markdown')
                return True
                
        except Exception as e:
            self.logger.error(f"예외 리포트 전송 실패: {e}")
            return False
    
    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시작 명령 처리"""
        welcome_message = """🚀 비트코인 예측 시스템에 오신 것을 환영합니다!

📊 슬래시 명령어:
- /report - 전체 분석 리포트
- /forecast - 단기 예측 요약
- /profit - 실시간 수익 현황
- /schedule - 자동 일정 안내
- /mirror - 미러 트레이딩 상태

💬 자연어 질문 예시:
- "오늘 수익은?"
- "지금 매수해도 돼?"
- "시장 상황 어때?"
- "얼마 벌었어?"
- "미러 트레이딩 상태"

🔔 자동 리포트:
매일 09:00, 13:00, 18:00, 22:00

⚡ 실시간 알림:
가격 급변동, 뉴스 이벤트, 펀딩비 이상 등

"""
        
        if self.config.ENABLE_MIRROR_TRADING:
            welcome_message += """🔄 미러 트레이딩:
Bitget → Gate.io 자동 동기화 활성화

"""
        
        welcome_message += "📈 GPT 기반 정확한 비트코인 분석을 제공합니다."
        
        await update.message.reply_text(welcome_message)
    
    async def start(self):
        """시스템 시작"""
        try:
            # Bitget 클라이언트 초기화
            await self.bitget_client.initialize()
            
            # Gate.io 클라이언트 초기화 (미러 트레이딩 활성화 시)
            if self.config.ENABLE_MIRROR_TRADING and self.gateio_client:
                await self.gateio_client.initialize()
                # 미러 트레이딩 시작
                asyncio.create_task(self.mirror_trading.start_monitoring())
                self.logger.info("🔄 미러 트레이딩 모니터링 시작")
            
            # 데이터 수집기 시작
            asyncio.create_task(self.data_collector.start())
            
            # 스케줄러 시작
            self.scheduler.start()
            
            # 텔레그램 봇 핸들러 등록
            self.telegram_bot.add_handler('start', self.handle_start_command)
            self.telegram_bot.add_handler('report', self.handle_report_command)
            self.telegram_bot.add_handler('forecast', self.handle_forecast_command)
            self.telegram_bot.add_handler('profit', self.handle_profit_command)
            self.telegram_bot.add_handler('schedule', self.handle_schedule_command)
            self.telegram_bot.add_handler('mirror', self.handle_mirror_status)
            
            # 자연어 메시지 핸들러 추가
            self.telegram_bot.add_message_handler(self.handle_natural_language)
            
            # 텔레그램 봇 시작
            await self.telegram_bot.start()
            
            self.logger.info("비트코인 예측 시스템 시작됨")
            
            # 시작 메시지
            start_msg = "🚀 비트코인 예측 시스템이 시작되었습니다!\n\n"
            if self.config.ENABLE_MIRROR_TRADING:
                start_msg += "🔄 미러 트레이딩: 활성화\n\n"
            start_msg += "명령어를 입력하거나 자연어로 질문해보세요.\n예: '오늘 수익은?' 또는 /help"
            
            await self.telegram_bot.send_message(start_msg)
            
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
            # 미러 트레이딩 중지
            if self.mirror_trading:
                self.mirror_trading.stop()
            
            self.scheduler.shutdown()
            await self.telegram_bot.stop()
            
            # 데이터 수집기 종료
            if self.data_collector.session:
                await self.data_collector.close()
            
            # Bitget 클라이언트 종료
            if self.bitget_client.session:
                await self.bitget_client.close()
            
            # Gate.io 클라이언트 종료
            if self.gateio_client and self.gateio_client.session:
                await self.gateio_client.close()
            
            self.logger.info("시스템이 안전하게 종료되었습니다")
        except Exception as e:
            self.logger.error(f"시스템 종료 중 오류: {str(e)}")

async def main():
    """메인 함수"""
    system = BitcoinPredictionSystem()
    await system.start()

if __name__ == "__main__":
    asyncio.run(main())
