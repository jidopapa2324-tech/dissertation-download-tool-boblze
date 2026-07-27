# RISS 논문 다운로더 — 작업 인수인계 문서

이 파일은 Claude Code가 이 저장소에서 작업할 때 먼저 읽는 문서다.
클라우드 세션에서 여기까지 만들었고, 이후 작업은 **사용자 Windows PC의
로컬 Claude Code**가 이어받는다(로컬은 실제 실행·검증이 가능하다).

## 이 도구가 하는 일

RISS(광운대 도서관 프록시)에서 논문을 검색·다운로드하고 서지정보를 축적한다.
사용자는 **빈집(空家) 관련 박사논문**을 준비 중이며, 이 도구를 다른 사람들에게도
배포할 예정이다(단일 exe).

**핵심 원칙 (바꾸지 말 것)**
1. **판단하지 않는다** — search는 결과 전부 반환, download는 받은 ID만 처리.
   무엇을 받을지는 사용자/외부 AI가 정한다.
2. **로그인하지 않는다** — 사용자가 직접 로그인한 Chrome(`--remote-debugging-port=9222`)에
   CDP로 붙기만 한다. 비밀번호를 코드가 다루지 않는다.
3. **순차 다운로드 유지** — 병렬화하면 기관 계정이 차단될 위험이 있다.
   `delay_sec` 간격을 없애지 말 것.
4. **stdout은 JSON 계약** — 진행 로그는 stderr로만. GUI/외부 AI가 이 계약에 의존한다.

## 구조

```
app.py         진입점(GUI/CLI 겸용). 인자가 서브커맨드면 CLI, 아니면 GUI.
               단일 exe에서 GUI가 자기 자신을 CLI 모드로 재실행한다.
paths.py       실행 경로 + DEFAULT_CONFIG(설정을 코드에 내장; config.json 안 만듦)
cli.py         서브커맨드 파싱/JSON 출력. 진행표시(stderr) 리포터.
gui.py         PySide6 GUI. QProcess로 cli를 호출하고 로그를 흘린다.
riss/
  browser.py   CDP attach (localhost→127.0.0.1 폴백)
  search.py    검색 URL 조립 + 결과 파싱(앵커 기반)
  download.py  다운로드 파이프라인(핵심, 아래 설명)
  export.py    인용 내보내기(자료유형별 서식)
  quotes.py    인용문 추출 + PDF 밑줄(PyMuPDF)
  metadata.py  index/metadata/failed 축적(JSONL)
  inspect.py   [개발용] 페이지 구조 덤프
  selectors.py RISS 셀렉터·URL·자료유형 상수 (페이지 바뀌면 여기만 수정)
```

## 실측으로 알아낸 RISS 지식 (추측 아님, 실제 URL/DOM 확인)

**검색 URL**: `/search/Search.do?query=…&colName=…&iStartCount=…`
- `colName`: `bib_t`(학위논문) / `re_a_kor`(국내학술논문) / `all`
- 저자검색은 `isDetailSearch=Y&queryText=znCreator,<이름>`
- 좌측 필터는 `exQuery`에 `<필드>:<값>◈` 조각을 이어붙임:
  - 국내박사 `mat_subtype_cd:T2◈`, 원문있음 `fulltext_kind:1◈`

**자료유형** (`p_mat_type`, `selectors.MAT_TYPES` — 실 검색결과 분석으로 확정):
| 코드 | 유형 |
|---|---|
| `1a0202e37d52c72d` | 국내학술논문 |
| `be54d9b8bc7cdb09` | 국내학위논문 |
| `3a11008f85f7c51d` | 학술지(컨테이너) — **원문 없음, 다운로드 즉시 스킵** |
| `d7345961987b50bf` | 단행본 |
| `6b4a196b69d9bee2` | 연구보고서 |

**다운로드 흐름** (실측):
```
RISS 상세페이지
  → '원문보기' 클릭 (href=javascript:void(0), onclick=ButtonSet.memberUrlDownload(...))
  → 팝업: RISS 중간 로더 UrlLoad.do
  → 자동 리다이렉트 → 외부 제공처(교보스콜라 등)
  → '원문저장' 클릭 → PDF 다운로드
```
제공처가 다양하므로 2중 전략을 쓴다:
1. 버튼 클릭 → `expect_download` (교보스콜라에서 검증됨)
2. **폴백**: 응답 URL 감시 → `.pdf`/`/pdf/`/`content-type: application/pdf` 감지,
   ezPDF 뷰어의 `?file=<인코딩>`을 디코딩해 원본 주소 추출 → 쿠키로 직접 GET
   (riss_paper_surfer 크롬확장에서 배운 기법)

실패하면 `data/diagnostics/{id}.json`에 그 페이지의 링크·버튼·iframe을 자동 저장한다.
**제공처 문제를 고칠 때는 이 진단 파일부터 볼 것.**

## 데이터 파일 (exe 옆에 생성)

- `reference/` — PDF 원문(파일명=논문 제목), `reference/annotated/`=밑줄 사본
- `data/index.jsonl` — 검색으로 발견한 목록(id↔detail_url). **download가 여기서 URL을 찾으므로
  검색을 먼저 해야 다운로드된다.**
- `data/metadata.jsonl` — 다운로드 완료본의 서지정보(`bib`, `provider_bib_text` 원문 포함)
- `data/failed.json` — 실패 대기열(`download --retry-failed`가 사용)
- `data/quotes.jsonl` — 저장한 인용문
- `config.json`은 **만들지 않는다**(기본값은 `paths.DEFAULT_CONFIG`). 사용자가 직접 두면 덮어씀.

## 명령

```bash
python app.py search --keyword "빈집" --doctoral --fulltext   # 국내박사+원문있음
python app.py search --author "서진형(Seo Jin Hyeong)" --collection article
python app.py list | library                                   # 목록/정리된 서지
python app.py download --progress --all | --ids A B | --retry-failed
python app.py export --format apa|korean|bibtex|ris|csljson [--out 파일]
python app.py quote --id <id> --text "문장"                    # 인용+밑줄
python app.py notes --style korean                             # 인용 노트
python app.py inspect <control_no|url> [--follow] [--meta]     # 개발용 구조 덤프
```

## 현재 상태

**동작 확인됨**: 검색(저자/키워드/필터), 교보스콜라 다운로드, 서지 축적,
인용문+밑줄, 인용 내보내기(자료유형별), GUI, 단일 exe 자동빌드(GitHub Actions →
Release `latest`).

**미검증(로컬에서 해야 함)**:
- 최신 exe 실사용 전 과정(로그인→검색→전체 다운로드→인용노트)
- 교보 외 제공처(DBpia/KISS/earticle)에서 URL감시 폴백이 실제로 먹는지
- 국내박사/원문있음 필터가 결과에 제대로 반영되는지

**다음 할 일**
1. 위 미검증 항목 실행 → 실패건의 `data/diagnostics/*.json` 분석 → 제공처 처리 보강
2. 비개발자용 배포 가이드(`사용법.md`)
3. 안정화되면 PR을 main에 병합

## 검증 방법

브라우저 없이 가능한 것(권장 — 빠름):
```bash
python -m py_compile app.py cli.py gui.py paths.py riss/*.py
python app.py library          # 서지 파싱 확인
python app.py export --format apa
QT_QPA_PLATFORM=offscreen python -c "import gui; ..."   # GUI 위젯 생성(리눅스)
```
실사용 검증은 Chrome을 9222 포트로 띄우고 RISS 로그인 후 GUI/CLI 실행.

**주의**: 이 환경(클라우드)에서는 RISS·교보가 403이고 로그인 세션이 없어
실제 다운로드 검증이 불가능했다. 로컬에서는 가능하다.

## 빌드/배포

- `.github/workflows/build-exe.yml` — push 시 Windows에서 PyInstaller 빌드 →
  Release `latest`에 exe 발행(로그인 없이 받는 고정 링크)
- 로컬 빌드는 `빌드.bat`
- 스펙 주의: `collect_all("PySide6")`를 쓰지 말 것(Qt 전체가 딸려와 exe가 수백 MB).
  현재는 playwright·pymupdf만 수집하고 미사용 Qt 모듈은 excludes 처리.

## 코드 스타일

주석·문서·커밋 메시지는 한국어. 함수 docstring에 "왜"를 적는다.
셀렉터는 `selectors.py`에만 두고, 실패해도 크래시 대신 명확한 에러 메시지를 남긴다.
