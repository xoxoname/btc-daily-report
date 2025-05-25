#!/bin/bash

# run.sh - 로컬 실행 스크립트

echo "🚀 비트코인 예측 시스템 시작 중..."

# 가상환경 확인
if [ ! -d "venv" ]; then
    echo "📦 가상환경 생성 중..."
    python3 -m venv venv
fi

# 가상환경 활성화
echo "🔧 가상환경 활성화..."
source venv/bin/activate

# 의존성 설치
echo "📋 의존성 패키지 설치 중..."
pip install -r requirements.txt

# 환경변수 확인
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일이 없습니다. 환경변수를 설정해주세요."
    echo "필요한 환경변수:"
    echo "BITGET_APIKEY=your_api_key"
    echo "BITGET_APISECRET=your_api_secret"
    echo "BITGET_PASSPHRASE=your_passphrase"
    echo "OPENAI_API_KEY=your_openai_key"
    echo "TELEGRAM_BOT_TOKEN=your_bot_token"
    echo "TELEGRAM_CHAT_ID=1038440081"
    exit 1
fi

# 환경변수 로드
export $(cat .env | xargs)

# 애플리케이션 실행
echo "🎯 애플리케이션 시작..."
python main.py
