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
    """Gate.io 미러링 전용 클라이언트 - 포지션 크기 기반 클로즈 주문 처리 강화 + 슬리피지 보호 개선 + 정확한 포지션 매칭"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config.GATE_API_KEY
        self.api_secret = config.GATE_API_SECRET
        self.base_url = "https://api.gateio.ws"
        self.session = None
        self._initialize_session()
        
        # TP/SL 설정 상수
        self.TP_SL_TIMEOUT = 10
        self.MAX_TP_SL_RETRIES = 3
        
        # 🔥🔥🔥 슬리피지 보호 설정 개선 - 0.05% (약 50달러)
        self.MAX_SLIPPAGE_PERCENT = 0.05  # 최대 슬리피지 0.05% (약 50달러)
        self.SLIPPAGE_CHECK_ENABLED = True
        self.FALLBACK_TO_LIMIT_ORDER = True
        
        # 🔥🔥🔥 지정가 주문 대기 시간 설정
        self.LIMIT_ORDER_WAIT_TIME = 5  # 지정가 주문 5초 대기
        self.LIMIT_ORDER_RETRIES = 2  # 지정가 주문 2회 재시도
        
        # 텔레그램 봇 참조 (알림용)
        self.telegram_bot = None
        
    def set_telegram_bot(self, telegram_bot):
        """텔레그램 봇 설정"""
        self.telegram_bot = telegram_bot
        
    def _initialize_session(self):
        """세션 초기화 - 타임아웃 증가"""
        if not self.session:
            # 🔥🔥🔥 타임아웃 설정 개선
            timeout = aiohttp.ClientTimeout(total=60, connect=20)  # 타임아웃 증가
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
            logger.info("Gate.io 미러링 클라이언트 세션 초기화 완료 (개선된 타임아웃)")
    
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
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None, max_retries: int = 5) -> Dict:
        """API 요청 - 강화된 재시도 로직"""
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
                
                # 🔥🔥🔥 각 시도마다 타임아웃 점진적 증가
                attempt_timeout = aiohttp.ClientTimeout(total=30 + (attempt * 10), connect=10 + (attempt * 5))
                
                async with self.session.request(
                    method, url, headers=headers, data=payload, timeout=attempt_timeout
                ) as response:
                    response_text = await response.text()
                    
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: {response_text}"
                        logger.error(f"Gate.io API 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) + (attempt * 0.5)  # 지수 백오프 + 추가 지연
                            await asyncio.sleep(wait_time)
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
                        result = json.loads(response_text)
                        logger.debug(f"Gate.io API 응답 성공: {method} {endpoint}")
                        return result
                    except json.JSONDecodeError as e:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise Exception(f"JSON 파싱 실패: {e}")
                            
            except asyncio.TimeoutError:
                logger.warning(f"Gate.io API 타임아웃 (시도 {attempt + 1}/{max_retries}): {method} {endpoint}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(3 + (attempt * 2))  # 타임아웃 시 더 긴 대기
                    continue
                else:
                    raise Exception(f"요청 타임아웃 (최대 {max_retries}회 시도)")
                    
            except aiohttp.ClientError as e:
                logger.warning(f"Gate.io API 클라이언트 오류 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise Exception(f"클라이언트 오류: {e}")
                    
            except Exception as e:
                logger.error(f"Gate.io API 예상치 못한 오류 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise
    
    async def get_current_price(self, contract: str = "BTC_USDT") -> float:
        """현재 시장가 조회 - 강화된 재시도"""
        try:
            ticker = await self.get_ticker(contract)
            if ticker:
                current_price = float(ticker.get('last', ticker.get('mark_price', 0)))
                if current_price > 0:
                    return current_price
                    
            # 가격이 0이거나 None인 경우 재시도
            await asyncio.sleep(1)
            ticker_retry = await self.get_ticker(contract)
            if ticker_retry:
                current_price = float(ticker_retry.get('last', ticker_retry.get('mark_price', 0)))
                return current_price
                
            return 0.0
        except Exception as e:
            logger.error(f"현재가 조회 실패: {e}")
            return 0.0
    
    async def get_ticker(self, contract: str = "BTC_USDT") -> Dict:
        """티커 정보 조회 - 강화된 오류 처리"""
        try:
            endpoint = f"/api/v4/futures/usdt/tickers"
            params = {'contract': contract}
            response = await self._request('GET', endpoint, params=params, max_retries=3)
            
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
        """🔥🔥🔥 포지션 조회 - 정확한 포지션 정보 반환"""
        try:
            endpoint = f"/api/v4/futures/usdt/positions/{contract}"
            response = await self._request('GET', endpoint)
            
            if isinstance(response, dict):
                size = response.get('size', 0)
                if size != 0:
                    logger.info(f"🔍 게이트 포지션 발견: 계약={contract}, 크기={size}")
                    logger.info(f"  - 진입가: {response.get('entry_price', 'N/A')}")
                    logger.info(f"  - 미실현 손익: {response.get('unrealised_pnl', 'N/A')}")
                    logger.info(f"  - 레버리지: {response.get('leverage', 'N/A')}")
                    return [response]
                else:
                    logger.debug(f"게이트 포지션 없음: {contract}")
                    return []
            
            return response if isinstance(response, list) else []
            
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []
    
    async def set_leverage(self, contract: str, leverage: int, cross_leverage_limit: int = 0, 
                          retry_count: int = 5) -> Dict:
        """🔥 레버리지 설정 - Gate.io API 수정된 방식 (오류 수정)"""
        for attempt in range(retry_count):
            try:
                endpoint = f"/api/v4/futures/usdt/positions/{contract}/leverage"
                
                # 🔥🔥🔥 Gate.io API v4 정확한 형식
                # API 문서에 따르면 쿼리 파라미터로 전송해야 함
                params = {
                    "leverage": str(leverage)
                }
                
                if cross_leverage_limit > 0:
                    params["cross_leverage_limit"] = str(cross_leverage_limit)
                
                logger.info(f"Gate.io 레버리지 설정 시도 {attempt + 1}/{retry_count}: {contract} - {leverage}x")
                logger.debug(f"레버리지 설정 파라미터: {params}")
                
                # POST 요청이지만 파라미터로 전송
                response = await self._request('POST', endpoint, params=params)
                
                await asyncio.sleep(1.0)
                
                # 설정 검증
                verify_success = await self._verify_leverage_setting(contract, leverage, max_attempts=3)
                if verify_success:
                    logger.info(f"✅ Gate.io 레버리지 설정 완료: {contract} - {leverage}x")
                    return response
                else:
                    if attempt < retry_count - 1:
                        await asyncio.sleep(2.0)
                        continue
                    else:
                        logger.warning(f"레버리지 설정 검증 실패하지만 계속 진행: {contract} - {leverage}x")
                        return response
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Gate.io 레버리지 설정 시도 {attempt + 1} 실패: {error_msg}")
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(2.0)
                    continue
                else:
                    # 🔥🔥🔥 레버리지 설정 실패해도 계속 진행 (경고만 출력)
                    logger.warning(f"레버리지 설정 최종 실패하지만 계속 진행: {contract} - {leverage}x")
                    return {"warning": "leverage_setting_failed", "requested_leverage": leverage}
        
        # 모든 시도 실패해도 경고만 출력하고 계속 진행
        logger.warning(f"레버리지 설정 모든 재시도 실패, 기본 레버리지로 계속 진행: {contract} - {leverage}x")
        return {"warning": "all_leverage_attempts_failed", "requested_leverage": leverage}
    
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
    
    async def _check_slippage_protection(self, current_price: float, expected_price: float, side: str) -> Tuple[bool, str]:
        """🔥🔥🔥 슬리피지 보호 체크 - 0.05% 임계값"""
        try:
            if not self.SLIPPAGE_CHECK_ENABLED:
                return True, "슬리피지 체크 비활성화"
            
            if current_price <= 0 or expected_price <= 0:
                return True, "가격 정보 부족으로 체크 스킵"
            
            # 슬리피지 계산
            if side.lower() == 'buy':
                # 매수: 현재가보다 높게 체결될 위험
                slippage_percent = ((expected_price - current_price) / current_price) * 100
            else:
                # 매도: 현재가보다 낮게 체결될 위험
                slippage_percent = ((current_price - expected_price) / current_price) * 100
            
            if slippage_percent > self.MAX_SLIPPAGE_PERCENT:
                slippage_amount = current_price * (slippage_percent / 100)
                return False, f"슬리피지 위험 ({slippage_percent:.3f}%, 약 ${slippage_amount:.2f}) > 임계값 {self.MAX_SLIPPAGE_PERCENT}%"
            
            slippage_amount = current_price * (slippage_percent / 100)
            return True, f"슬리피지 안전 ({slippage_percent:.3f}%, 약 ${slippage_amount:.2f})"
            
        except Exception as e:
            logger.error(f"슬리피지 보호 체크 실패: {e}")
            return True, "슬리피지 체크 오류, 진행"
    
    async def _place_limit_order_with_wait(self, contract: str, size: int, limit_price: float,
                                          reduce_only: bool = False) -> Tuple[Dict, bool]:
        """🔥🔥🔥 지정가 주문 대기 후 체결 확인"""
        try:
            logger.info(f"지정가 주문 생성: {size} @ ${limit_price:.2f} (대기시간: {self.LIMIT_ORDER_WAIT_TIME}초)")
            
            # 지정가 주문 생성
            order_result = await self.place_order(
                contract=contract,
                size=size,
                price=limit_price,
                reduce_only=reduce_only,
                tif="gtc",
                use_slippage_protection=False  # 이미 지정가로 보호됨
            )
            
            order_id = order_result.get('id')
            if not order_id:
                return order_result, False
            
            # 지정가 주문 대기
            await asyncio.sleep(self.LIMIT_ORDER_WAIT_TIME)
            
            # 주문 상태 확인
            order_status = await self._check_order_status(order_id)
            
            if order_status.get('status') == 'filled':
                logger.info(f"✅ 지정가 주문 체결 성공: {order_id}")
                return order_result, True
            else:
                logger.info(f"⏰ 지정가 주문 미체결, 취소 후 시장가 전환: {order_id}")
                try:
                    await self._cancel_order(order_id)
                except:
                    pass  # 취소 실패해도 계속 진행
                return order_result, False
                
        except Exception as e:
            logger.error(f"지정가 주문 대기 처리 실패: {e}")
            return {}, False
    
    async def _check_order_status(self, order_id: str) -> Dict:
        """주문 상태 확인"""
        try:
            endpoint = f"/api/v4/futures/usdt/orders/{order_id}"
            return await self._request('GET', endpoint)
        except Exception as e:
            logger.error(f"주문 상태 확인 실패: {order_id} - {e}")
            return {}
    
    async def _cancel_order(self, order_id: str) -> Dict:
        """주문 취소"""
        try:
            endpoint = f"/api/v4/futures/usdt/orders/{order_id}"
            return await self._request('DELETE', endpoint)
        except Exception as e:
            logger.error(f"주문 취소 실패: {order_id} - {e}")
            return {}
    
    async def _place_order_with_slippage_protection(self, contract: str, size: int, 
                                                   reduce_only: bool = False, 
                                                   max_retries: int = 2) -> Dict:
        """🔥🔥🔥 슬리피지 보호가 적용된 주문 생성 - 지정가 대기 후 시장가 전환"""
        try:
            side = 'buy' if size > 0 else 'sell'
            
            for attempt in range(max_retries):
                try:
                    # 현재가 조회
                    current_price = await self.get_current_price(contract)
                    if current_price <= 0:
                        logger.warning("현재가 조회 실패, 일반 시장가 주문으로 진행")
                        return await self.place_order(contract, size, None, reduce_only, use_slippage_protection=False)
                    
                    logger.info(f"슬리피지 보호 주문 시도 {attempt + 1}/{max_retries}: {side} {abs(size)} @ ${current_price:.2f}")
                    
                    # 시장가로 체결될 예상 가격 (스프레드 고려)
                    ticker = await self.get_ticker(contract)
                    if ticker:
                        bid_price = float(ticker.get('bid', current_price))
                        ask_price = float(ticker.get('ask', current_price))
                        
                        if side == 'buy':
                            expected_price = ask_price  # 매수는 ask에 체결
                            # 지정가는 현재가보다 약간 유리하게 설정
                            limit_price = current_price * (1 + (self.MAX_SLIPPAGE_PERCENT * 0.5) / 100)
                        else:
                            expected_price = bid_price  # 매도는 bid에 체결
                            # 지정가는 현재가보다 약간 유리하게 설정
                            limit_price = current_price * (1 - (self.MAX_SLIPPAGE_PERCENT * 0.5) / 100)
                    else:
                        expected_price = current_price
                        if side == 'buy':
                            limit_price = current_price * (1 + (self.MAX_SLIPPAGE_PERCENT * 0.5) / 100)
                        else:
                            limit_price = current_price * (1 - (self.MAX_SLIPPAGE_PERCENT * 0.5) / 100)
                    
                    # 슬리피지 보호 체크
                    is_safe, protection_msg = await self._check_slippage_protection(
                        current_price, expected_price, side
                    )
                    
                    logger.info(f"슬리피지 보호: {protection_msg}")
                    
                    if is_safe:
                        # 안전한 경우 시장가 주문
                        result = await self.place_order(contract, size, None, reduce_only, use_slippage_protection=False)
                        logger.info(f"✅ 슬리피지 안전 범위내 시장가 주문 성공: {side} {abs(size)}")
                        return result
                    else:
                        # 위험한 경우 지정가 주문 시도 후 시장가 전환
                        if self.FALLBACK_TO_LIMIT_ORDER:
                            logger.warning(f"슬리피지 위험으로 지정가 주문 시도: {protection_msg}")
                            
                            # 지정가 주문 시도
                            limit_result, filled = await self._place_limit_order_with_wait(
                                contract, size, limit_price, reduce_only
                            )
                            
                            if filled:
                                logger.info(f"✅ 지정가 주문 체결 성공: {side} {abs(size)} @ ${limit_price:.2f}")
                                return limit_result
                            else:
                                # 지정가 실패 시 시장가로 전환하고 알림
                                logger.warning(f"지정가 주문 실패, 시장가로 전환: {side} {abs(size)}")
                                
                                # 시장가 주문
                                market_result = await self.place_order(
                                    contract, size, None, reduce_only, use_slippage_protection=False
                                )
                                
                                # 🔥🔥🔥 시장가 체결 텔레그램 알림
                                await self._send_market_order_alert(
                                    side, abs(size), current_price, protection_msg, contract
                                )
                                
                                logger.info(f"✅ 지정가 실패 후 시장가 주문 성공: {side} {abs(size)}")
                                return market_result
                        else:
                            # 지정가 전환 비활성화된 경우 그냥 시장가 진행
                            logger.warning(f"슬리피지 위험 감지되었지만 시장가로 진행: {protection_msg}")
                            result = await self.place_order(contract, size, None, reduce_only, use_slippage_protection=False)
                            
                            # 시장가 체결 알림
                            await self._send_market_order_alert(
                                side, abs(size), current_price, protection_msg, contract
                            )
                            return result
                    
                except Exception as e:
                    logger.error(f"슬리피지 보호 주문 시도 {attempt + 1} 실패: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1.0)
                        # 현재가 갱신
                        continue
                    else:
                        raise
            
            # 모든 재시도 실패 시 기본 시장가 주문
            logger.warning("모든 슬리피지 보호 시도 실패, 기본 시장가 주문으로 진행")
            result = await self.place_order(contract, size, None, reduce_only, use_slippage_protection=False)
            
            # 재시도 실패 알림
            if self.telegram_bot:
                await self.telegram_bot.send_message(
                    f"⚠️ 슬리피지 보호 재시도 실패\n"
                    f"방향: {'매수' if size > 0 else '매도'}\n"
                    f"수량: {abs(size)}\n"
                    f"최종적으로 시장가 주문으로 체결됨"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"슬리피지 보호 주문 실패: {e}")
            # 실패 시 기본 시장가 주문으로 폴백
            return await self.place_order(contract, size, None, reduce_only, use_slippage_protection=False)
    
    async def _send_market_order_alert(self, side: str, size: int, current_price: float, 
                                      protection_msg: str, contract: str):
        """🔥🔥🔥 시장가 주문 체결 텔레그램 알림"""
        try:
            if self.telegram_bot:
                side_text = '매수' if side == 'buy' else '매도'
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                alert_msg = f"""🛡️ 슬리피지 보호 시장가 체결 알림

⏰ 시간: {current_time}
📊 종목: {contract}
🔄 방향: {side_text}
📦 수량: {size}
💰 현재가: ${current_price:,.2f}

🚨 사유: {protection_msg}

💡 지정가 주문이 {self.LIMIT_ORDER_WAIT_TIME}초 대기 후 미체결되어 
   안전한 시장가 주문으로 전환되었습니다.
   
📈 이는 정상적인 슬리피지 보호 작동입니다."""
                
                await self.telegram_bot.send_message(alert_msg)
                logger.info(f"시장가 체결 알림 전송 완료: {side_text} {size}")
        except Exception as e:
            logger.error(f"시장가 체결 알림 전송 실패: {e}")
    
    async def create_perfect_tp_sl_order(self, bitget_order: Dict, gate_size: int, gate_margin: float, 
                                       leverage: int, current_gate_price: float) -> Dict:
        """🔥🔥🔥 완벽한 TP/SL 미러링 주문 생성 - 클로즈 주문 처리 강화 + 정확한 포지션 매칭"""
        try:
            # 비트겟 주문 정보 추출
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            
            # 트리거 가격 추출
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price <= 0:
                raise Exception("유효한 트리거 가격을 찾을 수 없습니다")
            
            # 🔥 TP/SL 정보 정확하게 추출
            tp_price = None
            sl_price = None
            
            # TP 추출 - 비트겟 공식 필드
            tp_fields = ['presetStopSurplusPrice', 'stopSurplusPrice', 'takeProfitPrice']
            for field in tp_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        tp_price = float(value)
                        if tp_price > 0:
                            logger.info(f"🎯 비트겟 TP 추출: {field} = ${tp_price:.2f}")
                            break
                    except:
                        continue
            
            # SL 추출 - 비트겟 공식 필드
            sl_fields = ['presetStopLossPrice', 'stopLossPrice', 'stopPrice']
            for field in sl_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        sl_price = float(value)
                        if sl_price > 0:
                            logger.info(f"🛡️ 비트겟 SL 추출: {field} = ${sl_price:.2f}")
                            break
                    except:
                        continue
            
            # 🔥🔥🔥 클로즈 주문 여부 및 방향 판단 강화
            reduce_only = bitget_order.get('reduceOnly', False)
            is_close_order = (
                'close' in side or 
                reduce_only is True or 
                reduce_only == 'true' or
                str(reduce_only).lower() == 'true'
            )
            
            # 🔥🔥🔥 클로즈 주문인 경우 현재 포지션 크기 기반 처리
            if is_close_order:
                final_size, reduce_only_flag = await self._calculate_close_order_size_based_on_position(
                    bitget_order, gate_size, side
                )
                logger.info(f"🔄 클로즈 주문 처리: 원본크기={gate_size} → 조정크기={final_size}")
            else:
                # 오픈 주문: 방향 고려
                reduce_only_flag = False
                if 'short' in side or 'sell' in side:
                    final_size = -abs(gate_size)
                    logger.info(f"🔴 오픈 숏: 새 숏 포지션 생성 → 게이트 매도 (음수 사이즈: {final_size})")
                else:
                    final_size = abs(gate_size)
                    logger.info(f"🟢 오픈 롱: 새 롱 포지션 생성 → 게이트 매수 (양수 사이즈: {final_size})")
            
            # Gate.io 트리거 타입 결정
            gate_trigger_type = "ge" if trigger_price > current_gate_price else "le"
            
            logger.info(f"🔍 완벽 미러링 주문 생성:")
            logger.info(f"   - 비트겟 ID: {order_id}")
            logger.info(f"   - 방향: {side} ({'클로즈' if is_close_order else '오픈'})")
            logger.info(f"   - 트리거가: ${trigger_price:.2f}")
            
            # TP/SL 표시 수정
            tp_display = f"${tp_price:.2f}" if tp_price is not None else "없음"
            sl_display = f"${sl_price:.2f}" if sl_price is not None else "없음"
            
            logger.info(f"   - TP: {tp_display}")
            logger.info(f"   - SL: {sl_display}")
            logger.info(f"   - 게이트 사이즈: {final_size}")
            
            # 🔥 TP/SL 포함 통합 주문 생성
            if tp_price or sl_price:
                logger.info(f"🎯 TP/SL 포함 통합 주문 생성")
                
                gate_order = await self.create_conditional_order_with_tp_sl(
                    trigger_price=trigger_price,
                    order_size=final_size,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    reduce_only=reduce_only_flag,
                    trigger_type=gate_trigger_type
                )
                
                # TP/SL 설정 확인
                actual_tp = gate_order.get('stop_profit_price', '')
                actual_sl = gate_order.get('stop_loss_price', '')
                has_tp_sl = bool(actual_tp or actual_sl)
                
                return {
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
                    'perfect_mirror': has_tp_sl,
                    'position_adjusted': is_close_order  # 포지션 기반 조정 여부
                }
                
            else:
                # TP/SL 없는 일반 주문
                logger.info(f"📝 일반 예약 주문 생성 (TP/SL 없음)")
                
                gate_order = await self.create_price_triggered_order(
                    trigger_price=trigger_price,
                    order_size=final_size,
                    reduce_only=reduce_only_flag,
                    trigger_type=gate_trigger_type
                )
                
                return {
                    'success': True,
                    'gate_order_id': gate_order.get('id'),
                    'gate_order': gate_order,
                    'has_tp_sl': False,
                    'is_close_order': is_close_order,
                    'reduce_only': reduce_only_flag,
                    'perfect_mirror': True,  # TP/SL이 없으면 완벽
                    'position_adjusted': is_close_order
                }
            
        except Exception as e:
            logger.error(f"완벽한 TP/SL 미러링 주문 생성 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'has_tp_sl': False,
                'perfect_mirror': False,
                'position_adjusted': False
            }
    
    async def _calculate_close_order_size_based_on_position(self, bitget_order: Dict, 
                                                           original_gate_size: int, 
                                                           side: str) -> Tuple[int, bool]:
        """🔥🔥🔥 현재 포지션 크기 기반 클로즈 주문 크기 계산 - 정확한 BTC 매칭"""
        try:
            # 현재 게이트 포지션 조회
            gate_positions = await self.get_positions("BTC_USDT")
            
            if not gate_positions:
                logger.warning(f"⚠️ 게이트에 포지션이 없어 원본 크기 사용: {original_gate_size}")
                # 포지션이 없으면 원본 크기로 클로즈 주문 생성 (reduce_only=True)
                if 'short' in side.lower() or 'sell' in side.lower() or 'close_long' in side.lower():
                    return -abs(original_gate_size), True
                else:
                    return abs(original_gate_size), True
            
            position = gate_positions[0]
            current_gate_size = int(position.get('size', 0))
            
            if current_gate_size == 0:
                logger.warning(f"⚠️ 게이트 포지션 크기가 0이어서 원본 크기 사용: {original_gate_size}")
                if 'short' in side.lower() or 'sell' in side.lower() or 'close_long' in side.lower():
                    return -abs(original_gate_size), True
                else:
                    return abs(original_gate_size), True
            
            # 현재 포지션 방향 확인
            current_position_side = 'long' if current_gate_size > 0 else 'short'
            current_position_abs_size = abs(current_gate_size)
            
            logger.info(f"🔍 현재 게이트 포지션: {current_gate_size} ({current_position_side})")
            
            # 🔥🔥🔥 비트겟 클로즈 주문에서 실제 클로즈할 BTC 크기 추출
            bitget_close_btc = float(bitget_order.get('size', 0))
            
            # 🔥🔥🔥 비트겟 클로즈 크기를 게이트 계약 수로 변환
            # 1 BTC = 10,000 계약 (Gate.io 표준)
            bitget_close_contracts = int(bitget_close_btc * 10000)
            
            logger.info(f"🔍 비트겟 클로즈 요청: {bitget_close_btc} BTC = {bitget_close_contracts} 계약")
            
            # 부분 청산 비율 계산
            if bitget_close_contracts > 0 and current_position_abs_size > 0:
                close_ratio = min(bitget_close_contracts / current_position_abs_size, 1.0)
                logger.info(f"🔍 부분 청산 비율: {close_ratio*100:.1f}% (요청: {bitget_close_contracts}, 현재: {current_position_abs_size})")
            else:
                close_ratio = 1.0
                logger.info(f"🔍 전체 청산으로 처리")
            
            # 🔥🔥🔥 게이트 실제 클로즈 크기 계산
            actual_close_size = int(current_position_abs_size * close_ratio)
            
            # 최소 1개는 클로즈
            if actual_close_size == 0:
                actual_close_size = 1
            
            # 현재 포지션보다 클 수 없음
            if actual_close_size > current_position_abs_size:
                actual_close_size = current_position_abs_size
            
            # 🔥🔥🔥 클로즈 주문 방향 결정 (포지션과 반대 방향) - 강화된 로직
            if current_position_side == 'long':
                # 롱 포지션 클로즈 → 매도 (음수)
                final_size = -actual_close_size
                logger.info(f"🔴 롱 포지션 클로즈: {actual_close_size} → 매도 주문 (음수: {final_size})")
            else:
                # 숏 포지션 클로즈 → 매수 (양수)
                final_size = actual_close_size
                logger.info(f"🟢 숏 포지션 클로즈: {actual_close_size} → 매수 주문 (양수: {final_size})")
            
            # 🔥🔥🔥 비트겟 side와 현재 포지션 방향 검증
            bitget_side = side.lower()
            if 'close_long' in bitget_side and current_position_side != 'long':
                logger.warning(f"⚠️ 비트겟은 close_long인데 현재 포지션은 {current_position_side}")
            elif 'close_short' in bitget_side and current_position_side != 'short':
                logger.warning(f"⚠️ 비트겟은 close_short인데 현재 포지션은 {current_position_side}")
            
            logger.info(f"✅ 포지션 기반 클로즈 주문 크기 계산 완료:")
            logger.info(f"   - 현재 포지션: {current_gate_size}")
            logger.info(f"   - 비트겟 클로즈 BTC: {bitget_close_btc}")
            logger.info(f"   - 비트겟 클로즈 계약: {bitget_close_contracts}")
            logger.info(f"   - 클로즈 비율: {close_ratio*100:.1f}%")
            logger.info(f"   - 최종 클로즈 크기: {final_size}")
            
            return final_size, True  # reduce_only=True
            
        except Exception as e:
            logger.error(f"포지션 기반 클로즈 주문 크기 계산 실패: {e}")
            # 실패 시 원본 크기 사용
            if 'short' in side.lower() or 'sell' in side.lower() or 'close_long' in side.lower():
                return -abs(original_gate_size), True
            else:
                return abs(original_gate_size), True
    
    async def create_conditional_order_with_tp_sl(self, trigger_price: float, order_size: int,
                                                tp_price: Optional[float] = None,
                                                sl_price: Optional[float] = None,
                                                reduce_only: bool = False,
                                                trigger_type: str = "ge") -> Dict:
        """🔥 TP/SL 포함 조건부 주문 생성 - Gate.io 공식 API"""
        try:
            endpoint = "/api/v4/futures/usdt/price_orders"
            
            # 기본 주문 데이터
            initial_data = {
                "type": "market",  # 시장가 주문
                "contract": "BTC_USDT",
                "size": order_size,
                "price": str(trigger_price)  # Gate.io는 시장가에도 price 필수
            }
            
            if reduce_only:
                initial_data["reduce_only"] = True
            
            # 트리거 rule 설정 (Gate.io 공식 문서)
            rule_value = 1 if trigger_type == "ge" else 2
            
            data = {
                "initial": initial_data,
                "trigger": {
                    "strategy_type": 0,  # 가격 기반 트리거
                    "price_type": 0,     # 마크 가격 기준
                    "price": str(trigger_price),
                    "rule": rule_value   # 1: >=, 2: <=
                }
            }
            
            # 🔥 TP/SL 설정 (Gate.io 공식 필드)
            if tp_price and tp_price > 0:
                data["stop_profit_price"] = str(tp_price)
                logger.info(f"🎯 TP 설정: ${tp_price:.2f}")
            
            if sl_price and sl_price > 0:
                data["stop_loss_price"] = str(sl_price)
                logger.info(f"🛡️ SL 설정: ${sl_price:.2f}")
            
            logger.info(f"Gate.io TP/SL 통합 주문 데이터: {json.dumps(data, indent=2)}")
            
            response = await self._request('POST', endpoint, data=data)
            
            logger.info(f"✅ Gate.io TP/SL 통합 주문 생성 성공: {response.get('id')}")
            
            return response
            
        except Exception as e:
            logger.error(f"TP/SL 포함 조건부 주문 생성 실패: {e}")
            raise
    
    async def create_price_triggered_order(self, trigger_price: float, order_size: int,
                                         reduce_only: bool = False, trigger_type: str = "ge") -> Dict:
        """일반 가격 트리거 주문 생성"""
        try:
            endpoint = "/api/v4/futures/usdt/price_orders"
            
            initial_data = {
                "type": "market",
                "contract": "BTC_USDT",
                "size": order_size,
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
                         reduce_only: bool = False, tif: str = "gtc", iceberg: int = 0,
                         use_slippage_protection: bool = True) -> Dict:
        """🔥🔥🔥 시장가/지정가 주문 생성 - 강화된 슬리피지 보호"""
        try:
            # 🔥🔥🔥 시장가 주문이고 슬리피지 보호가 활성화된 경우
            if price is None and use_slippage_protection and self.SLIPPAGE_CHECK_ENABLED:
                logger.info(f"슬리피지 보호가 적용된 시장가 주문 실행: {size}")
                return await self._place_order_with_slippage_protection(contract, size, reduce_only)
            
            # 기본 주문 로직
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
        """포지션 종료 - 슬리피지 보호 적용"""
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
            
            # 🔥🔥🔥 슬리피지 보호가 적용된 포지션 클로즈
            logger.info(f"슬리피지 보호 포지션 클로즈: {close_size}")
            result = await self.place_order(
                contract=contract,
                size=close_size,
                price=None,
                reduce_only=True,
                use_slippage_protection=True  # 슬리피지 보호 활성화
            )
            
            return result
            
        except Exception as e:
            logger.error(f"포지션 종료 실패: {e}")
            raise
    
    async def get_current_position_details(self, contract: str = "BTC_USDT") -> Dict:
        """🔥🔥🔥 현재 포지션 상세 정보 조회"""
        try:
            positions = await self.get_positions(contract)
            
            if not positions:
                return {
                    'has_position': False,
                    'size': 0,
                    'abs_size': 0,
                    'side': 'none',
                    'entry_price': 0,
                    'unrealized_pnl': 0
                }
            
            position = positions[0]
            size = int(position.get('size', 0))
            
            if size == 0:
                return {
                    'has_position': False,
                    'size': 0,
                    'abs_size': 0,
                    'side': 'none',
                    'entry_price': 0,
                    'unrealized_pnl': 0
                }
            
            side = 'long' if size > 0 else 'short'
            abs_size = abs(size)
            entry_price = float(position.get('entry_price', 0))
            unrealized_pnl = float(position.get('unrealised_pnl', 0))
            
            return {
                'has_position': True,
                'size': size,
                'abs_size': abs_size,
                'side': side,
                'entry_price': entry_price,
                'unrealized_pnl': unrealized_pnl,
                'raw_position': position
            }
            
        except Exception as e:
            logger.error(f"현재 포지션 상세 정보 조회 실패: {e}")
            return {
                'has_position': False,
                'size': 0,
                'abs_size': 0,
                'side': 'error',
                'entry_price': 0,
                'unrealized_pnl': 0,
                'error': str(e)
            }
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Gate.io 미러링 클라이언트 세션 종료")
