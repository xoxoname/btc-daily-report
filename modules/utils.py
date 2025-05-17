# Utilities
from datetime import datetime

def get_now_kst():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M (KST 기준)')
