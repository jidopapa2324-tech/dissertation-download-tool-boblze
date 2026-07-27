@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem ============================================================
rem  관리자 정기점검 — Windows 작업 스케줄러가 이 파일을 부른다.
rem  Claude Code를 headless(-p)로 실행해 상태를 점검하고
rem  결과를 data\reports\ 에 날짜별로 남긴다.
rem
rem  등록 방법(관리자 권한 필요 없음):
rem    1) 시작 메뉴 → "작업 스케줄러" 실행
rem    2) [기본 작업 만들기] → 이름: RISS 정기점검
rem    3) 트리거: 매일 (원하는 시각)
rem    4) 동작: 프로그램 시작 → 이 파일(정기점검.bat) 선택
rem  또는 아래 한 줄을 PowerShell에 붙여넣어 등록할 수도 있다:
rem    schtasks /create /tn "RISS 정기점검" /tr "%~f0" /sc daily /st 09:00
rem ============================================================

if not exist "data\reports" mkdir "data\reports"

set "STAMP=%date:~0,4%%date:~5,2%%date:~8,2%"
set "OUT=data\reports\점검_%STAMP%.md"

echo [%date% %time%] 정기점검 시작...

claude -p "너는 관리자다. .claude/agents/manager.md 의 역할대로 행동해라. CLAUDE.md를 읽고, data/ 와 reference/ 를 확인해 현재 상태를 점검한 뒤 다음 할 일을 우선순위대로 정리해라. 브라우저가 필요한 작업은 실행하지 말고 '사용자 확인 필요'로 표시해라. 결과는 한국어 마크다운으로만 출력해라." > "%OUT%" 2>&1

if errorlevel 1 (
  echo 점검 실패. claude 명령을 찾을 수 없거나 오류가 발생했습니다.
  echo 자세한 내용: %OUT%
) else (
  echo 점검 완료 : %OUT%
)

rem 사람이 바로 볼 수 있게 메모장으로 열기(스케줄 실행 시엔 주석 처리 권장)
if exist "%OUT%" start "" notepad "%OUT%"
