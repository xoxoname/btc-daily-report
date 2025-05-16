# BTC Daily Report Bot

실시간 BTC 수익 및 매매 동향 예측을 텔레그램으로 자동 전달하는 Python 기반 봇입니다.

## 기능
- Coinbase 기준 실시간 BTC 가격 조회
- Bitget API 기반 포지션, 수익률 데이터 분석
- GPT 기반 매매 예측 분석 보고서 전송
- 정해진 시간대마다 자동 전송 (UTC 기준 0:30, 4:00, 14:00)
- 주요 가격 변동 감지 시 자동 경고 메시지 발송

## 명령어
- `/수익`: 현재 포지션 및 수익률 조회
- `/예측`: 심층 분석 기반 예측 보고서 전송
- `/리포트`: 즉시 전체 리포트 전송
- `/일정`: 정규 리포트 전송 시간 확인

## 환경변수
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENAI_API_KEY`

## 실행 방법
```bash
python main.py
