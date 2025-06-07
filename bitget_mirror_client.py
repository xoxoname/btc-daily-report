import asyncio
import aiohttp
import hmac
import hashlib
import base64
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import traceback

logger = logging.getLogger(__name__)

class BitgetMirrorClient:
    """Bitget 미러 트레이딩 전용 클라이언트 - API 엔드포인트 수정"""
    
    def __init__(self, config):
        self.config = config
        self.base_url = "https://api.bitget.com"
        self.session = None
        
        # 기본 설정
        self.symbol = "BTCUSDT"
        self.symbol_v1 = "BTCUSDT_UMCBL"
        self.product_type = "USDT-FUTURES"
        self.margin_coin = "USDT"
        
        # 🔥🔥🔥 올바른 API 엔드포인트들 (Bitget v2 공식 문서 기준)
        self.position_endpoints = [
            "/api/v2/mix/position/all-position",      # ✅ v2 포지션 조회 (올바른 엔드포인트)
            "/api/mix/v1/position/allPosition",       # v1 대체
        ]
        
        # 🔥🔥🔥 올바른 예약 주문 엔드포인트들
        self.plan_order_endpoints = [
            "/api/v2/mix/order/orders-plan-pending",  # ✅ v2 예약 주문 조회 (올바른 엔드포인트)
            "/api/mix/v1/plan/currentPlan",           # v1 대체
        ]
        
        # 🔥🔥🔥 올바른 주문 히스토리 엔드포인트들
        self.order_history_endpoints = [
            "/api/v2/mix/order/orders-history",       # ✅ v2 주문 히스토리 (올바른 엔드포인트)
            "/api/mix/v1/order/historyOrders",        # v1 대체
        ]
        
        # API 키 검증 상태
        self.api_keys_validated = False
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.min
        
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
        """API 키 유효성 검증 - 올바른 파라미터 사용"""
        try:
            logger.info("비트겟 미러링 API 키 유효성 검증 시작...")
            
            # 🔥🔥🔥 올바른 파라미터로 검증 시도 (Bitget v2 공식 문서 기준)
            endpoints_to_try = [
                # v2 API 시도 (권장)
                ("/api/v2/mix/account/accounts", {
                    'productType': self.product_type,  # USDT-FUTURES
                    'marginCoin': self.margin_coin     # USDT
                }),
                # v1 API 시도 (호환성)
                ("/api/mix/v1/account/accounts", {
                    'symbol': self.symbol_v1,  # BTCUSDT_UMCBL
                    'marginCoin': self.margin_coin
                }),
                # 가장 기본적인 계정 조회
                ("/api/v2/mix/account/accounts", {
                    'productType': self.product_type
                })
            ]
            
            for endpoint, params in endpoints_to_try:
                try:
                    logger.info(f"API 키 검증 시도: {endpoint}, 파라미터: {params}")
                    response = await self._request('GET', endpoint, params=params, max_retries=1)
                    
                    if response is not None:
                        self.api_keys_validated = True
                        self.api_connection_healthy = True
                        self.consecutive_failures = 0
                        logger.info("✅ 비트겟 미러링 API 키 검증 성공")
                        return
                        
                except Exception as e:
                    logger.warning(f"API 키 검증 시도 실패: {endpoint} - {e}")
                    continue
            
            logger.error("❌ 모든 API 키 검증 시도 실패")
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
        timestamp = str(int(datetime.now().timestamp() * 1000))
        signature = self._generate_signature(timestamp, method, request_path, body)
        
        return {
            'ACCESS-KEY': self.config.bitget_api_key,
            'ACCESS-SIGN': signature,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-PASSPHRASE': self.config.bitget_passphrase,
            'Content-Type': 'application/json',
            'locale': 'en-US'
        }
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                       data: Optional[Dict] = None, max_retries: int = 3) -> Optional[Dict]:
        """API 요청 - 파라미터 검증 강화"""
        if not self.session:
            self._initialize_session()
        
        # 🔥🔥🔥 파라미터 검증 및 정리
        if params:
            # None 값 제거
            params = {k: v for k, v in params.items() if v is not None}
            
            # 빈 문자열 제거
            params = {k: v for k, v in params.items() if v != ''}
            
            # 타입 검증
            for key, value in params.items():
                if isinstance(value, (int, float)):
                    params[key] = str(value)
                elif not isinstance(value, str):
                    params[key] = str(value)
        
        url = f"{self.base_url}{endpoint}"
        
        # 쿼리 스트링 생성
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            url = f"{url}?{query_string}"
            request_path = f"{endpoint}?{query_string}"
        else:
            request_path = endpoint
        
        body = json.dumps(data) if data else ''
        headers = self._get_headers(method, request_path, body)
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"비트겟 미러링 API 요청 (시도 {attempt + 1}/{max_retries}): {method} {endpoint}")
                
                attempt_timeout = aiohttp.ClientTimeout(total=20 + (attempt * 10), connect=10 + (attempt * 5))
                
                async with self.session.request(
                    method, url, headers=headers, data=body, timeout=attempt_timeout
                ) as response:
                    response_text = await response.text()
                    
                    # 🔥🔥🔥 404 오류는 즉시 실패 처리 (재시도 없음)
                    if response.status == 404:
                        error_msg = f"HTTP 404: 엔드포인트가 존재하지 않음 - {endpoint}"
                        logger.warning(f"비트겟 API 404 오류 (재시도 안함): {error_msg}")
                        raise Exception(error_msg)
                    
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: {response_text}"
                        
                        # 🔥🔥🔥 파라미터 오류 시 상세 로깅
                        if response.status == 400:
                            logger.warning(f"HTTP 400: {response_text}")
                            logger.error("파라미터 검증 실패 상세:")
                            logger.error(f"  - 엔드포인트: {endpoint}")
                            logger.error(f"  - 파라미터: {params}")
                            logger.error(f"  - URL: {url}")
                            logger.error(f"  - 응답: {response_text}")
                        else:
                            logger.warning(error_msg)
                        
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) + (attempt * 0.5)
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            self.consecutive_failures += 1
                            self.api_connection_healthy = False
                            logger.error(f"요청 실패 (3/3): HTTP {response.status}")
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
                # 404 오류는 재시도하지 않음
                if "404" in str(e) or "NOT FOUND" in str(e):
                    logger.warning(f"비트겟 API 404 오류 - 엔드포인트 사용 불가: {endpoint}")
                    raise
                
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
            # 🔥🔥🔥 올바른 파라미터로 계정 정보 조회
            params = {
                'productType': self.product_type,
                'marginCoin': self.margin_coin
            }
            
            response = await self._request('GET', "/api/v2/mix/account/accounts", params=params)
            
            if response is not None:
                if isinstance(response, list) and len(response) > 0:
                    return response[0]
                elif isinstance(response, dict):
                    return response
            
            return {}
            
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            return {}
    
    async def get_positions(self) -> List[Dict]:
        """포지션 조회 - 엔드포인트별 시도"""
        positions = []
        
        for endpoint in self.position_endpoints:
            try:
                logger.debug(f"포지션 조회 시도: {endpoint}")
                
                if endpoint == "/api/v2/mix/position/all-position":
                    # v2 API 파라미터
                    params = {
                        'productType': self.product_type,
                        'marginCoin': self.margin_coin
                    }
                elif endpoint == "/api/mix/v1/position/allPosition":
                    # v1 API 파라미터
                    params = {
                        'symbol': self.symbol_v1,
                        'marginCoin': self.margin_coin
                    }
                else:
                    params = {'productType': self.product_type}
                
                response = await self._request('GET', endpoint, params=params, max_retries=2)
                
                if response:
                    if isinstance(response, list):
                        positions = response
                    elif isinstance(response, dict) and 'data' in response:
                        positions = response['data']
                    else:
                        positions = [response] if response else []
                    
                    logger.info(f"✅ 포지션 조회 성공 ({endpoint}): {len(positions)}개")
                    break
                    
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg or "NOT FOUND" in error_msg:
                    logger.debug(f"포지션 엔드포인트 {endpoint} 404 오류 (예상됨), 다음 시도")
                else:
                    logger.warning(f"포지션 엔드포인트 {endpoint} 실패: {e}")
                continue
        
        return positions or []
    
    async def get_plan_orders(self) -> List[Dict]:
        """예약 주문 조회 - 엔드포인트별 시도"""
        orders = []
        
        for endpoint in self.plan_order_endpoints:
            try:
                logger.debug(f"예약 주문 조회 시도: {endpoint}")
                
                if endpoint == "/api/v2/mix/order/orders-plan-pending":
                    # v2 API 파라미터
                    params = {
                        'productType': self.product_type,
                        'symbol': self.symbol
                    }
                elif endpoint == "/api/mix/v1/plan/currentPlan":
                    # v1 API 파라미터
                    params = {
                        'symbol': self.symbol_v1,
                        'productType': 'umcbl'
                    }
                else:
                    params = {'symbol': self.symbol}
                
                response = await self._request('GET', endpoint, params=params, max_retries=2)
                
                if response:
                    if isinstance(response, list):
                        orders = response
                    elif isinstance(response, dict) and 'data' in response:
                        orders = response['data']
                    else:
                        orders = [response] if response else []
                    
                    logger.info(f"✅ 예약 주문 조회 성공 ({endpoint}): {len(orders)}개")
                    break
                    
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg or "NOT FOUND" in error_msg:
                    logger.debug(f"예약 주문 엔드포인트 {endpoint} 404 오류 (예상됨), 다음 시도")
                else:
                    logger.warning(f"예약 주문 엔드포인트 {endpoint} 실패: {e}")
                continue
        
        if not orders:
            logger.error("예약 주문 조회 실패: HTTP 400")
        
        return orders or []
    
    async def get_tp_sl_orders(self) -> List[Dict]:
        """TP/SL 주문 조회"""
        try:
            # 🔥🔥🔥 올바른 TP/SL 엔드포인트 사용
            params = {
                'productType': self.product_type,
                'symbol': self.symbol
            }
            
            response = await self._request('GET', "/api/v2/mix/order/orders-tpsl-pending", params=params)
            
            if response:
                if isinstance(response, list):
                    return response
                elif isinstance(response, dict) and 'data' in response:
                    return response['data']
                else:
                    return [response] if response else []
            
            return []
            
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "NOT FOUND" in error_msg:
                logger.debug("TP/SL 엔드포인트 404 오류 (예상됨)")
            else:
                logger.error(f"TP/SL 주문 조회 실패: {e}")
            logger.error("TP/SL 주문 조회 실패: HTTP 404")
            return []
    
    async def get_order_history(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict]:
        """주문 히스토리 조회"""
        orders = []
        
        for endpoint in self.order_history_endpoints:
            try:
                logger.debug(f"주문 히스토리 조회 시도: {endpoint}")
                
                if endpoint == "/api/v2/mix/order/orders-history":
                    # v2 API 파라미터
                    params = {
                        'productType': self.product_type,
                        'symbol': self.symbol
                    }
                elif endpoint == "/api/mix/v1/order/historyOrders":
                    # v1 API 파라미터
                    params = {
                        'symbol': self.symbol_v1,
                        'productType': 'umcbl'
                    }
                else:
                    params = {'symbol': self.symbol}
                
                # 시간 범위 추가 (선택적)
                if start_time:
                    params['startTime'] = str(start_time)
                if end_time:
                    params['endTime'] = str(end_time)
                
                response = await self._request('GET', endpoint, params=params, max_retries=2)
                
                if response:
                    if isinstance(response, list):
                        orders = response
                    elif isinstance(response, dict) and 'data' in response:
                        orders = response['data']
                    else:
                        orders = [response] if response else []
                    
                    logger.info(f"✅ 주문 히스토리 조회 성공 ({endpoint}): {len(orders)}개")
                    break
                    
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg or "NOT FOUND" in error_msg:
                    logger.debug(f"주문 히스토리 엔드포인트 {endpoint} 404 오류 (예상됨), 다음 시도")
                else:
                    logger.warning(f"주문 히스토리 엔드포인트 {endpoint} 실패: {e}")
                continue
        
        return orders or []
    
    async def place_order(self, side: str, size: str, order_type: str = "market", 
                          price: Optional[str] = None, reduce_only: bool = False) -> Optional[Dict]:
        """주문 실행"""
        try:
            # 🔥🔥🔥 올바른 주문 실행 엔드포인트 및 파라미터
            order_data = {
                'symbol': self.symbol,
                'productType': self.product_type,
                'marginMode': 'crossed',
                'marginCoin': self.margin_coin,
                'size': size,
                'side': side,
                'orderType': order_type,
                'force': 'gtc'
            }
            
            if price:
                order_data['price'] = price
            
            if reduce_only:
                order_data['reduceOnly'] = 'YES'
            
            response = await self._request('POST', "/api/v2/mix/order/place-order", data=order_data)
            
            if response:
                logger.info(f"✅ 주문 실행 성공: {side} {size} {self.symbol}")
                return response
            else:
                logger.error(f"❌ 주문 실행 실패: 응답 없음")
                return None
                
        except Exception as e:
            logger.error(f"❌ 주문 실행 실패: {e}")
            return None
    
    async def close(self):
        """클라이언트 종료"""
        try:
            if self.session:
                await self.session.close()
                self.session = None
                logger.info("Bitget 미러링 클라이언트 세션 종료")
        except Exception as e:
            logger.error(f"클라이언트 종료 실패: {e}")
