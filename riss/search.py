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
) -> list[dict]:
    """RISS를 검색해 결과 목록을 반환한다.

    keyword 또는 author 중 하나를 준다.
      - keyword: 통합/키워드 검색 (query=)
      - author : 저자 상세검색 (queryText=znCreator,<author>)
    collection: "all" | "thesis" | "article" (selectors.COLLECTIONS)

    반환: dict 리스트. 키: id, title, detail_url, collection.
    (저자/연도/대학 등 상세 서지는 다운로드 시 상세페이지에서 채운다.)
    발견한 항목은 index_file에 누적(dedupe)된다 — 다운로드 시 URL 조회에 쓰인다.
    """
    if not keyword and not author:
        raise ValueError("keyword 또는 author 중 하나는 필요합니다.")

    col_name = selectors.COLLECTIONS.get(collection, collection)
    seen: dict[str, dict] = {}

    for page_idx in range(max_pages):
        start_count = page_idx * 10
        url = _build_url(config, keyword, author, col_name, start_count, page_idx + 1)
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=config["timeout_sec"] * 1000)
        except Exception:
            pass  # networkidle 실패는 치명적이지 않음

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


def _build_url(config, keyword, author, col_name, start_count, page_number) -> str:
    base = config["base_url"]
    if author:
        return selectors.FIELD_SEARCH_URL.format(
            base_url=base,
            field=selectors.FIELD_CREATOR,
            value=quote(author),
            col_name=col_name,
            start_count=start_count,
            page_number=page_number,
        )
    return selectors.KEYWORD_SEARCH_URL.format(
        base_url=base,
        query=quote(keyword),
        col_name=col_name,
        start_count=start_count,
        page_number=page_number,
    )


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
