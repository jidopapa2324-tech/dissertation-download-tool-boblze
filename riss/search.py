"""키워드 검색 + 결과 목록 파싱.

판단 로직 없음 — 박사학위논문 필터를 적용한 결과 전체를 그대로 반환한다.
"""

from playwright.sync_api import Page


def search(page: Page, keyword: str, max_pages: int, config: dict) -> list[dict]:
    """RISS에서 keyword로 검색하고 박사학위논문 결과 목록을 반환한다.

    절차:
    1. 검색창(selectors.SEARCH_INPUT)에 keyword 입력 후 검색 실행
    2. '학위논문' 탭 → '박사' 필터 적용
    3. 각 결과 페이지를 파싱, max_pages 페이지까지 순회
       (페이지 이동 사이에 config["delay_sec"] 만큼 sleep)

    반환: README의 search JSON 계약과 동일한 dict의 리스트.
    각 dict 키: id, title, author, university, year, degree,
                detail_url, downloadable

    id는 detail_url에서 selectors.DETAIL_URL_ID_PATTERN 으로 추출한다.

    TODO(opus): 구현
    """
    raise NotImplementedError


def _parse_result_page(page: Page) -> list[dict]:
    """현재 표시된 결과 페이지 1장에서 논문 목록을 파싱한다.

    TODO(opus): 구현 (selectors.RESULT_* 사용)
    """
    raise NotImplementedError
