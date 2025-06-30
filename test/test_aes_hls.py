import os
import sys
import tempfile
import pytest

# Ensure the project root is in the path to import aes_hls
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from aes_hls import AESHLSManager


def test_generate_key_creates_file_and_returns_hex():
    with tempfile.TemporaryDirectory() as tmp_dir:
        manager = AESHLSManager(output_dir=tmp_dir)
        returned_key = manager.generate_key()
        key_path = os.path.join(tmp_dir, 'enc.key')

        assert os.path.isfile(key_path), 'enc.key should exist'
        assert isinstance(returned_key, str)
        assert len(returned_key) == 32
        # ensure returned string is hex
        int(returned_key, 16)