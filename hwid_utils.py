# hwid_utils.py

import hashlib
import uuid
import platform

def get_hwid():
    system_info = f"{platform.system()}-{platform.node()}-{platform.machine()}"
    mac = uuid.getnode()
    base = f"{system_info}-{mac}"
    hwid = hashlib.sha256(base.encode()).hexdigest()[:16].upper()
    return hwid

if __name__ == "__main__":
    print(f"HWID: {get_hwid()}")
