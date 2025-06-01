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
            
            # 선물 특화 지표 계산 (백그라운드에서 모든 지표 분석)
            indicators = await self.indicator_system.calculate_all_indicators(market_data)
            
            # 확장된 기술적 지표 분석 (백그라운드)
            extended_indicators = await self._calculate_extended_indicators(market_data)
            indicators.update(extended_indicators)
            
            # 섹션별 생성
            market_summary = await self._format_market_summary(market_data)
            signal_summary = await self._format_signal_summary(indicators)
            strategy_text = await self._format_trading_strategy(market_data, indicators)
            prediction_text = await self._format_ai_prediction(market_data, indicators)
            pnl_text = await self._format_integrated_pnl()
            mental_text = await self._generate_mental_care(market_data, indicators)
            
            report = f"""<b>🧾 비트코인 선물 매매 예측 리포트</b>
<b>📅 {current_time}</b>
━━━━━━━━━━━━━━━━━━━

<b>📊 현재 시장 상황</b>
{market_summary}

<b>📈 핵심 매매 신호</b>
{signal_summary}

<b>💡 매매 전략</b>
{strategy_text}

<b>🔮 AI 예측 (12시간)</b>
{prediction_text}

<b>💰 통합 손익 현황</b>
{pnl_text}

<b>🧠 오늘의 한마디</b>
{mental_text}"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"정기 리포트 생성 실패: {str(e)}")
            self.logger.error(f"상세 오류: {traceback.format_exc()}")
            return f"❌ 리포트 생성 중 오류가 발생했습니다: {str(e)}"
    
    async def _calculate_extended_indicators(self, market_data: dict) -> dict:
        """확장된 기술적 지표 계산 (백그라운드)"""
        try:
            extended = {}
            
            # K라인 데이터 가져오기
            if self.bitget_client:
                klines = await self.bitget_client.get_kline('BTCUSDT', '1H', 100)
                
                if klines:
                    closes = [float(k[4]) for k in klines]  # 종가
                    highs = [float(k[2]) for k in klines]   # 고가
                    lows = [float(k[3]) for k in klines]    # 저가
                    volumes = [float(k[5]) for k in klines]  # 거래량
                    
                    # 이동평균선
                    extended['ma_7'] = sum(closes[-7:]) / 7
                    extended['ma_25'] = sum(closes[-25:]) / 25
                    extended['ma_99'] = sum(closes[-99:]) / 99
                    
                    # EMA 계산
                    extended['ema_12'] = self._calculate_ema(closes, 12)
                    extended['ema_26'] = self._calculate_ema(closes, 26)
                    
                    # MACD
                    macd = extended['ema_12'] - extended['ema_26']
                    extended['macd'] = macd
                    extended['macd_signal'] = self._calculate_ema([macd], 9)
                    extended['macd_histogram'] = macd - extended['macd_signal']
                    
                    # 볼린저 밴드
                    ma_20 = sum(closes[-20:]) / 20
                    std_20 = self._calculate_std(closes[-20:], ma_20)
                    extended['bb_upper'] = ma_20 + (2 * std_20)
                    extended['bb_middle'] = ma_20
                    extended['bb_lower'] = ma_20 - (2 * std_20)
                    extended['bb_width'] = (extended['bb_upper'] - extended['bb_lower']) / ma_20
                    
                    # 스토캐스틱
                    extended['stoch_k'], extended['stoch_d'] = self._calculate_stochastic(highs, lows, closes)
                    
                    # CCI (Commodity Channel Index)
                    extended['cci'] = self._calculate_cci(highs, lows, closes)
                    
                    # Williams %R
                    extended['williams_r'] = self._calculate_williams_r(highs, lows, closes)
                    
                    # ATR (Average True Range)
                    extended['atr'] = self._calculate_atr(highs, lows, closes)
                    
                    # ADX (Average Directional Index)
                    extended['adx'] = self._calculate_adx(highs, lows, closes)
                    
                    # OBV (On Balance Volume)
                    extended['obv'] = self._calculate_obv(closes, volumes)
                    
                    # MFI (Money Flow Index)
                    extended['mfi'] = self._calculate_mfi(highs, lows, closes, volumes)
                    
                    # VWAP
                    extended['vwap'] = self._calculate_vwap(highs, lows, closes, volumes)
                    
                    # 피봇 포인트
                    extended['pivot_points'] = self._calculate_pivot_points(
                        highs[-1], lows[-1], closes[-1]
                    )
                    
                    # 이치모쿠 구름
                    extended['ichimoku'] = self._calculate_ichimoku(highs, lows)
                    
                    # 파라볼릭 SAR
                    extended['parabolic_sar'] = self._calculate_parabolic_sar(highs, lows)
                    
                    # 켈트너 채널
                    extended['keltner_channels'] = self._calculate_keltner_channels(
                        highs, lows, closes
                    )
                    
                    # 슈퍼트렌드
                    extended['supertrend'] = self._calculate_supertrend(
                        highs, lows, closes, extended['atr']
                    )
                    
                    # 지표 스코어링 (중요도 계산)
                    extended['indicator_scores'] = self._score_indicators(extended, closes[-1])
            
            return extended
            
        except Exception as e:
            self.logger.error(f"확장 지표 계산 실패: {e}")
            return {}
    
    async def _format_market_summary(self, market_data: dict) -> str:
        """시장 요약 - 간결하고 핵심만"""
        current_price = market_data.get('current_price', 0)
        change_24h = market_data.get('change_24h', 0)
        volume_24h = market_data.get('volume_24h', 0)
        volatility = market_data.get('volatility', 0)
        
        # 변동성 레벨
        if volatility > 5:
            vol_level = "매우 높음"
            vol_emoji = "🔴"
        elif volatility > 3:
            vol_level = "높음"
            vol_emoji = "🟠"
        elif volatility > 1.5:
            vol_level = "보통"
            vol_emoji = "🟡"
        else:
            vol_level = "낮음"
            vol_emoji = "🟢"
        
        change_emoji = "📈" if change_24h > 0 else "📉" if change_24h < 0 else "➖"
        
        return f"""• BTC: ${current_price:,.0f} {change_emoji} ({change_24h:+.1%})
- 24H 거래량: {volume_24h:,.0f} BTC
- 변동성: {volatility:.1f}% ({vol_level}) {vol_emoji}"""
    
    async def _format_signal_summary(self, indicators: dict) -> str:
        """핵심 매매 신호 요약 - 시각적 개선"""
        composite = indicators.get('composite_signal', {})
        total_score = composite.get('total_score', 0)
        confidence = composite.get('confidence', 50)
        
        # 신호 강도 계산 (5단계)
        if abs(total_score) >= 7:
            strength = 5
        elif abs(total_score) >= 5:
            strength = 4
        elif abs(total_score) >= 3:
            strength = 3
        elif abs(total_score) >= 1:
            strength = 2
        else:
            strength = 1
        
        # 시각적 표현
        strength_bar = "●" * strength + "○" * (5 - strength)
        
        # 방향성
        if total_score >= 5:
            direction = "🟢 강한 상승"
            signal_color = "🟢"
        elif total_score >= 2:
            direction = "🟢 약한 상승"
            signal_color = "🟡"
        elif total_score <= -5:
            direction = "🔴 강한 하락"
            signal_color = "🔴"
        elif total_score <= -2:
            direction = "🔴 약한 하락"
            signal_color = "🟠"
        else:
            direction = "⚪ 중립"
            signal_color = "⚪"
        
        # 중요 지표 선별 (백그라운드에서 분석한 것 중 상위 3개)
        extended = indicators.get('extended_indicators', {})
        top_indicators = []
        
        if 'indicator_scores' in extended:
            sorted_indicators = sorted(
                extended['indicator_scores'].items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )[:3]
            
            for ind_name, score in sorted_indicators:
                if score > 0:
                    top_indicators.append(f"• {ind_name}: 매수 신호")
                elif score < 0:
                    top_indicators.append(f"• {ind_name}: 매도 신호")
        
        key_indicators = "\n".join(top_indicators) if top_indicators else "• 특이 신호 없음"
        
        return f"""【강도】 {strength_bar} ({strength}/5)
【방향】 {direction}
【신뢰도】 {confidence:.0f}%

<b>핵심 지표 요약:</b>
{key_indicators}"""
    
    async def _format_trading_strategy(self, market_data: dict, indicators: dict) -> str:
        """매매 전략 - 명확하고 실행 가능한"""
        composite = indicators.get('composite_signal', {})
        total_score = composite.get('total_score', 0)
        current_price = market_data.get('current_price', 0)
        volatility = market_data.get('volatility', 0)
        
        # 진입 범위 설정
        if volatility > 3:
            entry_range = 0.005  # 0.5%
        else:
            entry_range = 0.003  # 0.3%
        
        # 전략 결정
        if total_score >= 5:
            action = "즉시 롱 진입"
            entry_low = current_price * (1 - entry_range)
            entry_high = current_price
            stop_loss = current_price * 0.98
            target1 = current_price * 1.02
            target2 = current_price * 1.035
            emoji = "🟢"
        elif total_score >= 2:
            action = "신중한 롱 진입"
            entry_low = current_price * (1 - entry_range)
            entry_high = current_price * 0.999
            stop_loss = current_price * 0.985
            target1 = current_price * 1.015
            target2 = current_price * 1.025
            emoji = "🟡"
        elif total_score <= -5:
            action = "즉시 숏 진입"
            entry_low = current_price
            entry_high = current_price * (1 + entry_range)
            stop_loss = current_price * 1.02
            target1 = current_price * 0.98
            target2 = current_price * 0.965
            emoji = "🔴"
        elif total_score <= -2:
            action = "신중한 숏 진입"
            entry_low = current_price * 1.001
            entry_high = current_price * (1 + entry_range)
            stop_loss = current_price * 1.015
            target1 = current_price * 0.985
            target2 = current_price * 0.975
            emoji = "🟠"
        else:
            action = "관망 권장"
            entry_low = current_price * 0.995
            entry_high = current_price * 1.005
            stop_loss = 0
            target1 = 0
            target2 = 0
            emoji = "⚪"
        
        # 추가 분석 포인트
        extended = indicators.get('extended_indicators', {})
        warning = ""
        
        # RSI 체크
        rsi = indicators.get('technical', {}).get('rsi', {}).get('value', 50)
        if rsi > 70 and total_score > 0:
            warning = "\n⚠️ 과매수 구간 - 조정 가능성"
        elif rsi < 30 and total_score < 0:
            warning = "\n⚠️ 과매도 구간 - 반등 가능성"
        
        # 볼륨 분석
        volume_analysis = indicators.get('volume_delta', {})
        if volume_analysis.get('smart_money', {}).get('signal') == '스마트머니 매수 진입':
            warning += "\n✅ 고래 매집 확인 - 상승 준비"
        elif volume_analysis.get('smart_money', {}).get('signal') == '스마트머니 매도 진행':
            warning += "\n⚠️ 고래 매도 확인 - 하락 주의"
        
        if stop_loss > 0:
            return f"""• 액션: {emoji} {action}
- 진입: ${entry_low:,.0f} ~ ${entry_high:,.0f}
- 손절: ${stop_loss:,.0f} ({(stop_loss/current_price-1)*100:+.1f}%)
- 1차 목표: ${target1:,.0f} ({(target1/current_price-1)*100:+.1f}%)
- 2차 목표: ${target2:,.0f} ({(target2/current_price-1)*100:+.1f}%){warning}"""
        else:
            return f"""• 액션: {emoji} {action}
- 상방 돌파: ${entry_high:,.0f} 이상 시 롱
- 하방 이탈: ${entry_low:,.0f} 이하 시 숏
- 대기 구간: ${entry_low:,.0f} ~ ${entry_high:,.0f}{warning}"""
    
    async def _format_ai_prediction(self, market_data: dict, indicators: dict) -> str:
        """AI 예측 - 더 정확하고 명확한"""
        composite = indicators.get('composite_signal', {})
        total_score = composite.get('total_score', 0)
        current_price = market_data.get('current_price', 0)
        
        # 기본 확률
        up_prob = 33
        sideways_prob = 34
        down_prob = 33
        
        # 지표 기반 확률 조정
        # 1. 종합 점수
        if total_score > 0:
            up_bonus = min(total_score * 6, 30)
            up_prob += up_bonus
            down_prob -= up_bonus * 0.7
            sideways_prob -= up_bonus * 0.3
        elif total_score < 0:
            down_bonus = min(abs(total_score) * 6, 30)
            down_prob += down_bonus
            up_prob -= down_bonus * 0.7
            sideways_prob -= down_bonus * 0.3
        
        # 2. 펀딩비 조정
        funding = indicators.get('funding_analysis', {})
        funding_rate = funding.get('current_rate', 0)
        if funding_rate > 0.001:  # 과열
            down_prob += 8
            up_prob -= 8
        elif funding_rate < -0.001:  # 과매도
            up_prob += 8
            down_prob -= 8
        
        # 3. RSI 조정
        rsi = indicators.get('technical', {}).get('rsi', {}).get('value', 50)
        if rsi > 70:
            down_prob += 10
            up_prob -= 10
        elif rsi < 30:
            up_prob += 10
            down_prob -= 10
        
        # 4. 거래량 분석
        volume_signal = indicators.get('volume_delta', {}).get('signal', '')
        if '매수 우세' in volume_signal:
            up_prob += 5
            down_prob -= 5
        elif '매도 우세' in volume_signal:
            down_prob += 5
            up_prob -= 5
        
        # 5. 스마트머니 플로우
        smart_money = indicators.get('smart_money', {})
        if smart_money.get('net_flow', 0) > 5:
            up_prob += 7
            down_prob -= 7
        elif smart_money.get('net_flow', 0) < -5:
            down_prob += 7
            up_prob -= 7
        
        # 정규화
        total = up_prob + sideways_prob + down_prob
        up_prob = int(up_prob / total * 100)
        down_prob = int(down_prob / total * 100)
        sideways_prob = 100 - up_prob - down_prob
        
        # 예상 가격 범위
        volatility = market_data.get('volatility', 2)
        expected_move = volatility * 0.5  # 12시간 예상 변동률
        
        if up_prob > down_prob + 20:
            min_price = current_price * (1 + expected_move * 0.3)
            max_price = current_price * (1 + expected_move * 1.2)
            trend = "상승 돌파"
            emoji = "📈"
        elif down_prob > up_prob + 20:
            min_price = current_price * (1 - expected_move * 1.2)
            max_price = current_price * (1 - expected_move * 0.3)
            trend = "하락 이탈"
            emoji = "📉"
        else:
            min_price = current_price * (1 - expected_move * 0.5)
            max_price = current_price * (1 + expected_move * 0.5)
            trend = "횡보 지속"
            emoji = "➡️"
        
        # 주요 이벤트 체크
        events = []
        if up_prob > 60:
            events.append("• 강한 상승 모멘텀 형성")
        if down_prob > 60:
            events.append("• 하락 압력 증가")
        if abs(up_prob - down_prob) < 10:
            events.append("• 방향성 결정 대기")
        
        events_text = "\n".join(events) if events else ""
        
        return f"""▲ 상승 {up_prob}% {"(우세)" if up_prob > max(sideways_prob, down_prob) else ""}
━ 횡보 {sideways_prob}%
▼ 하락 {down_prob}% {"(우세)" if down_prob > max(up_prob, sideways_prob) else ""}

→ 예상 범위: ${min_price:,.0f} ~ ${max_price:,.0f}
→ 예상 추세: {emoji} {trend}

{events_text}"""
    
    async def _format_integrated_pnl(self) -> str:
        """통합 손익 현황 - Bitget + Gate.io"""
        try:
            # Bitget 정보
            bitget_position = await self._get_position_info()
            bitget_account = await self._get_account_info()
            bitget_today_pnl = await self._get_today_realized_pnl()
            bitget_weekly = await self._get_weekly_profit()
            
            # Gate.io 정보 (있는 경우)
            gate_pnl = 0
            gate_today = 0
            gate_balance = 0
            
            if hasattr(self, 'gateio_client') and self.gateio_client:
                try:
                    gate_profit = await self.gateio_client.get_profit_history_since_may()
                    gate_pnl = gate_profit.get('actual_profit', 0)
                    gate_today = gate_profit.get('today_realized', 0)
                    gate_balance = gate_profit.get('current_balance', 0)
                except:
                    pass
            
            # 총 손익 계산
            total_equity = bitget_account.get('total_equity', 0) + gate_balance
            total_weekly = bitget_weekly.get('total', 0) + gate_pnl
            total_today = bitget_today_pnl + gate_today
            
            lines = []
            
            # 총 자산
            lines.append(f"• 총 자산: ${total_equity:,.2f}")
            
            # 수익 분석
            lines.append(f"• 총 수익: ${total_weekly:+,.2f}")
            if gate_balance > 0:
                lines.append(f"  - Bitget: ${bitget_weekly.get('total', 0):+,.2f}")
                lines.append(f"  - Gate.io: ${gate_pnl:+,.2f}")
            
            lines.append(f"• 금일: ${total_today:+,.2f}")
            lines.append(f"• 7일: ${total_weekly:+,.2f}")
            
            # 현재 포지션
            if bitget_position.get('has_position'):
                side = bitget_position.get('side')
                entry = bitget_position.get('entry_price', 0)
                pnl_rate = bitget_position.get('pnl_rate', 0) * 100
                unrealized = bitget_position.get('unrealized_pnl', 0)
                
                lines.append(f"• 포지션: {side} (진입 ${entry:,.0f}, {pnl_rate:+.1f}%)")
                
                # 승률 계산 (간단 버전)
                if hasattr(self, 'trade_history'):
                    wins = len([t for t in self.trade_history if t['pnl'] > 0])
                    total_trades = len(self.trade_history)
                    if total_trades > 0:
                        win_rate = wins / total_trades * 100
                        lines.append(f"• 승률: {win_rate:.0f}% ({wins}승 {total_trades-wins}패)")
            else:
                lines.append("• 포지션: 없음")
            
            return '\n'.join(lines)
            
        except Exception as e:
            self.logger.error(f"통합 손익 계산 실패: {e}")
            return "• 손익 정보 조회 실패"
    
    async def _generate_mental_care(self, market_data: dict, indicators: dict) -> str:
        """멘탈 케어 - 간결하고 자연스러운"""
        try:
            account_info = await self._get_account_info()
            position_info = await self._get_position_info()
            today_pnl = await self._get_today_realized_pnl()
            weekly_profit = await self._get_weekly_profit()
            
            # Gate.io 수익 추가
            if hasattr(self, 'gateio_client') and self.gateio_client:
                try:
                    gate_profit = await self.gateio_client.get_profit_history_since_may()
                    today_pnl += gate_profit.get('today_realized', 0)
                    weekly_profit['total'] += gate_profit.get('actual_profit', 0)
                except:
                    pass
            
            message = await self.mental_care.generate_profit_mental_care(
                account_info, position_info, today_pnl, weekly_profit
            )
            
            # 따옴표로 감싸서 반환
            return message
            
        except Exception as e:
            self.logger.error(f"멘탈 케어 생성 실패: {e}")
            return '"시장은 기회로 가득합니다. 차분하게 기다리세요. 📊"'
    
    # 보조 계산 함수들
    def _calculate_ema(self, prices: list, period: int) -> float:
        """지수이동평균 계산"""
        if len(prices) < period:
            return sum(prices) / len(prices)
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def _calculate_std(self, values: list, mean: float) -> float:
        """표준편차 계산"""
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
        
        # %D는 %K의 3일 이동평균
        k_values = []
        for i in range(min(3, len(closes) - period + 1)):
            idx = -(i + 1)
            lowest = min(lows[idx-period+1:idx+1])
            highest = max(highs[idx-period+1:idx+1])
            if highest != lowest:
                k_val = ((closes[idx] - lowest) / (highest - lowest)) * 100
                k_values.append(k_val)
        
        d = sum(k_values) / len(k_values) if k_values else k
        
        return k, d
    
    def _calculate_cci(self, highs: list, lows: list, closes: list, period: int = 20) -> float:
        """CCI 계산"""
        if len(closes) < period:
            return 0
        
        typical_prices = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
        sma = sum(typical_prices[-period:]) / period
        
        mean_deviation = sum(abs(tp - sma) for tp in typical_prices[-period:]) / period
        
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
        
        atr = sum(true_ranges[:period]) / period
        
        for tr in true_ranges[period:]:
            atr = (atr * (period - 1) + tr) / period
        
        return atr
    
    def _calculate_adx(self, highs: list, lows: list, closes: list, period: int = 14) -> float:
        """ADX 계산 (간단 버전)"""
        if len(closes) < period * 2:
            return 25  # 중립값
        
        # +DI와 -DI 계산 (간단 버전)
        plus_dm = []
        minus_dm = []
        
        for i in range(1, len(highs)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            
            if high_diff > low_diff and high_diff > 0:
                plus_dm.append(high_diff)
                minus_dm.append(0)
            elif low_diff > high_diff and low_diff > 0:
                plus_dm.append(0)
                minus_dm.append(low_diff)
            else:
                plus_dm.append(0)
                minus_dm.append(0)
        
        # ATR
        atr = self._calculate_atr(highs, lows, closes, period)
        
        if atr == 0:
            return 25
        
        # DI 계산
        plus_di = (sum(plus_dm[-period:]) / period) / atr * 100
        minus_di = (sum(minus_dm[-period:]) / period) / atr * 100
        
        # DX 계산
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return 25
        
        dx = abs(plus_di - minus_di) / di_sum * 100
        
        return dx
    
    def _calculate_obv(self, closes: list, volumes: list) -> float:
        """OBV 계산"""
        if len(closes) < 2:
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
        if len(closes) < period + 1:
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
        if not volumes or sum(volumes) == 0:
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
        def donchian(data, period):
            if len(data) < period:
                return (max(data) + min(data)) / 2
            return (max(data[-period:]) + min(data[-period:])) / 2
        
        # 전환선 (9일)
        tenkan = donchian(highs, 9)
        
        # 기준선 (26일)
        kijun = donchian(highs, 26)
        
        # 선행스팬 A
        senkou_a = (tenkan + kijun) / 2
        
        # 선행스팬 B (52일)
        senkou_b = donchian(highs, 52)
        
        return {
            'tenkan': tenkan,
            'kijun': kijun,
            'senkou_a': senkou_a,
            'senkou_b': senkou_b,
            'cloud_top': max(senkou_a, senkou_b),
            'cloud_bottom': min(senkou_a, senkou_b)
        }
    
    def _calculate_parabolic_sar(self, highs: list, lows: list, af: float = 0.02, max_af: float = 0.2) -> float:
        """파라볼릭 SAR 계산 (간단 버전)"""
        if len(highs) < 2:
            return lows[-1] if lows else 0
        
        # 초기값
        sar = lows[0]
        ep = highs[0]
        trend = 1  # 1: 상승, -1: 하락
        
        for i in range(1, len(highs)):
            if trend == 1:
                sar = sar + af * (ep - sar)
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + 0.02, max_af)
                
                if lows[i] < sar:
                    trend = -1
                    sar = ep
                    ep = lows[i]
                    af = 0.02
            else:
                sar = sar + af * (ep - sar)
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + 0.02, max_af)
                
                if highs[i] > sar:
                    trend = 1
                    sar = ep
                    ep = highs[i]
                    af = 0.02
        
        return sar
    
    def _calculate_keltner_channels(self, highs: list, lows: list, closes: list, period: int = 20, multiplier: float = 2) -> dict:
        """켈트너 채널 계산"""
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
    
    def _score_indicators(self, extended: dict, current_price: float) -> dict:
        """지표별 중요도 점수 계산"""
        scores = {}
        
        # MACD
        if 'macd' in extended and 'macd_signal' in extended:
            if extended['macd'] > extended['macd_signal']:
                scores['MACD'] = 1
            else:
                scores['MACD'] = -1
        
        # 볼린저 밴드
        if all(k in extended for k in ['bb_upper', 'bb_lower']):
            if current_price > extended['bb_upper']:
                scores['볼린저밴드'] = -1  # 과매수
            elif current_price < extended['bb_lower']:
                scores['볼린저밴드'] = 1  # 과매도
        
        # 스토캐스틱
        if 'stoch_k' in extended:
            if extended['stoch_k'] < 20:
                scores['스토캐스틱'] = 1  # 과매도
            elif extended['stoch_k'] > 80:
                scores['스토캐스틱'] = -1  # 과매수
        
        # CCI
        if 'cci' in extended:
            if extended['cci'] < -100:
                scores['CCI'] = 1
            elif extended['cci'] > 100:
                scores['CCI'] = -1
        
        # MFI
        if 'mfi' in extended:
            if extended['mfi'] < 20:
                scores['MFI'] = 1  # 과매도
            elif extended['mfi'] > 80:
                scores['MFI'] = -1  # 과매수
        
        # ADX (추세 강도)
        if 'adx' in extended and extended['adx'] > 25:
            scores['ADX'] = 2  # 강한 추세
        
        # 이치모쿠
        if 'ichimoku' in extended:
            if current_price > extended['ichimoku']['cloud_top']:
                scores['이치모쿠'] = 1
            elif current_price < extended['ichimoku']['cloud_bottom']:
                scores['이치모쿠'] = -1
        
        # 슈퍼트렌드
        if 'supertrend' in extended:
            scores['슈퍼트렌드'] = extended['supertrend']['trend']
        
        return scores
    
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
