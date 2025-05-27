# 📊 비트코인 선물 롱/숏 예측 시스템 v2.0

선물 거래에 특화된 고급 비트코인 분석 및 예측 시스템입니다. 실시간 데이터 분석을 통해 정확한 롱/숏 진입 시점을 제공합니다.

## 🎯 주요 특징

### 선물 거래 특화 지표
- **펀딩비 분석**: 실시간 펀딩비 추적 및 추세 분석
- **미결제약정(OI)**: 포지션 변화와 가격 다이버전스 감지
- **CVD(누적거래량델타)**: 매수/매도 압력 실시간 측정
- **청산 레벨 추적**: 주요 청산 가격대 모니터링
- **롱/숏 비율**: 시장 포지셔닝 분석
- **스마트머니 플로우**: 대형 거래 감지

### 고급 데이터 소스
- **Bitget API**: 선물 가격, 펀딩비, 포지션 데이터
- **CoinGecko**: 시장 전반 데이터, BTC 도미넌스
- **CryptoCompare**: 소셜 메트릭, 거래소 데이터
- **Alternative.me**: Fear & Greed Index
- **RSS 피드**: 15+ 주요 뉴스 소스 실시간 모니터링
- **3개 뉴스 API**: NewsAPI, NewsData, Alpha Vantage

### 인공지능 분석
- **GPT-4 기반**: 시장 상황 종합 분석
- **실시간 뉴스 영향도**: 선물 시장 관점 분석
- **개인화 전략**: 포지션별 맞춤 조언
- **멘탈 케어**: 심리적 지원 및 리스크 관리

## 📁 프로젝트 구조

```
bitcoin-futures-system/
├── main.py                        # 메인 실행 파일
├── config.py                      # 설정 관리
├── telegram_bot.py               # 텔레그램 봇
├── bitget_client.py              # Bitget API 클라이언트
├── analysis_engine.py            # GPT 분석 엔진
├── exception_detector.py         # 이상 징후 감지
├── data_collector.py             # 실시간 데이터 수집 (1% 민감도)
├── realistic_news_collector.py   # 뉴스 수집 시스템
├── trading_indicators.py         # 선물 특화 지표 시스템
├── report_generators/            # 리포트 생성 모듈
│   ├── __init__.py              
│   ├── base_generator.py        
│   ├── regular_report.py         # 종합 분석 리포트
│   ├── profit_report.py          # 손익 현황
│   ├── forecast_report.py        # 12시간 예측
│   ├── schedule_report.py        # 일정 안내
│   ├── exception_report.py       # 긴급 알림
│   └── mental_care.py            # 멘탈 케어
├── requirements.txt             
├── .env.example                  # 환경변수 예시
├── Dockerfile                   
└── README.md                    
```

## 🚀 빠른 시작

### 1. 저장소 클론
```bash
git clone https://github.com/your-repo/bitcoin-futures-system.git
cd bitcoin-futures-system
```

### 2. 가상환경 설정
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 환경변수 설정
```bash
cp .env.example .env
# .env 파일을 편집하여 API 키 입력
```

### 4. 실행
```bash
python main.py
```

## 🔧 환경 설정

### 필수 API
- **Telegram Bot Token**: [@BotFather](https://t.me/botfather)에서 생성
- **Bitget API**: [Bitget](https://www.bitget.com) 계정에서 생성 (읽기 권한만 필요)

### 권장 API
- **OpenAI API**: GPT 분석 기능 활성화
- **NewsAPI**: 실시간 뉴스 수집
- **CoinGecko API**: 시장 전반 데이터 (무료)

### 선택 API
- **CryptoCompare**: 소셜 메트릭
- **Glassnode**: 온체인 데이터
- **NewsData, Alpha Vantage**: 추가 뉴스 소스

## 📊 리포트 종류

### 1. 종합 분석 리포트 (/report)
- **발송 시간**: 09:00, 13:00, 17:00, 22:00 (자동)
- **내용**: 
  - 선물 시장 핵심 지표
  - 롱/숏 신호 분석 (점수화)
  - 구체적 전략 제안
  - 리스크 평가

### 2. 단기 예측 리포트 (/forecast)
- **주요 기능**: 12시간 집중 예측
- **내용**:
  - 진입 구간 및 방향
  - 손절/목표가 설정
  - 주요 이벤트 영향

### 3. 손익 현황 (/profit)
- **실시간 조회**
- **내용**:
  - 현재 포지션 상세
  - 실현/미실현 손익
  - 개인화 멘탈 케어

### 4. 예외 상황 알림 (자동)
- **조건**: 
  - 가격 1% 이상 급변동
  - 극단적 펀딩비
  - 대량 청산 감지
  - 중요 뉴스 발생

## 💬 사용 방법

### 슬래시 명령어
```
/start    - 시스템 소개 및 도움말
/report   - 종합 분석 리포트
/forecast - 단기 예측 (12시간)
/profit   - 실시간 손익 현황
/schedule - 자동 알림 일정
```

### 자연어 질문
- "지금 롱 들어가도 돼?"
- "숏 포지션 잡을까?"
- "오늘 수익은?"
- "시장 상황 어때?"

## 🎯 선물 특화 기능

### 롱/숏 점수 시스템
각 지표별 -10 ~ +10점 부여:
- **펀딩비**: 과열도에 따른 역방향 기회
- **OI 변화**: 포지션 증감과 가격 관계
- **CVD**: 실제 매수/매도 압력
- **청산 리스크**: 대량 청산 임박 여부
- **기술적 지표**: RSI, MACD 등
- **스마트머니**: 고래 움직임

### 리스크 관리
- 변동성 기반 포지션 크기 조절
- 자동 손절가 제안
- 펀딩비 비용 계산
- 청산 가격 모니터링

## 📈 성능 최적화

- **병렬 데이터 수집**: asyncio 활용
- **캐싱 시스템**: API 호출 최소화
- **메모리 관리**: 이벤트 버퍼 자동 정리
- **오류 복구**: 자동 재연결 및 폴백

## 🔐 보안

- API 키는 환경변수로 관리
- 거래 기능 없음 (읽기 전용)
- 로컬 실행 권장

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## ⚠️ 주의사항

- 이 시스템은 정보 제공 목적으로만 사용됩니다
- 투자 결정은 본인의 판단과 책임하에 이루어져야 합니다
- 선물 거래는 높은 리스크를 동반합니다

## 📞 문의

문제 발생시 Issue를 생성하거나 텔레그램으로 문의하세요.

---

**v2.0** - 선물 거래 특화 업데이트
- 펀딩비, OI, CVD 등 선물 핵심 지표 추가
- 롱/숏 신호 점수 시스템
- 가격 변동 민감도 1%로 향상
- 추가 데이터 소스 통합
