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
datas, binaries, hiddenimports = [], [], []
for pkg in ("playwright", "PySide6", "shiboken6"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# 기본 config.json을 번들(최초 실행 시 exe 옆으로 복사됨) + riss 패키지 포함.
datas += [("config.json", ".")]
hiddenimports += [
    "riss", "riss.browser", "riss.search", "riss.download",
    "riss.metadata", "riss.export", "riss.inspect", "riss.selectors",
    "cli", "gui", "paths",
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
