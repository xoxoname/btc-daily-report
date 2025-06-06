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
    """Bitget 미러링 전용 클라이언트 - 클로징 주문 감지 강화 + API 개선 + 정확한 레버리지 추출"""
    
    def __init__(self, config):
        self.config = config
        self.session = None
        self._initialize_session()
        
        # 🔥🔥🔥 API 연결 상태 추적
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
        self.max_consecutive_failures = 10
        
        # 🔥🔥🔥 백업 엔드포인트들 - 타임아웃 개선
        self.ticker_endpoints = [
            "/api/v2/mix/market/ticker",  # 기본 V2
            "/api/mix/v1/market/ticker",  # V1 백업
            "/api/v2/spot/market/tickers", # Spot 백업 (변환 필요)
        ]
        
        # API 키 검증 상태
        self.api_keys_validated = False
        
    def _initialize_session(self):
        """세션 초기화 - 타임아웃 개선"""
        if not self.session:
            # 🔥🔥🔥 연결 타임아웃 및 재시도 설정 강화
            timeout = aiohttp.ClientTimeout(total=60, connect=30)  # 타임아웃 증가
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=60,  # 연결 유지 시간 증가
                enable_cleanup_closed=True
            )
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )
            logger.info("Bitget 미러링 클라이언트 세션 초기화 완료 (개선된 타임아웃)")
        
    async def initialize(self):
        """클라이언트 초기화"""
        self._initialize_session()
        
        # 🔥🔥🔥 API 키 유효성 검증
        await self._validate_api_keys()
        
        logger.info("Bitget 미러링 클라이언트 초기화 완료")
    
    async def _validate_api_keys(self):
        """🔥🔥🔥 API 키 유효성 검증"""
        try:
            logger.info("비트겟 미러링 API 키 유효성 검증 시작...")
            
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
        """🔥🔥🔥 API 요청 - 강화된 오류 처리 + 타임아웃 개선"""
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
        
        # 🔥🔥🔥 재시도 로직 - 타임아웃 개선
        for attempt in range(max_retries):
            try:
                logger.debug(f"비트겟 미러링 API 요청 (시도 {attempt + 1}/{max_retries}): {method} {endpoint}")
                
                # 🔥🔥🔥 각 시도마다 타임아웃 점진적 증가
                attempt_timeout = aiohttp.ClientTimeout(
                    total=30 + (attempt * 15),  # 30초에서 시작해서 점진적 증가
                    connect=10 + (attempt * 5)
                )
                
                async with self.session.request(
                    method, url, headers=headers, data=body, timeout=attempt_timeout
                ) as response:
                    response_text = await response.text()
                    
                    # 🔥🔥🔥 상세한 응답 로깅
                    logger.debug(f"비트겟 미러링 API 응답 상태: {response.status}")
                    logger.debug(f"비트겟 미러링 API 응답 헤더: {dict(response.headers)}")
                    logger.debug(f"비트겟 미러링 API 응답 내용: {response_text[:500]}...")
                    
                    # 빈 응답 체크
                    if not response_text.strip():
                        error_msg = f"빈 응답 받음 (상태: {response.status})"
                        logger.warning(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(3 + (attempt * 2))  # 더 긴 대기
                            continue
                        else:
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    # HTTP 상태 코드 체크
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: {response_text}"
                        logger.error(f"비트겟 미러링 API HTTP 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(3 + (attempt * 2))
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
                            await asyncio.sleep(3 + (attempt * 2))
                            continue
                        else:
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    # API 응답 코드 체크
                    if response_data.get('code') != '00000':
                        error_msg = f"API 응답 오류: {response_data}"
                        logger.error(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(3 + (attempt * 2))
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
                    await asyncio.sleep(5 + (attempt * 3))  # 타임아웃 시 더 긴 대기
                    continue
                else:
                    self._record_failure(error_msg)
                    raise Exception(error_msg)
                    
            except aiohttp.ClientError as client_error:
                error_msg = f"클라이언트 오류 (시도 {attempt + 1}): {client_error}"
                logger.warning(error_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(3 + (attempt * 2))
                    continue
                else:
                    self._record_failure(error_msg)
                    raise Exception(error_msg)
                    
            except Exception as e:
                error_msg = f"예상치 못한 오류 (시도 {attempt + 1}): {e}"
                logger.error(error_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(3 + (attempt * 2))
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
            logger.error(f"비트겟 미러링 API 연결 비정상 상태: 연속 {self.consecutive_failures}회 실패")
        
        logger.warning(f"비트겟 미러링 API 실패 기록: {error_msg} (연속 실패: {self.consecutive_failures}회)")
    
    async def get_ticker(self, symbol: str = None) -> Dict:
        """🔥🔥🔥 현재가 정보 조회 - 다중 엔드포인트 지원 + 타임아웃 개선"""
        symbol = symbol or self.config.symbol
        
        # 🔥🔥🔥 여러 엔드포인트 순차 시도
        for i, endpoint in enumerate(self.ticker_endpoints):
            try:
                logger.debug(f"미러링 티커 조회 시도 {i + 1}/{len(self.ticker_endpoints)}: {endpoint}")
                
                if endpoint == "/api/v2/mix/market/ticker":
                    # V2 믹스 마켓 (기본)
                    params = {
                        'symbol': symbol,
                        'productType': 'USDT-FUTURES'
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=3)
                    
                    if isinstance(response, list) and len(response) > 0:
                        ticker_data = response[0]
                    elif isinstance(response, dict):
                        ticker_data = response
                    else:
                        logger.warning(f"미러링 V2 믹스: 예상치 못한 응답 형식: {type(response)}")
                        continue
                    
                elif endpoint == "/api/mix/v1/market/ticker":
                    # V1 믹스 마켓 (백업)
                    v1_symbol = f"{symbol}_UMCBL"
                    params = {
                        'symbol': v1_symbol
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=3)
                    
                    if isinstance(response, dict):
                        ticker_data = response
                    else:
                        logger.warning(f"미러링 V1 믹스: 예상치 못한 응답 형식: {type(response)}")
                        continue
                        
                elif endpoint == "/api/v2/spot/market/tickers":
                    # 스팟 마켓 (최후 백업)
                    spot_symbol = symbol.replace('USDT', '-USDT')
                    params = {
                        'symbol': spot_symbol
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=3)
                    
                    if isinstance(response, list) and len(response) > 0:
                        ticker_data = response[0]
                    elif isinstance(response, dict):
                        ticker_data = response
                    else:
                        logger.warning(f"미러링 V2 스팟: 예상치 못한 응답 형식: {type(response)}")
                        continue
                
                # 🔥🔥🔥 응답 데이터 검증 및 정규화
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
        
        # 🔥🔥🔥 모든 엔드포인트 실패
        error_msg = f"미러링 모든 티커 엔드포인트 실패: {', '.join(self.ticker_endpoints)}"
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
            
            logger.warning(f"미러링 유효한 가격 필드 없음: {list(ticker_data.keys())}")
            return False
            
        except Exception as e:
            logger.error(f"미러링 티커 데이터 검증 오류: {e}")
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
            logger.error(f"미러링 티커 데이터 정규화 실패: {e}")
            return ticker_data
    
    async def get_positions(self, symbol: str = None) -> List[Dict]:
        """🔥🔥🔥 포지션 조회 (V2 API) - 정확한 레버리지 및 포지션 정보"""
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
                    # 🔥🔥🔥 레버리지 정보 강화된 추출
                    leverage_raw = pos.get('leverage', '10')
                    try:
                        leverage = int(float(leverage_raw))
                        pos['leverage'] = str(leverage)  # 정수로 정규화
                        logger.info(f"포지션 레버리지 정규화: {leverage_raw} → {leverage}x")
                    except:
                        pos['leverage'] = '10'  # 기본값
                        logger.warning(f"레버리지 변환 실패, 기본값 사용: {leverage_raw}")
                    
                    # 🔥🔥🔥 포지션 크기 정보 상세 로깅
                    hold_side = pos.get('holdSide', 'unknown')
                    margin_size = float(pos.get('marginSize', 0))
                    entry_price = float(pos.get('openPriceAvg', 0))
                    unrealized_pnl = float(pos.get('unrealizedPL', 0))
                    
                    logger.info(f"🔍 활성 포지션 상세:")
                    logger.info(f"  - 심볼: {pos.get('symbol')}")
                    logger.info(f"  - 방향: {hold_side}")
                    logger.info(f"  - 크기: {total_size} BTC")
                    logger.info(f"  - 진입가: ${entry_price:,.2f}")
                    logger.info(f"  - 레버리지: {leverage}x")
                    logger.info(f"  - 마진: ${margin_size:,.2f}")
                    logger.info(f"  - 미실현 손익: ${unrealized_pnl:,.2f}")
                    
                    active_positions.append(pos)
                    
                    # 청산가 필드 로깅
                    logger.info(f"미러링 포지션 청산가 필드 확인:")
                    logger.info(f"  - liquidationPrice: {pos.get('liquidationPrice')}")
                    logger.info(f"  - markPrice: {pos.get('markPrice')}")
            
            logger.info(f"✅ 총 {len(active_positions)}개 활성 포지션 발견")
            return active_positions
        except Exception as e:
            logger.error(f"미러링 포지션 조회 실패: {e}")
            raise
    
    async def get_position_leverage(self, symbol: str = None) -> int:
        """🔥🔥🔥 포지션의 정확한 레버리지 정보 조회"""
        try:
            positions = await self.get_positions(symbol)
            
            for pos in positions:
                if float(pos.get('total', 0)) > 0:
                    leverage_raw = pos.get('leverage', '10')
                    try:
                        leverage = int(float(leverage_raw))
                        logger.info(f"📊 포지션 레버리지 조회 성공: {leverage}x")
                        return leverage
                    except:
                        logger.warning(f"포지션 레버리지 변환 실패: {leverage_raw}")
                        return 10
            
            # 포지션이 없는 경우 계정 기본 레버리지 조회
            logger.info("포지션이 없어 계정 기본 레버리지 조회")
            account_info = await self.get_account_info()
            
            # 계정에서 레버리지 추출
            for field in ['crossMarginLeverage', 'leverage', 'defaultLeverage']:
                leverage_value = account_info.get(field)
                if leverage_value:
                    try:
                        leverage = int(float(leverage_value))
                        if leverage > 1:
                            logger.info(f"📊 계정 기본 레버리지: {field} = {leverage}x")
                            return leverage
                    except:
                        continue
            
            logger.warning("레버리지 정보를 찾을 수 없어 기본값 10x 사용")
            return 10
            
        except Exception as e:
            logger.error(f"레버리지 조회 실패: {e}")
            return 10
    
    async def get_account_info(self) -> Dict:
        """🔥🔥🔥 계정 정보 조회 (V2 API) - 레버리지 정보 포함"""
        endpoint = "/api/v2/mix/account/accounts"
        params = {
            'productType': 'USDT-FUTURES',
            'marginCoin': 'USDT'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            logger.info(f"미러링 계정 정보 원본 응답: {response}")
            
            if isinstance(response, list) and len(response) > 0:
                account_info = response[0]
            else:
                account_info = response
            
            # 🔥🔥🔥 레버리지 관련 필드 상세 로깅
            logger.info(f"📊 계정 레버리지 관련 필드:")
            for field in ['crossMarginLeverage', 'leverage', 'defaultLeverage', 'maxLeverage']:
                value = account_info.get(field)
                if value:
                    logger.info(f"  - {field}: {value}")
            
            return account_info
        except Exception as e:
            logger.error(f"미러링 계정 정보 조회 실패: {e}")
            raise
    
    async def get_recent_filled_orders(self, symbol: str = None, minutes: int = 5) -> List[Dict]:
        """최근 체결된 주문 조회 (미러링용) - 레버리지 정보 포함"""
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
            
            logger.info(f"미러링 최근 {minutes}분간 체결된 주문: {len(filled_orders)}건")
            
            # 신규 진입 주문만 필터링 (reduce_only가 아닌 것)
            new_position_orders = []
            for order in filled_orders:
                reduce_only = order.get('reduceOnly', 'false')
                if reduce_only == 'false' or reduce_only is False:
                    # 🔥🔥🔥 주문에 레버리지 정보 추가 (포지션에서 조회)
                    try:
                        current_leverage = await self.get_position_leverage(symbol)
                        order['leverage'] = str(current_leverage)
                        logger.info(f"체결 주문에 레버리지 정보 추가: {current_leverage}x")
                    except:
                        order['leverage'] = '10'  # 기본값
                    
                    new_position_orders.append(order)
                    logger.info(f"미러링 신규 진입 주문 감지: {order.get('orderId')} - {order.get('side')} {order.get('size')} (레버리지: {order.get('leverage')}x)")
            
            return new_position_orders
            
        except Exception as e:
            logger.error(f"미러링 최근 체결 주문 조회 실패: {e}")
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
            logger.error(f"미러링 주문 내역 조회 실패: {e}")
            return []
    
    async def get_plan_orders_v2_working(self, symbol: str = None) -> List[Dict]:
        """🔥 V2 API로 예약 주문 조회 - 실제 작동하는 엔드포인트만 사용"""
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"🔍 미러링 V2 API 예약 주문 조회 시작: {symbol}")
            
            all_found_orders = []
            
            # 🔥 실제 작동하는 V2 엔드포인트만 사용
            working_endpoints = [
                "/api/v2/mix/order/orders-pending",          # ✅ 작동 확인됨
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
                    
                    # 응답에서 주문 목록 추출
                    orders = []
                    if isinstance(response, dict):
                        # entrustedList가 작동하는 필드명
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
                        
                        # 발견된 주문들 상세 로깅 - 🔥🔥🔥 TP/SL 정보 특별 체크 + 레버리지 정보
                        for i, order in enumerate(orders):
                            if order is None:
                                continue
                            
                            order_id = order.get('orderId', order.get('planOrderId', order.get('id', 'unknown')))
                            order_type = order.get('orderType', order.get('planType', order.get('type', 'unknown')))
                            side = order.get('side', order.get('tradeSide', 'unknown'))
                            trigger_price = order.get('triggerPrice', order.get('executePrice', order.get('price', 'unknown')))
                            size = order.get('size', order.get('volume', 'unknown'))
                            leverage = order.get('leverage', 'unknown')
                            
                            # 🔥🔥🔥 TP/SL 정보 상세 로깅
                            tp_price = order.get('presetStopSurplusPrice', order.get('stopSurplusPrice', order.get('takeProfitPrice')))
                            sl_price = order.get('presetStopLossPrice', order.get('stopLossPrice'))
                            
                            logger.info(f"  📝 미러링 주문 {i+1}: ID={order_id}, 타입={order_type}, 방향={side}, 크기={size}, 트리거가={trigger_price}, 레버리지={leverage}x")
                            
                            if tp_price:
                                logger.info(f"      🎯 TP 설정 발견: {tp_price}")
                            if sl_price:
                                logger.info(f"      🛡️ SL 설정 발견: {sl_price}")
                            
                            # 🔥🔥🔥 모든 필드 확인하여 TP/SL 관련 필드 찾기
                            tp_sl_fields = {}
                            for field_name, field_value in order.items():
                                if any(keyword in field_name.lower() for keyword in ['stop', 'profit', 'loss', 'tp', 'sl']):
                                    if field_value and str(field_value) not in ['0', '0.0', '', 'null']:
                                        tp_sl_fields[field_name] = field_value
                            
                            if tp_sl_fields:
                                logger.info(f"      🔍 TP/SL 관련 필드들: {tp_sl_fields}")
                        
                        # 첫 번째 성공한 엔드포인트에서 주문을 찾았으면 종료
                        break
                    else:
                        logger.debug(f"미러링 {endpoint}: 주문이 없음")
                        
                except Exception as e:
                    logger.debug(f"미러링 {endpoint} 조회 실패: {e}")
                    continue
            
            # 중복 제거
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
                    
                    # 🔥🔥🔥 주문에 레버리지 정보 추가 (없는 경우)
                    if not order.get('leverage'):
                        try:
                            current_leverage = await self.get_position_leverage()
                            order['leverage'] = str(current_leverage)
                            logger.info(f"예약 주문에 레버리지 정보 추가: {order_id} → {current_leverage}x")
                        except:
                            order['leverage'] = '10'  # 기본값
                    
                    unique_orders.append(order)
                    logger.debug(f"📝 미러링 V2 고유 예약 주문 추가: {order_id}")
            
            logger.info(f"🔥 미러링 V2 API에서 최종 발견된 고유한 예약 주문: {len(unique_orders)}건")
            return unique_orders
            
        except Exception as e:
            logger.error(f"미러링 V2 예약 주문 조회 실패: {e}")
            return []
    
    async def get_plan_orders_v1_working(self, symbol: str = None, plan_type: str = None) -> List[Dict]:
        """🔥 V1 API로 예약 주문 조회 - 실제 작동하는 엔드포인트만 사용"""
        try:
            # V1 API는 다른 심볼 형식을 사용
            symbol = symbol or self.config.symbol
            v1_symbol = f"{symbol}_UMCBL"
            
            logger.info(f"🔍 미러링 V1 API 예약 주문 조회 시작: {v1_symbol}")
            
            all_found_orders = []
            
            # 🔥 실제 작동하는 V1 엔드포인트만 사용
            working_endpoints = [
                "/api/mix/v1/plan/currentPlan",              # ✅ 작동 확인됨 (비어있을 뿐)
            ]
            
            for endpoint in working_endpoints:
                try:
                    params = {
                        'symbol': v1_symbol,
                        'productType': 'umcbl'
                    }
                    
                    # plan_type이 지정된 경우 추가
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
                    
                    # 응답에서 주문 목록 추출
                    orders = []
                    if isinstance(response, dict):
                        # V1 API 응답 구조
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
                        
                        # 발견된 주문들 상세 로깅 - 🔥🔥🔥 TP/SL 정보 특별 체크
                        for i, order in enumerate(orders):
                            if order is None:
                                continue
                            
                            order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
                            order_type = order.get('orderType', order.get('planType', 'unknown'))
                            side = order.get('side', order.get('tradeSide', 'unknown'))
                            trigger_price = order.get('triggerPrice', order.get('executePrice', 'unknown'))
                            size = order.get('size', order.get('volume', 'unknown'))
                            
                            # 🔥🔥🔥 TP/SL 정보 상세 로깅
                            tp_price = order.get('presetStopSurplusPrice', order.get('stopSurplusPrice', order.get('takeProfitPrice')))
                            sl_price = order.get('presetStopLossPrice', order.get('stopLossPrice'))
                            
                            logger.info(f"  📝 미러링 V1 주문 {i+1}: ID={order_id}, 타입={order_type}, 방향={side}, 크기={size}, 트리거가={trigger_price}")
                            
                            if tp_price:
                                logger.info(f"      🎯 V1 TP 설정 발견: {tp_price}")
                            if sl_price:
                                logger.info(f"      🛡️ V1 SL 설정 발견: {sl_price}")
                        
                        # 첫 번째 성공한 엔드포인트에서 주문을 찾았으면 종료
                        break
                    else:
                        logger.debug(f"미러링 {endpoint}: 주문이 없음")
                        
                except Exception as e:
                    logger.debug(f"미러링 {endpoint} 조회 실패: {e}")
                    continue
            
            # 중복 제거
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
        """🔥 모든 트리거 주문 조회 - 작동하는 엔드포인트만 사용"""
        all_orders = []
        symbol = symbol or self.config.symbol
        
        logger.info(f"🔍 미러링 모든 트리거 주문 조회 시작: {symbol}")
        
        # 🔥 1. V2 API 조회 (우선)
        try:
            v2_orders = await self.get_plan_orders_v2_working(symbol)
            if v2_orders:
                all_orders.extend(v2_orders)
                logger.info(f"✅ 미러링 V2에서 {len(v2_orders)}개 예약 주문 발견")
        except Exception as e:
            logger.warning(f"미러링 V2 예약 주문 조회 실패: {e}")
        
        # 🔥 2. V1 일반 예약 주문
        try:
            v1_orders = await self.get_plan_orders_v1_working(symbol)
            if v1_orders:
                all_orders.extend(v1_orders)
                logger.info(f"✅ 미러링 V1 일반에서 {len(v1_orders)}개 예약 주문 발견")
        except Exception as e:
            logger.warning(f"미러링 V1 일반 예약 주문 조회 실패: {e}")
        
        # 🔥 3. V1 TP/SL 주문
        try:
            v1_tp_sl = await self.get_plan_orders_v1_working(symbol, 'profit_loss')
            if v1_tp_sl:
                all_orders.extend(v1_tp_sl)
                logger.info(f"✅ 미러링 V1 TP/SL에서 {len(v1_tp_sl)}개 주문 발견")
        except Exception as e:
            logger.warning(f"미러링 V1 TP/SL 주문 조회 실패: {e}")
        
        # 중복 제거
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
        
        # 🔥🔥🔥 수정: 예약 주문이 없을 때 경고 로그 제거
        if unique_orders:
            logger.info("📋 미러링 발견된 예약 주문 목록:")
            for i, order in enumerate(unique_orders, 1):
                order_id = order.get('orderId', order.get('planOrderId', order.get('id', 'unknown')))
                side = order.get('side', order.get('tradeSide', 'unknown'))
                trigger_price = order.get('triggerPrice', order.get('executePrice', order.get('price', 'unknown')))
                size = order.get('size', order.get('volume', 'unknown'))
                order_type = order.get('orderType', order.get('planType', order.get('type', 'unknown')))
                leverage = order.get('leverage', 'unknown')
                
                # 🔥🔥🔥 TP/SL 정보도 로깅
                tp_price = order.get('presetStopSurplusPrice', order.get('stopSurplusPrice', order.get('takeProfitPrice')))
                sl_price = order.get('presetStopLossPrice', order.get('stopLossPrice'))
                
                logger.info(f"  {i}. ID: {order_id}, 방향: {side}, 수량: {size}, 트리거가: {trigger_price}, 타입: {order_type}, 레버리지: {leverage}x")
                if tp_price:
                    logger.info(f"     🎯 TP: {tp_price}")
                if sl_price:
                    logger.info(f"     🛡️ SL: {sl_price}")
        else:
            # 🔥🔥🔥 수정: WARNING → DEBUG로 변경하여 빨간 로그 제거
            logger.debug("📝 미러링 현재 예약 주문이 없습니다.")
        
        return unique_orders
    
    async def get_plan_orders(self, symbol: str = None, plan_type: str = None) -> List[Dict]:
        """플랜 주문(예약 주문) 조회 - 모든 방법 시도"""
        try:
            # 모든 트리거 주문 조회
            all_orders = await self.get_all_trigger_orders(symbol)
            
            # plan_type이 지정되면 필터링
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
        """🔥🔥🔥 모든 플랜 주문과 TP/SL 조회 - 클로징 주문 분류 강화 + 레버리지 정보"""
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"🔍 미러링 모든 예약 주문 및 TP/SL 조회 시작: {symbol}")
            
            # 모든 트리거 주문 조회 (개선된 방식)
            all_orders = await self.get_all_trigger_orders(symbol)
            
            # TP/SL과 일반 예약주문 분류 - 클로징 주문 감지 강화
            tp_sl_orders = []
            plan_orders = []
            
            # 🔥🔥🔥 현재 레버리지 정보 조회 (주문에 레버리지가 없는 경우 사용)
            current_leverage = await self.get_position_leverage(symbol)
            
            for order in all_orders:
                if order is None:
                    continue
                    
                is_tp_sl = False
                
                # 🔥🔥🔥 클로징 주문 분류 조건들 강화
                side = order.get('side', order.get('tradeSide', '')).lower()
                reduce_only = order.get('reduceOnly', False)
                order_type = order.get('orderType', order.get('planType', '')).lower()
                
                # 🔥🔥🔥 주문에 레버리지 정보 추가 (없는 경우)
                if not order.get('leverage'):
                    order['leverage'] = str(current_leverage)
                    logger.info(f"주문에 레버리지 정보 추가: {order.get('orderId', order.get('planOrderId'))} → {current_leverage}x")
                
                # TP/SL 분류 조건들 강화
                if (order.get('planType') == 'profit_loss' or 
                    order.get('isPlan') == 'profit_loss' or
                    'close' in side or
                    'tp/' in side or  # TP/SL 키워드 추가
                    'sl/' in side or
                    'profit' in side or
                    'loss' in side or
                    'close_long' in side or
                    'close_short' in side or
                    reduce_only == True or
                    reduce_only == 'true' or
                    str(reduce_only).lower() == 'true' or
                    'profit' in order_type or
                    'loss' in order_type or
                    'close' in order_type):
                    is_tp_sl = True
                
                # 🔥🔥🔥 TP/SL 가격이 설정된 경우 처리 개선
                tp_price = self._extract_tp_price(order)
                sl_price = self._extract_sl_price(order)
                
                # TP/SL이 설정된 일반 주문은 plan_orders에 분류하되 TP/SL 정보 보존
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
                    logger.info(f"📊 미러링 TP/SL 주문 분류: {order.get('orderId', order.get('planOrderId'))} - {order.get('side', order.get('tradeSide'))} (레버리지: {order.get('leverage')}x)")
                else:
                    plan_orders.append(order)
                    logger.info(f"📈 미러링 일반 예약 주문 분류: {order.get('orderId', order.get('planOrderId'))} - {order.get('side', order.get('tradeSide'))} (레버리지: {order.get('leverage')}x)")
            
            # 통합 결과
            result = {
                'plan_orders': plan_orders,
                'tp_sl_orders': tp_sl_orders,
                'total_count': len(all_orders)
            }
            
            logger.info(f"🔥 미러링 전체 예약 주문 분류 완료: 일반 {len(plan_orders)}건 + TP/SL {len(tp_sl_orders)}건 = 총 {result['total_count']}건")
            
            # 각 카테고리별 상세 로깅
            if plan_orders:
                logger.info("📈 미러링 일반 예약 주문 목록:")
                for i, order in enumerate(plan_orders, 1):
                    order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
                    side = order.get('side', order.get('tradeSide', 'unknown'))
                    price = order.get('price', order.get('triggerPrice', 'unknown'))
                    leverage = order.get('leverage', 'unknown')
                    
                    # 🔥🔥🔥 강화된 TP/SL 추출
                    tp_price = self._extract_tp_price(order)
                    sl_price = self._extract_sl_price(order)
                    
                    logger.info(f"  {i}. ID: {order_id}, 방향: {side}, 가격: {price}, 레버리지: {leverage}x")
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
                    leverage = order.get('leverage', 'unknown')
                    logger.info(f"  {i}. ID: {order_id}, 방향: {side}, 트리거가: {trigger_price}, 레버리지: {leverage}x")
            
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
        """🔥🔥🔥 TP 가격 추출 - 모든 가능한 필드 확인"""
        try:
            # 가능한 TP 필드명들
            tp_fields = [
                'presetStopSurplusPrice',  # 주요 필드
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
        """🔥🔥🔥 SL 가격 추출 - 모든 가능한 필드 확인"""
        try:
            # 가능한 SL 필드명들
            sl_fields = [
                'presetStopLossPrice',  # 주요 필드
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
        """🔥🔥🔥 API 연결 상태 조회"""
        return {
            'healthy': self.api_connection_healthy,
            'consecutive_failures': self.consecutive_failures,
            'last_successful_call': self.last_successful_call.isoformat(),
            'api_keys_validated': self.api_keys_validated,
            'max_failures_threshold': self.max_consecutive_failures
        }
    
    async def reset_connection_status(self):
        """🔥🔥🔥 연결 상태 리셋"""
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
        logger.info("비트겟 미러링 API 연결 상태 리셋 완료")
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 미러링 클라이언트 세션 종료")
