"""RISS 페이지 셀렉터/URL 상수 모음.

RISS 페이지 구조가 바뀌면 이 파일만 수정한다.
다른 모듈에서 셀렉터 문자열을 직접 쓰는 것 금지.

TODO(opus): 실제 RISS(libproxy 경유) 페이지를 열어 셀렉터를 채울 것.
아래 값들은 자리표시자이며 실제 페이지 확인 전에는 동작하지 않는다.
"""

# --- 검색 ---
SEARCH_INPUT = "#query"                # 메인 검색창 input
SEARCH_BUTTON = "TODO"                 # 검색 실행 버튼
TAB_THESIS = "TODO"                    # 검색 결과에서 '학위논문' 탭
FILTER_DOCTORAL = "TODO"               # 좌측 필터 '박사' 체크박스

# --- 검색 결과 목록 ---
RESULT_ITEM = "TODO"                   # 결과 리스트의 논문 1건 컨테이너
RESULT_TITLE_LINK = "TODO"             # 제목 링크 (href에서 논문 ID 추출)
RESULT_AUTHOR = "TODO"
RESULT_UNIVERSITY = "TODO"
RESULT_YEAR = "TODO"
RESULT_DEGREE = "TODO"                 # 석사/박사 구분 텍스트
NEXT_PAGE = "TODO"                     # 페이지네이션 다음 버튼

# --- 상세/다운로드 ---
DETAIL_DOWNLOAD_BUTTON = "TODO"        # 상세 페이지의 원문 다운로드 버튼
DETAIL_ABSTRACT = "TODO"               # 초록 영역 (메타데이터 축적용)

# --- URL 패턴 ---
# 논문 상세 URL에서 고유 ID를 뽑는 정규식. TODO(opus): 실제 URL 보고 확정.
DETAIL_URL_ID_PATTERN = r"TODO"
