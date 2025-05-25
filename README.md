# 📘 비트코인 자동 선물 예측 시스템

GPT 기반 비트코인 선물 자동 분석 및 예측 시스템입니다.

## 🎯 주요 기능

- **자동 분석 리포트**: 매일 4회 (09:00, 13:00, 17:00, 23:00 KST) 자동 분석 리포트 생성
- **실시간 예외 감지**: 5분마다 가격 급변동, 대량 거래 등 예외 상황 감지
- **텔레그램 봇**: 명령어 및 자연어 질의응답 지원
- **GPT 분석**: OpenAI GPT를 활용한 시장 분석 및 예측
- **Bitget API 연동**: 실시간 시장 데이터 및 포지션 정보 수집

## 📋 지원 명령어

### 슬래시 명령어
- `/report` - 전체 분석 리포트
- `/forecast` - 단기 예측 요약  
- `/profit` - 수익 현황
- `/schedule` - 자동 일정 안내

### 자연어 명령어
- "지금 매수해야 돼?"
- "얼마 벌었어?"
- "오늘 수익은?"
- "시장 상황 어때?"

## 🚀 배포 방법

### 1. 환경변수 설정

Render 대시보드에서 다음 환경변수를 설정하세요:

```
BITGET_APIKEY=your_bitget_api_key
BITGET_APISECRET=your_bitget_api_secret  
BITGET_PASSPHRASE=your_bitget_passphrase
OPENAI_API_KEY=your_openai_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=1038440081
```

### 2. GitHub 레포지토리 생성

1. 이 코드를 GitHub 레포지토리에 업로드
2. Render에서 레포지토리 연결
3. Worker 서비스로 배포

### 3. Render 설정

- **Service Type**: Background Worker
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python main.py`
- **Plan**: Starter (무료) 또는 상위 플랜

## 📁 프로젝트 구조

```
bitcoin-prediction-system/
├── main.py                 # 메인 애플리케이션
├── config.py              # 설정 관리
├── telegram_bot.py        # 텔레그램 봇
├── bitget_client.py       # Bitget API 클라이언트
├── analysis_engine.py     # GPT 분석 엔진
├── exception_detector.py  # 예외 상황 감지
├── requirements.txt       # Python 의존성
├── Dockerfile            # 컨테이너 설정
├── render.yaml           # Render 배포 설정
└── README.md             # 프로젝트 설명서
```

## 🔧 설정 방법

### Bitget API 설정
1. Bitget 계정 생성 및 API 키 발급
2. 선물 거래 권한 활성화
3. API 키, 시크릿, 패스프레이즈 환경변수 설정

### OpenAI API 설정  
1. OpenAI 계정 생성 및 API 키 발급
2. GPT-4 접근 권한 확인
3. API 키 환경변수 설정

### 텔레그램 봇 설정
1. @BotFather에서 새 봇 생성
2. 봇 토큰 발급
3. 채팅 ID 확인 및 설정

## 📊 분석 항목

### 기술적 분석
- RSI, 볼린저밴드, 이동평균
- 지지/저항선 분석
- 가격 패턴 인식

### 심리적 분석
- 펀딩비 분석
- 미결제약정 변화
- 공포탐욕지수

### 구조적 분석
- 거래량 분석
- 온체인 데이터
- 시장 지배력

## 🚨 예외 상황 감지

- **가격 급변동**: 2% 이상 변동 시 알림
- **거래량 급증**: 평균 대비 3배 이상 시 알림  
- **펀딩비 이상**: 0.02% 이상 시 알림
- **주요 이벤트**: FOMC 등 경제 이벤트 전 알림

## 📈 리포트 형식

모든 리포트는 한국어로 제공되며, 다음 정보를 포함합니다:

- 시장 이벤트 및 속보
- 기술적 분석 결과
- 심리·구조적 분석
- 향후 12시간 예측
- 수익 현황
- 멘탈 케어 코멘트

## 🔄 자동 스케줄

- **정규 리포트**: 09:00, 13:00, 17:00, 23:00 (한국시간)
- **예외 감지**: 5분마다 자동 스캔
- **긴급 알림**: 조건 만족 시 즉시 발송

## ⚠️ 주의사항

- 이 시스템은 참고용이며, 투자 결정에 대한 책임은 사용자에게 있습니다
- API 키는 반드시 안전하게 관리하세요
- 레버리지 거래는 높은 위험을 수반합니다

## 🛠️ 기술 스택

- **Python 3.11**
- **AsyncIO**: 비동기 처리
- **APScheduler**: 스케줄링
- **python-telegram-bot**: 텔레그램 봇
- **OpenAI**: GPT 분석
- **aiohttp**: HTTP 클라이언트
- **Render**: 배포 플랫폼

## 📞 지원

시스템 관련 문의나 오류 신고는 텔레그램을 통해 연락주세요.
