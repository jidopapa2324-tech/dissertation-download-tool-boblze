"""브라우저 연결 관리.

로그인 로직은 없다. 사용자가 --remote-debugging-port=9222 로 띄운 Chrome에
CDP로 붙어, 이미 로그인된 세션(쿠키가 든 기존 컨텍스트)을 그대로 사용한다.
"""

from dataclasses import dataclass
from urllib.parse import urlparse

from playwright.sync_api import Browser, Page, Playwright, sync_playwright


@dataclass
class Session:
    """열린 브라우저 연결 묶음. 작업이 끝나면 close()로 정리한다."""

    playwright: Playwright
    browser: Browser
    page: Page

    def close(self) -> None:
        # 사용자의 Chrome은 닫지 않는다. CDP 연결만 끊는다.
        try:
            self.playwright.stop()
        except Exception:
            pass


def connect(config: dict) -> Session:
    """실행 중인 Chrome에 CDP로 연결한다.

    - 기존 컨텍스트(로그인 쿠키 보유)에서 base_url 도메인이 열린 탭이 있으면
      그 탭을 재사용하고, 없으면 그 컨텍스트에 새 탭을 열어 base_url로 이동한다.
    - 새 컨텍스트를 만들면 로그인 쿠키가 없으므로 절대 만들지 않는다.
    """
    host = urlparse(config["base_url"]).netloc
    pw = sync_playwright().start()
    # localhost가 IPv6(::1)로 해석돼 연결이 거부되는 경우가 많아, 127.0.0.1로도 시도한다.
    raw = config["cdp_url"]
    candidates = [raw]
    if "localhost" in raw:
        candidates.append(raw.replace("localhost", "127.0.0.1"))
    browser = None
    last_err = None
    for url in candidates:
        try:
            browser = pw.chromium.connect_over_cdp(url)
            break
        except Exception as e:
            last_err = e
    if browser is None:
        pw.stop()
        raise RuntimeError(
            "브라우저 연결 실패: Chrome을 --remote-debugging-port=9222 로 "
            f"실행했는지, cdp_url({raw})이 맞는지 확인하세요. "
            f"(방화벽/포트 사용중일 수도 있음) ({last_err})"
        )

    contexts = browser.contexts
    if not contexts:
        pw.stop()
        raise RuntimeError(
            "브라우저에 열린 컨텍스트가 없습니다. RISS에 로그인된 탭이 "
            "있는 Chrome에 연결했는지 확인하세요."
        )

    # 이미 RISS 도메인이 열린 탭을 우선 재사용
    for ctx in contexts:
        for pg in ctx.pages:
            if host in (pg.url or ""):
                _configure(pg, config)
                return Session(pw, browser, pg)

    # 없으면 첫 컨텍스트(로그인 쿠키 보유)에 새 탭을 열어 이동
    ctx = contexts[0]
    page = ctx.new_page()
    _configure(page, config)
    page.goto(config["base_url"], wait_until="domcontentloaded")
    return Session(pw, browser, page)


def _configure(page: Page, config: dict) -> None:
    page.set_default_timeout(config["timeout_sec"] * 1000)


def ensure_logged_in(page: Page, config: dict) -> None:
    """세션이 살아있는지 가볍게 확인한다. 로그인을 시도하지는 않는다.

    로그인 페이지로 리다이렉트된 정황(URL에 'login')이 보이면 예외.
    """
    url = (page.url or "").lower()
    if "login" in url:
        raise RuntimeError(
            "로그인 만료로 보입니다: 브라우저에서 RISS(libproxy)에 다시 "
            "로그인한 뒤 재시도하세요."
        )
