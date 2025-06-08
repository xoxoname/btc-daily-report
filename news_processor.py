import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import hashlib
import re
import json
import os

logger = logging.getLogger(__name__)

class NewsProcessor:
    """뉴스 분석, 분류, 중복 체크, 이벤트 생성 전담"""
    
    def __init__(self, config):
        self.config = config
        
        # 중요 기업 리스트
        self.important_companies = [
            'tesla', 'microstrategy', 'square', 'block', 'paypal', 'mastercard', 'visa',
            'gamestop', 'gme', 'blackrock', 'fidelity', 'ark invest', 'grayscale',
            'coinbase', 'binance', 'kraken', 'bitget', 'okx', 'bybit',
            'metaplanet', '메타플래닛', '테슬라', '마이크로스트래티지',
            'sberbank', '스베르방크', 'jpmorgan', 'goldman sachs', 'morgan stanley',
            'nvidia', 'amd', 'intel', 'apple', 'microsoft', 'amazon',
            '삼성', 'samsung', 'lg', 'sk', 'hyundai'
        ]
        
        # 크리티컬 키워드
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
            
            # 가격 이정표 관련
            'bitcoin crosses 100k', 'bitcoin hits 100000', 'bitcoin 100k milestone',
            'bitcoin google search', 'bitcoin interest low', 'bitcoin searches unchanged',
            
            # Fed 금리 결정 (비트코인 영향)
            'fed rate decision', 'fomc decision', 'powell speech', 'interest rate decision',
            'federal reserve meeting', 'fed minutes', 'inflation report', 'cpi data',
            '연준 금리', '기준금리', '통화정책', 'jobless claims', 'unemployment rate',
            
            # 거시경제 영향
            'us economic policy', 'treasury secretary', 'inflation data', 'cpi report',
            'unemployment rate', 'gdp growth', 'recession fears', 'economic stimulus',
            'quantitative easing', 'dollar strength', 'dollar weakness', 'dxy index',
            '달러 강세', '달러 약세', '인플레이션', '경기침체', 'china economic data',
            
            # 미국 관세 및 무역
            'trump tariffs', 'china tariffs', 'trade war', 'trade deal', 'trade agreement',
            'customs duties', 'import tariffs', 'export restrictions', 'trade negotiations',
            'trade talks deadline', 'tariff exemption', 'tariff extension', 'wto ruling',
            '관세', '무역협상', '무역전쟁', '무역합의', 'usmca agreement',
        ]
        
        # 제외 키워드
        self.exclude_keywords = [
            'how to mine', '집에서 채굴', 'mining at home', 'mining tutorial',
            'price prediction tutorial', '가격 예측 방법', 'technical analysis tutorial',
            'altcoin only', 'ethereum only', 'ripple only', 'cardano only', 'solana only', 
            'dogecoin only', 'shiba only', 'nft only', 'web3 only', 'metaverse only',
            'defi only', 'gamefi only', 'celebrity news', 'entertainment only',
            'sports only', 'weather', 'local news', 'obituary', 'wedding',
            'movie review', 'book review', 'restaurant review', 'travel guide'
        ]
        
        # 중복 방지 데이터
        self.processed_news_hashes = set()
        self.sent_news_titles = {}
        self.sent_critical_reports = {}
        self.company_news_count = {}
        self.news_first_seen = {}
        
        # 파일 경로
        self.news_data_file = 'news_duplicates.json'
        self.processed_reports_file = 'processed_critical_reports.json'
        
        # 기존 데이터 로드
        self._load_duplicate_data()
        self._load_critical_reports()
        
        # 현실적인 뉴스 영향 패턴
        self.historical_patterns = {
            'etf_approval': {'avg_impact': 3.5, 'duration_hours': 24, 'confidence': 0.95},
            'etf_rejection': {'avg_impact': -2.8, 'duration_hours': 12, 'confidence': 0.9},
            'tesla_purchase': {'avg_impact': 2.2, 'duration_hours': 18, 'confidence': 0.9},
            'microstrategy_purchase': {'avg_impact': 0.7, 'duration_hours': 8, 'confidence': 0.85},
            'price_milestone': {'avg_impact': 0.2, 'duration_hours': 8, 'confidence': 0.6},
            'price_milestone_low_interest': {'avg_impact': 0.1, 'duration_hours': 4, 'confidence': 0.5},
            'ai_prediction': {'avg_impact': 0.05, 'duration_hours': 2, 'confidence': 0.3},
            'energy_crisis_prediction': {'avg_impact': 0.1, 'duration_hours': 4, 'confidence': 0.4},
            'fed_rate_hike': {'avg_impact': -1.2, 'duration_hours': 6, 'confidence': 0.7},
            'fed_rate_cut': {'avg_impact': 1.5, 'duration_hours': 8, 'confidence': 0.75},
            'new_tariffs': {'avg_impact': -0.8, 'duration_hours': 6, 'confidence': 0.65},
            'trade_deal': {'avg_impact': 0.6, 'duration_hours': 8, 'confidence': 0.7},
            'corporate_structured_product': {'avg_impact': 0.05, 'duration_hours': 2, 'confidence': 0.3},
        }
        
        logger.info(f"📊 뉴스 처리기 초기화 완료")
        logger.info(f"🎯 크리티컬 키워드: {len(self.critical_keywords)}개")
        logger.info(f"🏢 추적 기업: {len(self.important_companies)}개")
        logger.info(f"💾 중복 방지: 처리된 뉴스 {len(self.processed_news_hashes)}개")
    
    def _load_duplicate_data(self):
        """중복 방지 데이터 로드"""
        try:
            if os.path.exists(self.news_data_file):
                with open(self.news_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.processed_news_hashes = set(data.get('processed_news_hashes', []))
                
                # 시간 기반 데이터 정리
                current_time = datetime.now()
                cutoff_time = current_time - timedelta(hours=12)
                
                # 뉴스 제목 캐시
                title_data = data.get('sent_news_titles', {})
                for title_hash, time_str in title_data.items():
                    try:
                        sent_time = datetime.fromisoformat(time_str)
                        if sent_time > cutoff_time:
                            self.sent_news_titles[title_hash] = sent_time
                    except:
                        continue
                
                # 처리된 뉴스 해시 크기 제한
                if len(self.processed_news_hashes) > 3000:
                    self.processed_news_hashes = set(list(self.processed_news_hashes)[-1500:])
                
                logger.info(f"✅ 중복 방지 데이터 로드: {len(self.processed_news_hashes)}개")
                
        except Exception as e:
            logger.warning(f"❌ 중복 방지 데이터 로드 실패: {e}")
            self.processed_news_hashes = set()
            self.sent_news_titles = {}
    
    def _load_critical_reports(self):
        """크리티컬 리포트 중복 방지 데이터 로드"""
        try:
            if os.path.exists(self.processed_reports_file):
                with open(self.processed_reports_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                current_time = datetime.now()
                cutoff_time = current_time - timedelta(hours=4)
                
                for item in data:
                    try:
                        report_time = datetime.fromisoformat(item['time'])
                        if report_time > cutoff_time:
                            self.sent_critical_reports[item['hash']] = report_time
                    except:
                        continue
                
                logger.info(f"✅ 크리티컬 리포트 중복 방지 데이터 로드: {len(self.sent_critical_reports)}개")
                
        except Exception as e:
            logger.warning(f"❌ 크리티컬 리포트 데이터 로드 실패: {e}")
            self.sent_critical_reports = {}
    
    def _save_duplicate_data(self):
        """중복 방지 데이터 저장"""
        try:
            title_data = {}
            for title_hash, sent_time in self.sent_news_titles.items():
                title_data[title_hash] = sent_time.isoformat()
            
            data = {
                'processed_news_hashes': list(self.processed_news_hashes),
                'sent_news_titles': title_data,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.news_data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"❌ 중복 방지 데이터 저장 실패: {e}")
    
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
            logger.error(f"❌ 크리티컬 리포트 데이터 저장 실패: {e}")
    
    def is_bitcoin_or_macro_related(self, article: Dict) -> bool:
        """비트코인 직접 관련성 + 거시경제 영향 체크"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 제외 키워드 먼저 체크
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 1. 비트코인 직접 언급
        bitcoin_keywords = ['bitcoin', 'btc', '비트코인', 'bitcoins']
        has_bitcoin = any(keyword in content for keyword in bitcoin_keywords)
        
        if has_bitcoin:
            return True
        
        # 2. 암호화폐 일반 + 중요 내용
        crypto_keywords = ['crypto', 'cryptocurrency', '암호화폐', 'cryptocurrencies', 'digital currency']
        has_crypto = any(keyword in content for keyword in crypto_keywords)
        
        if has_crypto:
            important_terms = ['etf', 'sec', 'regulation', 'ban', 'approval', 'court', 'lawsuit', 
                             'bonds', 'russia', 'sberbank', 'institutional', 'adoption']
            if any(term in content for term in important_terms):
                return True
        
        # 3. Fed 금리 결정
        fed_keywords = ['fed rate decision', 'fomc decides', 'powell announces', 'federal reserve decision',
                       'interest rate decision', 'fed chair', 'fed meeting', 'monetary policy']
        if any(keyword in content for keyword in fed_keywords):
            return True
        
        # 4. 중요 경제 지표
        economic_keywords = ['inflation data', 'cpi report', 'unemployment rate', 'jobs report',
                           'gdp growth', 'pce index', 'retail sales', 'manufacturing pmi']
        if any(keyword in content for keyword in economic_keywords):
            return True
        
        # 5. 미국 관세 및 무역
        trade_keywords = ['trump tariffs', 'china tariffs', 'trade war escalation', 'trade deal signed',
                         'trade agreement', 'trade negotiations breakthrough']
        if any(keyword in content for keyword in trade_keywords):
            return True
        
        return False
    
    def is_critical_news(self, article: Dict) -> bool:
        """크리티컬 뉴스 판단"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 비트코인 + 거시경제 관련성 체크
        if not self.is_bitcoin_or_macro_related(article):
            return False
        
        # 제외 키워드 체크
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        # 가중치 체크
        if article.get('weight', 0) < 6:
            return False
        
        # 크리티컬 키워드 체크
        for keyword in self.critical_keywords:
            if keyword.lower() in content:
                # 부정적 필터 (루머, 추측 등)
                negative_filters = ['rumor', 'speculation', 'unconfirmed', 'fake', 'false', 
                                  '루머', '추측', '미확인', 'alleged', 'reportedly']
                if any(neg in content for neg in negative_filters):
                    continue
                
                logger.info(f"🚨 크리티컬 키워드 감지: '{keyword}' - {article.get('title', '')[:50]}...")
                return True
        
        # 추가 크리티컬 패턴
        critical_patterns = [
            ('bitcoin', 'etf', 'approved'),
            ('bitcoin', 'etf', 'rejected'),  
            ('bitcoin', 'billion', 'bought'),
            ('bitcoin', 'crosses', '100k'),
            ('tesla', 'bitcoin', 'purchase'),
            ('fed', 'rate', 'decision'),
            ('trump', 'announces', 'tariffs'),
        ]
        
        for pattern in critical_patterns:
            if all(word in content for word in pattern):
                logger.info(f"🚨 크리티컬 패턴 감지: {pattern} - {article.get('title', '')[:50]}...")
                return True
        
        return False
    
    def is_important_news(self, article: Dict) -> bool:
        """중요 뉴스 판단"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        if not self.is_bitcoin_or_macro_related(article):
            return False
        
        for exclude in self.exclude_keywords:
            if exclude.lower() in content:
                return False
        
        weight = article.get('weight', 0)
        category = article.get('category', '')
        
        conditions = [
            category == 'crypto' and weight >= 6,
            category == 'finance' and weight >= 6 and (
                any(word in content for word in ['bitcoin', 'btc', 'crypto']) or
                any(word in content for word in ['fed', 'rate', 'inflation', 'sec', 'tariffs', 'trade'])
            ),
            category == 'api' and weight >= 7,
            any(company.lower() in content for company in self.important_companies) and 
            any(word in content for word in ['bitcoin', 'btc', 'crypto', 'digital', 'blockchain']),
        ]
        
        return any(conditions)
    
    def extract_company_from_content(self, title: str, description: str = "") -> str:
        """컨텐츠에서 기업명 추출"""
        content = (title + " " + description).lower()
        
        found_companies = []
        for company in self.important_companies:
            if company.lower() in content:
                for original in self.important_companies:
                    if original.lower() == company.lower():
                        found_companies.append(original)
                        break
        
        if found_companies:
            return found_companies[0]
        
        return ""
    
    def classify_news_type(self, article: Dict) -> str:
        """뉴스 타입 분류"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # AI 예측 관련
        if any(word in content for word in ['ai based', 'ai predicts', 'energy crisis boom']):
            if 'energy crisis' in content and any(word in content for word in ['250000', '25']):
                return 'energy_crisis_prediction'
            else:
                return 'ai_prediction'
        
        # 가격 돌파/이정표 관련
        if any(word in content for word in ['crosses', '100k', '$100,000', 'milestone', 'breaks', 'hits']):
            if any(word in content for word in ['search', 'google', 'interest', 'attention']):
                return 'price_milestone'
        
        # ETF 관련
        if 'etf' in content:
            if any(word in content for word in ['approved', 'approval', 'launch']):
                return 'etf_approval'
            elif any(word in content for word in ['rejected', 'rejection', 'delay']):
                return 'etf_rejection'
        
        # 기업 투자 - 직접 vs 구조화 상품 구분
        if any(company in content for company in ['tesla', 'microstrategy', 'blackrock', 'gamestop']) and \
           any(word in content for word in ['bought', 'purchased', 'buys', 'adds']):
            return 'corporate_purchase_direct'
        
        # 구조화 상품
        if any(word in content for word in ['structured', 'bonds', 'linked', 'tracking', 'exposure']) and \
           any(word in content for word in ['bitcoin', 'btc']):
            return 'corporate_structured_product'
        
        # 규제 관련
        if any(word in content for word in ['regulation', 'legal', 'court']) and \
           any(word in content for word in ['positive', 'approved', 'favorable']):
            return 'regulation_positive'
        elif any(word in content for word in ['ban', 'prohibited', 'lawsuit', 'illegal']):
            return 'regulation_negative'
        
        # Fed 금리 및 거시경제
        if any(word in content for word in ['fed', 'fomc', 'federal reserve', 'interest rate']):
            return 'fed_rate_decision'
        elif any(word in content for word in ['trump', 'tariffs', 'trade war', 'china tariffs']):
            return 'trade_tariffs'
        elif any(word in content for word in ['inflation', 'cpi', 'pce']):
            return 'inflation_data'
        
        else:
            return 'macro_economic_general'
    
    def estimate_price_impact(self, article: Dict) -> str:
        """현실적 가격 영향 추정"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 과거 패턴 기반 예측
        pattern_match = self._match_historical_pattern(content)
        if pattern_match:
            pattern_data = self.historical_patterns[pattern_match]
            impact = pattern_data['avg_impact']
            duration = pattern_data['duration_hours']
            
            if impact > 0:
                min_impact = max(0.05, impact * 0.8)
                max_impact = impact * 1.2
                direction = "📈 상승"
                emoji = "🚀" if impact >= 2.0 else "📈"
            else:
                min_impact = max(0.05, abs(impact) * 0.8)
                max_impact = abs(impact) * 1.2
                direction = "📉 하락"
                emoji = "🔻" if abs(impact) >= 2.0 else "📉"
            
            return f"{emoji} {direction} {min_impact:.2f}~{max_impact:.2f}% ({duration}시간 내)"
        
        # 키워드 기반 분석
        return self._estimate_by_keywords(content)
    
    def _match_historical_pattern(self, content: str) -> Optional[str]:
        """과거 패턴 매칭"""
        patterns = {
            'etf_approval': ['bitcoin', 'etf', 'approved', 'sec'],
            'etf_rejection': ['bitcoin', 'etf', 'rejected', 'denied'],
            'tesla_purchase': ['tesla', 'bitcoin', 'bought', 'purchase'],
            'microstrategy_purchase': ['microstrategy', 'bitcoin', 'acquired', 'buy'],
            'price_milestone': ['bitcoin', 'crosses', '100k', 'milestone'],
            'price_milestone_low_interest': ['bitcoin', '100k', 'search', 'google'],
            'ai_prediction': ['ai', 'predicts', 'bitcoin', 'price'],
            'energy_crisis_prediction': ['energy', 'crisis', 'bitcoin', 'boom'],
            'fed_rate_hike': ['fed', 'raises', 'rate', 'hike'],
            'fed_rate_cut': ['fed', 'cuts', 'rate', 'lower'],
            'new_tariffs': ['trump', 'tariffs', 'china', 'new'],
            'trade_deal': ['trade', 'deal', 'agreement', 'signed'],
            'corporate_structured_product': ['structured', 'bonds', 'bitcoin', 'linked'],
        }
        
        for pattern_name, keywords in patterns.items():
            matches = sum(1 for keyword in keywords if keyword in content)
            if matches >= 2:
                return pattern_name
        
        return None
    
    def _estimate_by_keywords(self, content: str) -> str:
        """키워드 기반 가격 영향 추정"""
        # AI 예측 관련
        if any(word in content for word in ['ai based', 'ai predicts', 'energy crisis boom']):
            return '⚡ 변동 ±0.05~0.15% (2시간 내)'
        
        # 가격 이정표 관련
        if any(word in content for word in ['bitcoin crosses 100k', 'bitcoin hits 100000']):
            if any(word in content for word in ['google search', 'search unchanged', 'interest low']):
                return '📊 미미한 반응 +0.05~0.20% (4시간 내)'
            else:
                return '📈 상승 0.10~0.40% (8시간 내)'
        
        # ETF 관련
        elif any(word in content for word in ['etf approved', 'etf approval', 'sec approves bitcoin']):
            return '🚀 상승 2.50~4.00% (24시간 내)'
        elif any(word in content for word in ['etf rejected', 'etf denial', 'sec rejects bitcoin']):
            return '🔻 하락 2.00~3.50% (12시간 내)'
        
        # Fed 관련
        elif any(word in content for word in ['fed raises rates', 'rate hike', 'hawkish fed']):
            return '📉 하락 0.80~1.50% (6시간 내)'
        elif any(word in content for word in ['fed cuts rates', 'rate cut', 'dovish fed']):
            return '📈 상승 1.00~2.00% (8시간 내)'
        
        # 기업 구매
        elif any(word in content for word in ['tesla bought bitcoin', 'tesla bitcoin purchase']):
            return '🚀 상승 1.50~3.00% (18시간 내)'
        elif any(word in content for word in ['microstrategy bought bitcoin', 'saylor bitcoin']):
            return '📈 상승 0.50~1.20% (8시간 내)'
        
        # 구조화 상품
        elif any(word in content for word in ['structured', 'bonds', 'linked']):
            return '📊 미미한 반응 +0.05~0.20% (2시간 내)'
        
        # 무역/관세
        elif any(word in content for word in ['new tariffs', 'trade war']):
            return '📉 하락 0.50~1.20% (6시간 내)'
        elif any(word in content for word in ['trade deal', 'trade agreement']):
            return '📈 상승 0.40~1.00% (8시간 내)'
        
        # 기본값
        return '⚡ 변동 ±0.20~0.80% (단기)'
    
    def generate_content_hash(self, title: str, description: str = "") -> str:
        """뉴스 내용의 해시 생성 (중복 체크용)"""
        # 제목과 설명에서 핵심 내용 추출
        content = f"{title} {description[:200]}".lower()
        
        # 숫자 정규화
        content = re.sub(r'[\d,]+', lambda m: m.group(0).replace(',', ''), content)
        
        # 회사명 정규화
        companies_found = []
        for company in self.important_companies:
            if company.lower() in content:
                companies_found.append(company.lower())
        
        # 액션 키워드 추출
        action_keywords = []
        actions = ['bought', 'purchased', 'acquired', 'adds', 'buys', 'sells', 'sold', 
                  'announced', 'launches', 'approves', 'rejects', 'bans', 'raises', 'cuts',
                  'crosses', 'hits', 'breaks', 'reaches']
        for action in actions:
            if action in content:
                action_keywords.append(action)
        
        # BTC 수량 추출
        btc_amounts = re.findall(r'(\d+(?:,\d+)*)\s*(?:btc|bitcoin)', content)
        
        # 가격 관련 키워드 추출
        price_keywords = []
        price_terms = ['100k', '100000', 'milestone', 'search', 'google', 'interest']
        for term in price_terms:
            if term in content:
                price_keywords.append(term)
        
        # 고유 식별자 생성
        unique_parts = []
        if companies_found:
            unique_parts.append('_'.join(sorted(companies_found)))
        if action_keywords:
            unique_parts.append('_'.join(sorted(action_keywords)))
        if btc_amounts:
            unique_parts.append('_'.join(btc_amounts))
        if price_keywords:
            unique_parts.append('_'.join(sorted(price_keywords)))
        
        # 해시 생성
        if unique_parts:
            hash_content = '|'.join(unique_parts)
        else:
            # 핵심 단어만 추출
            words = re.findall(r'\b[a-z]{4,}\b', content)
            important_words = [w for w in words if w not in ['that', 'this', 'with', 'from', 'have', 'been', 'their', 'about']]
            hash_content = ' '.join(sorted(important_words[:10]))
        
        return hashlib.md5(hash_content.encode()).hexdigest()
    
    def is_duplicate_emergency(self, article: Dict, time_window: int = 240) -> bool:
        """긴급 알림이 중복인지 확인 (4시간 이내)"""
        try:
            current_time = datetime.now()
            content_hash = self.generate_content_hash(
                article.get('title', ''), 
                article.get('description', '')
            )
            
            # 크리티컬 리포트 중복 체크
            if content_hash in self.sent_critical_reports:
                last_sent = self.sent_critical_reports[content_hash]
                time_since_last = current_time - last_sent
                
                if time_since_last < timedelta(minutes=time_window):
                    logger.info(f"🔄 중복 크리티컬 리포트 방지: {article.get('title', '')[:50]}... (마지막 전송: {time_since_last})")
                    return True
            
            # 새로운 크리티컬 리포트로 기록
            self.sent_critical_reports[content_hash] = current_time
            
            # 오래된 크리티컬 리포트 기록 정리
            cutoff_time = current_time - timedelta(hours=6)
            self.sent_critical_reports = {
                k: v for k, v in self.sent_critical_reports.items()
                if v > cutoff_time
            }
            
            # 파일에 저장
            self._save_critical_reports()
            
            return False
            
        except Exception as e:
            logger.error(f"❌ 중복 체크 오류: {e}")
            return False
    
    def determine_impact(self, article: Dict) -> str:
        """뉴스 영향도 판단"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        expected_change = self.estimate_price_impact(article)
        
        # AI 예측 특별 처리
        if any(word in content for word in ['ai predicts', 'energy crisis boom', 'ai based']):
            return "💭 추측성 예측"
        
        # 예상 변동률에 따른 영향도
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
    
    def calculate_urgency_level(self, article: Dict) -> str:
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
    
    def calculate_market_relevance(self, article: Dict) -> str:
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
    
    async def create_emergency_event(self, article: Dict, translator=None) -> Dict:
        """긴급 이벤트 생성 - async로 변경"""
        try:
            # 이미 처리된 뉴스인지 확인
            content_hash = self.generate_content_hash(article.get('title', ''), article.get('description', ''))
            if content_hash in self.processed_news_hashes:
                return None
            
            # 처리된 뉴스로 기록
            self.processed_news_hashes.add(content_hash)
            
            # 크기 제한
            if len(self.processed_news_hashes) > 5000:
                self.processed_news_hashes = set(list(self.processed_news_hashes)[-2500:])
            
            # 최초 발견 시간 기록
            if content_hash not in self.news_first_seen:
                self.news_first_seen[content_hash] = datetime.now()
            
            # 번역 처리 (translator가 제공된 경우에만)
            if translator and translator.should_translate_for_emergency_report(article):
                translated_title = await translator.translate_text(article.get('title', ''))
                article['title_ko'] = translated_title
                logger.info(f"🔥 긴급 리포트 번역 완료: {translated_title[:50]}...")
            else:
                article['title_ko'] = article.get('title', '')
            
            # 이벤트 생성
            event = {
                'type': 'critical_news',
                'title': article.get('title', ''),
                'title_ko': article.get('title_ko', article.get('title', '')),
                'description': article.get('description', '')[:1600],
                'summary': article.get('summary', ''),
                'company': self.extract_company_from_content(
                    article.get('title', ''),
                    article.get('description', '')
                ),
                'source': article.get('source', ''),
                'url': article.get('url', ''),
                'timestamp': datetime.now(),
                'severity': 'critical',
                'impact': self.determine_impact(article),
                'expected_change': self.estimate_price_impact(article),
                'weight': article.get('weight', 5),
                'category': article.get('category', 'unknown'),
                'published_at': article.get('published_at', ''),
                'first_seen': self.news_first_seen[content_hash],
                'urgency_level': self.calculate_urgency_level(article),
                'market_relevance': self.calculate_market_relevance(article),
                'pattern_match': self._match_historical_pattern(
                    (article.get('title', '') + ' ' + article.get('description', '')).lower()
                )
            }
            
            # 파일에 저장
            self._save_duplicate_data()
            
            logger.info(f"🚨 크리티컬 이벤트 생성: {event['impact']} - {event['title_ko'][:60]}...")
            
            return event
            
        except Exception as e:
            logger.error(f"❌ 긴급 이벤트 생성 오류: {e}")
            return None
    
    def is_similar_news(self, title1: str, title2: str) -> bool:
        """유사 뉴스 판별"""
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
        
        # 단어 집합 비교
        words1 = set(clean1.split())
        words2 = set(clean2.split())
        
        if not words1 or not words2:
            return False
        
        # 교집합 비율 계산
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        similarity = intersection / union if union > 0 else 0
        
        # 80% 이상 유사하면 중복
        return similarity > 0.8
    
    def cleanup_old_data(self):
        """오래된 데이터 정리"""
        try:
            current_time = datetime.now()
            
            # 일일 리셋
            if current_time.date() > getattr(self, 'last_cleanup_date', current_time.date() - timedelta(days=1)):
                self.company_news_count = {}
                self.news_first_seen = {}
                
                # 크리티컬 리포트 중복 방지 데이터 정리
                cutoff_time = current_time - timedelta(hours=12)
                self.sent_critical_reports = {
                    k: v for k, v in self.sent_critical_reports.items()
                    if v > cutoff_time
                }
                self._save_critical_reports()
                
                logger.info(f"🔄 뉴스 처리기 일일 리셋 완료")
                self.last_cleanup_date = current_time.date()
                
        except Exception as e:
            logger.error(f"❌ 오래된 데이터 정리 실패: {e}")
