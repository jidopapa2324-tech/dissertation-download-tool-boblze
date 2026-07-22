"""키워드/저자 검색 + 결과 목록 파싱.

판단 로직 없음 — 필터에 걸린 결과를 전부 그대로 반환한다.
검색 결과는 상세링크 앵커에서 control_no와 detail_url을 뽑는 '앵커 기반'
방식으로 파싱해 세부 CSS 셀렉터 의존을 최소화한다.
"""

import re
import time
from urllib.parse import quote, urljoin

from . import metadata, selectors


def search(
    page,
    config: dict,
    keyword: str | None = None,
    author: str | None = None,
    collection: str = "all",
    max_pages: int = 3,
    doctoral: bool = False,
    fulltext_only: bool = False,
) -> list[dict]:
    """RISS를 검색해 결과 목록을 반환한다.

    keyword 또는 author 중 하나를 준다.
      - keyword: 통합/키워드 검색 (query=)
      - author : 저자 상세검색 (queryText=znCreator,<author>)
    collection: "all" | "thesis" | "article" (selectors.COLLECTIONS)
    doctoral: True면 학위유형=국내박사 필터 적용(학위논문 컬렉션으로 강제).
    fulltext_only: True면 원문있음 필터 적용(받을 수 있는 것만).

    반환: dict 리스트. 키: id, title, detail_url, collection.
    (저자/연도/대학 등 상세 서지는 다운로드 시 상세페이지에서 채운다.)
    발견한 항목은 index_file에 누적(dedupe)된다 — 다운로드 시 URL 조회에 쓰인다.
    """
    if not keyword and not author:
        raise ValueError("keyword 또는 author 중 하나는 필요합니다.")

    col_name = selectors.COLLECTIONS.get(collection, collection)
    if doctoral:
        col_name = selectors.COLLECTIONS["thesis"]  # 국내박사 필터는 학위논문에만 유효
    ex_query, ex_text = _build_filters(doctoral, fulltext_only)
    seen: dict[str, dict] = {}

    for page_idx in range(max_pages):
        start_count = page_idx * 10
        url = _build_url(config, keyword, author, col_name, start_count, page_idx + 1,
                         ex_query, ex_text)
        page.goto(url, wait_until="domcontentloaded")
        # networkidle(최대 30초)를 기다리지 않고, 결과 링크가 나타나면 바로 진행
        try:
            page.wait_for_selector(selectors.RESULT_DETAIL_LINK, timeout=config["timeout_sec"] * 1000)
        except Exception:
            pass  # 결과가 없어도(마지막 페이지 등) 파싱은 시도

        items = _parse_result_page(page, config, col_name)
        new_on_page = 0
        for it in items:
            if it["id"] not in seen:
                seen[it["id"]] = it
                new_on_page += 1
        # 이 페이지에 새 결과가 하나도 없으면 마지막 페이지로 간주하고 종료
        if new_on_page == 0:
            break
        if page_idx < max_pages - 1:
            time.sleep(config["delay_sec"])

    results = list(seen.values())
    # 발견 항목을 인덱스에 누적 (다운로드 시 detail_url 조회용)
    for it in results:
        metadata.index_append(it, config)
    return results


def _build_filters(doctoral: bool, fulltext_only: bool) -> tuple[str, str]:
    """선택된 필터들을 exQuery/exQueryText 조각으로 이어 붙인다."""
    frags = []
    if doctoral:
        frags.append(selectors.FILTER_DOCTORAL)
    if fulltext_only:
        frags.append(selectors.FILTER_FULLTEXT)
    ex_query = "".join(f[0] for f in frags)
    ex_text = "".join(f[1] for f in frags)
    return ex_query, ex_text


def _build_url(config, keyword, author, col_name, start_count, page_number,
               ex_query="", ex_text="") -> str:
    base = config["base_url"]
    if author:
        url = selectors.FIELD_SEARCH_URL.format(
            base_url=base,
            field=selectors.FIELD_CREATOR,
            value=quote(author),
            col_name=col_name,
            start_count=start_count,
            page_number=page_number,
        )
    else:
        url = selectors.KEYWORD_SEARCH_URL.format(
            base_url=base,
            query=quote(keyword),
            col_name=col_name,
            start_count=start_count,
            page_number=page_number,
        )
    if ex_query:
        url += "&exQuery=" + quote(ex_query) + "&exQueryText=" + quote(ex_text)
    return url


def _parse_result_page(page, config: dict, col_name: str) -> list[dict]:
    """현재 결과 페이지에서 (id, title, detail_url) 목록을 뽑는다."""
    out: list[dict] = []
    seen_ids: set[str] = set()
    anchors = page.query_selector_all(selectors.RESULT_DETAIL_LINK)
    for a in anchors:
        href = a.get_attribute("href") or ""
        m = re.search(selectors.CONTROL_NO_PATTERN, href)
        if not m:
            continue
        control_no = m.group(1)
        if control_no in seen_ids:
            continue
        seen_ids.add(control_no)
        title = (a.inner_text() or "").strip()
        detail_url = urljoin(config["base_url"], href)
        out.append(
            {
                "id": control_no,
                "title": title,
                "detail_url": detail_url,
                "collection": col_name,
            }
        )
    return out
