# -*- mode: python ; coding: utf-8 -*-
"""T.A.R.O. - PyInstaller Specification (TASK-093).

Builds Windows executable packaging:
- Core engine and safety system
- Capabilities and tools
- UI HTML/JS HUD assets
- Configuration files and templates
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

repo_root = Path.cwd()

# Data files to bundle
datas = [
    ('config', 'config'),
    ('ui', 'ui'),
    ('skills/_templates', 'skills/_templates'),
    ('data', 'data'),
    ('voice/assets', 'voice/assets'),
    # Bundle Vosk STT model
    ('models/vosk-model-small-en-us-0.15', 'models/vosk-model-small-en-us-0.15'),
    # Ensure voice expressions are bundled
    ('voice/assets/expressions', 'voice/assets/expressions'),
]

# Collect submodules
hiddenimports = [
    'core',
    'core.log',
    'core.model',
    'core.model.ollama_auto_starter',
    'core.safety',
    'core.tools',
    'core.skills',
    'core.forge',
    'core.ws',
    'core.analytics',
    'capabilities',
    'capabilities.files',
    'capabilities.system',
    'capabilities.web',
    'capabilities.notes',
    'capabilities.reminders',
    'capabilities.coding',
    'capabilities.office',
    'capabilities.vision',
    'capabilities.training',
    'voice',
    'voice.expressions',
    'winapi',
    'psutil',
    'httpx',
    'aiohttp',
    'websockets',
    'pydantic',
    'yaml',
    'pynput',
    'sounddevice',
    'vosk',
    'capabilities.web.browser_automation',
    'capabilities.office.excel_advanced',
    'capabilities.system.system_advanced',
    'capabilities.system.ui_automation_advanced',
    'capabilities.system.whatsapp_automation',
    'capabilities.system.monitoring',
    'capabilities.memory',
    'capabilities.memory.app_memory',
]

a = Analysis(
    ['main.py'],
    pathex=[str(repo_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='taro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='taro',
)
