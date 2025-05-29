# report_generators/regular_report.py
from .base_generator import BaseReportGenerator
from .mental_care import MentalCareGenerator
import traceback
from datetime import datetime, timedelta
import json
import pytz

class RegularReportGenerator(BaseReportGenerator):
    """정기 리포트 - 선물 롱/숏 판단 특화"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        self.mental_care = MentalCareGenerator(self.openai_client)
        self.last_prediction = None
    
    async def generate_report(self) -> str:
        """🧾 선물 롱/숏 판단 종합 리포트"""
        try:
            current_time = self._get_current_time_kst()
            
            # 포괄적 데이터 수집
            market_data = await self._collect_all_data()
            
            # 추가 시장 데이터 수집
            if self.data_collector:
                comprehensive_data = await self.data_collector.get_comprehensive_market_data()
                market_data.update(comprehensive_data)
            
            # 지표 시스템 설정
            if self.bitget_client and hasattr(self.indicator_system, 'set_bitget_client'):
                self.indicator_system.set_bitget_client(self.bitget_client)
            
            # 선물 특화 지표 계산
            indicators = await self.indicator_system.calculate_all_indicators(market_data)
            
            # 섹션별 생성
            events_text = await self._format_market_events(market_data)
            futures_analysis = await self._format_futures_analysis(market_data, indicators)
            technical_text = await self._format_technical_analysis(market_data, indicators)
            sentiment_text = await self._format_market_sentiment(market_data, indicators)
            signal_text = self._format_trading_signals(indicators)
            strategy_text = await self._format_strategy_recommendation(market_data, indicators)
            risk_text = await self._format_risk_assessment(market_data, indicators)
            
            # 향후 12시간 예측 추가
            prediction_text = await self._format_12h_prediction(market_data, indicators)
            
            validation_text = self._format_validation()
            pnl_text = await self._format_profit_loss()
            mental_text = await self._generate_mental_care(market_data, indicators)
            
            # 이번 예측 저장
            self._save_prediction(indicators)
            
            report = f"""🧾 /report 명령어 – GPT 비트코인 매매 예측 리포트
📅 작성 시각: {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

📌 **시장 이벤트 및 주요 속보**
{events_text}

━━━━━━━━━━━━━━━━━━━

📊 **선물 시장 핵심 지표**
{futures_analysis}

━━━━━━━━━━━━━━━━━━━

📉 **기술적 분석**
{technical_text}

━━━━━━━━━━━━━━━━━━━

🧠 **시장 심리 및 포지셔닝**
{sentiment_text}

━━━━━━━━━━━━━━━━━━━

🎯 **롱/숏 신호 분석**
{signal_text}

━━━━━━━━━━━━━━━━━━━

📌 **전략 제안**
{strategy_text}

━━━━━━━━━━━━━━━━━━━

⚠️ **리스크 평가**
{risk_text}

━━━━━━━━━━━━━━━━━━━

🔮 **향후 12시간 예측**
{prediction_text}

━━━━━━━━━━━━━━━━━━━

📊 **예측 검증**
{validation_text}

━━━━━━━━━━━━━━━━━━━

💰 **손익 현황**
{pnl_text}

━━━━━━━━━━━━━━━━━━━

🧠 **멘탈 케어**
{mental_text}"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"정기 리포트 생성 실패: {str(e)}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            return f"❌ 리포트 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _format_price_with_change(self, price: float, change_24h: float) -> str:
        """가격과 24시간 변동률 포맷팅"""
        change_percent = change_24h * 100
        change_emoji = "📈" if change_24h > 0 else "📉" if change_24h < 0 else "➖"
        return f"${price:,.0f} {change_emoji} ({change_percent:+.1f}%)"
    
    async def _format_market_events(self, market_data: dict) -> str:
        """시장 이벤트 - 비트코인/미증시 직결 뉴스만"""
        try:
            recent_news = await self.data_collector.get_recent_news(hours=3) if self.data_collector else []
            
            if not recent_news:
                return "• 현재 주요 시장 이벤트 없음"
            
            # 비트코인/미증시 직결 뉴스만 필터링
            filtered_news = []
            for news in recent_news:
                title = news.get('title_ko', news.get('title', '')).lower()
                description = news.get('description', '').lower()
                content = title + ' ' + description
                
                # 중요 키워드 체크
                important_keywords = [
                    # 비트코인 직접 관련
                    'bitcoin', 'btc', '비트코인',
                    # 기업 매입
                    'bought', 'purchase', 'acquisition', '구매', '매입',
                    # 정책/규제
                    'sec', 'fed', 'fomc', 'trump', 'regulation', 'policy',
                    '연준', '금리', '규제', '정책', '트럼프',
                    # ETF
                    'etf', '승인', 'approval', 'reject',
                    # 시장 급변동
                    'crash', 'surge', 'plunge', 'rally', '폭락', '급등',
                    # 주요 기업
                    'tesla', 'microstrategy', 'gamestop', 'coinbase', 'blackrock'
                ]
                
                # 제외 키워드
                exclude_keywords = [
                    'how to', 'tutorial', 'guide', 'learn',
                    '방법', '가이드', '배우기', '입문',
                    'price prediction', '가격 예측',
                    'crypto news today', '오늘의 암호화폐',
                    'gold', '금', 'oil', '원유'
                ]
                
                # 제외 키워드가 있으면 스킵
                if any(keyword in content for keyword in exclude_keywords):
                    continue
                
                # 중요 키워드가 2개 이상 포함된 경우만
                keyword_count = sum(1 for keyword in important_keywords if keyword in content)
                if keyword_count >= 2:
                    filtered_news.append(news)
            
            # 중요도 순으로 정렬
            filtered_news.sort(key=lambda x: x.get('weight', 0), reverse=True)
            
            # 상위 4개만 포맷팅
            formatted = await self.format_news_with_time(filtered_news[:4], max_items=4)
            
            return '\n'.join(formatted) if formatted else "• 특이 뉴스 없음"
            
        except Exception as e:
            self.logger.error(f"뉴스 포맷팅 오류: {e}")
            return "• 뉴스 데이터 조회 중 오류"
    
    async def _format_futures_analysis(self, market_data: dict, indicators: dict) -> str:
        """선물 시장 핵심 지표"""
        current_price = market_data.get('current_price', 0)
        change_24h = market_data.get('change_24h', 0)
        
        # 각 분석 결과 가져오기
        funding = indicators.get('funding_analysis', {})
        oi = indicators.get('oi_analysis', {})
        basis = indicators.get('futures_metrics', {}).get('basis', {})
        ls_ratio = indicators.get('long_short_ratio', {})
        liquidations = indicators.get('liquidation_analysis', {})
        
        lines = [
            f"• **현재가**: {self._format_price_with_change(current_price, change_24h)} (Bitget BTCUSDT)",
            f"• **펀딩비**: {funding.get('current_rate', 0):+.3%} (연환산 {funding.get('annual_rate', 0):+.1f}%) → {funding.get('signal', '중립')}",
            f"• **미결제약정**: {oi.get('oi_change_percent', 0):+.1f}% 변화 → {oi.get('price_divergence', '중립')}",
            f"• **선물 베이시스**: {basis.get('rate', 0):+.3f}% → {basis.get('signal', '중립')}",
            f"• **롱/숏 비율**: {ls_ratio.get('long_ratio', 50):.0f}:{ls_ratio.get('short_ratio', 50):.0f} → {ls_ratio.get('signal', '균형')}",
            f"• **청산 위험**: {liquidations.get('liquidation_pressure', '중립')}"
        ]
        
        # Fear & Greed Index 추가
        if 'fear_greed' in market_data and market_data['fear_greed']:
            fng = market_data['fear_greed']
            lines.append(f"• **공포탐욕지수**: {fng.get('value', 50)}/100 ({fng.get('value_classification', 'Neutral')})")
        
        # 종합 평가 추가
        lines.append("")
        lines.append(self._generate_futures_summary(indicators))
        
        return '\n'.join(lines)
    
    def _generate_futures_summary(self, indicators: dict) -> str:
        """선물 지표 종합 평가 - 더 명확한 방향성"""
        composite = indicators.get('composite_signal', {})
        total_score = composite.get('total_score', 0)
        signal = composite.get('signal', '중립')
        
        # 더 구체적인 평가
        if total_score >= 5:
            return "**핵심 지표 분석 종합 평가**: 강한 상승 신호로 적극적 롱 진입이 유리하다"
        elif total_score >= 3:
            return "**핵심 지표 분석 종합 평가**: 상승 우위로 신중한 롱 포지션이 유리하다"
        elif total_score <= -5:
            return "**핵심 지표 분석 종합 평가**: 강한 하락 신호로 적극적 숏 진입이 유리하다"
        elif total_score <= -3:
            return "**핵심 지표 분석 종합 평가**: 하락 우위로 신중한 숏 포지션이 유리하다"
        else:
            # 중립이어도 약간의 방향성 제시
            if total_score > 0:
                return "**핵심 지표 분석 종합 평가**: 약한 상승 신호나 명확한 돌파 확인 후 진입 권장"
            elif total_score < 0:
                return "**핵심 지표 분석 종합 평가**: 약한 하락 신호나 명확한 이탈 확인 후 진입 권장"
            else:
                return "**핵심 지표 분석 종합 평가**: 방향성 부재로 관망하되 돌파/이탈 시 빠른 대응 준비"
    
    async def _format_technical_analysis(self, market_data: dict, indicators: dict) -> str:
        """기술적 분석 - 선물 관점"""
        technical = indicators.get('technical', {})
        market_profile = indicators.get('market_profile', {})
        volume_delta = indicators.get('volume_delta', {})
        
        lines = [
            f"• **24H 고/저**: ${market_data.get('high_24h', 0):,.0f} / ${market_data.get('low_24h', 0):,.0f}",
            f"• **24H 변동**: {market_data.get('change_24h', 0):+.1%} | **거래량**: {market_data.get('volume_24h', 0):,.0f} BTC"
        ]
        
        # 거래량 분석 추가
        if volume_delta and volume_delta.get('signal'):
            buy_vol = volume_delta.get('buy_volume', 0)
            sell_vol = volume_delta.get('sell_volume', 0)
            if buy_vol > sell_vol * 1.2:
                lines.append("• 거래량 증가, 매수 체결 우세 → 롱 지지")
            elif sell_vol > buy_vol * 1.2:
                lines.append("• 거래량 증가, 매도 체결 우세 → 숏 지지")
            else:
                lines.append("• 거래량 균형 상태")
        
        # RSI
        if 'rsi' in technical:
            rsi_data = technical['rsi']
            rsi_val = rsi_data.get('value', 50)
            if rsi_val < 35:
                lines.append(f"• **RSI(14)**: {rsi_val:.1f} → 과매도 구간 (반등 가능)")
            elif rsi_val > 65:
                lines.append(f"• **RSI(14)**: {rsi_val:.1f} → 과매수 구간 (조정 가능)")
            else:
                lines.append(f"• **RSI(14)**: {rsi_val:.1f} → 중립")
        
        # 마켓 프로파일
        if market_profile and 'poc' in market_profile:
            poc = market_profile['poc']
            current = market_data.get('current_price', 0)
            
            if current > poc * 1.02:
                poc_signal = "강한 롱 신호"
            elif current > poc * 1.005:
                poc_signal = "롱 우세"
            elif current < poc * 0.98:
                poc_signal = "강한 숏 신호"
            elif current < poc * 0.995:
                poc_signal = "숏 압력"
            else:
                poc_signal = "균형점 근처"
            
            lines.append(f"• **POC (Point of Control)**: ${poc:,.0f} → {poc_signal}")
            lines.append(f"• **Value Area**: ${market_profile['value_area_low']:,.0f} ~ ${market_profile['value_area_high']:,.0f}")
            lines.append(f"• **현재 위치**: {market_profile.get('price_position', '중립')}")
        
        # 기술적 분석 종합
        lines.append("")
        lines.append(self._generate_technical_summary(market_data, indicators))
        
        return '\n'.join(lines)
    
    def _generate_technical_summary(self, market_data: dict, indicators: dict) -> str:
        """기술적 분석 종합 평가 - 더 명확한 방향성"""
        technical = indicators.get('technical', {})
        volume_delta = indicators.get('volume_delta', {})
        market_profile = indicators.get('market_profile', {})
        
        bullish_count = 0
        bearish_count = 0
        
        # RSI 체크 (가중치 2)
        rsi_val = technical.get('rsi', {}).get('value', 50)
        if rsi_val < 35:
            bullish_count += 2
        elif rsi_val > 65:
            bearish_count += 2
        
        # 거래량 체크 (가중치 1.5)
        if '매수 우세' in volume_delta.get('signal', ''):
            bullish_count += 1.5
        elif '매도 우세' in volume_delta.get('signal', ''):
            bearish_count += 1.5
        
        # 가격 위치 체크 (가중치 1)
        price_position = market_profile.get('price_position', '')
        if 'Value Area 하단' in price_position:
            bullish_count += 1
        elif 'Value Area 상단' in price_position:
            bearish_count += 1
        
        # POC 대비 위치 (가중치 1.5)
        current = market_data.get('current_price', 0)
        poc = market_profile.get('poc', current)
        if current > poc * 1.01:
            bullish_count += 1.5
        elif current < poc * 0.99:
            bearish_count += 1.5
        
        # 명확한 방향성 제시
        if bullish_count >= bearish_count + 2:
            return "**기술적 분석 종합 평가**: 강한 상승 신호들이 확인되어 즉시 롱 진입이 유리하다"
        elif bullish_count > bearish_count:
            return "**기술적 분석 종합 평가**: 상승 지표 우세로 롱 포지션 구축이 유리하다"
        elif bearish_count >= bullish_count + 2:
            return "**기술적 분석 종합 평가**: 강한 하락 신호들이 확인되어 즉시 숏 진입이 유리하다"
        elif bearish_count > bullish_count:
            return "**기술적 분석 종합 평가**: 하락 지표 우세로 숏 포지션 구축이 유리하다"
        else:
            return "**기술적 분석 종합 평가**: 지표 혼재로 추세 전환점 대기, 돌파 방향 추종 전략 권장"
    
    async def _format_market_sentiment(self, market_data: dict, indicators: dict) -> str:
        """시장 심리 및 포지셔닝"""
        cvd = indicators.get('volume_delta', {})
        smart_money = indicators.get('smart_money', {})
        
        lines = []
        
        # CVD (누적 거래량 델타)
        if cvd:
            lines.append(f"• **CVD**: {cvd.get('cvd_ratio', 0):+.1f}% → {cvd.get('signal', '균형')}")
            lines.append(f"• **매수/매도 거래량**: {cvd.get('buy_volume', 0):,.0f} / {cvd.get('sell_volume', 0):,.0f} BTC")
        
        # 스마트머니
        if smart_money:
            lines.append(f"• **대형 거래**: 매수 {smart_money.get('large_buy_count', 0)}건 vs 매도 {smart_money.get('large_sell_count', 0)}건")
            lines.append(f"• **스마트머니 플로우**: {smart_money.get('net_flow', 0):+.1f} BTC → {smart_money.get('signal', '중립')}")
        
        # 시장 개요 (CoinGecko)
        if 'market_overview' in market_data and market_data['market_overview']:
            overview = market_data['market_overview']
            lines.append(f"• **BTC 도미넌스**: {overview.get('btc_dominance', 0):.1f}%")
            lines.append(f"• **전체 시총 변화**: {overview.get('market_cap_change_24h', 0):+.1f}%")
        
        # 시장 심리 종합
        lines.append("")
        lines.append(self._generate_sentiment_summary(indicators, market_data))
        
        return '\n'.join(lines) if lines else "• 센티먼트 데이터 수집 중"
    
    def _generate_sentiment_summary(self, indicators: dict, market_data: dict) -> str:
        """시장 심리 종합 평가 - 더 명확한 방향성"""
        cvd = indicators.get('volume_delta', {})
        smart_money = indicators.get('smart_money', {})
        
        bullish_signals = 0
        bearish_signals = 0
        
        # CVD 체크 (가중치 2)
        cvd_ratio = cvd.get('cvd_ratio', 0)
        if cvd_ratio > 15:
            bullish_signals += 2
        elif cvd_ratio > 5:
            bullish_signals += 1
        elif cvd_ratio < -15:
            bearish_signals += 2
        elif cvd_ratio < -5:
            bearish_signals += 1
        
        # 스마트머니 체크 (가중치 2)
        net_flow = smart_money.get('net_flow', 0)
        if net_flow > 5:
            bullish_signals += 2
        elif net_flow > 2:
            bullish_signals += 1
        elif net_flow < -5:
            bearish_signals += 2
        elif net_flow < -2:
            bearish_signals += 1
        
        # Fear & Greed 체크 (가중치 1.5)
        if 'fear_greed' in market_data and market_data['fear_greed']:
            fng_value = market_data['fear_greed'].get('value', 50)
            if fng_value > 75:
                bullish_signals += 1.5
            elif fng_value > 60:
                bullish_signals += 0.5
            elif fng_value < 25:
                bearish_signals += 1.5
            elif fng_value < 40:
                bearish_signals += 0.5
        
        # 명확한 방향성 제시
        if bullish_signals >= bearish_signals + 2:
            return "**시장 심리 종합 평가**: 매수 심리 압도적 우위로 롱 포지션 적극 권장"
        elif bullish_signals > bearish_signals:
            return "**시장 심리 종합 평가**: 긍정적 심리 우세로 롱 진입이 유리하다"
        elif bearish_signals >= bullish_signals + 2:
            return "**시장 심리 종합 평가**: 매도 심리 압도적 우위로 숏 포지션 적극 권장"
        elif bearish_signals > bullish_signals:
            return "**시장 심리 종합 평가**: 부정적 심리 우세로 숏 진입이 유리하다"
        else:
            return "**시장 심리 종합 평가**: 심리 지표 중립, 기술적 지표 우선 고려 필요"
    
    def _format_trading_signals(self, indicators: dict) -> str:
        """롱/숏 신호 분석 - 더 명확한 신호"""
        composite = indicators.get('composite_signal', {})
        scores = composite.get('scores', {})
        total_score = composite.get('total_score', 0)
        
        # 신호 색상과 강도 결정
        if total_score >= 5:
            signal_emoji = "🟢"
            signal = "강한 롱 신호"
        elif total_score >= 2:
            signal_emoji = "🟡"
            signal = "롱 신호"
        elif total_score <= -5:
            signal_emoji = "🔴"
            signal = "강한 숏 신호"
        elif total_score <= -2:
            signal_emoji = "🟠"
            signal = "숏 신호"
        else:
            signal_emoji = "⚪"
            signal = "중립 (방향성 부재)"
        
        lines = [
            f"{signal_emoji} **종합 신호**: {signal} (신뢰도 {composite.get('confidence', 50):.0f}%)",
            "",
            "📊 **세부 점수** (±10점):"
        ]
        
        # 점수별 정렬 (절대값 기준)
        sorted_scores = sorted(scores.items(), key=lambda x: abs(x[1]), reverse=True)
        
        for indicator, score in sorted_scores:
            # 점수 표시 간소화
            lines.append(f"• {indicator:15s}: {score:+.1f}")
        
        lines.extend([
            "",
            f"📍 **최종 점수**: {total_score:+.1f}/10",
            f"📍 **추천 액션**: {self._get_clear_action(total_score)}",
            f"📍 **포지션 크기**: {composite.get('position_size', '표준')}"
        ])
        
        return '\n'.join(lines)
    
    def _get_clear_action(self, score: float) -> str:
        """명확한 액션 제시"""
        if score >= 5:
            return "즉시 롱 진입 (전체 자금의 30-40%)"
        elif score >= 3:
            return "롱 진입 (전체 자금의 20-30%)"
        elif score >= 1:
            return "소량 롱 테스트 (전체 자금의 10-15%)"
        elif score <= -5:
            return "즉시 숏 진입 (전체 자금의 30-40%)"
        elif score <= -3:
            return "숏 진입 (전체 자금의 20-30%)"
        elif score <= -1:
            return "소량 숏 테스트 (전체 자금의 10-15%)"
        else:
            return "관망 (명확한 신호 대기)"
    
    async def _format_strategy_recommendation(self, market_data: dict, indicators: dict) -> str:
        """구체적 전략 제안"""
        composite = indicators.get('composite_signal', {})
        total_score = composite.get('total_score', 0)
        current_price = market_data.get('current_price', 0)
        volatility = market_data.get('volatility', 0)
        
        # 변동성 기반 진입 범위 조정
        if volatility > 5:
            entry_range = 0.008  # 0.8%
        elif volatility > 3:
            entry_range = 0.005  # 0.5%
        else:
            entry_range = 0.003  # 0.3%
        
        if self.openai_client:
            # GPT 기반 전략 생성
            try:
                # 주요 지표 요약
                summary = {
                    '신호': self._get_clear_action(total_score),
                    '점수': total_score,
                    '현재가': current_price,
                    '변동성': volatility,
                    '펀딩비': indicators.get('funding_analysis', {}).get('current_rate', 0),
                    'OI변화': indicators.get('oi_analysis', {}).get('oi_change_percent', 0),
                    'CVD': indicators.get('volume_delta', {}).get('cvd_ratio', 0),
                    '리스크': indicators.get('risk_metrics', {}).get('risk_level', '보통')
                }
                
                prompt = f"""
비트코인 선물 트레이더를 위한 구체적 전략을 제시하세요:

현재 상황:
- 가격: ${summary['현재가']:,.0f}
- 종합 점수: {summary['점수']:.1f} (강한 신호: ±5 이상)
- 변동성: {summary['변동성']:.1f}%
- 펀딩비: {summary['펀딩비']:+.3%}
- OI 변화: {summary['OI변화']:+.1f}%
- CVD: {summary['CVD']:+.1f}%
- 리스크: {summary['리스크']}

다음을 포함하여 5줄로 작성:
1. 진입 방향과 이유 (점수 기반)
2. 구체적 진입가 범위 (현재가 기준 ±{entry_range*100:.1f}%)
3. 손절가 설정 (변동성 고려)
4. 목표가 (1차, 2차)
5. 주의사항

번호를 붙여서 각 항목을 명확히 구분하세요.
중립인 경우 관망을 권하되 돌파/이탈 가격을 명시하세요.
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "당신은 명확한 방향성을 제시하는 선물 트레이딩 전문가입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.3
                )
                
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                self.logger.error(f"GPT 전략 생성 실패: {e}")
        
        # 규칙 기반 전략 (더 명확한 방향성)
        if total_score >= 5:
            return f"""1. 강한 상승 신호 확인, 즉시 롱 진입 권장
2. 진입가 범위: ${current_price * (1-entry_range):,.0f} ~ ${current_price:,.0f}
3. 손절가: ${current_price * 0.98:,.0f} (-2%)
4. 목표가: 1차 ${current_price * 1.02:,.0f} (+2%), 2차 ${current_price * 1.04:,.0f} (+4%)
5. 주의: 과열 구간 진입 시 분할 익절 필수"""
        
        elif total_score >= 2:
            return f"""1. 상승 우위 확인, 신중한 롱 진입 권장
2. 진입가 범위: ${current_price * (1-entry_range):,.0f} ~ ${current_price * 0.998:,.0f}
3. 손절가: ${current_price * 0.985:,.0f} (-1.5%)
4. 목표가: 1차 ${current_price * 1.015:,.0f} (+1.5%), 2차 ${current_price * 1.025:,.0f} (+2.5%)
5. 주의: 저항선 근처 도달 시 일부 익절 고려"""
        
        elif total_score <= -5:
            return f"""1. 강한 하락 신호 확인, 즉시 숏 진입 권장
2. 진입가 범위: ${current_price:,.0f} ~ ${current_price * (1+entry_range):,.0f}
3. 손절가: ${current_price * 1.02:,.0f} (+2%)
4. 목표가: 1차 ${current_price * 0.98:,.0f} (-2%), 2차 ${current_price * 0.96:,.0f} (-4%)
5. 주의: 과매도 구간 진입 시 분할 익절 필수"""
        
        elif total_score <= -2:
            return f"""1. 하락 우위 확인, 신중한 숏 진입 권장
2. 진입가 범위: ${current_price * 1.002:,.0f} ~ ${current_price * (1+entry_range):,.0f}
3. 손절가: ${current_price * 1.015:,.0f} (+1.5%)
4. 목표가: 1차 ${current_price * 0.985:,.0f} (-1.5%), 2차 ${current_price * 0.975:,.0f} (-2.5%)
5. 주의: 지지선 근처 도달 시 일부 익절 고려"""
        
        else:
            return f"""1. 방향성 부재로 관망 권장, 돌파/이탈 대기
2. 상방 돌파: ${current_price * 1.008:,.0f} 이상 확정 시 롱
3. 하방 이탈: ${current_price * 0.992:,.0f} 이하 확정 시 숏
4. 목표: 돌파/이탈 방향으로 1.5~2% 수익
5. 주의: 가짜 돌파 주의, 거래량 확인 필수"""
    
    async def _format_risk_assessment(self, market_data: dict, indicators: dict) -> str:
        """리스크 평가 - 동적 생성"""
        risk = indicators.get('risk_metrics', {})
        liquidations = indicators.get('liquidation_analysis', {})
        
        # 계정 정보 가져오기
        position_info = await self._get_position_info()
        account_info = await self._get_account_info()
        
        # 기본 리스크 정보
        lines = [
            f"• **종합 리스크**: {risk.get('risk_level', '보통')} (점수 {risk.get('risk_score', 0)}/10)",
            f"• **변동성 리스크**: {risk.get('volatility_risk', '보통')}",
            f"• **펀딩비 리스크**: {risk.get('funding_risk', '보통')}"
        ]
        
        # 포지션별 맞춤 리스크 평가
        if position_info.get('has_position'):
            side = position_info.get('side', '')
            entry_price = position_info.get('entry_price', 0)
            current_price = market_data.get('current_price', 0)
            liquidation_price = position_info.get('liquidation_price', 0)
            
            # 청산까지 거리
            if liquidation_price > 0:
                if side == '롱':
                    liq_distance = ((current_price - liquidation_price) / current_price) * 100
                else:
                    liq_distance = ((liquidation_price - current_price) / current_price) * 100
                
                if liq_distance < 5:
                    lines.append(f"• ⚠️ **청산 경고**: 청산가까지 {liq_distance:.1f}%만 남음!")
                    lines.append("• **긴급 대응**: 즉시 포지션 축소 또는 증거금 추가 필요")
                elif liq_distance < 10:
                    lines.append(f"• **청산 주의**: 청산가까지 {liq_distance:.1f}% 여유")
                    lines.append("• **권장 대응**: 일부 포지션 정리 고려")
                else:
                    lines.append(f"• **청산 안전**: 청산가까지 {liq_distance:.1f}% 여유")
        else:
            # 포지션 없을 때
            total_equity = account_info.get('total_equity', 0)
            if total_equity > 0:
                # 권장 포지션 크기
                if risk.get('risk_level') == '높음':
                    recommended_size = total_equity * 0.1  # 10%
                    lines.append(f"• **권장 포지션**: ${recommended_size:.0f} (총 자산의 10%)")
                elif risk.get('risk_level') == '낮음':
                    recommended_size = total_equity * 0.3  # 30%
                    lines.append(f"• **권장 포지션**: ${recommended_size:.0f} (총 자산의 30%)")
                else:
                    recommended_size = total_equity * 0.2  # 20%
                    lines.append(f"• **권장 포지션**: ${recommended_size:.0f} (총 자산의 20%)")
        
        # 청산 레벨
        if liquidations and 'long_liquidation_levels' in liquidations:
            lines.extend([
                "",
                "⚡ **주요 청산 레벨**:",
                f"• 롱 청산: ${liquidations['long_liquidation_levels'][0]:,.0f} (3% 하락)",
                f"• 숏 청산: ${liquidations['short_liquidation_levels'][0]:,.0f} (3% 상승)"
            ])
        
        return '\n'.join(lines)
    
    async def _format_12h_prediction(self, market_data: dict, indicators: dict) -> str:
        """향후 12시간 예측 - 더 정확한 확률"""
        composite = indicators.get('composite_signal', {})
        total_score = composite.get('total_score', 0)
        current_price = market_data.get('current_price', 0)
        
        # 더 정밀한 확률 계산
        base_up = 33
        base_down = 33
        base_sideways = 34
        
        # 점수 기반 확률 조정 (더 극단적으로)
        if total_score > 0:
            up_bonus = min(total_score * 8, 40)  # 최대 +40%
            up_prob = base_up + up_bonus
            down_prob = max(10, base_down - up_bonus * 0.7)
            sideways_prob = 100 - up_prob - down_prob
        elif total_score < 0:
            down_bonus = min(abs(total_score) * 8, 40)  # 최대 +40%
            down_prob = base_down + down_bonus
            up_prob = max(10, base_up - down_bonus * 0.7)
            sideways_prob = 100 - up_prob - down_prob
        else:
            up_prob = base_up
            down_prob = base_down
            sideways_prob = base_sideways
        
        # 추가 요인 고려
        funding = indicators.get('funding_analysis', {})
        if funding.get('current_rate', 0) > 0.001:  # 펀딩비 과열
            down_prob += 5
            up_prob -= 5
        elif funding.get('current_rate', 0) < -0.001:
            up_prob += 5
            down_prob -= 5
        
        # 정규화
        total = up_prob + down_prob + sideways_prob
        up_prob = int(up_prob / total * 100)
        down_prob = int(down_prob / total * 100)
        sideways_prob = 100 - up_prob - down_prob
        
        lines = [
            f"**상승**: {up_prob}% / **횡보**: {sideways_prob}% / **하락**: {down_prob}%",
            "",
            "📌 **전략 제안**:"
        ]
        
        # 명확한 전략 제안
        if up_prob >= 60:
            lines.append(f"높은 상승 확률로 지지선 ${current_price * 0.985:,.0f} 위에서는 롱 유지")
            lines.append(f"저항선 ${current_price * 1.02:,.0f} 돌파 시 추가 상승 가속화 예상")
        elif down_prob >= 60:
            lines.append(f"높은 하락 확률로 저항선 ${current_price * 1.015:,.0f} 아래에서는 숏 유지")
            lines.append(f"지지선 ${current_price * 0.98:,.0f} 이탈 시 추가 하락 가속화 예상")
        elif up_prob > down_prob + 10:
            lines.append(f"상승 우위로 ${current_price * 0.992:,.0f} 위에서 롱 포지션 유리")
            lines.append(f"목표가 ${current_price * 1.015:,.0f} 도달 시 일부 익절 권장")
        elif down_prob > up_prob + 10:
            lines.append(f"하락 우위로 ${current_price * 1.008:,.0f} 아래에서 숏 포지션 유리")
            lines.append(f"목표가 ${current_price * 0.985:,.0f} 도달 시 일부 익절 권장")
        else:
            lines.append(f"${current_price * 0.99:,.0f} ~ ${current_price * 1.01:,.0f} 박스권 횡보 예상")
            lines.append("명확한 이탈 방향 확인 후 진입 권장")
        
        return '\n'.join(lines)
    
    def _format_validation(self) -> str:
        """이전 예측 검증"""
        if not self.last_prediction:
            return "• 이전 예측 기록 없음"
        
        # 실제 검증 로직 구현 필요
        return f"""• {self.last_prediction.get('time', '이전')} 리포트 "{self.last_prediction.get('signal', '중립')}" 예상 → 실제 ±{abs(self.last_prediction.get('actual_change', 1.0)):.1f}% 등락 → {"✅ 예측 적중" if self.last_prediction.get('accurate', False) else "❌ 예측 실패"}"""
    
    async def _format_profit_loss(self) -> str:
        """손익 현황"""
        try:
            position_info = await self._get_position_info()
            account_info = await self._get_account_info()
            today_pnl = await self._get_today_realized_pnl()
            
            lines = []
            
            # 포지션 정보
            if position_info.get('has_position'):
                side = position_info.get('side')
                entry = position_info.get('entry_price', 0)
                current = position_info.get('current_price', 0)
                pnl_rate = position_info.get('pnl_rate', 0) * 100
                
                lines.append(f"• **현재 포지션**: {side} (진입 ${entry:,.0f}, {pnl_rate:+.1f}%)")
                lines.append(f"• **미실현 손익**: {self._format_currency(position_info.get('unrealized_pnl', 0), False)}")
            else:
                lines.append("• **현재 포지션**: 없음")
            
            # 실현 손익
            lines.append(f"• **오늘 실현**: {self._format_currency(today_pnl, False)}")
            
            return '\n'.join(lines)
            
        except Exception as e:
            self.logger.error(f"손익 포맷팅 실패: {e}")
            return "• 손익 정보 조회 실패"
    
    async def _generate_mental_care(self, market_data: dict, indicators: dict) -> str:
        """멘탈 케어 - 선물 거래자 특화"""
        try:
            account_info = await self._get_account_info()
            position_info = await self._get_position_info()
            today_pnl = await self._get_today_realized_pnl()
            weekly_profit = await self._get_weekly_profit()
            
            # 시장 상황 고려
            signal = indicators.get('composite_signal', {}).get('signal', '중립')
            risk_level = indicators.get('risk_metrics', {}).get('risk_level', '보통')
            
            # 기본 멘탈 케어
            message = await self.mental_care.generate_profit_mental_care(
                account_info, position_info, today_pnl, weekly_profit
            )
            
            # 형식에 맞게 수정
            if self.openai_client:
                return f"""GPT는 사용자의 자산 규모, 포지션 상태, 실현·미실현 수익, 최근 수익률 추이, 감정 흐름을 실시간 분석하여
충동 매매를 억제할 수 있도록 매번 다른 말투로 코멘트를 생성합니다.
수익 시엔 과열을 막고, 손실 시엔 복구 욕구를 잠재우며, 반복 매매를 피할 수 있도록 설계되어 있습니다.
어떠한 문장도 하드코딩되어 있지 않으며, 사용자의 상태에 맞는 심리적 설득 효과를 유도합니다.

{message}"""
            
            return message
            
        except Exception as e:
            self.logger.error(f"멘탈 케어 생성 실패: {e}")
            return '"선물 거래는 높은 변동성과의 싸움입니다. 감정을 배제하고 시스템을 따르세요. 📊"'
    
    def _save_prediction(self, indicators: dict):
        """예측 저장"""
        composite = indicators.get('composite_signal', {})
        self.last_prediction = {
            'time': datetime.now().strftime('%m-%d %H:%M'),
            'signal': composite.get('signal', '중립'),
            'score': composite.get('total_score', 0),
            'confidence': composite.get('confidence', 50),
            'action': composite.get('action', '관망')
        }
