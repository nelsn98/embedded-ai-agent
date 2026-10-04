from datetime import datetime

def log(msg):

    timestamp = datetime.now()

    print(
        f"[{timestamp}] {msg}"
    )