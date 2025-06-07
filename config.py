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
                print("미러 트레이딩을 사용하려면 다음 환경변수를 설정하세요:")
                print("  GATE_API_KEY=your_gate_api_key")
                print("  GATE_API_SECRET=your_gate_api_secret")
                print("\n분석 전용 모드로 전환합니다...")
                self.MIRROR_TRADING_MODE = False
            else:
                required_configs.update({
                    'GATE_API_KEY': self.GATE_API_KEY,
                    'GATE_API_SECRET': self.GATE_API_SECRET
                })
        
        missing_configs = []
        for config_name, config_value in required_configs.items():
            if not config_value:
                missing_configs.append(config_name)
        
        if missing_configs:
            raise ValueError(f"다음 환경변수가 설정되지 않았습니다: {', '.join(missing_configs)}")
        
        # API 상태 출력
        self._print_config_status()
    
    def _print_config_status(self):
        """설정 상태 출력"""
        print("\n🔧 API 설정 상태:")
        print("━" * 50)
        
        # 운영 모드
        if self.MIRROR_TRADING_MODE:
            print("🔄 운영 모드: 미러 트레이딩 모드")
        else:
            print("📊 운영 모드: 분석 전용 모드")
        
        print("\n✅ 필수 API:")
        print(f"  • Telegram Bot: {'설정됨' if self.TELEGRAM_BOT_TOKEN else '미설정'}")
        print(f"  • Bitget API: {'설정됨' if self.BITGET_API_KEY else '미설정'}")
        
        if self.MIRROR_TRADING_MODE:
            print(f"  • Gate.io API: {'설정됨' if self.GATE_API_KEY else '미설정'}")
        elif self.GATE_API_KEY:
            print(f"  • Gate.io API: 설정됨 (미사용)")
        
        # 선택 API들
        optional_apis = {
            'OpenAI GPT': self.OPENAI_API_KEY,
            'Claude (Anthropic)': self.ANTHROPIC_API_KEY,
            'NewsAPI': self.NEWSAPI_KEY,
            'NewsData': self.NEWSDATA_KEY,
            'Alpha Vantage': self.ALPHA_VANTAGE_KEY,
            'CoinGecko': self.COINGECKO_API_KEY,
            'CryptoCompare': self.CRYPTOCOMPARE_API_KEY,
            'Glassnode': self.GLASSNODE_API_KEY
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
            print("  OPENAI_API_KEY=your_key (GPT 분석 활성화)")
        if not self.NEWSAPI_KEY:
            print("  NEWSAPI_KEY=your_key (뉴스 수집 강화)")
        if not self.COINGECKO_API_KEY:
            print("  COINGECKO_API_KEY=your_key (시장 데이터 확장)")
        
        print("━" * 50 + "\n")
    
    def is_mirror_mode_enabled(self):
        """미러 트레이딩 모드 활성화 여부"""
        return self.MIRROR_TRADING_MODE
    
    def get_active_apis(self):
        """활성화된 API 목록 반환"""
        active_apis = {
            'telegram': bool(self.TELEGRAM_BOT_TOKEN),
            'bitget': bool(self.BITGET_API_KEY),
            'gate': bool(self.GATE_API_KEY),
            'openai': bool(self.OPENAI_API_KEY),
            'anthropic': bool(self.ANTHROPIC_API_KEY),
            'newsapi': bool(self.NEWSAPI_KEY),
            'newsdata': bool(self.NEWSDATA_KEY),
            'alpha_vantage': bool(self.ALPHA_VANTAGE_KEY),
            'coingecko': bool(self.COINGECKO_API_KEY),
            'cryptocompare': bool(self.CRYPTOCOMPARE_API_KEY),
            'glassnode': bool(self.GLASSNODE_API_KEY)
        }
        return active_apis
    
    def get_config_summary(self):
        """설정 요약 정보"""
        return {
            'mode': 'mirror' if self.MIRROR_TRADING_MODE else 'analysis',
            'exchanges': {
                'bitget': bool(self.BITGET_API_KEY),
                'gate': bool(self.GATE_API_KEY) if self.MIRROR_TRADING_MODE else False
            },
            'features': {
                'ai_analysis': bool(self.OPENAI_API_KEY or self.ANTHROPIC_API_KEY),
                'claude_translation': bool(self.ANTHROPIC_API_KEY),
                'gpt_analysis': bool(self.OPENAI_API_KEY),
                'news_collection': any([self.NEWSAPI_KEY, self.NEWSDATA_KEY, self.ALPHA_VANTAGE_KEY]),
                'market_data': any([self.COINGECKO_API_KEY, self.CRYPTOCOMPARE_API_KEY]),
                'onchain_data': bool(self.GLASSNODE_API_KEY)
            }
        }
