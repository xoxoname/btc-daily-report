import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
import pytz
from bs4 import BeautifulSoup
import feedparser

logger = logging.getLogger(__name__)

class RealisticNewsCollector:
    def __init__(self, config):
        self.config = config
        self.session = None
        self.news_buffer = []
        
        # 모든 API 키들
        self.newsapi_key = getattr(config, 'NEWSAPI_KEY', None)
        self.newsdata_key = getattr(config, 'NEWSDATA_KEY', None)
        self.alpha_vantage_key = getattr(config, 'ALPHA_VANTAGE_KEY', None)
        
        # 크리티컬 키워드 (즉시 알림용)
        self.critical_keywords = [
            'trump bitcoin', 'trump crypto', 'trump ban', 'trump announces', 'trump says bitcoin',
            'fed rate decision', 'fed raises', 'fed cuts', 'powell says', 'fomc decides', 'fed meeting',
            'sec lawsuit bitcoin', 'sec sues', 'sec enforcement', 'sec charges bitcoin',
            'china bans bitcoin', 'china crypto ban', 'government bans crypto', 'regulatory ban',
            'bitcoin crash', 'crypto crash', 'market crash', 'flash crash', 'bitcoin plunge',
            'bitcoin etf approved', 'bitcoin etf rejected', 'etf decision', 'etf filing'
        ]
        
        # RSS 피드 (메인 소스)
        self.rss_feeds = [
            # 암호화폐 전문 (최우선)
            {'url': 'https://cointelegraph.com/rss', 'source': 'Cointelegraph', 'weight': 10, 'category': 'crypto'},
            {'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/', 'source': 'CoinDesk', 'weight': 10, 'category': 'crypto'},
            {'url': 'https://decrypt.co/feed', 'source': 'Decrypt', 'weight': 9, 'category': 'crypto'},
            {'url': 'https://bitcoinmagazine.com/.rss/full/', 'source': 'Bitcoin Magazine', 'weight': 9, 'category': 'crypto'},
            
            # 일반 금융 (고우선순위)
            {'url': 'https://feeds.reuters.com/reuters/businessNews', 'source': 'Reuters Business', 'weight': 9, 'category': 'finance'},
            {'url': 'https://feeds.bloomberg.com/markets/news.rss', 'source': 'Bloomberg Markets', 'weight': 9, 'category': 'finance'},
            {'url': 'https://rss.cnn.com/rss/money_news_economy.rss', 'source': 'CNN Business', 'weight': 8, 'category': 'finance'},
            {'url': 'https://feeds.finance.yahoo.com/rss/headline', 'source': 'Yahoo Finance', 'weight': 7, 'category': 'finance'},
            
            # 정치/정책 (중요)
            {'url': 'https://feeds.reuters.com/Reuters/PoliticsNews', 'source': 'Reuters Politics', 'weight': 8, 'category': 'politics'},
            {'url': 'https://feeds.washingtonpost.com/rss/politics', 'source': 'Washington Post Politics', 'weight': 7, 'category': 'politics'},
            
            # 추가 소스
            {'url': 'https://feeds.cnbc.com/cnbc/world', 'source': 'CNBC World', 'weight': 8, 'category': 'finance'},
            {'url': 'https://www.marketwatch.com/rss/topstories', 'source': 'MarketWatch', 'weight': 7, 'category': 'finance'},
        ]
        
        # API 사용량 추적
        self.api_usage = {
            'newsapi_today': 0,
            'newsdata_today': 0,
            'alpha_vantage_today': 0,
            'last_reset': datetime.now().date()
        }
        
        # API 일일 한도
        self.api_limits = {
            'newsapi': 20,      # 하루 20회
            'newsdata': 10,     # 하루 10회 (월 200건의 1/3)
            'alpha_vantage': 1  # 하루 1회 (월 25건의 1/4)
        }
        
        logger.info(f"뉴스 수집기 초기화 완료 - API 키 상태: NewsAPI={bool(self.newsapi_key)}, NewsData={bool(self.newsdata_key)}, AlphaVantage={bool(self.alpha_vantage_key)}")
    
    async def start_monitoring(self):
        """뉴스 모니터링 시작"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        logger.info("🔍 뉴스 모니터링 시작 - RSS 중심 + 스마트 API 사용")
        
        tasks = [
            self.monitor_rss_feeds(),      # 메인: RSS (30초마다)
            self.monitor_reddit(),         # 보조: Reddit (5분마다)
            self.smart_api_rotation()      # 제한적: 3개 API 순환 사용
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def monitor_rss_feeds(self):
        """RSS 피드 모니터링 - 메인 소스"""
        while True:
            try:
                # 가중치가 높은 소스부터 처리
                sorted_feeds = sorted(self.rss_feeds, key=lambda x: x['weight'], reverse=True)
                
                for feed_info in sorted_feeds:
                    try:
                        articles = await self._parse_rss_feed(feed_info)
                        
                        for article in articles:
                            # 가중치 8 이상은 크리티컬 체크
                            if feed_info['weight'] >= 8:
                                if self._is_critical_news(article):
                                    await self._trigger_emergency_alert(article)
                            
                            # 모든 RSS는 중요 뉴스 체크
                            if self._is_important_news(article):
                                await self._add_to_news_buffer(article)
                    
                    except Exception as e:
                        logger.error(f"RSS 오류 {feed_info['source']}: {e}")
                        continue
                
                await asyncio.sleep(30)  # 30초마다 전체 RSS 체크
                
            except Exception as e:
                logger.error(f"RSS 모니터링 전체 오류: {e}")
                await asyncio.sleep(180)
    
    async def monitor_reddit(self):
        """Reddit 모니터링"""
        reddit_subreddits = [
            {'name': 'Bitcoin', 'threshold': 300, 'weight': 8},
            {'name': 'CryptoCurrency', 'threshold': 500, 'weight': 7},
            {'name': 'investing', 'threshold': 1000, 'weight': 6},
            {'name': 'wallstreetbets', 'threshold': 3000, 'weight': 5}
        ]
        
        while True:
            try:
                for sub_info in reddit_subreddits:
                    try:
                        url = f"https://www.reddit.com/r/{sub_info['name']}/hot.json?limit=15"
                        
                        async with self.session.get(url, headers={'User-Agent': 'Bitcoin Monitor Bot'}) as response:
                            if response.status == 200:
                                data = await response.json()
                                posts = data['data']['children']
                                
                                for post in posts:
                                    post_data = post['data']
                                    
                                    if post_data['ups'] > sub_info['threshold']:
                                        article = {
                                            'title': post_data['title'],
                                            'description': post_data.get('selftext', '')[:200],
                                            'url': f"https://reddit.com{post_data['permalink']}",
                                            'source': f"Reddit r/{sub_info['name']}",
                                            'published_at': datetime.fromtimestamp(post_data['created_utc']).isoformat(),
                                            'upvotes': post_data['ups'],
                                            'weight': sub_info['weight']
                                        }
                                        
                                        if self._is_critical_news(article):
                                            await self._trigger_emergency_alert(article)
                                        elif self._is_important_news(article):
                                            await self._add_to_news_buffer(article)
                    
                    except Exception as e:
                        logger.error(f"Reddit 오류 {sub_info['name']}: {e}")
                        continue
                
                await asyncio.sleep(300)  # 5분마다 Reddit 체크
                
            except Exception as e:
                logger.error(f"Reddit 모니터링 전체 오류: {e}")
                await asyncio.sleep(600)
    
    async def smart_api_rotation(self):
        """3개 API 스마트 순환 사용"""
        while True:
            try:
                self._reset_daily_usage()
                
                # NewsAPI (가장 빈번히 사용)
                if self.newsapi_key and self.api_usage['newsapi_today'] < self.api_limits['newsapi']:
                    await self._call_newsapi()
                    self.api_usage['newsapi_today'] += 1
                    logger.info(f"NewsAPI 호출 완료 ({self.api_usage['newsapi_today']}/{self.api_limits['newsapi']})")
                
                await asyncio.sleep(1800)  # 30분 대기
                
                # NewsData API (중간 빈도)
                if self.newsdata_key and self.api_usage['newsdata_today'] < self.api_limits['newsdata']:
                    await self._call_newsdata()
                    self.api_usage['newsdata_today'] += 1
                    logger.info(f"NewsData API 호출 완료 ({self.api_usage['newsdata_today']}/{self.api_limits['newsdata']})")
                
                await asyncio.sleep(1800)  # 30분 대기
                
                # Alpha Vantage (가장 제한적)
                if self.alpha_vantage_key and self.api_usage['alpha_vantage_today'] < self.api_limits['alpha_vantage']:
                    await self._call_alpha_vantage()
                    self.api_usage['alpha_vantage_today'] += 1
                    logger.info(f"Alpha Vantage API 호출 완료 ({self.api_usage['alpha_vantage_today']}/{self.api_limits['alpha_vantage']})")
                
                await asyncio.sleep(3600)  # 1시간 대기
                
            except Exception as e:
                logger.error(f"API 순환 사용 오류: {e}")
                await asyncio.sleep(3600)
    
    async def _parse_rss_feed(self, feed_info: Dict) -> List[Dict]:
        """RSS 피드 파싱"""
        try:
            async with self.session.get(feed_info['url'], timeout=15) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    articles = []
                    
                    # 가중치에 따라 처리할 기사 수 결정
                    limit = min(20, max(8, feed_info['weight'] + 2))
                    
                    for entry in feed.entries[:limit]:
                        try:
                            # 발행 시간 처리
                            pub_time = datetime.now().isoformat()
                            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                pub_time = datetime(*entry.published_parsed[:6]).isoformat()
                        except:
                            pub_time = datetime.now().isoformat()
                        
                        article = {
                            'title': entry.get('title', ''),
                            'description': entry.get('summary', '')[:400],
                            'url': entry.get('link', ''),
                            'source': feed_info['source'],
                            'published_at': pub_time,
                            'weight': feed_info['weight'],
                            'category': feed_info['category']
                        }
                        
                        # 최근 4시간 내 기사만 (RSS는 빠른 업데이트)
                        try:
                            article_time = datetime.fromisoformat(pub_time.replace('Z', ''))
                            if datetime.now() - article_time < timedelta(hours=4):
                                articles.append(article)
                        except:
                            articles.append(article)
                    
                    return articles
        
        except Exception as e:
            logger.error(f"RSS 파싱 오류 {feed_info['url']}: {e}")
        
        return []
    
    async def _call_newsapi(self):
        """NewsAPI 호출"""
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': '(trump AND bitcoin) OR (fed AND rate) OR (sec AND bitcoin) OR "bitcoin etf" OR (powell AND crypto)',
                'language': 'en',
                'sortBy': 'publishedAt',
                'apiKey': self.newsapi_key,
                'pageSize': 15,
                'from': (datetime.now() - timedelta(hours=1)).isoformat()
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('articles', [])
                    
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'description': article.get('description', ''),
                            'url': article.get('url', ''),
                            'source': f"NewsAPI ({article.get('source', {}).get('name', 'Unknown')})",
                            'published_at': article.get('publishedAt', ''),
                            'weight': 10,
                            'category': 'api'
                        }
                        
                        if self._is_critical_news(formatted_article):
                            await self._trigger_emergency_alert(formatted_article)
                        elif self._is_important_news(formatted_article):
                            await self._add_to_news_buffer(formatted_article)
        
        except Exception as e:
            logger.error(f"NewsAPI 호출 오류: {e}")
    
    async def _call_newsdata(self):
        """NewsData API 호출"""
        try:
            url = "https://newsdata.io/api/1/news"
            params = {
                'apikey': self.newsdata_key,
                'q': 'bitcoin OR crypto OR "federal reserve" OR SEC',
                'language': 'en',
                'category': 'business,politics',
                'size': 10
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('results', [])
                    
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'description': article.get('description', ''),
                            'url': article.get('link', ''),
                            'source': f"NewsData ({article.get('source_id', 'Unknown')})",
                            'published_at': article.get('pubDate', ''),
                            'weight': 9,
                            'category': 'api'
                        }
                        
                        if self._is_critical_news(formatted_article):
                            await self._trigger_emergency_alert(formatted_article)
                        elif self._is_important_news(formatted_article):
                            await self._add_to_news_buffer(formatted_article)
        
        except Exception as e:
            logger.error(f"NewsData API 호출 오류: {e}")
    
    async def _call_alpha_vantage(self):
        """Alpha Vantage API 호출"""
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': 'CRYPTO:BTC',
                'topics': 'financial_markets,economy_monetary',
                'apikey': self.alpha_vantage_key,
                'sort': 'LATEST',
                'limit': 8
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('feed', [])
                    
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'description': article.get('summary', ''),
                            'url': article.get('url', ''),
                            'source': f"Alpha Vantage ({article.get('source', 'Unknown')})",
                            'published_at': article.get('time_published', ''),
                            'weight': 10,
                            'category': 'api',
                            'sentiment': article.get('overall_sentiment_label', 'Neutral')
                        }
                        
                        if self._is_critical_news(formatted_article):
                            await self._trigger_emergency_alert(formatted_article)
                        elif self._is_important_news(formatted_article):
                            await self._add_to_news_buffer(formatted_article)
        
        except Exception as e:
            logger.error(f"Alpha Vantage API 호출 오류: {e}")
    
    def _reset_daily_usage(self):
        """일일 사용량 리셋"""
        today = datetime.now().date()
        if today > self.api_usage['last_reset']:
            self.api_usage.update({
                'newsapi_today': 0,
                'newsdata_today': 0,
                'alpha_vantage_today': 0,
                'last_reset': today
            })
            logger.info("API 일일 사용량 리셋됨")
    
    def _is_critical_news(self, article: Dict) -> bool:
        """크리티컬 뉴스 판단"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        for keyword in self.critical_keywords:
            if keyword.lower() in content:
                # 신뢰할 만한 소스에서만 (가중치 7 이상)
                if article.get('weight', 0) >= 7:
                    logger.warning(f"🚨 크리티컬 뉴스 감지: {article.get('title', '')[:60]}...")
                    return True
        
        return False
    
    def _is_important_news(self, article: Dict) -> bool:
        """중요 뉴스 판단"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 비트코인/암호화폐 관련
        crypto_keywords = ['bitcoin', 'btc', 'crypto', 'cryptocurrency', 'digital asset']
        has_crypto = any(word in content for word in crypto_keywords)
        
        # 금융/정책 관련
        finance_keywords = ['fed', 'federal reserve', 'interest rate', 'inflation', 'sec', 'regulation', 'monetary policy']
        has_finance = any(word in content for word in finance_keywords)
        
        # 정치 관련
        political_keywords = ['trump', 'biden', 'congress', 'government', 'policy', 'administration']
        has_political = any(word in content for word in political_keywords)
        
        # 시장 관련
        market_keywords = ['market', 'trading', 'price', 'surge', 'crash', 'rally', 'dump', 'volatility']
        has_market = any(word in content for word in market_keywords)
        
        # 조건들
        conditions = [
            has_crypto and (has_finance or has_political or has_market),  # 암호화폐 + 다른 요소
            article.get('weight', 0) >= 9 and (has_finance or has_political),  # 고가중치 + 금융/정치
            article.get('category') == 'crypto' and has_market,  # 암호화폐 소스 + 시장 관련
            has_crypto and 'etf' in content,  # 암호화폐 ETF 관련
        ]
        
        return any(conditions)
    
    async def _trigger_emergency_alert(self, article: Dict):
        """긴급 알림 트리거"""
        try:
            event = {
                'type': 'critical_news',
                'title': article.get('title', '')[:100],
                'description': article.get('description', '')[:250],
                'source': article.get('source', ''),
                'url': article.get('url', ''),
                'timestamp': datetime.now(),
                'severity': 'critical',
                'impact': self._determine_impact(article),
                'weight': article.get('weight', 5),
                'category': article.get('category', 'unknown')
            }
            
            # 데이터 컬렉터에 전달
            if hasattr(self, 'data_collector') and self.data_collector:
                self.data_collector.events_buffer.append(event)
            
            logger.critical(f"🚨 긴급 뉴스 알림: {article.get('source', '')} - {article.get('title', '')}")
            
        except Exception as e:
            logger.error(f"긴급 알림 처리 오류: {e}")
    
    async def _add_to_news_buffer(self, article: Dict):
        """뉴스 버퍼에 추가"""
        try:
            # 중복 체크 (제목과 소스 기준)
            title_words = set(article.get('title', '').lower().split())
            source = article.get('source', '').lower()
            
            is_duplicate = False
            for existing in self.news_buffer:
                existing_words = set(existing.get('title', '').lower().split())
                existing_source = existing.get('source', '').lower()
                
                # 제목 유사도 70% 이상이고 소스가 같으면 중복
                if len(title_words & existing_words) / len(title_words | existing_words) > 0.7 and source == existing_source:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                self.news_buffer.append(article)
                
                # 버퍼 관리: 가중치와 시간 기준으로 정렬 후 상위 40개만 유지
                if len(self.news_buffer) > 40:
                    self.news_buffer.sort(
                        key=lambda x: (x.get('weight', 0), x.get('published_at', '')), 
                        reverse=True
                    )
                    self.news_buffer = self.news_buffer[:40]
        
        except Exception as e:
            logger.error(f"뉴스 버퍼 추가 오류: {e}")
    
    def _determine_impact(self, article: Dict) -> str:
        """뉴스 영향도 판단"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 강한 악재
        if any(word in content for word in ['ban', 'lawsuit', 'crash', 'crackdown', 'reject', 'enforcement action']):
            return "➖강한 악재"
        
        # 강한 호재
        if any(word in content for word in ['approval', 'approved', 'adoption', 'surge', 'breakthrough', 'all-time high']):
            return "➕강한 호재"
        
        # 일반 악재
        if any(word in content for word in ['concern', 'worry', 'decline', 'fall', 'drop', 'uncertainty']):
            return "➖악재 예상"
        
        # 일반 호재
        if any(word in content for word in ['growth', 'rise', 'increase', 'positive', 'rally', 'optimistic']):
            return "➕호재 예상"
        
        # 센티먼트 점수가 있는 경우 (Alpha Vantage)
        if article.get('sentiment'):
            sentiment = article.get('sentiment', '').lower()
            if 'bearish' in sentiment:
                return "➖악재 예상"
            elif 'bullish' in sentiment:
                return "➕호재 예상"
        
        return "중립"
    
    async def get_recent_news(self, hours: int = 6) -> List[Dict]:
        """최근 뉴스 가져오기"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_news = []
            
            for article in self.news_buffer:
                try:
                    if article.get('published_at'):
                        pub_time_str = article.get('published_at', '').replace('Z', '').replace('T', ' ')
                        pub_time = datetime.fromisoformat(pub_time_str)
                        if pub_time > cutoff_time:
                            recent_news.append(article)
                    else:
                        # 시간 정보가 없으면 최근 뉴스로 간주
                        recent_news.append(article)
                except:
                    recent_news.append(article)
            
            # 가중치, 카테고리, 시간순으로 정렬
            def sort_key(x):
                weight = x.get('weight', 0)
                category_priority = {'crypto': 3, 'api': 2, 'finance': 1, 'politics': 1}
                cat_score = category_priority.get(x.get('category', ''), 0)
                pub_time = x.get('published_at', '')
                return (weight, cat_score, pub_time)
            
            recent_news.sort(key=sort_key, reverse=True)
            
            logger.info(f"최근 {hours}시간 뉴스 {len(recent_news)}건 반환")
            return recent_news[:12]  # 최대 12개
            
        except Exception as e:
            logger.error(f"최근 뉴스 조회 오류: {e}")
            return []
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            logger.info("뉴스 수집기 세션 종료")
