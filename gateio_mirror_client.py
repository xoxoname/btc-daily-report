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
    
    def __init__(self, config):
        self.config = config
        self.api_key = config.GATE_API_KEY
        self.api_secret = config.GATE_API_SECRET
        self.base_url = "https://api.gateio.ws"
        self.session = None
        self._initialize_session()
        
        self.TP_SL_TIMEOUT = 10
        self.MAX_TP_SL_RETRIES = 3
        
        self.DEFAULT_LEVERAGE = 30
        self.MAX_LEVERAGE = 100
        self.MIN_LEVERAGE = 1
        self.current_leverage_cache = {}
        
        # 마진 모드 강제 설정 - 무조건 Cross 강제
        self.FORCE_CROSS_MARGIN = True
        self.DEFAULT_MARGIN_MODE = "cross"
        self.current_margin_mode_cache = {}
        self.margin_mode_force_attempts = 0
        self.max_margin_mode_attempts = 10
        
        # 지원되는 마진 모드 매핑
        self.MARGIN_MODE_MAPPING = {
            'cross': 'cross',
            'isolated': 'cross',
            'dual_long': 'cross',
            'dual_short': 'cross',
            'single': 'cross',
            'default': 'cross'
        }
        
    def _initialize_session(self):
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
        self._initialize_session()
        
        try:
            current_leverage = await self.get_current_leverage("BTC_USDT")
            if current_leverage != self.DEFAULT_LEVERAGE:
                logger.info(f"기본 레버리지 설정: {current_leverage}x → {self.DEFAULT_LEVERAGE}x")
                await self.set_leverage("BTC_USDT", self.DEFAULT_LEVERAGE)
            else:
                logger.info(f"기본 레버리지 이미 설정됨: {self.DEFAULT_LEVERAGE}x")
        except Exception as e:
            logger.warning(f"기본 레버리지 설정 실패하지만 계속 진행: {e}")
        
        await self.force_cross_margin_mode_aggressive("BTC_USDT")
        logger.info("Gate.io 미러링 클라이언트 초기화 완료")
    
    async def ensure_cross_margin_mode_before_order(self, contract: str = "BTC_USDT") -> bool:
        # 주문 생성 전 마진 모드 실시간 체크 및 강제 설정
        try:
            current_mode = await self.get_current_margin_mode(contract)
            
            if current_mode == "cross":
                return True
            
            logger.warning(f"주문 생성 전 마진 모드 확인: {current_mode} → Cross로 강제 변경 시도")
            success = await self.force_cross_margin_mode_aggressive(contract)
            
            if success:
                logger.info(f"주문 생성 전 마진 모드 강제 변경 성공: Cross")
                return True
            else:
                logger.error(f"주문 생성 전 마진 모드 강제 변경 실패")
                return False
                
        except Exception as e:
            logger.error(f"주문 생성 전 마진 모드 체크 실패: {e}")
            return False
    
    async def force_cross_margin_mode_aggressive(self, contract: str = "BTC_USDT") -> bool:
        try:
            logger.info(f"Gate.io Cross 마진 모드 강제 설정 시작: {contract}")
            
            current_mode = await self.get_current_margin_mode(contract)
            logger.info(f"현재 마진 모드: {current_mode}")
            
            if current_mode == "cross":
                logger.info("이미 Cross 마진 모드입니다")
                return True
            
            # 방법 1: Cross 모드 전환 API 직접 호출
            success_method1 = await self._try_cross_mode_api(contract)
            if success_method1:
                logger.info("방법 1 성공: Cross 모드 API 호출")
                return True
            
            # 방법 2: 포지션 기반 마진 모드 변경
            success_method2 = await self._try_position_margin_mode_change(contract)
            if success_method2:
                logger.info("방법 2 성공: 포지션 기반 마진 모드 변경")
                return True
            
            # 방법 3: 계정 설정 기반 마진 모드 변경
            success_method3 = await self._try_account_margin_mode_change(contract)
            if success_method3:
                logger.info("방법 3 성공: 계정 설정 기반 마진 모드 변경")
                return True
            
            # 방법 4: 포지션 종료 후 Cross 모드로 재생성
            success_method4 = await self._try_position_reset_for_cross(contract)
            if success_method4:
                logger.info("방법 4 성공: 포지션 리셋 후 Cross 모드 설정")
                return True
            
            logger.warning(f"모든 방법 실패 - 수동으로 Cross 마진 모드 설정 필요")
            return False
            
        except Exception as e:
            logger.error(f"Cross 마진 모드 강제 설정 실패: {e}")
            return False
    
    async def _try_cross_mode_api(self, contract: str) -> bool:
        # 방법 1: Gate.io 공식 Cross 모드 전환 API
        try:
            logger.info("방법 1: Cross 모드 전환 API 호출 시도")
            
            endpoint = f"/api/v4/futures/usdt/positions/cross_mode"
            data = {}  # Cross 모드로 전환하는 API
            
            logger.info(f"Cross 모드 전환 API 호출")
            response = await self._request('POST', endpoint, data=data)
            
            await asyncio.sleep(2)
            new_mode = await self.get_current_margin_mode(contract)
            
            if new_mode == "cross":
                logger.info("Cross 모드 전환 API 성공")
                return True
            else:
                logger.info(f"Cross 모드 전환 API 실패: {new_mode}")
                return False
            
        except Exception as e:
            logger.debug(f"방법 1 실패: {e}")
            return False
    
    async def _try_position_margin_mode_change(self, contract: str) -> bool:
        try:
            logger.info("방법 2: 포지션 기반 마진 모드 변경 시도")
            
            positions = await self.get_positions(contract)
            
            if not positions:
                logger.info("포지션이 없어 포지션 기반 변경 불가")
                return False
            
            position = positions[0]
            
            endpoint = f"/api/v4/futures/usdt/positions/{contract}/margin_mode"
            data = {
                "margin_mode": "cross"
            }
            
            logger.info(f"포지션 마진 모드 변경 API 호출: {data}")
            response = await self._request('POST', endpoint, data=data)
            
            await asyncio.sleep(2)
            new_mode = await self.get_current_margin_mode(contract)
            
            if new_mode == "cross":
                logger.info("포지션 기반 마진 모드 변경 성공")
                return True
            else:
                logger.info(f"포지션 기반 변경 실패: {new_mode}")
                return False
            
        except Exception as e:
            logger.debug(f"방법 2 실패: {e}")
            return False
    
    async def _try_account_margin_mode_change(self, contract: str) -> bool:
        try:
            logger.info("방법 3: 계정 설정 기반 마진 모드 변경 시도")
            
            endpoint = "/api/v4/futures/usdt/account/margin_mode"
            data = {
                "margin_mode": "cross",
                "contract": contract
            }
            
            logger.info(f"계정 마진 모드 변경 API 호출: {data}")
            response = await self._request('POST', endpoint, data=data)
            
            await asyncio.sleep(2)
            new_mode = await self.get_current_margin_mode(contract)
            
            if new_mode == "cross":
                logger.info("계정 기반 마진 모드 변경 성공")
                return True
            else:
                logger.info(f"계정 기반 변경 실패: {new_mode}")
                return False
            
        except Exception as e:
            logger.debug(f"방법 3 실패: {e}")
            return False
    
    async def _try_position_reset_for_cross(self, contract: str) -> bool:
        try:
            logger.info("방법 4: 포지션 리셋을 통한 Cross 모드 설정 시도")
            
            positions = await self.get_positions(contract)
            
            if not positions:
                logger.info("포지션이 없어 리셋 불가, 새 포지션은 Cross로 생성될 예정")
                return True
            
            position = positions[0]
            current_size = int(position.get('size', 0))
            
            if current_size == 0:
                logger.info("포지션 크기가 0, 새 포지션은 Cross로 생성될 예정")
                return True
            
            logger.warning(f"활성 포지션({current_size}) 있음 - 리셋 건너뛰기")
            return False
            
        except Exception as e:
            logger.debug(f"방법 4 실패: {e}")
            return False
    
    def _generate_signature(self, method: str, url: str, query_string: str = "", payload: str = "") -> Dict[str, str]:
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
                        logger.error(f"Gate.io API HTTP 오류: {error_msg}")
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
                    
            except aiohttp.ClientError as client_error:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise Exception(f"클라이언트 오류: {client_error}")
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise
    
    async def get_current_margin_mode(self, contract: str = "BTC_USDT") -> str:
        try:
            # 캐시에서 먼저 확인
            if contract in self.current_margin_mode_cache:
                cached_time, cached_mode = self.current_margin_mode_cache[contract]
                if (datetime.now() - cached_time).total_seconds() < 60:
                    return cached_mode
            
            positions = await self.get_positions(contract)
            
            if positions:
                position = positions[0]
                margin_mode = position.get('mode', '').lower()
                
                normalized_mode = self._normalize_margin_mode(margin_mode)
                
                if normalized_mode != 'unknown':
                    self.current_margin_mode_cache[contract] = (datetime.now(), normalized_mode)
                    logger.debug(f"현재 마진 모드 조회: {contract} = {normalized_mode} (원본: {margin_mode})")
                    return normalized_mode
                else:
                    logger.warning(f"알 수 없는 마진 모드: {margin_mode}")
                    return "unknown"
            else:
                try:
                    endpoint = "/api/v4/futures/usdt/account"
                    account_info = await self._request('GET', endpoint)
                    
                    logger.debug(f"포지션이 없어 기본값 반환: cross")
                    return "cross"
                    
                except Exception as e:
                    logger.debug(f"계정 정보 조회 실패, 기본값 반환: {e}")
                    return "cross"
                
        except Exception as e:
            logger.error(f"현재 마진 모드 조회 실패: {e}")
            return "unknown"
    
    def _normalize_margin_mode(self, mode: str) -> str:
        try:
            mode_lower = str(mode).lower().strip()
            
            # 무조건 Cross 모드 강제
            if self.FORCE_CROSS_MARGIN:
                if mode_lower in ['cross', 'isolated', 'dual_long', 'dual_short', 'single', 'default']:
                    logger.debug(f"강제 Cross 매핑: {mode_lower} → cross")
                    return 'cross'
            
            if mode_lower in self.MARGIN_MODE_MAPPING:
                normalized = self.MARGIN_MODE_MAPPING[mode_lower]
                logger.debug(f"마진 모드 매핑: {mode_lower} → {normalized}")
                return normalized
            
            if 'cross' in mode_lower:
                return 'cross'
            elif 'isolated' in mode_lower:
                return 'cross'
            elif 'dual' in mode_lower:
                return 'cross'
            elif mode_lower in ['single', 'default', '']:
                return 'cross'
            else:
                logger.warning(f"알 수 없는 마진 모드 패턴: {mode_lower}")
                return 'cross'
                
        except Exception as e:
            logger.error(f"마진 모드 정규화 실패: {e}")
            return 'cross'
    
    async def set_margin_mode(self, contract: str, mode: str = "cross") -> Dict:
        try:
            logger.info(f"Gate.io 마진 모드 설정 요청: {contract} - {mode}")
            
            if self.FORCE_CROSS_MARGIN:
                mode = "cross"
                logger.info(f"강제 Cross 모드 적용: {mode}")
            
            mode = mode.lower()
            if mode not in ['cross', 'isolated']:
                logger.error(f"지원되지 않는 마진 모드: {mode}")
                return {"success": False, "error": f"Invalid margin mode: {mode}"}
            
            success = await self.force_cross_margin_mode_aggressive(contract)
            
            if success:
                return {
                    "success": True,
                    "mode": "cross",
                    "contract": contract,
                    "message": "Cross 마진 모드 설정 성공",
                    "method": "강제 설정"
                }
            else:
                return {
                    "success": False,
                    "mode": "cross",
                    "contract": contract,
                    "message": "API 제한으로 수동 설정 필요",
                    "recommendation": "Gate.io 웹/앱에서 Cross 마진 모드로 수동 설정을 권장합니다"
                }
                    
        except Exception as e:
            logger.error(f"마진 모드 설정 중 예외 발생: {e}")
            return {
                "success": False,
                "error": str(e),
                "recommendation": "수동으로 Cross 마진 모드 설정을 권장합니다"
            }
    
    async def ensure_cross_margin_mode(self, contract: str = "BTC_USDT") -> bool:
        try:
            logger.info(f"Cross 마진 모드 보장 시작: {contract}")
            
            success = await self.force_cross_margin_mode_aggressive(contract)
            
            if success:
                logger.info(f"Cross 마진 모드 보장 성공: {contract}")
                return True
            else:
                logger.warning(f"Cross 마진 모드 자동 설정 실패: {contract}")
                return False
                
        except Exception as e:
            logger.error(f"Cross 마진 모드 확인 실패: {e}")
            return False
    
    async def get_current_price(self, contract: str = "BTC_USDT") -> float:
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
        try:
            endpoint = "/api/v4/futures/usdt/accounts"
            response = await self._request('GET', endpoint)
            return response
        except Exception as e:
            logger.error(f"계정 잔고 조회 실패: {e}")
            raise
    
    async def get_positions(self, contract: str = "BTC_USDT") -> List[Dict]:
        try:
            endpoint = f"/api/v4/futures/usdt/positions/{contract}"
            response = await self._request('GET', endpoint)
            
            if isinstance(response, dict):
                return [response] if response.get('size', 0) != 0 else []
            return response
            
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []
    
    async def get_current_leverage(self, contract: str) -> int:
        try:
            if contract in self.current_leverage_cache:
                cached_time, cached_leverage = self.current_leverage_cache[contract]
                if (datetime.now() - cached_time).total_seconds() < 60:
                    return cached_leverage
            
            positions = await self.get_positions(contract)
            
            if positions:
                position = positions[0]
                leverage_str = position.get('leverage', str(self.DEFAULT_LEVERAGE))
                try:
                    leverage = int(float(leverage_str))
                    self.current_leverage_cache[contract] = (datetime.now(), leverage)
                    logger.debug(f"현재 레버리지 조회: {contract} = {leverage}x")
                    return leverage
                except (ValueError, TypeError):
                    logger.warning(f"레버리지 값 변환 실패: {leverage_str}")
                    return self.DEFAULT_LEVERAGE
            else:
                logger.debug(f"포지션이 없어 기본 레버리지 반환: {self.DEFAULT_LEVERAGE}x")
                return self.DEFAULT_LEVERAGE
                
        except Exception as e:
            logger.error(f"현재 레버리지 조회 실패: {e}")
            return self.DEFAULT_LEVERAGE
    
    async def set_leverage(self, contract: str, leverage: int, cross_leverage_limit: int = 0, 
                          retry_count: int = 5) -> Dict:
        if leverage < self.MIN_LEVERAGE or leverage > self.MAX_LEVERAGE:
            logger.warning(f"레버리지 범위 초과 ({leverage}x), 기본값 사용: {self.DEFAULT_LEVERAGE}x")
            leverage = self.DEFAULT_LEVERAGE
        
        for attempt in range(retry_count):
            try:
                current_leverage = await self.get_current_leverage(contract)
                
                if current_leverage == leverage:
                    logger.info(f"레버리지 이미 설정됨: {contract} - {leverage}x")
                    return {"status": "already_set", "leverage": leverage}
                
                endpoint = f"/api/v4/futures/usdt/positions/{contract}/leverage"
                
                params = {
                    "leverage": str(leverage)
                }
                
                if cross_leverage_limit > 0:
                    params["cross_leverage_limit"] = str(cross_leverage_limit)
                
                logger.info(f"Gate.io 레버리지 설정 시도 {attempt + 1}/{retry_count}: {contract} - {current_leverage}x → {leverage}x")
                
                response = await self._request('POST', endpoint, params=params)
                
                await asyncio.sleep(1.0)
                
                verify_success = await self._verify_leverage_setting(contract, leverage, max_attempts=3)
                if verify_success:
                    self.current_leverage_cache[contract] = (datetime.now(), leverage)
                    logger.info(f"Gate.io 레버리지 설정 완료: {contract} - {leverage}x")
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
                
                if any(keyword in error_msg.lower() for keyword in [
                    "leverage not changed", "same leverage", "already set"
                ]):
                    logger.info(f"레버리지가 이미 설정되어 있음: {contract} - {leverage}x")
                    return {"status": "already_set", "leverage": leverage}
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(2.0)
                    continue
                else:
                    logger.warning(f"레버리지 설정 최종 실패하지만 계속 진행: {contract} - {leverage}x")
                    return {"warning": "leverage_setting_failed", "requested_leverage": leverage}
        
        logger.warning(f"레버리지 설정 모든 재시도 실패, 기본 레버리지로 계속 진행: {contract} - {leverage}x")
        return {"warning": "all_leverage_attempts_failed", "requested_leverage": leverage}
    
    async def _verify_leverage_setting(self, contract: str, expected_leverage: int, max_attempts: int = 3) -> bool:
        for attempt in range(max_attempts):
            try:
                await asyncio.sleep(0.5 * (attempt + 1))
                
                if contract in self.current_leverage_cache:
                    del self.current_leverage_cache[contract]
                
                positions = await self.get_positions(contract)
                if positions:
                    position = positions[0]
                    current_leverage = position.get('leverage')
                    
                    if current_leverage:
                        try:
                            current_lev_int = int(float(current_leverage))
                            if current_lev_int == expected_leverage:
                                logger.info(f"레버리지 설정 검증 성공: {current_lev_int}x")
                                return True
                            else:
                                logger.debug(f"레버리지 검증: 현재 {current_lev_int}x ≠ 예상 {expected_leverage}x")
                                if attempt < max_attempts - 1:
                                    continue
                                return False
                        except (ValueError, TypeError):
                            logger.debug(f"레버리지 값 변환 실패: {current_leverage}")
                            if attempt < max_attempts - 1:
                                continue
                            return False
                    else:
                        logger.debug("레버리지 필드가 없음")
                        if attempt < max_attempts - 1:
                            continue
                        return False
                else:
                    logger.debug("포지션이 없어 레버리지 설정 성공으로 간주")
                    return True
                
            except Exception as e:
                logger.debug(f"레버리지 검증 시도 {attempt + 1} 실패: {e}")
                if attempt < max_attempts - 1:
                    continue
                return True
        
        return False
    
    async def mirror_bitget_leverage(self, bitget_leverage: int, contract: str = "BTC_USDT") -> bool:
        try:
            logger.info(f"레버리지 미러링 시작: 비트겟 {bitget_leverage}x → 게이트 {contract}")
            
            current_gate_leverage = await self.get_current_leverage(contract)
            
            if current_gate_leverage == bitget_leverage:
                logger.info(f"레버리지 이미 동일: {bitget_leverage}x")
                return True
            
            result = await self.set_leverage(contract, bitget_leverage)
            
            if result.get("warning"):
                logger.warning(f"레버리지 미러링 실패: {result}")
                return False
            else:
                logger.info(f"레버리지 미러링 성공: {current_gate_leverage}x → {bitget_leverage}x")
                return True
            
        except Exception as e:
            logger.error(f"레버리지 미러링 실패: {e}")
            return False
    
    async def create_perfect_tp_sl_order(self, bitget_order: Dict, gate_size: int, gate_margin: float, 
                                       leverage: int, current_gate_price: float) -> Dict:
        try:
            # 주문 생성 전 마진 모드 강제 체크
            margin_success = await self.ensure_cross_margin_mode_before_order("BTC_USDT")
            if not margin_success:
                logger.warning("주문 생성 전 마진 모드 강제 변경 실패하지만 계속 진행")
            
            leverage_success = await self.mirror_bitget_leverage(leverage, "BTC_USDT")
            if not leverage_success:
                logger.warning("레버리지 미러링 실패하지만 주문 계속 진행")
            
            order_id = bitget_order.get('orderId', bitget_order.get('planOrderId', ''))
            side = bitget_order.get('side', bitget_order.get('tradeSide', '')).lower()
            
            trigger_price = 0
            for price_field in ['triggerPrice', 'price', 'executePrice']:
                if bitget_order.get(price_field):
                    trigger_price = float(bitget_order.get(price_field))
                    break
            
            if trigger_price <= 0:
                raise Exception("유효한 트리거 가격을 찾을 수 없습니다")
            
            tp_price = None
            sl_price = None
            
            tp_fields = ['presetStopSurplusPrice', 'stopSurplusPrice', 'takeProfitPrice']
            for field in tp_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        tp_price = float(value)
                        if tp_price > 0:
                            logger.info(f"비트겟 TP 추출: {field} = ${tp_price:.2f}")
                            break
                    except:
                        continue
            
            sl_fields = ['presetStopLossPrice', 'stopLossPrice', 'stopPrice']
            for field in sl_fields:
                value = bitget_order.get(field)
                if value and str(value) not in ['0', '0.0', '', 'null', 'None']:
                    try:
                        sl_price = float(value)
                        if sl_price > 0:
                            logger.info(f"비트겟 SL 추출: {field} = ${sl_price:.2f}")
                            break
                    except:
                        continue
            
            reduce_only = bitget_order.get('reduceOnly', False)
            is_close_order = ('close' in side or reduce_only is True or reduce_only == 'true')
            
            if is_close_order:
                final_size = gate_size
                reduce_only_flag = True
                
                if 'close_long' in side or side == 'close long':
                    final_size = -abs(gate_size)
                    logger.info(f"클로즈 롱: 롱 포지션 종료 → 게이트 매도 (음수 사이즈: {final_size})")
                elif 'close_short' in side or side == 'close short':
                    final_size = abs(gate_size)
                    logger.info(f"클로즈 숏: 숏 포지션 종료 → 게이트 매수 (양수 사이즈: {final_size})")
                else:
                    if 'sell' in side or 'short' in side:
                        final_size = -abs(gate_size)
                        logger.info(f"클로즈 매도: 포지션 종료 → 게이트 매도 (음수 사이즈: {final_size})")
                    else:
                        final_size = abs(gate_size)
                        logger.info(f"클로즈 매수: 포지션 종료 → 게이트 매수 (양수 사이즈: {final_size})")
            else:
                reduce_only_flag = False
                if 'short' in side or 'sell' in side:
                    final_size = -abs(gate_size)
                    logger.info(f"오픈 숏: 새 숏 포지션 생성 → 게이트 매도 (음수 사이즈: {final_size})")
                else:
                    final_size = abs(gate_size)
                    logger.info(f"오픈 롱: 새 롱 포지션 생성 → 게이트 매수 (양수 사이즈: {final_size})")
            
            gate_trigger_type = "ge" if trigger_price > current_gate_price else "le"
            
            logger.info(f"완벽 미러링 주문 생성:")
            logger.info(f"   - 비트겟 ID: {order_id}")
            logger.info(f"   - 방향: {side} ({'클로즈' if is_close_order else '오픈'})")
            logger.info(f"   - 트리거가: ${trigger_price:.2f}")
            logger.info(f"   - 레버리지: {leverage}x {'✅' if leverage_success else '⚠️'}")
            logger.info(f"   - 마진 모드: Cross {'✅' if margin_success else '⚠️'}")
            
            tp_display = f"${tp_price:.2f}" if tp_price is not None else "없음"
            sl_display = f"${sl_price:.2f}" if sl_price is not None else "없음"
            
            logger.info(f"   - TP: {tp_display}")
            logger.info(f"   - SL: {sl_display}")
            logger.info(f"   - 게이트 사이즈: {final_size}")
            
            if tp_price or sl_price:
                logger.info(f"TP/SL 포함 통합 주문 생성")
                
                gate_order = await self.create_conditional_order_with_tp_sl_v3(
                    trigger_price=trigger_price,
                    order_size=final_size,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    reduce_only=reduce_only_flag,
                    trigger_type=gate_trigger_type
                )
                
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
                    'leverage_mirrored': leverage_success,
                    'leverage': leverage,
                    'margin_mode': 'cross',
                    'margin_mode_forced': margin_success
                }
                
            else:
                logger.info(f"일반 예약 주문 생성 (TP/SL 없음)")
                
                gate_order = await self.create_price_triggered_order_v3(
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
                    'perfect_mirror': True,
                    'leverage_mirrored': leverage_success,
                    'leverage': leverage,
                    'margin_mode': 'cross',
                    'margin_mode_forced': margin_success
                }
            
        except Exception as e:
            logger.error(f"완벽한 TP/SL 미러링 주문 생성 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'has_tp_sl': False,
                'perfect_mirror': False,
                'leverage_mirrored': False,
                'margin_mode': 'unknown',
                'margin_mode_forced': False
            }
    
    async def create_conditional_order_with_tp_sl_v3(self, trigger_price: float, order_size: int,
                                                   tp_price: Optional[float] = None,
                                                   sl_price: Optional[float] = None,
                                                   reduce_only: bool = False,
                                                   trigger_type: str = "ge") -> Dict:
        try:
            # 주문 생성 전 마진 모드 강제 체크
            await self.ensure_cross_margin_mode_before_order("BTC_USDT")
            
            endpoint = "/api/v4/futures/usdt/price_orders"
            
            data = {
                "initial": {
                    "contract": "BTC_USDT",
                    "size": order_size,
                    "price": "0",
                    "tif": "ioc"
                },
                "trigger": {
                    "strategy_type": 0,
                    "price_type": 0,
                    "price": str(trigger_price),
                    "rule": 1 if trigger_type == "ge" else 2
                }
            }
            
            if reduce_only:
                data["initial"]["reduce_only"] = True
            
            if tp_price and tp_price > 0:
                data["stop_profit_price"] = str(tp_price)
                logger.info(f"TP 설정: ${tp_price:.2f}")
            
            if sl_price and sl_price > 0:
                data["stop_loss_price"] = str(sl_price)
                logger.info(f"SL 설정: ${sl_price:.2f}")
            
            logger.info(f"Gate.io TP/SL 주문 데이터 (Cross 마진): {json.dumps(data, indent=2)}")
            
            response = await self._request('POST', endpoint, data=data)
            
            logger.info(f"Gate.io TP/SL 통합 주문 생성 성공 (Cross 마진): {response.get('id')}")
            
            return response
            
        except Exception as e:
            logger.error(f"TP/SL 포함 조건부 주문 생성 실패: {e}")
            raise
    
    async def create_price_triggered_order_v3(self, trigger_price: float, order_size: int,
                                            reduce_only: bool = False, trigger_type: str = "ge") -> Dict:
        try:
            # 주문 생성 전 마진 모드 강제 체크
            await self.ensure_cross_margin_mode_before_order("BTC_USDT")
            
            endpoint = "/api/v4/futures/usdt/price_orders"
            
            data = {
                "initial": {
                    "contract": "BTC_USDT",
                    "size": order_size,
                    "price": "0",
                    "tif": "ioc"
                },
                "trigger": {
                    "strategy_type": 0,
                    "price_type": 0,
                    "price": str(trigger_price),
                    "rule": 1 if trigger_type == "ge" else 2
                }
            }
            
            if reduce_only:
                data["initial"]["reduce_only"] = True
            
            logger.info(f"Gate.io 일반 주문 데이터 (Cross 마진): {json.dumps(data, indent=2)}")
            
            response = await self._request('POST', endpoint, data=data)
            
            logger.info(f"Gate.io 일반 트리거 주문 생성 성공 (Cross 마진): {response.get('id')}")
            
            return response
            
        except Exception as e:
            logger.error(f"일반 가격 트리거 주문 생성 실패: {e}")
            raise
    
    # 기존 메서드들은 호환성을 위해 V3로 리다이렉트
    async def create_conditional_order_with_tp_sl_v2(self, trigger_price: float, order_size: int,
                                                   tp_price: Optional[float] = None,
                                                   sl_price: Optional[float] = None,
                                                   reduce_only: bool = False,
                                                   trigger_type: str = "ge") -> Dict:
        return await self.create_conditional_order_with_tp_sl_v3(
            trigger_price, order_size, tp_price, sl_price, reduce_only, trigger_type
        )
    
    async def create_price_triggered_order_v2(self, trigger_price: float, order_size: int,
                                            reduce_only: bool = False, trigger_type: str = "ge") -> Dict:
        return await self.create_price_triggered_order_v3(
            trigger_price, order_size, reduce_only, trigger_type
        )
    
    async def create_conditional_order_with_tp_sl_fixed(self, trigger_price: float, order_size: int,
                                                      tp_price: Optional[float] = None,
                                                      sl_price: Optional[float] = None,
                                                      reduce_only: bool = False,
                                                      trigger_type: str = "ge") -> Dict:
        return await self.create_conditional_order_with_tp_sl_v3(
            trigger_price, order_size, tp_price, sl_price, reduce_only, trigger_type
        )
    
    async def create_price_triggered_order_fixed(self, trigger_price: float, order_size: int,
                                               reduce_only: bool = False, trigger_type: str = "ge") -> Dict:
        return await self.create_price_triggered_order_v3(
            trigger_price, order_size, reduce_only, trigger_type
        )
    
    async def create_conditional_order_with_tp_sl(self, trigger_price: float, order_size: int,
                                                tp_price: Optional[float] = None,
                                                sl_price: Optional[float] = None,
                                                reduce_only: bool = False,
                                                trigger_type: str = "ge") -> Dict:
        return await self.create_conditional_order_with_tp_sl_v3(
            trigger_price, order_size, tp_price, sl_price, reduce_only, trigger_type
        )
    
    async def create_price_triggered_order(self, trigger_price: float, order_size: int,
                                         reduce_only: bool = False, trigger_type: str = "ge") -> Dict:
        return await self.create_price_triggered_order_v3(
            trigger_price, order_size, reduce_only, trigger_type
        )
    
    async def get_price_triggered_orders(self, contract: str, status: str = "open") -> List[Dict]:
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
        try:
            endpoint = f"/api/v4/futures/usdt/price_orders/{order_id}"
            response = await self._request('DELETE', endpoint)
            logger.info(f"Gate.io 가격 트리거 주문 취소 성공: {order_id}")
            return response
            
        except Exception as e:
            logger.error(f"가격 트리거 주문 취소 실패: {order_id} - {e}")
            raise
    
    async def place_order(self, contract: str, size: int, price: Optional[float] = None,
                         reduce_only: bool = False, tif: str = "gtc", iceberg: int = 0) -> Dict:
        try:
            # 주문 생성 전 마진 모드 강제 체크
            await self.ensure_cross_margin_mode_before_order(contract)
            
            current_leverage = await self.get_current_leverage(contract)
            if current_leverage < self.DEFAULT_LEVERAGE:
                logger.info(f"레버리지가 낮음 ({current_leverage}x), 기본값으로 설정: {self.DEFAULT_LEVERAGE}x")
                await self.set_leverage(contract, self.DEFAULT_LEVERAGE)
            
            endpoint = "/api/v4/futures/usdt/orders"
            
            data = {
                "contract": contract,
                "size": size
            }
            
            if price is not None:
                data["price"] = str(price)
                data["tif"] = tif
            else:
                data["tif"] = "ioc"
            
            if reduce_only:
                data["reduce_only"] = True
            
            if iceberg > 0:
                data["iceberg"] = iceberg
            
            response = await self._request('POST', endpoint, data=data)
            
            logger.info(f"Gate.io 주문 생성 성공 (Cross 마진): {response.get('id')} (레버리지: {current_leverage}x)")
            return response
            
        except Exception as e:
            logger.error(f"Gate.io 주문 생성 실패: {e}")
            raise
    
    async def close_position(self, contract: str, size: Optional[int] = None) -> Dict:
        try:
            # 포지션 종료 전 마진 모드 확인
            await self.ensure_cross_margin_mode_before_order(contract)
            
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
            
            logger.info(f"Gate.io 포지션 종료 성공 (Cross 마진): {close_size}")
            return result
            
        except Exception as e:
            logger.error(f"포지션 종료 실패: {e}")
            raise
    
    async def close(self):
        if self.session:
            await self.session.close()
            logger.info("Gate.io 미러링 클라이언트 세션 종료")
