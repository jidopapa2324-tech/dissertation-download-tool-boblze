"""단일 진입점 — GUI/CLI 겸용 (PyInstaller onefile 대상).

- 인자 첫 번째가 서브커맨드(search/download/…)면 CLI 모드로 실행.
- 그 외(인자 없음 등)면 GUI를 띄운다.
단일 exe로 묶이면, GUI가 자기 자신(exe)을 CLI 모드로 재실행해 작업을 수행한다.

개발 실행:  python app.py            → GUI
            python app.py list       → CLI
"""

import sys

import paths


def _dispatch(argv: list[str]) -> str:
    """argv(프로그램명 제외)로 실행 모드를 결정한다: 'cli' | 'gui'."""
    if argv and argv[0] in paths.SUBCOMMANDS:
        return "cli"
    return "gui"


def main() -> int:
    paths.ensure_runtime()  # 작업 폴더 고정 + config.json 준비
    mode = _dispatch(sys.argv[1:])
    if mode == "cli":
        import cli
        return cli.main()
    import gui
    gui.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
