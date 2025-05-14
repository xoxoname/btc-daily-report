@@ def format_profit_report_text(data):
-    return (
-        f"📈 현재 포지션: {data.get('position', '정보 없음')}\n"
-        f"💰 실현 손익: {data.get('realized_pnl', 'N/A')}\n"
-        f"📉 미실현 손익: {data.get('unrealized_pnl', 'N/A')}\n"
-        f"💹 총 손익: {data.get('total_pnl', 'N/A')}\n"
-        f"📊 BTC 현재가 (Coinbase): {data.get('btc_price', 'N/A')}\n"
-        f"🕓 분석 시각: {data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
-    )
+    # 오늘 수익 (실현+미실현). 백엔드에서 KST 자정에 초기화
+    today_pnl = data.get('today_pnl')
+
+    lines = [
+        f"📈 현재 포지션: {data.get('position', '정보 없음')}",
+        f"💰 실현 손익: {data.get('realized_pnl', 'N/A')}",
+        f"📉 미실현 손익: {data.get('unrealized_pnl', 'N/A')}",
+        f"🌅 오늘 수익 (미실현 포함): {today_pnl if today_pnl is not None else '정보 없음'}",
+        f"💹 총 손익: {data.get('total_pnl', 'N/A')}",
+        f"📊 BTC 현재가 (Coinbase): {data.get('btc_price', 'N/A')}",
+        f"🕓 분석 시각: {data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
+    ]
+    return "\n".join(lines)
