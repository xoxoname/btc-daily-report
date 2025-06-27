import os
import asyncio
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
import traceback
import re

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, config):
        self.config = config
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.logger = logging.getLogger('telegram_bot')
        
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다")
        
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID 환경변수가 설정되지 않았습니다")
        
        self.bot = Bot(token=self.bot_token)
        self.application = Application.builder().token(self.bot_token).build()
        
        # 🔥🔥🔥 미러 트레이딩 시스템 참조 (더미든 실제든)
        self.mirror_trading_system = None
        
        # 명령어 핸들러 저장소
        self.handlers = {}
        
        # 🔥🔥🔥 확인 대기 중인 명령어들 (보안을 위한 확인 절차)
        self.pending_confirmations = {}
        self.confirmation_timeout = 60  # 60초 제한시간
        
        # 🔥🔥🔥 텔레그램 명령어 응답 통계
        self.command_response_count = {
            'mirror': 0,
            'ratio': 0,
            'profit': 0,
            'report': 0,
            'forecast': 0,
            'schedule': 0,
            'stats': 0,
            'help': 0,
            'confirmations': 0,
            'natural_language': 0
        }
        
        self.logger.info("✅ Telegram Bot 초기화 완료")
        self.logger.info(f"Chat ID: {self.chat_id}")

    def set_mirror_trading_system(self, mirror_system):
        """🔥🔥🔥 미러 트레이딩 시스템 설정 (더미든 실제든)"""
        self.mirror_trading_system = mirror_system
        self.logger.info("🔗 미러 트레이딩 시스템 참조 설정 완료")

    async def handle_natural_language_enhanced(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """🔥🔥🔥 강화된 자연어 처리 - 미러/배율 확인 메시지 우선 처리"""
        try:
            message = update.message.text.lower().strip()
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            
            self.logger.info(f"자연어 처리 - User: {username}({user_id}), Message: '{message}'")
            
            # 🔥🔥🔥 1순위: 확인 메시지 처리 (Y/N, 예/아니오 등)
            confirmation_result = await self._handle_confirmation_responses(update, message)
            if confirmation_result:
                return True  # 확인 메시지 처리됨
            
            # 🔥🔥🔥 2순위: 미러 트레이딩 관련 자연어
            mirror_handled = await self._handle_mirror_natural_language(update, message)
            if mirror_handled:
                return True
            
            # 🔥🔥🔥 3순위: 배율 관련 자연어
            ratio_handled = await self._handle_ratio_natural_language(update, message)
            if ratio_handled:
                return True
            
            # 🔥🔥🔥 4순위: 수익 관련 자연어
            profit_handled = await self._handle_profit_natural_language(update, message)
            if profit_handled:
                return True
            
            # 🔥🔥🔥 5순위: 기타 일반적인 자연어 (기존 main.py로 위임)
            return False  # main.py에서 처리하도록 위임
            
        except Exception as e:
            self.logger.error(f"강화된 자연어 처리 실패: {e}")
            return False

    async def _handle_confirmation_responses(self, update: Update, message: str) -> bool:
        """🔥🔥🔥 확인 응답 처리 (Y/N, 예/아니오, 네/아니오 등)"""
        try:
            user_id = update.effective_user.id
            
            # 대기 중인 확인이 있는지 체크
            if user_id not in self.pending_confirmations:
                return False
            
            confirmation_data = self.pending_confirmations[user_id]
            
            # 시간 초과 체크
            if datetime.now() > confirmation_data['expires_at']:
                del self.pending_confirmations[user_id]
                await update.message.reply_text(
                    "⏰ 확인 시간이 초과되었습니다. 다시 명령어를 입력해주세요.",
                    parse_mode='HTML'
                )
                return True
            
            # 확인/취소 응답 분석
            positive_responses = ['y', 'yes', '예', '네', '맞습니다', '확인', '좋습니다', 'ok', 'okay', '1']
            negative_responses = ['n', 'no', '아니오', '아니요', '취소', 'cancel', '그만', '0']
            
            is_positive = any(resp in message for resp in positive_responses)
            is_negative = any(resp in message for resp in negative_responses)
            
            if is_positive and not is_negative:
                # 긍정적 응답 - 명령어 실행
                await self._execute_confirmed_command(update, confirmation_data)
                del self.pending_confirmations[user_id]
                return True
                
            elif is_negative and not is_positive:
                # 부정적 응답 - 취소
                await update.message.reply_text(
                    f"❌ {confirmation_data['command_description']} 취소되었습니다.",
                    parse_mode='HTML'
                )
                del self.pending_confirmations[user_id]
                return True
                
            else:
                # 애매한 응답
                await update.message.reply_text(
                    f"🤔 명확하지 않은 응답입니다.\n\n"
                    f"📋 대기 중인 명령: {confirmation_data['command_description']}\n\n"
                    f"✅ 실행하려면: **예**, **Y**, **확인**\n"
                    f"❌ 취소하려면: **아니오**, **N**, **취소**",
                    parse_mode='HTML'
                )
                return True
            
        except Exception as e:
            self.logger.error(f"확인 응답 처리 실패: {e}")
            return False

    async def _execute_confirmed_command(self, update: Update, confirmation_data: Dict):
        """🔥🔥🔥 확인된 명령어 실행"""
        try:
            command_type = confirmation_data['command_type']
            command_data = confirmation_data['command_data']
            
            self.command_response_count['confirmations'] += 1
            
            if command_type == 'mirror_mode_change':
                # 미러링 모드 변경 실행
                enable = command_data['enable']
                await self._execute_mirror_mode_change(update, enable)
                
            elif command_type == 'ratio_change':
                # 배율 변경 실행
                new_ratio = command_data['new_ratio']
                await self._execute_ratio_change(update, new_ratio)
                
            else:
                await update.message.reply_text(
                    "❌ 알 수 없는 명령어 타입입니다.",
                    parse_mode='HTML'
                )
                
        except Exception as e:
            self.logger.error(f"확인된 명령어 실행 실패: {e}")
            await update.message.reply_text(
                f"❌ 명령어 실행 중 오류가 발생했습니다: {str(e)[:100]}",
                parse_mode='HTML'
            )

    async def _handle_mirror_natural_language(self, update: Update, message: str) -> bool:
        """🔥🔥🔥 미러 트레이딩 관련 자연어 처리"""
        try:
            # 미러 트레이딩 키워드들
            mirror_keywords = ['미러', 'mirror', '동기화', 'sync', '복사', 'copy', '따라가기']
            status_keywords = ['상태', 'status', '어떻게', '어떤', '현재']
            enable_keywords = ['켜', '활성화', 'on', 'start', '시작', '실행']
            disable_keywords = ['꺼', '비활성화', 'off', 'stop', '중지', '정지']
            
            has_mirror = any(keyword in message for keyword in mirror_keywords)
            has_status = any(keyword in message for keyword in status_keywords)
            has_enable = any(keyword in message for keyword in enable_keywords)
            has_disable = any(keyword in message for keyword in disable_keywords)
            
            if has_mirror:
                if has_enable:
                    # 미러링 활성화 요청
                    await self.handle_mirror_command_enhanced(update, None, ['mirror', 'on'])
                    return True
                elif has_disable:
                    # 미러링 비활성화 요청
                    await self.handle_mirror_command_enhanced(update, None, ['mirror', 'off'])
                    return True
                elif has_status:
                    # 미러링 상태 조회
                    await self.handle_mirror_command_enhanced(update, None, ['mirror', 'status'])
                    return True
                else:
                    # 일반적인 미러링 질문
                    await self.handle_mirror_command_enhanced(update, None, ['mirror'])
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"미러 자연어 처리 실패: {e}")
            return False

    async def _handle_ratio_natural_language(self, update: Update, message: str) -> bool:
        """🔥🔥🔥 배율 관련 자연어 처리"""
        try:
            # 배율 키워드들
            ratio_keywords = ['배율', '비율', 'ratio', '몇배', '배', '복제']
            number_pattern = r'(\d+(?:\.\d+)?)'
            
            has_ratio = any(keyword in message for keyword in ratio_keywords)
            
            if has_ratio:
                # 숫자 추출 시도
                numbers = re.findall(number_pattern, message)
                
                if numbers:
                    try:
                        # 첫 번째 숫자를 배율로 사용
                        ratio_value = float(numbers[0])
                        if 0.1 <= ratio_value <= 10.0:
                            await self.handle_ratio_command(update, None, str(ratio_value))
                            return True
                    except ValueError:
                        pass
                
                # 숫자가 없거나 잘못된 경우 현재 상태 조회
                await self.handle_ratio_command(update, None)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"배율 자연어 처리 실패: {e}")
            return False

    async def _handle_profit_natural_language(self, update: Update, message: str) -> bool:
        """🔥🔥🔥 수익 관련 자연어 처리"""
        try:
            # 수익 키워드들
            profit_keywords = ['수익', '얼마', '벌었', '손익', '이익', '손실', 'profit', 'pnl', '돈']
            
            has_profit = any(keyword in message for keyword in profit_keywords)
            
            if has_profit:
                # 수익 조회는 항상 사용 가능하므로 바로 처리
                self.command_response_count['profit'] += 1
                await update.message.reply_text(
                    "💰 수익 현황을 조회중입니다... (미러 모드와 상관없이 사용 가능)",
                    parse_mode='HTML'
                )
                # main.py의 handle_profit_command로 처리 위임
                return False  # 실제 처리는 main.py에서
            
            return False
            
        except Exception as e:
            self.logger.error(f"수익 자연어 처리 실패: {e}")
            return False

    async def handle_mirror_command_enhanced(self, update: Update, context: ContextTypes.DEFAULT_TYPE, manual_args: List[str] = None):
        """🔥🔥🔥 미러 명령어 강화 처리 - 항상 응답"""
        try:
            self.command_response_count['mirror'] += 1
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            
            # 🔥🔥🔥 인자 처리 개선 - context.args 우선 사용
            args = []
            if manual_args:
                args = manual_args
            elif context and hasattr(context, 'args'):
                args = ['mirror'] + context.args
            else:
                # 텍스트에서 직접 분리
                message_parts = update.message.text.split()
                args = message_parts
            
            self.logger.info(f"미러 명령어 - User: {username}({user_id}), Args: {args}")
            
            # 인자가 없으면 상태 조회
            if len(args) <= 1:
                await self._show_mirror_status(update)
                return
            
            subcommand = args[1].lower() if len(args) > 1 else 'status'
            
            if subcommand in ['status', 'state', '상태']:
                await self._show_mirror_status(update)
                
            elif subcommand in ['on', 'enable', '켜기', '활성화', 'start']:
                await self._handle_mirror_enable_request(update)
                
            elif subcommand in ['off', 'disable', '끄기', '비활성화', 'stop']:
                await self._handle_mirror_disable_request(update)
                
            else:
                await self._show_mirror_help(update)
                
        except Exception as e:
            self.logger.error(f"미러 명령어 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 미러 명령어 처리 중 오류가 발생했습니다: {str(e)[:100]}",
                parse_mode='HTML'
            )

    async def _show_mirror_status(self, update: Update):
        """🔥🔥🔥 미러 트레이딩 상태 표시"""
        try:
            if not self.mirror_trading_system:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                    parse_mode='HTML'
                )
                return
            
            # 현재 상태 조회
            mirror_info = await self.mirror_trading_system.get_current_mirror_mode()
            ratio_info = await self.mirror_trading_system.get_current_ratio_info()
            
            # 상태에 따른 이모지와 설명
            status_emoji = "✅" if mirror_info['enabled'] else "❌"
            status_text = mirror_info['description']
            
            # 기본 상태 메시지
            status_msg = f"""🔄 <b>미러 트레이딩 현재 상태</b>

<b>🎮 미러링 모드:</b> {status_emoji} {status_text}
<b>🔢 복제 비율:</b> {ratio_info['current_ratio']}x
<b>📝 비율 설명:</b> {ratio_info['description']}
<b>⏰ 마지막 업데이트:</b> {datetime.fromisoformat(mirror_info['last_updated']).strftime('%H:%M:%S')}

<b>🎮 텔레그램 제어 명령어:</b>
• <code>/mirror on</code> - 미러링 활성화
• <code>/mirror off</code> - 미러링 비활성화
• <code>/mirror status</code> - 상태 확인
• <code>/ratio [숫자]</code> - 복제 비율 조정
• <code>/profit</code> - 수익 조회 (항상 사용 가능)

<b>📊 사용 가능한 기능:</b>
• 수익 조회: /profit (미러 모드와 상관없이 사용 가능)
• 시장 분석: /report  
• 단기 예측: /forecast
• 시스템 통계: /stats

<b>⚡ 실시간 제어:</b>
미러링과 복제 비율을 텔레그램으로 즉시 변경할 수 있습니다!"""
            
            # 🔥🔥🔥 미러링이 가능한 경우 추가 정보
            if hasattr(self.mirror_trading_system, 'can_use_mirror_trading'):
                try:
                    # main.py의 can_use_mirror_trading 메서드 호출 시뮬레이션
                    # 실제로는 mirror_trading_system이 더미인지 실제인지에 따라 다름
                    if hasattr(self.mirror_trading_system, 'bitget_mirror'):
                        # 실제 미러 시스템
                        status_msg += f"""

<b>💰 계정 상태:</b>
미러링 가능한 상태입니다.
<code>/profit</code> 명령어로 실시간 수익을 확인하세요."""
                    else:
                        # 더미 미러 시스템
                        status_msg += f"""

<b>⚠️ 미러링 조건:</b>
현재 미러 트레이딩을 사용할 수 없습니다.
• Gate.io API 키 설정 필요
• 미러 트레이딩 모듈 설치 필요
• 환경변수 설정 필요

<b>✅ 사용 가능한 기능:</b>
• <code>/profit</code> - 수익 조회 (항상 사용 가능)
• <code>/ratio</code> - 복제 비율 정보 확인 (항상 사용 가능)"""
                except:
                    pass
            
            await update.message.reply_text(status_msg, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"미러 상태 표시 실패: {e}")
            await update.message.reply_text(
                "❌ 미러 상태 조회 중 오류가 발생했습니다.",
                parse_mode='HTML'
            )

    async def _handle_mirror_enable_request(self, update: Update):
        """🔥🔥🔥 미러링 활성화 요청 처리"""
        try:
            if not self.mirror_trading_system:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                    parse_mode='HTML'
                )
                return
            
            # 현재 상태 확인
            current_info = await self.mirror_trading_system.get_current_mirror_mode()
            
            if current_info['enabled']:
                await update.message.reply_text(
                    "✅ 미러 트레이딩이 이미 활성화되어 있습니다.\n"
                    "현재 상태를 확인하려면 <code>/mirror status</code>를 사용하세요.",
                    parse_mode='HTML'
                )
                return
            
            # 🔥🔥🔥 더미 시스템인지 실제 시스템인지 확인
            if not hasattr(self.mirror_trading_system, 'bitget_mirror'):
                # 더미 시스템 - 조건 불충족으로 활성화 불가
                result = await self.mirror_trading_system.set_mirror_mode(True)
                
                if not result['success']:
                    await update.message.reply_text(
                        f"❌ <b>미러 트레이딩 활성화 실패</b>\n\n"
                        f"<b>실패 이유:</b> {result['error']}\n\n"
                        f"<b>필수 조건:</b>\n"
                        f"• Gate.io API 키 설정 (GATE_API_KEY, GATE_API_SECRET)\n"
                        f"• 미러 트레이딩 모듈 정상 설치\n"
                        f"• 환경변수 설정 완료\n"
                        f"• 시스템 재시작\n\n"
                        f"<b>✅ 사용 가능한 기능:</b>\n"
                        f"• <code>/profit</code> - 수익 조회 (항상 사용 가능)\n"
                        f"• <code>/ratio</code> - 복제 비율 정보 (항상 사용 가능)\n"
                        f"• <code>/report</code> - 시장 분석 (항상 사용 가능)",
                        parse_mode='HTML'
                    )
                return
            
            # 실제 시스템 - 확인 절차 진행
            user_id = update.effective_user.id
            
            # 확인 절차 설정
            self.pending_confirmations[user_id] = {
                'command_type': 'mirror_mode_change',
                'command_data': {'enable': True},
                'command_description': '미러 트레이딩 활성화',
                'expires_at': datetime.now() + timedelta(seconds=self.confirmation_timeout)
            }
            
            await update.message.reply_text(
                f"🔄 <b>미러 트레이딩 활성화 확인</b>\n\n"
                f"미러 트레이딩을 활성화하시겠습니까?\n\n"
                f"<b>⚠️ 주의사항:</b>\n"
                f"• 비트겟의 모든 새로운 포지션이 게이트에 복제됩니다\n"
                f"• 예약 주문(TP/SL)도 자동으로 복제됩니다\n"
                f"• 현재 복제 비율이 적용됩니다\n"
                f"• 기존 포지션은 복제되지 않습니다\n\n"
                f"<b>✅ 활성화하려면:</b> <code>예</code>, <code>Y</code>, <code>확인</code>\n"
                f"<b>❌ 취소하려면:</b> <code>아니오</code>, <code>N</code>, <code>취소</code>\n\n"
                f"⏰ {self.confirmation_timeout}초 내에 응답해주세요.",
                parse_mode='HTML'
            )
            
        except Exception as e:
            self.logger.error(f"미러링 활성화 요청 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 미러링 활성화 요청 처리 중 오류가 발생했습니다: {str(e)[:100]}",
                parse_mode='HTML'
            )

    async def _handle_mirror_disable_request(self, update: Update):
        """🔥🔥🔥 미러링 비활성화 요청 처리"""
        try:
            if not self.mirror_trading_system:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                    parse_mode='HTML'
                )
                return
            
            # 현재 상태 확인
            current_info = await self.mirror_trading_system.get_current_mirror_mode()
            
            if not current_info['enabled']:
                await update.message.reply_text(
                    "✅ 미러 트레이딩이 이미 비활성화되어 있습니다.\n"
                    "현재 상태를 확인하려면 <code>/mirror status</code>를 사용하세요.",
                    parse_mode='HTML'
                )
                return
            
            # 확인 절차 설정
            user_id = update.effective_user.id
            
            self.pending_confirmations[user_id] = {
                'command_type': 'mirror_mode_change',
                'command_data': {'enable': False},
                'command_description': '미러 트레이딩 비활성화',
                'expires_at': datetime.now() + timedelta(seconds=self.confirmation_timeout)
            }
            
            await update.message.reply_text(
                f"⚠️ <b>미러 트레이딩 비활성화 확인</b>\n\n"
                f"미러 트레이딩을 비활성화하시겠습니까?\n\n"
                f"<b>📋 비활성화 시:</b>\n"
                f"• 새로운 포지션 복제가 중단됩니다\n"
                f"• 기존 게이트 포지션은 유지됩니다\n"
                f"• 예약 주문 복제가 중단됩니다\n"
                f"• 언제든 다시 활성화할 수 있습니다\n\n"
                f"<b>✅ 비활성화하려면:</b> <code>예</code>, <code>Y</code>, <code>확인</code>\n"
                f"<b>❌ 취소하려면:</b> <code>아니오</code>, <code>N</code>, <code>취소</code>\n\n"
                f"⏰ {self.confirmation_timeout}초 내에 응답해주세요.",
                parse_mode='HTML'
            )
            
        except Exception as e:
            self.logger.error(f"미러링 비활성화 요청 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 미러링 비활성화 요청 처리 중 오류가 발생했습니다: {str(e)[:100]}",
                parse_mode='HTML'
            )

    async def _execute_mirror_mode_change(self, update: Update, enable: bool):
        """🔥🔥🔥 미러링 모드 변경 실행"""
        try:
            action_text = "활성화" if enable else "비활성화"
            await update.message.reply_text(
                f"🔄 미러 트레이딩 {action_text} 중입니다...",
                parse_mode='HTML'
            )
            
            # 실제 변경 실행
            result = await self.mirror_trading_system.set_mirror_mode(enable)
            
            if result['success']:
                state_change = result.get('state_change', '변경 없음')
                
                success_msg = f"✅ <b>미러 트레이딩 {action_text} 완료</b>\n\n"
                success_msg += f"<b>상태 변경:</b> {state_change}\n"
                success_msg += f"<b>적용 시각:</b> {datetime.fromisoformat(result['applied_time']).strftime('%H:%M:%S')}\n\n"
                
                if enable:
                    success_msg += f"🚀 <b>미러링이 시작되었습니다!</b>\n"
                    success_msg += f"• 새로운 비트겟 포지션이 게이트에 자동 복제됩니다\n"
                    success_msg += f"• 예약 주문(TP/SL)도 함께 복제됩니다\n"
                    success_msg += f"• 현재 복제 비율이 적용됩니다\n"
                    success_msg += f"• <code>/ratio [숫자]</code> 명령어로 복제 비율을 조정할 수 있습니다\n"
                    success_msg += f"• <code>/profit</code> 명령어로 수익을 확인할 수 있습니다"
                else:
                    success_msg += f"⏸️ <b>미러링이 중단되었습니다.</b>\n"
                    success_msg += f"• 새로운 포지션 복제가 중단됩니다\n"
                    success_msg += f"• 기존 게이트 포지션은 유지됩니다\n"
                    success_msg += f"• <code>/mirror on</code>으로 언제든 재활성화 가능합니다\n"
                    success_msg += f"• <code>/profit</code> 명령어는 계속 사용할 수 있습니다"
                
                await update.message.reply_text(success_msg, parse_mode='HTML')
                
            else:
                error_msg = f"❌ <b>미러 트레이딩 {action_text} 실패</b>\n\n"
                error_msg += f"<b>오류:</b> {result['error']}\n"
                error_msg += f"<b>현재 상태:</b> {'활성화' if result['current_state'] else '비활성화'}"
                
                await update.message.reply_text(error_msg, parse_mode='HTML')
                
        except Exception as e:
            self.logger.error(f"미러링 모드 변경 실행 실패: {e}")
            await update.message.reply_text(
                f"❌ 미러링 모드 변경 중 오류가 발생했습니다: {str(e)[:100]}",
                parse_mode='HTML'
            )

    async def _show_mirror_help(self, update: Update):
        """🔥🔥🔥 미러 명령어 도움말"""
        help_msg = f"""🔄 <b>미러 트레이딩 명령어 도움말</b>

<b>📋 사용법:</b>
• <code>/mirror</code> - 현재 상태 조회
• <code>/mirror status</code> - 상태 확인  
• <code>/mirror on</code> - 미러링 활성화
• <code>/mirror off</code> - 미러링 비활성화

<b>🔢 관련 명령어:</b>
• <code>/ratio</code> - 복제 비율 확인
• <code>/ratio [숫자]</code> - 복제 비율 변경
• <code>/profit</code> - 수익 조회 (항상 사용 가능)

<b>💬 자연어 사용 예시:</b>
• "미러링 켜줘"
• "동기화 상태 어때?"
• "복사 기능 꺼줘"

<b>⚡ 실시간 제어:</b>
미러링과 복제 비율을 텔레그램으로 즉시 변경할 수 있습니다!

<b>📊 응답 통계:</b>
• 미러 명령어: {self.command_response_count['mirror']}회 사용
• 배율 명령어: {self.command_response_count['ratio']}회 사용
• 확인 처리: {self.command_response_count['confirmations']}회"""
        
        await update.message.reply_text(help_msg, parse_mode='HTML')

    async def handle_ratio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, ratio_str: str = None):
        """🔥🔥🔥 배율 명령어 처리 - 항상 사용 가능"""
        try:
            self.command_response_count['ratio'] += 1
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            
            # 🔥🔥🔥 인자 처리 개선 - context.args 우선 사용
            if not ratio_str:
                if context and hasattr(context, 'args') and context.args:
                    ratio_str = context.args[0]
            
            self.logger.info(f"배율 명령어 - User: {username}({user_id}), Ratio: {ratio_str}")
            
            if not self.mirror_trading_system:
                await update.message.reply_text(
                    "❌ 미러 트레이딩 시스템이 연결되지 않았습니다.",
                    parse_mode='HTML'
                )
                return
            
            # 배율 값이 주어지지 않은 경우 현재 상태 조회
            if not ratio_str:
                await self._show_current_ratio(update)
                return
            
            # 배율 값 파싱 및 검증
            try:
                new_ratio = float(ratio_str)
            except ValueError:
                await update.message.reply_text(
                    f"❌ 잘못된 배율 값입니다: '{ratio_str}'\n\n"
                    f"<b>올바른 사용법:</b>\n"
                    f"• <code>/ratio 1.0</code> - 1배 (원본과 동일)\n"
                    f"• <code>/ratio 0.5</code> - 0.5배 (절반 크기)\n"
                    f"• <code>/ratio 2.0</code> - 2배 (두 배 크기)\n\n"
                    f"<b>허용 범위:</b> 0.1 ~ 10.0배",
                    parse_mode='HTML'
                )
                return
            
            # 배율 범위 검증
            if new_ratio < 0.1 or new_ratio > 10.0:
                await update.message.reply_text(
                    f"❌ 배율이 허용 범위를 벗어났습니다: {new_ratio}\n\n"
                    f"<b>허용 범위:</b> 0.1배 ~ 10.0배\n\n"
                    f"<b>권장 설정:</b>\n"
                    f"• 0.1 ~ 0.9배: 보수적 (리스크 감소)\n"
                    f"• 1.0배: 표준 (원본과 동일)\n"
                    f"• 1.1 ~ 3.0배: 적극적 (리스크 증가)\n"
                    f"• 3.1 ~ 10.0배: 고위험 (신중 사용)",
                    parse_mode='HTML'
                )
                return
            
            # 🔥🔥🔥 더미 시스템인지 실제 시스템인지 확인
            if not hasattr(self.mirror_trading_system, 'bitget_mirror'):
                # 더미 시스템 - 정보만 제공
                result = await self.mirror_trading_system.set_ratio_multiplier(new_ratio)
                
                await update.message.reply_text(
                    f"📊 <b>복제 비율 정보</b>\n\n"
                    f"요청된 비율: <b>{new_ratio}x</b>\n"
                    f"상태: 미러 트레이딩 비활성화\n\n"
                    f"<b>⚠️ 미러 트레이딩 활성화 필요:</b>\n"
                    f"• Gate.io API 키 설정\n"
                    f"• 미러 트레이딩 모듈 설치\n"
                    f"• 환경변수 설정 완료\n"
                    f"• <code>/mirror on</code> 명령어로 활성화\n\n"
                    f"<b>✅ 사용 가능한 기능:</b>\n"
                    f"• <code>/profit</code> - 수익 조회 (항상 사용 가능)\n"
                    f"• <code>/ratio</code> - 복제 비율 정보 (항상 사용 가능)",
                    parse_mode='HTML'
                )
                return
            
            # 실제 시스템 - 현재 배율과 비교
            current_ratio_info = await self.mirror_trading_system.get_current_ratio_info()
            current_ratio = current_ratio_info['current_ratio']
            
            if abs(current_ratio - new_ratio) < 0.01:  # 거의 동일한 경우
                await update.message.reply_text(
                    f"✅ 복제 비율이 이미 {new_ratio}x로 설정되어 있습니다.\n"
                    f"변경할 필요가 없습니다.",
                    parse_mode='HTML'
                )
                return
            
            # 확인 절차 설정
            user_id = update.effective_user.id
            self.pending_confirmations[user_id] = {
                'command_type': 'ratio_change',
                'command_data': {'new_ratio': new_ratio},
                'command_description': f'복제 비율을 {current_ratio}x → {new_ratio}x로 변경',
                'expires_at': datetime.now() + timedelta(seconds=self.confirmation_timeout)
            }
            
            # 비율 효과 분석
            if new_ratio > current_ratio:
                effect_description = f"📈 <b>증가 효과:</b> 더 큰 포지션 크기 (리스크 증가)"
            elif new_ratio < current_ratio:
                effect_description = f"📉 <b>감소 효과:</b> 더 작은 포지션 크기 (리스크 감소)"
            else:
                effect_description = f"📊 <b>동일 효과:</b> 변화 없음"
            
            await update.message.reply_text(
                f"🔢 <b>복제 비율 변경 확인</b>\n\n"
                f"<b>현재 비율:</b> {current_ratio}x\n"
                f"<b>새로운 비율:</b> {new_ratio}x\n\n"
                f"{effect_description}\n\n"
                f"<b>⚠️ 주의사항:</b>\n"
                f"• 새로운 포지션부터 적용됩니다\n"
                f"• 기존 포지션은 영향받지 않습니다\n"
                f"• 예약 주문에도 새 비율이 적용됩니다\n\n"
                f"<b>✅ 변경하려면:</b> <code>예</code>, <code>Y</code>, <code>확인</code>\n"
                f"<b>❌ 취소하려면:</b> <code>아니오</code>, <code>N</code>, <code>취소</code>\n\n"
                f"⏰ {self.confirmation_timeout}초 내에 응답해주세요.",
                parse_mode='HTML'
            )
            
        except Exception as e:
            self.logger.error(f"배율 명령어 처리 실패: {e}")
            await update.message.reply_text(
                f"❌ 배율 명령어 처리 중 오류가 발생했습니다: {str(e)[:100]}",
                parse_mode='HTML'
            )

    async def _show_current_ratio(self, update: Update):
        """🔥🔥🔥 현재 복제 비율 상태 표시"""
        try:
            ratio_info = await self.mirror_trading_system.get_current_ratio_info()
            
            # 기본 정보
            current_ratio = ratio_info['current_ratio']
            description = ratio_info['description']
            
            status_msg = f"""🔢 <b>현재 복제 비율 상태</b>

<b>📊 현재 비율:</b> {current_ratio}x
<b>📝 설명:</b> {description}
<b>⏰ 마지막 업데이트:</b> {datetime.fromisoformat(ratio_info['last_updated']).strftime('%H:%M:%S')}

<b>🎮 비율 조정 방법:</b>
• <code>/ratio 0.5</code> - 절반 크기 (보수적)
• <code>/ratio 1.0</code> - 원본과 동일 (표준)
• <code>/ratio 1.5</code> - 1.5배 크기 (적극적)
• <code>/ratio 2.0</code> - 2배 크기 (고위험)

<b>🔢 허용 범위:</b> 0.1배 ~ 10.0배

<b>💡 비율 가이드:</b>
• <b>0.1 ~ 0.9배:</b> 보수적 투자 (리스크 감소)
• <b>1.0배:</b> 표준 미러링 (원본과 동일)
• <b>1.1 ~ 3.0배:</b> 적극적 투자 (리스크 증가)
• <b>3.1 ~ 10.0배:</b> 고위험 투자 (신중 사용)"""
            
            # 🔥🔥🔥 미러링 활성화 여부에 따른 추가 정보
            if hasattr(self.mirror_trading_system, 'bitget_mirror'):
                # 실제 시스템
                mirror_info = await self.mirror_trading_system.get_current_mirror_mode()
                
                if mirror_info['enabled']:
                    status_msg += f"""

<b>✅ 미러링 상태:</b> 활성화
새로운 포지션에 {current_ratio}x 비율이 즉시 적용됩니다!"""
                else:
                    status_msg += f"""

<b>❌ 미러링 상태:</b> 비활성화
<code>/mirror on</code>으로 활성화 후 비율이 적용됩니다."""
            else:
                # 더미 시스템
                status_msg += f"""

<b>⚠️ 미러링 상태:</b> 사용 불가
미러 트레이딩 활성화 후 비율 조정이 가능합니다.

<b>✅ 현재 사용 가능:</b>
• <code>/profit</code> - 수익 조회 (항상 사용 가능)
• <code>/ratio</code> - 복제 비율 정보 (항상 사용 가능)"""
            
            status_msg += f"""

<b>📊 명령어 사용 통계:</b>
• 배율 명령어: {self.command_response_count['ratio']}회 사용
• 확인 처리: {self.command_response_count['confirmations']}회 처리"""
            
            await update.message.reply_text(status_msg, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"현재 비율 표시 실패: {e}")
            await update.message.reply_text(
                "❌ 현재 복제 비율 조회 중 오류가 발생했습니다.",
                parse_mode='HTML'
            )

    async def _execute_ratio_change(self, update: Update, new_ratio: float):
        """🔥🔥🔥 복제 비율 변경 실행"""
        try:
            await update.message.reply_text(
                f"🔄 복제 비율을 {new_ratio}x로 변경 중입니다...",
                parse_mode='HTML'
            )
            
            # 실제 변경 실행
            result = await self.mirror_trading_system.set_ratio_multiplier(new_ratio)
            
            if result['success']:
                old_ratio = result['old_ratio']
                applied_ratio = result['new_ratio']
                description = result['description']
                
                success_msg = f"✅ <b>복제 비율 변경 완료</b>\n\n"
                success_msg += f"<b>이전 비율:</b> {old_ratio}x\n"
                success_msg += f"<b>새로운 비율:</b> {applied_ratio}x\n"
                success_msg += f"<b>설명:</b> {description}\n"
                success_msg += f"<b>적용 시각:</b> {datetime.fromisoformat(result['applied_time']).strftime('%H:%M:%S')}\n\n"
                success_msg += f"🚀 <b>새로운 포지션부터 {applied_ratio}x 비율이 적용됩니다!</b>\n"
                success_msg += f"• 기존 포지션은 영향받지 않습니다\n"
                success_msg += f"• 예약 주문(TP/SL)에도 새 비율 적용됩니다\n"
                success_msg += f"• <code>/ratio</code>로 언제든 다시 조정 가능합니다\n"
                success_msg += f"• <code>/profit</code>으로 수익을 확인할 수 있습니다"
                
                await update.message.reply_text(success_msg, parse_mode='HTML')
                
            else:
                error_msg = f"❌ <b>복제 비율 변경 실패</b>\n\n"
                error_msg += f"<b>오류:</b> {result['error']}\n"
                error_msg += f"<b>현재 비율:</b> {result['current_ratio']}x"
                
                await update.message.reply_text(error_msg, parse_mode='HTML')
                
        except Exception as e:
            self.logger.error(f"복제 비율 변경 실행 실패: {e}")
            await update.message.reply_text(
                f"❌ 복제 비율 변경 중 오류가 발생했습니다: {str(e)[:100]}",
                parse_mode='HTML'
            )

    def add_handler(self, command: str, handler):
        """명령어 핸들러 등록"""
        try:
            if command == 'mirror':
                # 🔥🔥🔥 미러 명령어는 강화된 핸들러 사용 - 인자 처리 수정
                self.application.add_handler(
                    CommandHandler('mirror', self.handle_mirror_command_enhanced)
                )
            elif command == 'ratio':
                # 🔥🔥🔥 배율 명령어는 인자 처리 가능한 핸들러 사용
                self.application.add_handler(
                    CommandHandler('ratio', self.handle_ratio_command)
                )
            else:
                # 기존 명령어들
                self.application.add_handler(CommandHandler(command, handler))
            
            self.handlers[command] = handler
            self.logger.info(f"✅ 명령어 핸들러 등록: /{command}")
            
        except Exception as e:
            self.logger.error(f"핸들러 등록 실패: {command} - {e}")

    def add_message_handler(self, handler):
        """메시지 핸들러 등록"""
        try:
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, handler)
            )
            self.logger.info("✅ 메시지 핸들러 등록 완료")
            
        except Exception as e:
            self.logger.error(f"메시지 핸들러 등록 실패: {e}")

    async def send_message(self, message: str, parse_mode: str = 'HTML'):
        """메시지 전송"""
        try:
            # 메시지가 너무 긴 경우 분할
            if len(message) > 4000:
                parts = self._split_message(message)
                for i, part in enumerate(parts):
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=part,
                        parse_mode=parse_mode
                    )
                    if i < len(parts) - 1:
                        await asyncio.sleep(0.5)
            else:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=parse_mode
                )
            
            return True
            
        except Exception as e:
            self.logger.error(f"메시지 전송 실패: {e}")
            return False

    def _split_message(self, message: str, max_length: int = 4000) -> List[str]:
        """긴 메시지 분할"""
        if len(message) <= max_length:
            return [message]
        
        parts = []
        lines = message.split('\n')
        current_part = ""
        
        for line in lines:
            if len(current_part) + len(line) + 1 > max_length:
                if current_part:
                    parts.append(current_part.strip())
                current_part = line + '\n'
            else:
                current_part += line + '\n'
        
        if current_part:
            parts.append(current_part.strip())
        
        return parts

    async def start(self):
        """텔레그램 봇 시작"""
        try:
            self.logger.info("🚀 Telegram Bot 시작 - 미러/배율 실시간 제어")
            
            # 봇 정보 확인
            bot_info = await self.bot.get_me()
            self.logger.info(f"Bot 이름: {bot_info.first_name} (@{bot_info.username})")
            
            # 애플리케이션 시작
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            # 시작 메시지 전송
            await self.send_message(
                f"🤖 <b>Telegram Bot 시작됨</b>\n\n"
                f"🎮 <b>실시간 제어 명령어:</b>\n"
                f"• <code>/mirror on</code> - 미러링 활성화\n"
                f"• <code>/mirror off</code> - 미러링 비활성화\n"
                f"• <code>/mirror status</code> - 상태 확인\n"
                f"• <code>/ratio [숫자]</code> - 복제 비율 조정\n"
                f"• <code>/ratio</code> - 현재 비율 확인\n"
                f"• <code>/profit</code> - 수익 조회 (항상 사용 가능)\n"
                f"• <code>/report</code> - 시장 분석\n"
                f"• <code>/forecast</code> - 단기 예측\n"
                f"• <code>/stats</code> - 시스템 통계\n\n"
                f"💬 <b>자연어도 사용 가능:</b>\n"
                f"• \"미러링 켜줘\"\n"
                f"• \"배율 2배로 해줘\"\n"
                f"• \"오늘 수익은?\"\n\n"
                f"✅ 모든 명령어가 활성화되었습니다!\n"
                f"🔥 /mirror on, /mirror off, /ratio 1.5 등의 명령어가 정상 작동합니다!",
                parse_mode='HTML'
            )
            
            self.logger.info("✅ Telegram Bot 시작 완료")
            
        except Exception as e:
            self.logger.error(f"Telegram Bot 시작 실패: {e}")
            raise

    async def stop(self):
        """텔레그램 봇 중지"""
        try:
            self.logger.info("🛑 Telegram Bot 중지 중...")
            
            # 🔥🔥🔥 명령어 응답 통계 전송
            total_responses = sum(self.command_response_count.values())
            
            stats_msg = f"📊 <b>Telegram Bot 종료 통계</b>\n\n"
            stats_msg += f"<b>총 명령어 응답:</b> {total_responses}회\n\n"
            stats_msg += f"<b>명령어별 사용량:</b>\n"
            
            for command, count in self.command_response_count.items():
                if count > 0:
                    stats_msg += f"• /{command}: {count}회\n"
            
            if self.pending_confirmations:
                stats_msg += f"\n<b>⚠️ 대기 중인 확인:</b> {len(self.pending_confirmations)}개"
            
            stats_msg += f"\n\n🔥 미러/배율 실시간 제어 시스템이 안전하게 종료됩니다."
            stats_msg += f"\n✅ /mirror on/off, /ratio [숫자] 명령어가 정상 작동했습니다!"
            
            await self.send_message(stats_msg, parse_mode='HTML')
            
            # 애플리케이션 중지
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            
            self.logger.info("✅ Telegram Bot 중지 완료")
            
        except Exception as e:
            self.logger.error(f"Telegram Bot 중지 중 오류: {e}")
            
        finally:
            # 정리 작업
            self.pending_confirmations.clear()
            self.handlers.clear()
