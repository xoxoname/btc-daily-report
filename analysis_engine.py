async def _generate_gpt_mental_comment(self, profit_info: Dict) -> str:
        """GPT 기반 실시간 멘탈 케어 코멘트 생성"""
        try:
            total_profit_usd = profit_info.get('total_profit_usd', 0)
            profit_rate = profit_info.get('profit_rate', 0)
            total_equity = profit_info.get('total_equity', 0)
            realized_pnl = profit_info.get('realized_pnl', 0)
            unrealized_pnl = profit_info.get('unrealized_pnl', 0)
            has_position = profit_info.get('position_info') != '포지션 없음'
            
            # 한국어 환산
            krw_total_profit = total_profit_usd * self.config.usd_to_krw
            krw_realized = realized_pnl * self.config.usd_to_krw
            krw_unrealized = unrealized_pnl * self.config.usd_to_krw
            
            # GPT 프롬프트 구성
            system_prompt = """
당신은 비트코인 선물 거래자를 위한 전문 멘탈 케어 상담사입니다.
거래자의 현재 자산 상황과 손익을 바탕으로 개인화된 조언을 제공해주세요.

조언 방향:
1. 충동적 매매 방지
2. 감정적 대응 억제  
3. 현실적이고 구체적인 조언
4. 따뜻하지만 현실적인 톤
5. 2-3문장으로 간결하게 작성

금지 사항:
- 형식적이거나 천편일률적인 조언
- 투자 권유나 구체적 매매 신호
"""
            
            user_prompt = f"""
현재 거래자 상황:
- 총 자산: ${total_equity:.1f} (약 {total_equity * self.config.usd_to_krw:.0f}원)
- 오늘 손익: ${total_profit_usd:.1f} (약 {krw_total_profit:.0f}원)
- 수익률: {profit_rate:+.2f}%
- 지금까지 실현 손익: ${realized_pnl:.1f} (약 {krw_realized:.0f}원)
- 현재 미실현 손익: ${unrealized_pnl:.1f} (약 {krw_unrealized:.0f}원)
- 포지션 보유 여부: {'있음' if has_position else '없음'}

이 거래자에게 맞춤형 멘탈 케어 조언을 2-3문장으로 작성해주세요.
거래자의 실제 상황을 반영한 구체적이고 개인화된 조언이어야 합니다.
"""
            
            response = await self.client.chat.completions.create(
                model=self.config.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=300,
                temperature=0.8
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"GPT 멘탈 코멘트 생성 실패: {e}")
            # 폴백 코멘트
            return f"💪 총 ${profit_info.get('total_equity', 0):.0f}의 자산으로 꾸준히 하고 계시네요. 감정적인 매매보다는 계획적인 접근이 중요해요. 오늘 하루의 결과에 너무 연연하지 마시고 장기적인 관점을 유지해보세요."    def _generate_mental_comment(self, profit_info: Dict) -> str:
        """멘탈 케어 코멘트 생성 (매번 다르게, 실시간 상황 반영)"""
        try:
            total_profit_usd = profit_info.get('total_profit_usd', 0)
            profit_rate = profit_info.get('profit_rate', 0)
            total_equity = profit_info.get('total_equity', 0)
            has_position = profit_info.get('position_info') != '포지션 없음'
            
            # 실시간 상황 기반 코멘트 생성
            krw_profit = abs(total_profit_usd) * self.config.usd_to_krw
            
            if profit_rate >= 5:
                # 큰 수익
                comments = [
                    f"🎉 와! {krw_profit:.0f}원 수익이라니! 이 정도면 오늘은 정말 성공적인 거래였어요. 하지만 여기서 욕심 부리지 말고 적당한 선에서 익절하는 것도 고려해봐요. 시장은 항상 변하니까요.",
                    f"💎 {profit_rate:.2f}% 수익률! 대단해요! 하지만 승리에 취해서 레버리지를 더 올리거나 추가 매매하고 싶은 충동을 억제해봐요. 지금처럼 차근차근 하는 게 최고예요.",
                    f"🚀 {krw_profit:.0f}원이면 편의점 알바 하루치 급여네요! 하지만 시장은 언제든 변할 수 있으니 방심은 금물이에요. 적절한 익절 타이밍을 놓치지 마세요."
                ]
            elif profit_rate >= 1:
                # 적당한 수익
                comments = [
                    f"💰 {krw_profit:.0f}원의 꾸준한 수익! 작아 보일 수 있지만 이런 작은 수익들이 모여서 큰 자산이 되는 거예요. 조급해하지 말고 이 페이스 유지해봐요.",
                    f"📈 {profit_rate:.2f}% 수익률로 플러스 행진 중! 큰 수익은 아니지만 손실보다 훨씬 좋죠. 무리하지 말고 지금처럼만 해도 충분해요.",
                    f"☕ {krw_profit:.0f}원이면 좋은 커피 몇 잔은 마실 수 있겠네요! 작은 수익에 만족하며 다음 기회를 기다리는 것도 투자의 지혜입니다."
                ]
            elif -1 <= profit_rate <= 1:
                # 횡보/소폭 변동
                if has_position:
                    comments = [
                        f"⏳ 지금은 시장이 고민하는 시간인 것 같아요. 포지션이 있으니 조금 더 기다려봐도 될 것 같지만, 너무 오래 버티지는 마세요. 손절선도 중요해요.",
                        f"🧘‍♂️ 포지션을 들고 있는 상황에서 횡보라니 조금 답답하시겠어요. 하지만 급하게 추가 매매하지 말고 시장의 방향성이 나올 때까지 인내해봐요.",
                        f"📊 {total_equity:.0f}달러의 자산으로 안전하게 운용 중이시네요. 수익이 크지 않아도 손실 없이 유지하는 것만으로도 충분히 훌륭해요."
                    ]
                else:
                    comments = [
                        f"⏳ 포지션 없이 관망 중이시군요! 이럴 때일수록 섣불리 진입하지 말고 확실한 신호가 나올 때까지 기다리는 게 현명해요.",
                        f"🧘‍♂️ 현금 보유 상태에서 시장을 지켜보는 것도 훌륭한 전략이에요. 무리해서 포지션 잡지 말고 좋은 타이밍을 기다려봐요.",
                        f"📊 {total_equity:.0f}달러의 안전한 현금으로 다음 기회를 준비하고 계시네요. 조급해하지 마세요."
                    ]
            elif -5 <= profit_rate < -1:
                # 소폭 손실
                comments = [
                    f"📉 -{krw_profit:.0f}원 손실이지만 큰 문제없어요. 이 정도는 수업료라고 생각하시고, 복수 매매만 하지 마세요. 감정적으로 대응하면 더 큰 손실로 이어질 수 있어요.",
                    f"🌱 -{profit_rate:.2f}% 손실이네요. 아깝긴 하지만 이런 경험이 실력 향상에 도움이 될 거예요. 손절은 빨리, 익절은 천천히가 원칙이에요.",
                    f"🔄 -{krw_profit:.0f}원 손실! 지금 당장 만회하고 싶겠지# analysis_engine.py - GPT 분석 엔진
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
        """멘탈 케어 코멘트 생성 (매번 다르게, 실시간 상황 반영)"""
        try:
            total_profit_usd = profit_info.get('total_profit_usd', 0)
            profit_rate = profit_info.get('profit_rate', 0)
            total_equity = profit_info.get('total_equity', 0)
            realized_pnl = profit_info.get('realized_pnl', 0)
            has_position = profit_info.get('position_info') != '포지션 없음'
            
            # 실시간 상황 기반 코멘트 생성
            krw_profit = abs(total_profit_usd) * self.config.usd_to_krw
            
            if profit_rate >= 5:
                # 큰 수익
                comments = [
                    f"🎉 와! {krw_profit:.0f}원 수익이라니! 이 정도면 오늘은 정말 성공적인 거래였어요. 하지만 여기서 욕심 부리지 말고 적당한 선에서 익절하는 것도 고려해봐요. 시장은 항상 변하니까요.",
                    f"💎 {profit_rate:.2f}% 수익률! 대단해요! 하지만 승리에 취해서 레버리지를 더 올리거나 추가 매매하고 싶은 충동을 억제해봐요. 지금처럼 차근차근 하는 게 최고예요.",
                    f"🚀 {krw_profit:.0f}원이면 편의점 알바 하루치 급여네요! 하지만 시장은 언제든 변할 수 있으니 방심은 금물이에요. 적절한 익절 타이밍을 놓치지 마세요."
                ]
            elif profit_rate >= 1:
                # 적당한 수익
                comments = [
                    f"💰 {krw_profit:.0f}원의 꾸준한 수익! 작아 보일 수 있지만 이런 작은 수익들이 모여서 큰 자산이 되는 거예요. 조급해하지 말고 이 페이스 유지해봐요.",
                    f"📈 {profit_rate:.2f}% 수익률로 플러스 행진 중! 큰 수익은 아니지만 손실보다 훨씬 좋죠. 무리하지 말고 지금처럼만 해도 충분해요.",
                    f"☕ {krw_profit:.0f}원이면 좋은 커피 몇 잔은 마실 수 있겠네요! 작은 수익에 만족하며 다음 기회를 기다리는 것도 투자의 지혜입니다."
                ]
            elif -1 <= profit_rate <= 1:
                # 횡보/소폭 변동
                if has_position:
                    comments = [
                        f"⏳ 지금은 시장이 고민하는 시간인 것 같아요. 포지션이 있으니 조금 더 기다려봐도 될 것 같지만, 너무 오래 버티지는 마세요. 손절선도 중요해요.",
                        f"🧘‍♂️ 포지션을 들고 있는 상황에서 횡보라니 조금 답답하시겠어요. 하지만 급하게 추가 매매하지 말고 시장의 방향성이 나올 때까지 인내해봐요.",
                        f"📊 ${total_equity:.0f}의 자산으로 안전하게 운용 중이시네요. 수익이 크지 않아도 손실 없이 유지하는 것만으로도 충분히 훌륭해요."
                    ]
                else:
                    comments = [
                        f"⏳ 포지션 없이 관망 중이시군요! 이럴 때일수록 섣불리 진입하지 말고 확실한 신호가 나올 때까지 기다리는 게 현명해요.",
                        f"🧘‍♂️ 현금 보유 상태에서 시장을 지켜보는 것도 훌륭한 전략이에요. 무리해서 포지션 잡지 말고 좋은 타이밍을 기다려봐요.",
                        f"📊 ${total_equity:.0f}의 안전한 현금으로 다음 기회를 준비하고 계시네요. 조급해하지 마세요."
                    ]
            elif -5 <= profit_rate < -1:
                # 소폭 손실
                comments = [
                    f"📉 -{krw_profit:.0f}원 손실이지만 큰 문제없어요. 이 정도는 수업료라고 생각하시고, 복수 매매만 하지 마세요. 감정적으로 대응하면 더 큰 손실로 이어질 수 있어요.",
                    f"🌱 -{profit_rate:.2f}% 손실이네요. 아깝긴 하지만 이런 경험이 실력 향상에 도움이 될 거예요. 손절은 빨리, 익절은 천천히가 원칙이에요.",
                    f"🔄 -{krw_profit:.0f}원 손실! 지금 당장 만회하고 싶겠지만 더 큰 손실 방지를 위해 차분하게 접근하세요. 시장은 내일도 있어요."
                ]
            else:
                # 큰 손실
                comments = [
                    f"🛑 -{krw_profit:.0f}원의 큰 손실이네요. 지금은 감정적으로 대응하지 말고 하루 정도 쉬면서 마음을 정리하는 시간을 가져봐요. 복수 매매는 절대 금물이에요.",
                    f"💪 -{profit_rate:.2f}%의 손실이 크게 느껴지겠지만, 이럴 때일수록 기본으로 돌아가야 해요. 레버리지를 줄이고 안전한 매매로 천천히 회복해봐요.",
                    f"🎯 큰 손실 후에는 며칠 쉬는 것이 최선의 선택일 수 있어요. ${total_equity:.0f}의 자산이 남아있으니 충분히 회복 가능해요. 포기하지 마세요."
                ]
            
            # 실현 손익이 있을 경우 추가 멘트
            if realized_pnl > 0:
                additional_comment = f" 지금까지 총 {realized_pnl * self.config.usd_to_krw:.0f}원을 실현하셨네요. 꾸준히 하시고 계시는 것 같아 보기 좋습니다!"
            elif realized_pnl < 0:
                additional_comment = f" 지금까지 총 손실이 {abs(realized_pnl) * self.config.usd_to_krw:.0f}원이네요. 하지만 이것도 경험치예요. 포기하지 마세요."
            else:
                additional_comment = ""
            
            comment = random.choice(comments) + additional_comment
            
            return comment
            
        except Exception as e:
            logger.error(f"멘탈 코멘트 생성 실패: {e}")
            return f"💪 투자는 마라톤입니다. ${profit_info.get('total_equity', 0):.0f}의 자산으로 꾸준히 해나가시면 됩니다. 감정적인 매매는 피하고 계획에 따라 행동해봐요."봐요.",
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
        """수익 현황 리포트 생성 (GPT 멘탈 코멘트 포함)"""
        try:
            market_data = await self._get_market_data()
            profit_info = await self._calculate_profit_info(market_data)
            
            # GPT 기반 멘탈 케어 코멘트 생성
            mental_comment = await self._generate_gpt_mental_comment(profit_info)
            
            now = datetime.now(pytz.timezone('Asia/Seoul'))
            
            report = f"""💰 현재 수익 현황 요약
📅 작성 시각: {now.strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━
📌 포지션 정보
{profit_info.get('position_details', '보유 중인 포지션이 없습니다.')}

━━━━━━━━━━━━━━━━━━━
💸 손익 정보
- 미실현 손익: ${profit_info.get('unrealized_pnl', 0):.1f} ({profit_info.get('unrealized_pnl', 0) * self.config.usd_to_krw:.0f}원)
- 실현 손익: ${profit_info.get('realized_pnl', 0):.1f} ({profit_info.get('realized_pnl', 0) * self.config.usd_to_krw:.0f}원)
- 금일 총 수익: ${profit_info.get('total_profit_usd', 0):.1f} ({profit_info.get('total_profit_usd', 0) * self.config.usd_to_krw:.0f}원)
- 총 자산: ${profit_info.get('total_equity', 0):.1f}
- 금일 수익률: {profit_info.get('profit_rate', 0):+.2f}%
- 지금까지 총 수익률: {profit_info.get('total_return_rate', 0):+.2f}%
- 지금까지 총 수익금: ${profit_info.get('realized_pnl', 0):.1f} ({profit_info.get('realized_pnl', 0) * self.config.usd_to_krw:.0f}원)

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
            realized_pnl = 0  # 실현 손익 초기화
            position_info = "포지션 없음"
            position_details = "보유 중인 포지션이 없습니다."
            liquidation_info = ""
            
            if positions:
                pos = positions[0]  # 첫 번째 포지션
                # Bitget API에서는 'total' 필드가 실제 포지션 크기
                size = float(pos.get('total', 0))  
                side = pos.get('holdSide', '')  
                entry_price = float(pos.get('openPriceAvg', 0))  
                current_price = float(pos.get('markPrice', 0))  
                leverage = float(pos.get('leverage', 1))
                unrealized_pnl = float(pos.get('unrealizedPL', 0))
                realized_pnl = float(pos.get('achievedProfits', 0))  # 실현 손익 추가
                liquidation_price = float(pos.get('liquidationPrice', 0))
                
                # 청산가까지 거리 계산
                if liquidation_price > 0:
                    liquidation_distance_pct = ((liquidation_price - current_price) / current_price * 100)
                    liquidation_distance_usd = abs(liquidation_price - current_price)
                    liquidation_info = f"\n- 청산가: ${liquidation_price:.0f}\n- 청산까지 남은 거리: 약 {liquidation_distance_pct:+.1f}% (약 ${liquidation_distance_usd:.0f} {'하락' if liquidation_distance_pct < 0 else '상승'} 시 청산)"
                
                position_info = f"BTCUSDT {side.upper()} (진입가 ${entry_price:.0f} / 현재가 ${current_price:.0f})"
                position_details = f"""- 종목: BTCUSDT
- 방향: {side.upper()}
- 진입가: ${entry_price:.0f} / 현재가: ${current_price:.0f}
- 레버리지: {leverage:.0f}x
- 포지션 크기: {size} BTC
- 미실현 손익: ${unrealized_pnl:.1f}{liquidation_info}"""
            
            # 수익률 계산 - 실제 총 자산 기준으로 계산
            initial_balance = total_equity if total_equity > 0 else 6366.4  
            total_profit_usd = unrealized_pnl + realized_pnl  # 실현 + 미실현 합계
            profit_rate = (total_profit_usd / initial_balance * 100) if initial_balance > 0 else 0
            
            # 지금까지의 총 수익률과 수익금 (실현 손익 기준)
            total_return_rate = (realized_pnl / initial_balance * 100) if initial_balance > 0 else 0
            
            return {
                'unrealized_pnl': unrealized_pnl,
                'realized_pnl': realized_pnl,  # 실제 실현 손익 사용
                'total_profit_usd': total_profit_usd,
                'profit_rate': profit_rate,
                'total_return_rate': total_return_rate,  # 총 수익률 추가
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
                'total_return_rate': 0,
                'initial_balance': 6366.4,  
                'position_info': '포지션 없음',
                'position_details': '보유 중인 포지션이 없습니다.',
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
