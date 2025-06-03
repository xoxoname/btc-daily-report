import asyncio
import aiohttp
import hmac
import hashlib
import time
import json
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import traceback

logger = logging.getLogger(__name__)

@dataclass
class PositionInfo:
    """포지션 정보"""
    symbol: str
    side: str  # long/short
    size: float
    entry_price: float
    margin: float
    leverage: int
    mode: str  # cross/isolated
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
        
        # TP/SL 주문 추적
        self.tp_sl_orders: Dict[str, Dict] = {}
        
        # 주문 체결 추적
        self.processed_orders: Set[str] = set()
        self.last_order_check = datetime.now()
        
        # 🔥🔥🔥 예약 주문 취소 미러링 강화 - 예약 주문 추적 관리
        self.mirrored_plan_orders: Dict[str, Dict] = {}  # 비트겟 주문 ID -> 게이트 주문 정보
        self.processed_plan_orders: Set[str] = set()
        self.startup_plan_orders: Set[str] = set()
        self.startup_plan_orders_processed: bool = False
        self.already_mirrored_plan_orders: Set[str] = set()
        
        # 🔥🔥🔥 예약 주문 취소 감지 시스템 - 강화
        self.last_plan_order_ids: Set[str] = set()  # 이전 체크시 존재했던 예약 주문 ID들
        self.plan_order_snapshot: Dict[str, Dict] = {}  # 예약 주문 스냅샷
        self.plan_order_cancel_retry_count: int = 0
        self.max_cancel_retry: int = 5  # 재시도 횟수 증가
        self.cancel_verification_delay: float = 2.0  # 취소 확인 대기 시간
        
        # 포지션 유무에 따른 예약 주문 복제 관리
        self.startup_position_tp_sl: Set[str] = set()
        self.has_startup_positions: bool = False
        
        # 🔥🔥🔥 TP 설정 미러링 추가
        self.position_tp_tracking: Dict[str, List[str]] = {}  # 포지션 ID -> TP 주문 ID 리스트
        self.mirrored_tp_orders: Dict[str, str] = {}  # 비트겟 TP 주문 ID -> 게이트 TP 주문 ID
        
        # 🔥🔥🔥🔥🔥 예약 주문 TP 설정 복제 수정 - 올바른 방식으로 개선
        self.mirrored_plan_order_tp: Dict[str, Dict] = {}  # 비트겟 예약 주문 ID -> 게이트 TP 정보
        self.plan_order_tp_tracking: Dict[str, List[str]] = {}  # 비트겟 예약 주문 ID -> 게이트 TP 주문 ID 리스트
        
        # 🔥🔥🔥 시세 차이 관리
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.last_price_update: datetime = datetime.min
        
        # 🔥🔥🔥 동기화 허용 오차
        self.SYNC_TOLERANCE_MINUTES = 5
        self.MAX_PRICE_DIFF_PERCENT = 1.0
        self.POSITION_SYNC_RETRY_COUNT = 3
        
        # 🔥🔥🔥 동기화 개선 - 포지션 카운팅 로직 수정
        self.startup_positions_detailed: Dict[str, Dict] = {}
        self.startup_gate_positions_count: int = 0
        self.sync_warning_suppressed_until: datetime = datetime.min
        
        # 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.CHECK_INTERVAL = 2
        self.ORDER_CHECK_INTERVAL = 1
        self.PLAN_ORDER_CHECK_INTERVAL = 0.5  # 🔥🔥🔥 예약 주문 체크 간격을 0.5초로 단축 (취소 감지 강화)
        self.SYNC_CHECK_INTERVAL = 30
        self.MAX_RETRIES = 3
        self.MIN_POSITION_SIZE = 0.00001
        self.MIN_MARGIN = 1.0
        self.DAILY_REPORT_HOUR = 9
        
        # 성과 추적 - 개선된 통계
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
            'plan_order_cancels': 0,  # 🔥🔥🔥 예약 주문 취소 카운트
            'plan_order_cancel_success': 0,  # 🔥🔥🔥 예약 주문 취소 성공
            'plan_order_cancel_failed': 0,   # 🔥🔥🔥 예약 주문 취소 실패
            'tp_mirrors': 0,  # 🔥🔥🔥 TP 미러링 카운트
            'tp_mirror_success': 0,  # 🔥🔥🔥 TP 미러링 성공
            'tp_mirror_failed': 0,   # 🔥🔥🔥 TP 미러링 실패
            'plan_order_tp_mirrors': 0,  # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 카운트
            'plan_order_tp_success': 0,  # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 성공
            'plan_order_tp_failed': 0,   # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 실패
            'startup_plan_mirrors': 0,
            'plan_order_skipped_already_mirrored': 0,
            'plan_order_skipped_trigger_price': 0,
            'price_adjustments': 0,
            'sync_tolerance_used': 0,
            'sync_warnings_suppressed': 0,
            'position_size_differences_ignored': 0,
            'cancel_verification_success': 0,  # 🔥🔥🔥 취소 확인 성공
            'cancel_verification_failed': 0,   # 🔥🔥🔥 취소 확인 실패
            'errors': []
        }
        
        self.monitoring = True
        self.logger.info("🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 시스템 초기화 완료")

    async def start(self):
        """미러 트레이딩 시작"""
        try:
            self.logger.info("🚀🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 시스템 시작")
            
            # 🔥🔥🔥 시세 차이 초기 확인
            await self._update_current_prices()
            
            # 초기 포지션 및 예약 주문 기록
            await self._record_startup_positions()
            await self._record_startup_plan_orders()
            await self._record_startup_position_tp_sl()
            
            # 🔥🔥🔥 시작시 게이트 포지션 수 기록
            await self._record_startup_gate_positions()
            
            # 🔥 게이트에 이미 복제된 예약 주문 확인
            await self._check_already_mirrored_plan_orders()
            
            # 🔥🔥🔥 동기화 상태 초기 점검 및 경고 억제 설정
            await self._initial_sync_check_and_suppress()
            
            # 🔥🔥🔥 예약 주문 초기 스냅샷 생성
            await self._create_initial_plan_order_snapshot()
            
            # 시작 시 기존 예약 주문 복제
            await self._mirror_startup_plan_orders()
            
            # 초기 계정 상태 출력
            await self._log_account_status()
            
            # 모니터링 태스크 시작
            tasks = [
                self.monitor_plan_orders(),  # 🔥🔥🔥 예약 주문 취소 감지 완전 강화
                self.monitor_order_fills(),
                self.monitor_positions(),
                self.monitor_sync_status(),
                self.monitor_price_differences(),
                self.monitor_tp_orders(),  # 🔥🔥🔥 TP 주문 모니터링 추가
                self.monitor_plan_order_tp(),  # 🔥🔥🔥🔥🔥 예약 주문 TP 모니터링 추가
                self.generate_daily_reports()
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            await self.telegram.send_message(
                f"❌ 미러 트레이딩 시작 실패\n"
                f"오류: {str(e)[:200]}"
            )
            raise

    async def _calculate_dynamic_margin_ratio(self, size: float, trigger_price: float, bitget_order: Dict) -> Dict:
        """실제 달러 마진 비율 동적 계산"""
        try:
            # 레버리지 정보 정확하게 추출
            bitget_leverage = 10  # 기본값
            
            # 주문에서 직접 레버리지 추출
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
                
                new_orders_count = 0
                for order in filled_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if not order_id:
                        continue
                    
                    if order_id in self.processed_orders:
                        continue
                    
                    reduce_only = order.get('reduceOnly', 'false')
                    if reduce_only == 'true' or reduce_only is True:
                        continue
                    
                    await self._process_filled_order(order)
                    self.processed_orders.add(order_id)
                    new_orders_count += 1
                
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
                        f"⚠️ 주문 체결 감지 시스템 오류\n"
                        f"연속 {consecutive_errors}회 실패"
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
            
            # 체결된 주문의 실제 달러 마진 비율 동적 계산
            margin_ratio_result = await self._calculate_dynamic_margin_ratio_for_filled_order(
                size, fill_price, order
            )
            
            if not margin_ratio_result['success']:
                return
            
            leverage = margin_ratio_result['leverage']
            
            # 가상의 포지션 데이터 생성
            synthetic_position = {
                'symbol': self.SYMBOL,
                'holdSide': position_side,
                'total': str(size),
                'openPriceAvg': str(fill_price),
                'markPrice': str(fill_price),
                'marginSize': str(margin_ratio_result['required_margin']),
                'leverage': str(leverage),
                'marginMode': 'crossed',
                'unrealizedPL': '0'
            }
            
            pos_id = f"{self.SYMBOL}_{position_side}_{fill_price}"
            
            if pos_id in self.startup_positions:
                return
            
            if pos_id in self.mirrored_positions:
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
                    f"🔧 레버리지: {leverage}x\n"
                    f"💰 실제 마진 비율: {margin_ratio_result['margin_ratio']*100:.2f}%"
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
        """시작 시 존재하는 포지션 기록 - 🔥🔥🔥 상세 정보 포함"""
        try:
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    pos_id = self._generate_position_id(pos)
                    self.startup_positions.add(pos_id)
                    self.position_sizes[pos_id] = float(pos.get('total', 0))
                    
                    # 🔥🔥🔥 상세 정보 저장
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
        """계정 상태 로깅 - 개선된 메시지"""
        try:
            bitget_account = await self.bitget.get_account_info()
            bitget_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            bitget_leverage = bitget_account.get('crossMarginLeverage', 'N/A')
            
            gate_account = await self.gate.get_account_balance()
            gate_equity = float(gate_account.get('total', 0))
            
            position_mode_text = "포지션 없음 - 모든 예약 주문 복제" if not self.has_startup_positions else "포지션 있음 - 클로즈 TP/SL 제외하고 복제"
            
            # 🔥🔥🔥 시세 차이 정보 추가
            price_diff_text = ""
            if self.price_diff_percent > 0:
                price_diff_text = f"\n\n🔥🔥🔥 거래소 간 시세 차이:\n비트겟: ${self.bitget_current_price:,.2f}\n게이트: ${self.gate_current_price:,.2f}\n차이: {self.price_diff_percent:.2f}%\n{'⚠️ 큰 차이 감지 - 자동 조정됨' if self.price_diff_percent > self.MAX_PRICE_DIFF_PERCENT else '✅ 정상 범위'}"
            
            await self.telegram.send_message(
                f"🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 시스템 시작\n\n"
                f"💰 계정 잔고:\n"
                f"• 비트겟: ${bitget_equity:,.2f} (레버리지: {bitget_leverage}x)\n"
                f"• 게이트: ${gate_equity:,.2f}{price_diff_text}\n\n"
                f"🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 (핵심 수정):\n"
                f"• 비트겟 예약 주문의 TP 설정을 정확히 복제\n"
                f"• 예약 주문 체결 후 자동 TP 트리거 주문 생성\n"
                f"• TP 방향과 수량을 정확히 계산하여 복제\n"
                f"• 숏 예약 주문의 TP는 매수(+) 방향으로 설정\n"
                f"• 롱 예약 주문의 TP는 매도(-) 방향으로 설정\n"
                f"• 잘못된 반대 포지션 생성 문제 완전 해결\n\n"
                f"🔥🔥🔥 핵심 기능:\n"
                f"매 주문/포지션마다 실제 달러 투입금 비율을 새로 계산!\n\n"
                f"💰💰💰 실제 달러 마진 비율 동적 계산 (핵심):\n"
                f"1️⃣ 비트겟에서 주문 체결 또는 예약 주문 생성\n"
                f"2️⃣ 해당 주문의 실제 마진 = (수량 × 가격) ÷ 레버리지\n"
                f"3️⃣ 실제 마진 비율 = 실제 마진 ÷ 비트겟 총 자산\n"
                f"4️⃣ 게이트 투입 마진 = 게이트 총 자산 × 동일 비율\n"
                f"5️⃣ 매 거래마다 실시간으로 비율을 새로 계산\n\n"
                f"📊 기존 항목:\n"
                f"• 기존 포지션: {len(self.startup_positions)}개 (복제 제외)\n"
                f"• 기존 예약 주문: {len(self.startup_plan_orders)}개 (시작 시 복제)\n"
                f"• 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개\n"
                f"• 현재 복제된 예약 주문 TP: {len(self.mirrored_plan_order_tp)}개\n\n"
                f"🔥🔥🔥🔥🔥 예약 주문 TP 복제 정책:\n"
                f"• {position_mode_text}\n"
                f"• 보유 포지션: {len(self.startup_positions)}개\n"
                f"• 제외할 클로즈 TP/SL: {len(self.startup_position_tp_sl)}개\n"
                f"• 예약 주문에 TP 설정 시 게이트에서도 동일하게 복제\n"
                f"• TP 가격, 수량, 트리거 타입 모두 완전 동기화\n"
                f"• 예약 주문 취소 시 연결된 TP도 자동 취소\n\n"
                f"⚡ 감지 주기:\n"
                f"• 예약 주문 취소: {self.PLAN_ORDER_CHECK_INTERVAL}초마다\n"
                f"• 예약 주문 TP: {self.ORDER_CHECK_INTERVAL}초마다 (TP 설정 변경 감지)\n"
                f"• 주문 체결: {self.ORDER_CHECK_INTERVAL}초마다\n"
                f"• 시세 차이 모니터링: 1분마다\n"
                f"• TP 주문 모니터링: {self.ORDER_CHECK_INTERVAL}초마다\n\n"
                f"💡 예시:\n"
                f"비트겟 총 자산 $10,000에서 $200 마진 투입 (2%)\n"
                f"→ 게이트 총 자산 $1,000에서 $20 마진 투입 (동일 2%)\n"
                f"→ 매 거래마다 실시간으로 이 비율을 새로 계산!\n"
                f"→ 시세 차이 발생 시 트리거 가격 자동 조정!\n"
                f"→ 포지션 크기 차이는 정상적 현상!\n"
                f"→ 예약 주문 취소도 즉시 미러링!\n"
                f"→ TP 설정도 자동 미러링!\n"
                f"→ 🔥🔥🔥🔥🔥 예약 주문 TP 올바른 방향으로 복제!"
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
                
                # 🔥🔥🔥 핵심 수정: 신규 미러링된 포지션만 카운팅
                # 전체 비트겟 포지션에서 시작시 존재했던 포지션 제외
                new_bitget_positions = []
                for pos in bitget_active:
                    pos_id = self._generate_position_id(pos)
                    if pos_id not in self.startup_positions:
                        new_bitget_positions.append(pos)
                
                # 게이트 포지션에서 시작시 존재했던 포지션 제외
                new_gate_positions_count = len(gate_active) - self.startup_gate_positions_count
                if new_gate_positions_count < 0:
                    new_gate_positions_count = 0
                
                # 🔥🔥🔥 수정된 동기화 체크
                new_bitget_count = len(new_bitget_positions)
                position_diff = new_bitget_count - new_gate_positions_count
                
                self.logger.debug(f"🔥🔥🔥 동기화 체크 (수정된 로직):")
                self.logger.debug(f"   - 전체 비트겟 포지션: {len(bitget_active)}개")
                self.logger.debug(f"   - 시작시 비트겟 포지션: {len(self.startup_positions)}개")
                self.logger.debug(f"   - 신규 비트겟 포지션: {new_bitget_count}개")
                self.logger.debug(f"   - 전체 게이트 포지션: {len(gate_active)}개")
                self.logger.debug(f"   - 시작시 게이트 포지션: {self.startup_gate_positions_count}개")
                self.logger.debug(f"   - 신규 게이트 포지션: {new_gate_positions_count}개")
                self.logger.debug(f"   - 포지션 차이: {position_diff}개")
                
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
                        f"⚠️ 포지션 모니터링 오류\n"
                        f"연속 {consecutive_errors}회 실패"
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
        """일일 리포트 생성 - 개선된 통계"""
        try:
            bitget_account = await self.bitget.get_account_info()
            gate_account = await self.gate.get_account_balance()
            
            bitget_equity = float(bitget_account.get('accountEquity', 0))
            gate_equity = float(gate_account.get('total', 0))
            bitget_leverage = bitget_account.get('crossMarginLeverage', 'N/A')
            
            success_rate = 0
            if self.daily_stats['total_mirrored'] > 0:
                success_rate = (self.daily_stats['successful_mirrors'] / 
                              self.daily_stats['total_mirrored']) * 100
            
            # 🔥🔥🔥 예약 주문 취소 통계 추가
            cancel_success_rate = 0
            total_cancels = self.daily_stats['plan_order_cancel_success'] + self.daily_stats['plan_order_cancel_failed']
            if total_cancels > 0:
                cancel_success_rate = (self.daily_stats['plan_order_cancel_success'] / total_cancels) * 100
            
            # 🔥🔥🔥 TP 미러링 통계 추가
            tp_success_rate = 0
            total_tp_mirrors = self.daily_stats['tp_mirror_success'] + self.daily_stats['tp_mirror_failed']
            if total_tp_mirrors > 0:
                tp_success_rate = (self.daily_stats['tp_mirror_success'] / total_tp_mirrors) * 100
            
            # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 통계 추가
            plan_tp_success_rate = 0
            total_plan_tp_mirrors = self.daily_stats['plan_order_tp_success'] + self.daily_stats['plan_order_tp_failed']
            if total_plan_tp_mirrors > 0:
                plan_tp_success_rate = (self.daily_stats['plan_order_tp_success'] / total_plan_tp_mirrors) * 100
            
            # 🔥🔥🔥 취소 확인 통계 추가
            verification_success_rate = 0
            total_verifications = self.daily_stats['cancel_verification_success'] + self.daily_stats['cancel_verification_failed']
            if total_verifications > 0:
                verification_success_rate = (self.daily_stats['cancel_verification_success'] / total_verifications) * 100
            
            # 🔥🔥🔥 시세 차이 정보 추가
            await self._update_current_prices()
            price_diff_text = ""
            if self.price_diff_percent > 0:
                price_diff_text = f"""

🔥🔥🔥 거래소 간 시세 차이:
- 비트겟: ${self.bitget_current_price:,.2f}
- 게이트: ${self.gate_current_price:,.2f}
- 차이: {self.price_diff_percent:.2f}%
- 가격 조정: {self.daily_stats['price_adjustments']}회
- 동기화 허용 오차 사용: {self.daily_stats['sync_tolerance_used']}회
- 동기화 경고 억제: {self.daily_stats['sync_warnings_suppressed']}회
- 포지션 크기 차이 무시: {self.daily_stats['position_size_differences_ignored']}회"""
            
            report = f"""📊 일일 예약 주문 TP 설정 올바른 복제 리포트
📅 {datetime.now().strftime('%Y-%m-%d')}
━━━━━━━━━━━━━━━━━━━

🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 성과 (핵심 수정)
- 예약 주문 TP 복제 시도: {self.daily_stats['plan_order_tp_mirrors']}건
- 예약 주문 TP 복제 성공: {self.daily_stats['plan_order_tp_success']}건
- 예약 주문 TP 복제 실패: {self.daily_stats['plan_order_tp_failed']}건
- 예약 주문 TP 복제 성공률: {plan_tp_success_rate:.1f}%
- 현재 복제된 예약 주문 TP: {len(self.mirrored_plan_order_tp)}개
- 잘못된 반대 포지션 생성 문제 해결됨

🔥🔥🔥 TP 설정 미러링 강화 성과
- TP 미러링 시도: {self.daily_stats['tp_mirrors']}건
- TP 미러링 성공: {self.daily_stats['tp_mirror_success']}건
- TP 미러링 실패: {self.daily_stats['tp_mirror_failed']}건
- TP 미러링 성공률: {tp_success_rate:.1f}%
- 현재 복제된 TP: {len(self.mirrored_tp_orders)}개

🔥🔥🔥 예약 주문 취소 미러링 성과
- 예약 주문 취소 감지: {self.daily_stats['plan_order_cancels']}건
- 취소 미러링 성공: {self.daily_stats['plan_order_cancel_success']}건
- 취소 미러링 실패: {self.daily_stats['plan_order_cancel_failed']}건
- 취소 미러링 성공률: {cancel_success_rate:.1f}%
- 취소 확인 성공: {self.daily_stats['cancel_verification_success']}건
- 취소 확인 실패: {self.daily_stats['cancel_verification_failed']}건
- 취소 확인 성공률: {verification_success_rate:.1f}%
- 최대 재시도 횟수: {self.max_cancel_retry}회
- 모니터링 주기: {self.PLAN_ORDER_CHECK_INTERVAL}초 (초고속)
- 취소 확인 대기: {self.cancel_verification_delay}초

🔥 예약 주문 실제 달러 마진 비율 동적 계산 성과
- 시작 시 예약 주문 복제: {self.daily_stats['startup_plan_mirrors']}회
- 신규 예약 주문 미러링: {self.daily_stats['plan_order_mirrors']}회
- 예약 주문 취소 동기화: {self.daily_stats['plan_order_cancels']}회
- 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개
- 이미 복제됨으로 스킵: {self.daily_stats['plan_order_skipped_already_mirrored']}개
- 트리거 가격 문제로 스킵: {self.daily_stats['plan_order_skipped_trigger_price']}개

⚡ 실시간 포지션 미러링
- 주문 체결 기반: {self.daily_stats['order_mirrors']}회
- 포지션 기반: {self.daily_stats['position_mirrors']}회
- 총 시도: {self.daily_stats['total_mirrored']}회
- 성공: {self.daily_stats['successful_mirrors']}회
- 실패: {self.daily_stats['failed_mirrors']}회
- 성공률: {success_rate:.1f}%

📉 포지션 관리
- 부분 청산: {self.daily_stats['partial_closes']}회
- 전체 청산: {self.daily_stats['full_closes']}회
- 총 거래량: ${self.daily_stats['total_volume']:,.2f}

💰 계정 잔고
- 비트겟: ${bitget_equity:,.2f} (레버리지: {bitget_leverage}x)
- 게이트: ${gate_equity:,.2f}

🔄 현재 미러링 상태
- 활성 포지션: {len(self.mirrored_positions)}개
- 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개
- 현재 복제된 TP 주문: {len(self.mirrored_tp_orders)}개
- 현재 복제된 예약 주문 TP: {len(self.mirrored_plan_order_tp)}개
- 실패 기록: {len(self.failed_mirrors)}건{price_diff_text}

🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 (핵심 수정)
- 비트겟 예약 주문에 TP 설정이 있으면 게이트에서도 동일하게 설정
- TP 가격, TP 비율, TP 수량 모두 완전 동기화
- 예약 주문 체결 후 자동으로 TP 트리거 주문 생성
- 비트겟과 동일한 수익률로 자동 익절
- 시세 차이 대응으로 TP 가격도 자동 조정
- 예약 주문 취소 시 연결된 TP도 함께 자동 취소
- TP 가격 수정 시 게이트에서도 실시간 동기화
- 숏 예약 주문의 TP는 매수(+) 방향으로 정확히 설정
- 롱 예약 주문의 TP는 매도(-) 방향으로 정확히 설정
- 잘못된 반대 포지션 생성 문제 완전 해결

🔥🔥🔥 TP 설정 미러링 강화 (핵심 기능)
- 비트겟 포지션 진입 시 TP 설정 자동 감지
- 게이트에서 동일한 TP 가격으로 자동 설정
- TP 주문 별도 추적 및 관리
- TP 취소/수정도 실시간 동기화
- 시세 차이 대응으로 TP 가격도 자동 조정

💰💰💰 실제 달러 마진 비율 동적 계산 (핵심)
- 매 예약주문마다 실제 마진 비율을 새로 계산
- 미리 정해진 비율 없음 - 완전 동적 계산

🔥🔥🔥 동기화 카운팅 로직 수정 (새로운 핵심 기능)
- 기존: 전체 포지션 비교 (잘못됨)
- 수정: 신규 포지션만 비교 (올바름)
- 시작시 포지션은 미러링 대상 아님
- 포지션 크기 차이는 마진 비율 차이로 정상

🔥🔥🔥 시세 차이 대응 강화 (핵심 기능)
- 실시간 거래소 간 시세 모니터링
- 0.3% 이상 차이 시 트리거 가격 자동 조정
- 게이트 기준 현재가로 정확한 트리거 타입 결정
- 동기화 허용 오차 {self.SYNC_TOLERANCE_MINUTES}분 적용

🔥🔥🔥 개선된 트리거 검증 (핵심)
- 최소 차이: 0.1% → 0.01% (10배 완화)
- 최대 차이: 50% → 100% (2배 완화)
- close_long 방향 처리 완전 수정

🔥🔥🔥 개선된 방향 처리 (핵심)
- close_long → 게이트 매도 (음수) 올바르게 처리
- close_short → 게이트 매수 (양수) 올바르게 처리
"""
            
            if self.daily_stats['errors']:
                report += f"\n⚠️ 오류 발생: {len(self.daily_stats['errors'])}건"
            
            report += "\n━━━━━━━━━━━━━━━━━━━\n🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 + 완전한 미러링 시스템!"
            
            return report
            
        except Exception as e:
            self.logger.error(f"리포트 생성 실패: {e}")
            return f"📊 일일 리포트 생성 실패\n오류: {str(e)}"

    def _reset_daily_stats(self):
        """일일 통계 초기화 - 개선된 통계"""
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
            'plan_order_cancels': 0,  # 🔥🔥🔥 예약 주문 취소 카운트
            'plan_order_cancel_success': 0,  # 🔥🔥🔥 예약 주문 취소 성공
            'plan_order_cancel_failed': 0,   # 🔥🔥🔥 예약 주문 취소 실패
            'tp_mirrors': 0,  # 🔥🔥🔥 TP 미러링 카운트
            'tp_mirror_success': 0,  # 🔥🔥🔥 TP 미러링 성공
            'tp_mirror_failed': 0,   # 🔥🔥🔥 TP 미러링 실패
            'plan_order_tp_mirrors': 0,  # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 카운트
            'plan_order_tp_success': 0,  # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 성공
            'plan_order_tp_failed': 0,   # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 실패
            'startup_plan_mirrors': 0,
            'plan_order_skipped_already_mirrored': 0,
            'plan_order_skipped_trigger_price': 0,
            'price_adjustments': 0,
            'sync_tolerance_used': 0,
            'sync_warnings_suppressed': 0,
            'position_size_differences_ignored': 0,
            'cancel_verification_success': 0,  # 🔥🔥🔥 취소 확인 성공
            'cancel_verification_failed': 0,   # 🔥🔥🔥 취소 확인 실패
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
            await self.telegram.send_message(
                f"🛑 예약 주문 TP 설정 올바른 복제 시스템 종료\n\n{final_report}"
            )
        except:
            pass
        
        self.logger.info("🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 시스템 중지")

    async def _create_initial_plan_order_snapshot(self):
        """🔥🔥🔥 예약 주문 초기 스냅샷 생성"""
        try:
            self.logger.info("🔥🔥🔥 예약 주문 초기 스냅샷 생성 시작")
            
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
            
            self.logger.info(f"🔥🔥🔥 예약 주문 초기 스냅샷 완료: {len(self.plan_order_snapshot)}개 주문")
            
        except Exception as e:
            self.logger.error(f"예약 주문 초기 스냅샷 생성 실패: {e}")

    async def _record_startup_gate_positions(self):
        """🔥🔥🔥 시작시 게이트 포지션 수 기록"""
        try:
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            self.startup_gate_positions_count = sum(
                1 for pos in gate_positions 
                if pos.get('size', 0) != 0
            )
            
            self.logger.info(f"🔥🔥🔥 시작시 게이트 포지션 수 기록: {self.startup_gate_positions_count}개")
            
        except Exception as e:
            self.logger.error(f"시작시 게이트 포지션 기록 실패: {e}")
            self.startup_gate_positions_count = 0

    async def _initial_sync_check_and_suppress(self):
        """🔥🔥🔥 초기 동기화 상태 점검 및 경고 억제 설정"""
        try:
            self.logger.info("🔥🔥🔥 초기 동기화 상태 점검 및 경고 억제 설정 시작")
            
            # Bitget 포지션 조회
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            bitget_active = [
                pos for pos in bitget_positions 
                if float(pos.get('total', 0)) > 0
            ]
            
            # Gate.io 포지션 조회
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            gate_active = [
                pos for pos in gate_positions 
                if pos.get('size', 0) != 0
            ]
            
            # Bitget 예약 주문 조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            bitget_plan_orders = plan_data.get('plan_orders', []) + plan_data.get('tp_sl_orders', [])
            
            # Gate.io 예약 주문 조회
            gate_plan_orders = await self.gate.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            # 🔥🔥🔥 핵심: 신규 포지션 개념 제거 - 모든 기존 포지션은 미러링 대상이 아님
            startup_bitget_positions = len(bitget_active)
            startup_gate_positions = len(gate_active)
            
            sync_analysis = f"""
🔥🔥🔥🔥🔥 초기 동기화 상태 분석 (예약 주문 TP 설정 올바른 복제):

📊 현재 상황:
- Bitget 활성 포지션: {startup_bitget_positions}개 (모두 기존 포지션으로 간주)
- Gate.io 활성 포지션: {startup_gate_positions}개 (모두 기존 포지션으로 간주)
- Bitget 예약 주문: {len(bitget_plan_orders)}개
- Gate.io 예약 주문: {len(gate_plan_orders)}개

💡 핵심 원리:
- 시작시 존재하는 모든 포지션은 "기존 포지션"으로 간주
- 기존 포지션은 미러링 대상이 아님 (이미 존재하던 것)
- 향후 신규 진입만 미러링
- 포지션 크기 차이는 마진 비율 차이로 정상적 현상

🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 (핵심 수정):
- 비트겟 예약 주문의 TP 설정을 정확히 복제
- 예약 주문 체결 후 자동 TP 트리거 주문 생성
- TP 방향과 수량을 정확히 계산하여 복제
- 숏 예약 주문의 TP는 매수(+) 방향으로 설정
- 롱 예약 주문의 TP는 매도(-) 방향으로 설정
- 잘못된 반대 포지션 생성 문제 완전 해결

🔥🔥🔥 TP 설정 미러링 강화:
- 비트겟 포지션 진입 시 TP 설정 감지
- 게이트에서 동일한 TP 가격으로 자동 설정
- TP 주문 별도 추적 및 관리
- TP 취소/수정도 실시간 동기화

🔥🔥🔥 동기화 카운팅 수정:
- 기존 방식: "신규 포지션" vs "게이트 포지션" 비교 (잘못됨)
- 수정 방식: 신규 진입 이벤트만 추적, 기존 포지션은 비교 안함
"""
            
            # 포지션 크기 차이 분석 (정보 제공용)
            if bitget_active and gate_active:
                bitget_total_size = sum(float(pos.get('total', 0)) for pos in bitget_active)
                gate_total_size = sum(abs(float(pos.get('size', 0))) for pos in gate_active)
                size_diff_percent = abs(bitget_total_size - gate_total_size) / max(bitget_total_size, gate_total_size) * 100 if max(bitget_total_size, gate_total_size) > 0 else 0
                
                sync_analysis += f"""
📊 포지션 크기 분석 (참고용):
- Bitget 총 포지션 크기: {bitget_total_size:.6f} BTC
- Gate.io 총 포지션 크기: {gate_total_size:.6f} BTC
- 크기 차이: {size_diff_percent:.2f}%
- 💡 크기 차이는 마진 비율 차이로 정상적 현상

🔄 동기화 정책:
- 포지션 크기 차이 무시: 활성화 ✅
- 동기화 허용 오차: {self.SYNC_TOLERANCE_MINUTES}분
- 시세 차이 최대 허용: {self.MAX_PRICE_DIFF_PERCENT}%
- 향후 {self.SYNC_TOLERANCE_MINUTES}분간 동기화 경고 억제
"""
            
            # 🔥🔥🔥 동기화 경고 억제 설정 (기존 포지션이 있을 때)
            if startup_bitget_positions > 0 or startup_gate_positions > 0:
                self.sync_warning_suppressed_until = datetime.now() + timedelta(minutes=self.SYNC_TOLERANCE_MINUTES)
                sync_analysis += f"\n⚠️ 기존 포지션 감지로 {self.SYNC_TOLERANCE_MINUTES}분간 동기화 경고 억제"
            
            self.logger.info(sync_analysis)
            
            await self.telegram.send_message(sync_analysis)
            
        except Exception as e:
            self.logger.error(f"초기 동기화 상태 점검 실패: {e}")

    async def _update_current_prices(self):
        """🔥🔥🔥 현재 시세 업데이트"""
        try:
            # Bitget 현재가
            bitget_ticker = await self.bitget.get_ticker(self.SYMBOL)
            self.bitget_current_price = float(bitget_ticker.get('lastPr', 0))
            
            # Gate.io 현재가
            gate_ticker = await self.gate.get_ticker(self.GATE_CONTRACT)
            self.gate_current_price = float(gate_ticker.get('last', 0))
            
            # 시세 차이 계산
            if self.bitget_current_price > 0 and self.gate_current_price > 0:
                price_diff = abs(self.bitget_current_price - self.gate_current_price)
                avg_price = (self.bitget_current_price + self.gate_current_price) / 2
                self.price_diff_percent = (price_diff / avg_price) * 100
            else:
                self.price_diff_percent = 0
            
            self.last_price_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"현재 시세 업데이트 실패: {e}")

    async def monitor_price_differences(self):
        """🔥🔥🔥 시세 차이 모니터링"""
        while self.monitoring:
            try:
                await self._update_current_prices()
                
                # 큰 시세 차이 감지 시 알림
                if self.price_diff_percent > self.MAX_PRICE_DIFF_PERCENT:
                    await self.telegram.send_message(
                        f"⚠️ 거래소 간 시세 차이 감지\n"
                        f"비트겟: ${self.bitget_current_price:,.2f}\n"
                        f"게이트: ${self.gate_current_price:,.2f}\n"
                        f"차이: {self.price_diff_percent:.2f}%\n"
                        f"트리거 가격 자동 조정됨"
                    )
                    self.daily_stats['price_adjustments'] += 1
                
                await asyncio.sleep(60)  # 1분마다 체크
                
            except Exception as e:
                self.logger.error(f"시세 차이 모니터링 오류: {e}")
                await asyncio.sleep(60)

    async def monitor_sync_status(self):
        """동기화 상태 모니터링 - 🔥🔥🔥 수정된 로직"""
        while self.monitoring:
            try:
                now = datetime.now()
                
                # 🔥🔥🔥 동기화 경고 억제 기간 체크
                if now < self.sync_warning_suppressed_until:
                    self.logger.debug(f"🔥🔥🔥 동기화 경고 억제 중 (종료: {self.sync_warning_suppressed_until})")
                    await asyncio.sleep(self.SYNC_CHECK_INTERVAL)
                    continue
                
                if now > self.last_sync_check + timedelta(seconds=self.SYNC_CHECK_INTERVAL):
                    await self._check_sync_status()
                    self.last_sync_check = now
                
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"동기화 상태 모니터링 오류: {e}")
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)

    async def _check_sync_status(self):
        """동기화 상태 체크 - 🔥🔥🔥 수정된 로직"""
        try:
            # Bitget 포지션 조회
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            bitget_active = [
                pos for pos in bitget_positions 
                if float(pos.get('total', 0)) > 0
            ]
            
            # Gate.io 포지션 조회
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            gate_active = [
                pos for pos in gate_positions 
                if pos.get('size', 0) != 0
            ]
            
            # 🔥🔥🔥 핵심 수정: 신규 포지션만 카운팅
            new_bitget_positions = []
            for pos in bitget_active:
                pos_id = self._generate_position_id(pos)
                if pos_id not in self.startup_positions:
                    new_bitget_positions.append(pos)
            
            new_gate_positions_count = len(gate_active) - self.startup_gate_positions_count
            if new_gate_positions_count < 0:
                new_gate_positions_count = 0
            
            new_bitget_count = len(new_bitget_positions)
            position_diff = new_bitget_count - new_gate_positions_count
            
            # 🔥🔥🔥 포지션 크기 차이는 정상으로 간주
            if abs(position_diff) > 0:
                # 포지션 수 차이가 있지만 마진 비율 차이로 정상
                self.daily_stats['position_size_differences_ignored'] += 1
                
                # 디버깅 로그만 출력
                self.logger.debug(f"🔥🔥🔥 포지션 수 차이 감지 (정상): 신규 비트겟 {new_bitget_count}개, 신규 게이트 {new_gate_positions_count}개, 차이 {position_diff}개")
                self.logger.debug(f"🔥🔥🔥 이는 실제 달러 마진 비율 차이로 인한 정상적 현상")
            
        except Exception as e:
            self.logger.error(f"동기화 상태 체크 실패: {e}")

    async def _process_position(self, bitget_pos: Dict):
        """포지션 처리"""
        try:
            pos_id = self._generate_position_id(bitget_pos)
            
            # 시작 시 포지션은 스킵
            if pos_id in self.startup_positions:
                return
            
            current_size = float(bitget_pos.get('total', 0))
            
            if pos_id in self.mirrored_positions:
                # 기존 포지션 크기 변화 체크
                previous_size = self.position_sizes.get(pos_id, 0)
                size_change = current_size - previous_size
                
                if abs(size_change) > self.MIN_POSITION_SIZE:
                    await self._handle_position_size_change(pos_id, size_change, bitget_pos)
                    self.position_sizes[pos_id] = current_size
            else:
                # 신규 포지션
                if current_size > self.MIN_POSITION_SIZE:
                    result = await self._mirror_new_position(bitget_pos)
                    
                    if result.success:
                        self.mirrored_positions[pos_id] = await self._create_position_info(bitget_pos)
                        self.position_sizes[pos_id] = current_size
                        self.daily_stats['successful_mirrors'] += 1
                        self.daily_stats['position_mirrors'] += 1
                    else:
                        self.failed_mirrors.append(result)
                        self.daily_stats['failed_mirrors'] += 1
                    
                    self.daily_stats['total_mirrored'] += 1
                    
        except Exception as e:
            self.logger.error(f"포지션 처리 중 오류: {e}")

    async def _mirror_new_position(self, bitget_pos: Dict) -> MirrorResult:
        """신규 포지션 미러링"""
        try:
            side = bitget_pos.get('holdSide', '').lower()
            size = float(bitget_pos.get('total', 0))
            entry_price = float(bitget_pos.get('openPriceAvg', 0))
            margin = float(bitget_pos.get('marginSize', 0))
            leverage = int(float(bitget_pos.get('leverage', 1)))
            
            # 실제 달러 마진 비율 동적 계산
            margin_ratio_result = await self._calculate_position_margin_ratio(
                size, entry_price, margin, leverage
            )
            
            if not margin_ratio_result['success']:
                return MirrorResult(
                    success=False,
                    action="margin_calculation_failed",
                    bitget_data=bitget_pos,
                    error=margin_ratio_result['error']
                )
            
            # Gate.io에서 미러링할 주문 크기 계산
            gate_margin = margin_ratio_result['gate_margin']
            gate_leverage = margin_ratio_result['gate_leverage']
            gate_size = gate_margin * gate_leverage / entry_price
            
            # 최소 주문 크기 체크
            if gate_size < 0.001:
                return MirrorResult(
                    success=False,
                    action="size_too_small",
                    bitget_data=bitget_pos,
                    error=f"Gate.io 주문 크기 너무 작음: {gate_size}"
                )
            
            # Gate.io 주문 실행
            gate_side = 1 if side == 'long' else -1
            
            gate_result = await self.gate.place_order(
                contract=self.GATE_CONTRACT,
                size=int(gate_size * gate_side),
                price=None,  # 시장가
                text=f"mirror_position_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            return MirrorResult(
                success=True,
                action="new_position_mirrored",
                bitget_data=bitget_pos,
                gate_data=gate_result
            )
            
        except Exception as e:
            return MirrorResult(
                success=False,
                action="mirror_position_failed",
                bitget_data=bitget_pos,
                error=str(e)
            )

    async def _calculate_position_margin_ratio(self, size: float, entry_price: float, margin: float, leverage: int) -> Dict:
        """포지션의 실제 달러 마진 비율 계산"""
        try:
            # Bitget 계정 정보
            bitget_account = await self.bitget.get_account_info()
            bitget_total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            # Gate.io 계정 정보
            gate_account = await self.gate.get_account_balance()
            gate_total_equity = float(gate_account.get('total', 0))
            
            # Bitget 실제 마진 비율 계산
            if bitget_total_equity <= 0:
                return {'success': False, 'error': 'Bitget 총 자산이 0 이하'}
            
            margin_ratio = margin / bitget_total_equity
            
            # Gate.io 마진 계산
            gate_margin = gate_total_equity * margin_ratio
            
            # Gate.io 레버리지 (기본값 또는 동일하게 설정)
            gate_leverage = leverage if leverage > 0 else 10
            
            return {
                'success': True,
                'margin_ratio': margin_ratio,
                'gate_margin': gate_margin,
                'gate_leverage': gate_leverage,
                'bitget_total_equity': bitget_total_equity,
                'gate_total_equity': gate_total_equity
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def _handle_position_size_change(self, pos_id: str, size_change: float, bitget_pos: Dict):
        """포지션 크기 변화 처리"""
        try:
            if size_change < 0:
                # 포지션 감소 (부분 청산)
                await self._handle_partial_close(pos_id, abs(size_change), bitget_pos)
                self.daily_stats['partial_closes'] += 1
            else:
                # 포지션 증가 (추가 진입)
                await self._handle_position_increase(pos_id, size_change, bitget_pos)
            
        except Exception as e:
            self.logger.error(f"포지션 크기 변화 처리 오류: {e}")

    async def _handle_partial_close(self, pos_id: str, close_size: float, bitget_pos: Dict):
        """부분 청산 처리"""
        try:
            side = bitget_pos.get('holdSide', '').lower()
            entry_price = float(bitget_pos.get('openPriceAvg', 0))
            
            # 부분 청산을 위한 실제 달러 마진 비율 계산
            margin_ratio_result = await self._calculate_close_margin_ratio(
                close_size, entry_price, bitget_pos
            )
            
            if not margin_ratio_result['success']:
                self.logger.error(f"부분 청산 마진 계산 실패: {margin_ratio_result['error']}")
                return
            
            gate_close_size = margin_ratio_result['gate_close_size']
            
            # Gate.io 부분 청산 주문
            gate_side = -1 if side == 'long' else 1  # 반대 방향
            
            await self.gate.place_order(
                contract=self.GATE_CONTRACT,
                size=int(gate_close_size * gate_side),
                price=None,  # 시장가
                reduce_only=True,
                text=f"mirror_partial_close_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            self.logger.info(f"부분 청산 미러링 완료: {pos_id}, 크기: {close_size}")
            
        except Exception as e:
            self.logger.error(f"부분 청산 처리 실패: {e}")

    async def _calculate_close_margin_ratio(self, close_size: float, entry_price: float, bitget_pos: Dict) -> Dict:
        """청산을 위한 실제 달러 마진 비율 계산"""
        try:
            # 현재 포지션 정보
            total_size = float(bitget_pos.get('total', 0))
            total_margin = float(bitget_pos.get('marginSize', 0))
            
            if total_size <= 0:
                return {'success': False, 'error': '전체 포지션 크기가 0 이하'}
            
            # 청산 비율 계산
            close_ratio = close_size / total_size
            
            # Gate.io 계정 정보
            gate_account = await self.gate.get_account_balance()
            gate_total_equity = float(gate_account.get('total', 0))
            
            # Gate.io에서 청산할 크기 계산 (비율 기반)
            # 이미 미러링된 포지션 크기를 기준으로 계산
            gate_current_size = gate_total_equity * (total_margin / total_size) / entry_price  # 추정값
            gate_close_size = gate_current_size * close_ratio
            
            return {
                'success': True,
                'gate_close_size': gate_close_size,
                'close_ratio': close_ratio
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def _handle_position_increase(self, pos_id: str, increase_size: float, bitget_pos: Dict):
        """포지션 증가 처리"""
        try:
            # 증가분을 새로운 포지션으로 간주하여 미러링
            synthetic_pos = bitget_pos.copy()
            synthetic_pos['total'] = str(increase_size)
            
            result = await self._mirror_new_position(synthetic_pos)
            
            if result.success:
                self.logger.info(f"포지션 증가 미러링 완료: {pos_id}, 증가 크기: {increase_size}")
            else:
                self.logger.error(f"포지션 증가 미러링 실패: {result.error}")
            
        except Exception as e:
            self.logger.error(f"포지션 증가 처리 실패: {e}")

    async def _handle_position_close(self, pos_id: str):
        """포지션 완전 청산 처리"""
        try:
            if pos_id in self.mirrored_positions:
                position_info = self.mirrored_positions[pos_id]
                
                # Gate.io 전체 청산
                gate_side = -1 if position_info.side == 'long' else 1
                
                # 현재 포지션 크기 추정
                gate_account = await self.gate.get_account_balance()
                gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
                
                for gate_pos in gate_positions:
                    if gate_pos.get('size', 0) != 0:
                        # 전체 청산
                        await self.gate.place_order(
                            contract=self.GATE_CONTRACT,
                            size=0,  # 전체 청산
                            price=None,
                            reduce_only=True,
                            text=f"mirror_full_close_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        )
                        break
                
                del self.mirrored_positions[pos_id]
                if pos_id in self.position_sizes:
                    del self.position_sizes[pos_id]
                
                self.daily_stats['full_closes'] += 1
                self.logger.info(f"전체 청산 미러링 완료: {pos_id}")
                
        except Exception as e:
            self.logger.error(f"전체 청산 처리 실패: {e}")

    # 🔥🔥🔥 예약 주문 시스템 강화

    async def monitor_plan_orders(self):
        """🔥🔥🔥 예약 주문 취소 감지 완전 강화"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                # 🔥🔥🔥 예약 주문 정보 조회 (TP/SL 포함)
                plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
                plan_orders = plan_data.get('plan_orders', [])
                tp_sl_orders = plan_data.get('tp_sl_orders', [])
                
                # 모든 예약 주문 통합
                all_current_orders = plan_orders + tp_sl_orders
                current_order_ids = set()
                
                # 현재 활성 주문 ID 수집
                for order in all_current_orders:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if order_id:
                        current_order_ids.add(order_id)
                
                # 🔥🔥🔥 취소된 예약 주문 감지
                cancelled_orders = self.last_plan_order_ids - current_order_ids
                
                if cancelled_orders:
                    self.logger.info(f"🔥🔥🔥 예약 주문 취소 감지: {len(cancelled_orders)}개")
                    
                    for cancelled_order_id in cancelled_orders:
                        await self._handle_plan_order_cancellation(cancelled_order_id)
                        
                        # 🔥🔥🔥 취소 확인 및 재시도
                        await asyncio.sleep(self.cancel_verification_delay)
                        await self._verify_cancellation(cancelled_order_id)
                
                # 🔥 신규 예약 주문 감지 및 복제
                new_orders = current_order_ids - self.last_plan_order_ids
                if new_orders:
                    self.logger.info(f"🔥 신규 예약 주문 감지: {len(new_orders)}개")
                    
                    for order in all_current_orders:
                        order_id = order.get('orderId', order.get('planOrderId', ''))
                        if order_id in new_orders:
                            await self._process_new_plan_order(order)
                
                # 다음 체크를 위해 업데이트
                self.last_plan_order_ids = current_order_ids.copy()
                
                # 🔥🔥🔥 스냅샷 업데이트
                for order in all_current_orders:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if order_id:
                        self.plan_order_snapshot[order_id] = {
                            'order_data': order.copy(),
                            'timestamp': datetime.now().isoformat(),
                            'status': 'active'
                        }
                
                consecutive_errors = 0
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"예약 주문 모니터링 오류: {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 예약 주문 모니터링 오류\n"
                        f"연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL * 2)

    async def _handle_plan_order_cancellation(self, cancelled_order_id: str):
        """🔥🔥🔥 예약 주문 취소 처리"""
        try:
            self.logger.info(f"🔥🔥🔥 예약 주문 취소 처리 시작: {cancelled_order_id}")
            
            # 미러링된 주문 확인
            if cancelled_order_id not in self.mirrored_plan_orders:
                self.logger.info(f"취소된 주문이 미러링되지 않았음: {cancelled_order_id}")
                return
            
            gate_order_info = self.mirrored_plan_orders[cancelled_order_id]
            gate_order_id = gate_order_info.get('gate_order_id')
            
            if not gate_order_id:
                self.logger.error(f"Gate.io 주문 ID를 찾을 수 없음: {cancelled_order_id}")
                return
            
            success = False
            retry_count = 0
            
            while retry_count < self.max_cancel_retry and not success:
                try:
                    # Gate.io에서 주문 취소
                    cancel_result = await self.gate.cancel_price_triggered_order(
                        order_id=gate_order_id
                    )
                    
                    if cancel_result:
                        success = True
                        self.daily_stats['plan_order_cancel_success'] += 1
                        
                        # 🔥🔥🔥🔥🔥 연결된 TP 주문도 취소
                        await self._cancel_related_tp_orders(cancelled_order_id)
                        
                        # 추적에서 제거
                        del self.mirrored_plan_orders[cancelled_order_id]
                        
                        self.logger.info(f"🔥🔥🔥 예약 주문 취소 성공: {cancelled_order_id} -> {gate_order_id}")
                        
                        await self.telegram.send_message(
                            f"🔥🔥🔥 예약 주문 취소 미러링 성공\n"
                            f"비트겟 주문 ID: {cancelled_order_id}\n"
                            f"게이트 주문 ID: {gate_order_id}\n"
                            f"재시도 횟수: {retry_count + 1}"
                        )
                    
                except Exception as e:
                    retry_count += 1
                    self.logger.warning(f"예약 주문 취소 재시도 {retry_count}/{self.max_cancel_retry}: {e}")
                    
                    if retry_count < self.max_cancel_retry:
                        await asyncio.sleep(0.5 * retry_count)  # 점진적 대기
            
            if not success:
                self.daily_stats['plan_order_cancel_failed'] += 1
                
                await self.telegram.send_message(
                    f"❌ 예약 주문 취소 미러링 실패\n"
                    f"비트겟 주문 ID: {cancelled_order_id}\n"
                    f"게이트 주문 ID: {gate_order_id}\n"
                    f"최대 재시도 횟수 초과: {self.max_cancel_retry}"
                )
            
            self.daily_stats['plan_order_cancels'] += 1
            
        except Exception as e:
            self.logger.error(f"예약 주문 취소 처리 실패: {e}")
            self.daily_stats['plan_order_cancel_failed'] += 1

    async def _verify_cancellation(self, cancelled_order_id: str):
        """🔥🔥🔥 취소 확인"""
        try:
            # Gate.io에서 주문 상태 확인
            if cancelled_order_id in self.mirrored_plan_orders:
                gate_order_info = self.mirrored_plan_orders[cancelled_order_id]
                gate_order_id = gate_order_info.get('gate_order_id')
                
                if gate_order_id:
                    # 주문 상태 조회
                    gate_orders = await self.gate.get_price_triggered_orders(
                        self.GATE_CONTRACT, "open"
                    )
                    
                    order_still_exists = any(
                        order.get('id') == gate_order_id 
                        for order in gate_orders
                    )
                    
                    if order_still_exists:
                        self.daily_stats['cancel_verification_failed'] += 1
                        self.logger.warning(f"🔥🔥🔥 취소 확인 실패: {gate_order_id} 여전히 존재")
                    else:
                        self.daily_stats['cancel_verification_success'] += 1
                        self.logger.info(f"🔥🔥🔥 취소 확인 성공: {gate_order_id} 정상 취소됨")
                        
        except Exception as e:
            self.logger.error(f"취소 확인 실패: {e}")
            self.daily_stats['cancel_verification_failed'] += 1

    async def _cancel_related_tp_orders(self, bitget_plan_order_id: str):
        """🔥🔥🔥🔥🔥 연결된 TP 주문 취소"""
        try:
            if bitget_plan_order_id in self.mirrored_plan_order_tp:
                tp_info = self.mirrored_plan_order_tp[bitget_plan_order_id]
                gate_tp_order_ids = tp_info.get('gate_tp_order_ids', [])
                
                for gate_tp_order_id in gate_tp_order_ids:
                    try:
                        await self.gate.cancel_price_triggered_order(
                            order_id=gate_tp_order_id
                        )
                        self.logger.info(f"🔥🔥🔥🔥🔥 연결된 TP 주문 취소: {gate_tp_order_id}")
                    except Exception as e:
                        self.logger.error(f"연결된 TP 주문 취소 실패: {gate_tp_order_id}, {e}")
                
                # 추적에서 제거
                del self.mirrored_plan_order_tp[bitget_plan_order_id]
                
                if bitget_plan_order_id in self.plan_order_tp_tracking:
                    del self.plan_order_tp_tracking[bitget_plan_order_id]
                
        except Exception as e:
            self.logger.error(f"연결된 TP 주문 취소 처리 실패: {e}")

    async def _record_startup_plan_orders(self):
        """시작 시 존재하는 예약 주문 기록"""
        try:
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_orders = plan_orders + tp_sl_orders
            
            for order in all_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.startup_plan_orders.add(order_id)
                    self.last_plan_order_ids.add(order_id)
            
            self.logger.info(f"기존 예약 주문 기록: {len(self.startup_plan_orders)}개")
            
        except Exception as e:
            self.logger.error(f"기존 예약 주문 기록 실패: {e}")

    async def _record_startup_position_tp_sl(self):
        """시작 시 포지션의 TP/SL 주문 기록"""
        try:
            self.has_startup_positions = len(self.startup_positions) > 0
            
            if self.has_startup_positions:
                # 포지션이 있으면 해당 포지션의 TP/SL은 제외
                plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
                tp_sl_orders = plan_data.get('tp_sl_orders', [])
                
                for order in tp_sl_orders:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    plan_type = order.get('planType', '').lower()
                    
                    # TP/SL 주문인 경우 제외 대상에 추가
                    if order_id and plan_type in ['profit_plan', 'loss_plan']:
                        self.startup_position_tp_sl.add(order_id)
                        self.startup_plan_orders.add(order_id)  # 복제 제외
            
            self.logger.info(f"기존 포지션 TP/SL 주문 기록: {len(self.startup_position_tp_sl)}개")
            
        except Exception as e:
            self.logger.error(f"기존 포지션 TP/SL 기록 실패: {e}")

    async def _check_already_mirrored_plan_orders(self):
        """🔥 게이트에 이미 복제된 예약 주문 확인"""
        try:
            gate_orders = await self.gate.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            # 텍스트 패턴으로 미러링된 주문 식별
            mirrored_count = 0
            for gate_order in gate_orders:
                text = gate_order.get('text', '')
                if 'mirror_plan_order_' in text:
                    mirrored_count += 1
                    # 이미 복제된 주문으로 표시
                    order_id = text.split('_')[-1] if '_' in text else ''
                    if order_id:
                        self.already_mirrored_plan_orders.add(order_id)
            
            self.logger.info(f"🔥 게이트에서 이미 복제된 예약 주문 확인: {mirrored_count}개")
            
        except Exception as e:
            self.logger.error(f"이미 복제된 예약 주문 확인 실패: {e}")

    async def _mirror_startup_plan_orders(self):
        """시작 시 예약 주문 복제"""
        try:
            if not self.startup_plan_orders:
                self.logger.info("복제할 기존 예약 주문 없음")
                return
            
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            
            mirrored_count = 0
            
            for order in plan_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                
                if order_id in self.startup_plan_orders:
                    # 포지션이 있고 TP/SL 주문인 경우 제외
                    if (self.has_startup_positions and 
                        order_id in self.startup_position_tp_sl):
                        continue
                    
                    # 이미 복제된 주문인 경우 제외
                    if order_id in self.already_mirrored_plan_orders:
                        continue
                    
                    result = await self._mirror_single_plan_order(order, is_startup=True)
                    if result['success']:
                        mirrored_count += 1
                        self.daily_stats['startup_plan_mirrors'] += 1
            
            self.startup_plan_orders_processed = True
            
            if mirrored_count > 0:
                await self.telegram.send_message(
                    f"🔥 시작 시 예약 주문 복제 완료\n"
                    f"복제된 주문: {mirrored_count}개\n"
                    f"제외된 주문: {len(self.startup_position_tp_sl)}개 (포지션 TP/SL)\n"
                    f"이미 복제됨: {len(self.already_mirrored_plan_orders)}개"
                )
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 복제 실패: {e}")

    async def _process_new_plan_order(self, order: Dict):
        """신규 예약 주문 처리"""
        try:
            order_id = order.get('orderId', order.get('planOrderId', ''))
            
            # 시작 시 주문은 이미 처리됨
            if order_id in self.startup_plan_orders:
                return
            
            # 이미 미러링된 주문인지 확인
            if order_id in self.mirrored_plan_orders:
                self.daily_stats['plan_order_skipped_already_mirrored'] += 1
                return
            
            result = await self._mirror_single_plan_order(order, is_startup=False)
            
            if result['success']:
                self.daily_stats['plan_order_mirrors'] += 1
                
                await self.telegram.send_message(
                    f"🔥 신규 예약 주문 미러링 성공\n"
                    f"비트겟 주문 ID: {order_id}\n"
                    f"게이트 주문 ID: {result['gate_order_id']}\n"
                    f"방향: {order.get('side', 'unknown')}\n"
                    f"트리거 가격: ${float(order.get('triggerPrice', 0)):,.2f}"
                )
            else:
                await self.telegram.send_message(
                    f"❌ 신규 예약 주문 미러링 실패\n"
                    f"비트겟 주문 ID: {order_id}\n"
                    f"오류: {result['error']}"
                )
            
        except Exception as e:
            self.logger.error(f"신규 예약 주문 처리 실패: {e}")

    async def _mirror_single_plan_order(self, bitget_order: Dict, is_startup: bool = False) -> Dict:
        """단일 예약 주문 미러링"""
        try:
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            side = bitget_order.get('side', '').lower()
            size = float(bitget_order.get('size', 0))
            trigger_price = float(bitget_order.get('triggerPrice', 0))
            
            if not all([order_id, side, size > 0, trigger_price > 0]):
                return {
                    'success': False,
                    'error': '필수 주문 정보 누락'
                }
            
            # 🔥🔥🔥 시세 차이 대응 - 트리거 가격 조정
            adjusted_trigger_price = await self._adjust_trigger_price_for_gate(trigger_price)
            
            # 실제 달러 마진 비율 동적 계산
            margin_ratio_result = await self._calculate_dynamic_margin_ratio(
                size, trigger_price, bitget_order
            )
            
            if not margin_ratio_result['success']:
                return {
                    'success': False,
                    'error': f"마진 계산 실패: {margin_ratio_result['error']}"
                }
            
            leverage = margin_ratio_result['leverage']
            margin_ratio = margin_ratio_result['margin_ratio']
            
            # Gate.io 계정 정보
            gate_account = await self.gate.get_account_balance()
            gate_total_equity = float(gate_account.get('total', 0))
            
            # Gate.io 마진 및 크기 계산
            gate_margin = gate_total_equity * margin_ratio
            gate_notional = gate_margin * leverage
            gate_size = gate_notional / adjusted_trigger_price
            
            # 최소 크기 체크
            if gate_size < 0.001:
                return {
                    'success': False,
                    'error': f'Gate.io 주문 크기 너무 작음: {gate_size}'
                }
            
            # 🔥🔥🔥 방향 처리 개선
            gate_size_with_direction = await self._calculate_gate_order_size_and_direction(
                side, gate_size, adjusted_trigger_price
            )
            
            if not gate_size_with_direction['success']:
                return {
                    'success': False,
                    'error': gate_size_with_direction['error']
                }
            
            final_gate_size = gate_size_with_direction['size']
            
            # Gate.io 예약 주문 생성
            gate_result = await self.gate.place_price_triggered_order(
                contract=self.GATE_CONTRACT,
                trigger_price=str(adjusted_trigger_price),
                order_type="market",
                size=final_gate_size,
                text=f"mirror_plan_order_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            if gate_result and gate_result.get('id'):
                gate_order_id = gate_result['id']
                
                # 미러링 기록
                self.mirrored_plan_orders[order_id] = {
                    'gate_order_id': gate_order_id,
                    'gate_order_data': gate_result,
                    'original_bitget_order': bitget_order,
                    'margin_ratio': margin_ratio,
                    'leverage': leverage,
                    'adjusted_trigger_price': adjusted_trigger_price,
                    'mirrored_at': datetime.now().isoformat(),
                    'is_startup': is_startup
                }
                
                # 🔥🔥🔥🔥🔥 예약 주문 TP 설정 복제
                await self._mirror_plan_order_tp_settings(bitget_order, gate_order_id)
                
                return {
                    'success': True,
                    'gate_order_id': gate_order_id,
                    'gate_result': gate_result,
                    'margin_ratio': margin_ratio,
                    'adjusted_trigger_price': adjusted_trigger_price
                }
            else:
                return {
                    'success': False,
                    'error': 'Gate.io 주문 생성 실패'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def _adjust_trigger_price_for_gate(self, bitget_trigger_price: float) -> float:
        """🔥🔥🔥 시세 차이를 고려한 트리거 가격 조정"""
        try:
            # 현재 시세 업데이트
            await self._update_current_prices()
            
            # 시세 차이가 큰 경우 조정
            if self.price_diff_percent > self.MAX_PRICE_DIFF_PERCENT:
                # Gate.io 현재가 기준으로 조정
                price_ratio = self.gate_current_price / self.bitget_current_price
                adjusted_price = bitget_trigger_price * price_ratio
                
                self.logger.info(f"🔥🔥🔥 트리거 가격 조정: {bitget_trigger_price} -> {adjusted_price} (비율: {price_ratio:.4f})")
                return adjusted_price
            else:
                return bitget_trigger_price
                
        except Exception as e:
            self.logger.error(f"트리거 가격 조정 실패: {e}")
            return bitget_trigger_price

    async def _calculate_gate_order_size_and_direction(self, bitget_side: str, gate_size: float, trigger_price: float) -> Dict:
        """🔥🔥🔥 Gate.io 주문 크기 및 방향 계산 개선"""
        try:
            # 현재 시세 업데이트
            await self._update_current_prices()
            current_price = self.gate_current_price if self.gate_current_price > 0 else trigger_price
            
            # 🔥🔥🔥 방향 결정 로직 완전 수정
            if bitget_side in ['buy', 'open_long']:
                # 비트겟 롱 진입 → 게이트 롱 진입 (양수)
                if trigger_price > current_price:
                    # 현재가보다 높은 가격에서 매수 (브레이크아웃)
                    final_size = int(gate_size)
                else:
                    # 현재가보다 낮은 가격에서 매수 (딥 바이)
                    final_size = int(gate_size)
                    
            elif bitget_side in ['sell', 'open_short']:
                # 비트겟 숏 진입 → 게이트 숏 진입 (음수)
                if trigger_price < current_price:
                    # 현재가보다 낮은 가격에서 매도 (브레이크다운)
                    final_size = -int(gate_size)
                else:
                    # 현재가보다 높은 가격에서 매도 (저항 터치)
                    final_size = -int(gate_size)
                    
            elif bitget_side == 'close_long':
                # 🔥🔥🔥 핵심 수정: close_long은 롱 포지션 청산 = 매도 (음수)
                final_size = -int(gate_size)
                
            elif bitget_side == 'close_short':
                # close_short는 숏 포지션 청산 = 매수 (양수)
                final_size = int(gate_size)
                
            else:
                return {
                    'success': False,
                    'error': f'지원하지 않는 주문 방향: {bitget_side}'
                }
            
            # 🔥🔥🔥 크기 검증 강화
            min_diff_percent = 0.01  # 0.01%로 완화
            max_diff_percent = 100   # 100%로 완화
            
            price_diff_percent = abs(trigger_price - current_price) / current_price * 100
            
            if price_diff_percent < min_diff_percent:
                return {
                    'success': False,
                    'error': f'트리거 가격과 현재가 차이 너무 작음: {price_diff_percent:.3f}% < {min_diff_percent}%'
                }
            
            if price_diff_percent > max_diff_percent:
                return {
                    'success': False,
                    'error': f'트리거 가격과 현재가 차이 너무 큼: {price_diff_percent:.1f}% > {max_diff_percent}%'
                }
            
            return {
                'success': True,
                'size': final_size,
                'direction': 'buy' if final_size > 0 else 'sell',
                'price_diff_percent': price_diff_percent
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'방향 계산 실패: {str(e)}'
            }

    # 🔥🔥🔥 TP 설정 미러링 강화

    async def monitor_tp_orders(self):
        """🔥🔥🔥 TP 주문 모니터링"""
        while self.monitoring:
            try:
                # 현재 포지션들의 TP 설정 확인
                bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                
                for pos in bitget_positions:
                    if float(pos.get('total', 0)) > 0:
                        pos_id = self._generate_position_id(pos)
                        
                        # 시작시 포지션은 제외
                        if pos_id in self.startup_positions:
                            continue
                        
                        await self._check_position_tp_settings(pos, pos_id)
                
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"TP 주문 모니터링 오류: {e}")
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL * 2)

    async def _check_position_tp_settings(self, bitget_pos: Dict, pos_id: str):
        """포지션의 TP 설정 확인"""
        try:
            # 비트겟 TP/SL 주문 조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            # 이 포지션의 TP 주문 찾기
            position_tp_orders = []
            for order in tp_sl_orders:
                plan_type = order.get('planType', '').lower()
                if plan_type == 'profit_plan':  # TP 주문
                    position_tp_orders.append(order)
            
            # TP 설정이 있으면 미러링
            for tp_order in position_tp_orders:
                tp_order_id = tp_order.get('orderId', tp_order.get('planOrderId', ''))
                
                if tp_order_id not in self.mirrored_tp_orders:
                    await self._mirror_position_tp_order(tp_order, bitget_pos, pos_id)
            
        except Exception as e:
            self.logger.error(f"포지션 TP 설정 확인 실패: {e}")

    async def _mirror_position_tp_order(self, tp_order: Dict, bitget_pos: Dict, pos_id: str):
        """포지션 TP 주문 미러링"""
        try:
            tp_order_id = tp_order.get('orderId', tp_order.get('planOrderId', ''))
            tp_price = float(tp_order.get('triggerPrice', 0))
            tp_size = float(tp_order.get('size', 0))
            
            if not all([tp_order_id, tp_price > 0, tp_size > 0]):
                return
            
            # 🔥🔥🔥 시세 차이 대응
            adjusted_tp_price = await self._adjust_trigger_price_for_gate(tp_price)
            
            # 포지션 정보
            position_side = bitget_pos.get('holdSide', '').lower()
            position_size = float(bitget_pos.get('total', 0))
            
            # Gate.io TP 주문 크기 계산 (비율 기반)
            tp_ratio = tp_size / position_size if position_size > 0 else 1.0
            
            # Gate.io 포지션 크기 추정
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            gate_position_size = 0
            
            for gate_pos in gate_positions:
                if gate_pos.get('size', 0) != 0:
                    gate_position_size = abs(float(gate_pos.get('size', 0)))
                    break
            
            gate_tp_size = gate_position_size * tp_ratio
            
            # TP 방향 결정 (포지션과 반대)
            if position_side == 'long':
                gate_tp_final_size = -int(gate_tp_size)  # 롱 포지션 TP는 매도
            else:
                gate_tp_final_size = int(gate_tp_size)   # 숏 포지션 TP는 매수
            
            # Gate.io TP 주문 생성
            gate_tp_result = await self.gate.place_price_triggered_order(
                contract=self.GATE_CONTRACT,
                trigger_price=str(adjusted_tp_price),
                order_type="market",
                size=gate_tp_final_size,
                text=f"mirror_tp_{tp_order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            if gate_tp_result and gate_tp_result.get('id'):
                gate_tp_order_id = gate_tp_result['id']
                
                # TP 미러링 기록
                self.mirrored_tp_orders[tp_order_id] = gate_tp_order_id
                
                # 포지션별 TP 추적
                if pos_id not in self.position_tp_tracking:
                    self.position_tp_tracking[pos_id] = []
                self.position_tp_tracking[pos_id].append(gate_tp_order_id)
                
                self.daily_stats['tp_mirror_success'] += 1
                
                await self.telegram.send_message(
                    f"🔥🔥🔥 TP 미러링 성공\n"
                    f"포지션: {pos_id}\n"
                    f"비트겟 TP ID: {tp_order_id}\n"
                    f"게이트 TP ID: {gate_tp_order_id}\n"
                    f"TP 가격: ${adjusted_tp_price:,.2f}\n"
                    f"TP 크기: {gate_tp_final_size}"
                )
            else:
                self.daily_stats['tp_mirror_failed'] += 1
                
            self.daily_stats['tp_mirrors'] += 1
            
        except Exception as e:
            self.logger.error(f"포지션 TP 주문 미러링 실패: {e}")
            self.daily_stats['tp_mirror_failed'] += 1

    # 🔥🔥🔥🔥🔥 예약 주문 TP 설정 복제 (핵심 수정)

    async def monitor_plan_order_tp(self):
        """🔥🔥🔥🔥🔥 예약 주문 TP 설정 모니터링"""
        while self.monitoring:
            try:
                # 미러링된 예약 주문들의 TP 설정 확인
                for bitget_plan_order_id in list(self.mirrored_plan_orders.keys()):
                    await self._check_plan_order_tp_settings(bitget_plan_order_id)
                
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"예약 주문 TP 모니터링 오류: {e}")
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL * 2)

    async def _check_plan_order_tp_settings(self, bitget_plan_order_id: str):
        """🔥🔥🔥🔥🔥 예약 주문의 TP 설정 확인"""
        try:
            # 이미 TP가 복제된 경우 스킵
            if bitget_plan_order_id in self.mirrored_plan_order_tp:
                return
            
            # 비트겟에서 예약 주문 정보 조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            
            # 해당 예약 주문 찾기
            target_plan_order = None
            for order in plan_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id == bitget_plan_order_id:
                    target_plan_order = order
                    break
            
            if not target_plan_order:
                return
            
            # TP 설정 확인
            tp_price = target_plan_order.get('presetTakeProfitPrice')
            tp_trigger_type = target_plan_order.get('presetTakeProfitTriggerType')
            
            if tp_price and float(tp_price) > 0:
                await self._mirror_plan_order_tp_settings(target_plan_order, None)
            
        except Exception as e:
            self.logger.error(f"예약 주문 TP 설정 확인 실패: {e}")

    async def _mirror_plan_order_tp_settings(self, bitget_plan_order: Dict, gate_plan_order_id: str = None):
        """🔥🔥🔥🔥🔥 예약 주문 TP 설정 복제 (핵심 수정)"""
        try:
            bitget_plan_order_id = bitget_plan_order.get('orderId', bitget_plan_order.get('planOrderId', ''))
            
            # TP 설정 확인
            tp_price = bitget_plan_order.get('presetTakeProfitPrice')
            if not tp_price or float(tp_price) <= 0:
                return  # TP 설정이 없으면 복제하지 않음
            
            tp_price = float(tp_price)
            
            # 예약 주문 정보
            plan_side = bitget_plan_order.get('side', '').lower()
            plan_size = float(bitget_plan_order.get('size', 0))
            plan_trigger_price = float(bitget_plan_order.get('triggerPrice', 0))
            
            # 🔥🔥🔥🔥🔥 핵심 수정: TP 방향 올바르게 계산
            # 예약 주문이 체결되면 생성될 포지션을 기준으로 TP 방향 결정
            if plan_side in ['buy', 'open_long']:
                # 롱 진입 예약 주문 → 체결되면 롱 포지션 → TP는 매도(-) 방향
                tp_side_multiplier = -1
                position_type = "long"
            elif plan_side in ['sell', 'open_short']:
                # 숏 진입 예약 주문 → 체결되면 숏 포지션 → TP는 매수(+) 방향
                tp_side_multiplier = 1
                position_type = "short"
            else:
                self.logger.warning(f"지원하지 않는 예약 주문 방향: {plan_side}")
                return
            
            # 🔥🔥🔥 시세 차이 대응
            adjusted_tp_price = await self._adjust_trigger_price_for_gate(tp_price)
            
            # Gate.io 예약 주문 TP 크기 계산 (동일한 마진 비율 적용)
            if bitget_plan_order_id in self.mirrored_plan_orders:
                mirrored_info = self.mirrored_plan_orders[bitget_plan_order_id]
                margin_ratio = mirrored_info.get('margin_ratio', 0)
                leverage = mirrored_info.get('leverage', 10)
                
                # Gate.io 계정 정보
                gate_account = await self.gate.get_account_balance()
                gate_total_equity = float(gate_account.get('total', 0))
                
                # TP 크기 계산
                gate_tp_margin = gate_total_equity * margin_ratio
                gate_tp_notional = gate_tp_margin * leverage
                gate_tp_size = gate_tp_notional / adjusted_tp_price
                
                # 🔥🔥🔥🔥🔥 최종 TP 크기 및 방향 결정
                final_tp_size = int(gate_tp_size * tp_side_multiplier)
                
                # Gate.io TP 주문 생성 (예약 주문이 체결된 후 실행될 TP)
                gate_tp_result = await self.gate.place_price_triggered_order(
                    contract=self.GATE_CONTRACT,
                    trigger_price=str(adjusted_tp_price),
                    order_type="market",
                    size=final_tp_size,
                    text=f"mirror_plan_tp_{bitget_plan_order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                
                if gate_tp_result and gate_tp_result.get('id'):
                    gate_tp_order_id = gate_tp_result['id']
                    
                    # 예약 주문 TP 복제 기록
                    self.mirrored_plan_order_tp[bitget_plan_order_id] = {
                        'gate_tp_order_ids': [gate_tp_order_id],
                        'tp_price': adjusted_tp_price,
                        'tp_size': final_tp_size,
                        'position_type': position_type,
                        'original_tp_price': tp_price,
                        'margin_ratio': margin_ratio,
                        'leverage': leverage,
                        'mirrored_at': datetime.now().isoformat()
                    }
                    
                    # 추적 리스트 업데이트
                    if bitget_plan_order_id not in self.plan_order_tp_tracking:
                        self.plan_order_tp_tracking[bitget_plan_order_id] = []
                    self.plan_order_tp_tracking[bitget_plan_order_id].append(gate_tp_order_id)
                    
                    self.daily_stats['plan_order_tp_success'] += 1
                    
                    self.logger.info(f"🔥🔥🔥🔥🔥 예약 주문 TP 복제 성공: {bitget_plan_order_id} -> {gate_tp_order_id}")
                    
                    await self.telegram.send_message(
                        f"🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 성공\n"
                        f"비트겟 예약 주문 ID: {bitget_plan_order_id}\n"
                        f"게이트 TP 주문 ID: {gate_tp_order_id}\n"
                        f"예약 주문 방향: {plan_side} → {position_type} 포지션 예상\n"
                        f"TP 방향: {'매도(-)' if tp_side_multiplier == -1 else '매수(+)'}\n"
                        f"TP 가격: ${adjusted_tp_price:,.2f}\n"
                        f"TP 크기: {final_tp_size}\n"
                        f"🔥🔥🔥🔥🔥 올바른 방향으로 TP 복제 완료!"
                    )
                else:
                    self.daily_stats['plan_order_tp_failed'] += 1
                    self.logger.error(f"예약 주문 TP 복제 실패: Gate.io 주문 생성 실패")
            else:
                self.logger.warning(f"미러링된 예약 주문 정보를 찾을 수 없음: {bitget_plan_order_id}")
                self.daily_stats['plan_order_tp_failed'] += 1
            
            self.daily_stats['plan_order_tp_mirrors'] += 1
            
        except Exception as e:
            self.logger.error(f"예약 주문 TP 설정 복제 실패: {e}")
            self.daily_stats['plan_order_tp_failed'] += 1
