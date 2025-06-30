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
        
        # TP/SL 설정 상수
        self.TP_SL_TIMEOUT = 10
        self.MAX_TP_SL_RETRIES = 3
        
        # API 연결 상태 추적
        self.api_healthy = True
        self.last_successful_call = None
        
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
            logger.info("🔍 Gate.io API 연결 테스트 시작...")
            
            # 계정 잔고 조회 테스트
            test_result = await self.get_account_balance()
            if test_result is not None and test_result.get('total'):
                self.api_healthy = True
                self.last_successful_call = datetime.now()
                logger.info("✅ Gate.io 계정 조회 성공")
                
                # 거래 내역 조회 테스트 - 더 넓은 범위로 테스트
                try:
                    now = datetime.now()
                    thirty_days_ago = now - timedelta(days=30)
                    start_ts = int(thirty_days_ago.timestamp())
                    end_ts = int(now.timestamp())
                    
                    trades = await self.get_my_trades(
                        contract="BTC_USDT",
                        start_time=start_ts,
                        end_time=end_ts,
                        limit=50
                    )
                    
                    logger.info(f"✅ Gate.io 거래 내역 조회 테스트: {len(trades)}건 (30일간)")
                    
                except Exception as trade_error:
                    logger.warning(f"⚠️ Gate.io 거래 내역 조회 테스트 실패: {trade_error}")
                
            else:
                logger.warning("⚠️ Gate.io API 연결 테스트 실패 (빈 응답)")
                self.api_healthy = False
                
        except Exception as e:
            logger.error(f"❌ Gate.io API 연결 테스트 실패: {e}")
            self.api_healthy = False
        
        logger.info("Gate.io 미러링 클라이언트 초기화 완료")
    
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
                        error_msg = f"HTTP {response.status}: {response_text[:200]}"
                        logger.error(f"Gate.io API HTTP 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        else:
                            return {}
                    
                    if not response_text.strip():
                        logger.warning(f"Gate.io API 빈 응답")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        else:
                            return {}
                    
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
                            await asyncio.sleep(1)
                            continue
                        else:
                            return {}
                            
            except asyncio.TimeoutError:
                logger.warning(f"Gate.io API 타임아웃 (시도 {attempt + 1})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    self.api_healthy = False
                    return {}
                    
            except Exception as e:
                logger.error(f"Gate.io API 오류 (시도 {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    self.api_healthy = False
                    return {}
        
        self.api_healthy = False
        return {}
    
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
        try:
            endpoint = "/api/v4/futures/usdt/accounts"
            
            response = await self._request('GET', endpoint)
            
            if response is None:
                logger.warning("Gate.io 계정 잔고 응답이 None")
                return {}
            
            # 필수 필드 검증 및 기본값 설정
            if isinstance(response, dict):
                # 필수 필드가 없으면 기본값으로 설정
                required_fields = ['total', 'available', 'unrealised_pnl']
                for field in required_fields:
                    if field not in response:
                        response[field] = '0'
                
                # 데이터 타입 검증
                try:
                    total = float(response.get('total', 0))
                    available = float(response.get('available', 0))
                    unrealized_pnl = float(response.get('unrealised_pnl', 0))
                    
                    logger.info(f"✅ Gate.io 계정 정보:")
                    logger.info(f"  - 총 자산: ${total:.2f}")
                    logger.info(f"  - 가용 자산: ${available:.2f}")
                    logger.info(f"  - 미실현 손익: ${unrealized_pnl:.2f}")
                    
                    return response
                    
                except (ValueError, TypeError) as e:
                    logger.error(f"Gate.io 계정 데이터 변환 실패: {e}")
                    return {}
                    
            elif isinstance(response, list) and len(response) > 0:
                return response[0]
            else:
                logger.warning(f"Gate.io 계정 응답 형식 예상치 못함: {type(response)}")
                return {}
                
        except Exception as e:
            logger.error(f"Gate.io 계정 잔고 조회 실패: {e}")
            return {}
    
    async def get_positions(self, contract: str = "BTC_USDT") -> List[Dict]:
        try:
            endpoint = f"/api/v4/futures/usdt/positions/{contract}"
            
            response = await self._request('GET', endpoint)
            
            if response is None:
                logger.info("Gate.io 포지션 응답이 None - 포지션 없음으로 처리")
                return []
            
            if isinstance(response, dict):
                size = float(response.get('size', 0))
                if size != 0:
                    logger.info(f"✅ Gate.io 포지션 발견: 사이즈 {size}")
                    return [response]
                else:
                    logger.info("Gate.io 포지션 없음 (사이즈 0)")
                    return []
            elif isinstance(response, list):
                active_positions = []
                for pos in response:
                    if isinstance(pos, dict) and float(pos.get('size', 0)) != 0:
                        active_positions.append(pos)
                
                logger.info(f"✅ Gate.io 활성 포지션: {len(active_positions)}개")
                return active_positions
            else:
                logger.warning(f"Gate.io 포지션 응답 형식 예상치 못함: {type(response)}")
                return []
            
        except Exception as e:
            logger.error(f"Gate.io 포지션 조회 실패: {e}")
            return []

    async def get_account_book(self, contract: str = "BTC_USDT", start_time: int = None, end_time: int = None, limit: int = 1000) -> List[Dict]:
        """계정 변동 내역 조회 - 새로운 PnL 계산 방식"""
        try:
            endpoint = "/api/v4/futures/usdt/account_book"
            
            params = {
                'limit': str(min(limit, 1000))
            }
            
            if start_time is not None:
                start_sec = int(start_time / 1000) if start_time > 10000000000 else int(start_time)
                params['from'] = str(start_sec)
                
            if end_time is not None:
                end_sec = int(end_time / 1000) if end_time > 10000000000 else int(end_time)
                params['to'] = str(end_sec)
            
            logger.info(f"🔍 Gate.io 계정 변동 내역 조회:")
            logger.info(f"  - 시작시간: {params.get('from', 'None')}")
            logger.info(f"  - 종료시간: {params.get('to', 'None')}")
            
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list):
                logger.info(f"✅ Gate.io 계정 변동 내역: {len(response)}건")
                return response
            else:
                logger.warning(f"Gate.io 계정 변동 내역 응답 형식 예상치 못함: {type(response)}")
                return []
                
        except Exception as e:
            logger.error(f"Gate.io 계정 변동 내역 조회 실패: {e}")
            return []

    async def get_funding_book(self, contract: str = "BTC_USDT", start_time: int = None, end_time: int = None, limit: int = 1000) -> List[Dict]:
        """펀딩비 내역 조회"""
        try:
            endpoint = "/api/v4/futures/usdt/funding_book"
            
            params = {
                'contract': contract,
                'limit': str(min(limit, 1000))
            }
            
            if start_time is not None:
                start_sec = int(start_time / 1000) if start_time > 10000000000 else int(start_time)
                params['from'] = str(start_sec)
                
            if end_time is not None:
                end_sec = int(end_time / 1000) if end_time > 10000000000 else int(end_time)
                params['to'] = str(end_sec)
            
            logger.info(f"🔍 Gate.io 펀딩비 내역 조회: {contract}")
            
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list):
                logger.info(f"✅ Gate.io 펀딩비 내역: {len(response)}건")
                return response
            else:
                logger.warning(f"Gate.io 펀딩비 내역 응답 형식 예상치 못함: {type(response)}")
                return []
                
        except Exception as e:
            logger.error(f"Gate.io 펀딩비 내역 조회 실패: {e}")
            return []
    
    async def get_my_trades(self, contract: str = "BTC_USDT", start_time: int = None, end_time: int = None, limit: int = 1000) -> List[Dict]:
        try:
            endpoint = "/api/v4/futures/usdt/my_trades"
            
            # 기본 파라미터 설정
            params = {
                'contract': contract,
                'limit': str(min(limit, 1000))
            }
            
            # 시간 파라미터 처리 - Gate.io는 초 단위 사용
            if start_time is not None:
                if start_time > 10000000000:  # 밀리초 형태면 초로 변환
                    start_time_sec = int(start_time / 1000)
                else:
                    start_time_sec = int(start_time)
                params['from'] = str(start_time_sec)
                
            if end_time is not None:
                if end_time > 10000000000:  # 밀리초 형태면 초로 변환
                    end_time_sec = int(end_time / 1000)
                else:
                    end_time_sec = int(end_time)
                params['to'] = str(end_time_sec)
            
            logger.info(f"🔍 Gate.io 거래 내역 조회 요청:")
            logger.info(f"  - 계약: {contract}")
            logger.info(f"  - 시작시간: {params.get('from', 'None')}")
            logger.info(f"  - 종료시간: {params.get('to', 'None')}")
            logger.info(f"  - 제한: {params['limit']}")
            
            # 재시도 로직 강화
            for attempt in range(3):
                try:
                    response = await self._request('GET', endpoint, params=params, max_retries=2)
                    
                    if isinstance(response, list):
                        logger.info(f"✅ Gate.io 거래 내역 조회 성공: {len(response)}건 (시도 {attempt + 1})")
                        
                        # 응답 데이터 구조 확인을 위한 상세 로깅
                        if len(response) > 0:
                            sample_trade = response[0]
                            logger.debug(f"샘플 거래 내역 구조: {list(sample_trade.keys())}")
                            
                            # 중요 필드 존재 여부 확인
                            important_fields = ['id', 'create_time', 'contract', 'size', 'price', 'fee', 'point']
                            existing_fields = [field for field in important_fields if field in sample_trade]
                            logger.debug(f"존재하는 중요 필드: {existing_fields}")
                        
                        return response
                    else:
                        logger.warning(f"Gate.io 거래 내역 응답 형식 예상치 못함 (시도 {attempt + 1}): {type(response)}")
                        if response:
                            logger.debug(f"응답 내용 샘플: {str(response)[:200]}")
                        
                        if attempt < 2:
                            await asyncio.sleep(1)
                            continue
                        else:
                            return []
                            
                except Exception as e:
                    logger.warning(f"Gate.io 거래 내역 조회 시도 {attempt + 1} 실패: {e}")
                    if attempt < 2:
                        await asyncio.sleep(1)
                        continue
                    else:
                        return []
            
            return []
            
        except Exception as e:
            logger.error(f"Gate.io 거래 내역 조회 실패: {e}")
            return []
    
    async def get_position_pnl_alternative_method(self, start_time: int, end_time: int, contract: str = "BTC_USDT") -> Dict:
        """계정 변동 내역을 통한 대안 PnL 계산"""
        try:
            logger.info(f"🔍 Gate.io 대안 PnL 계산 시작 (계정 변동 내역 기반):")
            
            # 시간 형식 통일
            if start_time > 10000000000:
                start_sec = int(start_time / 1000)
            else:
                start_sec = int(start_time)
                
            if end_time > 10000000000:
                end_sec = int(end_time / 1000)
            else:
                end_sec = int(end_time)
            
            logger.info(f"  - 시작: {datetime.fromtimestamp(start_sec).strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  - 종료: {datetime.fromtimestamp(end_sec).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 계정 변동 내역과 펀딩비 내역 병렬 조회
            book_task = self.get_account_book(contract, start_sec, end_sec, 1000)
            funding_task = self.get_funding_book(contract, start_sec, end_sec, 1000)
            
            try:
                account_book, funding_book = await asyncio.gather(book_task, funding_task, return_exceptions=True)
                
                if isinstance(account_book, Exception):
                    logger.warning(f"계정 변동 내역 조회 실패: {account_book}")
                    account_book = []
                    
                if isinstance(funding_book, Exception):
                    logger.warning(f"펀딩비 내역 조회 실패: {funding_book}")
                    funding_book = []
                
            except Exception as e:
                logger.error(f"계정 내역 병렬 조회 실패: {e}")
                account_book = []
                funding_book = []
            
            total_pnl = 0.0
            total_trading_fees = 0.0
            total_funding_fees = 0.0
            trade_count = 0
            
            # 계정 변동 내역에서 실현 손익과 수수료 추출
            for entry in account_book:
                try:
                    entry_type = entry.get('type', '').lower()
                    change = float(entry.get('change', 0))
                    
                    if change == 0:
                        continue
                    
                    # 실현 손익 (PnL, 정산)
                    if any(keyword in entry_type for keyword in ['pnl', 'settle', 'realize']):
                        total_pnl += change
                        trade_count += 1
                        logger.debug(f"실현 손익: ${change:.4f} (타입: {entry_type})")
                    
                    # 거래 수수료
                    elif any(keyword in entry_type for keyword in ['fee', 'commission']):
                        total_trading_fees += abs(change)
                        logger.debug(f"거래 수수료: ${abs(change):.4f} (타입: {entry_type})")
                    
                except Exception as entry_error:
                    logger.debug(f"계정 변동 항목 처리 오류: {entry_error}")
                    continue
            
            # 펀딩비 내역 처리
            for funding in funding_book:
                try:
                    funding_amount = float(funding.get('funding', 0))
                    if funding_amount != 0:
                        total_funding_fees += funding_amount
                        logger.debug(f"펀딩비: {funding_amount:+.4f}")
                        
                except Exception as funding_error:
                    logger.debug(f"펀딩비 항목 처리 오류: {funding_error}")
                    continue
            
            net_profit = total_pnl + total_funding_fees - total_trading_fees
            
            logger.info(f"✅ Gate.io 대안 PnL 계산 완료 (계정 변동 기반):")
            logger.info(f"  - 계정 변동 항목: {len(account_book)}건")
            logger.info(f"  - 펀딩비 항목: {len(funding_book)}건")
            logger.info(f"  - 실현 손익: ${total_pnl:.4f}")
            logger.info(f"  - 거래 수수료: -${total_trading_fees:.4f}")
            logger.info(f"  - 펀딩비: {total_funding_fees:+.4f}")
            logger.info(f"  - 순 수익: ${net_profit:.4f}")
            
            return {
                'position_pnl': total_pnl,
                'trading_fees': total_trading_fees,
                'funding_fees': total_funding_fees,
                'net_profit': net_profit,
                'trade_count': trade_count,
                'account_book_count': len(account_book),
                'funding_book_count': len(funding_book),
                'source': 'gate_account_book_alternative',
                'confidence': 'high' if trade_count > 0 else 'medium'
            }
            
        except Exception as e:
            logger.error(f"Gate.io 대안 PnL 계산 실패: {e}")
            return {
                'position_pnl': 0.0,
                'trading_fees': 0.0,
                'funding_fees': 0.0,
                'net_profit': 0.0,
                'trade_count': 0,
                'source': 'alternative_method_error',
                'confidence': 'low'
            }
    
    async def get_position_pnl_based_profit(self, start_time: int, end_time: int, contract: str = "BTC_USDT") -> Dict:
        try:
            logger.info(f"🔍 Gate.io Position PnL 기준 손익 계산 시작...")
            
            # 시간 형식 통일 (밀리초 -> 초)
            if start_time > 10000000000:
                start_sec = int(start_time / 1000)
            else:
                start_sec = int(start_time)
                
            if end_time > 10000000000:
                end_sec = int(end_time / 1000)
            else:
                end_sec = int(end_time)
            
            logger.info(f"  - 계약: {contract}")
            logger.info(f"  - 시작: {datetime.fromtimestamp(start_sec).strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  - 종료: {datetime.fromtimestamp(end_sec).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 여러 방식으로 거래 내역 조회 시도
            trades_all = []
            
            # 방법 1: my_trades API (기존)
            try:
                trades_v1 = await self.get_my_trades(
                    contract=contract,
                    start_time=start_sec,
                    end_time=end_sec,
                    limit=1000
                )
                if trades_v1:
                    logger.info(f"방법 1 (my_trades): {len(trades_v1)}건")
                    trades_all.extend(trades_v1)
            except Exception as e:
                logger.warning(f"방법 1 실패: {e}")
            
            # 방법 2: 계정 변동 내역 기반 (대안)
            if len(trades_all) == 0:
                try:
                    logger.info("방법 2 시도: 계정 변동 내역 기반 PnL 계산")
                    alternative_result = await self.get_position_pnl_alternative_method(
                        start_sec, end_sec, contract
                    )
                    
                    if alternative_result.get('trade_count', 0) > 0:
                        logger.info(f"✅ 대안 방법 성공: {alternative_result}")
                        return alternative_result
                        
                except Exception as e:
                    logger.warning(f"방법 2 실패: {e}")
            
            # 기존 trades 처리 로직
            logger.info(f"Gate.io 총 거래 내역: {len(trades_all)}건")
            
            if not trades_all:
                logger.info("Gate.io 거래 내역이 없음 - 기간 내 거래 없음")
                return {
                    'position_pnl': 0.0,
                    'trading_fees': 0.0,
                    'funding_fees': 0.0,
                    'net_profit': 0.0,
                    'trade_count': 0,
                    'source': 'no_trades_found_in_period'
                }
            
            # 거래 내역 분석 및 PnL 계산 - 강화된 로직
            total_pnl = 0.0
            total_trading_fees = 0.0
            total_funding_fees = 0.0
            trade_count = 0
            processed_trades = 0
            
            for trade in trades_all:
                try:
                    processed_trades += 1
                    
                    # Gate.io V4 API에서 point 필드가 실제 PnL을 나타냄
                    trade_pnl = 0.0
                    pnl_fields = ['point', 'pnl', 'realized_pnl', 'profit', 'close_pnl']
                    for field in pnl_fields:
                        if field in trade and trade[field] is not None:
                            try:
                                pnl_value = float(trade[field])
                                if pnl_value != 0:
                                    trade_pnl = pnl_value
                                    logger.debug(f"PnL 발견 ({field}): {pnl_value}")
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    # 거래 수수료 확인
                    trading_fee = 0.0
                    fee_fields = ['fee', 'trading_fee', 'total_fee']
                    for field in fee_fields:
                        if field in trade and trade[field] is not None:
                            try:
                                fee_value = float(trade[field])
                                if fee_value != 0:
                                    trading_fee = abs(fee_value)  # 수수료는 항상 양수
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    # 펀딩비 확인 
                    funding_fee = 0.0
                    funding_fields = ['funding_fee', 'funding_rate_fee', 'funding_cost']
                    for field in funding_fields:
                        if field in trade and trade[field] is not None:
                            try:
                                funding_value = float(trade[field])
                                if funding_value != 0:
                                    funding_fee = funding_value
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    # 유효한 데이터가 있을 때만 누적
                    if trade_pnl != 0 or trading_fee != 0 or funding_fee != 0:
                        total_pnl += trade_pnl
                        total_trading_fees += trading_fee
                        total_funding_fees += funding_fee
                        trade_count += 1
                        
                        # 상세 로깅 (처음 5건만)
                        if trade_count <= 5:
                            logger.debug(f"거래 {trade_count}: PnL=${trade_pnl:.4f}, 수수료=${trading_fee:.4f}, 펀딩=${funding_fee:.4f}")
                
                except Exception as trade_error:
                    logger.debug(f"Gate.io 거래 내역 처리 오류: {trade_error}")
                    continue
            
            # 순 수익 계산
            net_profit = total_pnl + total_funding_fees - total_trading_fees
            
            logger.info(f"✅ Gate.io Position PnL 계산 완료:")
            logger.info(f"  - 처리된 거래: {processed_trades}건 중 {trade_count}건 유효")
            logger.info(f"  - Position PnL: ${total_pnl:.4f}")
            logger.info(f"  - 거래 수수료: -${total_trading_fees:.4f}")
            logger.info(f"  - 펀딩비: {total_funding_fees:+.4f}")
            logger.info(f"  - 순 수익: ${net_profit:.4f}")
            
            return {
                'position_pnl': total_pnl,
                'trading_fees': total_trading_fees,
                'funding_fees': total_funding_fees,
                'net_profit': net_profit,
                'trade_count': trade_count,
                'processed_trades': processed_trades,
                'source': 'gate_v4_api_enhanced_v3',
                'confidence': 'high' if trade_count > 0 else 'medium'
            }
            
        except Exception as e:
            logger.error(f"Gate.io Position PnL 계산 실패: {e}")
            
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
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 오늘 0시 (KST)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # UTC로 변환하여 타임스탬프 생성
            start_time_utc = today_start.astimezone(pytz.UTC)
            end_time_utc = now.astimezone(pytz.UTC)
            
            start_timestamp = int(start_time_utc.timestamp())
            end_timestamp = int(end_time_utc.timestamp())
            
            result = await self.get_position_pnl_based_profit(
                start_timestamp,
                end_timestamp,
                'BTC_USDT'
            )
            
            today_pnl = result.get('position_pnl', 0.0)
            
            logger.info(f"✅ Gate.io 오늘 PnL: ${today_pnl:.4f}")
            return today_pnl
            
        except Exception as e:
            logger.error(f"Gate.io 오늘 Position PnL 조회 실패: {e}")
            return 0.0
    
    async def get_7day_position_pnl(self) -> Dict:
        try:
            kst = pytz.timezone('Asia/Seoul')
            current_time = datetime.now(kst)
            
            # 현재에서 정확히 7일 전
            seven_days_ago = current_time - timedelta(days=7)
            
            logger.info(f"🔍 Gate.io 7일 Position PnL 계산 (강화된 방식):")
            logger.info(f"  - 시작: {seven_days_ago.strftime('%Y-%m-%d %H:%M')} KST")
            logger.info(f"  - 종료: {current_time.strftime('%Y-%m-%d %H:%M')} KST")
            
            # UTC로 변환
            start_time_utc = seven_days_ago.astimezone(pytz.UTC)
            end_time_utc = current_time.astimezone(pytz.UTC)
            
            # 초 단위 타임스탬프 생성
            start_timestamp = int(start_time_utc.timestamp())
            end_timestamp = int(end_time_utc.timestamp())
            
            # 실제 기간 계산
            duration_seconds = end_timestamp - start_timestamp
            duration_days = duration_seconds / (24 * 60 * 60)
            
            # 7일보다 조금 많으면 정확히 7일로 조정
            if duration_days > 7.1:
                logger.info(f"기간이 7일을 초과함: {duration_days:.1f}일, 정확히 7일로 조정")
                start_timestamp = end_timestamp - (7 * 24 * 60 * 60)
                duration_days = 7.0
            
            logger.info(f"실제 계산 기간: {duration_days:.1f}일")
            
            # 여러 방식으로 강화된 PnL 계산 수행
            result = None
            
            # 방법 1: 일반 방식
            try:
                logger.info("🔄 7일 PnL 계산 방법 1: 기본 방식")
                result = await self.get_position_pnl_based_profit(
                    start_timestamp,  # 초 단위로 전달
                    end_timestamp,    # 초 단위로 전달
                    'BTC_USDT'
                )
                
                if result.get('trade_count', 0) > 0:
                    logger.info(f"✅ 방법 1 성공: {result.get('trade_count')}건 거래")
                else:
                    raise Exception("거래 내역 없음")
                    
            except Exception as e:
                logger.warning(f"방법 1 실패: {e}")
                
                # 방법 2: 더 긴 기간으로 재시도
                try:
                    logger.info("🔄 7일 PnL 계산 방법 2: 10일 범위로 확장")
                    ten_days_ago = current_time - timedelta(days=10)
                    extended_start = int(ten_days_ago.astimezone(pytz.UTC).timestamp())
                    
                    extended_result = await self.get_position_pnl_based_profit(
                        extended_start,
                        end_timestamp,
                        'BTC_USDT'
                    )
                    
                    if extended_result.get('trade_count', 0) > 0:
                        # 10일 결과를 7일로 비례 조정
                        extended_pnl = extended_result.get('position_pnl', 0)
                        adjusted_pnl = extended_pnl * (7 / 10)
                        
                        result = {
                            'position_pnl': adjusted_pnl,
                            'trading_fees': extended_result.get('trading_fees', 0) * 0.7,
                            'funding_fees': extended_result.get('funding_fees', 0) * 0.7,
                            'net_profit': extended_result.get('net_profit', 0) * 0.7,
                            'trade_count': extended_result.get('trade_count', 0),
                            'source': 'gate_7days_extended_adjusted',
                            'confidence': 'medium'
                        }
                        logger.info(f"✅ 방법 2 성공 (10일→7일 조정): {adjusted_pnl:.4f}")
                    else:
                        raise Exception("확장된 범위에서도 거래 없음")
                        
                except Exception as e2:
                    logger.warning(f"방법 2도 실패: {e2}")
                    
                    # 방법 3: 계정 변동 내역 방식
                    try:
                        logger.info("🔄 7일 PnL 계산 방법 3: 계정 변동 내역")
                        result = await self.get_position_pnl_alternative_method(
                            start_timestamp,
                            end_timestamp,
                            'BTC_USDT'
                        )
                        
                        if result.get('trade_count', 0) > 0:
                            logger.info(f"✅ 방법 3 성공: {result.get('trade_count')}건")
                        else:
                            raise Exception("계정 변동 내역에서도 데이터 없음")
                            
                    except Exception as e3:
                        logger.error(f"모든 방법 실패: {e3}")
                        result = {
                            'position_pnl': 0.0,
                            'trading_fees': 0.0,
                            'funding_fees': 0.0,
                            'net_profit': 0.0,
                            'trade_count': 0,
                            'source': 'all_methods_failed',
                            'confidence': 'low'
                        }
            
            position_pnl = result.get('position_pnl', 0.0)
            trading_fees = result.get('trading_fees', 0.0)
            funding_fees = result.get('funding_fees', 0.0)
            net_profit = result.get('net_profit', 0.0)
            trade_count = result.get('trade_count', 0)
            source = result.get('source', 'unknown')
            confidence = result.get('confidence', 'low')
            
            # 일평균 계산
            daily_average = position_pnl / duration_days if duration_days > 0 else 0
            
            logger.info(f"✅ Gate.io 7일 Position PnL 계산 완료:")
            logger.info(f"  - 실제 기간: {duration_days:.1f}일")
            logger.info(f"  - 거래 건수: {trade_count}건")
            logger.info(f"  - Position PnL: ${position_pnl:.4f}")
            logger.info(f"  - 거래 수수료: -${trading_fees:.4f}")
            logger.info(f"  - 펀딩비: {funding_fees:+.4f}")
            logger.info(f"  - 순 수익: ${net_profit:.4f}")
            logger.info(f"  - 일평균: ${daily_average:.4f}")
            logger.info(f"  - 계산 방식: {source}")
            logger.info(f"  - 신뢰도: {confidence}")
            
            return {
                'total_pnl': position_pnl,
                'daily_pnl': {},
                'average_daily': daily_average,
                'trade_count': trade_count,
                'actual_days': duration_days,
                'trading_fees': trading_fees,
                'funding_fees': funding_fees,
                'net_profit': net_profit,
                'source': source,
                'confidence': confidence
            }
            
        except Exception as e:
            logger.error(f"Gate.io 7일 Position PnL 조회 실패: {e}")
            
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'average_daily': 0,
                'trade_count': 0,
                'actual_days': 7,
                'trading_fees': 0,
                'funding_fees': 0,
                'net_profit': 0,
                'source': 'error_fallback',
                'confidence': 'low'
            }

    async def get_real_cumulative_profit_analysis(self) -> Dict:
        """실제 누적 수익 분석 - 입금액 제외"""
        try:
            logger.info(f"🔍 Gate.io 누적 수익 분석 (실 입금액 제외):")
            
            # 현재 계정 정보
            account = await self.get_account_balance()
            if not account:
                logger.error("Gate.io 계정 정보 조회 실패")
                return {
                    'actual_profit': 0,
                    'initial_deposits': 0,
                    'current_balance': 0,
                    'roi': 0,
                    'calculation_method': 'account_error',
                    'confidence': 'low'
                }
            
            current_balance = float(account.get('total', 0))
            
            # 실제 입금액 계산을 위한 계정 변동 내역 조회 (전체 기간)
            try:
                # 계정 개설 이후 전체 기간의 입출금 내역 조회
                now = datetime.now()
                start_of_year = datetime(2025, 1, 1)  # 2025년 시작부터
                
                start_timestamp = int(start_of_year.timestamp())
                end_timestamp = int(now.timestamp())
                
                logger.info(f"계정 변동 내역 조회: {start_of_year.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}")
                
                account_book = await self.get_account_book(
                    'BTC_USDT', 
                    start_timestamp, 
                    end_timestamp, 
                    2000  # 충분한 기간 커버
                )
                
                total_deposits = 0.0
                total_withdrawals = 0.0
                
                for entry in account_book:
                    try:
                        entry_type = entry.get('type', '').lower()
                        change = float(entry.get('change', 0))
                        
                        # 입금 관련 항목
                        if any(keyword in entry_type for keyword in ['deposit', 'transfer_in', 'add']):
                            if change > 0:
                                total_deposits += change
                                logger.debug(f"입금 발견: +${change:.2f} (타입: {entry_type})")
                        
                        # 출금 관련 항목
                        elif any(keyword in entry_type for keyword in ['withdraw', 'transfer_out', 'sub']):
                            if change < 0:
                                total_withdrawals += abs(change)
                                logger.debug(f"출금 발견: -${abs(change):.2f} (타입: {entry_type})")
                                
                    except Exception as entry_error:
                        logger.debug(f"계정 변동 항목 처리 오류: {entry_error}")
                        continue
                
                net_deposits = total_deposits - total_withdrawals
                actual_profit = current_balance - net_deposits
                
                # ROI 계산
                roi = (actual_profit / net_deposits * 100) if net_deposits > 0 else 0
                
                logger.info(f"✅ Gate.io 누적 수익 분석 완료 (실제 입금액 기반):")
                logger.info(f"  - 현재 잔고: ${current_balance:.2f}")
                logger.info(f"  - 총 입금: ${total_deposits:.2f}")
                logger.info(f"  - 총 출금: ${total_withdrawals:.2f}")
                logger.info(f"  - 순 입금: ${net_deposits:.2f}")
                logger.info(f"  - 실제 수익: ${actual_profit:.2f}")
                logger.info(f"  - 수익률: {roi:+.1f}%")
                
                return {
                    'actual_profit': actual_profit,
                    'initial_deposits': net_deposits,
                    'current_balance': current_balance,
                    'roi': roi,
                    'calculation_method': 'account_book_deposits',
                    'total_deposits': total_deposits,
                    'total_withdrawals': total_withdrawals,
                    'net_investment': net_deposits,
                    'confidence': 'high'
                }
                
            except Exception as book_error:
                logger.warning(f"계정 변동 내역 기반 계산 실패: {book_error}")
                
                # 폴백: 추정값 사용
                estimated_deposits = 750  # 기본 추정값
                actual_profit = current_balance - estimated_deposits if current_balance > estimated_deposits else 0
                roi = (actual_profit / estimated_deposits * 100) if estimated_deposits > 0 else 0
                
                logger.info(f"✅ Gate.io 누적 수익 분석 (추정값 기반):")
                logger.info(f"  - 현재 잔고: ${current_balance:.2f}")
                logger.info(f"  - 추정 입금: ${estimated_deposits:.2f}")
                logger.info(f"  - 추정 수익: ${actual_profit:.2f}")
                logger.info(f"  - 추정 수익률: {roi:+.1f}%")
                
                return {
                    'actual_profit': actual_profit,
                    'initial_deposits': estimated_deposits,
                    'current_balance': current_balance,
                    'roi': roi,
                    'calculation_method': 'estimated_deposits_fallback',
                    'total_deposits': estimated_deposits,
                    'total_withdrawals': 0,
                    'net_investment': estimated_deposits,
                    'confidence': 'medium'
                }
            
        except Exception as e:
            logger.error(f"Gate.io 누적 수익 분석 실패: {e}")
            return {
                'actual_profit': 0,
                'initial_deposits': 750,
                'current_balance': 0,
                'roi': 0,
                'calculation_method': 'error',
                'confidence': 'low'
            }
    
    async def set_leverage(self, contract: str, leverage: int, cross_leverage_limit: int = 0, 
                          retry_count: int = 5) -> Dict:
        for attempt in range(retry_count):
            try:
                endpoint = f"/api/v4/futures/usdt/positions/{contract}/leverage"
                
                data = {
                    "leverage": str(leverage),
                    "cross_leverage_limit": str(cross_leverage_limit) if cross_leverage_limit > 0 else "0"
                }
                
                logger.info(f"Gate.io 레버리지 설정 시도 {attempt + 1}/{retry_count}: {contract} - {leverage}x")
                
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
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(2.0)
                    continue
                else:
                    logger.warning(f"레버리지 설정 최종 실패하지만 계속 진행: {contract} - {leverage}x")
                    return {"warning": "leverage_setting_failed", "requested_leverage": leverage}
        
        return {"warning": "all_leverage_attempts_failed", "requested_leverage": leverage}
    
    async def _verify_leverage_setting(self, contract: str, expected_leverage: int, max_attempts: int = 3) -> bool:
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
            
            # 클로즈 주문 방향 매핑
            final_size = gate_size
            reduce_only_flag = False
            
            if is_close_order:
                reduce_only_flag = True
                
                if 'close_long' in side or side == 'close long':
                    final_size = -abs(gate_size)
                elif 'close_short' in side or side == 'close short':
                    final_size = abs(gate_size)
                elif 'sell' in side and 'buy' not in side:
                    final_size = -abs(gate_size)
                elif 'buy' in side and 'sell' not in side:
                    final_size = abs(gate_size)
                else:
                    if 'long' in side:
                        final_size = -abs(gate_size)
                    elif 'short' in side:
                        final_size = abs(gate_size)
                    else:
                        final_size = -abs(gate_size)
            else:
                reduce_only_flag = False
                
                if 'short' in side or 'sell' in side:
                    final_size = -abs(gate_size)
                else:
                    final_size = abs(gate_size)
            
            # Gate.io 트리거 타입 결정
            gate_trigger_type = "ge" if trigger_price > current_gate_price else "le"
            
            # TP/SL 포함 통합 주문 생성
            if tp_price or sl_price:
                gate_order = await self.create_conditional_order_with_tp_sl(
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
                    'perfect_mirror': has_tp_sl
                }
            else:
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
            
            if tp_price and tp_price > 0:
                data["stop_profit_price"] = str(tp_price)
            
            if sl_price and sl_price > 0:
                data["stop_loss_price"] = str(sl_price)
            
            response = await self._request('POST', endpoint, data=data)
            return response
            
        except Exception as e:
            logger.error(f"TP/SL 포함 조건부 주문 생성 실패: {e}")
            raise
    
    async def create_price_triggered_order(self, trigger_price: float, order_size: int,
                                         reduce_only: bool = False, trigger_type: str = "ge") -> Dict:
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
            logger.info(f"✅ Gate.io 가격 트리거 주문 취소 성공: {order_id}")
            return response
            
        except Exception as e:
            logger.error(f"가격 트리거 주문 취소 실패: {order_id} - {e}")
            raise
    
    async def place_order(self, contract: str, size: int, price: Optional[float] = None,
                         reduce_only: bool = False, tif: str = "gtc", iceberg: int = 0) -> Dict:
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
        try:
            positions = await self.get_positions(contract)
            
            if not positions or float(positions[0].get('size', 0)) == 0:
                return {"status": "no_position"}
            
            position = positions[0]
            position_size = int(float(position['size']))
            
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
        if self.session:
            await self.session.close()
            logger.info("Gate.io 미러링 클라이언트 세션 종료")
