from datetime import datetime
import pytz

def kr_now_str():
    return datetime.now(pytz.timezone('Asia/Seoul')).strftime("%Y-%m-%d %H:%M:%S")
