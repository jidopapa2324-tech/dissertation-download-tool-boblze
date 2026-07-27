"""축적된 서지정보(metadata.jsonl)를 표준 인용 포맷으로 내보낸다.

기계용: bibtex(.bib) | ris(.ris) | csljson(.json)
사람용: apa | korean  (논문에 바로 붙여넣는 참고문헌 목록)

자료유형(학위논문/학술논문/단행본/보고서)에 따라 인용 서식이 다르므로
detail_url의 p_mat_type(selectors.MAT_TYPES)으로 판별해 분기한다.
완벽한 학회별 서식이 목적은 아니다 — 가진 필드로 최선을 다해 채우고,
부족한 필드는 비운다. 원본 텍스트(provider_bib_text)는 그대로 보존되므로
필요하면 이후에 더 다듬을 수 있다.
"""

import json
import os
import re

from . import selectors


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


def _bib_blob(rec: dict) -> str:
    """bib의 문자열 값 + 제공처 원문 텍스트를 한 덩어리로 (자유 텍스트 탐색용)."""
    parts = []
    for v in (rec.get("bib") or {}).values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(str(x) for x in v)
    parts.append(rec.get("provider_bib_text", "") or "")
    return " ".join(parts)


# --- 자료유형 -----------------------------------------------------------
def _doc_type(rec: dict) -> str:
    """thesis | article | book | report | journal | media."""
    m = re.search(r"p_mat_type=([0-9a-f]+)", rec.get("detail_url", "") or "")
    if m:
        t = selectors.MAT_TYPES.get(m.group(1))
        if t:
            return t
    col = rec.get("collection", "")
    if col == selectors.COLLECTIONS["thesis"]:
        return "thesis"
    if col == selectors.COLLECTIONS["article"]:
        return "article"
    if "학위논문" in _bib_blob(rec):
        return "thesis"
    return "article"


# --- 개별 필드 ----------------------------------------------------------
def _year(rec: dict) -> str:
    """발행연도에서 YYYY만 뽑는다."""
    bib = rec.get("bib", {})
    for key in ("발행연도", "발행년도", "연도", "발행일", "수여연도"):
        v = bib.get(key)
        if v:
            m = re.search(r"(\d{4})", str(v))
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


def _parse_vol_issue(text: str, allow_paren: bool) -> tuple[str, str]:
    """'제12권 제3호' / 'Vol.24 No.6' / '24(6)' / '제28호' → (권, 호)."""
    t = " ".join((text or "").split())
    m = re.search(r"제?\s*(\d{1,4})\s*권\s*제?\s*(\d{1,4})\s*호", t)
    if m:
        return m.group(1), m.group(2)
    m = re.search(r"Vol\.?\s*(\d{1,4})\s*,?\s*No\.?\s*(\d{1,4})", t, re.I)
    if m:
        return m.group(1), m.group(2)
    if allow_paren:  # 자유 텍스트에는 쓰지 않는다('43-67 (25 pages)' 오인 방지)
        m = re.search(r"\b(\d{1,4})\s*\(\s*(\d{1,4})\s*\)", t)
        if m:
            return m.group(1), m.group(2)
    vol = (re.search(r"제?\s*(\d{1,4})\s*권", t) or [None, ""])[1] if "권" in t else ""
    iss = (re.search(r"제?\s*(\d{1,4})\s*호", t) or [None, ""])[1] if "호" in t else ""
    return vol or "", iss or ""


def _volume_issue(rec: dict) -> tuple[str, str]:
    """권/호. bib 라벨을 우선하고, 없으면 제공처 텍스트에서 찾는다."""
    bib = rec.get("bib", {})
    for key in ("권호", "권/호", "권호사항", "Vol/No", "권차"):
        if bib.get(key):
            vi = _parse_vol_issue(str(bib[key]), allow_paren=True)
            if any(vi):
                return vi
    return _parse_vol_issue(rec.get("provider_bib_text", "") or "", allow_paren=False)


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
        n = re.sub(r"\s*\(.*?\)\s*", "", str(n)).strip()  # 괄호(영문명) 제거
        if n and n not in cleaned:
            cleaned.append(n)
    return cleaned


def _journal(rec: dict) -> str:
    """학술지명(수록지). 학위논문·단행본·보고서에는 해당 없음(발행기관을 쓴다)."""
    if _doc_type(rec) in ("thesis", "book", "report", "media"):
        return ""
    bib = rec.get("bib", {})
    for key in ("학술지명", "수록지명", "저널명", "학술지", "수록지", "발행처"):
        if bib.get(key):
            return str(bib[key]).strip()
    text = (rec.get("provider_bib_text", "") or "").strip()
    if text:
        first = _clean_journal(text.splitlines()[0])
        if first and len(first) <= 60:
            return first
    return ""


def _clean_journal(line: str) -> str:
    """학술지명 뒤에 붙은 권·호·발행일·페이지를 잘라낸다.

    제공처가 '부동산융복합연구 Vol.24 No.6 2022.12 101 - 120' 처럼 한 줄로
    주는 경우가 있어, 지명 이후의 서지 조각을 제거한다.
    """
    s = " ".join((line or "").split())
    cuts = [
        r"\s+Vol\.?\s*\d",           # Vol.24
        r"\s+제?\s*\d+\s*[권호]",     # 제28호 / 28권
        r"\s+\d{4}\s*[.\-/]\s*\d{1,2}",  # 2022.12
        r"\s+\d+\s*[-~]\s*\d+",       # 101 - 120
        r"\s+\(\s*\d+\s*pages?",      # (20 pages)
    ]
    for pat in cuts:
        m = re.search(pat, s, re.I)
        if m:
            s = s[: m.start()]
    return s.strip(" ,.·|")


def _institution(rec: dict) -> str:
    """수여기관(학위논문의 대학) 또는 발행기관(보고서/단행본의 출판사)."""
    bib = rec.get("bib", {})
    for key in ("수여기관", "학위수여기관", "발행기관", "발행처", "출판사", "대학", "발행사항"):
        v = bib.get(key)
        if v:
            s = " ".join(str(v).split())
            s = s.split(",")[0].strip()
            if s:
                return s
    m = re.search(r"([가-힣A-Za-z]{2,}(?:대학교|대학원|大學校))", _bib_blob(rec))
    return m.group(1) if m else ""


def _degree(rec: dict) -> str:
    """학위구분: '박사' | '석사' | ''."""
    blob = _bib_blob(rec)
    if "박사" in blob:
        return "박사"
    if "석사" in blob:
        return "석사"
    return ""


def _degree_label(rec: dict) -> str:
    d = _degree(rec)
    return f"{d}학위논문" if d else "학위논문"


FORMATS = ["bibtex", "ris", "csljson", "apa", "korean"]


def build(config: dict, fmt: str) -> str:
    """metadata.jsonl 전체를 fmt 문자열로 변환해 반환한다."""
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
        vol, iss = _volume_issue(r)
        out.append({
            "id": r.get("id", ""),
            "type": _doc_type(r),
            "title": r.get("title", ""),
            "authors": _authors(r),
            "year": _year(r),
            "journal": _journal(r),
            "volume": vol,
            "issue": iss,
            "institution": _institution(r),
            "degree": _degree(r),
            "pages": f"{sp}-{ep}" if sp and ep else "",
            "file": r.get("file", ""),
        })
    return out


def _sort_key(rec: dict):
    authors = _authors(rec)
    return ((authors[0] if authors else "힣"), _year(rec), rec.get("title", ""))


def _to_bibliography(recs: list[dict], style: str) -> str:
    """저자→연도 순으로 정렬된, 바로 붙여넣는 참고문헌 목록을 만든다."""
    lines = [_format_citation(r, style) for r in sorted(recs, key=_sort_key)]
    header = "% APA 근사 형식" if style == "apa" else "% 한국식(KCI) 근사 형식"
    return (header + " — 학회 규정에 맞게 확인/수정 필요\n\n"
            + "\n\n".join(lines) + ("\n" if lines else ""))


def _authors_apa(authors: list[str]) -> str:
    if len(authors) >= 2:
        return ", ".join(authors[:-1]) + ", & " + authors[-1]
    return authors[0] if authors else ""


def _vi_apa(vol: str, iss: str) -> str:
    """APA: 28(3) / 28 / (없음)."""
    if vol and iss:
        return f"{vol}({iss})"
    return vol or iss or ""


def _vi_korean(vol: str, iss: str) -> str:
    """한국식: 제28권 제3호 / 제28호."""
    if vol and iss:
        return f"제{vol}권 제{iss}호"
    if vol:
        return f"제{vol}권"
    if iss:
        return f"제{iss}호"
    return ""


def _format_citation(rec: dict, style: str) -> str:
    """자료유형에 맞는 참고문헌 한 줄을 만든다."""
    dtype = _doc_type(rec)
    authors = _authors(rec)
    year = _year(rec)
    title = (rec.get("title", "") or "").strip().rstrip(".")
    sp, ep = _pages(rec)
    pages = f"{sp}-{ep}" if sp and ep else ""
    vol, iss = _volume_issue(rec)
    inst = _institution(rec)

    apa = style == "apa"
    auth = _authors_apa(authors) if apa else "·".join(authors)
    head = f"{auth} ({year})." if auth else (f"({year})." if year else "")
    parts = [head] if head else []

    if dtype == "thesis":
        label = _degree_label(rec)
        if apa:
            # 백명기 (2009). 제목 [박사학위논문, 광운대학교].
            inner = f"{label}, {inst}" if inst else label
            parts.append(f"{title} [{inner}].")
        else:
            # 백명기 (2009). 「제목」. 광운대학교 박사학위논문.
            parts.append(f"「{title}」.")
            parts.append(f"{inst} {label}." if inst else f"{label}.")
        return " ".join(p for p in parts if p).strip()

    if dtype == "book":
        parts.append(f"{title}." if apa else f"「{title}」.")
        if inst:
            parts.append(f"{inst}.")
        return " ".join(p for p in parts if p).strip()

    if dtype == "report":
        if apa:
            parts.append(f"{title} [연구보고서].")
            if inst:
                parts.append(f"{inst}.")
        else:
            parts.append(f"「{title}」.")
            parts.append(f"{inst} 연구보고서." if inst else "연구보고서.")
        return " ".join(p for p in parts if p).strip()

    # article (기본)
    journal = _journal(rec)
    parts.append(f"{title}.")
    if apa:
        tail_bits = [b for b in (journal, _vi_apa(vol, iss), pages) if b]
        tail = ", ".join(tail_bits)
    else:
        jr = f"「{journal}」" if journal else ""
        tail_bits = [b for b in (jr, _vi_korean(vol, iss), pages) if b]
        tail = ", ".join(tail_bits)
    if tail:
        parts.append(tail + ".")
    return " ".join(p for p in parts if p).strip()


def _bib_escape(s: str) -> str:
    return (s or "").replace("{", "").replace("}", "").strip()


def _bib_key(rec: dict, authors: list[str], year: str) -> str:
    key = (authors[0] if authors else "ref") + (year or "") + "_" + (rec.get("id", "")[:6])
    return re.sub(r"[^0-9A-Za-z가-힣_]", "", key) or "ref"


def _to_bibtex(rec: dict) -> str:
    dtype = _doc_type(rec)
    authors = _authors(rec)
    year = _year(rec)
    sp, ep = _pages(rec)
    vol, iss = _volume_issue(rec)
    inst = _institution(rec)
    key = _bib_key(rec, authors, year)

    common = [
        ("title", _bib_escape(rec.get("title", ""))),
        ("author", " and ".join(authors)),
        ("year", year),
    ]
    if dtype == "thesis":
        entry = "mastersthesis" if _degree(rec) == "석사" else "phdthesis"
        fields = common + [
            ("school", _bib_escape(inst)),
            ("type", _degree_label(rec)),
        ]
    elif dtype == "book":
        entry = "book"
        fields = common + [("publisher", _bib_escape(inst))]
    elif dtype == "report":
        entry = "techreport"
        fields = common + [("institution", _bib_escape(inst))]
    else:
        entry = "article"
        fields = common + [
            ("journal", _bib_escape(_journal(rec))),
            ("volume", vol),
            ("number", iss),
            ("pages", f"{sp}--{ep}" if sp and ep else ""),
        ]
    fields.append(("url", rec.get("detail_url", "")))

    lines = [f"@{entry}{{{key},"]
    lines += [f"  {k} = {{{v}}}," for k, v in fields if v]
    lines.append("}")
    return "\n".join(lines)


_RIS_TYPES = {"thesis": "THES", "book": "BOOK", "report": "RPRT",
              "journal": "JOUR", "media": "GEN", "article": "JOUR"}


def _to_ris(rec: dict) -> str:
    dtype = _doc_type(rec)
    authors = _authors(rec)
    year = _year(rec)
    sp, ep = _pages(rec)
    vol, iss = _volume_issue(rec)
    inst = _institution(rec)

    lines = [f"TY  - {_RIS_TYPES.get(dtype, 'GEN')}", f"TI  - {rec.get('title','')}"]
    lines += [f"AU  - {a}" for a in authors]
    if year:
        lines.append(f"PY  - {year}")

    if dtype == "thesis":
        if inst:
            lines.append(f"PB  - {inst}")
        lines.append(f"M3  - {_degree_label(rec)}")
    elif dtype in ("book", "report"):
        if inst:
            lines.append(f"PB  - {inst}")
    else:
        if _journal(rec):
            lines.append(f"JO  - {_journal(rec)}")
        if vol:
            lines.append(f"VL  - {vol}")
        if iss:
            lines.append(f"IS  - {iss}")
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


_CSL_TYPES = {"thesis": "thesis", "book": "book", "report": "report",
              "journal": "article-journal", "media": "document",
              "article": "article-journal"}


def _to_csl(rec: dict) -> dict:
    dtype = _doc_type(rec)
    authors = _authors(rec)
    year = _year(rec)
    sp, ep = _pages(rec)
    vol, iss = _volume_issue(rec)
    inst = _institution(rec)

    item = {
        "type": _CSL_TYPES.get(dtype, "document"),
        "id": rec.get("id", ""),
        "title": rec.get("title", ""),
    }
    if authors:
        item["author"] = [{"family": a} for a in authors]
    if year:
        item["issued"] = {"date-parts": [[int(year)]]}

    if dtype == "thesis":
        if inst:
            item["publisher"] = inst
        item["genre"] = _degree_label(rec)
    elif dtype in ("book", "report"):
        if inst:
            item["publisher"] = inst
    else:
        if _journal(rec):
            item["container-title"] = _journal(rec)
        if vol:
            item["volume"] = vol
        if iss:
            item["issue"] = iss
        if sp and ep:
            item["page"] = f"{sp}-{ep}"

    if rec.get("detail_url"):
        item["URL"] = rec["detail_url"]
    if rec.get("abstract"):
        item["abstract"] = rec["abstract"]
    return item
