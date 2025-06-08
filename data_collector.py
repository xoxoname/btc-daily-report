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
        
        # 🔥🔥 뉴스 수집기 직접 초기화 - 임포트 문제 해결
        self.news_collector = None
        self._initialize_news_collector()
        
        # 뉴스 처리 통계
        self.news_stats = {
            'total_processed': 0,
            'critical_alerts': 0,
            'translations_done': 0,
            'claude_translations': 0,
            'gpt_translations': 0,
            'last_reset': datetime.now()
        }
        
        # 🔥🔥 예외 감지 강화
        self.last_exception_check = datetime.now()
        self.exception_check_interval = 60  # 1분마다 체크
        
    def _initialize_news_collector(self):
        """🔥🔥 뉴스 수집기 직접 초기화"""
        try:
            # news_collector_core.py 직접 사용
            from news_collector_core import NewsCollectorCore
            from news_processor import NewsProcessor
            from news_translator import NewsTranslator
            
            # 뉴스 수집기 컴포넌트들 초기화
            self.news_core = NewsCollectorCore(self.config)
            self.news_processor = NewsProcessor(self.config)
            self.news_translator = NewsTranslator(self.config)
            
            # 통합 뉴스 수집기 생성
            self.news_collector = self
            
            logger.info("✅ 뉴스 수집기 직접 초기화 완료")
            
        except ImportError as e:
            logger.error(f"❌ 뉴스 수집기 모듈 임포트 실패: {e}")
            self.news_collector = None
            self.news_core = None
            self.news_processor = None
            self.news_translator = None
        except Exception as e:
            logger.error(f"❌ 뉴스 수집기 초기화 실패: {e}")
            self.news_collector = None
    
    async def start_monitoring(self):
        """🔥🔥 뉴스 모니터링 시작 - 예외 감지 강화"""
        if not self.news_core:
            logger.error("❌ 뉴스 수집기가 초기화되지 않음")
            return
        
        logger.info("🔥 뉴스 모니터링 시작")
        
        tasks = [
            self.news_core.start_monitoring(),
            self.process_news_continuously(),
            self.generate_critical_events()
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def process_news_continuously(self):
        """🔥🔥 뉴스 지속적 처리 및 예외 이벤트 생성"""
        while True:
            try:
                await asyncio.sleep(15)  # 15초마다 처리
                
                if not self.news_core or not self.news_processor:
                    continue
                
                # 뉴스 코어에서 새로운 뉴스 가져오기
                recent_news = self.news_core.news_buffer[-20:] if self.news_core.news_buffer else []
                
                if not recent_news:
                    continue
                
                processed_count = 0
                critical_count = 0
                
                for article in recent_news:
                    try:
                        # 비트코인 관련성 체크
                        if not self.news_processor.is_bitcoin_or_macro_related(article):
                            continue
                        
                        processed_count += 1
                        
                        # 크리티컬 뉴스 체크
                        if self.news_processor.is_critical_news(article):
                            # 중복 체크 - 더 관대하게 적용
                            if not self.news_processor.is_duplicate_emergency(article, time_window=120):  # 2시간으로 단축
                                critical_count += 1
                                
                                # 크리티컬 이벤트 생성
                                event = await self.news_processor.create_emergency_event(
                                    article, 
                                    self.news_translator
                                )
                                
                                if event:
                                    self.events_buffer.append(event)
                                    self.news_stats['critical_alerts'] += 1
                                    
                                    logger.warning(f"🚨 크리티컬 이벤트 생성: {event.get('title_ko', event.get('title', ''))[:60]}...")
                        
                        # 중요 뉴스도 처리
                        elif self.news_processor.is_important_news(article):
                            # 중요 뉴스는 별도 처리 (덜 엄격한 조건)
                            event = {
                                'type': 'important_news',
                                'title': article.get('title', ''),
                                'title_ko': article.get('title', ''),
                                'description': article.get('description', '')[:800],
                                'source': article.get('source', ''),
                                'timestamp': datetime.now(),
                                'severity': 'medium',
                                'weight': article.get('weight', 5),
                                'category': article.get('category', 'news')
                            }
                            
                            # 중요 뉴스는 더 많이 허용
                            if len(self.events_buffer) < 50:
                                self.events_buffer.append(event)
                    
                    except Exception as e:
                        logger.error(f"❌ 뉴스 처리 오류: {e}")
                        continue
                
                if processed_count > 0:
                    logger.info(f"📰 뉴스 처리: {processed_count}개 처리, {critical_count}개 크리티컬 생성")
                
                # 통계 업데이트
                self.news_stats['total_processed'] += processed_count
                
            except Exception as e:
                logger.error(f"❌ 뉴스 지속 처리 오류: {e}")
                await asyncio.sleep(30)
    
    async def generate_critical_events(self):
        """🔥🔥 강제로 크리티컬 이벤트 생성 (테스트/디버깅용)"""
        while True:
            try:
                await asyncio.sleep(300)  # 5분마다
                
                current_time = datetime.now()
                time_since_last = current_time - self.last_exception_check
                
                # 30분간 크리티컬 이벤트가 없으면 강제 생성
                if time_since_last > timedelta(minutes=30):
                    # 시장 데이터 기반 예외 상황 체크
                    market_events = await self.check_market_anomalies()
                    
                    if market_events:
                        for event in market_events:
                            self.events_buffer.append(event)
                            logger.warning(f"🔥 시장 예외 상황 감지: {event.get('title', '')}")
                    
                    # 뉴스 기반 강제 이벤트
                    if not market_events and len(self.events_buffer) == 0:
                        # 최근 뉴스 중에서 강제로 이벤트 생성
                        await self.force_generate_news_event()
                    
                    self.last_exception_check = current_time
                
            except Exception as e:
                logger.error(f"❌ 크리티컬 이벤트 생성 오류: {e}")
                await asyncio.sleep(60)
    
    async def check_market_anomalies(self) -> List[Dict]:
        """🔥🔥 시장 이상 징후 직접 체크"""
        anomalies = []
        
        try:
            if not self.bitget_client:
                return anomalies
            
            # 현재 시장 데이터 조회
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            if not ticker:
                return anomalies
            
            current_price = float(ticker.get('last', 0)) if ticker.get('last') else 0
            change_24h = float(ticker.get('changeUtc', 0)) if ticker.get('changeUtc') else 0
            volume_24h = float(ticker.get('baseVolume', 0)) if ticker.get('baseVolume') else 0
            
            if current_price <= 0:
                return anomalies
            
            # 가격 급변동 체크 (1.5% 이상)
            if abs(change_24h) >= 0.015:
                anomaly = {
                    'type': 'price_anomaly',
                    'title': f"BTC {'급등' if change_24h > 0 else '급락'} {abs(change_24h*100):.1f}%",
                    'title_ko': f"비트코인 {'급등' if change_24h > 0 else '급락'} {abs(change_24h*100):.1f}%",
                    'description': f"24시간 내 ${current_price:,.0f}에서 {abs(change_24h*100):.1f}% {'상승' if change_24h > 0 else '하락'}",
                    'timestamp': datetime.now(),
                    'severity': 'high' if abs(change_24h) >= 0.03 else 'medium',
                    'impact': f"{'📈 호재' if change_24h > 0 else '📉 악재'}",
                    'expected_change': f"{'📈 추가 상승' if change_24h > 0 else '📉 추가 하락'} 가능성",
                    'source': 'Market Data',
                    'category': 'price_movement',
                    'weight': 8
                }
                anomalies.append(anomaly)
                logger.warning(f"🚨 가격 급변동 감지: {abs(change_24h*100):.1f}%")
            
            # 거래량 급증 체크
            avg_volume = 50000  # 평균 거래량 기준
            if volume_24h > avg_volume * 2:
                anomaly = {
                    'type': 'volume_anomaly',
                    'title': f"BTC 거래량 급증 {volume_24h/avg_volume:.1f}배",
                    'title_ko': f"비트코인 거래량 급증 {volume_24h/avg_volume:.1f}배",
                    'description': f"24시간 거래량이 평균 대비 {volume_24h/avg_volume:.1f}배 증가",
                    'timestamp': datetime.now(),
                    'severity': 'medium',
                    'impact': "⚡ 변동성 확대",
                    'expected_change': "단기 변동성 증가 예상",
                    'source': 'Market Data',
                    'category': 'volume_spike',
                    'weight': 7
                }
                anomalies.append(anomaly)
                logger.info(f"📊 거래량 급증: {volume_24h/avg_volume:.1f}배")
            
        except Exception as e:
            logger.error(f"❌ 시장 이상 징후 체크 실패: {e}")
        
        return anomalies
    
    async def force_generate_news_event(self):
        """🔥🔥 강제 뉴스 이벤트 생성 (디버깅용)"""
        try:
            # 최근 뉴스에서 비트코인 관련 뉴스 찾기
            if not self.news_core or not self.news_core.news_buffer:
                # 뉴스가 없으면 기본 이벤트 생성
                default_event = {
                    'type': 'system_check',
                    'title': 'Bitcoin Market Monitoring Active',
                    'title_ko': '비트코인 시장 모니터링 활성화',
                    'description': '시스템이 정상적으로 비트코인 시장을 모니터링하고 있습니다.',
                    'timestamp': datetime.now(),
                    'severity': 'low',
                    'impact': '📊 시스템 정상',
                    'expected_change': '지속적인 모니터링 중',
                    'source': 'System Monitor',
                    'category': 'system',
                    'weight': 5
                }
                self.events_buffer.append(default_event)
                logger.info("📊 기본 시스템 체크 이벤트 생성")
                return
            
            # 최근 뉴스 중에서 비트코인 관련 뉴스 찾기
            recent_news = self.news_core.news_buffer[-10:]
            bitcoin_news = []
            
            for article in recent_news:
                content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
                if any(word in content for word in ['bitcoin', 'btc', 'crypto', 'fed', 'etf']):
                    bitcoin_news.append(article)
            
            if bitcoin_news:
                # 가장 높은 가중치의 뉴스 선택
                best_news = max(bitcoin_news, key=lambda x: x.get('weight', 0))
                
                event = {
                    'type': 'forced_news',
                    'title': best_news.get('title', ''),
                    'title_ko': best_news.get('title', ''),
                    'description': best_news.get('description', '')[:800],
                    'timestamp': datetime.now(),
                    'severity': 'medium',
                    'impact': '📰 뉴스 업데이트',
                    'expected_change': '시장 관심 지속',
                    'source': best_news.get('source', 'News Monitor'),
                    'category': 'forced_news',
                    'weight': best_news.get('weight', 5),
                    'url': best_news.get('url', '')
                }
                
                self.events_buffer.append(event)
                logger.info(f"📰 강제 뉴스 이벤트 생성: {event['title'][:50]}...")
            
        except Exception as e:
            logger.error(f"❌ 강제 뉴스 이벤트 생성 실패: {e}")
        
    async def start(self):
        """데이터 수집 시작 - 뉴스 우선도 높임"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        logger.info("🚀 실시간 데이터 수집 시작 (뉴스 강화)")
        
        # 병렬 태스크 실행
        tasks = []
        
        # 🔥🔥 뉴스 모니터링을 최우선으로 시작
        if self.news_core:
            tasks.append(self.start_monitoring())
            logger.info("📰 강화된 뉴스 모니터링 활성화")
        else:
            logger.error("❌ 뉴스 수집기가 없어서 뉴스 모니터링을 시작할 수 없음")
        
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
                    else:
                        logger.warning("⚠️ 지난 1시간 동안 처리된 뉴스가 없음")
                    
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
            if self.news_core:
                news = await self.news_core.get_recent_news(hours)
                
                # 번역 통계 업데이트
                for article in news:
                    if article.get('title_ko') and article['title_ko'] != article.get('title', ''):
                        self.news_stats['translations_done'] += 1
                        
                        # Claude vs GPT 구분 (로그를 통해 추정)
                        if hasattr(self.news_translator, 'claude_translation_count'):
                            if self.news_translator.claude_translation_count > 0:
                                self.news_stats['claude_translations'] += 1
                        elif hasattr(self.news_translator, 'gpt_translation_count'):
                            if self.news_translator.gpt_translation_count > 0:
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
            
            if self.news_core:
                await self.news_core.close()
            
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
