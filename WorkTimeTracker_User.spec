# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\proj vs code\\WorkTimeTracker\\user_app\\main.py'],
    pathex=['.'],
    binaries=[],
    datas=[('D:\\proj vs code\\WorkTimeTracker\\config.py', '.'), ('D:\\proj vs code\\WorkTimeTracker\\auto_sync.py', '.'), ('D:\\proj vs code\\WorkTimeTracker\\sheets_api.py', '.'), ('D:\\proj vs code\\WorkTimeTracker\\user_app', 'user_app'), ('D:\\proj vs code\\WorkTimeTracker\\sync', 'sync')],
    hiddenimports=['PyQt5', 'PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui', 'user_app', 'user_app.db_local', 'user_app.gui', 'user_app.login_window', 'auto_sync', 'api_adapter', 'supabase_api', 'sync', 'sync.notifications', 'shared', 'shared.time_utils', 'notifications', 'notifications.engine', 'requests'],
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
    name='WorkTimeTracker_User',
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
    name='WorkTimeTracker_User',
)
