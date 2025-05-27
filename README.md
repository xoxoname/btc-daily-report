# 📊 비트코인 자동 선물 예측 시스템 v2.0

## 🆕 주요 개선사항

### 1. **모듈화된 리포트 시스템**
```
report_generators/
├── __init__.py           # 통합 매니저
├── base_generator.py     # 공통 기능
├── regular_report.py     # /report 명령어
├── profit_report.py      # /profit 명령어
├── forecast_report.py    # /forecast 명령어
├── schedule_report.py    # /schedule 명령어
├── exception_report.py   # 긴급 알림
└── mental_care.py        # 멘탈 케어 전담
```

### 2. **향상된 멘탈 케어 시스템**
- 🎯 **상황별 맞춤 메시지**: 수익/손실 규모에 따른 다양한 패턴
- 💰 **구체적 수익 언급**: "오늘 $150을 벌었군요!" 형태의 개인화
- 🤝 **GPT 연동**: OpenAI API로 더욱 자연스러운 멘트 생성
- 📊 **자산 상황 반영**: 총 자산, 7일 수익, 미실현손익 종합 고려

### 3. **정확한 데이터 처리**
- ✅ **하드코딩 제거**: 모든 수치를 실제 API에서 조회
- ✅ **포지션 파싱 개선**: 숏/롱, 청산가, 레버리지 정확한 표시
- ✅ **미실현손익 정확**: API 직접 연동으로 실시간 반영

## 📁 새로운 프로젝트 구조

```
bitcoin-prediction-system/
├── main.py                    # 🆕 업데이트된 메인
├── config.py                  # 설정 관리
├── telegram_bot.py           # 텔레그램 봇
├── bitget_client.py          # Bitget API 클라이언트
├── analysis_engine.py        # GPT 분석 엔진
├── exception_detector.py     # 예외 상황 감지
├── data_collector.py         # 실시간 데이터 수집
├── realistic_news_collector.py # 뉴스 수집
├── trading_indicators.py     # 고급 지표
├── report_generators/        # 🆕 리포트 생성기 모듈
│   ├── __init__.py          # 통합 매니저
│   ├── base_generator.py    # 공통 기능
│   ├── regular_report.py    # 정기 리포트
│   ├── profit_report.py     # 수익 리포트
│   ├── forecast_report.py   # 예측 리포트
│   ├── schedule_report.py   # 일정 리포트
│   ├── exception_report.py  # 예외 리포트
│   └── mental_care.py       # 멘탈 케어
├── requirements.txt         # 의존성
├── Dockerfile              # 컨테이너 설정
├── render.yaml             # 배포 설정
└── README.md               # 프로젝트 설명
```

## 🚀 사용법

### 기본 사용법 (기존과 동일)
```python
# main.py에서 자동으로 모든 리포트 생성기 초기화
system = BitcoinPredictionSystem()
await system.start()
```

### 개별 리포트 생성기 사용법
```python
from report_generators import ReportGeneratorManager

# 리포트 매니저 초기화
manager = ReportGeneratorManager(config, data_collector, indicator_system)
manager.set_bitget_client(bitget_client)

# 각종 리포트 생성
regular_report = await manager.generate_regular_report()      # /report
profit_report = await manager.generate_profit_report()       # /profit
forecast_report = await manager.generate_forecast_report()   # /forecast
schedule_report = await manager.generate_schedule_report()   # /schedule

# 예외 상황 리포트
event_data = {'type': 'price_anomaly', 'severity': 'high', ...}
exception_report = await manager.generate_exception_report(event_data)

# 독립적인 멘탈 케어
mental_message = await manager.generate_custom_mental_care(
    account_info, position_info, today_pnl, weekly_profit
)
```

## 🧠 새로운 멘탈 케어 기능

### 다양한 상황별 메시지 패턴

**큰 수익 시:**
```
"오늘 $150을 벌어들였군요! 현재 자산 $6,623은 당신의 실력을 보여줍니다. 
하지만 시장은 변덕스러우니 겸손함을 잊지 마세요. 🎯"
```

**꾸준한 수익 시:**
```
"$50 벌었군요! 큰 돈은 아니어도 꾸준함이 복리의 힘을 만듭니다. 
현재 자산 $6,623을 바탕으로 차근차근 늘려가세요. 🌱"
```

**손실 시:**
```
"현재 $30 마이너스 상태네요. 하지만 최근 7일간 $1,380을 벌었으니 
일시적인 조정일 수 있어요. 손절 기준을 명확히 하고 차분하게 대응하세요. 🧘‍♂️"
```

### GPT 기반 개인화 메시지
- OpenAI API 연동으로 상황에 맞는 자연스러운 조언
- 구체적 수익/손실 금액 언급
- 총 자산, 7일 수익 등 종합적 고려

## 🎯 각 리포트의 특징

### 💰 수익 리포트 (/profit)
- **실시간 포지션**: 숏/롱, 진입가, 청산가, 레버리지
- **정확한 손익**: API 직접 연동, 하드코딩 제거
- **개인화 멘탈케어**: 수익 상황별 맞춤 메시지

### 📈 예측 리포트 (/forecast)
- **단기 집중**: 12시간 내 가격 흐름 예측
- **간결한 정보**: 핵심 분석과 전략 제안
- **빠른 판단**: 매매 결정에 필요한 정보만 압축

### 🧾 정기 리포트 (/report)
- **종합 분석**: 시장 이벤트부터 예측까지 전체
- **자동 발송**: 09:00, 13:00, 17:00, 23:00 (KST)
- **검증 결과**: 이전 예측 정확도 추적

### 📅 일정 리포트 (/schedule)
- **경제 이벤트**: FOMC, ETF 승인 등 주요 일정
- **영향도 평가**: 각 이벤트의 호재/악재 판단

### 🚨 예외 리포트 (자동)
- **즉시 알림**: 급변동, 대량 거래 등 감지 시 자동 발송
- **GPT 분석**: 상황별 전문적 분석과 대응 전략
- **리스크 관리**: 구체적인 포지션 관리 방안 제시

## 🔧 개발자를 위한 확장 가이드

### 새로운 리포트 유형 추가
1. `report_generators/`에 새 파일 생성
2. `BaseReportGenerator` 상속
3. `generate_report()` 메서드 구현
4. `ReportGeneratorManager`에 등록

### 멘탈 케어 패턴 추가
```python
# mental_care.py의 패턴 메서드에 새로운 조건 추가
def _analyze_trading_situation(self, today_pnl, unrealized_pnl, weekly_total):
    # 새로운 상황 분류 로직
    if new_condition:
        return "new_situation_type"
        
def _new_situation_messages(self, ...):
    # 새로운 상황별 메시지 패턴
    patterns = [...]
    return random.choice(patterns)
```

## 🎉 마이그레이션 가이드

기존 `report_generator.py`에서 새로운 모듈식 구조로 전환:

```python
# 기존
from report_generator import EnhancedReportGenerator
generator = EnhancedReportGenerator(config, data_collector, indicators)

# 새로운 방식
from report_generators import ReportGeneratorManager
manager = ReportGeneratorManager(config, data_collector, indicators)

# 메서드명 변경
# generator.generate_profit_report() → manager.generate_profit_report()
```

하위 호환성을 위해 기존 클래스명도 유지됩니다.

## 📊 성능 최적화

- **병렬 데이터 수집**: asyncio.gather로 API 호출 최적화
- **캐싱 시스템**: 중복 API 호출 방지
- **메모리 관리**: 이벤트 버퍼 자동 정리
- **오류 처리**: 견고한 예외 처리와 폴백 시스템

이제 각 리포트가 독립적으로 관리되어 유지보수가 쉽고, 멘탈 케어가 더욱 개인화되었습니다! 🚀
