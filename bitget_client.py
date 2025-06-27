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
        
        # API 연결 상태 추적
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
        self.max_consecutive_failures = 10
        
        # 백업 엔드포인트들
        self.ticker_endpoints = [
            "/api/v2/mix/market/ticker",
            "/api/mix/v1/market/ticker",
            "/api/v2/spot/market/tickers",
        ]
        
        # API 키 검증 상태
        self.api_keys_validated = False
        
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
            logger.info("Bitget 클라이언트 세션 초기화 완료")
        
    async def initialize(self):
        """클라이언트 초기화"""
        self._initialize_session()
        
        # API 키 유효성 검증
        await self._validate_api_keys()
        
        logger.info("Bitget 클라이언트 초기화 완료")
    
    async def _validate_api_keys(self):
        """API 키 유효성 검증"""
        try:
            logger.info("비트겟 API 키 유효성 검증 시작...")
            
            # 간단한 계정 정보 조회로 API 키 검증
            endpoint = "/api/v2/mix/account/accounts"
            params = {
                'productType': 'USDT-FUTURES',
                'marginCoin': 'USDT'
            }
            
            response = await self._request('GET', endpoint, params=params)
            
            if response is not None:
                self.api_keys_validated = True
                self.api_connection_healthy = True
                self.consecutive_failures = 0
                logger.info("✅ 비트겟 API 키 검증 성공")
            else:
                logger.error("❌ 비트겟 API 키 검증 실패: 응답 없음")
                self.api_keys_validated = False
                
        except Exception as e:
            logger.error(f"❌ 비트겟 API 키 검증 실패: {e}")
            self.api_keys_validated = False
    
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
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None, max_retries: int = 3) -> Dict:
        """API 요청 - 강화된 오류 처리"""
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
        
        # 재시도 로직
        for attempt in range(max_retries):
            try:
                logger.debug(f"비트겟 API 요청 (시도 {attempt + 1}/{max_retries}): {method} {endpoint}")
                
                async with self.session.request(method, url, headers=headers, data=body) as response:
                    response_text = await response.text()
                    
                    logger.debug(f"비트겟 API 응답 상태: {response.status}")
                    logger.debug(f"비트겟 API 응답 내용: {response_text[:500]}...")
                    
                    # 빈 응답 체크
                    if not response_text.strip():
                        error_msg = f"빈 응답 받음 (상태: {response.status})"
                        logger.warning(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    # HTTP 상태 코드 체크
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: {response_text}"
                        logger.error(f"비트겟 API HTTP 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    # JSON 파싱
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError as json_error:
                        error_msg = f"JSON 파싱 실패: {json_error}, 응답: {response_text[:200]}"
                        logger.error(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    # API 응답 코드 체크
                    if response_data.get('code') != '00000':
                        error_msg = f"API 응답 오류: {response_data}"
                        logger.error(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            self._record_failure(error_msg)
                            raise Exception(error_msg)
                    
                    # 성공 기록
                    self._record_success()
                    return response_data.get('data', {})
                    
            except asyncio.TimeoutError:
                error_msg = f"요청 타임아웃 (시도 {attempt + 1})"
                logger.warning(error_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self._record_failure(error_msg)
                    raise Exception(error_msg)
                    
            except aiohttp.ClientError as client_error:
                error_msg = f"클라이언트 오류 (시도 {attempt + 1}): {client_error}"
                logger.warning(error_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self._record_failure(error_msg)
                    raise Exception(error_msg)
                    
            except Exception as e:
                error_msg = f"예상치 못한 오류 (시도 {attempt + 1}): {e}"
                logger.error(error_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self._record_failure(error_msg)
                    raise
        
        # 모든 재시도 실패
        final_error = f"모든 재시도 실패: {max_retries}회 시도"
        self._record_failure(final_error)
        raise Exception(final_error)
    
    def _record_success(self):
        """성공 기록"""
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
    
    def _record_failure(self, error_msg: str):
        """실패 기록"""
        self.consecutive_failures += 1
        
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.api_connection_healthy = False
            logger.error(f"비트겟 API 연결 비정상 상태: 연속 {self.consecutive_failures}회 실패")
        
        logger.warning(f"비트겟 API 실패 기록: {error_msg} (연속 실패: {self.consecutive_failures}회)")
    
    async def get_ticker(self, symbol: str = None) -> Dict:
        """현재가 정보 조회 - 다중 엔드포인트 지원"""
        symbol = symbol or self.config.symbol
        
        # 여러 엔드포인트 순차 시도
        for i, endpoint in enumerate(self.ticker_endpoints):
            try:
                logger.debug(f"티커 조회 시도 {i + 1}/{len(self.ticker_endpoints)}: {endpoint}")
                
                if endpoint == "/api/v2/mix/market/ticker":
                    # V2 믹스 마켓 (기본)
                    params = {
                        'symbol': symbol,
                        'productType': 'USDT-FUTURES'
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                    if isinstance(response, list) and len(response) > 0:
                        ticker_data = response[0]
                    elif isinstance(response, dict):
                        ticker_data = response
                    else:
                        logger.warning(f"V2 믹스: 예상치 못한 응답 형식: {type(response)}")
                        continue
                    
                elif endpoint == "/api/mix/v1/market/ticker":
                    # V1 믹스 마켓 (백업)
                    v1_symbol = f"{symbol}_UMCBL"
                    params = {
                        'symbol': v1_symbol
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                    if isinstance(response, dict):
                        ticker_data = response
                    else:
                        logger.warning(f"V1 믹스: 예상치 못한 응답 형식: {type(response)}")
                        continue
                        
                elif endpoint == "/api/v2/spot/market/tickers":
                    # 스팟 마켓 (최후 백업)
                    spot_symbol = symbol.replace('USDT', '-USDT')
                    params = {
                        'symbol': spot_symbol
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                    if isinstance(response, list) and len(response) > 0:
                        ticker_data = response[0]
                    elif isinstance(response, dict):
                        ticker_data = response
                    else:
                        logger.warning(f"V2 스팟: 예상치 못한 응답 형식: {type(response)}")
                        continue
                
                # 응답 데이터 검증 및 정규화
                if ticker_data and self._validate_ticker_data(ticker_data):
                    normalized_ticker = self._normalize_ticker_data(ticker_data, endpoint)
                    logger.info(f"✅ 티커 조회 성공 ({endpoint}): ${normalized_ticker.get('last', 'N/A')}")
                    return normalized_ticker
                else:
                    logger.warning(f"티커 데이터 검증 실패: {endpoint}")
                    continue
                    
            except Exception as e:
                logger.warning(f"티커 엔드포인트 {endpoint} 실패: {e}")
                continue
        
        # 모든 엔드포인트 실패
        error_msg = f"모든 티커 엔드포인트 실패: {', '.join(self.ticker_endpoints)}"
        logger.error(error_msg)
        self._record_failure("모든 티커 엔드포인트 실패")
        return {}
    
    def _validate_ticker_data(self, ticker_data: Dict) -> bool:
        """티커 데이터 유효성 검증"""
        try:
            if not isinstance(ticker_data, dict):
                return False
            
            # 필수 가격 필드 중 하나라도 있어야 함
            price_fields = ['last', 'lastPr', 'close', 'price', 'mark_price', 'markPrice']
            
            for field in price_fields:
                value = ticker_data.get(field)
                if value is not None:
                    try:
                        price = float(value)
                        if price > 0:
                            return True
                    except:
                        continue
            
            logger.warning(f"유효한 가격 필드 없음: {list(ticker_data.keys())}")
            return False
            
        except Exception as e:
            logger.error(f"티커 데이터 검증 오류: {e}")
            return False
    
    def _normalize_ticker_data(self, ticker_data: Dict, endpoint: str) -> Dict:
        """티커 데이터 정규화"""
        try:
            normalized = {}
            
            # 가격 필드 정규화
            price_mappings = [
                ('last', ['last', 'lastPr', 'close', 'price']),
                ('high', ['high', 'high24h', 'highPrice']),
                ('low', ['low', 'low24h', 'lowPrice']),
                ('volume', ['volume', 'vol', 'baseVolume', 'baseVol']),
                ('changeUtc', ['changeUtc', 'change', 'priceChange', 'priceChangePercent'])
            ]
            
            for target_field, source_fields in price_mappings:
                for source_field in source_fields:
                    value = ticker_data.get(source_field)
                    if value is not None:
                        try:
                            if target_field == 'changeUtc':
                                # 변화율을 소수로 변환 (예: 2.5% -> 0.025)
                                change_val = float(value)
                                if abs(change_val) > 1:  # 백분율 형태인 경우
                                    change_val = change_val / 100
                                normalized[target_field] = change_val
                            else:
                                normalized[target_field] = float(value)
                            break
                        except:
                            continue
            
            # 기본값 설정
            if 'last' not in normalized:
                normalized['last'] = 0
            if 'changeUtc' not in normalized:
                normalized['changeUtc'] = 0
            if 'volume' not in normalized:
                normalized['volume'] = 0
            
            # 원본 데이터도 포함
            normalized['_original'] = ticker_data
            normalized['_endpoint'] = endpoint
            
            return normalized
            
        except Exception as e:
            logger.error(f"티커 데이터 정규화 실패: {e}")
            return ticker_data
    
    async def get_funding_rate(self, symbol: str = None) -> Dict:
        """펀딩비 조회 - 수정된 엔드포인트 사용"""
        symbol = symbol or self.config.symbol
        
        # 수정된 펀딩비 엔드포인트들 (404 오류 수정)
        funding_endpoints = [
            "/api/v2/mix/market/funding-time",
            "/api/mix/v1/market/current-fundRate",
            "/api/v2/mix/market/symbol-info"
        ]
        
        for i, endpoint in enumerate(funding_endpoints):
            try:
                logger.debug(f"펀딩비 조회 시도 {i + 1}/{len(funding_endpoints)}: {endpoint}")
                
                if endpoint == "/api/v2/mix/market/funding-time":
                    # V2 펀딩 시간 엔드포인트 (가장 안정적)
                    params = {
                        'symbol': symbol,
                        'productType': 'USDT-FUTURES'
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                    if isinstance(response, list) and len(response) > 0:
                        funding_data = response[0]
                    elif isinstance(response, dict):
                        funding_data = response
                    else:
                        logger.warning(f"V2 펀딩 시간: 예상치 못한 응답 형식: {type(response)}")
                        continue
                    
                elif endpoint == "/api/mix/v1/market/current-fundRate":
                    # V1 엔드포인트
                    v1_symbol = f"{symbol}_UMCBL"
                    params = {
                        'symbol': v1_symbol
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                    if isinstance(response, dict):
                        funding_data = response
                    else:
                        logger.warning(f"V1 펀딩비: 예상치 못한 응답 형식: {type(response)}")
                        continue
                
                elif endpoint == "/api/v2/mix/market/symbol-info":
                    # 심볼 정보에서 펀딩비 추출
                    params = {
                        'symbol': symbol,
                        'productType': 'USDT-FUTURES'
                    }
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                    if isinstance(response, list) and len(response) > 0:
                        funding_data = response[0]
                    elif isinstance(response, dict):
                        funding_data = response
                    else:
                        logger.warning(f"심볼 정보: 예상치 못한 응답 형식: {type(response)}")
                        continue
                
                # 펀딩비 데이터 검증 및 정규화
                if funding_data and self._validate_funding_data(funding_data):
                    normalized_funding = self._normalize_funding_data(funding_data, endpoint)
                    logger.info(f"✅ 펀딩비 조회 성공 ({endpoint}): {normalized_funding.get('fundingRate', 'N/A')}")
                    return normalized_funding
                else:
                    logger.warning(f"펀딩비 데이터 검증 실패: {endpoint}")
                    continue
                    
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg or "NOT FOUND" in error_msg:
                    logger.debug(f"펀딩비 엔드포인트 {endpoint} 404 오류 (예상됨), 다음 시도")
                else:
                    logger.warning(f"펀딩비 엔드포인트 {endpoint} 실패: {e}")
                continue
        
        # 모든 엔드포인트 실패 - 기본값 반환
        logger.info("모든 펀딩비 엔드포인트 실패, 기본값 반환")
        return {
            'fundingRate': 0.0,
            'fundingTime': '',
            '_source': 'default_fallback',
            '_error': 'all_endpoints_failed'
        }
    
    def _validate_funding_data(self, funding_data: Dict) -> bool:
        """펀딩비 데이터 유효성 검증"""
        try:
            if not isinstance(funding_data, dict):
                return False
            
            # 펀딩비 필드 확인
            funding_fields = ['fundingRate', 'fundRate', 'rate', 'currentFundingRate', 'fundingFeeRate']
            
            for field in funding_fields:
                value = funding_data.get(field)
                if value is not None:
                    try:
                        rate = float(value)
                        # 펀딩비는 보통 -1 ~ 1 범위
                        if -1 <= rate <= 1:
                            return True
                    except:
                        continue
            
            # 심볼 정보에서 펀딩비를 찾을 수 없어도 유효한 응답으로 처리
            logger.debug(f"펀딩비 필드 없음, 하지만 유효한 응답으로 처리: {list(funding_data.keys())}")
            return True
            
        except Exception as e:
            logger.error(f"펀딩비 데이터 검증 오류: {e}")
            return False
    
    def _normalize_funding_data(self, funding_data: Dict, endpoint: str) -> Dict:
        """펀딩비 데이터 정규화"""
        try:
            normalized = {}
            
            # 펀딩비 필드 정규화
            funding_fields = ['fundingRate', 'fundRate', 'rate', 'currentFundingRate', 'fundingFeeRate']
            
            for field in funding_fields:
                value = funding_data.get(field)
                if value is not None:
                    try:
                        normalized['fundingRate'] = float(value)
                        break
                    except:
                        continue
            
            # 기본값 설정
            if 'fundingRate' not in normalized:
                normalized['fundingRate'] = 0.0
            
            # 추가 필드들
            time_fields = ['fundingTime', 'nextFundingTime', 'fundTime', 'fundingInterval']
            for field in time_fields:
                value = funding_data.get(field)
                if value is not None:
                    normalized[field] = value
                    break
            
            # 원본 데이터도 포함
            normalized['_original'] = funding_data
            normalized['_endpoint'] = endpoint
            
            return normalized
            
        except Exception as e:
            logger.error(f"펀딩비 데이터 정규화 실패: {e}")
            return {
                'fundingRate': 0.0,
                'fundingTime': '',
                '_error': str(e),
                '_endpoint': endpoint
            }
    
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
    
    async def get_account_info(self) -> Dict:
        """🔥🔥 계정 정보 조회 (V2 API) - 사용 증거금 계산 개선"""
        endpoint = "/api/v2/mix/account/accounts"
        params = {
            'productType': 'USDT-FUTURES',
            'marginCoin': 'USDT'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            logger.info(f"계정 정보 원본 응답: {response}")
            
            if isinstance(response, list) and len(response) > 0:
                account_data = response[0]
            elif isinstance(response, dict):
                account_data = response
            else:
                logger.warning("계정 정보 응답 형식이 예상과 다름")
                return {}
            
            # 🔥🔥 사용 증거금 계산 개선
            used_margin = 0.0
            total_equity = float(account_data.get('accountEquity', 0))
            available = float(account_data.get('available', 0))
            
            # 1순위: API에서 직접 제공하는 usedMargin 필드
            if 'usedMargin' in account_data and account_data['usedMargin']:
                try:
                    used_margin = float(account_data['usedMargin'])
                    if used_margin > 0:
                        logger.info(f"✅ 사용 증거금 (API 직접): ${used_margin:.2f}")
                    else:
                        # 2순위: 총자산 - 가용자산으로 계산
                        if total_equity > available:
                            used_margin = total_equity - available
                            logger.info(f"✅ 사용 증거금 (총자산-가용): ${used_margin:.2f}")
                except (ValueError, TypeError):
                    logger.warning("usedMargin 필드 변환 실패")
            else:
                # 2순위: 총자산 - 가용자산으로 계산
                if total_equity > available:
                    used_margin = total_equity - available
                    logger.info(f"✅ 사용 증거금 (계산): 총자산=${total_equity:.2f} - 가용=${available:.2f} = ${used_margin:.2f}")
                else:
                    logger.info("포지션이 없거나 사용 증거금 없음")
            
            # 🔥🔥 포지션 정보와 교차 검증
            try:
                positions = await self.get_positions()
                if positions:
                    position_margin_sum = 0
                    for pos in positions:
                        # 포지션별 증거금 계산
                        size = float(pos.get('total', 0))
                        if size > 0:
                            mark_price = float(pos.get('markPrice', 0))
                            leverage = float(pos.get('leverage', 30))
                            if mark_price > 0 and leverage > 0:
                                pos_value = size * mark_price
                                pos_margin = pos_value / leverage
                                position_margin_sum += pos_margin
                                logger.info(f"포지션 증거금 계산: 사이즈={size}, 가격=${mark_price:.2f}, 레버리지={leverage}x, 증거금=${pos_margin:.2f}")
                    
                    # 계산된 포지션 증거금과 비교
                    if position_margin_sum > 0:
                        margin_diff = abs(used_margin - position_margin_sum)
                        if margin_diff > 10:  # $10 이상 차이나면 경고
                            logger.warning(f"⚠️ 증거금 불일치: API={used_margin:.2f}, 계산={position_margin_sum:.2f}, 차이=${margin_diff:.2f}")
                        
                        # 계산된 값이 더 정확할 수 있으므로 사용
                        if used_margin == 0 and position_margin_sum > 0:
                            used_margin = position_margin_sum
                            logger.info(f"✅ 포지션 기반 증거금 사용: ${used_margin:.2f}")
                            
            except Exception as e:
                logger.debug(f"포지션 기반 증거금 검증 실패: {e}")
            
            # 최종 결과
            result = {
                'total_equity': total_equity,
                'available': available,
                'used_margin': used_margin,  # 🔥🔥 개선된 증거금 계산
                'unrealized_pnl': float(account_data.get('unrealizedPL', 0)),
                'margin_balance': float(account_data.get('marginBalance', 0)),
                'wallet_balance': float(account_data.get('walletBalance', 0)),
                '_original': account_data
            }
            
            logger.info(f"✅ 최종 계정 정보:")
            logger.info(f"  - 총 자산: ${total_equity:.2f}")
            logger.info(f"  - 가용 자산: ${available:.2f}")
            logger.info(f"  - 사용 증거금: ${used_margin:.2f}")
            logger.info(f"  - 미실현 손익: ${result['unrealized_pnl']:.4f}")
            
            return result
            
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            raise
    
    async def get_trade_fills(self, symbol: str = None, start_time: int = None, end_time: int = None, limit: int = 100) -> List[Dict]:
        """🔥🔥 거래 내역 조회 - 개선된 V2 API 사용"""
        symbol = symbol or self.config.symbol
        
        # 개선된 거래 내역 조회 엔드포인트들
        fill_endpoints = [
            "/api/v2/mix/order/fill-history",    # V2 거래 내역 (권장)
            "/api/v2/mix/order/fills",           # V2 거래 내역 (대안)
            "/api/mix/v1/order/fills"            # V1 거래 내역 (폴백)
        ]
        
        for endpoint in fill_endpoints:
            try:
                logger.debug(f"거래 내역 조회 시도: {endpoint}")
                
                if endpoint.startswith("/api/v2/"):
                    # V2 API 파라미터
                    params = {
                        'symbol': symbol,
                        'productType': 'USDT-FUTURES'
                    }
                    
                    if start_time:
                        params['startTime'] = str(start_time)
                    if end_time:
                        params['endTime'] = str(end_time)
                    if limit:
                        params['limit'] = str(min(limit, 500))
                    
                else:
                    # V1 API 파라미터
                    v1_symbol = f"{symbol}_UMCBL"
                    params = {
                        'symbol': v1_symbol,
                        'productType': 'umcbl'
                    }
                    
                    if start_time:
                        params['startTime'] = str(start_time)
                    if end_time:
                        params['endTime'] = str(end_time)
                    if limit:
                        params['pageSize'] = str(min(limit, 500))
                
                response = await self._request('GET', endpoint, params=params, max_retries=2)
                
                # 응답 처리
                fills = []
                if isinstance(response, dict):
                    # V2 API는 다양한 필드명 사용
                    for field in ['fillList', 'list', 'data', 'fills']:
                        if field in response and isinstance(response[field], list):
                            fills = response[field]
                            break
                elif isinstance(response, list):
                    fills = response
                
                if fills:
                    logger.info(f"✅ 거래 내역 조회 성공 ({endpoint}): {len(fills)}건")
                    return fills
                else:
                    logger.debug(f"거래 내역 없음: {endpoint}")
                    continue
                    
            except Exception as e:
                logger.debug(f"거래 내역 엔드포인트 {endpoint} 실패: {e}")
                continue
        
        # 모든 엔드포인트 실패
        logger.warning("모든 거래 내역 엔드포인트 실패")
        return []
    
    async def get_position_pnl_based_profit(self, start_time: int, end_time: int, symbol: str = None) -> Dict:
        """🔥🔥 Position PnL 기준 정확한 손익 계산 - 수수료 분리"""
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"🔍 Position PnL 기준 정확한 손익 계산 시작...")
            logger.info(f"  - 심볼: {symbol}")
            logger.info(f"  - 시작: {datetime.fromtimestamp(start_time/1000)}")
            logger.info(f"  - 종료: {datetime.fromtimestamp(end_time/1000)}")
            
            # 거래 내역 조회
            fills = await self.get_trade_fills(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                limit=500
            )
            
            logger.info(f"거래 내역 조회 결과: {len(fills)}건")
            
            if not fills:
                return {
                    'position_pnl': 0.0,
                    'trading_fees': 0.0,
                    'funding_fees': 0.0,
                    'net_profit': 0.0,
                    'trade_count': 0,
                    'source': 'no_fills_found'
                }
            
            # 🔥🔥 Position PnL과 수수료 분리 계산
            total_position_pnl = 0.0
            total_trading_fees = 0.0
            total_funding_fees = 0.0
            trade_count = 0
            
            for fill in fills:
                try:
                    # 🔥🔥 Position PnL 추출 (실제 포지션 손익 - 수수료 제외)
                    position_pnl = 0.0
                    
                    # Position PnL 관련 필드들 (우선순위 순)
                    pnl_fields = [
                        'positionPnl',      # 실제 포지션 손익
                        'realizedPnl',      # 실현 손익
                        'closedPnl',        # 청산 손익
                        'pnl'               # 일반 손익
                    ]
                    
                    for field in pnl_fields:
                        if field in fill and fill[field] is not None:
                            try:
                                position_pnl = float(fill[field])
                                if position_pnl != 0:
                                    logger.debug(f"Position PnL 추출: {field} = {position_pnl}")
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    # profit 필드는 마지막 백업 (수수료 포함될 수 있음)
                    if position_pnl == 0 and 'profit' in fill:
                        try:
                            position_pnl = float(fill.get('profit', 0))
                            logger.debug(f"백업 profit 필드 사용: {position_pnl}")
                        except (ValueError, TypeError):
                            pass
                    
                    # 🔥🔥 거래 수수료 추출 (Trading Fee)
                    trading_fee = 0.0
                    
                    # 거래 수수료 필드들
                    fee_fields = [
                        'tradingFee',       # 거래 수수료
                        'fee',              # 일반 수수료
                        'totalFee',         # 총 수수료
                        'commissionFee'     # 커미션 수수료
                    ]
                    
                    for field in fee_fields:
                        if field in fill and fill[field] is not None:
                            try:
                                fee_value = float(fill[field])
                                if fee_value != 0:
                                    trading_fee = abs(fee_value)  # 수수료는 항상 양수
                                    logger.debug(f"거래 수수료 추출: {field} = {trading_fee}")
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    # 🔥🔥 펀딩비 추출 (Funding Fee)
                    funding_fee = 0.0
                    
                    # 펀딩비 필드들
                    funding_fields = [
                        'fundingFee',       # 펀딩 수수료
                        'funding',          # 펀딩비
                        'fundFee'           # 펀드 수수료
                    ]
                    
                    for field in funding_fields:
                        if field in fill and fill[field] is not None:
                            try:
                                funding_value = float(fill[field])
                                if funding_value != 0:
                                    funding_fee = funding_value  # 펀딩비는 양수/음수 모두 가능
                                    logger.debug(f"펀딩비 추출: {field} = {funding_fee}")
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    # 통계 누적
                    if position_pnl != 0 or trading_fee != 0 or funding_fee != 0:
                        total_position_pnl += position_pnl
                        total_trading_fees += trading_fee
                        total_funding_fees += funding_fee
                        trade_count += 1
                        
                        logger.debug(f"거래 처리: PnL={position_pnl:.4f}, 거래수수료={trading_fee:.4f}, 펀딩비={funding_fee:.4f}")
                
                except Exception as fill_error:
                    logger.debug(f"거래 내역 처리 오류: {fill_error}")
                    continue
            
            # 🔥🔥 최종 계산
            net_profit = total_position_pnl + total_funding_fees - total_trading_fees
            
            logger.info(f"✅ Position PnL 기준 정확한 손익 계산 완료:")
            logger.info(f"  - Position PnL: ${total_position_pnl:.4f} (수수료 제외 실제 포지션 손익)")
            logger.info(f"  - 거래 수수료: -${total_trading_fees:.4f} (오픈/클로징 수수료)")
            logger.info(f"  - 펀딩비: {total_funding_fees:+.4f} (펀딩 수수료)")
            logger.info(f"  - 순 수익: ${net_profit:.4f} (Position PnL + 펀딩비 - 거래수수료)")
            logger.info(f"  - 거래 건수: {trade_count}건")
            
            return {
                'position_pnl': total_position_pnl,        # 실제 포지션 손익 (수수료 제외)
                'trading_fees': total_trading_fees,        # 거래 수수료 (오픈/클로징)
                'funding_fees': total_funding_fees,        # 펀딩비
                'net_profit': net_profit,                  # 순 수익
                'trade_count': trade_count,
                'source': 'position_pnl_based_accurate',
                'confidence': 'high'
            }
            
        except Exception as e:
            logger.error(f"Position PnL 기준 손익 계산 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            
            return {
                'position_pnl': 0.0,
                'trading_fees': 0.0,
                'funding_fees': 0.0,
                'net_profit': 0.0,
                'trade_count': 0,
                'source': 'error',
                'confidence': 'low'
            }
    
    async def get_today_position_pnl(self) -> float:
        """🔥🔥 오늘 Position PnL 기준 실현손익 조회"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 오늘 0시 (KST)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # UTC로 변환하여 타임스탬프 생성
            start_time_utc = today_start.astimezone(pytz.UTC)
            end_time_utc = now.astimezone(pytz.UTC)
            
            start_timestamp = int(start_time_utc.timestamp() * 1000)
            end_timestamp = int(end_time_utc.timestamp() * 1000)
            
            # Position PnL 기준 계산
            result = await self.get_position_pnl_based_profit(
                start_timestamp, 
                end_timestamp, 
                self.config.symbol
            )
            
            return result.get('position_pnl', 0.0)  # 수수료 제외한 실제 Position PnL
            
        except Exception as e:
            logger.error(f"오늘 Position PnL 조회 실패: {e}")
            return 0.0
    
    async def get_7day_position_pnl(self) -> Dict:
        """🔥🔥 정확한 7일 Position PnL 조회 - 비트겟 API 7일 제한 준수"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            current_time = datetime.now(kst)
            
            # 🔥🔥 비트겟 API 7일 제한 준수: 현재에서 정확히 7일 전
            seven_days_ago = current_time - timedelta(days=7)
            
            logger.info(f"🔍 비트겟 7일 Position PnL 계산 (API 7일 제한 준수):")
            logger.info(f"  - 시작: {seven_days_ago.strftime('%Y-%m-%d %H:%M')} KST")
            logger.info(f"  - 종료: {current_time.strftime('%Y-%m-%d %H:%M')} KST")
            
            # UTC로 변환
            start_time_utc = seven_days_ago.astimezone(pytz.UTC)
            end_time_utc = current_time.astimezone(pytz.UTC)
            
            start_timestamp = int(start_time_utc.timestamp() * 1000)
            end_timestamp = int(end_time_utc.timestamp() * 1000)
            
            # 🔥🔥 7일 제한 확인 (안전장치)
            duration_days = (end_timestamp - start_timestamp) / (1000 * 60 * 60 * 24)
            if duration_days > 7.1:  # 0.1일 여유
                logger.warning(f"기간이 7일을 초과함: {duration_days:.1f}일, 7일로 조정")
                start_timestamp = end_timestamp - (7 * 24 * 60 * 60 * 1000)
                duration_days = 7.0
            
            # Position PnL 기준 계산
            result = await self.get_position_pnl_based_profit(
                start_timestamp, 
                end_timestamp, 
                self.config.symbol
            )
            
            position_pnl = result.get('position_pnl', 0.0)
            daily_average = position_pnl / duration_days if duration_days > 0 else 0
            
            logger.info(f"✅ 비트겟 7일 Position PnL 계산 완료 (API 제한 준수):")
            logger.info(f"  - 실제 기간: {duration_days:.1f}일")
            logger.info(f"  - Position PnL: ${position_pnl:.4f}")
            logger.info(f"  - 일평균: ${daily_average:.4f}")
            
            return {
                'total_pnl': position_pnl,           # 수수료 제외한 실제 Position PnL
                'daily_pnl': {},                     # 일별 분석은 별도 구현 필요시
                'average_daily': daily_average,
                'trade_count': result.get('trade_count', 0),
                'actual_days': duration_days,
                'trading_fees': result.get('trading_fees', 0),
                'funding_fees': result.get('funding_fees', 0),
                'net_profit': result.get('net_profit', 0),
                'source': 'bitget_7days_api_limit_compliant',
                'confidence': 'high'
            }
            
        except Exception as e:
            logger.error(f"비트겟 7일 Position PnL 조회 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'average_daily': 0,
                'trade_count': 0,
                'actual_days': 7,
                'source': 'error',
                'confidence': 'low'
            }
    
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
    
    async def get_plan_orders(self, symbol: str = None, status: str = 'live') -> List[Dict]:
        """예약 주문 조회 - 통합된 방식"""
        symbol = symbol or self.config.symbol
        
        try:
            # V2 API로 예약 주문 조회
            endpoint = "/api/v2/mix/order/plan-orders-pending"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'
            }
            
            if status:
                params['status'] = status
            
            response = await self._request('GET', endpoint, params=params)
            logger.debug(f"예약 주문 조회 응답: {response}")
            
            # 응답 형태에 따라 처리
            if isinstance(response, dict):
                if 'orderList' in response:
                    return response['orderList']
                elif 'data' in response and isinstance(response['data'], list):
                    return response['data']
                elif isinstance(response.get('data'), dict) and 'orderList' in response['data']:
                    return response['data']['orderList']
            elif isinstance(response, list):
                return response
            
            logger.warning(f"예약 주문 응답 형식 예상치 못함: {type(response)}")
            return []
            
        except Exception as e:
            logger.error(f"예약 주문 조회 실패: {e}")
            return []
    
    async def get_tp_sl_orders(self, symbol: str = None, status: str = 'live') -> List[Dict]:
        """TP/SL 주문 조회 - 통합된 방식"""
        symbol = symbol or self.config.symbol
        
        try:
            # V2 API로 TP/SL 주문 조회
            endpoint = "/api/v2/mix/order/stop-orders-pending"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'
            }
            
            if status:
                params['status'] = status
            
            response = await self._request('GET', endpoint, params=params)
            logger.debug(f"TP/SL 주문 조회 응답: {response}")
            
            # 응답 형태에 따라 처리
            if isinstance(response, dict):
                if 'orderList' in response:
                    return response['orderList']
                elif 'data' in response and isinstance(response['data'], list):
                    return response['data']
                elif isinstance(response.get('data'), dict) and 'orderList' in response['data']:
                    return response['data']['orderList']
            elif isinstance(response, list):
                return response
            
            logger.warning(f"TP/SL 주문 응답 형식 예상치 못함: {type(response)}")
            return []
            
        except Exception as e:
            logger.error(f"TP/SL 주문 조회 실패: {e}")
            return []
    
    async def get_all_plan_orders_with_tp_sl(self, symbol: str = None) -> Dict:
        """예약 주문과 TP/SL 주문을 함께 조회"""
        symbol = symbol or self.config.symbol
        
        try:
            logger.info(f"🔍 전체 플랜 주문 조회 시작: {symbol}")
            
            # 예약 주문과 TP/SL 주문을 병렬로 조회
            plan_orders_task = self.get_plan_orders(symbol, 'live')
            tp_sl_orders_task = self.get_tp_sl_orders(symbol, 'live')
            
            plan_orders, tp_sl_orders = await asyncio.gather(
                plan_orders_task, 
                tp_sl_orders_task, 
                return_exceptions=True
            )
            
            # 예외 처리
            if isinstance(plan_orders, Exception):
                logger.error(f"예약 주문 조회 오류: {plan_orders}")
                plan_orders = []
            
            if isinstance(tp_sl_orders, Exception):
                logger.error(f"TP/SL 주문 조회 오류: {tp_sl_orders}")
                tp_sl_orders = []
            
            # 결과 로깅
            plan_count = len(plan_orders) if plan_orders else 0
            tp_sl_count = len(tp_sl_orders) if tp_sl_orders else 0
            total_count = plan_count + tp_sl_count
            
            logger.info(f"📊 전체 플랜 주문 조회 결과:")
            logger.info(f"   - 예약 주문: {plan_count}개")
            logger.info(f"   - TP/SL 주문: {tp_sl_count}개")
            logger.info(f"   - 총합: {total_count}개")
            
            # 각 주문의 TP/SL 정보 분석
            for i, order in enumerate(plan_orders[:3]):  # 최대 3개만 로깅
                order_id = order.get('orderId', order.get('planOrderId', f'unknown_{i}'))
                side = order.get('side', order.get('tradeSide', 'unknown'))
                trigger_price = order.get('triggerPrice', order.get('price', 0))
                
                # TP/SL 가격 확인
                tp_price = None
                sl_price = None
                
                # TP 추출
                for tp_field in ['presetStopSurplusPrice', 'stopSurplusPrice', 'takeProfitPrice']:
                    value = order.get(tp_field)
                    if value and str(value) not in ['0', '0.0', '', 'null']:
                        try:
                            tp_price = float(value)
                            if tp_price > 0:
                                break
                        except:
                            continue
                
                # SL 추출
                for sl_field in ['presetStopLossPrice', 'stopLossPrice', 'stopPrice']:
                    value = order.get(sl_field)
                    if value and str(value) not in ['0', '0.0', '', 'null']:
                        try:
                            sl_price = float(value)
                            if sl_price > 0:
                                break
                        except:
                            continue
                
                # 로깅
                tp_display = f"${tp_price:.2f}" if tp_price else "없음"
                sl_display = f"${sl_price:.2f}" if sl_price else "없음"
                
                logger.info(f"🎯 예약주문 {i+1}: ID={order_id}")
                logger.info(f"   방향: {side}, 트리거: ${trigger_price}")
                logger.info(f"   TP: {tp_display}")
                logger.info(f"   SL: {sl_display}")
            
            # TP/SL 주문도 분석
            for i, order in enumerate(tp_sl_orders[:3]):  # 최대 3개만 로깅
                order_id = order.get('orderId', order.get('planOrderId', f'tpsl_{i}'))
                side = order.get('side', order.get('tradeSide', 'unknown'))
                trigger_price = order.get('triggerPrice', order.get('price', 0))
                reduce_only = order.get('reduceOnly', False)
                
                logger.info(f"🛡️ TP/SL주문 {i+1}: ID={order_id}")
                logger.info(f"   방향: {side}, 트리거: ${trigger_price}")
                logger.info(f"   클로즈: {reduce_only}")
            
            return {
                'plan_orders': plan_orders or [],
                'tp_sl_orders': tp_sl_orders or [],
                'total_count': total_count,
                'plan_count': plan_count,
                'tp_sl_count': tp_sl_count
            }
            
        except Exception as e:
            logger.error(f"전체 플랜 주문 조회 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return {
                'plan_orders': [],
                'tp_sl_orders': [],
                'total_count': 0,
                'plan_count': 0,
                'tp_sl_count': 0,
                'error': str(e)
            }
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
