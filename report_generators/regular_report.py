# report_generators/regular_report.py
from .base_generator import BaseReportGenerator
from .mental_care import MentalCareGenerator
import traceback
from datetime import datetime, timedelta
import json
import pytz
import os

class RegularReportGenerator(BaseReportGenerator):
    """정기 리포트 - 선물 롱/숏 판단 특화 (완전 개선)"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        self.mental_care = MentalCareGenerator(self.openai_client)
        self.last_prediction = None
        self.prediction_history_file = 'prediction_history.json'
        self._load_prediction_history()
        
        # 실시간 데이터 캐시
        self.market_cache = {}
        self.indicators_cache = {}
        self.news_cache = []
    
    def _load_prediction_history(self):
        """예측 기록 로드"""
        try:
            if os.path.exists(self.prediction_history_file):
                with open(self.prediction_history_file, 'r') as f:
                    self.prediction_history = json.load(f)
            else:
                self.prediction_history = []
        except Exception as e:
            self.logger.error(f"예측 기록 로드 실패: {e}")
            self.prediction_history = []
    
    def _save_prediction_history(self):
        """예측 기록 저장"""
        try:
            # 최근 100개만 유지
            if len(self.prediction_history) > 100:
                self.prediction_history = self.prediction_history[-100:]
            
            with open(self.prediction_history_file, 'w') as f:
                json.dump(self.prediction_history, f, indent=2)
        except Exception as e:
            self.logger.error(f"예측 기록 저장 실패: {e}")

    async def generate_report(self) -> str:
        """🧾 선물 롱/숏 판단 종합 리포트 (완전 개선)"""
        try:
            current_time = self._get_current_time_kst()
            
            # 1. 포괄적 데이터 수집
            self.logger.info("📊 시장 데이터 수집 시작")
            market_data = await self._collect_comprehensive_market_data()
            
            # 2. 전체 지표 계산 (20+ 지표)
            self.logger.info("🔧 20+ 지표 분석 시작")
            indicators = await self._calculate_all_technical_indicators(market_data)
            
            # 3. 뉴스 이벤트 수집
            self.logger.info("📰 뉴스 이벤트 수집")
            news_events = await self._collect_recent_market_events()
            
            # 4. 이전 예측 검증
            self.logger.info("✅ 이전 예측 검증")
            validation_result = await self._comprehensive_prediction_validation(market_data)
            
            # 5. 섹션별 생성
            events_text = await self._format_enhanced_market_events(news_events)
            market_summary = await self._format_detailed_market_summary(market_data)
            technical_analysis = await self._format_comprehensive_technical_analysis(indicators)
            signal_summary = await self._format_enhanced_signal_summary(indicators)
            strategy_text = await self._format_precision_trading_strategy(market_data, indicators)
            prediction_text = await self._format_advanced_ai_prediction(market_data, indicators)
            pnl_text = await self._format_integrated_pnl()
            mental_text = await self._generate_mental_care(market_data, indicators)
            
            # 6. 현재 예측 저장
            await self._save_detailed_prediction(market_data, indicators)
            
            # 7. 종합 리포트 생성
            report = f"""<b>🧾 비트코인 선물 정밀 분석 리포트</b>
<b>📅 {current_time}</b> | <b>🎯 20+ 지표 종합 분석</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📌 최근 중요 이벤트 (6시간)</b>
{events_text}

<b>📊 현재 시장 현황</b>
{market_summary}

<b>🔧 기술적 지표 종합 (20+ 지표)</b>
{technical_analysis}

<b>🎯 핵심 매매 신호</b>
{signal_summary}

<b>💡 정밀 매매 전략</b>
{strategy_text}

<b>🔮 AI 정밀 예측 (12시간)</b>
{prediction_text}

<b>📈 이전 예측 검증</b>
{validation_result}

<b>💰 통합 손익 현황</b>
{pnl_text}

<b>🧠 오늘의 한마디</b>
{mental_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>⚡ 실시간 분석 완료</b> | 다음 업데이트: 3시간 후"""
            
            self.logger.info("✅ 정기 리포트 생성 완료")
            return report
            
        except Exception as e:
            self.logger.error(f"정기 리포트 생성 실패: {str(e)}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            return f"❌ 리포트 생성 중 오류가 발생했습니다: {str(e)}"

    async def _collect_comprehensive_market_data(self) -> dict:
        """포괄적 시장 데이터 수집"""
        try:
            # 기본 시장 데이터
            market_data = await self._collect_all_data()
            
            # 추가 데이터 수집
            if self.data_collector:
                comprehensive_data = await self.data_collector.get_comprehensive_market_data()
                market_data.update(comprehensive_data)
            
            # Bitget 추가 데이터
            if self.bitget_client:
                # K라인 데이터 (여러 시간대)
                klines_1h = await self.bitget_client.get_kline('BTCUSDT', '1H', 200)
                klines_4h = await self.bitget_client.get_kline('BTCUSDT', '4H', 100)
                klines_1d = await self.bitget_client.get_kline('BTCUSDT', '1D', 50)
                
                market_data.update({
                    'klines_1h': klines_1h,
                    'klines_4h': klines_4h,
                    'klines_1d': klines_1d,
                    'total_indicators': 25
                })
            
            # 캐시 업데이트
            self.market_cache = market_data
            return market_data
            
        except Exception as e:
            self.logger.error(f"시장 데이터 수집 실패: {e}")
            return self.market_cache or {}

    async def _calculate_all_technical_indicators(self, market_data: dict) -> dict:
        """모든 기술적 지표 계산 (20+ 지표)"""
        try:
            # 기본 지표 시스템
            if self.bitget_client and hasattr(self.indicator_system, 'set_bitget_client'):
                self.indicator_system.set_bitget_client(self.bitget_client)
            
            indicators = await self.indicator_system.calculate_all_indicators(market_data)
            
            # 확장된 지표 계산
            extended_indicators = await self._calculate_extended_indicators(market_data)
            indicators['extended'] = extended_indicators
            
            # 종합 점수 계산
            composite_score = await self._calculate_composite_score(indicators, extended_indicators)
            indicators['composite_advanced'] = composite_score
            
            # 추가 분석
            market_structure = await self._analyze_market_structure(market_data)
            indicators['market_structure'] = market_structure
            
            # 캐시 업데이트
            self.indicators_cache = indicators
            return indicators
            
        except Exception as e:
            self.logger.error(f"지표 계산 실패: {e}")
            return self.indicators_cache or {}

    async def _collect_recent_market_events(self) -> list:
        """최근 시장 이벤트 수집 (강화)"""
        try:
            events = []
            
            # 뉴스 수집
            if self.data_collector:
                # 최근 12시간 뉴스
                recent_news = await self.data_collector.get_recent_news(hours=12)
                
                # 중요도별 필터링
                critical_news = []
                important_news = []
                
                for news in recent_news:
                    title = news.get('title', '').lower()
                    title_ko = news.get('title_ko', title)
                    weight = news.get('weight', 0)
                    
                    # 비트코인 직접 관련
                    bitcoin_keywords = ['bitcoin', 'btc', '비트코인', 'cryptocurrency', '암호화폐']
                    is_bitcoin_related = any(keyword in title for keyword in bitcoin_keywords)
                    
                    # 거시경제 관련
                    macro_keywords = ['fed', 'federal reserve', '연준', 'interest rate', '금리', 
                                    'inflation', '인플레이션', 'cpi', 'unemployment', 'gdp',
                                    'trump', 'tariff', '관세', 'trade war', '무역전쟁']
                    is_macro_related = any(keyword in title for keyword in macro_keywords)
                    
                    # 기업 관련
                    company_keywords = ['tesla', '테슬라', 'microstrategy', '마이크로스트래티지',
                                      'blackrock', '블랙록', 'sberbank', '스베르방크', 'etf']
                    is_company_related = any(keyword in title for keyword in company_keywords)
                    
                    if weight >= 9 or is_bitcoin_related or is_macro_related or is_company_related:
                        event = {
                            'title': title_ko,
                            'source': news.get('source', ''),
                            'weight': weight,
                            'impact': news.get('impact', '중립'),
                            'published': news.get('published_at', ''),
                            'type': 'critical' if weight >= 9 else 'important'
                        }
                        
                        if weight >= 9:
                            critical_news.append(event)
                        else:
                            important_news.append(event)
                
                # 정렬 및 제한
                critical_news.sort(key=lambda x: x['weight'], reverse=True)
                important_news.sort(key=lambda x: x['weight'], reverse=True)
                
                events = critical_news[:3] + important_news[:2]  # 최대 5개
            
            # 추가 이벤트 생성 (뉴스가 없는 경우)
            if not events:
                # 가격 변동 이벤트
                current_price = self.market_cache.get('current_price', 0)
                change_24h = self.market_cache.get('change_24h', 0)
                
                if abs(change_24h) > 0.03:  # 3% 이상 변동
                    direction = "급등" if change_24h > 0 else "급락"
                    events.append({
                        'title': f'비트코인 {direction} {abs(change_24h)*100:.1f}% (${current_price:,.0f})',
                        'source': '시장 데이터',
                        'weight': 8,
                        'impact': '강한 호재' if change_24h > 0 else '강한 악재',
                        'published': datetime.now().isoformat(),
                        'type': 'price_movement'
                    })
                
                # 거래량 이벤트
                volume_24h = self.market_cache.get('volume_24h', 0)
                if volume_24h > 150000:  # 15만 BTC 이상
                    events.append({
                        'title': f'비트코인 거래량 급증 ({volume_24h:,.0f} BTC)',
                        'source': '시장 데이터',
                        'weight': 7,
                        'impact': '변동성 증가',
                        'published': datetime.now().isoformat(),
                        'type': 'volume_spike'
                    })
                
                # 펀딩비 이벤트
                funding_rate = self.market_cache.get('funding_rate', 0)
                if abs(funding_rate) > 0.002:  # 0.2% 이상
                    direction = "과열" if funding_rate > 0 else "과매도"
                    events.append({
                        'title': f'선물 펀딩비 {direction} ({funding_rate*100:.3f}%)',
                        'source': '시장 데이터',
                        'weight': 6,
                        'impact': '조정 신호' if funding_rate > 0 else '반등 신호',
                        'published': datetime.now().isoformat(),
                        'type': 'funding_rate'
                    })
            
            # 캐시 업데이트
            self.news_cache = events
            return events
            
        except Exception as e:
            self.logger.error(f"이벤트 수집 실패: {e}")
            return self.news_cache or []

    async def _format_enhanced_market_events(self, events: list) -> str:
        """강화된 시장 이벤트 포맷"""
        try:
            if not events:
                return "• 중요 이벤트 없음 (최근 6시간)\n• 시장 안정세 유지"
            
            formatted_events = []
            kst = pytz.timezone('Asia/Seoul')
            
            for event in events[:4]:  # 최대 4개
                try:
                    # 시간 포맷
                    if event.get('published'):
                        pub_time_str = event['published']
                        if 'T' in pub_time_str:
                            pub_time = datetime.fromisoformat(pub_time_str.replace('Z', ''))
                        else:
                            pub_time = datetime.now()
                        
                        if pub_time.tzinfo is None:
                            pub_time = pytz.UTC.localize(pub_time)
                        
                        pub_time_kst = pub_time.astimezone(kst)
                        time_str = pub_time_kst.strftime('%m-%d %H:%M')
                    else:
                        time_str = datetime.now(kst).strftime('%m-%d %H:%M')
                    
                    # 영향도 이모지
                    impact = event.get('impact', '중립')
                    if '강한 호재' in impact or '상승' in impact:
                        impact_emoji = "🚀"
                    elif '강한 악재' in impact or '하락' in impact:
                        impact_emoji = "📉"
                    elif '호재' in impact:
                        impact_emoji = "📈"
                    elif '악재' in impact:
                        impact_emoji = "⚠️"
                    else:
                        impact_emoji = "ℹ️"
                    
                    # 가중치 표시
                    weight = event.get('weight', 5)
                    weight_stars = "⭐" * min(weight // 2, 5)
                    
                    title = event.get('title', '')[:80]
                    source = event.get('source', '')
                    
                    formatted_events.append(
                        f"{time_str} {impact_emoji} {title}\n  └ {impact} | {source} {weight_stars}"
                    )
                    
                except Exception as e:
                    self.logger.debug(f"이벤트 포맷 오류: {e}")
                    continue
            
            return '\n'.join(formatted_events)
            
        except Exception as e:
            self.logger.error(f"이벤트 포맷팅 실패: {e}")
            return "• 이벤트 데이터 처리 중"

    async def _format_detailed_market_summary(self, market_data: dict) -> str:
        """상세 시장 요약"""
        try:
            current_price = market_data.get('current_price', 0)
            change_24h = market_data.get('change_24h', 0)
            volume_24h = market_data.get('volume_24h', 0)
            volatility = market_data.get('volatility', 0)
            high_24h = market_data.get('high_24h', 0)
            low_24h = market_data.get('low_24h', 0)
            funding_rate = market_data.get('funding_rate', 0)
            
            # 변동성 분석
            if volatility > 5:
                vol_analysis = "매우 높음 🔴 (위험)"
            elif volatility > 3:
                vol_analysis = "높음 🟠 (주의)"
            elif volatility > 1.5:
                vol_analysis = "보통 🟡 (정상)"
            else:
                vol_analysis = "낮음 🟢 (안정)"
            
            # 24시간 범위 분석
            price_position = (current_price - low_24h) / (high_24h - low_24h) if high_24h != low_24h else 0.5
            if price_position > 0.8:
                position_text = "고점 근처 (저항 테스트)"
            elif price_position < 0.2:
                position_text = "저점 근처 (지지 테스트)"
            else:
                position_text = f"중간 구간 ({price_position*100:.0f}%)"
            
            # 거래량 분석
            avg_volume = 80000  # 평균 거래량 (BTC)
            volume_ratio = volume_24h / avg_volume
            if volume_ratio > 1.5:
                volume_analysis = f"급증 ({volume_ratio:.1f}배) 🔥"
            elif volume_ratio > 1.2:
                volume_analysis = f"증가 ({volume_ratio:.1f}배) ⬆️"
            elif volume_ratio < 0.8:
                volume_analysis = f"감소 ({volume_ratio:.1f}배) ⬇️"
            else:
                volume_analysis = "정상 📊"
            
            # 펀딩비 분석
            if funding_rate > 0.002:
                funding_analysis = f"과열 ({funding_rate*100:.3f}%) ⚠️"
            elif funding_rate > 0.001:
                funding_analysis = f"높음 ({funding_rate*100:.3f}%) 📈"
            elif funding_rate < -0.001:
                funding_analysis = f"저조 ({funding_rate*100:.3f}%) 📉"
            else:
                funding_analysis = f"중립 ({funding_rate*100:.3f}%) ➖"
            
            change_emoji = "🚀" if change_24h > 0.02 else "📈" if change_24h > 0 else "📉" if change_24h < -0.02 else "➖"
            
            return f"""• 현재가: <b>${current_price:,.0f}</b> {change_emoji} <b>({change_24h:+.2%})</b>
• 24H 범위: ${low_24h:,.0f} ~ ${high_24h:,.0f}
• 현재 위치: {position_text}
• 거래량: {volume_24h:,.0f} BTC ({volume_analysis})
• 변동성: {volatility:.1f}% ({vol_analysis})
• 펀딩비: {funding_analysis} (8시간)"""
            
        except Exception as e:
            self.logger.error(f"시장 요약 생성 실패: {e}")
            return "• 시장 데이터 분석 중..."

    async def _format_comprehensive_technical_analysis(self, indicators: dict) -> str:
        """종합 기술적 분석 (20+ 지표)"""
        try:
            extended = indicators.get('extended', {})
            technical = indicators.get('technical', {})
            
            # 주요 지표들
            analysis_sections = []
            
            # 1. 추세 지표들
            trend_indicators = []
            if 'ma_7' in extended and 'ma_25' in extended and 'ma_99' in extended:
                current_price = self.market_cache.get('current_price', 0)
                ma7, ma25, ma99 = extended['ma_7'], extended['ma_25'], extended['ma_99']
                
                if current_price > ma7 > ma25 > ma99:
                    trend_status = "🟢 강한 상승추세"
                elif current_price < ma7 < ma25 < ma99:
                    trend_status = "🔴 강한 하락추세"
                elif current_price > ma7 > ma25:
                    trend_status = "🟡 단기 상승추세"
                elif current_price < ma7 < ma25:
                    trend_status = "🟠 단기 하락추세"
                else:
                    trend_status = "⚪ 혼조세"
                
                trend_indicators.append(f"MA배열: {trend_status}")
            
            if 'adx' in extended:
                adx = extended['adx']
                if adx > 40:
                    trend_strength = "매우 강함"
                elif adx > 25:
                    trend_strength = "강함"
                elif adx > 15:
                    trend_strength = "보통"
                else:
                    trend_strength = "약함"
                trend_indicators.append(f"ADX: {adx:.1f} ({trend_strength})")
            
            if trend_indicators:
                analysis_sections.append("📈 <b>추세 분석</b>\n" + "\n".join(f"  • {ind}" for ind in trend_indicators))
            
            # 2. 모멘텀 지표들
            momentum_indicators = []
            
            # RSI
            rsi_data = technical.get('rsi', {})
            if rsi_data:
                rsi_value = rsi_data.get('value', 50)
                if rsi_value > 70:
                    rsi_status = f"🔴 과매수 ({rsi_value:.0f})"
                elif rsi_value < 30:
                    rsi_status = f"🟢 과매도 ({rsi_value:.0f})"
                else:
                    rsi_status = f"🟡 중립 ({rsi_value:.0f})"
                momentum_indicators.append(f"RSI: {rsi_status}")
            
            # MACD
            if 'macd' in extended and 'macd_signal' in extended:
                macd = extended['macd']
                macd_signal = extended['macd_signal']
                macd_hist = extended.get('macd_histogram', 0)
                
                if macd > macd_signal and macd_hist > 0:
                    macd_status = "🟢 상승신호"
                elif macd < macd_signal and macd_hist < 0:
                    macd_status = "🔴 하락신호"
                else:
                    macd_status = "🟡 중립"
                momentum_indicators.append(f"MACD: {macd_status}")
            
            # 스토캐스틱
            if 'stoch_k' in extended and 'stoch_d' in extended:
                stoch_k = extended['stoch_k']
                stoch_d = extended['stoch_d']
                
                if stoch_k < 20:
                    stoch_status = f"🟢 과매도 ({stoch_k:.0f})"
                elif stoch_k > 80:
                    stoch_status = f"🔴 과매수 ({stoch_k:.0f})"
                else:
                    stoch_status = f"🟡 중립 ({stoch_k:.0f})"
                momentum_indicators.append(f"Stoch: {stoch_status}")
            
            if momentum_indicators:
                analysis_sections.append("⚡ <b>모멘텀 분석</b>\n" + "\n".join(f"  • {ind}" for ind in momentum_indicators))
            
            # 3. 지지저항 분석
            support_resistance = []
            
            # 볼린저 밴드
            if 'bb_upper' in extended and 'bb_lower' in extended:
                current_price = self.market_cache.get('current_price', 0)
                bb_upper = extended['bb_upper']
                bb_lower = extended['bb_lower']
                bb_middle = extended.get('bb_middle', (bb_upper + bb_lower) / 2)
                
                bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
                
                if bb_position > 0.9:
                    bb_status = f"🔴 상단돌파 (${bb_upper:,.0f})"
                elif bb_position < 0.1:
                    bb_status = f"🟢 하단터치 (${bb_lower:,.0f})"
                else:
                    bb_status = f"🟡 중간대 (${bb_middle:,.0f})"
                
                support_resistance.append(f"볼밴: {bb_status}")
            
            # 피봇 포인트
            if 'pivot_points' in extended:
                pivot = extended['pivot_points']
                current_price = self.market_cache.get('current_price', 0)
                
                if current_price > pivot['r1']:
                    pivot_status = f"상방 (저항 ${pivot['r2']:,.0f})"
                elif current_price < pivot['s1']:
                    pivot_status = f"하방 (지지 ${pivot['s2']:,.0f})"
                else:
                    pivot_status = f"중립 (${pivot['pivot']:,.0f})"
                
                support_resistance.append(f"피봇: {pivot_status}")
            
            if support_resistance:
                analysis_sections.append("🎯 <b>지지저항</b>\n" + "\n".join(f"  • {ind}" for ind in support_resistance))
            
            # 4. 거래량 분석
            volume_indicators = []
            
            if 'obv' in extended:
                obv = extended['obv']
                if obv > 0:
                    obv_status = "🟢 매수우세"
                else:
                    obv_status = "🔴 매도우세"
                volume_indicators.append(f"OBV: {obv_status}")
            
            if 'mfi' in extended:
                mfi = extended['mfi']
                if mfi > 80:
                    mfi_status = f"🔴 과매수 ({mfi:.0f})"
                elif mfi < 20:
                    mfi_status = f"🟢 과매도 ({mfi:.0f})"
                else:
                    mfi_status = f"🟡 중립 ({mfi:.0f})"
                volume_indicators.append(f"MFI: {mfi_status}")
            
            if volume_indicators:
                analysis_sections.append("📊 <b>거래량 분석</b>\n" + "\n".join(f"  • {ind}" for ind in volume_indicators))
            
            # 5. 종합 점수
            composite_advanced = indicators.get('composite_advanced', {})
            total_score = composite_advanced.get('total_score', 0)
            bullish_count = composite_advanced.get('bullish_signals', 0)
            bearish_count = composite_advanced.get('bearish_signals', 0)
            neutral_count = composite_advanced.get('neutral_signals', 0)
            
            score_analysis = f"""🏆 <b>종합 점수</b>
  • 총점: <b>{total_score:+.1f}점</b> / 25개 지표
  • 상승신호: {bullish_count}개 🟢
  • 하락신호: {bearish_count}개 🔴  
  • 중립신호: {neutral_count}개 🟡"""
            
            analysis_sections.append(score_analysis)
            
            return '\n\n'.join(analysis_sections)
            
        except Exception as e:
            self.logger.error(f"기술적 분석 실패: {e}")
            return "• 기술적 지표 분석 중..."

    async def _format_enhanced_signal_summary(self, indicators: dict) -> str:
        """강화된 신호 요약"""
        try:
            composite_advanced = indicators.get('composite_advanced', {})
            total_score = composite_advanced.get('total_score', 0)
            confidence = composite_advanced.get('confidence', 50)
            
            # 신호 강도 계산 (10단계)
            strength = min(max(int(abs(total_score) / 2), 1), 10)
            strength_bar = "●" * strength + "○" * (10 - strength)
            
            # 방향성 및 색상
            if total_score >= 8:
                direction = "🚀 매우 강한 상승"
                action = "적극 매수"
                color = "🟢"
            elif total_score >= 5:
                direction = "📈 강한 상승"
                action = "매수"
                color = "🟢"
            elif total_score >= 2:
                direction = "🟡 약한 상승"
                action = "신중한 매수"
                color = "🟡"
            elif total_score <= -8:
                direction = "🔻 매우 강한 하락"
                action = "적극 매도/숏"
                color = "🔴"
            elif total_score <= -5:
                direction = "📉 강한 하락"
                action = "매도/숏"
                color = "🔴"
            elif total_score <= -2:
                direction = "🟠 약한 하락"
                action = "신중한 매도"
                color = "🟠"
            else:
                direction = "➖ 중립"
                action = "관망"
                color = "⚪"
            
            # 주요 근거
            reasons = []
            extended = indicators.get('extended', {})
            technical = indicators.get('technical', {})
            
            # RSI 근거
            rsi_data = technical.get('rsi', {})
            if rsi_data:
                rsi_value = rsi_data.get('value', 50)
                if rsi_value > 75:
                    reasons.append(f"RSI 극도과매수 ({rsi_value:.0f})")
                elif rsi_value < 25:
                    reasons.append(f"RSI 극도과매도 ({rsi_value:.0f})")
                elif rsi_value > 65:
                    reasons.append(f"RSI 과매수권 ({rsi_value:.0f})")
                elif rsi_value < 35:
                    reasons.append(f"RSI 과매도권 ({rsi_value:.0f})")
            
            # MACD 근거
            if 'macd_histogram' in extended:
                macd_hist = extended['macd_histogram']
                if macd_hist > 50:
                    reasons.append("MACD 강한 상승")
                elif macd_hist < -50:
                    reasons.append("MACD 강한 하락")
                elif macd_hist > 0:
                    reasons.append("MACD 상승신호")
                elif macd_hist < 0:
                    reasons.append("MACD 하락신호")
            
            # 이동평균 근거
            if all(k in extended for k in ['ma_7', 'ma_25', 'ma_99']):
                current_price = self.market_cache.get('current_price', 0)
                if current_price > extended['ma_7'] > extended['ma_25'] > extended['ma_99']:
                    reasons.append("완벽한 상승 이평 배열")
                elif current_price < extended['ma_7'] < extended['ma_25'] < extended['ma_99']:
                    reasons.append("완벽한 하락 이평 배열")
            
            # 거래량 근거
            if 'mfi' in extended:
                mfi = extended['mfi']
                if mfi > 80:
                    reasons.append(f"MFI 과매수 ({mfi:.0f})")
                elif mfi < 20:
                    reasons.append(f"MFI 과매도 ({mfi:.0f})")
            
            # 변동성 근거
            volatility = self.market_cache.get('volatility', 0)
            if volatility > 5:
                reasons.append(f"고변동성 ({volatility:.1f}%)")
            elif volatility < 1:
                reasons.append(f"저변동성 ({volatility:.1f}%)")
            
            reasons_text = '\n'.join(f"  • {reason}" for reason in reasons[:4])
            
            return f"""【강도】 {strength_bar} ({strength}/10)
【방향】 {direction}
【신뢰도】 <b>{confidence:.0f}%</b>
【권장】 {color} <b>{action}</b>

<b>핵심 근거:</b>
{reasons_text}"""
            
        except Exception as e:
            self.logger.error(f"신호 요약 실패: {e}")
            return "• 신호 분석 중..."

    async def _format_precision_trading_strategy(self, market_data: dict, indicators: dict) -> str:
        """정밀 매매 전략"""
        try:
            composite_advanced = indicators.get('composite_advanced', {})
            total_score = composite_advanced.get('total_score', 0)
            current_price = market_data.get('current_price', 0)
            volatility = market_data.get('volatility', 2)
            
            # ATR 기반 리스크 계산
            extended = indicators.get('extended', {})
            atr = extended.get('atr', current_price * 0.015)
            
            # 진입 전략
            if total_score >= 8:
                # 강한 상승 신호
                entry_strategy = "🚀 즉시 롱 진입"
                entry_price = current_price
                stop_loss = current_price - (atr * 1.5)
                target1 = current_price + (atr * 2)
                target2 = current_price + (atr * 3.5)
                target3 = current_price + (atr * 5)
                position_size = "표준 포지션 (2-3%)"
                
            elif total_score >= 5:
                # 상승 신호
                entry_strategy = "📈 롱 진입"
                entry_price = current_price - (atr * 0.3)
                stop_loss = current_price - (atr * 1.2)
                target1 = current_price + (atr * 1.5)
                target2 = current_price + (atr * 2.8)
                target3 = current_price + (atr * 4)
                position_size = "표준 포지션 (2%)"
                
            elif total_score >= 2:
                # 약한 상승 신호
                entry_strategy = "🟡 신중한 롱"
                entry_price = current_price - (atr * 0.5)
                stop_loss = current_price - (atr * 1)
                target1 = current_price + (atr * 1)
                target2 = current_price + (atr * 2)
                target3 = current_price + (atr * 3)
                position_size = "작은 포지션 (1%)"
                
            elif total_score <= -8:
                # 강한 하락 신호
                entry_strategy = "🔻 즉시 숏 진입"
                entry_price = current_price
                stop_loss = current_price + (atr * 1.5)
                target1 = current_price - (atr * 2)
                target2 = current_price - (atr * 3.5)
                target3 = current_price - (atr * 5)
                position_size = "표준 포지션 (2-3%)"
                
            elif total_score <= -5:
                # 하락 신호
                entry_strategy = "📉 숏 진입"
                entry_price = current_price + (atr * 0.3)
                stop_loss = current_price + (atr * 1.2)
                target1 = current_price - (atr * 1.5)
                target2 = current_price - (atr * 2.8)
                target3 = current_price - (atr * 4)
                position_size = "표준 포지션 (2%)"
                
            elif total_score <= -2:
                # 약한 하락 신호
                entry_strategy = "🟠 신중한 숏"
                entry_price = current_price + (atr * 0.5)
                stop_loss = current_price + (atr * 1)
                target1 = current_price - (atr * 1)
                target2 = current_price - (atr * 2)
                target3 = current_price - (atr * 3)
                position_size = "작은 포지션 (1%)"
                
            else:
                # 중립
                support = current_price - (atr * 1)
                resistance = current_price + (atr * 1)
                return f"""• 액션: ⚪ <b>관망 권장</b>
- 현재가: ${current_price:,.0f}
- 상방 돌파: ${resistance:,.0f} 이상 → 롱 고려
- 하방 이탈: ${support:,.0f} 이하 → 숏 고려
- 권장: 명확한 신호 대기"""
            
            # 리스크 계산
            risk_per_trade = abs(entry_price - stop_loss) / entry_price * 100
            reward_risk_1 = abs(target1 - entry_price) / abs(entry_price - stop_loss)
            reward_risk_2 = abs(target2 - entry_price) / abs(entry_price - stop_loss)
            
            # 추가 조건
            warnings = []
            
            # RSI 경고
            rsi_data = indicators.get('technical', {}).get('rsi', {})
            if rsi_data:
                rsi_value = rsi_data.get('value', 50)
                if total_score > 5 and rsi_value > 70:
                    warnings.append("⚠️ RSI 과매수 - 분할 진입 권장")
                elif total_score < -5 and rsi_value < 30:
                    warnings.append("⚠️ RSI 과매도 - 분할 진입 권장")
            
            # 변동성 경고
            if volatility > 4:
                warnings.append("⚠️ 고변동성 - 포지션 크기 축소")
            
            # 펀딩비 경고
            funding_rate = market_data.get('funding_rate', 0)
            if abs(funding_rate) > 0.002:
                direction = "롱" if total_score > 0 else "숏"
                if (funding_rate > 0.002 and total_score > 0) or (funding_rate < -0.002 and total_score < 0):
                    warnings.append(f"⚠️ 펀딩비 불리 - {direction} 비용 증가")
            
            warnings_text = '\n' + '\n'.join(warnings) if warnings else ""
            
            return f"""• 액션: <b>{entry_strategy}</b>
- 진입: ${entry_price:,.0f}
- 손절: ${stop_loss:,.0f} ({risk_per_trade:.1f}% 리스크)
- 1차: ${target1:,.0f} (R/R {reward_risk_1:.1f}:1)
- 2차: ${target2:,.0f} (R/R {reward_risk_2:.1f}:1)
- 3차: ${target3:,.0f}
- 크기: {position_size}{warnings_text}"""
            
        except Exception as e:
            self.logger.error(f"전략 생성 실패: {e}")
            return "• 전략 분석 중..."

    async def _format_advanced_ai_prediction(self, market_data: dict, indicators: dict) -> str:
        """고급 AI 예측 (확률 정교화)"""
        try:
            # 기본 확률 (더 극단적으로 시작)
            up_prob = 25
            sideways_prob = 50  
            down_prob = 25
            
            current_price = market_data.get('current_price', 0)
            extended = indicators.get('extended', {})
            technical = indicators.get('technical', {})
            composite_advanced = indicators.get('composite_advanced', {})
            
            # 1. 종합 점수 기반 대폭 조정
            total_score = composite_advanced.get('total_score', 0)
            if total_score > 0:
                up_bonus = min(total_score * 12, 50)  # 더 큰 가중치
                up_prob += up_bonus
                down_prob -= up_bonus * 0.7
                sideways_prob -= up_bonus * 0.3
            elif total_score < 0:
                down_bonus = min(abs(total_score) * 12, 50)
                down_prob += down_bonus
                up_prob -= down_bonus * 0.7
                sideways_prob -= down_bonus * 0.3
            
            # 2. RSI 강화 조정
            rsi_data = technical.get('rsi', {})
            if rsi_data:
                rsi_value = rsi_data.get('value', 50)
                if rsi_value > 80:
                    down_prob += 20
                    up_prob -= 15
                    sideways_prob -= 5
                elif rsi_value > 70:
                    down_prob += 12
                    up_prob -= 8
                    sideways_prob -= 4
                elif rsi_value < 20:
                    up_prob += 20
                    down_prob -= 15
                    sideways_prob -= 5
                elif rsi_value < 30:
                    up_prob += 12
                    down_prob -= 8
                    sideways_prob -= 4
            
            # 3. MACD 신호 강화
            if 'macd_histogram' in extended:
                macd_hist = extended['macd_histogram']
                if macd_hist > 100:
                    up_prob += 15
                    down_prob -= 15
                elif macd_hist > 0:
                    up_prob += 8
                    down_prob -= 8
                elif macd_hist < -100:
                    down_prob += 15
                    up_prob -= 15
                elif macd_hist < 0:
                    down_prob += 8
                    up_prob -= 8
            
            # 4. 이동평균 배열 강화
            if all(k in extended for k in ['ma_7', 'ma_25', 'ma_99']):
                ma7, ma25, ma99 = extended['ma_7'], extended['ma_25'], extended['ma_99']
                if current_price > ma7 > ma25 > ma99:
                    up_prob += 18  # 완벽한 상승 배열
                    down_prob -= 18
                elif current_price < ma7 < ma25 < ma99:
                    down_prob += 18  # 완벽한 하락 배열
                    up_prob -= 18
                elif current_price > ma7 > ma25:
                    up_prob += 10
                    down_prob -= 10
                elif current_price < ma7 < ma25:
                    down_prob += 10
                    up_prob -= 10
            
            # 5. 거래량 분석 강화
            if 'mfi' in extended:
                mfi = extended['mfi']
                if mfi > 85:
                    down_prob += 15
                    up_prob -= 10
                    sideways_prob -= 5
                elif mfi < 15:
                    up_prob += 15
                    down_prob -= 10
                    sideways_prob -= 5
            
            # 6. 볼린저 밴드 위치
            if 'bb_upper' in extended and 'bb_lower' in extended:
                bb_position = (current_price - extended['bb_lower']) / (extended['bb_upper'] - extended['bb_lower'])
                if bb_position > 0.95:
                    down_prob += 12
                    up_prob -= 12
                elif bb_position < 0.05:
                    up_prob += 12
                    down_prob -= 12
            
            # 7. ADX 추세 강도
            if 'adx' in extended:
                adx = extended['adx']
                if adx > 40:  # 강한 추세
                    if total_score > 0:
                        up_prob += 10
                        sideways_prob -= 10
                    elif total_score < 0:
                        down_prob += 10
                        sideways_prob -= 10
            
            # 8. 펀딩비 조정
            funding_rate = market_data.get('funding_rate', 0)
            if funding_rate > 0.003:  # 극도 과열
                down_prob += 15
                up_prob -= 15
            elif funding_rate > 0.002:
                down_prob += 10
                up_prob -= 10
            elif funding_rate < -0.002:
                up_prob += 10
                down_prob -= 10
            
            # 9. 변동성 조정 강화
            volatility = market_data.get('volatility', 2)
            if volatility > 5:
                sideways_prob -= 15
                up_prob += 8
                down_prob += 7
            elif volatility < 1:
                sideways_prob += 15
                up_prob -= 8
                down_prob -= 7
            
            # 10. 시장 구조 분석
            market_structure = indicators.get('market_structure', {})
            if market_structure:
                structure_trend = market_structure.get('trend', 'neutral')
                if structure_trend == 'strong_bullish':
                    up_prob += 12
                    down_prob -= 12
                elif structure_trend == 'strong_bearish':
                    down_prob += 12
                    up_prob -= 12
            
            # 정규화 및 최소값 보장
            up_prob = max(5, up_prob)
            down_prob = max(5, down_prob)
            sideways_prob = max(5, sideways_prob)
            
            total = up_prob + sideways_prob + down_prob
            up_prob = int(up_prob / total * 100)
            down_prob = int(down_prob / total * 100)
            sideways_prob = 100 - up_prob - down_prob
            
            # 예상 가격 범위 (ATR 기반)
            atr = extended.get('atr', current_price * 0.015)
            expected_move_12h = atr * 1.2  # 12시간 예상 변동
            
            # 방향성에 따른 범위 계산
            if up_prob > down_prob + 25:
                min_price = current_price - expected_move_12h * 0.2
                max_price = current_price + expected_move_12h * 2
                center_price = current_price + expected_move_12h * 1.2
                trend = "강한 상승 돌파"
                emoji = "🚀"
            elif up_prob > down_prob + 15:
                min_price = current_price - expected_move_12h * 0.4
                max_price = current_price + expected_move_12h * 1.5
                center_price = current_price + expected_move_12h * 0.8
                trend = "상승 추세"
                emoji = "📈"
            elif down_prob > up_prob + 25:
                min_price = current_price - expected_move_12h * 2
                max_price = current_price + expected_move_12h * 0.2
                center_price = current_price - expected_move_12h * 1.2
                trend = "강한 하락 돌파"
                emoji = "🔻"
            elif down_prob > up_prob + 15:
                min_price = current_price - expected_move_12h * 1.5
                max_price = current_price + expected_move_12h * 0.4
                center_price = current_price - expected_move_12h * 0.8
                trend = "하락 추세"
                emoji = "📉"
            else:
                min_price = current_price - expected_move_12h * 0.7
                max_price = current_price + expected_move_12h * 0.7
                center_price = current_price
                trend = "박스권 횡보"
                emoji = "➡️"
            
            # 핵심 판단 근거
            reasons = []
            
            if abs(total_score) > 8:
                direction = "강한 상승" if total_score > 0 else "강한 하락"
                reasons.append(f"• 25개 지표 종합: {direction} 신호")
            
            # RSI 근거
            if rsi_data:
                rsi_value = rsi_data.get('value', 50)
                if rsi_value > 75 or rsi_value < 25:
                    reasons.append(f"• RSI 극단: {rsi_value:.0f} (반전 가능)")
            
            # 이동평균 근거
            if all(k in extended for k in ['ma_7', 'ma_25', 'ma_99']):
                if current_price > extended['ma_7'] > extended['ma_25'] > extended['ma_99']:
                    reasons.append("• 완벽한 상승 이평선 배열")
                elif current_price < extended['ma_7'] < extended['ma_25'] < extended['ma_99']:
                    reasons.append("• 완벽한 하락 이평선 배열")
            
            # 거래량 근거
            if 'mfi' in extended:
                mfi = extended['mfi']
                if mfi > 80:
                    reasons.append(f"• MFI 과매수: {mfi:.0f} (조정 압력)")
                elif mfi < 20:
                    reasons.append(f"• MFI 과매도: {mfi:.0f} (반등 압력)")
            
            # 펀딩비 근거
            if abs(funding_rate) > 0.002:
                if funding_rate > 0:
                    reasons.append(f"• 펀딩비 과열: {funding_rate*100:.3f}% (조정 신호)")
                else:
                    reasons.append(f"• 펀딩비 저조: {funding_rate*100:.3f}% (반등 신호)")
            
            # 변동성 근거
            if volatility > 4:
                reasons.append(f"• 고변동성: {volatility:.1f}% (방향성 강화)")
            elif volatility < 1.5:
                reasons.append(f"• 저변동성: {volatility:.1f}% (돌파 임박)")
            
            reasons_text = '\n'.join(reasons[:5])  # 최대 5개
            
            # 확률 표시 (우세한 것 강조)
            prob_display = []
            if up_prob >= 50:
                prob_display.append(f"▲ 상승 <b>{up_prob}%</b> 🎯")
            else:
                prob_display.append(f"▲ 상승 {up_prob}%")
            
            prob_display.append(f"━ 횡보 {sideways_prob}%")
            
            if down_prob >= 50:
                prob_display.append(f"▼ 하락 <b>{down_prob}%</b> 🎯")
            else:
                prob_display.append(f"▼ 하락 {down_prob}%")
            
            # 신뢰도 계산
            max_prob = max(up_prob, down_prob, sideways_prob)
            confidence = composite_advanced.get('confidence', 50)
            
            if max_prob >= 60:
                confidence_text = f"높음 ({confidence:.0f}%)"
            elif max_prob >= 45:
                confidence_text = f"보통 ({confidence:.0f}%)"
            else:
                confidence_text = f"낮음 ({confidence:.0f}%)"
            
            return f"""{' | '.join(prob_display)}

→ 예상 범위: <b>${min_price:,.0f} ~ ${max_price:,.0f}</b>
→ 중심 예상가: <b>${center_price:,.0f}</b>
→ 예상 추세: {emoji} <b>{trend}</b>
→ 신뢰도: {confidence_text}

<b>핵심 판단 근거:</b>
{reasons_text}"""
            
        except Exception as e:
            self.logger.error(f"AI 예측 실패: {e}")
            return "• AI 예측 분석 중..."

    async def _comprehensive_prediction_validation(self, market_data: dict) -> str:
        """종합적인 예측 검증"""
        try:
            if not self.prediction_history:
                return "• 검증할 이전 예측 없음\n• 첫 번째 예측 생성 중"
            
            current_time = datetime.now()
            current_price = market_data.get('current_price', 0)
            
            # 최근 예측들 검증
            recent_predictions = []
            validated_count = 0
            correct_count = 0
            
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
                        pred_score = pred.get('score', 0)
                        
                        if pred_price > 0:
                            actual_change = ((current_price - pred_price) / pred_price) * 100
                            
                            # 방향 적중 여부
                            direction_correct = False
                            if pred_direction == 'up' and actual_change > 0.5:
                                direction_correct = True
                            elif pred_direction == 'down' and actual_change < -0.5:
                                direction_correct = True
                            elif pred_direction == 'sideways' and abs(actual_change) <= 1:
                                direction_correct = True
                            
                            # 범위 적중 여부
                            range_correct = pred_min <= current_price <= pred_max
                            
                            validated_count += 1
                            if direction_correct:
                                correct_count += 1
                            
                            # 최근 3개 예측 저장
                            if len(recent_predictions) < 3:
                                recent_predictions.append({
                                    'time': pred_time.strftime('%m-%d %H:%M'),
                                    'direction': pred_direction.upper(),
                                    'actual_change': actual_change,
                                    'direction_correct': direction_correct,
                                    'range_correct': range_correct,
                                    'score': pred_score
                                })
                
                except Exception as e:
                    self.logger.debug(f"예측 검증 오류: {e}")
                    continue
            
            if validated_count == 0:
                return "• 검증 가능한 예측 없음 (12시간 경과 필요)\n• 다음 검증: 12시간 후"
            
            # 정확도 계산
            accuracy_rate = (correct_count / validated_count) * 100
            
            # 최근 예측 결과
            recent_results = []
            for pred in recent_predictions:
                if pred['direction_correct']:
                    result_emoji = "✅"
                    result_text = "적중"
                else:
                    result_emoji = "❌"
                    result_text = "실패"
                
                recent_results.append(
                    f"{pred['time']}: {pred['direction']} → {result_emoji} {result_text} ({pred['actual_change']:+.1f}%)"
                )
            
            recent_text = '\n'.join(recent_results) if recent_results else "• 최근 검증 결과 없음"
            
            # 성과 분석
            if accuracy_rate >= 70:
                performance = "🟢 우수"
            elif accuracy_rate >= 60:
                performance = "🟡 양호"
            elif accuracy_rate >= 50:
                performance = "🟠 보통"
            else:
                performance = "🔴 개선 필요"
            
            return f"""• 총 검증: {validated_count}건 중 {correct_count}건 적중
• 정확도: <b>{accuracy_rate:.1f}%</b> ({performance})

<b>최근 예측 결과:</b>
{recent_text}"""
            
        except Exception as e:
            self.logger.error(f"예측 검증 실패: {e}")
            return "• 예측 검증 시스템 오류"

    async def _save_detailed_prediction(self, market_data: dict, indicators: dict):
        """상세한 예측 저장"""
        try:
            current_price = market_data.get('current_price', 0)
            composite_advanced = indicators.get('composite_advanced', {})
            total_score = composite_advanced.get('total_score', 0)
            confidence = composite_advanced.get('confidence', 50)
            
            # 예측 방향 결정 (점수 기반)
            if total_score >= 3:
                direction = 'up'
            elif total_score <= -3:
                direction = 'down'
            else:
                direction = 'sideways'
            
            # 예상 범위 계산
            extended = indicators.get('extended', {})
            atr = extended.get('atr', current_price * 0.015)
            volatility = market_data.get('volatility', 2)
            
            # 방향별 범위 설정
            if direction == 'up':
                pred_min = current_price - atr * 0.3
                pred_max = current_price + atr * 2
            elif direction == 'down':
                pred_min = current_price - atr * 2
                pred_max = current_price + atr * 0.3
            else:
                pred_min = current_price - atr * 0.8
                pred_max = current_price + atr * 0.8
            
            # 주요 지표 값들 저장
            rsi_data = indicators.get('technical', {}).get('rsi', {})
            rsi_value = rsi_data.get('value', 50)
            
            prediction = {
                'timestamp': datetime.now().isoformat(),
                'price': current_price,
                'predicted_direction': direction,
                'predicted_min': pred_min,
                'predicted_max': pred_max,
                'score': total_score,
                'confidence': confidence,
                'volatility': volatility,
                'rsi': rsi_value,
                'macd_hist': extended.get('macd_histogram', 0),
                'funding_rate': market_data.get('funding_rate', 0),
                'volume_24h': market_data.get('volume_24h', 0),
                'signals': {
                    'bullish': composite_advanced.get('bullish_signals', 0),
                    'bearish': composite_advanced.get('bearish_signals', 0),
                    'neutral': composite_advanced.get('neutral_signals', 0)
                }
            }
            
            self.prediction_history.append(prediction)
            self._save_prediction_history()
            
            self.logger.info(f"예측 저장: {direction.upper()} (점수: {total_score:.1f}, 신뢰도: {confidence:.0f}%)")
            
        except Exception as e:
            self.logger.error(f"예측 저장 실패: {e}")

    async def _calculate_extended_indicators(self, market_data: dict) -> dict:
        """확장된 기술적 지표 계산 (25개 지표)"""
        try:
            extended = {}
            
            # K라인 데이터 가져오기
            if self.bitget_client:
                klines_1h = market_data.get('klines_1h', [])
                klines_4h = market_data.get('klines_4h', [])
                
                if klines_1h:
                    # 1시간 데이터 분석
                    closes_1h = [float(k[4]) for k in klines_1h[-100:]]  # 종가
                    highs_1h = [float(k[2]) for k in klines_1h[-100:]]   # 고가
                    lows_1h = [float(k[3]) for k in klines_1h[-100:]]    # 저가
                    volumes_1h = [float(k[5]) for k in klines_1h[-100:]]  # 거래량
                    
                    if len(closes_1h) >= 50:
                        # 이동평균선들
                        extended['ma_7'] = sum(closes_1h[-7:]) / 7
                        extended['ma_25'] = sum(closes_1h[-25:]) / 25
                        extended['ma_50'] = sum(closes_1h[-50:]) / 50
                        extended['ma_99'] = sum(closes_1h[-99:]) / 99 if len(closes_1h) >= 99 else sum(closes_1h) / len(closes_1h)
                        
                        # EMA 계산
                        extended['ema_12'] = self._calculate_ema(closes_1h, 12)
                        extended['ema_26'] = self._calculate_ema(closes_1h, 26)
                        extended['ema_50'] = self._calculate_ema(closes_1h, 50)
                        
                        # MACD
                        macd = extended['ema_12'] - extended['ema_26']
                        extended['macd'] = macd
                        extended['macd_signal'] = self._calculate_ema([macd], 9)
                        extended['macd_histogram'] = macd - extended['macd_signal']
                        
                        # 볼린저 밴드
                        ma_20 = sum(closes_1h[-20:]) / 20
                        std_20 = self._calculate_std(closes_1h[-20:], ma_20)
                        extended['bb_upper'] = ma_20 + (2 * std_20)
                        extended['bb_middle'] = ma_20
                        extended['bb_lower'] = ma_20 - (2 * std_20)
                        extended['bb_width'] = (extended['bb_upper'] - extended['bb_lower']) / ma_20
                        
                        # 스토캐스틱
                        extended['stoch_k'], extended['stoch_d'] = self._calculate_stochastic(highs_1h, lows_1h, closes_1h)
                        
                        # CCI
                        extended['cci'] = self._calculate_cci(highs_1h, lows_1h, closes_1h)
                        
                        # Williams %R
                        extended['williams_r'] = self._calculate_williams_r(highs_1h, lows_1h, closes_1h)
                        
                        # ATR
                        extended['atr'] = self._calculate_atr(highs_1h, lows_1h, closes_1h)
                        
                        # ADX
                        extended['adx'] = self._calculate_adx(highs_1h, lows_1h, closes_1h)
                        
                        # OBV
                        extended['obv'] = self._calculate_obv(closes_1h, volumes_1h)
                        
                        # MFI
                        extended['mfi'] = self._calculate_mfi(highs_1h, lows_1h, closes_1h, volumes_1h)
                        
                        # VWAP
                        extended['vwap'] = self._calculate_vwap(highs_1h, lows_1h, closes_1h, volumes_1h)
                        
                        # 피봇 포인트
                        extended['pivot_points'] = self._calculate_pivot_points(
                            highs_1h[-1], lows_1h[-1], closes_1h[-1]
                        )
                        
                        # 이치모쿠 구름
                        extended['ichimoku'] = self._calculate_ichimoku(highs_1h, lows_1h)
                        
                        # 파라볼릭 SAR
                        extended['parabolic_sar'] = self._calculate_parabolic_sar(highs_1h, lows_1h)
                        
                        # 켈트너 채널
                        extended['keltner_channels'] = self._calculate_keltner_channels(highs_1h, lows_1h, closes_1h)
                        
                        # 슈퍼트렌드
                        extended['supertrend'] = self._calculate_supertrend(highs_1h, lows_1h, closes_1h, extended['atr'])
                        
                        # 추가 고급 지표들
                        extended['roc'] = self._calculate_roc(closes_1h)  # Rate of Change
                        extended['momentum'] = self._calculate_momentum(closes_1h)  # Momentum
                        extended['trix'] = self._calculate_trix(closes_1h)  # TRIX
                        extended['ultimate_oscillator'] = self._calculate_ultimate_oscillator(highs_1h, lows_1h, closes_1h)
                        extended['commodity_channel_index'] = extended['cci']  # 별칭
                        
                # 4시간 데이터로 추가 분석
                if klines_4h and len(klines_4h) >= 20:
                    closes_4h = [float(k[4]) for k in klines_4h[-50:]]
                    highs_4h = [float(k[2]) for k in klines_4h[-50:]]
                    lows_4h = [float(k[3]) for k in klines_4h[-50:]]
                    
                    # 4시간 추세 분석
                    extended['trend_4h'] = self._analyze_trend(closes_4h)
                    extended['support_resistance_4h'] = self._calculate_support_resistance(highs_4h, lows_4h, closes_4h)
            
            return extended
            
        except Exception as e:
            self.logger.error(f"확장 지표 계산 실패: {e}")
            return {}

    async def _calculate_composite_score(self, indicators: dict, extended: dict) -> dict:
        """종합 점수 계산 (25개 지표 기반)"""
        try:
            signals = {
                'bullish': 0,
                'bearish': 0,
                'neutral': 0,
                'scores': {}
            }
            
            current_price = self.market_cache.get('current_price', 0)
            
            # 1. RSI (3점)
            rsi_data = indicators.get('technical', {}).get('rsi', {})
            if rsi_data:
                rsi_value = rsi_data.get('value', 50)
                if rsi_value < 30:
                    signals['bullish'] += 1
                    signals['scores']['RSI'] = 3
                elif rsi_value > 70:
                    signals['bearish'] += 1
                    signals['scores']['RSI'] = -3
                else:
                    signals['neutral'] += 1
                    signals['scores']['RSI'] = 0
            
            # 2. MACD (3점)
            if 'macd' in extended and 'macd_signal' in extended:
                macd_hist = extended.get('macd_histogram', 0)
                if macd_hist > 0:
                    signals['bullish'] += 1
                    signals['scores']['MACD'] = 2 if macd_hist > 50 else 1
                elif macd_hist < 0:
                    signals['bearish'] += 1
                    signals['scores']['MACD'] = -2 if macd_hist < -50 else -1
                else:
                    signals['neutral'] += 1
                    signals['scores']['MACD'] = 0
            
            # 3. 이동평균 배열 (4점)
            if all(k in extended for k in ['ma_7', 'ma_25', 'ma_99']):
                ma7, ma25, ma99 = extended['ma_7'], extended['ma_25'], extended['ma_99']
                if current_price > ma7 > ma25 > ma99:
                    signals['bullish'] += 1
                    signals['scores']['MA_Array'] = 4
                elif current_price < ma7 < ma25 < ma99:
                    signals['bearish'] += 1
                    signals['scores']['MA_Array'] = -4
                elif current_price > ma7 > ma25:
                    signals['bullish'] += 1
                    signals['scores']['MA_Array'] = 2
                elif current_price < ma7 < ma25:
                    signals['bearish'] += 1
                    signals['scores']['MA_Array'] = -2
                else:
                    signals['neutral'] += 1
                    signals['scores']['MA_Array'] = 0
            
            # 4. 볼린저 밴드 (2점)
            if 'bb_upper' in extended and 'bb_lower' in extended:
                bb_position = (current_price - extended['bb_lower']) / (extended['bb_upper'] - extended['bb_lower'])
                if bb_position > 0.8:
                    signals['bearish'] += 1
                    signals['scores']['Bollinger'] = -2
                elif bb_position < 0.2:
                    signals['bullish'] += 1
                    signals['scores']['Bollinger'] = 2
                else:
                    signals['neutral'] += 1
                    signals['scores']['Bollinger'] = 0
            
            # 5. 스토캐스틱 (2점)
            if 'stoch_k' in extended:
                stoch_k = extended['stoch_k']
                if stoch_k < 20:
                    signals['bullish'] += 1
                    signals['scores']['Stochastic'] = 2
                elif stoch_k > 80:
                    signals['bearish'] += 1
                    signals['scores']['Stochastic'] = -2
                else:
                    signals['neutral'] += 1
                    signals['scores']['Stochastic'] = 0
            
            # 6. ADX (2점)
            if 'adx' in extended:
                adx = extended['adx']
                if adx > 25:
                    # 강한 추세, 방향은 이동평균으로 판단
                    if current_price > extended.get('ma_25', current_price):
                        signals['bullish'] += 1
                        signals['scores']['ADX'] = 2
                    else:
                        signals['bearish'] += 1
                        signals['scores']['ADX'] = -2
                else:
                    signals['neutral'] += 1
                    signals['scores']['ADX'] = 0
            
            # 7. CCI (2점)
            if 'cci' in extended:
                cci = extended['cci']
                if cci < -100:
                    signals['bullish'] += 1
                    signals['scores']['CCI'] = 2
                elif cci > 100:
                    signals['bearish'] += 1
                    signals['scores']['CCI'] = -2
                else:
                    signals['neutral'] += 1
                    signals['scores']['CCI'] = 0
            
            # 8. Williams %R (2점)
            if 'williams_r' in extended:
                williams_r = extended['williams_r']
                if williams_r < -80:
                    signals['bullish'] += 1
                    signals['scores']['Williams_R'] = 2
                elif williams_r > -20:
                    signals['bearish'] += 1
                    signals['scores']['Williams_R'] = -2
                else:
                    signals['neutral'] += 1
                    signals['scores']['Williams_R'] = 0
            
            # 9. MFI (2점)
            if 'mfi' in extended:
                mfi = extended['mfi']
                if mfi < 20:
                    signals['bullish'] += 1
                    signals['scores']['MFI'] = 2
                elif mfi > 80:
                    signals['bearish'] += 1
                    signals['scores']['MFI'] = -2
                else:
                    signals['neutral'] += 1
                    signals['scores']['MFI'] = 0
            
            # 10. 이치모쿠 (2점)
            if 'ichimoku' in extended:
                ichimoku = extended['ichimoku']
                cloud_top = ichimoku.get('cloud_top', current_price)
                cloud_bottom = ichimoku.get('cloud_bottom', current_price)
                
                if current_price > cloud_top:
                    signals['bullish'] += 1
                    signals['scores']['Ichimoku'] = 2
                elif current_price < cloud_bottom:
                    signals['bearish'] += 1
                    signals['scores']['Ichimoku'] = -2
                else:
                    signals['neutral'] += 1
                    signals['scores']['Ichimoku'] = 0
            
            # 11-25. 추가 지표들 (각 1점)
            additional_indicators = [
                ('parabolic_sar', 1), ('roc', 1), ('momentum', 1), ('trix', 1),
                ('ultimate_oscillator', 1), ('vwap', 1), ('supertrend', 1),
                ('keltner_channels', 1), ('ema_12', 1), ('ema_26', 1),
                ('ema_50', 1), ('ma_50', 1), ('trend_4h', 1), ('support_resistance_4h', 1), ('obv', 1)
            ]
            
            for indicator, weight in additional_indicators:
                if indicator in extended:
                    value = extended[indicator]
                    # 간단한 판단 로직
                    if isinstance(value, (int, float)):
                        if value > 0:
                            signals['bullish'] += 1
                            signals['scores'][indicator] = weight
                        elif value < 0:
                            signals['bearish'] += 1
                            signals['scores'][indicator] = -weight
                        else:
                            signals['neutral'] += 1
                            signals['scores'][indicator] = 0
                    else:
                        signals['neutral'] += 1
                        signals['scores'][indicator] = 0
            
            # 총점 계산
            total_score = sum(signals['scores'].values())
            total_indicators = len(signals['scores'])
            
            # 신뢰도 계산
            max_signals = max(signals['bullish'], signals['bearish'], signals['neutral'])
            confidence = (max_signals / total_indicators) * 100 if total_indicators > 0 else 50
            
            return {
                'total_score': total_score,
                'bullish_signals': signals['bullish'],
                'bearish_signals': signals['bearish'],
                'neutral_signals': signals['neutral'],
                'confidence': confidence,
                'total_indicators': total_indicators,
                'signal_breakdown': signals['scores']
            }
            
        except Exception as e:
            self.logger.error(f"종합 점수 계산 실패: {e}")
            return {
                'total_score': 0,
                'bullish_signals': 0,
                'bearish_signals': 0,
                'neutral_signals': 0,
                'confidence': 50,
                'total_indicators': 0,
                'signal_breakdown': {}
            }

    async def _analyze_market_structure(self, market_data: dict) -> dict:
        """시장 구조 분석"""
        try:
            structure = {}
            
            # 4시간 데이터로 구조 분석
            klines_4h = market_data.get('klines_4h', [])
            if klines_4h and len(klines_4h) >= 20:
                closes_4h = [float(k[4]) for k in klines_4h[-20:]]
                highs_4h = [float(k[2]) for k in klines_4h[-20:]]
                lows_4h = [float(k[3]) for k in klines_4h[-20:]]
                
                # 고점/저점 분석
                recent_high = max(highs_4h[-10:])
                recent_low = min(lows_4h[-10:])
                current_price = closes_4h[-1]
                
                # 추세 강도
                price_change = (current_price - closes_4h[0]) / closes_4h[0]
                
                if price_change > 0.05:
                    structure['trend'] = 'strong_bullish'
                elif price_change > 0.02:
                    structure['trend'] = 'bullish'
                elif price_change < -0.05:
                    structure['trend'] = 'strong_bearish'
                elif price_change < -0.02:
                    structure['trend'] = 'bearish'
                else:
                    structure['trend'] = 'neutral'
                
                # 변동성 분석
                volatility = (recent_high - recent_low) / current_price
                structure['volatility_level'] = 'high' if volatility > 0.1 else 'normal' if volatility > 0.05 else 'low'
                
                # 지지/저항 레벨
                structure['resistance'] = recent_high
                structure['support'] = recent_low
                structure['current_position'] = (current_price - recent_low) / (recent_high - recent_low)
            
            return structure
            
        except Exception as e:
            self.logger.error(f"시장 구조 분석 실패: {e}")
            return {}

    # 추가 지표 계산 함수들
    def _calculate_roc(self, prices: list, period: int = 10) -> float:
        """Rate of Change"""
        if len(prices) < period + 1:
            return 0
        return ((prices[-1] - prices[-period-1]) / prices[-period-1]) * 100

    def _calculate_momentum(self, prices: list, period: int = 10) -> float:
        """Momentum"""
        if len(prices) < period + 1:
            return 0
        return prices[-1] - prices[-period-1]

    def _calculate_trix(self, prices: list, period: int = 14) -> float:
        """TRIX"""
        if len(prices) < period * 3:
            return 0
        
        # Triple smoothed EMA
        ema1 = self._calculate_ema(prices, period)
        ema2 = self._calculate_ema([ema1], period)
        ema3 = self._calculate_ema([ema2], period)
        
        # Rate of change of triple smoothed EMA
        return ((ema3 - ema3) / ema3) * 10000 if ema3 != 0 else 0

    def _calculate_ultimate_oscillator(self, highs: list, lows: list, closes: list) -> float:
        """Ultimate Oscillator"""
        if len(closes) < 28:
            return 50
        
        # 간단한 구현
        bp_sum_7 = sum(closes[-7:]) - sum(lows[-7:])
        tr_sum_7 = sum(highs[-7:]) - sum(lows[-7:])
        
        bp_sum_14 = sum(closes[-14:]) - sum(lows[-14:])
        tr_sum_14 = sum(highs[-14:]) - sum(lows[-14:])
        
        bp_sum_28 = sum(closes[-28:]) - sum(lows[-28:])
        tr_sum_28 = sum(highs[-28:]) - sum(lows[-28:])
        
        avg7 = (bp_sum_7 / tr_sum_7) * 4 if tr_sum_7 != 0 else 0
        avg14 = (bp_sum_14 / tr_sum_14) * 2 if tr_sum_14 != 0 else 0
        avg28 = (bp_sum_28 / tr_sum_28) * 1 if tr_sum_28 != 0 else 0
        
        return ((avg7 + avg14 + avg28) / 7) * 100

    def _analyze_trend(self, prices: list) -> str:
        """추세 분석"""
        if len(prices) < 10:
            return 'neutral'
        
        recent = prices[-5:]
        older = prices[-10:-5]
        
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        
        change = (recent_avg - older_avg) / older_avg
        
        if change > 0.02:
            return 'bullish'
        elif change < -0.02:
            return 'bearish'
        else:
            return 'neutral'

    def _calculate_support_resistance(self, highs: list, lows: list, closes: list) -> dict:
        """지지/저항 계산"""
        try:
            if len(closes) < 10:
                return {'support': closes[-1] * 0.95, 'resistance': closes[-1] * 1.05}
            
            recent_high = max(highs[-10:])
            recent_low = min(lows[-10:])
            
            return {
                'support': recent_low,
                'resistance': recent_high,
                'range': recent_high - recent_low
            }
        except:
            current_price = closes[-1] if closes else 100000
            return {'support': current_price * 0.95, 'resistance': current_price * 1.05}

    # 기존 보조 함수들 (이미 구현된 것들 유지)
    def _calculate_ema(self, prices: list, period: int) -> float:
        """지수이동평균 계산"""
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema

    def _calculate_std(self, values: list, mean: float) -> float:
        """표준편차 계산"""
        if not values:
            return 0
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def _calculate_stochastic(self, highs: list, lows: list, closes: list, period: int = 14) -> tuple:
        """스토캐스틱 계산"""
        if len(closes) < period:
            return 50, 50
        
        lowest_low = min(lows[-period:])
        highest_high = max(highs[-period:])
        
        if highest_high == lowest_low:
            return 50, 50
        
        k = ((closes[-1] - lowest_low) / (highest_high - lowest_low)) * 100
        
        # %D는 %K의 3일 이동평균 (간단 구현)
        d = k  # 간단히 같은 값 사용
        
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
        """ADX 계산 (간단 버전)"""
        if len(closes) < period * 2:
            return 25
        
        # 간단한 ADX 계산
        price_ranges = []
        for i in range(1, len(closes)):
            high_diff = abs(highs[i] - highs[i-1])
            low_diff = abs(lows[i] - lows[i-1])
            close_diff = abs(closes[i] - closes[i-1])
            price_ranges.append(max(high_diff, low_diff, close_diff))
        
        if not price_ranges:
            return 25
        
        avg_range = sum(price_ranges[-period:]) / min(period, len(price_ranges))
        return min(avg_range * 100, 100)  # 0-100 범위로 정규화

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

    def _calculate_vwap(self, highs: list, lows: list, closes: list, volumes: list) -> float:
        """VWAP 계산"""
        if not volumes or sum(volumes) == 0 or len(volumes) != len(closes):
            return closes[-1] if closes else 0
        
        typical_prices = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
        
        total_pv = sum(tp * v for tp, v in zip(typical_prices, volumes))
        total_volume = sum(volumes)
        
        return total_pv / total_volume if total_volume > 0 else closes[-1]

    def _calculate_pivot_points(self, high: float, low: float, close: float) -> dict:
        """피봇 포인트 계산"""
        pivot = (high + low + close) / 3
        
        return {
            'pivot': pivot,
            'r1': 2 * pivot - low,
            'r2': pivot + (high - low),
            'r3': high + 2 * (pivot - low),
            's1': 2 * pivot - high,
            's2': pivot - (high - low),
            's3': low - 2 * (high - pivot)
        }

    def _calculate_ichimoku(self, highs: list, lows: list) -> dict:
        """이치모쿠 구름 계산"""
        def donchian(highs_data, lows_data, period):
            if len(highs_data) < period or len(lows_data) < period:
                return (max(highs_data) + min(lows_data)) / 2
            return (max(highs_data[-period:]) + min(lows_data[-period:])) / 2
        
        # 전환선 (9일)
        tenkan = donchian(highs, lows, 9)
        
        # 기준선 (26일)
        kijun = donchian(highs, lows, 26)
        
        # 선행스팬 A
        senkou_a = (tenkan + kijun) / 2
        
        # 선행스팬 B (52일)
        senkou_b = donchian(highs, lows, 52)
        
        return {
            'tenkan': tenkan,
            'kijun': kijun,
            'senkou_a': senkou_a,
            'senkou_b': senkou_b,
            'cloud_top': max(senkou_a, senkou_b),
            'cloud_bottom': min(senkou_a, senkou_b)
        }

    def _calculate_parabolic_sar(self, highs: list, lows: list, af: float = 0.02, max_af: float = 0.2) -> float:
        """파라볼릭 SAR 계산"""
        if len(highs) < 2:
            return lows[-1] if lows else 0
        
        # 간단한 구현
        return (highs[-1] + lows[-1]) / 2

    def _calculate_keltner_channels(self, highs: list, lows: list, closes: list, period: int = 20, multiplier: float = 2) -> dict:
        """켈트너 채널 계산"""
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

    def _calculate_supertrend(self, highs: list, lows: list, closes: list, atr: float, multiplier: float = 3) -> dict:
        """슈퍼트렌드 계산"""
        if not closes:
            return {'trend': 0, 'value': 0}
        
        hl_avg = (highs[-1] + lows[-1]) / 2
        
        upper_band = hl_avg + (multiplier * atr)
        lower_band = hl_avg - (multiplier * atr)
        
        # 추세 결정
        if closes[-1] > upper_band:
            trend = 1  # 상승
            value = lower_band
        elif closes[-1] < lower_band:
            trend = -1  # 하락
            value = upper_band
        else:
            trend = 0  # 중립
            value = hl_avg
        
        return {
            'trend': trend,
            'value': value,
            'upper': upper_band,
            'lower': lower_band
        }

    # 기타 필요한 함수들은 기존 코드에서 그대로 사용
