"""지정된 논문 ID의 원문(PDF) 다운로드.

어떤 논문을 받을지 판단하지 않는다 — 호출자가 넘긴 ID만 처리한다.
"""

from playwright.sync_api import Page


def download_one(page: Page, thesis_id: str, config: dict) -> dict:
    """논문 1건의 원문을 다운로드하고 결과 dict를 반환한다.

    절차:
    1. 이미 config["download_dir"]/{thesis_id}.pdf 가 존재하면
       {"id": ..., "ok": True, "file": ..., "skipped": True} 로 즉시 반환
    2. 논문 상세 페이지로 이동
    3. selectors.DETAIL_DOWNLOAD_BUTTON 클릭, Playwright의
       expect_download 로 파일 저장 → {download_dir}/{thesis_id}.pdf
    4. 상세 페이지의 서지정보(초록 포함)를 파싱해 metadata.append() 호출
    5. config["delay_sec"] 만큼 sleep

    실패(원문 미제공, 버튼 없음, 타임아웃 등) 시 예외를 던지지 말고
    {"id": ..., "ok": False, "error": "..."} 를 반환한다.
    한 건의 실패가 나머지 다운로드를 막으면 안 된다.

    TODO(opus): 구현
    """
    raise NotImplementedError


def download_many(page: Page, thesis_ids: list[str], config: dict) -> list[dict]:
    """thesis_ids를 순서대로 download_one에 넘기고 결과 리스트를 반환한다.

    TODO(opus): 구현 (단순 루프면 충분)
    """
    raise NotImplementedError
