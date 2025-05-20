# 비트코인 자동 선물 예측 시스템

## 주요 특징
- GPT 실시간 예측 & Bitget API 기반 자산/포지션/수익 분석
- 09:00 / 13:00 / 17:00 / 23:00 정규 리포트, 5분마다 예외 감지
- 텔레그램 명령어 및 자연어 인식 (/report, /forecast, /profit, /schedule)
- 멘탈 케어, 실시간 예측 검증, 자기반성 피드백, 모든 한국시간(Asia/Seoul) 기준
- 환경 변수는 반드시 Render 환경 변수 메뉴에서 설정

## 폴더 구조/사용법
1. 코드를 zip으로 받아 압축 해제 후, GitHub로 업로드
2. Render Background Worker에 연결하여 실행
3. `.env` 파일 불필요, 환경 변수로만 API 키 입력
