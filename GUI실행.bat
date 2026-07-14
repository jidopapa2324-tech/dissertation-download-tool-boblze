@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 파이썬 명령 자동 감지
where python >nul 2>nul && (set "PY=python") || (set "PY=py")

rem PySide6 설치 여부 확인, 없으면 안내
%PY% -c "import PySide6" 2>nul
if errorlevel 1 (
  echo GUI 라이브러리(PySide6)가 없습니다. 지금 설치할까요?
  echo 설치하려면 아무 키나 누르세요. 취소하려면 창을 닫으세요.
  pause
  %PY% -m pip install -r requirements-gui.txt
)

%PY% gui.py
if errorlevel 1 pause
