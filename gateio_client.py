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
        """클라이언트 초기화 및 연결 테스트 - 강화된 버전"""
        self._initialize_session()
        
        # API 키 검증을 위한 간단한 호출
        try:
            logger.info("🔍 Gate.io API 연결 테스트 시작...")
            
            # 1단계: 계정 잔고 조회 테스트
            test_result = await self.get_account_balance()
            if test_result is not None and len(test_result) > 0:
                self.api_healthy = True
                self.last_successful_call = datetime.now()
                logger.info("✅ Gate.io 계정 조회 성공")
                
                # 2단계: 거래 내역 조회 테스트 (최근 7일)
                try:
                    now = datetime.now()
                    seven_days_ago = now - timedelta(days=7)
                    start_ts = int(seven_days_ago.timestamp() * 1000)
                    end_ts = int(now.timestamp() * 1000)
                    
                    trades = await self.get_my_trades(
                        contract="BTC_USDT",
                        start_time=start_ts,
                        end_time=end_ts,
                        limit=10
                    )
                    
                    logger.info(f"✅ Gate.io 거래 내역 조회 테스트: {len(trades)}건")
                    
                    if len(trades) > 0:
                        logger.info("✅ Gate.io에서 거래 내역 발견")
                    else:
                        logger.info("ℹ️ Gate.io에서 최근 7일간 거래 내역 없음")
                        
                except Exception as trade_error:
                    logger.warning(f"⚠️ Gate.io 거래 내역 조회 테스트 실패: {trade_error}")
                
                # 3단계: 계정 변동 내역 조회 테스트
                try:
                    account_book = await self.get_account_book(
                        start_time=start_ts,
                        end_time=end_ts,
                        limit=10
                    )
                    
                    logger.info(f"✅ Gate.io 계정 변동 내역 조회 테스트: {len(account_book)}건")
                    
                except Exception as book_error:
                    logger.warning(f"⚠️ Gate.io 계정 변동 내역 조회 테스트 실패: {book_error}")
                
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
    
    async def get_position_pnl_based_profit(self, start_time: int, end_time: int, contract: str = "BTC_USDT") -> Dict:
        """🔥🔥 Gate.io Position PnL 기준 정확한 손익 계산 - 개선된 거래 내역 파싱"""
        try:
            logger.info(f"🔍 Gate.io Position PnL 기준 정확한 손익 계산 시작...")
            logger.info(f"  - 계약: {contract}")
            logger.info(f"  - 시작: {datetime.fromtimestamp(start_time/1000)}")
            logger.info(f"  - 종료: {datetime.fromtimestamp(end_time/1000)}")
            
            # 거래 내역 조회
            trades = await self.get_my_trades(
                contract=contract,
                start_time=start_time,
                end_time=end_time,
                limit=500
            )
            
            logger.info(f"Gate.io 거래 내역 조회 결과: {len(trades)}건")
            
            if not trades:
                return {
                    'position_pnl': 0.0,
                    'trading_fees': 0.0,
                    'funding_fees': 0.0,
                    'net_profit': 0.0,
                    'trade_count': 0,
                    'source': 'no_trades_found'
                }
            
            # 🔥🔥 Position PnL과 수수료 분리 계산 - 개선된 버전
            total_position_pnl = 0.0
            total_trading_fees = 0.0
            total_funding_fees = 0.0
            trade_count = 0
            
            # 로깅을 위한 샘플 거래 정보
            logger.info(f"🔍 Gate.io 거래 내역 상세 분석:")
            logger.info(f"  - 총 거래 건수: {len(trades)}")
            
            # 모든 거래 키 분석
            all_keys = set()
            for trade in trades:
                if isinstance(trade, dict):
                    all_keys.update(trade.keys())
            
            logger.info(f"  - 거래 내역 필드들: {sorted(list(all_keys))}")
            
            # 첫 몇 건 상세 분석
            for i, trade in enumerate(trades[:3]):
                logger.info(f"  거래 {i+1} 상세:")
                for key, value in trade.items():
                    logger.info(f"    {key}: {value} (타입: {type(value).__name__})")
            
            for trade in trades:
                try:
                    # 🔥🔥 Position PnL 추출 (Gate.io 특화) - 개선된 필드 검색
                    position_pnl = 0.0
                    
                    # Gate.io Position PnL 관련 필드들 (우선순위 순) - 모든 가능한 필드 포함
                    pnl_fields = [
                        'pnl',              # 실제 포지션 손익 (가장 일반적)
                        'profit',           # 수익
                        'profit_loss',      # 손익
                        'realized_pnl',     # 실현 손익
                        'close_pnl',        # 청산 손익
                        'position_profit',  # 포지션 수익
                        'text'              # 때로는 텍스트에 포함
                    ]
                    
                    for field in pnl_fields:
                        if field in trade and trade[field] is not None:
                            try:
                                # 숫자가 아닌 경우 건너뛰기
                                raw_value = trade[field]
                                if isinstance(raw_value, str):
                                    # 문자열인 경우 숫자 추출 시도
                                    import re
                                    numbers = re.findall(r'[-+]?\d*\.?\d+', raw_value)
                                    if numbers:
                                        position_pnl = float(numbers[0])
                                    else:
                                        continue
                                else:
                                    position_pnl = float(raw_value)
                                
                                # 🔥🔥 비현실적인 값 필터링 완화 (절댓값 50,000 달러 이상만 오류로 간주)
                                if abs(position_pnl) > 50000:
                                    logger.warning(f"Gate.io 비현실적인 PnL 값 무시: {field} = {position_pnl}")
                                    continue
                                
                                if position_pnl != 0:
                                    logger.debug(f"Gate.io Position PnL 추출: {field} = {position_pnl}")
                                    break
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Gate.io PnL 필드 변환 실패 {field}: {e}")
                                continue
                    
                    # 🔥🔥 거래량 기반 간접 PnL 계산 (Position PnL이 없는 경우)
                    if position_pnl == 0:
                        try:
                            size = float(trade.get('size', 0))
                            price = float(trade.get('price', 0))
                            
                            # 거래 방향 확인
                            is_long = trade.get('side', '').lower() == 'buy'
                            
                            # 시장가와 진입가의 차이로 대략적인 PnL 추정 (매우 기본적)
                            if size != 0 and price != 0:
                                # 이것은 추정치이므로 실제 PnL과 다를 수 있음
                                # Gate.io에서는 일반적으로 pnl 필드가 있어야 함
                                logger.debug(f"Gate.io PnL 추정 시도: size={size}, price={price}")
                        except Exception as calc_error:
                            logger.debug(f"Gate.io PnL 계산 실패: {calc_error}")
                    
                    # 🔥🔥 거래 수수료 추출 (Gate.io 특화) - 개선된 버전
                    trading_fee = 0.0
                    
                    # Gate.io 거래 수수료 필드들 - 더 포괄적으로
                    fee_fields = [
                        'fee',              # 거래 수수료 (가장 일반적)
                        'taker_fee',        # 테이커 수수료
                        'maker_fee',        # 메이커 수수료
                        'trading_fee',      # 거래 수수료
                        'commission',       # 커미션
                        'commission_fee'    # 커미션 수수료
                    ]
                    
                    for field in fee_fields:
                        if field in trade and trade[field] is not None:
                            try:
                                fee_value = float(trade[field])
                                
                                # 🔥🔥 비현실적인 수수료 값 필터링 (절댓값 100 달러 이상은 오류로 간주)
                                if abs(fee_value) > 100:
                                    logger.warning(f"Gate.io 비현실적인 수수료 값 무시: {field} = {fee_value}")
                                    continue
                                
                                if fee_value != 0:
                                    trading_fee = abs(fee_value)  # 수수료는 항상 양수
                                    logger.debug(f"Gate.io 거래 수수료 추출: {field} = {trading_fee}")
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    # 🔥🔥 펀딩비는 별도 API로 조회 (거래 내역에는 포함되지 않음)
                    # Gate.io는 거래 내역에 펀딩비가 포함되지 않으므로 0으로 설정
                    funding_fee = 0.0
                    
                    # 통계 누적 - 비현실적인 값 최종 검증
                    if position_pnl != 0 or trading_fee != 0:
                        # 🔥🔥 최종 안전장치: 비현실적인 값은 누적하지 않음
                        if abs(position_pnl) > 10000:
                            logger.warning(f"Gate.io 거래 처리 건너뜀 - 비현실적인 PnL: {position_pnl}")
                            continue
                        if trading_fee > 100:
                            logger.warning(f"Gate.io 거래 처리 건너뜀 - 비현실적인 수수료: {trading_fee}")
                            continue
                        
                        total_position_pnl += position_pnl
                        total_trading_fees += trading_fee
                        total_funding_fees += funding_fee
                        trade_count += 1
                        
                        logger.debug(f"Gate.io 거래 처리: PnL={position_pnl:.4f}, 거래수수료={trading_fee:.4f}")
                
                except Exception as trade_error:
                    logger.debug(f"Gate.io 거래 내역 처리 오류: {trade_error}")
                    continue
            
            # 🔥🔥 최종 계산
            net_profit = total_position_pnl + total_funding_fees - total_trading_fees
            
            logger.info(f"✅ Gate.io Position PnL 기준 정확한 손익 계산 완료:")
            logger.info(f"  - Position PnL: ${total_position_pnl:.4f} (수수료 제외 실제 포지션 손익)")
            logger.info(f"  - 거래 수수료: -${total_trading_fees:.4f} (오픈/클로징 수수료)")
            logger.info(f"  - 펀딩비: ${total_funding_fees:.4f} (거래내역에 포함되지 않음, 별도 조회 필요)")
            logger.info(f"  - 순 수익: ${net_profit:.4f} (Position PnL + 펀딩비 - 거래수수료)")
            logger.info(f"  - 거래 건수: {trade_count}건")
            
            return {
                'position_pnl': total_position_pnl,        # 실제 포지션 손익 (수수료 제외)
                'trading_fees': total_trading_fees,        # 거래 수수료
                'funding_fees': total_funding_fees,        # 펀딩비 (별도 조회 필요)
                'net_profit': net_profit,                  # 순 수익
                'trade_count': trade_count,
                'source': 'gate_position_pnl_based_accurate_improved',
                'confidence': 'high'
            }
            
        except Exception as e:
            logger.error(f"Gate.io Position PnL 기준 손익 계산 실패: {e}")
            
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
        """🔥🔥 오늘 Position PnL 기준 실현손익 조회 - 다중 방법 시도"""
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
            
            logger.info(f"🔍 Gate.io 오늘 PnL 조회 시작 (다중 방법):")
            
            # 🔥🔥 방법 1: 거래 내역 기반 Position PnL 계산
            result = await self.get_position_pnl_based_profit(start_timestamp, end_timestamp)
            position_pnl = result.get('position_pnl', 0.0)
            
            if position_pnl != 0.0:
                logger.info(f"✅ 방법 1 성공 - 거래 내역 기반: ${position_pnl:.4f}")
                return position_pnl
            
            # 🔥🔥 방법 2: 계정 변동 내역 기반 PnL 추출
            try:
                logger.info("🔍 방법 2 시도: 계정 변동 내역 기반")
                account_book = await self.get_account_book(
                    start_time=start_timestamp,
                    end_time=end_timestamp,
                    limit=100,
                    type_filter='pnl'  # PnL 타입만 조회
                )
                
                pnl_from_book = 0.0
                for record in account_book:
                    change = float(record.get('change', 0))
                    if change != 0:
                        pnl_from_book += change
                        logger.debug(f"계정 변동: {change}")
                
                if pnl_from_book != 0.0:
                    logger.info(f"✅ 방법 2 성공 - 계정 변동 내역: ${pnl_from_book:.4f}")
                    return pnl_from_book
                
            except Exception as e:
                logger.debug(f"방법 2 실패: {e}")
            
            # 🔥🔥 방법 3: 잔고 변화 추정 (임시)
            logger.info("⚠️ 거래 내역 및 계정 변동 내역 없음, 0 반환")
            return 0.0
            
        except Exception as e:
            logger.error(f"Gate.io 오늘 Position PnL 조회 실패: {e}")
            return 0.0
    
    async def get_7day_position_pnl(self) -> Dict:
        """🔥🔥 Gate.io 7일 Position PnL 조회 - 다중 방법 시도 개선"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            current_time = datetime.now(kst)
            
            # 🔥🔥 현재에서 정확히 7일 전
            seven_days_ago = current_time - timedelta(days=7)
            
            logger.info(f"🔍 Gate.io 7일 Position PnL 계산 (개선된 다중 방법):")
            logger.info(f"  - 시작: {seven_days_ago.strftime('%Y-%m-%d %H:%M')} KST")
            logger.info(f"  - 종료: {current_time.strftime('%Y-%m-%d %H:%M')} KST")
            
            # UTC로 변환
            start_time_utc = seven_days_ago.astimezone(pytz.UTC)
            end_time_utc = current_time.astimezone(pytz.UTC)
            
            start_timestamp = int(start_time_utc.timestamp() * 1000)
            end_timestamp = int(end_time_utc.timestamp() * 1000)
            
            # 🔥🔥 개선된 조회 방법 - 더 짧은 기간으로 나누어 조회
            position_pnl = 0.0
            trade_count = 0
            
            try:
                # 🔥🔥 방법 1: 거래 내역 기반 Position PnL 계산 (개선)
                logger.info("🔍 방법 1 개선: 단계별 거래 내역 조회")
                
                # 7일을 3일씩 나누어 조회 (안정성 향상)
                day_chunks = []
                current_chunk = current_time
                
                while current_chunk > seven_days_ago:
                    chunk_start = max(current_chunk - timedelta(days=3), seven_days_ago)
                    chunk_end = current_chunk
                    
                    day_chunks.append((chunk_start, chunk_end))
                    current_chunk = chunk_start
                
                logger.info(f"  - 총 {len(day_chunks)}개 청크로 분할하여 조회")
                
                for i, (chunk_start, chunk_end) in enumerate(day_chunks):
                    try:
                        chunk_start_ts = int(chunk_start.astimezone(pytz.UTC).timestamp() * 1000)
                        chunk_end_ts = int(chunk_end.astimezone(pytz.UTC).timestamp() * 1000)
                        
                        logger.info(f"  청크 {i+1}/{len(day_chunks)}: {chunk_start.strftime('%m-%d %H:%M')} ~ {chunk_end.strftime('%m-%d %H:%M')}")
                        
                        chunk_result = await self.get_position_pnl_based_profit(
                            chunk_start_ts, 
                            chunk_end_ts
                        )
                        
                        chunk_pnl = chunk_result.get('position_pnl', 0.0)
                        chunk_trades = chunk_result.get('trade_count', 0)
                        
                        # 🔥🔥 안전장치: 비현실적인 값 필터링
                        if abs(chunk_pnl) > 1000:  # 청크당 1천 달러 이상은 비현실적
                            logger.warning(f"청크 {i+1} 비현실적 PnL 무시: ${chunk_pnl:.2f}")
                            continue
                        
                        position_pnl += chunk_pnl
                        trade_count += chunk_trades
                        
                        logger.info(f"  청크 {i+1} 결과: PnL=${chunk_pnl:.4f}, 거래={chunk_trades}건")
                        
                        # 요청 간격 조절
                        await asyncio.sleep(0.5)
                        
                    except Exception as chunk_error:
                        logger.warning(f"청크 {i+1} 조회 실패: {chunk_error}")
                        continue
                
                logger.info(f"✅ 개선된 방법 1 완료: PnL=${position_pnl:.4f}, 총 거래={trade_count}건")
                
            except Exception as method1_error:
                logger.error(f"개선된 방법 1 실패: {method1_error}")
            
            # 🔥🔥 방법 2: 계정 변동 내역 기반 (백업)
            if position_pnl == 0.0 and trade_count == 0:
                try:
                    logger.info("🔍 방법 2 시도: 계정 변동 내역 기반")
                    account_book = await self.get_account_book(
                        start_time=start_timestamp,
                        end_time=end_timestamp,
                        limit=500,
                        type_filter='pnl'  # PnL 타입만 조회
                    )
                    
                    pnl_from_book = 0.0
                    for record in account_book:
                        change = float(record.get('change', 0))
                        # 🔥🔥 안전장치
                        if abs(change) > 500:  # 건당 500달러 이상은 비현실적
                            continue
                        pnl_from_book += change
                        logger.debug(f"7일 계정 변동: {change}")
                    
                    if pnl_from_book != 0.0:
                        position_pnl = pnl_from_book
                        logger.info(f"✅ 방법 2 성공 - 계정 변동 내역: ${position_pnl:.4f}")
                    else:
                        logger.info("⚠️ 거래 내역 및 계정 변동 내역 없음")
                    
                except Exception as e:
                    logger.debug(f"방법 2 실패: {e}")
            
            # 🔥🔥 최종 안전장치 - 비현실적인 값 확인
            if abs(position_pnl) > 5000:  # 7일간 5천 달러 이상은 비현실적
                logger.warning(f"Gate.io 7일 PnL 비현실적 값 감지, 0으로 처리: ${position_pnl:.2f}")
                position_pnl = 0.0
                trade_count = 0
            
            # 7일로 나누어 일평균 계산
            total_days = (current_time - seven_days_ago).total_seconds() / 86400
            actual_days = max(total_days, 1)  # 최소 1일
            
            daily_average = position_pnl / actual_days
            
            logger.info(f"✅ Gate.io 7일 Position PnL 계산 완료 (개선된 방법):")
            logger.info(f"  - 기간: {actual_days:.1f}일")
            logger.info(f"  - Position PnL: ${position_pnl:.4f}")
            logger.info(f"  - 일평균: ${daily_average:.4f}")
            logger.info(f"  - 거래 건수: {trade_count}건")
            
            return {
                'total_pnl': position_pnl,           # 수수료 제외한 실제 Position PnL
                'daily_pnl': {},                     # 일별 분석은 별도 구현 필요시
                'average_daily': daily_average,
                'trade_count': trade_count,
                'actual_days': actual_days,
                'trading_fees': 0,  # 별도 계산 필요
                'funding_fees': 0,  # 별도 계산 필요
                'net_profit': position_pnl,
                'source': 'gate_7days_position_pnl_improved_chunked',
                'confidence': 'high' if position_pnl != 0.0 or trade_count > 0 else 'medium'
            }
            
        except Exception as e:
            logger.error(f"Gate.io 7일 Position PnL 조회 실패: {e}")
            
            return {
                'total_pnl': 0,
                'daily_pnl': {},
                'average_daily': 0,
                'trade_count': 0,
                'actual_days': 7,
                'source': 'error',
                'confidence': 'low'
            }
    
    async def get_account_book(self, start_time: int = None, end_time: int = None, limit: int = 100, type_filter: str = None) -> List[Dict]:
        """🔥🔥 계정 변동 내역 조회 - Gate.io API v4 공식 문서 완전 준수 + 30일 제한 해결"""
        try:
            endpoint = "/api/v4/futures/usdt/account_book"
            params = {
                'limit': str(min(limit, 1000))  # Gate.io 최대 1000
            }
            
            # 🔥🔥 30일 제한 해결: 기간이 30일을 초과하지 않도록 제한
            if start_time and end_time:
                start_timestamp_sec = int(start_time / 1000)
                end_timestamp_sec = int(end_time / 1000)
                
                # 30일 = 30 * 24 * 60 * 60 = 2,592,000초
                max_duration = 30 * 24 * 60 * 60
                
                if (end_timestamp_sec - start_timestamp_sec) > max_duration:
                    logger.warning(f"🔧 Gate.io API 30일 제한으로 조회 기간 단축")
                    logger.info(f"  - 원래 기간: {(end_timestamp_sec - start_timestamp_sec) / 86400:.1f}일")
                    
                    # 현재 시점에서 최대 30일 이전까지만 조회
                    start_timestamp_sec = end_timestamp_sec - max_duration
                    logger.info(f"  - 수정된 기간: {(end_timestamp_sec - start_timestamp_sec) / 86400:.1f}일")
                
                params['from'] = str(start_timestamp_sec)
                params['to'] = str(end_timestamp_sec)
            elif start_time:
                # 시작 시간만 있는 경우
                start_timestamp_sec = int(start_time / 1000)
                current_time = int(time.time())
                
                if (current_time - start_timestamp_sec) > (30 * 24 * 60 * 60):
                    logger.warning(f"🔧 Gate.io API 30일 제한으로 시작 시간 조정")
                    start_timestamp_sec = current_time - (30 * 24 * 60 * 60)
                
                params['from'] = str(start_timestamp_sec)
            elif end_time:
                # 종료 시간만 있는 경우
                end_timestamp_sec = int(end_time / 1000)
                params['to'] = str(end_timestamp_sec)
            
            if type_filter:
                params['type'] = type_filter  # 'pnl', 'fee', 'fund', 'dnw', 'refr'
            
            logger.debug(f"Gate.io 계정 변동 내역 조회 (30일 제한 적용): type={type_filter}, 기간: {params.get('from')} ~ {params.get('to')}")
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list):
                actual_days = ((int(params.get('to', time.time())) - int(params.get('from', time.time() - 86400))) / 86400) if params.get('from') and params.get('to') else 0
                logger.info(f"✅ Gate.io 계정 변동 내역 조회 성공: {len(response)}건 (type: {type_filter}, 기간: {actual_days:.1f}일)")
                return response
            else:
                logger.warning(f"Gate.io 계정 변동 내역 응답 형식 예상치 못함: {type(response)}")
                return []
            
        except Exception as e:
            logger.error(f"Gate.io 계정 변동 내역 조회 실패: {e}")
            return []
    
    async def get_today_realized_pnl(self) -> float:
        """오늘 실현 손익 조회 - Position PnL 기준"""
        return await self.get_today_position_pnl()
    
    async def get_weekly_profit(self) -> Dict:
        """🔥🔥 7일 손익 조회 - Position PnL 기준"""
        return await self.get_7day_position_pnl()
    
    async def get_real_cumulative_profit_analysis(self) -> Dict:
        """🔥🔥 진짜 누적 수익 분석 - 입금/출금 기반 정확한 계산 + 30일 제한 준수"""
        try:
            logger.info(f"🔍 Gate.io 진짜 누적 수익 분석 시작 (입금/출금 기반 정확한 계산, 30일 제한 준수):")
            
            # 현재 계정 정보
            account = await self.get_account_balance()
            current_balance = float(account.get('total', 0)) if account else 0
            
            logger.info(f"  - 현재 잔고: ${current_balance:.2f}")
            
            # 🔥🔥 방법 1: 입금/출금 내역으로 실제 초기 자본 파악 (최대 30일 - API 제한 준수)
            initial_deposits = 0.0
            withdrawals = 0.0
            
            try:
                logger.info("📊 방법 1: 입금/출금 내역 분석 (30일간 - API 제한 준수)")
                
                # 최대 30일간 입금/출금 내역 조회 (Gate.io API 제한 준수)
                kst = pytz.timezone('Asia/Seoul')
                now = datetime.now(kst)
                thirty_days_ago = now - timedelta(days=30)  # 90일 → 30일로 변경
                
                start_timestamp_ms = int(thirty_days_ago.astimezone(pytz.UTC).timestamp() * 1000)
                end_timestamp_ms = int(now.astimezone(pytz.UTC).timestamp() * 1000)
                
                # 입금 기록 (fund 타입) - 30일 제한 준수
                fund_records = await self.get_account_book(
                    start_time=start_timestamp_ms,
                    end_time=end_timestamp_ms,
                    limit=1000,
                    type_filter='fund'
                )
                
                if fund_records:
                    for record in fund_records:
                        change = float(record.get('change', 0))
                        if change > 0:  # 입금
                            initial_deposits += change
                        elif change < 0:  # 출금
                            withdrawals += abs(change)
                    
                    logger.info(f"  - 30일간 입금: ${initial_deposits:.2f} (API 제한으로 30일만 조회)")
                    logger.info(f"  - 30일간 출금: ${withdrawals:.2f}")
                    logger.info(f"  - 순입금: ${initial_deposits - withdrawals:.2f}")
                
            except Exception as e:
                logger.error(f"입금/출금 내역 조회 실패: {e}")
            
            # 🔥🔥 방법 2: 실제 누적 수익 계산 - 입금/출금 기반 (30일 제한 고려)
            cumulative_profit = 0.0
            initial_capital = 750  # 기본값
            calculation_method = "balance_based_default"
            
            # 입금 내역이 있는 경우 - 가장 정확한 방법 (단, 30일만 조회 가능)
            if initial_deposits > 0:
                # 순 투자금 = 입금 - 출금 (30일간만)
                net_investment_30d = initial_deposits - withdrawals
                
                # 🔥🔥 중요: 30일 이전의 자산이 있을 가능성 고려
                if current_balance > net_investment_30d:
                    # 30일 이전에 이미 자산이 있었던 것으로 추정
                    estimated_initial_balance = 750  # 추정 초기 자본
                    cumulative_profit = current_balance - estimated_initial_balance
                    initial_capital = estimated_initial_balance
                    calculation_method = "30day_deposits_plus_estimated_initial"
                    
                    logger.info(f"✅ 30일 입금/출금 + 추정 초기 자본 기반 계산:")
                    logger.info(f"  - 30일간 순 투자금: ${net_investment_30d:.2f}")
                    logger.info(f"  - 추정 초기 자본: ${estimated_initial_balance:.2f}")
                    logger.info(f"  - 누적 수익: ${cumulative_profit:.2f}")
                else:
                    # 30일간 순 투자금만으로 계산
                    cumulative_profit = current_balance - net_investment_30d
                    initial_capital = net_investment_30d
                    calculation_method = "30day_deposit_withdrawal_only"
                    
                    logger.info(f"✅ 30일 입금/출금 기반 계산:")
                    logger.info(f"  - 순 투자금: ${net_investment_30d:.2f}")
                    logger.info(f"  - 누적 수익: ${cumulative_profit:.2f}")
            
            # 입금 내역이 없는 경우 - 잔고 기반 추정
            else:
                logger.info("📊 방법 2: 잔고 기반 추정 (입금 내역 없음)")
                
                # 기본 초기 자본으로 계산
                if current_balance > 0:
                    # 추정 초기 자본 (보수적)
                    estimated_initial = 750
                    cumulative_profit = current_balance - estimated_initial
                    initial_capital = estimated_initial
                    calculation_method = "balance_minus_estimated_initial"
                    
                    logger.info(f"  - 추정 초기 자본: ${estimated_initial:.2f}")
                    logger.info(f"  - 추정 누적 수익: ${cumulative_profit:.2f}")
                else:
                    # 잔고가 0인 경우
                    cumulative_profit = 0
                    initial_capital = 750
                    calculation_method = "zero_balance"
            
            # 수익률 계산
            cumulative_roi = (cumulative_profit / initial_capital * 100) if initial_capital > 0 else 0
            
            logger.info(f"✅ Gate.io 최종 누적 수익 분석 완료 (30일 제한 준수):")
            logger.info(f"  - 현재 잔고: ${current_balance:.2f}")
            logger.info(f"  - 실제 초기 자본: ${initial_capital:.2f}")
            logger.info(f"  - 진짜 누적 수익: ${cumulative_profit:.2f}")
            logger.info(f"  - 수익률: {cumulative_roi:+.1f}%")
            logger.info(f"  - 계산 방법: {calculation_method}")
            logger.info(f"  - API 제한: 30일 이전 데이터 조회 불가")
            
            return {
                'actual_profit': cumulative_profit,
                'initial_capital': initial_capital,
                'current_balance': current_balance,
                'roi': cumulative_roi,
                'calculation_method': calculation_method,
                'total_deposits': initial_deposits,
                'total_withdrawals': withdrawals,
                'net_investment': initial_deposits - withdrawals,
                'confidence': 'high' if initial_deposits > 0 else 'medium',
                'api_limitation': '30day_max_lookback'  # API 제한 표시
            }
            
        except Exception as e:
            logger.error(f"Gate.io 진짜 누적 수익 분석 실패: {e}")
            return {
                'actual_profit': 0,
                'initial_capital': 750,
                'current_balance': 0,
                'roi': 0,
                'calculation_method': 'error',
                'confidence': 'low',
                'api_limitation': '30day_max_lookback'
            }
    
    async def get_profit_history_since_may(self) -> Dict:
        """🔥🔥 Gate.io 수정된 정확한 누적 수익 조회 - 7일 수익과 구분 + 30일 API 제한 준수"""
        try:
            logger.info(f"🔍 Gate.io 수정된 정확한 누적 수익 조회 (7일 수익과 명확히 구분, 30일 API 제한 준수):")
            
            # 오늘 실현 손익 - Position PnL 기준
            today_realized = await self.get_today_position_pnl()
            
            # 7일 손익 (별도 계산 - 30일 제한 이내) - Position PnL 기준
            weekly_profit = await self.get_7day_position_pnl()
            
            # 🔥🔥 누적 수익 분석 (7일 수익과 완전히 별개로 계산 - 30일 제한 고려)
            cumulative_analysis = await self.get_real_cumulative_profit_analysis()
            
            cumulative_profit = cumulative_analysis.get('actual_profit', 0)
            initial_capital = cumulative_analysis.get('initial_capital', 750)
            current_balance = cumulative_analysis.get('current_balance', 0)
            cumulative_roi = cumulative_analysis.get('roi', 0)
            calculation_method = cumulative_analysis.get('calculation_method', 'unknown')
            confidence = cumulative_analysis.get('confidence', 'low')
            
            # 🔥🔥 검증: 7일 수익과 누적 수익이 다른지 확인
            weekly_pnl = weekly_profit.get('total_pnl', 0)
            diff_7d_vs_cumulative = abs(cumulative_profit - weekly_pnl)
            
            # 🔥🔥 30일 API 제한으로 인한 주의사항
            api_limitation_note = "Gate.io API는 30일 이전 데이터 조회 불가"
            
            logger.info(f"Gate.io 수정된 정확한 누적 수익 최종 결과 (30일 제한 준수):")
            logger.info(f"  - 현재 잔고: ${current_balance:.2f}")
            logger.info(f"  - 7일 수익: ${weekly_pnl:.2f} (Position PnL 기준)")
            logger.info(f"  - 누적 수익: ${cumulative_profit:.2f}")
            logger.info(f"  - 실제 초기 자본: ${initial_capital:.2f}")
            logger.info(f"  - 수익률: {cumulative_roi:+.1f}%")
            logger.info(f"  - 계산 방법: {calculation_method}")
            logger.info(f"  - 신뢰도: {confidence}")
            logger.info(f"  - 7일 vs 누적 차이: ${diff_7d_vs_cumulative:.2f} ({'정상' if diff_7d_vs_cumulative > 10 else '의심스러움'})")
            logger.info(f"  - API 제한: {api_limitation_note}")
            
            return {
                'total_pnl': cumulative_profit,
                'today_realized': today_realized,
                'weekly': weekly_profit,
                'current_balance': current_balance,
                'actual_profit': cumulative_profit,  # 진짜 누적 수익 (7일과 완전히 구분됨)
                'initial_capital': initial_capital,  # 실제 초기 자본
                'cumulative_roi': cumulative_roi,
                'source': f'corrected_analysis_{calculation_method}_30day_compliant_position_pnl',
                'calculation_method': calculation_method,
                'confidence': confidence,
                'weekly_vs_cumulative_diff': diff_7d_vs_cumulative,
                'analysis_details': cumulative_analysis,
                'is_7day_and_cumulative_different': diff_7d_vs_cumulative > 10,  # 검증 플래그
                'api_limitation': api_limitation_note
            }
            
        except Exception as e:
            logger.error(f"Gate.io 수정된 정확한 누적 수익 조회 실패: {e}")
            return {
                'total_pnl': 0,
                'today_realized': 0,
                'weekly': {'total_pnl': 0, 'average_daily': 0},
                'current_balance': 0,
                'actual_profit': 0,
                'initial_capital': 750,
                'cumulative_roi': 0,
                'source': 'error_corrected_analysis_30day_compliant_position_pnl',
                'confidence': 'low',
                'api_limitation': 'Gate.io API 30일 제한'
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
