from datetime import datetime
import pytz

def get_kst_now() -> str:
    kst = pytz.timezone("Asia/Seoul")
    return datetime.now(kst).strftime("%Y-%m-%d %H:%M KST")
