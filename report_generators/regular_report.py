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
        
        logger.info("정기 리포트 생성기 초기화 완료")
    
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
        """정밀 분석 리포트 생성"""
        try:
            current_time = self._get_current_time_kst()
            
            logger.info("정기 리포트 생성 시작")
            
            # 1. 시장 데이터 수집
            market_data = await self._collect_market_data()
            indicators = await self._calculate_indicators()
            news_events = await self._collect_news_events()
            
            # 2. 리포트 섹션 생성
            events_section = await self._format_market_events(news_events)
            market_section = await self._format_market_status(market_data)
            indicators_section = await self._format_technical_analysis(indicators, market_data)
            signals_section = await self._format_trading_signals(indicators, market_data)
            strategy_section = await self._format_trading_strategy(indicators, market_data)
            prediction_section = await self._format_price_prediction(indicators, market_data)
            validation_section = await self._validate_predictions(market_data)
            pnl_section = await self._format_pnl()
            mental_section = await self._generate_mental_care(market_data, indicators)
            
            # 3. 현재 예측 저장
            await self._save_current_prediction(market_data, indicators)
            
            # 4. 최종 리포트
            report = f"""<b>🧾 비트코인 선물 정밀 분석 리포트</b>
<b>📅 {current_time}</b> | <b>🎯 종합 분석</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🚨 최근 중요 시장 이벤트</b>
{events_section}

<b>📊 현재 시장 상황</b>
{market_section}

<b>🔧 기술적 지표 분석</b>
{indicators_section}

<b>🎯 핵심 매매 신호</b>
{signals_section}

<b>💡 실전 매매 전략</b>
{strategy_section}

<b>🔮 AI 가격 예측 (12시간)</b>
{prediction_section}

<b>📈 이전 예측 검증</b>
{validation_section}

<b>💰 통합 손익 현황</b>
{pnl_section}

<b>🧠 오늘의 매매 조언</b>
{mental_section}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>⚡ 실시간 분석 완료</b> | 다음 업데이트: 4시간 후"""
            
            logger.info("정기 리포트 생성 완료")
            return report
            
        except Exception as e:
            logger.error(f"정기 리포트 생성 실패: {str(e)}")
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return f"❌ 리포트 생성 중 오류가 발생했습니다: {str(e)}"

    async def _collect_market_data(self) -> dict:
        """시장 데이터 수집"""
        try:
            market_data = {}
            
            if self.bitget_client:
                # 티커 정보
                ticker = await self.bitget_client.get_ticker('BTCUSDT')
                if ticker:
                    current_price = float(ticker.get('last', 0))
                    market_data.update({
                        'current_price': current_price,
                        'change_24h': float(ticker.get('changeUtc', 0)),
                        'high_24h': float(ticker.get('high24h', 0)),
                        'low_24h': float(ticker.get('low24h', 0)),
                        'volume_24h': float(ticker.get('baseVolume', 0)),
                        'quote_volume_24h': float(ticker.get('quoteVolume', 0))
                    })
                    logger.info(f"현재 BTC 가격: ${current_price:,.0f}")
                
                # K라인 데이터
                try:
                    klines_1h = await self.bitget_client.get_kline('BTCUSDT', '1H', 200)
                    klines_4h = await self.bitget_client.get_kline('BTCUSDT', '4H', 100)
                    klines_1d = await self.bitget_client.get_kline('BTCUSDT', '1D', 50)
                    
                    market_data.update({
                        'klines_1h': klines_1h,
                        'klines_4h': klines_4h,
                        'klines_1d': klines_1d
                    })
                except Exception as e:
                    logger.warning(f"K라인 데이터 수집 실패: {e}")
                
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
            
            # 기본값 설정
            if 'current_price' not in market_data or market_data['current_price'] == 0:
                market_data['current_price'] = 104000  # 기본값
                market_data['change_24h'] = 0
                market_data['high_24h'] = 106000
                market_data['low_24h'] = 102000
                market_data['volume_24h'] = 80000
                logger.warning("시장 데이터 수집 실패, 기본값 사용")
            
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
            
            self.market_cache = market_data
            return market_data
            
        except Exception as e:
            logger.error(f"시장 데이터 수집 실패: {e}")
            # 폴백 데이터 반환
            fallback_data = {
                'current_price': 104000,
                'change_24h': 0,
                'high_24h': 106000,
                'low_24h': 102000,
                'volume_24h': 80000,
                'volatility': 2.0,
                'funding_rate': 0,
                'open_interest': 0
            }
            self.market_cache = fallback_data
            return fallback_data

    async def _calculate_indicators(self) -> dict:
        """기술적 지표 계산"""
        try:
            indicators = {
                'trend_indicators': {},
                'momentum_indicators': {},
                'volatility_indicators': {},
                'volume_indicators': {},
                'composite_signals': {}
            }
            
            if not self.market_cache or not self.market_cache.get('klines_1h'):
                return self._get_default_indicators()
            
            klines_1h = self.market_cache.get('klines_1h', [])
            
            if not klines_1h:
                return self._get_default_indicators()
            
            closes_1h = [float(k[4]) for k in klines_1h[-200:]]
            highs_1h = [float(k[2]) for k in klines_1h[-200:]]
            lows_1h = [float(k[3]) for k in klines_1h[-200:]]
            volumes_1h = [float(k[5]) for k in klines_1h[-200:]]
            
            current_price = closes_1h[-1] if closes_1h else 0
            
            # 추세 지표
            indicators['trend_indicators'] = {
                'sma_20': self._calculate_sma(closes_1h, 20),
                'sma_50': self._calculate_sma(closes_1h, 50),
                'sma_100': self._calculate_sma(closes_1h, 100),
                'ema_12': self._calculate_ema(closes_1h, 12),
                'ema_26': self._calculate_ema(closes_1h, 26),
                'adx': self._calculate_adx(highs_1h, lows_1h, closes_1h),
                'trend_strength': self._analyze_trend_strength(closes_1h),
                'ma_alignment': self._analyze_ma_alignment(closes_1h, current_price)
            }
            
            # 모멘텀 지표
            indicators['momentum_indicators'] = {
                'rsi_14': self._calculate_rsi(closes_1h, 14),
                'rsi_7': self._calculate_rsi(closes_1h, 7),
                'macd': self._calculate_macd(closes_1h),
                'stoch_k': self._calculate_stochastic(highs_1h, lows_1h, closes_1h)[0],
                'stoch_d': self._calculate_stochastic(highs_1h, lows_1h, closes_1h)[1],
                'cci': self._calculate_cci(highs_1h, lows_1h, closes_1h),
                'williams_r': self._calculate_williams_r(highs_1h, lows_1h, closes_1h)
            }
            
            # 변동성 지표
            indicators['volatility_indicators'] = {
                'bollinger_bands': self._calculate_bollinger_bands(closes_1h),
                'atr': self._calculate_atr(highs_1h, lows_1h, closes_1h)
            }
            
            # 거래량 지표
            indicators['volume_indicators'] = {
                'volume_sma': self._calculate_sma(volumes_1h, 20),
                'volume_ratio': volumes_1h[-1] / self._calculate_sma(volumes_1h, 20) if volumes_1h and self._calculate_sma(volumes_1h, 20) > 0 else 1,
                'mfi': self._calculate_mfi(highs_1h, lows_1h, closes_1h, volumes_1h)
            }
            
            # 종합 신호
            indicators['composite_signals'] = self._calculate_composite_signals(indicators)
            
            self.indicators_cache = indicators
            return indicators
            
        except Exception as e:
            logger.error(f"지표 계산 실패: {e}")
            return self._get_default_indicators()

    def _get_default_indicators(self) -> dict:
        """기본 지표 반환"""
        return {
            'trend_indicators': {
                'sma_20': 0, 'sma_50': 0, 'sma_100': 0,
                'ema_12': 0, 'ema_26': 0,
                'adx': 25, 'trend_strength': 'weak', 'ma_alignment': 'neutral'
            },
            'momentum_indicators': {
                'rsi_14': 50, 'rsi_7': 50, 'macd': {'macd': 0, 'signal': 0, 'histogram': 0},
                'stoch_k': 50, 'stoch_d': 50, 'cci': 0, 'williams_r': -50
            },
            'volatility_indicators': {
                'bollinger_bands': {'upper': 0, 'middle': 0, 'lower': 0},
                'atr': 0
            },
            'volume_indicators': {
                'volume_sma': 0, 'volume_ratio': 1, 'mfi': 50
            },
            'composite_signals': {'total_score': 0, 'direction': 'neutral', 'strength': 'weak'}
        }

    async def _collect_news_events(self) -> list:
        """뉴스 이벤트 수집"""
        try:
            events = []
            
            if self.data_collector and hasattr(self.data_collector, 'get_recent_news'):
                try:
                    recent_news = await self.data_collector.get_recent_news(hours=6)
                    if recent_news:
                        # 번역 및 요약 처리
                        for news in recent_news[:5]:
                            # 제목 번역
                            if news.get('title') and not news.get('title_ko'):
                                news['title_ko'] = await self._translate_news_title(news['title'])
                            
                            # 요약 생성
                            if news.get('description') and len(news.get('description', '')) > 200:
                                news['summary'] = await self._summarize_news(news['title'], news['description'])
                            
                            events.append(news)
                        
                        logger.info(f"뉴스 수집 완료: {len(events)}개")
                except Exception as e:
                    logger.warning(f"뉴스 수집 실패: {e}")
            
            if not events:
                events = self._generate_default_events()
            
            self.news_cache = events
            return events
            
        except Exception as e:
            logger.error(f"뉴스 이벤트 수집 실패: {e}")
            return self.news_cache or []

    async def _translate_news_title(self, title: str) -> str:
        """뉴스 제목 번역"""
        try:
            if not self.openai_client:
                return title
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "비트코인 뉴스 전문 번역가입니다. 제목을 자연스러운 한국어로 번역하세요."},
                    {"role": "user", "content": f"다음 제목을 한국어로 번역해주세요: {title}"}
                ],
                max_tokens=100,
                temperature=0.2
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.warning(f"번역 실패: {e}")
            return title

    async def _summarize_news(self, title: str, description: str) -> str:
        """뉴스 요약"""
        try:
            if not self.openai_client:
                return ""
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "비트코인 투자 전문가입니다. 뉴스를 간결하게 요약하고 시장 영향을 분석하세요."},
                    {"role": "user", "content": f"제목: {title}\n내용: {description[:500]}\n\n이 뉴스를 2-3문장으로 요약하고 비트코인 가격에 미칠 영향을 분석해주세요."}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.warning(f"요약 실패: {e}")
            return ""

    def _generate_default_events(self) -> list:
        """기본 이벤트 생성"""
        current_time = datetime.now()
        return [
            {
                'title': '비트코인 시장 현황 분석',
                'title_ko': '비트코인 시장 현황 분석',
                'description': '현재 비트코인 시장의 기술적 지표와 거래량을 종합 분석',
                'source': '시장 분석',
                'published_at': current_time.isoformat(),
                'impact': '📊 중립적 분석',
                'weight': 5,
                'summary': '현재 시장은 횡보 구간에서 방향성을 찾고 있으며, 주요 지표들은 중립적 신호를 보이고 있다.'
            }
        ]

    async def _format_market_events(self, events: list) -> str:
        """시장 이벤트 포맷"""
        try:
            if not events:
                return "• 현재 주요 시장 이벤트가 포착되지 않았습니다\n• 안정적인 거래 환경이 유지되고 있습니다"
            
            formatted_events = []
            kst = pytz.timezone('Asia/Seoul')
            
            for event in events[:5]:
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
                    
                    title_ko = event.get('title_ko', event.get('title', ''))[:100]
                    summary = event.get('summary', '')
                    
                    # 제목을 굵게 표시
                    if summary:
                        event_text = f"<b>{time_str}</b> <b>{title_ko}</b>\n  └ {summary}"
                    else:
                        event_text = f"<b>{time_str}</b> <b>{title_ko}</b>"
                    
                    formatted_events.append(event_text)
                    
                except Exception as e:
                    logger.debug(f"이벤트 포맷 오류: {e}")
                    continue
            
            return '\n\n'.join(formatted_events)
            
        except Exception as e:
            logger.error(f"이벤트 포맷팅 실패: {e}")
            return "• 이벤트 데이터 처리 중입니다"

    async def _format_market_status(self, market_data: dict) -> str:
        """시장 상황 포맷"""
        try:
            current_price = market_data.get('current_price', 0)
            change_24h = market_data.get('change_24h', 0)
            volume_24h = market_data.get('volume_24h', 0)
            high_24h = market_data.get('high_24h', 0)
            low_24h = market_data.get('low_24h', 0)
            volatility = market_data.get('volatility', 0)
            funding_rate = market_data.get('funding_rate', 0)
            open_interest = market_data.get('open_interest', 0)
            
            # 변동성 상태
            if volatility > 5:
                vol_status = "🔴 매우 높음"
            elif volatility > 3:
                vol_status = "🟠 높음"
            elif volatility > 1.5:
                vol_status = "🟡 보통"
            else:
                vol_status = "🟢 낮음"
            
            # 24시간 범위 내 위치
            if high_24h != low_24h and current_price > 0:
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
            volume_ratio = volume_24h / avg_volume if volume_24h > 0 else 1
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
• 미결제약정: {open_interest:,.0f} USDT"""
            
        except Exception as e:
            logger.error(f"시장 상황 포맷 실패: {e}")
            return "• 시장 데이터 분석 중..."

    async def _format_technical_analysis(self, indicators: dict, market_data: dict) -> str:
        """기술적 분석 포맷"""
        try:
            if not indicators:
                return "• 기술적 지표 분석 중..."
            
            current_price = market_data.get('current_price', 0)
            analysis_sections = []
            
            # 추세 분석
            trend = indicators.get('trend_indicators', {})
            trend_analysis = []
            
            sma_20 = trend.get('sma_20', 0)
            sma_50 = trend.get('sma_50', 0)
            sma_100 = trend.get('sma_100', 0)
            
            if current_price and sma_20 and sma_50 and sma_100:
                if current_price > sma_20 > sma_50 > sma_100:
                    ma_signal = "🟢 완전한 상승 배열 (강력한 상승 추세)"
                elif current_price < sma_20 < sma_50 < sma_100:
                    ma_signal = "🔴 완전한 하락 배열 (강력한 하락 추세)"
                elif current_price > sma_20 > sma_50:
                    ma_signal = "🟡 단기 상승 추세"
                elif current_price < sma_20 < sma_50:
                    ma_signal = "🟠 단기 하락 추세"
                else:
                    ma_signal = "⚪ 혼조세 (방향성 불분명)"
                trend_analysis.append(f"이동평균: {ma_signal}")
            
            adx = trend.get('adx', 25)
            if adx > 40:
                adx_signal = f"🔥 매우 강한 추세 ({adx:.0f}) - 추세 지속 가능성 높음"
            elif adx > 25:
                adx_signal = f"📈 강한 추세 ({adx:.0f}) - 방향성 있음"
            else:
                adx_signal = f"📊 약한 추세 ({adx:.0f}) - 횡보 구간"
            trend_analysis.append(f"ADX: {adx_signal}")
            
            if trend_analysis:
                analysis_sections.append(f"<b>📈 추세 분석</b>\n" + "\n".join(f"  • {item}" for item in trend_analysis))
            
            # 모멘텀 분석
            momentum = indicators.get('momentum_indicators', {})
            momentum_analysis = []
            
            rsi_14 = momentum.get('rsi_14', 50)
            if rsi_14 > 80:
                rsi_signal = f"🔴 극도 과매수 ({rsi_14:.0f}) - 조정 압력 높음"
            elif rsi_14 > 70:
                rsi_signal = f"🟠 과매수 ({rsi_14:.0f}) - 상승 둔화 가능"
            elif rsi_14 < 20:
                rsi_signal = f"🟢 극도 과매도 ({rsi_14:.0f}) - 반등 기대"
            elif rsi_14 < 30:
                rsi_signal = f"🟡 과매도 ({rsi_14:.0f}) - 바닥 접근"
            else:
                rsi_signal = f"⚪ 중립 ({rsi_14:.0f}) - 관망"
            momentum_analysis.append(f"RSI(14): {rsi_signal}")
            
            macd_data = momentum.get('macd', {})
            if isinstance(macd_data, dict):
                macd_hist = macd_data.get('histogram', 0)
                if macd_hist > 100:
                    macd_signal = "🟢 강한 상승 신호 - 매수 모멘텀"
                elif macd_hist > 0:
                    macd_signal = "🟡 상승 신호 - 긍정적"
                elif macd_hist < -100:
                    macd_signal = "🔴 강한 하락 신호 - 매도 압력"
                elif macd_hist < 0:
                    macd_signal = "🟠 하락 신호 - 부정적"
                else:
                    macd_signal = "⚪ 중립 - 방향성 대기"
                momentum_analysis.append(f"MACD: {macd_signal}")
            
            if momentum_analysis:
                analysis_sections.append(f"<b>⚡ 모멘텀 분석</b>\n" + "\n".join(f"  • {item}" for item in momentum_analysis))
            
            # 종합 점수
            composite = indicators.get('composite_signals', {})
            total_score = composite.get('total_score', 0)
            direction = composite.get('direction', 'neutral')
            strength = composite.get('strength', 'weak')
            
            if total_score > 5:
                score_color = "🟢"
                score_text = f"강한 상승 신호 ({total_score:.1f}점)"
                market_outlook = "상승 모멘텀 강함 - 매수 우위"
            elif total_score > 2:
                score_color = "🟡"
                score_text = f"약한 상승 신호 ({total_score:.1f}점)"
                market_outlook = "상승 가능성 - 신중한 매수"
            elif total_score < -5:
                score_color = "🔴"
                score_text = f"강한 하락 신호 ({total_score:.1f}점)"
                market_outlook = "하락 모멘텀 강함 - 매도 우위"
            elif total_score < -2:
                score_color = "🟠"
                score_text = f"약한 하락 신호 ({total_score:.1f}점)"
                market_outlook = "하락 가능성 - 신중한 매도"
            else:
                score_color = "⚪"
                score_text = f"중립 ({total_score:.1f}점)"
                market_outlook = "방향성 불분명 - 관망 권장"
            
            analysis_sections.append(f"<b>🏆 종합 분석</b>\n  • 지표 종합: {score_color} <b>{score_text}</b>\n  • 시장 전망: <b>{market_outlook}</b>")
            
            return '\n\n'.join(analysis_sections)
            
        except Exception as e:
            logger.error(f"기술적 분석 포맷 실패: {e}")
            return "• 기술적 지표 분석 중..."

    async def _format_trading_signals(self, indicators: dict, market_data: dict) -> str:
        """매매 신호 포맷"""
        try:
            if not indicators:
                return "• 매매 신호 분석 중..."
            
            composite = indicators.get('composite_signals', {})
            total_score = composite.get('total_score', 0)
            confidence = self._calculate_signal_confidence(indicators)
            
            strength = min(max(int(abs(total_score)), 1), 10)
            strength_bar = "●" * strength + "○" * (10 - strength)
            
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
            
            reasons = self._extract_signal_reasons(indicators, market_data)
            reasons_text = '\n'.join(f"  • {reason}" for reason in reasons[:3])
            
            return f"""【강도】 {strength_bar} ({strength}/10)
【방향】 {signal_direction}
【신뢰도】 <b>{confidence:.0f}%</b>
【권장】 {color} <b>{action}</b>

<b>핵심 근거:</b>
{reasons_text}"""
            
        except Exception as e:
            logger.error(f"매매 신호 포맷 실패: {e}")
            return "• 매매 신호 분석 중..."

    def _calculate_signal_confidence(self, indicators: dict) -> float:
        """신호 신뢰도 계산"""
        try:
            confidence_factors = []
            
            trend = indicators.get('trend_indicators', {})
            ma_alignment = trend.get('ma_alignment', 'neutral')
            if ma_alignment in ['strong_bullish', 'strong_bearish']:
                confidence_factors.append(20)
            elif ma_alignment != 'neutral':
                confidence_factors.append(10)
            
            adx = trend.get('adx', 25)
            if adx > 40:
                confidence_factors.append(20)
            elif adx > 25:
                confidence_factors.append(10)
            
            momentum = indicators.get('momentum_indicators', {})
            rsi = momentum.get('rsi_14', 50)
            if rsi > 70 or rsi < 30:
                confidence_factors.append(15)
            
            volume = indicators.get('volume_indicators', {})
            volume_ratio = volume.get('volume_ratio', 1)
            if volume_ratio > 1.3:
                confidence_factors.append(15)
            
            composite = indicators.get('composite_signals', {})
            total_score = abs(composite.get('total_score', 0))
            if total_score > 5:
                confidence_factors.append(20)
            elif total_score > 2:
                confidence_factors.append(10)
            
            total_confidence = sum(confidence_factors)
            max_possible = 90
            confidence = (total_confidence / max_possible) * 100
            
            return min(max(confidence, 30), 95)
            
        except Exception as e:
            logger.error(f"신뢰도 계산 실패: {e}")
            return 50

    def _extract_signal_reasons(self, indicators: dict, market_data: dict) -> list:
        """신호 근거 추출"""
        reasons = []
        
        try:
            trend = indicators.get('trend_indicators', {})
            current_price = market_data.get('current_price', 0)
            sma_20 = trend.get('sma_20', 0)
            sma_50 = trend.get('sma_50', 0)
            
            if current_price and sma_20 and sma_50:
                if current_price > sma_20 > sma_50:
                    reasons.append("이동평균선 상승 배열")
                elif current_price < sma_20 < sma_50:
                    reasons.append("이동평균선 하락 배열")
            
            momentum = indicators.get('momentum_indicators', {})
            rsi = momentum.get('rsi_14', 50)
            if rsi > 75:
                reasons.append(f"RSI 극도과매수 ({rsi:.0f})")
            elif rsi < 25:
                reasons.append(f"RSI 극도과매도 ({rsi:.0f})")
            
            macd_data = momentum.get('macd', {})
            if isinstance(macd_data, dict):
                macd_hist = macd_data.get('histogram', 0)
                if abs(macd_hist) > 50:
                    direction = "상승" if macd_hist > 0 else "하락"
                    reasons.append(f"MACD 강한 {direction} 신호")
            
            volume = indicators.get('volume_indicators', {})
            volume_ratio = volume.get('volume_ratio', 1)
            if volume_ratio > 1.5:
                reasons.append(f"거래량 급증 ({volume_ratio:.1f}배)")
            
            volatility_val = market_data.get('volatility', 0)
            if volatility_val > 5:
                reasons.append(f"고변동성 ({volatility_val:.1f}%)")
            
            return reasons[:5]
            
        except Exception as e:
            logger.error(f"근거 추출 실패: {e}")
            return ["기술적 지표 종합 분석"]

    async def _format_trading_strategy(self, indicators: dict, market_data: dict) -> str:
        """매매 전략 포맷"""
        try:
            composite = indicators.get('composite_signals', {})
            total_score = composite.get('total_score', 0)
            current_price = market_data.get('current_price', 0)
            
            volatility_indicators = indicators.get('volatility_indicators', {})
            atr = volatility_indicators.get('atr', current_price * 0.015)
            if atr == 0:
                atr = current_price * 0.015
            
            if total_score >= 6:
                return self._format_aggressive_long_strategy(current_price, atr)
            elif total_score >= 3:
                return self._format_moderate_long_strategy(current_price, atr)
            elif total_score <= -6:
                return self._format_aggressive_short_strategy(current_price, atr)
            elif total_score <= -3:
                return self._format_moderate_short_strategy(current_price, atr)
            else:
                return self._format_neutral_strategy(current_price, atr)
            
        except Exception as e:
            logger.error(f"매매 전략 포맷 실패: {e}")
            return "• 전략 분석 중..."

    def _format_aggressive_long_strategy(self, current_price: float, atr: float) -> str:
        """적극적 롱 전략"""
        entry_price = current_price
        stop_loss = current_price - (atr * 1.5)
        target1 = current_price + (atr * 2.5)
        target2 = current_price + (atr * 4.0)
        
        risk_pct = ((entry_price - stop_loss) / entry_price) * 100
        
        return f"""• 전략: 🚀 <b>적극적 롱 진입</b>
- 진입: <b>즉시 ${entry_price:,.0f}</b>
- 손절: ${stop_loss:,.0f} ({risk_pct:.1f}% 리스크)
- 목표1: ${target1:,.0f}
- 목표2: ${target2:,.0f}
- 포지션: <b>표준 크기 (2-3%)</b>"""

    def _format_moderate_long_strategy(self, current_price: float, atr: float) -> str:
        """보통 롱 전략"""
        entry_price = current_price - (atr * 0.3)
        stop_loss = current_price - (atr * 1.2)
        target1 = current_price + (atr * 1.8)
        target2 = current_price + (atr * 3.0)
        
        risk_pct = ((entry_price - stop_loss) / entry_price) * 100
        
        return f"""• 전략: 📈 <b>롱 진입</b>
- 진입: ${entry_price:,.0f} (지정가 대기)
- 손절: ${stop_loss:,.0f} ({risk_pct:.1f}% 리스크)
- 목표1: ${target1:,.0f}
- 목표2: ${target2:,.0f}
- 포지션: <b>표준 크기 (1-2%)</b>"""

    def _format_aggressive_short_strategy(self, current_price: float, atr: float) -> str:
        """적극적 숏 전략"""
        entry_price = current_price
        stop_loss = current_price + (atr * 1.5)
        target1 = current_price - (atr * 2.5)
        target2 = current_price - (atr * 4.0)
        
        risk_pct = ((stop_loss - entry_price) / entry_price) * 100
        
        return f"""• 전략: 🔻 <b>적극적 숏 진입</b>
- 진입: <b>즉시 ${entry_price:,.0f}</b>
- 손절: ${stop_loss:,.0f} ({risk_pct:.1f}% 리스크)
- 목표1: ${target1:,.0f}
- 목표2: ${target2:,.0f}
- 포지션: <b>표준 크기 (2-3%)</b>"""

    def _format_moderate_short_strategy(self, current_price: float, atr: float) -> str:
        """보통 숏 전략"""
        entry_price = current_price + (atr * 0.3)
        stop_loss = current_price + (atr * 1.2)
        target1 = current_price - (atr * 1.8)
        target2 = current_price - (atr * 3.0)
        
        risk_pct = ((stop_loss - entry_price) / entry_price) * 100
        
        return f"""• 전략: 📉 <b>숏 진입</b>
- 진입: ${entry_price:,.0f} (지정가 대기)
- 손절: ${stop_loss:,.0f} ({risk_pct:.1f}% 리스크)
- 목표1: ${target1:,.0f}
- 목표2: ${target2:,.0f}
- 포지션: <b>표준 크기 (1-2%)</b>"""

    def _format_neutral_strategy(self, current_price: float, atr: float) -> str:
        """중립 전략"""
        support = current_price - (atr * 1.0)
        resistance = current_price + (atr * 1.0)
        
        return f"""• 전략: ⚪ <b>관망 및 레벨 대기</b>
- 현재가: ${current_price:,.0f}
- 상방 돌파: <b>${resistance:,.0f} 이상</b> → 롱 진입 고려
- 하방 이탈: <b>${support:,.0f} 이하</b> → 숏 진입 고려
- 권장: <b>명확한 돌파 신호 대기</b>"""

    async def _format_price_prediction(self, indicators: dict, market_data: dict) -> str:
        """가격 예측 포맷"""
        try:
            up_prob = 20
            sideways_prob = 60  
            down_prob = 20
            
            current_price = market_data.get('current_price', 0)
            
            composite = indicators.get('composite_signals', {})
            total_score = composite.get('total_score', 0)
            
            if total_score > 0:
                score_bonus = min(total_score * 10, 50)
                up_prob += score_bonus
                down_prob -= score_bonus * 0.8
                sideways_prob -= score_bonus * 0.2
            elif total_score < 0:
                score_bonus = min(abs(total_score) * 10, 50)
                down_prob += score_bonus
                up_prob -= score_bonus * 0.8
                sideways_prob -= score_bonus * 0.2
            
            momentum = indicators.get('momentum_indicators', {})
            rsi = momentum.get('rsi_14', 50)
            
            if rsi > 80:
                down_prob += 20
                up_prob -= 15
                sideways_prob -= 5
            elif rsi > 70:
                down_prob += 10
                up_prob -= 8
                sideways_prob -= 2
            elif rsi < 20:
                up_prob += 20
                down_prob -= 15
                sideways_prob -= 5
            elif rsi < 30:
                up_prob += 10
                down_prob -= 8
                sideways_prob -= 2
            
            up_prob = max(5, up_prob)
            down_prob = max(5, down_prob)
            sideways_prob = max(10, sideways_prob)
            
            total = up_prob + sideways_prob + down_prob
            up_prob = int(up_prob / total * 100)
            down_prob = int(down_prob / total * 100)
            sideways_prob = 100 - up_prob - down_prob
            
            volatility_indicators = indicators.get('volatility_indicators', {})
            atr = volatility_indicators.get('atr', current_price * 0.015)
            expected_move_12h = atr * 1.5
            
            if up_prob > down_prob + 20:
                min_price = current_price - expected_move_12h * 0.3
                max_price = current_price + expected_move_12h * 2.0
                center_price = current_price + expected_move_12h * 1.2
                trend = "상승 추세"
                emoji = "📈"
            elif down_prob > up_prob + 20:
                min_price = current_price - expected_move_12h * 2.0
                max_price = current_price + expected_move_12h * 0.3
                center_price = current_price - expected_move_12h * 1.2
                trend = "하락 추세"
                emoji = "📉"
            else:
                min_price = current_price - expected_move_12h * 0.8
                max_price = current_price + expected_move_12h * 0.8
                center_price = current_price
                trend = "박스권 횡보"
                emoji = "➡️"
            
            prob_display = []
            
            if up_prob >= 50:
                prob_display.append(f"▲ 상승 <b>{up_prob}%</b> 🎯")
            else:
                prob_display.append(f"▲ 상승 {up_prob}%")
            
            if sideways_prob >= 50:
                prob_display.append(f"━ 횡보 <b>{sideways_prob}%</b> 🎯")
            else:
                prob_display.append(f"━ 횡보 {sideways_prob}%")
            
            if down_prob >= 50:
                prob_display.append(f"▼ 하락 <b>{down_prob}%</b> 🎯")
            else:
                prob_display.append(f"▼ 하락 {down_prob}%")
            
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
→ 신뢰도: {confidence_text}"""
            
        except Exception as e:
            logger.error(f"가격 예측 실패: {e}")
            return "• AI 예측 분석 중..."

    async def _validate_predictions(self, market_data: dict) -> str:
        """예측 검증"""
        try:
            if not self.prediction_history:
                return "• 검증할 이전 예측이 없습니다\n• 첫 번째 예측을 생성하고 있습니다\n• 다음 검증: 12시간 후"
            
            current_time = datetime.now()
            current_price = market_data.get('current_price', 0)
            
            recent_validations = []
            total_predictions = 0
            correct_predictions = 0
            
            for pred in reversed(self.prediction_history[-10:]):
                try:
                    pred_time = datetime.fromisoformat(pred['timestamp'])
                    time_diff = current_time - pred_time
                    
                    if time_diff.total_seconds() >= 12 * 3600:
                        pred_price = pred.get('price', 0)
                        pred_direction = pred.get('predicted_direction', 'neutral')
                        
                        if pred_price > 0:
                            actual_change = ((current_price - pred_price) / pred_price) * 100
                            
                            direction_correct = False
                            if pred_direction == 'up' and actual_change > 1.0:
                                direction_correct = True
                            elif pred_direction == 'down' and actual_change < -1.0:
                                direction_correct = True
                            elif pred_direction == 'sideways' and abs(actual_change) <= 2.0:
                                direction_correct = True
                            
                            total_predictions += 1
                            if direction_correct:
                                correct_predictions += 1
                            
                            if len(recent_validations) < 3:
                                recent_validations.append({
                                    'time': pred_time.strftime('%m-%d %H:%M'),
                                    'direction': pred_direction.upper(),
                                    'actual_change': actual_change,
                                    'direction_correct': direction_correct
                                })
                
                except Exception as e:
                    logger.debug(f"예측 검증 오류: {e}")
                    continue
            
            if total_predictions == 0:
                return "• 검증 가능한 예측이 없습니다\n• 다음 검증: 12시간 후"
            
            accuracy_rate = (correct_predictions / total_predictions) * 100
            
            recent_results = []
            for val in recent_validations:
                result_emoji = "✅" if val['direction_correct'] else "❌"
                recent_results.append(
                    f"<b>{val['time']}</b>: {val['direction']} → {result_emoji} ({val['actual_change']:+.1f}%)"
                )
            
            recent_text = '\n'.join(recent_results) if recent_results else "• 최근 검증 결과 없음"
            
            if accuracy_rate >= 70:
                performance = "🥇 우수"
            elif accuracy_rate >= 60:
                performance = "🥈 양호"
            elif accuracy_rate >= 50:
                performance = "🥉 보통"
            else:
                performance = "🔴 개선 필요"
            
            return f"""• 총 검증: <b>{total_predictions}건</b> 중 <b>{correct_predictions}건</b> 적중
• 정확도: <b>{accuracy_rate:.1f}%</b> ({performance})

<b>최근 예측 결과:</b>
{recent_text}"""
            
        except Exception as e:
            logger.error(f"예측 검증 실패: {e}")
            return "• 예측 검증 시스템 오류"

    async def _save_current_prediction(self, market_data: dict, indicators: dict):
        """현재 예측 저장"""
        try:
            current_price = market_data.get('current_price', 0)
            composite = indicators.get('composite_signals', {})
            total_score = composite.get('total_score', 0)
            
            if total_score >= 3:
                direction = 'up'
            elif total_score <= -3:
                direction = 'down'
            else:
                direction = 'sideways'
            
            volatility_indicators = indicators.get('volatility_indicators', {})
            atr = volatility_indicators.get('atr', current_price * 0.015)
            
            if direction == 'up':
                pred_min = current_price - atr * 0.7
                pred_max = current_price + atr * 2.0
            elif direction == 'down':
                pred_min = current_price - atr * 2.0
                pred_max = current_price + atr * 0.7
            else:
                pred_min = current_price - atr * 1.0
                pred_max = current_price + atr * 1.0
            
            confidence = self._calculate_signal_confidence(indicators)
            
            prediction = {
                'timestamp': datetime.now().isoformat(),
                'price': current_price,
                'predicted_direction': direction,
                'predicted_min': pred_min,
                'predicted_max': pred_max,
                'score': total_score,
                'confidence': confidence
            }
            
            self.prediction_history.append(prediction)
            
            if len(self.prediction_history) > 50:
                self.prediction_history = self.prediction_history[-50:]
            
            self._save_prediction_history()
            
            logger.info(f"예측 저장: {direction.upper()} (점수: {total_score:.1f})")
            
        except Exception as e:
            logger.error(f"예측 저장 실패: {e}")

    async def _format_pnl(self) -> str:
        """손익 현황 포맷 - 수익 리포트와 통일"""
        try:
            if not self.bitget_client:
                return "• 손익 데이터를 불러올 수 없습니다"
            
            # 계정 정보
            account_info = await self.bitget_client.get_account_info()
            if not account_info:
                return "• 계정 정보 조회 실패"
            
            total_equity = float(account_info.get('accountEquity', 0))
            available_balance = float(account_info.get('available', 0))
            unrealized_pnl = float(account_info.get('unrealizedPL', 0))
            
            # 포지션 정보
            positions = await self.bitget_client.get_positions('BTCUSDT')
            
            position_info = "없음"
            position_size = 0
            
            if positions:
                for pos in positions:
                    size = float(pos.get('total', 0))
                    if size > 0:
                        position_size = size
                        side = pos.get('side', '')
                        entry_price = float(pos.get('averageOpenPrice', 0))
                        
                        if side == 'long':
                            position_info = f"롱 {size} BTC (진입: ${entry_price:,.0f})"
                        else:
                            position_info = f"숏 {size} BTC (진입: ${entry_price:,.0f})"
                        break
            
            # enhanced_profit_history 사용 (수익 리포트와 동일한 방식)
            weekly_pnl_data = await self.bitget_client.get_enhanced_profit_history(days=7)
            weekly_total = weekly_pnl_data.get('total_pnl', 0)
            daily_avg = weekly_pnl_data.get('average_daily', 0)
            
            today_pnl_data = await self.bitget_client.get_enhanced_profit_history(days=1)
            today_realized = today_pnl_data.get('total_pnl', 0)
            
            # 총 수익 계산 (초기 자본 4000 달러 기준)
            initial_capital = 4000
            total_profit = total_equity - initial_capital
            
            if total_equity > 0:
                total_return_pct = (total_profit / initial_capital) * 100
                weekly_return_pct = (weekly_total / initial_capital) * 100
            else:
                total_return_pct = 0
                weekly_return_pct = 0
            
            # 이모지
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
            return "• 손익 데이터 처리 중..."

    async def _generate_mental_care(self, market_data: dict, indicators: dict) -> str:
        """멘탈 케어 생성"""
        try:
            if not self.mental_care:
                return "오늘도 차분하게 시장을 분석하며 현명한 판단을 내리시길 바랍니다. 📊"
            
            # 계정 정보 조회
            account_info = {}
            position_info = {}
            today_pnl = 0
            weekly_profit = {'total': 0, 'average': 0}
            
            if self.bitget_client:
                try:
                    account_info = await self.bitget_client.get_account_info()
                    positions = await self.bitget_client.get_positions('BTCUSDT')
                    
                    if positions:
                        for pos in positions:
                            size = float(pos.get('total', 0))
                            if size > 0:
                                position_info = {'has_position': True}
                                break
                        else:
                            position_info = {'has_position': False}
                    else:
                        position_info = {'has_position': False}
                    
                    # 손익 데이터
                    today_data = await self.bitget_client.get_enhanced_profit_history(days=1)
                    today_pnl = today_data.get('total_pnl', 0)
                    
                    weekly_data = await self.bitget_client.get_enhanced_profit_history(days=7)
                    weekly_profit = {
                        'total': weekly_data.get('total_pnl', 0),
                        'average': weekly_data.get('average_daily', 0)
                    }
                    
                except Exception as e:
                    logger.warning(f"멘탈 케어용 데이터 수집 실패: {e}")
            
            # 멘탈 케어 생성
            mental_message = await self.mental_care.generate_profit_mental_care(
                account_info, position_info, today_pnl, weekly_profit
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

    # 기술적 지표 계산 메서드들
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
        signal = macd
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
        d = k
        
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
        """ADX 계산"""
        if len(closes) < period * 2:
            return 25
        
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
        
        adx = min((avg_range / current_price) * 10000, 100) if current_price > 0 else 25
        return max(adx, 0)

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
            
            # 추세 지표
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
            
            # ADX
            adx = trend.get('adx', 25)
            if adx > 40:
                trend_multiplier = 1.5
            elif adx > 25:
                trend_multiplier = 1.2
            else:
                trend_multiplier = 0.8
            
            # 모멘텀 지표
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
            
            # MACD
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
                total_score *= 1.2
            elif volume_ratio < 0.7:
                total_score *= 0.8
            
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

    async def close(self):
        """세션 정리"""
        try:
            logger.info("정기 리포트 생성기 세션 종료")
        except Exception as e:
            logger.error(f"세션 종료 중 오류: {e}")
