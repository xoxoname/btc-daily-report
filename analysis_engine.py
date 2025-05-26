import logging
from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime, timedelta
import traceback
import os
import openai

class AnalysisEngine:
    def __init__(self, bitget_client, openai_client=None):
        self.bitget_client = bitget_client
        self.logger = logging.getLogger('analysis_engine')
        
        # OpenAI 클라이언트 초기화
        if openai_client is None:
            openai.api_key = os.getenv('OPENAI_API_KEY')
            self.openai_client = openai.AsyncOpenAI(api_key=openai.api_key)
        else:
            self.openai_client = openai_client
        
    async def generate_prediction(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """AI 기반 비트코인 예측 생성"""
        try:
            # 시장 데이터 분석
            analysis_result = await self._analyze_market_data(market_data)
            
            # OpenAI를 사용한 예측 생성
            prediction_prompt = self._create_prediction_prompt(market_data, analysis_result)
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "당신은 전문적인 암호화폐 분석가입니다. 시장 데이터를 기반으로 정확하고 신중한 예측을 제공합니다."},
                    {"role": "user", "content": prediction_prompt}
                ],
                max_tokens=1500,
                temperature=0.7
            )
            
            ai_analysis = response.choices[0].message.content
            
            # 예측 결과 구조화
            prediction = {
                'timestamp': datetime.now().isoformat(),
                'current_price': market_data.get('current_price', 0),
                'ai_analysis': ai_analysis,
                'technical_analysis': analysis_result,
                'prediction_confidence': self._calculate_confidence(analysis_result),
                'risk_level': self._assess_risk_level(market_data, analysis_result),
                'recommended_action': self._get_recommendation(analysis_result)
            }
            
            return prediction
            
        except Exception as e:
            self.logger.error(f"예측 생성 실패: {str(e)}")
            self.logger.debug(f"예측 생성 오류 상세: {traceback.format_exc()}")
            raise

    async def generate_profit_report(self, position_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """수익 리포트 생성"""
        try:
            self.logger.info("수익 리포트 생성 시작")
            
            # 현재 시장 데이터 조회
            current_price = await self._get_current_price()
            if not current_price:
                return {
                    'error': '현재 가격을 조회할 수 없습니다',
                    'timestamp': datetime.now().isoformat()
                }
            
            # 기본 시장 정보
            market_info = await self._get_market_summary()
            
            # 포지션 데이터가 있는 경우 수익 계산
            profit_info = {}
            if position_data:
                profit_info = await self.calculate_profit_info(position_data)
            
            # 24시간 성과 요약
            performance_summary = await self._calculate_24h_performance()
            
            # AI 분석 추가 (OpenAI API 키가 있는 경우에만)
            ai_summary = "시장 데이터 기반 분석을 진행중입니다."
            if os.getenv('OPENAI_API_KEY'):
                try:
                    ai_summary = await self._generate_ai_summary(market_info, profit_info)
                except Exception as e:
                    self.logger.warning(f"AI 분석 생성 실패: {str(e)}")
                    ai_summary = "AI 분석을 일시적으로 사용할 수 없습니다."
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'current_price': current_price,
                'market_info': market_info,
                'profit_info': profit_info,
                'performance_summary': performance_summary,
                'ai_summary': ai_summary,
                'status': 'success'
            }
            
            self.logger.info("수익 리포트 생성 완료")
            return report
            
        except Exception as e:
            self.logger.error(f"수익 리포트 생성 실패: {str(e)}")
            self.logger.debug(f"수익 리포트 오류 상세: {traceback.format_exc()}")
            return {
                'error': f'수익 리포트 생성 중 오류 발생: {str(e)}',
                'timestamp': datetime.now().isoformat(),
                'status': 'error'
            }

    async def calculate_profit_info(self, position_data: Dict[str, Any]) -> Dict[str, Any]:
        """수익 정보 계산"""
        try:
            current_price = await self._get_current_price()
            if not current_price:
                return {'error': '현재 가격을 가져올 수 없습니다'}
            
            entry_price = position_data.get('entry_price', 0)
            position_size = position_data.get('size', 0)
            side = position_data.get('side', 'long')  # 'long' 또는 'short'
            
            if entry_price == 0:
                return {'error': '진입 가격 정보가 없습니다'}
            
            if position_size == 0:
                return {'error': '포지션 크기 정보가 없습니다'}
            
            # 수익률 계산
            if side.lower() == 'long':
                pnl_rate = (current_price - entry_price) / entry_price
                pnl_usd = position_size * (current_price - entry_price)
            else:  # short
                pnl_rate = (entry_price - current_price) / entry_price
                pnl_usd = position_size * (entry_price - current_price)
            
            return {
                'current_price': current_price,
                'entry_price': entry_price,
                'position_size': position_size,
                'side': side,
                'pnl_rate': pnl_rate,
                'pnl_usd': pnl_usd,
                'pnl_percentage': pnl_rate * 100,
                'status': 'profit' if pnl_usd > 0 else 'loss' if pnl_usd < 0 else 'breakeven'
            }
            
        except Exception as e:
            self.logger.error(f"수익 정보 계산 실패: {str(e)}")
            return {'error': f'수익 계산 중 오류 발생: {str(e)}'}

    async def _get_market_summary(self) -> Dict[str, Any]:
        """시장 요약 정보 조회"""
        try:
            # BitgetClient 메서드 확인 및 호출
            if hasattr(self.bitget_client, 'get_ticker'):
                ticker_data = await self.bitget_client.get_ticker('BTCUSDT')
            else:
                self.logger.error("BitgetClient에 get_ticker 메서드가 없습니다")
                return {'error': 'BitgetClient 설정 오류'}
            
            if isinstance(ticker_data, list):
                if ticker_data:
                    ticker_data = ticker_data[0]
                else:
                    return {'error': '시장 데이터를 가져올 수 없습니다'}
            
            # 안전한 데이터 추출
            def safe_get(data, keys, default=0):
                for key in keys:
                    if key in data:
                        try:
                            return float(data[key])
                        except (ValueError, TypeError):
                            continue
                return default
            
            current_price = safe_get(ticker_data, ['last', 'lastPr', 'price', 'close'])
            high_24h = safe_get(ticker_data, ['high', 'high24h', 'highPr'])
            low_24h = safe_get(ticker_data, ['low', 'low24h', 'lowPr'])
            volume_24h = safe_get(ticker_data, ['baseVolume', 'volume', 'vol24h', 'baseVol'])
            change_24h = safe_get(ticker_data, ['changeUtc', 'change24h', 'priceChangePercent'])
            
            return {
                'current_price': current_price,
                'high_24h': high_24h,
                'low_24h': low_24h,
                'volume_24h': volume_24h,
                'change_24h': change_24h,
                'change_24h_percent': change_24h * 100,
                'volatility': ((high_24h - low_24h) / current_price * 100) if current_price > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"시장 요약 조회 실패: {str(e)}")
            return {'error': f'시장 데이터 조회 실패: {str(e)}'}

    async def _calculate_24h_performance(self) -> Dict[str, Any]:
        """24시간 성과 계산"""
        try:
            market_info = await self._get_market_summary()
            
            if 'error' in market_info:
                return market_info
            
            change_24h = market_info.get('change_24h', 0)
            volatility = market_info.get('volatility', 0)
            
            # 성과 등급 계산
            if change_24h > 0.05:  # 5% 이상 상승
                performance_grade = "매우 좋음"
            elif change_24h > 0.02:  # 2% 이상 상승
                performance_grade = "좋음"
            elif change_24h > -0.02:  # -2% ~ 2%
                performance_grade = "보통"
            elif change_24h > -0.05:  # -5% ~ -2%
                performance_grade = "나쁨"
            else:
                performance_grade = "매우 나쁨"
            
            return {
                'change_24h_percent': change_24h * 100,
                'volatility_percent': volatility,
                'performance_grade': performance_grade,
                'trend': '상승' if change_24h > 0 else '하락' if change_24h < 0 else '횡보'
            }
            
        except Exception as e:
            self.logger.error(f"24시간 성과 계산 실패: {str(e)}")
            return {'error': f'성과 계산 실패: {str(e)}'}

    async def _generate_ai_summary(self, market_info: Dict[str, Any], profit_info: Dict[str, Any]) -> str:
        """AI 요약 생성"""
        try:
            if 'error' in market_info:
                return "시장 데이터를 분석할 수 없어 AI 요약을 생성할 수 없습니다."
            
            prompt = f"""
다음 비트코인 시장 데이터를 분석해주세요:

현재 가격: ${market_info.get('current_price', 0):,.2f}
24시간 변동: {market_info.get('change_24h_percent', 0):.2f}%
24시간 고가: ${market_info.get('high_24h', 0):,.2f}
24시간 저가: ${market_info.get('low_24h', 0):,.2f}
변동성: {market_info.get('volatility', 0):.2f}%

{"포지션 수익률: " + str(profit_info.get('pnl_percentage', 0)) + "%" if profit_info and 'pnl_percentage' in profit_info else ""}

간단하고 명확한 한국어로 현재 시장 상황을 요약해주세요. (3-4줄)
"""
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "당신은 간결하고 명확한 암호화폐 시장 분석가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.5
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"AI 요약 생성 실패: {str(e)}")
            return "AI 분석을 생성할 수 없습니다. 시장 데이터를 직접 확인해주세요."

    async def _get_current_price(self) -> Optional[float]:
        """현재 가격 조회"""
        try:
            # BitgetClient 메서드 확인
            if not hasattr(self.bitget_client, 'get_ticker'):
                self.logger.error("BitgetClient에 get_ticker 메서드가 없습니다")
                return None
            
            ticker_data = await self.bitget_client.get_ticker('BTCUSDT')
            
            if isinstance(ticker_data, list):
                if ticker_data:
                    ticker_data = ticker_data[0]
                else:
                    return None
            
            price_fields = ['last', 'lastPr', 'price', 'close']
            for field in price_fields:
                if field in ticker_data:
                    try:
                        return float(ticker_data[field])
                    except (ValueError, TypeError):
                        continue
                        
        except Exception as e:
            self.logger.error(f"현재 가격 조회 실패: {str(e)}")
            
        return None

    async def _analyze_market_data(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """시장 데이터 기술적 분석"""
        try:
            analysis = {
                'price_trend': self._analyze_price_trend(market_data),
                'volume_analysis': self._analyze_volume(market_data),
                'volatility': self._calculate_volatility(market_data),
                'support_resistance': await self._find_support_resistance(),
                'market_sentiment': self._analyze_sentiment(market_data)
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"시장 데이터 분석 실패: {str(e)}")
            return {}
    
    def _analyze_price_trend(self, market_data: Dict[str, Any]) -> str:
        """가격 트렌드 분석"""
        try:
            change_24h = market_data.get('change_24h', 0)
            
            if change_24h > 0.05:  # 5% 이상 상승
                return "강한 상승 트렌드"
            elif change_24h > 0.02:  # 2% 이상 상승
                return "상승 트렌드"
            elif change_24h > -0.02:  # -2% ~ 2%
                return "횡보"
            elif change_24h > -0.05:  # -5% ~ -2%
                return "하락 트렌드"
            else:
                return "강한 하락 트렌드"
                
        except Exception:
            return "분석 불가"
    
    def _analyze_volume(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """거래량 분석"""
        try:
            volume_24h = market_data.get('volume_24h', 0)
            
            # 평균 거래량 대비 분석 (임시로 고정값 사용)
            avg_volume = 50000  # BTC 기준
            volume_ratio = volume_24h / avg_volume if avg_volume > 0 else 0
            
            if volume_ratio > 2.0:
                volume_status = "매우 높음"
            elif volume_ratio > 1.5:
                volume_status = "높음"
            elif volume_ratio > 0.8:
                volume_status = "보통"
            else:
                volume_status = "낮음"
            
            return {
                'volume_24h': volume_24h,
                'volume_ratio': volume_ratio,
                'status': volume_status
            }
            
        except Exception:
            return {'status': '분석 불가'}
    
    def _calculate_volatility(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """변동성 계산"""
        try:
            high_24h = market_data.get('high_24h', 0)
            low_24h = market_data.get('low_24h', 0)
            current_price = market_data.get('current_price', 0)
            
            if current_price > 0:
                volatility = ((high_24h - low_24h) / current_price) * 100
                
                if volatility > 10:
                    volatility_level = "매우 높음"
                elif volatility > 5:
                    volatility_level = "높음"
                elif volatility > 2:
                    volatility_level = "보통"
                else:
                    volatility_level = "낮음"
                
                return {
                    'volatility_percent': volatility,
                    'level': volatility_level,
                    'high_24h': high_24h,
                    'low_24h': low_24h
                }
            
        except Exception:
            pass
            
        return {'level': '분석 불가'}
    
    async def _find_support_resistance(self) -> Dict[str, Any]:
        """지지/저항선 찾기"""
        try:
            current_price = await self._get_current_price()
            
            if current_price:
                # 간단한 지지/저항선 계산
                support = current_price * 0.95  # 현재가의 95%
                resistance = current_price * 1.05  # 현재가의 105%
                
                return {
                    'support': support,
                    'resistance': resistance,
                    'current_price': current_price
                }
                
        except Exception as e:
            self.logger.warning(f"지지/저항선 계산 실패: {str(e)}")
            
        return {}
    
    def _analyze_sentiment(self, market_data: Dict[str, Any]) -> str:
        """시장 심리 분석"""
        try:
            change_24h = market_data.get('change_24h', 0)
            volume_analysis = self._analyze_volume(market_data)
            
            # 가격 변동과 거래량을 종합한 심리 분석
            if change_24h > 0.03 and volume_analysis.get('volume_ratio', 0) > 1.5:
                return "매우 낙관적"
            elif change_24h > 0.01:
                return "낙관적"
            elif change_24h > -0.01:
                return "중립적"
            elif change_24h > -0.03:
                return "비관적"
            else:
                return "매우 비관적"
                
        except Exception:
            return "분석 불가"
    
    def _create_prediction_prompt(self, market_data: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        """AI 예측을 위한 프롬프트 생성"""
        return f"""
다음 비트코인 시장 데이터와 기술적 분석을 바탕으로 향후 24시간 예측을 제공해주세요:

**현재 시장 상황:**
- 현재 가격: ${market_data.get('current_price', 'N/A'):,}
- 24시간 변동: {market_data.get('change_24h', 0):.2%}
- 거래량: {market_data.get('volume_24h', 'N/A')} BTC

**기술적 분석:**
- 가격 트렌드: {analysis.get('price_trend', 'N/A')}
- 거래량 상태: {analysis.get('volume_analysis', {}).get('status', 'N/A')}
- 변동성: {analysis.get('volatility', {}).get('level', 'N/A')}
- 시장 심리: {analysis.get('market_sentiment', 'N/A')}

다음 요소들을 포함해서 분석해주세요:
1. 단기 가격 전망 (24시간)
2. 주요 위험 요소
3. 거래 시 주의사항
4. 신뢰도 평가

간결하고 명확하게 한국어로 답변해주세요.
"""
    
    def _calculate_confidence(self, analysis: Dict[str, Any]) -> str:
        """예측 신뢰도 계산"""
        try:
            complete_factors = 0
            total_factors = 5
            
            if analysis.get('price_trend') and analysis['price_trend'] != '분석 불가':
                complete_factors += 1
            if analysis.get('volume_analysis', {}).get('status') != '분석 불가':
                complete_factors += 1
            if analysis.get('volatility', {}).get('level') != '분석 불가':
                complete_factors += 1
            if analysis.get('support_resistance'):
                complete_factors += 1
            if analysis.get('market_sentiment') != '분석 불가':
                complete_factors += 1
            
            confidence_ratio = complete_factors / total_factors
            
            if confidence_ratio >= 0.8:
                return "높음"
            elif confidence_ratio >= 0.6:
                return "보통"
            else:
                return "낮음"
                
        except Exception:
            return "낮음"
    
    def _assess_risk_level(self, market_data: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        """위험 수준 평가"""
        try:
            volatility_level = analysis.get('volatility', {}).get('level', '')
            volume_ratio = analysis.get('volume_analysis', {}).get('volume_ratio', 0)
            change_24h = abs(market_data.get('change_24h', 0))
            
            risk_score = 0
            
            # 변동성 기반 위험도
            if volatility_level == "매우 높음":
                risk_score += 3
            elif volatility_level == "높음":
                risk_score += 2
            elif volatility_level == "보통":
                risk_score += 1
            
            # 거래량 기반 위험도
            if volume_ratio > 3:
                risk_score += 2
            elif volume_ratio > 2:
                risk_score += 1
            
            # 가격 변동 기반 위험도
            if change_24h > 0.1:  # 10% 이상
                risk_score += 3
            elif change_24h > 0.05:  # 5% 이상
                risk_score += 2
            elif change_24h > 0.02:  # 2% 이상
                risk_score += 1
            
            if risk_score >= 6:
                return "매우 높음"
            elif risk_score >= 4:
                return "높음"
            elif risk_score >= 2:
                return "보통"
            else:
                return "낮음"
                
        except Exception:
            return "보통"
    
    def _get_recommendation(self, analysis: Dict[str, Any]) -> str:
        """투자 추천 생성"""
        try:
            price_trend = analysis.get('price_trend', '')
            volatility_level = analysis.get('volatility', {}).get('level', '')
            market_sentiment = analysis.get('market_sentiment', '')
            
            if '강한 상승' in price_trend and market_sentiment in ['매우 낙관적', '낙관적']:
                return "매수 고려 (단, 리스크 관리 필수)"
            elif '강한 하락' in price_trend and market_sentiment in ['매우 비관적', '비관적']:
                return "매도 고려 또는 관망"
            elif volatility_level in ['매우 높음', '높음']:
                return "관망 권장 (높은 변동성)"
            elif '횡보' in price_trend:
                return "관망 또는 소량 분할 매수"
            else:
                return "신중한 접근 권장"
                
        except Exception:
            return "신중한 접근 권장"
