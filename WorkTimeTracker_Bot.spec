# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\proj vs code\\WorkTimeTracker\\bot_launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[('D:\\proj vs code\\WorkTimeTracker\\config.py', '.'), ('D:\\proj vs code\\WorkTimeTracker\\.env', '.')],
    hiddenimports=['PyQt5', 'PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui', 'telegram_bot', 'telegram_bot.main'],
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
    [],
    exclude_binaries=True,
    name='WorkTimeTracker_Bot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WorkTimeTracker_Bot',
)
