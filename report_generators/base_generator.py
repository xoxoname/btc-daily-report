# report_generators/base_generator.py
from datetime import datetime, timedelta
import asyncio
from typing import Dict, List, Optional, Any
import logging
import pytz
import traceback

class BaseReportGenerator:
    """리포트 생성기 기본 클래스"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        self.config = config
        self.data_collector = data_collector
        self.indicator_system = indicator_system
        self.bitget_client = bitget_client
        self.logger = logging.getLogger(self.__class__.__name__)
        self.kst = pytz.timezone('Asia/Seoul')
        
        # OpenAI 클라이언트 초기화
        self.openai_client = None
        if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY:
            import openai
            self.openai_client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    
    def set_bitget_client(self, bitget_client):
        """Bitget 클라이언트 설정"""
        self.bitget_client = bitget_client
        self.logger.info("✅ Bitget 클라이언트 설정 완료")
    
    def _format_price_with_change(self, current_price: float, change_24h: float) -> str:
        """현재가와 24시간 변동률을 함께 표시"""
        change_percent = change_24h * 100
        return f"${current_price:,.0f} ({change_percent:+.2f}%)"
    
    async def analyze_news_impact(self, title: str, description: str = "") -> str:
        """통합 뉴스 영향 분석 - 모든 리포트에서 동일한 결과 반환"""
        # 전체 텍스트 (제목 + 설명)
        full_text = (title + " " + description).lower()
        
        # 영향도 점수 계산
        bullish_score = 0
        bearish_score = 0
        
        # 강한 호재 키워드
        strong_bullish = [
            'etf approved', 'etf 승인', 'institutional adoption', '기관 채택',
            'bitcoin reserve', '비트코인 준비금', 'legal tender', '법정화폐',
            'bullish', '상승', 'surge', '급등', 'rally', '랠리',
            'all time high', 'ath', '신고가', 'breakthrough', '돌파'
        ]
        
        # 강한 악재 키워드
        strong_bearish = [
            'ban', '금지', 'crackdown', '단속', 'lawsuit', '소송',
            'hack', '해킹', 'bankruptcy', '파산', 'liquidation', '청산',
            'crash', '폭락', 'plunge', '급락', 'investigation', '조사',
            'sec charges', 'sec 기소', 'fraud', '사기'
        ]
        
        # 일반 호재 키워드
        mild_bullish = [
            'buy', '매입', 'invest', '투자', 'adoption', '채택',
            'positive', '긍정', 'growth', '성장', 'partnership', '파트너십',
            'upgrade', '상향', 'support', '지지', 'accumulate', '축적'
        ]
        
        # 일반 악재 키워드
        mild_bearish = [
            'sell', '매도', 'concern', '우려', 'risk', '위험',
            'regulation', '규제', 'warning', '경고', 'decline', '하락',
            'uncertainty', '불확실', 'delay', '지연', 'reject', '거부'
        ]
        
        # 점수 계산
        for keyword in strong_bullish:
            if keyword in full_text:
                bullish_score += 3
        
        for keyword in strong_bearish:
            if keyword in full_text:
                bearish_score += 3
        
        for keyword in mild_bullish:
            if keyword in full_text:
                bullish_score += 1
        
        for keyword in mild_bearish:
            if keyword in full_text:
                bearish_score += 1
        
        # 특수 케이스 처리
        # Fed/FOMC 관련
        if any(word in full_text for word in ['fed', 'fomc', '연준', '금리']):
            if any(word in full_text for word in ['raise', 'hike', '인상', 'hawkish', '매파']):
                bearish_score += 2
            elif any(word in full_text for word in ['cut', 'lower', '인하', 'dovish', '비둘기']):
                bullish_score += 2
            else:
                # 중립적 금리 뉴스
                return "중립 (금리 정책 관망)"
        
        # 중국 관련
        if any(word in full_text for word in ['china', '중국']):
            if any(word in full_text for word in ['ban', '금지', 'crackdown', '단속']):
                bearish_score += 2
            elif any(word in full_text for word in ['open', '개방', 'allow', '허용']):
                bullish_score += 2
        
        # 최종 판단
        net_score = bullish_score - bearish_score
        
        if net_score >= 3:
            return "➕강한 호재"
        elif net_score >= 1:
            return "➕호재 예상"
        elif net_score <= -3:
            return "➖강한 악재"
        elif net_score <= -1:
            return "➖악재 예상"
        else:
            # 중립적이지만 특정 카테고리 확인
            if '비트코인' in full_text or 'bitcoin' in full_text:
                if '매입' in full_text or 'buy' in full_text:
                    return "➕호재 예상"
                elif '매도' in full_text or 'sell' in full_text:
                    return "➖악재 예상"
            
            return "중립"
    
    async def format_news_with_time(self, news_list: List[Dict], max_items: int = 4) -> List[str]:
        """뉴스를 시간 포함 형식으로 포맷팅"""
        formatted = []
        
        for news in news_list[:max_items]:
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
                
                # 통합 영향 분석
                impact = await self.analyze_news_impact(title, description)
                
                # 형식: 시간 "제목" → 영향
                formatted.append(f'{time_str} "{title[:60]}{"..." if len(title) > 60 else ""}" → {impact}')
                
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
            return f"{usd_text} (약 {krw_amount:+.1f}만원)"
        return usd_text
    
    def _get_current_time_kst(self) -> str:
        """현재 KST 시간 문자열"""
        return datetime.now(self.kst).strftime('%Y-%m-%d %H:%M')
    
    async def _get_recent_news(self, hours: int = 6) -> List[Dict]:
        """최근 뉴스 가져오기"""
        try:
            if self.data_collector:
                return await self.data_collector.get_recent_news(hours)
            return []
        except Exception as e:
            self.logger.error(f"뉴스 조회 실패: {e}")
            return []
