# Day 1 validation

18 offline tests passed (pytest). Python syntax compilation passed.
Missing ESP-IDF environment correctly fails at BUILD, exits with code 1,
and saves a JSON failure report without attempting FLASH.

Tests use synthetic UART logs and mocked hardware/toolchain interfaces.
ESP-IDF C compilation, flashing, real UART timing and physical LED operation
have NOT been verified in this environment.

Remaining local acceptance:
1. Offline pytest: 18 passed.
2. Real device, expected 500ms: PASS (press RESET after MONITOR READY).
3. Same firmware, expected 1000ms: FAIL at verify.
4. Visual confirmation of external LED toggling.

No LLM integration is included in Day 1.
