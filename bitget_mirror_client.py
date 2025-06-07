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
        
        # 🔥🔥🔥 시세 조회 엔드포인트들
        self.ticker_endpoints = [
            "/api/v2/mix/market/ticker",              # ✅ v2 시세 조회
            "/api/mix/v1/market/ticker",              # v1 대체
            "/api/v2/spot/market/tickers",            # 스팟 백업
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
        
        # 재시도 로직
        for attempt in range(max_retries):
            try:
                logger.debug(f"비트겟 미러링 API 요청 (시도 {attempt + 1}/{max_retries}): {method} {endpoint}")
                
                async with self.session.request(method, url, headers=headers, data=body) as response:
                    response_text = await response.text()
                    
                    logger.debug(f"비트겟 미러링 API 응답 상태: {response.status}")
                    logger.debug(f"비트겟 미러링 API 응답 내용: {response_text[:500]}...")
                    
                    # 빈 응답 체크
                    if not response_text.strip():
                        error_msg = f"빈 응답 받음 (상태: {response.status})"
                        logger.warning(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            logger.error(error_msg)
                            raise Exception(error_msg)
                    
                    # HTTP 상태 코드 체크
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: {response_text}"
                        logger.error(f"비트겟 미러링 API HTTP 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            logger.error(error_msg)
                            raise Exception(error_msg)
                    
                    # JSON 파싱
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError as json_error:
                        error_msg = f"JSON 파싱 실패: {json_error}, 응답: {response_text[:200]}"
                        logger.error(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            logger.error(error_msg)
                            raise Exception(error_msg)
                    
                    # API 응답 코드 체크
                    if response_data.get('code') != '00000':
                        error_msg = f"API 오류 코드: {response_data.get('code')}, 메시지: {response_data.get('msg', 'Unknown error')}"
                        logger.error(f"비트겟 미러링 API 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            logger.error(error_msg)
                            raise Exception(error_msg)
                    
                    # 성공 시 연결 상태 업데이트
                    self.api_connection_healthy = True
                    self.consecutive_failures = 0
                    self.last_successful_call = datetime.now()
                    
                    return response_data.get('data')
                    
            except Exception as e:
                self.consecutive_failures += 1
                logger.error(f"비트겟 미러링 API 요청 실패 (시도 {attempt + 1}): {e}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    if self.consecutive_failures >= 5:
                        self.api_connection_healthy = False
                    logger.error(f"비트겟 미러링 API 요청 최종 실패: {e}")
                    raise
        
        return None

    # 🔥🔥🔥 누락된 메서드들 추가 🔥🔥🔥
    
    async def get_ticker(self, symbol: str = None) -> Dict:
        """현재가 정보 조회"""
        symbol = symbol or self.symbol
        
        # 여러 엔드포인트 순차 시도
        for i, endpoint in enumerate(self.ticker_endpoints):
            try:
                logger.debug(f"티커 조회 시도 {i + 1}/{len(self.ticker_endpoints)}: {endpoint}")
                
                if endpoint == "/api/v2/mix/market/ticker":
                    # V2 믹스 마켓 (기본)
                    params = {
                        'symbol': symbol,
                        'productType': self.product_type
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                    if isinstance(response, list) and len(response) > 0:
                        ticker_data = response[0]
                    elif isinstance(response, dict):
                        ticker_data = response
                    else:
                        continue
                    
                elif endpoint == "/api/mix/v1/market/ticker":
                    # V1 믹스 마켓 (백업)
                    v1_symbol = f"{symbol}_UMCBL"
                    params = {
                        'symbol': v1_symbol
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                    if isinstance(response, dict):
                        ticker_data = response
                    else:
                        continue
                        
                elif endpoint == "/api/v2/spot/market/tickers":
                    # 스팟 마켓 (최후 백업)
                    spot_symbol = symbol.replace('USDT', '-USDT')
                    params = {
                        'symbol': spot_symbol
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                    if isinstance(response, list) and len(response) > 0:
                        ticker_data = response[0]
                    elif isinstance(response, dict):
                        ticker_data = response
                    else:
                        continue
                
                # 응답 데이터 검증 및 정규화
                if ticker_data and self._validate_ticker_data(ticker_data):
                    normalized_ticker = self._normalize_ticker_data(ticker_data, endpoint)
                    logger.debug(f"✅ 티커 조회 성공 ({endpoint}): ${normalized_ticker.get('last', 'N/A')}")
                    return normalized_ticker
                else:
                    logger.warning(f"티커 데이터 검증 실패: {endpoint}")
                    continue
                    
            except Exception as e:
                logger.warning(f"티커 엔드포인트 {endpoint} 실패: {e}")
                continue
        
        # 모든 엔드포인트 실패
        error_msg = f"모든 티커 엔드포인트 실패: {', '.join(self.ticker_endpoints)}"
        logger.error(error_msg)
        return {}
    
    def _validate_ticker_data(self, ticker_data: Dict) -> bool:
        """티커 데이터 유효성 검증"""
        try:
            if not isinstance(ticker_data, dict):
                return False
            
            # 필수 가격 필드 중 하나라도 있어야 함
            price_fields = ['last', 'lastPr', 'close', 'price', 'mark_price', 'markPrice']
            
            for field in price_fields:
                value = ticker_data.get(field)
                if value is not None:
                    try:
                        price = float(value)
                        if price > 0:
                            return True
                    except:
                        continue
            
            logger.warning(f"유효한 가격 필드 없음: {list(ticker_data.keys())}")
            return False
            
        except Exception as e:
            logger.error(f"티커 데이터 검증 오류: {e}")
            return False
    
    def _normalize_ticker_data(self, ticker_data: Dict, endpoint: str) -> Dict:
        """티커 데이터 정규화"""
        try:
            normalized = {}
            
            # 가격 필드 정규화
            price_mappings = [
                ('last', ['last', 'lastPr', 'close', 'price']),
                ('high', ['high', 'high24h', 'highPrice']),
                ('low', ['low', 'low24h', 'lowPrice']),
                ('volume', ['volume', 'vol', 'baseVolume', 'baseVol']),
                ('changeUtc', ['changeUtc', 'change', 'priceChange', 'priceChangePercent'])
            ]
            
            for target_field, source_fields in price_mappings:
                for source_field in source_fields:
                    value = ticker_data.get(source_field)
                    if value is not None:
                        try:
                            if target_field == 'changeUtc':
                                # 변화율을 소수로 변환 (예: "2.5%" -> 0.025)
                                if isinstance(value, str) and '%' in value:
                                    normalized[target_field] = float(value.replace('%', '')) / 100
                                else:
                                    normalized[target_field] = float(value)
                            else:
                                normalized[target_field] = float(value)
                            break
                        except:
                            continue
            
            # 기본값 설정
            if 'last' not in normalized:
                normalized['last'] = 0
            
            logger.debug(f"티커 데이터 정규화 완료: {normalized}")
            return normalized
            
        except Exception as e:
            logger.error(f"티커 데이터 정규화 오류: {e}")
            return {}

    async def get_positions(self) -> List[Dict]:
        """포지션 조회 - 인자 수정"""
        # 여러 엔드포인트 순차 시도
        for i, endpoint in enumerate(self.position_endpoints):
            try:
                logger.debug(f"포지션 조회 시도 {i + 1}/{len(self.position_endpoints)}: {endpoint}")
                
                if endpoint == "/api/v2/mix/position/all-position":
                    # V2 API
                    params = {
                        'productType': self.product_type,
                        'marginCoin': self.margin_coin
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                elif endpoint == "/api/mix/v1/position/allPosition":
                    # V1 API
                    params = {
                        'symbol': self.symbol_v1,
                        'marginCoin': self.margin_coin
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                
                if response is not None:
                    if isinstance(response, list):
                        logger.debug(f"✅ 포지션 조회 성공 ({endpoint}): {len(response)}개")
                        return response
                    elif isinstance(response, dict) and 'data' in response:
                        logger.debug(f"✅ 포지션 조회 성공 ({endpoint}): {len(response['data'])}개")
                        return response['data']
                    else:
                        logger.debug(f"✅ 포지션 조회 성공 ({endpoint}): 빈 결과")
                        return []
                        
            except Exception as e:
                logger.warning(f"포지션 엔드포인트 {endpoint} 실패: {e}")
                continue
        
        # 모든 엔드포인트 실패
        logger.error("모든 포지션 엔드포인트 실패")
        return []

    async def get_all_plan_orders_with_tp_sl(self) -> List[Dict]:
        """TP/SL 포함 예약 주문 조회"""
        # 여러 엔드포인트 순차 시도
        for i, endpoint in enumerate(self.plan_order_endpoints):
            try:
                logger.debug(f"예약 주문 조회 시도 {i + 1}/{len(self.plan_order_endpoints)}: {endpoint}")
                
                if endpoint == "/api/v2/mix/order/orders-plan-pending":
                    # V2 API
                    params = {
                        'productType': self.product_type,
                        'symbol': self.symbol
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                elif endpoint == "/api/mix/v1/plan/currentPlan":
                    # V1 API
                    params = {
                        'symbol': self.symbol_v1,
                        'productType': 'umcbl'
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                
                if response is not None:
                    if isinstance(response, list):
                        logger.debug(f"✅ 예약 주문 조회 성공 ({endpoint}): {len(response)}개")
                        return response
                    elif isinstance(response, dict) and 'data' in response:
                        logger.debug(f"✅ 예약 주문 조회 성공 ({endpoint}): {len(response['data'])}개")
                        return response['data']
                    else:
                        logger.debug(f"✅ 예약 주문 조회 성공 ({endpoint}): 빈 결과")
                        return []
                        
            except Exception as e:
                logger.warning(f"예약 주문 엔드포인트 {endpoint} 실패: {e}")
                continue
        
        # 모든 엔드포인트 실패
        logger.error("모든 예약 주문 엔드포인트 실패")
        return []

    async def get_recent_filled_orders(self, limit: int = 100) -> List[Dict]:
        """최근 체결 주문 조회"""
        # 여러 엔드포인트 순차 시도
        for i, endpoint in enumerate(self.order_history_endpoints):
            try:
                logger.debug(f"체결 주문 조회 시도 {i + 1}/{len(self.order_history_endpoints)}: {endpoint}")
                
                if endpoint == "/api/v2/mix/order/orders-history":
                    # V2 API
                    params = {
                        'productType': self.product_type,
                        'symbol': self.symbol,
                        'limit': str(limit)
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                elif endpoint == "/api/mix/v1/order/historyOrders":
                    # V1 API
                    params = {
                        'symbol': self.symbol_v1,
                        'pageSize': str(limit)
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                
                if response is not None:
                    if isinstance(response, list):
                        # 체결된 주문만 필터링
                        filled_orders = [order for order in response if order.get('state') == 'filled' or order.get('status') == 'filled']
                        logger.debug(f"✅ 체결 주문 조회 성공 ({endpoint}): {len(filled_orders)}개")
                        return filled_orders
                    elif isinstance(response, dict) and 'data' in response:
                        filled_orders = [order for order in response['data'] if order.get('state') == 'filled' or order.get('status') == 'filled']
                        logger.debug(f"✅ 체결 주문 조회 성공 ({endpoint}): {len(filled_orders)}개")
                        return filled_orders
                    else:
                        logger.debug(f"✅ 체결 주문 조회 성공 ({endpoint}): 빈 결과")
                        return []
                        
            except Exception as e:
                logger.warning(f"체결 주문 엔드포인트 {endpoint} 실패: {e}")
                continue
        
        # 모든 엔드포인트 실패
        logger.error("모든 체결 주문 엔드포인트 실패")
        return []

    async def close(self):
        """클라이언트 종료"""
        try:
            if self.session and not self.session.closed:
                await self.session.close()
                logger.info("Bitget 미러링 클라이언트 세션 종료")
        except Exception as e:
            logger.error(f"Bitget 미러링 클라이언트 종료 오류: {e}")

    def __del__(self):
        """소멸자"""
        try:
            if self.session and not self.session.closed:
                asyncio.create_task(self.session.close())
        except:
            pass
