# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 스펙 — 단일 exe(onefile) 빌드.

빌드(Windows에서):  pyinstaller RISS다운로더.spec
결과:               dist\\RISS다운로더.exe  (파일 하나)

주의: 이 스펙은 Windows에서 실행해야 Windows용 exe가 나온다.
(PyInstaller는 크로스 컴파일을 하지 않는다.)
"""

from PyInstaller.utils.hooks import collect_all

# Playwright(node 드라이버 포함)와 PySide6를 통째로 수집.
# 브라우저 바이너리는 CDP attach 방식이라 불필요(용량 절약).
# PySide6는 collect_all로 통째 수집하지 않는다 — 그러면 Qt 전체 모듈
# (WebEngine/Quick3D/Pdf/SerialBus 등)이 딸려와 빌드가 느려지고 exe가 수백 MB로
# 불어난다. PyInstaller의 내장 훅이 우리가 import한 QtCore/QtGui/QtWidgets만
# 알아서 포함하므로, 여기선 playwright/pymupdf만 명시 수집한다.
datas, binaries, hiddenimports = [], [], []
for pkg in ("playwright", "pymupdf"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# 기본 config.json을 번들(최초 실행 시 exe 옆으로 복사됨) + 우리 모듈 포함.
datas += [("config.json", ".")]
hiddenimports += [
    "riss", "riss.browser", "riss.search", "riss.download",
    "riss.metadata", "riss.export", "riss.inspect", "riss.selectors",
    "riss.quotes", "pymupdf", "fitz",
    "cli", "gui", "paths",
    "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
]

# 우리가 쓰지 않는 무거운 Qt 모듈은 제외해 용량/빌드시간을 줄인다.
excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets", "PySide6.QtQml",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtSpatialAudio",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DExtras", "PySide6.Qt3DAnimation",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtSql",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSerialPort", "PySide6.QtSerialBus",
    "PySide6.QtSensors", "PySide6.QtPositioning", "PySide6.QtLocation",
    "PySide6.QtWebSockets", "PySide6.QtWebChannel", "PySide6.QtScxml",
    "PySide6.QtStateMachine", "PySide6.QtRemoteObjects", "PySide6.QtTextToSpeech",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtTest", "PySide6.QtQuickControls2",
    "tkinter",
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="RISS다운로더",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUI: 콘솔 창 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 아이콘 있으면 "app.ico" 등으로 지정
)
