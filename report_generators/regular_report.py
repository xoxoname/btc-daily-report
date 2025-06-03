# report_generators/regular_report.py
from .base_generator import BaseReportGenerator
from .mental_care import MentalCareGenerator
import traceback
from datetime import datetime, timedelta
import json
import pytz
import os
import logging
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

class RegularReportGenerator(BaseReportGenerator):
    """🔥🔥 완전히 재작성된 정기 리포트 - 실전 매매 특화"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        self.mental_care = MentalCareGenerator(self.openai_client)
        self.prediction_history_file = 'prediction_history.json'
        self.prediction_history = []
        self._load_prediction_history()
        
        # 캐시 시스템
        self.market_cache = {}
        self.indicators_cache = {}
        self.news_cache = []
        self.analysis_cache = {}
        
        # 실시간 뉴스 수집을 위한 세션
        self.news_session = None
        
        logger.info("🔥🔥 강화된 정기 리포트 생성기 초기화 완료")
    
    def _load_prediction_history(self):
        """예측 기록 로드"""
        try:
            if os.path.exists(self.prediction_history_file):
                with open(self.prediction_history_file, 'r', encoding='utf-8') as f:
                    self.prediction_history = json.load(f)
                # 최근 50개만 유지
                if len(self.prediction_history) > 50:
                    self.prediction_history = self.prediction_history[-50:]
            else:
                self.prediction_history = []
        except Exception as e:
            logger.error(f"예측 기록 로드 실패: {e}")
            self.prediction_history = []
    
    def _save_prediction_history(self):
        """예측 기록 저장"""
        try:
            with open(self.prediction_history_file, 'w', encoding='utf-8') as f:
                json.dump(self.prediction_history, f, indent=2)
        except Exception as e:
            logger.error(f"예측 기록 저장 실패: {e}")

    async def generate_report(self) -> str:
        """🔥🔥 완전히 재작성된 정밀 분석 리포트"""
        try:
            current_time = self._get_current_time_kst()
            
            logger.info("🔥🔥 강화된 정기 리포트 생성 시작")
            
            # 1. 실시간 시장 데이터 수집 (병렬 처리)
            market_data_task = self._collect_enhanced_market_data()
            indicators_task = self._calculate_comprehensive_indicators()
            news_task = self._collect_real_time_market_events()
            
            market_data, indicators, news_events = await asyncio.gather(
                market_data_task, indicators_task, news_task, return_exceptions=True
            )
            
            # 예외 처리
            if isinstance(market_data, Exception):
                logger.error(f"시장 데이터 수집 실패: {market_data}")
                market_data = {}
            if isinstance(indicators, Exception):
                logger.error(f"지표 계산 실패: {indicators}")
                indicators = {}
            if isinstance(news_events, Exception):
                logger.error(f"뉴스 수집 실패: {news_events}")
                news_events = []
            
            # 2. 이전 예측 검증
            prediction_validation = await self._comprehensive_prediction_validation(market_data)
            
            # 3. 종합 분석 및 리포트 섹션 생성
            events_section = await self._format_critical_market_events(news_events)
            market_section = await self._format_enhanced_market_status(market_data)
            indicators_section = await self._format_detailed_technical_analysis(indicators, market_data)
            signals_section = await self._format_precision_trading_signals(indicators, market_data)
            strategy_section = await self._format_actionable_trading_strategy(indicators, market_data)
            prediction_section = await self._format_intelligent_price_prediction(indicators, market_data)
            pnl_section = await self._format_comprehensive_pnl()
            mental_section = await self._generate_intelligent_mental_care(market_data, indicators)
            
            # 4. 현재 예측 저장
            await self._save_current_prediction(market_data, indicators)
            
            # 5. 최종 리포트 조합
            report = f"""<b>🧾 비트코인 선물 정밀 분석 리포트</b>
<b>📅 {current_time}</b> | <b>🎯 25개 지표 종합 분석</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🚨 최근 중요 시장 이벤트 (6시간)</b>
{events_section}

<b>📊 현재 시장 상황</b>
{market_section}

<b>🔧 기술적 지표 종합 분석 (25개 지표)</b>
{indicators_section}

<b>🎯 핵심 매매 신호</b>
{signals_section}

<b>💡 실전 매매 전략</b>
{strategy_section}

<b>🔮 AI 정밀 예측 (12시간)</b>
{prediction_section}

<b>📈 이전 예측 검증</b>
{prediction_validation}

<b>💰 통합 손익 현황</b>
{pnl_section}

<b>🧠 오늘의 매매 조언</b>
{mental_section}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>⚡ 실시간 분석 완료</b> | 다음 업데이트: 3시간 후"""
            
            logger.info("✅ 강화된 정기 리포트 생성 완료")
            return report
            
        except Exception as e:
            logger.error(f"정기 리포트 생성 실패: {str(e)}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return f"❌ 리포트 생성 중 오류가 발생했습니다: {str(e)}"

    async def _collect_enhanced_market_data(self) -> dict:
        """🔥 강화된 시장 데이터 수집"""
        try:
            market_data = {}
            
            if self.bitget_client:
                # 기본 티커 정보
                ticker = await self.bitget_client.get_ticker('BTCUSDT')
                if ticker:
                    market_data.update({
                        'current_price': float(ticker.get('last', 0)),
                        'change_24h': float(ticker.get('changeUtc', 0)),
                        'high_24h': float(ticker.get('high24h', 0)),
                        'low_24h': float(ticker.get('low24h', 0)),
                        'volume_24h': float(ticker.get('baseVolume', 0)),
                        'quote_volume_24h': float(ticker.get('quoteVolume', 0))
                    })
                
                # K라인 데이터 (여러 시간대)
                try:
                    klines_1m = await self.bitget_client.get_kline('BTCUSDT', '1m', 60)
                    klines_5m = await self.bitget_client.get_kline('BTCUSDT', '5m', 100)
                    klines_15m = await self.bitget_client.get_kline('BTCUSDT', '15m', 100)
                    klines_1h = await self.bitget_client.get_kline('BTCUSDT', '1H', 200)
                    klines_4h = await self.bitget_client.get_kline('BTCUSDT', '4H', 100)
                    klines_1d = await self.bitget_client.get_kline('BTCUSDT', '1D', 50)
                    
                    market_data.update({
                        'klines_1m': klines_1m,
                        'klines_5m': klines_5m,
                        'klines_15m': klines_15m,
                        'klines_1h': klines_1h,
                        'klines_4h': klines_4h,
                        'klines_1d': klines_1d
                    })
                except Exception as e:
                    logger.warning(f"K라인 데이터 수집 부분 실패: {e}")
                
                # 펀딩비
                try:
                    funding = await self.bitget_client.get_funding_rate('BTCUSDT')
                    if funding:
                        market_data['funding_rate'] = float(funding.get('fundingRate', 0))
                        market_data['next_funding_time'] = funding.get('nextFundingTime', '')
                except Exception as e:
                    logger.warning(f"펀딩비 데이터 수집 실패: {e}")
                    market_data['funding_rate'] = 0
                
                # 미결제약정
                try:
                    oi = await self.bitget_client.get_open_interest('BTCUSDT')
                    if oi:
                        market_data['open_interest'] = float(oi.get('openInterest', 0))
                        market_data['oi_change_24h'] = float(oi.get('change24h', 0))
                except Exception as e:
                    logger.warning(f"미결제약정 데이터 수집 실패: {e}")
            
            # 변동성 계산
            if 'klines_1h' in market_data and market_data['klines_1h']:
                closes = [float(k[4]) for k in market_data['klines_1h'][-24:]]
                if len(closes) >= 2:
                    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
                    volatility = (sum(r*r for r in returns) / len(returns)) ** 0.5 * (24 ** 0.5) * 100
                    market_data['volatility'] = volatility
                else:
                    market_data['volatility'] = 2.0
            else:
                market_data['volatility'] = 2.0
            
            # 캐시 업데이트
            self.market_cache = market_data
            return market_data
            
        except Exception as e:
            logger.error(f"시장 데이터 수집 실패: {e}")
            return self.market_cache or {}

    async def _calculate_comprehensive_indicators(self) -> dict:
        """🔥 25개 이상 지표의 종합적 계산"""
        try:
            indicators = {
                'trend_indicators': {},
                'momentum_indicators': {},
                'volatility_indicators': {},
                'volume_indicators': {},
                'support_resistance': {},
                'composite_signals': {},
                'market_structure': {}
            }
            
            # 시장 데이터 확인
            if not self.market_cache or not self.market_cache.get('klines_1h'):
                logger.warning("시장 데이터 부족으로 기본 지표만 계산")
                return self._calculate_basic_indicators()
            
            klines_1h = self.market_cache.get('klines_1h', [])
            klines_4h = self.market_cache.get('klines_4h', [])
            klines_1d = self.market_cache.get('klines_1d', [])
            
            if not klines_1h:
                return self._calculate_basic_indicators()
            
            # 가격 데이터 추출
            closes_1h = [float(k[4]) for k in klines_1h[-200:]]
            highs_1h = [float(k[2]) for k in klines_1h[-200:]]
            lows_1h = [float(k[3]) for k in klines_1h[-200:]]
            volumes_1h = [float(k[5]) for k in klines_1h[-200:]]
            
            current_price = closes_1h[-1] if closes_1h else 0
            
            # 1. 추세 지표들 (7개)
            indicators['trend_indicators'] = {
                'sma_20': self._calculate_sma(closes_1h, 20),
                'sma_50': self._calculate_sma(closes_1h, 50),
                'sma_100': self._calculate_sma(closes_1h, 100),
                'ema_12': self._calculate_ema(closes_1h, 12),
                'ema_26': self._calculate_ema(closes_1h, 26),
                'ema_50': self._calculate_ema(closes_1h, 50),
                'adx': self._calculate_adx(highs_1h, lows_1h, closes_1h),
                'trend_strength': self._analyze_trend_strength(closes_1h),
                'ma_alignment': self._analyze_ma_alignment(closes_1h, current_price)
            }
            
            # 2. 모멘텀 지표들 (8개)
            indicators['momentum_indicators'] = {
                'rsi_14': self._calculate_rsi(closes_1h, 14),
                'rsi_7': self._calculate_rsi(closes_1h, 7),
                'macd': self._calculate_macd(closes_1h),
                'stoch_k': self._calculate_stochastic(highs_1h, lows_1h, closes_1h)[0],
                'stoch_d': self._calculate_stochastic(highs_1h, lows_1h, closes_1h)[1],
                'cci': self._calculate_cci(highs_1h, lows_1h, closes_1h),
                'williams_r': self._calculate_williams_r(highs_1h, lows_1h, closes_1h),
                'momentum': self._calculate_momentum(closes_1h),
                'roc': self._calculate_roc(closes_1h)
            }
            
            # 3. 변동성 지표들 (5개)
            indicators['volatility_indicators'] = {
                'bollinger_bands': self._calculate_bollinger_bands(closes_1h),
                'atr': self._calculate_atr(highs_1h, lows_1h, closes_1h),
                'keltner_channels': self._calculate_keltner_channels(highs_1h, lows_1h, closes_1h),
                'volatility_ratio': self._calculate_volatility_ratio(closes_1h),
                'price_channels': self._calculate_price_channels(highs_1h, lows_1h)
            }
            
            # 4. 거래량 지표들 (4개)
            indicators['volume_indicators'] = {
                'volume_sma': self._calculate_sma(volumes_1h, 20),
                'volume_ratio': volumes_1h[-1] / self._calculate_sma(volumes_1h, 20) if volumes_1h else 1,
                'obv': self._calculate_obv(closes_1h, volumes_1h),
                'mfi': self._calculate_mfi(highs_1h, lows_1h, closes_1h, volumes_1h)
            }
            
            # 5. 지지/저항 (4개)
            indicators['support_resistance'] = {
                'pivot_points': self._calculate_pivot_points(highs_1h, lows_1h, closes_1h),
                'fibonacci_levels': self._calculate_fibonacci_levels(highs_1h, lows_1h),
                'key_levels': self._identify_key_levels(highs_1h, lows_1h, closes_1h),
                'breakout_levels': self._calculate_breakout_levels(closes_1h)
            }
            
            # 6. 종합 신호 계산
            indicators['composite_signals'] = self._calculate_composite_signals(indicators)
            
            # 7. 시장 구조 분석
            indicators['market_structure'] = self._analyze_market_structure_detailed(klines_1h, klines_4h, klines_1d)
            
            # 캐시 업데이트
            self.indicators_cache = indicators
            return indicators
            
        except Exception as e:
            logger.error(f"지표 계산 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return self._calculate_basic_indicators()

    def _calculate_basic_indicators(self) -> dict:
        """기본 지표 계산 (폴백용)"""
        return {
            'trend_indicators': {
                'sma_20': 0, 'sma_50': 0, 'sma_100': 0,
                'ema_12': 0, 'ema_26': 0, 'ema_50': 0,
                'adx': 25, 'trend_strength': 'weak', 'ma_alignment': 'neutral'
            },
            'momentum_indicators': {
                'rsi_14': 50, 'rsi_7': 50, 'macd': {'macd': 0, 'signal': 0, 'histogram': 0},
                'stoch_k': 50, 'stoch_d': 50, 'cci': 0, 'williams_r': -50,
                'momentum': 0, 'roc': 0
            },
            'volatility_indicators': {
                'bollinger_bands': {'upper': 0, 'middle': 0, 'lower': 0},
                'atr': 0, 'keltner_channels': {'upper': 0, 'middle': 0, 'lower': 0},
                'volatility_ratio': 1, 'price_channels': {'upper': 0, 'lower': 0}
            },
            'volume_indicators': {
                'volume_sma': 0, 'volume_ratio': 1, 'obv': 0, 'mfi': 50
            },
            'support_resistance': {
                'pivot_points': {}, 'fibonacci_levels': {}, 'key_levels': {}, 'breakout_levels': {}
            },
            'composite_signals': {'total_score': 0, 'direction': 'neutral', 'strength': 'weak'},
            'market_structure': {'trend': 'sideways', 'phase': 'consolidation'}
        }

    async def _collect_real_time_market_events(self) -> list:
        """🔥 실시간 시장 이벤트 수집 - 강화"""
        try:
            events = []
            
            # 1. 데이터 컬렉터에서 최근 뉴스 가져오기
            if self.data_collector and hasattr(self.data_collector, 'get_recent_news'):
                try:
                    recent_news = await self.data_collector.get_recent_news(hours=6)
                    if recent_news:
                        events.extend(recent_news[:5])  # 최대 5개
                        logger.info(f"데이터 컬렉터에서 {len(recent_news)}개 뉴스 수집")
                except Exception as e:
                    logger.warning(f"데이터 컬렉터 뉴스 수집 실패: {e}")
            
            # 2. 직접 뉴스 API 호출 (보완)
            if len(events) < 3:
                try:
                    direct_news = await self._fetch_direct_news()
                    events.extend(direct_news)
                    logger.info(f"직접 뉴스 API에서 {len(direct_news)}개 추가 수집")
                except Exception as e:
                    logger.warning(f"직접 뉴스 수집 실패: {e}")
            
            # 3. 시장 데이터 기반 이벤트 생성
            market_events = await self._generate_market_data_events()
            events.extend(market_events)
            
            # 4. 이벤트가 없으면 기본 시장 분석 이벤트 생성
            if not events:
                events = await self._generate_default_market_events()
            
            # 최신순 정렬 및 제한
            events.sort(key=lambda x: x.get('published_at', ''), reverse=True)
            self.news_cache = events[:8]  # 최대 8개
            
            return self.news_cache
            
        except Exception as e:
            logger.error(f"실시간 이벤트 수집 실패: {e}")
            return self.news_cache or []

    async def _fetch_direct_news(self) -> list:
        """직접 뉴스 API 호출"""
        try:
            if not self.news_session:
                self.news_session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10)
                )
            
            # NewsAPI 호출 (간단한 버전)
            newsapi_key = os.getenv('NEWSAPI_KEY')
            if newsapi_key:
                url = "https://newsapi.org/v2/everything"
                params = {
                    'q': 'bitcoin OR "bitcoin ETF" OR "fed rate" OR "trump tariff" OR "china trade" OR "powell speech"',
                    'language': 'en',
                    'sortBy': 'publishedAt',
                    'apiKey': newsapi_key,
                    'pageSize': 20,
                    'from': (datetime.now() - timedelta(hours=6)).isoformat()
                }
                
                async with self.news_session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = data.get('articles', [])
                        
                        formatted_news = []
                        for article in articles[:10]:
                            if self._is_relevant_news(article):
                                formatted_news.append({
                                    'title': article.get('title', ''),
                                    'title_ko': article.get('title', ''),
                                    'description': article.get('description', '')[:500],
                                    'source': f"NewsAPI ({article.get('source', {}).get('name', 'Unknown')})",
                                    'published_at': article.get('publishedAt', ''),
                                    'url': article.get('url', ''),
                                    'impact': self._analyze_news_impact(article),
                                    'weight': 8,
                                    'category': 'direct_api'
                                })
                        
                        return formatted_news
            
            return []
            
        except Exception as e:
            logger.error(f"직접 뉴스 수집 실패: {e}")
            return []

    def _is_relevant_news(self, article: dict) -> bool:
        """뉴스 관련성 체크"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 비트코인 직접 관련
        bitcoin_keywords = ['bitcoin', 'btc', 'cryptocurrency', 'crypto']
        if any(keyword in content for keyword in bitcoin_keywords):
            return True
        
        # Fed 관련
        fed_keywords = ['federal reserve', 'fed rate', 'powell', 'fomc', 'interest rate']
        if any(keyword in content for keyword in fed_keywords):
            return True
        
        # 경제/무역 관련
        econ_keywords = ['trump tariff', 'china trade', 'inflation', 'cpi', 'unemployment']
        if any(keyword in content for keyword in econ_keywords):
            return True
        
        # 기업 관련
        company_keywords = ['tesla', 'microstrategy', 'blackrock', 'coinbase']
        if any(keyword in content for keyword in company_keywords):
            return True
        
        return False

    def _analyze_news_impact(self, article: dict) -> str:
        """뉴스 영향 분석"""
        content = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        # 강한 호재
        if any(word in content for word in ['etf approved', 'bitcoin surge', 'rate cut', 'trade deal']):
            return '🚀 강한 호재'
        
        # 호재
        elif any(word in content for word in ['bitcoin rise', 'positive', 'bullish', 'adoption']):
            return '📈 호재'
        
        # 강한 악재
        elif any(word in content for word in ['bitcoin crash', 'ban', 'rate hike', 'war']):
            return '🔻 강한 악재'
        
        # 악재
        elif any(word in content for word in ['bitcoin fall', 'negative', 'bearish', 'decline']):
            return '📉 악재'
        
        # 중립
        else:
            return '⚡ 변동성'

    async def _generate_market_data_events(self) -> list:
        """시장 데이터 기반 이벤트 생성"""
        try:
            events = []
            
            if not self.market_cache:
                return events
            
            current_price = self.market_cache.get('current_price', 0)
            change_24h = self.market_cache.get('change_24h', 0)
            volume_24h = self.market_cache.get('volume_24h', 0)
            funding_rate = self.market_cache.get('funding_rate', 0)
            volatility = self.market_cache.get('volatility', 0)
            
            # 가격 변동 이벤트
            if abs(change_24h) > 0.03:  # 3% 이상 변동
                direction = "급등" if change_24h > 0 else "급락"
                impact = "🚀 강한 호재" if change_24h > 0 else "🔻 강한 악재"
                events.append({
                    'title': f'비트코인 {direction} {abs(change_24h)*100:.1f}%',
                    'title_ko': f'비트코인 {direction} {abs(change_24h)*100:.1f}% (현재 ${current_price:,.0f})',
                    'description': f'비트코인이 24시간 동안 {abs(change_24h)*100:.1f}% {direction}하며 ${current_price:,.0f}에 거래되고 있습니다.',
                    'source': '시장 데이터',
                    'published_at': datetime.now().isoformat(),
                    'impact': impact,
                    'weight': 9,
                    'category': 'market_data'
                })
            
            # 거래량 이벤트
            avg_volume = 80000  # 평균 거래량
            if volume_24h > avg_volume * 1.5:
                events.append({
                    'title': f'비트코인 거래량 급증',
                    'title_ko': f'비트코인 거래량 급증 ({volume_24h:,.0f} BTC)',
                    'description': f'24시간 거래량이 {volume_24h:,.0f} BTC로 평균 대비 {volume_24h/avg_volume:.1f}배 증가했습니다.',
                    'source': '시장 데이터',
                    'published_at': datetime.now().isoformat(),
                    'impact': '⚡ 변동성 확대',
                    'weight': 7,
                    'category': 'market_data'
                })
            
            # 펀딩비 이벤트
            if abs(funding_rate) > 0.002:  # 0.2% 이상
                direction = "과열" if funding_rate > 0 else "과매도"
                impact = "⚠️ 조정 신호" if funding_rate > 0 else "📈 반등 신호"
                events.append({
                    'title': f'선물 펀딩비 {direction}',
                    'title_ko': f'선물 펀딩비 {direction} ({funding_rate*100:.3f}%)',
                    'description': f'8시간 펀딩비가 {funding_rate*100:.3f}%로 {direction} 상태입니다.',
                    'source': '시장 데이터',
                    'published_at': datetime.now().isoformat(),
                    'impact': impact,
                    'weight': 6,
                    'category': 'market_data'
                })
            
            # 변동성 이벤트
            if volatility > 5:
                events.append({
                    'title': f'고변동성 구간 진입',
                    'title_ko': f'고변동성 구간 진입 (변동성 {volatility:.1f}%)',
                    'description': f'24시간 변동성이 {volatility:.1f}%로 높은 수준을 기록하고 있습니다.',
                    'source': '시장 데이터',
                    'published_at': datetime.now().isoformat(),
                    'impact': '⚡ 변동성 확대',
                    'weight': 6,
                    'category': 'market_data'
                })
            
            return events
            
        except Exception as e:
            logger.error(f"시장 데이터 이벤트 생성 실패: {e}")
            return []

    async def _generate_default_market_events(self) -> list:
        """기본 시장 이벤트 생성 (뉴스가 없을 때)"""
        try:
            current_time = datetime.now()
            
            # 시장 상황에 따른 기본 이벤트
            events = [
                {
                    'title': '비트코인 시장 현황 분석',
                    'title_ko': '비트코인 시장 현황 분석',
                    'description': '현재 비트코인 시장의 기술적 지표와 거래량을 종합 분석한 결과입니다.',
                    'source': '시장 분석',
                    'published_at': current_time.isoformat(),
                    'impact': '📊 중립적 분석',
                    'weight': 5,
                    'category': 'market_analysis'
                },
                {
                    'title': '글로벌 거시경제 동향',
                    'title_ko': '글로벌 거시경제 동향 점검',
                    'description': 'Fed 통화정책, 인플레이션, 지정학적 리스크 등 주요 거시경제 요인들의 현재 상황입니다.',
                    'source': '경제 분석',
                    'published_at': current_time.isoformat(),
                    'impact': '📈 거시경제 영향',
                    'weight': 6,
                    'category': 'macro_analysis'
                }
            ]
            
            return events
            
        except Exception as e:
            logger.error(f"기본 이벤트 생성 실패: {e}")
            return []

    async def _format_critical_market_events(self, events: list) -> str:
        """🔥 크리티컬 시장 이벤트 포맷"""
        try:
            if not events:
                return "• 현재 주요 시장 이벤트가 포착되지 않았습니다\n• 안정적인 거래 환경이 유지되고 있습니다\n• 다음 주요 이벤트를 대기 중입니다"
            
            formatted_events = []
            kst = pytz.timezone('Asia/Seoul')
            
            for event in events[:5]:  # 최대 5개
                try:
                    # 시간 포맷
                    if event.get('published_at'):
                        pub_time_str = event['published_at']
                        try:
                            if 'T' in pub_time_str:
                                pub_time = datetime.fromisoformat(pub_time_str.replace('Z', ''))
                            else:
                                pub_time = datetime.now()
                            
                            if pub_time.tzinfo is None:
                                pub_time = pytz.UTC.localize(pub_time)
                            
                            pub_time_kst = pub_time.astimezone(kst)
                            time_str = pub_time_kst.strftime('%m-%d %H:%M')
                        except:
                            time_str = datetime.now(kst).strftime('%m-%d %H:%M')
                    else:
                        time_str = datetime.now(kst).strftime('%m-%d %H:%M')
                    
                    # 영향도 이모지
                    impact = event.get('impact', '📊 중립적 분석')
                    
                    # 가중치 표시
                    weight = event.get('weight', 5)
                    importance = "🔥" * min((weight // 2), 5)
                    
                    title = event.get('title_ko', event.get('title', ''))[:70]
                    source = event.get('source', '')
                    
                    formatted_events.append(
                        f"<b>{time_str}</b> {impact}\n  └ {title}\n  └ {source} {importance}"
                    )
                    
                except Exception as e:
                    logger.debug(f"이벤트 포맷 오류: {e}")
                    continue
            
            return '\n\n'.join(formatted_events)
            
        except Exception as e:
            logger.error(f"이벤트 포맷팅 실패: {e}")
            return "• 이벤트 데이터 처리 중입니다"

    async def _format_enhanced_market_status(self, market_data: dict) -> str:
        """🔥 강화된 시장 상황 포맷"""
        try:
            current_price = market_data.get('current_price', 0)
            change_24h = market_data.get('change_24h', 0)
            volume_24h = market_data.get('volume_24h', 0)
            high_24h = market_data.get('high_24h', 0)
            low_24h = market_data.get('low_24h', 0)
            volatility = market_data.get('volatility', 0)
            funding_rate = market_data.get('funding_rate', 0)
            open_interest = market_data.get('open_interest', 0)
            
            # 변동성 분석
            if volatility > 5:
                vol_status = "🔴 매우 높음 (위험)"
            elif volatility > 3:
                vol_status = "🟠 높음 (주의)"
            elif volatility > 1.5:
                vol_status = "🟡 보통 (정상)"
            else:
                vol_status = "🟢 낮음 (안정)"
            
            # 24시간 범위 내 위치
            if high_24h != low_24h:
                price_position = (current_price - low_24h) / (high_24h - low_24h)
                if price_position > 0.8:
                    position_text = "고점 근처 (저항 테스트)"
                elif price_position < 0.2:
                    position_text = "저점 근처 (지지 테스트)"
                else:
                    position_text = f"중간 구간 ({price_position*100:.0f}%)"
            else:
                position_text = "범위 분석 불가"
            
            # 거래량 분석
            avg_volume = 80000
            volume_ratio = volume_24h / avg_volume
            if volume_ratio > 1.5:
                volume_status = f"🔥 급증 ({volume_ratio:.1f}배)"
            elif volume_ratio > 1.2:
                volume_status = f"📈 증가 ({volume_ratio:.1f}배)"
            elif volume_ratio < 0.8:
                volume_status = f"📉 감소 ({volume_ratio:.1f}배)"
            else:
                volume_status = f"📊 정상 ({volume_ratio:.1f}배)"
            
            # 펀딩비 분석
            if funding_rate > 0.002:
                funding_status = f"🔥 과열 ({funding_rate*100:.3f}%)"
            elif funding_rate > 0.001:
                funding_status = f"📈 높음 ({funding_rate*100:.3f}%)"
            elif funding_rate < -0.001:
                funding_status = f"📉 저조 ({funding_rate*100:.3f}%)"
            else:
                funding_status = f"⚖️ 중립 ({funding_rate*100:.3f}%)"
            
            # 미결제약정 분석
            if open_interest > 0:
                oi_text = f"• 미결제약정: {open_interest:,.0f} USDT"
            else:
                oi_text = "• 미결제약정: 데이터 수집 중"
            
            # 가격 변동 이모지
            if change_24h > 0.03:
                change_emoji = "🚀"
            elif change_24h > 0:
                change_emoji = "📈"
            elif change_24h < -0.03:
                change_emoji = "🔻"
            elif change_24h < 0:
                change_emoji = "📉"
            else:
                change_emoji = "➖"
            
            return f"""• 현재가: <b>${current_price:,.0f}</b> {change_emoji} <b>({change_24h:+.2%})</b>
• 24H 범위: ${low_24h:,.0f} ~ ${high_24h:,.0f}
• 현재 위치: <b>{position_text}</b>
• 거래량: {volume_24h:,.0f} BTC ({volume_status})
• 변동성: <b>{volatility:.1f}%</b> ({vol_status})
• 펀딩비: {funding_status} (8시간)
{oi_text}"""
            
        except Exception as e:
            logger.error(f"시장 상황 포맷 실패: {e}")
            return "• 시장 데이터 분석 중..."

    async def _format_detailed_technical_analysis(self, indicators: dict, market_data: dict) -> str:
        """🔥 상세한 기술적 분석 포맷 (25개 지표)"""
        try:
            if not indicators:
                return "• 기술적 지표 분석 중..."
            
            current_price = market_data.get('current_price', 0)
            analysis_sections = []
            
            # 1. 추세 지표 분석
            trend = indicators.get('trend_indicators', {})
            trend_analysis = []
            
            # 이동평균 분석
            sma_20 = trend.get('sma_20', 0)
            sma_50 = trend.get('sma_50', 0)
            sma_100 = trend.get('sma_100', 0)
            
            if current_price and sma_20 and sma_50 and sma_100:
                if current_price > sma_20 > sma_50 > sma_100:
                    ma_signal = "🟢 완벽한 상승 배열"
                elif current_price < sma_20 < sma_50 < sma_100:
                    ma_signal = "🔴 완벽한 하락 배열"
                elif current_price > sma_20 > sma_50:
                    ma_signal = "🟡 단기 상승 추세"
                elif current_price < sma_20 < sma_50:
                    ma_signal = "🟠 단기 하락 추세"
                else:
                    ma_signal = "⚪ 혼조세"
                trend_analysis.append(f"이동평균: {ma_signal}")
            
            # ADX 분석
            adx = trend.get('adx', 25)
            if adx > 40:
                adx_signal = f"🔥 매우 강한 추세 ({adx:.0f})"
            elif adx > 25:
                adx_signal = f"📈 강한 추세 ({adx:.0f})"
            else:
                adx_signal = f"📊 약한 추세 ({adx:.0f})"
            trend_analysis.append(f"ADX: {adx_signal}")
            
            if trend_analysis:
                analysis_sections.append(f"<b>📈 추세 분석</b>\n" + "\n".join(f"  • {item}" for item in trend_analysis))
            
            # 2. 모멘텀 지표 분석
            momentum = indicators.get('momentum_indicators', {})
            momentum_analysis = []
            
            # RSI 분석
            rsi_14 = momentum.get('rsi_14', 50)
            if rsi_14 > 80:
                rsi_signal = f"🔴 극도 과매수 ({rsi_14:.0f})"
            elif rsi_14 > 70:
                rsi_signal = f"🟠 과매수 ({rsi_14:.0f})"
            elif rsi_14 < 20:
                rsi_signal = f"🟢 극도 과매도 ({rsi_14:.0f})"
            elif rsi_14 < 30:
                rsi_signal = f"🟡 과매도 ({rsi_14:.0f})"
            else:
                rsi_signal = f"⚪ 중립 ({rsi_14:.0f})"
            momentum_analysis.append(f"RSI(14): {rsi_signal}")
            
            # MACD 분석
            macd_data = momentum.get('macd', {})
            if isinstance(macd_data, dict):
                macd_hist = macd_data.get('histogram', 0)
                if macd_hist > 100:
                    macd_signal = "🟢 강한 상승 신호"
                elif macd_hist > 0:
                    macd_signal = "🟡 상승 신호"
                elif macd_hist < -100:
                    macd_signal = "🔴 강한 하락 신호"
                elif macd_hist < 0:
                    macd_signal = "🟠 하락 신호"
                else:
                    macd_signal = "⚪ 중립"
                momentum_analysis.append(f"MACD: {macd_signal}")
            
            # 스토캐스틱 분석
            stoch_k = momentum.get('stoch_k', 50)
            if stoch_k > 80:
                stoch_signal = f"🔴 과매수 ({stoch_k:.0f})"
            elif stoch_k < 20:
                stoch_signal = f"🟢 과매도 ({stoch_k:.0f})"
            else:
                stoch_signal = f"⚪ 중립 ({stoch_k:.0f})"
            momentum_analysis.append(f"Stochastic: {stoch_signal}")
            
            if momentum_analysis:
                analysis_sections.append(f"<b>⚡ 모멘텀 분석</b>\n" + "\n".join(f"  • {item}" for item in momentum_analysis))
            
            # 3. 변동성 및 지지저항 분석
            volatility = indicators.get('volatility_indicators', {})
            support_resistance = indicators.get('support_resistance', {})
            sr_analysis = []
            
            # 볼린저 밴드 분석
            bb = volatility.get('bollinger_bands', {})
            if isinstance(bb, dict) and current_price:
                bb_upper = bb.get('upper', 0)
                bb_lower = bb.get('lower', 0)
                bb_middle = bb.get('middle', 0)
                
                if bb_upper and bb_lower:
                    bb_position = (current_price - bb_lower) / (bb_upper - bb_lower)
                    if bb_position > 0.9:
                        bb_signal = f"🔴 상단 돌파 (${bb_upper:,.0f})"
                    elif bb_position < 0.1:
                        bb_signal = f"🟢 하단 터치 (${bb_lower:,.0f})"
                    else:
                        bb_signal = f"⚪ 중간대 (${bb_middle:,.0f})"
                    sr_analysis.append(f"볼린저밴드: {bb_signal}")
            
            # ATR 분석
            atr = volatility.get('atr', 0)
            if atr > 0:
                atr_pct = (atr / current_price) * 100 if current_price else 0
                if atr_pct > 3:
                    atr_signal = f"🔥 고변동성 ({atr_pct:.1f}%)"
                elif atr_pct > 2:
                    atr_signal = f"📈 중변동성 ({atr_pct:.1f}%)"
                else:
                    atr_signal = f"📊 저변동성 ({atr_pct:.1f}%)"
                sr_analysis.append(f"ATR: {atr_signal}")
            
            if sr_analysis:
                analysis_sections.append(f"<b>🎯 지지저항</b>\n" + "\n".join(f"  • {item}" for item in sr_analysis))
            
            # 4. 거래량 분석
            volume_indicators = indicators.get('volume_indicators', {})
            volume_analysis = []
            
            volume_ratio = volume_indicators.get('volume_ratio', 1)
            if volume_ratio > 1.5:
                vol_signal = f"🔥 거래량 급증 ({volume_ratio:.1f}배)"
            elif volume_ratio > 1.2:
                vol_signal = f"📈 거래량 증가 ({volume_ratio:.1f}배)"
            elif volume_ratio < 0.8:
                vol_signal = f"📉 거래량 감소 ({volume_ratio:.1f}배)"
            else:
                vol_signal = f"📊 정상 거래량 ({volume_ratio:.1f}배)"
            volume_analysis.append(f"거래량: {vol_signal}")
            
            # MFI 분석
            mfi = volume_indicators.get('mfi', 50)
            if mfi > 80:
                mfi_signal = f"🔴 자금 과매수 ({mfi:.0f})"
            elif mfi < 20:
                mfi_signal = f"🟢 자금 과매도 ({mfi:.0f})"
            else:
                mfi_signal = f"⚪ 자금 중립 ({mfi:.0f})"
            volume_analysis.append(f"MFI: {mfi_signal}")
            
            if volume_analysis:
                analysis_sections.append(f"<b>📊 거래량 분석</b>\n" + "\n".join(f"  • {item}" for item in volume_analysis))
            
            # 5. 종합 점수
            composite = indicators.get('composite_signals', {})
            total_score = composite.get('total_score', 0)
            direction = composite.get('direction', 'neutral')
            strength = composite.get('strength', 'weak')
            
            if total_score > 5:
                score_color = "🟢"
                score_text = f"강한 상승 ({total_score:.1f}점)"
            elif total_score > 2:
                score_color = "🟡"
                score_text = f"약한 상승 ({total_score:.1f}점)"
            elif total_score < -5:
                score_color = "🔴"
                score_text = f"강한 하락 ({total_score:.1f}점)"
            elif total_score < -2:
                score_color = "🟠"
                score_text = f"약한 하락 ({total_score:.1f}점)"
            else:
                score_color = "⚪"
                score_text = f"중립 ({total_score:.1f}점)"
            
            analysis_sections.append(f"<b>🏆 종합 점수</b>\n  • 25개 지표 종합: {score_color} <b>{score_text}</b>\n  • 신호 강도: {strength.upper()}")
            
            return '\n\n'.join(analysis_sections)
            
        except Exception as e:
            logger.error(f"기술적 분석 포맷 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return "• 기술적 지표 분석 중..."

    async def _format_precision_trading_signals(self, indicators: dict, market_data: dict) -> str:
        """🔥 정밀 매매 신호 포맷"""
        try:
            if not indicators:
                return "• 매매 신호 분석 중..."
            
            # 종합 신호 계산
            composite = indicators.get('composite_signals', {})
            total_score = composite.get('total_score', 0)
            direction = composite.get('direction', 'neutral')
            confidence = self._calculate_signal_confidence(indicators)
            
            # 신호 강도 (10단계)
            strength = min(max(int(abs(total_score)), 1), 10)
            strength_bar = "●" * strength + "○" * (10 - strength)
            
            # 방향성 및 행동 권장
            if total_score >= 6:
                signal_direction = "🚀 매우 강한 상승"
                action = "적극 매수 (롱)"
                color = "🟢"
            elif total_score >= 3:
                signal_direction = "📈 강한 상승"
                action = "매수 (롱)"
                color = "🟢"
            elif total_score >= 1:
                signal_direction = "🟡 약한 상승"
                action = "신중한 매수"
                color = "🟡"
            elif total_score <= -6:
                signal_direction = "🔻 매우 강한 하락"
                action = "적극 매도 (숏)"
                color = "🔴"
            elif total_score <= -3:
                signal_direction = "📉 강한 하락"
                action = "매도 (숏)"
                color = "🔴"
            elif total_score <= -1:
                signal_direction = "🟠 약한 하락"
                action = "신중한 매도"
                color = "🟠"
            else:
                signal_direction = "➖ 중립"
                action = "관망"
                color = "⚪"
            
            # 핵심 근거 수집
            reasons = self._extract_key_reasons(indicators, market_data)
            reasons_text = '\n'.join(f"  • {reason}" for reason in reasons[:5])
            
            # 리스크 요인
            risk_factors = self._identify_risk_factors(indicators, market_data)
            risk_text = ""
            if risk_factors:
                risk_text = f"\n\n<b>⚠️ 주의사항:</b>\n" + '\n'.join(f"  • {risk}" for risk in risk_factors[:3])
            
            return f"""【강도】 {strength_bar} ({strength}/10)
【방향】 {signal_direction}
【신뢰도】 <b>{confidence:.0f}%</b>
【권장】 {color} <b>{action}</b>

<b>핵심 근거:</b>
{reasons_text}{risk_text}"""
            
        except Exception as e:
            logger.error(f"매매 신호 포맷 실패: {e}")
            return "• 매매 신호 분석 중..."

    def _calculate_signal_confidence(self, indicators: dict) -> float:
        """신호 신뢰도 계산"""
        try:
            confidence_factors = []
            
            # 추세 일치도
            trend = indicators.get('trend_indicators', {})
            ma_alignment = trend.get('ma_alignment', 'neutral')
            if ma_alignment == 'strong_bullish' or ma_alignment == 'strong_bearish':
                confidence_factors.append(20)
            elif ma_alignment != 'neutral':
                confidence_factors.append(10)
            
            # ADX 강도
            adx = trend.get('adx', 25)
            if adx > 40:
                confidence_factors.append(20)
            elif adx > 25:
                confidence_factors.append(10)
            
            # 모멘텀 일치도
            momentum = indicators.get('momentum_indicators', {})
            rsi = momentum.get('rsi_14', 50)
            if rsi > 70 or rsi < 30:
                confidence_factors.append(15)
            
            # 거래량 지원
            volume = indicators.get('volume_indicators', {})
            volume_ratio = volume.get('volume_ratio', 1)
            if volume_ratio > 1.3:
                confidence_factors.append(15)
            
            # 종합 점수 일관성
            composite = indicators.get('composite_signals', {})
            total_score = abs(composite.get('total_score', 0))
            if total_score > 5:
                confidence_factors.append(20)
            elif total_score > 2:
                confidence_factors.append(10)
            
            # 신뢰도 계산
            total_confidence = sum(confidence_factors)
            max_possible = 90
            confidence = (total_confidence / max_possible) * 100
            
            return min(max(confidence, 30), 95)  # 30-95% 범위
            
        except Exception as e:
            logger.error(f"신뢰도 계산 실패: {e}")
            return 50

    def _extract_key_reasons(self, indicators: dict, market_data: dict) -> list:
        """핵심 근거 추출"""
        reasons = []
        
        try:
            # 추세 근거
            trend = indicators.get('trend_indicators', {})
            current_price = market_data.get('current_price', 0)
            sma_20 = trend.get('sma_20', 0)
            sma_50 = trend.get('sma_50', 0)
            
            if current_price and sma_20 and sma_50:
                if current_price > sma_20 > sma_50:
                    reasons.append("이동평균선 상승 배열")
                elif current_price < sma_20 < sma_50:
                    reasons.append("이동평균선 하락 배열")
            
            # 모멘텀 근거
            momentum = indicators.get('momentum_indicators', {})
            rsi = momentum.get('rsi_14', 50)
            if rsi > 75:
                reasons.append(f"RSI 극도과매수 ({rsi:.0f})")
            elif rsi < 25:
                reasons.append(f"RSI 극도과매도 ({rsi:.0f})")
            elif rsi > 65:
                reasons.append(f"RSI 과매수권 ({rsi:.0f})")
            elif rsi < 35:
                reasons.append(f"RSI 과매도권 ({rsi:.0f})")
            
            # MACD 근거
            macd_data = momentum.get('macd', {})
            if isinstance(macd_data, dict):
                macd_hist = macd_data.get('histogram', 0)
                if abs(macd_hist) > 50:
                    direction = "상승" if macd_hist > 0 else "하락"
                    reasons.append(f"MACD 강한 {direction} 신호")
            
            # 거래량 근거
            volume = indicators.get('volume_indicators', {})
            volume_ratio = volume.get('volume_ratio', 1)
            if volume_ratio > 1.5:
                reasons.append(f"거래량 급증 ({volume_ratio:.1f}배)")
            elif volume_ratio < 0.7:
                reasons.append(f"거래량 급감 ({volume_ratio:.1f}배)")
            
            # 변동성 근거
            volatility_val = market_data.get('volatility', 0)
            if volatility_val > 5:
                reasons.append(f"고변동성 ({volatility_val:.1f}%)")
            elif volatility_val < 1:
                reasons.append(f"저변동성 ({volatility_val:.1f}%)")
            
            # 펀딩비 근거
            funding_rate = market_data.get('funding_rate', 0)
            if abs(funding_rate) > 0.002:
                if funding_rate > 0:
                    reasons.append(f"펀딩비 과열 ({funding_rate*100:.3f}%)")
                else:
                    reasons.append(f"펀딩비 저조 ({funding_rate*100:.3f}%)")
            
            return reasons[:5]  # 최대 5개
            
        except Exception as e:
            logger.error(f"근거 추출 실패: {e}")
            return ["기술적 지표 종합 분석"]

    def _identify_risk_factors(self, indicators: dict, market_data: dict) -> list:
        """리스크 요인 식별"""
        risks = []
        
        try:
            # 과매수/과매도 위험
            momentum = indicators.get('momentum_indicators', {})
            rsi = momentum.get('rsi_14', 50)
            
            composite = indicators.get('composite_signals', {})
            total_score = composite.get('total_score', 0)
            
            if total_score > 5 and rsi > 70:
                risks.append("과매수 구간에서 추가 상승 제한적")
            elif total_score < -5 and rsi < 30:
                risks.append("과매도 구간에서 추가 하락 제한적")
            
            # 변동성 위험
            volatility = market_data.get('volatility', 0)
            if volatility > 5:
                risks.append("높은 변동성으로 급격한 반전 가능")
            
            # 거래량 위험
            volume = indicators.get('volume_indicators', {})
            volume_ratio = volume.get('volume_ratio', 1)
            if volume_ratio < 0.7:
                risks.append("저조한 거래량으로 신호 신뢰도 낮음")
            
            # 펀딩비 위험
            funding_rate = market_data.get('funding_rate', 0)
            if abs(funding_rate) > 0.003:
                if funding_rate > 0:
                    risks.append("높은 펀딩비로 롱 포지션 비용 증가")
                else:
                    risks.append("낮은 펀딩비로 숏 포지션 비용 증가")
            
            return risks[:3]  # 최대 3개
            
        except Exception as e:
            logger.error(f"리스크 식별 실패: {e}")
            return []

    async def _format_actionable_trading_strategy(self, indicators: dict, market_data: dict) -> str:
        """🔥 실행 가능한 매매 전략 포맷"""
        try:
            composite = indicators.get('composite_signals', {})
            total_score = composite.get('total_score', 0)
            current_price = market_data.get('current_price', 0)
            
            # ATR 기반 리스크 계산
            volatility_indicators = indicators.get('volatility_indicators', {})
            atr = volatility_indicators.get('atr', current_price * 0.015)
            if atr == 0:
                atr = current_price * 0.015
            
            # 전략 결정
            if total_score >= 6:
                return self._format_aggressive_long_strategy(current_price, atr, total_score)
            elif total_score >= 3:
                return self._format_moderate_long_strategy(current_price, atr, total_score)
            elif total_score >= 1:
                return self._format_conservative_long_strategy(current_price, atr, total_score)
            elif total_score <= -6:
                return self._format_aggressive_short_strategy(current_price, atr, total_score)
            elif total_score <= -3:
                return self._format_moderate_short_strategy(current_price, atr, total_score)
            elif total_score <= -1:
                return self._format_conservative_short_strategy(current_price, atr, total_score)
            else:
                return self._format_neutral_strategy(current_price, atr, indicators, market_data)
            
        except Exception as e:
            logger.error(f"매매 전략 포맷 실패: {e}")
            return "• 전략 분석 중..."

    def _format_aggressive_long_strategy(self, current_price: float, atr: float, score: float) -> str:
        """적극적 롱 전략"""
        entry_price = current_price
        stop_loss = current_price - (atr * 1.5)
        target1 = current_price + (atr * 2.5)
        target2 = current_price + (atr * 4.0)
        target3 = current_price + (atr * 6.0)
        
        risk_pct = ((entry_price - stop_loss) / entry_price) * 100
        reward_risk_1 = (target1 - entry_price) / (entry_price - stop_loss)
        
        return f"""• 전략: 🚀 <b>적극적 롱 진입</b>
- 진입: <b>즉시 ${entry_price:,.0f}</b>
- 손절: ${stop_loss:,.0f} ({risk_pct:.1f}% 리스크)
- 목표1: ${target1:,.0f} (R/R {reward_risk_1:.1f}:1)
- 목표2: ${target2:,.0f}
- 목표3: ${target3:,.0f}
- 포지션: <b>표준 크기 (2-3%)</b>
- 추천: 분할 매수로 리스크 분산"""

    def _format_moderate_long_strategy(self, current_price: float, atr: float, score: float) -> str:
        """보통 롱 전략"""
        entry_price = current_price - (atr * 0.3)
        stop_loss = current_price - (atr * 1.2)
        target1 = current_price + (atr * 1.8)
        target2 = current_price + (atr * 3.0)
        
        risk_pct = ((entry_price - stop_loss) / entry_price) * 100
        reward_risk_1 = (target1 - entry_price) / (entry_price - stop_loss)
        
        return f"""• 전략: 📈 <b>롱 진입</b>
- 진입: ${entry_price:,.0f} (지정가 대기)
- 손절: ${stop_loss:,.0f} ({risk_pct:.1f}% 리스크)
- 목표1: ${target1:,.0f} (R/R {reward_risk_1:.1f}:1)
- 목표2: ${target2:,.0f}
- 포지션: <b>표준 크기 (1-2%)</b>
- 추천: 지지선 확인 후 진입"""

    def _format_conservative_long_strategy(self, current_price: float, atr: float, score: float) -> str:
        """보수적 롱 전략"""
        entry_price = current_price - (atr * 0.5)
        stop_loss = current_price - (atr * 1.0)
        target1 = current_price + (atr * 1.2)
        target2 = current_price + (atr * 2.0)
        
        risk_pct = ((entry_price - stop_loss) / entry_price) * 100
        
        return f"""• 전략: 🟡 <b>신중한 롱</b>
- 진입: ${entry_price:,.0f} (확인 후)
- 손절: ${stop_loss:,.0f} ({risk_pct:.1f}% 리스크)
- 목표1: ${target1:,.0f}
- 목표2: ${target2:,.0f}
- 포지션: <b>작은 크기 (0.5-1%)</b>
- 추천: 추가 확인 신호 대기"""

    def _format_aggressive_short_strategy(self, current_price: float, atr: float, score: float) -> str:
        """적극적 숏 전략"""
        entry_price = current_price
        stop_loss = current_price + (atr * 1.5)
        target1 = current_price - (atr * 2.5)
        target2 = current_price - (atr * 4.0)
        target3 = current_price - (atr * 6.0)
        
        risk_pct = ((stop_loss - entry_price) / entry_price) * 100
        reward_risk_1 = (entry_price - target1) / (stop_loss - entry_price)
        
        return f"""• 전략: 🔻 <b>적극적 숏 진입</b>
- 진입: <b>즉시 ${entry_price:,.0f}</b>
- 손절: ${stop_loss:,.0f} ({risk_pct:.1f}% 리스크)
- 목표1: ${target1:,.0f} (R/R {reward_risk_1:.1f}:1)
- 목표2: ${target2:,.0f}
- 목표3: ${target3:,.0f}
- 포지션: <b>표준 크기 (2-3%)</b>
- 추천: 분할 매도로 리스크 분산"""

    def _format_moderate_short_strategy(self, current_price: float, atr: float, score: float) -> str:
        """보통 숏 전략"""
        entry_price = current_price + (atr * 0.3)
        stop_loss = current_price + (atr * 1.2)
        target1 = current_price - (atr * 1.8)
        target2 = current_price - (atr * 3.0)
        
        risk_pct = ((stop_loss - entry_price) / entry_price) * 100
        reward_risk_1 = (entry_price - target1) / (stop_loss - entry_price)
        
        return f"""• 전략: 📉 <b>숏 진입</b>
- 진입: ${entry_price:,.0f} (지정가 대기)
- 손절: ${stop_loss:,.0f} ({risk_pct:.1f}% 리스크)
- 목표1: ${target1:,.0f} (R/R {reward_risk_1:.1f}:1)
- 목표2: ${target2:,.0f}
- 포지션: <b>표준 크기 (1-2%)</b>
- 추천: 저항선 확인 후 진입"""

    def _format_conservative_short_strategy(self, current_price: float, atr: float, score: float) -> str:
        """보수적 숏 전략"""
        entry_price = current_price + (atr * 0.5)
        stop_loss = current_price + (atr * 1.0)
        target1 = current_price - (atr * 1.2)
        target2 = current_price - (atr * 2.0)
        
        risk_pct = ((stop_loss - entry_price) / entry_price) * 100
        
        return f"""• 전략: 🟠 <b>신중한 숏</b>
- 진입: ${entry_price:,.0f} (확인 후)
- 손절: ${stop_loss:,.0f} ({risk_pct:.1f}% 리스크)
- 목표1: ${target1:,.0f}
- 목표2: ${target2:,.0f}
- 포지션: <b>작은 크기 (0.5-1%)</b>
- 추천: 추가 하락 신호 대기"""

    def _format_neutral_strategy(self, current_price: float, atr: float, indicators: dict, market_data: dict) -> str:
        """중립 전략"""
        support = current_price - (atr * 1.0)
        resistance = current_price + (atr * 1.0)
        
        # 좀 더 정확한 지지/저항 찾기
        sr_data = indicators.get('support_resistance', {})
        key_levels = sr_data.get('key_levels', {})
        
        if key_levels:
            support = key_levels.get('support', support)
            resistance = key_levels.get('resistance', resistance)
        
        return f"""• 전략: ⚪ <b>관망 및 레벨 대기</b>
- 현재가: ${current_price:,.0f}
- 상방 돌파: <b>${resistance:,.0f} 이상</b> → 롱 진입 고려
- 하방 이탈: <b>${support:,.0f} 이하</b> → 숏 진입 고려
- 구간: ${support:,.0f} ~ ${resistance:,.0f}
- 권장: <b>명확한 돌파 신호 대기</b>
- 포지션: 현재 관망 권장"""

    async def _format_intelligent_price_prediction(self, indicators: dict, market_data: dict) -> str:
        """🔥 지능적 가격 예측 (극단적이고 정확하게)"""
        try:
            # 기본 확률 (더 극단적으로 시작)
            up_prob = 20
            sideways_prob = 60  
            down_prob = 20
            
            current_price = market_data.get('current_price', 0)
            
            # 1. 종합 점수 기반 대폭 조정 (가중치 2배 증가)
            composite = indicators.get('composite_signals', {})
            total_score = composite.get('total_score', 0)
            
            if total_score > 0:
                score_bonus = min(total_score * 15, 60)  # 기존 8 → 15로 증가
                up_prob += score_bonus
                down_prob -= score_bonus * 0.8
                sideways_prob -= score_bonus * 0.2
            elif total_score < 0:
                score_bonus = min(abs(total_score) * 15, 60)
                down_prob += score_bonus
                up_prob -= score_bonus * 0.8
                sideways_prob -= score_bonus * 0.2
            
            # 2. RSI 극단값 강화 조정
            momentum = indicators.get('momentum_indicators', {})
            rsi = momentum.get('rsi_14', 50)
            
            if rsi > 85:  # 극도 과매수
                down_prob += 25
                up_prob -= 20
                sideways_prob -= 5
            elif rsi > 75:
                down_prob += 15
                up_prob -= 12
                sideways_prob -= 3
            elif rsi < 15:  # 극도 과매도
                up_prob += 25
                down_prob -= 20
                sideways_prob -= 5
            elif rsi < 25:
                up_prob += 15
                down_prob -= 12
                sideways_prob -= 3
            
            # 3. MACD 히스토그램 강화
            macd_data = momentum.get('macd', {})
            if isinstance(macd_data, dict):
                macd_hist = macd_data.get('histogram', 0)
                if macd_hist > 200:  # 매우 강한 상승
                    up_prob += 20
                    down_prob -= 20
                elif macd_hist > 0:
                    up_prob += max(int(macd_hist / 20), 5)
                    down_prob -= max(int(macd_hist / 20), 5)
                elif macd_hist < -200:  # 매우 강한 하락
                    down_prob += 20
                    up_prob -= 20
                elif macd_hist < 0:
                    down_prob += max(int(abs(macd_hist) / 20), 5)
                    up_prob -= max(int(abs(macd_hist) / 20), 5)
            
            # 4. 이동평균 배열 강화
            trend = indicators.get('trend_indicators', {})
            sma_20 = trend.get('sma_20', 0)
            sma_50 = trend.get('sma_50', 0)
            sma_100 = trend.get('sma_100', 0)
            
            if current_price and sma_20 and sma_50 and sma_100:
                if current_price > sma_20 > sma_50 > sma_100:
                    # 완벽한 상승 배열
                    up_prob += 25
                    down_prob -= 25
                elif current_price < sma_20 < sma_50 < sma_100:
                    # 완벽한 하락 배열
                    down_prob += 25
                    up_prob -= 25
                elif current_price > sma_20 > sma_50:
                    up_prob += 15
                    down_prob -= 15
                elif current_price < sma_20 < sma_50:
                    down_prob += 15
                    up_prob -= 15
            
            # 5. 거래량 강화
            volume = indicators.get('volume_indicators', {})
            volume_ratio = volume.get('volume_ratio', 1)
            
            if volume_ratio > 2.0:  # 거래량 2배 이상
                # 방향성에 따라 강화
                if total_score > 0:
                    up_prob += 15
                    sideways_prob -= 15
                elif total_score < 0:
                    down_prob += 15
                    sideways_prob -= 15
            elif volume_ratio < 0.5:  # 거래량 급감
                sideways_prob += 20
                up_prob -= 10
                down_prob -= 10
            
            # 6. 변동성 조정 강화
            volatility = market_data.get('volatility', 2)
            if volatility > 6:  # 매우 높은 변동성
                sideways_prob -= 20
                up_prob += 10
                down_prob += 10
            elif volatility < 1:  # 매우 낮은 변동성
                sideways_prob += 20
                up_prob -= 10
                down_prob -= 10
            
            # 7. 펀딩비 극단 조정
            funding_rate = market_data.get('funding_rate', 0)
            if funding_rate > 0.004:  # 극도 과열
                down_prob += 20
                up_prob -= 20
            elif funding_rate < -0.002:  # 극도 저조
                up_prob += 15
                down_prob -= 15
            
            # 8. ADX 추세 강도
            adx = trend.get('adx', 25)
            if adx > 50:  # 매우 강한 추세
                sideways_prob -= 15
                if total_score > 0:
                    up_prob += 15
                elif total_score < 0:
                    down_prob += 15
            elif adx < 15:  # 매우 약한 추세
                sideways_prob += 15
                up_prob -= 7
                down_prob -= 8
            
            # 정규화 및 최소값 보장
            up_prob = max(5, up_prob)
            down_prob = max(5, down_prob)
            sideways_prob = max(10, sideways_prob)
            
            total = up_prob + sideways_prob + down_prob
            up_prob = int(up_prob / total * 100)
            down_prob = int(down_prob / total * 100)
            sideways_prob = 100 - up_prob - down_prob
            
            # 예상 가격 범위 계산 (더 정교하게)
            volatility_indicators = indicators.get('volatility_indicators', {})
            atr = volatility_indicators.get('atr', current_price * 0.015)
            expected_move_12h = atr * 1.5  # 12시간 예상 변동
            
            # 방향성에 따른 범위 계산 (더 극단적으로)
            if up_prob > down_prob + 30:  # 상승 확률이 30% 이상 높음
                min_price = current_price - expected_move_12h * 0.3
                max_price = current_price + expected_move_12h * 2.5
                center_price = current_price + expected_move_12h * 1.5
                trend = "강한 상승 돌파"
                emoji = "🚀"
            elif up_prob > down_prob + 15:
                min_price = current_price - expected_move_12h * 0.5
                max_price = current_price + expected_move_12h * 1.8
                center_price = current_price + expected_move_12h * 1.0
                trend = "상승 추세"
                emoji = "📈"
            elif down_prob > up_prob + 30:  # 하락 확률이 30% 이상 높음
                min_price = current_price - expected_move_12h * 2.5
                max_price = current_price + expected_move_12h * 0.3
                center_price = current_price - expected_move_12h * 1.5
                trend = "강한 하락 돌파"
                emoji = "🔻"
            elif down_prob > up_prob + 15:
                min_price = current_price - expected_move_12h * 1.8
                max_price = current_price + expected_move_12h * 0.5
                center_price = current_price - expected_move_12h * 1.0
                trend = "하락 추세"
                emoji = "📉"
            else:
                min_price = current_price - expected_move_12h * 0.8
                max_price = current_price + expected_move_12h * 0.8
                center_price = current_price
                trend = "박스권 횡보"
                emoji = "➡️"
            
            # 핵심 판단 근거
            reasons = []
            
            if abs(total_score) > 6:
                direction = "매우 강한 상승" if total_score > 0 else "매우 강한 하락"
                reasons.append(f"• 25개 지표 종합: {direction} 신호")
            
            # RSI 근거
            if rsi > 80 or rsi < 20:
                reasons.append(f"• RSI 극단값: {rsi:.0f} (강한 반전 압력)")
            
            # 이동평균 근거
            if current_price and sma_20 and sma_50 and sma_100:
                if current_price > sma_20 > sma_50 > sma_100:
                    reasons.append("• 완벽한 상승 이평선 정렬")
                elif current_price < sma_20 < sma_50 < sma_100:
                    reasons.append("• 완벽한 하락 이평선 정렬")
            
            # 거래량 근거
            if volume_ratio > 1.8:
                reasons.append(f"• 거래량 급증: {volume_ratio:.1f}배 (강한 동력)")
            elif volume_ratio < 0.6:
                reasons.append(f"• 거래량 위축: {volume_ratio:.1f}배 (약한 신호)")
            
            # 변동성 근거
            if volatility > 5:
                reasons.append(f"• 고변동성: {volatility:.1f}% (급격한 변화 가능)")
            elif volatility < 1.5:
                reasons.append(f"• 저변동성: {volatility:.1f}% (돌파 임박)")
            
            reasons_text = '\n'.join(reasons[:4])  # 최대 4개
            
            # 확률 표시 (가장 높은 것 강조)
            prob_display = []
            
            if up_prob >= 50:
                prob_display.append(f"▲ 상승 <b>{up_prob}%</b> 🎯")
            elif up_prob >= 40:
                prob_display.append(f"▲ 상승 <b>{up_prob}%</b>")
            else:
                prob_display.append(f"▲ 상승 {up_prob}%")
            
            if sideways_prob >= 50:
                prob_display.append(f"━ 횡보 <b>{sideways_prob}%</b> 🎯")
            elif sideways_prob >= 40:
                prob_display.append(f"━ 횡보 <b>{sideways_prob}%</b>")
            else:
                prob_display.append(f"━ 횡보 {sideways_prob}%")
            
            if down_prob >= 50:
                prob_display.append(f"▼ 하락 <b>{down_prob}%</b> 🎯")
            elif down_prob >= 40:
                prob_display.append(f"▼ 하락 <b>{down_prob}%</b>")
            else:
                prob_display.append(f"▼ 하락 {down_prob}%")
            
            # 신뢰도 계산
            max_prob = max(up_prob, down_prob, sideways_prob)
            if max_prob >= 60:
                confidence_text = f"높음 ({max_prob}%)"
            elif max_prob >= 45:
                confidence_text = f"보통 ({max_prob}%)"
            else:
                confidence_text = f"낮음 ({max_prob}%)"
            
            return f"""{' | '.join(prob_display)}

→ 예상 범위: <b>${min_price:,.0f} ~ ${max_price:,.0f}</b>
→ 중심 예상가: <b>${center_price:,.0f}</b>
→ 예상 추세: {emoji} <b>{trend}</b>
→ 신뢰도: {confidence_text}

<b>핵심 판단 근거:</b>
{reasons_text}"""
            
        except Exception as e:
            logger.error(f"AI 예측 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return "• AI 예측 분석 중..."

    async def _comprehensive_prediction_validation(self, market_data: dict) -> str:
        """🔥 종합적인 예측 검증"""
        try:
            if not self.prediction_history:
                return "• 검증할 이전 예측이 없습니다\n• 첫 번째 예측을 생성하고 있습니다\n• 다음 검증: 12시간 후"
            
            current_time = datetime.now()
            current_price = market_data.get('current_price', 0)
            
            # 최근 예측들 검증
            recent_validations = []
            total_predictions = 0
            correct_predictions = 0
            
            for pred in reversed(self.prediction_history[-10:]):  # 최근 10개
                try:
                    pred_time = datetime.fromisoformat(pred['timestamp'])
                    time_diff = current_time - pred_time
                    
                    # 12시간 이상 지난 예측만 검증
                    if time_diff.total_seconds() >= 12 * 3600:
                        pred_price = pred.get('price', 0)
                        pred_direction = pred.get('predicted_direction', 'neutral')
                        pred_min = pred.get('predicted_min', pred_price)
                        pred_max = pred.get('predicted_max', pred_price)
                        
                        if pred_price > 0:
                            actual_change = ((current_price - pred_price) / pred_price) * 100
                            
                            # 방향 적중 여부 (더 엄격하게)
                            direction_correct = False
                            if pred_direction == 'up' and actual_change > 1.0:  # 1% 이상 상승
                                direction_correct = True
                            elif pred_direction == 'down' and actual_change < -1.0:  # 1% 이상 하락
                                direction_correct = True
                            elif pred_direction == 'sideways' and abs(actual_change) <= 2.0:  # 2% 이내 횡보
                                direction_correct = True
                            
                            # 범위 적중 여부
                            range_correct = pred_min <= current_price <= pred_max
                            
                            total_predictions += 1
                            if direction_correct:
                                correct_predictions += 1
                            
                            # 최근 3개 예측만 상세 표시
                            if len(recent_validations) < 3:
                                accuracy_score = 100 if direction_correct else 0
                                if range_correct:
                                    accuracy_score = min(accuracy_score + 20, 100)
                                
                                recent_validations.append({
                                    'time': pred_time.strftime('%m-%d %H:%M'),
                                    'direction': pred_direction.upper(),
                                    'predicted_price': pred_price,
                                    'actual_change': actual_change,
                                    'direction_correct': direction_correct,
                                    'range_correct': range_correct,
                                    'accuracy_score': accuracy_score
                                })
                
                except Exception as e:
                    logger.debug(f"예측 검증 오류: {e}")
                    continue
            
            if total_predictions == 0:
                return "• 검증 가능한 예측이 없습니다 (12시간 경과 필요)\n• 현재 예측을 저장하고 있습니다\n• 다음 검증: 12시간 후"
            
            # 정확도 계산
            accuracy_rate = (correct_predictions / total_predictions) * 100
            
            # 최근 예측 결과 포맷
            recent_results = []
            for val in recent_validations:
                result_emoji = "✅" if val['direction_correct'] else "❌"
                range_emoji = "🎯" if val['range_correct'] else "📍"
                
                recent_results.append(
                    f"<b>{val['time']}</b>: {val['direction']} → {result_emoji} {range_emoji} ({val['actual_change']:+.1f}%)"
                )
            
            recent_text = '\n'.join(recent_results) if recent_results else "• 최근 검증 결과 없음"
            
            # 성과 분석 (더 엄격한 기준)
            if accuracy_rate >= 80:
                performance = "🥇 매우 우수"
                advice = "신뢰도 높은 예측 시스템"
            elif accuracy_rate >= 70:
                performance = "🥈 우수"
                advice = "안정적인 예측 성능"
            elif accuracy_rate >= 60:
                performance = "🥉 양호"
                advice = "참고용으로 활용 권장"
            elif accuracy_rate >= 50:
                performance = "🟡 보통"
                advice = "추가 지표와 함께 활용"
            else:
                performance = "🔴 개선 필요"
                advice = "신중한 판단 필요"
            
            return f"""• 총 검증: <b>{total_predictions}건</b> 중 <b>{correct_predictions}건</b> 적중
• 방향 정확도: <b>{accuracy_rate:.1f}%</b> ({performance})
• 평가: {advice}

<b>최근 예측 검증 결과:</b>
{recent_text}"""
            
        except Exception as e:
            logger.error(f"예측 검증 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return "• 예측 검증 시스템 일시 오류\n• 데이터 복구 중입니다"

    async def _save_current_prediction(self, market_data: dict, indicators: dict):
        """현재 예측 저장"""
        try:
            current_price = market_data.get('current_price', 0)
            composite = indicators.get('composite_signals', {})
            total_score = composite.get('total_score', 0)
            
            # 예측 방향 결정
            if total_score >= 3:
                direction = 'up'
            elif total_score <= -3:
                direction = 'down'
            else:
                direction = 'sideways'
            
            # 예상 범위 계산
            volatility_indicators = indicators.get('volatility_indicators', {})
            atr = volatility_indicators.get('atr', current_price * 0.015)
            
            # 방향별 범위 설정 (더 정교하게)
            if direction == 'up':
                if total_score >= 6:  # 매우 강한 상승
                    pred_min = current_price - atr * 0.5
                    pred_max = current_price + atr * 3.0
                else:  # 보통 상승
                    pred_min = current_price - atr * 0.7
                    pred_max = current_price + atr * 2.0
            elif direction == 'down':
                if total_score <= -6:  # 매우 강한 하락
                    pred_min = current_price - atr * 3.0
                    pred_max = current_price + atr * 0.5
                else:  # 보통 하락
                    pred_min = current_price - atr * 2.0
                    pred_max = current_price + atr * 0.7
            else:  # 횡보
                pred_min = current_price - atr * 1.0
                pred_max = current_price + atr * 1.0
            
            # 신뢰도 계산
            confidence = self._calculate_signal_confidence(indicators)
            
            # 주요 지표 값들 저장
            momentum = indicators.get('momentum_indicators', {})
            rsi_value = momentum.get('rsi_14', 50)
            macd_data = momentum.get('macd', {})
            macd_hist = macd_data.get('histogram', 0) if isinstance(macd_data, dict) else 0
            
            prediction = {
                'timestamp': datetime.now().isoformat(),
                'price': current_price,
                'predicted_direction': direction,
                'predicted_min': pred_min,
                'predicted_max': pred_max,
                'score': total_score,
                'confidence': confidence,
                'volatility': market_data.get('volatility', 0),
                'rsi': rsi_value,
                'macd_histogram': macd_hist,
                'funding_rate': market_data.get('funding_rate', 0),
                'volume_24h': market_data.get('volume_24h', 0),
                'atr': atr,
                'prediction_strength': 'strong' if abs(total_score) >= 6 else 'moderate' if abs(total_score) >= 3 else 'weak'
            }
            
            self.prediction_history.append(prediction)
            
            # 최근 50개만 유지
            if len(self.prediction_history) > 50:
                self.prediction_history = self.prediction_history[-50:]
            
            self._save_prediction_history()
            
            logger.info(f"예측 저장: {direction.upper()} (점수: {total_score:.1f}, 신뢰도: {confidence:.0f}%)")
            
        except Exception as e:
            logger.error(f"예측 저장 실패: {e}")

    # 보조 함수들 (기술적 지표 계산)
    def _calculate_sma(self, prices: list, period: int) -> float:
        """단순이동평균"""
        if len(prices) < period:
            return 0
        return sum(prices[-period:]) / period

    def _calculate_ema(self, prices: list, period: int) -> float:
        """지수이동평균"""
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema

    def _calculate_rsi(self, prices: list, period: int = 14) -> float:
        """RSI 계산"""
        if len(prices) < period + 1:
            return 50
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        if len(gains) < period:
            return 50
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    def _calculate_macd(self, prices: list) -> dict:
        """MACD 계산"""
        if len(prices) < 26:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
        
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        macd = ema_12 - ema_26
        
        # Signal line (MACD의 9일 EMA)
        macd_values = [macd]  # 실제로는 여러 일의 MACD가 필요하지만 간단히 처리
        signal = macd  # 간단히 처리
        histogram = macd - signal
        
        return {
            'macd': macd,
            'signal': signal,
            'histogram': histogram
        }

    def _calculate_stochastic(self, highs: list, lows: list, closes: list, period: int = 14) -> tuple:
        """스토캐스틱 계산"""
        if len(closes) < period:
            return 50, 50
        
        lowest_low = min(lows[-period:])
        highest_high = max(highs[-period:])
        
        if highest_high == lowest_low:
            return 50, 50
        
        k = ((closes[-1] - lowest_low) / (highest_high - lowest_low)) * 100
        d = k  # 간단히 처리
        
        return k, d

    def _calculate_cci(self, highs: list, lows: list, closes: list, period: int = 20) -> float:
        """CCI 계산"""
        if len(closes) < period:
            return 0
        
        typical_prices = [(h + l + c) / 3 for h, l, c in zip(highs[-period:], lows[-period:], closes[-period:])]
        sma = sum(typical_prices) / len(typical_prices)
        
        mean_deviation = sum(abs(tp - sma) for tp in typical_prices) / len(typical_prices)
        
        if mean_deviation == 0:
            return 0
        
        cci = (typical_prices[-1] - sma) / (0.015 * mean_deviation)
        return cci

    def _calculate_williams_r(self, highs: list, lows: list, closes: list, period: int = 14) -> float:
        """Williams %R 계산"""
        if len(closes) < period:
            return -50
        
        highest_high = max(highs[-period:])
        lowest_low = min(lows[-period:])
        
        if highest_high == lowest_low:
            return -50
        
        williams_r = ((highest_high - closes[-1]) / (highest_high - lowest_low)) * -100
        return williams_r

    def _calculate_momentum(self, prices: list, period: int = 10) -> float:
        """모멘텀 계산"""
        if len(prices) < period + 1:
            return 0
        return prices[-1] - prices[-period-1]

    def _calculate_roc(self, prices: list, period: int = 10) -> float:
        """Rate of Change"""
        if len(prices) < period + 1:
            return 0
        return ((prices[-1] - prices[-period-1]) / prices[-period-1]) * 100

    def _calculate_bollinger_bands(self, prices: list, period: int = 20, std_dev: int = 2) -> dict:
        """볼린저 밴드"""
        if len(prices) < period:
            return {'upper': 0, 'middle': 0, 'lower': 0}
        
        sma = sum(prices[-period:]) / period
        variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
        std = variance ** 0.5
        
        return {
            'upper': sma + (std_dev * std),
            'middle': sma,
            'lower': sma - (std_dev * std)
        }

    def _calculate_atr(self, highs: list, lows: list, closes: list, period: int = 14) -> float:
        """ATR 계산"""
        if len(closes) < 2:
            return 0
        
        true_ranges = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            true_ranges.append(max(high_low, high_close, low_close))
        
        if len(true_ranges) < period:
            return sum(true_ranges) / len(true_ranges) if true_ranges else 0
        
        return sum(true_ranges[-period:]) / period

    def _calculate_adx(self, highs: list, lows: list, closes: list, period: int = 14) -> float:
        """ADX 계산 (간소화)"""
        if len(closes) < period * 2:
            return 25
        
        # 간단한 ADX 근사치
        price_ranges = []
        for i in range(1, len(closes)):
            high_diff = abs(highs[i] - highs[i-1])
            low_diff = abs(lows[i] - lows[i-1])
            close_diff = abs(closes[i] - closes[i-1])
            price_ranges.append(max(high_diff, low_diff, close_diff))
        
        if not price_ranges:
            return 25
        
        avg_range = sum(price_ranges[-period:]) / min(period, len(price_ranges))
        current_price = closes[-1]
        
        # 정규화
        adx = min((avg_range / current_price) * 10000, 100) if current_price > 0 else 25
        return max(adx, 0)

    def _calculate_obv(self, closes: list, volumes: list) -> float:
        """OBV 계산"""
        if len(closes) < 2 or len(volumes) != len(closes):
            return 0
        
        obv = 0
        for i in range(1, len(closes)):
            if closes[i] > closes[i-1]:
                obv += volumes[i]
            elif closes[i] < closes[i-1]:
                obv -= volumes[i]
        
        return obv

    def _calculate_mfi(self, highs: list, lows: list, closes: list, volumes: list, period: int = 14) -> float:
        """MFI 계산"""
        if len(closes) < period + 1 or len(volumes) != len(closes):
            return 50
        
        typical_prices = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
        
        positive_flow = 0
        negative_flow = 0
        
        for i in range(len(typical_prices) - period, len(typical_prices)):
            if i == 0:
                continue
            
            money_flow = typical_prices[i] * volumes[i]
            
            if typical_prices[i] > typical_prices[i-1]:
                positive_flow += money_flow
            elif typical_prices[i] < typical_prices[i-1]:
                negative_flow += money_flow
        
        if negative_flow == 0:
            return 100
        
        money_ratio = positive_flow / negative_flow
        mfi = 100 - (100 / (1 + money_ratio))
        
        return mfi

    def _calculate_keltner_channels(self, highs: list, lows: list, closes: list, period: int = 20, multiplier: float = 2) -> dict:
        """켈트너 채널"""
        if len(closes) < period:
            ema = sum(closes) / len(closes) if closes else 0
        else:
            ema = self._calculate_ema(closes, period)
        
        atr = self._calculate_atr(highs, lows, closes, period)
        
        return {
            'upper': ema + (multiplier * atr),
            'middle': ema,
            'lower': ema - (multiplier * atr)
        }

    def _calculate_volatility_ratio(self, prices: list, period: int = 20) -> float:
        """변동성 비율"""
        if len(prices) < period:
            return 1
        
        recent_prices = prices[-period:]
        returns = [(recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1] 
                  for i in range(1, len(recent_prices))]
        
        if not returns:
            return 1
        
        volatility = (sum(r*r for r in returns) / len(returns)) ** 0.5
        
        # 정규화
        return min(volatility * 100, 10)

    def _calculate_price_channels(self, highs: list, lows: list, period: int = 20) -> dict:
        """가격 채널"""
        if len(highs) < period or len(lows) < period:
            return {'upper': 0, 'lower': 0}
        
        return {
            'upper': max(highs[-period:]),
            'lower': min(lows[-period:])
        }

    def _calculate_pivot_points(self, highs: list, lows: list, closes: list) -> dict:
        """피봇 포인트"""
        if not highs or not lows or not closes:
            return {}
        
        high = highs[-1]
        low = lows[-1]
        close = closes[-1]
        
        pivot = (high + low + close) / 3
        
        return {
            'pivot': pivot,
            'r1': 2 * pivot - low,
            'r2': pivot + (high - low),
            's1': 2 * pivot - high,
            's2': pivot - (high - low)
        }

    def _calculate_fibonacci_levels(self, highs: list, lows: list, period: int = 50) -> dict:
        """피보나치 레벨"""
        if len(highs) < period or len(lows) < period:
            return {}
        
        recent_high = max(highs[-period:])
        recent_low = min(lows[-period:])
        diff = recent_high - recent_low
        
        return {
            'level_236': recent_high - (diff * 0.236),
            'level_382': recent_high - (diff * 0.382),
            'level_500': recent_high - (diff * 0.500),
            'level_618': recent_high - (diff * 0.618),
            'level_786': recent_high - (diff * 0.786)
        }

    def _identify_key_levels(self, highs: list, lows: list, closes: list) -> dict:
        """주요 레벨 식별"""
        if not closes:
            return {}
        
        current_price = closes[-1]
        
        # 최근 20일 고점/저점
        period = min(20, len(highs))
        if period > 0:
            resistance = max(highs[-period:])
            support = min(lows[-period:])
        else:
            resistance = current_price * 1.02
            support = current_price * 0.98
        
        return {
            'support': support,
            'resistance': resistance,
            'current_position': (current_price - support) / (resistance - support) if resistance != support else 0.5
        }

    def _calculate_breakout_levels(self, closes: list) -> dict:
        """돌파 레벨 계산"""
        if len(closes) < 20:
            return {}
        
        recent_closes = closes[-20:]
        avg_price = sum(recent_closes) / len(recent_closes)
        
        # 표준편차 계산
        variance = sum((p - avg_price) ** 2 for p in recent_closes) / len(recent_closes)
        std_dev = variance ** 0.5
        
        return {
            'upper_breakout': avg_price + (2 * std_dev),
            'lower_breakout': avg_price - (2 * std_dev),
            'average': avg_price
        }

    def _analyze_trend_strength(self, closes: list) -> str:
        """추세 강도 분석"""
        if len(closes) < 10:
            return 'weak'
        
        recent = closes[-5:]
        older = closes[-10:-5]
        
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        
        change_pct = ((recent_avg - older_avg) / older_avg) * 100
        
        if abs(change_pct) > 5:
            return 'very_strong'
        elif abs(change_pct) > 2:
            return 'strong'
        elif abs(change_pct) > 0.5:
            return 'moderate'
        else:
            return 'weak'

    def _analyze_ma_alignment(self, closes: list, current_price: float) -> str:
        """이동평균 배열 분석"""
        if len(closes) < 100 or current_price == 0:
            return 'neutral'
        
        sma_20 = self._calculate_sma(closes, 20)
        sma_50 = self._calculate_sma(closes, 50)
        sma_100 = self._calculate_sma(closes, 100)
        
        if current_price > sma_20 > sma_50 > sma_100:
            return 'strong_bullish'
        elif current_price < sma_20 < sma_50 < sma_100:
            return 'strong_bearish'
        elif current_price > sma_20 > sma_50:
            return 'bullish'
        elif current_price < sma_20 < sma_50:
            return 'bearish'
        else:
            return 'neutral'

    def _calculate_composite_signals(self, indicators: dict) -> dict:
        """종합 신호 계산"""
        try:
            signals = {'bullish': 0, 'bearish': 0, 'neutral': 0}
            total_score = 0
            
            # 추세 지표 점수
            trend = indicators.get('trend_indicators', {})
            ma_alignment = trend.get('ma_alignment', 'neutral')
            
            if ma_alignment == 'strong_bullish':
                total_score += 4
                signals['bullish'] += 1
            elif ma_alignment == 'bullish':
                total_score += 2
                signals['bullish'] += 1
            elif ma_alignment == 'strong_bearish':
                total_score -= 4
                signals['bearish'] += 1
            elif ma_alignment == 'bearish':
                total_score -= 2
                signals['bearish'] += 1
            else:
                signals['neutral'] += 1
            
            # ADX 점수
            adx = trend.get('adx', 25)
            if adx > 40:
                trend_multiplier = 1.5
            elif adx > 25:
                trend_multiplier = 1.2
            else:
                trend_multiplier = 0.8
            
            # 모멘텀 지표 점수
            momentum = indicators.get('momentum_indicators', {})
            rsi = momentum.get('rsi_14', 50)
            
            if rsi > 80:
                total_score -= 3
                signals['bearish'] += 1
            elif rsi > 70:
                total_score -= 1
                signals['bearish'] += 1
            elif rsi < 20:
                total_score += 3
                signals['bullish'] += 1
            elif rsi < 30:
                total_score += 1
                signals['bullish'] += 1
            else:
                signals['neutral'] += 1
            
            # MACD 점수
            macd_data = momentum.get('macd', {})
            if isinstance(macd_data, dict):
                macd_hist = macd_data.get('histogram', 0)
                if macd_hist > 100:
                    total_score += 2
                    signals['bullish'] += 1
                elif macd_hist > 0:
                    total_score += 1
                    signals['bullish'] += 1
                elif macd_hist < -100:
                    total_score -= 2
                    signals['bearish'] += 1
                elif macd_hist < 0:
                    total_score -= 1
                    signals['bearish'] += 1
                else:
                    signals['neutral'] += 1
            
            # 거래량 가중치
            volume = indicators.get('volume_indicators', {})
            volume_ratio = volume.get('volume_ratio', 1)
            
            if volume_ratio > 1.5:
                total_score *= 1.2  # 거래량이 높으면 신호 강화
            elif volume_ratio < 0.7:
                total_score *= 0.8  # 거래량이 낮으면 신호 약화
            
            # 추세 강도 적용
            total_score *= trend_multiplier
            
            # 방향 결정
            if total_score > 3:
                direction = 'strong_bullish'
                strength = 'strong'
            elif total_score > 1:
                direction = 'bullish'
                strength = 'moderate'
            elif total_score < -3:
                direction = 'strong_bearish'
                strength = 'strong'
            elif total_score < -1:
                direction = 'bearish'
                strength = 'moderate'
            else:
                direction = 'neutral'
                strength = 'weak'
            
            return {
                'total_score': total_score,
                'direction': direction,
                'strength': strength,
                'bullish_signals': signals['bullish'],
                'bearish_signals': signals['bearish'],
                'neutral_signals': signals['neutral']
            }
            
        except Exception as e:
            logger.error(f"종합 신호 계산 실패: {e}")
            return {
                'total_score': 0,
                'direction': 'neutral',
                'strength': 'weak',
                'bullish_signals': 0,
                'bearish_signals': 0,
                'neutral_signals': 1
            }

    def _analyze_market_structure_detailed(self, klines_1h: list, klines_4h: list, klines_1d: list) -> dict:
        """상세한 시장 구조 분석"""
        try:
            structure = {}
            
            # 4시간 구조 분석
            if klines_4h and len(klines_4h) >= 20:
                closes_4h = [float(k[4]) for k in klines_4h[-20:]]
                highs_4h = [float(k[2]) for k in klines_4h[-20:]]
                lows_4h = [float(k[3]) for k in klines_4h[-20:]]
                
                # 고점/저점 패턴
                recent_high = max(highs_4h[-10:])
                recent_low = min(lows_4h[-10:])
                current_price = closes_4h[-1]
                
                # 추세 분석
                price_change = (current_price - closes_4h[0]) / closes_4h[0]
                
                if price_change > 0.05:
                    structure['trend'] = 'strong_uptrend'
                elif price_change > 0.02:
                    structure['trend'] = 'uptrend'
                elif price_change < -0.05:
                    structure['trend'] = 'strong_downtrend'
                elif price_change < -0.02:
                    structure['trend'] = 'downtrend'
                else:
                    structure['trend'] = 'sideways'
                
                # 변동성 구조
                volatility_4h = (recent_high - recent_low) / current_price
                if volatility_4h > 0.15:
                    structure['volatility_structure'] = 'high_volatility'
                elif volatility_4h > 0.08:
                    structure['volatility_structure'] = 'medium_volatility'
                else:
                    structure['volatility_structure'] = 'low_volatility'
                
                # 시장 단계
                if recent_high == max(highs_4h) and recent_low == min(lows_4h):
                    structure['phase'] = 'expansion'
                elif recent_high < max(highs_4h[-15:-5]) and recent_low > min(lows_4h[-15:-5]):
                    structure['phase'] = 'consolidation'
                else:
                    structure['phase'] = 'transition'
            
            # 일봉 구조 (장기)
            if klines_1d and len(klines_1d) >= 10:
                closes_1d = [float(k[4]) for k in klines_1d[-10:]]
                
                # 장기 추세
                long_term_change = (closes_1d[-1] - closes_1d[0]) / closes_1d[0]
                
                if long_term_change > 0.1:
                    structure['long_term_trend'] = 'strong_bull_market'
                elif long_term_change > 0.05:
                    structure['long_term_trend'] = 'bull_market'
                elif long_term_change < -0.1:
                    structure['long_term_trend'] = 'strong_bear_market'
                elif long_term_change < -0.05:
                    structure['long_term_trend'] = 'bear_market'
                else:
                    structure['long_term_trend'] = 'ranging_market'
            
            return structure
            
        except Exception as e:
            logger.error(f"시장 구조 분석 실패: {e}")
            return {
                'trend': 'sideways',
                'phase': 'consolidation',
                'volatility_structure': 'medium_volatility',
                'long_term_trend': 'ranging_market'
            }

    async def _format_comprehensive_pnl(self) -> str:
        """종합 손익 현황 포맷"""
        try:
            if not self.bitget_client:
                return "• 손익 데이터를 불러올 수 없습니다"
            
            # 계정 정보 조회
            account_info = await self.bitget_client.get_account_info()
            
            if not account_info:
                return "• 계정 정보 조회 실패"
            
            # 현재 자산 정보
            total_equity = float(account_info.get('accountEquity', 0))
            available_balance = float(account_info.get('available', 0))
            unrealized_pnl = float(account_info.get('unrealizedPL', 0))
            
            # 현재 포지션 조회
            positions = await self.bitget_client.get_positions('BTCUSDT')
            
            position_info = "없음"
            position_pnl = 0
            position_size = 0
            
            if positions:
                for pos in positions:
                    size = float(pos.get('total', 0))
                    if size > 0:
                        position_size = size
                        position_pnl = float(pos.get('unrealizedPL', 0))
                        side = pos.get('side', '')
                        entry_price = float(pos.get('averageOpenPrice', 0))
                        current_price = float(pos.get('markPrice', 0))
                        
                        if side == 'long':
                            position_info = f"롱 {size} BTC (진입: ${entry_price:,.0f})"
                        else:
                            position_info = f"숏 {size} BTC (진입: ${entry_price:,.0f})"
                        break
            
            # 7일 손익 조회 (개선된 버전)
            weekly_pnl_data = await self.bitget_client.get_enhanced_profit_history(days=7)
            weekly_total = weekly_pnl_data.get('total_pnl', 0)
            daily_avg = weekly_pnl_data.get('average_daily', 0)
            
            # 오늘 손익 (실현 손익 기준)
            today_pnl_data = await self.bitget_client.get_enhanced_profit_history(days=1)
            today_realized = today_pnl_data.get('total_pnl', 0)
            
            # 초기 자본 기준 총 수익 계산
            initial_capital = 8000  # 기본 초기 자본 설정
            total_profit = total_equity - initial_capital
            
            # 수익률 계산
            if initial_capital > 0:
                total_return_pct = (total_profit / initial_capital) * 100
                weekly_return_pct = (weekly_total / initial_capital) * 100
            else:
                total_return_pct = 0
                weekly_return_pct = 0
            
            # 이모지 및 색상
            total_emoji = "🟢" if total_profit >= 0 else "🔴"
            weekly_emoji = "📈" if weekly_total >= 0 else "📉"
            today_emoji = "⬆️" if today_realized >= 0 else "⬇️"
            unrealized_emoji = "💰" if unrealized_pnl >= 0 else "💸"
            
            return f"""• 총 자산: <b>${total_equity:,.2f}</b>
• 사용 가능: ${available_balance:,.2f}
• 총 수익: {total_emoji} <b>${total_profit:+,.2f}</b> ({total_return_pct:+.1f}%)
• 금일 실현: {today_emoji} <b>${today_realized:+,.2f}</b>
• 7일 손익: {weekly_emoji} <b>${weekly_total:+,.2f}</b> ({weekly_return_pct:+.1f}%)
• 일평균: <b>${daily_avg:+,.2f}</b>
• 미실현: {unrealized_emoji} <b>${unrealized_pnl:+,.2f}</b>
• 현재 포지션: <b>{position_info}</b>"""
            
        except Exception as e:
            logger.error(f"손익 현황 포맷 실패: {e}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return "• 손익 데이터 처리 중..."

    async def _generate_intelligent_mental_care(self, market_data: dict, indicators: dict) -> str:
        """🔥 지능적 멘탈 케어 생성"""
        try:
            if not self.mental_care:
                return "오늘도 차분하게 시장을 분석하며 현명한 판단을 내리시길 바랍니다. 📊"
            
            # 현재 시장 상황 분석
            current_price = market_data.get('current_price', 0)
            change_24h = market_data.get('change_24h', 0)
            volatility = market_data.get('volatility', 0)
            
            # 기술적 지표 상황
            composite = indicators.get('composite_signals', {})
            total_score = composite.get('total_score', 0)
            direction = composite.get('direction', 'neutral')
            
            # 모멘텀 지표
            momentum = indicators.get('momentum_indicators', {})
            rsi = momentum.get('rsi_14', 50)
            
            # 손익 정보 (간단히)
            pnl_context = ""
            if self.bitget_client:
                try:
                    account_info = await self.bitget_client.get_account_info()
                    if account_info:
                        unrealized_pnl = float(account_info.get('unrealizedPL', 0))
                        if unrealized_pnl > 100:
                            pnl_context = "현재 좋은 수익을 내고 계시는군요!"
                        elif unrealized_pnl < -100:
                            pnl_context = "일시적인 손실이 있지만 장기적 관점을 유지하세요."
                        else:
                            pnl_context = "안정적인 포지션을 유지하고 계십니다."
                except:
                    pnl_context = ""
            
            # 상황별 멘탈 케어 메시지
            mental_message = await self.mental_care.generate_mental_care(
                market_trend=direction,
                volatility=volatility,
                user_context={
                    'rsi': rsi,
                    'price_change': change_24h,
                    'signal_strength': abs(total_score),
                    'pnl_context': pnl_context
                }
            )
            
            return mental_message
            
        except Exception as e:
            logger.error(f"멘탈 케어 생성 실패: {e}")
            
            # 폴백 메시지
            fallback_messages = [
                "시장은 항상 변화합니다. 감정이 아닌 데이터로 판단하세요. 📊",
                "인내심을 갖고 기다리는 것도 훌륭한 전략입니다. ⏳",
                "리스크 관리가 수익보다 더 중요합니다. 🛡️",
                "오늘의 손실이 내일의 기회가 될 수 있습니다. 🌅",
                "시장에 겸손하되, 자신의 분석에는 확신을 가지세요. 💪"
            ]
            
            import random
            return random.choice(fallback_messages)

    async def close(self):
        """세션 정리"""
        try:
            if self.news_session:
                await self.news_session.close()
                logger.info("뉴스 세션 종료")
        except Exception as e:
            logger.error(f"세션 종료 중 오류: {e}")
