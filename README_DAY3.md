# Day 3：單一入口實機 Demo

將此 ZIP 內容合併到已完成 Day 2 的專案根目錄。
需要先前的 Gemini 3.8 修正與 UART 同步補丁。這個補丁新增 agent/run_demo.py。

## 安裝及離線測試

在 ESP-IDF Terminal、專案根目錄：

```powershell
python -m pip install -r requirements-day3.txt
python scripts/run_offline_tests.py
```

預期 38 passed。離線測試不使用 API Key 或真實設備。

## 第一次單一入口驗收：改回 500ms

目前板子已驗證 1000ms，這次改回 500ms，方便肉眼觀察差異。

```powershell
python -m agent.run_demo --model gemini-3.8-flash --request "將 LED 每次 ON/OFF 切換間隔改為 500ms，讀取韌體、修改參數並編譯。" --expected-ms 500 --port COM4
```

執行流程：
1. Gemini 依序呼叫 inspect_firmware、set_led_interval、build_firmware。
2. 畫面出現 `Type FLASH to proceed` 時，輸入大寫 `FLASH` 並按 Enter。
3. 程式燒錄 COM4；出現 MONITOR READY 後，只按一次 EN/RESET。
4. BOOT_OK captured 後，自動採集及驗證。
5. 預期顯示 `DEMO PASS` 與統一 report.json 路徑。

500ms 代表亮 0.5 秒、滅 0.5 秒。
輸入其他內容會取消燒錄，保留修改後原始碼、編譯結果及取消報告。
程式不會自動還原韌體檔案；report 資料夾留有 source_before.c 備份。

## 第二組驗收：1000ms

```powershell
python -m agent.run_demo --model gemini-3.8-flash --request "將 LED 每次 ON/OFF 切換間隔改為 1000ms，讀取韌體、修改參數並編譯。" --expected-ms 1000 --port COM4
```

同樣輸入 FLASH，並在 MONITOR READY 後按一次 RESET。
採集時間會依期望間隔自動設定，至少涵蓋 10 個完整亮滅週期。
可使用 --duration 加長時間；過短的時間會在執行前被拒絕。

## 確認失敗情境

在 1000ms 韌體已通過後，可用既有 Pipeline 故意要求 500ms：

```powershell
python -m pipeline.run_pipeline --port COM4 --expected-ms 500 --duration 25
```

預期 FAIL: verify。這是独立設備驗證器的負面 Demo，不是 Agent 自動修復。
燒錄取消、Agent 失敗、設備失敗的流程控制另有離線測試。

## 統一證據

每次執行建立 reports/demo_<UTC時間>/：

| 檔案 | 內容 |
| --- | --- |
| report.json | 原始需求、獨立驗收值、Agent 工具紀錄、燒錄確認、設備及驗證結果 |
| summary.md | 便於閱讀的結果摘要 |
| source_before.c | 執行前的韌體備份 |
| source_after.c | Agent 執行後的韌體快照 |
| device.log | 本次啟動後的驗證日誌 |
| raw_device.log | 同步前後的原始採集文字 |

report.json 在各階段寫入；一般例外、Ctrl+C 或取消會保存失敗／取消狀態。
若作業系統直接終止程序，可能留下最後一次 running 紀錄，不能視為成功。
裝置未連接或 API 權限不足仍須在實際環境診斷。
退出碼：0=PASS；1=FAIL；2=取消。

## 實際邊界

Gemini 負責讀取、改參數與 Build；Python 主流程負責燒錄確認、Flash、UART、驗證與最終判定。
需手動輸入 FLASH 及按一次 RESET。UART 日誌不是 GPIO 電壓或光學量測。
Day 3 整合版尚待使用者實機驗收；先前 Day 1 的 500ms 和 Day 2 的 1000ms 分段流程已通過。
