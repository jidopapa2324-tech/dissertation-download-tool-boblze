"""인용문 추출 + 밑줄(Zotero-lite).

다운로드한 PDF에서 문장을 선택해 저장하면:
  1) 인용문 + 서지정보(저자·연도·페이지)를 data/quotes.jsonl 에 축적
  2) 그 문장을 PDF에서 찾아 '밑줄 친 사본'(reference/annotated/{id}.pdf)에 누적

PyMuPDF(pymupdf)는 함수 안에서 지연 import 한다(시작 속도/의존성 분리).
스캔본(텍스트 레이어 없는) PDF는 추출/밑줄이 불가하다.
"""

import datetime as _dt
import json
import os
import shutil

from . import export


# --- 유틸 ---------------------------------------------------------------
def _norm(s: str) -> str:
    return " ".join((s or "").split())


def _quotes_path(config: dict) -> str:
    return config.get("quotes_file", "data/quotes.jsonl")


def _annotated_dir(config: dict) -> str:
    return config.get("annotated_dir", "reference/annotated")


def find_record(config: dict, paper_id: str) -> dict | None:
    """metadata.jsonl(다운로드 완료본)에서 해당 논문 레코드를 찾는다."""
    for r in export._records(config):
        if r.get("id") == paper_id:
            return r
    return None


# --- PDF 텍스트 ---------------------------------------------------------
def extract_pages(pdf_path: str) -> list[str]:
    """페이지별 텍스트 리스트. 스캔본이면 대부분 빈 문자열."""
    import pymupdf

    doc = pymupdf.open(pdf_path)
    try:
        return [pg.get_text() for pg in doc]
    finally:
        doc.close()


def has_text(pdf_path: str) -> bool:
    try:
        return any(p.strip() for p in extract_pages(pdf_path))
    except Exception:
        return False


def _find_page(pages: list[str], quote: str) -> str:
    """인용문이 있는 페이지 번호(1-based, 문자열). 못 찾으면 ''."""
    nq = _norm(quote)
    for i, t in enumerate(pages):
        if nq and nq in _norm(t):
            return str(i + 1)
    return ""


# --- 밑줄 주석 ----------------------------------------------------------
def _annotate(config: dict, paper_id: str, src_pdf: str, quote: str) -> bool:
    """annotated 사본에 밑줄을 누적한다. 성공 시 True."""
    import pymupdf

    os.makedirs(_annotated_dir(config), exist_ok=True)
    dst = os.path.join(_annotated_dir(config), f"{paper_id}.pdf")
    if not os.path.exists(dst):
        shutil.copyfile(src_pdf, dst)

    doc = pymupdf.open(dst)
    try:
        added = False
        for page in doc:
            rects = page.search_for(quote)
            if not rects:
                # 여러 줄에 걸치면 실패할 수 있어 앞부분만 재시도
                head = quote.strip()[:40]
                if len(head) >= 8:
                    rects = page.search_for(head)
            if rects:
                page.add_underline_annot(rects)
                added = True
                break
        if not added:
            return False
        tmp = dst + ".tmp"
        doc.save(tmp, garbage=3, deflate=True)
    finally:
        doc.close()
    os.replace(tmp, dst)
    return True


# --- 인용 저장/조회 -----------------------------------------------------
def _citation_fields(rec: dict) -> dict:
    return {
        "title": rec.get("title", ""),
        "authors": export._authors(rec),
        "year": export._year(rec),
        "journal": export._journal(rec),
    }


def _load_quotes(config: dict) -> list[dict]:
    path = _quotes_path(config)
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def add_quote(config: dict, paper_id: str, quote: str) -> dict:
    """인용문을 저장하고 밑줄 사본을 갱신한다. 예외를 던지지 않는다."""
    quote = (quote or "").strip()
    if not quote:
        return {"ok": False, "error": "빈 인용문입니다."}
    rec = find_record(config, paper_id)
    if not rec:
        return {"ok": False, "error": "해당 논문이 다운로드 목록에 없습니다 (먼저 다운로드하세요)."}

    # 중복 방지 (같은 논문의 동일 인용문)
    for q in _load_quotes(config):
        if q.get("id") == paper_id and _norm(q.get("quote", "")) == _norm(quote):
            return {"ok": True, "quote": q, "annotated": False, "duplicate": True}

    pdf = rec.get("file", "")
    page_no = ""
    annotated = False
    if pdf and os.path.exists(pdf):
        try:
            page_no = _find_page(extract_pages(pdf), quote)
        except Exception:
            page_no = ""
        try:
            annotated = _annotate(config, paper_id, pdf, quote)
        except Exception:
            annotated = False

    entry = {
        "id": paper_id,
        "quote": quote,
        "page": page_no,
        "saved_at": _dt.datetime.now().isoformat(timespec="seconds"),
        **_citation_fields(rec),
    }
    path = _quotes_path(config)
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"ok": True, "quote": entry, "annotated": annotated}


def list_quotes(config: dict, paper_id: str | None = None) -> list[dict]:
    qs = _load_quotes(config)
    if paper_id:
        qs = [q for q in qs if q.get("id") == paper_id]
    return qs


# --- 인용/노트 서식 -----------------------------------------------------
def format_quote(entry: dict, style: str = "korean") -> str:
    """복붙용 문자열: "인용문" (저자, 연도, 페이지)."""
    authors = entry.get("authors") or []
    year = entry.get("year", "")
    page = entry.get("page", "")
    quote = entry.get("quote", "").strip()

    if style == "apa":
        if len(authors) >= 2:
            au = ", ".join(authors[:-1]) + ", & " + authors[-1]
        else:
            au = authors[0] if authors else ""
        loc = f"{au}, {year}" if au else year
        if page:
            loc += f", p. {page}"
        return f'"{quote}" ({loc})'

    # korean
    au = "·".join(authors)
    loc = f"{au}, {year}" if au else year
    if page:
        loc += f", {page}쪽"
    return f'"{quote}" ({loc})'


def export_notes(config: dict, style: str = "korean") -> str:
    """모든 인용을 논문별로 묶어 노트 텍스트로 만든다 (Zotero '주석에서 노트')."""
    quotes = _load_quotes(config)
    by_paper: dict[str, list[dict]] = {}
    titles: dict[str, str] = {}
    for q in quotes:
        by_paper.setdefault(q["id"], []).append(q)
        titles[q["id"]] = q.get("title", "")
    blocks = []
    for pid, qs in by_paper.items():
        header = titles.get(pid) or pid
        lines = [f"## {header}"]
        for q in qs:
            lines.append(f"- {format_quote(q, style)}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + ("\n" if blocks else "")
