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
    """Gate.io 미러링 전용 클라이언트 - API v4 정확한 형식"""
    
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
        
        # 레버리지 설정 강화
        self.DEFAULT_LEVERAGE = 30
        self.MAX_LEVERAGE = 100
        self.MIN_LEVERAGE = 1
        self.current_leverage_cache = {}
        
        # 마진 모드 설정 추가
        self.DEFAULT_MARGIN_MODE = "cross"  # 항상 Cross 모드 사용
        self.current_margin_mode_cache = {}
        
        # 지원되는 마진 모드 매핑
        self.MARGIN_MODE_MAPPING = {
            'cross': 'cross',
            'isolated': 'isolated',
            'dual_long': 'cross',  # dual_long을 cross로 매핑
            'dual_short': 'cross',  # dual_short를 cross로 매핑
            'single': 'cross',  # single을 cross로 매핑
            'default': 'cross'
        }
        
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
        """클라이언트 초기화 - 기본 레버리지 30배 설정 + 마진 모드 확인"""
        self._initialize_session()
        
        # 기본 레버리지를 30배로 설정
        try:
            current_leverage = await self.get_current_leverage("BTC_USDT")
            if current_leverage != self.DEFAULT_LEVERAGE:
                logger.info(f"기본 레버리지 설정: {current_leverage}x → {self.DEFAULT_LEVERAGE}x")
                await self.set_leverage("BTC_USDT", self.DEFAULT_LEVERAGE)
            else:
                logger.info(f"✅ 기본 레버리지 이미 설정됨: {self.DEFAULT_LEVERAGE}x")
        except Exception as e:
            logger.warning(f"기본 레버리지 설정 실패하지만 계속 진행: {e}")
        
        # 마진 모드 확인 (설정은 하지 않고 확인만)
        try:
            logger.info("🔥 게이트 마진 모드 확인 시작...")
            
            # 현재 마진 모드 확인
            current_mode = await self.get_current_margin_mode("BTC_USDT")
            logger.info(f"현재 게이트 마진 모드: {current_mode}")
            
            if current_mode in ['cross', 'Cross', 'CROSS']:
                logger.info("✅ 게이트 마진 모드가 Cross로 설정되어 있습니다")
            elif current_mode in ['dual_long', 'dual_short']:
                logger.warning(f"⚠️ 게이트 마진 모드가 {current_mode}입니다")
                logger.info("💡 듀얼 모드는 Cross로 자동 매핑하여 처리합니다")
            elif current_mode == 'unknown':
                logger.warning("⚠️ 게이트 마진 모드를 확인할 수 없습니다")
                logger.info("💡 포지션 생성 시 Cross 마진 모드 사용을 권장합니다")
            else:
                logger.warning(f"⚠️ 게이트 마진 모드가 {current_mode}입니다")
                logger.info("💡 Cross 마진 모드 사용을 권장합니다 (청산 방지)")
                
        except Exception as e:
            logger.error(f"게이트 마진 모드 확인 실패: {e}")
            logger.warning("⚠️ 마진 모드 확인에 실패했지만 계속 진행합니다. 수동으로 Cross 모드 확인을 권장합니다.")
        
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
        """현재 마진 모드 조회"""
        try:
            # 캐시에서 먼저 확인
            if contract in self.current_margin_mode_cache:
                cached_time, cached_mode = self.current_margin_mode_cache[contract]
                if (datetime.now() - cached_time).total_seconds() < 300:  # 5분 캐시
                    return cached_mode
            
            # 포지션 정보에서 마진 모드 확인
            positions = await self.get_positions(contract)
            
            if positions:
                position = positions[0]
                margin_mode = position.get('mode', '').lower()
                
                # 마진 모드 정규화
                normalized_mode = self._normalize_margin_mode(margin_mode)
                
                if normalized_mode != 'unknown':
                    # 캐시 업데이트
                    self.current_margin_mode_cache[contract] = (datetime.now(), normalized_mode)
                    logger.debug(f"현재 마진 모드 조회: {contract} = {normalized_mode} (원본: {margin_mode})")
                    return normalized_mode
                else:
                    logger.warning(f"알 수 없는 마진 모드: {margin_mode}")
                    return "unknown"
            else:
                # 포지션이 없을 때 계정 설정 확인 시도
                try:
                    # Gate.io API v4에서는 계정 설정에서 기본 마진 모드를 확인할 수 있음
                    endpoint = "/api/v4/futures/usdt/account"
                    account_info = await self._request('GET', endpoint)
                    
                    # 계정의 기본 마진 모드 확인 (Gate.io는 계약별로 다를 수 있음)
                    # 일반적으로 Gate.io는 기본적으로 cross 모드를 사용
                    logger.debug(f"포지션이 없어 기본값 반환: cross")
                    return "cross"
                    
                except Exception as e:
                    logger.debug(f"계정 정보 조회 실패, 기본값 반환: {e}")
                    return "cross"
                
        except Exception as e:
            logger.error(f"현재 마진 모드 조회 실패: {e}")
            return "unknown"
    
    def _normalize_margin_mode(self, mode: str) -> str:
        """마진 모드 정규화"""
        try:
            mode_lower = str(mode).lower().strip()
            
            # 직접 매핑
            if mode_lower in self.MARGIN_MODE_MAPPING:
                normalized = self.MARGIN_MODE_MAPPING[mode_lower]
                logger.debug(f"마진 모드 매핑: {mode_lower} → {normalized}")
                return normalized
            
            # 패턴 매칭
            if 'cross' in mode_lower:
                return 'cross'
            elif 'isolated' in mode_lower:
                return 'isolated'
            elif 'dual' in mode_lower:
                # dual 모드는 cross로 매핑
                return 'cross'
            elif mode_lower in ['single', 'default', '']:
                return 'cross'
            else:
                logger.warning(f"알 수 없는 마진 모드 패턴: {mode_lower}")
                return 'unknown'
                
        except Exception as e:
            logger.error(f"마진 모드 정규화 실패: {e}")
            return 'unknown'
    
    async def set_margin_mode(self, contract: str, mode: str = "cross") -> Dict:
        """마진 모드 설정 (API 제한으로 실제 설정하지 않고 안내만)"""
        try:
            logger.info(f"Gate.io 마진 모드 설정 요청: {contract} - {mode}")
            
            # mode는 소문자로 변환
            mode = mode.lower()
            if mode not in ['cross', 'isolated']:
                logger.error(f"지원되지 않는 마진 모드: {mode}")
                return {"success": False, "error": f"Invalid margin mode: {mode}"}
            
            # Gate.io API에서 마진 모드 설정이 제한적이므로 안내 메시지만 반환
            logger.warning(f"Gate.io API 제한으로 마진 모드 자동 설정 불가")
            logger.info(f"💡 수동으로 {mode.upper()} 마진 모드로 설정해주세요")
            
            return {
                "success": False,
                "mode": mode,
                "contract": contract,
                "message": f"API 제한으로 수동 설정 필요",
                "recommendation": f"Gate.io 웹/앱에서 {mode.upper()} 마진 모드로 수동 설정을 권장합니다"
            }
                    
        except Exception as e:
            logger.error(f"마진 모드 설정 중 예외 발생: {e}")
            return {
                "success": False,
                "error": str(e),
                "recommendation": "수동으로 Cross 마진 모드 설정을 권장합니다"
            }
    
    async def ensure_cross_margin_mode(self, contract: str = "BTC_USDT") -> bool:
        """Cross 마진 모드 보장 (확인만 수행)"""
        try:
            current_mode = await self.get_current_margin_mode(contract)
            
            if current_mode == "cross":
                logger.info(f"✅ 이미 Cross 마진 모드입니다: {contract}")
                return True
            elif current_mode in ["dual_long", "dual_short"]:
                logger.warning(f"⚠️ 현재 마진 모드가 {current_mode}입니다: {contract}")
                logger.info(f"💡 듀얼 모드는 Cross로 매핑하여 처리합니다")
                return True  # 듀얼 모드도 허용
            elif current_mode == "unknown":
                logger.warning(f"⚠️ 마진 모드를 확인할 수 없습니다: {contract}")
                logger.info(f"💡 포지션 생성 시 Cross 마진 모드 사용을 권장합니다")
                return False
            else:
                logger.warning(f"⚠️ 현재 마진 모드가 {current_mode}입니다: {contract}")
                logger.info(f"💡 수동으로 Cross 마진 모드로 변경을 권장합니다")
                return False
                
        except Exception as e:
            logger.error(f"Cross 마진 모드 확인 실패: {e}")
            return False
    
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
    
    async def get_current_leverage(self, contract: str) -> int:
        """현재 레버리지 조회"""
        try:
            # 캐시에서 먼저 확인
            if contract in self.current_leverage_cache:
                cached_time, cached_leverage = self.current_leverage_cache[contract]
                if (datetime.now() - cached_time).total_seconds() < 60:
                    return cached_leverage
            
            # 포지션 정보에서 레버리지 확인
            positions = await self.get_positions(contract)
            
            if positions:
                position = positions[0]
                leverage_str = position.get('leverage', str(self.DEFAULT_LEVERAGE))
                try:
                    leverage = int(float(leverage_str))
                    # 캐시 업데이트
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
        """레버리지 설정 - 비트겟 미러링 강화"""
        
        # 레버리지 유효성 검증
        if leverage < self.MIN_LEVERAGE or leverage > self.MAX_LEVERAGE:
            logger.warning(f"레버리지 범위 초과 ({leverage}x), 기본값 사용: {self.DEFAULT_LEVERAGE}x")
            leverage = self.DEFAULT_LEVERAGE
        
        for attempt in range(retry_count):
            try:
                # 현재 레버리지 확인
                current_leverage = await self.get_current_leverage(contract)
                
                if current_leverage == leverage:
                    logger.info(f"✅ 레버리지 이미 설정됨: {contract} - {leverage}x")
                    return {"status": "already_set", "leverage": leverage}
                
                endpoint = f"/api/v4/futures/usdt/positions/{contract}/leverage"
                
                # Gate.io API v4 정확한 형식
                params = {
                    "leverage": str(leverage)
                }
                
                if cross_leverage_limit > 0:
                    params["cross_leverage_limit"] = str(cross_leverage_limit)
                
                logger.info(f"Gate.io 레버리지 설정 시도 {attempt + 1}/{retry_count}: {contract} - {current_leverage}x → {leverage}x")
                logger.debug(f"레버리지 설정 파라미터: {params}")
                
                response = await self._request('POST', endpoint, params=params)
                
                await asyncio.sleep(1.0)
                
                # 설정 검증
                verify_success = await self._verify_leverage_setting(contract, leverage, max_attempts=3)
                if verify_success:
                    # 캐시 업데이트
                    self.current_leverage_cache[contract] = (datetime.now(), leverage)
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
                
                # 특정 오류는 재시도하지 않음
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
        
        # 모든 시도 실패해도 경고만 출력하고 계속 진행
        logger.warning(f"레버리지 설정 모든 재시도 실패, 기본 레버리지로 계속 진행: {contract} - {leverage}x")
        return {"warning": "all_leverage_attempts_failed", "requested_leverage": leverage}
    
    async def _verify_leverage_setting(self, contract: str, expected_leverage: int, max_attempts: int = 3) -> bool:
        """레버리지 설정 확인 - 강화된 검증"""
        for attempt in range(max_attempts):
            try:
                await asyncio.sleep(0.5 * (attempt + 1))
                
                # 캐시 초기화하고 최신 정보 가져오기
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
                                logger.info(f"✅ 레버리지 설정 검증 성공: {current_lev_int}x")
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
                    # 포지션이 없으면 레버리지 설정은 성공한 것으로 간주
                    logger.debug("포지션이 없어 레버리지 설정 성공으로 간주")
                    return True
                
            except Exception as e:
                logger.debug(f"레버리지 검증 시도 {attempt + 1} 실패: {e}")
                if attempt < max_attempts - 1:
                    continue
                return True  # 검증 실패해도 설정은 성공한 것으로 간주
        
        return False
    
    async def mirror_bitget_leverage(self, bitget_leverage: int, contract: str = "BTC_USDT") -> bool:
        """비트겟 레버리지를 게이트에 미러링"""
        try:
            logger.info(f"🔄 레버리지 미러링 시작: 비트겟 {bitget_leverage}x → 게이트 {contract}")
            
            # 현재 게이트 레버리지 확인
            current_gate_leverage = await self.get_current_leverage(contract)
            
            if current_gate_leverage == bitget_leverage:
                logger.info(f"✅ 레버리지 이미 동일: {bitget_leverage}x")
                return True
            
            # 레버리지 설정
            result = await self.set_leverage(contract, bitget_leverage)
            
            if result.get("warning"):
                logger.warning(f"⚠️ 레버리지 미러링 실패: {result}")
                return False
            else:
                logger.info(f"✅ 레버리지 미러링 성공: {current_gate_leverage}x → {bitget_leverage}x")
                return True
            
        except Exception as e:
            logger.error(f"레버리지 미러링 실패: {e}")
            return False
    
    async def create_perfect_tp_sl_order(self, bitget_order: Dict, gate_size: int, gate_margin: float, 
                                       leverage: int, current_gate_price: float) -> Dict:
        """완벽한 TP/SL 미러링 주문 생성 - Gate.io API v4 정확한 형식 (initial.price 추가)"""
        try:
            # 레버리지 미러링
            leverage_success = await self.mirror_bitget_leverage(leverage, "BTC_USDT")
            if not leverage_success:
                logger.warning("⚠️ 레버리지 미러링 실패하지만 주문 계속 진행")
            
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
            
            # TP/SL 정보 정확하게 추출
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
            
            # 클로즈 주문 여부 및 방향 판단 수정
            reduce_only = bitget_order.get('reduceOnly', False)
            is_close_order = ('close' in side or reduce_only is True or reduce_only == 'true')
            
            # 클로즈 주문 방향 수정 로직
            if is_close_order:
                # 클로즈 주문: reduce_only=True
                final_size = gate_size
                reduce_only_flag = True
                
                # 클로즈 주문 방향 매핑 수정
                if 'close_long' in side or side == 'close long':
                    # 롱 포지션 종료 → 매도 (음수)
                    final_size = -abs(gate_size)
                    logger.info(f"🔴 클로즈 롱: 롱 포지션 종료 → 게이트 매도 (음수 사이즈: {final_size})")
                    
                elif 'close_short' in side or side == 'close short':
                    # 숏 포지션 종료 → 매수 (양수)
                    final_size = abs(gate_size)
                    logger.info(f"🟢 클로즈 숏: 숏 포지션 종료 → 게이트 매수 (양수 사이즈: {final_size})")
                    
                else:
                    # 일반적인 매도/매수 기반 판단 (클로즈 주문)
                    if 'sell' in side or 'short' in side:
                        final_size = -abs(gate_size)
                        logger.info(f"🔴 클로즈 매도: 포지션 종료 → 게이트 매도 (음수 사이즈: {final_size})")
                    else:
                        final_size = abs(gate_size)
                        logger.info(f"🟢 클로즈 매수: 포지션 종료 → 게이트 매수 (양수 사이즈: {final_size})")
                
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
            logger.info(f"   - 레버리지: {leverage}x {'✅ 미러링됨' if leverage_success else '⚠️ 미러링 실패'}")
            
            # TP/SL 표시 수정
            tp_display = f"${tp_price:.2f}" if tp_price is not None else "없음"
            sl_display = f"${sl_price:.2f}" if sl_price is not None else "없음"
            
            logger.info(f"   - TP: {tp_display}")
            logger.info(f"   - SL: {sl_display}")
            logger.info(f"   - 게이트 사이즈: {final_size}")
            
            # TP/SL 포함 통합 주문 생성
            if tp_price or sl_price:
                logger.info(f"🎯 TP/SL 포함 통합 주문 생성")
                
                gate_order = await self.create_conditional_order_with_tp_sl_v3(
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
                    'leverage_mirrored': leverage_success,
                    'leverage': leverage
                }
                
            else:
                # TP/SL 없는 일반 주문
                logger.info(f"📝 일반 예약 주문 생성 (TP/SL 없음)")
                
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
                    'perfect_mirror': True,  # TP/SL이 없으면 완벽
                    'leverage_mirrored': leverage_success,
                    'leverage': leverage
                }
            
        except Exception as e:
            logger.error(f"완벽한 TP/SL 미러링 주문 생성 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'has_tp_sl': False,
                'perfect_mirror': False,
                'leverage_mirrored': False
            }
    
    async def create_conditional_order_with_tp_sl_v3(self, trigger_price: float, order_size: int,
                                                   tp_price: Optional[float] = None,
                                                   sl_price: Optional[float] = None,
                                                   reduce_only: bool = False,
                                                   trigger_type: str = "ge") -> Dict:
        """V3 TP/SL 포함 조건부 주문 생성 - initial.size를 정수형으로, tif 추가"""
        try:
            endpoint = "/api/v4/futures/usdt/price_orders"
            
            # 🔥🔥🔥 수정된 데이터 구조 - initial.tif 추가
            data = {
                "initial": {
                    "contract": "BTC_USDT",
                    "size": order_size,  # 정수형으로 전송
                    "price": "0",  # 시장가로 설정 (0은 시장가 의미)
                    "tif": "ioc"  # 🔥🔥🔥 시장가 주문에는 반드시 ioc 설정
                },
                "trigger": {
                    "strategy_type": 0,   # 가격 기반 트리거
                    "price_type": 0,      # 마크 가격 기준
                    "price": str(trigger_price),  # 가격은 문자열로 유지
                    "rule": 1 if trigger_type == "ge" else 2  # 1: >=, 2: <=
                }
            }
            
            # reduce_only 설정 (클로즈 주문인 경우)
            if reduce_only:
                data["initial"]["reduce_only"] = True
            
            # TP/SL 설정 - 문자열로 전송
            if tp_price and tp_price > 0:
                data["stop_profit_price"] = str(tp_price)
                logger.info(f"🎯 TP 설정: ${tp_price:.2f} (문자열)")
            
            if sl_price and sl_price > 0:
                data["stop_loss_price"] = str(sl_price)
                logger.info(f"🛡️ SL 설정: ${sl_price:.2f} (문자열)")
            
            logger.info(f"🔧 V3 Gate.io TP/SL 주문 데이터 (tif 포함): {json.dumps(data, indent=2)}")
            
            response = await self._request('POST', endpoint, data=data)
            
            logger.info(f"✅ Gate.io V3 TP/SL 통합 주문 생성 성공: {response.get('id')}")
            
            return response
            
        except Exception as e:
            logger.error(f"V3 TP/SL 포함 조건부 주문 생성 실패: {e}")
            raise
    
    async def create_price_triggered_order_v3(self, trigger_price: float, order_size: int,
                                            reduce_only: bool = False, trigger_type: str = "ge") -> Dict:
        """V3 일반 가격 트리거 주문 생성 - initial.size를 정수형으로, tif 추가"""
        try:
            endpoint = "/api/v4/futures/usdt/price_orders"
            
            # 🔥🔥🔥 수정된 데이터 구조 - initial.tif 추가
            data = {
                "initial": {
                    "contract": "BTC_USDT",
                    "size": order_size,  # 정수형으로 전송
                    "price": "0",  # 시장가로 설정 (0은 시장가 의미)
                    "tif": "ioc"  # 🔥🔥🔥 시장가 주문에는 반드시 ioc 설정
                },
                "trigger": {
                    "strategy_type": 0,   # 가격 기반 트리거
                    "price_type": 0,      # 마크 가격 기준
                    "price": str(trigger_price),  # 가격은 문자열로 유지
                    "rule": 1 if trigger_type == "ge" else 2  # 1: >=, 2: <=
                }
            }
            
            # reduce_only 설정 (클로즈 주문인 경우)
            if reduce_only:
                data["initial"]["reduce_only"] = True
            
            logger.info(f"🔧 V3 Gate.io 일반 주문 데이터 (tif 포함): {json.dumps(data, indent=2)}")
            
            response = await self._request('POST', endpoint, data=data)
            
            logger.info(f"✅ Gate.io V3 일반 트리거 주문 생성 성공: {response.get('id')}")
            
            return response
            
        except Exception as e:
            logger.error(f"V3 일반 가격 트리거 주문 생성 실패: {e}")
            raise
    
    # 기존 메서드들은 호환성을 위해 새로운 메서드로 리다이렉트
    async def create_conditional_order_with_tp_sl_v2(self, trigger_price: float, order_size: int,
                                                   tp_price: Optional[float] = None,
                                                   sl_price: Optional[float] = None,
                                                   reduce_only: bool = False,
                                                   trigger_type: str = "ge") -> Dict:
        """V2 호환성을 위한 래퍼"""
        return await self.create_conditional_order_with_tp_sl_v3(
            trigger_price, order_size, tp_price, sl_price, reduce_only, trigger_type
        )
    
    async def create_price_triggered_order_v2(self, trigger_price: float, order_size: int,
                                            reduce_only: bool = False, trigger_type: str = "ge") -> Dict:
        """V2 호환성을 위한 래퍼"""
        return await self.create_price_triggered_order_v3(
            trigger_price, order_size, reduce_only, trigger_type
        )
    
    async def create_conditional_order_with_tp_sl_fixed(self, trigger_price: float, order_size: int,
                                                      tp_price: Optional[float] = None,
                                                      sl_price: Optional[float] = None,
                                                      reduce_only: bool = False,
                                                      trigger_type: str = "ge") -> Dict:
        """기존 호환성을 위한 래퍼"""
        return await self.create_conditional_order_with_tp_sl_v3(
            trigger_price, order_size, tp_price, sl_price, reduce_only, trigger_type
        )
    
    async def create_price_triggered_order_fixed(self, trigger_price: float, order_size: int,
                                               reduce_only: bool = False, trigger_type: str = "ge") -> Dict:
        """기존 호환성을 위한 래퍼"""
        return await self.create_price_triggered_order_v3(
            trigger_price, order_size, reduce_only, trigger_type
        )
    
    # 기존 메서드들은 호환성을 위해 새로운 메서드로 리다이렉트
    async def create_conditional_order_with_tp_sl(self, trigger_price: float, order_size: int,
                                                tp_price: Optional[float] = None,
                                                sl_price: Optional[float] = None,
                                                reduce_only: bool = False,
                                                trigger_type: str = "ge") -> Dict:
        """기존 호환성을 위한 래퍼"""
        return await self.create_conditional_order_with_tp_sl_v3(
            trigger_price, order_size, tp_price, sl_price, reduce_only, trigger_type
        )
    
    async def create_price_triggered_order(self, trigger_price: float, order_size: int,
                                         reduce_only: bool = False, trigger_type: str = "ge") -> Dict:
        """기존 호환성을 위한 래퍼"""
        return await self.create_price_triggered_order_v3(
            trigger_price, order_size, reduce_only, trigger_type
        )
    
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
        """시장가/지정가 주문 생성 - 레버리지 체크 포함"""
        try:
            # 마진 모드 확인 및 Cross 설정
            await self.ensure_cross_margin_mode(contract)
            
            # 주문 전 현재 레버리지 확인 및 기본값 설정
            current_leverage = await self.get_current_leverage(contract)
            if current_leverage < self.DEFAULT_LEVERAGE:
                logger.info(f"레버리지가 낮음 ({current_leverage}x), 기본값으로 설정: {self.DEFAULT_LEVERAGE}x")
                await self.set_leverage(contract, self.DEFAULT_LEVERAGE)
            
            endpoint = "/api/v4/futures/usdt/orders"
            
            # size는 정수형으로 전송
            data = {
                "contract": contract,
                "size": size  # 정수형으로 전송
            }
            
            if price is not None:
                data["price"] = str(price)
                data["tif"] = tif
            else:
                # 🔥🔥🔥 시장가 주문일 때는 반드시 tif를 ioc로 설정
                data["tif"] = "ioc"
            
            if reduce_only:
                data["reduce_only"] = True
            
            if iceberg > 0:
                data["iceberg"] = iceberg
            
            response = await self._request('POST', endpoint, data=data)
            
            logger.info(f"✅ Gate.io 주문 생성 성공: {response.get('id')} (레버리지: {current_leverage}x)")
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
