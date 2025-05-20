import pytz
from datetime import datetime

def kr_now_str():
    return datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
