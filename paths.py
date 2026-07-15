"""실행 위치/설정 경로 처리 (개발 실행과 단일 exe 실행을 모두 지원).

- 개발(파이썬): 이 파일이 있는 저장소 폴더가 기준.
- 단일 exe(PyInstaller onefile): exe가 놓인 폴더가 기준. 사용자 데이터
  (config.json, data/, reference/)는 임시 추출 폴더(_MEIPASS)가 아니라
  exe 옆에 두어야 영구 보존된다.
"""

import os
import shutil
import sys

# 서브커맨드 목록 — app.py의 GUI/CLI 디스패치와 공유
SUBCOMMANDS = {"search", "download", "export", "list", "library", "inspect"}


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
    """작업 디렉터리를 runtime_base로 고정하고, 없으면 기본 config.json을 복사한다.

    이후 모든 상대경로(config.json, data/, reference/)가 exe 옆 기준으로 해석된다.
    """
    base = runtime_base()
    try:
        os.chdir(base)
    except Exception:
        pass
    cfg = os.path.join(base, "config.json")
    if not os.path.exists(cfg):
        src = os.path.join(bundled_base(), "config.json")
        if os.path.exists(src) and os.path.abspath(src) != os.path.abspath(cfg):
            try:
                shutil.copyfile(src, cfg)
            except Exception:
                pass


def config_path() -> str:
    return os.path.join(runtime_base(), "config.json")
