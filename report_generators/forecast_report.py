# report_generators/forecast_report.py
from .base_generator import BaseReportGenerator
from .mental_care import MentalCareGenerator
import asyncio
from datetime import datetime, timedelta
import pytz

class ForecastReportGenerator(BaseReportGenerator):
    """선물 롱/숏 단기 예측 리포트"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        self.mental_care = MentalCareGenerator(self.openai_client)
    
    async def generate_report(self) -> str:
        """📈 선물 롱/숏 단기 예측"""
        try:
            current_time = self._get_current_time_kst()
            
            # 데이터 수집
            market_data = await self._collect_all_data()
            
            # 추가 시장 데이터
            if self.data_collector:
                comprehensive_data = await self.data_collector.get_comprehensive_market_data()
                market_data.update(comprehensive_data)
            
            # 지표 시스템 설정
            if self.bitget_client and hasattr(self.indicator_system, 'set_bitget_client'):
                self.indicator_system.set_bitget_client(self.bitget_client)
                
            indicators = await self.indicator_system.calculate_all_indicators(market_data)
            
            # AI 기반 단기 예측
            if self.openai_client:
                forecast_analysis = await self._generate_ai_forecast(market_data, indicators)
            else:
                forecast_analysis = self._generate_basic_forecast(market_data, indicators)
            
            # 섹션별 포맷
            events_text = await self._format_upcoming_events()
            key_levels = self._format_key_levels(market_data, indicators)
            quick_analysis = await self._format_quick_analysis(indicators, market_data)
            prediction_text = self._format_predictions(indicators, forecast_analysis)
            entry_points = await self._format_entry_strategy(market_data, indicators, forecast_analysis)
            risk_alerts = self._format_risk_alerts(indicators)
            pnl_summary = await self._format_profit_summary()
            mental_text = await self._generate_focused_mental_care(indicators)
            
            report = f"""📈 선물 단기 예측 (12시간)
📅 작성 시각: {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

🔔 주요 예정 이벤트
{events_text}

━━━━━━━━━━━━━━━━━━━

📍 핵심 가격 레벨
{key_levels}

━━━━━━━━━━━━━━━━━━━

⚡ 퀵 분석 (선물 시장)
{quick_analysis}

━━━━━━━━━━━━━━━━━━━

🔮 12시간 예측
{prediction_text}

━━━━━━━━━━━━━━━━━━━

🎯 진입 전략
{entry_points}

━━━━━━━━━━━━━━━━━━━

⚠️ 리스크 알림
{risk_alerts}

━━━━━━━━━━━━━━━━━━━

💰 현재 상태
{pnl_summary}

━━━━━━━━━━━━━━━━━━━

🧠 트레이딩 조언
{mental_text}"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"예측 리포트 생성 실패: {str(e)}")
            return "❌ 예측 분석 중 오류가 발생했습니다."
    
    async def _format_upcoming_events(self) -> str:
        """선물 시장에 영향을 줄 이벤트"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            events = []
            
            # 펀딩비 시간 체크 (UTC 기준 00:00, 08:00, 16:00)
            utc_now = now.astimezone(pytz.UTC)
            hours_to_funding = 8 - (utc_now.hour % 8)
            if hours_to_funding <= 2:
                events.append(f"• {hours_to_funding}시간 후 펀딩비 정산 → 포지션 조정 예상")
            
            # 주요 시장 시간
            est = pytz.timezone('US/Eastern')
            est_now = now.astimezone(est)
            
            if 8 <= est_now.hour < 9:
                events.append("• 1시간 내 미국 시장 개장 → 변동성 증가")
            elif 13 <= est_now.hour < 14:
                events.append("• FOMC 의사록 공개 임박 → 급변동 대비")
            
            # 주말 체크
            if now.weekday() == 4 and now.hour >= 20:
                events.append("• 주말 진입 → 유동성 감소, 갭 리스크")
            elif now.weekday() == 6 and now.hour >= 20:
                events.append("• CME 선물 개장 임박 → 갭 발생 주의")
            
            # 옵션 만기
            if now.day >= 25:
                events.append("• 월말 옵션 만기 임박 → 맥스페인 영향")
            
            if not events:
                events.append("• 향후 12시간 특별 이벤트 없음")
            
            return '\n'.join(events)
            
        except Exception as e:
            self.logger.error(f"이벤트 포맷팅 오류: {e}")
            return "• 이벤트 정보 조회 중 오류"
    
    def _format_key_levels(self, market_data: dict, indicators: dict) -> str:
        """핵심 가격 레벨"""
        current_price = market_data.get('current_price', 0)
        market_profile = indicators.get('market_profile', {})
        liquidations = indicators.get('liquidation_analysis', {})
        
        lines = [
            f"• 현재가: ${current_price:,.0f}",
            f"• 일일 고/저: ${market_data.get('high_24h', 0):,.0f} / ${market_data.get('low_24h', 0):,.0f}"
        ]
        
        # 마켓 프로파일 레벨
        if market_profile and 'poc' in market_profile:
            lines.extend([
                f"• POC (최다 거래): ${market_profile['poc']:,.0f}",
                f"• Value Area: ${market_profile['value_area_low']:,.0f} ~ ${market_profile['value_area_high']:,.0f}"
            ])
        
        # 청산 레벨
        if liquidations and 'long_liquidation_levels' in liquidations:
            lines.extend([
                f"• 주요 롱 청산: ${liquidations['long_liquidation_levels'][0]:,.0f}",
                f"• 주요 숏 청산: ${liquidations['short_liquidation_levels'][0]:,.0f}"
            ])
        
        return '\n'.join(lines)
    
    async def _format_quick_analysis(self, indicators: dict, market_data: dict) -> str:
        """핵심 지표 빠른 요약"""
        composite = indicators.get('composite_signal', {})
        funding = indicators.get('funding_analysis', {})
        cvd = indicators.get('volume_delta', {})
        oi = indicators.get('oi_analysis', {})
        
        # 이모지로 상태 표시
        def get_emoji(value, thresholds):
            if value > thresholds[1]:
                return "🔴"  # 과열/위험
            elif value > thresholds[0]:
                return "🟡"  # 주의
            elif value < -thresholds[1]:
                return "🟢"  # 기회
            elif value < -thresholds[0]:
                return "🟡"  # 주의
            else:
                return "⚪"  # 중립
        
        funding_rate = funding.get('current_rate', 0) * 100
        funding_emoji = get_emoji(funding_rate, [0.5, 1.0])
        
        cvd_ratio = cvd.get('cvd_ratio', 0)
        cvd_emoji = "🟢" if cvd_ratio > 10 else "🔴" if cvd_ratio < -10 else "⚪"
        
        lines = [
            f"{funding_emoji} 펀딩: {funding_rate:+.3f}% → {funding.get('trade_bias', '중립')}",
            f"{cvd_emoji} CVD: {cvd_ratio:+.1f}% → {cvd.get('signal', '균형')}",
            f"{'🟢' if oi.get('oi_change_percent', 0) > 0 else '🔴'} OI: {oi.get('oi_change_percent', 0):+.1f}% → {oi.get('signal', '안정')}",
            f"📊 종합: {composite.get('signal', '중립')} (신뢰도 {composite.get('confidence', 50):.0f}%)"
        ]
        
        return '\n'.join(lines)
    
    async def _generate_ai_forecast(self, market_data: dict, indicators: dict) -> dict:
        """AI 기반 단기 예측"""
        try:
            composite = indicators.get('composite_signal', {})
            
            prompt = f"""
선물 트레이더를 위한 12시간 예측:

현재 상황:
- 가격: ${market_data.get('current_price', 0):,.0f}
- 종합 신호: {composite.get('signal', '중립')} (점수 {composite.get('total_score', 0):.1f}/10)
- 펀딩비: {indicators.get('funding_analysis', {}).get('current_rate', 0):+.3%}
- CVD: {indicators.get('volume_delta', {}).get('cvd_ratio', 0):+.1f}%
- OI 변화: {indicators.get('oi_analysis', {}).get('oi_change_percent', 0):+.1f}%

다음을 JSON으로 답변:
{{
    "direction": "LONG/SHORT/NEUTRAL",
    "confidence": 0-100,
    "target_high": 숫자,
    "target_low": 숫자,
    "key_support": 숫자,
    "key_resistance": 숫자,
    "entry_zone": [min, max],
    "stop_loss": 숫자,
    "risk_factors": ["factor1", "factor2"],
    "opportunities": ["opp1", "opp2"]
}}
"""
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "정확한 수치 예측을 제공하는 선물 거래 전문가"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            import json
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            self.logger.error(f"AI 예측 생성 실패: {e}")
            return self._get_default_forecast(market_data, indicators)
    
    def _get_default_forecast(self, market_data: dict, indicators: dict) -> dict:
        """기본 예측"""
        current_price = market_data.get('current_price', 0)
        composite = indicators.get('composite_signal', {})
        
        if composite.get('total_score', 0) > 2:
            return {
                "direction": "LONG",
                "confidence": min(80, 50 + composite['total_score'] * 10),
                "target_high": current_price * 1.025,
                "target_low": current_price * 0.995,
                "key_support": current_price * 0.985,
                "key_resistance": current_price * 1.015,
                "entry_zone": [current_price * 0.995, current_price * 1.002],
                "stop_loss": current_price * 0.98,
                "risk_factors": ["펀딩비 상승", "저항선 근접"],
                "opportunities": ["상승 모멘텀", "매수 우세"]
            }
        elif composite.get('total_score', 0) < -2:
            return {
                "direction": "SHORT",
                "confidence": min(80, 50 - composite['total_score'] * 10),
                "target_high": current_price * 1.005,
                "target_low": current_price * 0.975,
                "key_support": current_price * 0.985,
                "key_resistance": current_price * 1.015,
                "entry_zone": [current_price * 0.998, current_price * 1.005],
                "stop_loss": current_price * 1.02,
                "risk_factors": ["숏 스퀴즈", "지지선 근접"],
                "opportunities": ["하락 압력", "매도 우세"]
            }
        else:
            return {
                "direction": "NEUTRAL",
                "confidence": 40,
                "target_high": current_price * 1.01,
                "target_low": current_price * 0.99,
                "key_support": current_price * 0.98,
                "key_resistance": current_price * 1.02,
                "entry_zone": [current_price * 0.99, current_price * 1.01],
                "stop_loss": current_price * 0.97,
                "risk_factors": ["방향성 부재", "낮은 변동성"],
                "opportunities": ["브레이크아웃 대기", "변동성 확대 예상"]
            }
    
    def _format_predictions(self, indicators: dict, forecast: dict) -> str:
        """예측 포맷팅"""
        direction = forecast.get('direction', 'NEUTRAL')
        confidence = forecast.get('confidence', 50)
        
        # 방향성 이모지
        direction_emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"
        
        lines = [
            f"{direction_emoji} 예상 방향: {direction} (신뢰도 {confidence}%)",
            f"📊 예상 레인지: ${forecast['target_low']:,.0f} ~ ${forecast['target_high']:,.0f}",
            f"🛡️ 주요 지지: ${forecast['key_support']:,.0f}",
            f"🚧 주요 저항: ${forecast['key_resistance']:,.0f}",
            "",
            "🎯 주요 시나리오:",
        ]
        
        if direction == "LONG":
            lines.extend([
                f"• 상승: {forecast['key_resistance']:,.0f} 돌파 시 {forecast['target_high']:,.0f} 목표",
                f"• 하락: {forecast['key_support']:,.0f} 이탈 시 숏 전환 검토"
            ])
        elif direction == "SHORT":
            lines.extend([
                f"• 하락: {forecast['key_support']:,.0f} 이탈 시 {forecast['target_low']:,.0f} 목표",
                f"• 상승: {forecast['key_resistance']:,.0f} 돌파 시 롱 전환 검토"
            ])
        else:
            lines.extend([
                f"• 상방: {forecast['key_resistance']:,.0f} 돌파 관찰",
                f"• 하방: {forecast['key_support']:,.0f} 지지 확인"
            ])
        
        return '\n'.join(lines)
    
    async def _format_entry_strategy(self, market_data: dict, indicators: dict, forecast: dict) -> str:
        """구체적 진입 전략"""
        current_price = market_data.get('current_price', 0)
        direction = forecast.get('direction', 'NEUTRAL')
        entry_zone = forecast.get('entry_zone', [current_price * 0.99, current_price * 1.01])
        
        lines = []
        
        if direction == "LONG":
            lines = [
                f"🟢 롱 진입 전략:",
                f"• 진입 구간: ${entry_zone[0]:,.0f} ~ ${entry_zone[1]:,.0f}",
                f"• 손절가: ${forecast['stop_loss']:,.0f} (-{((current_price - forecast['stop_loss'])/current_price*100):.1f}%)",
                f"• 1차 목표: ${current_price * 1.01:,.0f} (+1.0%)",
                f"• 2차 목표: ${current_price * 1.02:,.0f} (+2.0%)",
                f"• 진입 시점: 단기 조정 또는 지지 확인 시"
            ]
        elif direction == "SHORT":
            lines = [
                f"🔴 숏 진입 전략:",
                f"• 진입 구간: ${entry_zone[0]:,.0f} ~ ${entry_zone[1]:,.0f}",
                f"• 손절가: ${forecast['stop_loss']:,.0f} (+{((forecast['stop_loss'] - current_price)/current_price*100):.1f}%)",
                f"• 1차 목표: ${current_price * 0.99:,.0f} (-1.0%)",
                f"• 2차 목표: ${current_price * 0.98:,.0f} (-2.0%)",
                f"• 진입 시점: 단기 반등 또는 저항 확인 시"
            ]
        else:
            lines = [
                f"⚪ 중립 전략:",
                f"• 관망 구간: ${entry_zone[0]:,.0f} ~ ${entry_zone[1]:,.0f}",
                f"• 롱 진입: ${forecast['key_resistance']:,.0f} 돌파 확정 시",
                f"• 숏 진입: ${forecast['key_support']:,.0f} 이탈 확정 시",
                f"• 손절: 진입 반대 방향 1.5%",
                f"• 대기: 명확한 방향성 확인까지"
            ]
        
        return '\n'.join(lines)
    
    def _format_risk_alerts(self, indicators: dict) -> str:
        """리스크 알림"""
        risk = indicators.get('risk_metrics', {})
        funding = indicators.get('funding_analysis', {})
        
        alerts = []
        
        # 리스크 레벨별 알림
        risk_level = risk.get('risk_level', '보통')
        if risk_level in ['높음', '매우 높음']:
            alerts.append(f"🚨 {risk_level} 리스크 - 포지션 축소 권장")
        
        # 펀딩비 알림
        funding_rate = funding.get('current_rate', 0)
        if abs(funding_rate) > 0.01:
            alerts.append(f"💰 펀딩비 {funding_rate:+.3%} - {'롱' if funding_rate > 0 else '숏'} 비용 주의")
        
        # 청산 리스크
        if risk.get('volatility_risk') == '높음':
            alerts.append("⚡ 높은 변동성 - 타이트한 손절 필수")
        
        if not alerts:
            alerts.append("✅ 특별한 리스크 없음")
        
        return '\n'.join(alerts)
    
    async def _format_profit_summary(self) -> str:
        """간단한 현재 상태"""
        try:
            position_info = await self._get_position_info()
            today_pnl = await self._get_today_realized_pnl()
            
            lines = []
            
            if position_info.get('has_position'):
                side = position_info.get('side')
                pnl_rate = position_info.get('pnl_rate', 0) * 100
                unrealized = position_info.get('unrealized_pnl', 0)
                
                emoji = "🟢" if unrealized > 0 else "🔴" if unrealized < 0 else "⚪"
                lines.append(f"{emoji} {side} 포지션: {pnl_rate:+.1f}% ({self._format_currency(unrealized, False)})")
            else:
                lines.append("⚪ 포지션 없음")
            
            lines.append(f"💵 오늘 실현: {self._format_currency(today_pnl, False)}")
            
            return '\n'.join(lines)
            
        except Exception as e:
            self.logger.error(f"수익 요약 실패: {e}")
            return "• 수익 정보 조회 실패"
    
    async def _generate_focused_mental_care(self, indicators: dict) -> str:
        """집중된 트레이딩 조언"""
        composite = indicators.get('composite_signal', {})
        signal = composite.get('signal', '중립')
        confidence = composite.get('confidence', 50)
        
        if self.openai_client:
            try:
                prompt = f"""
선물 트레이더에게 짧고 강력한 조언 한 문장:
- 현재 신호: {signal}
- 신뢰도: {confidence}%
- 상황: {'명확한 기회' if confidence > 70 else '애매한 상황' if confidence < 50 else '보통'}

20단어 이내, 구체적이고 실용적인 조언
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "간결하고 날카로운 트레이딩 조언 전문가"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=50,
                    temperature=0.7
                )
                
                return f'"{response.choices[0].message.content.strip()}"'
                
            except Exception as e:
                self.logger.error(f"멘탈 케어 생성 실패: {e}")
        
        # 폴백 메시지
        if confidence > 70:
            return '"신호가 명확합니다. 계획대로 실행하되 손절은 엄격하게. 🎯"'
        elif confidence < 50:
            return '"불확실한 시장입니다. 관망이 최선의 포지션일 수 있습니다. 🧘‍♂️"'
        else:
            return '"시장을 따르되 욕심내지 마세요. 작은 수익이 큰 수익을 만듭니다. 📊"'
