# BTC Daily Report Bot

비트코인 실시간 수익/예측/일정 리포트를 텔레그램으로 자동 전송하는 시스템입니다.

## 명령어
- `/수익`: 현재 포지션, 수익률, 총 수익 등 실시간 수익 리포트 제공
- `/예측`: 심층 분석 기반 12시간 예측 리포트 제공
- `/리포트`: GPT 기반 정규 리포트 (뉴스/온체인/기술적 지표/심리 등 포함)
- `/일정`: 향후 7일간 비트코인 관련 주요 일정 및 영향 요약

## 환경변수 설정
Render.com의 Environment Variables에 아래 항목을 등록:
- TELEGRAM_TOKEN
- TELEGRAM_CHAT_ID
- OPENAI_API_KEY
- BITGET_APIKEY
- BITGET_APISECRET
- BITGET_PASSPHRASE
