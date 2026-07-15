@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   RISS 다운로더 단일 exe 빌드
echo ============================================
echo 이 작업은 Windows에서 한 번만 하면 됩니다.
echo 완료되면 dist\RISS다운로더.exe (파일 하나)가 생깁니다.
echo.

rem 파이썬 명령 자동 감지
where python >nul 2>nul && (set "PY=python") || (set "PY=py")

echo [1/3] 빌드 도구/의존성 설치...
%PY% -m pip install --upgrade pyinstaller >nul
%PY% -m pip install -r requirements-gui.txt >nul
%PY% -m pip install -r requirements.txt >nul

echo [2/3] Playwright 파이썬 패키지 확인...
%PY% -c "import playwright" 2>nul || %PY% -m pip install playwright >nul

echo [3/3] exe 빌드 (수 분 소요)...
%PY% -m PyInstaller RISS다운로더.spec --noconfirm
if errorlevel 1 (
  echo.
  echo 빌드 실패. 위 오류 메시지를 확인하세요.
  pause
  exit /b 1
)

echo.
echo 완료! dist\RISS다운로더.exe 를 원하는 폴더로 옮겨 더블클릭하세요.
echo (첫 실행은 압축 해제로 조금 느릴 수 있습니다.)
explorer dist
pause
