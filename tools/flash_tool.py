from tools.common import run_idf

def flash(port, timeout=120):
    return run_idf(["-p", port, "flash"], timeout)
