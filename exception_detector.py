import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from config import Config
from bitget_client import BitgetClient
from telegram_bot import send_telegram_message
from technical_analysis import TechnicalAnalyzer
from data_fetcher import DataFetcher
from openai_analyzer import OpenAIAnalyzer

logger = logging.getLogger(__name__)

class ExceptionReporter:
    """긴급 이벤트 자동 감지 및 예외 리포트 생성"""
    
    def __init__(self, config: Config, bitget_client: BitgetClient, 
                 analyzer: TechnicalAnalyzer, data_fetcher: DataFetcher,
                 openai_analyzer: OpenAIAnalyzer):
        self.config = config
        self.bitget = bitget_client
        self.analyzer = analyzer
        self.data_fetcher = data_fetcher
        self.openai = openai_analyzer
        
        # 탐지 기준값
        self.WHALE_THRESHOLD = 1000  # BTC
        self.VOLATILITY_THRESHOLD = 2.0  # %
        self.VOLUME_SPIKE_THRESHOLD = 3.0  # 배수
        self.PRICE_CHANGE_THRESHOLD = 3.0  # %
        self.FUNDING_RATE_THRESHOLD = 0.05  # %
        
        # 마지막 알림 시간 추적
        self.last_alerts = {}
        self.alert_cooldown = 300  # 5분
        
    async def monitor_exceptions(self):
        """예외 상황 모니터링 (무한 루프)"""
        logger.info("예외 상황 모니터링 시작")
        
        while True:
            try:
                # 여러 예외 상황 동시 체크
                tasks = [
                    self.check_whale_movements(),
                    self.check_price_volatility(),
                    self.check_volume_anomaly(),
                    self.check_funding_rate_anomaly(),
                    self.check_liquidations(),
                    self.check_news_events()
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 탐지된 예외 상황 처리
                exceptions_detected = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"예외 체크 중 오류: {result}")
                    elif result:
                        exceptions_detected.append(result)
                
                # 중요 예외 상황 발생 시 리포트 생성
                if exceptions_detected:
                    await self.generate_exception_report(exceptions_detected)
                
                # 30초마다 체크
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"예외 모니터링 오류: {e}")
                await asyncio.sleep(60)
    
    async def check_whale_movements(self) -> Optional[Dict]:
        """고래 이동 감지"""
        try:
            # Whale Alert API 또는 온체인 데이터 체크
            whale_data = await self.data_fetcher.get_whale_movements()
            
            if not whale_data:
                return None
                
            for movement in whale_data:
                amount = movement.get('amount', 0)
                from_type = movement.get('from_type', '')
                to_type = movement.get('to_type', '')
                
                # 거래소로의 대량 이동 감지
                if amount >= self.WHALE_THRESHOLD and to_type == 'exchange':
                    if not self._is_alert_on_cooldown('whale', movement['hash']):
                        return {
                            'type': 'whale_movement',
                            'severity': 'high',
                            'amount': amount,
                            'direction': 'to_exchange',
                            'message': f"🐋 {amount:,.0f} BTC 대량 거래소 입금 감지",
                            'impact': 'bearish',
                            'timestamp': datetime.now()
                        }
                        
                # 거래소에서의 대량 출금 감지
                elif amount >= self.WHALE_THRESHOLD and from_type == 'exchange':
                    if not self._is_alert_on_cooldown('whale', movement['hash']):
                        return {
                            'type': 'whale_movement',
                            'severity': 'medium',
                            'amount': amount,
                            'direction': 'from_exchange',
                            'message': f"🐋 {amount:,.0f} BTC 대량 거래소 출금 감지",
                            'impact': 'bullish',
                            'timestamp': datetime.now()
                        }
                        
        except Exception as e:
            logger.error(f"고래 이동 체크 오류: {e}")
            
        return None
    
    async def check_price_volatility(self) -> Optional[Dict]:
        """급격한 가격 변동 감지"""
        try:
            current_data = await self.bitget.get_current_price()
            current_price = current_data['current_price']
            
            # 5분, 15분 가격 변화율 체크
            klines_5m = await self.bitget.get_klines('5m', 3)
            klines_15m = await self.bitget.get_klines('15m', 2)
            
            if klines_5m and len(klines_5m) >= 3:
                price_5m_ago = float(klines_5m[-3][1])  # 5분 전 시가
                change_5m = ((current_price - price_5m_ago) / price_5m_ago) * 100
                
                if abs(change_5m) >= self.VOLATILITY_THRESHOLD:
                    if not self._is_alert_on_cooldown('volatility_5m', str(current_price)):
                        direction = "급등" if change_5m > 0 else "급락"
                        return {
                            'type': 'price_volatility',
                            'severity': 'high',
                            'timeframe': '5분',
                            'change_percent': change_5m,
                            'current_price': current_price,
                            'message': f"⚡ BTC 5분간 {abs(change_5m):.1f}% {direction}",
                            'impact': 'high_volatility',
                            'timestamp': datetime.now()
                        }
            
            if klines_15m and len(klines_15m) >= 2:
                price_15m_ago = float(klines_15m[-2][1])
                change_15m = ((current_price - price_15m_ago) / price_15m_ago) * 100
                
                if abs(change_15m) >= self.PRICE_CHANGE_THRESHOLD:
                    if not self._is_alert_on_cooldown('volatility_15m', str(current_price)):
                        direction = "상승" if change_15m > 0 else "하락"
                        return {
                            'type': 'price_volatility',
                            'severity': 'medium',
                            'timeframe': '15분',
                            'change_percent': change_15m,
                            'current_price': current_price,
                            'message': f"📊 BTC 15분간 {abs(change_15m):.1f}% {direction}",
                            'impact': 'volatility',
                            'timestamp': datetime.now()
                        }
                        
        except Exception as e:
            logger.error(f"가격 변동성 체크 오류: {e}")
            
        return None
    
    async def check_volume_anomaly(self) -> Optional[Dict]:
        """거래량 이상 감지"""
        try:
            # 현재 거래량과 평균 거래량 비교
            current_volume = await self.bitget.get_24h_volume()
            avg_volume_data = await self.bitget.get_average_volume(7)  # 7일 평균
            
            if current_volume and avg_volume_data:
                avg_volume = avg_volume_data['average']
                volume_ratio = current_volume / avg_volume
                
                if volume_ratio >= self.VOLUME_SPIKE_THRESHOLD:
                    if not self._is_alert_on_cooldown('volume', str(current_volume)):
                        return {
                            'type': 'volume_anomaly',
                            'severity': 'medium',
                            'current_volume': current_volume,
                            'average_volume': avg_volume,
                            'ratio': volume_ratio,
                            'message': f"📈 거래량 급증: 평균 대비 {volume_ratio:.1f}배",
                            'impact': 'high_activity',
                            'timestamp': datetime.now()
                        }
                        
        except Exception as e:
            logger.error(f"거래량 이상 체크 오류: {e}")
            
        return None
    
    async def check_funding_rate_anomaly(self) -> Optional[Dict]:
        """펀딩비 이상 감지"""
        try:
            funding_data = await self.bitget.get_funding_rate()
            
            if funding_data:
                current_rate = funding_data['funding_rate']
                
                if abs(current_rate) >= self.FUNDING_RATE_THRESHOLD:
                    if not self._is_alert_on_cooldown('funding', str(current_rate)):
                        position = "롱" if current_rate > 0 else "숏"
                        return {
                            'type': 'funding_anomaly',
                            'severity': 'medium',
                            'funding_rate': current_rate,
                            'message': f"💰 펀딩비 이상: {current_rate:.3f}% ({position} 과열)",
                            'impact': 'position_imbalance',
                            'timestamp': datetime.now()
                        }
                        
        except Exception as e:
            logger.error(f"펀딩비 체크 오류: {e}")
            
        return None
    
    async def check_liquidations(self) -> Optional[Dict]:
        """대규모 청산 감지"""
        try:
            liquidation_data = await self.data_fetcher.get_liquidations()
            
            if liquidation_data:
                total_liquidations = liquidation_data.get('total_24h', 0)
                recent_liquidations = liquidation_data.get('last_hour', 0)
                
                # 1시간 내 1000만 달러 이상 청산
                if recent_liquidations >= 10_000_000:
                    if not self._is_alert_on_cooldown('liquidation', str(recent_liquidations)):
                        return {
                            'type': 'mass_liquidation',
                            'severity': 'high',
                            'amount': recent_liquidations,
                            'message': f"🔥 대규모 청산 발생: ${recent_liquidations/1_000_000:.1f}M",
                            'impact': 'high_volatility',
                            'timestamp': datetime.now()
                        }
                        
        except Exception as e:
            logger.error(f"청산 데이터 체크 오류: {e}")
            
        return None
    
    async def check_news_events(self) -> Optional[Dict]:
        """중요 뉴스/이벤트 감지"""
        try:
            # 최근 뉴스 체크
            news_data = await self.data_fetcher.get_crypto_news()
            
            if news_data:
                for news in news_data[:5]:  # 최근 5개만
                    sentiment = news.get('sentiment', 'neutral')
                    importance = news.get('importance', 'low')
                    
                    if importance == 'high' and sentiment in ['very_negative', 'very_positive']:
                        news_id = news.get('id', news.get('title', ''))
                        if not self._is_alert_on_cooldown('news', news_id):
                            impact = 'bearish' if 'negative' in sentiment else 'bullish'
                            return {
                                'type': 'news_event',
                                'severity': 'high',
                                'title': news.get('title'),
                                'sentiment': sentiment,
                                'message': f"📰 중요 뉴스: {news.get('title', '뉴스 제목 없음')}",
                                'impact': impact,
                                'timestamp': datetime.now()
                            }
                            
        except Exception as e:
            logger.error(f"뉴스 체크 오류: {e}")
            
        return None
    
    async def generate_exception_report(self, exceptions: List[Dict]):
        """예외 리포트 생성 및 전송"""
        try:
            # 중요도 순으로 정렬
            severity_order = {'high': 0, 'medium': 1, 'low': 2}
            exceptions.sort(key=lambda x: severity_order.get(x.get('severity', 'low'), 3))
            
            # 현재 시장 상황 파악
            market_data = await self._get_market_snapshot()
            
            # GPT 분석 요청
            analysis = await self.openai.analyze_exceptions(exceptions, market_data)
            
            # 리포트 생성
            report = self._format_exception_report(exceptions, market_data, analysis)
            
            # 텔레그램 전송
            await send_telegram_message(self.config, report)
            
            # 알림 기록 업데이트
            for exc in exceptions:
                alert_type = exc.get('type')
                alert_key = str(exc.get('amount', exc.get('current_price', '')))
                self._record_alert(alert_type, alert_key)
                
        except Exception as e:
            logger.error(f"예외 리포트 생성 오류: {e}")
    
    def _format_exception_report(self, exceptions: List[Dict], 
                                market_data: Dict, analysis: Dict) -> str:
        """예외 리포트 포맷팅"""
        kst_time = datetime.now() + timedelta(hours=9)
        
        report = f"""🚨 예외 리포트 – 긴급 이벤트 자동 감지
📅 발생 시각: {kst_time.strftime('%m-%d %H:%M')} (KST)
━━━━━━━━━━━━━━━━━━━
❗ 원인 요약
"""
        
        # 예외 상황 나열
        for exc in exceptions[:3]:  # 최대 3개만
            report += f"{exc['message']}\n"
        
        report += f"""
━━━━━━━━━━━━━━━━━━━
📌 GPT 판단
{analysis.get('summary', '분석 중...')}

━━━━━━━━━━━━━━━━━━━
🛡️ 전략 제안
{analysis.get('strategy', '전략 수립 중...')}

━━━━━━━━━━━━━━━━━━━
📊 현재 시장 상황
• 현재가: ${market_data['current_price']:,.0f}
• 24H 변동: {market_data['change_24h']:+.2f}%
• RSI(1H): {market_data['rsi_1h']:.1f}
• 펀딩비: {market_data['funding_rate']:+.3f}%

━━━━━━━━━━━━━━━━━━━
🧠 GPT 멘탈 케어
{analysis.get('mental_care', '침착하게 대응하세요.')}"""
        
        return report
    
    async def _get_market_snapshot(self) -> Dict:
        """현재 시장 상황 스냅샷"""
        try:
            price_data = await self.bitget.get_current_price()
            indicators = await self.analyzer.get_key_indicators('1h')
            funding_data = await self.bitget.get_funding_rate()
            
            return {
                'current_price': price_data['current_price'],
                'change_24h': price_data['change_24h_percent'],
                'rsi_1h': indicators.get('rsi', 50),
                'funding_rate': funding_data.get('funding_rate', 0),
                'volume_24h': price_data.get('volume_24h', 0)
            }
        except Exception as e:
            logger.error(f"시장 스냅샷 오류: {e}")
            return {}
    
    def _is_alert_on_cooldown(self, alert_type: str, alert_key: str) -> bool:
        """알림 쿨다운 체크"""
        key = f"{alert_type}:{alert_key}"
        last_alert = self.last_alerts.get(key)
        
        if last_alert:
            if datetime.now() - last_alert < timedelta(seconds=self.alert_cooldown):
                return True
                
        return False
    
    def _record_alert(self, alert_type: str, alert_key: str):
        """알림 기록"""
        key = f"{alert_type}:{alert_key}"
        self.last_alerts[key] = datetime.now()
        
        # 오래된 알림 정리
        cutoff = datetime.now() - timedelta(hours=1)
        self.last_alerts = {
            k: v for k, v in self.last_alerts.items() 
            if v > cutoff
        }
