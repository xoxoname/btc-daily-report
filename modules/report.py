# modules/schedule.py

import requests
from datetime import datetime, timedelta
import pytz

def get_upcoming_events():
    """
    향후 1주일간의 BTC/미경제 지표 일정을 가져옵니다.
    실제 환경에서는 공신력 있는 경제 캘린더 API를 호출하도록 구현하세요.
    """
    kst = pytz.timezone("Asia/Seoul")
    today = datetime.now(kst)
    week_later = today + timedelta(days=7)

    # TODO: 여기에 진짜 API 호출 로직을 넣으세요.
    # 아래는 예시 더미 데이터입니다.
    events = [
        {"time": (today + timedelta(days=1)).strftime("%Y-%m-%d 21:30"), "event": "미국 CPI 발표",     "impact": "높음"},
        {"time": (today + timedelta(days=2)).strftime("%Y-%m-%d 22:00"), "event": "FOMC 의사록 공개",   "impact": "중간"},
        {"time": (today + timedelta(days=3)).strftime("%Y-%m-%d 20:00"), "event": "BTC 주요 온체인 지표", "impact": "낮음"},
        # ...
    ]
    return events

def format_schedule_text(events):
    """get_upcoming_events() 결과를 문자열로 포맷팅"""
    lines = ["📅 *향후 1주일 일정*"]
    for e in events:
        lines.append(f"- `{e['time']}`: {e['event']} (영향: {e['impact']})")
    return "\n".join(lines)
