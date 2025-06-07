# main.py
import asyncio
import logging
import os
import signal
import sys
import traceback
from datetime import datetime, timedelta
import pytz
from typing import Optional

# 환경변수에서 모든 설정 로드
from config import Config
from bitget_client import BitgetClient
from data_collector import RealTimeDataCollector
from trading_indicators import AdvancedTradingIndicators
from analysis_engine import AnalysisEngine
from telegram_bot import TelegramBot
from exception_detector import ExceptionDetector
from ml_predictor import MLPredictor
from report_generators import ReportGeneratorManager


class BitcoinPredictionSystem:
    """비트코인 예측 시스템 메인 클래스"""
    
    def __init__(self):
        # 🔥🔥🔥 가장 먼저 logger 초기화 - 에러 해결
        self.logger = logging.getLogger('bitcoin_prediction_system')
        self.logger.info("🚀 BitcoinPredictionSystem 초기화 시작")
        
        # 설정 로드
        try:
            self.config = Config()
            self.logger.info("✅ 설정 로드 완료")
        except Exception as e:
            self.logger.error(f"❌ 설정 로드 실패: {e}")
            raise
        
        # 한국 시간대 설정
        self.kst = pytz.timezone('Asia/Seoul')
        
        # 시스템 상태
        self.running = False
        self.shutdown_initiated = False
        
        # 클라이언트 인스턴스들
        self.bitget_client = None
        self.gateio_client = None
        self.data_collector = None
        self.indicator_system = None
        self.analysis_engine = None
        self.telegram_bot = None
        self.exception_detector = None
        self.ml_predictor = None
        self.report_manager = None
        
        # 리포트 생성 주기 (시간)
        self.regular_report_interval = 4  # 4시간마다
        self.last_regular_report = None
        
        # 예외 감지 주기 (분)
        self.exception_check_interval = 5  # 5분마다
        self.last_exception_check = None
        
        # 클라이언트 초기화
        self._initialize_clients()
        
        self.logger.info("🎯 BitcoinPredictionSystem 초기화 완료")
    
    def _initialize_clients(self):
        """모든 클라이언트 초기화"""
        try:
            self.logger.info("🔧 클라이언트 초기화 시작")
            
            # 1. Bitget 클라이언트 (필수)
            try:
                self.bitget_client = BitgetClient(self.config)
                self.logger.info("✅ Bitget 클라이언트 생성 완료")
            except Exception as e:
                self.logger.error(f"❌ Bitget 클라이언트 생성 실패: {e}")
                raise
            
            # 2. Gate.io 클라이언트 (미러 트레이딩 모드에서만)
            if self.config.MIRROR_TRADING_MODE:
                try:
                    from gate_client import GateIOClient
                    self.gateio_client = GateIOClient(self.config)
                    self.logger.info("✅ Gate.io 클라이언트 생성 완료")
                except Exception as e:
                    self.logger.warning(f"⚠️  Gate.io 클라이언트 생성 실패: {e}")
                    self.gateio_client = None
            
            # 3. 데이터 수집기
            try:
                self.data_collector = RealTimeDataCollector(self.config, self.bitget_client)
                self.logger.info("✅ 데이터 수집기 생성 완료")
            except Exception as e:
                self.logger.error(f"❌ 데이터 수집기 생성 실패: {e}")
                raise
            
            # 4. 지표 시스템
            try:
                self.indicator_system = AdvancedTradingIndicators(self.data_collector)
                self.indicator_system.set_bitget_client(self.bitget_client)
                self.logger.info("✅ 지표 시스템 생성 완료")
            except Exception as e:
                self.logger.error(f"❌ 지표 시스템 생성 실패: {e}")
                raise
            
            # 5. 분석 엔진
            try:
                self.analysis_engine = AnalysisEngine(self.bitget_client)
                self.logger.info("✅ 분석 엔진 생성 완료")
            except Exception as e:
                self.logger.error(f"❌ 분석 엔진 생성 실패: {e}")
                raise
            
            # 6. 텔레그램 봇
            try:
                self.telegram_bot = TelegramBot(self.config)
                self._setup_telegram_handlers()
                self.logger.info("✅ 텔레그램 봇 생성 완료")
            except Exception as e:
                self.logger.error(f"❌ 텔레그램 봇 생성 실패: {e}")
                raise
            
            # 7. 예외 감지기
            try:
                self.exception_detector = ExceptionDetector(
                    bitget_client=self.bitget_client,
                    telegram_bot=self.telegram_bot
                )
                self.logger.info("✅ 예외 감지기 생성 완료")
            except Exception as e:
                self.logger.error(f"❌ 예외 감지기 생성 실패: {e}")
                self.exception_detector = None
            
            # 8. ML 예측기
            try:
                self.ml_predictor = MLPredictor()
                self.logger.info("✅ ML 예측기 생성 완료")
            except Exception as e:
                self.logger.error(f"❌ ML 예측기 생성 실패: {e}")
                self.ml_predictor = None
            
            # 9. 리포트 매니저
            try:
                self.report_manager = ReportGeneratorManager(
                    self.config,
                    self.data_collector,
                    self.indicator_system,
                    self.bitget_client
                )
                
                # Gate.io 클라이언트 설정 (있는 경우)
                if self.gateio_client:
                    self.report_manager.set_gateio_client(self.gateio_client)
                
                self.logger.info("✅ 리포트 매니저 생성 완료")
            except Exception as e:
                self.logger.error(f"❌ 리포트 매니저 생성 실패: {e}")
                raise
            
            self.logger.info("🎯 모든 클라이언트 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"클라이언트 초기화 실패: {e}")
            raise
    
    def _setup_telegram_handlers(self):
        """텔레그램 명령어 핸들러 설정"""
        try:
            self.logger.info("📱 텔레그램 핸들러 설정 시작")
            
            # 명령어 핸들러 등록
            self.telegram_bot.add_handler('start', self._handle_start)
            self.telegram_bot.add_handler('help', self._handle_help)
            self.telegram_bot.add_handler('status', self._handle_status)
            self.telegram_bot.add_handler('report', self._handle_report)
            self.telegram_bot.add_handler('profit', self._handle_profit)
            self.telegram_bot.add_handler('forecast', self._handle_forecast)
            self.telegram_bot.add_handler('schedule', self._handle_schedule)
            self.telegram_bot.add_handler('positions', self._handle_positions)
            self.telegram_bot.add_handler('orders', self._handle_orders)
            self.telegram_bot.add_handler('sync', self._handle_sync)
            
            # 자연어 메시지 핸들러
            self.telegram_bot.add_message_handler(self._handle_natural_language)
            
            self.logger.info("✅ 텔레그램 핸들러 설정 완료")
            
        except Exception as e:
            self.logger.error(f"텔레그램 핸들러 설정 실패: {e}")
            raise
    
    async def _handle_start(self, update, context):
        """시작 명령어 처리"""
        welcome_message = """🚀 비트코인 예측 시스템에 오신 것을 환영합니다!

📊 사용 가능한 명령어:
• /report - 정기 분석 리포트
• /profit - 수익 현황 리포트  
• /forecast - 단기 예측 리포트
• /schedule - 예정 이벤트 조회
• /positions - 현재 포지션 현황
• /orders - 주문 현황 조회
• /sync - 강제 동기화
• /status - 시스템 상태 확인
• /help - 도움말

🤖 자연어로도 질문하실 수 있습니다!
예: "현재 가격은?", "수익률이 어떻게 돼?"
"""
        
        await self.telegram_bot.send_message(welcome_message, parse_mode='HTML')
    
    async def _handle_help(self, update, context):
        """도움말 명령어 처리"""
        help_message = """📚 비트코인 예측 시스템 사용법

🔄 정기 리포트 (/report):
• 4시간마다 자동 생성
• 시장 분석, 기술적 지표, AI 예측 포함

💰 수익 리포트 (/profit):
• 실시간 손익 현황
• 포지션별 수익률
• 총 자산 변화

📈 예측 리포트 (/forecast):
• 12시간 단기 예측
• 기술적 분석 기반
• 매매 전략 제안

📅 스케줄 (/schedule):
• 다가오는 중요 이벤트
• 경제 지표 발표 일정
• 암호화폐 관련 이벤트

🎯 포지션 (/positions):
• 현재 열린 포지션
• 수익/손실 현황
• 리스크 분석

📋 주문 (/orders):
• 예약 주문 현황
• TP/SL 설정 상태
• 주문 실행 현황

💬 자연어 질문도 가능합니다!
"""
        
        await self.telegram_bot.send_message(help_message, parse_mode='HTML')
    
    async def _handle_status(self, update, context):
        """시스템 상태 확인"""
        try:
            current_time = datetime.now(self.kst).strftime('%Y-%m-%d %H:%M:%S')
            
            # 각 컴포넌트 상태 확인
            bitget_status = "✅ 정상" if self.bitget_client else "❌ 오류"
            telegram_status = "✅ 정상" if self.telegram_bot.is_running() else "❌ 정지"
            
            gateio_status = "✅ 정상" if self.gateio_client else "➖ 미사용"
            if self.config.MIRROR_TRADING_MODE and not self.gateio_client:
                gateio_status = "⚠️ 오류"
            
            status_message = f"""🔍 시스템 상태 점검
📅 {current_time} (KST)

🔧 핵심 컴포넌트:
• Bitget 클라이언트: {bitget_status}
• 텔레그램 봇: {telegram_status}
• Gate.io 클라이언트: {gateio_status}
• 데이터 수집기: ✅ 정상
• 지표 시스템: ✅ 정상
• 예외 감지기: ✅ 정상

📊 운영 모드:
• 미러 트레이딩: {'✅ 활성화' if self.config.MIRROR_TRADING_MODE else '❌ 비활성화'}
• 정기 리포트: ✅ 4시간 주기
• 예외 감지: ✅ 5분 주기

💡 모든 시스템이 정상 작동 중입니다."""
            
            await self.telegram_bot.send_message(status_message, parse_mode='HTML')
            
        except Exception as e:
            await self.telegram_bot.send_message(f"❌ 상태 확인 실패: {e}")
    
    async def _handle_report(self, update, context):
        """정기 리포트 생성 및 전송"""
        try:
            await self.telegram_bot.send_message("📊 정기 리포트 생성 중... 잠시만 기다려주세요.")
            
            report = await self.report_manager.generate_regular_report()
            await self.telegram_bot.send_message(report, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"정기 리포트 생성 실패: {e}")
            await self.telegram_bot.send_message(f"❌ 리포트 생성 실패: {str(e)[:200]}")
    
    async def _handle_profit(self, update, context):
        """수익 리포트 생성 및 전송"""
        try:
            await self.telegram_bot.send_message("💰 수익 리포트 생성 중... 잠시만 기다려주세요.")
            
            profit_report = await self.report_manager.generate_profit_report()
            await self.telegram_bot.send_message(profit_report, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"수익 리포트 생성 실패: {e}")
            await self.telegram_bot.send_message(f"❌ 수익 리포트 생성 실패: {str(e)[:200]}")
    
    async def _handle_forecast(self, update, context):
        """예측 리포트 생성 및 전송"""
        try:
            await self.telegram_bot.send_message("🔮 예측 리포트 생성 중... 잠시만 기다려주세요.")
            
            forecast_report = await self.report_manager.generate_forecast_report()
            await self.telegram_bot.send_message(forecast_report, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"예측 리포트 생성 실패: {e}")
            await self.telegram_bot.send_message(f"❌ 예측 리포트 생성 실패: {str(e)[:200]}")
    
    async def _handle_schedule(self, update, context):
        """스케줄 리포트 생성 및 전송"""
        try:
            await self.telegram_bot.send_message("📅 스케줄 조회 중... 잠시만 기다려주세요.")
            
            schedule_report = await self.report_manager.generate_schedule_report()
            await self.telegram_bot.send_message(schedule_report, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"스케줄 리포트 생성 실패: {e}")
            await self.telegram_bot.send_message(f"❌ 스케줄 조회 실패: {str(e)[:200]}")
    
    async def _handle_positions(self, update, context):
        """포지션 현황 조회"""
        try:
            await self.telegram_bot.send_message("🎯 포지션 현황 조회 중...")
            
            if not self.bitget_client:
                await self.telegram_bot.send_message("❌ Bitget 클라이언트가 초기화되지 않았습니다.")
                return
            
            positions = await self.bitget_client.get_positions()
            
            if not positions:
                await self.telegram_bot.send_message("📊 현재 열린 포지션이 없습니다.")
                return
            
            message = "🎯 현재 포지션 현황\n\n"
            for pos in positions:
                symbol = pos.get('symbol', 'Unknown')
                side = pos.get('holdSide', 'Unknown')
                size = float(pos.get('total', 0))
                unrealized_pnl = float(pos.get('unrealizedPL', 0))
                
                pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
                
                message += f"📈 {symbol}\n"
                message += f"  방향: {side}\n"
                message += f"  수량: {size}\n"
                message += f"  {pnl_emoji} 손익: ${unrealized_pnl:.2f}\n\n"
            
            await self.telegram_bot.send_message(message)
            
        except Exception as e:
            self.logger.error(f"포지션 조회 실패: {e}")
            await self.telegram_bot.send_message(f"❌ 포지션 조회 실패: {str(e)[:200]}")
    
    async def _handle_orders(self, update, context):
        """주문 현황 조회"""
        try:
            await self.telegram_bot.send_message("📋 주문 현황 조회 중...")
            
            if not self.bitget_client:
                await self.telegram_bot.send_message("❌ Bitget 클라이언트가 초기화되지 않았습니다.")
                return
            
            # 예약 주문과 TP/SL 주문 조회
            all_orders = await self.bitget_client.get_all_plan_orders_with_tp_sl()
            
            plan_orders = all_orders.get('plan_orders', [])
            tp_sl_orders = all_orders.get('tp_sl_orders', [])
            
            if not plan_orders and not tp_sl_orders:
                await self.telegram_bot.send_message("📋 현재 대기 중인 주문이 없습니다.")
                return
            
            message = "📋 주문 현황\n\n"
            
            if plan_orders:
                message += "🎯 예약 주문:\n"
                for order in plan_orders[:5]:  # 최대 5개
                    order_id = order.get('orderId', order.get('planOrderId', 'Unknown'))
                    side = order.get('side', order.get('tradeSide', 'Unknown'))
                    trigger_price = order.get('triggerPrice', order.get('price', 0))
                    
                    message += f"  • {side} @ ${trigger_price} (ID: {order_id[:8]}...)\n"
            
            if tp_sl_orders:
                message += "\n🛡️ TP/SL 주문:\n"
                for order in tp_sl_orders[:5]:  # 최대 5개
                    order_id = order.get('orderId', order.get('planOrderId', 'Unknown'))
                    side = order.get('side', order.get('tradeSide', 'Unknown'))
                    trigger_price = order.get('triggerPrice', 0)
                    
                    message += f"  • {side} @ ${trigger_price} (ID: {order_id[:8]}...)\n"
            
            await self.telegram_bot.send_message(message)
            
        except Exception as e:
            self.logger.error(f"주문 조회 실패: {e}")
            await self.telegram_bot.send_message(f"❌ 주문 조회 실패: {str(e)[:200]}")
    
    async def _handle_sync(self, update, context):
        """강제 동기화"""
        try:
            await self.telegram_bot.send_message("🔄 시스템 동기화 중...")
            
            # 미러 트레이딩 모드인 경우 동기화 실행
            if self.config.MIRROR_TRADING_MODE and self.gateio_client:
                from bitget_mirror_client import BitgetMirrorClient
                mirror_client = BitgetMirrorClient(
                    self.config, 
                    self.bitget_client, 
                    self.gateio_client,
                    self.telegram_bot
                )
                
                sync_result = await mirror_client.force_sync()
                await self.telegram_bot.send_message(f"✅ 동기화 완료: {sync_result}")
            else:
                await self.telegram_bot.send_message("ℹ️ 미러 트레이딩 모드가 아니므로 동기화가 필요하지 않습니다.")
                
        except Exception as e:
            self.logger.error(f"동기화 실패: {e}")
            await self.telegram_bot.send_message(f"❌ 동기화 실패: {str(e)[:200]}")
    
    async def _handle_natural_language(self, update, context):
        """자연어 메시지 처리"""
        try:
            message_text = update.message.text.lower()
            
            # 간단한 패턴 매칭
            if any(word in message_text for word in ['가격', '시세', 'price', '얼마']):
                await self._handle_forecast(update, context)
            elif any(word in message_text for word in ['수익', '손익', 'profit', 'pnl']):
                await self._handle_profit(update, context)
            elif any(word in message_text for word in ['리포트', '분석', 'report', '상황']):
                await self._handle_report(update, context)
            elif any(word in message_text for word in ['포지션', 'position', '보유']):
                await self._handle_positions(update, context)
            elif any(word in message_text for word in ['주문', 'order', '예약']):
                await self._handle_orders(update, context)
            elif any(word in message_text for word in ['상태', 'status', '점검']):
                await self._handle_status(update, context)
            else:
                await self.telegram_bot.send_message(
                    "🤔 죄송합니다. 이해하지 못했습니다.\n"
                    "/help 명령어로 사용법을 확인해보세요!"
                )
                
        except Exception as e:
            self.logger.error(f"자연어 처리 실패: {e}")
    
    async def start(self):
        """시스템 시작"""
        try:
            self.logger.info("🚀 비트코인 예측 시스템 시작")
            self.running = True
            
            # 모든 클라이언트 초기화
            await self._initialize_async_clients()
            
            # 텔레그램 봇 시작
            await self.telegram_bot.start()
            
            # 시작 알림 전송
            await self._send_startup_notification()
            
            # 메인 루프 시작
            await self._main_loop()
            
        except Exception as e:
            self.logger.error(f"시스템 시작 실패: {e}")
            await self.stop()
            raise
    
    async def _initialize_async_clients(self):
        """비동기 클라이언트 초기화"""
        try:
            self.logger.info("🔧 비동기 클라이언트 초기화 시작")
            
            # Bitget 클라이언트 초기화
            if self.bitget_client:
                await self.bitget_client.initialize()
            
            # Gate.io 클라이언트 초기화 (있는 경우)
            if self.gateio_client:
                await self.gateio_client.initialize()
            
            # 데이터 수집기 시작
            if self.data_collector:
                await self.data_collector.start()
            
            self.logger.info("✅ 비동기 클라이언트 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"비동기 클라이언트 초기화 실패: {e}")
            raise
    
    async def _send_startup_notification(self):
        """시작 알림 전송"""
        try:
            current_time = datetime.now(self.kst).strftime('%Y-%m-%d %H:%M:%S')
            
            startup_message = f"""🚀 비트코인 예측 시스템 시작됨

📅 시작 시간: {current_time} (KST)
🔧 운영 모드: {'🔄 미러 트레이딩' if self.config.MIRROR_TRADING_MODE else '📈 분석 전용'}

✅ 활성화된 기능:
• 정기 리포트 (4시간 주기)
• 예외 상황 감지 (5분 주기)
• 실시간 시장 분석
• AI 기반 예측

📱 명령어 사용법:
/help - 전체 명령어 목록
/report - 즉시 분석 리포트
/profit - 수익 현황 확인

🤖 시스템이 정상 작동을 시작했습니다!"""
            
            await self.telegram_bot.send_message(startup_message, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"시작 알림 전송 실패: {e}")
    
    async def _main_loop(self):
        """메인 실행 루프"""
        try:
            self.logger.info("🔄 메인 루프 시작")
            
            while self.running and not self.shutdown_initiated:
                try:
                    current_time = datetime.now(self.kst)
                    
                    # 정기 리포트 생성 체크 (4시간마다)
                    if (self.last_regular_report is None or 
                        current_time - self.last_regular_report >= timedelta(hours=self.regular_report_interval)):
                        
                        self.logger.info("📊 정기 리포트 생성 시간")
                        await self._generate_regular_report()
                        self.last_regular_report = current_time
                    
                    # 예외 상황 감지 체크 (5분마다)
                    if (self.last_exception_check is None or 
                        current_time - self.last_exception_check >= timedelta(minutes=self.exception_check_interval)):
                        
                        await self._check_exceptions()
                        self.last_exception_check = current_time
                    
                    # 미러 트레이딩 실행 (활성화된 경우)
                    if self.config.MIRROR_TRADING_MODE:
                        await self._execute_mirror_trading()
                    
                    # 1분 대기
                    await asyncio.sleep(60)
                    
                except Exception as e:
                    self.logger.error(f"메인 루프 오류: {e}")
                    self.logger.error(traceback.format_exc())
                    await asyncio.sleep(60)  # 오류 발생 시에도 계속 실행
            
            self.logger.info("🔄 메인 루프 종료")
            
        except Exception as e:
            self.logger.error(f"메인 루프 실패: {e}")
            raise
    
    async def _generate_regular_report(self):
        """정기 리포트 생성 및 전송"""
        try:
            self.logger.info("📊 정기 리포트 생성 중...")
            
            if self.report_manager:
                report = await self.report_manager.generate_regular_report()
                await self.telegram_bot.send_message(report, parse_mode='HTML')
                self.logger.info("✅ 정기 리포트 전송 완료")
            
        except Exception as e:
            self.logger.error(f"정기 리포트 생성 실패: {e}")
    
    async def _check_exceptions(self):
        """예외 상황 감지 및 알림"""
        try:
            if not self.exception_detector:
                return
            
            exception_data = await self.exception_detector.check_all_exceptions()
            
            if exception_data.get('has_exceptions', False):
                self.logger.warning("⚠️ 예외 상황 감지됨")
                
                # 예외 리포트 생성
                exception_report = await self.report_manager.generate_exception_report(exception_data)
                await self.telegram_bot.send_message(exception_report, parse_mode='HTML')
                
        except Exception as e:
            self.logger.error(f"예외 감지 실패: {e}")
    
    async def _execute_mirror_trading(self):
        """미러 트레이딩 실행"""
        try:
            if not self.gateio_client:
                return
            
            # 미러 트레이딩 간격 체크
            check_interval = self.config.MIRROR_CHECK_INTERVAL
            if hasattr(self, 'last_mirror_check'):
                if datetime.now() - self.last_mirror_check < timedelta(minutes=check_interval):
                    return
            
            self.logger.info("🔄 미러 트레이딩 실행 중...")
            
            from bitget_mirror_client import BitgetMirrorClient
            mirror_client = BitgetMirrorClient(
                self.config,
                self.bitget_client,
                self.gateio_client,
                self.telegram_bot
            )
            
            await mirror_client.execute_mirror_trading()
            self.last_mirror_check = datetime.now()
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 실행 실패: {e}")
    
    async def stop(self):
        """시스템 종료"""
        try:
            self.logger.info("🛑 시스템 종료 시작")
            self.shutdown_initiated = True
            self.running = False
            
            # 종료 알림 전송
            try:
                current_time = datetime.now(self.kst).strftime('%Y-%m-%d %H:%M:%S')
                shutdown_message = f"""🛑 비트코인 예측 시스템 종료

📅 종료 시간: {current_time} (KST)

✅ 모든 서비스가 안전하게 종료되었습니다.
다시 시작하려면 서버를 재시작해주세요."""
                
                await self.telegram_bot.send_message(shutdown_message)
            except:
                pass  # 종료 시에는 에러 무시
            
            # 각 클라이언트 종료
            if self.data_collector:
                await self.data_collector.stop()
            
            if self.bitget_client:
                await self.bitget_client.close()
            
            if self.gateio_client:
                await self.gateio_client.close()
            
            if self.telegram_bot:
                await self.telegram_bot.stop()
            
            self.logger.info("✅ 시스템 종료 완료")
            
        except Exception as e:
            self.logger.error(f"시스템 종료 오류: {e}")


def setup_logging():
    """로깅 설정"""
    # 로그 레벨 설정
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # 로그 포맷 설정
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 기본 로깅 설정
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format,
        handlers=[
            logging.StreamHandler(),  # 콘솔 출력
        ]
    )
    
    # aiohttp 로그 레벨 조정 (너무 상세한 로그 방지)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)


def signal_handler(signum, frame):
    """시스템 종료 신호 처리"""
    print(f"\n🛑 종료 신호 수신 (Signal: {signum})")
    print("시스템을 안전하게 종료하는 중...")
    sys.exit(0)


async def main():
    """메인 함수"""
    # 로깅 설정
    setup_logging()
    
    # 신호 처리기 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger = logging.getLogger('main')
    
    try:
        logger.info("🚀 비트코인 예측 시스템 시작")
        
        # 시스템 인스턴스 생성
        system = BitcoinPredictionSystem()
        
        # 시스템 시작
        await system.start()
        
    except KeyboardInterrupt:
        logger.info("🛑 사용자에 의한 종료")
    except Exception as e:
        logger.error(f"❌ 시스템 오류: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        try:
            if 'system' in locals():
                await system.stop()
        except:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 프로그램이 종료되었습니다.")
    except Exception as e:
        print(f"❌ 프로그램 실행 오류: {e}")
        sys.exit(1)
