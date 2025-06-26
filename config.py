import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
    def __init__(self):
        # 미러 트레이딩 모드는 더 이상 환경변수에 의존하지 않음
        # 기본값으로만 사용하고, 텔레그램에서 실시간 제어
        self.MIRROR_TRADING_DEFAULT = self._parse_mirror_trading_default()
        
        # Telegram 설정
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
        
        # Bitget API 설정
        self.BITGET_API_KEY = os.getenv('BITGET_APIKEY')
        self.BITGET_SECRET_KEY = os.getenv('BITGET_APISECRET')
        self.BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')
        
        # Gate.io API 설정 (미러링용 - 항상 필요)
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
        self.NEWSDATA_KEY = os.getenv('SDATA_KEY')  # SDATA_KEY 유지
        self.ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY')
        
        # 추가 데이터 소스 API
        self.COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY')  # 선택사항
        self.CRYPTOCOMPARE_API_KEY = os.getenv('CRYPTOCOMPARE_API_KEY')
        self.GLASSNODE_API_KEY = os.getenv('GLASSNODE_API_KEY')
        
        # AI API 설정
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        self.ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')  # Claude API 추가
        
        # 미러링 체크 간격 설정
        self.MIRROR_CHECK_INTERVAL = int(os.getenv('MIRROR_CHECK_INTERVAL', '1'))
        
        # 설정 검증
        self._validate_config()
    
    def _parse_mirror_trading_default(self) -> bool:
        """미러링 모드 기본값 파싱 - 환경변수는 기본값으로만 사용"""
        try:
            # ENABLE_MIRROR_TRADING이 우선
            enable_mirror = os.getenv('ENABLE_MIRROR_TRADING', '').lower()
            if enable_mirror in ['true', '1', 'yes', 'on', 'o']:
                return True
            elif enable_mirror in ['false', '0', 'no', 'off', 'x']:
                return False
            
            # MIRROR_TRADING_MODE가 다음 우선순위
            mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'X').strip().upper()
            
            # O = 활성화, X = 비활성화
            if mirror_mode == 'O':
                return True
            elif mirror_mode == 'X':
                return False
            elif mirror_mode in ['ON', 'TRUE', 'YES', '1']:
                return True
            elif mirror_mode in ['OFF', 'FALSE', 'NO', '0']:
                return False
            else:
                # 기본값: 비활성화 (텔레그램에서 활성화)
                return False
                
        except Exception as e:
            print(f"⚠️ 미러링 모드 기본값 파싱 실패: {e}, 기본값(비활성화) 사용")
            return False
    
    def _validate_config(self):
        """필수 설정 검증 - Gate.io API는 항상 필수"""
        required_configs = {
            'TELEGRAM_BOT_TOKEN': self.TELEGRAM_BOT_TOKEN,
            'TELEGRAM_CHAT_ID': self.TELEGRAM_CHAT_ID,
            'BITGET_API_KEY': self.BITGET_API_KEY,
            'BITGET_SECRET_KEY': self.BITGET_SECRET_KEY,
            'BITGET_PASSPHRASE': self.BITGET_PASSPHRASE,
            'GATE_API_KEY': self.GATE_API_KEY,  # 항상 필수
            'GATE_API_SECRET': self.GATE_API_SECRET  # 항상 필수
        }
        
        missing_configs = []
        for config_name, config_value in required_configs.items():
            if not config_value:
                missing_configs.append(config_name)
        
        if missing_configs:
            raise ValueError(f"다음 환경변수가 설정되지 않았습니다: {', '.join(missing_configs)}")
        
        # API 상태 출력
        self._print_config_status()
    
    def _print_config_status(self):
        """설정 상태 출력 - 텔레그램 제어 모드 안내"""
        print("\n🔧 API 설정 상태:")
        print("━" * 50)
        
        # 미러링 모드는 텔레그램 제어로 변경됨
        print("🎮 운영 모드: 텔레그램 실시간 제어")
        print(f"📊 미러링 기본값: {'활성화' if self.MIRROR_TRADING_DEFAULT else '비활성화'}")
        print("💡 미러링 제어: 텔레그램 /mirror on/off")
        
        print("\n✅ 필수 API:")
        print(f"  • Telegram Bot: {'설정됨' if self.TELEGRAM_BOT_TOKEN else '미설정'}")
        print(f"  • Bitget API: {'설정됨' if self.BITGET_API_KEY else '미설정'}")
        print(f"  • Gate.io API: {'설정됨' if self.GATE_API_KEY else '미설정'} (미러링용 필수)")
        
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
        
        # 텔레그램 제어 안내
        print("\n🎮 텔레그램 실시간 제어:")
        print("  • 미러링 활성화: /mirror on 또는 '미러링 켜기'")
        print("  • 미러링 비활성화: /mirror off 또는 '미러링 끄기'")
        print("  • 미러링 상태: /mirror status 또는 '미러링 상태'")
        print("  • 복제 비율 변경: /ratio 1.5 또는 '비율 1.5배'")
        print("  • 현재 배율 확인: /ratio 또는 '현재 배율'")
        
        print("\n💳 Gate.io 설정:")
        print("  • Margin Mode: 자동으로 Cross 설정됨 (청산 방지)")
        print("  • 시작 시 항상 Cross 확인 및 설정")
        print("  • Isolated → Cross 자동 변경")
        
        print("\n💡 현재 기능:")
        print("  • 실시간 가격 모니터링")
        print("  • 기술적 분석 리포트")
        print("  • AI 기반 예측")
        print("  • 뉴스 및 이벤트 추적")
        print("  • 수익 현황 조회")
        print("  • 🎮 텔레그램 실시간 미러링 제어")
        print("  • 💳 Gate.io 마진 모드 자동 Cross 설정")
        print("  • 📊 복제 비율 실시간 조정")
        
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
        """설정 요약 정보 - 텔레그램 제어 모드 반영"""
        return {
            'mode': 'telegram_controlled',  # 텔레그램 제어 모드
            'mirror_default': self.MIRROR_TRADING_DEFAULT,
            'exchanges': {
                'bitget': bool(self.BITGET_API_KEY),
                'gate': bool(self.GATE_API_KEY)
            },
            'features': {
                'telegram_control': True,  # 텔레그램 제어 활성화
                'margin_mode_auto': True,  # 마진 모드 자동 설정
                'ai_analysis': bool(self.OPENAI_API_KEY or self.ANTHROPIC_API_KEY),
                'claude_translation': bool(self.ANTHROPIC_API_KEY),
                'gpt_analysis': bool(self.OPENAI_API_KEY),
                'news_collection': any([self.NEWSAPI_KEY, self.NEWSDATA_KEY, self.ALPHA_VANTAGE_KEY]),
                'market_data': any([self.COINGECKO_API_KEY, self.CRYPTOCOMPARE_API_KEY]),
                'onchain_data': bool(self.GLASSNODE_API_KEY)
            }
        }
