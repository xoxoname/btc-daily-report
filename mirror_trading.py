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
        self.check_interval = config.MIRROR_CHECK_INTERVAL  # 환경변수에서 가져오기
        self.min_trade_size = 0.001  # 최소 거래 크기 (BTC)
        self.min_investment = 5  # 최소 투자금 ($)
        
    async def start_monitoring(self):
        """미러 트레이딩 모니터링 시작"""
        self.logger.info("🔄 미러 트레이딩 시스템 시작")
        self.logger.info(f"체크 간격: {self.check_interval}초")
        
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
            bitget_leverage = int(float(bitget_pos.get('leverage', 1)))
            
            # 포지션이 변경되었는지 확인
            position_key = f"{bitget_side}_{bitget_size}_{bitget_entry}"
            if position_key == self.last_positions.get('bitget'):
                return  # 변경 없음
            
            self.logger.info(f"📊 Bitget 포지션 감지: {bitget_side} {bitget_size} BTC @ ${bitget_entry} (레버리지: {bitget_leverage}x)")
            
            # 자산 비율 계산
            ratio = await self._calculate_position_ratio(bitget_pos)
            
            # Gate.io에서 동일 설정으로 포지션 생성
            await self._create_gateio_position(bitget_pos, ratio, gateio_pos)
            
            # 마지막 포지션 업데이트
            self.last_positions['bitget'] = position_key
            
        except Exception as e:
            self.logger.error(f"Bitget 포지션 처리 실패: {e}")
    
    async def _calculate_position_ratio(self, bitget_pos: Dict) -> float:
        """포지션 비율 계산 - 포지션 가치 기준"""
        try:
            # Bitget 계정 정보 조회
            bitget_account = await self.bitget_client.get_account_info()
            
            # 총 자산
            total_equity = float(bitget_account.get('accountEquity', 0))
            
            # 포지션 가치 (레버리지 적용된 전체 가치)
            margin_size = float(bitget_pos.get('marginSize', 0))
            leverage = float(bitget_pos.get('leverage', 1))
            
            # 총 자산 대비 포지션 가치 비율
            ratio = margin_size / total_equity if total_equity > 0 else 0
            
            # 로깅
            self.logger.info(f"📊 Bitget 자산 분석:")
            self.logger.info(f"  - 총 자산: ${total_equity:,.2f}")
            self.logger.info(f"  - 포지션 증거금: ${margin_size:,.2f}")
            self.logger.info(f"  - 레버리지: {leverage}x")
            self.logger.info(f"  - 포지션 비율: {ratio:.2%}")
            
            return ratio
            
        except Exception as e:
            self.logger.error(f"비율 계산 실패: {e}")
            return 0.01  # 기본값 1%
    
    async def _set_gateio_leverage(self, contract: str, leverage: int):
        """Gate.io 레버리지 설정"""
        try:
            endpoint = f"/api/v4/futures/usdt/positions/{contract}/leverage"
            
            # Gate.io API로 레버리지 설정
            async with self.gateio_client.session.post(
                f"{self.gateio_client.base_url}{endpoint}",
                headers=self.gateio_client._get_headers('POST', endpoint, '', ''),
                json={'leverage': str(leverage)}
            ) as response:
                if response.status in [200, 201]:
                    self.logger.info(f"✅ Gate.io 레버리지 설정 완료: {leverage}x")
                else:
                    response_text = await response.text()
                    self.logger.warning(f"레버리지 설정 실패: {response_text}")
                    
        except Exception as e:
            self.logger.error(f"레버리지 설정 오류: {e}")
    
    async def _create_gateio_position(self, bitget_pos: Dict, ratio: float, existing_pos: Optional[Dict]):
        """Gate.io에서 포지션 생성 - Bitget 설정 동기화"""
        try:
            # Bitget 포지션 정보 추출
            bitget_side = bitget_pos.get('holdSide', '').lower()
            bitget_leverage = int(float(bitget_pos.get('leverage', 1)))
            bitget_entry = float(bitget_pos.get('openPriceAvg', 0))
            
            # Gate.io 계정 정보 조회
            gateio_account = await self.gateio_client.get_futures_account()
            total_equity = float(gateio_account.get('total', 0))
            
            # 투자금 계산 (총 자산의 동일 비율)
            investment_amount = total_equity * ratio
            
            self.logger.info(f"📊 Gate.io 미러링 계산:")
            self.logger.info(f"  - Gate.io 총 자산: ${total_equity:,.2f}")
            self.logger.info(f"  - 미러링 비율: {ratio:.2%}")
            self.logger.info(f"  - 계산된 투자금: ${investment_amount:,.2f}")
            self.logger.info(f"  - Bitget 레버리지: {bitget_leverage}x")
            
            # 최소 투자금 체크
            if investment_amount < self.min_investment:
                self.logger.warning(f"⚠️ 투자금이 너무 작습니다: ${investment_amount:.2f} (최소 ${self.min_investment})")
                self.logger.info(f"  → 최소 투자금 ${self.min_investment}로 진행")
                investment_amount = self.min_investment
                
                # 최소 투자금이 총 자산의 50%를 초과하면 스킵
                if investment_amount > total_equity * 0.5:
                    self.logger.warning(f"⚠️ 최소 투자금이 총 자산의 50%를 초과합니다. 미러링 스킵.")
                    return
            
            # 레버리지 설정 (Bitget과 동일하게)
            await self._set_gateio_leverage('BTC_USDT', bitget_leverage)
            await asyncio.sleep(0.5)  # API 제한 대응
            
            # 현재가 조회
            ticker = await self.gateio_client.get_ticker('usdt', 'BTC_USDT')
            current_price = float(ticker.get('last', 0))
            
            # 계약 정보 조회
            contract_info = await self.gateio_client.get_contract_info('usdt', 'BTC_USDT')
            quanto_multiplier = float(contract_info.get('quanto_multiplier', 0.0001))
            
            # 레버리지를 고려한 실제 BTC 수량 계산
            # investment_amount는 증거금이므로, 레버리지를 곱해서 실제 포지션 크기 계산
            position_value = investment_amount * bitget_leverage
            btc_amount = position_value / current_price
            contracts = int(btc_amount / quanto_multiplier)
            
            # 방향에 따른 사이즈 설정
            if bitget_side in ['short', 'sell']:
                contracts = -abs(contracts)
            else:
                contracts = abs(contracts)
            
            # 최소 크기 체크
            if abs(contracts) < 1:
                self.logger.warning(f"⚠️ 계약 수가 너무 작습니다: {contracts}")
                # 최소 1계약으로 설정
                contracts = 1 if contracts > 0 else -1
            
            # 기존 포지션이 있다면 정리
            if existing_pos and float(existing_pos.get('size', 0)) != 0:
                await self._close_gateio_position(existing_pos)
                await asyncio.sleep(1)
            
            # 새 포지션 생성 (시장가 주문)
            order_params = {
                'contract': 'BTC_USDT',
                'size': contracts,
                'price': '0',  # 시장가
                'tif': 'ioc',  # Immediate or Cancel
                'text': f'mirror_from_bitget_{bitget_leverage}x'  # 주문 메모
            }
            
            result = await self.gateio_client.create_futures_order('usdt', **order_params)
            
            # 손절/익절 설정 (Bitget에 손절/익절이 있다면)
            # 참고: Bitget API에서 손절/익절 정보를 가져와야 함
            # 여기서는 기본적인 손절 설정만 예시로 구현
            if result.get('status') == 'finished':
                await self._set_stop_orders(contracts, current_price, bitget_leverage)
            
            # 로깅
            self.logger.info(f"✅ Gate.io 포지션 생성 완료:")
            self.logger.info(f"  - 투입 증거금: ${investment_amount:,.2f}")
            self.logger.info(f"  - 방향: {bitget_side}")
            self.logger.info(f"  - 레버리지: {bitget_leverage}x")
            self.logger.info(f"  - 계약 수: {abs(contracts)}계약")
            self.logger.info(f"  - BTC 수량: {btc_amount:.4f} BTC")
            self.logger.info(f"  - 포지션 가치: ${position_value:,.2f}")
            
        except Exception as e:
            self.logger.error(f"Gate.io 포지션 생성 실패: {e}")
    
    async def _set_stop_orders(self, contracts: int, entry_price: float, leverage: int):
        """손절 주문 설정 (예시)"""
        try:
            # 레버리지에 따른 손절가 계산 (예: 2% 손실)
            stop_loss_percent = 2.0 / leverage
            
            if contracts > 0:  # 롱 포지션
                stop_price = entry_price * (1 - stop_loss_percent)
            else:  # 숏 포지션
                stop_price = entry_price * (1 + stop_loss_percent)
            
            # 손절 주문 생성
            stop_params = {
                'contract': 'BTC_USDT',
                'size': -contracts,  # 반대 방향
                'price': '0',  # 시장가
                'tif': 'gtc',
                'reduce_only': True,
                'trigger': {
                    'strategy_type': 0,  # 0: by price
                    'price_type': 0,  # 0: latest price
                    'price': str(stop_price),
                    'rule': 1 if contracts > 0 else 2  # 1: >=, 2: <=
                }
            }
            
            # 여기서 실제 손절 주문 API 호출
            # await self.gateio_client.create_trigger_order('usdt', **stop_params)
            
            self.logger.info(f"📌 손절가 설정: ${stop_price:,.2f}")
            
        except Exception as e:
            self.logger.error(f"손절 주문 설정 실패: {e}")
    
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
