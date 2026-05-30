# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['../main.py'],
    pathex=['..'],
    binaries=[
        ('../resources/bin/*.dll', 'resources/bin'),
        ('../resources/bin/*.exe', 'resources/bin'),
    ],
    datas=[
        ('../resources/styles/*.qss', 'resources/styles'),
        ('../resources/version.txt', 'resources'),
        # --- Translations ---
        ('../resources/translations/*.json', 'resources/translations'),
        # --- icons ---
        ('../resources/icons/*.png', 'resources/icons'),
        ('../resources/icons/*.ico', 'resources/icons'),
    ],
    hiddenimports=[
        'scanner',
        'updater',
        'update_dialog',
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
        'numpy',
        'matplotlib',
        'PyQt6.QtPdf',
        'PyQt6.QtNetwork',
        'PyQt6.QtQml',
        'PyQt6.QtQuick',
        'PyQt6.QtSql',
        'PyQt6.QtTest',
        'PyQt6.QtXml',
        'PyQt6.Qt3D',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebChannel',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

# Exclude Qt6 standard translation files (~6MB) to save space
a.datas = [x for x in a.datas if 'pyqt6/qt6/translations' not in x[1].lower().replace('\\', '/')]

# Exclude large unused binaries to save space
a.binaries = [x for x in a.binaries if not (
    x[0].lower().endswith('opengl32sw.dll') or 
    x[0].lower().endswith('qt6pdf.dll') or 
    x[0].lower().endswith('qt6network.dll')
)]

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
