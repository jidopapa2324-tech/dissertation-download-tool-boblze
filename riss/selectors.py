"""RISS 페이지 셀렉터/URL 상수 모음.

RISS 페이지 구조가 바뀌면 이 파일만 수정한다.
다른 모듈에서 셀렉터/URL 문자열을 직접 쓰는 것 금지.

설계 원칙: 가능한 한 UI 클릭 대신 URL 직접 조립으로 이동한다.
(검색창 타이핑, 탭 클릭이 필요 없어져 셀렉터 의존도가 낮아진다)

TODO(opus): "TODO" 표시된 값을 실제 로그인된 페이지 HTML을 보고 채울 것.
"""

# =====================================================================
# URL 패턴 (실제 RISS 프록시 URL에서 확인된 구조)
# =====================================================================

# 검색 결과 페이지. UI 조작 없이 이 URL로 바로 이동한다.
#   {query}       : URL 인코딩된 검색 키워드
#   {start_count} : 결과 오프셋 (0, 10, 20, ... = (페이지-1) * page_scale)
#   {col_name}    : 검색 대상 컬렉션. TODO(opus): '학위논문' 탭 클릭 후
#                   URL에서 실제 값 확인 (국내학위논문은 "bib_t"로 추정)
SEARCH_URL_TEMPLATE = (
    "{base_url}/search/Search.do"
    "?query={query}"
    "&colName={col_name}"
    "&iStartCount={start_count}"
    "&pageScale=10"
    "&isDetailSearch=N&searchGubun=true&strSort=RANK&order=%2FDESC"
    "&icate=all&isTab=Y&pageNumber={page_number}"
)
COL_NAME_THESIS = "TODO"  # '학위논문' 컬렉션의 colName 값 (추정: bib_t)

# 논문 상세 페이지. control_no(논문 고유 ID)만 있으면 조립 가능.
# p_mat_type은 자료유형(학위논문)별 상수로 확인됨.
DETAIL_URL_TEMPLATE = (
    "{base_url}/search/detail/DetailView.do"
    "?p_mat_type={p_mat_type}"
    "&control_no={control_no}"
)
P_MAT_TYPE_THESIS = "1a0202e37d52c72d"  # 학위논문 자료유형 상수 (실 URL에서 확인)

# 검색 결과의 제목 링크 href에서 논문 ID(control_no)를 추출하는 정규식
DETAIL_URL_ID_PATTERN = r"control_no=([0-9a-f]+)"

# =====================================================================
# 검색 결과 목록 셀렉터
# =====================================================================
FILTER_DOCTORAL = "TODO"       # 좌측 필터 '박사' 체크박스 (URL 파라미터로
                               # 대체 가능하면 그 방식을 우선할 것)
RESULT_ITEM = "TODO"           # 결과 리스트의 논문 1건 컨테이너
RESULT_TITLE_LINK = "TODO"     # 제목 링크 (href에서 control_no 추출)
RESULT_AUTHOR = "TODO"
RESULT_UNIVERSITY = "TODO"
RESULT_YEAR = "TODO"
RESULT_DEGREE = "TODO"         # 석사/박사 구분 텍스트

# =====================================================================
# 상세 페이지 셀렉터
# =====================================================================
DETAIL_DOWNLOAD_BUTTON = "TODO"  # 원문 다운로드 버튼
DETAIL_ABSTRACT = "TODO"         # 초록 영역 (메타데이터 축적용)
