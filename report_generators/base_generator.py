async def _get_position_info(self) -> Dict:
    """포지션 정보 조회 - API 데이터만 사용"""
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
        
        # 포지션 상세 정보 - API에서 제공하는 값만 사용
        side = active_position.get('holdSide', '').lower()
        size = float(active_position.get('total', 0))
        entry_price = float(active_position.get('openPriceAvg', 0))
        unrealized_pnl = float(active_position.get('unrealizedPL', 0))
        margin = float(active_position.get('marginSize', 0))  # marginSize가 정확한 증거금
        leverage = int(float(active_position.get('leverage', 1)))
        
        # 청산가 - API에서 직접 가져오기
        liquidation_price = float(active_position.get('liquidationPrice', 0))
        
        # 손익률 계산 - achievedProfits 대신 unrealizedPL 사용
        pnl_rate = unrealized_pnl / margin if margin > 0 else 0
        
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
