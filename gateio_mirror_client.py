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

class GateioMirrorClient:
    """Gate.io 미러링 전용 클라이언트"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config.GATE_API_KEY
        self.api_secret = config.GATE_API_SECRET
        self.base_url = "https://api.gateio.ws"
        self.session = None
        self._initialize_session()
        
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
            logger.info("Gate.io 미러링 클라이언트 세션 초기화 완료")
    
    async def initialize(self):
        """클라이언트 초기화"""
        self._initialize_session()
        logger.info("Gate.io 미러링 클라이언트 초기화 완료")
    
    def _generate_signature(self, method: str, url: str, query_string: str = "", payload: str = "") -> Dict[str, str]:
        """Gate.io API 서명 생성"""
        timestamp = str(int(time.time()))
        
        hashed_payload = hashlib.sha512(payload.encode('utf-8')).hexdigest()
        s = f"{method}\n{url}\n{query_string}\n{hashed_payload}\n{timestamp}"
        
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
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None, max_retries: int = 3) -> Dict:
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
        
        for attempt in range(max_retries):
            try:
                headers = self._generate_signature(method, endpoint, query_string, payload)
                
                logger.debug(f"Gate.io API 요청 (시도 {attempt + 1}/{max_retries}): {method} {endpoint}")
                
                async with self.session.request(method, url, headers=headers, data=payload) as response:
                    response_text = await response.text()
                    
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: {response_text}"
                        logger.error(f"Gate.io API 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise Exception(error_msg)
                    
                    if not response_text.strip():
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise Exception("빈 응답")
                    
                    try:
                        return json.loads(response_text)
                    except json.JSONDecodeError as e:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise Exception(f"JSON 파싱 실패: {e}")
                            
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise Exception("요청 타임아웃")
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise
    
    async def get_current_price(self, contract: str = "BTC_USDT") -> float:
        """현재 시장가 조회"""
        try:
            ticker = await self.get_ticker(contract)
            if ticker:
                current_price = float(ticker.get('last', ticker.get('mark_price', 0)))
                return current_price
            return 0.0
        except Exception as e:
            logger.error(f"현재가 조회 실패: {e}")
            return 0.0
    
    async def get_ticker(self, contract: str = "BTC_USDT") -> Dict:
        """티커 정보 조회"""
        try:
            endpoint = f"/api/v4/futures/usdt/tickers"
            params = {'contract': contract}
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list) and len(response) > 0:
                ticker_data = response[0]
                if 'last' not in ticker_data and 'mark_price' in ticker_data:
                    ticker_data['last'] = ticker_data['mark_price']
                return ticker_data
            elif isinstance(response, dict):
                if 'last' not in response and 'mark_price' in response:
                    response['last'] = response['mark_price']
                return response
            else:
                return {}
            
        except Exception as e:
            logger.error(f"Gate.io 티커 조회 실패: {e}")
            return {}
    
    async def get_account_balance(self) -> Dict:
        """계정 잔고 조회"""
        try:
            endpoint = "/api/v4/futures/usdt/accounts"
            response = await self._request('GET', endpoint)
            return response
        except Exception as e:
            logger.error(f"계정 잔고 조회 실패: {e}")
            raise
    
    async def get_positions(self, contract: str = "BTC_USDT") -> List[Dict]:
        """포지션 조회"""
        try:
            endpoint = f"/api/v4/futures/usdt/positions/{contract}"
            response = await self._request('GET', endpoint)
            
            if isinstance(response, dict):
                return [response] if response.get('size', 0) != 0 else []
            return response
            
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []
    
    async def set_leverage(self, contract: str, leverage: int, cross_leverage_limit: int = 0, 
                          retry_count: int = 5) -> Dict:
        """레버리지 설정"""
        for attempt in range(retry_count):
            try:
                endpoint = f"/api/v4/futures/usdt/positions/{contract}/leverage"
                
                data = {
                    "leverage": str(leverage),
                    "cross_leverage_limit": str(cross_leverage_limit) if cross_leverage_limit > 0 else "0"
                }
                
                try:
                    positions = await self.get_positions(contract)
                    if positions and len(positions) > 0:
                        current_pos = positions[0]
                        if 'mode' in current_pos:
                            data["mode"] = current_pos.get('mode', 'single')
                        else:
                            data["mode"] = "single"
                    else:
                        data["mode"] = "single"
                except Exception:
                    data["mode"] = "single"
                
                logger.info(f"Gate.io 레버리지 설정 시도 {attempt + 1}/{retry_count}: {contract} - {leverage}x")
                
                response = await self._request('POST', endpoint, data=data)
                
                await asyncio.sleep(1.0)
                
                verify_success = await self._verify_leverage_setting(contract, leverage, max_attempts=3)
                if verify_success:
                    logger.info(f"✅ Gate.io 레버리지 설정 완료: {contract} - {leverage}x")
                    return response
                else:
                    if attempt < retry_count - 1:
                        await asyncio.sleep(2.0)
                        continue
                    else:
                        return response
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Gate.io 레버리지 설정 시도 {attempt + 1} 실패: {error_msg}")
                
                if "MISSING_REQUIRED_PARAM" in error_msg:
                    try:
                        basic_data = {"leverage": str(leverage)}
                        response = await self._request('POST', endpoint, data=basic_data)
                        await asyncio.sleep(1.0)
                        return response
                    except Exception as basic_error:
                        logger.warning(f"기본 레버리지 설정도 실패: {basic_error}")
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(2.0)
                    continue
                else:
                    raise
        
        raise Exception(f"레버리지 설정 최대 재시도 횟수 초과: {contract} - {leverage}x")
    
    async def _verify_leverage_setting(self, contract: str, expected_leverage: int, max_attempts: int = 3) -> bool:
        """레버리지 설정 확인"""
        for attempt in range(max_attempts):
            try:
                await asyncio.sleep(0.5 * (attempt + 1))
                
                positions = await self.get_positions(contract)
                if positions:
                    position = positions[0]
                    current_leverage = position.get('leverage')
                    
                    if current_leverage:
                        try:
                            current_lev_int = int(float(current_leverage))
                            if current_lev_int == expected_leverage:
                                return True
                            else:
                                if attempt < max_attempts - 1:
                                    continue
                                return False
                        except (ValueError, TypeError):
                            if attempt < max_attempts - 1:
                                continue
                            return False
                    else:
                        if attempt < max_attempts - 1:
                            continue
                        return False
                else:
                    return True
                
            except Exception:
                if attempt < max_attempts - 1:
                    continue
                return True
        
        return False
    
    async def create_perfect_mirror_order(self, bitget_order: Dict, gate_price: float, gate_margin: float, 
                                        gate_size: int, leverage: int) -> Dict:
        """🔥 완벽한 미러링 주문 생성 - TP/SL 포함"""
        try:
            # 비트겟 주문 정보 추출
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            trigger_price = 0
            
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            # TP/SL 정보 추출 (강화된 방식)
            tp_price = None
            sl_price = None
            
            # TP 추출
            tp_fields = ['presetStopSurplusPrice', 'stopSurplusPrice', 'takeProfitPrice', 'tpPrice', 'stopProfit']
            for field in tp_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        tp_price = float(value)
                        if tp_price > 0:
                            logger.info(f"🎯 비트겟 TP 추출: {field} = {tp_price}")
                            break
                    except:
                        continue
            
            # SL 추출
            sl_fields = ['presetStopLossPrice', 'stopLossPrice', 'stopPrice', 'slPrice', 'lossPrice']
            for field in sl_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        sl_price = float(value)
                        if sl_price > 0:
                            logger.info(f"🛡️ 비트겟 SL 추출: {field} = {sl_price}")
                            break
                    except:
                        continue
            
            # 클로즈 주문 여부 판단
            reduce_only = bitget_order.get('reduceOnly', False)
            is_close_order = ('close' in side or reduce_only is True or reduce_only == 'true')
            
            # Gate.io 트리거 타입 결정
            gate_trigger_type = "ge" if trigger_price > gate_price else "le"
            
            # Gate.io 사이즈 조정 (방향 포함)
            if is_close_order:
                # 클로즈 주문: reduce_only=True
                final_size = gate_size
                reduce_only_flag = True
            else:
                # 오픈 주문: reduce_only=False
                if 'short' in side or 'sell' in side:
                    final_size = -abs(gate_size)
                else:
                    final_size = abs(gate_size)
                reduce_only_flag = False
            
            logger.info(f"🔍 주문 정보 최종 확인:")
            logger.info(f"   - 비트겟 ID: {order_id}")
            logger.info(f"   - 방향: {side}")
            logger.info(f"   - 트리거가: ${trigger_price:.2f}")
            logger.info(f"   - TP: ${tp_price:.2f if tp_price else 0}")
            logger.info(f"   - SL: ${sl_price:.2f if sl_price else 0}")
            logger.info(f"   - 게이트 사이즈: {final_size}")
            logger.info(f"   - 클로즈 주문: {is_close_order}")
            
            # 🔥 Gate.io 통합 TP/SL 주문 생성
            if tp_price or sl_price:
                logger.info(f"🎯 TP/SL 포함 통합 주문 생성")
                
                gate_order = await self.create_unified_order_with_tp_sl(
                    trigger_type=gate_trigger_type,
                    trigger_price=str(trigger_price),
                    order_type="market",
                    contract="BTC_USDT",
                    size=final_size,
                    tp_price=str(tp_price) if tp_price else None,
                    sl_price=str(sl_price) if sl_price else None,
                    reduce_only=reduce_only_flag
                )
                
                # TP/SL 설정 결과 확인
                has_tp_sl = gate_order.get('has_tp_sl', False)
                actual_tp = gate_order.get('stop_profit_price', '')
                actual_sl = gate_order.get('stop_loss_price', '')
                
                result = {
                    'success': True,
                    'gate_order_id': gate_order.get('id'),
                    'gate_order': gate_order,
                    'has_tp_sl': has_tp_sl,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'actual_tp_price': actual_tp,
                    'actual_sl_price': actual_sl,
                    'is_close_order': is_close_order,
                    'reduce_only': reduce_only_flag,
                    'perfect_mirror': has_tp_sl and (tp_price or sl_price)
                }
                
                if has_tp_sl:
                    logger.info(f"✅ 완벽한 TP/SL 미러링 성공: {order_id}")
                else:
                    logger.warning(f"⚠️ TP/SL 설정 부분 실패: {order_id}")
                
                return result
                
            else:
                # TP/SL 없는 일반 주문
                logger.info(f"📝 일반 예약 주문 생성 (TP/SL 없음)")
                
                gate_order = await self.create_price_triggered_order(
                    trigger_type=gate_trigger_type,
                    trigger_price=str(trigger_price),
                    order_type="market",
                    contract="BTC_USDT",
                    size=final_size,
                    reduce_only=reduce_only_flag
                )
                
                return {
                    'success': True,
                    'gate_order_id': gate_order.get('id'),
                    'gate_order': gate_order,
                    'has_tp_sl': False,
                    'is_close_order': is_close_order,
                    'reduce_only': reduce_only_flag,
                    'perfect_mirror': True  # TP/SL이 없으면 완벽
                }
            
        except Exception as e:
            logger.error(f"완벽한 미러링 주문 생성 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'has_tp_sl': False,
                'perfect_mirror': False
            }
    
    async def create_unified_order_with_tp_sl(self, trigger_type: str, trigger_price: str,
                                           order_type: str, contract: str, size: int,
                                           tp_price: Optional[str] = None,
                                           sl_price: Optional[str] = None,
                                           reduce_only: bool = False) -> Dict:
        """TP/SL 포함 통합 주문 생성"""
        try:
            # 트리거 가격 유효성 검증
            trigger_price_float = float(trigger_price)
            is_valid, validation_msg, adjusted_price = await self.validate_trigger_price(
                trigger_price_float, trigger_type, contract
            )
            
            if not is_valid:
                raise Exception(f"트리거 가격 유효성 검증 실패: {validation_msg}")
            
            if adjusted_price != trigger_price_float:
                trigger_price = str(adjusted_price)
                logger.info(f"🔧 트리거 가격 조정: {trigger_price_float:.2f} → {adjusted_price:.2f}")
            
            endpoint = "/api/v4/futures/usdt/price_orders"
            
            initial_data = {
                "type": order_type,
                "contract": contract,
                "size": size
            }
            
            if reduce_only:
                initial_data["reduce_only"] = True
                logger.info(f"🔴 클로즈 주문: reduce_only=True")
            else:
                logger.info(f"🟢 오픈 주문: reduce_only 미설정")
            
            # Gate.io API 요구사항에 따라 시장가에도 price 필수
            initial_data["price"] = str(trigger_price)
            
            # 트리거 rule 설정
            rule_value = 1 if trigger_type == "ge" else 2
            
            data = {
                "initial": initial_data,
                "trigger": {
                    "strategy_type": 0,
                    "price_type": 0,
                    "price": str(trigger_price),
                    "rule": rule_value
                }
            }
            
            # TP/SL 설정
            has_tp_sl = False
            if tp_price and float(tp_price) > 0:
                data["stop_profit_price"] = str(tp_price)
                has_tp_sl = True
                logger.info(f"🎯 TP 설정: ${tp_price}")
            
            if sl_price and float(sl_price) > 0:
                data["stop_loss_price"] = str(sl_price)
                has_tp_sl = True
                logger.info(f"🛡️ SL 설정: ${sl_price}")
            
            logger.info(f"Gate.io 통합 TP/SL 주문 생성: {data}")
            response = await self._request('POST', endpoint, data=data)
            
            # 응답 검증
            actual_tp = response.get('stop_profit_price', '')
            actual_sl = response.get('stop_loss_price', '')
            
            response.update({
                'has_tp_sl': has_tp_sl and (actual_tp or actual_sl),
                'requested_tp': tp_price,
                'requested_sl': sl_price,
                'reduce_only': reduce_only
            })
            
            if has_tp_sl:
                if actual_tp:
                    logger.info(f"✅ TP 설정 확인: ${actual_tp}")
                if actual_sl:
                    logger.info(f"✅ SL 설정 확인: ${actual_sl}")
            
            return response
            
        except Exception as e:
            logger.error(f"통합 TP/SL 주문 생성 실패: {e}")
            raise
    
    async def create_price_triggered_order(self, trigger_type: str, trigger_price: str,
                                         order_type: str, contract: str, size: int,
                                         reduce_only: bool = False) -> Dict:
        """일반 가격 트리거 주문 생성"""
        try:
            trigger_price_float = float(trigger_price)
            is_valid, validation_msg, adjusted_price = await self.validate_trigger_price(
                trigger_price_float, trigger_type, contract
            )
            
            if not is_valid:
                raise Exception(f"트리거 가격 유효성 검증 실패: {validation_msg}")
            
            if adjusted_price != trigger_price_float:
                trigger_price = str(adjusted_price)
            
            endpoint = "/api/v4/futures/usdt/price_orders"
            
            initial_data = {
                "type": order_type,
                "contract": contract,
                "size": size,
                "price": str(trigger_price)
            }
            
            if reduce_only:
                initial_data["reduce_only"] = True
            
            rule_value = 1 if trigger_type == "ge" else 2
            
            data = {
                "initial": initial_data,
                "trigger": {
                    "strategy_type": 0,
                    "price_type": 0,
                    "price": str(trigger_price),
                    "rule": rule_value
                }
            }
            
            response = await self._request('POST', endpoint, data=data)
            return response
            
        except Exception as e:
            logger.error(f"가격 트리거 주문 생성 실패: {e}")
            raise
    
    async def validate_trigger_price(self, trigger_price: float, trigger_type: str, 
                                   contract: str) -> Tuple[bool, str, float]:
        """트리거 가격 유효성 검증 및 조정"""
        try:
            current_price = await self.get_current_price(contract)
            if current_price == 0:
                return False, "현재가 조회 실패", trigger_price
            
            price_diff_percent = abs(trigger_price - current_price) / current_price * 100
            
            # 가격이 너무 근접한 경우 조정
            if price_diff_percent < 0.01:
                if trigger_type == "ge":
                    adjusted_price = current_price * 1.0005
                elif trigger_type == "le":
                    adjusted_price = current_price * 0.9995
                else:
                    adjusted_price = trigger_price
                
                return True, "가격 조정됨", adjusted_price
            
            # Gate.io 규칙 검증
            if trigger_type == "ge":
                if trigger_price <= current_price:
                    adjusted_price = current_price * 1.001
                    return True, "GE 가격 조정됨", adjusted_price
                else:
                    return True, "유효한 GE 트리거가", trigger_price
            elif trigger_type == "le":
                if trigger_price >= current_price:
                    adjusted_price = current_price * 0.999
                    return True, "LE 가격 조정됨", adjusted_price
                else:
                    return True, "유효한 LE 트리거가", trigger_price
            
            return True, "유효한 트리거가", trigger_price
            
        except Exception as e:
            logger.error(f"트리거 가격 검증 실패: {e}")
            return False, f"검증 오류: {str(e)}", trigger_price
    
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
            logger.error(f"가격 트리거 주문 취소 실패: {order_id} - {e}")
            raise
    
    async def place_order(self, contract: str, size: int, price: Optional[float] = None,
                         reduce_only: bool = False, tif: str = "gtc", iceberg: int = 0) -> Dict:
        """시장가/지정가 주문 생성"""
        try:
            endpoint = "/api/v4/futures/usdt/orders"
            
            data = {
                "contract": contract,
                "size": size
            }
            
            if price is not None:
                data["price"] = str(price)
                data["tif"] = tif
            
            if reduce_only:
                data["reduce_only"] = True
            
            if iceberg > 0:
                data["iceberg"] = iceberg
            
            response = await self._request('POST', endpoint, data=data)
            return response
            
        except Exception as e:
            logger.error(f"Gate.io 주문 생성 실패: {e}")
            raise
    
    async def close_position(self, contract: str, size: Optional[int] = None) -> Dict:
        """포지션 종료"""
        try:
            positions = await self.get_positions(contract)
            
            if not positions or positions[0].get('size', 0) == 0:
                return {"status": "no_position"}
            
            position = positions[0]
            position_size = int(position['size'])
            
            if size is None:
                close_size = -position_size
            else:
                if position_size > 0:
                    close_size = -min(abs(size), position_size)
                else:
                    close_size = min(abs(size), abs(position_size))
            
            result = await self.place_order(
                contract=contract,
                size=close_size,
                price=None,
                reduce_only=True
            )
            
            return result
            
        except Exception as e:
            logger.error(f"포지션 종료 실패: {e}")
            raise
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Gate.io 미러링 클라이언트 세션 종료")
