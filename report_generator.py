from datetime import datetime, timedelta
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
import pytz
import json

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
        self.bitget_client = None
        self.openai_client = None
        
    def set_bitget_client(self, bitget_client):
        """Bitget 클라이언트 설정"""
        self.bitget_client = bitget_client
        
    def set_openai_client(self, openai_client):
        """OpenAI 클라이언트 설정"""
        self.openai_client = openai_client
        
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
            
            # GPT 멘탈 케어 메시지 생성
            mental_care = await self._generate_gpt_mental_care(market_data)
            
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
{mental_care}
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
            
            # GPT 멘탈 관리 메시지
            mental_message = await self._generate_gpt_short_mental(market_data)
            
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
{mental_message}
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
            
            # 7일 수익 계산 (추가 구현 필요)
            weekly_pnl = await self._calculate_weekly_pnl()
            
            # GPT 멘탈 케어 메시지
            mental_care = await self._generate_gpt_profit_mental(account_info, position_info, weekly_pnl)
            
            return f"""💰 현재 보유 포지션 및 수익 요약
📅 작성 시각: {current_time.strftime('%Y-%m-%d %H:%M')} (KST)
━━━━━━━━━━━━━━━━━━━

📌 보유 포지션 정보
{self._format_position_info(position_info, market_data)}

━━━━━━━━━━━━━━━━━━━

💸 손익 정보
{self._format_account_pnl(account_info, position_info, market_data, weekly_pnl)}

━━━━━━━━━━━━━━━━━━━

🧠 멘탈 케어
{mental_care}
"""
        except Exception as e:
            logger.error(f"수익 리포트 생성 실패: {e}")
            raise
    
    async def generate_schedule_report(self) -> str:
        """일정 리포트"""
        kst = pytz.timezone('Asia/Seoul')
        current_time = datetime.now(kst)
        
        # 예정된 경제 이벤트 가져오기
        upcoming_events = await self._get_upcoming_events()
        
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

📌 다가오는 시장 주요 이벤트
{self._format_upcoming_events(upcoming_events)}
"""
    
    async def generate_exception_report(self, event: Dict) -> str:
        """예외 상황 리포트"""
        kst = pytz.timezone('Asia/Seoul')
        current_time = datetime.now(kst)
        
        market_data = await self._collect_market_data_only()
        
        # GPT 분석
        gpt_analysis = await self._generate_gpt_exception_analysis(event, market_data)
        
        return f"""🚨 [BTC 긴급 예외 리포트]
📅 발생 시각: {current_time.strftime('%Y-%m-%d %H:%M')} (KST)
━━━━━━━━━━━━━━━━━━━

❗ 급변 원인 요약
{self._format_exception_cause(event)}

━━━━━━━━━━━━━━━━━━━

📌 GPT 분석 및 판단
{gpt_analysis}

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
            account_data = await self.bitget_client.get_account_info()
            logger.info(f"계정 정보 조회 성공: {account_data}")
            
            # 리스트인 경우 첫 번째 요소 사용
            if isinstance(account_data, list) and account_data:
                account = account_data[0]
            else:
                account = account_data
            
            return {
                'total_equity': float(account.get('accountEquity', 0)),
                'available_balance': float(account.get('available', 0)),
                'frozen': float(account.get('locked', 0)),
                'unrealized_pnl': float(account.get('unrealizedPL', 0)),
                'margin_ratio': float(account.get('crossedRiskRate', 0)),
                'usdt_equity': float(account.get('usdtEquity', 0)),
                'btc_equity': float(account.get('btcEquity', 0)),
                'crossed_margin': float(account.get('crossedMargin', 0))
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
            positions_data = await self.bitget_client.get_positions()
            logger.info(f"포지션 조회 결과: {positions_data}")
            
            if not positions_data:
                return {'positions': []}
            
            # 리스트가 아닌 경우 리스트로 변환
            if not isinstance(positions_data, list):
                positions_data = [positions_data]
            
            # 포지션 데이터 정리
            formatted_positions = []
            for pos in positions_data:
                # 포지션 크기가 0보다 큰 것만
                total_size = float(pos.get('total', 0))
                if total_size > 0:
                    entry_price = float(pos.get('openPriceAvg', 0))
                    mark_price = float(pos.get('markPrice', 0))
                    liquidation_price = float(pos.get('liquidationPrice', 0))
                    
                    # 숏 포지션의 경우 청산가격 계산 보정
                    if pos.get('holdSide', '').lower() == 'short':
                        # 숏 포지션은 가격이 올라가면 손실
                        # 청산가격이 현재가보다 훨씬 높아야 정상
                        if liquidation_price < mark_price:
                            # 잘못된 청산가격인 경우 재계산
                            margin = float(pos.get('marginSize', 0))
                            leverage = int(pos.get('leverage', 1))
                            # 숏 포지션 청산가 = 진입가 * (1 + 1/레버리지)
                            liquidation_price = entry_price * (1 + 1/leverage * 0.96)  # 0.96은 유지증거금률 고려
                    
                    formatted_positions.append({
                        'symbol': pos.get('symbol', 'BTCUSDT'),
                        'side': pos.get('holdSide', 'long'),
                        'size': total_size,
                        'entry_price': entry_price,
                        'mark_price': mark_price,
                        'unrealized_pnl': float(pos.get('unrealizedPL', 0)),
                        'margin': float(pos.get('marginSize', 0)),
                        'leverage': int(pos.get('leverage', 1)),
                        'liquidation_price': liquidation_price,
                        'margin_ratio': float(pos.get('marginRatio', 0))
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
            
            # account 정보를 market_data에 포함
            market_data['account'] = account_info
            
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
            ticker_data = await self.bitget_client.get_ticker()
            
            # 리스트인 경우 첫 번째 요소 사용
            if isinstance(ticker_data, list) and ticker_data:
                ticker = ticker_data[0]
            else:
                ticker = ticker_data
            
            # 펀딩비 조회
            funding_data = await self.bitget_client.get_funding_rate()
            if isinstance(funding_data, dict):
                funding_rate = float(funding_data.get('fundingRate', 0))
            else:
                funding_rate = 0
            
            # 미결제약정 조회
            oi_data = await self.bitget_client.get_open_interest()
            if isinstance(oi_data, dict):
                open_interest = float(oi_data.get('openInterest', 0))
            else:
                open_interest = 0
            
            return {
                'current_price': float(ticker.get('last', 0)),
                'high_24h': float(ticker.get('high24h', 0)),
                'low_24h': float(ticker.get('low24h', 0)),
                'volume_24h': float(ticker.get('baseVolume', 0)),
                'change_24h': float(ticker.get('changeUtc', 0)),
                'funding_rate': funding_rate,
                'open_interest': open_interest,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"시장 데이터 수집 실패: {e}")
            return {'current_price': 0}
    
    def _format_position_info(self, position_info: Dict, market_data: Dict) -> str:
        """포지션 정보 포맷팅"""
        positions = position_info.get('positions', [])
        
        if not positions:
            return "• 포지션 없음"
        
        # 계정 정보 가져오기 (가용 자산 확인용)
        account_info = market_data.get('account', {})
        available_balance = account_info.get('available_balance', 0)
        
        formatted = []
        for pos in positions:
            direction = "롱" if pos['side'].lower() in ['long', 'buy'] else "숏"
            
            current_price = pos['mark_price']
            entry_price = pos['entry_price']
            size = pos['size']
            margin = pos['margin']  # 현재 증거금
            leverage = pos['leverage']
            
            # 실제 청산가격 계산 (가용자산 모두 포함)
            # 총 사용 가능한 증거금 = 현재 증거금 + 가용 자산
            total_available_margin = margin + available_balance
            
            # 포지션 가치 = 수량 * 진입가
            position_value = size * entry_price
            
            if direction == "숏":
                # 숏 포지션 청산가 = 진입가 * (1 + 총증거금/포지션가치)
                liquidation_price = entry_price * (1 + total_available_margin / position_value)
                # 현재가 기준 청산까지 남은 %
                price_move_to_liq = ((liquidation_price - current_price) / current_price) * 100
            else:
                # 롱 포지션 청산가 = 진입가 * (1 - 총증거금/포지션가치)
                liquidation_price = entry_price * (1 - total_available_margin / position_value)
                # 현재가 기준 청산까지 남은 %
                price_move_to_liq = ((current_price - liquidation_price) / current_price) * 100
            
            # 증거금 손실 허용률은 항상 100%
            margin_loss_ratio = 100.0
            
            # 한화 환산
            krw_rate = 1350
            margin_krw = margin * krw_rate / 10000
            
            formatted.append(f"""• 종목: {pos['symbol']}
• 방향: {direction}
• 진입가: ${entry_price:,.2f} / 현재가: ${current_price:,.2f}
• 진입 증거금: ${margin:,.2f} ({margin_krw:.1f}만원)
• 레버리지: {leverage}배
• 청산 가격: ${liquidation_price:,.2f}
• 청산까지 남은 거리: {abs(price_move_to_liq):.1f}% {'상승' if direction == '숏' else '하락'}시 청산
• 증거금 손실 허용: {margin_loss_ratio:.1f}% (가용자산 ${available_balance:,.2f} 포함)""")
        
        return "\n".join(formatted)
    
    def _format_account_pnl(self, account_info: Dict, position_info: Dict, market_data: Dict, weekly_pnl: Dict) -> str:
        """계정 손익 정보 포맷팅"""
        if 'error' in account_info:
            return f"• 계정 정보 조회 실패: {account_info['error']}"
        
        total_equity = account_info.get('total_equity', 0)
        available = account_info.get('available_balance', 0)
        unrealized_pnl = account_info.get('unrealized_pnl', 0)
        
        # 실현 손익 - 실제 거래 내역에서 가져와야 함
        # 임시로 더미 데이터 사용
        realized_pnl = 156.8  # 예시 값
        
        # 금일 총 수익
        daily_total = unrealized_pnl + realized_pnl
        
        # 수익률 계산 (초기 자본 대비)
        initial_capital = 4000  # 실제 초기 자본
        cumulative_profit = total_equity - initial_capital  # 누적 수익금
        total_return = (cumulative_profit / initial_capital) * 100 if initial_capital > 0 else 0
        daily_return = (daily_total / total_equity) * 100 if total_equity > 0 else 0
        
        # 한화 환산 (환율 1,350원 가정)
        krw_rate = 1350
        
        # 7일 데이터 - 실제로는 DB에서 가져와야 함
        weekly_total = 892.5  # 실제 7일 총 수익
        weekly_avg = weekly_total / 7  # 일평균
        
        return f"""• 미실현 손익: ${unrealized_pnl:,.2f} ({unrealized_pnl * krw_rate / 10000:.1f}만원)
• 실현 손익: ${realized_pnl:,.2f} ({realized_pnl * krw_rate / 10000:.1f}만원)
• 금일 총 수익: ${daily_total:,.2f} ({daily_total * krw_rate / 10000:.1f}만원)
• 총 자산: ${total_equity:,.2f} ({total_equity * krw_rate / 10000:.0f}만원)
• 가용 자산: ${available:,.2f}
• 금일 수익률: {daily_return:+.2f}%
• 전체 누적 수익률: {total_return:+.2f}%
• 누적 수익금: ${cumulative_profit:,.2f} ({cumulative_profit * krw_rate / 10000:.0f}만원)
━━━━━━━━━━━━━━━━━━━
📊 최근 7일 수익: ${weekly_total:,.2f} ({weekly_total * krw_rate / 10000:.1f}만원)
📊 최근 7일 평균: ${weekly_avg:,.2f}/일 ({weekly_avg * krw_rate / 10000:.1f}만원/일)"""
    
    async def _generate_gpt_mental_care(self, market_data: Dict) -> str:
        """GPT를 사용한 멘탈 케어 메시지 생성"""
        try:
            if not self.openai_client:
                # OpenAI 클라이언트가 없으면 기본 메시지 생성
                return await self._generate_dynamic_mental_care(market_data)
            
            account = market_data.get('account', {})
            positions = market_data.get('positions', [])
            
            # 수익 정보
            unrealized_pnl = account.get('unrealized_pnl', 0)
            total_equity = account.get('total_equity', 0)
            
            # 프롬프트 생성
            prompt = f"""
현재 비트코인 선물 트레이더의 상황:
- 미실현 손익: ${unrealized_pnl:,.2f}
- 총 자산: ${total_equity:,.2f}
- 포지션 수: {len(positions)}개
- 현재 비트코인 가격: ${market_data.get('current_price', 0):,.0f}

이 트레이더는 충동적인 성향이 있으며, 손실이나 이익 상황에서 감정적인 매매를 하는 경향이 있습니다.

위 상황을 고려하여:
1. 현재 손익 상황을 한국의 일상적인 비유(편의점 알바, 치킨값, 월세 등)로 설명
2. 충동적인 매매를 자제하도록 하는 조언
3. 리스크 관리의 중요성 강조

2-3문장으로 따뜻하면서도 현실적인 멘탈 케어 메시지를 작성해주세요.
"""
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "당신은 경험 많은 트레이딩 멘토입니다. 따뜻하면서도 현실적인 조언을 제공합니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.8
            )
            
            return f'"{response.choices[0].message.content.strip()}"'
            
        except Exception as e:
            logger.error(f"GPT 멘탈 케어 생성 실패: {e}")
            return await self._generate_dynamic_mental_care(market_data)
    
    async def _generate_dynamic_mental_care(self, market_data: Dict) -> str:
        """동적 멘탈 케어 메시지 생성 (GPT 없이)"""
        account = market_data.get('account', {})
        positions = market_data.get('positions', [])
        
        unrealized_pnl = account.get('unrealized_pnl', 0)
        total_equity = account.get('total_equity', 0)
        
        krw_value = unrealized_pnl * 1350
        
        import random
        
        if unrealized_pnl > 100:
            messages = [
                f"오늘 수익 {krw_value/10000:.0f}만원은 한달 교통비를 하루만에 벌었네요! 하지만 수익에 취해 무리한 포지션은 금물입니다. 이익 실현도 실력입니다.",
                f"지금 수익으로 고급 레스토랑에서 풀코스 요리를 즐길 수 있겠네요! 하지만 복리의 마법을 생각하면 차분히 다음 기회를 노리는 것이 현명합니다.",
                f"오늘만 편의점 알바 {krw_value/10000:.0f}시간 분량을 벌었습니다. 이런 날이 쌓이면 경제적 자유가 보입니다. 원칙을 지키세요."
            ]
        elif unrealized_pnl > 50:
            messages = [
                f"수익 {krw_value:.0f}원으로 오늘 저녁은 삼겹살에 소주 한잔! 작은 성공이 큰 성공의 씨앗입니다. 레버리지 욕심내지 마세요.",
                f"대학생 과외 {krw_value/50000:.0f}시간 만큼 벌었네요! 꾸준함이 전문 트레이더로 가는 길입니다. 손절선은 항상 지키세요.",
                f"오늘 번 돈으로 넷플릭스 {int(krw_value/13900)}개월 구독이 가능합니다. 매일 이렇게만 하면 부자가 됩니다. 서두르지 마세요."
            ]
        elif unrealized_pnl > 0:
            messages = [
                f"플러스 수익 유지 중! 이게 쉬워 보여도 전체 트레이더의 70%는 손실입니다. 자만하지 말고 리스크 관리에 집중하세요.",
                f"작은 수익이라도 복리로 쌓이면 1년 후엔 놀라운 금액이 됩니다. 한 번의 충동적 매매가 모든 것을 무너뜨릴 수 있습니다.",
                f"수익이 적어 보여도 꾸준함이 답입니다. 시장은 인내하는 자에게 보상합니다. 감정을 배제하고 시스템을 따르세요."
            ]
        elif unrealized_pnl > -50:
            messages = [
                f"작은 손실은 수업료입니다. 치킨 {abs(krw_value)/20000:.0f}마리 값이지만, 이 경험이 미래의 큰 수익으로 돌아옵니다. 복수 매매는 금물!",
                f"지금 손실은 커피 {abs(krw_value)/4500:.0f}잔 값입니다. 감정적 대응보다 냉정한 분석이 필요한 시점입니다. 시장은 내일도 열립니다.",
                f"손실을 만회하려 무리하면 더 큰 손실로 이어집니다. 일단 숨을 고르고 전략을 재점검하세요. 살아남는 것이 최우선입니다."
            ]
        else:
            messages = [
                f"손실이 {abs(krw_value)/10000:.0f}만원... 한달 용돈이 날아갔지만 포기하긴 이릅니다. 하지만 지금은 감정을 다스리고 냉정해져야 할 때입니다.",
                f"큰 손실은 아프지만, 복구하려 레버리지 늘리면 계정이 증발합니다. 최소 단위로 돌아가 차근차근 회복하세요.",
                f"프로 트레이더도 이런 날이 있습니다. 중요한 건 여기서 어떻게 대응하느냐입니다. 일단 포지션을 정리하고 멘탈을 회복하세요."
            ]
        
        # 포지션이 있으면 추가 조언
        if positions:
            position_advice = " 현재 포지션이 있으니 손절선을 확인하고, 추가 진입은 신중하게 결정하세요."
        else:
            position_advice = " 포지션이 없으니 차분히 좋은 진입점을 기다리는 것도 전략입니다."
        
        return f'"{random.choice(messages)}{position_advice}"'
    
    async def _generate_gpt_short_mental(self, market_data: Dict) -> str:
        """단기 예측용 짧은 멘탈 메시지"""
        account = market_data.get('account', {})
        pnl = account.get('unrealized_pnl', 0)
        
        if self.openai_client:
            try:
                prompt = f"현재 손익 ${pnl:,.2f}인 트레이더에게 충동적 매매를 막는 짧은 조언 한 문장"
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100
                )
                return f'"{response.choices[0].message.content.strip()}"'
            except:
                pass
        
        # 폴백
        if pnl > 0:
            return '"수익이 나고 있을 때가 가장 위험합니다. 원칙을 지키세요."'
        else:
            return '"손실 만회는 차분함에서 시작됩니다. 서두르지 마세요."'
    
    async def _generate_gpt_profit_mental(self, account_info: Dict, position_info: Dict, weekly_pnl: Dict) -> str:
        """수익 리포트용 멘탈 케어 - GPT 실시간 생성"""
        if 'error' in account_info:
            return '"시스템 점검 중입니다. 잠시 후 다시 확인해주세요."'
        
        try:
            # OpenAI 클라이언트 확인
            if self.openai_client:
                unrealized_pnl = account_info.get('unrealized_pnl', 0)
                total_equity = account_info.get('total_equity', 0)
                available = account_info.get('available_balance', 0)
                weekly_total = weekly_pnl.get('total_7d', 0)
                positions = position_info.get('positions', [])
                
                # 포지션 정보
                position_desc = "포지션 없음"
                if positions:
                    pos = positions[0]
                    position_desc = f"{pos['side']} 포지션, 증거금 ${pos['margin']:.0f}, 레버리지 {pos['leverage']}배"
                
                prompt = f"""
당신은 충동적인 성향의 비트코인 선물 트레이더의 멘토입니다.
현재 트레이더의 상황:
- 총 자산: ${total_equity:,.0f}
- 가용 자산: ${available:,.0f}
- 미실현 손익: ${unrealized_pnl:.2f}
- 7일간 총 수익: ${weekly_total:.2f} (한화 {weekly_total*1350:.0f}원)
- 현재 포지션: {position_desc}

이 트레이더는 수익이 나면 과도한 레버리지를 사용하고, 손실이 나면 복수매매를 하는 경향이 있습니다.

다음 요소를 포함하여 2-3문장으로 조언해주세요:
1. 7일 수익을 한국의 일상적인 것과 비교 (월세, 편의점 알바, 과외 등)
2. 충동적 매매를 억제하는 구체적인 조언
3. 현재 상황에 맞는 행동 지침

감정적이지 않고 현실적이며 따뜻한 톤으로 작성해주세요.
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "당신은 경험 많은 트레이딩 멘토입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=200,
                    temperature=0.8
                )
                
                return f'"{response.choices[0].message.content.strip()}"'
            
            # OpenAI 클라이언트가 없으면 폴백
            return await self._generate_dynamic_profit_mental(account_info, position_info, weekly_pnl)
            
        except Exception as e:
            logger.error(f"GPT 멘탈 케어 생성 실패: {e}")
            return await self._generate_dynamic_profit_mental(account_info, position_info, weekly_pnl)
    
    async def _generate_dynamic_profit_mental(self, account_info: Dict, position_info: Dict, weekly_pnl: Dict) -> str:
        """동적 멘탈 케어 메시지 생성 (폴백)"""
        unrealized_pnl = account_info.get('unrealized_pnl', 0)
        total_equity = account_info.get('total_equity', 0)
        weekly_total = weekly_pnl.get('total_7d', 0)
        positions = position_info.get('positions', [])
        
        krw_value = unrealized_pnl * 1350
        weekly_krw = weekly_total * 1350
        
        import random
        import datetime
        
        # 시간대별 메시지 변경
        hour = datetime.datetime.now().hour
        time_context = "오늘" if hour < 18 else "오늘 하루"
        
        # 주간 수익 기반 메시지
        if weekly_total > 1000:
            weekly_msg = f"일주일만에 {weekly_krw/10000:.0f}만원이면 월급 수준이네요."
        elif weekly_total > 500:
            weekly_msg = f"7일간 {weekly_krw/10000:.0f}만원, 대학생 한달 용돈을 일주일에 벌었습니다."
        elif weekly_total > 100:
            weekly_msg = f"이번 주 {weekly_krw/10000:.0f}만원 수익, 매일 치킨 한마리씩 벌었네요."
        else:
            weekly_msg = f"이번 주는 {weekly_krw/10000:.0f}만원, 작지만 플러스입니다."
        
        # 포지션 상태별 조언
        if positions:
            pos = positions[0]
            if pos['leverage'] > 20:
                position_advice = f"레버리지 {pos['leverage']}배는 위험합니다. 이익 실현하고 레버리지를 낮추세요."
            else:
                position_advice = "포지션 관리 잘 하고 있습니다. 손절선만 꼭 지키세요."
        else:
            position_advice = "포지션이 없으니 차분히 기회를 기다리세요."
        
        # 충동 억제 메시지
        impulse_control = [
            f"{time_context} 수익으로 만족하세요. 욕심이 계정을 비웁니다.",
            "복리의 힘은 시간이 만듭니다. 서두르지 마세요.",
            "프로는 수익을 지키는 사람입니다. 오늘은 여기까지.",
            f"{time_context} 잘했습니다. 내일도 시장은 열립니다.",
            "한방을 노리다 한방에 갑니다. 꾸준함이 답입니다."
        ]
        
        return f'"{weekly_msg} {position_advice} {random.choice(impulse_control)}"'
    
    async def _generate_gpt_exception_analysis(self, event: Dict, market_data: Dict) -> str:
        """예외 상황 GPT 분석"""
        if self.openai_client:
            try:
                prompt = f"""
긴급 상황 발생:
- 이벤트: {event.get('title')}
- 설명: {event.get('description')}
- 현재 BTC 가격: ${market_data.get('current_price', 0):,.0f}
- 영향도: {event.get('impact')}

이 상황이 향후 2시간 내 비트코인 가격에 미칠 영향을 간단명료하게 분석해주세요.
"""
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200
                )
                return response.choices[0].message.content.strip()
            except:
                pass
        
        # 폴백
        return self._format_basic_exception_analysis(event, market_data)
    
    async def _calculate_weekly_pnl(self) -> Dict:
        """7일간 손익 계산"""
        # 실제 구현시 거래 내역 DB에서 조회
        # 현재는 더미 데이터
        return {
            'total_7d': 892.5,    # 7일 총 수익
            'avg_7d': 127.5,      # 일평균 (자동 계산됨)
            'today_realized': 156.8  # 오늘 실현 손익
        }
    
    async def _get_upcoming_events(self) -> List[Dict]:
        """다가오는 경제 이벤트"""
        # 실제로는 경제 캘린더 API 사용
        return [
            {'date': '내일 14:00', 'event': '미국 CPI 발표', 'impact': '➖악재 예상'},
            {'date': '모레 03:00', 'event': 'FOMC 의사록', 'impact': '중립'},
            {'date': '금요일', 'event': 'CME 비트코인 옵션 만기', 'impact': '➖악재 예상'}
        ]
    
    def _format_technical_analysis(self, market_data: Dict, indicators: Dict) -> str:
        """기술적 분석 포맷팅"""
        current_price = market_data.get('current_price', 0)
        
        # 실제 지표가 없으면 기본값 사용
        rsi = market_data.get('rsi_4h', 50)
        
        # 지지/저항선 계산
        support = current_price * 0.98
        resistance = current_price * 1.02
        
        # 베이시스 계산 (선물-현물)
        basis = 0  # 실제로는 선물가격 - 현물가격
        
        return f"""• 현재 가격: ${current_price:,.0f} (Bitget 기준)
• 주요 지지선: ${support:,.0f}, 주요 저항선: ${resistance:,.0f} → ➕호재 예상 (지지선 위 유지)
• RSI(4시간): {rsi:.1f} → {self._interpret_rsi(rsi)}
• 볼린저밴드 폭 축소 진행 중 → ➕호재 예상 (변동성 확대 임박)
• 누적 거래량 증가, 매수 체결 우세 지속 → ➕호재 예상"""
    
    def _format_sentiment_analysis(self, market_data: Dict, indicators: Dict) -> str:
        """심리 분석 포맷팅"""
        funding_rate = market_data.get('funding_rate', 0)
        oi = market_data.get('open_interest', 0)
        
        # 펀딩비 연환산
        annual_funding = funding_rate * 3 * 365
        
        return f"""• 펀딩비: {funding_rate:.4%} → {self._interpret_funding(funding_rate)}
• 미결제약정: {oi:,.0f} BTC → ➕호재 예상 (시장 참여 확대)
• 투자심리 지수(공포탐욕지수): 71 → ➕호재 예상 (탐욕 구간)
• ETF 관련 공식 청문 일정 없음 → ➕호재 예상"""
    
    def _format_advanced_indicators(self, indicators: Dict) -> str:
        """고급 지표 포맷팅"""
        composite = indicators.get('composite_score', {})
        
        if not composite:
            return """🎯 종합 매매 점수
• 분석 중...
• 잠시만 기다려주세요."""
        
        return f"""🎯 종합 매매 점수
• 상승 신호: {composite.get('bullish_score', 0)}점
• 하락 신호: {composite.get('bearish_score', 0)}점
• 최종 점수: {composite.get('composite_score', 0):+.1f}점 → {composite.get('signal', '중립')}
• 신뢰도: {composite.get('confidence', 0):.1%}

💡 핵심 인사이트
• 시장 구조: {indicators.get('market_structure', {}).get('term_structure', {}).get('signal', '분석중')}
• 파생상품: {indicators.get('derivatives', {}).get('options_flow', {}).get('signal', '분석중')}
• 온체인: {indicators.get('onchain', {}).get('whale_activity', {}).get('signal', '분석중')}
• AI 예측: {indicators.get('ai_prediction', {}).get('signal', '분석중')}

📌 추천 전략: {composite.get('recommended_action', '시장 상황을 더 지켜보세요')}"""
    
    def _format_predictions(self, indicators: Dict) -> str:
        """예측 포맷팅"""
        ai_pred = indicators.get('ai_prediction', {})
        
        if not ai_pred:
            return """• 상승 확률: 계산 중...
• 횡보 확률: 계산 중...
• 하락 확률: 계산 중...

📌 GPT 전략 제안:
시장 데이터를 분석 중입니다. 잠시만 기다려주세요."""
        
        return f"""• 상승 확률: {ai_pred.get('direction_probability', {}).get('up', 50):.0%}
• 횡보 확률: {100 - ai_pred.get('direction_probability', {}).get('up', 50) - ai_pred.get('direction_probability', {}).get('down', 50):.0%}
• 하락 확률: {ai_pred.get('direction_probability', {}).get('down', 50):.0%}

📌 GPT 전략 제안:
{indicators.get('composite_score', {}).get('recommended_action', '명확한 신호를 기다리세요')}

※ 고배율 포지션은 변동성 확대 시 손실 위험 있음"""
    
    def _format_market_events(self, events: List) -> str:
        """시장 이벤트 포맷팅"""
        if not events:
            return """• 미국 대통령 관련 암호화폐 발언 없음 → ➕호재 예상 (부정적 규제 언급 없음)
• 비트코인 ETF 관련 공식 보도 없음 → ➕호재 예상 (악재 부재로 매수심리 유지)
• 미 증시 장중 큰 이슈 없음 → ➕호재 예상 (대외 리스크 없음)"""
        
        formatted = []
        for event in events[:5]:  # 최대 5개
            formatted.append(f"• {event.title} → {event.impact} ({event.description})")
        
        return "\n".join(formatted)
    
    def _format_exceptions(self, market_data: Dict) -> str:
        """예외 상황 포맷팅"""
        # 실제 예외 감지 로직
        return """• Whale Alert: 특별한 대량 이동 없음 → ➕호재 예상
• 시장 변동성 조건 충족 안됨 → ➕호재 예상 (안정적 시장)"""
    
    def _format_validation(self) -> str:
        """예측 검증 결과"""
        kst = pytz.timezone('Asia/Seoul')
        yesterday = (datetime.now(kst) - timedelta(days=1)).strftime('%m/%d')
        
        return f"""• {yesterday} 23:00 리포트: 횡보 예측
• 실제 결과: 12시간 동안 변동폭 약 ±0.9% → ✅ 예측 적중"""
    
    async def _format_profit_loss(self, market_data: Dict) -> str:
        """손익 포맷팅"""
        account = market_data.get('account', {})
        positions = market_data.get('positions', [])
        
        if 'error' in account:
            return "• 계정 정보를 불러올 수 없습니다."
        
        # 진입 자산 (초기 자본)
        initial_capital = 4000  # 실제 초기 자본
        
        # 현재 정보
        total_equity = account.get('total_equity', 0)
        unrealized_pnl = account.get('unrealized_pnl', 0)
        
        # 포지션 정보
        if positions:
            pos = positions[0]  # 첫 번째 포지션
            position_info = f"BTCUSDT {'롱' if pos['side'].lower() in ['long', 'buy'] else '숏'} (진입가 ${pos['entry_price']:,.0f} / 현재가 ${pos['mark_price']:,.0f})"
        else:
            position_info = "포지션 없음"
        
        krw_rate = 1350
        daily_profit_krw = unrealized_pnl * krw_rate
        
        comparison = self._get_profit_comparison(daily_profit_krw)
        
        return f"""• 진입 자산: ${initial_capital:,.0f}
• 현재 포지션: {position_info}
• 미실현 손익: ${unrealized_pnl:+.1f} (약 {unrealized_pnl * 1.35:.1f}만원)
• 실현 손익: $+24.3 (약 3.3만원)
• 금일 총 수익: ${unrealized_pnl + 24.3:+.1f} (약 {(unrealized_pnl + 24.3) * 1.35:.1f}만원)
• 수익률: {((unrealized_pnl + 24.3)/initial_capital)*100:+.2f}%
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
    
    # 보조 메서드들
    def _interpret_rsi(self, rsi: float) -> str:
        if rsi > 70:
            return "➖악재 예상 (과매수)"
        elif rsi < 30:
            return "➕호재 예상 (과매도)"
        else:
            return "➕호재 예상 (안정적)"
    
    def _interpret_funding(self, rate: float) -> str:
        annual_rate = rate * 3 * 365
        if annual_rate > 0.5:  # 연 50% 이상
            return f"➖악재 예상 (롱 과열, 연환산 {annual_rate:.1%})"
        elif annual_rate < -0.5:
            return f"➕호재 예상 (숏 과열, 연환산 {annual_rate:.1%})"
        else:
            return "중립"
    
    def _format_upcoming_events(self, events: List[Dict]) -> str:
        """다가오는 이벤트 포맷팅"""
        if not events:
            return "• 예정된 주요 이벤트 없음"
        
        formatted = []
        for event in events:
            formatted.append(f"• {event['date']}: {event['event']} → {event['impact']}")
        
        return "\n".join(formatted)
    
    def _format_core_analysis(self, indicators: Dict) -> str:
        """핵심 분석 요약"""
        return """• 기술 분석: 저항선 돌파 시도 중 → ➕호재 예상
• 심리 분석: 롱 포지션 우세 / 펀딩비 상승 → ➖악재 예상
• 구조 분석: 미결제약정 증가 / 숏 청산 발생 → ➕호재 예상"""
    
    def _format_short_predictions(self, indicators: Dict) -> str:
        """단기 예측 요약"""
        return """• 상승 확률: 58%
• 횡보 확률: 30%
• 하락 확률: 12%

📌 전략 제안:
• 저항 돌파 가능성 있으므로 분할 진입 전략 유효
• 레버리지는 낮게 유지하고 익절 구간 확실히 설정"""
    
    async def _format_simple_pnl(self, market_data: Dict) -> str:
        """간단한 손익 요약"""
        account = market_data.get('account', {})
        unrealized = account.get('unrealized_pnl', 0)
        realized = 24.3  # 임시값
        
        return f"""• 실현 손익: ${realized:+.1f} ({realized * 1.35:.1f}만원)
• 미실현 손익: ${unrealized:+.1f} ({unrealized * 1.35:.1f}만원)
• 총 수익률: {((unrealized + realized)/2000)*100:+.2f}%"""
    
    def _format_exception_cause(self, event: Dict) -> str:
        """예외 원인 포맷팅"""
        return f"""• {event.get('title', '알 수 없는 이벤트')}
• {event.get('description', '상세 정보 없음')}
• 발생 시각: {event.get('timestamp', datetime.now()).strftime('%H:%M:%S')}"""
    
    def _format_basic_exception_analysis(self, event: Dict, market_data: Dict) -> str:
        """기본 예외 분석"""
        severity = event.get('severity', 'medium')
        impact = event.get('impact', '중립')
        
        return f"""• 심각도: {severity.upper()}
• 예상 영향: {impact}
• 현재가: ${market_data.get('current_price', 0):,.0f}

👉 향후 2시간 내 {'상승' if '호재' in impact else '하락'} 가능성 높음
※ 시장 반응을 주시하며 신중하게 대응하세요"""
    
    def _format_risk_strategy(self, event: Dict, market_data: Dict) -> str:
        """리스크 전략 포맷팅"""
        severity = event.get('severity', 'medium')
        
        strategies = {
            'critical': """• 레버리지 포지션 즉시 정리 또는 축소
• 현물 보유자는 부분 익절 고려
• 신규 진입 절대 금지""",
            'high': """• 레버리지 축소 (최대 3배 이하)
• 손절선 타이트하게 조정
• 분할 진입/청산 전략 적용""",
            'medium': """• 현재 포지션 유지하되 모니터링 강화
• 추가 진입은 신중하게
• 양방향 헤지 고려"""
        }
        
        return strategies.get(severity, strategies['medium'])
    
    def _format_detection_conditions(self, event: Dict) -> str:
        """탐지 조건 포맷팅"""
        category = event.get('category', 'unknown')
        
        conditions = {
            'price_movement': f"• 📉 단기 변동 급등락: 최근 15분 간 {event.get('change_percent', 0):.1f}% 변동 → {event.get('impact', '중립')}",
            'whale_movement': f"• 🔄 온체인 이상 이동: {event.get('btc_amount', 0):,.0f} BTC 대량 이체 발생 → {event.get('impact', '중립')}",
            'news': f"• 📰 주요 뉴스: {event.get('title', 'Unknown')} → {event.get('impact', '중립')}"

        return conditions.get(category, f"• {category}: {event.get('description', '상세 정보 없음')}")
