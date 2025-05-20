from datetime import datetime
import pytz

def kr_now():
    tz = pytz.timezone("Asia/Seoul")
    return datetime.now(tz)

def kr_now_str():
    return kr_now().strftime("%Y-%m-%d %H:%M")

def format_number(n, digits=2):
    try:
        return f"{float(n):,.{digits}f}"
    except Exception:
        return str(n)

def usd_to_krw(usd, rate=13300):
    try:
        return int(float(usd) * rate)
    except Exception:
        return 0

def with_krw(usd, digits=1):
    krw = usd_to_krw(usd)
    return f"${format_number(usd, digits)} ({int(krw/10000)}.{int((krw%10000)/1000)}만원)"

def percent(v):
    try:
        return f"{float(v)*100:.2f}%"
    except Exception:
        return str(v)
