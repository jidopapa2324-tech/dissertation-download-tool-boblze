"""지정된 논문 ID의 원문 다운로드.

어떤 논문을 받을지 판단하지 않는다 — 호출자가 넘긴 ID만 처리한다.
ID = RISS control_no. detail_url은 index_file(검색 결과)에서 조회한다.
"""

import datetime as _dt
import os
import time

from . import metadata, selectors


def download_one(page, thesis_id: str, config: dict) -> dict:
    """논문 1건을 다운로드하고 결과 dict를 반환한다. 예외를 던지지 않는다."""
    out_path = os.path.join(config["download_dir"], f"{thesis_id}.pdf")
    if os.path.exists(out_path):
        return {"id": thesis_id, "ok": True, "file": out_path, "skipped": True}

    entry = metadata.index_lookup(thesis_id, config)
    if not entry or not entry.get("detail_url"):
        return {
            "id": thesis_id,
            "ok": False,
            "error": "인덱스에 detail_url이 없습니다. 먼저 search로 해당 논문을 찾으세요.",
        }
    detail_url = entry["detail_url"]

    try:
        page.goto(detail_url, wait_until="domcontentloaded")
        if "login" in (page.url or "").lower():
            return {"id": thesis_id, "ok": False, "error": "로그인 만료: 다시 로그인 후 재시도"}

        meta = _parse_detail(page, thesis_id, detail_url, entry)

        button = _find_download_button(page)
        if button is None:
            return {
                "id": thesis_id,
                "ok": False,
                "error": "원문 다운로드 버튼을 찾지 못했습니다 (원문이 외부 사이트에 있거나 미제공).",
            }

        os.makedirs(config["download_dir"], exist_ok=True)
        try:
            with page.expect_download(timeout=config["timeout_sec"] * 1000) as di:
                button.click()
            di.value.save_as(out_path)
        except Exception as e:
            return {
                "id": thesis_id,
                "ok": False,
                "error": f"다운로드가 시작되지 않았습니다 (외부 뷰어/사이트 가능성): {e}",
            }

        meta["file"] = out_path
        meta["downloaded_at"] = _dt.datetime.now().isoformat(timespec="seconds")
        metadata.append(meta, config)
        time.sleep(config["delay_sec"])
        return {"id": thesis_id, "ok": True, "file": out_path}
    except Exception as e:
        return {"id": thesis_id, "ok": False, "error": str(e)}


def download_many(page, thesis_ids: list[str], config: dict) -> list[dict]:
    return [download_one(page, tid, config) for tid in thesis_ids]


def _find_download_button(page):
    for sel in selectors.DETAIL_DOWNLOAD_CANDIDATES:
        try:
            el = page.query_selector(sel)
        except Exception:
            el = None
        if el:
            return el
    return None


def _first_text(page, candidates) -> str:
    for sel in candidates:
        try:
            el = page.query_selector(sel)
        except Exception:
            el = None
        if el:
            txt = (el.inner_text() or "").strip()
            if txt:
                return txt
    return ""


def _parse_detail(page, thesis_id: str, detail_url: str, entry: dict) -> dict:
    """상세페이지 서지정보를 방어적으로 파싱한다. 실패한 필드는 비운다."""
    title = _first_text(page, selectors.DETAIL_TITLE_CANDIDATES) or entry.get("title", "")
    abstract = _first_text(page, selectors.DETAIL_ABSTRACT_CANDIDATES)
    return {
        "id": thesis_id,
        "title": title,
        "detail_url": detail_url,
        "collection": entry.get("collection", ""),
        "abstract": abstract,
    }
