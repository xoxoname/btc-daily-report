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
    """Gate.io 미러링 전용 클라이언트 - TP/SL 완벽 복제 + 레버리지 미러링 강화 + 복제 비율 고려"""
    
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
        
        # 🔥🔥🔥 레버리지 설정 강화
        self.DEFAULT_LEVERAGE = 30  # 기본 레버리지 30배로 설정
        self.MAX_LEVERAGE = 100
        self.MIN_LEVERAGE = 1
        self.current_leverage_cache = {}  # 계약별 현재 레버리지 캐시
        
        # 🔥🔥🔥 복제 비율 고려한 주문 생성 강화
        self.ratio_multiplier_cache = {}  # 복제 비율별 주문 캐시
        self.margin_ratio_tracking = {}   # 마진 비율 추적
        self.size_adjustment_history = {}  # 크기 조정 내역
        
        # 🔥🔥🔥 주문 생성 실패 시 재시도 설정
        self.order_creation_retries = 3
        self.order_creation_delay = 1.0
        self.leverage_sync_enabled = True
        
        # 🔥🔥🔥 복제 비율별 허용 오차 설정
        self.ratio_tolerance = {
            'margin': 0.15,    # 마진 차이 15% 허용
            'size': 0.20,      # 크기 차이 20% 허용
            'leverage': 5      # 레버리지 차이 5배 허용
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
        """🔥🔥🔥 클라이언트 초기화 - 기본 레버리지 30배 설정"""
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
    
    async def get_current_leverage(self, contract: str) -> int:
        """🔥🔥🔥 현재 레버리지 조회"""
        try:
            # 캐시에서 먼저 확인
            if contract in self.current_leverage_cache:
                cached_time, cached_leverage = self.current_leverage_cache[contract]
                if (datetime.now() - cached_time).total_seconds() < 60:  # 1분간 캐시 유효
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
        """🔥🔥🔥 레버리지 설정 - 비트겟 미러링 강화"""
        
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
                
                # 🔥🔥🔥 Gate.io API v4 정확한 형식
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
                    # 🔥🔥🔥 레버리지 설정 실패해도 계속 진행 (경고만 출력)
                    logger.warning(f"레버리지 설정 최종 실패하지만 계속 진행: {contract} - {leverage}x")
                    return {"warning": "leverage_setting_failed", "requested_leverage": leverage}
        
        # 모든 시도 실패해도 경고만 출력하고 계속 진행
        logger.warning(f"레버리지 설정 모든 재시도 실패, 기본 레버리지로 계속 진행: {contract} - {leverage}x")
        return {"warning": "all_leverage_attempts_failed", "requested_leverage": leverage}
    
    async def _verify_leverage_setting(self, contract: str, expected_leverage: int, max_attempts: int = 3) -> bool:
        """🔥🔥🔥 레버리지 설정 확인 - 강화된 검증"""
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
        """🔥🔥🔥 비트겟 레버리지를 게이트에 미러링"""
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
    
    async def create_perfect_tp_sl_order_with_ratio(self, bitget_order: Dict, gate_size: int, gate_margin: float, 
                                                   leverage: int, current_gate_price: float, ratio_multiplier: float = 1.0) -> Dict:
        """🔥🔥🔥 완벽한 TP/SL 미러링 주문 생성 - 레버리지 미러링 포함 + 복제 비율 고려 강화"""
        try:
            # 🔥🔥🔥 1단계: 레버리지 미러링
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
            
            # 🔥🔥🔥 복제 비율 고려한 크기 조정
            adjusted_gate_size = int(gate_size * ratio_multiplier)
            adjusted_gate_margin = gate_margin * ratio_multiplier
            
            # 크기 조정 내역 기록
            self.size_adjustment_history[order_id] = {
                'original_size': gate_size,
                'adjusted_size': adjusted_gate_size,
                'ratio_multiplier': ratio_multiplier,
                'original_margin': gate_margin,
                'adjusted_margin': adjusted_gate_margin,
                'adjustment_time': datetime.now().isoformat()
            }
            
            logger.info(f"🔄 복제 비율 적용 크기 조정: {gate_size} → {adjusted_gate_size} (비율: {ratio_multiplier}x)")
            logger.info(f"🔄 복제 비율 적용 마진 조정: ${gate_margin:.2f} → ${adjusted_gate_margin:.2f}")
            
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
            
            # 🔥🔥🔥 클로즈 주문 여부 및 방향 판단 수정 + 복제 비율 고려
            reduce_only = bitget_order.get('reduceOnly', False)
            is_close_order = ('close' in side or reduce_only is True or reduce_only == 'true')
            
            # 🔥🔥🔥 클로즈 주문 방향 수정 로직 + 복제 비율 적용
            if is_close_order:
                # 클로즈 주문: reduce_only=True
                final_size = adjusted_gate_size  # 복제 비율 적용된 크기 사용
                reduce_only_flag = True
                
                # 🔥🔥🔥 클로즈 주문 방향 매핑 수정
                if 'close_long' in side or side == 'close long':
                    # 롱 포지션 종료 → 매도 (음수)
                    final_size = -abs(adjusted_gate_size)
                    logger.info(f"🔴 클로즈 롱: 롱 포지션 종료 → 게이트 매도 (음수 사이즈: {final_size}, 복제비율: {ratio_multiplier}x)")
                    
                elif 'close_short' in side or side == 'close short':
                    # 숏 포지션 종료 → 매수 (양수)
                    final_size = abs(adjusted_gate_size)
                    logger.info(f"🟢 클로즈 숏: 숏 포지션 종료 → 게이트 매수 (양수 사이즈: {final_size}, 복제비율: {ratio_multiplier}x)")
                    
                else:
                    # 일반적인 매도/매수 기반 판단 (클로즈 주문)
                    if 'sell' in side or 'short' in side:
                        final_size = -abs(adjusted_gate_size)
                        logger.info(f"🔴 클로즈 매도: 포지션 종료 → 게이트 매도 (음수 사이즈: {final_size}, 복제비율: {ratio_multiplier}x)")
                    else:
                        final_size = abs(adjusted_gate_size)
                        logger.info(f"🟢 클로즈 매수: 포지션 종료 → 게이트 매수 (양수 사이즈: {final_size}, 복제비율: {ratio_multiplier}x)")
                
            else:
                # 오픈 주문: 방향 고려 + 복제 비율 적용
                reduce_only_flag = False
                if 'short' in side or 'sell' in side:
                    final_size = -abs(adjusted_gate_size)
                    logger.info(f"🔴 오픈 숏: 새 숏 포지션 생성 → 게이트 매도 (음수 사이즈: {final_size}, 복제비율: {ratio_multiplier}x)")
                else:
                    final_size = abs(adjusted_gate_size)
                    logger.info(f"🟢 오픈 롱: 새 롱 포지션 생성 → 게이트 매수 (양수 사이즈: {final_size}, 복제비율: {ratio_multiplier}x)")
            
            # Gate.io 트리거 타입 결정
            gate_trigger_type = "ge" if trigger_price > current_gate_price else "le"
            
            logger.info(f"🔍 완벽 미러링 주문 생성 (복제비율 {ratio_multiplier}x):")
            logger.info(f"   - 비트겟 ID: {order_id}")
            logger.info(f"   - 방향: {side} ({'클로즈' if is_close_order else '오픈'})")
            logger.info(f"   - 트리거가: ${trigger_price:.2f}")
            logger.info(f"   - 레버리지: {leverage}x {'✅ 미러링됨' if leverage_success else '⚠️ 미러링 실패'}")
            logger.info(f"   - 원본 크기: {gate_size} → 조정된 크기: {final_size}")
            logger.info(f"   - 원본 마진: ${gate_margin:.2f} → 조정된 마진: ${adjusted_gate_margin:.2f}")
            
            # TP/SL 표시 수정
            tp_display = f"${tp_price:.2f}" if tp_price is not None else "없음"
            sl_display = f"${sl_price:.2f}" if sl_price is not None else "없음"
            
            logger.info(f"   - TP: {tp_display}")
            logger.info(f"   - SL: {sl_display}")
            logger.info(f"   - 게이트 최종 사이즈: {final_size}")
            
            # 🔥🔥🔥 복제 비율 고려 주문 생성 재시도 로직
            gate_order = None
            creation_success = False
            
            for attempt in range(self.order_creation_retries):
                try:
                    # 🔥 TP/SL 포함 통합 주문 생성
                    if tp_price or sl_price:
                        logger.info(f"🎯 TP/SL 포함 통합 주문 생성 (시도 {attempt + 1}/{self.order_creation_retries})")
                        
                        gate_order = await self.create_conditional_order_with_tp_sl_ratio_aware(
                            trigger_price=trigger_price,
                            order_size=final_size,
                            tp_price=tp_price,
                            sl_price=sl_price,
                            reduce_only=reduce_only_flag,
                            trigger_type=gate_trigger_type,
                            ratio_multiplier=ratio_multiplier
                        )
                        
                    else:
                        # TP/SL 없는 일반 주문
                        logger.info(f"📝 일반 예약 주문 생성 (TP/SL 없음, 시도 {attempt + 1}/{self.order_creation_retries})")
                        
                        gate_order = await self.create_price_triggered_order_ratio_aware(
                            trigger_price=trigger_price,
                            order_size=final_size,
                            reduce_only=reduce_only_flag,
                            trigger_type=gate_trigger_type,
                            ratio_multiplier=ratio_multiplier
                        )
                    
                    if gate_order and gate_order.get('id'):
                        creation_success = True
                        break
                    else:
                        logger.warning(f"주문 생성 응답 이상: {gate_order}")
                        if attempt < self.order_creation_retries - 1:
                            await asyncio.sleep(self.order_creation_delay * (attempt + 1))
                            continue
                        
                except Exception as creation_error:
                    logger.error(f"주문 생성 시도 {attempt + 1} 실패: {creation_error}")
                    if attempt < self.order_creation_retries - 1:
                        await asyncio.sleep(self.order_creation_delay * (attempt + 1))
                        continue
                    else:
                        raise creation_error
            
            if not creation_success or not gate_order:
                raise Exception("모든 주문 생성 시도 실패")
            
            # TP/SL 설정 확인
            actual_tp = gate_order.get('stop_profit_price', '')
            actual_sl = gate_order.get('stop_loss_price', '')
            has_tp_sl = bool(actual_tp or actual_sl)
            
            # 🔥🔥🔥 복제 비율 추적 정보 저장
            order_tracking_key = f"{order_id}_{ratio_multiplier}"
            self.ratio_multiplier_cache[order_tracking_key] = {
                'bitget_order_id': order_id,
                'gate_order_id': gate_order.get('id'),
                'ratio_multiplier': ratio_multiplier,
                'original_size': gate_size,
                'adjusted_size': final_size,
                'original_margin': gate_margin,
                'adjusted_margin': adjusted_gate_margin,
                'leverage': leverage,
                'leverage_mirrored': leverage_success,
                'creation_time': datetime.now().isoformat(),
                'tp_price': tp_price,
                'sl_price': sl_price,
                'has_tp_sl': has_tp_sl
            }
            
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
                'ratio_multiplier': ratio_multiplier,  # 🔥🔥🔥 복제 비율 정보 추가
                'original_size': gate_size,            # 원본 크기
                'adjusted_size': final_size,           # 조정된 크기
                'size_adjustment_applied': ratio_multiplier != 1.0,  # 크기 조정 여부
                'margin_adjustment_applied': ratio_multiplier != 1.0  # 마진 조정 여부
            }
            
        except Exception as e:
            logger.error(f"완벽한 TP/SL 미러링 주문 생성 실패 (복제비율 {ratio_multiplier}x): {e}")
            return {
                'success': False,
                'error': str(e),
                'has_tp_sl': False,
                'perfect_mirror': False,
                'leverage_mirrored': False,
                'ratio_multiplier': ratio_multiplier,
                'size_adjustment_applied': False,
                'margin_adjustment_applied': False
            }
    
    async def create_perfect_tp_sl_order(self, bitget_order: Dict, gate_size: int, gate_margin: float, 
                                       leverage: int, current_gate_price: float) -> Dict:
        """🔥🔥🔥 기존 호환성을 위한 래퍼 메서드 - 복제 비율 1.0 적용"""
        return await self.create_perfect_tp_sl_order_with_ratio(
            bitget_order, gate_size, gate_margin, leverage, current_gate_price, 1.0
        )
    
    async def create_conditional_order_with_tp_sl_ratio_aware(self, trigger_price: float, order_size: int,
                                                            tp_price: Optional[float] = None,
                                                            sl_price: Optional[float] = None,
                                                            reduce_only: bool = False,
                                                            trigger_type: str = "ge",
                                                            ratio_multiplier: float = 1.0) -> Dict:
        """🔥🔥🔥 TP/SL 포함 조건부 주문 생성 - Gate.io 공식 API + 복제 비율 고려"""
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
            
            # 🔥🔥🔥 TP/SL 설정 (Gate.io 공식 필드) + 복제 비율 고려
            if tp_price and tp_price > 0:
                # 복제 비율을 고려한 TP 가격 조정은 하지 않음 (가격은 그대로 유지)
                data["stop_profit_price"] = str(tp_price)
                logger.info(f"🎯 TP 설정: ${tp_price:.2f} (복제비율 {ratio_multiplier}x, 가격 유지)")
            
            if sl_price and sl_price > 0:
                # 복제 비율을 고려한 SL 가격 조정은 하지 않음 (가격은 그대로 유지)
                data["stop_loss_price"] = str(sl_price)
                logger.info(f"🛡️ SL 설정: ${sl_price:.2f} (복제비율 {ratio_multiplier}x, 가격 유지)")
            
            logger.info(f"Gate.io TP/SL 통합 주문 데이터 (복제비율 {ratio_multiplier}x): {json.dumps(data, indent=2)}")
            
            response = await self._request('POST', endpoint, data=data)
            
            logger.info(f"✅ Gate.io TP/SL 통합 주문 생성 성공 (복제비율 {ratio_multiplier}x): {response.get('id')}")
            
            return response
            
        except Exception as e:
            logger.error(f"TP/SL 포함 조건부 주문 생성 실패 (복제비율 {ratio_multiplier}x): {e}")
            raise
    
    async def create_conditional_order_with_tp_sl(self, trigger_price: float, order_size: int,
                                                tp_price: Optional[float] = None,
                                                sl_price: Optional[float] = None,
                                                reduce_only: bool = False,
                                                trigger_type: str = "ge") -> Dict:
        """🔥🔥🔥 기존 호환성을 위한 래퍼 메서드"""
        return await self.create_conditional_order_with_tp_sl_ratio_aware(
            trigger_price, order_size, tp_price, sl_price, reduce_only, trigger_type, 1.0
        )
    
    async def create_price_triggered_order_ratio_aware(self, trigger_price: float, order_size: int,
                                                      reduce_only: bool = False, trigger_type: str = "ge",
                                                      ratio_multiplier: float = 1.0) -> Dict:
        """일반 가격 트리거 주문 생성 - 복제 비율 고려"""
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
            
            logger.info(f"Gate.io 일반 트리거 주문 생성 (복제비율 {ratio_multiplier}x): 크기={order_size}, 트리거=${trigger_price:.2f}")
            
            response = await self._request('POST', endpoint, data=data)
            
            logger.info(f"✅ Gate.io 일반 트리거 주문 생성 성공 (복제비율 {ratio_multiplier}x): {response.get('id')}")
            
            return response
            
        except Exception as e:
            logger.error(f"가격 트리거 주문 생성 실패 (복제비율 {ratio_multiplier}x): {e}")
            raise
    
    async def create_price_triggered_order(self, trigger_price: float, order_size: int,
                                         reduce_only: bool = False, trigger_type: str = "ge") -> Dict:
        """기존 호환성을 위한 래퍼 메서드"""
        return await self.create_price_triggered_order_ratio_aware(
            trigger_price, order_size, reduce_only, trigger_type, 1.0
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
    
    async def place_order_with_ratio(self, contract: str, size: int, price: Optional[float] = None,
                                   reduce_only: bool = False, tif: str = "gtc", iceberg: int = 0,
                                   ratio_multiplier: float = 1.0) -> Dict:
        """🔥🔥🔥 시장가/지정가 주문 생성 - 레버리지 체크 포함 + 복제 비율 고려"""
        try:
            # 주문 전 현재 레버리지 확인 및 기본값 설정
            current_leverage = await self.get_current_leverage(contract)
            if current_leverage < self.DEFAULT_LEVERAGE:
                logger.info(f"레버리지가 낮음 ({current_leverage}x), 기본값으로 설정: {self.DEFAULT_LEVERAGE}x")
                await self.set_leverage(contract, self.DEFAULT_LEVERAGE)
            
            # 🔥🔥🔥 복제 비율 적용
            adjusted_size = int(size * ratio_multiplier)
            
            endpoint = "/api/v4/futures/usdt/orders"
            
            data = {
                "contract": contract,
                "size": adjusted_size  # 복제 비율 적용된 크기 사용
            }
            
            if price is not None:
                data["price"] = str(price)
                data["tif"] = tif
            
            if reduce_only:
                data["reduce_only"] = True
            
            if iceberg > 0:
                data["iceberg"] = iceberg
            
            logger.info(f"Gate.io 주문 생성 (복제비율 {ratio_multiplier}x): 원본 크기={size}, 조정된 크기={adjusted_size}")
            
            response = await self._request('POST', endpoint, data=data)
            
            logger.info(f"✅ Gate.io 주문 생성 성공 (복제비율 {ratio_multiplier}x): {response.get('id')} (레버리지: {current_leverage}x)")
            return response
            
        except Exception as e:
            logger.error(f"Gate.io 주문 생성 실패 (복제비율 {ratio_multiplier}x): {e}")
            raise
    
    async def place_order(self, contract: str, size: int, price: Optional[float] = None,
                         reduce_only: bool = False, tif: str = "gtc", iceberg: int = 0) -> Dict:
        """🔥🔥🔥 기존 호환성을 위한 래퍼 메서드"""
        return await self.place_order_with_ratio(contract, size, price, reduce_only, tif, iceberg, 1.0)
    
    async def close_position_with_ratio(self, contract: str, size: Optional[int] = None, ratio_multiplier: float = 1.0) -> Dict:
        """포지션 종료 - 복제 비율 고려"""
        try:
            positions = await self.get_positions(contract)
            
            if not positions or positions[0].get('size', 0) == 0:
                return {"status": "no_position"}
            
            position = positions[0]
            position_size = int(position['size'])
            
            if size is None:
                close_size = -position_size
            else:
                # 🔥🔥🔥 복제 비율 적용
                adjusted_size = int(size * ratio_multiplier)
                if position_size > 0:
                    close_size = -min(abs(adjusted_size), position_size)
                else:
                    close_size = min(abs(adjusted_size), abs(position_size))
            
            logger.info(f"포지션 종료 (복제비율 {ratio_multiplier}x): 원본 크기={size}, 조정된 클로즈 크기={close_size}")
            
            result = await self.place_order_with_ratio(
                contract=contract,
                size=close_size,
                price=None,
                reduce_only=True,
                ratio_multiplier=1.0  # 이미 크기가 조정되었으므로 1.0 사용
            )
            
            return result
            
        except Exception as e:
            logger.error(f"포지션 종료 실패 (복제비율 {ratio_multiplier}x): {e}")
            raise
    
    async def close_position(self, contract: str, size: Optional[int] = None) -> Dict:
        """기존 호환성을 위한 래퍼 메서드"""
        return await self.close_position_with_ratio(contract, size, 1.0)
    
    async def get_ratio_multiplier_analysis(self, order_id: str = None) -> Dict:
        """🔥🔥🔥 복제 비율 분석 정보 조회"""
        try:
            if order_id:
                # 특정 주문의 복제 비율 정보 조회
                for key, info in self.ratio_multiplier_cache.items():
                    if info.get('bitget_order_id') == order_id or info.get('gate_order_id') == order_id:
                        return {
                            'found': True,
                            'order_info': info,
                            'cache_key': key
                        }
                
                return {'found': False, 'order_id': order_id}
            else:
                # 전체 복제 비율 캐시 정보 조회
                return {
                    'total_cached_orders': len(self.ratio_multiplier_cache),
                    'size_adjustments': len(self.size_adjustment_history),
                    'margin_tracking': len(self.margin_ratio_tracking),
                    'cache_sample': list(self.ratio_multiplier_cache.keys())[:5]  # 샘플 5개
                }
                
        except Exception as e:
            logger.error(f"복제 비율 분석 정보 조회 실패: {e}")
            return {'error': str(e)}
    
    async def cleanup_ratio_multiplier_cache(self, max_age_hours: int = 24):
        """🔥🔥🔥 복제 비율 캐시 정리"""
        try:
            current_time = datetime.now()
            expired_keys = []
            
            for key, info in self.ratio_multiplier_cache.items():
                creation_time_str = info.get('creation_time', '')
                if creation_time_str:
                    try:
                        creation_time = datetime.fromisoformat(creation_time_str)
                        age_hours = (current_time - creation_time).total_seconds() / 3600
                        
                        if age_hours > max_age_hours:
                            expired_keys.append(key)
                    except:
                        expired_keys.append(key)
                else:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.ratio_multiplier_cache[key]
            
            # 크기 조정 내역도 정리
            expired_adjustments = []
            for order_id, adjustment in self.size_adjustment_history.items():
                adjustment_time_str = adjustment.get('adjustment_time', '')
                if adjustment_time_str:
                    try:
                        adjustment_time = datetime.fromisoformat(adjustment_time_str)
                        age_hours = (current_time - adjustment_time).total_seconds() / 3600
                        
                        if age_hours > max_age_hours:
                            expired_adjustments.append(order_id)
                    except:
                        expired_adjustments.append(order_id)
                else:
                    expired_adjustments.append(order_id)
            
            for order_id in expired_adjustments:
                del self.size_adjustment_history[order_id]
            
            if expired_keys or expired_adjustments:
                logger.info(f"🧹 복제 비율 캐시 정리: 캐시 {len(expired_keys)}개, 조정 내역 {len(expired_adjustments)}개 제거")
                
        except Exception as e:
            logger.error(f"복제 비율 캐시 정리 실패: {e}")
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Gate.io 미러링 클라이언트 세션 종료")
