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

## CLI 사용법 (외부 AI가 호출하는 계약)

### 검색

```bash
python cli.py search --keyword "딥러닝" [--max-pages 3]
```

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
    {"id": "ID1", "ok": true,  "file": "data/downloads/ID1.pdf"},
    {"id": "ID2", "ok": false, "error": "원문 제공 안 됨"}
  ]
}
```

다운로드 성공 시 해당 논문의 메타데이터가 `data/metadata.jsonl`에 한 줄씩 추가된다.

### 에러 규약

모든 실패는 exit code 1 + `{"ok": false, "error": "사람이 읽을 수 있는 메시지"}`.
브라우저 미연결, 로그인 만료, 셀렉터 불일치 등을 error 메시지로 구분해준다.

## 데이터 축적

- `data/metadata.jsonl` — 다운로드한 논문의 서지정보를 JSON Lines로 append.
  중복 ID는 다시 쓰지 않는다.
- `data/downloads/` — PDF 원문. 파일명은 `{id}.pdf`.

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
