# report_generators/base_generator.py
from datetime import datetime, timedelta
import asyncio
from typing import Dict, List, Optional, Any, Set
import logging
import pytz
import traceback
import re
import hashlib

class BaseReportGenerator:
    """리포트 생성기 기본 클래스"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        self.config = config
        self.data_collector = data_collector
        self.indicator_system = indicator_system
        self.bitget_client = bitget_client
        self.logger = logging.getLogger(self.__class__.__name__)
        self.kst = pytz.timezone('Asia/Seoul')
        self.processed_news_hashes: Set[str] = set()  # 처리된 뉴스 해시
        
        # OpenAI 클라이언트 초기화
        self.openai_client = None
        if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY:
            import openai
            self.openai_client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    
    def set_bitget_client(self, bitget_client):
        """Bitget 클라이언트 설정"""
        self.bitget_client = bitget_client
        self.logger.info("✅ Bitget 클라이언트 설정 완료")
    
    def _generate_news_hash(self, title: str, source: str = "") -> str:
        """뉴스 제목과 소스로 해시 생성"""
        # 제목에서 숫자와 특수문자 제거
        clean_title = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title.lower())
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        # 회사명 추출
        companies = ['gamestop', 'tesla', 'microstrategy', 'metaplanet', '게임스탑', '테슬라', '메타플래닛']
        found_companies = [c for c in companies if c in clean_title]
        
        # 키워드 추출
        keywords = ['bitcoin', 'btc', 'purchase', 'bought', 'buys', '구매', '매입', 'etf', '승인']
        found_keywords = [k for k in keywords if k in clean_title]
        
        # 회사명과 키워드로 해시 생성
        if found_companies and found_keywords:
            hash_content = f"{','.join(sorted(found_companies))}_{','.join(sorted(found_keywords))}"
        else:
            hash_content = clean_title
        
        return hashlib.md5(f"{hash_content}_{source}".encode()).hexdigest()
    
    def _is_similar_news(self, title1: str, title2: str) -> bool:
        """두 뉴스 제목이 유사한지 확인"""
        # 숫자와 특수문자 제거
        clean1 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title1.lower())
        clean2 = re.sub(r'[0-9$,.\-:;!?@#%^&*()\[\]{}]', '', title2.lower())
        
        clean1 = re.sub(r'\s+', ' ', clean1).strip()
        clean2 = re.sub(r'\s+', ' ', clean2).strip()
        
        # 단어 집합 비교
        words1 = set(clean1.split())
        words2 = set(clean2.split())
        
        if not words1 or not words2:
            return False
        
        # 교집합 비율 계산
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        similarity = intersection / union if union > 0 else 0
        
        # 70% 이상 유사하면 중복으로 간주
        return similarity > 0.7
    
    async def analyze_news_impact(self, title: str, description: str = "") -> str:
        """통합 뉴스 영향 분석 - 개선된 로직"""
        # 전체 텍스트 (제목 + 설명)
        full_text = (title + " " + description).lower()
        
        # 영향도 점수 계산
        bullish_score = 0
        bearish_score = 0
        impact_reason = []
        
        # 강한 호재 키워드 (확장 및 개선)
        strong_bullish = {
            # ETF 관련
            'etf approved': (5, 'ETF 승인'),
            'etf 승인': (5, 'ETF 승인'),
            'etf approval': (5, 'ETF 승인 가능성'),
            
            # 기관 채택
            'institutional adoption': (4, '기관 채택'),
            '기관 채택': (4, '기관 채택'),
            'institutional investment': (4, '기관 투자'),
            'corporate treasury': (4, '기업 자금 투자'),
            
            # 직접 매입
            'btc 구매': (5, 'BTC 직접 매입'),
            'bitcoin 구매': (5, 'BTC 직접 매입'),
            'bitcoin purchase': (5, 'BTC 직접 매입'),
            'bought bitcoin': (5, 'BTC 매입 완료'),
            '비트코인 매입': (5, 'BTC 직접 매입'),
            'btc로 첫': (5, '첫 BTC 매입'),
            
            # 금액 관련
            '억 달러': (4, '대규모 자금 유입'),
            'million dollar': (3, '대규모 자금'),
            'billion dollar': (5, '초대규모 자금'),
            
            # 규제 우호
            'bitcoin reserve': (5, '비트코인 준비금'),
            '비트코인 준비금': (5, '비트코인 준비금'),
            'legal tender': (5, '법정화폐 지정'),
            '법정화폐': (5, '법정화폐 지정'),
            'regulatory clarity': (3, '규제 명확화'),
            
            # 시장 긍정
            'bullish': (3, '강세 신호'),
            '상승': (2, '상승 신호'),
            'surge': (3, '급등'),
            '급등': (3, '급등'),
            'rally': (3, '랠리'),
            '랠리': (3, '랠리'),
            'all time high': (3, '신고가'),
            'ath': (3, '신고가'),
            '신고가': (3, '신고가'),
            'breakthrough': (3, '돌파'),
            '돌파': (3, '돌파'),
            
            # 기업 관련
            'gamestop': (4, '게임스탑 참여'),
            '게임스탑': (4, '게임스탑 참여'),
            'metaplanet': (4, '메타플래닛 참여'),
            '메타플래닛': (4, '메타플래닛 참여'),
            'microstrategy': (4, '마이크로스트래티지'),
            'tesla': (4, '테슬라 관련'),
            
            # 긍정적 판결/발표
            '증권이 아니': (4, '증권 분류 제외'),
            'not securities': (4, '증권 분류 제외'),
            'not a security': (4, '증권 분류 제외'),
        }
        
        # 강한 악재 키워드 (확장 및 개선)
        strong_bearish = {
            'ban': (5, '금지'),
            '금지': (5, '금지'),
            'banned': (5, '금지됨'),
            'crackdown': (4, '단속'),
            '단속': (4, '단속'),
            'lawsuit': (4, '소송'),
            '소송': (4, '소송'),
            'sec lawsuit': (5, 'SEC 소송'),
            'sec charges': (5, 'SEC 기소'),
            'sec 기소': (5, 'SEC 기소'),
            'hack': (5, '해킹'),
            '해킹': (5, '해킹'),
            'hacked': (5, '해킹 발생'),
            'bankruptcy': (5, '파산'),
            '파산': (5, '파산'),
            'liquidation': (4, '청산'),
            '청산': (4, '청산'),
            'crash': (5, '폭락'),
            '폭락': (5, '폭락'),
            'plunge': (4, '급락'),
            '급락': (4, '급락'),
            'investigation': (3, '조사'),
            '조사': (3, '조사'),
            'fraud': (5, '사기'),
            '사기': (5, '사기'),
            'shutdown': (4, '폐쇄'),
            'exit scam': (5, '먹튀'),
        }
        
        # 약한 호재 키워드
        mild_bullish = {
            'buy': (1, '매입'),
            '매입': (1, '매입'),
            'invest': (1, '투자'),
            '투자': (1, '투자'),
            'adoption': (2, '채택'),
            '채택': (2, '채택'),
            'positive': (1, '긍정적'),
            '긍정': (1, '긍정적'),
            'growth': (1, '성장'),
            '성장': (1, '성장'),
            'partnership': (2, '파트너십'),
            '파트너십': (2, '파트너십'),
            'upgrade': (2, '상향'),
            '상향': (2, '상향'),
            'support': (1, '지지'),
            '지지': (1, '지지'),
            'accumulate': (2, '축적'),
            '축적': (2, '축적'),
            'integration': (2, '통합'),
            'mainstream': (2, '주류 편입'),
        }
        
        # 약한 악재 키워드
        mild_bearish = {
            'sell': (1, '매도'),
            '매도': (1, '매도'),
            'concern': (1, '우려'),
            '우려': (1, '우려'),
            'risk': (1, '위험'),
            '위험': (1, '위험'),
            'regulation': (2, '규제'),
            '규제': (2, '규제'),
            'warning': (2, '경고'),
            '경고': (2, '경고'),
            'decline': (1, '하락'),
            '하락': (1, '하락'),
            'uncertainty': (2, '불확실성'),
            '불확실': (2, '불확실성'),
            'delay': (2, '지연'),
            '지연': (2, '지연'),
            'reject': (3, '거부'),
            '거부': (3, '거부'),
            'rejected': (3, '거부됨'),
            'bearish': (2, '약세'),
            'correction': (2, '조정'),
        }
        
        # 점수 계산 - 키워드별 가중치와 이유 저장
        for keyword, (weight, reason) in strong_bullish.items():
            if keyword in full_text:
                bullish_score += weight
                if reason not in impact_reason:
                    impact_reason.append(reason)
        
        for keyword, (weight, reason) in strong_bearish.items():
            if keyword in full_text:
                bearish_score += weight
                if reason not in impact_reason:
                    impact_reason.append(reason)
        
        for keyword, (weight, reason) in mild_bullish.items():
            if keyword in full_text:
                bullish_score += weight
                if reason not in impact_reason:
                    impact_reason.append(reason)
        
        for keyword, (weight, reason) in mild_bearish.items():
            if keyword in full_text:
                bearish_score += weight
                if reason not in impact_reason:
                    impact_reason.append(reason)
        
        # 특수 케이스 처리
        # Fed/FOMC 관련
        if any(word in full_text for word in ['fed', 'fomc', '연준', '금리', 'federal reserve']):
            if any(word in full_text for word in ['raise', 'hike', '인상', 'hawkish', '매파']):
                bearish_score += 3
                impact_reason.append('금리 인상')
            elif any(word in full_text for word in ['cut', 'lower', '인하', 'dovish', '비둘기']):
                bullish_score += 3
                impact_reason.append('금리 인하')
            elif any(word in full_text for word in ['pause', 'hold', '유지', '동결']):
                bullish_score += 1
                impact_reason.append('금리 동결')
        
        # BoJ (일본은행) 관련
        if 'boj' in full_text or '일본은행' in full_text:
            if '금리 인상' in full_text or 'rate hike' in full_text:
                bearish_score += 2
                impact_reason.append('엔화 강세 우려')
        
        # 중국 관련
        if any(word in full_text for word in ['china', '중국', 'chinese']):
            if any(word in full_text for word in ['ban', '금지', 'crackdown', '단속']):
                bearish_score += 3
                impact_reason.append('중국 규제')
            elif any(word in full_text for word in ['open', '개방', 'allow', '허용', 'approve']):
                bullish_score += 3
                impact_reason.append('중국 개방')
        
        # USD/JPY 관련 (달러/엔 환율)
        if 'usd/jpy' in full_text or '달러엔' in full_text:
            # USD/JPY는 비트코인과 직접적 관련이 적으므로 영향도를 낮춤
            if impact_reason and '엔화' not in ' '.join(impact_reason):
                impact_reason.append('간접 영향')
        
        # 최종 판단
        net_score = bullish_score - bearish_score
        
        # 이유가 없으면 일반적인 판단
        if not impact_reason:
            if '가격' in full_text or 'price' in full_text:
                if '멈춰' in full_text or 'stop' in full_text or 'halt' in full_text:
                    impact_reason.append('가격 정체')
        
        # 점수 기반 최종 판단
        if net_score >= 5:
            result = "➕강한 호재"
        elif net_score >= 2:
            result = "➕호재 예상"
        elif net_score <= -5:
            result = "➖강한 악재"
        elif net_score <= -2:
            result = "➖악재 예상"
        else:
            # 중립이지만 이유가 있는 경우
            if impact_reason:
                if bullish_score > bearish_score:
                    result = "➕약한 호재"
                elif bearish_score > bullish_score:
                    result = "➖약한 악재"
                else:
                    result = "중립"
            else:
                result = "중립"
        
        # 이유 추가
        if impact_reason and result != "중립":
            reason_text = ', '.join(impact_reason[:3])  # 최대 3개 이유만
            return f"{result} ({reason_text})"
        
        return result
    
    async def format_news_with_time(self, news_list: List[Dict], max_items: int = 4) -> List[str]:
        """뉴스를 시간 포함 형식으로 포맷팅 - 중복 제거 강화"""
        formatted = []
        seen_hashes = set()
        seen_titles = []
        
        for news in news_list[:max_items * 2]:  # 중복 제거를 위해 더 많이 처리
            try:
                # 시간 처리
                if news.get('published_at'):
                    pub_time_str = news.get('published_at', '').replace('Z', '+00:00')
                    if 'T' in pub_time_str:
                        pub_time = datetime.fromisoformat(pub_time_str)
                    else:
                        from dateutil import parser
                        pub_time = parser.parse(pub_time_str)
                    
                    pub_time_kst = pub_time.astimezone(self.kst)
                    time_str = pub_time_kst.strftime('%m-%d %H:%M')
                else:
                    time_str = datetime.now(self.kst).strftime('%m-%d %H:%M')
                
                # 한글 제목 우선 사용
                title = news.get('title_ko', news.get('title', '')).strip()
                description = news.get('description', '')
                source = news.get('source', '')
                
                # 중복 체크
                news_hash = self._generate_news_hash(title, source)
                if news_hash in seen_hashes:
                    continue
                
                # 유사한 제목 체크
                is_similar = False
                for seen_title in seen_titles:
                    if self._is_similar_news(title, seen_title):
                        is_similar = True
                        break
                
                if is_similar:
                    continue
                
                # 통합 영향 분석
                impact = await self.analyze_news_impact(title, description)
                
                # 형식: 시간 "제목" → 영향
                formatted_news = f'{time_str} "{title[:60]}{"..." if len(title) > 60 else ""}" → {impact}'
                formatted.append(formatted_news)
                seen_hashes.add(news_hash)
                seen_titles.append(title)
                
                # 원하는 개수만큼 수집했으면 종료
                if len(formatted) >= max_items:
                    break
                
            except Exception as e:
                self.logger.warning(f"뉴스 포맷팅 오류: {e}")
                continue
        
        return formatted
    
    async def _collect_all_data(self) -> Dict:
        """모든 데이터 수집"""
        try:
            # 병렬로 데이터 수집
            tasks = [
                self._get_market_data(),
                self._get_account_info(),
                self._get_position_info()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            market_data = results[0] if not isinstance(results[0], Exception) else {}
            account_info = results[1] if not isinstance(results[1], Exception) else {}
            position_info = results[2] if not isinstance(results[2], Exception) else {}
            
            # 이벤트 버퍼에서 가져오기
            events = []
            if self.data_collector and hasattr(self.data_collector, 'events_buffer'):
                events = self.data_collector.events_buffer[-5:]  # 최근 5개
            
            return {
                **market_data,
                'account': account_info,
                'positions': position_info,
                'events': events
            }
            
        except Exception as e:
            self.logger.error(f"데이터 수집 실패: {e}")
            return {}
    
    async def _get_market_data(self) -> Dict:
        """시장 데이터 조회"""
        try:
            if not self.bitget_client:
                return {}
            
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            
            # 안전한 데이터 추출
            current_price = float(ticker.get('last', ticker.get('lastPr', 0)))
            high_24h = float(ticker.get('high24h', ticker.get('high', 0)))
            low_24h = float(ticker.get('low24h', ticker.get('low', 0)))
            volume_24h = float(ticker.get('baseVolume', ticker.get('volume', 0)))
            change_24h = float(ticker.get('changeUtc', ticker.get('change24h', 0)))
            
            # 변동성 계산
            volatility = ((high_24h - low_24h) / current_price * 100) if current_price > 0 else 0
            
            # 펀딩비
            try:
                funding_data = await self.bitget_client.get_funding_rate('BTCUSDT')
                funding_rate = float(funding_data.get('fundingRate', 0)) if isinstance(funding_data, dict) else 0
            except:
                funding_rate = 0
            
            return {
                'current_price': current_price,
                'high_24h': high_24h,
                'low_24h': low_24h,
                'volume_24h': volume_24h,
                'change_24h': change_24h,
                'volatility': volatility,
                'funding_rate': funding_rate
            }
            
        except Exception as e:
            self.logger.error(f"시장 데이터 조회 실패: {str(e)}")
            return {}
    
    async def _get_position_info(self) -> Dict:
        """포지션 정보 조회 - API 데이터만 사용"""
        try:
            if not self.bitget_client:
                return {'has_position': False}
            
            positions = await self.bitget_client.get_positions('BTCUSDT')
            
            if not positions:
                return {'has_position': False}
            
            # 활성 포지션 찾기
            active_position = None
            for pos in positions:
                total_size = float(pos.get('total', 0))
                if total_size > 0:
                    active_position = pos
                    break
            
            if not active_position:
                return {'has_position': False}
            
            # 현재가 조회
            ticker = await self.bitget_client.get_ticker('BTCUSDT')
            current_price = float(ticker.get('last', ticker.get('lastPr', 0)))
            
            # 포지션 상세 정보 - API에서 제공하는 값만 사용
            side = active_position.get('holdSide', '').lower()
            size = float(active_position.get('total', 0))
            entry_price = float(active_position.get('openPriceAvg', 0))
            unrealized_pnl = float(active_position.get('unrealizedPL', 0))
            margin = float(active_position.get('marginSize', 0))  # marginSize가 정확한 증거금
            leverage = int(float(active_position.get('leverage', 1)))
            
            # 청산가 - API에서 직접 가져오기
            liquidation_price = float(active_position.get('liquidationPrice', 0))
            
            # 손익률 계산 - achievedProfits 대신 unrealizedPL 사용
            pnl_rate = unrealized_pnl / margin if margin > 0 else 0
            
            return {
                'has_position': True,
                'symbol': active_position.get('symbol', 'BTCUSDT'),
                'side': '숏' if side in ['short', 'sell'] else '롱',
                'side_en': side,
                'size': size,
                'entry_price': entry_price,
                'current_price': current_price,
                'liquidation_price': liquidation_price,
                'pnl_rate': pnl_rate,
                'unrealized_pnl': unrealized_pnl,
                'margin': margin,
                'leverage': leverage
            }
            
        except Exception as e:
            self.logger.error(f"포지션 정보 조회 실패: {str(e)}")
            return {'has_position': False}
    
    async def _get_account_info(self) -> Dict:
        """계정 정보 조회 - API 값만 사용"""
        try:
            if not self.bitget_client:
                return {}
            
            account = await self.bitget_client.get_account_info()
            
            # API에서 제공하는 값만 사용
            total_equity = float(account.get('accountEquity', 0))
            available = float(account.get('crossedMaxAvailable', 0))
            used_margin = float(account.get('crossedMargin', 0))
            unrealized_pnl = float(account.get('unrealizedPL', 0))
            margin_ratio = float(account.get('crossedRiskRate', 0))
            
            return {
                'total_equity': total_equity,
                'available': available,
                'used_margin': used_margin,
                'margin_ratio': margin_ratio * 100,
                'unrealized_pnl': unrealized_pnl,
                'locked': float(account.get('locked', 0))
            }
            
        except Exception as e:
            self.logger.error(f"계정 정보 조회 실패: {str(e)}")
            return {}
    
    async def _get_today_realized_pnl(self) -> float:
        """금일 실현 손익 조회 - API 값만 사용"""
        try:
            if not self.bitget_client:
                return 0.0
            
            # KST 기준 금일 0시부터 현재까지
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            start_time = int(today_start.timestamp() * 1000)
            end_time = int(now.timestamp() * 1000)
            
            # 거래 내역 조회
            fills = await self.bitget_client.get_trade_fills('BTCUSDT', start_time, end_time, 500)
            
            if not fills:
                return 0.0
            
            total_realized_pnl = 0.0
            
            for fill in fills:
                try:
                    # API에서 제공하는 profit 필드만 사용
                    profit = float(fill.get('profit', 0))
                    
                    # 수수료
                    fee = 0.0
                    fee_detail = fill.get('feeDetail', [])
                    if isinstance(fee_detail, list):
                        for fee_info in fee_detail:
                            if isinstance(fee_info, dict):
                                fee += abs(float(fee_info.get('totalFee', 0)))
                    
                    total_realized_pnl += (profit - fee)
                    
                except Exception as e:
                    self.logger.warning(f"거래 파싱 오류: {e}")
                    continue
            
            return total_realized_pnl
            
        except Exception as e:
            self.logger.error(f"금일 실현 손익 조회 실패: {e}")
            return 0.0
    
    async def _get_weekly_profit(self) -> Dict:
        """7일 수익 조회 - API 값만 사용"""
        try:
            if not self.bitget_client:
                return {'total': 0.0, 'average': 0.0}
            
            # API에서 7일 손익 데이터 가져오기
            profit_data = await self.bitget_client.get_profit_loss_history('BTCUSDT', 7)
            
            return {
                'total': profit_data.get('total_pnl', 0),
                'average': profit_data.get('average_daily', 0),
                'source': 'API'
            }
            
        except Exception as e:
            self.logger.error(f"7일 수익 조회 실패: {e}")
            return {'total': 0.0, 'average': 0.0}
    
    def _format_currency(self, amount: float, include_krw: bool = True) -> str:
        """통화 포맷팅"""
        usd_text = f"${amount:+,.2f}" if amount != 0 else "$0.00"
        if include_krw and amount != 0:
            krw_amount = amount * 1350 / 10000
            return f"{usd_text} ({krw_amount:+.1f}만원)"
        return usd_text
    
    def _get_current_time_kst(self) -> str:
        """현재 KST 시간 문자열"""
        return datetime.now(self.kst).strftime('%Y-%m-%d %H:%M')
    
    def _format_price_with_change(self, price: float, change_24h: float) -> str:
        """가격과 24시간 변동률 포맷팅"""
        change_percent = change_24h * 100
        change_emoji = "📈" if change_24h > 0 else "📉" if change_24h < 0 else "➖"
        return f"${price:,.0f} {change_emoji} ({change_percent:+.1f}%)"
    
    async def _get_recent_news(self, hours: int = 6) -> List[Dict]:
        """최근 뉴스 가져오기 - 중복 제거"""
        try:
            if self.data_collector:
                all_news = await self.data_collector.get_recent_news(hours)
                
                # 추가 중복 제거
                filtered_news = []
                seen_hashes = set()
                
                for news in all_news:
                    news_hash = self._generate_news_hash(
                        news.get('title_ko', news.get('title', '')),
                        news.get('source', '')
                    )
                    
                    if news_hash not in seen_hashes and news_hash not in self.processed_news_hashes:
                        filtered_news.append(news)
                        seen_hashes.add(news_hash)
                        self.processed_news_hashes.add(news_hash)
                
                # 해시 세트가 너무 커지면 정리
                if len(self.processed_news_hashes) > 500:
                    self.processed_news_hashes = set(list(self.processed_news_hashes)[-250:])
                
                return filtered_news
            
            return []
        except Exception as e:
            self.logger.error(f"뉴스 조회 실패: {e}")
            return []
