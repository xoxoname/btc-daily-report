import asyncio
import logging
from typing import Dict, Optional, List, Tuple
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
        self.synced_positions = {}  # 이미 동기화된 포지션 추적
        self.pending_orders = {}
        self.sync_enabled = True
        
        # 설정
        self.check_interval = config.MIRROR_CHECK_INTERVAL
        self.min_margin = 10  # 최소 증거금 $10
        
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
                await asyncio.sleep(30)
    
    async def check_and_sync_positions(self):
        """포지션 체크 및 동기화"""
        try:
            # 1. 계정 정보 먼저 조회
            bitget_account = await self.bitget_client.get_account_info()
            gateio_account = await self.gateio_client.get_futures_account()
            
            bitget_total = float(bitget_account.get('accountEquity', 0))
            gateio_total = float(gateio_account.get('total', 0))
            
            # 2. 포지션 조회
            bitget_positions = await self.bitget_client.get_positions('BTCUSDT')
            gateio_positions = await self.gateio_client.get_positions('usdt')
            
            # 3. 신규 포지션만 동기화
            await self._sync_new_positions(
                bitget_positions, 
                gateio_positions,
                bitget_total,
                gateio_total
            )
            
        except Exception as e:
            self.logger.error(f"포지션 체크 실패: {e}")
    
    async def _sync_new_positions(self, bitget_positions: List[Dict], 
                                 gateio_positions: List[Dict],
                                 bitget_total: float,
                                 gateio_total: float):
        """신규 포지션만 동기화"""
        
        # Bitget 활성 포지션 찾기
        for pos in bitget_positions:
            if float(pos.get('total', 0)) > 0:
                position_id = self._generate_position_id(pos)
                
                # 이미 동기화된 포지션인지 확인
                if position_id in self.synced_positions:
                    continue
                
                # 신규 포지션 발견
                self.logger.info(f"🆕 신규 Bitget 포지션 발견: {position_id}")
                
                # Gate.io에 미러링
                success = await self._mirror_position_to_gateio(
                    pos, bitget_total, gateio_total
                )
                
                if success:
                    self.synced_positions[position_id] = datetime.now()
                    self.logger.info(f"✅ 포지션 동기화 완료: {position_id}")
    
    def _generate_position_id(self, position: Dict) -> str:
        """포지션 고유 ID 생성"""
        side = position.get('holdSide', '')
        entry = float(position.get('openPriceAvg', 0))
        size = float(position.get('total', 0))
        return f"{side}_{entry:.2f}_{size:.6f}"
    
    async def _mirror_position_to_gateio(self, bitget_pos: Dict, 
                                       bitget_total: float, 
                                       gateio_total: float) -> bool:
        """Bitget 포지션을 Gate.io에 미러링"""
        try:
            # Bitget 포지션 정보 추출
            side = bitget_pos.get('holdSide', '').lower()
            margin_used = float(bitget_pos.get('marginSize', 0))  # 실제 사용된 증거금
            leverage = int(float(bitget_pos.get('leverage', 1)))
            entry_price = float(bitget_pos.get('openPriceAvg', 0))
            
            # 총 자산 대비 증거금 비율 계산
            margin_ratio = margin_used / bitget_total if bitget_total > 0 else 0
            
            # Gate.io에서 사용할 증거금 계산
            gateio_margin = gateio_total * margin_ratio
            
            self.logger.info(f"📊 미러링 계산:")
            self.logger.info(f"  - Bitget 총자산: ${bitget_total:,.2f}")
            self.logger.info(f"  - Bitget 증거금: ${margin_used:,.2f} ({margin_ratio:.2%})")
            self.logger.info(f"  - Bitget 레버리지: {leverage}x")
            self.logger.info(f"  - Gate.io 총자산: ${gateio_total:,.2f}")
            self.logger.info(f"  - Gate.io 증거금 (계산): ${gateio_margin:,.2f}")
            
            # 최소 증거금 체크
            if gateio_margin < self.min_margin:
                self.logger.warning(f"⚠️ 증거금이 너무 작습니다: ${gateio_margin:.2f}")
                gateio_margin = self.min_margin
            
            # Gate.io 레버리지 설정 (Bitget과 동일하게)
            await self._ensure_gateio_settings('BTC_USDT', leverage)
            
            # 지정가 주문을 위한 가격 계산 (유리한 가격)
            ticker = await self.gateio_client.get_ticker('usdt', 'BTC_USDT')
            current_price = float(ticker.get('last', 0))
            
            if side == 'long':
                # 롱은 현재가보다 약간 낮은 가격으로
                order_price = min(entry_price, current_price * 0.9995)
            else:
                # 숏은 현재가보다 약간 높은 가격으로
                order_price = max(entry_price, current_price * 1.0005)
            
            # 계약 수 계산 (증거금과 레버리지 기반)
            contract_info = await self.gateio_client.get_contract_info('usdt', 'BTC_USDT')
            quanto_multiplier = float(contract_info.get('quanto_multiplier', 0.0001))
            
            # 포지션 가치 = 증거금 × 레버리지
            position_value = gateio_margin * leverage
            btc_amount = position_value / order_price
            contracts = int(btc_amount / quanto_multiplier)
            
            # 방향 설정
            if side in ['short', 'sell']:
                contracts = -abs(contracts)
            else:
                contracts = abs(contracts)
            
            # 최소 1계약
            if abs(contracts) < 1:
                contracts = 1 if contracts >= 0 else -1
            
            # 주문 생성
            order_params = {
                'contract': 'BTC_USDT',
                'size': contracts,
                'price': str(order_price),
                'tif': 'gtc',  # Good Till Cancel
                'text': f'mirror_bitget_{leverage}x_{margin_ratio:.2%}'
            }
            
            result = await self.gateio_client.create_futures_order('usdt', **order_params)
            
            if result.get('id'):
                self.logger.info(f"✅ Gate.io 미러 주문 생성:")
                self.logger.info(f"  - 방향: {side}")
                self.logger.info(f"  - 레버리지: {leverage}x")
                self.logger.info(f"  - 증거금: ${gateio_margin:,.2f}")
                self.logger.info(f"  - 계약수: {abs(contracts)}")
                self.logger.info(f"  - 주문가: ${order_price:,.2f}")
                
                # 손절/익절 설정 (TODO: Bitget에서 실제 손절/익절 정보 가져오기)
                # await self._mirror_stop_orders(bitget_pos, contracts, order_price)
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Gate.io 미러링 실패: {e}")
            return False
    
    async def _ensure_gateio_settings(self, contract: str, leverage: int):
        """Gate.io 설정 확인 및 조정"""
        try:
            # 현재 포지션 설정 조회
            positions = await self.gateio_client.get_positions('usdt')
            
            for pos in positions:
                if pos.get('contract') == contract:
                    current_leverage = int(pos.get('leverage', 0))
                    if current_leverage != leverage:
                        self.logger.info(f"⚙️ 레버리지 변경 필요: {current_leverage}x → {leverage}x")
                        # 레버리지 변경 API 호출
                        await self._update_gateio_leverage(contract, leverage)
                    return
            
            # 포지션이 없으면 기본 설정
            await self._update_gateio_leverage(contract, leverage)
            
        except Exception as e:
            self.logger.error(f"Gate.io 설정 확인 실패: {e}")
    
    async def _update_gateio_leverage(self, contract: str, leverage: int):
        """Gate.io 레버리지 업데이트"""
        try:
            # Gate.io API를 통한 레버리지 설정
            # 실제 API 엔드포인트에 맞게 수정 필요
            endpoint = f"/api/v4/futures/usdt/positions/{contract}/leverage"
            
            # POST 요청으로 레버리지 변경
            async with self.gateio_client.session.post(
                f"{self.gateio_client.base_url}{endpoint}",
                headers=self.gateio_client._get_headers('POST', endpoint, '', json.dumps({'leverage': leverage})),
                json={'leverage': leverage}
            ) as response:
                if response.status in [200, 201]:
                    self.logger.info(f"✅ 레버리지 설정 완료: {leverage}x")
                else:
                    response_text = await response.text()
                    self.logger.warning(f"레버리지 설정 실패: {response_text}")
                    
        except Exception as e:
            self.logger.error(f"레버리지 업데이트 오류: {e}")
    
    async def _mirror_stop_orders(self, bitget_pos: Dict, contracts: int, entry_price: float):
        """손절/익절 주문 미러링"""
        # TODO: Bitget API에서 실제 손절/익절 정보를 가져와서 동일하게 설정
        # 여기서는 기본 예시만 제공
        pass
    
    def _cleanup_old_synced_positions(self):
        """오래된 동기화 기록 정리"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.synced_positions = {
            pid: sync_time 
            for pid, sync_time in self.synced_positions.items()
            if sync_time > cutoff_time
        }
    
    def stop(self):
        """미러 트레이딩 중지"""
        self.sync_enabled = False
        self.logger.info("🛑 미러 트레이딩 시스템 중지")
