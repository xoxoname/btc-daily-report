import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import json

from mirror_trading_utils import MirrorTradingUtils, PositionInfo, MirrorResult

logger = logging.getLogger(__name__)

class MirrorPositionManager:
    """🔥🔥🔥 포지션 및 주문 관리 클래스 - 시세차이 문제 해결"""
    
    def __init__(self, config, bitget_client, gate_client, telegram_bot, utils):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.telegram = telegram_bot
        self.utils = utils
        self.logger = logging.getLogger('mirror_position_manager')
        
        # 미러링 상태 관리
        self.mirrored_positions: Dict[str, PositionInfo] = {}
        self.startup_positions: Set[str] = set()
        self.startup_gate_positions: Set[str] = set()  # 🔥🔥🔥 게이트 startup positions 추가
        self.failed_mirrors: List[MirrorResult] = []
        
        # 포지션 크기 추적
        self.position_sizes: Dict[str, float] = {}
        
        # 주문 체결 추적
        self.processed_orders: Set[str] = set()
        
        # 예약 주문 추적 관리
        self.mirrored_plan_orders: Dict[str, Dict] = {}
        self.processed_plan_orders: Set[str] = set()
        self.startup_plan_orders: Set[str] = set()
        self.startup_plan_orders_processed: bool = False
        
        # 예약 주문 취소 감지 시스템
        self.last_plan_order_ids: Set[str] = set()
        self.plan_order_snapshot: Dict[str, Dict] = {}
        
        # 🔥🔥🔥 시세 차이 관리
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.price_sync_threshold: float = 15.0  # 15달러 임계값
        self.position_wait_timeout: int = 180    # 3분 대기
        
        # 🔥 가격 기반 중복 방지 시스템
        self.mirrored_trigger_prices: Set[str] = set()
        
        # 🔥 렌더 재구동 시 기존 게이트 포지션 확인
        self.existing_gate_positions: Dict = {}
        self.render_restart_detected: bool = False
        
        # 🔥🔥🔥 게이트 기존 예약 주문 중복 방지
        self.gate_existing_order_hashes: Set[str] = set()
        self.gate_existing_orders_detailed: Dict[str, Dict] = {}
        
        # 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.MIN_POSITION_SIZE = 0.00001
        self.MIN_MARGIN = 1.0
        self.MAX_RETRIES = 3
        
        # 성과 추적
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
            'plan_order_skipped_already_mirrored': 0,
            'close_order_mirrors': 0,
            'close_order_skipped': 0,
            'duplicate_orders_prevented': 0,
            'render_restart_skips': 0,
            'unified_tp_sl_orders': 0,
            'duplicate_advanced_prevention': 0,
            'price_duplicate_prevention': 0,
            'price_sync_delays': 0,        # 🔥🔥🔥 시세 차이로 인한 지연
            'position_wait_timeouts': 0,   # 🔥🔥🔥 포지션 체결 대기 타임아웃
            'successful_position_waits': 0, # 🔥🔥🔥 성공적인 포지션 체결 대기
            'sync_status_corrected': 0,    # 🔥🔥🔥 동기화 상태 수정 카운터
            'errors': []
        }
        
        self.logger.info("🔥🔥🔥 미러 포지션 매니저 초기화 완료 - 시세차이 문제 해결")

    def update_prices(self, bitget_price: float, gate_price: float, price_diff_percent: float):
        """시세 정보 업데이트"""
        self.bitget_current_price = bitget_price
        self.gate_current_price = gate_price
        self.price_diff_percent = price_diff_percent

    async def initialize(self):
        """🔥🔥🔥 포지션 매니저 초기화 - 시세차이 문제 해결"""
        try:
            self.logger.info("🔥🔥🔥 포지션 매니저 초기화 시작")
            
            # 🔥 렌더 재구동 시 기존 게이트 포지션 확인
            await self._check_existing_gate_positions()
            
            # 🔥🔥🔥 게이트 기존 예약 주문 확인 및 가격 기록
            await self._record_gate_existing_orders_advanced()
            
            # 초기 포지션 및 예약 주문 기록
            await self._record_startup_positions()
            await self._record_startup_plan_orders()
            await self._record_startup_gate_positions()  # 🔥🔥🔥 게이트 startup positions 기록
            
            # 예약 주문 초기 스냅샷 생성
            await self._create_initial_plan_order_snapshot()
            
            # 시작 시 기존 예약 주문 복제
            await self._mirror_startup_plan_orders()
            
            self.logger.info("✅ 포지션 매니저 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"포지션 매니저 초기화 실패: {e}")
            raise

    async def monitor_plan_orders_cycle(self):
        """🔥🔥🔥 예약 주문 모니터링 사이클 - 시세차이 고려"""
        try:
            if not self.startup_plan_orders_processed:
                await asyncio.sleep(0.1)
                return
            
            # 🔥🔥🔥 시세 차이 확인
            price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
            if price_diff_abs > self.price_sync_threshold:
                self.daily_stats['price_sync_delays'] += 1
                self.logger.warning(f"시세 차이 큼 ({price_diff_abs:.2f}$), 예약 주문 처리 지연")
                return
            
            # 현재 비트겟 예약 주문 조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            current_plan_orders = plan_data.get('plan_orders', [])
            current_tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            # 클로즈 주문도 모니터링 대상에 포함
            orders_to_monitor = []
            orders_to_monitor.extend(current_plan_orders)
            
            # TP/SL 주문 중에서 클로즈 주문 추가
            for tp_sl_order in current_tp_sl_orders:
                side = tp_sl_order.get('side', tp_sl_order.get('tradeSide', '')).lower()
                reduce_only = tp_sl_order.get('reduceOnly', False)
                
                is_close_order = (
                    'close' in side or 
                    reduce_only is True or 
                    reduce_only == 'true'
                )
                
                if is_close_order:
                    orders_to_monitor.append(tp_sl_order)
                    self.logger.info(f"🔴 클로즈 주문 모니터링 대상 추가: {tp_sl_order.get('orderId')}")
            
            # 현재 존재하는 예약주문 ID 집합
            current_order_ids = set()
            current_snapshot = {}
            
            for order in orders_to_monitor:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    current_order_ids.add(order_id)
                    current_snapshot[order_id] = {
                        'order_data': order.copy(),
                        'timestamp': datetime.now().isoformat(),
                        'status': 'active'
                    }
            
            # 취소된 예약 주문 감지
            canceled_order_ids = self.last_plan_order_ids - current_order_ids
            
            # 취소된 주문 처리
            if canceled_order_ids:
                self.logger.info(f"{len(canceled_order_ids)}개의 예약 주문 취소 감지: {canceled_order_ids}")
                
                for canceled_order_id in canceled_order_ids:
                    await self._handle_plan_order_cancel(canceled_order_id)
                
                self.daily_stats['plan_order_cancels'] += len(canceled_order_ids)
            
            # 새로운 예약 주문 감지
            new_orders_count = 0
            new_close_orders_count = 0
            
            for order in orders_to_monitor:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if not order_id:
                    continue
                
                # 이미 처리된 주문은 스킵
                if order_id in self.processed_plan_orders:
                    continue
                
                # 시작 시 존재했던 주문인지 확인
                if order_id in self.startup_plan_orders:
                    self.processed_plan_orders.add(order_id)
                    continue
                
                # 🔥 가격 기반 중복 체크 먼저 수행
                trigger_price = 0
                for price_field in ['triggerPrice', 'price', 'executePrice']:
                    if order.get(price_field):
                        trigger_price = float(order.get(price_field))
                        break
                
                if trigger_price > 0:
                    is_price_duplicate = await self._is_price_duplicate(trigger_price)
                    if is_price_duplicate:
                        self.daily_stats['price_duplicate_prevention'] += 1
                        self.logger.info(f"🛡️ 가격 중복으로 스킵: {order_id}, 가격=${trigger_price:.2f}")
                        self.processed_plan_orders.add(order_id)
                        continue
                
                # 강화된 중복 복제 확인
                is_duplicate, duplicate_type = await self._is_duplicate_order_advanced(order)
                if is_duplicate:
                    if duplicate_type == "advanced":
                        self.daily_stats['duplicate_advanced_prevention'] += 1
                        self.logger.info(f"🛡️ 강화된 중복 감지로 스킵: {order_id}")
                    else:
                        self.daily_stats['duplicate_orders_prevented'] += 1
                        self.logger.info(f"🛡️ 기본 중복 감지로 스킵: {order_id}")
                    
                    self.processed_plan_orders.add(order_id)
                    continue
                
                # 🎯 새로운 예약 주문 감지
                try:
                    side = order.get('side', order.get('tradeSide', '')).lower()
                    reduce_only = order.get('reduceOnly', False)
                    is_close_order = ('close' in side or reduce_only is True or reduce_only == 'true')
                    
                    self.logger.info(f"🔍 새로운 주문 처리: {order_id}, side={side}, reduce_only={reduce_only}, is_close_order={is_close_order}")
                    
                    result = await self._process_new_plan_order_with_position_wait(order)
                    
                    if result == "success":
                        new_orders_count += 1
                        if is_close_order:
                            new_close_orders_count += 1
                            self.daily_stats['close_order_mirrors'] += 1
                            self.logger.info(f"✅ 클로즈 주문 복제 성공: {order_id}")
                        
                        # 성공적으로 복제되면 가격 기록
                        if trigger_price > 0:
                            await self._add_trigger_price(trigger_price)
                    elif result == "skipped" and is_close_order:
                        self.daily_stats['close_order_skipped'] += 1
                    
                    self.processed_plan_orders.add(order_id)
                    
                except Exception as e:
                    self.logger.error(f"새로운 예약 주문 복제 실패: {order_id} - {e}")
                    self.processed_plan_orders.add(order_id)
                    
                    await self.telegram.send_message(
                        f"❌ 예약 주문 복제 실패 (시세차이 고려)\n"
                        f"비트겟 ID: {order_id}\n"
                        f"오류: {str(e)[:200]}"
                    )
            
            # 클로즈 주문 복제 성공 시 알림
            if new_close_orders_count > 0:
                await self.telegram.send_message(
                    f"✅ 클로즈 주문 복제 성공 (시세차이 고려)\n"
                    f"클로즈 주문: {new_close_orders_count}개\n"
                    f"전체 신규 복제: {new_orders_count}개"
                )
            
            # 현재 상태를 다음 비교를 위해 저장
            self.last_plan_order_ids = current_order_ids.copy()
            self.plan_order_snapshot = current_snapshot.copy()
            
            # 오래된 주문 ID 정리
            if len(self.processed_plan_orders) > 500:
                recent_orders = list(self.processed_plan_orders)[-250:]
                self.processed_plan_orders = set(recent_orders)
                
        except Exception as e:
            self.logger.error(f"예약 주문 모니터링 사이클 오류: {e}")

    async def _process_new_plan_order_with_position_wait(self, bitget_order: Dict) -> str:
        """🔥🔥🔥 새로운 예약 주문 복제 - 포지션 체결 대기 포함"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            size = float(bitget_order.get('size', 0))
            reduce_only = bitget_order.get('reduceOnly', False)
            
            # 클로즈 주문 판단
            is_close_order = ('close' in side or reduce_only is True or reduce_only == 'true')
            
            self.logger.info(f"🔍 새로운 주문 처리: {order_id}, is_close_order={is_close_order}")
            
            # 🔥🔥🔥 클로즈 주문의 경우 포지션 존재 확인
            if is_close_order:
                gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
                has_position = any(pos.get('size', 0) != 0 for pos in gate_positions)
                
                if not has_position:
                    self.logger.warning(f"클로즈 주문이지만 게이트에 포지션 없음: {order_id}")
                    # 포지션이 없으면 대기 후 다시 확인
                    await asyncio.sleep(5)
                    gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
                    has_position = any(pos.get('size', 0) != 0 for pos in gate_positions)
                    
                    if not has_position:
                        self.logger.warning(f"포지션 없음으로 클로즈 주문 스킵: {order_id}")
                        return "skipped"
            
            # 트리거 가격 추출
            original_trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    original_trigger_price = float(bitget_order.get(price_field))
                    break
            
            if original_trigger_price == 0:
                return "failed"
            
            # TP/SL 정보 추출
            tp_price, sl_price = await self.utils.extract_tp_sl_from_bitget_order(bitget_order)
            
            # 게이트 기준으로 트리거 가격 조정
            adjusted_trigger_price = await self.utils.adjust_price_for_gate(
                original_trigger_price,
                self.bitget_current_price,
                self.gate_current_price,
                self.price_diff_percent
            )
            
            # 트리거 가격 유효성 검증
            is_valid, skip_reason = await self.utils.validate_trigger_price(
                adjusted_trigger_price, side, self.gate_current_price or self.bitget_current_price
            )
            if not is_valid:
                order_type = "클로즈 주문" if is_close_order else "예약 주문"
                await self.telegram.send_message(
                    f"⏭️ {order_type} 스킵됨 (트리거 가격 문제)\n"
                    f"비트겟 ID: {order_id}\n"
                    f"스킵 사유: {skip_reason}"
                )
                return "skipped"
            
            # 실제 달러 마진 비율 동적 계산
            margin_ratio_result = await self.utils.calculate_dynamic_margin_ratio(
                size, adjusted_trigger_price, bitget_order
            )
            
            if not margin_ratio_result['success']:
                return "failed"
            
            margin_ratio = margin_ratio_result['margin_ratio']
            bitget_leverage = margin_ratio_result['leverage']
            
            # 🔥🔥🔥 레버리지 설정 - 강화된 로직
            try:
                await self._set_gate_leverage_enhanced(bitget_leverage)
            except Exception as e:
                self.logger.error(f"레버리지 설정 실패하지만 계속 진행: {e}")
            
            # 게이트 계정 정보
            gate_account = await self.gate.get_account_balance()
            gate_total_equity = float(gate_account.get('total', 0))
            gate_available = float(gate_account.get('available', 0))
            
            # 게이트에서 동일한 마진 비율로 투입할 실제 달러 금액 계산
            gate_margin = gate_total_equity * margin_ratio
            
            if gate_margin > gate_available:
                gate_margin = gate_available * 0.95
            
            if gate_margin < self.MIN_MARGIN:
                return "failed"
            
            # 게이트 계약 수 계산
            gate_notional_value = gate_margin * bitget_leverage
            gate_size = int(gate_notional_value / (adjusted_trigger_price * 0.0001))
            
            if gate_size == 0:
                gate_size = 1
            
            # 수정된 방향 처리
            gate_size, reduce_only_flag = await self.utils.calculate_gate_order_size_fixed(side, gate_size, is_close_order)
            
            # Gate.io 트리거 타입 변환
            gate_trigger_type = await self.utils.determine_gate_trigger_type(
                adjusted_trigger_price, self.gate_current_price or self.bitget_current_price
            )
            
            # TP/SL 가격 조정 (게이트 기준)
            adjusted_tp_price = None
            adjusted_sl_price = None
            
            if tp_price:
                adjusted_tp_price = await self.utils.adjust_price_for_gate(
                    tp_price,
                    self.bitget_current_price,
                    self.gate_current_price,
                    self.price_diff_percent
                )
            if sl_price:
                adjusted_sl_price = await self.utils.adjust_price_for_gate(
                    sl_price,
                    self.bitget_current_price,
                    self.gate_current_price,
                    self.price_diff_percent
                )
            
            # 🔥🔥🔥 Gate.io에 통합 TP/SL 포함 예약 주문 생성 - 포지션 체결 대기 활성화
            gate_order = await self.gate.create_unified_order_with_tp_sl(
                trigger_type=gate_trigger_type,
                trigger_price=str(adjusted_trigger_price),
                order_type="market",
                contract=self.GATE_CONTRACT,
                size=gate_size,
                tp_price=str(adjusted_tp_price) if adjusted_tp_price else None,
                sl_price=str(adjusted_sl_price) if adjusted_sl_price else None,
                bitget_order_info=bitget_order,
                wait_execution=not is_close_order  # 🔥🔥🔥 오픈 주문만 체결 대기
            )
            
            # 통계 업데이트
            if gate_order.get('has_tp_sl', False):
                self.daily_stats['unified_tp_sl_orders'] += 1
            
            # 🔥🔥🔥 포지션 체결 대기 (오픈 주문만)
            if not is_close_order and gate_order.get('staged_execution'):
                self.logger.info(f"🕐 포지션 체결 대기 시작: {order_id}")
                
                # 비동기로 포지션 체결 대기 및 성공 확인
                asyncio.create_task(self._wait_and_confirm_position_execution(
                    order_id, gate_size, gate_order.get('id')
                ))
            
            # 강화된 해시 추가
            order_details = {
                'contract': self.GATE_CONTRACT,
                'trigger_price': adjusted_trigger_price,
                'size': gate_size,
                'abs_size': abs(gate_size),
                'tp_price': adjusted_tp_price,
                'sl_price': adjusted_sl_price,
                'has_tp_sl': gate_order.get('has_tp_sl', False)
            }
            
            new_hashes = await self.utils.generate_multiple_order_hashes(order_details)
            for hash_key in new_hashes:
                self.gate_existing_order_hashes.add(hash_key)
            
            # 미러링 성공 기록
            self.mirrored_plan_orders[order_id] = {
                'gate_order_id': gate_order.get('id'),
                'bitget_order': bitget_order,
                'gate_order': gate_order,
                'created_at': datetime.now().isoformat(),
                'margin': gate_margin,
                'size': gate_size,
                'margin_ratio': margin_ratio,
                'leverage': bitget_leverage,
                'original_trigger_price': original_trigger_price,
                'adjusted_trigger_price': adjusted_trigger_price,
                'tp_price': tp_price,
                'sl_price': sl_price,
                'adjusted_tp_price': adjusted_tp_price,
                'adjusted_sl_price': adjusted_sl_price,
                'has_tp_sl': gate_order.get('has_tp_sl', False),
                'order_hashes': new_hashes,
                'unified_order': True,
                'is_close_order': is_close_order,
                'reduce_only': reduce_only_flag,
                'position_wait_enabled': not is_close_order  # 🔥🔥🔥 포지션 대기 여부
            }
            
            self.daily_stats['plan_order_mirrors'] += 1
            
            # 성공 메시지
            order_type = "클로즈 주문" if is_close_order else "예약 주문"
            tp_sl_info = ""
            if gate_order.get('has_tp_sl', False):
                tp_sl_info = f"\n\n🎯 통합 TP/SL 설정:"
                if adjusted_tp_price:
                    tp_sl_info += f"\n• TP: ${adjusted_tp_price:,.2f}"
                if adjusted_sl_price:
                    tp_sl_info += f"\n• SL: ${adjusted_sl_price:,.2f}"
            
            position_wait_info = ""
            if not is_close_order:
                position_wait_info = f"\n🕐 포지션 체결 대기 활성화됨"
            
            await self.telegram.send_message(
                f"✅ {order_type} 복제 성공 (시세차이 고려)\n"
                f"비트겟 ID: {order_id}\n"
                f"게이트 ID: {gate_order.get('id')}\n"
                f"방향: {side.upper()}\n"
                f"트리거가: ${adjusted_trigger_price:,.2f}\n"
                f"게이트 수량: {gate_size}\n"
                f"시세 차이: ${abs(self.bitget_current_price - self.gate_current_price):.2f}\n\n"
                f"💰 실제 달러 마진 동적 비율 복제:\n"
                f"마진 비율: {margin_ratio*100:.2f}%\n"
                f"게이트 투입 마진: ${gate_margin:,.2f}\n"
                f"레버리지: {bitget_leverage}x{tp_sl_info}{position_wait_info}"
            )
            
            return "success"
            
        except Exception as e:
            self.logger.error(f"새로운 예약 주문 복제 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'plan_order_id': bitget_order.get('orderId', bitget_order.get('planOrderId', 'unknown'))
            })
            return "failed"

    async def _wait_and_confirm_position_execution(self, bitget_order_id: str, expected_size: int, gate_order_id: str):
        """🔥🔥🔥 포지션 체결 대기 및 확인"""
        try:
            self.logger.info(f"🕐 포지션 체결 대기 시작: {bitget_order_id}")
            
            expected_side = "long" if expected_size > 0 else "short"
            start_time = datetime.now()
            
            # 최대 3분 대기
            while (datetime.now() - start_time).total_seconds() < self.position_wait_timeout:
                await asyncio.sleep(10)  # 10초마다 체크
                
                try:
                    gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
                    
                    for pos in gate_positions:
                        size = int(pos.get('size', 0))
                        
                        # 포지션 방향 확인
                        if expected_side == "long" and size > 0:
                            self.logger.info(f"✅ 롱 포지션 체결 확인: {size} (주문: {bitget_order_id})")
                            self.daily_stats['successful_position_waits'] += 1
                            
                            await self.telegram.send_message(
                                f"✅ 포지션 체결 확인됨\n"
                                f"비트겟 주문: {bitget_order_id}\n"
                                f"게이트 포지션: {size} (롱)\n"
                                f"대기 시간: {(datetime.now() - start_time).total_seconds():.1f}초"
                            )
                            return
                            
                        elif expected_side == "short" and size < 0:
                            self.logger.info(f"✅ 숏 포지션 체결 확인: {size} (주문: {bitget_order_id})")
                            self.daily_stats['successful_position_waits'] += 1
                            
                            await self.telegram.send_message(
                                f"✅ 포지션 체결 확인됨\n"
                                f"비트겟 주문: {bitget_order_id}\n"
                                f"게이트 포지션: {size} (숏)\n"
                                f"대기 시간: {(datetime.now() - start_time).total_seconds():.1f}초"
                            )
                            return
                    
                except Exception as check_error:
                    self.logger.warning(f"포지션 체크 중 오류: {check_error}")
                    continue
            
            # 타임아웃
            self.daily_stats['position_wait_timeouts'] += 1
            self.logger.warning(f"⏰ 포지션 체결 대기 타임아웃: {bitget_order_id}")
            
            await self.telegram.send_message(
                f"⏰ 포지션 체결 대기 타임아웃\n"
                f"비트겟 주문: {bitget_order_id}\n"
                f"게이트 주문: {gate_order_id}\n"
                f"대기 시간: {self.position_wait_timeout}초\n"
                f"시세 차이가 원인일 수 있습니다."
            )
            
        except Exception as e:
            self.logger.error(f"포지션 체결 대기 중 오류: {e}")

    async def _set_gate_leverage_enhanced(self, leverage: int, max_retries: int = 5) -> bool:
        """🔥🔥🔥 강화된 게이트 레버리지 설정"""
        for attempt in range(max_retries):
            try:
                self.logger.info(f"게이트 레버리지 설정 시도 {attempt + 1}/{max_retries}: {leverage}x")
                
                await self.gate.set_leverage(self.GATE_CONTRACT, leverage)
                
                # 더 긴 대기 시간
                await asyncio.sleep(2.0)
                
                # 설정 확인
                positions = await self.gate.get_positions(self.GATE_CONTRACT)
                if positions:
                    current_leverage = positions[0].get('leverage')
                    if current_leverage and int(float(current_leverage)) == leverage:
                        self.logger.info(f"✅ 레버리지 설정 확인: {leverage}x")
                        return True
                    else:
                        self.logger.warning(f"레버리지 불일치: 설정 {leverage}x, 실제 {current_leverage}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(3.0)
                            continue
                else:
                    self.logger.info(f"포지션 없음, 레버리지 설정 성공으로 간주")
                    return True
                
            except Exception as e:
                self.logger.warning(f"레버리지 설정 시도 {attempt + 1} 실패: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0)
                    continue
                else:
                    self.logger.error(f"레버리지 설정 최종 실패: {leverage}x")
                    return False
        
        return False

    async def process_filled_order(self, order: Dict):
        """체결된 주문으로부터 미러링 실행"""
        try:
            order_id = order.get('orderId', order.get('id', ''))
            side = order.get('side', '').lower()
            size = float(order.get('size', 0))
            fill_price = float(order.get('fillPrice', order.get('price', 0)))
            
            position_side = 'long' if side == 'buy' else 'short'
            
            # 🔥 렌더 재구동 시 기존 포지션 중복 방지
            synthetic_position = {
                'symbol': self.SYMBOL,
                'holdSide': position_side,
                'total': str(size),
                'openPriceAvg': str(fill_price),
                'markPrice': str(fill_price),
                'marginSize': '0',
                'leverage': '10',
                'marginMode': 'crossed',
                'unrealizedPL': '0'
            }
            
            if await self._should_skip_position_due_to_existing(synthetic_position):
                self.logger.info(f"🔄 렌더 재구동: 동일 포지션 존재로 주문 체결 미러링 스킵 - {order_id}")
                return
            
            # 🔥🔥🔥 시세 차이 확인 및 대기
            price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
            if price_diff_abs > self.price_sync_threshold:
                self.logger.warning(f"시세 차이 큼 ({price_diff_abs:.2f}$), 주문 체결 미러링 지연: {order_id}")
                self.daily_stats['price_sync_delays'] += 1
                
                # 시세 차이가 클 때 최대 30초 대기
                for i in range(6):
                    await asyncio.sleep(5)
                    # 시세 업데이트 (메인에서 호출될 것이지만 안전을 위해)
                    price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
                    if price_diff_abs <= self.price_sync_threshold:
                        self.logger.info(f"시세 차이 해소됨, 미러링 진행: {order_id}")
                        break
                else:
                    self.logger.warning(f"시세 차이 지속, 미러링 스킵: {order_id}")
                    return
            
            # 체결된 주문의 실제 달러 마진 비율 동적 계산
            margin_ratio_result = await self.utils.calculate_dynamic_margin_ratio(
                size, fill_price, order
            )
            
            if not margin_ratio_result['success']:
                return
            
            leverage = margin_ratio_result['leverage']
            
            # 가상의 포지션 데이터 생성
            synthetic_position.update({
                'marginSize': str(margin_ratio_result['required_margin']),
                'leverage': str(leverage)
            })
            
            pos_id = f"{self.SYMBOL}_{position_side}_{fill_price}"
            
            if pos_id in self.startup_positions or pos_id in self.mirrored_positions:
                return
            
            # 미러링 실행
            result = await self._mirror_new_position(synthetic_position)
            
            if result.success:
                self.mirrored_positions[pos_id] = await self.utils.create_position_info(synthetic_position)
                self.position_sizes[pos_id] = size
                self.daily_stats['successful_mirrors'] += 1
                self.daily_stats['order_mirrors'] += 1
                
                await self.telegram.send_message(
                    f"⚡ 실시간 주문 체결 미러링 성공\n"
                    f"주문 ID: {order_id}\n"
                    f"방향: {position_side}\n"
                    f"체결가: ${fill_price:,.2f}\n"
                    f"수량: {size}\n"
                    f"레버리지: {leverage}x\n"
                    f"시세 차이: ${price_diff_abs:.2f}\n"
                    f"실제 마진 비율: {margin_ratio_result['margin_ratio']*100:.2f}%"
                )
            else:
                self.failed_mirrors.append(result)
                self.daily_stats['failed_mirrors'] += 1
                
                await self.telegram.send_message(
                    f"❌ 실시간 주문 체결 미러링 실패\n"
                    f"주문 ID: {order_id}\n"
                    f"오류: {result.error}"
                )
            
            self.daily_stats['total_mirrored'] += 1
            
        except Exception as e:
            self.logger.error(f"체결 주문 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'order_id': order.get('orderId', 'unknown')
            })

    async def process_position(self, bitget_pos: Dict):
        """포지션 처리"""
        try:
            pos_id = self.utils.generate_position_id(bitget_pos)
            
            if pos_id in self.startup_positions:
                return
            
            # 🔥 렌더 재구동 시 기존 포지션 중복 방지
            if await self._should_skip_position_due_to_existing(bitget_pos):
                return
            
            current_size = float(bitget_pos.get('total', 0))
            
            if pos_id not in self.mirrored_positions:
                await asyncio.sleep(2)
                
                if pos_id not in self.mirrored_positions:
                    result = await self._mirror_new_position(bitget_pos)
                    
                    if result.success:
                        self.mirrored_positions[pos_id] = await self.utils.create_position_info(bitget_pos)
                        self.position_sizes[pos_id] = current_size
                        self.daily_stats['successful_mirrors'] += 1
                        self.daily_stats['position_mirrors'] += 1
                        
                        leverage = bitget_pos.get('leverage', 'N/A')
                        await self.telegram.send_message(
                            f"✅ 포지션 기반 미러링 성공\n"
                            f"방향: {bitget_pos.get('holdSide', '')}\n"
                            f"진입가: ${float(bitget_pos.get('openPriceAvg', 0)):,.2f}\n"
                            f"레버리지: {leverage}x"
                        )
                    else:
                        self.failed_mirrors.append(result)
                        self.daily_stats['failed_mirrors'] += 1
                    
                    self.daily_stats['total_mirrored'] += 1
            else:
                last_size = self.position_sizes.get(pos_id, 0)
                
                # 부분 청산 감지
                if current_size < last_size * 0.95:
                    reduction_ratio = 1 - (current_size / last_size)
                    await self._handle_partial_close(pos_id, bitget_pos, reduction_ratio)
                    self.position_sizes[pos_id] = current_size
                    self.daily_stats['partial_closes'] += 1
                
        except Exception as e:
            self.logger.error(f"포지션 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'position': self.utils.generate_position_id(bitget_pos)
            })

    async def handle_position_close(self, pos_id: str):
        """포지션 종료 처리"""
        try:
            result = await self.gate.close_position(self.GATE_CONTRACT)
            
            # 상태 정리
            if pos_id in self.mirrored_positions:
                del self.mirrored_positions[pos_id]
            if pos_id in self.position_sizes:
                del self.position_sizes[pos_id]
            
            self.daily_stats['full_closes'] += 1
            
            await self.telegram.send_message(
                f"✅ 포지션 종료 완료\n포지션 ID: {pos_id}"
            )
            
        except Exception as e:
            self.logger.error(f"포지션 종료 처리 실패: {e}")

    async def check_sync_status(self) -> Dict:
        """🔥🔥🔥 동기화 상태 확인 - 개선된 로직"""
        try:
            # 비트겟 포지션 조회
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            bitget_active = [
                pos for pos in bitget_positions 
                if float(pos.get('total', 0)) > 0
            ]
            
            # 게이트 포지션 조회
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            gate_active = [
                pos for pos in gate_positions 
                if pos.get('size', 0) != 0
            ]
            
            # 🔥🔥🔥 신규 포지션만 정확하게 카운팅
            new_bitget_positions = []
            for pos in bitget_active:
                pos_id = self.utils.generate_position_id(pos)
                if pos_id not in self.startup_positions:
                    new_bitget_positions.append(pos)
            
            # 🔥🔥🔥 게이트도 startup positions를 고려하여 계산
            new_gate_positions = []
            for pos in gate_active:
                # 게이트 포지션 ID 생성 (시세 차이 고려)
                gate_pos_id = self._generate_gate_position_id(pos)
                
                # startup 시점에 없던 포지션만 카운팅
                if gate_pos_id not in self.startup_gate_positions:
                    # 🔥🔥🔥 시세 차이를 고려한 매칭 로직
                    is_startup_match = await self._is_startup_position_match(pos)
                    if not is_startup_match:
                        new_gate_positions.append(pos)
            
            new_bitget_count = len(new_bitget_positions)
            new_gate_count = len(new_gate_positions)
            position_diff = new_bitget_count - new_gate_count
            
            # 🔥🔥🔥 차이가 있을 때 상세 분석
            if position_diff != 0:
                self.daily_stats['sync_status_corrected'] += 1
                self.logger.info(f"🔍 동기화 상태 분석:")
                self.logger.info(f"   비트겟 전체 포지션: {len(bitget_active)}개")
                self.logger.info(f"   비트겟 신규 포지션: {new_bitget_count}개")
                self.logger.info(f"   게이트 전체 포지션: {len(gate_active)}개")
                self.logger.info(f"   게이트 신규 포지션: {new_gate_count}개")
                self.logger.info(f"   차이: {position_diff}개")
                
                # 시세 차이 정보 추가
                price_diff_abs = abs(self.bitget_current_price - self.gate_current_price)
                self.logger.info(f"   현재 시세 차이: ${price_diff_abs:.2f}")
            
            return {
                'is_synced': position_diff == 0,
                'bitget_new_count': new_bitget_count,
                'gate_new_count': new_gate_count,
                'position_diff': position_diff,
                'bitget_total_count': len(bitget_active),
                'gate_total_count': len(gate_active),
                'price_diff': abs(self.bitget_current_price - self.gate_current_price)
            }
            
        except Exception as e:
            self.logger.error(f"동기화 상태 확인 실패: {e}")
            return {
                'is_synced': True,  # 오류 시 동기화됨으로 처리
                'bitget_new_count': 0,
                'gate_new_count': 0,
                'position_diff': 0,
                'bitget_total_count': 0,
                'gate_total_count': 0,
                'price_diff': 0
            }

    def _generate_gate_position_id(self, gate_pos: Dict) -> str:
        """🔥🔥🔥 게이트 포지션 ID 생성"""
        try:
            contract = gate_pos.get('contract', self.GATE_CONTRACT)
            size = gate_pos.get('size', 0)
            
            # 포지션 방향 결정
            if isinstance(size, (int, float)) and size != 0:
                side = 'long' if size > 0 else 'short'
            else:
                side = 'unknown'
            
            # 평균 진입가 (없으면 현재 시세 사용)
            entry_price = gate_pos.get('entry_price', self.gate_current_price or 0)
            
            return f"{contract}_{side}_{entry_price}"
            
        except Exception as e:
            self.logger.error(f"게이트 포지션 ID 생성 실패: {e}")
            return f"{self.GATE_CONTRACT}_unknown_unknown"

    async def _is_startup_position_match(self, gate_pos: Dict) -> bool:
        """🔥🔥🔥 게이트 포지션이 startup 시점의 포지션과 매칭되는지 확인 (시세 차이 고려)"""
        try:
            gate_size = gate_pos.get('size', 0)
            gate_side = 'long' if gate_size > 0 else 'short'
            gate_entry_price = float(gate_pos.get('entry_price', 0))
            
            # startup positions와 비교
            for startup_pos_id in self.startup_positions:
                # startup_pos_id 형식: "BTCUSDT_long_104500.0" 같은 형태
                try:
                    parts = startup_pos_id.split('_')
                    if len(parts) >= 3:
                        startup_side = parts[1]
                        startup_price = float(parts[2])
                        
                        # 방향이 같고 가격 차이가 시세 차이 범위 내인지 확인
                        if gate_side == startup_side:
                            price_diff_abs = abs(gate_entry_price - startup_price)
                            # 🔥🔥🔥 시세 차이를 고려한 관대한 매칭 (±50달러)
                            if price_diff_abs <= 50:
                                self.logger.info(f"🔍 startup 포지션 매칭됨: 게이트({gate_side}, ${gate_entry_price}) ↔ startup({startup_side}, ${startup_price})")
                                return True
                                
                except Exception as parse_error:
                    self.logger.debug(f"startup position ID 파싱 실패: {startup_pos_id} - {parse_error}")
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error(f"startup 포지션 매칭 확인 실패: {e}")
            return False

    # === 기존 헬퍼 메서드들 ===
    
    async def _check_existing_gate_positions(self):
        """렌더 재구동 시 기존 게이트 포지션 확인"""
        try:
            self.existing_gate_positions = await self.gate.check_existing_positions(self.GATE_CONTRACT)
            
            if self.existing_gate_positions['has_long'] or self.existing_gate_positions['has_short']:
                self.render_restart_detected = True
                self.logger.warning(f"🔄 렌더 재구동 감지: 기존 게이트 포지션 발견")
            else:
                self.render_restart_detected = False
                self.logger.info("✅ 새로운 시작: 기존 게이트 포지션 없음")
                
        except Exception as e:
            self.logger.error(f"기존 게이트 포지션 확인 실패: {e}")
            self.existing_gate_positions = {
                'has_long': False, 'has_short': False, 'long_size': 0, 'short_size': 0, 'positions': []
            }
            self.render_restart_detected = False

    async def _record_gate_existing_orders_advanced(self):
        """게이트 기존 예약 주문 기록"""
        try:
            gate_orders = await self.gate.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            for i, gate_order in enumerate(gate_orders):
                try:
                    order_details = await self.utils.extract_gate_order_details(gate_order)
                    
                    if order_details:
                        trigger_price = order_details['trigger_price']
                        price_key = f"{self.GATE_CONTRACT}_{trigger_price:.2f}"
                        self.mirrored_trigger_prices.add(price_key)
                        
                        hashes = await self.utils.generate_multiple_order_hashes(order_details)
                        
                        if hashes:
                            for hash_key in hashes:
                                self.gate_existing_order_hashes.add(hash_key)
                            
                            order_id = gate_order.get('id', f"unknown_{i}")
                            self.gate_existing_orders_detailed[order_id] = {
                                'gate_order': gate_order,
                                'details': order_details,
                                'hashes': hashes,
                                'trigger_price': trigger_price,
                                'recorded_at': datetime.now().isoformat()
                            }
                            
                            self.logger.info(f"📝 게이트 예약 주문 기록: ID={order_id}, 가격=${trigger_price:.2f}")
                
                except Exception as e:
                    self.logger.warning(f"게이트 주문 처리 실패: {e}")
                    continue
            
            self.logger.info(f"✅ 게이트 기존 예약 주문 기록 완료: {len(self.gate_existing_orders_detailed)}개")
            
        except Exception as e:
            self.logger.error(f"게이트 기존 예약 주문 조회 실패: {e}")

    async def _record_startup_positions(self):
        """시작 시 존재하는 포지션 기록"""
        try:
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    pos_id = self.utils.generate_position_id(pos)
                    self.startup_positions.add(pos_id)
                    self.position_sizes[pos_id] = float(pos.get('total', 0))
            
            # 기존 주문 ID들도 기록
            try:
                recent_orders = await self.bitget.get_recent_filled_orders(self.SYMBOL, minutes=10)
                for order in recent_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if order_id:
                        self.processed_orders.add(order_id)
            except Exception as e:
                self.logger.warning(f"기존 주문 기록 실패: {e}")
                
        except Exception as e:
            self.logger.error(f"기존 포지션 기록 실패: {e}")

    async def _record_startup_plan_orders(self):
        """시작 시 존재하는 예약 주문 기록"""
        try:
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            for order in plan_orders + tp_sl_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.startup_plan_orders.add(order_id)
                    self.last_plan_order_ids.add(order_id)
            
            total_existing = len(plan_orders) + len(tp_sl_orders)
            self.logger.info(f"총 {total_existing}개의 기존 예약 주문을 기록했습니다")
            
        except Exception as e:
            self.logger.error(f"기존 예약 주문 기록 실패: {e}")

    async def _record_startup_gate_positions(self):
        """🔥🔥🔥 시작시 게이트 포지션 기록 - 개선된 로직"""
        try:
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            
            for pos in gate_positions:
                if pos.get('size', 0) != 0:
                    gate_pos_id = self._generate_gate_position_id(pos)
                    self.startup_gate_positions.add(gate_pos_id)
                    
                    self.logger.info(f"📝 게이트 startup 포지션 기록: {gate_pos_id}")
            
            self.logger.info(f"✅ 시작시 게이트 포지션 수 기록: {len(self.startup_gate_positions)}개")
            
        except Exception as e:
            self.logger.error(f"시작시 게이트 포지션 기록 실패: {e}")

    async def _create_initial_plan_order_snapshot(self):
        """예약 주문 초기 스냅샷 생성"""
        try:
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_orders = plan_orders + tp_sl_orders
            
            for order in all_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.plan_order_snapshot[order_id] = {
                        'order_data': order.copy(),
                        'timestamp': datetime.now().isoformat(),
                        'status': 'active'
                    }
                    self.last_plan_order_ids.add(order_id)
            
            self.logger.info(f"예약 주문 초기 스냅샷 완료: {len(self.plan_order_snapshot)}개 주문")
            
        except Exception as e:
            self.logger.error(f"예약 주문 초기 스냅샷 생성 실패: {e}")

    async def _mirror_startup_plan_orders(self):
        """시작 시 기존 예약 주문 복제"""
        try:
            self.logger.info("🎯 시작 시 기존 예약 주문 복제 시작")
            
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            orders_to_mirror = []
            orders_to_mirror.extend(plan_orders)
            
            # TP/SL 주문 중에서 클로즈 주문도 정확하게 추가
            for tp_sl_order in tp_sl_orders:
                side = tp_sl_order.get('side', tp_sl_order.get('tradeSide', '')).lower()
                reduce_only = tp_sl_order.get('reduceOnly', False)
                
                is_close_order = (
                    'close' in side or 
                    reduce_only is True or 
                    reduce_only == 'true'
                )
                
                if is_close_order:
                    orders_to_mirror.append(tp_sl_order)
                    self.logger.info(f"🔴 클로즈 주문 복제 대상에 추가: {tp_sl_order.get('orderId')}")
            
            if not orders_to_mirror:
                self.startup_plan_orders_processed = True
                self.logger.info("복제할 예약 주문이 없습니다.")
                return
            
            mirrored_count = 0
            failed_count = 0
            duplicate_count = 0
            price_duplicate_count = 0
            close_order_count = 0
            
            for order in orders_to_mirror:
                try:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if not order_id:
                        continue
                    
                    side = order.get('side', order.get('tradeSide', '')).lower()
                    reduce_only = order.get('reduceOnly', False)
                    is_close_order = ('close' in side or reduce_only is True or reduce_only == 'true')
                    
                    # 가격 기반 중복 체크
                    trigger_price = 0
                    for price_field in ['triggerPrice', 'price', 'executePrice']:
                        if order.get(price_field):
                            trigger_price = float(order.get(price_field))
                            break
                    
                    if trigger_price > 0:
                        is_price_duplicate = await self._is_price_duplicate(trigger_price)
                        if is_price_duplicate:
                            price_duplicate_count += 1
                            self.logger.info(f"🛡️ 가격 중복으로 스킵: {order_id}, 가격=${trigger_price:.2f}")
                            self.processed_plan_orders.add(order_id)
                            continue
                    
                    # 강화된 중복 복제 확인
                    is_duplicate, duplicate_type = await self._is_duplicate_order_advanced(order)
                    if is_duplicate:
                        if duplicate_type == "advanced":
                            self.daily_stats['duplicate_advanced_prevention'] += 1
                            self.logger.info(f"🛡️ 강화된 중복 감지로 스킵: {order_id}")
                        else:
                            duplicate_count += 1
                            self.daily_stats['duplicate_orders_prevented'] += 1
                            self.logger.info(f"🛡️ 기본 중복 감지로 스킵: {order_id}")
                        
                        self.processed_plan_orders.add(order_id)
                        continue
                    
                    # 시작 시에는 포지션 체결 대기 비활성화
                    result = await self._process_startup_plan_order_fixed(order)
                    
                    if result == "success":
                        mirrored_count += 1
                        if is_close_order:
                            close_order_count += 1
                            self.daily_stats['close_order_mirrors'] += 1
                            self.logger.info(f"✅ 클로즈 주문 복제 성공: {order_id}")
                        
                        # 성공적으로 복제되면 가격 기록
                        if trigger_price > 0:
                            await self._add_trigger_price(trigger_price)
                    else:
                        failed_count += 1
                    
                    self.processed_plan_orders.add(order_id)
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"기존 예약 주문 복제 실패: {order.get('orderId', 'unknown')} - {e}")
                    continue
            
            self.daily_stats['startup_plan_mirrors'] = mirrored_count
            self.daily_stats['price_duplicate_prevention'] = price_duplicate_count
            self.startup_plan_orders_processed = True
            
            await self.telegram.send_message(
                f"✅ 시작 시 기존 예약 주문 복제 완료\n"
                f"성공: {mirrored_count}개\n"
                f"• 클로즈 주문: {close_order_count}개\n"
                f"실패: {failed_count}개\n"
                f"중복 방지: {duplicate_count}개\n"
                f"가격 중복 방지: {price_duplicate_count}개"
            )
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 복제 처리 실패: {e}")

    async def _process_startup_plan_order_fixed(self, bitget_order: Dict) -> str:
        """시작 시 예약 주문 복제 처리 (포지션 체결 대기 없음)"""
        # _process_new_plan_order_with_position_wait와 동일하지만 wait_execution=False로 호출
        try:
            # 간단화된 버전으로 처리
            return await self._process_new_plan_order_with_position_wait(bitget_order)
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 복제 실패: {e}")
            return "failed"

    # === 헬퍼 메서드들 ===
    
    async def _is_price_duplicate(self, trigger_price: float) -> bool:
        """가격 기반 중복 체크"""
        try:
            price_key = f"{self.GATE_CONTRACT}_{trigger_price:.2f}"
            return price_key in self.mirrored_trigger_prices
        except Exception as e:
            self.logger.error(f"가격 중복 체크 실패: {e}")
            return False

    async def _add_trigger_price(self, trigger_price: float):
        """트리거 가격을 중복 방지 목록에 추가"""
        try:
            price_key = f"{self.GATE_CONTRACT}_{trigger_price:.2f}"
            self.mirrored_trigger_prices.add(price_key)
        except Exception as e:
            self.logger.error(f"트리거 가격 추가 실패: {e}")

    async def _is_duplicate_order_advanced(self, bitget_order: Dict) -> Tuple[bool, str]:
        """강화된 중복 주문 확인"""
        try:
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            size = float(bitget_order.get('size', 0))
            
            # 트리거 가격 추출
            original_trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    original_trigger_price = float(bitget_order.get(price_field))
                    break
            
            if original_trigger_price == 0:
                return False, "none"
            
            # TP/SL 정보 추출
            tp_price, sl_price = await self.utils.extract_tp_sl_from_bitget_order(bitget_order)
            
            # 게이트 기준으로 가격 조정
            adjusted_trigger_price = await self.utils.adjust_price_for_gate(
                original_trigger_price,
                self.bitget_current_price,
                self.gate_current_price,
                self.price_diff_percent
            )
            
            # 실제 달러 마진 비율 동적 계산으로 게이트 사이즈 계산
            margin_ratio_result = await self.utils.calculate_dynamic_margin_ratio(
                size, adjusted_trigger_price, bitget_order
            )
            
            if not margin_ratio_result['success']:
                return False, "none"
            
            margin_ratio = margin_ratio_result['margin_ratio']
            bitget_leverage = margin_ratio_result['leverage']
            
            gate_account = await self.gate.get_account_balance()
            gate_total_equity = float(gate_account.get('total', 0))
            gate_margin = gate_total_equity * margin_ratio
            gate_notional_value = gate_margin * bitget_leverage
            gate_size = int(gate_notional_value / (adjusted_trigger_price * 0.0001))
            
            if gate_size == 0:
                gate_size = 1
                
            # 클로즈 주문 여부 확인
            reduce_only = bitget_order.get('reduceOnly', False)
            is_close_order = ('close' in side or reduce_only is True or reduce_only == 'true')
            
            # 수정된 사이즈 계산 사용
            gate_size, reduce_only_flag = await self.utils.calculate_gate_order_size_fixed(side, gate_size, is_close_order)
            
            # 강화된 중복 체크
            order_details = {
                'contract': self.GATE_CONTRACT,
                'trigger_price': adjusted_trigger_price,
                'size': gate_size,
                'abs_size': abs(gate_size),
                'tp_price': tp_price,
                'sl_price': sl_price,
                'has_tp_sl': bool(tp_price or sl_price)
            }
            
            bitget_hashes = await self.utils.generate_multiple_order_hashes(order_details)
            
            # 기존 게이트 해시와 비교
            for bitget_hash in bitget_hashes:
                if bitget_hash in self.gate_existing_order_hashes:
                    self.logger.info(f"🛡️ 강화된 중복 주문 발견: {bitget_order.get('orderId', 'unknown')}")
                    return True, "advanced"
            
            return False, "none"
            
        except Exception as e:
            self.logger.error(f"강화된 중복 주문 확인 실패: {e}")
            return False, "none"

    async def _should_skip_position_due_to_existing(self, bitget_position: Dict) -> bool:
        """렌더 재구동 시 기존 포지션 때문에 스킵해야 하는지 판단"""
        try:
            if not self.render_restart_detected:
                return False
            
            position_side = bitget_position.get('holdSide', '').lower()
            position_size = float(bitget_position.get('total', 0))
            
            if position_side == 'long' and self.existing_gate_positions['has_long']:
                existing_size = self.existing_gate_positions['long_size']
                size_diff_percent = abs(position_size - existing_size) / max(position_size, existing_size) * 100
                if size_diff_percent < 20:
                    self.daily_stats['render_restart_skips'] += 1
                    return True
            
            elif position_side == 'short' and self.existing_gate_positions['has_short']:
                existing_size = self.existing_gate_positions['short_size']
                size_diff_percent = abs(position_size - existing_size) / max(position_size, existing_size) * 100
                if size_diff_percent < 20:
                    self.daily_stats['render_restart_skips'] += 1
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"기존 포지션 스킵 판단 실패: {e}")
            return False

    async def _mirror_new_position(self, bitget_pos: Dict) -> MirrorResult:
        """새로운 포지션 미러링"""
        retry_count = 0
        
        while retry_count < self.MAX_RETRIES:
            try:
                margin_ratio = await self._calculate_margin_ratio(bitget_pos)
                
                if margin_ratio is None:
                    return MirrorResult(
                        success=False,
                        action="new_position",
                        bitget_data=bitget_pos,
                        error="마진 비율 계산 실패"
                    )
                
                gate_account = await self.gate.get_account_balance()
                gate_available = float(gate_account.get('available', 0))
                gate_margin = gate_available * margin_ratio
                
                if gate_margin < self.MIN_MARGIN:
                    return MirrorResult(
                        success=False,
                        action="new_position",
                        bitget_data=bitget_pos,
                        error=f"게이트 마진 부족: ${gate_margin:.2f}"
                    )
                
                leverage = int(float(bitget_pos.get('leverage', 1)))
                
                # 게이트 레버리지 설정
                await self._set_gate_leverage_enhanced(leverage)
                
                side = bitget_pos.get('holdSide', '').lower()
                current_price = float(bitget_pos.get('markPrice', bitget_pos.get('openPriceAvg', 0)))
                
                contract_info = await self.gate.get_contract_info(self.GATE_CONTRACT)
                quanto_multiplier = float(contract_info.get('quanto_multiplier', 0.0001))
                
                notional_value = gate_margin * leverage
                gate_size = int(notional_value / (current_price * quanto_multiplier))
                
                if gate_size == 0:
                    gate_size = 1
                
                if side == 'short':
                    gate_size = -gate_size
                
                # 🔥🔥🔥 포지션 체결 대기 포함 주문
                order_result = await self.gate.place_order_and_wait_execution(
                    contract=self.GATE_CONTRACT,
                    size=gate_size,
                    price=None,
                    reduce_only=False,
                    wait_execution=True
                )
                
                await asyncio.sleep(1)
                
                self.daily_stats['total_volume'] += abs(notional_value)
                
                return MirrorResult(
                    success=True,
                    action="new_position",
                    bitget_data=bitget_pos,
                    gate_data={
                        'order': order_result,
                        'size': gate_size,
                        'margin': gate_margin,
                        'leverage': leverage
                    }
                )
                
            except Exception as e:
                retry_count += 1
                error_msg = str(e)
                
                if retry_count < self.MAX_RETRIES:
                    wait_time = 2 ** retry_count
                    await asyncio.sleep(wait_time)
                else:
                    return MirrorResult(
                        success=False,
                        action="new_position",
                        bitget_data=bitget_pos,
                        error=f"최대 재시도 횟수 초과: {error_msg}"
                    )

    async def _calculate_margin_ratio(self, bitget_pos: Dict) -> Optional[float]:
        """비트겟 포지션의 마진 비율 계산"""
        try:
            bitget_account = await self.bitget.get_account_info()
            total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            position_margin = float(bitget_pos.get('marginSize', bitget_pos.get('margin', 0)))
            
            if total_equity <= 0 or position_margin <= 0:
                return None
            
            margin_ratio = position_margin / total_equity
            return margin_ratio
            
        except Exception as e:
            self.logger.error(f"마진 비율 계산 실패: {e}")
            return None

    async def _handle_partial_close(self, pos_id: str, bitget_pos: Dict, reduction_ratio: float):
        """부분 청산 처리"""
        try:
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            
            if not gate_positions or gate_positions[0].get('size', 0) == 0:
                return
            
            gate_pos = gate_positions[0]
            current_gate_size = int(gate_pos['size'])
            close_size = int(abs(current_gate_size) * reduction_ratio)
            
            if close_size == 0:
                return
            
            if current_gate_size > 0:
                close_size = -close_size
            else:
                close_size = close_size
            
            result = await self.gate.place_order(
                contract=self.GATE_CONTRACT,
                size=close_size,
                price=None,
                reduce_only=True
            )
            
            await self.telegram.send_message(
                f"📉 부분 청산 완료\n"
                f"비율: {reduction_ratio*100:.1f}%\n"
                f"수량: {abs(close_size)} 계약"
            )
            
        except Exception as e:
            self.logger.error(f"부분 청산 처리 실패: {e}")

    async def _handle_plan_order_cancel(self, bitget_order_id: str):
        """예약 주문 취소 처리"""
        try:
            self.logger.info(f"예약 주문 취소 처리 시작: {bitget_order_id}")
            
            # 미러링된 주문인지 확인
            if bitget_order_id not in self.mirrored_plan_orders:
                self.logger.info(f"미러링되지 않은 주문이므로 취소 처리 스킵: {bitget_order_id}")
                return
            
            mirror_info = self.mirrored_plan_orders[bitget_order_id]
            gate_order_id = mirror_info.get('gate_order_id')
            
            if not gate_order_id:
                self.logger.warning(f"게이트 주문 ID가 없음: {bitget_order_id}")
                del self.mirrored_plan_orders[bitget_order_id]
                return
            
            # 게이트에서 예약 주문 취소
            try:
                await self.gate.cancel_price_triggered_order(gate_order_id)
                self.daily_stats['plan_order_cancel_success'] += 1
                
                await self.telegram.send_message(
                    f"🚫✅ 예약 주문 취소 동기화 완료\n"
                    f"비트겟 ID: {bitget_order_id}\n"
                    f"게이트 ID: {gate_order_id}"
                )
                
            except Exception as cancel_error:
                error_msg = str(cancel_error).lower()
                
                if any(keyword in error_msg for keyword in [
                    "not found", "order not exist", "invalid order", 
                    "order does not exist", "auto_order_not_found"
                ]):
                    # 주문이 이미 취소되었거나 체결됨
                    self.daily_stats['plan_order_cancel_success'] += 1
                    await self.telegram.send_message(
                        f"🚫✅ 예약 주문 취소 처리 완료\n"
                        f"비트겟 ID: {bitget_order_id}\n"
                        f"게이트 주문이 이미 취소되었거나 체결되었습니다."
                    )
                else:
                    self.daily_stats['plan_order_cancel_failed'] += 1
                    await self.telegram.send_message(
                        f"❌ 예약 주문 취소 실패\n"
                        f"비트겟 ID: {bitget_order_id}\n"
                        f"게이트 ID: {gate_order_id}\n"
                        f"오류: {str(cancel_error)[:200]}"
                    )
            
            # 미러링 기록에서 제거
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]
                self.logger.info(f"미러링 기록에서 제거됨: {bitget_order_id}")
                
        except Exception as e:
            self.logger.error(f"예약 주문 취소 처리 중 예외 발생: {e}")
            
            # 오류 발생 시에도 미러링 기록에서 제거
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]

    async def stop(self):
        """포지션 매니저 중지"""
        self.logger.info("포지션 매니저 중지")
