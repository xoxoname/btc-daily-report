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
        
    def _initialize_session(self):
        """세션 초기화"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            logger.info("Bitget 클라이언트 세션 초기화 완료")
        
    async def initialize(self):
        """클라이언트 초기화"""
        self._initialize_session()
        logger.info("Bitget 클라이언트 초기화 완료")
    
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
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """API 요청"""
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
        
        try:
            logger.debug(f"API 요청: {method} {url}")
            async with self.session.request(method, url, headers=headers, data=body) as response:
                response_text = await response.text()
                logger.debug(f"API 응답 상태: {response.status}")
                
                response_data = json.loads(response_text)
                
                if response.status != 200:
                    logger.error(f"API 요청 실패: {response.status} - {response_data}")
                    raise Exception(f"API 요청 실패: {response_data}")
                
                if response_data.get('code') != '00000':
                    logger.error(f"API 응답 오류: {response_data}")
                    raise Exception(f"API 응답 오류: {response_data}")
                
                return response_data.get('data', {})
                
        except Exception as e:
            logger.error(f"API 요청 중 오류: {e}")
            raise
    
    async def get_ticker(self, symbol: str = None) -> Dict:
        """현재가 정보 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/market/ticker"
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
            logger.error(f"현재가 조회 실패: {e}")
            raise
    
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
    
    async def get_plan_orders_v2_working(self, symbol: str = None) -> List[Dict]:
        """V2 API로 예약 주문 조회 - 실제 작동하는 엔드포인트만 사용"""
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"🔍 V2 API 예약 주문 조회 시작: {symbol}")
            
            all_found_orders = []
            
            # 실제 작동하는 V2 엔드포인트만 사용
            working_endpoints = [
                "/api/v2/mix/order/orders-pending",          # ✅ 작동 확인됨
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
                    
                    # 응답에서 주문 목록 추출
                    orders = []
                    if isinstance(response, dict):
                        # entrustedList가 작동하는 필드명
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
                        
                        # 발견된 주문들 상세 로깅
                        for i, order in enumerate(orders):
                            if order is None:
                                continue
                            
                            order_id = order.get('orderId', order.get('planOrderId', order.get('id', 'unknown')))
                            order_type = order.get('orderType', order.get('planType', order.get('type', 'unknown')))
                            side = order.get('side', order.get('tradeSide', 'unknown'))
                            trigger_price = order.get('triggerPrice', order.get('executePrice', order.get('price', 'unknown')))
                            size = order.get('size', order.get('volume', 'unknown'))
                            
                            logger.info(f"  📝 주문 {i+1}: ID={order_id}, 타입={order_type}, 방향={side}, 크기={size}, 트리거가={trigger_price}")
                        
                        # 첫 번째 성공한 엔드포인트에서 주문을 찾았으면 종료
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
                    logger.debug(f"📝 V2 고유 예약 주문 추가: {order_id}")
            
            logger.info(f"🔥 V2 API에서 최종 발견된 고유한 예약 주문: {len(unique_orders)}건")
            return unique_orders
            
        except Exception as e:
            logger.error(f"V2 예약 주문 조회 실패: {e}")
            return []
    
    async def get_plan_orders_v1_working(self, symbol: str = None, plan_type: str = None) -> List[Dict]:
        """V1 API로 예약 주문 조회 - 실제 작동하는 엔드포인트만 사용"""
        try:
            # V1 API는 다른 심볼 형식을 사용
            symbol = symbol or self.config.symbol
            v1_symbol = f"{symbol}_UMCBL"
            
            logger.info(f"🔍 V1 API 예약 주문 조회 시작: {v1_symbol}")
            
            all_found_orders = []
            
            # 실제 작동하는 V1 엔드포인트만 사용
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
                    
                    logger.info(f"🔍 V1 예약 주문 조회: {endpoint}")
                    response = await self._request('GET', endpoint, params=params)
                    
                    if response is None:
                        logger.debug(f"{endpoint}: 응답이 None")
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
                                    logger.info(f"✅ {endpoint}: {field_name}에서 {len(orders)}개 주문 발견")
                                    break
                    elif isinstance(response, list):
                        orders = response
                        logger.info(f"✅ {endpoint}: 직접 리스트에서 {len(orders)}개 주문 발견")
                    
                    if orders:
                        all_found_orders.extend(orders)
                        logger.info(f"🎯 {endpoint}에서 발견: {len(orders)}개 주문")
                        
                        # 발견된 주문들 상세 로깅
                        for i, order in enumerate(orders):
                            if order is None:
                                continue
                            
                            order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
                            order_type = order.get('orderType', order.get('planType', 'unknown'))
                            side = order.get('side', order.get('tradeSide', 'unknown'))
                            trigger_price = order.get('triggerPrice', order.get('executePrice', 'unknown'))
                            size = order.get('size', order.get('volume', 'unknown'))
                            
                            logger.info(f"  📝 V1 주문 {i+1}: ID={order_id}, 타입={order_type}, 방향={side}, 크기={size}, 트리거가={trigger_price}")
                        
                        # 첫 번째 성공한 엔드포인트에서 주문을 찾았으면 종료
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
                    logger.debug(f"📝 V1 고유 예약 주문 추가: {order_id}")
            
            logger.info(f"🔥 V1 API에서 최종 발견된 고유한 예약 주문: {len(unique_orders)}건")
            return unique_orders
            
        except Exception as e:
            logger.error(f"V1 예약 주문 조회 실패: {e}")
            return []
    
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
                logger.debug(f"📝 최종 고유 예약 주문 추가: {order_id}")
        
        logger.info(f"🔥 최종 발견된 고유한 트리거 주문: {len(unique_orders)}건")
        
        # 수정: 예약 주문이 없을 때 경고 로그 제거
        if unique_orders:
            logger.info("📋 발견된 예약 주문 목록:")
            for i, order in enumerate(unique_orders, 1):
                order_id = order.get('orderId', order.get('planOrderId', order.get('id', 'unknown')))
                side = order.get('side', order.get('tradeSide', 'unknown'))
                trigger_price = order.get('triggerPrice', order.get('executePrice', order.get('price', 'unknown')))
                size = order.get('size', order.get('volume', 'unknown'))
                order_type = order.get('orderType', order.get('planType', order.get('type', 'unknown')))
                logger.info(f"  {i}. ID: {order_id}, 방향: {side}, 수량: {size}, 트리거가: {trigger_price}, 타입: {order_type}")
        else:
            # WARNING → DEBUG로 변경하여 빨간 로그 제거
            logger.debug("📝 현재 예약 주문이 없습니다.")
        
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
            logger.error(f"플랜 주문 조회 실패, 빈 리스트 반환: {e}")
            return []
    
    async def get_all_plan_orders_with_tp_sl(self, symbol: str = None) -> Dict:
        """모든 플랜 주문과 TP/SL 조회 - 개선된 분류"""
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"🔍 모든 예약 주문 및 TP/SL 조회 시작: {symbol}")
            
            # 모든 트리거 주문 조회 (개선된 방식)
            all_orders = await self.get_all_trigger_orders(symbol)
            
            # TP/SL과 일반 예약주문 분류
            tp_sl_orders = []
            plan_orders = []
            
            for order in all_orders:
                if order is None:
                    continue
                    
                is_tp_sl = False
                
                # TP/SL 분류 조건들
                if (order.get('planType') == 'profit_loss' or 
                    order.get('isPlan') == 'profit_loss' or
                    order.get('side') in ['close_long', 'close_short'] or
                    order.get('tradeSide') in ['close_long', 'close_short'] or
                    order.get('reduceOnly') == True or
                    order.get('reduceOnly') == 'true'):
                    is_tp_sl = True
                
                # TP/SL 가격이 설정된 경우도 확인
                elif (order.get('presetStopSurplusPrice') or 
                      order.get('presetStopLossPrice')):
                    # 이 경우는 일반 주문에 TP/SL이 설정된 것이므로 plan_orders로 분류
                    pass
                
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
            
            # 각 카테고리별 상세 로깅
            if plan_orders:
                logger.info("📈 일반 예약 주문 목록:")
                for i, order in enumerate(plan_orders, 1):
                    order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
                    side = order.get('side', order.get('tradeSide', 'unknown'))
                    price = order.get('price', order.get('triggerPrice', 'unknown'))
                    tp_price = order.get('presetStopSurplusPrice', '')
                    sl_price = order.get('presetStopLossPrice', '')
                    logger.info(f"  {i}. ID: {order_id}, 방향: {side}, 가격: {price}")
                    if tp_price:
                        logger.info(f"     TP 설정: {tp_price}")
                    if sl_price:
                        logger.info(f"     SL 설정: {sl_price}")
            
            if tp_sl_orders:
                logger.info("📊 TP/SL 주문 목록:")
                for i, order in enumerate(tp_sl_orders, 1):
                    order_id = order.get('orderId', order.get('planOrderId', 'unknown'))
                    side = order.get('side', order.get('tradeSide', 'unknown'))
                    trigger_price = order.get('triggerPrice', 'unknown')
                    logger.info(f"  {i}. ID: {order_id}, 방향: {side}, 트리거가: {trigger_price}")
            
            return result
            
        except Exception as e:
            logger.error(f"전체 플랜 주문 조회 실패: {e}")
            return {
                'plan_orders': [],
                'tp_sl_orders': [],
                'total_count': 0,
                'error': str(e)
            }
    
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
    
    async def get_account_bills_v2_corrected(self, start_time: int = None, end_time: int = None, 
                                           business_type: str = None, limit: int = 100,
                                           next_id: str = None) -> List[Dict]:
        """V2 Account Bills 수정된 방식 - businessType 파라미터 조정"""
        
        # businessType error가 발생한 엔드포인트를 다른 방식으로 시도
        working_endpoint = "/api/v2/mix/account/bill"
        
        # businessType 파라미터를 다양한 방식으로 시도
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
        
        # 모든 businessType variant가 실패한 경우, V1 API 시도
        logger.info("🔄 V2 실패, V1 Account Bills 시도")
        return await self.get_account_bills_v1_fallback(start_time, end_time, business_type, limit, next_id)
    
    async def get_account_bills_v1_fallback(self, start_time: int = None, end_time: int = None, 
                                          business_type: str = None, limit: int = 100,
                                          next_id: str = None) -> List[Dict]:
        """V1 Account Bills 폴백 (V2가 모두 실패할 때)"""
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
            logger.error(
