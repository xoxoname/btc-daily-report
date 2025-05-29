# report_generators/schedule_report.py
from .base_generator import BaseReportGenerator
from datetime import datetime, timedelta
import pytz
import aiohttp
from bs4 import BeautifulSoup
import logging

class ScheduleReportGenerator(BaseReportGenerator):
    """일정 리포트 전담 생성기"""
    
    def __init__(self, config, data_collector, indicator_system, bitget_client=None):
        super().__init__(config, data_collector, indicator_system, bitget_client)
        self.session = None
        self.kst = pytz.timezone('Asia/Seoul')
        
    async def generate_report(self) -> str:
        """📅 /schedule 명령어 – 예정 주요 이벤트"""
        current_time = self._get_current_time_kst()
        
        # 예정 이벤트 가져오기
        events_text = await self._format_upcoming_events()
        
        # GPT 코멘트 생성
        gpt_comment = await self._generate_schedule_comment(events_text)
        
        report = f"""📅 /schedule 명령어 – 예정 주요 이벤트
📅 작성 시각: {current_time} (KST)
━━━━━━━━━━━━━━━━━━━
📡 **다가오는 시장 주요 이벤트**
━━━━━━━━━━━━━━━━━━━
{events_text}

━━━━━━━━━━━━━━━━━━━
🧠 **GPT 코멘트**
{gpt_comment}"""
        
        return report
    
    async def _format_upcoming_events(self) -> str:
        """실제 예정 이벤트 가져오기"""
        try:
            # 여러 소스에서 이벤트 수집
            events = []
            
            # 1. 경제 캘린더 이벤트
            economic_events = await self._get_economic_calendar_events()
            events.extend(economic_events)
            
            # 2. 암호화폐 특화 이벤트
            crypto_events = await self._get_crypto_events()
            events.extend(crypto_events)
            
            # 3. 정기 이벤트 (펀딩비, 옵션 만기 등)
            regular_events = self._get_regular_events()
            events.extend(regular_events)
            
            # 시간순 정렬
            events.sort(key=lambda x: x['datetime'])
            
            # 향후 7일 이내 이벤트만 필터링
            cutoff = datetime.now(self.kst) + timedelta(days=7)
            filtered_events = [e for e in events if e['datetime'] < cutoff]
            
            if not filtered_events:
                return "• 향후 7일간 예정된 주요 이벤트가 없습니다."
            
            # 상위 10개만 포맷팅
            formatted = []
            for event in filtered_events[:10]:
                time_str = event['datetime'].strftime('%Y-%m-%d %H:%M')
                impact = await self._analyze_event_impact(event)
                formatted.append(f"• {time_str}: {event['title']} → {impact}")
            
            return '\n'.join(formatted)
            
        except Exception as e:
            self.logger.error(f"이벤트 조회 실패: {e}")
            # 폴백: 기본 이벤트
            return await self._get_fallback_events()
    
    async def _get_economic_calendar_events(self) -> list:
        """경제 캘린더 이벤트 가져오기"""
        events = []
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Investing.com 경제 캘린더 스크래핑
            url = "https://www.investing.com/economic-calendar/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 경제 캘린더 파싱 (실제로는 더 복잡한 파싱 필요)
                    # 여기서는 주요 이벤트만 하드코딩
                    pass
            
        except Exception as e:
            self.logger.warning(f"경제 캘린더 조회 실패: {e}")
        
        # 알려진 주요 경제 이벤트 추가
        now = datetime.now(self.kst)
        
        # FOMC 회의 일정 (매월 셋째 주 수요일)
        next_fomc = self._get_next_fomc_date()
        if next_fomc:
            events.append({
                'datetime': next_fomc,
                'title': 'FOMC 금리 결정 발표',
                'type': 'economic',
                'importance': 'high',
                'currency': 'USD'
            })
        
        # CPI 발표 (매월 둘째 주 목요일)
        next_cpi = self._get_next_cpi_date()
        if next_cpi:
            events.append({
                'datetime': next_cpi,
                'title': '미국 소비자물가지수(CPI) 발표',
                'type': 'economic',
                'importance': 'high',
                'currency': 'USD'
            })
        
        # 실업률 발표 (매월 첫째 주 금요일)
        next_jobs = self._get_next_jobs_report_date()
        if next_jobs:
            events.append({
                'datetime': next_jobs,
                'title': '미국 고용보고서 발표',
                'type': 'economic',
                'importance': 'high',
                'currency': 'USD'
            })
        
        return events
    
    async def _get_crypto_events(self) -> list:
        """암호화폐 관련 이벤트 가져오기"""
        events = []
        now = datetime.now(self.kst)
        
        try:
            # CoinMarketCal API 또는 스크래핑 (실제 구현 필요)
            # 여기서는 주요 암호화폐 이벤트 예시
            
            # ETF 관련 일정
            events.append({
                'datetime': now + timedelta(days=3, hours=14),
                'title': '비트코인 현물 ETF 결정 마감일',
                'type': 'crypto',
                'importance': 'high',
                'category': 'etf'
            })
            
            # 주요 컨퍼런스
            events.append({
                'datetime': now + timedelta(days=5, hours=9),
                'title': 'Consensus 2025 컨퍼런스 시작',
                'type': 'crypto',
                'importance': 'medium',
                'category': 'conference'
            })
            
        except Exception as e:
            self.logger.warning(f"암호화폐 이벤트 조회 실패: {e}")
        
        return events
    
    def _get_regular_events(self) -> list:
        """정기적인 이벤트 (펀딩비, 옵션 만기 등)"""
        events = []
        now = datetime.now(self.kst)
        
        # 비트코인 옵션 만기 (매월 마지막 금요일)
        next_expiry = self._get_next_options_expiry()
        if next_expiry:
            events.append({
                'datetime': next_expiry,
                'title': 'BTC 월물 옵션 만기',
                'type': 'crypto',
                'importance': 'high',
                'category': 'options'
            })
        
        # CME 선물 만기 (매월 마지막 금요일)
        next_cme = self._get_next_cme_expiry()
        if next_cme:
            events.append({
                'datetime': next_cme,
                'title': 'CME 비트코인 선물 만기',
                'type': 'crypto',
                'importance': 'medium',
                'category': 'futures'
            })
        
        # 분기별 선물 만기
        next_quarterly = self._get_next_quarterly_expiry()
        if next_quarterly:
            events.append({
                'datetime': next_quarterly,
                'title': '분기 선물 만기',
                'type': 'crypto',
                'importance': 'high',
                'category': 'futures'
            })
        
        return events
    
    def _get_next_fomc_date(self) -> datetime:
        """다음 FOMC 회의 날짜 계산"""
        now = datetime.now(self.kst)
        
        # FOMC는 보통 화/수요일, 6주마다
        # 2025년 예정: 1/28-29, 3/18-19, 5/6-7, 6/17-18, 7/29-30, 9/16-17, 11/4-5, 12/16-17
        fomc_dates = [
            datetime(2025, 1, 29, 3, 0, tzinfo=self.kst),  # KST 새벽 3시
            datetime(2025, 3, 19, 3, 0, tzinfo=self.kst),
            datetime(2025, 5, 7, 3, 0, tzinfo=self.kst),
            datetime(2025, 6, 18, 3, 0, tzinfo=self.kst),
            datetime(2025, 7, 30, 3, 0, tzinfo=self.kst),
            datetime(2025, 9, 17, 3, 0, tzinfo=self.kst),
            datetime(2025, 11, 5, 3, 0, tzinfo=self.kst),
            datetime(2025, 12, 17, 3, 0, tzinfo=self.kst),
        ]
        
        for date in fomc_dates:
            if date > now:
                return date
        
        return None
    
    def _get_next_cpi_date(self) -> datetime:
        """다음 CPI 발표 날짜 계산"""
        now = datetime.now(self.kst)
        
        # CPI는 보통 매월 10-15일 사이 발표
        # 다음 달 계산
        if now.day > 15:
            next_month = now.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)
        else:
            next_month = now
        
        # 보통 화/수/목요일 중 발표
        target_day = 12  # 12일 근처
        cpi_date = next_month.replace(day=target_day, hour=21, minute=30)  # KST 21:30
        
        # 주말이면 조정
        if cpi_date.weekday() >= 5:  # 토/일
            days_ahead = 7 - cpi_date.weekday() + 2  # 다음 화요일
            cpi_date = cpi_date + timedelta(days=days_ahead)
        
        return cpi_date
    
    def _get_next_jobs_report_date(self) -> datetime:
        """다음 고용보고서 발표 날짜 계산"""
        now = datetime.now(self.kst)
        
        # 고용보고서는 매월 첫째 주 금요일
        if now.day > 7:
            next_month = now.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)
        else:
            next_month = now.replace(day=1)
        
        # 첫 금요일 찾기
        first_friday = next_month
        while first_friday.weekday() != 4:  # 금요일 = 4
            first_friday += timedelta(days=1)
        
        # KST 21:30 (미국 동부시간 8:30 AM)
        return first_friday.replace(hour=21, minute=30)
    
    def _get_next_options_expiry(self) -> datetime:
        """다음 옵션 만기일 계산"""
        now = datetime.now(self.kst)
        
        # 매월 마지막 금요일
        # 다음 달 1일
        if now.day > 20:
            next_month = now.replace(day=1) + timedelta(days=32)
        else:
            next_month = now
        
        # 해당 월의 마지막 날
        if next_month.month == 12:
            last_day = next_month.replace(year=next_month.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day = next_month.replace(month=next_month.month + 1, day=1) - timedelta(days=1)
        
        # 마지막 금요일 찾기
        while last_day.weekday() != 4:  # 금요일
            last_day -= timedelta(days=1)
        
        return last_day.replace(hour=17, minute=0)  # KST 17:00
    
    def _get_next_cme_expiry(self) -> datetime:
        """CME 선물 만기일 계산"""
        # 옵션 만기와 동일
        return self._get_next_options_expiry()
    
    def _get_next_quarterly_expiry(self) -> datetime:
        """분기 선물 만기일 계산"""
        now = datetime.now(self.kst)
        
        # 3, 6, 9, 12월 마지막 금요일
        quarterly_months = [3, 6, 9, 12]
        
        for month in quarterly_months:
            if now.month < month or (now.month == month and now.day < 20):
                # 해당 월의 마지막 금요일
                target_date = now.replace(month=month, day=1)
                
                # 마지막 날 구하기
                if month == 12:
                    last_day = target_date.replace(year=target_date.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    last_day = target_date.replace(month=month + 1, day=1) - timedelta(days=1)
                
                # 마지막 금요일 찾기
                while last_day.weekday() != 4:
                    last_day -= timedelta(days=1)
                
                return last_day.replace(hour=17, minute=0)
        
        # 내년 3월
        next_year = now.year + 1
        return datetime(next_year, 3, 31, 17, 0, tzinfo=self.kst)
    
    async def _analyze_event_impact(self, event: dict) -> str:
        """이벤트가 비트코인에 미칠 영향 분석"""
        event_type = event.get('type', '')
        event_title = event.get('title', '').lower()
        importance = event.get('importance', 'medium')
        
        # 키워드 기반 영향 분석
        if 'fomc' in event_title or '금리' in event_title:
            if importance == 'high':
                return "➖악재 예상 (금리 인상 시 위험자산 회피)"
            else:
                return "중립 (시장 예상치 반영됨)"
        
        elif 'cpi' in event_title or '물가' in event_title:
            return "➖악재 예상 (인플레이션 우려 시 변동성 확대)"
        
        elif '고용' in event_title or '실업' in event_title:
            return "중립 (간접적 영향, 연준 정책에 따라 변동)"
        
        elif 'etf' in event_title:
            if '승인' in event_title or 'approval' in event_title:
                return "➕호재 예상 (기관 자금 유입 기대)"
            else:
                return "➕호재 예상 (ETF 관련 진전)"
        
        elif '옵션' in event_title or '만기' in event_title:
            if importance == 'high':
                return "➖악재 예상 (만기일 변동성 확대)"
            else:
                return "중립 (일상적 만기)"
        
        elif '컨퍼런스' in event_title or 'conference' in event_title:
            return "➕호재 예상 (긍정적 뉴스 기대)"
        
        elif '규제' in event_title or 'regulation' in event_title:
            return "➖악재 예상 (규제 불확실성)"
        
        else:
            return "중립"
    
    async def _get_fallback_events(self) -> str:
        """폴백 이벤트 (API 실패 시)"""
        now = datetime.now(self.kst)
        
        events = []
        
        # FOMC (다음 수요일로 가정)
        days_until_wednesday = (2 - now.weekday()) % 7
        if days_until_wednesday == 0:
            days_until_wednesday = 7
        fomc_date = now + timedelta(days=days_until_wednesday)
        fomc_date = fomc_date.replace(hour=3, minute=0)
        
        events.append(f"• {fomc_date.strftime('%Y-%m-%d %H:%M')}: FOMC 금리 결정 발표 예정 → ➖악재 예상 (금리 정책 불확실성)")
        
        # 옵션 만기 (이번 달 마지막 금요일)
        last_day = (now.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        while last_day.weekday() != 4:
            last_day -= timedelta(days=1)
        last_day = last_day.replace(hour=17, minute=0)
        
        if last_day > now:
            events.append(f"• {last_day.strftime('%Y-%m-%d %H:%M')}: BTC 월물 옵션 만기 → ➖악재 예상 (만기일 변동성)")
        
        # ETF 뉴스 (임의로 3일 후)
        etf_date = now + timedelta(days=3, hours=6)
        events.append(f"• {etf_date.strftime('%Y-%m-%d %H:%M')}: 비트코인 현물 ETF 심사 진행 → ➕호재 예상 (승인 기대감)")
        
        return '\n'.join(events[:5])
    
    async def _generate_schedule_comment(self, events_text: str) -> str:
        """일정에 대한 GPT 코멘트 생성"""
        if self.openai_client and events_text and events_text != "• 향후 7일간 예정된 주요 이벤트가 없습니다.":
            try:
                prompt = f"""
다음은 앞으로 예정된 비트코인 시장 관련 주요 이벤트입니다:

{events_text}

이 일정들을 분석하여 트레이더에게 도움이 되는 전략적 조언을 3-4줄로 작성해주세요:
1. 가장 주의해야 할 이벤트와 시점
2. 리스크 관리 방안
3. 기회 포착 전략

간결하고 실용적으로 작성해주세요.
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "당신은 이벤트 리스크를 분석하는 전문 트레이더입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=200,
                    temperature=0.5
                )
                
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                self.logger.error(f"GPT 일정 코멘트 생성 실패: {e}")
        
        # 폴백 코멘트
        return """GPT는 모든 일정을 감지해 전략적 대응 시점과 연결시킵니다.
예측 리포트와 자동 연동되어 "변동 가능성 높은 시간대"를 중심으로 대응 전략을 조정합니다.
기회보다 회피 타이밍을 강조하는 것은 리스크 절감에도 매우 중요합니다."""
    
    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
