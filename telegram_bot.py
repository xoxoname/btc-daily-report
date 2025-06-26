import logging
from telegram import Bot, Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
        self.mirror_trading_system = None
        self._initialize_bot()
        
        # 🔥🔥🔥 대기 상태 관리 - 각 기능별로 분리
        self.pending_ratio_confirmations = {}  # user_id: {'ratio': float, 'timestamp': datetime}
        self.pending_mirror_confirmations = {}  # user_id: {'action': str, 'timestamp': datetime}
        
    def _initialize_bot(self):
        """봇 초기화"""
        try:
            telegram_token = self.config.TELEGRAM_BOT_TOKEN
            if not telegram_token:
                raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
            
            self.bot = Bot(token=telegram_token)
            self.application = Application.builder().token(telegram_token).build()
            
            self.logger.info("텔레그램 봇 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"텔레그램 봇 초기화 실패: {str(e)}")
            raise
    
    def set_mirror_trading_system(self, mirror_system):
        """🔥🔥🔥 미러 트레이딩 시스템 참조 설정"""
        self.mirror_trading_system = mirror_system
        self.logger.info("미러 트레이딩 시스템 참조 설정 완료")
    
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
    
    async def handle_mirror_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔥🔥🔥 /mirror 명령어 처리 - 미러 트레이딩 활성화/비활성화"""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            
            # 미러 트레이딩 시스템 참조 확인
            if not self.mirror_trading_system:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.\n"
                    "시스템 관리자에게 문의하세요.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return
            
            # 현재 미러링 모드 정보 조회
            current_info = await self.mirror_trading_system.get_current_mirror_mode()
            current_enabled = current_info['enabled']
            description = current_info['description']
            
            # 파라미터 확인
            if context.args:
                arg = context.args[0].lower()
                
                if arg in ['on', 'enable', 'start', '1', 'o', 'true', 'yes']:
                    # 활성화 요청
                    if current_enabled:
                        await update.message.reply_text(
                            f"💡 이미 미러 트레이딩이 활성화되어 있습니다.\n"
                            f"현재 상태: {description}",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        return
                    
                    await self._request_mirror_confirmation(update, user_id, chat_id, True)
                    
                elif arg in ['off', 'disable', 'stop', '0', 'x', 'false', 'no']:
                    # 비활성화 요청
                    if not current_enabled:
                        await update.message.reply_text(
                            f"💡 이미 미러 트레이딩이 비활성화되어 있습니다.\n"
                            f"현재 상태: {description}",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        return
                    
                    await self._request_mirror_confirmation(update, user_id, chat_id, False)
                    
                elif arg in ['status', 'check', 'info']:
                    # 상태 확인
                    await self._show_mirror_status(update)
                    
                else:
                    await update.message.reply_text(
                        f"❌ 올바르지 않은 명령어: '{arg}'\n\n"
                        f"사용법:\n"
                        f"• /mirror on - 활성화\n"
                        f"• /mirror off - 비활성화\n"
                        f"• /mirror status - 상태 확인",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    
            else:
                # 파라미터 없음 - 상태 확인
                await self._show_mirror_status(update)
                
        except Exception as e:
            self.logger.error(f"미러 명령어 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 미러 명령어 처리 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def _request_mirror_confirmation(self, update: Update, user_id: int, chat_id: int, enable: bool):
        """🔥🔥🔥 미러 트레이딩 활성화/비활성화 확인 요청"""
        try:
            from datetime import datetime, timedelta
            
            # 기존 대기 상태 정리
            if user_id in self.pending_mirror_confirmations:
                del self.pending_mirror_confirmations[user_id]
            
            action = "활성화" if enable else "비활성화"
            action_english = "enable" if enable else "disable"
            
            # 대기 상태 저장
            self.pending_mirror_confirmations[user_id] = {
                'action': action_english,
                'enable': enable,
                'timestamp': datetime.now(),
                'chat_id': chat_id
            }
            
            # 현재 정보
            current_info = await self.mirror_trading_system.get_current_mirror_mode()
            ratio_info = await self.mirror_trading_system.get_current_ratio_info()
            
            # 확인 키보드 생성
            keyboard = [
                [KeyboardButton(f"✅ 예, {action}합니다"), KeyboardButton("❌ 아니오, 취소")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            warning_text = ""
            if not enable:
                warning_text = "\n⚠️ 비활성화하면 새로운 포지션과 예약 주문이 복제되지 않습니다."
            
            await update.message.reply_text(
                f"🔄 미러 트레이딩 {action} 확인\n\n"
                f"📊 현재 상태:\n"
                f"• 미러링: {current_info['description']}\n"
                f"• 복제 비율: {ratio_info['current_ratio']}x\n\n"
                f"🎯 요청 작업:\n"
                f"• 미러 트레이딩을 {action}하시겠습니까?\n"
                f"• 변경은 즉시 적용됩니다{warning_text}\n\n"
                f"💡 확인해주세요:",
                reply_markup=reply_markup
            )
            
            # 자동 만료 스케줄링
            async def cleanup_mirror_confirmation():
                await asyncio.sleep(60)  # 1분 후 만료
                if user_id in self.pending_mirror_confirmations:
                    del self.pending_mirror_confirmations[user_id]
            
            asyncio.create_task(cleanup_mirror_confirmation())
            
        except Exception as e:
            self.logger.error(f"미러 확인 요청 실패: {e}")
            await update.message.reply_text(
                f"❌ 확인 요청 실패\n오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def _show_mirror_status(self, update: Update):
        """미러 트레이딩 상태 표시"""
        try:
            current_info = await self.mirror_trading_system.get_current_mirror_mode()
            ratio_info = await self.mirror_trading_system.get_current_ratio_info()
            
            status_emoji = "✅" if current_info['enabled'] else "❌"
            
            await update.message.reply_text(
                f"📊 미러 트레이딩 현재 상태\n\n"
                f"🔄 미러링: {status_emoji} {current_info['description']}\n"
                f"📈 복제 비율: {ratio_info['current_ratio']}x\n"
                f"📝 비율 설명: {ratio_info['description']}\n\n"
                f"💡 제어 명령어:\n"
                f"• 활성화: /mirror on\n"
                f"• 비활성화: /mirror off\n"
                f"• 복제 비율 조정: /ratio [숫자]\n"
                f"• 수익 조회: /profit\n\n"
                f"🔥 실시간 제어가 가능합니다!",
                reply_markup=ReplyKeyboardRemove()
            )
            
        except Exception as e:
            self.logger.error(f"미러 상태 표시 실패: {e}")
            await update.message.reply_text(
                "❌ 상태 조회 실패",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def handle_ratio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔥🔥🔥 /ratio 명령어 처리 - 복제 비율 실시간 조정"""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            
            # 미러 트레이딩 시스템 참조 확인
            if not self.mirror_trading_system:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.\n"
                    "시스템 관리자에게 문의하세요.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return
            
            # 현재 배율 정보 조회
            current_info = await self.mirror_trading_system.get_current_ratio_info()
            current_ratio = current_info['current_ratio']
            description = current_info['description']
            
            # 파라미터 확인
            if context.args:
                # 배율 변경 시도
                try:
                    new_ratio_str = context.args[0]
                    
                    # 숫자 유효성 검증
                    try:
                        new_ratio = float(new_ratio_str)
                    except ValueError:
                        await update.message.reply_text(
                            f"❌ 올바르지 않은 숫자 형식: '{new_ratio_str}'\n"
                            f"예시: /ratio 1.5",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        return
                    
                    # 범위 확인 (사전 검증)
                    if new_ratio < 0.1 or new_ratio > 10.0:
                        await update.message.reply_text(
                            f"❌ 배율 범위 초과: {new_ratio}\n"
                            f"허용 범위: 0.1 ~ 10.0\n"
                            f"현재 설정: {current_ratio}x",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        return
                    
                    # 동일한 배율인지 확인
                    if abs(new_ratio - current_ratio) < 0.01:
                        await update.message.reply_text(
                            f"💡 이미 해당 배율로 설정되어 있습니다.\n"
                            f"현재 배율: {current_ratio}x\n"
                            f"요청 배율: {new_ratio}x",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        return
                    
                    await self._request_ratio_confirmation(update, user_id, chat_id, new_ratio)
                    
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ 배율 변경 처리 중 오류 발생\n"
                        f"오류: {str(e)[:200]}\n"
                        f"현재 배율 유지: {current_ratio}x",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    
            else:
                # 현재 배율 정보만 표시
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
            await update.message.reply_text(
                f"❌ 배율 명령어 처리 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def _request_ratio_confirmation(self, update: Update, user_id: int, chat_id: int, new_ratio: float):
        """🔥🔥🔥 배율 변경 확인 요청"""
        try:
            from datetime import datetime
            
            # 기존 대기 상태 정리
            if user_id in self.pending_ratio_confirmations:
                del self.pending_ratio_confirmations[user_id]
            
            # 대기 상태 저장
            self.pending_ratio_confirmations[user_id] = {
                'ratio': new_ratio,
                'timestamp': datetime.now(),
                'chat_id': chat_id
            }
            
            # 현재 정보
            current_info = await self.mirror_trading_system.get_current_ratio_info()
            current_ratio = current_info['current_ratio']
            description = current_info['description']
            
            # 새 배율 효과 미리 분석
            new_description = self.mirror_trading_system.utils.get_ratio_multiplier_description(new_ratio)
            effect_analysis = self.mirror_trading_system.utils.analyze_ratio_multiplier_effect(
                new_ratio, 0.1, 0.1 * new_ratio
            )
            
            # 확인 키보드 생성
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
            
            # 1분 후 자동 만료
            async def cleanup_ratio_confirmation():
                await asyncio.sleep(60)
                if user_id in self.pending_ratio_confirmations:
                    del self.pending_ratio_confirmations[user_id]
            
            asyncio.create_task(cleanup_ratio_confirmation())
            
        except Exception as e:
            self.logger.error(f"배율 확인 요청 실패: {e}")
            await update.message.reply_text(
                f"❌ 확인 요청 실패\n오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def handle_ratio_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔥🔥🔥 배율 설정 확인 처리"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text.strip()
            
            # 대기 중인 확인이 있는지 확인
            if user_id not in self.pending_ratio_confirmations:
                return False  # 이 메시지는 배율 확인과 관련 없음
            
            pending_info = self.pending_ratio_confirmations[user_id]
            new_ratio = pending_info['ratio']
            
            # 만료 확인 (1분 제한)
            from datetime import datetime, timedelta
            if datetime.now() - pending_info['timestamp'] > timedelta(minutes=1):
                del self.pending_ratio_confirmations[user_id]
                await update.message.reply_text(
                    "⏰ 배율 설정 확인 시간이 만료되었습니다.\n"
                    "/ratio 명령어를 다시 사용해 주세요.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return True
            
            # 확인 응답 처리
            if "✅" in message_text or "예" in message_text:
                # 배율 적용
                try:
                    if not self.mirror_trading_system:
                        await update.message.reply_text(
                            "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        del self.pending_ratio_confirmations[user_id]
                        return True
                    
                    # 실제 배율 변경 실행
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
                # 취소
                await update.message.reply_text(
                    f"🚫 배율 변경이 취소되었습니다.\n"
                    f"현재 배율 유지: {self.mirror_trading_system.mirror_ratio_multiplier if self.mirror_trading_system else '불명'}x",
                    reply_markup=ReplyKeyboardRemove()
                )
                
            else:
                # 잘못된 응답 - 키보드 다시 표시하지 않고 메시지만
                await update.message.reply_text(
                    f"❓ 올바른 응답을 선택해 주세요.\n"
                    f"'✅ 예, 적용합니다' 또는 '❌ 아니오, 취소'를 선택하거나\n"
                    f"/ratio 명령어를 다시 입력해주세요.",
                    reply_markup=ReplyKeyboardRemove()
                )
                del self.pending_ratio_confirmations[user_id]
                return True
            
            # 확인 상태 정리
            del self.pending_ratio_confirmations[user_id]
            return True
            
        except Exception as e:
            self.logger.error(f"배율 확인 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 배율 확인 처리 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()
            )
            # 확인 상태 정리
            if user_id in self.pending_ratio_confirmations:
                del self.pending_ratio_confirmations[user_id]
            return True
    
    async def handle_mirror_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔥🔥🔥 미러 트레이딩 활성화/비활성화 확인 처리"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text.strip()
            
            # 대기 중인 확인이 있는지 확인
            if user_id not in self.pending_mirror_confirmations:
                return False  # 이 메시지는 미러 확인과 관련 없음
            
            pending_info = self.pending_mirror_confirmations[user_id]
            action = pending_info['action']
            enable = pending_info['enable']
            action_ko = "활성화" if enable else "비활성화"
            
            # 만료 확인 (1분 제한)
            from datetime import datetime, timedelta
            if datetime.now() - pending_info['timestamp'] > timedelta(minutes=1):
                del self.pending_mirror_confirmations[user_id]
                await update.message.reply_text(
                    "⏰ 미러 트레이딩 설정 확인 시간이 만료되었습니다.\n"
                    "/mirror 명령어를 다시 사용해 주세요.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return True
            
            # 확인 응답 처리
            if "✅" in message_text or "예" in message_text:
                # 미러링 모드 변경 적용
                try:
                    if not self.mirror_trading_system:
                        await update.message.reply_text(
                            "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        del self.pending_mirror_confirmations[user_id]
                        return True
                    
                    # 실제 미러링 모드 변경 실행
                    result = await self.mirror_trading_system.set_mirror_mode(enable)
                    
                    if result['success']:
                        old_state = result['old_state']
                        new_state = result['new_state']
                        state_change = result['state_change']
                        
                        status_emoji = "✅" if new_state else "❌"
                        old_text = "활성화" if old_state else "비활성화"
                        new_text = "활성화" if new_state else "비활성화"
                        
                        await update.message.reply_text(
                            f"✅ 미러 트레이딩 {action_ko} 완료!\n\n"
                            f"📊 변경 사항:\n"
                            f"• 이전: {old_text} → 새로운: {status_emoji} {new_text}\n"
                            f"• 변경 내용: {state_change}\n\n"
                            f"🔥 {'새로운 포지션과 예약 주문이 즉시 복제됩니다!' if new_state else '새로운 복제가 중단되었습니다.'}\n"
                            f"⚡ 기존 활성 주문과 포지션은 그대로 유지됩니다.",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        
                        self.logger.info(f"텔레그램으로 미러링 모드 변경: {old_text} → {new_text} (사용자: {user_id})")
                        
                    else:
                        await update.message.reply_text(
                            f"❌ 미러 트레이딩 {action_ko} 실패\n"
                            f"오류: {result.get('error', '알 수 없는 오류')}\n"
                            f"현재 상태 유지",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ 미러 트레이딩 {action_ko} 중 오류 발생\n"
                        f"오류: {str(e)[:200]}",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    
            elif "❌" in message_text or "아니" in message_text:
                # 취소
                current_info = await self.mirror_trading_system.get_current_mirror_mode()
                await update.message.reply_text(
                    f"🚫 미러 트레이딩 {action_ko}이 취소되었습니다.\n"
                    f"현재 상태 유지: {current_info['description']}",
                    reply_markup=ReplyKeyboardRemove()
                )
                
            else:
                # 잘못된 응답 - 키보드 다시 표시하지 않고 메시지만
                await update.message.reply_text(
                    f"❓ 올바른 응답을 선택해 주세요.\n"
                    f"'✅ 예, {action_ko}합니다' 또는 '❌ 아니오, 취소'를 선택하거나\n"
                    f"/mirror 명령어를 다시 입력해주세요.",
                    reply_markup=ReplyKeyboardRemove()
                )
                del self.pending_mirror_confirmations[user_id]
                return True
            
            # 확인 상태 정리
            del self.pending_mirror_confirmations[user_id]
            return True
            
        except Exception as e:
            self.logger.error(f"미러 확인 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 미러 트레이딩 확인 처리 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()
            )
            # 확인 상태 정리
            if user_id in self.pending_mirror_confirmations:
                del self.pending_mirror_confirmations[user_id]
            return True
    
    async def handle_natural_language_enhanced(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔥🔥🔥 자연어 처리 강화 - 확인 메시지 우선 처리"""
        try:
            # 1순위: 배율 확인 메시지 처리
            if await self.handle_ratio_confirmation(update, context):
                return  # 배율 확인 메시지였으면 여기서 종료
            
            # 2순위: 미러 확인 메시지 처리
            if await self.handle_mirror_confirmation(update, context):
                return  # 미러 확인 메시지였으면 여기서 종료
            
            # 3순위: 일반 자연어 처리는 기존 핸들러에 위임
            # (main.py의 handle_natural_language 호출됨)
            return False  # 다른 핸들러가 처리하도록
            
        except Exception as e:
            self.logger.error(f"강화된 자연어 처리 실패: {e}")
            await update.message.reply_text(
                "❌ 메시지 처리 중 오류가 발생했습니다.",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def handle_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """도움말 명령어 처리"""
        try:
            help_text = """🤖 미러 트레이딩 봇 도움말

📊 미러 트레이딩 제어:
• /mirror - 현재 상태 확인
• /mirror on - 미러 트레이딩 활성화
• /mirror off - 미러 트레이딩 비활성화
• /mirror status - 상세 상태 조회

🎯 복제 비율 조정:
• /ratio - 현재 복제 비율 확인
• /ratio [숫자] - 복제 비율 변경
• 예시: /ratio 1.5 (1.5배로 확대)
• 예시: /ratio 0.5 (절반으로 축소)
• 허용 범위: 0.1 ~ 10.0배

💰 수익 및 상태:
• /profit - 수익 현황 조회
• /report - 전체 분석 리포트
• /forecast - 단기 예측 요약
• /stats - 시스템 통계

📋 복제 비율 설명:
• 0.1 ~ 0.4배: 매우 보수적 (리스크 최소)
• 0.5 ~ 0.9배: 보수적 (리스크 감소)
• 1.0배: 표준 (원본과 동일)
• 1.1 ~ 2.0배: 적극적 (리스크 증가)
• 2.1 ~ 5.0배: 공격적 (높은 리스크)
• 5.1 ~ 10.0배: 매우 공격적 (최고 리스크)

⚡ 실시간 적용:
• 모든 설정 변경은 즉시 적용
• 새로운 예약 주문부터 바로 반영
• 기존 활성 주문은 영향받지 않음
• 안전한 확인 절차 포함

🔥 시스템이 24시간 안전하게 작동합니다!"""
            
            await update.message.reply_text(help_text, reply_markup=ReplyKeyboardRemove())
            
        except Exception as e:
            self.logger.error(f"도움말 명령어 처리 실패: {e}")
            await update.message.reply_text(
                "❌ 도움말 표시 실패",
                reply_markup=ReplyKeyboardRemove()
            )
    
    def _clean_html_message(self, text: str) -> str:
        """🔥🔥 HTML 메시지 정리 및 검증"""
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
            
            # 허용되지 않는 태그를 일반 텍스트로 변환
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
        """🔥 HTML 구조 검증"""
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
        """🔥🔥 개선된 메시지 전송 - HTML 파싱 오류 완전 해결"""
        try:
            if chat_id is None:
                chat_id = self.config.TELEGRAM_CHAT_ID
            
            if self.bot is None:
                self._initialize_bot()
            
            original_text = str(text)
            
            # 1차: HTML 정리
            if parse_mode == 'HTML':
                cleaned_text = self._clean_html_message(text)
                
                if self._validate_html_structure(cleaned_text):
                    try:
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=cleaned_text,
                            parse_mode='HTML',
                            reply_markup=ReplyKeyboardRemove()
                        )
                        self.logger.info("HTML 메시지 전송 성공")
                        return
                    except Exception as html_error:
                        self.logger.warning(f"정리된 HTML 메시지 전송 실패: {html_error}")
                else:
                    self.logger.warning("HTML 구조 검증 실패, 텍스트 모드로 전환")
            
            # 2차: 텍스트 모드
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
                    reply_markup=ReplyKeyboardRemove()
                )
                self.logger.info("텍스트 모드 메시지 전송 성공")
                return
                
            except Exception as text_error:
                self.logger.error(f"텍스트 모드 전송도 실패: {text_error}")
            
            # 3차: 폴백 메시지
            try:
                fallback_message = f"""🚨 메시지 전송 오류 발생

원본 메시지가 올바르지 않은 형식을 포함하고 있어 전송에 실패했습니다.

시간: {str(text)[:100]}...

시스템이 정상 작동 중이며, 다음 메시지부터는 정상 전송될 예정입니다."""

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
            self.logger.error(f"원본 메시지 (처음 200자): {str(text)[:200]}")
            
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
                if "byte offset" in error_str:
                    offset_match = re.search(r'byte offset (\d+)', error_str)
                    if offset_match:
                        offset = int(offset_match.group(1))
                        problem_area = str(text)[max(0, offset-50):offset+50]
                        self.logger.error(f"문제 구간 (offset {offset} 주변): {repr(problem_area)}")
            
            raise
