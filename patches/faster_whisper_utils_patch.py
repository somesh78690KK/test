"""Patch for faster_whisper utils to work with PyInstaller."""

import sys
import os

# Monkey-patch get_assets_path to work with PyInstaller
original_get_assets_path = None

def patched_get_assets_path():
    """Returns the path to the assets directory, handling PyInstaller bundles."""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        base_path = sys._MEIPASS
        assets_path = os.path.join(base_path, 'faster_whisper', 'assets')
        if os.path.exists(assets_path):
            return assets_path
        # Fallback to original behavior
    return original_get_assets_path()

# Apply the patch
try:
    from faster_whisper import utils
    original_get_assets_path = utils.get_assets_path
    utils.get_assets_path = patched_get_assets_path
except ImportError:
    pass
