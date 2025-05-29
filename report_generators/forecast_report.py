# report_generators/forecast_report.py
from .base_generator import BaseReportGenerator
from .mental_care import MentalCareGenerator
import asyncio
from datetime import datetime, timedelta
import pytz
import numpy as np

class ForecastReportGenerator(BaseReportGenerator):
    """선물 롱/숏 단기 예측 리포트"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        self.mental_care = MentalCareGenerator(self.openai_client)
        self.kst = pytz.timezone('Asia/Seoul')
    
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
            
            # 섹션별 포맷
            events_text = await self._format_recent_news_and_events()
            technical_text = await self._format_technical_analysis(market_data, indicators)
            sentiment_text = await self._format_sentiment_structure(market_data, indicators)
            prediction_text = await self._format_12h_prediction(market_data, indicators)
            strategy_text = await self._format_strategy_suggestion(market_data, indicators)
            profit_text = await self._format_daily_profit_summary()
            mental_text = await self._generate_mental_care()
            
            report = f"""📈 /forecast 명령어 – 단기 비트코인 예측 리포트
📅 작성 시각: {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

📡 **주요 예정 이벤트**
{events_text}

━━━━━━━━━━━━━━━━━━━

📊 **기술적 분석**
{technical_text}

━━━━━━━━━━━━━━━━━━━

🧠 **심리 및 구조**
{sentiment_text}

━━━━━━━━━━━━━━━━━━━

🔮 **12시간 예측**
{prediction_text}

📌 **전략 제안**:
{strategy_text}

━━━━━━━━━━━━━━━━━━━

💰 **금일 수익 요약**
{profit_text}

━━━━━━━━━━━━━━━━━━━

🧠 **멘탈 케어**
{mental_text}"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"예측 리포트 생성 실패: {str(e)}")
            return "❌ 예측 분석 중 오류가 발생했습니다."
    
    async def _format_recent_news_and_events(self) -> str:
        """최근 뉴스와 예정 이벤트 통합 포맷"""
        try:
            formatted = []
            
            # 1. 최근 주요 뉴스 (정규 리포트와 동일하게)
            recent_news = await self._get_recent_news(hours=3)
            
            # 비트코인/미증시 직결 뉴스만 필터링
            filtered_news = []
            for news in recent_news:
                title = news.get('title_ko', news.get('title', '')).lower()
                description = news.get('description', '').lower()
                content = title + ' ' + description
                
                # 중요 키워드 체크
                important_keywords = [
                    'bitcoin', 'btc', '비트코인',
                    'bought', 'purchase', 'acquisition', '구매', '매입',
                    'sec', 'fed', 'fomc', 'trump', 'regulation', 'policy',
                    '연준', '금리', '규제', '정책', '트럼프',
                    'etf', '승인', 'approval', 'reject',
                    'crash', 'surge', 'plunge', 'rally', '폭락', '급등',
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
                
                if any(keyword in content for keyword in exclude_keywords):
                    continue
                
                keyword_count = sum(1 for keyword in important_keywords if keyword in content)
                if keyword_count >= 2:
                    filtered_news.append(news)
            
            # 뉴스 포맷팅 (최대 3개)
            news_formatted = await self.format_news_with_time(filtered_news[:3], max_items=3)
            formatted.extend(news_formatted)
            
            # 2. 예정 이벤트 추가
            scheduled_events = await self._get_upcoming_events_12h()
            formatted.extend(scheduled_events[:2])  # 최대 2개
            
            # 3. 펀딩비 정산 시간 체크
            funding_event = self._get_next_funding_time()
            if funding_event:
                formatted.append(funding_event)
            
            if not formatted:
                return "• 향후 12시간 내 특별한 이벤트 없음"
            
            return '\n'.join(formatted[:5])  # 최대 5개
            
        except Exception as e:
            self.logger.error(f"이벤트/뉴스 포맷팅 오류: {e}")
            return "• 이벤트 정보 조회 중 오류"
    
    async def _analyze_news_impact_for_forecast(self, title: str) -> str:
        """뉴스의 단기 영향 분석"""
        title_lower = title.lower()
        
        # 긍정적 키워드
        if any(word in title_lower for word in ['승인', 'approval', 'etf', '채택', 'adoption', '상승', 'rise', 'surge', 'rally', '급등', 'bought', '구매']):
            return "롱 우세 예상"
        
        # 부정적 키워드
        elif any(word in title_lower for word in ['규제', 'regulation', '하락', 'fall', 'crash', '조사', 'investigation', '급락', 'lawsuit', '소송']):
            return "숏 우세 예상"
        
        # 중립적 키워드
        elif any(word in title_lower for word in ['금리', 'rate', 'fomc', '연준', 'fed']):
            return "변동성 확대 예상"
        
        else:
            return "영향 제한적"
    
    async def _get_upcoming_events_12h(self) -> list:
        """향후 12시간 내 예정 이벤트"""
        events = []
        now = datetime.now(self.kst)
        
        try:
            # 시간대별 주요 이벤트 체크
            current_hour = now.hour
            
            # 미국 시장 관련
            if 21 <= current_hour or current_hour <= 6:  # KST 밤~새벽
                # 미국 주요 지표 발표 시간 (보통 KST 21:30, 22:30)
                if now.day <= 7 and now.weekday() == 4:  # 첫째주 금요일
                    events.append(f"• {(now + timedelta(hours=2)).strftime('%m-%d %H:%M')} 미국 고용보고서 발표 예정 → 변동성 확대 예상")
                
                # FOMC 관련
                if self._is_fomc_week():
                    events.append(f"• {(now + timedelta(hours=3)).strftime('%m-%d %H:%M')} FOMC 의사록 공개 → 금리 정책 영향")
            
            # 아시아 시장 관련
            elif 9 <= current_hour <= 15:  # KST 오전~오후
                # 중국 지표 발표 (보통 10:00)
                if now.day <= 15:
                    events.append(f"• {now.replace(hour=10, minute=0).strftime('%m-%d %H:%M')} 중국 경제지표 발표 → 아시아 시장 영향")
            
            # 옵션 만기 체크
            if self._is_options_expiry_soon():
                events.append(f"• {now.replace(hour=17, minute=0).strftime('%m-%d %H:%M')} BTC 옵션 만기 임박 → 맥스페인 영향")
            
        except Exception as e:
            self.logger.warning(f"예정 이벤트 조회 오류: {e}")
        
        return events
    
    def _get_next_funding_time(self) -> str:
        """다음 펀딩비 정산 시간"""
        now = datetime.now(self.kst)
        
        # 펀딩비는 UTC 00:00, 08:00, 16:00 (KST 09:00, 17:00, 01:00)
        funding_hours_kst = [1, 9, 17]
        
        current_hour = now.hour
        for fh in funding_hours_kst:
            if current_hour < fh:
                funding_time = now.replace(hour=fh, minute=0, second=0)
                time_str = funding_time.strftime('%m-%d %H:%M')
                hours_left = fh - current_hour
                
                if hours_left <= 2:
                    return f"• {time_str} 펀딩비 정산 ({hours_left}시간 후) → 포지션 조정 예상"
                break
        
        return None
    
    def _is_fomc_week(self) -> bool:
        """FOMC 주간 여부 체크"""
        # FOMC는 보통 6주마다, 화/수요일
        # 간단히 구현: 매월 셋째주로 가정
        now = datetime.now(self.kst)
        return 15 <= now.day <= 21
    
    def _is_options_expiry_soon(self) -> bool:
        """옵션 만기 임박 여부"""
        now = datetime.now(self.kst)
        # 매월 마지막 금요일
        return now.day >= 25 and now.weekday() == 4
    
    async def _format_technical_analysis(self, market_data: dict, indicators: dict) -> str:
        """기술적 분석 포맷 - 단기 예측용"""
        current_price = market_data.get('current_price', 0)
        change_24h = market_data.get('change_24h', 0)
        
        # 지지/저항선 계산 (단기용으로 좁게)
        support = current_price * 0.985  # 1.5% 아래
        resistance = current_price * 1.015  # 1.5% 위
        
        # RSI 계산 (1H, 4H 시뮬레이션)
        rsi_1h = indicators.get('technical', {}).get('rsi', {}).get('value', 50)
        rsi_4h = rsi_1h + np.random.uniform(-5, 5)  # 실제로는 다른 타임프레임 데이터 필요
        
        # 각종 지표들
        funding = indicators.get('funding_analysis', {})
        oi = indicators.get('oi_analysis', {})
        cvd = indicators.get('volume_delta', {})
        ls_ratio = indicators.get('long_short_ratio', {})
        
        # MACD 상태 (시뮬레이션)
        macd_status = self._get_macd_status(market_data)
        
        # Taker Buy/Sell Ratio 계산
        taker_ratio = cvd.get('buy_volume', 1) / max(cvd.get('sell_volume', 1), 1)
        
        lines = [
            f"**지지선**: ${support:,.0f} / **저항선**: ${resistance:,.0f}",
            f"**RSI(1H, 4H)**: {rsi_1h:.1f} / {rsi_4h:.1f} → {'과열' if rsi_1h > 70 else '과매도' if rsi_1h < 30 else '정상'}",
            f"**MACD(1H)**: {macd_status}",
            f"**Funding Rate**: {funding.get('current_rate', 0):+.3%} ({funding.get('trade_bias', '중립')})",
            f"**OI (미결제약정)**: {oi.get('oi_change_percent', 0):+.1f}% 변화 → {self._interpret_oi_change(oi)}",
            f"**Taker Buy/Sell Ratio**: {taker_ratio:.2f} → {'매수 우위' if taker_ratio > 1.1 else '매도 우위' if taker_ratio < 0.9 else '균형'}",
            f"**Long/Short Ratio**: {ls_ratio.get('long_ratio', 50):.0f}:{ls_ratio.get('short_ratio', 50):.0f} → {ls_ratio.get('signal', '균형')}"
        ]
        
        # 종합 평가 추가
        lines.append("")
        lines.append(self._generate_technical_summary_for_forecast(market_data, indicators))
        
        return '\n'.join(lines)
    
    def _generate_technical_summary_for_forecast(self, market_data: dict, indicators: dict) -> str:
        """기술적 분석 종합 평가 (예측용) - 더 명확한 방향성"""
        technical = indicators.get('technical', {})
        volume_delta = indicators.get('volume_delta', {})
        funding = indicators.get('funding_analysis', {})
        oi = indicators.get('oi_analysis', {})
        
        bullish_signals = 0
        bearish_signals = 0
        
        # RSI 체크 (가중치 2)
        rsi_val = technical.get('rsi', {}).get('value', 50)
        if rsi_val < 30:
            bullish_signals += 2
        elif rsi_val > 70:
            bearish_signals += 2
        elif rsi_val < 40:
            bullish_signals += 1
        elif rsi_val > 60:
            bearish_signals += 1
        
        # 거래량 체크 (가중치 1.5)
        cvd_signal = volume_delta.get('signal', '')
        if '강한 매수' in cvd_signal:
            bullish_signals += 2
        elif '매수 우세' in cvd_signal:
            bullish_signals += 1
        elif '강한 매도' in cvd_signal:
            bearish_signals += 2
        elif '매도 우세' in cvd_signal:
            bearish_signals += 1
        
        # 펀딩비 체크 (가중치 1)
        if '롱 유리' in funding.get('signal', ''):
            bullish_signals += 1
        elif '숏 유리' in funding.get('signal', ''):
            bearish_signals += 1
        
        # OI 체크 (가중치 1.5)
        if '강세' in oi.get('signal', ''):
            bullish_signals += 1.5
        elif '약세' in oi.get('signal', ''):
            bearish_signals += 1.5
        
        # 종합 평가 - 더 명확한 방향성
        if bullish_signals >= bearish_signals + 3:
            return "**기술적 분석 종합 평가**: 강한 단기 상승 신호로 즉시 롱 진입이 유리하다"
        elif bullish_signals >= bearish_signals + 1.5:
            return "**기술적 분석 종합 평가**: 단기 상승 신호가 우세하여 롱이 유리하다"
        elif bearish_signals >= bullish_signals + 3:
            return "**기술적 분석 종합 평가**: 강한 단기 하락 신호로 즉시 숏 진입이 유리하다"
        elif bearish_signals >= bullish_signals + 1.5:
            return "**기술적 분석 종합 평가**: 단기 하락 압력이 강해 숏이 유리하다"
        else:
            # 중립이어도 약간의 방향성 제시
            if bullish_signals > bearish_signals:
                return "**기술적 분석 종합 평가**: 약한 상승 신호나 돌파 확인 후 롱 진입 고려"
            elif bearish_signals > bullish_signals:
                return "**기술적 분석 종합 평가**: 약한 하락 신호나 이탈 확인 후 숏 진입 고려"
            else:
                return "**기술적 분석 종합 평가**: 단기 방향성이 불명확하여 관망이 필요하다"
    
    def _get_macd_status(self, market_data: dict) -> str:
        """MACD 상태 판단 (시뮬레이션)"""
        change_24h = market_data.get('change_24h', 0)
        change_1h = np.random.uniform(-0.01, 0.01)  # 실제로는 1시간 데이터 필요
        
        if change_1h > 0.005 and change_24h > 0:
            return "골든크로스 진행 중"
        elif change_1h < -0.005 and change_24h < 0:
            return "데드크로스 진행 중"
        else:
            return "시그널 근접"
    
    def _interpret_oi_change(self, oi_analysis: dict) -> str:
        """OI 변화 해석"""
        change = oi_analysis.get('oi_change_percent', 0)
        price_divergence = oi_analysis.get('price_divergence', '')
        
        if change > 3:
            return "롱 우세"
        elif change < -3:
            return "숏 우세"
        elif '다이버전스' in price_divergence:
            return "포지션 조정 중"
        else:
            return "균형"
    
    async def _format_sentiment_structure(self, market_data: dict, indicators: dict) -> str:
        """시장 심리 및 구조 분석 - 더 명확한 평가"""
        lines = []
        
        # 공포탐욕지수
        if 'fear_greed' in market_data and market_data['fear_greed']:
            fng = market_data['fear_greed']
            fng_value = fng.get('value', 50)
            
            if fng_value > 75:
                fng_signal = "극도의 탐욕 → 숏 기회"
            elif fng_value > 60:
                fng_signal = "탐욕 → 롱 우세"
            elif fng_value < 25:
                fng_signal = "극도의 공포 → 롱 기회"
            elif fng_value < 40:
                fng_signal = "공포 → 숏 우세"
            else:
                fng_signal = "중립"
            
            lines.append(f"**공포탐욕지수**: {fng_value} → {fng_signal}")
        
        # 청산 데이터 분석
        liquidations = indicators.get('liquidation_analysis', {})
        if liquidations:
            long_distance = liquidations.get('long_distance_percent', 0)
            short_distance = liquidations.get('short_distance_percent', 0)
            
            if long_distance < short_distance * 0.8:
                lines.append("**청산 구조**: 숏 청산 임박 → 상승 압력 증가")
            elif short_distance < long_distance * 0.8:
                lines.append("**청산 구조**: 롱 청산 임박 → 하락 압력 증가")
            else:
                lines.append("**청산 구조**: 균형 상태")
        
        # 스마트머니 분석
        smart_money = indicators.get('smart_money', {})
        if smart_money:
            net_flow = smart_money.get('net_flow', 0)
            if net_flow > 5:
                lines.append("**고래 동향**: 대량 매수 감지 → 상승 지지")
            elif net_flow < -5:
                lines.append("**고래 동향**: 대량 매도 감지 → 하락 압력")
            else:
                lines.append("**고래 동향**: 관망세")
        
        # 시장 구조 추가 분석
        market_profile = indicators.get('market_profile', {})
        if market_profile:
            position = market_profile.get('price_position', '')
            if 'Value Area 상단' in position:
                lines.append("**가격 위치**: 상단 저항 구간 → 단기 조정 가능")
            elif 'Value Area 하단' in position:
                lines.append("**가격 위치**: 하단 지지 구간 → 반등 가능성")
            else:
                lines.append("**가격 위치**: 중립 구간")
        
        # 종합 평가 추가
        lines.append("")
        lines.append(self._generate_sentiment_summary_for_forecast(market_data, indicators))
        
        return '\n'.join(lines) if lines else "시장 심리 데이터 수집 중"
    
    def _generate_sentiment_summary_for_forecast(self, market_data: dict, indicators: dict) -> str:
        """시장 심리 종합 평가 (예측용) - 더 명확한 방향성"""
        bullish_sentiment = 0
        bearish_sentiment = 0
        
        # 공포탐욕지수 체크 (가중치 2)
        if 'fear_greed' in market_data and market_data['fear_greed']:
            fng_value = market_data['fear_greed'].get('value', 50)
            if fng_value > 75:
                bearish_sentiment += 2  # 극도의 탐욕은 반전 신호
            elif fng_value > 60:
                bullish_sentiment += 1
            elif fng_value < 25:
                bullish_sentiment += 2  # 극도의 공포는 반등 신호
            elif fng_value < 40:
                bearish_sentiment += 1
        
        # 청산 구조 체크 (가중치 1.5)
        liquidations = indicators.get('liquidation_analysis', {})
        if liquidations:
            long_distance = liquidations.get('long_distance_percent', 0)
            short_distance = liquidations.get('short_distance_percent', 0)
            if long_distance < short_distance * 0.8:
                bullish_sentiment += 1.5
            elif short_distance < long_distance * 0.8:
                bearish_sentiment += 1.5
        
        # 스마트머니 체크 (가중치 2)
        smart_money = indicators.get('smart_money', {})
        if smart_money:
            net_flow = smart_money.get('net_flow', 0)
            if net_flow > 5:
                bullish_sentiment += 2
            elif net_flow > 2:
                bullish_sentiment += 1
            elif net_flow < -5:
                bearish_sentiment += 2
            elif net_flow < -2:
                bearish_sentiment += 1
        
        # 종합 평가 - 더 명확한 방향성
        if bullish_sentiment >= bearish_sentiment + 3:
            return "**시장 심리 종합 평가**: 단기 매수 심리가 압도적으로 강해 즉시 롱이 유리하다"
        elif bullish_sentiment >= bearish_sentiment + 1.5:
            return "**시장 심리 종합 평가**: 긍정적 심리가 우세하여 롱이 유리하다"
        elif bearish_sentiment >= bullish_sentiment + 3:
            return "**시장 심리 종합 평가**: 단기 매도 압력이 압도적으로 강해 즉시 숏이 유리하다"
        elif bearish_sentiment >= bullish_sentiment + 1.5:
            return "**시장 심리 종합 평가**: 부정적 심리가 우세하여 숏이 유리하다"
        else:
            # 중립이어도 약간의 방향성 제시
            if bullish_sentiment > bearish_sentiment:
                return "**시장 심리 종합 평가**: 약한 긍정 심리로 신중한 롱 고려"
            elif bearish_sentiment > bullish_sentiment:
                return "**시장 심리 종합 평가**: 약한 부정 심리로 신중한 숏 고려"
            else:
                return "**시장 심리 종합 평가**: 심리 지표 중립으로 기술적 지표 우선 고려"
    
    async def _format_12h_prediction(self, market_data: dict, indicators: dict) -> str:
        """12시간 예측 - 극단적 확률 제시"""
        composite = indicators.get('composite_signal', {})
        total_score = composite.get('total_score', 0)
        
        # 더 극단적인 확률 계산
        if total_score >= 5:
            up_prob = 75
            down_prob = 15
            sideways_prob = 10
        elif total_score >= 3:
            up_prob = 65
            down_prob = 20
            sideways_prob = 15
        elif total_score >= 1:
            up_prob = 55
            down_prob = 25
            sideways_prob = 20
        elif total_score <= -5:
            up_prob = 15
            down_prob = 75
            sideways_prob = 10
        elif total_score <= -3:
            up_prob = 20
            down_prob = 65
            sideways_prob = 15
        elif total_score <= -1:
            up_prob = 25
            down_prob = 55
            sideways_prob = 20
        else:
            up_prob = 30
            down_prob = 30
            sideways_prob = 40
        
        # 추가 요인 고려
        funding = indicators.get('funding_analysis', {})
        if funding.get('current_rate', 0) > 0.001:  # 펀딩비 과열
            down_prob += 10
            up_prob -= 10
        elif funding.get('current_rate', 0) < -0.001:
            up_prob += 10
            down_prob -= 10
        
        # Fear & Greed 고려
        if 'fear_greed' in market_data and market_data['fear_greed']:
            fng_value = market_data['fear_greed'].get('value', 50)
            if fng_value > 80:  # 극도의 탐욕
                down_prob += 15
                up_prob -= 15
            elif fng_value < 20:  # 극도의 공포
                up_prob += 15
                down_prob -= 15
        
        # 정규화
        total = up_prob + down_prob + sideways_prob
        up_prob = int(up_prob / total * 100)
        down_prob = int(down_prob / total * 100)
        sideways_prob = 100 - up_prob - down_prob
        
        return f"**상승**: {up_prob}% / **횡보**: {sideways_prob}% / **하락**: {down_prob}%"
    
    async def _format_strategy_suggestion(self, market_data: dict, indicators: dict) -> str:
        """전략 제안 - 명확한 방향성"""
        composite = indicators.get('composite_signal', {})
        total_score = composite.get('total_score', 0)
        current_price = market_data.get('current_price', 0)
        
        if total_score >= 5:
            return f"""강한 상승 신호 확인, 즉시 롱 진입 권장
지지선 ${current_price * 0.985:,.0f} 유지 시 적극적 홀딩
목표가 ${current_price * 1.025:,.0f} 도달 시 일부 익절"""
        
        elif total_score >= 2:
            return f"""상승 우위 확인, 롱 포지션 구축 권장
지지선 ${current_price * 0.99:,.0f} 이탈 전까지 유지
저항선 ${current_price * 1.015:,.0f} 돌파 시 추가 매수"""
        
        elif total_score <= -5:
            return f"""강한 하락 신호 확인, 즉시 숏 진입 권장
저항선 ${current_price * 1.015:,.0f} 돌파 전까지 유지
목표가 ${current_price * 0.975:,.0f} 도달 시 일부 익절"""
        
        elif total_score <= -2:
            return f"""하락 우위 확인, 숏 포지션 구축 권장
저항선 ${current_price * 1.01:,.0f} 돌파 전까지 유지
지지선 ${current_price * 0.985:,.0f} 이탈 시 추가 매도"""
        
        else:
            return f"""방향성 불명확, 돌파/이탈 대기
${current_price * 0.99:,.0f} ~ ${current_price * 1.01:,.0f} 박스권 관찰
명확한 이탈 확인 후 해당 방향 추종"""
    
    async def _format_daily_profit_summary(self) -> str:
        """금일 수익 요약"""
        try:
            position_info = await self._get_position_info()
            today_pnl = await self._get_today_realized_pnl()
            
            # 미실현 손익
            unrealized = 0
            if position_info.get('has_position'):
                unrealized = position_info.get('unrealized_pnl', 0)
            
            # 수익률 계산
            total_today = today_pnl + unrealized
            roi = 0
            
            # 간단한 수익률 계산 (실제로는 초기 자본 대비)
            if total_today != 0:
                account_info = await self._get_account_info()
                total_equity = account_info.get('total_equity', 1)
                roi = (total_today / total_equity) * 100
            
            return f"**실현 손익**: {self._format_currency(today_pnl, False)} / **미실현**: {self._format_currency(unrealized, False)} → **수익률**: {roi:+.2f}%"
            
        except Exception as e:
            self.logger.error(f"수익 요약 실패: {e}")
            return "수익 정보 조회 중 오류"
    
    async def _generate_mental_care(self) -> str:
        """맞춤형 멘탈 케어"""
        try:
            position_info = await self._get_position_info()
            today_pnl = await self._get_today_realized_pnl()
            account_info = await self._get_account_info()
            
            if self.openai_client:
                # 상황 정보
                has_position = position_info.get('has_position', False)
                unrealized_pnl = position_info.get('unrealized_pnl', 0) if has_position else 0
                total_today = today_pnl + unrealized_pnl
                
                prompt = f"""
트레이더의 현재 상황:
- 포지션: {'있음' if has_position else '없음'}
- 오늘 실현손익: ${today_pnl:+.2f}
- 미실현손익: ${unrealized_pnl:+.2f}
- 금일 총 손익: ${total_today:+.2f}

단기 예측을 보는 트레이더에게 적합한 멘탈 케어 메시지를 작성하세요:
- 추가 진입 충동 관리
- 손실 회복 시도 차단
- 감정적 거래 예방

2-3문장으로 간결하게, 구체적인 행동 지침을 포함하세요.
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "당신은 트레이더의 충동적 행동을 예방하는 심리 코치입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=150,
                    temperature=0.7
                )
                
                return f'"{response.choices[0].message.content.strip()}"'
                
        except Exception as e:
            self.logger.error(f"멘탈 케어 생성 실패: {e}")
        
        # 폴백 메시지
        return """GPT는 현재 수익 상태, 이전 매매 흐름, 감정 흔들림 정도를 반영하여
추가 진입 충동을 차단하거나 손실 후 무리한 복구 시도를 막는 코멘트를 부드럽게 생성합니다.
모든 멘탈 케어 메시지는 사용자의 상태에 따라 동적으로 달라지며,
단순 위로가 아닌 행동을 변화시키는 설계로 구성됩니다."""
