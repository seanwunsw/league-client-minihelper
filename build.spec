# PyInstaller spec file for LoL Helper
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main_ui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.yaml', '.'),
        ('ui/index.html', 'ui'),
        ('ui/style.css', 'ui'),
        ('ui/app.js', 'ui'),
        ('ui/combobox.css', 'ui'),
        ('ui/combobox.js', 'ui'),
        ('assets/icon.ico', 'assets'),
        ('assets/icon_square.png', 'assets'),
        ('data/champion_data_fallback.json', 'data'),
    ],
    hiddenimports=[
        'websocket',
        'yaml',
        'psutil',
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'webview',
        'webview.platforms.winforms',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'IPython', 'jupyter', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LoLAutoAccept',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    # uac_admin=False: asInvoker, not requireAdministrator. There is no
    # application manifest requesting elevation. Start-with-Windows therefore
    # uses HKCU\Software\Microsoft\Windows\CurrentVersion\Run (see
    # core/windows_startup.py). If you enable uac_admin, also set
    # REQUIRES_ADMIN_ELEVATION there to True: a Run key will not elevate
    # silently at logon, so registration must use a highest-privileges
    # Task Scheduler logon task instead.
    uac_admin=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',  # Application icon
)
