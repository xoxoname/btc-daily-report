import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
import pytz
from bs4 import BeautifulSoup
import feedparser
import openai
import os

logger = logging.getLogger(__name__)

class RealisticNewsCollector:
    def __init__(self, config):
        self.config = config
        self.session = None
        self.news_buffer = []
        
        # OpenAI 클라이언트 초기화 (번역용)
        self.openai_client = None
        if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY:
            self.openai_client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        
        # 모든 API 키들
        self.newsapi_key = getattr(config, 'NEWSAPI_KEY', None)
        self.newsdata_key = getattr(config, 'NEWSDATA_KEY', None)
        self.alpha_vantage_key = getattr(config, 'ALPHA_VANTAGE_KEY', None)
        
        # 크리티컬 키워드 (즉시 알림용) - 한국어 추가
        self.critical_keywords = [
            'trump bitcoin', 'trump crypto', 'trump ban', 'trump announces', 'trump says bitcoin',
            '트럼프 비트코인', '트럼프 암호화폐', '트럼프 규제',
            'fed rate decision', 'fed raises', 'fed cuts', 'powell says', 'fomc decides', 'fed meeting',
            '연준 금리', 'FOMC 결정', '파월 발언', '금리 인상', '금리 인하',
            'sec lawsuit bitcoin', 'sec sues', 'sec enforcement', 'sec charges bitcoin',
            'SEC 소송', 'SEC 규제', 'SEC 비트코인',
            'china bans bitcoin', 'china crypto ban', 'government bans crypto', 'regulatory ban',
            '중국 비트코인 금지', '정부 규제', '암호화폐 금지',
            'bitcoin crash', 'crypto crash', 'market crash', 'flash crash', 'bitcoin plunge',
            '비트코인 폭락', '암호화폐 급락', '시장 붕괴',
            'bitcoin etf approved', 'bitcoin etf rejected', 'etf decision', 'etf filing',
            'ETF 승인', 'ETF 거부', 'ETF 결정'
        ]
        
        # RSS 피드 (문제있는 2개 제거)
        self.rss_feeds = [
            # 암호화폐 전문 (최우선) - 확실히 작동하는 것들
            {'url': 'https://cointelegraph.com/rss', 'source': 'Cointelegraph', 'weight': 10, 'category': 'crypto'},
            {'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/', 'source': 'CoinDesk', 'weight': 10, 'category': 'crypto'},
            {'url': 'https://decrypt.co/feed', 'source': 'Decrypt', 'weight': 9, 'category': 'crypto'},
            {'url': 'https://bitcoinmagazine.com/.rss/full/', 'source': 'Bitcoin Magazine', 'weight': 9, 'category': 'crypto'},
            
            # 새로운 암호화폐 소스 (CryptoCoinsNews 제거됨)
            {'url': 'https://ambcrypto.com/feed/', 'source': 'AMBCrypto', 'weight': 8, 'category': 'crypto'},
            {'url': 'https://cryptopotato.com/feed/', 'source': 'CryptoPotato', 'weight': 8, 'category': 'crypto'},
            
            # 일반 금융 (Reuters Finance 제거됨)
            {'url': 'https://www.marketwatch.com/rss/topstories', 'source': 'MarketWatch', 'weight': 8, 'category': 'finance'},
            {'url': 'https://seekingalpha.com/feed.xml', 'source': 'Seeking Alpha', 'weight': 8, 'category': 'finance'},
            {'url': 'https://feeds.feedburner.com/InvestingcomAnalysis', 'source': 'Investing.com', 'weight': 8, 'category': 'finance'},
            {'url': 'https://www.fool.com/feeds/index.aspx', 'source': 'Motley Fool', 'weight': 7, 'category': 'finance'},
            
            # 일반 뉴스 (확실한 것들)
            {'url': 'https://rss.cnn.com/rss/edition.rss', 'source': 'CNN World', 'weight': 8, 'category': 'news'},
            {'url': 'http://feeds.bbci.co.uk/news/business/rss.xml', 'source': 'BBC Business', 'weight': 8, 'category': 'finance'},
            {'url': 'https://feeds.npr.org/1001/rss.xml', 'source': 'NPR News', 'weight': 7, 'category': 'news'},
            {'url': 'https://feeds.washingtonpost.com/rss/business', 'source': 'Washington Post Business', 'weight': 7, 'category': 'finance'},
            
            # 테크/비즈니스 (안정적인 것들)
            {'url': 'https://techcrunch.com/feed/', 'source': 'TechCrunch', 'weight': 7, 'category': 'tech'},
            {'url': 'https://www.wired.com/feed/rss', 'source': 'Wired', 'weight': 6, 'category': 'tech'},
            {'url': 'https://feeds.feedburner.com/venturebeat/SZYF', 'source': 'VentureBeat', 'weight': 7, 'category': 'tech'},
            
            # 추가 신뢰할만한 금융 소스 (Bloomberg만 유지)
            {'url': 'https://feeds.bloomberg.com/markets/news.rss', 'source': 'Bloomberg Markets', 'weight': 9, 'category': 'finance'},
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
            'newsapi': 15,      # 하루 15회 (안전하게)
            'newsdata': 8,      # 하루 8회 (월 200건의 1/4)
            'alpha_vantage': 1  # 하루 1회
        }
        
        logger.info(f"뉴스 수집기 초기화 완료 - API 키 상태: NewsAPI={bool(self.newsapi_key)}, NewsData={bool(self.newsdata_key)}, AlphaVantage={bool(self.alpha_vantage_key)}")
    
    async def translate_text(self, text: str, max_length: int = 100) -> str:
        """텍스트를 한국어로 번역"""
        if not self.openai_client:
            return text
        
        try:
            # 길이 제한
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional translator. Translate the following text to Korean concisely and accurately. Keep it under 80 characters."},
                    {"role": "user", "content": text}
                ],
                max_tokens=150,
                temperature=0.3
            )
            
            translated = response.choices[0].message.content.strip()
            # 번역 결과가 너무 길면 자르기
            if len(translated) > 80:
                translated = translated[:77] + "..."
            
            return translated
            
        except Exception as e:
            logger.warning(f"번역 실패: {str(e)[:50]}")
            return text[:80] + "..." if len(text) > 80 else text
    
    async def start_monitoring(self):
        """뉴스 모니터링 시작"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),  # 타임아웃 설정
                connector=aiohttp.TCPConnector(limit=100, limit_per_host=30)
            )
        
        logger.info("🔍 뉴스 모니터링 시작 - RSS 중심 + 스마트 API 사용")
        
        tasks = [
            self.monitor_rss_feeds(),      # 메인: RSS (45초마다)
            self.monitor_reddit(),         # 보조: Reddit (10분마다)
            self.smart_api_rotation()      # 제한적: 3개 API 순환 사용
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def monitor_rss_feeds(self):
        """RSS 피드 모니터링 - 메인 소스"""
        while True:
            try:
                # 가중치가 높은 소스부터 처리
                sorted_feeds = sorted(self.rss_feeds, key=lambda x: x['weight'], reverse=True)
                successful_feeds = 0
                
                for feed_info in sorted_feeds:
                    try:
                        articles = await self._parse_rss_feed(feed_info)
                        
                        if articles:  # 성공적으로 기사를 가져온 경우
                            successful_feeds += 1
                            
                            for article in articles:
                                # 제목 번역
                                if self.openai_client and article.get('title'):
                                    article['title_ko'] = await self.translate_text(article['title'])
                                else:
                                    article['title_ko'] = article.get('title', '')
                                
                                # 가중치 8 이상은 크리티컬 체크
                                if feed_info['weight'] >= 8:
                                    if self._is_critical_news(article):
                                        await self._trigger_emergency_alert(article)
                                
                                # 모든 RSS는 중요 뉴스 체크
                                if self._is_important_news(article):
                                    await self._add_to_news_buffer(article)
                    
                    except Exception as e:
                        logger.warning(f"RSS 피드 일시 오류 {feed_info['source']}: {str(e)[:100]}")
                        continue
                
                logger.info(f"📰 RSS 스캔 완료: {successful_feeds}/{len(sorted_feeds)} 피드 성공")
                await asyncio.sleep(45)  # 45초마다 전체 RSS 체크
                
            except Exception as e:
                logger.error(f"RSS 모니터링 전체 오류: {e}")
                await asyncio.sleep(180)
    
    async def monitor_reddit(self):
        """Reddit 모니터링"""
        reddit_subreddits = [
            {'name': 'Bitcoin', 'threshold': 200, 'weight': 8},
            {'name': 'CryptoCurrency', 'threshold': 400, 'weight': 7},
            {'name': 'investing', 'threshold': 800, 'weight': 6},
            {'name': 'wallstreetbets', 'threshold': 2000, 'weight': 5}
        ]
        
        while True:
            try:
                successful_subs = 0
                
                for sub_info in reddit_subreddits:
                    try:
                        url = f"https://www.reddit.com/r/{sub_info['name']}/hot.json?limit=20"
                        
                        async with self.session.get(url, headers={'User-Agent': 'Bitcoin Monitor Bot 1.0'}) as response:
                            if response.status == 200:
                                data = await response.json()
                                posts = data['data']['children']
                                successful_subs += 1
                                
                                relevant_posts = 0
                                for post in posts:
                                    post_data = post['data']
                                    
                                    if post_data['ups'] > sub_info['threshold']:
                                        article = {
                                            'title': post_data['title'],
                                            'title_ko': await self.translate_text(post_data['title']) if self.openai_client else post_data['title'],
                                            'description': post_data.get('selftext', '')[:200],
                                            'url': f"https://reddit.com{post_data['permalink']}",
                                            'source': f"Reddit r/{sub_info['name']}",
                                            'published_at': datetime.fromtimestamp(post_data['created_utc']).isoformat(),
                                            'upvotes': post_data['ups'],
                                            'weight': sub_info['weight']
                                        }
                                        
                                        if self._is_critical_news(article):
                                            await self._trigger_emergency_alert(article)
                                            relevant_posts += 1
                                        elif self._is_important_news(article):
                                            await self._add_to_news_buffer(article)
                                            relevant_posts += 1
                                
                                if relevant_posts > 0:
                                    logger.info(f"📱 Reddit r/{sub_info['name']}: {relevant_posts}개 관련 포스트 발견")
                    
                    except Exception as e:
                        logger.warning(f"Reddit 오류 {sub_info['name']}: {str(e)[:50]}")
                        continue
                
                logger.info(f"📱 Reddit 스캔 완료: {successful_subs}/{len(reddit_subreddits)} 서브레딧 성공")
                await asyncio.sleep(600)  # 10분마다 Reddit 체크
                
            except Exception as e:
                logger.error(f"Reddit 모니터링 전체 오류: {e}")
                await asyncio.sleep(900)
    
    async def smart_api_rotation(self):
        """3개 API 스마트 순환 사용"""
        while True:
            try:
                self._reset_daily_usage()
                
                # NewsAPI (30분마다)
                if self.newsapi_key and self.api_usage['newsapi_today'] < self.api_limits['newsapi']:
                    try:
                        await self._call_newsapi()
                        self.api_usage['newsapi_today'] += 1
                        logger.info(f"✅ NewsAPI 호출 완료 ({self.api_usage['newsapi_today']}/{self.api_limits['newsapi']})")
                    except Exception as e:
                        logger.error(f"NewsAPI 호출 실패: {str(e)[:100]}")
                
                await asyncio.sleep(1800)  # 30분 대기
                
                # NewsData API (1시간마다)
                if self.newsdata_key and self.api_usage['newsdata_today'] < self.api_limits['newsdata']:
                    try:
                        await self._call_newsdata()
                        self.api_usage['newsdata_today'] += 1
                        logger.info(f"✅ NewsData API 호출 완료 ({self.api_usage['newsdata_today']}/{self.api_limits['newsdata']})")
                    except Exception as e:
                        logger.error(f"NewsData API 호출 실패: {str(e)[:100]}")
                
                await asyncio.sleep(1800)  # 30분 대기
                
                # Alpha Vantage (하루 1회)
                if self.alpha_vantage_key and self.api_usage['alpha_vantage_today'] < self.api_limits['alpha_vantage']:
                    try:
                        await self._call_alpha_vantage()
                        self.api_usage['alpha_vantage_today'] += 1
                        logger.info(f"✅ Alpha Vantage API 호출 완료 ({self.api_usage['alpha_vantage_today']}/{self.api_limits['alpha_vantage']})")
                    except Exception as e:
                        logger.error(f"Alpha Vantage API 호출 실패: {str(e)[:100]}")
                
                await asyncio.sleep(3600)  # 1시간 대기
                
            except Exception as e:
                logger.error(f"API 순환 사용 오류: {e}")
                await asyncio.sleep(3600)
    
    async def _parse_rss_feed(self, feed_info: Dict) -> List[Dict]:
        """RSS 피드 파싱 - 향상된 오류 처리"""
        articles = []
        try:
            async with self.session.get(
                feed_info['url'], 
                timeout=aiohttp.ClientTimeout(total=10),
                headers={'User-Agent': 'Mozilla/5.0 (compatible; NewsBot/1.0)'}
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # feedparser로 파싱
                    feed = feedparser.parse(content)
                    
                    if feed.entries:
                        # 가중치에 따라 처리할 기사 수 결정
                        limit = min(15, max(5, feed_info['weight']))
                        
                        for entry in feed.entries[:limit]:
                            try:
                                # 발행 시간 처리
                                pub_time = datetime.now().isoformat()
                                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                    pub_time = datetime(*entry.published_parsed[:6]).isoformat()
                                elif hasattr(entry, 'published'):
                                    # 문자열 시간 파싱 시도
                                    try:
                                        from dateutil import parser
                                        pub_time = parser.parse(entry.published).isoformat()
                                    except:
                                        pass
                                
                                article = {
                                    'title': entry.get('title', '').strip(),
                                    'description': entry.get('summary', '').strip()[:400],
                                    'url': entry.get('link', '').strip(),
                                    'source': feed_info['source'],
                                    'published_at': pub_time,
                                    'weight': feed_info['weight'],
                                    'category': feed_info['category']
                                }
                                
                                # 유효한 기사만 추가
                                if article['title'] and article['url']:
                                    # 최근 6시간 내 기사만
                                    try:
                                        article_time = datetime.fromisoformat(pub_time.replace('Z', ''))
                                        if datetime.now() - article_time < timedelta(hours=6):
                                            articles.append(article)
                                    except:
                                        articles.append(article)  # 시간 파싱 실패시 포함
                                        
                            except Exception as e:
                                logger.debug(f"기사 파싱 오류 {feed_info['source']}: {str(e)[:50]}")
                                continue
                    
                    if articles:
                        logger.debug(f"✅ {feed_info['source']}: {len(articles)}개 기사 수집")
                    
                elif response.status == 403:
                    logger.warning(f"⚠️  {feed_info['source']}: 접근 거부 (403)")
                elif response.status == 404:
                    logger.warning(f"⚠️  {feed_info['source']}: 피드 없음 (404)")
                elif response.status == 401:
                    logger.warning(f"⚠️  {feed_info['source']}: HTTP 401")
                else:
                    logger.warning(f"⚠️  {feed_info['source']}: HTTP {response.status}")
        
        except asyncio.TimeoutError:
            logger.debug(f"⏰ {feed_info['source']}: 타임아웃")
        except aiohttp.ClientConnectorError:
            logger.debug(f"🔌 {feed_info['source']}: 연결 실패")
        except Exception as e:
            logger.debug(f"❌ {feed_info['source']}: {str(e)[:50]}")
        
        return articles
    
    async def _call_newsapi(self):
        """NewsAPI 호출"""
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': '(trump AND bitcoin) OR (fed AND rate) OR (sec AND bitcoin) OR "bitcoin etf" OR (powell AND crypto)',
                'language': 'en',
                'sortBy': 'publishedAt',
                'apiKey': self.newsapi_key,
                'pageSize': 12,
                'from': (datetime.now() - timedelta(hours=1)).isoformat()
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('articles', [])
                    
                    processed = 0
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'title_ko': await self.translate_text(article.get('title', '')) if self.openai_client else article.get('title', ''),
                            'description': article.get('description', ''),
                            'url': article.get('url', ''),
                            'source': f"NewsAPI ({article.get('source', {}).get('name', 'Unknown')})",
                            'published_at': article.get('publishedAt', ''),
                            'weight': 10,
                            'category': 'api'
                        }
                        
                        if self._is_critical_news(formatted_article):
                            await self._trigger_emergency_alert(formatted_article)
                            processed += 1
                        elif self._is_important_news(formatted_article):
                            await self._add_to_news_buffer(formatted_article)
                            processed += 1
                    
                    if processed > 0:
                        logger.info(f"📰 NewsAPI: {processed}개 관련 뉴스 처리")
                else:
                    logger.warning(f"NewsAPI 응답 오류: {response.status}")
        
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
                'size': 8
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('results', [])
                    
                    processed = 0
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'title_ko': await self.translate_text(article.get('title', '')) if self.openai_client else article.get('title', ''),
                            'description': article.get('description', ''),
                            'url': article.get('link', ''),
                            'source': f"NewsData ({article.get('source_id', 'Unknown')})",
                            'published_at': article.get('pubDate', ''),
                            'weight': 9,
                            'category': 'api'
                        }
                        
                        if self._is_critical_news(formatted_article):
                            await self._trigger_emergency_alert(formatted_article)
                            processed += 1
                        elif self._is_important_news(formatted_article):
                            await self._add_to_news_buffer(formatted_article)
                            processed += 1
                    
                    if processed > 0:
                        logger.info(f"📰 NewsData: {processed}개 관련 뉴스 처리")
                else:
                    logger.warning(f"NewsData API 응답 오류: {response.status}")
        
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
                'limit': 6
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('feed', [])
                    
                    processed = 0
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'title_ko': await self.translate_text(article.get('title', '')) if self.openai_client else article.get('title', ''),
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
                            processed += 1
                        elif self._is_important_news(formatted_article):
                            await self._add_to_news_buffer(formatted_article)
                            processed += 1
                    
                    if processed > 0:
                        logger.info(f"📰 Alpha Vantage: {processed}개 관련 뉴스 처리")
                else:
                    logger.warning(f"Alpha Vantage API 응답 오류: {response.status}")
        
        except Exception as e:
            logger.error(f"Alpha Vantage API 호출 오류: {e}")
    
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
            logger.info(f"🔄 API 일일 사용량 리셋: NewsAPI {old_usage['newsapi_today']}→0, NewsData {old_usage['newsdata_today']}→0")
    
    def _is_critical_news(self, article: Dict) -> bool:
        """크리티컬 뉴스 판단 - 더 정확한 필터링"""
        # 제목과 설명 모두 체크 (한글 제목도 포함)
        content = (article.get('title', '') + ' ' + article.get('description', '') + ' ' + article.get('title_ko', '')).lower()
        
        for keyword in self.critical_keywords:
            if keyword.lower() in content:
                # 신뢰할 만한 소스에서만 (가중치 7 이상)
                if article.get('weight', 0) >= 7:
                    # 추가 검증: 부정적 키워드 제외
                    negative_filters = ['fake', 'rumor', 'unconfirmed', 'alleged', 'speculation', '루머', '추측', '미확인']
                    if not any(neg in content for neg in negative_filters):
                        logger.warning(f"🚨 크리티컬 뉴스 감지: {article.get('source', '')[:20]} - {article.get('title_ko', article.get('title', ''))[:50]}...")
                        return True
        
        return False
    
    def _is_important_news(self, article: Dict) -> bool:
        """중요 뉴스 판단 - 향상된 로직"""
        content = (article.get('title', '') + ' ' + article.get('description', '') + ' ' + article.get('title_ko', '')).lower()
        
        # 키워드 그룹별 점수 시스템
        crypto_keywords = ['bitcoin', 'btc', 'crypto', 'cryptocurrency', 'digital asset', 'blockchain', '비트코인', '암호화폐', '블록체인']
        finance_keywords = ['fed', 'federal reserve', 'interest rate', 'inflation', 'sec', 'regulation', 'monetary policy', '연준', '금리', '인플레이션', '규제']
        political_keywords = ['trump', 'biden', 'congress', 'government', 'policy', 'administration', 'white house', '트럼프', '바이든', '정부', '정책']
        market_keywords = ['market', 'trading', 'price', 'surge', 'crash', 'rally', 'dump', 'volatility', 'etf', '시장', '거래', '가격', '급등', '폭락', 'ETF']
        
        crypto_score = sum(1 for word in crypto_keywords if word in content)
        finance_score = sum(1 for word in finance_keywords if word in content)
        political_score = sum(1 for word in political_keywords if word in content)
        market_score = sum(1 for word in market_keywords if word in content)
        
        total_score = crypto_score + finance_score + political_score + market_score
        weight = article.get('weight', 0)
        category = article.get('category', '')
        
        # 판단 조건들
        conditions = [
            crypto_score >= 2,  # 암호화폐 키워드 2개 이상
            crypto_score >= 1 and (finance_score >= 1 or political_score >= 1),  # 암호화폐 + 금융/정치
            weight >= 9 and total_score >= 2,  # 고가중치 소스 + 관련 키워드
            category == 'crypto' and market_score >= 1,  # 암호화폐 소스 + 시장 키워드
            crypto_score >= 1 and 'etf' in content,  # ETF 관련
            finance_score >= 2 and weight >= 8,  # 금융 키워드 + 신뢰할만한 소스
        ]
        
        is_important = any(conditions)
        
        if is_important:
            logger.debug(f"📋 중요 뉴스: {article.get('source', '')[:15]} - 점수(C:{crypto_score},F:{finance_score},P:{political_score},M:{market_score})")
        
        return is_important
    
    async def _trigger_emergency_alert(self, article: Dict):
        """긴급 알림 트리거"""
        try:
            event = {
                'type': 'critical_news',
                'title': article.get('title_ko', article.get('title', ''))[:100],
                'description': article.get('description', '')[:250],
                'source': article.get('source', ''),
                'url': article.get('url', ''),
                'timestamp': datetime.now(),
                'severity': 'critical',
                'impact': self._determine_impact(article),
                'weight': article.get('weight', 5),
                'category': article.get('category', 'unknown'),
                'published_at': article.get('published_at', '')
            }
            
            # 데이터 컬렉터에 전달
            if hasattr(self, 'data_collector') and self.data_collector:
                self.data_collector.events_buffer.append(event)
            
            logger.critical(f"🚨 긴급 뉴스 알림: {article.get('source', '')} - {article.get('title_ko', article.get('title', ''))[:60]}")
            
        except Exception as e:
            logger.error(f"긴급 알림 처리 오류: {e}")
    
    async def _add_to_news_buffer(self, article: Dict):
        """뉴스 버퍼에 추가 - 향상된 중복 제거"""
        try:
            # 제목 기반 중복 체크 (더 정교하게)
            new_title = article.get('title', '').lower()
            new_title_ko = article.get('title_ko', '').lower()
            new_source = article.get('source', '').lower()
            
            # 제목의 핵심 단어들 추출
            import re
            new_keywords = set(re.findall(r'\b\w{4,}\b', new_title + ' ' + new_title_ko))  # 4글자 이상 단어만
            
            is_duplicate = False
            for existing in self.news_buffer:
                existing_title = existing.get('title', '').lower()
                existing_title_ko = existing.get('title_ko', '').lower()
                existing_source = existing.get('source', '').lower()
                existing_keywords = set(re.findall(r'\b\w{4,}\b', existing_title + ' ' + existing_title_ko))
                
                # 중복 판단: (키워드 유사도 70% 이상 AND 같은 소스) OR (키워드 유사도 90% 이상)
                if new_keywords and existing_keywords:
                    similarity = len(new_keywords & existing_keywords) / len(new_keywords | existing_keywords)
                    if (similarity > 0.7 and new_source == existing_source) or similarity > 0.9:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                self.news_buffer.append(article)
                
                # 버퍼 관리: 가중치, 카테고리, 시간 기준으로 정렬 후 상위 50개만 유지
                if len(self.news_buffer) > 50:
                    def sort_key(x):
                        weight = x.get('weight', 0)
                        category_priority = {'crypto': 4, 'api': 3, 'finance': 2, 'news': 1, 'tech': 1}
                        cat_score = category_priority.get(x.get('category', ''), 0)
                        pub_time = x.get('published_at', '')
                        return (weight, cat_score, pub_time)
                    
                    self.news_buffer.sort(key=sort_key, reverse=True)
                    self.news_buffer = self.news_buffer[:50]
            else:
                logger.debug(f"🔄 중복 뉴스 제외: {new_title_ko[:30] if new_title_ko else new_title[:30]}...")
        
        except Exception as e:
            logger.error(f"뉴스 버퍼 추가 오류: {e}")
    
    def _determine_impact(self, article: Dict) -> str:
        """뉴스 영향도 판단 - 더 세밀한 분석"""
        content = (article.get('title', '') + ' ' + article.get('description', '') + ' ' + article.get('title_ko', '')).lower()
        
        # 강한 악재 (즉시 매도 신호)
        strong_bearish = ['ban', 'banned', 'lawsuit', 'crash', 'crackdown', 'reject', 'rejected', 'hack', 'hacked', '금지', '규제', '소송', '폭락', '해킹']
        # 강한 호재 (즉시 매수 신호)
        strong_bullish = ['approval', 'approved', 'adoption', 'breakthrough', 'all-time high', 'ath', 'pump', '승인', '채택', '신고가']
        # 일반 악재
        bearish = ['concern', 'worry', 'decline', 'fall', 'drop', 'uncertainty', 'regulation', 'fine', '우려', '하락', '불확실']
        # 일반 호재
        bullish = ['growth', 'rise', 'increase', 'positive', 'rally', 'surge', 'investment', 'institutional', '상승', '증가', '긍정적', '투자']
        
        # 가중치 계산
        strong_bearish_count = sum(2 for word in strong_bearish if word in content)  # 가중치 2
        strong_bullish_count = sum(2 for word in strong_bullish if word in content)  # 가중치 2
        bearish_count = sum(1 for word in bearish if word in content)
        bullish_count = sum(1 for word in bullish if word in content)
        
        bearish_total = strong_bearish_count + bearish_count
        bullish_total = strong_bullish_count + bullish_count
        
        # 센티먼트 점수가 있는 경우 (Alpha Vantage)
        sentiment = article.get('sentiment', '').lower()
        if 'bearish' in sentiment:
            bearish_total += 1
        elif 'bullish' in sentiment:
            bullish_total += 1
        
        # 최종 판단
        if strong_bearish_count > 0:
            return "➖강한 악재"
        elif strong_bullish_count > 0:
            return "➕강한 호재"
        elif bearish_total > bullish_total + 1:  # 명확한 차이
            return "➖악재 예상"
        elif bullish_total > bearish_total + 1:  # 명확한 차이
            return "➕호재 예상"
        else:
            return "중립"
    
    async def get_recent_news(self, hours: int = 6) -> List[Dict]:
        """최근 뉴스 가져오기 - 향상된 필터링"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_news = []
            
            for article in self.news_buffer:
                try:
                    # 발행 시간 체크
                    if article.get('published_at'):
                        pub_time_str = article.get('published_at', '').replace('Z', '').replace('T', ' ')
                        # 다양한 시간 형식 처리
                        try:
                            if 'T' in article.get('published_at', ''):
                                pub_time = datetime.fromisoformat(pub_time_str)
                            else:
                                from dateutil import parser
                                pub_time = parser.parse(article.get('published_at', ''))
                            
                            if pub_time > cutoff_time:
                                recent_news.append(article)
                        except:
                            # 시간 파싱 실패시 최근 뉴스로 간주 (안전장치)
                            recent_news.append(article)
                    else:
                        recent_news.append(article)
                except:
                    recent_news.append(article)
            
            # 정렬 기준: 가중치 → 카테고리 → 시간
            def sort_key(x):
                weight = x.get('weight', 0)
                category_priority = {'crypto': 4, 'api': 3, 'finance': 2, 'news': 1, 'tech': 1}
                cat_score = category_priority.get(x.get('category', ''), 0)
                pub_time = x.get('published_at', '')
                return (weight, cat_score, pub_time)
            
            recent_news.sort(key=sort_key, reverse=True)
            
            # 카테고리별 균형 조정 (암호화폐 뉴스 우선, 하지만 다양성 유지)
            balanced_news = []
            crypto_count = 0
            other_count = 0
            
            for article in recent_news:
                category = article.get('category', '')
                if category == 'crypto' and crypto_count < 8:
                    balanced_news.append(article)
                    crypto_count += 1
                elif category != 'crypto' and other_count < 4:
                    balanced_news.append(article)
                    other_count += 1
                elif len(balanced_news) < 10:  # 총 10개 미만이면 추가
                    balanced_news.append(article)
            
            final_news = balanced_news[:12]  # 최대 12개
            
            logger.info(f"📰 최근 {hours}시간 뉴스 반환: 총 {len(final_news)}건 (암호화폐: {crypto_count}, 기타: {other_count})")
            return final_news
            
        except Exception as e:
            logger.error(f"최근 뉴스 조회 오류: {e}")
            return []
    
    async def close(self):
        """세션 종료"""
        try:
            if self.session:
                await self.session.close()
                logger.info("🔚 뉴스 수집기 세션 종료 완료")
        except Exception as e:
            logger.error(f"세션 종료 중 오류: {e}")
