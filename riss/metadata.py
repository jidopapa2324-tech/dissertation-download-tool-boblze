"""학술 데이터 축적 — data/metadata.jsonl 에 JSON Lines로 append.

DB 없이 파일 하나로 유지한다. 외부 AI가 이 파일을 그대로 읽어 활용한다.
"""


def append(record: dict, config: dict) -> None:
    """논문 메타데이터 1건을 metadata.jsonl 에 append 한다.

    - record 필수 키: id, title, author, university, year, degree,
      detail_url, downloaded_at (ISO 8601). 선택 키: abstract, file
    - 이미 같은 id가 파일에 있으면 쓰지 않는다 (중복 방지)
    - 파일/디렉터리가 없으면 생성

    TODO(opus): 구현
    """
    raise NotImplementedError


def load_ids(config: dict) -> set[str]:
    """metadata.jsonl 에 기록된 논문 id 집합을 반환한다 (중복 체크용).

    파일이 없으면 빈 set.

    TODO(opus): 구현
    """
    raise NotImplementedError
