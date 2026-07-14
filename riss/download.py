"""지정된 논문 ID의 원문 다운로드.

어떤 논문을 받을지 판단하지 않는다 — 호출자가 넘긴 ID만 처리한다.
ID = RISS control_no. detail_url은 index_file(검색 결과)에서 조회한다.

실 페이지 확인 결과 흐름:
  RISS 상세페이지 → '원문보기' 클릭(memberUrlDownload) → 새 팝업(외부 제공처,
  예: 교보스콜라) → 그 팝업에서 PDF 다운로드.
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

        link = _find_first(page, selectors.FULLTEXT_LINK_CANDIDATES)
        if link is None:
            return {"id": thesis_id, "ok": False, "error": "'원문보기' 링크를 찾지 못했습니다 (원문 미제공 가능)."}

        os.makedirs(config["download_dir"], exist_ok=True)
        timeout = config["timeout_sec"] * 1000

        # '원문보기'는 새 팝업을 띄운다. 팝업/다운로드 두 경우 모두 대비.
        provider = None
        try:
            with page.expect_popup(timeout=timeout) as pi:
                link.click()
            provider = pi.value
            provider.wait_for_load_state("domcontentloaded")
        except Exception:
            # 팝업이 없으면 같은 탭에서 처리됐을 수 있음
            provider = page

        provider_url = provider.url
        meta["provider_url"] = provider_url

        # 팝업(외부 제공처)에서 실제 PDF 다운로드 시도
        dl_button = _find_first(provider, selectors.PROVIDER_DOWNLOAD_CANDIDATES)
        if dl_button is None:
            return {
                "id": thesis_id,
                "ok": False,
                "error": "외부 제공처에서 다운로드 버튼을 찾지 못했습니다.",
                "provider_url": provider_url,
            }

        try:
            with provider.expect_download(timeout=timeout) as di:
                dl_button.click()
            di.value.save_as(out_path)
        except Exception as e:
            return {
                "id": thesis_id,
                "ok": False,
                "error": f"다운로드가 시작되지 않았습니다: {e}",
                "provider_url": provider_url,
            }

        meta["file"] = out_path
        meta["downloaded_at"] = _dt.datetime.now().isoformat(timespec="seconds")
        metadata.append(meta, config)
        time.sleep(config["delay_sec"])
        return {"id": thesis_id, "ok": True, "file": out_path, "provider_url": provider_url}
    except Exception as e:
        return {"id": thesis_id, "ok": False, "error": str(e)}


def download_many(page, thesis_ids: list[str], config: dict) -> list[dict]:
    return [download_one(page, tid, config) for tid in thesis_ids]


def _find_first(page, candidates):
    for sel in candidates:
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
