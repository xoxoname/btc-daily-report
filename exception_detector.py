import logging
from typing import Dict, Any, Optional
import traceback

class ExceptionDetector:
    def __init__(self, bitget_client, telegram_bot):
        self.bitget_client = bitget_client
        self.telegram_bot = telegram_bot
        self.logger = logging.getLogger('exception_detector')
        
    async def check_funding_rate_anomaly(self) -> Optional[Dict[str, Any]]:
        """펀딩비 이상 징후 감지"""
        try:
            # Bitget API 호출
            funding_data = await self.bitget_client.get_funding_rate('BTCUSDT')
            
            # 응답 데이터 타입 확인 및 처리
            if isinstance(funding_data, list):
                if not funding_data:
                    self.logger.warning("펀딩비 데이터가 비어있습니다.")
                    return None
                # 리스트인 경우 첫 번째 요소 사용
                funding_rate_data = funding_data[0]
            elif isinstance(funding_data, dict):
                funding_rate_data = funding_data
            else:
                self.logger.error(f"예상하지 못한 펀딩비 데이터 타입: {type(funding_data)}")
                return None
            
            # 펀딩비 추출 (다양한 필드명 시도)
            funding_rate = None
            possible_fields = ['fundingRate', 'funding_rate', 'rate', 'fundRate']
            
            for field in possible_fields:
                if field in funding_rate_data:
                    funding_rate = float(funding_rate_data[field])
                    break
            
            if funding_rate is None:
                self.logger.warning(f"펀딩비 필드를 찾을 수 없습니다. 데이터: {funding_rate_data}")
                return None
            
            # 펀딩비 임계값 확인 (연 기준 ±50% 이상)
            annual_rate = funding_rate * 3 * 365  # 8시간마다 3번, 365일
            
            if abs(annual_rate) > 0.5:  # 50% 이상
                return {
                    'type': 'funding_rate_anomaly',
                    'funding_rate': funding_rate,
                    'annual_rate': annual_rate,
                    'severity': 'high' if abs(annual_rate) > 1.0 else 'medium'
                }
                
        except Exception as e:
            self.logger.error(f"펀딩비 감지 실패: {str(e)}")
            self.logger.debug(f"펀딩비 감지 오류 상세: {traceback.format_exc()}")
            
        return None
    
    async def check_price_anomaly(self) -> Optional[Dict[str, Any]]:
        """가격 이상 징후 감지"""
        try:
            # 현재 가격 조회
            ticker_data = await self.bitget_client.get_ticker('BTCUSDT')
            
            if isinstance(ticker_data, list):
                if not ticker_data:
                    return None
                ticker_data = ticker_data[0]
            
            # 가격 추출
            current_price = None
            price_fields = ['last', 'lastPr', 'price', 'close']
            
            for field in price_fields:
                if field in ticker_data:
                    current_price = float(ticker_data[field])
                    break
            
            if current_price is None:
                self.logger.warning(f"가격 필드를 찾을 수 없습니다. 데이터: {ticker_data}")
                return None
            
            # 24시간 변동률 확인
            change_24h = None
            change_fields = ['changeUtc', 'change24h', 'priceChangePercent']
            
            for field in change_fields:
                if field in ticker_data:
                    change_24h = float(ticker_data[field])
                    break
            
            if change_24h and abs(change_24h) > 0.15:  # 15% 이상 변동
                return {
                    'type': 'price_anomaly',
                    'current_price': current_price,
                    'change_24h': change_24h,
                    'severity': 'high' if abs(change_24h) > 0.25 else 'medium'
                }
                
        except Exception as e:
            self.logger.error(f"가격 이상 감지 실패: {str(e)}")
            
        return None
    
    async def check_volume_anomaly(self) -> Optional[Dict[str, Any]]:
        """거래량 이상 징후 감지"""
        try:
            # 24시간 거래량 데이터 조회
            ticker_data = await self.bitget_client.get_ticker('BTCUSDT')
            
            if isinstance(ticker_data, list):
                if not ticker_data:
                    return None
                ticker_data = ticker_data[0]
            
            # 거래량 추출
            volume_24h = None
            volume_fields = ['baseVolume', 'volume', 'vol24h', 'baseVol']
            
            for field in volume_fields:
                if field in ticker_data:
                    volume_24h = float(ticker_data[field])
                    break
            
            if volume_24h is None:
                return None
            
            # 평균 거래량과 비교 (임시로 고정값 사용, 실제로는 과거 데이터와 비교)
            avg_volume = 50000  # BTC 기준 평균 거래량 (예시)
            
            if volume_24h > avg_volume * 3:  # 평균의 3배 이상
                return {
                    'type': 'volume_anomaly',
                    'volume_24h': volume_24h,
                    'avg_volume': avg_volume,
                    'ratio': volume_24h / avg_volume,
                    'severity': 'high' if volume_24h > avg_volume * 5 else 'medium'
                }
                
        except Exception as e:
            self.logger.error(f"거래량 이상 감지 실패: {str(e)}")
            
        return None
    
    async def detect_all_anomalies(self) -> list:
        """모든 이상 징후 감지"""
        anomalies = []
        
        # 각 감지 함수 실행
        detectors = [
            self.check_funding_rate_anomaly,
            self.check_price_anomaly,
            self.check_volume_anomaly
        ]
        
        for detector in detectors:
            try:
                result = await detector()
                if result:
                    anomalies.append(result)
            except Exception as e:
                self.logger.error(f"이상 징후 감지 중 오류: {str(e)}")
        
        return anomalies
    
    async def send_alert(self, anomaly: Dict[str, Any]):
        """이상 징후 알림 전송"""
        try:
            message = self._format_alert_message(anomaly)
            await self.telegram_bot.send_message(message)
        except Exception as e:
            self.logger.error(f"알림 전송 실패: {str(e)}")
    
    def _format_alert_message(self, anomaly: Dict[str, Any]) -> str:
        """알림 메시지 포맷팅"""
        severity_emoji = "🚨" if anomaly['severity'] == 'high' else "⚠️"
        
        if anomaly['type'] == 'funding_rate_anomaly':
            return f"""
{severity_emoji} **펀딩비 이상 감지**

현재 펀딩비: {anomaly['funding_rate']:.6f}
연환산 수익률: {anomaly['annual_rate']:.2%}
심각도: {anomaly['severity']}

⚡ 높은 펀딩비는 포지션 청산 위험을 의미할 수 있습니다.
"""
        
        elif anomaly['type'] == 'price_anomaly':
            return f"""
{severity_emoji} **가격 급변동 감지**

현재 가격: ${anomaly['current_price']:,.2f}
24시간 변동: {anomaly['change_24h']:.2%}
심각도: {anomaly['severity']}

📈 급격한 가격 변동이 감지되었습니다.
"""
        
        elif anomaly['type'] == 'volume_anomaly':
            return f"""
{severity_emoji} **거래량 급증 감지**

24시간 거래량: {anomaly['volume_24h']:,.2f} BTC
평균 대비: {anomaly['ratio']:.1f}배
심각도: {anomaly['severity']}

💹 비정상적인 거래량 증가가 감지되었습니다.
"""
        
        return f"{severity_emoji} 이상 징후가 감지되었습니다: {anomaly['type']}"
