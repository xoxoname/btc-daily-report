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
    """Bitget 미러링 전용 클라이언트 - 정확한 API 파라미터 사용 + USDT-M Futures 지원"""
    
    def __init__(self, config):
        self.config = config
        self.session = None
        self._initialize_session()
        
        # API 연결 상태 추적
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
        self.max_consecutive_failures = 10
        
        # 🔥🔥🔥 정확한 Bitget 파라미터 설정 - 수정됨
        self.product_type = "umcbl"      # USDT-M Futures (소문자)
        self.symbol = "BTCUSDT"          # 정확한 심볼
        self.margin_coin = "USDT"        # 마진 코인
        
        # 🔥🔥🔥 정확한 v2 API 엔드포인트들
        self.ticker_endpoints = [
            "/api/v2/mix/market/ticker",   # v2 API 메인
        ]
        
        # 🔥🔥🔥 정확한 예약 주문 조회 엔드포인트들
        self.plan_order_endpoints = [
            "/api/v2/mix/order/orders-plan-pending",  # v2 정확한 엔드포인트
        ]
        
        # 🔥🔥🔥 정확한 예약 주문 체결 내역 엔드포인트들
        self.plan_history_endpoints = [
            "/api/v2/mix/order/orders-plan-history",  # v2 정확한 엔드포인트
        ]
        
        # 🔥🔥🔥 체결 내역 엔드포인트
        self.fill_history_endpoints = [
            "/api/v2/mix/order/fills-history",        # v2 정확한 엔드포인트
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
            
            # 정확한 파라미터로 계정 정보 조회
            endpoint = "/api/v2/mix/account/accounts"
            params = {
                'productType': self.product_type,
                'marginCoin': self.margin_coin
            }
            
            logger.info(f"API 키 검증 요청: {endpoint}, 파라미터: {params}")
            
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
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None, max_retries: int = 3) -> Dict:
        """API 요청 - 강화된 오류 처리 + 파라미터 검증 로깅"""
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
        """계정 정보 조회 - 정확한 파라미터 사용"""
        try:
            endpoint = "/api/v2/mix/account/accounts"
            params = {
                'productType': self.product_type,
                'marginCoin': self.margin_coin
            }
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list) and len(response) > 0:
                return response[0]
            elif isinstance(response, dict):
                return response
            
            return {}
                
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            raise
    
    async def get_positions(self, symbol: str = "BTCUSDT") -> List[Dict]:
        """포지션 조회 - 정확한 파라미터 사용"""
        try:
            endpoint = "/api/v2/mix/position/all-position"
            params = {
                'productType': self.product_type,
                'marginCoin': self.margin_coin
            }
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list):
                filtered_positions = []
                for pos in response:
                    if pos.get('symbol') == symbol and float(pos.get('total', 0)) > 0:
                        filtered_positions.append(pos)
                return filtered_positions
            
            return []
            
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []
    
    async def get_ticker(self, symbol: str = "BTCUSDT") -> Dict:
        """🔥🔥🔥 티커 정보 조회 - 정확한 파라미터 사용"""
        try:
            endpoint = "/api/v2/mix/market/ticker"
            params = {
                'symbol': symbol,
                'productType': self.product_type
            }
            
            logger.debug(f"비트겟 티커 조회: {endpoint}, 심볼: {symbol}, productType: {self.product_type}")
            
            response = await self._request('GET', endpoint, params=params, max_retries=2)
            
            # 응답 처리
            ticker_data = None
            if isinstance(response, list) and len(response) > 0:
                ticker_data = response[0]
            elif isinstance(response, dict):
                ticker_data = response
            else:
                logger.warning(f"티커 엔드포인트 빈 응답: {endpoint}")
                return {}
            
            # 데이터 정규화 및 검증
            if ticker_data and isinstance(ticker_data, dict):
                # last 가격 확인 및 정규화
                last_price = None
                for price_field in ['last', 'close', 'price', 'lastPr']:
                    if ticker_data.get(price_field):
                        try:
                            last_price = float(ticker_data[price_field])
                            if last_price > 0:
                                ticker_data['last'] = last_price
                                break
                        except (ValueError, TypeError):
                            continue
                
                if last_price and last_price > 0:
                    logger.debug(f"✅ 티커 조회 성공: {endpoint}, 가격: ${last_price:,.2f}")
                    return ticker_data
                else:
                    logger.warning(f"티커 데이터에 유효한 가격 없음: {ticker_data}")
                    return {}
            else:
                logger.warning(f"티커 데이터 형식 오류: {type(ticker_data)}")
                return {}
                
        except Exception as e:
            logger.error(f"티커 조회 실패 - 심볼: {symbol}, 오류: {e}")
            return {}
    
    async def get_all_plan_orders_with_tp_sl(self, symbol: str = "BTCUSDT") -> Dict:
        """🔥🔥🔥 모든 예약 주문 (Plan Orders + TP/SL Orders) 조회 - 정확한 파라미터 사용"""
        try:
            logger.info(f"🎯 비트겟 모든 예약 주문 조회 시작: {symbol}")
            
            plan_orders = []
            tp_sl_orders = []
            
            # 🔥🔥🔥 정확한 파라미터로 v2 API 사용
            try:
                # v2 일반 예약 주문
                endpoint = "/api/v2/mix/order/orders-plan-pending"
                params = {
                    'symbol': symbol,
                    'productType': self.product_type
                }
                
                response = await self._request('GET', endpoint, params=params)
                
                if isinstance(response, list):
                    all_orders = response
                elif isinstance(response, dict):
                    # v2 API는 여러 형태의 응답 구조를 가질 수 있음
                    all_orders = response.get('orderList', response.get('entrustedList', []))
                else:
                    all_orders = []
                
                # 주문 타입별로 분류
                for order in all_orders:
                    plan_type = order.get('planType', '').lower()
                    order_type = order.get('orderType', '').lower()
                    
                    # TP/SL 주문인지 확인
                    if any(tp_sl_keyword in plan_type for tp_sl_keyword in ['profit_loss', 'tp_sl', 'stop']) or \
                       any(tp_sl_keyword in order_type for tp_sl_keyword in ['stop', 'take_profit']):
                        tp_sl_orders.append(order)
                    else:
                        plan_orders.append(order)
                
                logger.info(f"✅ v2 API 예약 주문 조회 성공: 일반 {len(plan_orders)}개, TP/SL {len(tp_sl_orders)}개")
                
            except Exception as api_error:
                logger.error(f"v2 API 예약 주문 조회 실패: {api_error}")
                
                # 빈 결과 반환
                plan_orders = []
                tp_sl_orders = []
            
            # 결과 정리
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
        """🔥🔥🔥 최근 체결된 주문 조회 - 정확한 파라미터 사용"""
        try:
            # 시간 범위 계산 (UTC)
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=minutes)
            
            filled_orders = []
            
            # 정확한 v2 API 엔드포인트
            endpoint = "/api/v2/mix/order/fills-history"
            params = {
                'symbol': symbol,
                'productType': self.product_type,
                'startTime': str(int(start_time.timestamp() * 1000)),
                'endTime': str(int(end_time.timestamp() * 1000)),
                'limit': '100'
            }
            
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list):
                filled_orders = response
            elif isinstance(response, dict):
                filled_orders = response.get('fillList', response.get('data', []))
            
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
        """🔥🔥🔥 최근 체결된 예약 주문 조회 - 정확한 파라미터 사용"""
        try:
            logger.info(f"🎯 최근 체결된 예약 주문 조회: {symbol}, {minutes}분간")
            
            # 시간 범위 계산
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=minutes)
            
            filled_plan_orders = []
            
            # 정확한 v2 API 엔드포인트
            endpoint = "/api/v2/mix/order/orders-plan-history"
            params = {
                'symbol': symbol,
                'productType': self.product_type,
                'startTime': str(int(start_time.timestamp() * 1000)),
                'endTime': str(int(end_time.timestamp() * 1000)),
                'limit': '100'
            }
            
            if order_id:
                params['planOrderId'] = order_id
            
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list):
                filled_plan_orders = response
            elif isinstance(response, dict):
                filled_plan_orders = response.get('orderList', response.get('entrustedList', response.get('data', [])))
            
            # 특정 주문 ID 검색
            if order_id:
                matching_orders = []
                for order in filled_plan_orders:
                    order_check_id = order.get('orderId', order.get('planOrderId', order.get('id', '')))
                    if order_check_id == order_id:
                        matching_orders.append(order)
                
                if matching_orders:
                    logger.info(f"🎯 특정 주문 ID {order_id} 체결 내역 발견: {len(matching_orders)}개")
                    return matching_orders
                else:
                    logger.info(f"📝 특정 주문 ID {order_id} 체결 내역 없음")
                    return []
            
            # 중복 제거
            unique_filled_orders = {}
            for order in filled_plan_orders:
                order_check_id = order.get('orderId', order.get('planOrderId', order.get('id', '')))
                if order_check_id and order_check_id not in unique_filled_orders:
                    unique_filled_orders[order_check_id] = order
            
            result = list(unique_filled_orders.values())
            
            if result:
                logger.info(f"✅ 최근 {minutes}분간 체결된 예약 주문: {len(result)}개")
            else:
                logger.debug(f"최근 {minutes}분간 체결된 예약 주문 없음")
            
            return result
            
        except Exception as e:
            logger.error(f"최근 체결 예약 주문 조회 실패: {e}")
            return []
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("비트겟 미러링 클라이언트 세션 종료")
