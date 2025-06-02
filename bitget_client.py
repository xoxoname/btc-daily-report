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
    
    async def get_plan_orders(self, symbol: str = None, plan_type: str = 'normal') -> List[Dict]:
        """플랜 주문(예약 주문) 조회 (V2 API) - planType 파라미터 추가"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/order/orders-plan-pending"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES',
            'planType': plan_type  # normal, profit_loss
        }
        
        try:
            response = await self._request('GET', endpoint, params=params)
            logger.debug(f"플랜 주문 조회 응답: {response}")
            
            orders = response if isinstance(response, list) else []
            
            # 상세 정보 로깅
            for order in orders:
                logger.info(f"예약 주문: {order.get('planOrderId')} - {order.get('side')} {order.get('size')} @ trigger: {order.get('triggerPrice')}")
            
            return orders
            
        except Exception as e:
            logger.error(f"플랜 주문 조회 실패: {e}")
            return []
    
    async def get_plan_order_history(self, symbol: str = None, start_time: int = None, end_time: int = None, limit: int = 100) -> List[Dict]:
        """플랜 주문 히스토리 조회 (V2 API)"""
        symbol = symbol or self.config.symbol
        endpoint = "/api/v2/mix/order/orders-plan-history"
        params = {
            'symbol': symbol,
            'productType': 'USDT-FUTURES',
            'pageSize': str(limit)
        }
        
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
            logger.error(f"플랜 주문 히스토리 조회 실패: {e}")
            return []
    
    async def get_all_plan_orders_with_tp_sl(self, symbol: str = None) -> Dict:
        """모든 플랜 주문과 TP/SL 조회 (통합)"""
        try:
            symbol = symbol or self.config.symbol
            
            # 1. 일반 플랜 주문 조회 (planType=normal)
            plan_orders = await self.get_plan_orders(symbol, plan_type='normal')
            
            # 2. TP/SL 주문 조회 (profit-loss 타입)
            tp_sl_orders = await self.get_plan_orders(symbol, plan_type='profit_loss')
            
            # 3. 통합 결과
            result = {
                'plan_orders': plan_orders,
                'tp_sl_orders': tp_sl_orders,
                'total_count': len(plan_orders) + len(tp_sl_orders)
            }
            
            logger.info(f"전체 예약 주문: 일반 {len(plan_orders)}건 + TP/SL {len(tp_sl_orders)}건 = 총 {result['total_count']}건")
            
            return result
            
        except Exception as e:
            logger.error(f"전체 플랜 주문 조회 실패: {e}")
            return {
                'plan_orders': [],
                'tp_sl_orders': [],
                'total_count': 0,
                'error': str(e)
            }
    
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
    
    async def get_account_bills(self, start_time: int = None, end_time: int = None, 
                               business_type: str = None, limit: int = 100,
                               next_id: str = None) -> List[Dict]:
        """계정 거래 내역 조회 (Account Bills)"""
        endpoint = "/api/v2/mix/account/bills"
        params = {
            'productType': 'USDT-FUTURES',
            'marginCoin': 'USDT'
        }
        
        if start_time:
            params['startTime'] = str(start_time)
        if end_time:
            params['endTime'] = str(end_time)
        if business_type:
            params['businessType'] = business_type  # 'contract_settle' for realized PnL
        if limit:
            params['limit'] = str(min(limit, 100))
        if next_id:
            params['startId'] = str(next_id)
        
        try:
            response = await self._request('GET', endpoint, params=params)
            
            if isinstance(response, list):
                return response
            elif isinstance(response, dict):
                # 페이징 정보가 있는 경우
                return response.get('billsList', response.get('bills', []))
            return []
            
        except Exception as e:
            logger.error(f"계정 내역 조회 실패: {e}")
            return []
    
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
        """손익 내역 조회 - 우선 Account Bills 시도, 실패시 기존 방식"""
        try:
            # 먼저 Account Bills 방식 시도
            result = await self.get_profit_loss_history_v2(symbol, days)
            
            # 결과가 있으면 반환
            if result.get('total_pnl', 0) != 0 or result.get('trade_count', 0) > 0:
                return result
            
            # Account Bills에서 데이터가 없으면 기존 방식으로 폴백
            logger.info("Account Bills에 데이터가 없어 기존 방식으로 전환")
            return await self._get_profit_loss_history_original(symbol, days)
            
        except Exception as e:
            logger.error(f"Account Bills 조회 실패, 기존 방식으로 전환: {e}")
            return await self._get_profit_loss_history_original(symbol, days)
    
    async def _get_profit_loss_history_original(self, symbol: str = None, days: int = 7) -> Dict:
        """손익 내역 조회 - 기존 방식 (30일 조회 후 필터링)"""
        try:
            symbol = symbol or self.config.symbol
            
            # KST 기준 현재 시간
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 실제 필요한 기간
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_start = today_start - timedelta(days=days-1)
            period_end = now
            
            logger.info(f"=== {days}일 손익 조회 (기존 방식) ===")
            logger.info(f"실제 필요 기간: {period_start.strftime('%Y-%m-%d %H:%M')} ~ {period_end.strftime('%Y-%m-%d %H:%M')} (KST)")
            
            # 30일 데이터 조회 (안정적인 데이터 확보를 위해)
            base_days = 30
            extended_start = today_start - timedelta(days=base_days-1)
            
            # UTC로 변환
            start_time_utc = extended_start.astimezone(pytz.UTC)
            end_time_utc = now.astimezone(pytz.UTC)
            
            start_time = int(start_time_utc.timestamp() * 1000)
            end_time = int(end_time_utc.timestamp() * 1000)
            
            logger.info(f"30일 전체 조회: {extended_start.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}")
            
            # 모든 거래 내역 조회
            all_fills = await self._get_all_fills_comprehensive(symbol, start_time, end_time)
            
            logger.info(f"30일 동안 조회된 총 거래 수: {len(all_fills)}건")
            
            # 날짜별로 거래 분류
            trades_by_date = {}
            total_pnl = 0.0
            daily_pnl = {}
            total_fees = 0.0
            trade_count = 0
            
            # 모든 거래 처리
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
                    
                    # 거래 정보 저장
                    if trade_date_str not in trades_by_date:
                        trades_by_date[trade_date_str] = []
                    
                    trades_by_date[trade_date_str].append({
                        'time': trade_time,
                        'profit': profit,
                        'fee': fee,
                        'pnl': profit - fee
                    })
                    
                except Exception as e:
                    logger.warning(f"거래 파싱 오류: {e}")
                    continue
            
            # 필요한 기간의 데이터만 추출
            logger.info(f"\n=== {days}일 손익 계산 ===")
            for i in range(days):
                date = period_start + timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                
                if date_str in trades_by_date:
                    day_trades = trades_by_date[date_str]
                    day_pnl = sum(t['pnl'] for t in day_trades)
                    day_fees = sum(t['fee'] for t in day_trades)
                    
                    daily_pnl[date_str] = day_pnl
                    total_pnl += day_pnl
                    total_fees += day_fees
                    trade_count += len(day_trades)
                    
                    logger.info(f"{date_str}: ${day_pnl:,.2f} ({len(day_trades)}건, 수수료 ${day_fees:.2f})")
                else:
                    logger.info(f"{date_str}: 거래 없음")
            
            logger.info(f"\n=== {days}일 총 손익: ${total_pnl:,.2f} (거래 {trade_count}건, 수수료 ${total_fees:.2f}) ===")
            
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
    
    async def _get_all_fills_comprehensive(self, symbol: str, start_time: int, end_time: int) -> List[Dict]:
        """포괄적인 거래 내역 조회 - 7일씩 나눠서 조회"""
        all_fills = []
        seen_ids = set()
        
        # 7일씩 나눠서 조회
        current_start = start_time
        
        while current_start < end_time:
            current_end = min(current_start + (7 * 24 * 60 * 60 * 1000), end_time)
            
            # KST로 변환하여 로깅
            kst = pytz.timezone('Asia/Seoul')
            start_kst = datetime.fromtimestamp(current_start/1000, tz=kst)
            end_kst = datetime.fromtimestamp(current_end/1000, tz=kst)
            logger.info(f"\n부분 조회: {start_kst.strftime('%Y-%m-%d')} ~ {end_kst.strftime('%Y-%m-%d')}")
            
            # 해당 기간 조회
            period_fills = await self._get_period_fills_with_paging(symbol, current_start, current_end)
            
            # 중복 제거하며 추가
            new_count = 0
            for fill in period_fills:
                fill_id = self._get_fill_id(fill)
                if fill_id and fill_id not in seen_ids:
                    seen_ids.add(fill_id)
                    all_fills.append(fill)
                    new_count += 1
            
            logger.info(f"조회 결과: {len(period_fills)}건 중 {new_count}건 추가")
            
            current_start = current_end
            await asyncio.sleep(0.2)
        
        return all_fills
    
    async def _get_period_fills_with_paging(self, symbol: str, start_time: int, end_time: int) -> List[Dict]:
        """특정 기간의 모든 거래 조회 (페이징)"""
        all_fills = []
        last_id = None
        page = 0
        endpoint = "/api/v2/mix/order/fill-history"
        
        while page < 20:  # 최대 20페이지
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES',
                'startTime': str(start_time),
                'endTime': str(end_time),
                'limit': '500'
            }
            
            if last_id:
                params['lastEndId'] = str(last_id)
            
            try:
                response = await self._request('GET', endpoint, params=params)
                
                fills = []
                if isinstance(response, dict):
                    fills = response.get('fillList', response.get('list', []))
                elif isinstance(response, list):
                    fills = response
                
                if not fills:
                    break
                
                all_fills.extend(fills)
                logger.info(f"페이지 {page + 1}: {len(fills)}건 조회 (누적 {len(all_fills)}건)")
                
                if len(fills) < 500:
                    break
                
                # 다음 페이지 ID
                last_fill = fills[-1]
                new_last_id = self._get_fill_id(last_fill)
                
                if not new_last_id or new_last_id == last_id:
                    break
                
                last_id = new_last_id
                page += 1
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"페이지 {page + 1} 조회 오류: {e}")
                break
        
        return all_fills
    
    def _get_fill_id(self, fill: Dict) -> Optional[str]:
        """거래 ID 추출"""
        for field in ['fillId', 'id', 'orderId', 'tradeId']:
            if field in fill and fill[field]:
                return str(fill[field])
        return None
    
    async def get_simple_weekly_profit(self, days: int = 7) -> Dict:
        """간단한 주간 손익 계산 - achievedProfits vs 실제 거래내역 비교"""
        try:
            logger.info(f"=== {days}일 손익 계산 시작 ===")
            
            # 현재 계정 정보
            account = await self.get_account_info()
            current_equity = float(account.get('accountEquity', 0))
            
            # 현재 포지션 정보
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
            
            # 실제 거래 내역 기반 계산
            actual_profit = await self.get_profit_loss_history(days=days)
            actual_pnl = actual_profit.get('total_pnl', 0)
            
            logger.info(f"achievedProfits: ${achieved_profits:.2f}")
            logger.info(f"실제 {days}일 거래내역: ${actual_pnl:.2f}")
            
            # 두 값 중 더 정확한 값 선택
            if achieved_profits > 0 and actual_pnl > 0:
                # 둘 다 있는 경우
                if position_open_time:
                    kst = pytz.timezone('Asia/Seoul')
                    now = datetime.now(kst)
                    position_days = (now - position_open_time).days + 1
                    
                    # 포지션이 정확히 7일 이내에 열렸고, achievedProfits가 합리적인 범위이면 사용
                    if position_days <= days and abs(achieved_profits - actual_pnl) / max(abs(actual_pnl), 1) < 0.5:
                        logger.info(f"achievedProfits 사용 (포지션 기간: {position_days}일)")
                        return {
                            'total_pnl': achieved_profits,
                            'days': days,
                            'average_daily': achieved_profits / days,
                            'source': 'achievedProfits',
                            'position_days': position_days,
                            'daily_pnl': {}
                        }
                    else:
                        logger.info(f"실제 거래내역 사용 (포지션 너무 오래됨 또는 차이 큼: {position_days}일)")
                        return actual_profit
                else:
                    # 포지션 시간 모르면 실제 거래내역 사용
                    logger.info("실제 거래내역 사용 (포지션 시간 불명)")
                    return actual_profit
            elif achieved_profits > 0 and actual_pnl == 0:
                # achievedProfits만 있는 경우
                logger.info("achievedProfits만 사용 (거래내역 없음)")
                return {
                    'total_pnl': achieved_profits,
                    'days': days,
                    'average_daily': achieved_profits / days,
                    'source': 'achievedProfits_only',
                    'daily_pnl': {}
                }
            else:
                # 실제 거래내역 사용
                logger.info("실제 거래내역 사용 (기본)")
                return actual_profit
            
        except Exception as e:
            logger.error(f"주간 손익 계산 실패: {e}")
            return {
                'total_pnl': 0,
                'days': days,
                'average_daily': 0,
                'error': str(e)
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
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")
