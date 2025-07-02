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
        
        self.api_keys_validated = False
        
        # 체결된 주문 추적 강화
        self.recently_filled_orders = set()  # 최근 체결된 주문 ID 추적
        self.filled_orders_cache_time = 300  # 5분간 캐시
        self.last_filled_check = datetime.min
        
    def _initialize_session(self):
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,
                use_dns_cache=True
            )
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )
            logger.info("Bitget 미러링 클라이언트 세션 초기화 완료")
        
    async def initialize(self):
        self._initialize_session()
        await self._validate_api_keys()
        logger.info("Bitget 미러링 클라이언트 초기화 완료")
    
    async def _validate_api_keys(self):
        try:
            logger.info("비트겟 미러링 API 키 유효성 검증 시작...")
            
            endpoint = "/api/v2/mix/account/accounts"
            params = {
                'productType': 'USDT-FUTURES',
                'marginCoin': 'USDT'
            }
            
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
                
                async with self.session.request(method, url, headers=headers, data=body) as response:
                    response_text = await response.text()
                    
                    logger.debug(f"비트겟 미러링 API 응답 상태: {response.status}")
                    logger.debug(f"비트겟 미러링 API 응답 내용: {response_text[:500]}...")
                    
                    if not response_text.strip():
                        error_msg = f"빈 응답 받음 (상태: {response.status})"
                        logger.warning(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: {response_text}"
                        logger.error(f"비트겟 미러링 API HTTP 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError as json_error:
                        error_msg = f"JSON 파싱 실패: {json_error}, 응답: {response_text[:200]}"
                        logger.error(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    if response_data.get('code') != '00000':
                        error_msg = f"API 응답 오류: {response_data}"
                        logger.error(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    self._record_success()
                    return response_data.get('data', {})
                    
            except asyncio.TimeoutError:
                error_msg = f"요청 타임아웃 (시도 {attempt + 1})"
                logger.warning(error_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self._record_failure(error_msg)
                    raise Exception(error_msg)
                    
            except aiohttp.ClientError as client_error:
                error_msg = f"클라이언트 오류 (시도 {attempt + 1}): {client_error}"
                logger.warning(error_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self._record_failure(error_msg)
                    raise Exception(error_msg)
                    
            except Exception as e:
                error_msg = f"예상치 못한 오류 (시도 {attempt + 1}): {e}"
                logger.error(error_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self._record_failure(error_msg)
                    raise
        
        final_error = f"모든 재시도 실패: {max_retries}회 시도"
        self._record_failure(final_error)
        raise Exception(final_error)
    
    def _record_success(self):
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
    
    def _record_failure(self, error_msg: str):
        self.consecutive_failures += 1
        
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.api_connection_healthy = False
            logger.error(f"비트겟 미러링 API 연결 비정상 상태: 연속 {self.consecutive_failures}회 실패")
        
        logger.warning(f"비트겟 미러링 API 실패 기록: {error_msg} (연속 실패: {self.consecutive_failures}회)")
    
    async def get_ticker(self, symbol: str = None) -> Dict:
        symbol = symbol or self.config.symbol
        
        for i, endpoint in enumerate(self.ticker_endpoints):
            try:
                logger.debug(f"미러링 티커 조회 시도 {i + 1}/{len(self.ticker_endpoints)}: {endpoint}")
                
                if endpoint == "/api/v2/mix/market/ticker":
                    params = {
                        'symbol': symbol,
                        'productType': 'USDT-FUTURES'
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                    if isinstance(response, list) and len(response) > 0:
                        ticker_data = response[0]
                    elif isinstance(response, dict):
                        ticker_data = response
                    else:
                        logger.warning(f"미러링 V2 믹스: 예상치 못한 응답 형식: {type(response)}")
                        continue
                    
                elif endpoint == "/api/mix/v1/market/ticker":
                    v1_symbol = f"{symbol}_UMCBL"
                    params = {
                        'symbol': v1_symbol
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                    if isinstance(response, dict):
                        ticker_data = response
                    else:
                        logger.warning(f"미러링 V1 믹스: 예상치 못한 응답 형식: {type(response)}")
                        continue
                        
                elif endpoint == "/api/v2/spot/market/tickers":
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
                        logger.warning(f"미러링 V2 스팟: 예상치 못한 응답 형식: {type(response)}")
                        continue
                
                if ticker_data and self._validate_ticker_data(ticker_data):
                    normalized_ticker = self._normalize_ticker_data(ticker_data, endpoint)
                    logger.info(f"✅ 미러링 티커 조회 성공 ({endpoint}): ${normalized_ticker.get('last', 'N/A')}")
                    return normalized_ticker
                else:
                    logger.warning(f"미러링 티커 데이터 검증 실패: {endpoint}")
                    continue
                    
            except Exception as e:
                logger.warning(f"미러링 티커 엔드포인트 {endpoint} 실패: {e}")
                continue
        
        error_msg = f"미러링 모든 티커 엔드포인트 실패: {', '.join(self.ticker_endpoints)}"
        logger.error(error_msg)
        self._record_failure("모든 티커 엔드포인트 실패")
        return {}
    
    def _validate_ticker_data(self, ticker_data: Dict) -> bool:
        try:
            if not isinstance(ticker_data, dict):
                return False
            
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
            
            logger.warning(f"미러링 유효한 가격 필드 없음: {list(ticker_data.keys())}")
            return False
            
        except Exception as e:
            logger.error(f"미러링 티커 데이터 검증 오류: {e}")
            return False
    
    def _normalize_ticker_data(self, ticker_data: Dict, endpoint: str) -> Dict:
        try:
            normalized = {}
            
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
                                change_val = float(value)
                                if abs(change_val) > 1:
                                    change_val = change_val / 100
                                normalized[target_field] = change_val
                            else:
                                normalized[target_field] = float(value)
                            break
                        except:
                            continue
            
            if 'last' not in normalized:
                normalized['last'] = 0
            if 'changeUtc' not in normalized:
                normalized['changeUtc'] = 0
            if 'volume' not in normalized:
                normalized['volume'] = 0
            
            normalized['_original'] = ticker_data
            normalized['_endpoint'] = endpoint
            
            return normalized
            
        except Exception as e:
            logger.error(f"미러링 티커 데이터 정규화 실패: {e}")
            return ticker_data
    
    async def get_positions(self, symbol: str = None) -> List[Dict]:
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/position/all-position"
        params = {
            'productType': 'USDT-FUTURES',
            'marginCoin': 'USDT'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            logger.info(f"미러링 포지션 정보 원본 응답: {response}")
            positions = response if isinstance(response, list) else []
            
            if symbol and positions:
                positions = [pos for pos in positions if pos.get('symbol') == symbol]
            
            active_positions = []
            for pos in positions:
                total_size = float(pos.get('total', 0))
                if total_size > 0:
                    active_positions.append(pos)
                    logger.info(f"미러링 포지션 청산가 필드 확인:")
                    logger.info(f"  - liquidationPrice: {pos.get('liquidationPrice')}")
                    logger.info(f"  - markPrice: {pos.get('markPrice')}")
            
            return active_positions
        except Exception as e:
            logger.error(f"미러링 포지션 조회 실패: {e}")
            raise
    
    async def get_account_info(self) -> Dict:
        endpoint = "/api/v2/mix/account/accounts"
        params = {
            'productType': 'USDT-FUTURES',
            'marginCoin': 'USDT'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            logger.info(f"미러링 계정 정보 원본 응답: {response}")
            if isinstance(response, list) and len(response) > 0:
                return response[0]
            return response
        except Exception as e:
            logger.error(f"미러링 계정 정보 조회 실패: {e}")
            raise
    
    async def get_recent_filled_orders(self, symbol: str = None, minutes: int = 5) -> List[Dict]:
        try:
            symbol = symbol or self.config.symbol
            
            now = datetime.now()
            start_time = now - timedelta(minutes=minutes)
            start_timestamp = int(start_time.timestamp() * 1000)
            end_timestamp = int(now.timestamp() * 1000)
            
            filled_orders = await self.get_order_history(
                symbol=symbol,
                status='filled',
                start_time=start_timestamp,
                end_time=end_timestamp,
                limit=100
            )
            
            logger.info(f"미러링 최근 {minutes}분간 체결된 주문: {len(filled_orders)}건")
            
            new_position_orders = []
            for order in filled_orders:
                reduce_only = order.get('reduceOnly', 'false')
                if reduce_only == 'false' or reduce_only is False:
                    new_position_orders.append(order)
                    logger.info(f"미러링 신규 진입 주문 감지: {order.get('orderId')} - {order.get('side')} {order.get('size')}")
            
            return new_position_orders
            
        except Exception as e:
            logger.error(f"미러링 최근 체결 주문 조회 실패: {e}")
            return []
    
    async def get_order_history(self, symbol: str = None, status: str = 'filled', 
                              start_time: int = None, end_time: int = None, limit: int = 100) -> List[Dict]:
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/order/orders-history"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES',
            'pageSize': str(limit)
        }
        
        if status:
            params['status'] = status
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
            logger.error(f"미러링 주문 내역 조회 실패: {e}")
            return []
    
    async def get_filled_orders_by_ids(self, order_ids: List[str], symbol: str = None) -> List[Dict]:
        try:
            if not order_ids:
                return []
            
            symbol = symbol or self.config.symbol
            
            filled_orders = await self.get_recent_filled_orders(symbol=symbol, minutes=30)
            
            matched_orders = []
            for order in filled_orders:
                order_id = order.get('orderId', order.get('id', ''))
                if order_id in order_ids:
                    matched_orders.append(order)
                    logger.info(f"체결 확인: {order_id} - {order.get('side')} {order.get('size')}")
            
            logger.info(f"요청된 {len(order_ids)}개 주문 중 {len(matched_orders)}개 체결 확인")
            return matched_orders
            
        except Exception as e:
            logger.error(f"특정 주문 ID 체결 확인 실패: {e}")
            return []
    
    async def update_recently_filled_orders(self, symbol: str = None) -> Set[str]:
        try:
            now = datetime.now()
            
            # 5분마다 체결된 주문 업데이트
            if (now - self.last_filled_check).total_seconds() < 60:
                return self.recently_filled_orders
            
            recent_filled = await self.get_recent_filled_orders(symbol, minutes=10)
            
            # 캐시 업데이트
            new_filled_ids = set()
            for order in recent_filled:
                order_id = order.get('orderId', order.get('id', ''))
                if order_id:
                    new_filled_ids.add(order_id)
            
            # 이전 캐시와 병합 (최대 300초간 유지)
            cache_cutoff = now - timedelta(seconds=self.filled_orders_cache_time)
            
            # 최근 체결된 주문 ID 업데이트
            self.recently_filled_orders = new_filled_ids
            self.last_filled_check = now
            
            logger.debug(f"체결된 주문 캐시 업데이트: {len(self.recently_filled_orders)}개")
            return self.recently_filled_orders
            
        except Exception as e:
            logger.error(f"체결된 주문 업데이트 실패: {e}")
            return self.recently_filled_orders
    
    async def is_order_recently_filled(self, order_id: str, symbol: str = None) -> bool:
        try:
            await self.update_recently_filled_orders(symbol)
            return order_id in self.recently_filled_orders
        except Exception as e:
            logger.error(f"주문 체결 상태 확인 실패: {e}")
            return False
    
    async def get_plan_orders_v2_working(self, symbol: str = None) -> List[Dict]:
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"🔍 미러링 V2 API 예약 주문 조회 시작: {symbol}")
            
            all_found_orders = []
            
            working_endpoints = [
                "/api/v2/mix/order/orders-pending",
            ]
            
            for endpoint in working_endpoints:
                try:
                    params = {
                        'symbol': symbol,
                        'productType': 'USDT-FUTURES'
                    }
                    
                    logger.info(f"🔍 미러링 예약 주문 조회: {endpoint}")
                    response = await self._request('GET', endpoint, params=params)
                    
                    if response is None:
                        logger.debug(f"미러링 {endpoint}: 응답이 None")
                        continue
                    
                    orders = []
                    if isinstance(response, dict):
                        if 'entrustedList' in response:
                            orders_raw = response['entrustedList']
                            if isinstance(orders_raw, list):
                                orders = orders_raw
                                logger.info(f"✅ 미러링 {endpoint}: entrustedList에서 {len(orders)}개 주문 발견")
                    elif isinstance(response, list):
                        orders = response
                        logger.info(f"✅ 미러링 {endpoint}: 직접 리스트에서 {len(orders)}개 주문 발견")
                    
                    if orders:
                        all_found_orders.extend(orders)
                        logger.info(f"🎯 미러링 {endpoint}에서 발견: {len(orders)}개 주문")
                        
                        for i, order in enumerate(orders):
                            if order is None:
                                continue
                            
                            order_id = order.get('orderId', order.get('planOrderId', order.get('id', 'unknown')))
                            order_type = order.get('orderType', order.get('planType', order.get('type', 'unknown')))
                            side = order.get('side', order.get('tradeSide', 'unknown'))
                            trigger_price = order.get('triggerPrice', order.get('executePrice', order.get('price', 'unknown')))
                            size = order.get('size', order.get('volume', 'unknown'))
                            
                            tp_price = order.get('presetStopSurplusPrice', order.get('stopSurplusPrice', order.get('takeProfitPrice')))
                            sl_price = order.get('presetStopLossPrice', order.get('stopLossPrice'))
                            
                            logger.info(f"  📝 미러링 주문 {i+1}: ID={order_id}, 타입={order_type}, 방향={side}, 크기={size}, 트리거가={trigger_price}")
                            
                            if tp_price:
                                logger.info(f"      🎯 TP 설정 발견: {tp_price}")
                            if sl_price:
                                logger.info(f"      🛡️ SL 설정 발견: {sl_price}")
                            
                            tp_sl_fields = {}
                            for field_name, field_value in order.items():
                                if any(keyword in field_name.lower() for keyword in ['stop', 'profit', 'loss', 'tp', 'sl']):
                                    if field_value and str(field_value) not in ['0', '0.0', '', 'null']:
                                        tp_sl_fields[field_name] = field_value
                            
                            if tp_sl_fields:
                                logger.info(f"      🔍 TP/SL 관련 필드들: {tp_sl_fields}")
                        
                        break
                    else:
                        logger.debug(f"미러링 {endpoint}: 주문이 없음")
                        
                except Exception as e:
                    logger.debug(f"미러링 {endpoint} 조회 실패: {e}")
                    continue
            
            seen = set()
            unique_orders = []
            for order in all_found_orders:
                if order is None:
                    continue
                    
                order_id = (order.get('orderId') or 
                           order.get('planOrderId') or 
                           order.get('id') or
                           str(order.get('cTime', '')))
                
                if order_id and order_id not in seen:
                    seen.add(order_id)
                    unique_orders.append(order)
                    logger.debug(f"📝 미러링 V2 고유 예약 주문 추가: {order_id}")
            
            logger.info(f"🔥 미러링 V2 API에서 최종 발견된 고유한 예약 주문: {len(unique_orders)}건")
            return unique_orders
            
        except Exception as e:
            logger.error(f"미러링 V2 예약 주문 조회 실패: {e}")
            return []
    
    async def get_plan_orders_v1_working(self, symbol: str = None, plan_type: str = None) -> List[Dict]:
        try:
            symbol = symbol or self.config.symbol
            v1_symbol = f"{symbol}_UMCBL"
            
            logger.info(f"🔍 미러링 V1 API 예약 주문 조회 시작: {v1_symbol}")
            
            all_found_orders = []
            
            working_endpoints = [
                "/api/mix/v1/plan/currentPlan",
            ]
            
            for endpoint in working_endpoints:
                try:
                    params = {
                        'symbol': v1_symbol,
                        'productType': 'umcbl'
                    }
                    
                    if plan_type:
                        if plan_type == 'profit_loss':
                            params['isPlan'] = 'profit_loss'
                        else:
                            params['planType'] = plan_type
                    
                    logger.info(f"🔍 미러링 V1 예약 주문 조회: {endpoint}")
                    response = await self._request('GET', endpoint, params=params)
                    
                    if response is None:
                        logger.debug(f"미러링 {endpoint}: 응답이 None")
                        continue
                    
                    orders = []
                    if isinstance(response, dict):
                        for field_name in ['list', 'data']:
                            if field_name in response:
                                orders_raw = response[field_name]
                                if isinstance(orders_raw, list):
                                    orders = orders_raw
                                    logger.info(f"✅ 미러링 {endpoint}: {field_name}에서 {len(orders)}개 주문 발견")
                                    break
                    elif isinstance(response, list):
                        orders = response
                        logger.info(f"✅ 미러링 {endpoint}: 직접 리스트에서 {len(orders)}개 주문 발견")
                    
                    if orders:
                        all_found_orders.extend(orders)
                        logger.info(f"🎯 미러링 {endpoint}에서 발견: {len(orders)}개 주문")
                        
                        for i, order in enumerate(orders):
                            if order is None:
                                continue
                            
                            order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
                            order_type = order.get('orderType', order.get('planType', 'unknown'))
                            side = order.get('side', order.get('tradeSide', 'unknown'))
                            trigger_price = order.get('triggerPrice', order.get('executePrice', 'unknown'))
                            size = order.get('size', order.get('volume', 'unknown'))
                            
                            tp_price = order.get('presetStopSurplusPrice', order.get('stopSurplusPrice', order.get('takeProfitPrice')))
                            sl_price = order.get('presetStopLossPrice', order.get('stopLossPrice'))
                            
                            logger.info(f"  📝 미러링 V1 주문 {i+1}: ID={order_id}, 타입={order_type}, 방향={side}, 크기={size}, 트리거가={trigger_price}")
                            
                            if tp_price:
                                logger.info(f"      🎯 V1 TP 설정 발견: {tp_price}")
                            if sl_price:
                                logger.info(f"      🛡️ V1 SL 설정 발견: {sl_price}")
                        
                        break
                    else:
                        logger.debug(f"미러링 {endpoint}: 주문이 없음")
                        
                except Exception as e:
                    logger.debug(f"미러링 {endpoint} 조회 실패: {e}")
                    continue
            
            seen = set()
            unique_orders = []
            for order in all_found_orders:
                if order is None:
                    continue
                    
                order_id = (order.get('orderId') or 
                           order.get('planOrderId') or 
                           order.get('id') or
                           str(order.get('cTime', '')))
                
                if order_id and order_id not in seen:
                    seen.add(order_id)
                    unique_orders.append(order)
                    logger.debug(f"📝 미러링 V1 고유 예약 주문 추가: {order_id}")
            
            logger.info(f"🔥 미러링 V1 API에서 최종 발견된 고유한 예약 주문: {len(unique_orders)}건")
            return unique_orders
            
        except Exception as e:
            logger.error(f"미러링 V1 예약 주문 조회 실패: {e}")
            return []
    
    async def get_all_trigger_orders(self, symbol: str = None) -> List[Dict]:
        all_orders = []
        symbol = symbol or self.config.symbol
        
        logger.info(f"🔍 미러링 모든 트리거 주문 조회 시작: {symbol}")
        
        try:
            v2_orders = await self.get_plan_orders_v2_working(symbol)
            if v2_orders:
                all_orders.extend(v2_orders)
                logger.info(f"✅ 미러링 V2에서 {len(v2_orders)}개 예약 주문 발견")
        except Exception as e:
            logger.warning(f"미러링 V2 예약 주문 조회 실패: {e}")
        
        try:
            v1_orders = await self.get_plan_orders_v1_working(symbol)
            if v1_orders:
                all_orders.extend(v1_orders)
                logger.info(f"✅ 미러링 V1 일반에서 {len(v1_orders)}개 예약 주문 발견")
        except Exception as e:
            logger.warning(f"미러링 V1 일반 예약 주문 조회 실패: {e}")
        
        try:
            v1_tp_sl = await self.get_plan_orders_v1_working(symbol, 'profit_loss')
            if v1_tp_sl:
                all_orders.extend(v1_tp_sl)
                logger.info(f"✅ 미러링 V1 TP/SL에서 {len(v1_tp_sl)}개 주문 발견")
        except Exception as e:
            logger.warning(f"미러링 V1 TP/SL 주문 조회 실패: {e}")
        
        seen = set()
        unique_orders = []
        for order in all_orders:
            if order is None:
                continue
                
            order_id = (order.get('orderId') or 
                       order.get('planOrderId') or 
                       order.get('id') or
                       str(order.get('cTime', '')))
            
            if order_id and order_id not in seen:
                seen.add(order_id)
                unique_orders.append(order)
                logger.debug(f"📝 미러링 최종 고유 예약 주문 추가: {order_id}")
        
        logger.info(f"🔥 미러링 최종 발견된 고유한 트리거 주문: {len(unique_orders)}건")
        
        if unique_orders:
            logger.info("📋 미러링 발견된 예약 주문 목록:")
            for i, order in enumerate(unique_orders, 1):
                order_id = order.get('orderId', order.get('planOrderId', order.get('id', 'unknown')))
                side = order.get('side', order.get('tradeSide', 'unknown'))
                trigger_price = order.get('triggerPrice', order.get('executePrice', order.get('price', 'unknown')))
                size = order.get('size', order.get('volume', 'unknown'))
                order_type = order.get('orderType', order.get('planType', order.get('type', 'unknown')))
                
                tp_price = order.get('presetStopSurplusPrice', order.get('stopSurplusPrice', order.get('takeProfitPrice')))
                sl_price = order.get('presetStopLossPrice', order.get('stopLossPrice'))
                
                logger.info(f"  {i}. ID: {order_id}, 방향: {side}, 수량: {size}, 트리거가: {trigger_price}, 타입: {order_type}")
                if tp_price:
                    logger.info(f"     🎯 TP: {tp_price}")
                if sl_price:
                    logger.info(f"     🛡️ SL: {sl_price}")
        else:
            logger.debug("📝 미러링 현재 예약 주문이 없습니다.")
        
        return unique_orders
    
    async def get_plan_orders(self, symbol: str = None, plan_type: str = None) -> List[Dict]:
        try:
            all_orders = await self.get_all_trigger_orders(symbol)
            
            if plan_type == 'profit_loss':
                filtered = [o for o in all_orders if o and (o.get('planType') == 'profit_loss' or o.get('isPlan') == 'profit_loss')]
                return filtered
            elif plan_type:
                filtered = [o for o in all_orders if o and o.get('planType') == plan_type]
                return filtered
            
            return all_orders
            
        except Exception as e:
            logger.error(f"미러링 플랜 주문 조회 실패, 빈 리스트 반환: {e}")
            return []
    
    async def get_all_plan_orders_with_tp_sl(self, symbol: str = None) -> Dict:
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"🔍 미러링 모든 예약 주문 및 TP/SL 조회 시작: {symbol}")
            
            all_orders = await self.get_all_trigger_orders(symbol)
            
            tp_sl_orders = []
            plan_orders = []
            
            for order in all_orders:
                if order is None:
                    continue
                    
                is_tp_sl = False
                
                if (order.get('planType') == 'profit_loss' or 
                    order.get('isPlan') == 'profit_loss' or
                    order.get('side') in ['close_long', 'close_short'] or
                    order.get('tradeSide') in ['close_long', 'close_short'] or
                    order.get('reduceOnly') == True or
                    order.get('reduceOnly') == 'true'):
                    is_tp_sl = True
                
                tp_price = self._extract_tp_price(order)
                sl_price = self._extract_sl_price(order)
                
                if tp_price or sl_price:
                    logger.info(f"🎯 미러링 TP/SL 설정이 있는 예약 주문 발견: {order.get('orderId', order.get('planOrderId'))}")
                    if tp_price:
                        tp_price_str = f"{tp_price:.2f}" if tp_price else "0"
                        logger.info(f"   TP: {tp_price_str}")
                    if sl_price:
                        sl_price_str = f"{sl_price:.2f}" if sl_price else "0"
                        logger.info(f"   SL: {sl_price_str}")
                
                if is_tp_sl:
                    tp_sl_orders.append(order)
                    logger.info(f"📊 미러링 TP/SL 주문 분류: {order.get('orderId', order.get('planOrderId'))} - {order.get('side', order.get('tradeSide'))}")
                else:
                    plan_orders.append(order)
                    logger.info(f"📈 미러링 일반 예약 주문 분류: {order.get('orderId', order.get('planOrderId'))} - {order.get('side', order.get('tradeSide'))}")
            
            result = {
                'plan_orders': plan_orders,
                'tp_sl_orders': tp_sl_orders,
                'total_count': len(all_orders)
            }
            
            logger.info(f"🔥 미러링 전체 예약 주문 분류 완료: 일반 {len(plan_orders)}건 + TP/SL {len(tp_sl_orders)}건 = 총 {result['total_count']}건")
            
            if plan_orders:
                logger.info("📈 미러링 일반 예약 주문 목록:")
                for i, order in enumerate(plan_orders, 1):
                    order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
                    side = order.get('side', order.get('tradeSide', 'unknown'))
                    price = order.get('price', order.get('triggerPrice', 'unknown'))
                    
                    tp_price = self._extract_tp_price(order)
                    sl_price = self._extract_sl_price(order)
                    
                    logger.info(f"  {i}. ID: {order_id}, 방향: {side}, 가격: {price}")
                    if tp_price:
                        tp_price_str = f"{tp_price:.2f}" if tp_price else "0"
                        logger.info(f"     🎯 TP 설정: {tp_price_str}")
                    if sl_price:
                        sl_price_str = f"{sl_price:.2f}" if sl_price else "0"
                        logger.info(f"     🛡️ SL 설정: {sl_price_str}")
            
            if tp_sl_orders:
                logger.info("📊 미러링 TP/SL 주문 목록:")
                for i, order in enumerate(tp_sl_orders, 1):
                    order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
                    side = order.get('side', order.get('tradeSide', 'unknown'))
                    trigger_price = order.get('triggerPrice', 'unknown')
                    logger.info(f"  {i}. ID: {order_id}, 방향: {side}, 트리거가: {trigger_price}")
            
            return result
            
        except Exception as e:
            logger.error(f"미러링 전체 플랜 주문 조회 실패: {e}")
            return {
                'plan_orders': [],
                'tp_sl_orders': [],
                'total_count': 0,
                'error': str(e)
            }
    
    def _extract_tp_price(self, order: Dict) -> Optional[float]:
        try:
            tp_fields = [
                'presetStopSurplusPrice',
                'stopSurplusPrice',
                'takeProfitPrice',
                'tpPrice',
                'stopProfit',
                'profitPrice'
            ]
            
            for field in tp_fields:
                value = order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        tp_price = float(value)
                        if tp_price > 0:
                            logger.debug(f"미러링 TP 가격 추출 성공: {field} = {tp_price}")
                            return tp_price
                    except:
                        continue
            
            return None
            
        except Exception as e:
            logger.debug(f"미러링 TP 가격 추출 오류: {e}")
            return None
    
    def _extract_sl_price(self, order: Dict) -> Optional[float]:
        try:
            sl_fields = [
                'presetStopLossPrice',
                'stopLossPrice',
                'stopPrice',
                'slPrice',
                'lossPrice'
            ]
            
            for field in sl_fields:
                value = order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        sl_price = float(value)
                        if sl_price > 0:
                            logger.debug(f"미러링 SL 가격 추출 성공: {field} = {sl_price}")
                            return sl_price
                    except:
                        continue
            
            return None
            
        except Exception as e:
            logger.debug(f"미러링 SL 가격 추출 오류: {e}")
            return None
    
    async def get_api_connection_status(self) -> Dict:
        return {
            'healthy': self.api_connection_healthy,
            'consecutive_failures': self.consecutive_failures,
            'last_successful_call': self.last_successful_call.isoformat(),
            'api_keys_validated': self.api_keys_validated,
            'max_failures_threshold': self.max_consecutive_failures
        }
    
    async def reset_connection_status(self):
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
        logger.info("비트겟 미러링 API 연결 상태 리셋 완료")
    
    async def close(self):
        if self.session:
            await self.session.close()
            logger.info("Bitget 미러링 클라이언트 세션 종료")
