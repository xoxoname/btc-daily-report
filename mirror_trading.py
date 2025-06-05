import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import json
import traceback

# 유틸리티 클래스 import
from mirror_trading_utils import MirrorTradingUtils, PositionInfo, MirrorResult
from mirror_position_manager import MirrorPositionManager

logger = logging.getLogger(__name__)

class MirrorTradingSystem:
    def __init__(self, config, bitget_client, gate_client, telegram_bot):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.telegram = telegram_bot
        self.logger = logging.getLogger('mirror_trading')
        
        # 유틸리티 클래스 초기화
        self.utils = MirrorTradingUtils(config, bitget_client, gate_client)
        
        # 🔥🔥🔥 포지션 관리자 초기화 (새로운 분할)
        self.position_manager = MirrorPositionManager(
            config, bitget_client, gate_client, telegram_bot, self.utils
        )
        
        # 미러링 상태 관리 (포지션 매니저에 위임)
        self.mirrored_positions = self.position_manager.mirrored_positions
        self.startup_positions = self.position_manager.startup_positions
        self.failed_mirrors = self.position_manager.failed_mirrors
        
        # 기본 설정
        self.last_sync_check = datetime.min
        self.last_report_time = datetime.min
        
        # 🔥🔥🔥 시세 차이 관리 (강화된 버전)
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.last_price_update: datetime = datetime.min
        self.price_sync_threshold: float = 15.0  # 15달러 이상 차이나면 대기
        self.position_wait_timeout: int = 180    # 포지션 체결 대기 3분
        
        # 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.CHECK_INTERVAL = 2
        self.ORDER_CHECK_INTERVAL = 1
        self.PLAN_ORDER_CHECK_INTERVAL = 0.5
        self.SYNC_CHECK_INTERVAL = 30
        self.MAX_RETRIES = 3
        self.MIN_POSITION_SIZE = 0.00001
        self.MIN_MARGIN = 1.0
        self.DAILY_REPORT_HOUR = 9
        
        # 성과 추적 (포지션 매니저와 공유)
        self.daily_stats = self.position_manager.daily_stats
        
        self.monitoring = True
        self.logger.info("🔥🔥🔥 미러 트레이딩 시스템 초기화 완료 - 시세차이 문제 해결, 코드 분할")

    async def start(self):
        """미러 트레이딩 시작"""
        try:
            self.logger.info("🔥🔥🔥 미러 트레이딩 시스템 시작 - 시세차이 문제 해결, 코드 분할")
            
            # 현재 시세 업데이트
            await self._update_current_prices()
            
            # 포지션 매니저 초기화
            await self.position_manager.initialize()
            
            # 초기 계정 상태 출력
            await self._log_account_status()
            
            # 모니터링 태스크 시작
            tasks = [
                self.monitor_plan_orders(),
                self.monitor_order_fills(), 
                self.monitor_positions(),
                self.monitor_sync_status(),
                self.monitor_price_differences(),
                self.generate_daily_reports()
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시작 실패: {e}")
            await self.telegram.send_message(
                f"❌ 미러 트레이딩 시작 실패\n오류: {str(e)[:200]}"
            )
            raise

    async def monitor_plan_orders(self):
        """🔥🔥🔥 예약 주문 모니터링 - 포지션 매니저로 위임"""
        self.logger.info("🎯 예약 주문 모니터링 시작 (시세차이 문제 해결)")
        
        while self.monitoring:
            try:
                await self.position_manager.monitor_plan_orders_cycle()
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"예약 주문 모니터링 중 오류: {e}")
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL * 2)

    async def monitor_order_fills(self):
        """실시간 주문 체결 감지"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                # 🔥🔥🔥 시세 차이 확인 후 처리
                await self._update_current_prices()
                
                filled_orders = await self.bitget.get_recent_filled_orders(
                    symbol=self.SYMBOL, 
                    minutes=1
                )
                
                for order in filled_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if not order_id or order_id in self.position_manager.processed_orders:
                        continue
                    
                    reduce_only = order.get('reduceOnly', 'false')
                    if reduce_only == 'true' or reduce_only is True:
                        continue
                    
                    # 🔥🔥🔥 시세 차이가 큰 경우 처리 지연
                    if abs(self.bitget_current_price - self.gate_current_price) > self.price_sync_threshold:
                        self.logger.warning(f"시세 차이 큼 ({abs(self.bitget_current_price - self.gate_current_price):.2f}$), 주문 처리 지연: {order_id}")
                        await asyncio.sleep(5)  # 5초 대기
                        continue
                    
                    await self.position_manager.process_filled_order(order)
                    self.position_manager.processed_orders.add(order_id)
                
                # 오래된 주문 ID 정리
                if len(self.position_manager.processed_orders) > 1000:
                    recent_orders = list(self.position_manager.processed_orders)[-500:]
                    self.position_manager.processed_orders = set(recent_orders)
                
                consecutive_errors = 0
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"주문 체결 감지 중 오류: {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 주문 체결 감지 시스템 오류\n연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL * 2)

    async def monitor_positions(self):
        """포지션 모니터링"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                bitget_active = [
                    pos for pos in bitget_positions 
                    if float(pos.get('total', 0)) > 0
                ]
                
                # 실제 포지션 처리
                active_position_ids = set()
                
                for pos in bitget_active:
                    pos_id = self.utils.generate_position_id(pos)
                    active_position_ids.add(pos_id)
                    await self.position_manager.process_position(pos)
                
                # 종료된 포지션 처리
                closed_positions = set(self.mirrored_positions.keys()) - active_position_ids
                for pos_id in closed_positions:
                    if pos_id not in self.startup_positions:
                        await self.position_manager.handle_position_close(pos_id)
                
                consecutive_errors = 0
                await asyncio.sleep(self.CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"포지션 모니터링 중 오류: {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 포지션 모니터링 오류\n연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(self.CHECK_INTERVAL * 2)

    async def _update_current_prices(self):
        """🔥🔥🔥 양쪽 거래소 현재 시세 업데이트 - 강화된 버전"""
        try:
            # 비트겟 현재가
            bitget_ticker = await self.bitget.get_ticker(self.SYMBOL)
            if bitget_ticker:
                self.bitget_current_price = float(bitget_ticker.get('last', 0))
            
            # 게이트 현재가
            try:
                gate_ticker = await self.gate.get_ticker(self.GATE_CONTRACT)
                if gate_ticker:
                    self.gate_current_price = float(gate_ticker.get('last', 0))
                else:
                    # 폴백: 계약 정보에서 조회
                    gate_contract_info = await self.gate.get_contract_info(self.GATE_CONTRACT)
                    if 'last_price' in gate_contract_info:
                        self.gate_current_price = float(gate_contract_info['last_price'])
                    elif 'mark_price' in gate_contract_info:
                        self.gate_current_price = float(gate_contract_info['mark_price'])
            except Exception as gate_error:
                self.logger.warning(f"게이트 시세 조회 실패, 비트겟 시세 사용: {gate_error}")
                self.gate_current_price = self.bitget_current_price
            
            # 🔥🔥🔥 시세 차이 계산 및 로깅
            if self.bitget_current_price > 0 and self.gate_current_price > 0:
                price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
                self.price_diff_percent = price_diff_abs / self.bitget_current_price * 100
                
                # 큰 시세 차이 감지 시 로깅
                if price_diff_abs > self.price_sync_threshold:
                    self.logger.warning(f"⚠️ 큰 시세 차이 감지: 비트겟 ${self.bitget_current_price:.2f}, 게이트 ${self.gate_current_price:.2f}, 차이 ${price_diff_abs:.2f}")
                    
            else:
                self.price_diff_percent = 0.0
            
            self.last_price_update = datetime.now()
            
            # 포지션 매니저에도 시세 정보 전달
            self.position_manager.update_prices(
                self.bitget_current_price, 
                self.gate_current_price, 
                self.price_diff_percent
            )
            
        except Exception as e:
            self.logger.error(f"시세 업데이트 실패: {e}")

    async def monitor_price_differences(self):
        """🔥🔥🔥 거래소 간 시세 차이 모니터링 - 강화된 버전"""
        consecutive_errors = 0
        last_warning_time = datetime.min
        
        while self.monitoring:
            try:
                await self._update_current_prices()
                
                # 시세 차이가 임계값을 초과하는 경우 주기적 경고
                price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
                now = datetime.now()
                
                if (price_diff_abs > self.price_sync_threshold and 
                    (now - last_warning_time).total_seconds() > 300):  # 5분마다 경고
                    
                    await self.telegram.send_message(
                        f"⚠️ 시세 차이 경고\n"
                        f"비트겟: ${self.bitget_current_price:,.2f}\n"
                        f"게이트: ${self.gate_current_price:,.2f}\n"
                        f"차이: ${price_diff_abs:.2f} (임계값: ${self.price_sync_threshold})\n"
                        f"백분율: {self.price_diff_percent:.3f}%\n\n"
                        f"🔄 미러링 지연 처리 활성화됨"
                    )
                    last_warning_time = now
                
                # 1시간마다 상세 시세 차이 리포트
                if (now - self.last_price_update).total_seconds() > 3600:
                    if self.price_diff_percent > 0.1:  # 0.1% 이상 차이
                        await self.telegram.send_message(
                            f"📊 시간당 시세 차이 리포트\n"
                            f"비트겟: ${self.bitget_current_price:,.2f}\n"
                            f"게이트: ${self.gate_current_price:,.2f}\n"
                            f"차이: ${price_diff_abs:.2f} ({self.price_diff_percent:.3f}%)\n"
                            f"상태: {'⚠️ 주의' if price_diff_abs > self.price_sync_threshold else '✅ 정상'}"
                        )
                
                consecutive_errors = 0
                await asyncio.sleep(30)  # 30초마다 체크
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"시세 차이 모니터링 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 시세 차이 모니터링 시스템 오류\n연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(60)  # 오류 시 1분 대기

    async def monitor_sync_status(self):
        """포지션 동기화 상태 모니터링"""
        sync_retry_count = 0
        
        while self.monitoring:
            try:
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)
                
                # 포지션 매니저에서 동기화 상태 확인
                sync_status = await self.position_manager.check_sync_status()
                
                if not sync_status['is_synced']:
                    sync_retry_count += 1
                    
                    if sync_retry_count >= 3:  # 3회 연속 불일치
                        # 시세 차이 정보 포함한 경고
                        price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
                        
                        await self.telegram.send_message(
                            f"⚠️ 포지션 동기화 불일치 지속\n"
                            f"비트겟 신규: {sync_status['bitget_new_count']}개\n"
                            f"게이트 신규: {sync_status['gate_new_count']}개\n"
                            f"차이: {sync_status['position_diff']}개\n"
                            f"시세 차이: ${price_diff_abs:.2f}\n"
                            f"연속 감지: {sync_retry_count}회\n\n"
                            f"🔄 시세 차이가 원인일 수 있습니다."
                        )
                        
                        sync_retry_count = 0  # 리셋
                else:
                    sync_retry_count = 0
                
            except Exception as e:
                self.logger.error(f"동기화 모니터링 오류: {e}")
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)

    async def generate_daily_reports(self):
        """일일 리포트 생성"""
        while self.monitoring:
            try:
                now = datetime.now()
                
                if now.hour == self.DAILY_REPORT_HOUR and now > self.last_report_time + timedelta(hours=23):
                    report = await self._create_daily_report()
                    await self.telegram.send_message(report)
                    
                    self._reset_daily_stats()
                    self.last_report_time = now
                
                await asyncio.sleep(3600)
                
            except Exception as e:
                self.logger.error(f"일일 리포트 생성 오류: {e}")
                await asyncio.sleep(3600)

    async def _create_daily_report(self) -> str:
        """🔥🔥🔥 일일 리포트 생성 - 시세 차이 정보 포함"""
        try:
            bitget_account = await self.bitget.get_account_info()
            gate_account = await self.gate.get_account_balance()
            
            bitget_equity = float(bitget_account.get('accountEquity', 0))
            gate_equity = float(gate_account.get('total', 0))
            
            success_rate = 0
            if self.daily_stats['total_mirrored'] > 0:
                success_rate = (self.daily_stats['successful_mirrors'] / 
                              self.daily_stats['total_mirrored']) * 100
            
            # 시세 차이 통계
            await self._update_current_prices()
            price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
            
            report = f"""📊 미러 트레이딩 일일 리포트 (시세차이 문제 해결)
📅 {datetime.now().strftime('%Y-%m-%d')}
━━━━━━━━━━━━━━━━━━━

💰 계정 잔고:
- 비트겟: ${bitget_equity:,.2f}
- 게이트: ${gate_equity:,.2f}

📈 시세 차이 현황:
- 비트겟: ${self.bitget_current_price:,.2f}
- 게이트: ${self.gate_current_price:,.2f}
- 차이: ${price_diff_abs:.2f} ({self.price_diff_percent:.3f}%)
- {'⚠️ 임계값 초과' if price_diff_abs > self.price_sync_threshold else '✅ 정상 범위'}

⚡ 실시간 포지션 미러링:
- 주문 체결 기반: {self.daily_stats['order_mirrors']}회
- 포지션 기반: {self.daily_stats['position_mirrors']}회
- 총 시도: {self.daily_stats['total_mirrored']}회
- 성공: {self.daily_stats['successful_mirrors']}회
- 실패: {self.daily_stats['failed_mirrors']}회
- 성공률: {success_rate:.1f}%

🔄 예약 주문 미러링:
- 시작 시 복제: {self.daily_stats['startup_plan_mirrors']}회
- 신규 미러링: {self.daily_stats['plan_order_mirrors']}회
- 취소 동기화: {self.daily_stats['plan_order_cancels']}회
- 클로즈 주문: {self.daily_stats['close_order_mirrors']}회
- 중복 방지: {self.daily_stats['duplicate_orders_prevented']}회

📉 포지션 관리:
- 부분 청산: {self.daily_stats['partial_closes']}회
- 전체 청산: {self.daily_stats['full_closes']}회
- 총 거래량: ${self.daily_stats['total_volume']:,.2f}

🔄 현재 미러링 상태:
- 활성 포지션: {len(self.mirrored_positions)}개
- 예약 주문: {len(self.position_manager.mirrored_plan_orders)}개
- 실패 기록: {len(self.failed_mirrors)}건

━━━━━━━━━━━━━━━━━━━
🎯 시세차이 문제 해결 + 코드 분할 완료"""
            
            if self.daily_stats['errors']:
                report += f"\n⚠️ 오류 발생: {len(self.daily_stats['errors'])}건"
            
            return report
            
        except Exception as e:
            self.logger.error(f"리포트 생성 실패: {e}")
            return f"📊 일일 리포트 생성 실패\n오류: {str(e)}"

    def _reset_daily_stats(self):
        """일일 통계 초기화"""
        self.daily_stats = {
            'total_mirrored': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'total_volume': 0.0,
            'order_mirrors': 0,
            'position_mirrors': 0,
            'plan_order_mirrors': 0,
            'plan_order_cancels': 0,
            'plan_order_cancel_success': 0,
            'plan_order_cancel_failed': 0,
            'startup_plan_mirrors': 0,
            'close_order_mirrors': 0,
            'close_order_skipped': 0,
            'duplicate_orders_prevented': 0,
            'render_restart_skips': 0,
            'unified_tp_sl_orders': 0,
            'duplicate_advanced_prevention': 0,
            'price_duplicate_prevention': 0,
            'price_sync_delays': 0,  # 🔥🔥🔥 시세 차이로 인한 지연 카운트
            'position_wait_timeouts': 0,  # 🔥🔥🔥 포지션 체결 대기 타임아웃
            'errors': []
        }
        self.failed_mirrors.clear()
        
        # 포지션 매니저의 통계도 동기화
        self.position_manager.daily_stats = self.daily_stats

    async def _log_account_status(self):
        """🔥🔥🔥 계정 상태 로깅 - 시세 차이 정보 포함"""
        try:
            bitget_account = await self.bitget.get_account_info()
            bitget_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            gate_account = await self.gate.get_account_balance()
            gate_equity = float(gate_account.get('total', 0))
            
            # 시세 차이 정보
            price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
            price_status = "정상" if price_diff_abs <= self.price_sync_threshold else "주의 필요"
            
            await self.telegram.send_message(
                f"🔄 미러 트레이딩 시스템 시작 (시세차이 문제 해결)\n\n"
                f"💰 계정 잔고:\n"
                f"• 비트겟: ${bitget_equity:,.2f}\n"
                f"• 게이트: ${gate_equity:,.2f}\n\n"
                f"📈 시세 상태:\n"
                f"• 비트겟: ${self.bitget_current_price:,.2f}\n"
                f"• 게이트: ${self.gate_current_price:,.2f}\n"
                f"• 차이: ${price_diff_abs:.2f} ({price_status})\n"
                f"• 임계값: ${self.price_sync_threshold}\n\n"
                f"📊 현재 상태:\n"
                f"• 기존 포지션: {len(self.startup_positions)}개 (복제 제외)\n"
                f"• 기존 예약 주문: {len(self.position_manager.startup_plan_orders)}개\n"
                f"• 현재 복제된 예약 주문: {len(self.position_manager.mirrored_plan_orders)}개\n\n"
                f"⚡ 개선 사항:\n"
                f"• 시세 차이 실시간 모니터링\n"
                f"• 포지션 체결 확인 후 클로즈 주문 생성\n"
                f"• 강화된 레버리지 설정\n"
                f"• 코드 3개 파일로 분할\n"
                f"• 포지션 체결 대기 시간: {self.position_wait_timeout}초"
            )
            
        except Exception as e:
            self.logger.error(f"계정 상태 조회 실패: {e}")

    async def stop(self):
        """미러 트레이딩 중지"""
        self.monitoring = False
        
        try:
            # 포지션 매니저 중지
            await self.position_manager.stop()
            
            final_report = await self._create_daily_report()
            await self.telegram.send_message(f"🛑 미러 트레이딩 시스템 종료\n\n{final_report}")
        except:
            pass
        
        self.logger.info("미러 트레이딩 시스템 중지")
