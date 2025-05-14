Your free instance will spin down with inactivity, which can delay requests by 50 seconds or more.
Upgrade now
May 14, 2025 at 10:29 AM
in progress
0b2f397
Update main.py
Cancel deploy

All logs
Search
Search

Live tail
GMT+9

Menu
==> Cloning from https://github.com/xoxoname/btc-daily-report
==> Checking out commit 0b2f3974615cf57ca3c603c93560768a76292908 in branch main
==> Using Python version 3.11.11 (default)
==> Docs on specifying a Python version: https://render.com/docs/python-version
==> Using Poetry version 1.7.1 (default)
==> Docs on specifying a Poetry version: https://render.com/docs/poetry-version
==> Running build command 'pip install -r requirements.txt'...
Collecting requests (from -r requirements.txt (line 1))
  Downloading requests-2.32.3-py3-none-any.whl.metadata (4.6 kB)
Collecting python-dotenv (from -r requirements.txt (line 2))
  Downloading python_dotenv-1.1.0-py3-none-any.whl.metadata (24 kB)
Collecting pytz (from -r requirements.txt (line 3))
  Downloading pytz-2025.2-py2.py3-none-any.whl.metadata (22 kB)
Collecting charset-normalizer<4,>=2 (from requests->-r requirements.txt (line 1))
  Downloading charset_normalizer-3.4.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (35 kB)
Collecting idna<4,>=2.5 (from requests->-r requirements.txt (line 1))
  Downloading idna-3.10-py3-none-any.whl.metadata (10 kB)
Collecting urllib3<3,>=1.21.1 (from requests->-r requirements.txt (line 1))
  Downloading urllib3-2.4.0-py3-none-any.whl.metadata (6.5 kB)
Collecting certifi>=2017.4.17 (from requests->-r requirements.txt (line 1))
  Downloading certifi-2025.4.26-py3-none-any.whl.metadata (2.5 kB)
Downloading requests-2.32.3-py3-none-any.whl (64 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 64.9/64.9 kB 7.1 MB/s eta 0:00:00
Downloading python_dotenv-1.1.0-py3-none-any.whl (20 kB)
Downloading pytz-2025.2-py2.py3-none-any.whl (509 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 509.2/509.2 kB 20.4 MB/s eta 0:00:00
Downloading certifi-2025.4.26-py3-none-any.whl (159 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 159.6/159.6 kB 23.0 MB/s eta 0:00:00
Downloading charset_normalizer-3.4.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (147 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 147.3/147.3 kB 24.0 MB/s eta 0:00:00
Downloading idna-3.10-py3-none-any.whl (70 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 70.4/70.4 kB 11.0 MB/s eta 0:00:00
Downloading urllib3-2.4.0-py3-none-any.whl (128 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 128.7/128.7 kB 18.0 MB/s eta 0:00:00
Installing collected packages: pytz, urllib3, python-dotenv, idna, charset-normalizer, certifi, requests
Successfully installed certifi-2025.4.26 charset-normalizer-3.4.2 idna-3.10 python-dotenv-1.1.0 pytz-2025.2 requests-2.32.3 urllib3-2.4.0
[notice] A new release of pip is available: 24.0 -> 25.1.1
[notice] To update, run: pip install --upgrade pip
==> Uploading build...
==> Uploaded in 4.0s. Compression took 1.0s
==> Build successful 🎉
==> Deploying...
==> Running 'python main.py'
❌ Bitget API 호출 실패: 404 Client Error: Not Found for url: https://api.bitget.com/api/mix/v1/position/allPositions?productType=USDT-FUTURES&marginCoin=USDT
📈 [BTC 실시간 포지션 수익 요약 - 전체 조회]
시각: 2025-05-14 10:30:34
📭 현재 보유 중인 포지션이 없습니다.
==> Running 'python main.py'
❌ Bitget API 호출 실패: 404 Client Error: Not Found for url: https://api.bitget.com/api/mix/v1/position/allPositions?productType=USDT-FUTURES&marginCoin=USDT
📈 [BTC 실시간 포지션 수익 요약 - 전체 조회]
시각: 2025-05-14 10:30:44
📭 현재 보유 중인 포지션이 없습니다.
