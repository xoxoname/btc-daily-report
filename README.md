# 비트코인 자동 예측 봇

## 설치 및 배포

1. 이 저장소를 Render에 업로드(또는 직접 서버에 복사)
2. `.env.example` 파일을 참고해 Render/서버 환경변수에 키 입력
3. 빌드 커맨드: `pip install -r requirements.txt`
4. 실행 커맨드: `python app.py`

## 환경변수(반드시 Render/서버에 설정)
- BITGET_APIKEY
- BITGET_APISECRET
- BITGET_PASSPHRASE
- OPENAI_API_KEY
- PERPLEXITY_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID (1038440081)

## 주요 기능
- 09:00/13:00/17:00/23:00(KST) 자동 리포트
- 실시간 시장 데이터 수집 (Bitget)
- GPT-4o 및 Perplexity pplx-api 기반 예측/분석
- 텔레그램 알림 발송

## Perplexity pplx-api 연동 예시
- pplx-api 키는 반드시 환경변수(PERPLEXITY_API_KEY)로 관리
- Python 예제는 `modules/perplexity.py` 참고  
- 공식 가이드: https://www.perplexity.ai/ko/hub/blog/introducing-pplx-api
