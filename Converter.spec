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
        'qfluentwidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtSvg',
        'PyQt5.QtPrintSupport',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebChannel',
        'PyQt5.QtWebSockets',
        'PyQt5.QtMultimedia',
        'tkinter',
        # WebEngine modules (not used)
        'QtWebEngineCore',
        'QtWebEngineWidgets',
        'QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngine',
        
        # Multimedia modules (not used)
        'QtMultimedia',
        'QtMultimediaWidgets',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        
        # Network modules (not used)
        'QtNetwork',
        'PySide6.QtNetwork',
        
        # Bluetooth modules (not used)
        'QtBluetooth',
        'PySide6.QtBluetooth',
        
        # Positioning modules (not used)
        'QtPositioning',
        'PySide6.QtPositioning',
        
        # Sensors modules (not used)
        'QtSensors',
        'PySide6.QtSensors',
        
        # SerialPort modules (not used)
        'QtSerialPort',
        'PySide6.QtSerialPort',
        
        # WebChannel modules (not used)
        'QtWebChannel',
        'PySide6.QtWebChannel',
        
        # 3D modules (not used)
        'Qt3DCore',
        'Qt3DExtras',
        'Qt3DInput',
        'Qt3DLogic',
        'Qt3DRender',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DRender',
        
        # Quick modules (not used)
        'QtQuick',
        'QtQuickWidgets',
        'QtQuickControls2',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtQuickControls2',
        
        # Charts modules (not used)
        'QtCharts',
        'PySide6.QtCharts',
        
        # DataVisualization modules (not used)
        'QtDataVisualization',
        'PySide6.QtDataVisualization',
        
        # TextToSpeech modules (not used)
        'QtTextToSpeech',
        'PySide6.QtTextToSpeech',
        
        # Speech modules (not used)
        'QtSpeech',
        'PySide6.QtSpeech',
        
        # WebSockets modules (not used)
        'QtWebSockets',
        'PySide6.QtWebSockets',
        
        # RemoteObjects modules (not used)
        'QtRemoteObjects',
        'PySide6.QtRemoteObjects',
        
        # Help modules (not used)
        'QtHelp',
        'PySide6.QtHelp',
        
        # Script modules (not used)
        'QtScript',
        'PySide6.QtScript',
        
        # ScriptTools modules (not used)
        'QtScriptTools',
        'PySide6.QtScriptTools',
        
        # SCXML modules (not used)
        'QtScxml',
        'PySide6.QtScxml',
        
        # StateMachine modules (not used)
        'QtStateMachine',
        'PySide6.QtStateMachine',
        
        # Concurrent modules (not used)
        'QtConcurrent',
        'PySide6.QtConcurrent',
        
        # OpenGL modules (not used)
        'QtOpenGL',
        'QtOpenGLWidgets',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        
        # Sql modules (not used)
        'QtSql',
        'PySide6.QtSql',
        
        # PrintSupport modules (not used)
        'QtPrintSupport',
        'PySide6.QtPrintSupport',
        
        # Designer modules (not used)
        'QtDesigner',
        'PySide6.QtDesigner',
        
        # UiTools modules (not used)
        'QtUiTools',
        'PySide6.QtUiTools',
        
        # AxContainer modules (not used)
        'QtAxContainer',
        'PySide6.QtAxContainer',
        
        # DBus modules (not used)
        'QtDBus',
        'PySide6.QtDBus',
        
        # Network modules (already excluded, but explicitly listed)
        'QtNetwork',
        'PySide6.QtNetwork',
        
        # OpenGL modules (already excluded, but explicitly listed)
        'QtOpenGL',
        'QtOpenGLWidgets',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        
        # PDF modules (not used)
        'QtPdf',
        'PySide6.QtPdf',
        
        # QML modules (not used)
        'QtQml',
        'QtQmlModels',
        'QtQmlMeta',
        'QtQmlWorkerScript',
        'PySide6.QtQml',
        'PySide6.QtQmlModels',
        'PySide6.QtQmlMeta',
        'PySide6.QtQmlWorkerScript',
        # Quick modules (already excluded, but explicitly listed)
        'QtQuick',
        'QtQuickWidgets',
        'QtQuickControls2',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtQuickControls2',
        # VirtualKeyboard modules (not used)
        'QtVirtualKeyboard',
        'QtVirtualKeyboardQml',
        'PySide6.QtVirtualKeyboard',
        'PySide6.QtVirtualKeyboardQml',
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
    strip=True,
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
        'LSMinimumSystemVersion': '11.7',
    },
    version='2.0.0',
)