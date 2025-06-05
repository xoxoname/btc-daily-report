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
        
        # 🔥🔥🔥 API 연결 상태 추적
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
        self.max_consecutive_failures = 10
        
        # 🔥🔥🔥 백업 엔드포인트들
        self.ticker_endpoints = [
            "/api/v2/mix/market/ticker",  # 기본 V2
            "/api/mix/v1/market/ticker",  # V1 백업
            "/api/v2/spot/market/tickers", # Spot 백업 (변환 필요)
        ]
        
        # API 키 검증 상태
        self.api_keys_validated = False
        
    def _initialize_session(self):
        """세션 초기화"""
        if not self.session:
            # 🔥🔥🔥 연결 타임아웃 및 재시도 설정 강화
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
        
        # 🔥🔥🔥 API 키 유효성 검증
        await self._validate_api_keys()
        
        logger.info("Bitget 클라이언트 초기화 완료")
    
    async def _validate_api_keys(self):
        """🔥🔥🔥 API 키 유효성 검증"""
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
        """🔥🔥🔥 API 요청 - 강화된 오류 처리"""
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
        
        # 🔥🔥🔥 재시도 로직
        for attempt in range(max_retries):
            try:
                logger.debug(f"비트겟 API 요청 (시도 {attempt + 1}/{max_retries}): {method} {endpoint}")
                
                async with self.session.request(method, url, headers=headers, data=body) as response:
                    response_text = await response.text()
                    
                    # 🔥🔥🔥 상세한 응답 로깅
                    logger.debug(f"비트겟 API 응답 상태: {response.status}")
                    logger.debug(f"비트겟 API 응답 헤더: {dict(response.headers)}")
                    logger.debug(f"비트겟 API 응답 내용: {response_text[:500]}...")
                    
                    # 빈 응답 체크
                    if not response_text.strip():
                        error_msg = f"빈 응답 받음 (상태: {response.status})"
                        logger.warning(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # 지수 백오프
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
                    
                    # 🔥🔥🔥 성공 기록
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
        """🔥🔥🔥 성공 기록"""
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
    
    def _record_failure(self, error_msg: str):
        """🔥🔥🔥 실패 기록"""
        self.consecutive_failures += 1
        
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.api_connection_healthy = False
            logger.error(f"비트겟 API 연결 비정상 상태: 연속 {self.consecutive_failures}회 실패")
        
        logger.warning(f"비트겟 API 실패 기록: {error_msg} (연속 실패: {self.consecutive_failures}회)")
    
    async def get_ticker(self, symbol: str = None) -> Dict:
        """🔥🔥🔥 현재가 정보 조회 - 다중 엔드포인트 지원"""
        symbol = symbol or self.config.symbol
        
        # 🔥🔥🔥 여러 엔드포인트 순차 시도
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
                
                # 🔥🔥🔥 응답 데이터 검증 및 정규화
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
        
        # 🔥🔥🔥 모든 엔드포인트 실패
        error_msg = f"모든 티커 엔드포인트 실패: {', '.join(self.ticker_endpoints)}"
        logger.error(error_msg)
        self._record_failure("모든 티커 엔드포인트 실패")
        return {}
    
    def _validate_ticker_data(self, ticker_data: Dict) -> bool:
        """🔥🔥🔥 티커 데이터 유효성 검증"""
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
        """🔥🔥🔥 티커 데이터 정규화"""
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
            
            # 🔥 방법 1: Account Bills 기반 조회 (수정된 방식)
            bills_result = await self._get_profit_from_account_bills_corrected(start_timestamp, end_timestamp, period_start, days)
            
            # 🔥 방법 2: 거래 내역 기반 조회 (강화된 방식)
            fills_result = await self._get_profit_from_fills_enhanced(symbol, start_timestamp, end_timestamp, period_start, days)
            
            # 🔥 방법 3: achievedProfits 기반 (포지션 수익)
            achieved_result = await self._get_achieved_profits()
            
            # 🔥 결과 비교 및 최적 값 선택
            final_result = self._select_best_profit_data_corrected(bills_result, fills_result, achieved_result, days)
            
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
    
    async def _get_profit_from_account_bills_corrected(self, start_timestamp: int, end_timestamp: int, 
                                                     period_start: datetime, days: int) -> Dict:
        """🔥🔥🔥 Account Bills에서 손익 추출 - 수정된 방식"""
        try:
            logger.info("🔥 Account Bills 기반 손익 조회 시작 (수정된 방식)")
            
            kst = pytz.timezone('Asia/Seoul')
            
            # 모든 손익 관련 Bills 조회 (수정된 방식)
            all_bills = []
            
            # 🔥🔥🔥 수정된 Account Bills 조회 사용
            # contract_settle (실현 손익)
            settle_bills = await self._get_all_bills_with_paging_corrected(
                start_timestamp, end_timestamp, 'contract_settle'
            )
            all_bills.extend(settle_bills)
            logger.info(f"실현 손익 Bills: {len(settle_bills)}건")
            
            # fee (수수료)
            fee_bills = await self._get_all_bills_with_paging_corrected(
                start_timestamp, end_timestamp, 'contract_fee'
            )
            all_bills.extend(fee_bills)
            logger.info(f"수수료 Bills: {len(fee_bills)}건")
            
            # funding (펀딩비)
            funding_bills = await self._get_all_bills_with_paging_corrected(
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
                    
                    # 🔥🔥🔥 수정된 businessType에 맞춰 조정
                    if business_type in ['contract_settle', 'settle', 'realized', 'pnl', 'profit']:
                        daily_data[bill_date_str]['pnl'] += amount
                        daily_data[bill_date_str]['trades'] += 1
                        total_pnl += amount
                        trade_count += 1
                    elif business_type in ['contract_fee', 'fee', 'trading_fee', 'trade_fee']:
                        daily_data[bill_date_str]['fees'] += abs(amount)
                        total_fees += abs(amount)
                    elif business_type in ['contract_funding_fee', 'funding', 'funding_fee', 'fund']:
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
            
            # 🔥🔥🔥 Account Bills가 성공했는지 확인
            confidence = 'high' if len(all_bills) > 0 else 'low'
            source = 'account_bills_corrected' if len(all_bills) > 0 else 'account_bills_empty'
            
            return {
                'total_pnl': total_pnl,
                'daily_pnl': daily_pnl,
                'days': days,
                'average_daily': total_pnl / days if days > 0 else 0,
                'trade_count': trade_count,
                'total_fees': total_fees,
                'source': source,
                'confidence': confidence
            }
            
        except Exception as e:
            logger.error(f"Account Bills 손익 조회 실패: {e}")
            return {
                'total_pnl': 0, 'daily_pnl': {}, 'days': days,
                'average_daily': 0, 'trade_count': 0, 'total_fees': 0,
                'source': 'account_bills_error', 'confidence': 'low'
            }
    
    async def _get_all_bills_with_paging_corrected(self, start_timestamp: int, end_timestamp: int, 
                                                 business_type: str) -> List[Dict]:
        """🔥🔥🔥 수정된 방식으로 모든 Bills 조회"""
        all_bills = []
        next_id = None
        page = 0
        
        while page < 20:  # 최대 20페이지
            bills = await self.get_account_bills_v2_corrected(
                start_time=start_timestamp,
                end_time=end_timestamp,
                business_type=business_type,
                limit=100,
                next_id=next_id
            )
            
            if not bills:
                logger.info(f"{business_type} Bills 페이지 {page + 1}: 데이터 없음, 종료")
                break
            
            all_bills.extend(bills)
            logger.info(f"{business_type} Bills 페이지 {page + 1}: {len(bills)}건 조회 (누적 {len(all_bills)}건)")
            
            if len(bills) < 100:
                logger.info(f"{business_type} Bills: 마지막 페이지 도달 ({len(bills)}건 < 100건)")
                break
            
            # 다음 페이지 ID
            last_bill = bills[-1]
            next_id = last_bill.get('billId', last_bill.get('id'))
            if not next_id:
                logger.info(f"{business_type} Bills: 다음 페이지 ID 없음, 종료")
                break
            
            page += 1
            await asyncio.sleep(0.1)
        
        logger.info(f"{business_type} Bills 총 {len(all_bills)}건 조회")
        return all_bills
    
    async def get_account_bills_v2_corrected(self, start_time: int = None, end_time: int = None, 
                                           business_type: str = None, limit: int = 100,
                                           next_id: str = None) -> List[Dict]:
        """🔥🔥🔥 V2 Account Bills 수정된 방식 - businessType 파라미터 조정"""
        
        # 🔥🔥🔥 businessType error가 발생한 엔드포인트를 다른 방식으로 시도
        working_endpoint = "/api/v2/mix/account/bill"
        
        # 🔥🔥🔥 businessType 파라미터를 다양한 방식으로 시도
        business_type_variants = []
        
        if business_type == 'contract_settle':
            business_type_variants = ['settle', 'realized', 'pnl', 'profit', 'trade_settle']
        elif business_type == 'contract_fee':
            business_type_variants = ['fee', 'trading_fee', 'trade_fee']
        elif business_type == 'contract_funding_fee':
            business_type_variants = ['funding', 'funding_fee', 'fund']
        else:
            business_type_variants = [None]  # businessType 없이 시도
        
        for variant in business_type_variants:
            try:
                params = {
                    'productType': 'USDT-FUTURES',
                    'marginCoin': 'USDT'
                }
                
                if start_time:
                    params['startTime'] = str(start_time)
                if end_time:
                    params['endTime'] = str(end_time)
                if variant:  # businessType이 있는 경우만 추가
                    params['businessType'] = variant
                if limit:
                    params['limit'] = str(min(limit, 100))
                if next_id:
                    params['startId'] = str(next_id)
                
                logger.info(f"🔍 Account Bills V2 businessType 시도: '{variant}'")
                response = await self._request('GET', working_endpoint, params=params)
                
                if response is not None:
                    logger.info(f"✅ businessType '{variant}' 성공!")
                    
                    if isinstance(response, list):
                        logger.info(f"📊 businessType '{variant}'에서 {len(response)}건 조회 성공")
                        return response
                    elif isinstance(response, dict):
                        # 다양한 필드명 시도
                        for field in ['billsList', 'bills', 'list', 'data']:
                            if field in response and isinstance(response[field], list):
                                bills = response[field]
                                logger.info(f"📊 businessType '{variant}'에서 {len(bills)}건 조회 성공 ({field} 필드)")
                                return bills
                        
                        # dict이지만 리스트 필드가 없는 경우
                        logger.warning(f"⚠️ businessType '{variant}': dict 응답이지만 알려진 리스트 필드 없음: {list(response.keys())}")
                        continue
                    else:
                        logger.warning(f"⚠️ businessType '{variant}': 알 수 없는 응답 타입: {type(response)}")
                        continue
                        
            except Exception as e:
                error_msg = str(e)
                if "Parameter businessType error" in error_msg:
                    logger.debug(f"❌ businessType '{variant}' 파라미터 오류, 다음 시도")
                    continue
                elif "404" in error_msg or "NOT FOUND" in error_msg:
                    logger.debug(f"❌ businessType '{variant}' 404 오류")
                    break  # 404면 다른 variant도 같은 결과일 것
                else:
                    logger.warning(f"❌ businessType '{variant}' 기타 오류: {e}")
                    continue
        
        # 🔥🔥🔥 모든 businessType variant가 실패한 경우, V1 API 시도
        logger.info("🔄 V2 실패, V1 Account Bills 시도")
        return await self.get_account_bills_v1_fallback(start_time, end_time, business_type, limit, next_id)
    
    async def get_account_bills_v1_fallback(self, start_time: int = None, end_time: int = None, 
                                          business_type: str = None, limit: int = 100,
                                          next_id: str = None) -> List[Dict]:
        """🔥🔥🔥 V1 Account Bills 폴백 (V2가 모두 실패할 때)"""
        try:
            # V1 API 엔드포인트들
            v1_endpoints = [
                "/api/mix/v1/account/accountBill",
                "/api/mix/v1/account/bill", 
                "/api/mix/v1/account/bills"
            ]
            
            for endpoint in v1_endpoints:
                try:
                    # V1은 다른 파라미터 형식 사용
                    params = {
                        'symbol': f"{self.config.symbol}_UMCBL",
                        'productType': 'umcbl'
                    }
                    
                    if start_time:
                        params['startTime'] = str(start_time)
                    if end_time:
                        params['endTime'] = str(end_time)
                    if business_type:
                        # V1에서는 다른 businessType 이름 사용 가능
                        if business_type == 'contract_settle':
                            params['businessType'] = 'settle'
                        elif business_type == 'contract_fee':
                            params['businessType'] = 'fee'
                        elif business_type == 'contract_funding_fee':
                            params['businessType'] = 'funding'
                        else:
                            params['businessType'] = business_type
                    if limit:
                        params['pageSize'] = str(min(limit, 100))
                    if next_id:
                        params['lastEndId'] = str(next_id)
                    
                    logger.info(f"🔍 V1 Account Bills 시도: {endpoint}")
                    response = await self._request('GET', endpoint, params=params)
                    
                    if response is not None:
                        logger.info(f"✅ V1 {endpoint} 성공!")
                        
                        if isinstance(response, list):
                            logger.info(f"📊 V1에서 {len(response)}건 조회 성공")
                            return response
                        elif isinstance(response, dict):
                            # V1 응답 구조
                            for field in ['billsList', 'bills', 'list', 'data']:
                                if field in response and isinstance(response[field], list):
                                    bills = response[field]
                                    logger.info(f"📊 V1에서 {len(bills)}건 조회 성공 ({field} 필드)")
                                    return bills
                        
                        logger.debug(f"V1 {endpoint}: 빈 응답 또는 알 수 없는 구조")
                        continue
                    
                except Exception as e:
                    logger.debug(f"V1 {endpoint} 실패: {e}")
                    continue
            
            logger.warning("⚠️ 모든 V1 Account Bills 엔드포인트도 실패")
            return []
            
        except Exception as e:
            logger.error(f"V1 Account Bills 폴백 실패: {e}")
            return []
    
    async def _get_profit_from_fills_enhanced(self, symbol: str, start_timestamp: int, end_timestamp: int,
                                            period_start: datetime, days: int) -> Dict:
        """🔥🔥🔥 거래 내역(Fills)에서 손익 추출 - 강화된 버전"""
        try:
            logger.info("🔥 거래 내역(Fills) 기반 손익 조회 시작 (강화된 버전)")
            
            kst = pytz.timezone('Asia/Seoul')
            
            # 모든 거래 내역 조회 (강화된 방식)
            all_fills = await self._get_enhanced_fills_v2(symbol, start_timestamp, end_timestamp)
            
            logger.info(f"조회된 총 거래 수: {len(all_fills)}건")
            
            # 중복 제거 (강화된 로직)
            unique_fills = self._remove_duplicate_fills_enhanced(all_fills)
            logger.info(f"중복 제거 후: {len(unique_fills)}건")
            
            # 날짜별 분석
            daily_pnl = {}
            total_pnl = 0
            total_fees = 0
            trade_count = 0
            
            for fill in unique_fills:
                try:
                    # 시간 추출 (더 많은 필드 시도)
                    fill_time = None
                    for time_field in ['cTime', 'createTime', 'createdTime', 'updateTime', 'time', 'timestamp']:
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
                    
                    # 손익 추출 (더 많은 필드 시도)
                    profit = 0.0
                    for profit_field in ['profit', 'realizedPL', 'realizedPnl', 'pnl', 'realizedProfit']:
                        if profit_field in fill and fill[profit_field] is not None:
                            try:
                                profit = float(fill[profit_field])
                                if profit != 0:
                                    break
                            except:
                                continue
                    
                    # 수수료 추출 (강화)
                    fee = self._extract_fee_from_fill_enhanced(fill)
                    
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
                'source': 'trade_fills_enhanced',
                'confidence': 'high' if trade_count > 0 else 'medium'  # 거래가 있으면 high
            }
            
        except Exception as e:
            logger.error(f"거래 내역 손익 조회 실패: {e}")
            return {
                'total_pnl': 0, 'daily_pnl': {}, 'days': days,
                'average_daily': 0, 'trade_count': 0, 'total_fees': 0,
                'source': 'fills_error', 'confidence': 'low'
            }
    
    async def _get_enhanced_fills_v2(self, symbol: str, start_timestamp: int, end_timestamp: int) -> List[Dict]:
        """🔥🔥🔥 향상된 거래 내역 조회 V2"""
        all_fills = []
        
        # 더 세밀하게 나눠서 조회 (3일씩)
        current_start = start_timestamp
        
        while current_start < end_timestamp:
            current_end = min(current_start + (3 * 24 * 60 * 60 * 1000), end_timestamp)
            
            # 해당 기간 조회
            period_fills = await self._get_period_fills_v2(symbol, current_start, current_end)
            all_fills.extend(period_fills)
            
            current_start = current_end
            await asyncio.sleep(0.1)  # 더 짧은 대기
        
        return all_fills
    
    async def _get_period_fills_v2(self, symbol: str, start_time: int, end_time: int) -> List[Dict]:
        """🔥🔥🔥 특정 기간의 거래 내역 조회 V2"""
        all_fills = []
        
        # 더 많은 엔드포인트 시도
        endpoints = [
            "/api/v2/mix/order/fill-history",
            "/api/v2/mix/order/fills",
            "/api/v2/mix/order/trade-history",  # 추가
            "/api/v2/mix/trade/fills"           # 추가
        ]
        
        for endpoint in endpoints:
            try:
                fills = await self._get_fills_from_endpoint_v2(endpoint, symbol, start_time, end_time)
                if fills:
                    all_fills.extend(fills)
                    logger.info(f"{endpoint}: {len(fills)}건 조회")
                    break  # 성공하면 다른 엔드포인트는 시도하지 않음
            except Exception as e:
                logger.debug(f"{endpoint} 실패: {e}")
                continue
        
        return all_fills
    
    async def _get_fills_from_endpoint_v2(self, endpoint: str, symbol: str, 
                                        start_time: int, end_time: int) -> List[Dict]:
        """🔥🔥🔥 특정 엔드포인트에서 거래 내역 조회 V2"""
        all_fills = []
        last_id = None
        page = 0
        
        while page < 15:  # 더 많은 페이지 허용
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES',
                'startTime': str(start_time),
                'endTime': str(end_time),
                'limit': '500'
            }
            
            if last_id:
                # 다양한 페이징 파라미터 시도
                for page_param in ['lastEndId', 'idLessThan', 'fromId', 'startId']:
                    params_copy = params.copy()
                    params_copy[page_param] = str(last_id)
                    
                    try:
                        response = await self._request('GET', endpoint, params=params_copy)
                        break
                    except:
                        continue
                else:
                    # 모든 페이징 파라미터 실패
                    break
            else:
                response = await self._request('GET', endpoint, params=params)
            
            fills = []
            if isinstance(response, dict):
                # 더 많은 응답 필드 시도
                for field in ['fillList', 'list', 'data', 'fills', 'trades', 'records']:
                    if field in response and isinstance(response[field], list):
                        fills = response[field]
                        break
            elif isinstance(response, list):
                fills = response
            
            if not fills:
                break
            
            all_fills.extend(fills)
            
            if len(fills) < 500:
                break
            
            # 다음 페이지 ID (더 많은 필드 시도)
            last_fill = fills[-1]
            new_last_id = self._get_enhanced_fill_id_v2(last_fill)
            
            if not new_last_id or new_last_id == last_id:
                break
            
            last_id = new_last_id
            page += 1
            
            await asyncio.sleep(0.05)  # 더 짧은 대기
        
        return all_fills
    
    def _get_enhanced_fill_id_v2(self, fill: Dict) -> Optional[str]:
        """🔥🔥🔥 향상된 거래 ID 추출 V2"""
        for field in ['fillId', 'tradeId', 'id', 'orderId', 'clientOid', 'cTime', 'createTime']:
            if field in fill and fill[field]:
                return str(fill[field])
        return None
    
    def _remove_duplicate_fills_enhanced(self, fills: List[Dict]) -> List[Dict]:
        """🔥🔥🔥 향상된 중복 제거 V2"""
        seen = set()
        unique_fills = []
        
        for fill in fills:
            # 더 정교한 중복 체크
            fill_id = self._get_enhanced_fill_id_v2(fill)
            
            # 더 많은 필드로 복합 키 생성
            time_key = str(fill.get('cTime', fill.get('createTime', '')))
            size_key = str(fill.get('size', fill.get('amount', '')))
            price_key = str(fill.get('price', fill.get('fillPrice', '')))
            side_key = str(fill.get('side', ''))
            
            composite_key = f"{fill_id}_{time_key}_{size_key}_{price_key}_{side_key}"
            
            if composite_key not in seen:
                seen.add(composite_key)
                unique_fills.append(fill)
            else:
                logger.debug(f"중복 제거: {fill_id}")
        
        return unique_fills
    
    def _extract_fee_from_fill_enhanced(self, fill: Dict) -> float:
        """🔥🔥🔥 거래에서 수수료 추출 - 강화된 버전"""
        fee = 0.0
        
        # 더 많은 수수료 필드 확인
        fee_fields = [
            'fee', 'fees', 'totalFee', 'tradeFee', 'commission',
            'feeAmount', 'feeCoin', 'feeRate'
        ]
        
        # feeDetail 확인 (강화)
        fee_detail = fill.get('feeDetail', [])
        if isinstance(fee_detail, list):
            for fee_info in fee_detail:
                if isinstance(fee_info, dict):
                    for fee_field in ['totalFee', 'fee', 'amount']:
                        if fee_field in fee_info:
                            fee += abs(float(fee_info.get(fee_field, 0)))
        
        # 다른 수수료 필드들 확인 (강화)
        if fee == 0:
            for fee_field in fee_fields:
                if fee_field in fill and fill[fee_field] is not None:
                    try:
                        fee_value = float(fill[fee_field])
                        if fee_value != 0:
                            fee = abs(fee_value)
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
    
    def _select_best_profit_data_corrected(self, bills_result: Dict, fills_result: Dict, 
                                         achieved_result: Dict, days: int) -> Dict:
        """🔥🔥🔥 최적의 손익 데이터 선택 - 수정된 로직"""
        
        logger.info("🔥 손익 데이터 비교 및 선택 (수정된 로직)")
        logger.info(f"   - Account Bills: ${bills_result['total_pnl']:.2f} (신뢰도: {bills_result['confidence']})")
        logger.info(f"   - Trade Fills: ${fills_result['total_pnl']:.2f} (신뢰도: {fills_result['confidence']})")
        logger.info(f"   - Achieved Profits: ${achieved_result['total_pnl']:.2f} (신뢰도: {achieved_result['confidence']})")
        
        # 🔥🔥🔥 데이터 유효성 확인
        bills_has_data = (bills_result['confidence'] == 'high' and 
                         (bills_result['total_pnl'] != 0 or bills_result['trade_count'] > 0))
        
        fills_has_data = (fills_result['confidence'] in ['high', 'medium'] and 
                         (fills_result['total_pnl'] != 0 or fills_result['trade_count'] > 0))
        
        achieved_has_data = achieved_result['total_pnl'] != 0
        
        # 1순위: Trade Fills (강화된 버전이 성공하고 데이터가 있으면)
        if fills_has_data and fills_result['confidence'] == 'high':
            logger.info("✅ Trade Fills Enhanced 선택 (강화된 버전, 데이터 있음)")
            fills_result['source'] = 'trade_fills_enhanced_primary'
            return fills_result
        
        # 2순위: Account Bills (수정된 방식이 성공했으면)
        if bills_has_data:
            logger.info("✅ Account Bills 선택 (수정된 방식, 데이터 있음)")
            bills_result['source'] = 'account_bills_corrected_primary'
            return bills_result
        
        # 3순위: Trade Fills (중간 신뢰도라도 데이터가 있으면)
        if fills_has_data:
            logger.info("✅ Trade Fills 선택 (중간 신뢰도, 데이터 있음)")
            fills_result['source'] = 'trade_fills_enhanced_secondary'
            return fills_result
        
        # 4순위: Achieved Profits
        if achieved_has_data:
            logger.info("✅ Achieved Profits 선택 (다른 방법 실패)")
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
        
        # 5순위: 데이터가 없더라도 가장 신뢰할 만한 소스
        if bills_result['trade_count'] > 0 or bills_result['total_pnl'] != 0:
            logger.info("✅ Account Bills 선택 (최종 폴백)")
            bills_result['source'] = 'account_bills_final_fallback'
            return bills_result
        
        if fills_result['trade_count'] > 0 or fills_result['total_pnl'] != 0:
            logger.info("✅ Trade Fills 선택 (최종 폴백)")
            fills_result['source'] = 'trade_fills_final_fallback'
            return fills_result
        
        # 최종: 모든 데이터가 0
        logger.warning("⚠️ 모든 손익 데이터가 0 또는 없음 (Trade Fills 기본 반환)")
        fills_result['source'] = 'no_data_available'
        fills_result['confidence'] = 'none'
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
    
    async def get_account_bills(self, start_time: int = None, end_time: int = None, 
                               business_type: str = None, limit: int = 100,
                               next_id: str = None) -> List[Dict]:
        """🔥🔥🔥 계정 거래 내역 조회 - 수정된 방식"""
        return await self.get_account_bills_v2_corrected(start_time, end_time, business_type, limit, next_id)
    
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
                # Trade Fills Enhanced가 성공하면 우선 사용
                logger.info("✅ Trade Fills Enhanced 기반 정확한 데이터 사용")
                result = actual_profit.copy()
                result['source'] = 'enhanced_trade_fills'
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
    
    async def get_api_connection_status(self) -> Dict:
        """🔥🔥🔥 API 연결 상태 조회"""
        return {
            'healthy': self.api_connection_healthy,
            'consecutive_failures': self.consecutive_failures,
            'last_successful_call': self.last_successful_call.isoformat(),
            'api_keys_validated': self.api_keys_validated,
            'max_failures_threshold': self.max_consecutive_failures
        }
    
    async def reset_connection_status(self):
        """🔥🔥🔥 연결 상태 리셋"""
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
        logger.info("비트겟 API 연결 상태 리셋 완료")
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
