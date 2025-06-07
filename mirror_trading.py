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
        self.bitget = bitget_client  # 기본 수익 조회용
        self.gate = gate_client  # 기본 수익 조회용
        self.telegram = telegram_bot
        self.logger = logging.getLogger('mirror_trading')
        
        # Bitget 미러링 전용 클라이언트 import
        try:
            from bitget_mirror_client import BitgetMirrorClient
            self.bitget_mirror = BitgetMirrorClient(config)
            logger.info("✅ Bitget 미러링 전용 클라이언트 초기화")
        except ImportError as e:
            logger.error(f"❌ Bitget 미러링 클라이언트 import 실패: {e}")
            raise
        
        # 유틸리티 클래스 초기화 (미러링 클라이언트 사용)
        self.utils = MirrorTradingUtils(config, self.bitget_mirror, gate_client)
        
        # Gate.io 미러링 전용 클라이언트 import
        try:
            from gateio_mirror_client import GateioMirrorClient
            self.gate_mirror = GateioMirrorClient(config)
            # 🔥🔥🔥 텔레그램 봇 설정 (시장가 체결 알림용)
            self.gate_mirror.set_telegram_bot(telegram_bot)
            logger.info("✅ Gate.io 미러링 전용 클라이언트 초기화 + 텔레그램 알림 설정")
        except ImportError as e:
            logger.error(f"❌ Gate.io 미러링 클라이언트 import 실패: {e}")
            raise
        
        # 포지션 관리자 초기화 (미러링 클라이언트 포함)
        self.position_manager = MirrorPositionManager(
            config, self.bitget_mirror, gate_client, self.gate_mirror, telegram_bot, self.utils
        )
        
        # 미러링 상태 관리 (포지션 매니저에 위임)
        self.mirrored_positions = self.position_manager.mirrored_positions
        self.startup_positions = self.position_manager.startup_positions
        self.failed_mirrors = self.position_manager.failed_mirrors
        
        # 기본 설정
        self.last_sync_check = datetime.min
        self.last_report_time = datetime.min
        
        # 🔥🔥🔥 시세 차이 관리 - 처리 차단 없음으로 완전 변경
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.last_price_update: datetime = datetime.min
        self.price_sync_threshold: float = 999999.0  # 🔥🔥🔥 사실상 무제한으로 설정
        self.position_wait_timeout: int = 0  # 🔥🔥🔥 대기 시간 완전 제거
        
        # 시세 조회 실패 관리 강화
        self.last_valid_bitget_price: float = 0.0
        self.last_valid_gate_price: float = 0.0
        self.bitget_price_failures: int = 0
        self.gate_price_failures: int = 0
        self.max_price_failures: int = 10
        
        # 예약 주문 동기화 강화 설정
        self.order_sync_enabled: bool = True
        self.order_sync_interval: int = 15
        self.last_order_sync_time: datetime = datetime.min
        
        # 🔥🔥🔥 슬리피지 보호 개선 - 0.05% (약 50달러)
        self.max_slippage_percent: float = 0.05
        
        # 모니터링 상태
        self.monitoring = True
        self.system_initialized = False
        
        # 타이밍 설정
        self.CHECK_INTERVAL = 2
        self.ORDER_CHECK_INTERVAL = 1
        self.SYNC_CHECK_INTERVAL = 30
        self.PRICE_CHECK_INTERVAL = 5
        self.DAILY_REPORT_HOUR = 9
        
        # 정확한 심볼 설정
        self.SYMBOL = "BTCUSDT"  # Bitget
        self.GATE_CONTRACT = "BTC_USDT"  # Gate.io
        
        # 성과 추적 (포지션 매니저에 위임)
        self.daily_stats = self.position_manager.daily_stats
        
        logger.info("✅ 미러 트레이딩 시스템 초기화 완료")

    async def start(self):
        """미러 트레이딩 시작"""
        try:
            self.logger.info("🚀 미러 트레이딩 시스템 시작")
            
            # 🔥🔥🔥 초기화 수행 - 실패해도 시스템 시작
            initialization_success = await self._perform_initialization()
            
            if initialization_success:
                self.logger.info("✅ 초기화 완료 - 모든 기능 정상")
                self.system_initialized = True
            else:
                self.logger.warning("⚠️ 초기화 일부 실패하지만 계속 진행")
                self.system_initialized = False
            
            # 🔥🔥🔥 초기화 성공 여부와 관계없이 모니터링 시작
            await self.telegram.send_message(
                f"🔥 미러 트레이딩 시스템 시작\n"
                f"초기화 상태: {'✅ 성공' if initialization_success else '⚠️ 부분 실패'}\n"
                f"🎯 정확한 심볼: {self.SYMBOL}\n"
                f"🎯 예약 주문 모니터링: 활성화\n"
                f"🛡️ 슬리피지 보호: 0.05% (약 $50)\n"
                f"🔥 시세 차이와 무관하게 즉시 처리\n"
                f"📱 텔레그램 알림: 활성화"
            )
            
            # 모니터링 태스크 시작
            tasks = [
                self.monitor_plan_orders(),
                self.monitor_order_fills(), 
                self.monitor_positions(),
                self.monitor_sync_status(),
                self.monitor_price_differences(),
                self.monitor_order_synchronization(),
                self.generate_daily_reports()
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시작 실패: {e}")
            await self.telegram.send_message(
                f"❌ 미러 트레이딩 시작 실패\n오류: {str(e)[:200]}\n"
                f"🔄 5분 후 자동 재시작 시도"
            )
            
            # 5분 후 재시작 시도
            await asyncio.sleep(300)
            await self.start()

    async def _perform_initialization(self) -> bool:
        """🔥🔥🔥 단계별 초기화 수행"""
        try:
            self.logger.info("🎯 미러 트레이딩 시스템 초기화 시작")
            
            # 1. Bitget 미러링 클라이언트 초기화
            try:
                await self.bitget_mirror.initialize()
                self.logger.info("✅ Bitget 미러링 클라이언트 초기화 성공")
            except Exception as e:
                self.logger.error(f"❌ Bitget 미러링 클라이언트 초기화 실패: {e}")
                return False
            
            # 2. Gate.io 미러링 클라이언트 초기화
            try:
                await self.gate_mirror.initialize()
                self.logger.info("✅ Gate.io 미러링 클라이언트 초기화 성공")
            except Exception as e:
                self.logger.error(f"❌ Gate.io 미러링 클라이언트 초기화 실패: {e}")
                return False
            
            # 3. 현재 시세 업데이트
            try:
                await self._update_current_prices()
                self.logger.info("✅ 현재 시세 업데이트 성공")
            except Exception as e:
                self.logger.warning(f"⚠️ 현재 시세 업데이트 실패: {e}")
                # 시세 업데이트 실패는 치명적이지 않음
            
            # 4. 포지션 매니저 초기화
            try:
                self.position_manager.price_sync_threshold = self.price_sync_threshold
                self.position_manager.position_wait_timeout = self.position_wait_timeout
                await self.position_manager.initialize()
                self.logger.info("✅ 포지션 매니저 초기화 성공")
            except Exception as e:
                self.logger.error(f"❌ 포지션 매니저 초기화 실패: {e}")
                # 포지션 매니저 초기화 실패해도 기본 모니터링은 시작
                self.position_manager.monitoring_enabled = True
                self.position_manager.startup_plan_orders_processed = True
            
            # 5. 초기 계정 상태 출력
            try:
                await self._log_account_status()
                self.logger.info("✅ 계정 상태 출력 성공")
            except Exception as e:
                self.logger.warning(f"⚠️ 계정 상태 출력 실패: {e}")
                # 계정 상태 출력 실패는 치명적이지 않음
            
            return True
            
        except Exception as e:
            self.logger.error(f"전체 초기화 실패: {e}")
            return False

    async def monitor_plan_orders(self):
        """🔥🔥🔥 예약 주문 모니터링 - 포지션 매니저로 위임 + 강화된 안정성"""
        self.logger.info("🎯 예약 주문 모니터링 시작")
        
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while self.monitoring:
            try:
                # 🔥🔥🔥 포지션 매니저 모니터링 활성화 체크
                if not hasattr(self.position_manager, 'monitoring_enabled'):
                    self.position_manager.monitoring_enabled = True
                    self.logger.info("포지션 매니저 모니터링 강제 활성화")
                
                if not self.position_manager.monitoring_enabled:
                    self.logger.debug("포지션 매니저 모니터링 비활성화 상태, 5초 대기")
                    await asyncio.sleep(5)
                    continue
                
                # 포지션 매니저의 모니터링 사이클 실행
                await self.position_manager.monitor_plan_orders()
                
                consecutive_errors = 0
                await asyncio.sleep(self.CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"예약 주문 모니터링 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    await self.telegram.send_message(
                        f"⚠️ 예약 주문 모니터링 시스템 오류\n"
                        f"연속 {consecutive_errors}회 실패\n"
                        f"시스템 재시작을 권장합니다."
                    )
                    # 연속 실패 카운터 리셋하고 계속 시도
                    consecutive_errors = 0
                    await asyncio.sleep(30)
                else:
                    await asyncio.sleep(5)

    async def monitor_order_fills(self):
        """🔥🔥🔥 실시간 주문 체결 감지 - 슬리피지 보호 0.05% 적용"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                # 현재 시세 업데이트 (정보용)
                await self._update_current_prices()
                
                # 🔥🔥🔥 시세 차이 확인만 하고 처리는 항상 즉시 진행
                valid_price_diff = self._get_valid_price_difference()
                if valid_price_diff is not None:
                    self.logger.debug(f"시세 차이 ${valid_price_diff:.2f} 확인됨, 슬리피지 보호 0.05% 적용하여 즉시 처리")
                
                # 미러링 클라이언트로 체결 주문 조회 - symbol 인자 제거
                filled_orders = await self.bitget_mirror.get_recent_filled_orders(
                    minutes=1
                )
                
                for order in filled_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if not order_id or order_id in self.position_manager.processed_orders:
                        continue
                    
                    reduce_only = order.get('reduceOnly', 'false')
                    if reduce_only == 'true' or reduce_only is True:
                        continue
                    
                    # 🔥🔥🔥 슬리피지 보호 정보 추가
                    await self._process_filled_order_with_slippage_protection(order)
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

    async def _process_filled_order_with_slippage_protection(self, order: Dict):
        """🔥🔥🔥 슬리피지 보호 0.05%가 적용된 체결 주문 처리"""
        try:
            order_id = order.get('orderId', order.get('id', ''))
            side = order.get('side', '').lower()
            size = float(order.get('size', 0))
            fill_price = float(order.get('fillPrice', order.get('price', 0)))
            
            # 🔥🔥🔥 슬리피지 체크 0.05% (약 50달러)
            current_gate_price = await self.gate_mirror.get_current_price(self.GATE_CONTRACT)
            
            if current_gate_price > 0 and fill_price > 0:
                price_diff_percent = abs(current_gate_price - fill_price) / fill_price * 100
                
                if price_diff_percent > self.max_slippage_percent:
                    self.logger.warning(f"⚠️ 가격 차이 감지: {price_diff_percent:.3f}% - 슬리피지 보호 0.05% 적용")
                    
                    # 게이트 슬리피지 보호 활성화
                    self.gate_mirror.SLIPPAGE_CHECK_ENABLED = True
                    self.gate_mirror.MAX_SLIPPAGE_PERCENT = self.max_slippage_percent
                    
                    await self.telegram.send_message(
                        f"🛡️ 슬리피지 보호 0.05% 활성화\n"
                        f"비트겟 체결가: ${fill_price:,.2f}\n"
                        f"게이트 현재가: ${current_gate_price:,.2f}\n"
                        f"가격 차이: {price_diff_percent:.3f}%\n"
                        f"💡 5초간 지정가 시도 후 시장가 전환으로 안전하게 처리"
                    )
                else:
                    # 정상 범위내면 슬리피지 보호 기본값 사용
                    self.gate_mirror.SLIPPAGE_CHECK_ENABLED = True
                    self.gate_mirror.MAX_SLIPPAGE_PERCENT = 0.05
            
            # 기존 체결 주문 처리 로직 호출
            await self.position_manager.process_filled_order(order)
            
        except Exception as e:
            self.logger.error(f"슬리피지 보호 체결 주문 처리 실패: {e}")
            # 실패해도 기본 처리는 진행
            await self.position_manager.process_filled_order(order)

    async def monitor_positions(self):
        """포지션 모니터링"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                # 미러링 클라이언트로 포지션 조회
                bitget_positions = await self.bitget_mirror.get_positions(self.SYMBOL)
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
        """양쪽 거래소 현재 시세 업데이트"""
        try:
            # 비트겟 현재가 조회
            try:
                bitget_ticker = await self.bitget_mirror.get_ticker(self.SYMBOL)
                if bitget_ticker and bitget_ticker.get('last'):
                    new_bitget_price = float(bitget_ticker.get('last'))
                    if new_bitget_price > 0:
                        self.bitget_current_price = new_bitget_price
                        self.last_valid_bitget_price = new_bitget_price
                        self.bitget_price_failures = 0
                else:
                    self.bitget_price_failures += 1
                    if self.last_valid_bitget_price > 0:
                        self.bitget_current_price = self.last_valid_bitget_price
            except Exception as e:
                self.logger.debug(f"비트겟 시세 조회 실패: {e}")
                self.bitget_price_failures += 1
                if self.last_valid_bitget_price > 0:
                    self.bitget_current_price = self.last_valid_bitget_price
            
            # 게이트 현재가 조회
            try:
                gate_price = await self.gate_mirror.get_current_price(self.GATE_CONTRACT)
                if gate_price and gate_price > 0:
                    self.gate_current_price = gate_price
                    self.last_valid_gate_price = gate_price
                    self.gate_price_failures = 0
                else:
                    self.gate_price_failures += 1
                    if self.last_valid_gate_price > 0:
                        self.gate_current_price = self.last_valid_gate_price
            except Exception as e:
                self.logger.debug(f"게이트 시세 조회 실패: {e}")
                self.gate_price_failures += 1
                if self.last_valid_gate_price > 0:
                    self.gate_current_price = self.last_valid_gate_price
            
            # 시세 차이 계산 - 정보용으로만 사용
            if self.bitget_current_price > 0 and self.gate_current_price > 0:
                price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
                self.price_diff_percent = price_diff_abs / self.bitget_current_price * 100
                
                # 🔥🔥🔥 시세 차이는 정보용으로만 사용, 처리에는 영향 없음
                if price_diff_abs <= 10000:  # 10000달러까지 정상으로 간주
                    if price_diff_abs > 100:  # 100달러 이상일 때만 로깅
                        self.logger.debug(f"시세 차이 정보: 비트겟 ${self.bitget_current_price:.2f}, 게이트 ${self.gate_current_price:.2f}, 차이 ${price_diff_abs:.2f} (처리에 영향 없음)")
                else:
                    self.logger.info(f"큰 시세 차이 감지: ${price_diff_abs:.2f}, 슬리피지 보호 0.05%로 안전하게 처리")
                    
            else:
                self.price_diff_percent = 0.0
                self.logger.warning(f"시세 조회 실패: 비트겟={self.bitget_current_price}, 게이트={self.gate_current_price}")
            
            self.last_price_update = datetime.now()
            
            # 포지션 매니저에도 시세 정보 전달
            self.position_manager.update_prices(
                self.bitget_current_price, 
                self.gate_current_price, 
                self.price_diff_percent
            )
            
        except Exception as e:
            self.logger.error(f"시세 업데이트 실패: {e}")

    def _get_valid_price_difference(self) -> Optional[float]:
        """유효한 시세 차이 반환 (0 가격 제외)"""
        try:
            if self.bitget_current_price <= 0 or self.gate_current_price <= 0:
                return None
            
            price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
            
            # 🔥🔥🔥 정보용으로만 사용 - 처리 차단 없음
            return price_diff_abs
            
        except Exception as e:
            self.logger.error(f"시세 차이 계산 실패: {e}")
            return None

    async def monitor_price_differences(self):
        """🔥🔥🔥 거래소 간 시세 차이 모니터링 - 정보용으로만 사용"""
        consecutive_errors = 0
        last_warning_time = datetime.min
        last_normal_report_time = datetime.min
        
        while self.monitoring:
            try:
                await self._update_current_prices()
                
                # 유효한 시세 차이만 확인 (정보용)
                valid_price_diff = self._get_valid_price_difference()
                
                if valid_price_diff is None:
                    self.logger.debug("유효하지 않은 시세 차이")
                    consecutive_errors = 0
                    await asyncio.sleep(self.PRICE_CHECK_INTERVAL)
                    continue
                
                # 🔥🔥🔥 극도로 높은 임계값 설정으로 알림 최소화
                if valid_price_diff > 10000:  # 10000달러 이상일 때만 알림
                    if datetime.now() - last_warning_time > timedelta(minutes=30):
                        await self.telegram.send_message(
                            f"📊 큰 시세 차이 정보\n"
                            f"비트겟: ${self.bitget_current_price:,.2f}\n"
                            f"게이트: ${self.gate_current_price:,.2f}\n"
                            f"차이: ${valid_price_diff:.2f} ({self.price_diff_percent:.3f}%)\n"
                            f"💡 슬리피지 보호 0.05%로 안전하게 처리 중"
                        )
                        last_warning_time = datetime.now()
                else:
                    # 🔥🔥🔥 정상 범위 알림은 하루에 한 번만
                    if datetime.now() - last_normal_report_time > timedelta(hours=24):
                        self.logger.info(
                            f"시세 차이 정상 범위: ${valid_price_diff:.2f} "
                            f"(비트겟 ${self.bitget_current_price:.2f}, 게이트 ${self.gate_current_price:.2f})"
                        )
                        last_normal_report_time = datetime.now()
                
                consecutive_errors = 0
                await asyncio.sleep(self.PRICE_CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"시세 차이 모니터링 오류: {e}")
                
                if consecutive_errors >= 5:
                    self.logger.warning(f"시세 차이 모니터링 연속 {consecutive_errors}회 실패")
                
                await asyncio.sleep(self.PRICE_CHECK_INTERVAL * 2)

    async def monitor_order_synchronization(self):
        """🔥🔥🔥 예약 주문 동기화 상태 모니터링 - 종합 개선"""
        sync_retry_count = 0
        
        while self.monitoring:
            try:
                if not self.order_sync_enabled:
                    await asyncio.sleep(self.order_sync_interval)
                    continue
                
                # 동기화 체크 주기
                if datetime.now() - self.last_order_sync_time > timedelta(seconds=self.order_sync_interval):
                    await self._comprehensive_order_sync()
                    self.last_order_sync_time = datetime.now()
                    sync_retry_count = 0
                
                await asyncio.sleep(5)
                
            except Exception as e:
                sync_retry_count += 1
                self.logger.error(f"예약 주문 동기화 오류 (시도 {sync_retry_count}): {e}")
                
                if sync_retry_count >= 3:
                    await self.telegram.send_message(
                        f"⚠️ 예약 주문 동기화 연속 실패\n"
                        f"오류: {str(e)[:200]}\n"
                        f"🔄 30초 후 재시도"
                    )
                    await asyncio.sleep(30)
                else:
                    await asyncio.sleep(10)

    async def _comprehensive_order_sync(self):
        """🔥🔥🔥 종합적인 예약 주문 동기화 - 누락/고아 주문 처리"""
        try:
            self.logger.info("🔄 예약 주문 동기화 모니터링 시작")
            
            # 1. 비트겟 예약 주문 조회
            plan_data = await self.bitget_mirror.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            bitget_plan_orders = plan_data.get('plan_orders', [])
            bitget_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            # 모든 비트겟 예약 주문 (TP/SL 클로즈 주문 포함)
            all_bitget_orders = []
            all_bitget_orders.extend(bitget_plan_orders)
            
            # TP/SL 주문 중 클로즈 주문만 추가
            for tp_sl_order in bitget_tp_sl_orders:
                side = tp_sl_order.get('side', tp_sl_order.get('tradeSide', '')).lower()
                reduce_only = tp_sl_order.get('reduceOnly', False)
                
                is_close_order = (
                    'close' in side or 
                    reduce_only is True or 
                    reduce_only == 'true'
                )
                
                if is_close_order:
                    all_bitget_orders.append(tp_sl_order)
            
            # 2. 게이트 예약 주문 조회
            gate_orders = await self.gate_mirror.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            # 3. 동기화 분석
            sync_analysis = await self._analyze_comprehensive_sync(all_bitget_orders, gate_orders)
            
            # 4. 문제가 있으면 수정
            if sync_analysis['requires_action']:
                await self._fix_sync_issues(sync_analysis)
            else:
                self.logger.debug(f"✅ 예약 주문 동기화 상태 양호: 비트겟 {len(all_bitget_orders)}개, 게이트 {len(gate_orders)}개")
            
        except Exception as e:
            self.logger.error(f"종합 예약 주문 동기화 실패: {e}")

    async def _analyze_comprehensive_sync(self, bitget_orders: List[Dict], gate_orders: List[Dict]) -> Dict:
        """종합적인 동기화 분석"""
        try:
            analysis = {
                'requires_action': False,
                'missing_mirrors': [],
                'orphaned_orders': [],
                'price_mismatches': [],
                'size_mismatches': [],
                'total_issues': 0
            }
            
            # 비트겟 주문 분석
            for bitget_order in bitget_orders:
                bitget_order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
                if not bitget_order_id:
                    continue
                
                # 스타트업 주문은 제외
                if bitget_order_id in self.position_manager.startup_plan_orders:
                    continue
                
                # 미러링 기록 확인
                if bitget_order_id in self.position_manager.mirrored_plan_orders:
                    mirror_info = self.position_manager.mirrored_plan_orders[bitget_order_id]
                    expected_gate_id = mirror_info.get('gate_order_id')
                    
                    # 게이트에서 해당 주문 찾기
                    gate_order_found = None
                    for gate_order in gate_orders:
                        if gate_order.get('id') == expected_gate_id:
                            gate_order_found = gate_order
                            break
                    
                    if not gate_order_found:
                        # 미러링 기록은 있는데 게이트에 주문이 없음 (누락)
                        analysis['missing_mirrors'].append({
                            'bitget_order_id': bitget_order_id,
                            'bitget_order': bitget_order,
                            'expected_gate_id': expected_gate_id
                        })
                        analysis['requires_action'] = True
                        
                else:
                    # 미러링 기록이 없음 (새로운 주문)
                    analysis['missing_mirrors'].append({
                        'bitget_order_id': bitget_order_id,
                        'bitget_order': bitget_order,
                        'expected_gate_id': None
                    })
                    analysis['requires_action'] = True
            
            # 게이트 고아 주문 찾기
            for gate_order in gate_orders:
                gate_order_id = gate_order.get('id')
                if not gate_order_id:
                    continue
                
                # 이 게이트 주문이 어떤 비트겟 주문의 미러인지 찾기
                is_orphan = True
                for bitget_order_id, mirror_info in self.position_manager.mirrored_plan_orders.items():
                    if mirror_info.get('gate_order_id') == gate_order_id:
                        # 비트겟에 원본이 있는지 확인
                        bitget_exists = any(
                            o.get('orderId', o.get('planOrderId', '')) == bitget_order_id 
                            for o in bitget_orders
                        )
                        if bitget_exists:
                            is_orphan = False
                            break
                
                if is_orphan:
                    analysis['orphaned_orders'].append({
                        'gate_order_id': gate_order_id,
                        'gate_order': gate_order
                    })
                    analysis['requires_action'] = True
            
            analysis['total_issues'] = (
                len(analysis['missing_mirrors']) + 
                len(analysis['orphaned_orders'])
            )
            
            if analysis['total_issues'] > 0:
                self.logger.info(
                    f"🔍 동기화 문제 발견: "
                    f"누락 미러링 {len(analysis['missing_mirrors'])}개, "
                    f"고아 주문 {len(analysis['orphaned_orders'])}개"
                )
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"동기화 분석 실패: {e}")
            return {'requires_action': False, 'total_issues': 0}

    async def _fix_sync_issues(self, sync_analysis: Dict):
        """동기화 문제 해결"""
        try:
            fixed_count = 0
            
            # 1. 누락된 미러링 처리 (병렬 처리로 속도 개선)
            missing_tasks = []
            for missing in sync_analysis['missing_mirrors'][:5]:  # 최대 5개씩 병렬 처리
                try:
                    bitget_order = missing['bitget_order']
                    bitget_order_id = missing['bitget_order_id']
                    
                    self.logger.info(f"🔄 누락된 미러링 복제: {bitget_order_id}")
                    
                    # 이미 처리된 주문인지 확인
                    if bitget_order_id not in self.position_manager.processed_plan_orders:
                        task = self.position_manager._process_perfect_mirror_order(bitget_order)
                        missing_tasks.append((bitget_order_id, task))
                        
                        self.position_manager.processed_plan_orders.add(bitget_order_id)
                    
                except Exception as e:
                    self.logger.error(f"누락 미러링 태스크 생성 실패: {missing['bitget_order_id']} - {e}")
            
            # 병렬 실행
            if missing_tasks:
                results = await asyncio.gather(*[task for _, task in missing_tasks], return_exceptions=True)
                
                for i, (order_id, _) in enumerate(missing_tasks):
                    try:
                        result = results[i]
                        if isinstance(result, Exception):
                            self.logger.error(f"누락 미러링 실행 실패: {order_id} - {result}")
                        elif result in ["perfect_success", "partial_success"]:
                            fixed_count += 1
                            self.daily_stats['sync_corrections'] += 1
                            self.logger.info(f"✅ 누락 미러링 완료: {order_id}")
                    except Exception as e:
                        self.logger.error(f"누락 미러링 결과 처리 실패: {order_id} - {e}")
            
            # 2. 고아 주문 삭제 (병렬 처리)
            orphan_tasks = []
            for orphan in sync_analysis['orphaned_orders'][:5]:  # 최대 5개씩 병렬 처리
                try:
                    gate_order_id = orphan['gate_order_id']
                    self.logger.info(f"🗑️ 고아 주문 삭제: {gate_order_id}")
                    
                    task = self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                    orphan_tasks.append((gate_order_id, task))
                    
                except Exception as e:
                    self.logger.error(f"고아 주문 삭제 태스크 생성 실패: {orphan['gate_order_id']} - {e}")
            
            # 병렬 실행
            if orphan_tasks:
                results = await asyncio.gather(*[task for _, task in orphan_tasks], return_exceptions=True)
                
                for i, (order_id, _) in enumerate(orphan_tasks):
                    try:
                        result = results[i]
                        if isinstance(result, Exception):
                            self.logger.error(f"고아 주문 삭제 실패: {order_id} - {result}")
                        elif result:
                            fixed_count += 1
                            self.daily_stats['sync_deletions'] += 1
                            self.logger.info(f"✅ 고아 주문 삭제 완료: {order_id}")
                    except Exception as e:
                        self.logger.error(f"고아 주문 삭제 결과 처리 실패: {order_id} - {e}")
            
            # 동기화 결과 알림 (5개 이상 문제가 해결되었을 때만)
            if fixed_count >= 5:
                price_diff = abs(self.bitget_current_price - self.gate_current_price) if (self.bitget_current_price > 0 and self.gate_current_price > 0) else 0
                await self.telegram.send_message(
                    f"🔄 예약 주문 대규모 동기화 완료\n"
                    f"해결된 문제: {fixed_count}건\n"
                    f"- 누락 미러링 복제: {len(sync_analysis['missing_mirrors'])}건\n"
                    f"- 고아 주문 삭제: {len(sync_analysis['orphaned_orders'])}건\n\n"
                    f"📊 현재 시세 차이: ${price_diff:.2f}\n"
                    f"🔥 시세 차이와 무관하게 모든 주문 즉시 처리\n"
                    f"🛡️ 슬리피지 보호 0.05% (약 $50) 적용"
                )
            elif fixed_count > 0:
                self.logger.info(f"🔄 예약 주문 동기화 완료: {fixed_count}건 해결")
            
        except Exception as e:
            self.logger.error(f"동기화 문제 해결 실패: {e}")

    async def monitor_sync_status(self):
        """동기화 상태 모니터링"""
        while self.monitoring:
            try:
                now = datetime.now()
                
                if now - self.last_sync_check > timedelta(minutes=5):
                    sync_retry_count = 0
                    
                    # 포지션 동기화 체크
                    bitget_positions = await self.bitget_mirror.get_positions(self.SYMBOL)
                    bitget_active = [
                        pos for pos in bitget_positions 
                        if float(pos.get('total', 0)) > 0
                    ]
                    
                    # 게이트 포지션 확인
                    gate_positions = await self.gate_mirror.get_positions(self.GATE_CONTRACT)
                    gate_active = [
                        pos for pos in gate_positions 
                        if pos.get('size', 0) != 0
                    ]
                    
                    if len(bitget_active) != len(gate_active):
                        sync_retry_count += 1
                        self.logger.warning(
                            f"포지션 동기화 불일치: 비트겟 {len(bitget_active)}개, "
                            f"게이트 {len(gate_active)}개"
                        )
                        
                        if sync_retry_count >= 3:
                            await self.telegram.send_message(
                                f"⚠️ 포지션 동기화 경고\n"
                                f"비트겟: {len(bitget_active)}개\n"
                                f"게이트: {len(gate_active)}개\n"
                                f"수동 확인이 필요할 수 있습니다."
                            )
                            sync_retry_count = 0
                    else:
                        sync_retry_count = 0
                    
                    self.last_sync_check = now
                    
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)
                
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
        """일일 리포트 생성"""
        try:
            # 기본 클라이언트로 계정 조회
            bitget_account = await self.bitget.get_account_info()
            gate_account = await self.gate_mirror.get_account_balance()
            
            bitget_equity = float(bitget_account.get('accountEquity', 0))
            gate_equity = float(gate_account.get('total', 0))
            
            success_rate = 0
            if self.daily_stats['total_mirrored'] > 0:
                success_rate = (self.daily_stats['successful_mirrors'] / 
                              self.daily_stats['total_mirrored']) * 100
            
            # 시세 차이 통계
            await self._update_current_prices()
            valid_price_diff = self._get_valid_price_difference()
            
            price_status_info = ""
            if valid_price_diff is not None:
                price_status_info = f"""📈 시세 차이 현황:
- 비트겟: ${self.bitget_current_price:,.2f}
- 게이트: ${self.gate_current_price:,.2f}
- 차이: ${valid_price_diff:.2f} ({self.price_diff_percent:.3f}%)
- 🔥 처리 상태: 시세 차이와 무관하게 모든 주문 즉시 처리
- 🛡️ 슬리피지 보호: 0.05% (약 $50) 제한
- ⏰ 지정가 대기: 5초 후 시장가 전환"""
            else:
                price_status_info = f"""📈 시세 차이 현황:
- 시세 조회에 문제가 있었습니다
- 비트겟 조회 실패: {self.bitget_price_failures}회
- 게이트 조회 실패: {self.gate_price_failures}회
- 🔥 처리 상태: 시세 조회 실패와 무관하게 모든 주문 정상 처리
- 🛡️ 슬리피지 보호: 0.05% 활성화됨"""
            
            # TP/SL 미러링 성과 통계
            perfect_mirrors = self.daily_stats.get('perfect_mirrors', 0)
            partial_mirrors = self.daily_stats.get('partial_mirrors', 0)
            tp_sl_success = self.daily_stats.get('tp_sl_success', 0)
            tp_sl_failed = self.daily_stats.get('tp_sl_failed', 0)
            
            report = f"""📊 미러 트레이딩 일일 리포트
📅 {datetime.now().strftime('%Y-%m-%d')}
━━━━━━━━━━━━━━━━━━━

💰 계정 잔고:
- 비트겟: ${bitget_equity:,.2f}
- 게이트: ${gate_equity:,.2f}

{price_status_info}

⚡ 실시간 포지션 미러링:
- 주문 체결 기반: {self.daily_stats['order_mirrors']}회
- 포지션 기반: {self.daily_stats['position_mirrors']}회
- 총 시도: {self.daily_stats['total_mirrored']}회
- 성공: {self.daily_stats['successful_mirrors']}회
- 실패: {self.daily_stats['failed_mirrors']}회
- 성공률: {success_rate:.1f}%

🎯 완벽한 TP/SL 미러링 성과:
- 완벽한 미러링: {perfect_mirrors}회 ✨
- 부분 미러링: {partial_mirrors}회
- TP/SL 성공: {tp_sl_success}회 🎯
- TP/SL 실패: {tp_sl_failed}회 ❌
- 완벽 성공률: {(perfect_mirrors / max(perfect_mirrors + partial_mirrors, 1) * 100):.1f}%

🔄 예약 주문 미러링:
- 시작 시 복제: {self.daily_stats['startup_plan_mirrors']}회
- 신규 미러링: {self.daily_stats['plan_order_mirrors']}회
- 취소 동기화: {self.daily_stats['plan_order_cancels']}회
- 클로즈 주문: {self.daily_stats['close_order_mirrors']}회
- 중복 방지: {self.daily_stats['duplicate_orders_prevented']}회

📈 동기화 성과:
- 자동 동기화 수정: {self.daily_stats.get('sync_corrections', 0)}회
- 고아 주문 삭제: {self.daily_stats.get('sync_deletions', 0)}회
- 자동 클로즈 주문 정리: {self.daily_stats.get('auto_close_order_cleanups', 0)}회
- 포지션 종료 정리: {self.daily_stats.get('position_closed_cleanups', 0)}회

📉 포지션 관리:
- 부분 청산: {self.daily_stats['partial_closes']}회
- 전체 청산: {self.daily_stats['full_closes']}회
- 총 거래량: ${self.daily_stats['total_volume']:,.2f}

🔄 현재 미러링 상태:
- 활성 포지션: {len(self.mirrored_positions)}개
- 예약 주문: {len(self.position_manager.mirrored_plan_orders)}개
- 완벽한 TP/SL 주문: {len([o for o in self.position_manager.mirrored_plan_orders.values() if o.get('perfect_mirror')])}개
- 실패 기록: {len(self.failed_mirrors)}건

🔥 슬리피지 보호 개선:
- 임계값: 0.05% (약 $50)
- 지정가 대기: 5초
- 시장가 전환: 자동
- 텔레그램 알림: 즉시
- 안전 장치: 지정가 주문 폴백 지원

🎯 예약 주문 체결/취소 구분:
- 체결 처리: {self.daily_stats.get('plan_order_executions', 0)}회
- 잘못된 취소 방지: {self.daily_stats.get('false_cancellation_prevented', 0)}회
- 모니터링 사이클: {self.daily_stats.get('monitoring_cycles', 0)}회

━━━━━━━━━━━━━━━━━━━
✅ 미러 트레이딩 시스템 정상 작동 중"""
            
            if self.daily_stats.get('errors'):
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
            'startup_plan_mirrors': 0,
            'close_order_mirrors': 0,
            'close_order_skipped': 0,
            'duplicate_orders_prevented': 0,
            'perfect_mirrors': 0,
            'partial_mirrors': 0,
            'tp_sl_success': 0,
            'tp_sl_failed': 0,
            'sync_corrections': 0,
            'sync_deletions': 0,
            'auto_close_order_cleanups': 0,
            'position_closed_cleanups': 0,
            'position_size_corrections': 0,
            'plan_order_executions': 0,
            'false_cancellation_prevented': 0,
            'monitoring_cycles': 0,
            'monitoring_errors': 0,
            'errors': []
        }
        self.failed_mirrors.clear()
        
        # 시세 조회 실패 카운터 리셋
        self.bitget_price_failures = 0
        self.gate_price_failures = 0

    async def _log_account_status(self):
        """계정 상태 로그"""
        try:
            # 기본 클라이언트로 계정 상태 조회
            bitget_account = await self.bitget.get_account_info()
            gate_account = await self.gate_mirror.get_account_balance()
            
            self.logger.info(f"💰 비트겟 계정: ${float(bitget_account.get('accountEquity', 0)):,.2f}")
            self.logger.info(f"💰 게이트 계정: ${float(gate_account.get('total', 0)):,.2f}")
            
        except Exception as e:
            self.logger.error(f"계정 상태 조회 실패: {e}")

    def stop(self):
        """미러 트레이딩 중지"""
        self.logger.info("미러 트레이딩 시스템 중지 요청")
        self.monitoring = False
        self.position_manager.monitoring = False
