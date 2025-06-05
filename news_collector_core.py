import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
import pytz
import feedparser
import os
import json

logger = logging.getLogger(__name__)

class NewsCollectorCore:
    """뉴스 수집 핵심 기능 - RSS, API 수집"""
    
    def __init__(self, config):
        self.config = config
        self.session = None
        self.news_buffer = []
        
        # API 키들
        self.newsapi_key = getattr(config, 'NEWSAPI_KEY', None)
        self.newsdata_key = getattr(config, 'NEWSDATA_KEY', None)
        self.alpha_vantage_key = getattr(config, 'ALPHA_VANTAGE_KEY', None)
        
        # API 사용량 추적
        self.api_usage = {
            'newsapi_today': 0,
            'newsdata_today': 0,
            'alpha_vantage_today': 0,
            'last_reset': datetime.now().date()
        }
        
        # API 일일 한도
        self.api_limits = {
            'newsapi': 50,
            'newsdata': 25,
            'alpha_vantage': 5
        }
        
        # RSS 피드
        self.rss_feeds = [
            # 암호화폐 전문 (최우선)
            {'url': 'https://cointelegraph.com/rss', 'source': 'Cointelegraph', 'weight': 10, 'category': 'crypto'},
            {'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/', 'source': 'CoinDesk', 'weight': 10, 'category': 'crypto'},
            {'url': 'https://decrypt.co/feed', 'source': 'Decrypt', 'weight': 9, 'category': 'crypto'},
            {'url': 'https://bitcoinmagazine.com/.rss/full/', 'source': 'Bitcoin Magazine', 'weight': 10, 'category': 'crypto'},
            {'url': 'https://cryptopotato.com/feed/', 'source': 'CryptoPotato', 'weight': 8, 'category': 'crypto'},
            {'url': 'https://u.today/rss', 'source': 'U.Today', 'weight': 8, 'category': 'crypto'},
            {'url': 'https://ambcrypto.com/feed/', 'source': 'AMBCrypto', 'weight': 8, 'category': 'crypto'},
            {'url': 'https://cryptonews.com/news/feed/', 'source': 'Cryptonews', 'weight': 8, 'category': 'crypto'},
            {'url': 'https://www.watcher.guru/news/feed', 'source': 'Watcher.Guru', 'weight': 9, 'category': 'crypto'},
            {'url': 'https://cryptoslate.com/feed/', 'source': 'CryptoSlate', 'weight': 8, 'category': 'crypto'},
            
            # 금융 (Fed/규제 관련)
            {'url': 'https://feeds.bloomberg.com/markets/news.rss', 'source': 'Bloomberg Markets', 'weight': 9, 'category': 'finance'},
            {'url': 'https://feeds.bloomberg.com/economics/news.rss', 'source': 'Bloomberg Economics', 'weight': 9, 'category': 'finance'},
            {'url': 'https://www.marketwatch.com/rss/topstories', 'source': 'MarketWatch', 'weight': 8, 'category': 'finance'},
            {'url': 'https://feeds.reuters.com/reuters/businessNews', 'source': 'Reuters Business', 'weight': 8, 'category': 'news'},
            {'url': 'https://feeds.cnbc.com/cnbc/ID/100003114/device/rss/rss.html', 'source': 'CNBC Markets', 'weight': 8, 'category': 'finance'},
            {'url': 'https://www.ft.com/rss/home/us', 'source': 'Financial Times', 'weight': 9, 'category': 'finance'},
            
            # 기술 뉴스
            {'url': 'https://techcrunch.com/feed/', 'source': 'TechCrunch', 'weight': 7, 'category': 'tech'},
            {'url': 'https://www.wired.com/feed/rss', 'source': 'Wired', 'weight': 7, 'category': 'tech'}
        ]
        
        logger.info(f"🔥 뉴스 수집기 초기화 완료")
        logger.info(f"📡 RSS 소스: {len(self.rss_feeds)}개")
        logger.info(f"🔑 NewsAPI: {'활성화' if self.newsapi_key else '비활성화'}")
        logger.info(f"🔑 NewsData: {'활성화' if self.newsdata_key else '비활성화'}")
        logger.info(f"🔑 Alpha Vantage: {'활성화' if self.alpha_vantage_key else '비활성화'}")
    
    async def start_monitoring(self):
        """뉴스 모니터링 시작"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=aiohttp.TCPConnector(limit=150, limit_per_host=50)
            )
        
        logger.info("🔥 뉴스 수집 모니터링 시작")
        
        tasks = [
            self.monitor_rss_feeds(),
            self.monitor_reddit(),
            self.api_rotation()
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def monitor_rss_feeds(self):
        """RSS 피드 모니터링 - 5초마다"""
        while True:
            try:
                sorted_feeds = sorted(self.rss_feeds, key=lambda x: x['weight'], reverse=True)
                successful_feeds = 0
                processed_articles = 0
                
                for feed_info in sorted_feeds:
                    try:
                        articles = await self._parse_rss_feed(feed_info)
                        
                        if articles:
                            successful_feeds += 1
                            
                            for article in articles:
                                # 최신 뉴스만 처리 (2시간 이내)
                                if not self._is_recent_news(article, hours=2):
                                    continue
                                
                                processed_articles += 1
                                # 버퍼에 추가 (다른 모듈에서 처리)
                                self.news_buffer.append(article)
                    
                    except Exception as e:
                        logger.warning(f"❌ RSS 피드 오류 {feed_info['source']}: {str(e)[:50]}")
                        continue
                
                if processed_articles > 0:
                    logger.info(f"📡 RSS 스캔: {successful_feeds}개 피드, {processed_articles}개 뉴스")
                
                # 버퍼 크기 관리
                if len(self.news_buffer) > 100:
                    self.news_buffer = self.news_buffer[-100:]
                
                await asyncio.sleep(5)  # 5초마다
                
            except Exception as e:
                logger.error(f"❌ RSS 모니터링 오류: {e}")
                await asyncio.sleep(30)
    
    async def monitor_reddit(self):
        """Reddit 모니터링 - 5분마다"""
        reddit_subreddits = [
            {'name': 'Bitcoin', 'threshold': 300, 'weight': 9},
            {'name': 'CryptoCurrency', 'threshold': 800, 'weight': 8},
            {'name': 'BitcoinMarkets', 'threshold': 200, 'weight': 9},
            {'name': 'investing', 'threshold': 1000, 'weight': 7},
            {'name': 'Economics', 'threshold': 500, 'weight': 7},
        ]
        
        while True:
            try:
                for sub_info in reddit_subreddits:
                    try:
                        url = f"https://www.reddit.com/r/{sub_info['name']}/hot.json?limit=15"
                        
                        async with self.session.get(url, headers={'User-Agent': 'Bitcoin Monitor Bot 1.0'}) as response:
                            if response.status == 200:
                                data = await response.json()
                                posts = data['data']['children']
                                
                                for post in posts:
                                    post_data = post['data']
                                    
                                    if post_data['ups'] > sub_info['threshold']:
                                        article = {
                                            'title': post_data['title'],
                                            'title_ko': post_data['title'],
                                            'description': post_data.get('selftext', '')[:1600],
                                            'url': f"https://reddit.com{post_data['permalink']}",
                                            'source': f"Reddit r/{sub_info['name']}",
                                            'published_at': datetime.fromtimestamp(post_data['created_utc']).isoformat(),
                                            'upvotes': post_data['ups'],
                                            'weight': sub_info['weight'],
                                            'category': 'social'
                                        }
                                        
                                        self.news_buffer.append(article)
                    
                    except Exception as e:
                        logger.warning(f"❌ Reddit 오류 {sub_info['name']}: {str(e)[:50]}")
                
                await asyncio.sleep(300)  # 5분마다
                
            except Exception as e:
                logger.error(f"❌ Reddit 모니터링 오류: {e}")
                await asyncio.sleep(600)
    
    async def api_rotation(self):
        """API 순환 사용"""
        while True:
            try:
                self._reset_daily_usage()
                
                # NewsAPI
                if self.newsapi_key and self.api_usage['newsapi_today'] < self.api_limits['newsapi']:
                    try:
                        await self._call_newsapi()
                        self.api_usage['newsapi_today'] += 1
                        logger.info(f"✅ NewsAPI 호출 ({self.api_usage['newsapi_today']}/{self.api_limits['newsapi']})")
                    except Exception as e:
                        logger.error(f"❌ NewsAPI 오류: {str(e)[:100]}")
                
                await asyncio.sleep(600)  # 10분 대기
                
                # NewsData API
                if self.newsdata_key and self.api_usage['newsdata_today'] < self.api_limits['newsdata']:
                    try:
                        await self._call_newsdata()
                        self.api_usage['newsdata_today'] += 1
                        logger.info(f"✅ NewsData 호출 ({self.api_usage['newsdata_today']}/{self.api_limits['newsdata']})")
                    except Exception as e:
                        logger.error(f"❌ NewsData 오류: {str(e)[:100]}")
                
                await asyncio.sleep(600)  # 10분 대기
                
                # Alpha Vantage
                if self.alpha_vantage_key and self.api_usage['alpha_vantage_today'] < self.api_limits['alpha_vantage']:
                    try:
                        await self._call_alpha_vantage()
                        self.api_usage['alpha_vantage_today'] += 1
                        logger.info(f"✅ Alpha Vantage 호출 ({self.api_usage['alpha_vantage_today']}/{self.api_limits['alpha_vantage']})")
                    except Exception as e:
                        logger.error(f"❌ Alpha Vantage 오류: {str(e)[:100]}")
                
                await asyncio.sleep(1200)  # 20분 대기
                
            except Exception as e:
                logger.error(f"❌ API 순환 오류: {e}")
                await asyncio.sleep(1800)
    
    async def _parse_rss_feed(self, feed_info: Dict) -> List[Dict]:
        """RSS 피드 파싱"""
        articles = []
        try:
            async with self.session.get(
                feed_info['url'], 
                timeout=aiohttp.ClientTimeout(total=12),
                headers={'User-Agent': 'Mozilla/5.0 (compatible; BitcoinNewsBot/2.0)'}
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    if feed.entries:
                        limit = min(25, max(10, feed_info['weight']))
                        
                        for entry in feed.entries[:limit]:
                            try:
                                # 발행 시간 처리
                                pub_time = datetime.now().isoformat()
                                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                    pub_time = datetime(*entry.published_parsed[:6]).isoformat()
                                elif hasattr(entry, 'published'):
                                    try:
                                        from dateutil import parser
                                        pub_time = parser.parse(entry.published).isoformat()
                                    except:
                                        pass
                                
                                article = {
                                    'title': entry.get('title', '').strip(),
                                    'description': entry.get('summary', '').strip()[:1600],
                                    'url': entry.get('link', '').strip(),
                                    'source': feed_info['source'],
                                    'published_at': pub_time,
                                    'weight': feed_info['weight'],
                                    'category': feed_info.get('category', 'unknown')
                                }
                                
                                if article['title'] and article['url']:
                                    articles.append(article)
                                        
                            except Exception as e:
                                logger.debug(f"❌ 기사 파싱 오류: {str(e)[:50]}")
                                continue
        
        except asyncio.TimeoutError:
            logger.debug(f"⏰ {feed_info['source']}: 타임아웃")
        except Exception as e:
            logger.debug(f"❌ {feed_info['source']}: {str(e)[:50]}")
        
        return articles
    
    async def _call_newsapi(self):
        """NewsAPI 호출"""
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': '(bitcoin OR btc OR "bitcoin etf" OR "fed rate" OR "trump tariffs" OR "trade deal" OR "inflation data" OR "china manufacturing" OR "powell speech" OR "fomc decision" OR "cpi report" OR "unemployment rate" OR "sec bitcoin" OR "tesla bitcoin" OR "microstrategy bitcoin" OR "blackrock bitcoin" OR "russia bitcoin" OR "ukraine war" OR "china sanctions" OR "bitcoin crosses 100k" OR "bitcoin 100000") AND NOT ("altcoin only" OR "how to mine" OR "price prediction tutorial")',
                'language': 'en',
                'sortBy': 'publishedAt',
                'apiKey': self.newsapi_key,
                'pageSize': 100,
                'from': (datetime.now() - timedelta(hours=3)).isoformat()
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('articles', [])
                    
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'title_ko': article.get('title', ''),
                            'description': article.get('description', '')[:1600],
                            'url': article.get('url', ''),
                            'source': f"NewsAPI ({article.get('source', {}).get('name', 'Unknown')})",
                            'published_at': article.get('publishedAt', ''),
                            'weight': 9,
                            'category': 'api'
                        }
                        
                        self.news_buffer.append(formatted_article)
                else:
                    logger.warning(f"❌ NewsAPI 응답 오류: {response.status}")
        
        except Exception as e:
            logger.error(f"❌ NewsAPI 호출 오류: {e}")
    
    async def _call_newsdata(self):
        """NewsData API 호출"""
        try:
            url = "https://newsdata.io/api/1/news"
            params = {
                'apikey': self.newsdata_key,
                'q': 'bitcoin OR btc OR "bitcoin etf" OR "bitcoin regulation" OR "russia bitcoin" OR "sberbank bitcoin" OR "fed rate decision" OR "trump tariffs" OR "trade deal" OR "inflation data" OR "china manufacturing" OR "powell speech" OR "fomc decision" OR "tesla bitcoin" OR "microstrategy bitcoin" OR "sec bitcoin" OR "ukraine war" OR "china sanctions" OR "bitcoin crosses 100k"',
                'language': 'en',
                'category': 'business,top,politics',
                'size': 50
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('results', [])
                    
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'title_ko': article.get('title', ''),
                            'description': article.get('description', '')[:1600],
                            'url': article.get('link', ''),
                            'source': f"NewsData ({article.get('source_id', 'Unknown')})",
                            'published_at': article.get('pubDate', ''),
                            'weight': 8,
                            'category': 'api'
                        }
                        
                        self.news_buffer.append(formatted_article)
                else:
                    logger.warning(f"❌ NewsData 응답 오류: {response.status}")
        
        except Exception as e:
            logger.error(f"❌ NewsData 호출 오류: {e}")
    
    async def _call_alpha_vantage(self):
        """Alpha Vantage API 호출"""
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': 'CRYPTO:BTC,TSLA,MSTR',
                'topics': 'financial_markets,technology,earnings,economy',
                'apikey': self.alpha_vantage_key,
                'sort': 'LATEST',
                'limit': 50
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('feed', [])
                    
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'title_ko': article.get('title', ''),
                            'description': article.get('summary', '')[:1600],
                            'url': article.get('url', ''),
                            'source': f"Alpha Vantage ({article.get('source', 'Unknown')})",
                            'published_at': article.get('time_published', ''),
                            'weight': 9,
                            'category': 'api',
                            'sentiment': article.get('overall_sentiment_label', 'Neutral')
                        }
                        
                        self.news_buffer.append(formatted_article)
                else:
                    logger.warning(f"❌ Alpha Vantage 응답 오류: {response.status}")
        
        except Exception as e:
            logger.error(f"❌ Alpha Vantage 호출 오류: {e}")
    
    def _is_recent_news(self, article: Dict, hours: int = 2) -> bool:
        """뉴스가 최근 것인지 확인"""
        try:
            pub_time_str = article.get('published_at', '')
            if not pub_time_str:
                return True
            
            try:
                if 'T' in pub_time_str:
                    pub_time = datetime.fromisoformat(pub_time_str.replace('Z', ''))
                else:
                    from dateutil import parser
                    pub_time = parser.parse(pub_time_str)
                
                if pub_time.tzinfo is None:
                    pub_time = pytz.UTC.localize(pub_time)
                
                time_diff = datetime.now(pytz.UTC) - pub_time
                return time_diff.total_seconds() < (hours * 3600)
            except:
                return True
        except:
            return True
    
    def _reset_daily_usage(self):
        """일일 사용량 리셋"""
        today = datetime.now().date()
        if today > self.api_usage['last_reset']:
            old_usage = dict(self.api_usage)
            self.api_usage.update({
                'newsapi_today': 0,
                'newsdata_today': 0,
                'alpha_vantage_today': 0,
                'last_reset': today
            })
            logger.info(f"🔄 일일 API 사용량 리셋")
    
    async def get_recent_news(self, hours: int = 12) -> List[Dict]:
        """최근 뉴스 가져오기"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_news = []
            seen_hashes = set()
            
            for article in sorted(self.news_buffer, key=lambda x: (x.get('weight', 0), x.get('published_at', '')), reverse=True):
                try:
                    if article.get('published_at'):
                        pub_time_str = article.get('published_at', '')
                        try:
                            if 'T' in pub_time_str:
                                pub_time = datetime.fromisoformat(pub_time_str.replace('Z', ''))
                            else:
                                from dateutil import parser
                                pub_time = parser.parse(pub_time_str)
                            
                            if pub_time > cutoff_time:
                                import hashlib
                                content_hash = hashlib.md5(article.get('title', '').encode()).hexdigest()
                                if content_hash not in seen_hashes:
                                    recent_news.append(article)
                                    seen_hashes.add(content_hash)
                        except:
                            pass
                except:
                    pass
            
            recent_news.sort(key=lambda x: (x.get('weight', 0), x.get('published_at', '')), reverse=True)
            
            logger.info(f"📰 최근 {hours}시간 뉴스: {len(recent_news)}개")
            
            return recent_news[:25]
            
        except Exception as e:
            logger.error(f"❌ 최근 뉴스 조회 오류: {e}")
            return []
    
    async def close(self):
        """세션 종료"""
        try:
            if self.session:
                await self.session.close()
                logger.info("🔚 뉴스 수집기 세션 종료")
        except Exception as e:
            logger.error(f"❌ 세션 종료 중 오류: {e}")
