from datetime import datetime, timedelta
import pytz

KST = pytz.timezone("Asia/Seoul")

def now_kst():
    return datetime.now(KST)

def format_usd_krw(usd: float, rate: float = 1350):
    krw = int(usd * rate)
    return f"${usd:,.2f} ≈ {krw//10000}.{(krw%10000)//1000}만 원"

def next_schedule_time():
    now = now_kst()
    base_times = [9, 13, 23]
    for hour in base_times:
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if now < target:
            return target.strftime("%H:%M")
    return now.replace(day=now.day+1, hour=9).strftime("%H:%M")
