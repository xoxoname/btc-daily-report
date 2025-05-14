
Search

Live tail
GMT+9

Menu
==> Cloning from https://github.com/xoxoname/btc-daily-report
==> Checking out commit 8279129ad8a62b672a7dff82879b4de24ad4c93e in branch main
==> Downloading cache...
==> Using Python version 3.11.11 (default)
==> Docs on specifying a Python version: https://render.com/docs/python-version
==> Transferred 114MB in 7s. Extraction took 2s.
==> Using Poetry version 1.7.1 (default)
==> Docs on specifying a Poetry version: https://render.com/docs/poetry-version
==> Running build command 'pip install -r requirements.txt'...
Collecting flask==2.3.2 (from -r requirements.txt (line 1))
  Using cached Flask-2.3.2-py3-none-any.whl.metadata (3.7 kB)
Collecting ccxt==4.4.82 (from -r requirements.txt (line 2))
  Using cached ccxt-4.4.82-py2.py3-none-any.whl.metadata (129 kB)
Collecting requests>=2.18.4 (from -r requirements.txt (line 3))
  Using cached requests-2.32.3-py3-none-any.whl.metadata (4.6 kB)
Collecting apscheduler==3.10.4 (from -r requirements.txt (line 4))
  Using cached APScheduler-3.10.4-py3-none-any.whl.metadata (5.7 kB)
Collecting python-telegram-bot==20.7 (from -r requirements.txt (line 5))
  Using cached python_telegram_bot-20.7-py3-none-any.whl.metadata (15 kB)
Collecting openai==1.14.3 (from -r requirements.txt (line 6))
  Using cached openai-1.14.3-py3-none-any.whl.metadata (20 kB)
Collecting python-dotenv==1.0.1 (from -r requirements.txt (line 7))
  Using cached python_dotenv-1.0.1-py3-none-any.whl.metadata (23 kB)
Collecting Werkzeug>=2.3.3 (from flask==2.3.2->-r requirements.txt (line 1))
  Using cached werkzeug-3.1.3-py3-none-any.whl.metadata (3.7 kB)
Collecting Jinja2>=3.1.2 (from flask==2.3.2->-r requirements.txt (line 1))
  Using cached jinja2-3.1.6-py3-none-any.whl.metadata (2.9 kB)
Collecting itsdangerous>=2.1.2 (from flask==2.3.2->-r requirements.txt (line 1))
  Using cached itsdangerous-2.2.0-py3-none-any.whl.metadata (1.9 kB)
Collecting click>=8.1.3 (from flask==2.3.2->-r requirements.txt (line 1))
  Using cached click-8.2.0-py3-none-any.whl.metadata (2.5 kB)
Collecting blinker>=1.6.2 (from flask==2.3.2->-r requirements.txt (line 1))
  Using cached blinker-1.9.0-py3-none-any.whl.metadata (1.6 kB)
Requirement already satisfied: setuptools>=60.9.0 in ./.venv/lib/python3.11/site-packages (from ccxt==4.4.82->-r requirements.txt (line 2)) (65.5.0)
Collecting certifi>=2018.1.18 (from ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached certifi-2025.4.26-py3-none-any.whl.metadata (2.5 kB)
Collecting cryptography>=2.6.1 (from ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached cryptography-44.0.3-cp39-abi3-manylinux_2_34_x86_64.whl.metadata (5.7 kB)
Collecting typing-extensions>=4.4.0 (from ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached typing_extensions-4.13.2-py3-none-any.whl.metadata (3.0 kB)
Collecting aiohttp<=3.10.11 (from ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached aiohttp-3.10.11-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (7.7 kB)
Collecting aiodns>=1.1.1 (from ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached aiodns-3.4.0-py3-none-any.whl.metadata (4.7 kB)
Collecting yarl>=1.7.2 (from ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached yarl-1.20.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (72 kB)
Collecting six>=1.4.0 (from apscheduler==3.10.4->-r requirements.txt (line 4))
  Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
Collecting pytz (from apscheduler==3.10.4->-r requirements.txt (line 4))
  Using cached pytz-2025.2-py2.py3-none-any.whl.metadata (22 kB)
Collecting tzlocal!=3.*,>=2.0 (from apscheduler==3.10.4->-r requirements.txt (line 4))
  Using cached tzlocal-5.3.1-py3-none-any.whl.metadata (7.6 kB)
Collecting httpx~=0.25.2 (from python-telegram-bot==20.7->-r requirements.txt (line 5))
  Using cached httpx-0.25.2-py3-none-any.whl.metadata (6.9 kB)
Collecting anyio<5,>=3.5.0 (from openai==1.14.3->-r requirements.txt (line 6))
  Using cached anyio-4.9.0-py3-none-any.whl.metadata (4.7 kB)
Collecting distro<2,>=1.7.0 (from openai==1.14.3->-r requirements.txt (line 6))
  Using cached distro-1.9.0-py3-none-any.whl.metadata (6.8 kB)
Collecting pydantic<3,>=1.9.0 (from openai==1.14.3->-r requirements.txt (line 6))
  Using cached pydantic-2.11.4-py3-none-any.whl.metadata (66 kB)
Collecting sniffio (from openai==1.14.3->-r requirements.txt (line 6))
  Using cached sniffio-1.3.1-py3-none-any.whl.metadata (3.9 kB)
Collecting tqdm>4 (from openai==1.14.3->-r requirements.txt (line 6))
  Using cached tqdm-4.67.1-py3-none-any.whl.metadata (57 kB)
Collecting charset-normalizer<4,>=2 (from requests>=2.18.4->-r requirements.txt (line 3))
  Using cached charset_normalizer-3.4.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (35 kB)
Collecting idna<4,>=2.5 (from requests>=2.18.4->-r requirements.txt (line 3))
  Using cached idna-3.10-py3-none-any.whl.metadata (10 kB)
Collecting urllib3<3,>=1.21.1 (from requests>=2.18.4->-r requirements.txt (line 3))
  Using cached urllib3-2.4.0-py3-none-any.whl.metadata (6.5 kB)
Collecting pycares>=4.0.0 (from aiodns>=1.1.1->ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached pycares-4.8.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (4.3 kB)
Collecting aiohappyeyeballs>=2.3.0 (from aiohttp<=3.10.11->ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached aiohappyeyeballs-2.6.1-py3-none-any.whl.metadata (5.9 kB)
Collecting aiosignal>=1.1.2 (from aiohttp<=3.10.11->ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached aiosignal-1.3.2-py2.py3-none-any.whl.metadata (3.8 kB)
Collecting attrs>=17.3.0 (from aiohttp<=3.10.11->ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached attrs-25.3.0-py3-none-any.whl.metadata (10 kB)
Collecting frozenlist>=1.1.1 (from aiohttp<=3.10.11->ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached frozenlist-1.6.0-cp311-cp311-manylinux_2_5_x86_64.manylinux1_x86_64.manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (16 kB)
Collecting multidict<7.0,>=4.5 (from aiohttp<=3.10.11->ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached multidict-6.4.3-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (5.3 kB)
Collecting cffi>=1.12 (from cryptography>=2.6.1->ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached cffi-1.17.1-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (1.5 kB)
Collecting httpcore==1.* (from httpx~=0.25.2->python-telegram-bot==20.7->-r requirements.txt (line 5))
  Using cached httpcore-1.0.9-py3-none-any.whl.metadata (21 kB)
Collecting h11>=0.16 (from httpcore==1.*->httpx~=0.25.2->python-telegram-bot==20.7->-r requirements.txt (line 5))
  Using cached h11-0.16.0-py3-none-any.whl.metadata (8.3 kB)
Collecting MarkupSafe>=2.0 (from Jinja2>=3.1.2->flask==2.3.2->-r requirements.txt (line 1))
  Using cached MarkupSafe-3.0.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (4.0 kB)
Collecting annotated-types>=0.6.0 (from pydantic<3,>=1.9.0->openai==1.14.3->-r requirements.txt (line 6))
  Using cached annotated_types-0.7.0-py3-none-any.whl.metadata (15 kB)
Collecting pydantic-core==2.33.2 (from pydantic<3,>=1.9.0->openai==1.14.3->-r requirements.txt (line 6))
  Using cached pydantic_core-2.33.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (6.8 kB)
Collecting typing-inspection>=0.4.0 (from pydantic<3,>=1.9.0->openai==1.14.3->-r requirements.txt (line 6))
  Using cached typing_inspection-0.4.0-py3-none-any.whl.metadata (2.6 kB)
Collecting propcache>=0.2.1 (from yarl>=1.7.2->ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached propcache-0.3.1-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (10 kB)
Collecting pycparser (from cffi>=1.12->cryptography>=2.6.1->ccxt==4.4.82->-r requirements.txt (line 2))
  Using cached pycparser-2.22-py3-none-any.whl.metadata (943 bytes)
Using cached Flask-2.3.2-py3-none-any.whl (96 kB)
Using cached ccxt-4.4.82-py2.py3-none-any.whl (5.8 MB)
Using cached APScheduler-3.10.4-py3-none-any.whl (59 kB)
Using cached python_telegram_bot-20.7-py3-none-any.whl (552 kB)
Using cached openai-1.14.3-py3-none-any.whl (262 kB)
Using cached python_dotenv-1.0.1-py3-none-any.whl (19 kB)
Using cached requests-2.32.3-py3-none-any.whl (64 kB)
Using cached aiodns-3.4.0-py3-none-any.whl (7.1 kB)
Using cached aiohttp-3.10.11-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (1.3 MB)
Using cached anyio-4.9.0-py3-none-any.whl (100 kB)
Using cached blinker-1.9.0-py3-none-any.whl (8.5 kB)
Using cached certifi-2025.4.26-py3-none-any.whl (159 kB)
Using cached charset_normalizer-3.4.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (147 kB)
Using cached click-8.2.0-py3-none-any.whl (102 kB)
Using cached cryptography-44.0.3-cp39-abi3-manylinux_2_34_x86_64.whl (4.2 MB)
Using cached distro-1.9.0-py3-none-any.whl (20 kB)
Using cached httpx-0.25.2-py3-none-any.whl (74 kB)
Using cached httpcore-1.0.9-py3-none-any.whl (78 kB)
Using cached idna-3.10-py3-none-any.whl (70 kB)
Using cached itsdangerous-2.2.0-py3-none-any.whl (16 kB)
Using cached jinja2-3.1.6-py3-none-any.whl (134 kB)
Using cached pydantic-2.11.4-py3-none-any.whl (443 kB)
Using cached pydantic_core-2.33.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (2.0 MB)
Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
Using cached sniffio-1.3.1-py3-none-any.whl (10 kB)
Using cached tqdm-4.67.1-py3-none-any.whl (78 kB)
Using cached typing_extensions-4.13.2-py3-none-any.whl (45 kB)
Using cached tzlocal-5.3.1-py3-none-any.whl (18 kB)
Using cached urllib3-2.4.0-py3-none-any.whl (128 kB)
Using cached werkzeug-3.1.3-py3-none-any.whl (224 kB)
Using cached yarl-1.20.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (358 kB)
Using cached pytz-2025.2-py2.py3-none-any.whl (509 kB)
Using cached aiohappyeyeballs-2.6.1-py3-none-any.whl (15 kB)
Using cached aiosignal-1.3.2-py2.py3-none-any.whl (7.6 kB)
Using cached annotated_types-0.7.0-py3-none-any.whl (13 kB)
Using cached attrs-25.3.0-py3-none-any.whl (63 kB)
Using cached cffi-1.17.1-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (467 kB)
Using cached frozenlist-1.6.0-cp311-cp311-manylinux_2_5_x86_64.manylinux1_x86_64.manylinux_2_17_x86_64.manylinux2014_x86_64.whl (313 kB)
Using cached MarkupSafe-3.0.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (23 kB)
Using cached multidict-6.4.3-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (223 kB)
Using cached propcache-0.3.1-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (232 kB)
Using cached pycares-4.8.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (626 kB)
Using cached typing_inspection-0.4.0-py3-none-any.whl (14 kB)
Using cached h11-0.16.0-py3-none-any.whl (37 kB)
Using cached pycparser-2.22-py3-none-any.whl (117 kB)
Installing collected packages: pytz, urllib3, tzlocal, typing-extensions, tqdm, sniffio, six, python-dotenv, pycparser, propcache, multidict, MarkupSafe, itsdangerous, idna, h11, frozenlist, distro, click, charset-normalizer, certifi, blinker, attrs, annotated-types, aiohappyeyeballs, yarl, Werkzeug, typing-inspection, requests, pydantic-core, Jinja2, httpcore, cffi, apscheduler, anyio, aiosignal, pydantic, pycares, httpx, flask, cryptography, aiohttp, python-telegram-bot, openai, aiodns, ccxt
Successfully installed Jinja2-3.1.6 MarkupSafe-3.0.2 Werkzeug-3.1.3 aiodns-3.4.0 aiohappyeyeballs-2.6.1 aiohttp-3.10.11 aiosignal-1.3.2 annotated-types-0.7.0 anyio-4.9.0 apscheduler-3.10.4 attrs-25.3.0 blinker-1.9.0 ccxt-4.4.82 certifi-2025.4.26 cffi-1.17.1 charset-normalizer-3.4.2 click-8.2.0 cryptography-44.0.3 distro-1.9.0 flask-2.3.2 frozenlist-1.6.0 h11-0.16.0 httpcore-1.0.9 httpx-0.25.2 idna-3.10 itsdangerous-2.2.0 multidict-6.4.3 openai-1.14.3 propcache-0.3.1 pycares-4.8.0 pycparser-2.22 pydantic-2.11.4 pydantic-core-2.33.2 python-dotenv-1.0.1 python-telegram-bot-20.7 pytz-2025.2 requests-2.32.3 six-1.17.0 sniffio-1.3.1 tqdm-4.67.1 typing-extensions-4.13.2 typing-inspection-0.4.0 tzlocal-5.3.1 urllib3-2.4.0 yarl-1.20.0
[notice] A new release of pip is available: 24.0 -> 25.1.1
[notice] To update, run: pip install --upgrade pip
==> Uploading build...
==> Uploaded in 4.4s. Compression took 1.3s
==> Build successful 🎉
==> Deploying...
==> Running 'python main.py'
Exception in thread Thread-1 (run_bot):
Traceback (most recent call last):
  File "/usr/local/lib/python3.11/asyncio/unix_events.py", line 105, in add_signal_handler
    signal.set_wakeup_fd(self._csock.fileno())
ValueError: set_wakeup_fd only works in main thread of the main interpreter
During handling of the above exception, another exception occurred:
Traceback (most recent call last):
  File "/usr/local/lib/python3.11/threading.py", line 1045, in _bootstrap_inner
    self.run()
  File "/usr/local/lib/python3.11/threading.py", line 982, in run
    self._target(*self._args, **self._kwargs)
  File "/opt/render/project/src/main.py", line 63, in run_bot
    application.run_polling()
  File "/opt/render/project/src/.venv/lib/python3.11/site-packages/telegram/ext/_application.py", line 818, in run_polling
    return self.__run(
           ^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.11/site-packages/telegram/ext/_application.py", line 985, in __run
    loop.add_signal_handler(sig, self._raise_system_exit)
  File "/usr/local/lib/python3.11/asyncio/unix_events.py", line 107, in add_signal_handler
    raise RuntimeError(str(exc))
RuntimeError: set_wakeup_fd only works in main thread of the main interpreter
/usr/local/lib/python3.11/threading.py:1047: RuntimeWarning: coroutine 'Updater.start_polling' was never awaited
  self._invoke_excepthook(self)
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
 * Serving Flask app 'main'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:10000
 * Running on http://10.223.230.37:10000
Press CTRL+C to quit
127.0.0.1 - - [14/May/2025 15:30:36] "HEAD / HTTP/1.1" 200 -
==> Your service is live 🎉
127.0.0.1 - - [14/May/2025 15:30:38] "GET / HTTP/1.1" 200 -
