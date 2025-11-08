# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PySide6 import QtCore

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(SPEC))

# Main script
main_script = os.path.join(current_dir, 'Converter.py')

# Analysis
a = Analysis(
    [main_script],
    pathex=[current_dir],
    binaries=[],
    datas=[
        ('zip.png', '.'),
        ('zipd.png', '.'),
        ('AppIcon.png', '.'),
        ('AppIcond.png', '.'),
        ('AppIcon.icns', '.'),
        ('qss', 'qss'),
        ('support/CLI/Darwin', 'support/CLI/Darwin'),
        ('update', 'update'),
    ],
    hiddenimports=[
        'arc_gui',
        'image_converter',
        'support',
        'update',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'QtWebEngineCore',
        'QtWebEngineWidgets',
        'QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngine',
    ],
    noarchive=False,
)

# PYZ
pyz = PYZ(a.pure)

# EXE
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Converter',
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

# COLLECT
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Converter',
)

# Create macOS app bundle
app = BUNDLE(
    coll,
    name='Converter.app',
    icon=os.path.join(current_dir, 'AppIcon.icns'),
    bundle_identifier='com.pyquick.converter',
    info_plist={
        'CFBundleDisplayName': 'Converter',
        'CFBundleExecutable': 'Converter',
        'CFBundleIconFile': 'AppIcon.icns',
        'CFBundleIdentifier': 'com.pyquick.converter',
        'CFBundleInfoDictionaryVersion': '6.0',
        'CFBundleName': 'Converter',
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': '2.0',
        'CFBundleVersion': '2.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13',
    },
    version='2.0',
)