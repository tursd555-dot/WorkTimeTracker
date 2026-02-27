# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('config.py', '.'), ('api_adapter.py', '.'), ('sheets_api.py', '.'), ('supabase_api.py', '.'), ('auto_sync.py', '.'), ('logging_setup.py', '.'), ('shared', 'shared'), ('sync', 'sync'), ('notifications', 'notifications'), ('admin_app', 'admin_app'), ('.env', '.')]
binaries = []
hiddenimports = ['PyQt5.sip', 'gspread', 'google.auth', 'google.oauth2', 'requests', 'sqlite3', 'cryptography', 'pyzipper', 'dotenv', 'supabase', 'supabase.client', 'supabase._sync', 'postgrest', 'realtime', 'api_adapter', 'supabase_api', 'sheets_api', 'httpx', 'httpx._client', 'httpx._transports', 'httpx._config', 'certifi', 'ssl', 'admin_app', 'admin_app.repo', 'admin_app.break_manager', 'shared', 'shared.time_utils']
hiddenimports += collect_submodules('httpx')
hiddenimports += collect_submodules('supabase')
tmp_ret = collect_all('certifi')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['admin_app\\realtime_monitor.py'],
    pathex=['.'],
    binaries=binaries,
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
    [],
    exclude_binaries=True,
    name='WorkTimeTracker_Monitor',
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
    name='WorkTimeTracker_Monitor',
)
