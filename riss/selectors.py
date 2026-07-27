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

# RISS 좌측 필터(exQuery). 각 필터는 "<필드>:<값>◈" 조각이며 이어 붙여 조합한다.
# 실 URL에서 확인: (exQuery 조각, exQueryText 조각)
FILTER_DOCTORAL = ("mat_subtype_cd:T2◈", "학위유형 [국내박사]@@mat_subtype_cd:T2◈")
FILTER_FULLTEXT = ("fulltext_kind:1◈", "원문유무 [원문있음]@@fulltext_kind:1◈")

# 검색 결과에서 논문 고유 ID(control_no)를 뽑는 정규식
CONTROL_NO_PATTERN = r"control_no=([0-9a-zA-Z]+)"

# 학술지(저널) 자체 레코드의 자료유형(p_mat_type). 논문이 아니라 컨테이너
# 레코드라 원문 파일이 없다 → 다운로드 시 즉시 건너뛴다(타임아웃/재시도 낭비 방지).
P_MAT_TYPE_JOURNAL = "3a11008f85f7c51d"

# 상세 URL의 p_mat_type → 자료유형. 실 검색결과(index.jsonl) 분석으로 확인했다.
# 인용 서식이 자료유형마다 다르므로(학위논문은 대학·학위구분이 필요) 여기서 판별한다.
MAT_TYPES = {
    "1a0202e37d52c72d": "article",   # 국내학술논문
    "be54d9b8bc7cdb09": "thesis",    # 국내학위논문
    P_MAT_TYPE_JOURNAL: "journal",   # 학술지(컨테이너) — 원문 없음
    "d7345961987b50bf": "book",      # 단행본
    "6b4a196b69d9bee2": "report",    # 연구보고서
    "e21c2016a7c3498b": "article",   # 해외학술논문
    "695c7ada7e580906": "article",   # 학술발표/기타 논문(추정)
    "2db2effbc5804a39": "media",     # 강의·멀티미디어
}

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

# 팝업(외부 제공처)에서 실제 PDF '저장' 버튼 후보.
# 교보스콜라 확인 결과: '원문저장'이 PDF 저장, '원문보기'는 웹뷰어(다운로드 아님).
# onclick이 비어 JS로 바인딩돼 있으므로 텍스트로 클릭해 핸들러를 실행한다.
# 중복 배치(상단/플로팅)가 있어 '보이는' 요소를 클릭한다(download._find_first).
PROVIDER_DOWNLOAD_CANDIDATES = [
    # 교보스콜라
    "a:has-text('원문저장')",
    "button:has-text('원문저장')",
    # 공통/여러 제공처(DBpia·KISS·earticle 등)
    "a:has-text('PDF 다운로드')",
    "a:has-text('원문 다운로드')",
    "a:has-text('전체 원문')",
    "a:has-text('내려받기')",
    "a:has-text('다운로드')",
    "button:has-text('다운로드')",
    "button:has-text('내려받기')",
    "button:has-text('저장')",
    "a:has-text('PDF')",
    "button:has-text('PDF')",
    "a[href$='.pdf']",
    "a[href*='download']",
    "a[href*='fulltext']",
    "a[href*='pdf']",
]

# 서지정보 파싱 후보 (label 텍스트 → 값). 상세페이지의 정의목록(dl/dt/dd)
# 구조가 흔하므로 그 형태를 우선 파싱하고, 실패 시 아래 셀렉터 후보를 쓴다.
DETAIL_TITLE_CANDIDATES = ["h3.title", ".thesisInfo h3", "h3", "title"]
DETAIL_ABSTRACT_CANDIDATES = [".abstractTxt", "#soptionview .content", ".abstract"]

# 외부 제공처(교보스콜라 등) 페이지에서 서지정보가 담긴 영역 후보.
# 못 찾으면 download 로직이 body 전체 텍스트로 폴백하므로 정보는 유실되지 않는다.
# TODO(opus): 교보스콜라 실제 클래스 확인되면 앞쪽에 추가해 정확도 향상.
PROVIDER_INFO_CANDIDATES = [
    ".article_info",
    ".book_info",
    ".title_wrap",
    ".detail_info",
    "main",
]
