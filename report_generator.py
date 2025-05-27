import asyncio
import hmac
import hashlib
import base64
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional  # 이 줄이 추가되어야 합니다!
import aiohttp
import pytz

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
        # 세션 확인
        if not self.session:
            self._initialize_session()
            
        url = f"{self.config.bitget_base_url}{endpoint}"
        
        # 쿼리 파라미터 처리
        if params:
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            url += f"?{query_string}"
            request_path = f"{endpoint}?{query_string}"
        else:
            request_path = endpoint
        
        # 바디 데이터 처리
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
        """거래 체결 내역 조회 (V2 API) - 단순화된 버전"""
        symbol = symbol or self.config.symbol
        
        # 7일 제한 확인
        if start_time and end_time:
            max_days = 7
            time_diff = end_time - start_time
            max_time_diff = max_days * 24 * 60 * 60 * 1000  # 7일 in milliseconds
            
            if time_diff > max_time_diff:
                # 최근 7일만 조회
                start_time = end_time - max_time_diff
                logger.info(f"7일 제한으로 조정: {datetime.fromtimestamp(start_time/1000)} ~ {datetime.fromtimestamp(end_time/1000)}")
        
        # 단일 조회 (limit 증가)
        return await self._get_fills_batch(symbol, start_time, end_time, min(limit, 500))
    
    async def _get_fills_batch(self, symbol: str, start_time: int = None, end_time: int = None, limit: int = 100, last_id: str = None) -> List[Dict]:
        """거래 체결 내역 배치 조회"""
        # fill-history와 fills 두 엔드포인트 모두 시도
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
                
                # 응답 형식 확인
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
    
    async def get_order_history(self, symbol: str = None, start_time: int = None, end_time: int = None) -> List[Dict]:
        """주문 내역 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/order/history"
        
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES'
        }
        
        if start_time:
            params['startTime'] = str(start_time)
        if end_time:
            params['endTime'] = str(end_time)
        
        try:
            response = await self._request('GET', endpoint, params=params)
            if isinstance(response, dict) and 'orderList' in response:
                return response['orderList']
            elif isinstance(response, list):
                return response
            return []
        except Exception as e:
            logger.error(f"주문 내역 조회 실패: {e}")
            return []
    
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
