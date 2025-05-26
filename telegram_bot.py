import logging
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
from typing import Callable

class TelegramBot:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger('telegram_bot')
        self.bot = None
        self.application = None
        self._initialize_bot()
        
    def _initialize_bot(self):
        """봇 초기화"""
        try:
            # Bot 인스턴스 생성
            self.bot = Bot(token=self.config.TELEGRAM_TOKEN)
            
            # Application 생성
            self.application = Application.builder().token(self.config.TELEGRAM_TOKEN).build()
            
            self.logger.info("텔레그램 봇 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"텔레그램 봇 초기화 실패: {str(e)}")
            raise
    
    def add_handler(self, command: str, handler_func: Callable):
        """명령 핸들러 추가"""
        try:
            if self.application is None:
                self._initialize_bot()
            
            command_handler = CommandHandler(command, handler_func)
            self.application.add_handler(command_handler)
            self.logger.info(f"핸들러 등록 완료: /{command}")
            
        except Exception as e:
            self.logger.error(f"핸들러 등록 실패: {str(e)}")
            raise
    
    def add_message_handler(self, handler_func: Callable):
        """자연어 메시지 핸들러 추가"""
        try:
            if self.application is None:
                self._initialize_bot()
            
            message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handler_func)
            self.application.add_handler(message_handler)
            self.logger.info("자연어 메시지 핸들러 등록 완료")
            
        except Exception as e:
            self.logger.error(f"메시지 핸들러 등록 실패: {str(e)}")
            raise
    
    async def start(self):
        """봇 시작"""
        try:
            if self.application is None:
                self._initialize_bot()
            
            # Application 시작
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            self.logger.info("텔레그램 봇 시작됨")
            
        except Exception as e:
            self.logger.error(f"텔레그램 봇 시작 실패: {str(e)}")
            raise
    
    async def stop(self):
        """봇 정지"""
        try:
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                self.logger.info("텔레그램 봇 정지됨")
                
        except Exception as e:
            self.logger.error(f"텔레그램 봇 정지 실패: {str(e)}")
    
    async def send_message(self, text: str, chat_id: str = None, parse_mode: str = None):
        """메시지 전송"""
        try:
            if chat_id is None:
                chat_id = self.config.TELEGRAM_CHAT_ID
            
            if self.bot is None:
                self._initialize_bot()
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode
            )
            
            self.logger.info("메시지 전송 완료")
            
        except Exception as e:
            self.logger.error(f"메시지 전송 실패: {str(e)}")
            raise
