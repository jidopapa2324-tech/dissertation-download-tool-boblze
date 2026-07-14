"""RISS 논문 다운로더 GUI (PySide6).

실제 작업은 하지 않는다 — 기존 cli.py를 QProcess로 호출하고, 그 출력을
로그 창에 실시간으로 보여줄 뿐이다. 상태(목록/실패수)는 data/*.json(l)을
읽어서 표시한다. 백엔드(cli.py, riss/*)는 건드리지 않는다.

실행:  python gui.py   (사전: pip install -r requirements-gui.txt)
"""

import json
import os
import re
import sys

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
COLLECTIONS = ["all", "thesis", "article"]


# --------------------------------------------------------------------------
# 순수 함수 (브라우저 불필요, 단위 테스트 가능) — cli.py 인자 조립
# --------------------------------------------------------------------------
def build_search_args(mode: str, value: str, collection: str, max_pages: int = 3) -> list[str]:
    """검색 명령 인자. mode: 'author' | 'keyword'."""
    flag = "--author" if mode == "author" else "--keyword"
    return ["search", flag, value, "--collection", collection, "--max-pages", str(max_pages)]


def build_download_args(ids: list[str] | None, *, all_: bool = False,
                        retry_failed: bool = False) -> list[str]:
    """다운로드 명령 인자. 항상 --progress 를 켠다."""
    args = ["download", "--progress"]
    if retry_failed:
        args.append("--retry-failed")
    elif all_:
        args.append("--all")
    else:
        args += ["--ids", *(ids or [])]
    return args


def build_export_args(fmt: str, out_path: str) -> list[str]:
    return ["export", "--format", fmt, "--out", out_path]


def load_config() -> dict:
    try:
        with open(os.path.join(APP_DIR, "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _read_jsonl(path: str) -> list[dict]:
    out = []
    if not os.path.exists(path):
        return out
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except Exception:
        pass
    return out


def load_index(config: dict) -> list[dict]:
    return _read_jsonl(os.path.join(APP_DIR, config.get("index_file", "data/index.jsonl")))


def failed_count(config: dict) -> int:
    path = os.path.join(APP_DIR, config.get("failed_file", "data/failed.json"))
    if not os.path.exists(path):
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return len(data) if isinstance(data, list) else 0
    except Exception:
        return 0


def find_chrome() -> str | None:
    """Windows 크롬 실행 경로 자동 감지 (없으면 None)."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def chrome_launch_args() -> list[str]:
    """실행.bat의 :chrome 과 동일한 인자."""
    return [
        "--remote-debugging-port=9222",
        r"--user-data-dir=C:\chrome-riss",
        "https://kupis.kw.ac.kr/",
    ]


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RISS 논문 다운로더")
        self.resize(920, 680)
        self.config = load_config()
        self.proc: QProcess | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # 1) 상단 바
        top = QHBoxLayout()
        self.btn_login = QPushButton("① 크롬 켜고 로그인")
        self.btn_login.clicked.connect(self.on_login)
        self.btn_update = QPushButton("⟳ 최신 코드 업데이트")
        self.btn_update.clicked.connect(self.on_update)
        top.addWidget(self.btn_login)
        top.addWidget(self.btn_update)
        top.addStretch(1)
        root.addLayout(top)

        # 2) 검색 패널
        search = QHBoxLayout()
        self.rb_author = QRadioButton("저자")
        self.rb_keyword = QRadioButton("키워드")
        self.rb_author.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.rb_author)
        grp.addButton(self.rb_keyword)
        self.ed_query = QLineEdit()
        self.ed_query.setPlaceholderText("예: 서진형(Seo Jin Hyeong)")
        self.ed_query.returnPressed.connect(self.on_search)
        self.cmb_col = QComboBox()
        self.cmb_col.addItems(COLLECTIONS)
        default_col = self.config.get("default_collection", "all")
        if default_col in COLLECTIONS:
            self.cmb_col.setCurrentText(default_col)
        self.btn_search = QPushButton("검색")
        self.btn_search.clicked.connect(self.on_search)
        search.addWidget(self.rb_author)
        search.addWidget(self.rb_keyword)
        search.addWidget(self.ed_query, 1)
        search.addWidget(QLabel("범위"))
        search.addWidget(self.cmb_col)
        search.addWidget(self.btn_search)
        root.addLayout(search)

        # 3) 결과 테이블
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["", "제목", "id"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 32)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table, 1)

        selrow = QHBoxLayout()
        self.btn_all = QPushButton("전체 선택")
        self.btn_all.clicked.connect(lambda: self._check_all(True))
        self.btn_none = QPushButton("선택 해제")
        self.btn_none.clicked.connect(lambda: self._check_all(False))
        selrow.addWidget(self.btn_all)
        selrow.addWidget(self.btn_none)
        selrow.addStretch(1)
        root.addLayout(selrow)

        # 4) 작업 버튼
        actions = QHBoxLayout()
        self.btn_dl_sel = QPushButton("선택 다운로드")
        self.btn_dl_sel.clicked.connect(self.on_download_selected)
        self.btn_dl_all = QPushButton("전체 다운로드")
        self.btn_dl_all.clicked.connect(self.on_download_all)
        self.btn_retry = QPushButton("실패만 재시도")
        self.btn_retry.clicked.connect(self.on_retry)
        self.cmb_fmt = QComboBox()
        self.cmb_fmt.addItems(["bibtex", "ris", "csljson"])
        self.btn_export = QPushButton("인용 내보내기")
        self.btn_export.clicked.connect(self.on_export)
        actions.addWidget(self.btn_dl_sel)
        actions.addWidget(self.btn_dl_all)
        actions.addWidget(self.btn_retry)
        actions.addStretch(1)
        actions.addWidget(self.cmb_fmt)
        actions.addWidget(self.btn_export)
        root.addLayout(actions)

        # 5) 진행바 + 로그
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 9))
        self.log.setMaximumBlockCount(5000)
        root.addWidget(self.log, 1)

        self.statusBar().showMessage("준비됨")

        self._action_buttons = [
            self.btn_search, self.btn_dl_sel, self.btn_dl_all,
            self.btn_retry, self.btn_export, self.btn_update,
        ]
        self._refresh_state()

    # ---- 상태 갱신 -------------------------------------------------------
    def _refresh_state(self):
        rows = load_index(self.config)
        self._fill_table(rows)
        n = failed_count(self.config)
        self.btn_retry.setText(f"실패만 재시도 ({n}건)")
        self.btn_retry.setEnabled(n > 0 and self.proc is None)

    def _fill_table(self, rows: list[dict]):
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Unchecked)
            self.table.setItem(i, 0, chk)
            self.table.setItem(i, 1, QTableWidgetItem(r.get("title", "")))
            self.table.setItem(i, 2, QTableWidgetItem(r.get("id", "")))

    def _check_all(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(state)

    def _selected_ids(self) -> list[str]:
        ids = []
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).checkState() == Qt.Checked:
                ids.append(self.table.item(i, 2).text())
        return ids

    # ---- 명령 실행 -------------------------------------------------------
    def _busy(self) -> bool:
        return self.proc is not None

    def _set_enabled(self, enabled: bool):
        for b in self._action_buttons:
            b.setEnabled(enabled)
        if enabled:
            self._refresh_state()  # 재시도 버튼 활성/카운트 재계산

    def run_cli(self, args: list[str], done_msg: str = "완료"):
        """cli.py <args> 를 QProcess로 실행하고 출력을 로그창에 흘린다."""
        if self._busy():
            QMessageBox.information(self, "실행 중", "다른 작업이 끝난 뒤 시도하세요.")
            return
        self._set_enabled(False)
        self.progress.setValue(0)
        self.log.appendPlainText(f"\n$ cli.py {' '.join(args)}\n")

        proc = QProcess(self)
        proc.setWorkingDirectory(APP_DIR)
        proc.readyReadStandardOutput.connect(lambda: self._read(proc, False))
        proc.readyReadStandardError.connect(lambda: self._read(proc, True))
        proc.finished.connect(lambda code, _st: self._on_finished(code, done_msg))
        self.proc = proc
        self.statusBar().showMessage(f"실행 중: {args[0]} …")
        proc.start(sys.executable, [os.path.join(APP_DIR, "cli.py"), *args])

    def _read(self, proc: QProcess, err: bool):
        raw = (proc.readAllStandardError() if err else proc.readAllStandardOutput())
        text = bytes(raw).decode("utf-8", errors="replace")
        if not text:
            return
        self.log.appendPlainText(text.rstrip("\n"))
        for m in re.finditer(r"(\d+)%", text):
            self.progress.setValue(min(100, int(m.group(1))))

    def _on_finished(self, code: int, done_msg: str):
        self.proc = None
        self.progress.setValue(100 if code == 0 else self.progress.value())
        self.statusBar().showMessage(f"{done_msg} (종료코드 {code})")
        self._set_enabled(True)

    # ---- 버튼 핸들러 -----------------------------------------------------
    def on_login(self):
        chrome = find_chrome()
        if not chrome:
            QMessageBox.warning(self, "크롬 없음",
                                "Chrome 실행 파일을 찾지 못했습니다.\n설치 경로를 확인하세요.")
            return
        QProcess.startDetached(chrome, chrome_launch_args())
        self.log.appendPlainText(
            "크롬을 켰습니다(포트 9222). 뜬 창에서 광운대 포털 로그인 →\n"
            "  대학원생 선택 → schosite/list/1 에서 RISS 접속 후, 이 창에서 검색하세요.")
        self.statusBar().showMessage("크롬 실행됨 — 로그인 후 검색하세요")

    def on_update(self):
        if self._busy():
            return
        self._set_enabled(False)
        self.log.appendPlainText("\n$ git pull\n")
        proc = QProcess(self)
        proc.setWorkingDirectory(APP_DIR)
        proc.readyReadStandardOutput.connect(lambda: self._read(proc, False))
        proc.readyReadStandardError.connect(lambda: self._read(proc, True))
        proc.finished.connect(lambda code, _st: self._on_finished(code, "업데이트 완료"))
        self.proc = proc
        proc.start("git", ["pull"])

    def on_search(self):
        value = self.ed_query.text().strip()
        if not value:
            QMessageBox.information(self, "입력 필요", "검색어를 입력하세요.")
            return
        mode = "author" if self.rb_author.isChecked() else "keyword"
        args = build_search_args(mode, value, self.cmb_col.currentText())
        self.run_cli(args, "검색 완료")

    def on_download_selected(self):
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(self, "선택 없음", "다운로드할 논문을 체크하세요.")
            return
        self.run_cli(build_download_args(ids), "다운로드 완료")

    def on_download_all(self):
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "목록 없음", "먼저 검색해서 목록을 채우세요.")
            return
        self.run_cli(build_download_args(None, all_=True), "다운로드 완료")

    def on_retry(self):
        self.run_cli(build_download_args(None, retry_failed=True), "재시도 완료")

    def on_export(self):
        fmt = self.cmb_fmt.currentText()
        ext = {"bibtex": "bib", "ris": "ris", "csljson": "json"}[fmt]
        out = os.path.join("reference", f"citations.{ext}")
        self.run_cli(build_export_args(fmt, out), f"내보내기 완료 → {out}")


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
