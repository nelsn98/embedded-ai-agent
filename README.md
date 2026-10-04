# Embedded Agent Lab — Day 1

目前完成的是 ESP32 工具鏈修復版，尚未加入 LLM Tool Calling。
原始 `.7z` 保持不變；交付 ZIP 不含 `.env`、Git 歷史、建置產物或舊 IDE 設定。

## 驗收範圍

GPIO 控制 → Build → Flash → UART → Verify → JSON Report。
日誌測試驗證軟體行為，未量測引腳電壓或 LED 光學輸出。
`LED_INTERVAL_MS=500` 表示每 500ms 切換一次，完整亮滅週期為 1000ms。
離線 pytest 使用合成資料及 Mock 工具，不代表實機通過。

## Windows：先完成這一輪

1. 將 ZIP 解壓到新資料夾，保留原專案作備份。
2. 在 **ESP-IDF PowerShell / ESP-IDF Terminal** 打開新資料夾根目錄。
   請用啟用 ESP-IDF 環境的 Python；不要另外切換到缺少 IDF 依賴的 Python 環境。
3. 接外部 LED：GPIO4 → 220Ω 或 330Ω 電阻 → LED 長腳；LED 短腳 → GND。
   請先確認實際開發板型號與接線，GPIO4 為本版範例配置。
   這版不控制板載 RGB LED。接線時先拔除 USB 電源。
4. 插回板子，關閉 `idf.py monitor` 或其他串口程式。
5. 依次執行：

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m serial.tools.list_ports
```

預期離線測試全部通過。從串口列表找到你的板子；下例 `COM3` 請換成實際埠。

```powershell
python -m pipeline.run_pipeline --port COM3 --expected-ms 500 --duration 20
```

看到 `MONITOR READY` 後，立即按一下板子的 **EN/RESET** 按鍵。
工具會採集 20 秒資料，要求 BOOT_OK、ON/OFF 交替、至少 10 個完整週期，
且所有韌體時間戳的切換間隔為 500 ± 50ms。
期望值由 CLI 提供，驗證器不從韌體原始碼自動推定。

成功會顯示 `PASS`，失敗會顯示失敗階段與原因，程式退出碼為 1。
報告及原始日誌位於 `reports/<執行時間>/report.json` 和 `device.log`。
請肉眼確認外部 LED 同時亮滅；UART PASS 仍不能證明電氣或光學輸出正常。

## 負面驗收：錯誤間隔必須 FAIL

保持韌體 500ms，不修改原始碼，執行：

```powershell
python -m pipeline.run_pipeline --port COM3 --expected-ms 1000 --duration 25
```

同樣在 MONITOR READY 後按 RESET。預期 `FAIL: verify`，不是 PASS。

## 改成 1000ms（Day 1 手動工具，尚無 AI）

```powershell
python -c "from tools.file_tools import set_interval; print(set_interval(1000))"
python -m pipeline.run_pipeline --port COM3 --expected-ms 1000 --duration 30
```

再按 RESET，預期 PASS；完整亮滅週期此時為 2 秒。
回到 500ms 可呼叫 `set_interval(500)` 再執行 500ms 驗收。

## 常見失敗

- BUILD：先確認 ESP-IDF terminal 中 `idf.py --version` 能執行，檢查報告 stderr。
- FLASH：確認 COM 埠、USB 資料線、板子連接，以及串口未被其他程式佔用。
- MONITOR：確認波特率 115200、console 的 USB/UART 介面與所選埠一致。
- VERIFY / boot：串口開啟後沒按 RESET，或採集期間設備重啟多次。
- VERIFY / enough_cycles：採集太短或太晚按 RESET，增加 `--duration`。
- VERIFY / interval：實際韌體間隔與期望不同；先看 `intervals_ms`，不要直接放寬容差。

本版沿用原專案的 ESP32-S3 sdkconfig。若實際晶片不同，先確認型號再設定 target。

## 模組與限制

- `tools/common.py`：使用當前 Python 呼叫 `$IDF_PATH/tools/idf.py`，不透過 Shell。
- `build_tool.py` / `flash_tool.py`：超時與結構化結果。
- `monitor_tool.py`：有限時間採集、關閉串口、回傳斷線錯誤。
- `verify_tool.py`：啟動、順序、週期及時間容差驗證。
- `file_tools.py`：僅能修改固定韌體檔中的單一 LED_INTERVAL_MS，範圍 100–2000。
- `pipeline/run_pipeline.py`：失敗停止，保存報告，無 import 執行副作用。
- `agent/agent.py`：修正為 Day 1 deterministic 入口；`python -m agent.agent` 接受相同參數。

此環境沒有 ESP-IDF 或 ESP32；尚未驗證 C 編譯、燒錄和實體 UART。
Day 1 完成條件：離線測試 PASS、實機 500ms PASS、錯誤期望 1000ms FAIL、肉眼看到 LED。
Day 2 再接 LLM；本版不需要 API key。

官方參考：
- https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/gpio.html
- https://docs.espressif.com/projects/esp-idf/en/release-v5.3/esp32s3/api-reference/system/esp_timer.html
- https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/get-started/start-project.html
