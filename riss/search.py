"""키워드 검색 + 결과 목록 파싱.

판단 로직 없음 — 박사학위논문 필터를 적용한 결과 전체를 그대로 반환한다.
"""

from playwright.sync_api import Page


def search(page: Page, keyword: str, max_pages: int, config: dict) -> list[dict]:
    """RISS에서 keyword로 검색하고 박사학위논문 결과 목록을 반환한다.

    절차 (UI 클릭 대신 URL 직접 조립 방식):
    1. selectors.SEARCH_URL_TEMPLATE 에 keyword(URL 인코딩),
       colName=COL_NAME_THESIS, iStartCount 를 채워 page.goto()
    2. '박사' 필터 적용 — URL 파라미터로 가능하면 URL에 포함,
       불가하면 selectors.FILTER_DOCTORAL 클릭.
       필터가 안 먹어도 RESULT_DEGREE 텍스트가 "박사"가 아닌 행은 버린다.
    3. iStartCount를 10씩 늘려가며 max_pages 페이지까지 순회
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
