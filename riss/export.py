"""축적된 서지정보(metadata.jsonl)를 표준 인용 포맷으로 내보낸다.

지원: bibtex(.bib) | ris(.ris) | csljson(.json)
완벽한 서식 변환은 목적이 아니다 — 가진 필드로 최선을 다해 채우고,
부족한 필드는 비운다. 최종 서식은 이후 AI/레퍼런스 매니저가 다듬는다.
"""

import json
import os
import re


def _records(config: dict) -> list[dict]:
    path = config["metadata_file"]
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _year(rec: dict) -> str:
    """발행연도에서 YYYY만 뽑는다."""
    bib = rec.get("bib", {})
    for key in ("발행연도", "발행년도", "연도", "발행일"):
        v = bib.get(key)
        if v:
            m = re.search(r"(\d{4})", v)
            if m:
                return m.group(1)
    m = re.search(r"(\d{4})", rec.get("provider_bib_text", "") or "")
    return m.group(1) if m else ""


def _pages(rec: dict) -> tuple[str, str]:
    """페이지 범위 (시작, 끝). 없으면 ('','')."""
    bib = rec.get("bib", {})
    text = str(bib.get("페이지", "")) + " " + (rec.get("provider_bib_text", "") or "")
    m = re.search(r"(\d+)\s*[-~]\s*(\d+)", text)
    return (m.group(1), m.group(2)) if m else ("", "")


def _authors(rec: dict) -> list[str]:
    """저자 목록. '홍길동(Hong)' 형태면 한글 이름만 취한다."""
    bib = rec.get("bib", {})
    raw = bib.get("저자")
    if isinstance(raw, list):
        names = raw
    elif isinstance(raw, str):
        names = re.findall(r"[가-힣]{2,}\([^)]*\)|[가-힣]{2,}", raw)
    else:
        names = re.findall(r"[가-힣]{2,}\([A-Za-z][A-Za-z .]*\)",
                           rec.get("provider_bib_text", "") or "")
    cleaned = []
    for n in names:
        n = re.sub(r"\s*\(.*?\)\s*", "", n).strip()  # 괄호(영문명) 제거
        if n and n not in cleaned:
            cleaned.append(n)
    return cleaned


def _journal(rec: dict) -> str:
    """학술지명(수록지). bib 라벨 우선, 없으면 provider 텍스트 첫 줄 추정."""
    bib = rec.get("bib", {})
    for key in ("학술지명", "수록지명", "저널명", "학술지", "수록지", "발행처"):
        if bib.get(key):
            return bib[key]
    text = (rec.get("provider_bib_text", "") or "").strip()
    if text:
        first = text.splitlines()[0].strip()
        if first and len(first) <= 60:
            return first
    return ""


FORMATS = ["bibtex", "ris", "csljson", "apa", "korean"]


def build(config: dict, fmt: str) -> str:
    """metadata.jsonl 전체를 fmt 문자열로 변환해 반환한다.

    기계용: bibtex | ris | csljson
    사람용(바로 붙여넣는 참고문헌 목록): apa | korean
    """
    recs = _records(config)
    if fmt == "bibtex":
        return "\n".join(_to_bibtex(r) for r in recs) + ("\n" if recs else "")
    if fmt == "ris":
        return "\n".join(_to_ris(r) for r in recs)
    if fmt == "csljson":
        return json.dumps([_to_csl(r) for r in recs], ensure_ascii=False, indent=2)
    if fmt in ("apa", "korean"):
        return _to_bibliography(recs, fmt)
    raise ValueError(f"지원하지 않는 형식: {fmt} ({'|'.join(FORMATS)})")


def library(config: dict) -> list[dict]:
    """다운로드 완료된 참고문헌을 정리된 필드로 반환한다 (라이브러리/정리 뷰)."""
    out = []
    for r in sorted(_records(config), key=_sort_key):
        sp, ep = _pages(r)
        out.append({
            "id": r.get("id", ""),
            "title": r.get("title", ""),
            "authors": _authors(r),
            "year": _year(r),
            "journal": _journal(r),
            "pages": f"{sp}-{ep}" if sp and ep else "",
            "file": r.get("file", ""),
        })
    return out


def _sort_key(rec: dict):
    authors = _authors(rec)
    return ((authors[0] if authors else "힣"), _year(rec), rec.get("title", ""))


def _to_bibliography(recs: list[dict], style: str) -> str:
    """저자→연도 순으로 정렬된, 바로 붙여넣는 참고문헌 목록을 만든다.

    스타일별 세부 규칙은 학회마다 다르므로 근사치다. 정확한 서식이 필요하면
    metadata.jsonl의 원본(provider_bib_text 등)으로 이후에 다듬는다.
    """
    lines = [_format_citation(r, style) for r in sorted(recs, key=_sort_key)]
    header = "% APA 근사 형식" if style == "apa" else "% 한국식(KCI) 근사 형식"
    return header + " — 학회 규정에 맞게 확인/수정 필요\n\n" + "\n\n".join(lines) + ("\n" if lines else "")


def _format_citation(rec: dict, style: str) -> str:
    authors = _authors(rec)
    year = _year(rec)
    title = (rec.get("title", "") or "").strip().rstrip(".")
    journal = _journal(rec)
    sp, ep = _pages(rec)
    pages = f"{sp}-{ep}" if sp and ep else ""

    if style == "apa":
        # 홍길동, & 이몽룡 (2009). 제목. 학술지, 43-47.
        if len(authors) >= 2:
            auth = ", ".join(authors[:-1]) + ", & " + authors[-1]
        elif authors:
            auth = authors[0]
        else:
            auth = ""
        parts = []
        if auth:
            parts.append(f"{auth} ({year}).")
        elif year:
            parts.append(f"({year}).")
        if title:
            parts.append(f"{title}.")
        tail = journal
        if pages:
            tail = (tail + ", " + pages) if tail else pages
        if tail:
            parts.append(tail + ".")
        return " ".join(parts).strip()

    # korean: 홍길동·이몽룡 (2009). 제목. 「학술지」, 43-47.
    auth = "·".join(authors)
    parts = []
    if auth:
        parts.append(f"{auth} ({year}).")
    elif year:
        parts.append(f"({year}).")
    if title:
        parts.append(f"{title}.")
    tail = f"「{journal}」" if journal else ""
    if pages:
        tail = (tail + ", " + pages) if tail else pages
    if tail:
        parts.append(tail + ".")
    return " ".join(parts).strip()


def _bib_escape(s: str) -> str:
    return (s or "").replace("{", "").replace("}", "").strip()


def _to_bibtex(rec: dict) -> str:
    authors = _authors(rec)
    sp, ep = _pages(rec)
    year = _year(rec)
    key = (authors[0] if authors else "ref") + (year or "") + "_" + (rec.get("id", "")[:6])
    key = re.sub(r"[^0-9A-Za-z가-힣_]", "", key) or "ref"
    lines = [f"@article{{{key},"]
    fields = [
        ("title", _bib_escape(rec.get("title", ""))),
        ("author", " and ".join(authors)),
        ("journal", _bib_escape(_journal(rec))),
        ("year", year),
        ("pages", f"{sp}--{ep}" if sp and ep else ""),
        ("url", rec.get("detail_url", "")),
    ]
    body = [f"  {k} = {{{v}}}," for k, v in fields if v]
    lines.extend(body)
    lines.append("}")
    return "\n".join(lines)


def _to_ris(rec: dict) -> str:
    authors = _authors(rec)
    sp, ep = _pages(rec)
    year = _year(rec)
    lines = ["TY  - JOUR", f"TI  - {rec.get('title','')}"]
    for a in authors:
        lines.append(f"AU  - {a}")
    if _journal(rec):
        lines.append(f"JO  - {_journal(rec)}")
    if year:
        lines.append(f"PY  - {year}")
    if sp:
        lines.append(f"SP  - {sp}")
    if ep:
        lines.append(f"EP  - {ep}")
    if rec.get("detail_url"):
        lines.append(f"UR  - {rec['detail_url']}")
    if rec.get("abstract"):
        lines.append(f"AB  - {rec['abstract']}")
    lines.append("ER  - ")
    return "\n".join(lines) + "\n"


def _to_csl(rec: dict) -> dict:
    authors = _authors(rec)
    sp, ep = _pages(rec)
    year = _year(rec)
    item = {
        "type": "article-journal",
        "id": rec.get("id", ""),
        "title": rec.get("title", ""),
    }
    if authors:
        item["author"] = [{"family": a} for a in authors]
    if _journal(rec):
        item["container-title"] = _journal(rec)
    if year:
        item["issued"] = {"date-parts": [[int(year)]]}
    if sp and ep:
        item["page"] = f"{sp}-{ep}"
    if rec.get("detail_url"):
        item["URL"] = rec["detail_url"]
    if rec.get("abstract"):
        item["abstract"] = rec["abstract"]
    return item
