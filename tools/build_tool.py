from tools.common import run_idf

def build(timeout=300):
    return run_idf(["build"], timeout)
