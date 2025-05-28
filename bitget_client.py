import asyncio
import hmac
import hashlib
import base64
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
import pytz
import traceback

logger = logging.getLogger(__name__)

class BitgetClient:
    def __init__(self, config):
        self.config = config
        self.session = None
        self._initialize_session()
        
    def _initialize_session(self):
        """세션 초기화"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            logger.info("Bitget 클라이언트 세션 초기화 완료")
        
    async def initialize(self):
        """클라이언트 초기화"""
        self._initialize_session()
        logger.info("Bitget 클라이언트 초기화 완료")
    
    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """API 서명 생성"""
        message = timestamp + method.upper() + request_path + body
        signature = base64.b64encode(
            hmac.new(
                self.config.bitget_api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        return signature
    
    def _get_headers(self, method: str, request_path: str, body: str = '') -> Dict[str, str]:
        """API 헤더 생성"""
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(timestamp, method, request_path, body)
        
        return {
            'ACCESS-KEY': self.config.bitget_api_key,
            'ACCESS-SIGN': signature,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-PASSPHRASE': self.config.bitget_passphrase,
            'Content-Type': 'application/json',
            'locale': 'en-US'
        }
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """API 요청"""
        if not self.session:
            self._initialize_session()
            
        url = f"{self.config.bitget_base_url}{endpoint}"
        
        if params:
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            url += f"?{query_string}"
            request_path = f"{endpoint}?{query_string}"
        else:
            request_path = endpoint
        
        body = json.dumps(data) if data else ''
        headers = self._get_headers(method, request_path, body)
        
        try:
            logger.info(f"API 요청: {method} {url}")
            async with self.session.request(method, url, headers=headers, data=body) as response:
                response_text = await response.text()
                logger.info(f"API 응답 상태: {response.status}")
                logger.debug(f"API 응답 내용: {response_text[:500]}")
                
                response_data = json.loads(response_text)
                
                if response.status != 200:
                    logger.error(f"API 요청 실패: {response.status} - {response_data}")
                    raise Exception(f"API 요청 실패: {response_data}")
                
                if response_data.get('code') != '00000':
                    logger.error(f"API 응답 오류: {response_data}")
                    raise Exception(f"API 응답 오류: {response_data}")
                
                return response_data.get('data', {})
                
        except Exception as e:
            logger.error(f"API 요청 중 오류: {e}")
            raise
    
    async def get_ticker(self, symbol: str = None) -> Dict:
        """현재가 정보 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/market/ticker"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            if isinstance(response, list) and len(response) > 0:
                return response[0]
            return response
        except Exception as e:
            logger.error(f"현재가 조회 실패: {e}")
            raise
    
    async def get_positions(self, symbol: str = None) -> List[Dict]:
        """포지션 조회 (V2 API)"""
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
            
            if symbol and positions:
                positions = [pos for pos in positions if pos.get('symbol') == symbol]
            
            active_positions = []
            for pos in positions:
                total_size = float(pos.get('total', 0))
                if total_size > 0:
                    active_positions.append(pos)
                    # 청산가 필드 로깅
                    logger.info(f"포지션 청산가 필드 확인:")
                    logger.info(f"  - liquidationPrice: {pos.get('liquidationPrice')}")
                    logger.info(f"  - markPrice: {pos.get('markPrice')}")
            
            return active_positions
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            raise
    
    async def get_account_info(self) -> Dict:
        """계정 정보 조회 (V2 API)"""
        endpoint = "/api/v2/mix/account/accounts"
        params = {
            'productType': 'USDT-FUTURES',
            'marginCoin': 'USDT'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            logger.info(f"계정 정보 원본 응답: {response}")
            if isinstance(response, list) and len(response) > 0:
                return response[0]
            return response
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            raise
    
    async def get_trade_fills(self, symbol: str = None, start_time: int = None, end_time: int = None, limit: int = 100) -> List[Dict]:
        """거래 체결 내역 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        
        if start_time and end_time:
            max_days = 7
            time_diff = end_time - start_time
            max_time_diff = max_days * 24 * 60 * 60 * 1000
            
            if time_diff > max_time_diff:
                start_time = end_time - max_time_diff
                logger.info(f"7일 제한으로 조정: {datetime.fromtimestamp(start_time/1000)} ~ {datetime.fromtimestamp(end_time/1000)}")
        
        return await self._get_fills_batch(symbol, start_time, end_time, min(limit, 500))
    
    async def _get_fills_batch(self, symbol: str, start_time: int = None, end_time: int = None, limit: int = 100, last_id: str = None) -> List[Dict]:
        """거래 체결 내역 배치 조회"""
        endpoints = ["/api/v2/mix/order/fill-history", "/api/v2/mix/order/fills"]
        
        for endpoint in endpoints:
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'
            }
            
            if start_time:
                params['startTime'] = str(start_time)
            if end_time:
                params['endTime'] = str(end_time)
            if limit:
                params['limit'] = str(limit)
            if last_id:
                params['lastEndId'] = str(last_id)
            
            try:
                response = await self._request('GET', endpoint, params=params)
                
                fills = []
                if isinstance(response, dict):
                    if 'fillList' in response:
                        fills = response['fillList']
                    elif 'fills' in response:
                        fills = response['fills']
                    elif 'list' in response:
                        fills = response['list']
                    elif 'data' in response and isinstance(response['data'], list):
                        fills = response['data']
                elif isinstance(response, list):
                    fills = response
                
                if fills:
                    logger.info(f"{endpoint} 거래 내역 조회 성공: {len(fills)}건")
                    return fills
                    
            except Exception as e:
                logger.debug(f"{endpoint} 조회 실패: {e}")
                continue
        
        return []
    
    async def get_all_trade_fills(self, symbol: str = None, start_time: int = None, end_time: int = None) -> List[Dict]:
        """모든 거래 내역 조회 - 페이징 처리"""
        symbol = symbol or self.config.symbol
        all_fills = []
        
        endpoints = [
            ("/api/v2/mix/order/fill-history", ["fillList", "fills", "list"]),
            ("/api/v2/mix/order/history", ["orderList", "list", "data"]),
            ("/api/v2/mix/order/fills", ["fills", "list", "data"])
        ]
        
        for endpoint, possible_keys in endpoints:
            last_id = None
            page = 0
            consecutive_empty = 0
            
            while page < 50:
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
                        if consecutive_empty >= 2:
                            break
                        page += 1
                        await asyncio.sleep(0.1)
                        continue
                    
                    consecutive_empty = 0
                    all_fills.extend(fills)
                    logger.info(f"{endpoint} 페이지 {page + 1}: {len(fills)}건 (누적 {len(all_fills)}건)")
                    
                    if len(fills) < 100:
                        logger.info(f"{endpoint} 마지막 페이지 도달")
                        break
                    
                    last_fill = fills[-1]
                    new_last_id = None
                    
                    id_fields = ['fillId', 'orderId', 'id', 'tradeId', 'billId']
                    for field in id_fields:
                        if field in last_fill and last_fill[field]:
                            new_last_id = str(last_fill[field])
                            break
                    
                    if not new_last_id or new_last_id == last_id:
                        logger.warning(f"다음 페이지 ID를 찾을 수 없음")
                        break
                    
                    last_id = new_last_id
                    page += 1
                    
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
        """손익 내역 조회 - 모든 거래 내역 집계"""
        try:
            symbol = symbol or self.config.symbol
            
            # KST 기준 7일 전부터 현재까지
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            start_date = now - timedelta(days=days)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            end_time = int(now.timestamp() * 1000)
            start_time = int(start_date.timestamp() * 1000)
            
            # 모든 거래 내역 조회
            trades = await self.get_all_trade_fills(symbol, start_time, end_time)
            logger.info(f"=== 7일간 거래 내역: {len(trades)}건 ===")
            
            total_pnl = 0.0
            daily_pnl = {}
            total_fees = 0.0
            trade_count = 0
            
            for trade in trades:
                try:
                    trade_time = int(trade.get('cTime', 0))
                    if trade_time == 0:
                        continue
                    
                    # KST 기준 날짜
                    trade_date_kst = datetime.fromtimestamp(trade_time / 1000, tz=kst)
                    trade_date = trade_date_kst.strftime('%Y-%m-%d')
                    
                    # API에서 제공하는 profit 필드 사용
                    profit = float(trade.get('profit', 0))
                    
                    # 수수료 계산
                    fee = 0.0
                    fee_detail = trade.get('feeDetail', [])
                    if isinstance(fee_detail, list):
                        for fee_info in fee_detail:
                            if isinstance(fee_info, dict):
                                fee += abs(float(fee_info.get('totalFee', 0)))
                    
                    # 실현 손익 = profit - 수수료
                    realized_pnl = profit - fee
                    
                    # 집계
                    total_pnl += realized_pnl
                    total_fees += fee
                    trade_count += 1
                    
                    if trade_date not in daily_pnl:
                        daily_pnl[trade_date] = 0
                    daily_pnl[trade_date] += realized_pnl
                    
                    logger.debug(f"거래 {trade_count}: {trade_date} profit={profit:.2f}, fee={fee:.2f}, pnl={realized_pnl:.2f}")
                    
                except Exception as e:
                    logger.warning(f"거래 파싱 오류: {e}")
                    continue
            
            # 일별 손익 로그
            for date, pnl in sorted(daily_pnl.items()):
                logger.info(f"  {date}: ${pnl:,.2f}")
            
            logger.info(f"=== 최종 7일 손익: ${total_pnl:,.2f} (거래 {trade_count}건, 수수료 ${total_fees:.2f}) ===")
            
            return {
                'total_pnl': total_pnl,
                'daily_pnl': daily_pnl,
                'days': days,
                'average_daily': total_pnl / days if days > 0 else 0,
                'trade_count': trade_count,
                'total_fees': total_fees
            }
            
        except Exception as e:
            logger.error(f"손익 내역 조회 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'days': days,
                'average_daily': 0,
                'trade_count': 0,
                'total_fees': 0
            }
    
    async def get_funding_rate(self, symbol: str = None) -> Dict:
        """펀딩비 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/market/current-fund-rate"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            return response
        except Exception as e:
            logger.error(f"펀딩비 조회 실패: {e}")
            raise
    
    async def get_open_interest(self, symbol: str = None) -> Dict:
        """미결제약정 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/market/open-interest"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            return response
        except Exception as e:
            logger.error(f"미결제약정 조회 실패: {e}")
            raise
    
    async def get_kline(self, symbol: str = None, granularity: str = '1H', limit: int = 100) -> List[Dict]:
        """K라인 데이터 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/market/candles"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES',
            'granularity': granularity,
            'limit': str(limit)
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            return response if isinstance(response, list) else []
        except Exception as e:
            logger.error(f"K라인 조회 실패: {e}")
            raise
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
