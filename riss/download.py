"""지정된 논문 ID의 원문 다운로드.

어떤 논문을 받을지 판단하지 않는다 — 호출자가 넘긴 ID만 처리한다.
ID = RISS control_no. detail_url은 index_file(검색 결과)에서 조회한다.

실 페이지 확인 결과 흐름:
  RISS 상세페이지 → '원문보기' 클릭(memberUrlDownload) → RISS 중간 로더
  (UrlLoad.do) 팝업 → 자동 리다이렉트로 외부 제공처(예: 교보스콜라) 도착
  → 거기서 '원문저장' 클릭 → PDF 다운로드.
"""

import datetime as _dt
import os
import time
from urllib.parse import urlparse

from . import metadata, selectors


def download_one(page, thesis_id: str, config: dict) -> dict:
    """논문 1건을 다운로드하고 결과 dict를 반환한다. 예외를 던지지 않는다."""
    entry = metadata.index_lookup(thesis_id, config)
    if not entry or not entry.get("detail_url"):
        return {
            "id": thesis_id,
            "ok": False,
            "error": "인덱스에 detail_url이 없습니다. 먼저 search로 해당 논문을 찾으세요.",
        }
    detail_url = entry["detail_url"]

    # 파일명은 논문 제목(기본형). 동일 제목의 다른 논문 충돌 시 id 일부를 붙임.
    out_path = _out_path(config, entry.get("title") or thesis_id, thesis_id)
    if os.path.exists(out_path):
        return {"id": thesis_id, "ok": True, "file": out_path, "skipped": True}

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
        base_host = urlparse(config["base_url"]).netloc

        # '원문보기'는 RISS 중간 로더(UrlLoad.do) 팝업을 띄우고, 그게 외부
        # 제공처로 리다이렉트된다. 팝업이 RISS를 벗어날 때까지 기다린다.
        pages_before = list(page.context.pages)
        try:
            with page.expect_popup(timeout=timeout) as pi:
                link.click()
            popup = pi.value
        except Exception:
            popup = None

        provider = _wait_for_provider(page.context, base_host, pages_before, popup, timeout)
        if provider is None:
            return {
                "id": thesis_id,
                "ok": False,
                "error": "'원문보기' 후 외부 제공처 창을 찾지 못했습니다.",
                "provider_url": (popup.url if popup else ""),
            }
        try:
            provider.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass
        provider_url = provider.url
        meta["provider_url"] = provider_url

        if base_host in provider_url:
            return {
                "id": thesis_id,
                "ok": False,
                "error": "외부 제공처로 리다이렉트되지 않았습니다 (RISS 로더에 머묾).",
                "provider_url": provider_url,
            }

        # 외부 제공처(교보스콜라)에서 '원문저장' 클릭 → PDF 다운로드
        dl_button = _find_visible(provider, selectors.PROVIDER_DOWNLOAD_CANDIDATES)
        if dl_button is None:
            return {
                "id": thesis_id,
                "ok": False,
                "error": "외부 제공처에서 '원문저장' 버튼을 찾지 못했습니다.",
                "provider_url": provider_url,
            }

        # 다운로드는 현재 탭 또는 새 팝업 어디서든 시작될 수 있어 둘 다 대비.
        download = _click_and_capture_download(provider, dl_button, timeout)
        if download is None:
            return {
                "id": thesis_id,
                "ok": False,
                "error": "'원문저장' 클릭 후 다운로드가 시작되지 않았습니다 (뷰어로 열렸을 수 있음).",
                "provider_url": provider_url,
            }
        download.save_as(out_path)

        meta["file"] = out_path
        meta["downloaded_at"] = _dt.datetime.now().isoformat(timespec="seconds")
        metadata.append(meta, config)
        time.sleep(config["delay_sec"])
        return {"id": thesis_id, "ok": True, "file": out_path, "provider_url": provider_url}
    except Exception as e:
        return {"id": thesis_id, "ok": False, "error": str(e)}


def download_many(page, thesis_ids: list[str], config: dict) -> list[dict]:
    return [download_one(page, tid, config) for tid in thesis_ids]


def _wait_for_provider(context, base_host, pages_before, popup, timeout):
    """'원문보기' 후 RISS를 벗어나 외부 제공처로 이동한 페이지를 찾는다.

    로더 팝업(UrlLoad.do)이 같은 창에서 리다이렉트하는 경우와, 새 창을
    다시 여는 경우를 모두 대비한다. 기존에 열려있던 탭은 무시한다.
    실패 시 (있으면) popup을, 없으면 None을 반환한다.
    """
    before_ids = {id(p) for p in pages_before}
    deadline = time.time() + timeout / 1000.0
    while time.time() < deadline:
        # 1) 로더 팝업이 스스로 외부로 리다이렉트한 경우
        if popup is not None:
            try:
                u = popup.url or ""
            except Exception:
                u = ""
            if u.startswith("http") and base_host not in u:
                return popup
        # 2) 새 창이 다시 열려 외부로 간 경우
        for pg in context.pages:
            if id(pg) in before_ids:
                continue
            if popup is not None and pg is popup:
                continue
            try:
                u = pg.url or ""
            except Exception:
                u = ""
            if u.startswith("http") and base_host not in u:
                return pg
        time.sleep(0.5)
    return popup


def _find_first(page, candidates):
    for sel in candidates:
        try:
            el = page.query_selector(sel)
        except Exception:
            el = None
        if el:
            return el
    return None


def _find_visible(page, candidates):
    """후보 중 실제로 '보이는' 요소를 반환 (중복 배치된 버튼 대비)."""
    for sel in candidates:
        try:
            els = page.query_selector_all(sel)
        except Exception:
            els = []
        for el in els:
            try:
                if el.is_visible():
                    return el
            except Exception:
                continue
    return None


def _click_and_capture_download(provider, button, timeout):
    """button 클릭 후 다운로드를 잡는다. 현재 탭/새 팝업 어디서 시작되든 대응.

    성공 시 Download 객체, 실패 시 None.
    """
    ctx = provider.context
    # 1) 현재 탭에서 다운로드가 시작되는 경우
    try:
        with provider.expect_download(timeout=timeout) as di:
            button.click()
        return di.value
    except Exception:
        pass
    # 2) 새 팝업이 열리고 그 팝업에서 다운로드가 시작되는 경우
    for pg in ctx.pages:
        if pg is provider:
            continue
        try:
            with pg.expect_download(timeout=5000) as di:
                pass  # 팝업 로드 과정에서 자동 시작되는 다운로드 포착
            return di.value
        except Exception:
            continue
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
    """상세페이지 서지정보를 방어적으로 파싱한다.

    개별 필드를 완벽히 구조화하기보다, 상세페이지의 '라벨:값' 쌍을 통째로
    bib에 담아둔다 → 나중에 AI가 필요한 서식(저자/연도/페이지 등)으로 변환.
    """
    title = entry.get("title") or _first_text(page, selectors.DETAIL_TITLE_CANDIDATES)
    abstract = _first_text(page, selectors.DETAIL_ABSTRACT_CANDIDATES)
    return {
        "id": thesis_id,
        "title": title,
        "detail_url": detail_url,
        "collection": entry.get("collection", ""),
        "abstract": abstract,
        "bib": _extract_bib(page),
    }


def _extract_bib(page) -> dict:
    """상세페이지의 서지 라벨:값 쌍을 dict로 뽑는다. (dl>dt/dd, tr>th/td)"""
    bib: dict[str, str] = {}
    try:
        for dl in page.query_selector_all("dl"):
            dts = dl.query_selector_all("dt")
            dds = dl.query_selector_all("dd")
            for dt, dd in zip(dts, dds):
                label = (dt.inner_text() or "").strip()
                value = " ".join((dd.inner_text() or "").split()).strip()
                if label and value and label not in bib:
                    bib[label] = value
        for tr in page.query_selector_all("tr"):
            th = tr.query_selector("th")
            td = tr.query_selector("td")
            if th and td:
                label = (th.inner_text() or "").strip()
                value = " ".join((td.inner_text() or "").split()).strip()
                if label and value and label not in bib:
                    bib[label] = value
    except Exception:
        pass
    return bib


def _out_path(config: dict, title: str, thesis_id: str) -> str:
    """제목 기반 파일 경로. 동일 제목의 다른 논문과 충돌하면 id 일부를 덧붙임."""
    base = _safe_filename(title)
    path = os.path.join(config["download_dir"], f"{base}.pdf")
    if os.path.exists(path) and thesis_id not in metadata.load_ids(config):
        path = os.path.join(config["download_dir"], f"{base} ({thesis_id[:6]}).pdf")
    return path


def _safe_filename(name: str, max_len: int = 150) -> str:
    """Windows/공통 파일명 규칙에 맞게 정리한다."""
    name = " ".join((name or "").split())          # 개행/중복 공백 정리
    for ch in '\\/:*?"<>|':                          # 금지문자 → 공백
        name = name.replace(ch, " ")
    name = " ".join(name.split()).strip(" .")        # 다시 정리 + 끝의 . 제거
    if len(name) > max_len:
        name = name[:max_len].strip()
    return name or "untitled"
