# exception_detector.py - 예외 상황 감지
import logging
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pytz

logger = logging.getLogger(__name__)

class ExceptionDetector:
    def __init__(self, config, bitget_client):
        self.config = config
        self.bitget_client = bitget_client
        self.last_check_time = None
        self.last_price = None
        self.session = None
        
    async def initialize(self):
        """감지기 초기화"""
        self.session = aiohttp.ClientSession()
        logger.info("예외 감지기 초기화 완료")
    
    async def detect_exceptions(self) -> List[Dict]:
        """예외 상황 감지"""
        exceptions = []
        
        try:
            # 가격 급변동 감지
            price_exception = await self._detect_price_volatility()
            if price_exception:
                exceptions.append(price_exception)
            
            # 대량 거래 감지 (Whale Alert API 대신 거래량으로 대체)
            volume_exception = await self._detect_high_volume()
            if volume_exception:
                exceptions.append(volume_exception)
            
            # 펀딩비 급변 감지
            funding_exception = await self._detect_funding_anomaly()
            if funding_exception:
                exceptions.append(funding_exception)
            
            # 뉴스/이벤트 감지 (간단한 키워드 기반)
            news_exception = await self._detect_news_events()
            if news_exception:
                exceptions.append(news_exception)
            
            self.last_check_time = datetime.now(pytz.timezone('Asia/Seoul'))
            
        except Exception as e:
            logger.error(f"예외 감지 중 오류: {e}")
        
        return exceptions
    
    async def _detect_price_volatility(self) -> Optional[Dict]:
        """가격 급변동 감지"""
        try:
            # 현재가 조회
            ticker = await self.bitget_client.get_ticker()
            current_price = float(ticker.get('lastPr', 0))
            
            if self.last_price is None:
                self.last_price = current_price
                return None
            
            # 변동률 계산
            price_change = (current_price - self.last_price) / self.last_price * 100
            
            # 임계값 초과 시 예외 발생
            if abs(price_change) >= self.config.price_change_threshold:
                direction = "상승" if price_change > 0 else "하락"
                
                self.last_price = current_price
                
                return {
                    'type': '가격 급변동',
                    'description': f'최근 5분간 {abs(price_change):.1f}% {direction}',
                    'impact': 'positive' if price_change > 0 else 'negative',
                    'severity': 'high' if abs(price_change) >= 5 else 'medium',
                    'price_change': price_change,
                    'current_price': current_price
                }
            
            self.last_price = current_price
            return None
            
        except Exception as e:
            logger.error(f"가격 변동 감지 실패: {e}")
            return None
    
    async def _detect_high_volume(self) -> Optional[Dict]:
        """높은 거래량 감지"""
        try:
            # 최근 1시간 거래량 조회
            klines = await self.bitget_client.get_kline(granularity='1H', limit=24)
            
            if len(klines) < 2:
                return None
            
            # 최근 거래량
            recent_volume = float(klines[0][5])  # 최신 캔들의 거래량
            
            # 평균 거래량 계산 (최근 24시간)
            avg_volume = sum(float(k[5]) for k in klines) / len(klines)
            
            # 거래량이 평균의 3배 이상일 때
            if recent_volume > avg_volume * 3:
                return {
                    'type': '거래량 급증',
                    'description': f'시간당 거래량이 평균의 {recent_volume/avg_volume:.1f}배 증가',
                    'impact': 'positive
