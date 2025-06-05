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
        
        # 🔥🔥🔥 시세 차이 문제 해결을 위한 설정
        self.PRICE_TOLERANCE = 50.0  # 50달러까지 시세 차이 허용
        self.POSITION_WAIT_TIMEOUT = 300  # 5분 포지션 체결 대기
        self.LEVERAGE_RETRY_MAX = 10  # 레버리지 설정 최대 재시도
        
        logger.info("🔥🔥🔥 Gate.io 클라이언트 초기화 완료 - 시세차이 문제 해결")
        
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
        """🔥🔥🔥 API 요청 - 파라미터 검증 강화"""
        if not self.session:
            self._initialize_session()
        
        url = f"{self.base_url}{endpoint}"
        query_string = ""
        payload = ""
        
        if params:
            # 🔥🔥🔥 파라미터 검증 및 정리
            cleaned_params = {}
            for k, v in params.items():
                if v is not None and str(v) != '':
                    # 특수 문자 및 유효하지 않은 값 필터링
                    if isinstance(v, (int, float)):
                        cleaned_params[k] = str(v)
                    elif isinstance(v, str):
                        # 특수 문자 제거 (#, &, 등)
                        clean_value = v.replace('#', '').replace('&', '').strip()
                        if clean_value:
                            cleaned_params[k] = clean_value
                    else:
                        cleaned_params[k] = str(v)
            
            if cleaned_params:
                query_string = "&".join([f"{k}={v}" for k, v in cleaned_params.items()])
                url += f"?{query_string}"
        
        if data:
            # 🔥🔥🔥 데이터 검증 및 정리
            cleaned_data = {}
            for k, v in data.items():
                if v is not None:
                    if isinstance(v, (int, float)):
                        cleaned_data[k] = v
                    elif isinstance(v, str):
                        # 특수 문자 제거
                        clean_value = v.replace('#', '').replace('&', '').strip()
                        if clean_value:
                            cleaned_data[k] = clean_value
                    elif isinstance(v, bool):
                        cleaned_data[k] = v
                    elif isinstance(v, dict):
                        cleaned_data[k] = v
                    else:
                        cleaned_data[k] = str(v)
            
            payload = json.dumps(cleaned_data)
        
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
    
    async def get_current_price(self, contract: str = "BTC_USDT") -> float:
        """🔥🔥🔥 현재 시장가 조회 - 강화된 버전"""
        try:
            # 1차: 티커에서 조회
            ticker = await self.get_ticker(contract)
            if ticker:
                for price_field in ['last', 'mark_price', 'index_price']:
                    price_value = ticker.get(price_field)
                    if price_value and float(price_value) > 0:
                        current_price = float(price_value)
                        logger.debug(f"Gate.io 현재가 ({price_field}): ${current_price:.2f}")
                        return current_price
            
            # 2차: 계약 정보에서 조회
            contract_info = await self.get_contract_info(contract)
            if contract_info:
                for price_field in ['last_price', 'mark_price', 'index_price']:
                    price_value = contract_info.get(price_field)
                    if price_value and float(price_value) > 0:
                        current_price = float(price_value)
                        logger.debug(f"Gate.io 계약 현재가 ({price_field}): ${current_price:.2f}")
                        return current_price
            
            logger.warning("Gate.io 현재가 조회 실패")
            return 0.0
            
        except Exception as e:
            logger.error(f"현재가 조회 실패: {e}")
            return 0.0
    
    async def validate_trigger_price(self, trigger_price: float, trigger_type: str, contract: str = "BTC_USDT") -> Tuple[bool, str, float]:
        """🔥🔥🔥 트리거 가격 유효성 검증 및 조정 - 시세차이 고려"""
        try:
            current_price = await self.get_current_price(contract)
            if current_price == 0:
                # 현재가 조회 실패 시 관대하게 처리
                logger.warning("현재가 조회 실패, 트리거 가격 그대로 사용")
                return True, "현재가 조회 실패, 원본 사용", trigger_price
            
            price_diff_percent = abs(trigger_price - current_price) / current_price * 100
            price_diff_abs = abs(trigger_price - current_price)
            
            # 🔥🔥🔥 시세 차이를 고려한 관대한 검증
            # 가격이 너무 근접한 경우 (0.01% 이하 또는 5달러 이하)
            if price_diff_percent < 0.01 or price_diff_abs < 5.0:
                if trigger_type == "ge":
                    adjusted_price = current_price * 1.0015  # 0.15% 위로 조정
                elif trigger_type == "le":
                    adjusted_price = current_price * 0.9985  # 0.15% 아래로 조정
                else:
                    adjusted_price = trigger_price
                
                logger.info(f"🔧 트리거가 너무 근접, 조정: ${trigger_price:.2f} → ${adjusted_price:.2f}")
                return True, "가격 조정됨", adjusted_price
            
            # 🔥🔥🔥 시세 차이가 큰 경우 관대하게 처리
            if price_diff_abs > self.PRICE_TOLERANCE:
                logger.warning(f"큰 시세 차이 감지 (${price_diff_abs:.2f}), 그대로 허용")
                return True, f"큰 시세차이지만 허용 (차이: ${price_diff_abs:.2f})", trigger_price
            
            # Gate.io 규칙 검증 (완화된 버전)
            if trigger_type == "ge":  # greater than or equal
                if trigger_price <= current_price:
                    # 시세 차이를 고려하여 더 관대하게 조정
                    adjusted_price = current_price * 1.002  # 0.2% 위로
                    logger.info(f"🔧 GE 트리거가 조정: ${trigger_price:.2f} → ${adjusted_price:.2f}")
                    return True, "GE 가격 조정됨", adjusted_price
                else:
                    return True, "유효한 GE 트리거가", trigger_price
            
            elif trigger_type == "le":  # less than or equal
                if trigger_price >= current_price:
                    # 시세 차이를 고려하여 더 관대하게 조정
                    adjusted_price = current_price * 0.998  # 0.2% 아래로
                    logger.info(f"🔧 LE 트리거가 조정: ${trigger_price:.2f} → ${adjusted_price:.2f}")
                    return True, "LE 가격 조정됨", adjusted_price
                else:
                    return True, "유효한 LE 트리거가", trigger_price
            
            return True, "유효한 트리거가", trigger_price
            
        except Exception as e:
            logger.error(f"트리거 가격 검증 실패하지만 허용: {e}")
            return True, f"검증 오류지만 허용: {str(e)}", trigger_price
    
    async def get_account_balance(self) -> Dict:
        """계정 잔고 조회"""
        try:
            endpoint = "/api/v4/futures/usdt/accounts"
            response = await self._request('GET', endpoint)
            logger.debug(f"Gate.io 계정 잔고 응답: {response}")
            return response
        except Exception as e:
            logger.error(f"계정 잔고 조회 실패: {e}")
            raise
    
    async def get_futures_account(self) -> Dict:
        """선물 계정 정보 조회"""
        return await self.get_account_balance()
    
    async def get_ticker(self, contract: str = "BTC_USDT") -> Dict:
        """🔥🔥🔥 티커 정보 조회 - 강화된 버전"""
        try:
            endpoint = f"/api/v4/futures/usdt/tickers"
            params = {'contract': contract}
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list) and len(response) > 0:
                ticker_data = response[0]
                # 가격 필드 보완
                if 'last' not in ticker_data:
                    for fallback_field in ['mark_price', 'index_price', 'best_bid', 'best_ask']:
                        if fallback_field in ticker_data and ticker_data[fallback_field]:
                            ticker_data['last'] = ticker_data[fallback_field]
                            logger.debug(f"티커 last 가격을 {fallback_field}로 보완: {ticker_data['last']}")
                            break
                return ticker_data
            elif isinstance(response, dict):
                # 가격 필드 보완
                if 'last' not in response:
                    for fallback_field in ['mark_price', 'index_price', 'best_bid', 'best_ask']:
                        if fallback_field in response and response[fallback_field]:
                            response['last'] = response[fallback_field]
                            logger.debug(f"티커 last 가격을 {fallback_field}로 보완: {response['last']}")
                            break
                return response
            else:
                logger.warning(f"Gate.io 티커 응답 형식 이상: {response}")
                return {}
            
        except Exception as e:
            logger.error(f"Gate.io 티커 조회 실패: {e}")
            return {}
    
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
    
    async def check_existing_positions(self, contract: str = "BTC_USDT") -> Dict:
        """기존 포지션 확인 - 렌더 재구동 시 중복 방지용"""
        try:
            positions = await self.get_positions(contract)
            
            existing_positions = {
                'has_long': False,
                'has_short': False,
                'long_size': 0,
                'short_size': 0,
                'positions': positions
            }
            
            for pos in positions:
                size = int(pos.get('size', 0))
                if size > 0:
                    existing_positions['has_long'] = True
                    existing_positions['long_size'] = size
                elif size < 0:
                    existing_positions['has_short'] = True
                    existing_positions['short_size'] = abs(size)
            
            logger.info(f"기존 게이트 포지션 확인: 롱={existing_positions['has_long']}({existing_positions['long_size']}), 숏={existing_positions['has_short']}({existing_positions['short_size']})")
            return existing_positions
            
        except Exception as e:
            logger.error(f"기존 포지션 확인 실패: {e}")
            return {
                'has_long': False,
                'has_short': False,
                'long_size': 0,
                'short_size': 0,
                'positions': []
            }
    
    async def wait_for_position_execution(self, contract: str, expected_side: str, timeout: int = 300) -> Dict:
        """🔥🔥🔥 포지션 체결 대기 - 시세 차이 문제 해결"""
        try:
            logger.info(f"🕐 포지션 체결 대기 시작: {contract}, 예상 방향: {expected_side}, 타임아웃: {timeout}초")
            start_time = time.time()
            check_interval = 5  # 5초마다 체크
            last_log_time = start_time
            
            while time.time() - start_time < timeout:
                try:
                    positions = await self.get_positions(contract)
                    
                    for pos in positions:
                        size = int(pos.get('size', 0))
                        
                        # 포지션 방향 확인
                        if expected_side == "long" and size > 0:
                            elapsed_time = time.time() - start_time
                            logger.info(f"✅ 롱 포지션 체결 확인: {size} (대기시간: {elapsed_time:.1f}초)")
                            return pos
                        elif expected_side == "short" and size < 0:
                            elapsed_time = time.time() - start_time
                            logger.info(f"✅ 숏 포지션 체결 확인: {size} (대기시간: {elapsed_time:.1f}초)")
                            return pos
                    
                    # 30초마다 대기 상태 로깅
                    current_time = time.time()
                    if current_time - last_log_time >= 30:
                        elapsed_time = current_time - start_time
                        remaining_time = timeout - elapsed_time
                        logger.info(f"🕐 포지션 체결 대기 중... (경과: {elapsed_time:.0f}초, 남은시간: {remaining_time:.0f}초)")
                        last_log_time = current_time
                    
                except Exception as position_check_error:
                    logger.warning(f"포지션 체크 중 일시적 오류: {position_check_error}")
                
                # 체크 간격 대기
                await asyncio.sleep(check_interval)
            
            # 타임아웃
            elapsed_time = time.time() - start_time
            logger.warning(f"⏰ 포지션 체결 대기 타임아웃: {elapsed_time:.1f}초 경과")
            return {}
            
        except Exception as e:
            logger.error(f"포지션 체결 대기 실패: {e}")
            return {}
    
    async def place_order_and_wait_execution(self, contract: str, size: int, price: Optional[float] = None, 
                                           reduce_only: bool = False, tif: str = "gtc", iceberg: int = 0,
                                           wait_execution: bool = True, timeout: int = 60) -> Dict:
        """🔥🔥🔥 주문 생성 후 체결 대기 - 타임아웃 설정 가능"""
        try:
            logger.info(f"🎯 주문 생성 후 체결 대기: size={size}, wait={wait_execution}, timeout={timeout}초")
            
            # 주문 생성
            order_result = await self.place_order(
                contract=contract,
                size=size,
                price=price,
                reduce_only=reduce_only,
                tif=tif,
                iceberg=iceberg
            )
            
            # 포지션 오픈 주문이고 체결 대기가 활성화된 경우
            if not reduce_only and wait_execution and size != 0:
                expected_side = "long" if size > 0 else "short"
                logger.info(f"🕐 포지션 체결 대기 중: {expected_side} (타임아웃: {timeout}초)")
                
                # 포지션 체결 대기
                executed_position = await self.wait_for_position_execution(contract, expected_side, timeout=timeout)
                
                if executed_position:
                    order_result['position_executed'] = executed_position
                    order_result['execution_confirmed'] = True
                    order_result['execution_time'] = timeout
                    logger.info(f"✅ 포지션 체결 확인 완료")
                else:
                    order_result['execution_confirmed'] = False
                    order_result['execution_timeout'] = True
                    logger.warning(f"⚠️ 포지션 체결 확인 실패 (타임아웃: {timeout}초)")
            else:
                order_result['execution_confirmed'] = True  # 클로즈 주문은 바로 성공으로 처리
                order_result['skip_execution_wait'] = True
            
            return order_result
            
        except Exception as e:
            logger.error(f"주문 생성 및 체결 대기 실패: {e}")
            raise
    
    async def place_order(self, contract: str, size: int, price: Optional[float] = None, 
                         reduce_only: bool = False, tif: str = "gtc", iceberg: int = 0) -> Dict:
        """🔥🔥🔥 시장가/지정가 주문 생성 - 파라미터 검증 강화"""
        try:
            endpoint = "/api/v4/futures/usdt/orders"
            
            # 🔥🔥🔥 파라미터 검증 강화
            if size == 0:
                raise ValueError("주문 수량이 0입니다")
            
            if abs(size) > 1000000:  # 비정상적으로 큰 수량 방지
                raise ValueError(f"주문 수량이 너무 큼: {size}")
            
            data = {
                "contract": str(contract).strip(),
                "size": int(size)
            }
            
            if price is not None:
                if price <= 0:
                    raise ValueError(f"주문 가격이 유효하지 않음: {price}")
                data["price"] = f"{price:.2f}"  # 소수점 2자리로 제한
                data["tif"] = str(tif).strip()
                logger.info(f"지정가 주문 생성: {contract}, 수량: {size}, 가격: {price:.2f}, TIF: {tif}")
            else:
                logger.info(f"시장가 주문 생성: {contract}, 수량: {size}")
            
            # 🔥🔥🔥 reduce_only 플래그 올바른 처리
            if reduce_only:
                data["reduce_only"] = True
                logger.info(f"포지션 감소 전용 주문 (클로즈): reduce_only=True")
            else:
                # reduce_only가 False인 경우 명시적으로 설정하지 않음 (Gate.io 기본값)
                logger.info(f"포지션 증가 주문 (오픈): reduce_only 미설정")
            
            if iceberg > 0:
                data["iceberg"] = int(iceberg)
                logger.info(f"빙산 주문: {iceberg}")
            
            # 🔥🔥🔥 주문 방향 확인 로그 강화
            order_direction = "매수(롱)" if size > 0 else "매도(숏)"
            order_type = "클로즈" if reduce_only else "오픈"
            logger.info(f"🔍 Gate.io 주문 생성: {order_type} {order_direction}, 수량={size}, reduce_only={reduce_only}")
            
            # 🔥🔥🔥 파라미터 최종 검증
            for key, value in data.items():
                if value is None or (isinstance(value, str) and value.strip() == ''):
                    raise ValueError(f"파라미터 {key}가 비어있음: {value}")
            
            logger.info(f"Gate.io 주문 생성 요청: {data}")
            response = await self._request('POST', endpoint, data=data)
            logger.info(f"✅ Gate.io 주문 생성 성공: {response}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Gate.io 주문 생성 실패: {e}")
            logger.error(f"주문 파라미터: contract={contract}, size={size}, price={price}, reduce_only={reduce_only}, tif={tif}")
            raise
    
    async def set_leverage(self, contract: str, leverage: int, cross_leverage_limit: int = 0, 
                          retry_count: int = None) -> Dict:
        """🔥🔥🔥 레버리지 설정 - 대폭 강화된 로직"""
        
        if retry_count is None:
            retry_count = self.LEVERAGE_RETRY_MAX
        
        logger.info(f"🎯 Gate.io 레버리지 설정 시작: {contract} - {leverage}x (최대 재시도: {retry_count}회)")
        
        for attempt in range(retry_count):
            try:
                endpoint = f"/api/v4/futures/usdt/positions/{contract}/leverage"
                
                # 🔥🔥🔥 레버리지 파라미터 검증 강화
                if leverage < 1 or leverage > 100:
                    raise ValueError(f"레버리지 값이 유효하지 않음: {leverage}")
                
                # 🔥 레버리지를 정수 문자열로 전달
                data = {
                    "leverage": str(int(leverage))
                }
                
                if cross_leverage_limit > 0:
                    data["cross_leverage_limit"] = str(int(cross_leverage_limit))
                
                logger.info(f"레버리지 설정 시도 {attempt + 1}/{retry_count}: {contract} - {leverage}x")
                logger.debug(f"레버리지 설정 데이터: {data}")
                
                response = await self._request('POST', endpoint, data=data)
                logger.info(f"레버리지 설정 응답: {response}")
                
                # 🔥🔥🔥 설정 후 더 긴 대기 시간
                await asyncio.sleep(3.0)
                
                # 🔥🔥🔥 레버리지 설정 확인을 더 강력하게 (여러 번 시도)
                verify_success = False
                for verify_attempt in range(5):  # 5번까지 확인 시도
                    try:
                        await asyncio.sleep(1.0)  # 확인 간격
                        
                        positions = await self.get_positions(contract)
                        if positions:
                            position = positions[0]
                            current_leverage = position.get('leverage')
                            
                            if current_leverage:
                                try:
                                    current_lev_int = int(float(current_leverage))
                                    target_lev_int = int(leverage)
                                    
                                    if current_lev_int == target_lev_int:
                                        logger.info(f"✅ 레버리지 설정 확인 성공 (시도 {verify_attempt + 1}): {current_lev_int}x = {target_lev_int}x")
                                        verify_success = True
                                        break
                                    else:
                                        logger.warning(f"⚠️ 레버리지 불일치 (확인시도 {verify_attempt + 1}): 현재 {current_lev_int}x, 목표 {target_lev_int}x")
                                        
                                        # 불일치가 계속되면 다시 설정 시도
                                        if verify_attempt >= 2:
                                            logger.warning(f"레버리지 불일치 지속, 재설정 필요")
                                            break
                                            
                                except (ValueError, TypeError) as lev_error:
                                    logger.warning(f"레버리지 값 변환 실패 (확인시도 {verify_attempt + 1}): {current_leverage}, 오류: {lev_error}")
                            else:
                                logger.warning(f"포지션에서 레버리지 정보 없음 (확인시도 {verify_attempt + 1})")
                        else:
                            logger.info(f"📝 포지션이 없어 레버리지 확인 불가 (확인시도 {verify_attempt + 1}), 설정 성공으로 처리")
                            verify_success = True
                            break
                            
                    except Exception as verify_error:
                        logger.warning(f"레버리지 확인 중 오류 (확인시도 {verify_attempt + 1}): {verify_error}")
                        if verify_attempt >= 3:  # 4번째 시도부터는 성공으로 처리
                            verify_success = True
                            break
                
                if verify_success:
                    logger.info(f"✅ Gate.io 레버리지 설정 및 확인 완료: {contract} - {leverage}x")
                    return response
                else:
                    logger.warning(f"⚠️ 레버리지 설정 확인 실패, 재시도 {attempt + 1}/{retry_count}")
                    if attempt < retry_count - 1:
                        await asyncio.sleep(5.0)  # 더 긴 대기 후 재시도
                        continue
                    else:
                        logger.error(f"❌ 레버리지 설정 최종 확인 실패: {contract} - {leverage}x")
                        # 그래도 설정 시도는 했으므로 응답 반환
                        return response
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Gate.io 레버리지 설정 시도 {attempt + 1} 실패: {error_msg}")
                
                # 특정 오류의 경우 재시도 중단
                if any(keyword in error_msg.lower() for keyword in [
                    "invalid argument", "invalid protocol", "parameter error", 
                    "invalid contract", "contract not found"
                ]):
                    logger.error(f"❌ 레버리지 설정 파라미터 오류, 재시도 중단: {error_msg}")
                    break
                
                if attempt < retry_count - 1:
                    wait_time = min(3.0 * (attempt + 1), 15.0)  # 점진적 대기 (최대 15초)
                    logger.info(f"🔄 {wait_time}초 후 레버리지 설정 재시도...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ 레버리지 설정 최대 재시도 횟수 초과: {contract} - {leverage}x")
                    raise
        
        raise Exception(f"레버리지 설정 최대 재시도 횟수 초과: {contract} - {leverage}x")
    
    async def create_price_triggered_order(self, trigger_type: str, trigger_price: str, 
                                         order_type: str, contract: str, size: int, 
                                         price: Optional[str] = None,
                                         stop_profit_price: Optional[str] = None,
                                         stop_loss_price: Optional[str] = None,
                                         reduce_only: bool = False) -> Dict:
        """🔥🔥🔥 가격 트리거 주문 생성 - 파라미터 검증 대폭 강화"""
        try:
            # 🔥🔥🔥 파라미터 사전 검증
            if not trigger_price or float(trigger_price) <= 0:
                raise ValueError(f"유효하지 않은 트리거 가격: {trigger_price}")
            
            if size == 0:
                raise ValueError("주문 수량이 0입니다")
            
            if abs(size) > 1000000:
                raise ValueError(f"주문 수량이 너무 큼: {size}")
            
            # 트리거 가격 유효성 검증 및 조정
            trigger_price_float = float(trigger_price)
            is_valid, validation_msg, adjusted_price = await self.validate_trigger_price(
                trigger_price_float, trigger_type, contract
            )
            
            if not is_valid:
                raise Exception(f"트리거 가격 유효성 검증 실패: {validation_msg}")
            
            # 조정된 가격 사용
            if adjusted_price != trigger_price_float:
                trigger_price = f"{adjusted_price:.2f}"
                logger.info(f"🔧 트리거 가격 조정됨: {trigger_price_float:.2f} → {adjusted_price:.2f}")
            
            endpoint = "/api/v4/futures/usdt/price_orders"
            
            initial_data = {
                "type": str(order_type).strip(),
                "contract": str(contract).strip(),
                "size": int(size)
            }
            
            # 🔥🔥🔥 reduce_only 플래그 처리
            if reduce_only:
                initial_data["reduce_only"] = True
                logger.info(f"🔴 클로즈 주문: reduce_only=True 설정")
            else:
                logger.info(f"🟢 오픈 주문: reduce_only 미설정")
            
            # 🔥🔥🔥 Gate.io API에서 시장가 트리거 주문도 initial.price가 필수임
            if order_type == "limit":
                if price and float(price) > 0:
                    initial_data["price"] = f"{float(price):.2f}"
                    logger.info(f"지정가 주문에 지정된 가격 사용: {price}")
                else:
                    initial_data["price"] = trigger_price
                    logger.info(f"지정가 주문에 트리거 가격을 price로 사용: {trigger_price}")
            elif order_type == "market":
                # 🔥🔥🔥 시장가 주문에도 initial.price 필수 설정
                initial_data["price"] = trigger_price
                logger.info(f"시장가 트리거 주문에 trigger_price를 initial.price로 설정: {trigger_price}")
            
            # 🔥🔥🔥 트리거 rule을 정수로 변환 (파라미터 검증 강화)
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
                    "price": trigger_price,
                    "rule": rule_value
                }
            }
            
            # 🔥 실제 TP/SL 설정
            has_tp_sl = False
            if stop_profit_price and float(stop_profit_price) > 0:
                data["stop_profit_price"] = f"{float(stop_profit_price):.2f}"
                has_tp_sl = True
                logger.info(f"🎯 실제 TP 설정: ${stop_profit_price}")
            
            if stop_loss_price and float(stop_loss_price) > 0:
                data["stop_loss_price"] = f"{float(stop_loss_price):.2f}"
                has_tp_sl = True
                logger.info(f"🛡️ 실제 SL 설정: ${stop_loss_price}")
            
            # 🔥🔥🔥 주문 방향 및 타입 확인 로그 강화
            order_direction = "매수(롱)" if size > 0 else "매도(숏)"
            order_purpose = "클로즈" if reduce_only else "오픈"
            logger.info(f"🔍 Gate.io 트리거 주문: {order_purpose} {order_direction}, 수량={size}, reduce_only={reduce_only}")
            
            # 🔥🔥🔥 최종 파라미터 검증
            self._validate_order_data(data)
            
            logger.info(f"Gate.io 가격 트리거 주문 생성 (TP/SL 포함): {data}")
            response = await self._request('POST', endpoint, data=data)
            logger.info(f"✅ Gate.io 가격 트리거 주문 생성 성공: {response}")
            
            # 응답에 TP/SL 정보 추가
            response['has_tp_sl'] = has_tp_sl
            response['requested_tp'] = stop_profit_price
            response['requested_sl'] = stop_loss_price
            response['reduce_only'] = reduce_only
            
            # TP/SL 설정 결과 확인
            actual_tp = response.get('stop_profit_price', '')
            actual_sl = response.get('stop_loss_price', '')
            
            if has_tp_sl:
                if actual_tp and actual_tp != '':
                    logger.info(f"✅ TP 설정 확인됨: ${actual_tp}")
                elif stop_profit_price:
                    logger.warning(f"⚠️ TP 설정 요청했으나 응답에 없음: {stop_profit_price}")
                
                if actual_sl and actual_sl != '':
                    logger.info(f"✅ SL 설정 확인됨: ${actual_sl}")
                elif stop_loss_price:
                    logger.warning(f"⚠️ SL 설정 요청했으나 응답에 없음: {stop_loss_price}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ 가격 트리거 주문 생성 실패: {e}")
            logger.error(f"트리거 주문 파라미터: trigger_type={trigger_type}, trigger_price={trigger_price}, order_type={order_type}, size={size}, price={price}, tp={stop_profit_price}, sl={stop_loss_price}, reduce_only={reduce_only}")
            raise
    
    def _validate_order_data(self, data: Dict):
        """🔥🔥🔥 주문 데이터 최종 검증"""
        try:
            # initial 검증
            initial = data.get('initial', {})
            if not initial.get('contract'):
                raise ValueError("contract가 비어있음")
            if not initial.get('size') or initial.get('size') == 0:
                raise ValueError("size가 0이거나 없음")
            if not initial.get('type'):
                raise ValueError("type이 비어있음")
            
            # trigger 검증
            trigger = data.get('trigger', {})
            if not trigger.get('price') or float(trigger.get('price', 0)) <= 0:
                raise ValueError("trigger price가 유효하지 않음")
            if trigger.get('rule') not in [1, 2]:
                raise ValueError(f"trigger rule이 유효하지 않음: {trigger.get('rule')}")
                
            logger.debug("주문 데이터 검증 통과")
            
        except Exception as e:
            logger.error(f"주문 데이터 검증 실패: {e}")
            raise ValueError(f"주문 데이터 검증 실패: {e}")
    
    async def create_unified_order_with_tp_sl(self, trigger_type: str, trigger_price: str,
                                           order_type: str, contract: str, size: int,
                                           price: Optional[str] = None,
                                           tp_price: Optional[str] = None,
                                           sl_price: Optional[str] = None,
                                           bitget_order_info: Optional[Dict] = None,
                                           wait_execution: bool = True) -> Dict:
        """🔥🔥🔥 통합된 TP/SL 포함 예약 주문 생성 - 포지션 체결 대기 개선"""
        try:
            logger.info(f"🎯 통합 TP/SL 포함 예약 주문 생성 시도 (포지션 체결 대기 개선)")
            logger.info(f"   - 트리거가: {trigger_price}")
            logger.info(f"   - TP: {tp_price}")
            logger.info(f"   - SL: {sl_price}")
            logger.info(f"   - 체결 대기: {wait_execution}")
            
            # 🔥🔥🔥 비트겟 주문 정보에서 reduce_only 판단
            reduce_only = False
            if bitget_order_info:
                side = bitget_order_info.get('side', bitget_order_info.get('tradeSide', '')).lower()
                bitget_reduce_only = bitget_order_info.get('reduceOnly', False)
                
                # 클로즈 주문인지 판단
                is_close_order = (
                    'close' in side or 
                    bitget_reduce_only is True or 
                    bitget_reduce_only == 'true'
                )
                
                if is_close_order:
                    reduce_only = True
                    logger.info(f"🔴 클로즈 주문 감지: side={side}, bitget_reduce_only={bitget_reduce_only} → reduce_only=True")
                else:
                    reduce_only = False
                    logger.info(f"🟢 오픈 주문 감지: side={side}, bitget_reduce_only={bitget_reduce_only} → reduce_only=False")
            
            # 🔥🔥🔥 오픈 주문인 경우만 TP/SL을 별도로 처리하고, 포지션 체결 대기
            if not reduce_only and wait_execution and (tp_price or sl_price):
                logger.info(f"🔄 오픈 주문 + TP/SL → 단계별 처리 (체결 대기 후 TP/SL 설정)")
                
                # 1단계: 일반 예약 주문만 먼저 생성 (TP/SL 없이)
                order_response = await self.create_price_triggered_order(
                    trigger_type=trigger_type,
                    trigger_price=trigger_price,
                    order_type=order_type,
                    contract=contract,
                    size=size,
                    price=price,
                    reduce_only=reduce_only
                    # TP/SL 제외
                )
                
                order_id = order_response.get('id')
                logger.info(f"✅ 1단계: 오픈 예약 주문 생성 완료: {order_id}")
                
                # 2단계: 예약 주문이 체결되어 포지션이 생성될 때까지 대기 (별도 태스크로)
                expected_side = "long" if size > 0 else "short"
                logger.info(f"🕐 2단계: 포지션 체결 대기 예약 ({expected_side})")
                
                # TP/SL 설정을 별도 태스크로 비동기 처리 (더 긴 타임아웃)
                asyncio.create_task(self._wait_and_create_tp_sl(
                    contract=contract,
                    expected_side=expected_side,
                    planned_size=size,
                    tp_price=float(tp_price) if tp_price else None,
                    sl_price=float(sl_price) if sl_price else None,
                    order_id=order_id,
                    timeout=self.POSITION_WAIT_TIMEOUT  # 5분 타임아웃
                ))
                
                order_response.update({
                    'has_tp_sl': True,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'tp_sl_pending': True,  # TP/SL이 나중에 설정될 예정
                    'unified_order': True,
                    'staged_execution': True,  # 단계별 실행
                    'reduce_only': reduce_only,
                    'position_wait_timeout': self.POSITION_WAIT_TIMEOUT
                })
                
                return order_response
            
            else:
                # 🔥 클로즈 주문이거나 TP/SL이 없는 경우 → 기존 방식 사용
                logger.info(f"📝 일반 처리: 클로즈 주문({reduce_only}) 또는 TP/SL 없음")
                
                order_response = await self.create_price_triggered_order(
                    trigger_type=trigger_type,
                    trigger_price=trigger_price,
                    order_type=order_type,
                    contract=contract,
                    size=size,
                    price=price,
                    stop_profit_price=tp_price,  # 실제 TP 설정
                    stop_loss_price=sl_price,    # 실제 SL 설정
                    reduce_only=reduce_only
                )
                
                order_id = order_response.get('id')
                logger.info(f"✅ 일반 예약 주문 생성 완료: {order_id}")
                
                # TP/SL 설정 결과 검증
                has_tp_sl = order_response.get('has_tp_sl', False)
                actual_tp = order_response.get('stop_profit_price', '')
                actual_sl = order_response.get('stop_loss_price', '')
                
                if tp_price or sl_price:
                    tp_sl_success = False
                    tp_sl_info = f"\n\n🎯 TP/SL 설정 결과:"
                    
                    if tp_price and actual_tp and actual_tp != '':
                        tp_sl_info += f"\n✅ TP 성공: ${actual_tp}"
                        tp_sl_success = True
                    elif tp_price:
                        tp_sl_info += f"\n❌ TP 실패: 요청 ${tp_price} → 응답 '{actual_tp}'"
                    
                    if sl_price and actual_sl and actual_sl != '':
                        tp_sl_info += f"\n✅ SL 성공: ${actual_sl}"
                        tp_sl_success = True
                    elif sl_price:
                        tp_sl_info += f"\n❌ SL 실패: 요청 ${sl_price} → 응답 '{actual_sl}'"
                    
                    if tp_sl_success:
                        tp_sl_info += f"\n🎯 Gate.io 네이티브 TP/SL 설정 완료"
                    else:
                        tp_sl_info += f"\n⚠️ TP/SL 설정이 반영되지 않았습니다."
                    
                    logger.info(tp_sl_info)
                    
                    # 결과에 상세 정보 추가
                    order_response.update({
                        'has_tp_sl': tp_sl_success,
                        'tp_price': tp_price,
                        'sl_price': sl_price,
                        'actual_tp_price': actual_tp,
                        'actual_sl_price': actual_sl,
                        'unified_order': True,
                        'bitget_style': True,
                        'tp_sl_status': 'success' if tp_sl_success else 'failed',
                        'reduce_only': reduce_only
                    })
                else:
                    logger.info(f"📝 TP/SL 설정 없는 일반 예약 주문")
                    order_response.update({
                        'has_tp_sl': False,
                        'unified_order': True,
                        'bitget_style': False,
                        'reduce_only': reduce_only
                    })
                
                return order_response
            
        except Exception as e:
            logger.error(f"❌ 통합 TP/SL 예약 주문 생성 실패: {e}")
            # 폴백: 일반 예약 주문만 생성
            logger.info("🔄 폴백: TP/SL 없는 일반 예약 주문 생성")
            fallback_order = await self.create_price_triggered_order(
                trigger_type=trigger_type,
                trigger_price=trigger_price,
                order_type=order_type,
                contract=contract,
                size=size,
                price=price,
                reduce_only=reduce_only
                # TP/SL 제외
            )
            fallback_order.update({
                'has_tp_sl': False,
                'unified_order': True,
                'bitget_style': False,
                'fallback': True,
                'error': str(e),
                'reduce_only': reduce_only
            })
            return fallback_order
    
    async def _wait_and_create_tp_sl(self, contract: str, expected_side: str, planned_size: int,
                                   tp_price: Optional[float], sl_price: Optional[float], order_id: str,
                                   timeout: int = 300):
        """🔥🔥🔥 포지션 체결 대기 후 TP/SL 생성 (비동기 태스크) - 타임아웃 연장"""
        try:
            logger.info(f"🕐 TP/SL 설정을 위한 포지션 체결 대기 시작: {order_id} (타임아웃: {timeout}초)")
            
            # 포지션 체결 대기 (더 긴 타임아웃)
            executed_position = await self.wait_for_position_execution(contract, expected_side, timeout=timeout)
            
            if executed_position:
                logger.info(f"✅ 포지션 체결 확인, TP/SL 설정 시작")
                
                # TP/SL 주문 생성
                tp_sl_result = await self.create_tp_sl_orders_for_planned_position(
                    contract=contract,
                    planned_position_size=planned_size,
                    tp_price=tp_price,
                    sl_price=sl_price
                )
                
                if tp_sl_result['success_count'] > 0:
                    logger.info(f"✅ 지연된 TP/SL 설정 완료: {tp_sl_result['success_count']}개 성공")
                else:
                    logger.warning(f"⚠️ 지연된 TP/SL 설정 실패: {tp_sl_result['errors']}")
            else:
                logger.warning(f"⚠️ 포지션 체결 확인 실패 (타임아웃: {timeout}초), TP/SL 설정 건너뜀: {order_id}")
                
        except Exception as e:
            logger.error(f"지연된 TP/SL 설정 중 오류: {e}")
    
    async def create_tp_sl_orders_for_planned_position(self, contract: str, planned_position_size: int,
                                                     tp_price: Optional[float] = None,
                                                     sl_price: Optional[float] = None) -> Dict:
        """🔥 예약 주문에 대한 TP/SL 생성 - 수정된 로직"""
        try:
            result = {
                'tp_order': None,
                'sl_order': None,
                'success_count': 0,
                'error_count': 0,
                'errors': []
            }
            
            current_price = await self.get_current_price(contract)
            if current_price == 0:
                raise Exception("현재가 조회 실패")
            
            logger.info(f"🎯 예약 주문 TP/SL 생성 - 현재가: ${current_price:.2f}, 예정 포지션: {planned_position_size}")
            
            # 예약 주문이 체결된 후 생기는 포지션 방향 분석
            future_position_direction = "long" if planned_position_size > 0 else "short"
            logger.info(f"📊 예정 포지션 방향: {future_position_direction}")
            
            # TP 주문 생성
            if tp_price and tp_price > 0:
                try:
                    if future_position_direction == "long":
                        # 롱 포지션의 TP: 현재가보다 높은 가격에서 매도 (이익 실현)
                        if tp_price <= current_price:
                            logger.warning(f"롱 포지션 TP가 현재가보다 낮음: ${tp_price:.2f} <= ${current_price:.2f}")
                            tp_price = current_price * 1.005
                            logger.info(f"TP 가격 조정: ${tp_price:.2f}")
                        
                        tp_trigger_type = "ge"  # 가격이 TP 이상이 되면
                        tp_size = -abs(planned_position_size)  # 매도 (포지션 클로즈)
                        
                    else:  # short
                        # 숏 포지션의 TP: 현재가보다 낮은 가격에서 매수 (이익 실현)
                        if tp_price >= current_price:
                            logger.warning(f"숏 포지션 TP가 현재가보다 높음: ${tp_price:.2f} >= ${current_price:.2f}")
                            tp_price = current_price * 0.995
                            logger.info(f"TP 가격 조정: ${tp_price:.2f}")
                        
                        tp_trigger_type = "le"  # 가격이 TP 이하가 되면
                        tp_size = abs(planned_position_size)   # 매수 (포지션 클로즈)
                    
                    logger.info(f"🎯 TP 주문 생성: {future_position_direction} → {tp_trigger_type}, ${tp_price:.2f}, size={tp_size}")
                    
                    tp_order = await self.create_price_triggered_order(
                        trigger_type=tp_trigger_type,
                        trigger_price=str(tp_price),
                        order_type="market",
                        contract=contract,
                        size=tp_size,
                        reduce_only=True  # TP는 항상 클로즈 주문
                    )
                    
                    result['tp_order'] = tp_order
                    result['success_count'] += 1
                    logger.info(f"✅ TP 주문 생성 성공: {tp_order.get('id')}")
                    
                except Exception as tp_error:
                    error_msg = str(tp_error)
                    logger.error(f"❌ TP 주문 생성 실패: {error_msg}")
                    result['errors'].append(f"TP: {error_msg}")
                    result['error_count'] += 1
            
            # SL 주문 생성
            if sl_price and sl_price > 0:
                try:
                    if future_position_direction == "long":
                        # 롱 포지션의 SL: 현재가보다 낮은 가격에서 매도 (손실 제한)
                        if sl_price >= current_price:
                            logger.warning(f"롱 포지션 SL이 현재가보다 높음: ${sl_price:.2f} >= ${current_price:.2f}")
                            sl_price = current_price * 0.995
                            logger.info(f"SL 가격 조정: ${sl_price:.2f}")
                        
                        sl_trigger_type = "le"  # 가격이 SL 이하가 되면
                        sl_size = -abs(planned_position_size)  # 매도 (포지션 클로즈)
                        
                    else:  # short
                        # 숏 포지션의 SL: 현재가보다 높은 가격에서 매수 (손실 제한)
                        if sl_price <= current_price:
                            logger.warning(f"숏 포지션 SL이 현재가보다 낮음: ${sl_price:.2f} <= ${current_price:.2f}")
                            sl_price = current_price * 1.005
                            logger.info(f"SL 가격 조정: ${sl_price:.2f}")
                        
                        sl_trigger_type = "ge"  # 가격이 SL 이상이 되면
                        sl_size = abs(planned_position_size)   # 매수 (포지션 클로즈)
                    
                    logger.info(f"🛡️ SL 주문 생성: {future_position_direction} → {sl_trigger_type}, ${sl_price:.2f}, size={sl_size}")
                    
                    sl_order = await self.create_price_triggered_order(
                        trigger_type=sl_trigger_type,
                        trigger_price=str(sl_price),
                        order_type="market",
                        contract=contract,
                        size=sl_size,
                        reduce_only=True  # SL은 항상 클로즈 주문
                    )
                    
                    result['sl_order'] = sl_order
                    result['success_count'] += 1
                    logger.info(f"✅ SL 주문 생성 성공: {sl_order.get('id')}")
                    
                except Exception as sl_error:
                    error_msg = str(sl_error)
                    logger.error(f"❌ SL 주문 생성 실패: {error_msg}")
                    result['errors'].append(f"SL: {error_msg}")
                    result['error_count'] += 1
            
            logger.info(f"🎯 예약 주문 TP/SL 생성 완료: 성공 {result['success_count']}개, 실패 {result['error_count']}개")
            return result
            
        except Exception as e:
            logger.error(f"❌ 예약 주문 TP/SL 생성 전체 실패: {e}")
            return {
                'tp_order': None,
                'sl_order': None,
                'success_count': 0,
                'error_count': 1,
                'errors': [str(e)]
            }
    
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
        """🔥🔥🔥 포지션 종료 - reduce_only 플래그 사용"""
        try:
            positions = await self.get_positions(contract)
            
            if not positions or positions[0].get('size', 0) == 0:
                logger.warning(f"종료할 포지션이 없습니다: {contract}")
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
            
            logger.info(f"Gate.io 포지션 종료: {contract}, 현재 사이즈: {position_size}, 종료 사이즈: {close_size}")
            
            # 포지션 종료는 항상 reduce_only=True
            result = await self.place_order(
                contract=contract,
                size=close_size,
                price=None,
                reduce_only=True  # 포지션 종료는 클로즈 주문
            )
            
            logger.info(f"✅ Gate.io 포지션 종료 성공: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 포지션 종료 실패: {e}")
            raise
    
    async def get_profit_history_since_may(self) -> Dict:
        """2025년 5월 29일부터의 손익 계산"""
        try:
            import pytz
            from datetime import datetime
            
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_timestamp = int(today_start.timestamp())
            seven_days_ago = today_start - timedelta(days=6)
            seven_days_timestamp = int(seven_days_ago.timestamp())
            start_timestamp = int(self.GATE_START_DATE.timestamp())
            
            account = await self.get_account_balance()
            current_balance = float(account.get('total', 0))
            initial_capital = 700.0
            
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
            
            # 수수료 조회
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
            
            # 펀딩비 조회
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
            
            cumulative_net_profit = total_pnl - total_fee + total_fund
            
            # 7일간 손익 계산
            weekly_pnl = 0.0
            today_pnl = 0.0
            weekly_fee = 0.0
            
            actual_start_timestamp = max(seven_days_timestamp, start_timestamp)
            
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
                    
                    if record_time >= today_timestamp:
                        today_pnl += change
            except Exception as e:
                logger.error(f"주간 PnL 조회 실패: {e}")
            
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
            
            weekly_net = weekly_pnl - weekly_fee
            days_traded = min(7, (now - self.GATE_START_DATE).days + 1)
            
            logger.info(f"Gate.io 거래 일수: {days_traded}일")
            logger.info(f"Gate.io 7일 손익 - PnL: ${weekly_pnl:.2f}, Fee: ${weekly_fee:.2f}, Net: ${weekly_net:.2f}")
            logger.info(f"Gate.io 오늘 실현 손익: ${today_pnl:.2f}")
            
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
            try:
                account = await self.get_account_balance()
                total_equity = float(account.get('total', 0))
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
    
    async def get_account_book(self, type: Optional[str] = None, 
                             start_time: Optional[int] = None, end_time: Optional[int] = None,
                             limit: int = 100) -> List[Dict]:
        """계정 장부 조회"""
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
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Gate.io 클라이언트 세션 종료")
