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
        
    def _initialize_session(self):
        """세션 초기화"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            logger.info("Bitget 클라이언트 세션 초기화 완료")
        
    async def initialize(self):
        """클라이언트 초기화"""
        self._initialize_session()
        logger.info("Bitget 클라이언트 초기화 완료")
    
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
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """API 요청"""
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
        
        try:
            logger.info(f"API 요청: {method} {url}")
            async with self.session.request(method, url, headers=headers, data=body) as response:
                response_text = await response.text()
                logger.info(f"API 응답 상태: {response.status}")
                logger.debug(f"API 응답 내용: {response_text[:500]}")
                
                response_data = json.loads(response_text)
                
                if response.status != 200:
                    logger.error(f"API 요청 실패: {response.status} - {response_data}")
                    raise Exception(f"API 요청 실패: {response_data}")
                
                if response_data.get('code') != '00000':
                    logger.error(f"API 응답 오류: {response_data}")
                    raise Exception(f"API 응답 오류: {response_data}")
                
                return response_data.get('data', {})
                
        except Exception as e:
            logger.error(f"API 요청 중 오류: {e}")
            raise
    
    async def get_ticker(self, symbol: str = None) -> Dict:
        """현재가 정보 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/market/ticker"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES'
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            if isinstance(response, list) and len(response) > 0:
                return response[0]
            return response
        except Exception as e:
            logger.error(f"현재가 조회 실패: {e}")
            raise
    
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
    
    async def get_trade_fills(self, symbol: str = None, start_time: int = None, end_time: int = None, limit: int = 100) -> List[Dict]:
        """거래 체결 내역 조회 (V2 API) - 페이징 처리 포함"""
        symbol = symbol or self.config.symbol
        
        # 시간 제한 확인
        if start_time and end_time:
            max_days = 7
            time_diff = end_time - start_time
            max_time_diff = max_days * 24 * 60 * 60 * 1000
            
            if time_diff > max_time_diff:
                start_time = end_time - max_time_diff
                logger.info(f"7일 제한으로 조정: {datetime.fromtimestamp(start_time/1000)} ~ {datetime.fromtimestamp(end_time/1000)}")
        
        # 페이징 처리로 모든 거래 조회
        return await self._get_all_fills_for_period(symbol, start_time, end_time)
    
    async def get_profit_loss_history(self, symbol: str = None, days: int = 7) -> Dict:
        """손익 내역 조회 - 더 긴 기간 조회 후 필터링"""
        try:
            symbol = symbol or self.config.symbol
            
            # KST 기준 현재 시간
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 조회 기간 설정
            # days = 7이면: 오늘 포함 7일 (6일 전 0시부터 현재까지)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_start = today_start - timedelta(days=days-1)
            period_end = now
            
            # 7일 이하인 경우 더 긴 기간을 조회하여 안정성 확보
            if days <= 7:
                # 10일치를 조회한 후 필터링
                extended_days = 10
                extended_start = today_start - timedelta(days=extended_days-1)
                
                # UTC로 변환하여 타임스탬프 생성
                start_time_utc = extended_start.astimezone(pytz.UTC)
                end_time_utc = period_end.astimezone(pytz.UTC)
                
                start_time = int(start_time_utc.timestamp() * 1000)
                end_time = int(end_time_utc.timestamp() * 1000)
                
                logger.info(f"=== {days}일 손익을 위해 {extended_days}일 조회 ===")
                logger.info(f"전체 조회 기간: {extended_start.strftime('%Y-%m-%d %H:%M')} ~ {period_end.strftime('%Y-%m-%d %H:%M')} (KST)")
                logger.info(f"실제 필터링 기간: {period_start.strftime('%Y-%m-%d %H:%M')} ~ {period_end.strftime('%Y-%m-%d %H:%M')} (KST)")
            else:
                # 7일 초과인 경우 원래대로
                start_time_utc = period_start.astimezone(pytz.UTC)
                end_time_utc = period_end.astimezone(pytz.UTC)
                
                start_time = int(start_time_utc.timestamp() * 1000)
                end_time = int(end_time_utc.timestamp() * 1000)
                
                logger.info(f"=== {days}일 손익 조회 ===")
                logger.info(f"기간: {period_start.strftime('%Y-%m-%d %H:%M')} ~ {period_end.strftime('%Y-%m-%d %H:%M')} (KST)")
            
            logger.info(f"타임스탬프: {start_time} ~ {end_time}")
            
            # 예상 날짜 목록 출력
            logger.info(f"예상 거래일 목록 ({days}일):")
            expected_dates = []
            for i in range(days):
                date = period_start + timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                expected_dates.append(date_str)
                logger.info(f"  - {date_str}")
            
            total_pnl = 0.0
            daily_pnl = {}
            total_fees = 0.0
            trade_count = 0
            
            # 모든 거래 내역 조회 (페이징 처리)
            all_fills = []
            
            # 기간별 조회
            if days <= 7:
                # 10일치 한 번에 조회
                all_fills = await self._get_all_fills_for_period_with_retries(symbol, start_time, end_time)
            elif days > 7:
                # 7일씩 나눠서 조회
                current_start = start_time
                
                while current_start < end_time:
                    current_end = min(current_start + (7 * 24 * 60 * 60 * 1000), end_time)
                    
                    # KST로 변환하여 로깅
                    start_kst = datetime.fromtimestamp(current_start/1000, tz=kst)
                    end_kst = datetime.fromtimestamp(current_end/1000, tz=kst)
                    logger.info(f"부분 조회: {start_kst.strftime('%Y-%m-%d')} ~ {end_kst.strftime('%Y-%m-%d')}")
                    
                    # 해당 기간의 모든 거래 조회 (페이징 처리)
                    period_fills = await self._get_all_fills_for_period_with_retries(symbol, current_start, current_end)
                    all_fills.extend(period_fills)
                    
                    current_start = current_end
                    await asyncio.sleep(0.2)  # API 요청 간격
            
            logger.info(f"총 조회된 거래 수: {len(all_fills)}건")
            
            # 거래 처리 - 실제 필요한 기간만 필터링
            filtered_count = 0
            for trade in all_fills:
                try:
                    # 시간 필드 찾기
                    trade_time = None
                    for time_field in ['cTime', 'createdTime', 'createTime', 'time']:
                        if time_field in trade:
                            trade_time = int(trade[time_field])
                            break
                    
                    if not trade_time:
                        continue
                    
                    # KST 기준 날짜
                    trade_date_kst = datetime.fromtimestamp(trade_time / 1000, tz=kst)
                    trade_date_str = trade_date_kst.strftime('%Y-%m-%d')
                    
                    # 실제 조회 기간 내의 거래만 처리
                    if trade_date_kst < period_start or trade_date_kst > period_end:
                        logger.debug(f"기간 외 거래 제외: {trade_date_str}")
                        continue
                    
                    filtered_count += 1
                    
                    # 손익 필드 찾기
                    profit = 0.0
                    for profit_field in ['profit', 'realizedPL', 'realizedPnl', 'pnl']:
                        if profit_field in trade:
                            val = trade[profit_field]
                            if val and str(val).replace('.', '').replace('-', '').isdigit():
                                profit = float(val)
                                break
                    
                    # 수수료 계산
                    fee = 0.0
                    
                    # feeDetail 확인
                    fee_detail = trade.get('feeDetail', [])
                    if isinstance(fee_detail, list):
                        for fee_info in fee_detail:
                            if isinstance(fee_info, dict):
                                fee += abs(float(fee_info.get('totalFee', 0)))
                    
                    # fee 필드 확인
                    if fee == 0 and 'fee' in trade:
                        fee = abs(float(trade.get('fee', 0)))
                    
                    # fees 필드 확인
                    if fee == 0 and 'fees' in trade:
                        fee = abs(float(trade.get('fees', 0)))
                    
                    # 실현 손익 = profit - 수수료
                    if profit != 0 or fee != 0:
                        realized_pnl = profit - fee
                        total_pnl += realized_pnl
                        total_fees += fee
                        trade_count += 1
                        
                        if trade_date_str not in daily_pnl:
                            daily_pnl[trade_date_str] = 0
                        daily_pnl[trade_date_str] += realized_pnl
                        
                        logger.debug(f"거래 포함: {trade_date_str} profit={profit:.2f}, fee={fee:.2f}, pnl={realized_pnl:.2f}")
                    
                except Exception as e:
                    logger.warning(f"거래 파싱 오류: {e}")
                    continue
            
            logger.info(f"필터링 후 거래 수: {filtered_count}건 (실제 손익 계산: {trade_count}건)")
            
            # 결과 로그
            if daily_pnl:
                logger.info("=== 일별 손익 내역 ===")
                for date, pnl in sorted(daily_pnl.items()):
                    logger.info(f"  {date}: ${pnl:,.2f}")
            else:
                logger.warning("조회된 손익 내역이 없습니다")
            
            # 누락된 날짜 확인
            logger.info("누락된 거래일 확인:")
            for expected_date in expected_dates:
                if expected_date not in daily_pnl:
                    logger.warning(f"  - {expected_date}: 거래 없음")
            
            logger.info(f"=== {days}일 총 손익: ${total_pnl:,.2f} (거래 {trade_count}건, 수수료 ${total_fees:.2f}) ===")
            
            return {
                'total_pnl': total_pnl,
                'daily_pnl': daily_pnl,
                'days': days,
                'average_daily': total_pnl / days if days > 0 else 0,
                'trade_count': trade_count,
                'total_fees': total_fees
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
    
    async def _get_all_fills_for_period_with_retries(self, symbol: str, start_time: int, end_time: int, max_retries: int = 3) -> List[Dict]:
        """특정 기간의 모든 거래 내역 조회 (재시도 포함)"""
        for retry in range(max_retries):
            try:
                fills = await self._get_all_fills_for_period(symbol, start_time, end_time)
                if fills or retry == max_retries - 1:
                    return fills
                logger.warning(f"조회된 거래가 없음. 재시도 {retry + 1}/{max_retries}")
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"거래 조회 실패 (재시도 {retry + 1}/{max_retries}): {e}")
                if retry < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    raise
        return []
    
    async def _get_all_fills_for_period(self, symbol: str, start_time: int, end_time: int) -> List[Dict]:
        """특정 기간의 모든 거래 내역 조회 (페이징 처리)"""
        all_fills = []
        last_id = None
        page = 0
        
        # 날짜 로깅
        kst = pytz.timezone('Asia/Seoul')
        start_kst = datetime.fromtimestamp(start_time/1000, tz=kst)
        end_kst = datetime.fromtimestamp(end_time/1000, tz=kst)
        logger.info(f"기간별 전체 거래 조회: {start_kst.strftime('%Y-%m-%d %H:%M')} ~ {end_kst.strftime('%Y-%m-%d %H:%M')}")
        
        # ID 기반 중복 체크를 위한 세트
        seen_ids = set()
        
        while page < 50:  # 최대 50페이지까지
            try:
                endpoint = "/api/v2/mix/order/fill-history"
                params = {
                    'symbol': symbol,
                    'productType': 'USDT-FUTURES',
                    'startTime': str(start_time),
                    'endTime': str(end_time),
                    'limit': '500'  # 최대 한도
                }
                
                if last_id:
                    params['lastEndId'] = str(last_id)
                
                logger.info(f"페이지 {page + 1} 조회 중... (lastId: {last_id})")
                response = await self._request('GET', endpoint, params=params)
                
                fills = []
                if response is None:
                    logger.warning("응답이 None입니다")
                    break
                elif isinstance(response, dict):
                    fills = response.get('fillList', response.get('list', []))
                elif isinstance(response, list):
                    fills = response
                
                if not fills:
                    logger.info(f"페이지 {page + 1}: 더 이상 데이터가 없습니다")
                    break
                
                # 중복 제거 및 추가
                new_fills_count = 0
                last_fill_in_page = None
                
                for fill in fills:
                    # ID 찾기
                    fill_id = None
                    for field in ['fillId', 'id', 'orderId', 'tradeId']:
                        if field in fill and fill[field]:
                            fill_id = str(fill[field])
                            break
                    
                    # 중복 체크
                    if fill_id and fill_id not in seen_ids:
                        seen_ids.add(fill_id)
                        all_fills.append(fill)
                        new_fills_count += 1
                        last_fill_in_page = fill
                
                logger.info(f"페이지 {page + 1}: {len(fills)}건 조회, {new_fills_count}건 추가 (누적 {len(all_fills)}건)")
                
                # 새로 추가된 거래가 없으면 종료
                if new_fills_count == 0:
                    logger.info("중복된 데이터만 있어 조회 종료")
                    break
                
                # 500건 미만이면 마지막 페이지
                if len(fills) < 500:
                    logger.info("마지막 페이지 도달")
                    break
                
                # 다음 페이지를 위한 lastId 찾기
                if last_fill_in_page:
                    new_last_id = None
                    for field in ['fillId', 'id', 'orderId', 'tradeId']:
                        if field in last_fill_in_page and last_fill_in_page[field]:
                            new_last_id = str(last_fill_in_page[field])
                            logger.debug(f"다음 페이지 ID 필드: {field} = {new_last_id}")
                            break
                    
                    if not new_last_id or new_last_id == last_id:
                        logger.warning("다음 페이지 ID를 찾을 수 없음")
                        break
                    
                    last_id = new_last_id
                else:
                    logger.warning("마지막 거래를 찾을 수 없음")
                    break
                
                page += 1
                
                # API 요청 간격
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"페이지 {page + 1} 조회 오류: {e}")
                break
        
        logger.info(f"기간별 조회 완료: 총 {len(all_fills)}건")
        
        # 날짜별로 거래 수 확인 (디버깅용)
        date_counts = {}
        for fill in all_fills:
            trade_time = None
            for time_field in ['cTime', 'createdTime', 'createTime', 'time']:
                if time_field in fill:
                    trade_time = int(fill[time_field])
                    break
            
            if trade_time:
                trade_date = datetime.fromtimestamp(trade_time / 1000, tz=kst).strftime('%Y-%m-%d')
                date_counts[trade_date] = date_counts.get(trade_date, 0) + 1
        
        logger.info("날짜별 거래 수:")
        for date, count in sorted(date_counts.items()):
            logger.info(f"  {date}: {count}건")
        
        return all_fills
    
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
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
