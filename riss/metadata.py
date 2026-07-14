"""학술 데이터 축적 — JSON Lines(append-only) 파일 두 개.

- index_file    : 검색으로 '발견'한 모든 논문(중복 제거). 다운로드 시 URL 조회용.
- metadata_file : 실제 '다운로드'한 논문의 서지정보(초록 포함) 로그.

DB 없이 파일로 유지한다. 외부 AI가 이 파일들을 그대로 읽어 활용한다.
"""

import json
import os


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def _load_ids(path: str) -> set[str]:
    ids: set[str] = set()
    if not os.path.exists(path):
        return ids
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in rec:
                ids.add(rec["id"])
    return ids


def _append(path: str, record: dict) -> None:
    _ensure_dir(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def index_append(record: dict, config: dict) -> None:
    """검색 발견 항목을 index_file에 append (id 중복이면 무시)."""
    path = config["index_file"]
    if record.get("id") in _load_ids(path):
        return
    _append(path, record)


def index_lookup(thesis_id: str, config: dict) -> dict | None:
    """index_file에서 id로 항목(주로 detail_url)을 찾는다. 없으면 None."""
    path = config["index_file"]
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("id") == thesis_id:
                return rec
    return None


def index_all(config: dict) -> list[dict]:
    """index_file의 모든 발견 항목을 리스트로 반환 (list/전체 다운로드용)."""
    path = config["index_file"]
    out: list[dict] = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def append(record: dict, config: dict) -> None:
    """다운로드한 논문 메타데이터를 metadata_file에 append (id 중복이면 무시).

    record 권장 키: id, title, author, university, year, degree,
    detail_url, downloaded_at(ISO8601). 선택: abstract, file, collection.
    """
    path = config["metadata_file"]
    if record.get("id") in _load_ids(path):
        return
    _append(path, record)


def load_ids(config: dict) -> set[str]:
    """이미 다운로드(metadata_file 기록)된 id 집합. 중복 다운로드 체크용."""
    return _load_ids(config["metadata_file"])
