from modules.bitget_api import fetch_position

if __name__ == "__main__":
    print("🚀 시스템 시작됨")
    try:
        data = fetch_position()
        print("📡 Bitget API 응답 원문:", data)
    except Exception as e:
        print("❗ Bitget API 호출 중 오류 발생:", str(e))
