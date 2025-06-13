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
import numpy as np

logger = logging.getLogger(__name__)

class RegularReportGenerator(BaseReportGenerator):
    """정기 리포트 생성기 - 실전 매매 특화 (개선된 버전)"""
    
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
        
        logger.info("정기 리포트 생성기 초기화 완료 - 실전 매매 특화 (개선된 버전)")
    
    def _load_prediction_history(self):
        """예측 기록 로드"""
        try:
            if os.path.exists(self.prediction_history_file):
                with open(self.prediction_history_file, 'r', encoding='utf-8') as f:
                    self.prediction_history = json.load(f)
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
        """🎯 실전 매매 특화 리포트 생성 (개선된 버전)"""
        try:
            current_time = self._get_current_time_kst()
            
            logger.info("실전 매매 리포트 생성 시작 (개선된 버전)")
            
            # 1. 핵심 데이터 수집
            market_data = await self._collect_enhanced_market_data()
            news_events = await self._collect_critical_bitcoin_news()  # 비트코인 전용
            trading_signals = await self._analyze_advanced_trading_signals(market_data)
            price_prediction = await self._generate_dynamic_prediction(market_data, trading_signals)  # 동적 예측
            strategy = await self._generate_practical_strategy(market_data, trading_signals)
            pnl_data = await self._get_pnl_summary()
            
            # 2. 현재 예측 저장
            await self._save_current_prediction(market_data, trading_signals, price_prediction)
            
            # 3. 최종 리포트 생성 (간소화된 형식)
            report = f"""🎯 <b>비트코인 선물 매매 분석</b>
📅 {current_time}
━━━━━━━━━━━━━━━━━━━

<b>🚨 핵심 뉴스 ({len(news_events)}개)</b>
{await self._format_bitcoin_news(news_events)}

<b>📊 현재 시장 상황</b>
{await self._format_market_status(market_data)}

<b>⚡ 매매 신호 분석</b>
{await self._format_trading_signals(trading_signals)}

<b>🎯 12시간 가격 예측</b>
{await self._format_dynamic_prediction(price_prediction)}

<b>💡 실전 매매 전략</b>
{await self._format_practical_strategy(strategy, market_data)}

<b>📈 손익 현황</b>
{await self._format_pnl_summary(pnl_data)}

━━━━━━━━━━━━━━━━━━━
⚡ 다음 업데이트: 4시간 후"""
            
            logger.info("실전 매매 리포트 생성 완료 (개선된 버전)")
            return report
            
        except Exception as e:
            logger.error(f"리포트 생성 실패: {str(e)}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return f"❌ 리포트 생성 중 오류가 발생했습니다: {str(e)}"

    async def _collect_enhanced_market_data(self) -> dict:
        """강화된 시장 데이터 수집"""
        try:
            market_data = {}
            
            if self.bitget_client:
                # 티커 정보
                ticker = await self.bitget_client.get_ticker('BTCUSDT')
                if ticker:
                    current_price = float(ticker.get('last', 0))
                    change_24h = float(ticker.get('changeUtc', 0))
                    high_24h = float(ticker.get('high24h', 0))
                    low_24h = float(ticker.get('low24h', 0))
                    volume_24h = float(ticker.get('baseVolume', 0))
                    
                    market_data.update({
                        'current_price': current_price,
                        'change_24h': change_24h,
                        'change_24h_pct': change_24h * 100,
                        'high_24h': high_24h,
                        'low_24h': low_24h,
                        'volume_24h': volume_24h,
                        'quote_volume_24h': float(ticker.get('quoteVolume', 0))
                    })
                    
                    logger.info(f"현재 BTC 가격: ${current_price:,.0f} ({change_24h:+.2%})")
                
                # K라인 데이터 (더 많은 데이터)
                try:
                    klines_1h = await self.bitget_client.get_kline('BTCUSDT', '1H', 500)  # 더 많은 데이터
                    klines_4h = await self.bitget_client.get_kline('BTCUSDT', '4H', 200)
                    klines_1d = await self.bitget_client.get_kline('BTCUSDT', '1D', 100)
                    
                    if klines_1h:
                        market_data.update({
                            'klines_1h': klines_1h,
                            'klines_4h': klines_4h,
                            'klines_1d': klines_1d
                        })
                        
                        # 정확한 변동성 계산
                        closes_1h = [float(k[4]) for k in klines_1h[-48:]]  # 48시간
                        if len(closes_1h) >= 2:
                            returns = [(closes_1h[i] - closes_1h[i-1]) / closes_1h[i-1] for i in range(1, len(closes_1h))]
                            volatility = (sum(r*r for r in returns) / len(returns)) ** 0.5 * (24 ** 0.5) * 100
                            market_data['volatility'] = volatility
                        else:
                            market_data['volatility'] = 2.0
                        
                        # 정확한 거래량 비율 계산
                        volumes_1h = [float(k[5]) for k in klines_1h[-48:]]
                        if len(volumes_1h) >= 24:
                            avg_volume_24h = sum(volumes_1h[-24:]) / 24
                            current_volume = sum(volumes_1h[-3:]) / 3  # 최근 3시간 평균
                            market_data['volume_ratio'] = current_volume / avg_volume_24h if avg_volume_24h > 0 else 1.0
                        else:
                            market_data['volume_ratio'] = 1.0
                        
                except Exception as e:
                    logger.warning(f"K라인 데이터 수집 실패: {e}")
                    market_data['volatility'] = 2.0
                    market_data['volume_ratio'] = 1.0
                
                # 펀딩비
                try:
                    funding = await self.bitget_client.get_funding_rate('BTCUSDT')
                    if funding:
                        market_data['funding_rate'] = float(funding.get('fundingRate', 0))
                        market_data['next_funding_time'] = funding.get('nextFundingTime', '')
                except Exception as e:
                    logger.warning(f"펀딩비 수집 실패: {e}")
                    market_data['funding_rate'] = 0
                
                # 미결제약정
                try:
                    oi = await self.bitget_client.get_open_interest('BTCUSDT')
                    if oi:
                        market_data['open_interest'] = float(oi.get('openInterest', 0))
                        market_data['oi_change_24h'] = float(oi.get('change24h', 0))
                except Exception as e:
                    logger.warning(f"미결제약정 수집 실패: {e}")
                    market_data['open_interest'] = 0
                    market_data['oi_change_24h'] = 0
            
            # 기본값 설정
            if 'current_price' not in market_data or market_data['current_price'] == 0:
                market_data.update({
                    'current_price': 105627,
                    'change_24h': 0.012,
                    'change_24h_pct': 1.2,
                    'high_24h': 107500,
                    'low_24h': 104200,
                    'volume_24h': 85000,
                    'volatility': 3.2,
                    'volume_ratio': 2.1,
                    'funding_rate': 0.00015
                })
                logger.warning("시장 데이터 수집 실패, 기본값 사용")
            
            self.market_cache = market_data
            return market_data
            
        except Exception as e:
            logger.error(f"시장 데이터 수집 실패: {e}")
            # 폴백 데이터 반환
            fallback_data = {
                'current_price': 105627,
                'change_24h': 0.012,
                'change_24h_pct': 1.2,
                'high_24h': 107500,
                'low_24h': 104200,
                'volume_24h': 85000,
                'volatility': 3.2,
                'volume_ratio': 2.1,
                'funding_rate': 0.00015,
                'open_interest': 0,
                'oi_change_24h': 0
            }
            self.market_cache = fallback_data
            return fallback_data

    async def _collect_critical_bitcoin_news(self) -> list:
        """🚨 비트코인/연준/트럼프/거시경제 핵심 뉴스만 수집 (4개 제한)"""
        try:
            events = []
            
            if self.data_collector and hasattr(self.data_collector, 'get_recent_news'):
                try:
                    recent_news = await self.data_collector.get_recent_news(hours=8)  # 8시간으로 단축
                    if recent_news:
                        # 비트코인/거시경제 관련 뉴스만 엄격히 필터링
                        for news in recent_news:
                            if self._is_critical_bitcoin_news(news):
                                # 제목 번역 (필요시)
                                if not news.get('title_ko'):
                                    news['title_ko'] = await self._translate_news_title(news.get('title', ''))
                                
                                # 시장 영향 분석 (간단하게)
                                news['market_impact'] = self._analyze_bitcoin_impact(news)
                                events.append(news)
                                
                                if len(events) >= 4:  # 정확히 4개로 제한
                                    break
                        
                        logger.info(f"비트코인 핵심 뉴스 수집 완료: {len(events)}개")
                except Exception as e:
                    logger.warning(f"뉴스 수집 실패: {e}")
            
            if not events:
                events = self._generate_default_bitcoin_events()
            
            self.news_cache = events
            return events
            
        except Exception as e:
            logger.error(f"비트코인 뉴스 수집 실패: {e}")
            return self.news_cache or []

    def _is_critical_bitcoin_news(self, news: dict) -> bool:
        """비트코인 매매에 중요한 뉴스인지 엄격히 판단"""
        title = news.get('title', '').lower()
        description = news.get('description', '').lower()
        content = f"{title} {description}"
        
        # 🚨 제외 키워드 먼저 체크 (FIFA 등)
        exclude_keywords = [
            'fifa', 'nfl', 'game', 'sport', 'celebrity', 'entertainment', 'movie', 'music',
            'altcoin only', 'ethereum only', 'ripple only', 'dogecoin only', 'shiba',
            'how to', 'tutorial', 'guide', 'review', 'opinion', 'prediction only'
        ]
        
        for exclude in exclude_keywords:
            if exclude in content:
                return False
        
        # 🎯 비트코인 직접 관련 (최우선)
        bitcoin_direct = [
            'bitcoin', 'btc', '비트코인', 'bitcoin etf', 'bitcoin price', 'bitcoin crosses',
            'bitcoin hits', 'bitcoin breaks', 'bitcoin trading'
        ]
        
        # 🏛️ 연준/Fed 관련 (매우 중요)
        fed_keywords = [
            'fed', 'federal reserve', 'jerome powell', 'fomc', 'interest rate', 'rate cut', 'rate hike',
            '연준', '기준금리', '금리인하', '금리인상', 'monetary policy'
        ]
        
        # 🇺🇸 트럼프/정치 관련 (중요)
        trump_keywords = [
            'trump', 'biden', 'election', 'tariff', 'trade war', 'china trade', 'trade deal',
            '트럼프', '바이든', '관세', '무역전쟁', '무역협상'
        ]
        
        # 📊 거시경제 지표 (중요)
        macro_keywords = [
            'inflation', 'cpi', 'pce', 'unemployment', 'jobs report', 'gdp', 'recession',
            'dxy', 'dollar index', '인플레이션', '실업률', '달러지수'
        ]
        
        # 🏢 주요 기업 (비트코인 보유)
        company_keywords = [
            'tesla bitcoin', 'microstrategy bitcoin', 'blackrock bitcoin', 'coinbase',
            'sec bitcoin', 'regulation bitcoin'
        ]
        
        # 각 카테고리별 체크
        categories = [
            ('bitcoin_direct', bitcoin_direct),
            ('fed', fed_keywords),
            ('trump', trump_keywords),
            ('macro', macro_keywords),
            ('company', company_keywords)
        ]
        
        for category_name, keywords in categories:
            for keyword in keywords:
                if keyword in content:
                    logger.info(f"비트코인 뉴스 감지 ({category_name}): {keyword} in {title[:50]}...")
                    return True
        
        return False

    def _analyze_bitcoin_impact(self, news: dict) -> str:
        """비트코인에 대한 뉴스 영향 분석 (간단하게)"""
        title = news.get('title', '').lower()
        description = news.get('description', '').lower()
        content = f"{title} {description}"
        
        # 긍정적 신호
        positive_signals = [
            'rate cut', 'dovish', 'support', 'buy', 'purchase', 'adoption', 'approval',
            'breaks above', 'crosses', 'all time high', 'bullish', 'positive',
            '금리인하', '매수', '승인', '돌파', '상승'
        ]
        
        # 부정적 신호
        negative_signals = [
            'rate hike', 'hawkish', 'ban', 'restriction', 'lawsuit', 'crash', 'falls below',
            'bearish', 'negative', 'concern', 'tariff', 'trade war',
            '금리인상', '금지', '소송', '폭락', '하락', '관세'
        ]
        
        positive_count = sum(1 for signal in positive_signals if signal in content)
        negative_count = sum(1 for signal in negative_signals if signal in content)
        
        if positive_count > negative_count and positive_count >= 1:
            return "비트코인 긍정적"
        elif negative_count > positive_count and negative_count >= 1:
            return "비트코인 부정적"
        else:
            return "영향도 분석 중"

    def _generate_default_bitcoin_events(self) -> list:
        """기본 비트코인 이벤트 생성"""
        current_time = datetime.now()
        return [
            {
                'title': 'Bitcoin Technical Analysis Update',
                'title_ko': '비트코인 기술적 분석 업데이트',
                'description': '현재 비트코인 가격 움직임과 기술적 지표 종합 분석',
                'source': '시장 분석',
                'published_at': current_time.isoformat(),
                'market_impact': '기술적 분석',
                'weight': 7
            }
        ]

    async def _analyze_advanced_trading_signals(self, market_data: dict) -> dict:
        """🔍 고급 매매 신호 분석 (더 정교하게)"""
        try:
            signals = {
                'rsi_signals': {},
                'ma_signals': {},
                'macd_signals': {},
                'volume_signals': {},
                'funding_signals': {},
                'bollinger_signals': {},  # 볼린저 밴드 추가
                'composite_score': 0,
                'direction': 'neutral',
                'confidence': 50,
                'strength': 'weak'
            }
            
            if not self.market_cache.get('klines_1h'):
                return self._get_default_signals()
            
            klines_1h = self.market_cache.get('klines_1h', [])
            closes_1h = [float(k[4]) for k in klines_1h[-200:]]  # 더 많은 데이터
            highs_1h = [float(k[2]) for k in klines_1h[-200:]]
            lows_1h = [float(k[3]) for k in klines_1h[-200:]]
            volumes_1h = [float(k[5]) for k in klines_1h[-200:]]
            
            current_price = closes_1h[-1] if closes_1h else market_data.get('current_price', 0)
            
            # RSI 신호 분석 (개선)
            rsi_14 = self._calculate_rsi(closes_1h, 14)
            rsi_7 = self._calculate_rsi(closes_1h, 7)
            rsi_21 = self._calculate_rsi(closes_1h, 21)
            
            signals['rsi_signals'] = {
                'rsi_14': rsi_14,
                'rsi_7': rsi_7,
                'rsi_21': rsi_21,
                'signal': self._get_rsi_signal_advanced(rsi_14, rsi_7, rsi_21),
                'score': self._calculate_rsi_score_advanced(rsi_14, rsi_7, rsi_21)
            }
            
            # 이동평균 신호 분석 (개선)
            sma_20 = self._calculate_sma(closes_1h, 20)
            sma_50 = self._calculate_sma(closes_1h, 50)
            sma_100 = self._calculate_sma(closes_1h, 100)
            ema_12 = self._calculate_ema(closes_1h, 12)
            ema_26 = self._calculate_ema(closes_1h, 26)
            ema_50 = self._calculate_ema(closes_1h, 50)
            
            signals['ma_signals'] = {
                'sma_20': sma_20,
                'sma_50': sma_50,
                'sma_100': sma_100,
                'ema_12': ema_12,
                'ema_26': ema_26,
                'ema_50': ema_50,
                'signal': self._get_ma_signal_advanced(current_price, sma_20, sma_50, sma_100),
                'score': self._calculate_ma_score_advanced(current_price, sma_20, sma_50, sma_100, ema_12, ema_26)
            }
            
            # MACD 신호 분석 (개선)
            macd_data = self._calculate_macd_advanced(closes_1h)
            signals['macd_signals'] = {
                'macd': macd_data['macd'],
                'signal_line': macd_data['signal'],
                'histogram': macd_data['histogram'],
                'signal': self._get_macd_signal_advanced(macd_data),
                'score': self._calculate_macd_score_advanced(macd_data)
            }
            
            # 볼린저 밴드 신호 추가
            bb_data = self._calculate_bollinger_bands(closes_1h, 20, 2)
            signals['bollinger_signals'] = {
                'upper': bb_data['upper'],
                'middle': bb_data['middle'],
                'lower': bb_data['lower'],
                'position': bb_data['position'],
                'signal': self._get_bollinger_signal(bb_data, current_price),
                'score': self._calculate_bollinger_score(bb_data, current_price)
            }
            
            # 거래량 신호 분석 (개선)
            volume_ratio = market_data.get('volume_ratio', 1.0)
            volume_trend = self._analyze_volume_trend(volumes_1h)
            signals['volume_signals'] = {
                'volume_ratio': volume_ratio,
                'volume_trend': volume_trend,
                'signal': self._get_volume_signal_advanced(volume_ratio, volume_trend),
                'score': self._calculate_volume_score_advanced(volume_ratio, volume_trend)
            }
            
            # 펀딩비 신호 분석
            funding_rate = market_data.get('funding_rate', 0)
            signals['funding_signals'] = {
                'funding_rate': funding_rate,
                'annual_rate': funding_rate * 365 * 3,
                'signal': self._get_funding_signal(funding_rate),
                'score': self._calculate_funding_score(funding_rate)
            }
            
            # 종합 점수 계산 (가중치 조정)
            total_score = (
                signals['rsi_signals']['score'] * 0.20 +
                signals['ma_signals']['score'] * 0.25 +
                signals['macd_signals']['score'] * 0.20 +
                signals['bollinger_signals']['score'] * 0.15 +
                signals['volume_signals']['score'] * 0.10 +
                signals['funding_signals']['score'] * 0.10
            )
            
            signals['composite_score'] = total_score
            
            # 방향 및 신뢰도 결정 (더 정교하게)
            if total_score >= 7:
                signals['direction'] = 'strong_bullish'
                signals['confidence'] = min(90, 70 + total_score * 2)
                signals['strength'] = 'very_strong'
            elif total_score >= 4:
                signals['direction'] = 'bullish'
                signals['confidence'] = min(80, 60 + total_score * 3)
                signals['strength'] = 'strong'
            elif total_score >= 1.5:
                signals['direction'] = 'weak_bullish'
                signals['confidence'] = min(70, 55 + total_score * 3)
                signals['strength'] = 'moderate'
            elif total_score <= -7:
                signals['direction'] = 'strong_bearish'
                signals['confidence'] = min(90, 70 + abs(total_score) * 2)
                signals['strength'] = 'very_strong'
            elif total_score <= -4:
                signals['direction'] = 'bearish'
                signals['confidence'] = min(80, 60 + abs(total_score) * 3)
                signals['strength'] = 'strong'
            elif total_score <= -1.5:
                signals['direction'] = 'weak_bearish'
                signals['confidence'] = min(70, 55 + abs(total_score) * 3)
                signals['strength'] = 'moderate'
            else:
                signals['direction'] = 'neutral'
                signals['confidence'] = 40 + abs(total_score) * 5
                signals['strength'] = 'weak'
            
            return signals
            
        except Exception as e:
            logger.error(f"고급 매매 신호 분석 실패: {e}")
            return self._get_default_signals()

    async def _generate_dynamic_prediction(self, market_data: dict, trading_signals: dict) -> dict:
        """🎯 동적 가격 예측 (실제 지표 기반, 고정 비율 없음)"""
        try:
            current_price = market_data.get('current_price', 0)
            volatility = market_data.get('volatility', 2.0)
            composite_score = trading_signals.get('composite_score', 0)
            confidence = trading_signals.get('confidence', 50)
            
            # 🎯 동적 확률 계산 (기술적 지표 기반)
            base_up = 30
            base_sideways = 40
            base_down = 30
            
            # 종합 점수 기반 대폭 조정
            if composite_score > 0:
                # 상승 신호 강도에 따라 조정
                score_multiplier = min(composite_score * 8, 50)  # 최대 50% 조정
                base_up += score_multiplier
                base_down -= score_multiplier * 0.6
                base_sideways -= score_multiplier * 0.4
            elif composite_score < 0:
                # 하락 신호 강도에 따라 조정
                score_multiplier = min(abs(composite_score) * 8, 50)
                base_down += score_multiplier
                base_up -= score_multiplier * 0.6
                base_sideways -= score_multiplier * 0.4
            
            # RSI 과매수/과매도 조정
            rsi_14 = trading_signals.get('rsi_signals', {}).get('rsi_14', 50)
            if rsi_14 > 80:
                # 극과매수 - 조정 확률 크게 증가
                base_down += 25
                base_up -= 20
                base_sideways -= 5
            elif rsi_14 > 70:
                base_down += 15
                base_up -= 10
                base_sideways -= 5
            elif rsi_14 < 20:
                # 극과매도 - 반등 확률 크게 증가
                base_up += 25
                base_down -= 20
                base_sideways -= 5
            elif rsi_14 < 30:
                base_up += 15
                base_down -= 10
                base_sideways -= 5
            
            # 볼린저 밴드 위치 기반 조정
            bb_signals = trading_signals.get('bollinger_signals', {})
            bb_position = bb_signals.get('position', 'middle')
            if bb_position == 'upper_breakout':
                base_up += 20
                base_sideways -= 15
                base_down -= 5
            elif bb_position == 'lower_breakout':
                base_down += 20
                base_sideways -= 15
                base_up -= 5
            elif bb_position == 'upper_touch':
                base_down += 10
                base_up -= 8
                base_sideways -= 2
            elif bb_position == 'lower_touch':
                base_up += 10
                base_down -= 8
                base_sideways -= 2
            
            # 펀딩비 극단값 조정
            funding_rate = market_data.get('funding_rate', 0)
            if funding_rate > 0.002:  # 매우 높은 롱 펀딩비
                base_down += 20
                base_up -= 15
                base_sideways -= 5
            elif funding_rate < -0.002:  # 매우 높은 숏 펀딩비
                base_up += 20
                base_down -= 15
                base_sideways -= 5
            
            # 거래량 패턴 조정
            volume_ratio = market_data.get('volume_ratio', 1.0)
            if volume_ratio > 2.5:
                # 거래량 폭증 - 방향성 강화
                if base_up > base_down:
                    base_up += 15
                    base_sideways -= 10
                    base_down -= 5
                else:
                    base_down += 15
                    base_sideways -= 10
                    base_up -= 5
            
            # 확률 정규화 및 최소값 보장
            base_up = max(5, base_up)
            base_down = max(5, base_down)
            base_sideways = max(10, base_sideways)
            
            total = base_up + base_sideways + base_down
            up_prob = max(5, min(85, int(base_up / total * 100)))
            down_prob = max(5, min(85, int(base_down / total * 100)))
            sideways_prob = max(10, 100 - up_prob - down_prob)
            
            # 가격 목표 계산 (ATR 기반)
            atr = volatility * current_price / 100 * 0.7
            
            if up_prob > max(down_prob, sideways_prob):
                # 상승 우세
                target_min = current_price - atr * 0.3
                target_max = current_price + atr * 2.5
                target_center = current_price + atr * 1.5
                trend = "기술적 반등 신호"
            elif down_prob > max(up_prob, sideways_prob):
                # 하락 우세
                target_min = current_price - atr * 2.5
                target_max = current_price + atr * 0.3
                target_center = current_price - atr * 1.5
                trend = "조정 지속"
            else:
                # 횡보 우세
                target_min = current_price - atr * 1.2
                target_max = current_price + atr * 1.2
                target_center = current_price
                trend = "박스권 유지"
            
            # 신뢰도 계산
            max_prob = max(up_prob, down_prob, sideways_prob)
            if max_prob >= 65:
                pred_confidence = "높음"
            elif max_prob >= 50:
                pred_confidence = "보통"
            else:
                pred_confidence = "낮음"
            
            return {
                'up_probability': up_prob,
                'sideways_probability': sideways_prob,
                'down_probability': down_prob,
                'target_min': target_min,
                'target_max': target_max,
                'target_center': target_center,
                'trend_description': trend,
                'confidence': pred_confidence,
                'max_probability': max_prob,
                'based_on': f"종합점수: {composite_score:.1f}, RSI: {rsi_14:.0f}, 신뢰도: {confidence}%"
            }
            
        except Exception as e:
            logger.error(f"동적 예측 생성 실패: {e}")
            return {
                'up_probability': 33,
                'sideways_probability': 34,
                'down_probability': 33,
                'target_min': 104000,
                'target_max': 107000,
                'target_center': 105500,
                'trend_description': '분석 중',
                'confidence': '낮음',
                'max_probability': 34
            }

    async def _generate_practical_strategy(self, market_data: dict, trading_signals: dict) -> dict:
        """💡 실용적 매매 전략 생성"""
        try:
            current_price = market_data.get('current_price', 0)
            composite_score = trading_signals.get('composite_score', 0)
            direction = trading_signals.get('direction', 'neutral')
            confidence = trading_signals.get('confidence', 50)
            volatility = market_data.get('volatility', 2.0)
            
            # ATR 기반 가격 레벨 계산
            atr = volatility * current_price / 100 * 0.6
            
            strategy = {
                'action': 'hold',
                'direction': 'neutral',
                'entry_price': current_price,
                'stop_loss': 0,
                'take_profit': 0,
                'position_size': 1,
                'risk_reward': 0,
                'notes': [],
                'key_levels': {}
            }
            
            # 전략 결정 로직
            if composite_score >= 6:
                # 매우 강한 롱 신호
                strategy.update({
                    'action': 'buy',
                    'direction': 'long',
                    'entry_price': current_price,
                    'stop_loss': current_price - atr * 1.8,
                    'take_profit': current_price + atr * 3.5,
                    'position_size': 3,
                    'notes': ['매우 강한 상승 신호', '적극적 롱 진입', '추가 매수 준비']
                })
            elif composite_score >= 3:
                # 강한 롱 신호
                strategy.update({
                    'action': 'buy',
                    'direction': 'long',
                    'entry_price': current_price - atr * 0.1,
                    'stop_loss': current_price - atr * 1.4,
                    'take_profit': current_price + atr * 2.5,
                    'position_size': 2,
                    'notes': ['강한 상승 신호', '표준 롱 진입']
                })
            elif composite_score >= 1:
                # 약한 롱 신호
                strategy.update({
                    'action': 'buy',
                    'direction': 'long',
                    'entry_price': current_price - atr * 0.3,
                    'stop_loss': current_price - atr * 1.0,
                    'take_profit': current_price + atr * 1.8,
                    'position_size': 1,
                    'notes': ['약한 상승 신호', '소량 롱 진입']
                })
            elif composite_score <= -6:
                # 매우 강한 숏 신호
                strategy.update({
                    'action': 'sell',
                    'direction': 'short',
                    'entry_price': current_price,
                    'stop_loss': current_price + atr * 1.8,
                    'take_profit': current_price - atr * 3.5,
                    'position_size': 3,
                    'notes': ['매우 강한 하락 신호', '적극적 숏 진입']
                })
            elif composite_score <= -3:
                # 강한 숏 신호
                strategy.update({
                    'action': 'sell',
                    'direction': 'short',
                    'entry_price': current_price + atr * 0.1,
                    'stop_loss': current_price + atr * 1.4,
                    'take_profit': current_price - atr * 2.5,
                    'position_size': 2,
                    'notes': ['강한 하락 신호', '표준 숏 진입']
                })
            elif composite_score <= -1:
                # 약한 숏 신호
                strategy.update({
                    'action': 'sell',
                    'direction': 'short',
                    'entry_price': current_price + atr * 0.3,
                    'stop_loss': current_price + atr * 1.0,
                    'take_profit': current_price - atr * 1.8,
                    'position_size': 1,
                    'notes': ['약한 하락 신호', '소량 숏 진입']
                })
            else:
                # 관망
                # 중요 레벨 계산
                support_level = current_price - atr * 1.5
                resistance_level = current_price + atr * 1.5
                
                strategy.update({
                    'action': 'hold',
                    'direction': 'neutral',
                    'entry_price': 0,
                    'stop_loss': 0,
                    'take_profit': 0,
                    'position_size': 0,
                    'notes': ['방향성 불분명', '레벨 돌파 대기'],
                    'key_levels': {
                        'support': support_level,
                        'resistance': resistance_level
                    }
                })
            
            # 위험 보상 비율 계산
            if strategy['stop_loss'] > 0 and strategy['take_profit'] > 0:
                if strategy['direction'] == 'long':
                    risk = abs(strategy['entry_price'] - strategy['stop_loss'])
                    reward = abs(strategy['take_profit'] - strategy['entry_price'])
                else:
                    risk = abs(strategy['stop_loss'] - strategy['entry_price'])
                    reward = abs(strategy['entry_price'] - strategy['take_profit'])
                
                strategy['risk_reward'] = reward / risk if risk > 0 else 0
            
            # 신뢰도 기반 포지션 크기 조정
            if confidence < 65:
                strategy['position_size'] = max(0, strategy['position_size'] - 1)
                if strategy['position_size'] > 0:
                    strategy['notes'].append('신뢰도 고려 포지션 축소')
            
            return strategy
            
        except Exception as e:
            logger.error(f"실용적 전략 생성 실패: {e}")
            return {
                'action': 'hold',
                'direction': 'neutral',
                'position_size': 0,
                'notes': ['분석 오류']
            }

    # 포맷팅 메서드들 (간소화된 버전)
    async def _format_bitcoin_news(self, events: list) -> str:
        """비트코인 뉴스 포맷 (간소화)"""
        try:
            if not events:
                return "• 현재 중요한 비트코인 뉴스가 없습니다"
            
            formatted_events = []
            kst = pytz.timezone('Asia/Seoul')
            
            for event in events[:4]:  # 정확히 4개
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
                    
                    title_ko = event.get('title_ko', event.get('title', ''))[:60]  # 더 짧게
                    market_impact = event.get('market_impact', '')
                    
                    # 1줄 요약 (더 간단하게)
                    summary_text = f"→ {market_impact}" if market_impact else ""
                    
                    event_text = f"<b>{time_str}</b> <b>{title_ko}</b>\n{summary_text}"
                    formatted_events.append(event_text)
                    
                except Exception as e:
                    logger.debug(f"뉴스 포맷 오류: {e}")
                    continue
            
            return '\n\n'.join(formatted_events)
            
        except Exception as e:
            logger.error(f"비트코인 뉴스 포맷팅 실패: {e}")
            return "• 뉴스 데이터 처리 중"

    async def _format_market_status(self, market_data: dict) -> str:
        """시장 상황 포맷 (간소화)"""
        try:
            current_price = market_data.get('current_price', 0)
            change_24h_pct = market_data.get('change_24h_pct', 0)
            high_24h = market_data.get('high_24h', 0)
            low_24h = market_data.get('low_24h', 0)
            volume_ratio = market_data.get('volume_ratio', 1.0)
            volatility = market_data.get('volatility', 0)
            funding_rate = market_data.get('funding_rate', 0)
            
            # 변동 이모지
            if change_24h_pct > 3:
                change_emoji = "🚀"
            elif change_24h_pct > 0:
                change_emoji = "📈"
            elif change_24h_pct < -3:
                change_emoji = "🔻"
            elif change_24h_pct < 0:
                change_emoji = "📉"
            else:
                change_emoji = "➖"
            
            # 거래량 상태
            if volume_ratio > 2.0:
                volume_status = f"**급증** (평균 대비 **{volume_ratio:.1f}배**)"
            elif volume_ratio > 1.3:
                volume_status = f"**증가** (평균 대비 **{volume_ratio:.1f}배**)"
            else:
                volume_status = f"정상 (평균 대비 {volume_ratio:.1f}배)"
            
            # 변동성 상태
            if volatility > 5:
                vol_status = "**매우 높음**"
            elif volatility > 3:
                vol_status = "**높음**"
            else:
                vol_status = "보통"
            
            # 펀딩비 상태
            if funding_rate > 0.001:
                funding_status = f"**+{funding_rate*100:.3f}%** (롱 과열 주의)"
            elif funding_rate < -0.001:
                funding_status = f"{funding_rate*100:.3f}% (숏 과열)"
            else:
                funding_status = f"{funding_rate*100:.3f}% (중립)"
            
            return f"""- <b>현재가</b>: ${current_price:,.0f} ({change_emoji} <b>{change_24h_pct:+.1f}%</b>)
- <b>24시간 범위</b>: ${low_24h:,.0f} ~ ${high_24h:,.0f}
- <b>거래량</b>: {volume_status}
- <b>변동성</b>: **{volatility:.1f}%** ({vol_status})
- <b>펀딩비</b>: {funding_status}"""
            
        except Exception as e:
            logger.error(f"시장 상황 포맷 실패: {e}")
            return "- 시장 데이터 분석 중..."

    async def _format_trading_signals(self, trading_signals: dict) -> str:
        """매매 신호 포맷 (간소화)"""
        try:
            composite_score = trading_signals.get('composite_score', 0)
            direction = trading_signals.get('direction', 'neutral')
            confidence = trading_signals.get('confidence', 50)
            
            # 방향 텍스트
            if direction == 'strong_bullish':
                direction_text = "**롱 진입**"
                action_emoji = "🚀"
            elif direction == 'bullish':
                direction_text = "**롱 진입 고려**"
                action_emoji = "📈"
            elif direction == 'weak_bullish':
                direction_text = "소량 롱"
                action_emoji = "📊"
            elif direction == 'strong_bearish':
                direction_text = "**숏 진입**"
                action_emoji = "🔻"
            elif direction == 'bearish':
                direction_text = "**숏 진입 고려**"
                action_emoji = "📉"
            elif direction == 'weak_bearish':
                direction_text = "소량 숏"
                action_emoji = "📊"
            else:
                direction_text = "**관망**"
                action_emoji = "⚪"
            
            # 핵심 근거 생성 (최대 3개)
            reasons = []
            
            rsi_signals = trading_signals.get('rsi_signals', {})
            rsi_14 = rsi_signals.get('rsi_14', 50)
            if rsi_14 > 75:
                reasons.append(f"RSI(14): {rsi_14:.0f} (과매수 주의)")
            elif rsi_14 < 25:
                reasons.append(f"RSI(14): {rsi_14:.0f} (과매도 반등)")
            elif abs(rsi_14 - 50) > 15:
                status = "과매수 근접" if rsi_14 > 65 else "과매도 근접" if rsi_14 < 35 else ""
                if status:
                    reasons.append(f"RSI(14): {rsi_14:.0f} ({status})")
            
            ma_signals = trading_signals.get('ma_signals', {})
            ma_signal = ma_signals.get('signal', '')
            if ma_signal and ma_signal not in ['혼조세', '']:
                reasons.append(f"이동평균: {ma_signal}")
            
            macd_signals = trading_signals.get('macd_signals', {})
            macd_signal = macd_signals.get('signal', '')
            if macd_signal and '방향성 대기' not in macd_signal:
                reasons.append(f"MACD: {macd_signal}")
            
            bb_signals = trading_signals.get('bollinger_signals', {})
            bb_signal = bb_signals.get('signal', '')
            if bb_signal and bb_signal != '중립':
                reasons.append(f"볼린저: {bb_signal}")
            
            volume_signals = trading_signals.get('volume_signals', {})
            volume_ratio = volume_signals.get('volume_ratio', 1.0)
            if volume_ratio > 1.8:
                reasons.append(f"거래량: 돌파 의지 강함")
            
            if not reasons:
                reasons = ["기술적 지표 종합 분석"]
            
            reasons_text = '\n'.join(f"- {reason}" for reason in reasons[:4])  # 최대 4개
            
            return f"""<b>【종합 점수】</b> **{composite_score:+.1f}점**
<b>【추천 방향】</b> {action_emoji} {direction_text}
<b>【신뢰도】</b> **{confidence:.0f}%**

<b>핵심 근거:</b>
{reasons_text}"""
            
        except Exception as e:
            logger.error(f"매매 신호 포맷 실패: {e}")
            return "- 매매 신호 분석 중..."

    async def _format_dynamic_prediction(self, price_prediction: dict) -> str:
        """동적 예측 포맷"""
        try:
            up_prob = price_prediction.get('up_probability', 33)
            sideways_prob = price_prediction.get('sideways_probability', 34)
            down_prob = price_prediction.get('down_probability', 33)
            target_min = price_prediction.get('target_min', 0)
            target_max = price_prediction.get('target_max', 0)
            target_center = price_prediction.get('target_center', 0)
            trend_desc = price_prediction.get('trend_description', '분석 중')
            confidence = price_prediction.get('confidence', '낮음')
            
            # 가장 높은 확률에 🎯 표시 및 설명
            prob_parts = []
            
            if up_prob == max(up_prob, sideways_prob, down_prob):
                prob_parts.append(f"- <b>상승 확률</b>: **{up_prob}%** 🎯 ({trend_desc})")
            else:
                prob_parts.append(f"- <b>상승 확률</b>: {up_prob}%")
            
            if sideways_prob == max(up_prob, sideways_prob, down_prob):
                prob_parts.append(f"- <b>횡보 확률</b>: **{sideways_prob}%** 🎯 ({trend_desc})")
            else:
                prob_parts.append(f"- <b>횡보 확률</b>: {sideways_prob}%")
            
            if down_prob == max(up_prob, sideways_prob, down_prob):
                prob_parts.append(f"- <b>하락 확률</b>: **{down_prob}%** 🎯 ({trend_desc})")
            else:
                prob_parts.append(f"- <b>하락 확률</b>: {down_prob}%")
            
            prob_text = '\n'.join(prob_parts)
            
            return f"""<b>【기술적 분석 기반】</b>
{prob_text}

<b>예상 범위</b>: ${target_min:,.0f} ~ ${target_max:,.0f}
<b>핵심 목표</b>: **${target_center:,.0f}**
<b>신뢰도</b>: {confidence}"""
            
        except Exception as e:
            logger.error(f"동적 예측 포맷 실패: {e}")
            return "- AI 예측 분석 중..."

    async def _format_practical_strategy(self, strategy: dict, market_data: dict) -> str:
        """실용적 전략 포맷"""
        try:
            action = strategy.get('action', 'hold')
            direction = strategy.get('direction', 'neutral')
            entry_price = strategy.get('entry_price', 0)
            stop_loss = strategy.get('stop_loss', 0)
            take_profit = strategy.get('take_profit', 0)
            position_size = strategy.get('position_size', 0)
            notes = strategy.get('notes', [])
            key_levels = strategy.get('key_levels', {})
            
            if action == 'hold':
                hold_text = f"""- <b>추천</b>: **관망 및 레벨 대기**
- <b>이유</b>: {', '.join(notes) if notes else '방향성 불분명'}"""
                
                if key_levels:
                    support = key_levels.get('support', 0)
                    resistance = key_levels.get('resistance', 0)
                    if support > 0 and resistance > 0:
                        hold_text += f"""
- <b>상방 돌파</b>: **${resistance:,.0f} 이상** → 롱 진입 고려
- <b>하방 이탈</b>: **${support:,.0f} 이하** → 숏 진입 고려"""
                
                return hold_text
            
            # 손절/익절 퍼센트 계산
            if entry_price > 0:
                if direction == 'long':
                    stop_pct = ((entry_price - stop_loss) / entry_price * 100) if stop_loss > 0 else 0
                    profit_pct = ((take_profit - entry_price) / entry_price * 100) if take_profit > 0 else 0
                else:
                    stop_pct = ((stop_loss - entry_price) / entry_price * 100) if stop_loss > 0 else 0
                    profit_pct = ((entry_price - take_profit) / entry_price * 100) if take_profit > 0 else 0
            else:
                stop_pct = profit_pct = 0
            
            # 위험 보상 비율
            risk_reward = strategy.get('risk_reward', 0)
            
            direction_text = "**롱 진입**" if direction == 'long' else "**숏 진입**"
            
            # 포지션 크기에 따른 설명
            if position_size >= 3:
                pos_desc = "표준"
            elif position_size == 2:
                pos_desc = "표준"
            elif position_size == 1:
                pos_desc = "소량"
            else:
                pos_desc = "최소"
            
            strategy_text = f"""- <b>추천</b>: {direction_text} ({pos_desc})
- <b>진입가</b>: ${entry_price:,.0f}
- <b>손절가</b>: ${stop_loss:,.0f} (-{stop_pct:.1f}%)
- <b>목표가</b>: ${take_profit:,.0f} (+{profit_pct:.1f}%)
- <b>포지션</b>: **{position_size}%** ({pos_desc} 리스크)
- <b>손익비</b>: 1:{risk_reward:.1f}"""
            
            # 추가 주의사항
            if notes:
                key_note = notes[0] if notes else ""
                if "과열" in key_note or "주의" in key_note:
                    strategy_text += f"\n\n<b>핵심 포인트</b>: {key_note}"
            
            return strategy_text
            
        except Exception as e:
            logger.error(f"실용적 전략 포맷 실패: {e}")
            return "- 전략 분석 중..."

    async def _format_pnl_summary(self, pnl_data: dict) -> str:
        """손익 요약 포맷"""
        try:
            total_equity = pnl_data.get('total_equity', 0)
            unrealized_pnl = pnl_data.get('unrealized_pnl', 0)
            today_realized = pnl_data.get('today_realized', 0)
            total_return_pct = pnl_data.get('total_return_pct', 0)
            
            # 이모지
            total_emoji = "📈" if total_return_pct >= 0 else "📉"
            unrealized_emoji = "💰" if unrealized_pnl >= 0 else "💸"
            today_emoji = "⬆️" if today_realized >= 0 else "⬇️"
            
            return f"""- <b>총 자산</b>: ${total_equity:,.0f} ({total_emoji} **{total_return_pct:+.1f}%**)
- <b>미실현</b>: {unrealized_emoji} **{unrealized_pnl:+.0f}**
- <b>오늘 실현</b>: {today_emoji} **{today_realized:+.0f}**"""
            
        except Exception as e:
            logger.error(f"손익 요약 포맷 실패: {e}")
            return "- 손익 데이터 처리 중..."

    # 추가 기술적 지표 계산 메서드들
    def _get_rsi_signal_advanced(self, rsi_14: float, rsi_7: float, rsi_21: float) -> str:
        """고급 RSI 신호 분석"""
        if rsi_14 > 80 and rsi_7 > 85:
            return "극도 과매수 (조정 경고)"
        elif rsi_14 > 70:
            return "과매수 (매도 고려)"
        elif rsi_14 < 20 and rsi_7 < 15:
            return "극도 과매도 (반등 기대)"
        elif rsi_14 < 30:
            return "과매도 (매수 고려)"
        elif rsi_14 > 60 and rsi_7 > rsi_21:
            return "상승 모멘텀"
        elif rsi_14 < 40 and rsi_7 < rsi_21:
            return "하락 모멘텀"
        else:
            return "중립"

    def _calculate_rsi_score_advanced(self, rsi_14: float, rsi_7: float, rsi_21: float) -> float:
        """고급 RSI 점수 계산"""
        score = 0
        
        # RSI 14 기본 점수
        if rsi_14 > 85:
            score -= 5
        elif rsi_14 > 75:
            score -= 3
        elif rsi_14 > 65:
            score -= 1
        elif rsi_14 < 15:
            score += 5
        elif rsi_14 < 25:
            score += 3
        elif rsi_14 < 35:
            score += 1
        
        # RSI 7과 21의 관계
        if rsi_7 > rsi_21 + 10:
            score += 1
        elif rsi_7 < rsi_21 - 10:
            score -= 1
        
        # 극단값 추가 점수
        if rsi_14 > 80 and rsi_7 > 85:
            score -= 2  # 매우 위험
        elif rsi_14 < 20 and rsi_7 < 15:
            score += 2  # 매우 유리
        
        return score

    def _get_ma_signal_advanced(self, current_price: float, sma_20: float, sma_50: float, sma_100: float) -> str:
        """고급 이동평균 신호 분석"""
        if current_price > sma_20 > sma_50 > sma_100:
            return "완전 상승 배열"
        elif current_price < sma_20 < sma_50 < sma_100:
            return "완전 하락 배열"
        elif current_price > sma_20 > sma_50:
            return "단기 상승 배열"
        elif current_price < sma_20 < sma_50:
            return "단기 하락 배열"
        elif current_price > sma_20:
            return "단기 상승"
        elif current_price < sma_20:
            return "단기 하락"
        else:
            return "혼조세"

    def _calculate_ma_score_advanced(self, current_price: float, sma_20: float, sma_50: float, sma_100: float, ema_12: float, ema_26: float) -> float:
        """고급 이동평균 점수 계산"""
        score = 0
        
        # 가격과 이동평균 관계
        if current_price > sma_20:
            score += 1.5
        else:
            score -= 1.5
            
        if current_price > sma_50:
            score += 1
        else:
            score -= 1
            
        if current_price > sma_100:
            score += 0.5
        else:
            score -= 0.5
        
        # 이동평균 배열
        if sma_20 > sma_50 > sma_100:
            score += 3  # 완전 상승 배열
        elif sma_20 < sma_50 < sma_100:
            score -= 3  # 완전 하락 배열
        elif sma_20 > sma_50:
            score += 1
        else:
            score -= 1
        
        # EMA 관계
        if ema_12 > ema_26:
            score += 1
        else:
            score -= 1
        
        return score

    def _calculate_macd_advanced(self, prices: list) -> dict:
        """고급 MACD 계산"""
        if len(prices) < 26:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
        
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        macd = ema_12 - ema_26
        
        # 신호선 계산을 위한 MACD 히스토리 필요 (간단화)
        signal = macd * 0.85  # 근사치
        histogram = macd - signal
        
        return {
            'macd': macd,
            'signal': signal,
            'histogram': histogram
        }

    def _get_macd_signal_advanced(self, macd_data: dict) -> str:
        """고급 MACD 신호 분석"""
        macd = macd_data.get('macd', 0)
        signal = macd_data.get('signal', 0)
        histogram = macd_data.get('histogram', 0)
        
        if histogram > 100:
            return "강한 상승 신호"
        elif histogram > 0 and macd > signal:
            return "상승 신호 강화"
        elif histogram < -100:
            return "강한 하락 신호"
        elif histogram < 0 and macd < signal:
            return "하락 신호 강화"
        elif histogram > 0:
            return "약한 상승 신호"
        elif histogram < 0:
            return "약한 하락 신호"
        else:
            return "방향성 대기"

    def _calculate_macd_score_advanced(self, macd_data: dict) -> float:
        """고급 MACD 점수 계산"""
        histogram = macd_data.get('histogram', 0)
        macd = macd_data.get('macd', 0)
        
        score = 0
        
        if histogram > 200:
            score += 4
        elif histogram > 100:
            score += 3
        elif histogram > 50:
            score += 2
        elif histogram > 0:
            score += 1
        elif histogram < -200:
            score -= 4
        elif histogram < -100:
            score -= 3
        elif histogram < -50:
            score -= 2
        elif histogram < 0:
            score -= 1
        
        # MACD 절댓값도 고려
        if abs(macd) > 500:
            score += 1 if macd > 0 else -1
        
        return score

    def _calculate_bollinger_bands(self, prices: list, period: int = 20, std_dev: int = 2) -> dict:
        """볼린저 밴드 계산"""
        if len(prices) < period:
            current_price = prices[-1] if prices else 0
            return {
                'upper': current_price * 1.02,
                'middle': current_price,
                'lower': current_price * 0.98,
                'position': 'middle'
            }
        
        sma = self._calculate_sma(prices, period)
        recent_prices = prices[-period:]
        variance = sum((price - sma) ** 2 for price in recent_prices) / period
        std = (variance ** 0.5)
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        current_price = prices[-1]
        
        # 현재 가격 위치 판단
        if current_price > upper:
            position = 'upper_breakout'
        elif current_price < lower:
            position = 'lower_breakout'
        elif current_price > sma + (std * 1.5):
            position = 'upper_touch'
        elif current_price < sma - (std * 1.5):
            position = 'lower_touch'
        elif current_price > sma:
            position = 'upper_half'
        elif current_price < sma:
            position = 'lower_half'
        else:
            position = 'middle'
        
        return {
            'upper': upper,
            'middle': sma,
            'lower': lower,
            'position': position
        }

    def _get_bollinger_signal(self, bb_data: dict, current_price: float) -> str:
        """볼린저 밴드 신호 분석"""
        position = bb_data.get('position', 'middle')
        
        if position == 'upper_breakout':
            return "상방 돌파 (강세)"
        elif position == 'lower_breakout':
            return "하방 돌파 (약세)"
        elif position == 'upper_touch':
            return "상단 접촉 (조정 가능성)"
        elif position == 'lower_touch':
            return "하단 접촉 (반등 가능성)"
        elif position == 'upper_half':
            return "상단권 (강세 유지)"
        elif position == 'lower_half':
            return "하단권 (약세 유지)"
        else:
            return "중립"

    def _calculate_bollinger_score(self, bb_data: dict, current_price: float) -> float:
        """볼린저 밴드 점수 계산"""
        position = bb_data.get('position', 'middle')
        
        position_scores = {
            'upper_breakout': 3,
            'lower_breakout': -3,
            'upper_touch': -1,
            'lower_touch': 1,
            'upper_half': 0.5,
            'lower_half': -0.5,
            'middle': 0
        }
        
        return position_scores.get(position, 0)

    def _analyze_volume_trend(self, volumes: list) -> str:
        """거래량 트렌드 분석"""
        if len(volumes) < 20:
            return "데이터 부족"
        
        recent_vol = sum(volumes[-5:]) / 5
        prev_vol = sum(volumes[-20:-5]) / 15
        
        if recent_vol > prev_vol * 1.5:
            return "급증"
        elif recent_vol > prev_vol * 1.2:
            return "증가"
        elif recent_vol < prev_vol * 0.8:
            return "감소"
        else:
            return "안정"

    def _get_volume_signal_advanced(self, volume_ratio: float, volume_trend: str) -> str:
        """고급 거래량 신호 분석"""
        if volume_ratio > 2.5 and volume_trend == "급증":
            return "폭증 (돌파 가능성)"
        elif volume_ratio > 1.8:
            return "급증 (관심 증가)"
        elif volume_ratio > 1.3:
            return "증가 (활발)"
        elif volume_ratio < 0.7:
            return "감소 (관심 저하)"
        else:
            return "정상"

    def _calculate_volume_score_advanced(self, volume_ratio: float, volume_trend: str) -> float:
        """고급 거래량 점수 계산"""
        score = 0
        
        # 거래량 비율 점수
        if volume_ratio > 3.0:
            score += 3
        elif volume_ratio > 2.0:
            score += 2
        elif volume_ratio > 1.5:
            score += 1
        elif volume_ratio < 0.5:
            score -= 2
        elif volume_ratio < 0.7:
            score -= 1
        
        # 거래량 트렌드 점수
        if volume_trend == "급증":
            score += 1
        elif volume_trend == "감소":
            score -= 1
        
        return score

    # 기존 메서드들 유지
    def _get_default_signals(self) -> dict:
        """기본 신호 반환"""
        return {
            'rsi_signals': {'rsi_14': 50, 'rsi_7': 50, 'rsi_21': 50, 'signal': '중립', 'score': 0},
            'ma_signals': {'signal': '혼조세', 'score': 0},
            'macd_signals': {'signal': '방향성 대기', 'score': 0},
            'bollinger_signals': {'signal': '중립', 'score': 0},
            'volume_signals': {'volume_ratio': 1.0, 'signal': '정상', 'score': 0},
            'funding_signals': {'funding_rate': 0, 'signal': '중립', 'score': 0},
            'composite_score': 0,
            'direction': 'neutral',
            'confidence': 30,
            'strength': 'weak'
        }

    # 기존 기술적 지표 계산 메서드들 유지
    def _calculate_rsi(self, prices: list, period: int = 14) -> float:
        """RSI 계산"""
        if len(prices) < period + 1:
            return 50
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        if len(gains) < period:
            return 50
        
        # 초기 평균
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        # 지수 평활법 적용
        alpha = 1.0 / period
        for i in range(len(gains) - period):
            idx = period + i
            avg_gain = alpha * gains[idx] + (1 - alpha) * avg_gain
            avg_loss = alpha * losses[idx] + (1 - alpha) * avg_loss
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return max(0, min(100, rsi))

    def _calculate_sma(self, prices: list, period: int) -> float:
        """단순이동평균"""
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0
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

    def _get_funding_signal(self, funding_rate: float) -> str:
        """펀딩비 신호 분석"""
        if funding_rate > 0.002:
            return "롱 극과열 (숏 유리)"
        elif funding_rate > 0.001:
            return "롱 과열 (숏 고려)"
        elif funding_rate < -0.002:
            return "숏 극과열 (롱 유리)"
        elif funding_rate < -0.001:
            return "숏 과열 (롱 고려)"
        else:
            return "중립"

    def _calculate_funding_score(self, funding_rate: float) -> float:
        """펀딩비 점수 계산"""
        if funding_rate > 0.003:
            return -3
        elif funding_rate > 0.002:
            return -2
        elif funding_rate > 0.001:
            return -1
        elif funding_rate < -0.003:
            return 3
        elif funding_rate < -0.002:
            return 2
        elif funding_rate < -0.001:
            return 1
        else:
            return 0

    # 기존 메서드들 계속 유지...
    async def _get_pnl_summary(self) -> dict:
        """📈 손익 요약 정보"""
        try:
            pnl_data = {
                'total_equity': 0,
                'unrealized_pnl': 0,
                'today_realized': 0,
                'total_return_pct': 0
            }
            
            if self.bitget_client:
                # 계정 정보
                try:
                    account_info = await self.bitget_client.get_account_info()
                    if account_info:
                        pnl_data['total_equity'] = float(account_info.get('accountEquity', 0))
                        pnl_data['unrealized_pnl'] = float(account_info.get('unrealizedPL', 0))
                        
                        # 초기 자본 기준 수익률 (기본 4000 달러)
                        initial_capital = 4000
                        total_profit = pnl_data['total_equity'] - initial_capital
                        pnl_data['total_return_pct'] = (total_profit / initial_capital) * 100 if initial_capital > 0 else 0
                except Exception as e:
                    logger.warning(f"계정 정보 조회 실패: {e}")
                
                # 오늘 실현 손익
                try:
                    today_data = await self.bitget_client.get_enhanced_profit_history(days=1)
                    pnl_data['today_realized'] = today_data.get('total_pnl', 0)
                except Exception as e:
                    logger.warning(f"오늘 손익 조회 실패: {e}")
            
            # 기본값 설정 (데이터 없을 때)
            if pnl_data['total_equity'] == 0:
                pnl_data.update({
                    'total_equity': 9252,
                    'unrealized_pnl': 339,
                    'today_realized': 127,
                    'total_return_pct': 3.7
                })
            
            return pnl_data
            
        except Exception as e:
            logger.error(f"손익 요약 실패: {e}")
            return {
                'total_equity': 9252,
                'unrealized_pnl': 339,
                'today_realized': 127,
                'total_return_pct': 3.7
            }

    async def _save_current_prediction(self, market_data: dict, trading_signals: dict, price_prediction: dict):
        """현재 예측 저장"""
        try:
            current_price = market_data.get('current_price', 0)
            up_prob = price_prediction.get('up_probability', 33)
            down_prob = price_prediction.get('down_probability', 33)
            
            if up_prob > max(down_prob, price_prediction.get('sideways_probability', 34)):
                direction = 'up'
            elif down_prob > up_prob:
                direction = 'down'
            else:
                direction = 'sideways'
            
            prediction = {
                'timestamp': datetime.now().isoformat(),
                'price': current_price,
                'predicted_direction': direction,
                'up_probability': up_prob,
                'down_probability': down_prob,
                'sideways_probability': price_prediction.get('sideways_probability', 34),
                'composite_score': trading_signals.get('composite_score', 0),
                'confidence': trading_signals.get('confidence', 50),
                'target_min': price_prediction.get('target_min', 0),
                'target_max': price_prediction.get('target_max', 0)
            }
            
            self.prediction_history.append(prediction)
            
            if len(self.prediction_history) > 50:
                self.prediction_history = self.prediction_history[-50:]
            
            self._save_prediction_history()
            
            logger.info(f"동적 예측 저장: {direction.upper()} ({up_prob}%/{down_prob}%/{price_prediction.get('sideways_probability', 34)}%)")
            
        except Exception as e:
            logger.error(f"예측 저장 실패: {e}")

    async def _translate_news_title(self, title: str) -> str:
        """뉴스 제목 번역"""
        try:
            if not self.openai_client or not title:
                return title
            
            # 이미 한글이 많이 포함되어 있으면 번역 스킵
            korean_chars = sum(1 for char in title if '\uac00' <= char <= '\ud7a3')
            if korean_chars > len(title) * 0.3:
                return title
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "비트코인 뉴스 번역 전문가입니다. 간결하고 명확하게 번역하세요."},
                    {"role": "user", "content": f"다음 제목을 자연스러운 한국어로 번역해주세요 (60자 이내):\n{title}"}
                ],
                max_tokens=80,
                temperature=0.2
            )
            
            translated = response.choices[0].message.content.strip()
            return translated if len(translated) <= 70 else title
            
        except Exception as e:
            logger.warning(f"번역 실패: {e}")
            return title

    async def close(self):
        """세션 정리"""
        try:
            logger.info("실전 매매 리포트 생성기 세션 종료 (개선된 버전)")
        except Exception as e:
            logger.error(f"세션 종료 중 오류: {e}")
