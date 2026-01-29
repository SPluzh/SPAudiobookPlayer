# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['../main.py'],
    pathex=['..'],
    binaries=[
        ('../resources/bin/bass.dll', 'resources/bin'),
        ('../resources/bin/bass_fx.dll', 'resources/bin'),
        ('../resources/bin/ffprobe.exe', 'resources/bin'),
    ],
    datas=[
        ('../resources/styles/dark.qss', 'resources/styles'),
        ('../resources/version.txt', 'resources'),
        # --- Translations ---
        ('../resources/translations/ru.json', 'resources/translations'),
        ('../resources/translations/en.json', 'resources/translations'),
        # --- icons ---
        ('../resources/icons/*.png', 'resources/icons'),
        ('../resources/icons/*.ico', 'resources/icons'),
    ],
    hiddenimports=[
        'scanner',
        'mutagen.mp3',
        'mutagen.mp4',
        'mutagen.flac',
        'mutagen.oggvorbis',
        'mutagen.wave',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'xmlrpc',
        'pydoc',
        'lib2to3',
        'pdb',
        'distutils',
        'setuptools',
        'multiprocessing',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SP Audiobook Player',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='../resources/icons/app_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=['bass.dll', 'bass_fx.dll'],
    name='SP Audiobook Player',
)
