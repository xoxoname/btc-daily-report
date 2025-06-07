import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
    def __init__(self):
        # 🔥🔥🔥 미러 트레이딩 모드 설정 - 두 환경변수 모두 지원
        enable_mirror = os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true'
        mirror_mode = os.getenv('MIRROR_TRADING_MODE', 'false').lower() == 'true'
        self.MIRROR_TRADING_MODE = enable_mirror or mirror_mode  # 둘 중 하나라도 true면 활성화
        
        # Telegram 설정
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
        
        # Bitget API 설정 (환경변수 이름 사용자 요구사항대로 유지)
        self.BITGET_API_KEY = os.getenv('BITGET_APIKEY')
        self.BITGET_SECRET_KEY = os.getenv('BITGET_APISECRET')
        self.BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')
        
        # Gate.io API 설정 (환경변수 이름 사용자 요구사항대로 유지)
        self.GATE_API_KEY = os.getenv('GATE_API_KEY')
        self.GATE_API_SECRET = os.getenv('GATE_API_SECRET')
        
        # Bitget 추가 설정
        self.bitget_base_url = "https://api.bitget.com"
        self.bitget_api_key = self.BITGET_API_KEY
        self.bitget_api_secret = self.BITGET_SECRET_KEY
        self.bitget_passphrase = self.BITGET_PASSPHRASE
        self.symbol = "BTCUSDT"
        
        # 🔥🔥🔥 미러 트레이딩 체크 간격 설정 (사용자 요구사항대로 유지)
        self.MIRROR_CHECK_INTERVAL = int(os.getenv('MIRROR_CHECK_INTERVAL', '15'))  # 기본 15초
        
        # 기존 뉴스 API (환경변수 이름 사용자 요구사항대로 유지)
        self.NEWSAPI_KEY = os.getenv('NEWSAPI_KEY')
        self.ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY')
        self.SDATA_KEY = os.getenv('SDATA_KEY')  # 사용자가 언급한 환경변수 추가
        
        # 추가 데이터 소스 API (환경변수 이름 사용자 요구사항대로 유지)
        self.COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY')  # 선택사항
        self.CRYPTOCOMPARE_API_KEY = os.getenv('CRYPTOCOMPARE_API_KEY')
        self.GLASSNODE_API_KEY = os.getenv('GLASSNODE_API_KEY')
        
        # AI API 설정 (환경변수 이름 사용자 요구사항대로 유지)
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        self.ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')  # Claude API
        
        # 🔥🔥🔥 게이트 예약주문 보호 설정 추가
        self.GATE_ORDER_PROTECTION_ENABLED = True  # 게이트 주문 보호 활성화
        self.GATE_ORDER_PROTECTION_DURATION = 600  # 10분간 보호
        self.BITGET_ORDER_CHECK_INTERVAL = 30  # 비트겟 주문 체크 간격 (초)
        self.REQUIRE_BITGET_CANCEL_CONFIRMATION = True  # 비트겟 취소 확인 필수
        self.MAX_DELETION_ATTEMPTS = 2  # 최대 삭제 시도 횟수
        self.DELETION_COOLDOWN = 3600  # 삭제 시도 쿨다운 (초)
        
        # 🔥🔥🔥 안전성 강화 설정
        self.SAFE_DELETION_THRESHOLD = 3  # 안전 삭제 임계값
        self.DELETION_VERIFICATION_DELAY = 15  # 삭제 전 대기 시간 (초)
        self.SIMILAR_ORDER_TOLERANCE = 0.1  # 유사 주문 허용 오차 (10%)
        self.PRICE_DIFFERENCE_TOLERANCE = 1000.0  # 시세 차이 허용 임계값 ($)
        
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
                print("다음 환경변수를 설정해주세요:")
                print("- GATE_API_KEY: Gate.io API 키")
                print("- GATE_API_SECRET: Gate.io API 시크릿")
                print("\n🔥 게이트 예약주문 보호 시스템이 활성화됩니다.")
                self.MIRROR_TRADING_MODE = False
                return
        
        # 필수 설정 검증
        missing_configs = []
        for key, value in required_configs.items():
            if not value:
                missing_configs.append(key)
        
        if missing_configs:
            print(f"\n❌ 다음 필수 환경변수가 설정되지 않았습니다:")
            for config in missing_configs:
                print(f"   - {config}")
            print(f"\n환경변수를 설정한 후 다시 시작해주세요.")
            raise ValueError(f"필수 환경변수 누락: {', '.join(missing_configs)}")
        
        # 설정 완료 메시지
        print(f"\n✅ 설정 검증 완료")
        print(f"🔧 미러 트레이딩: {'활성화' if self.MIRROR_TRADING_MODE else '비활성화'}")
        
        if self.MIRROR_TRADING_MODE:
            print(f"🔥 게이트 예약주문 보호: 활성화")
            print(f"   - 보호 시간: {self.GATE_ORDER_PROTECTION_DURATION}초")
            print(f"   - 체크 간격: {self.BITGET_ORDER_CHECK_INTERVAL}초")
            print(f"   - 미러 체크 간격: {self.MIRROR_CHECK_INTERVAL}초")
        
        # 선택적 API 상태 출력
        optional_apis = {
            'OpenAI API': self.OPENAI_API_KEY,
            'NewsAPI': self.NEWSAPI_KEY,
            'Alpha Vantage': self.ALPHA_VANTAGE_KEY,
            'CoinGecko': self.COINGECKO_API_KEY,
            'CryptoCompare': self.CRYPTOCOMPARE_API_KEY
        }
        
        print(f"\n📡 선택적 API 상태:")
        for api_name, api_key in optional_apis.items():
            status = "✅" if api_key else "❌"
            print(f"   {status} {api_name}")
        
        print()  # 빈 줄 추가
    
    def get_mirror_trading_config(self) -> dict:
        """🔥🔥🔥 미러 트레이딩 관련 설정 반환"""
        return {
            'enabled': self.MIRROR_TRADING_MODE,
            'check_interval': self.MIRROR_CHECK_INTERVAL,
            'gate_protection_enabled': self.GATE_ORDER_PROTECTION_ENABLED,
            'gate_protection_duration': self.GATE_ORDER_PROTECTION_DURATION,
            'bitget_check_interval': self.BITGET_ORDER_CHECK_INTERVAL,
            'require_cancel_confirmation': self.REQUIRE_BITGET_CANCEL_CONFIRMATION,
            'max_deletion_attempts': self.MAX_DELETION_ATTEMPTS,
            'deletion_cooldown': self.DELETION_COOLDOWN,
            'safe_deletion_threshold': self.SAFE_DELETION_THRESHOLD,
            'deletion_verification_delay': self.DELETION_VERIFICATION_DELAY,
            'similar_order_tolerance': self.SIMILAR_ORDER_TOLERANCE,
            'price_difference_tolerance': self.PRICE_DIFFERENCE_TOLERANCE
        }
    
    def get_api_config(self) -> dict:
        """API 설정 반환"""
        return {
            'bitget': {
                'api_key': self.BITGET_API_KEY,
                'secret_key': self.BITGET_SECRET_KEY,
                'passphrase': self.BITGET_PASSPHRASE,
                'base_url': self.bitget_base_url,
                'symbol': self.symbol
            },
            'gate': {
                'api_key': self.GATE_API_KEY,
                'api_secret': self.GATE_API_SECRET
            } if self.MIRROR_TRADING_MODE else None,
            'telegram': {
                'bot_token': self.TELEGRAM_BOT_TOKEN,
                'chat_id': self.TELEGRAM_CHAT_ID
            },
            'openai': {
                'api_key': self.OPENAI_API_KEY
            } if self.OPENAI_API_KEY else None,
            'news': {
                'newsapi_key': self.NEWSAPI_KEY,
                'alpha_vantage_key': self.ALPHA_VANTAGE_KEY,
                'sdata_key': self.SDATA_KEY,
                'coingecko_key': self.COINGECKO_API_KEY,
                'cryptocompare_key': self.CRYPTOCOMPARE_API_KEY
            }
        }
    
    def is_mirror_trading_enabled(self) -> bool:
        """미러 트레이딩 활성화 여부 확인"""
        return self.MIRROR_TRADING_MODE and bool(self.GATE_API_KEY) and bool(self.GATE_API_SECRET)
    
    def get_protection_settings(self) -> dict:
        """🔥🔥🔥 보호 설정 반환"""
        return {
            'gate_order_protection': self.GATE_ORDER_PROTECTION_ENABLED,
            'protection_duration': self.GATE_ORDER_PROTECTION_DURATION,
            'bitget_check_interval': self.BITGET_ORDER_CHECK_INTERVAL,
            'cancel_confirmation_required': self.REQUIRE_BITGET_CANCEL_CONFIRMATION,
            'max_deletion_attempts': self.MAX_DELETION_ATTEMPTS,
            'deletion_cooldown': self.DELETION_COOLDOWN,
            'safe_deletion_threshold': self.SAFE_DELETION_THRESHOLD,
            'verification_delay': self.DELETION_VERIFICATION_DELAY,
            'order_similarity_tolerance': self.SIMILAR_ORDER_TOLERANCE,
            'price_tolerance': self.PRICE_DIFFERENCE_TOLERANCE
        }
