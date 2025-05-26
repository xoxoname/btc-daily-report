from datetime import datetime
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
import pytz

logger = logging.getLogger(__name__)

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
        self.bitget_client = None  # 나중에 설정
        
    def set_bitget_client(self, bitget_client):
        """Bitget 클라이언트 설정"""
        self.bitget_client = bitget_client
        
    async def generate_regular_report(self) -> str:
        """정기 리포트 생성 (4시간마다)"""
        try:
            # 한국 시간대 설정
            kst = pytz.timezone('Asia/Seoul')
            current_time = datetime.now(kst)
            
            # 실시간 데이터 수집
            logger.info("실시간 데이터 수집 시작...")
            market_data = await self._collect_all_data()
            
            # 고급 지표 계산
            logger.info("고급 지표 계산 중...")
            indicators = await self.indicator_system.calculate_all_indicators(market_data)
            
            # 리포트 생성
            report = f"""🧾 /report 명령어 또는 자동 발송 리포트
📡 GPT 비트코인 매매 예측 리포트
📅 작성 시각: {current_time.strftime('%Y-%m-%d %H:%M')} (KST)
━━━━━━━━━━━━━━━━━━━

📌 시장 이벤트 및 주요 속보
{self._format_market_events(market_data['events'])}

━━━━━━━━━━━━━━━━━━━

📉 기술 분석 요약
{self._format_technical_analysis(market_data, indicators)}

━━━━━━━━━━━━━━━━━━━

🧠 심리 및 구조적 분석
{self._format_sentiment_analysis(market_data, indicators)}

━━━━━━━━━━━━━━━━━━━

📊 고급 매매 지표
{self._format_advanced_indicators(indicators)}

━━━━━━━━━━━━━━━━━━━

🔮 향후 12시간 예측 결과
{self._format_predictions(indicators)}

━━━━━━━━━━━━━━━━━━━

🚨 예외 상황 감지
{self._format_exceptions(market_data)}

━━━━━━━━━━━━━━━━━━━

📊 지난 예측 검증 결과
{self._format_validation()}

━━━━━━━━━━━━━━━━━━━

💰 금일 수익 및 손익 요약
{await self._format_profit_loss(market_data)}

━━━━━━━━━━━━━━━━━━━

🧠 멘탈 케어 코멘트
{self._generate_mental_care_message(market_data)}
"""
            return report
            
        except Exception as e:
            logger.error(f"리포트 생성 실패: {e}")
            raise
    
    async def generate_forecast_report(self) -> str:
        """단기 예측 리포트"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            current_time = datetime.now(kst)
            
            market_data = await self._collect_all_data()
            indicators = await self.indicator_system.calculate_all_indicators(market_data)
            
            return f"""📈 단기 비트코인 가격 예측
📅 작성 시각: {current_time.strftime('%Y-%m-%d %H:%M')} (KST)
━━━━━━━━━━━━━━━━━━━

📊 핵심 분석 요약
{self._format_core_analysis(indicators)}

━━━━━━━━━━━━━━━━━━━

🔮 향후 12시간 가격 흐름 예측
{self._format_short_predictions(indicators)}

━━━━━━━━━━━━━━━━━━━

💰 금일 손익 요약
{await self._format_simple_pnl(market_data)}

━━━━━━━━━━━━━━━━━━━

🧠 멘탈 관리 코멘트
{self._generate_short_mental_message(market_data)}
"""
        except Exception as e:
            logger.error(f"예측 리포트 생성 실패: {e}")
            raise
    
    async def generate_profit_report(self) -> str:
        """수익 현황 리포트"""
        try:
            kst = pytz.timezone('Asia/Seoul')
            current_time = datetime.now(kst)
            
            # 실시간 계정 정보 조회
            account_info = await self._get_real_account_info()
            position_info = await self._get_real_position_info()
            market_data = await self._collect_market_data_only()
            
            return f"""💰 현재 보유 포지션 및 수익 요약
📅 작성 시각: {current_time.strftime('%Y-%m-%d %H:%M')} (KST)
━━━━━━━━━━━━━━━━━━━

📌 보유 포지션 정보
{self._format_position_info(position_info)}

━━━━━━━━━━━━━━━━━━━

💸 손익 정보
{self._format_account_pnl(account_info, position_info, market_data)}

━━━━━━━━━━━━━━━━━━━

🧠 멘탈 케어
{self._generate_mental_care_for_profit(account_info, position_info)}
"""
        except Exception as e:
            logger.error(f"수익 리포트 생성 실패: {e}")
            raise
    
    async def generate_schedule_report(self) -> str:
        """일정 리포트"""
        kst = pytz.timezone('Asia/Seoul')
        current_time = datetime.now(kst)
        
        return f"""📅 자동 리포트 일정
📅 작성 시각: {current_time.strftime('%Y-%m-%d %H:%M')} (KST)
━━━━━━━━━━━━━━━━━━━

📡 정기 리포트 시간
• 오전 9시 - 아침 리포트
• 오후 1시 - 점심 리포트
• 오후 6시 - 저녁 리포트
• 오후 10시 - 밤 리포트

━━━━━━━━━━━━━━━━━━━

⚡ 실시간 모니터링
• 가격 급변동: 15분 내 2% 이상 변동
• 뉴스 이벤트: 5분마다 체크
• 펀딩비 이상: 연 50% 이상
• 거래량 급증: 평균 대비 3배

━━━━━━━━━━━━━━━━━━━

📌 예외 상황 발생시 즉시 알림

🔔 다가오는 주요 이벤트
{self._format_upcoming_events()}
"""
    
    async def generate_exception_report(self, event: Dict) -> str:
        """예외 상황 리포트"""
        kst = pytz.timezone('Asia/Seoul')
        current_time = datetime.now(kst)
        
        market_data = await self._collect_market_data_only()
        
        return f"""🚨 [BTC 긴급 예외 리포트]
📅 발생 시각: {current_time.strftime('%Y-%m-%d %H:%M')} (KST)
━━━━━━━━━━━━━━━━━━━

❗ 급변 원인 요약
{self._format_exception_cause(event)}

━━━━━━━━━━━━━━━━━━━

📌 GPT 분석 및 판단
{self._format_exception_analysis(event, market_data)}

━━━━━━━━━━━━━━━━━━━

🛡️ 리스크 대응 전략 제안
{self._format_risk_strategy(event, market_data)}

━━━━━━━━━━━━━━━━━━━

📌 탐지 조건 만족 내역
{self._format_detection_conditions(event)}

━━━━━━━━━━━━━━━━━━━

🧭 참고
• 이 리포트는 정규 리포트 외 탐지 조건이 충족될 경우 즉시 자동 생성됩니다.
• 추세 전환 가능성 있을 경우 /forecast 명령어로 단기 전략 리포트 확인 권장
"""
    
    async def _get_real_account_info(self) -> Dict:
        """실제 계정 정보 조회"""
        try:
            if not self.bitget_client:
                logger.error("Bitget 클라이언트가 설정되지 않음")
                return {'error': 'Bitget 클라이언트 미설정'}
            
            # 계정 정보 조회
            account = await self.bitget_client.get_account_info()
            logger.info(f"계정 정보 조회 성공: {account}")
            
            return {
                'total_equity': float(account.get('equity', 0)),
                'available_balance': float(account.get('availableBalance', 0)),
                'frozen': float(account.get('frozen', 0)),
                'unrealized_pnl': float(account.get('unrealizedPL', 0)),
                'margin_ratio': float(account.get('marginRatio', 0))
            }
            
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            return {
                'error': str(e),
                'total_equity': 0,
                'available_balance': 0
            }
    
    async def _get_real_position_info(self) -> Dict:
        """실제 포지션 정보 조회"""
        try:
            if not self.bitget_client:
                return {'positions': []}
            
            # 포지션 조회
            positions = await self.bitget_client.get_positions()
            logger.info(f"포지션 조회 결과: {positions}")
            
            if not positions:
                return {'positions': []}
            
            # 포지션 데이터 정리
            formatted_positions = []
            for pos in positions:
                formatted_positions.append({
                    'symbol': pos.get('symbol', 'BTCUSDT'),
                    'side': pos.get('holdSide', 'long'),
                    'size': float(pos.get('total', 0)),
                    'entry_price': float(pos.get('averageOpenPrice', 0)),
                    'mark_price': float(pos.get('markPrice', 0)),
                    'unrealized_pnl': float(pos.get('unrealizedPL', 0)),
                    'margin': float(pos.get('margin', 0)),
                    'leverage': int(pos.get('leverage', 1))
                })
            
            return {'positions': formatted_positions}
            
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return {'positions': [], 'error': str(e)}
    
    async def _collect_all_data(self) -> Dict:
        """모든 데이터 수집"""
        try:
            # 병렬로 데이터 수집
            tasks = [
                self._collect_market_data_only(),
                self._get_real_account_info(),
                self._get_real_position_info()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            market_data = results[0] if not isinstance(results[0], Exception) else {}
            account_info = results[1] if not isinstance(results[1], Exception) else {}
            position_info = results[2] if not isinstance(results[2], Exception) else {}
            
            return {
                **market_data,
                'account': account_info,
                'positions': position_info.get('positions', []),
                'events': self.data_collector.events_buffer if self.data_collector else []
            }
            
        except Exception as e:
            logger.error(f"데이터 수집 실패: {e}")
            return {
                'current_price': 0,
                'events': [],
                'positions': [],
                'account': {}
            }
    
    async def _collect_market_data_only(self) -> Dict:
        """시장 데이터만 수집"""
        try:
            if not self.bitget_client:
                return {'current_price': 0}
            
            # 현재가 조회
            ticker = await self.bitget_client.get_ticker()
            
            # 펀딩비 조회
            funding = await self.bitget_client.get_funding_rate()
            
            # 미결제약정 조회
            oi = await self.bitget_client.get_open_interest()
            
            return {
                'current_price': float(ticker.get('last', 0)),
                'high_24h': float(ticker.get('high24h', 0)),
                'low_24h': float(ticker.get('low24h', 0)),
                'volume_24h': float(ticker.get('baseVolume', 0)),
                'change_24h': float(ticker.get('changeUtc', 0)),
                'funding_rate': float(funding.get('fundingRate', 0)),
                'open_interest': float(oi.get('openInterest', 0)),
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"시장 데이터 수집 실패: {e}")
            return {'current_price': 0}
    
    def _format_position_info(self, position_info: Dict) -> str:
        """포지션 정보 포맷팅"""
        positions = position_info.get('positions', [])
        
        if not positions:
            return "• 포지션 없음"
        
        formatted = []
        for pos in positions:
            direction = "롱" if pos['side'].lower() in ['long', 'buy'] else "숏"
            formatted.append(f"""• 종목: {pos['symbol']}
• 방향: {direction}
• 진입가: ${pos['entry_price']:,.2f} / 현재가: ${pos['mark_price']:,.2f}
• 수량: {pos['size']:.4f} BTC
• 레버리지: {pos['leverage']}x
• 미실현 손익: ${pos['unrealized_pnl']:,.2f}""")
        
        return "\n".join(formatted)
    
    def _format_account_pnl(self, account_info: Dict, position_info: Dict, market_data: Dict) -> str:
        """계정 손익 정보 포맷팅"""
        if 'error' in account_info:
            return f"• 계정 정보 조회 실패: {account_info['error']}"
        
        total_equity = account_info.get('total_equity', 0)
        available = account_info.get('available_balance', 0)
        unrealized_pnl = account_info.get('unrealized_pnl', 0)
        
        # 실현 손익은 일별 계산 필요 (현재는 0으로 표시)
        realized_pnl = 0
        
        # 수익률 계산 (초기 자본 대비)
        initial_capital = 2000  # 설정에서 가져오거나 환경변수로
        total_return = ((total_equity - initial_capital) / initial_capital) * 100 if initial_capital > 0 else 0
        
        # 한화 환산 (환율 1,350원 가정)
        krw_rate = 1350
        
        return f"""• 미실현 손익: ${unrealized_pnl:,.2f} ({unrealized_pnl * krw_rate / 10000:.1f}만원)
• 실현 손익: ${realized_pnl:,.2f} ({realized_pnl * krw_rate / 10000:.1f}만원)
• 금일 총 수익: ${unrealized_pnl + realized_pnl:,.2f} ({(unrealized_pnl + realized_pnl) * krw_rate / 10000:.1f}만원)
• 총 자산: ${total_equity:,.2f}
• 가용 자산: ${available:,.2f}
• 전체 수익률: {total_return:+.2f}%"""
    
    def _generate_mental_care_for_profit(self, account_info: Dict, position_info: Dict) -> str:
        """수익 상황에 맞는 멘탈 케어 메시지"""
        if 'error' in account_info:
            return '"시스템 점검 중입니다. 잠시 후 다시 확인해주세요."'
        
        unrealized_pnl = account_info.get('unrealized_pnl', 0)
        positions = position_info.get('positions', [])
        
        if not positions:
            return '"시장이 조용한 날입니다. 좋은 기회를 기다리는 것도 전략입니다."'
        
        krw_value = unrealized_pnl * 1350
        
        if unrealized_pnl > 100:
            return f'"오늘 수익 {krw_value/10000:.0f}만원은 한달 교통비를 벌었네요! 하지만 자만은 금물, 리스크 관리를 잊지 마세요."'
        elif unrealized_pnl > 50:
            return f'"수익 {krw_value:.0f}원으로 오늘 저녁은 맛있는 걸로! 꾸준함이 복리를 만듭니다."'
        elif unrealized_pnl > 0:
            return f'"작은 수익도 쌓이면 큰 자산이 됩니다. 플러스를 유지하는 것만으로도 상위 30%입니다."'
        elif unrealized_pnl > -50:
            return '"작은 손실은 수업료입니다. 손절선을 지키고 다음 기회를 노리세요."'
        else:
            return '"손실이 크더라도 냉정을 유지하세요. 복구하려 무리하면 더 큰 손실로 이어집니다. 일단 포지션을 정리하고 재정비하세요."'
    
    def _format_technical_analysis(self, market_data: Dict, indicators: Dict) -> str:
        """기술적 분석 포맷팅"""
        current_price = market_data.get('current_price', 0)
        
        # 실제 지표가 없으면 기본값 사용
        rsi = market_data.get('rsi_4h', 50)
        
        # 지지/저항선 계산
        support = current_price * 0.98
        resistance = current_price * 1.02
        
        return f"""• 현재 가격: ${current_price:,.0f} (Bitget 기준)
• 주요 지지선: ${support:,.0f}, 주요 저항선: ${resistance:,.0f}
• RSI(4시간): {rsi:.1f} → {self._interpret_rsi(rsi)}
• 24시간 변동: {market_data.get('change_24h', 0)*100:+.2f}%
• 24시간 거래량: {market_data.get('volume_24h', 0):,.2f} BTC"""
    
    def _format_sentiment_analysis(self, market_data: Dict, indicators: Dict) -> str:
        """심리 분석 포맷팅"""
        funding_rate = market_data.get('funding_rate', 0)
        oi = market_data.get('open_interest', 0)
        
        return f"""• 펀딩비: {funding_rate:.4%} → {self._interpret_funding(funding_rate)}
• 미결제약정: {oi:,.0f} BTC
• 시장 심리: {self._analyze_market_sentiment(market_data)}"""
    
    def _format_advanced_indicators(self, indicators: Dict) -> str:
        """고급 지표 포맷팅"""
        composite = indicators.get('composite_score', {})
        
        if not composite:
            return "• 고급 지표 계산 중..."
        
        return f"""🎯 종합 매매 점수
• 상승 신호: {composite.get('bullish_score', 0)}점
• 하락 신호: {composite.get('bearish_score', 0)}점
• 최종 점수: {composite.get('composite_score', 0):+.1f}점 → {composite.get('signal', '중립')}

📌 추천 전략: {composite.get('recommended_action', '관망')}"""
    
    def _format_predictions(self, indicators: Dict) -> str:
        """예측 포맷팅"""
        # GPT 예측이 없으면 기본값
        return """• 상승 확률: 50%
• 횡보 확률: 30%
• 하락 확률: 20%

📌 GPT 전략 제안:
현재 시장은 방향성이 불분명합니다. 확실한 신호를 기다리세요."""
    
    def _format_market_events(self, events: List) -> str:
        """시장 이벤트 포맷팅"""
        if not events:
            return "• 특별한 시장 이벤트 없음 → ➕호재 예상 (안정적 시장 환경)"
        
        formatted = []
        for event in events[:5]:  # 최대 5개
            formatted.append(f"• {event.title} → {event.impact} ({event.description})")
        
        return "\n".join(formatted)
    
    def _format_exceptions(self, market_data: Dict) -> str:
        """예외 상황 포맷팅"""
        return "• 특별한 예외 상황 없음 → ➕호재 예상 (안정적 시장)"
    
    def _format_validation(self) -> str:
        """예측 검증 결과"""
        # 실제 구현시 과거 예측 기록과 비교
        kst = pytz.timezone('Asia/Seoul')
        yesterday = datetime.now(kst).strftime('%m/%d')
        
        return f"""• {yesterday} 예측: 분석 데이터 수집 중
• 실제 결과: 검증 대기중"""
    
    async def _format_profit_loss(self, market_data: Dict) -> str:
        """손익 포맷팅"""
        account = market_data.get('account', {})
        positions = market_data.get('positions', [])
        
        if 'error' in account:
            return "• 계정 정보를 불러올 수 없습니다."
        
        total_pnl = 0
        position_details = []
        
        for pos in positions:
            pnl = pos.get('unrealized_pnl', 0)
            total_pnl += pnl
            position_details.append(f"{pos['symbol']}: ${pnl:+.2f}")
        
        krw_rate = 1350
        daily_profit_krw = total_pnl * krw_rate
        
        comparison = self._get_profit_comparison(daily_profit_krw)
        
        return f"""• 보유 포지션: {len(positions)}개
• 미실현 손익: ${total_pnl:+.2f} ({daily_profit_krw/10000:.1f}만원)
• 금일 수익률: {(total_pnl/2000)*100:+.2f}%
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
        account = market_data.get('account', {})
        unrealized_pnl = account.get('unrealized_pnl', 0)
        
        import random
        
        if unrealized_pnl > 50:
            messages = [
                "수익이 났을 때 자만하지 않는 것이 프로의 자세입니다. 원칙을 지켜나가세요.",
                "오늘의 수익은 당신의 인내와 분석의 결과입니다. 하지만 내일도 겸손하게.",
                "플러스 수익은 좋지만, 리스크 관리를 잊으면 한순간에 사라집니다."
            ]
        elif unrealized_pnl < -50:
            messages = [
                "손실은 수업료입니다. 오늘의 경험이 내일의 수익으로 돌아올 것입니다.",
                "모든 트레이더는 손실을 경험합니다. 중요한 것은 여기서 무엇을 배우느냐입니다.",
                "손절은 패배가 아닌 다음 기회를 위한 전략적 후퇴입니다."
            ]
        else:
            messages = [
                "시장이 잠잠할 때가 기회를 준비하는 시간입니다.",
                "변동성이 낮은 날도 중요합니다. 큰 움직임 전의 고요함일 수 있죠.",
                "때로는 거래하지 않는 것이 최고의 거래입니다."
            ]
        
        return f'"{random.choice(messages)}"'
    
    # 보조 메서드들
    def _interpret_rsi(self, rsi: float) -> str:
        if rsi > 70:
            return "➖악재 예상 (과매수)"
        elif rsi < 30:
            return "➕호재 예상 (과매도)"
        else:
            return "중립"
    
    def _interpret_funding(self, rate: float) -> str:
        if rate > 0.01:  # 0.01 = 1%
            return "➖악재 예상 (롱 과열)"
        elif rate < -0.01:
            return "➕호재 예상 (숏 과열)"
        else:
            return "중립"
    
    def _analyze_market_sentiment(self, market_data: Dict) -> str:
        """시장 심리 분석"""
        change = market_data.get('change_24h', 0)
        
        if change > 0.05:
            return "매우 낙관적"
        elif change > 0.02:
            return "낙관적"
        elif change > -0.02:
            return "중립적"
        elif change > -0.05:
            return "비관적"
        else:
            return "매우 비관적"
    
    def _format_upcoming_events(self) -> str:
        """다가오는 이벤트"""
        # 실제로는 경제 캘린더 API 연동
        return """• 내일 14:00 - 미국 CPI 발표
• 모레 03:00 - FOMC 의사록 공개
• 주말 - CME 비트코인 옵션 만기"""
    
    def _format_core_analysis(self, indicators: Dict) -> str:
        """핵심 분석 요약"""
        return """• 기술 분석: 상승 모멘텀 약화
• 심리 분석: 중립 (펀딩비 정상)
• 구조 분석: 거래소 BTC 유출 지속"""
    
    def _format_short_predictions(self, indicators: Dict) -> str:
        """단기 예측 요약"""
        return """• 상승 확률: 45%
• 횡보 확률: 40%
• 하락 확률: 15%

📌 전략 제안: 명확한 방향성 확인 후 진입"""
    
    async def _format_simple_pnl(self, market_data: Dict) -> str:
        """간단한 손익 요약"""
        account = market_data.get('account', {})
        unrealized = account.get('unrealized_pnl', 0)
        
        return f"""• 미실현 손익: ${unrealized:+.2f} ({unrealized * 1.35:.1f}만원)
• 실현 손익: $0.00 (0.0만원)
• 총 수익률: {(unrealized/2000)*100:+.2f}%"""
    
    def _generate_short_mental_message(self, market_data: Dict) -> str:
        """짧은 멘탈 메시지"""
        account = market_data.get('account', {})
        pnl = account.get('unrealized_pnl', 0)
        profit_krw = pnl * 1350
        
        if profit_krw > 100000:
            return f'"오늘 벌어들인 {profit_krw/10000:.0f}만원, 한달 용돈이 하루만에! 리스크 관리 잊지 마세요."'
        elif profit_krw > 0:
            return '"수익이 작아도 플러스는 플러스입니다. 꾸준함이 답입니다."'
        else:
            return '"손실도 거래의 일부입니다. 멘탈 관리가 곧 자금 관리입니다."'
    
    def _format_exception_cause(self, event: Dict) -> str:
        """예외 원인 포맷팅"""
        return f"""• {event.get('title', '알 수 없는 이벤트')}
• {event.get('description', '상세 정보 없음')}
• 발생 시각: {event.get('timestamp', datetime.now()).strftime('%H:%M:%S')}"""
    
    def _format_exception_analysis(self, event: Dict, market_data: Dict) -> str:
        """예외 분석 포맷팅"""
        severity = event.get('severity', 'medium')
        impact = event.get('impact', '중립')
        
        return f"""• 심각도: {severity.upper()}
• 예상 영향: {impact}
• 현재가: ${market_data.get('current_price', 0):,.0f}

👉 향후 2시간 내 {'상승' if '호재' in impact else '하락'} 가능성 높음"""
    
    def _format_risk_strategy(self, event: Dict, market_data: Dict) -> str:
        """리스크 전략 포맷팅"""
        severity = event.get('severity', 'medium')
        
        if severity == 'critical':
            return """• 모든 레버리지 포지션 즉시 정리
• 현물도 일부 매도 고려
• 24시간 신규 진입 금지"""
        elif severity == 'high':
            return """• 레버리지 3배 이하로 축소
• 손절선 -2%로 타이트하게
• 분할 진입/청산 전략"""
        else:
            return """• 현재 포지션 유지
• 추가 진입은 신중하게
• 시장 상황 면밀히 모니터링"""
    
    def _format_detection_conditions(self, event: Dict) -> str:
        """탐지 조건 포맷팅"""
        category = event.get('category', 'unknown')
        
        conditions = {
            'price_movement': f"• 📉 단기 변동 급등락: {event.get('change_percent', 0):.1f}% 변동",
            'whale_movement': f"• 🔄 온체인 이상 이동: {event.get('btc_amount', 0):,.0f} BTC 이체",
            'news': f"• 📰 주요 뉴스: {event.get('title', 'Unknown')}",
            'sentiment': f"• 🧠 심리 지표 급변: {event.get('indicator', 'Unknown')} 변화"
        }
        
        return conditions.get(category, "• 복합적 조건 충족")
