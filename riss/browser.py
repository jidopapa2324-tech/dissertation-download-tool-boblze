"""브라우저 연결 관리.

로그인 로직은 없다. 사용자가 --remote-debugging-port=9222 로 띄운 Chrome에
CDP로 붙어, 이미 로그인된 세션을 그대로 사용한다.
"""

from playwright.sync_api import Page


def connect(config: dict) -> Page:
    """이미 실행 중인 Chrome에 CDP로 연결해 Page 객체를 반환한다.

    - config["cdp_url"] 로 connect_over_cdp
    - 기존 컨텍스트에서 config["base_url"] 도메인이 열린 탭이 있으면 그 탭을 사용,
      없으면 새 탭을 열어 base_url 로 이동
    - 연결 실패 시 RuntimeError("브라우저 연결 실패: Chrome을
      --remote-debugging-port=9222 로 실행했는지 확인") 를 던진다

    TODO(opus): 구현
    """
    raise NotImplementedError


def ensure_logged_in(page: Page, config: dict) -> None:
    """세션이 살아있는지(로그인 상태인지) 가볍게 확인한다.

    로그인 페이지로 리다이렉트되면 RuntimeError("로그인 만료: 브라우저에서
    다시 로그인 후 재시도") 를 던진다. 로그인을 시도하지는 않는다.

    TODO(opus): 구현 (로그인/로그아웃 상태를 구분할 수 있는 요소 확인)
    """
    raise NotImplementedError
