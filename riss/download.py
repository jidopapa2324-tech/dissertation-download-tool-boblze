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
import re
import time
from urllib.parse import urlparse

from . import metadata, selectors


def _acquire(page, thesis_id: str, config: dict, entry: dict | None, step=None) -> dict:
    """논문 1건의 '다운로드 시작'까지 진행한다 (저장은 하지 않음).

    반환 dict의 "_kind":
      - "skip"    : 이미 받음. "result"에 최종 결과.
      - "fail"    : 실패. "result"에 최종 결과.
      - "started" : 다운로드가 시작됨. download/out_path/meta/provider/_popups 포함.
    저장/검증/메타기록/팝업정리는 _finalize에서 한다 → 다음 논문과 겹쳐 처리 가능.
    """
    def _step(msg):
        if step:
            step(msg)

    if not entry or not entry.get("detail_url"):
        return {"_kind": "fail", "result": {
            "id": thesis_id, "ok": False,
            "error": "인덱스에 detail_url이 없습니다. 먼저 search로 해당 논문을 찾으세요.",
            "retryable": False,
        }}
    detail_url = entry["detail_url"]

    # 학술지(저널) 자체 레코드는 원문이 없다 → 즉시 건너뜀(20초 타임아웃/재시도 방지).
    if selectors.P_MAT_TYPE_JOURNAL in detail_url:
        _step("학술지 레코드 → 건너뜀(원문 없음)")
        return {"_kind": "skip", "result": {
            "id": thesis_id, "ok": True, "skipped": True, "file": "",
            "reason": "학술지(저널) 레코드 — 원문 없음",
        }}

    out_path = _out_path(config, entry.get("title") or thesis_id, thesis_id)
    if os.path.exists(out_path):
        _step("이미 받음 → 건너뜀")
        return {"_kind": "skip", "result": {
            "id": thesis_id, "ok": True, "file": out_path, "skipped": True,
        }}

    def _fail(msg, provider_url="", retryable=True):
        return {"_kind": "fail", "result": {
            "id": thesis_id, "ok": False, "error": msg,
            "provider_url": provider_url, "retryable": retryable,
        }}

    try:
        _step("상세페이지 여는 중...")
        page.goto(detail_url, wait_until="domcontentloaded")
        if "login" in (page.url or "").lower():
            return _fail("로그인 만료: 다시 로그인 후 재시도", retryable=False)

        meta = _parse_detail(page, thesis_id, detail_url, entry)

        link = _find_first(page, selectors.FULLTEXT_LINK_CANDIDATES)
        if link is None:
            return _fail("'원문보기' 링크를 찾지 못했습니다 (원문 미제공 가능).", retryable=False)

        os.makedirs(config["download_dir"], exist_ok=True)
        timeout = config["timeout_sec"] * 1000
        base_host = urlparse(config["base_url"]).netloc

        _step("원문보기 클릭, 제공처로 이동 중...")
        pages_before = list(page.context.pages)
        try:
            with page.expect_popup(timeout=timeout) as pi:
                link.click()
            popup = pi.value
        except Exception:
            popup = None

        provider = _wait_for_provider(page.context, base_host, pages_before, popup, timeout)
        # 이 논문 때문에 새로 열린 팝업들(로더/제공처/다운로드창) — 나중에 정리
        popups = [pg for pg in page.context.pages if pg not in pages_before]
        if provider is None:
            return {"_kind": "fail", "result": {
                "id": thesis_id, "ok": False,
                "error": "'원문보기' 후 외부 제공처 창을 찾지 못했습니다.",
                "provider_url": (popup.url if popup else ""),
                "retryable": True,
            }, "_popups": popups}
        try:
            provider.wait_for_load_state("domcontentloaded", timeout=timeout)
        except Exception:
            pass
        provider_url = provider.url
        meta["provider_url"] = provider_url

        if base_host in provider_url:
            return {"_kind": "fail", "result": {
                "id": thesis_id, "ok": False,
                "error": "외부 제공처로 리다이렉트되지 않았습니다 (RISS 로더에 머묾).",
                "provider_url": provider_url,
                "retryable": True,
            }, "_popups": popups}

        dl_button = _find_visible_wait(provider, selectors.PROVIDER_DOWNLOAD_CANDIDATES, timeout)
        _step("서지정보 수집 중...")
        _capture_provider_bib(provider, meta)
        if dl_button is None:
            return {"_kind": "fail", "result": {
                "id": thesis_id, "ok": False,
                "error": "외부 제공처에서 '원문저장' 버튼을 찾지 못했습니다.",
                "provider_url": provider_url,
                "retryable": True,
            }, "_popups": popups}

        _step("다운로드 시작 중...")
        download = _click_and_capture_download(provider, dl_button, timeout)
        popups = [pg for pg in page.context.pages if pg not in pages_before]
        if download is None:
            return {"_kind": "fail", "result": {
                "id": thesis_id, "ok": False,
                "error": "'원문저장' 클릭 후 다운로드가 시작되지 않았습니다 (뷰어로 열렸을 수 있음).",
                "provider_url": provider_url,
                "retryable": True,
            }, "_popups": popups}

        return {
            "_kind": "started",
            "id": thesis_id,
            "download": download,
            "out_path": out_path,
            "meta": meta,
            "provider_url": provider_url,
            "_popups": popups,
        }
    except Exception as e:
        return _fail(str(e))


def _finalize(item: dict, config: dict) -> dict:
    """시작된 다운로드를 저장→PDF 검증→메타 기록→팝업 정리 후 결과를 반환한다."""
    thesis_id = item["id"]
    out_path = item["out_path"]
    provider_url = item.get("provider_url", "")
    try:
        item["download"].save_as(out_path)  # 파일이 완전히 받아질 때까지 대기
    except Exception as e:
        _close_popups(item.get("_popups"))
        return {"id": thesis_id, "ok": False,
                "error": f"파일 저장 실패: {e}", "provider_url": provider_url,
                "retryable": True}

    # #3 무결성 검증: 실제 PDF인지 확인 (HTML 오류페이지 등을 걸러냄)
    if not _looks_like_pdf(out_path):
        try:
            os.remove(out_path)
        except Exception:
            pass
        _close_popups(item.get("_popups"))
        return {"id": thesis_id, "ok": False,
                "error": "받은 파일이 정상 PDF가 아닙니다 (원문 미제공/오류페이지 가능). 삭제함.",
                "provider_url": provider_url, "retryable": False}

    meta = item["meta"]
    meta["file"] = out_path
    meta["downloaded_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    metadata.append(meta, config)
    _close_popups(item.get("_popups"))
    return {"id": thesis_id, "ok": True, "file": out_path, "provider_url": provider_url}


def _looks_like_pdf(path: str, min_bytes: int = 1024) -> bool:
    """저장된 파일이 실제 PDF인지 확인한다 (헤더 %PDF- + 최소 크기)."""
    try:
        if os.path.getsize(path) < min_bytes:
            return False
        with open(path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except Exception:
        return False


def _close_popups(popups) -> None:
    for pg in (popups or []):
        try:
            pg.close()
        except Exception:
            pass


def download_one(page, thesis_id: str, config: dict, step=None) -> dict:
    """논문 1건을 받아 최종 결과를 반환한다 (겹치기 없이 단건 처리)."""
    entry = metadata.index_lookup(thesis_id, config)
    item = _acquire(page, thesis_id, config, entry, step=step)
    if item["_kind"] != "started":
        return item["result"]
    return _finalize(item, config)


def download_many(page, thesis_ids: list[str], config: dict, report=None) -> list[dict]:
    """여러 논문을 받는다. 다운로드가 '시작'되면 곧바로 다음 논문으로 진행하고,
    파일 저장(마무리)은 뒤이어 겹쳐서 처리한다. 동시에 열리는 팝업 수를
    config['overlap_batch'](기본 4)로 제한한다.

    report(i, total, title, phase, data):
      phase="start" | "step"(data=메시지) | "started"(다운로드 시작) |
            "done"(건너뜀/실패 즉시확정, data=결과) | "saved"(마무리 완료, data=결과)
    """
    total = len(thesis_ids)
    batch = max(1, int(config.get("overlap_batch", 4)))
    ordered: dict[int, dict] = {}
    pending: list[dict] = []

    def flush():
        for it in pending:
            res = _finalize(it, config)
            if report:
                report(it["_i"], total, it["_title"], "saved", res)
            ordered[it["_i"]] = res
        pending.clear()

    for i, tid in enumerate(thesis_ids, 1):
        entry = metadata.index_lookup(tid, config)
        title = (entry.get("title") if entry else "") or tid
        if report:
            report(i, total, title, "start", None)
        step = (lambda msg, _i=i, _t=title: report(_i, total, _t, "step", msg)) if report else None

        item = _acquire(page, tid, config, entry, step=step)
        item["_i"] = i
        item["_title"] = title

        if item["_kind"] == "started":
            if report:
                report(i, total, title, "started", None)
            pending.append(item)
            if len(pending) >= batch:
                flush()
        else:
            res = item["result"]
            if report:
                report(i, total, title, "done", res)
            ordered[i] = res

        # 정중한 간격 (서버 부하/계정 보호)
        if i < total:
            time.sleep(config["delay_sec"])

    flush()
    results = [ordered[k] for k in sorted(ordered)]

    # #1 자동 재시도: 일시적 실패(retryable)만 백오프를 두고 다시 시도
    results = _retry_failed(page, results, config, report)
    return results


def _retry_failed(page, results, config, report=None) -> list[dict]:
    """retryable 실패를 max_retries회까지 지수 백오프로 재시도한다 (겹치기 없이 단건)."""
    max_retries = int(config.get("max_retries", 2))
    by_id = {r["id"]: r for r in results}
    total = len(results)
    for attempt in range(1, max_retries + 1):
        targets = [r for r in results if not r["ok"] and r.get("retryable")]
        if not targets:
            break
        backoff = 2 ** attempt  # 2초, 4초, ...
        if report:
            print_msg = f"\n[재시도 {attempt}/{max_retries}] {len(targets)}건 (대기 {backoff}초)"
            report(0, total, print_msg, "retry_header", None)
        time.sleep(backoff)
        for r in targets:
            tid = r["id"]
            entry = metadata.index_lookup(tid, config)
            title = (entry.get("title") if entry else "") or tid
            if report:
                report(0, total, title, "retry_start", None)
            new_r = download_one(page, tid, config)
            new_r.setdefault("retryable", r.get("retryable", False))
            by_id[tid].clear()
            by_id[tid].update(new_r)
            if report:
                report(0, total, title, "retry_done", new_r)
            time.sleep(config["delay_sec"])
    return results


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


def _find_visible_wait(page, candidates, timeout_ms):
    """후보 버튼이 나타날 때까지 짧게 폴링하며 기다린다 (networkidle 대체).

    페이지가 완전히 idle 되기 전이라도 버튼이 보이면 즉시 진행 → 속도 향상.
    """
    deadline = time.time() + min(timeout_ms, 15000) / 1000.0
    while time.time() < deadline:
        el = _find_visible(page, candidates)
        if el is not None:
            return el
        time.sleep(0.3)
    return _find_visible(page, candidates)


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


def _capture_provider_bib(provider, meta: dict) -> None:
    """외부 제공처 페이지의 서지 텍스트를 통째로 저장하고 주요 필드를 추출한다.

    구조를 몰라도 정보를 잃지 않도록 페이지 텍스트를 보관(provider_bib_text)하고,
    발행연도/페이지/저자는 정규식으로 뽑아 meta['bib']에 병합한다.
    """
    text = ""
    for sel in selectors.PROVIDER_INFO_CANDIDATES:
        try:
            el = provider.query_selector(sel)
        except Exception:
            el = None
        if el:
            t = (el.inner_text() or "").strip()
            if t:
                text = t
                break
    if not text:
        try:
            text = provider.inner_text("body")
        except Exception:
            text = ""
    text = text.strip()  # 개행은 보존(가독성/후처리용)
    if len(text) > 6000:
        text = text[:6000]
    meta["provider_bib_text"] = text

    bib = meta.setdefault("bib", {})
    m = re.search(r"(\d{4}\.\d{2})", text)
    if m:
        bib.setdefault("발행연도", m.group(1))
    m = re.search(r"(\d+\s*[-~]\s*\d+\s*\(\s*\d+\s*pages?\s*\))", text)
    if m:
        bib.setdefault("페이지", re.sub(r"\s+", " ", m.group(1)))
    authors = re.findall(r"[가-힣]{2,}\([A-Za-z][A-Za-z .]*\)", text)
    if authors:
        # 순서 유지 중복 제거
        seen = []
        for a in authors:
            if a not in seen:
                seen.append(a)
        bib.setdefault("저자", seen[:10])


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
