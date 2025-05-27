# bitget_client.py - 수정된 전체 코드
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
        """포지션 조회 - 개선된 버전"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/position/all-position"
        params = {
            'productType': 'USDT-FUTURES',
            'marginCoin': 'USDT'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            
            # 전체 응답 로깅
            logger.info(f"=== 포지션 API 응답 ===")
            logger.info(f"{json.dumps(response, indent=2, ensure_ascii=False)[:1000]}")
            
            positions = response if isinstance(response, list) else []
            
            # 특정 심볼 필터링
            if symbol and positions:
                positions = [pos for pos in positions if pos.get('symbol') == symbol]
            
            # 활성 포지션만 필터링
            active_positions = []
            for pos in positions:
                total_size = float(pos.get('total', 0))
                if total_size > 0:
                    # 모든 필드 키 출력
                    logger.info(f"포지션 필드: {sorted(list(pos.keys()))}")
                    
                    # 청산가 찾기
                    liquidation_price = 0
                    liq_fields = ['liquidationPrice', 'liqPrice', 'liquidationPx', 'estLiqPrice']
                    
                    for field in liq_fields:
                        if field in pos and pos[field]:
                            try:
                                value = float(pos[field])
                                if value > 0:
                                    liquidation_price = value
                                    logger.info(f"청산가 필드 발견: {field} = ${value:,.2f}")
                                    break
                            except:
                                continue
                    
                    # 청산가가 없으면 계산
                    if liquidation_price == 0:
                        position_data = {
                            'side': pos.get('holdSide', 'long'),
                            'entry_price': float(pos.get('openPriceAvg', 0)),
                            'leverage': int(pos.get('leverage', 1)),
                            'maint_margin_ratio': float(pos.get('maintMarginRatio', 0.005))
                        }
                        liquidation_price = self._calculate_liquidation_price(position_data)
                        logger.info(f"계산된 청산가: ${liquidation_price:,.2f}")
                    
                    # liquidation_price 필드 추가
                    pos['liquidationPrice'] = liquidation_price
                    active_positions.append(pos)
            
            return active_positions
            
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            raise
    
    def _calculate_liquidation_price(self, position_data: Dict) -> float:
        """청산가 계산"""
        try:
            side = position_data.get('side', 'long').lower()
            entry_price = position_data.get('entry_price', 0)
            leverage = position_data.get('leverage', 1)
            maint_margin_ratio = position_data.get('maint_margin_ratio', 0.005)
            
            if entry_price == 0 or leverage == 0:
                return 0
            
            if side in ['long', 'buy']:
                liq_price = entry_price * (1 - 1/leverage + maint_margin_ratio)
            else:  # short, sell
                liq_price = entry_price * (1 + 1/leverage - maint_margin_ratio)
            
            return liq_price
            
        except Exception as e:
            logger.error(f"청산가 계산 실패: {e}")
            return 0
    
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
        """거래 체결 내역 조회 - 개선된 버전"""
        symbol = symbol or self.config.symbol
        all_fills = []
        
        # 7일 제한 처리
        if start_time and end_time:
            max_days = 7
            time_diff = end_time - start_time
            max_time_diff = max_days * 24 * 60 * 60 * 1000
            
            if time_diff > max_time_diff:
                start_time = end_time - max_time_diff
                logger.info(f"7일 제한으로 조정")
        
        # 여러 엔드포인트 시도
        endpoints = [
            "/api/v2/mix/order/fill-history",
            "/api/v2/mix/order/fills",
            "/api/v2/mix/order/history"
        ]
        
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
            
            try:
                response = await self._request('GET', endpoint, params=params)
                
                # 응답 형식 확인
                fills = []
                if isinstance(response, dict):
                    for key in ['fillList', 'fills', 'list', 'orderList', 'data']:
                        if key in response and isinstance(response[key], list):
                            fills = response[key]
                            break
                elif isinstance(response, list):
                    fills = response
                
                if fills:
                    logger.info(f"{endpoint} 거래 내역 조회 성공: {len(fills)}건")
                    return fills
                    
            except Exception as e:
                logger.debug(f"{endpoint} 조회 실패: {e}")
                continue
        
        return all_fills
    
    async def get_profit_loss_history(self, symbol: str = None, days: int = 7) -> Dict:
        """손익 내역 조회 - 개선된 버전"""
        try:
            symbol = symbol or self.config.symbol
            
            # 1. 계정 정보에서 총 손익 확인
            account_info = await self.get_account_info()
            
            # 가능한 손익 필드들
            pnl_fields = [
                'totalRealizedPL',
                'realizedPL',
                'achievedProfits',
                'totalProfitLoss',
                'cumulativeRealizedPL'
            ]
            
            account_total_pnl = 0
            for field in pnl_fields:
                if field in account_info:
                    value = float(account_info.get(field, 0))
                    if value != 0:
                        account_total_pnl = value
                        logger.info(f"계정 {field}: ${value:,.2f}")
                        break
            
            # 2. 최근 거래 내역 조회
            kst = pytz.timezone('Asia/Seoul')
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = end_time - (days * 24 * 60 * 60 * 1000)
            
            trades = await self.get_trade_fills(symbol, start_time, end_time, 500)
            
            if not trades:
                logger.warning("거래 내역이 없음")
                return {
                    'total_pnl': account_total_pnl,
                    'daily_pnl': {},
                    'days': days,
                    'average_daily': account_total_pnl / days if days > 0 else 0
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
                    
                    trade_date = datetime.fromtimestamp(trade_time / 1000, tz=kst).strftime('%Y-%m-%d')
                    
                    # 손익 계산
                    profit = 0
                    profit_fields = ['profit', 'realizedPnl', 'pnl', 'pl']
                    for field in profit_fields:
                        if field in trade:
                            profit = float(trade.get(field, 0))
                            if profit != 0:
                                break
                    
                    # 수수료
                    fee = 0.0
                    fee_detail = trade.get('feeDetail', [])
                    if isinstance(fee_detail, list):
                        for fee_info in fee_detail:
                            if isinstance(fee_info, dict):
                                fee += abs(float(fee_info.get('totalFee', 0)))
                    
                    # 실현 손익
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
            
            # 최종 결과 (계정 총액이 더 정확하면 사용)
            final_total = account_total_pnl if account_total_pnl != 0 else total_pnl
            
            return {
                'total_pnl': final_total,
                'daily_pnl': daily_pnl,
                'days': days,
                'average_daily': final_total / days if days > 0 else 0
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
