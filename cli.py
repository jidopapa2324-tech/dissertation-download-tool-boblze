"""외부 AI가 호출하는 진입점. 명령 파싱과 JSON 직렬화만 담당한다.

사용법 (JSON 계약의 상세는 README.md 참고):
    python cli.py search --keyword "딥러닝" [--max-pages 3]
    python cli.py download --ids ID1 ID2 ID3

모든 출력은 stdout에 JSON 한 덩어리. 실패 시 exit code 1 +
{"ok": false, "error": "..."}.
"""

import argparse
import json
import sys


def load_config() -> dict:
    """cli.py 옆의 config.json을 읽는다. TODO(opus): 구현"""
    raise NotImplementedError


def cmd_search(args: argparse.Namespace, config: dict) -> dict:
    """browser.connect → ensure_logged_in → search.search 를 엮어
    README의 search JSON 계약대로 dict를 만들어 반환한다.

    TODO(opus): 구현
    """
    raise NotImplementedError


def cmd_download(args: argparse.Namespace, config: dict) -> dict:
    """browser.connect → ensure_logged_in → download.download_many 를 엮어
    README의 download JSON 계약대로 dict를 만들어 반환한다.

    TODO(opus): 구현
    """
    raise NotImplementedError


def main() -> int:
    parser = argparse.ArgumentParser(description="RISS 박사학위논문 다운로더")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="키워드 검색, 결과 목록을 JSON으로 출력")
    p_search.add_argument("--keyword", required=True)
    p_search.add_argument("--max-pages", type=int, default=3)

    p_download = sub.add_parser("download", help="지정한 ID의 원문 다운로드")
    p_download.add_argument("--ids", nargs="+", required=True)

    args = parser.parse_args()

    try:
        config = load_config()
        if args.command == "search":
            out = cmd_search(args, config)
        else:
            out = cmd_download(args, config)
    except Exception as e:  # 모든 실패를 JSON 계약으로 변환
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
