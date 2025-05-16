May 16, 2025 at 3:06 PM
af5d5f2
Update report.py
Rollback

All logs
Search
Search

May 16, 3:05 PM - 3:08 PM
GMT+9

Menu
==> Cloning from https://github.com/xoxoname/btc-daily-report
==> Checking out commit af5d5f2144c29eb28ddce9916840691af67bceb6 in branch main
==> Downloading cache...
==> Transferred 76MB in 7s. Extraction took 2s.
==> Using Python version 3.11.11 (default)
==> Docs on specifying a Python version: https://render.com/docs/python-version
==> Using Poetry version 1.7.1 (default)
==> Docs on specifying a Poetry version: https://render.com/docs/poetry-version
==> Running build command 'pip install -r requirements.txt'...
Collecting flask (from -r requirements.txt (line 1))
  Using cached flask-3.1.1-py3-none-any.whl.metadata (3.0 kB)
Collecting requests (from -r requirements.txt (line 2))
  Using cached requests-2.32.3-py3-none-any.whl.metadata (4.6 kB)
Collecting apscheduler (from -r requirements.txt (line 3))
  Using cached APScheduler-3.11.0-py3-none-any.whl.metadata (6.4 kB)
Collecting openai (from -r requirements.txt (line 4))
  Using cached openai-1.78.1-py3-none-any.whl.metadata (25 kB)
Collecting pytz (from -r requirements.txt (line 5))
  Using cached pytz-2025.2-py2.py3-none-any.whl.metadata (22 kB)
Collecting blinker>=1.9.0 (from flask->-r requirements.txt (line 1))
  Using cached blinker-1.9.0-py3-none-any.whl.metadata (1.6 kB)
Collecting click>=8.1.3 (from flask->-r requirements.txt (line 1))
  Using cached click-8.2.0-py3-none-any.whl.metadata (2.5 kB)
Collecting itsdangerous>=2.2.0 (from flask->-r requirements.txt (line 1))
  Using cached itsdangerous-2.2.0-py3-none-any.whl.metadata (1.9 kB)
Collecting jinja2>=3.1.2 (from flask->-r requirements.txt (line 1))
  Using cached jinja2-3.1.6-py3-none-any.whl.metadata (2.9 kB)
Collecting markupsafe>=2.1.1 (from flask->-r requirements.txt (line 1))
  Using cached MarkupSafe-3.0.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (4.0 kB)
Collecting werkzeug>=3.1.0 (from flask->-r requirements.txt (line 1))
  Using cached werkzeug-3.1.3-py3-none-any.whl.metadata (3.7 kB)
Collecting charset-normalizer<4,>=2 (from requests->-r requirements.txt (line 2))
  Using cached charset_normalizer-3.4.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (35 kB)
Collecting idna<4,>=2.5 (from requests->-r requirements.txt (line 2))
  Using cached idna-3.10-py3-none-any.whl.metadata (10 kB)
Collecting urllib3<3,>=1.21.1 (from requests->-r requirements.txt (line 2))
  Using cached urllib3-2.4.0-py3-none-any.whl.metadata (6.5 kB)
Collecting certifi>=2017.4.17 (from requests->-r requirements.txt (line 2))
  Using cached certifi-2025.4.26-py3-none-any.whl.metadata (2.5 kB)
Collecting tzlocal>=3.0 (from apscheduler->-r requirements.txt (line 3))
  Using cached tzlocal-5.3.1-py3-none-any.whl.metadata (7.6 kB)
Collecting anyio<5,>=3.5.0 (from openai->-r requirements.txt (line 4))
  Using cached anyio-4.9.0-py3-none-any.whl.metadata (4.7 kB)
Collecting distro<2,>=1.7.0 (from openai->-r requirements.txt (line 4))
  Using cached distro-1.9.0-py3-none-any.whl.metadata (6.8 kB)
Collecting httpx<1,>=0.23.0 (from openai->-r requirements.txt (line 4))
  Using cached httpx-0.28.1-py3-none-any.whl.metadata (7.1 kB)
Collecting jiter<1,>=0.4.0 (from openai->-r requirements.txt (line 4))
  Using cached jiter-0.9.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (5.2 kB)
Collecting pydantic<3,>=1.9.0 (from openai->-r requirements.txt (line 4))
  Using cached pydantic-2.11.4-py3-none-any.whl.metadata (66 kB)
Collecting sniffio (from openai->-r requirements.txt (line 4))
  Using cached sniffio-1.3.1-py3-none-any.whl.metadata (3.9 kB)
Collecting tqdm>4 (from openai->-r requirements.txt (line 4))
  Using cached tqdm-4.67.1-py3-none-any.whl.metadata (57 kB)
Collecting typing-extensions<5,>=4.11 (from openai->-r requirements.txt (line 4))
  Using cached typing_extensions-4.13.2-py3-none-any.whl.metadata (3.0 kB)
Collecting httpcore==1.* (from httpx<1,>=0.23.0->openai->-r requirements.txt (line 4))
  Using cached httpcore-1.0.9-py3-none-any.whl.metadata (21 kB)
Collecting h11>=0.16 (from httpcore==1.*->httpx<1,>=0.23.0->openai->-r requirements.txt (line 4))
  Using cached h11-0.16.0-py3-none-any.whl.metadata (8.3 kB)
Collecting annotated-types>=0.6.0 (from pydantic<3,>=1.9.0->openai->-r requirements.txt (line 4))
  Using cached annotated_types-0.7.0-py3-none-any.whl.metadata (15 kB)
Collecting pydantic-core==2.33.2 (from pydantic<3,>=1.9.0->openai->-r requirements.txt (line 4))
  Using cached pydantic_core-2.33.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (6.8 kB)
Collecting typing-inspection>=0.4.0 (from pydantic<3,>=1.9.0->openai->-r requirements.txt (line 4))
  Using cached typing_inspection-0.4.0-py3-none-any.whl.metadata (2.6 kB)
Using cached flask-3.1.1-py3-none-any.whl (103 kB)
Using cached requests-2.32.3-py3-none-any.whl (64 kB)
Using cached APScheduler-3.11.0-py3-none-any.whl (64 kB)
Using cached openai-1.78.1-py3-none-any.whl (680 kB)
Using cached pytz-2025.2-py2.py3-none-any.whl (509 kB)
Using cached anyio-4.9.0-py3-none-any.whl (100 kB)
Using cached blinker-1.9.0-py3-none-any.whl (8.5 kB)
Using cached certifi-2025.4.26-py3-none-any.whl (159 kB)
Using cached charset_normalizer-3.4.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (147 kB)
Using cached click-8.2.0-py3-none-any.whl (102 kB)
Using cached distro-1.9.0-py3-none-any.whl (20 kB)
Using cached httpx-0.28.1-py3-none-any.whl (73 kB)
Using cached httpcore-1.0.9-py3-none-any.whl (78 kB)
Using cached idna-3.10-py3-none-any.whl (70 kB)
Using cached itsdangerous-2.2.0-py3-none-any.whl (16 kB)
Using cached jinja2-3.1.6-py3-none-any.whl (134 kB)
Using cached jiter-0.9.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (351 kB)
Using cached MarkupSafe-3.0.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (23 kB)
Using cached pydantic-2.11.4-py3-none-any.whl (443 kB)
Using cached pydantic_core-2.33.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (2.0 MB)
Using cached sniffio-1.3.1-py3-none-any.whl (10 kB)
Using cached tqdm-4.67.1-py3-none-any.whl (78 kB)
Using cached typing_extensions-4.13.2-py3-none-any.whl (45 kB)
Using cached tzlocal-5.3.1-py3-none-any.whl (18 kB)
Using cached urllib3-2.4.0-py3-none-any.whl (128 kB)
Using cached werkzeug-3.1.3-py3-none-any.whl (224 kB)
Using cached annotated_types-0.7.0-py3-none-any.whl (13 kB)
Using cached typing_inspection-0.4.0-py3-none-any.whl (14 kB)
Using cached h11-0.16.0-py3-none-any.whl (37 kB)
Installing collected packages: pytz, urllib3, tzlocal, typing-extensions, tqdm, sniffio, markupsafe, jiter, itsdangerous, idna, h11, distro, click, charset-normalizer, certifi, blinker, annotated-types, werkzeug, typing-inspection, requests, pydantic-core, jinja2, httpcore, apscheduler, anyio, pydantic, httpx, flask, openai
Successfully installed annotated-types-0.7.0 anyio-4.9.0 apscheduler-3.11.0 blinker-1.9.0 certifi-2025.4.26 charset-normalizer-3.4.2 click-8.2.0 distro-1.9.0 flask-3.1.1 h11-0.16.0 httpcore-1.0.9 httpx-0.28.1 idna-3.10 itsdangerous-2.2.0 jinja2-3.1.6 jiter-0.9.0 markupsafe-3.0.2 openai-1.78.1 pydantic-2.11.4 pydantic-core-2.33.2 pytz-2025.2 requests-2.32.3 sniffio-1.3.1 tqdm-4.67.1 typing-extensions-4.13.2 typing-inspection-0.4.0 tzlocal-5.3.1 urllib3-2.4.0 werkzeug-3.1.3
[notice] A new release of pip is available: 24.0 -> 25.1.1
[notice] To update, run: pip install --upgrade pip
==> Uploading build...
==> Uploaded in 4.5s. Compression took 1.1s
==> Build successful 🎉
==> Deploying...
==> Running 'python main.py'
✅ 스케줄러 시작됨
 * Serving Flask app 'main'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://10.223.32.225:5000
Press CTRL+C to quit
127.0.0.1 - - [16/May/2025 06:07:09] "HEAD / HTTP/1.1" 200 -
==> Your service is live 🎉
127.0.0.1 - - [16/May/2025 06:07:13] "GET / HTTP/1.1" 200 -
127.0.0.1 - - [16/May/2025 06:07:34] "GET /report HTTP/1.1" 404 -
127.0.0.1 - - [16/May/2025 06:07:37] "GET /report HTTP/1.1" 404 -
127.0.0.1 - - [16/May/2025 06:07:38] "GET /report HTTP/1.1" 404 -
127.0.0.1 - - [16/May/2025 06:07:39] "GET /report HTTP/1.1" 404 -
127.0.0.1 - - [16/May/2025 06:07:40] "GET /report HTTP/1.1" 404 -
127.0.0.1 - - [16/May/2025 06:07:42] "GET /report HTTP/1.1" 404 -
127.0.0.1 - - [16/May/2025 06:07:44] "POST /7581311098:AAEr5ZghXGHOLmsduXDlYPZm6l05OULM5nE HTTP/1.1" 200 -
127.0.0.1 - - [16/May/2025 06:07:45] "GET /report HTTP/1.1" 404 -
127.0.0.1 - - [16/May/2025 06:07:48] "POST /7581311098:AAEr5ZghXGHOLmsduXDlYPZm6l05OULM5nE HTTP/1.1" 200 -
127.0.0.1 - - [16/May/2025 06:07:55] "POST /7581311098:AAEr5ZghXGHOLmsduXDlYPZm6l05OULM5nE HTTP/1.1" 200 -
