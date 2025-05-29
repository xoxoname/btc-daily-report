# report_generators/exception_report.py
from .base_generator import BaseReportGenerator
from typing import Dict
from datetime import datetime
import pytz

class ExceptionReportGenerator(BaseReportGenerator):
    """예외 상황 리포트 전담 생성기"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
    
    async def generate_report(self, event: Dict) -> str:
        """🚨 긴급 예외 리포트 생성"""
        current_time = self._get_current_time_kst()
        
        # 원인 요약
        cause_summary = self._format_exception_cause(event)
        
        # GPT 분석
        gpt_analysis = await self._generate_exception_analysis(event)
        
        # 리스크 대응 - 동적 생성
        risk_strategy = await self._format_dynamic_risk_strategy(event)
        
        # 탐지 조건
        detection_conditions = self._format_detection_conditions(event)
        
        report = f"""🚨 BTC 긴급 예외 리포트
📅 발생 시각: {current_time} (KST)
━━━━━━━━━━━━━━━━━━━

❗ **급변 원인 요약**
{cause_summary}

━━━━━━━━━━━━━━━━━━━

📌 **GPT 분석 및 판단**
{gpt_analysis}

━━━━━━━━━━━━━━━━━━━

🛡️ **리스크 대응 전략 제안**
{risk_strategy}

━━━━━━━━━━━━━━━━━━━

📌 **탐지 조건 만족 내역**
{detection_conditions}

━━━━━━━━━━━━━━━━━━━

🧭 **참고**
- 이 리포트는 정규 리포트 외 탐지 조건이 충족될 경우 즉시 자동 생성됩니다."""
        
        return report
    
    def _format_exception_cause(self, event: Dict) -> str:
        """예외 원인 포맷팅 - 시간 추가"""
        event_type = event.get('type', 'unknown')
        kst = pytz.timezone('Asia/Seoul')
        
        # 이벤트 시간 처리
        try:
            if isinstance(event.get('timestamp'), datetime):
                event_time = event['timestamp'].astimezone(kst)
            elif event.get('published_at'):
                from dateutil import parser
                event_time = parser.parse(event['published_at']).astimezone(kst)
            else:
                event_time = datetime.now(kst)
            
            time_str = event_time.strftime('%m-%d %H:%M')
        except:
            time_str = datetime.now(kst).strftime('%m-%d %H:%M')
        
        if event_type == 'price_anomaly':
            change = event.get('change_24h', 0) * 100
            price = event.get('current_price', 0)
            return f"""• {time_str} 비트코인 가격 {abs(change):.1f}% {'급등' if change > 0 else '급락'}
- 현재가: ${price:,.0f}
- 직후 {'매수' if change > 0 else '매도'}세 집중 현상 관측"""
        
        elif event_type == 'volume_anomaly':
            volume = event.get('volume_24h', 0)
            ratio = event.get('ratio', 0)
            return f"""• {time_str} 24시간 거래량 급증: {volume:,.0f} BTC
- 평균 대비 {ratio:.1f}배 증가
- 대량 거래 감지로 인한 유동성 변화"""
        
        elif event_type == 'funding_rate_anomaly':
            rate = event.get('funding_rate', 0)
            annual = event.get('annual_rate', 0) * 100
            return f"""• {time_str} 펀딩비 이상 급등: {rate:.4f}%
- 연환산 {annual:+.1f}% 수준
- 롱/숏 불균형 심화로 인한 시장 왜곡"""
        
        elif event_type == 'critical_news':
            title = event.get('title', '')
            impact = event.get('impact', '')
            
            # 한글 제목 우선 사용
            if 'title_ko' in event:
                title = event['title_ko']
            
            return f"""• {time_str} "{title}"
- 예상 영향: {impact}
- 직후 시장 반응 및 심리 변화 감지"""
        
        else:
            # 기본 포맷
            return f"""• {time_str} {event.get('description', '이상 징후 감지')}
- {event.get('impact', '시장 영향 분석 중')}"""
    
    async def _generate_exception_analysis(self, event: Dict) -> str:
        """예외 분석 생성"""
        if self.openai_client:
            try:
                # 이벤트 정보 정리
                event_info = {
                    'type': event.get('type', 'unknown'),
                    'severity': event.get('severity', 'medium'),
                    'title': event.get('title', ''),
                    'impact': event.get('impact', ''),
                    'description': event.get('description', '')
                }
                
                # 비트코인 관련성 확인
                is_bitcoin_related = any(
                    keyword in str(event_info).lower() 
                    for keyword in ['bitcoin', 'btc', '비트코인', 'crypto', '암호화폐']
                )
                
                if not is_bitcoin_related and event_info['type'] != 'critical_news':
                    return "• 비트코인과 직접적 관련성이 낮은 이벤트입니다."
                
                prompt = f"""
비트코인 시장에서 다음 예외 상황이 발생했습니다:

이벤트: {event_info['title'] or event_info['type']}
심각도: {event_info['severity']}
영향: {event_info['impact']}
설명: {event_info['description']}

이 상황에 대한 전문적인 분석을 제공해주세요:
1. 즉각적인 시장 영향 (롱/숏 어느쪽이 유리한지)
2. 향후 2-4시간 예상 시나리오
3. 투자자 대응 방안

간결하고 명확하게 한국어로 작성해주세요. 3-4줄로 요약하세요.
반드시 롱/숏 중 명확한 방향성을 제시하세요.
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "당신은 명확한 방향성을 제시하는 긴급 상황 암호화폐 분석가입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.5
                )
                
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                self.logger.error(f"GPT 예외 분석 생성 실패: {e}")
        
        # 폴백 분석
        event_type = event.get('type', 'unknown')
        impact = event.get('impact', '')
        
        if event_type == 'critical_news':
            if '호재' in impact:
                return """• 긍정적 뉴스로 단기 상승 압력 증가
- 매수세 유입으로 향후 2-4시간 내 추가 상승 예상
- 롱 포지션 유리, 저항선 돌파 시 추가 매수 고려
※ 과열 구간 진입 시 분할 익절 필수"""
            elif '악재' in impact:
                return """• 부정적 뉴스로 단기 하락 압력 증가
- 매도세 증가로 향후 2-4시간 내 추가 하락 예상
- 숏 포지션 유리, 지지선 이탈 시 추가 매도 고려
※ 과매도 구간 진입 시 분할 익절 필수"""
            else:
                return """• 뉴스 영향 평가 중, 시장 반응 주시 필요
- 단기적으로 변동성 확대 예상
- 방향성 확인 후 진입 권장
※ 가짜 돌파/이탈 주의"""
        
        elif event_type == 'price_anomaly':
            change = event.get('change_24h', 0)
            if change > 0:
                return """• 급격한 가격 상승으로 FOMO 매수세 유입
- 단기 과열 가능성 있으나 추가 상승 모멘텀 존재
- 롱 우세나 진입 시점 신중히 선택
※ 고점 매수 리스크 주의"""
            else:
                return """• 급격한 가격 하락으로 패닉 매도세 확산
- 단기 과매도 가능성 있으나 추가 하락 압력 존재
- 숏 우세나 반등 타이밍 주시
※ 저점 매도 리스크 주의"""
        
        else:
            return """• 비정상적 시장 움직임으로 불확실성 증가
- 추가 변동성 확대 가능성 높음
- 포지션 축소 및 리스크 관리 최우선
※ 명확한 방향성 확인까지 관망"""
    
    async def _format_dynamic_risk_strategy(self, event: Dict) -> str:
        """동적 리스크 전략 생성"""
        severity = event.get('severity', 'medium')
        event_type = event.get('type', 'unknown')
        
        # 계정 정보 가져오기
        try:
            position_info = await self._get_position_info()
            account_info = await self._get_account_info()
            
            has_position = position_info.get('has_position', False)
            total_equity = account_info.get('total_equity', 0)
            
            if severity == 'critical':
                if has_position:
                    side = position_info.get('side', '')
                    unrealized_pnl = position_info.get('unrealized_pnl', 0)
                    leverage = position_info.get('leverage', 1)
                    
                    # 포지션 방향과 이벤트 영향 분석
                    event_impact = event.get('impact', '')
                    
                    if ('호재' in event_impact and side == '롱') or ('악재' in event_impact and side == '숏'):
                        # 유리한 방향
                        if unrealized_pnl > 0:
                            return f"""• 현재 {side} 포지션이 이벤트와 일치 (수익 ${unrealized_pnl:.2f})
- 일부 익절로 원금 확보 후 나머지 홀딩 권장
- 추가 진입은 되돌림 시점에서 소량만
- 레버리지 {leverage}배 유지 또는 축소"""
                        else:
                            return f"""• 현재 {side} 포지션이 이벤트와 일치 (손실 ${abs(unrealized_pnl):.2f})
- 방향은 맞으나 타이밍 아쉬움, 홀딩 권장
- 평단가 개선 위한 추가 매수는 신중히
- 손절선은 기존 계획 유지"""
                    else:
                        # 불리한 방향
                        return f"""• ⚠️ 현재 {side} 포지션이 이벤트와 반대 방향!
- 즉시 포지션 50% 이상 정리 권장
- 남은 포지션은 타이트한 손절 설정
- 반대 방향 진입은 추세 확인 후"""
                else:
                    # 포지션 없을 때
                    if total_equity > 0:
                        if '호재' in event.get('impact', ''):
                            recommended_size = min(total_equity * 0.3, 1000)  # 최대 30% 또는 $1000
                            return f"""• 강한 상승 신호, 롱 진입 기회
- 권장 진입 규모: ${recommended_size:.0f} (총 자산의 {recommended_size/total_equity*100:.0f}%)
- 레버리지는 3배 이하로 제한
- 분할 진입으로 리스크 분산"""
                        elif '악재' in event.get('impact', ''):
                            recommended_size = min(total_equity * 0.3, 1000)
                            return f"""• 강한 하락 신호, 숏 진입 기회
- 권장 진입 규모: ${recommended_size:.0f} (총 자산의 {recommended_size/total_equity*100:.0f}%)
- 레버리지는 3배 이하로 제한
- 분할 진입으로 리스크 분산"""
                        else:
                            return f"""• 방향성 불명확, 관망 권장
- 총 자산 ${total_equity:.0f} 보존 우선
- 명확한 방향 확인 후 진입
- 진입 시 자산의 10-15%만 사용"""
                    else:
                        return self._get_fallback_risk_strategy(severity, event_type)
            else:
                # severity가 critical이 아닌 경우
                if has_position:
                    return f"""• 현재 포지션 점검 및 리스크 관리
- 손절선 재확인 및 필요시 조정
- 추가 진입보다는 기존 포지션 관리 집중
- 변동성 확대에 대비한 증거금 여유 확보"""
                else:
                    return f"""• 시장 변동성 증가, 신중한 접근 필요
- 소량 테스트 포지션으로 시작
- 명확한 방향성 확인 후 본격 진입
- 리스크 관리 최우선"""
                    
        except Exception as e:
            self.logger.error(f"동적 리스크 전략 생성 실패: {e}")
            return self._get_fallback_risk_strategy(severity, event_type)
    
    def _get_fallback_risk_strategy(self, severity: str, event_type: str) -> str:
        """폴백 리스크 전략"""
        if severity == 'critical':
            if event_type == 'critical_news':
                return """• 모든 레버리지 포지션 즉시 점검
- 뉴스 방향성과 반대 포지션은 즉시 청산 검토
- 신규 진입은 변동성 안정화까지 대기
- 현물 보유자는 일부 헤지 고려"""
            else:
                return """• 레버리지 포지션 보유 시: 즉시 포지션 축소 또는 청산 검토
- 현물 보유자는 일부 매도 후 하락 시 재진입 준비
- 신규 진입 시 소량 분할 매수로 리스크 분산
- 손절선 엄격 준수 및 감정적 거래 금지"""
        else:
            return """• 레버리지 포지션 보유 시: 청산가와 거리 확인 필수
- 현물 보유자는 분할 매수 재진입 준비
- 고배율 진입자는 즉시 포지션 축소 또는 정리 권고
- 단기 변동성 활용보다는 리스크 관리 우선"""
    
    def _format_detection_conditions(self, event: Dict) -> str:
        """탐지 조건 포맷팅"""
        event_type = event.get('type', 'unknown')
        
        conditions = []
        
        if event_type == 'price_anomaly':
            change = event.get('change_24h', 0) * 100
            conditions.append(f"• 📉 **단기 변동 급등락**: 최근 30분 간 {abs(change):.1f}% 변동 → {'➕호재 예상 (매수세 급증)' if change > 0 else '➖악재 예상 (매도세 급증)'}")
        
        if event_type == 'volume_anomaly':
            ratio = event.get('ratio', 0)
            conditions.append(f"• 📊 **거래량 급증**: 평균 대비 {ratio:.1f}배 증가 → 대규모 포지션 변화")
        
        if event_type == 'funding_rate_anomaly':
            rate = event.get('funding_rate', 0)
            conditions.append(f"• 💰 **펀딩비 이상**: {rate:+.4f}% 돌파 → {'롱 과열' if rate > 0 else '숏 과열'}")
        
        if event_type == 'critical_news':
            impact = event.get('impact', '중립')
            conditions.append(f"• 📰 **중요 뉴스 발생**: {event.get('title', '')[:50]}... → {impact}")
        
        # 추가 일반 조건들
        if event.get('smart_money_alert'):
            conditions.append("• 🐋 **고래 이동 감지**: 대량 거래소 유입/유출")
        
        if event.get('liquidation_alert'):
            conditions.append("• 💥 **대량 청산 감지**: 연쇄 청산 위험")
        
        if len(conditions) < 3:
            conditions.append("• 🧠 **심리 지표 급변**: 시장 센티먼트 급속 변화")
        
        return '\n'.join(conditions[:4])  # 최대 4개만 표시
