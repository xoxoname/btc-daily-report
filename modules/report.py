from modules.utils import send_telegram_message, get_kst_now

def build_and_send_report():
    now = get_kst_now().strftime('%Y-%m-%d %H:%M:%S')
    msg = f"📈 정규 BTC 예측 분석 리포트\n\n🕒 {now}\n\n📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다."
    send_telegram_message(msg)
