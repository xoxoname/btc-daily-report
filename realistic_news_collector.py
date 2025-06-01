import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Set
import pytz
from bs4 import BeautifulSoup
import feedparser
import openai
import os
import hashlib
import re

logger = logging.getLogger(__name__)

class RealisticNewsCollector:
    def __init__(self, config):
        self.config = config
        self.session = None
        self.news_buffer = []
        self.emergency_alerts_sent = {}  # 중복 긴급 알림 방지용
        self.processed_news_hashes = set()  # 처리된 뉴스 해시 저장
        self.news_title_cache = {}  # 제목별 캐시
        self.company_news_count = {}  # 회사별 뉴스 카운트
        self.news_first_seen = {}  # 뉴스 최초 발견 시간
        
        # 번역 캐시 및 rate limit 관리 - 한도 증가
        self.translation_cache = {}  # 번역 캐시
        self.translation_count = 0  # 번역 횟수 추적
        self.last_translation_reset = datetime.now()
        self.max_translations_per_15min = 150  # 15분당 최대 번역 수 (대폭 증가)
        self.translation_reset_interval = 900  # 15분 (기존 30분에서 단축)
        
        # OpenAI 클라이언트 초기화 (번역용)
        self.openai_client = None
        if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY:
            self.openai_client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        
        # 모든 API 키들
        self.newsapi_key = getattr(config, 'NEWSAPI_KEY', None)
        self.newsdata_key = getattr(config, 'NEWSDATA_KEY', None)
        self.alpha_vantage_key = getattr(config, 'ALPHA_VANTAGE_KEY', None)
        
        # 크리티컬 키워드 (즉시 알림용) - 대폭 확장
        self.critical_keywords = [
            # 트럼프 관련 - 대폭 확장
            'trump', 'donald trump', 'president trump', 'trump administration', 'trump says', 'trump announces', 
            'trump declares', 'trump signs', 'trump executive order', 'trump policy', 'trump statement', 
            'trump twitter', 'trump social media', 'trump interview', 'trump speech', 'trump meeting',
            'trump china', 'trump tariff', 'trump trade', 'trump federal', 'trump bitcoin', 'trump crypto',
            '트럼프', '트럼프 대통령', '트럼프 정부', '트럼프 발언', '트럼프 정책', '트럼프 행정명령',
            
            # 미중 무역/관계 - 신규 추가
            'us china trade', 'china trade war', 'trade talks', 'trade deal', 'trade agreement',
            'china tariff', 'tariff war', 'xi jinping', 'biden china', 'us china relations',
            'trade dispute', 'trade negotiations', 'china exports', 'china imports',
            '미중 무역', '무역 전쟁', '무역 협상', '관세', '시진핑', '중국 무역',
            
            # 연준/금리 관련 - 확장
            'fed rate decision', 'fed raises', 'fed cuts', 'powell says', 'fomc decides', 'fed meeting',
            'interest rate hike', 'interest rate cut', 'monetary policy', 'federal reserve',
            'jerome powell', 'fed chair', 'fed statement', 'fed minutes', 'fed policy',
            'rate decision', 'rate hike', 'rate cut', 'inflation data', 'cpi data', 'ppi data',
            '연준', '연방준비제도', 'FOMC', '파월', '제롬 파월', '금리 인상', '금리 인하', '금리 결정',
            
            # 경제 지표 - 신규 추가
            'gdp growth', 'unemployment rate', 'jobs report', 'nonfarm payrolls', 'retail sales',
            'consumer confidence', 'manufacturing pmi', 'inflation rate', 'consumer price index',
            'producer price index', 'housing data', 'durable goods', 'trade balance',
            
            # SEC/규제 관련 - 확장
            'sec lawsuit bitcoin', 'sec sues', 'sec enforcement', 'sec charges bitcoin',
            'sec approves', 'sec rejects', 'sec bitcoin etf', 'gary gensler', 'sec chair',
            'cftc bitcoin', 'cftc crypto', 'regulatory approval', 'regulatory rejection',
            'SEC', 'CFTC', '게리 겐슬러', 'SEC 소송', 'SEC 규제', 'SEC 비트코인', 'SEC 승인', 'SEC 거부',
            
            # 규제/금지 관련 - 확장
            'china bans bitcoin', 'china crypto ban', 'government bans crypto', 'regulatory ban',
            'court blocks', 'federal court', 'supreme court crypto', 'legal ruling',
            'regulatory crackdown', 'crypto regulation', 'digital asset regulation',
            '중국 비트코인 금지', '정부 규제', '암호화폐 금지', '법원 판결', '규제 당국',
            
            # 시장 급변동 - 확장
            'bitcoin crash', 'crypto crash', 'market crash', 'flash crash', 'bitcoin plunge',
            'bitcoin surge', 'bitcoin rally', 'bitcoin breaks', 'bitcoin soars', 'bitcoin tumbles',
            'market meltdown', 'sell-off', 'massive liquidation', 'whale move', 'whale alert',
            '비트코인 폭락', '암호화폐 급락', '시장 붕괴', '비트코인 급등', '대량 청산',
            
            # ETF 관련 - 확장  
            'bitcoin etf approved', 'bitcoin etf rejected', 'etf decision', 'etf filing',
            'spot bitcoin etf', 'bitcoin etf launch', 'etf flows', 'etf inflows', 'etf outflows',
            'blackrock etf', 'fidelity etf', 'grayscale etf', 'ark etf',
            'ETF 승인', 'ETF 거부', 'ETF 결정', '현물 ETF', '비트코인 ETF',
            
            # 기업 비트코인 구매 - 확장
            'bought bitcoin', 'buys bitcoin', 'purchased bitcoin', 'bitcoin purchase', 'bitcoin acquisition',
            'tesla bitcoin', 'microstrategy bitcoin', 'square bitcoin', 'paypal bitcoin',
            'gamestop bitcoin', 'gme bitcoin', '$gme bitcoin', 'metaplanet bitcoin',
            'corporate bitcoin', 'institutional bitcoin', 'treasury bitcoin',
            '비트코인 구매', '비트코인 매입', '비트코인 투자', '비트코인 보유', '기업 비트코인',
            
            # 대량 거래/이동 - 확장
            'whale alert', 'large bitcoin transfer', 'bitcoin moved', 'btc transferred',
            'exchange inflow', 'exchange outflow', 'massive transfer', 'billion dollar move',
            'cold wallet', 'hot wallet', 'wallet movement', 'address activity',
            '고래 이동', '대량 이체', '비트코인 이동', '거래소 유입', '거래소 유출', '지갑 이동',
            
            # 해킹/보안 - 확장
            'exchange hacked', 'bitcoin stolen', 'crypto hack', 'security breach',
            'wallet compromised', 'private key stolen', 'smart contract exploit',
            'defi hack', 'bridge hack', 'cross-chain hack',
            '거래소 해킹', '비트코인 도난', '보안 사고', '지갑 해킹', '스마트 컨트랙트 해킹',
            
            # 글로벌 경제/정치 - 신규 대폭 추가
            'war', 'military action', 'geopolitical', 'sanctions', 'embargo',
            'energy crisis', 'oil price surge', 'oil price crash', 'opec decision',
            'bank crisis', 'banking system', 'financial crisis', 'recession warning',
            'stock market crash', 'dow jones crash', 'nasdaq crash', 's&p 500 crash',
            'dollar strength', 'dollar weakness', 'currency crisis', 'inflation shock',
            '전쟁', '지정학적', '제재', '유가', '오일쇼크', '금융위기', '경기침체', '달러',
            
            # 중앙은행 디지털화폐 - 신규 추가
            'cbdc', 'digital dollar', 'digital yuan', 'central bank digital currency',
            'fed digital currency', 'china digital currency', 'digital currency pilot',
            '중앙은행 디지털화폐', '디지털 달러', '디지털 위안',
            
            # 기술/채굴 관련 - 확장
            'bitcoin mining ban', 'mining crackdown', 'hash rate', 'mining difficulty',
            'energy consumption', 'carbon footprint', 'proof of stake', 'ethereum merge',
            '비트코인 채굴', '채굴 금지', '해시레이트', '에너지 소비',
        ]
        
        # 제외 키워드 (비트코인과 직접 관련 없는 것들) - 축소하여 더 많은 뉴스 포함
        self.exclude_keywords = [
            'how to mine', '집에서 채굴', 'mining at home',
            'price prediction tutorial', '가격 예측 방법'
        ]
        
        # 중요 기업 리스트 - 확장
        self.important_companies = [
            'tesla', 'microstrategy', 'square', 'block', 'paypal', 'mastercard', 'visa',
            'apple', 'google', 'amazon', 'meta', 'facebook', 'microsoft', 'netflix',
            'gamestop', 'gme', 'amc', 'blackrock', 'fidelity', 'jpmorgan', 'goldman',
            'morgan stanley', 'bank of america', 'wells fargo', 'citigroup',
            'samsung', 'lg', 'sk', 'kakao', 'naver', '삼성', '카카오', '네이버',
            'metaplanet', '메타플래닛', 'coinbase', 'binance', 'ftx', 'kraken'
        ]
        
        # RSS 피드 - 더 빠른 소스 추가
        self.rss_feeds = [
            # 실시간 뉴스 (최우선) - 신규 추가
            {'url': 'https://feeds.reuters.com/reuters/businessNews', 'source': 'Reuters Business', 'weight': 10, 'category': 'news'},
            {'url': 'https://feeds.reuters.com/Reuters/worldNews', 'source': 'Reuters World', 'weight': 10, 'category': 'news'},
            {'url': 'http://feeds.feedburner.com/ap/business', 'source': 'AP Business', 'weight': 10, 'category': 'news'},
            {'url': 'https://feeds.bloomberg.com/politics/news.rss', 'source': 'Bloomberg Politics', 'weight': 10, 'category': 'news'},
            {'url': 'https://feeds.bloomberg.com/economics/news.rss', 'source': 'Bloomberg Economics', 'weight': 10, 'category': 'news'},
            
            # 암호화폐 전문 (최우선)
            {'url': 'https://cointelegraph.com/rss', 'source': 'Cointelegraph', 'weight': 10, 'category': 'crypto'},
            {'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/', 'source': 'CoinDesk', 'weight': 10, 'category': 'crypto'},
            {'url': 'https://decrypt.co/feed', 'source': 'Decrypt', 'weight': 9, 'category': 'crypto'},
            {'url': 'https://bitcoinmagazine.com/.rss/full/', 'source': 'Bitcoin Magazine', 'weight': 9, 'category': 'crypto'},
            
            # 새로운 암호화폐 소스
            {'url': 'https://ambcrypto.com/feed/', 'source': 'AMBCrypto', 'weight': 8, 'category': 'crypto'},
            {'url': 'https://cryptopotato.com/feed/', 'source': 'CryptoPotato', 'weight': 8, 'category': 'crypto'},
            {'url': 'https://u.today/rss', 'source': 'U.Today', 'weight': 8, 'category': 'crypto'},
            {'url': 'https://cryptonews.com/news/feed/', 'source': 'Cryptonews', 'weight': 8, 'category': 'crypto'},
            
            # 일반 금융 - 빠른 소스 우선
            {'url': 'https://feeds.bloomberg.com/markets/news.rss', 'source': 'Bloomberg Markets', 'weight': 9, 'category': 'finance'},
            {'url': 'https://www.marketwatch.com/rss/topstories', 'source': 'MarketWatch', 'weight': 8, 'category': 'finance'},
            {'url': 'https://seekingalpha.com/feed.xml', 'source': 'Seeking Alpha', 'weight': 8, 'category': 'finance'},
            {'url': 'https://feeds.feedburner.com/InvestingcomAnalysis', 'source': 'Investing.com', 'weight': 8, 'category': 'finance'},
            {'url': 'https://www.fool.com/feeds/index.aspx', 'source': 'Motley Fool', 'weight': 7, 'category': 'finance'},
            
            # 정치/정책 뉴스 - 신규 추가
            {'url': 'https://feeds.washingtonpost.com/rss/politics', 'source': 'Washington Post Politics', 'weight': 9, 'category': 'politics'},
            {'url': 'https://feeds.npr.org/1014/rss.xml', 'source': 'NPR Politics', 'weight': 8, 'category': 'politics'},
            {'url': 'https://feeds.cnn.com/rss/edition_politics.rss', 'source': 'CNN Politics', 'weight': 8, 'category': 'politics'},
            
            # 일반 뉴스 (확실한 것들)
            {'url': 'https://rss.cnn.com/rss/edition.rss', 'source': 'CNN World', 'weight': 8, 'category': 'news'},
            {'url': 'http://feeds.bbci.co.uk/news/business/rss.xml', 'source': 'BBC Business', 'weight': 8, 'category': 'finance'},
            {'url': 'https://feeds.npr.org/1001/rss.xml', 'source': 'NPR News', 'weight': 7, 'category': 'news'},
            
            # 테크/비즈니스
            {'url': 'https://techcrunch.com/feed/', 'source': 'TechCrunch', 'weight': 7, 'category': 'tech'},
            {'url': 'https://www.wired.com/feed/rss', 'source': 'Wired', 'weight': 6, 'category': 'tech'},
            {'url': 'https://feeds.feedburner.com/venturebeat/SZYF', 'source': 'VentureBeat', 'weight': 7, 'category': 'tech'},
        ]
        
        # API 사용량 추적 - 더 자주 사용
        self.api_usage = {
            'newsapi_today': 0,
            'newsdata_today': 0,
            'alpha_vantage_today': 0,
            'last_reset': datetime.now().date()
        }
        
        # API 일일 한도 - 증가
        self.api_limits = {
            'newsapi': 25,  # 15 → 25
            'newsdata': 15,  # 8 → 15
            'alpha_vantage': 3  # 1 → 3
        }
        
        logger.info(f"뉴스 수집기 초기화 완료 - API 키 상태: NewsAPI={bool(self.newsapi_key)}, NewsData={bool(self.newsdata_key)}, AlphaVantage={bool(self.alpha_vantage_key)}")
        logger.info(f"📊 개선된 설정: RSS 15초 체크, 번역 15분당 {self.max_translations_per_15min}개, 크리티컬 키워드 {len(self.critical_keywords)}개")
    
    def _reset_translation_count_if_needed(self):
        """필요시 번역 카운트 리셋 - 15분마다"""
        now = datetime.now()
        if (now - self.last_translation_reset).total_seconds() > self.translation_reset_interval:
            old_count = self.translation_count
            self.translation_count = 0
            self.last_translation_reset = now
            logger.info(f"번역 카운트 리셋: {old_count} → 0 (15분 경과)")
    
    def _should_translate(self, article: Dict) -> bool:
        """뉴스를 번역해야 하는지 결정하는 함수 - 우선순위 조정"""
        # 이미 한글 제목이 있으면 번역 불필요
        if article.get('title_ko') and article['title_ko'] != article.get('title', ''):
            return False
        
        # 번역 우선순위 결정
        weight = article.get('weight', 0)
        category = article.get('category', '')
        
        # 1순위: 크리티컬 뉴스는 항상 번역
        if self._is_critical_news(article):
            return True
        
        # 2순위: 정치/뉴스 카테고리 + 높은 가중치 (트럼프, 미중 무역 등)
        if category in ['politics', 'news'] and weight >= 8:
            return True
        
        # 3순위: 중요 뉴스 + 높은 가중치
        if self._is_important_news(article) and weight >= 8:
            return True
        
        # 4순위: 암호화폐 카테고리 + 중요 뉴스
        if category == 'crypto' and self._is_important_news(article):
            return True
        
        # 5순위: API 뉴스 (NewsAPI, NewsData 등)
        if category == 'api' and weight >= 9:
            return True
        
        # 나머지는 번역 하지 않음
        return False
    
    async def translate_text(self, text: str, max_length: int = 100) -> str:
        """텍스트를 한국어로 번역 (Rate limit 처리 포함)"""
        if not self.openai_client:
            return text
        
        # 번역 카운트 리셋 체크
        self._reset_translation_count_if_needed()
        
        # 캐시 확인
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]
        
        # Rate limit 체크
        if self.translation_count >= self.max_translations_per_15min:
            logger.warning(f"번역 한도 초과: {self.translation_count}/{self.max_translations_per_15min} (15분)")
            return text[:max_length] + "..." if len(text) > max_length else text
        
        try:
            # 길이 제한
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional translator. Translate the following text to Korean in a natural and easy-to-understand way. Keep it concise and under 80 characters. If it's about cryptocurrency scams or hacks, make sure to clearly distinguish between 'losses decreasing' (positive) and 'scam amounts' (negative)."},
                    {"role": "user", "content": text}
                ],
                max_tokens=150,
                temperature=0.3
            )
            
            translated = response.choices[0].message.content.strip()
            # 번역 결과가 너무 길면 자르기
            if len(translated) > 80:
                translated = translated[:77] + "..."
            
            # 캐시 저장 및 카운트 증가
            self.translation_cache[cache_key] = translated
            self.translation_count += 1
            
            # 캐시 크기 제한
            if len(self.translation_cache) > 1000:
                # 가장 오래된 500개 제거
                keys_to_remove = list(self.translation_cache.keys())[:500]
                for key in keys_to_remove:
                    del self.translation_cache[key]
            
            return translated
            
        except openai.RateLimitError as e:
            logger.warning(f"OpenAI Rate limit 오류: {str(e)}")
            self.translation_count = self.max_translations_per_15min  # 더 이상 시도하지 않도록
            return text[:80] + "..." if len(text) > 80 else text
        except Exception as e:
            logger.warning(f"번역 실패: {str(e)[:50]}")
            return text[:80] + "..." if len(text) > 80 else text
    
    def _generate_content_hash(self, title: str, description: str = "") -> str:
        """뉴스 내용의 해시 생성 (중복 체크용) - 강화된 버전"""
        # 제목에서 숫자와 특수문자 제거하여 유사한 뉴스 감지
        clean_title = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title.lower())
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        # 회사명과 키워드 추출
        companies = []
        keywords = []
        
        for company in self.important_companies:
            if company.lower() in clean_title.lower():
                companies.append(company.lower())
        
        # 핵심 키워드 추출
        key_terms = ['bitcoin', 'btc', 'purchase', 'bought', 'buys', 'acquisition', '구매', '매입', 'first', '첫', 'trump', 'china', 'trade']
        for term in key_terms:
            if term in clean_title.lower():
                keywords.append(term)
        
        # 회사명 + 핵심 키워드로 해시 생성
        if companies and keywords:
            # 회사별로 하나의 해시만 생성 (숫자 무시)
            hash_content = f"{','.join(sorted(set(companies)))}_{','.join(sorted(set(keywords)))}"
        else:
            # 일반 뉴스는 전체 내용으로 해시
            hash_content = clean_title
        
        return hashlib.md5(hash_content.encode()).hexdigest()
    
    def _is_duplicate_emergency(self, article: Dict, time_window: int = 30) -> bool:
        """긴급 알림이 중복인지 확인 (30분 이내 유사 내용) - 시간 단축"""
        try:
            current_time = datetime.now()
            content_hash = self._generate_content_hash(
                article.get('title', ''), 
                article.get('description', '')
            )
            
            # 시간이 지난 알림 제거
            cutoff_time = current_time - timedelta(minutes=time_window)
            self.emergency_alerts_sent = {
                k: v for k, v in self.emergency_alerts_sent.items()
                if v > cutoff_time
            }
            
            # 중복 체크
            if content_hash in self.emergency_alerts_sent:
                logger.info(f"🔄 중복 긴급 알림 방지: {article.get('title', '')[:50]}...")
                return True
            
            # 새로운 알림 기록
            self.emergency_alerts_sent[content_hash] = current_time
            return False
            
        except Exception as e:
            logger.error(f"중복 체크 오류: {e}")
            return False
    
    def _is_similar_news(self, title1: str, title2: str) -> bool:
        """두 뉴스 제목이 유사한지 확인 - 더 엄격한 기준"""
        # 숫자와 특수문자 제거
        clean1 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title1.lower())
        clean2 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title2.lower())
        
        clean1 = re.sub(r'\s+', ' ', clean1).strip()
        clean2 = re.sub(r'\s+', ' ', clean2).strip()
        
        # 특정 회사의 비트코인 구매 뉴스인지 체크
        for company in self.important_companies:
            company_lower = company.lower()
            if company_lower in clean1 and company_lower in clean2:
                # 같은 회사의 비트코인 관련 뉴스면 중복으로 처리
                bitcoin_keywords = ['bitcoin', 'btc', '비트코인', 'purchase', 'bought', '구매', '매입']
                if any(keyword in clean1 for keyword in bitcoin_keywords) and \
                   any(keyword in clean2 for keyword in bitcoin_keywords):
                    return True
        
        # 단어 집합 비교
        words1 = set(clean1.split())
        words2 = set(clean2.split())
        
        if not words1 or not words2:
            return False
        
        # 교집합 비율 계산
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        if union == 0:
            return False
        
        similarity = intersection / union
        
        # 65% 이상 유사하면 중복으로 간주
        return similarity > 0.65
    
    def _is_recent_news(self, article: Dict, hours: int = 1) -> bool:
        """뉴스가 최근 것인지 확인 - 1시간 내로 더 엄격"""
        try:
            pub_time_str = article.get('published_at', '')
            if not pub_time_str:
                return True  # 시간 정보 없으면 일단 포함
            
            # 다양한 시간 형식 처리
            try:
                if 'T' in pub_time_str:
                    pub_time = datetime.fromisoformat(pub_time_str.replace('Z', ''))
                else:
                    from dateutil import parser
                    pub_time = parser.parse(pub_time_str)
                
                # UTC to local time if needed
                if pub_time.tzinfo is None:
                    pub_time = pytz.UTC.localize(pub_time)
                
                time_diff = datetime.now(pytz.UTC) - pub_time
                return time_diff.total_seconds() < (hours * 3600)
            except:
                return True  # 파싱 실패시 포함
        except:
            return True
    
    async def start_monitoring(self):
        """뉴스 모니터링 시작 - 속도 최적화"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),  # 타임아웃 단축 15→10초
                connector=aiohttp.TCPConnector(limit=150, limit_per_host=50)  # 연결수 증가
            )
        
        logger.info("🔍 뉴스 모니터링 시작 - 초고속 RSS + 적극적 API 사용")
        logger.info(f"📊 설정: RSS 15초 체크, 번역 15분당 최대 {self.max_translations_per_15min}개, 크리티컬 키워드 {len(self.critical_keywords)}개")
        
        # 회사별 뉴스 카운트 초기화
        self.company_news_count = {}
        
        tasks = [
            self.monitor_rss_feeds(),      # 메인: RSS (15초마다)
            self.monitor_reddit(),         # 보조: Reddit (10분마다)
            self.aggressive_api_rotation() # 적극적: API 순환 사용 (더 자주)
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def monitor_rss_feeds(self):
        """RSS 피드 모니터링 - 15초마다 초고속 체크"""
        while True:
            try:
                # 가중치가 높은 소스부터 처리
                sorted_feeds = sorted(self.rss_feeds, key=lambda x: x['weight'], reverse=True)
                successful_feeds = 0
                processed_articles = 0
                
                for feed_info in sorted_feeds:
                    try:
                        articles = await self._parse_rss_feed(feed_info)
                        
                        if articles:  # 성공적으로 기사를 가져온 경우
                            successful_feeds += 1
                            
                            for article in articles:
                                # 최신 뉴스만 처리 (1시간 이내로 단축)
                                if not self._is_recent_news(article, hours=1):
                                    continue
                                
                                # 번역 필요 여부 체크 (우선순위 높은 것만)
                                if self.openai_client and self._should_translate(article):
                                    article['title_ko'] = await self.translate_text(article['title'])
                                else:
                                    article['title_ko'] = article.get('title', '')
                                
                                # 가중치 8 이상이거나 정치/뉴스 카테고리는 크리티컬 체크
                                if feed_info['weight'] >= 8 or feed_info['category'] in ['politics', 'news']:
                                    if self._is_critical_news(article):
                                        # 중복 체크 후 알림
                                        if not self._is_duplicate_emergency(article):
                                            # 변동 예상률 추가
                                            article['expected_change'] = self._estimate_price_impact(article)
                                            await self._trigger_emergency_alert(article)
                                            processed_articles += 1
                                
                                # 모든 RSS는 중요 뉴스 체크
                                if self._is_important_news(article):
                                    await self._add_to_news_buffer(article)
                                    processed_articles += 1
                    
                    except Exception as e:
                        logger.warning(f"RSS 피드 일시 오류 {feed_info['source']}: {str(e)[:50]}")
                        continue
                
                logger.info(f"📰 RSS 스캔 완료: {successful_feeds}/{len(sorted_feeds)} 피드 성공, {processed_articles}개 처리 (번역: {self.translation_count}/{self.max_translations_per_15min})")
                await asyncio.sleep(15)  # 15초마다 전체 RSS 체크
                
            except Exception as e:
                logger.error(f"RSS 모니터링 전체 오류: {e}")
                await asyncio.sleep(30)
    
    def _estimate_price_impact(self, article: Dict) -> str:
        """뉴스의 예상 가격 영향 추정 - 트럼프/정치 이벤트 강화"""
        content = (article.get('title', '') + ' ' + article.get('description', '') + ' ' + article.get('title_ko', '')).lower()
        impact = article.get('impact', '')
        
        # 트럼프 관련 - 강화된 평가
        if 'trump' in content:
            if any(word in content for word in ['china', 'trade', 'tariff']):
                return '±2~5%'  # 미중 무역 관련
            elif any(word in content for word in ['bitcoin', 'crypto', 'digital asset']):
                return '+1~3%'  # 비트코인 직접 언급
            elif any(word in content for word in ['executive order', 'policy', 'announce']):
                return '±1~3%'  # 정책 발표
            else:
                return '±0.5~2%'  # 일반 트럼프 뉴스
        
        # 미중 무역/관계 - 신규 추가
        if any(word in content for word in ['us china trade', 'trade war', 'china tariff', 'xi jinping']):
            return '±1~4%'
        
        # Fed/금리 관련 - 강화
        if any(word in content for word in ['fed rate', 'powell', 'fomc', 'interest rate']):
            if any(word in content for word in ['hike', 'raise', 'increase']):
                return '-1~3%'  # 금리 인상
            elif any(word in content for word in ['cut', 'lower', 'decrease']):
                return '+2~5%'  # 금리 인하
            else:
                return '±1~2%'  # 일반 Fed 뉴스
        
        # 경제 지표 - 신규 추가
        if any(word in content for word in ['gdp', 'unemployment', 'inflation', 'cpi', 'ppi']):
            return '±0.5~2%'
        
        # 지정학적 리스크 - 신규 추가
        if any(word in content for word in ['war', 'military', 'sanctions', 'geopolitical']):
            return '±2~7%'  # 높은 변동성
        
        # 비트코인 우세/도미넌스 관련 - 중립으로 처리
        if any(word in content for word in ['dominance', '우세', '점유율']):
            return '±0.5%'  # 이미 반영된 움직임
        
        # 사기/해킹 관련 - 구분해서 처리
        if any(word in content for word in ['scam', 'fraud', 'hack', '사기', '해킹']):
            if 'decrease' in content or '감소' in content:
                return '±0.3%'  # 보안 개선은 간접적 호재
            else:
                return '-0.3~0.5%'  # 투자 심리 위축
        
        # 키워드별 예상 변동률 (더 현실적으로)
        strong_bullish_keywords = {
            'etf approved': '+2~4%',  # 기존 +5~10%에서 하향
            'bought bitcoin': '+0.5~1.5%',  # 기존 +2~5%에서 하향
            'bitcoin purchase': '+0.5~1.5%',
            'adoption': '+1~2%',  # 기존 +3~7%에서 하향
            'all-time high': '+2~5%',  # 기존 +5~15%에서 하향
            'institutional': '+0.5~1%'  # 기존 +2~4%에서 하향
        }
        
        strong_bearish_keywords = {
            'ban': '-2~5%',  # 기존 -5~10%에서 하향
            'lawsuit': '-1~3%',  # 기존 -3~7%에서 하향
            'hack': '-2~4%',  # 기존 -5~8%에서 하향
            'crash': '-5~10%',  # 기존 -10~20%에서 하향
            'reject': '-1~2%',  # 기존 -3~5%에서 하향
            'crackdown': '-2~4%'  # 기존 -5~10%에서 하향
        }
        
        moderate_keywords = {
            'concern': '±0.5~1%',  # 기존 ±1~3%에서 하향
            'uncertainty': '±1~2%',  # 기존 ±2~4%에서 하향
            'volatility': '±1~3%',  # 기존 ±3~5%에서 하향
            'meeting': '±0.3~0.5%',  # 기존 ±1~2%에서 하향
            'discussion': '±0.3~0.5%'  # 기존 ±1~2%에서 하향
        }
        
        # 예상 변동률 결정
        for keyword, change in strong_bullish_keywords.items():
            if keyword in content:
                return change
        
        for keyword, change in strong_bearish_keywords.items():
            if keyword in content:
                return change
        
        for keyword, change in moderate_keywords.items():
            if keyword in content:
                return change
        
        # 기본값 (더 보수적으로)
        if '호재' in impact:
            return '+0.3~1%'  # 기존 +1~3%에서 하향
        elif '악재' in impact:
            return '-0.3~1%'  # 기존 -1~3%에서 하향
        else:
            return '±0.3%'  # 기존 ±1~2%에서 하향
    
    async def monitor_reddit(self):
        """Reddit 모니터링"""
        reddit_subreddits = [
            {'name': 'Bitcoin', 'threshold': 200, 'weight': 8},
            {'name': 'CryptoCurrency', 'threshold': 400, 'weight': 7},
            {'name': 'investing', 'threshold': 800, 'weight': 6},
            {'name': 'wallstreetbets', 'threshold': 2000, 'weight': 5},
            {'name': 'politics', 'threshold': 1000, 'weight': 6},  # 신규 추가
            {'name': 'worldnews', 'threshold': 1500, 'weight': 6}  # 신규 추가
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
                                            'title_ko': post_data['title'],  # Reddit은 기본적으로 번역 생략
                                            'description': post_data.get('selftext', '')[:200],
                                            'url': f"https://reddit.com{post_data['permalink']}",
                                            'source': f"Reddit r/{sub_info['name']}",
                                            'published_at': datetime.fromtimestamp(post_data['created_utc']).isoformat(),
                                            'upvotes': post_data['ups'],
                                            'weight': sub_info['weight']
                                        }
                                        
                                        # Reddit도 중요도에 따라 번역
                                        if self._is_critical_news(article) and self.openai_client and self._should_translate(article):
                                            article['title_ko'] = await self.translate_text(article['title'])
                                        
                                        if self._is_critical_news(article):
                                            if not self._is_duplicate_emergency(article):
                                                article['expected_change'] = self._estimate_price_impact(article)
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
    
    async def aggressive_api_rotation(self):
        """적극적 API 순환 사용 - 더 자주 호출"""
        while True:
            try:
                self._reset_daily_usage()
                
                # NewsAPI (15분마다로 단축)
                if self.newsapi_key and self.api_usage['newsapi_today'] < self.api_limits['newsapi']:
                    try:
                        await self._call_newsapi()
                        self.api_usage['newsapi_today'] += 1
                        logger.info(f"✅ NewsAPI 호출 완료 ({self.api_usage['newsapi_today']}/{self.api_limits['newsapi']})")
                    except Exception as e:
                        logger.error(f"NewsAPI 호출 실패: {str(e)[:100]}")
                
                await asyncio.sleep(900)  # 15분 대기 (기존 30분에서 단축)
                
                # NewsData API (30분마다로 단축)
                if self.newsdata_key and self.api_usage['newsdata_today'] < self.api_limits['newsdata']:
                    try:
                        await self._call_newsdata()
                        self.api_usage['newsdata_today'] += 1
                        logger.info(f"✅ NewsData API 호출 완료 ({self.api_usage['newsdata_today']}/{self.api_limits['newsdata']})")
                    except Exception as e:
                        logger.error(f"NewsData API 호출 실패: {str(e)[:100]}")
                
                await asyncio.sleep(900)  # 15분 대기
                
                # Alpha Vantage (하루 3회로 증가)
                if self.alpha_vantage_key and self.api_usage['alpha_vantage_today'] < self.api_limits['alpha_vantage']:
                    try:
                        await self._call_alpha_vantage()
                        self.api_usage['alpha_vantage_today'] += 1
                        logger.info(f"✅ Alpha Vantage API 호출 완료 ({self.api_usage['alpha_vantage_today']}/{self.api_limits['alpha_vantage']})")
                    except Exception as e:
                        logger.error(f"Alpha Vantage API 호출 실패: {str(e)[:100]}")
                
                await asyncio.sleep(1800)  # 30분 대기
                
            except Exception as e:
                logger.error(f"API 순환 사용 오류: {e}")
                await asyncio.sleep(1800)
    
    async def _parse_rss_feed(self, feed_info: Dict) -> List[Dict]:
        """RSS 피드 파싱 - 향상된 오류 처리"""
        articles = []
        try:
            async with self.session.get(
                feed_info['url'], 
                timeout=aiohttp.ClientTimeout(total=8),  # 타임아웃 더 단축
                headers={'User-Agent': 'Mozilla/5.0 (compatible; NewsBot/1.0)'}
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # feedparser로 파싱
                    feed = feedparser.parse(content)
                    
                    if feed.entries:
                        # 가중치에 따라 처리할 기사 수 결정
                        limit = min(20, max(5, feed_info['weight']))  # 기사 수 증가
                        
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
                                    articles.append(article)
                                        
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
        """NewsAPI 호출 - 트럼프 및 정책 관련 키워드 대폭 확장"""
        try:
            # 검색어 대폭 강화
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': '(bitcoin AND (bought OR purchased OR buys OR "buying bitcoin" OR acquisition)) OR (gamestop AND bitcoin) OR (tesla AND bitcoin) OR (microstrategy AND bitcoin) OR "whale alert" OR (trump AND (bitcoin OR crypto OR tariff OR policy OR china OR trade)) OR (fed AND (rate OR powell OR fomc)) OR (sec AND bitcoin) OR "bitcoin etf" OR (court AND bitcoin) OR ("us china" AND trade) OR ("trade war") OR ("xi jinping") OR ("federal reserve") OR ("interest rate") OR ("monetary policy") OR ("inflation data") OR ("economic data")',
                'language': 'en',
                'sortBy': 'publishedAt',
                'apiKey': self.newsapi_key,
                'pageSize': 25,  # 기사 수 증가
                'from': (datetime.now() - timedelta(hours=1)).isoformat()  # 1시간 내로 단축
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('articles', [])
                    
                    processed = 0
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'title_ko': article.get('title', ''),  # 번역은 나중에 선택적으로
                            'description': article.get('description', ''),
                            'url': article.get('url', ''),
                            'source': f"NewsAPI ({article.get('source', {}).get('name', 'Unknown')})",
                            'published_at': article.get('publishedAt', ''),
                            'weight': 10,
                            'category': 'api'
                        }
                        
                        # 번역 필요성 체크
                        if self.openai_client and self._should_translate(formatted_article):
                            formatted_article['title_ko'] = await self.translate_text(formatted_article['title'])
                        
                        if self._is_critical_news(formatted_article):
                            if not self._is_duplicate_emergency(formatted_article):
                                formatted_article['expected_change'] = self._estimate_price_impact(formatted_article)
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
        """NewsData API 호출 - 키워드 확장"""
        try:
            url = "https://newsdata.io/api/1/news"
            params = {
                'apikey': self.newsdata_key,
                'q': 'bitcoin OR crypto OR "federal reserve" OR SEC OR gamestop OR tesla OR trump OR "us china trade" OR "trade war" OR tariff OR powell OR "interest rate"',
                'language': 'en',
                'category': 'business,politics,top',
                'size': 15  # 기사 수 증가
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('results', [])
                    
                    processed = 0
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'title_ko': article.get('title', ''),
                            'description': article.get('description', ''),
                            'url': article.get('link', ''),
                            'source': f"NewsData ({article.get('source_id', 'Unknown')})",
                            'published_at': article.get('pubDate', ''),
                            'weight': 9,
                            'category': 'api'
                        }
                        
                        # 번역 필요성 체크
                        if self.openai_client and self._should_translate(formatted_article):
                            formatted_article['title_ko'] = await self.translate_text(formatted_article['title'])
                        
                        if self._is_critical_news(formatted_article):
                            if not self._is_duplicate_emergency(formatted_article):
                                formatted_article['expected_change'] = self._estimate_price_impact(formatted_article)
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
        """Alpha Vantage API 호출 - 티커 확장"""
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': 'CRYPTO:BTC,COIN:MSTR,COIN:TSLA,COIN:GME,FOREX:USD,SPY,QQQ',  # 티커 확장
                'topics': 'financial_markets,economy_monetary,technology,earnings,mergers_and_acquisitions,ipo',  # 토픽 확장
                'apikey': self.alpha_vantage_key,
                'sort': 'LATEST',
                'limit': 15  # 기사 수 증가
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('feed', [])
                    
                    processed = 0
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'title_ko': article.get('title', ''),
                            'description': article.get('summary', ''),
                            'url': article.get('url', ''),
                            'source': f"Alpha Vantage ({article.get('source', 'Unknown')})",
                            'published_at': article.get('time_published', ''),
                            'weight': 10,
                            'category': 'api',
                            'sentiment': article.get('overall_sentiment_label', 'Neutral')
                        }
                        
                        # 번역 필요성 체크
                        if self.openai_client and self._should_translate(formatted_article):
                            formatted_article['title_ko'] = await self.translate_text(formatted_article['title'])
                        
                        if self._is_critical_news(formatted_article):
                            if not self._is_duplicate_emergency(formatted_article):
                                formatted_article['expected_change'] = self._estimate_price_impact(formatted_article)
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
            # 회사별 뉴스 카운트도 리셋
            self.company_news_count = {}
            # 번역 카운트 리셋
            self.translation_count = 0
            self.last_translation_reset = datetime.now()
            # 최초 발견 시간 정리
            self.news_first_seen = {}
            logger.info(f"🔄 API 일일 사용량 리셋: NewsAPI {old_usage['newsapi_today']}→0, NewsData {old_usage['newsdata_today']}→0, AlphaVantage {old_usage['alpha_vantage_today']}→0")
    
    def _is_critical_news(self, article: Dict) -> bool:
        """크리티컬 뉴스 판단 - 비트코인 직접 영향만 필터링"""
        # 제목과 설명 모두 체크 (한글 제목도 포함)
        content = (article.get('title', '') + ' ' + article.get('description', '') + ' ' + article.get('title_ko', '')).lower()
        
        # 제외 키워드 먼저 체크
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 비트코인 관련성 먼저 체크 - 더 엄격하게
        bitcoin_related = ['bitcoin', 'btc', '비트코인']
        crypto_general = ['crypto', 'cryptocurrency', '암호화폐']
        
        has_bitcoin = any(keyword in content for keyword in bitcoin_related)
        has_crypto = any(keyword in content for keyword in crypto_general)
        
        # 1. 비트코인 직접 언급이 있는 경우만 우선 처리
        if has_bitcoin:
            # 비트코인 + 기업 구매
            for company in self.important_companies:
                if company.lower() in content:
                    purchase_keywords = ['bought', 'buys', 'purchased', 'purchase', 'acquisition', '구매', '매입', '투자']
                    if any(keyword in content for keyword in purchase_keywords):
                        if any(char in content for char in ['$', '달러', 'dollar', 'million', 'billion']):
                            logger.warning(f"🚨 기업 비트코인 구매: {company} - {article.get('title', '')[:50]}...")
                            return True
            
            # 비트코인 + ETF
            if any(word in content for word in ['etf', 'etf approval', 'etf rejected', 'spot etf']):
                if article.get('weight', 0) >= 7:
                    logger.warning(f"🚨 비트코인 ETF 뉴스: {article.get('title', '')[:50]}...")
                    return True
            
            # 비트코인 + 규제
            if any(word in content for word in ['sec', 'regulation', 'ban', 'lawsuit', 'court', '규제', '금지']):
                if article.get('weight', 0) >= 7:
                    logger.warning(f"🚨 비트코인 규제 뉴스: {article.get('title', '')[:50]}...")
                    return True
        
        # 2. 트럼프 관련 - 비트코인/경제 관련만
        trump_keywords = ['trump', 'donald trump', 'president trump', '트럼프']
        if any(keyword in content for keyword in trump_keywords):
            # 트럼프 + 비트코인/암호화폐/경제 관련만
            trump_relevant = ['bitcoin', 'btc', 'crypto', 'cryptocurrency', '비트코인', '암호화폐', 
                            'tariff', 'trade', 'china', 'fed', 'federal reserve', 'economy', 
                            '관세', '무역', '중국', '연준', '경제', 'executive order', 'policy']
            if any(rel in content for rel in trump_relevant):
                if article.get('weight', 0) >= 7:
                    logger.warning(f"🚨 트럼프 경제/암호화폐 뉴스: {article.get('title', '')[:50]}...")
                    return True
            else:
                # 트럼프 관련이지만 경제/암호화폐와 무관하면 제외
                return False
        
        # 3. 미중 무역 - 비트코인 언급 또는 경제 전반 영향
        trade_keywords = ['us china trade', 'china trade war', 'trade talks', 'xi jinping', '미중 무역', '시진핑']
        if any(keyword in content for keyword in trade_keywords):
            # 글로벌 경제에 영향을 주는 규모의 뉴스만
            if any(word in content for word in ['billion', 'trillion', 'agreement', 'deal', '협정', '합의']) and article.get('weight', 0) >= 7:
                logger.warning(f"🚨 미중 무역 주요 뉴스: {article.get('title', '')[:50]}...")
                return True
            elif has_bitcoin or has_crypto:
                logger.warning(f"🚨 미중 무역 + 암호화폐: {article.get('title', '')[:50]}...")
                return True
            else:
                return False
        
        # 4. Fed/금리 관련 - 실제 결정이나 중요 발언만
        fed_keywords = ['fed rate decision', 'powell says', 'fomc decides', 'interest rate hike', 'interest rate cut', '연준 금리']
        fed_important = ['rate decision', 'rate hike', 'rate cut', 'fomc meeting', 'powell speech', '금리 결정', '금리 인상', '금리 인하']
        if any(keyword in content for keyword in fed_keywords) or any(keyword in content for keyword in fed_important):
            if article.get('weight', 0) >= 7:
                logger.warning(f"🚨 Fed 중요 뉴스: {article.get('title', '')[:50]}...")
                return True
        
        # 5. 기타 크리티컬 키워드 - 비트코인 관련성 있을 때만
        if has_bitcoin:
            bitcoin_critical = [
                'bitcoin crash', 'bitcoin surge', 'bitcoin rally', 'bitcoin plunge',
                'whale alert', 'large bitcoin transfer', 'bitcoin moved',
                'exchange hacked', 'bitcoin stolen', 'security breach',
                '비트코인 폭락', '비트코인 급등', '고래 이동', '거래소 해킹'
            ]
            
            for keyword in bitcoin_critical:
                if keyword.lower() in content:
                    if article.get('weight', 0) >= 6:
                        negative_filters = ['fake', 'rumor', 'unconfirmed', 'alleged', 'speculation', '루머', '추측', '미확인']
                        if not any(neg in content for neg in negative_filters):
                            logger.warning(f"🚨 비트코인 크리티컬: {article.get('title', '')[:50]}...")
                            return True
        
        # 6. 알트코인 뉴스는 비트코인 직접 영향 있을 때만
        altcoin_keywords = ['ethereum', 'eth', 'xrp', 'ripple', 'solana', 'sol', 'cardano', 'ada']
        if any(alt in content for alt in altcoin_keywords):
            # 알트코인 뉴스는 비트코인과 직접 연관성이 명시된 경우만
            if has_bitcoin and any(word in content for word in ['correlation', 'impact on bitcoin', 'bitcoin follows', '비트코인 영향']):
                if article.get('weight', 0) >= 8:  # 더 높은 가중치 요구
                    logger.warning(f"🚨 알트코인→비트코인 영향: {article.get('title', '')[:50]}...")
                    return True
            else:
                # 알트코인 단독 뉴스는 제외
                return False
        
        return False
    
    def _is_important_news(self, article: Dict) -> bool:
        """중요 뉴스 판단 - 비트코인 관련성 강화"""
        content = (article.get('title', '') + ' ' + article.get('description', '') + ' ' + article.get('title_ko', '')).lower()
        
        # 제외 키워드 체크
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 키워드 그룹별 점수 시스템
        bitcoin_keywords = ['bitcoin', 'btc', '비트코인']  # 비트코인 직접 언급
        crypto_keywords = ['crypto', 'cryptocurrency', 'digital asset', 'blockchain', '암호화폐', '블록체인']  # 암호화폐 일반
        finance_keywords = ['fed', 'federal reserve', 'interest rate', 'inflation', 'sec', 'regulation', 'monetary policy', '연준', '금리', '인플레이션', '규제']
        political_keywords = ['trump', 'biden', 'congress', 'government', 'policy', 'administration', 'white house', '트럼프', '바이든', '정부', '정책', 'china', 'trade']
        market_keywords = ['market', 'trading', 'price', 'surge', 'crash', 'rally', 'dump', 'volatility', 'etf', '시장', '거래', '가격', '급등', '폭락', 'ETF']
        company_keywords = self.important_companies
        
        bitcoin_score = sum(1 for word in bitcoin_keywords if word in content)
        crypto_score = sum(1 for word in crypto_keywords if word in content)
        finance_score = sum(1 for word in finance_keywords if word in content)
        political_score = sum(1 for word in political_keywords if word in content)
        market_score = sum(1 for word in market_keywords if word in content)
        company_score = sum(1 for word in company_keywords if word.lower() in content)
        
        total_score = bitcoin_score + crypto_score + finance_score + political_score + market_score + company_score
        weight = article.get('weight', 0)
        category = article.get('category', '')
        
        # 비트코인 직접 관련성 우선 - 더 엄격한 조건
        conditions = [
            # 비트코인 직접 언급 + 다른 요소
            bitcoin_score >= 1 and (finance_score >= 1 or political_score >= 1 or company_score >= 1),
            
            # 비트코인 + ETF
            bitcoin_score >= 1 and 'etf' in content,
            
            # 기업 + 비트코인 조합
            company_score >= 1 and bitcoin_score >= 1,
            
            # 암호화폐 전문 소스 + 비트코인
            category == 'crypto' and bitcoin_score >= 1 and weight >= 8,
            
            # 고가중치 소스 + 비트코인 언급
            weight >= 9 and bitcoin_score >= 1,
            
            # Fed/금리 + 높은 가중치 (비트코인 언급 없어도 중요)
            finance_score >= 2 and weight >= 8 and any(word in content for word in ['rate decision', 'fomc', 'powell', '금리 결정']),
            
            # 트럼프 + 경제/무역 관련 (비트코인 언급 없어도 시장 영향)
            political_score >= 1 and weight >= 8 and any(word in content for word in ['trump', '트럼프']) and 
            any(word in content for word in ['tariff', 'trade', 'china', 'economy', '관세', '무역', '중국', '경제']),
            
            # API 뉴스 + 비트코인/암호화폐
            category == 'api' and weight >= 9 and (bitcoin_score >= 1 or crypto_score >= 1),
        ]
        
        is_important = any(conditions)
        
        # 알트코인 단독 뉴스는 중요도 낮춤
        altcoin_keywords = ['ethereum', 'eth', 'xrp', 'ripple', 'solana', 'sol', 'cardano', 'ada']
        if any(alt in content for alt in altcoin_keywords) and bitcoin_score == 0:
            # 알트코인 뉴스는 ETF나 대규모 이벤트가 아니면 제외
            if not any(word in content for word in ['etf', 'billion', 'major', 'breakthrough', '십억', '대규모']):
                is_important = False
        
        if is_important:
            logger.debug(f"📋 중요 뉴스: {article.get('source', '')[:15]} - BTC:{bitcoin_score},C:{crypto_score},F:{finance_score},P:{political_score},M:{market_score},Co:{company_score}")
        
        return is_important
    
    async def _trigger_emergency_alert(self, article: Dict):
        """긴급 알림 트리거 - 첫 발견 시간 추적"""
        try:
            # 이미 처리된 뉴스인지 확인
            content_hash = self._generate_content_hash(article.get('title', ''), article.get('description', ''))
            if content_hash in self.processed_news_hashes:
                logger.info(f"🔄 이미 처리된 긴급 뉴스 스킵: {article.get('title', '')[:30]}...")
                return
            
            # 처리된 뉴스로 기록
            self.processed_news_hashes.add(content_hash)
            
            # 오래된 해시 정리 (1000개 초과시)
            if len(self.processed_news_hashes) > 1000:
                self.processed_news_hashes = set(list(self.processed_news_hashes)[-500:])
            
            # 최초 발견 시간 기록
            if content_hash not in self.news_first_seen:
                self.news_first_seen[content_hash] = datetime.now()
            
            event = {
                'type': 'critical_news',
                'title': article.get('title_ko', article.get('title', ''))[:100],
                'description': article.get('description', '')[:250],
                'source': article.get('source', ''),
                'url': article.get('url', ''),
                'timestamp': datetime.now(),
                'severity': 'critical',
                'impact': self._determine_impact(article),
                'expected_change': article.get('expected_change', '±0.3%'),
                'weight': article.get('weight', 5),
                'category': article.get('category', 'unknown'),
                'published_at': article.get('published_at', ''),
                'first_seen': self.news_first_seen[content_hash]
            }
            
            # 데이터 컬렉터에 전달
            if hasattr(self, 'data_collector') and self.data_collector:
                self.data_collector.events_buffer.append(event)
            
            logger.critical(f"🚨 긴급 뉴스 알림: {article.get('source', '')} - {article.get('title_ko', article.get('title', ''))[:60]} (예상: {event['expected_change']})")
            
        except Exception as e:
            logger.error(f"긴급 알림 처리 오류: {e}")
    
    async def _add_to_news_buffer(self, article: Dict):
        """뉴스 버퍼에 추가 - 회사별 카운트 제한"""
        try:
            # 제목 기반 중복 체크
            new_title = article.get('title', '').lower()
            new_title_ko = article.get('title_ko', '').lower()
            new_source = article.get('source', '').lower()
            
            # 이미 처리된 뉴스인지 확인
            content_hash = self._generate_content_hash(article.get('title', ''), article.get('description', ''))
            if content_hash in self.processed_news_hashes:
                logger.debug(f"🔄 이미 처리된 뉴스 스킵: {new_title[:30]}...")
                return
            
            # 회사별 뉴스 카운트 확인
            for company in self.important_companies:
                if company.lower() in new_title or company.lower() in new_title_ko:
                    # 비트코인 관련 뉴스인지 확인
                    bitcoin_keywords = ['bitcoin', 'btc', '비트코인', 'purchase', 'bought', '구매', '매입']
                    if any(keyword in new_title or keyword in new_title_ko for keyword in bitcoin_keywords):
                        # 해당 회사의 비트코인 뉴스가 이미 1개 이상인지 확인
                        if self.company_news_count.get(company.lower(), 0) >= 1:
                            logger.debug(f"🔄 {company} 비트코인 뉴스 이미 있음, 스킵: {new_title[:30]}...")
                            return
            
            # 버퍼에 있는 뉴스와 중복 체크
            is_duplicate = False
            for existing in self.news_buffer:
                # 동일한 뉴스 체크
                if self._is_similar_news(new_title, existing.get('title', '')):
                    is_duplicate = True
                    break
                
                # 한글 제목도 체크
                if new_title_ko and existing.get('title_ko', ''):
                    if self._is_similar_news(new_title_ko, existing.get('title_ko', '')):
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                self.news_buffer.append(article)
                self.processed_news_hashes.add(content_hash)
                
                # 회사별 카운트 업데이트
                for company in self.important_companies:
                    if company.lower() in new_title or company.lower() in new_title_ko:
                        bitcoin_keywords = ['bitcoin', 'btc', '비트코인', 'purchase', 'bought', '구매', '매입']
                        if any(keyword in new_title or keyword in new_title_ko for keyword in bitcoin_keywords):
                            self.company_news_count[company.lower()] = self.company_news_count.get(company.lower(), 0) + 1
                            logger.debug(f"📊 {company} 비트코인 뉴스 카운트: {self.company_news_count[company.lower()]}")
                
                # 버퍼 관리: 가중치, 카테고리, 시간 기준으로 정렬 후 상위 60개만 유지 (기존 50개에서 증가)
                if len(self.news_buffer) > 60:
                    def sort_key(x):
                        weight = x.get('weight', 0)
                        category_priority = {'crypto': 5, 'api': 4, 'politics': 3, 'finance': 2, 'news': 2, 'tech': 1}  # 정치 카테고리 추가
                        cat_score = category_priority.get(x.get('category', ''), 0)
                        pub_time = x.get('published_at', '')
                        return (weight, cat_score, pub_time)
                    
                    self.news_buffer.sort(key=sort_key, reverse=True)
                    self.news_buffer = self.news_buffer[:60]
            else:
                logger.debug(f"🔄 중복 뉴스 제외: {new_title_ko[:30] if new_title_ko else new_title[:30]}...")
        
        except Exception as e:
            logger.error(f"뉴스 버퍼 추가 오류: {e}")
    
    def _determine_impact(self, article: Dict) -> str:
        """뉴스 영향도 판단 - 비트코인 중심으로 재조정"""
        content = (article.get('title', '') + ' ' + article.get('description', '') + ' ' + article.get('title_ko', '')).lower()
        
        # 비트코인 직접 언급 확인
        has_bitcoin = any(word in content for word in ['bitcoin', 'btc', '비트코인'])
        
        # 트럼프 관련 - 경제/암호화폐 관련만
        if 'trump' in content:
            if any(word in content for word in ['bitcoin', 'crypto', 'digital asset', '비트코인', '암호화폐']):
                return "📈 약한 호재"  # 비트코인 직접 언급
            elif any(word in content for word in ['china', 'trade', 'tariff', '중국', '무역', '관세']):
                return "📊 시장 관심"  # 간접 영향
            elif any(word in content for word in ['economy', 'economic', '경제']):
                return "⚠️ 관련성 검토"  # 경제 관련
            else:
                return "⚠️ 비트코인 무관"  # 직접 관련 없음
        
        # 미중 무역/관계 - 글로벌 경제 영향만
        if any(word in content for word in ['us china trade', 'trade war', 'china tariff', 'xi jinping']):
            if has_bitcoin:
                return "📊 중간 변동성"
            elif any(word in content for word in ['billion', 'trillion', 'agreement', '협정']):
                return "⚠️ 간접 영향"  # 대규모 경제 이벤트
            else:
                return "⚠️ 제한적 영향"
        
        # Fed/금리 관련 - 비트코인에 직접 영향
        if any(word in content for word in ['fed rate', 'powell', 'fomc', 'interest rate']):
            if any(word in content for word in ['hike', 'raise', 'increase']):
                return "📉 중간 악재"  # 금리 인상
            elif any(word in content for word in ['cut', 'lower', 'decrease']):
                return "📈 중간 호재"  # 금리 인하
            else:
                return "⚠️ 통화 정책"
        
        # 기업 비트코인 구매
        if has_bitcoin:
            for company in self.important_companies:
                if company.lower() in content and any(word in content for word in ['bought', 'purchased', 'buys', 'bitcoin', '비트코인 구매', '매입']):
                    if any(word in content for word in ['billion', '억 달러', '십억']):
                        return "📈 중간 호재"
                    else:
                        return "📈 약한 호재"
        
        # 비트코인 관련성이 없는 경우
        if not has_bitcoin and not any(word in content for word in ['crypto', 'cryptocurrency', '암호화폐']):
            # 알트코인 뉴스
            if any(word in content for word in ['ethereum', 'eth', 'xrp', 'ripple']):
                return "⚠️ 알트코인 (BTC 무관)"
            # 일반 뉴스
            else:
                return "⚠️ 비트코인 무관"
        
        # 비트코인 우세/도미넌스 관련
        if any(word in content for word in ['dominance', '우세', '점유율']):
            return "⚠️ 중립 (이미 반영)"
        
        # 사기/해킹 관련 - 비트코인 관련만
        if has_bitcoin and any(word in content for word in ['scam', 'fraud', 'hack', '사기', '해킹']):
            if any(word in content for word in ['decrease', 'down', '감소', '줄어']):
                return "📈 약한 호재"  # 보안 개선
            else:
                return "📉 약한 악재"  # 사기 피해
        
        # 강한 악재/호재 (비트코인 관련)
        if has_bitcoin:
            strong_bearish = ['ban', 'banned', 'lawsuit', 'crash', 'crackdown', 'reject', 'rejected', 'hack', 'hacked', '금지', '규제', '소송', '폭락', '해킹']
            strong_bullish = ['approval', 'approved', 'adoption', 'breakthrough', 'all-time high', 'ath', '승인', '채택', '신고가']
            bearish = ['concern', 'worry', 'decline', 'fall', 'drop', 'uncertainty', 'regulation', 'fine', '우려', '하락', '불확실']
            bullish = ['growth', 'rise', 'increase', 'positive', 'rally', 'surge', 'investment', 'institutional', '상승', '증가', '긍정적', '투자']
            
            strong_bearish_count = sum(1 for word in strong_bearish if word in content)
            strong_bullish_count = sum(1 for word in strong_bullish if word in content)
            bearish_count = sum(1 for word in bearish if word in content)
            bullish_count = sum(1 for word in bullish if word in content)
            
            if strong_bearish_count >= 1:
                return "📉 중간 악재"
            elif strong_bullish_count >= 1:
                return "📈 중간 호재"
            elif bearish_count > bullish_count:
                return "📉 약한 악재"
            elif bullish_count > bearish_count:
                return "📈 약한 호재"
        
        # 기본값
        if has_bitcoin:
            return "⚠️ 중립"
        else:
            return "⚠️ 비트코인 무관"
    
    async def get_recent_news(self, hours: int = 6) -> List[Dict]:
        """최근 뉴스 가져오기 - 회사별 중복 제거 강화"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_news = []
            seen_titles = set()  # 중복 체크용
            company_count = {}  # 회사별 카운트
            
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
                                # 중복 체크
                                title_hash = self._generate_content_hash(article.get('title', ''), '')
                                if title_hash not in seen_titles:
                                    # 회사별 카운트 확인
                                    skip = False
                                    article_title = (article.get('title', '') + ' ' + article.get('title_ko', '')).lower()
                                    
                                    for company in self.important_companies:
                                        if company.lower() in article_title:
                                            bitcoin_keywords = ['bitcoin', 'btc', '비트코인', 'purchase', 'bought', '구매', '매입']
                                            if any(keyword in article_title for keyword in bitcoin_keywords):
                                                if company_count.get(company.lower(), 0) >= 1:
                                                    skip = True
                                                    break
                                                else:
                                                    company_count[company.lower()] = company_count.get(company.lower(), 0) + 1
                                    
                                    if not skip:
                                        recent_news.append(article)
                                        seen_titles.add(title_hash)
                        except:
                            # 시간 파싱 실패시 최근 뉴스로 간주 (안전장치)
                            title_hash = self._generate_content_hash(article.get('title', ''), '')
                            if title_hash not in seen_titles:
                                recent_news.append(article)
                                seen_titles.add(title_hash)
                    else:
                        title_hash = self._generate_content_hash(article.get('title', ''), '')
                        if title_hash not in seen_titles:
                            recent_news.append(article)
                            seen_titles.add(title_hash)
                except:
                    pass
            
            # 추가 중복 제거: 유사한 제목 제거
            final_news = []
            for article in recent_news:
                is_similar = False
                for final_article in final_news:
                    if self._is_similar_news(article.get('title', ''), final_article.get('title', '')):
                        is_similar = True
                        break
                
                if not is_similar:
                    final_news.append(article)
            
            # 정렬 기준: 가중치 → 카테고리 → 시간
            def sort_key(x):
                weight = x.get('weight', 0)
                category_priority = {'crypto': 5, 'api': 4, 'politics': 3, 'finance': 2, 'news': 2, 'tech': 1}  # 정치 카테고리 추가
                cat_score = category_priority.get(x.get('category', ''), 0)
                pub_time = x.get('published_at', '')
                return (weight, cat_score, pub_time)
            
            final_news.sort(key=sort_key, reverse=True)
            
            # 카테고리별 균형 조정 (정치/뉴스 카테고리 추가)
            balanced_news = []
            crypto_count = 0
            politics_count = 0  # 신규 추가
            other_count = 0
            
            for article in final_news:
                category = article.get('category', '')
                if category == 'crypto' and crypto_count < 8:
                    balanced_news.append(article)
                    crypto_count += 1
                elif category in ['politics', 'news'] and politics_count < 4:  # 정치/뉴스 카테고리 추가
                    balanced_news.append(article)
                    politics_count += 1
                elif category not in ['crypto', 'politics', 'news'] and other_count < 3:
                    balanced_news.append(article)
                    other_count += 1
                elif len(balanced_news) < 12:  # 총 12개 미만이면 추가
                    balanced_news.append(article)
            
            final_result = balanced_news[:15]  # 최대 15개로 증가
            
            logger.info(f"📰 최근 {hours}시간 뉴스 반환: 총 {len(final_result)}건 (암호화폐: {crypto_count}, 정치: {politics_count}, 기타: {other_count})")
            return final_result
            
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
