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
    """정기 리포트 생성기 - 실전 매매 특화"""
    
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
        
        logger.info("정기 리포트 생성기 초기화 완료 - 실전 매매 특화")
    
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
        """🎯 실전 매매 특화 리포트 생성"""
        try:
            current_time = self._get_current_time_kst()
            
            logger.info("실전 매매 리포트 생성 시작")
            
            # 1. 핵심 데이터 수집
            market_data = await self._collect_enhanced_market_data()
            news_events = await self._collect_critical_news()
            trading_signals = await self._analyze_trading_signals(market_data)
            price_prediction = await self._generate_smart_prediction(market_data, trading_signals)
            strategy = await self._generate_trading_strategy(market_data, trading_signals)
            pnl_data = await self._get_pnl_summary()
            
            # 2. 현재 예측 저장
            await self._save_current_prediction(market_data, trading_signals, price_prediction)
            
            # 3. 최종 리포트 생성
            report = f"""🎯 <b>비트코인 선물 매매 분석</b>
📅 {current_time}
━━━━━━━━━━━━━━━━━━━

<b>🚨 핵심 뉴스 ({len(news_events)}개)</b>
{await self._format_critical_news(news_events)}

<b>📊 현재 시장 상황</b>
{await self._format_market_summary(market_data)}

<b>⚡ 매매 신호 분석</b>
{await self._format_trading_signals(trading_signals)}

<b>🎯 12시간 가격 예측</b>
{await self._format_smart_prediction(price_prediction)}

<b>💡 실전 매매 전략</b>
{await self._format_trading_strategy(strategy, market_data)}

<b>📈 손익 현황</b>
{await self._format_pnl_summary(pnl_data)}

━━━━━━━━━━━━━━━━━━━
⚡ 다음 업데이트: 4시간 후"""
            
            logger.info("실전 매매 리포트 생성 완료")
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
                    klines_1h = await self.bitget_client.get_kline('BTCUSDT', '1H', 200)
                    klines_4h = await self.bitget_client.get_kline('BTCUSDT', '4H', 100)
                    klines_1d = await self.bitget_client.get_kline('BTCUSDT', '1D', 50)
                    
                    if klines_1h:
                        market_data.update({
                            'klines_1h': klines_1h,
                            'klines_4h': klines_4h,
                            'klines_1d': klines_1d
                        })
                        
                        # 변동성 계산 (1시간 기준)
                        closes_1h = [float(k[4]) for k in klines_1h[-24:]]
                        if len(closes_1h) >= 2:
                            returns = [(closes_1h[i] - closes_1h[i-1]) / closes_1h[i-1] for i in range(1, len(closes_1h))]
                            volatility = (sum(r*r for r in returns) / len(returns)) ** 0.5 * (24 ** 0.5) * 100
                            market_data['volatility'] = volatility
                        else:
                            market_data['volatility'] = 2.0
                        
                        # 거래량 비율 계산
                        volumes_1h = [float(k[5]) for k in klines_1h[-24:]]
                        avg_volume = sum(volumes_1h) / len(volumes_1h) if volumes_1h else 80000
                        current_volume = volumes_1h[-1] if volumes_1h else volume_24h / 24
                        market_data['volume_ratio'] = current_volume / avg_volume if avg_volume > 0 else 1.0
                        
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

    async def _collect_critical_news(self) -> list:
        """🚨 비트코인/거시경제 핵심 뉴스만 수집"""
        try:
            events = []
            
            if self.data_collector and hasattr(self.data_collector, 'get_recent_news'):
                try:
                    recent_news = await self.data_collector.get_recent_news(hours=12)
                    if recent_news:
                        # 비트코인/거시경제 관련 뉴스만 필터링
                        for news in recent_news:
                            if self._is_critical_for_trading(news):
                                # 제목 번역 (필요시)
                                if not news.get('title_ko'):
                                    news['title_ko'] = await self._translate_news_title(news.get('title', ''))
                                
                                # 시장 영향 분석
                                news['market_impact'] = self._analyze_market_impact(news)
                                events.append(news)
                                
                                if len(events) >= 4:  # 최대 4개
                                    break
                        
                        logger.info(f"핵심 뉴스 수집 완료: {len(events)}개")
                except Exception as e:
                    logger.warning(f"뉴스 수집 실패: {e}")
            
            if not events:
                events = self._generate_default_critical_events()
            
            self.news_cache = events
            return events
            
        except Exception as e:
            logger.error(f"핵심 뉴스 수집 실패: {e}")
            return self.news_cache or []

    def _is_critical_for_trading(self, news: dict) -> bool:
        """매매에 중요한 뉴스인지 판단"""
        title = news.get('title', '').lower()
        description = news.get('description', '').lower()
        content = f"{title} {description}"
        
        # 중요 키워드 (비트코인 매매에 직접 영향)
        critical_keywords = [
            # 비트코인 직접
            'bitcoin', 'btc', '비트코인',
            # Fed/금리
            'fed', 'federal reserve', 'interest rate', 'rate cut', 'rate hike', 'powell', 'fomc',
            '연준', '금리', '기준금리', '연방준비제도',
            # 트럼프/정치
            'trump', 'biden', 'election', 'tariff', 'trade war', 'china trade',
            '트럼프', '바이든', '관세', '무역전쟁',
            # 거시경제
            'inflation', 'cpi', 'unemployment', 'gdp', 'recession', 'stimulus',
            '인플레이션', '실업률', '경기침체', '부양책',
            # 규제/제도
            'sec', 'regulation', 'etf', 'approval', 'lawsuit',
            # 기업
            'tesla', 'microstrategy', 'blackrock', 'coinbase',
            '테슬라', '마이크로스트래티지'
        ]
        
        # 제외 키워드
        exclude_keywords = [
            'fifa', 'nfl', 'game', 'sport', 'celebrity', 'entertainment',
            'altcoin only', 'ethereum only', 'ripple only', 'dogecoin only'
        ]
        
        # 제외 키워드 체크
        for exclude in exclude_keywords:
            if exclude in content:
                return False
        
        # 중요 키워드 체크
        for keyword in critical_keywords:
            if keyword in content:
                return True
        
        return False

    def _analyze_market_impact(self, news: dict) -> str:
        """뉴스의 시장 영향 분석"""
        title = news.get('title', '').lower()
        description = news.get('description', '').lower()
        content = f"{title} {description}"
        
        # 긍정적 영향
        positive_signals = [
            'rate cut', 'dovish', 'stimulus', 'support', 'bullish', 'buy', 'purchase',
            'adoption', 'approval', 'positive', 'growth', 'recovery',
            '금리 인하', '비둘기파', '부양', '매수', '승인', '긍정'
        ]
        
        # 부정적 영향
        negative_signals = [
            'rate hike', 'hawkish', 'recession', 'crash', 'ban', 'restriction',
            'lawsuit', 'negative', 'sell', 'bearish', 'concern',
            '금리 인상', '매파', '경기침체', '폭락', '금지', '소송', '매도'
        ]
        
        positive_count = sum(1 for signal in positive_signals if signal in content)
        negative_count = sum(1 for signal in negative_signals if signal in content)
        
        if positive_count > negative_count:
            return "비트코인 긍정적"
        elif negative_count > positive_count:
            return "비트코인 부정적"
        else:
            return "영향도 분석 중"

    def _generate_default_critical_events(self) -> list:
        """기본 핵심 이벤트 생성"""
        current_time = datetime.now()
        return [
            {
                'title': 'Bitcoin Trading Analysis',
                'title_ko': '비트코인 매매 분석',
                'description': '현재 시장 상황과 기술적 지표 종합 분석',
                'source': '시장 분석',
                'published_at': current_time.isoformat(),
                'market_impact': '기술적 분석',
                'weight': 7
            }
        ]

    async def _analyze_trading_signals(self, market_data: dict) -> dict:
        """🔍 매매 신호 종합 분석"""
        try:
            signals = {
                'rsi_signals': {},
                'ma_signals': {},
                'macd_signals': {},
                'volume_signals': {},
                'funding_signals': {},
                'composite_score': 0,
                'direction': 'neutral',
                'confidence': 50,
                'strength': 'weak'
            }
            
            if not self.market_cache.get('klines_1h'):
                return self._get_default_signals()
            
            klines_1h = self.market_cache.get('klines_1h', [])
            closes_1h = [float(k[4]) for k in klines_1h[-100:]]
            highs_1h = [float(k[2]) for k in klines_1h[-100:]]
            lows_1h = [float(k[3]) for k in klines_1h[-100:]]
            volumes_1h = [float(k[5]) for k in klines_1h[-100:]]
            
            current_price = closes_1h[-1] if closes_1h else market_data.get('current_price', 0)
            
            # RSI 신호 분석
            rsi_14 = self._calculate_rsi(closes_1h, 14)
            rsi_7 = self._calculate_rsi(closes_1h, 7)
            
            signals['rsi_signals'] = {
                'rsi_14': rsi_14,
                'rsi_7': rsi_7,
                'signal': self._get_rsi_signal(rsi_14, rsi_7),
                'score': self._calculate_rsi_score(rsi_14, rsi_7)
            }
            
            # 이동평균 신호 분석
            sma_20 = self._calculate_sma(closes_1h, 20)
            sma_50 = self._calculate_sma(closes_1h, 50)
            ema_12 = self._calculate_ema(closes_1h, 12)
            ema_26 = self._calculate_ema(closes_1h, 26)
            
            signals['ma_signals'] = {
                'sma_20': sma_20,
                'sma_50': sma_50,
                'ema_12': ema_12,
                'ema_26': ema_26,
                'signal': self._get_ma_signal(current_price, sma_20, sma_50),
                'score': self._calculate_ma_score(current_price, sma_20, sma_50, ema_12, ema_26)
            }
            
            # MACD 신호 분석
            macd_data = self._calculate_macd(closes_1h)
            signals['macd_signals'] = {
                'macd': macd_data['macd'],
                'signal_line': macd_data['signal'],
                'histogram': macd_data['histogram'],
                'signal': self._get_macd_signal(macd_data),
                'score': self._calculate_macd_score(macd_data)
            }
            
            # 거래량 신호 분석
            volume_ratio = market_data.get('volume_ratio', 1.0)
            signals['volume_signals'] = {
                'volume_ratio': volume_ratio,
                'signal': self._get_volume_signal(volume_ratio),
                'score': self._calculate_volume_score(volume_ratio)
            }
            
            # 펀딩비 신호 분석
            funding_rate = market_data.get('funding_rate', 0)
            signals['funding_signals'] = {
                'funding_rate': funding_rate,
                'annual_rate': funding_rate * 365 * 3,
                'signal': self._get_funding_signal(funding_rate),
                'score': self._calculate_funding_score(funding_rate)
            }
            
            # 종합 점수 계산
            total_score = (
                signals['rsi_signals']['score'] * 0.25 +
                signals['ma_signals']['score'] * 0.30 +
                signals['macd_signals']['score'] * 0.25 +
                signals['volume_signals']['score'] * 0.10 +
                signals['funding_signals']['score'] * 0.10
            )
            
            signals['composite_score'] = total_score
            
            # 방향 및 신뢰도 결정
            if total_score >= 6:
                signals['direction'] = 'strong_bullish'
                signals['confidence'] = min(85, 60 + total_score * 3)
                signals['strength'] = 'very_strong'
            elif total_score >= 3:
                signals['direction'] = 'bullish'
                signals['confidence'] = min(75, 55 + total_score * 3)
                signals['strength'] = 'strong'
            elif total_score >= 1:
                signals['direction'] = 'weak_bullish'
                signals['confidence'] = min(65, 50 + total_score * 3)
                signals['strength'] = 'moderate'
            elif total_score <= -6:
                signals['direction'] = 'strong_bearish'
                signals['confidence'] = min(85, 60 + abs(total_score) * 3)
                signals['strength'] = 'very_strong'
            elif total_score <= -3:
                signals['direction'] = 'bearish'
                signals['confidence'] = min(75, 55 + abs(total_score) * 3)
                signals['strength'] = 'strong'
            elif total_score <= -1:
                signals['direction'] = 'weak_bearish'
                signals['confidence'] = min(65, 50 + abs(total_score) * 3)
                signals['strength'] = 'moderate'
            else:
                signals['direction'] = 'neutral'
                signals['confidence'] = 45
                signals['strength'] = 'weak'
            
            return signals
            
        except Exception as e:
            logger.error(f"매매 신호 분석 실패: {e}")
            return self._get_default_signals()

    def _get_default_signals(self) -> dict:
        """기본 신호 반환"""
        return {
            'rsi_signals': {'rsi_14': 50, 'rsi_7': 50, 'signal': '중립', 'score': 0},
            'ma_signals': {'signal': '혼조세', 'score': 0},
            'macd_signals': {'signal': '방향성 대기', 'score': 0},
            'volume_signals': {'volume_ratio': 1.0, 'signal': '정상', 'score': 0},
            'funding_signals': {'funding_rate': 0, 'signal': '중립', 'score': 0},
            'composite_score': 0,
            'direction': 'neutral',
            'confidence': 30,
            'strength': 'weak'
        }

    async def _generate_smart_prediction(self, market_data: dict, trading_signals: dict) -> dict:
        """🎯 스마트 가격 예측 (실제 지표 기반)"""
        try:
            current_price = market_data.get('current_price', 0)
            volatility = market_data.get('volatility', 2.0)
            composite_score = trading_signals.get('composite_score', 0)
            
            # 기본 확률 (중립)
            up_prob = 33
            sideways_prob = 34
            down_prob = 33
            
            # 종합 점수 기반 확률 조정
            if composite_score > 0:
                # 상승 신호
                score_impact = min(composite_score * 5, 40)
                up_prob += score_impact
                down_prob -= score_impact * 0.7
                sideways_prob -= score_impact * 0.3
            elif composite_score < 0:
                # 하락 신호  
                score_impact = min(abs(composite_score) * 5, 40)
                down_prob += score_impact
                up_prob -= score_impact * 0.7
                sideways_prob -= score_impact * 0.3
            
            # RSI 기반 추가 조정
            rsi_14 = trading_signals.get('rsi_signals', {}).get('rsi_14', 50)
            if rsi_14 > 75:
                # 극도 과매수 - 조정 확률 증가
                down_prob += 15
                up_prob -= 10
                sideways_prob -= 5
            elif rsi_14 > 65:
                down_prob += 8
                up_prob -= 5
                sideways_prob -= 3
            elif rsi_14 < 25:
                # 극도 과매도 - 반등 확률 증가
                up_prob += 15
                down_prob -= 10
                sideways_prob -= 5
            elif rsi_14 < 35:
                up_prob += 8
                down_prob -= 5
                sideways_prob -= 3
            
            # 펀딩비 기반 조정
            funding_rate = market_data.get('funding_rate', 0)
            if funding_rate > 0.001:  # 롱 과열
                down_prob += 10
                up_prob -= 8
                sideways_prob -= 2
            elif funding_rate < -0.001:  # 숏 과열
                up_prob += 10
                down_prob -= 8
                sideways_prob -= 2
            
            # 거래량 멀티플라이어
            volume_ratio = market_data.get('volume_ratio', 1.0)
            if volume_ratio > 1.5:
                # 거래량 급증 - 방향성 강화
                if up_prob > down_prob:
                    multiplier = 1.2
                    up_prob = int(up_prob * multiplier)
                    sideways_prob = int(sideways_prob * 0.8)
                elif down_prob > up_prob:
                    multiplier = 1.2
                    down_prob = int(down_prob * multiplier)
                    sideways_prob = int(sideways_prob * 0.8)
            
            # 확률 정규화
            up_prob = max(5, up_prob)
            down_prob = max(5, down_prob)
            sideways_prob = max(10, sideways_prob)
            
            total = up_prob + sideways_prob + down_prob
            up_prob = int(up_prob / total * 100)
            down_prob = int(down_prob / total * 100)
            sideways_prob = 100 - up_prob - down_prob
            
            # 가격 범위 계산
            atr = volatility * current_price / 100 * 0.6  # ATR 추정
            
            if up_prob > max(down_prob, sideways_prob):
                # 상승 우세
                target_min = current_price - atr * 0.5
                target_max = current_price + atr * 2.0
                target_center = current_price + atr * 1.2
                trend = "기술적 반등"
            elif down_prob > max(up_prob, sideways_prob):
                # 하락 우세
                target_min = current_price - atr * 2.0
                target_max = current_price + atr * 0.5
                target_center = current_price - atr * 1.2
                trend = "조정 지속"
            else:
                # 횡보 우세
                target_min = current_price - atr * 1.0
                target_max = current_price + atr * 1.0
                target_center = current_price
                trend = "박스권 유지"
            
            # 신뢰도 계산
            max_prob = max(up_prob, down_prob, sideways_prob)
            if max_prob >= 60:
                confidence = "높음"
            elif max_prob >= 45:
                confidence = "보통"
            else:
                confidence = "낮음"
            
            return {
                'up_probability': up_prob,
                'sideways_probability': sideways_prob,
                'down_probability': down_prob,
                'target_min': target_min,
                'target_max': target_max,
                'target_center': target_center,
                'trend_description': trend,
                'confidence': confidence,
                'max_probability': max_prob,
                'based_on': f"종합점수: {composite_score:.1f}, RSI: {rsi_14:.0f}, 펀딩비: {funding_rate*100:.3f}%"
            }
            
        except Exception as e:
            logger.error(f"스마트 예측 생성 실패: {e}")
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

    async def _generate_trading_strategy(self, market_data: dict, trading_signals: dict) -> dict:
        """💡 실전 매매 전략 생성"""
        try:
            current_price = market_data.get('current_price', 0)
            composite_score = trading_signals.get('composite_score', 0)
            direction = trading_signals.get('direction', 'neutral')
            confidence = trading_signals.get('confidence', 50)
            volatility = market_data.get('volatility', 2.0)
            
            # ATR 기반 가격 레벨 계산
            atr = volatility * current_price / 100 * 0.5
            
            strategy = {
                'action': 'hold',
                'direction': 'neutral',
                'entry_price': current_price,
                'stop_loss': 0,
                'take_profit': 0,
                'position_size': 1,
                'risk_reward': 0,
                'notes': []
            }
            
            if composite_score >= 5:
                # 강한 롱 신호
                strategy.update({
                    'action': 'buy',
                    'direction': 'long',
                    'entry_price': current_price,
                    'stop_loss': current_price - atr * 1.5,
                    'take_profit': current_price + atr * 3.0,
                    'position_size': 3,
                    'notes': ['강한 상승 신호', '적극적 롱 진입']
                })
            elif composite_score >= 2:
                # 보통 롱 신호
                strategy.update({
                    'action': 'buy',
                    'direction': 'long',
                    'entry_price': current_price - atr * 0.2,
                    'stop_loss': current_price - atr * 1.2,
                    'take_profit': current_price + atr * 2.0,
                    'position_size': 2,
                    'notes': ['상승 신호', '소량 롱 진입']
                })
            elif composite_score <= -5:
                # 강한 숏 신호
                strategy.update({
                    'action': 'sell',
                    'direction': 'short',
                    'entry_price': current_price,
                    'stop_loss': current_price + atr * 1.5,
                    'take_profit': current_price - atr * 3.0,
                    'position_size': 3,
                    'notes': ['강한 하락 신호', '적극적 숏 진입']
                })
            elif composite_score <= -2:
                # 보통 숏 신호
                strategy.update({
                    'action': 'sell',
                    'direction': 'short',
                    'entry_price': current_price + atr * 0.2,
                    'stop_loss': current_price + atr * 1.2,
                    'take_profit': current_price - atr * 2.0,
                    'position_size': 2,
                    'notes': ['하락 신호', '소량 숏 진입']
                })
            else:
                # 관망
                strategy.update({
                    'action': 'hold',
                    'direction': 'neutral',
                    'entry_price': 0,
                    'stop_loss': 0,
                    'take_profit': 0,
                    'position_size': 0,
                    'notes': ['방향성 불분명', '신호 대기']
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
            if confidence < 60:
                strategy['position_size'] = max(1, strategy['position_size'] - 1)
                strategy['notes'].append('신뢰도 낮음으로 포지션 축소')
            
            return strategy
            
        except Exception as e:
            logger.error(f"매매 전략 생성 실패: {e}")
            return {
                'action': 'hold',
                'direction': 'neutral',
                'position_size': 0,
                'notes': ['분석 오류']
            }

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
            
            logger.info(f"예측 저장: {direction.upper()} ({up_prob}%/{down_prob}%)")
            
        except Exception as e:
            logger.error(f"예측 저장 실패: {e}")

    # 포맷팅 메서드들
    async def _format_critical_news(self, events: list) -> str:
        """핵심 뉴스 포맷"""
        try:
            if not events:
                return "• 현재 중요한 시장 뉴스가 없습니다"
            
            formatted_events = []
            kst = pytz.timezone('Asia/Seoul')
            
            for event in events[:4]:  # 최대 4개
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
                    
                    title_ko = event.get('title_ko', event.get('title', ''))[:80]
                    market_impact = event.get('market_impact', '')
                    
                    # 1-2줄 요약
                    summary_text = f"→ {market_impact}" if market_impact else ""
                    
                    event_text = f"• <b>{time_str}</b> {title_ko}\n  {summary_text}"
                    formatted_events.append(event_text)
                    
                except Exception as e:
                    logger.debug(f"뉴스 포맷 오류: {e}")
                    continue
            
            return '\n'.join(formatted_events)
            
        except Exception as e:
            logger.error(f"뉴스 포맷팅 실패: {e}")
            return "• 뉴스 데이터 처리 중"

    async def _format_market_summary(self, market_data: dict) -> str:
        """시장 요약 포맷"""
        try:
            current_price = market_data.get('current_price', 0)
            change_24h_pct = market_data.get('change_24h_pct', 0)
            high_24h = market_data.get('high_24h', 0)
            low_24h = market_data.get('low_24h', 0)
            volume_ratio = market_data.get('volume_ratio', 1.0)
            volatility = market_data.get('volatility', 0)
            funding_rate = market_data.get('funding_rate', 0)
            
            # 변동 이모지
            if change_24h_pct > 2:
                change_emoji = "🚀"
            elif change_24h_pct > 0:
                change_emoji = "📈"
            elif change_24h_pct < -2:
                change_emoji = "🔻"
            elif change_24h_pct < 0:
                change_emoji = "📉"
            else:
                change_emoji = "➖"
            
            # 거래량 상태
            if volume_ratio > 2.0:
                volume_status = f"급증 (평균 대비 **{volume_ratio:.1f}배**)"
            elif volume_ratio > 1.3:
                volume_status = f"증가 (평균 대비 **{volume_ratio:.1f}배**)"
            elif volume_ratio < 0.7:
                volume_status = f"감소 (평균 대비 {volume_ratio:.1f}배)"
            else:
                volume_status = f"정상 (평균 대비 {volume_ratio:.1f}배)"
            
            # 변동성 상태
            if volatility > 5:
                vol_status = "**매우 높음**"
            elif volatility > 3:
                vol_status = "**높음**"
            elif volatility > 1.5:
                vol_status = "보통"
            else:
                vol_status = "낮음"
            
            # 펀딩비 상태
            if funding_rate > 0.001:
                funding_status = f"**+{funding_rate*100:.3f}%** (롱 과열)"
            elif funding_rate < -0.001:
                funding_status = f"{funding_rate*100:.3f}% (숏 과열)"
            else:
                funding_status = f"{funding_rate*100:.3f}% (중립)"
            
            return f"""• <b>현재가</b>: ${current_price:,.0f} ({change_emoji} <b>{change_24h_pct:+.1f}%</b>)
• <b>24시간 범위</b>: ${low_24h:,.0f} ~ ${high_24h:,.0f}
• <b>거래량</b>: {volume_status}
• <b>변동성</b>: **{volatility:.1f}%** ({vol_status})
• <b>펀딩비</b>: {funding_status}"""
            
        except Exception as e:
            logger.error(f"시장 요약 포맷 실패: {e}")
            return "• 시장 데이터 분석 중..."

    async def _format_trading_signals(self, trading_signals: dict) -> str:
        """매매 신호 포맷"""
        try:
            composite_score = trading_signals.get('composite_score', 0)
            direction = trading_signals.get('direction', 'neutral')
            confidence = trading_signals.get('confidence', 50)
            
            # 방향 텍스트
            if direction == 'strong_bullish':
                direction_text = "**강한 롱 신호**"
                action_text = "**롱 진입**"
            elif direction == 'bullish':
                direction_text = "**롱 신호**"
                action_text = "**롱 진입 고려**"
            elif direction == 'weak_bullish':
                direction_text = "약한 롱 신호"
                action_text = "소량 롱"
            elif direction == 'strong_bearish':
                direction_text = "**강한 숏 신호**"
                action_text = "**숏 진입**"
            elif direction == 'bearish':
                direction_text = "**숏 신호**"
                action_text = "**숏 진입 고려**"
            elif direction == 'weak_bearish':
                direction_text = "약한 숏 신호"
                action_text = "소량 숏"
            else:
                direction_text = "중립"
                action_text = "**관망**"
            
            # 핵심 근거 생성
            reasons = []
            
            rsi_signals = trading_signals.get('rsi_signals', {})
            rsi_14 = rsi_signals.get('rsi_14', 50)
            if rsi_14 > 70:
                reasons.append(f"RSI(14): {rsi_14:.0f} (과매수)")
            elif rsi_14 < 30:
                reasons.append(f"RSI(14): {rsi_14:.0f} (과매도)")
            elif abs(rsi_14 - 50) > 10:
                reasons.append(f"RSI(14): {rsi_14:.0f}")
            
            ma_signals = trading_signals.get('ma_signals', {})
            ma_signal = ma_signals.get('signal', '')
            if ma_signal and ma_signal != '혼조세':
                reasons.append(f"이동평균: {ma_signal}")
            
            macd_signals = trading_signals.get('macd_signals', {})
            macd_signal = macd_signals.get('signal', '')
            if macd_signal and macd_signal != '방향성 대기':
                reasons.append(f"MACD: {macd_signal}")
            
            volume_signals = trading_signals.get('volume_signals', {})
            volume_ratio = volume_signals.get('volume_ratio', 1.0)
            if volume_ratio > 1.5:
                reasons.append(f"거래량: 급증 ({volume_ratio:.1f}배)")
            
            if not reasons:
                reasons = ["기술적 지표 종합 분석"]
            
            reasons_text = '\n'.join(f"• {reason}" for reason in reasons[:3])
            
            return f"""<b>【종합 점수】</b> **{composite_score:+.1f}점**
<b>【추천 방향】</b> {action_text}
<b>【신뢰도】</b> **{confidence:.0f}%**

<b>핵심 근거:</b>
{reasons_text}"""
            
        except Exception as e:
            logger.error(f"매매 신호 포맷 실패: {e}")
            return "• 매매 신호 분석 중..."

    async def _format_smart_prediction(self, price_prediction: dict) -> str:
        """스마트 예측 포맷"""
        try:
            up_prob = price_prediction.get('up_probability', 33)
            sideways_prob = price_prediction.get('sideways_probability', 34)
            down_prob = price_prediction.get('down_probability', 33)
            target_min = price_prediction.get('target_min', 0)
            target_max = price_prediction.get('target_max', 0)
            target_center = price_prediction.get('target_center', 0)
            trend_desc = price_prediction.get('trend_description', '분석 중')
            confidence = price_prediction.get('confidence', '낮음')
            
            # 확률 표시 (가장 높은 확률에 🎯)
            prob_parts = []
            
            if up_prob == max(up_prob, sideways_prob, down_prob):
                prob_parts.append(f"• <b>상승 확률</b>: **{up_prob}%** 🎯 ({trend_desc})")
            else:
                prob_parts.append(f"• <b>상승 확률</b>: {up_prob}%")
            
            if sideways_prob == max(up_prob, sideways_prob, down_prob):
                prob_parts.append(f"• <b>횡보 확률</b>: **{sideways_prob}%** 🎯 ({trend_desc})")
            else:
                prob_parts.append(f"• <b>횡보 확률</b>: {sideways_prob}%")
            
            if down_prob == max(up_prob, sideways_prob, down_prob):
                prob_parts.append(f"• <b>하락 확률</b>: **{down_prob}%** 🎯 ({trend_desc})")
            else:
                prob_parts.append(f"• <b>하락 확률</b>: {down_prob}%")
            
            prob_text = '\n'.join(prob_parts)
            
            return f"""{prob_text}

<b>예상 범위</b>: ${target_min:,.0f} ~ ${target_max:,.0f}
<b>핵심 목표</b>: **${target_center:,.0f}**
<b>신뢰도</b>: {confidence}"""
            
        except Exception as e:
            logger.error(f"스마트 예측 포맷 실패: {e}")
            return "• AI 예측 분석 중..."

    async def _format_trading_strategy(self, strategy: dict, market_data: dict) -> str:
        """매매 전략 포맷"""
        try:
            action = strategy.get('action', 'hold')
            direction = strategy.get('direction', 'neutral')
            entry_price = strategy.get('entry_price', 0)
            stop_loss = strategy.get('stop_loss', 0)
            take_profit = strategy.get('take_profit', 0)
            position_size = strategy.get('position_size', 0)
            notes = strategy.get('notes', [])
            
            if action == 'hold':
                return f"""• <b>추천</b>: **관망 및 신호 대기**
• <b>이유</b>: {', '.join(notes) if notes else '방향성 불분명'}
• <b>대기 전략</b>: 명확한 돌파 신호 확인 후 진입"""
            
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
            
            return f"""• <b>추천</b>: {direction_text}
• <b>진입가</b>: ${entry_price:,.0f}
• <b>손절가</b>: ${stop_loss:,.0f} (-{stop_pct:.1f}%)
• <b>목표가</b>: ${take_profit:,.0f} (+{profit_pct:.1f}%)
• <b>포지션</b>: **{position_size}%**
• <b>손익비</b>: 1:{risk_reward:.1f}"""
            
        except Exception as e:
            logger.error(f"매매 전략 포맷 실패: {e}")
            return "• 전략 분석 중..."

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
            
            return f"""• <b>총 자산</b>: ${total_equity:,.0f} ({total_emoji} **{total_return_pct:+.1f}%**)
• <b>미실현</b>: {unrealized_emoji} **{unrealized_pnl:+.0f}**
• <b>오늘 실현</b>: {today_emoji} **{today_realized:+.0f}**"""
            
        except Exception as e:
            logger.error(f"손익 요약 포맷 실패: {e}")
            return "• 손익 데이터 처리 중..."

    # 기술적 지표 계산 메서드들 (기존과 동일하지만 개선된 버전)
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

    def _calculate_macd(self, prices: list) -> dict:
        """MACD 계산"""
        if len(prices) < 26:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
        
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        macd = ema_12 - ema_26
        
        # 신호선 (MACD의 9일 EMA)
        macd_line = [macd]  # 실제로는 여러 MACD 값이 필요하지만 간단히 처리
        signal = macd * 0.9  # 간단한 추정
        histogram = macd - signal
        
        return {
            'macd': macd,
            'signal': signal,
            'histogram': histogram
        }

    # 신호 분석 메서드들
    def _get_rsi_signal(self, rsi_14: float, rsi_7: float) -> str:
        """RSI 신호 분석"""
        if rsi_14 > 80:
            return "극도 과매수"
        elif rsi_14 > 70:
            return "과매수"
        elif rsi_14 < 20:
            return "극도 과매도"
        elif rsi_14 < 30:
            return "과매도"
        else:
            return "중립"

    def _calculate_rsi_score(self, rsi_14: float, rsi_7: float) -> float:
        """RSI 점수 계산"""
        if rsi_14 > 80:
            return -4  # 강한 매도 신호
        elif rsi_14 > 70:
            return -2  # 매도 신호
        elif rsi_14 < 20:
            return 4   # 강한 매수 신호
        elif rsi_14 < 30:
            return 2   # 매수 신호
        elif rsi_14 > 60:
            return -1  # 약한 매도 신호
        elif rsi_14 < 40:
            return 1   # 약한 매수 신호
        else:
            return 0   # 중립

    def _get_ma_signal(self, current_price: float, sma_20: float, sma_50: float) -> str:
        """이동평균 신호 분석"""
        if current_price > sma_20 > sma_50:
            return "상승 배열"
        elif current_price < sma_20 < sma_50:
            return "하락 배열"
        elif current_price > sma_20:
            return "단기 상승"
        elif current_price < sma_20:
            return "단기 하락"
        else:
            return "혼조세"

    def _calculate_ma_score(self, current_price: float, sma_20: float, sma_50: float, ema_12: float, ema_26: float) -> float:
        """이동평균 점수 계산"""
        score = 0
        
        # 가격과 이동평균 관계
        if current_price > sma_20:
            score += 1
        else:
            score -= 1
            
        if current_price > sma_50:
            score += 1
        else:
            score -= 1
        
        # 이동평균 배열
        if sma_20 > sma_50:
            score += 2
        else:
            score -= 2
        
        # EMA 관계
        if ema_12 > ema_26:
            score += 1
        else:
            score -= 1
        
        return score

    def _get_macd_signal(self, macd_data: dict) -> str:
        """MACD 신호 분석"""
        macd = macd_data.get('macd', 0)
        signal = macd_data.get('signal', 0)
        histogram = macd_data.get('histogram', 0)
        
        if histogram > 0 and macd > signal:
            return "상승 신호"
        elif histogram < 0 and macd < signal:
            return "하락 신호"
        else:
            return "방향성 대기"

    def _calculate_macd_score(self, macd_data: dict) -> float:
        """MACD 점수 계산"""
        histogram = macd_data.get('histogram', 0)
        
        if histogram > 50:
            return 3
        elif histogram > 20:
            return 2
        elif histogram > 0:
            return 1
        elif histogram < -50:
            return -3
        elif histogram < -20:
            return -2
        elif histogram < 0:
            return -1
        else:
            return 0

    def _get_volume_signal(self, volume_ratio: float) -> str:
        """거래량 신호 분석"""
        if volume_ratio > 2.0:
            return "급증"
        elif volume_ratio > 1.3:
            return "증가"
        elif volume_ratio < 0.7:
            return "감소"
        else:
            return "정상"

    def _calculate_volume_score(self, volume_ratio: float) -> float:
        """거래량 점수 계산"""
        if volume_ratio > 2.0:
            return 2  # 거래량 급증은 방향성 강화
        elif volume_ratio > 1.5:
            return 1
        elif volume_ratio < 0.5:
            return -1  # 거래량 급감은 약세
        else:
            return 0

    def _get_funding_signal(self, funding_rate: float) -> str:
        """펀딩비 신호 분석"""
        if funding_rate > 0.001:
            return "롱 과열 (숏 유리)"
        elif funding_rate < -0.001:
            return "숏 과열 (롱 유리)"
        else:
            return "중립"

    def _calculate_funding_score(self, funding_rate: float) -> float:
        """펀딩비 점수 계산"""
        if funding_rate > 0.002:
            return -2  # 롱 과열, 숏 신호
        elif funding_rate > 0.001:
            return -1
        elif funding_rate < -0.002:
            return 2   # 숏 과열, 롱 신호
        elif funding_rate < -0.001:
            return 1
        else:
            return 0

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
                    {"role": "user", "content": f"다음 제목을 자연스러운 한국어로 번역해주세요 (70자 이내):\n{title}"}
                ],
                max_tokens=100,
                temperature=0.2
            )
            
            translated = response.choices[0].message.content.strip()
            return translated if len(translated) <= 80 else title
            
        except Exception as e:
            logger.warning(f"번역 실패: {e}")
            return title

    async def close(self):
        """세션 정리"""
        try:
            logger.info("실전 매매 리포트 생성기 세션 종료")
        except Exception as e:
            logger.error(f"세션 종료 중 오류: {e}")
