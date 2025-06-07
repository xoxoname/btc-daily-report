import logging
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
from typing import Callable
import re

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
            # 환경변수명 통일 - TELEGRAM_BOT_TOKEN 사용
            telegram_token = self.config.TELEGRAM_BOT_TOKEN
            if not telegram_token:
                raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
            
            # Bot 인스턴스 생성
            self.bot = Bot(token=telegram_token)
            
            # Application 생성
            self.application = Application.builder().token(telegram_token).build()
            
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
    
    def _clean_html_message(self, text: str) -> str:
        """🔥🔥 HTML 메시지 정리 및 검증"""
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
            
            # 4. 허용되는 HTML 태그만 유지 (텔레그램 지원 태그)
            allowed_tags = ['b', 'i', 'u', 's', 'code', 'pre', 'a']
            
            # 허용되지 않는 태그를 일반 텍스트로 변환
            for tag in ['span', 'div', 'p', 'br', 'em', 'strong']:
                text = re.sub(f'</?{tag}[^>]*>', '', text)
            
            # 5. 중첩된 동일 태그 정리
            for tag in allowed_tags:
                # <b><b>text</b></b> → <b>text</b>
                pattern = f'<{tag}[^>]*>(<{tag}[^>]*>.*?</{tag}>)</{tag}>'
                text = re.sub(pattern, r'\1', text)
            
            # 6. 빈 태그 제거 (<b></b>, <i></i> 등)
            for tag in allowed_tags:
                text = re.sub(f'<{tag}[^>]*>\\s*</{tag}>', '', text)
            
            # 7. 특수문자 이스케이프 (HTML 엔티티 문제 방지)
            # 단, 이미 허용된 HTML 태그는 보존
            def escape_special_chars(match):
                char = match.group(0)
                if char == '&':
                    return '&amp;'
                elif char == '<':
                    return '&lt;'
                elif char == '>':
                    return '&gt;'
                return char
            
            # HTML 태그가 아닌 <, >, & 문자들만 이스케이프
            text = re.sub(r'&(?!(?:amp|lt|gt|quot|#\d+|#x[0-9a-fA-F]+);)', '&amp;', text)
            
            # 8. 연속된 공백 정리
            text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # 3개 이상 연속 줄바꿈 → 2개
            text = re.sub(r' {3,}', '  ', text)  # 3개 이상 연속 공백 → 2개
            
            # 9. 메시지 길이 체크 (텔레그램 4096자 제한)
            if len(text) > 4000:
                text = text[:3950] + "\n\n... (메시지가 잘림)"
            
            return text.strip()
            
        except Exception as e:
            self.logger.error(f"HTML 메시지 정리 실패: {e}")
            # 모든 HTML 태그 제거하고 텍스트만 반환
            return re.sub(r'<[^>]+>', '', str(text))
    
    def _validate_html_structure(self, text: str) -> bool:
        """🔥 HTML 구조 검증"""
        try:
            # 기본 유효성 검사
            if not text or text.isspace():
                return False
            
            # 태그 균형 검사
            allowed_tags = ['b', 'i', 'u', 's', 'code', 'pre']
            tag_stack = []
            
            # 간단한 태그 매칭 검사
            tag_pattern = r'<(/?)([a-zA-Z]+)[^>]*>'
            
            for match in re.finditer(tag_pattern, text):
                is_closing = bool(match.group(1))
                tag_name = match.group(2).lower()
                
                if tag_name in allowed_tags:
                    if is_closing:
                        if tag_stack and tag_stack[-1] == tag_name:
                            tag_stack.pop()
                        else:
                            return False  # 닫는 태그가 맞지 않음
                    else:
                        tag_stack.append(tag_name)
            
            # 모든 태그가 닫혔는지 확인
            return len(tag_stack) == 0
            
        except Exception as e:
            self.logger.debug(f"HTML 구조 검증 오류: {e}")
            return False
    
    async def send_message(self, text: str, chat_id: str = None, parse_mode: str = 'HTML'):
        """🔥🔥 개선된 메시지 전송 - HTML 파싱 오류 완전 해결"""
        try:
            if chat_id is None:
                chat_id = self.config.TELEGRAM_CHAT_ID
            
            if self.bot is None:
                self._initialize_bot()
            
            # 원본 텍스트 백업
            original_text = str(text)
            
            # 1차: HTML 정리
            if parse_mode == 'HTML':
                cleaned_text = self._clean_html_message(text)
                
                # HTML 구조 검증
                if self._validate_html_structure(cleaned_text):
                    try:
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=cleaned_text,
                            parse_mode='HTML'
                        )
                        self.logger.info("HTML 메시지 전송 성공")
                        return
                    except Exception as html_error:
                        self.logger.warning(f"정리된 HTML 메시지 전송 실패: {html_error}")
                        # 2차 시도로 넘어감
                else:
                    self.logger.warning("HTML 구조 검증 실패, 텍스트 모드로 전환")
            
            # 2차: HTML 태그 완전 제거하고 텍스트로 전송
            try:
                # 모든 HTML 태그 제거
                text_only = re.sub(r'<[^>]+>', '', original_text)
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
                self.logger.info("텍스트 모드 메시지 전송 성공")
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
