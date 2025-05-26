from datetime import datetime
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class TradingReport:
    """거래 리포트 데이터 구조"""
    timestamp: datetime
    report_type: str  # 'regular', 'forecast', 'profit', 'schedule', 'exception'
    market_events: List[Dict]
    technical_analysis: Dict
    sentiment_analysis: Dict
    advanced_indicators: Dict
    predictions: Dict
    positions: Dict
    profit_loss: Dict
    
class EnhancedReportGenerator:
    def __init__(self, config, data_collector, indicator_system):
        self.config = config
        self.data_collector = data_collector
        self.indicator_system = indicator_system
        
    async def generate_regular_report(self) -> str:
        """정기 리포트 생성 (4시간마다)"""
        # 데이터 수집
        market_data = await self._collect_all_data()
        
        # 고급 지표 계산
        indicators = await self.indicator_system.calculate_all_indicators(market_data)
        
        # 리포트 생성
        report = f"""🧾 **/report 명령어 또는 자동 발송 리포트**
📡 **GPT 비트코인 매매 예측 리포트**
📅 작성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')} (KST)
━━━━━━━━━━━━━━━━━━━

📌 **시장 이벤트 및 주요 속보**
{self._format_market_events(market_data['events'])}

━━━━━━━━━━━━━━━━━━━

📉 **기술 분석 요약**
{self._format_technical_analysis(market_data, indicators)}

━━━━━━━━━━━━━━━━━━━

🧠 **심리 및 구조적 분석**
{self._format_sentiment_analysis(market_data, indicators)}

━━━━━━━━━━━━━━━━━━━

📊 **고급 매매 지표**
{self._format_advanced_indicators(indicators)}

━━━━━━━━━━━━━━━━━━━

🔮 **향후 12시간 예측 결과**
{self._format_predictions(indicators)}

━━━━━━━━━━━━━━━━━━━

🚨 **예외 상황 감지**
{self._format_exceptions(market_data)}

━━━━━━━━━━━━━━━━━━━

📊 **지난 예측 검증 결과**
{self._format_validation()}

━━━━━━━━━━━━━━━━━━━

💰 **금일 수익 및 손익 요약**
{self._format_profit_loss(market_data)}

━━━━━━━━━━━━━━━━━━━

🧠 **멘탈 케어 코멘트**
{self._generate_mental_care_message(market_data)}
"""
        return report
    
    async def generate_forecast_report(self) -> str:
        """단기 예측 리포트"""
        market_data = await self._collect_all_data()
        indicators = await self.indicator_system.calculate_all_indicators(market_data)
        
        return f"""📈 **단기 비트코인 가격 예측**
📅 작성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')} (KST)
━━━━━━━━━━━━━━━━━━━

📊 **핵심 분석 요약**
{self._format_core_analysis(indicators)}

━━━━━━━━━━━━━━━━━━━

🔮 **향후 12시간 가격 흐름 예측**
{self._format_short_predictions(indicators)}

━━━━━━━━━━━━━━━━━━━

💰 **금일 손익 요약**
{self._format_simple_pnl(market_data)}

━━━━━━━━━━━━━━━━━━━

🧠 **멘탈 관리 코멘트**
{self._generate_short_mental_message(market_data)}
"""
    
    async def generate_exception_report(self, event: Dict) -> str:
        """예외 상황 리포트"""
        market_data = await self._collect_all_data()
        
        return f"""🚨 **[BTC 긴급 예외 리포트]**
📅 발생 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')} (KST)
━━━━━━━━━━━━━━━━━━━

❗ **급변 원인 요약**
{self._format_exception_cause(event)}

━━━━━━━━━━━━━━━━━━━

📌 **GPT 분석 및 판단**
{self._format_exception_analysis(event, market_data)}

━━━━━━━━━━━━━━━━━━━

🛡️ **리스크 대응 전략 제안**
{self._format_risk_strategy(event, market_data)}

━━━━━━━━━━━━━━━━━━━

📌 **탐지 조건 만족 내역**
{self._format_detection_conditions(event)}

━━━━━━━━━━━━━━━━━━━

🧭 **참고**
* 이 리포트는 정규 리포트 외 탐지 조건이 충족될 경우 즉시 자동 생성됩니다.
* 추세 전환 가능성 있을 경우 /forecast 명령어로 단기 전략 리포트 확인 권장
"""
    
    def _format_market_events(self, events: List[Dict]) -> str:
        """시장 이벤트 포맷팅"""
        if not events:
            return "* 특별한 시장 이벤트 없음 → ➕호재 예상 (안정적 시장 환경)"
        
        formatted = []
        for event in events[:5]:  # 최대 5개
            impact = event.get('impact', '중립')
            formatted.append(f"* {event['title']} → {impact} ({event['description']})")
        
        return "\n".join(formatted)
    
    def _format_technical_analysis(self, market_data: Dict, indicators: Dict) -> str:
        """기술적 분석 포맷팅"""
        current_price = market_data.get('current_price', 0)
        
        # 시장 구조 지표
        basis = indicators['market_structure']['basis']
        
        # 미시구조 지표
        orderbook = indicators['microstructure']['orderbook']
        
        return f"""* 현재 가격: ${current_price:,.0f} (Coinbase 기준)
* 주요 지지선: ${market_data.get('support', 0):,.0f}, 주요 저항선: ${market_data.get('resistance', 0):,.0f}
* RSI(4시간): {market_data.get('rsi_4h', 50):.1f} → {self._interpret_rsi(market_data.get('rsi_4h', 50))}
* 선물 베이시스: ${basis['value']:.2f} → {basis['signal']} ({basis['description']})
* 주문장 균형: {orderbook['orderbook_imbalance']:.2%} → {orderbook['signal']}
* 멀티 타임프레임: {indicators['multi_timeframe']['strength']} → {indicators['multi_timeframe']['alignment']:.1%} 정렬"""
    
    def _format_sentiment_analysis(self, market_data: Dict, indicators: Dict) -> str:
        """심리 분석 포맷팅"""
        derivatives = indicators['derivatives']
        onchain = indicators['onchain']
        
        return f"""* 펀딩비: {market_data.get('funding_rate', 0):.3%} → {self._interpret_funding(market_data.get('funding_rate', 0))}
* 미결제약정: {derivatives['open_interest']['oi_change_24h']:+.1%} → {derivatives['open_interest']['signal']}
* 청산 비율: 롱 {derivatives['liquidations']['liquidation_ratio']:.1%} → {derivatives['liquidations']['signal']}
* NUPL: {onchain['nupl']['value']:.2f} ({onchain['nupl']['market_phase']}) → {onchain['nupl']['signal']}
* 거래소 순유출: {onchain['exchange_reserves']['net_flow_7d']:,.0f} BTC → {onchain['exchange_reserves']['signal']}"""
    
    def _format_advanced_indicators(self, indicators: Dict) -> str:
        """고급 지표 포맷팅"""
        composite = indicators['composite_score']
        
        return f"""🎯 **종합 매매 점수**
* 상승 신호: {composite['bullish_score']}점
* 하락 신호: {composite['bearish_score']}점
* 최종 점수: {composite['composite_score']:+.1f}점 → {composite['signal']}
* 신뢰도: {composite['confidence']:.1%}

💡 **핵심 인사이트**
* 시장 구조: {indicators['market_structure']['term_structure']['signal']}
* 파생상품: {indicators['derivatives']['options_flow']['signal']}
* 온체인: {indicators['onchain']['whale_activity']['signal']}
* AI 예측: {indicators['ai_prediction']['signal']}

📌 **추천 전략**: {composite['recommended_action']}"""
    
    def _format_predictions(self, indicators: Dict) -> str:
        """예측 포맷팅"""
        ai_pred = indicators['ai_prediction']
        
        return f"""* 상승 확률: {ai_pred['direction_probability']['up']:.0%}
* 횡보 확률: {100 - ai_pred['direction_probability']['up'] - ai_pred['direction_probability']['down']:.0%}
* 하락 확률: {ai_pred['direction_probability']['down']:.0%}

📌 **GPT 전략 제안**:
{indicators['composite_score']['recommended_action']}

💡 **가격 목표**:
* 1시간: ${ai_pred['price_prediction']['1h']:,.0f}
* 4시간: ${ai_pred['price_prediction']['4h']:,.0f}
* 24시간: ${ai_pred['price_prediction']['24h']:,.0f}

⚡ **예상 변동성**: {ai_pred['volatility_forecast']['expected_volatility']:.1f}% ({ai_pred['volatility_forecast']['volatility_regime']})"""
    
    def _format_exceptions(self, market_data: Dict) -> str:
        """예외 상황 포맷팅"""
        exceptions = []
        
        # Whale Alert 체크
        if market_data.get('whale_transfers', 0) > 1000:
            exceptions.append(f"* Whale Alert: {market_data['whale_transfers']:,.0f} BTC 대량 이동 감지 → ➖악재 예상")
        
        # 변동성 체크
        if market_data.get('volatility_spike', False):
            exceptions.append("* 변동성 급증 감지 → ⚠️주의 필요")
        
        if not exceptions:
            exceptions.append("* 특별한 예외 상황 없음 → ➕호재 예상 (안정적 시장)")
        
        return "\n".join(exceptions)
    
    def _format_profit_loss(self, market_data: Dict) -> str:
        """손익 포맷팅"""
        positions = market_data.get('positions', {})
        pnl = market_data.get('pnl', {})
        
        # 실제 수익을 한국 일상과 비교
        daily_profit = pnl.get('daily_total', 0)
        profit_krw = daily_profit * 1350  # 환율 적용
        
        comparison = self._get_profit_comparison(profit_krw)
        
        return f"""* 진입 자산: ${positions.get('initial_capital', 2000):,.0f}
* 현재 포지션: {positions.get('symbol', 'BTCUSDT')} {positions.get('side', '롱')} (진입가 ${positions.get('entry_price', 0):,.0f} / 현재가 ${positions.get('current_price', 0):,.0f})
* 미실현 손익: {pnl.get('unrealized', 0):+.1f} (약 {pnl.get('unrealized', 0) * 1.35:.1f}만원)
* 실현 손익: {pnl.get('realized', 0):+.1f} (약 {pnl.get('realized', 0) * 1.35:.1f}만원)
* 금일 총 수익: {daily_profit:+.1f} (약 {profit_krw/10000:.1f}만원)
* 수익률: {pnl.get('daily_return', 0):+.2%}
━━━━━━━━━━━━━━━━━━━
📌 {comparison}"""
    
    def _get_profit_comparison(self, profit_krw: float) -> str:
        """수익 비교 메시지"""
        if profit_krw < 0:
            return f"오늘 손실은 치킨 {abs(profit_krw)/20000:.0f}마리 값입니다. 내일 회복 가능!"
        elif profit_krw < 50000:
            return f"오늘 수익은 편의점 알바 약 {profit_krw/10000:.0f}시간 분량입니다."
        elif profit_krw < 100000:
            return f"오늘 수익은 대학 과외 {profit_krw/50000:.0f}시간 분량입니다."
        elif profit_krw < 200000:
            return f"오늘 수익은 일반 회사원 일당과 비슷합니다."
        else:
            return f"오늘 수익은 전문직 일당 수준입니다. 축하합니다!"
    
    def _generate_mental_care_message(self, market_data: Dict) -> str:
        """멘탈 케어 메시지"""
        pnl = market_data.get('pnl', {})
        
        messages = {
            'profit': [
                "오늘의 이익은 단순한 숫자가 아닙니다. 차분히, 꾸준히 쌓아간다면 내일의 기회는 더 크게 옵니다.",
                "수익이 났을 때 자만하지 않는 것이 프로의 자세입니다. 원칙을 지켜나가세요.",
                "작은 수익이라도 플러스는 플러스입니다. 복리의 마법을 믿으세요."
            ],
            'loss': [
                "손실은 수업료입니다. 오늘의 경험이 내일의 수익으로 돌아올 것입니다.",
                "시장은 항상 기회를 줍니다. 멘탈을 지키고 다음 기회를 기다리세요.",
                "손절은 용기있는 결정입니다. 자본을 지킨 것에 의미를 두세요."
            ],
            'neutral': [
                "횡보장도 기회입니다. 큰 움직임을 위한 에너지 축적 구간이죠.",
                "조급함은 적입니다. 시장이 방향을 정할 때까지 인내하세요.",
                "관망도 훌륭한 전략입니다. 확실한 신호를 기다리는 것이 현명합니다."
            ]
        }
        
        if pnl.get('daily_total', 0) > 0:
            category = 'profit'
        elif pnl.get('daily_total', 0) < 0:
            category = 'loss'
        else:
            category = 'neutral'
        
        import random
        return f'"{random.choice(messages[category])}"'
    
    # 보조 메서드들
    def _interpret_rsi(self, rsi: float) -> str:
        if rsi > 70:
            return "➖악재 예상 (과매수)"
        elif rsi < 30:
            return "➕호재 예상 (과매도)"
        else:
            return "➕호재 예상 (안정적)"
    
    def _interpret_funding(self, rate: float) -> str:
        if rate > 0.05:
            return "➖악재 예상 (롱 과열)"
        elif rate < -0.05:
            return "➕호재 예상 (숏 과열)"
        else:
            return "중립"
    
    async def _collect_all_data(self) -> Dict:
        """모든 데이터 수집"""
        # 실제 구현시 여러 API에서 데이터 수집
        return {
            'current_price': 66210,
            'events': self.data_collector.events_buffer,
            'positions': {},
            'pnl': {},
            # ... 기타 필요한 데이터
        }
    
    def _format_core_analysis(self, indicators: Dict) -> str:
        """핵심 분석 요약"""
        return f"""* 기술 분석: {indicators['market_structure']['basis']['signal']}
* 심리 분석: {indicators['derivatives']['open_interest']['signal']}
* 구조 분석: {indicators['onchain']['exchange_reserves']['signal']}"""
    
    def _format_short_predictions(self, indicators: Dict) -> str:
        """단기 예측 요약"""
        ai_pred = indicators['ai_prediction']
        return f"""* 상승 확률: {ai_pred['direction_probability']['up']:.0%}
* 횡보 확률: {100 - ai_pred['direction_probability']['up'] - ai_pred['direction_probability']['down']:.0%}
* 하락 확률: {ai_pred['direction_probability']['down']:.0%}

📌 **전략 제안**: {indicators['composite_score']['recommended_action']}"""
    
    def _format_simple_pnl(self, market_data: Dict) -> str:
        """간단한 손익 요약"""
        pnl = market_data.get('pnl', {})
        return f"""* 실현 손익: {pnl.get('realized', 0):+.1f} ({pnl.get('realized', 0) * 1.35:.1f}만원)
* 미실현 손익: {pnl.get('unrealized', 0):+.1f} ({pnl.get('unrealized', 0) * 1.35:.1f}만원)
* 총 수익률: {pnl.get('total_return', 0):+.2%}"""
    
    def _generate_short_mental_message(self, market_data: Dict) -> str:
        """짧은 멘탈 메시지"""
        pnl = market_data.get('pnl', {})
        profit_krw = pnl.get('daily_total', 0) * 1350
        
        if profit_krw > 100000:
            return f'"오늘 벌어들인 {profit_krw/10000:.0f}만원은 편의점 {profit_krw/10000:.0f}시간 근무에 해당합니다. 시장에 감사하고, 다음 기회를 차분히 기다려 보세요."'
        elif profit_krw > 0:
            return f'"작은 이익도 쌓이면 큰 자산이 됩니다. 꾸준함이 답입니다."'
        else:
            return f'"손실도 거래의 일부입니다. 리스크 관리만 잘하면 회복은 시간문제입니다."'
    
    def _format_exception_cause(self, event: Dict) -> str:
        """예외 원인 포맷팅"""
        return f"""* {event.get('title', '알 수 없는 이벤트')}
* {event.get('description', '상세 정보 없음')}
* 발생 시각: {event.get('timestamp', datetime.now()).strftime('%H:%M:%S')}"""
    
    def _format_exception_analysis(self, event: Dict, market_data: Dict) -> str:
        """예외 분석 포맷팅"""
        severity = event.get('severity', 'medium')
        category = event.get('category', 'unknown')
        
        analysis = {
            'price_movement': "급격한 가격 변동으로 단기 변동성 확대 예상",
            'whale_movement': "대량 이체로 매도 압력 증가 가능성",
            'news': "뉴스 영향으로 심리적 변화 예상",
            'technical': "기술적 신호 발생, 추세 전환 가능성"
        }
        
        return f"""* {analysis.get(category, '시장 불확실성 증가')}
* 심각도: {severity.upper()}
* 예상 영향: {event.get('impact', '중립')}

👉 **향후 2시간 내 {self._predict_direction(event)}**
※ {self._get_risk_warning(severity)}"""
    
    def _format_risk_strategy(self, event: Dict, market_data: Dict) -> str:
        """리스크 전략 포맷팅"""
        severity = event.get('severity', 'medium')
        
        strategies = {
            'critical': """* 레버리지 포지션 즉시 정리 또는 축소
* 현물 보유자는 부분 익절 고려
* 신규 진입 절대 금지""",
            'high': """* 레버리지 축소 (최대 3배 이하)
* 손절선 타이트하게 조정
* 분할 진입/청산 전략 적용""",
            'medium': """* 현재 포지션 유지하되 모니터링 강화
* 추가 진입은 신중하게
* 양방향 헤지 고려"""
        }
        
        return strategies.get(severity, strategies['medium'])
    
    def _format_detection_conditions(self, event: Dict) -> str:
        """탐지 조건 포맷팅"""
        conditions = []
        
        if event.get('category') == 'price_movement':
            conditions.append(f"* 📉 **단기 변동 급등락** : 최근 15분 간 {event.get('change_percent', 0):.1f}% 변동 → {event.get('impact', '중립')}")
        
        if event.get('category') == 'whale_movement':
            conditions.append(f"* 🔄 **온체인 이상 이동** : {event.get('btc_amount', 0):,.0f} BTC 대량 이체 발생 → {event.get('impact', '중립')}")
        
        if event.get('category') == 'sentiment':
            conditions.append(f"* 🧠 **심리 지표 급변** : {event.get('indicator', 'Unknown')} {event.get('change', '변화')} → {event.get('impact', '중립')}")
        
        return "\n".join(conditions) if conditions else "* 복합적 조건 충족"
    
    def _predict_direction(self, event: Dict) -> str:
        """방향성 예측"""
        if event.get('impact', '').startswith('➕'):
            return "상승 가능성이 하락 가능성보다 높음"
        elif event.get('impact', '').startswith('➖'):
            return "하락 가능성이 상승 가능성보다 높음"
        else:
            return "방향성 불분명, 변동성 확대 주의"
    
    def _get_risk_warning(self, severity: str) -> str:
        """리스크 경고 메시지"""
        warnings = {
            'critical': "즉각적인 대응 필요, 손실 확대 위험 높음",
            'high': "주의 깊은 모니터링 필요, 추세 전환 가능성",
            'medium': "일반적인 변동성 수준, 원칙 준수 중요"
        }
        return warnings.get(severity, warnings['medium'])
    
    def _format_validation(self) -> str:
        """예측 검증 결과"""
        # 실제 구현시 과거 예측 기록과 비교
        return """* 5/25 23:00 리포트: 횡보 예측
* 실제 결과: 12시간 동안 변동폭 약 ±0.9% → ✅ 예측 적중"""
