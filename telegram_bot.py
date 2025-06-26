import logging
from telegram import Bot, Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
from typing import Callable
import re
import traceback
from datetime import datetime

class TelegramBot:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger('telegram_bot')
        self.bot = None
        self.application = None
        self.mirror_trading_system = None
        self.system_reference = None
        
        # 디버깅을 위한 상태 추적
        self.debug_stats = {
            'messages_received': 0,
            'commands_received': 0,
            'handler_calls': {},
            'errors': [],
            'last_activity': None
        }
        
        # 배율 설정 관련 상태 관리
        self.pending_ratio_confirmations = {}
        self.pending_mirror_confirmations = {}
        
        # 핸들러 등록 여부 추적
        self._handlers_registered = False
        
        # 봇 실행 상태 추가
        self._is_running = False
        self._is_initialized = False
        self._polling_started = False
        
        self.logger.info("🔥 TelegramBot 인스턴스 생성 완료 - 강화된 디버깅 모드")
        
    def _initialize_bot(self):
        """봇 초기화 - 강화된 디버깅 및 검증"""
        try:
            if self._is_initialized:
                self.logger.info("봇이 이미 초기화되어 있습니다.")
                return
                
            self.logger.info("=" * 50)
            self.logger.info("🔥 텔레그램 봇 초기화 시작 - 상세 진단 모드")
            self.logger.info("=" * 50)
            
            # 1. 환경변수 상세 검증
            telegram_token = self.config.TELEGRAM_BOT_TOKEN
            telegram_chat_id = self.config.TELEGRAM_CHAT_ID
            
            self.logger.info(f"🔍 환경변수 상세 검증:")
            self.logger.info(f"  - TELEGRAM_BOT_TOKEN 존재: {'✅' if telegram_token else '❌'}")
            if telegram_token:
                self.logger.info(f"  - 토큰 길이: {len(telegram_token)}자")
                self.logger.info(f"  - 토큰 형식: {'유효' if ':' in telegram_token else '의심스러움'}")
                token_parts = telegram_token.split(':') if ':' in telegram_token else []
                if len(token_parts) == 2:
                    self.logger.info(f"  - 봇 ID: {token_parts[0]}")
                    self.logger.info(f"  - 토큰 해시: {token_parts[1][:10]}...")
                else:
                    self.logger.error(f"  - 토큰 형식 오류: 올바른 형식이 아님")
            
            self.logger.info(f"  - TELEGRAM_CHAT_ID 존재: {'✅' if telegram_chat_id else '❌'}")
            if telegram_chat_id:
                self.logger.info(f"  - 챗 ID 값: {telegram_chat_id}")
                self.logger.info(f"  - 챗 ID 타입: {type(telegram_chat_id)}")
                
                # 챗 ID 형식 검증 및 변환
                try:
                    if isinstance(telegram_chat_id, str):
                        if telegram_chat_id.isdigit() or (telegram_chat_id.startswith('-') and telegram_chat_id[1:].isdigit()):
                            chat_id_int = int(telegram_chat_id)
                            self.logger.info(f"  - 챗 ID 숫자 변환 성공: {chat_id_int}")
                        else:
                            self.logger.error(f"  - 챗 ID 형식 오류: 숫자가 아님 '{telegram_chat_id}'")
                    elif isinstance(telegram_chat_id, (int, float)):
                        chat_id_int = int(telegram_chat_id)
                        self.logger.info(f"  - 챗 ID 이미 숫자: {chat_id_int}")
                    else:
                        self.logger.error(f"  - 챗 ID 타입 오류: {type(telegram_chat_id)}")
                except ValueError as ve:
                    self.logger.error(f"  - 챗 ID 변환 실패: {ve}")
            
            # 2. 환경변수 검증
            if not telegram_token:
                raise ValueError("❌ TELEGRAM_BOT_TOKEN 환경변수가 없거나 빈 값입니다.")
            
            if not telegram_chat_id:
                raise ValueError("❌ TELEGRAM_CHAT_ID 환경변수가 없거나 빈 값입니다.")
            
            if ':' not in telegram_token:
                raise ValueError(f"❌ TELEGRAM_BOT_TOKEN 형식이 올바르지 않습니다: {telegram_token[:20]}...")
            
            # 3. Bot 인스턴스 생성
            self.logger.info("🔄 Bot 인스턴스 생성 중...")
            self.bot = Bot(token=telegram_token)
            self.logger.info("✅ Bot 인스턴스 생성 완료")
            
            # 4. Application 생성 - 더 상세한 설정
            self.logger.info("🔄 Application 인스턴스 생성 중...")
            builder = Application.builder()
            builder.token(telegram_token)
            
            # 네트워크 설정 강화
            builder.read_timeout(30)
            builder.write_timeout(30) 
            builder.connect_timeout(30)
            builder.pool_timeout(30)
            
            self.application = builder.build()
            self.logger.info("✅ Application 인스턴스 생성 완료")
            
            self._is_initialized = True
            self.logger.info("✅ 텔레그램 봇 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"❌ 텔레그램 봇 초기화 실패: {str(e)}")
            self.logger.error(f"초기화 실패 상세: {traceback.format_exc()}")
            raise
    
    def set_mirror_trading_system(self, mirror_system):
        """미러 트레이딩 시스템 참조 설정"""
        self.mirror_trading_system = mirror_system
        self.logger.info("✅ 미러 트레이딩 시스템 참조 설정 완료")
    
    def set_system_reference(self, system):
        """메인 시스템 참조 설정"""
        self.system_reference = system
        self.logger.info("✅ 메인 시스템 참조 설정 완료")
    
    def setup_handlers(self, handlers_map):
        """핸들러 일괄 등록 - 강화된 디버깅"""
        try:
            self.logger.info("=" * 50)
            self.logger.info("🔥 핸들러 등록 시작 - 강화된 검증 모드")
            self.logger.info("=" * 50)
            
            if not self._is_initialized:
                self.logger.info("봇이 초기화되지 않음 - 초기화 시작")
                self._initialize_bot()
            
            if self.application is None:
                raise ValueError("❌ Application이 초기화되지 않았습니다.")
            
            # 전달받은 핸들러 맵 상세 검증
            self.logger.info(f"🔍 전달받은 핸들러 맵 상세 검증:")
            self.logger.info(f"  - 총 핸들러 수: {len(handlers_map)}개")
            for key, handler in handlers_map.items():
                handler_type = type(handler).__name__
                is_callable = callable(handler)
                module = getattr(handler, '__module__', 'unknown') if handler else 'None'
                self.logger.info(f"  - {key}: {handler_type} ({'호출가능' if is_callable else '호출불가'}) from {module}")
                
                if not is_callable and handler is not None:
                    self.logger.error(f"  ❌ {key} 핸들러가 호출 가능한 함수가 아닙니다!")
            
            # 기존 핸들러 모두 제거
            self.logger.info("🗑️ 기존 핸들러 모두 제거")
            self.application.handlers.clear()
            
            # 핸들러 등록 전 상태 확인
            self.logger.info(f"🔍 Application 상태 확인:")
            self.logger.info(f"  - Application 객체: {type(self.application)}")
            self.logger.info(f"  - 핸들러 그룹 수: {len(self.application.handlers)}")
            
            # 명령어 핸들러들을 먼저 등록 (높은 우선순위: 0)
            command_handlers = [
                ('start', handlers_map.get('start')),
                ('help', handlers_map.get('help')),
                ('debug', handlers_map.get('debug')),      # 🔥 디버그 핸들러 우선 등록
                ('test', handlers_map.get('test')),        # 🔥 테스트 핸들러 우선 등록
                ('mirror', handlers_map.get('mirror')),
                ('ratio', handlers_map.get('ratio')),
                ('report', handlers_map.get('report')),
                ('forecast', handlers_map.get('forecast')),
                ('profit', handlers_map.get('profit')),
                ('schedule', handlers_map.get('schedule')),
                ('stats', handlers_map.get('stats')),
            ]
            
            registered_commands = []
            failed_commands = []
            
            for command, handler_func in command_handlers:
                try:
                    if handler_func and callable(handler_func):
                        # 디버깅 래퍼로 핸들러 감싸기
                        wrapped_handler = self._create_debug_wrapper(command, handler_func)
                        command_handler = CommandHandler(command, wrapped_handler)
                        
                        # 핸들러 등록
                        self.application.add_handler(command_handler, 0)  # 높은 우선순위
                        registered_commands.append(command)
                        self.logger.info(f"✅ 명령어 핸들러 등록 성공: /{command} (우선순위: 0)")
                    elif handler_func:
                        failed_commands.append(f"{command}: 함수가 아님 ({type(handler_func)})")
                        self.logger.error(f"❌ /{command} 핸들러가 함수가 아님: {type(handler_func)}")
                    else:
                        failed_commands.append(f"{command}: 핸들러 없음")
                        self.logger.warning(f"⚠️ /{command} 핸들러 함수 없음")
                except Exception as handler_error:
                    failed_commands.append(f"{command}: 등록 실패 ({str(handler_error)})")
                    self.logger.error(f"❌ /{command} 핸들러 등록 실패: {handler_error}")
            
            # 메시지 핸들러를 낮은 우선순위로 등록 (낮은 우선순위: 1)
            message_handler_func = handlers_map.get('message_handler')
            message_handler_registered = False
            
            try:
                if message_handler_func and callable(message_handler_func):
                    wrapped_message_handler = self._create_debug_wrapper('message', message_handler_func)
                    message_handler = MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        wrapped_message_handler
                    )
                    self.application.add_handler(message_handler, 1)  # 낮은 우선순위
                    message_handler_registered = True
                    self.logger.info(f"✅ 메시지 핸들러 등록 성공 (우선순위: 1)")
                elif message_handler_func:
                    self.logger.error(f"❌ 메시지 핸들러가 함수가 아님: {type(message_handler_func)}")
                else:
                    self.logger.warning("⚠️ 메시지 핸들러 함수 없음")
            except Exception as msg_handler_error:
                self.logger.error(f"❌ 메시지 핸들러 등록 실패: {msg_handler_error}")
            
            # 등록 결과 요약
            total_registered = len(registered_commands) + (1 if message_handler_registered else 0)
            self.logger.info("=" * 50)
            self.logger.info(f"📊 핸들러 등록 결과 요약:")
            self.logger.info(f"  ✅ 성공한 명령어: {len(registered_commands)}개 - {', '.join(registered_commands)}")
            self.logger.info(f"  ✅ 메시지 핸들러: {'등록됨' if message_handler_registered else '실패'}")
            self.logger.info(f"  📋 총 등록된 핸들러: {total_registered}개")
            
            if failed_commands:
                self.logger.error(f"  ❌ 실패한 핸들러: {len(failed_commands)}개")
                for failed in failed_commands:
                    self.logger.error(f"    - {failed}")
            
            if total_registered == 0:
                raise ValueError("❌ 등록된 핸들러가 하나도 없습니다!")
            
            self._handlers_registered = True
            self.logger.info("=" * 50)
            
            # 등록된 핸들러 최종 검증
            self._verify_handlers()
            
        except Exception as e:
            self.logger.error(f"❌ 핸들러 등록 실패: {str(e)}")
            self.logger.error(f"핸들러 등록 오류 상세: {traceback.format_exc()}")
            raise
    
    def _create_debug_wrapper(self, handler_name: str, original_handler):
        """핸들러를 디버깅 래퍼로 감싸기"""
        async def debug_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            try:
                self.debug_stats['last_activity'] = datetime.now()
                
                if handler_name in self.debug_stats['handler_calls']:
                    self.debug_stats['handler_calls'][handler_name] += 1
                else:
                    self.debug_stats['handler_calls'][handler_name] = 1
                
                # 사용자 정보 상세 로깅
                user = update.effective_user
                chat = update.effective_chat
                
                self.logger.info("=" * 30)
                self.logger.info(f"🔥 핸들러 호출됨: {handler_name}")
                self.logger.info(f"👤 사용자: {user.username or user.first_name} (ID: {user.id})")
                self.logger.info(f"💬 채팅: {chat.type} (ID: {chat.id})")
                
                if handler_name == 'message':
                    self.debug_stats['messages_received'] += 1
                    message_text = update.message.text if update.message else 'No text'
                    self.logger.info(f"📝 메시지: '{message_text[:100]}...'")
                else:
                    self.debug_stats['commands_received'] += 1
                    command_args = context.args if context.args else []
                    self.logger.info(f"⚡ 명령어: /{handler_name} {' '.join(command_args)}")
                
                self.logger.info("=" * 30)
                
                # 원본 핸들러 실행
                await original_handler(update, context)
                
                self.logger.info(f"✅ 핸들러 실행 완료: {handler_name}")
                
            except Exception as e:
                error_info = {
                    'handler': handler_name,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat(),
                    'message': update.message.text if update.message else 'No message',
                    'user_id': update.effective_user.id if update.effective_user else 'Unknown',
                    'chat_id': update.effective_chat.id if update.effective_chat else 'Unknown'
                }
                self.debug_stats['errors'].append(error_info)
                
                self.logger.error(f"❌ 핸들러 실행 오류: {handler_name}")
                self.logger.error(f"오류 내용: {str(e)}")
                self.logger.error(f"사용자: {error_info['user_id']}, 채팅: {error_info['chat_id']}")
                self.logger.error(f"핸들러 오류 상세: {traceback.format_exc()}")
                
                # 오류 응답 전송
                try:
                    await update.message.reply_text(
                        f"❌ 명령어 처리 중 오류가 발생했습니다.\n"
                        f"핸들러: {handler_name}\n"
                        f"오류: {str(e)[:100]}\n"
                        f"시간: {datetime.now().strftime('%H:%M:%S')}",
                        reply_markup=ReplyKeyboardRemove()
                    )
                except Exception as reply_error:
                    self.logger.error(f"오류 응답 전송 실패: {reply_error}")
        
        return debug_wrapper
    
    def _verify_handlers(self):
        """핸들러 등록 검증 - 상세 버전"""
        try:
            self.logger.info("🔍 핸들러 등록 상세 검증 시작")
            
            total_handlers = 0
            command_handlers = 0
            message_handlers = 0
            
            for group_idx, group in enumerate(self.application.handlers):
                self.logger.info(f"  📁 핸들러 그룹 {group_idx}: {len(group)}개")
                
                for idx, handler in enumerate(group):
                    total_handlers += 1
                    
                    if isinstance(handler, CommandHandler):
                        command_handlers += 1
                        commands = ', '.join(handler.commands) if hasattr(handler, 'commands') else 'unknown'
                        callback_name = handler.callback.__name__ if hasattr(handler.callback, '__name__') else 'unknown'
                        self.logger.info(f"    ✅ [{idx}] 명령어: /{commands} → {callback_name}")
                        
                        # 중요 명령어 확인
                        if any(cmd in ['debug', 'test', 'help', 'start'] for cmd in handler.commands):
                            self.logger.info(f"      🎯 중요 명령어 확인됨: /{commands}")
                            
                    elif isinstance(handler, MessageHandler):
                        message_handlers += 1
                        callback_name = handler.callback.__name__ if hasattr(handler.callback, '__name__') else 'unknown'
                        self.logger.info(f"    ✅ [{idx}] 메시지 핸들러 → {callback_name}")
                    else:
                        self.logger.info(f"    ❓ [{idx}] 기타 핸들러: {type(handler).__name__}")
            
            # 검증 결과 요약
            self.logger.info("📊 핸들러 검증 결과:")
            self.logger.info(f"  - 총 핸들러: {total_handlers}개")
            self.logger.info(f"  - 명령어 핸들러: {command_handlers}개")  
            self.logger.info(f"  - 메시지 핸들러: {message_handlers}개")
            
            # 필수 핸들러 확인
            essential_commands = ['debug', 'test', 'help', 'start']
            found_essential = []
            
            for group in self.application.handlers:
                for handler in group:
                    if isinstance(handler, CommandHandler):
                        for cmd in essential_commands:
                            if cmd in handler.commands:
                                found_essential.append(cmd)
            
            self.logger.info(f"  - 필수 명령어: {len(found_essential)}/{len(essential_commands)}개 ({', '.join(found_essential)})")
            
            if total_handlers == 0:
                raise ValueError("❌ 등록된 핸들러가 없습니다!")
            
            if command_handlers == 0:
                raise ValueError("❌ 명령어 핸들러가 없습니다!")
            
            if len(found_essential) < 2:  # 최소 2개 이상의 필수 명령어
                self.logger.warning(f"⚠️ 필수 명령어가 부족합니다: {found_essential}")
            
            self.logger.info("✅ 핸들러 검증 완료")
            
        except Exception as e:
            self.logger.error(f"❌ 핸들러 검증 실패: {e}")
            raise
    
    async def start(self):
        """봇 시작 - 강화된 디버깅 및 검증"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("🚀 텔레그램 봇 시작 프로세스 시작 - 완전 진단 모드")
            self.logger.info("=" * 60)
            
            # 1. 초기화 확인
            if not self._is_initialized:
                self.logger.info("🔄 봇이 초기화되지 않음 - 초기화 시작")
                self._initialize_bot()
            
            if self.application is None:
                raise ValueError("❌ Application이 초기화되지 않았습니다.")
            
            # 2. 핸들러 확인
            if not self._handlers_registered:
                raise ValueError("❌ 핸들러가 등록되지 않았습니다! setup_handlers()를 먼저 호출하세요.")
            
            # 3. 핸들러 재검증
            self._verify_handlers()
            
            # 4. 환경변수 재확인
            await self._verify_environment_variables()
            
            # 5. 봇 실행 상태 설정
            self._is_running = True
            
            # 6. Application 초기화
            self.logger.info("🔄 Application 초기화 중...")
            await self.application.initialize()
            self.logger.info("✅ Application 초기화 완료")
            
            # 7. Application 시작
            self.logger.info("🔄 Application 시작 중...")
            await self.application.start()
            self.logger.info("✅ Application 시작 완료")
            
            # 8. 봇 정보 확인 및 권한 테스트
            await self._comprehensive_bot_test()
            
            # 9. 폴링 설정 및 시작
            await self._start_polling()
            
            # 10. 최종 성공 메시지
            self.logger.info("=" * 60)
            self.logger.info("🎉 텔레그램 봇 시작 완료 - 모든 검증 통과!")
            self.logger.info("📱 명령어 수신 대기 중...")
            self.logger.info("🔍 문제 발생 시 /debug 또는 /test 명령어 사용")
            self.logger.info("=" * 60)
            
            # 11. 시작 알림 메시지 전송
            await self._send_startup_notification()
            
        except Exception as e:
            self._is_running = False
            self._polling_started = False
            self.logger.error("=" * 60)
            self.logger.error(f"❌ 텔레그램 봇 시작 실패: {str(e)}")
            self.logger.error(f"봇 시작 오류 상세: {traceback.format_exc()}")
            self.logger.error("=" * 60)
            raise
    
    async def _verify_environment_variables(self):
        """환경변수 재검증"""
        try:
            self.logger.info("🔍 환경변수 최종 검증:")
            
            token = self.config.TELEGRAM_BOT_TOKEN
            chat_id = self.config.TELEGRAM_CHAT_ID
            
            # 토큰 검증
            if not token or ':' not in token:
                raise ValueError(f"❌ 잘못된 봇 토큰: {token[:20] if token else 'None'}...")
            
            token_parts = token.split(':')
            if len(token_parts) != 2:
                raise ValueError(f"❌ 봇 토큰 형식 오류: 2개 부분이 아님")
            
            bot_id = token_parts[0]
            if not bot_id.isdigit():
                raise ValueError(f"❌ 봇 ID가 숫자가 아님: {bot_id}")
            
            self.logger.info(f"  ✅ 봇 토큰: 유효 (봇 ID: {bot_id})")
            
            # 챗 ID 검증 및 변환
            if chat_id is None:
                raise ValueError("❌ TELEGRAM_CHAT_ID가 None입니다.")
            
            try:
                if isinstance(chat_id, str):
                    if chat_id.lstrip('-').isdigit():
                        chat_id_int = int(chat_id)
                    else:
                        raise ValueError(f"챗 ID가 숫자 문자열이 아님: '{chat_id}'")
                elif isinstance(chat_id, (int, float)):
                    chat_id_int = int(chat_id)
                else:
                    raise ValueError(f"챗 ID 타입 오류: {type(chat_id)}")
                
                self.logger.info(f"  ✅ 챗 ID: {chat_id_int} (타입: {type(chat_id_int).__name__})")
                
                # config 객체에 정수 형태로 저장
                self.config.TELEGRAM_CHAT_ID = chat_id_int
                
            except (ValueError, TypeError) as e:
                raise ValueError(f"❌ 챗 ID 변환 실패: {e}")
            
            self.logger.info("✅ 환경변수 검증 완료")
            
        except Exception as e:
            self.logger.error(f"❌ 환경변수 검증 실패: {e}")
            raise
    
    async def _comprehensive_bot_test(self):
        """포괄적인 봇 테스트"""
        try:
            self.logger.info("🔍 포괄적인 봇 연결 테스트 시작:")
            
            # 1. 봇 정보 확인
            self.logger.info("  1️⃣ 봇 정보 조회 중...")
            bot_info = await self.bot.get_me()
            
            self.logger.info(f"    🤖 봇 이름: {bot_info.first_name}")
            self.logger.info(f"    🏷️ 사용자명: @{bot_info.username}")
            self.logger.info(f"    🆔 봇 ID: {bot_info.id}")
            self.logger.info(f"    🔐 봇 여부: {bot_info.is_bot}")
            self.logger.info(f"    🔗 딥링크: t.me/{bot_info.username}")
            
            if not bot_info.is_bot:
                raise ValueError("❌ 이것은 봇 계정이 아닙니다!")
            
            # 2. 채팅방 정보 확인
            self.logger.info("  2️⃣ 채팅방 정보 조회 중...")
            chat_id = self.config.TELEGRAM_CHAT_ID
            
            try:
                chat_info = await self.bot.get_chat(chat_id)
                
                self.logger.info(f"    💬 채팅 ID: {chat_info.id}")
                self.logger.info(f"    📝 채팅 타입: {chat_info.type}")
                
                if hasattr(chat_info, 'title') and chat_info.title:
                    self.logger.info(f"    🏷️ 채팅 제목: {chat_info.title}")
                if hasattr(chat_info, 'username') and chat_info.username:
                    self.logger.info(f"    🔗 채팅 사용자명: @{chat_info.username}")
                if hasattr(chat_info, 'description') and chat_info.description:
                    self.logger.info(f"    📄 채팅 설명: {chat_info.description[:50]}...")
                
                # 채팅 타입별 권한 확인
                if chat_info.type == 'private':
                    self.logger.info(f"    👤 개인 채팅 - 봇과 사용자 간 직접 대화")
                elif chat_info.type in ['group', 'supergroup']:
                    self.logger.info(f"    👥 그룹 채팅 - 다수 참여자")
                    
                    # 그룹에서 봇 권한 확인
                    try:
                        bot_member = await self.bot.get_chat_member(chat_id, bot_info.id)
                        self.logger.info(f"    🎭 봇 상태: {bot_member.status}")
                        
                        if bot_member.status in ['left', 'kicked']:
                            raise ValueError(f"❌ 봇이 그룹에서 제거됨: {bot_member.status}")
                        elif bot_member.status == 'restricted':
                            self.logger.warning(f"⚠️ 봇이 제한된 상태입니다.")
                        
                    except Exception as member_error:
                        self.logger.warning(f"⚠️ 봇 멤버 상태 확인 실패: {member_error}")
                        
                elif chat_info.type == 'channel':
                    self.logger.info(f"    📢 채널 - 브로드캐스트 모드")
                
            except Exception as chat_error:
                self.logger.error(f"    ❌ 채팅방 정보 조회 실패: {chat_error}")
                
                # 일반적인 오류 원인 안내
                if "chat not found" in str(chat_error).lower():
                    raise ValueError(f"❌ 채팅방을 찾을 수 없습니다. 챗 ID를 확인하세요: {chat_id}")
                elif "forbidden" in str(chat_error).lower():
                    raise ValueError(f"❌ 봇이 해당 채팅방에 접근할 권한이 없습니다: {chat_id}")
                else:
                    raise ValueError(f"❌ 채팅방 접근 실패: {chat_error}")
            
            # 3. 메시지 전송 테스트 (실제 전송하지 않고 권한만 확인)
            self.logger.info("  3️⃣ 메시지 전송 권한 확인...")
            try:
                # 실제로는 전송하지 않고 권한만 확인하는 방법이 없으므로
                # 아주 간단한 테스트 메시지를 전송하고 즉시 삭제 시도
                test_message = await self.bot.send_message(
                    chat_id=chat_id,
                    text="🔍 봇 연결 테스트 중...",
                    disable_notification=True
                )
                
                self.logger.info(f"    ✅ 테스트 메시지 전송 성공 (메시지 ID: {test_message.message_id})")
                
                # 즉시 삭제 시도 (권한이 있다면)
                try:
                    await asyncio.sleep(1)
                    await self.bot.delete_message(chat_id=chat_id, message_id=test_message.message_id)
                    self.logger.info(f"    🗑️ 테스트 메시지 삭제 완료")
                except Exception as delete_error:
                    self.logger.info(f"    ℹ️ 테스트 메시지 삭제 실패 (권한 부족): {delete_error}")
                
            except Exception as send_error:
                self.logger.error(f"    ❌ 메시지 전송 실패: {send_error}")
                
                if "chat not found" in str(send_error).lower():
                    raise ValueError(f"❌ 채팅방을 찾을 수 없습니다: {chat_id}")
                elif "bot was blocked" in str(send_error).lower():
                    raise ValueError(f"❌ 사용자가 봇을 차단했습니다.")
                elif "forbidden" in str(send_error).lower():
                    raise ValueError(f"❌ 봇이 메시지를 보낼 권한이 없습니다.")
                else:
                    raise ValueError(f"❌ 메시지 전송 테스트 실패: {send_error}")
            
            self.logger.info("✅ 포괄적인 봇 테스트 완료 - 모든 권한 확인됨")
            
        except Exception as e:
            self.logger.error(f"❌ 봇 테스트 실패: {e}")
            raise
    
    async def _start_polling(self):
        """폴링 시작 - 강화된 설정"""
        try:
            self.logger.info("🔄 텔레그램 폴링 시작 중...")
            
            # 폴링 설정
            polling_config = {
                'allowed_updates': Update.ALL_TYPES,
                'drop_pending_updates': True,  # 이전 업데이트 무시
                'timeout': 30,          # 30초 타임아웃
                'read_timeout': 25,     # 읽기 타임아웃
                'write_timeout': 25,    # 쓰기 타임아웃
                'connect_timeout': 25,  # 연결 타임아웃
                'pool_timeout': 25,     # 풀 타임아웃
            }
            
            self.logger.info(f"🔧 폴링 설정: {polling_config}")
            
            # 폴링 시작
            await self.application.updater.start_polling(**polling_config)
            self._polling_started = True
            
            self.logger.info("✅ 텔레그램 폴링 시작 완료")
            self.logger.info("👂 봇이 메시지를 수신하고 있습니다...")
            
            # 폴링 상태 확인
            await asyncio.sleep(2)
            if self.application.updater.running:
                self.logger.info("🟢 폴링 상태: 정상 실행 중")
            else:
                self.logger.warning("🟡 폴링 상태: 불확실")
            
        except Exception as e:
            self._polling_started = False
            self.logger.error(f"❌ 폴링 시작 실패: {e}")
            self.logger.error(f"폴링 오류 상세: {traceback.format_exc()}")
            raise
    
    async def _send_startup_notification(self):
        """시작 알림 메시지 전송"""
        try:
            self.logger.info("📤 시작 알림 메시지 전송 중...")
            
            startup_message = """🔥 텔레그램 봇이 완전히 시작되었습니다!

✅ 모든 시스템 검증 완료:
- 봇 토큰 ✅
- 채팅방 접근 ✅  
- 메시지 전송 ✅
- 핸들러 등록 ✅
- 폴링 시작 ✅

🧪 즉시 테스트 가능:
• /test - 기본 응답 확인
• /debug - 상세 진단 정보
• /help - 전체 도움말

🎮 주요 명령어:
• /mirror - 미러링 제어
• /ratio - 복제 비율
• /report - 분석 리포트
• /stats - 시스템 통계

💡 지금 바로 /test 를 입력해보세요!
모든 명령어가 즉시 응답해야 합니다."""

            await self.send_message(startup_message)
            self.logger.info("✅ 시작 알림 메시지 전송 완료")
            
            # 추가 진단 정보 전송 (선택적)
            await asyncio.sleep(2)
            await self._send_diagnostic_info()
            
        except Exception as e:
            self.logger.error(f"❌ 시작 알림 메시지 전송 실패: {e}")
            # 시작 과정은 계속 진행 (알림 실패가 전체를 중단시키지 않음)
    
    async def _send_diagnostic_info(self):
        """진단 정보 전송"""
        try:
            stats = self.get_debug_stats()
            
            diagnostic_message = f"""🔍 봇 진단 정보:

🤖 봇 상태:
- 초기화: {'✅' if stats['is_initialized'] else '❌'}
- 실행 중: {'✅' if stats['is_running'] else '❌'}
- 폴링: {'✅' if self._polling_started else '❌'}

📋 핸들러 현황:
- 등록됨: {'✅' if stats['handlers_registered'] else '❌'}
- 총 개수: {stats['total_handlers']}개

📊 활동 통계:
- 수신 메시지: {stats['messages_received']}개
- 수신 명령어: {stats['commands_received']}개
- 오류 발생: {len(stats['errors'])}건

⚡ 문제가 있다면:
1. /test 입력 → 기본 응답 확인
2. /debug 입력 → 상세 정보 확인

🎯 모든 명령어가 정상 작동해야 합니다!"""

            await self.send_message(diagnostic_message)
            
        except Exception as e:
            self.logger.error(f"진단 정보 전송 실패: {e}")
    
    def get_debug_stats(self):
        """디버깅 통계 반환"""
        return {
            **self.debug_stats,
            'is_running': self._is_running,
            'is_initialized': self._is_initialized,
            'handlers_registered': self._handlers_registered,
            'polling_started': self._polling_started,
            'total_handlers': sum(len(group) for group in self.application.handlers) if self.application else 0
        }
    
    async def send_debug_report(self):
        """디버깅 리포트 전송"""
        try:
            stats = self.get_debug_stats()
            
            report = f"""🔍 텔레그램 봇 상세 디버깅 리포트

📊 시스템 상태:
- 봇 초기화: {'✅' if stats['is_initialized'] else '❌'}
- 봇 실행 중: {'✅' if stats['is_running'] else '❌'}  
- 핸들러 등록: {'✅' if stats['handlers_registered'] else '❌'}
- 폴링 시작: {'✅' if stats['polling_started'] else '❌'}
- 총 핸들러: {stats['total_handlers']}개

📈 활동 통계:
- 수신 메시지: {stats['messages_received']}개
- 수신 명령어: {stats['commands_received']}개
- 마지막 활동: {stats['last_activity'].strftime('%H:%M:%S') if stats['last_activity'] else '없음'}

🎯 핸들러 호출 현황:"""
            
            if stats['handler_calls']:
                for handler_name, count in stats['handler_calls'].items():
                    report += f"\n- {handler_name}: {count}회"
            else:
                report += "\n- 아직 호출된 핸들러 없음 ⚠️"
            
            report += f"""

❌ 오류 현황: {len(stats['errors'])}건"""
            
            if stats['errors']:
                report += "\n\n최근 오류:"
                for error in stats['errors'][-3:]:  # 최근 3개만
                    report += f"\n- {error['handler']}: {error['error'][:50]}..."
            
            report += """

🔧 문제 해결 가이드:
1. 모든 상태가 ✅ 인지 확인
2. 핸들러 호출 현황에 활동이 있는지 확인  
3. 오류가 있다면 세부 내용 분석

💡 /test 명령어로 기본 동작 확인하세요!"""
            
            await self.send_message(report)
            
        except Exception as e:
            self.logger.error(f"디버깅 리포트 전송 실패: {e}")
    
    async def stop(self):
        """봇 정지 - 안전한 종료"""
        try:
            self.logger.info("🔄 텔레그램 봇 정지 프로세스 시작...")
            
            if self.application:
                # 1. 봇 실행 상태를 False로 설정
                self._is_running = False
                self._polling_started = False
                
                # 2. 폴링 중지
                if self.application.updater and self.application.updater.running:
                    self.logger.info("🛑 폴링 중지 중...")
                    await self.application.updater.stop()
                    self.logger.info("✅ 폴링 중지 완료")
                
                # 3. Application 정지
                self.logger.info("🛑 Application 정지 중...")
                await self.application.stop()
                self.logger.info("✅ Application 정지 완료")
                
                # 4. Application 종료
                self.logger.info("🛑 Application 종료 중...")
                await self.application.shutdown()
                self.logger.info("✅ Application 종료 완료")
                
                self.logger.info("🎉 텔레그램 봇이 안전하게 정지되었습니다")
                
        except Exception as e:
            self.logger.error(f"❌ 텔레그램 봇 정지 실패: {str(e)}")
            self.logger.error(f"봇 정지 오류 상세: {traceback.format_exc()}")
    
    # 기존 핸들러 메서드들은 그대로 유지...
    async def handle_mirror_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """미러 트레이딩 상태 확인"""
        try:
            self.logger.info(f"🔥 미러링 상태 확인 요청 - 사용자: {update.effective_user.id}")
            
            if self.mirror_trading_system:
                current_info = await self.mirror_trading_system.get_current_mirror_mode()
                current_enabled = current_info['enabled']
                description = current_info['description']
                ratio_multiplier = current_info.get('ratio_multiplier', 1.0)
            elif self.system_reference and hasattr(self.system_reference, 'get_mirror_mode'):
                current_enabled = self.system_reference.get_mirror_mode()
                description = '활성화' if current_enabled else '비활성화'
                ratio_multiplier = 1.0
                if self.mirror_trading_system:
                    ratio_multiplier = self.mirror_trading_system.mirror_ratio_multiplier
            else:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return
            
            status_emoji = "✅" if current_enabled else "⏸️"
            status_color = "🟢" if current_enabled else "🔴"
            
            await update.message.reply_text(
                f"{status_emoji} 현재 미러링 상태\n\n"
                f"{status_color} 미러링: {description}\n"
                f"🎯 복제 비율: {ratio_multiplier}x\n"
                f"💳 마진 모드: Cross (자동 유지)\n"
                f"🔄 적용 범위: {'모든 새로운 거래' if current_enabled else '미러링 중지'}\n\n"
                f"💡 사용법:\n"
                f"• 활성화: /mirror on\n"
                f"• 비활성화: /mirror off\n"
                f"• 상태 확인: /mirror\n"
                f"• 복제 비율: /ratio [숫자]\n\n"
                f"🚀 실시간 제어로 언제든 변경 가능합니다!",
                reply_markup=ReplyKeyboardRemove()
            )
            
        except Exception as e:
            self.logger.error(f"미러링 상태 조회 실패: {e}")
            await update.message.reply_text(
                f"❌ 미러링 상태 조회 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def handle_mirror_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """미러 명령어 처리"""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            
            self.logger.info(f"🔥 /mirror 명령어 수신 - 사용자: {user_id}, 인자: {context.args}")
            
            if not self.mirror_trading_system:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.\n"
                    "시스템 관리자에게 문의하세요.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return
            
            current_info = await self.mirror_trading_system.get_current_mirror_mode()
            current_enabled = current_info['enabled']
            description = current_info['description']
            ratio_multiplier = current_info.get('ratio_multiplier', 1.0)
            
            if context.args:
                arg = context.args[0].lower()
                
                if arg in ['on', 'o', '1', 'true', 'start', '활성화', '켜기', '시작']:
                    new_mode = True
                    mode_text = "활성화"
                elif arg in ['off', 'x', '0', 'false', 'stop', '비활성화', '끄기', '중지']:
                    new_mode = False
                    mode_text = "비활성화"
                elif arg in ['status', 'check', 'info', '상태', '확인']:
                    await self._show_current_mirror_status(update)
                    return
                else:
                    await update.message.reply_text(
                        f"❌ 올바르지 않은 옵션: '{arg}'\n\n"
                        f"💡 사용법:\n"
                        f"• 활성화: /mirror on (또는 o, 1, start)\n"
                        f"• 비활성화: /mirror off (또는 x, 0, stop)\n"
                        f"• 상태 확인: /mirror status\n"
                        f"• 현재 상태: /mirror",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return
                
                if new_mode == current_enabled:
                    status_emoji = "✅" if new_mode else "⏸️"
                    await update.message.reply_text(
                        f"{status_emoji} 이미 해당 모드로 설정되어 있습니다.\n"
                        f"현재 상태: {description}\n"
                        f"복제 비율: {ratio_multiplier}x",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return
                
                from datetime import datetime, timedelta
                
                self.pending_mirror_confirmations[user_id] = {
                    'mode': new_mode,
                    'timestamp': datetime.now(),
                    'chat_id': chat_id
                }
                
                change_description = f"{'비활성화' if current_enabled else '활성화'} → {mode_text}"
                
                if new_mode:
                    impact_info = (
                        "🔥 모든 새로운 포지션과 예약 주문이 즉시 미러링됩니다.\n"
                        "⚡ 기존 활성 주문은 영향받지 않습니다.\n"
                        "💳 게이트 마진 모드가 Cross로 자동 설정됩니다.\n"
                        "🎯 완벽한 TP/SL 미러링이 활성화됩니다."
                    )
                    warning_info = "⚠️ 활성화 후 모든 거래가 자동 복제됩니다!"
                else:
                    impact_info = (
                        "⏸️ 모든 미러링이 중지됩니다.\n"
                        "🛑 새로운 포지션과 예약 주문이 복제되지 않습니다.\n"
                        "💡 기존 활성 주문은 그대로 유지됩니다.\n"
                        "📊 모니터링은 계속 진행됩니다."
                    )
                    warning_info = "💡 비활성화 후에도 기존 주문은 유지됩니다."
                
                keyboard = [
                    [KeyboardButton("✅ 예, 변경합니다"), KeyboardButton("❌ 아니오, 취소")]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
                
                await update.message.reply_text(
                    f"🔄 미러링 모드 변경 확인\n\n"
                    f"📊 현재 설정:\n"
                    f"• 미러링: {description}\n"
                    f"• 복제 비율: {ratio_multiplier}x\n\n"
                    f"🎯 새로운 설정:\n"
                    f"• 미러링: {mode_text}\n"
                    f"• 변경: {change_description}\n\n"
                    f"📋 영향:\n"
                    f"{impact_info}\n\n"
                    f"{warning_info}\n\n"
                    f"💡 이 모드로 변경하시겠습니까?",
                    reply_markup=reply_markup
                )
                
                async def cleanup_mirror_confirmation():
                    await asyncio.sleep(60)
                    if user_id in self.pending_mirror_confirmations:
                        del self.pending_mirror_confirmations[user_id]
                
                asyncio.create_task(cleanup_mirror_confirmation())
                
            else:
                await self._show_current_mirror_status(update)
                
        except Exception as e:
            self.logger.error(f"미러링 명령어 처리 실패: {e}")
            self.logger.error(f"미러링 명령어 오류 상세: {traceback.format_exc()}")
            await update.message.reply_text(
                f"❌ 미러링 명령어 처리 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def _show_current_mirror_status(self, update: Update):
        """현재 미러링 상태 표시"""
        try:
            if not self.mirror_trading_system:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return
            
            current_info = await self.mirror_trading_system.get_current_mirror_mode()
            current_enabled = current_info['enabled']
            description = current_info['description']
            ratio_multiplier = current_info.get('ratio_multiplier', 1.0)
            
            status_emoji = "✅" if current_enabled else "⏸️"
            status_color = "🟢" if current_enabled else "🔴"
            
            await update.message.reply_text(
                f"{status_emoji} 현재 미러링 상태\n\n"
                f"{status_color} 미러링: {description}\n"
                f"🎯 복제 비율: {ratio_multiplier}x\n"
                f"💳 마진 모드: Cross (자동 유지)\n"
                f"🔄 적용 범위: {'모든 새로운 거래' if current_enabled else '미러링 중지'}\n\n"
                f"💡 사용법:\n"
                f"• 활성화: /mirror on\n"
                f"• 비활성화: /mirror off\n"
                f"• 상태 확인: /mirror\n"
                f"• 복제 비율: /ratio [숫자]\n\n"
                f"🚀 실시간 제어로 언제든 변경 가능합니다!",
                reply_markup=ReplyKeyboardRemove()
            )
            
        except Exception as e:
            self.logger.error(f"미러링 상태 표시 실패: {e}")
            await update.message.reply_text(
                f"❌ 상태 조회 실패: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def handle_mirror_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """미러링 모드 설정 확인 처리"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text.strip()
            
            if user_id not in self.pending_mirror_confirmations:
                return False
            
            pending_info = self.pending_mirror_confirmations[user_id]
            new_mode = pending_info['mode']
            
            from datetime import datetime, timedelta
            if datetime.now() - pending_info['timestamp'] > timedelta(minutes=1):
                del self.pending_mirror_confirmations[user_id]
                await update.message.reply_text(
                    "⏰ 미러링 설정 확인 시간이 만료되었습니다.\n"
                    "/mirror 명령어를 다시 사용해 주세요.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return True
            
            if "✅" in message_text or "예" in message_text:
                try:
                    if not self.mirror_trading_system:
                        await update.message.reply_text(
                            "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        return True
                    
                    result = await self.mirror_trading_system.set_mirror_mode(new_mode)
                    
                    if result['success']:
                        old_state = result['old_state']
                        new_state = result['new_state']
                        state_change = result['state_change']
                        
                        status_emoji = "✅" if new_state else "⏸️"
                        mode_text = "활성화" if new_state else "비활성화"
                        
                        margin_info = ""
                        if new_state:
                            try:
                                margin_success = await self.mirror_trading_system.gate_mirror.ensure_cross_margin_mode("BTC_USDT")
                                if margin_success:
                                    margin_info = "\n💳 게이트 마진 모드: Cross로 설정 완료"
                                else:
                                    margin_info = "\n⚠️ 게이트 마진 모드 설정 실패 (수동 확인 필요)"
                            except Exception as margin_error:
                                margin_info = f"\n⚠️ 마진 모드 확인 실패: {str(margin_error)[:100]}"
                        
                        await update.message.reply_text(
                            f"{status_emoji} 미러링 모드 변경 완료!\n\n"
                            f"📊 변경 사항:\n"
                            f"• {state_change}\n"
                            f"• 현재 상태: {mode_text}\n"
                            f"• 복제 비율: {self.mirror_trading_system.mirror_ratio_multiplier}x{margin_info}\n\n"
                            f"🔥 {'새로운 거래부터 즉시 미러링 시작!' if new_state else '미러링이 중지되었습니다.'}\n"
                            f"⚡ 기존 활성 주문은 영향받지 않습니다.\n"
                            f"📱 언제든 /mirror on/off로 실시간 제어 가능합니다.",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        
                        self.logger.info(f"텔레그램으로 미러링 모드 변경: {old_state} → {new_state} (사용자: {user_id})")
                        
                    else:
                        await update.message.reply_text(
                            f"❌ 미러링 모드 변경 실패\n"
                            f"오류: {result.get('error', '알 수 없는 오류')}\n"
                            f"현재 상태 유지: {result.get('current_state', '불명')}",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ 미러링 모드 적용 중 오류 발생\n"
                        f"오류: {str(e)[:200]}",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    
            elif "❌" in message_text or "아니" in message_text:
                current_status = "활성화" if self.mirror_trading_system.mirror_trading_enabled else "비활성화"
                await update.message.reply_text(
                    f"🚫 미러링 모드 변경이 취소되었습니다.\n"
                    f"현재 상태 유지: {current_status}",
                    reply_markup=ReplyKeyboardRemove()
                )
                
            else:
                await update.message.reply_text(
                    f"❓ 올바른 응답을 선택해 주세요.\n"
                    f"✅ 예, 변경합니다 또는 ❌ 아니오, 취소",
                    reply_markup=ReplyKeyboardRemove()
                )
                return True
            
            del self.pending_mirror_confirmations[user_id]
            return True
            
        except Exception as e:
            self.logger.error(f"미러링 확인 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 미러링 확인 처리 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()
            )
            return True
    
    async def handle_ratio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """복제 비율 실시간 조정"""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            
            self.logger.info(f"🔥 /ratio 명령어 수신 - 사용자: {user_id}, 인자: {context.args}")
            
            if not self.mirror_trading_system:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.\n"
                    "시스템 관리자에게 문의하세요.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return
            
            current_info = await self.mirror_trading_system.get_current_ratio_info()
            current_ratio = current_info['current_ratio']
            description = current_info['description']
            
            if context.args:
                try:
                    new_ratio_str = context.args[0]
                    
                    try:
                        new_ratio = float(new_ratio_str)
                    except ValueError:
                        await update.message.reply_text(
                            f"❌ 올바르지 않은 숫자 형식: '{new_ratio_str}'\n"
                            f"예시: /ratio 1.5",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        return
                    
                    if new_ratio < 0.1 or new_ratio > 10.0:
                        await update.message.reply_text(
                            f"❌ 배율 범위 초과: {new_ratio}\n"
                            f"허용 범위: 0.1 ~ 10.0\n"
                            f"현재 설정: {current_ratio}x",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        return
                    
                    if abs(new_ratio - current_ratio) < 0.01:
                        await update.message.reply_text(
                            f"💡 이미 해당 배율로 설정되어 있습니다.\n"
                            f"현재 배율: {current_ratio}x\n"
                            f"요청 배율: {new_ratio}x",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        return
                    
                    from datetime import datetime, timedelta
                    
                    self.pending_ratio_confirmations[user_id] = {
                        'ratio': new_ratio,
                        'timestamp': datetime.now(),
                        'chat_id': chat_id
                    }
                    
                    new_description = self.mirror_trading_system.utils.get_ratio_multiplier_description(new_ratio)
                    effect_analysis = self.mirror_trading_system.utils.analyze_ratio_multiplier_effect(
                        new_ratio, 0.1, 0.1 * new_ratio
                    )
                    
                    keyboard = [
                        [KeyboardButton("✅ 예, 적용합니다"), KeyboardButton("❌ 아니오, 취소")]
                    ]
                    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
                    
                    await update.message.reply_text(
                        f"🔄 복제 비율 변경 확인\n\n"
                        f"📊 현재 설정:\n"
                        f"• 배율: {current_ratio}x\n"
                        f"• 설명: {description}\n\n"
                        f"🎯 새로운 설정:\n"
                        f"• 배율: {new_ratio}x\n"
                        f"• 설명: {new_description}\n"
                        f"• 리스크: {effect_analysis['risk_level']}\n"
                        f"• 영향: {effect_analysis['impact']}\n"
                        f"• 권장사항: {effect_analysis['recommendation']}\n\n"
                        f"💡 이 배율로 설정하시겠습니까?\n"
                        f"새로운 예약 주문부터 즉시 적용됩니다.",
                        reply_markup=reply_markup
                    )
                    
                    async def cleanup_confirmation():
                        await asyncio.sleep(60)
                        if user_id in self.pending_ratio_confirmations:
                            del self.pending_ratio_confirmations[user_id]
                    
                    asyncio.create_task(cleanup_confirmation())
                    
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ 배율 변경 처리 중 오류 발생\n"
                        f"오류: {str(e)[:200]}\n"
                        f"현재 배율 유지: {current_ratio}x",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    
            else:
                await update.message.reply_text(
                    f"📊 현재 복제 비율 설정\n\n"
                    f"🎯 배율: {current_ratio}x\n"
                    f"📝 설명: {description}\n"
                    f"🔄 적용 상태: {'기본 비율' if current_ratio == 1.0 else '사용자 지정'}\n\n"
                    f"💡 사용법:\n"
                    f"• 현재 상태 확인: /ratio\n"
                    f"• 배율 변경: /ratio [숫자]\n"
                    f"• 예시: /ratio 1.5 (1.5배로 확대)\n"
                    f"• 예시: /ratio 0.5 (절반으로 축소)\n"
                    f"• 허용 범위: 0.1 ~ 10.0\n\n"
                    f"🔥 변경 시 새로운 예약 주문부터 즉시 적용됩니다.",
                    reply_markup=ReplyKeyboardRemove()
                )
                
        except Exception as e:
            self.logger.error(f"배율 명령어 처리 실패: {e}")
            self.logger.error(f"배율 명령어 오류 상세: {traceback.format_exc()}")
            await update.message.reply_text(
                f"❌ 배율 명령어 처리 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def handle_ratio_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """배율 설정 확인 처리"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text.strip()
            
            if user_id not in self.pending_ratio_confirmations:
                return False
            
            pending_info = self.pending_ratio_confirmations[user_id]
            new_ratio = pending_info['ratio']
            
            from datetime import datetime, timedelta
            if datetime.now() - pending_info['timestamp'] > timedelta(minutes=1):
                del self.pending_ratio_confirmations[user_id]
                await update.message.reply_text(
                    "⏰ 배율 설정 확인 시간이 만료되었습니다.\n"
                    "/ratio 명령어를 다시 사용해 주세요.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return True
            
            if "✅" in message_text or "예" in message_text:
                try:
                    if not self.mirror_trading_system:
                        await update.message.reply_text(
                            "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        return True
                    
                    result = await self.mirror_trading_system.set_ratio_multiplier(new_ratio)
                    
                    if result['success']:
                        old_ratio = result['old_ratio']
                        new_ratio = result['new_ratio']
                        description = result['description']
                        effect = result['effect']
                        
                        await update.message.reply_text(
                            f"✅ 복제 비율 변경 완료!\n\n"
                            f"📊 변경 사항:\n"
                            f"• 이전: {old_ratio}x → 새로운: {new_ratio}x\n"
                            f"• 설명: {description}\n"
                            f"• 리스크 레벨: {effect['risk_level']}\n"
                            f"• 영향: {effect['impact']}\n\n"
                            f"🔥 새로운 예약 주문부터 즉시 적용됩니다!\n"
                            f"⚡ 기존 활성 주문은 영향받지 않습니다.",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        
                        self.logger.info(f"텔레그램으로 복제 비율 변경: {old_ratio}x → {new_ratio}x (사용자: {user_id})")
                        
                    else:
                        await update.message.reply_text(
                            f"❌ 배율 변경 실패\n"
                            f"오류: {result.get('error', '알 수 없는 오류')}\n"
                            f"현재 배율 유지: {result.get('current_ratio', '불명')}x",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ 배율 적용 중 오류 발생\n"
                        f"오류: {str(e)[:200]}",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    
            elif "❌" in message_text or "아니" in message_text:
                await update.message.reply_text(
                    f"🚫 배율 변경이 취소되었습니다.\n"
                    f"현재 배율 유지: {self.mirror_trading_system.mirror_ratio_multiplier if self.mirror_trading_system else '불명'}x",
                    reply_markup=ReplyKeyboardRemove()
                )
                
            else:
                await update.message.reply_text(
                    f"❓ 올바른 응답을 선택해 주세요.\n"
                    f"✅ 예, 적용합니다 또는 ❌ 아니오, 취소",
                    reply_markup=ReplyKeyboardRemove()
                )
                return True
            
            del self.pending_ratio_confirmations[user_id]
            return True
            
        except Exception as e:
            self.logger.error(f"배율 확인 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 배율 확인 처리 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()
            )
            return True
    
    async def handle_universal_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """통합 메시지 핸들러 - 확인 메시지들을 우선 처리"""
        try:
            self.logger.info(f"🔥 통합 메시지 핸들러 수신: {update.message.text[:50]}...")
            
            # 1. 미러링 모드 확인 처리
            if await self.handle_mirror_confirmation(update, context):
                self.logger.info("미러링 확인 메시지 처리됨")
                return
            
            # 2. 배율 확인 처리
            if await self.handle_ratio_confirmation(update, context):
                self.logger.info("배율 확인 메시지 처리됨")
                return
            
            # 3. 기타 메시지는 main.py로 전달 (자연어 처리)
            if self.system_reference and hasattr(self.system_reference, 'handle_natural_language'):
                self.logger.info("자연어 처리를 위해 main.py로 전달")
                await self.system_reference.handle_natural_language(update, context)
            else:
                self.logger.warning("시스템 참조가 없거나 자연어 처리 함수가 없음")
                await update.message.reply_text(
                    "죄송합니다. 이해하지 못했습니다. 🤔\n\n"
                    "사용 가능한 명령어:\n"
                    "• /help - 도움말\n"
                    "• /mirror - 미러링 상태\n"
                    "• /ratio - 복제 비율\n"
                    "• /report - 분석 리포트\n"
                    "• /stats - 시스템 통계",
                    reply_markup=ReplyKeyboardRemove()
                )
            
        except Exception as e:
            self.logger.error(f"통합 메시지 처리 실패: {e}")
            self.logger.error(f"통합 메시지 처리 오류 상세: {traceback.format_exc()}")
            await update.message.reply_text(
                "❌ 메시지 처리 중 오류가 발생했습니다.",
                reply_markup=ReplyKeyboardRemove()
            )
    
    def _clean_html_message(self, text: str) -> str:
        """HTML 메시지 정리 및 검증"""
        try:
            if not text:
                return "빈 메시지"
            
            text = str(text)
            
            # 빈 태그 제거
            text = re.sub(r'<\s*>', '', text)
            text = re.sub(r'<\s*/\s*>', '', text)
            text = re.sub(r'<\s+/?\s*>', '', text)
            
            # 깨진 태그 수정
            text = re.sub(r'<([^>]*?)(?=<|$)', r'', text)
            text = re.sub(r'(?<!>)>([^<]*?)>', r'\1', text)
            
            # 허용되는 HTML 태그만 유지
            allowed_tags = ['b', 'i', 'u', 's', 'code', 'pre', 'a']
            
            for tag in ['span', 'div', 'p', 'br', 'em', 'strong']:
                text = re.sub(f'</?{tag}[^>]*>', '', text)
            
            # 중첩된 동일 태그 정리
            for tag in allowed_tags:
                pattern = f'<{tag}[^>]*>(<{tag}[^>]*>.*?</{tag}>)</{tag}>'
                text = re.sub(pattern, r'\1', text)
            
            # 빈 태그 제거
            for tag in allowed_tags:
                text = re.sub(f'<{tag}[^>]*>\\s*</{tag}>', '', text)
            
            # 특수문자 이스케이프
            text = re.sub(r'&(?!(?:amp|lt|gt|quot|#\d+|#x[0-9a-fA-F]+);)', '&amp;', text)
            
            # 연속된 공백 정리
            text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
            text = re.sub(r' {3,}', '  ', text)
            
            # 메시지 길이 체크
            if len(text) > 4000:
                text = text[:3950] + "\n\n... (메시지가 잘림)"
            
            return text.strip()
            
        except Exception as e:
            self.logger.error(f"HTML 메시지 정리 실패: {e}")
            return re.sub(r'<[^>]+>', '', str(text))
    
    def _validate_html_structure(self, text: str) -> bool:
        """HTML 구조 검증"""
        try:
            if not text or text.isspace():
                return False
            
            allowed_tags = ['b', 'i', 'u', 's', 'code', 'pre']
            tag_stack = []
            
            tag_pattern = r'<(/?)([a-zA-Z]+)[^>]*>'
            
            for match in re.finditer(tag_pattern, text):
                is_closing = bool(match.group(1))
                tag_name = match.group(2).lower()
                
                if tag_name in allowed_tags:
                    if is_closing:
                        if tag_stack and tag_stack[-1] == tag_name:
                            tag_stack.pop()
                        else:
                            return False
                    else:
                        tag_stack.append(tag_name)
            
            return len(tag_stack) == 0
            
        except Exception as e:
            self.logger.debug(f"HTML 구조 검증 오류: {e}")
            return False
    
    async def send_message(self, text: str, chat_id: str = None, parse_mode: str = 'HTML'):
        """강화된 메시지 전송 - 상세한 오류 처리"""
        try:
            if chat_id is None:
                chat_id = self.config.TELEGRAM_CHAT_ID
            
            if self.bot is None:
                self.logger.warning("봇이 초기화되지 않음 - 초기화 시작")
                self._initialize_bot()
            
            self.logger.debug(f"메시지 전송 시도: {len(str(text))}자, 채팅 ID: {chat_id}")
            
            original_text = str(text)
            
            # 1차: HTML 정리 및 전송 시도
            if parse_mode == 'HTML':
                try:
                    cleaned_text = self._clean_html_message(text)
                    
                    if self._validate_html_structure(cleaned_text):
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=cleaned_text,
                            parse_mode='HTML',
                            reply_markup=ReplyKeyboardRemove(),
                            disable_web_page_preview=True
                        )
                        self.logger.debug("HTML 모드 메시지 전송 성공")
                        return
                    else:
                        self.logger.warning("HTML 구조 검증 실패, 텍스트 모드로 전환")
                except Exception as html_error:
                    self.logger.warning(f"HTML 모드 전송 실패: {html_error}")
            
            # 2차: HTML 태그 완전 제거하고 텍스트로 전송
            try:
                text_only = re.sub(r'<[^>]+>', '', original_text)
                text_only = text_only.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                text_only = text_only.replace('&quot;', '"').replace('&#39;', "'")
                
                text_only = re.sub(r'\n\s*\n\s*\n', '\n\n', text_only)
                text_only = re.sub(r' {3,}', '  ', text_only)
                
                if len(text_only) > 4000:
                    text_only = text_only[:3950] + "\n\n... (메시지가 잘림)"
                
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text_only.strip(),
                    reply_markup=ReplyKeyboardRemove(),
                    disable_web_page_preview=True
                )
                self.logger.debug("텍스트 모드 메시지 전송 성공")
                return
                
            except Exception as text_error:
                self.logger.error(f"텍스트 모드 전송도 실패: {text_error}")
                
                # 오류 유형별 세부 처리
                error_msg = str(text_error).lower()
                if "chat not found" in error_msg:
                    raise ValueError(f"❌ 채팅방을 찾을 수 없습니다: {chat_id}")
                elif "bot was blocked" in error_msg:
                    raise ValueError(f"❌ 사용자가 봇을 차단했습니다")
                elif "forbidden" in error_msg:
                    raise ValueError(f"❌ 봇이 메시지를 보낼 권한이 없습니다")
                elif "message is too long" in error_msg:
                    self.logger.warning("메시지가 너무 길어서 분할 시도")
                    await self._send_long_message(original_text, chat_id)
                    return
                else:
                    raise text_error
            
            # 3차: 최후 수단 - 폴백 메시지
            try:
                current_time = datetime.now().strftime('%H:%M:%S')
                fallback_message = f"""🚨 메시지 전송 오류 발생

원본 메시지가 올바르지 않은 형식을 포함하고 있어 전송에 실패했습니다.

시간: {current_time}
길이: {len(original_text)}자

시스템이 정상 작동 중이며, 다음 메시지부터는 정상 전송될 예정입니다.

문제가 계속되면 /debug 명령어로 확인하세요."""

                await self.bot.send_message(
                    chat_id=chat_id,
                    text=fallback_message,
                    reply_markup=ReplyKeyboardRemove()
                )
                self.logger.warning("폴백 메시지 전송 완료")
                
            except Exception as fallback_error:
                self.logger.error(f"폴백 메시지 전송도 실패: {fallback_error}")
                raise fallback_error
            
        except Exception as e:
            self.logger.error(f"메시지 전송 최종 실패: {str(e)}")
            self.logger.error(f"원본 메시지 (처음 300자): {str(text)[:300]}")
            self.logger.error(f"채팅 ID: {chat_id}")
            self.logger.error(f"메시지 전송 오류 상세: {traceback.format_exc()}")
            raise
    
    async def _send_long_message(self, text: str, chat_id: str):
        """긴 메시지 분할 전송"""
        try:
            # 4000자 단위로 분할
            max_length = 3800  # 여유 공간 확보
            text_parts = []
            
            lines = text.split('\n')
            current_part = ""
            
            for line in lines:
                if len(current_part) + len(line) + 1 > max_length:
                    if current_part:
                        text_parts.append(current_part.strip())
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'
            
            if current_part:
                text_parts.append(current_part.strip())
            
            # 분할된 메시지 전송
            for i, part in enumerate(text_parts):
                if i > 0:
                    part = f"📄 ({i+1}/{len(text_parts)})\n\n" + part
                
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=part,
                    reply_markup=ReplyKeyboardRemove()
                )
                
                if i < len(text_parts) - 1:
                    await asyncio.sleep(1)  # 전송 간격 조절
            
            self.logger.info(f"긴 메시지 분할 전송 완료: {len(text_parts)}개 부분")
            
        except Exception as e:
            self.logger.error(f"긴 메시지 분할 전송 실패: {e}")
            raise
