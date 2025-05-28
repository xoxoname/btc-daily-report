import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class ExceptionDetector:
    """예외 상황 감지 및 알림"""
    
    def __init__(self, bitget_client=None, telegram_bot=None):
        self.bitget_client = bitget_client
        self.telegram_bot = telegram_bot
        self.logger = logging.getLogger('exception_detector')
        
        # 임계값 설정
        self.PRICE_CHANGE_THRESHOLD = 1.0  # 1% 이상 변동
        self.VOLUME_SPIKE_THRESHOLD = 3.0  # 평균 대비 3배
        self.FUNDING_RATE_THRESHOLD = 0.01  # 1% 이상
        self.LIQUIDATION_THRESHOLD = 10_000_000  # 1천만 달러
        
        # 마지막 알림 시간 추적
        self.last_alerts = {}
        self.alert_cooldown = timedelta(minutes=5)
        
    async def detect_all_anomalies(self) -> List[Dict]:
        """모든 이상 징후 감지"""
        anomalies = []
        
        try:
            # 가격 변동 체크
            price_anomaly = await self.check_price_volatility()
            if price_anomaly:
                anomalies.append(price_anomaly)
            
            # 거래량 이상 체크
            volume_anomaly = await self.check_volume_anomaly()
            if volume_anomaly:
                anomalies.append(volume_anomaly)
            
            # 펀딩비 이상 체크
            funding_anomaly = await self.check_funding_rate()
            if funding_anomaly:
                anomalies.append(funding_anomaly)
            
        except Exception as e:
            self.logger.error(f"이상 징후 감지 중 오류: {e}")
        
        return anomalies
    
    async def check_price_volatility(self) -> Optional[Dict]:
        """가격 급변동 감지"""
        try:
            if not self.bitget_client:
                return None
            
            # 현재 가격 조회
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            if not ticker:
                return None
            
            current_price = float(ticker.get('last', 0))
            change_24h = float(ticker.get('changeUtc', 0))
            
            # 24시간 변동률이 임계값 초과
            if abs(change_24h) >= self.PRICE_CHANGE_THRESHOLD:
                key = f"price_{current_price}"
                if not self._is_on_cooldown('price_volatility', key):
                    self._update_alert_time('price_volatility', key)
                    
                    return {
                        'type': 'price_anomaly',
                        'severity': 'critical' if abs(change_24h) >= 3 else 'high',
                        'current_price': current_price,
                        'change_24h': change_24h,
                        'description': f"BTC {'급등' if change_24h > 0 else '급락'} {abs(change_24h):.1f}%",
                        'timestamp': datetime.now()
                    }
            
        except Exception as e:
            self.logger.error(f"가격 변동 체크 오류: {e}")
        
        return None
    
    async def check_volume_anomaly(self) -> Optional[Dict]:
        """거래량 이상 감지"""
        try:
            if not self.bitget_client:
                return None
            
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            if not ticker:
                return None
            
            volume_24h = float(ticker.get('baseVolume', 0))
            
            # 거래량이 특정 임계값 초과 (임시로 50000 BTC 기준)
            if volume_24h > 50000 * self.VOLUME_SPIKE_THRESHOLD:
                key = f"volume_{volume_24h}"
                if not self._is_on_cooldown('volume_anomaly', key):
                    self._update_alert_time('volume_anomaly', key)
                    
                    return {
                        'type': 'volume_anomaly',
                        'severity': 'high',
                        'volume_24h': volume_24h,
                        'ratio': volume_24h / 50000,
                        'description': f"거래량 급증: {volume_24h:,.0f} BTC",
                        'timestamp': datetime.now()
                    }
            
        except Exception as e:
            self.logger.error(f"거래량 체크 오류: {e}")
        
        return None
    
    async def check_funding_rate(self) -> Optional[Dict]:
        """펀딩비 이상 감지"""
        try:
            if not self.bitget_client:
                return None
            
            funding_data = await self.bitget_client.get_funding_rate('BTCUSDT')
            if not funding_data:
                return None
            
            # API가 리스트를 반환하는 경우 처리
            if isinstance(funding_data, list):
                if len(funding_data) > 0:
                    funding_data = funding_data[0]
                else:
                    return None
            
            funding_rate = float(funding_data.get('fundingRate', 0))
            
            # 펀딩비가 임계값 초과
            if abs(funding_rate) >= self.FUNDING_RATE_THRESHOLD:
                key = f"funding_{funding_rate}"
                if not self._is_on_cooldown('funding_rate', key):
                    self._update_alert_time('funding_rate', key)
                    
                    return {
                        'type': 'funding_rate_anomaly',
                        'severity': 'high' if abs(funding_rate) >= 0.05 else 'medium',
                        'funding_rate': funding_rate,
                        'annual_rate': funding_rate * 365 * 3,
                        'description': f"펀딩비 이상: {funding_rate:.4f}%",
                        'timestamp': datetime.now()
                    }
            
        except Exception as e:
            self.logger.error(f"펀딩비 체크 오류: {e}")
        
        return None
    
    async def send_alert(self, anomaly: Dict):
        """이상 징후 알림 전송"""
        try:
            if not self.telegram_bot:
                return
            
            # 알림 메시지 생성
            severity_emoji = {
                'critical': '🚨',
                'high': '⚠️',
                'medium': '📊'
            }
            
            emoji = severity_emoji.get(anomaly.get('severity', 'medium'), '📊')
            
            message = f"{emoji} 예외 상황 감지\n\n"
            message += f"유형: {anomaly.get('type', 'unknown')}\n"
            message += f"설명: {anomaly.get('description', '설명 없음')}\n"
            message += f"심각도: {anomaly.get('severity', 'medium')}\n"
            message += f"시간: {anomaly.get('timestamp', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}"
            
            await self.telegram_bot.send_message(message)
            
        except Exception as e:
            self.logger.error(f"알림 전송 실패: {e}")
    
    def _is_on_cooldown(self, alert_type: str, key: str) -> bool:
        """알림 쿨다운 체크"""
        last_alert_key = f"{alert_type}_{key}"
        last_time = self.last_alerts.get(last_alert_key)
        
        if last_time:
            if datetime.now() - last_time < self.alert_cooldown:
                return True
        
        return False
    
    def _update_alert_time(self, alert_type: str, key: str):
        """알림 시간 업데이트"""
        last_alert_key = f"{alert_type}_{key}"
        self.last_alerts[last_alert_key] = datetime.now()
        
        # 오래된 알림 기록 정리
        cutoff_time = datetime.now() - timedelta(hours=1)
        self.last_alerts = {
            k: v for k, v in self.last_alerts.items()
            if v > cutoff_time
        }
