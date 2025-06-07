import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import json

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
    metadata: Optional[Dict] = None

class RealTimeDataCollector:
    def __init__(self, config, bitget_client=None):
        self.config = config
        self.bitget_client = bitget_client
        self.session = None
        self.events_buffer = []
        self.news_buffer = []
        self.last_price = None
        self.price_history = []
        
        # 추가 API 키들
        self.coingecko_key = getattr(config, 'COINGECKO_API_KEY', None)
        self.cryptocompare_key = getattr(config, 'CRYPTOCOMPARE_API_KEY', None)
        self.glassnode_key = getattr(config, 'GLASSNODE_API_KEY', None)
        
        # 캐시 (API 제한 관리)
        self.cache = {
            'fear_greed': {'data': None, 'timestamp': None},
            'market_cap': {'data': None, 'timestamp': None},
            'social_metrics': {'data': None, 'timestamp': None}
        }
        
        # RealisticNewsCollector 임포트 및 강화
        try:
            from realistic_news_collector import RealisticNewsCollector
            self.news_collector = RealisticNewsCollector(config)
            self.news_collector.data_collector = self
            logger.info("✅ RealisticNewsCollector 초기화 완료 (Claude 번역 지원)")
        except ImportError as e:
            logger.error(f"RealisticNewsCollector 임포트 실패: {e}")
            self.news_collector = None
        
        # 뉴스 처리 통계
        self.news_stats = {
            'total_processed': 0,
            'critical_alerts': 0,
            'translations_done': 0,
            'claude_translations': 0,
            'gpt_translations': 0,
            'last_reset': datetime.now()
        }
        
    async def start(self):
        """데이터 수집 시작 - 뉴스 우선도 높임"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        logger.info("🚀 실시간 데이터 수집 시작 (Claude 번역 강화)")
        
        # 병렬 태스크 실행
        tasks = []
        
        # 뉴스 수집 시작 (최우선)
        if self.news_collector:
            tasks.append(asyncio.create_task(self.news_collector.start()))
            logger.info("📰 뉴스 수집기 시작 (Claude 번역 지원)")
        
        # 가격 모니터링
        tasks.append(asyncio.create_task(self.price_monitoring()))
        
        # 시장 데이터 수집
        tasks.append(asyncio.create_task(self.market_data_collection()))
        
        # Fear & Greed Index
        tasks.append(asyncio.create_task(self.fear_greed_monitoring()))
        
        # 소셜 메트릭 수집
        if self.cryptocompare_key:
            tasks.append(asyncio.create_task(self.social_metrics_collection()))
        
        # 모든 태스크 실행
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"데이터 수집 중 오류: {e}")
    
    async def price_monitoring(self):
        """가격 모니터링 - 1% 민감도"""
        while True:
            try:
                if not self.bitget_client:
                    await asyncio.sleep(5)
                    continue
                
                # 현재 가격 조회
                ticker_data = await self.bitget_client.get_ticker('BTCUSDT')
                
                if ticker_data:
                    current_price = float(ticker_data.get('last', 0))
                    
                    if current_price > 0:
                        # 가격 변화 감지 (1% 임계값)
                        if self.last_price and abs(current_price - self.last_price) / self.last_price >= 0.01:
                            change_percent = ((current_price - self.last_price) / self.last_price) * 100
                            
                            severity = EventSeverity.MEDIUM if abs(change_percent) >= 2 else EventSeverity.LOW
                            
                            event = MarketEvent(
                                timestamp=datetime.now(),
                                severity=severity,
                                category='price_movement',
                                title=f'비트코인 가격 {change_percent:+.2f}% 변동',
                                description=f'${self.last_price:,.0f} → ${current_price:,.0f}',
                                impact=f'{change_percent:+.2f}%',
                                source='Bitget'
                            )
                            
                            self.events_buffer.append(event)
                            logger.info(f"💰 가격 변동 감지: {change_percent:+.2f}%")
                        
                        self.last_price = current_price
                        self.price_history.append({
                            'timestamp': datetime.now(),
                            'price': current_price
                        })
                        
                        # 가격 히스토리 정리 (최근 1000개만 유지)
                        if len(self.price_history) > 1000:
                            self.price_history = self.price_history[-1000:]
                
                await asyncio.sleep(10)  # 10초마다 확인
                
            except Exception as e:
                logger.error(f"가격 모니터링 오류: {e}")
                await asyncio.sleep(30)
    
    async def market_data_collection(self):
        """시장 데이터 수집"""
        while True:
            try:
                # CoinGecko 시장 데이터
                if self.coingecko_key:
                    await self.collect_coingecko_data()
                
                # 글로벌 시장 데이터
                await self.collect_global_market_data()
                
                await asyncio.sleep(300)  # 5분마다
                
            except Exception as e:
                logger.error(f"시장 데이터 수집 오류: {e}")
                await asyncio.sleep(600)
    
    async def collect_coingecko_data(self):
        """CoinGecko 데이터 수집"""
        try:
            # 시장 캡 데이터
            if self._should_update_cache('market_cap', 300):  # 5분 캐시
                url = "https://api.coingecko.com/api/v3/global"
                headers = {"x-cg-demo-api-key": self.coingecko_key} if self.coingecko_key else {}
                
                async with self.session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if 'data' in data:
                            global_data = data['data']
                            
                            # BTC 도미넌스 변화 감지
                            btc_dominance = global_data.get('market_cap_percentage', {}).get('btc', 0)
                            
                            if btc_dominance:
                                event = MarketEvent(
                                    timestamp=datetime.now(),
                                    severity=EventSeverity.LOW,
                                    category='market_data',
                                    title=f'BTC 도미넌스: {btc_dominance:.1f}%',
                                    description=f'전체 암호화폐 시가총액 대비 비트코인 비중',
                                    impact=f'{btc_dominance:.1f}%',
                                    source='CoinGecko'
                                )
                                self.events_buffer.append(event)
                            
                            self.cache['market_cap'] = {
                                'data': global_data,
                                'timestamp': datetime.now()
                            }
                            
                            logger.debug(f"✅ CoinGecko 시장 데이터 수집: BTC 도미넌스 {btc_dominance:.1f}%")
        
        except Exception as e:
            logger.error(f"CoinGecko 데이터 수집 오류: {e}")
    
    async def collect_global_market_data(self):
        """글로벌 시장 데이터 수집"""
        try:
            # 알터너티브 공포탐욕지수 (무료)
            url = "https://api.alternative.me/fng/"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if 'data' in data and data['data']:
                        fng_data = data['data'][0]
                        fng_value = int(fng_data.get('value', 0))
                        fng_classification = fng_data.get('value_classification', 'Unknown')
                        
                        severity = EventSeverity.MEDIUM if fng_value <= 25 or fng_value >= 75 else EventSeverity.LOW
                        
                        event = MarketEvent(
                            timestamp=datetime.now(),
                            severity=severity,
                            category='sentiment',
                            title=f'공포탐욕지수: {fng_value}/100 ({fng_classification})',
                            description=f'시장 심리 지표',
                            impact=fng_classification,
                            source='Alternative.me'
                        )
                        self.events_buffer.append(event)
                        
                        logger.debug(f"📊 공포탐욕지수: {fng_value}/100 ({fng_classification})")
        
        except Exception as e:
            logger.error(f"글로벌 시장 데이터 수집 오류: {e}")
    
    async def fear_greed_monitoring(self):
        """공포탐욕지수 모니터링"""
        while True:
            try:
                if self._should_update_cache('fear_greed', 1800):  # 30분 캐시
                    url = "https://api.alternative.me/fng/"
                    
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if 'data' in data and data['data']:
                                current_fng = data['data'][0]
                                
                                self.cache['fear_greed'] = {
                                    'data': current_fng,
                                    'timestamp': datetime.now()
                                }
                                
                                fng_value = int(current_fng.get('value', 0))
                                
                                # 극단적 수치일 때 이벤트 생성
                                if fng_value <= 20:
                                    severity = EventSeverity.HIGH
                                    title = f"극도의 공포: {fng_value}/100"
                                    impact = "매수 기회 가능성"
                                elif fng_value >= 80:
                                    severity = EventSeverity.HIGH
                                    title = f"극도의 탐욕: {fng_value}/100"
                                    impact = "조정 위험 증가"
                                else:
                                    continue
                                
                                event = MarketEvent(
                                    timestamp=datetime.now(),
                                    severity=severity,
                                    category='critical_sentiment',
                                    title=title,
                                    description=f"시장 심리가 극단적 수준에 도달",
                                    impact=impact,
                                    source='Alternative.me'
                                )
                                self.events_buffer.append(event)
                                
                                logger.warning(f"⚠️ 극단적 시장 심리 감지: {title}")
                
                await asyncio.sleep(1800)  # 30분마다
                
            except Exception as e:
                logger.error(f"공포탐욕지수 모니터링 오류: {e}")
                await asyncio.sleep(1800)
    
    async def social_metrics_collection(self):
        """소셜 메트릭 수집"""
        while True:
            try:
                if self._should_update_cache('social_metrics', 3600):  # 1시간 캐시
                    # CryptoCompare 소셜 데이터
                    url = f"https://min-api.cryptocompare.com/data/social/coin/histo/hour"
                    params = {
                        'coinId': '1182',  # Bitcoin ID
                        'limit': 1,
                        'api_key': self.cryptocompare_key
                    }
                    
                    async with self.session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if 'Data' in data and data['Data']:
                                social_data = data['Data'][0]
                                
                                # 소셜 점수 변화 감지
                                reddit_comments = social_data.get('comments', 0)
                                twitter_followers = social_data.get('followers', 0)
                                
                                if reddit_comments > 1000 or twitter_followers > 100000:
                                    event = MarketEvent(
                                        timestamp=datetime.now(),
                                        severity=EventSeverity.LOW,
                                        category='social_activity',
                                        title=f'높은 소셜 활동 감지',
                                        description=f'Reddit 댓글: {reddit_comments:,}, Twitter 팔로워: {twitter_followers:,}',
                                        impact='관심도 증가',
                                        source='CryptoCompare'
                                    )
                                    self.events_buffer.append(event)
                                
                                self.cache['social_metrics'] = {
                                    'data': social_data,
                                    'timestamp': datetime.now()
                                }
                                
                                logger.debug(f"📱 소셜 메트릭 수집: Reddit {reddit_comments}, Twitter {twitter_followers}")
                
                await asyncio.sleep(3600)  # 1시간마다
                
            except Exception as e:
                logger.error(f"소셜 메트릭 수집 오류: {e}")
                await asyncio.sleep(3600)
    
    def _should_update_cache(self, cache_key: str, max_age_seconds: int) -> bool:
        """캐시 업데이트 필요 여부 확인"""
        if cache_key not in self.cache:
            return True
        
        cache_data = self.cache[cache_key]
        if not cache_data['timestamp']:
            return True
        
        age = (datetime.now() - cache_data['timestamp']).total_seconds()
        return age > max_age_seconds
    
    def get_recent_events(self, hours: int = 1, severity: Optional[EventSeverity] = None) -> List[MarketEvent]:
        """최근 이벤트 조회"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        events = [event for event in self.events_buffer if event.timestamp > cutoff_time]
        
        if severity:
            events = [event for event in events if event.severity == severity]
        
        return sorted(events, key=lambda x: x.timestamp, reverse=True)
    
    def get_current_market_summary(self) -> Dict:
        """현재 시장 요약"""
        summary = {
            'current_price': self.last_price,
            'events_count': len(self.events_buffer),
            'recent_events': len(self.get_recent_events(1)),
            'fear_greed_index': None,
            'btc_dominance': None,
            'last_update': datetime.now().isoformat()
        }
        
        # 캐시된 데이터 추가
        if 'fear_greed' in self.cache and self.cache['fear_greed']['data']:
            fng_data = self.cache['fear_greed']['data']
            summary['fear_greed_index'] = {
                'value': fng_data.get('value'),
                'classification': fng_data.get('value_classification')
            }
        
        if 'market_cap' in self.cache and self.cache['market_cap']['data']:
            market_data = self.cache['market_cap']['data']
            btc_dominance = market_data.get('market_cap_percentage', {}).get('btc')
            if btc_dominance:
                summary['btc_dominance'] = btc_dominance
        
        return summary
    
    async def get_recent_news(self, hours: int = 12) -> List[Dict]:
        """최근 뉴스 조회 - RealisticNewsCollector 우선 사용"""
        try:
            if self.news_collector:
                return await self.news_collector.get_recent_news(hours)
            else:
                # 폴백: 이벤트 버퍼에서 뉴스 이벤트 조회
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
                    'weight': 5
                })
        
        return news_events[:8]
    
    def set_bitget_client(self, bitget_client):
        """Bitget 클라이언트 설정"""
        self.bitget_client = bitget_client
        logger.info("✅ Bitget 클라이언트 설정 완료")
    
    def update_news_stats(self, event_type: str, translation_type: str = None):
        """뉴스 처리 통계 업데이트"""
        self.news_stats['total_processed'] += 1
        
        if event_type == 'critical':
            self.news_stats['critical_alerts'] += 1
        
        if translation_type == 'claude':
            self.news_stats['claude_translations'] += 1
        elif translation_type == 'gpt':
            self.news_stats['gpt_translations'] += 1
    
    async def close(self):
        """세션 종료"""
        try:
            if self.session:
                await self.session.close()
            
            if self.news_collector:
                await self.news_collector.close()
            
            # 최종 통계 출력
            total = self.news_stats['total_processed']
            if total > 0:
                logger.info("📊 최종 뉴스 처리 통계:")
                logger.info(f"  총 처리: {total}건")
                logger.info(f"  크리티컬: {self.news_stats['critical_alerts']}건")
                logger.info(f"  Claude 번역: {self.news_stats['claude_translations']}건")
                logger.info(f"  GPT 번역: {self.news_stats['gpt_translations']}건")
            
            logger.info("🔚 데이터 수집기 종료 완료")
            
        except Exception as e:
            logger.error(f"데이터 수집기 종료 중 오류: {e}")
