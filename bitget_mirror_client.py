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
                async with self.session.request(method, url, headers=headers, data=body if body else None) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        try:
                            result = json.loads(response_text)
                            
                            # 응답 상태 확인
                            if isinstance(result, dict):
                                if result.get('code') == '00000':
                                    self.api_connection_healthy = True
                                    self.consecutive_failures = 0
                                    self.last_successful_call = datetime.now()
                                    return result.get('data')
                                else:
                                    error_msg = result.get('msg', 'Unknown error')
                                    logger.warning(f"API 응답 오류: {error_msg}")
                                    if attempt == max_retries - 1:
                                        raise Exception(f"API Error: {error_msg}")
                            else:
                                self.api_connection_healthy = True
                                self.consecutive_failures = 0
                                self.last_successful_call = datetime.now()
                                return result
                        except json.JSONDecodeError:
                            logger.error(f"JSON 디코딩 실패: {response_text[:200]}")
                            if attempt == max_retries - 1:
                                raise Exception("Invalid JSON response")
                    else:
                        logger.warning(f"HTTP {response.status}: {response_text[:200]}")
                        if attempt == max_retries - 1:
                            raise Exception(f"HTTP {response.status}")
                
            except asyncio.TimeoutError:
                logger.warning(f"요청 타임아웃 ({attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    self.consecutive_failures += 1
                    raise Exception("Request timeout")
            except Exception as e:
                logger.error(f"요청 실패 ({attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    self.consecutive_failures += 1
                    raise
            
            await asyncio.sleep(0.5 * (attempt + 1))
        
        return None

    async def get_ticker(self, symbol: str = None) -> Dict:
        """현재가 조회 - 정확한 심볼 사용"""
        symbol = symbol or self.symbol
        
        for endpoint in self.ticker_endpoints:
            try:
                # v1 API인 경우 심볼 변환
                if self._is_v1_endpoint(endpoint):
                    query_symbol = self._get_v1_symbol(symbol)
                    params = {'symbol': query_symbol}
                else:
                    # v2 API는 원래 심볼 사용
                    params = {'symbol': symbol}
                
                logger.debug(f"티커 조회: {endpoint}, 심볼: {params['symbol']}")
                
                response = await self._request('GET', endpoint, params=params, max_retries=2)
                
                if response is not None:
                    logger.debug(f"티커 조회 성공: {endpoint}")
                    return response
                    
            except Exception as e:
                logger.warning(f"티커 조회 실패: {endpoint} - {e}")
                continue
        
        logger.error("모든 티커 엔드포인트에서 조회 실패")
        return {}

    async def get_account_info(self) -> Dict:
        """계정 정보 조회"""
        try:
            params = {
                'productType': self.product_type,
                'marginCoin': self.margin_coin
            }
            
            response = await self._request('GET', "/api/v2/mix/account/accounts", params=params)
            
            if response:
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

    async def get_tp_sl_orders(self, symbol: str = None, status: str = 'live') -> List[Dict]:
        """TP/SL 주문 조회 - 통합된 방식"""
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
        """예약 주문과 TP/SL 주문을 함께 조회"""
        symbol = symbol or self.config.symbol
        
        try:
            logger.info(f"🔍 전체 플랜 주문 조회 시작: {symbol}")
            
            # 예약 주문과 TP/SL 주문을 병렬로 조회
            plan_orders_task = self.get_plan_orders(symbol)
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
            
            # 결과 로깅
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
                
                # TP/SL 가격 확인
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
                
                # 로깅
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

    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
