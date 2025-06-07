import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
    def __init__(self):
        # 미러 트레이딩 모드 먼저 확인
        self.MIRROR_TRADING_MODE = os.getenv('MIRROR_TRADING_MODE', 'false').lower() == 'true'
        
        # Telegram 설정
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
        
        # Bitget API 설정
        self.BITGET_API_KEY = os.getenv('BITGET_APIKEY')
        self.BITGET_SECRET_KEY = os.getenv('BITGET_APISECRET')
        self.BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')
        
        # Gate.io API 설정 (선택사항)
        self.GATE_API_KEY = os.getenv('GATE_API_KEY')
        self.GATE_API_SECRET = os.getenv('GATE_API_SECRET')
        
        # Bitget 추가 설정
        self.bitget_base_url = "https://api.bitget.com"
        self.bitget_api_key = self.BITGET_API_KEY
        self.bitget_api_secret = self.BITGET_SECRET_KEY
        self.bitget_passphrase = self.BITGET_PASSPHRASE
        self.symbol = "BTCUSDT"
        
        # 기존 뉴스 API (3개)
        self.NEWSAPI_KEY = os.getenv('NEWSAPI_KEY')
        self.NEWSDATA_KEY = os.getenv('NEWSDATA_KEY')
        self.ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY')
        
        # 추가 데이터 소스 API
        self.COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY')  # 선택사항
        self.CRYPTOCOMPARE_API_KEY = os.getenv('CRYPTOCOMPARE_API_KEY')
        self.GLASSNODE_API_KEY = os.getenv('GLASSNODE_API_KEY')
        
        # AI API 설정
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        self.ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')  # Claude API 추가
        
        # 🔥🔥🔥 미러 트레이딩 강화 설정
        self.ENABLE_MIRROR_TRADING = os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true'
        self.MIRROR_CHECK_INTERVAL = int(os.getenv('MIRROR_CHECK_INTERVAL', '5'))  # 5초로 단축
        
        # 🔥🔥🔥 추가 미러 트레이딩 관련 환경변수 지원
        self.SDATA_KEY = os.getenv('SDATA_KEY')  # 추가 데이터 소스
        
        # 설정 검증
        self._validate_config()
    
    def _validate_config(self):
        """필수 설정 검증"""
        # 기본 필수 설정 (항상 필요)
        required_configs = {
            'TELEGRAM_BOT_TOKEN': self.TELEGRAM_BOT_TOKEN,
            'TELEGRAM_CHAT_ID': self.TELEGRAM_CHAT_ID,
            'BITGET_API_KEY': self.BITGET_API_KEY,
            'BITGET_SECRET_KEY': self.BITGET_SECRET_KEY,
            'BITGET_PASSPHRASE': self.BITGET_PASSPHRASE
        }
        
        # 미러 트레이딩 모드일 때만 Gate.io API 필수
        if self.MIRROR_TRADING_MODE:
            if not self.GATE_API_KEY or not self.GATE_API_SECRET:
                print("\n⚠️  미러 트레이딩 모드가 활성화되었지만 Gate.io API가 설정되지 않았습니다.")
                print("   다음 환경변수를 설정해주세요:")
                print("   - GATE_API_KEY")
                print("   - GATE_API_SECRET")
                print("   또는 MIRROR_TRADING_MODE=false로 설정하여 분석 전용 모드로 실행하세요.")
                # 시스템 종료하지 않고 경고만 출력
            else:
                required_configs.update({
                    'GATE_API_KEY': self.GATE_API_KEY,
                    'GATE_API_SECRET': self.GATE_API_SECRET
                })
        
        # 필수 설정 검증
        missing_configs = []
        for config_name, config_value in required_configs.items():
            if not config_value:
                missing_configs.append(config_name)
        
        if missing_configs:
            print(f"\n❌ 필수 환경변수가 설정되지 않았습니다:")
            for config in missing_configs:
                print(f"   - {config}")
            print(f"\n환경변수를 설정한 후 다시 실행해주세요.")
            exit(1)
        
        # 설정 완료 메시지
        print(f"\n✅ 기본 설정 검증 완료")
        print(f"📊 모드: {'🔄 미러 트레이딩' if self.MIRROR_TRADING_MODE else '📈 분석 전용'}")
        
        # 선택적 API 상태 확인
        optional_apis = {
            'NewsAPI': self.NEWSAPI_KEY,
            'NewsData': self.NEWSDATA_KEY,
            'Alpha Vantage': self.ALPHA_VANTAGE_KEY,
            'CoinGecko': self.COINGECKO_API_KEY,
            'CryptoCompare': self.CRYPTOCOMPARE_API_KEY,
            'Glassnode': self.GLASSNODE_API_KEY,
            'OpenAI': self.OPENAI_API_KEY,
            'Anthropic': self.ANTHROPIC_API_KEY,
            'SData': self.SDATA_KEY
        }
        
        available = []
        missing = []
        
        for api_name, api_key in optional_apis.items():
            if api_key:
                available.append(api_name)
            else:
                missing.append(api_name)
        
        if available:
            print(f"\n✅ 사용 가능한 추가 API ({len(available)}개):")
            for api in available:
                print(f"  • {api}")
        
        if missing:
            print(f"\n⚠️  미설정 API ({len(missing)}개):")
            for api in missing:
                print(f"  • {api}")
        
        # AI 번역 우선순위 표시
        if self.ANTHROPIC_API_KEY and self.OPENAI_API_KEY:
            print(f"\n🤖 AI 번역 설정: Claude 우선, GPT 백업")
        elif self.ANTHROPIC_API_KEY:
            print(f"\n🤖 AI 번역 설정: Claude만 사용")
        elif self.OPENAI_API_KEY:
            print(f"\n🤖 AI 번역 설정: GPT만 사용")
        else:
            print(f"\n⚠️  AI 번역 미설정 (번역 기능 제한)")
        
        # 운영 모드별 추가 정보
        if self.MIRROR_TRADING_MODE:
            print("\n💡 미러 트레이딩 설정:")
            print("  • 기준 거래소: Bitget")
            print("  • 미러 거래소: Gate.io")
            print("  • 미러링 방식: 마진 비율 기반")
            print("  • 기존 포지션: 복제 제외")
            print("  • 신규 진입만 미러링")
            print(f"  • 🔥 예약 주문 체크 주기: {self.MIRROR_CHECK_INTERVAL}초 (강화)")
            print("  • 🔥 강제 동기화: 15초마다 (강화)")
            print("  • 🔥 스타트업 제외: 15분으로 단축")
        else:
            print("\n💡 현재 기능:")
            print("  • 실시간 가격 모니터링")
            print("  • 기술적 분석 리포트")
            print("  • AI 기반 예측")
            print("  • 뉴스 및 이벤트 추적")
            print("  • 수익 현황 조회")
            
            if not self.GATE_API_KEY:
                print("\n💡 미러 트레이딩 활성화 방법:")
                print("  환경변수에 다음 추가:")
                print("  MIRROR_TRADING_MODE=true")
                print("  GATE_API_KEY=your_gate_key")
                print("  GATE_API_SECRET=your_gate_secret")
        
        print("\n💡 추가 API 설정 방법:")
        print("  환경변수에 추가:")
        
        if not self.ANTHROPIC_API_KEY:
            print("  ANTHROPIC_API_KEY=your_key (Claude 번역 활성화)")
        if not self.OPENAI_API_KEY:
            print("  OPENAI_API_KEY=your_key (GPT 번역 활성화)")
        if not self.NEWSAPI_KEY:
            print("  NEWSAPI_KEY=your_key (뉴스 수집 활성화)")
        if not self.COINGECKO_API_KEY:
            print("  COINGECKO_API_KEY=your_key (시장 데이터 강화)")
        if not self.CRYPTOCOMPARE_API_KEY:
            print("  CRYPTOCOMPARE_API_KEY=your_key (가격 데이터 강화)")
        
        print("\n" + "="*50)
        
        # 🔥🔥🔥 미러 트레이딩 모드 전용 추가 검증
        if self.MIRROR_TRADING_MODE:
            print("\n🔥 미러 트레이딩 강화 설정:")
            print(f"  • ENABLE_MIRROR_TRADING: {self.ENABLE_MIRROR_TRADING}")
            print(f"  • MIRROR_CHECK_INTERVAL: {self.MIRROR_CHECK_INTERVAL}초")
            print("  • 🚀 더 빠른 동기화로 누락 복제 최소화")
            print("  • 🎯 클로즈 주문 즉시 감지 및 복제")
            print("  • 🔄 적극적인 강제 동기화")

# 전역 설정 인스턴스
config = Config()
