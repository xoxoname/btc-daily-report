# main.py의 __init__ 메서드에 추가할 부분

from data_collector import RealTimeDataCollector  # import 추가

class BitcoinPredictionSystem:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 설정 로드
        self.config = Config()
        
        # 클라이언트 초기화
        self.bitget_client = BitgetClient(self.config)
        self.telegram_bot = TelegramBot(self.config)
        
        # 데이터 수집기 초기화 (새로 추가)
        self.data_collector = RealTimeDataCollector(self.config)
        self.data_collector.set_bitget_client(self.bitget_client)
        
        # 엔진 초기화
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
    
    # start 메서드 수정
    async def start(self):
        """시스템 시작"""
        try:
            # 데이터 수집기 시작 (새로 추가)
            asyncio.create_task(self.data_collector.start())
            
            # 스케줄러 시작
            self.scheduler.start()
            
            # ... 기존 코드 ...
    
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
                if event.severity in ['high', 'critical']:
                    # 예외 리포트 형식으로 전송
                    alert_message = self._format_event_alert(event)
                    await self.telegram_bot.send_message(alert_message, parse_mode='HTML')
            
            # 버퍼 클리어
            self.data_collector.events_buffer = []
                
        except Exception as e:
            self.logger.error(f"예외 감지 실패: {str(e)}")
    
    # 새로운 메서드 추가
    def _format_event_alert(self, event):
        """이벤트 알림 포맷팅"""
        return f"""🚨 <b>[BTC 긴급 예외 리포트]</b>
📅 발생 시각: {event.timestamp.strftime('%Y-%m-%d %H:%M')} (KST)
━━━━━━━━━━━━━━━━━━━

❗ <b>급변 원인 요약</b>
• {event.title}
• {event.description}

━━━━━━━━━━━━━━━━━━━

📌 <b>GPT 분석 및 판단</b>
• 카테고리: {event.category}
• 심각도: {event.severity.value}
• 예상 영향: {event.impact}

━━━━━━━━━━━━━━━━━━━

🛡️ <b>리스크 대응 전략 제안</b>
• 현재 포지션 재검토 필요
• 변동성 확대 대비 리스크 관리
• 추가 정보 확인 후 신중한 대응

━━━━━━━━━━━━━━━━━━━

🧭 <b>참고</b>
• 출처: {event.source}
• 상세: {event.url if event.url else 'N/A'}
"""
