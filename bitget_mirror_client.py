import asyncio
import hmac
import hashlib
import base64
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import aiohttp
import pytz
import traceback

logger = logging.getLogger(__name__)

class BitgetMirrorClient:
    """Bitget 미러링 전용 클라이언트 - 예약 주문 체결 내역 확인 기능 추가"""
    
    def __init__(self, config):
        self.config = config
        self.session = None
        self._initialize_session()
        
        # API 연결 상태 추적
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
        self.max_consecutive_failures = 10
        
        # 백업 엔드포인트들
        self.ticker_endpoints = [
            "/api/v2/mix/market/ticker",
            "/api/mix/v1/market/ticker",
            "/api/v2/spot/market/tickers",
        ]
        
        # API 키 검증 상태
        self.api_keys_validated = False
        
    def _initialize_session(self):
        """세션 초기화"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=60, connect=30)
            connector = aiohttp.TCPConnector(
                limit=100, limit_per_host=30, ttl_dns_cache=300,
                use_dns_cache=True, keepalive_timeout=60, enable_cleanup_closed=True
            )
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
            logger.info("Bitget 미러링 클라이언트 세션 초기화 완료")
        
    async def initialize(self):
        """클라이언트 초기화"""
        self._initialize_session()
        await self._validate_api_keys()
        logger.info("Bitget 미러링 클라이언트 초기화 완료")
    
    async def _validate_api_keys(self):
        """API 키 유효성 검증"""
        try:
            logger.info("비트겟 미러링 API 키 유효성 검증 시작...")
            
            endpoint = "/api/v2/mix/account/accounts"
            params = {'productType': 'USDT-FUTURES', 'marginCoin': 'USDT'}
            
            response = await self._request('GET', endpoint, params=params)
            
            if response is not None:
                self.api_keys_validated = True
                self.api_connection_healthy = True
                self.consecutive_failures = 0
                logger.info("✅ 비트겟 미러링 API 키 검증 성공")
            else:
                logger.error("❌ 비트겟 미러링 API 키 검증 실패: 응답 없음")
                self.api_keys_validated = False
                
        except Exception as e:
            logger.error(f"❌ 비트겟 미러링 API 키 검증 실패: {e}")
            self.api_keys_validated = False
    
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
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None, max_retries: int = 5) -> Dict:
        """API 요청 - 강화된 오류 처리"""
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
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"비트겟 미러링 API 요청 (시도 {attempt + 1}/{max_retries}): {method} {endpoint}")
                
                attempt_timeout = aiohttp.ClientTimeout(total=30 + (attempt * 10), connect=10 + (attempt * 5))
                
                async with self.session.request(
                    method, url, headers=headers, data=body, timeout=attempt_timeout
                ) as response:
                    response_text = await response.text()
                    
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: {response_text}"
                        logger.error(f"비트겟 API 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) + (attempt * 0.5)
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            self.consecutive_failures += 1
                            self.api_connection_healthy = False
                            raise Exception(error_msg)
                    
                    if not response_text.strip():
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise Exception("빈 응답")
                    
                    try:
                        result = json.loads(response_text)
                        
                        # Bitget API 응답 구조 확인
                        if isinstance(result, dict):
                            if result.get('code') == '00000':
                                # 성공 응답
                                self.consecutive_failures = 0
                                self.api_connection_healthy = True
                                self.last_successful_call = datetime.now()
                                logger.debug(f"비트겟 API 응답 성공: {method} {endpoint}")
                                return result.get('data', result)
                            else:
                                # 에러 응답
                                error_code = result.get('code', 'unknown')
                                error_msg = result.get('msg', 'Unknown error')
                                logger.error(f"비트겟 API 에러: {error_code} - {error_msg}")
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(2 ** attempt)
                                    continue
                                else:
                                    self.consecutive_failures += 1
                                    raise Exception(f"Bitget API Error: {error_code} - {error_msg}")
                        else:
                            # 리스트나 다른 형태의 응답
                            self.consecutive_failures = 0
                            self.api_connection_healthy = True
                            self.last_successful_call = datetime.now()
                            return result
                            
                    except json.JSONDecodeError as e:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise Exception(f"JSON 파싱 실패: {e}")
                            
            except asyncio.TimeoutError:
                logger.warning(f"비트겟 API 타임아웃 (시도 {attempt + 1}/{max_retries}): {method} {endpoint}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(3 + (attempt * 2))
                    continue
                else:
                    self.consecutive_failures += 1
                    self.api_connection_healthy = False
                    raise Exception(f"요청 타임아웃 (최대 {max_retries}회 시도)")
                    
            except aiohttp.ClientError as e:
                logger.warning(f"비트겟 API 클라이언트 오류 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self.consecutive_failures += 1
                    self.api_connection_healthy = False
                    raise Exception(f"클라이언트 오류: {e}")
                    
            except Exception as e:
                logger.error(f"비트겟 API 예상치 못한 오류 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self.consecutive_failures += 1
                    self.api_connection_healthy = False
                    raise
    
    async def get_account_info(self) -> Dict:
        """계정 정보 조회"""
        try:
            endpoint = "/api/v2/mix/account/accounts"
            params = {'productType': 'USDT-FUTURES', 'marginCoin': 'USDT'}
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list) and len(response) > 0:
                return response[0]
            elif isinstance(response, dict):
                return response
            else:
                return {}
                
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            raise
    
    async def get_positions(self, symbol: str = "BTCUSDT") -> List[Dict]:
        """포지션 조회"""
        try:
            endpoint = "/api/v2/mix/position/all-position"
            params = {'productType': 'USDT-FUTURES', 'marginCoin': 'USDT'}
            response = await self._request('GET', endpoint, params=params)
            
            if not isinstance(response, list):
                return []
            
            # 특정 심볼 필터링
            filtered_positions = []
            for pos in response:
                if pos.get('symbol') == symbol and float(pos.get('total', 0)) > 0:
                    filtered_positions.append(pos)
            
            return filtered_positions
            
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []
    
    async def get_ticker(self, symbol: str = "BTCUSDT") -> Dict:
        """티커 정보 조회 - 여러 엔드포인트 시도"""
        for i, endpoint in enumerate(self.ticker_endpoints):
            try:
                params = {'symbol': symbol}
                if 'mix' in endpoint:
                    params['productType'] = 'USDT-FUTURES'
                
                response = await self._request('GET', endpoint, params=params, max_retries=2)
                
                if isinstance(response, list) and len(response) > 0:
                    ticker_data = response[0]
                elif isinstance(response, dict):
                    ticker_data = response
                else:
                    continue
                
                # 데이터 정규화
                if 'last' not in ticker_data and 'close' in ticker_data:
                    ticker_data['last'] = ticker_data['close']
                if 'last' not in ticker_data and 'price' in ticker_data:
                    ticker_data['last'] = ticker_data['price']
                
                if ticker_data.get('last'):
                    logger.debug(f"티커 조회 성공 (엔드포인트 {i+1}): {endpoint}")
                    return ticker_data
                    
            except Exception as e:
                logger.warning(f"티커 엔드포인트 {i+1} 실패: {endpoint} - {e}")
                continue
        
        logger.error("모든 티커 엔드포인트 실패")
        return {}
    
    async def get_all_plan_orders_with_tp_sl(self, symbol: str = "BTCUSDT") -> Dict:
        """🔥🔥🔥 모든 예약 주문 (Plan Orders + TP/SL Orders) 조회 - 핵심 메서드"""
        try:
            logger.info(f"🎯 비트겟 모든 예약 주문 조회 시작: {symbol}")
            
            # 1. 일반 예약 주문 조회
            plan_orders = []
            try:
                plan_endpoint = "/api/v2/mix/order/plan-orders-pending"
                plan_params = {
                    'symbol': symbol,
                    'productType': 'USDT-FUTURES'
                }
                plan_response = await self._request('GET', plan_endpoint, params=plan_params)
                
                if isinstance(plan_response, list):
                    plan_orders = plan_response
                elif isinstance(plan_response, dict) and 'orderList' in plan_response:
                    plan_orders = plan_response['orderList']
                
                logger.info(f"📋 일반 예약 주문: {len(plan_orders)}개")
                
            except Exception as e:
                logger.error(f"일반 예약 주문 조회 실패: {e}")
            
            # 2. TP/SL 주문 조회
            tp_sl_orders = []
            try:
                tp_sl_endpoint = "/api/v2/mix/order/plan-orders-tpsl-pending"
                tp_sl_params = {
                    'symbol': symbol,
                    'productType': 'USDT-FUTURES'
                }
                tp_sl_response = await self._request('GET', tp_sl_endpoint, params=tp_sl_params)
                
                if isinstance(tp_sl_response, list):
                    tp_sl_orders = tp_sl_response
                elif isinstance(tp_sl_response, dict) and 'orderList' in tp_sl_response:
                    tp_sl_orders = tp_sl_response['orderList']
                
                logger.info(f"🎯 TP/SL 주문: {len(tp_sl_orders)}개")
                
            except Exception as e:
                logger.error(f"TP/SL 주문 조회 실패: {e}")
            
            # 3. 결과 정리
            result = {
                'plan_orders': plan_orders,
                'tp_sl_orders': tp_sl_orders,
                'total_count': len(plan_orders) + len(tp_sl_orders)
            }
            
            logger.info(f"✅ 예약 주문 조회 완료: 일반 {len(plan_orders)}개, TP/SL {len(tp_sl_orders)}개, 총 {result['total_count']}개")
            
            return result
            
        except Exception as e:
            logger.error(f"모든 예약 주문 조회 실패: {e}")
            return {
                'plan_orders': [],
                'tp_sl_orders': [],
                'total_count': 0,
                'error': str(e)
            }
    
    async def get_recent_filled_orders(self, symbol: str = "BTCUSDT", minutes: int = 5) -> List[Dict]:
        """🔥🔥🔥 최근 체결된 주문 조회 - 실시간 미러링용"""
        try:
            # 시간 범위 계산 (UTC)
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=minutes)
            
            endpoint = "/api/v2/mix/order/fill-history"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES',
                'startTime': str(int(start_time.timestamp() * 1000)),
                'endTime': str(int(end_time.timestamp() * 1000)),
                'limit': '100'
            }
            
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list):
                filled_orders = response
            elif isinstance(response, dict) and 'fillList' in response:
                filled_orders = response['fillList']
            else:
                filled_orders = []
            
            # 중복 제거 및 정렬
            unique_orders = {}
            for order in filled_orders:
                order_id = order.get('orderId', order.get('id', ''))
                if order_id and order_id not in unique_orders:
                    unique_orders[order_id] = order
            
            result = list(unique_orders.values())
            
            if result:
                logger.info(f"🔥 최근 {minutes}분간 체결된 주문: {len(result)}개")
            else:
                logger.debug(f"최근 {minutes}분간 체결된 주문 없음")
            
            return result
            
        except Exception as e:
            logger.error(f"최근 체결 주문 조회 실패: {e}")
            return []
    
    async def get_recent_filled_plan_orders(self, symbol: str = "BTCUSDT", minutes: int = 5, order_id: str = None) -> List[Dict]:
        """🔥🔥🔥 최근 체결된 예약 주문 조회 - 예약 주문 체결/취소 구분용"""
        try:
            logger.info(f"🎯 최근 체결된 예약 주문 조회: {symbol}, {minutes}분간")
            
            # 시간 범위 계산
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=minutes)
            
            # 1. 일반 예약 주문 체결 내역
            filled_plan_orders = []
            try:
                plan_endpoint = "/api/v2/mix/order/plan-orders-history"
                plan_params = {
                    'symbol': symbol,
                    'productType': 'USDT-FUTURES',
                    'startTime': str(int(start_time.timestamp() * 1000)),
                    'endTime': str(int(end_time.timestamp() * 1000)),
                    'limit': '100'
                }
                
                if order_id:
                    plan_params['planOrderId'] = order_id
                
                plan_response = await self._request('GET', plan_endpoint, params=plan_params)
                
                if isinstance(plan_response, list):
                    filled_plan_orders.extend(plan_response)
                elif isinstance(plan_response, dict) and 'orderList' in plan_response:
                    filled_plan_orders.extend(plan_response['orderList'])
                
            except Exception as e:
                logger.error(f"예약 주문 체결 내역 조회 실패: {e}")
            
            # 2. TP/SL 주문 체결 내역
            try:
                tp_sl_endpoint = "/api/v2/mix/order/plan-orders-tpsl-history"
                tp_sl_params = {
                    'symbol': symbol,
                    'productType': 'USDT-FUTURES',
                    'startTime': str(int(start_time.timestamp() * 1000)),
                    'endTime': str(int(end_time.timestamp() * 1000)),
                    'limit': '100'
                }
                
                if order_id:
                    tp_sl_params['planOrderId'] = order_id
                
                tp_sl_response = await self._request('GET', tp_sl_endpoint, params=tp_sl_params)
                
                if isinstance(tp_sl_response, list):
                    filled_plan_orders.extend(tp_sl_response)
                elif isinstance(tp_sl_response, dict) and 'orderList' in tp_sl_response:
                    filled_plan_orders.extend(tp_sl_response['orderList'])
                
            except Exception as e:
                logger.error(f"TP/SL 주문 체결 내역 조회 실패: {e}")
            
            # 3. 특정 주문 ID 검색
            if order_id:
                matching_orders = [
                    order for order in filled_plan_orders 
                    if order.get('orderId') == order_id or order.get('planOrderId') == order_id
                ]
                
                if matching_orders:
                    logger.info(f"🎯 특정 주문 ID {order_id} 체결 내역 발견: {len(matching_orders)}개")
                    return matching_orders
                else:
                    logger.info(f"📝 특정 주문 ID {order_id} 체결 내역 없음")
                    return []
            
            # 4. 전체 결과 반환
            if filled_plan_orders:
                logger.info(f"✅ 최근 {minutes}분간 체결된 예약 주문: {len(filled_plan_orders)}개")
            else:
                logger.debug(f"최근 {minutes}분간 체결된 예약 주문 없음")
            
            return filled_plan_orders
            
        except Exception as e:
            logger.error(f"최근 체결 예약 주문 조회 실패: {e}")
            return []
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("비트겟 미러링 클라이언트 세션 종료")
