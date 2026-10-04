import time
from tools.verify_tool import BOOT


def capture_log(port, duration=20, baud=115200, boot_timeout=20):
    """Wait for a fresh boot, then capture one full observation window.

    Pre-boot traffic stays in raw_log but is excluded from verification.
    Any subsequent reboot is retained so the verifier rejects that run.
    """
    import serial
    if duration <= 0 or boot_timeout <= 0:
        raise ValueError('duration and boot_timeout must be positive')
    raw = []
    lines = []
    pending = ''
    started = False
    try:
        with serial.Serial(port, baud, timeout=0.2) as device:
            # Opening USB-UART may reset the board. Let that startup settle
            # before requesting the explicit reset used for this test run.
            time.sleep(1.0)
            device.reset_input_buffer()
            print('MONITOR READY: press EN/RESET ONCE now; capture starts at BOOT_OK.', flush=True)
            deadline = time.monotonic() + boot_timeout
            while time.monotonic() < deadline:
                chunk = device.readline().decode(errors='replace')
                if not chunk:
                    continue
                raw.append(chunk)
                pending += chunk
                while '\n' in pending:
                    line, pending = pending.split('\n', 1)
                    line = line.rstrip('\r')
                    if not started:
                        if not BOOT.fullmatch(line.strip()):
                            continue
                        started = True
                        deadline = time.monotonic() + duration
                        print('BOOT_OK captured; collecting device events...', flush=True)
                    lines.append(line + '\n')
        return {'success': started, 'log': ''.join(lines), 'raw_log': ''.join(raw),
                'error': '' if started else 'No BOOT_OK received: press EN/RESET after MONITOR READY',
                'capture_duration_s': duration, 'synchronized_to_boot': started}
    except (serial.SerialException, OSError) as exc:
        return {'success': False, 'log': ''.join(lines), 'raw_log': ''.join(raw), 'error': str(exc)}
