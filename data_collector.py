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
    def __init__(self, config):
        self.config = config
        self.session = None
        self.events_buffer = []
        self.news_buffer = []
        self.last_price = None
        self.price_history = []
        self.bitget_client = None
        
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
        
        # 뉴스 모니터링을 최우선으로 시작
        if self.news_collector:
            tasks.append(self.news_collector.start_monitoring())
            logger.info("📰 고급 뉴스 모니터링 활성화 (Claude 우선 번역)")
        
        # Bitget 클라이언트가 설정된 경우에만 가격 모니터링 시작
        if self.bitget_client:
            tasks.append(self.monitor_price_changes())
            logger.info("📈 가격 모니터링 활성화 (1% 민감도)")
        
        # 기본 모니터링
        tasks.append(self.monitor_sentiment())
        tasks.append(self.monitor_market_metrics())
        
        # 뉴스 품질 모니터링 추가
        tasks.append(self.monitor_news_quality())
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def monitor_news_quality(self):
        """뉴스 품질 및 번역 상태 모니터링"""
        while True:
            try:
                await asyncio.sleep(1800)  # 30분마다
                
                current_time = datetime.now()
                time_since_reset = current_time - self.news_stats['last_reset']
                hours = time_since_reset.total_seconds() / 3600
                
                if hours >= 1.0:  # 1시간마다 통계 리포트
                    total = self.news_stats['total_processed']
                    critical = self.news_stats['critical_alerts']
                    claude_trans = self.news_stats['claude_translations']
                    gpt_trans = self.news_stats['gpt_translations']
                    
                    if total > 0:
                        logger.info(f"📊 뉴스 처리 통계 (지난 {hours:.1f}시간):")
                        logger.info(f"  총 처리: {total}건")
                        logger.info(f"  크리티컬 알림: {critical}건 ({critical/total*100:.1f}%)")
                        logger.info(f"  Claude 번역: {claude_trans}건")
                        logger.info(f"  GPT 번역: {gpt_trans}건")
                        
                        # 번역 성공률 체크
                        total_translations = claude_trans + gpt_trans
                        if total_translations > 0:
                            claude_ratio = claude_trans / total_translations * 100
                            logger.info(f"  번역 품질: Claude {claude_ratio:.1f}% / GPT {100-claude_ratio:.1f}%")
                    
                    # 통계 리셋
                    self.news_stats = {
                        'total_processed': 0,
                        'critical_alerts': 0,
                        'translations_done': 0,
                        'claude_translations': 0,
                        'gpt_translations': 0,
                        'last_reset': current_time
                    }
                
            except Exception as e:
                logger.error(f"뉴스 품질 모니터링 오류: {e}")
    
    async def monitor_price_changes(self):
        """가격 급변동 모니터링 - 1% 민감도"""
        while True:
            try:
                if not self.bitget_client:
                    await asyncio.sleep(30)
                    continue
                
                ticker_data = await self.bitget_client.get_ticker('BTCUSDT')
                
                if isinstance(ticker_data, dict):
                    current_price = float(ticker_data.get('last', 0))
                    
                    if self.last_price and current_price > 0:
                        change_percent = ((current_price - self.last_price) / self.last_price) * 100
                        
                        # 1% 이상 급변동 감지
                        if abs(change_percent) >= 1.0:
                            severity = EventSeverity.CRITICAL if abs(change_percent) >= 3 else EventSeverity.HIGH
                            
                            event = MarketEvent(
                                timestamp=datetime.now(),
                                severity=severity,
                                category="price_movement",
                                title=f"BTC {'급등' if change_percent > 0 else '급락'} {abs(change_percent):.2f}%",
                                description=f"1분 내 ${self.last_price:,.0f} → ${current_price:,.0f}",
                                impact="➕호재" if change_percent > 0 else "➖악재",
                                source="Bitget Real-time",
                                metadata={
                                    'change_percent': change_percent,
                                    'from_price': self.last_price,
                                    'to_price': current_price
                                }
                            )
                            self.events_buffer.append(event)
                            
                            logger.warning(f"🚨 가격 급변동: {change_percent:+.2f}% (${self.last_price:,.0f} → ${current_price:,.0f})")
                    
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
            
            await asyncio.sleep(30)  # 30초마다 체크
    
    async def monitor_sentiment(self):
        """시장 심리 지표 모니터링 - 확장"""
        while True:
            try:
                # Fear & Greed Index
                fng_data = await self.get_fear_greed_index()
                if fng_data:
                    fng_value = fng_data.get('value', 50)
                    fng_class = fng_data.get('value_classification', 'Neutral')
                    
                    # 극단적 심리 상태 감지
                    if fng_value <= 20 or fng_value >= 80:
                        event = MarketEvent(
                            timestamp=datetime.now(),
                            severity=EventSeverity.HIGH,
                            category="sentiment",
                            title=f"극단적 시장 심리: {fng_class} ({fng_value})",
                            description=f"공포탐욕지수가 극단적 수준에 도달",
                            impact="➕호재" if fng_value <= 20 else "➖악재",
                            source="Fear & Greed Index",
                            metadata={'fng_value': fng_value, 'classification': fng_class}
                        )
                        self.events_buffer.append(event)
                        logger.info(f"😨 극단적 심리: {fng_class} ({fng_value})")
                
                # CryptoCompare Social Data (있는 경우)
                if self.cryptocompare_key:
                    social_data = await self.get_social_metrics()
                    if social_data:
                        # 소셜 미디어 급증 감지
                        social_volume = social_data.get('social_volume', 0)
                        if social_volume > 10000:  # 임계값
                            logger.info(f"📱 소셜 미디어 활동 급증: {social_volume}")
                
            except Exception as e:
                logger.error(f"심리 지표 모니터링 오류: {e}")
            
            await asyncio.sleep(1800)  # 30분마다 체크
    
    async def monitor_market_metrics(self):
        """시장 메트릭 모니터링"""
        while True:
            try:
                # CoinGecko 시장 데이터
                if self.coingecko_key or True:  # CoinGecko는 키 없이도 사용 가능
                    market_data = await self.get_market_overview()
                    if market_data:
                        btc_dominance = market_data.get('btc_dominance', 0)
                        total_market_cap = market_data.get('total_market_cap', 0)
                        
                        # 도미넌스 급변동 감지
                        if abs(btc_dominance - 50) > 10:  # 50%에서 크게 벗어남
                            logger.info(f"📊 BTC 도미넌스 이상: {btc_dominance:.1f}%")
                
                # Glassnode 온체인 데이터 (있는 경우)
                if self.glassnode_key:
                    onchain_data = await self.get_onchain_metrics()
                    if onchain_data:
                        # 온체인 이상 징후 감지
                        exchange_inflow = onchain_data.get('exchange_inflow', 0)
                        if exchange_inflow > 10000:  # BTC
                            event = MarketEvent(
                                timestamp=datetime.now(),
                                severity=EventSeverity.HIGH,
                                category="onchain",
                                title=f"대량 거래소 유입: {exchange_inflow:,.0f} BTC",
                                description="매도 압력 증가 가능성",
                                impact="➖악재",
                                source="Glassnode",
                                metadata={'inflow': exchange_inflow}
                            )
                            self.events_buffer.append(event)
                
            except Exception as e:
                logger.error(f"시장 메트릭 모니터링 오류: {e}")
            
            await asyncio.sleep(3600)  # 1시간마다 체크
    
    async def get_fear_greed_index(self) -> Optional[Dict]:
        """Fear & Greed Index 조회"""
        try:
            # 캐시 확인 (10분)
            if self.cache['fear_greed']['timestamp']:
                if datetime.now() - self.cache['fear_greed']['timestamp'] < timedelta(minutes=10):
                    return self.cache['fear_greed']['data']
            
            url = "https://api.alternative.me/fng/?limit=1"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and 'data' in data:
                        result = {
                            'value': int(data['data'][0]['value']),
                            'value_classification': data['data'][0]['value_classification'],
                            'timestamp': data['data'][0]['timestamp']
                        }
                        
                        # 캐시 저장
                        self.cache['fear_greed'] = {
                            'data': result,
                            'timestamp': datetime.now()
                        }
                        
                        return result
                        
        except Exception as e:
            logger.error(f"Fear & Greed Index 조회 실패: {e}")
        
        return None
    
    async def get_market_overview(self) -> Optional[Dict]:
        """CoinGecko 시장 개요"""
        try:
            # 캐시 확인 (5분)
            if self.cache['market_cap']['timestamp']:
                if datetime.now() - self.cache['market_cap']['timestamp'] < timedelta(minutes=5):
                    return self.cache['market_cap']['data']
            
            # Global 데이터
            url = "https://api.coingecko.com/api/v3/global"
            headers = {}
            if self.coingecko_key:
                headers['x-cg-pro-api-key'] = self.coingecko_key
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    global_data = data.get('data', {})
                    
                    result = {
                        'total_market_cap': global_data.get('total_market_cap', {}).get('usd', 0),
                        'total_volume': global_data.get('total_volume', {}).get('usd', 0),
                        'btc_dominance': global_data.get('market_cap_percentage', {}).get('btc', 0),
                        'eth_dominance': global_data.get('market_cap_percentage', {}).get('eth', 0),
                        'market_cap_change_24h': global_data.get('market_cap_change_percentage_24h_usd', 0)
                    }
                    
                    # 캐시 저장
                    self.cache['market_cap'] = {
                        'data': result,
                        'timestamp': datetime.now()
                    }
                    
                    return result
                    
        except Exception as e:
            logger.error(f"CoinGecko 시장 데이터 조회 실패: {e}")
        
        return None
    
    async def get_social_metrics(self) -> Optional[Dict]:
        """CryptoCompare 소셜 메트릭"""
        if not self.cryptocompare_key:
            return None
            
        try:
            url = "https://min-api.cryptocompare.com/data/social/coin/latest"
            params = {
                'coinId': 1182,  # Bitcoin ID
                'api_key': self.cryptocompare_key
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('Response') == 'Success':
                        social_data = data.get('Data', {})
                        
                        return {
                            'social_volume': social_data.get('General', {}).get('Points', 0),
                            'twitter_followers': social_data.get('Twitter', {}).get('followers', 0),
                            'reddit_subscribers': social_data.get('Reddit', {}).get('subscribers', 0)
                        }
                        
        except Exception as e:
            logger.error(f"CryptoCompare 소셜 데이터 조회 실패: {e}")
        
        return None
    
    async def get_onchain_metrics(self) -> Optional[Dict]:
        """Glassnode 온체인 메트릭"""
        if not self.glassnode_key:
            return None
            
        try:
            # Exchange Inflow
            url = "https://api.glassnode.com/v1/metrics/transactions/transfers_to_exchanges"
            params = {
                'a': 'BTC',
                'api_key': self.glassnode_key,
                'i': '24h',
                'f': 'JSON'
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        latest = data[-1] if isinstance(data, list) else data
                        
                        return {
                            'exchange_inflow': latest.get('v', 0),
                            'timestamp': latest.get('t', 0)
                        }
                        
        except Exception as e:
            logger.error(f"Glassnode 온체인 데이터 조회 실패: {e}")
        
        return None
    
    async def get_comprehensive_market_data(self) -> Dict:
        """종합 시장 데이터 수집"""
        tasks = [
            self.get_fear_greed_index(),
            self.get_market_overview(),
            self.get_social_metrics(),
            self.get_onchain_metrics()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        comprehensive_data = {
            'fear_greed': results[0] if not isinstance(results[0], Exception) else None,
            'market_overview': results[1] if not isinstance(results[1], Exception) else None,
            'social_metrics': results[2] if not isinstance(results[2], Exception) else None,
            'onchain_metrics': results[3] if not isinstance(results[3], Exception) else None,
            'timestamp': datetime.now().isoformat()
        }
        
        return comprehensive_data
    
    async def get_recent_news(self, hours: int = 6) -> List[Dict]:
        """최근 뉴스 가져오기 - 번역 통계 업데이트"""
        try:
            if self.news_collector:
                news = await self.news_collector.get_recent_news(hours)
                
                # 번역 통계 업데이트
                for article in news:
                    if article.get('title_ko') and article['title_ko'] != article.get('title', ''):
                        self.news_stats['translations_done'] += 1
                        
                        # Claude vs GPT 구분 (로그를 통해 추정)
                        if hasattr(self.news_collector, 'claude_translation_count'):
                            if self.news_collector.claude_translation_count > 0:
                                self.news_stats['claude_translations'] += 1
                        elif hasattr(self.news_collector, 'gpt_translation_count'):
                            if self.news_collector.gpt_translation_count > 0:
                                self.news_stats['gpt_translations'] += 1
                
                logger.info(f"📰 최근 {hours}시간 뉴스 {len(news)}건 조회 (번역: {sum([1 for n in news if n.get('title_ko')])}건)")
                return news
            else:
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
