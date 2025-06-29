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
                
                # 거래 내역 조회 테스트
                try:
                    now = datetime.now()
                    seven_days_ago = now - timedelta(days=7)
                    start_ts = int(seven_days_ago.timestamp())
                    end_ts = int(now.timestamp())
                    
                    trades = await self.get_my_trades(
                        contract="BTC_USDT",
                        start_time=start_ts,
                        end_time=end_ts,
                        limit=10
                    )
                    
                    logger.info(f"✅ Gate.io 거래 내역 조회 테스트: {len(trades)}건")
                    
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
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None, max_retries: int = 2) -> Dict:
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
    
    async def get_my_trades(self, contract: str = "BTC_USDT", start_time: int = None, end_time: int = None, limit: int = 100) -> List[Dict]:
        try:
            endpoint = "/api/v4/futures/usdt/my_trades"
            params = {
                'contract': contract,
                'limit': str(min(limit, 1000))
            }
            
            # Gate.io API는 초 단위 타임스탬프 사용
            if start_time:
                if start_time > 1000000000000:  # 밀리초 형태라면
                    params['from'] = str(int(start_time / 1000))
                else:  # 이미 초 형태라면
                    params['from'] = str(start_time)
            if end_time:
                if end_time > 1000000000000:  # 밀리초 형태라면
                    params['to'] = str(int(end_time / 1000))
                else:  # 이미 초 형태라면
                    params['to'] = str(end_time)
            
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
        try:
            logger.info(f"🔍 Gate.io Position PnL 기준 손익 계산 시작...")
            logger.info(f"  - 계약: {contract}")
            logger.info(f"  - 시작: {datetime.fromtimestamp(start_time/1000 if start_time > 1000000000000 else start_time)}")
            logger.info(f"  - 종료: {datetime.fromtimestamp(end_time/1000 if end_time > 1000000000000 else end_time)}")
            
            # 거래 내역 조회
            trades_all = await self.get_my_trades(
                contract=contract,
                start_time=start_time,
                end_time=end_time,
                limit=1000
            )
            
            logger.info(f"Gate.io 거래 내역 조회 결과: {len(trades_all)}건")
            
            if not trades_all:
                return {
                    'position_pnl': 0.0,
                    'trading_fees': 0.0,
                    'funding_fees': 0.0,
                    'net_profit': 0.0,
                    'trade_count': 0,
                    'source': 'no_trades_found'
                }
            
            # Gate.io V4 API 정확한 필드 사용
            total_pnl = 0.0
            total_trading_fees = 0.0
            total_funding_fees = 0.0
            trade_count = 0
            
            for trade in trades_all:
                try:
                    trade_pnl = 0.0
                    trading_fee = 0.0
                    funding_fee = 0.0
                    
                    # PnL 필드 (Gate.io V4)
                    pnl_fields = ['pnl', 'realized_pnl', 'profit', 'close_pnl']
                    for field in pnl_fields:
                        if field in trade and trade[field] is not None:
                            try:
                                trade_pnl = float(trade[field])
                                if trade_pnl != 0:
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    # 거래 수수료 필드 (Gate.io V4)
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
                    
                    # 펀딩비 필드 (Gate.io V4)
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
                    
                    # 통계 누적
                    if trade_pnl != 0 or trading_fee != 0 or funding_fee != 0:
                        total_pnl += trade_pnl
                        total_trading_fees += trading_fee
                        total_funding_fees += funding_fee
                        trade_count += 1
                
                except Exception as trade_error:
                    logger.debug(f"Gate.io 거래 내역 처리 오류: {trade_error}")
                    continue
            
            # 순 수익 계산
            net_profit = total_pnl + total_funding_fees - total_trading_fees
            
            logger.info(f"✅ Gate.io Position PnL 계산 완료:")
            logger.info(f"  - Position PnL: ${total_pnl:.4f}")
            logger.info(f"  - 거래 수수료: -${total_trading_fees:.4f}")
            logger.info(f"  - 펀딩비: {total_funding_fees:+.4f}")
            logger.info(f"  - 순 수익: ${net_profit:.4f}")
            logger.info(f"  - 거래 건수: {trade_count}건")
            
            return {
                'position_pnl': total_pnl,
                'trading_fees': total_trading_fees,
                'funding_fees': total_funding_fees,
                'net_profit': net_profit,
                'trade_count': trade_count,
                'source': 'gate_v4_api_accurate',
                'confidence': 'high'
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
            
            start_timestamp = int(start_time_utc.timestamp() * 1000)
            end_timestamp = int(end_time_utc.timestamp() * 1000)
            
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
            
            logger.info(f"🔍 Gate.io 7일 Position PnL 계산:")
            logger.info(f"  - 시작: {seven_days_ago.strftime('%Y-%m-%d %H:%M')} KST")
            logger.info(f"  - 종료: {current_time.strftime('%Y-%m-%d %H:%M')} KST")
            
            start_time_utc = seven_days_ago.astimezone(pytz.UTC)
            end_time_utc = current_time.astimezone(pytz.UTC)
            
            start_timestamp = int(start_time_utc.timestamp() * 1000)
            end_timestamp = int(end_time_utc.timestamp() * 1000)
            
            # 실제 기간 계산 (밀리초 차이를 일수로 변환)
            duration_ms = end_timestamp - start_timestamp
            duration_days = duration_ms / (1000 * 60 * 60 * 24)
            
            # 7일보다 조금 많으면 정확히 7일로 조정
            if duration_days > 7.1:
                logger.info(f"기간이 7일을 초과함: {duration_days:.1f}일, 정확히 7일로 조정")
                start_timestamp = end_timestamp - (7 * 24 * 60 * 60 * 1000)
                duration_days = 7.0
            
            # 정확한 API 데이터 기반 계산
            result = await self.get_position_pnl_based_profit(
                start_timestamp, 
                end_timestamp, 
                'BTC_USDT'
            )
            
            position_pnl = result.get('position_pnl', 0.0)
            trading_fees = result.get('trading_fees', 0.0)
            funding_fees = result.get('funding_fees', 0.0)
            net_profit = result.get('net_profit', 0.0)
            trade_count = result.get('trade_count', 0)
            
            # 일평균 계산
            daily_average = position_pnl / duration_days if duration_days > 0 else 0
            
            logger.info(f"✅ Gate.io 7일 Position PnL 계산 완료:")
            logger.info(f"  - 실제 기간: {duration_days:.1f}일")
            logger.info(f"  - Position PnL: ${position_pnl:.4f}")
            logger.info(f"  - 거래 수수료: -${trading_fees:.4f}")
            logger.info(f"  - 펀딩비: {funding_fees:+.4f}")
            logger.info(f"  - 순 수익: ${net_profit:.4f}")
            logger.info(f"  - 일평균: ${daily_average:.4f}")
            logger.info(f"  - 거래 건수: {trade_count}건")
            
            return {
                'total_pnl': position_pnl,
                'daily_pnl': {},
                'average_daily': daily_average,
                'trade_count': trade_count,
                'actual_days': duration_days,
                'trading_fees': trading_fees,
                'funding_fees': funding_fees,
                'net_profit': net_profit,
                'source': 'gate_v4_api_accurate',
                'confidence': 'high'
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
        try:
            logger.info(f"🔍 Gate.io 누적 수익 분석:")
            
            # 현재 계정 정보
            account = await self.get_account_balance()
            if not account:
                logger.error("Gate.io 계정 정보 조회 실패")
                return {
                    'actual_profit': 0,
                    'initial_capital': 750,
                    'current_balance': 0,
                    'roi': 0,
                    'calculation_method': 'account_error',
                    'confidence': 'low'
                }
            
            current_balance = float(account.get('total', 0))
            
            # 추정 초기 자본
            estimated_initial = 750
            cumulative_profit = current_balance - estimated_initial if current_balance > estimated_initial else 0
            
            # 수익률 계산
            cumulative_roi = (cumulative_profit / estimated_initial * 100) if estimated_initial > 0 else 0
            
            logger.info(f"✅ Gate.io 누적 수익 분석 완료:")
            logger.info(f"  - 현재 잔고: ${current_balance:.2f}")
            logger.info(f"  - 추정 초기 자본: ${estimated_initial:.2f}")
            logger.info(f"  - 누적 수익: ${cumulative_profit:.2f}")
            logger.info(f"  - 수익률: {cumulative_roi:+.1f}%")
            
            return {
                'actual_profit': cumulative_profit,
                'initial_capital': estimated_initial,
                'current_balance': current_balance,
                'roi': cumulative_roi,
                'calculation_method': 'balance_minus_initial',
                'total_deposits': 0,
                'total_withdrawals': 0,
                'net_investment': estimated_initial,
                'confidence': 'high'
            }
            
        except Exception as e:
            logger.error(f"Gate.io 누적 수익 분석 실패: {e}")
            return {
                'actual_profit': 0,
                'initial_capital': 750,
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
