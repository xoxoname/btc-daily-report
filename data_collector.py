import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class EventSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class MarketEvent:
    timestamp: datetime
    severity: EventSeverity
    category: str
    title: str
    description: str
    impact: str
    source: str
    url: Optional[str] = None

class RealTimeDataCollector:
    def __init__(self, config):
        self.config = config
        self.session = None
        self.events_buffer = []
        self.last_price = None
        self.price_history = []
        
    async def start(self):
        """데이터 수집 시작"""
        self.session = aiohttp.ClientSession()
        
        # 병렬로 여러 데이터 소스 모니터링
        await asyncio.gather(
            self.monitor_news(),
            self.monitor_price_changes(),
            self.monitor_sentiment()
        )
    
    async def monitor_news(self):
        """뉴스 모니터링 (NewsAPI)"""
        while True:
            try:
                # NewsAPI 키가 없으면 스킵
                if not hasattr(self.config, 'NEWSAPI_KEY') or not self.config.NEWSAPI_KEY:
                    logger.warning("NewsAPI 키가 없어 뉴스 모니터링 비활성화")
                    await asyncio.sleep(3600)  # 1시간 대기
                    continue
                
                # NewsAPI 호출
                url = "https://newsapi.org/v2/everything"
                params = {
                    'q': 'bitcoin OR btc OR crypto OR trump OR "bitcoin etf" OR fomc',
                    'language': 'en',
                    'sortBy': 'publishedAt',
                    'apiKey': self.config.NEWSAPI_KEY,
                    'pageSize': 20,
                    'from': (datetime.now() - timedelta(hours=1)).isoformat()
                }
                
                async with self.session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"NewsAPI 오류: {response.status}")
                        await asyncio.sleep(600)
                        continue
                        
                    data = await response.json()
                    
                    for article in data.get('articles', []):
                        event = await self.analyze_news(article)
                        if event and event.severity in [EventSeverity.HIGH, EventSeverity.CRITICAL]:
                            self.events_buffer.append(event)
                
            except Exception as e:
                logger.error(f"뉴스 모니터링 오류: {e}")
            
            await asyncio.sleep(300)  # 5분마다 체크
    
    async def monitor_price_changes(self):
        """가격 급변동 모니터링 (Bitget 데이터 활용)"""
        while True:
            try:
                # Bitget 클라이언트에서 가격 가져오기
                if hasattr(self, 'bitget_client'):
                    ticker_data = await self.bitget_client.get_ticker('BTCUSDT')
                    
                    if isinstance(ticker_data, dict):
                        current_price = float(ticker_data.get('last', 0))
                        
                        if self.last_price:
                            change_percent = ((current_price - self.last_price) / self.last_price) * 100
                            
                            # 15분 내 2% 이상 변동 시 알림
                            if abs(change_percent) >= 2:
                                event = MarketEvent(
                                    timestamp=datetime.now(),
                                    severity=EventSeverity.HIGH if abs(change_percent) >= 3 else EventSeverity.MEDIUM,
                                    category="price_movement",
                                    title=f"BTC {'급등' if change_percent > 0 else '급락'} {abs(change_percent):.1f}%",
                                    description=f"15분 내 ${self.last_price:,.0f} → ${current_price:,.0f}",
                                    impact="➕호재" if change_percent > 0 else "➖악재",
                                    source="Bitget"
                                )
                                self.events_buffer.append(event)
                        
                        self.last_price = current_price
                        self.price_history.append({
                            'price': current_price,
                            'timestamp': datetime.now()
                        })
                        
                        # 1시간 이상 된 데이터 제거
                        self.price_history = [
                            p for p in self.price_history 
                            if p['timestamp'] > datetime.now() - timedelta(hours=1)
                        ]
                
            except Exception as e:
                logger.error(f"가격 모니터링 오류: {e}")
            
            await asyncio.sleep(60)  # 1분마다 체크
    
    async def monitor_sentiment(self):
        """시장 심리 지표 모니터링"""
        while True:
            try:
                # Fear & Greed Index (무료 API)
                url = "https://api.alternative.me/fng/"
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        fng_value = int(data['data'][0]['value'])
                        fng_class = data['data'][0]['value_classification']
                        
                        # 극단적 심리 상태
                        if fng_value <= 20 or fng_value >= 80:
                            event = MarketEvent(
                                timestamp=datetime.now(),
                                severity=EventSeverity.MEDIUM,
                                category="sentiment",
                                title=f"극단적 시장 심리: {fng_class} ({fng_value})",
                                description="시장 심리 전환점 가능성",
                                impact="➕호재" if fng_value <= 20 else "➖악재",
                                source="Fear & Greed Index"
                            )
                            self.events_buffer.append(event)
                
            except Exception as e:
                logger.error(f"심리 지표 모니터링 오류: {e}")
            
            await asyncio.sleep(600)  # 10분마다 체크
    
    async def analyze_news(self, article) -> Optional[MarketEvent]:
        """뉴스 분석 및 중요도 판단"""
        # 중요 키워드
        keywords = {
            'critical': ['ban', 'hack', 'collapse', 'crash', 'sec lawsuit', 'regulatory crackdown'],
            'high': ['etf approval', 'etf rejection', 'trump', 'biden', 'fed', 'interest rate', 'fomc'],
            'medium': ['adoption', 'partnership', 'upgrade', 'institutional']
        }
        
        title = (article.get('title') or '').lower()
        description = (article.get('description') or '').lower()
        content = title + " " + description
        
        severity = EventSeverity.LOW
        for level, words in keywords.items():
            if any(word in content for word in words):
                severity = EventSeverity[level.upper()]
                break
        
        if severity in [EventSeverity.HIGH, EventSeverity.CRITICAL]:
            # 영향도 판단
            impact = "➖악재"
            positive_words = ['approval', 'adoption', 'partnership', 'bullish', 'surge', 'rally']
            if any(word in content for word in positive_words):
                impact = "➕호재"
            
            return MarketEvent(
                timestamp=datetime.now(),
                severity=severity,
                category="news",
                title=article['title'][:100],
                description=(article.get('description') or '')[:200],
                impact=impact,
                source=article.get('source', {}).get('name', 'Unknown'),
                url=article.get('url')
            )
        
        return None
    
    def set_bitget_client(self, bitget_client):
        """Bitget 클라이언트 설정"""
        self.bitget_client = bitget_client
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
