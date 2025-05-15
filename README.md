# BTC Daily Report System

This service provides:

- 🔄 Real-time PnL monitoring via Bitget API
- 📊 BTC movement prediction report using OpenAI
- 📡 Emergency detection for BTC price fluctuations
- ⏰ Automatic scheduled reports at 09:00, 13:00, 23:00 KST

## Telegram Bot Commands

- `/수익`: 현재 포지션 및 수익률 조회
- `/예측`: 심층 분석 기반 예측 보고서 전송
- `/리포트`: 실시간 정규 리포트 수동 전송
- `/일정`: 정규 보고 일정 확인

## Deploy & Run

1. Set the following environment variables on Render:
   - `BITGET_APIKEY`, `BITGET_SECRETKEY`, `BITGET_PASSPHRASE`
   - `OPENAI_API_KEY`
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`

2. Deploy via GitHub to Render using **Web Service** mode.

3. System will auto-start with full monitoring and Telegram interaction.
