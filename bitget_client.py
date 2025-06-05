import asyncio
import hmac
import hashlib
import base64
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import aiohttp
import pytz
import traceback

logger = logging.getLogger(__name__)

class BitgetClient:
    def __init__(self, config):
        self.config = config
        self.session = None
        self._initialize_session()
        
        # 🔥🔥🔥 API 연결 상태 추적
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
        self.max_consecutive_failures = 10
        
        # 🔥🔥🔥 백업 엔드포인트들
        self.ticker_endpoints = [
            "/api/v2/mix/market/ticker",  # 기본 V2
            "/api/mix/v1/market/ticker",  # V1 백업
            "/api/v2/spot/market/tickers", # Spot 백업 (변환 필요)
        ]
        
        # API 키 검증 상태
        self.api_keys_validated = False
        
    def _initialize_session(self):
        """세션 초기화"""
        if not self.session:
            # 🔥🔥🔥 연결 타임아웃 및 재시도 설정 강화
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
            logger.info("Bitget 클라이언트 세션 초기화 완료")
        
    async def initialize(self):
        """클라이언트 초기화"""
        self._initialize_session()
        
        # 🔥🔥🔥 API 키 유효성 검증
        await self._validate_api_keys()
        
        logger.info("Bitget 클라이언트 초기화 완료")
    
    async def _validate_api_keys(self):
        """🔥🔥🔥 API 키 유효성 검증"""
        try:
            logger.info("비트겟 API 키 유효성 검증 시작...")
            
            # 간단한 계정 정보 조회로 API 키 검증
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
                logger.info("✅ 비트겟 API 키 검증 성공")
            else:
                logger.error("❌ 비트겟 API 키 검증 실패: 응답 없음")
                self.api_keys_validated = False
                
        except Exception as e:
            logger.error(f"❌ 비트겟 API 키 검증 실패: {e}")
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
        """🔥🔥🔥 API 요청 - 강화된 오류 처리"""
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
        
        # 🔥🔥🔥 재시도 로직
        for attempt in range(max_retries):
            try:
                logger.debug(f"비트겟 API 요청 (시도 {attempt + 1}/{max_retries}): {method} {endpoint}")
                
                async with self.session.request(method, url, headers=headers, data=body) as response:
                    response_text = await response.text()
                    
                    # 🔥🔥🔥 상세한 응답 로깅
                    logger.debug(f"비트겟 API 응답 상태: {response.status}")
                    logger.debug(f"비트겟 API 응답 헤더: {dict(response.headers)}")
                    logger.debug(f"비트겟 API 응답 내용: {response_text[:500]}...")
                    
                    # 빈 응답 체크
                    if not response_text.strip():
                        error_msg = f"빈 응답 받음 (상태: {response.status})"
                        logger.warning(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # 지수 백오프
                            continue
                        else:
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    # HTTP 상태 코드 체크
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: {response_text}"
                        logger.error(f"비트겟 API HTTP 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            self._record_failure(error_msg)
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
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    # API 응답 코드 체크
                    if response_data.get('code') != '00000':
                        error_msg = f"API 응답 오류: {response_data}"
                        logger.error(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    # 🔥🔥🔥 성공 기록
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
        
        # 모든 재시도 실패
        final_error = f"모든 재시도 실패: {max_retries}회 시도"
        self._record_failure(final_error)
        raise Exception(final_error)
    
    def _record_success(self):
        """🔥🔥🔥 성공 기록"""
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
    
    def _record_failure(self, error_msg: str):
        """🔥🔥🔥 실패 기록"""
        self.consecutive_failures += 1
        
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.api_connection_healthy = False
            logger.error(f"비트겟 API 연결 비정상 상태: 연속 {self.consecutive_failures}회 실패")
        
        logger.warning(f"비트겟 API 실패 기록: {error_msg} (연속 실패: {self.consecutive_failures}회)")
    
    async def get_ticker(self, symbol: str = None) -> Dict:
        """🔥🔥🔥 현재가 정보 조회 - 다중 엔드포인트 지원"""
        symbol = symbol or self.config.symbol
        
        # 🔥🔥🔥 여러 엔드포인트 순차 시도
        for i, endpoint in enumerate(self.ticker_endpoints):
            try:
                logger.debug(f"티커 조회 시도 {i + 1}/{len(self.ticker_endpoints)}: {endpoint}")
                
                if endpoint == "/api/v2/mix/market/ticker":
                    # V2 믹스 마켓 (기본)
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
                        logger.warning(f"V2 믹스: 예상치 못한 응답 형식: {type(response)}")
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
                        logger.warning(f"V1 믹스: 예상치 못한 응답 형식: {type(response)}")
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
                        logger.warning(f"V2 스팟: 예상치 못한 응답 형식: {type(response)}")
                        continue
                
                # 🔥🔥🔥 응답 데이터 검증 및 정규화
                if ticker_data and self._validate_ticker_data(ticker_data):
                    normalized_ticker = self._normalize_ticker_data(ticker_data, endpoint)
                    logger.info(f"✅ 티커 조회 성공 ({endpoint}): ${normalized_ticker.get('last', 'N/A')}")
                    return normalized_ticker
                else:
                    logger.warning(f"티커 데이터 검증 실패: {endpoint}")
                    continue
                    
            except Exception as e:
                logger.warning(f"티커 엔드포인트 {endpoint} 실패: {e}")
                continue
        
        # 🔥🔥🔥 모든 엔드포인트 실패
        error_msg = f"모든 티커 엔드포인트 실패: {', '.join(self.ticker_endpoints)}"
        logger.error(error_msg)
        self._record_failure("모든 티커 엔드포인트 실패")
        return {}
    
    def _validate_ticker_data(self, ticker_data: Dict) -> bool:
        """🔥🔥🔥 티커 데이터 유효성 검증"""
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
        """🔥🔥🔥 티커 데이터 정규화"""
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
                                # 변화율을 소수로 변환 (예: 2.5% -> 0.025)
                                change_val = float(value)
                                if abs(change_val) > 1:  # 백분율 형태인 경우
                                    change_val = change_val / 100
                                normalized[target_field] = change_val
                            else:
                                normalized[target_field] = float(value)
                            break
                        except:
                            continue
            
            # 기본값 설정
            if 'last' not in normalized:
                normalized['last'] = 0
            if 'changeUtc' not in normalized:
                normalized['changeUtc'] = 0
            if 'volume' not in normalized:
                normalized['volume'] = 0
            
            # 원본 데이터도 포함
            normalized['_original'] = ticker_data
            normalized['_endpoint'] = endpoint
            
            return normalized
            
        except Exception as e:
            logger.error(f"티커 데이터 정규화 실패: {e}")
            return ticker_data
    
    async def get_positions(self, symbol: str = None) -> List[Dict]:
        """포지션 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/position/all-position"
        params = {
            'productType': 'USDT-FUTURES',
            'marginCoin': 'USDT'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            logger.info(f"포지션 정보 원본 응답: {response}")
            positions = response if isinstance(response, list) else []
            
            if symbol and positions:
                positions = [pos for pos in positions if pos.get('symbol') == symbol]
            
            active_positions = []
            for pos in positions:
                total_size = float(pos.get('total', 0))
                if total_size > 0:
                    active_positions.append(pos)
                    # 청산가 필드 로깅
                    logger.info(f"포지션 청산가 필드 확인:")
                    logger.info(f"  - liquidationPrice: {pos.get('liquidationPrice')}")
                    logger.info(f"  - markPrice: {pos.get('markPrice')}")
            
            return active_positions
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            raise
    
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
    
    async def get_orders(self, symbol: str = None, status: str = None, limit: int = 100) -> List[Dict]:
        """주문 조회 (V2 API) - 예약 주문 포함"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/order/orders-pending"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES'
        }
        
        if status:
            params['status'] = status
        if limit:
            params['limit'] = str(limit)
        
        try:
            response = await self._request('GET', endpoint, params=params)
            logger.debug(f"주문 조회 응답: {response}")
            
            orders = response if isinstance(response, list) else []
            return orders
            
        except Exception as e:
            logger.error(f"주문 조회 실패: {e}")
            return []
    
    async def get_order_history(self, symbol: str = None, status: str = 'filled', 
                              start_time: int = None, end_time: int = None, limit: int = 100) -> List[Dict]:
        """주문 내역 조회 (V2 API)"""
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
            
            # 응답이 dict이고 orderList가 있는 경우
            if isinstance(response, dict) and 'orderList' in response:
                return response['orderList']
            # 응답이 리스트인 경우
            elif isinstance(response, list):
                return response
            
            return []
            
        except Exception as e:
            logger.error(f"주문 내역 조회 실패: {e}")
            return []
    
    async def get_recent_filled_orders(self, symbol: str = None, minutes: int = 5) -> List[Dict]:
        """최근 체결된 주문 조회 (미러링용)"""
        try:
            symbol = symbol or self.config.symbol
            
            # 현재 시간에서 N분 전까지
            now = datetime.now()
            start_time = now - timedelta(minutes=minutes)
            start_timestamp = int(start_time.timestamp() * 1000)
            end_timestamp = int(now.timestamp() * 1000)
            
            # 최근 체결된 주문 조회
            filled_orders = await self.get_order_history(
                symbol=symbol,
                status='filled',
                start_time=start_timestamp,
                end_time=end_timestamp,
                limit=50
            )
            
            logger.info(f"최근 {minutes}분간 체결된 주문: {len(filled_orders)}건")
            
            # 신규 진입 주문만 필터링 (reduce_only가 아닌 것)
            new_position_orders = []
            for order in filled_orders:
                reduce_only = order.get('reduceOnly', 'false')
                if reduce_only == 'false' or reduce_only is False:
                    new_position_orders.append(order)
                    logger.info(f"신규 진입 주문 감지: {order.get('orderId')} - {order.get('side')} {order.get('size')}")
            
            return new_position_orders
            
        except Exception as e:
            logger.error(f"최근 체결 주문 조회 실패: {e}")
            return []
    
    async def get_plan_orders(self, symbol: str = None, status: str = 'live') -> List[Dict]:
        """🔥🔥🔥 예약 주문 조회 - 통합된 방식"""
        symbol = symbol or self.config.symbol
        
        try:
            # V2 API로 예약 주문 조회
            endpoint = "/api/v2/mix/order/plan-orders-pending"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'
            }
            
            if status:
                params['status'] = status
            
            response = await self._request('GET', endpoint, params=params)
            logger.debug(f"예약 주문 조회 응답: {response}")
            
            # 응답 형태에 따라 처리
            if isinstance(response, dict):
                if 'orderList' in response:
                    return response['orderList']
                elif 'data' in response and isinstance(response['data'], list):
                    return response['data']
                elif isinstance(response.get('data'), dict) and 'orderList' in response['data']:
                    return response['data']['orderList']
            elif isinstance(response, list):
                return response
            
            logger.warning(f"예약 주문 응답 형식 예상치 못함: {type(response)}")
            return []
            
        except Exception as e:
            logger.error(f"예약 주문 조회 실패: {e}")
            return []
    
    async def get_tp_sl_orders(self, symbol: str = None, status: str = 'live') -> List[Dict]:
        """🔥🔥🔥 TP/SL 주문 조회 - 통합된 방식"""
        symbol = symbol or self.config.symbol
        
        try:
            # V2 API로 TP/SL 주문 조회
            endpoint = "/api/v2/mix/order/stop-orders-pending"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'
            }
            
            if status:
                params['status'] = status
            
            response = await self._request('GET', endpoint, params=params)
            logger.debug(f"TP/SL 주문 조회 응답: {response}")
            
            # 응답 형태에 따라 처리
            if isinstance(response, dict):
                if 'orderList' in response:
                    return response['orderList']
                elif 'data' in response and isinstance(response['data'], list):
                    return response['data']
                elif isinstance(response.get('data'), dict) and 'orderList' in response['data']:
                    return response['data']['orderList']
            elif isinstance(response, list):
                return response
            
            logger.warning(f"TP/SL 주문 응답 형식 예상치 못함: {type(response)}")
            return []
            
        except Exception as e:
            logger.error(f"TP/SL 주문 조회 실패: {e}")
            return []
    
    async def get_all_plan_orders_with_tp_sl(self, symbol: str = None) -> Dict:
        """🔥🔥🔥 예약 주문과 TP/SL 주문을 함께 조회 - 수정된 f-string"""
        symbol = symbol or self.config.symbol
        
        try:
            logger.info(f"🔍 전체 플랜 주문 조회 시작: {symbol}")
            
            # 예약 주문과 TP/SL 주문을 병렬로 조회
            plan_orders_task = self.get_plan_orders(symbol, 'live')
            tp_sl_orders_task = self.get_tp_sl_orders(symbol, 'live')
            
            plan_orders, tp_sl_orders = await asyncio.gather(
                plan_orders_task, 
                tp_sl_orders_task, 
                return_exceptions=True
            )
            
            # 예외 처리
            if isinstance(plan_orders, Exception):
                logger.error(f"예약 주문 조회 오류: {plan_orders}")
                plan_orders = []
            
            if isinstance(tp_sl_orders, Exception):
                logger.error(f"TP/SL 주문 조회 오류: {tp_sl_orders}")
                tp_sl_orders = []
            
            # 결과 로깅 - 수정된 f-string
            plan_count = len(plan_orders) if plan_orders else 0
            tp_sl_count = len(tp_sl_orders) if tp_sl_orders else 0
            total_count = plan_count + tp_sl_count
            
            logger.info(f"📊 전체 플랜 주문 조회 결과:")
            logger.info(f"   - 예약 주문: {plan_count}개")
            logger.info(f"   - TP/SL 주문: {tp_sl_count}개")
            logger.info(f"   - 총합: {total_count}개")
            
            # 각 주문의 TP/SL 정보 분석
            for i, order in enumerate(plan_orders[:3]):  # 최대 3개만 로깅
                order_id = order.get('orderId', order.get('planOrderId', f'unknown_{i}'))
                side = order.get('side', order.get('tradeSide', 'unknown'))
                trigger_price = order.get('triggerPrice', order.get('price', 0))
                
                # TP/SL 가격 확인 - 수정된 f-string
                tp_price = None
                sl_price = None
                
                # TP 추출
                for tp_field in ['presetStopSurplusPrice', 'stopSurplusPrice', 'takeProfitPrice']:
                    value = order.get(tp_field)
                    if value and str(value) not in ['0', '0.0', '', 'null']:
                        try:
                            tp_price = float(value)
                            if tp_price > 0:
                                break
                        except:
                            continue
                
                # SL 추출
                for sl_field in ['presetStopLossPrice', 'stopLossPrice', 'stopPrice']:
                    value = order.get(sl_field)
                    if value and str(value) not in ['0', '0.0', '', 'null']:
                        try:
                            sl_price = float(value)
                            if sl_price > 0:
                                break
                        except:
                            continue
                
                # 로깅 - 수정된 f-string (조건문을 밖으로 분리)
                tp_display = f"${tp_price:.2f}" if tp_price else "없음"
                sl_display = f"${sl_price:.2f}" if sl_price else "없음"
                
                logger.info(f"🎯 예약주문 {i+1}: ID={order_id}")
                logger.info(f"   방향: {side}, 트리거: ${trigger_price}")
                logger.info(f"   TP: {tp_display}")
                logger.info(f"   SL: {sl_display}")
            
            # TP/SL 주문도 분석
            for i, order in enumerate(tp_sl_orders[:3]):  # 최대 3개만 로깅
                order_id = order.get('orderId', order.get('planOrderId', f'tpsl_{i}'))
                side = order.get('side', order.get('tradeSide', 'unknown'))
                trigger_price = order.get('triggerPrice', order.get('price', 0))
                reduce_only = order.get('reduceOnly', False)
                
                logger.info(f"🛡️ TP/SL주문 {i+1}: ID={order_id}")
                logger.info(f"   방향: {side}, 트리거: ${trigger_price}")
                logger.info(f"   클로즈: {reduce_only}")
            
            return {
                'plan_orders': plan_orders or [],
                'tp_sl_orders': tp_sl_orders or [],
                'total_count': total_count,
                'plan_count': plan_count,
                'tp_sl_count': tp_sl_count
            }
            
        except Exception as e:
            logger.error(f"전체 플랜 주문 조회 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return {
                'plan_orders': [],
                'tp_sl_orders': [],
                'total_count': 0,
                'plan_count': 0,
                'tp_sl_count': 0,
                'error': str(e)
            }
    
    async def get_enhanced_profit_history(self, symbol: str = None, days: int = 7) -> Dict:
        """🔥🔥 개선된 정확한 손익 조회 - 다중 검증 방식"""
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"=== 🔥 개선된 {days}일 손익 조회 시작 ===")
            
            # KST 기준 시간 설정
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 정확한 기간 설정 (오늘 0시부터 역산)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_start = today_start - timedelta(days=days-1)
            period_end = now
            
            logger.info(f"📅 조회 기간: {period_start.strftime('%Y-%m-%d %H:%M')} ~ {period_end.strftime('%Y-%m-%d %H:%M')} (KST)")
            
            # UTC 변환
            start_time_utc = period_start.astimezone(pytz.UTC)
            end_time_utc = period_end.astimezone(pytz.UTC)
            start_timestamp = int(start_time_utc.timestamp() * 1000)
            end_timestamp = int(end_time_utc.timestamp() * 1000)
            
            # 🔥 방법 1: Account Bills 기반 조회 (수정된 방식)
            bills_result = await self._get_profit_from_account_bills_corrected(start_timestamp, end_timestamp, period_start, days)
            
            # 🔥 방법 2: 거래 내역 기반 조회 (강화된 방식)
            fills_result = await self._get_profit_from_fills_enhanced(symbol, start_timestamp, end_timestamp, period_start, days)
            
            # 🔥 방법 3: achievedProfits 기반 (포지션 수익)
            achieved_result = await self._get_achieved_profits()
            
            # 🔥 결과 비교 및 최적 값 선택
            final_result = self._select_best_profit_data_corrected(bills_result, fills_result, achieved_result, days)
            
            logger.info(f"🎯 최종 선택된 결과:")
            logger.info(f"   - 총 손익: ${final_result['total_pnl']:.2f}")
            logger.info(f"   - 거래 건수: {final_result['trade_count']}건")
            logger.info(f"   - 데이터 소스: {final_result.get('source', 'unknown')}")
            logger.info(f"   - 신뢰도: {final_result.get('confidence', 'unknown')}")
            
            return final_result
            
        except Exception as e:
            logger.error(f"개선된 손익 조회 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'days': days,
                'average_daily': 0,
                'trade_count': 0,
                'total_fees': 0,
                'source': 'error',
                'confidence': 'low',
                'error': str(e)
            }
    
    async def _get_profit_from_account_bills_corrected(self, start_timestamp: int, end_timestamp: int, 
                                                     period_start: datetime, days: int) -> Dict:
        """🔥🔥🔥 Account Bills에서 손익 추출 - 수정된 방식"""
        try:
            logger.info("🔥 Account Bills 기반 손익 조회 시작 (수정된 방식)")
            
            kst = pytz.timezone('Asia/Seoul')
            
            # 모든 손익 관련 Bills 조회 (수정된 방식)
            all_bills = []
            
            # 🔥🔥🔥 수정된 Account Bills 조회 사용
            # contract_settle (실현 손익)
            settle_bills = await self._get_all_bills_with_paging_corrected(
                start_timestamp, end_timestamp, 'contract_settle'
            )
            all_bills.extend(settle_bills)
            logger.info(f"실현 손익 Bills: {len(settle_bills)}건")
            
            # fee (수수료)
            fee_bills = await self._get_all_bills_with_paging_corrected(
                start_timestamp, end_timestamp, 'contract_fee'
            )
            all_bills.extend(fee_bills)
            logger.info(f"수수료 Bills: {len(fee_bills)}건")
            
            # funding (펀딩비)
            funding_bills = await self._get_all_bills_with_paging_corrected(
                start_timestamp, end_timestamp, 'contract_funding_fee'
            )
            all_bills.extend(funding_bills)
            logger.info(f"펀딩비 Bills: {len(funding_bills)}건")
            
            # 날짜별 분석
            daily_data = {}
            total_pnl = 0
            total_fees = 0
            trade_count = 0
            
            for bill in all_bills:
                try:
                    bill_time = int(bill.get('cTime', 0))
                    if not bill_time:
                        continue
                    
                    bill_date_kst = datetime.fromtimestamp(bill_time / 1000, tz=kst)
                    bill_date_str = bill_date_kst.strftime('%Y-%m-%d')
                    
                    # 기간 내 체크
                    if bill_date_kst < period_start:
                        continue
                    
                    amount = float(bill.get('amount', 0))
                    business_type = bill.get('businessType', '')
                    
                    if bill_date_str not in daily_data:
                        daily_data[bill_date_str] = {
                            'pnl': 0, 'fees': 0, 'funding': 0, 'trades': 0
                        }
                    
                    # 🔥🔥🔥 수정된 businessType에 맞춰 조정
                    if business_type in ['contract_settle', 'settle', 'realized', 'pnl', 'profit']:
                        daily_data[bill_date_str]['pnl'] += amount
                        daily_data[bill_date_str]['trades'] += 1
                        total_pnl += amount
                        trade_count += 1
                    elif business_type in ['contract_fee', 'fee', 'trading_fee', 'trade_fee']:
                        daily_data[bill_date_str]['fees'] += abs(amount)
                        total_fees += abs(amount)
                    elif business_type in ['contract_funding_fee', 'funding', 'funding_fee', 'fund']:
                        daily_data[bill_date_str]['funding'] += amount
                        # 펀딩비는 손익에 포함
                        total_pnl += amount
                    
                except Exception as e:
                    logger.warning(f"Bills 항목 파싱 오류: {e}")
                    continue
            
            # 일별 순손익 계산
            daily_pnl = {}
            for date_str, data in daily_data.items():
                net_pnl = data['pnl'] + data['funding']  # 실현손익 + 펀딩비
                daily_pnl[date_str] = net_pnl
                logger.info(f"📊 {date_str}: PnL ${data['pnl']:.2f} + Funding ${data['funding']:.2f} = ${net_pnl:.2f} ({data['trades']}건)")
            
            # 🔥🔥🔥 Account Bills가 성공했는지 확인
            confidence = 'high' if len(all_bills) > 0 else 'low'
            source = 'account_bills_corrected' if len(all_bills) > 0 else 'account_bills_empty'
            
            return {
                'total_pnl': total_pnl,
                'daily_pnl': daily_pnl,
                'days': days,
                'average_daily': total_pnl / days if days > 0 else 0,
                'trade_count': trade_count,
                'total_fees': total_fees,
                'source': source,
                'confidence': confidence
            }
            
        except Exception as e:
            logger.error(f"Account Bills 손익 조회 실패: {e}")
            return {
                'total_pnl': 0, 'daily_pnl': {}, 'days': days,
                'average_daily': 0, 'trade_count': 0, 'total_fees': 0,
                'source': 'account_bills_error', 'confidence': 'low'
            }
    
    async def _get_all_bills_with_paging_corrected(self, start_timestamp: int, end_timestamp: int, 
                                                 business_type: str) -> List[Dict]:
        """🔥🔥🔥 수정된 방식으로 모든 Bills 조회"""
        all_bills = []
        next_id = None
        page = 0
        
        while page < 20:  # 최대 20페이지
            bills = await self.get_account_bills_v2_corrected(
                start_time=start_timestamp,
                end_time=end_timestamp,
                business_type=business_type,
                limit=100,
                next_id=next_id
            )
            
            if not bills:
                logger.info(f"{business_type} Bills 페이지 {page + 1}: 데이터 없음, 종료")
                break
            
            all_bills.extend(bills)
            logger.info(f"{business_type} Bills 페이지 {page + 1}: {len(bills)}건 조회 (누적 {len(all_bills)}건)")
            
            if len(bills) < 100:
                logger.info(f"{business_type} Bills: 마지막 페이지 도달 ({len(bills)}건 < 100건)")
                break
            
            # 다음 페이지 ID
            last_bill = bills[-1]
            next_id = last_bill.get('billId', last_bill.get('id'))
            if not next_id:
                logger.info(f"{business_type} Bills: 다음 페이지 ID 없음, 종료")
                break
            
            page += 1
            await asyncio.sleep(0.1)
        
        logger.info(f"{business_type} Bills 총 {len(all_bills)}건 조회")
        return all_bills
    
    async def get_account_bills_v2_corrected(self, start_time: int = None, end_time: int = None, 
                                           business_type: str = None, limit: int = 100,
                                           next_id: str = None) -> List[Dict]:
        """🔥🔥🔥 V2 Account Bills 수정된 방식 - businessType 파라미터 조정"""
        
        # 🔥🔥🔥 businessType error가 발생한 엔드포인트를 다른 방식으로 시도
        working_endpoint = "/api/v2/mix/account/bill"
        
        # 🔥🔥🔥 businessType 파라미터를 다양한 방식으로 시도
        business_type_variants = []
        
        if business_type == 'contract_settle':
            business_type_variants = ['settle', 'realized', 'pnl', 'profit', 'trade_settle']
        elif business_type == 'contract_fee':
            business_type_variants = ['fee', 'trading_fee', 'trade_fee']
        elif business_type == 'contract_funding_fee':
            business_type_variants = ['funding', 'funding_fee', 'fund']
        else:
            business_type_variants = [None]  # businessType 없이 시도
        
        for variant in business_type_variants:
            try:
                params = {
                    'productType': 'USDT-FUTURES',
                    'marginCoin': 'USDT'
                }
                
                if start_time:
                    params['startTime'] = str(start_time)
                if end_time:
                    params['endTime'] = str(end_time)
                if variant:  # businessType이 있는 경우만 추가
                    params['businessType'] = variant
                if limit:
                    params['limit'] = str(min(limit, 100))
                if next_id:
                    params['startId'] = str(next_id)
                
                logger.info(f"🔍 Account Bills V2 businessType 시도: '{variant}'")
                response = await self._request('GET', working_endpoint, params=params)
                
                if response is not None:
                    logger.info(f"✅ businessType '{variant}' 성공!")
                    
                    if isinstance(response, list):
                        logger.info(f"📊 businessType '{variant}'에서 {len(response)}건 조회 성공")
                        return response
                    elif isinstance(response, dict):
                        # 다양한 필드명 시도
                        for field in ['billsList', 'bills', 'list', 'data']:
                            if field in response and isinstance(response[field], list):
                                bills = response[field]
                                logger.info(f"📊 businessType '{variant}'에서 {len(bills)}건 조회 성공 ({field} 필드)")
                                return bills
                        
                        # dict이지만 리스트 필드가 없는 경우
                        logger.warning(f"⚠️ businessType '{variant}': dict 응답이지만 알려진 리스트 필드 없음: {list(response.keys())}")
                        continue
                    else:
                        logger.warning(f"⚠️ businessType '{variant}': 알 수 없는 응답 타입: {type(response)}")
                        continue
                        
            except Exception as e:
                error_msg = str(e)
                if "Parameter businessType error" in error_msg:
                    logger.debug(f"❌ businessType '{variant}' 파라미터 오류, 다음 시도")
                    continue
                elif "404" in error_msg or "NOT FOUND" in error_msg:
                    logger.debug(f"❌ businessType '{variant}' 404 오류")
                    break  # 404면 다른 variant도 같은 결과일 것
                else:
                    logger.warning(f"❌ businessType '{variant}' 기타 오류: {e}")
                    continue
        
        # 🔥🔥🔥 모든 businessType variant가 실패한 경우, V1 API 시도
        logger.info("🔄 V2 실패, V1 Account Bills 시도")
        return await self.get_account_bills_v1_fallback(start_time, end_time, business_type, limit, next_id)
    
    async def get_account_bills_v1_fallback(self, start_time: int = None, end_time: int = None, 
                                          business_type: str = None, limit: int = 100,
                                          next_id: str = None) -> List[Dict]:
        """🔥🔥🔥 V1 Account Bills 폴백 (V2가 모두 실패할 때)"""
        try:
            # V1 API 엔드포인트들
            v1_endpoints = [
                "/api/mix/v1/account/accountBill",
                "/api/mix/v1/account/bill", 
                "/api/mix/v1/account/bills"
            ]
            
            for endpoint in v1_endpoints:
                try:
                    # V1은 다른 파라미터 형식 사용
                    params = {
                        'symbol': f"{self.config.symbol}_UMCBL",
                        'productType': 'umcbl'
                    }
                    
                    if start_time:
                        params['startTime'] = str(start_time)
                    if end_time:
                        params['endTime'] = str(end_time)
                    if business_type:
                        # V1에서는 다른 businessType 이름 사용 가능
                        if business_type == 'contract_settle':
                            params['businessType'] = 'settle'
                        elif business_type == 'contract_fee':
                            params['businessType'] = 'fee'
                        elif business_type == 'contract_funding_fee':
                            params['businessType'] = 'funding'
                        else:
                            params['businessType'] = business_type
                    if limit:
                        params['pageSize'] = str(min(limit, 100))
                    if next_id:
                        params['lastEndId'] = str(next_id)
                    
                    logger.info(f"🔍 V1 Account Bills 시도: {endpoint}")
                    response = await self._request('GET', endpoint, params=params)
                    
                    if response is not None:
                        logger.info(f"✅ V1 {endpoint} 성공!")
                        
                        if isinstance(response, list):
                            logger.info(f"📊 V1에서 {len(response)}건 조회 성공")
                            return response
                        elif isinstance(response, dict):
                            # V1 응답 구조
                            for field in ['billsList', 'bills', 'list', 'data']:
                                if field in response and isinstance(response[field], list):
                                    bills = response[field]
                                    logger.info(f"📊 V1에서 {len(bills)}건 조회 성공 ({field} 필드)")
                                    return bills
                        
                        logger.debug(f"V1 {endpoint}: 빈 응답 또는 알 수 없는 구조")
                        continue
                    
                except Exception as e:
                    logger.debug(f"V1 {endpoint} 실패: {e}")
                    continue
            
            logger.warning("⚠️ 모든 V1 Account Bills 엔드포인트도 실패")
            return []
            
        except Exception as e:
            logger.error(f"V1 Account Bills 폴백 실패: {e}")
            return []
    
    async def _get_profit_from_fills_enhanced(self, symbol: str, start_timestamp: int, end_timestamp: int,
                                            period_start: datetime, days: int) -> Dict:
        """🔥🔥🔥 거래 내역(Fills)에서 손익 추출 - 강화된 버전"""
        try:
            logger.info("🔥 거래 내역(Fills) 기반 손익 조회 시작 (강화된 버전)")
            
            kst = pytz.timezone('Asia/Seoul')
            
            # 모든 거래 내역 조회 (강화된 방식)
            all_fills = await self._get_enhanced_fills_v2(symbol, start_timestamp, end_timestamp)
            
            logger.info(f"조회된 총 거래 수: {len(all_fills)}건")
            
            # 중복 제거 (강화된 로직)
            unique_fills = self._remove_duplicate_fills_enhanced(all_fills)
            logger.info(f"중복 제거 후: {len(unique_fills)}건")
            
            # 날짜별 분석
            daily_pnl = {}
            total_pnl = 0
            total_fees = 0
            trade_count = 0
            
            for fill in unique_fills:
                try:
                    # 시간 추출 (더 많은 필드 시도)
                    fill_time = None
                    for time_field in ['cTime', 'createTime', 'createdTime', 'updateTime', 'time', 'timestamp']:
                        if time_field in fill and fill[time_field]:
                            fill_time = int(fill[time_field])
                            break
                    
                    if not fill_time:
                        continue
                    
                    fill_date_kst = datetime.fromtimestamp(fill_time / 1000, tz=kst)
                    fill_date_str = fill_date_kst.strftime('%Y-%m-%d')
                    
                    # 기간 내 체크
                    if fill_date_kst < period_start:
                        continue
                    
                    # 손익 추출 (더 많은 필드 시도)
                    profit = 0.0
                    for profit_field in ['profit', 'realizedPL', 'realizedPnl', 'pnl', 'realizedProfit']:
                        if profit_field in fill and fill[profit_field] is not None:
                            try:
                                profit = float(fill[profit_field])
                                if profit != 0:
                                    break
                            except:
                                continue
                    
                    # 수수료 추출 (강화)
                    fee = self._extract_fee_from_fill_enhanced(fill)
                    
                    # 순손익 계산
                    net_pnl = profit - fee
                    
                    if fill_date_str not in daily_pnl:
                        daily_pnl[fill_date_str] = 0
                    
                    daily_pnl[fill_date_str] += net_pnl
                    total_pnl += net_pnl
                    total_fees += fee
                    trade_count += 1
                    
                    if profit != 0 or fee != 0:
                        logger.debug(f"거래: {fill_date_str} - Profit: ${profit:.2f}, Fee: ${fee:.2f}, Net: ${net_pnl:.2f}")
                    
                except Exception as e:
                    logger.warning(f"Fill 항목 파싱 오류: {e}")
                    continue
            
            # 일별 로깅
            for date_str, pnl in sorted(daily_pnl.items()):
                logger.info(f"📊 {date_str}: ${pnl:.2f}")
            
            return {
                'total_pnl': total_pnl,
                'daily_pnl': daily_pnl,
                'days': days,
                'average_daily': total_pnl / days if days > 0 else 0,
                'trade_count': trade_count,
                'total_fees': total_fees,
                'source': 'trade_fills_enhanced',
                'confidence': 'high' if trade_count > 0 else 'medium'  # 거래가 있으면 high
            }
            
        except Exception as e:
            logger.error(f"거래 내역 손익 조회 실패: {e}")
            return {
                'total_pnl': 0, 'daily_pnl': {}, 'days': days,
                'average_daily': 0, 'trade_count': 0, 'total_fees': 0,
                'source': 'fills_error', 'confidence': 'low'
            }
    
    async def _get_enhanced_fills_v2(self, symbol: str, start_timestamp: int, end_timestamp: int) -> List[Dict]:
        """🔥🔥🔥 향상된 거래 내역 조회 V2"""
        all_fills = []
        
        # 더 세밀하게 나눠서 조회 (3일씩)
        current_start = start_timestamp
        
        while current_start < end_timestamp:
            current_end = min(current_start + (3 * 24 * 60 * 60 * 1000), end_timestamp)
            
            # 해당 기간 조회
            period_fills = await self._get_period_fills_v2(symbol, current_start, current_end)
            all_fills.extend(period_fills)
            
            current_start = current_end
            await asyncio.sleep(0.1)  # 더 짧은 대기
        
        return all_fills
    
    async def _get_period_fills_v2(self, symbol: str, start_time: int, end_time: int) -> List[Dict]:
        """🔥🔥🔥 특정 기간의 거래 내역 조회 V2"""
        all_fills = []
        
        # 더 많은 엔드포인트 시도
        endpoints = [
            "/api/v2/mix/order/fill-history",
            "/api/v2/mix/order/fills",
            "/api/v2/mix/order/trade-history",  # 추가
            "/api/v2/mix/trade/fills"           # 추가
        ]
        
        for endpoint in endpoints:
            try:
                fills = await self._get_fills_from_endpoint_v2(endpoint, symbol, start_time, end_time)
                if fills:
                    all_fills.extend(fills)
                    logger.info(f"{endpoint}: {len(fills)}건 조회")
                    break  # 성공하면 다른 엔드포인트는 시도하지 않음
            except Exception as e:
                logger.debug(f"{endpoint} 실패: {e}")
                continue
        
        return all_fills
    
    async def _get_fills_from_endpoint_v2(self, endpoint: str, symbol: str, 
                                        start_time: int, end_time: int) -> List[Dict]:
        """🔥🔥🔥 특정 엔드포인트에서 거래 내역 조회 V2"""
        all_fills = []
        last_id = None
        page = 0
        
        while page < 15:  # 더 많은 페이지 허용
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES',
                'startTime': str(start_time),
                'endTime': str(end_time),
                'limit': '500'
            }
            
            if last_id:
                # 다양한 페이징 파라미터 시도
                for page_param in ['lastEndId', 'idLessThan', 'fromId', 'startId']:
                    params_copy = params.copy()
                    params_copy[page_param] = str(last_id)
                    
                    try:
                        response = await self._request('GET', endpoint, params=params_copy)
                        break
                    except:
                        continue
                else:
                    # 모든 페이징 파라미터 실패
                    break
            else:
                response = await self._request('GET', endpoint, params=params)
            
            fills = []
            if isinstance(response, dict):
                # 더 많은 응답 필드 시도
                for field in ['fillList', 'list', 'data', 'fills', 'trades', 'records']:
                    if field in response and isinstance(response[field], list):
                        fills = response[field]
                        break
            elif isinstance(response, list):
                fills = response
            
            if not fills:
                break
            
            all_fills.extend(fills)
            
            if len(fills) < 500:
                break
            
            # 다음 페이지 ID
            last_fill = fills[-1]
            last_id = last_fill.get('tradeId', last_fill.get('id', last_fill.get('fillId')))
            if not last_id:
                break
            
            page += 1
            await asyncio.sleep(0.1)
        
        return all_fills
    
    def _remove_duplicate_fills_enhanced(self, fills: List[Dict]) -> List[Dict]:
        """🔥🔥🔥 강화된 중복 제거"""
        seen_ids = set()
        unique_fills = []
        
        for fill in fills:
            # 다양한 ID 필드 확인
            fill_id = None
            for id_field in ['tradeId', 'id', 'fillId', 'orderId']:
                if id_field in fill and fill[id_field]:
                    fill_id = str(fill[id_field])
                    break
            
            if fill_id and fill_id not in seen_ids:
                seen_ids.add(fill_id)
                unique_fills.append(fill)
        
        return unique_fills
    
    def _extract_fee_from_fill_enhanced(self, fill: Dict) -> float:
        """🔥🔥🔥 강화된 수수료 추출"""
        fee = 0.0
        
        # 다양한 수수료 필드 시도
        for fee_field in ['fee', 'fees', 'feeDetail', 'commission', 'tradeFee']:
            if fee_field in fill and fill[fee_field] is not None:
                try:
                    fee_value = fill[fee_field]
                    if isinstance(fee_value, dict):
                        # feeDetail 구조인 경우
                        fee = abs(float(fee_value.get('totalFee', fee_value.get('fee', 0))))
                    else:
                        fee = abs(float(fee_value))
                    
                    if fee > 0:
                        break
                except:
                    continue
        
        return fee
    
    async def _get_achieved_profits(self) -> Dict:
        """🔥🔥🔥 achievedProfits 기반 수익 조회"""
        try:
            # 여러 엔드포인트 시도
            endpoints = [
                "/api/v2/mix/account/achieved-profits",
                "/api/mix/v1/account/achievedProfits"
            ]
            
            for endpoint in endpoints:
                try:
                    if 'v2' in endpoint:
                        params = {
                            'productType': 'USDT-FUTURES',
                            'marginCoin': 'USDT'
                        }
                    else:
                        params = {
                            'symbol': f"{self.config.symbol}_UMCBL",
                            'productType': 'umcbl'
                        }
                    
                    response = await self._request('GET', endpoint, params=params)
                    
                    if response:
                        # 응답 처리
                        profits = []
                        if isinstance(response, list):
                            profits = response
                        elif isinstance(response, dict):
                            for field in ['list', 'data', 'profits']:
                                if field in response and isinstance(response[field], list):
                                    profits = response[field]
                                    break
                        
                        if profits:
                            total_profit = sum(float(p.get('achievedPnl', p.get('profit', 0))) for p in profits)
                            return {
                                'total_pnl': total_profit,
                                'trade_count': len(profits),
                                'source': 'achieved_profits',
                                'confidence': 'medium'
                            }
                
                except Exception as e:
                    logger.debug(f"{endpoint} 실패: {e}")
                    continue
            
            return {
                'total_pnl': 0,
                'trade_count': 0,
                'source': 'achieved_profits_failed',
                'confidence': 'low'
            }
            
        except Exception as e:
            logger.error(f"achievedProfits 조회 실패: {e}")
            return {
                'total_pnl': 0,
                'trade_count': 0,
                'source': 'achieved_profits_error',
                'confidence': 'low'
            }
    
    def _select_best_profit_data_corrected(self, bills_result: Dict, fills_result: Dict, 
                                         achieved_result: Dict, days: int) -> Dict:
        """🔥🔥🔥 최적의 손익 데이터 선택 - 수정된 방식"""
        try:
            # 신뢰도 점수 계산
            def calculate_confidence_score(result):
                confidence_map = {'high': 3, 'medium': 2, 'low': 1}
                base_score = confidence_map.get(result.get('confidence', 'low'), 1)
                
                # 거래 건수가 있으면 점수 증가
                if result.get('trade_count', 0) > 0:
                    base_score += 1
                
                # 데이터 소스별 가중치
                if 'bills' in result.get('source', ''):
                    base_score += 2  # Bills가 가장 신뢰할만함
                elif 'fills' in result.get('source', ''):
                    base_score += 1
                
                return base_score
            
            # 각 결과의 점수 계산
            bills_score = calculate_confidence_score(bills_result)
            fills_score = calculate_confidence_score(fills_result)
            achieved_score = calculate_confidence_score(achieved_result)
            
            logger.info(f"신뢰도 점수: Bills={bills_score}, Fills={fills_score}, Achieved={achieved_score}")
            
            # 가장 높은 점수의 결과 선택
            if bills_score >= fills_score and bills_score >= achieved_score:
                best_result = bills_result
                logger.info("✅ Account Bills 결과 선택")
            elif fills_score >= achieved_score:
                best_result = fills_result
                logger.info("✅ Trade Fills 결과 선택")
            else:
                best_result = achieved_result
                logger.info("✅ Achieved Profits 결과 선택")
            
            # 기본값 보장
            final_result = {
                'total_pnl': best_result.get('total_pnl', 0),
                'daily_pnl': best_result.get('daily_pnl', {}),
                'days': days,
                'average_daily': best_result.get('total_pnl', 0) / days if days > 0 else 0,
                'trade_count': best_result.get('trade_count', 0),
                'total_fees': best_result.get('total_fees', 0),
                'source': best_result.get('source', 'unknown'),
                'confidence': best_result.get('confidence', 'low')
            }
            
            return final_result
            
        except Exception as e:
            logger.error(f"최적 데이터 선택 실패: {e}")
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'days': days,
                'average_daily': 0,
                'trade_count': 0,
                'total_fees': 0,
                'source': 'selection_error',
                'confidence': 'low'
            }
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
