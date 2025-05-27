# bitget_client.py 개선 사항 추가

async def get_all_trade_fills(self, symbol: str = None, start_time: int = None, end_time: int = None) -> List[Dict]:
    """모든 거래 내역 조회 - 페이징 처리 강화"""
    symbol = symbol or self.config.symbol
    all_fills = []
    
    # 여러 엔드포인트 시도
    endpoints = [
        ("/api/v2/mix/order/fill-history", ["fillList", "fills", "list"]),
        ("/api/v2/mix/order/history", ["orderList", "list", "data"]),
        ("/api/v2/mix/order/fills", ["fills", "list", "data"])
    ]
    
    for endpoint, possible_keys in endpoints:
        last_id = None
        page = 0
        consecutive_empty = 0
        
        while page < 50:  # 최대 50페이지 (5000건)
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES',
                'limit': '100'
            }
            
            if start_time:
                params['startTime'] = str(start_time)
            if end_time:
                params['endTime'] = str(end_time)
            if last_id:
                params['lastEndId'] = str(last_id)
            
            try:
                logger.info(f"{endpoint} 페이지 {page + 1} 조회 중...")
                response = await self._request('GET', endpoint, params=params)
                
                # 응답에서 거래 데이터 추출
                fills = []
                if isinstance(response, dict):
                    for key in possible_keys:
                        if key in response and isinstance(response[key], list):
                            fills = response[key]
                            break
                elif isinstance(response, list):
                    fills = response
                
                if not fills:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:  # 연속 2번 빈 응답이면 중단
                        break
                    page += 1
                    await asyncio.sleep(0.1)
                    continue
                
                consecutive_empty = 0
                all_fills.extend(fills)
                logger.info(f"{endpoint} 페이지 {page + 1}: {len(fills)}건 (누적 {len(all_fills)}건)")
                
                # 100개 미만이면 마지막 페이지
                if len(fills) < 100:
                    logger.info(f"{endpoint} 마지막 페이지 도달")
                    break
                
                # 다음 페이지를 위한 마지막 ID 추출
                last_fill = fills[-1]
                new_last_id = None
                
                # 가능한 ID 필드들
                id_fields = ['fillId', 'orderId', 'id', 'tradeId', 'billId']
                for field in id_fields:
                    if field in last_fill and last_fill[field]:
                        new_last_id = str(last_fill[field])
                        break
                
                # ID를 못 찾았거나 같은 ID면 중단
                if not new_last_id or new_last_id == last_id:
                    logger.warning(f"다음 페이지 ID를 찾을 수 없음")
                    break
                
                last_id = new_last_id
                page += 1
                
                # API 제한 대응
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"{endpoint} 페이지 {page + 1} 오류: {e}")
                break
        
        if all_fills:
            logger.info(f"{endpoint} 총 {len(all_fills)}건 조회 완료")
            return all_fills
    
    logger.warning(f"모든 엔드포인트에서 거래 내역을 찾을 수 없음")
    return all_fills

async def get_profit_loss_history(self, symbol: str = None, days: int = 7) -> Dict:
    """손익 내역 조회 - 강화된 버전"""
    try:
        symbol = symbol or self.config.symbol
        
        # 1. 계정 정보 조회
        account_info = await self.get_account_info()
        logger.info(f"=== 계정 정보 ===")
        
        # 가능한 모든 손익 필드 확인
        pnl_fields = {
            'achievedProfits': '달성 수익',
            'realizedPL': '실현 손익',
            'totalRealizedPL': '총 실현 손익',
            'cumulativeRealizedPL': '누적 실현 손익',
            'totalProfitLoss': '총 손익',
            'todayProfit': '오늘 수익',
            'weekProfit': '주간 수익'
        }
        
        account_pnl_data = {}
        for field, desc in pnl_fields.items():
            if field in account_info:
                value = float(account_info.get(field, 0))
                if value != 0:
                    account_pnl_data[field] = value
                    logger.info(f"{desc} ({field}): ${value:,.2f}")
        
        # 2. 거래 내역 조회
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = end_time - (days * 24 * 60 * 60 * 1000)
        
        trades = await self.get_all_trade_fills(symbol, start_time, end_time)
        logger.info(f"=== 거래 내역: {len(trades)}건 ===")
        
        if not trades:
            # 계정 정보에서 가장 적절한 값 선택
            best_pnl = 0
            best_field = None
            
            # 우선순위: achievedProfits > weekProfit > realizedPL
            priority_fields = ['achievedProfits', 'weekProfit', 'realizedPL', 'totalRealizedPL']
            for field in priority_fields:
                if field in account_pnl_data and account_pnl_data[field] > 0:
                    best_pnl = account_pnl_data[field]
                    best_field = field
                    break
            
            if best_pnl > 0:
                logger.info(f"계정 {best_field} 사용: ${best_pnl:,.2f}")
                return {
                    'total_pnl': best_pnl,
                    'daily_pnl': {},
                    'days': days,
                    'average_daily': best_pnl / days if days > 0 else 0,
                    'source': f'account.{best_field}'
                }
        
        # 3. 거래 내역 분석
        total_pnl = 0.0
        daily_pnl = {}
        total_fees = 0.0
        
        for trade in trades:
            try:
                # 거래 시간
                trade_time = int(trade.get('cTime', 0))
                if trade_time == 0:
                    continue
                
                trade_date = datetime.fromtimestamp(trade_time / 1000).strftime('%Y-%m-%d')
                
                # 손익 - profit 필드 직접 사용
                profit = float(trade.get('profit', 0))
                
                # 수수료
                fee = 0.0
                fee_detail = trade.get('feeDetail', [])
                if isinstance(fee_detail, list):
                    for fee_info in fee_detail:
                        if isinstance(fee_info, dict):
                            fee += abs(float(fee_info.get('totalFee', 0)))
                
                realized_pnl = profit - fee
                total_pnl += realized_pnl
                total_fees += fee
                
                # 일별 누적
                if trade_date not in daily_pnl:
                    daily_pnl[trade_date] = 0
                daily_pnl[trade_date] += realized_pnl
                
            except Exception as e:
                logger.warning(f"거래 파싱 오류: {e}")
                continue
        
        # 4. 계정 정보와 비교
        if 'achievedProfits' in account_pnl_data:
            achieved = account_pnl_data['achievedProfits']
            if achieved > total_pnl and achieved < total_pnl * 1.5:
                logger.info(f"achievedProfits가 더 정확: ${achieved:,.2f} vs 계산값 ${total_pnl:,.2f}")
                total_pnl = achieved
        
        logger.info(f"=== 최종 7일 손익: ${total_pnl:,.2f} ===")
        
        return {
            'total_pnl': total_pnl,
            'daily_pnl': daily_pnl,
            'days': days,
            'average_daily': total_pnl / days if days > 0 else 0,
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
                             'estLiqPrice', 'liqPx', 'markPrice', 'liquidationPx']
                
                logger.info(f"포지션 청산가 필드 확인:")
                for field in liq_fields:
                    if field in pos:
                        logger.info(f"  - {field}: {pos.get(field)}")
                
                active_positions.append(pos)
        
        return active_positions
    except Exception as e:
        logger.error(f"포지션 조회 실패: {e}")
        raise
