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
        self.system_reference = None
        
        # 배율 설정 관련 상태 관리
        self.pending_ratio_confirmations = {}
        self.pending_mirror_confirmations = {}
        
        # 핸들러 등록 여부 추적
        self._handlers_registered = False
        
        self._initialize_bot()
        
    def _initialize_bot(self):
        """봇 초기화"""
        try:
            telegram_token = self.config.TELEGRAM_BOT_TOKEN
            if not telegram_token:
                raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
            
            # Bot 인스턴스 생성
            self.bot = Bot(token=telegram_token)
            
            # Application 생성
            self.application = Application.builder().token(telegram_token).build()
            
            self.logger.info("✅ 텔레그램 봇 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"텔레그램 봇 초기화 실패: {str(e)}")
            raise
    
    def set_mirror_trading_system(self, mirror_system):
        """미러 트레이딩 시스템 참조 설정"""
        self.mirror_trading_system = mirror_system
        self.logger.info("미러 트레이딩 시스템 참조 설정 완료")
    
    def set_system_reference(self, system):
        """메인 시스템 참조 설정"""
        self.system_reference = system
        self.logger.info("메인 시스템 참조 설정 완료")
    
    def setup_handlers(self):
        """핸들러 직접 등록 - 간단한 방식"""
        try:
            if self.application is None:
                self._initialize_bot()
            
            self.logger.info("🔥 핸들러 직접 등록 시작")
            
            # 기존 핸들러 모두 제거
            self.application.handlers.clear()
            self.logger.info("기존 핸들러 모두 제거")
            
            # 명령어 핸들러들 등록
            handlers = [
                CommandHandler('start', self._handle_start),
                CommandHandler('help', self._handle_start),
                CommandHandler('report', self._handle_report),
                CommandHandler('forecast', self._handle_forecast),
                CommandHandler('profit', self._handle_profit),
                CommandHandler('schedule', self._handle_schedule),
                CommandHandler('stats', self._handle_stats),
                CommandHandler('mirror', self._handle_mirror),
                CommandHandler('ratio', self._handle_ratio),
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message),
            ]
            
            for handler in handlers:
                self.application.add_handler(handler)
                if isinstance(handler, CommandHandler):
                    commands = ', '.join(handler.commands)
                    self.logger.info(f"✅ 명령어 핸들러 등록: /{commands}")
                else:
                    self.logger.info(f"✅ 메시지 핸들러 등록")
            
            self._handlers_registered = True
            self.logger.info("✅ 모든 핸들러 등록 완료")
            
        except Exception as e:
            self.logger.error(f"핸들러 등록 실패: {str(e)}")
            raise
    
    # 내부 핸들러들 - 시스템 메소드 호출
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """시작 명령어 처리"""
        try:
            if self.system_reference:
                await self.system_reference.handle_start_command(update, context)
            else:
                await update.message.reply_text("❌ 시스템이 연결되지 않았습니다.")
        except Exception as e:
            self.logger.error(f"start 명령어 처리 실패: {e}")
            await update.message.reply_text("❌ 명령어 처리 중 오류가 발생했습니다.")
    
    async def _handle_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """리포트 명령어 처리"""
        try:
            if self.system_reference:
                await self.system_reference.handle_report_command(update, context)
            else:
                await update.message.reply_text("❌ 시스템이 연결되지 않았습니다.")
        except Exception as e:
            self.logger.error(f"report 명령어 처리 실패: {e}")
            await update.message.reply_text("❌ 명령어 처리 중 오류가 발생했습니다.")
    
    async def _handle_forecast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """예측 명령어 처리"""
        try:
            if self.system_reference:
                await self.system_reference.handle_forecast_command(update, context)
            else:
                await update.message.reply_text("❌ 시스템이 연결되지 않았습니다.")
        except Exception as e:
            self.logger.error(f"forecast 명령어 처리 실패: {e}")
            await update.message.reply_text("❌ 명령어 처리 중 오류가 발생했습니다.")
    
    async def _handle_profit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """수익 명령어 처리"""
        try:
            if self.system_reference:
                await self.system_reference.handle_profit_command(update, context)
            else:
                await update.message.reply_text("❌ 시스템이 연결되지 않았습니다.")
        except Exception as e:
            self.logger.error(f"profit 명령어 처리 실패: {e}")
            await update.message.reply_text("❌ 명령어 처리 중 오류가 발생했습니다.")
    
    async def _handle_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """일정 명령어 처리"""
        try:
            if self.system_reference:
                await self.system_reference.handle_schedule_command(update, context)
            else:
                await update.message.reply_text("❌ 시스템이 연결되지 않았습니다.")
        except Exception as e:
            self.logger.error(f"schedule 명령어 처리 실패: {e}")
            await update.message.reply_text("❌ 명령어 처리 중 오류가 발생했습니다.")
    
    async def _handle_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """통계 명령어 처리"""
        try:
            if self.system_reference:
                await self.system_reference.handle_stats_command(update, context)
            else:
                await update.message.reply_text("❌ 시스템이 연결되지 않았습니다.")
        except Exception as e:
            self.logger.error(f"stats 명령어 처리 실패: {e}")
            await update.message.reply_text("❌ 명령어 처리 중 오류가 발생했습니다.")
    
    async def _handle_mirror(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """미러 명령어 처리"""
        try:
            await self.handle_mirror_command(update, context)
        except Exception as e:
            self.logger.error(f"mirror 명령어 처리 실패: {e}")
            await update.message.reply_text("❌ 명령어 처리 중 오류가 발생했습니다.")
    
    async def _handle_ratio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """배율 명령어 처리"""
        try:
            await self.handle_ratio_command(update, context)
        except Exception as e:
            self.logger.error(f"ratio 명령어 처리 실패: {e}")
            await update.message.reply_text("❌ 명령어 처리 중 오류가 발생했습니다.")
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """일반 메시지 처리"""
        try:
            # 1. 미러링 모드 확인 처리
            if await self.handle_mirror_confirmation(update, context):
                return
            
            # 2. 배율 확인 처리
            if await self.handle_ratio_confirmation(update, context):
                return
            
            # 3. 자연어 처리는 시스템에 위임
            if self.system_reference:
                await self.system_reference.handle_natural_language(update, context)
            else:
                await update.message.reply_text("❌ 시스템이 연결되지 않았습니다.")
                
        except Exception as e:
            self.logger.error(f"메시지 처리 실패: {e}")
            await update.message.reply_text("❌ 메시지 처리 중 오류가 발생했습니다.")
    
    async def start(self):
        """봇 시작"""
        try:
            if self.application is None:
                self._initialize_bot()
            
            # 핸들러 등록
            if not self._handlers_registered:
                self.setup_handlers()
            
            # Application 초기화
            self.logger.info("Application 초기화 중...")
            await self.application.initialize()
            
            # Application 시작
            self.logger.info("Application 시작 중...")
            await self.application.start()
            
            # 봇 정보 확인
            bot_info = await self.bot.get_me()
            self.logger.info(f"🤖 봇 정보: @{bot_info.username} (ID: {bot_info.id})")
            
            # 폴링 시작
            self.logger.info("🔄 텔레그램 폴링 시작...")
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                timeout=30,
                read_timeout=10,
                write_timeout=10,
                connect_timeout=10,
                pool_timeout=10
            )
            
            self.logger.info("✅ 텔레그램 봇 시작 완료 - 명령어 수신 대기 중")
            
            # 테스트 메시지 전송
            try:
                await self.send_message("🚀 텔레그램 봇이 시작되었습니다! /help로 명령어를 확인하세요.")
                self.logger.info("✅ 테스트 메시지 전송 성공")
            except Exception as test_error:
                self.logger.error(f"테스트 메시지 전송 실패: {test_error}")
            
        except Exception as e:
            self.logger.error(f"텔레그램 봇 시작 실패: {str(e)}")
            raise
    
    async def stop(self):
        """봇 정지"""
        try:
            if self.application:
                self.logger.info("텔레그램 봇 정지 중...")
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                self.logger.info("텔레그램 봇 정지됨")
                
        except Exception as e:
            self.logger.error(f"텔레그램 봇 정지 실패: {str(e)}")
    
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
        """개선된 메시지 전송"""
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
                    reply_markup=ReplyKeyboardRemove()
                )
                self.logger.info("텍스트 모드 메시지 전송 성공")
                return
                
            except Exception as text_error:
                self.logger.error(f"텍스트 모드 전송도 실패: {text_error}")
            
            # 3차: 최후 수단
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
            raise
