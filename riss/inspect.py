"""페이지 구조 덤프 — 셀렉터 확정을 위한 진단 도구.

로그인된 브라우저에서 상세페이지를 열고, 링크/버튼/iframe 등 구조를
JSON으로 뽑는다. 이 출력을 보고 selectors.py를 확정한다.
'개발용'이며 일상 다운로드 흐름과는 무관하다.
"""

from urllib.parse import urljoin

from . import metadata, selectors


def inspect(page, config: dict, target: str) -> dict:
    """target(=control_no 또는 detail_url)의 페이지 구조를 덤프한다."""
    detail_url = _resolve_url(config, target)
    page.goto(detail_url, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=config["timeout_sec"] * 1000)
    except Exception:
        pass

    base = config["base_url"]

    links = []
    for a in page.query_selector_all("a"):
        text = (a.inner_text() or "").strip()
        href = a.get_attribute("href") or ""
        onclick = a.get_attribute("onclick") or ""
        # 원문/다운로드와 관련 있어 보이는 것만 추림 (노이즈 제거)
        blob = f"{text} {href} {onclick}".lower()
        if any(k in blob for k in ["원문", "download", "다운", "pdf", "viewer", "scholar", "dbpia", "kiss", "earticle"]):
            links.append({
                "text": text,
                "href": urljoin(base, href) if href and not href.startswith("javascript") else href,
                "onclick": onclick[:200],
            })

    buttons = []
    for b in page.query_selector_all("button, input[type=button], input[type=submit]"):
        text = (b.inner_text() or b.get_attribute("value") or "").strip()
        onclick = b.get_attribute("onclick") or ""
        cls = b.get_attribute("class") or ""
        if text or onclick:
            buttons.append({"text": text, "class": cls, "onclick": onclick[:200]})

    iframes = [f.get_attribute("src") for f in page.query_selector_all("iframe") if f.get_attribute("src")]

    return {
        "ok": True,
        "command": "inspect",
        "detail_url": detail_url,
        "final_url": page.url,
        "page_title": page.title(),
        "candidate_links": links,
        "buttons": buttons,
        "iframes": iframes,
    }


def _resolve_url(config: dict, target: str) -> str:
    if target.startswith("http"):
        return target
    entry = metadata.index_lookup(target, config)
    if entry and entry.get("detail_url"):
        return entry["detail_url"]
    # 인덱스에 없으면 기본 학위논문 p_mat_type으로 조립 시도
    return (
        f"{config['base_url']}/search/detail/DetailView.do"
        f"?p_mat_type=1a0202e37d52c72d&control_no={target}"
    )
