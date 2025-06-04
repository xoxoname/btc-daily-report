import asyncio
import aiohttp
import hmac
import hashlib
import time
import json
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import traceback
import base64

logger = logging.getLogger(__name__)

class BitgetClient:
    """Bitget API 클라이언트"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config.BITGET_APIKEY
        self.api_secret = config.BITGET_APISECRET
        self.passphrase = config.BITGET_PASSPHRASE
        self.base_url = "https://api.bitget.com"
        self.session = None
        
    async def initialize(self):
        """클라이언트 초기화"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            logger.info("Bitget 클라이언트 초기화 완료")
    
    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """API 서명 생성 - 수정된 버전"""
        try:
            # Bitget API v2 서명 방식
            message = timestamp + method.upper() + request_path + body
            
            # HMAC-SHA256으로 서명 생성
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
            
            # Base64 인코딩
            return base64.b64encode(signature).decode('utf-8')
            
        except Exception as e:
            logger.error(f"서명 생성 실패: {e}")
            raise
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """API 요청 - 수정된 버전"""
        if not self.session:
            await self.initialize()
        
        url = f"{self.base_url}{endpoint}"
        timestamp = str(int(time.time() * 1000))
        
        query_string = ""
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            if query_string:
                url += f"?{query_string}"
        
        body = ""
        if data:
            body = json.dumps(data)
        
        request_path = endpoint
        if query_string:
            request_path += f"?{query_string}"
        
        try:
            signature = self._generate_signature(timestamp, method, request_path, body)
        except Exception as e:
            logger.error(f"서명 생성 중 오류: {e}")
            raise
        
        headers = {
            'ACCESS-KEY': self.api_key,
            'ACCESS-SIGN': signature,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json',
            'locale': 'en-US'
        }
        
        try:
            logger.debug(f"Bitget API 요청: {method} {url}")
            async with self.session.request(method, url, headers=headers, data=body) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    logger.error(f"Bitget API 오류: {response.status} - {response_text}")
                    # 🔥 수정: 예외를 던지지 않고 에러 응답을 반환
                    try:
                        error_result = json.loads(response_text) if response_text else {}
                        return error_result
                    except:
                        return {'code': str(response.status), 'msg': response_text, 'data': None}
                
                result = json.loads(response_text) if response_text else {}
                
                # 🔥 수정: 에러 코드 체크를 제거하고 결과를 그대로 반환
                # API 응답 코드가 성공이 아니어도 결과를 반환하여 호출하는 쪽에서 처리하도록 함
                return result
                
        except Exception as e:
            logger.error(f"Bitget API 요청 중 오류: {e}")
            raise
    
    async def get_account_info(self) -> Dict:
        """계정 정보 조회 - 파라미터 수정"""
        try:
            # V2 API 엔드포인트 사용 - 파라미터 수정
            endpoint = "/api/v2/mix/account/account"
            params = {
                'symbol': 'BTCUSDT',
                'marginCoin': 'USDT',
                'productType': 'USDT-FUTURES'  # 필수 파라미터 추가
            }
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                return response['data']
            else:
                logger.error(f"계정 정보 조회 실패: {response}")
                return {}
                
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            return {}
    
    async def get_positions(self, symbol: str = "BTCUSDT") -> List[Dict]:
        """포지션 조회 - 파라미터 수정"""
        try:
            # V2 API 엔드포인트 사용 - 파라미터 수정
            endpoint = "/api/v2/mix/position/all-position"
            params = {
                'symbol': symbol,
                'marginCoin': 'USDT',
                'productType': 'USDT-FUTURES'  # 필수 파라미터 추가
            }
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []
    
    async def get_ticker(self, symbol: str = "BTCUSDT") -> Dict:
        """티커 정보 조회 - 파라미터 수정"""
        try:
            # V2 API 엔드포인트 사용 - 필수 파라미터 추가
            endpoint = "/api/v2/mix/market/ticker"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'  # 🔥 필수 파라미터 추가
            }
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                data = response['data']
                # 데이터가 리스트인 경우 첫 번째 요소 반환
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                else:
                    return data
            else:
                logger.warning(f"티커 조회 응답 확인: {response}")
                return {}
                
        except Exception as e:
            logger.error(f"티커 조회 실패: {e}")
            return {}
    
    async def get_kline(self, symbol: str, granularity: str, limit: int = 100) -> List[List]:
        """K라인 데이터 조회 - 파라미터 수정"""
        try:
            # V2 API 엔드포인트 사용 - 필수 파라미터 추가
            endpoint = "/api/v2/mix/market/candles"
            params = {
                'symbol': symbol,
                'granularity': granularity,
                'limit': str(limit),
                'productType': 'USDT-FUTURES'  # 🔥 필수 파라미터 추가
            }
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"K라인 데이터 조회 실패: {e}")
            return []
    
    async def get_funding_rate(self, symbol: str = "BTCUSDT") -> Dict:
        """펀딩비 조회 - 파라미터 수정"""
        try:
            # V2 API 엔드포인트 사용 - 필수 파라미터 추가
            endpoint = "/api/v2/mix/market/current-fund-rate"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'  # 🔥 필수 파라미터 추가
            }
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                data = response['data']
                # 데이터가 리스트인 경우 첫 번째 요소 반환
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                else:
                    return data
            else:
                return {}
                
        except Exception as e:
            logger.error(f"펀딩비 조회 실패: {e}")
            return {}
    
    async def get_open_interest(self, symbol: str = "BTCUSDT") -> Dict:
        """미결제약정 조회 - 파라미터 수정"""
        try:
            # V2 API 엔드포인트 사용 - 필수 파라미터 추가
            endpoint = "/api/v2/mix/market/open-interest"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'  # 🔥 필수 파라미터 추가
            }
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                data = response['data']
                # 데이터가 리스트인 경우 첫 번째 요소 반환
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                else:
                    return data
            else:
                return {}
                
        except Exception as e:
            logger.error(f"미결제약정 조회 실패: {e}")
            return {}
    
    async def get_recent_filled_orders(self, symbol: str = "BTCUSDT", minutes: int = 5) -> List[Dict]:
        """최근 체결 주문 조회 - 파라미터 형식 수정"""
        try:
            # V2 API 엔드포인트 사용 - 파라미터 수정
            endpoint = "/api/v2/mix/order/fills"
            
            # 필수 파라미터 추가
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'  # 필수 파라미터
            }
            
            # 시간 범위가 필요한 경우만 추가
            if minutes and minutes > 0:
                end_time = int(time.time() * 1000)
                start_time = end_time - (minutes * 60 * 1000)
                params['startTime'] = str(start_time)
                params['endTime'] = str(end_time)
            
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"최근 체결 주문 조회 실패: {e}")
            return []
    
    async def get_all_plan_orders_with_tp_sl(self, symbol: str = "BTCUSDT") -> Dict:
        """모든 예약 주문 조회 (TP/SL 포함) - 🔥🔥🔥 완전 수정"""
        try:
            result = {
                'plan_orders': [],
                'tp_sl_orders': []
            }
            
            # 🔥🔥🔥 Bitget API v2에서 실제로 지원하는 planType 값만 사용
            # API 문서에 따르면 v2에서는 다음 값들만 지원:
            plan_types_to_check = [
                'pl',       # Profit & Loss (손익 주문)
                'tp',       # Take Profit (이익실현)
                'sl',       # Stop Loss (손절)
                'normal',   # Normal plan order (일반 계획 주문)
                'pos_profit',  # Position take profit
                'pos_loss',    # Position stop loss
                'moving_plan', # Trailing stop
                'track'        # Track order
            ]
            
            # 각 planType별로 조회
            for plan_type in plan_types_to_check:
                try:
                    endpoint = "/api/v2/mix/order/orders-plan-pending"
                    params = {
                        'symbol': symbol,
                        'productType': 'USDT-FUTURES',
                        'planType': plan_type
                    }
                    
                    logger.debug(f"🔥 예약 주문 조회 - planType: {plan_type}")
                    response = await self._request('GET', endpoint, params=params)
                    
                    # 🔥🔥🔥 응답 처리 수정 - 에러 응답도 제대로 처리
                    if isinstance(response, dict):
                        response_code = response.get('code')
                        
                        if response_code == '00000' and response.get('data'):
                            orders = response['data']
                            
                            for order in orders:
                                # 주문 타입에 따라 분류
                                current_plan_type = order.get('planType', plan_type)
                                trade_side = order.get('tradeSide', order.get('side', ''))
                                
                                # TP/SL 주문 분류
                                is_tp_sl = plan_type in ['tp', 'sl', 'pl', 'pos_profit', 'pos_loss']
                                
                                # tradeSide로도 추가 분류
                                if trade_side in ['close_long', 'close_short']:
                                    is_tp_sl = True
                                
                                if is_tp_sl:
                                    result['tp_sl_orders'].append(order)
                                else:
                                    result['plan_orders'].append(order)
                            
                            logger.info(f"✅ planType '{plan_type}' 조회 성공: {len(orders)}개")
                        
                        elif response_code == '40812':
                            # 지원되지 않는 planType - 정상적인 상황이므로 debug 로그만
                            logger.debug(f"📝 planType '{plan_type}'은 현재 지원되지 않음")
                            continue
                        
                        elif response_code == '40002':
                            # 잘못된 파라미터 - 경고 로그
                            logger.warning(f"⚠️ planType '{plan_type}' 파라미터 오류: {response.get('msg', '')}")
                            continue
                        
                        else:
                            # 기타 오류
                            logger.warning(f"⚠️ planType '{plan_type}' 조회 응답: code={response_code}, msg={response.get('msg', '')}")
                            continue
                    else:
                        # 응답이 딕셔너리가 아닌 경우
                        logger.warning(f"⚠️ planType '{plan_type}' 조회 - 예상치 못한 응답 형식: {type(response)}")
                        continue
                    
                except Exception as e:
                    # 예외 처리
                    error_msg = str(e)
                    logger.warning(f"⚠️ planType '{plan_type}' 조회 중 예외 발생: {error_msg}")
                    continue
            
            total_orders = len(result['plan_orders']) + len(result['tp_sl_orders'])
            logger.info(f"✅ 전체 예약 주문 조회 완료: 일반 {len(result['plan_orders'])}개, TP/SL {len(result['tp_sl_orders'])}개, 총 {total_orders}개")
            
            return result
            
        except Exception as e:
            logger.error(f"예약 주문 조회 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return {'plan_orders': [], 'tp_sl_orders': []}
    
    async def get_trade_fills(self, symbol: str = "BTCUSDT", start_time: int = 0, end_time: int = 0, limit: int = 100) -> List[Dict]:
        """거래 내역 조회 - 파라미터 형식 수정"""
        try:
            endpoint = "/api/v2/mix/order/fills"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES',  # 필수 파라미터 추가
                'limit': str(limit)
            }
            
            if start_time > 0:
                params['startTime'] = str(start_time)
            if end_time > 0:
                params['endTime'] = str(end_time)
            
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"거래 내역 조회 실패: {e}")
            return []
    
    async def get_enhanced_profit_history(self, days: int = 7) -> Dict:
        """향상된 손익 내역 조회 - 파라미터 수정"""
        try:
            end_time = int(time.time() * 1000)
            start_time = end_time - (days * 24 * 60 * 60 * 1000)
            
            # V2 API 엔드포인트 사용 - 파라미터 수정
            endpoint = "/api/v2/mix/account/account-bill"
            params = {
                'symbol': 'BTCUSDT',
                'marginCoin': 'USDT',
                'productType': 'USDT-FUTURES',  # 필수 파라미터 추가
                'startTime': str(start_time),
                'endTime': str(end_time),
                'pageSize': '100'
            }
            
            response = await self._request('GET', endpoint, params=params)
            
            total_pnl = 0.0
            
            if response.get('code') == '00000' and response.get('data'):
                for record in response['data']:
                    change = float(record.get('amount', 0))
                    business_type = record.get('businessType', '')
                    
                    # 실현 손익만 계산
                    if business_type in ['close_long', 'close_short', 'delivery_long', 'delivery_short']:
                        total_pnl += change
            
            return {
                'total_pnl': total_pnl,
                'average_daily': total_pnl / days if days > 0 else 0,
                'days': days
            }
            
        except Exception as e:
            logger.error(f"손익 내역 조회 실패: {e}")
            return {
                'total_pnl': 0.0,
                'average_daily': 0.0,
                'days': days
            }
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
