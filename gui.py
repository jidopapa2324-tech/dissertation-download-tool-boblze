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

import paths
from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
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

APP_DIR = paths.runtime_base()
COLLECTIONS = ["all", "thesis", "article"]


# --------------------------------------------------------------------------
# 순수 함수 (브라우저 불필요, 단위 테스트 가능) — cli.py 인자 조립
# --------------------------------------------------------------------------
def build_search_args(mode: str, value: str, collection: str, max_pages: int = 3,
                      doctoral: bool = False, fulltext: bool = False) -> list[str]:
    """검색 명령 인자. mode: 'author' | 'keyword'."""
    flag = "--author" if mode == "author" else "--keyword"
    args = ["search", flag, value, "--collection", collection, "--max-pages", str(max_pages)]
    if doctoral:
        args.append("--doctoral")
    if fulltext:
        args.append("--fulltext")
    return args


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
    return paths.load_config()


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
        # 단일 exe 배포본에는 git 소스가 없으므로 업데이트 버튼을 숨긴다.
        if not paths.is_frozen():
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
        self.chk_doctoral = QCheckBox("국내박사만")
        self.chk_fulltext = QCheckBox("원문있음만")
        search.addWidget(self.chk_doctoral)
        search.addWidget(self.chk_fulltext)
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
        self.btn_quotes = QPushButton("인용 노트")
        self.btn_quotes.clicked.connect(self.on_quotes)
        self.btn_dl_sel = QPushButton("선택 다운로드")
        self.btn_dl_sel.clicked.connect(self.on_download_selected)
        self.btn_dl_all = QPushButton("전체 다운로드")
        self.btn_dl_all.clicked.connect(self.on_download_all)
        self.btn_retry = QPushButton("실패만 재시도")
        self.btn_retry.clicked.connect(self.on_retry)
        self.cmb_fmt = QComboBox()
        self.cmb_fmt.addItems(["apa", "korean", "bibtex", "ris", "csljson"])
        self.btn_export = QPushButton("인용 내보내기")
        self.btn_export.clicked.connect(self.on_export)
        actions.addWidget(self.btn_dl_sel)
        actions.addWidget(self.btn_dl_all)
        actions.addWidget(self.btn_retry)
        actions.addWidget(self.btn_quotes)
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
        # frozen(단일 exe): exe가 자기 자신을 CLI 모드로 재실행.
        # dev: python cli.py <args>.
        if paths.is_frozen():
            proc.start(sys.executable, [*args])
        else:
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
        args = build_search_args(
            mode, value, self.cmb_col.currentText(),
            doctoral=self.chk_doctoral.isChecked(),
            fulltext=self.chk_fulltext.isChecked(),
        )
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

    def on_quotes(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "선택 없음", "목록에서 논문을 한 줄 선택하세요.")
            return
        paper_id = self.table.item(row, 2).text()
        title = self.table.item(row, 1).text()
        dlg = QuoteDialog(self.config, paper_id, title, self)
        dlg.exec()

    def on_export(self):
        fmt = self.cmb_fmt.currentText()
        ext = {"bibtex": "bib", "ris": "ris", "csljson": "json",
               "apa": "txt", "korean": "txt"}[fmt]
        name = "bibliography" if fmt in ("apa", "korean") else "citations"
        out = os.path.join("reference", f"{name}_{fmt}.{ext}")
        self.run_cli(build_export_args(fmt, out), f"내보내기 완료 → {out}")


class QuoteDialog(QDialog):
    """인용 노트: PDF 텍스트에서 문장 선택 → 저장(서지·페이지 첨부)·복사·밑줄."""

    def __init__(self, config: dict, paper_id: str, title: str, parent=None):
        super().__init__(parent)
        self.config = config
        self.paper_id = paper_id
        self.setWindowTitle(f"인용 노트 — {title}")
        self.resize(820, 620)

        from riss import quotes as q  # 지연 import (PyMuPDF)
        self.q = q

        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"[{title}]  문장을 드래그 선택한 뒤 '인용 저장'을 누르세요."))

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont("Consolas", 10))
        root.addWidget(self.text, 3)

        row = QHBoxLayout()
        self.btn_save = QPushButton("인용 저장")
        self.btn_save.clicked.connect(self._save_selection)
        self.cmb_style = QComboBox()
        self.cmb_style.addItems(["korean", "apa"])
        self.btn_copy = QPushButton("선택 인용 복사")
        self.btn_copy.clicked.connect(self._copy_selected_quote)
        self.btn_notes = QPushButton("노트 내보내기")
        self.btn_notes.clicked.connect(self._export_notes)
        row.addWidget(self.btn_save)
        row.addStretch(1)
        row.addWidget(QLabel("스타일"))
        row.addWidget(self.cmb_style)
        row.addWidget(self.btn_copy)
        row.addWidget(self.btn_notes)
        root.addLayout(row)

        root.addWidget(QLabel("저장된 인용 (더블클릭 = 복사)"))
        self.qlist = QListWidget()
        self.qlist.itemDoubleClicked.connect(lambda _it: self._copy_selected_quote())
        root.addWidget(self.qlist, 2)

        self.status = QLabel("")
        root.addWidget(self.status)

        self._load_pdf_text()
        self._refresh_quotes()

    def _load_pdf_text(self):
        rec = self.q.find_record(self.config, self.paper_id)
        if not rec or not rec.get("file") or not os.path.exists(rec["file"]):
            self.text.setPlainText("이 논문의 다운로드된 PDF를 찾지 못했습니다.\n"
                                   "먼저 해당 논문을 다운로드하세요.")
            self.btn_save.setEnabled(False)
            return
        try:
            pages = self.q.extract_pages(rec["file"])
        except Exception as e:
            self.text.setPlainText(f"PDF 텍스트 추출 실패: {e}")
            self.btn_save.setEnabled(False)
            return
        if not any(p.strip() for p in pages):
            self.text.setPlainText("이 PDF는 텍스트가 없습니다(스캔본으로 보임).\n"
                                   "인용문 추출/밑줄이 불가합니다.")
            self.btn_save.setEnabled(False)
            return
        blocks = []
        for i, t in enumerate(pages, 1):
            blocks.append(f"────── p.{i} ──────\n{t.strip()}")
        self.text.setPlainText("\n\n".join(blocks))

    def _selected_text(self) -> str:
        # Qt는 문단 구분에 U+2029를 쓰므로 공백으로 정리
        return " ".join(self.text.textCursor().selectedText().split())

    def _save_selection(self):
        sel = self._selected_text()
        if not sel:
            QMessageBox.information(self, "선택 없음", "PDF 텍스트에서 문장을 드래그하세요.")
            return
        res = self.q.add_quote(self.config, self.paper_id, sel)
        if not res.get("ok"):
            QMessageBox.warning(self, "저장 실패", res.get("error", ""))
            return
        page = res["quote"].get("page") or "?"
        mark = "밑줄 O" if res.get("annotated") else "밑줄 X(문장 못 찾음)"
        self.status.setText(f"저장됨: p.{page}, {mark}")
        self._refresh_quotes()

    def _refresh_quotes(self):
        self.qlist.clear()
        self._quotes = self.q.list_quotes(self.config, self.paper_id)
        style = self.cmb_style.currentText()
        for entry in self._quotes:
            self.qlist.addItem(self.q.format_quote(entry, style))

    def _copy_selected_quote(self):
        row = self.qlist.currentRow()
        if row < 0 or row >= len(self._quotes):
            QMessageBox.information(self, "선택 없음", "저장된 인용 목록에서 하나를 고르세요.")
            return
        style = self.cmb_style.currentText()
        text = self.q.format_quote(self._quotes[row], style)
        QApplication.clipboard().setText(text)
        self.status.setText("복사됨: " + text[:60])

    def _export_notes(self):
        style = self.cmb_style.currentText()
        text = self.q.export_notes(self.config, style)
        out = os.path.join("reference", f"notes_{style}.md")
        d = os.path.dirname(out)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        self.status.setText(f"노트 저장: {out}")
        QMessageBox.information(self, "내보내기", f"저장 완료:\n{out}")


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
