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
        """멘탈 케어 코멘트 생성 (충동 매매 방지 포함)"""
        try:
            total_profit_usd = profit_info.get('total_profit_usd', 0)
            profit_rate = profit_info.get('profit_rate', 0)
            
            # 수익 상황별 코멘트 (더 길고 구체적으로)
            if profit_rate >= 10:
                comments = [
                    f"🎉 오늘 선물로 {abs(total_profit_usd * self.config.usd_to_krw):.0f}원을 벌었다니, 편의점 알바 10시간을 해야 벌 수 있는 돈이에요! 이제 이 수익으로 오늘 매매는 쉬고 다음 타점이 나올 때까지 차분히 기다려봐요. 과욕은 금물입니다.",
                    f"💎 대단한 성과네요! {abs(total_profit_usd * self.config.usd_to_krw):.0f}원이면 맛있는 저녁 한 달치예요. 하지만 연승에 취해서 레버리지를 높이거나 무리한 매매는 피해주세요. 오늘 같은 날에도 겸손함을 잃지 마세요.",
                    f"🚀 로켓 같은 수익률이지만, 시장은 항상 변합니다. 지금 이 순간의 희열에 빠져 추가 매매를 하고 싶겠지만, 잠시 멈추고 호흡을 가다듬어보세요. 다음 기회는 충분히 올 거예요."
                ]
            elif profit_rate >= 1:
                comments = [
                    f"💰 수익은 습관입니다. 오늘 {abs(total_profit_usd * self.config.usd_to_krw):.0f}원의 작은 성과도 쌓이면 큰 산이 됩니다. 조급해하지 말고 꾸준히 가는 것이 승리의 비결이에요. 작은 수익에 만족하며 다음을 준비해봐요.",
                    f"📈 꾸준함이 최고의 전략입니다. 오늘도 플러스를 기록했으니 충분해요. 더 큰 수익을 위해 무리하지 말고, 이 페이스를 유지하는 것이 중요합니다. 급하게 갈 필요 없어요.",
                    f"☕ 오늘 수익으로 좋은 커피 한 잔 마시며 만족해봐요. 작은 수익을 무시하고 큰 수익만 좇다 보면 오히려 손실로 이어질 수 있어요. 지금처럼만 하면 됩니다."
                ]
            elif -1 <= profit_rate <= 1:
                comments = [
                    f"⏳ 조용한 날도 내일의 기회를 위해 꼭 필요합니다. 수익이 없다고 조급해하지 마세요. 오히려 이런 날에 섣불리 매매하다가 손실을 보는 경우가 많아요. 참을성이 투자의 미덕입니다.",
                    f"🧘‍♂️ 횡보는 폭풍 전의 고요함일 수 있어요. 지금 당장 움직임이 없다고 해서 무리하게 포지션을 잡을 필요는 없습니다. 기다리는 것도 실력이고, 때로는 가장 현명한 선택이에요.",
                    f"📊 시장이 쉬어가는 날에는 우리도 쉬어가며 다음 기회를 준비해요. 매일 수익을 내려고 하는 것은 욕심입니다. 좋은 타이밍이 올 때까지 인내심을 갖고 기다려봐요."
                ]
            elif -5 <= profit_rate < -1:
                comments = [
                    f"📉 작은 손실은 학습비라고 생각해요. {abs(total_profit_usd * self.config.usd_to_krw):.0f}원의 손실이 아깝다고 해서 급하게 만회하려고 하면 더 큰 손실이 올 수 있어요. 오늘은 여기서 정리하고 내일을 기약해봐요.",
                    f"🌱 손실도 성장의 밑거름이 됩니다. 지금 당장은 아프지만 이런 경험이 쌓여야 진짜 투자자가 되는 거예요. 복수 매매는 절대 금물이니까 마음을 가라앉히고 다음을 준비해봐요.",
                    f"🔄 시장은 항상 변합니다. 오늘의 빨간불이 내일의 파란불을 위한 준비시간이라고 생각해요. 손실을 만회하려고 레버리지를 높이거나 무리한 매매는 하지 마세요."
                ]
            else:
                comments = [
                    f"🛑 큰 손실이지만 패닉은 금물입니다. {abs(total_profit_usd * self.config.usd_to_krw):.0f}원의 손실이 크게 느껴지겠지만, 지금 감정적으로 매매하면 더 큰 손실이 올 수 있어요. 하루 정도 쉬면서 마음을 정리해봐요.",
                    f"💪 어려운 시기일수록 기본으로 돌아가는 것이 중요합니다. 손실을 빨리 만회하고 싶은 마음은 이해하지만, 지금은 휴식을 취하고 전략을 재점검할 때입니다. 시스템을 믿고 기다려봐요.",
                    f"🎯 지금은 휴식기입니다. 큰 손실 후에는 감정이 앞서기 마련이에요. 무리하지 말고 며칠 쉬면서 객관적인 시각을 되찾는 것이 중요합니다. 다시 일어설 수 있어요."
                ]
            
            # 수익을 시간당 임금으로 환산
            krw_profit = abs(total_profit_usd) * self.config.usd_to_krw
            if krw_profit >= 100000:
                time_equivalent = "편의점 알바 약 10시간"
            elif krw_profit >= 50000:
                time_equivalent = "편의점 알바 약 5시간"
            elif krw_profit >= 20000:
                time_equivalent = "카페 알바 약 2시간"
            elif krw_profit >= 10000:
                time_equivalent = "햄버거 세트 2개"
            else:
                time_equivalent = "커피 한 잔"
            
            comment = random.choice(comments)
            
            return comment
            
        except Exception as e:
            logger.error(f"멘탈 코멘트 생성 실패: {e}")
            return "💪 투자는 마라톤입니다. 오늘 하루의 결과에 일희일비하지 말고, 장기적인 관점에서 꾸준히 해나가는 것이 중요해요. 감정적인 매매는 피하고 계획에 따라 행동해봐요."
    
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
        """단기 예측 리포트 생성 (문서 형식에 맞게)"""
        try:
            market_data = await self._get_market_data()
            profit_info = await self._calculate_profit_info(market_data)
            mental_comment = self._generate_mental_comment(profit_info)
            
            # GPT 단기 예측 분석
            gpt_forecast = await self._get_gpt_analysis(market_data, "forecast")
            
            # 기술적 지표 계산
            tech_indicators = self._calculate_technical_indicators(market_data.get('klines_4h', []))
            ticker = market_data.get('ticker', {})
            funding = market_data.get('funding', {})
            
            now = datetime.now(pytz.timezone('Asia/Seoul'))
            
            # 분석 요약 섹션 생성
            current_price = ticker.get('lastPr', 'N/A')
            price_change_24h = ticker.get('change24h', 'N/A')
            rsi = tech_indicators.get('rsi', 'N/A')
            funding_rate = funding.get('fundingRate', 'N/A')
            
            # 호재/악재 판단
            tech_status = "📈 호재" if rsi and float(rsi) < 70 else "⚠️ 악재" if rsi else "📊 중립"
            funding_status = "⚠️ 악재" if funding_rate and abs(float(funding_rate)) > 0.0001 else "📈 호재"
            
            report = f"""📈 오늘의 단기 매동 예측
📅 작성 시각: {now.strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━
📊 분석 요약
- 기술적 분석: 현재가 ${current_price}, RSI {rsi} → {tech_status}
- 심리 분석: 펀딩비 {funding_rate}, 24h 변동 {price_change_24h}% → {funding_status}
- 구조 분석: 시장 동향 분석 중 → 📊 중립

━━━━━━━━━━━━━━━━━━━
🔮 12시간 매동 전망
- 상승 확률: 40%
- 횡보 확률: 35%
- 하락 확률: 25%
📌 전략 제안: 분할 진입 + 익절 설정 필수
레버리지 포지션은 고점 추격 유의

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
            
            # 수익률 계산 - 실제 총 자산 기준으로 계산
            initial_balance = total_equity if total_equity > 0 else 6366.4  # 실제 자산 사용
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
                'initial_balance': 6366.4,  # 실제 자산으로 설정
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
