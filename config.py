import asyncio
import aiohttp
import hmac
import hashlib
import time
import json
import logging
import base64
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import traceback

logger = logging.getLogger(__name__)

class BitgetClient:
    """Bitget API V2 클라이언트"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config.BITGET_APIKEY
        self.api_secret = config.BITGET_APISECRET
        self.passphrase = config.BITGET_PASSPHRASE
        self.base_url = "https://api.bitget.com"
        self.session = None
        
        # 심볼 설정 - V2 API 형식
        self.symbol = "BTCUSDT_UMCBL"  # USDT-M 선물
        
    async def initialize(self):
        """클라이언트 초기화"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info("Bitget 클라이언트 초기화 완료")
    
    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """API 서명 생성 - V2 방식"""
        try:
            # V2 API 서명 메시지 형식
            message = timestamp + method.upper() + request_path + body
            
            # Base64로 인코딩된 secret key 사용
            secret_key = base64.b64decode(self.api_secret)
            
            # HMAC-SHA256 서명
            signature = hmac.new(
                secret_key,
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
            
            # Base64 인코딩
            return base64.b64encode(signature).decode('utf-8')
            
        except Exception as e:
            logger.error(f"서명 생성 실패: {e}")
            # 폴백: 기존 방식
            message = timestamp + method.upper() + request_path + body
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
            return base64.b64encode(signature).decode('utf-8')
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """API 요청"""
        if not self.session:
            await self.initialize()
        
        url = f"{self.base_url}{endpoint}"
        timestamp = str(int(time.time() * 1000))
        
        query_string = ""
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            if query_string:
                url += f"?{query_string}"
        
        body = ""
        if data:
            body = json.dumps(data, separators=(',', ':'))
        
        request_path = endpoint
        if query_string:
            request_path += f"?{query_string}"
        
        signature = self._generate_signature(timestamp, method, request_path, body)
        
        headers = {
            'ACCESS-KEY': self.api_key,
            'ACCESS-SIGN': signature,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json',
            'locale': 'en-US'
        }
        
        try:
            logger.debug(f"Bitget API 요청: {method} {url}")
            if body:
                logger.debug(f"요청 본문: {body}")
            
            async with self.session.request(method, url, headers=headers, data=body) as response:
                response_text = await response.text()
                logger.debug(f"Bitget 응답: {response.status} - {response_text[:500]}")
                
                if response.status != 200:
                    logger.error(f"Bitget API 오류: {response.status} - {response_text}")
                    raise Exception(f"Bitget API 오류: {response_text}")
                
                result = json.loads(response_text) if response_text else {}
                
                # V2 API 오류 체크
                if result.get('code') != '00000':
                    error_msg = result.get('msg', 'Unknown error')
                    logger.error(f"Bitget API 오류 응답: {result}")
                    raise Exception(f"Bitget API 오류: {error_msg}")
                
                return result
                
        except Exception as e:
            logger.error(f"Bitget API 요청 중 오류: {e}")
            raise
    
    async def get_account_info(self) -> Dict:
        """계정 정보 조회 - V2 API"""
        try:
            # V2 API 엔드포인트
            endpoint = "/api/v2/mix/account/account"
            params = {
                'symbol': self.symbol,
                'marginCoin': 'USDT'
            }
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('data'):
                return response['data']
            else:
                logger.error(f"계정 정보 조회 실패: {response}")
                return {}
                
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            return {}
    
    async def get_positions(self, symbol: str = None) -> List[Dict]:
        """포지션 조회 - V2 API"""
        try:
            if symbol is None:
                symbol = self.symbol
                
            # V2 API 엔드포인트
            endpoint = "/api/v2/mix/position/all-position"
            params = {
                'symbol': symbol,
                'marginCoin': 'USDT'
            }
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []
    
    async def get_ticker(self, symbol: str = None) -> Dict:
        """티커 정보 조회 - V2 API"""
        try:
            if symbol is None:
                symbol = self.symbol
                
            # V2 API 엔드포인트
            endpoint = "/api/v2/mix/market/ticker"
            params = {'symbol': symbol}
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('data'):
                return response['data']
            else:
                return {}
                
        except Exception as e:
            logger.error(f"티커 조회 실패: {e}")
            return {}
    
    async def get_kline(self, symbol: str, granularity: str, limit: int = 100) -> List[List]:
        """K라인 데이터 조회 - V2 API"""
        try:
            endpoint = "/api/v2/mix/market/candles"
            params = {
                'symbol': symbol or self.symbol,
                'granularity': granularity,
                'limit': str(limit)
            }
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"K라인 데이터 조회 실패: {e}")
            return []
    
    async def get_funding_rate(self, symbol: str = None) -> Dict:
        """펀딩비 조회 - V2 API"""
        try:
            if symbol is None:
                symbol = self.symbol
                
            endpoint = "/api/v2/mix/market/current-fund-rate"
            params = {'symbol': symbol}
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('data'):
                return response['data']
            else:
                return {}
                
        except Exception as e:
            logger.error(f"펀딩비 조회 실패: {e}")
            return {}
    
    async def get_open_interest(self, symbol: str = None) -> Dict:
        """미결제약정 조회 - V2 API"""
        try:
            if symbol is None:
                symbol = self.symbol
                
            endpoint = "/api/v2/mix/market/open-interest"
            params = {'symbol': symbol}
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('data'):
                return response['data']
            else:
                return {}
                
        except Exception as e:
            logger.error(f"미결제약정 조회 실패: {e}")
            return {}
    
    async def get_recent_filled_orders(self, symbol: str = None, minutes: int = 5) -> List[Dict]:
        """최근 체결 주문 조회 - V2 API"""
        try:
            if symbol is None:
                symbol = self.symbol
                
            endpoint = "/api/v2/mix/order/fills"
            end_time = int(time.time() * 1000)
            start_time = end_time - (minutes * 60 * 1000)
            
            params = {
                'symbol': symbol,
                'startTime': str(start_time),
                'endTime': str(end_time)
            }
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"최근 체결 주문 조회 실패: {e}")
            return []
    
    async def get_trade_fills(self, symbol: str = None, start_time: int = None, 
                            end_time: int = None, limit: int = 100) -> List[Dict]:
        """거래 내역 조회 - V2 API"""
        try:
            if symbol is None:
                symbol = self.symbol
                
            endpoint = "/api/v2/mix/order/fills"
            params = {
                'symbol': symbol,
                'limit': str(limit)
            }
            
            if start_time:
                params['startTime'] = str(start_time)
            if end_time:
                params['endTime'] = str(end_time)
            
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"거래 내역 조회 실패: {e}")
            return []
    
    async def get_all_plan_orders_with_tp_sl(self, symbol: str = None) -> Dict:
        """모든 예약 주문 조회 (TP/SL 포함) - V2 API"""
        try:
            if symbol is None:
                symbol = self.symbol
                
            result = {
                'plan_orders': [],
                'tp_sl_orders': []
            }
            
            # 일반 예약 주문 조회
            try:
                endpoint = "/api/v2/mix/order/plan-pending"
                params = {'symbol': symbol}
                response = await self._request('GET', endpoint, params=params)
                
                if response.get('data'):
                    result['plan_orders'] = response['data']
            except Exception as e:
                logger.warning(f"예약 주문 조회 실패: {e}")
            
            # TP/SL 주문 조회
            try:
                endpoint = "/api/v2/mix/order/plan-pending"
                params = {
                    'symbol': symbol,
                    'planType': 'profit_plan'
                }
                response = await self._request('GET', endpoint, params=params)
                
                if response.get('data'):
                    result['tp_sl_orders'].extend(response['data'])
            except Exception as e:
                logger.warning(f"TP/SL 주문 조회 실패: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"예약 주문 조회 실패: {e}")
            return {'plan_orders': [], 'tp_sl_orders': []}
    
    async def get_enhanced_profit_history(self, days: int = 7) -> Dict:
        """향상된 손익 내역 조회 - V2 API"""
        try:
            end_time = int(time.time() * 1000)
            start_time = end_time - (days * 24 * 60 * 60 * 1000)
            
            endpoint = "/api/v2/mix/account/account-bill"
            params = {
                'symbol': self.symbol,
                'marginCoin': 'USDT',
                'startTime': str(start_time),
                'endTime': str(end_time),
                'pageSize': '100'
            }
            
            response = await self._request('GET', endpoint, params=params)
            
            total_pnl = 0.0
            
            if response.get('data'):
                for record in response['data']:
                    change = float(record.get('amount', 0))
                    business_type = record.get('businessType', '')
                    
                    # 실현 손익만 계산
                    if business_type in ['close_long', 'close_short', 'delivery_long', 'delivery_short']:
                        total_pnl += change
            
            return {
                'total_pnl': total_pnl,
                'average_daily': total_pnl / days if days > 0 else 0,
                'days': days
            }
            
        except Exception as e:
            logger.error(f"손익 내역 조회 실패: {e}")
            return {
                'total_pnl': 0.0,
                'average_daily': 0.0,
                'days': days
            }
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
