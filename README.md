# riss-downloader

RISS(광운대 도서관 프록시 경유) 박사학위논문 자동 다운로드 도구.

이미 로그인된 브라우저 세션에 붙어서 **검색 → 목록 반환 → 지정된 논문 다운로드 → 메타데이터 축적**만 수행한다.
어떤 논문을 받을지는 판단하지 않는다 — 그 결정은 이 도구를 호출하는 외부 AI가 한다.

## 아키텍처

```
[외부 AI (아티팩트)]
      │  CLI 호출, JSON 입출력
      ▼
   cli.py  ──────────────  진입점. 명령 파싱, JSON 직렬화만 담당
      │
      ├── riss/browser.py    이미 열려있는 Chrome에 CDP로 연결 (로그인 로직 없음)
      ├── riss/search.py     키워드 검색 + 결과 목록 파싱 → dict 리스트
      ├── riss/download.py   지정된 논문 ID의 원문(PDF) 다운로드
      ├── riss/metadata.py   data/metadata.jsonl 에 학술 데이터 append
      └── riss/selectors.py  RISS 페이지 셀렉터/URL 상수 (유지보수 포인트 집중)
```

### 설계 원칙

1. **판단하지 않는다.** search는 전부 반환, download는 받은 ID만 처리.
2. **로그인하지 않는다.** 사용자가 `--remote-debugging-port=9222`로 띄운 Chrome에서
   이미 로그인된 탭을 그대로 사용한다.
3. **셀렉터는 `selectors.py` 한 곳에만.** RISS 페이지가 바뀌면 이 파일만 수정.
   또한 UI 클릭 대신 URL 직접 조립을 우선한다 — 검색은
   `/search/Search.do?query=...&iStartCount=...`, 상세는
   `/search/detail/DetailView.do?control_no=...` 로 바로 이동하므로
   검색창/탭 셀렉터가 아예 필요 없다. 논문 ID = RISS `control_no`.
4. **모든 출력은 JSON.** 외부 AI가 파싱하는 유일한 계약(contract)이다.
5. **요청 간 지연(`config.json`의 `delay_sec`)을 반드시 둔다.**
   기관 계정 보호 및 서버 부하 방지 목적. 개인 연구 목적 사용을 전제로 한다.

## 사전 준비 (사용자)

```bash
# 1. 디버깅 포트를 연 Chrome 실행 후, RISS 프록시 페이지에 수동 로그인
chrome --remote-debugging-port=9222

# 2. 의존성 설치
pip install -r requirements.txt
playwright install chromium   # 실제로는 CDP attach만 하므로 브라우저 설치 불필요할 수 있음
```

## 사람이 쓸 때 (2): GUI (PySide6)

클릭 기반 화면을 원하면 `GUI실행.bat`을 더블클릭한다. 처음 실행 시 GUI
라이브러리(PySide6)를 설치할지 물어본다(설치는 한 번만).

```
pip install -r requirements-gui.txt   # 수동 설치 시
python gui.py
```

GUI는 실제 작업을 직접 하지 않고 **기존 `cli.py`를 그대로 호출**한다.
버튼: 크롬 켜고 로그인 · 검색(저자/키워드) · 결과 체크 후 선택/전체 다운로드 ·
실패만 재시도 · 인용 내보내기. 자식 프로세스의 진행바·단계·소요시간이 하단
로그 창에 실시간으로 흐른다. (백엔드/CLI 계약은 변경 없음)

## 사람이 쓸 때 (1): 실행.bat (Windows, cmd 메뉴)

`실행.bat`을 **더블클릭**하면 메뉴가 뜬다. cmd에 명령을 직접 칠 필요가 없다.

```
1. 크롬 켜기 (로그인용)      5. 선택 다운로드 (ID 입력)
2. 저자로 검색              6. 검색된 전체 다운로드
3. 키워드로 검색            9. 최신 코드로 업데이트(git pull)
4. 검색결과 목록 보기        0. 종료
```

일반적 흐름: **1(크롬 켜서 로그인) → 2/3(검색) → 4(목록 확인) → 5/6(다운로드)**.
크롬 경로와 python/py 명령은 자동 감지한다.

`list` 명령은 사람이 읽기 쉬운 목록을 출력한다 (`python cli.py list`).
`download --all` 은 인덱스(검색된) 전체를 받는다.
`download --retry-failed` 는 이전에 실패한 논문만 다시 받는다 (실패 목록은
`data/failed.json` 에 자동 관리 — 성공하면 빠지고 실패하면 쌓인다).
`export --format bibtex|ris|csljson|apa|korean [--out 파일]` 은 축적된
서지정보를 내보낸다:
  - 기계용(관리 프로그램 가져오기): `bibtex` · `ris` · `csljson`
  - 사람용(논문에 바로 붙여넣는 참고문헌 목록): `apa` · `korean`
    (학회 규정마다 세부 서식이 달라 근사치이며, 정확한 서식은 확인 후 다듬는다)
`library` 는 다운로드한 참고문헌을 저자순으로 정리해 목록으로 출력한다.

## CLI 사용법 (외부 AI가 호출하는 계약)

### 검색

```bash
# 키워드 검색
python cli.py search --keyword "딥러닝" --collection article [--max-pages 3]

# 저자 검색 (국내학술논문)
python cli.py search --author "서진형(Seo Jin Hyeong)" --collection article
```

`--collection`: `all`(통합) | `thesis`(국내학위논문) | `article`(국내학술논문).

stdout (JSON):

```json
{
  "ok": true,
  "command": "search",
  "keyword": "딥러닝",
  "count": 42,
  "results": [
    {
      "id": "RISS 논문 고유 ID (상세페이지 URL에서 추출)",
      "title": "논문 제목",
      "author": "저자",
      "university": "수여 대학",
      "year": "2024",
      "degree": "박사",
      "detail_url": "상세 페이지 절대 URL",
      "downloadable": true
    }
  ]
}
```

### 다운로드

```bash
python cli.py download --ids ID1 ID2 ID3
```

stdout (JSON):

```json
{
  "ok": true,
  "command": "download",
  "results": [
    {"id": "ID1", "ok": true,  "file": "reference/논문제목.pdf"},
    {"id": "ID2", "ok": false, "error": "원문 제공 안 됨"}
  ]
}
```

다운로드 성공 시 해당 논문의 메타데이터가 `data/metadata.jsonl`에 한 줄씩 추가된다.

### 에러 규약

모든 실패는 exit code 1 + `{"ok": false, "error": "사람이 읽을 수 있는 메시지"}`.
브라우저 미연결, 로그인 만료, 셀렉터 불일치 등을 error 메시지로 구분해준다.

## 데이터 축적

- `data/index.jsonl` — 검색으로 **발견**한 모든 논문(중복 제거). `id`↔`detail_url`
  매핑이 여기 저장되며, `download`는 이 파일에서 URL을 조회한다.
  따라서 **download 전에 해당 논문이 search로 인덱싱돼 있어야** 한다.
- `data/metadata.jsonl` — 실제 **다운로드**한 논문의 서지정보를 JSON Lines로
  append. 중복 ID는 다시 쓰지 않는다. 각 레코드에는 상세페이지의 서지
  '라벨:값' 쌍을 통째로 담은 `bib` 필드가 있어, 나중에 AI가 이걸 읽어 원하는
  참조문헌 서식(저자·연도·페이지 등)으로 변환할 수 있다.
- 다운로드는 **PDF 무결성 검증**을 거친다(`%PDF` 헤더 + 최소 크기). 원문 미제공
  등으로 HTML 오류페이지가 내려오면 정상 PDF가 아니므로 파일을 지우고 실패로 처리한다.
- 다운로드가 **시작되면 곧바로 다음 논문으로 진행**하고, 파일 저장(마무리)은
  뒤이어 겹쳐서 처리해 전체 시간을 줄인다. 동시에 열리는 팝업 수는
  `config.json`의 `overlap_batch`(기본 4)로 제한한다.
- `reference/` — 원문 파일. 파일명은 **논문 제목**(기본형).
  Windows 금지문자는 공백으로 치환하고 길이를 제한하며, 동일 제목의 다른
  논문과 충돌하면 파일명 끝에 id 일부를 붙여 구분한다.

`id`는 RISS `control_no`이며 `search` 결과의 `detail_url`에서 추출된다.

## 유지보수 가이드

| 증상 | 고칠 곳 |
|---|---|
| 검색 결과가 안 잡힘 | `riss/selectors.py`의 검색 관련 셀렉터 |
| 다운로드 버튼을 못 찾음 | `riss/selectors.py`의 다운로드 관련 셀렉터 |
| 프록시 URL 변경 | `config.json`의 `base_url` |
| 브라우저 연결 실패 | Chrome이 `--remote-debugging-port=9222`로 실행됐는지 확인 |

## 개발 상태

**현재는 구조(스켈레톤)만 존재한다.** 각 모듈의 함수 시그니처와 docstring이 명세이며,
본문은 `TODO(opus)` 주석과 `NotImplementedError`로 표시되어 있다.
실제 구현 시 이 README의 JSON 계약을 변경하지 말 것 — 외부 AI가 이 계약에 의존한다.
