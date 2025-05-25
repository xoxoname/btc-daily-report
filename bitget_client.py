# bitget_client.py - Bitget API 클라이언트 (V2 API 대응)
import hmac
import hashlib
import base64
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp

logger = logging.getLogger(__name__)

class BitgetClient:
    def __init__(self, config):
        self.config = config
        self.session = None
        
    async def initialize(self):
        """클라이언트 초기화"""
        self.session = aiohttp.ClientSession()
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
            async with self.session.request(method, url, headers=headers, data=body) as response:
                response_data = await response.json()
                
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
            'productType': 'USDT-FUTURES'  # V2에서는 USDT-FUTURES 형식 사용
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            if isinstance(response, list) and len(response) > 0:
                return response[0]
            return response
        except Exception as e:
            logger.error(f"현재가 조회 실패: {e}")
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
    
    async def get_positions(self, symbol: str = None) -> List[Dict]:
        """포지션 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/position/all-position"
        params = {
            'productType': 'USDT-FUTURES',  # V2에서는 USDT-FUTURES 사용
            'marginCoin': 'USDT'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            logger.info(f"포지션 정보 원본 응답: {response}")  # 디버그 로그 추가
            positions = response if isinstance(response, list) else []
            
            # 특정 심볼 필터링
            if symbol:
                positions = [pos for pos in positions if pos.get('symbol') == symbol]
            
            # 포지션이 있는 것만 필터링 (사이즈가 0이 아닌 것)
            active_positions = []
            for pos in positions:
                size = float(pos.get('size', 0))
                if size > 0:
                    active_positions.append(pos)
            
            return active_positions
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            raise
    
    async def get_account_info(self) -> Dict:
        """계정 정보 조회 (V2 API)"""
        endpoint = "/api/v2/mix/account/accounts"
        params = {
            'productType': 'USDT-FUTURES',  # V2에서는 USDT-FUTURES 사용
            'marginCoin': 'USDT'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            logger.info(f"계정 정보 원본 응답: {response}")  # 디버그 로그 추가
            if isinstance(response, list) and len(response) > 0:
                return response[0]
            return response
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            raise
    
    async def get_funding_rate(self, symbol: str = None) -> Dict:
        """펀딩비 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/market/current-fund-rate"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES'  # V2에서는 USDT-FUTURES 사용
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
            'productType': 'USDT-FUTURES'  # V2에서는 USDT-FUTURES 사용
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            return response
        except Exception as e:
            logger.error(f"미결제약정 조회 실패: {e}")
            raise
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
