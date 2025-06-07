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
    """Bitget 미러링 전용 클라이언트 - 정확한 API 엔드포인트 및 파라미터 사용"""
    
    def __init__(self, config):
        self.config = config
        self.session = None
        self._initialize_session()
        
        # API 연결 상태 추적
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
        self.max_consecutive_failures = 10
        
        # 🔥🔥🔥 정확한 Bitget 파라미터 설정
        self.product_type = "usdt-futures"  # 정확한 소문자 형식
        self.symbol = "BTCUSDT"             # 기본 심볼
        self.symbol_v1 = "BTCUSDT_UMCBL"    # v1 API용 심볼 형식
        self.margin_coin = "USDT"           # 마진 코인
        
        # 🔥🔥🔥 정확한 v2 API 엔드포인트들 (수정됨)
        self.ticker_endpoints = [
            "/api/v2/mix/market/ticker",   # v2 API 메인
            "/api/mix/v1/market/ticker",   # v1 대체
        ]
        
        # 🔥🔥🔥 정확한 예약 주문 조회 엔드포인트들 (수정됨)
        self.plan_order_endpoints = [
            "/api/v2/mix/order/orders-plan-pending",  # ✅ 정확한 v2 엔드포인트
            "/api/mix/v1/plan/currentPlan",           # v1 대체
        ]
        
        # 🔥🔥🔥 정확한 예약 주문 히스토리 엔드포인트들 (수정됨)
        self.plan_history_endpoints = [
            "/api/v2/mix/order/orders-plan-history",  # ✅ 정확한 v2 엔드포인트
            "/api/mix/v1/plan/historyPlan",           # v1 대체
        ]
        
        # 🔥🔥🔥 정확한 주문 히스토리 엔드포인트들 (수정됨)
        self.order_history_endpoints = [
            "/api/v2/mix/order/orders-history",       # ✅ 정확한 v2 엔드포인트
            "/api/mix/v1/order/historyOrders",        # v1 대체
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
        """API 키 유효성 검증 - 정확한 파라미터 사용"""
        try:
            logger.info("비트겟 미러링 API 키 유효성 검증 시작...")
            
            # 🔥🔥🔥 정확한 파라미터로 검증 시도
            endpoints_to_try = [
                ("/api/v2/mix/account/accounts", {
                    'productType': self.product_type,  # usdt-futures
                    'marginCoin': self.margin_coin
                }),
                ("/api/mix/v1/account/accounts", {
                    'symbol': self.symbol_v1,  # v1 API는 _UMCBL 형식 사용
                    'marginCoin': self.margin_coin
                }),
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
    
    def _get_v1_symbol(self, symbol: str = None) -> str:
        """🔥🔥🔥 v1 API용 심볼 변환"""
        if symbol is None:
            symbol = self.symbol
        
        # 이미 _UMCBL이 있으면 그대로 반환
        if "_UMCBL" in symbol:
            return symbol
        
        # BTCUSDT -> BTCUSDT_UMCBL
        return f"{symbol}_UMCBL"
    
    def _is_v1_endpoint(self, endpoint: str) -> bool:
        """🔥🔥🔥 v1 API 엔드포인트인지 확인"""
        return "/v1/" in endpoint or endpoint.startswith("/api/mix/v1/")
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None, max_retries: int = 3) -> Dict:
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
                        logger.error(f"비트겟 API 오류: {error_msg}")
                        
                        # 🔥🔥🔥 파라미터 오류 시 상세 로깅
                        if response.status == 400:
                            logger.error("파라미터 검증 실패 상세:")
                            logger.error(f"  - 엔드포인트: {endpoint}")
                            logger.error(f"  - 파라미터: {params}")
                            logger.error(f"  - 응답: {response_text}")
                        
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
            raise
    
    async def get_positions(self, symbol: str = "BTCUSDT") -> List[Dict]:
        """포지션 조회"""
        try:
            params = {
                'productType': self.product_type,
                'marginCoin': self.margin_coin
            }
            
            if symbol:
                params['symbol'] = symbol
            
            response = await self._request('GET', "/api/v2/mix/position/all-position", params=params)
            
            if response is not None:
                return response if isinstance(response, list) else []
            
            return []
            
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []
    
    async def get_pending_orders(self, symbol: str = "BTCUSDT") -> List[Dict]:
        """미체결 주문 조회"""
        try:
            params = {
                'symbol': symbol,
                'productType': self.product_type
            }
            
            response = await self._request('GET', "/api/v2/mix/order/orders-pending", params=params)
            
            if response is not None:
                return response if isinstance(response, list) else []
            
            return []
            
        except Exception as e:
            logger.error(f"미체결 주문 조회 실패: {e}")
            return []
    
    async def get_plan_orders(self, symbol: str = "BTCUSDT") -> List[Dict]:
        """🔥🔥🔥 예약 주문 조회 - 정확한 엔드포인트 사용"""
        try:
            # 🔥🔥🔥 정확한 파라미터 사용
            params = {
                'symbol': symbol,
                'productType': self.product_type  # usdt-futures
            }
            
            # 🔥🔥🔥 정확한 엔드포인트 사용
            response = await self._request('GET', "/api/v2/mix/order/orders-plan-pending", params=params)
            
            if response is not None:
                return response if isinstance(response, list) else []
            
            return []
            
        except Exception as e:
            logger.error(f"예약 주문 조회 실패: {e}")
            return []
    
    async def get_all_plan_orders(self, symbol: str = "BTCUSDT") -> List[Dict]:
        """🎯 비트겟 모든 예약 주문 조회 (모든 타입)"""
        logger.info(f"🎯 비트겟 모든 예약 주문 조회 시작: {symbol}")
        
        all_orders = []
        
        # 🔥🔥🔥 모든 예약 주문 타입 조회
        plan_types = [
            'profit_loss',      # TP/SL 주문
            'normal_plan',      # 일반 예약 주문
            'pos_profit_loss',  # 포지션 TP/SL
            'moving_plan'       # 트레일링 스탑
        ]
        
        for plan_type in plan_types:
            try:
                params = {
                    'symbol': symbol,
                    'productType': self.product_type,  # usdt-futures
                    'planType': plan_type
                }
                
                logger.debug(f"예약 주문 조회 - 타입: {plan_type}")
                
                # 🔥🔥🔥 정확한 엔드포인트 사용
                response = await self._request('GET', "/api/v2/mix/order/orders-plan-pending", params=params)
                
                if response and isinstance(response, list):
                    for order in response:
                        order['planType'] = plan_type  # 타입 명시
                    all_orders.extend(response)
                    logger.debug(f"예약 주문 발견: {plan_type} - {len(response)}개")
                    
            except Exception as e:
                logger.warning(f"예약 주문 타입 {plan_type} 조회 실패: {e}")
                continue
        
        logger.info(f"🎯 비트겟 모든 예약 주문 조회 완료: 총 {len(all_orders)}개")
        return all_orders
    
    async def get_plan_order_history(self, symbol: str = "BTCUSDT", days: int = 7) -> List[Dict]:
        """🔥🔥🔥 예약 주문 히스토리 조회 - 정확한 엔드포인트 사용"""
        try:
            # 🔥🔥🔥 정확한 파라미터 사용
            params = {
                'symbol': symbol,
                'productType': self.product_type,  # usdt-futures
                'startTime': str(int((datetime.now() - timedelta(days=days)).timestamp() * 1000)),
                'endTime': str(int(datetime.now().timestamp() * 1000))
            }
            
            # 🔥🔥🔥 정확한 엔드포인트 사용
            response = await self._request('GET', "/api/v2/mix/order/orders-plan-history", params=params)
            
            if response is not None:
                return response if isinstance(response, list) else []
            
            return []
            
        except Exception as e:
            logger.error(f"예약 주문 히스토리 조회 실패: {e}")
            return []
    
    async def get_order_history(self, symbol: str = "BTCUSDT", days: int = 7) -> List[Dict]:
        """🔥🔥🔥 주문 히스토리 조회 - 정확한 엔드포인트 사용"""
        try:
            # 🔥🔥🔥 정확한 파라미터 사용
            params = {
                'symbol': symbol,
                'productType': self.product_type,  # usdt-futures
                'startTime': str(int((datetime.now() - timedelta(days=days)).timestamp() * 1000)),
                'endTime': str(int(datetime.now().timestamp() * 1000))
            }
            
            # 🔥🔥🔥 정확한 엔드포인트 사용
            response = await self._request('GET', "/api/v2/mix/order/orders-history", params=params)
            
            if response is not None:
                # 응답이 dict이고 entrustedList가 있는 경우
                if isinstance(response, dict) and 'entrustedList' in response:
                    return response['entrustedList']
                # 응답이 list인 경우
                elif isinstance(response, list):
                    return response
            
            return []
            
        except Exception as e:
            logger.error(f"주문 히스토리 조회 실패: {e}")
            return []
    
    async def get_ticker(self, symbol: str = "BTCUSDT") -> Optional[Dict]:
        """티커 정보 조회"""
        try:
            params = {
                'symbol': symbol,
                'productType': self.product_type
            }
            
            response = await self._request('GET', "/api/v2/mix/market/ticker", params=params)
            
            if response and isinstance(response, list) and len(response) > 0:
                return response[0]
            
            return None
            
        except Exception as e:
            logger.error(f"티커 정보 조회 실패: {e}")
            return None
    
    async def place_order(self, order_data: Dict) -> Optional[Dict]:
        """주문 생성"""
        try:
            # 기본 파라미터 추가
            order_data['productType'] = self.product_type
            if 'marginCoin' not in order_data:
                order_data['marginCoin'] = self.margin_coin
            
            response = await self._request('POST', "/api/v2/mix/order/place-order", data=order_data)
            return response
            
        except Exception as e:
            logger.error(f"주문 생성 실패: {e}")
            return None
    
    async def cancel_order(self, order_id: str, symbol: str = "BTCUSDT") -> bool:
        """주문 취소"""
        try:
            order_data = {
                'orderId': order_id,
                'symbol': symbol,
                'productType': self.product_type
            }
            
            response = await self._request('POST', "/api/v2/mix/order/cancel-order", data=order_data)
            return response is not None
            
        except Exception as e:
            logger.error(f"주문 취소 실패: {e}")
            return False
    
    async def cancel_plan_order(self, order_id: str, symbol: str = "BTCUSDT", plan_type: str = "normal_plan") -> bool:
        """예약 주문 취소"""
        try:
            order_data = {
                'orderId': order_id,
                'symbol': symbol,
                'productType': self.product_type,
                'planType': plan_type
            }
            
            response = await self._request('POST', "/api/v2/mix/order/cancel-plan-order", data=order_data)
            return response is not None
            
        except Exception as e:
            logger.error(f"예약 주문 취소 실패: {e}")
            return False
    
    async def close(self):
        """클라이언트 종료"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("Bitget 미러링 클라이언트 세션 종료")
    
    def __del__(self):
        """소멸자"""
        if self.session:
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self.close())
            except:
                pass
