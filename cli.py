"""외부 AI가 호출하는 진입점. 명령 파싱과 JSON 직렬화만 담당한다.

사용법 (JSON 계약의 상세는 README.md 참고):
    python cli.py search --keyword "딥러닝" [--collection article] [--max-pages 3]
    python cli.py search --author "서진형(Seo Jin Hyeong)" --collection article
    python cli.py download --ids ID1 ID2 ID3

모든 출력은 stdout에 JSON 한 덩어리. 실패 시 exit code 1 +
{"ok": false, "error": "..."}.
"""

import argparse
import json
import os
import sys
import time

from riss import browser, download, metadata, search
from riss import inspect as inspect_mod


def load_config() -> dict:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_result(out: dict, config: dict, name: str) -> None:
    """명령 결과 JSON을 파일로도 저장한다 (사람이 열어 붙여넣기 쉽게)."""
    try:
        data_dir = os.path.dirname(config.get("metadata_file", "data/x")) or "."
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # 저장 실패는 무시 (부가 기능)


def cmd_search(args: argparse.Namespace, config: dict) -> dict:
    session = browser.connect(config)
    try:
        browser.ensure_logged_in(session.page, config)
        results = search.search(
            session.page,
            config,
            keyword=args.keyword,
            author=args.author,
            collection=args.collection or config["default_collection"],
            max_pages=args.max_pages,
        )
    finally:
        session.close()
    return {
        "ok": True,
        "command": "search",
        "keyword": args.keyword,
        "author": args.author,
        "collection": args.collection or config["default_collection"],
        "count": len(results),
        "results": results,
    }


def cmd_inspect(args: argparse.Namespace, config: dict) -> dict:
    session = browser.connect(config)
    try:
        browser.ensure_logged_in(session.page, config)
        return inspect_mod.inspect(
            session.page, config, args.target, follow=args.follow, meta=args.meta
        )
    finally:
        session.close()


def _make_reporter():
    """진행 상황을 stderr에 진행바+단계별 소요시간으로 출력하는 콜백을 만든다.

    각 단계는 '시작 시 바로' 출력하고(멈춤 여부 확인용), 그 단계가 끝나면
    걸린 시간(초)을 그 아래에 찍는다. 편(paper)마다 총 소요시간도 표시.
    """
    st = {"label": None, "t0": None, "paper_t": None}

    def _flush(now):
        if st["label"] is not None:
            print(f"        ⏱ {now - st['t0']:.1f}초", file=sys.stderr, flush=True)
            st["label"] = None

    def report(i, total, title, phase, data):
        now = time.perf_counter()
        short = title if len(title) <= 40 else title[:39] + "…"
        if phase == "retry_header":
            print(title, file=sys.stderr, flush=True)  # title에 안내문이 담겨옴
        elif phase == "retry_start":
            print(f"  ↻ 재시도: {short}", file=sys.stderr, flush=True)
        elif phase == "retry_done":
            if data.get("ok") and not data.get("skipped"):
                print(f"    ✔ 재시도 성공: {short}", file=sys.stderr, flush=True)
            elif data.get("skipped"):
                print(f"    - 이미 있음: {short}", file=sys.stderr, flush=True)
            else:
                print(f"    ✗ 재시도 실패: {short}", file=sys.stderr, flush=True)
        elif phase == "start":
            st["paper_t"] = now
            st["label"] = None
            print(f"\n[{i}/{total}] {short}", file=sys.stderr, flush=True)
        elif phase == "step":
            _flush(now)                       # 이전 단계 소요시간 출력
            st["label"] = data
            st["t0"] = now
            print(f"      - {data}", file=sys.stderr, flush=True)  # 새 단계 즉시 표시
        elif phase == "started":
            # 다운로드가 시작됨 → 여기서 진행바를 올리고 다음 논문으로 넘어간다.
            # 파일 저장(마무리)은 뒤이어 겹쳐서 처리되고 'saved'로 통지된다.
            _flush(now)
            total_s = now - st["paper_t"] if st["paper_t"] else 0.0
            pct = int(i / total * 100)
            filled = pct // 10
            bar = "█" * filled + "░" * (10 - filled)
            print(f"      => 다운로드 시작 ✓ (탐색 {total_s:.1f}초) → 다음 논문 진행",
                  file=sys.stderr, flush=True)
            print(f"      [{bar}] {pct}%  ({i}/{total})", file=sys.stderr, flush=True)
        elif phase == "saved":
            # 백그라운드 저장 마무리 결과 (진행바는 이미 올림)
            if data.get("ok"):
                print(f"      ✔ 저장 완료: {short}", file=sys.stderr, flush=True)
            else:
                print(f"      ✗ 저장 실패: {short} ({str(data.get('error',''))[:50]})",
                      file=sys.stderr, flush=True)
        elif phase == "done":
            _flush(now)                       # 마지막 단계 소요시간 출력
            total_s = now - st["paper_t"] if st["paper_t"] else 0.0
            if data.get("skipped"):
                mark = "건너뜀"
            elif data.get("ok"):
                mark = "완료 ✓"
            else:
                mark = "실패 ✗ (" + str(data.get("error", ""))[:50] + ")"
            pct = int(i / total * 100)
            filled = pct // 10
            bar = "█" * filled + "░" * (10 - filled)
            print(f"      => {mark}  (총 {total_s:.1f}초)", file=sys.stderr, flush=True)
            print(f"      [{bar}] {pct}%  ({i}/{total})", file=sys.stderr, flush=True)
    return report


def cmd_download(args: argparse.Namespace, config: dict) -> dict:
    if args.all:
        ids = [r["id"] for r in metadata.index_all(config) if r.get("id")]
    else:
        ids = args.ids or []
    if not ids:
        raise SystemExit("--ids 로 논문 ID를 주거나 --all 을 사용하세요.")
    report = _make_reporter() if args.progress else None
    session = browser.connect(config)
    try:
        browser.ensure_logged_in(session.page, config)
        results = download.download_many(session.page, ids, config, report=report)
    finally:
        session.close()
    if args.progress:
        ok_n = sum(1 for r in results if r["ok"] and not r.get("skipped"))
        skip_n = sum(1 for r in results if r.get("skipped"))
        fail_n = sum(1 for r in results if not r["ok"])
        print(
            f"\n완료: 성공 {ok_n} / 건너뜀 {skip_n} / 실패 {fail_n} (총 {len(results)})",
            file=sys.stderr,
            flush=True,
        )
    out = {
        "ok": all(r["ok"] for r in results),
        "command": "download",
        "results": results,
    }
    _save_result(out, config, "last_download.json")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="RISS 논문 다운로더")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="키워드/저자 검색, 결과 목록을 JSON으로 출력")
    p_search.add_argument("--keyword", help="키워드 검색어")
    p_search.add_argument("--author", help="저자명 (예: '서진형(Seo Jin Hyeong)')")
    p_search.add_argument(
        "--collection", help="all | thesis | article (기본: config.default_collection)"
    )
    p_search.add_argument("--max-pages", type=int, default=3)

    p_download = sub.add_parser("download", help="지정한 ID(control_no)의 원문 다운로드")
    p_download.add_argument("--ids", nargs="+", help="다운로드할 논문 ID들 (띄어쓰기 구분)")
    p_download.add_argument("--all", action="store_true", help="검색된(인덱스의) 전체 다운로드")
    p_download.add_argument(
        "--progress", action="store_true", help="진행바/단계를 화면(stderr)에 표시"
    )

    sub.add_parser("list", help="검색된 논문 목록을 사람이 읽기 쉽게 출력")

    p_inspect = sub.add_parser("inspect", help="[개발용] 상세페이지 구조 덤프 (셀렉터 확정용)")
    p_inspect.add_argument("target", help="control_no 또는 전체 detail_url")
    p_inspect.add_argument(
        "--follow",
        action="store_true",
        help="'원문보기'를 클릭해 뜨는 외부 제공처(팝업) 구조를 덤프",
    )
    p_inspect.add_argument(
        "--meta",
        action="store_true",
        help="상세페이지의 서지정보(라벨:값)를 덤프 (파일명/메타 확정용)",
    )

    args = parser.parse_args()

    try:
        config = load_config()
        if args.command == "list":
            # 사람이 읽는 목록 (JSON 아님)
            records = metadata.index_all(config)
            for i, r in enumerate(records, 1):
                print(f"{i:3}. {r.get('title', '')}  [{r.get('id', '')}]")
            print(f"\n총 {len(records)}건 (data/index.jsonl)")
            return 0
        if args.command == "search":
            if not args.keyword and not args.author:
                raise SystemExit("--keyword 또는 --author 중 하나가 필요합니다.")
            out = cmd_search(args, config)
        elif args.command == "inspect":
            out = cmd_inspect(args, config)
        else:
            out = cmd_download(args, config)
    except Exception as e:
        err = {"ok": False, "error": str(e)}
        try:
            _save_result(err, load_config(), "last_download.json")
        except Exception:
            pass
        print(json.dumps(err, ensure_ascii=False))
        return 1

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
