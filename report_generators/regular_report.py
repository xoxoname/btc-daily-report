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
            risk_text = self._format_risk_assessment(indicators)
            
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

📌 시장 이벤트 및 주요 속보
{events_text}

━━━━━━━━━━━━━━━━━━━

📊 선물 시장 핵심 지표
{futures_analysis}

━━━━━━━━━━━━━━━━━━━

📉 기술적 분석
{technical_text}

━━━━━━━━━━━━━━━━━━━

🧠 시장 심리 및 포지셔닝
{sentiment_text}

━━━━━━━━━━━━━━━━━━━

🎯 롱/숏 신호 분석
{signal_text}

━━━━━━━━━━━━━━━━━━━

📌 전략 제안
{strategy_text}

━━━━━━━━━━━━━━━━━━━

⚠️ 리스크 평가
{risk_text}

━━━━━━━━━━━━━━━━━━━

🔮 향후 12시간 예측
{prediction_text}

━━━━━━━━━━━━━━━━━━━

📊 예측 검증
{validation_text}

━━━━━━━━━━━━━━━━━━━

💰 손익 현황
{pnl_text}

━━━━━━━━━━━━━━━━━━━

🧠 멘탈 케어
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
        """시장 이벤트 - 통합 뉴스 분석 사용"""
        try:
            recent_news = await self.data_collector.get_recent_news(hours=6) if self.data_collector else []
            
            if not recent_news:
                return "• 현재 주요 시장 이벤트 없음"
            
            # 통합 포맷팅 함수 사용
            formatted = await self.format_news_with_time(recent_news, max_items=4)
            
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
            f"• 현재가: {self._format_price_with_change(current_price, change_24h)} (Bitget BTCUSDT)",
            f"• 펀딩비: {funding.get('current_rate', 0):+.3%} (연환산 {funding.get('annual_rate', 0):+.1f}%) → {funding.get('signal', '중립')}",
            f"• 미결제약정: {oi.get('oi_change_percent', 0):+.1f}% 변화 → {oi.get('price_divergence', '중립')}",
            f"• 선물 베이시스: {basis.get('rate', 0):+.3f}% → {basis.get('signal', '중립')}",
            f"• 롱/숏 비율: {ls_ratio.get('long_ratio', 50):.0f}:{ls_ratio.get('short_ratio', 50):.0f} → {ls_ratio.get('signal', '균형')}",
            f"• 청산 위험: {liquidations.get('liquidation_pressure', '중립')}"
        ]
        
        # Fear & Greed Index 추가
        if 'fear_greed' in market_data and market_data['fear_greed']:
            fng = market_data['fear_greed']
            lines.append(f"• 공포탐욕지수: {fng.get('value', 50)}/100 ({fng.get('value_classification', 'Neutral')})")
        
        # 종합 평가 추가
        lines.append("")
        lines.append(self._generate_futures_summary(indicators))
        
        return '\n'.join(lines)
    
    def _generate_futures_summary(self, indicators: dict) -> str:
        """선물 지표 종합 평가"""
        composite = indicators.get('composite_signal', {})
        signal = composite.get('signal', '중립')
        
        if '강한 롱' in signal:
            return "핵심 지표 분석 종합 평가 요약: 펀딩비 안정적이고 매수 압력 우세로 롱이 유리하다"
        elif '강한 숏' in signal:
            return "핵심 지표 분석 종합 평가 요약: 매도 압력 증가와 과열 신호로 숏이 유리하다"
        elif '롱' in signal:
            return "핵심 지표 분석 종합 평가 요약: 전반적으로 롱 신호가 우세하나 신중한 접근 필요"
        elif '숏' in signal:
            return "핵심 지표 분석 종합 평가 요약: 숏 신호가 나타나고 있으나 강도는 보통 수준"
        else:
            return "핵심 지표 분석 종합 평가 요약: 명확한 방향성 없이 중립 상태 지속"
    
    async def _format_technical_analysis(self, market_data: dict, indicators: dict) -> str:
        """기술적 분석 - 선물 관점"""
        technical = indicators.get('technical', {})
        market_profile = indicators.get('market_profile', {})
        volume_delta = indicators.get('volume_delta', {})
        
        lines = [
            f"• 24H 고/저: ${market_data.get('high_24h', 0):,.0f} / ${market_data.get('low_24h', 0):,.0f}",
            f"• 24H 변동: {market_data.get('change_24h', 0):+.1%} | 거래량: {market_data.get('volume_24h', 0):,.0f} BTC"
        ]
        
        # 거래량 분석 추가
        if volume_delta and volume_delta.get('signal'):
            buy_vol = volume_delta.get('buy_volume', 0)
            sell_vol = volume_delta.get('sell_volume', 0)
            if buy_vol > sell_vol * 1.1:
                lines.append("• 거래량 증가, 매수 체결 우세 → 롱 지지")
            elif sell_vol > buy_vol * 1.1:
                lines.append("• 거래량 증가, 매도 체결 우세 → 숏 지지")
            else:
                lines.append("• 거래량 균형 상태")
        
        # RSI
        if 'rsi' in technical:
            rsi_data = technical['rsi']
            rsi_val = rsi_data.get('value', 50)
            if rsi_val < 40:
                lines.append(f"• RSI(14): {rsi_val:.1f} → 상승 여력 존재")
            elif rsi_val > 60:
                lines.append(f"• RSI(14): {rsi_val:.1f} → 과열 주의")
            else:
                lines.append(f"• RSI(14): {rsi_val:.1f} → 중립")
        
        # 마켓 프로파일
        if market_profile and 'poc' in market_profile:
            poc = market_profile['poc']
            current = market_data.get('current_price', 0)
            
            if current > poc * 1.01:
                poc_signal = "롱 강세 신호"
            elif current < poc * 0.99:
                poc_signal = "숏 압력 증가"
            else:
                poc_signal = "균형점 근처"
            
            lines.append(f"• POC (Point of Control): ${poc:,.0f} → {poc_signal}")
            lines.append(f"• Value Area: ${market_profile['value_area_low']:,.0f} ~ ${market_profile['value_area_high']:,.0f}")
            lines.append(f"• 현재 위치: {market_profile.get('price_position', '중립')}")
        
        # 기술적 분석 종합
        lines.append("")
        lines.append(self._generate_technical_summary(market_data, indicators))
        
        return '\n'.join(lines)
    
    def _generate_technical_summary(self, market_data: dict, indicators: dict) -> str:
        """기술적 분석 종합 평가"""
        technical = indicators.get('technical', {})
        volume_delta = indicators.get('volume_delta', {})
        
        bullish_count = 0
        bearish_count = 0
        
        # RSI 체크
        if technical.get('rsi', {}).get('signal') == '과매도':
            bullish_count += 1
        elif technical.get('rsi', {}).get('signal') == '과매수':
            bearish_count += 1
        
        # 거래량 체크
        if '매수 우세' in volume_delta.get('signal', ''):
            bullish_count += 1
        elif '매도 우세' in volume_delta.get('signal', ''):
            bearish_count += 1
        
        # 가격 위치 체크
        market_profile = indicators.get('market_profile', {})
        if 'Value Area 하단' in market_profile.get('price_position', ''):
            bullish_count += 1
        elif 'Value Area 상단' in market_profile.get('price_position', ''):
            bearish_count += 1
        
        if bullish_count > bearish_count:
            return "기술적 분석 종합 평가 요약: 주요 지표들이 상승 신호를 보이며 롱이 유리하다"
        elif bearish_count > bullish_count:
            return "기술적 분석 종합 평가 요약: 기술적 지표들이 하락 압력을 시사하여 숏이 유리하다"
        else:
            return "기술적 분석 종합 평가 요약: 기술적 지표들이 혼재되어 방향성이 불명확하다"
    
    async def _format_market_sentiment(self, market_data: dict, indicators: dict) -> str:
        """시장 심리 및 포지셔닝"""
        cvd = indicators.get('volume_delta', {})
        smart_money = indicators.get('smart_money', {})
        
        lines = []
        
        # CVD (누적 거래량 델타)
        if cvd:
            lines.append(f"• CVD: {cvd.get('cvd_ratio', 0):+.1f}% → {cvd.get('signal', '균형')}")
            lines.append(f"• 매수/매도 거래량: {cvd.get('buy_volume', 0):,.0f} / {cvd.get('sell_volume', 0):,.0f} BTC")
        
        # 스마트머니
        if smart_money:
            lines.append(f"• 대형 거래: 매수 {smart_money.get('large_buy_count', 0)}건 vs 매도 {smart_money.get('large_sell_count', 0)}건")
            lines.append(f"• 스마트머니 플로우: {smart_money.get('net_flow', 0):+.1f} BTC → {smart_money.get('signal', '중립')}")
        
        # 시장 개요 (CoinGecko)
        if 'market_overview' in market_data and market_data['market_overview']:
            overview = market_data['market_overview']
            lines.append(f"• BTC 도미넌스: {overview.get('btc_dominance', 0):.1f}%")
            lines.append(f"• 전체 시총 변화: {overview.get('market_cap_change_24h', 0):+.1f}%")
        
        # 시장 심리 종합
        lines.append("")
        lines.append(self._generate_sentiment_summary(indicators, market_data))
        
        return '\n'.join(lines) if lines else "• 센티먼트 데이터 수집 중"
    
    def _generate_sentiment_summary(self, indicators: dict, market_data: dict) -> str:
        """시장 심리 종합 평가"""
        cvd = indicators.get('volume_delta', {})
        smart_money = indicators.get('smart_money', {})
        
        bullish_signals = 0
        bearish_signals = 0
        
        # CVD 체크
        if cvd.get('cvd_ratio', 0) > 10:
            bullish_signals += 1
        elif cvd.get('cvd_ratio', 0) < -10:
            bearish_signals += 1
        
        # 스마트머니 체크
        if smart_money.get('net_flow', 0) > 5:
            bullish_signals += 1
        elif smart_money.get('net_flow', 0) < -5:
            bearish_signals += 1
        
        # Fear & Greed 체크
        if 'fear_greed' in market_data and market_data['fear_greed']:
            fng_value = market_data['fear_greed'].get('value', 50)
            if fng_value > 70:
                bullish_signals += 1
            elif fng_value < 30:
                bearish_signals += 1
        
        if bullish_signals > bearish_signals:
            return "시장 심리 종합 평가 요약: 매수 심리가 우세하여 롱이 유리하다"
        elif bearish_signals > bullish_signals:
            return "시장 심리 종합 평가 요약: 매도 심리가 강해 숏이 유리하다"
        else:
            return "시장 심리 종합 평가 요약: 시장 심리가 중립적이며 관망세가 우세하다"
    
    def _format_trading_signals(self, indicators: dict) -> str:
        """롱/숏 신호 분석"""
        composite = indicators.get('composite_signal', {})
        scores = composite.get('scores', {})
        
        # 신호 색상 결정
        signal = composite.get('signal', '중립')
        if '강한 롱' in signal:
            signal_emoji = "🟢"
        elif '롱' in signal:
            signal_emoji = "🟡"
        elif '강한 숏' in signal:
            signal_emoji = "🔴"
        elif '숏' in signal:
            signal_emoji = "🟠"
        else:
            signal_emoji = "⚪"
        
        lines = [
            f"{signal_emoji} 종합 신호: {signal} (신뢰도 {composite.get('confidence', 50):.0f}%)",
            "",
            "📊 세부 점수 (±10점):"
        ]
        
        # 점수별 정렬 (절대값 기준)
        sorted_scores = sorted(scores.items(), key=lambda x: abs(x[1]), reverse=True)
        
        for indicator, score in sorted_scores:
            # 점수 표시 간소화
            lines.append(f"• {indicator:15s}: {score:+.1f}")
        
        lines.extend([
            "",
            f"📍 최종 점수: {composite.get('total_score', 0):+.1f}/10",
            f"📍 추천 액션: {composite.get('action', '관망')}",
            f"📍 포지션 크기: {composite.get('position_size', '표준')}"
        ])
        
        return '\n'.join(lines)
    
    async def _format_strategy_recommendation(self, market_data: dict, indicators: dict) -> str:
        """구체적 전략 제안"""
        composite = indicators.get('composite_signal', {})
        signal = composite.get('signal', '중립')
        current_price = market_data.get('current_price', 0)
        change_24h = market_data.get('change_24h', 0)
        
        if self.openai_client:
            # GPT 기반 전략 생성
            try:
                # 주요 지표 요약
                summary = {
                    '신호': signal,
                    '점수': composite.get('total_score', 0),
                    '펀딩비': indicators.get('funding_analysis', {}).get('current_rate', 0),
                    'OI변화': indicators.get('oi_analysis', {}).get('oi_change_percent', 0),
                    'CVD': indicators.get('volume_delta', {}).get('cvd_ratio', 0),
                    '리스크': indicators.get('risk_metrics', {}).get('risk_level', '보통')
                }
                
                prompt = f"""
비트코인 선물 트레이더를 위한 구체적 전략을 제시하세요:

현재 상황:
- 가격: ${current_price:,.0f} (24시간 변동: {change_24h*100:+.2f}%)
- 종합 신호: {summary['신호']} (점수 {summary['점수']:.1f})
- 펀딩비: {summary['펀딩비']:+.3%}
- OI 변화: {summary['OI변화']:+.1f}%
- CVD: {summary['CVD']:+.1f}%
- 리스크: {summary['리스크']}

다음을 포함하여 5줄 이내로 작성:
1. 진입 방향 (롱/숏/관망)
2. 구체적 진입가 범위
3. 손절가 설정
4. 목표가 (1차, 2차)
5. 주의사항

번호를 붙여서 각 항목을 명확히 구분하세요.
레버리지 언급은 절대 금지
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "당신은 리스크 관리를 최우선으로 하는 선물 트레이딩 전문가입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.3
                )
                
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                self.logger.error(f"GPT 전략 생성 실패: {e}")
        
        # 규칙 기반 전략
        if '강한 롱' in signal:
            return f"""1. 진입: 현재가 근처 또는 단기 조정 시 롱 진입
2. 진입가 범위: ${current_price * 0.995:,.0f} ~ ${current_price * 1.002:,.0f}
3. 손절가: ${current_price * 0.985:,.0f} (-1.5%)
4. 목표가: 1차 ${current_price * 1.015:,.0f} (+1.5%), 2차 ${current_price * 1.03:,.0f} (+3%)
5. 주의: 펀딩비 과열 시 익절 타이밍 중요"""
        
        elif '강한 숏' in signal:
            return f"""1. 진입: 현재가 근처 또는 단기 반등 시 숏 진입
2. 진입가 범위: ${current_price * 0.998:,.0f} ~ ${current_price * 1.005:,.0f}
3. 손절가: ${current_price * 1.015:,.0f} (+1.5%)
4. 목표가: 1차 ${current_price * 0.985:,.0f} (-1.5%), 2차 ${current_price * 0.97:,.0f} (-3%)
5. 주의: 숏 스퀴즈 가능성 항상 염두"""
        
        else:
            return f"""1. 현재 명확한 방향성 부재, 관망 권장
2. 상방 돌파 대기: ${current_price * 1.01:,.0f} 이상 확정 시 롱
3. 하방 이탈 대기: ${current_price * 0.99:,.0f} 이하 확정 시 숏
4. 목표: 돌파/이탈 방향으로 1.5~2% 수익
5. 주의: 변동성 확대 시점까지 인내심 필요"""
    
    def _format_risk_assessment(self, indicators: dict) -> str:
        """리스크 평가"""
        risk = indicators.get('risk_metrics', {})
        liquidations = indicators.get('liquidation_analysis', {})
        
        lines = [
            f"• 종합 리스크: {risk.get('risk_level', '보통')} (점수 {risk.get('risk_score', 0)}/10)",
            f"• 변동성 리스크: {risk.get('volatility_risk', '보통')}",
            f"• 펀딩비 리스크: {risk.get('funding_risk', '보통')}",
            f"• 권장 포지션: {risk.get('position_sizing', '표준 포지션')}"
        ]
        
        # 청산 레벨
        if liquidations and 'long_liquidation_levels' in liquidations:
            lines.extend([
                "",
                "⚡ 주요 청산 레벨:",
                f"• 롱 청산: ${liquidations['long_liquidation_levels'][0]:,.0f} (3% 하락)",
                f"• 숏 청산: ${liquidations['short_liquidation_levels'][0]:,.0f} (3% 상승)"
            ])
        
        return '\n'.join(lines)
    
    async def _format_12h_prediction(self, market_data: dict, indicators: dict) -> str:
        """향후 12시간 예측"""
        composite = indicators.get('composite_signal', {})
        total_score = composite.get('total_score', 0)
        current_price = market_data.get('current_price', 0)
        
        # 확률 계산
        if total_score > 2:
            up_prob = min(60 + total_score * 5, 80)
            down_prob = max(10, 20 - total_score * 2)
        elif total_score < -2:
            up_prob = max(10, 30 + total_score * 2)
            down_prob = min(60 - total_score * 5, 80)
        else:
            up_prob = 35 + total_score * 5
            down_prob = 35 - total_score * 5
        
        sideways_prob = 100 - up_prob - down_prob
        
        lines = [
            f"상승: {up_prob}% / 횡보: {sideways_prob}% / 하락: {down_prob}%",
            "",
            "📌 전략 제안:"
        ]
        
        if up_prob > 60:
            lines.append(f"지지선 ${current_price * 0.98:,.0f} 이탈 전까지 롱 유지 / 저항선 ${current_price * 1.02:,.0f} 돌파 시 추가 상승 가능성")
        elif down_prob > 60:
            lines.append(f"저항선 ${current_price * 1.02:,.0f} 돌파 전까지 숏 유지 / 지지선 ${current_price * 0.98:,.0f} 이탈 시 추가 하락 가능성")
        else:
            lines.append(f"${current_price * 0.98:,.0f} ~ ${current_price * 1.02:,.0f} 박스권 내 횡보 예상 / 이탈 방향 주시")
        
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
                
                lines.append(f"• 현재 포지션: {side} (진입 ${entry:,.0f}, {pnl_rate:+.1f}%)")
                lines.append(f"• 미실현 손익: {self._format_currency(position_info.get('unrealized_pnl', 0), False)}")
            else:
                lines.append("• 현재 포지션: 없음")
            
            # 실현 손익
            lines.append(f"• 오늘 실현: {self._format_currency(today_pnl, False)}")
            
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
