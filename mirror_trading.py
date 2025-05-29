import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class MirrorTradingSystem:
    def __init__(self, bitget_client, gateio_client, config):
        self.bitget_client = bitget_client
        self.gateio_client = gateio_client
        self.config = config
        self.logger = logging.getLogger('mirror_trading')
        
        # 상태 추적
        self.last_positions = {}
        self.pending_orders = {}
        self.sync_enabled = True
        
        # 설정
        self.check_interval = 10  # 10초마다 체크
        self.min_trade_size = 0.001  # 최소 거래 크기 (BTC)
        
    async def start_monitoring(self):
        """미러 트레이딩 모니터링 시작"""
        self.logger.info("🔄 미러 트레이딩 시스템 시작")
        
        while self.sync_enabled:
            try:
                await self.check_and_sync_positions()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"미러 트레이딩 오류: {e}")
                await asyncio.sleep(30)  # 오류 시 30초 대기
    
    async def check_and_sync_positions(self):
        """포지션 체크 및 동기화"""
        try:
            # 1. Bitget 포지션 조회
            bitget_positions = await self.bitget_client.get_positions('BTCUSDT')
            
            # 2. Gate.io 포지션 조회
            gateio_positions = await self.gateio_client.get_positions('usdt')
            
            # 3. 포지션 비교 및 동기화
            await self._sync_positions(bitget_positions, gateio_positions)
            
        except Exception as e:
            self.logger.error(f"포지션 체크 실패: {e}")
    
    async def _sync_positions(self, bitget_positions: List[Dict], gateio_positions: List[Dict]):
        """포지션 동기화"""
        # Bitget 활성 포지션 찾기
        bitget_active = None
        for pos in bitget_positions:
            if float(pos.get('total', 0)) > 0:
                bitget_active = pos
                break
        
        # Gate.io BTC 포지션 찾기
        gateio_btc = None
        for pos in gateio_positions:
            if pos.get('contract', '') == 'BTC_USDT':
                gateio_btc = pos
                break
        
        # 동기화 필요 여부 확인
        if bitget_active:
            await self._handle_bitget_position(bitget_active, gateio_btc)
        elif gateio_btc and float(gateio_btc.get('size', 0)) != 0:
            # Bitget에는 포지션이 없는데 Gate.io에는 있는 경우
            await self._close_gateio_position(gateio_btc)
    
    async def _handle_bitget_position(self, bitget_pos: Dict, gateio_pos: Optional[Dict]):
        """Bitget 포지션 처리"""
        try:
            # Bitget 포지션 정보
            bitget_side = bitget_pos.get('holdSide', '').lower()
            bitget_size = float(bitget_pos.get('total', 0))
            bitget_entry = float(bitget_pos.get('openPriceAvg', 0))
            
            # 포지션이 변경되었는지 확인
            position_key = f"{bitget_side}_{bitget_size}_{bitget_entry}"
            if position_key == self.last_positions.get('bitget'):
                return  # 변경 없음
            
            self.logger.info(f"📊 Bitget 포지션 감지: {bitget_side} {bitget_size} BTC @ ${bitget_entry}")
            
            # 자산 비율 계산
            ratio = await self._calculate_position_ratio(bitget_pos)
            
            # Gate.io에서 동일 비율로 포지션 생성
            await self._create_gateio_position(bitget_side, ratio, gateio_pos)
            
            # 마지막 포지션 업데이트
            self.last_positions['bitget'] = position_key
            
        except Exception as e:
            self.logger.error(f"Bitget 포지션 처리 실패: {e}")
    
    async def _calculate_position_ratio(self, bitget_pos: Dict) -> float:
        """포지션 비율 계산"""
        try:
            # Bitget 계정 정보 조회
            bitget_account = await self.bitget_client.get_account_info()
            
            # 총 자산
            total_equity = float(bitget_account.get('accountEquity', 0))
            
            # 사용된 증거금 (레버리지 고려)
            margin_used = float(bitget_pos.get('marginSize', 0))
            leverage = float(bitget_pos.get('leverage', 1))
            actual_investment = margin_used / leverage if leverage > 0 else margin_used
            
            # 비율 계산
            ratio = actual_investment / total_equity if total_equity > 0 else 0
            
            self.logger.info(f"📊 포지션 비율: {ratio:.2%} (투자금 ${actual_investment:.2f} / 총자산 ${total_equity:.2f})")
            
            return ratio
            
        except Exception as e:
            self.logger.error(f"비율 계산 실패: {e}")
            return 0.1  # 기본값 10%
    
    async def _create_gateio_position(self, side: str, ratio: float, existing_pos: Optional[Dict]):
        """Gate.io에서 포지션 생성"""
        try:
            # Gate.io 계정 정보 조회
            gateio_account = await self.gateio_client.get_futures_account()
            total_equity = float(gateio_account.get('total', 0))
            
            # 투자금 계산
            investment_amount = total_equity * ratio
            
            # 현재가 조회
            ticker = await self.gateio_client.get_ticker('usdt', 'BTC_USDT')
            current_price = float(ticker.get('last', 0))
            
            # 계약 정보 조회 (계약 크기 확인)
            contract_info = await self.gateio_client.get_contract_info('usdt', 'BTC_USDT')
            quanto_multiplier = float(contract_info.get('quanto_multiplier', 0.0001))
            
            # 계약 수 계산
            # Gate.io는 계약 단위로 거래 (1계약 = quanto_multiplier BTC)
            btc_amount = investment_amount / current_price
            contracts = int(btc_amount / quanto_multiplier)
            
            # 방향에 따른 사이즈 설정 (양수: 롱, 음수: 숏)
            if side in ['short', 'sell']:
                contracts = -abs(contracts)
            else:
                contracts = abs(contracts)
            
            # 최소 크기 체크
            if abs(contracts) < 1:
                self.logger.warning(f"⚠️ 계약 수가 너무 작습니다: {contracts}")
                return
            
            # 기존 포지션이 있다면 정리
            if existing_pos and float(existing_pos.get('size', 0)) != 0:
                await self._close_gateio_position(existing_pos)
                await asyncio.sleep(1)  # 잠시 대기
            
            # 새 포지션 생성
            order_params = {
                'contract': 'BTC_USDT',
                'size': contracts,
                'price': '0',  # 시장가 주문
                'tif': 'ioc'  # immediate or cancel
            }
            
            result = await self.gateio_client.create_futures_order('usdt', **order_params)
            
            self.logger.info(f"✅ Gate.io 포지션 생성: {side} {contracts}계약 (${investment_amount:.2f}, {ratio:.2%})")
            
        except Exception as e:
            self.logger.error(f"Gate.io 포지션 생성 실패: {e}")
    
    async def _close_gateio_position(self, position: Dict):
        """Gate.io 포지션 종료"""
        try:
            current_size = float(position.get('size', 0))
            
            if current_size == 0:
                return
            
            # 반대 방향으로 같은 수량 주문
            close_size = -current_size
            
            order_params = {
                'contract': 'BTC_USDT',
                'size': int(close_size),
                'price': '0',  # 시장가
                'tif': 'ioc',
                'reduce_only': True
            }
            
            result = await self.gateio_client.create_futures_order('usdt', **order_params)
            
            self.logger.info(f"✅ Gate.io 포지션 종료: {close_size}계약")
            
        except Exception as e:
            self.logger.error(f"Gate.io 포지션 종료 실패: {e}")
    
    def stop(self):
        """미러 트레이딩 중지"""
        self.sync_enabled = False
        self.logger.info("🛑 미러 트레이딩 시스템 중지")
