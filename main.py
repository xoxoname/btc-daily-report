from modules.telegram_bot import run_telegram_bot
from modules.schedule import start_schedulers

if __name__ == "__main__":
    run_telegram_bot()      # run_polling()은 동기함수라 바로 실행
    # start_schedulers()     # (만약 스케줄도 돌리면 아래 참고)
