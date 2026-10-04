# Day 2 — Gemini Function Calling

在你已通過 Day 1 正常及負面測試的專案上使用。
將 ZIP 的內容合併到 D:\code\embedded-ai-agent-day1 根目錄，保留 Day 1 的檔案。
此補丁新增 agent/gemini_agent.py；不覆蓋韌體、GPIO、sdkconfig、UART 同步補丁或原有 Agent 入口。

## 1. 安裝

在啟用 ESP-IDF 的 PowerShell、專案根目錄：

```powershell
python -m pip install -r requirements-day2.txt
python scripts/run_offline_tests.py
```

預期 30 passed（21 項 Day 1 + 9 項 Day 2）。
此腳本只在本次程序停用第三方 pytest 自動載入。
測試使用 Mock API、Mock Build 與合成 UART 日誌，沒有呼叫付費 API或實體設備。

## 2. 設定 Gemini

從 https://aistudio.google.com/apikey 取得自己的 Gemini API Key。
使用你可用免費層的專案；免費額度、模型權限以 AI Studio 為準。
官方價格：https://ai.google.dev/gemini-api/docs/pricing
官方配額：https://ai.google.dev/gemini-api/docs/rate-limits

```powershell
notepad .env
```

在本機 .env 加入或更新以下設定；保留其他既有設定：

```dotenv
GEMINI_API_KEY=你的實際金鑰
GEMINI_MODEL=gemini-2.5-flash
```

不要把 .env 上傳或提交。Day 1 .gitignore 已排除它。
若有相同名稱的環境變數，會優先使用環境變數，.env 不會覆蓋它。
免費層資料可能被 Google 用於改善產品；本 Demo 只使用示範韌體，不提交機密程式。

## 3. 真正的 LLM 工具呼叫

```powershell
python -m agent.gemini_agent --request "將 LED 每次 ON/OFF 切換間隔改成 1000ms，讀取韌體、修改參數並編譯。" --expected-ms 1000
```

預期看到：

```text
TOOL: inspect_firmware ... -> OK
TOOL: set_led_interval {'interval_ms': 1000} -> OK
TOOL: build_firmware ... -> OK
AGENT BUILD PASS
Report: ...agent_report.json
```

工具順序和編譯成功由 Python 檢查，不依賴模型的口頭宣稱。
`--expected-ms` 是你根據原始需求設定的獨立驗收值。
LLM 選擇的數值若不符此值，工具直接拒絕，不能改動測試期望。
只有原始碼參數與 Build 已驗證；尚未 Flash 或進行設備驗證。
1000ms 是切換間隔，完整 ON/OFF 週期為 2000ms。

## 4. 用既有 Pipeline 驗證實體設備

確認 AGENT BUILD PASS 後：

```powershell
python -m pipeline.run_pipeline --port COM4 --expected-ms 1000 --duration 30
```

看到 MONITOR READY 後只按一次 EN/RESET。
預期 PASS，LED 比原本慢；這一步才證明修改後韌體已燒錄並通過 UART 驗證。
若實際串口不同，替換 COM4。

## 工具範圍

- inspect_firmware：只讀固定示範韌體。
- set_led_interval：只改 LED_INTERVAL_MS，限制 100–2000ms。
- build_firmware：只執行 ESP-IDF Build。

沒有任意檔案路徑、任意 Shell、自動燒錄或自動修復。
API 輪數最多 8 輪；單次 HTTP 超時 60 秒；Build 沿用 Day 1 超时 300 秒。
發生 API 或工具錯誤立即返回失敗，不自動循環重試。
本地報告保存工具參數、結果、時間與完整 Build 輸出；送回模型的編譯輸出會截短。
保留模型原始 Content 和 thought signature，並對齊 function call ID。

## 故障處理

- GEMINI_API_KEY missing：檢查根目錄 .env 欄位名稱。
- 400：查看 API 錯誤與 SDK 版本。
- 401/403：檢查 Key、API 權限、專案及可用地區。
- 404：檢查該專案可用模型，必要時用 --model 指定模型 ID。
- 429：代表額度或速率限制；查看 AI Studio 配額，等候後手動重試。
- IDF_PATH missing：重新開啟 ESP-IDF Terminal。
- build 失敗：讀 agent_report.json 中 build_firmware 的完整 stdout/stderr。

本次驗證：30 項離線測試通過、Python 語法檢查通過。
尚未用真實 Gemini Key 呼叫 API，亦未在此環境編譯或操作 ESP32。
請先提供執行結果或 agent_report.json；不用提供 .env 或金鑰。
