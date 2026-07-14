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


def build(config: dict, fmt: str) -> str:
    """metadata.jsonl 전체를 fmt 문자열로 변환해 반환한다."""
    recs = _records(config)
    if fmt == "bibtex":
        return "\n".join(_to_bibtex(r) for r in recs) + ("\n" if recs else "")
    if fmt == "ris":
        return "\n".join(_to_ris(r) for r in recs)
    if fmt == "csljson":
        return json.dumps([_to_csl(r) for r in recs], ensure_ascii=False, indent=2)
    raise ValueError(f"지원하지 않는 형식: {fmt} (bibtex|ris|csljson)")


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
