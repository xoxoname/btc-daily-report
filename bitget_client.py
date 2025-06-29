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
        self.max_consecutive_failures = 5  # 임계값 낮춤
        
        # API 키 검증 상태
        self.api_keys_validated = False
        
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
            logger.info("Bitget 클라이언트 세션 초기화 완료")
        
    async def initialize(self):
        self._initialize_session()
        await self._validate_api_keys()
        logger.info("Bitget 클라이언트 초기화 완료")
    
    async def _validate_api_keys(self):
        try:
            logger.info("비트겟 API 키 유효성 검증 시작...")
            
            # 계정 정보 조회로 API 키 검증 (더 안정적인 엔드포인트)
            endpoint = "/api/v2/mix/account/accounts"
            params = {
                'productType': 'USDT-FUTURES'
            }
            
            response = await self._request('GET', endpoint, params=params)
            
            if response is not None and isinstance(response, (list, dict)):
                self.api_keys_validated = True
                self.api_connection_healthy = True
                self.consecutive_failures = 0
                logger.info("✅ 비트겟 API 키 검증 성공")
            else:
                logger.error("❌ 비트겟 API 키 검증 실패: 잘못된 응답")
                self.api_keys_validated = False
                
        except Exception as e:
            logger.error(f"❌ 비트겟 API 키 검증 실패: {e}")
            self.api_keys_validated = False
    
    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
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
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None, max_retries: int = 2) -> Dict:
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
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"비트겟 API 요청 (시도 {attempt + 1}/{max_retries}): {method} {endpoint}")
                
                async with self.session.request(method, url, headers=headers, data=body) as response:
                    response_text = await response.text()
                    
                    if not response_text.strip():
                        error_msg = f"빈 응답 받음 (상태: {response.status})"
                        logger.warning(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        else:
                            self._record_failure(error_msg)
                            return {}
                    
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: {response_text[:200]}"
                        logger.error(f"비트겟 API HTTP 오류: {error_msg}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        else:
                            self._record_failure(error_msg)
                            return {}
                    
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError as json_error:
                        error_msg = f"JSON 파싱 실패: {json_error}"
                        logger.error(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        else:
                            self._record_failure(error_msg)
                            return {}
                    
                    if response_data.get('code') != '00000':
                        error_msg = f"API 응답 오류: {response_data.get('msg', 'Unknown error')}"
                        logger.error(error_msg)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        else:
                            self._record_failure(error_msg)
                            return {}
                    
                    self._record_success()
                    return response_data.get('data', {})
                    
            except asyncio.TimeoutError:
                error_msg = f"요청 타임아웃 (시도 {attempt + 1})"
                logger.warning(error_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    self._record_failure(error_msg)
                    return {}
                    
            except Exception as e:
                error_msg = f"예상치 못한 오류 (시도 {attempt + 1}): {e}"
                logger.error(error_msg)
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    self._record_failure(error_msg)
                    return {}
        
        final_error = f"모든 재시도 실패: {max_retries}회 시도"
        self._record_failure(final_error)
        return {}
    
    def _record_success(self):
        self.api_connection_healthy = True
        self.consecutive_failures = 0
        self.last_successful_call = datetime.now()
    
    def _record_failure(self, error_msg: str):
        self.consecutive_failures += 1
        
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.api_connection_healthy = False
            logger.error(f"비트겟 API 연결 비정상 상태: 연속 {self.consecutive_failures}회 실패")
        
        logger.warning(f"비트겟 API 실패 기록: {error_msg} (연속 실패: {self.consecutive_failures}회)")
    
    async def get_ticker(self, symbol: str = None) -> Dict:
        symbol = symbol or self.config.symbol
        
        try:
            endpoint = "/api/v2/mix/market/ticker"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'
            }
            
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list) and len(response) > 0:
                ticker_data = response[0]
            elif isinstance(response, dict):
                ticker_data = response
            else:
                logger.warning(f"예상치 못한 티커 응답 형식: {type(response)}")
                return {}
            
            if self._validate_ticker_data(ticker_data):
                normalized_ticker = self._normalize_ticker_data(ticker_data)
                logger.info(f"✅ 티커 조회 성공: ${normalized_ticker.get('last', 'N/A')}")
                return normalized_ticker
            else:
                logger.warning("티커 데이터 검증 실패")
                return {}
                
        except Exception as e:
            logger.error(f"티커 조회 실패: {e}")
            return {}
    
    def _validate_ticker_data(self, ticker_data: Dict) -> bool:
        if not isinstance(ticker_data, dict):
            return False
        
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
        
        return False
    
    def _normalize_ticker_data(self, ticker_data: Dict) -> Dict:
        try:
            normalized = {}
            
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
                                change_val = float(value)
                                if abs(change_val) > 1:
                                    change_val = change_val / 100
                                normalized[target_field] = change_val
                            else:
                                normalized[target_field] = float(value)
                            break
                        except:
                            continue
            
            if 'last' not in normalized:
                normalized['last'] = 0
            if 'changeUtc' not in normalized:
                normalized['changeUtc'] = 0
            if 'volume' not in normalized:
                normalized['volume'] = 0
            
            normalized['_original'] = ticker_data
            
            return normalized
            
        except Exception as e:
            logger.error(f"티커 데이터 정규화 실패: {e}")
            return ticker_data
    
    async def get_funding_rate(self, symbol: str = None) -> Dict:
        symbol = symbol or self.config.symbol
        
        try:
            endpoint = "/api/v2/mix/market/funding-time"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'
            }
            
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list) and len(response) > 0:
                funding_data = response[0]
            elif isinstance(response, dict):
                funding_data = response
            else:
                logger.warning(f"예상치 못한 펀딩비 응답 형식: {type(response)}")
                return {'fundingRate': 0.0, 'fundingTime': ''}
            
            normalized_funding = self._normalize_funding_data(funding_data)
            logger.info(f"✅ 펀딩비 조회 성공: {normalized_funding.get('fundingRate', 'N/A')}")
            return normalized_funding
                
        except Exception as e:
            logger.error(f"펀딩비 조회 실패: {e}")
            return {'fundingRate': 0.0, 'fundingTime': ''}
    
    def _normalize_funding_data(self, funding_data: Dict) -> Dict:
        try:
            normalized = {}
            
            funding_fields = ['fundingRate', 'fundRate', 'rate', 'currentFundingRate', 'fundingFeeRate']
            
            for field in funding_fields:
                value = funding_data.get(field)
                if value is not None:
                    try:
                        normalized['fundingRate'] = float(value)
                        break
                    except:
                        continue
            
            if 'fundingRate' not in normalized:
                normalized['fundingRate'] = 0.0
            
            time_fields = ['fundingTime', 'nextFundingTime', 'fundTime', 'fundingInterval']
            for field in time_fields:
                value = funding_data.get(field)
                if value is not None:
                    normalized[field] = value
                    break
            
            normalized['_original'] = funding_data
            
            return normalized
            
        except Exception as e:
            logger.error(f"펀딩비 데이터 정규화 실패: {e}")
            return {
                'fundingRate': 0.0,
                'fundingTime': '',
                '_error': str(e)
            }
    
    async def get_positions(self, symbol: str = None) -> List[Dict]:
        symbol = symbol or self.config.symbol
        
        try:
            endpoint = "/api/v2/mix/position/all-position"
            params = {
                'productType': 'USDT-FUTURES',
                'marginCoin': 'USDT'
            }
            
            response = await self._request('GET', endpoint, params=params)
            
            if not response:
                logger.info("포지션 응답이 비어있음")
                return []
            
            positions = []
            if isinstance(response, list):
                positions = response
            elif isinstance(response, dict) and 'list' in response:
                positions = response['list']
            elif isinstance(response, dict):
                positions = [response]
            
            active_positions = []
            for pos in positions:
                if not isinstance(pos, dict):
                    continue
                    
                pos_symbol = pos.get('symbol', '')
                if symbol and pos_symbol != symbol:
                    continue
                
                total_size = float(pos.get('total', 0))
                if total_size > 0:
                    logger.info(f"🎯 활성 포지션 발견:")
                    logger.info(f"  - 심볼: {pos_symbol}")
                    logger.info(f"  - 사이즈: {total_size}")
                    logger.info(f"  - marginSize: ${float(pos.get('marginSize', 0)):.2f}")
                    
                    active_positions.append(pos)
            
            return active_positions
            
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []
    
    async def get_account_info(self) -> Dict:
        try:
            endpoint = "/api/v2/mix/account/accounts"
            params = {
                'productType': 'USDT-FUTURES'
            }
            
            response = await self._request('GET', endpoint, params=params)
            
            if not response:
                logger.error("계정 정보 응답이 비어있음")
                return {}
            
            # Bitget V2 API 응답 구조 처리 개선
            account_data = {}
            if isinstance(response, list) and len(response) > 0:
                # USDT 계정 찾기
                for account in response:
                    if account.get('marginCoin') == 'USDT':
                        account_data = account
                        break
                if not account_data:
                    account_data = response[0]
            elif isinstance(response, dict):
                account_data = response
            
            # 필수 필드 검증
            required_fields = ['usdtEquity', 'available']
            for field in required_fields:
                if field not in account_data or account_data[field] is None:
                    logger.warning(f"계정 정보에서 {field} 필드 누락")
                    account_data[field] = '0'
            
            # 데이터 타입 안전성 보장
            try:
                equity = float(account_data.get('usdtEquity', 0))
                available = float(account_data.get('available', 0))
                unrealized_pl = float(account_data.get('unrealizedPL', 0))
                
                logger.info(f"✅ Bitget 계정 정보 조회 성공:")
                logger.info(f"  - 총 자산: ${equity:.2f}")
                logger.info(f"  - 가용 자산: ${available:.2f}")
                logger.info(f"  - 미실현 손익: ${unrealized_pl:.2f}")
                
                return account_data
                
            except (ValueError, TypeError) as e:
                logger.error(f"계정 정보 데이터 변환 실패: {e}")
                return {}
            
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            return {}
    
    async def get_accurate_used_margin(self) -> float:
        try:
            positions = await self.get_positions(self.config.symbol)
            total_margin_size = 0.0
            
            for position in positions:
                total_size = float(position.get('total', 0))
                if total_size > 0:
                    margin_size = float(position.get('marginSize', 0))
                    total_margin_size += margin_size
                    
                    logger.info(f"📊 포지션별 증거금:")
                    logger.info(f"  - marginSize: ${margin_size:.2f}")
            
            logger.info(f"🎯 총 사용 증거금: ${total_margin_size:.2f}")
            return total_margin_size
            
        except Exception as e:
            logger.error(f"실제 사용 증거금 조회 실패: {e}")
            return 0.0
    
    async def get_trade_fills(self, symbol: str = None, start_time: int = None, end_time: int = None, limit: int = 100) -> List[Dict]:
        symbol = symbol or self.config.symbol
        
        try:
            endpoint = "/api/v2/mix/order/fill-history"
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
            
            response = await self._request('GET', endpoint, params=params)
            
            fills = []
            if isinstance(response, dict):
                for field in ['fillList', 'list', 'data', 'fills']:
                    if field in response and isinstance(response[field], list):
                        fills = response[field]
                        break
            elif isinstance(response, list):
                fills = response
            
            if fills:
                logger.info(f"✅ 거래 내역 조회 성공: {len(fills)}건")
                return fills
            else:
                logger.debug("거래 내역 없음")
                return []
                
        except Exception as e:
            logger.error(f"거래 내역 조회 실패: {e}")
            return []
    
    async def get_position_pnl_based_profit(self, start_time: int, end_time: int, symbol: str = None) -> Dict:
        try:
            symbol = symbol or self.config.symbol
            
            logger.info(f"🔍 Position PnL 기준 손익 계산 시작...")
            logger.info(f"  - 심볼: {symbol}")
            logger.info(f"  - 시작: {datetime.fromtimestamp(start_time/1000)}")
            logger.info(f"  - 종료: {datetime.fromtimestamp(end_time/1000)}")
            
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
            
            total_position_pnl = 0.0
            total_trading_fees = 0.0
            total_funding_fees = 0.0
            trade_count = 0
            
            for fill in fills:
                try:
                    position_pnl = 0.0
                    pnl_fields = ['pnl', 'profit', 'realizedPnl', 'closedPnl']
                    
                    for field in pnl_fields:
                        if field in fill and fill[field] is not None:
                            try:
                                position_pnl = float(fill[field])
                                if position_pnl != 0:
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    trading_fee = 0.0
                    fee_fields = ['fee', 'tradingFee', 'totalFee']
                    
                    for field in fee_fields:
                        if field in fill and fill[field] is not None:
                            try:
                                fee_value = float(fill[field])
                                if fee_value != 0:
                                    trading_fee = abs(fee_value)
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    funding_fee = 0.0
                    funding_fields = ['fundingFee', 'funding', 'fundFee']
                    
                    for field in funding_fields:
                        if field in fill and fill[field] is not None:
                            try:
                                funding_value = float(fill[field])
                                if funding_value != 0:
                                    funding_fee = funding_value
                                    break
                            except (ValueError, TypeError):
                                continue
                    
                    if position_pnl != 0 or trading_fee != 0 or funding_fee != 0:
                        total_position_pnl += position_pnl
                        total_trading_fees += trading_fee
                        total_funding_fees += funding_fee
                        trade_count += 1
                
                except Exception as fill_error:
                    logger.debug(f"거래 내역 처리 오류: {fill_error}")
                    continue
            
            net_profit = total_position_pnl + total_funding_fees - total_trading_fees
            
            logger.info(f"✅ Position PnL 기준 손익 계산 완료:")
            logger.info(f"  - Position PnL: ${total_position_pnl:.4f}")
            logger.info(f"  - 거래 수수료: -${total_trading_fees:.4f}")
            logger.info(f"  - 펀딩비: {total_funding_fees:+.4f}")
            logger.info(f"  - 순 수익: ${net_profit:.4f}")
            logger.info(f"  - 거래 건수: {trade_count}건")
            
            return {
                'position_pnl': total_position_pnl,
                'trading_fees': total_trading_fees,
                'funding_fees': total_funding_fees,
                'net_profit': net_profit,
                'trade_count': trade_count,
                'source': 'bitget_v2_api_accurate',
                'confidence': 'high'
            }
            
        except Exception as e:
            logger.error(f"Position PnL 기준 손익 계산 실패: {e}")
            
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
            
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            start_time_utc = today_start.astimezone(pytz.UTC)
            end_time_utc = now.astimezone(pytz.UTC)
            
            start_timestamp = int(start_time_utc.timestamp() * 1000)
            end_timestamp = int(end_time_utc.timestamp() * 1000)
            
            result = await self.get_position_pnl_based_profit(
                start_timestamp, 
                end_timestamp, 
                self.config.symbol
            )
            
            return result.get('position_pnl', 0.0)
            
        except Exception as e:
            logger.error(f"오늘 Position PnL 조회 실패: {e}")
            return 0.0
    
    async def get_7day_position_pnl(self) -> Dict:
        try:
            kst = pytz.timezone('Asia/Seoul')
            current_time = datetime.now(kst)
            
            seven_days_ago = current_time - timedelta(days=7)
            
            logger.info(f"🔍 비트겟 7일 Position PnL 계산:")
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
            
            result = await self.get_position_pnl_based_profit(
                start_timestamp, 
                end_timestamp, 
                self.config.symbol
            )
            
            position_pnl = result.get('position_pnl', 0.0)
            daily_average = position_pnl / duration_days if duration_days > 0 else 0
            
            logger.info(f"✅ 비트겟 7일 Position PnL 계산 완료:")
            logger.info(f"  - 실제 기간: {duration_days:.1f}일")
            logger.info(f"  - Position PnL: ${position_pnl:.4f}")
            logger.info(f"  - 일평균: ${daily_average:.4f}")
            
            return {
                'total_pnl': position_pnl,
                'daily_pnl': {},
                'average_daily': daily_average,
                'trade_count': result.get('trade_count', 0),
                'actual_days': duration_days,
                'trading_fees': result.get('trading_fees', 0),
                'funding_fees': result.get('funding_fees', 0),
                'net_profit': result.get('net_profit', 0),
                'source': 'bitget_7days_v2_api',
                'confidence': 'high'
            }
            
        except Exception as e:
            logger.error(f"비트겟 7일 Position PnL 조회 실패: {e}")
            
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
            orders = response if isinstance(response, list) else []
            return orders
            
        except Exception as e:
            logger.error(f"주문 조회 실패: {e}")
            return []
    
    async def get_order_history(self, symbol: str = None, status: str = 'filled', 
                              start_time: int = None, end_time: int = None, limit: int = 100) -> List[Dict]:
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
            
            if isinstance(response, dict) and 'orderList' in response:
                return response['orderList']
            elif isinstance(response, list):
                return response
            
            return []
            
        except Exception as e:
            logger.error(f"주문 내역 조회 실패: {e}")
            return []
    
    async def get_recent_filled_orders(self, symbol: str = None, minutes: int = 5) -> List[Dict]:
        try:
            symbol = symbol or self.config.symbol
            
            now = datetime.now()
            start_time = now - timedelta(minutes=minutes)
            start_timestamp = int(start_time.timestamp() * 1000)
            end_timestamp = int(now.timestamp() * 1000)
            
            filled_orders = await self.get_order_history(
                symbol=symbol,
                status='filled',
                start_time=start_timestamp,
                end_time=end_timestamp,
                limit=50
            )
            
            logger.info(f"최근 {minutes}분간 체결된 주문: {len(filled_orders)}건")
            
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
        symbol = symbol or self.config.symbol
        
        try:
            endpoint = "/api/v2/mix/order/plan-orders-pending"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'
            }
            
            if status:
                params['status'] = status
            
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, dict):
                if 'orderList' in response:
                    return response['orderList']
                elif 'data' in response and isinstance(response['data'], list):
                    return response['data']
                elif isinstance(response.get('data'), dict) and 'orderList' in response['data']:
                    return response['data']['orderList']
            elif isinstance(response, list):
                return response
            
            return []
            
        except Exception as e:
            logger.error(f"예약 주문 조회 실패: {e}")
            return []
    
    async def get_tp_sl_orders(self, symbol: str = None, status: str = 'live') -> List[Dict]:
        symbol = symbol or self.config.symbol
        
        try:
            endpoint = "/api/v2/mix/order/stop-orders-pending"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'
            }
            
            if status:
                params['status'] = status
            
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, dict):
                if 'orderList' in response:
                    return response['orderList']
                elif 'data' in response and isinstance(response['data'], list):
                    return response['data']
                elif isinstance(response.get('data'), dict) and 'orderList' in response['data']:
                    return response['data']['orderList']
            elif isinstance(response, list):
                return response
            
            return []
            
        except Exception as e:
            logger.error(f"TP/SL 주문 조회 실패: {e}")
            return []
    
    async def get_all_plan_orders_with_tp_sl(self, symbol: str = None) -> Dict:
        symbol = symbol or self.config.symbol
        
        try:
            logger.info(f"🔍 전체 플랜 주문 조회 시작: {symbol}")
            
            plan_orders_task = self.get_plan_orders(symbol, 'live')
            tp_sl_orders_task = self.get_tp_sl_orders(symbol, 'live')
            
            plan_orders, tp_sl_orders = await asyncio.gather(
                plan_orders_task, 
                tp_sl_orders_task, 
                return_exceptions=True
            )
            
            if isinstance(plan_orders, Exception):
                logger.error(f"예약 주문 조회 오류: {plan_orders}")
                plan_orders = []
            
            if isinstance(tp_sl_orders, Exception):
                logger.error(f"TP/SL 주문 조회 오류: {tp_sl_orders}")
                tp_sl_orders = []
            
            plan_count = len(plan_orders) if plan_orders else 0
            tp_sl_count = len(tp_sl_orders) if tp_sl_orders else 0
            total_count = plan_count + tp_sl_count
            
            logger.info(f"📊 전체 플랜 주문 조회 결과:")
            logger.info(f"   - 예약 주문: {plan_count}개")
            logger.info(f"   - TP/SL 주문: {tp_sl_count}개")
            logger.info(f"   - 총합: {total_count}개")
            
            return {
                'plan_orders': plan_orders or [],
                'tp_sl_orders': tp_sl_orders or [],
                'total_count': total_count,
                'plan_count': plan_count,
                'tp_sl_count': tp_sl_count
            }
            
        except Exception as e:
            logger.error(f"전체 플랜 주문 조회 실패: {e}")
            return {
                'plan_orders': [],
                'tp_sl_orders': [],
                'total_count': 0,
                'plan_count': 0,
                'tp_sl_count': 0,
                'error': str(e)
            }
    
    async def close(self):
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
