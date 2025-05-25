# analysis_engine.py - GPT 분석 엔진
import logging
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class AnalysisEngine:
    def __init__(self, config, bitget_client):
        self.config = config
        self.bitget_client = bitget_client
        self.client = AsyncOpenAI(api_key=config.openai_api_key)
        self.prediction_history = []  # 예측 정확도 추적용
        
    async def _get_market_data(self) -> Dict:
        """시장 데이터 수집"""
        try:
            # 현재가 정보
            ticker = await self.bitget_client.get_ticker()
            
            # K라인 데이터 (4시간)
            klines_4h = await self.bitget_client.get_kline(granularity='4H', limit=50)
            
            # 포지션 정보
            positions = await self.bitget_client.get_positions()
            
            # 계정 정보
            account = await self.bitget_client.get_account_info()
            
            # 펀딩비
            funding = await self.bitget_client.get_funding_rate()
            
            # 미결제약정
            open_interest = await self.bitget_client.get_open_interest()
            
            return {
                'ticker': ticker,
                'klines_4h': klines_4h,
                'positions': positions,
                'account': account,
                'funding': funding,
                'open_interest': open_interest,
                'timestamp': datetime.now(pytz.timezone('Asia/Seoul')).isoformat()
            }
        except Exception as e:
            logger.error(f"시장 데이터 수집 실패: {e}")
            raise
    
    def _calculate_technical_indicators(self, klines: List[Dict]) -> Dict:
        """기술적 지표 계산"""
        if not klines or len(klines) < 14:
            return {}
        
        try:
            # 가격 데이터 추출
            closes = [float(k[4]) for k in klines]  # 종가
            highs = [float(k[2]) for k in klines]   # 고가
            lows = [float(k[3]) for k in klines]    # 저가
            
            # RSI 계산 (14일)
            rsi = self._calculate_rsi(closes, 14)
            
            # 볼린저 밴드 계산
            bb = self._calculate_bollinger_bands(closes, 20)
            
            # 이동평균
            ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
            ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
            
            return {
                'rsi': rsi,
                'bollinger_bands': bb,
                'ma20': ma20,
                'ma50': ma50,
                'current_price': closes[-1],
                'price_change_24h': ((closes[-1] - closes[-6]) / closes[-6] * 100) if len(closes) >= 6 else 0
            }
        except Exception as e:
            logger.error(f"기술적 지표 계산 실패: {e}")
            return {}
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """RSI 계산"""
        if len(prices) < period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if len(gains) < period:
            return None
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20) -> Dict:
        """볼린저 밴드 계산"""
        if len(prices) < period:
            return {}
        
        recent_prices = prices[-period:]
        sma = sum(recent_prices) / period
        
        variance = sum([(price - sma) ** 2 for price in recent_prices]) / period
        std_dev = variance ** 0.5
        
        upper_band = sma + (2 * std_dev)
        lower_band = sma - (2 * std_dev)
        
        return {
            'upper': round(upper_band, 2),
            'middle': round(sma, 2),
            'lower': round(lower_band, 2)
        }
    
    def _generate_mental_comment(self, profit_info: Dict) -> str:
        """멘탈 케어 코멘트 생성"""
        try:
            total_profit_usd = profit_info.get('total_profit_usd', 0)
            profit_rate = profit_info.get('profit_rate', 0)
            
            # 수익 상황별 코멘트
            if profit_rate >= 10:
                comments = [
                    f"🎉 오늘 수익은 주말 여행 항공권에 해당합니다! {total_profit_usd:.1f}달러면 꽤 괜찮은 여행이 가능해요.",
                    f"💎 대단한 성과입니다! 이 정도 수익이면 맛있는 저녁 한 달치는 충분해요.",
                    f"🚀 로켓 같은 수익률이네요! 하지만 내일은 또 다른 도전이 기다립니다."
                ]
            elif profit_rate >= 1:
                comments = [
                    f"💰 수익은 습관입니다. 오늘 한 걸음이 내일 계단이 됩니다.",
                    f"📈 꾸준함이 승리의 열쇠입니다. 오늘도 목표에 한 발짝 더 가까워졌어요.",
                    f"☕ 오늘 수익으로 좋은 원두 한 포대는 살 수 있겠네요!"
                ]
            elif -1 <= profit_rate <= 1:
                comments = [
                    f"⏳ 조용한 날도 내일의 기회를 위해 꼭 필요합니다.",
                    f"🧘‍♂️ 횡보는 폭풍 전의 고요함일 수 있어요. 인내심을 가져봐요.",
                    f"📊 시장이 쉬어가는 날에는 우리도 쉬어가며 다음 기회를 준비해요."
                ]
            elif -5 <= profit_rate < -1:
                comments = [
                    f"📉 작은 손실은 기회비용입니다. 다시 시작하면 됩니다.",
                    f"🌱 손실도 성장의 밑거름이 됩니다. 경험치가 쌓이고 있어요.",
                    f"🔄 시장은 항상 변합니다. 오늘의 빨간불은 내일의 파란불을 위한 준비시간이에요."
                ]
            else:
                comments = [
                    f"🛑 손실이 크더라도 패닉은 금물입니다. 시스템을 믿으세요.",
                    f"💪 어려운 시기일수록 기본을 지키는 것이 중요합니다.",
                    f"🎯 지금은 휴식기입니다. 무리하지 말고 다음 기회를 기다려봐요."
                ]
            
            # 수익을 시간당 임금으로 환산
            krw_profit = abs(total_profit_usd) * self.config.usd_to_krw
            if krw_profit >= 100000:
                time_equivalent = "편의점 알바 약 8시간"
            elif krw_profit >= 50000:
                time_equivalent = "편의점 알바 약 4시간"
            elif krw_profit >= 20000:
                time_equivalent = "카페 알바 약 2시간"
            else:
                time_equivalent = "커피 한 잔"
            
            comment = random.choice(comments)
            comment += f"\n👟 오늘 {'수익' if total_profit_usd >= 0 else '손실'}은 {time_equivalent} 분량입니다."
            
            return comment
            
        except Exception as e:
            logger.error(f"멘탈 코멘트 생성 실패: {e}")
            return "💪 오늘도 고생하셨습니다. 내일은 더 좋은 날이 될 거예요!"
    
    async def _get_gpt_analysis(self, market_data: Dict, analysis_type: str = "full") -> str:
        """GPT 분석 요청"""
        try:
            # 기술적 지표 계산
            tech_indicators = self._calculate_technical_indicators(market_data.get('klines_4h', []))
            
            # 프롬프트 구성
            system_prompt = f"""
당신은 비트코인 선물 거래 전문 분석가입니다. 
주어진 시장 데이터를 바탕으로 {analysis_type} 분석을 수행하고, 
한국어로 간결하고 실용적인 분석을 제공해주세요.

분석 시 고려사항:
1. 기술적 분석: RSI, 볼린저밴드, 이동평균, 지지/저항선
2. 심리적 분석: 펀딩비, 미결제약정
3. 시장 동향 분석
4. 리스크 관리 조언

현재 시각: {datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M')} (한국시간)
"""
            
            user_prompt = f"""
시장 데이터 요약:
- 현재가: {market_data.get('ticker', {}).get('lastPr', 'N/A')}
- 24시간 변동: {market_data.get('ticker', {}).get('change24h', 'N/A')}%
- 펀딩비: {market_data.get('funding', {}).get('fundingRate', 'N/A')}
- RSI: {tech_indicators.get('rsi', 'N/A')}
- 볼린저밴드: {tech_indicators.get('bollinger_bands', {})}

분석 유형: {analysis_type}

다음 항목들을 포함하여 분석해주세요:
1. 현재 시장 상황 요약
2. 기술적 지표 해석  
3. 향후 12시간 방향성 예측 (상승/횡보/하락 확률)
4. 거래 전략 제안
5. 주의사항

간결하고 실용적으로 작성해주세요.
"""
            
            response = await self.client.chat.completions.create(
                model=self.config.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"GPT 분석 실패: {e}")
            return f"📊 기술적 분석\n- 현재가: {market_data.get('ticker', {}).get('lastPr', 'N/A')}\n- 시장 상황: 데이터 수집 중\n\n🔮 향후 12시간 예측\n- 분석 시스템 점검 중입니다."
    
    async def generate_full_report(self) -> str:
        """정규 리포트 생성"""
        try:
            market_data = await self._get_market_data()
            
            # GPT 분석
            gpt_analysis = await self._get_gpt_analysis(market_data, "full")
            
            # 포지션 및 수익 정보
            profit_info = await self._calculate_profit_info(market_data)
            
            # 멘탈 케어 코멘트
            mental_comment = self._generate_mental_comment(profit_info)
            
            # 예측 검증 정보
            verification = self._get_prediction_verification()
            
            now = datetime.now(pytz.timezone('Asia/Seoul'))
            
            report = f"""📡 GPT 매동 예측 분석 리포트
📅 작성 시각: {now.strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━

{gpt_analysis}

━━━━━━━━━━━━━━━━━━━
📊 예측 검증 (지난 리포트 대비)
{verification}

━━━━━━━━━━━━━━━━━━━
💰 금일 수익 및 미실현 손익
- 진입 자산: ${profit_info.get('initial_balance', 0):.1f}
- 현재 포지션: {profit_info.get('position_info', '포지션 없음')}
- 미실현 손익: ${profit_info.get('unrealized_pnl', 0):.1f} (약 {profit_info.get('unrealized_pnl', 0) * self.config.usd_to_krw:.0f}원)
- 실현 손익: ${profit_info.get('realized_pnl', 0):.1f} (약 {profit_info.get('realized_pnl', 0) * self.config.usd_to_krw:.0f}원)
- 금일 총 수익: ${profit_info.get('total_profit_usd', 0):.1f} (약 {profit_info.get('total_profit_usd', 0) * self.config.usd_to_krw:.0f}원)
- 수익률: {profit_info.get('profit_rate', 0):+.2f}%

━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어 코멘트
{mental_comment}"""
            
            return report
            
        except Exception as e:
            logger.error(f"정규 리포트 생성 실패: {e}")
            raise
    
    async def generate_forecast_report(self) -> str:
        """단기 예측 리포트 생성"""
        try:
            market_data = await self._get_market_data()
            profit_info = await self._calculate_profit_info(market_data)
            mental_comment = self._generate_mental_comment(profit_info)
            
            # GPT 단기 예측 분석
            gpt_forecast = await self._get_gpt_analysis(market_data, "forecast")
            
            now = datetime.now(pytz.timezone('Asia/Seoul'))
            
            report = f"""📈 오늘의 단기 매동 예측
📅 작성 시각: {now.strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━
{gpt_forecast}

━━━━━━━━━━━━━━━━━━━
💰 금일 손익
- 실현 손익: ${profit_info.get('realized_pnl', 0):.1f} ({profit_info.get('realized_pnl', 0) * self.config.usd_to_krw:.0f}원)
- 미실현 손익: ${profit_info.get('unrealized_pnl', 0):.1f} ({profit_info.get('unrealized_pnl', 0) * self.config.usd_to_krw:.0f}원)
- 수익률: {profit_info.get('profit_rate', 0):+.2f}%

━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어 코멘트
{mental_comment}"""
            
            return report
            
        except Exception as e:
            logger.error(f"단기 예측 리포트 생성 실패: {e}")
            raise
    
    async def generate_profit_report(self) -> str:
        """수익 현황 리포트 생성"""
        try:
            market_data = await self._get_market_data()
            profit_info = await self._calculate_profit_info(market_data)
            mental_comment = self._generate_mental_comment(profit_info)
            
            now = datetime.now(pytz.timezone('Asia/Seoul'))
            
            report = f"""💰 현재 수익 현황 요약
📅 작성 시각: {now.strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━
📌 포지션 정보
{profit_info.get('position_details', '현재 포지션이 없습니다.')}

━━━━━━━━━━━━━━━━━━━
💸 손익 정보
- 미실현 손익: ${profit_info.get('unrealized_pnl', 0):.1f} ({profit_info.get('unrealized_pnl', 0) * self.config.usd_to_krw:.0f}원)
- 실현 손익: ${profit_info.get('realized_pnl', 0):.1f} ({profit_info.get('realized_pnl', 0) * self.config.usd_to_krw:.0f}원)
- 금일 총 수익: ${profit_info.get('total_profit_usd', 0):.1f} ({profit_info.get('total_profit_usd', 0) * self.config.usd_to_krw:.0f}원)
- 진입 자산: ${profit_info.get('initial_balance', 0):.1f}
- 수익률: {profit_info.get('profit_rate', 0):+.2f}%

━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어
{mental_comment}
━━━━━━━━━━━━━━━━━━━"""
            
            return report
            
        except Exception as e:
            logger.error(f"수익 리포트 생성 실패: {e}")
            raise
    
    async def generate_schedule_report(self) -> str:
        """일정 안내 리포트 생성"""
        try:
            now = datetime.now(pytz.timezone('Asia/Seoul'))
            
            # 향후 주요 이벤트 (예시)
            events = [
                {"date": "2025-05-26 21:00", "event": "FOMC 결과 발표 예정", "impact": "호재"},
                {"date": "2025-05-28 18:00", "event": "비트코인 현물 ETF 심사 마감 예정", "impact": "호재"},
                {"date": "2025-05-30 09:00", "event": "미국 GDP 발표 예정", "impact": "중립"}
            ]
            
            report = f"""📅 자동 분석 일정 및 예정 이벤트
📅 작성 시각: {now.strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━
📋 정규 리포트 일정
- 🌅 오전 리포트: 매일 09:00 (한국시간)
- 🌞 오후 리포트: 매일 13:00 (한국시간) 
- 🌆 저녁 리포트: 매일 17:00 (한국시간)
- 🌙 야간 리포트: 매일 23:00 (한국시간)

━━━━━━━━━━━━━━━━━━━
⚡ 예외 상황 감지
- 🔍 실시간 감지: 5분마다 자동 스캔
- 🚨 긴급 알림: 2% 이상 급변동 시 즉시 발송
- 🐋 대량 이체: 1,000 BTC 이상 이동 감지 시

━━━━━━━━━━━━━━━━━━━
📡 예정 주요 이벤트"""
            
            for event in events:
                report += f"\n- {event['date']}: {event['event']} -> {event['impact']}"
            
            report += "\n\n━━━━━━━━━━━━━━━━━━━"
            report += "\n💡 사용 가능한 명령어"
            report += "\n- /report: 전체 분석 리포트"
            report += "\n- /forecast: 단기 예측 요약"
            report += "\n- /profit: 수익 현황"
            report += "\n- /schedule: 이 일정표"
            report += "\n\n🗣️ 자연어로도 질문 가능:"
            report += "\n\"지금 매수해야 돼?\", \"얼마 벌었어?\" 등"
            
            return report
            
        except Exception as e:
            logger.error(f"일정 리포트 생성 실패: {e}")
            raise
    
    async def generate_emergency_report(self, exceptions: List[Dict]) -> str:
        """긴급 상황 리포트 생성"""
        try:
            market_data = await self._get_market_data()
            
            now = datetime.now(pytz.timezone('Asia/Seoul'))
            
            # 예외 상황 요약
            exception_summary = "\n".join([
                f"- {ex['type']}: {ex['description']} -> {'호재' if ex.get('impact') == 'positive' else '악재'}"
                for ex in exceptions
            ])
            
            # GPT 긴급 분석
            gpt_emergency = await self._get_gpt_analysis(market_data, "emergency")
            
            report = f"""🚨 [BTC 예외 리포트] {now.strftime('%Y-%m-%d %H:%M')}

❗ 감지된 예외 상황:
{exception_summary}

━━━━━━━━━━━━━━━━━━━
{gpt_emergency}

━━━━━━━━━━━━━━━━━━━
📌 탐지 조건 만족 내역:
{exception_summary}"""
            
            return report
            
        except Exception as e:
            logger.error(f"긴급 리포트 생성 실패: {e}")
            raise
    
    async def _calculate_profit_info(self, market_data: Dict) -> Dict:
        """수익 정보 계산"""
        try:
            positions = market_data.get('positions', [])
            account = market_data.get('account', {})
            ticker = market_data.get('ticker', {})
            
            # 계정 정보
            total_equity = float(account.get('usdtEquity', 0))
            available_balance = float(account.get('available', 0))
            
            # 포지션 정보
            unrealized_pnl = 0
            position_info = "포지션 없음"
            position_details = "현재 포지션이 없습니다."
            
            if positions:
                pos = positions[0]  # 첫 번째 포지션
                size = float(pos.get('size', 0))
                side = pos.get('side', '')
                entry_price = float(pos.get('averageOpenPrice', 0))
                current_price = float(ticker.get('lastPr', 0))
                leverage = float(pos.get('leverage', 1))
                unrealized_pnl = float(pos.get('unrealizedPL', 0))
                
                position_info = f"BTCUSDT {side.upper()} (진입가 ${entry_price:.0f} / 현재가 ${current_price:.0f})"
                position_details = f"""- 종목: BTCUSDT
- 방향: {side.upper()}
- 진입가: ${entry_price:.0f} / 현재가: ${current_price:.0f}
- 레버리지: {leverage:.0f}x
- 포지션 크기: {size} BTC
- 미실현 손익: ${unrealized_pnl:.1f}"""
            
            # 수익률 계산 (가정: 초기 자산 기준)
            initial_balance = max(2000, total_equity)  # 실제 자산이 있으면 사용
            total_profit_usd = unrealized_pnl  # 실현손익은 별도 관리 필요
            profit_rate = (total_profit_usd / initial_balance * 100) if initial_balance > 0 else 0
            
            return {
                'unrealized_pnl': unrealized_pnl,
                'realized_pnl': 0,  # 실현손익은 별도 DB 관리 필요
                'total_profit_usd': total_profit_usd,
                'profit_rate': profit_rate,
                'initial_balance': initial_balance,
                'position_info': position_info,
                'position_details': position_details,
                'total_equity': total_equity,
                'available_balance': available_balance
            }
            
        except Exception as e:
            logger.error(f"수익 정보 계산 실패: {e}")
            return {
                'unrealized_pnl': 0,
                'realized_pnl': 0,
                'total_profit_usd': 0,
                'profit_rate': 0,
                'initial_balance': 2000,
                'position_info': '포지션 없음',
                'position_details': '현재 포지션이 없습니다.',
                'total_equity': 0,
                'available_balance': 0
            }
    
    def _get_prediction_verification(self) -> str:
        """예측 검증 정보"""
        if not self.prediction_history:
            return "- 검증할 이전 예측이 없습니다."
        
        # 최근 예측 정확도 계산 (임시 구현)
        recent_predictions = self.prediction_history[-10:]
        correct_predictions = sum(1 for p in recent_predictions if p.get('correct', False))
        accuracy = (correct_predictions / len(recent_predictions) * 100) if recent_predictions else 0
        
        last_prediction = self.prediction_history[-1] if self.prediction_history else None
        if last_prediction:
            result = "✅ 적중" if last_prediction.get('correct', False) else "❌ 미적중"
            return f"- {last_prediction.get('date', '날짜미상')} 예측: {last_prediction.get('prediction', '예측미상')} → {result}\n- 최근 10회 중 {correct_predictions}회 적중 (정확도: {accuracy:.0f}%)"
        
        return "- 검증할 예측 데이터가 없습니다."
