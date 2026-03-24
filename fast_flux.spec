# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# We need to include the bin/ directory with ffmpeg.exe
added_files = [
    ('bin/ffmpeg.exe', 'bin'),
    ('src/media', 'src/media'),
]

a = Analysis(
    ['src/main.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=['qasync'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PySide2', 'PySide6'],
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
    name='Fast-Flux',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, # Set to True if you want a console window for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/media/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Fast-Flux',
)
