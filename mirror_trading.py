# mirror_trading.py
import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple, Set
import json
import pytz

logger = logging.getLogger(__name__)

class MirrorTradingSystem:
    """비트겟 → 게이트 미러 트레이딩 시스템"""
    
    def __init__(self, bitget_client, gateio_client, config, telegram_bot=None):
        self.bitget_client = bitget_client
        self.gateio_client = gateio_client
        self.config = config
        self.telegram_bot = telegram_bot
        self.logger = logging.getLogger('mirror_trading')
        
        # 상태 추적
        self.is_running = False
        self.check_interval = config.MIRROR_CHECK_INTERVAL  # 초
        self.kst = pytz.timezone('Asia/Seoul')
        
        # 포지션 추적 (신규 진입만 미러링하기 위함)
        self.tracked_positions = {}  # {symbol: {'side': 'long/short', 'entry_time': datetime, 'margin_ratio': float}}
        self.initial_scan_done = False  # 첫 스캔 완료 플래그
        
        # 초기 포지션 스냅샷 (시스템 시작 시점의 포지션만 제외)
        self.initial_positions = set()  # 초기 포지션의 고유 ID 저장
        
        # 주문 추적 (TP/SL 수정 감지용)
        self.tracked_orders = {}  # {symbol: {'tp_price': float, 'sl_price': float, 'tp_order_id': str, 'sl_order_id': str}}
        
        # 주문 로그
        self.order_logs = []
        
        # 에러 복구
        self.retry_count = {}  # {action_key: count}
        self.max_retries = 3
        self.retry_delay = 5  # 초
        
        # 모니터링
        self.position_mismatch_alerts = {}  # {symbol: last_alert_time}
        self.alert_cooldown = timedelta(minutes=30)  # 30분 쿨다운
        
        # 성과 추적
        self.daily_stats = {
            'mirror_entries': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'errors': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0
        }
        
        self.logger.info(f"🔄 미러 트레이딩 시스템 초기화 (체크 간격: {self.check_interval}초)")
    
    async def start_monitoring(self):
        """미러링 모니터링 시작"""
        self.is_running = True
        self.logger.info("🚀 미러 트레이딩 모니터링 시작")
        
        # 초기 포지션 스캔
        await self._initial_position_scan()
        
        # 메인 모니터링 루프
        monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        # 일일 리포트 스케줄러
        report_task = asyncio.create_task(self._daily_report_scheduler())
        
        # 두 태스크 동시 실행
        await asyncio.gather(monitoring_task, report_task, return_exceptions=True)
    
    async def _monitoring_loop(self):
        """메인 모니터링 루프"""
        consecutive_errors = 0
        
        while self.is_running:
            try:
                await self._check_and_mirror()
                consecutive_errors = 0  # 성공 시 리셋
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"미러링 체크 중 오류 (연속 {consecutive_errors}회): {e}")
                self.daily_stats['errors'] += 1
                
                # 연속 오류 시 재연결 시도
                if consecutive_errors >= 3:
                    await self._reconnect_clients()
                    consecutive_errors = 0
                
                await asyncio.sleep(self.check_interval * 2)  # 오류 시 대기 시간 증가
    
    async def _reconnect_clients(self):
        """클라이언트 재연결"""
        self.logger.warning("🔄 클라이언트 재연결 시도...")
        
        try:
            # 세션 재초기화
            if hasattr(self.bitget_client, '_initialize_session'):
                self.bitget_client._initialize_session()
            if hasattr(self.gateio_client, '_initialize_session'):
                self.gateio_client._initialize_session()
            
            # 연결 테스트
            await self.bitget_client.get_account_info()
            await self.gateio_client.get_futures_account()
            
            self.logger.info("✅ 클라이언트 재연결 성공")
            
            if self.telegram_bot:
                await self.telegram_bot.send_message("🔄 미러 트레이딩 클라이언트 재연결 완료")
                
        except Exception as e:
            self.logger.error(f"클라이언트 재연결 실패: {e}")
            if self.telegram_bot:
                await self.telegram_bot.send_message(f"❌ 미러 트레이딩 재연결 실패: {str(e)[:100]}")
    
    async def _daily_report_scheduler(self):
        """일일 리포트 스케줄러"""
        while self.is_running:
            try:
                now = datetime.now(self.kst)
                
                # 오후 9시 계산
                target_time = now.replace(hour=21, minute=0, second=0, microsecond=0)
                if now >= target_time:
                    # 이미 9시가 지났으면 다음날 9시
                    target_time += timedelta(days=1)
                
                # 대기 시간 계산
                wait_seconds = (target_time - now).total_seconds()
                
                self.logger.info(f"📅 다음 일일 리포트: {target_time.strftime('%Y-%m-%d %H:%M')} ({wait_seconds/3600:.1f}시간 후)")
                
                await asyncio.sleep(wait_seconds)
                
                # 리포트 생성 및 전송
                await self._send_daily_report()
                
                # 통계 리셋
                self.daily_stats = {
                    'mirror_entries': 0,
                    'partial_closes': 0,
                    'full_closes': 0,
                    'errors': 0,
                    'successful_mirrors': 0,
                    'failed_mirrors': 0
                }
                
            except Exception as e:
                self.logger.error(f"일일 리포트 스케줄러 오류: {e}")
                await asyncio.sleep(3600)  # 오류 시 1시간 후 재시도
    
    def stop(self):
        """미러링 중지"""
        self.is_running = False
        self.logger.info("🛑 미러 트레이딩 모니터링 중지")
    
    async def _initial_position_scan(self):
        """초기 포지션 스캔 - 기존 포지션의 고유 ID만 저장"""
        try:
            self.logger.info("📋 초기 포지션 스캔 시작...")
            
            # 비트겟 현재 포지션 확인
            bitget_positions = await self.bitget_client.get_positions('BTCUSDT')
            
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    symbol = pos.get('symbol', 'BTCUSDT')
                    side = 'long' if pos.get('holdSide', '').lower() in ['long', 'buy'] else 'short'
                    cTime = pos.get('cTime', '')  # 포지션 생성 시간
                    
                    # 포지션의 고유 ID 생성 (심볼 + 방향 + 생성시간)
                    position_id = f"{symbol}_{side}_{cTime}"
                    self.initial_positions.add(position_id)
                    
                    # 추적은 하지만 미러링은 하지 않을 것임을 표시
                    self.tracked_positions[symbol] = {
                        'side': side,
                        'entry_time': datetime.now(),
                        'margin_ratio': 0,
                        'position_id': position_id,
                        'cTime': cTime
                    }
                    
                    # 기존 TP/SL 추적
                    tp_price = float(pos.get('takeProfitPrice', 0) or pos.get('takeProfit', 0) or 0)
                    sl_price = float(pos.get('stopLossPrice', 0) or pos.get('stopLoss', 0) or 0)
                    
                    if tp_price > 0 or sl_price > 0:
                        self.tracked_orders[symbol] = {
                            'tp_price': tp_price,
                            'sl_price': sl_price,
                            'tp_order_id': None,
                            'sl_order_id': None
                        }
                    
                    self.logger.info(f"📌 초기 포지션 발견: {symbol} {side} (ID: {position_id})")
            
            self.initial_scan_done = True
            self.logger.info(f"✅ 초기 포지션 스캔 완료 - {len(self.initial_positions)}개 포지션 발견")
            
        except Exception as e:
            self.logger.error(f"초기 포지션 스캔 실패: {e}")
    
    async def _check_and_mirror(self):
        """포지션 체크 및 미러링"""
        try:
            # 1. 비트겟 포지션 확인
            bitget_positions = await self.bitget_client.get_positions('BTCUSDT')
            bitget_account = await self.bitget_client.get_account_info()
            bitget_total_equity = float(bitget_account.get('accountEquity', 0))
            
            # 2. 게이트 계정 정보
            gateio_account = await self.gateio_client.get_futures_account()
            gateio_total_equity = float(gateio_account.get('total', 0))
            
            self.logger.debug(f"💰 계정 잔고 - Bitget: ${bitget_total_equity:.2f}, Gate.io: ${gateio_total_equity:.2f}")
            
            # 3. 활성 포지션 처리
            active_symbols = set()
            
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    symbol = pos.get('symbol', 'BTCUSDT')
                    active_symbols.add(symbol)
                    
                    await self._process_position(pos, bitget_total_equity, gateio_total_equity)
                    
                    # TP/SL 수정 체크
                    await self._check_order_modifications(symbol, pos)
            
            # 4. 종료된 포지션 처리
            closed_symbols = set(self.tracked_positions.keys()) - active_symbols
            for symbol in closed_symbols:
                await self._handle_position_close(symbol)
            
            # 5. 포지션 일치성 체크
            await self._check_position_consistency()
            
        except Exception as e:
            self.logger.error(f"미러링 체크 실패: {e}")
    
    async def _process_position(self, bitget_pos: Dict, bitget_equity: float, gateio_equity: float):
        """개별 포지션 처리"""
        try:
            symbol = bitget_pos.get('symbol', 'BTCUSDT')
            side = 'long' if bitget_pos.get('holdSide', '').lower() in ['long', 'buy'] else 'short'
            cTime = bitget_pos.get('cTime', '')
            
            # 포지션의 고유 ID 생성
            position_id = f"{symbol}_{side}_{cTime}"
            
            # 마진 계산 (USDT 기준)
            margin = float(bitget_pos.get('marginSize', 0))
            margin_ratio = margin / bitget_equity if bitget_equity > 0 else 0
            
            # 신규 포지션 감지
            if symbol not in self.tracked_positions:
                self.logger.info(f"🆕 신규 포지션 감지: {symbol} {side} (Margin: ${margin:.2f}, 비율: {margin_ratio:.2%})")
                
                # 포지션 추적 시작
                self.tracked_positions[symbol] = {
                    'side': side,
                    'entry_time': datetime.now(),
                    'margin_ratio': margin_ratio,
                    'position_id': position_id,
                    'cTime': cTime
                }
                
                # 초기 스캔에서 발견된 포지션이 아닌 경우만 미러링
                if position_id not in self.initial_positions:
                    self.logger.info(f"🔄 신규 포지션 미러링 시작: {symbol} {side}")
                    # 게이트에 미러링
                    success = await self._mirror_new_position_with_retry(bitget_pos, margin_ratio, gateio_equity)
                    
                    if success:
                        self.daily_stats['mirror_entries'] += 1
                        self.daily_stats['successful_mirrors'] += 1
                    else:
                        self.daily_stats['failed_mirrors'] += 1
                else:
                    self.logger.info(f"⏭️ 초기 포지션이므로 미러링 스킵: {symbol} {side}")
                
            else:
                # 기존 포지션 업데이트 체크
                tracked = self.tracked_positions[symbol]
                
                # 포지션 ID가 변경되었는지 확인 (같은 심볼이지만 다른 포지션)
                if tracked.get('position_id') != position_id:
                    self.logger.info(f"🔄 포지션 ID 변경 감지 - 새로운 포지션: {symbol} {side}")
                    
                    # 이전 포지션 정보 업데이트
                    self.tracked_positions[symbol] = {
                        'side': side,
                        'entry_time': datetime.now(),
                        'margin_ratio': margin_ratio,
                        'position_id': position_id,
                        'cTime': cTime
                    }
                    
                    # 초기 포지션이 아니면 미러링
                    if position_id not in self.initial_positions:
                        success = await self._mirror_new_position_with_retry(bitget_pos, margin_ratio, gateio_equity)
                        
                        if success:
                            self.daily_stats['mirror_entries'] += 1
                            self.daily_stats['successful_mirrors'] += 1
                        else:
                            self.daily_stats['failed_mirrors'] += 1
                else:
                    # 부분 청산 체크
                    current_margin_ratio = margin / bitget_equity if bitget_equity > 0 else 0
                    if abs(current_margin_ratio - tracked['margin_ratio']) > 0.01:  # 1% 이상 변화
                        await self._handle_partial_close(symbol, bitget_pos, current_margin_ratio, gateio_equity)
                        tracked['margin_ratio'] = current_margin_ratio
                        self.daily_stats['partial_closes'] += 1
            
        except Exception as e:
            self.logger.error(f"포지션 처리 실패: {e}")
    
    async def _mirror_new_position_with_retry(self, bitget_pos: Dict, margin_ratio: float, gateio_equity: float) -> bool:
        """신규 포지션 미러링 (재시도 포함)"""
        action_key = f"mirror_entry_{bitget_pos.get('symbol')}_{datetime.now().strftime('%Y%m%d%H')}"
        
        for attempt in range(self.max_retries):
            try:
                await self._mirror_new_position(bitget_pos, margin_ratio, gateio_equity)
                self.retry_count.pop(action_key, None)  # 성공 시 카운트 제거
                return True
                
            except Exception as e:
                self.logger.error(f"미러 주문 실패 (시도 {attempt + 1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    # 최종 실패 시 알림
                    if self.telegram_bot:
                        await self.telegram_bot.send_message(
                            f"❌ 미러링 실패 알림\n\n"
                            f"심볼: {bitget_pos.get('symbol')}\n"
                            f"방향: {bitget_pos.get('holdSide')}\n"
                            f"마진: ${float(bitget_pos.get('marginSize', 0)):.2f}\n"
                            f"오류: {str(e)[:100]}"
                        )
        
        return False
    
    async def _mirror_new_position(self, bitget_pos: Dict, margin_ratio: float, gateio_equity: float):
        """신규 포지션 미러링"""
        try:
            # 게이트 진입 마진 계산
            gateio_margin = gateio_equity * margin_ratio
            
            # 최소 주문 금액 체크
            if gateio_margin < 10:  # 최소 10 USDT
                self.logger.warning(f"⚠️ 게이트 자산 부족으로 미러링 불가 (필요: ${gateio_margin:.2f})")
                self._log_order({
                    'action': 'mirror_failed',
                    'reason': 'insufficient_balance',
                    'required_margin': gateio_margin,
                    'gateio_equity': gateio_equity
                })
                return
            
            # 비트겟 포지션 정보
            side = bitget_pos.get('holdSide', '').lower()
            leverage = int(float(bitget_pos.get('leverage', 1)))
            entry_price = float(bitget_pos.get('openPriceAvg', 0))
            
            # 현재가 조회 (진입가가 0인 경우 대비)
            if entry_price == 0:
                ticker = await self.bitget_client.get_ticker('BTCUSDT')
                entry_price = float(ticker.get('last', 0))
            
            # 게이트 주문 크기 계산 (USDT 기준)
            # Gate.io는 계약 단위로 거래하므로 변환 필요
            # 1 계약 = 0.0001 BTC
            btc_value = gateio_margin * leverage / entry_price
            contract_size = int(btc_value / 0.0001)
            
            if contract_size < 1:
                self.logger.warning(f"⚠️ 계약 크기가 너무 작음: {contract_size}")
                return
            
            # 게이트 주문 실행
            order_params = {
                'contract': 'BTC_USDT',
                'size': contract_size if side in ['long', 'buy'] else -contract_size,
                'price': str(entry_price),
                'tif': 'ioc',  # Immediate or Cancel
                'reduce_only': False,
                'text': f'mirror_from_bitget_{datetime.now().strftime("%Y%m%d%H%M%S")}'
            }
            
            self.logger.info(f"📤 게이트 미러 주문 시작:")
            self.logger.info(f"   - 방향: {side}")
            self.logger.info(f"   - 계약수: {contract_size}")
            self.logger.info(f"   - 가격: ${entry_price}")
            self.logger.info(f"   - 마진: ${gateio_margin:.2f}")
            self.logger.info(f"   - 레버리지: {leverage}x")
            
            order_result = await self.gateio_client.create_futures_order(**order_params)
            
            self._log_order({
                'action': 'mirror_entry',
                'timestamp': datetime.now().isoformat(),
                'bitget_margin': float(bitget_pos.get('marginSize', 0)),
                'bitget_equity': gateio_equity / margin_ratio,  # 역산
                'gateio_margin': gateio_margin,
                'gateio_equity': gateio_equity,
                'margin_ratio': margin_ratio,
                'side': side,
                'leverage': leverage,
                'entry_price': entry_price,
                'contract_size': contract_size,
                'order_result': order_result
            })
            
            self.logger.info(f"✅ 미러 주문 성공: {order_result.get('id')}")
            
            # 성공 알림
            if self.telegram_bot:
                await self.telegram_bot.send_message(
                    f"✅ 미러 주문 성공\n\n"
                    f"거래소: Gate.io\n"
                    f"방향: {side.upper()}\n"
                    f"계약수: {contract_size}\n"
                    f"진입가: ${entry_price:,.2f}\n"
                    f"마진: ${gateio_margin:.2f}\n"
                    f"레버리지: {leverage}x"
                )
            
            # TP/SL 설정 미러링
            await self._mirror_tp_sl(bitget_pos, contract_size, side)
            
        except Exception as e:
            self.logger.error(f"미러 주문 실패: {e}")
            self._log_order({
                'action': 'mirror_error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            raise
    
    async def _mirror_tp_sl(self, bitget_pos: Dict, contract_size: int, side: str):
        """TP/SL 설정 미러링"""
        try:
            symbol = bitget_pos.get('symbol', 'BTCUSDT')
            tp_price = float(bitget_pos.get('takeProfitPrice', 0) or bitget_pos.get('takeProfit', 0) or 0)
            sl_price = float(bitget_pos.get('stopLossPrice', 0) or bitget_pos.get('stopLoss', 0) or 0)
            
            tp_order_id = None
            sl_order_id = None
            
            # TP 설정
            if tp_price > 0:
                tp_order_params = {
                    'contract': 'BTC_USDT',
                    'size': -contract_size if side in ['long', 'buy'] else contract_size,
                    'price': str(tp_price),
                    'tif': 'gtc',
                    'reduce_only': True,
                    'text': 'tp_order'
                }
                
                tp_result = await self.gateio_client.create_futures_order(**tp_order_params)
                tp_order_id = tp_result.get('id')
                self.logger.info(f"✅ TP 설정: ${tp_price} (ID: {tp_order_id})")
            
            # SL 설정 (지정가로만)
            if sl_price > 0:
                sl_order_params = {
                    'contract': 'BTC_USDT',
                    'size': -contract_size if side in ['long', 'buy'] else contract_size,
                    'price': str(sl_price),
                    'tif': 'gtc',
                    'reduce_only': True,
                    'text': 'sl_order'
                }
                
                sl_result = await self.gateio_client.create_futures_order(**sl_order_params)
                sl_order_id = sl_result.get('id')
                self.logger.info(f"✅ SL 설정: ${sl_price} (ID: {sl_order_id})")
            
            # 주문 추적
            self.tracked_orders[symbol] = {
                'tp_price': tp_price,
                'sl_price': sl_price,
                'tp_order_id': tp_order_id,
                'sl_order_id': sl_order_id
            }
            
        except Exception as e:
            self.logger.error(f"TP/SL 설정 실패: {e}")
    
    async def _check_order_modifications(self, symbol: str, bitget_pos: Dict):
        """주문 수정 체크"""
        try:
            if symbol not in self.tracked_orders:
                return
            
            tracked = self.tracked_orders[symbol]
            current_tp = float(bitget_pos.get('takeProfitPrice', 0) or bitget_pos.get('takeProfit', 0) or 0)
            current_sl = float(bitget_pos.get('stopLossPrice', 0) or bitget_pos.get('stopLoss', 0) or 0)
            
            # TP 수정 체크
            if abs(current_tp - tracked['tp_price']) > 0.01:  # 가격 변경
                self.logger.info(f"📝 TP 수정 감지: ${tracked['tp_price']} → ${current_tp}")
                
                # 기존 주문 취소
                if tracked['tp_order_id']:
                    try:
                        await self.gateio_client.cancel_order('usdt', tracked['tp_order_id'])
                    except:
                        pass
                
                # 새 주문 생성
                if current_tp > 0:
                    # 현재 게이트 포지션 확인
                    gateio_positions = await self.gateio_client.get_positions('usdt')
                    for pos in gateio_positions:
                        if pos.get('contract') == 'BTC_USDT' and float(pos.get('size', 0)) != 0:
                            size = float(pos.get('size', 0))
                            
                            tp_params = {
                                'contract': 'BTC_USDT',
                                'size': -size,
                                'price': str(current_tp),
                                'tif': 'gtc',
                                'reduce_only': True,
                                'text': 'tp_order_modified'
                            }
                            
                            result = await self.gateio_client.create_futures_order(**tp_params)
                            tracked['tp_order_id'] = result.get('id')
                            tracked['tp_price'] = current_tp
                            break
            
            # SL 수정 체크
            if abs(current_sl - tracked['sl_price']) > 0.01:  # 가격 변경
                self.logger.info(f"📝 SL 수정 감지: ${tracked['sl_price']} → ${current_sl}")
                
                # 기존 주문 취소
                if tracked['sl_order_id']:
                    try:
                        await self.gateio_client.cancel_order('usdt', tracked['sl_order_id'])
                    except:
                        pass
                
                # 새 주문 생성
                if current_sl > 0:
                    # 현재 게이트 포지션 확인
                    gateio_positions = await self.gateio_client.get_positions('usdt')
                    for pos in gateio_positions:
                        if pos.get('contract') == 'BTC_USDT' and float(pos.get('size', 0)) != 0:
                            size = float(pos.get('size', 0))
                            
                            sl_params = {
                                'contract': 'BTC_USDT',
                                'size': -size,
                                'price': str(current_sl),
                                'tif': 'gtc',
                                'reduce_only': True,
                                'text': 'sl_order_modified'
                            }
                            
                            result = await self.gateio_client.create_futures_order(**sl_params)
                            tracked['sl_order_id'] = result.get('id')
                            tracked['sl_price'] = current_sl
                            break
            
        except Exception as e:
            self.logger.error(f"주문 수정 체크 실패: {e}")
    
    async def _handle_partial_close(self, symbol: str, bitget_pos: Dict, new_margin_ratio: float, gateio_equity: float):
        """부분 청산 처리"""
        try:
            tracked = self.tracked_positions[symbol]
            old_ratio = tracked['margin_ratio']
            
            # 청산 비율 계산
            close_ratio = 1 - (new_margin_ratio / old_ratio) if old_ratio > 0 else 0
            
            if close_ratio > 0.05:  # 5% 이상 청산
                self.logger.info(f"📉 부분 청산 감지: {symbol} {close_ratio:.1%}")
                
                # 게이트 현재 포지션 확인
                gateio_positions = await self.gateio_client.get_positions('usdt')
                
                for pos in gateio_positions:
                    if pos.get('contract') == 'BTC_USDT' and float(pos.get('size', 0)) != 0:
                        current_size = float(pos.get('size', 0))
                        close_size = int(abs(current_size) * close_ratio)
                        
                        if close_size > 0:
                            # 부분 청산 주문
                            close_order_params = {
                                'contract': 'BTC_USDT',
                                'size': -close_size if current_size > 0 else close_size,
                                'price': '0',  # 시장가
                                'tif': 'ioc',
                                'reduce_only': True,
                                'text': 'partial_close'
                            }
                            
                            result = await self.gateio_client.create_futures_order(**close_order_params)
                            
                            self.logger.info(f"✅ 부분 청산 완료: {close_size}계약")
                            self._log_order({
                                'action': 'partial_close',
                                'symbol': symbol,
                                'close_ratio': close_ratio,
                                'close_size': close_size,
                                'result': result
                            })
                        break
            
        except Exception as e:
            self.logger.error(f"부분 청산 처리 실패: {e}")
    
    async def _handle_position_close(self, symbol: str):
        """포지션 종료 처리 - 시장가 손절 포함"""
        try:
            self.logger.info(f"🔚 포지션 종료 감지: {symbol}")
            
            # 비트겟 최근 거래 체결 확인 (시장가 손절 감지)
            is_market_stop = await self._check_market_stop_loss(symbol)
            
            # 게이트 포지션 전량 청산
            gateio_positions = await self.gateio_client.get_positions('usdt')
            
            for pos in gateio_positions:
                if pos.get('contract') == 'BTC_USDT' and float(pos.get('size', 0)) != 0:
                    current_size = float(pos.get('size', 0))
                    
                    # 전량 청산 주문
                    close_order_params = {
                        'contract': 'BTC_USDT',
                        'size': -current_size,
                        'price': '0',  # 시장가
                        'tif': 'ioc',
                        'reduce_only': True,
                        'text': 'market_stop' if is_market_stop else 'full_close'
                    }
                    
                    result = await self.gateio_client.create_futures_order(**close_order_params)
                    
                    close_type = "시장가 손절" if is_market_stop else "전량 청산"
                    self.logger.info(f"✅ {close_type} 완료: {symbol}")
                    
                    self._log_order({
                        'action': 'full_close',
                        'symbol': symbol,
                        'close_size': current_size,
                        'close_type': close_type,
                        'is_market_stop': is_market_stop,
                        'result': result
                    })
                    
                    self.daily_stats['full_closes'] += 1
                    
                    # 알림 전송
                    if is_market_stop and self.telegram_bot:
                        await self.telegram_bot.send_message(
                            f"⚠️ 시장가 손절 동기화\n\n"
                            f"심볼: {symbol}\n"
                            f"타입: 시장가 손절\n"
                            f"게이트 동기화 완료"
                        )
                    
                    # 잔여 포지션 체크 및 강제 청산
                    await asyncio.sleep(1)
                    await self._cleanup_residual_position()
                    break
            
            # 추적에서 제거
            del self.tracked_positions[symbol]
            if symbol in self.tracked_orders:
                del self.tracked_orders[symbol]
            
        except Exception as e:
            self.logger.error(f"포지션 종료 처리 실패: {e}")
    
    async def _check_market_stop_loss(self, symbol: str) -> bool:
        """시장가 손절 체크"""
        try:
            # 최근 1분 이내 거래 체결 조회
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = end_time - (60 * 1000)  # 1분 전
            
            fills = await self.bitget_client.get_trade_fills(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                limit=10
            )
            
            # 손절 관련 체결 찾기
            for fill in fills:
                order_type = fill.get('orderType', '').lower()
                trade_scope = fill.get('tradeScope', '').lower()
                
                # 시장가 손절 패턴 감지
                if any(keyword in order_type for keyword in ['stop', 'market']):
                    return True
                if any(keyword in trade_scope for keyword in ['stop', 'loss']):
                    return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"시장가 손절 체크 실패: {e}")
            return False
    
    async def _cleanup_residual_position(self):
        """잔여 포지션 정리"""
        try:
            gateio_positions = await self.gateio_client.get_positions('usdt')
            
            for pos in gateio_positions:
                if pos.get('contract') == 'BTC_USDT':
                    size = float(pos.get('size', 0))
                    
                    # 극소량 잔여 포지션 감지 (0.0001 BTC = 1계약 미만)
                    if 0 < abs(size) < 1:
                        self.logger.warning(f"⚠️ 잔여 포지션 감지: {size}계약")
                        
                        # 강제 청산
                        cleanup_params = {
                            'contract': 'BTC_USDT',
                            'size': -size,
                            'price': '0',
                            'tif': 'ioc',
                            'reduce_only': True,
                            'text': 'cleanup_residual'
                        }
                        
                        await self.gateio_client.create_futures_order(**cleanup_params)
                        self.logger.info("✅ 잔여 포지션 정리 완료")
            
        except Exception as e:
            self.logger.error(f"잔여 포지션 정리 실패: {e}")
    
    async def _check_position_consistency(self):
        """포지션 일치성 체크"""
        try:
            # 비트겟 포지션
            bitget_positions = await self.bitget_client.get_positions('BTCUSDT')
            bitget_has_position = any(float(pos.get('total', 0)) > 0 for pos in bitget_positions)
            
            # 게이트 포지션
            gateio_positions = await self.gateio_client.get_positions('usdt')
            gateio_has_position = any(
                pos.get('contract') == 'BTC_USDT' and float(pos.get('size', 0)) != 0 
                for pos in gateio_positions
            )
            
            # 불일치 감지
            if bitget_has_position != gateio_has_position:
                symbol = 'BTCUSDT'
                
                # 쿨다운 체크
                last_alert = self.position_mismatch_alerts.get(symbol)
                now = datetime.now()
                
                if not last_alert or (now - last_alert) > self.alert_cooldown:
                    self.logger.warning(f"⚠️ 포지션 불일치 감지!")
                    
                    if self.telegram_bot:
                        await self.telegram_bot.send_message(
                            f"⚠️ 미러링 포지션 불일치\n\n"
                            f"Bitget: {'포지션 있음' if bitget_has_position else '포지션 없음'}\n"
                            f"Gate.io: {'포지션 있음' if gateio_has_position else '포지션 없음'}\n\n"
                            f"수동 확인이 필요합니다."
                        )
                    
                    self.position_mismatch_alerts[symbol] = now
            
        except Exception as e:
            self.logger.error(f"포지션 일치성 체크 실패: {e}")
    
    async def _send_daily_report(self):
        """일일 성과 리포트 전송"""
        try:
            now = datetime.now(self.kst)
            
            # 성과 요약
            total_actions = (self.daily_stats['mirror_entries'] + 
                           self.daily_stats['partial_closes'] + 
                           self.daily_stats['full_closes'])
            
            success_rate = 0
            if self.daily_stats['successful_mirrors'] + self.daily_stats['failed_mirrors'] > 0:
                success_rate = (self.daily_stats['successful_mirrors'] / 
                              (self.daily_stats['successful_mirrors'] + self.daily_stats['failed_mirrors'])) * 100
            
            report = f"""📊 **미러 트레이딩 일일 리포트**
📅 {now.strftime('%Y-%m-%d')} 21:00 기준
━━━━━━━━━━━━━━━━━━━

📈 **오늘의 활동**
- 신규 미러링: {self.daily_stats['mirror_entries']}건
- 부분 청산: {self.daily_stats['partial_closes']}건
- 전량 청산: {self.daily_stats['full_closes']}건
- 총 작업: {total_actions}건

📊 **성공률**
- 성공: {self.daily_stats['successful_mirrors']}건
- 실패: {self.daily_stats['failed_mirrors']}건
- 성공률: {success_rate:.1f}%

⚠️ **오류 현황**
- 오류 발생: {self.daily_stats['errors']}회

💡 **시스템 상태**
- 추적중인 포지션: {len(self.tracked_positions)}개
- 주문 로그: {len(self.order_logs)}개

━━━━━━━━━━━━━━━━━━━
💪 내일도 안정적인 미러링을 위해 노력하겠습니다!"""
            
            if self.telegram_bot:
                await self.telegram_bot.send_message(report, parse_mode='Markdown')
            
            self.logger.info(f"📊 일일 리포트 전송 완료")
            
        except Exception as e:
            self.logger.error(f"일일 리포트 전송 실패: {e}")
    
    def _log_order(self, log_data: Dict):
        """주문 로그 저장"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            **log_data
        }
        
        self.order_logs.append(log_entry)
        
        # 로그 파일로 저장 (선택사항)
        self.logger.info(f"📝 주문 로그: {json.dumps(log_entry, ensure_ascii=False, indent=2)}")
        
        # 메모리 관리 - 최대 1000개 로그 유지
        if len(self.order_logs) > 1000:
            self.order_logs = self.order_logs[-500:]
    
    def get_status(self) -> Dict:
        """미러링 상태 조회"""
        return {
            'is_running': self.is_running,
            'tracked_positions': self.tracked_positions,
            'tracked_orders': self.tracked_orders,
            'order_logs_count': len(self.order_logs),
            'last_orders': self.order_logs[-10:],  # 최근 10개
            'daily_stats': self.daily_stats,
            'retry_counts': self.retry_count,
            'initial_positions_count': len(self.initial_positions)
        }
