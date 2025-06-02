# report_generators/exception_report.py
from .base_generator import BaseReportGenerator
from typing import Dict
from datetime import datetime
import pytz
import re
import sys
import os

# ML 예측기 임포트
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from ml_predictor import MLPredictor
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

class ExceptionReportGenerator(BaseReportGenerator):
    """예외 상황 리포트 전담 생성기 - 간소화"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        
        # ML 예측기 초기화
        self.ml_predictor = None
        if ML_AVAILABLE:
            try:
                self.ml_predictor = MLPredictor()
                self.logger.info(f"ML 예측기 초기화 완료")
            except Exception as e:
                self.logger.error(f"ML 예측기 초기화 실패: {e}")
    
    async def generate_report(self, event: Dict) -> str:
        """🚨 긴급 예외 리포트 생성 - 상세 정보 포함"""
        current_time = self._get_current_time_kst()
        event_type = event.get('type', 'unknown')
        
        if event_type == 'critical_news':
            # 뉴스 정보
            title = event.get('title', '')
            title_ko = event.get('title_ko', title)
            description = event.get('description', '')
            summary = event.get('summary', '')
            impact = event.get('impact', '')
            expected_change = event.get('expected_change', '')
            source = event.get('source', '')
            published_at = event.get('published_at', '')
            company = event.get('company', '')  # 기업명
            
            # 발행 시각 포맷팅
            pub_time_str = ""
            if published_at:
                try:
                    if 'T' in published_at:
                        pub_time = datetime.fromisoformat(published_at.replace('Z', ''))
                    else:
                        from dateutil import parser
                        pub_time = parser.parse(published_at)
                    
                    if pub_time.tzinfo is None:
                        pub_time = pytz.UTC.localize(pub_time)
                    
                    kst_time = pub_time.astimezone(pytz.timezone('Asia/Seoul'))
                    pub_time_str = kst_time.strftime('%Y-%m-%d %H:%M')
                except:
                    pub_time_str = "시간 정보 없음"
            else:
                pub_time_str = "시간 정보 없음"
            
            # 영향도에 따른 분석
            if '호재' in impact:
                impact_emoji = "📈"
                if '강한' in impact:
                    recommendation = "적극 매수 고려"
                    strategy = "• 분할 매수 추천\n• 목표가: +2~3%\n• 손절가: -1%"
                else:
                    recommendation = "소량 매수 고려"
                    strategy = "• 신중한 진입\n• 목표가: +1~2%\n• 손절가: -0.5%"
            elif '악재' in impact:
                impact_emoji = "📉"
                if '강한' in impact:
                    recommendation = "매도/숏 포지션"
                    strategy = "• 즉시 청산 고려\n• 숏 진입 가능\n• 반등 시 손절"
                else:
                    recommendation = "리스크 관리"
                    strategy = "• 포지션 축소\n• 추가 매수 보류\n• 지지선 확인"
            else:
                impact_emoji = "⚡"
                recommendation = "관망"
                strategy = "• 방향성 확인 대기\n• 소량 거래만\n• 변동성 주의"
            
            # 기업명이 있으면 포함
            company_info = ""
            if company:
                company_info = f"\n🏢 <b>관련 기업</b>: {company}"
            
            # 요약 정보
            summary_info = ""
            if summary and summary != description[:200]:
                summary_info = f"\n\n📝 <b>요약</b>:\n{summary}"
            elif description:
                # description에서 핵심 내용 추출
                desc_summary = description[:300]
                if len(description) > 300:
                    desc_summary += "..."
                summary_info = f"\n\n📝 <b>내용</b>:\n{desc_summary}"
            
            # 리포트 생성
            report = f"""🚨 <b>BTC 긴급 예외 리포트</b>
📅 발행: {pub_time_str}
━━━━━━━━━━━━━━━

{impact_emoji} <b>{title_ko}</b>

📰 <b>원문</b>: {title}{company_info}
📊 <b>영향</b>: {impact}
💹 <b>예상 변동</b>: {expected_change}
📰 <b>출처</b>: {source}{summary_info}

━━━━━━━━━━━━━━━

🎯 <b>추천</b>: {recommendation}

{strategy}

━━━━━━━━━━━━━━━
⏰ {current_time}"""
            
        elif event_type == 'price_anomaly':
            # 가격 이상 징후
            change = event.get('change_24h', 0)
            current_price = event.get('current_price', 0)
            
            if abs(change) >= 0.05:  # 5% 이상
                severity = "급변동"
                emoji = "🚨"
            elif abs(change) >= 0.03:  # 3% 이상
                severity = "주의"
                emoji = "⚠️"
            else:
                severity = "변동"
                emoji = "📊"
            
            direction = "상승" if change > 0 else "하락"
            
            # 추천 전략
            if change > 0.03:
                recommendation = "과열 주의"
                strategy = "• 분할 익절 고려\n• 추격 매수 자제\n• 조정 대기"
            elif change < -0.03:
                recommendation = "반등 대기"
                strategy = "• 분할 매수 준비\n• 지지선 확인\n• 패닉 셀링 자제"
            else:
                recommendation = "추세 관찰"
                strategy = "• 거래량 확인\n• 지표 점검\n• 신중한 접근"
            
            report = f"""🚨 <b>BTC 가격 {severity}</b>
━━━━━━━━━━━━━━━

{emoji} <b>{abs(change*100):.1f}% {direction}</b>

💰 현재가: <b>${current_price:,.0f}</b>
📊 24시간: <b>{change*100:+.1f}%</b>

━━━━━━━━━━━━━━━

🎯 <b>추천</b>: {recommendation}

{strategy}

━━━━━━━━━━━━━━━
⏰ {current_time}"""
            
        elif event_type == 'volume_anomaly':
            # 거래량 이상
            ratio = event.get('ratio', 0)
            volume = event.get('volume_24h', 0)
            
            if ratio >= 5:
                severity = "폭증"
                emoji = "🔥"
                recommendation = "중요 변동 예상"
                strategy = "• 뉴스 확인 필수\n• 포지션 점검\n• 높은 변동성 대비"
            elif ratio >= 3:
                severity = "급증"
                emoji = "📈"
                recommendation = "추세 전환 가능"
                strategy = "• 방향성 확인\n• 분할 진입\n• 거래량 지속성 확인"
            else:
                severity = "증가"
                emoji = "📊"
                recommendation = "관심 필요"
                strategy = "• 시장 모니터링\n• 소량 테스트\n• 추가 신호 대기"
            
            report = f"""🚨 <b>BTC 거래량 {severity}</b>
━━━━━━━━━━━━━━━

{emoji} 평균 대비 <b>{ratio:.1f}배</b>

📊 24시간: <b>{volume:,.0f} BTC</b>
💹 시장 관심 급증

━━━━━━━━━━━━━━━

🎯 <b>추천</b>: {recommendation}

{strategy}

━━━━━━━━━━━━━━━
⏰ {current_time}"""
            
        else:
            # 기타 이벤트
            description = event.get('description', '이상 신호 감지')
            
            report = f"""🚨 <b>BTC 이상 신호</b>
━━━━━━━━━━━━━━━

⚠️ {description}

━━━━━━━━━━━━━━━

🎯 <b>추천</b>: 주의 관찰

- 포지션 점검
- 리스크 관리
- 추가 정보 수집

━━━━━━━━━━━━━━━
⏰ {current_time}"""
        
        return report
    
    # 나머지 메서드들은 사용하지 않으므로 pass 처리
    async def _format_detailed_exception_cause(self, event: Dict) -> str:
        pass
    
    async def _generate_ml_analysis(self, event: Dict) -> str:
        pass
    
    async def _generate_exception_analysis(self, event: Dict) -> str:
        pass
    
    async def _format_dynamic_risk_strategy(self, event: Dict) -> str:
        pass
    
    def _format_detection_conditions(self, event: Dict) -> str:
        pass
    
    def _get_fallback_risk_strategy(self, severity: str, event_type: str) -> str:
        pass
    
    def _get_realistic_fallback_analysis(self, event: Dict) -> str:
        pass
    
    async def _get_market_data_for_ml(self) -> Dict:
        pass
    
    async def _get_position_info(self) -> Dict:
        return {'has_position': False}
    
    async def _get_account_info(self) -> Dict:
        return {'total_equity': 0}
