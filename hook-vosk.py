"""PyInstaller hook for vosk library."""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files('vosk')
hiddenimports = collect_submodules('vosk')
