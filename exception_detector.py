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
                    'impact': 'positive',
                    'severity': 'medium',
                    'volume_ratio': recent_volume/avg_volume
                }
            
            return None
            
        except Exception as e:
            logger.error(f"거래량 감지 실패: {e}")
            return None
    
    async def _detect_funding_anomaly(self) -> Optional[Dict]:
        """펀딩비 이상 감지"""
        try:
            funding = await self.bitget_client.get_funding_rate()
            current_funding = float(funding.get('fundingRate', 0))
            
            # 펀딩비가 0.02% (연 73%) 이상일 때
            if abs(current_funding) >= 0.0002:
                direction = "롱 과열" if current_funding > 0 else "숏 과열"
                
                return {
                    'type': '펀딩비 이상',
                    'description': f'{direction} - 펀딩비 {current_funding*100:.3f}%',
                    'impact': 'negative',
                    'severity': 'high' if abs(current_funding) >= 0.0005 else 'medium',
                    'funding_rate': current_funding
                }
            
            return None
            
        except Exception as e:
            logger.error(f"펀딩비 감지 실패: {e}")
            return None
    
    async def _detect_news_events(self) -> Optional[Dict]:
        """뉴스/이벤트 감지 (간단한 구현)"""
        try:
            # 실제로는 뉴스 API나 소셜 미디어 API를 사용해야 함
            # 여기서는 시간 기반으로 가상의 이벤트 생성
            now = datetime.now(pytz.timezone('Asia/Seoul'))
            
            # FOMC 등 주요 이벤트 시간대 체크
            fomc_times = [
                (21, 0),  # 21:00 FOMC 발표
                (2, 0),   # 02:00 FOMC 발표 (서머타임)
            ]
            
            current_time = (now.hour, now.minute)
            
            for event_time in fomc_times:
                # 이벤트 시간 1시간 전부터 감지
                event_hour, event_minute = event_time
                time_diff = abs((now.hour * 60 + now.minute) - (event_hour * 60 + event_minute))
                
                if time_diff <= 60:  # 1시간 이내
                    return {
                        'type': '주요 경제 이벤트',
                        'description': f'FOMC 발표 {time_diff}분 전',
                        'impact': 'neutral',
                        'severity': 'high',
                        'event_type': 'FOMC'
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"뉴스 이벤트 감지 실패: {e}")
            return None
    
    async def _detect_open_interest_anomaly(self) -> Optional[Dict]:
        """미결제약정 이상 감지"""
        try:
            oi_data = await self.bitget_client.get_open_interest()
            current_oi = float(oi_data.get('openInterest', 0))
            
            # 이전 데이터와 비교 (실제로는 DB에 저장해야 함)
            # 여기서는 간단히 구현
            
            return None
            
        except Exception as e:
            logger.error(f"미결제약정 감지 실패: {e}")
            return None
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("예외 감지기 세션 종료")
            
