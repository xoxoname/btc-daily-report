# analysis_engine.py - GPT 분석 엔진
import logging
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz
import openai
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
