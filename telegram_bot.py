import logging
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
from typing import Callable
import re
import os

class TelegramBot:
    """싱글톤 패턴 적용된 텔레그램 봇 - 중복 인스턴스 방지"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls, config):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super(TelegramBot, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config):
        # 이미 초기화되었으면 재초기화하지 않음
        if self._initialized:
            self.logger.info("✅ 기존 텔레그램 봇 인스턴스 재사용")
            return
            
        self.config = config
        self.logger = logging.getLogger('telegram_bot')
        self.bot = None
        self.application = None
        self._running = False
        
        # 🔥🔥🔥 중복 실행 방지를 위한 상태 플래그
        self._starting = False
        self._stopping = False
        
        self._initialize_bot()
        self._initialized = True
        
    def _initialize_bot(self):
        """봇 초기화"""
        try:
            # 환경변수명 통일 - TELEGRAM_BOT_TOKEN 사용
            telegram_token = self.config.TELEGRAM_BOT_TOKEN
            if not telegram_token:
                raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
            
            # 🔥🔥🔥 기존 Application이 있으면 정리
            if self.application:
                try:
                    if self.application.updater and self.application.updater.running:
                        self.logger.warning("기존 Application 정리 중...")
                        # 동기적으로 정리 시도
                        pass
                except Exception as cleanup_error:
                    self.logger.warning(f"기존 Application 정리 실패: {cleanup_error}")
            
            # Bot 인스턴스 생성
            self.bot = Bot(token=telegram_token)
            
            # 🔥🔥🔥 Application 생성 - read_timeout과 write_timeout 설정으로 충돌 방지
            self.application = Application.builder().token(telegram_token).read_timeout(30).write_timeout(30).build()
            
            self.logger.info("텔레그램 봇 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"텔레그램 봇 초기화 실패: {str(e)}")
            raise
    
    def add_handler(self, command: str, handler_func: Callable):
        """명령 핸들러 추가"""
        try:
            if self.application is None:
                self._initialize_bot()
            
            # 🔥🔥🔥 기존 핸들러가 있으면 제거 후 추가
            existing_handlers = []
            for handler_group in self.application.handlers.values():
                for handler in handler_group:
                    if hasattr(handler, 'command') and isinstance(handler.command, list):
                        if command in handler.command:
                            existing_handlers.append(handler)
                    elif hasattr(handler, 'command') and handler.command == command:
                        existing_handlers.append(handler)
            
            for existing_handler in existing_handlers:
                self.application.remove_handler(existing_handler)
                self.logger.debug(f"기존 핸들러 제거: /{command}")
            
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
            
            # 🔥🔥🔥 기존 메시지 핸들러가 있으면 제거
            existing_message_handlers = []
            for handler_group in self.application.handlers.values():
                for handler in handler_group:
                    if isinstance(handler, MessageHandler) and (filters.TEXT & ~filters.COMMAND) in str(handler.filters):
                        existing_message_handlers.append(handler)
            
            for existing_handler in existing_message_handlers:
                self.application.remove_handler(existing_handler)
                self.logger.debug("기존 메시지 핸들러 제거")
            
            message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handler_func)
            self.application.add_handler(message_handler)
            self.logger.info("자연어 메시지 핸들러 등록 완료")
            
        except Exception as e:
            self.logger.error(f"메시지 핸들러 등록 실패: {str(e)}")
            raise
    
    async def start(self):
        """봇 시작 - 중복 실행 방지 로직 강화"""
        try:
            # 🔥🔥🔥 이미 시작 중이거나 실행 중이면 대기 또는 종료
            if self._starting:
                self.logger.info("텔레그램 봇이 이미 시작 중입니다. 대기...")
                # 최대 10초 대기
                for _ in range(100):
                    if not self._starting:
                        break
                    await asyncio.sleep(0.1)
                
                if self._running:
                    self.logger.info("✅ 텔레그램 봇이 이미 실행 중입니다.")
                    return
            
            if self._running:
                self.logger.info("✅ 텔레그램 봇이 이미 실행 중입니다.")
                return
            
            self._starting = True
            
            if self.application is None:
                self._initialize_bot()
            
            # 🔥🔥🔥 Application 상태 확인 및 정리
            if hasattr(self.application, 'updater') and self.application.updater:
                if self.application.updater.running:
                    self.logger.warning("기존 updater가 실행 중입니다. 정지 시도...")
                    try:
                        await self.application.updater.stop()
                        await asyncio.sleep(1)  # 정지 완료 대기
                    except Exception as stop_error:
                        self.logger.warning(f"기존 updater 정지 실패: {stop_error}")
            
            # 🔥🔥🔥 Application 초기화 및 시작 (예외 처리 강화)
            self.logger.info("텔레그램 봇 Application 초기화 중...")
            await self.application.initialize()
            
            self.logger.info("텔레그램 봇 Application 시작 중...")
            await self.application.start()
            
            # 🔥🔥🔥 Polling 시작 (ConflictError 방지)
            self.logger.info("텔레그램 봇 Polling 시작 중...")
            try:
                await self.application.updater.start_polling(
                    drop_pending_updates=True,  # 대기 중인 업데이트 삭제
                    allowed_updates=Update.ALL_TYPES,
                    read_timeout=30,
                    write_timeout=30,
                    connect_timeout=30,
                    pool_timeout=30
                )
                
                self._running = True
                self._starting = False
                self.logger.info("✅ 텔레그램 봇 시작됨")
                
            except Exception as polling_error:
                error_msg = str(polling_error).lower()
                
                # 🔥🔥🔥 ConflictError 처리 (다른 인스턴스가 실행 중)
                if "conflict" in error_msg or "terminated by other getupdates" in error_msg:
                    self.logger.error("❌ 다른 봇 인스턴스가 이미 실행 중입니다!")
                    self.logger.error("해결 방법:")
                    self.logger.error("1. 다른 실행 중인 봇 프로세스를 종료하세요")
                    self.logger.error("2. 또는 webhook을 사용 중이라면 삭제하세요")
                    self.logger.error("3. 몇 분 후 다시 시도하세요")
                    
                    # 현재 Application 정리
                    try:
                        await self.application.stop()
                        await self.application.shutdown()
                    except:
                        pass
                    
                    self._running = False
                    self._starting = False
                    raise Exception("ConflictError: 다른 봇 인스턴스가 실행 중입니다.")
                else:
                    self.logger.error(f"Polling 시작 실패: {polling_error}")
                    self._running = False
                    self._starting = False
                    raise
            
        except Exception as e:
            self.logger.error(f"텔레그램 봇 시작 실패: {str(e)}")
            self._running = False
            self._starting = False
            raise
    
    async def stop(self):
        """봇 정지 - 안전한 종료 로직"""
        try:
            if self._stopping:
                self.logger.info("텔레그램 봇이 이미 정지 중입니다.")
                return
            
            if not self._running:
                self.logger.info("텔레그램 봇이 실행 중이 아닙니다.")
                return
            
            self._stopping = True
            
            self.logger.info("텔레그램 봇 정지 중...")
            
            if self.application:
                try:
                    # Updater 정지
                    if hasattr(self.application, 'updater') and self.application.updater:
                        if self.application.updater.running:
                            await self.application.updater.stop()
                            await asyncio.sleep(0.5)  # 정지 완료 대기
                    
                    # Application 정지
                    await self.application.stop()
                    await asyncio.sleep(0.5)  # 정지 완료 대기
                    
                    # Application 종료
                    await self.application.shutdown()
                    await asyncio.sleep(0.5)  # 종료 완료 대기
                    
                    self.logger.info("✅ 텔레그램 봇 정지됨")
                    
                except Exception as stop_error:
                    self.logger.error(f"텔레그램 봇 정지 중 오류: {stop_error}")
                finally:
                    self._running = False
                    self._stopping = False
            else:
                self._running = False
                self._stopping = False
                
        except Exception as e:
            self.logger.error(f"텔레그램 봇 정지 실패: {str(e)}")
            self._running = False
            self._stopping = False
    
    def _clean_html_message(self, text: str) -> str:
        """🔥🔥 HTML 메시지 정리 및 검증 - 오류 방지 강화"""
        try:
            # 1. 기본 null/None 체크
            if not text:
                return "빈 메시지"
            
            text = str(text)
            
            # 2. 빈 태그 제거 (가장 큰 문제)
            text = re.sub(r'<\s*>', '', text)  # < >
            text = re.sub(r'<\s*/\s*>', '', text)  # </ >
            text = re.sub(r'<\s+/?\s*>', '', text)  # 공백만 있는 태그
            
            # 3. 깨진 태그 수정
            text = re.sub(r'<([^>]*?)(?=<|$)', r'', text)  # 닫히지 않은 태그 시작 제거
            text = re.sub(r'(?<!>)>([^<]*?)>', r'\1', text)  # 시작 없는 닫는 태그 제거
            
            # 4. 지원되지 않는 태그 제거
            allowed_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'code', 'pre', 'a']
            text = re.sub(r'<(?!/?(?:' + '|'.join(allowed_tags) + r')\b)[^>]*>', '', text)
            
            # 5. 중첩된 같은 태그 정리
            for tag in ['b', 'i', 'u', 's', 'code']:
                text = re.sub(f'<{tag}[^>]*><{tag}[^>]*>', f'<{tag}>', text)
                text = re.sub(f'</{tag}></{tag}>', f'</{tag}>', text)
            
            # 6. 빈 태그 제거
            for tag in allowed_tags:
                text = re.sub(f'<{tag}[^>]*>\\s*</{tag}>', '', text)
            
            # 7. HTML 엔티티 정리
            html_entities = {
                '&amp;': '&', '&lt;': '<', '&gt;': '>', 
                '&quot;': '"', '&#39;': "'", '&#x27;': "'",
                '&nbsp;': ' ', '&#160;': ' '
            }
            for entity, replacement in html_entities.items():
                text = text.replace(entity, replacement)
            
            # 8. 연속 공백 및 개행 정리
            text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # 3개 이상 개행을 2개로
            text = re.sub(r' {3,}', '  ', text)  # 3개 이상 공백을 2개로
            text = re.sub(r'\t+', ' ', text)  # 탭을 공백으로
            
            # 9. 길이 제한 (텔레그램 메시지 최대 길이)
            if len(text) > 4000:
                text = text[:3950] + "\n\n... (메시지가 잘림)"
            
            # 10. 최종 공백 정리
            text = text.strip()
            
            return text if text else "빈 메시지"
            
        except Exception as e:
            self.logger.error(f"HTML 메시지 정리 실패: {e}")
            # 안전한 텍스트만 반환
            try:
                clean_text = re.sub(r'<[^>]*>', '', str(text))
                return clean_text[:500] if clean_text else "메시지 정리 실패"
            except:
                return "메시지 정리 실패"
    
    async def send_message(self, text: str, parse_mode: str = None, chat_id: str = None):
        """메시지 전송 - 오류 처리 강화"""
        try:
            if not self.bot:
                raise Exception("텔레그램 봇이 초기화되지 않았습니다.")
            
            if not chat_id:
                chat_id = self.config.TELEGRAM_CHAT_ID
            
            if not chat_id:
                raise Exception("TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
            
            # 🔥🔥🔥 텍스트 전처리 및 검증
            if not text or not str(text).strip():
                self.logger.warning("빈 메시지 전송 요청 무시")
                return
            
            # HTML 파싱 모드인 경우 메시지 정리
            if parse_mode == 'HTML':
                original_text = text
                text = self._clean_html_message(text)
                
                # 정리 후에도 문제가 있는지 확인
                if len(text) < len(original_text) * 0.3:  # 원본의 30% 미만으로 줄어들면
                    self.logger.warning("HTML 정리 후 텍스트가 너무 많이 줄어듦, 텍스트 모드로 전환")
                    parse_mode = None
                    text = re.sub(r'<[^>]*>', '', original_text)
            
            # 1차: HTML 모드 시도
            if parse_mode == 'HTML':
                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode='HTML'
                    )
                    self.logger.debug("HTML 모드 메시지 전송 성공")
                    return
                    
                except Exception as html_error:
                    error_msg = str(html_error).lower()
                    self.logger.warning(f"HTML 모드 전송 실패: {html_error}")
                    
                    # HTML 파싱 오류인 경우 텍스트 모드로 폴백
                    if any(keyword in error_msg for keyword in [
                        "can't parse entities", "unsupported start tag", "can't parse",
                        "bad character", "html parsing", "entities", "tag"
                    ]):
                        self.logger.info("HTML 파싱 오류로 텍스트 모드로 전환")
                        parse_mode = None  # 텍스트 모드로 전환
                    else:
                        raise html_error
            
            # 2차: 텍스트 모드 시도
            if parse_mode != 'HTML':
                try:
                    # HTML 태그 완전 제거
                    text_only = re.sub(r'<[^>]*>', '', str(text))
                    
                    # HTML 엔티티 디코딩
                    text_only = text_only.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                    text_only = text_only.replace('&quot;', '"').replace('&#39;', "'")
                    
                    # 연속 공백 정리
                    text_only = re.sub(r'\n\s*\n\s*\n', '\n\n', text_only)
                    text_only = re.sub(r' {3,}', '  ', text_only)
                    
                    # 길이 제한
                    if len(text_only) > 4000:
                        text_only = text_only[:3950] + "\n\n... (메시지가 잘림)"
                    
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=text_only.strip()
                    )
                    self.logger.debug("텍스트 모드 메시지 전송 성공")
                    return
                    
                except Exception as text_error:
                    self.logger.error(f"텍스트 모드 전송도 실패: {text_error}")
            
            # 3차: 최후 수단 - 기본 오류 메시지
            try:
                fallback_message = f"""🚨 메시지 전송 오류 발생

원본 메시지가 올바르지 않은 형식을 포함하고 있어 전송에 실패했습니다.

시간: {str(text)[:100]}...

시스템이 정상 작동 중이며, 다음 메시지부터는 정상 전송될 예정입니다."""

                await self.bot.send_message(
                    chat_id=chat_id,
                    text=fallback_message
                )
                self.logger.warning("폴백 메시지 전송 완료")
                
            except Exception as fallback_error:
                self.logger.error(f"폴백 메시지 전송도 실패: {fallback_error}")
                raise fallback_error
            
        except Exception as e:
            self.logger.error(f"메시지 전송 최종 실패: {str(e)}")
            self.logger.error(f"원본 메시지 (처음 200자): {str(text)[:200]}")
            
            # 오류 메시지에서 HTML 파싱 오류 감지
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in [
                "can't parse entities", 
                "unsupported start tag",
                "can't parse",
                "bad character",
                "html parsing"
            ]):
                self.logger.error("🚨 HTML 파싱 오류가 계속 발생하고 있습니다!")
                self.logger.error(f"오류 상세: {str(e)}")
                # 여기서 문제가 되는 부분의 offset 정보도 로깅
                if "byte offset" in error_str:
                    offset_match = re.search(r'byte offset (\d+)', error_str)
                    if offset_match:
                        offset = int(offset_match.group(1))
                        problem_area = str(text)[max(0, offset-50):offset+50]
                        self.logger.error(f"문제 구간 (offset {offset} 주변): {repr(problem_area)}")
            
            raise
    
    def is_running(self) -> bool:
        """봇 실행 상태 확인"""
        return self._running and not self._stopping
    
    @classmethod
    def reset_instance(cls):
        """인스턴스 리셋 (디버깅용)"""
        cls._instance = None
        cls._initialized = False
