"""실행 위치/설정 경로 처리 (개발 실행과 단일 exe 실행을 모두 지원).

- 개발(파이썬): 이 파일이 있는 저장소 폴더가 기준.
- 단일 exe(PyInstaller onefile): exe가 놓인 폴더가 기준. 사용자 데이터
  (config.json, data/, reference/)는 임시 추출 폴더(_MEIPASS)가 아니라
  exe 옆에 두어야 영구 보존된다.
"""

import json
import os
import sys

# 서브커맨드 목록 — app.py의 GUI/CLI 디스패치와 공유
SUBCOMMANDS = {
    "search", "download", "export", "list", "library", "inspect",
    "quote", "quotes", "notes", "pdftext",
}

# 기본 설정 — 코드에 내장한다. config.json 파일을 만들지 않아도 동작하며,
# 사용자가 exe 옆에 config.json을 직접 두면 그 값으로 덮어쓴다(선택).
DEFAULT_CONFIG = {
    "base_url": "https://www-riss-kr.libproxy.kw.ac.kr",
    "cdp_url": "http://127.0.0.1:9222",
    "download_dir": "reference",
    "metadata_file": "data/metadata.jsonl",
    "index_file": "data/index.jsonl",
    "failed_file": "data/failed.json",
    "quotes_file": "data/quotes.jsonl",
    "annotated_dir": "reference/annotated",
    "diagnostics_dir": "data/diagnostics",
    "default_collection": "all",
    "delay_sec": 1,
    "timeout_sec": 20,
    "overlap_batch": 4,
    "max_retries": 2,
}


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def runtime_base() -> str:
    """사용자 데이터/설정이 놓이는 기준 폴더(쓰기 가능)."""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def bundled_base() -> str:
    """번들된 리소스(기본 config 등)가 있는 폴더. onefile이면 _MEIPASS."""
    return getattr(sys, "_MEIPASS", runtime_base())


def ensure_runtime() -> None:
    """작업 디렉터리를 runtime_base로 고정한다.

    config.json은 만들지 않는다(기본값은 코드에 내장). 이후 상대경로
    (data/, reference/)가 exe 옆 기준으로 해석된다.
    """
    try:
        os.chdir(runtime_base())
    except Exception:
        pass


def config_path() -> str:
    return os.path.join(runtime_base(), "config.json")


def load_config() -> dict:
    """내장 기본값을 반환하되, exe 옆에 config.json이 있으면 그 값으로 덮어쓴다."""
    cfg = dict(DEFAULT_CONFIG)
    path = config_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
        except Exception:
            pass
    return cfg
