from datetime import datetime, timedelta
import pytz

def get_kst_now():
    return datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Seoul'))

def parse_command(text):
    if text.startswith("/"):
        return text.strip().split()[0]
    return ""

def generate_schedule_message():
    now = get_kst_now()
    date_str = now.strftime("%Y년 %m월 %d일")
    return (
        f"📅 향후 7일간 주요 일정 (/일정 명령어 예시)\n"
        f"기준 날짜: {date_str} (KST 기준)\n"
        "\n"
        "날짜 (KST) | 이벤트 | 예상 영향\n"
        "-----------|--------|-------------\n"
        "5월 17일 | 트럼프 대통령의 암호화폐 연설 | 시장에 긍정적 신호 제공 가능성\n"
        "5월 20일 | 연준의 금리 결정 발표 | 시장 변동성 증가 예상\n"
        "5월 22일 | 미국-중국 무역 협상 회담 | 시장 안정성에 영향 가능성\n"
        "5월 25일 | 비트코인 관련 국제 컨퍼런스 | 시장 관심도 증가 예상\n"
        "\n"
        "이러한 일정들은 비트코인 시장에 직접적인 영향을 미칠 수 있으므로, 주의 깊게 관찰하시기 바랍니다."
    )
