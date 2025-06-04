import asyncio
import aiohttp
import hmac
import hashlib
import time
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

class GateClient:
    def __init__(self, config):
        self.config = config
        self.api_key = config.GATE_API_KEY
        self.api_secret = config.GATE_API_SECRET
        self.base_url = "https://api.gateio.ws"
        self.session = None
        self._initialize_session()
        
        # Gate.io 거래 시작일 설정 (2025년 5월 29일)
        self.GATE_START_DATE = datetime(2025, 5, 29, 0, 0, 0, tzinfo=pytz.timezone('Asia/Seoul'))
        
    def _initialize_session(self):
        """세션 초기화"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            logger.info("Gate.io 클라이언트 세션 초기화 완료")
    
    async def initialize(self):
        """클라이언트 초기화"""
        self._initialize_session()
        logger.info("Gate.io 클라이언트 초기화 완료")
    
    def _generate_signature(self, method: str, url: str, query_string: str = "", payload: str = "") -> Dict[str, str]:
        """Gate.io API 서명 생성"""
        timestamp = str(int(time.time()))
        
        # 서명 메시지 생성
        hashed_payload = hashlib.sha512(payload.encode('utf-8')).hexdigest()
        s = f"{method}\n{url}\n{query_string}\n{hashed_payload}\n{timestamp}"
        
        # HMAC-SHA512 서명
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            s.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return {
            'KEY': self.api_key,
            'Timestamp': timestamp,
            'SIGN': signature,
            'Content-Type': 'application/json'
        }
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """API 요청"""
        if not self.session:
            self._initialize_session()
        
        url = f"{self.base_url}{endpoint}"
        query_string = ""
        payload = ""
        
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            url += f"?{query_string}"
        
        if data:
            payload = json.dumps(data)
        
        headers = self._generate_signature(method, endpoint, query_string, payload)
        
        try:
            logger.debug(f"Gate.io API 요청: {method} {url}")
            if data:
                logger.debug(f"요청 데이터: {payload}")
            
            async with self.session.request(method, url, headers=headers, data=payload) as response:
                response_text = await response.text()
                logger.debug(f"Gate.io 응답: {response_text[:500]}")
                
                if response.status != 200:
                    logger.error(f"Gate.io API 오류: {response.status} - {response_text}")
                    raise Exception(f"Gate.io API 오류: {response_text}")
                
                return json.loads(response_text) if response_text else {}
                
        except Exception as e:
            logger.error(f"Gate.io API 요청 중 오류: {e}")
            raise
    
    async def get_account_balance(self) -> Dict:
        """계정 잔고 조회 - 선물 계정"""
        try:
            endpoint = "/api/v4/futures/usdt/accounts"
            response = await self._request('GET', endpoint)
            logger.debug(f"Gate.io 계정 잔고 응답: {response}")
            return response
        except Exception as e:
            logger.error(f"계정 잔고 조회 실패: {e}")
            raise
    
    async def get_futures_account(self) -> Dict:
        """선물 계정 정보 조회 (get_account_balance와 동일)"""
        return await self.get_account_balance()
    
    async def get_ticker(self, contract: str = "BTC_USDT") -> Dict:
        """티커 정보 조회 - 추가된 메서드"""
        try:
            endpoint = f"/api/v4/futures/usdt/tickers"
            params = {'contract': contract}
            response = await self._request('GET', endpoint, params=params)
            
            # Gate.io는 리스트 형태로 반환하므로 첫 번째 요소 반환
            if isinstance(response, list) and len(response) > 0:
                ticker_data = response[0]
                # last 필드가 없으면 mark_price 사용
                if 'last' not in ticker_data and 'mark_price' in ticker_data:
                    ticker_data['last'] = ticker_data['mark_price']
                return ticker_data
            elif isinstance(response, dict):
                # last 필드가 없으면 mark_price 사용
                if 'last' not in response and 'mark_price' in response:
                    response['last'] = response['mark_price']
                return response
            else:
                logger.warning(f"Gate.io 티커 응답 형식 이상: {response}")
                return {}
            
        except Exception as e:
            logger.error(f"Gate.io 티커 조회 실패: {e}")
            # 티커 조회 실패 시 빈 딕셔너리 반환
            return {}
    
    async def get_positions(self, contract: str = "BTC_USDT") -> List[Dict]:
        """포지션 조회"""
        try:
            endpoint = f"/api/v4/futures/usdt/positions/{contract}"
            response = await self._request('GET', endpoint)
            
            # 단일 포지션이면 리스트로 변환
            if isinstance(response, dict):
                return [response] if response.get('size', 0) != 0 else []
            return response
            
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []
    
    async def place_order(self, contract: str, size: int, price: Optional[float] = None, 
                         reduce_only: bool = False, tif: str = "gtc", iceberg: int = 0) -> Dict:
        """시장가/지정가 주문 생성
        
        Args:
            contract: 계약명 (예: BTC_USDT)
            size: 주문 수량 (양수=롱, 음수=숏)
            price: 지정가 (None이면 시장가)
            reduce_only: 포지션 감소 전용
            tif: Time in Force (지정가일 때만 사용)
            iceberg: 빙산 주문 수량
        """
        try:
            endpoint = "/api/v4/futures/usdt/orders"
            
            # 기본 주문 데이터
            data = {
                "contract": contract,
                "size": size  # 정수로 유지
            }
            
            if price is not None:
                # 지정가 주문
                data["price"] = str(price)
                data["tif"] = tif
                logger.info(f"지정가 주문 생성: {contract}, 수량: {size}, 가격: {price}, TIF: {tif}")
            else:
                # 시장가 주문 - TIF 제거
                logger.info(f"시장가 주문 생성: {contract}, 수량: {size}")
            
            # reduce_only 처리
            if reduce_only:
                data["reduce_only"] = True
                logger.info(f"포지션 감소 전용 주문")
            
            # 빙산 주문 (필요한 경우만 추가)
            if iceberg > 0:
                data["iceberg"] = iceberg
                logger.info(f"빙산 주문: {iceberg}")
            
            logger.info(f"Gate.io 주문 생성 요청: {data}")
            response = await self._request('POST', endpoint, data=data)
            logger.info(f"✅ Gate.io 주문 생성 성공: {response}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Gate.io 주문 생성 실패: {e}")
            logger.error(f"주문 파라미터: contract={contract}, size={size}, price={price}, reduce_only={reduce_only}, tif={tif}")
            raise
    
    async def set_leverage(self, contract: str, leverage: int, cross_leverage_limit: int = 0, 
                          retry_count: int = 3) -> Dict:
        """레버리지 설정 - 재시도 및 확인 로직 포함"""
        for attempt in range(retry_count):
            try:
                endpoint = f"/api/v4/futures/usdt/positions/{contract}/leverage"
                
                params = {
                    "leverage": str(leverage)
                }
                
                if cross_leverage_limit > 0:
                    params["cross_leverage_limit"] = str(cross_leverage_limit)
                
                logger.info(f"Gate.io 레버리지 설정 시도 {attempt + 1}/{retry_count}: {contract} - {leverage}x")
                response = await self._request('POST', endpoint, params=params)
                
                # 설정 후 잠시 대기
                await asyncio.sleep(0.3)
                
                # 설정 확인
                verify_success = await self._verify_leverage_setting(contract, leverage)
                if verify_success:
                    logger.info(f"✅ Gate.io 레버리지 설정 및 확인 완료: {contract} - {leverage}x")
                    return response
                else:
                    logger.warning(f"⚠️ 레버리지 설정 확인 실패, 재시도 {attempt + 1}/{retry_count}")
                    if attempt < retry_count - 1:
                        await asyncio.sleep(0.5)
                        continue
                    else:
                        logger.error(f"❌ 레버리지 설정 최종 실패: {contract} - {leverage}x")
                        return response
                
            except Exception as e:
                logger.error(f"❌ Gate.io 레버리지 설정 시도 {attempt + 1} 실패: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(1.0)
                    continue
                else:
                    raise
        
        raise Exception(f"레버리지 설정 최대 재시도 횟수 초과: {contract} - {leverage}x")
    
    async def _verify_leverage_setting(self, contract: str, expected_leverage: int) -> bool:
        """레버리지 설정 확인"""
        try:
            positions = await self.get_positions(contract)
            if positions:
                current_leverage = positions[0].get('leverage')
                if current_leverage:
                    current_lev_int = int(float(current_leverage))
                    if current_lev_int == expected_leverage:
                        logger.info(f"✅ 레버리지 확인 성공: {current_lev_int}x = {expected_leverage}x")
                        return True
                    else:
                        logger.warning(f"⚠️ 레버리지 불일치: 현재 {current_lev_int}x, 예상 {expected_leverage}x")
                        return False
            
            logger.info("📝 포지션이 없어 레버리지 확인 불가, 설정 성공으로 처리")
            return True
            
        except Exception as e:
            logger.warning(f"레버리지 확인 중 오류: {e}")
            return True
    
    async def get_leverage_info(self, contract: str = "BTC_USDT") -> Dict:
        """현재 레버리지 정보 조회"""
        try:
            positions = await self.get_positions(contract)
            if positions:
                position = positions[0]
                leverage = position.get('leverage', 'N/A')
                mode = position.get('mode', 'N/A')
                
                logger.info(f"Gate.io 현재 레버리지: {leverage}x, 모드: {mode}")
                return {
                    'leverage': leverage,
                    'mode': mode,
                    'contract': contract
                }
            else:
                logger.info("📝 활성 포지션이 없어 레버리지 정보 조회 불가")
                return {
                    'leverage': 'N/A',
                    'mode': 'N/A',
                    'contract': contract
                }
                
        except Exception as e:
            logger.error(f"레버리지 정보 조회 실패: {e}")
            return {
                'leverage': 'Error',
                'mode': 'Error',
                'contract': contract,
                'error': str(e)
            }
    
    async def set_position_mode(self, contract: str, mode: str = "dual_long") -> Dict:
        """포지션 모드 설정 (dual_long, dual_short, single)"""
        try:
            endpoint = f"/api/v4/futures/usdt/positions/{contract}/margin"
            
            data = {
                "change": "0",
                "mode": mode
            }
            
            response = await self._request('POST', endpoint, data=data)
            return response
            
        except Exception as e:
            logger.error(f"포지션 모드 설정 실패: {e}")
            raise
    
    async def create_price_triggered_order(self, trigger_type: str, trigger_price: str, 
                                         order_type: str, contract: str, size: int, 
                                         price: Optional[str] = None) -> Dict:
        """가격 트리거 주문 생성 (TP/SL)
        
        Args:
            trigger_type: 트리거 타입 (ge=이상, le=이하)
            trigger_price: 트리거 가격
            order_type: 주문 타입 (limit, market)
            contract: 계약명
            size: 수량 (정수)
            price: 지정가 (시장가면 None)
        """
        try:
            endpoint = "/api/v4/futures/usdt/price_orders"
            
            initial_data = {
                "type": order_type,
                "contract": contract,
                "size": size
            }
            
            # 시장가 트리거 주문에서도 price 필드 필수 - trigger_price 사용
            if order_type == "limit":
                if price:
                    initial_data["price"] = str(price)
                else:
                    initial_data["price"] = str(trigger_price)
                    logger.info(f"지정가 주문에 트리거 가격을 price로 사용: {trigger_price}")
            elif order_type == "market":
                initial_data["price"] = str(trigger_price)
                logger.info(f"시장가 트리거 주문에 trigger_price를 initial.price로 설정: {trigger_price}")
            
            # 트리거 rule을 정수로 변환
            if trigger_type == "ge":
                rule_value = 1  # >= (greater than or equal)
            elif trigger_type == "le":
                rule_value = 2  # <= (less than or equal)
            else:
                rule_value = 1
                logger.warning(f"알 수 없는 trigger_type: {trigger_type}, 기본값 ge(1) 사용")
            
            data = {
                "initial": initial_data,
                "trigger": {
                    "strategy_type": 0,
                    "price_type": 0,
                    "price": str(trigger_price),
                    "rule": rule_value
                }
            }
            
            logger.info(f"Gate.io 가격 트리거 주문 생성: {data}")
            response = await self._request('POST', endpoint, data=data)
            logger.info(f"✅ Gate.io 가격 트리거 주문 생성 성공: {response}")
            return response
            
        except Exception as e:
            logger.error(f"❌ 가격 트리거 주문 생성 실패: {e}")
            logger.error(f"트리거 주문 파라미터: trigger_type={trigger_type}, trigger_price={trigger_price}, order_type={order_type}, size={size}, price={price}")
            raise
    
    async def create_price_triggered_order_with_tp_sl(self, trigger_type: str, trigger_price: str,
                                                     order_type: str, contract: str, size: int,
                                                     price: Optional[str] = None,
                                                     tp_price: Optional[str] = None,
                                                     sl_price: Optional[str] = None) -> Dict:
        """TP/SL 설정이 포함된 가격 트리거 주문 생성 - auto_size 파라미터 제거
        
        Args:
            trigger_type: 트리거 타입 (ge=이상, le=이하)
            trigger_price: 트리거 가격
            order_type: 주문 타입 (limit, market)
            contract: 계약명
            size: 수량 (정수)
            price: 지정가 (시장가면 None)
            tp_price: Take Profit 가격
            sl_price: Stop Loss 가격
        """
        try:
            # 먼저 기본 트리거 주문 생성
            logger.info(f"🎯 TP/SL 포함 트리거 주문 생성 시도 - TP: {tp_price}, SL: {sl_price}")
            
            # 기본 트리거 주문 생성
            basic_order = await self.create_price_triggered_order(
                trigger_type=trigger_type,
                trigger_price=trigger_price,
                order_type=order_type,
                contract=contract,
                size=size,
                price=price
            )
            
            # TP/SL이 설정되어 있으면 별도 주문으로 생성
            tp_order = None
            sl_order = None
            
            if tp_price:
                try:
                    # TP 주문 생성
                    tp_trigger_type = "le" if size > 0 else "ge"  # 롱이면 le (가격이 TP 이하로 떨어지면), 숏이면 ge
                    tp_size = -size  # 반대 방향으로 청산
                    
                    tp_order = await self.create_price_triggered_order(
                        trigger_type=tp_trigger_type,
                        trigger_price=tp_price,
                        order_type="market",
                        contract=contract,
                        size=tp_size
                    )
                    logger.info(f"🎯 TP 주문 생성 성공: {tp_order.get('id')}")
                    
                except Exception as tp_error:
                    logger.error(f"TP 주문 생성 실패: {tp_error}")
            
            if sl_price:
                try:
                    # SL 주문 생성
                    sl_trigger_type = "ge" if size > 0 else "le"  # 롱이면 ge (가격이 SL 이상으로 올라가면), 숏이면 le
                    sl_size = -size  # 반대 방향으로 청산
                    
                    sl_order = await self.create_price_triggered_order(
                        trigger_type=sl_trigger_type,
                        trigger_price=sl_price,
                        order_type="market",
                        contract=contract,
                        size=sl_size
                    )
                    logger.info(f"🛡️ SL 주문 생성 성공: {sl_order.get('id')}")
                    
                except Exception as sl_error:
                    logger.error(f"SL 주문 생성 실패: {sl_error}")
            
            # 결과 반환 - 기본 주문에 TP/SL 주문 정보 추가
            result = basic_order.copy()
            result['tp_order'] = tp_order
            result['sl_order'] = sl_order
            result['has_tp_sl'] = bool(tp_order or sl_order)
            
            logger.info(f"✅ TP/SL 포함 트리거 주문 생성 완료: 기본={basic_order.get('id')}, TP={tp_order.get('id') if tp_order else None}, SL={sl_order.get('id') if sl_order else None}")
            return result
            
        except Exception as e:
            logger.error(f"❌ TP/SL 포함 트리거 주문 생성 실패: {e}")
            # 폴백: 일반 트리거 주문만 생성
            logger.info("폴백: TP/SL 없는 일반 트리거 주문 생성")
            return await self.create_price_triggered_order(
                trigger_type=trigger_type,
                trigger_price=trigger_price,
                order_type=order_type,
                contract=contract,
                size=size,
                price=price
            )
    
    async def create_conditional_order_with_tp_sl(self, contract: str, size: int, 
                                                 trigger_price: float, trigger_type: str,
                                                 tp_price: Optional[float] = None,
                                                 sl_price: Optional[float] = None) -> Dict:
        """TP/SL 설정이 포함된 조건부 주문 생성 (대안 방법) - auto_size 파라미터 제거"""
        try:
            logger.info(f"조건부 주문 (TP/SL 포함) 생성 시작 - TP: {tp_price}, SL: {sl_price}")
            
            # 기본 트리거 주문 생성
            main_order = await self.create_price_triggered_order(
                trigger_type=trigger_type,
                trigger_price=str(trigger_price),
                order_type="market",
                contract=contract,
                size=size
            )
            
            # TP/SL 별도 주문 생성
            tp_order = None
            sl_order = None
            
            if tp_price:
                try:
                    tp_trigger_type = "le" if size > 0 else "ge"
                    tp_size = -size
                    
                    tp_order = await self.create_price_triggered_order(
                        trigger_type=tp_trigger_type,
                        trigger_price=str(tp_price),
                        order_type="market",
                        contract=contract,
                        size=tp_size
                    )
                    logger.info(f"조건부 주문에 TP 설정 완료: {tp_price}")
                    
                except Exception as tp_error:
                    logger.error(f"조건부 TP 주문 생성 실패: {tp_error}")
            
            if sl_price:
                try:
                    sl_trigger_type = "ge" if size > 0 else "le"
                    sl_size = -size
                    
                    sl_order = await self.create_price_triggered_order(
                        trigger_type=sl_trigger_type,
                        trigger_price=str(sl_price),
                        order_type="market",
                        contract=contract,
                        size=sl_size
                    )
                    logger.info(f"조건부 주문에 SL 설정 완료: {sl_price}")
                    
                except Exception as sl_error:
                    logger.error(f"조건부 SL 주문 생성 실패: {sl_error}")
            
            # 결과 통합
            result = main_order.copy()
            result['tp_order'] = tp_order
            result['sl_order'] = sl_order
            result['has_tp_sl'] = bool(tp_order or sl_order)
            
            logger.info(f"✅ 조건부 주문 (TP/SL 포함) 생성 성공: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 조건부 주문 (TP/SL 포함) 생성 실패: {e}")
            raise
    
    async def get_price_triggered_orders(self, contract: str, status: str = "open") -> List[Dict]:
        """가격 트리거 주문 조회"""
        try:
            endpoint = "/api/v4/futures/usdt/price_orders"
            params = {
                "contract": contract,
                "status": status
            }
            
            response = await self._request('GET', endpoint, params=params)
            return response if isinstance(response, list) else []
            
        except Exception as e:
            logger.error(f"가격 트리거 주문 조회 실패: {e}")
            return []
    
    async def cancel_price_triggered_order(self, order_id: str) -> Dict:
        """가격 트리거 주문 취소"""
        try:
            endpoint = f"/api/v4/futures/usdt/price_orders/{order_id}"
            response = await self._request('DELETE', endpoint)
            logger.info(f"✅ Gate.io 가격 트리거 주문 취소 성공: {order_id}")
            return response
            
        except Exception as e:
            logger.error(f"❌ 가격 트리거 주문 취소 실패: {order_id} - {e}")
            raise
    
    async def get_contract_info(self, contract: str = "BTC_USDT") -> Dict:
        """계약 정보 조회"""
        try:
            endpoint = f"/api/v4/futures/usdt/contracts/{contract}"
            response = await self._request('GET', endpoint)
            return response
            
        except Exception as e:
            logger.error(f"계약 정보 조회 실패: {e}")
            raise
    
    async def close_position(self, contract: str, size: Optional[int] = None) -> Dict:
        """포지션 종료
        
        Args:
            contract: 계약명
            size: 종료할 수량 (None이면 전체 종료)
        """
        try:
            positions = await self.get_positions(contract)
            
            if not positions or positions[0].get('size', 0) == 0:
                logger.warning(f"종료할 포지션이 없습니다: {contract}")
                return {"status": "no_position"}
            
            position = positions[0]
            position_size = int(position['size'])
            
            # 종료할 수량 계산
            if size is None:
                close_size = -position_size  # 전체 종료
            else:
                # 부분 종료
                if position_size > 0:  # 롱 포지션
                    close_size = -min(abs(size), position_size)
                else:  # 숏 포지션
                    close_size = min(abs(size), abs(position_size))
            
            logger.info(f"Gate.io 포지션 종료: {contract}, 현재 사이즈: {position_size}, 종료 사이즈: {close_size}")
            
            # 시장가로 포지션 종료
            result = await self.place_order(
                contract=contract,
                size=close_size,
                price=None,  # 시장가
                reduce_only=True
            )
            
            logger.info(f"✅ Gate.io 포지션 종료 성공: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 포지션 종료 실패: {e}")
            raise
    
    async def get_order_history(self, contract: str = "BTC_USDT", status: str = "finished", 
                              start_time: Optional[int] = None, end_time: Optional[int] = None,
                              limit: int = 100) -> List[Dict]:
        """주문 내역 조회"""
        try:
            endpoint = "/api/v4/futures/usdt/orders"
            params = {
                "contract": contract,
                "status": status,
                "limit": str(limit)
            }
            
            if start_time:
                params["from"] = str(start_time)
            if end_time:
                params["to"] = str(end_time)
            
            response = await self._request('GET', endpoint, params=params)
            return response if isinstance(response, list) else []
            
        except Exception as e:
            logger.error(f"주문 내역 조회 실패: {e}")
            return []
    
    async def get_position_history(self, contract: str = "BTC_USDT", 
                                 start_time: Optional[int] = None, end_time: Optional[int] = None,
                                 limit: int = 100) -> List[Dict]:
        """포지션 히스토리 조회"""
        try:
            endpoint = "/api/v4/futures/usdt/position_close"
            params = {
                "contract": contract,
                "limit": str(limit)
            }
            
            if start_time:
                params["from"] = str(start_time)
            if end_time:
                params["to"] = str(end_time)
            
            response = await self._request('GET', endpoint, params=params)
            return response if isinstance(response, list) else []
            
        except Exception as e:
            logger.error(f"포지션 히스토리 조회 실패: {e}")
            return []
    
    async def get_account_book(self, type: Optional[str] = None, 
                             start_time: Optional[int] = None, end_time: Optional[int] = None,
                             limit: int = 100) -> List[Dict]:
        """계정 장부 조회 (손익 내역)"""
        try:
            endpoint = "/api/v4/futures/usdt/account_book"
            params = {
                "limit": str(limit)
            }
            
            if type:
                params["type"] = type
            if start_time:
                params["from"] = str(start_time)
            if end_time:
                params["to"] = str(end_time)
            
            response = await self._request('GET', endpoint, params=params)
            return response if isinstance(response, list) else []
            
        except Exception as e:
            logger.error(f"계정 장부 조회 실패: {e}")
            return []
    
    async def get_profit_history_since_may(self) -> Dict:
        """2025년 5월 29일부터의 손익 계산 - 개선된 오류 처리"""
        try:
            import pytz
            from datetime import datetime
            
            kst = pytz.timezone('Asia/Seoul')
            
            # 현재 시간
            now = datetime.now(kst)
            
            # 오늘 0시 (KST)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_timestamp = int(today_start.timestamp())
            
            # 7일 전 0시 (KST)
            seven_days_ago = today_start - timedelta(days=6)
            seven_days_timestamp = int(seven_days_ago.timestamp())
            
            # 2025년 5월 29일 0시 (KST) - 실제 거래 시작일
            start_timestamp = int(self.GATE_START_DATE.timestamp())
            
            # 계정 정보
            account = await self.get_account_balance()
            current_balance = float(account.get('total', 0))
            
            # 초기 자본 설정
            initial_capital = 700.0  # 기본값
            
            # 5월 29일부터 현재까지의 손익 계산
            total_pnl = 0.0
            total_fee = 0.0
            total_fund = 0.0
            
            # PnL 조회 (5월 29일부터)
            try:
                pnl_records = await self.get_account_book(
                    type="pnl",
                    start_time=start_timestamp,
                    limit=1000
                )
                
                for record in pnl_records:
                    change = float(record.get('change', 0))
                    total_pnl += change
                    
                logger.info(f"Gate.io 5월 29일부터 PnL: ${total_pnl:.2f}")
            except Exception as e:
                logger.error(f"PnL 조회 실패: {e}")
            
            # 수수료 조회 (5월 29일부터)
            try:
                fee_records = await self.get_account_book(
                    type="fee",
                    start_time=start_timestamp,
                    limit=1000
                )
                
                for record in fee_records:
                    total_fee += abs(float(record.get('change', 0)))
                    
                logger.info(f"Gate.io 5월 29일부터 수수료: ${total_fee:.2f}")
            except Exception as e:
                logger.error(f"수수료 조회 실패: {e}")
            
            # 펀딩비 조회 (5월 29일부터)
            try:
                fund_records = await self.get_account_book(
                    type="fund",
                    start_time=start_timestamp,
                    limit=1000
                )
                
                for record in fund_records:
                    total_fund += float(record.get('change', 0))
                    
                logger.info(f"Gate.io 5월 29일부터 펀딩비: ${total_fund:.2f}")
            except Exception as e:
                logger.error(f"펀딩비 조회 실패: {e}")
            
            # 5월 29일부터의 순수익 = 실현손익 - 수수료 + 펀딩비
            cumulative_net_profit = total_pnl - total_fee + total_fund
            
            # 7일간 손익 계산
            weekly_pnl = 0.0
            today_pnl = 0.0
            weekly_fee = 0.0
            
            # 현재가 거래 시작일로부터 7일이 안 되었을 경우
            actual_start_timestamp = max(seven_days_timestamp, start_timestamp)
            
            # PnL 조회 (최근 7일 또는 거래 시작일부터)
            try:
                pnl_records = await self.get_account_book(
                    type="pnl",
                    start_time=actual_start_timestamp,
                    limit=1000
                )
                
                for record in pnl_records:
                    change = float(record.get('change', 0))
                    record_time = int(record.get('time', 0))
                    
                    weekly_pnl += change
                    
                    # 오늘 손익
                    if record_time >= today_timestamp:
                        today_pnl += change
            except Exception as e:
                logger.error(f"주간 PnL 조회 실패: {e}")
            
            # 수수료 조회 (최근 7일 또는 거래 시작일부터)
            try:
                fee_records = await self.get_account_book(
                    type="fee",
                    start_time=actual_start_timestamp,
                    limit=1000
                )
                
                for record in fee_records:
                    weekly_fee += abs(float(record.get('change', 0)))
            except Exception as e:
                logger.error(f"주간 수수료 조회 실패: {e}")
            
            # 7일 순수익
            weekly_net = weekly_pnl - weekly_fee
            
            # 실제 거래 일수 계산
            days_traded = min(7, (now - self.GATE_START_DATE).days + 1)
            
            logger.info(f"Gate.io 거래 일수: {days_traded}일")
            logger.info(f"Gate.io 7일 손익 - PnL: ${weekly_pnl:.2f}, Fee: ${weekly_fee:.2f}, Net: ${weekly_net:.2f}")
            logger.info(f"Gate.io 오늘 실현 손익: ${today_pnl:.2f}")
            
            # 실제 수익 = 현재 잔고 - 초기 자본
            actual_profit = current_balance - initial_capital
            
            return {
                'total': cumulative_net_profit,
                'weekly': {
                    'total': weekly_net,
                    'average': weekly_net / days_traded if days_traded > 0 else 0
                },
                'today_realized': today_pnl,
                'current_balance': current_balance,
                'initial_capital': initial_capital,
                'actual_profit': actual_profit,
                'days_traded': days_traded
            }
            
        except Exception as e:
            logger.error(f"Gate 손익 내역 조회 실패: {e}")
            # 폴백: 현재 잔고 기반 계산
            try:
                account = await self.get_account_balance()
                total_equity = float(account.get('total', 0))
                # 초기 자본 700 달러 기준
                total_pnl = total_equity - 700
                
                logger.info(f"Gate.io 폴백 계산: 현재 ${total_equity:.2f} - 초기 $700 = ${total_pnl:.2f}")
                
                return {
                    'total': total_pnl,
                    'weekly': {
                        'total': 0,
                        'average': 0
                    },
                    'today_realized': 0.0,
                    'current_balance': total_equity,
                    'initial_capital': 700,
                    'actual_profit': total_pnl,
                    'error': f"상세 내역 조회 실패: {str(e)[:100]}"
                }
            except Exception as fallback_error:
                logger.error(f"폴백 계산도 실패: {fallback_error}")
                return {
                    'total': 0,
                    'weekly': {'total': 0, 'average': 0},
                    'today_realized': 0,
                    'current_balance': 0,
                    'initial_capital': 700,
                    'actual_profit': 0,
                    'error': f"전체 조회 실패: {str(e)[:100]}"
                }
    
    async def test_connection(self) -> Dict:
        """연결 테스트 및 기본 정보 확인"""
        try:
            logger.info("Gate.io 연결 테스트 시작")
            
            # 1. 계정 잔고 조회
            account = await self.get_account_balance()
            balance = float(account.get('total', 0))
            
            # 2. 레버리지 정보 조회
            leverage_info = await self.get_leverage_info()
            
            # 3. 계약 정보 조회
            contract_info = await self.get_contract_info()
            
            result = {
                'connection': 'success',
                'balance': balance,
                'leverage': leverage_info.get('leverage', 'N/A'),
                'mode': leverage_info.get('mode', 'N/A'),
                'contract': contract_info.get('name', 'BTC_USDT'),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Gate.io 연결 테스트 성공: 잔고 ${balance:.2f}, 레버리지 {leverage_info.get('leverage')}x")
            return result
            
        except Exception as e:
            logger.error(f"❌ Gate.io 연결 테스트 실패: {e}")
            return {
                'connection': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Gate.io 클라이언트 세션 종료")
