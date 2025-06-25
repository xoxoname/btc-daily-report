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
        self.mirror_trading_system = None  # 미러 트레이딩 시스템 참조
        self.system_reference = None  # 메인 시스템 참조
        
        # 배율 설정 관련 상태 관리
        self.pending_ratio_confirmations = {}  # user_id: {'ratio': float, 'timestamp': datetime}
        
        # 🔥🔥🔥 미러링 모드 설정 관련 상태 관리
        self.pending_mirror_confirmations = {}  # user_id: {'mode': bool, 'timestamp': datetime}
        
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
            
            # 🔥🔥🔥 핸들러 자동 등록 (이 부분이 누락되어 있었음!)
            self._register_all_handlers()
            
            self.logger.info("텔레그램 봇 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"텔레그램 봇 초기화 실패: {str(e)}")
            raise
    
    def _register_all_handlers(self):
        """🔥🔥🔥 모든 핸들러 자동 등록 - 이 부분이 핵심 수정사항"""
        try:
            # 명령어 핸들러들 등록
            self.application.add_handler(CommandHandler("mirror", self.handle_mirror_command))
            self.application.add_handler(CommandHandler("ratio", self.handle_ratio_command))
            self.application.add_handler(CommandHandler("help", self.handle_help_command))
            self.application.add_handler(CommandHandler("start", self.handle_help_command))
            
            # 메시지 핸들러 등록 (확인 응답 처리 포함)
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            self.logger.info("🔥 모든 텔레그램 핸들러 자동 등록 완료")
            
        except Exception as e:
            self.logger.error(f"핸들러 자동 등록 실패: {str(e)}")
            raise
    
    def set_mirror_trading_system(self, mirror_system):
        """미러 트레이딩 시스템 참조 설정"""
        self.mirror_trading_system = mirror_system
        self.logger.info("미러 트레이딩 시스템 참조 설정 완료")
    
    def set_system_reference(self, system):
        """메인 시스템 참조 설정"""
        self.system_reference = system
        self.logger.info("메인 시스템 참조 설정 완료")
    
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
    
    async def handle_mirror_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """미러 트레이딩 상태 확인"""
        try:
            # 미러 트레이딩 시스템 또는 메인 시스템에서 상태 조회
            if self.mirror_trading_system:
                current_info = await self.mirror_trading_system.get_current_mirror_mode()
                current_enabled = current_info['enabled']
                description = current_info['description']
                ratio_multiplier = current_info.get('ratio_multiplier', 1.0)
            elif self.system_reference and hasattr(self.system_reference, 'get_mirror_mode'):
                current_enabled = self.system_reference.get_mirror_mode()
                description = '활성화' if current_enabled else '비활성화'
                ratio_multiplier = getattr(self.system_reference, 'mirror_ratio_multiplier', 1.0)
            else:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                    reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
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
                reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
            )
            
        except Exception as e:
            self.logger.error(f"미러링 상태 조회 실패: {e}")
            await update.message.reply_text(
                f"❌ 미러링 상태 조회 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
            )
    
    async def handle_mirror_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔥🔥🔥 /mirror 명령어 처리 - 미러링 모드 실시간 제어"""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            
            # 미러 트레이딩 시스템 참조 확인
            if not self.mirror_trading_system:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.\n"
                    "시스템 관리자에게 문의하세요.",
                    reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                )
                return
            
            # 현재 미러링 모드 정보 조회
            current_info = await self.mirror_trading_system.get_current_mirror_mode()
            current_enabled = current_info['enabled']
            description = current_info['description']
            ratio_multiplier = current_info.get('ratio_multiplier', 1.0)
            
            # 파라미터 확인
            if context.args:
                arg = context.args[0].lower()
                
                # 단축어 처리
                if arg in ['on', 'o', '1', 'true', 'start', '활성화', '켜기', '시작']:
                    new_mode = True
                    mode_text = "활성화"
                    
                elif arg in ['off', 'x', '0', 'false', 'stop', '비활성화', '끄기', '중지']:
                    new_mode = False
                    mode_text = "비활성화"
                    
                elif arg in ['status', 'check', 'info', '상태', '확인']:
                    # 현재 상태만 표시
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
                        reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                    )
                    return
                
                # 동일한 모드인지 확인
                if new_mode == current_enabled:
                    status_emoji = "✅" if new_mode else "⏸️"
                    await update.message.reply_text(
                        f"{status_emoji} 이미 해당 모드로 설정되어 있습니다.\n"
                        f"현재 상태: {description}\n"
                        f"복제 비율: {ratio_multiplier}x",
                        reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                    )
                    return
                
                # 🔥🔥🔥 확인 절차 - 대기 상태 저장
                from datetime import datetime, timedelta
                
                self.pending_mirror_confirmations[user_id] = {
                    'mode': new_mode,
                    'timestamp': datetime.now(),
                    'chat_id': chat_id
                }
                
                # 변경 사항 미리 분석
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
                
                # 확인 키보드 생성
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
                
                # 1분 후 자동 만료 스케줄링
                async def cleanup_mirror_confirmation():
                    await asyncio.sleep(60)
                    if user_id in self.pending_mirror_confirmations:
                        del self.pending_mirror_confirmations[user_id]
                
                asyncio.create_task(cleanup_mirror_confirmation())
                
            else:
                # 현재 상태만 표시
                await self._show_current_mirror_status(update)
                
        except Exception as e:
            self.logger.error(f"미러링 명령어 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 미러링 명령어 처리 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
            )
    
    async def _show_current_mirror_status(self, update: Update):
        """현재 미러링 상태 표시"""
        try:
            if not self.mirror_trading_system:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                    reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
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
                reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
            )
            
        except Exception as e:
            self.logger.error(f"미러링 상태 표시 실패: {e}")
            await update.message.reply_text(
                f"❌ 상태 조회 실패: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
            )
    
    async def handle_mirror_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔥🔥🔥 미러링 모드 설정 확인 처리"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text.strip()
            
            # 대기 중인 확인이 있는지 확인
            if user_id not in self.pending_mirror_confirmations:
                return False  # 이 메시지는 미러링 확인과 관련 없음
            
            pending_info = self.pending_mirror_confirmations[user_id]
            new_mode = pending_info['mode']
            
            # 만료 확인 (1분 제한)
            from datetime import datetime, timedelta
            if datetime.now() - pending_info['timestamp'] > timedelta(minutes=1):
                del self.pending_mirror_confirmations[user_id]
                await update.message.reply_text(
                    "⏰ 미러링 설정 확인 시간이 만료되었습니다.\n"
                    "/mirror 명령어를 다시 사용해 주세요.",
                    reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                )
                return True
            
            # 확인 응답 처리
            if "✅" in message_text or "예" in message_text:
                # 미러링 모드 적용
                try:
                    if not self.mirror_trading_system:
                        await update.message.reply_text(
                            "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                            reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                        )
                        return True
                    
                    # 실제 미러링 모드 변경 실행
                    result = await self.mirror_trading_system.set_mirror_mode(new_mode)
                    
                    if result['success']:
                        old_state = result['old_state']
                        new_state = result['new_state']
                        state_change = result['state_change']
                        
                        status_emoji = "✅" if new_state else "⏸️"
                        mode_text = "활성화" if new_state else "비활성화"
                        
                        # 게이트 마진 모드 확인 (활성화 시)
                        margin_info = ""
                        if new_state:
                            try:
                                # 마진 모드 Cross 확인 및 설정
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
                            reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                        )
                        
                        self.logger.info(f"텔레그램으로 미러링 모드 변경: {old_state} → {new_state} (사용자: {user_id})")
                        
                    else:
                        await update.message.reply_text(
                            f"❌ 미러링 모드 변경 실패\n"
                            f"오류: {result.get('error', '알 수 없는 오류')}\n"
                            f"현재 상태 유지: {result.get('current_state', '불명')}",
                            reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                        )
                        
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ 미러링 모드 적용 중 오류 발생\n"
                        f"오류: {str(e)[:200]}",
                        reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                    )
                    
            elif "❌" in message_text or "아니" in message_text:
                # 취소
                current_status = "활성화" if self.mirror_trading_system.mirror_trading_enabled else "비활성화"
                await update.message.reply_text(
                    f"🚫 미러링 모드 변경이 취소되었습니다.\n"
                    f"현재 상태 유지: {current_status}",
                    reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                )
                
            else:
                # 잘못된 응답
                await update.message.reply_text(
                    f"❓ 올바른 응답을 선택해 주세요.\n"
                    f"✅ 예, 변경합니다 또는 ❌ 아니오, 취소",
                    reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                )
                return True  # 다시 대기
            
            # 확인 상태 정리
            del self.pending_mirror_confirmations[user_id]
            return True
            
        except Exception as e:
            self.logger.error(f"미러링 확인 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 미러링 확인 처리 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
            )
            return True
    
    async def handle_ratio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """복제 비율 실시간 조정"""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            
            # 미러 트레이딩 시스템 참조 확인
            if not self.mirror_trading_system:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.\n"
                    "시스템 관리자에게 문의하세요.",
                    reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
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
                            reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                        )
                        return
                    
                    # 범위 확인 (사전 검증)
                    if new_ratio < 0.1 or new_ratio > 10.0:
                        await update.message.reply_text(
                            f"❌ 배율 범위 초과: {new_ratio}\n"
                            f"허용 범위: 0.1 ~ 10.0\n"
                            f"현재 설정: {current_ratio}x",
                            reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                        )
                        return
                    
                    # 동일한 배율인지 확인
                    if abs(new_ratio - current_ratio) < 0.01:
                        await update.message.reply_text(
                            f"💡 이미 해당 배율로 설정되어 있습니다.\n"
                            f"현재 배율: {current_ratio}x\n"
                            f"요청 배율: {new_ratio}x",
                            reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                        )
                        return
                    
                    # 확인 절차 - 대기 상태 저장
                    from datetime import datetime, timedelta
                    
                    self.pending_ratio_confirmations[user_id] = {
                        'ratio': new_ratio,
                        'timestamp': datetime.now(),
                        'chat_id': chat_id
                    }
                    
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
                    
                    # 1분 후 자동 만료 스케줄링
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
                        reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
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
                    reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                )
                
        except Exception as e:
            self.logger.error(f"배율 명령어 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 배율 명령어 처리 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
            )
    
    async def handle_ratio_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """배율 설정 확인 처리"""
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
                    reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                )
                return True
            
            # 확인 응답 처리
            if "✅" in message_text or "예" in message_text:
                # 배율 적용
                try:
                    if not self.mirror_trading_system:
                        await update.message.reply_text(
                            "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                            reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                        )
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
                            reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                        )
                        
                        self.logger.info(f"텔레그램으로 복제 비율 변경: {old_ratio}x → {new_ratio}x (사용자: {user_id})")
                        
                    else:
                        await update.message.reply_text(
                            f"❌ 배율 변경 실패\n"
                            f"오류: {result.get('error', '알 수 없는 오류')}\n"
                            f"현재 배율 유지: {result.get('current_ratio', '불명')}x",
                            reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                        )
                        
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ 배율 적용 중 오류 발생\n"
                        f"오류: {str(e)[:200]}",
                        reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                    )
                    
            elif "❌" in message_text or "아니" in message_text:
                # 취소
                await update.message.reply_text(
                    f"🚫 배율 변경이 취소되었습니다.\n"
                    f"현재 배율 유지: {self.mirror_trading_system.mirror_ratio_multiplier if self.mirror_trading_system else '불명'}x",
                    reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                )
                
            else:
                # 잘못된 응답
                await update.message.reply_text(
                    f"❓ 올바른 응답을 선택해 주세요.\n"
                    f"✅ 예, 적용합니다 또는 ❌ 아니오, 취소",
                    reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
                )
                return True  # 다시 대기
            
            # 확인 상태 정리
            del self.pending_ratio_confirmations[user_id]
            return True
            
        except Exception as e:
            self.logger.error(f"배율 확인 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 배율 확인 처리 실패\n"
                f"오류: {str(e)[:200]}",
                reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
            )
            return True
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔥🔥🔥 통합 메시지 핸들러 - 확인 메시지들을 우선 처리"""
        try:
            # 1. 미러링 모드 확인 처리
            if await self.handle_mirror_confirmation(update, context):
                return
            
            # 2. 배율 확인 처리
            if await self.handle_ratio_confirmation(update, context):
                return
            
            # 3. 기타 메시지 처리 (필요한 경우 추가)
            message_text = update.message.text.strip().lower()
            
            # 자연어 단축어 처리
            if any(keyword in message_text for keyword in ['미러링 켜', '미러링 시작', '미러링 활성화']):
                context.args = ['on']
                await self.handle_mirror_command(update, context)
                return
                
            elif any(keyword in message_text for keyword in ['미러링 꺼', '미러링 중지', '미러링 비활성화']):
                context.args = ['off']
                await self.handle_mirror_command(update, context)
                return
                
            elif any(keyword in message_text for keyword in ['미러링 상태', '미러링 확인']):
                context.args = ['status']
                await self.handle_mirror_command(update, context)
                return
            
            # 기타 메시지는 무시 (로그 없이)
            
        except Exception as e:
            self.logger.error(f"메시지 처리 실패: {e}")
    
    async def handle_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """도움말 명령어 처리"""
        try:
            help_text = """🤖 미러 트레이딩 봇 도움말

🔄 미러링 제어:
• /mirror - 현재 미러링 상태 확인
• /mirror on - 미러링 활성화 (단축어: o, 1, start)
• /mirror off - 미러링 비활성화 (단축어: x, 0, stop)
• /mirror status - 상태 확인

📊 복제 비율 제어:
• /ratio - 현재 복제 비율 확인
• /ratio [숫자] - 복제 비율 변경
• /ratio 1.0 - 원본 비율 그대로 (기본값)
• /ratio 0.5 - 원본의 절반 크기로 축소
• /ratio 2.0 - 원본의 2배 크기로 확대

💡 기타:
• /help - 이 도움말 표시

🎯 사용 예시:
• /mirror on (미러링 시작)
• /ratio 1.5 (1.5배로 확대)
• /mirror off (미러링 중지)

📋 허용 범위:
• 복제 비율: 0.1 ~ 10.0배
• 실시간 적용: 즉시 반영

⚡ 실시간 제어:
• 변경 즉시 새로운 거래에 적용
• 기존 활성 주문은 영향받지 않음
• 확인 절차로 안전하게 변경
• 게이트 마진 모드 자동 Cross 설정

🔥 리스크 관리:
• 0.5배 이하: 보수적 (리스크 감소)
• 1.0배: 표준 (원본과 동일)
• 1.5배 이상: 적극적 (리스크 증가)
• 3.0배 이상: 공격적 (높은 리스크)

💳 자동 설정:
• 게이트 마진 모드: 항상 Cross로 유지
• TP/SL 완벽 미러링
• 예약 주문 체결/취소 정확한 구분

💡 시스템이 24시간 안전하게 작동합니다."""
            
            await update.message.reply_text(
                help_text,
                reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
            )
            
        except Exception as e:
            self.logger.error(f"도움말 명령어 처리 실패: {e}")
            await update.message.reply_text(
                "❌ 도움말 표시 실패",
                reply_markup=ReplyKeyboardRemove()  # 🔥 키보드 제거
            )
    
    def _clean_html_message(self, text: str) -> str:
        """HTML 메시지 정리 및 검증"""
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
        """HTML 구조 검증"""
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
        """개선된 메시지 전송 - HTML 파싱 오류 완전 해결"""
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
                            parse_mode='HTML',
                            reply_markup=ReplyKeyboardRemove()  # 🔥 기본적으로 키보드 제거
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
                    text=text_only.strip(),
                    reply_markup=ReplyKeyboardRemove()  # 🔥 기본적으로 키보드 제거
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
                    text=fallback_message,
                    reply_markup=ReplyKeyboardRemove()  # 🔥 기본적으로 키보드 제거
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
