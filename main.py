import requests
def print_public_ip():
    try:
        ip = requests.get("https://api.ipify.org", timeout=5).text
        print(f"🌐 Render 서버 퍼블릭 IP: {ip}")
    except:
        print("⚠️ IP 확인 실패")

from modules.report import generate_report
from modules.telegram import send_report

print_public_ip()

if __name__ == "__main__":
    # 테스트 명령어: "/report", "/forecast", "/profit", "/schedule"
    command = "/report"
    report = generate_report(command)
    send_report(report)