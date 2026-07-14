@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 파이썬 명령 자동 감지 (python 없으면 py)
where python >nul 2>nul && (set "PY=python") || (set "PY=py")

rem 크롬 경로 자동 감지
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

:menu
cls
echo ================================================
echo    RISS 논문 다운로더
echo ================================================
echo    1. 크롬 켜기 (로그인용, 디버깅 모드)
echo    2. 저자로 검색
echo    3. 키워드로 검색
echo    4. 검색결과 목록 보기
echo    5. 선택 다운로드 (논문 ID 입력)
echo    6. 검색된 전체 다운로드
echo    9. 최신 코드로 업데이트 (git pull)
echo    0. 종료
echo ================================================
set /p sel=번호 선택:

if "%sel%"=="1" goto chrome
if "%sel%"=="2" goto search_author
if "%sel%"=="3" goto search_keyword
if "%sel%"=="4" goto listcmd
if "%sel%"=="5" goto download
if "%sel%"=="6" goto download_all
if "%sel%"=="9" goto update
if "%sel%"=="0" exit
goto menu

:chrome
start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="C:\chrome-riss" "https://kupis.kw.ac.kr/"
echo.
echo 크롬을 켜고 광운대 포털(kupis.kw.ac.kr)로 이동했습니다.
echo   1) 로그인 (대학원생 선택 후 아이디/비번)
echo   2) 로그인 후 https://kupis.kw.ac.kr/schosite/list/1 에서 RISS 접속
echo 로그인이 끝나면 이 창으로 돌아와 2번(검색)부터 진행하세요.
pause
goto menu

:search_author
echo.
set /p author=저자명 입력 (예: 서진형(Seo Jin Hyeong)):
%PY% cli.py search --author "%author%" --collection article
echo.
echo --- 검색 결과 목록 ---
%PY% cli.py list
pause
goto menu

:search_keyword
echo.
set /p kw=검색어 입력:
%PY% cli.py search --keyword "%kw%" --collection article
echo.
echo --- 검색 결과 목록 ---
%PY% cli.py list
pause
goto menu

:listcmd
echo.
%PY% cli.py list
pause
goto menu

:download
echo.
set /p ids=다운로드할 논문 ID (여러 개는 띄어쓰기로 구분):
%PY% cli.py download --progress --ids %ids%
echo.
echo 결과를 메모장으로 엽니다. (문제 보고 시 전체 복사 Ctrl+A → Ctrl+C 해서 붙여넣기)
if exist "data\last_download.json" start "" notepad "data\last_download.json"
pause
goto menu

:download_all
echo.
echo 검색된(목록의) 모든 논문을 다운로드합니다. 이미 받은 것은 건너뜁니다.
%PY% cli.py download --progress --all
echo.
echo 결과를 메모장으로 엽니다. (문제 보고 시 전체 복사 Ctrl+A → Ctrl+C 해서 붙여넣기)
if exist "data\last_download.json" start "" notepad "data\last_download.json"
pause
goto menu

:update
echo.
git pull
pause
goto menu
