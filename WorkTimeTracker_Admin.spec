# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('D:\\proj vs code\\WorkTimeTracker\\config.py', '.')]
binaries = []
hiddenimports = ['auto_sync', 'sheets_api', 'supabase_api', 'user_app.db_local', 'admin_app', 'admin_app.repo', 'admin_app.break_manager', 'admin_app.reports_tab', 'shared', 'sync', 'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui', 'openpyxl', 'openpyxl.styles', 'openpyxl.styles.fonts', 'openpyxl.styles.fills', 'openpyxl.styles.alignment', 'openpyxl.styles.borders', 'openpyxl.utils', 'openpyxl.utils.datetime', 'openpyxl.workbook', 'openpyxl.worksheet', 'openpyxl.cell', 'openpyxl.cell.cell', 'openpyxl.cell.text', 'et_xmlfile', 'supabase', 'supabase.client', 'postgrest', 'realtime']
tmp_ret = collect_all('openpyxl')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['D:\\proj vs code\\WorkTimeTracker\\admin_app\\main_admin.py'],
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
    name='WorkTimeTracker_Admin',
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
    name='WorkTimeTracker_Admin',
)
