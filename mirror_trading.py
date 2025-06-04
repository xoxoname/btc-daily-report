import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json
import traceback

logger = logging.getLogger(__name__)

@dataclass
class PositionInfo:
    """포지션 정보"""
    symbol: str
    side: str
    size: float
    entry_price: float
    margin: float
    leverage: int
    mode: str
    tp_orders: List[Dict] = field(default_factory=list)
    sl_orders: List[Dict] = field(default_factory=list)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)
    
@dataclass
class MirrorResult:
    """미러링 결과"""
    success: bool
    action: str
    bitget_data: Dict
    gate_data: Optional[Dict] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

class MirrorTradingSystem:
    def __init__(self, config, bitget_client, gate_client, telegram_bot):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.telegram = telegram_bot
        self.logger = logging.getLogger('mirror_trading')
        
        # 미러링 상태 관리
        self.mirrored_positions: Dict[str, PositionInfo] = {}
        self.startup_positions: Set[str] = set()
        self.failed_mirrors: List[MirrorResult] = []
        self.last_sync_check = datetime.min
        self.last_report_time = datetime.min
        
        # 포지션 크기 추적
        self.position_sizes: Dict[str, float] = {}
        
        # 주문 체결 추적
        self.processed_orders: Set[str] = set()
        self.last_order_check = datetime.now()
        
        # 예약 주문 추적 관리
        self.mirrored_plan_orders: Dict[str, Dict] = {}
        self.processed_plan_orders: Set[str] = set()
        self.startup_plan_orders: Set[str] = set()
        self.startup_plan_orders_processed: bool = False
        
        # 예약 주문 취소 감지 시스템
        self.last_plan_order_ids: Set[str] = set()
        self.plan_order_snapshot: Dict[str, Dict] = {}
        self.cancel_retry_count: int = 0
        self.max_cancel_retry: int = 3
        self.cancel_verification_delay: float = 2.0
        
        # 포지션 유무에 따른 예약 주문 복제 관리
        self.startup_position_tp_sl: Set[str] = set()
        self.has_startup_positions: bool = False
        
        # 🔥 렌더 재구동 시 기존 게이트 포지션 확인
        self.existing_gate_positions: Dict = {}
        self.render_restart_detected: bool = False
        
        # 시세 차이 관리
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.last_price_update: datetime = datetime.min
        
        # 동기화 허용 오차
        self.SYNC_TOLERANCE_MINUTES = 5
        self.MAX_PRICE_DIFF_PERCENT = 1.0
        self.POSITION_SYNC_RETRY_COUNT = 3
        
        # 동기화 개선 - 포지션 카운팅 로직 수정
        self.startup_positions_detailed: Dict[str, Dict] = {}
        self.startup_gate_positions_count: int = 0
        self.sync_warning_suppressed_until: datetime = datetime.min
        
        # 🔥 게이트 기존 예약 주문 추적 (중복 방지)
        self.gate_existing_order_hashes: Set[str] = set()
        
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
            'plan_order_skipped_trigger_price': 0,
            'price_adjustments': 0,
            'sync_tolerance_used': 0,
            'sync_warnings_suppressed': 0,
            'position_size_differences_ignored': 0,
            'cancel_verification_success': 0,
            'cancel_verification_failed': 0,
            'tp_sl_mirrors_success': 0,
            'tp_sl_mirrors_failed': 0,
            'tp_only_mirrors': 0,
            'sl_only_mirrors': 0,
            'tp_sl_both_mirrors': 0,
            'duplicate_orders_prevented': 0,
            'render_restart_skips': 0,
            'unified_tp_sl_orders': 0,
            'errors': []
        }
        
        self.monitoring = True
        self.logger.info("미러 트레이딩 시스템 초기화 완료 - 통합 TP/SL 예약주문 복제 + 렌더 재구동 대응")

    async def start(self):
        """미러 트레이딩 시작"""
        try:
            self.logger.info("미러 트레이딩 시스템 시작 - 통합 TP/SL 예약주문 복제 + 렌더 재구동 대응")
            
            # 현재 시세 업데이트
            await self._update_current_prices()
            
            # 🔥 렌더 재구동 시 기존 게이트 포지션 확인
            await self._check_existing_gate_positions()
            
            # 🔥 게이트 기존 예약 주문 확인 (중복 방지)
            await self._record_gate_existing_orders()
            
            # 초기 포지션 및 예약 주문 기록
            await self._record_startup_positions()
            await self._record_startup_plan_orders()
            await self._record_startup_position_tp_sl()
            await self._record_startup_gate_positions()
            
            # 예약 주문 초기 스냅샷 생성
            await self._create_initial_plan_order_snapshot()
            
            # 시작 시 기존 예약 주문 복제 (통합 TP/SL 방식)
            await self._mirror_startup_plan_orders()
            
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

    async def _check_existing_gate_positions(self):
        """🔥 렌더 재구동 시 기존 게이트 포지션 확인"""
        try:
            self.logger.info("🔍 렌더 재구동 시 기존 게이트 포지션 확인 중...")
            
            self.existing_gate_positions = await self.gate.check_existing_positions(self.GATE_CONTRACT)
            
            if self.existing_gate_positions['has_long'] or self.existing_gate_positions['has_short']:
                self.render_restart_detected = True
                self.logger.warning(f"🔄 렌더 재구동 감지: 기존 게이트 포지션 발견")
                self.logger.warning(f"   - 롱 포지션: {self.existing_gate_positions['has_long']} (크기: {self.existing_gate_positions['long_size']})")
                self.logger.warning(f"   - 숏 포지션: {self.existing_gate_positions['has_short']} (크기: {self.existing_gate_positions['short_size']})")
                self.logger.warning(f"   - 동일 포지션 중복 복제 방지 활성화")
            else:
                self.render_restart_detected = False
                self.logger.info("✅ 새로운 시작: 기존 게이트 포지션 없음")
            
        except Exception as e:
            self.logger.error(f"기존 게이트 포지션 확인 실패: {e}")
            self.existing_gate_positions = {
                'has_long': False,
                'has_short': False,
                'long_size': 0,
                'short_size': 0,
                'positions': []
            }
            self.render_restart_detected = False

    async def _record_gate_existing_orders(self):
        """🔥 게이트 기존 예약 주문 기록 (중복 방지)"""
        try:
            self.logger.info("🔍 게이트 기존 예약 주문 조회 중...")
            
            gate_orders = await self.gate.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            for gate_order in gate_orders:
                # 게이트 주문의 특성으로 해시 생성
                order_hash = self._generate_order_hash_from_gate_order(gate_order)
                if order_hash:
                    self.gate_existing_order_hashes.add(order_hash)
            
            self.logger.info(f"✅ 게이트 기존 예약 주문 {len(self.gate_existing_order_hashes)}개 기록됨")
            
        except Exception as e:
            self.logger.error(f"게이트 기존 예약 주문 조회 실패: {e}")
            # 실패해도 계속 진행

    def _generate_order_hash_from_gate_order(self, gate_order: Dict) -> Optional[str]:
        """게이트 주문으로부터 해시 생성"""
        try:
            trigger_price = gate_order.get('trigger', {}).get('price', '')
            initial_size = gate_order.get('initial', {}).get('size', 0)
            contract = gate_order.get('contract', '')
            
            if trigger_price and initial_size and contract:
                # 간단한 해시 생성
                hash_str = f"{contract}_{trigger_price}_{abs(int(initial_size))}"
                return hash_str
            
            return None
            
        except Exception as e:
            self.logger.debug(f"게이트 주문 해시 생성 실패: {e}")
            return None

    def _generate_order_hash(self, trigger_price: float, size: int, contract: str = None) -> str:
        """주문 특성으로 해시 생성 (중복 방지용)"""
        contract = contract or self.GATE_CONTRACT
        return f"{contract}_{trigger_price:.2f}_{abs(size)}"

    async def _extract_tp_sl_from_bitget_order(self, bitget_order: Dict) -> Tuple[Optional[float], Optional[float]]:
        """🔥 비트겟 예약 주문에서 TP/SL 정보 추출"""
        try:
            tp_price = None
            sl_price = None
            
            # TP 가격 추출
            tp_fields = [
                'presetStopSurplusPrice',
                'stopSurplusPrice', 
                'takeProfitPrice',
                'tpPrice'
            ]
            
            for field in tp_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        tp_price = float(value)
                        if tp_price > 0:
                            self.logger.info(f"🎯 TP 가격 추출: {field} = {tp_price}")
                            break
                    except:
                        continue
            
            # SL 가격 추출
            sl_fields = [
                'presetStopLossPrice',
                'stopLossPrice',
                'stopPrice',
                'slPrice'
            ]
            
            for field in sl_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        sl_price = float(value)
                        if sl_price > 0:
                            self.logger.info(f"🛡️ SL 가격 추출: {field} = {sl_price}")
                            break
                    except:
                        continue
            
            return tp_price, sl_price
            
        except Exception as e:
            self.logger.error(f"TP/SL 정보 추출 실패: {e}")
            return None, None

    async def _should_skip_position_due_to_existing(self, bitget_position: Dict) -> bool:
        """🔥 렌더 재구동 시 기존 포지션 때문에 스킵해야 하는지 판단"""
        try:
            if not self.render_restart_detected:
                return False
            
            position_side = bitget_position.get('holdSide', '').lower()
            position_size = float(bitget_position.get('total', 0))
            
            if position_side == 'long' and self.existing_gate_positions['has_long']:
                existing_size = self.existing_gate_positions['long_size']
                # 크기가 유사하면 동일한 포지션으로 판단
                size_diff_percent = abs(position_size - existing_size) / max(position_size, existing_size) * 100
                if size_diff_percent < 20:  # 20% 이하 차이면 동일 포지션으로 판단
                    self.logger.info(f"🔄 렌더 재구동: 동일한 롱 포지션 감지, 복제 스킵 (비트겟: {position_size}, 게이트: {existing_size})")
                    self.daily_stats['render_restart_skips'] += 1
                    return True
            
            elif position_side == 'short' and self.existing_gate_positions['has_short']:
                existing_size = self.existing_gate_positions['short_size']
                size_diff_percent = abs(position_size - existing_size) / max(position_size, existing_size) * 100
                if size_diff_percent < 20:
                    self.logger.info(f"🔄 렌더 재구동: 동일한 숏 포지션 감지, 복제 스킵 (비트겟: {position_size}, 게이트: {existing_size})")
                    self.daily_stats['render_restart_skips'] += 1
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"기존 포지션 스킵 판단 실패: {e}")
            return False

    async def _calculate_dynamic_margin_ratio(self, size: float, trigger_price: float, bitget_order: Dict) -> Dict:
        """실제 달러 마진 비율 동적 계산"""
        try:
            # 레버리지 정보 추출
            bitget_leverage = 10  # 기본값
            
            order_leverage = bitget_order.get('leverage')
            if order_leverage:
                try:
                    bitget_leverage = int(float(order_leverage))
                except:
                    pass
            
            # 계정 정보에서 레버리지 추출
            if not order_leverage:
                try:
                    bitget_account = await self.bitget.get_account_info()
                    account_leverage = bitget_account.get('crossMarginLeverage')
                    if account_leverage:
                        bitget_leverage = int(float(account_leverage))
                except Exception as e:
                    self.logger.warning(f"계정 레버리지 조회 실패: {e}")
            
            # 비트겟 계정 정보 조회
            bitget_account = await self.bitget.get_account_info()
            bitget_total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            # 비트겟에서 이 주문이 체결될 때 사용할 실제 마진 계산
            bitget_notional_value = size * trigger_price
            bitget_required_margin = bitget_notional_value / bitget_leverage
            
            # 비트겟 총 자산 대비 실제 마진 투입 비율 계산
            if bitget_total_equity > 0:
                margin_ratio = bitget_required_margin / bitget_total_equity
            else:
                return {
                    'success': False,
                    'error': '비트겟 총 자산이 0이거나 음수입니다.'
                }
            
            return {
                'success': True,
                'margin_ratio': margin_ratio,
                'leverage': bitget_leverage,
                'required_margin': bitget_required_margin,
                'total_equity': bitget_total_equity,
                'notional_value': bitget_notional_value
            }
            
        except Exception as e:
            self.logger.error(f"실제 달러 마진 비율 동적 계산 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def monitor_order_fills(self):
        """실시간 주문 체결 감지"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                filled_orders = await self.bitget.get_recent_filled_orders(
                    symbol=self.SYMBOL, 
                    minutes=1
                )
                
                for order in filled_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if not order_id or order_id in self.processed_orders:
                        continue
                    
                    reduce_only = order.get('reduceOnly', 'false')
                    if reduce_only == 'true' or reduce_only is True:
                        continue
                    
                    await self._process_filled_order(order)
                    self.processed_orders.add(order_id)
                
                # 오래된 주문 ID 정리
                if len(self.processed_orders) > 1000:
                    recent_orders = list(self.processed_orders)[-500:]
                    self.processed_orders = set(recent_orders)
                
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

    async def _process_filled_order(self, order: Dict):
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
                'marginSize': '0',  # 임시값
                'leverage': '10',  # 임시값
                'marginMode': 'crossed',
                'unrealizedPL': '0'
            }
            
            if await self._should_skip_position_due_to_existing(synthetic_position):
                self.logger.info(f"🔄 렌더 재구동: 동일 포지션 존재로 주문 체결 미러링 스킵 - {order_id}")
                return
            
            # 체결된 주문의 실제 달러 마진 비율 동적 계산
            margin_ratio_result = await self._calculate_dynamic_margin_ratio_for_filled_order(
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
                self.mirrored_positions[pos_id] = await self._create_position_info(synthetic_position)
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

    async def _calculate_dynamic_margin_ratio_for_filled_order(self, size: float, fill_price: float, order: Dict) -> Dict:
        """체결된 주문의 실제 달러 마진 비율 동적 계산"""
        try:
            leverage = 10
            try:
                order_leverage = order.get('leverage')
                if order_leverage:
                    leverage = int(float(order_leverage))
                else:
                    account = await self.bitget.get_account_info()
                    if account:
                        account_leverage = account.get('crossMarginLeverage')
                        if account_leverage:
                            leverage = int(float(account_leverage))
            except Exception as e:
                self.logger.warning(f"체결 주문 레버리지 조회 실패: {e}")
            
            bitget_account = await self.bitget.get_account_info()
            bitget_total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            notional = size * fill_price
            required_margin = notional / leverage
            margin_ratio = required_margin / bitget_total_equity if bitget_total_equity > 0 else 0
            
            return {
                'success': True,
                'margin_ratio': margin_ratio,
                'leverage': leverage,
                'required_margin': required_margin,
                'total_equity': bitget_total_equity,
                'notional_value': notional
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def _record_startup_positions(self):
        """시작 시 존재하는 포지션 기록"""
        try:
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    pos_id = self._generate_position_id(pos)
                    self.startup_positions.add(pos_id)
                    self.position_sizes[pos_id] = float(pos.get('total', 0))
                    
                    # 상세 정보 저장
                    self.startup_positions_detailed[pos_id] = {
                        'size': float(pos.get('total', 0)),
                        'side': pos.get('holdSide', ''),
                        'entry_price': float(pos.get('openPriceAvg', 0)),
                        'margin': float(pos.get('marginSize', 0)),
                        'leverage': pos.get('leverage', 'N/A')
                    }
            
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

    async def _log_account_status(self):
        """계정 상태 로깅"""
        try:
            bitget_account = await self.bitget.get_account_info()
            bitget_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            bitget_leverage = bitget_account.get('crossMarginLeverage', 'N/A')
            
            gate_account = await self.gate.get_account_balance()
            gate_equity = float(gate_account.get('total', 0))
            
            # 시세 차이 정보 추가
            price_diff_text = ""
            if self.price_diff_percent > 0:
                price_diff_text = f"\n시세 차이: {self.price_diff_percent:.2f}% (비트겟: ${self.bitget_current_price:,.2f}, 게이트: ${self.gate_current_price:,.2f})"
            
            # 렌더 재구동 정보 추가
            restart_info = ""
            if self.render_restart_detected:
                restart_info = f"\n🔄 렌더 재구동 감지: 기존 게이트 포지션 있음 (중복 복제 방지 활성화)"
            
            await self.telegram.send_message(
                f"🔄 미러 트레이딩 시스템 시작 (통합 TP/SL 예약주문 복제){restart_info}\n\n"
                f"💰 계정 잔고:\n"
                f"• 비트겟: ${bitget_equity:,.2f} (레버리지: {bitget_leverage}x)\n"
                f"• 게이트: ${gate_equity:,.2f}{price_diff_text}\n\n"
                f"📊 현재 상태:\n"
                f"• 기존 포지션: {len(self.startup_positions)}개 (복제 제외)\n"
                f"• 기존 예약 주문: {len(self.startup_plan_orders)}개\n"
                f"• 게이트 기존 예약 주문: {len(self.gate_existing_order_hashes)}개 (중복 방지)\n"
                f"• 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개\n\n"
                f"⚡ 감지 주기:\n"
                f"• 예약 주문 취소: {self.PLAN_ORDER_CHECK_INTERVAL}초마다\n"
                f"• 주문 체결: {self.ORDER_CHECK_INTERVAL}초마다\n"
                f"• 시세 차이 모니터링: 1분마다\n\n"
                f"🎯 통합 TP/SL 예약주문 복제 기능:\n"
                f"• 비트겟과 동일한 형태로 TP/SL 포함 예약 주문 복제\n"
                f"• 중복 복제 방지 시스템\n"
                f"• 렌더 재구동 시 기존 주문 스킵\n"
                f"• 기존 포지션 중복 방지\n\n"
                f"💡 실제 달러 마진 비율 동적 계산:\n"
                f"매 거래마다 실시간으로 동일한 마진 비율 적용"
            )
            
        except Exception as e:
            self.logger.error(f"계정 상태 조회 실패: {e}")

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
                
                gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
                gate_active = [
                    pos for pos in gate_positions 
                    if pos.get('size', 0) != 0
                ]
                
                # 신규 미러링된 포지션만 카운팅
                new_bitget_positions = []
                for pos in bitget_active:
                    pos_id = self._generate_position_id(pos)
                    if pos_id not in self.startup_positions:
                        new_bitget_positions.append(pos)
                
                # 게이트 포지션에서 시작시 존재했던 포지션 제외
                new_gate_positions_count = len(gate_active) - self.startup_gate_positions_count
                if new_gate_positions_count < 0:
                    new_gate_positions_count = 0
                
                # 실제 포지션 처리
                active_position_ids = set()
                
                for pos in bitget_active:
                    pos_id = self._generate_position_id(pos)
                    active_position_ids.add(pos_id)
                    await self._process_position(pos)
                
                # 종료된 포지션 처리
                closed_positions = set(self.mirrored_positions.keys()) - active_position_ids
                for pos_id in closed_positions:
                    if pos_id not in self.startup_positions:
                        await self._handle_position_close(pos_id)
                
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
            bitget_account = await self.bitget.get_account_info()
            gate_account = await self.gate.get_account_balance()
            
            bitget_equity = float(bitget_account.get('accountEquity', 0))
            gate_equity = float(gate_account.get('total', 0))
            
            success_rate = 0
            if self.daily_stats['total_mirrored'] > 0:
                success_rate = (self.daily_stats['successful_mirrors'] / 
                              self.daily_stats['total_mirrored']) * 100
            
            # 예약 주문 취소 통계
            cancel_success_rate = 0
            total_cancels = self.daily_stats['plan_order_cancel_success'] + self.daily_stats['plan_order_cancel_failed']
            if total_cancels > 0:
                cancel_success_rate = (self.daily_stats['plan_order_cancel_success'] / total_cancels) * 100
            
            # 통합 TP/SL 복제 통계
            tp_sl_stats = f"""
🎯 통합 TP/SL 복제 통계:
- 통합 TP/SL 주문: {self.daily_stats['unified_tp_sl_orders']}회
- TP/SL 복제 성공: {self.daily_stats['tp_sl_mirrors_success']}회
- TP/SL 복제 실패: {self.daily_stats['tp_sl_mirrors_failed']}회
- TP만 복제: {self.daily_stats['tp_only_mirrors']}회
- SL만 복제: {self.daily_stats['sl_only_mirrors']}회
- TP+SL 복제: {self.daily_stats['tp_sl_both_mirrors']}회"""
            
            # 현재 시세 차이 정보 추가
            await self._update_current_prices()
            price_diff_text = ""
            if self.price_diff_percent > 0:
                price_diff_text = f"""

시세 차이:
- 비트겟: ${self.bitget_current_price:,.2f}
- 게이트: ${self.gate_current_price:,.2f}
- 차이: {self.price_diff_percent:.2f}%
- 가격 조정: {self.daily_stats['price_adjustments']}회"""
            
            # 렌더 재구동 관련 통계
            restart_stats = ""
            if self.daily_stats['render_restart_skips'] > 0:
                restart_stats = f"""

🔄 렌더 재구동 대응:
- 중복 포지션 스킵: {self.daily_stats['render_restart_skips']}회"""
            
            report = f"""📊 미러 트레이딩 일일 리포트
📅 {datetime.now().strftime('%Y-%m-%d')}
━━━━━━━━━━━━━━━━━━━

⚡ 실시간 포지션 미러링
- 주문 체결 기반: {self.daily_stats['order_mirrors']}회
- 포지션 기반: {self.daily_stats['position_mirrors']}회
- 총 시도: {self.daily_stats['total_mirrored']}회
- 성공: {self.daily_stats['successful_mirrors']}회
- 실패: {self.daily_stats['failed_mirrors']}회
- 성공률: {success_rate:.1f}%

🔄 예약 주문 미러링
- 시작 시 예약 주문 복제: {self.daily_stats['startup_plan_mirrors']}회
- 신규 예약 주문 미러링: {self.daily_stats['plan_order_mirrors']}회
- 예약 주문 취소 동기화: {self.daily_stats['plan_order_cancels']}회
- 취소 성공률: {cancel_success_rate:.1f}%
- 중복 방지: {self.daily_stats['duplicate_orders_prevented']}회
- 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개{tp_sl_stats}{restart_stats}

📉 포지션 관리
- 부분 청산: {self.daily_stats['partial_closes']}회
- 전체 청산: {self.daily_stats['full_closes']}회
- 총 거래량: ${self.daily_stats['total_volume']:,.2f}

💰 계정 잔고
- 비트겟: ${bitget_equity:,.2f}
- 게이트: ${gate_equity:,.2f}

🔄 현재 미러링 상태
- 활성 포지션: {len(self.mirrored_positions)}개
- 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개
- 실패 기록: {len(self.failed_mirrors)}건{price_diff_text}

━━━━━━━━━━━━━━━━━━━
🎯 통합 TP/SL 예약주문 복제 + 렌더 재구동 대응 + 실제 달러 마진 비율 동적 계산"""
            
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
            'plan_order_skipped_already_mirrored': 0,
            'plan_order_skipped_trigger_price': 0,
            'price_adjustments': 0,
            'sync_tolerance_used': 0,
            'sync_warnings_suppressed': 0,
            'position_size_differences_ignored': 0,
            'cancel_verification_success': 0,
            'cancel_verification_failed': 0,
            'tp_sl_mirrors_success': 0,
            'tp_sl_mirrors_failed': 0,
            'tp_only_mirrors': 0,
            'sl_only_mirrors': 0,
            'tp_sl_both_mirrors': 0,
            'duplicate_orders_prevented': 0,
            'render_restart_skips': 0,
            'unified_tp_sl_orders': 0,
            'errors': []
        }
        self.failed_mirrors.clear()

    def _generate_position_id(self, pos: Dict) -> str:
        """포지션 고유 ID 생성"""
        symbol = pos.get('symbol', self.SYMBOL)
        side = pos.get('holdSide', '')
        entry_price = pos.get('openPriceAvg', '')
        return f"{symbol}_{side}_{entry_price}"

    async def _create_position_info(self, bitget_pos: Dict) -> PositionInfo:
        """포지션 정보 객체 생성"""
        return PositionInfo(
            symbol=bitget_pos.get('symbol', self.SYMBOL),
            side=bitget_pos.get('holdSide', '').lower(),
            size=float(bitget_pos.get('total', 0)),
            entry_price=float(bitget_pos.get('openPriceAvg', 0)),
            margin=float(bitget_pos.get('marginSize', 0)),
            leverage=int(float(bitget_pos.get('leverage', 1))),
            mode='cross' if bitget_pos.get('marginMode') == 'crossed' else 'isolated',
            unrealized_pnl=float(bitget_pos.get('unrealizedPL', 0))
        )

    async def stop(self):
        """미러 트레이딩 중지"""
        self.monitoring = False
        
        try:
            final_report = await self._create_daily_report()
            await self.telegram.send_message(f"🛑 미러 트레이딩 시스템 종료\n\n{final_report}")
        except:
            pass
        
        self.logger.info("미러 트레이딩 시스템 중지")

    async def _create_initial_plan_order_snapshot(self):
        """예약 주문 초기 스냅샷 생성"""
        try:
            self.logger.info("예약 주문 초기 스냅샷 생성 시작")
            
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_orders = plan_orders + tp_sl_orders
            
            # 스냅샷 저장
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

    async def _record_startup_gate_positions(self):
        """시작시 게이트 포지션 수 기록"""
        try:
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            self.startup_gate_positions_count = sum(
                1 for pos in gate_positions 
                if pos.get('size', 0) != 0
            )
            
            self.logger.info(f"시작시 게이트 포지션 수 기록: {self.startup_gate_positions_count}개")
            
        except Exception as e:
            self.logger.error(f"시작시 게이트 포지션 기록 실패: {e}")
            self.startup_gate_positions_count = 0

    async def _update_current_prices(self):
        """양쪽 거래소 현재 시세 업데이트"""
        try:
            # 비트겟 현재가
            bitget_ticker = await self.bitget.get_ticker(self.SYMBOL)
            if bitget_ticker:
                self.bitget_current_price = float(bitget_ticker.get('last', 0))
            
            # 게이트 현재가
            try:
                gate_contract_info = await self.gate.get_contract_info(self.GATE_CONTRACT)
                if 'last_price' in gate_contract_info:
                    self.gate_current_price = float(gate_contract_info['last_price'])
                elif 'mark_price' in gate_contract_info:
                    self.gate_current_price = float(gate_contract_info['mark_price'])
            except:
                # 게이트 가격 조회 실패 시 비트겟 가격 사용
                self.gate_current_price = self.bitget_current_price
            
            # 가격 차이 계산
            if self.bitget_current_price > 0 and self.gate_current_price > 0:
                self.price_diff_percent = abs(self.bitget_current_price - self.gate_current_price) / self.bitget_current_price * 100
            else:
                self.price_diff_percent = 0.0
            
            self.last_price_update = datetime.now()
            
            # 큰 차이 발생 시 로깅
            if self.price_diff_percent > self.MAX_PRICE_DIFF_PERCENT:
                self.logger.warning(f"거래소 간 시세 차이 큼: 비트겟 ${self.bitget_current_price:,.2f}, 게이트 ${self.gate_current_price:,.2f} (차이: {self.price_diff_percent:.2f}%)")
            
        except Exception as e:
            self.logger.error(f"시세 업데이트 실패: {e}")

    async def _record_startup_plan_orders(self):
        """시작 시 존재하는 예약 주문 기록"""
        try:
            self.logger.info("기존 예약 주문 기록 시작")
            
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

    async def _mirror_startup_plan_orders(self):
        """시작 시 기존 예약 주문 복제 - 통합 TP/SL 방식"""
        try:
            self.logger.info("🎯 시작 시 기존 예약 주문 복제 시작 (통합 TP/SL 방식)")
            
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            # TP/SL 주문은 복제하지 않고 일반 예약 주문만 복제
            orders_to_mirror = plan_orders
            
            if not orders_to_mirror:
                self.startup_plan_orders_processed = True
                self.logger.info("복제할 일반 예약 주문이 없습니다.")
                return
            
            mirrored_count = 0
            failed_count = 0
            duplicate_count = 0
            
            for order in orders_to_mirror:
                try:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if not order_id:
                        continue
                    
                    # 포지션이 있을 때만 기존 포지션의 클로즈 TP/SL 제외
                    if self.has_startup_positions and order_id in self.startup_position_tp_sl:
                        continue
                    
                    # 🔥 중복 복제 확인
                    if await self._is_duplicate_order(order):
                        duplicate_count += 1
                        self.processed_plan_orders.add(order_id)
                        continue
                    
                    # 🔥 통합 TP/SL 포함 예약 주문 복제
                    result = await self._process_startup_plan_order_unified(order)
                    
                    if result == "success":
                        mirrored_count += 1
                    else:
                        failed_count += 1
                    
                    self.processed_plan_orders.add(order_id)
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"기존 예약 주문 복제 실패: {order.get('orderId', 'unknown')} - {e}")
                    continue
            
            self.daily_stats['startup_plan_mirrors'] = mirrored_count
            self.daily_stats['duplicate_orders_prevented'] = duplicate_count
            self.startup_plan_orders_processed = True
            
            await self.telegram.send_message(
                f"✅ 시작 시 기존 예약 주문 복제 완료 (통합 TP/SL 방식)\n"
                f"성공: {mirrored_count}개\n"
                f"실패: {failed_count}개\n"
                f"중복 방지: {duplicate_count}개\n"
                f"복제 방식: 통합 TP/SL 예약 주문 (비트겟과 동일한 형태)"
            )
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 복제 처리 실패: {e}")

    async def _is_duplicate_order(self, bitget_order: Dict) -> bool:
        """🔥 중복 주문 확인"""
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
                return False
            
            # 게이트 기준으로 가격 조정
            adjusted_trigger_price = await self._adjust_price_for_gate(original_trigger_price)
            
            # 실제 달러 마진 비율 동적 계산으로 게이트 사이즈 계산
            margin_ratio_result = await self._calculate_dynamic_margin_ratio(
                size, adjusted_trigger_price, bitget_order
            )
            
            if not margin_ratio_result['success']:
                return False
            
            margin_ratio = margin_ratio_result['margin_ratio']
            bitget_leverage = margin_ratio_result['leverage']
            
            gate_account = await self.gate.get_account_balance()
            gate_total_equity = float(gate_account.get('total', 0))
            gate_margin = gate_total_equity * margin_ratio
            gate_notional_value = gate_margin * bitget_leverage
            gate_size = int(gate_notional_value / (adjusted_trigger_price * 0.0001))
            
            if gate_size == 0:
                gate_size = 1
                
            gate_size = await self._calculate_gate_order_size(side, gate_size)
            
            # 해시 생성
            order_hash = self._generate_order_hash(adjusted_trigger_price, gate_size)
            
            if order_hash in self.gate_existing_order_hashes:
                self.logger.info(f"중복 주문 발견 (스킵됨): {bitget_order.get('orderId', 'unknown')} - 해시: {order_hash}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"중복 주문 확인 실패: {e}")
            return False

    async def _process_startup_plan_order_unified(self, bitget_order: Dict) -> str:
        """🔥 시작 시 예약 주문 복제 처리 - 통합 TP/SL 방식"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            size = float(bitget_order.get('size', 0))
            
            # 트리거 가격 추출
            original_trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    original_trigger_price = float(bitget_order.get(price_field))
                    break
            
            if original_trigger_price == 0:
                return "failed"
            
            # 🔥 TP/SL 정보 추출
            tp_price, sl_price = await self._extract_tp_sl_from_bitget_order(bitget_order)
            
            # 현재 시세 업데이트
            await self._update_current_prices()
            
            # 게이트 기준으로 트리거 가격 조정
            adjusted_trigger_price = await self._adjust_price_for_gate(original_trigger_price)
            
            # 트리거 가격 유효성 검증
            is_valid, skip_reason = await self._validate_trigger_price(adjusted_trigger_price, side)
            if not is_valid:
                self.logger.warning(f"시작 시 예약 주문 스킵됨: {order_id} - {skip_reason}")
                return "skipped"
            
            # 실제 달러 마진 비율 동적 계산
            margin_ratio_result = await self._calculate_dynamic_margin_ratio(
                size, adjusted_trigger_price, bitget_order
            )
            
            if not margin_ratio_result['success']:
                return "failed"
            
            margin_ratio = margin_ratio_result['margin_ratio']
            bitget_leverage = margin_ratio_result['leverage']
            
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
            
            # 방향 처리
            gate_size = await self._calculate_gate_order_size(side, gate_size)
            
            # Gate.io 트리거 타입 변환
            gate_trigger_type = await self._determine_gate_trigger_type(adjusted_trigger_price)
            
            # 게이트 레버리지 설정
            try:
                await self.gate.set_leverage(self.GATE_CONTRACT, bitget_leverage)
                await asyncio.sleep(0.3)
            except Exception as e:
                self.logger.error(f"시작 시 레버리지 설정 실패: {e}")
            
            # 🔥 TP/SL 가격 조정 (게이트 기준)
            adjusted_tp_price = None
            adjusted_sl_price = None
            
            if tp_price:
                adjusted_tp_price = await self._adjust_price_for_gate(tp_price)
            if sl_price:
                adjusted_sl_price = await self._adjust_price_for_gate(sl_price)
            
            # 🎯 Gate.io에 통합 TP/SL 포함 예약 주문 생성
            gate_order = await self.gate.create_unified_order_with_tp_sl(
                trigger_type=gate_trigger_type,
                trigger_price=str(adjusted_trigger_price),
                order_type="market",
                contract=self.GATE_CONTRACT,
                size=gate_size,
                tp_price=str(adjusted_tp_price) if adjusted_tp_price else None,
                sl_price=str(adjusted_sl_price) if adjusted_sl_price else None,
                bitget_order_info=bitget_order
            )
            
            # 통계 업데이트
            if gate_order.get('has_tp_sl', False):
                self.daily_stats['unified_tp_sl_orders'] += 1
                self.daily_stats['tp_sl_mirrors_success'] += 1
                
                if adjusted_tp_price and adjusted_sl_price:
                    self.daily_stats['tp_sl_both_mirrors'] += 1
                elif adjusted_tp_price:
                    self.daily_stats['tp_only_mirrors'] += 1
                elif adjusted_sl_price:
                    self.daily_stats['sl_only_mirrors'] += 1
            
            # 🔥 해시 추가하여 중복 방지
            order_hash = self._generate_order_hash(adjusted_trigger_price, gate_size)
            self.gate_existing_order_hashes.add(order_hash)
            
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
                'is_startup_order': True,
                'original_trigger_price': original_trigger_price,
                'adjusted_trigger_price': adjusted_trigger_price,
                'tp_price': tp_price,
                'sl_price': sl_price,
                'adjusted_tp_price': adjusted_tp_price,
                'adjusted_sl_price': adjusted_sl_price,
                'has_tp_sl': gate_order.get('has_tp_sl', False),
                'order_hash': order_hash,
                'unified_order': True  # 통합 주문 표시
            }
            
            return "success"
            
        except Exception as e:
            self.logger.error(f"시작 시 통합 TP/SL 예약 주문 복제 실패: {e}")
            return "failed"

    async def _adjust_price_for_gate(self, price: float) -> float:
        """게이트 기준으로 가격 조정"""
        if price == 0 or self.price_diff_percent <= 0.3:
            return price
        
        if self.bitget_current_price > 0:
            price_ratio = self.gate_current_price / self.bitget_current_price
            adjusted_price = price * price_ratio
            
            # 조정 폭이 너무 크면 원본 사용
            adjustment_percent = abs(adjusted_price - price) / price * 100
            if adjustment_percent <= 2.0:
                return adjusted_price
        
        return price

    async def _validate_trigger_price(self, trigger_price: float, side: str) -> Tuple[bool, str]:
        """트리거 가격 유효성 검증"""
        try:
            current_price = self.gate_current_price or self.bitget_current_price
            
            if current_price == 0:
                return False, "현재 시장가를 조회할 수 없음"
            
            # 트리거가와 현재가가 너무 근접하면 스킵
            price_diff_percent = abs(trigger_price - current_price) / current_price * 100
            if price_diff_percent < 0.01:
                return False, f"트리거가와 현재가 차이가 너무 작음 ({price_diff_percent:.4f}%)"
            
            if trigger_price <= 0:
                return False, "트리거 가격이 0 이하입니다"
            
            # 극단적인 가격 차이 검증
            if price_diff_percent > 100:
                return False, f"트리거가와 현재가 차이가 너무 큼 ({price_diff_percent:.1f}%)"
            
            return True, "유효한 트리거 가격"
            
        except Exception as e:
            self.logger.error(f"트리거 가격 검증 실패: {e}")
            return False, f"검증 오류: {str(e)}"

    async def _calculate_gate_order_size(self, side: str, base_size: int) -> int:
        """게이트 주문 수량 계산"""
        try:
            if side in ['buy', 'open_long']:
                return abs(base_size)
            elif side in ['sell', 'open_short']:
                return -abs(base_size)
            elif side in ['close_long']:
                return -abs(base_size)
            elif side in ['close_short']:
                return abs(base_size)
            else:
                if 'buy' in side.lower():
                    return abs(base_size)
                elif 'sell' in side.lower():
                    return -abs(base_size)
                else:
                    self.logger.warning(f"알 수 없는 주문 방향: {side}, 기본값 사용")
                    return base_size
            
        except Exception as e:
            self.logger.error(f"게이트 주문 수량 계산 실패: {e}")
            return base_size

    async def _determine_gate_trigger_type(self, trigger_price: float) -> str:
        """Gate.io 트리거 타입 결정"""
        try:
            current_price = self.gate_current_price or self.bitget_current_price
            
            if current_price == 0:
                return "ge"
            
            if trigger_price > current_price:
                return "ge"
            else:
                return "le"
                
        except Exception as e:
            self.logger.error(f"Gate.io 트리거 타입 결정 실패: {e}")
            return "ge"

    async def _record_startup_position_tp_sl(self):
        """포지션 유무에 따른 TP/SL 분류"""
        try:
            self.logger.info("포지션 유무에 따른 예약 주문 복제 정책 설정 시작")
            
            # 현재 활성 포지션들 조회
            positions = await self.bitget.get_positions(self.SYMBOL)
            
            active_positions = []
            for pos in positions:
                if float(pos.get('total', 0)) > 0:
                    active_positions.append(pos)
            
            self.has_startup_positions = len(active_positions) > 0
            
            if not self.has_startup_positions:
                # 포지션이 없으면 모든 예약 주문을 복제
                self.startup_position_tp_sl.clear()
            else:
                # 포지션이 있으면 기존 로직대로 클로즈 TP/SL만 제외
                for pos in active_positions:
                    pos_side = pos.get('holdSide', '').lower()
                    
                    # 해당 포지션의 TP/SL 주문들 찾기
                    plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
                    tp_sl_orders = plan_data.get('tp_sl_orders', [])
                    
                    for tp_sl_order in tp_sl_orders:
                        trade_side = tp_sl_order.get('tradeSide', tp_sl_order.get('side', '')).lower()
                        reduce_only = tp_sl_order.get('reduceOnly', False)
                        
                        # 기존 포지션의 클로즈 TP/SL인지 판단
                        is_existing_position_close = False
                        
                        if pos_side == 'long':
                            if (trade_side in ['close_long', 'sell'] and 
                                (reduce_only is True or reduce_only == 'true')):
                                is_existing_position_close = True
                        elif pos_side == 'short':
                            if (trade_side in ['close_short', 'buy'] and 
                                (reduce_only is True or reduce_only == 'true')):
                                is_existing_position_close = True
                        
                        order_id = tp_sl_order.get('orderId', tp_sl_order.get('planOrderId', ''))
                        if order_id and is_existing_position_close:
                            self.startup_position_tp_sl.add(order_id)
            
        except Exception as e:
            self.logger.error(f"포지션 유무에 따른 예약 주문 정책 설정 실패: {e}")
            self.has_startup_positions = False
            self.startup_position_tp_sl.clear()

    async def monitor_plan_orders(self):
        """예약 주문 모니터링 - 통합 TP/SL 복제"""
        self.logger.info("🎯 예약 주문 취소 미러링 모니터링 시작 (통합 TP/SL 복제)")
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                if not self.startup_plan_orders_processed:
                    await asyncio.sleep(0.1)
                    continue
                
                # 현재 비트겟 예약 주문 조회
                plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
                current_plan_orders = plan_data.get('plan_orders', [])
                current_tp_sl_orders = plan_data.get('tp_sl_orders', [])
                
                # 일반 예약 주문만 처리 (TP/SL 주문 제외)
                current_orders_to_monitor = current_plan_orders
                
                # 현재 존재하는 예약주문 ID 집합
                current_order_ids = set()
                current_snapshot = {}
                
                for order in current_orders_to_monitor:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if order_id:
                        current_order_ids.add(order_id)
                        current_snapshot[order_id] = {
                            'order_data': order.copy(),
                            'timestamp': datetime.now().isoformat(),
                            'status': 'active'
                        }
                
                # 취소된 예약 주문 감지 (일반 예약 주문만)
                canceled_order_ids = self.last_plan_order_ids - current_order_ids
                
                # 취소된 주문 처리
                if canceled_order_ids:
                    self.logger.info(f"{len(canceled_order_ids)}개의 예약 주문 취소 감지: {canceled_order_ids}")
                    
                    for canceled_order_id in canceled_order_ids:
                        await self._handle_plan_order_cancel(canceled_order_id)
                    
                    # 통계 업데이트
                    self.daily_stats['plan_order_cancels'] += len(canceled_order_ids)
                
                # 새로운 예약 주문 감지 (일반 예약 주문만)
                new_orders_count = 0
                
                for order in current_orders_to_monitor:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if not order_id:
                        continue
                    
                    # 포지션 유무에 따른 필터링
                    if self.has_startup_positions and order_id in self.startup_position_tp_sl:
                        continue
                    
                    # 이미 처리된 주문은 스킵
                    if order_id in self.processed_plan_orders:
                        continue
                    
                    # 시작 시 존재했던 주문인지 확인
                    if order_id in self.startup_plan_orders:
                        self.processed_plan_orders.add(order_id)
                        continue
                    
                    # 🔥 중복 복제 확인
                    if await self._is_duplicate_order(order):
                        self.daily_stats['duplicate_orders_prevented'] += 1
                        self.processed_plan_orders.add(order_id)
                        continue
                    
                    # 🎯 새로운 예약 주문 감지 - 통합 TP/SL 복제
                    try:
                        result = await self._process_new_plan_order_unified(order)
                        
                        if result == "success":
                            new_orders_count += 1
                        
                        self.processed_plan_orders.add(order_id)
                        
                    except Exception as e:
                        self.logger.error(f"새로운 예약 주문 복제 실패: {order_id} - {e}")
                        self.processed_plan_orders.add(order_id)
                        
                        await self.telegram.send_message(
                            f"❌ 예약 주문 복제 실패 (통합 TP/SL)\n"
                            f"비트겟 ID: {order_id}\n"
                            f"오류: {str(e)[:200]}"
                        )
                
                # 현재 상태를 다음 비교를 위해 저장
                self.last_plan_order_ids = current_order_ids.copy()
                self.plan_order_snapshot = current_snapshot.copy()
                
                # 오래된 주문 ID 정리
                if len(self.processed_plan_orders) > 500:
                    recent_orders = list(self.processed_plan_orders)[-250:]
                    self.processed_plan_orders = set(recent_orders)
                
                consecutive_errors = 0
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"예약 주문 모니터링 중 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 예약 주문 모니터링 시스템 오류\n"
                        f"연속 {consecutive_errors}회 실패\n"
                        f"오류: {str(e)[:200]}"
                    )
                
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL * 2)

    async def _process_new_plan_order_unified(self, bitget_order: Dict) -> str:
        """🔥 새로운 예약 주문 복제 - 통합 TP/SL 방식"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            size = float(bitget_order.get('size', 0))
            
            # 트리거 가격 추출
            original_trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    original_trigger_price = float(bitget_order.get(price_field))
                    break
            
            if original_trigger_price == 0:
                return "failed"
            
            # 🔥 TP/SL 정보 추출
            tp_price, sl_price = await self._extract_tp_sl_from_bitget_order(bitget_order)
            
            # 현재 시세 업데이트
            await self._update_current_prices()
            
            # 게이트 기준으로 트리거 가격 조정
            adjusted_trigger_price = await self._adjust_price_for_gate(original_trigger_price)
            
            # 트리거 가격 유효성 검증
            is_valid, skip_reason = await self._validate_trigger_price(adjusted_trigger_price, side)
            if not is_valid:
                await self.telegram.send_message(
                    f"⏭️ 예약 주문 스킵됨 (트리거 가격 문제)\n"
                    f"비트겟 ID: {order_id}\n"
                    f"방향: {side.upper()}\n"
                    f"원본 트리거가: ${original_trigger_price:,.2f}\n"
                    f"조정 트리거가: ${adjusted_trigger_price:,.2f}\n"
                    f"스킵 사유: {skip_reason}"
                )
                return "skipped"
            
            # 실제 달러 마진 비율 동적 계산
            margin_ratio_result = await self._calculate_dynamic_margin_ratio(
                size, adjusted_trigger_price, bitget_order
            )
            
            if not margin_ratio_result['success']:
                return "failed"
            
            margin_ratio = margin_ratio_result['margin_ratio']
            bitget_leverage = margin_ratio_result['leverage']
            bitget_required_margin = margin_ratio_result['required_margin']
            bitget_total_equity = margin_ratio_result['total_equity']
            
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
            
            # 방향 처리
            gate_size = await self._calculate_gate_order_size(side, gate_size)
            
            # Gate.io 트리거 타입 변환
            gate_trigger_type = await self._determine_gate_trigger_type(adjusted_trigger_price)
            
            # 게이트 레버리지 설정
            try:
                await self.gate.set_leverage(self.GATE_CONTRACT, bitget_leverage)
                await asyncio.sleep(0.3)
            except Exception as e:
                self.logger.error(f"게이트 레버리지 설정 실패: {e}")
            
            # 🔥 TP/SL 가격 조정 (게이트 기준)
            adjusted_tp_price = None
            adjusted_sl_price = None
            
            if tp_price:
                adjusted_tp_price = await self._adjust_price_for_gate(tp_price)
            if sl_price:
                adjusted_sl_price = await self._adjust_price_for_gate(sl_price)
            
            # 🎯 Gate.io에 통합 TP/SL 포함 예약 주문 생성
            gate_order = await self.gate.create_unified_order_with_tp_sl(
                trigger_type=gate_trigger_type,
                trigger_price=str(adjusted_trigger_price),
                order_type="market",
                contract=self.GATE_CONTRACT,
                size=gate_size,
                tp_price=str(adjusted_tp_price) if adjusted_tp_price else None,
                sl_price=str(adjusted_sl_price) if adjusted_sl_price else None,
                bitget_order_info=bitget_order
            )
            
            # 통계 업데이트
            if gate_order.get('has_tp_sl', False):
                self.daily_stats['unified_tp_sl_orders'] += 1
                self.daily_stats['tp_sl_mirrors_success'] += 1
                
                if adjusted_tp_price and adjusted_sl_price:
                    self.daily_stats['tp_sl_both_mirrors'] += 1
                elif adjusted_tp_price:
                    self.daily_stats['tp_only_mirrors'] += 1
                elif adjusted_sl_price:
                    self.daily_stats['sl_only_mirrors'] += 1
            
            # 🔥 해시 추가하여 중복 방지
            order_hash = self._generate_order_hash(adjusted_trigger_price, gate_size)
            self.gate_existing_order_hashes.add(order_hash)
            
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
                'bitget_required_margin': bitget_required_margin,
                'gate_total_equity': gate_total_equity,
                'bitget_total_equity': bitget_total_equity,
                'original_trigger_price': original_trigger_price,
                'adjusted_trigger_price': adjusted_trigger_price,
                'tp_price': tp_price,
                'sl_price': sl_price,
                'adjusted_tp_price': adjusted_tp_price,
                'adjusted_sl_price': adjusted_sl_price,
                'has_tp_sl': gate_order.get('has_tp_sl', False),
                'order_hash': order_hash,
                'unified_order': True  # 통합 주문 표시
            }
            
            self.daily_stats['plan_order_mirrors'] += 1
            
            # 성공 메시지
            tp_sl_info = ""
            if gate_order.get('has_tp_sl', False):
                tp_sl_info = f"\n\n🎯 통합 TP/SL 설정:"
                if adjusted_tp_price:
                    tp_sl_info += f"\n• TP: ${adjusted_tp_price:,.2f}"
                if adjusted_sl_price:
                    tp_sl_info += f"\n• SL: ${adjusted_sl_price:,.2f}"
                tp_sl_info += f"\n• 비트겟과 동일한 형태로 복제됨"
            
            await self.telegram.send_message(
                f"✅ 예약 주문 복제 성공 (통합 TP/SL 방식)\n"
                f"비트겟 ID: {order_id}\n"
                f"게이트 ID: {gate_order.get('id')}\n"
                f"방향: {side.upper()}\n"
                f"트리거가: ${adjusted_trigger_price:,.2f}\n"
                f"트리거 타입: {gate_trigger_type.upper()}\n"
                f"게이트 수량: {gate_size}\n\n"
                f"💰 실제 달러 마진 동적 비율 복제:\n"
                f"비트겟 실제 마진: ${bitget_required_margin:,.2f}\n"
                f"실제 마진 비율: {margin_ratio*100:.2f}%\n"
                f"게이트 투입 마진: ${gate_margin:,.2f} (동일 {margin_ratio*100:.2f}%)\n"
                f"레버리지: {bitget_leverage}x{tp_sl_info}"
            )
            
            return "success"
            
        except Exception as e:
            self.logger.error(f"통합 TP/SL 예약 주문 복제 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'plan_order_id': bitget_order.get('orderId', bitget_order.get('planOrderId', 'unknown'))
            })
            return "failed"

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
            order_hash = mirror_info.get('order_hash')
            is_unified = mirror_info.get('unified_order', False)
            
            if not gate_order_id:
                self.logger.warning(f"게이트 주문 ID가 없음: {bitget_order_id}")
                del self.mirrored_plan_orders[bitget_order_id]
                return
            
            # 재시도 로직으로 확실한 취소 보장
            cancel_success = False
            retry_count = 0
            
            while retry_count < self.max_cancel_retry and not cancel_success:
                try:
                    retry_count += 1
                    self.logger.info(f"게이트 예약 주문 취소 시도 {retry_count}/{self.max_cancel_retry}: {gate_order_id}")
                    
                    # 게이트에서 예약 주문 취소
                    await self.gate.cancel_price_triggered_order(gate_order_id)
                    
                    # 취소 확인을 위해 대기
                    await asyncio.sleep(self.cancel_verification_delay)
                    
                    # 취소 확인
                    verification_success = await self._verify_order_cancellation(gate_order_id)
                    
                    if verification_success:
                        cancel_success = True
                        self.logger.info(f"게이트 예약 주문 취소 확인됨: {gate_order_id}")
                        self.daily_stats['plan_order_cancel_success'] += 1
                        self.daily_stats['cancel_verification_success'] += 1
                        
                        cancel_type = "통합 TP/SL 주문" if is_unified else "일반 예약 주문"
                        
                        await self.telegram.send_message(
                            f"🚫✅ 예약 주문 취소 동기화 완료\n"
                            f"비트겟 ID: {bitget_order_id}\n"
                            f"게이트 ID: {gate_order_id}\n"
                            f"타입: {cancel_type}\n"
                            f"재시도: {retry_count}회"
                        )
                        break
                    else:
                        self.logger.warning(f"취소 시도했지만 주문이 여전히 존재함 (재시도 {retry_count}/{self.max_cancel_retry})")
                        self.daily_stats['cancel_verification_failed'] += 1
                        
                        if retry_count < self.max_cancel_retry:
                            wait_time = min(self.cancel_verification_delay * retry_count, 10.0)
                            await asyncio.sleep(wait_time)
                        
                except Exception as cancel_error:
                    error_msg = str(cancel_error).lower()
                    
                    if any(keyword in error_msg for keyword in ["not found", "order not exist", "invalid order", "order does not exist"]):
                        # 주문이 이미 취소되었거나 체결됨
                        cancel_success = True
                        self.logger.info(f"게이트 예약 주문이 이미 취소/체결됨: {gate_order_id}")
                        self.daily_stats['plan_order_cancel_success'] += 1
                        self.daily_stats['cancel_verification_success'] += 1
                        
                        await self.telegram.send_message(
                            f"🚫✅ 예약 주문 취소 처리 완료\n"
                            f"비트겟 ID: {bitget_order_id}\n"
                            f"게이트 주문이 이미 취소되었거나 체결되었습니다."
                        )
                        break
                    else:
                        self.logger.error(f"게이트 예약 주문 취소 실패 (시도 {retry_count}/{self.max_cancel_retry}): {cancel_error}")
                        
                        if retry_count >= self.max_cancel_retry:
                            # 최종 실패
                            self.daily_stats['plan_order_cancel_failed'] += 1
                            self.daily_stats['cancel_verification_failed'] += 1
                            
                            await self.telegram.send_message(
                                f"❌ 예약 주문 취소 최종 실패\n"
                                f"비트겟 ID: {bitget_order_id}\n"
                                f"게이트 ID: {gate_order_id}\n"
                                f"오류: {str(cancel_error)[:200]}\n"
                                f"재시도: {retry_count}회"
                            )
                        else:
                            wait_time = min(3.0 * retry_count, 15.0)
                            await asyncio.sleep(wait_time)
            
            # 미러링 기록에서 제거 및 해시 제거
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]
                self.logger.info(f"미러링 기록에서 제거됨: {bitget_order_id}")
            
            # 🔥 해시도 제거하여 동일한 주문의 재복제 허용
            if order_hash and order_hash in self.gate_existing_order_hashes:
                self.gate_existing_order_hashes.remove(order_hash)
                self.logger.info(f"주문 해시 제거됨: {order_hash}")
            
        except Exception as e:
            self.logger.error(f"예약 주문 취소 처리 중 예외 발생: {e}")
            
            # 오류 발생 시에도 미러링 기록에서 제거
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]
            
            await self.telegram.send_message(
                f"❌ 예약 주문 취소 처리 중 오류\n"
                f"비트겟 ID: {bitget_order_id}\n"
                f"오류: {str(e)[:200]}"
            )

    async def _verify_order_cancellation(self, gate_order_id: str) -> bool:
        """주문 취소 확인 검증"""
        try:
            # 활성 예약 주문 목록에서 확인
            try:
                gate_orders = await self.gate.get_price_triggered_orders(self.GATE_CONTRACT, "open")
                order_still_exists = any(order.get('id') == gate_order_id for order in gate_orders)
                
                if not order_still_exists:
                    self.logger.info(f"주문이 활성 목록에 없음 - {gate_order_id}")
                    return True
                else:
                    self.logger.warning(f"주문이 여전히 활성 목록에 있음 - {gate_order_id}")
                    return False
                    
            except Exception as e:
                self.logger.debug(f"활성 주문 확인 실패: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"주문 취소 확인 검증 실패: {e}")
            return False

    async def monitor_price_differences(self):
        """거래소 간 시세 차이 모니터링"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                await self._update_current_prices()
                
                # 1시간마다 시세 차이 리포트
                if (datetime.now() - self.last_price_update).total_seconds() > 3600:
                    if self.price_diff_percent > 0.5:  # 0.5% 이상 차이
                        await self.telegram.send_message(
                            f"📊 거래소 간 시세 차이 리포트\n"
                            f"비트겟: ${self.bitget_current_price:,.2f}\n"
                            f"게이트: ${self.gate_current_price:,.2f}\n"
                            f"차이: {self.price_diff_percent:.2f}%\n"
                            f"{'⚠️ 큰 차이 감지' if self.price_diff_percent > self.MAX_PRICE_DIFF_PERCENT else '✅ 정상 범위'}"
                        )
                
                consecutive_errors = 0
                await asyncio.sleep(60)  # 1분마다 체크
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"시세 차이 모니터링 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 시세 차이 모니터링 시스템 오류\n연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(120)  # 오류 시 2분 대기

    async def _process_position(self, bitget_pos: Dict):
        """포지션 처리"""
        try:
            pos_id = self._generate_position_id(bitget_pos)
            
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
                        self.mirrored_positions[pos_id] = await self._create_position_info(bitget_pos)
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
                'position': self._generate_position_id(bitget_pos)
            })

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
                try:
                    await self.gate.set_leverage(self.GATE_CONTRACT, leverage)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    self.logger.error(f"게이트 레버리지 설정 실패: {e}")
                
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
                
                # 진입 주문
                order_result = await self.gate.place_order(
                    contract=self.GATE_CONTRACT,
                    size=gate_size,
                    price=None,
                    reduce_only=False
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

    async def _handle_position_close(self, pos_id: str):
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

    async def monitor_sync_status(self):
        """포지션 동기화 상태 모니터링"""
        sync_retry_count = 0
        
        while self.monitoring:
            try:
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)
                
                # 경고 억제 시간 체크
                now = datetime.now()
                if now < self.sync_warning_suppressed_until:
                    self.logger.debug("동기화 경고 억제 중")
                    continue
                
                bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                bitget_active = [
                    pos for pos in bitget_positions 
                    if float(pos.get('total', 0)) > 0
                ]
                
                gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
                gate_active = [
                    pos for pos in gate_positions 
                    if pos.get('size', 0) != 0
                ]
                
                # 신규 미러링된 포지션만 카운팅
                new_bitget_positions = []
                for pos in bitget_active:
                    pos_id = self._generate_position_id(pos)
                    if pos_id not in self.startup_positions:
                        new_bitget_positions.append(pos)
                
                # 게이트 포지션에서 시작시 존재했던 포지션 제외
                new_gate_positions_count = len(gate_active) - self.startup_gate_positions_count
                if new_gate_positions_count < 0:
                    new_gate_positions_count = 0
                
                # 수정된 동기화 체크
                new_bitget_count = len(new_bitget_positions)
                position_diff = new_bitget_count - new_gate_positions_count
                
                # 포지션 크기 차이는 정상적 현상으로 간주
                if bitget_active and gate_active:
                    self.daily_stats['position_size_differences_ignored'] += 1
                
                # 개선된 동기화 체크 - 허용 오차 적용
                sync_tolerance_met = False
                
                if position_diff != 0:
                    # 최근 체결된 주문이 있는지 확인 (허용 오차 시간 내)
                    recent_orders = []
                    
                    try:
                        recent_bitget_orders = await self.bitget.get_recent_filled_orders(
                            symbol=self.SYMBOL, 
                            minutes=self.SYNC_TOLERANCE_MINUTES
                        )
                        recent_orders.extend(recent_bitget_orders)
                    except:
                        pass
                    
                    # 최근 주문이 있으면 허용 오차 적용
                    if recent_orders:
                        sync_tolerance_met = True
                        sync_retry_count = 0
                        self.daily_stats['sync_tolerance_used'] += 1
                
                # 허용 오차를 초과하거나 지속적인 불일치 시에만 경고
                if not sync_tolerance_met and position_diff != 0:
                    sync_retry_count += 1
                    
                    if sync_retry_count >= self.POSITION_SYNC_RETRY_COUNT:
                        # 시세 차이 정보 포함한 경고
                        await self._update_current_prices()
                        
                        price_diff_info = ""
                        if self.price_diff_percent > 0.5:
                            price_diff_info = f"\n시세 차이: {self.price_diff_percent:.2f}% (비트겟: ${self.bitget_current_price:,.2f}, 게이트: ${self.gate_current_price:,.2f})"
                        
                        # 렌더 재구동 정보 추가
                        restart_info = ""
                        if self.render_restart_detected:
                            restart_info = f"\n🔄 렌더 재구동: 중복 방지 활성화됨 (스킵: {self.daily_stats['render_restart_skips']}회)"
                        
                        await self.telegram.send_message(
                            f"⚠️ 신규 포지션 동기화 불일치 감지\n"
                            f"신규 비트겟: {new_bitget_count}개\n"
                            f"신규 게이트: {new_gate_positions_count}개\n"
                            f"차이: {position_diff}개\n"
                            f"복제된 예약 주문: {len(self.mirrored_plan_orders)}개\n"
                            f"연속 감지: {sync_retry_count}회{price_diff_info}{restart_info}\n\n"
                            f"📊 상세 정보:\n"
                            f"• 전체 비트겟: {len(bitget_active)}개 (시작시: {len(self.startup_positions)}개)\n"
                            f"• 전체 게이트: {len(gate_active)}개 (시작시: {self.startup_gate_positions_count}개)"
                        )
                        
                        sync_retry_count = 0  # 리셋
                else:
                    # 동기화 상태 정상
                    sync_retry_count = 0
                
            except Exception as e:
                self.logger.error(f"동기화 모니터링 오류: {e}")
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)
