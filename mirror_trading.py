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
        self.mirrored_positions: Dict[str, PositionInfo] = {}  # 포지션 ID: PositionInfo
        self.startup_positions: Set[str] = set()   # 시작 시 존재했던 포지션
        self.failed_mirrors: List[MirrorResult] = []  # 실패한 미러링 기록
        self.last_sync_check = datetime.min
        self.last_report_time = datetime.min
        
        # 포지션 크기 추적 (부분 청산 감지용)
        self.position_sizes: Dict[str, float] = {}  # 포지션 ID: 마지막 크기
        
        # TP/SL 주문 추적
        self.tp_sl_orders: Dict[str, Dict] = {}  # 포지션 ID: {tp: [주문ID], sl: [주문ID]}
        
        # 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.CHECK_INTERVAL = 3  # 3초마다 체크
        self.SYNC_CHECK_INTERVAL = 30  # 30초마다 동기화 체크
        self.MAX_RETRIES = 3
        self.MIN_POSITION_SIZE = 0.00001  # BTC
        self.MIN_MARGIN = 1.0  # 최소 마진 $1
        self.DAILY_REPORT_HOUR = 9  # 매일 오전 9시 리포트
        
        # 성과 추적
        self.daily_stats = {
            'total_mirrored': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'total_volume': 0.0,
            'errors': []
        }
        
        self.monitoring = True
        self.logger.info("미러 트레이딩 시스템 초기화 완료")
    
    async def start(self):
        """미러 트레이딩 시작"""
        try:
            self.logger.info("🚀 미러 트레이딩 시스템 시작")
            
            # 초기 포지션 기록 (복제하지 않을 기존 포지션)
            await self._record_startup_positions()
            
            # 초기 계정 상태 출력
            await self._log_account_status()
            
            # 모니터링 태스크 시작
            tasks = [
                self.monitor_positions(),
                self.monitor_sync_status(),
                self.generate_daily_reports()
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시작 실패: {e}")
            await self.telegram.send_message(
                f"❌ 미러 트레이딩 시작 실패\n"
                f"오류: {str(e)[:200]}"
            )
            raise
    
    async def _record_startup_positions(self):
        """시작 시 존재하는 포지션 기록"""
        try:
            # 비트겟 기존 포지션 확인
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    # 포지션 ID 생성
                    pos_id = self._generate_position_id(pos)
                    self.startup_positions.add(pos_id)
                    
                    # 크기 기록
                    self.position_sizes[pos_id] = float(pos.get('total', 0))
                    
                    self.logger.info(f"기존 포지션 기록 (복제 제외): {pos_id}")
            
            self.logger.info(f"총 {len(self.startup_positions)}개의 기존 포지션이 복제에서 제외됩니다")
            
            # 게이트 기존 포지션 확인
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            if gate_positions and any(pos.get('size', 0) != 0 for pos in gate_positions):
                self.logger.warning("⚠️ 게이트에 기존 포지션이 있습니다. 수동 확인이 필요할 수 있습니다.")
            
        except Exception as e:
            self.logger.error(f"기존 포지션 기록 실패: {e}")
    
    async def _log_account_status(self):
        """계정 상태 로깅"""
        try:
            # 비트겟 계정 정보
            bitget_account = await self.bitget.get_account_info()
            bitget_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            # 게이트 계정 정보
            gate_account = await self.gate.get_account_balance()
            gate_equity = float(gate_account.get('total', 0))
            
            self.logger.info(
                f"💰 계정 상태\n"
                f"비트겟: ${bitget_equity:,.2f}\n"
                f"게이트: ${gate_equity:,.2f}"
            )
            
            await self.telegram.send_message(
                f"🔄 미러 트레이딩 시작\n\n"
                f"💰 계정 잔고:\n"
                f"• 비트겟: ${bitget_equity:,.2f}\n"
                f"• 게이트: ${gate_equity:,.2f}\n\n"
                f"📊 기존 포지션: {len(self.startup_positions)}개 (복제 제외)"
            )
            
        except Exception as e:
            self.logger.error(f"계정 상태 조회 실패: {e}")
    
    async def monitor_positions(self):
        """포지션 모니터링 메인 루프"""
        self.logger.info("포지션 모니터링 시작")
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                # 비트겟 포지션 확인
                bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                
                # 활성 포지션 처리
                active_position_ids = set()
                
                for pos in bitget_positions:
                    if float(pos.get('total', 0)) > 0:
                        pos_id = self._generate_position_id(pos)
                        active_position_ids.add(pos_id)
                        
                        # 새 포지션 또는 업데이트 확인
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
                self.logger.error(f"모니터링 중 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 미러 트레이딩 모니터링 오류\n"
                        f"연속 {consecutive_errors}회 실패\n"
                        f"오류: {str(e)[:200]}"
                    )
                
                await asyncio.sleep(self.CHECK_INTERVAL * 2)
    
    async def _process_position(self, bitget_pos: Dict):
        """포지션 처리 (신규/업데이트)"""
        try:
            pos_id = self._generate_position_id(bitget_pos)
            
            # 시작 시 존재했던 포지션은 무시
            if pos_id in self.startup_positions:
                return
            
            current_size = float(bitget_pos.get('total', 0))
            
            # 새로운 포지션
            if pos_id not in self.mirrored_positions:
                self.logger.info(f"🆕 새로운 포지션 감지: {pos_id}")
                result = await self._mirror_new_position(bitget_pos)
                
                if result.success:
                    self.mirrored_positions[pos_id] = await self._create_position_info(bitget_pos)
                    self.position_sizes[pos_id] = current_size
                    self.daily_stats['successful_mirrors'] += 1
                    
                    await self.telegram.send_message(
                        f"✅ 포지션 미러링 성공\n"
                        f"방향: {bitget_pos.get('holdSide', '')}\n"
                        f"진입가: ${float(bitget_pos.get('openPriceAvg', 0)):,.2f}\n"
                        f"마진: ${result.gate_data.get('margin', 0):,.2f}"
                    )
                else:
                    self.failed_mirrors.append(result)
                    self.daily_stats['failed_mirrors'] += 1
                    
                    await self.telegram.send_message(
                        f"❌ 포지션 미러링 실패\n"
                        f"오류: {result.error}"
                    )
                
                self.daily_stats['total_mirrored'] += 1
                
            # 기존 포지션 업데이트 확인
            else:
                last_size = self.position_sizes.get(pos_id, 0)
                
                # 부분 청산 감지
                if current_size < last_size * 0.95:  # 5% 이상 감소
                    reduction_ratio = 1 - (current_size / last_size)
                    self.logger.info(f"📉 부분 청산 감지: {reduction_ratio*100:.1f}% 감소")
                    
                    await self._handle_partial_close(pos_id, bitget_pos, reduction_ratio)
                    self.position_sizes[pos_id] = current_size
                    self.daily_stats['partial_closes'] += 1
                
                # TP/SL 업데이트 확인
                await self._check_tp_sl_updates(pos_id, bitget_pos)
                
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
                # 1. 자산 비율 계산
                margin_ratio = await self._calculate_margin_ratio(bitget_pos)
                
                if margin_ratio is None:
                    return MirrorResult(
                        success=False,
                        action="new_position",
                        bitget_data=bitget_pos,
                        error="마진 비율 계산 실패"
                    )
                
                # 2. 게이트 진입 금액 계산
                gate_account = await self.gate.get_account_balance()
                gate_available = float(gate_account.get('available', 0))
                gate_margin = gate_available * margin_ratio
                
                # 최소 마진 체크
                if gate_margin < self.MIN_MARGIN:
                    return MirrorResult(
                        success=False,
                        action="new_position",
                        bitget_data=bitget_pos,
                        error=f"게이트 마진 부족: ${gate_margin:.2f} < ${self.MIN_MARGIN}"
                    )
                
                self.logger.info(
                    f"💰 게이트 진입 계산\n"
                    f"비율: {margin_ratio:.4f}\n"
                    f"가용자산: ${gate_available:.2f}\n"
                    f"진입마진: ${gate_margin:.2f}"
                )
                
                # 3. 레버리지 설정
                leverage = int(float(bitget_pos.get('leverage', 1)))
                await self.gate.set_leverage(self.GATE_CONTRACT, leverage)
                
                # 4. 포지션 방향 및 수량 계산
                side = bitget_pos.get('holdSide', '').lower()
                current_price = float(bitget_pos.get('markPrice', bitget_pos.get('openPriceAvg', 0)))
                
                # 계약 정보 조회
                contract_info = await self.gate.get_contract_info(self.GATE_CONTRACT)
                quanto_multiplier = float(contract_info.get('quanto_multiplier', 0.0001))
                
                # 계약 수 계산
                notional_value = gate_margin * leverage
                gate_size = int(notional_value / (current_price * quanto_multiplier))
                
                if side == 'short':
                    gate_size = -gate_size
                
                self.logger.info(
                    f"📊 주문 계산\n"
                    f"방향: {side}\n"
                    f"레버리지: {leverage}x\n"
                    f"계약수: {gate_size}"
                )
                
                # 5. 진입 주문 (시장가)
                order_result = await self.gate.place_order(
                    contract=self.GATE_CONTRACT,
                    size=gate_size,
                    price=None,  # 시장가
                    reduce_only=False
                )
                
                self.logger.info(f"✅ 게이트 진입 성공: {order_result}")
                
                # 6. TP/SL 설정 (잠시 대기 후)
                await asyncio.sleep(1)
                tp_sl_result = await self._set_gate_tp_sl(bitget_pos, gate_size)
                
                # 7. 통계 업데이트
                self.daily_stats['total_volume'] += abs(notional_value)
                
                return MirrorResult(
                    success=True,
                    action="new_position",
                    bitget_data=bitget_pos,
                    gate_data={
                        'order': order_result,
                        'size': gate_size,
                        'margin': gate_margin,
                        'tp_sl': tp_sl_result
                    }
                )
                
            except Exception as e:
                retry_count += 1
                self.logger.error(f"포지션 미러링 시도 {retry_count}/{self.MAX_RETRIES} 실패: {e}")
                
                if retry_count < self.MAX_RETRIES:
                    await asyncio.sleep(2 ** retry_count)  # 지수 백오프
                else:
                    return MirrorResult(
                        success=False,
                        action="new_position",
                        bitget_data=bitget_pos,
                        error=f"최대 재시도 횟수 초과: {str(e)}"
                    )
    
    async def _calculate_margin_ratio(self, bitget_pos: Dict) -> Optional[float]:
        """비트겟 포지션의 마진 비율 계산"""
        try:
            # 비트겟 계정 정보
            bitget_account = await self.bitget.get_account_info()
            
            # 총 자산 (USDT)
            total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            # 포지션 마진 (USDT)
            position_margin = float(bitget_pos.get('marginSize', bitget_pos.get('margin', 0)))
            
            if total_equity <= 0 or position_margin <= 0:
                self.logger.warning(f"잘못된 마진 데이터: 총자산={total_equity}, 마진={position_margin}")
                return None
            
            # 마진 비율
            margin_ratio = position_margin / total_equity
            
            # 비율 제한 (최대 50%)
            margin_ratio = min(margin_ratio, 0.5)
            
            self.logger.info(
                f"📊 마진 비율 계산\n"
                f"비트겟 총자산: ${total_equity:,.2f}\n"
                f"포지션 마진: ${position_margin:,.2f}\n"
                f"비율: {margin_ratio:.4f} ({margin_ratio*100:.2f}%)"
            )
            
            return margin_ratio
            
        except Exception as e:
            self.logger.error(f"마진 비율 계산 실패: {e}")
            return None
    
    async def _set_gate_tp_sl(self, bitget_pos: Dict, gate_size: int) -> Dict:
        """게이트에 TP/SL 설정"""
        try:
            pos_id = self._generate_position_id(bitget_pos)
            entry_price = float(bitget_pos.get('openPriceAvg', 0))
            side = bitget_pos.get('holdSide', '').lower()
            
            tp_orders = []
            sl_orders = []
            
            # 기본 TP/SL 설정 (실제로는 비트겟 API에서 가져와야 함)
            if side == 'long':
                # 롱 포지션
                tp_prices = [
                    entry_price * 1.01,  # 1% TP
                    entry_price * 1.02,  # 2% TP
                    entry_price * 1.03   # 3% TP
                ]
                sl_price = entry_price * 0.98  # 2% SL
                
                # TP 주문들 (분할 익절)
                remaining_size = abs(gate_size)
                for i, tp_price in enumerate(tp_prices):
                    tp_size = int(remaining_size * 0.33)  # 33%씩
                    if i == len(tp_prices) - 1:  # 마지막은 남은 전체
                        tp_size = remaining_size
                    
                    tp_order = await self.gate.create_price_triggered_order(
                        trigger_type="ge",
                        trigger_price=str(tp_price),
                        order_type="limit",
                        contract=self.GATE_CONTRACT,
                        size=-tp_size,
                        price=str(tp_price)
                    )
                    tp_orders.append(tp_order)
                    remaining_size -= tp_size
                
                # SL 주문 (전체)
                sl_order = await self.gate.create_price_triggered_order(
                    trigger_type="le",
                    trigger_price=str(sl_price),
                    order_type="market",
                    contract=self.GATE_CONTRACT,
                    size=-abs(gate_size)
                )
                sl_orders.append(sl_order)
                
            else:
                # 숏 포지션
                tp_prices = [
                    entry_price * 0.99,  # 1% TP
                    entry_price * 0.98,  # 2% TP
                    entry_price * 0.97   # 3% TP
                ]
                sl_price = entry_price * 1.02  # 2% SL
                
                # TP 주문들
                remaining_size = abs(gate_size)
                for i, tp_price in enumerate(tp_prices):
                    tp_size = int(remaining_size * 0.33)
                    if i == len(tp_prices) - 1:
                        tp_size = remaining_size
                    
                    tp_order = await self.gate.create_price_triggered_order(
                        trigger_type="le",
                        trigger_price=str(tp_price),
                        order_type="limit",
                        contract=self.GATE_CONTRACT,
                        size=tp_size,
                        price=str(tp_price)
                    )
                    tp_orders.append(tp_order)
                    remaining_size -= tp_size
                
                # SL 주문
                sl_order = await self.gate.create_price_triggered_order(
                    trigger_type="ge",
                    trigger_price=str(sl_price),
                    order_type="market",
                    contract=self.GATE_CONTRACT,
                    size=abs(gate_size)
                )
                sl_orders.append(sl_order)
            
            # TP/SL 주문 ID 저장
            self.tp_sl_orders[pos_id] = {
                'tp': [order.get('id') for order in tp_orders],
                'sl': [order.get('id') for order in sl_orders]
            }
            
            self.logger.info(
                f"📍 TP/SL 설정 완료\n"
                f"TP: {len(tp_orders)}개\n"
                f"SL: {len(sl_orders)}개"
            )
            
            return {
                'tp_orders': tp_orders,
                'sl_orders': sl_orders
            }
            
        except Exception as e:
            self.logger.error(f"TP/SL 설정 실패: {e}")
            return {'tp_orders': [], 'sl_orders': []}
    
    async def _handle_partial_close(self, pos_id: str, bitget_pos: Dict, reduction_ratio: float):
        """부분 청산 처리"""
        try:
            # 게이트 포지션 조회
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            
            if not gate_positions or gate_positions[0].get('size', 0) == 0:
                self.logger.warning(f"게이트 포지션을 찾을 수 없습니다: {pos_id}")
                return
            
            gate_pos = gate_positions[0]
            current_gate_size = int(gate_pos['size'])
            
            # 청산할 수량 계산
            close_size = int(abs(current_gate_size) * reduction_ratio)
            
            if close_size == 0:
                return
            
            # 방향에 따라 부호 조정
            if current_gate_size > 0:  # 롱
                close_size = -close_size
            else:  # 숏
                close_size = close_size
            
            self.logger.info(f"부분 청산 실행: {close_size} 계약 ({reduction_ratio*100:.1f}%)")
            
            # 시장가로 부분 청산
            result = await self.gate.place_order(
                contract=self.GATE_CONTRACT,
                size=close_size,
                price=None,  # 시장가
                reduce_only=True
            )
            
            await self.telegram.send_message(
                f"📉 부분 청산 완료\n"
                f"비율: {reduction_ratio*100:.1f}%\n"
                f"수량: {abs(close_size)} 계약"
            )
            
        except Exception as e:
            self.logger.error(f"부분 청산 처리 실패: {e}")
            await self.telegram.send_message(
                f"❌ 부분 청산 실패\n"
                f"포지션: {pos_id}\n"
                f"오류: {str(e)[:200]}"
            )
    
    async def _handle_position_close(self, pos_id: str):
        """포지션 종료 처리"""
        try:
            self.logger.info(f"🔚 포지션 종료 감지: {pos_id}")
            
            # 게이트 포지션 전체 종료
            result = await self.gate.close_position(self.GATE_CONTRACT)
            
            # TP/SL 주문 취소
            if pos_id in self.tp_sl_orders:
                orders = self.tp_sl_orders[pos_id]
                
                # TP 주문 취소
                for order_id in orders.get('tp', []):
                    try:
                        await self.gate.cancel_price_triggered_order(order_id)
                    except:
                        pass
                
                # SL 주문 취소
                for order_id in orders.get('sl', []):
                    try:
                        await self.gate.cancel_price_triggered_order(order_id)
                    except:
                        pass
                
                del self.tp_sl_orders[pos_id]
            
            # 상태 정리
            if pos_id in self.mirrored_positions:
                del self.mirrored_positions[pos_id]
            if pos_id in self.position_sizes:
                del self.position_sizes[pos_id]
            
            self.daily_stats['full_closes'] += 1
            
            await self.telegram.send_message(
                f"✅ 포지션 종료 완료\n"
                f"포지션 ID: {pos_id}"
            )
            
        except Exception as e:
            self.logger.error(f"포지션 종료 처리 실패: {e}")
            await self.telegram.send_message(
                f"❌ 포지션 종료 실패\n"
                f"포지션: {pos_id}\n"
                f"오류: {str(e)[:200]}"
            )
    
    async def _check_tp_sl_updates(self, pos_id: str, bitget_pos: Dict):
        """TP/SL 업데이트 확인"""
        # 실제 구현에서는 비트겟 API로 TP/SL 주문을 조회하고
        # 변경사항이 있으면 게이트 주문도 업데이트해야 함
        pass
    
    async def monitor_sync_status(self):
        """포지션 동기화 상태 모니터링"""
        while self.monitoring:
            try:
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)
                
                # 비트겟 포지션
                bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                bitget_active = [
                    pos for pos in bitget_positions 
                    if float(pos.get('total', 0)) > 0
                ]
                
                # 게이트 포지션
                gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
                gate_active = [
                    pos for pos in gate_positions 
                    if pos.get('size', 0) != 0
                ]
                
                # 포지션 수 비교
                bitget_count = len(bitget_active)
                gate_count = len(gate_active)
                
                # 미러링된 포지션만 카운트 (시작 시 존재했던 것 제외)
                mirrored_bitget_count = sum(
                    1 for pos in bitget_active 
                    if self._generate_position_id(pos) not in self.startup_positions
                )
                
                if mirrored_bitget_count != gate_count:
                    self.logger.warning(
                        f"⚠️ 포지션 불일치 감지\n"
                        f"비트겟 (미러링 대상): {mirrored_bitget_count}\n"
                        f"게이트: {gate_count}"
                    )
                    
                    # 상세 분석
                    await self._analyze_sync_mismatch(bitget_active, gate_active)
                else:
                    self.logger.info(f"✅ 포지션 동기화 정상: {gate_count}개")
                
            except Exception as e:
                self.logger.error(f"동기화 모니터링 오류: {e}")
    
    async def _analyze_sync_mismatch(self, bitget_positions: List[Dict], gate_positions: List[Dict]):
        """동기화 불일치 분석"""
        try:
            # 비트겟에만 있는 포지션
            for bitget_pos in bitget_positions:
                pos_id = self._generate_position_id(bitget_pos)
                
                # 시작 시 존재했던 포지션은 제외
                if pos_id in self.startup_positions:
                    continue
                
                if pos_id not in self.mirrored_positions:
                    self.logger.warning(f"비트겟에만 존재하는 포지션: {pos_id}")
                    
                    # 자동 미러링 시도
                    result = await self._mirror_new_position(bitget_pos)
                    if result.success:
                        self.logger.info(f"동기화 복구 성공: {pos_id}")
                    else:
                        await self.telegram.send_message(
                            f"⚠️ 동기화 문제\n"
                            f"비트겟 포지션이 게이트에 없습니다\n"
                            f"포지션: {pos_id}\n"
                            f"자동 복구 실패: {result.error}"
                        )
            
            # 게이트에만 있는 포지션
            if len(gate_positions) > 0 and len(self.mirrored_positions) == 0:
                self.logger.warning("게이트에 추적되지 않는 포지션 존재")
                
                # 자동 정리
                for gate_pos in gate_positions:
                    if gate_pos.get('size', 0) != 0:
                        self.logger.info("추적되지 않는 게이트 포지션 종료")
                        await self.gate.close_position(self.GATE_CONTRACT)
                        
                        await self.telegram.send_message(
                            f"🔄 게이트 단독 포지션 정리\n"
                            f"대응하는 비트겟 포지션이 없어 종료했습니다"
                        )
            
        except Exception as e:
            self.logger.error(f"동기화 분석 중 오류: {e}")
    
    async def generate_daily_reports(self):
        """일일 리포트 생성"""
        while self.monitoring:
            try:
                now = datetime.now()
                
                # 매일 지정된 시간에 리포트 생성
                if now.hour == self.DAILY_REPORT_HOUR and now > self.last_report_time + timedelta(hours=23):
                    report = await self._create_daily_report()
                    await self.telegram.send_message(report)
                    
                    # 통계 초기화
                    self._reset_daily_stats()
                    self.last_report_time = now
                
                await asyncio.sleep(3600)  # 1시간마다 체크
                
            except Exception as e:
                self.logger.error(f"일일 리포트 생성 오류: {e}")
                await asyncio.sleep(3600)
    
    async def _create_daily_report(self) -> str:
        """일일 리포트 생성"""
        try:
            # 계정 정보 조회
            bitget_account = await self.bitget.get_account_info()
            gate_account = await self.gate.get_account_balance()
            
            bitget_equity = float(bitget_account.get('accountEquity', 0))
            gate_equity = float(gate_account.get('total', 0))
            
            # 성공률 계산
            success_rate = 0
            if self.daily_stats['total_mirrored'] > 0:
                success_rate = (self.daily_stats['successful_mirrors'] / 
                              self.daily_stats['total_mirrored']) * 100
            
            report = f"""📊 일일 미러 트레이딩 리포트
📅 {datetime.now().strftime('%Y-%m-%d')}
━━━━━━━━━━━━━━━━━━━

📈 미러링 통계
- 총 시도: {self.daily_stats['total_mirrored']}회
- 성공: {self.daily_stats['successful_mirrors']}회
- 실패: {self.daily_stats['failed_mirrors']}회
- 성공률: {success_rate:.1f}%

📉 포지션 관리
- 부분 청산: {self.daily_stats['partial_closes']}회
- 전체 청산: {self.daily_stats['full_closes']}회
- 총 거래량: ${self.daily_stats['total_volume']:,.2f}

💰 계정 잔고
- 비트겟: ${bitget_equity:,.2f}
- 게이트: ${gate_equity:,.2f}

🔄 현재 미러링 포지션
- 활성: {len(self.mirrored_positions)}개
- 실패 기록: {len(self.failed_mirrors)}건

"""
            
            # 오류가 있었다면 추가
            if self.daily_stats['errors']:
                report += f"\n⚠️ 오류 발생: {len(self.daily_stats['errors'])}건\n"
                for i, error in enumerate(self.daily_stats['errors'][-3:], 1):  # 최근 3개만
                    report += f"{i}. {error['error'][:50]}...\n"
            
            report += "\n━━━━━━━━━━━━━━━━━━━"
            
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
        
        # 최종 리포트 생성
        try:
            final_report = await self._create_daily_report()
            await self.telegram.send_message(
                f"🛑 미러 트레이딩 종료\n\n{final_report}"
            )
        except:
            pass
        
        self.logger.info("미러 트레이딩 시스템 중지")
