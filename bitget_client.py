# bitget_client.py의 수정된 메서드들

async def get_positions_v2(self, symbol: str = None) -> List[Dict]:
    """포지션 조회 V2 - 정확한 청산가 포함"""
    symbol = symbol or self.config.symbol
    endpoint = "/api/v2/mix/position/all-position"
    params = {
        'productType': 'USDT-FUTURES',
        'marginCoin': 'USDT'
    }
    
    try:
        response = await self._request('GET', endpoint, params=params)
        
        # 전체 응답 로깅 (디버깅용)
        logger.info(f"=== 포지션 API 전체 응답 ===")
        logger.info(f"{json.dumps(response, indent=2, ensure_ascii=False)}")
        
        positions = response if isinstance(response, list) else []
        
        # 특정 심볼 필터링
        if symbol and positions:
            positions = [pos for pos in positions if pos.get('symbol') == symbol]
        
        # 활성 포지션만 필터링하고 청산가 확인
        active_positions = []
        for pos in positions:
            total_size = float(pos.get('total', 0))
            if total_size > 0:
                # 모든 필드 키 출력
                logger.info(f"=== 포지션 필드 목록 ===")
                logger.info(f"사용 가능한 필드: {sorted(list(pos.keys()))}")
                
                # 청산가 관련 가능한 모든 필드 확인
                liq_fields = [
                    'liquidationPrice',    # 표준 필드
                    'liqPrice',           # 구버전
                    'liquidationPx',      # 다른 표기
                    'liqPx',             # 축약
                    'estLiqPrice',       # 예상 청산가
                    'liquidation_price', # 언더스코어
                    'liq_price',        # 언더스코어 축약
                    'autoDeleveraging',  # ADL 관련
                    'adlRankIndicator', # ADL 순위
                ]
                
                logger.info(f"=== 청산가 필드 확인 ===")
                for field in liq_fields:
                    if field in pos:
                        logger.info(f"{field}: {pos[field]}")
                
                # 기타 중요 필드들도 확인
                important_fields = [
                    'markPrice',         # 마크 가격
                    'openPriceAvg',     # 평균 진입가
                    'leverage',         # 레버리지
                    'marginSize',       # 증거금
                    'marginRatio',      # 증거금 비율
                    'maintMarginRatio', # 유지 증거금 비율
                    'marginMode',       # 증거금 모드
                    'holdMode',         # 포지션 모드
                ]
                
                logger.info(f"=== 기타 중요 필드 ===")
                for field in important_fields:
                    if field in pos:
                        logger.info(f"{field}: {pos[field]}")
                
                # 포지션 데이터 정리
                position_data = {
                    'symbol': pos.get('symbol', 'BTCUSDT'),
                    'side': pos.get('holdSide', 'long'),
                    'size': total_size,
                    'entry_price': float(pos.get('openPriceAvg', 0)),
                    'mark_price': float(pos.get('markPrice', 0)),
                    'unrealized_pnl': float(pos.get('unrealizedPL', 0)),
                    'margin': float(pos.get('marginSize', 0)),
                    'leverage': int(pos.get('leverage', 1)),
                    'margin_ratio': float(pos.get('marginRatio', 0)),
                    'achieved_profits': float(pos.get('achievedProfits', 0)),
                    'available': float(pos.get('available', 0)),
                    'locked': float(pos.get('locked', 0)),
                    'total_fee': float(pos.get('totalFee', 0)),
                    'maint_margin_ratio': float(pos.get('maintMarginRatio', 0.005))
                }
                
                # 청산가 찾기 (여러 필드 시도)
                liquidation_price = 0
                for field in ['liquidationPrice', 'liqPrice', 'liquidationPx', 'estLiqPrice']:
                    if field in pos and pos[field]:
                        try:
                            liquidation_price = float(pos[field])
                            if liquidation_price > 0:
                                logger.info(f"청산가 발견: {field} = ${liquidation_price:,.2f}")
                                break
                        except:
                            continue
                
                # API에서 청산가를 못 가져온 경우 직접 계산
                if liquidation_price == 0:
                    logger.warning("API에서 청산가를 찾을 수 없음 - 직접 계산")
                    liquidation_price = self._calculate_liquidation_price(position_data)
                    logger.info(f"계산된 청산가: ${liquidation_price:,.2f}")
                
                position_data['liquidation_price'] = liquidation_price
                active_positions.append(position_data)
        
        return active_positions
        
    except Exception as e:
        logger.error(f"포지션 조회 실패: {e}")
        raise

def _calculate_liquidation_price(self, position_data: Dict) -> float:
    """청산가 계산 (Bitget 공식 사용)"""
    try:
        side = position_data.get('side', 'long').lower()
        entry_price = position_data.get('entry_price', 0)
        leverage = position_data.get('leverage', 1)
        maint_margin_ratio = position_data.get('maint_margin_ratio', 0.005)  # 기본 0.5%
        
        if entry_price == 0 or leverage == 0:
            return 0
        
        # Bitget 청산가 계산 공식
        # 롱: 진입가 × (1 - 1/레버리지 + 유지증거금비율)
        # 숏: 진입가 × (1 + 1/레버리지 - 유지증거금비율)
        
        if side in ['long', 'buy']:
            liq_price = entry_price * (1 - 1/leverage + maint_margin_ratio)
        else:  # short, sell
            liq_price = entry_price * (1 + 1/leverage - maint_margin_ratio)
        
        logger.info(f"청산가 계산: {side} 포지션, 진입가=${entry_price:,.2f}, "
                   f"레버리지={leverage}x, 유지증거금비율={maint_margin_ratio:.3%} "
                   f"=> 청산가=${liq_price:,.2f}")
        
        return liq_price
        
    except Exception as e:
        logger.error(f"청산가 계산 실패: {e}")
        return 0

async def get_profit_history_v2(self, symbol: str = None, days: int = 7) -> Dict:
    """실제 거래 기록 기반 정확한 손익 조회"""
    symbol = symbol or self.config.symbol
    all_trades = []
    
    try:
        # 1. 먼저 계정의 손익 요약 정보 조회
        account_info = await self.get_account_info()
        logger.info(f"=== 계정 손익 정보 ===")
        
        # 가능한 손익 필드들 확인
        pnl_fields = [
            'totalRealizedPL',      # 총 실현 손익
            'realizedPL',          # 실현 손익
            'achievedProfits',     # 달성 수익
            'totalProfitLoss',     # 총 손익
            'cumulativeRealizedPL', # 누적 실현 손익
            'totalProfit',         # 총 수익
        ]
        
        account_total_pnl = 0
        for field in pnl_fields:
            if field in account_info:
                value = float(account_info.get(field, 0))
                if value != 0:
                    logger.info(f"{field}: ${value:,.2f}")
                    account_total_pnl = value
        
        # 2. 일별로 거래 내역 조회 (API 제한 회피)
        kst = pytz.timezone('Asia/Seoul')
        daily_pnl = {}
        total_api_pnl = 0
        total_fees = 0
        
        for day_offset in range(days):
            # KST 기준 날짜 계산
            target_date = datetime.now(kst) - timedelta(days=day_offset)
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1) - timedelta(seconds=1)
            
            start_time = int(start_of_day.timestamp() * 1000)
            end_time = int(end_of_day.timestamp() * 1000)
            
            date_str = start_of_day.strftime('%Y-%m-%d')
            logger.info(f"\n=== {date_str} 거래 내역 조회 ===")
            
            # 여러 엔드포인트 시도
            day_trades = await self._try_multiple_trade_endpoints(symbol, start_time, end_time)
            
            if day_trades:
                logger.info(f"{date_str}: {len(day_trades)}건 거래 발견")
                
                day_pnl = 0
                day_fees = 0
                
                for trade in day_trades:
                    # 손익 추출
                    pnl = 0
                    pnl_fields = ['profit', 'realizedPnl', 'pnl', 'pl', 'realizedProfit', 'realizedPL']
                    for field in pnl_fields:
                        if field in trade and trade[field]:
                            pnl = float(trade[field])
                            if pnl != 0:
                                break
                    
                    # 수수료 추출
                    fee = 0
                    if 'feeDetail' in trade and isinstance(trade['feeDetail'], list):
                        for fee_item in trade['feeDetail']:
                            fee += abs(float(fee_item.get('totalFee', 0)))
                    else:
                        fee_fields = ['fee', 'totalFee', 'commission', 'tradeFee']
                        for field in fee_fields:
                            if field in trade and trade[field]:
                                fee = abs(float(trade[field]))
                                if fee != 0:
                                    break
                    
                    day_pnl += pnl
                    day_fees += fee
                    
                    logger.debug(f"거래 {trade.get('orderId', 'unknown')}: "
                               f"손익=${pnl:.2f}, 수수료=${fee:.2f}")
                
                net_day_pnl = day_pnl - day_fees
                
                daily_pnl[date_str] = {
                    'pnl': net_day_pnl,
                    'gross_pnl': day_pnl,
                    'fees': day_fees,
                    'trades': len(day_trades)
                }
                
                total_api_pnl += net_day_pnl
                total_fees += day_fees
                
                logger.info(f"{date_str} 요약: 순손익=${net_day_pnl:.2f}, "
                           f"총손익=${day_pnl:.2f}, 수수료=${day_fees:.2f}")
                
                all_trades.extend(day_trades)
            else:
                daily_pnl[date_str] = {
                    'pnl': 0,
                    'gross_pnl': 0,
                    'fees': 0,
                    'trades': 0
                }
            
            # API 호출 제한 대응
            await asyncio.sleep(0.1)
        
        # 3. 결과 정리
        logger.info(f"\n=== 최종 손익 정리 ===")
        logger.info(f"계정 총 손익: ${account_total_pnl:,.2f}")
        logger.info(f"API 조회 손익: ${total_api_pnl:,.2f}")
        logger.info(f"총 거래 건수: {len(all_trades)}")
        logger.info(f"총 수수료: ${total_fees:,.2f}")
        
        # 계정 손익이 더 정확한 경우가 많으므로 우선 사용
        final_total_pnl = account_total_pnl if account_total_pnl != 0 else total_api_pnl
        
        return {
            'total_pnl': final_total_pnl,
            'api_pnl': total_api_pnl,
            'account_pnl': account_total_pnl,
            'daily_pnl': daily_pnl,
            'trade_count': len(all_trades),
            'total_fees': total_fees,
            'average_daily': final_total_pnl / days if days > 0 else 0,
            'days': days,
            'trades': all_trades[:10]  # 최근 10개 거래만 포함
        }
        
    except Exception as e:
        logger.error(f"손익 내역 조회 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'total_pnl': 0,
            'daily_pnl': {},
            'trade_count': 0,
            'total_fees': 0,
            'average_daily': 0,
            'days': days,
            'error': str(e)
        }

async def _try_multiple_trade_endpoints(self, symbol: str, start_time: int, end_time: int) -> List[Dict]:
    """여러 엔드포인트를 시도하여 거래 내역 조회"""
    endpoints = [
        ("/api/v2/mix/order/fill-history", "fillList"),
        ("/api/v2/mix/order/fills", "fills"),
        ("/api/v2/mix/order/history", "orderList"),
        ("/api/v2/mix/order/detail", "data"),
        ("/api/v2/mix/order/marginCoinCurrent", "orderList"),
    ]
    
    for endpoint, data_key in endpoints:
        try:
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES',
                'startTime': str(start_time),
                'endTime': str(end_time),
                'limit': '100'
            }
            
            response = await self._request('GET', endpoint, params=params)
            
            # 응답에서 거래 데이터 추출
            trades = []
            if isinstance(response, dict) and data_key in response:
                trades = response[data_key]
            elif isinstance(response, list):
                trades = response
            elif isinstance(response, dict):
                # data_key가 없어도 다른 키 확인
                for key in ['list', 'data', 'orders', 'trades']:
                    if key in response and isinstance(response[key], list):
                        trades = response[key]
                        break
            
            if trades:
                logger.info(f"{endpoint} 성공: {len(trades)}건")
                return trades
                
        except Exception as e:
            logger.debug(f"{endpoint} 실패: {str(e)[:100]}")
            continue
    
    return []

# report_generator.py의 수정된 메서드들

async def _get_weekly_profit_data(self) -> Dict:
    """최근 7일 수익 데이터 조회 - 개선된 버전"""
    try:
        # bitget_client의 새로운 메서드 사용
        profit_history = await self.bitget_client.get_profit_history_v2('BTCUSDT', 7)
        
        total_pnl = profit_history.get('total_pnl', 0)
        api_pnl = profit_history.get('api_pnl', 0)
        account_pnl = profit_history.get('account_pnl', 0)
        
        logger.info(f"=== 7일 수익 조회 결과 ===")
        logger.info(f"총 손익: ${total_pnl:,.2f}")
        logger.info(f"API 손익: ${api_pnl:,.2f}")
        logger.info(f"계정 손익: ${account_pnl:,.2f}")
        
        # 일별 손익 로그
        daily_pnl = profit_history.get('daily_pnl', {})
        for date, data in sorted(daily_pnl.items()):
            if data['trades'] > 0:
                logger.info(f"{date}: ${data['pnl']:,.2f} ({data['trades']}건)")
        
        return {
            'total': total_pnl,
            'average': profit_history.get('average_daily', 0),
            'daily_breakdown': daily_pnl,
            'trade_count': profit_history.get('trade_count', 0)
        }
        
    except Exception as e:
        logger.error(f"주간 수익 조회 실패: {e}")
        return {'total': 0, 'average': 0}

async def _get_real_position_info(self) -> Dict:
    """실제 포지션 정보 조회 - 개선된 버전"""
    try:
        if not self.bitget_client:
            return {'positions': []}
        
        # 새로운 메서드 사용
        positions_data = await self.bitget_client.get_positions_v2()
        
        if not positions_data:
            return {'positions': []}
        
        # 이미 정리된 데이터이므로 그대로 반환
        return {'positions': positions_data}
        
    except Exception as e:
        logger.error(f"포지션 조회 실패: {e}")
        return {'positions': [], 'error': str(e)}

# bitget_client.py에 추가할 import
import pytz
