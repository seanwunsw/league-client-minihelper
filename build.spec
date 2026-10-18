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
        ('assets/icon.ico', 'assets'),
        ('assets/icon_square.png', 'assets'),
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
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',  # Application icon
)
