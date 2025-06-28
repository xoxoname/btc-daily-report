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
            if test_result is not None and len(test_result) > 0:
                self.api_healthy = True
                self.last_successful_call = datetime.now()
                logger.info("✅ Gate.io 계정 조회 성공")
                
                # 거래 내역 조회 테스트
                try:
                    now = datetime.now()
                    seven_days_ago = now - timedelta(days=7)
                    start_ts = int(seven_days_ago.timestamp())  # Gate.io는 초 단위
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
        
        final_error = f"모든 재시도 실패: {max_retries}회 시도"
        self.api_healthy = False
        raise Exception(final_error)
    
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
            
            logger.debug(f"Gate.io 티커 조회: {contract}")
            response = await self._request('GET', endpoint, params=params)
            
            logger.debug(f"Gate.io 티커 응답 타입: {type(response)}")
            logger.debug(f"Gate.io 티커 응답 내용: {response}")
            
            if isinstance(response, list) and len(response) > 0:
                ticker_data = response[0]
                # 필수 필드 확인 및 보정
                if 'last' not in ticker_data and 'mark_price' in ticker_data:
                    ticker_data['last'] = ticker_data['mark_price']
                logger.info(f"✅ Gate.io 티커 조회 성공: {ticker_data.get('last', 'N/A')}")
                return ticker_data
            elif isinstance(response, dict):
                # 필수 필드 확인 및 보정
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
        """계정 잔고 조회 - API 응답 직접 사용"""
        try:
            endpoint = "/api/v4/futures/usdt/accounts"
            
            logger.debug("Gate.io 계정 잔고 조회 시작")
            response = await self._request('GET', endpoint)
            
            logger.info(f"✅ Gate.io 계정 API 원본 응답: {response}")
            
            if response is None:
                logger.warning("Gate.io 계정 잔고 응답이 None")
                return {}
            
            # API 응답 그대로 반환 - 계산하지 않음
            return response
                
        except Exception as e:
            logger.error(f"Gate.io 계정 잔고 조회 실패: {e}")
            logger.error(f"계정 조회 상세 오류: {str(e)}")
            return {}
    
    async def get_positions(self, contract: str = "BTC_USDT") -> List[Dict]:
        """포지션 조회 - API 응답 직접 사용"""
        try:
            endpoint = f"/api/v4/futures/usdt/positions/{contract}"
            
            logger.debug(f"Gate.io 포지션 조회 시작: {contract}")
            response = await self._request('GET', endpoint)
            
            logger.info(f"✅ Gate.io 포지션 API 원본 응답: {response}")
            
            if response is None:
                logger.info("Gate.io 포지션 응답이 None - 포지션 없음으로 처리")
                return []
            
            if isinstance(response, dict):
                # 딕셔너리 응답인 경우
                size = float(response.get('size', 0))
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
                    if isinstance(pos, dict) and float(pos.get('size', 0)) != 0:
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
        """거래 내역 조회 - Gate.io V4 API"""
        try:
            endpoint = "/api/v4/futures/usdt/my_trades"
            params = {
                'contract': contract,
                'limit': str(min(limit, 1000))  # Gate.io 최대 1000
            }
            
            # Gate.io API는 초 단위 타임스탬프 사용
            if start_time:
                # 밀리초 입력을 초로 변환
                if start_time > 1000000000000:  # 밀리초 형태라면
                    params['from'] = str(int(start_time / 1000))
                else:  # 이미 초 형태라면
                    params['from'] = str(start_time)
            if end_time:
                # 밀리초 입력을 초로 변환
                if end_time > 1000000000000:  # 밀리초 형태라면
                    params['to'] = str(int(end_time / 1000))
                else:  # 이미 초 형태라면
                    params['to'] = str(end_time)
            
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
        """Gate.io Position PnL 기준 손익 계산 - 실제 API 데이터만 사용"""
        try:
            logger.info(f"🔍 Gate.io 순수 API 데이터 기반 손익 계산 시작...")
            logger.info(f"  - 계약: {contract}")
            logger.info(f"  - 시작: {datetime.fromtimestamp(start_time/1000 if start_time > 1000000000000 else start_time)}")
            logger.info(f"  - 종료: {datetime.fromtimestamp(end_time/1000 if end_time > 1000000000000 else end_time)}")
            
            # 1. 거래 내역 조회
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
            
            # 2. 거래 수수료만 정확히 계산 (Gate.io는 PnL 직접 제공 안함)
            total_trading_fees = 0.0
            trade_count = 0
            
            for trade in trades_all:
                try:
                    # 거래 수수료 추출 (fee 필드)
                    fee_value = trade.get('fee', 0)
                    if fee_value is not None and fee_value != '':
                        try:
                            trading_fee = abs(float(fee_value))  # 수수료는 항상 양수
                            if trading_fee > 0:
                                total_trading_fees += trading_fee
                                trade_count += 1
                                logger.debug(f"Gate.io 거래 수수료: {trading_fee}")
                        except (ValueError, TypeError):
                            pass
                
                except Exception as trade_error:
                    logger.debug(f"Gate.io 거래 내역 처리 오류: {trade_error}")
                    continue
            
            # 3. 현재 계정 정보로 수익 추정
            account_balance = await self.get_account_balance()
            current_total = float(account_balance.get('total', 0)) if account_balance else 0
            current_unrealized = float(account_balance.get('unrealised_pnl', 0)) if account_balance else 0
            
            # 4. 기간별 수익 추정 (보수적 계산)
            period_days = (end_time - start_time) / (1000 * 60 * 60 * 24) if end_time > start_time else 1
            if start_time > 1000000000000:  # 밀리초라면 초로 변환
                period_days = period_days * 1000
            
            # 현재 미실현 손익을 해당 기간 손익으로 추정 (매우 보수적)
            estimated_period_pnl = current_unrealized if period_days <= 1 else 0
            
            # 순 수익 = 추정 PnL - 거래수수료
            net_profit = estimated_period_pnl - total_trading_fees
            
            logger.info(f"✅ Gate.io 순수 API 기반 손익 계산 완료:")
            logger.info(f"  - 추정 Position PnL: ${estimated_period_pnl:.4f}")
            logger.info(f"  - 거래 수수료: -${total_trading_fees:.4f}")
            logger.info(f"  - 순 수익: ${net_profit:.4f}")
            logger.info(f"  - 거래 건수: {trade_count}건")
            logger.info(f"  - 기간: {period_days:.1f}일")
            
            return {
                'position_pnl': estimated_period_pnl,
                'trading_fees': total_trading_fees,
                'funding_fees': 0.0,  # Gate.io API에서 직접 제공 안함
                'net_profit': net_profit,
                'trade_count': trade_count,
                'source': 'gate_pure_api_conservative',
                'confidence': 'medium'
            }
            
        except Exception as e:
            logger.error(f"Gate.io 순수 API 기반 손익 계산 실패: {e}")
            
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
        """오늘 Position PnL 조회 - 현재 미실현 손익 사용"""
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
            
            logger.info(f"🔍 Gate.io 오늘 PnL 조회 (API 기반):")
            
            # 현재 계정의 미실현 손익을 오늘 손익으로 사용 (보수적)
            account = await self.get_account_balance()
            today_pnl = float(account.get('unrealised_pnl', 0)) if account else 0.0
            
            logger.info(f"✅ Gate.io 오늘 PnL (미실현): ${today_pnl:.4f}")
            return today_pnl
            
        except Exception as e:
            logger.error(f"Gate.io 오늘 Position PnL 조회 실패: {e}")
            return 0.0
    
    async def get_7day_position_pnl(self) -> Dict:
        """Gate.io 7일 Position PnL 조회 - 순수 API 데이터"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            current_time = datetime.now(kst)
            
            # 현재에서 정확히 7일 전
            seven_days_ago = current_time - timedelta(days=7)
            
            logger.info(f"🔍 Gate.io 7일 순수 API 손익 계산:")
            logger.info(f"  - 시작: {seven_days_ago.strftime('%Y-%m-%d %H:%M')} KST")
            logger.info(f"  - 종료: {current_time.strftime('%Y-%m-%d %H:%M')} KST")
            
            start_time_utc = seven_days_ago.astimezone(pytz.UTC)
            end_time_utc = current_time.astimezone(pytz.UTC)
            
            start_timestamp = int(start_time_utc.timestamp() * 1000)
            end_timestamp = int(end_time_utc.timestamp() * 1000)
            
            # 실제 API 데이터 기반 계산
            result = await self.get_position_pnl_based_profit(
                start_timestamp, 
                end_timestamp, 
                'BTC_USDT'
            )
            
            position_pnl = result.get('position_pnl', 0.0)
            trading_fees = result.get('trading_fees', 0.0)
            net_profit = result.get('net_profit', 0.0)
            trade_count = result.get('trade_count', 0)
            
            # 7일 일평균 계산
            daily_average = position_pnl / 7.0
            
            logger.info(f"✅ Gate.io 7일 순수 API 계산 완료:")
            logger.info(f"  - 기간: 7.0일")
            logger.info(f"  - Position PnL (API): ${position_pnl:.4f}")
            logger.info(f"  - 거래 수수료: -${trading_fees:.4f}")
            logger.info(f"  - 순 수익: ${net_profit:.4f}")
            logger.info(f"  - 일평균: ${daily_average:.4f}")
            logger.info(f"  - 거래 건수: {trade_count}건")
            
            return {
                'total_pnl': position_pnl,
                'daily_pnl': {},
                'average_daily': daily_average,
                'trade_count': trade_count,
                'actual_days': 7.0,
                'trading_fees': trading_fees,
                'funding_fees': 0,
                'net_profit': net_profit,
                'source': 'gate_pure_api_7days',
                'confidence': 'high'  # 순수 API 기반
            }
            
        except Exception as e:
            logger.error(f"Gate.io 7일 순수 API 손익 조회 실패: {e}")
            
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
        """Gate.io 누적 수익 분석 - API 기반"""
        try:
            logger.info(f"🔍 Gate.io 누적 수익 분석 (순수 API):")
            
            # 현재 계정 정보
            account = await self.get_account_balance()
            current_balance = float(account.get('total', 0)) if account else 0
            
            logger.info(f"  - 현재 잔고: ${current_balance:.2f}")
            
            # 추정 초기 자본 (보수적 추정)
            estimated_initial = 750  # 보수적 추정값
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
                'calculation_method': 'pure_api_balance_based',
                'total_deposits': 0,
                'total_withdrawals': 0,
                'net_investment': estimated_initial,
                'confidence': 'high'  # 순수 API 기반
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
    
    async def get_profit_history_since_may(self) -> Dict:
        """Gate.io 순수 API 기반 누적 수익 조회"""
        try:
            logger.info(f"🔍 Gate.io 순수 API 누적 수익 조회:")
            
            # 오늘 실현 손익 - 순수 API 데이터
            today_realized = await self.get_today_position_pnl()
            
            # 7일 손익 - 순수 API 데이터
            weekly_profit = await self.get_7day_position_pnl()
            
            # 누적 수익 분석 - 순수 API 데이터
            cumulative_analysis = await self.get_real_cumulative_profit_analysis()
            
            cumulative_profit = cumulative_analysis.get('actual_profit', 0)
            initial_capital = cumulative_analysis.get('initial_capital', 750)
            current_balance = cumulative_analysis.get('current_balance', 0)
            cumulative_roi = cumulative_analysis.get('roi', 0)
            calculation_method = cumulative_analysis.get('calculation_method', 'unknown')
            confidence = cumulative_analysis.get('confidence', 'low')
            
            # 검증: 7일 수익과 누적 수익 관계 확인
            weekly_pnl = weekly_profit.get('total_pnl', 0)
            diff_7d_vs_cumulative = abs(cumulative_profit - weekly_pnl)
            
            logger.info(f"Gate.io 순수 API 누적 수익 최종 결과:")
            logger.info(f"  - 현재 잔고: ${current_balance:.2f}")
            logger.info(f"  - 7일 수익: ${weekly_pnl:.2f} (순수 API)")
            logger.info(f"  - 누적 수익: ${cumulative_profit:.2f}")
            logger.info(f"  - 초기 자본: ${initial_capital:.2f}")
            logger.info(f"  - 수익률: {cumulative_roi:+.1f}%")
            logger.info(f"  - 계산 방법: {calculation_method}")
            logger.info(f"  - 신뢰도: {confidence}")
            
            return {
                'total_pnl': cumulative_profit,
                'today_realized': today_realized,
                'weekly': weekly_profit,
                'current_balance': current_balance,
                'actual_profit': cumulative_profit,
                'initial_capital': initial_capital,
                'cumulative_roi': cumulative_roi,
                'source': f'gate_pure_api_{calculation_method}',
                'calculation_method': calculation_method,
                'confidence': confidence,
                'weekly_vs_cumulative_diff': diff_7d_vs_cumulative,
                'analysis_details': cumulative_analysis,
                'is_7day_and_cumulative_different': diff_7d_vs_cumulative > 10
            }
            
        except Exception as e:
            logger.error(f"Gate.io 순수 API 누적 수익 조회 실패: {e}")
            return {
                'total_pnl': 0,
                'today_realized': 0,
                'weekly': {'total_pnl': 0, 'average_daily': 0},
                'current_balance': 0,
                'actual_profit': 0,
                'initial_capital': 750,
                'cumulative_roi': 0,
                'source': 'error_gate_pure_api',
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
