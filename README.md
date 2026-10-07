# Embedded Agent Lab — Day 1 ~ Day 3 完整整合版

> 一個會自己改 code、編譯、燒錄、看日誌的 AI 工程師，控制 ESP32-S3 外接 LED。
> Day 1 完成工具鏈修復，Day 2 接入 Gemini Function Calling，Day 3 實現單一入口實機 Demo。

原始 `.7z` 保持不變；交付 ZIP 不含 `.env`、Git 歷史、建置產物或舊 IDE 設定。

---

## 目錄
- [專案目標與架構](#專案目標與架構)
- [硬體與環境需求](#硬體與環境需求)
- [Day 1：ESP32 工具鏈修復版](#day-1esp32-工具鏈修復版)
- [Day 2：Gemini Function Calling](#day-2gemini-function-calling)
- [Day 3：單一入口實機 Demo](#day-3單一入口實機-demo)
- [通用驗證與常見失敗](#通用驗證與常見失敗)
- [模組與限制](#模組與限制)
- [官方參考](#官方參考)

## 專案目標與架構

**一句話：** 讓 LLM 能透過工具呼叫完成嵌入式開發閉環：讀韌體 → 改參數 → 編譯 → 燒錄 → UART 驗證 → JSON 報告。

**驗收範圍：**
GPIO 控制 → Build → Flash → UART → Verify → JSON Report
日誌測試只驗證軟體行為，未量測引腳電壓或光學輸出。`LED_INTERVAL_MS=500` 表示每 500ms 切換一次，完整亮滅週期 1000ms。

**演進路線：**
- **Day 1：** Deterministic 工具鏈，無 AI。重點是把 Build/Flash/Monitor/Verify 變成可被 AI 調用的穩定 Python 工具。
- **Day 2：** 新增 `agent/gemini_agent.py`，實現真正的 LLM Tool Calling（inspect_firmware, set_led_interval, build_firmware）。
- **Day 3：** 新增 `agent/run_demo.py`，實現單一入口：從改碼到燒錄到驗證，一個指令完成，含 FLASH 二次確認。

## 硬體與環境需求

1.  ESP32-S3 開發板（本版沿用 ESP32-S3 sdkconfig，若晶片不同需先設定 target）
2.  外部 LED：GPIO4 → 220Ω/330Ω 電阻 → LED 長腳；LED 短腳 → GND。本版不控制板載 RGB LED，接線前先拔 USB 電源。
3.  **ESP-IDF PowerShell / ESP-IDF Terminal** 環境，請用已啟用 IDF 的 Python，不要切到其他 Python。
4.  波特率 115200，關閉其他佔用串口的程式（`idf.py monitor` 等）。

## Day 1：ESP32 工具鏈修復版

### Windows 快速開始

1.  將 ZIP 解壓到新資料夾，保留原專案作備份。
2.  在 ESP-IDF Terminal 打開專案根目錄。
3.  接好外部 LED，插回板子。
4.  執行：

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m serial.tools.list_ports
```

預期離線測試全部 PASS（使用合成資料及 Mock 工具，不代表實機通過）。

5.  實機驗收（500ms）：

```powershell
python -m pipeline.run_pipeline --port COM3 --expected-ms 500 --duration 20
```

看到 `MONITOR READY` 後，**立即按一下 EN/RESET**。
工具會要求：BOOT_OK、ON/OFF 交替、至少 10 個完整週期，且所有時間戳間隔為 500 ± 50ms。
期望值由 CLI 提供，驗證器不從原始碼自動推定。

成功顯示 `PASS`，報告位於 `reports/<時間>/report.json` 和 `device.log`。
**請肉眼確認外部 LED 同步亮滅，UART PASS 不能證明電氣正常。**

### 負面驗收：錯誤間隔必須 FAIL

保持韌體 500ms，不改原始碼：

```powershell
python -m pipeline.run_pipeline --port COM3 --expected-ms 1000 --duration 25
```

同樣在 MONITOR READY 後按 RESET，預期 `FAIL: verify`，不是 PASS。

### 手動改成 1000ms（Day 1 無 AI 版）

```powershell
python -c "from tools.file_tools import set_interval; print(set_interval(1000))"
python -m pipeline.run_pipeline --port COM3 --expected-ms 1000 --duration 30
```

再按 RESET 預期 PASS，完整週期變 2 秒。改回 500ms 用 `set_interval(500)`。

Day 1 完成條件：離線 PASS + 實機 500ms PASS + 錯誤期望 1000ms FAIL + 肉眼看到 LED。

## Day 2：Gemini Function Calling

在已通過 Day 1 的專案上合併此補丁。此補丁新增 `agent/gemini_agent.py`，不覆蓋韌體、GPIO、sdkconfig、UART 同步補丁。

### 1. 安裝及離線測試

```powershell
python -m pip install -r requirements-day2.txt
python scripts/run_offline_tests.py
```

預期 30 passed（21 項 Day1 + 9 項 Day2）。測試使用 Mock API / Mock Build / 合成 UART，不呼叫付費 API 或實體設備。

### 2. 設定 Gemini

從 https://aistudio.google.com/apikey 取得 API Key。

```powershell
notepad .env
```

加入：

```dotenv
GEMINI_API_KEY=你的實際金鑰
GEMINI_MODEL=gemini-2.5-flash
```

不要上傳 `.env`，.gitignore 已排除。若有同名環境變數，優先使用環境變數。
免費層資料可能被 Google 用於改善產品，本 Demo 只使用示範韌體。

### 3. 真正的 LLM 工具呼叫

```powershell
python -m agent.gemini_agent --request "將 LED 每次 ON/OFF 切換間隔改成 1000ms，讀取韌體、修改參數並編譯。" --expected-ms 1000
```

預期：

```text
TOOL: inspect_firmware ... -> OK
TOOL: set_led_interval {'interval_ms': 1000} -> OK
TOOL: build_firmware ... -> OK
AGENT BUILD PASS
Report: ...agent_report.json
```

工具順序和編譯成功由 Python 檢查，不依賴模型口頭宣稱。`--expected-ms` 是獨立驗收值，LLM 選值不符會被工具直接拒絕。
此階段只驗證原始碼參數與 Build，尚未 Flash。

1000ms 是切換間隔，完整 ON/OFF 週期為 2000ms。

### 4. 用既有 Pipeline 驗證實體

確認 `AGENT BUILD PASS` 後：

```powershell
python -m pipeline.run_pipeline --port COM4 --expected-ms 1000 --duration 30
```

MONITOR READY 後按一次 RESET，預期 PASS，LED 變慢。

## Day 3：單一入口實機 Demo

將此 ZIP 合併到已完成 Day 2 的專案，需要先前的 Gemini 修正與 UART 同步補丁。此補丁新增 `agent/run_demo.py`。

### 1. 安裝及離線測試

```powershell
python -m pip install -r requirements-day3.txt
python scripts/run_offline_tests.py
```

預期 38 passed，離線不使用 API Key 或設備。

### 2. 第一次單一入口驗收：改回 500ms

目前板子是 1000ms，改回 500ms 方便肉眼對比：

```powershell
python -m agent.run_demo --model gemini-3.8-flash --request "將 LED 每次 ON/OFF 切換間隔改為 500ms，讀取韌體、修改參數並編譯。" --expected-ms 500 --port COM4
```

流程：
1.  Gemini 依序呼叫 inspect_firmware、set_led_interval、build_firmware
2.  出現 `Type FLASH to proceed` 時，輸入大寫 `FLASH` 按 Enter
3.  程式燒錄 COM4；出現 MONITOR READY 後，只按一次 EN/RESET
4.  BOOT_OK captured 後自動採集及驗證
5.  預期顯示 `DEMO PASS` 與統一 report.json 路徑

500ms = 亮 0.5 秒、滅 0.5 秒。輸入其他內容會取消燒錄，保留修改後原始碼、編譯結果及取消報告。程式不會自動還原韌體，report 資料夾留有 source_before.c 備份。

### 3. 第二組驗收：1000ms

```powershell
python -m agent.run_demo --model gemini-3.8-flash --request "將 LED 每次 ON/OFF 切換間隔改為 1000ms，讀取韌體、修改參數並編譯。" --expected-ms 1000 --port COM4
```

同樣輸入 FLASH，MONITOR READY 後按一次 RESET。採集時間依期望間隔自動設定，至少涵蓋 10 個完整週期，可用 --duration 加長時間，過短會在執行前被拒絕。

### 4. 確認失敗情境

在 1000ms 韌體已通過後，故意用錯期望值驗證驗證器：

```powershell
python -m pipeline.run_pipeline --port COM4 --expected-ms 500 --duration 25
```

預期 FAIL: verify。這是獨立設備驗證器的負面 Demo，不是 Agent 自動修復。

## 通用驗證與常見失敗

- **BUILD：** 確認 ESP-IDF terminal 中 `idf.py --version` 能執行，檢查報告 stderr。
- **FLASH：** 確認 COM 埠、USB 資料線、板子連接，串口未被佔用。
- **MONITOR：** 確認波特率 115200、console 的 USB/UART 介面與所選埠一致。
- **VERIFY / boot：** 串口開啟後沒按 RESET，或採集期間設備重啟多次。
- **VERIFY / enough_cycles：** 採集太短或太晚按 RESET，增加 --duration。
- **VERIFY / interval：** 實際韌體間隔與期望不同；先看 intervals_ms，不要直接放寬容差。

## 模組與限制

- `tools/common.py`：使用當前 Python 呼叫 `$IDF_PATH/tools/idf.py`，不透過 Shell。
- `build_tool.py` / `flash_tool.py`：超時與結構化結果。
- `monitor_tool.py`：有限時間採集、關閉串口、回傳斷線錯誤。
- `verify_tool.py`：啟動、順序、週期及時間容差驗證。
- `file_tools.py`：僅能修改固定韌體檔中的單一 LED_INTERVAL_MS，範圍 100–2000。
- `pipeline/run_pipeline.py`：失敗停止，保存報告，無 import 執行副作用。
- `agent/agent.py`：Day 1 deterministic 入口。
- `agent/gemini_agent.py`：Day 2 LLM Tool Calling 入口。
- `agent/run_demo.py`：Day 3 單一入口，含 FLASH 二次確認。

此環境沒有 ESP-IDF 或 ESP32 時，只能跑離線測試；Day 2/3 需要 Gemini API Key，Day 1 不需要。

## 官方參考
- https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/gpio.html
- https://docs.espressif.com/projects/esp-idf/en/release-v5.3/esp32s3/api-reference/system/esp_timer.html
- https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/get-started/start-project.html
