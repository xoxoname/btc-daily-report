import time, hmac, base64, requests

API_KEY = "bg_165a2ef1edbb76933e1ba55dc21d552d"     # 복붙 주의, 공백 제거
API_SECRET = "dc5d5992fe8140d456932368d0f3cdf5c8d468a91b8b91a85d1111115b0b2a6a" # 복붙 주의
PASSPHRASE = "ektha2405"  # 영문/숫자만, 공백·한글·특수문자 X

def check_ascii(text, name):
    try:
        text.encode('ascii')
        print(f"{name} OK: {text}")
    except Exception as e:
        print(f"{name} ASCII ERROR: {text} ({e})")

for key, name in [(API_KEY, "API_KEY"), (API_SECRET, "API_SECRET"), (PASSPHRASE, "PASSPHRASE")]:
    check_ascii(key, name)
    print(f"{name} (length): {len(key)}")

timestamp = str(int(time.time() * 1000))
method = "GET"
request_path = "/api/v2/mix/account/accounts?productType=USDT-FUTURES"
body = ""
message = timestamp + method + request_path + body

sign = base64.b64encode(
    hmac.new(API_SECRET.encode('utf-8'), message.encode('utf-8'), digestmod='sha256').digest()
).decode('utf-8')

headers = {
    "ACCESS-KEY": API_KEY,
    "ACCESS-SIGN": sign,
    "ACCESS-TIMESTAMP": timestamp,
    "ACCESS-PASSPHRASE": PASSPHRASE,
    "Content-Type": "application/json"
}

print("Headers:", headers)
url = "https://api.bitget.com" + request_path
r = requests.get(url, headers=headers)
print("Status:", r.status_code)
print("Response:", r.text)
