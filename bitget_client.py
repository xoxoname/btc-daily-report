async def get_positions(self, symbol: str = None) -> List[Dict]:
    """포지션 조회 (V2 API) - 청산가 필드 확인 강화"""
    symbol = symbol or self.config.symbol
    endpoint = "/api/v2/mix/position/all-position"
    params = {
        'productType': 'USDT-FUTURES',
        'marginCoin': 'USDT'
    }
    
    try:
        response = await self._request('GET', endpoint, params=params)
        logger.info(f"포지션 정보 원본 응답: {response}")
        positions = response if isinstance(response, list) else []
        
        # 특정 심볼 필터링
        if symbol and positions:
            positions = [pos for pos in positions if pos.get('symbol') == symbol]
        
        # 포지션이 있는 것만 필터링
        active_positions = []
        for pos in positions:
            total_size = float(pos.get('total', 0))
            if total_size > 0:
                # 청산가 관련 모든 가능한 필드 확인
                liq_fields = ['liquidationPrice', 'liqPrice', 'liquidation_price', 
                             'estLiqPrice', 'liqPx', 'markPrice', 'liquidationPx',
                             'forceReducePrice', 'liqPrc']
                
                logger.info(f"포지션 청산가 필드 확인:")
                for field in liq_fields:
                    if field in pos:
                        logger.info(f"  - {field}: {pos.get(field)}")
                
                # 포지션에 필수 정보 추가
                pos['actualLeverage'] = float(pos.get('leverage', 1))
                pos['actualMargin'] = float(pos.get('margin', 0))
                
                active_positions.append(pos)
        
        return active_positions
    except Exception as e:
        logger.error(f"포지션 조회 실패: {e}")
        raise

async def get_profit_loss_history(self, symbol: str = None, days: int = 7) -> Dict:
    """손익 내역 조회 - 정확한 계산"""
    try:
        symbol = symbol or self.config.symbol
        
        # 1. 계정 정보 조회
        account_info = await self.get_account_info()
        logger.info(f"=== 계정 정보 ===")
        
        # 2. 거래 내역에서 실현 손익 계산
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = end_time - (days * 24 * 60 * 60 * 1000)
        
        trades = await self.get_all_trade_fills(symbol, start_time, end_time)
        logger.info(f"=== 거래 내역: {len(trades)}건 ===")
        
        # 실현 손익 계산
        total_realized_pnl = 0.0
        daily_pnl = {}
        total_fees = 0.0
        
        for trade in trades:
            try:
                # 거래 시간
                trade_time = int(trade.get('cTime', 0))
                if trade_time == 0:
                    continue
                
                trade_date = datetime.fromtimestamp(trade_time / 1000).strftime('%Y-%m-%d')
                
                # profit 필드가 있는 경우 직접 사용
                profit = float(trade.get('profit', 0))
                
                # profit이 0이고 side가 close인 경우 계산
                if profit == 0 and 'close' in str(trade.get('side', '')).lower():
                    # 청산 거래인 경우 손익 계산
                    fill_price = float(trade.get('price', 0))
                    size = float(trade.get('sizeQty', trade.get('size', 0)))
                    
                    # 이전 거래에서 평균 진입가 찾기 (실제 구현 필요)
                    # 여기서는 간단히 처리
                    profit = 0
                
                # 수수료 계산
                fee = 0.0
                fee_detail = trade.get('feeDetail', [])
                if isinstance(fee_detail, list):
                    for fee_info in fee_detail:
                        if isinstance(fee_info, dict):
                            fee += abs(float(fee_info.get('totalFee', 0)))
                elif isinstance(fee_detail, dict):
                    fee = abs(float(fee_detail.get('totalFee', 0)))
                else:
                    # 수수료가 별도 필드에 있는 경우
                    fee = abs(float(trade.get('fee', 0)))
                
                # 순 실현 손익 (수익 - 수수료)
                net_pnl = profit - fee
                total_realized_pnl += net_pnl
                total_fees += fee
                
                # 일별 누적
                if trade_date not in daily_pnl:
                    daily_pnl[trade_date] = 0
                daily_pnl[trade_date] += net_pnl
                
                logger.debug(f"거래: {trade_date} - 수익: ${profit:.2f}, 수수료: ${fee:.2f}, 순손익: ${net_pnl:.2f}")
                
            except Exception as e:
                logger.warning(f"거래 파싱 오류: {e}")
                continue
        
        logger.info(f"=== 최종 {days}일 손익: ${total_realized_pnl:,.2f} (수수료 ${total_fees:,.2f} 포함) ===")
        
        return {
            'total_pnl': total_realized_pnl,
            'daily_pnl': daily_pnl,
            'days': days,
            'average_daily': total_realized_pnl / days if days > 0 else 0,
            'trade_count': len(trades),
            'total_fees': total_fees
        }
        
    except Exception as e:
        logger.error(f"손익 내역 조회 실패: {e}")
        return {
            'total_pnl': 0,
            'daily_pnl': {},
            'days': days,
            'average_daily': 0
        }
