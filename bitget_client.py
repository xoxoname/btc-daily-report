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
    
    async def get_all_trade_fills(self, symbol: str = None, start_time: int = None, end_time: int = None) -> List[Dict]:
        """모든 거래 내역 조회 - 페이징 처리"""
        symbol = symbol or self.config.symbol
        all_fills = []
        
        endpoints = [
            ("/api/v2/mix/order/fill-history", ["fillList", "fills", "list"]),
            ("/api/v2/mix/order/history", ["orderList", "list", "data"]),
            ("/api/v2/mix/order/fills", ["fills", "list", "data"])
        ]
        
        for endpoint, possible_keys in endpoints:
            last_id = None
            page = 0
            consecutive_empty = 0
            
            while page < 50:
                params = {
                    'symbol': symbol,
                    'productType': 'USDT-FUTURES',
                    'limit': '100'
                }
                
                if start_time:
                    params['startTime'] = str(start_time)
                if end_time:
                    params['endTime'] = str(end_time)
                if last_id:
                    params['lastEndId'] = str(last_id)
                
                try:
                    logger.info(f"{endpoint} 페이지 {page + 1} 조회 중...")
                    response = await self._request('GET', endpoint, params=params)
                    
                    fills = []
                    if isinstance(response, dict):
                        for key in possible_keys:
                            if key in response and isinstance(response[key], list):
                                fills = response[key]
                                break
                    elif isinstance(response, list):
                        fills = response
                    
                    if not fills:
                        consecutive_empty += 1
                        if consecutive_empty >= 2:
                            break
                        page += 1
                        await asyncio.sleep(0.1)
                        continue
                    
                    consecutive_empty = 0
                    all_fills.extend(fills)
                    logger.info(f"{endpoint} 페이지 {page + 1}: {len(fills)}건 (누적 {len(all_fills)}건)")
                    
                    if len(fills) < 100:
                        logger.info(f"{endpoint} 마지막 페이지 도달")
                        break
                    
                    last_fill = fills[-1]
                    new_last_id = None
                    
                    id_fields = ['fillId', 'orderId', 'id', 'tradeId', 'billId']
                    for field in id_fields:
                        if field in last_fill and last_fill[field]:
                            new_last_id = str(last_fill[field])
                            break
                    
                    if not new_last_id or new_last_id == last_id:
                        logger.warning(f"다음 페이지 ID를 찾을 수 없음")
                        break
                    
                    last_id = new_last_id
                    page += 1
                    
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"{endpoint} 페이지 {page + 1} 오류: {e}")
                    break
            
            if all_fills:
                logger.info(f"{endpoint} 총 {len(all_fills)}건 조회 완료")
                return all_fills
        
        logger.warning(f"모든 엔드포인트에서 거래 내역을 찾을 수 없음")
        return all_fills
    
    async def get_profit_loss_history(self, symbol: str = None, days: int = 7) -> Dict:
        """손익 내역 조회 - 페이징 처리 추가"""
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
            
            # UTC로 변환하여 타임스탬프 생성
            start_time_utc = period_start.astimezone(pytz.UTC)
            end_time_utc = period_end.astimezone(pytz.UTC)
            
            start_time = int(start_time_utc.timestamp() * 1000)
            end_time = int(end_time_utc.timestamp() * 1000)
            
            logger.info(f"=== {days}일 손익 조회 ===")
            logger.info(f"기간: {period_start.strftime('%Y-%m-%d %H:%M')} ~ {period_end.strftime('%Y-%m-%d %H:%M')} (KST)")
            logger.info(f"타임스탬프: {start_time} ~ {end_time}")
            
            # 디버깅용: 실제 날짜 범위 확인
            actual_days = (period_end - period_start).days + 1
            logger.info(f"실제 조회 일수: {actual_days}일")
            
            # 예상 날짜 목록 출력
            logger.info("예상 거래일 목록:")
            for i in range(days):
                date = period_start + timedelta(days=i)
                logger.info(f"  - {date.strftime('%Y-%m-%d')}")
            
            total_pnl = 0.0
            daily_pnl = {}
            total_fees = 0.0
            trade_count = 0
            
            # 모든 거래 내역 조회 (페이징 처리)
            all_fills = []
            
            # days가 7일을 초과하는 경우 7일씩 나눠서 조회
            if days > 7:
                current_start = start_time
                
                while current_start < end_time:
                    current_end = min(current_start + (7 * 24 * 60 * 60 * 1000), end_time)
                    
                    # KST로 변환하여 로깅
                    start_kst = datetime.fromtimestamp(current_start/1000, tz=kst)
                    end_kst = datetime.fromtimestamp(current_end/1000, tz=kst)
                    logger.info(f"부분 조회: {start_kst.strftime('%Y-%m-%d')} ~ {end_kst.strftime('%Y-%m-%d')}")
                    
                    # 해당 기간의 모든 거래 조회 (페이징 처리)
                    period_fills = await self._get_all_fills_for_period(symbol, current_start, current_end)
                    all_fills.extend(period_fills)
                    
                    current_start = current_end
                    await asyncio.sleep(0.2)  # API 요청 간격
            else:
                # 7일 이하는 페이징 처리로 모든 거래 조회
                logger.info(f"페이징 처리로 {days}일 거래 내역 조회 시작")
                all_fills = await self._get_all_fills_for_period(symbol, start_time, end_time)
            
            logger.info(f"총 조회된 거래 수: {len(all_fills)}건")
            
            # 거래 처리
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
                    
                    # 조회 기간 내의 거래만 처리
                    if trade_date_kst < period_start or trade_date_kst > period_end:
                        logger.debug(f"기간 외 거래 제외: {trade_date_str}")
                        continue
                    
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
                        
                        logger.debug(f"거래: {trade_date_str} profit={profit:.2f}, fee={fee:.2f}, pnl={realized_pnl:.2f}")
                    
                except Exception as e:
                    logger.warning(f"거래 파싱 오류: {e}")
                    continue
            
            # 결과 로그
            if daily_pnl:
                logger.info("=== 일별 손익 내역 ===")
                for date, pnl in sorted(daily_pnl.items()):
                    logger.info(f"  {date}: ${pnl:,.2f}")
            else:
                logger.warning("조회된 손익 내역이 없습니다")
            
            # 누락된 날짜 확인
            logger.info("누락된 거래일 확인:")
            for i in range(days):
                date = (period_start + timedelta(days=i)).strftime('%Y-%m-%d')
                if date not in daily_pnl:
                    logger.warning(f"  - {date}: 거래 없음")
            
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
                
                # 중복 제거를 위해 ID 기록
                new_fills_count = 0
                for fill in fills:
                    fill_id = None
                    for field in ['fillId', 'id', 'orderId', 'tradeId']:
                        if field in fill and fill[field]:
                            fill_id = str(fill[field])
                            break
                    
                    # 중복 체크
                    is_duplicate = False
                    if fill_id:
                        for existing_fill in all_fills:
                            existing_id = None
                            for field in ['fillId', 'id', 'orderId', 'tradeId']:
                                if field in existing_fill and existing_fill[field]:
                                    existing_id = str(existing_fill[field])
                                    break
                            if existing_id == fill_id:
                                is_duplicate = True
                                break
                    
                    if not is_duplicate:
                        all_fills.append(fill)
                        new_fills_count += 1
                
                logger.info(f"페이지 {page + 1}: {len(fills)}건 조회, {new_fills_count}건 추가 (누적 {len(all_fills)}건)")
                
                # 500건 미만이면 마지막 페이지
                if len(fills) < 500:
                    logger.info("마지막 페이지 도달")
                    break
                
                # 다음 페이지를 위한 lastId 찾기
                last_fill = fills[-1]
                new_last_id = None
                
                for field in ['fillId', 'id', 'orderId', 'tradeId']:
                    if field in last_fill and last_fill[field]:
                        new_last_id = str(last_fill[field])
                        logger.debug(f"다음 페이지 ID 필드: {field} = {new_last_id}")
                        break
                
                if not new_last_id or new_last_id == last_id:
                    logger.warning("다음 페이지 ID를 찾을 수 없음")
                    break
                
                last_id = new_last_id
                page += 1
                
                # API 요청 간격
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"페이지 {page + 1} 조회 오류: {e}")
                break
        
        logger.info(f"기간별 조회 완료: 총 {len(all_fills)}건")
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
