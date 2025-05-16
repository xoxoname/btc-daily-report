# BTC Daily Report

비트코인 실시간 수익 분석 및 예측 리포트 자동화 시스템입니다.

## 기능
- Bitget API를 통해 현재 포지션과 수익률 자동 분석
- Coinbase 실시간 가격 기반 수익률 계산
- 텔레그램 봇 명령어:
  - `/수익`: 실시간 수익 리포트
  - `/예측`: 12시간 예측 분석
  - `/리포트`: 정규 리포트 (GPT 기반 분석)
  - `/일정`: 7일 내 주요 경제 일정

## 환경 변수 (.env or Render dashboard)
- `TELEGRAM_TOKEN`: 텔레그램 봇 토큰
- `TELEGRAM_CHAT_ID`: 수신할 텔레그램 ID
- `BITGET_APIKEY`: Bitget API Key
- `BITGET_APISECRET`: Bitget API Secret
- `BITGET_PASSPHRASE`: Bitget Passphrase
- `OPENAI_API_KEY`: GPT 리포트용 키

## 사용 방법
Render에 배포하고 Webhook URL을 다음 형식으로 설정:
