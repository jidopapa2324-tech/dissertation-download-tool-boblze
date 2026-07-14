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

from riss import browser, download, search
from riss import inspect as inspect_mod


def load_config() -> dict:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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
        return inspect_mod.inspect(session.page, config, args.target, follow=args.follow)
    finally:
        session.close()


def cmd_download(args: argparse.Namespace, config: dict) -> dict:
    session = browser.connect(config)
    try:
        browser.ensure_logged_in(session.page, config)
        results = download.download_many(session.page, args.ids, config)
    finally:
        session.close()
    return {
        "ok": all(r["ok"] for r in results),
        "command": "download",
        "results": results,
    }


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
    p_download.add_argument("--ids", nargs="+", required=True)

    p_inspect = sub.add_parser("inspect", help="[개발용] 상세페이지 구조 덤프 (셀렉터 확정용)")
    p_inspect.add_argument("target", help="control_no 또는 전체 detail_url")
    p_inspect.add_argument(
        "--follow",
        action="store_true",
        help="'원문보기'를 클릭해 뜨는 외부 제공처(팝업) 구조를 덤프",
    )

    args = parser.parse_args()

    try:
        config = load_config()
        if args.command == "search":
            if not args.keyword and not args.author:
                raise SystemExit("--keyword 또는 --author 중 하나가 필요합니다.")
            out = cmd_search(args, config)
        elif args.command == "inspect":
            out = cmd_inspect(args, config)
        else:
            out = cmd_download(args, config)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
