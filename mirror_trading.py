import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
import traceback
from collections import defaultdict

from bitget_mirror_client import BitgetMirrorClient
from gate_mirror_client import GateMirrorClient  
from mirror_position_manager import MirrorPositionManager
from mirror_trading_utils import MirrorTradingUtils
from telegram_bot import TelegramBot

logger = logging.getLogger(__name__)

class MirrorTradingSystem:
    """🔥🔥🔥 미러 트레이딩 시스템 - 게이트 예약주문 자동취소 방지 강화"""
    
    def __init__(self, config, bitget_client, gate_client, telegram_bot):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.telegram = telegram_bot
        self.logger = logging.getLogger('mirror_trading')
        
        # 미러링 클라이언트 초기화
        self.bitget_mirror = BitgetMirrorClient(config, bitget_client)
        self.gate_mirror = GateMirrorClient(config, gate_client)
        
        # 포지션 매니저 초기화
        self.position_manager = MirrorPositionManager(
            config, 
            self.bitget_mirror, 
            self.gate_mirror,
            telegram_bot
        )
        
        # 유틸리티 초기화
        self.trading_utils = MirrorTradingUtils(config, bitget_client, gate_client)
        
        # 시세 관리
        self.bitget_current_price = 0.0
        self.gate_current_price = 0.0
        self.last_price_update = datetime.now()
        
        # 🔥🔥🔥 게이트 예약주문 자동취소 방지 강화
        self.price_sync_threshold = 1000.0  # 시세 차이 허용 임계값 대폭 상향
        self.position_wait_timeout = 300  # 포지션 대기 시간 연장
        
        # 🔥🔥🔥 비트겟 예약주문 상태 추적 강화
        self.last_known_bitget_orders = {}  # 마지막으로 확인된 비트겟 예약주문 상태
        self.bitget_order_check_interval = 30  # 🔥 10초 → 30초로 늘려서 과도한 체크 방지
        self.last_bitget_order_check = datetime.now()
        
        # 🔥🔥🔥 게이트 예약주문 보호 로직 강화
        self.protected_gate_orders = set()  # 보호된 게이트 예약주문 ID
        self.order_protection_duration = 600  # 🔥 5분 → 10분으로 연장
        self.order_protection_timestamps = {}  # 예약주문별 보호 시작 시간
        
        # 🔥🔥🔥 게이트 예약주문 취소 방지 추가 보호
        self.gate_order_cancel_protection = True  # 게이트 주문 취소 보호 활성화
        self.require_bitget_cancel_confirmation = True  # 비트겟 취소 확인 필수
        self.cancel_verification_timeout = 60  # 취소 확인 대기 시간 (초)
        
        # 시스템 상태
        self.startup_positions = {}
        self.failed_mirrors = []
        self.bitget_price_failures = 0
        self.gate_price_failures = 0
        
        # 시스템 설정
        self.MONITOR_INTERVAL = 15
        self.MAX_RETRIES = 3
        self.MIN_POSITION_SIZE = 0.00001
        self.MIN_MARGIN = 1.0
        self.DAILY_REPORT_HOUR = 9
        
        # 성과 추적 (포지션 매니저와 공유)
        self.daily_stats = self.position_manager.daily_stats
        
        self.monitoring = True
        self.logger.info("🔥 미러 트레이딩 시스템 초기화 완료 - 게이트 예약주문 자동취소 방지 강화")

    async def start(self):
        """미러 트레이딩 시작"""
        try:
            self.logger.info("🔥 미러 트레이딩 시스템 시작 - 게이트 예약주문 자동취소 방지 강화")
            
            # Bitget 미러링 클라이언트 초기화
            await self.bitget_mirror.initialize()
            
            # Gate.io 미러링 클라이언트 초기화
            await self.gate_mirror.initialize()
            
            # 현재 시세 업데이트
            await self._update_current_prices()
            
            # 포지션 매니저 초기화
            self.position_manager.price_sync_threshold = self.price_sync_threshold
            self.position_manager.position_wait_timeout = self.position_wait_timeout
            await self.position_manager.initialize()
            
            # 🔥🔥🔥 기존 비트겟 예약주문 상태 저장
            await self._initialize_bitget_order_tracking()
            
            # 초기 계정 상태 출력
            await self._log_account_status()
            
            # 모니터링 태스크 시작
            tasks = [
                self.monitor_plan_orders(),
                self.monitor_order_fills(), 
                self.monitor_positions(),
                self.monitor_sync_status(),
                self.monitor_price_differences(),
                self.monitor_order_synchronization(),
                self.monitor_bitget_order_status_safe(),  # 🔥🔥🔥 안전한 모니터링으로 변경
                self.generate_daily_reports()
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시스템 시작 실패: {e}")
            await self.telegram.send_message(f"❌ 미러 트레이딩 시스템 시작 실패\n{str(e)}")
            raise

    # 🔥🔥🔥 강화된 비트겟 예약주문 상태 추적 메서드들
    
    async def _initialize_bitget_order_tracking(self):
        """비트겟 예약주문 상태 추적 초기화"""
        try:
            self.logger.info("🔍 비트겟 예약주문 상태 추적 초기화 시작")
            
            # 현재 비트겟의 모든 예약주문 조회
            bitget_orders = await self.bitget_mirror.get_all_plan_orders_with_tp_sl()
            
            # 예약주문 상태 저장
            self.last_known_bitget_orders = {}
            total_orders = bitget_orders.get('total_count', 0)
            
            # 일반 예약주문 저장
            for order in bitget_orders.get('plan_orders', []):
                order_id = order.get('orderId', order.get('planOrderId'))
                if order_id:
                    self.last_known_bitget_orders[order_id] = {
                        'type': 'plan',
                        'order': order,
                        'timestamp': datetime.now()
                    }
            
            # TP/SL 주문 저장
            for order in bitget_orders.get('tp_sl_orders', []):
                order_id = order.get('orderId', order.get('planOrderId'))
                if order_id:
                    self.last_known_bitget_orders[order_id] = {
                        'type': 'tp_sl',
                        'order': order,
                        'timestamp': datetime.now()
                    }
            
            self.logger.info(f"✅ 비트겟 예약주문 상태 추적 초기화 완료: {len(self.last_known_bitget_orders)}개 주문 추적 시작")
            
        except Exception as e:
            self.logger.error(f"비트겟 예약주문 상태 추적 초기화 실패: {e}")

    async def monitor_bitget_order_status_safe(self):
        """🔥🔥🔥 안전한 비트겟 예약주문 상태 모니터링 - 게이트 예약주문 보호"""
        while self.monitoring:
            try:
                now = datetime.now()
                
                # 지정된 간격마다 체크 (더 긴 간격으로 변경)
                if (now - self.last_bitget_order_check).total_seconds() >= self.bitget_order_check_interval:
                    await self._check_bitget_order_changes_safe()
                    self.last_bitget_order_check = now
                
                # 보호 시간 만료된 예약주문 정리
                await self._cleanup_expired_order_protection()
                
                await asyncio.sleep(10)  # 10초마다 체크
                
            except Exception as e:
                self.logger.error(f"비트겟 예약주문 상태 모니터링 오류: {e}")
                await asyncio.sleep(30)

    async def _check_bitget_order_changes_safe(self):
        """🔥🔥🔥 안전한 비트겟 예약주문 변경 사항 체크 - 게이트 주문 보호"""
        try:
            # 현재 비트겟 예약주문 조회
            current_orders = await self.bitget_mirror.get_all_plan_orders_with_tp_sl()
            current_order_ids = set()
            
            # 현재 주문 ID 수집
            for order in current_orders.get('plan_orders', []) + current_orders.get('tp_sl_orders', []):
                order_id = order.get('orderId', order.get('planOrderId'))
                if order_id:
                    current_order_ids.add(order_id)
            
            # 🔥🔥🔥 사라진 비트겟 주문 감지 - 매우 신중하게 처리
            disappeared_orders = set(self.last_known_bitget_orders.keys()) - current_order_ids
            
            for disappeared_order_id in disappeared_orders:
                await self._handle_disappeared_bitget_order_safe(disappeared_order_id)
            
            # 🔥🔥🔥 새로운 비트겟 주문 감지 - 미러링 필요
            new_orders = current_order_ids - set(self.last_known_bitget_orders.keys())
            
            for new_order_id in new_orders:
                # 새 주문 찾기
                new_order = None
                for order in current_orders.get('plan_orders', []) + current_orders.get('tp_sl_orders', []):
                    if order.get('orderId', order.get('planOrderId')) == new_order_id:
                        new_order = order
                        break
                
                if new_order:
                    await self._handle_new_bitget_order(new_order_id, new_order)
            
            # 상태 업데이트
            self.last_known_bitget_orders = {}
            for order in current_orders.get('plan_orders', []) + current_orders.get('tp_sl_orders', []):
                order_id = order.get('orderId', order.get('planOrderId'))
                if order_id:
                    self.last_known_bitget_orders[order_id] = {
                        'type': 'plan' if order in current_orders.get('plan_orders', []) else 'tp_sl',
                        'order': order,
                        'timestamp': datetime.now()
                    }
            
        except Exception as e:
            self.logger.error(f"비트겟 예약주문 변경 사항 체크 실패: {e}")

    async def _handle_disappeared_bitget_order_safe(self, order_id: str):
        """🔥🔥🔥 사라진 비트겟 주문 안전 처리 - 게이트 주문 보호 강화"""
        try:
            # 🔥🔥🔥 게이트 주문 취소 보호가 활성화된 경우 처리 안함
            if self.gate_order_cancel_protection:
                self.logger.info(f"🛡️ 게이트 주문 취소 보호 활성화로 처리 생략: {order_id}")
                return
            
            # 연결된 게이트 주문 ID 찾기
            gate_order_id = self.position_manager.bitget_to_gate_order_mapping.get(order_id)
            if not gate_order_id:
                self.logger.debug(f"연결된 게이트 주문이 없음: {order_id}")
                return
            
            # 🔥🔥🔥 비트겟 주문이 정말 취소되었는지 이중 확인
            if self.require_bitget_cancel_confirmation:
                is_really_cancelled = await self._verify_bitget_order_cancellation(order_id)
                if not is_really_cancelled:
                    self.logger.info(f"🔍 비트겟 주문 취소 확인 실패, 게이트 주문 보존: {order_id}")
                    # 🔥🔥🔥 의심스러운 경우 게이트 주문 보호
                    self._protect_gate_order(gate_order_id)
                    return
            
            # 🔥🔥🔥 게이트 주문이 보호 중이면 처리하지 않음
            if self._is_gate_order_protected(gate_order_id):
                self.logger.info(f"🛡️ 보호 중인 게이트 주문, 취소 생략: {gate_order_id}")
                return
            
            # 🔥🔥🔥 추가 안전 장치: 잠시 대기 후 다시 확인
            await asyncio.sleep(5)
            
            # 비트겟 주문이 정말 사라졌는지 재확인
            recheck_orders = await self.bitget_mirror.get_all_plan_orders_with_tp_sl()
            all_current_ids = set()
            for order in recheck_orders.get('plan_orders', []) + recheck_orders.get('tp_sl_orders', []):
                current_id = order.get('orderId', order.get('planOrderId'))
                if current_id:
                    all_current_ids.add(current_id)
            
            if order_id in all_current_ids:
                self.logger.info(f"🔍 재확인 결과 비트겟 주문 여전히 존재, 게이트 주문 보존: {order_id}")
                return
            
            # 모든 검증을 통과한 경우에만 게이트 주문 취소
            self.logger.info(f"🔥 비트겟 주문 취소 확인됨, 연결된 게이트 주문 취소: {order_id} → {gate_order_id}")
            
            try:
                await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                
                # 매핑에서 제거
                if order_id in self.position_manager.bitget_to_gate_order_mapping:
                    del self.position_manager.bitget_to_gate_order_mapping[order_id]
                if gate_order_id in self.position_manager.gate_to_bitget_order_mapping:
                    del self.position_manager.gate_to_bitget_order_mapping[gate_order_id]
                if order_id in self.position_manager.mirrored_plan_orders:
                    del self.position_manager.mirrored_plan_orders[order_id]
                
                self.daily_stats['plan_order_cancels'] += 1
                self.logger.info(f"✅ 게이트 주문 취소 완료: {gate_order_id}")
                
            except Exception as e:
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in [
                    "not found", "order not exist", "invalid order", "already cancelled"
                ]):
                    self.logger.info(f"게이트 주문이 이미 처리됨: {gate_order_id}")
                else:
                    self.logger.error(f"게이트 주문 취소 실패: {gate_order_id} - {e}")
                    # 실패한 경우 보호 설정
                    self._protect_gate_order(gate_order_id)
            
        except Exception as e:
            self.logger.error(f"사라진 비트겟 주문 처리 실패: {order_id} - {e}")

    async def _verify_bitget_order_cancellation(self, order_id: str) -> bool:
        """🔥🔥🔥 비트겟 주문 취소 검증"""
        try:
            # 여러 방법으로 주문 상태 확인
            await asyncio.sleep(3)  # 잠시 대기
            
            # 1. 모든 예약주문에서 재검색
            orders = await self.bitget_mirror.get_all_plan_orders_with_tp_sl()
            all_orders = orders.get('plan_orders', []) + orders.get('tp_sl_orders', [])
            
            for order in all_orders:
                current_id = order.get('orderId', order.get('planOrderId'))
                if current_id == order_id:
                    self.logger.info(f"🔍 비트겟 주문 여전히 존재: {order_id}")
                    return False
            
            # 2. 취소된 주문 내역에서 확인 (가능한 경우)
            try:
                cancelled_orders = await self.bitget_mirror.get_recently_cancelled_orders(minutes=10)
                for cancelled in cancelled_orders:
                    if cancelled.get('orderId', cancelled.get('planOrderId')) == order_id:
                        self.logger.info(f"✅ 비트겟 주문 취소 확인됨: {order_id}")
                        return True
            except:
                pass  # 취소 내역 조회 실패는 무시
            
            # 3. 주문이 없으면 취소된 것으로 간주
            self.logger.info(f"🔍 비트겟 주문 조회되지 않음, 취소된 것으로 판단: {order_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"비트겟 주문 취소 검증 실패: {order_id} - {e}")
            return False  # 검증 실패 시 안전하게 취소 안됨으로 처리

    async def _handle_new_bitget_order(self, order_id: str, order: Dict):
        """새로운 비트겟 주문 처리"""
        try:
            self.logger.info(f"🆕 새로운 비트겟 주문 감지: {order_id}")
            
            # 이미 미러링된 주문인지 확인
            if order_id in self.position_manager.mirrored_plan_orders:
                self.logger.debug(f"이미 미러링된 주문: {order_id}")
                return
            
            # 새 주문 미러링
            await self.position_manager.mirror_plan_order(order)
            
        except Exception as e:
            self.logger.error(f"새로운 비트겟 주문 처리 실패: {order_id} - {e}")

    def _protect_gate_order(self, gate_order_id: str):
        """🔥🔥🔥 게이트 주문 보호"""
        self.protected_gate_orders.add(gate_order_id)
        self.order_protection_timestamps[gate_order_id] = datetime.now()
        self.logger.info(f"🛡️ 게이트 주문 보호 설정: {gate_order_id}")

    def _is_gate_order_protected(self, gate_order_id: str) -> bool:
        """🔥🔥🔥 게이트 주문 보호 상태 확인"""
        if gate_order_id not in self.protected_gate_orders:
            return False
        
        # 보호 시간 만료 확인
        protection_start = self.order_protection_timestamps.get(gate_order_id)
        if protection_start:
            elapsed = (datetime.now() - protection_start).total_seconds()
            if elapsed > self.order_protection_duration:
                self.protected_gate_orders.discard(gate_order_id)
                self.order_protection_timestamps.pop(gate_order_id, None)
                self.logger.info(f"🛡️ 게이트 주문 보호 시간 만료: {gate_order_id}")
                return False
        
        return True

    async def _cleanup_expired_order_protection(self):
        """만료된 주문 보호 정리"""
        try:
            now = datetime.now()
            expired_orders = []
            
            for gate_order_id, start_time in self.order_protection_timestamps.items():
                if (now - start_time).total_seconds() > self.order_protection_duration:
                    expired_orders.append(gate_order_id)
            
            for gate_order_id in expired_orders:
                self.protected_gate_orders.discard(gate_order_id)
                self.order_protection_timestamps.pop(gate_order_id, None)
                self.logger.debug(f"🛡️ 만료된 보호 제거: {gate_order_id}")
            
        except Exception as e:
            self.logger.error(f"만료된 주문 보호 정리 실패: {e}")

    async def monitor_plan_orders(self):
        """예약 주문 모니터링"""
        while self.monitoring:
            try:
                await self._monitor_plan_orders_safe()
                await asyncio.sleep(self.MONITOR_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"예약 주문 모니터링 오류: {e}")
                await asyncio.sleep(30)

    async def _monitor_plan_orders_safe(self):
        """안전한 예약 주문 모니터링"""
        try:
            # 비트겟 예약 주문 조회
            bitget_plan_orders = await self.bitget_mirror.get_all_plan_orders_with_tp_sl()
            
            if not bitget_plan_orders or bitget_plan_orders.get('total_count', 0) == 0:
                return
            
            plan_orders = bitget_plan_orders.get('plan_orders', [])
            tp_sl_orders = bitget_plan_orders.get('tp_sl_orders', [])
            all_orders = plan_orders + tp_sl_orders
            
            # 🔥🔥🔥 각 예약 주문을 안전하게 처리
            for order in all_orders:
                try:
                    await self._process_single_plan_order_safe(order)
                except Exception as e:
                    order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
                    self.logger.error(f"예약 주문 처리 실패: {order_id} - {e}")
            
        except Exception as e:
            self.logger.error(f"예약 주문 모니터링 실패: {e}")

    async def _process_single_plan_order_safe(self, order: Dict):
        """단일 예약 주문 안전 처리 - 🔥🔥🔥 과도한 취소 방지"""
        try:
            order_id = order.get('orderId', order.get('planOrderId'))
            if not order_id:
                return
            
            # 이미 미러링된 주문인지 확인
            if order_id in self.position_manager.mirrored_plan_orders:
                # 🔥🔥🔥 기존 미러링된 주문은 상태만 확인하고 건드리지 않음
                await self._verify_existing_mirror_order_safe(order_id, order)
                return
            
            # 새로운 예약 주문 미러링 처리
            side = order.get('side', order.get('tradeSide', ''))
            size = float(order.get('size', order.get('sz', 0)))
            trigger_price = float(order.get('triggerPrice', order.get('executePrice', 0)))
            
            if size <= 0 or trigger_price <= 0:
                return
            
            # 포지션 존재 여부 확인 (TP/SL 주문용)
            is_tp_sl_order = self._is_tp_sl_order(order)
            
            if is_tp_sl_order:
                # TP/SL 주문은 포지션이 있을 때만 미러링
                has_position = await self._check_positions_exist()
                if not has_position:
                    self.logger.debug(f"포지션 없음으로 TP/SL 주문 미러링 대기: {order_id}")
                    return
            
            # 새로운 예약 주문 미러링 실행
            await self.position_manager.mirror_plan_order(order)
            
        except Exception as e:
            self.logger.error(f"예약 주문 안전 처리 실패: {e}")

    async def _verify_existing_mirror_order_safe(self, order_id: str, bitget_order: Dict):
        """🔥🔥🔥 기존 미러링된 주문 안전 검증 - 불필요한 취소 방지"""
        try:
            # 연결된 게이트 주문 ID 찾기
            gate_order_id = self.position_manager.bitget_to_gate_order_mapping.get(order_id)
            if not gate_order_id:
                return
            
            # 🔥🔥🔥 게이트 주문이 보호 중이면 건드리지 않음
            if self._is_gate_order_protected(gate_order_id):
                self.logger.debug(f"보호 중인 게이트 주문, 검증 생략: {gate_order_id}")
                return
            
            # 🔥🔥🔥 게이트 주문 존재 여부만 확인 (취소하지 않음)
            gate_orders = await self.gate_mirror.get_all_price_triggered_orders()
            gate_order_exists = any(
                order.get('id') == gate_order_id 
                for order in gate_orders
            )
            
            if not gate_order_exists:
                self.logger.warning(f"연결된 게이트 주문이 사라짐: {gate_order_id}, 비트겟 주문: {order_id}")
                
                # 🔥🔥🔥 게이트 주문이 사라진 경우에만 미러링 기록 정리
                if order_id in self.position_manager.mirrored_plan_orders:
                    del self.position_manager.mirrored_plan_orders[order_id]
                if order_id in self.position_manager.bitget_to_gate_order_mapping:
                    del self.position_manager.bitget_to_gate_order_mapping[order_id]
                if gate_order_id in self.position_manager.gate_to_bitget_order_mapping:
                    del self.position_manager.gate_to_bitget_order_mapping[gate_order_id]
                
                # 비트겟 주문이 여전히 존재하면 다시 미러링
                await self.position_manager.mirror_plan_order(bitget_order)
            
        except Exception as e:
            self.logger.error(f"기존 미러 주문 검증 실패: {order_id} - {e}")

    def _is_tp_sl_order(self, order: Dict) -> bool:
        """TP/SL 주문 여부 판단"""
        return (
            order.get('planType') == 'profit_loss' or
            order.get('isPlan') == 'profit_loss' or
            order.get('side') in ['close_long', 'close_short'] or
            order.get('tradeSide') in ['close_long', 'close_short'] or
            order.get('reduceOnly') == True or
            order.get('reduceOnly') == 'true'
        )

    async def monitor_order_fills(self):
        """주문 체결 모니터링"""
        while self.monitoring:
            try:
                # 최근 5분간 체결된 주문 조회
                recent_orders = await self.bitget_mirror.get_recent_filled_orders(minutes=5)
                
                for order in recent_orders:
                    # 신규 진입 주문만 처리 (reduceOnly가 아닌 것)
                    reduce_only = order.get('reduceOnly', 'false')
                    if reduce_only == 'false' or reduce_only is False:
                        await self.position_manager.handle_order_fill(order)
                
                await asyncio.sleep(self.MONITOR_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"주문 체결 모니터링 오류: {e}")
                await asyncio.sleep(30)

    async def monitor_positions(self):
        """포지션 모니터링"""
        while self.monitoring:
            try:
                # 포지션 변화 감지 및 처리
                await self.position_manager.monitor_position_changes()
                await asyncio.sleep(self.MONITOR_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"포지션 모니터링 오류: {e}")
                await asyncio.sleep(30)

    async def monitor_sync_status(self):
        """동기화 상태 모니터링 - 🔥🔥🔥 개선된 보호 로직"""
        while self.monitoring:
            try:
                await self._perform_safe_sync_check()
                await asyncio.sleep(60)  # 🔥 30초 → 60초로 늘려서 과도한 체크 방지
                
            except Exception as e:
                self.logger.error(f"동기화 상태 모니터링 오류: {e}")
                await asyncio.sleep(120)

    async def _perform_safe_sync_check(self):
        """안전한 동기화 체크 - 🔥🔥🔥 과도한 정리 방지"""
        try:
            # 🔥🔥🔥 게이트 주문 취소 보호가 활성화된 경우 동기화 체크 생략
            if self.gate_order_cancel_protection:
                self.logger.debug("게이트 주문 취소 보호 활성화로 동기화 체크 생략")
                return
            
            # 동기화 상태 분석
            sync_analysis = await self.position_manager.analyze_order_sync_status()
            
            if not sync_analysis:
                return
            
            missing_count = len(sync_analysis.get('missing_mirrors', []))
            orphaned_count = len(sync_analysis.get('orphaned_orders', []))
            
            if missing_count > 0:
                self.logger.info(f"🔍 미러링 누락 감지: {missing_count}개")
                # 누락된 미러링 처리 (최대 3개씩만)
                for missing in sync_analysis['missing_mirrors'][:3]:  # 🔥 5개 → 3개로 줄임
                    try:
                        bitget_order = missing.get('bitget_order')
                        if bitget_order:
                            await self.position_manager.mirror_plan_order(bitget_order)
                    except Exception as e:
                        self.logger.error(f"누락 미러링 처리 실패: {e}")
            
            # 🔥🔥🔥 고아 주문 처리 - 매우 신중하게 (더 줄임)
            if orphaned_count > 0:
                self.logger.info(f"🔍 고아 주문 감지: {orphaned_count}개")
                await self._handle_orphaned_orders_safely(sync_analysis.get('orphaned_orders', []))
            
        except Exception as e:
            self.logger.error(f"안전한 동기화 체크 실패: {e}")

    async def _handle_orphaned_orders_safely(self, orphaned_orders: List[Dict]):
        """🔥🔥🔥 고아 주문 안전 처리 - 신중한 검증 강화"""
        try:
            # 🔥🔥🔥 게이트 주문 취소 보호가 활성화된 경우 처리 안함
            if self.gate_order_cancel_protection:
                self.logger.info("🛡️ 게이트 주문 취소 보호 활성화로 고아 주문 정리 생략")
                return
            
            for orphaned in orphaned_orders[:1]:  # 🔥 3개 → 1개로 줄여서 매우 신중하게
                try:
                    gate_order_id = orphaned.get('gate_order_id')
                    if not gate_order_id:
                        continue
                    
                    # 🔥🔥🔥 보호 중인 주문은 건드리지 않음
                    if self._is_gate_order_protected(gate_order_id):
                        self.logger.info(f"보호 중인 게이트 주문, 고아 정리 생략: {gate_order_id}")
                        continue
                    
                    # 🔥🔥🔥 삼중 검증: 비트겟에서 연결된 주문이 정말 없는지 확인
                    verified_orphan = await self._verify_orphaned_order_thoroughly(gate_order_id, orphaned)
                    
                    if verified_orphan:
                        self.logger.info(f"🗑️ 삼중 검증된 고아 주문 정리: {gate_order_id}")
                        await self.gate_mirror.cancel_price_triggered_order(gate_order_id)
                        
                        # 매핑에서 제거
                        if gate_order_id in self.position_manager.gate_to_bitget_order_mapping:
                            bitget_id = self.position_manager.gate_to_bitget_order_mapping[gate_order_id]
                            del self.position_manager.gate_to_bitget_order_mapping[gate_order_id]
                            if bitget_id in self.position_manager.bitget_to_gate_order_mapping:
                                del self.position_manager.bitget_to_gate_order_mapping[bitget_id]
                        
                        self.daily_stats['sync_deletions'] += 1
                    else:
                        self.logger.info(f"고아 주문 검증 실패, 보존 및 보호 설정: {gate_order_id}")
                        # 🔥🔥🔥 의심스러운 경우 보호 설정
                        self._protect_gate_order(gate_order_id)
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in [
                        "not found", "order not exist", "invalid order"
                    ]):
                        self.logger.info(f"고아 주문이 이미 처리됨: {gate_order_id}")
                    else:
                        self.logger.error(f"고아 주문 처리 실패: {gate_order_id} - {e}")
                    
        except Exception as e:
            self.logger.error(f"고아 주문 안전 처리 실패: {e}")

    async def _verify_orphaned_order_thoroughly(self, gate_order_id: str, orphaned_info: Dict) -> bool:
        """🔥🔥🔥 고아 주문 삼중 검증 - 매우 신중한 검증"""
        try:
            # 1차 검증: 게이트 주문 정보 재조회
            gate_orders = await self.gate_mirror.get_all_price_triggered_orders()
            gate_order = next((o for o in gate_orders if o.get('id') == gate_order_id), None)
            
            if not gate_order:
                self.logger.info(f"1차 검증: 게이트 주문이 이미 없음: {gate_order_id}")
                return False
            
            # 2차 검증: 비트겟에서 유사한 주문 검색 (더 관대한 기준)
            bitget_orders = await self.bitget_mirror.get_all_plan_orders_with_tp_sl()
            all_bitget_orders = bitget_orders.get('plan_orders', []) + bitget_orders.get('tp_sl_orders', [])
            
            gate_side = gate_order.get('side', '')
            gate_price = float(gate_order.get('price', 0))
            gate_size = float(gate_order.get('size', 0))
            
            # 유사한 비트겟 주문이 있는지 검색 (매우 관대한 기준)
            for bitget_order in all_bitget_orders:
                bitget_side = bitget_order.get('side', bitget_order.get('tradeSide', ''))
                bitget_price = float(bitget_order.get('triggerPrice', bitget_order.get('executePrice', 0)))
                bitget_size = float(bitget_order.get('size', bitget_order.get('sz', 0)))
                
                # 방향, 가격, 크기가 유사하면 고아가 아닐 수 있음
                if (bitget_side == gate_side and 
                    gate_price > 0 and bitget_price > 0 and
                    abs(bitget_price - gate_price) / gate_price < 0.05 and  # 🔥 1% → 5%로 더 관대하게
                    gate_size > 0 and bitget_size > 0 and
                    abs(bitget_size - gate_size) / gate_size < 0.2):  # 🔥 10% → 20%로 더 관대하게
                    
                    self.logger.info(f"2차 검증: 유사한 비트겟 주문 발견, 고아 아님: {gate_order_id}")
                    return False
            
            # 3차 검증: 추가 대기 후 재확인
            await asyncio.sleep(10)  # 10초 더 대기
            
            # 비트겟 주문 재조회
            recheck_orders = await self.bitget_mirror.get_all_plan_orders_with_tp_sl()
            recheck_all = recheck_orders.get('plan_orders', []) + recheck_orders.get('tp_sl_orders', [])
            
            # 다시 한 번 유사한 주문 검색
            for bitget_order in recheck_all:
                bitget_side = bitget_order.get('side', bitget_order.get('tradeSide', ''))
                bitget_price = float(bitget_order.get('triggerPrice', bitget_order.get('executePrice', 0)))
                bitget_size = float(bitget_order.get('size', bitget_order.get('sz', 0)))
                
                if (bitget_side == gate_side and 
                    gate_price > 0 and bitget_price > 0 and
                    abs(bitget_price - gate_price) / gate_price < 0.05 and
                    gate_size > 0 and bitget_size > 0 and
                    abs(bitget_size - gate_size) / gate_size < 0.2):
                    
                    self.logger.info(f"3차 검증: 재확인에서 유사한 비트겟 주문 발견, 고아 아님: {gate_order_id}")
                    return False
            
            # 모든 검증을 통과한 경우에만 정말 고아로 판단
            self.logger.info(f"삼중 검증 완료: 정말 고아 주문으로 확인됨: {gate_order_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"고아 주문 삼중 검증 실패: {gate_order_id} - {e}")
            return False  # 검증 실패 시 안전하게 보존

    async def monitor_price_differences(self):
        """시세 차이 모니터링"""
        while self.monitoring:
            try:
                await self._update_current_prices()
                
                price_diff = self._get_valid_price_difference()
                if price_diff is not None and price_diff > self.price_sync_threshold:
                    self.logger.warning(f"큰 시세 차이 감지: ${price_diff:.2f}")
                
                await asyncio.sleep(60)  # 1분마다 시세 체크
                
            except Exception as e:
                self.logger.error(f"시세 차이 모니터링 오류: {e}")
                await asyncio.sleep(120)

    async def monitor_order_synchronization(self):
        """주문 동기화 모니터링"""
        while self.monitoring:
            try:
                # 포지션이 없는데 클로즈 주문이 있는 경우 정리
                await self.position_manager.cleanup_close_orders_without_position()
                await asyncio.sleep(60)  # 1분마다 체크
                
            except Exception as e:
                self.logger.error(f"주문 동기화 모니터링 오류: {e}")
                await asyncio.sleep(120)

    async def generate_daily_reports(self):
        """일일 리포트 생성"""
        while self.monitoring:
            try:
                now = datetime.now()
                
                # 매일 오전 9시에 리포트 생성
                if now.hour == self.DAILY_REPORT_HOUR and now.minute < 5:
                    report = await self._create_daily_report()
                    await self.telegram.send_message(report)
                    self._reset_daily_stats()
                    
                    # 다음 리포트까지 대기
                    await asyncio.sleep(3600)  # 1시간 대기
                
                await asyncio.sleep(300)  # 5분마다 체크
                
            except Exception as e:
                self.logger.error(f"일일 리포트 생성 오류: {e}")
                await asyncio.sleep(1800)  # 30분 대기 후 재시도

    async def _update_current_prices(self):
        """현재 시세 업데이트"""
        try:
            # 병렬로 시세 조회
            bitget_task = self.bitget.get_current_price(self.config.symbol)
            gate_task = self.gate.get_current_price('BTC_USDT')
            
            results = await asyncio.gather(bitget_task, gate_task, return_exceptions=True)
            
            # Bitget 시세 처리
            if not isinstance(results[0], Exception) and results[0] > 0:
                self.bitget_current_price = results[0]
                self.bitget_price_failures = 0
            else:
                self.bitget_price_failures += 1
                
            # Gate 시세 처리
            if not isinstance(results[1], Exception) and results[1] > 0:
                self.gate_current_price = results[1]
                self.gate_price_failures = 0
            else:
                self.gate_price_failures += 1
            
            self.last_price_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"시세 업데이트 실패: {e}")

    def _get_valid_price_difference(self) -> Optional[float]:
        """유효한 시세 차이 반환"""
        if self.bitget_current_price > 0 and self.gate_current_price > 0:
            return abs(self.bitget_current_price - self.gate_current_price)
        return None

    async def _check_positions_exist(self) -> bool:
        """포지션 존재 여부 확인"""
        try:
            bitget_positions = await self.bitget.get_positions(self.config.symbol)
            gate_positions = await self.gate.get_positions('BTC_USDT')
            
            # 비트겟 포지션 확인
            bitget_has_position = any(
                float(pos.get('total', pos.get('sizeQty', 0))) > 0 
                for pos in bitget_positions
            )
            
            # 게이트 포지션 확인
            gate_has_position = any(
                float(pos.get('size', 0)) != 0 
                for pos in gate_positions
            )
            
            return bitget_has_position or gate_has_position
            
        except Exception as e:
            self.logger.error(f"포지션 존재 여부 확인 실패: {e}")
            return False

    async def health_check(self) -> bool:
        """시스템 상태 확인"""
        try:
            # 기본 연결 상태 확인
            if not self.monitoring:
                return False
            
            # 클라이언트 상태 확인
            bitget_health = await self.bitget_mirror.health_check()
            gate_health = await self.gate_mirror.health_check()
            
            return bitget_health and gate_health
            
        except Exception as e:
            self.logger.error(f"헬스체크 실패: {e}")
            return False

    async def _create_daily_report(self) -> str:
        """일일 리포트 생성"""
        try:
            stats = self.daily_stats
            
            # 성공률 계산
            total_attempts = stats['total_mirrored']
            success_rate = (stats['successful_mirrors'] / total_attempts * 100) if total_attempts > 0 else 0
            
            # 실패 건수
            failed_count = len(self.failed_mirrors)
            
            report = f"""📊 미러 트레이딩 일일 리포트
            
🔄 미러링 성과:
• 총 시도: {stats['total_mirrored']}회
• 성공: {stats['successful_mirrors']}회
• 실패: {stats['failed_mirrors']}회
• 성공률: {success_rate:.1f}%

📋 주문 처리:
• 예약 주문 미러링: {stats['plan_order_mirrors']}회
• 예약 주문 취소: {stats['plan_order_cancels']}회
• 부분 청산: {stats['partial_closes']}회
• 전체 청산: {stats['full_closes']}회

💰 거래량:
• 총 거래량: ${stats['total_volume']:,.2f}

🔧 시스템 상태:
• 보호된 게이트 주문: {len(self.protected_gate_orders)}개
• 시세 차이 허용치: ${self.price_sync_threshold:,.0f}
• 🔥 게이트 주문 취소 보호: {'활성화' if self.gate_order_cancel_protection else '비활성화'}

⚡ 주요 개선사항:
• 🛡️ 게이트 예약주문 10분간 보호
• 🔍 비트겟 취소 삼중 검증
• 🔒 과도한 동기화 방지
• 🎯 안전한 고아 주문 정리"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"일일 리포트 생성 실패: {e}")
            return "일일 리포트 생성 중 오류가 발생했습니다."

    def _reset_daily_stats(self):
        """일일 통계 리셋"""
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
            'errors': []
        }
        self.failed_mirrors.clear()
        
        # 시세 조회 실패 카운터 리셋
        self.bitget_price_failures = 0
        self.gate_price_failures = 0
        
        # 🔥🔥🔥 보호 관련 통계도 리셋하지만 실제 보호는 유지
        # (보호는 시간 기반으로 자동 해제됨)
        
        # 포지션 매니저의 통계도 동기화
        self.position_manager.daily_stats = self.daily_stats

    async def _log_account_status(self):
        """계정 상태 로깅"""
        try:
            # 기본 클라이언트로 계정 조회
            bitget_account = await self.bitget.get_account_info()
            bitget_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            gate_account = await self.gate_mirror.get_account_balance()
            gate_equity = float(gate_account.get('total', 0))
            
            # 시세 차이 정보
            valid_price_diff = self._get_valid_price_difference()
            
            if valid_price_diff is not None:
                price_status = "정상" if valid_price_diff <= self.price_sync_threshold else "범위 초과"
                price_info = f"""📈 시세 상태:
• 비트겟: ${self.bitget_current_price:,.2f}
• 게이트: ${self.gate_current_price:,.2f}
• 차이: ${valid_price_diff:.2f} ({price_status})
• 🔥 처리: 시세 차이와 무관하게 즉시 처리"""
            else:
                price_info = f"""📈 시세 상태:
• 시세 조회 중 문제 발생
• 시스템이 자동으로 복구 중
• 🔥 처리: 시세 조회 실패와 무관하게 정상 처리"""
            
            await self.telegram.send_message(
                f"🔄 미러 트레이딩 시스템 시작 (게이트 예약주문 보호 강화)\n\n"
                f"💰 계정 잔고:\n"
                f"• 비트겟: ${bitget_equity:,.2f}\n"
                f"• 게이트: ${gate_equity:,.2f}\n\n"
                f"{price_info}\n\n"
                f"📊 현재 상태:\n"
                f"• 기존 포지션: {len(self.startup_positions)}개 (복제 제외)\n"
                f"• 기존 예약 주문: {len(self.position_manager.startup_plan_orders)}개\n"
                f"• 현재 복제된 예약 주문: {len(self.position_manager.mirrored_plan_orders)}개\n"
                f"• 추적 중인 비트겟 주문: {len(self.last_known_bitget_orders)}개\n\n"
                f"⚡ 핵심 기능 (🔥 강화됨):\n"
                f"• 🎯 완벽한 TP/SL 미러링\n"
                f"• 🔄 15초마다 자동 동기화\n"
                f"• 🛡️ 중복 복제 방지\n"
                f"• 🗑️ 안전한 고아 주문 정리\n"
                f"• 📊 클로즈 주문 포지션 체크\n"
                f"• 🔥 게이트 예약주문 10분간 보호\n"
                f"• 🔒 비트겟 취소 시에만 게이트 취소\n"
                f"• 🔍 삼중 검증으로 오취소 방지\n"
                f"• 🛡️ 게이트 취소 보호 모드: {'활성화' if self.gate_order_cancel_protection else '비활성화'}\n\n"
                f"🚀 게이트 예약주문 자동취소 방지가 강화된 시스템이 시작되었습니다!"
            )
            
        except Exception as e:
            self.logger.error(f"계정 상태 조회 실패: {e}")

    async def stop(self):
        """미러 트레이딩 중지"""
        self.monitoring = False
        
        try:
            # 포지션 매니저 중지
            await self.position_manager.stop()
            
            # Bitget 미러링 클라이언트 종료
            await self.bitget_mirror.close()
            
            # Gate.io 미러링 클라이언트 종료
            await self.gate_mirror.close()
            
            final_report = await self._create_daily_report()
            await self.telegram.send_message(f"🛑 미러 트레이딩 시스템 종료\n\n{final_report}")
        except:
            pass
        
        self.logger.info("미러 트레이딩 시스템 중지")
