# aes_hls.py

import os
import secrets
from datetime import datetime

KEY_DIR = "keys"
KEY_FILENAME = "enc.key"
KEY_INFO_FILENAME = "enc.keyinfo"

class AESHLSManager:
    def __init__(self, output_dir=KEY_DIR):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_key(self):
        key = secrets.token_bytes(16)  # AES-128
        key_path = os.path.join(self.output_dir, KEY_FILENAME)
        with open(key_path, "wb") as f:
            f.write(key)
        print(f"[INFO] Neuer AES-Key generiert: {key.hex()}")
        return key.hex()

    def write_keyinfo(self, base_url="http://localhost/keys/"):
        key_uri = base_url + KEY_FILENAME
        key_path = os.path.join(self.output_dir, KEY_FILENAME)
        key_info_path = os.path.join(self.output_dir, KEY_INFO_FILENAME)

        with open(key_info_path, "w") as f:
            f.write(f"{key_uri}\n")
            f.write(f"{key_path}\n")
            f.write(f"{secrets.token_hex(16)}\n")  # IV (random)

        print(f"[INFO] Keyinfo-Datei erstellt: {key_info_path}")
        return key_info_path

    def rotate_key(self):
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        new_key_file = os.path.join(self.output_dir, f"enc_{now}.key")
        key = secrets.token_bytes(16)
        with open(new_key_file, "wb") as f:
            f.write(key)
        print(f"[INFO] Key-Rotation durchgeführt: {new_key_file}")
        return new_key_file
