# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [
    ('app/templates/index.html', 'app/templates'),
]

try:
    datas += collect_data_files('customtkinter')
except Exception:
    pass

try:
    datas += collect_data_files('tkinterdnd2')
except Exception:
    pass

hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'tkinterdnd2',
    'customtkinter',
    'pystray',
    'plyer',
    'cryptography',
    'zeroconf',
    'psutil',
    'qrcode',
    'PIL',
]

try:
    hiddenimports += collect_submodules('uvicorn')
    hiddenimports += collect_submodules('zeroconf')
    hiddenimports += collect_submodules('fastapi')
except Exception:
    pass

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Webdrop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
