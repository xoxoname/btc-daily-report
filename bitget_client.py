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
        await self._validate_api_keys()
        logger.info("Bitget 클라이언트 초기화 완료")
    
    async def _validate_api_keys(self):
        """API 키 유효성 검증"""
        try:
            logger.info("비트겟 API 키 유효성 검증 시작...")
            
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
                logger.debug(f"비트겟 API 요청 (시도 {attempt + 1}/{max_retries}): {method} {endpoint}")
                
                async with self.session.request(method, url, headers=headers, data=body) as response:
                    response_text = await response.text()
                    
                    logger.debug(f"비트겟 API 응답 상태: {response.status}")
                    
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
                        logger.error(f"비트겟 API HTTP 오류: {error_msg}")
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
        """성공 기록"""
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
    
    def _record_failure(self, error_msg: str):
        """실패 기록"""
        self.consecutive_failures += 1
        
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.api_connection_healthy = False
            logger.error(f"비트겟 API 연결 비정상 상태: 연속 {self.consecutive_failures}회 실패")
        
        logger.warning(f"비트겟 API 실패 기록: {error_msg} (연속 실패: {self.consecutive_failures}회)")
    
    async def get_ticker(self, symbol: str = None) -> Dict:
        """현재가 정보 조회 - 다중 엔드포인트 지원"""
        symbol = symbol or self.config.symbol
        
        for i, endpoint in enumerate(self.ticker_endpoints):
            try:
                logger.debug(f"티커 조회 시도 {i + 1}/{len(self.ticker_endpoints)}: {endpoint}")
                
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
                        logger.warning(f"V2 믹스: 예상치 못한 응답 형식: {type(response)}")
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
                        logger.warning(f"V1 믹스: 예상치 못한 응답 형식: {type(response)}")
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
                        logger.warning(f"V2 스팟: 예상치 못한 응답 형식: {type(response)}")
                        continue
                
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
        
        error_msg = f"모든 티커 엔드포인트 실패: {', '.join(self.ticker_endpoints)}"
        logger.error(error_msg)
        self._record_failure("모든 티커 엔드포인트 실패")
        return {}
    
    def _validate_ticker_data(self, ticker_data: Dict) -> bool:
        """티커 데이터 유효성 검증"""
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
            
            logger.warning(f"유효한 가격 필드 없음: {list(ticker_data.keys())}")
            return False
            
        except Exception as e:
            logger.error(f"티커 데이터 검증 오류: {e}")
            return False
    
    def _normalize_ticker_data(self, ticker_data: Dict, endpoint: str) -> Dict:
        """티커 데이터 정규화"""
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
            
            return active_positions
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
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
            
            if isinstance(response, dict) and 'orderList' in response:
                return response['orderList']
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
            
            now = datetime.now()
            start_time = now - timedelta(minutes=minutes)
            start_timestamp = int(start_time.timestamp() * 1000)
            end_timestamp = int(now.timestamp() * 1000)
            
            filled_orders = await self.get_order_history(
                symbol=symbol,
                status='filled',
                start_time=start_timestamp,
                end_time=end_timestamp,
                limit=50
            )
            
            logger.info(f"최근 {minutes}분간 체결된 주문: {len(filled_orders)}건")
            
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
    
    async def get_all_plan_orders_with_tp_sl(self, symbol: str = None) -> Dict:
        """🔥 모든 플랜 주문과 TP/SL 조회 - 개선된 TP/SL 정보 추출"""
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"🔍 모든 예약 주문 및 TP/SL 조회 시작: {symbol}")
            
            # 모든 트리거 주문 조회
            all_orders = await self.get_all_trigger_orders(symbol)
            
            # TP/SL과 일반 예약주문 분류
            tp_sl_orders = []
            plan_orders = []
            
            for order in all_orders:
                if order is None:
                    continue
                
                # 🔥 TP/SL 정보 강화 추출
                tp_price = self._extract_tp_price_enhanced(order)
                sl_price = self._extract_sl_price_enhanced(order)
                
                # TP/SL 설정이 있는 주문에 정보 추가
                if tp_price or sl_price:
                    order['extracted_tp_price'] = tp_price
                    order['extracted_sl_price'] = sl_price
                    order['has_tp_sl_settings'] = True
                    logger.info(f"🎯 TP/SL 설정 발견: {order.get('orderId', order.get('planOrderId'))} - TP: ${tp_price:.2f if tp_price else 0}, SL: ${sl_price:.2f if sl_price else 0}")
                else:
                    order['has_tp_sl_settings'] = False
                
                # TP/SL 분류 조건들
                is_tp_sl = False
                if (order.get('planType') == 'profit_loss' or 
                    order.get('isPlan') == 'profit_loss' or
                    order.get('side') in ['close_long', 'close_short'] or
                    order.get('tradeSide') in ['close_long', 'close_short'] or
                    order.get('reduceOnly') == True or
                    order.get('reduceOnly') == 'true'):
                    is_tp_sl = True
                
                if is_tp_sl:
                    tp_sl_orders.append(order)
                    logger.info(f"📊 TP/SL 주문 분류: {order.get('orderId', order.get('planOrderId'))} - {order.get('side', order.get('tradeSide'))}")
                else:
                    plan_orders.append(order)
                    logger.info(f"📈 일반 예약 주문 분류: {order.get('orderId', order.get('planOrderId'))} - {order.get('side', order.get('tradeSide'))}")
            
            # 통합 결과
            result = {
                'plan_orders': plan_orders,
                'tp_sl_orders': tp_sl_orders,
                'total_count': len(all_orders)
            }
            
            logger.info(f"🔥 전체 예약 주문 분류 완료: 일반 {len(plan_orders)}건 + TP/SL {len(tp_sl_orders)}건 = 총 {result['total_count']}건")
            
            return result
            
        except Exception as e:
            logger.error(f"전체 플랜 주문 조회 실패: {e}")
            return {
                'plan_orders': [],
                'tp_sl_orders': [],
                'total_count': 0,
                'error': str(e)
            }
    
    def _extract_tp_price_enhanced(self, order: Dict) -> Optional[float]:
        """🔥 강화된 TP 가격 추출 - 비트겟 공식 필드"""
        try:
            # 비트겟 공식 TP 필드명들 (우선순위 순)
            tp_fields = [
                'presetStopSurplusPrice',  # 가장 정확한 필드
                'stopSurplusPrice',
                'takeProfitPrice',
                'tpPrice',
                'stopProfit'
            ]
            
            for field in tp_fields:
                value = order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        tp_price = float(value)
                        if tp_price > 0:
                            logger.debug(f"TP 가격 추출 성공: {field} = ${tp_price:.2f}")
                            return tp_price
                    except:
                        continue
            
            return None
            
        except Exception as e:
            logger.debug(f"TP 가격 추출 오류: {e}")
            return None
    
    def _extract_sl_price_enhanced(self, order: Dict) -> Optional[float]:
        """🔥 강화된 SL 가격 추출 - 비트겟 공식 필드"""
        try:
            # 비트겟 공식 SL 필드명들 (우선순위 순)
            sl_fields = [
                'presetStopLossPrice',  # 가장 정확한 필드
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
                            logger.debug(f"SL 가격 추출 성공: {field} = ${sl_price:.2f}")
                            return sl_price
                    except:
                        continue
            
            return None
            
        except Exception as e:
            logger.debug(f"SL 가격 추출 오류: {e}")
            return None
    
    async def get_all_trigger_orders(self, symbol: str = None) -> List[Dict]:
        """모든 트리거 주문 조회 - 작동하는 엔드포인트만 사용"""
        all_orders = []
        symbol = symbol or self.config.symbol
        
        logger.info(f"🔍 모든 트리거 주문 조회 시작: {symbol}")
        
        # V2 API 조회 (우선)
        try:
            v2_orders = await self.get_plan_orders_v2_working(symbol)
            if v2_orders:
                all_orders.extend(v2_orders)
                logger.info(f"✅ V2에서 {len(v2_orders)}개 예약 주문 발견")
        except Exception as e:
            logger.warning(f"V2 예약 주문 조회 실패: {e}")
        
        # V1 일반 예약 주문
        try:
            v1_orders = await self.get_plan_orders_v1_working(symbol)
            if v1_orders:
                all_orders.extend(v1_orders)
                logger.info(f"✅ V1 일반에서 {len(v1_orders)}개 예약 주문 발견")
        except Exception as e:
            logger.warning(f"V1 일반 예약 주문 조회 실패: {e}")
        
        # V1 TP/SL 주문
        try:
            v1_tp_sl = await self.get_plan_orders_v1_working(symbol, 'profit_loss')
            if v1_tp_sl:
                all_orders.extend(v1_tp_sl)
                logger.info(f"✅ V1 TP/SL에서 {len(v1_tp_sl)}개 주문 발견")
        except Exception as e:
            logger.warning(f"V1 TP/SL 주문 조회 실패: {e}")
        
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
        
        logger.info(f"🔥 최종 발견된 고유한 트리거 주문: {len(unique_orders)}건")
        
        if unique_orders:
            logger.info("📋 발견된 예약 주문 목록:")
            for i, order in enumerate(unique_orders, 1):
                order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
                side = order.get('side', order.get('tradeSide', 'unknown'))
                trigger_price = order.get('triggerPrice', order.get('executePrice', order.get('price', 'unknown')))
                size = order.get('size', order.get('volume', 'unknown'))
                order_type = order.get('orderType', order.get('planType', order.get('type', 'unknown')))
                
                # TP/SL 정보도 로깅
                tp_price = self._extract_tp_price_enhanced(order)
                sl_price = self._extract_sl_price_enhanced(order)
                
                logger.info(f"  {i}. ID: {order_id}, 방향: {side}, 수량: {size}, 트리거가: {trigger_price}, 타입: {order_type}")
                if tp_price:
                    logger.info(f"     🎯 TP: ${tp_price:.2f}")
                if sl_price:
                    logger.info(f"     🛡️ SL: ${sl_price:.2f}")
        else:
            logger.debug("📝 현재 예약 주문이 없습니다.")
        
        return unique_orders
    
    async def get_plan_orders_v2_working(self, symbol: str = None) -> List[Dict]:
        """V2 API로 예약 주문 조회 - 실제 작동하는 엔드포인트만 사용"""
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"🔍 V2 API 예약 주문 조회 시작: {symbol}")
            
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
                    
                    logger.info(f"🔍 예약 주문 조회: {endpoint}")
                    response = await self._request('GET', endpoint, params=params)
                    
                    if response is None:
                        logger.debug(f"{endpoint}: 응답이 None")
                        continue
                    
                    orders = []
                    if isinstance(response, dict):
                        if 'entrustedList' in response:
                            orders_raw = response['entrustedList']
                            if isinstance(orders_raw, list):
                                orders = orders_raw
                                logger.info(f"✅ {endpoint}: entrustedList에서 {len(orders)}개 주문 발견")
                    elif isinstance(response, list):
                        orders = response
                        logger.info(f"✅ {endpoint}: 직접 리스트에서 {len(orders)}개 주문 발견")
                    
                    if orders:
                        all_found_orders.extend(orders)
                        logger.info(f"🎯 {endpoint}에서 발견: {len(orders)}개 주문")
                        
                        # 발견된 주문들 상세 로깅 - TP/SL 정보 특별 체크
                        for i, order in enumerate(orders):
                            if order is None:
                                continue
                            
                            order_id = order.get('orderId', order.get('planOrderId', order.get('id', 'unknown')))
                            order_type = order.get('orderType', order.get('planType', order.get('type', 'unknown')))
                            side = order.get('side', order.get('tradeSide', 'unknown'))
                            trigger_price = order.get('triggerPrice', order.get('executePrice', order.get('price', 'unknown')))
                            size = order.get('size', order.get('volume', 'unknown'))
                            
                            # TP/SL 정보 상세 로깅
                            tp_price = self._extract_tp_price_enhanced(order)
                            sl_price = self._extract_sl_price_enhanced(order)
                            
                            logger.info(f"  📝 주문 {i+1}: ID={order_id}, 타입={order_type}, 방향={side}, 크기={size}, 트리거가={trigger_price}")
                            
                            if tp_price:
                                logger.info(f"      🎯 TP 설정 발견: ${tp_price:.2f}")
                            if sl_price:
                                logger.info(f"      🛡️ SL 설정 발견: ${sl_price:.2f}")
                        
                        break
                    else:
                        logger.debug(f"{endpoint}: 주문이 없음")
                        
                except Exception as e:
                    logger.debug(f"{endpoint} 조회 실패: {e}")
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
            
            logger.info(f"🔥 V2 API에서 최종 발견된 고유한 예약 주문: {len(unique_orders)}건")
            return unique_orders
            
        except Exception as e:
            logger.error(f"V2 예약 주문 조회 실패: {e}")
            return []
    
    async def get_plan_orders_v1_working(self, symbol: str = None, plan_type: str = None) -> List[Dict]:
        """V1 API로 예약 주문 조회 - 실제 작동하는 엔드포인트만 사용"""
        try:
            symbol = symbol or self.config.symbol
            v1_symbol = f"{symbol}_UMCBL"
            
            logger.info(f"🔍 V1 API 예약 주문 조회 시작: {v1_symbol}")
            
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
                    
                    logger.info(f"🔍 V1 예약 주문 조회: {endpoint}")
                    response = await self._request('GET', endpoint, params=params)
                    
                    if response is None:
                        logger.debug(f"{endpoint}: 응답이 None")
                        continue
                    
                    orders = []
                    if isinstance(response, dict):
                        for field_name in ['list', 'data']:
                            if field_name in response:
                                orders_raw = response[field_name]
                                if isinstance(orders_raw, list):
                                    orders = orders_raw
                                    logger.info(f"✅ {endpoint}: {field_name}에서 {len(orders)}개 주문 발견")
                                    break
                    elif isinstance(response, list):
                        orders = response
                        logger.info(f"✅ {endpoint}: 직접 리스트에서 {len(orders)}개 주문 발견")
                    
                    if orders:
                        all_found_orders.extend(orders)
                        logger.info(f"🎯 {endpoint}에서 발견: {len(orders)}개 주문")
                        
                        # 발견된 주문들 상세 로깅 - TP/SL 정보 특별 체크
                        for i, order in enumerate(orders):
                            if order is None:
                                continue
                            
                            order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
                            order_type = order.get('orderType', order.get('planType', 'unknown'))
                            side = order.get('side', order.get('tradeSide', 'unknown'))
                            trigger_price = order.get('triggerPrice', order.get('executePrice', 'unknown'))
                            size = order.get('size', order.get('volume', 'unknown'))
                            
                            # TP/SL 정보 상세 로깅
                            tp_price = self._extract_tp_price_enhanced(order)
                            sl_price = self._extract_sl_price_enhanced(order)
                            
                            logger.info(f"  📝 V1 주문 {i+1}: ID={order_id}, 타입={order_type}, 방향={side}, 크기={size}, 트리거가={trigger_price}")
                            
                            if tp_price:
                                logger.info(f"      🎯 V1 TP 설정 발견: ${tp_price:.2f}")
                            if sl_price:
                                logger.info(f"      🛡️ V1 SL 설정 발견: ${sl_price:.2f}")
                        
                        break
                    else:
                        logger.debug(f"{endpoint}: 주문이 없음")
                        
                except Exception as e:
                    logger.debug(f"{endpoint} 조회 실패: {e}")
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
            
            logger.info(f"🔥 V1 API에서 최종 발견된 고유한 예약 주문: {len(unique_orders)}건")
            return unique_orders
            
        except Exception as e:
            logger.error(f"V1 예약 주문 조회 실패: {e}")
            return []
    
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
    
    async def get_enhanced_profit_history(self, symbol: str = None, days: int = 7) -> Dict:
        """개선된 정확한 손익 조회 - 다중 검증 방식"""
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"=== 🔥 개선된 {days}일 손익 조회 시작 ===")
            
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_start = today_start - timedelta(days=days-1)
            period_end = now
            
            logger.info(f"📅 조회 기간: {period_start.strftime('%Y-%m-%d %H:%M')} ~ {period_end.strftime('%Y-%m-%d %H:%M')} (KST)")
            
            start_time_utc = period_start.astimezone(pytz.UTC)
            end_time_utc = period_end.astimezone(pytz.UTC)
            start_timestamp = int(start_time_utc.timestamp() * 1000)
            end_timestamp = int(end_time_utc.timestamp() * 1000)
            
            # 현재 계정 정보
            account = await self.get_account_info()
            current_equity = float(account.get('accountEquity', 0))
            
            # 현재 포지션 정보에서 achievedProfits 확인
            positions = await self.get_positions()
            achieved_profits = 0
            
            for pos in positions:
                achieved = float(pos.get('achievedProfits', 0))
                if achieved != 0:
                    achieved_profits = achieved
                    logger.info(f"포지션 achievedProfits: ${achieved:.2f}")
            
            # 간단한 7일 손익 계산 (achievedProfits 기반)
            if achieved_profits > 0:
                return {
                    'total_pnl': achieved_profits,
                    'days': days,
                    'average_daily': achieved_profits / days,
                    'source': 'achievedProfits',
                    'confidence': 'medium',
                    'daily_pnl': {}
                }
            else:
                return {
                    'total_pnl': 0,
                    'days': days,
                    'average_daily': 0,
                    'source': 'no_data',
                    'confidence': 'low',
                    'daily_pnl': {}
                }
            
        except Exception as e:
            logger.error(f"개선된 손익 조회 실패: {e}")
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
    
    async def get_profit_loss_history(self, symbol: str = None, days: int = 7) -> Dict:
        """손익 내역 조회 - 새로운 정확한 방식 사용"""
        return await self.get_enhanced_profit_history(symbol, days)
    
    async def get_funding_rate(self, symbol: str = None) -> Dict:
        """펀딩비 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/market/current-fund-rate"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            if isinstance(response, list) and len(response) > 0:
                return response[0]
            return response
        except Exception as e:
            logger.error(f"펀딩비 조회 실패: {e}")
            raise
    
    async def get_open_interest(self, symbol: str = None) -> Dict:
        """미결제약정 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/market/open-interest"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            return response
        except Exception as e:
            logger.error(f"미결제약정 조회 실패: {e}")
            raise
    
    async def get_kline(self, symbol: str = None, granularity: str = '1H', limit: int = 100) -> List[Dict]:
        """K라인 데이터 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/market/candles"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES',
            'granularity': granularity,
            'limit': str(limit)
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            return response if isinstance(response, list) else []
        except Exception as e:
            logger.error(f"K라인 조회 실패: {e}")
            raise
    
    async def get_api_connection_status(self) -> Dict:
        """API 연결 상태 조회"""
        return {
            'healthy': self.api_connection_healthy,
            'consecutive_failures': self.consecutive_failures,
            'last_successful_call': self.last_successful_call.isoformat(),
            'api_keys_validated': self.api_keys_validated,
            'max_failures_threshold': self.max_consecutive_failures
        }
    
    async def reset_connection_status(self):
        """연결 상태 리셋"""
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
        logger.info("비트겟 API 연결 상태 리셋 완료")
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
