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
import json

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
        
        # 중복 방지 데이터 파일 경로
        self.persistence_file = 'news_duplicates.json'
        
        # 전송된 뉴스 제목 캐시 (중복 방지 강화) - 초기화
        self.sent_news_titles = {}
        
        # 🔥🔥 Claude API 우선 사용, GPT는 백업용
        self.translation_cache = {}  # 번역 캐시
        self.claude_translation_count = 0  # Claude 번역 횟수
        self.gpt_translation_count = 0  # GPT 번역 횟수 
        self.last_translation_reset = datetime.now()
        self.max_claude_translations_per_15min = 100  # Claude는 더 많이 사용 가능
        self.max_gpt_translations_per_15min = 10  # GPT는 백업용으로만
        self.translation_reset_interval = 900  # 15분
        
        # Claude API 클라이언트 초기화
        self.anthropic_client = None
        if hasattr(config, 'ANTHROPIC_API_KEY') and config.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self.anthropic_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
                logger.info("✅ Claude API 클라이언트 초기화 완료")
            except ImportError:
                logger.warning("❌ anthropic 라이브러리가 설치되지 않음: pip install anthropic")
            except Exception as e:
                logger.warning(f"Claude API 초기화 실패: {e}")
        
        # OpenAI 클라이언트 초기화 (백업용)
        self.openai_client = None
        if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY:
            self.openai_client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        
        # GPT 요약 사용량 제한 추가
        self.summary_count = 0
        self.max_summaries_per_15min = 30  # 15개에서 30개로 증가
        self.last_summary_reset = datetime.now()
        
        # 모든 API 키들
        self.newsapi_key = getattr(config, 'NEWSAPI_KEY', None)
        self.newsdata_key = getattr(config, 'NEWSDATA_KEY', None)
        self.alpha_vantage_key = getattr(config, 'ALPHA_VANTAGE_KEY', None)
        
        # 🔥🔥 강화된 크리티컬 키워드 (더 포괄적이고 민감하게)
        self.critical_keywords = [
            # 비트코인 ETF 관련 (최우선)
            'bitcoin etf approved', 'bitcoin etf rejected', 'spot bitcoin etf', 'etf decision',
            'blackrock bitcoin etf', 'fidelity bitcoin etf', 'ark bitcoin etf', 'grayscale bitcoin etf',
            'SEC 비트코인 ETF', 'ETF 승인', 'ETF 거부', 'SEC approves bitcoin', 'SEC rejects bitcoin',
            
            # 기업 비트코인 구매 (직접적)
            'tesla bought bitcoin', 'microstrategy bought bitcoin', 'bought bitcoin', 'buys bitcoin',
            'gamestop bitcoin purchase', 'metaplanet bitcoin', 'corporate bitcoin purchase',
            'bitcoin acquisition', 'adds bitcoin', 'bitcoin investment', 'purchases bitcoin',
            '비트코인 구매', '비트코인 매입', 'BTC 구매', 'BTC 매입', 'bitcoin holdings',
            
            # 국가/은행 채택
            'central bank bitcoin', 'russia bitcoin', 'sberbank bitcoin', 'bitcoin bonds',
            'government bitcoin', 'country adopts bitcoin', 'bitcoin legal tender',
            '중앙은행 비트코인', '러시아 비트코인', '비트코인 채권', 'el salvador bitcoin',
            'putin bitcoin', 'russia legalize bitcoin', 'china bitcoin ban lifted',
            
            # 비트코인 규제 (직접적)
            'sec bitcoin lawsuit', 'bitcoin ban', 'bitcoin regulation', 'bitcoin lawsuit',
            'china bans bitcoin', 'government bans bitcoin', 'court bitcoin', 'biden bitcoin',
            'regulatory approval bitcoin', 'regulatory rejection bitcoin', 'trump bitcoin',
            'SEC 비트코인', '비트코인 금지', '비트코인 규제', 'coinbase lawsuit',
            
            # 비트코인 시장 급변동
            'bitcoin crash', 'bitcoin surge', 'bitcoin breaks', 'bitcoin plunge',
            'bitcoin all time high', 'bitcoin ath', 'bitcoin tumbles', 'bitcoin soars',
            '비트코인 폭락', '비트코인 급등', '비트코인 급락', 'bitcoin reaches',
            'bitcoin hits', 'bitcoin falls below', 'bitcoin crosses',
            
            # 대량 비트코인 이동
            'whale alert bitcoin', 'large bitcoin transfer', 'bitcoin moved exchange',
            'massive bitcoin', 'billion bitcoin', 'btc whale', 'bitcoin outflow',
            '고래 비트코인', '대량 비트코인', 'BTC 이동', 'satoshi nakamoto',
            
            # 비트코인 해킹/보안
            'bitcoin stolen', 'bitcoin hack', 'exchange hacked bitcoin',
            'bitcoin security breach', 'btc stolen', 'binance hack', 'coinbase hack',
            '비트코인 도난', '비트코인 해킹', '거래소 해킹', 'mt gox',
            
            # Fed 금리 결정 (비트코인 영향) - 강화
            'fed rate decision', 'fomc decision', 'powell speech', 'interest rate decision',
            'federal reserve meeting', 'fed minutes', 'inflation report', 'cpi data',
            '연준 금리', '기준금리', '통화정책', 'jobless claims', 'unemployment rate',
            
            # 거시경제 영향 (강화)
            'us economic policy', 'treasury secretary', 'inflation data', 'cpi report',
            'unemployment rate', 'gdp growth', 'recession fears', 'economic stimulus',
            'quantitative easing', 'dollar strength', 'dollar weakness', 'dxy index',
            '달러 강세', '달러 약세', '인플레이션', '경기침체', 'china economic data',
            
            # 지정학적 리스크 (강화)
            'ukraine war', 'russia sanctions', 'north korea sanctions', 'iran sanctions',
            'china us tensions', 'taiwan conflict', 'middle east conflict', 'israel iran',
            'energy crisis', 'oil price surge', 'natural gas crisis', 'europe energy',
            '지정학적 리스크', '제재', '분쟁', 'gaza conflict', 'russia ukraine',
            
            # 미국 관세 및 무역 (강화)
            'trump tariffs', 'china tariffs', 'trade war', 'trade deal', 'trade agreement',
            'customs duties', 'import tariffs', 'export restrictions', 'trade negotiations',
            'trade talks deadline', 'tariff exemption', 'tariff extension', 'wto ruling',
            '관세', '무역협상', '무역전쟁', '무역합의', 'usmca agreement',
            
            # 암호화폐 거래소/인프라
            'coinbase public', 'binance regulation', 'kraken ipo', 'crypto exchange hack',
            'tether audit', 'usdc regulation', 'defi hack', 'crypto mining ban',
            '암호화폐 거래소', '테더', 'CBDC', 'digital dollar',
            
            # 기관 투자자 진입
            'institutional adoption', 'pension fund bitcoin', 'insurance company bitcoin',
            'bank crypto custody', 'goldman sachs bitcoin', 'jpmorgan bitcoin',
            '기관 투자자', '연기금', '보험사', 'sovereign wealth fund',
            
            # 기술적 이슈
            'bitcoin mining', 'bitcoin halving', 'lightning network', 'bitcoin fork',
            'bitcoin upgrade', 'taproot activation', 'mining difficulty', 'hash rate',
            '비트코인 반감기', '채굴', '해시레이트', 'proof of work'
        ]
        
        # 제외 키워드 (비트코인과 무관한 것들) - 강화
        self.exclude_keywords = [
            'how to mine', '집에서 채굴', 'mining at home', 'mining tutorial',
            'price prediction tutorial', '가격 예측 방법', 'technical analysis tutorial',
            'altcoin only', 'ethereum only', 'ripple only', 'cardano only', 'solana only', 
            'dogecoin only', 'shiba only', 'nft only', 'web3 only', 'metaverse only',
            'defi only', 'gamefi only', 'celebrity news', 'entertainment only',
            'sports only', 'weather', 'local news', 'obituary', 'wedding',
            'movie review', 'book review', 'restaurant review', 'travel guide'
        ]
        
        # 중요 기업 리스트 (비트코인 보유/관련) - 확장
        self.important_companies = [
            'tesla', 'microstrategy', 'square', 'block', 'paypal', 'mastercard', 'visa',
            'gamestop', 'gme', 'blackrock', 'fidelity', 'ark invest', 'grayscale',
            'coinbase', 'binance', 'kraken', 'bitget', 'okx', 'bybit',
            'metaplanet', '메타플래닛', '테슬라', '마이크로스트래티지',
            'sberbank', '스베르방크', 'jpmorgan', 'goldman sachs', 'morgan stanley',
            'nvidia', 'amd', 'intel', 'apple', 'microsoft', 'amazon',
            '삼성', 'samsung', 'lg', 'sk', 'hyundai'
        ]
        
        # 🔥🔥 현실적인 과거 뉴스 영향 패턴 (더 정교하게 - 실제 시장 반응 기반)
        self.historical_patterns = {
            # ETF 관련 (가장 큰 영향)
            'etf_approval': {'avg_impact': 3.5, 'duration_hours': 24, 'confidence': 0.95},
            'etf_rejection': {'avg_impact': -2.8, 'duration_hours': 12, 'confidence': 0.9},
            'etf_filing': {'avg_impact': 0.8, 'duration_hours': 6, 'confidence': 0.7},
            
            # 기업 구매 (규모별)
            'tesla_purchase': {'avg_impact': 2.2, 'duration_hours': 18, 'confidence': 0.9},
            'microstrategy_purchase': {'avg_impact': 0.7, 'duration_hours': 8, 'confidence': 0.85},
            'large_corp_purchase': {'avg_impact': 1.2, 'duration_hours': 12, 'confidence': 0.8},
            'small_corp_purchase': {'avg_impact': 0.3, 'duration_hours': 4, 'confidence': 0.6},
            
            # 규제 관련
            'sec_lawsuit': {'avg_impact': -1.5, 'duration_hours': 8, 'confidence': 0.8},
            'china_ban': {'avg_impact': -4.2, 'duration_hours': 24, 'confidence': 0.85},
            'regulatory_clarity': {'avg_impact': 1.8, 'duration_hours': 12, 'confidence': 0.75},
            
            # 거시경제 (Fed 관련)
            'fed_rate_hike': {'avg_impact': -1.2, 'duration_hours': 6, 'confidence': 0.7},
            'fed_rate_cut': {'avg_impact': 1.5, 'duration_hours': 8, 'confidence': 0.75},
            'fed_dovish': {'avg_impact': 0.8, 'duration_hours': 4, 'confidence': 0.6},
            'fed_hawkish': {'avg_impact': -0.6, 'duration_hours': 4, 'confidence': 0.6},
            
            # 인플레이션/경제지표
            'high_inflation': {'avg_impact': 1.2, 'duration_hours': 6, 'confidence': 0.65},
            'low_inflation': {'avg_impact': -0.4, 'duration_hours': 4, 'confidence': 0.55},
            'recession_fears': {'avg_impact': 0.8, 'duration_hours': 8, 'confidence': 0.6},
            'strong_jobs': {'avg_impact': -0.3, 'duration_hours': 3, 'confidence': 0.5},
            
            # 지정학적 리스크
            'war_escalation': {'avg_impact': 1.5, 'duration_hours': 12, 'confidence': 0.7},
            'peace_talks': {'avg_impact': -0.5, 'duration_hours': 6, 'confidence': 0.55},
            'sanctions': {'avg_impact': 0.8, 'duration_hours': 8, 'confidence': 0.6},
            
            # 무역/관세
            'new_tariffs': {'avg_impact': -0.8, 'duration_hours': 6, 'confidence': 0.65},
            'trade_deal': {'avg_impact': 0.6, 'duration_hours': 8, 'confidence': 0.7},
            
            # 기술적/보안 이슈
            'major_hack': {'avg_impact': -2.2, 'duration_hours': 8, 'confidence': 0.8},
            'minor_hack': {'avg_impact': -0.4, 'duration_hours': 3, 'confidence': 0.6},
            'upgrade_news': {'avg_impact': 0.3, 'duration_hours': 4, 'confidence': 0.5},
            
            # 채굴/인프라
            'mining_ban': {'avg_impact': -1.8, 'duration_hours': 12, 'confidence': 0.75},
            'mining_support': {'avg_impact': 0.5, 'duration_hours': 6, 'confidence': 0.6},
            'halving_approach': {'avg_impact': 0.4, 'duration_hours': 8, 'confidence': 0.65},
            
            # 기관/은행 관련
            'bank_adoption': {'avg_impact': 1.0, 'duration_hours': 10, 'confidence': 0.75},
            'bank_restriction': {'avg_impact': -0.8, 'duration_hours': 6, 'confidence': 0.7},
            'pension_entry': {'avg_impact': 0.8, 'duration_hours': 8, 'confidence': 0.7}
        }
        
        # RSS 피드 - 더 많은 소스 추가
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
            
            # 금융 (Fed/규제 관련) - 확장
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
        
        # API 사용량 추적
        self.api_usage = {
            'newsapi_today': 0,
            'newsdata_today': 0,
            'alpha_vantage_today': 0,
            'last_reset': datetime.now().date()
        }
        
        # API 일일 한도 증가
        self.api_limits = {
            'newsapi': 50,  # 20 → 50
            'newsdata': 25,  # 10 → 25
            'alpha_vantage': 5   # 2 → 5
        }
        
        # 중복 방지 데이터 로드
        self._load_duplicate_data()
        
        logger.info(f"🔥🔥 Claude 우선 번역 뉴스 수집기 초기화 완료")
        logger.info(f"🤖 Claude API: {'활성화' if self.anthropic_client else '비활성화'} (15분당 {self.max_claude_translations_per_15min}개)")
        logger.info(f"🧠 GPT API: {'활성화' if self.openai_client else '비활성화'} (백업용 15분당 {self.max_gpt_translations_per_15min}개)")
        logger.info(f"📊 설정: RSS 5초 체크 (빠른 감지), 요약 15분당 {self.max_summaries_per_15min}개")
        logger.info(f"🎯 크리티컬 키워드: {len(self.critical_keywords)}개 (대폭 확장)")
        logger.info(f"🏢 추적 기업: {len(self.important_companies)}개")
        logger.info(f"📈 가격 패턴: {len(self.historical_patterns)}개 시나리오")
        logger.info(f"📡 RSS 소스: {len(self.rss_feeds)}개 (확장)")
        logger.info(f"💾 중복 방지: 처리된 뉴스 {len(self.processed_news_hashes)}개")
    
    def _load_duplicate_data(self):
        """중복 방지 데이터 파일에서 로드"""
        try:
            if os.path.exists(self.persistence_file):
                with open(self.persistence_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 처리된 뉴스 해시 로드
                self.processed_news_hashes = set(data.get('processed_news_hashes', []))
                
                # 긴급 알림 데이터 로드 (시간 문자열을 datetime으로 변환)
                emergency_data = data.get('emergency_alerts_sent', {})
                current_time = datetime.now()
                cutoff_time = current_time - timedelta(hours=12)  # 12시간 이내 데이터만 유지
                
                for hash_key, time_str in emergency_data.items():
                    try:
                        alert_time = datetime.fromisoformat(time_str)
                        if alert_time > cutoff_time:  # 12시간 이내 데이터만 유지
                            self.emergency_alerts_sent[hash_key] = alert_time
                    except:
                        continue
                
                # 뉴스 제목 캐시 로드
                title_data = data.get('sent_news_titles', {})
                cutoff_time = current_time - timedelta(hours=3)  # 3시간 이내 데이터만 유지
                
                for title_hash, time_str in title_data.items():
                    try:
                        sent_time = datetime.fromisoformat(time_str)
                        if sent_time > cutoff_time:  # 3시간 이내 데이터만 유지
                            self.sent_news_titles[title_hash] = sent_time
                    except:
                        continue
                
                # 처리된 뉴스 해시 크기 제한 (최대 3000개)
                if len(self.processed_news_hashes) > 3000:
                    self.processed_news_hashes = set(list(self.processed_news_hashes)[-1500:])
                
                logger.info(f"중복 방지 데이터 로드 완료: 처리된 뉴스 {len(self.processed_news_hashes)}개")
                
        except Exception as e:
            logger.warning(f"중복 방지 데이터 로드 실패: {e}")
            # 기본값으로 초기화
            self.processed_news_hashes = set()
            self.emergency_alerts_sent = {}
            self.sent_news_titles = {}
    
    def _save_duplicate_data(self):
        """중복 방지 데이터를 파일에 저장"""
        try:
            # datetime을 문자열로 변환하여 저장
            emergency_data = {}
            for hash_key, alert_time in self.emergency_alerts_sent.items():
                emergency_data[hash_key] = alert_time.isoformat()
            
            title_data = {}
            for title_hash, sent_time in self.sent_news_titles.items():
                title_data[title_hash] = sent_time.isoformat()
            
            data = {
                'processed_news_hashes': list(self.processed_news_hashes),
                'emergency_alerts_sent': emergency_data,
                'sent_news_titles': title_data,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.persistence_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"중복 방지 데이터 저장 완료: {len(self.processed_news_hashes)}개 해시")
            
        except Exception as e:
            logger.error(f"중복 방지 데이터 저장 실패: {e}")
    
    def _reset_translation_count_if_needed(self):
        """필요시 번역 카운트 리셋"""
        now = datetime.now()
        if (now - self.last_translation_reset).total_seconds() > self.translation_reset_interval:
            old_claude_count = self.claude_translation_count
            old_gpt_count = self.gpt_translation_count
            self.claude_translation_count = 0
            self.gpt_translation_count = 0
            self.last_translation_reset = now
            if old_claude_count > 0 or old_gpt_count > 0:
                logger.info(f"번역 카운트 리셋: Claude {old_claude_count} → 0, GPT {old_gpt_count} → 0")
    
    def _reset_summary_count_if_needed(self):
        """필요시 요약 카운트 리셋"""
        now = datetime.now()
        if (now - self.last_summary_reset).total_seconds() > self.translation_reset_interval:
            old_count = self.summary_count
            self.summary_count = 0
            self.last_summary_reset = now
            if old_count > 0:
                logger.info(f"요약 카운트 리셋: {old_count} → 0 (15분당 {self.max_summaries_per_15min}개 제한)")
    
    def _should_translate(self, article: Dict) -> bool:
        """🔥🔥 번역 대상을 좀 더 관대하게 - Claude는 더 많이 사용 가능"""
        # 이미 한글 제목이 있으면 번역 불필요
        if article.get('title_ko') and article['title_ko'] != article.get('title', ''):
            return False
        
        # 🔥🔥 크리티컬 뉴스는 번역 (weight >= 8로 낮춤)
        weight = article.get('weight', 0)
        if weight < 8:
            return False
        
        # 🔥🔥 크리티컬 뉴스이면서 비트코인 관련만
        if not self._is_critical_news(article):
            return False
        
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 비트코인 또는 중요 경제 키워드가 있어야 함
        important_keywords = ['bitcoin', 'btc', '비트코인', 'fed', 'tariff', 'inflation', 'etf', 
                             'tesla', 'microstrategy', 'sec', 'regulation']
        if not any(keyword in content for keyword in important_keywords):
            return False
        
        return True
    
    def _should_use_gpt_summary(self, article: Dict) -> bool:
        """🔥🔥 GPT 요약 사용 여부 결정 - 더 관대하게"""
        # 요약 카운트 리셋 체크
        self._reset_summary_count_if_needed()
        
        # Rate limit 체크
        if self.summary_count >= self.max_summaries_per_15min:
            return False
        
        # weight >= 9이면서 크리티컬 뉴스만
        if article.get('weight', 0) < 9:
            return False
        
        if not self._is_critical_news_enhanced(article):
            return False
        
        # description이 충분히 길어야 함 (요약할 가치가 있어야 함)
        description = article.get('description', '')
        if len(description) < 200:  # 300자에서 200자로 낮춤
            return False
        
        return True
    
    async def translate_text_with_claude(self, text: str, max_length: int = 400) -> str:
        """🔥🔥 Claude API를 사용한 번역"""
        if not self.anthropic_client:
            return text
        
        # 번역 카운트 리셋 체크
        self._reset_translation_count_if_needed()
        
        # 캐시 확인
        cache_key = f"claude_{hashlib.md5(text.encode()).hexdigest()}"
        if cache_key in self.translation_cache:
            logger.debug(f"🔄 Claude 번역 캐시 히트")
            return self.translation_cache[cache_key]
        
        # Claude Rate limit 체크
        if self.claude_translation_count >= self.max_claude_translations_per_15min:
            logger.warning(f"Claude 번역 한도 초과: {self.claude_translation_count}/{self.max_claude_translations_per_15min}")
            return text
        
        try:
            response = await self.anthropic_client.messages.create(
                model="claude-3-5-haiku-20241022",  # 빠르고 저렴한 모델
                max_tokens=200,
                messages=[{
                    "role": "user", 
                    "content": f"""다음 영문 뉴스 제목을 자연스러운 한국어로 번역해주세요. 전문 용어는 다음과 같이 번역하세요:

- Bitcoin/BTC → 비트코인
- ETF → ETF
- Tesla → 테슬라
- MicroStrategy → 마이크로스트래티지
- SEC → SEC
- Fed/Federal Reserve → 연준
- Trump → 트럼프
- China → 중국
- Russia → 러시아
- tariffs → 관세

최대 {max_length}자 이내로 번역하되, 의미가 명확하게 전달되도록 해주세요.

제목: {text}"""
                }]
            )
            
            translated = response.content[0].text.strip()
            
            # 길이 체크
            if len(translated) > max_length:
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
            self.claude_translation_count += 1
            
            # 캐시 크기 제한
            if len(self.translation_cache) > 500:
                keys_to_remove = list(self.translation_cache.keys())[:250]
                for key in keys_to_remove:
                    del self.translation_cache[key]
            
            logger.info(f"🤖 Claude 번역 완료 ({self.claude_translation_count}/{self.max_claude_translations_per_15min})")
            return translated
            
        except Exception as e:
            logger.warning(f"Claude 번역 실패: {str(e)[:50]} - GPT 백업 시도")
            return await self.translate_text_with_gpt(text, max_length)
    
    async def translate_text_with_gpt(self, text: str, max_length: int = 400) -> str:
        """🔥🔥 GPT API를 사용한 백업 번역"""
        if not self.openai_client:
            return text
        
        # GPT Rate limit 체크
        if self.gpt_translation_count >= self.max_gpt_translations_per_15min:
            logger.warning(f"GPT 번역 한도 초과: {self.gpt_translation_count}/{self.max_gpt_translations_per_15min}")
            return text
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "비트코인 전문 번역가입니다. 영문을 자연스러운 한국어로 번역하세요."},
                    {"role": "user", "content": f"다음을 한국어로 번역 (최대 {max_length}자):\n\n{text}"}
                ],
                max_tokens=150,
                temperature=0.2
            )
            
            translated = response.choices[0].message.content.strip()
            
            # 길이 체크
            if len(translated) > max_length:
                translated = translated[:max_length-3] + "..."
            
            self.gpt_translation_count += 1
            logger.info(f"🧠 GPT 백업 번역 완료 ({self.gpt_translation_count}/{self.max_gpt_translations_per_15min})")
            return translated
            
        except Exception as e:
            logger.warning(f"GPT 번역도 실패: {str(e)[:50]}")
            return text
    
    async def translate_text(self, text: str, max_length: int = 400) -> str:
        """🔥🔥 통합 번역 함수 - Claude 우선, GPT 백업"""
        if self.anthropic_client:
            return await self.translate_text_with_claude(text, max_length)
        elif self.openai_client:
            return await self.translate_text_with_gpt(text, max_length)
        else:
            return text
    
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
                  'announced', 'launches', 'approves', 'rejects', 'bans', 'raises', 'cuts']
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
    
    def _is_duplicate_emergency(self, article: Dict, time_window: int = 30) -> bool:
        """긴급 알림이 중복인지 확인 (30분 이내로 단축)"""
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
            
            # 파일에 저장
            self._save_duplicate_data()
            
            return False
            
        except Exception as e:
            logger.error(f"중복 체크 오류: {e}")
            return False
    
    def _is_recent_news(self, article: Dict, hours: int = 2) -> bool:
        """뉴스가 최근 것인지 확인 - 2시간 이내로 단축"""
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
        """🔥🔥 강화된 뉴스 모니터링 시작 - 더 빠른 감지"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=aiohttp.TCPConnector(limit=150, limit_per_host=50)
            )
        
        logger.info("🔥🔥 Claude 우선 번역 비트코인 + 거시경제 뉴스 모니터링 시작")
        logger.info(f"🤖 Claude API: {'활성화' if self.anthropic_client else '비활성화'}")
        logger.info(f"🧠 GPT API: {'활성화 (백업)' if self.openai_client else '비활성화'}")
        logger.info(f"📊 RSS 체크: 5초마다 (빠른 감지)")
        logger.info(f"🎯 크리티컬 키워드: {len(self.critical_keywords)}개")
        logger.info(f"🏢 추적 기업: {len(self.important_companies)}개")
        logger.info(f"📡 RSS 소스: {len(self.rss_feeds)}개")
        
        # 회사별 뉴스 카운트 초기화
        self.company_news_count = {}
        
        tasks = [
            self.monitor_rss_feeds_enhanced(),      # RSS (5초마다) - 더 빠르게
            self.monitor_reddit_enhanced(),         # Reddit (5분마다) - 강화
            self.aggressive_api_rotation_enhanced() # API 순환 사용 - 강화
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def monitor_rss_feeds_enhanced(self):
        """🔥🔥 강화된 RSS 피드 모니터링 - 5초마다 (더 빠르게)"""
        while True:
            try:
                # 가중치가 높은 소스부터 처리
                sorted_feeds = sorted(self.rss_feeds, key=lambda x: x['weight'], reverse=True)
                successful_feeds = 0
                processed_articles = 0
                critical_found = 0
                translated_count = 0
                
                for feed_info in sorted_feeds:
                    try:
                        articles = await self._parse_rss_feed_enhanced(feed_info)
                        
                        if articles:
                            successful_feeds += 1
                            
                            for article in articles:
                                # 최신 뉴스만 처리 (2시간 이내로 단축)
                                if not self._is_recent_news(article, hours=2):
                                    continue
                                
                                # 비트코인 + 거시경제 관련성 체크 (강화)
                                if not self._is_bitcoin_or_macro_related_enhanced(article):
                                    continue
                                
                                # 기업명 추출
                                company = self._extract_company_from_content(
                                    article.get('title', ''),
                                    article.get('description', '')
                                )
                                if company:
                                    article['company'] = company
                                
                                # 🔥🔥 번역 - Claude 우선 사용
                                if self._should_translate(article):
                                    article['title_ko'] = await self.translate_text(article['title'])
                                    translated_count += 1
                                else:
                                    article['title_ko'] = article.get('title', '')
                                
                                # 🔥🔥 강화된 크리티컬 뉴스 체크
                                if self._is_critical_news_enhanced(article):
                                    # 요약 (선택적)
                                    if self._should_use_gpt_summary(article):
                                        summary = await self.summarize_article_enhanced(
                                            article['title'],
                                            article.get('description', '')
                                        )
                                        if summary:
                                            article['summary'] = summary
                                    
                                    if not self._is_duplicate_emergency(article):
                                        article['expected_change'] = self._estimate_price_impact_enhanced(article)
                                        await self._trigger_emergency_alert_enhanced(article)
                                        processed_articles += 1
                                        critical_found += 1
                                
                                # 중요 뉴스는 버퍼에 추가
                                elif self._is_important_news_enhanced(article):
                                    await self._add_to_news_buffer_enhanced(article)
                                    processed_articles += 1
                    
                    except Exception as e:
                        logger.warning(f"RSS 피드 오류 {feed_info['source']}: {str(e)[:50]}")
                        continue
                
                if processed_articles > 0:
                    logger.info(f"🔥 RSS 스캔 완료: {successful_feeds}개 피드, {processed_articles}개 관련 뉴스 (크리티컬: {critical_found}개, 번역: {translated_count}개)")
                
                await asyncio.sleep(5)  # 5초마다 (더 빈번하게)
                
            except Exception as e:
                logger.error(f"RSS 모니터링 오류: {e}")
                await asyncio.sleep(30)
    
    def _is_bitcoin_or_macro_related_enhanced(self, article: Dict) -> bool:
        """🔥🔥 강화된 비트코인 직접 관련성 + 거시경제 영향 체크"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 제외 키워드 먼저 체크 (더 엄격하게)
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 🔥 1. 비트코인 직접 언급 (가장 우선)
        bitcoin_keywords = ['bitcoin', 'btc', '비트코인', 'bitcoins']
        has_bitcoin = any(keyword in content for keyword in bitcoin_keywords)
        
        if has_bitcoin:
            return True
        
        # 🔥 2. 암호화폐 일반 + 중요 내용
        crypto_keywords = ['crypto', 'cryptocurrency', '암호화폐', 'cryptocurrencies', 'digital currency']
        has_crypto = any(keyword in content for keyword in crypto_keywords)
        
        if has_crypto:
            # ETF, SEC, 규제 등 중요 키워드와 함께 나오면 포함
            important_terms = ['etf', 'sec', 'regulation', 'ban', 'approval', 'court', 'lawsuit', 
                             'bonds', 'russia', 'sberbank', 'institutional', 'adoption']
            if any(term in content for term in important_terms):
                return True
        
        # 🔥 3. Fed 금리 결정 (비트코인 언급 없어도 중요)
        fed_keywords = ['fed rate decision', 'fomc decides', 'powell announces', 'federal reserve decision',
                       'interest rate decision', 'fed chair', 'fed meeting', 'monetary policy']
        if any(keyword in content for keyword in fed_keywords):
            return True
        
        # 🔥 4. 중요 경제 지표 (비트코인 시장에 직접 영향)
        economic_keywords = ['inflation data', 'cpi report', 'unemployment rate', 'jobs report',
                           'gdp growth', 'pce index', 'retail sales', 'manufacturing pmi']
        if any(keyword in content for keyword in economic_keywords):
            return True
        
        # 🔥 5. 미국 관세 및 무역 (비트코인 시장에 영향)
        trade_keywords = ['trump tariffs', 'china tariffs', 'trade war escalation', 'trade deal signed',
                         'trade agreement', 'trade negotiations breakthrough', 'wto ruling']
        if any(keyword in content for keyword in trade_keywords):
            return True
        
        # 🔥 6. 달러 강세/약세 (비트코인과 역상관)
        dollar_keywords = ['dollar strength surge', 'dollar weakness', 'dxy breaks', 'dollar index hits',
                          'usd strengthens', 'usd weakens']
        if any(keyword in content for keyword in dollar_keywords):
            return True
        
        # 🔥 7. 지정학적 리스크 (안전자산 수요)
        geopolitical_keywords = ['ukraine war escalation', 'russia sanctions expanded', 'china us tensions',
                               'middle east conflict', 'iran israel', 'energy crisis', 'oil price surge']
        if any(keyword in content for keyword in geopolitical_keywords):
            return True
        
        # 🔥 8. 주요 기업 관련 (비트코인 보유 기업들)
        for company in self.important_companies:
            if company.lower() in content:
                # 기업이 언급되고 중요한 키워드가 함께 나오면 포함
                relevant_terms = ['earnings', 'acquisition', 'investment', 'purchase', 'announces',
                                'reports', 'launches', 'partnership', 'regulation', 'lawsuit']
                if any(term in content for term in relevant_terms):
                    return True
        
        # 🔥 9. 중앙은행 정책 (글로벌 영향)
        central_bank_keywords = ['ecb rate decision', 'bank of japan policy', 'people bank of china',
                               'boe rate decision', 'rba decision', 'snb policy']
        if any(keyword in content for keyword in central_bank_keywords):
            return True
        
        return False
    
    def _is_critical_news_enhanced(self, article: Dict) -> bool:
        """🔥🔥 강화된 크리티컬 뉴스 판단 - 더 민감하게"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 비트코인 + 거시경제 관련성 체크
        if not self._is_bitcoin_or_macro_related_enhanced(article):
            return False
        
        # 제외 키워드 체크
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 🔥🔥 가중치 체크를 낮춤 (7 이상만 → 6 이상으로)
        if article.get('weight', 0) < 6:
            return False
        
        # 🔥🔥 강화된 크리티컬 키워드 체크
        for keyword in self.critical_keywords:
            if keyword.lower() in content:
                # 부정적 필터 (루머, 추측 등)
                negative_filters = ['rumor', 'speculation', 'unconfirmed', 'fake', 'false', 
                                  '루머', '추측', '미확인', 'alleged', 'reportedly']
                if any(neg in content for neg in negative_filters):
                    continue
                
                logger.info(f"🚨 크리티컬 키워드 감지: '{keyword}' - {article.get('title', '')[:50]}...")
                return True
        
        # 🔥🔥 추가 크리티컬 패턴 (더 민감하게)
        critical_patterns = [
            # 비트코인 직접
            ('bitcoin', 'etf', 'approved'),
            ('bitcoin', 'etf', 'rejected'),  
            ('bitcoin', 'billion', 'bought'),
            ('bitcoin', 'sec', 'lawsuit'),
            ('bitcoin', 'ban', 'china'),
            ('bitcoin', 'all', 'time', 'high'),
            ('bitcoin', 'crash', 'below'),
            
            # 기업 구매
            ('tesla', 'bitcoin', 'purchase'),
            ('microstrategy', 'bitcoin', 'buy'),
            ('blackrock', 'bitcoin', 'fund'),
            
            # Fed 관련
            ('fed', 'rate', 'decision'),
            ('powell', 'announces', 'rate'),
            ('fomc', 'decides', 'policy'),
            
            # 경제 지표
            ('inflation', 'surges', 'above'),
            ('unemployment', 'drops', 'below'),
            ('gdp', 'growth', 'exceeds'),
            ('cpi', 'data', 'shows'),
            
            # 무역/지정학
            ('trump', 'announces', 'tariffs'),
            ('china', 'trade', 'deal'),
            ('ukraine', 'war', 'escalates'),
            ('russia', 'sanctions', 'expanded'),
            
            # 기타 중요
            ('dollar', 'index', 'breaks'),
            ('oil', 'price', 'surges'),
            ('gold', 'hits', 'record')
        ]
        
        for pattern in critical_patterns:
            if all(word in content for word in pattern):
                logger.info(f"🚨 크리티컬 패턴 감지: {pattern} - {article.get('title', '')[:50]}...")
                return True
        
        return False
    
    def _is_important_news_enhanced(self, article: Dict) -> bool:
        """🔥🔥 강화된 중요 뉴스 판단"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 비트코인 + 거시경제 관련성 체크
        if not self._is_bitcoin_or_macro_related_enhanced(article):
            return False
        
        # 제외 키워드 체크
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 가중치와 카테고리 체크
        weight = article.get('weight', 0)
        category = article.get('category', '')
        
        # 🔥🔥 조건들 (더 포괄적으로)
        conditions = [
            # 암호화폐 전문 소스 (가중치 낮춤)
            category == 'crypto' and weight >= 6,
            
            # 금융 소스 + 비트코인 또는 중요 키워드
            category == 'finance' and weight >= 6 and (
                any(word in content for word in ['bitcoin', 'btc', 'crypto']) or
                any(word in content for word in ['fed', 'rate', 'inflation', 'sec', 'tariffs', 'trade'])
            ),
            
            # API 뉴스 (가중치 낮춤)
            category == 'api' and weight >= 7,
            
            # 기업 + 비트코인/암호화폐
            any(company.lower() in content for company in self.important_companies) and 
            any(word in content for word in ['bitcoin', 'btc', 'crypto', 'digital', 'blockchain']),
            
            # 거시경제 중요 뉴스
            any(word in content for word in ['fed rate decision', 'inflation data', 'cpi report', 
                                           'unemployment rate', 'gdp growth', 'trade deal']) and weight >= 6,
            
            # 지정학적/무역 뉴스
            any(word in content for word in ['trump tariffs', 'china trade', 'ukraine war', 
                                           'russia sanctions', 'middle east']) and weight >= 6,
            
            # 중앙은행 정책
            any(word in content for word in ['central bank', 'monetary policy', 'ecb decision', 
                                           'boj policy']) and weight >= 6
        ]
        
        return any(conditions)
    
    def _estimate_price_impact_enhanced(self, article: Dict) -> str:
        """🔥🔥 강화된 현실적 가격 영향 추정"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 🔥 1. 과거 패턴 기반 예측 (우선)
        pattern_match = self._match_historical_pattern_enhanced(content)
        if pattern_match:
            pattern_data = self.historical_patterns[pattern_match]
            impact = pattern_data['avg_impact']
            confidence = pattern_data['confidence']
            duration = pattern_data['duration_hours']
            
            # 신뢰도 기반 범위 조정
            if confidence >= 0.9:
                range_modifier = 0.2
            elif confidence >= 0.75:
                range_modifier = 0.3
            else:
                range_modifier = 0.4
            
            if impact > 0:
                min_impact = impact * (1 - range_modifier)
                max_impact = impact * (1 + range_modifier)
                direction = "📈 상승"
                emoji = "🚀" if impact >= 2.0 else "📈"
            else:
                min_impact = abs(impact) * (1 - range_modifier)
                max_impact = abs(impact) * (1 + range_modifier)
                direction = "📉 하락"
                emoji = "🔻" if abs(impact) >= 2.0 else "📉"
            
            return f"{emoji} {direction} {min_impact:.1f}~{max_impact:.1f}% ({duration}시간 내)"
        
        # 🔥 2. 키워드 기반 세밀한 분석
        return self._estimate_price_impact_by_keywords(content)
    
    def _match_historical_pattern_enhanced(self, content: str) -> Optional[str]:
        """🔥🔥 강화된 과거 패턴 매칭"""
        patterns = {
            # ETF 관련
            'etf_approval': ['bitcoin', 'etf', 'approved', 'sec'],
            'etf_rejection': ['bitcoin', 'etf', 'rejected', 'denied'],
            'etf_filing': ['bitcoin', 'etf', 'filing', 'application'],
            
            # 기업 구매 (규모별)
            'tesla_purchase': ['tesla', 'bitcoin', 'bought', 'purchase'],
            'microstrategy_purchase': ['microstrategy', 'bitcoin', 'acquired', 'buy'],
            'large_corp_purchase': ['billion', 'bitcoin', 'purchase', 'acquired'],
            'small_corp_purchase': ['million', 'bitcoin', 'bought', 'adds'],
            
            # 규제
            'sec_lawsuit': ['sec', 'lawsuit', 'bitcoin', 'crypto'],
            'china_ban': ['china', 'ban', 'bitcoin', 'cryptocurrency'],
            'regulatory_clarity': ['regulatory', 'clarity', 'bitcoin', 'approved'],
            
            # Fed 관련 (세분화)
            'fed_rate_hike': ['fed', 'raises', 'rate', 'hike'],
            'fed_rate_cut': ['fed', 'cuts', 'rate', 'lower'],
            'fed_dovish': ['powell', 'dovish', 'accommodative', 'supportive'],
            'fed_hawkish': ['powell', 'hawkish', 'aggressive', 'tightening'],
            
            # 경제 지표
            'high_inflation': ['inflation', 'cpi', 'above', 'exceeds'],
            'low_inflation': ['inflation', 'cpi', 'below', 'falls'],
            'recession_fears': ['recession', 'fears', 'slowdown', 'contraction'],
            'strong_jobs': ['jobs', 'unemployment', 'strong', 'beats'],
            
            # 지정학
            'war_escalation': ['ukraine', 'war', 'escalation', 'conflict'],
            'peace_talks': ['peace', 'talks', 'ceasefire', 'negotiations'],
            'sanctions': ['sanctions', 'russia', 'expanded', 'additional'],
            
            # 무역
            'new_tariffs': ['trump', 'tariffs', 'china', 'new'],
            'trade_deal': ['trade', 'deal', 'agreement', 'signed'],
            
            # 보안/기술
            'major_hack': ['billion', 'hack', 'stolen', 'breach'],
            'minor_hack': ['million', 'hack', 'stolen', 'compromise'],
            'upgrade_news': ['bitcoin', 'upgrade', 'improvement', 'taproot'],
            
            # 채굴
            'mining_ban': ['mining', 'ban', 'china', 'prohibited'],
            'mining_support': ['mining', 'support', 'renewable', 'green'],
            'halving_approach': ['halving', 'approach', 'countdown', 'event'],
            
            # 기관
            'bank_adoption': ['bank', 'adopt', 'bitcoin', 'custody'],
            'bank_restriction': ['bank', 'restrict', 'bitcoin', 'prohibited'],
            'pension_entry': ['pension', 'fund', 'bitcoin', 'allocation']
        }
        
        # 더 정확한 매칭 (최소 3개 키워드 일치)
        for pattern_name, keywords in patterns.items():
            matches = sum(1 for keyword in keywords if keyword in content)
            if matches >= 3:  # 최소 3개 키워드 매칭
                logger.info(f"🎯 패턴 매칭: {pattern_name} ({matches}/{len(keywords)} 키워드)")
                return pattern_name
        
        return None
    
    def _estimate_price_impact_by_keywords(self, content: str) -> str:
        """키워드 기반 가격 영향 추정"""
        # ETF 관련 (가장 높은 영향)
        if any(word in content for word in ['etf approved', 'etf approval', 'sec approves bitcoin']):
            return '🚀 상승 2.5~4.0% (24시간 내)'
        elif any(word in content for word in ['etf rejected', 'etf denial', 'sec rejects bitcoin']):
            return '🔻 하락 2.0~3.5% (12시간 내)'
        
        # Fed 관련
        elif any(word in content for word in ['fed raises rates', 'rate hike', 'hawkish fed']):
            return '📉 하락 0.8~1.5% (6시간 내)'
        elif any(word in content for word in ['fed cuts rates', 'rate cut', 'dovish fed']):
            return '📈 상승 1.0~2.0% (8시간 내)'
        
        # 인플레이션
        elif any(word in content for word in ['inflation above', 'cpi exceeds', 'high inflation']):
            return '📈 상승 0.8~1.8% (6시간 내)'
        elif any(word in content for word in ['inflation below', 'cpi falls', 'low inflation']):
            return '📉 하락 0.3~0.8% (4시간 내)'
        
        # 기업 구매
        elif any(word in content for word in ['tesla bought bitcoin', 'tesla bitcoin purchase']):
            return '🚀 상승 1.5~3.0% (18시간 내)'
        elif any(word in content for word in ['microstrategy bought bitcoin', 'saylor bitcoin']):
            return '📈 상승 0.5~1.2% (8시간 내)'
        
        # 규제
        elif any(word in content for word in ['china bans bitcoin', 'bitcoin banned']):
            return '🔻 하락 3.0~5.0% (24시간 내)'
        elif any(word in content for word in ['regulatory clarity', 'bitcoin approved']):
            return '📈 상승 1.2~2.5% (12시간 내)'
        
        # 지정학
        elif any(word in content for word in ['war escalation', 'conflict escalates']):
            return '📈 상승 0.8~2.0% (12시간 내)'
        elif any(word in content for word in ['peace talks', 'ceasefire']):
            return '📉 하락 0.2~0.8% (6시간 내)'
        
        # 무역
        elif any(word in content for word in ['new tariffs', 'trade war']):
            return '📉 하락 0.5~1.2% (6시간 내)'
        elif any(word in content for word in ['trade deal', 'trade agreement']):
            return '📈 상승 0.4~1.0% (8시간 내)'
        
        # 해킹/보안
        elif any(word in content for word in ['billion stolen', 'major hack']):
            return '🔻 하락 1.5~3.0% (8시간 내)'
        elif any(word in content for word in ['million stolen', 'minor hack']):
            return '📉 하락 0.3~0.8% (4시간 내)'
        
        # 기본값 (보수적)
        return '⚡ 변동 ±0.2~0.8% (단기)'
    
    async def summarize_article_enhanced(self, title: str, description: str, max_length: int = 200) -> str:
        """🔥🔥 개선된 요약 - 기본 요약 우선, GPT는 백업"""
        
        # 🔥🔥 먼저 기본 요약으로 시도
        basic_summary = self._generate_basic_summary_enhanced(title, description)
        if basic_summary and len(basic_summary.strip()) > 50:
            logger.debug(f"🔄 기본 요약 사용")
            return basic_summary
        
        # GPT 요약이 정말 필요한 경우만
        if not self.openai_client or not description:
            return basic_summary or "비트코인 관련 발표가 있었다. 투자자들은 신중한 접근이 필요하다."
        
        if len(description) <= 200:
            return basic_summary or self._generate_basic_summary_enhanced(title, description)
        
        # 요약 카운트 리셋 체크
        self._reset_summary_count_if_needed()
        
        # Rate limit 체크
        if self.summary_count >= self.max_summaries_per_15min:
            logger.warning(f"요약 한도 초과: {self.summary_count}/{self.max_summaries_per_15min} - 기본 요약 사용")
            return basic_summary or "비트코인 관련 발표가 있었다. 투자자들은 신중한 접근이 필요하다."
        
        try:
            news_type = self._classify_news_for_summary_enhanced(title, description)
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"비트코인 투자 전문가입니다. 3문장으로 요약하세요.\n\n1문장: 핵심 사실\n2문장: 중요성\n3문장: 시장 영향\n\n뉴스 타입: {news_type}"},
                    {"role": "user", "content": f"3문장 요약 (최대 {max_length}자):\n\n제목: {title}\n\n내용: {description[:800]}"}
                ],
                max_tokens=250,
                temperature=0.2
            )
            
            summary = response.choices[0].message.content.strip()
            
            if len(summary) > max_length:
                sentences = summary.split('.')
                result = ""
                for sentence in sentences[:3]:
                    if len(result + sentence + ".") <= max_length - 3:
                        result += sentence + "."
                    else:
                        break
                summary = result.strip() or summary[:max_length-3] + "..."
            
            self.summary_count += 1
            logger.info(f"📝 GPT 요약 완료 ({self.summary_count}/{self.max_summaries_per_15min})")
            
            return summary
            
        except Exception as e:
            logger.warning(f"GPT 요약 실패: {str(e)[:50]} - 기본 요약 사용")
            return basic_summary or "비트코인 관련 발표가 있었다. 투자자들은 신중한 접근이 필요하다."
    
    def _classify_news_for_summary_enhanced(self, title: str, description: str) -> str:
        """강화된 뉴스 타입 분류"""
        content = (title + " " + description).lower()
        
        if any(word in content for word in ['etf approved', 'etf rejected', 'etf filing']):
            return 'etf'
        elif any(word in content for word in ['fed rate', 'fomc', 'powell', 'interest rate']):
            return 'fed_policy'
        elif any(word in content for word in ['inflation', 'cpi', 'pce', 'unemployment']):
            return 'economic_data'
        elif any(company in content for company in ['tesla', 'microstrategy', 'blackrock']):
            return 'corporate_action'
        elif any(word in content for word in ['sec', 'regulation', 'ban', 'lawsuit']):
            return 'regulation'
        elif any(word in content for word in ['tariff', 'trade war', 'trade deal']):
            return 'trade_policy'
        elif any(word in content for word in ['hack', 'stolen', 'breach', 'security']):
            return 'security_incident'
        elif any(word in content for word in ['war', 'conflict', 'sanctions', 'geopolitical']):
            return 'geopolitical'
        else:
            return 'general'
    
    def _generate_basic_summary_enhanced(self, title: str, description: str) -> str:
        """🔥🔥 강화된 기본 요약 생성 - GPT 대신 사용할 고품질 요약"""
        try:
            content = (title + " " + description).lower()
            summary_parts = []
            
            # 구조화 상품 특별 처리
            if any(word in content for word in ['structured', 'bonds', 'linked', 'exposure']):
                if 'sberbank' in content:
                    summary_parts.append("러시아 최대 은행 스베르방크가 비트코인 가격에 연동된 구조화 채권을 출시했다.")
                    summary_parts.append("이는 직접적인 비트코인 매수가 아닌 가격 추적 상품으로, 실제 BTC 수요 창출 효과는 제한적이다.")
                    summary_parts.append("러시아 제재 상황과 OTC 거래로 인해 글로벌 시장에 미치는 즉각적 영향은 미미할 것으로 예상된다.")
                else:
                    summary_parts.append("새로운 비트코인 연계 구조화 상품이 출시되었다.")
                    summary_parts.append("직접적인 비트코인 수요보다는 간접적 노출 제공에 중점을 둔 상품으로 평가된다.")
                    summary_parts.append("시장에 미치는 실질적 영향은 제한적일 것으로 전망된다.")
                
                return " ".join(summary_parts)
            
            # 기업명과 행동 매칭
            companies_in_title = []
            for company in ['tesla', 'microstrategy', 'blackrock', 'gamestop']:
                if company in content:
                    companies_in_title.append(company)
            
            if companies_in_title:
                company = companies_in_title[0]
                
                # 마이크로스트래티지 처리
                if company == 'microstrategy':
                    if 'bought' in content or 'purchase' in content:
                        btc_amounts = re.findall(r'(\d+(?:,\d+)*)\s*(?:btc|bitcoin)', content)
                        if btc_amounts:
                            summary_parts.append(f"마이크로스트래티지가 비트코인 {btc_amounts[0]}개를 직접 매입했다.")
                        else:
                            summary_parts.append("마이크로스트래티지가 비트코인을 추가 매입했다.")
                        
                        summary_parts.append("이는 실제 BTC 수요 증가를 의미하며, 기업 재무 전략의 일환으로 시장에 긍정적 신호를 보낸다.")
                        summary_parts.append("대형 기업의 지속적인 비트코인 매입은 시장 신뢰도 향상에 기여할 것으로 예상된다.")
                
                # 테슬라 처리
                elif company == 'tesla':
                    if 'bought' in content or 'purchase' in content:
                        summary_parts.append("테슬라가 비트코인 직접 매입을 재개했다.")
                        summary_parts.append("일론 머스크의 영향력과 함께 시장에 상당한 관심을 불러일으킬 것으로 예상된다.")
                        summary_parts.append("기업의 비트코인 채택 확산에 긍정적 영향을 미칠 전망이다.")
                
                # 블랙록 처리
                elif company == 'blackrock':
                    if 'etf' in content:
                        if 'approved' in content:
                            summary_parts.append("세계 최대 자산운용사 블랙록의 비트코인 ETF가 승인되었다.")
                            summary_parts.append("이는 기관 자금의 대규모 유입 가능성을 열어주는 획기적 사건이다.")
                            summary_parts.append("비트코인 시장의 제도화와 주류 채택에 중요한 이정표가 될 것으로 보인다.")
                        else:
                            summary_parts.append("블랙록의 비트코인 ETF 관련 중요한 발표가 있었다.")
                            summary_parts.append("세계 최대 자산운용사의 움직임이 시장에 주목받고 있다.")
                            summary_parts.append("기관 투자자들의 비트코인 관심도가 높아지고 있음을 시사한다.")
            
            # 거시경제 패턴 처리 (새로 추가)
            if not summary_parts:
                # 관세 관련
                if any(word in content for word in ['trump', 'tariffs', 'trade war']):
                    summary_parts.append("미국의 새로운 관세 정책이 발표되었다.")
                    summary_parts.append("무역 분쟁 우려로 인해 단기적으로 리스크 자산에 부담이 될 수 있다.")
                    summary_parts.append("하지만 달러 약세 요인이 비트코인에는 중장기적으로 유리할 것으로 분석된다.")
                
                # 인플레이션 관련
                elif any(word in content for word in ['inflation', 'cpi']):
                    summary_parts.append("최신 인플레이션 데이터가 발표되었다.")
                    summary_parts.append("인플레이션 헤지 자산으로서 비트코인에 대한 관심이 높아지고 있다.")
                    summary_parts.append("실물 자산 대비 우월한 성과를 보이며 투자자들의 주목을 받고 있다.")
                
                # ETF 관련
                elif 'etf' in content:
                    if 'approved' in content or 'approval' in content:
                        summary_parts.append("비트코인 현물 ETF 승인 소식이 전해졌다.")
                        summary_parts.append("ETF 승인은 기관 투자자들의 대규모 자금 유입을 가능하게 하는 중요한 이정표다.")
                        summary_parts.append("비트코인 시장의 성숙도와 제도적 인정을 보여주는 상징적 사건으로 평가된다.")
                    elif 'rejected' in content or 'delay' in content:
                        summary_parts.append("비트코인 ETF 승인이 지연되거나 거부되었다.")
                        summary_parts.append("단기적 실망감은 있으나, 지속적인 신청은 결국 승인 가능성을 높이고 있다.")
                        summary_parts.append("시장은 이미 ETF 승인을 기정사실로 받아들이고 있어 장기 전망은 긍정적이다.")
                
                # Fed 금리 관련
                elif 'fed' in content or 'rate' in content:
                    if 'cut' in content or 'lower' in content:
                        summary_parts.append("연준의 금리 인하 결정이 발표되었다.")
                        summary_parts.append("금리 인하는 유동성 증가를 통해 비트코인과 같은 리스크 자산에 긍정적 영향을 미친다.")
                        summary_parts.append("저금리 환경에서 대안 투자처로서 비트코인의 매력도가 더욱 부각될 전망이다.")
                    elif 'hike' in content or 'increase' in content:
                        summary_parts.append("연준의 금리 인상 결정이 발표되었다.")
                        summary_parts.append("단기적으로는 부담이지만 인플레이션 헤지 자산으로서의 비트코인 가치는 지속될 것이다.")
                        summary_parts.append("고금리 환경에서도 디지털 금으로서의 역할은 변함없을 것으로 예상된다.")
                
                # 기본 케이스
                else:
                    summary_parts.append("비트코인 시장에 영향을 미칠 수 있는 발표가 있었다.")
                    summary_parts.append("투자자들은 이번 소식의 실제 시장 영향을 면밀히 분석하고 있다.")
                    summary_parts.append("단기 변동성은 있겠지만 장기 트렌드에는 큰 변화가 없을 것으로 전망된다.")
            
            return " ".join(summary_parts[:3]) if summary_parts else "비트코인 관련 소식이 발표되었다. 시장 반응을 지켜볼 필요가 있다. 투자자들은 신중한 접근이 필요하다."
            
        except Exception as e:
            logger.error(f"스마트 요약 생성 실패: {e}")
            return "비트코인 시장 관련 소식이 발표되었다. 자세한 내용은 원문을 확인하시기 바란다. 실제 시장 반응을 면밀히 분석할 필요가 있다."
    
    async def _trigger_emergency_alert_enhanced(self, article: Dict):
        """🔥🔥 강화된 긴급 알림 트리거"""
        try:
            # 이미 처리된 뉴스인지 확인
            content_hash = self._generate_content_hash(article.get('title', ''), article.get('description', ''))
            if content_hash in self.processed_news_hashes:
                return
            
            # 처리된 뉴스로 기록
            self.processed_news_hashes.add(content_hash)
            
            # 처리된 뉴스 해시 크기 제한
            if len(self.processed_news_hashes) > 5000:
                self.processed_news_hashes = set(list(self.processed_news_hashes)[-2500:])
            
            # 최초 발견 시간 기록
            if content_hash not in self.news_first_seen:
                self.news_first_seen[content_hash] = datetime.now()
            
            # 🔥🔥 강화된 이벤트 생성
            event = {
                'type': 'critical_news',
                'title': article.get('title', ''),
                'title_ko': article.get('title_ko', article.get('title', '')),
                'description': article.get('description', '')[:1600],  # 더 길게
                'summary': article.get('summary', ''),
                'company': article.get('company', ''),
                'source': article.get('source', ''),
                'url': article.get('url', ''),
                'timestamp': datetime.now(),
                'severity': 'critical',
                'impact': self._determine_impact_enhanced(article),
                'expected_change': article.get('expected_change', '±0.5%'),
                'weight': article.get('weight', 5),
                'category': article.get('category', 'unknown'),
                'published_at': article.get('published_at', ''),
                'first_seen': self.news_first_seen[content_hash],
                
                # 🔥 추가 분석 정보
                'urgency_level': self._calculate_urgency_level(article),
                'market_relevance': self._calculate_market_relevance(article),
                'pattern_match': self._match_historical_pattern_enhanced(
                    (article.get('title', '') + ' ' + article.get('description', '')).lower()
                )
            }
            
            # 파일에 저장
            self._save_duplicate_data()
            
            # 데이터 컬렉터에 전달
            if hasattr(self, 'data_collector') and self.data_collector:
                self.data_collector.events_buffer.append(event)
            
            logger.critical(f"🚨🚨 크리티컬 뉴스: {event['impact']} - {event['title_ko'][:60]}... (예상: {event['expected_change']})")
            
        except Exception as e:
            logger.error(f"긴급 알림 처리 오류: {e}")
    
    def _determine_impact_enhanced(self, article: Dict) -> str:
        """🔥🔥 강화된 뉴스 영향도 판단"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        expected_change = self._estimate_price_impact_enhanced(article)
        
        # 예상 변동률에 따른 영향도 (더 세밀하게)
        if '🚀' in expected_change or any(x in expected_change for x in ['3%', '4%', '5%']):
            return "🚀 매우 강한 호재"
        elif '📈' in expected_change and any(x in expected_change for x in ['1.5%', '2%']):
            return "📈 강한 호재"
        elif '📈' in expected_change:
            return "📈 호재"
        elif '🔻' in expected_change or any(x in expected_change for x in ['3%', '4%', '5%']):
            return "🔻 매우 강한 악재"
        elif '📉' in expected_change and any(x in expected_change for x in ['1.5%', '2%']):
            return "📉 강한 악재"
        elif '📉' in expected_change:
            return "📉 악재"
        else:
            return "⚡ 변동성 확대"
    
    def _calculate_urgency_level(self, article: Dict) -> str:
        """긴급도 레벨 계산"""
        weight = article.get('weight', 0)
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 즉시 반응이 필요한 키워드
        immediate_keywords = ['approved', 'rejected', 'announced', 'breaking', 'urgent', 'alert']
        has_immediate = any(keyword in content for keyword in immediate_keywords)
        
        if weight >= 10 and has_immediate:
            return "극도 긴급"
        elif weight >= 9:
            return "매우 긴급"
        elif weight >= 8:
            return "긴급"
        else:
            return "중요"
    
    def _calculate_market_relevance(self, article: Dict) -> str:
        """시장 관련성 계산"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 직접적 비트코인 관련
        if any(word in content for word in ['bitcoin', 'btc']):
            return "직접적"
        
        # 암호화폐 일반
        elif any(word in content for word in ['crypto', 'cryptocurrency']):
            return "암호화폐"
        
        # 거시경제
        elif any(word in content for word in ['fed', 'rate', 'inflation', 'gdp']):
            return "거시경제"
        
        # 지정학적
        elif any(word in content for word in ['war', 'sanctions', 'conflict']):
            return "지정학적"
        
        else:
            return "간접적"
    
    async def _add_to_news_buffer_enhanced(self, article: Dict):
        """🔥🔥 강화된 뉴스 버퍼 추가"""
        try:
            # 중복 체크
            content_hash = self._generate_content_hash(article.get('title', ''), article.get('description', ''))
            if content_hash in self.processed_news_hashes:
                return
            
            # 제목 유사성 체크
            new_title = article.get('title', '').lower()
            for existing in self.news_buffer:
                if self._is_similar_news_enhanced(new_title, existing.get('title', '')):
                    return
            
            # 회사별 뉴스 카운트 체크 (더 관대하게)
            for company in self.important_companies:
                if company.lower() in new_title:
                    important_keywords = ['bitcoin', 'btc', 'crypto', 'purchase', 'bought', 'investment']
                    if any(keyword in new_title for keyword in important_keywords):
                        if self.company_news_count.get(company.lower(), 0) >= 3:  # 2 → 3개로 증가
                            return
                        self.company_news_count[company.lower()] = self.company_news_count.get(company.lower(), 0) + 1
            
            # 버퍼에 추가
            self.news_buffer.append(article)
            self.processed_news_hashes.add(content_hash)
            
            # 파일에 저장
            self._save_duplicate_data()
            
            # 버퍼 크기 관리 (최대 100개로 증가)
            if len(self.news_buffer) > 100:
                # 가중치와 시간 기준 정렬
                self.news_buffer.sort(key=lambda x: (x.get('weight', 0), x.get('published_at', '')), reverse=True)
                self.news_buffer = self.news_buffer[:100]
            
            logger.debug(f"✅ 중요 뉴스 버퍼 추가: {new_title[:50]}...")
        
        except Exception as e:
            logger.error(f"뉴스 버퍼 추가 오류: {e}")
    
    def _is_similar_news_enhanced(self, title1: str, title2: str) -> bool:
        """강화된 유사 뉴스 판별"""
        # 숫자와 특수문자 제거
        clean1 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title1.lower())
        clean2 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title2.lower())
        
        clean1 = re.sub(r'\s+', ' ', clean1).strip()
        clean2 = re.sub(r'\s+', ' ', clean2).strip()
        
        # 특정 회사의 비트코인 관련 뉴스인지 체크
        for company in self.important_companies:
            company_lower = company.lower()
            if company_lower in clean1 and company_lower in clean2:
                bitcoin_keywords = ['bitcoin', 'btc', '비트코인', 'crypto', 'purchase', 'bought']
                if any(keyword in clean1 for keyword in bitcoin_keywords) and \
                   any(keyword in clean2 for keyword in bitcoin_keywords):
                    return True
        
        # 단어 집합 비교 (더 엄격하게)
        words1 = set(clean1.split())
        words2 = set(clean2.split())
        
        if not words1 or not words2:
            return False
        
        # 교집합 비율 계산
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        similarity = intersection / union if union > 0 else 0
        
        # 80% 이상 유사하면 중복 (더 엄격하게)
        return similarity > 0.8
    
    async def monitor_reddit_enhanced(self):
        """🔥🔥 강화된 Reddit 모니터링 - 5분마다"""
        reddit_subreddits = [
            {'name': 'Bitcoin', 'threshold': 300, 'weight': 9},  # 임계값 낮춤
            {'name': 'CryptoCurrency', 'threshold': 800, 'weight': 8},
            {'name': 'BitcoinMarkets', 'threshold': 200, 'weight': 9},
            {'name': 'investing', 'threshold': 1000, 'weight': 7},  # 추가
            {'name': 'Economics', 'threshold': 500, 'weight': 7},  # 추가
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
                                        
                                        if self._is_bitcoin_or_macro_related_enhanced(article):
                                            # 기업명 추출
                                            company = self._extract_company_from_content(
                                                article['title'],
                                                article.get('description', '')
                                            )
                                            if company:
                                                article['company'] = company
                                            
                                            if self._is_critical_news_enhanced(article):
                                                # Reddit에서는 번역 제한적으로만
                                                if self._should_translate(article):
                                                    article['title_ko'] = await self.translate_text(article['title'])
                                                
                                                # Reddit에서는 요약 거의 사용 안함
                                                if self._should_use_gpt_summary(article):
                                                    summary = await self.summarize_article_enhanced(
                                                        article['title'],
                                                        article.get('description', '')
                                                    )
                                                    if summary:
                                                        article['summary'] = summary
                                                
                                                if not self._is_duplicate_emergency(article):
                                                    article['expected_change'] = self._estimate_price_impact_enhanced(article)
                                                    await self._trigger_emergency_alert_enhanced(article)
                                            
                                            elif self._is_important_news_enhanced(article):
                                                await self._add_to_news_buffer_enhanced(article)
                    
                    except Exception as e:
                        logger.warning(f"Reddit 오류 {sub_info['name']}: {str(e)[:50]}")
                
                await asyncio.sleep(300)  # 5분마다
                
            except Exception as e:
                logger.error(f"Reddit 모니터링 오류: {e}")
                await asyncio.sleep(600)
    
    async def aggressive_api_rotation_enhanced(self):
        """🔥🔥 강화된 API 순환 사용"""
        while True:
            try:
                self._reset_daily_usage()
                
                # NewsAPI (더 자주)
                if self.newsapi_key and self.api_usage['newsapi_today'] < self.api_limits['newsapi']:
                    try:
                        await self._call_newsapi_enhanced()
                        self.api_usage['newsapi_today'] += 1
                        logger.info(f"✅ NewsAPI 호출 ({self.api_usage['newsapi_today']}/{self.api_limits['newsapi']})")
                    except Exception as e:
                        logger.error(f"NewsAPI 오류: {str(e)[:100]}")
                
                await asyncio.sleep(600)  # 10분 대기
                
                # NewsData API
                if self.newsdata_key and self.api_usage['newsdata_today'] < self.api_limits['newsdata']:
                    try:
                        await self._call_newsdata_enhanced()
                        self.api_usage['newsdata_today'] += 1
                        logger.info(f"✅ NewsData 호출 ({self.api_usage['newsdata_today']}/{self.api_limits['newsdata']})")
                    except Exception as e:
                        logger.error(f"NewsData 오류: {str(e)[:100]}")
                
                await asyncio.sleep(600)  # 10분 대기
                
                # Alpha Vantage
                if self.alpha_vantage_key and self.api_usage['alpha_vantage_today'] < self.api_limits['alpha_vantage']:
                    try:
                        await self._call_alpha_vantage_enhanced()
                        self.api_usage['alpha_vantage_today'] += 1
                        logger.info(f"✅ Alpha Vantage 호출 ({self.api_usage['alpha_vantage_today']}/{self.api_limits['alpha_vantage']})")
                    except Exception as e:
                        logger.error(f"Alpha Vantage 오류: {str(e)[:100]}")
                
                await asyncio.sleep(1200)  # 20분 대기
                
            except Exception as e:
                logger.error(f"API 순환 오류: {e}")
                await asyncio.sleep(1800)
    
    async def _call_newsapi_enhanced(self):
        """🔥🔥 강화된 NewsAPI 호출"""
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': '(bitcoin OR btc OR "bitcoin etf" OR "fed rate" OR "trump tariffs" OR "trade deal" OR "inflation data" OR "china manufacturing" OR "powell speech" OR "fomc decision" OR "cpi report" OR "unemployment rate" OR "sec bitcoin" OR "tesla bitcoin" OR "microstrategy bitcoin" OR "blackrock bitcoin" OR "russia bitcoin" OR "ukraine war" OR "china sanctions") AND NOT ("altcoin only" OR "how to mine" OR "price prediction tutorial")',
                'language': 'en',
                'sortBy': 'publishedAt',
                'apiKey': self.newsapi_key,
                'pageSize': 100,  # 50 → 100으로 증가
                'from': (datetime.now() - timedelta(hours=3)).isoformat()  # 6시간 → 3시간으로 단축 (더 빠른 감지)
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('articles', [])
                    
                    processed = 0
                    critical_found = 0
                    translated_count = 0
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
                        
                        if self._is_bitcoin_or_macro_related_enhanced(formatted_article):
                            # 기업명 추출
                            company = self._extract_company_from_content(
                                formatted_article['title'],
                                formatted_article.get('description', '')
                            )
                            if company:
                                formatted_article['company'] = company
                            
                            # 번역 - Claude 우선 사용
                            if self._should_translate(formatted_article):
                                formatted_article['title_ko'] = await self.translate_text(formatted_article['title'])
                                translated_count += 1
                            
                            if self._is_critical_news_enhanced(formatted_article):
                                # 요약 (선택적)
                                if self._should_use_gpt_summary(formatted_article):
                                    summary = await self.summarize_article_enhanced(
                                        formatted_article['title'],
                                        formatted_article.get('description', '')
                                    )
                                    if summary:
                                        formatted_article['summary'] = summary
                                
                                if not self._is_duplicate_emergency(formatted_article):
                                    formatted_article['expected_change'] = self._estimate_price_impact_enhanced(formatted_article)
                                    await self._trigger_emergency_alert_enhanced(formatted_article)
                                processed += 1
                                critical_found += 1
                            elif self._is_important_news_enhanced(formatted_article):
                                await self._add_to_news_buffer_enhanced(formatted_article)
                                processed += 1
                    
                    if processed > 0:
                        logger.info(f"🔥 NewsAPI: {processed}개 관련 뉴스 처리 (크리티컬: {critical_found}개, 번역: {translated_count}개)")
                else:
                    logger.warning(f"NewsAPI 응답 오류: {response.status}")
        
        except Exception as e:
            logger.error(f"NewsAPI 호출 오류: {e}")
    
    async def _call_newsdata_enhanced(self):
        """🔥🔥 강화된 NewsData API 호출"""
        try:
            url = "https://newsdata.io/api/1/news"
            params = {
                'apikey': self.newsdata_key,
                'q': 'bitcoin OR btc OR "bitcoin etf" OR "bitcoin regulation" OR "russia bitcoin" OR "sberbank bitcoin" OR "fed rate decision" OR "trump tariffs" OR "trade deal" OR "inflation data" OR "china manufacturing" OR "powell speech" OR "fomc decision" OR "tesla bitcoin" OR "microstrategy bitcoin" OR "sec bitcoin" OR "ukraine war" OR "china sanctions"',
                'language': 'en',
                'category': 'business,top,politics',  # 카테고리 확장
                'size': 50  # 30 → 50으로 증가
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('results', [])
                    
                    processed = 0
                    critical_found = 0
                    translated_count = 0
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
                        
                        if self._is_bitcoin_or_macro_related_enhanced(formatted_article):
                            # 기업명 추출
                            company = self._extract_company_from_content(
                                formatted_article['title'],
                                formatted_article.get('description', '')
                            )
                            if company:
                                formatted_article['company'] = company
                            
                            # 번역 - Claude 우선 사용
                            if self._should_translate(formatted_article):
                                formatted_article['title_ko'] = await self.translate_text(formatted_article['title'])
                                translated_count += 1
                            
                            if self._is_critical_news_enhanced(formatted_article):
                                # 요약 (선택적)
                                if self._should_use_gpt_summary(formatted_article):
                                    summary = await self.summarize_article_enhanced(
                                        formatted_article['title'],
                                        formatted_article.get('description', '')
                                    )
                                    if summary:
                                        formatted_article['summary'] = summary
                                
                                if not self._is_duplicate_emergency(formatted_article):
                                    formatted_article['expected_change'] = self._estimate_price_impact_enhanced(formatted_article)
                                    await self._trigger_emergency_alert_enhanced(formatted_article)
                                processed += 1
                                critical_found += 1
                            elif self._is_important_news_enhanced(formatted_article):
                                await self._add_to_news_buffer_enhanced(formatted_article)
                                processed += 1
                    
                    if processed > 0:
                        logger.info(f"🔥 NewsData: {processed}개 관련 뉴스 처리 (크리티컬: {critical_found}개, 번역: {translated_count}개)")
                else:
                    logger.warning(f"NewsData 응답 오류: {response.status}")
        
        except Exception as e:
            logger.error(f"NewsData 호출 오류: {e}")
    
    async def _call_alpha_vantage_enhanced(self):
        """🔥🔥 강화된 Alpha Vantage API 호출"""
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': 'CRYPTO:BTC,TSLA,MSTR',  # 티커 확장
                'topics': 'financial_markets,technology,earnings,economy',  # 토픽 확장
                'apikey': self.alpha_vantage_key,
                'sort': 'LATEST',
                'limit': 50  # 20 → 50으로 증가
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('feed', [])
                    
                    processed = 0
                    critical_found = 0
                    translated_count = 0
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
                        
                        if self._is_bitcoin_or_macro_related_enhanced(formatted_article):
                            # 기업명 추출
                            company = self._extract_company_from_content(
                                formatted_article['title'],
                                formatted_article.get('description', '')
                            )
                            if company:
                                formatted_article['company'] = company
                            
                            # 번역 - Claude 우선 사용
                            if self._should_translate(formatted_article):
                                formatted_article['title_ko'] = await self.translate_text(formatted_article['title'])
                                translated_count += 1
                            
                            if self._is_critical_news_enhanced(formatted_article):
                                # 요약 (선택적)
                                if self._should_use_gpt_summary(formatted_article):
                                    summary = await self.summarize_article_enhanced(
                                        formatted_article['title'],
                                        formatted_article.get('description', '')
                                    )
                                    if summary:
                                        formatted_article['summary'] = summary
                                
                                if not self._is_duplicate_emergency(formatted_article):
                                    formatted_article['expected_change'] = self._estimate_price_impact_enhanced(formatted_article)
                                    await self._trigger_emergency_alert_enhanced(formatted_article)
                                processed += 1
                                critical_found += 1
                            elif self._is_important_news_enhanced(formatted_article):
                                await self._add_to_news_buffer_enhanced(formatted_article)
                                processed += 1
                    
                    if processed > 0:
                        logger.info(f"🔥 Alpha Vantage: {processed}개 관련 뉴스 처리 (크리티컬: {critical_found}개, 번역: {translated_count}개)")
                else:
                    logger.warning(f"Alpha Vantage 응답 오류: {response.status}")
        
        except Exception as e:
            logger.error(f"Alpha Vantage 호출 오류: {e}")
    
    async def _parse_rss_feed_enhanced(self, feed_info: Dict) -> List[Dict]:
        """🔥🔥 강화된 RSS 피드 파싱"""
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
                        # 더 많은 기사 처리
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
                                logger.debug(f"기사 파싱 오류: {str(e)[:50]}")
                                continue
        
        except asyncio.TimeoutError:
            logger.debug(f"⏰ {feed_info['source']}: 타임아웃")
        except Exception as e:
            logger.debug(f"❌ {feed_info['source']}: {str(e)[:50]}")
        
        return articles
    
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
        
        return ""
    
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
            self.claude_translation_count = 0
            self.gpt_translation_count = 0
            self.summary_count = 0
            self.last_translation_reset = datetime.now()
            self.last_summary_reset = datetime.now()
            self.news_first_seen = {}
            logger.info(f"🔄 일일 리셋 완료 (Claude: {self.max_claude_translations_per_15min}/15분, GPT: {self.max_gpt_translations_per_15min}/15분, 요약: {self.max_summaries_per_15min}/15분)")
    
    async def get_recent_news_enhanced(self, hours: int = 12) -> List[Dict]:
        """🔥🔥 강화된 최근 뉴스 가져오기"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_news = []
            seen_hashes = set()
            
            # 더 많은 뉴스 반환
            for article in sorted(self.news_buffer, key=lambda x: (x.get('weight', 0), x.get('published_at', '')), reverse=True):
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
            
            logger.info(f"🔥 최근 {hours}시간 뉴스: {len(recent_news)}개 (총 버퍼: {len(self.news_buffer)}개)")
            
            return recent_news[:25]  # 15 → 25개로 증가
            
        except Exception as e:
            logger.error(f"최근 뉴스 조회 오류: {e}")
            return []
    
    async def get_recent_news(self, hours: int = 12) -> List[Dict]:
        """최근 뉴스 가져오기 (호환성을 위한 래퍼)"""
        return await self.get_recent_news_enhanced(hours)
    
    def _is_critical_news(self, article: Dict) -> bool:
        """기존 호환성을 위한 메서드"""
        return self._is_critical_news_enhanced(article)
    
    async def close(self):
        """세션 종료"""
        try:
            # 중복 방지 데이터 저장
            self._save_duplicate_data()
            
            if self.session:
                await self.session.close()
                logger.info("🔚 Claude 우선 번역 뉴스 수집기 세션 종료")
                logger.info(f"🤖 최종 Claude 번역: {self.claude_translation_count}, GPT 번역: {self.gpt_translation_count}")
                logger.info(f"📝 최종 GPT 요약: {self.summary_count}")
        except Exception as e:
            logger.error(f"세션 종료 중 오류: {e}")
