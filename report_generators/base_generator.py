async def _get_account_info(self) -> Dict:
    """계정 정보 조회 - 정확한 필드 매핑"""
    try:
        if not self.bitget_client:
            return {}
        
        account = await self.bitget_client.get_account_info()
        
        # 계정 정보 정확한 파싱
        total_equity = float(account.get('accountEquity', account.get('usdtEquity', 0)))
        
        # 가용 자산은 crossedMaxAvailable이 정확함
        available = float(account.get('crossedMaxAvailable', account.get('isolatedMaxAvailable', 0)))
        
        # 사용중인 증거금
        used_margin = float(account.get('crossedMargin', account.get('locked', 0)))
        
        # 미실현 손익
        unrealized_pnl = float(account.get('unrealizedPL', 0))
        
        # 위험률
        margin_ratio = float(account.get('crossedRiskRate', 0))
        
        return {
            'total_equity': total_equity,
            'available': available,
            'used_margin': used_margin,
            'margin_ratio': margin_ratio * 100,
            'unrealized_pnl': unrealized_pnl,
            'locked': float(account.get('locked', 0))
        }
        
    except Exception as e:
        self.logger.error(f"계정 정보 조회 실패: {str(e)}")
        return {}

async def _get_position_info(self) -> Dict:
    """포지션 정보 조회 - 청산가 계산 추가"""
    try:
        if not self.bitget_client:
            return {'has_position': False}
        
        positions = await self.bitget_client.get_positions('BTCUSDT')
        
        if not positions:
            return {'has_position': False}
        
        # 활성 포지션 찾기
        active_position = None
        for pos in positions:
            total_size = float(pos.get('total', 0))
            if total_size > 0:
                active_position = pos
                break
        
        if not active_position:
            return {'has_position': False}
        
        # 현재가 조회
        ticker = await self.bitget_client.get_ticker('BTCUSDT')
        current_price = float(ticker.get('last', ticker.get('lastPr', 0)))
        
        # 포지션 상세 정보 파싱
        side = active_position.get('holdSide', '').lower()
        size = float(active_position.get('total', 0))
        entry_price = float(active_position.get('openPriceAvg', active_position.get('averageOpenPrice', 0)))
        unrealized_pnl = float(active_position.get('unrealizedPL', 0))
        margin = float(active_position.get('margin', 0))
        leverage = int(float(active_position.get('leverage', 1)))
        
        # 청산가 계산 (청산가 필드가 없는 경우)
        liquidation_price = 0
        
        # 1. API에서 제공하는 청산가 찾기
        liq_fields = ['liquidationPrice', 'liqPrice', 'estLiqPrice', 'liqPx', 'forceReducePrice']
        for field in liq_fields:
            if field in active_position and active_position[field]:
                try:
                    liquidation_price = float(active_position[field])
                    break
                except:
                    continue
        
        # 2. 청산가가 없으면 계산
        if liquidation_price == 0 and entry_price > 0 and leverage > 0:
            # 유지 증거금률 (보통 0.5%)
            maintenance_margin_rate = 0.005
            
            if side in ['long', 'buy']:
                # 롱 청산가 = 진입가 * (1 - 1/레버리지 + 유지증거금률)
                liquidation_price = entry_price * (1 - 1/leverage + maintenance_margin_rate)
            else:  # short
                # 숏 청산가 = 진입가 * (1 + 1/레버리지 - 유지증거금률)
                liquidation_price = entry_price * (1 + 1/leverage - maintenance_margin_rate)
        
        # 손익률 계산
        if entry_price > 0:
            if side in ['short', 'sell']:
                pnl_rate = (entry_price - current_price) / entry_price
            else:  # long
                pnl_rate = (current_price - entry_price) / entry_price
        else:
            pnl_rate = 0
        
        return {
            'has_position': True,
            'symbol': active_position.get('symbol', 'BTCUSDT'),
            'side': '숏' if side in ['short', 'sell'] else '롱',
            'side_en': side,
            'size': size,
            'entry_price': entry_price,
            'current_price': current_price,
            'liquidation_price': liquidation_price,
            'pnl_rate': pnl_rate,
            'unrealized_pnl': unrealized_pnl,
            'margin': margin,
            'leverage': leverage
        }
        
    except Exception as e:
        self.logger.error(f"포지션 정보 조회 실패: {str(e)}")
        return {'has_position': False}
