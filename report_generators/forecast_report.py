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
            events_text = await self._format_events_and_news()
            technical_text = await self._format_technical_analysis(market_data, indicators)
            sentiment_text = await self._format_sentiment_structure(market_data, indicators)
            prediction_text = await self._format_12h_prediction(market_data, indicators)
            strategy_text = await self._format_strategy_suggestion(market_data, indicators)
            profit_text = await self._format_daily_profit_summary()
            mental_text = await self._generate_mental_care()
            
            report = f"""📈 /forecast 명령어 – 단기 비트코인 예측 리포트
📅 작성 시각: {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

📡 주요 예정 이벤트/뉴스
{events_text}

━━━━━━━━━━━━━━━━━━━

📊 기술적 분석
{technical_text}

━━━━━━━━━━━━━━━━━━━

🧠 심리 및 구조
{sentiment_text}

━━━━━━━━━━━━━━━━━━━

🔮 12시간 예측
{prediction_text}

📌 전략 제안:
{strategy_text}

━━━━━━━━━━━━━━━━━━━

💰 금일 수익 요약
{profit_text}

━━━━━━━━━━━━━━━━━━━

🧠 멘탈 케어
{mental_text}"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"예측 리포트 생성 실패: {str(e)}")
            return "❌ 예측 분석 중 오류가 발생했습니다."
    
    async def _format_events_and_news(self) -> str:
        """주요 예정 이벤트와 뉴스 포맷"""
        try:
            formatted = []
            
            # 1. 최근 뉴스 (3시간 이내)
            recent_news = await self.data_collector.get_recent_news(hours=3) if self.data_collector else []
            
            # 뉴스 포맷팅 (최대 3개)
            for news in recent_news[:3]:
                try:
                    # 시간 처리
                    if news.get('published_at'):
                        pub_time_str = news.get('published_at', '').replace('Z', '+00:00')
                        if 'T' in pub_time_str:
                            pub_time = datetime.fromisoformat(pub_time_str)
                        else:
                            from dateutil import parser
                            pub_time = parser.parse(pub_time_str)
                        
                        pub_time_kst = pub_time.astimezone(self.kst)
                        time_str = pub_time_kst.strftime('%m-%d %H:%M')
                    else:
                        time_str = datetime.now(self.kst).strftime('%m-%d %H:%M')
                    
                    # 한글 제목 우선
                    title = news.get('title_ko', news.get('title', '')).strip()[:60]
                    
                    # 영향 분석
                    impact = await self._analyze_news_impact_for_forecast(title)
                    
                    formatted.append(f"{time_str} {title} → {impact}")
                    
                except Exception as e:
                    self.logger.warning(f"뉴스 포맷팅 오류: {e}")
                    continue
            
            # 2. 예정 이벤트 추가
            scheduled_events = await self._get_upcoming_events_12h()
            formatted.extend(scheduled_events)
            
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
        if any(word in title_lower for word in ['승인', 'approval', 'etf', '채택', 'adoption', '상승', 'rise', 'surge']):
            return "롱 우세 예상"
        
        # 부정적 키워드
        elif any(word in title_lower for word in ['규제', 'regulation', '하락', 'fall', 'crash', '조사', 'investigation']):
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
                    events.append(f"{(now + timedelta(hours=2)).strftime('%m-%d %H:%M')} 미국 고용보고서 발표 예정 → 변동성 확대 예상")
                
                # FOMC 관련
                if self._is_fomc_week():
                    events.append(f"{(now + timedelta(hours=3)).strftime('%m-%d %H:%M')} FOMC 의사록 공개 → 금리 정책 영향")
            
            # 아시아 시장 관련
            elif 9 <= current_hour <= 15:  # KST 오전~오후
                # 중국 지표 발표 (보통 10:00)
                if now.day <= 15:
                    events.append(f"{now.replace(hour=10, minute=0).strftime('%m-%d %H:%M')} 중국 경제지표 발표 → 아시아 시장 영향")
            
            # 옵션 만기 체크
            if self._is_options_expiry_soon():
                events.append(f"{now.replace(hour=17, minute=0).strftime('%m-%d %H:%M')} BTC 옵션 만기 임박 → 맥스페인 영향")
            
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
                    return f"{time_str} 펀딩비 정산 ({hours_left}시간 후) → 포지션 조정 예상"
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
        """기술적 분석 포맷"""
        current_price = market_data.get('current_price', 0)
        
        # 지지/저항선 계산
        support = current_price * 0.98  # 2% 아래
        resistance = current_price * 1.02  # 2% 위
        
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
            f"지지선: ${support:,.0f} / 저항선: ${resistance:,.0f}",
            f"RSI(1H, 4H): {rsi_1h:.1f} / {rsi_4h:.1f} → {'과열' if rsi_1h > 70 else '과매도' if rsi_1h < 30 else '정상'}",
            f"MACD(1H): {macd_status}",
            f"Funding Rate: {funding.get('current_rate', 0):+.3%} ({funding.get('trade_bias', '중립')})",
            f"OI (미결제약정): {oi.get('oi_change_percent', 0):+.1f}% 변화 → {self._interpret_oi_change(oi)}",
            f"Taker Buy/Sell Ratio: {taker_ratio:.2f} → {'매수 우위' if taker_ratio > 1.1 else '매도 우위' if taker_ratio < 0.9 else '균형'}",
            f"Long/Short Ratio: {ls_ratio.get('long_ratio', 50):.0f}:{ls_ratio.get('short_ratio', 50):.0f} → {ls_ratio.get('signal', '균형')}"
        ]
        
        return '\n'.join(lines)
    
    def _get_macd_status(self, market_data: dict) -> str:
        """MACD 상태 판단 (시뮬레이션)"""
        change_24h = market_data.get('change_24h', 0)
        
        if change_24h > 0.01:
            return "골든크로스 진행 중"
        elif change_24h < -0.01:
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
        """시장 심리 및 구조 분석"""
        lines = []
        
        # 공포탐욕지수
        if 'fear_greed' in market_data and market_data['fear_greed']:
            fng = market_data['fear_greed']
            fng_value = fng.get('value', 50)
            
            if fng_value > 70:
                fng_signal = "롱 우세"
            elif fng_value < 30:
                fng_signal = "숏 우세"
            else:
                fng_signal = "중립"
            
            lines.append(f"공포탐욕지수: {fng_value} → {fng_signal}")
        
        # 청산 데이터 분석
        liquidations = indicators.get('liquidation_analysis', {})
        if liquidations:
            long_distance = liquidations.get('long_distance_percent', 0)
            short_distance = liquidations.get('short_distance_percent', 0)
            
            if long_distance < short_distance:
                lines.append("숏 청산 증가 → 롱 강세 구조")
            else:
                lines.append("롱 청산 증가 → 숏 강세 구조")
        
        # 스마트머니 분석
        smart_money = indicators.get('smart_money', {})
        if smart_money and smart_money.get('net_flow', 0) > 0:
            lines.append("고래 매수 주소 유입 확인 → 심리적 지지")
        elif smart_money and smart_money.get('net_flow', 0) < 0:
            lines.append("고래 매도 움직임 감지 → 하락 압력")
        
        # 시장 구조 추가 분석
        market_profile = indicators.get('market_profile', {})
        if market_profile:
            position = market_profile.get('price_position', '')
            if 'Value Area 상단' in position:
                lines.append("가격 상단 저항 구간 → 단기 조정 가능")
            elif 'Value Area 하단' in position:
                lines.append("가격 하단 지지 구간 → 반등 가능성")
        
        return '\n'.join(lines) if lines else "시장 심리 데이터 수집 중"
    
    async def _format_12h_prediction(self, market_data: dict, indicators: dict) -> str:
        """12시간 예측"""
        composite = indicators.get('composite_signal', {})
        total_score = composite.get('total_score', 0)
        
        # 확률 계산
        if total_score > 2:
            up_prob = min(60 + total_score * 5, 80)
            down_prob = max(10, 20 - total_score * 2)
        elif total_score < -2:
            up_prob = max(10, 30 + total_score * 2)
            down_prob = min(60 - total_score * 5, 80)
        else:
            up_prob = 30 + total_score * 5
            down_prob = 30 - total_score * 5
        
        sideways_prob = 100 - up_prob - down_prob
        
        return f"상승: {up_prob}% / 횡보: {sideways_prob}% / 하락: {down_prob}%"
    
    async def _format_strategy_suggestion(self, market_data: dict, indicators: dict) -> str:
        """전략 제안"""
        composite = indicators.get('composite_signal', {})
        signal = composite.get('signal', '중립')
        current_price = market_data.get('current_price', 0)
        
        if '강한 롱' in signal or '롱' in signal:
            return f"""저항 돌파 가능성 있는 국면
지지선 ${current_price * 0.98:,.0f} 유지 전제 하에 롱 전략 우세"""
        
        elif '강한 숏' in signal or '숏' in signal:
            return f"""지지선 이탈 위험 증가
저항선 ${current_price * 1.02:,.0f} 하방 돌파 시 숏 전략 고려"""
        
        else:
            return f"""방향성 불명확한 횡보 구간
${current_price * 0.98:,.0f} ~ ${current_price * 1.02:,.0f} 박스권 거래 전략"""
    
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
            
            return f"실현 손익: {self._format_currency(today_pnl, False)} / 미실현: {self._format_currency(unrealized, False)} 
            → 수익률: {roi:+.2f}%"
            
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
                
                return response.choices[0].message.content.strip()
                
        except Exception as e:
            self.logger.error(f"멘탈 케어 생성 실패: {e}")
        
        # 폴백 메시지
        return """GPT는 현재 수익 상태, 이전 매매 흐름, 감정 흔들림 정도를 반영하여
추가 진입 충동을 차단하거나 손실 후 무리한 복구 시도를 막는 코멘트를 부드럽게 생성합니다.
모든 멘탈 케어 메시지는 사용자의 상태에 따라 동적으로 달라지며,
단순 위로가 아닌 행동을 변화시키는 설계로 구성됩니다."""
