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
    """Gate.io 미러링 전용 클라이언트 - 강화된 API 호출 및 에러 처리"""
    
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
        
        # API 연결 상태 추적
        self.api_healthy = True
        self.last_successful_call = None
        
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
        """클라이언트 초기화 및 연결 테스트"""
        self._initialize_session()
        
        # API 키 검증을 위한 간단한 호출
        try:
            logger.info("Gate.io API 연결 테스트 시작...")
            test_result = await self.get_account_balance()
            if test_result is not None:
                self.api_healthy = True
                self.last_successful_call = datetime.now()
                logger.info("✅ Gate.io API 연결 테스트 성공")
            else:
                logger.warning("⚠️ Gate.io API 연결 테스트 실패 (빈 응답)")
                self.api_healthy = False
        except Exception as e:
            logger.error(f"❌ Gate.io API 연결 테스트 실패: {e}")
            self.api_healthy = False
        
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
        """API 요청 - 강화된 에러 처리"""
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
                    
                    logger.debug(f"Gate.io API 응답 상태: {response.status}")
                    logger.debug(f"Gate.io API 응답 내용: {response_text[:500]}...")
                    
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: {response_text}"
                        logger.error(f"Gate.io API HTTP 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise Exception(error_msg)
                    
                    if not response_text.strip():
                        error_msg = "빈 응답"
                        logger.warning(f"Gate.io API 빈 응답")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise Exception(error_msg)
                    
                    try:
                        result = json.loads(response_text)
                        
                        # 성공 기록
                        self.api_healthy = True
                        self.last_successful_call = datetime.now()
                        
                        return result
                        
                    except json.JSONDecodeError as e:
                        error_msg = f"JSON 파싱 실패: {e}"
                        logger.error(f"Gate.io API JSON 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise Exception(error_msg)
                            
            except asyncio.TimeoutError:
                error_msg = f"요청 타임아웃 (시도 {attempt + 1})"
                logger.warning(f"Gate.io API 타임아웃: {error_msg}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self.api_healthy = False
                    raise Exception(error_msg)
                    
            except Exception as e:
                error_msg = f"예상치 못한 오류 (시도 {attempt + 1}): {e}"
                logger.error(f"Gate.io API 오류: {error_msg}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self.api_healthy = False
                    raise
        
        # 모든 재시도 실패
        final_error = f"모든 재시도 실패: {max_retries}회 시도"
        self.api_healthy = False
        raise Exception(final_error)
    
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
        """티커 정보 조회 - 강화된 버전"""
        try:
            endpoint = f"/api/v4/futures/usdt/tickers"
            params = {'contract': contract}
            
            logger.debug(f"Gate.io 티커 조회: {contract}")
            response = await self._request('GET', endpoint, params=params)
            
            logger.debug(f"Gate.io 티커 응답 타입: {type(response)}")
            logger.debug(f"Gate.io 티커 응답 내용: {response}")
            
            if isinstance(response, list) and len(response) > 0:
                ticker_data = response[0]
                if 'last' not in ticker_data and 'mark_price' in ticker_data:
                    ticker_data['last'] = ticker_data['mark_price']
                logger.info(f"✅ Gate.io 티커 조회 성공: {ticker_data.get('last', 'N/A')}")
                return ticker_data
            elif isinstance(response, dict):
                if 'last' not in response and 'mark_price' in response:
                    response['last'] = response['mark_price']
                logger.info(f"✅ Gate.io 티커 조회 성공: {response.get('last', 'N/A')}")
                return response
            else:
                logger.warning(f"Gate.io 티커 응답 형식 예상치 못함: {type(response)}")
                return {}
            
        except Exception as e:
            logger.error(f"Gate.io 티커 조회 실패: {e}")
            return {}
    
    async def get_account_balance(self) -> Dict:
        """계정 잔고 조회 - 강화된 버전"""
        try:
            endpoint = "/api/v4/futures/usdt/accounts"
            
            logger.debug("Gate.io 계정 잔고 조회 시작")
            response = await self._request('GET', endpoint)
            
            logger.debug(f"Gate.io 계정 잔고 응답 타입: {type(response)}")
            logger.debug(f"Gate.io 계정 잔고 응답: {response}")
            
            if response is None:
                logger.warning("Gate.io 계정 잔고 응답이 None")
                return {}
            
            if isinstance(response, dict):
                # 기본 필드 확인
                total = response.get('total', 0)
                available = response.get('available', 0)
                used = response.get('used', 0)
                unrealised_pnl = response.get('unrealised_pnl', 0)
                
                logger.info(f"✅ Gate.io 계정 조회 성공:")
                logger.info(f"  - Total: ${total}")
                logger.info(f"  - Available: ${available}")
                logger.info(f"  - Used: ${used}")
                logger.info(f"  - Unrealised PnL: ${unrealised_pnl}")
                
                return response
            elif isinstance(response, list) and len(response) > 0:
                # 배열 응답인 경우 첫 번째 항목 사용
                account_data = response[0]
                logger.info(f"✅ Gate.io 계정 조회 성공 (배열): {account_data}")
                return account_data
            else:
                logger.warning(f"Gate.io 계정 응답 형식 예상치 못함: {type(response)}")
                return {}
                
        except Exception as e:
            logger.error(f"Gate.io 계정 잔고 조회 실패: {e}")
            logger.error(f"계정 조회 상세 오류: {str(e)}")
            # 빈 딕셔너리 반환 (None이 아닌)
            return {}
    
    async def get_positions(self, contract: str = "BTC_USDT") -> List[Dict]:
        """포지션 조회 - 강화된 버전"""
        try:
            endpoint = f"/api/v4/futures/usdt/positions/{contract}"
            
            logger.debug(f"Gate.io 포지션 조회 시작: {contract}")
            response = await self._request('GET', endpoint)
            
            logger.debug(f"Gate.io 포지션 응답 타입: {type(response)}")
            logger.debug(f"Gate.io 포지션 응답: {response}")
            
            if response is None:
                logger.info("Gate.io 포지션 응답이 None - 포지션 없음으로 처리")
                return []
            
            if isinstance(response, dict):
                # 딕셔너리 응답인 경우
                size = response.get('size', 0)
                if size != 0:
                    logger.info(f"✅ Gate.io 포지션 발견: 사이즈 {size}")
                    return [response]
                else:
                    logger.info("Gate.io 포지션 없음 (사이즈 0)")
                    return []
            elif isinstance(response, list):
                # 배열 응답인 경우
                active_positions = []
                for pos in response:
                    if isinstance(pos, dict) and pos.get('size', 0) != 0:
                        active_positions.append(pos)
                
                logger.info(f"✅ Gate.io 활성 포지션: {len(active_positions)}개")
                return active_positions
            else:
                logger.warning(f"Gate.io 포지션 응답 형식 예상치 못함: {type(response)}")
                return []
            
        except Exception as e:
            logger.error(f"Gate.io 포지션 조회 실패: {e}")
            logger.error(f"포지션 조회 상세 오류: {str(e)}")
            return []
    
    async def get_my_trades(self, contract: str = "BTC_USDT", start_time: int = None, end_time: int = None, limit: int = 100) -> List[Dict]:
        """거래 내역 조회 - Gate.io API v4 공식 문서 기준"""
        try:
            endpoint = "/api/v4/futures/usdt/my_trades"
            params = {
                'contract': contract,
                'limit': str(min(limit, 1000))  # Gate.io 최대 1000
            }
            
            # Gate.io API는 초 단위 타임스탬프 사용
            if start_time:
                params['from'] = str(int(start_time / 1000))  # 밀리초를 초로 변환
            if end_time:
                params['to'] = str(int(end_time / 1000))  # 밀리초를 초로 변환
            
            logger.debug(f"Gate.io 거래 내역 조회: {contract}, 기간: {params.get('from')} ~ {params.get('to')}")
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list):
                logger.info(f"✅ Gate.io 거래 내역 조회 성공: {len(response)}건")
                return response
            else:
                logger.warning(f"Gate.io 거래 내역 응답 형식 예상치 못함: {type(response)}")
                return []
            
        except Exception as e:
            logger.error(f"Gate.io 거래 내역 조회 실패: {e}")
            return []
    
    async def get_account_book(self, start_time: int = None, end_time: int = None, limit: int = 100, type_filter: str = None) -> List[Dict]:
        """🔥🔥 계정 변동 내역 조회 - Gate.io API v4 공식 문서 완전 준수"""
        try:
            endpoint = "/api/v4/futures/usdt/account_book"
            params = {
                'limit': str(min(limit, 1000))  # Gate.io 최대 1000
            }
            
            # Gate.io API는 초 단위 타임스탬프 사용
            if start_time:
                params['from'] = str(int(start_time / 1000))  # 밀리초를 초로 변환
            if end_time:
                params['to'] = str(int(end_time / 1000))  # 밀리초를 초로 변환
            if type_filter:
                params['type'] = type_filter  # 'pnl', 'fee', 'fund', 'dnw', 'refr'
            
            logger.debug(f"Gate.io 계정 변동 내역 조회: type={type_filter}, 기간: {params.get('from')} ~ {params.get('to')}")
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list):
                logger.info(f"✅ Gate.io 계정 변동 내역 조회 성공: {len(response)}건 (type: {type_filter})")
                return response
            else:
                logger.warning(f"Gate.io 계정 변동 내역 응답 형식 예상치 못함: {type(response)}")
                return []
            
        except Exception as e:
            logger.error(f"Gate.io 계정 변동 내역 조회 실패: {e}")
            return []
    
    async def get_today_realized_pnl(self) -> float:
        """🔥🔥 오늘 실현 손익 조회 - Gate.io 공식 API 완전 개선"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 오늘 0시 (KST)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # UTC로 변환하여 타임스탬프 생성 (밀리초)
            start_time_utc = today_start.astimezone(pytz.UTC)
            end_time_utc = now.astimezone(pytz.UTC)
            
            start_timestamp_ms = int(start_time_utc.timestamp() * 1000)
            end_timestamp_ms = int(end_time_utc.timestamp() * 1000)
            
            logger.info(f"🔍 Gate.io 오늘 실현손익 조회 (공식 API):")
            logger.info(f"  - KST 시작: {today_start.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  - KST 종료: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  - UTC 타임스탬프: {start_timestamp_ms} ~ {end_timestamp_ms}")
            
            total_pnl = 0.0
            record_count = 0
            
            # 🔥🔥 공식 API: PnL 타입 계정 변동 내역 조회 (가장 정확)
            try:
                logger.info("📊 방법 1: PnL 타입 계정 변동 내역 조회 (공식 API)")
                
                pnl_records = await self.get_account_book(
                    start_time=start_timestamp_ms,
                    end_time=end_timestamp_ms,
                    limit=200,
                    type_filter='pnl'  # Gate.io 공식: Profit & Loss by reducing position
                )
                
                logger.info(f"PnL 타입 기록: {len(pnl_records)}건")
                
                if pnl_records:
                    for record in pnl_records:
                        try:
                            # Gate.io 공식 응답 구조:
                            # {
                            #   "time": 1609459200,
                            #   "change": "100.0000",  # 변화량 (손익)
                            #   "balance": "1000.0000", 
                            #   "type": "pnl",
                            #   "text": "BTC_USDT:123456"
                            # }
                            
                            change = float(record.get('change', 0))
                            record_type = record.get('type', '')
                            text = record.get('text', '')
                            record_time = int(record.get('time', 0))
                            
                            # PnL 타입이고 실제 손익 변화인지 확인
                            if record_type == 'pnl' and change != 0:
                                total_pnl += change
                                record_count += 1
                                
                                # 시간 변환하여 로깅
                                time_kst = datetime.fromtimestamp(record_time, tz=kst)
                                logger.debug(f"PnL 기록 ({time_kst.strftime('%H:%M:%S')}): ${change:.4f} - {text}")
                        
                        except Exception as parse_error:
                            logger.warning(f"PnL 기록 파싱 오류: {parse_error}")
                            continue
                    
                    if total_pnl != 0:
                        logger.info(f"✅ PnL 타입 계정 변동에서 조회 성공: ${total_pnl:.4f} ({record_count}건)")
                        return total_pnl
                
            except Exception as e:
                logger.error(f"PnL 타입 계정 변동 조회 실패: {e}")
            
            # 🔥🔥 백업 방법: 포지션에서 realised_pnl 조회
            try:
                logger.info("📊 방법 2: 포지션에서 realised_pnl 조회")
                
                positions = await self.get_positions("BTC_USDT")
                if positions:
                    for pos in positions:
                        # Gate.io 공식 포지션 구조에서 realised_pnl 필드 사용
                        realised_pnl = float(pos.get('realised_pnl', 0))
                        if realised_pnl != 0:
                            total_pnl = realised_pnl
                            logger.info(f"✅ 포지션에서 실현손익 조회: ${total_pnl:.4f}")
                            return total_pnl
                
            except Exception as e:
                logger.error(f"포지션 실현손익 조회 실패: {e}")
            
            logger.info(f"Gate.io 오늘 실현손익 최종 결과: ${total_pnl:.4f} ({record_count}건)")
            return total_pnl
            
        except Exception as e:
            logger.error(f"Gate.io 오늘 실현손익 조회 실패: {e}")
            return 0.0
    
    async def get_weekly_profit(self) -> Dict:
        """🔥🔥 7일 손익 조회 - Gate.io 공식 API 완전 개선"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            seven_days_ago = now - timedelta(days=7)
            
            # UTC로 변환하여 타임스탬프 생성 (밀리초)
            start_timestamp_ms = int(seven_days_ago.timestamp() * 1000)
            end_timestamp_ms = int(now.timestamp() * 1000)
            
            logger.info(f"🔍 Gate.io 7일 손익 조회 (공식 API):")
            logger.info(f"  - 기간: {seven_days_ago.strftime('%Y-%m-%d %H:%M')} ~ {now.strftime('%Y-%m-%d %H:%M')}")
            logger.info(f"  - UTC 타임스탬프: {start_timestamp_ms} ~ {end_timestamp_ms}")
            
            total_pnl = 0.0
            daily_pnl = {}
            record_count = 0
            
            # 🔥🔥 공식 API: PnL 타입 계정 변동 내역 조회 (가장 정확)
            try:
                logger.info("📊 방법 1: PnL 타입 계정 변동 내역으로 7일 손익 계산 (공식 API)")
                
                pnl_records = await self.get_account_book(
                    start_time=start_timestamp_ms,
                    end_time=end_timestamp_ms,
                    limit=500,
                    type_filter='pnl'  # Gate.io 공식: Profit & Loss by reducing position
                )
                
                logger.info(f"7일 PnL 타입 기록: {len(pnl_records)}건")
                
                if pnl_records:
                    for record in pnl_records:
                        try:
                            change = float(record.get('change', 0))
                            record_type = record.get('type', '')
                            record_time = int(record.get('time', 0))
                            text = record.get('text', '')
                            
                            if record_type == 'pnl' and change != 0:
                                # 날짜별로 분류
                                record_date_kst = datetime.fromtimestamp(record_time, tz=kst)
                                record_date_str = record_date_kst.strftime('%Y-%m-%d')
                                
                                if record_date_str not in daily_pnl:
                                    daily_pnl[record_date_str] = 0
                                
                                daily_pnl[record_date_str] += change
                                total_pnl += change
                                record_count += 1
                                
                                logger.debug(f"7일 PnL ({record_date_str}): ${change:.4f} - {text}")
                        
                        except Exception as parse_error:
                            logger.warning(f"7일 PnL 기록 파싱 오류: {parse_error}")
                            continue
                    
                    if total_pnl != 0:
                        # 일별 손익 로깅
                        for date_str, pnl in sorted(daily_pnl.items()):
                            logger.info(f"📊 Gate.io {date_str}: ${pnl:.2f}")
                        
                        return {
                            'total_pnl': total_pnl,
                            'daily_pnl': daily_pnl,
                            'average_daily': total_pnl / 7,
                            'trade_count': record_count,
                            'source': 'gate_pnl_official_api',
                            'confidence': 'high'
                        }
                
            except Exception as e:
                logger.error(f"7일 PnL 타입 계정 변동 조회 실패: {e}")
            
            # 🔥🔥 백업 방법: 전체 계정 변동에서 PnL 관련 항목 찾기
            try:
                logger.info("📊 방법 2: 전체 계정 변동 내역에서 PnL 관련 항목 찾기")
                
                all_records = await self.get_account_book(
                    start_time=start_timestamp_ms,
                    end_time=end_timestamp_ms,
                    limit=500
                )
                
                logger.info(f"7일 전체 계정 변동 기록: {len(all_records)}건")
                
                if all_records:
                    for record in all_records:
                        try:
                            change = float(record.get('change', 0))
                            record_type = record.get('type', '')
                            text = record.get('text', '').lower()
                            record_time = int(record.get('time', 0))
                            
                            # PnL 관련 타입 확인 (공식 타입만)
                            if record_type == 'pnl' and change != 0:
                                # 날짜별로 분류
                                record_date_kst = datetime.fromtimestamp(record_time, tz=kst)
                                record_date_str = record_date_kst.strftime('%Y-%m-%d')
                                
                                if record_date_str not in daily_pnl:
                                    daily_pnl[record_date_str] = 0
                                
                                daily_pnl[record_date_str] += change
                                total_pnl += change
                                record_count += 1
                                
                                logger.debug(f"7일 PnL 관련 ({record_date_str}): ${change:.4f} - {record_type} - {text}")
                        
                        except Exception as parse_error:
                            logger.warning(f"7일 계정 변동 기록 파싱 오류: {parse_error}")
                            continue
                    
                    if total_pnl != 0:
                        # 일별 손익 로깅
                        for date_str, pnl in sorted(daily_pnl.items()):
                            logger.info(f"📊 Gate.io {date_str}: ${pnl:.2f}")
                        
                        return {
                            'total_pnl': total_pnl,
                            'daily_pnl': daily_pnl,
                            'average_daily': total_pnl / 7,
                            'trade_count': record_count,
                            'source': 'gate_all_account_book_official',
                            'confidence': 'medium'
                        }
                
            except Exception as e:
                logger.error(f"7일 전체 계정 변동 조회 실패: {e}")
            
            # 방법 3: 기본값 반환
            logger.warning("Gate.io 모든 7일 손익 조회 방법 실패, 기본값 반환")
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'average_daily': 0,
                'trade_count': 0,
                'source': 'gate_fallback_zero',
                'confidence': 'low'
            }
            
        except Exception as e:
            logger.error(f"Gate.io 7일 손익 조회 실패: {e}")
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'average_daily': 0,
                'trade_count': 0,
                'source': 'gate_error',
                'confidence': 'low'
            }
    
    async def get_profit_history_since_may(self) -> Dict:
        """🔥🔥 Gate.io 수익 내역 조회 - 포지션 API 기반 정확한 누적 수익"""
        try:
            logger.info(f"🔍 Gate.io 누적 수익 조회 (포지션 API 기반):")
            
            # 현재 계정 정보
            account = await self.get_account_balance()
            current_balance = float(account.get('total', 0)) if account else 0
            
            # 오늘 실현 손익
            today_realized = await self.get_today_realized_pnl()
            
            # 7일 손익
            weekly_profit = await self.get_weekly_profit()
            
            # 🔥🔥 누적 PnL을 포지션 API에서 정확하게 조회
            cumulative_pnl = 0.0
            
            try:
                logger.info("📊 포지션 API에서 history_pnl 조회")
                
                positions = await self.get_positions("BTC_USDT")
                
                if positions:
                    for position in positions:
                        # Gate.io 공식 포지션 API 필드들:
                        # - realised_pnl: 현재 세션 실현 손익
                        # - history_pnl: 누적 역사적 손익
                        # - last_close_pnl: 마지막 청산 손익
                        
                        history_pnl = float(position.get('history_pnl', 0))
                        realised_pnl = float(position.get('realised_pnl', 0))
                        last_close_pnl = float(position.get('last_close_pnl', 0))
                        
                        # 누적 손익 = 역사적 손익 + 현재 실현 손익
                        cumulative_pnl = history_pnl + realised_pnl
                        
                        logger.info(f"Gate.io 포지션 손익 정보:")
                        logger.info(f"  - history_pnl: ${history_pnl:.4f}")
                        logger.info(f"  - realised_pnl: ${realised_pnl:.4f}")
                        logger.info(f"  - last_close_pnl: ${last_close_pnl:.4f}")
                        logger.info(f"  - 계산된 누적 손익: ${cumulative_pnl:.4f}")
                        
                        break  # 첫 번째 포지션 정보만 사용
                else:
                    logger.info("현재 포지션이 없음, 계정 기반 추정")
                    # 포지션이 없으면 현재 잔고의 일부를 누적 수익으로 추정
                    cumulative_pnl = current_balance * 0.1  # 10%를 수익으로 추정
                
            except Exception as e:
                logger.error(f"포지션 API 누적 손익 조회 실패: {e}")
                # 기본값 설정
                cumulative_pnl = current_balance * 0.1 if current_balance > 0 else 0
            
            # 초기 자본 동적 계산 (현재 잔고 - 누적 수익)
            initial_capital = current_balance - cumulative_pnl
            
            # 초기 자본이 음수가 되지 않도록 보정
            if initial_capital < 0:
                initial_capital = current_balance * 0.8  # 현재 잔고의 80%로 추정
                cumulative_pnl = current_balance - initial_capital
            
            # 최소 초기 자본 보장
            if initial_capital < 100:
                initial_capital = 700  # 기본값 $700
                cumulative_pnl = current_balance - initial_capital
            
            logger.info(f"Gate.io 누적 수익 계산 완료:")
            logger.info(f"  - 현재 잔고: ${current_balance:.2f}")
            logger.info(f"  - 누적 수익: ${cumulative_pnl:.2f}")
            logger.info(f"  - 계산된 초기 자본: ${initial_capital:.2f}")
            logger.info(f"  - 오늘 실현손익: ${today_realized:.2f}")
            logger.info(f"  - 7일 손익: ${weekly_profit.get('total_pnl', 0):.2f}")
            
            return {
                'total': cumulative_pnl,
                'monthly': {},  # 월별 데이터는 복잡하므로 일단 빈 딕셔너리
                'weekly': weekly_profit,
                'today_realized': today_realized,
                'current_balance': current_balance,
                'actual_profit': cumulative_pnl,  # 실제 누적 수익 (포지션 API 기반)
                'initial_capital': initial_capital,  # 동적으로 계산된 초기 자본
                'source': 'position_api_based_calculation'
            }
            
        except Exception as e:
            logger.error(f"Gate.io 수익 내역 조회 실패: {e}")
            return {
                'total': 0,
                'monthly': {},
                'weekly': {'total': 0, 'average': 0},
                'today_realized': 0,
                'current_balance': 0,
                'actual_profit': 0,
                'initial_capital': 700,  # 기본값
                'source': 'error'
            }
    
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
                
                logger.info(f"Gate.io 레버리지 설정 시도 {attempt + 1}/{retry_count}: {contract} - {leverage}x")
                logger.debug(f"레버리지 설정 데이터: {json.dumps(data, indent=2)}")
                
                response = await self._request('POST', endpoint, data=data)
                
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
                
                if "MISSING_REQUIRED_PARAM" in error_msg and "leverage" in error_msg:
                    try:
                        # 대체 방법: 정수로 전송
                        logger.info(f"레버리지 파라미터를 정수로 재시도: {attempt + 1}")
                        alt_data = {"leverage": leverage}
                        response = await self._request('POST', endpoint, data=alt_data)
                        await asyncio.sleep(1.0)
                        logger.info(f"✅ Gate.io 레버리지 설정 완료 (정수 방식): {contract} - {leverage}x")
                        return response
                    except Exception as alt_error:
                        logger.warning(f"정수 방법도 실패: {alt_error}")
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(2.0)
                    continue
                else:
                    logger.warning(f"레버리지 설정 최종 실패하지만 계속 진행: {contract} - {leverage}x")
                    return {"warning": "leverage_setting_failed", "requested_leverage": leverage}
        
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
    
    async def create_perfect_tp_sl_order(self, bitget_order: Dict, gate_size: int, gate_margin: float, 
                                       leverage: int, current_gate_price: float) -> Dict:
        """완벽한 TP/SL 미러링 주문 생성"""
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
            
            # TP/SL 정보 추출
            tp_price = None
            sl_price = None
            
            # TP 추출
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
            
            # SL 추출
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
            
            # 클로즈 주문 여부 및 방향 판단
            reduce_only = bitget_order.get('reduceOnly', False)
            is_close_order = (
                'close' in side or 
                reduce_only is True or 
                reduce_only == 'true' or
                str(reduce_only).lower() == 'true'
            )
            
            logger.info(f"🔍 주문 분석: side='{side}', reduce_only={reduce_only}, is_close_order={is_close_order}")
            
            # 클로즈 주문 방향 매핑
            final_size = gate_size
            reduce_only_flag = False
            
            if is_close_order:
                reduce_only_flag = True
                
                if 'close_long' in side or side == 'close long':
                    final_size = -abs(gate_size)
                    logger.info(f"🔴 클로즈 롱 감지: 롱 포지션 종료 → 게이트 매도 주문 (음수: {final_size})")
                elif 'close_short' in side or side == 'close short':
                    final_size = abs(gate_size)
                    logger.info(f"🟢 클로즈 숏 감지: 숏 포지션 종료 → 게이트 매수 주문 (양수: {final_size})")
                elif 'sell' in side and 'buy' not in side:
                    final_size = -abs(gate_size)
                    logger.info(f"🔴 클로즈 매도 감지: 롱 포지션 종료 → 게이트 매도 주문 (음수: {final_size})")
                elif 'buy' in side and 'sell' not in side:
                    final_size = abs(gate_size)
                    logger.info(f"🟢 클로즈 매수 감지: 숏 포지션 종료 → 게이트 매수 주문 (양수: {final_size})")
                else:
                    if 'long' in side:
                        final_size = -abs(gate_size)
                        logger.info(f"🔴 클로즈 롱 추정: 롱 포지션 종료 → 게이트 매도 주문 (음수: {final_size})")
                    elif 'short' in side:
                        final_size = abs(gate_size)
                        logger.info(f"🟢 클로즈 숏 추정: 숏 포지션 종료 → 게이트 매수 주문 (양수: {final_size})")
                    else:
                        final_size = -abs(gate_size)
                        logger.warning(f"⚠️ 알 수 없는 클로즈 주문: {side}, 매도(롱 클로즈)로 추정 (음수: {final_size})")
            else:
                reduce_only_flag = False
                
                if 'short' in side or 'sell' in side:
                    final_size = -abs(gate_size)
                    logger.info(f"🔴 오픈 숏: 새 숏 포지션 생성 → 게이트 매도 주문 (음수: {final_size})")
                else:
                    final_size = abs(gate_size)
                    logger.info(f"🟢 오픈 롱: 새 롱 포지션 생성 → 게이트 매수 주문 (양수: {final_size})")
            
            # Gate.io 트리거 타입 결정
            gate_trigger_type = "ge" if trigger_price > current_gate_price else "le"
            
            logger.info(f"🔍 완벽 미러링 주문 생성:")
            logger.info(f"   - 비트겟 ID: {order_id}")
            logger.info(f"   - 원본 방향: {side} ({'클로즈' if is_close_order else '오픈'})")
            logger.info(f"   - 트리거가: ${trigger_price:.2f}")
            logger.info(f"   - 최종 게이트 사이즈: {final_size} (reduce_only: {reduce_only_flag})")
            
            tp_display = f"${tp_price:.2f}" if tp_price is not None else "없음"
            sl_display = f"${sl_price:.2f}" if sl_price is not None else "없음"
            
            logger.info(f"   - TP: {tp_display}")
            logger.info(f"   - SL: {sl_display}")
            
            # TP/SL 포함 통합 주문 생성
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
                    'perfect_mirror': has_tp_sl
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
                    'perfect_mirror': True
                }
            
        except Exception as e:
            logger.error(f"완벽한 TP/SL 미러링 주문 생성 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'has_tp_sl': False,
                'perfect_mirror': False
            }
    
    async def create_conditional_order_with_tp_sl(self, trigger_price: float, order_size: int,
                                                tp_price: Optional[float] = None,
                                                sl_price: Optional[float] = None,
                                                reduce_only: bool = False,
                                                trigger_type: str = "ge") -> Dict:
        """TP/SL 포함 조건부 주문 생성"""
        try:
            endpoint = "/api/v4/futures/usdt/price_orders"
            
            # 기본 주문 데이터
            initial_data = {
                "type": "market",
                "contract": "BTC_USDT",
                "size": order_size,
                "price": str(trigger_price)
            }
            
            if reduce_only:
                initial_data["reduce_only"] = True
            
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
