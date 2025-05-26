# main.py 상단에 import 추가
from data_collector import RealTimeDataCollector
from trading_indicators import AdvancedTradingIndicators
from report_generator import EnhancedReportGenerator

# BitcoinPredictionSystem 클래스의 __init__ 메서드 수정
class BitcoinPredictionSystem:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 설정 로드
        self.config = Config()
        
        # 클라이언트 초기화
        self.bitget_client = BitgetClient(self.config)
        self.telegram_bot = TelegramBot(self.config)
        
        # 새로운 컴포넌트 추가
        self.data_collector = RealTimeDataCollector(self.config)
        self.data_collector.set_bitget_client(self.bitget_client)
        
        self.indicator_system = AdvancedTradingIndicators()
        self.report_generator = EnhancedReportGenerator(
            self.config,
            self.data_collector,
            self.indicator_system
        )
        
        # 기존 엔진은 그대로 유지
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
        
        self.logger.info("시스템 초기화 완료")
    
    # start 메서드에 데이터 수집기 추가
    async def start(self):
        """시스템 시작"""
        try:
            # 데이터 수집기 시작 (새로 추가)
            asyncio.create_task(self.data_collector.start())
            
            # 스케줄러 시작
            self.scheduler.start()
            
            # 텔레그램 봇 핸들러 등록
            self.telegram_bot.add_handler('start', self.handle_start_command)
            self.telegram_bot.add_handler('report', self.handle_report_command)
            
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
    
    # check_exceptions 메서드 수정
    async def check_exceptions(self):
        """예외 상황 감지"""
        try:
            # 기존 예외 감지
            anomalies = await self.exception_detector.detect_all_anomalies()
            
            for anomaly in anomalies:
                await self.exception_detector.send_alert(anomaly)
            
            # 데이터 수집기의 이벤트 확인 (새로 추가)
            for event in self.data_collector.events_buffer:
                if event.severity.value in ['high', 'critical']:
                    # 예외 리포트 생성
                    report = await self.report_generator.generate_exception_report(event.__dict__)
                    await self.telegram_bot.send_message(report, parse_mode='Markdown')
            
            # 버퍼 클리어
            self.data_collector.events_buffer = []
                
        except Exception as e:
            self.logger.error(f"예외 감지 실패: {str(e)}")
    
    # stop 메서드에 데이터 수집기 종료 추가
    async def stop(self):
        """시스템 종료"""
        try:
            self.scheduler.shutdown()
            await self.telegram_bot.stop()
            
            # 데이터 수집기 종료 (새로 추가)
            if self.data_collector.session:
                await self.data_collector.close()
            
            self.logger.info("시스템이 안전하게 종료되었습니다")
        except Exception as e:
            self.logger.error(f"시스템 종료 중 오류: {str(e)}")
