# telegram_bot.py - 텔레그램 봇
import logging
import re
from typing import Dict, Callable, Any
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    ContextTypes,
    filters
)

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, config):
        self.config = config
        self.application = None
        self.handlers: Dict[str, Callable] = {}
        
    async def initialize(self):
        """봇 초기화"""
        try:
            self.application = Application.builder().token(self.config.telegram_bot_token).build()
            logger.info("텔레그램 봇 초기화 완료")
        except Exception as e:
            logger.error(f"텔레그램 봇 초기화 실패: {e}")
            raise
    
    def add_handler(self, command: str, handler: Callable):
        """명령어 핸들러 추가"""
        self.handlers[command] = handler
        
        # 텔레그램 명령어 핸들러 등록
        self.application.add_handler(
            CommandHandler(command, self._wrap_handler(handler))
        )
        
        # 자연어 처리를 위한 메시지 핸들러도 등록
        if not hasattr(self, '_message_handler_added'):
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_natural_language)
            )
            self._message_handler_added = True
    
    def _wrap_handler(self, handler: Callable):
        """핸들러 래핑"""
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Chat ID 확인
            if str(update.effective_chat.id) != self.config.telegram_chat_id:
                await update.message.reply_text("❌ 권한이 없습니다.")
                return
            
            await handler(update, context)
        
        return wrapped
    
    async def _handle_natural_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """자연어 명령 처리"""
        if str(update.effective_chat.id) != self.config.telegram_chat_id:
            return
            
        text = update.message.text.lower()
        
        # 자연어 패턴 매칭
        patterns = {
            'report': [
                r'리포트', r'분석', r'예측', r'전체.*분석', r'상황.*분석'
            ],
            'forecast': [
                r'예측', r'전망', r'앞으로', r'향후', r'매수.*해야', r'매도.*해야',
                r'지금.*사야', r'지금.*팔아야', r'오늘.*어때'
            ],
            'profit': [
                r'수익', r'손익', r'얼마.*벌었', r'얼마.*잃었', r'현재.*상황',
                r'포지션', r'수익률'
            ],
            'schedule': [
                r'일정', r'스케줄', r'언제', r'예정', r'이벤트'
            ]
        }
        
        for command, pattern_list in patterns.items():
            for pattern in pattern_list:
                if re.search(pattern, text):
                    if command in self.handlers:
                        await self.handlers[command](update, context)
                        return
        
        # 매칭되지 않은 경우
        help_text = """
📋 사용 가능한 명령어:
/report - 전체 분석 리포트
/forecast - 단기 예측
/profit - 수익 현황
/schedule - 예정 일정

🤖 자연어로도 질문 가능:
"지금 매수해야 돼?", "얼마 벌었어?", "오늘 수익은?" 등
        """
        await update.message.reply_text(help_text.strip())
    
    async def send_message(self, message: str):
        """메시지 전송"""
        try:
            await self.application.bot.send_message(
                chat_id=self.config.telegram_chat_id,
                text=message,
                parse_mode='HTML'
            )
            logger.info("메시지 전송 완료")
        except Exception as e:
            logger.error(f"메시지 전송 실패: {e}")
            raise
    
    async def start(self):
        """봇 시작"""
        if not self.application:
            await self.initialize()
        
        try:
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            logger.info("텔레그램 봇 시작됨")
        except Exception as e:
            logger.error(f"봇 시작 실패: {e}")
            raise
    
    async def stop(self):
        """봇 중지"""
        try:
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            logger.info("텔레그램 봇 중지됨")
        except Exception as e:
            logger.error(f"봇 중지 실패: {e}")
            
