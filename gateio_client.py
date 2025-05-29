import asyncio
import hmac
import hashlib
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp

logger = logging.getLogger(__name__)

class GateioClient:
    def __init__(self, config):
        self.config = config
        self.session = None
        self.base_url = "https://api.gateio.ws"
        self._initialize_session()
        
    def _initialize_session(self):
        """세션 초기화"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            logger.info("Gate.io 클라이언트 세션 초기화 완료")
    
    async def initialize(self):
        """클라이언트 초기화"""
        self._initialize_session()
        logger.info("Gate.io 클라이언트 초기화 완료")
    
    def _generate_signature(self, method: str, url: str, query_string: str = "", 
                          payload_string: str = "", timestamp: str = "") -> str:
        """API 서명 생성"""
        hashed_payload = hashlib.sha512(payload_string.encode('utf-8')).hexdigest()
        s = f'{method}\n{url}\n{query_string}\n{hashed_payload}\n{timestamp}'
        h = hmac.new(self.config.gateio_api_secret.encode('utf-8'), 
                     s.encode('utf-8'), hashlib.sha512)
        return h.hexdigest()
    
    def _get_headers(self, method: str, url: str, query_string: str = "", 
                    payload_string: str = "") -> Dict[str, str]:
        """API 헤더 생성"""
        timestamp = str(int(time.time()))
        signature = self._generate_signature(method, url, query_string, payload_string, timestamp)
        
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'KEY': self.config.gateio_api_key,
            'Timestamp': timestamp,
            'SIGN': signature
        }
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                      data: Optional[Dict] = None) -> Dict:
        """API 요청"""
        if not self.session:
            self._initialize_session()
        
        url = f"{self.base_url}{endpoint}"
        
        query_string = ""
        if params:
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            url += f"?{query_string}"
        
        payload_string = json.dumps(data) if data else ""
        headers = self._get_headers(method, endpoint, query_string, payload_string)
        
        try:
            logger.info(f"Gate.io API 요청: {method} {url}")
            
            kwargs = {'headers': headers}
            if method == 'GET' and params:
                kwargs['params'] = params
            elif data:
                kwargs['data'] = payload_string
            
            async with self.session.request(method, url, **kwargs) as response:
                response_text = await response.text()
                logger.info(f"Gate.io API 응답 상태: {response.status}")
                
                response_data = json.loads(response_text)
                
                if response.status != 200:
                    logger.error(f"Gate.io API 요청 실패: {response.status} - {response_data}")
                    raise Exception(f"API 요청 실패: {response_data}")
                
                return response_data
                
        except Exception as e:
            logger.error(f"Gate.io API 요청 중 오류: {e}")
            raise
    
    async def get_account_info(self) -> Dict:
        """계정 정보 조회"""
        endpoint = "/api/v4/spot/accounts"
        try:
            response = await self._request('GET', endpoint)
            return response
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            raise
    
    async def get_futures_account(self) -> Dict:
        """선물 계정 정보 조회"""
        endpoint = "/api/v4/futures/usdt/accounts"
        try:
            response = await self._request('GET', endpoint)
            return response
        except Exception as e:
            logger.error(f"선물 계정 정보 조회 실패: {e}")
            raise
    
    async def get_positions(self, settle: str = "usdt") -> List[Dict]:
        """포지션 조회"""
        endpoint = f"/api/v4/futures/{settle}/positions"
        try:
            response = await self._request('GET', endpoint)
            return response
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            raise
    
    async def create_futures_order(self, settle: str = "usdt", **order_params) -> Dict:
        """선물 주문 생성"""
        endpoint = f"/api/v4/futures/{settle}/orders"
        try:
            # 필수 파라미터 검증
            required = ['contract', 'size', 'price']
            for param in required:
                if param not in order_params:
                    raise ValueError(f"필수 파라미터 누락: {param}")
            
            # 기본값 설정
            order_data = {
                'contract': order_params['contract'],  # 예: BTC_USDT
                'size': order_params['size'],  # 양수: 롱, 음수: 숏
                'price': str(order_params['price']),
                'tif': order_params.get('tif', 'gtc'),  # good till cancelled
                'reduce_only': order_params.get('reduce_only', False),
                'close': order_params.get('close', False),
                'auto_size': order_params.get('auto_size', None)
            }
            
            # None 값 제거
            order_data = {k: v for k, v in order_data.items() if v is not None}
            
            response = await self._request('POST', endpoint, data=order_data)
            logger.info(f"주문 생성 완료: {response}")
            return response
            
        except Exception as e:
            logger.error(f"주문 생성 실패: {e}")
            raise
    
    async def get_contract_info(self, settle: str = "usdt", contract: str = "BTC_USDT") -> Dict:
        """계약 정보 조회"""
        endpoint = f"/api/v4/futures/{settle}/contracts/{contract}"
        try:
            response = await self._request('GET', endpoint)
            return response
        except Exception as e:
            logger.error(f"계약 정보 조회 실패: {e}")
            raise
    
    async def get_ticker(self, settle: str = "usdt", contract: str = "BTC_USDT") -> Dict:
        """현재가 조회"""
        endpoint = f"/api/v4/futures/{settle}/tickers"
        params = {'contract': contract}
        try:
            response = await self._request('GET', endpoint, params=params)
            if isinstance(response, list) and len(response) > 0:
                return response[0]
            return response
        except Exception as e:
            logger.error(f"현재가 조회 실패: {e}")
            raise
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Gate.io 클라이언트 세션 종료")
