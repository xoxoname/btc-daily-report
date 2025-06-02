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
        
        # 번역 캐시 및 rate limit 관리
        self.translation_cache = {}  # 번역 캐시
        self.translation_count = 0  # 번역 횟수 추적
        self.last_translation_reset = datetime.now()
        self.max_translations_per_15min = 100  # 15분당 최대 번역 수
        self.translation_reset_interval = 900  # 15분
        
        # OpenAI 클라이언트 초기화 (번역용)
        self.openai_client = None
        if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY:
            self.openai_client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        
        # 모든 API 키들
        self.newsapi_key = getattr(config, 'NEWSAPI_KEY', None)
        self.newsdata_key = getattr(config, 'NEWSDATA_KEY', None)
        self.alpha_vantage_key = getattr(config, 'ALPHA_VANTAGE_KEY', None)
        
        # 크리티컬 키워드 (비트코인 직접 영향만)
        self.critical_keywords = [
            # 비트코인 ETF 관련 (최우선)
            'bitcoin etf approved', 'bitcoin etf rejected', 'spot bitcoin etf', 'etf decision',
            'blackrock bitcoin etf', 'fidelity bitcoin etf', 'ark bitcoin etf',
            'SEC 비트코인 ETF', 'ETF 승인', 'ETF 거부',
            
            # 기업 비트코인 구매 (직접적)
            'tesla bought bitcoin', 'microstrategy bought bitcoin', 'bought bitcoin',
            'gamestop bitcoin purchase', 'metaplanet bitcoin', 'corporate bitcoin purchase',
            'bitcoin acquisition', 'adds bitcoin', 'bitcoin investment',
            '비트코인 구매', '비트코인 매입', 'BTC 구매',
            
            # 국가/은행 채택
            'central bank bitcoin', 'russia bitcoin', 'sberbank bitcoin', 'bitcoin bonds',
            'government bitcoin', 'country adopts bitcoin', 'bitcoin legal tender',
            '중앙은행 비트코인', '러시아 비트코인', '비트코인 채권',
            
            # 비트코인 규제 (직접적)
            'sec bitcoin lawsuit', 'bitcoin ban', 'bitcoin regulation', 'bitcoin lawsuit',
            'china bans bitcoin', 'government bans bitcoin', 'court bitcoin',
            'regulatory approval bitcoin', 'regulatory rejection bitcoin',
            'SEC 비트코인', '비트코인 금지', '비트코인 규제',
            
            # 비트코인 시장 급변동
            'bitcoin crash', 'bitcoin surge', 'bitcoin breaks', 'bitcoin plunge',
            'bitcoin all time high', 'bitcoin ath', 'bitcoin tumbles', 'bitcoin soars',
            '비트코인 폭락', '비트코인 급등', '비트코인 급락',
            
            # 대량 비트코인 이동
            'whale alert bitcoin', 'large bitcoin transfer', 'bitcoin moved exchange',
            'massive bitcoin', 'billion bitcoin', 'btc whale',
            '고래 비트코인', '대량 비트코인', 'BTC 이동',
            
            # 비트코인 해킹/보안
            'bitcoin stolen', 'bitcoin hack', 'exchange hacked bitcoin',
            'bitcoin security breach', 'btc stolen',
            '비트코인 도난', '비트코인 해킹', '거래소 해킹',
            
            # Fed 금리 결정 (비트코인 영향)
            'fed rate decision bitcoin', 'fomc bitcoin', 'interest rate bitcoin',
            'powell bitcoin', 'federal reserve bitcoin',
            '연준 비트코인', '금리 비트코인'
        ]
        
        # 제외 키워드 (비트코인과 무관한 것들)
        self.exclude_keywords = [
            'how to mine', '집에서 채굴', 'mining at home', 'mining tutorial',
            'price prediction tutorial', '가격 예측 방법', 'technical analysis tutorial',
            'altcoin', 'ethereum', 'ripple', 'cardano', 'solana', 'dogecoin', 'shiba',
            'defi', 'nft', 'web3', 'metaverse', 'gamefi',
            'stock market', 'dow jones', 'nasdaq', 's&p 500',
            'oil price', 'gold price', 'commodity',
            'sports', 'entertainment', 'celebrity'
        ]
        
        # 중요 기업 리스트 (비트코인 보유/관련)
        self.important_companies = [
            'tesla', 'microstrategy', 'square', 'block', 'paypal', 'mastercard',
            'gamestop', 'gme', 'blackrock', 'fidelity', 'ark invest',
            'coinbase', 'binance', 'kraken', 'bitget',
            'metaplanet', '메타플래닛', '테슬라', '마이크로스트래티지',
            'sberbank', '스베르방크', 'jpmorgan', 'goldman sachs'
        ]
        
        # RSS 피드 - 암호화폐 전문 소스 위주
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
            {'url': 'https://www.watcher.guru/news/feed', 'source': 'Watcher.Guru', 'weight': 9, 'category': 'crypto'},  # WatcherGuru 추가
            
            # 금융 (Fed/규제 관련)
            {'url': 'https://feeds.bloomberg.com/markets/news.rss', 'source': 'Bloomberg Markets', 'weight': 9, 'category': 'finance'},
            {'url': 'https://feeds.bloomberg.com/economics/news.rss', 'source': 'Bloomberg Economics', 'weight': 8, 'category': 'finance'},
            {'url': 'https://www.marketwatch.com/rss/topstories', 'source': 'MarketWatch', 'weight': 7, 'category': 'finance'},
            {'url': 'https://feeds.reuters.com/reuters/businessNews', 'source': 'Reuters Business', 'weight': 8, 'category': 'news'},
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
            'newsapi': 20,
            'newsdata': 10,
            'alpha_vantage': 2
        }
        
        logger.info(f"뉴스 수집기 초기화 완료 - 비트코인 전용 필터링 강화")
        logger.info(f"📊 설정: RSS 15초 체크, 번역 15분당 {self.max_translations_per_15min}개, 크리티컬 키워드 {len(self.critical_keywords)}개")
    
    def _reset_translation_count_if_needed(self):
        """필요시 번역 카운트 리셋"""
        now = datetime.now()
        if (now - self.last_translation_reset).total_seconds() > self.translation_reset_interval:
            old_count = self.translation_count
            self.translation_count = 0
            self.last_translation_reset = now
            if old_count > 0:
                logger.info(f"번역 카운트 리셋: {old_count} → 0")
    
    def _should_translate(self, article: Dict) -> bool:
        """뉴스를 번역해야 하는지 결정"""
        # 이미 한글 제목이 있으면 번역 불필요
        if article.get('title_ko') and article['title_ko'] != article.get('title', ''):
            return False
        
        # 크리티컬 뉴스는 항상 번역
        if self._is_critical_news(article):
            return True
        
        # 높은 가중치 + 암호화폐 카테고리
        if article.get('weight', 0) >= 8 and article.get('category') == 'crypto':
            return True
        
        # API 뉴스
        if article.get('category') == 'api' and article.get('weight', 0) >= 9:
            return True
        
        return False
    
    async def translate_text(self, text: str, max_length: int = 400) -> str:
        """텍스트를 한국어로 번역 - 완벽히 자연스럽게"""
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
            logger.warning(f"번역 한도 초과: {self.translation_count}/{self.max_translations_per_15min}")
            return text
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system", 
                        "content": """당신은 한국의 블록체인 전문 기자입니다. 비트코인 뉴스를 한국 독자들이 즉시 이해할 수 있도록 매끄러운 한국어로 번역합니다.

번역 원칙:
1. 한국 경제 뉴스처럼 자연스럽게 번역
2. 핵심 정보를 명확하게 전달:
   - 주체 (기업/인물/국가)
   - 행동 (매입, 매도, 발표, 승인 등)
   - 규모 (금액, 수량)
   - 영향/의미
3. 전문 용어 처리:
   - MicroStrategy → 마이크로스트래티지
   - Tesla → 테슬라  
   - Sberbank → 스베르방크
   - BlackRock → 블랙록
   - SEC → SEC (미국 증권거래위원회)
   - ETF → ETF
   - Bitcoin bonds → 비트코인 연계 채권
4. 자연스러운 한국어 문장 구조 사용
5. 불필요한 수식어 제거, 핵심만 전달

예시:
"MicroStrategy buys 500 BTC" → "마이크로스트래티지, 비트코인 500개 추가 매입"
"Russia's Sberbank launches Bitcoin-linked bonds" → "러시아 최대 은행 스베르방크, 비트코인 연계 채권 출시"
"SEC approves spot Bitcoin ETF" → "SEC, 현물 비트코인 ETF 승인""""
                    },
                    {
                        "role": "user", 
                        "content": f"다음 비트코인 뉴스를 자연스러운 한국어로 번역해주세요 (최대 {max_length}자):\n\n{text}"
                    }
                ],
                max_tokens=600,
                temperature=0.3
            )
            
            translated = response.choices[0].message.content.strip()
            
            # 길이 체크
            if len(translated) > max_length:
                # 의미가 끊기지 않도록 문장 단위로 자르기
                sentences = translated.split('.')
                result = ""
                for sentence in sentences:
                    if len(result + sentence + ".") <= max_length - 3:
                        result += sentence + "."
                    else:
                        break
                translated = result.strip()
                if not translated:
                    translated = translated[:max_length-3] + "..."
            
            # 캐시 저장 및 카운트 증가
            self.translation_cache[cache_key] = translated
            self.translation_count += 1
            
            # 캐시 크기 제한
            if len(self.translation_cache) > 1000:
                keys_to_remove = list(self.translation_cache.keys())[:500]
                for key in keys_to_remove:
                    del self.translation_cache[key]
            
            return translated
            
        except openai.RateLimitError:
            logger.warning("OpenAI Rate limit 도달")
            self.translation_count = self.max_translations_per_15min
            return text
        except Exception as e:
            logger.warning(f"번역 실패: {str(e)[:50]}")
            # GPT-3.5로 폴백
            try:
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system", 
                            "content": "비트코인 뉴스를 자연스러운 한국어로 번역합니다. 기업명은 한국식으로 (테슬라, 마이크로스트래티지 등), 금액과 행동을 명확히 표현해주세요."
                        },
                        {
                            "role": "user", 
                            "content": f"다음을 한국어로 번역 (최대 {max_length}자):\n{text}"
                        }
                    ],
                    max_tokens=400,
                    temperature=0.3
                )
                
                translated = response.choices[0].message.content.strip()
                if len(translated) > max_length:
                    translated = translated[:max_length-3] + "..."
                
                self.translation_cache[cache_key] = translated
                self.translation_count += 1
                
                return translated
            except:
                return text
    
    async def summarize_article(self, title: str, description: str, max_length: int = 500) -> str:
        """기사 내용을 한국어로 상세 요약"""
        if not self.openai_client or not description:
            return ""
        
        # 이미 짧으면 그대로 반환
        if len(description) <= 200:
            return ""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system", 
                        "content": """당신은 한국의 비트코인 투자 전문가입니다. 비트코인 뉴스의 핵심을 한국 투자자들이 즉시 활용할 수 있도록 상세히 요약합니다.

요약 원칙:
1. 투자 판단에 필요한 모든 정보 포함:
   - 누가: 기업/인물/국가명 (한국식 표기)
   - 무엇을: 구체적 행동 (매입, 매도, 발표, 출시 등)
   - 얼마나: 정확한 금액/수량
   - 언제: 시기 정보
   - 왜: 배경과 이유
   - 영향: 시장에 미칠 영향
2. 투자자 관점에서 중요도 순으로 정리
3. 구체적인 숫자와 사실 위주
4. 불확실한 추측은 제외
5. 한국 투자자가 바로 이해할 수 있는 표현 사용

예시:
"마이크로스트래티지가 12월 15일 580,955개의 비트코인을 보유하게 되었다. 이는 약 270억 달러 규모로, 전체 비트코인 공급량의 2.7%에 해당한다. 평균 매입가는 46,500달러이며, 현재 시세 대비 30% 수익을 보고 있다."
"""
                    },
                    {
                        "role": "user", 
                        "content": f"다음 비트코인 뉴스를 한국어로 상세 요약해주세요 (최대 {max_length}자):\n\n제목: {title}\n\n내용: {description[:1500]}"
                    }
                ],
                max_tokens=800,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            
            if len(summary) > max_length:
                sentences = summary.split('.')
                result = ""
                for sentence in sentences:
                    if len(result + sentence + ".") <= max_length - 3:
                        result += sentence + "."
                    else:
                        break
                summary = result.strip() or summary[:max_length-3] + "..."
            
            return summary
            
        except Exception as e:
            logger.warning(f"요약 실패: {str(e)[:50]}")
            # GPT-3.5로 폴백
            try:
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system", 
                            "content": "비트코인 뉴스의 핵심을 한국어로 요약합니다. 누가, 무엇을, 얼마나, 왜를 중심으로 구체적인 정보를 포함해주세요."
                        },
                        {
                            "role": "user", 
                            "content": f"요약 (최대 {max_length}자):\n제목: {title}\n내용: {description[:1000]}"
                        }
                    ],
                    max_tokens=600,
                    temperature=0.3
                )
                
                summary = response.choices[0].message.content.strip()
                if len(summary) > max_length:
                    summary = summary[:max_length-3] + "..."
                
                return summary
            except:
                return description[:max_length] + "..." if len(description) > max_length else description
    
    def _extract_company_from_content(self, title: str, description: str = "") -> str:
        """컨텐츠에서 기업명 추출"""
        content = (title + " " + description).lower()
        
        # 중요 기업 확인
        found_companies = []
        for company in self.important_companies:
            if company.lower() in content:
                # 원래 대소문자 유지
                for original in self.important_companies:
                    if original.lower() == company.lower():
                        found_companies.append(original)
                        break
        
        # 첫 번째 발견된 기업 반환
        if found_companies:
            return found_companies[0]
        
        # 특정 패턴으로 기업명 찾기
        patterns = [
            r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:bought|purchased|acquired|adds)',
            r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+bitcoin',
            r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+BTC',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, title + " " + description)
            if matches:
                # 알려진 기업명인지 확인
                for match in matches:
                    if len(match) > 2 and match.lower() not in ['the', 'and', 'for', 'with']:
                        return match
        
        return ""
    
    def _generate_content_hash(self, title: str, description: str = "") -> str:
        """뉴스 내용의 해시 생성 (중복 체크용) - 더 엄격하게"""
        # 제목과 설명에서 핵심 내용 추출
        content = f"{title} {description[:200]}".lower()
        
        # 숫자 정규화 (580,955 -> 580955)
        content = re.sub(r'[\d,]+', lambda m: m.group(0).replace(',', ''), content)
        
        # 회사명 정규화
        companies_found = []
        for company in self.important_companies:
            if company.lower() in content:
                companies_found.append(company.lower())
        
        # 액션 키워드 추출
        action_keywords = []
        actions = ['bought', 'purchased', 'acquired', 'adds', 'buys', 'sells', 'sold', 
                  'announced', 'launches', 'approves', 'rejects', 'bans']
        for action in actions:
            if action in content:
                action_keywords.append(action)
        
        # BTC 수량 추출
        btc_amounts = re.findall(r'(\d+(?:,\d+)*)\s*(?:btc|bitcoin)', content)
        
        # 고유 식별자 생성
        unique_parts = []
        if companies_found:
            unique_parts.append('_'.join(sorted(companies_found)))
        if action_keywords:
            unique_parts.append('_'.join(sorted(action_keywords)))
        if btc_amounts:
            unique_parts.append('_'.join(btc_amounts))
        
        # 해시 생성
        if unique_parts:
            hash_content = '|'.join(unique_parts)
        else:
            # 핵심 단어만 추출
            words = re.findall(r'\b[a-z]{4,}\b', content)
            important_words = [w for w in words if w not in ['that', 'this', 'with', 'from', 'have', 'been', 'their', 'about']]
            hash_content = ' '.join(sorted(important_words[:10]))
        
        return hashlib.md5(hash_content.encode()).hexdigest()
    
    def _is_duplicate_emergency(self, article: Dict, time_window: int = 120) -> bool:
        """긴급 알림이 중복인지 확인 (120분 이내) - 더 엄격하게"""
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
            
            # 제목 유사성 체크
            current_title = article.get('title', '').lower()
            for sent_hash in self.emergency_alerts_sent:
                # 이미 전송된 뉴스들과 유사성 체크
                if self._calculate_title_similarity(current_title, sent_hash) > 0.8:
                    logger.info(f"🔄 유사 긴급 알림 방지: {article.get('title', '')[:50]}...")
                    return True
            
            # 새로운 알림 기록
            self.emergency_alerts_sent[content_hash] = current_time
            return False
            
        except Exception as e:
            logger.error(f"중복 체크 오류: {e}")
            return False
    
    def _calculate_title_similarity(self, title1: str, title2_hash: str) -> float:
        """제목 유사도 계산"""
        # 간단한 단어 기반 유사도
        words1 = set(re.findall(r'\b\w+\b', title1.lower()))
        # 해시는 직접 비교 불가하므로 기본값 반환
        return 0.0
    
    def _is_similar_news(self, title1: str, title2: str) -> bool:
        """두 뉴스 제목이 유사한지 확인"""
        # 숫자와 특수문자 제거
        clean1 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title1.lower())
        clean2 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title2.lower())
        
        clean1 = re.sub(r'\s+', ' ', clean1).strip()
        clean2 = re.sub(r'\s+', ' ', clean2).strip()
        
        # 특정 회사의 비트코인 구매 뉴스인지 체크
        for company in self.important_companies:
            company_lower = company.lower()
            if company_lower in clean1 and company_lower in clean2:
                bitcoin_keywords = ['bitcoin', 'btc', '비트코인', 'purchase', 'bought']
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
        
        similarity = intersection / union if union > 0 else 0
        
        # 70% 이상 유사하면 중복
        return similarity > 0.7
    
    def _is_recent_news(self, article: Dict, hours: int = 2) -> bool:
        """뉴스가 최근 것인지 확인 - 2시간 이내"""
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
    
    async def start_monitoring(self):
        """뉴스 모니터링 시작"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=aiohttp.TCPConnector(limit=100, limit_per_host=30)
            )
        
        logger.info("🔍 비트코인 전용 뉴스 모니터링 시작")
        
        # 회사별 뉴스 카운트 초기화
        self.company_news_count = {}
        
        tasks = [
            self.monitor_rss_feeds(),      # RSS (15초마다)
            self.monitor_reddit(),         # Reddit (10분마다)
            self.aggressive_api_rotation() # API 순환 사용
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def monitor_rss_feeds(self):
        """RSS 피드 모니터링 - 15초마다"""
        while True:
            try:
                # 가중치가 높은 소스부터 처리
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
                                
                                # 비트코인 관련성 체크
                                if not self._is_bitcoin_related(article):
                                    continue
                                
                                # 기업명 추출
                                company = self._extract_company_from_content(
                                    article.get('title', ''),
                                    article.get('description', '')
                                )
                                if company:
                                    article['company'] = company
                                
                                # 번역 필요 여부 체크
                                if self.openai_client and self._should_translate(article):
                                    article['title_ko'] = await self.translate_text(article['title'])
                                    
                                    # 요약 생성 (크리티컬 뉴스만)
                                    if self._is_critical_news(article):
                                        summary = await self.summarize_article(
                                            article['title'],
                                            article.get('description', '')
                                        )
                                        if summary:
                                            article['summary'] = summary
                                else:
                                    article['title_ko'] = article.get('title', '')
                                
                                # 크리티컬 뉴스 체크
                                if self._is_critical_news(article):
                                    if not self._is_duplicate_emergency(article):
                                        article['expected_change'] = self._estimate_price_impact(article)
                                        await self._trigger_emergency_alert(article)
                                        processed_articles += 1
                                
                                # 중요 뉴스는 버퍼에 추가
                                elif self._is_important_news(article):
                                    await self._add_to_news_buffer(article)
                                    processed_articles += 1
                    
                    except Exception as e:
                        logger.warning(f"RSS 피드 오류 {feed_info['source']}: {str(e)[:50]}")
                        continue
                
                if processed_articles > 0:
                    logger.info(f"📰 RSS 스캔 완료: {successful_feeds}개 피드, {processed_articles}개 비트코인 뉴스")
                
                await asyncio.sleep(15)  # 15초마다
                
            except Exception as e:
                logger.error(f"RSS 모니터링 오류: {e}")
                await asyncio.sleep(30)
    
    def _is_bitcoin_related(self, article: Dict) -> bool:
        """비트코인 직접 관련성 체크"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 제외 키워드 먼저 체크
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 비트코인 직접 언급
        bitcoin_keywords = ['bitcoin', 'btc', '비트코인']
        has_bitcoin = any(keyword in content for keyword in bitcoin_keywords)
        
        if has_bitcoin:
            return True
        
        # 암호화폐 일반 + 중요 내용
        crypto_keywords = ['crypto', 'cryptocurrency', '암호화폐']
        has_crypto = any(keyword in content for keyword in crypto_keywords)
        
        if has_crypto:
            # ETF, SEC, 규제 등 중요 키워드와 함께 나오면 포함
            important_terms = ['etf', 'sec', 'regulation', 'ban', 'approval', 'court', 'lawsuit', 'bonds', 'russia', 'sberbank']
            if any(term in content for term in important_terms):
                return True
        
        # Fed 금리 결정 (비트코인 언급 없어도 중요)
        fed_keywords = ['fed rate decision', 'fomc decides', 'interest rate hike', 'interest rate cut', 'powell announces']
        if any(keyword in content for keyword in fed_keywords):
            return True
        
        return False
    
    def _estimate_price_impact(self, article: Dict) -> str:
        """뉴스의 예상 가격 영향 추정 - 명확하게 상승/하락 표시"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # ETF 관련
        if 'etf approved' in content or 'etf approval' in content:
            return '📈 상승 +1~3%'
        elif 'etf rejected' in content or 'etf rejection' in content:
            return '📉 하락 -1~3%'
        elif 'etf' in content:
            return '⚡ 변동 ±0.5~1%'
        
        # 기업/국가 구매
        for entity in ['tesla', 'microstrategy', 'gamestop', 'blackrock', 'russia', 'sberbank']:
            if entity in content and any(word in content for word in ['bought', 'purchased', 'buys', 'adds', 'launches', 'bonds']):
                if 'billion' in content:
                    return '📈 상승 +0.5~2%'
                elif 'million' in content:
                    return '📈 상승 +0.3~1%'
                else:
                    return '📈 상승 +0.2~0.5%'
        
        # 규제/금지
        if any(word in content for word in ['ban', 'banned', 'prohibit']):
            if 'china' in content:
                return '📉 하락 -2~4%'
            else:
                return '📉 하락 -1~3%'
        elif 'lawsuit' in content or 'sue' in content:
            return '📉 하락 -0.5~2%'
        elif 'regulation' in content:
            return '⚡ 변동 ±0.5~1.5%'
        
        # Fed 금리
        if any(word in content for word in ['rate hike', 'rates higher', 'hawkish']):
            return '📉 하락 -0.5~2%'
        elif any(word in content for word in ['rate cut', 'rates lower', 'dovish']):
            return '📈 상승 +0.5~2%'
        elif 'fed' in content or 'fomc' in content:
            return '⚡ 변동 ±0.3~1%'
        
        # 시장 급변동
        if any(word in content for word in ['crash', 'plunge', 'tumble']):
            return '📉 하락 -3~5%'
        elif any(word in content for word in ['surge', 'soar', 'rally', 'all time high', 'ath']):
            return '📈 상승 +2~4%'
        
        # 해킹/보안
        if any(word in content for word in ['hack', 'stolen', 'breach']):
            if 'billion' in content:
                return '📉 하락 -1~3%'
            else:
                return '📉 하락 -0.5~1.5%'
        
        # 고래 이동
        if 'whale' in content or 'large transfer' in content:
            if 'exchange' in content:
                return '⚡ 변동 ±0.5~1.5%'
            else:
                return '⚡ 변동 ±0.2~0.5%'
        
        # 기본값
        return '⚡ 변동 ±0.3~1%'
    
    def _is_critical_news(self, article: Dict) -> bool:
        """크리티컬 뉴스 판단 - 비트코인 직접 영향만"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 비트코인 관련성 체크
        if not self._is_bitcoin_related(article):
            return False
        
        # 제외 키워드 체크
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 가중치 체크 (8 이상만)
        if article.get('weight', 0) < 8:
            return False
        
        # 크리티컬 키워드 체크
        for keyword in self.critical_keywords:
            if keyword.lower() in content:
                # 부정적 필터 (루머, 추측 등)
                negative_filters = ['rumor', 'speculation', 'unconfirmed', 'fake', 'false', '루머', '추측', '미확인']
                if any(neg in content for neg in negative_filters):
                    continue
                
                logger.info(f"🚨 크리티컬 뉴스 감지: {keyword} - {article.get('title', '')[:50]}...")
                return True
        
        # 추가 크리티컬 패턴
        critical_patterns = [
            ('bitcoin', 'billion', 'bought'),  # 대규모 구매
            ('bitcoin', 'court', 'ruling'),     # 법원 판결
            ('bitcoin', 'sec', 'decision'),     # SEC 결정
            ('bitcoin', 'ban', 'government'),   # 정부 금지
            ('bitcoin', 'etf', 'launch'),       # ETF 출시
            ('fed', 'rate', 'decision'),        # Fed 금리 결정
            ('russia', 'bitcoin', 'bonds'),     # 러시아 비트코인 채권
            ('sberbank', 'bitcoin'),            # 스베르방크 비트코인
        ]
        
        for pattern in critical_patterns:
            if all(word in content for word in pattern):
                logger.info(f"🚨 크리티컬 패턴 감지: {pattern} - {article.get('title', '')[:50]}...")
                return True
        
        return False
    
    def _is_important_news(self, article: Dict) -> bool:
        """중요 뉴스 판단"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 비트코인 관련성 체크
        if not self._is_bitcoin_related(article):
            return False
        
        # 제외 키워드 체크
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 가중치와 카테고리 체크
        weight = article.get('weight', 0)
        category = article.get('category', '')
        
        # 조건들
        conditions = [
            # 암호화폐 전문 소스 + 비트코인 언급
            category == 'crypto' and any(word in content for word in ['bitcoin', 'btc']) and weight >= 7,
            
            # 금융 소스 + 비트코인 또는 중요 키워드
            category == 'finance' and weight >= 7 and (
                any(word in content for word in ['bitcoin', 'btc', 'crypto']) or
                any(word in content for word in ['fed', 'rate', 'regulation', 'sec'])
            ),
            
            # API 뉴스 + 높은 가중치
            category == 'api' and weight >= 9,
            
            # 기업 + 비트코인
            any(company.lower() in content for company in self.important_companies) and 
            any(word in content for word in ['bitcoin', 'btc', 'crypto']),
        ]
        
        return any(conditions)
    
    def _determine_impact(self, article: Dict) -> str:
        """뉴스 영향도 판단 - 간단명료하게"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        expected_change = self._estimate_price_impact(article)
        
        # 예상 변동률에 따른 영향도
        if '📈' in expected_change:
            if any(x in expected_change for x in ['3%', '4%', '5%']):
                return "📈 강한 호재"
            else:
                return "📈 호재"
        elif '📉' in expected_change:
            if any(x in expected_change for x in ['3%', '4%', '5%']):
                return "📉 강한 악재"
            else:
                return "📉 악재"
        else:
            return "⚡ 변동성"
    
    async def _trigger_emergency_alert(self, article: Dict):
        """긴급 알림 트리거"""
        try:
            # 이미 처리된 뉴스인지 확인
            content_hash = self._generate_content_hash(article.get('title', ''), article.get('description', ''))
            if content_hash in self.processed_news_hashes:
                return
            
            # 처리된 뉴스로 기록
            self.processed_news_hashes.add(content_hash)
            
            # 오래된 해시 정리
            if len(self.processed_news_hashes) > 1000:
                self.processed_news_hashes = set(list(self.processed_news_hashes)[-500:])
            
            # 최초 발견 시간 기록
            if content_hash not in self.news_first_seen:
                self.news_first_seen[content_hash] = datetime.now()
            
            event = {
                'type': 'critical_news',
                'title': article.get('title', ''),
                'title_ko': article.get('title_ko', article.get('title', '')),
                'description': article.get('description', '')[:1400],  # 1400자 유지
                'summary': article.get('summary', ''),  # 요약 추가
                'company': article.get('company', ''),  # 기업명 추가
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
            
            logger.critical(f"🚨 비트코인 긴급 뉴스: {event['impact']} - {event['title_ko'][:60]}... (예상: {event['expected_change']})")
            
        except Exception as e:
            logger.error(f"긴급 알림 처리 오류: {e}")
    
    async def _add_to_news_buffer(self, article: Dict):
        """뉴스 버퍼에 추가"""
        try:
            # 중복 체크
            content_hash = self._generate_content_hash(article.get('title', ''), article.get('description', ''))
            if content_hash in self.processed_news_hashes:
                return
            
            # 제목 유사성 체크
            new_title = article.get('title', '').lower()
            for existing in self.news_buffer:
                if self._is_similar_news(new_title, existing.get('title', '')):
                    return
            
            # 회사별 뉴스 카운트 체크
            for company in self.important_companies:
                if company.lower() in new_title:
                    bitcoin_keywords = ['bitcoin', 'btc', 'purchase', 'bought']
                    if any(keyword in new_title for keyword in bitcoin_keywords):
                        if self.company_news_count.get(company.lower(), 0) >= 2:  # 회사당 최대 2개
                            return
                        self.company_news_count[company.lower()] = self.company_news_count.get(company.lower(), 0) + 1
            
            # 버퍼에 추가
            self.news_buffer.append(article)
            self.processed_news_hashes.add(content_hash)
            
            # 버퍼 크기 관리 (최대 50개)
            if len(self.news_buffer) > 50:
                # 가중치와 시간 기준 정렬
                self.news_buffer.sort(key=lambda x: (x.get('weight', 0), x.get('published_at', '')), reverse=True)
                self.news_buffer = self.news_buffer[:50]
        
        except Exception as e:
            logger.error(f"뉴스 버퍼 추가 오류: {e}")
    
    async def monitor_reddit(self):
        """Reddit 모니터링"""
        reddit_subreddits = [
            {'name': 'Bitcoin', 'threshold': 500, 'weight': 8},
            {'name': 'CryptoCurrency', 'threshold': 1000, 'weight': 7},
            {'name': 'BitcoinMarkets', 'threshold': 300, 'weight': 8},
        ]
        
        while True:
            try:
                for sub_info in reddit_subreddits:
                    try:
                        url = f"https://www.reddit.com/r/{sub_info['name']}/hot.json?limit=10"
                        
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
                                            'description': post_data.get('selftext', '')[:1400],
                                            'url': f"https://reddit.com{post_data['permalink']}",
                                            'source': f"Reddit r/{sub_info['name']}",
                                            'published_at': datetime.fromtimestamp(post_data['created_utc']).isoformat(),
                                            'upvotes': post_data['ups'],
                                            'weight': sub_info['weight']
                                        }
                                        
                                        if self._is_bitcoin_related(article):
                                            # 기업명 추출
                                            company = self._extract_company_from_content(
                                                article['title'],
                                                article.get('description', '')
                                            )
                                            if company:
                                                article['company'] = company
                                            
                                            if self._is_critical_news(article):
                                                if self._should_translate(article):
                                                    article['title_ko'] = await self.translate_text(article['title'])
                                                    summary = await self.summarize_article(
                                                        article['title'],
                                                        article.get('description', '')
                                                    )
                                                    if summary:
                                                        article['summary'] = summary
                                                
                                                if not self._is_duplicate_emergency(article):
                                                    article['expected_change'] = self._estimate_price_impact(article)
                                                    await self._trigger_emergency_alert(article)
                    
                    except Exception as e:
                        logger.warning(f"Reddit 오류 {sub_info['name']}: {str(e)[:50]}")
                
                await asyncio.sleep(600)  # 10분마다
                
            except Exception as e:
                logger.error(f"Reddit 모니터링 오류: {e}")
                await asyncio.sleep(900)
    
    async def aggressive_api_rotation(self):
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
                        logger.error(f"NewsAPI 오류: {str(e)[:100]}")
                
                await asyncio.sleep(900)  # 15분 대기
                
                # NewsData API
                if self.newsdata_key and self.api_usage['newsdata_today'] < self.api_limits['newsdata']:
                    try:
                        await self._call_newsdata()
                        self.api_usage['newsdata_today'] += 1
                        logger.info(f"✅ NewsData 호출 ({self.api_usage['newsdata_today']}/{self.api_limits['newsdata']})")
                    except Exception as e:
                        logger.error(f"NewsData 오류: {str(e)[:100]}")
                
                await asyncio.sleep(900)  # 15분 대기
                
                # Alpha Vantage
                if self.alpha_vantage_key and self.api_usage['alpha_vantage_today'] < self.api_limits['alpha_vantage']:
                    try:
                        await self._call_alpha_vantage()
                        self.api_usage['alpha_vantage_today'] += 1
                        logger.info(f"✅ Alpha Vantage 호출 ({self.api_usage['alpha_vantage_today']}/{self.api_limits['alpha_vantage']})")
                    except Exception as e:
                        logger.error(f"Alpha Vantage 오류: {str(e)[:100]}")
                
                await asyncio.sleep(1800)  # 30분 대기
                
            except Exception as e:
                logger.error(f"API 순환 오류: {e}")
                await asyncio.sleep(1800)
    
    async def _parse_rss_feed(self, feed_info: Dict) -> List[Dict]:
        """RSS 피드 파싱"""
        articles = []
        try:
            async with self.session.get(
                feed_info['url'], 
                timeout=aiohttp.ClientTimeout(total=8),
                headers={'User-Agent': 'Mozilla/5.0 (compatible; BitcoinNewsBot/1.0)'}
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    if feed.entries:
                        limit = min(15, max(5, feed_info['weight']))
                        
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
                                    'description': entry.get('summary', '').strip()[:1400],  # 1400자 유지
                                    'url': entry.get('link', '').strip(),
                                    'source': feed_info['source'],
                                    'published_at': pub_time,
                                    'weight': feed_info['weight'],
                                    'category': feed_info.get('category', 'unknown')
                                }
                                
                                if article['title'] and article['url']:
                                    articles.append(article)
                                        
                            except Exception as e:
                                logger.debug(f"기사 파싱 오류: {str(e)[:50]}")
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
                'q': '(bitcoin OR btc) AND (etf OR sec OR "bought bitcoin" OR "tesla bitcoin" OR "microstrategy bitcoin" OR "bitcoin ban" OR "bitcoin regulation" OR "bitcoin hack" OR "whale alert" OR "fed rate" OR "russia bitcoin" OR "sberbank")',
                'language': 'en',
                'sortBy': 'publishedAt',
                'apiKey': self.newsapi_key,
                'pageSize': 50,
                'from': (datetime.now() - timedelta(hours=2)).isoformat()
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('articles', [])
                    
                    processed = 0
                    for article in articles:
                        formatted_article = {
                            'title': article.get('title', ''),
                            'title_ko': article.get('title', ''),
                            'description': article.get('description', '')[:1400],
                            'url': article.get('url', ''),
                            'source': f"NewsAPI ({article.get('source', {}).get('name', 'Unknown')})",
                            'published_at': article.get('publishedAt', ''),
                            'weight': 9,
                            'category': 'api'
                        }
                        
                        if self._is_bitcoin_related(formatted_article):
                            # 기업명 추출
                            company = self._extract_company_from_content(
                                formatted_article['title'],
                                formatted_article.get('description', '')
                            )
                            if company:
                                formatted_article['company'] = company
                            
                            if self._should_translate(formatted_article):
                                formatted_article['title_ko'] = await self.translate_text(formatted_article['title'])
                                if self._is_critical_news(formatted_article):
                                    summary = await self.summarize_article(
                                        formatted_article['title'],
                                        formatted_article.get('description', '')
                                    )
                                    if summary:
                                        formatted_article['summary'] = summary
                            
                            if self._is_critical_news(formatted_article):
                                if not self._is_duplicate_emergency(formatted_article):
                                    formatted_article['expected_change'] = self._estimate_price_impact(formatted_article)
                                    await self._trigger_emergency_alert(formatted_article)
                                processed += 1
                            elif self._is_important_news(formatted_article):
                                await self._add_to_news_buffer(formatted_article)
                                processed += 1
                    
                    if processed > 0:
                        logger.info(f"📰 NewsAPI: {processed}개 비트코인 뉴스 처리")
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
                'q': 'bitcoin OR btc OR "bitcoin etf" OR "bitcoin regulation" OR "russia bitcoin" OR "sberbank bitcoin"',
                'language': 'en',
                'category': 'business,top',
                'size': 30
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
                            'description': article.get('description', '')[:1400],
                            'url': article.get('link', ''),
                            'source': f"NewsData ({article.get('source_id', 'Unknown')})",
                            'published_at': article.get('pubDate', ''),
                            'weight': 8,
                            'category': 'api'
                        }
                        
                        if self._is_bitcoin_related(formatted_article):
                            # 기업명 추출
                            company = self._extract_company_from_content(
                                formatted_article['title'],
                                formatted_article.get('description', '')
                            )
                            if company:
                                formatted_article['company'] = company
                            
                            if self._should_translate(formatted_article):
                                formatted_article['title_ko'] = await self.translate_text(formatted_article['title'])
                                if self._is_critical_news(formatted_article):
                                    summary = await self.summarize_article(
                                        formatted_article['title'],
                                        formatted_article.get('description', '')
                                    )
                                    if summary:
                                        formatted_article['summary'] = summary
                            
                            if self._is_critical_news(formatted_article):
                                if not self._is_duplicate_emergency(formatted_article):
                                    formatted_article['expected_change'] = self._estimate_price_impact(formatted_article)
                                    await self._trigger_emergency_alert(formatted_article)
                                processed += 1
                            elif self._is_important_news(formatted_article):
                                await self._add_to_news_buffer(formatted_article)
                                processed += 1
                    
                    if processed > 0:
                        logger.info(f"📰 NewsData: {processed}개 비트코인 뉴스 처리")
                else:
                    logger.warning(f"NewsData 응답 오류: {response.status}")
        
        except Exception as e:
            logger.error(f"NewsData 호출 오류: {e}")
    
    async def _call_alpha_vantage(self):
        """Alpha Vantage API 호출"""
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': 'CRYPTO:BTC',
                'topics': 'financial_markets,technology,earnings',
                'apikey': self.alpha_vantage_key,
                'sort': 'LATEST',
                'limit': 20
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
                            'description': article.get('summary', '')[:1400],
                            'url': article.get('url', ''),
                            'source': f"Alpha Vantage ({article.get('source', 'Unknown')})",
                            'published_at': article.get('time_published', ''),
                            'weight': 9,
                            'category': 'api',
                            'sentiment': article.get('overall_sentiment_label', 'Neutral')
                        }
                        
                        if self._is_bitcoin_related(formatted_article):
                            # 기업명 추출
                            company = self._extract_company_from_content(
                                formatted_article['title'],
                                formatted_article.get('description', '')
                            )
                            if company:
                                formatted_article['company'] = company
                            
                            if self._should_translate(formatted_article):
                                formatted_article['title_ko'] = await self.translate_text(formatted_article['title'])
                                if self._is_critical_news(formatted_article):
                                    summary = await self.summarize_article(
                                        formatted_article['title'],
                                        formatted_article.get('description', '')
                                    )
                                    if summary:
                                        formatted_article['summary'] = summary
                            
                            if self._is_critical_news(formatted_article):
                                if not self._is_duplicate_emergency(formatted_article):
                                    formatted_article['expected_change'] = self._estimate_price_impact(formatted_article)
                                    await self._trigger_emergency_alert(formatted_article)
                                processed += 1
                            elif self._is_important_news(formatted_article):
                                await self._add_to_news_buffer(formatted_article)
                                processed += 1
                    
                    if processed > 0:
                        logger.info(f"📰 Alpha Vantage: {processed}개 비트코인 뉴스 처리")
                else:
                    logger.warning(f"Alpha Vantage 응답 오류: {response.status}")
        
        except Exception as e:
            logger.error(f"Alpha Vantage 호출 오류: {e}")
    
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
            self.company_news_count = {}
            self.translation_count = 0
            self.last_translation_reset = datetime.now()
            self.news_first_seen = {}
            logger.info(f"🔄 일일 리셋 완료")
    
    async def get_recent_news(self, hours: int = 6) -> List[Dict]:
        """최근 뉴스 가져오기"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_news = []
            seen_hashes = set()
            
            for article in self.news_buffer:
                try:
                    # 시간 체크
                    if article.get('published_at'):
                        pub_time_str = article.get('published_at', '')
                        try:
                            if 'T' in pub_time_str:
                                pub_time = datetime.fromisoformat(pub_time_str.replace('Z', ''))
                            else:
                                from dateutil import parser
                                pub_time = parser.parse(pub_time_str)
                            
                            if pub_time > cutoff_time:
                                # 중복 체크
                                content_hash = self._generate_content_hash(article.get('title', ''), '')
                                if content_hash not in seen_hashes:
                                    recent_news.append(article)
                                    seen_hashes.add(content_hash)
                        except:
                            pass
                except:
                    pass
            
            # 정렬: 가중치 → 시간
            recent_news.sort(key=lambda x: (x.get('weight', 0), x.get('published_at', '')), reverse=True)
            
            return recent_news[:15]
            
        except Exception as e:
            logger.error(f"최근 뉴스 조회 오류: {e}")
            return []
    
    async def close(self):
        """세션 종료"""
        try:
            if self.session:
                await self.session.close()
                logger.info("🔚 뉴스 수집기 세션 종료")
        except Exception as e:
            logger.error(f"세션 종료 중 오류: {e}")
