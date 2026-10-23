import ctypes
import os
import sys

def test_mci(filepath):
    path = os.path.abspath(filepath)
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return False
    alias = "voice_sample"
    ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)
    ret = ctypes.windll.winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, None)
    print(f"Open result: {ret}")
    if ret == 0:
        buf = ctypes.create_unicode_buffer(128)
        ctypes.windll.winmm.mciSendStringW(f'status {alias} length', buf, 128, None)
        print(f"Duration (ms): {buf.value}")
        ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)
        return True
    return False

if __name__ == "__main__":
    test_mci("voice/assets/expressions/expression_sample_1.mp3")
