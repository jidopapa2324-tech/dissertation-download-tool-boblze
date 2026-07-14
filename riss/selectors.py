"""RISS 페이지 셀렉터/URL 상수 모음.

RISS 페이지 구조가 바뀌면 이 파일만 수정한다.
다른 모듈에서 셀렉터/URL 문자열을 직접 쓰는 것 금지.

설계 원칙: 가능한 한 UI 클릭 대신 URL 직접 조립으로 이동하고,
검색 결과는 상세링크(DetailView.do) 앵커에서 control_no를 추출하는
'앵커 기반' 방식을 쓴다. 이러면 결과 목록의 세부 CSS 셀렉터에 거의
의존하지 않아 페이지 개편에 강하다.
"""

# =====================================================================
# 컬렉션(colName) 코드 — RISS 실 URL에서 확인/추정
# =====================================================================
COLLECTIONS = {
    "all": "all",          # 통합검색
    "thesis": "bib_t",     # 국내학위논문 (추정: bib_t)
    "article": "re_a_kor",  # 국내학술논문 (실 URL에서 확인)
}

# =====================================================================
# 검색 URL 템플릿 (실 RISS 프록시 URL 구조 기반)
# =====================================================================

# 키워드 검색: query=<키워드>
KEYWORD_SEARCH_URL = (
    "{base_url}/search/Search.do"
    "?query={query}"
    "&colName={col_name}&icate={col_name}"
    "&iStartCount={start_count}"
    "&pageScale=10&pageNumber={page_number}"
    "&isDetailSearch=N&searchGubun=true&strSort=RANK&order=%2FDESC&isTab=Y"
)

# 상세(필드) 검색: queryText=znCreator,<저자명>  → 저자로 검색
# field는 znCreator(저자) 등 RISS 상세검색 필드 코드.
FIELD_SEARCH_URL = (
    "{base_url}/search/Search.do"
    "?isDetailSearch=Y&isFDetailSearch=N&searchGubun=true"
    "&queryText={field}%2C{value}"
    "&colName={col_name}&icate={col_name}"
    "&iStartCount={start_count}"
    "&pageScale=10&pageNumber={page_number}"
    "&strSort=RANK&order=%2FDESC&fsearchMethod=search&sflag=1&isTab=Y"
)
FIELD_CREATOR = "znCreator"  # 저자 검색 필드 코드

# 검색 결과에서 논문 고유 ID(control_no)를 뽑는 정규식
CONTROL_NO_PATTERN = r"control_no=([0-9a-zA-Z]+)"

# 검색 결과 페이지에서 상세페이지로 가는 앵커. 이 앵커의 href에
# 완전한 DetailView URL(p_mat_type + control_no 포함)이 들어있어,
# 다운로드 때 URL을 재조립할 필요 없이 그대로 재사용한다.
RESULT_DETAIL_LINK = "a[href*='DetailView.do']"

# =====================================================================
# 상세 페이지 셀렉터 (메타데이터/다운로드)
#   실제 로그인된 상세 페이지 HTML을 보고 확정해야 함. 아래는 후보 목록이며
#   parse/download 로직이 순서대로 시도하고 없으면 건너뛴다(크래시 방지).
# =====================================================================

# '원문보기' 링크 후보. 실 페이지 확인 결과, 이 링크는 href가
# javascript:void(0)이고 onclick으로 ButtonSet.memberUrlDownload(...)를
# 호출해 '새 창(팝업)'을 띄운다 → 그 팝업이 외부 원문 제공처(교보스콜라 등).
# 따라서 이 링크를 클릭한 뒤 expect_popup 으로 새 창을 잡아야 한다.
FULLTEXT_LINK_CANDIDATES = [
    "a[onclick*='memberUrlDownload']",
    "a:has-text('원문보기')",
]

# 팝업(외부 제공처)에서 실제 PDF 다운로드 버튼 후보.
# TODO(opus): inspect --follow 로 교보스콜라 등 실제 팝업 구조를 확인해 확정.
PROVIDER_DOWNLOAD_CANDIDATES = [
    "a:has-text('PDF 다운로드')",
    "a:has-text('원문 다운로드')",
    "a:has-text('다운로드')",
    "button:has-text('다운로드')",
    "a[href$='.pdf']",
    "a[href*='download']",
]

# 서지정보 파싱 후보 (label 텍스트 → 값). 상세페이지의 정의목록(dl/dt/dd)
# 구조가 흔하므로 그 형태를 우선 파싱하고, 실패 시 아래 셀렉터 후보를 쓴다.
DETAIL_TITLE_CANDIDATES = ["h3.title", ".thesisInfo h3", "h3", "title"]
DETAIL_ABSTRACT_CANDIDATES = [".abstractTxt", "#soptionview .content", ".abstract"]
