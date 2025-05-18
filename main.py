from modules.report import generate_report
from modules.telegram import send_report

if __name__ == "__main__":
    # 테스트 명령어: "/report", "/forecast", "/profit", "/schedule"
    command = "/report"
    report = generate_report(command)
    send_report(report)