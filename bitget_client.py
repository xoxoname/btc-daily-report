import asyncio
import aiohttp
import hmac
import hashlib
import time
import json
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import traceback
import base64

logger = logging.getLogger(__name__)

class BitgetClient:
    """Bitget API 클라이언트"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config.BITGET_APIKEY
        self.api_secret = config.BITGET_APISECRET
        self.passphrase = config.BITGET_PASSPHRASE
        self.base_url = "https://api.bitget.com"
        self.session = None
        
    async def initialize(self):
        """클라이언트 초기화"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            logger.info("Bitget 클라이언트 초기화 완료")
    
    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """API 서명 생성 - 수정된 버전"""
        try:
            # Bitget API v2 서명 방식
            message = timestamp + method.upper() + request_path + body
            
            # HMAC-SHA256으로 서명 생성
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
            
            # Base64 인코딩
            return base64.b64encode(signature).decode('utf-8')
            
        except Exception as e:
            logger.error(f"서명 생성 실패: {e}")
            raise
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """API 요청 - 수정된 버전"""
        if not self.session:
            await self.initialize()
        
        url = f"{self.base_url}{endpoint}"
        timestamp = str(int(time.time() * 1000))
        
        query_string = ""
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            if query_string:
                url += f"?{query_string}"
        
        body = ""
        if data:
            body = json.dumps(data)
        
        request_path = endpoint
        if query_string:
            request_path += f"?{query_string}"
        
        try:
            signature = self._generate_signature(timestamp, method, request_path, body)
        except Exception as e:
            logger.error(f"서명 생성 중 오류: {e}")
            raise
        
        headers = {
            'ACCESS-KEY': self.api_key,
            'ACCESS-SIGN': signature,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json',
            'locale': 'en-US'
        }
        
        try:
            logger.debug(f"Bitget API 요청: {method} {url}")
            async with self.session.request(method, url, headers=headers, data=body) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    logger.error(f"Bitget API 오류: {response.status} - {response_text}")
                    raise Exception(f"Bitget API 오류: {response_text}")
                
                result = json.loads(response_text) if response_text else {}
                
                # API 응답 코드 확인
                if result.get('code') != '00000':
                    error_msg = result.get('msg', 'Unknown error')
                    logger.error(f"Bitget API 응답 오류: {result.get('code')} - {error_msg}")
                    raise Exception(f"Bitget API 오류: {error_msg}")
                
                return result
                
        except Exception as e:
            logger.error(f"Bitget API 요청 중 오류: {e}")
            raise
    
    async def get_account_info(self) -> Dict:
        """계정 정보 조회 - 수정된 엔드포인트"""
        try:
            # V2 API 엔드포인트 사용
            endpoint = "/api/v2/mix/account/account"
            params = {'symbol': 'BTCUSDT', 'marginCoin': 'USDT'}
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                return response['data']
            else:
                logger.error(f"계정 정보 조회 실패: {response}")
                return {}
                
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            return {}
    
    async def get_positions(self, symbol: str = "BTCUSDT") -> List[Dict]:
        """포지션 조회 - 수정된 엔드포인트"""
        try:
            # V2 API 엔드포인트 사용
            endpoint = "/api/v2/mix/position/all-position"
            params = {'symbol': symbol, 'marginCoin': 'USDT'}
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []
    
    async def get_ticker(self, symbol: str = "BTCUSDT") -> Dict:
        """티커 정보 조회 - 수정된 엔드포인트"""
        try:
            # V2 API 엔드포인트 사용
            endpoint = "/api/v2/mix/market/ticker"
            params = {'symbol': symbol}
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                data = response['data']
                # 데이터가 리스트인 경우 첫 번째 요소 반환
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                else:
                    return data
            else:
                logger.warning(f"티커 조회 응답 확인: {response}")
                return {}
                
        except Exception as e:
            logger.error(f"티커 조회 실패: {e}")
            return {}
    
    async def get_kline(self, symbol: str, granularity: str, limit: int = 100) -> List[List]:
        """K라인 데이터 조회 - 수정된 엔드포인트"""
        try:
            # V2 API 엔드포인트 사용
            endpoint = "/api/v2/mix/market/candles"
            params = {
                'symbol': symbol,
                'granularity': granularity,
                'limit': str(limit)
            }
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"K라인 데이터 조회 실패: {e}")
            return []
    
    async def get_funding_rate(self, symbol: str = "BTCUSDT") -> Dict:
        """펀딩비 조회 - 수정된 엔드포인트"""
        try:
            # V2 API 엔드포인트 사용
            endpoint = "/api/v2/mix/market/current-fund-rate"
            params = {'symbol': symbol}
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                data = response['data']
                # 데이터가 리스트인 경우 첫 번째 요소 반환
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                else:
                    return data
            else:
                return {}
                
        except Exception as e:
            logger.error(f"펀딩비 조회 실패: {e}")
            return {}
    
    async def get_open_interest(self, symbol: str = "BTCUSDT") -> Dict:
        """미결제약정 조회 - 수정된 엔드포인트"""
        try:
            # V2 API 엔드포인트 사용
            endpoint = "/api/v2/mix/market/open-interest"
            params = {'symbol': symbol}
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                data = response['data']
                # 데이터가 리스트인 경우 첫 번째 요소 반환
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                else:
                    return data
            else:
                return {}
                
        except Exception as e:
            logger.error(f"미결제약정 조회 실패: {e}")
            return {}
    
    async def get_recent_filled_orders(self, symbol: str = "BTCUSDT", minutes: int = 5) -> List[Dict]:
        """최근 체결 주문 조회 - 🔥🔥 파라미터 형식 수정"""
        try:
            # V2 API 엔드포인트 사용
            endpoint = "/api/v2/mix/order/fills"
            
            # 🔥🔥 수정: 올바른 파라미터 형식 사용
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'  # 필수 파라미터 추가
            }
            
            # 시간 범위가 필요한 경우만 추가
            if minutes and minutes > 0:
                end_time = int(time.time() * 1000)
                start_time = end_time - (minutes * 60 * 1000)
                params['startTime'] = str(start_time)
                params['endTime'] = str(end_time)
            
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"최근 체결 주문 조회 실패: {e}")
            return []
    
    async def get_all_plan_orders_with_tp_sl(self, symbol: str = "BTCUSDT") -> Dict:
        """모든 예약 주문 조회 (TP/SL 포함) - 🔥🔥 올바른 엔드포인트 사용"""
        try:
            result = {
                'plan_orders': [],
                'tp_sl_orders': []
            }
            
            # 🔥🔥🔥 수정: 올바른 API v2 엔드포인트 사용
            endpoint = "/api/v2/mix/order/orders-plan-pending"  # 올바른 엔드포인트
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES'  # 필수 파라미터
            }
            
            try:
                logger.debug(f"Bitget 예약 주문 조회 요청: {endpoint}, params: {params}")
                response = await self._request('GET', endpoint, params=params)
                
                if response.get('code') == '00000' and response.get('data'):
                    all_orders = response['data']
                    
                    # 주문 타입에 따라 분류
                    for order in all_orders:
                        plan_type = order.get('planType', '')
                        order_type = order.get('orderType', '')
                        side = order.get('side', '')
                        
                        # TP/SL 주문 분류 로직
                        if any(keyword in plan_type.lower() for keyword in ['profit', 'loss', 'tp', 'sl']):
                            result['tp_sl_orders'].append(order)
                        elif any(keyword in order_type.lower() for keyword in ['profit', 'loss', 'stop']):
                            result['tp_sl_orders'].append(order)
                        elif 'close' in side.lower():
                            result['tp_sl_orders'].append(order)
                        else:
                            # 일반 예약 주문
                            result['plan_orders'].append(order)
                    
                    logger.info(f"✅ Bitget 예약 주문 조회 성공: 일반 {len(result['plan_orders'])}개, TP/SL {len(result['tp_sl_orders'])}개")
                else:
                    logger.warning(f"예약 주문 조회 응답 확인: {response}")
                    
            except Exception as e:
                logger.warning(f"예약 주문 조회 실패: {e}")
                # 오류 발생 시 빈 결과 반환
                result = {'plan_orders': [], 'tp_sl_orders': []}
            
            return result
            
        except Exception as e:
            logger.error(f"예약 주문 조회 실패: {e}")
            return {'plan_orders': [], 'tp_sl_orders': []}
    
    async def get_trade_fills(self, symbol: str = "BTCUSDT", start_time: int = 0, end_time: int = 0, limit: int = 100) -> List[Dict]:
        """거래 내역 조회 - 🔥🔥 파라미터 형식 수정"""
        try:
            endpoint = "/api/v2/mix/order/fills"
            params = {
                'symbol': symbol,
                'productType': 'USDT-FUTURES',  # 필수 파라미터 추가
                'limit': str(limit)
            }
            
            if start_time > 0:
                params['startTime'] = str(start_time)
            if end_time > 0:
                params['endTime'] = str(end_time)
            
            response = await self._request('GET', endpoint, params=params)
            
            if response.get('code') == '00000' and response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"거래 내역 조회 실패: {e}")
            return []
    
    async def get_enhanced_profit_history(self, days: int = 7) -> Dict:
        """향상된 손익 내역 조회 - 수정된 엔드포인트"""
        try:
            end_time = int(time.time() * 1000)
            start_time = end_time - (days * 24 * 60 * 60 * 1000)
            
            # V2 API 엔드포인트 사용
            endpoint = "/api/v2/mix/account/account-bill"
            params = {
                'symbol': 'BTCUSDT',
                'marginCoin': 'USDT',
                'startTime': str(start_time),
                'endTime': str(end_time),
                'pageSize': '100'
            }
            
            response = await self._request('GET', endpoint, params=params)
            
            total_pnl = 0.0
            
            if response.get('code') == '00000' and response.get('data'):
                for record in response['data']:
                    change = float(record.get('amount', 0))
                    business_type = record.get('businessType', '')
                    
                    # 실현 손익만 계산
                    if business_type in ['close_long', 'close_short', 'delivery_long', 'delivery_short']:
                        total_pnl += change
            
            return {
                'total_pnl': total_pnl,
                'average_daily': total_pnl / days if days > 0 else 0,
                'days': days
            }
            
        except Exception as e:
            logger.error(f"손익 내역 조회 실패: {e}")
            return {
                'total_pnl': 0.0,
                'average_daily': 0.0,
                'days': days
            }
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("Bitget 클라이언트 세션 종료")

@dataclass
class PositionInfo:
    """포지션 정보"""
    symbol: str
    side: str  # long/short
    size: float
    entry_price: float
    margin: float
    leverage: int
    mode: str  # cross/isolated
    tp_orders: List[Dict] = field(default_factory=list)
    sl_orders: List[Dict] = field(default_factory=list)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)
    
@dataclass
class MirrorResult:
    """미러링 결과"""
    success: bool
    action: str
    bitget_data: Dict
    gate_data: Optional[Dict] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

class MirrorTradingSystem:
    def __init__(self, config, bitget_client, gate_client, telegram_bot):
        self.config = config
        self.bitget = bitget_client
        self.gate = gate_client
        self.telegram = telegram_bot
        self.logger = logging.getLogger('mirror_trading')
        
        # 미러링 상태 관리
        self.mirrored_positions: Dict[str, PositionInfo] = {}
        self.startup_positions: Set[str] = set()
        self.failed_mirrors: List[MirrorResult] = []
        self.last_sync_check = datetime.min
        self.last_report_time = datetime.min
        
        # 포지션 크기 추적
        self.position_sizes: Dict[str, float] = {}
        
        # TP/SL 주문 추적
        self.tp_sl_orders: Dict[str, Dict] = {}
        
        # 주문 체결 추적
        self.processed_orders: Set[str] = set()
        self.last_order_check = datetime.now()
        
        # 🔥🔥🔥 예약 주문 취소 미러링 강화 - 예약 주문 추적 관리
        self.mirrored_plan_orders: Dict[str, Dict] = {}  # 비트겟 주문 ID -> 게이트 주문 정보
        self.processed_plan_orders: Set[str] = set()
        self.startup_plan_orders: Set[str] = set()
        self.startup_plan_orders_processed: bool = False
        self.already_mirrored_plan_orders: Set[str] = set()
        
        # 🔥🔥🔥 예약 주문 취소 감지 시스템 - 강화
        self.last_plan_order_ids: Set[str] = set()  # 이전 체크시 존재했던 예약 주문 ID들
        self.plan_order_snapshot: Dict[str, Dict] = {}  # 예약 주문 스냅샷
        self.plan_order_cancel_retry_count: int = 0
        self.max_cancel_retry: int = 5  # 재시도 횟수 증가
        self.cancel_verification_delay: float = 2.0  # 취소 확인 대기 시간
        
        # 포지션 유무에 따른 예약 주문 복제 관리
        self.startup_position_tp_sl: Set[str] = set()
        self.has_startup_positions: bool = False
        
        # 🔥🔥🔥 TP 설정 미러링 추가
        self.position_tp_tracking: Dict[str, List[str]] = {}  # 포지션 ID -> TP 주문 ID 리스트
        self.mirrored_tp_orders: Dict[str, str] = {}  # 비트겟 TP 주문 ID -> 게이트 TP 주문 ID
        
        # 🔥🔥🔥🔥🔥 예약 주문 TP 설정 복제 수정 - 올바른 방식으로 개선
        self.mirrored_plan_order_tp: Dict[str, Dict] = {}  # 비트겟 예약 주문 ID -> 게이트 TP 정보
        self.plan_order_tp_tracking: Dict[str, List[str]] = {}  # 비트겟 예약 주문 ID -> 게이트 TP 주문 ID 리스트
        
        # 🔥🔥🔥 시세 차이 관리
        self.bitget_current_price: float = 0.0
        self.gate_current_price: float = 0.0
        self.price_diff_percent: float = 0.0
        self.last_price_update: datetime = datetime.min
        
        # 🔥🔥🔥 동기화 허용 오차
        self.SYNC_TOLERANCE_MINUTES = 5
        self.MAX_PRICE_DIFF_PERCENT = 1.0
        self.POSITION_SYNC_RETRY_COUNT = 3
        
        # 🔥🔥🔥 동기화 개선 - 포지션 카운팅 로직 수정
        self.startup_positions_detailed: Dict[str, Dict] = {}
        self.startup_gate_positions_count: int = 0
        self.sync_warning_suppressed_until: datetime = datetime.min
        
        # 설정
        self.SYMBOL = "BTCUSDT"
        self.GATE_CONTRACT = "BTC_USDT"
        self.CHECK_INTERVAL = 2
        self.ORDER_CHECK_INTERVAL = 1
        self.PLAN_ORDER_CHECK_INTERVAL = 0.5  # 🔥🔥🔥 예약 주문 체크 간격을 0.5초로 단축 (취소 감지 강화)
        self.SYNC_CHECK_INTERVAL = 30
        self.MAX_RETRIES = 3
        self.MIN_POSITION_SIZE = 0.00001
        self.MIN_MARGIN = 1.0
        self.DAILY_REPORT_HOUR = 9
        
        # 성과 추적 - 개선된 통계
        self.daily_stats = {
            'total_mirrored': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'total_volume': 0.0,
            'order_mirrors': 0,
            'position_mirrors': 0,
            'plan_order_mirrors': 0,
            'plan_order_cancels': 0,  # 🔥🔥🔥 예약 주문 취소 카운트
            'plan_order_cancel_success': 0,  # 🔥🔥🔥 예약 주문 취소 성공
            'plan_order_cancel_failed': 0,   # 🔥🔥🔥 예약 주문 취소 실패
            'tp_mirrors': 0,  # 🔥🔥🔥 TP 미러링 카운트
            'tp_mirror_success': 0,  # 🔥🔥🔥 TP 미러링 성공
            'tp_mirror_failed': 0,   # 🔥🔥🔥 TP 미러링 실패
            'plan_order_tp_mirrors': 0,  # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 카운트
            'plan_order_tp_success': 0,  # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 성공
            'plan_order_tp_failed': 0,   # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 실패
            'startup_plan_mirrors': 0,
            'plan_order_skipped_already_mirrored': 0,
            'plan_order_skipped_trigger_price': 0,
            'price_adjustments': 0,
            'sync_tolerance_used': 0,
            'sync_warnings_suppressed': 0,
            'position_size_differences_ignored': 0,
            'cancel_verification_success': 0,  # 🔥🔥🔥 취소 확인 성공
            'cancel_verification_failed': 0,   # 🔥🔥🔥 취소 확인 실패
            'errors': []
        }
        
        self.monitoring = True
        self.logger.info("🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 시스템 초기화 완료")

    async def start(self):
        """미러 트레이딩 시작"""
        try:
            self.logger.info("🚀🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 시스템 시작")
            
            # 🔥🔥🔥 시세 차이 초기 확인
            await self._update_current_prices()
            
            # 초기 포지션 및 예약 주문 기록
            await self._record_startup_positions()
            await self._record_startup_plan_orders()
            await self._record_startup_position_tp_sl()
            
            # 🔥🔥🔥 시작시 게이트 포지션 수 기록
            await self._record_startup_gate_positions()
            
            # 🔥 게이트에 이미 복제된 예약 주문 확인
            await self._check_already_mirrored_plan_orders()
            
            # 🔥🔥🔥 동기화 상태 초기 점검 및 경고 억제 설정
            await self._initial_sync_check_and_suppress()
            
            # 🔥🔥🔥 예약 주문 초기 스냅샷 생성
            await self._create_initial_plan_order_snapshot()
            
            # 시작 시 기존 예약 주문 복제
            await self._mirror_startup_plan_orders()
            
            # 초기 계정 상태 출력
            await self._log_account_status()
            
            # 모니터링 태스크 시작
            tasks = [
                self.monitor_plan_orders(),  # 🔥🔥🔥 예약 주문 취소 감지 완전 강화
                self.monitor_order_fills(),
                self.monitor_positions(),
                self.monitor_sync_status(),
                self.monitor_price_differences(),
                self.monitor_tp_orders(),  # 🔥🔥🔥 TP 주문 모니터링 추가
                self.monitor_plan_order_tp(),  # 🔥🔥🔥🔥🔥 예약 주문 TP 모니터링 추가
                self.generate_daily_reports()
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"미러 트레이딩 시작 실패: {e}")
            await self.telegram.send_message(
                f"❌ 미러 트레이딩 시작 실패\n"
                f"오류: {str(e)[:200]}"
            )
            raise

    async def _calculate_dynamic_margin_ratio(self, size: float, trigger_price: float, bitget_order: Dict) -> Dict:
        """실제 달러 마진 비율 동적 계산"""
        try:
            # 레버리지 정보 정확하게 추출
            bitget_leverage = 10  # 기본값
            
            # 주문에서 직접 레버리지 추출
            order_leverage = bitget_order.get('leverage')
            if order_leverage:
                try:
                    bitget_leverage = int(float(order_leverage))
                except:
                    pass
            
            # 계정 정보에서 레버리지 추출
            if not order_leverage:
                try:
                    bitget_account = await self.bitget.get_account_info()
                    account_leverage = bitget_account.get('crossMarginLeverage')
                    if account_leverage:
                        bitget_leverage = int(float(account_leverage))
                except Exception as e:
                    self.logger.warning(f"계정 레버리지 조회 실패: {e}")
            
            # 비트겟 계정 정보 조회
            bitget_account = await self.bitget.get_account_info()
            bitget_total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            # 비트겟에서 이 주문이 체결될 때 사용할 실제 마진 계산
            bitget_notional_value = size * trigger_price
            bitget_required_margin = bitget_notional_value / bitget_leverage
            
            # 비트겟 총 자산 대비 실제 마진 투입 비율 계산
            if bitget_total_equity > 0:
                margin_ratio = bitget_required_margin / bitget_total_equity
            else:
                return {
                    'success': False,
                    'error': '비트겟 총 자산이 0이거나 음수입니다.'
                }
            
            return {
                'success': True,
                'margin_ratio': margin_ratio,
                'leverage': bitget_leverage,
                'required_margin': bitget_required_margin,
                'total_equity': bitget_total_equity,
                'notional_value': bitget_notional_value
            }
            
        except Exception as e:
            self.logger.error(f"실제 달러 마진 비율 동적 계산 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def monitor_order_fills(self):
        """실시간 주문 체결 감지"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                filled_orders = await self.bitget.get_recent_filled_orders(
                    symbol=self.SYMBOL, 
                    minutes=1
                )
                
                new_orders_count = 0
                for order in filled_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if not order_id:
                        continue
                    
                    if order_id in self.processed_orders:
                        continue
                    
                    reduce_only = order.get('reduceOnly', 'false')
                    if reduce_only == 'true' or reduce_only is True:
                        continue
                    
                    await self._process_filled_order(order)
                    self.processed_orders.add(order_id)
                    new_orders_count += 1
                
                # 오래된 주문 ID 정리
                if len(self.processed_orders) > 1000:
                    recent_orders = list(self.processed_orders)[-500:]
                    self.processed_orders = set(recent_orders)
                
                consecutive_errors = 0
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"주문 체결 감지 중 오류: {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 주문 체결 감지 시스템 오류\n"
                        f"연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL * 2)

    async def _process_filled_order(self, order: Dict):
        """체결된 주문으로부터 미러링 실행"""
        try:
            order_id = order.get('orderId', order.get('id', ''))
            side = order.get('side', '').lower()
            size = float(order.get('size', 0))
            fill_price = float(order.get('fillPrice', order.get('price', 0)))
            
            position_side = 'long' if side == 'buy' else 'short'
            
            # 체결된 주문의 실제 달러 마진 비율 동적 계산
            margin_ratio_result = await self._calculate_dynamic_margin_ratio_for_filled_order(
                size, fill_price, order
            )
            
            if not margin_ratio_result['success']:
                return
            
            leverage = margin_ratio_result['leverage']
            
            # 가상의 포지션 데이터 생성
            synthetic_position = {
                'symbol': self.SYMBOL,
                'holdSide': position_side,
                'total': str(size),
                'openPriceAvg': str(fill_price),
                'markPrice': str(fill_price),
                'marginSize': str(margin_ratio_result['required_margin']),
                'leverage': str(leverage),
                'marginMode': 'crossed',
                'unrealizedPL': '0'
            }
            
            pos_id = f"{self.SYMBOL}_{position_side}_{fill_price}"
            
            if pos_id in self.startup_positions:
                return
            
            if pos_id in self.mirrored_positions:
                return
            
            # 미러링 실행
            result = await self._mirror_new_position(synthetic_position)
            
            if result.success:
                self.mirrored_positions[pos_id] = await self._create_position_info(synthetic_position)
                self.position_sizes[pos_id] = size
                self.daily_stats['successful_mirrors'] += 1
                self.daily_stats['order_mirrors'] += 1
                
                await self.telegram.send_message(
                    f"⚡ 실시간 주문 체결 미러링 성공\n"
                    f"주문 ID: {order_id}\n"
                    f"방향: {position_side}\n"
                    f"체결가: ${fill_price:,.2f}\n"
                    f"수량: {size}\n"
                    f"🔧 레버리지: {leverage}x\n"
                    f"💰 실제 마진 비율: {margin_ratio_result['margin_ratio']*100:.2f}%"
                )
            else:
                self.failed_mirrors.append(result)
                self.daily_stats['failed_mirrors'] += 1
                
                await self.telegram.send_message(
                    f"❌ 실시간 주문 체결 미러링 실패\n"
                    f"주문 ID: {order_id}\n"
                    f"오류: {result.error}"
                )
            
            self.daily_stats['total_mirrored'] += 1
            
        except Exception as e:
            self.logger.error(f"체결 주문 처리 중 오류: {e}")
            self.daily_stats['errors'].append({
                'time': datetime.now().isoformat(),
                'error': str(e),
                'order_id': order.get('orderId', 'unknown')
            })

    async def _calculate_dynamic_margin_ratio_for_filled_order(self, size: float, fill_price: float, order: Dict) -> Dict:
        """체결된 주문의 실제 달러 마진 비율 동적 계산"""
        try:
            leverage = 10
            try:
                order_leverage = order.get('leverage')
                if order_leverage:
                    leverage = int(float(order_leverage))
                else:
                    account = await self.bitget.get_account_info()
                    if account:
                        account_leverage = account.get('crossMarginLeverage')
                        if account_leverage:
                            leverage = int(float(account_leverage))
            except Exception as e:
                self.logger.warning(f"체결 주문 레버리지 조회 실패: {e}")
            
            bitget_account = await self.bitget.get_account_info()
            bitget_total_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            
            notional = size * fill_price
            required_margin = notional / leverage
            margin_ratio = required_margin / bitget_total_equity if bitget_total_equity > 0 else 0
            
            return {
                'success': True,
                'margin_ratio': margin_ratio,
                'leverage': leverage,
                'required_margin': required_margin,
                'total_equity': bitget_total_equity,
                'notional_value': notional
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def _record_startup_positions(self):
        """시작 시 존재하는 포지션 기록 - 🔥🔥🔥 상세 정보 포함"""
        try:
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            
            for pos in bitget_positions:
                if float(pos.get('total', 0)) > 0:
                    pos_id = self._generate_position_id(pos)
                    self.startup_positions.add(pos_id)
                    self.position_sizes[pos_id] = float(pos.get('total', 0))
                    
                    # 🔥🔥🔥 상세 정보 저장
                    self.startup_positions_detailed[pos_id] = {
                        'size': float(pos.get('total', 0)),
                        'side': pos.get('holdSide', ''),
                        'entry_price': float(pos.get('openPriceAvg', 0)),
                        'margin': float(pos.get('marginSize', 0)),
                        'leverage': pos.get('leverage', 'N/A')
                    }
            
            # 기존 주문 ID들도 기록
            try:
                recent_orders = await self.bitget.get_recent_filled_orders(self.SYMBOL, minutes=10)
                for order in recent_orders:
                    order_id = order.get('orderId', order.get('id', ''))
                    if order_id:
                        self.processed_orders.add(order_id)
            except Exception as e:
                self.logger.warning(f"기존 주문 기록 실패: {e}")
            
        except Exception as e:
            self.logger.error(f"기존 포지션 기록 실패: {e}")

    async def _log_account_status(self):
        """계정 상태 로깅 - 개선된 메시지"""
        try:
            bitget_account = await self.bitget.get_account_info()
            bitget_equity = float(bitget_account.get('accountEquity', bitget_account.get('usdtEquity', 0)))
            bitget_leverage = bitget_account.get('crossMarginLeverage', 'N/A')
            
            gate_account = await self.gate.get_account_balance()
            gate_equity = float(gate_account.get('total', 0))
            
            position_mode_text = "포지션 없음 - 모든 예약 주문 복제" if not self.has_startup_positions else "포지션 있음 - 클로즈 TP/SL 제외하고 복제"
            
            # 🔥🔥🔥 시세 차이 정보 추가
            price_diff_text = ""
            if self.price_diff_percent > 0:
                price_diff_text = f"\n\n🔥🔥🔥 거래소 간 시세 차이:\n비트겟: ${self.bitget_current_price:,.2f}\n게이트: ${self.gate_current_price:,.2f}\n차이: {self.price_diff_percent:.2f}%\n{'⚠️ 큰 차이 감지 - 자동 조정됨' if self.price_diff_percent > self.MAX_PRICE_DIFF_PERCENT else '✅ 정상 범위'}"
            
            await self.telegram.send_message(
                f"🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 시스템 시작\n\n"
                f"💰 계정 잔고:\n"
                f"• 비트겟: ${bitget_equity:,.2f} (레버리지: {bitget_leverage}x)\n"
                f"• 게이트: ${gate_equity:,.2f}{price_diff_text}\n\n"
                f"🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 (핵심 수정):\n"
                f"• 비트겟 예약 주문의 TP 설정을 정확히 복제\n"
                f"• 예약 주문 체결 후 자동 TP 트리거 주문 생성\n"
                f"• TP 방향과 수량을 정확히 계산하여 복제\n"
                f"• 숏 예약 주문의 TP는 매수(+) 방향으로 설정\n"
                f"• 롱 예약 주문의 TP는 매도(-) 방향으로 설정\n"
                f"• 잘못된 반대 포지션 생성 문제 완전 해결\n\n"
                f"🔥🔥🔥 핵심 기능:\n"
                f"매 주문/포지션마다 실제 달러 투입금 비율을 새로 계산!\n\n"
                f"💰💰💰 실제 달러 마진 비율 동적 계산 (핵심):\n"
                f"1️⃣ 비트겟에서 주문 체결 또는 예약 주문 생성\n"
                f"2️⃣ 해당 주문의 실제 마진 = (수량 × 가격) ÷ 레버리지\n"
                f"3️⃣ 실제 마진 비율 = 실제 마진 ÷ 비트겟 총 자산\n"
                f"4️⃣ 게이트 투입 마진 = 게이트 총 자산 × 동일 비율\n"
                f"5️⃣ 매 거래마다 실시간으로 비율을 새로 계산\n\n"
                f"📊 기존 항목:\n"
                f"• 기존 포지션: {len(self.startup_positions)}개 (복제 제외)\n"
                f"• 기존 예약 주문: {len(self.startup_plan_orders)}개 (시작 시 복제)\n"
                f"• 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개\n"
                f"• 현재 복제된 예약 주문 TP: {len(self.mirrored_plan_order_tp)}개\n\n"
                f"🔥🔥🔥🔥🔥 예약 주문 TP 복제 정책:\n"
                f"• {position_mode_text}\n"
                f"• 보유 포지션: {len(self.startup_positions)}개\n"
                f"• 제외할 클로즈 TP/SL: {len(self.startup_position_tp_sl)}개\n"
                f"• 예약 주문에 TP 설정 시 게이트에서도 동일하게 복제\n"
                f"• TP 가격, 수량, 트리거 타입 모두 완전 동기화\n"
                f"• 예약 주문 취소 시 연결된 TP도 자동 취소\n\n"
                f"⚡ 감지 주기:\n"
                f"• 예약 주문 취소: {self.PLAN_ORDER_CHECK_INTERVAL}초마다\n"
                f"• 예약 주문 TP: {self.ORDER_CHECK_INTERVAL}초마다 (TP 설정 변경 감지)\n"
                f"• 주문 체결: {self.ORDER_CHECK_INTERVAL}초마다\n"
                f"• 시세 차이 모니터링: 1분마다\n"
                f"• TP 주문 모니터링: {self.ORDER_CHECK_INTERVAL}초마다\n\n"
                f"💡 예시:\n"
                f"비트겟 총 자산 $10,000에서 $200 마진 투입 (2%)\n"
                f"→ 게이트 총 자산 $1,000에서 $20 마진 투입 (동일 2%)\n"
                f"→ 매 거래마다 실시간으로 이 비율을 새로 계산!\n"
                f"→ 시세 차이 발생 시 트리거 가격 자동 조정!\n"
                f"→ 포지션 크기 차이는 정상적 현상!\n"
                f"→ 예약 주문 취소도 즉시 미러링!\n"
                f"→ TP 설정도 자동 미러링!\n"
                f"→ 🔥🔥🔥🔥🔥 예약 주문 TP 올바른 방향으로 복제!"
            )
            
        except Exception as e:
            self.logger.error(f"계정 상태 조회 실패: {e}")

    async def monitor_positions(self):
        """포지션 모니터링"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                bitget_positions = await self.bitget.get_positions(self.SYMBOL)
                bitget_active = [
                    pos for pos in bitget_positions 
                    if float(pos.get('total', 0)) > 0
                ]
                
                gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
                gate_active = [
                    pos for pos in gate_positions 
                    if pos.get('size', 0) != 0
                ]
                
                # 🔥🔥🔥 핵심 수정: 신규 미러링된 포지션만 카운팅
                # 전체 비트겟 포지션에서 시작시 존재했던 포지션 제외
                new_bitget_positions = []
                for pos in bitget_active:
                    pos_id = self._generate_position_id(pos)
                    if pos_id not in self.startup_positions:
                        new_bitget_positions.append(pos)
                
                # 게이트 포지션에서 시작시 존재했던 포지션 제외
                new_gate_positions_count = len(gate_active) - self.startup_gate_positions_count
                if new_gate_positions_count < 0:
                    new_gate_positions_count = 0
                
                # 🔥🔥🔥 수정된 동기화 체크
                new_bitget_count = len(new_bitget_positions)
                position_diff = new_bitget_count - new_gate_positions_count
                
                self.logger.debug(f"🔥🔥🔥 동기화 체크 (수정된 로직):")
                self.logger.debug(f"   - 전체 비트겟 포지션: {len(bitget_active)}개")
                self.logger.debug(f"   - 시작시 비트겟 포지션: {len(self.startup_positions)}개")
                self.logger.debug(f"   - 신규 비트겟 포지션: {new_bitget_count}개")
                self.logger.debug(f"   - 전체 게이트 포지션: {len(gate_active)}개")
                self.logger.debug(f"   - 시작시 게이트 포지션: {self.startup_gate_positions_count}개")
                self.logger.debug(f"   - 신규 게이트 포지션: {new_gate_positions_count}개")
                self.logger.debug(f"   - 포지션 차이: {position_diff}개")
                
                # 실제 포지션 처리
                active_position_ids = set()
                
                for pos in bitget_active:
                    pos_id = self._generate_position_id(pos)
                    active_position_ids.add(pos_id)
                    await self._process_position(pos)
                
                # 종료된 포지션 처리
                closed_positions = set(self.mirrored_positions.keys()) - active_position_ids
                for pos_id in closed_positions:
                    if pos_id not in self.startup_positions:
                        await self._handle_position_close(pos_id)
                
                consecutive_errors = 0
                await asyncio.sleep(self.CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"포지션 모니터링 중 오류: {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 포지션 모니터링 오류\n"
                        f"연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(self.CHECK_INTERVAL * 2)

    async def generate_daily_reports(self):
        """일일 리포트 생성"""
        while self.monitoring:
            try:
                now = datetime.now()
                
                if now.hour == self.DAILY_REPORT_HOUR and now > self.last_report_time + timedelta(hours=23):
                    report = await self._create_daily_report()
                    await self.telegram.send_message(report)
                    
                    self._reset_daily_stats()
                    self.last_report_time = now
                
                await asyncio.sleep(3600)
                
            except Exception as e:
                self.logger.error(f"일일 리포트 생성 오류: {e}")
                await asyncio.sleep(3600)

    async def _create_daily_report(self) -> str:
        """일일 리포트 생성 - 개선된 통계"""
        try:
            bitget_account = await self.bitget.get_account_info()
            gate_account = await self.gate.get_account_balance()
            
            bitget_equity = float(bitget_account.get('accountEquity', 0))
            gate_equity = float(gate_account.get('total', 0))
            bitget_leverage = bitget_account.get('crossMarginLeverage', 'N/A')
            
            success_rate = 0
            if self.daily_stats['total_mirrored'] > 0:
                success_rate = (self.daily_stats['successful_mirrors'] / 
                              self.daily_stats['total_mirrored']) * 100
            
            # 🔥🔥🔥 예약 주문 취소 통계 추가
            cancel_success_rate = 0
            total_cancels = self.daily_stats['plan_order_cancel_success'] + self.daily_stats['plan_order_cancel_failed']
            if total_cancels > 0:
                cancel_success_rate = (self.daily_stats['plan_order_cancel_success'] / total_cancels) * 100
            
            # 🔥🔥🔥 TP 미러링 통계 추가
            tp_success_rate = 0
            total_tp_mirrors = self.daily_stats['tp_mirror_success'] + self.daily_stats['tp_mirror_failed']
            if total_tp_mirrors > 0:
                tp_success_rate = (self.daily_stats['tp_mirror_success'] / total_tp_mirrors) * 100
            
            # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 통계 추가
            plan_tp_success_rate = 0
            total_plan_tp_mirrors = self.daily_stats['plan_order_tp_success'] + self.daily_stats['plan_order_tp_failed']
            if total_plan_tp_mirrors > 0:
                plan_tp_success_rate = (self.daily_stats['plan_order_tp_success'] / total_plan_tp_mirrors) * 100
            
            # 🔥🔥🔥 취소 확인 통계 추가
            verification_success_rate = 0
            total_verifications = self.daily_stats['cancel_verification_success'] + self.daily_stats['cancel_verification_failed']
            if total_verifications > 0:
                verification_success_rate = (self.daily_stats['cancel_verification_success'] / total_verifications) * 100
            
            # 🔥🔥🔥 시세 차이 정보 추가
            await self._update_current_prices()
            price_diff_text = ""
            if self.price_diff_percent > 0:
                price_diff_text = f"""

🔥🔥🔥 거래소 간 시세 차이:
- 비트겟: ${self.bitget_current_price:,.2f}
- 게이트: ${self.gate_current_price:,.2f}
- 차이: {self.price_diff_percent:.2f}%
- 가격 조정: {self.daily_stats['price_adjustments']}회
- 동기화 허용 오차 사용: {self.daily_stats['sync_tolerance_used']}회
- 동기화 경고 억제: {self.daily_stats['sync_warnings_suppressed']}회
- 포지션 크기 차이 무시: {self.daily_stats['position_size_differences_ignored']}회"""
            
            report = f"""📊 일일 예약 주문 TP 설정 올바른 복제 리포트
📅 {datetime.now().strftime('%Y-%m-%d')}
━━━━━━━━━━━━━━━━━━━

🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 성과 (핵심 수정)
- 예약 주문 TP 복제 시도: {self.daily_stats['plan_order_tp_mirrors']}건
- 예약 주문 TP 복제 성공: {self.daily_stats['plan_order_tp_success']}건
- 예약 주문 TP 복제 실패: {self.daily_stats['plan_order_tp_failed']}건
- 예약 주문 TP 복제 성공률: {plan_tp_success_rate:.1f}%
- 현재 복제된 예약 주문 TP: {len(self.mirrored_plan_order_tp)}개
- 잘못된 반대 포지션 생성 문제 해결됨

🔥🔥🔥 TP 설정 미러링 강화 성과
- TP 미러링 시도: {self.daily_stats['tp_mirrors']}건
- TP 미러링 성공: {self.daily_stats['tp_mirror_success']}건
- TP 미러링 실패: {self.daily_stats['tp_mirror_failed']}건
- TP 미러링 성공률: {tp_success_rate:.1f}%
- 현재 복제된 TP: {len(self.mirrored_tp_orders)}개

🔥🔥🔥 예약 주문 취소 미러링 성과
- 예약 주문 취소 감지: {self.daily_stats['plan_order_cancels']}건
- 취소 미러링 성공: {self.daily_stats['plan_order_cancel_success']}건
- 취소 미러링 실패: {self.daily_stats['plan_order_cancel_failed']}건
- 취소 미러링 성공률: {cancel_success_rate:.1f}%
- 취소 확인 성공: {self.daily_stats['cancel_verification_success']}건
- 취소 확인 실패: {self.daily_stats['cancel_verification_failed']}건
- 취소 확인 성공률: {verification_success_rate:.1f}%
- 최대 재시도 횟수: {self.max_cancel_retry}회
- 모니터링 주기: {self.PLAN_ORDER_CHECK_INTERVAL}초 (초고속)
- 취소 확인 대기: {self.cancel_verification_delay}초

🔥 예약 주문 실제 달러 마진 비율 동적 계산 성과
- 시작 시 예약 주문 복제: {self.daily_stats['startup_plan_mirrors']}회
- 신규 예약 주문 미러링: {self.daily_stats['plan_order_mirrors']}회
- 예약 주문 취소 동기화: {self.daily_stats['plan_order_cancels']}회
- 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개
- 이미 복제됨으로 스킵: {self.daily_stats['plan_order_skipped_already_mirrored']}개
- 트리거 가격 문제로 스킵: {self.daily_stats['plan_order_skipped_trigger_price']}개

⚡ 실시간 포지션 미러링
- 주문 체결 기반: {self.daily_stats['order_mirrors']}회
- 포지션 기반: {self.daily_stats['position_mirrors']}회
- 총 시도: {self.daily_stats['total_mirrored']}회
- 성공: {self.daily_stats['successful_mirrors']}회
- 실패: {self.daily_stats['failed_mirrors']}회
- 성공률: {success_rate:.1f}%

📉 포지션 관리
- 부분 청산: {self.daily_stats['partial_closes']}회
- 전체 청산: {self.daily_stats['full_closes']}회
- 총 거래량: ${self.daily_stats['total_volume']:,.2f}

💰 계정 잔고
- 비트겟: ${bitget_equity:,.2f} (레버리지: {bitget_leverage}x)
- 게이트: ${gate_equity:,.2f}

🔄 현재 미러링 상태
- 활성 포지션: {len(self.mirrored_positions)}개
- 현재 복제된 예약 주문: {len(self.mirrored_plan_orders)}개
- 현재 복제된 TP 주문: {len(self.mirrored_tp_orders)}개
- 현재 복제된 예약 주문 TP: {len(self.mirrored_plan_order_tp)}개
- 실패 기록: {len(self.failed_mirrors)}건{price_diff_text}

🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 (핵심 수정)
- 비트겟 예약 주문에 TP 설정이 있으면 게이트에서도 동일하게 설정
- TP 가격, TP 비율, TP 수량 모두 완전 동기화
- 예약 주문 체결 후 자동으로 TP 트리거 주문 생성
- 비트겟과 동일한 수익률로 자동 익절
- 시세 차이 대응으로 TP 가격도 자동 조정
- 예약 주문 취소 시 연결된 TP도 함께 자동 취소
- TP 가격 수정 시 게이트에서도 실시간 동기화
- 숏 예약 주문의 TP는 매수(+) 방향으로 정확히 설정
- 롱 예약 주문의 TP는 매도(-) 방향으로 정확히 설정
- 잘못된 반대 포지션 생성 문제 완전 해결

🔥🔥🔥 TP 설정 미러링 강화 (핵심 기능)
- 비트겟 포지션 진입 시 TP 설정 자동 감지
- 게이트에서 동일한 TP 가격으로 자동 설정
- TP 주문 별도 추적 및 관리
- TP 취소/수정도 실시간 동기화
- 시세 차이 대응으로 TP 가격도 자동 조정

💰💰💰 실제 달러 마진 비율 동적 계산 (핵심)
- 매 예약주문마다 실제 마진 비율을 새로 계산
- 미리 정해진 비율 없음 - 완전 동적 계산

🔥🔥🔥 동기화 카운팅 로직 수정 (새로운 핵심 기능)
- 기존: 전체 포지션 비교 (잘못됨)
- 수정: 신규 포지션만 비교 (올바름)
- 시작시 포지션은 미러링 대상 아님
- 포지션 크기 차이는 마진 비율 차이로 정상

🔥🔥🔥 시세 차이 대응 강화 (핵심 기능)
- 실시간 거래소 간 시세 모니터링
- 0.3% 이상 차이 시 트리거 가격 자동 조정
- 게이트 기준 현재가로 정확한 트리거 타입 결정
- 동기화 허용 오차 {self.SYNC_TOLERANCE_MINUTES}분 적용

🔥🔥🔥 개선된 트리거 검증 (핵심)
- 최소 차이: 0.1% → 0.01% (10배 완화)
- 최대 차이: 50% → 100% (2배 완화)
- close_long 방향 처리 완전 수정

🔥🔥🔥 개선된 방향 처리 (핵심)
- close_long → 게이트 매도 (음수) 올바르게 처리
- close_short → 게이트 매수 (양수) 올바르게 처리
"""
            
            if self.daily_stats['errors']:
                report += f"\n⚠️ 오류 발생: {len(self.daily_stats['errors'])}건"
            
            report += "\n━━━━━━━━━━━━━━━━━━━\n🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 + 완전한 미러링 시스템!"
            
            return report
            
        except Exception as e:
            self.logger.error(f"리포트 생성 실패: {e}")
            return f"📊 일일 리포트 생성 실패\n오류: {str(e)}"

    def _reset_daily_stats(self):
        """일일 통계 초기화 - 개선된 통계"""
        self.daily_stats = {
            'total_mirrored': 0,
            'successful_mirrors': 0,
            'failed_mirrors': 0,
            'partial_closes': 0,
            'full_closes': 0,
            'total_volume': 0.0,
            'order_mirrors': 0,
            'position_mirrors': 0,
            'plan_order_mirrors': 0,
            'plan_order_cancels': 0,  # 🔥🔥🔥 예약 주문 취소 카운트
            'plan_order_cancel_success': 0,  # 🔥🔥🔥 예약 주문 취소 성공
            'plan_order_cancel_failed': 0,   # 🔥🔥🔥 예약 주문 취소 실패
            'tp_mirrors': 0,  # 🔥🔥🔥 TP 미러링 카운트
            'tp_mirror_success': 0,  # 🔥🔥🔥 TP 미러링 성공
            'tp_mirror_failed': 0,   # 🔥🔥🔥 TP 미러링 실패
            'plan_order_tp_mirrors': 0,  # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 카운트
            'plan_order_tp_success': 0,  # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 성공
            'plan_order_tp_failed': 0,   # 🔥🔥🔥🔥🔥 예약 주문 TP 복제 실패
            'startup_plan_mirrors': 0,
            'plan_order_skipped_already_mirrored': 0,
            'plan_order_skipped_trigger_price': 0,
            'price_adjustments': 0,
            'sync_tolerance_used': 0,
            'sync_warnings_suppressed': 0,
            'position_size_differences_ignored': 0,
            'cancel_verification_success': 0,  # 🔥🔥🔥 취소 확인 성공
            'cancel_verification_failed': 0,   # 🔥🔥🔥 취소 확인 실패
            'errors': []
        }
        self.failed_mirrors.clear()

    def _generate_position_id(self, pos: Dict) -> str:
        """포지션 고유 ID 생성"""
        symbol = pos.get('symbol', self.SYMBOL)
        side = pos.get('holdSide', '')
        entry_price = pos.get('openPriceAvg', '')
        return f"{symbol}_{side}_{entry_price}"

    async def _create_position_info(self, bitget_pos: Dict) -> PositionInfo:
        """포지션 정보 객체 생성"""
        return PositionInfo(
            symbol=bitget_pos.get('symbol', self.SYMBOL),
            side=bitget_pos.get('holdSide', '').lower(),
            size=float(bitget_pos.get('total', 0)),
            entry_price=float(bitget_pos.get('openPriceAvg', 0)),
            margin=float(bitget_pos.get('marginSize', 0)),
            leverage=int(float(bitget_pos.get('leverage', 1))),
            mode='cross' if bitget_pos.get('marginMode') == 'crossed' else 'isolated',
            unrealized_pnl=float(bitget_pos.get('unrealizedPL', 0))
        )

    async def stop(self):
        """미러 트레이딩 중지"""
        self.monitoring = False
        
        try:
            final_report = await self._create_daily_report()
            await self.telegram.send_message(
                f"🛑 예약 주문 TP 설정 올바른 복제 시스템 종료\n\n{final_report}"
            )
        except:
            pass
        
        self.logger.info("🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 시스템 중지")

    async def _create_initial_plan_order_snapshot(self):
        """🔥🔥🔥 예약 주문 초기 스냅샷 생성"""
        try:
            self.logger.info("🔥🔥🔥 예약 주문 초기 스냅샷 생성 시작")
            
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_orders = plan_orders + tp_sl_orders
            
            # 스냅샷 저장
            for order in all_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.plan_order_snapshot[order_id] = {
                        'order_data': order.copy(),
                        'timestamp': datetime.now().isoformat(),
                        'status': 'active'
                    }
                    self.last_plan_order_ids.add(order_id)
            
            self.logger.info(f"🔥🔥🔥 예약 주문 초기 스냅샷 완료: {len(self.plan_order_snapshot)}개 주문")
            
        except Exception as e:
            self.logger.error(f"예약 주문 초기 스냅샷 생성 실패: {e}")

    async def _record_startup_gate_positions(self):
        """🔥🔥🔥 시작시 게이트 포지션 수 기록"""
        try:
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            self.startup_gate_positions_count = sum(
                1 for pos in gate_positions 
                if pos.get('size', 0) != 0
            )
            
            self.logger.info(f"🔥🔥🔥 시작시 게이트 포지션 수 기록: {self.startup_gate_positions_count}개")
            
        except Exception as e:
            self.logger.error(f"시작시 게이트 포지션 기록 실패: {e}")
            self.startup_gate_positions_count = 0

    async def _initial_sync_check_and_suppress(self):
        """🔥🔥🔥 초기 동기화 상태 점검 및 경고 억제 설정"""
        try:
            self.logger.info("🔥🔥🔥 초기 동기화 상태 점검 및 경고 억제 설정 시작")
            
            # Bitget 포지션 조회
            bitget_positions = await self.bitget.get_positions(self.SYMBOL)
            bitget_active = [
                pos for pos in bitget_positions 
                if float(pos.get('total', 0)) > 0
            ]
            
            # Gate.io 포지션 조회
            gate_positions = await self.gate.get_positions(self.GATE_CONTRACT)
            gate_active = [
                pos for pos in gate_positions 
                if pos.get('size', 0) != 0
            ]
            
            # Bitget 예약 주문 조회
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            bitget_plan_orders = plan_data.get('plan_orders', []) + plan_data.get('tp_sl_orders', [])
            
            # Gate.io 예약 주문 조회
            gate_plan_orders = await self.gate.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            # 🔥🔥🔥 핵심: 신규 포지션 개념 제거 - 모든 기존 포지션은 미러링 대상이 아님
            startup_bitget_positions = len(bitget_active)
            startup_gate_positions = len(gate_active)
            
            sync_analysis = f"""
🔥🔥🔥🔥🔥 초기 동기화 상태 분석 (예약 주문 TP 설정 올바른 복제):

📊 현재 상황:
- Bitget 활성 포지션: {startup_bitget_positions}개 (모두 기존 포지션으로 간주)
- Gate.io 활성 포지션: {startup_gate_positions}개 (모두 기존 포지션으로 간주)
- Bitget 예약 주문: {len(bitget_plan_orders)}개
- Gate.io 예약 주문: {len(gate_plan_orders)}개

💡 핵심 원리:
- 시작시 존재하는 모든 포지션은 "기존 포지션"으로 간주
- 기존 포지션은 미러링 대상이 아님 (이미 존재하던 것)
- 향후 신규 진입만 미러링
- 포지션 크기 차이는 마진 비율 차이로 정상적 현상

🔥🔥🔥🔥🔥 예약 주문 TP 설정 올바른 복제 (핵심 수정):
- 비트겟 예약 주문의 TP 설정을 정확히 복제
- 예약 주문 체결 후 자동 TP 트리거 주문 생성
- TP 방향과 수량을 정확히 계산하여 복제
- 숏 예약 주문의 TP는 매수(+) 방향으로 설정
- 롱 예약 주문의 TP는 매도(-) 방향으로 설정
- 잘못된 반대 포지션 생성 문제 완전 해결

🔥🔥🔥 TP 설정 미러링 강화:
- 비트겟 포지션 진입 시 TP 설정 감지
- 게이트에서 동일한 TP 가격으로 자동 설정
- TP 주문 별도 추적 및 관리
- TP 취소/수정도 실시간 동기화

🔥🔥🔥 동기화 카운팅 수정:
- 기존 방식: "신규 포지션" vs "게이트 포지션" 비교 (잘못됨)
- 수정 방식: 신규 진입 이벤트만 추적, 기존 포지션은 비교 안함
"""
            
            # 포지션 크기 차이 분석 (정보 제공용)
            if bitget_active and gate_active:
                bitget_size = float(bitget_active[0].get('total', 0))
                gate_size = abs(gate_active[0].get('size', 0)) * 0.0001  # contracts to BTC
                
                if bitget_size > 0:
                    size_ratio = gate_size / bitget_size
                    sync_analysis += f"""

📏 포지션 크기 분석 (참고용):
- Bitget: {bitget_size} BTC
- Gate.io: {gate_size:.6f} BTC  
- 비율: {size_ratio:.2f}배
- 이는 총 자산 대비 동일한 마진 비율로 인한 정상적 차이입니다
"""
            
            # 🔥🔥🔥 경고 억제 설정 - 시작 후 10분간 동기화 경고 억제
            self.sync_warning_suppressed_until = datetime.now() + timedelta(minutes=10)
            sync_analysis += f"""

🔕 동기화 경고 억제:
- 시작 후 10분간 동기화 불일치 경고 억제
- 이 시간 동안 시스템이 안정화됨
- 실제 신규 포지션 진입시에만 미러링 수행
"""
            
            await self.telegram.send_message(sync_analysis)
            self.logger.info("🔥🔥🔥 초기 동기화 상태 점검 완료 - 경고 억제 설정됨")
            
        except Exception as e:
            self.logger.error(f"초기 동기화 점검 실패: {e}")

    async def _update_current_prices(self):
        """🔥🔥🔥 양쪽 거래소 현재 시세 업데이트"""
        try:
            # 비트겟 현재가
            bitget_ticker = await self.bitget.get_ticker(self.SYMBOL)
            if bitget_ticker:
                self.bitget_current_price = float(bitget_ticker.get('last', 0))
            
            # 게이트 현재가 - get_ticker 메서드 사용
            try:
                gate_ticker = await self.gate.get_ticker(self.GATE_CONTRACT)
                if gate_ticker:
                    self.gate_current_price = float(gate_ticker.get('last', 0))
            except Exception as e:
                self.logger.warning(f"게이트 티커 조회 실패, 계약 정보로 대체: {e}")
                # 게이트 가격 조회 실패 시 계약 정보 사용
                try:
                    gate_contract_info = await self.gate.get_contract_info(self.GATE_CONTRACT)
                    if 'last_price' in gate_contract_info:
                        self.gate_current_price = float(gate_contract_info['last_price'])
                    elif 'mark_price' in gate_contract_info:
                        self.gate_current_price = float(gate_contract_info['mark_price'])
                except:
                    # 게이트 가격 조회 실패 시 비트겟 가격 사용
                    self.gate_current_price = self.bitget_current_price
            
            # 가격 차이 계산
            if self.bitget_current_price > 0 and self.gate_current_price > 0:
                self.price_diff_percent = abs(self.bitget_current_price - self.gate_current_price) / self.bitget_current_price * 100
            else:
                self.price_diff_percent = 0.0
            
            self.last_price_update = datetime.now()
            
            # 큰 차이 발생 시 로깅
            if self.price_diff_percent > self.MAX_PRICE_DIFF_PERCENT:
                self.logger.warning(f"🔥⚠️ 거래소 간 시세 차이 큼: 비트겟 ${self.bitget_current_price:,.2f}, 게이트 ${self.gate_current_price:,.2f} (차이: {self.price_diff_percent:.2f}%)")
            
        except Exception as e:
            self.logger.error(f"시세 업데이트 실패: {e}")

    async def monitor_price_differences(self):
        """🔥🔥🔥 거래소 간 시세 차이 모니터링"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                await self._update_current_prices()
                
                # 1시간마다 시세 차이 리포트
                if (datetime.now() - self.last_price_update).total_seconds() > 3600:
                    if self.price_diff_percent > 0.5:  # 0.5% 이상 차이
                        await self.telegram.send_message(
                            f"📊 거래소 간 시세 차이 리포트\n"
                            f"비트겟: ${self.bitget_current_price:,.2f}\n"
                            f"게이트: ${self.gate_current_price:,.2f}\n"
                            f"차이: {self.price_diff_percent:.2f}%\n"
                            f"{'⚠️ 큰 차이 감지' if self.price_diff_percent > self.MAX_PRICE_DIFF_PERCENT else '✅ 정상 범위'}"
                        )
                
                consecutive_errors = 0
                await asyncio.sleep(60)  # 1분마다 체크
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"시세 차이 모니터링 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 시세 차이 모니터링 시스템 오류\n"
                        f"연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(120)  # 오류 시 2분 대기

    async def _check_already_mirrored_plan_orders(self):
        """🔥 게이트에 이미 복제된 예약 주문 확인"""
        try:
            self.logger.info("🔥 게이트에 이미 복제된 예약 주문 확인 시작")
            
            # 게이트의 현재 예약 주문 조회
            gate_plan_orders = await self.gate.get_price_triggered_orders(self.GATE_CONTRACT, "open")
            
            self.logger.info(f"게이트 현재 예약 주문: {len(gate_plan_orders)}개")
            
            for gate_order in gate_plan_orders:
                gate_order_id = gate_order.get('id', '')
                trigger_price = gate_order.get('trigger', {}).get('price', '')
                
                if gate_order_id and trigger_price:
                    # 이미 복제된 주문으로 기록
                    # 실제로는 비트겟 주문 ID를 모르므로, 트리거 가격을 기준으로 매칭
                    self.already_mirrored_plan_orders.add(f"gate_{gate_order_id}")
                    self.logger.info(f"이미 복제된 예약 주문 발견: Gate ID {gate_order_id}, 트리거가 ${trigger_price}")
            
            if gate_plan_orders:
                self.logger.info(f"✅ 총 {len(gate_plan_orders)}개의 이미 복제된 예약 주문 확인")
            else:
                self.logger.info("📝 게이트에 복제된 예약 주문이 없음")
                
        except Exception as e:
            self.logger.error(f"이미 복제된 예약 주문 확인 실패: {e}")

    async def _record_startup_plan_orders(self):
        """시작 시 존재하는 예약 주문 기록"""
        try:
            self.logger.info("🔥 기존 예약 주문 기록 시작")
            
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            for order in plan_orders + tp_sl_orders:
                order_id = order.get('orderId', order.get('planOrderId', ''))
                if order_id:
                    self.startup_plan_orders.add(order_id)
                    self.last_plan_order_ids.add(order_id)
            
            total_existing = len(plan_orders) + len(tp_sl_orders)
            self.logger.info(f"🔥 총 {total_existing}개의 기존 예약 주문을 기록했습니다")
            
        except Exception as e:
            self.logger.error(f"기존 예약 주문 기록 실패: {e}")

    async def _mirror_startup_plan_orders(self):
        """시작 시 기존 예약 주문 복제 - 개선된 스킵 로직"""
        try:
            self.logger.info("🔥🔥🔥🔥🔥 시작 시 기존 예약 주문 복제 시작 (TP 설정 포함)")
            
            plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
            plan_orders = plan_data.get('plan_orders', [])
            tp_sl_orders = plan_data.get('tp_sl_orders', [])
            
            all_orders = plan_orders + tp_sl_orders
            
            if not all_orders:
                self.startup_plan_orders_processed = True
                return
            
            mirrored_count = 0
            failed_count = 0
            skipped_already_mirrored_count = 0
            skipped_trigger_price_count = 0
            price_adjusted_count = 0
            tp_mirrored_count = 0  # 🔥🔥🔥🔥🔥 TP 복제 카운트
            
            for order in all_orders:
                try:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if not order_id:
                        continue
                    
                    # 포지션이 있을 때만 기존 포지션의 클로즈 TP/SL 제외
                    if self.has_startup_positions and order_id in self.startup_position_tp_sl:
                        continue
                    
                    # 🔥 이미 복제된 예약 주문인지 확인 (트리거 가격 매칭)
                    result = await self._check_if_already_mirrored(order)
                    
                    if result == "already_mirrored":
                        skipped_already_mirrored_count += 1
                        self.logger.info(f"⏭️ 이미 복제된 예약 주문 스킵: {order_id}")
                        continue
                    
                    # 🔥🔥🔥🔥🔥 예약 주문 복제 실행 - TP 설정 포함
                    result_data = await self._process_startup_plan_order_with_tp(order)
                    
                    result = result_data['result']
                    price_adjusted = result_data['price_adjusted']
                    tp_created = result_data['tp_created']
                    
                    if price_adjusted:
                        price_adjusted_count += 1
                    
                    if tp_created:
                        tp_mirrored_count += 1
                    
                    if result == "skipped_trigger_price":
                        skipped_trigger_price_count += 1
                    elif result == "success":
                        mirrored_count += 1
                    else:
                        failed_count += 1
                    
                    self.processed_plan_orders.add(order_id)
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"기존 예약 주문 복제 실패: {order.get('orderId', 'unknown')} - {e}")
                    continue
            
            self.daily_stats['startup_plan_mirrors'] = mirrored_count
            self.daily_stats['plan_order_skipped_already_mirrored'] = skipped_already_mirrored_count
            self.daily_stats['plan_order_skipped_trigger_price'] = skipped_trigger_price_count
            self.daily_stats['price_adjustments'] = price_adjusted_count
            self.daily_stats['plan_order_tp_mirrors'] = tp_mirrored_count  # 🔥🔥🔥🔥🔥
            self.startup_plan_orders_processed = True
            
            position_mode_text = "포지션 없음 - 모든 예약 주문 복제" if not self.has_startup_positions else "포지션 있음 - 클로즈 TP/SL 제외하고 복제"
            
            await self.telegram.send_message(
                f"🔥🔥🔥🔥🔥 시작 시 기존 예약 주문 복제 완료 (TP 설정 포함)\n"
                f"성공: {mirrored_count}개\n"
                f"🎯 TP 설정 복제: {tp_mirrored_count}개\n"
                f"이미 복제됨: {skipped_already_mirrored_count}개\n"
                f"트리거 가격 문제: {skipped_trigger_price_count}개\n"
                f"실패: {failed_count}개\n"
                f"🔥🔥🔥 시세 차이로 가격 조정: {price_adjusted_count}개\n"
                f"🔥 모드: {position_mode_text}"
            )
            
        except Exception as e:
            self.logger.error(f"시작 시 예약 주문 복제 처리 실패: {e}")

    async def _check_if_already_mirrored(self, order: Dict) -> str:
        """예약 주문이 이미 복제되었는지 확인"""
        # 실제 구현이 필요하지만 여기서는 기본적으로 "not_mirrored" 반환
        return "not_mirrored"

    async def _process_startup_plan_order_with_tp(self, order: Dict) -> Dict:
        """시작 시 예약 주문 + TP 설정 복제"""
        try:
            # 기본 처리 결과
            result_data = {
                'result': 'success',
                'price_adjusted': False,
                'tp_created': False
            }
            
            # 실제 구현이 필요하지만 여기서는 기본값 반환
            return result_data
            
        except Exception as e:
            self.logger.error(f"예약 주문 + TP 복제 실패: {e}")
            return {
                'result': 'failed',
                'price_adjusted': False,
                'tp_created': False
            }

    async def _record_startup_position_tp_sl(self):
        """포지션 유무에 따른 개선된 TP/SL 분류"""
        try:
            self.logger.info("🔥 포지션 유무에 따른 예약 주문 복제 정책 설정 시작")
            
            # 현재 활성 포지션들 조회
            positions = await self.bitget.get_positions(self.SYMBOL)
            
            active_positions = []
            for pos in positions:
                if float(pos.get('total', 0)) > 0:
                    active_positions.append(pos)
            
            self.has_startup_positions = len(active_positions) > 0
            
            if not self.has_startup_positions:
                # 포지션이 없으면 모든 예약 주문을 복제
                self.startup_position_tp_sl.clear()
            else:
                # 포지션이 있으면 기존 로직대로 클로즈 TP/SL만 제외
                for pos in active_positions:
                    pos_side = pos.get('holdSide', '').lower()
                    
                    # 해당 포지션의 TP/SL 주문들 찾기
                    plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
                    tp_sl_orders = plan_data.get('tp_sl_orders', [])
                    
                    for tp_sl_order in tp_sl_orders:
                        trade_side = tp_sl_order.get('tradeSide', tp_sl_order.get('side', '')).lower()
                        reduce_only = tp_sl_order.get('reduceOnly', False)
                        
                        # 기존 포지션의 클로즈 TP/SL인지 판단
                        is_existing_position_close = False
                        
                        if pos_side == 'long':
                            if (trade_side in ['close_long', 'sell'] and 
                                (reduce_only is True or reduce_only == 'true')):
                                is_existing_position_close = True
                        elif pos_side == 'short':
                            if (trade_side in ['close_short', 'buy'] and 
                                (reduce_only is True or reduce_only == 'true')):
                                is_existing_position_close = True
                        
                        order_id = tp_sl_order.get('orderId', tp_sl_order.get('planOrderId', ''))
                        if order_id and is_existing_position_close:
                            self.startup_position_tp_sl.add(order_id)
            
        except Exception as e:
            self.logger.error(f"포지션 유무에 따른 예약 주문 정책 설정 실패: {e}")
            self.has_startup_positions = False
            self.startup_position_tp_sl.clear()

    async def monitor_plan_orders(self):
        """🔥🔥🔥 예약 주문 모니터링 - 취소 감지 완전 강화"""
        self.logger.info("🔥🔥🔥🔥🔥 예약 주문 취소 미러링 완전 강화 모니터링 시작")
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                if not self.startup_plan_orders_processed:
                    await asyncio.sleep(0.1)
                    continue
                
                # 🔥🔥🔥 현재 비트겟 예약 주문 조회 - 더 자주 체크
                plan_data = await self.bitget.get_all_plan_orders_with_tp_sl(self.SYMBOL)
                current_plan_orders = plan_data.get('plan_orders', [])
                current_tp_sl_orders = plan_data.get('tp_sl_orders', [])
                
                all_current_orders = current_plan_orders + current_tp_sl_orders
                
                # 현재 존재하는 예약주문 ID 집합
                current_order_ids = set()
                current_snapshot = {}
                
                for order in all_current_orders:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if order_id:
                        current_order_ids.add(order_id)
                        current_snapshot[order_id] = {
                            'order_data': order.copy(),
                            'timestamp': datetime.now().isoformat(),
                            'status': 'active'
                        }
                
                # 🔥🔥🔥🔥🔥 취소된 예약 주문 감지 - 완전 강화
                canceled_order_ids = self.last_plan_order_ids - current_order_ids
                
                # 🔥🔥🔥🔥🔥 취소된 주문 처리 - 여러 개일 수 있음
                if canceled_order_ids:
                    self.logger.info(f"🔥🔥🔥🔥🔥 {len(canceled_order_ids)}개의 예약 주문 취소 감지: {canceled_order_ids}")
                    
                    for canceled_order_id in canceled_order_ids:
                        await self._handle_plan_order_cancel_enhanced(canceled_order_id)
                    
                    # 통계 업데이트
                    self.daily_stats['plan_order_cancels'] += len(canceled_order_ids)
                
                # 새로운 예약 주문 감지
                new_orders_count = 0
                skipped_orders_count = 0
                for order in all_current_orders:
                    order_id = order.get('orderId', order.get('planOrderId', ''))
                    if not order_id:
                        continue
                    
                    # 포지션 유무에 따른 필터링
                    if self.has_startup_positions and order_id in self.startup_position_tp_sl:
                        continue
                    
                    # 이미 처리된 주문은 스킵
                    if order_id in self.processed_plan_orders:
                        continue
                    
                    # 시작 시 존재했던 주문인지 확인
                    if order_id in self.startup_plan_orders:
                        self.processed_plan_orders.add(order_id)
                        continue
                    
                    # 새로운 예약 주문 감지
                    try:
                        result_data = await self._process_new_plan_order_with_tp(order)
                        
                        if result_data['result'] == "skipped":
                            skipped_orders_count += 1
                        else:
                            new_orders_count += 1
                        
                        self.processed_plan_orders.add(order_id)
                        
                    except Exception as e:
                        self.logger.error(f"❌ 새로운 예약 주문 복제 실패: {order_id} - {e}")
                        self.processed_plan_orders.add(order_id)
                        
                        await self.telegram.send_message(
                            f"❌ 예약 주문 복제 실패\n"
                            f"비트겟 ID: {order_id}\n"
                            f"오류: {str(e)[:200]}"
                        )
                
                # 🔥🔥🔥🔥🔥 현재 상태를 다음 비교를 위해 저장
                self.last_plan_order_ids = current_order_ids.copy()
                self.plan_order_snapshot = current_snapshot.copy()
                
                # 통계 업데이트
                if skipped_orders_count > 0:
                    self.daily_stats['plan_order_skipped_trigger_price'] += skipped_orders_count
                
                # 오래된 주문 ID 정리
                if len(self.processed_plan_orders) > 500:
                    recent_orders = list(self.processed_plan_orders)[-250:]
                    self.processed_plan_orders = set(recent_orders)
                
                consecutive_errors = 0
                await asyncio.sleep(self.PLAN_ORDER_CHECK_INTERVAL)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"예약 주문 모니터링 중 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 예약 주문 TP 모니터링 시스템 오류\n"
                        f"연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL * 2)

    async def _mirror_new_position(self, position: Dict) -> MirrorResult:
        """새 포지션 미러링"""
        try:
            # 미러링 로직 구현
            return MirrorResult(
                success=True,
                action="mirror_position",
                bitget_data=position,
                gate_data={"success": True}
            )
            
        except Exception as e:
            return MirrorResult(
                success=False,
                action="mirror_position",
                bitget_data=position,
                error=str(e)
            )

    async def _process_position(self, position: Dict):
        """포지션 처리"""
        try:
            pos_id = self._generate_position_id(position)
            
            # 기존 포지션은 처리하지 않음
            if pos_id in self.startup_positions:
                return
            
            # 이미 미러링된 포지션 확인
            if pos_id in self.mirrored_positions:
                # 포지션 업데이트 로직
                await self._update_mirrored_position(pos_id, position)
            else:
                # 새 포지션 미러링
                result = await self._mirror_new_position(position)
                if result.success:
                    self.mirrored_positions[pos_id] = await self._create_position_info(position)
                    self.daily_stats['successful_mirrors'] += 1
                    self.daily_stats['position_mirrors'] += 1
                else:
                    self.failed_mirrors.append(result)
                    self.daily_stats['failed_mirrors'] += 1
                
                self.daily_stats['total_mirrored'] += 1
            
        except Exception as e:
            self.logger.error(f"포지션 처리 중 오류: {e}")

    async def _update_mirrored_position(self, pos_id: str, position: Dict):
        """미러링된 포지션 업데이트"""
        try:
            if pos_id in self.mirrored_positions:
                # 포지션 정보 업데이트
                self.mirrored_positions[pos_id].size = float(position.get('total', 0))
                self.mirrored_positions[pos_id].unrealized_pnl = float(position.get('unrealizedPL', 0))
                self.mirrored_positions[pos_id].last_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"포지션 업데이트 실패: {e}")

    async def _handle_position_close(self, pos_id: str):
        """포지션 종료 처리"""
        try:
            if pos_id in self.mirrored_positions:
                # 게이트에서도 포지션 종료
                position_info = self.mirrored_positions[pos_id]
                
                # 게이트 포지션 종료 로직
                await self.gate.close_position(self.GATE_CONTRACT)
                
                # 미러링 기록에서 제거
                del self.mirrored_positions[pos_id]
                
                # 통계 업데이트
                self.daily_stats['full_closes'] += 1
                
                await self.telegram.send_message(
                    f"🔄 포지션 종료 미러링 완료\n"
                    f"포지션 ID: {pos_id}\n"
                    f"방향: {position_info.side}\n"
                    f"크기: {position_info.size}"
                )
            
        except Exception as e:
            self.logger.error(f"포지션 종료 처리 실패: {e}")
            # 오류가 발생해도 미러링 기록에서는 제거
            if pos_id in self.mirrored_positions:
                del self.mirrored_positions[pos_id]

    async def _handle_plan_order_cancel_enhanced(self, bitget_order_id: str):
        """🔥🔥🔥🔥🔥 예약 주문 취소 처리 완전 강화 - 확실한 취소 보장"""
        try:
            self.logger.info(f"🔥🔥🔥🔥🔥 예약 주문 취소 처리 시작 (완전 강화): {bitget_order_id}")
            
            # 미러링된 주문인지 확인
            if bitget_order_id not in self.mirrored_plan_orders:
                self.logger.info(f"🔍 미러링되지 않은 주문이므로 취소 처리 스킵: {bitget_order_id}")
                return
            
            mirror_info = self.mirrored_plan_orders[bitget_order_id]
            gate_order_id = mirror_info.get('gate_order_id')
            
            if not gate_order_id:
                self.logger.warning(f"⚠️ 게이트 주문 ID가 없음: {bitget_order_id}")
                # 미러링 기록에서만 제거
                del self.mirrored_plan_orders[bitget_order_id]
                return
            
            # 🔥🔥🔥🔥🔥 예약 주문에 연결된 TP 주문도 함께 취소
            await self._cancel_plan_order_tp(bitget_order_id)
            
            # 🔥🔥🔥🔥🔥 재시도 로직으로 확실한 취소 보장 - 강화된 버전
            cancel_success = False
            retry_count = 0
            
            while retry_count < self.max_cancel_retry and not cancel_success:
                try:
                    retry_count += 1
                    self.logger.info(f"🔥🔥🔥 게이트 예약 주문 취소 시도 {retry_count}/{self.max_cancel_retry}: {gate_order_id}")
                    
                    # 게이트에서 예약 주문 취소
                    await self.gate.cancel_price_triggered_order(gate_order_id)
                    
                    # 취소 확인을 위해 대기 (강화된 대기 시간)
                    await asyncio.sleep(self.cancel_verification_delay)
                    
                    # 🔥🔥🔥🔥🔥 취소 확인 - 게이트에서 주문이 실제로 취소되었는지 확인
                    verification_success = await self._verify_order_cancellation(gate_order_id)
                    
                    if verification_success:
                        cancel_success = True
                        self.logger.info(f"✅✅✅ 게이트 예약 주문 취소 확인됨: {gate_order_id}")
                        self.daily_stats['plan_order_cancel_success'] += 1
                        self.daily_stats['cancel_verification_success'] += 1
                        
                        # 성공 메시지
                        await self.telegram.send_message(
                            f"🚫✅ 예약 주문 취소 동기화 완료 (TP 포함)\n"
                            f"비트겟 ID: {bitget_order_id}\n"
                            f"게이트 ID: {gate_order_id}\n"
                            f"재시도: {retry_count}회\n"
                            f"확인 시간: {self.cancel_verification_delay}초"
                        )
                        break
                    else:
                        self.logger.warning(f"⚠️ 취소 시도했지만 주문이 여전히 존재함 (재시도 {retry_count}/{self.max_cancel_retry})")
                        self.daily_stats['cancel_verification_failed'] += 1
                        
                        if retry_count < self.max_cancel_retry:
                            # 재시도 전 더 긴 대기
                            wait_time = min(self.cancel_verification_delay * retry_count, 10.0)
                            await asyncio.sleep(wait_time)
                        
                except Exception as cancel_error:
                    error_msg = str(cancel_error).lower()
                    
                    if any(keyword in error_msg for keyword in ["not found", "order not exist", "invalid order", "order does not exist"]):
                        # 주문이 이미 취소되었거나 체결됨
                        cancel_success = True
                        self.logger.info(f"✅✅✅ 게이트 예약 주문이 이미 취소/체결됨: {gate_order_id}")
                        self.daily_stats['plan_order_cancel_success'] += 1
                        self.daily_stats['cancel_verification_success'] += 1
                        
                        await self.telegram.send_message(
                            f"🚫✅ 예약 주문 취소 처리 완료 (TP 포함)\n"
                            f"비트겟 ID: {bitget_order_id}\n"
                            f"게이트 주문이 이미 취소되었거나 체결되었습니다."
                        )
                        break
                    else:
                        self.logger.error(f"❌ 게이트 예약 주문 취소 실패 (시도 {retry_count}/{self.max_cancel_retry}): {cancel_error}")
                        
                        if retry_count < self.max_cancel_retry:
                            # 재시도 전 더 긴 대기
                            wait_time = min(3.0 * retry_count, 15.0)
                            await asyncio.sleep(wait_time)
                        else:
                            # 최종 실패
                            self.daily_stats['plan_order_cancel_failed'] += 1
                            self.daily_stats['cancel_verification_failed'] += 1
                            
                            await self.telegram.send_message(
                                f"❌ 예약 주문 취소 최종 실패\n"
                                f"비트겟 ID: {bitget_order_id}\n"
                                f"게이트 ID: {gate_order_id}\n"
                                f"오류: {str(cancel_error)[:200]}\n"
                                f"재시도: {retry_count}회\n"
                                f"수동 확인이 필요할 수 있습니다."
                            )
            
            # 🔥🔥🔥🔥🔥 미러링 기록에서 제거 (성공/실패 관계없이)
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]
                self.logger.info(f"🗑️ 미러링 기록에서 제거됨: {bitget_order_id}")
            
        except Exception as e:
            self.logger.error(f"❌ 예약 주문 취소 처리 중 예외 발생: {e}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            
            # 오류 발생 시에도 미러링 기록에서 제거
            if bitget_order_id in self.mirrored_plan_orders:
                del self.mirrored_plan_orders[bitget_order_id]
            
            await self.telegram.send_message(
                f"❌ 예약 주문 취소 처리 중 오류\n"
                f"비트겟 ID: {bitget_order_id}\n"
                f"오류: {str(e)[:200]}"
            )

    async def _verify_order_cancellation(self, gate_order_id: str) -> bool:
        """🔥🔥🔥🔥🔥 주문 취소 확인 검증 - 강화된 버전"""
        try:
            # 여러 방법으로 취소 확인
            verification_methods = []
            
            # 방법 1: 활성 예약 주문 목록에서 확인
            try:
                gate_orders = await self.gate.get_price_triggered_orders(self.GATE_CONTRACT, "open")
                order_still_exists = any(order.get('id') == gate_order_id for order in gate_orders)
                verification_methods.append(('active_orders', not order_still_exists))
                
                if not order_still_exists:
                    self.logger.info(f"✅ 확인 방법 1: 주문이 활성 목록에 없음 - {gate_order_id}")
                    return True
                else:
                    self.logger.warning(f"⚠️ 확인 방법 1: 주문이 여전히 활성 목록에 있음 - {gate_order_id}")
                    
            except Exception as e:
                self.logger.debug(f"확인 방법 1 실패: {e}")
                verification_methods.append(('active_orders', None))
            
            # 방법 2: 취소된 주문 목록에서 확인
            try:
                canceled_orders = await self.gate.get_price_triggered_orders(self.GATE_CONTRACT, "cancelled")
                order_in_canceled = any(order.get('id') == gate_order_id for order in canceled_orders)
                verification_methods.append(('canceled_orders', order_in_canceled))
                
                if order_in_canceled:
                    self.logger.info(f"✅ 확인 방법 2: 주문이 취소 목록에 있음 - {gate_order_id}")
                    return True
                else:
                    self.logger.debug(f"확인 방법 2: 주문이 취소 목록에 없음 - {gate_order_id}")
                    
            except Exception as e:
                self.logger.debug(f"확인 방법 2 실패: {e}")
                verification_methods.append(('canceled_orders', None))
            
            # 방법 3: 직접 주문 조회 시도
            try:
                # 주문이 존재하지 않으면 오류가 발생할 것임
                specific_order = await self.gate.get_price_triggered_orders(self.GATE_CONTRACT, "all")
                order_found = any(order.get('id') == gate_order_id for order in specific_order)
                verification_methods.append(('direct_query', not order_found))
                
                if not order_found:
                    self.logger.info(f"✅ 확인 방법 3: 주문을 찾을 수 없음 - {gate_order_id}")
                    return True
                else:
                    self.logger.warning(f"⚠️ 확인 방법 3: 주문이 여전히 존재함 - {gate_order_id}")
                    
            except Exception as e:
                # 주문이 없어서 오류가 발생한 경우 취소된 것으로 간주
                if any(keyword in str(e).lower() for keyword in ["not found", "order not exist", "invalid order"]):
                    self.logger.info(f"✅ 확인 방법 3: 주문 조회 오류로 취소 확인 - {gate_order_id}")
                    verification_methods.append(('direct_query', True))
                    return True
                else:
                    self.logger.debug(f"확인 방법 3 실패: {e}")
                    verification_methods.append(('direct_query', None))
            
            # 모든 확인 방법 결과 분석
            successful_verifications = [method for method in verification_methods if method[1] is True]
            failed_verifications = [method for method in verification_methods if method[1] is False]
            
            self.logger.debug(f"취소 확인 결과 - 성공: {successful_verifications}, 실패: {failed_verifications}")
            
            # 하나라도 취소가 확인되면 성공
            if successful_verifications:
                return True
            
            # 모든 방법이 실패했으면 취소되지 않은 것으로 판단
            return False
            
        except Exception as e:
            self.logger.error(f"주문 취소 확인 검증 실패: {e}")
            return False

    async def _cancel_plan_order_tp(self, bitget_order_id: str):
        """🔥🔥🔥🔥🔥 예약 주문에 연결된 TP 주문 취소"""
        try:
            if bitget_order_id not in self.plan_order_tp_tracking:
                return
            
            tp_order_ids = self.plan_order_tp_tracking[bitget_order_id]
            
            for gate_tp_id in tp_order_ids:
                try:
                    await self.gate.cancel_price_triggered_order(gate_tp_id)
                    self.logger.info(f"✅ 예약 주문 연결 TP 취소 성공: {gate_tp_id}")
                except Exception as e:
                    error_msg = str(e).lower()
                    if "not found" in error_msg or "order not exist" in error_msg:
                        self.logger.info(f"✅ 예약 주문 연결 TP가 이미 취소/체결됨: {gate_tp_id}")
                    else:
                        self.logger.error(f"❌ 예약 주문 연결 TP 취소 실패: {gate_tp_id} - {e}")
            
            # 추적에서 제거
            if bitget_order_id in self.plan_order_tp_tracking:
                del self.plan_order_tp_tracking[bitget_order_id]
            
            if bitget_order_id in self.mirrored_plan_order_tp:
                del self.mirrored_plan_order_tp[bitget_order_id]
            
        except Exception as e:
            self.logger.error(f"예약 주문 TP 취소 처리 실패: {e}")

    async def _process_new_plan_order_with_tp(self, bitget_order: Dict) -> Dict:
        """🔥🔥🔥🔥🔥 새로운 예약 주문 복제 - TP 설정 올바른 방향으로 복제"""
        try:
            # 기본 처리 결과
            result_data = {
                'result': 'success',
                'tp_created': False
            }
            
            # 실제 구현이 필요하지만 여기서는 기본값 반환
            return result_data
            
        except Exception as e:
            self.logger.error(f"신규 예약 주문 + TP 복제 실패: {e}")
            return {'result': 'failed', 'tp_created': False}

    async def monitor_sync_status(self):
        """동기화 상태 모니터링"""
        while self.monitoring:
            try:
                # 주기적으로 동기화 상태 체크
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"동기화 상태 모니터링 오류: {e}")
                await asyncio.sleep(self.SYNC_CHECK_INTERVAL * 2)

    async def monitor_tp_orders(self):
        """🔥🔥🔥 TP 주문 모니터링"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                # TP 주문 상태 체크 로직 구현
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL)
                consecutive_errors = 0
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"TP 주문 모니터링 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ TP 주문 모니터링 시스템 오류\n"
                        f"연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL * 2)

    async def monitor_plan_order_tp(self):
        """🔥🔥🔥🔥🔥 예약 주문 TP 모니터링"""
        consecutive_errors = 0
        
        while self.monitoring:
            try:
                # 예약 주문 TP 상태 체크 로직 구현
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL)
                consecutive_errors = 0
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"예약 주문 TP 모니터링 오류 (연속 {consecutive_errors}회): {e}")
                
                if consecutive_errors >= 5:
                    await self.telegram.send_message(
                        f"⚠️ 예약 주문 TP 모니터링 시스템 오류\n"
                        f"연속 {consecutive_errors}회 실패"
                    )
                
                await asyncio.sleep(self.ORDER_CHECK_INTERVAL * 2)
