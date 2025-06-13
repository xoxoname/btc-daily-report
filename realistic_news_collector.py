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
import random

logger = logging.getLogger(__name__)

class RealisticNewsCollector:
    def __init__(self, config):
        self.config = config
        self.session = None
        self.news_buffer = []
        self.emergency_alerts_sent = {}
        self.processed_news_hashes = set()
        self.news_title_cache = {}
        self.company_news_count = {}
        self.news_first_seen = {}
        
        # 중복 방지 데이터 파일
        self.persistence_file = 'news_duplicates.json'
        self.processed_reports_file = 'processed_critical_reports.json'
        
        # 전송된 뉴스 제목 캐시
        self.sent_news_titles = {}
        self.sent_critical_reports = {}
        
        # 번역 사용량 추적
        self.translation_cache = {}
        self.claude_translation_count = 0
        self.gpt_translation_count = 0
        self.claude_error_count = 0
        self.last_translation_reset = datetime.now()
        self.max_claude_translations_per_15min = 15
        self.max_gpt_translations_per_15min = 30
        self.translation_reset_interval = 900
        self.claude_cooldown_until = None
        self.claude_cooldown_duration = 300
        
        # Claude API 클라이언트 초기화
        self.anthropic_client = None
        if hasattr(config, 'ANTHROPIC_API_KEY') and config.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self.anthropic_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
                logger.info("✅ Claude API 클라이언트 초기화 완료")
            except ImportError:
                logger.warning("❌ anthropic 라이브러리가 설치되지 않음")
            except Exception as e:
                logger.warning(f"Claude API 초기화 실패: {e}")
        
        # OpenAI 클라이언트 초기화
        self.openai_client = None
        if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY:
            self.openai_client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        
        # GPT 요약 사용량 제한
        self.summary_count = 0
        self.max_summaries_per_15min = 25
        self.last_summary_reset = datetime.now()
        
        # API 키들
        self.newsapi_key = getattr(config, 'NEWSAPI_KEY', None)
        self.newsdata_key = getattr(config, 'NEWSDATA_KEY', None)
        self.alpha_vantage_key = getattr(config, 'ALPHA_VANTAGE_KEY', None)
        
        # 🔥🔥 크리티컬 키워드 (기준 완화)
        self.critical_keywords = [
            # 비트코인 ETF
            'bitcoin etf approved', 'bitcoin etf rejected', 'spot bitcoin etf', 'etf decision',
            'blackrock bitcoin etf', 'fidelity bitcoin etf', 'bitcoin etf launches',
            'SEC approves bitcoin', 'SEC rejects bitcoin', 'bitcoin etf trading',
            
            # 기업 비트코인 구매
            'tesla bought bitcoin', 'microstrategy bought bitcoin', 'bought bitcoin', 'buys bitcoin',
            'gamestop bitcoin purchase', 'bitcoin acquisition', 'adds bitcoin',
            'purchases bitcoin', 'bitcoin investment', 'bitcoin holdings',
            
            # 국가/은행 채택
            'russia bitcoin', 'sberbank bitcoin', 'bitcoin bonds', 'government bitcoin',
            'country adopts bitcoin', 'central bank bitcoin', 'china bitcoin',
            'putin bitcoin', 'russia legalize bitcoin',
            
            # 비트코인 규제
            'bitcoin ban', 'bitcoin regulation', 'bitcoin lawsuit', 'sec bitcoin',
            'china bans bitcoin', 'government bans bitcoin', 'trump bitcoin',
            'regulatory approval bitcoin', 'coinbase lawsuit',
            
            # 비트코인 가격 이정표
            'bitcoin crosses 100k', 'bitcoin hits 100000', 'bitcoin 100k',
            'bitcoin all time high', 'bitcoin ath', 'bitcoin breaks',
            'bitcoin reaches', 'bitcoin milestone',
            
            # Fed 금리 및 거시경제
            'fed rate decision', 'fomc decision', 'powell speech', 'interest rate decision',
            'fed minutes', 'inflation report', 'cpi data', 'unemployment rate',
            
            # 무역/관세
            'trump tariffs', 'china tariffs', 'trade war', 'trade deal',
            'trade agreement', 'tariff announcement',
            
            # 기타 중요
            'bitcoin hack', 'bitcoin stolen', 'exchange hacked bitcoin',
            'whale alert bitcoin', 'large bitcoin transfer'
        ]
        
        # 제외 키워드
        self.exclude_keywords = [
            'how to mine', 'mining tutorial', 'price prediction tutorial',
            'altcoin only', 'ethereum only', 'nft only', 'defi only',
            'celebrity news', 'entertainment', 'sports', 'weather'
        ]
        
        # 중요 기업
        self.important_companies = [
            'tesla', 'microstrategy', 'square', 'block', 'paypal',
            'gamestop', 'gme', 'blackrock', 'fidelity', 'ark invest',
            'coinbase', 'binance', 'kraken', 'bitget',
            'metaplanet', 'sberbank', 'jpmorgan', 'goldman sachs'
        ]
        
        # 🔥🔥 User-Agent 로테이션 (403 오류 해결)
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0'
        ]
        
        # 🔥🔥 RSS 피드 개선 (403 오류 피드 제거/교체)
        self.rss_feeds = [
            # 암호화폐 전문 (문제없는 피드만)
            {'url': 'https://cointelegraph.com/rss', 'source': 'Cointelegraph', 'weight': 10, 'category': 'crypto'},
            {'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/', 'source': 'CoinDesk', 'weight': 10, 'category': 'crypto'},
            {'url': 'https://decrypt.co/feed', 'source': 'Decrypt', 'weight': 9, 'category': 'crypto'},
            {'url': 'https://bitcoinmagazine.com/.rss/full/', 'source': 'Bitcoin Magazine', 'weight': 10, 'category': 'crypto'},
            {'url': 'https://cryptopotato.com/feed/', 'source': 'CryptoPotato', 'weight': 8, 'category': 'crypto'},
            {'url': 'https://u.today/rss', 'source': 'U.Today', 'weight': 8, 'category': 'crypto'},
            # CryptoSlate 제거 (403 오류)
            {'url': 'https://cryptonews.com/news/feed/', 'source': 'Cryptonews', 'weight': 8, 'category': 'crypto'},
            {'url': 'https://www.newsbtc.com/feed/', 'source': 'NewsBTC', 'weight': 8, 'category': 'crypto'},
            {'url': 'https://beincrypto.com/feed/', 'source': 'BeInCrypto', 'weight': 8, 'category': 'crypto'},
            
            # 금융 뉴스
            {'url': 'https://www.marketwatch.com/rss/topstories', 'source': 'MarketWatch', 'weight': 8, 'category': 'finance'},
            {'url': 'https://feeds.reuters.com/reuters/businessNews', 'source': 'Reuters Business', 'weight': 8, 'category': 'news'},
            {'url': 'https://feeds.cnbc.com/cnbc/ID/100003114/device/rss/rss.html', 'source': 'CNBC Markets', 'weight': 8, 'category': 'finance'},
            
            # 기술 뉴스
            {'url': 'https://techcrunch.com/feed/', 'source': 'TechCrunch', 'weight': 7, 'category': 'tech'}
        ]
        
        # API 사용량 추적
        self.api_usage = {
            'newsapi_today': 0,
            'newsdata_today': 0,
            'alpha_vantage_today': 0,
            'last_reset': datetime.now().date()
        }
        
        # API 한도
        self.api_limits = {
            'newsapi': 60,
            'newsdata': 30,
            'alpha_vantage': 8
        }
        
        # 뉴스 처리 통계
        self.processing_stats = {
            'total_articles_checked': 0,
            'bitcoin_related_found': 0,
            'critical_news_found': 0,
            'important_news_found': 0,
            'alerts_sent': 0,
            'translation_attempts': 0,
            'translation_successes': 0,
            'api_errors': 0,
            'rss_errors': 0,
            'last_reset': datetime.now()
        }
        
        # 중복 방지 데이터 로드
        self._load_duplicate_data()
        self._load_critical_reports()
        
        logger.info(f"🔥🔥 뉴스 수집기 초기화 완료 (403 오류 해결 버전)")
        logger.info(f"🧠 GPT API: {'활성화' if self.openai_client else '비활성화'}")
        logger.info(f"🤖 Claude API: {'활성화' if self.anthropic_client else '비활성화'}")
        logger.info(f"🎯 크리티컬 키워드: {len(self.critical_keywords)}개")
        logger.info(f"🏢 추적 기업: {len(self.important_companies)}개")
        logger.info(f"📡 RSS 소스: {len(self.rss_feeds)}개 (403 오류 피드 제거)")
        
        # 🔥🔥 중복 방지 기준 완화 설정
        self.duplicate_check_hours = 2  # 2시간 이내 중복만 체크 (기존 4시간에서 완화)
        self.critical_report_cooldown_minutes = 60  # 1시간 쿨다운 (기존 240분에서 완화)
    
    def _get_random_user_agent(self) -> str:
        """랜덤 User-Agent 반환"""
        return random.choice(self.user_agents)
    
    def _load_duplicate_data(self):
        """중복 방지 데이터 로드"""
        try:
            if os.path.exists(self.persistence_file):
                with open(self.persistence_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.processed_news_hashes = set(data.get('processed_news_hashes', []))
                
                # 긴급 알림 데이터 로드 (시간 완화)
                emergency_data = data.get('emergency_alerts_sent', {})
                current_time = datetime.now()
                cutoff_time = current_time - timedelta(hours=self.duplicate_check_hours)
                
                for hash_key, time_str in emergency_data.items():
                    try:
                        alert_time = datetime.fromisoformat(time_str)
                        if alert_time > cutoff_time:
                            self.emergency_alerts_sent[hash_key] = alert_time
                    except:
                        continue
                
                # 제목 캐시 로드 (시간 완화)
                title_data = data.get('sent_news_titles', {})
                cutoff_time = current_time - timedelta(hours=self.duplicate_check_hours)
                
                for title_hash, time_str in title_data.items():
                    try:
                        sent_time = datetime.fromisoformat(time_str)
                        if sent_time > cutoff_time:
                            self.sent_news_titles[title_hash] = sent_time
                    except:
                        continue
                
                # 크기 제한
                if len(self.processed_news_hashes) > 2000:
                    self.processed_news_hashes = set(list(self.processed_news_hashes)[-1000:])
                
                logger.info(f"중복 방지 데이터 로드: {len(self.processed_news_hashes)}개 (기준 완화: {self.duplicate_check_hours}시간)")
                
        except Exception as e:
            logger.warning(f"중복 방지 데이터 로드 실패: {e}")
            self.processed_news_hashes = set()
            self.emergency_alerts_sent = {}
            self.sent_news_titles = {}
    
    def _load_critical_reports(self):
        """크리티컬 리포트 중복 방지 데이터 로드"""
        try:
            if os.path.exists(self.processed_reports_file):
                with open(self.processed_reports_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                current_time = datetime.now()
                cutoff_time = current_time - timedelta(minutes=self.critical_report_cooldown_minutes)
                
                for item in data:
                    try:
                        report_time = datetime.fromisoformat(item['time'])
                        if report_time > cutoff_time:
                            self.sent_critical_reports[item['hash']] = report_time
                    except:
                        continue
                
                logger.info(f"크리티컬 리포트 중복 방지: {len(self.sent_critical_reports)}개 (쿨다운: {self.critical_report_cooldown_minutes}분)")
                
        except Exception as e:
            logger.warning(f"크리티컬 리포트 데이터 로드 실패: {e}")
            self.sent_critical_reports = {}
    
    def _save_duplicate_data(self):
        """중복 방지 데이터 저장"""
        try:
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
                
        except Exception as e:
            logger.error(f"중복 방지 데이터 저장 실패: {e}")
    
    def _save_critical_reports(self):
        """크리티컬 리포트 중복 방지 데이터 저장"""
        try:
            data_to_save = []
            for report_hash, report_time in self.sent_critical_reports.items():
                data_to_save.append({
                    'hash': report_hash,
                    'time': report_time.isoformat()
                })
            
            with open(self.processed_reports_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"크리티컬 리포트 데이터 저장 실패: {e}")
    
    def _reset_translation_count_if_needed(self):
        """번역 카운트 리셋"""
        now = datetime.now()
        if (now - self.last_translation_reset).total_seconds() > self.translation_reset_interval:
            old_claude_count = self.claude_translation_count
            old_gpt_count = self.gpt_translation_count
            old_error_count = self.claude_error_count
            self.claude_translation_count = 0
            self.gpt_translation_count = 0
            self.claude_error_count = 0
            self.last_translation_reset = now
            
            if self.claude_cooldown_until and now > self.claude_cooldown_until:
                self.claude_cooldown_until = None
                logger.info("Claude 쿨다운 해제")
            
            if old_claude_count > 0 or old_gpt_count > 0:
                logger.info(f"번역 카운트 리셋: GPT {old_gpt_count} → 0, Claude {old_claude_count} → 0")
    
    def _reset_summary_count_if_needed(self):
        """요약 카운트 리셋"""
        now = datetime.now()
        if (now - self.last_summary_reset).total_seconds() > self.translation_reset_interval:
            old_count = self.summary_count
            self.summary_count = 0
            self.last_summary_reset = now
            if old_count > 0:
                logger.info(f"요약 카운트 리셋: {old_count} → 0")
    
    def _should_translate_for_emergency_report(self, article: Dict) -> bool:
        """긴급 리포트 전송 시에만 번역"""
        if not self._is_critical_news_enhanced(article):
            return False
            
        if article.get('title_ko') and article['title_ko'] != article.get('title', ''):
            return False
        
        self._reset_translation_count_if_needed()
        
        can_use_gpt = self.openai_client and self.gpt_translation_count < self.max_gpt_translations_per_15min
        can_use_claude = self._is_claude_available()
        
        return can_use_gpt or can_use_claude
    
    def _is_claude_available(self) -> bool:
        """Claude API 사용 가능 여부 확인"""
        if not self.anthropic_client:
            return False
        
        if self.claude_cooldown_until and datetime.now() < self.claude_cooldown_until:
            return False
        
        self._reset_translation_count_if_needed()
        
        if self.claude_translation_count >= self.max_claude_translations_per_15min:
            return False
        
        if self.claude_error_count >= 2:
            self.claude_cooldown_until = datetime.now() + timedelta(seconds=self.claude_cooldown_duration)
            logger.warning(f"Claude API 에러 {self.claude_error_count}회, 쿨다운 시작")
            return False
        
        return True
    
    async def translate_text_with_claude(self, text: str, max_length: int = 400) -> str:
        """Claude API 번역"""
        if not self._is_claude_available():
            return ""
        
        cache_key = f"claude_{hashlib.md5(text.encode()).hexdigest()}"
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]
        
        try:
            self.processing_stats['translation_attempts'] += 1
            
            response = await self.anthropic_client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                timeout=10.0,
                messages=[{
                    "role": "user", 
                    "content": f"""다음 영문 뉴스 제목을 자연스러운 한국어로 번역해주세요.

최대 {max_length}자 이내로 번역하세요.

제목: {text}"""
                }]
            )
            
            translated = response.content[0].text.strip()
            
            if len(translated) > max_length:
                translated = translated[:max_length-3] + "..."
            
            self.translation_cache[cache_key] = translated
            self.claude_translation_count += 1
            self.processing_stats['translation_successes'] += 1
            
            # 캐시 크기 제한
            if len(self.translation_cache) > 300:
                keys_to_remove = list(self.translation_cache.keys())[:150]
                for key in keys_to_remove:
                    del self.translation_cache[key]
            
            logger.info(f"🤖 Claude 번역 완료 ({self.claude_translation_count}/{self.max_claude_translations_per_15min})")
            return translated
            
        except Exception as e:
            self.claude_error_count += 1
            self.processing_stats['api_errors'] += 1
            error_str = str(e)
            
            if "529" in error_str or "rate" in error_str.lower():
                self.claude_cooldown_until = datetime.now() + timedelta(minutes=30)
                logger.warning(f"Claude API rate limit, 30분 쿨다운")
            else:
                logger.warning(f"Claude 번역 실패: {error_str[:50]}")
            
            return ""
    
    async def translate_text_with_gpt(self, text: str, max_length: int = 400) -> str:
        """GPT API 번역"""
        if not self.openai_client:
            return text
        
        self._reset_translation_count_if_needed()
        
        if self.gpt_translation_count >= self.max_gpt_translations_per_15min:
            logger.warning(f"GPT 번역 한도 초과: {self.gpt_translation_count}/{self.max_gpt_translations_per_15min}")
            return text
        
        cache_key = f"gpt_{hashlib.md5(text.encode()).hexdigest()}"
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]
        
        try:
            self.processing_stats['translation_attempts'] += 1
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "비트코인 전문 번역가입니다. 영문을 자연스러운 한국어로 번역하세요."},
                    {"role": "user", "content": f"다음을 한국어로 번역 (최대 {max_length}자):\n\n{text}"}
                ],
                max_tokens=150,
                temperature=0.2,
                timeout=15.0
            )
            
            translated = response.choices[0].message.content.strip()
            
            if len(translated) > max_length:
                translated = translated[:max_length-3] + "..."
            
            self.translation_cache[cache_key] = translated
            self.gpt_translation_count += 1
            self.processing_stats['translation_successes'] += 1
            
            logger.info(f"🧠 GPT 번역 완료 ({self.gpt_translation_count}/{self.max_gpt_translations_per_15min})")
            return translated
            
        except Exception as e:
            self.processing_stats['api_errors'] += 1
            logger.warning(f"GPT 번역 실패: {str(e)[:50]}")
            return text
    
    async def translate_text(self, text: str, max_length: int = 400) -> str:
        """통합 번역 함수 - GPT 우선, Claude 보조"""
        try:
            # GPT 우선
            if self.openai_client:
                result = await self.translate_text_with_gpt(text, max_length)
                if result != text:
                    return result
            
            # Claude 보조
            if self._is_claude_available():
                result = await self.translate_text_with_claude(text, max_length)
                if result:
                    return result
            
            return text
            
        except Exception as e:
            logger.error(f"번역 함수 오류: {e}")
            return text
    
    def _should_use_gpt_summary(self, article: Dict) -> bool:
        """GPT 요약 사용 여부 결정"""
        self._reset_summary_count_if_needed()
        
        if self.summary_count >= self.max_summaries_per_15min:
            return False
        
        if not self._is_critical_news_enhanced(article):
            return False
        
        description = article.get('description', '')
        if len(description) < 100:
            return False
        
        return True
    
    def _generate_content_hash(self, title: str, description: str = "") -> str:
        """뉴스 내용 해시 생성"""
        content = f"{title} {description[:200]}".lower()
        
        # 숫자 정규화
        content = re.sub(r'[\d,]+', lambda m: m.group(0).replace(',', ''), content)
        
        # 회사명 추출
        companies_found = []
        for company in self.important_companies:
            if company.lower() in content:
                companies_found.append(company.lower())
        
        # 액션 키워드 추출
        action_keywords = []
        actions = ['bought', 'purchased', 'acquired', 'adds', 'buys', 'sells', 'sold', 
                  'announced', 'launches', 'approves', 'rejects', 'bans', 'crosses', 'hits']
        for action in actions:
            if action in content:
                action_keywords.append(action)
        
        # 고유 식별자 생성
        unique_parts = []
        if companies_found:
            unique_parts.append('_'.join(sorted(companies_found)))
        if action_keywords:
            unique_parts.append('_'.join(sorted(action_keywords)))
        
        if unique_parts:
            hash_content = '|'.join(unique_parts)
        else:
            words = re.findall(r'\b[a-z]{4,}\b', content)
            important_words = [w for w in words if w not in ['that', 'this', 'with', 'from', 'have', 'been']]
            hash_content = ' '.join(sorted(important_words[:8]))
        
        return hashlib.md5(hash_content.encode()).hexdigest()
    
    def _is_duplicate_emergency(self, article: Dict, time_window: int = None) -> bool:
        """🔥🔥 긴급 알림 중복 확인 (기준 대폭 완화)"""
        try:
            if time_window is None:
                time_window = self.critical_report_cooldown_minutes
                
            current_time = datetime.now()
            content_hash = self._generate_content_hash(
                article.get('title', ''), 
                article.get('description', '')
            )
            
            # 크리티컬 리포트 중복 체크
            if content_hash in self.sent_critical_reports:
                last_sent = self.sent_critical_reports[content_hash]
                time_since_last = current_time - last_sent
                
                if time_since_last < timedelta(minutes=time_window):
                    logger.info(f"🔄 중복 크리티컬 리포트 방지 ({time_window}분): {article.get('title', '')[:50]}...")
                    return True
            
            # 새로운 크리티컬 리포트로 기록
            self.sent_critical_reports[content_hash] = current_time
            
            # 오래된 기록 정리
            cutoff_time = current_time - timedelta(hours=4)
            self.sent_critical_reports = {
                k: v for k, v in self.sent_critical_reports.items()
                if v > cutoff_time
            }
            
            self._save_critical_reports()
            
            # 기존 알림 체크
            cutoff_time = current_time - timedelta(minutes=time_window)
            self.emergency_alerts_sent = {
                k: v for k, v in self.emergency_alerts_sent.items()
                if v > cutoff_time
            }
            
            if content_hash in self.emergency_alerts_sent:
                logger.info(f"🔄 중복 긴급 알림 방지: {article.get('title', '')[:50]}...")
                return True
            
            self.emergency_alerts_sent[content_hash] = current_time
            self._save_duplicate_data()
            
            return False
            
        except Exception as e:
            logger.error(f"중복 체크 오류: {e}")
            return False
    
    def _is_recent_news(self, article: Dict, hours: int = 6) -> bool:
        """뉴스 최신성 확인 (6시간으로 확장)"""
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
        """🔥🔥 모니터링 시작 (403 오류 해결 버전)"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20),
                connector=aiohttp.TCPConnector(limit=100, limit_per_host=30)
            )
        
        logger.info("🔥🔥 뉴스 모니터링 시작 (403 오류 해결 + 기준 완화)")
        logger.info(f"🧠 GPT API: {'활성화' if self.openai_client else '비활성화'}")
        logger.info(f"🤖 Claude API: {'활성화' if self.anthropic_client else '비활성화'}")
        logger.info(f"📊 RSS 체크: 3초마다")
        logger.info(f"🔄 중복 체크: {self.duplicate_check_hours}시간")
        logger.info(f"⏰ 크리티컬 쿨다운: {self.critical_report_cooldown_minutes}분")
        logger.info(f"🎯 크리티컬 키워드: {len(self.critical_keywords)}개")
        logger.info(f"📡 RSS 소스: {len(self.rss_feeds)}개")
        
        self.company_news_count = {}
        
        tasks = [
            self.monitor_rss_feeds_enhanced(),
            self.monitor_reddit_enhanced(),
            self.aggressive_api_rotation_enhanced(),
            self.log_stats_periodically()
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def log_stats_periodically(self):
        """정기적 통계 로그"""
        while True:
            try:
                await asyncio.sleep(1800)  # 30분마다
                self._log_processing_stats()
            except Exception as e:
                logger.error(f"통계 로그 오류: {e}")
                await asyncio.sleep(1800)
    
    def _log_processing_stats(self):
        """처리 통계 로그"""
        try:
            current_time = datetime.now()
            time_since_reset = current_time - self.processing_stats['last_reset']
            hours = time_since_reset.total_seconds() / 3600
            
            if hours >= 0.5:
                stats = self.processing_stats
                logger.info(f"📊 뉴스 처리 통계 (최근 {hours:.1f}시간):")
                logger.info(f"  총 기사 확인: {stats['total_articles_checked']}개")
                logger.info(f"  비트코인 관련: {stats['bitcoin_related_found']}개")
                logger.info(f"  크리티컬 발견: {stats['critical_news_found']}개")
                logger.info(f"  중요 뉴스: {stats['important_news_found']}개")
                logger.info(f"  알림 전송: {stats['alerts_sent']}개")
                
                if stats['total_articles_checked'] > 0:
                    bitcoin_rate = stats['bitcoin_related_found'] / stats['total_articles_checked'] * 100
                    logger.info(f"  비트코인 관련률: {bitcoin_rate:.1f}%")
                
                if stats['bitcoin_related_found'] > 0:
                    critical_rate = stats['critical_news_found'] / stats['bitcoin_related_found'] * 100
                    logger.info(f"  크리티컬 비율: {critical_rate:.1f}%")
                
                # 통계 리셋
                self.processing_stats = {
                    'total_articles_checked': 0,
                    'bitcoin_related_found': 0,
                    'critical_news_found': 0,
                    'important_news_found': 0,
                    'alerts_sent': 0,
                    'translation_attempts': 0,
                    'translation_successes': 0,
                    'api_errors': 0,
                    'rss_errors': 0,
                    'last_reset': current_time
                }
        except Exception as e:
            logger.error(f"통계 로그 오류: {e}")
    
    async def monitor_rss_feeds_enhanced(self):
        """🔥🔥 RSS 피드 모니터링 (403 오류 해결)"""
        consecutive_errors = 0
        max_consecutive_errors = 8
        
        while True:
            try:
                sorted_feeds = sorted(self.rss_feeds, key=lambda x: x['weight'], reverse=True)
                successful_feeds = 0
                processed_articles = 0
                critical_found = 0
                
                for feed_info in sorted_feeds:
                    try:
                        articles = await self._parse_rss_feed_enhanced(feed_info)
                        
                        if articles:
                            successful_feeds += 1
                            
                            for article in articles:
                                self.processing_stats['total_articles_checked'] += 1
                                
                                try:
                                    # 최신 뉴스만 처리 (6시간으로 확장)
                                    if not self._is_recent_news(article, hours=6):
                                        continue
                                    
                                    # 비트코인 관련성 체크
                                    if not self._is_bitcoin_or_macro_related_enhanced(article):
                                        continue
                                    
                                    self.processing_stats['bitcoin_related_found'] += 1
                                    
                                    # 기업명 추출
                                    company = self._extract_company_from_content(
                                        article.get('title', ''),
                                        article.get('description', '')
                                    )
                                    if company:
                                        article['company'] = company
                                    
                                    # 크리티컬 뉴스 체크
                                    if self._is_critical_news_enhanced(article):
                                        self.processing_stats['critical_news_found'] += 1
                                        
                                        # 번역 시도
                                        try:
                                            if self._should_translate_for_emergency_report(article):
                                                translated = await self.translate_text(article.get('title', ''))
                                                article['title_ko'] = translated
                                            else:
                                                article['title_ko'] = article.get('title', '')
                                        except Exception as e:
                                            logger.warning(f"번역 오류: {e}")
                                            article['title_ko'] = article.get('title', '')
                                        
                                        # 요약 시도
                                        try:
                                            if self._should_use_gpt_summary(article):
                                                summary = await self.summarize_article_enhanced(
                                                    article['title'],
                                                    article.get('description', '')
                                                )
                                                if summary:
                                                    article['summary'] = summary
                                        except Exception as e:
                                            logger.warning(f"요약 오류: {e}")
                                        
                                        # 중복 체크 후 알림 전송
                                        if not self._is_duplicate_emergency(article):
                                            article['expected_change'] = self._estimate_price_impact_enhanced(article)
                                            await self._trigger_emergency_alert_enhanced(article)
                                            processed_articles += 1
                                            critical_found += 1
                                            self.processing_stats['alerts_sent'] += 1
                                    
                                    # 중요 뉴스는 버퍼에 추가
                                    elif self._is_important_news_enhanced(article):
                                        self.processing_stats['important_news_found'] += 1
                                        await self._add_to_news_buffer_enhanced(article)
                                        processed_articles += 1
                                
                                except Exception as e:
                                    logger.warning(f"기사 처리 오류: {e}")
                                    continue
                    
                    except Exception as e:
                        self.processing_stats['rss_errors'] += 1
                        logger.warning(f"RSS 피드 오류 {feed_info['source']}: {str(e)[:50]}")
                        continue
                
                if processed_articles > 0:
                    logger.info(f"🔥 RSS 스캔: {successful_feeds}개 피드, {processed_articles}개 관련 뉴스 (크리티컬: {critical_found}개)")
                    consecutive_errors = 0
                else:
                    logger.debug(f"📡 RSS 스캔: {successful_feeds}개 피드 활성, 새 뉴스 없음")
                
                await asyncio.sleep(3)  # 3초마다
                
            except Exception as e:
                consecutive_errors += 1
                self.processing_stats['rss_errors'] += 1
                logger.error(f"RSS 모니터링 오류 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"연속 {max_consecutive_errors}회 오류, 30초 대기")
                    await asyncio.sleep(30)
                    consecutive_errors = 0
                else:
                    await asyncio.sleep(10)
    
    def _is_bitcoin_or_macro_related_enhanced(self, article: Dict) -> bool:
        """🔥🔥 비트코인 관련성 체크 (기준 완화)"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 제외 키워드 체크
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 비트코인 직접 언급
        bitcoin_keywords = ['bitcoin', 'btc', '비트코인']
        if any(keyword in content for keyword in bitcoin_keywords):
            return True
        
        # 암호화폐 + 중요 키워드
        crypto_keywords = ['crypto', 'cryptocurrency', '암호화폐']
        if any(keyword in content for keyword in crypto_keywords):
            important_terms = ['etf', 'sec', 'regulation', 'approval', 'russia', 'sberbank', 'bonds']
            if any(term in content for term in important_terms):
                return True
        
        # Fed 금리 (중요)
        fed_keywords = ['fed rate', 'fomc', 'powell', 'federal reserve', 'interest rate decision']
        if any(keyword in content for keyword in fed_keywords):
            return True
        
        # 경제 지표
        economic_keywords = ['inflation data', 'cpi report', 'unemployment rate', 'gdp growth']
        if any(keyword in content for keyword in economic_keywords):
            return True
        
        # 무역/관세
        trade_keywords = ['trump tariffs', 'china tariffs', 'trade war', 'trade deal']
        if any(keyword in content for keyword in trade_keywords):
            return True
        
        # 중요 기업
        for company in self.important_companies:
            if company.lower() in content:
                relevant_terms = ['bitcoin', 'crypto', 'investment', 'purchase', 'announces']
                if any(term in content for term in relevant_terms):
                    return True
        
        return False
    
    def _is_critical_news_enhanced(self, article: Dict) -> bool:
        """🔥🔥 크리티컬 뉴스 판단 (기준 대폭 완화)"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        if not self._is_bitcoin_or_macro_related_enhanced(article):
            return False
        
        # 제외 키워드 체크
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 🔥🔥 크리티컬 키워드 체크 (기준 완화)
        for keyword in self.critical_keywords:
            if keyword.lower() in content:
                # 부정적 필터
                negative_filters = ['rumor', 'speculation', 'unconfirmed', 'fake', 'allegedly']
                if any(neg in content for neg in negative_filters):
                    continue
                
                logger.info(f"🚨 크리티컬 키워드 감지: '{keyword}' - {article.get('title', '')[:50]}...")
                return True
        
        # 🔥🔥 패턴 매칭 (기준 완화)
        critical_patterns = [
            ('bitcoin', 'etf'),
            ('bitcoin', 'sec'),
            ('bitcoin', 'ban'),
            ('bitcoin', 'regulation'),
            ('bitcoin', 'crosses'),
            ('bitcoin', '100k'),
            ('tesla', 'bitcoin'),
            ('microstrategy', 'bitcoin'),
            ('sberbank', 'bitcoin'),
            ('russia', 'bitcoin'),
            ('fed', 'rate'),
            ('trump', 'tariffs'),
            ('inflation', 'data'),
            ('trade', 'deal')
        ]
        
        score = 0
        for pattern in critical_patterns:
            if all(word in content for word in pattern):
                score += 1
                logger.info(f"🚨 크리티컬 패턴: {pattern}")
        
        # 🔥🔥 기준 점수 완화 (1점 이상이면 크리티컬)
        if score >= 1:
            logger.info(f"🚨 크리티컬 뉴스 승인: 패턴 점수 {score}점")
            return True
        
        return False
    
    def _is_important_news_enhanced(self, article: Dict) -> bool:
        """중요 뉴스 판단 (기준 완화)"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        if not self._is_bitcoin_or_macro_related_enhanced(article):
            return False
        
        # 제외 키워드 체크
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        weight = article.get('weight', 0)
        category = article.get('category', '')
        
        # 조건들 (기준 완화)
        conditions = [
            category == 'crypto' and weight >= 4,  # 5 → 4
            category == 'finance' and weight >= 4,  # 5 → 4
            category == 'api' and weight >= 5,  # 6 → 5
            any(company.lower() in content for company in self.important_companies) and 
            any(word in content for word in ['bitcoin', 'crypto', 'investment']),
            any(word in content for word in ['fed rate', 'inflation', 'trade deal']) and weight >= 4
        ]
        
        return any(conditions)
    
    def _estimate_price_impact_enhanced(self, article: Dict) -> str:
        """현실적 가격 영향 추정"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # ETF 관련
        if 'etf approved' in content or 'etf approval' in content:
            return '🚀 상승 2.0~3.5% (24시간 내)'
        elif 'etf rejected' in content or 'etf delay' in content:
            return '🔻 하락 1.5~2.5% (12시간 내)'
        
        # Fed 관련
        elif 'fed cuts rates' in content or 'rate cut' in content:
            return '📈 상승 1.0~2.0% (8시간 내)'
        elif 'fed raises rates' in content or 'rate hike' in content:
            return '📉 하락 0.8~1.5% (6시간 내)'
        
        # 기업 구매
        elif 'tesla' in content and 'bitcoin' in content:
            return '🚀 상승 1.2~2.5% (18시간 내)'
        elif 'microstrategy' in content and 'bitcoin' in content:
            return '📈 상승 0.4~1.0% (8시간 내)'
        
        # 구조화 상품
        elif any(word in content for word in ['structured', 'bonds', 'linked']):
            return '📊 미미한 반응 +0.05~0.2% (4시간 내)'
        
        # 규제
        elif 'china bans bitcoin' in content or 'bitcoin banned' in content:
            return '🔻 하락 2.0~4.0% (24시간 내)'
        elif 'regulatory clarity' in content or 'bitcoin approved' in content:
            return '📈 상승 0.8~1.8% (12시간 내)'
        
        # 무역/관세
        elif 'tariffs' in content or 'trade war' in content:
            return '📉 하락 0.3~1.0% (6시간 내)'
        elif 'trade deal' in content:
            return '📈 상승 0.2~0.8% (8시간 내)'
        
        # 인플레이션
        elif 'inflation' in content or 'cpi' in content:
            return '📈 상승 0.3~1.0% (6시간 내)'
        
        # 해킹
        elif 'hack' in content or 'stolen' in content:
            return '📉 하락 0.2~1.0% (4시간 내)'
        
        # 기본값
        return '⚡ 변동 ±0.2~0.8% (단기)'
    
    async def summarize_article_enhanced(self, title: str, description: str, max_length: int = 200) -> str:
        """개선된 요약"""
        # 기본 요약 우선
        try:
            basic_summary = self._generate_basic_summary_enhanced(title, description)
            if basic_summary and len(basic_summary.strip()) > 30:
                return basic_summary
        except Exception as e:
            logger.warning(f"기본 요약 오류: {e}")
        
        # GPT 요약
        if not self.openai_client or not description:
            return "비트코인 관련 발표가 있었다. 투자자들은 신중한 접근이 필요하다."
        
        if len(description) <= 150:
            return basic_summary or "비트코인 시장에 영향을 미칠 수 있는 발표가 있었다."
        
        self._reset_summary_count_if_needed()
        
        if self.summary_count >= self.max_summaries_per_15min:
            return basic_summary or "비트코인 관련 발표가 있었다."
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "비트코인 투자 전문가입니다. 3문장으로 요약하세요."},
                    {"role": "user", "content": f"3문장 요약 (최대 {max_length}자):\n\n제목: {title}\n\n내용: {description[:600]}"}
                ],
                max_tokens=200,
                temperature=0.2,
                timeout=15.0
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
            self.processing_stats['api_errors'] += 1
            logger.warning(f"GPT 요약 실패: {str(e)[:50]}")
            return basic_summary or "비트코인 관련 발표가 있었다."
    
    def _generate_basic_summary_enhanced(self, title: str, description: str) -> str:
        """기본 요약 생성"""
        try:
            content = (title + " " + description).lower()
            summary_parts = []
            
            # 구조화 상품 특별 처리
            if 'sberbank' in content and any(word in content for word in ['structured', 'bonds', 'linked']):
                summary_parts.append("러시아 최대 은행 스베르방크가 비트코인 가격에 연동된 구조화 채권을 출시했다.")
                summary_parts.append("이는 직접적인 비트코인 매수가 아닌 가격 추적 상품으로, 실제 BTC 수요 창출 효과는 제한적이다.")
                summary_parts.append("러시아 제재 상황과 OTC 거래로 인해 글로벌 시장에 미치는 즉각적 영향은 미미할 것으로 예상된다.")
                return " ".join(summary_parts)
            
            # 기업 구매
            if any(company in content for company in ['tesla', 'microstrategy']) and 'bitcoin' in content:
                if 'tesla' in content:
                    summary_parts.append("테슬라가 비트코인 직접 매입을 발표했다.")
                    summary_parts.append("일론 머스크의 영향력과 함께 시장에 상당한 관심을 불러일으킬 것으로 예상된다.")
                elif 'microstrategy' in content:
                    summary_parts.append("마이크로스트래티지가 비트코인을 추가 매입했다.")
                    summary_parts.append("기업의 지속적인 비트코인 매입 전략의 일환으로 시장에 긍정적 신호를 보낸다.")
                summary_parts.append("기업의 비트코인 채택 확산에 긍정적 영향을 미칠 전망이다.")
                return " ".join(summary_parts)
            
            # ETF 관련
            if 'etf' in content:
                if 'approved' in content:
                    summary_parts.append("비트코인 현물 ETF 승인 소식이 전해졌다.")
                    summary_parts.append("ETF 승인은 기관 투자자들의 자금 유입을 가능하게 하는 중요한 이정표다.")
                    summary_parts.append("비트코인 시장의 제도화와 주류 채택에 기여할 것으로 보인다.")
                else:
                    summary_parts.append("비트코인 ETF 관련 중요한 발표가 있었다.")
                    summary_parts.append("ETF 승인은 기관 투자자들의 비트코인 관심도를 보여준다.")
                    summary_parts.append("시장의 제도화 진행 상황을 나타내는 지표로 평가된다.")
                return " ".join(summary_parts)
            
            # Fed 관련
            if 'fed' in content or 'rate' in content:
                summary_parts.append("연준의 금리 정책 발표가 있었다.")
                summary_parts.append("금리 정책은 비트코인을 포함한 리스크 자산에 직접적 영향을 미친다.")
                summary_parts.append("투자자들은 정책 방향성에 따른 포트폴리오 조정을 고려하고 있다.")
                return " ".join(summary_parts)
            
            # 관세 관련
            if 'tariff' in content or 'trade' in content:
                summary_parts.append("미국의 무역 정책 발표가 있었다.")
                summary_parts.append("무역 정책 변화는 글로벌 시장과 달러 강세에 영향을 미칠 수 있다.")
                summary_parts.append("달러 약세 요인이 비트코인에는 중장기적으로 유리할 것으로 분석된다.")
                return " ".join(summary_parts)
            
            # 기본 케이스
            if title and len(title) > 10:
                summary_parts.append("비트코인 시장과 관련된 중요한 소식이 발표되었다.")
            else:
                summary_parts.append("비트코인 관련 발표가 있었다.")
            
            summary_parts.append("투자자들은 이번 소식의 실제 시장 영향을 분석하고 있다.")
            summary_parts.append("단기 변동성은 있겠지만 장기 트렌드 지속이 예상된다.")
            
            return " ".join(summary_parts[:3])
            
        except Exception as e:
            logger.error(f"기본 요약 생성 실패: {e}")
            return "비트코인 관련 소식이 발표되었다. 시장 반응을 지켜볼 필요가 있다."
    
    async def _trigger_emergency_alert_enhanced(self, article: Dict):
        """긴급 알림 트리거 (오류 방지)"""
        try:
            content_hash = self._generate_content_hash(article.get('title', ''), article.get('description', ''))
            if content_hash in self.processed_news_hashes:
                return
            
            self.processed_news_hashes.add(content_hash)
            
            # 크기 제한
            if len(self.processed_news_hashes) > 3000:
                self.processed_news_hashes = set(list(self.processed_news_hashes)[-1500:])
            
            # 최초 발견 시간 기록
            if content_hash not in self.news_first_seen:
                self.news_first_seen[content_hash] = datetime.now()
            
            # 번역 시도 (실패해도 뉴스 전송)
            try:
                if self._should_translate_for_emergency_report(article):
                    translated_title = await self.translate_text(article.get('title', ''))
                    article['title_ko'] = translated_title
                else:
                    article['title_ko'] = article.get('title', '')
            except Exception as e:
                logger.warning(f"번역 오류, 원문 사용: {e}")
                article['title_ko'] = article.get('title', '')
            
            # 이벤트 생성
            event = {
                'type': 'critical_news',
                'title': article.get('title', ''),
                'title_ko': article.get('title_ko', article.get('title', '')),
                'description': article.get('description', '')[:1200],
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
                'first_seen': self.news_first_seen[content_hash]
            }
            
            self._save_duplicate_data()
            
            # 데이터 컬렉터에 전달
            if hasattr(self, 'data_collector') and self.data_collector:
                self.data_collector.events_buffer.append(event)
            
            logger.critical(f"🚨🚨 크리티컬 뉴스: {event['title_ko'][:60]}... (예상: {event['expected_change']})")
            
        except Exception as e:
            logger.error(f"긴급 알림 처리 오류: {e}")
            
            # 폴백 이벤트 생성 (오류 시에도 뉴스 전송)
            try:
                fallback_event = {
                    'type': 'critical_news',
                    'title': article.get('title', 'Unknown Title'),
                    'title_ko': article.get('title', 'Unknown Title'),
                    'description': article.get('description', '')[:500],
                    'source': article.get('source', 'Unknown'),
                    'timestamp': datetime.now(),
                    'severity': 'critical',
                    'impact': '📊 시장 관심',
                    'expected_change': '⚡ 변동 ±0.3~1.0%',
                    'weight': 5
                }
                
                if hasattr(self, 'data_collector') and self.data_collector:
                    self.data_collector.events_buffer.append(fallback_event)
                
                logger.warning(f"🚨 폴백 이벤트 생성: {article.get('title', '')[:50]}...")
                
            except Exception as e2:
                logger.error(f"폴백 이벤트 생성 실패: {e2}")
    
    def _determine_impact_enhanced(self, article: Dict) -> str:
        """영향도 판단"""
        expected_change = self._estimate_price_impact_enhanced(article)
        
        if '🚀' in expected_change or any(x in expected_change for x in ['3%', '4%', '2.5%']):
            return "🚀 매우 강한 호재"
        elif '📈' in expected_change and any(x in expected_change for x in ['1.5%', '2%']):
            return "📈 강한 호재"
        elif '📈' in expected_change:
            return "📈 호재"
        elif '🔻' in expected_change or any(x in expected_change for x in ['3%', '4%']):
            return "🔻 매우 강한 악재"
        elif '📉' in expected_change and any(x in expected_change for x in ['1.5%', '2%']):
            return "📉 강한 악재"
        elif '📉' in expected_change:
            return "📉 악재"
        else:
            return "⚡ 변동성 확대"
    
    async def _add_to_news_buffer_enhanced(self, article: Dict):
        """뉴스 버퍼 추가"""
        try:
            content_hash = self._generate_content_hash(article.get('title', ''), article.get('description', ''))
            if content_hash in self.processed_news_hashes:
                return
            
            # 제목 유사성 체크
            new_title = article.get('title', '').lower()
            for existing in self.news_buffer:
                if self._is_similar_news_enhanced(new_title, existing.get('title', '')):
                    return
            
            # 회사별 뉴스 카운트 체크
            for company in self.important_companies:
                if company.lower() in new_title:
                    if self.company_news_count.get(company.lower(), 0) >= 5:
                        return
                    self.company_news_count[company.lower()] = self.company_news_count.get(company.lower(), 0) + 1
            
            self.news_buffer.append(article)
            self.processed_news_hashes.add(content_hash)
            self._save_duplicate_data()
            
            # 버퍼 크기 관리
            if len(self.news_buffer) > 150:
                self.news_buffer.sort(key=lambda x: (x.get('weight', 0), x.get('published_at', '')), reverse=True)
                self.news_buffer = self.news_buffer[:150]
            
            logger.debug(f"✅ 중요 뉴스 버퍼 추가: {new_title[:50]}...")
        
        except Exception as e:
            logger.error(f"뉴스 버퍼 추가 오류: {e}")
    
    def _is_similar_news_enhanced(self, title1: str, title2: str) -> bool:
        """유사 뉴스 판별"""
        try:
            clean1 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title1.lower())
            clean2 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title2.lower())
            
            clean1 = re.sub(r'\s+', ' ', clean1).strip()
            clean2 = re.sub(r'\s+', ' ', clean2).strip()
            
            # 회사별 비트코인 뉴스 체크
            for company in self.important_companies:
                company_lower = company.lower()
                if company_lower in clean1 and company_lower in clean2:
                    bitcoin_keywords = ['bitcoin', 'btc', 'crypto']
                    if any(keyword in clean1 for keyword in bitcoin_keywords) and \
                       any(keyword in clean2 for keyword in bitcoin_keywords):
                        return True
            
            # 단어 집합 비교
            words1 = set(clean1.split())
            words2 = set(clean2.split())
            
            if not words1 or not words2:
                return False
            
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            
            similarity = intersection / union if union > 0 else 0
            
            return similarity > 0.75  # 75% 이상 유사하면 중복
        except Exception as e:
            logger.error(f"유사 뉴스 판별 오류: {e}")
            return False
    
    async def monitor_reddit_enhanced(self):
        """Reddit 모니터링"""
        reddit_subreddits = [
            {'name': 'Bitcoin', 'threshold': 200, 'weight': 9},
            {'name': 'CryptoCurrency', 'threshold': 500, 'weight': 8},
            {'name': 'BitcoinMarkets', 'threshold': 100, 'weight': 9},
            {'name': 'investing', 'threshold': 600, 'weight': 7},
        ]
        
        while True:
            try:
                for sub_info in reddit_subreddits:
                    try:
                        url = f"https://www.reddit.com/r/{sub_info['name']}/hot.json?limit=10"
                        headers = {'User-Agent': self._get_random_user_agent()}
                        
                        async with self.session.get(url, headers=headers) as response:
                            if response.status == 200:
                                data = await response.json()
                                posts = data['data']['children']
                                
                                for post in posts:
                                    try:
                                        post_data = post['data']
                                        
                                        if post_data['ups'] > sub_info['threshold']:
                                            article = {
                                                'title': post_data['title'],
                                                'title_ko': post_data['title'],
                                                'description': post_data.get('selftext', '')[:1200],
                                                'url': f"https://reddit.com{post_data['permalink']}",
                                                'source': f"Reddit r/{sub_info['name']}",
                                                'published_at': datetime.fromtimestamp(post_data['created_utc']).isoformat(),
                                                'upvotes': post_data['ups'],
                                                'weight': sub_info['weight'],
                                                'category': 'social'
                                            }
                                            
                                            self.processing_stats['total_articles_checked'] += 1
                                            
                                            if self._is_bitcoin_or_macro_related_enhanced(article):
                                                self.processing_stats['bitcoin_related_found'] += 1
                                                
                                                if self._is_critical_news_enhanced(article):
                                                    self.processing_stats['critical_news_found'] += 1
                                                    
                                                    if not self._is_duplicate_emergency(article):
                                                        article['expected_change'] = self._estimate_price_impact_enhanced(article)
                                                        await self._trigger_emergency_alert_enhanced(article)
                                                        self.processing_stats['alerts_sent'] += 1
                                                
                                                elif self._is_important_news_enhanced(article):
                                                    self.processing_stats['important_news_found'] += 1
                                                    await self._add_to_news_buffer_enhanced(article)
                                    
                                    except Exception as e:
                                        logger.warning(f"Reddit 포스트 처리 오류: {e}")
                                        continue
                    
                    except Exception as e:
                        self.processing_stats['rss_errors'] += 1
                        logger.warning(f"Reddit 오류 {sub_info['name']}: {str(e)[:50]}")
                
                await asyncio.sleep(300)  # 5분마다
                
            except Exception as e:
                logger.error(f"Reddit 모니터링 오류: {e}")
                await asyncio.sleep(600)
    
    async def aggressive_api_rotation_enhanced(self):
        """API 순환 사용"""
        while True:
            try:
                self._reset_daily_usage()
                
                # NewsAPI
                if self.newsapi_key and self.api_usage['newsapi_today'] < self.api_limits['newsapi']:
                    try:
                        await self._call_newsapi_enhanced()
                        self.api_usage['newsapi_today'] += 1
                        logger.info(f"✅ NewsAPI 호출 ({self.api_usage['newsapi_today']}/{self.api_limits['newsapi']})")
                    except Exception as e:
                        self.processing_stats['api_errors'] += 1
                        logger.error(f"NewsAPI 오류: {str(e)[:100]}")
                
                await asyncio.sleep(600)
                
                # NewsData API
                if self.newsdata_key and self.api_usage['newsdata_today'] < self.api_limits['newsdata']:
                    try:
                        await self._call_newsdata_enhanced()
                        self.api_usage['newsdata_today'] += 1
                        logger.info(f"✅ NewsData 호출 ({self.api_usage['newsdata_today']}/{self.api_limits['newsdata']})")
                    except Exception as e:
                        self.processing_stats['api_errors'] += 1
                        logger.error(f"NewsData 오류: {str(e)[:100]}")
                
                await asyncio.sleep(1200)
                
            except Exception as e:
                logger.error(f"API 순환 오류: {e}")
                await asyncio.sleep(1800)
    
    async def _call_newsapi_enhanced(self):
        """NewsAPI 호출 (오류 방지)"""
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': '(bitcoin OR btc OR "bitcoin etf" OR "fed rate" OR "trump tariffs" OR "trade deal" OR "sberbank bitcoin" OR "russia bitcoin" OR "bitcoin crosses 100k") AND NOT ("altcoin only" OR "how to mine")',
                'language': 'en',
                'sortBy': 'publishedAt',
                'apiKey': self.newsapi_key,
                'pageSize': 80,
                'from': (datetime.now() - timedelta(hours=4)).isoformat()
            }
            
            headers = {'User-Agent': self._get_random_user_agent()}
            
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('articles', [])
                    
                    processed = 0
                    critical_found = 0
                    for article in articles:
                        try:
                            formatted_article = {
                                'title': article.get('title', ''),
                                'title_ko': article.get('title', ''),
                                'description': article.get('description', '')[:1200],
                                'url': article.get('url', ''),
                                'source': f"NewsAPI ({article.get('source', {}).get('name', 'Unknown')})",
                                'published_at': article.get('publishedAt', ''),
                                'weight': 9,
                                'category': 'api'
                            }
                            
                            self.processing_stats['total_articles_checked'] += 1
                            
                            if self._is_bitcoin_or_macro_related_enhanced(formatted_article):
                                self.processing_stats['bitcoin_related_found'] += 1
                                
                                if self._is_critical_news_enhanced(formatted_article):
                                    self.processing_stats['critical_news_found'] += 1
                                    
                                    if not self._is_duplicate_emergency(formatted_article):
                                        formatted_article['expected_change'] = self._estimate_price_impact_enhanced(formatted_article)
                                        await self._trigger_emergency_alert_enhanced(formatted_article)
                                    processed += 1
                                    critical_found += 1
                                    self.processing_stats['alerts_sent'] += 1
                                elif self._is_important_news_enhanced(formatted_article):
                                    self.processing_stats['important_news_found'] += 1
                                    await self._add_to_news_buffer_enhanced(formatted_article)
                                    processed += 1
                        
                        except Exception as e:
                            logger.warning(f"NewsAPI 기사 처리 오류: {e}")
                            continue
                    
                    if processed > 0:
                        logger.info(f"🔥 NewsAPI: {processed}개 관련 뉴스 (크리티컬: {critical_found}개)")
                else:
                    logger.warning(f"NewsAPI 응답 오류: {response.status}")
        
        except Exception as e:
            logger.error(f"NewsAPI 호출 오류: {e}")
    
    async def _call_newsdata_enhanced(self):
        """NewsData API 호출"""
        try:
            url = "https://newsdata.io/api/1/news"
            params = {
                'apikey': self.newsdata_key,
                'q': 'bitcoin OR btc OR "bitcoin etf" OR "sberbank bitcoin" OR "russia bitcoin" OR "fed rate decision" OR "trump tariffs" OR "bitcoin crosses 100k"',
                'language': 'en',
                'category': 'business,top',
                'size': 40
            }
            
            headers = {'User-Agent': self._get_random_user_agent()}
            
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get('results', [])
                    
                    processed = 0
                    critical_found = 0
                    for article in articles:
                        try:
                            formatted_article = {
                                'title': article.get('title', ''),
                                'title_ko': article.get('title', ''),
                                'description': article.get('description', '')[:1200],
                                'url': article.get('link', ''),
                                'source': f"NewsData ({article.get('source_id', 'Unknown')})",
                                'published_at': article.get('pubDate', ''),
                                'weight': 8,
                                'category': 'api'
                            }
                            
                            self.processing_stats['total_articles_checked'] += 1
                            
                            if self._is_bitcoin_or_macro_related_enhanced(formatted_article):
                                self.processing_stats['bitcoin_related_found'] += 1
                                
                                if self._is_critical_news_enhanced(formatted_article):
                                    self.processing_stats['critical_news_found'] += 1
                                    
                                    if not self._is_duplicate_emergency(formatted_article):
                                        formatted_article['expected_change'] = self._estimate_price_impact_enhanced(formatted_article)
                                        await self._trigger_emergency_alert_enhanced(formatted_article)
                                    processed += 1
                                    critical_found += 1
                                    self.processing_stats['alerts_sent'] += 1
                                elif self._is_important_news_enhanced(formatted_article):
                                    self.processing_stats['important_news_found'] += 1
                                    await self._add_to_news_buffer_enhanced(formatted_article)
                                    processed += 1
                        
                        except Exception as e:
                            logger.warning(f"NewsData 기사 처리 오류: {e}")
                            continue
                    
                    if processed > 0:
                        logger.info(f"🔥 NewsData: {processed}개 관련 뉴스 (크리티컬: {critical_found}개)")
                else:
                    logger.warning(f"NewsData 응답 오류: {response.status}")
        
        except Exception as e:
            logger.error(f"NewsData 호출 오류: {e}")
    
    async def _parse_rss_feed_enhanced(self, feed_info: Dict) -> List[Dict]:
        """🔥🔥 RSS 피드 파싱 (403 오류 해결)"""
        articles = []
        try:
            # 랜덤 User-Agent 사용
            headers = {
                'User-Agent': self._get_random_user_agent(),
                'Accept': 'application/rss+xml, application/xml, text/xml',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'no-cache'
            }
            
            # 타임아웃 단축
            async with self.session.get(
                feed_info['url'], 
                timeout=aiohttp.ClientTimeout(total=8),
                headers=headers
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    if feed.entries:
                        limit = min(15, max(6, feed_info['weight']))
                        
                        for entry in feed.entries[:limit]:
                            try:
                                # 발행 시간 처리
                                pub_time = datetime.now().isoformat()
                                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                    try:
                                        pub_time = datetime(*entry.published_parsed[:6]).isoformat()
                                    except:
                                        pass
                                elif hasattr(entry, 'published'):
                                    try:
                                        from dateutil import parser
                                        pub_time = parser.parse(entry.published).isoformat()
                                    except:
                                        pass
                                
                                title = entry.get('title', '').strip()
                                description = entry.get('summary', '').strip()
                                url = entry.get('link', '').strip()
                                
                                # 기본 검증
                                if not title or len(title) < 10:
                                    continue
                                if not url or not url.startswith('http'):
                                    continue
                                
                                article = {
                                    'title': title[:400],
                                    'description': description[:1200],
                                    'url': url,
                                    'source': feed_info['source'],
                                    'published_at': pub_time,
                                    'weight': feed_info['weight'],
                                    'category': feed_info.get('category', 'unknown')
                                }
                                
                                articles.append(article)
                                        
                            except Exception as e:
                                logger.debug(f"기사 파싱 오류: {str(e)[:50]}")
                                continue
                
                elif response.status == 403:
                    logger.warning(f"🚫 {feed_info['source']}: 접근 거부 (403) - User-Agent 로테이션 중")
                elif response.status == 429:
                    logger.warning(f"⏰ {feed_info['source']}: Rate limit (429)")
                else:
                    logger.warning(f"❌ {feed_info['source']}: HTTP {response.status}")
        
        except asyncio.TimeoutError:
            logger.debug(f"⏰ {feed_info['source']}: 타임아웃")
        except aiohttp.ClientConnectorError:
            logger.debug(f"🔌 {feed_info['source']}: 연결 오류")
        except Exception as e:
            logger.debug(f"❌ {feed_info['source']}: {str(e)[:50]}")
        
        return articles
    
    def _extract_company_from_content(self, title: str, description: str = "") -> str:
        """컨텐츠에서 기업명 추출"""
        try:
            content = (title + " " + description).lower()
            
            for company in self.important_companies:
                if company.lower() in content:
                    # 원래 대소문자 유지
                    for original in self.important_companies:
                        if original.lower() == company.lower():
                            return original.title()
            
            return ""
        except Exception as e:
            logger.error(f"기업명 추출 오류: {e}")
            return ""
    
    def _reset_daily_usage(self):
        """일일 사용량 리셋"""
        try:
            today = datetime.now().date()
            if today > self.api_usage['last_reset']:
                self.api_usage.update({
                    'newsapi_today': 0,
                    'newsdata_today': 0,
                    'alpha_vantage_today': 0,
                    'last_reset': today
                })
                self.company_news_count = {}
                self.claude_translation_count = 0
                self.gpt_translation_count = 0
                self.claude_error_count = 0
                self.summary_count = 0
                self.last_translation_reset = datetime.now()
                self.last_summary_reset = datetime.now()
                self.news_first_seen = {}
                self.claude_cooldown_until = None
                
                # 크리티컬 리포트 중복 방지 데이터 정리
                current_time = datetime.now()
                cutoff_time = current_time - timedelta(hours=8)
                self.sent_critical_reports = {
                    k: v for k, v in self.sent_critical_reports.items()
                    if v > cutoff_time
                }
                self._save_critical_reports()
                
                logger.info(f"🔄 일일 리셋 완료 (중복 체크: {self.duplicate_check_hours}시간, 쿨다운: {self.critical_report_cooldown_minutes}분)")
        except Exception as e:
            logger.error(f"일일 리셋 오류: {e}")
    
    async def get_recent_news_enhanced(self, hours: int = 8) -> List[Dict]:
        """최근 뉴스 가져오기 (시간 확장)"""
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
                                content_hash = self._generate_content_hash(article.get('title', ''), '')
                                if content_hash not in seen_hashes:
                                    recent_news.append(article)
                                    seen_hashes.add(content_hash)
                        except:
                            pass
                except:
                    pass
            
            recent_news.sort(key=lambda x: (x.get('weight', 0), x.get('published_at', '')), reverse=True)
            
            logger.info(f"🔥 최근 {hours}시간 뉴스: {len(recent_news)}개")
            
            return recent_news[:40]  # 40개로 증가
            
        except Exception as e:
            logger.error(f"최근 뉴스 조회 오류: {e}")
            return []
    
    async def get_recent_news(self, hours: int = 8) -> List[Dict]:
        """최근 뉴스 가져오기 (호환성)"""
        return await self.get_recent_news_enhanced(hours)
    
    def _is_critical_news(self, article: Dict) -> bool:
        """기존 호환성"""
        return self._is_critical_news_enhanced(article)
    
    async def close(self):
        """세션 종료"""
        try:
            self._save_duplicate_data()
            self._save_critical_reports()
            
            if self.session:
                await self.session.close()
                logger.info("🔚 뉴스 수집기 세션 종료 (403 오류 해결 버전)")
                logger.info(f"🔄 최종 설정: 중복 체크 {self.duplicate_check_hours}시간, 쿨다운 {self.critical_report_cooldown_minutes}분")
                
                stats = self.processing_stats
                if stats['total_articles_checked'] > 0:
                    logger.info(f"📊 최종 통계:")
                    logger.info(f"  총 기사: {stats['total_articles_checked']}개")
                    logger.info(f"  크리티컬: {stats['critical_news_found']}개")
                    logger.info(f"  알림 전송: {stats['alerts_sent']}개")
                
        except Exception as e:
            logger.error(f"세션 종료 오류: {e}")
