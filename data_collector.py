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
        self.news_buffer = []
        self.last_price = None
        self.price_history = []
        self.bitget_client = None
        
        # RealisticNewsCollector 임포트 및 초기화
        try:
            from realistic_news_collector import RealisticNewsCollector
            self.news_collector = RealisticNewsCollector(config)
            self.news_collector.data_collector = self  # 참조 설정
            logger.info("✅ RealisticNewsCollector 초기화 완료")
        except ImportError as e:
            logger.error(f"RealisticNewsCollector 임포트 실패: {e}")
            self.news_collector = None
        except Exception as e:
            logger.error(f"RealisticNewsCollector 초기화 실패: {e}")
            self.news_collector = None
        
    async def start(self):
        """데이터 수집 시작"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        logger.info("🚀 실시간 데이터 수집 시작")
        
        # 병렬 태스크 실행
        tasks = []
        
        # Bitget 클라이언트가 설정된 경우에만 가격 모니터링 시작
        if self.bitget_client:
            tasks.append(self.monitor_price_changes())
            logger.info("📈 가격 모니터링 활성화")
        
        # 기본 모니터링
        tasks.append(self.monitor_sentiment())
        
        # 뉴스 모니터링 (새로운 시스템 또는 폴백)
        if self.news_collector:
            tasks.append(self.news_collector.start_monitoring())
            logger.info("📰 고급 뉴스 모니터링 활성화 (RSS 중심 + 3개 API)")
        else:
            tasks.append(self.monitor_news_fallback())
            logger.warning("📰 기본 뉴스 모니터링 사용 (폴백)")
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def monitor_news_fallback(self):
        """기존 뉴스 모니터링 (폴백용)"""
        while True:
            try:
                # NewsAPI만 사용하는 기본 모니터링
                if not hasattr(self.config, 'NEWSAPI_KEY') or not self.config.NEWSAPI_KEY:
                    logger.warning("NewsAPI 키가 없어 뉴스 모니터링 제한됨")
                    await asyncio.sleep(3600)
                    continue
                
                url = "https://newsapi.org/v2/everything"
                params = {
                    'q': 'bitcoin OR btc OR crypto OR trump OR "bitcoin etf" OR fomc',
                    'language': 'en',
                    'sortBy': 'publishedAt',
                    'apiKey': self.config.NEWSAPI_KEY,
                    'pageSize': 15,
                    'from': (datetime.now() - timedelta(hours=2)).isoformat()
                }
                
                async with self.session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"NewsAPI 오류: {response.status}")
                        await asyncio.sleep(1800)
                        continue
                        
                    data = await response.json()
                    
                    for article in data.get('articles', []):
                        event = await self.analyze_news(article)
                        if event and event.severity in [EventSeverity.HIGH, EventSeverity.CRITICAL]:
                            self.events_buffer.append(event)
                            logger.info(f"📰 중요 뉴스 감지: {event.title[:50]}...")
                
            except Exception as e:
                logger.error(f"폴백 뉴스 모니터링 오류: {e}")
            
            await asyncio.sleep(1800)  # 30분마다 체크
    
    async def monitor_price_changes(self):
        """가격 급변동 모니터링"""
        while True:
            try:
                if not self.bitget_client:
                    await asyncio.sleep(60)
                    continue
                
                ticker_data = await self.bitget_client.get_ticker('BTCUSDT')
                
                if isinstance(ticker_data, dict):
                    current_price = float(ticker_data.get('last', 0))
                    
                    if self.last_price and current_price > 0:
                        change_percent = ((current_price - self.last_price) / self.last_price) * 100
                        
                        # 급변동 감지 임계값
                        if abs(change_percent) >= 2:
                            severity = EventSeverity.CRITICAL if abs(change_percent) >= 5 else EventSeverity.HIGH
                            
                            event = MarketEvent(
                                timestamp=datetime.now(),
                                severity=severity,
                                category="price_movement",
                                title=f"BTC {'급등' if change_percent > 0 else '급락'} {abs(change_percent):.1f}%",
                                description=f"1분 내 ${self.last_price:,.0f} → ${current_price:,.0f}",
                                impact="➕호재" if change_percent > 0 else "➖악재",
                                source="Bitget Real-time"
                            )
                            self.events_buffer.append(event)
                            
                            logger.warning(f"🚨 가격 급변동: {change_percent:+.1f}% (${self.last_price:,.0f} → ${current_price:,.0f})")
                    
                    if current_price > 0:
                        self.last_price = current_price
                        self.price_history.append({
                            'price': current_price,
                            'timestamp': datetime.now()
                        })
                        
                        # 오래된 데이터 정리 (1시간)
                        cutoff_time = datetime.now() - timedelta(hours=1)
                        self.price_history = [
                            p for p in self.price_history 
                            if p['timestamp'] > cutoff_time
                        ]
                
            except Exception as e:
                logger.error(f"가격 모니터링 오류: {e}")
            
            await asyncio.sleep(60)  # 1분마다 체크
    
    async def monitor_sentiment(self):
        """시장 심리 지표 모니터링"""
        while True:
            try:
                # Fear & Greed Index
                url = "https://api.alternative.me/fng/"
                
                if self.session:
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            fng_value = int(data['data'][0]['value'])
                            fng_class = data['data'][0]['value_classification']
                            
                            # 극단적 심리 상태만 이벤트로 처리
                            if fng_value <= 15 or fng_value >= 85:
                                event = MarketEvent(
                                    timestamp=datetime.now(),
                                    severity=EventSeverity.MEDIUM,
                                    category="sentiment",
                                    title=f"극단적 시장 심리: {fng_class} ({fng_value})",
                                    description=f"공포탐욕지수가 극단적 수준에 도달했습니다",
                                    impact="➕호재" if fng_value <= 15 else "➖악재",
                                    source="Fear & Greed Index"
                                )
                                self.events_buffer.append(event)
                                logger.info(f"😨 극단적 심리: {fng_class} ({fng_value})")
                
            except Exception as e:
                logger.error(f"심리 지표 모니터링 오류: {e}")
            
            await asyncio.sleep(1800)  # 30분마다 체크
    
    async def get_recent_news(self, hours: int = 6) -> List[Dict]:
        """최근 뉴스 가져오기"""
        try:
            if self.news_collector:
                # 새로운 뉴스 수집기 사용
                news = await self.news_collector.get_recent_news(hours)
                logger.info(f"📰 최근 {hours}시간 뉴스 {len(news)}건 조회 (고급 수집기)")
                return news
            else:
                # 폴백: 이벤트 버퍼에서 뉴스만 추출
                return self._get_fallback_news(hours)
        except Exception as e:
            logger.error(f"최근 뉴스 조회 오류: {e}")
            return []
    
    def _get_fallback_news(self, hours: int) -> List[Dict]:
        """폴백 뉴스 조회"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        news_events = []
        
        for event in self.events_buffer:
            if (hasattr(event, 'timestamp') and event.timestamp > cutoff_time and 
                hasattr(event, 'category') and event.category in ['news', 'critical_news']):
                news_events.append({
                    'title': event.title,
                    'description': event.description,
                    'source': event.source,
                    'published_at': event.timestamp.isoformat(),
                    'impact': event.impact,
                    'weight': 5  # 기본 가중치
                })
        
        logger.info(f"📰 폴백 뉴스 {len(news_events)}건 반환")
        return news_events[:8]
    
    async def analyze_news(self, article) -> Optional[MarketEvent]:
        """뉴스 분석 및 중요도 판단 (폴백용)"""
        keywords = {
            'critical': ['ban', 'hack', 'collapse', 'crash', 'sec lawsuit', 'regulatory crackdown', 'government ban'],
            'high': ['etf approval', 'etf rejection', 'trump', 'biden', 'fed', 'interest rate', 'fomc', 'powell'],
            'medium': ['adoption', 'partnership', 'upgrade', 'institutional', 'whale movement']
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
            positive_words = ['approval', 'adoption', 'partnership', 'bullish', 'surge', 'rally', 'pump']
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
        logger.info("✅ Bitget 클라이언트 설정 완료")
    
    async def close(self):
        """세션 종료"""
        try:
            if self.session:
                await self.session.close()
            
            if self.news_collector:
                await self.news_collector.close()
            
            logger.info("🔚 데이터 수집기 종료 완료")
            
        except Exception as e:
            logger.error(f"데이터 수집기 종료 중 오류: {e}")
