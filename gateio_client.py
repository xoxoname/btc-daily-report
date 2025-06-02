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

class GateClient:
    def __init__(self, config):
        self.config = config
        self.api_key = config.GATE_API_KEY
        self.api_secret = config.GATE_API_SECRET
        self.base_url = "https://api.gateio.ws"
        self.session = None
        self._initialize_session()
        
        # Gate.io 거래 시작일 설정 (2025년 5월 29일)
        self.GATE_START_DATE = datetime(2025, 5, 29, 0, 0, 0, tzinfo=pytz.timezone('Asia/Seoul'))
        
    def _initialize_session(self):
        """세션 초기화"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            logger.info("Gate.io 클라이언트 세션 초기화 완료")
    
    async def initialize(self):
        """클라이언트 초기화"""
        self._initialize_session()
        logger.info("Gate.io 클라이언트 초기화 완료")
    
    def _generate_signature(self, method: str, url: str, query_string: str = "", payload: str = "") -> Dict[str, str]:
        """Gate.io API 서명 생성"""
        timestamp = str(int(time.time()))
        
        # 서명 메시지 생성
        hashed_payload = hashlib.sha512(payload.encode('utf-8')).hexdigest()
        s = f"{method}\n{url}\n{query_string}\n{hashed_payload}\n{timestamp}"
        
        # HMAC-SHA512 서명
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
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """API 요청"""
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
        
        headers = self._generate_signature(method, endpoint, query_string, payload)
        
        try:
            logger.info(f"Gate.io API 요청: {method} {url}")
            if data:
                logger.info(f"요청 데이터: {payload}")
            
            async with self.session.request(method, url, headers=headers, data=payload) as response:
                response_text = await response.text()
                logger.debug(f"Gate.io 응답: {response_text[:500]}")
                
                if response.status != 200:
                    logger.error(f"Gate.io API 오류: {response.status} - {response_text}")
                    raise Exception(f"Gate.io API 오류: {response_text}")
                
                return json.loads(response_text) if response_text else {}
                
        except Exception as e:
            logger.error(f"Gate.io API 요청 중 오류: {e}")
            raise
    
    async def get_account_balance(self) -> Dict:
        """계정 잔고 조회 - 선물 계정"""
        try:
            endpoint = "/api/v4/futures/usdt/accounts"
            response = await self._request('GET', endpoint)
            logger.info(f"Gate.io 계정 잔고 응답: {response}")
            return response
        except Exception as e:
            logger.error(f"계정 잔고 조회 실패: {e}")
            raise
    
    async def get_futures_account(self) -> Dict:
        """선물 계정 정보 조회 (get_account_balance와 동일)"""
        return await self.get_account_balance()
    
    async def get_positions(self, contract: str = "BTC_USDT") -> List[Dict]:
        """포지션 조회"""
        try:
            endpoint = f"/api/v4/futures/usdt/positions/{contract}"
            response = await self._request('GET', endpoint)
            
            # 단일 포지션이면 리스트로 변환
            if isinstance(response, dict):
                return [response] if response.get('size', 0) != 0 else []
            return response
            
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []
    
    async def place_order(self, contract: str, size: int, price: Optional[float] = None, 
                         reduce_only: bool = False, tif: str = "gtc", iceberg: int = 0) -> Dict:
        """선물 주문 생성 - Gate.io API 규격에 맞춰 수정
        
        Args:
            contract: 계약명 (예: BTC_USDT)
            size: 주문 수량 (양수=롱, 음수=숏)
            price: 지정가 (None이면 시장가)
            reduce_only: 포지션 감소 전용
            tif: Time in Force (gtc, ioc, poc, fok)
            iceberg: 빙산 주문 수량
        """
        try:
            endpoint = "/api/v4/futures/usdt/orders"
            
            # 기본 주문 데이터
            data = {
                "contract": contract,
                "size": size,
                "reduce_only": reduce_only
            }
            
            # 지정가 주문
            if price is not None:
                data["price"] = str(price)
                data["tif"] = tif
            else:
                # 시장가 주문 - tif는 ioc 또는 생략
                data["tif"] = "ioc"
            
            # 빙산 주문
            if iceberg > 0:
                data["iceberg"] = iceberg
            
            # 자동 사이즈 감소 (Gate.io 기본값)
            data["auto_size"] = "close_long" if size < 0 else "close_short" if reduce_only else None
            if data["auto_size"] is None:
                del data["auto_size"]
            
            logger.info(f"Gate.io 주문 생성 요청: {data}")
            response = await self._request('POST', endpoint, data=data)
            logger.info(f"Gate.io 주문 생성 성공: {response}")
            return response
            
        except Exception as e:
            logger.error(f"주문 생성 실패: {e}")
            raise
    
    async def set_leverage(self, contract: str, leverage: int, cross_leverage_limit: int = 0) -> Dict:
        """레버리지 설정"""
        try:
            endpoint = f"/api/v4/futures/usdt/positions/{contract}/leverage"
            
            params = {
                "leverage": str(leverage)
            }
            
            if cross_leverage_limit > 0:
                params["cross_leverage_limit"] = str(cross_leverage_limit)
            
            response = await self._request('POST', endpoint, params=params)
            logger.info(f"레버리지 설정 완료: {contract} - {leverage}x")
            return response
            
        except Exception as e:
            logger.error(f"레버리지 설정 실패: {e}")
            raise
    
    async def set_position_mode(self, contract: str, mode: str = "dual_long") -> Dict:
        """포지션 모드 설정 (dual_long, dual_short, single)"""
        try:
            endpoint = f"/api/v4/futures/usdt/positions/{contract}/margin"
            
            data = {
                "change": "0",  # 마진 변경 없음
                "mode": mode
            }
            
            response = await self._request('POST', endpoint, data=data)
            return response
            
        except Exception as e:
            logger.error(f"포지션 모드 설정 실패: {e}")
            raise
    
    async def create_price_triggered_order(self, trigger_type: str, trigger_price: str, 
                                         order_type: str, contract: str, size: int, 
                                         price: Optional[str] = None) -> Dict:
        """가격 트리거 주문 생성 (TP/SL)
        
        Args:
            trigger_type: 트리거 타입 (ge=이상, le=이하)
            trigger_price: 트리거 가격
            order_type: 주문 타입 (limit, market)
            contract: 계약명
            size: 수량
            price: 지정가 (시장가면 None)
        """
        try:
            endpoint = "/api/v4/futures/usdt/price_orders"
            
            initial_data = {
                "type": order_type,
                "side": "long" if size > 0 else "short",
                "size": str(abs(size))
            }
            
            if order_type == "limit" and price:
                initial_data["price"] = str(price)
            
            data = {
                "initial": initial_data,
                "trigger": {
                    "strategy_type": "0",  # 가격 트리거
                    "price_type": "0",     # 최종가격
                    "price": trigger_price,
                    "rule": trigger_type   # ge(>=) 또는 le(<=)
                },
                "contract": contract
            }
            
            logger.info(f"Gate.io 가격 트리거 주문: {data}")
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
            return response
            
        except Exception as e:
            logger.error(f"가격 트리거 주문 취소 실패: {e}")
            raise
    
    async def get_contract_info(self, contract: str = "BTC_USDT") -> Dict:
        """계약 정보 조회"""
        try:
            endpoint = f"/api/v4/futures/usdt/contracts/{contract}"
            response = await self._request('GET', endpoint)
            return response
            
        except Exception as e:
            logger.error(f"계약 정보 조회 실패: {e}")
            raise
    
    async def close_position(self, contract: str, size: Optional[int] = None) -> Dict:
        """포지션 종료
        
        Args:
            contract: 계약명
            size: 종료할 수량 (None이면 전체 종료)
        """
        try:
            # 현재 포지션 조회
            positions = await self.get_positions(contract)
            
            if not positions or positions[0].get('size', 0) == 0:
                logger.warning(f"종료할 포지션이 없습니다: {contract}")
                return {"status": "no_position"}
            
            position = positions[0]
            position_size = int(position['size'])
            
            # 종료할 수량 계산
            if size is None:
                close_size = -position_size  # 전체 종료
            else:
                # 부분 종료
                if position_size > 0:  # 롱 포지션
                    close_size = -min(abs(size), position_size)
                else:  # 숏 포지션
                    close_size = min(abs(size), abs(position_size))
            
            # 시장가로 포지션 종료
            return await self.place_order(
                contract=contract,
                size=close_size,
                reduce_only=True,
                tif="ioc"  # 즉시 체결
            )
            
        except Exception as e:
            logger.error(f"포지션 종료 실패: {e}")
            raise
    
    async def get_order_history(self, contract: str = "BTC_USDT", status: str = "finished", 
                              start_time: Optional[int] = None, end_time: Optional[int] = None,
                              limit: int = 100) -> List[Dict]:
        """주문 내역 조회"""
        try:
            endpoint = "/api/v4/futures/usdt/orders"
            params = {
                "contract": contract,
                "status": status,
                "limit": str(limit)
            }
            
            if start_time:
                params["from"] = str(start_time)
            if end_time:
                params["to"] = str(end_time)
            
            response = await self._request('GET', endpoint, params=params)
            return response if isinstance(response, list) else []
            
        except Exception as e:
            logger.error(f"주문 내역 조회 실패: {e}")
            return []
    
    async def get_position_history(self, contract: str = "BTC_USDT", 
                                 start_time: Optional[int] = None, end_time: Optional[int] = None,
                                 limit: int = 100) -> List[Dict]:
        """포지션 히스토리 조회"""
        try:
            endpoint = "/api/v4/futures/usdt/position_close"
            params = {
                "contract": contract,
                "limit": str(limit)
            }
            
            if start_time:
                params["from"] = str(start_time)
            if end_time:
                params["to"] = str(end_time)
            
            response = await self._request('GET', endpoint, params=params)
            return response if isinstance(response, list) else []
            
        except Exception as e:
            logger.error(f"포지션 히스토리 조회 실패: {e}")
            return []
    
    async def get_account_book(self, type: Optional[str] = None, 
                             start_time: Optional[int] = None, end_time: Optional[int] = None,
                             limit: int = 100) -> List[Dict]:
        """계정 장부 조회 (손익 내역)"""
        try:
            endpoint = "/api/v4/futures/usdt/account_book"
            params = {
                "limit": str(limit)
            }
            
            if type:
                params["type"] = type  # pnl, fee, refr, fund, point_fee, point_refr, point_dnw
            if start_time:
                params["from"] = str(start_time)
            if end_time:
                params["to"] = str(end_time)
            
            response = await self._request('GET', endpoint, params=params)
            return response if isinstance(response, list) else []
            
        except Exception as e:
            logger.error(f"계정 장부 조회 실패: {e}")
            return []
    
    async def get_profit_history_since_may(self) -> Dict:
        """2025년 5월 29일부터의 손익 계산"""
        try:
            import pytz
            from datetime import datetime
            
            kst = pytz.timezone('Asia/Seoul')
            
            # 현재 시간
            now = datetime.now(kst)
            
            # 오늘 0시 (KST)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_timestamp = int(today_start.timestamp())
            
            # 7일 전 0시 (KST)
            seven_days_ago = today_start - timedelta(days=6)
            seven_days_timestamp = int(seven_days_ago.timestamp())
            
            # 2025년 5월 29일 0시 (KST) - 실제 거래 시작일
            start_timestamp = int(self.GATE_START_DATE.timestamp())
            
            # 계정 정보
            account = await self.get_account_balance()
            current_balance = float(account.get('total', 0))
            
            # 초기 자본 설정
            initial_capital = 700.0  # 기본값
            
            # 5월 29일부터 현재까지의 손익 계산
            total_pnl = 0.0
            total_fee = 0.0
            total_fund = 0.0
            
            # PnL 조회 (5월 29일부터)
            try:
                pnl_records = await self.get_account_book(
                    type="pnl",
                    start_time=start_timestamp,
                    limit=1000
                )
                
                for record in pnl_records:
                    change = float(record.get('change', 0))
                    total_pnl += change
                    
                logger.info(f"Gate.io 5월 29일부터 PnL: ${total_pnl:.2f}")
            except Exception as e:
                logger.error(f"PnL 조회 실패: {e}")
            
            # 수수료 조회 (5월 29일부터)
            try:
                fee_records = await self.get_account_book(
                    type="fee",
                    start_time=start_timestamp,
                    limit=1000
                )
                
                for record in fee_records:
                    total_fee += abs(float(record.get('change', 0)))
                    
                logger.info(f"Gate.io 5월 29일부터 수수료: ${total_fee:.2f}")
            except Exception as e:
                logger.error(f"수수료 조회 실패: {e}")
            
            # 펀딩비 조회 (5월 29일부터)
            try:
                fund_records = await self.get_account_book(
                    type="fund",
                    start_time=start_timestamp,
                    limit=1000
                )
                
                for record in fund_records:
                    total_fund += float(record.get('change', 0))
                    
                logger.info(f"Gate.io 5월 29일부터 펀딩비: ${total_fund:.2f}")
            except Exception as e:
                logger.error(f"펀딩비 조회 실패: {e}")
            
            # 5월 29일부터의 순수익 = 실현손익 - 수수료 + 펀딩비
            cumulative_net_profit = total_pnl - total_fee + total_fund
            
            # 7일간 손익 계산
            weekly_pnl = 0.0
            today_pnl = 0.0
            weekly_fee = 0.0
            
            # 현재가 거래 시작일로부터 7일이 안 되었을 경우
            actual_start_timestamp = max(seven_days_timestamp, start_timestamp)
            
            # PnL 조회 (최근 7일 또는 거래 시작일부터)
            pnl_records = await self.get_account_book(
                type="pnl",
                start_time=actual_start_timestamp,
                limit=1000
            )
            
            for record in pnl_records:
                change = float(record.get('change', 0))
                record_time = int(record.get('time', 0))
                
                weekly_pnl += change
                
                # 오늘 손익
                if record_time >= today_timestamp:
                    today_pnl += change
            
            # 수수료 조회 (최근 7일 또는 거래 시작일부터)
            fee_records = await self.get_account_book(
                type="fee",
                start_time=actual_start_timestamp,
                limit=1000
            )
            
            for record in fee_records:
                weekly_fee += abs(float(record.get('change', 0)))
            
            # 7일 순수익
            weekly_net = weekly_pnl - weekly_fee
            
            # 실제 거래 일수 계산
            days_traded = min(7, (now - self.GATE_START_DATE).days + 1)
            
            logger.info(f"Gate.io 거래 일수: {days_traded}일")
            logger.info(f"Gate.io 7일 손익 - PnL: ${weekly_pnl:.2f}, Fee: ${weekly_fee:.2f}, Net: ${weekly_net:.2f}")
            logger.info(f"Gate.io 오늘 실현 손익: ${today_pnl:.2f}")
            
            # 실제 수익 = 현재 잔고 - 초기 자본
            actual_profit = current_balance - initial_capital
            
            return {
                'total': cumulative_net_profit,  # 5월 29일부터의 순수익
                'weekly': {
                    'total': weekly_net,
                    'average': weekly_net / days_traded if days_traded > 0 else 0
                },
                'today_realized': today_pnl,
                'current_balance': current_balance,
                'initial_capital': initial_capital,
                'actual_profit': actual_profit,  # 실제 수익 (현재잔고 - 초기자본)
                'days_traded': days_traded  # 실제 거래 일수
            }
            
        except Exception as e:
            logger.error(f"Gate 손익 내역 조회 실패: {e}")
            # 폴백: 현재 잔고 기반 계산
            try:
                account = await self.get_account_balance()
                total_equity = float(account.get('total', 0))
                # 초기 자본 700 달러 기준
                total_pnl = total_equity - 700
                
                return {
                    'total': total_pnl,
                    'weekly': {
                        'total': 0,  # 알 수 없음
                        'average': 0
                    },
                    'today_realized': 0.0,
                    'current_balance': total_equity,
                    'initial_capital': 700,
                    'actual_profit': total_pnl
                }
            except:
                return {
                    'total': 0,
                    'weekly': {'total': 0, 'average': 0},
                    'today_realized': 0,
                    'current_balance': 0,
                    'initial_capital': 700,
                    'actual_profit': 0
                }
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Gate.io 클라이언트 세션 종료")
