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
            logger.info(f"API 요청: {method} {url}")
            async with self.session.request(method, url, headers=headers, data=body) as response:
                response_text = await response.text()
                logger.info(f"API 응답 상태: {response.status}")
                logger.debug(f"API 응답 내용: {response_text[:500]}")
                
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
    
    async def get_plan_orders_v2_comprehensive(self, symbol: str = None) -> List[Dict]:
        """🔥🔥🔥 V2 API로 예약 주문 조회 - 완전 개선된 다중 엔드포인트 시도"""
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"🔍🔍 V2 API 예약 주문 포괄적 조회 시작: {symbol}")
            
            all_found_orders = []
            
            # 🔥🔥🔥 V2 API 예약 주문 전용 엔드포인트들
            v2_endpoints = [
                # 주요 예약 주문 엔드포인트들
                "/api/v2/mix/plan/orders-pending",           # V2 예약 주문 전용
                "/api/v2/mix/plan/currentPlan",              # V2 현재 예약 주문
                "/api/v2/mix/plan/orders-plan-pending",      # V2 플랜 주문 대기
                "/api/v2/mix/order/orders-pending",          # V2 일반 대기 주문 (예약 주문 포함 가능)
                "/api/v2/mix/trigger/orders-pending",        # V2 트리거 주문
                "/api/v2/mix/plan/pending",                  # V2 예약 대기
                
                # 추가 가능한 엔드포인트들
                "/api/v2/mix/order/plan-orders",             # V2 계획 주문
                "/api/v2/mix/order/trigger-orders",          # V2 트리거 주문
                "/api/v2/mix/plan/trigger-pending",          # V2 트리거 대기
                "/api/v2/mix/plan/list",                     # V2 예약 주문 리스트
            ]
            
            for endpoint in v2_endpoints:
                try:
                    params = {
                        'symbol': symbol,
                        'productType': 'USDT-FUTURES'
                    }
                    
                    logger.info(f"🔍 V2 예약 주문 조회 시도: {endpoint}")
                    response = await self._request('GET', endpoint, params=params)
                    
                    if response is None:
                        logger.info(f"{endpoint}: 응답이 None")
                        continue
                    
                    # 응답에서 주문 목록 추출
                    orders = []
                    if isinstance(response, dict):
                        # 다양한 필드명 시도
                        for field_name in ['entrustedList', 'orderList', 'planList', 'data', 'list', 'pending', 'orders', 'planOrders']:
                            if field_name in response:
                                orders_raw = response[field_name]
                                if orders_raw is None:
                                    continue
                                elif isinstance(orders_raw, list):
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
                            
                            order_id = order.get('orderId', order.get('planOrderId', order.get('id', 'unknown')))
                            order_type = order.get('orderType', order.get('planType', order.get('type', 'unknown')))
                            side = order.get('side', order.get('tradeSide', 'unknown'))
                            trigger_price = order.get('triggerPrice', order.get('executePrice', order.get('price', 'unknown')))
                            size = order.get('size', order.get('volume', 'unknown'))
                            
                            logger.info(f"  📝 주문 {i+1}: ID={order_id}, 타입={order_type}, 방향={side}, 크기={size}, 트리거가={trigger_price}")
                        
                        # 주문을 찾았으므로 해당 엔드포인트에서 성공
                        logger.info(f"🎯🎯 성공한 엔드포인트: {endpoint} - {len(orders)}개 예약 주문 발견")
                        break
                    else:
                        logger.info(f"{endpoint}: 주문이 없음")
                        
                except Exception as e:
                    logger.debug(f"{endpoint} 조회 실패: {e}")
                    continue
            
            # 🔥🔥 중복 제거
            seen = set()
            unique_orders = []
            for order in all_found_orders:
                if order is None:
                    continue
                    
                # 여러 ID 필드 확인
                order_id = (order.get('orderId') or 
                           order.get('planOrderId') or 
                           order.get('id') or
                           order.get('clientOid') or
                           str(order.get('cTime', '')))
                
                if order_id and order_id not in seen:
                    seen.add(order_id)
                    unique_orders.append(order)
                    logger.info(f"📝 V2 고유 예약 주문 추가: {order_id}")
            
            logger.info(f"🔥🔥 V2 API에서 최종 발견된 고유한 예약 주문: {len(unique_orders)}건")
            return unique_orders
            
        except Exception as e:
            logger.error(f"V2 예약 주문 포괄적 조회 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return []
    
    async def get_plan_orders_v1_comprehensive(self, symbol: str = None, plan_type: str = None) -> List[Dict]:
        """🔥🔥🔥 V1 API로 예약 주문 조회 - 완전 개선된 다중 엔드포인트 시도"""
        try:
            # V1 API는 다른 심볼 형식을 사용
            # BTCUSDT -> BTCUSDT_UMCBL
            symbol = symbol or self.config.symbol
            v1_symbol = f"{symbol}_UMCBL"
            
            logger.info(f"🔍🔍 V1 API 예약 주문 포괄적 조회 시작: {v1_symbol}")
            
            all_found_orders = []
            
            # 🔥🔥🔥 V1 API 예약 주문 엔드포인트들
            v1_endpoints = [
                # 주요 V1 예약 주문 엔드포인트들
                "/api/mix/v1/plan/currentPlan",              # V1 현재 예약 주문
                "/api/mix/v1/plan/pendingOrders",            # V1 대기 주문
                "/api/mix/v1/plan/planOrders",               # V1 계획 주문
                "/api/mix/v1/order/plan-orders",             # V1 주문 계획
                "/api/mix/v1/trigger/currentTrigger",        # V1 현재 트리거
                "/api/mix/v1/plan/orders",                   # V1 예약 주문들
                
                # TP/SL 전용 엔드포인트들
                "/api/mix/v1/plan/profit-loss",              # V1 손익 계획
                "/api/mix/v1/plan/stopPlan",                 # V1 스탑 계획
                "/api/mix/v1/order/profit-loss-orders",      # V1 손익 주문들
            ]
            
            for endpoint in v1_endpoints:
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
                    
                    logger.info(f"🔍 V1 예약 주문 조회 시도: {endpoint}")
                    response = await self._request('GET', endpoint, params=params)
                    
                    if response is None:
                        logger.info(f"{endpoint}: 응답이 None")
                        continue
                    
                    # 응답에서 주문 목록 추출
                    orders = []
                    if isinstance(response, dict):
                        # V1 API 특성상 다양한 필드명들
                        for field_name in ['list', 'data', 'orderList', 'planList', 'orders', 'planOrders', 'pending', 'currentPlan']:
                            if field_name in response:
                                orders_raw = response[field_name]
                                if orders_raw is None:
                                    continue
                                elif isinstance(orders_raw, list):
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
                            
                            order_id = order.get('orderId', order.get('planOrderId', order.get('id', 'unknown')))
                            order_type = order.get('orderType', order.get('planType', order.get('type', 'unknown')))
                            side = order.get('side', order.get('tradeSide', 'unknown'))
                            trigger_price = order.get('triggerPrice', order.get('executePrice', order.get('price', 'unknown')))
                            size = order.get('size', order.get('volume', 'unknown'))
                            
                            logger.info(f"  📝 V1 주문 {i+1}: ID={order_id}, 타입={order_type}, 방향={side}, 크기={size}, 트리거가={trigger_price}")
                        
                        # 주문을 찾았으므로 다른 엔드포인트는 시도하지 않고 종료 (첫 번째 성공한 곳만 사용)
                        logger.info(f"🎯🎯 V1 성공한 엔드포인트: {endpoint} - {len(orders)}개 예약 주문 발견")
                        break
                    else:
                        logger.info(f"{endpoint}: 주문이 없음")
                        
                except Exception as e:
                    logger.debug(f"{endpoint} 조회 실패: {e}")
                    continue
            
            # 🔥🔥 중복 제거
            seen = set()
            unique_orders = []
            for order in all_found_orders:
                if order is None:
                    continue
                    
                # 여러 ID 필드 확인
                order_id = (order.get('orderId') or 
                           order.get('planOrderId') or 
                           order.get('id') or
                           order.get('clientOid') or
                           str(order.get('cTime', '')))
                
                if order_id and order_id not in seen:
                    seen.add(order_id)
                    unique_orders.append(order)
                    logger.info(f"📝 V1 고유 예약 주문 추가: {order_id}")
            
            logger.info(f"🔥🔥 V1 API에서 최종 발견된 고유한 예약 주문: {len(unique_orders)}건")
            return unique_orders
            
        except Exception as e:
            logger.error(f"V1 예약 주문 포괄적 조회 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return []
    
    async def get_plan_orders_v1(self, symbol: str = None, plan_type: str = None) -> List[Dict]:
        """플랜 주문 조회 - V1 API (기존 방식도 유지)"""
        return await self.get_plan_orders_v1_comprehensive(symbol, plan_type)
    
    async def get_plan_orders_v2_pending(self, symbol: str = None) -> List[Dict]:
        """V2 API로 대기중인 전체 주문 조회하여 예약 주문 필터링 (기존 방식도 유지)"""
        return await self.get_plan_orders_v2_comprehensive(symbol)
    
    async def get_all_trigger_orders(self, symbol: str = None) -> List[Dict]:
        """🔥🔥🔥 모든 트리거 주문 조회 - 완전 개선된 버전 (V1 + V2 포괄적 조회)"""
        all_orders = []
        symbol = symbol or self.config.symbol
        
        logger.info(f"🔍🔍🔍 모든 트리거 주문 완전 포괄적 조회 시작: {symbol}")
        
        # 🔥🔥🔥 1. V2 API 포괄적 조회 (우선)
        try:
            v2_orders = await self.get_plan_orders_v2_comprehensive(symbol)
            if v2_orders:
                all_orders.extend(v2_orders)
                logger.info(f"✅ V2 포괄적 조회에서 {len(v2_orders)}개 예약 주문 발견")
            else:
                logger.info("⚠️ V2 포괄적 조회에서 예약 주문을 찾지 못함")
        except Exception as e:
            logger.warning(f"V2 포괄적 예약 주문 조회 실패: {e}")
        
        # 🔥🔥🔥 2. V1 API 포괄적 조회
        try:
            v1_orders = await self.get_plan_orders_v1_comprehensive(symbol)
            if v1_orders:
                all_orders.extend(v1_orders)
                logger.info(f"✅ V1 포괄적 조회에서 {len(v1_orders)}개 예약 주문 발견")
        except Exception as e:
            logger.warning(f"V1 포괄적 예약 주문 조회 실패: {e}")
        
        # 🔥🔥🔥 3. V1 TP/SL 전용 조회
        try:
            v1_tp_sl = await self.get_plan_orders_v1_comprehensive(symbol, 'profit_loss')
            if v1_tp_sl:
                all_orders.extend(v1_tp_sl)
                logger.info(f"✅ V1 TP/SL에서 {len(v1_tp_sl)}개 주문 발견")
        except Exception as e:
            logger.warning(f"V1 TP/SL 주문 조회 실패: {e}")
        
        # 🔥🔥🔥 중복 제거 (더 정확한 ID 매칭)
        seen = set()
        unique_orders = []
        for order in all_orders:
            if order is None:
                continue
                
            # 여러 ID 필드 확인
            order_id = (order.get('orderId') or 
                       order.get('planOrderId') or 
                       order.get('id') or
                       order.get('clientOid') or
                       str(order.get('cTime', '')))
            
            if order_id and order_id not in seen:
                seen.add(order_id)
                unique_orders.append(order)
                logger.info(f"📝 최종 고유 예약 주문 추가: {order_id}")
        
        logger.info(f"🔥🔥🔥 최종 발견된 고유한 트리거 주문: {len(unique_orders)}건")
        
        # 🔥🔥🔥 발견된 주문들의 상세 정보 로깅
        if unique_orders:
            logger.info("📋📋📋 발견된 예약 주문 목록:")
            for i, order in enumerate(unique_orders, 1):
                order_id = order.get('orderId', order.get('planOrderId', order.get('id', 'unknown')))
                side = order.get('side', order.get('tradeSide', 'unknown'))
                trigger_price = order.get('triggerPrice', order.get('executePrice', order.get('price', 'unknown')))
                size = order.get('size', order.get('volume', 'unknown'))
                order_type = order.get('orderType', order.get('planType', order.get('type', 'unknown')))
                logger.info(f"  {i}. ID: {order_id}, 방향: {side}, 수량: {size}, 트리거가: {trigger_price}, 타입: {order_type}")
        else:
            logger.warning("⚠️⚠️⚠️ 모든 API 조회에서 예약 주문을 전혀 찾지 못했습니다!")
            logger.warning("가능한 원인:")
            logger.warning("1. 예약 주문이 실제로 없음")
            logger.warning("2. API 엔드포인트가 변경됨") 
            logger.warning("3. 심볼 형식이 잘못됨")
            logger.warning("4. API 권한 문제")
            logger.warning("5. 예약 주문이 다른 상태 (체결 대기가 아님)")
        
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
        """🔥🔥🔥 모든 플랜 주문과 TP/SL 조회 - 완전 개선된 분류"""
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"🔍🔍🔍 모든 예약 주문 및 TP/SL 포괄적 조회 시작: {symbol}")
            
            # 모든 트리거 주문 조회 (완전 개선된 방식)
            all_orders = await self.get_all_trigger_orders(symbol)
            
            # TP/SL과 일반 예약주문 분류 (더 정확한 분류)
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
                    # 하지만 별도로 TP/SL 정보를 추출할 수 있음
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
            
            logger.info(f"🔥🔥🔥 전체 예약 주문 분류 완료: 일반 {len(plan_orders)}건 + TP/SL {len(tp_sl_orders)}건 = 총 {result['total_count']}건")
            
            # 각 카테고리별 상세 로깅
            if plan_orders:
                logger.info("📈📈📈 일반 예약 주문 목록:")
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
                logger.info("📊📊📊 TP/SL 주문 목록:")
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
    
    async def get_account_bills(self, start_time: int = None, end_time: int = None, 
                               business_type: str = None, limit: int = 100,
                               next_id: str = None) -> List[Dict]:
        """계정 거래 내역 조회 (Account Bills)"""
        endpoint = "/api/v2/mix/account/bills"
        params = {
            'productType': 'USDT-FUTURES',
            'marginCoin': 'USDT'
        }
        
        if start_time:
            params['startTime'] = str(start_time)
        if end_time:
            params['endTime'] = str(end_time)
        if business_type:
            params['businessType'] = business_type  # 'contract_settle' for realized PnL
        if limit:
            params['limit'] = str(min(limit, 100))
        if next_id:
            params['startId'] = str(next_id)
        
        try:
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list):
                return response
            elif isinstance(response, dict):
                # 페이징 정보가 있는 경우
                return response.get('billsList', response.get('bills', []))
            return []
            
        except Exception as e:
            logger.error(f"계정 내역 조회 실패: {e}")
            return []
    
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
            
            # 🔥 방법 1: Account Bills 기반 조회 (가장 신뢰도 높음)
            bills_result = await self._get_profit_from_account_bills(start_timestamp, end_timestamp, period_start, days)
            
            # 🔥 방법 2: 거래 내역 기반 조회 (보조 검증용)
            fills_result = await self._get_profit_from_fills(symbol, start_timestamp, end_timestamp, period_start, days)
            
            # 🔥 방법 3: achievedProfits 기반 (포지션 수익)
            achieved_result = await self._get_achieved_profits()
            
            # 🔥 결과 비교 및 최적 값 선택
            final_result = self._select_best_profit_data(bills_result, fills_result, achieved_result, days)
            
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
    
    async def _get_profit_from_account_bills(self, start_timestamp: int, end_timestamp: int, 
                                           period_start: datetime, days: int) -> Dict:
        """Account Bills에서 손익 추출"""
        try:
            logger.info("🔥 Account Bills 기반 손익 조회 시작")
            
            kst = pytz.timezone('Asia/Seoul')
            
            # 모든 손익 관련 Bills 조회
            all_bills = []
            next_id = None
            page = 0
            
            # contract_settle (실현 손익)
            settle_bills = await self._get_all_bills_with_paging(
                start_timestamp, end_timestamp, 'contract_settle'
            )
            all_bills.extend(settle_bills)
            logger.info(f"실현 손익 Bills: {len(settle_bills)}건")
            
            # fee (수수료)
            fee_bills = await self._get_all_bills_with_paging(
                start_timestamp, end_timestamp, 'contract_fee'
            )
            all_bills.extend(fee_bills)
            logger.info(f"수수료 Bills: {len(fee_bills)}건")
            
            # funding (펀딩비)
            funding_bills = await self._get_all_bills_with_paging(
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
                    
                    if business_type == 'contract_settle':
                        daily_data[bill_date_str]['pnl'] += amount
                        daily_data[bill_date_str]['trades'] += 1
                        total_pnl += amount
                        trade_count += 1
                    elif business_type == 'contract_fee':
                        daily_data[bill_date_str]['fees'] += abs(amount)
                        total_fees += abs(amount)
                    elif business_type == 'contract_funding_fee':
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
            
            return {
                'total_pnl': total_pnl,
                'daily_pnl': daily_pnl,
                'days': days,
                'average_daily': total_pnl / days if days > 0 else 0,
                'trade_count': trade_count,
                'total_fees': total_fees,
                'source': 'account_bills',
                'confidence': 'high'
            }
            
        except Exception as e:
            logger.error(f"Account Bills 손익 조회 실패: {e}")
            return {
                'total_pnl': 0, 'daily_pnl': {}, 'days': days,
                'average_daily': 0, 'trade_count': 0, 'total_fees': 0,
                'source': 'account_bills_error', 'confidence': 'low'
            }
    
    async def _get_all_bills_with_paging(self, start_timestamp: int, end_timestamp: int, 
                                       business_type: str) -> List[Dict]:
        """페이징을 통한 모든 Bills 조회"""
        all_bills = []
        next_id = None
        page = 0
        
        while page < 20:  # 최대 20페이지
            bills = await self.get_account_bills(
                start_time=start_timestamp,
                end_time=end_timestamp,
                business_type=business_type,
                limit=100,
                next_id=next_id
            )
            
            if not bills:
                break
            
            all_bills.extend(bills)
            
            if len(bills) < 100:
                break
            
            # 다음 페이지 ID
            last_bill = bills[-1]
            next_id = last_bill.get('billId', last_bill.get('id'))
            if not next_id:
                break
            
            page += 1
            await asyncio.sleep(0.1)
        
        logger.info(f"{business_type} Bills 총 {len(all_bills)}건 조회")
        return all_bills
    
    async def _get_profit_from_fills(self, symbol: str, start_timestamp: int, end_timestamp: int,
                                   period_start: datetime, days: int) -> Dict:
        """거래 내역(Fills)에서 손익 추출"""
        try:
            logger.info("🔥 거래 내역(Fills) 기반 손익 조회 시작")
            
            kst = pytz.timezone('Asia/Seoul')
            
            # 모든 거래 내역 조회
            all_fills = await self._get_enhanced_fills(symbol, start_timestamp, end_timestamp)
            
            logger.info(f"조회된 총 거래 수: {len(all_fills)}건")
            
            # 중복 제거 (강화된 로직)
            unique_fills = self._remove_duplicate_fills(all_fills)
            logger.info(f"중복 제거 후: {len(unique_fills)}건")
            
            # 날짜별 분석
            daily_pnl = {}
            total_pnl = 0
            total_fees = 0
            trade_count = 0
            
            for fill in unique_fills:
                try:
                    # 시간 추출
                    fill_time = None
                    for time_field in ['cTime', 'createdTime', 'createTime', 'time']:
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
                    
                    # 손익 추출
                    profit = 0.0
                    for profit_field in ['profit', 'realizedPL', 'realizedPnl', 'pnl']:
                        if profit_field in fill and fill[profit_field]:
                            try:
                                profit = float(fill[profit_field])
                                break
                            except:
                                continue
                    
                    # 수수료 추출
                    fee = self._extract_fee_from_fill(fill)
                    
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
                'source': 'trade_fills',
                'confidence': 'medium'
            }
            
        except Exception as e:
            logger.error(f"거래 내역 손익 조회 실패: {e}")
            return {
                'total_pnl': 0, 'daily_pnl': {}, 'days': days,
                'average_daily': 0, 'trade_count': 0, 'total_fees': 0,
                'source': 'fills_error', 'confidence': 'low'
            }
    
    async def _get_enhanced_fills(self, symbol: str, start_timestamp: int, end_timestamp: int) -> List[Dict]:
        """향상된 거래 내역 조회"""
        all_fills = []
        
        # 7일씩 나눠서 조회
        current_start = start_timestamp
        
        while current_start < end_timestamp:
            current_end = min(current_start + (7 * 24 * 60 * 60 * 1000), end_timestamp)
            
            # 해당 기간 조회
            period_fills = await self._get_period_fills_enhanced(symbol, current_start, current_end)
            all_fills.extend(period_fills)
            
            current_start = current_end
            await asyncio.sleep(0.2)
        
        return all_fills
    
    async def _get_period_fills_enhanced(self, symbol: str, start_time: int, end_time: int) -> List[Dict]:
        """특정 기간의 거래 내역 조회 (향상된 버전)"""
        all_fills = []
        
        # 다양한 엔드포인트 시도
        endpoints = [
            "/api/v2/mix/order/fill-history",
            "/api/v2/mix/order/fills"
        ]
        
        for endpoint in endpoints:
            try:
                fills = await self._get_fills_from_endpoint(endpoint, symbol, start_time, end_time)
                if fills:
                    all_fills.extend(fills)
                    logger.info(f"{endpoint}: {len(fills)}건 조회")
                    break  # 성공하면 다른 엔드포인트는 시도하지 않음
            except Exception as e:
                logger.debug(f"{endpoint} 실패: {e}")
                continue
        
        return all_fills
    
    async def _get_fills_from_endpoint(self, endpoint: str, symbol: str, 
                                     start_time: int, end_time: int) -> List[Dict]:
        """특정 엔드포인트에서 거래 내역 조회 (페이징 포함)"""
        all_fills = []
        last_id = None
        page = 0
        
        while page < 10:  # 최대 10페이지
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES',
                'startTime': str(start_time),
                'endTime': str(end_time),
                'limit': '500'
            }
            
            if last_id:
                params['lastEndId'] = str(last_id)
            
            try:
                response = await self._request('GET', endpoint, params=params)
                
                fills = []
                if isinstance(response, dict):
                    fills = response.get('fillList', response.get('list', response.get('data', [])))
                elif isinstance(response, list):
                    fills = response
                
                if not fills:
                    break
                
                all_fills.extend(fills)
                
                if len(fills) < 500:
                    break
                
                # 다음 페이지 ID
                last_fill = fills[-1]
                new_last_id = self._get_enhanced_fill_id(last_fill)
                
                if not new_last_id or new_last_id == last_id:
                    break
                
                last_id = new_last_id
                page += 1
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"페이지 {page + 1} 조회 오류: {e}")
                break
        
        return all_fills
    
    def _get_enhanced_fill_id(self, fill: Dict) -> Optional[str]:
        """향상된 거래 ID 추출"""
        for field in ['fillId', 'id', 'tradeId', 'orderId', 'cTime']:
            if field in fill and fill[field]:
                return str(fill[field])
        return None
    
    def _remove_duplicate_fills(self, fills: List[Dict]) -> List[Dict]:
        """향상된 중복 제거"""
        seen = set()
        unique_fills = []
        
        for fill in fills:
            # 다중 키 기반 중복 체크
            fill_id = self._get_enhanced_fill_id(fill)
            
            # 추가 중복 체크 키 생성
            time_key = str(fill.get('cTime', ''))
            size_key = str(fill.get('size', ''))
            price_key = str(fill.get('price', ''))
            composite_key = f"{fill_id}_{time_key}_{size_key}_{price_key}"
            
            if composite_key not in seen:
                seen.add(composite_key)
                unique_fills.append(fill)
            else:
                logger.debug(f"중복 제거: {fill_id}")
        
        return unique_fills
    
    def _extract_fee_from_fill(self, fill: Dict) -> float:
        """거래에서 수수료 추출"""
        fee = 0.0
        
        # feeDetail 확인
        fee_detail = fill.get('feeDetail', [])
        if isinstance(fee_detail, list):
            for fee_info in fee_detail:
                if isinstance(fee_info, dict):
                    fee += abs(float(fee_info.get('totalFee', 0)))
        
        # 다른 수수료 필드들 확인
        if fee == 0:
            for fee_field in ['fee', 'fees', 'totalFee']:
                if fee_field in fill and fill[fee_field]:
                    try:
                        fee = abs(float(fill[fee_field]))
                        break
                    except:
                        continue
        
        return fee
    
    async def _get_achieved_profits(self) -> Dict:
        """포지션에서 achievedProfits 조회"""
        try:
            logger.info("🔥 achievedProfits 조회 시작")
            
            positions = await self.get_positions()
            achieved_profits = 0
            position_open_time = None
            
            for pos in positions:
                achieved = float(pos.get('achievedProfits', 0))
                if achieved != 0:
                    achieved_profits = achieved
                    ctime = pos.get('cTime')
                    if ctime:
                        kst = pytz.timezone('Asia/Seoul')
                        position_open_time = datetime.fromtimestamp(int(ctime)/1000, tz=kst)
                    break
            
            return {
                'total_pnl': achieved_profits,
                'position_open_time': position_open_time,
                'source': 'achieved_profits',
                'confidence': 'medium' if achieved_profits > 0 else 'low'
            }
            
        except Exception as e:
            logger.error(f"achievedProfits 조회 실패: {e}")
            return {
                'total_pnl': 0,
                'position_open_time': None,
                'source': 'achieved_error',
                'confidence': 'low'
            }
    
    def _select_best_profit_data(self, bills_result: Dict, fills_result: Dict, 
                               achieved_result: Dict, days: int) -> Dict:
        """최적의 손익 데이터 선택"""
        
        logger.info("🔥 손익 데이터 비교 및 선택")
        logger.info(f"   - Account Bills: ${bills_result['total_pnl']:.2f} (신뢰도: {bills_result['confidence']})")
        logger.info(f"   - Trade Fills: ${fills_result['total_pnl']:.2f} (신뢰도: {fills_result['confidence']})")
        logger.info(f"   - Achieved Profits: ${achieved_result['total_pnl']:.2f} (신뢰도: {achieved_result['confidence']})")
        
        # 1순위: Account Bills (가장 정확함)
        if bills_result['confidence'] == 'high' and bills_result['total_pnl'] != 0:
            logger.info("✅ Account Bills 선택 (가장 신뢰도 높음)")
            bills_result['source'] = 'account_bills_verified'
            return bills_result
        
        # 2순위: Trade Fills (중간 신뢰도)
        if fills_result['confidence'] == 'medium' and fills_result['total_pnl'] != 0:
            logger.info("✅ Trade Fills 선택 (중간 신뢰도)")
            fills_result['source'] = 'trade_fills_verified'
            return fills_result
        
        # 3순위: Achieved Profits (포지션 기반)
        if achieved_result['total_pnl'] != 0:
            logger.info("✅ Achieved Profits 선택 (포지션 기반)")
            return {
                'total_pnl': achieved_result['total_pnl'],
                'daily_pnl': {},
                'days': days,
                'average_daily': achieved_result['total_pnl'] / days,
                'trade_count': 0,
                'total_fees': 0,
                'source': 'achieved_profits_fallback',
                'confidence': 'medium'
            }
        
        # 마지막: Account Bills (데이터가 있으면)
        if bills_result['total_pnl'] != 0 or bills_result['trade_count'] > 0:
            logger.info("✅ Account Bills 선택 (폴백)")
            bills_result['source'] = 'account_bills_fallback'
            return bills_result
        
        # 최종 폴백: Trade Fills
        logger.info("⚠️ Trade Fills 선택 (최종 폴백)")
        fills_result['source'] = 'trade_fills_fallback'
        return fills_result
    
    async def get_profit_loss_history_v2(self, symbol: str = None, days: int = 7) -> Dict:
        """손익 내역 조회 - Account Bills 사용"""
        try:
            symbol = symbol or self.config.symbol
            
            # KST 기준 현재 시간
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 조회 기간 설정
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_start = today_start - timedelta(days=days-1)
            period_end = now
            
            # UTC로 변환
            start_time_utc = period_start.astimezone(pytz.UTC)
            end_time_utc = period_end.astimezone(pytz.UTC)
            
            start_time = int(start_time_utc.timestamp() * 1000)
            end_time = int(end_time_utc.timestamp() * 1000)
            
            logger.info(f"=== {days}일 손익 조회 (Account Bills) ===")
            logger.info(f"기간: {period_start.strftime('%Y-%m-%d %H:%M')} ~ {period_end.strftime('%Y-%m-%d %H:%M')} (KST)")
            
            # 모든 계정 내역 조회
            all_bills = []
            next_id = None
            page = 0
            
            while page < 50:  # 최대 50페이지
                bills = await self.get_account_bills(
                    start_time=start_time,
                    end_time=end_time,
                    business_type='contract_settle',  # 실현 손익만
                    limit=100,
                    next_id=next_id
                )
                
                if not bills:
                    break
                
                all_bills.extend(bills)
                logger.info(f"페이지 {page + 1}: {len(bills)}건 조회 (누적 {len(all_bills)}건)")
                
                if len(bills) < 100:
                    break
                
                # 다음 페이지
                last_bill = bills[-1]
                next_id = last_bill.get('billId', last_bill.get('id'))
                if not next_id:
                    break
                    
                page += 1
                await asyncio.sleep(0.1)
            
            # 날짜별 손익 계산
            daily_pnl = {}
            total_pnl = 0.0
            total_fees = 0.0
            trade_count = 0
            
            for bill in all_bills:
                try:
                    # 시간
                    bill_time = int(bill.get('cTime', 0))
                    if not bill_time:
                        continue
                    
                    bill_date_kst = datetime.fromtimestamp(bill_time / 1000, tz=kst)
                    bill_date_str = bill_date_kst.strftime('%Y-%m-%d')
                    
                    # 금액
                    amount = float(bill.get('amount', 0))
                    
                    # 손익인 경우만 처리
                    business_type = bill.get('businessType', '')
                    if business_type == 'contract_settle' and amount != 0:
                        if bill_date_str not in daily_pnl:
                            daily_pnl[bill_date_str] = 0
                        
                        daily_pnl[bill_date_str] += amount
                        total_pnl += amount
                        trade_count += 1
                        
                        logger.debug(f"손익: {bill_date_str} - ${amount:.2f}")
                    
                except Exception as e:
                    logger.warning(f"계정 내역 파싱 오류: {e}")
                    continue
            
            # 수수료는 별도 조회 필요 (trade fills에서)
            # 여기서는 손익만 계산
            
            logger.info(f"\n=== 일별 손익 내역 (Account Bills) ===")
            for date, pnl in sorted(daily_pnl.items()):
                logger.info(f"{date}: ${pnl:,.2f}")
            
            logger.info(f"\n=== {days}일 총 손익: ${total_pnl:,.2f} (거래 {trade_count}건) ===")
            
            return {
                'total_pnl': total_pnl,
                'daily_pnl': daily_pnl,
                'days': days,
                'average_daily': total_pnl / days if days > 0 else 0,
                'trade_count': trade_count,
                'total_fees': 0  # 수수료는 별도 계산 필요
            }
            
        except Exception as e:
            logger.error(f"손익 내역 조회 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'days': days,
                'average_daily': 0,
                'trade_count': 0,
                'total_fees': 0,
                'error': str(e)
            }
    
    async def get_trade_fills(self, symbol: str = None, start_time: int = None, end_time: int = None, limit: int = 100) -> List[Dict]:
        """거래 체결 내역 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        
        if start_time and end_time:
            max_days = 7
            time_diff = end_time - start_time
            max_time_diff = max_days * 24 * 60 * 60 * 1000
            
            if time_diff > max_time_diff:
                start_time = end_time - max_time_diff
                logger.info(f"7일 제한으로 조정: {datetime.fromtimestamp(start_time/1000)} ~ {datetime.fromtimestamp(end_time/1000)}")
        
        return await self._get_fills_batch(symbol, start_time, end_time, min(limit, 500))
    
    async def _get_fills_batch(self, symbol: str, start_time: int = None, end_time: int = None, limit: int = 100, last_id: str = None) -> List[Dict]:
        """거래 체결 내역 배치 조회"""
        endpoints = ["/api/v2/mix/order/fill-history", "/api/v2/mix/order/fills"]
        
        for endpoint in endpoints:
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'
            }
            
            if start_time:
                params['startTime'] = str(start_time)
            if end_time:
                params['endTime'] = str(end_time)
            if limit:
                params['limit'] = str(limit)
            if last_id:
                params['lastEndId'] = str(last_id)
            
            try:
                response = await self._request('GET', endpoint, params=params)
                
                fills = []
                if isinstance(response, dict):
                    if 'fillList' in response:
                        fills = response['fillList']
                    elif 'fills' in response:
                        fills = response['fills']
                    elif 'list' in response:
                        fills = response['list']
                    elif 'data' in response and isinstance(response['data'], list):
                        fills = response['data']
                elif isinstance(response, list):
                    fills = response
                
                if fills:
                    logger.info(f"{endpoint} 거래 내역 조회 성공: {len(fills)}건")
                    return fills
                    
            except Exception as e:
                logger.debug(f"{endpoint} 조회 실패: {e}")
                continue
        
        return []
    
    async def get_profit_loss_history(self, symbol: str = None, days: int = 7) -> Dict:
        """🔥🔥 개선된 손익 내역 조회 - 새로운 정확한 방식 사용"""
        return await self.get_enhanced_profit_history(symbol, days)
    
    async def _get_profit_loss_history_original(self, symbol: str = None, days: int = 7) -> Dict:
        """손익 내역 조회 - 기존 방식 (30일 조회 후 필터링)"""
        try:
            symbol = symbol or self.config.symbol
            
            # KST 기준 현재 시간
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 실제 필요한 기간
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_start = today_start - timedelta(days=days-1)
            period_end = now
            
            logger.info(f"=== {days}일 손익 조회 (기존 방식) ===")
            logger.info(f"실제 필요 기간: {period_start.strftime('%Y-%m-%d %H:%M')} ~ {period_end.strftime('%Y-%m-%d %H:%M')} (KST)")
            
            # 30일 데이터 조회 (안정적인 데이터 확보를 위해)
            base_days = 30
            extended_start = today_start - timedelta(days=base_days-1)
            
            # UTC로 변환
            start_time_utc = extended_start.astimezone(pytz.UTC)
            end_time_utc = now.astimezone(pytz.UTC)
            
            start_time = int(start_time_utc.timestamp() * 1000)
            end_time = int(end_time_utc.timestamp() * 1000)
            
            logger.info(f"30일 전체 조회: {extended_start.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}")
            
            # 모든 거래 내역 조회
            all_fills = await self._get_all_fills_comprehensive(symbol, start_time, end_time)
            
            logger.info(f"30일 동안 조회된 총 거래 수: {len(all_fills)}건")
            
            # 날짜별로 거래 분류
            trades_by_date = {}
            total_pnl = 0.0
            daily_pnl = {}
            total_fees = 0.0
            trade_count = 0
            
            # 모든 거래 처리
            for trade in all_fills:
                try:
                    # 시간 필드 찾기
                    trade_time = None
                    for time_field in ['cTime', 'createdTime', 'createTime', 'time']:
                        if time_field in trade:
                            trade_time = int(trade[time_field])
                            break
                    
                    if not trade_time:
                        continue
                    
                    # KST 기준 날짜
                    trade_date_kst = datetime.fromtimestamp(trade_time / 1000, tz=kst)
                    trade_date_str = trade_date_kst.strftime('%Y-%m-%d')
                    
                    # 손익 필드 찾기
                    profit = 0.0
                    for profit_field in ['profit', 'realizedPL', 'realizedPnl', 'pnl']:
                        if profit_field in trade:
                            val = trade[profit_field]
                            if val and str(val).replace('.', '').replace('-', '').isdigit():
                                profit = float(val)
                                break
                    
                    # 수수료 계산
                    fee = 0.0
                    
                    # feeDetail 확인
                    fee_detail = trade.get('feeDetail', [])
                    if isinstance(fee_detail, list):
                        for fee_info in fee_detail:
                            if isinstance(fee_info, dict):
                                fee += abs(float(fee_info.get('totalFee', 0)))
                    
                    # fee 필드 확인
                    if fee == 0 and 'fee' in trade:
                        fee = abs(float(trade.get('fee', 0)))
                    
                    # fees 필드 확인
                    if fee == 0 and 'fees' in trade:
                        fee = abs(float(trade.get('fees', 0)))
                    
                    # 거래 정보 저장
                    if trade_date_str not in trades_by_date:
                        trades_by_date[trade_date_str] = []
                    
                    trades_by_date[trade_date_str].append({
                        'time': trade_time,
                        'profit': profit,
                        'fee': fee,
                        'pnl': profit - fee
                    })
                    
                except Exception as e:
                    logger.warning(f"거래 파싱 오류: {e}")
                    continue
            
            # 필요한 기간의 데이터만 추출
            logger.info(f"\n=== {days}일 손익 계산 ===")
            for i in range(days):
                date = period_start + timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                
                if date_str in trades_by_date:
                    day_trades = trades_by_date[date_str]
                    day_pnl = sum(t['pnl'] for t in day_trades)
                    day_fees = sum(t['fee'] for t in day_trades)
                    
                    daily_pnl[date_str] = day_pnl
                    total_pnl += day_pnl
                    total_fees += day_fees
                    trade_count += len(day_trades)
                    
                    logger.info(f"{date_str}: ${day_pnl:,.2f} ({len(day_trades)}건, 수수료 ${day_fees:.2f})")
                else:
                    logger.info(f"{date_str}: 거래 없음")
            
            logger.info(f"\n=== {days}일 총 손익: ${total_pnl:,.2f} (거래 {trade_count}건, 수수료 ${total_fees:.2f}) ===")
            
            return {
                'total_pnl': total_pnl,
                'daily_pnl': daily_pnl,
                'days': days,
                'average_daily': total_pnl / days if days > 0 else 0,
                'trade_count': trade_count,
                'total_fees': total_fees
            }
            
        except Exception as e:
            logger.error(f"손익 내역 조회 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'days': days,
                'average_daily': 0,
                'trade_count': 0,
                'total_fees': 0,
                'error': str(e)
            }
    
    async def _get_all_fills_comprehensive(self, symbol: str, start_time: int, end_time: int) -> List[Dict]:
        """포괄적인 거래 내역 조회 - 7일씩 나눠서 조회"""
        all_fills = []
        seen_ids = set()
        
        # 7일씩 나눠서 조회
        current_start = start_time
        
        while current_start < end_time:
            current_end = min(current_start + (7 * 24 * 60 * 60 * 1000), end_time)
            
            # KST로 변환하여 로깅
            kst = pytz.timezone('Asia/Seoul')
            start_kst = datetime.fromtimestamp(current_start/1000, tz=kst)
            end_kst = datetime.fromtimestamp(current_end/1000, tz=kst)
            logger.info(f"\n부분 조회: {start_kst.strftime('%Y-%m-%d')} ~ {end_kst.strftime('%Y-%m-%d')}")
            
            # 해당 기간 조회
            period_fills = await self._get_period_fills_with_paging(symbol, current_start, current_end)
            
            # 중복 제거하며 추가
            new_count = 0
            for fill in period_fills:
                fill_id = self._get_fill_id(fill)
                if fill_id and fill_id not in seen_ids:
                    seen_ids.add(fill_id)
                    all_fills.append(fill)
                    new_count += 1
            
            logger.info(f"조회 결과: {len(period_fills)}건 중 {new_count}건 추가")
            
            current_start = current_end
            await asyncio.sleep(0.2)
        
        return all_fills
    
    async def _get_period_fills_with_paging(self, symbol: str, start_time: int, end_time: int) -> List[Dict]:
        """특정 기간의 모든 거래 조회 (페이징)"""
        all_fills = []
        last_id = None
        page = 0
        endpoint = "/api/v2/mix/order/fill-history"
        
        while page < 20:  # 최대 20페이지
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES',
                'startTime': str(start_time),
                'endTime': str(end_time),
                'limit': '500'
            }
            
            if last_id:
                params['lastEndId'] = str(last_id)
            
            try:
                response = await self._request('GET', endpoint, params=params)
                
                fills = []
                if isinstance(response, dict):
                    fills = response.get('fillList', response.get('list', []))
                elif isinstance(response, list):
                    fills = response
                
                if not fills:
                    break
                
                all_fills.extend(fills)
                logger.info(f"페이지 {page + 1}: {len(fills)}건 조회 (누적 {len(all_fills)}건)")
                
                if len(fills) < 500:
                    break
                
                # 다음 페이지 ID
                last_fill = fills[-1]
                new_last_id = self._get_fill_id(last_fill)
                
                if not new_last_id or new_last_id == last_id:
                    break
                
                last_id = new_last_id
                page += 1
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"페이지 {page + 1} 조회 오류: {e}")
                break
        
        return all_fills
    
    def _get_fill_id(self, fill: Dict) -> Optional[str]:
        """거래 ID 추출"""
        for field in ['fillId', 'id', 'orderId', 'tradeId']:
            if field in fill and fill[field]:
                return str(fill[field])
        return None
    
    async def get_simple_weekly_profit(self, days: int = 7) -> Dict:
        """🔥🔥 개선된 간단한 주간 손익 계산 - achievedProfits vs 정확한 거래내역 비교"""
        try:
            logger.info(f"=== 🔥 개선된 {days}일 손익 계산 시작 ===")
            
            # 현재 계정 정보
            account = await self.get_account_info()
            current_equity = float(account.get('accountEquity', 0))
            
            # 현재 포지션 정보에서 achievedProfits 확인
            positions = await self.get_positions()
            achieved_profits = 0
            position_open_time = None
            
            for pos in positions:
                achieved = float(pos.get('achievedProfits', 0))
                if achieved != 0:
                    achieved_profits = achieved
                    ctime = pos.get('cTime')
                    if ctime:
                        kst = pytz.timezone('Asia/Seoul')
                        position_open_time = datetime.fromtimestamp(int(ctime)/1000, tz=kst)
                    logger.info(f"포지션 achievedProfits: ${achieved:.2f}")
                    if position_open_time:
                        logger.info(f"포지션 오픈 시간: {position_open_time.strftime('%Y-%m-%d %H:%M')} KST")
            
            # 🔥🔥 새로운 정확한 거래 내역 기반 계산 사용
            actual_profit = await self.get_enhanced_profit_history(days=days)
            actual_pnl = actual_profit.get('total_pnl', 0)
            
            logger.info(f"🔥 비교 결과:")
            logger.info(f"   achievedProfits: ${achieved_profits:.2f}")
            logger.info(f"   정확한 {days}일 거래내역: ${actual_pnl:.2f}")
            logger.info(f"   데이터 소스: {actual_profit.get('source', 'unknown')}")
            logger.info(f"   신뢰도: {actual_profit.get('confidence', 'unknown')}")
            
            # 🔥🔥 더 정교한 선택 로직
            if actual_profit.get('confidence') == 'high' and actual_pnl != 0:
                # Account Bills 기반 결과가 신뢰도 높으면 우선 사용
                logger.info("✅ Account Bills 기반 정확한 데이터 사용")
                result = actual_profit.copy()
                result['source'] = 'enhanced_account_bills'
                return result
            
            elif achieved_profits > 0 and position_open_time:
                # achievedProfits가 있고 포지션 시간 정보가 있는 경우
                kst = pytz.timezone('Asia/Seoul')
                now = datetime.now(kst)
                position_days = (now - position_open_time).days + 1
                
                # 포지션이 요청 기간 내에 열렸고, 두 값의 차이가 합리적인 범위면 achievedProfits 사용
                if position_days <= days:
                    if actual_pnl == 0 or abs(achieved_profits - actual_pnl) / max(abs(actual_pnl), 1) < 0.3:
                        logger.info(f"✅ achievedProfits 사용 (포지션 기간: {position_days}일, 차이 합리적)")
                        return {
                            'total_pnl': achieved_profits,
                            'days': days,
                            'average_daily': achieved_profits / days,
                            'source': 'achievedProfits',
                            'confidence': 'medium',
                            'position_days': position_days,
                            'daily_pnl': {}
                        }
                    else:
                        logger.info(f"⚠️ achievedProfits와 실제 거래내역 차이 큼: ${abs(achieved_profits - actual_pnl):.2f}")
                        # 차이가 크면 실제 거래내역 사용
                        result = actual_profit.copy()
                        result['source'] = f"{result.get('source', 'unknown')}_vs_achieved"
                        return result
                else:
                    logger.info(f"⚠️ 포지션이 너무 오래됨: {position_days}일 > {days}일")
            
            # 기본적으로 정확한 거래내역 사용
            if actual_pnl != 0 or actual_profit.get('trade_count', 0) > 0:
                logger.info("✅ 정확한 거래내역 사용 (기본)")
                result = actual_profit.copy()
                result['source'] = f"{result.get('source', 'unknown')}_primary"
                return result
            
            # 마지막 폴백: achievedProfits만 있는 경우
            if achieved_profits > 0:
                logger.info("✅ achievedProfits만 사용 (폴백)")
                return {
                    'total_pnl': achieved_profits,
                    'days': days,
                    'average_daily': achieved_profits / days,
                    'source': 'achievedProfits_only',
                    'confidence': 'low',
                    'daily_pnl': {}
                }
            
            # 최종: 빈 결과
            logger.warning("⚠️ 모든 손익 데이터가 0 또는 없음")
            return {
                'total_pnl': 0,
                'days': days,
                'average_daily': 0,
                'source': 'no_data',
                'confidence': 'none',
                'daily_pnl': {}
            }
            
        except Exception as e:
            logger.error(f"개선된 주간 손익 계산 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return {
                'total_pnl': 0,
                'days': days,
                'average_daily': 0,
                'source': 'error',
                'confidence': 'none',
                'error': str(e),
                'daily_pnl': {}
            }
    
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
            # 리스트인 경우 첫 번째 요소 반환
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
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
