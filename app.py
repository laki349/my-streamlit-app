import os
import json
import re
import difflib
from typing import Dict, Any, List, Tuple, Optional

import streamlit as st

# Optional (install if you want better extraction):
# pip install requests trafilatura pdfplumber
import requests

try:
    import trafilatura
except Exception:
    trafilatura = None

try:
    import pdfplumber
except Exception:
    pdfplumber = None


# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="RePurpose | 목적 기반 텍스트 변환",
    page_icon="🛠️",
    layout="wide"
)

# -----------------------------
# Global CSS (iPhone-like, minimal, app-like)
# -----------------------------
st.markdown(
    """
<style>
:root{
  --bg: #F5F6FA;
  --panel: rgba(255,255,255,.85);
  --panel-strong: #FFFFFF;
  --ink: #0B1020;
  --muted: #5B647A;
  --line: rgba(15, 23, 42, .10);

  --brandA: #6A5CFF;
  --brandB: #9B8CFF;
  --brandSoft: rgba(106,92,255,.12);

  --radius-xl: 22px;
  --radius-lg: 18px;
  --radius-md: 14px;

  --shadow: 0 14px 40px rgba(16, 24, 40, 0.10);
  --shadow-sm: 0 10px 24px rgba(16, 24, 40, 0.08);
}

html, body, [data-testid="stAppViewContainer"]{
  background: radial-gradient(1100px 600px at 20% 0%, rgba(106,92,255,.16), transparent 55%),
              radial-gradient(900px 500px at 100% 10%, rgba(155,140,255,.14), transparent 60%),
              var(--bg) !important;
  color: var(--ink);
}

[data-testid="stHeader"]{
  background: transparent;
}

.block-container{
  padding-top: 20px;
  padding-bottom: 80px;
  max-width: 1280px;
}

.app-shell{
  display: block;
  margin: 0 auto;
}

.hero{
  background: linear-gradient(120deg, var(--brandA), var(--brandB));
  border-radius: var(--radius-xl);
  padding: 20px 22px;
  color: white;
  box-shadow: var(--shadow);
  margin-bottom: 16px;
}

.hero h1{
  font-size: 1.85rem;
  line-height: 1.2;
  margin: 0 0 6px 0;
}

.hero p{
  margin: 0;
  opacity: .92;
  font-size: .98rem;
}

.card{
  background: var(--panel);
  border: 1px solid rgba(255,255,255,.55);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  padding: 18px 18px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.card-title{
  font-weight: 800;
  font-size: 1.05rem;
  margin-bottom: 10px;
}

.pill{
  display:inline-flex;
  gap: 8px;
  align-items:center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,.20);
  border: 1px solid rgba(255,255,255,.35);
  font-size: .85rem;
}

hr{
  border: none;
  border-top: 1px solid var(--line);
  margin: 12px 0;
}

[data-testid="stSidebar"]{
  background: transparent;
}

[data-testid="stSidebar"] > div:first-child{
  background: rgba(255,255,255,.75);
  border: 1px solid rgba(255,255,255,.55);
  border-radius: var(--radius-xl);
  margin: 14px;
  padding: 14px 14px 18px;
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.stButton > button{
  background: linear-gradient(120deg, var(--brandA), var(--brandB));
  border: none;
  color: white;
  padding: 0.9rem 1.4rem;
  border-radius: 14px;
  font-weight: 800;
  box-shadow: 0 12px 26px rgba(106,92,255,.24);
}

.stButton > button:hover{
  filter: brightness(1.02);
}

.secondary-btn button{
  background: rgba(106,92,255,.10) !important;
  color: var(--brandA) !important;
  border: 1px solid rgba(106,92,255,.18) !important;
  box-shadow: none !important;
}

textarea{
  border-radius: 16px !important;
}

small, .muted{
  color: var(--muted);
}
</style>
""",
    unsafe_allow_html=True
)


# -----------------------------
# Constants (keep your existing)
# -----------------------------
PERSONA_OPTIONS = ["대학생", "취준생", "기획자", "마케팅/콘텐츠 담당자", "연구/학술", "기타(직접 입력)"]

MAJOR_PURPOSES = {
    "자소서/면접": ["자기소개", "지원동기", "직무역량"],
    "기획/비즈니스": ["기획서", "PRD", "제안서"],
    "학술/논문": ["서론", "결론"],
    "SNS/콘텐츠": ["캡션", "대본"]
}

TONE = ["격식체", "보통", "친근한", "단호한"]
STYLE = ["논리형", "스토리텔링", "데이터 중심"]
AUDIENCE = ["평가자", "대중", "교수"]

LENGTH_PRESET = {
    "짧게": 600,
    "보통": 1200,
    "길게": 2200
}

EDIT_INTENSITY = {
    "유지 위주": "원본 구조를 최대한 유지",
    "균형 조정": "논리와 흐름 재정렬",
    "적극 재구성": "구조 전면 재설계",
    "완전 리라이팅": "새 글처럼 재작성"
}

STRUCTURE_TEMPLATES = {
    "자기소개": "도입 → 정체성 → 경험 → 역량 → 목표",
    "지원동기": "문제 → 계기 → 행동 → 결과 → 이유",
    "직무역량": "상황 → 과제 → 해결 → 성과 → 재현성",
    "서론": "배경 → 한계 → 공백 → 목적",
    "결론": "요약 → 핵심 결과 → 해석 → 한계 → 시사점",
    "기획서": "문제 → 원인 → 해결 → 차별성 → 효과",
    "PRD": "문제 → 사용자 → 요구사항 → 해결안 → 지표",
    "제안서": "현황 → 문제 → 제안 → 실행 → 기대효과",
    "캡션": "후킹 → 공감 → 메시지 → 행동 유도",
    "대본": "오프닝 → 전개 → 포인트 → 마무리"
}

# -----------------------------
# Session State
# -----------------------------
if "reference_text" not in st.session_state:
    st.session_state.reference_text = ""
if "reference_meta" not in st.session_state:
    st.session_state.reference_meta = {}
if "last_raw" not in st.session_state:
    st.session_state.last_raw = ""
if "last_data" not in st.session_state:
    st.session_state.last_data = {}
if "last_rewritten" not in st.session_state:
    st.session_state.last_rewritten = ""


# -----------------------------
# Diff Helpers (keep)
# -----------------------------
def tokenize(text):
    return re.findall(r"\w+|[^\w\s]", text)

def render_diff_html(original, revised):
    a, b = tokenize(original), tokenize(revised)
    sm = difflib.SequenceMatcher(a=a, b=b)

    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append(" ".join(b[j1:j2]))
        elif tag == "insert":
            out.append(f"<span style='background:#FFF3A3'>{' '.join(b[j1:j2])}</span>")
        elif tag == "replace":
            out.append(f"<span style='background:#C8FACC'>{' '.join(b[j1:j2])}</span>")
        elif tag == "delete":
            out.append(
                f"<span style='background:#FDE2E2;color:#B91C1C;text-decoration:line-through'>"
                f"{' '.join(a[i1:i2])}</span>"
            )

    return f"<div style='line-height:1.85; font-size: 0.98rem'>{' '.join(out)}</div>"


# -----------------------------
# Insight Helpers (keep)
# -----------------------------
def derive_change_points(original, rewritten):
    points = []
    if not original.strip() or not rewritten.strip():
        return points

    length_delta = len(rewritten) - len(original)
    if abs(length_delta) >= 50:
        direction = "확장" if length_delta > 0 else "축약"
        points.append(f"분량이 약 {abs(length_delta)}자 {direction}되었습니다.")

    original_lines = [line.strip() for line in original.splitlines() if line.strip()]
    rewritten_lines = [line.strip() for line in rewritten.splitlines() if line.strip()]
    if len(rewritten_lines) != len(original_lines):
        points.append("문장 구성이 재배열되어 흐름이 다듬어졌습니다.")

    if not points:
        points.append("핵심 표현을 유지하면서 문장을 매끄럽게 다듬었습니다.")
    return points

def derive_repurpose_suggestions(major, minor):
    suggestions = []
    for item in MAJOR_PURPOSES.get(major, []):
        if item != minor:
            suggestions.append({"major_purpose": major, "minor_purpose": item})
    if len(suggestions) < 2:
        for other_major, minors in MAJOR_PURPOSES.items():
            if other_major == major:
                continue
            suggestions.append({"major_purpose": other_major, "minor_purpose": minors[0]})
            if len(suggestions) >= 3:
                break
    return suggestions


# -----------------------------
# Reference Extractors (NEW)
# -----------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_url_text(url: str, timeout: int = 12) -> Tuple[str, Dict[str, Any]]:
    """
    Tries to extract readable article text from a URL.
    - Works best on blog/articles/public pages.
    - May fail on paywalled/login pages (LinkedIn/DBpia often).
    """
    meta = {"url": url}
    try:
        r = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"
        })
        meta["status_code"] = r.status_code
        html = r.text
    except Exception as e:
        return "", {"url": url, "error": str(e)}

    # Best effort extraction
    if trafilatura:
        try:
            downloaded = trafilatura.extract(html, include_comments=False, include_tables=False)
            if downloaded and len(downloaded.strip()) > 200:
                return downloaded.strip(), meta
        except Exception as e:
            meta["trafilatura_error"] = str(e)

    # Fallback: crude strip
    text = re.sub(r"<script[\s\S]*?</script>", " ", html)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 2000:
        text = text[:20000]  # prevent huge
        meta["truncated"] = True
    return text, meta

def extract_pdf_text(file_bytes: bytes, max_pages: int = 12) -> str:
    if not pdfplumber:
        return "PDF 텍스트 추출을 위해 pdfplumber 설치가 필요합니다. (pip install pdfplumber)"
    out = []
    try:
        import io
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for i, page in enumerate(pdf.pages[:max_pages]):
                txt = page.extract_text() or ""
                if txt.strip():
                    out.append(txt.strip())
    except Exception as e:
        return f"PDF 추출 실패: {e}"
    return "\n\n".join(out).strip()


# -----------------------------
# Free Paper Search (NEW) - Semantic Scholar + arXiv
# -----------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def semantic_scholar_search(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """
    Semantic Scholar public endpoint (no key needed for basic use).
    Returns title/authors/year/abstract/url
    """
    if not query.strip():
        return []
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,year,authors,abstract,url,venue"
    }
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        out = []
        for p in data.get("data", []):
            out.append({
                "title": p.get("title", ""),
                "year": p.get("year"),
                "authors": ", ".join([a.get("name","") for a in (p.get("authors") or [])][:4]),
                "venue": p.get("venue",""),
                "abstract": p.get("abstract","") or "",
                "url": p.get("url","") or ""
            })
        return out
    except Exception:
        return []

@st.cache_data(show_spinner=False, ttl=3600)
def arxiv_search(query: str, limit: int = 6) -> List[Dict[str, Any]]:
    """
    Simple arXiv ATOM search without extra libs.
    """
    if not query.strip():
        return []
    api = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit
    }
    try:
        r = requests.get(api, params=params, timeout=12)
        r.raise_for_status()
        xml = r.text
    except Exception:
        return []

    # Minimal parsing
    entries = xml.split("<entry>")
    out = []
    for chunk in entries[1:]:
        def pick(tag):
            m = re.search(rf"<{tag}>([\s\S]*?)</{tag}>", chunk)
            return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
        title = pick("title")
        summary = pick("summary")
        link_m = re.search(r"<id>([\s\S]*?)</id>", chunk)
        url = link_m.group(1).strip() if link_m else ""
        out.append({
            "title": title,
            "abstract": summary,
            "url": url
        })
    return out


# -----------------------------
# AI Call (OpenAI v1+)
# -----------------------------
def call_openai(api_key, model, system_prompt, user_prompt, temperature):
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    resp = client.responses.create(
        model=model,
        temperature=temperature,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    return resp.output_text

def safe_json(text):
    try:
        return json.loads(text)
    except:
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group()) if m else {}


# -----------------------------
# Prompt Builder (UPGRADED: reference template)
# -----------------------------
def build_prompt(p: Dict[str, Any]):
    template = STRUCTURE_TEMPLATES.get(p["minor"], "논리적 구조로 구성")

    # reference instructions
    ref_text = (p.get("reference_text") or "").strip()
    ref_block = ""
    if ref_text:
        # keep it short to avoid token explosion
        ref_short = ref_text[:6000]
        ref_block = f"""
[참고 레퍼런스(템플릿)]
- 아래 레퍼런스의 '구조/문단 길이/문장 톤/헤딩 스타일/불릿 패턴'을 강하게 모사하되,
  원문 사실은 절대 왜곡하지 마라.
- 레퍼런스에서 반복되는 표현 패턴(예: "저는 ~했습니다", "이를 통해 ~를 달성")을 학습해 동일한 리듬으로 적용하라.
- 레퍼런스가 자소서라면: STAR/성과/수치/역할/배운점/지원직무 연결을 강화하라.
- 레퍼런스가 논문이라면: 배경-공백-목적-방법-결과-의의의 논리 연결을 강화하라.

[레퍼런스 본문]
{ref_short}
"""

    system = (
        "너는 전문 텍스트 편집자이자 목적 기반 리라이팅 전문가다. "
        "모든 사실 정보는 유지하되, 표현 방식만 목적에 맞는 언어 영역(register)으로 변환하라. "
        "학술, 비즈니스, SNS, 자기소개서 각각의 문체 차이를 엄격히 구분하여 적용하라. "
        "부적절한 관용구, 도메인 표현, 톤은 제거하지 말고 반드시 목적에 맞게 치환하라. "
        "문체의 다양성과 리듬은 유지하고 문장을 획일화하지 마라. "
        "추론 설명 없이 결과만 JSON으로 반환하라. "
        "원문에 없는 정보라도 목적에 어울리는 홍보/설명/맥락 요소를 자의적으로 추가할 수 있다. "
        "단, 사실관계(회사명/기간/수치/역할/성과)는 원문에서 벗어나지 마라. "
        "각 목적에는 고유한 언어 영역(register)이 존재한다. "
        "원본 표현을 삭제하지 말고, 목적에 맞는 표현으로 변환(치환)하라. "
        "학술 → 비학술 목적(자소서, 기획, 비즈니스)에서 "
        "'본 연구는', '본 논문에서는', '분석 결과', '통계적으로 유의미한' 같은 표현은 "
        "개인 경험 기반 성과 표현 또는 문제 해결 서술로 변환하라. "
        "SNS → 학술/논문에서는 감정 과잉 표현, 구어체, 과장 표현, 이모지, 유행어를 "
        "객관적 서술, 논리 연결, 근거 중심 문장으로 변환하라. "
        "일기/감정 서술 → 비즈니스/기획에서는 막연한 감정 중심 문장을 "
        "문제 정의 + 행동 + 결과 구조로 변환하라. "
        "의미는 유지하되 언어 영역만 이동시켜라. "
        "표현의 다양성은 유지하되 목적과 충돌하는 어조만 교정하라. "
        "각 문장을 목적 적합/부분 충돌/완전 충돌로 분류해 "
        "유지 또는 고급화/치환/구조 재서술로 처리하라. "
        "결과물에는 목적 언어 영역만 존재하도록 정제하라. "
        "반드시 선택된 목적에 대응하는 구조 템플릿을 사용해 글을 재구성하라. "
        "[논문 템플릿] 배경 -> 문제 -> 연구 공백 -> 목적 -> 시사점 "
        "[기획서 템플릿] 문제 -> 원인 -> 해결 -> 차별성 -> 효과 "
        "[자소서 템플릿] 상황 -> 행동 -> 역량 -> 결과 -> 연결 "
        "[SNS 템플릿] 후킹 -> 공감 -> 메시지 -> 행동 유도 "
    )

    user = f"""
{ref_block}

[원본]
{p["text"]}

[목적]
{p["major"]} → {p["minor"]}

[구조 템플릿]
{template}

[편집 조건]
편집 강도: {EDIT_INTENSITY[p["edit"]]}
톤: {p["tone"]}, 스타일: {p["style"]}, 독자: {p["audience"]}
분량: {p["length"]}자 근처 (±15%)

[출력 JSON 스키마]
{{
 "rewritten_text": "",
 "change_points": [],
 "highlight_reasons": [],
 "detected_original_traits": [],
 "suggested_repurposes": []
}}
"""
    return system, user


# -----------------------------
# Sidebar (settings + reference import)
# -----------------------------
with st.sidebar:
    st.markdown("### ⚙️ 설정")

    api_key = st.text_input("API Key", type="password")
    model = st.selectbox("모델", ["gpt-4o-mini", "gpt-4.1-mini"])
    persona = st.selectbox("특성", PERSONA_OPTIONS)

    st.markdown("---")
    st.markdown("### 🧩 목적 설정")
    major = st.selectbox("대목적", list(MAJOR_PURPOSES.keys()))
    minor = st.selectbox("소목적", MAJOR_PURPOSES[major])
    tone = st.selectbox("톤", TONE)
    style = st.selectbox("스타일", STYLE)
    audience = st.selectbox("독자", AUDIENCE)
    length_key = st.select_slider("분량", list(LENGTH_PRESET.keys()))
    edit_level = st.select_slider("편집 강도", list(EDIT_INTENSITY.keys()))
    temperature = st.slider("창의성", 0.0, 1.0, 0.5)

    st.markdown("---")
    st.markdown("### 📚 레퍼런스(템플릿) 가져오기")

    ref_mode = st.radio(
        "가져오기 방식",
        ["사용자 링크 붙여넣기(LinkedIn/DBpia/블로그 등)", "논문 검색(무료 API)", "PDF 업로드", "직접 붙여넣기"],
        index=0
    )

    if ref_mode == "사용자 링크 붙여넣기(LinkedIn/DBpia/블로그 등)":
        ref_url = st.text_input("레퍼런스 URL", placeholder="예: 공개된 합격 자소서 글, 공개 논문 페이지 URL")
        colA, colB = st.columns(2)
        with colA:
            load_ref = st.button("URL 가져오기")
        with colB:
            clear_ref = st.button("레퍼런스 비우기", key="clear_ref_1")

        if load_ref and ref_url.strip():
            with st.spinner("레퍼런스 추출 중..."):
                txt, meta = fetch_url_text(ref_url.strip())
            if txt.strip():
                st.session_state.reference_text = txt
                st.session_state.reference_meta = meta
                st.success("레퍼런스를 불러왔습니다.")
            else:
                st.warning("본문을 추출하지 못했습니다. (로그인/유료/차단 페이지일 수 있음) PDF 업로드 또는 직접 붙여넣기를 권장합니다.")
        if clear_ref:
            st.session_state.reference_text = ""
            st.session_state.reference_meta = {}
            st.success("레퍼런스를 비웠습니다.")

    elif ref_mode == "논문 검색(무료 API)":
        paper_query = st.text_input("논문 키워드", placeholder="예: reinforcement learning for recommendation")
        src = st.selectbox("검색 소스", ["Semantic Scholar", "arXiv"])
        search_btn = st.button("검색")
        clear_ref = st.button("레퍼런스 비우기", key="clear_ref_2")

        if search_btn and paper_query.strip():
            with st.spinner("검색 중..."):
                results = semantic_scholar_search(paper_query) if src == "Semantic Scholar" else arxiv_search(paper_query)
            if not results:
                st.warning("검색 결과가 없습니다. 키워드를 바꿔보세요.")
            else:
                pick = st.selectbox("선택", list(range(len(results))), format_func=lambda i: results[i].get("title","(no title)")[:80])
                chosen = results[pick]
                # Use abstract as template; URL optional
                ref_txt = (chosen.get("abstract") or "").strip()
                if not ref_txt:
                    ref_txt = f"제목: {chosen.get('title','')}\n\n(초록을 제공하지 않는 결과입니다. URL에서 직접 추출하거나 PDF 업로드를 사용하세요.)"
                st.session_state.reference_text = ref_txt
                st.session_state.reference_meta = {"source": src, **chosen}
                st.success("선택한 논문(초록)을 레퍼런스로 설정했습니다.")

        if clear_ref:
            st.session_state.reference_text = ""
            st.session_state.reference_meta = {}
            st.success("레퍼런스를 비웠습니다.")

    elif ref_mode == "PDF 업로드":
        pdf_file = st.file_uploader("PDF 업로드", type=["pdf"])
        colA, colB = st.columns(2)
        with colA:
            load_pdf = st.button("PDF 텍스트 추출")
        with colB:
            clear_ref = st.button("레퍼런스 비우기", key="clear_ref_3")

        if load_pdf and pdf_file is not None:
            with st.spinner("PDF 텍스트 추출 중..."):
                txt = extract_pdf_text(pdf_file.read())
            if txt.strip():
                st.session_state.reference_text = txt
                st.session_state.reference_meta = {"source": "pdf", "name": pdf_file.name}
                st.success("PDF 텍스트를 레퍼런스로 설정했습니다.")
            else:
                st.warning("PDF 텍스트 추출에 실패했습니다.")
        if clear_ref:
            st.session_state.reference_text = ""
            st.session_state.reference_meta = {}
            st.success("레퍼런스를 비웠습니다.")

    else:  # 직접 붙여넣기
        ref_paste = st.text_area("레퍼런스 텍스트", height=160, placeholder="합격 자소서/논문 초록/서론 일부 등을 붙여넣기")
        colA, colB = st.columns(2)
        with colA:
            apply_ref = st.button("레퍼런스로 설정")
        with colB:
            clear_ref = st.button("레퍼런스 비우기", key="clear_ref_4")
        if apply_ref:
            st.session_state.reference_text = ref_paste or ""
            st.session_state.reference_meta = {"source": "pasted"}
            st.success("레퍼런스를 설정했습니다.")
        if clear_ref:
            st.session_state.reference_text = ""
            st.session_state.reference_meta = {}
            st.success("레퍼런스를 비웠습니다.")

    if st.session_state.reference_text.strip():
        st.markdown("---")
        st.markdown("### ✅ 현재 레퍼런스 상태")
        meta = st.session_state.reference_meta or {}
        st.write("• 길이:", len(st.session_state.reference_text), "chars")
        if meta.get("url"):
            st.write("• URL:", meta["url"])
        if meta.get("title"):
            st.write("• 제목:", meta["title"])


# -----------------------------
# Main UI
# -----------------------------
st.markdown("<div class='app-shell'>", unsafe_allow_html=True)
st.markdown(
    """
<div class="hero">
  <div class="pill">🛠️ RePurpose</div>
  <h1>목적 기반 텍스트 리라이팅 워크스페이스</h1>
  <p>원문을 붙여넣고, 레퍼런스(합격 자소서/논문) 템플릿을 적용해 같은 결로 다시 씁니다.</p>
</div>
""",
    unsafe_allow_html=True
)

# Two-pane layout: Left (Reference + Original), Right (Output)
left, right = st.columns([1.05, 1.15], gap="large")

with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🧾 원본 텍스트</div>', unsafe_allow_html=True)
    original_text = st.text_area("원본 텍스트", height=280, key="original_text")
    st.markdown("<hr/>", unsafe_allow_html=True)

    st.markdown('<div class="card-title">📌 레퍼런스(템플릿) 미리보기</div>', unsafe_allow_html=True)
    if st.session_state.reference_text.strip():
        st.caption("이 레퍼런스의 구조/톤/리듬을 모사해 리라이팅합니다.")
        st.text_area("Reference", st.session_state.reference_text[:7000], height=240, key="ref_preview")
    else:
        st.caption("사이드바에서 레퍼런스를 설정하면 여기에서 확인할 수 있어요.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    run = st.button("변환 실행")

with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">✅ 변환 결과</div>', unsafe_allow_html=True)

    if run:
        if not api_key.strip():
            st.error("API Key를 입력해줘.")
        elif not original_text.strip():
            st.error("원본 텍스트를 입력해줘.")
        else:
            payload = {
                "text": original_text,
                "major": major,
                "minor": minor,
                "tone": tone,
                "style": style,
                "audience": audience,
                "length": LENGTH_PRESET[length_key],
                "edit": edit_level,
                "reference_text": st.session_state.reference_text
            }
            system, user = build_prompt(payload)

            with st.spinner("변환 중..."):
                raw = call_openai(api_key, model, system, user, temperature)

            data = safe_json(raw)
            rewritten = data.get("rewritten_text", "")

            st.session_state.last_raw = raw
            st.session_state.last_data = data
            st.session_state.last_rewritten = rewritten

    # Render if available (either from this run or previous run)
    data = st.session_state.last_data or {}
    rewritten = st.session_state.last_rewritten or ""

    if rewritten.strip() and original_text.strip():
        # Highlighted diff
        st.markdown("**하이라이트(변경점 표시)**")
        st.markdown(render_diff_html(original_text, rewritten), unsafe_allow_html=True)

        st.markdown("<hr/>", unsafe_allow_html=True)

        # reasons
        highlight_reasons = data.get("highlight_reasons") or data.get("change_points", [])
        st.markdown("**하이라이트 이유**")
        if highlight_reasons:
            for reason in highlight_reasons:
                st.write("-", reason)
        else:
            st.caption("표시할 이유가 없습니다.")

        st.markdown("<hr/>", unsafe_allow_html=True)

        # change points
        st.markdown("**🔍 변경 포인트**")
        change_points = data.get("change_points") or derive_change_points(original_text, rewritten)
        for c in change_points:
            if isinstance(c, dict):
                st.markdown(
                    f"**원문:** {c.get('original','')}\n\n"
                    f"➡️ **변경:** {c.get('rewritten','')}"
                )
            else:
                st.write("•", c)

        st.markdown("<hr/>", unsafe_allow_html=True)

        # Repurpose suggestions + Score + Downloads
        col1, col2 = st.columns([1, 1], gap="large")

        with col1:
            st.markdown("**💡 재활용 추천**")
            suggested = data.get("suggested_repurposes") or derive_repurpose_suggestions(major, minor)
            if suggested:
                for r in suggested:
                    if isinstance(r, dict):
                        st.write(f"{r.get('major_purpose','기타')} → {r.get('minor_purpose','기타')}")
                    else:
                        st.write(r)
            else:
                st.caption("추천 항목이 없습니다.")

        with col2:
            st.markdown("**📈 품질 점수**")
            score = min(95, 60 + len(rewritten)//200)
            st.progress(score/100)
            st.write(f"{score}/100")

        st.markdown("<hr/>", unsafe_allow_html=True)

        st.markdown("**⬇️ 다운로드**")
        d1, d2 = st.columns(2)
        with d1:
            st.download_button("TXT 다운로드", rewritten, file_name="result.txt")
        with d2:
            st.download_button("MD 다운로드", rewritten, file_name="result.md")

    else:
        st.caption("변환 실행 후 결과가 표시됩니다.")

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
# ============================================================
# (2/2) Template Engine + Reference Library + Company/Role + A/B Compare
# 이 아래를 (1/2) 코드 맨 아래에 그대로 추가
# ============================================================

# -----------------------------
# More Session State
# -----------------------------
if "reference_library" not in st.session_state:
    # each item: {"name": str, "text": str, "meta": dict, "template": dict}
    st.session_state.reference_library = []
if "reference_template" not in st.session_state:
    st.session_state.reference_template = {}
if "company_target" not in st.session_state:
    st.session_state.company_target = ""
if "role_target" not in st.session_state:
    st.session_state.role_target = ""
if "ab_variant" not in st.session_state:
    st.session_state.ab_variant = {"A": "", "B": ""}


# -----------------------------
# Template Extraction Helpers (RULE + LLM optional)
# -----------------------------
def simple_structure_guess(text: str) -> Dict[str, Any]:
    """
    Rule-based structure guesser.
    Produces a lightweight template that can be used to enforce headings & paragraph roles.
    """
    t = (text or "").strip()
    if not t:
        return {"type": "unknown", "sections": []}

    # Try detect headings like "1) 2) / (1) (2) / ■ / - / ###"
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    headings = []
    for ln in lines:
        if re.match(r"^(#{1,4}\s+)", ln) or re.match(r"^(\d+[\.\)]\s+)", ln) or re.match(r"^(\(\d+\)\s+)", ln):
            headings.append(ln)

    # If no headings, split by blank lines into paragraphs
    paras = re.split(r"\n\s*\n", t)
    paras = [p.strip() for p in paras if p.strip()]

    # Heuristic: if looks like self-intro (자소서) => STAR-ish
    # if looks like paper abstract => Background/Gap/Method/Result/Implication
    lower = t.lower()
    is_paperish = any(k in lower for k in ["abstract", "introduction", "method", "results", "conclusion", "본 연구", "본 논문", "연구 목적"])
    is_resumeish = any(k in t for k in ["지원동기", "직무", "역량", "경험", "성과", "프로젝트", "팀", "협업"])

    if headings:
        sections = [{"heading": h, "slot": f"sec_{i+1}", "guidance": ""} for i, h in enumerate(headings[:8])]
        return {
            "type": "paper" if is_paperish else ("resume" if is_resumeish else "generic"),
            "sections": sections,
            "style_rules": {
                "heading_style": "use_detected_headings",
                "paragraph_count_hint": min(len(paras), 8),
                "tone_hint": "match_reference"
            }
        }

    # No explicit headings: generate canonical sections
    if is_paperish:
        return {
            "type": "paper",
            "sections": [
                {"heading": "배경", "slot": "background", "guidance": "주제의 맥락과 중요성"},
                {"heading": "문제/한계", "slot": "problem", "guidance": "기존 접근의 한계"},
                {"heading": "연구 공백", "slot": "gap", "guidance": "왜 아직 해결되지 않았는지"},
                {"heading": "목적/기여", "slot": "purpose", "guidance": "무엇을 제안/검증하는지"},
                {"heading": "시사점", "slot": "implication", "guidance": "이 연구가 주는 의미"},
            ],
            "style_rules": {"tone_hint": "academic", "paragraph_count_hint": 5, "format": "headed_paragraphs"}
        }

    if is_resumeish:
        return {
            "type": "resume",
            "sections": [
                {"heading": "상황", "slot": "situation", "guidance": "문제/맥락 요약"},
                {"heading": "행동", "slot": "action", "guidance": "내가 한 일(역할/방법)"},
                {"heading": "성과", "slot": "result", "guidance": "수치/결과/임팩트"},
                {"heading": "배운 점", "slot": "learning", "guidance": "인사이트/재현 가능한 원리"},
                {"heading": "직무 연결", "slot": "fit", "guidance": "지원 직무/회사에 어떻게 기여"},
            ],
            "style_rules": {"tone_hint": "professional", "paragraph_count_hint": 5, "format": "headed_paragraphs"}
        }

    # Generic
    return {
        "type": "generic",
        "sections": [
            {"heading": "도입", "slot": "intro", "guidance": "핵심 메시지"},
            {"heading": "핵심 내용", "slot": "body", "guidance": "논리 전개"},
            {"heading": "마무리", "slot": "close", "guidance": "요약 + 다음 행동"},
        ],
        "style_rules": {"tone_hint": "match_reference", "paragraph_count_hint": 3, "format": "headed_paragraphs"}
    }


def build_template_prompt(reference_text: str) -> Tuple[str, str]:
    """
    LLM-based template extractor: returns a JSON template for structural imitation.
    """
    system = (
        "너는 글 구조 분석가다. 입력된 레퍼런스 텍스트의 구조를 '템플릿(JSON)'으로 추출하라. "
        "헤딩/문단 역할/불릿 패턴/문장 리듬/톤 규칙을 간결하게 정의한다. "
        "반드시 JSON만 출력한다."
    )

    user = f"""
[레퍼런스 텍스트]
{(reference_text or '')[:8000]}

[출력 JSON 스키마]
{{
  "type": "resume|paper|generic",
  "sections": [
    {{
      "heading": "섹션 제목(없으면 생성)",
      "slot": "background|problem|... 등 간단한 영문키",
      "guidance": "이 섹션에서 반드시 포함할 요소"
    }}
  ],
  "style_rules": {{
    "heading_style": "### heading / numbering / none",
    "bullet_style": "dash / dot / none",
    "sentence_rhythm": "짧게/보통/길게 + 예시",
    "tone_hint": "academic/professional/friendly 등",
    "signature_patterns": ["반복되는 표현 패턴 2~5개"]
  }}
}}
"""
    return system, user


def extract_template_with_llm(api_key: str, model: str, reference_text: str) -> Dict[str, Any]:
    """
    Try LLM template extraction; fallback to rule-based.
    """
    if not reference_text.strip():
        return {"type": "unknown", "sections": []}

    # If no API key, fallback rule based
    if not api_key.strip():
        return simple_structure_guess(reference_text)

    try:
        system, user = build_template_prompt(reference_text)
        raw = call_openai(api_key, model, system, user, temperature=0.2)
        tpl = safe_json(raw)
        if isinstance(tpl, dict) and tpl.get("sections"):
            return tpl
    except Exception:
        pass

    return simple_structure_guess(reference_text)


def render_template_preview(tpl: Dict[str, Any]) -> str:
    if not tpl:
        return "(템플릿 없음)"
    lines = [f"type: {tpl.get('type','unknown')}"]
    for s in tpl.get("sections", [])[:10]:
        lines.append(f"- {s.get('heading','(no heading)')}  |  slot: {s.get('slot','')}")
        g = (s.get("guidance") or "").strip()
        if g:
            lines.append(f"    · {g}")
    rules = tpl.get("style_rules") or {}
    if rules:
        lines.append("")
        lines.append("[style_rules]")
        for k, v in list(rules.items())[:8]:
            lines.append(f"- {k}: {v}")
    return "\n".join(lines)


# -----------------------------
# Rewrite Prompt (Template-Fill mode)
# -----------------------------
def build_prompt_template_fill(p: Dict[str, Any], template: Dict[str, Any]) -> Tuple[str, str]:
    """
    Uses a structural template to generate rewritten text.
    This tends to be more stable than pure imitation.
    """
    template = template or {"type": "generic", "sections": []}
    sections = template.get("sections", [])[:10]
    rules = template.get("style_rules") or {}

    # company/role anchoring
    company = (p.get("company") or "").strip()
    role = (p.get("role") or "").strip()
    anchor = ""
    if company or role:
        anchor = f"""
[지원 정보]
- 지원 회사: {company or "(미기입)"}
- 지원 직무: {role or "(미기입)"}
- 글 안에서 회사/직무 요구역량을 자연스럽게 반영하되, 사실은 원문에서만 가져와라.
"""

    # compact template spec
    template_spec = {
        "type": template.get("type", "generic"),
        "sections": sections,
        "style_rules": rules
    }

    system = (
        "너는 목적 기반 리라이팅 전문가다. "
        "입력된 원문을 '주어진 템플릿 구조'에 맞춰 재작성하라. "
        "원문의 사실(회사명/기간/수치/역할/성과)은 변경 금지. "
        "다만 문장/구조/표현은 목적에 맞게 적극적으로 편집 가능. "
        "출력은 반드시 JSON만."
    )

    user = f"""
{anchor}

[템플릿(JSON)]
{json.dumps(template_spec, ensure_ascii=False, indent=2)}

[원문]
{p["text"]}

[목적]
{p["major"]} → {p["minor"]}

[편집 조건]
편집 강도: {EDIT_INTENSITY[p["edit"]]}
톤: {p["tone"]}, 스타일: {p["style"]}, 독자: {p["audience"]}
분량: {p["length"]}자 근처 (±15%)

[요구사항]
- 섹션 헤딩을 템플릿대로 사용하라(heading_style에 맞춤).
- 각 섹션은 guidance를 충족하도록 작성.
- bullet_style이 있으면 해당 스타일로 불릿을 사용.
- style_rules.signature_patterns를 자연스럽게 반영(과하지 않게).
- 원문에 없는 성과 수치/기간/직책/기술은 만들어내지 마라.
- 결과는 목적 언어영역(register)만 남도록 정제.

[출력 JSON]
{{
 "rewritten_text": "",
 "change_points": [],
 "highlight_reasons": [],
 "detected_original_traits": [],
 "suggested_repurposes": []
}}
"""
    return system, user


# -----------------------------
# UI: Company/Role + Template mode + Library + A/B Compare
# -----------------------------
st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
st.markdown(
    """
<div class="card">
  <div class="card-title">🎯 회사/직무 + 템플릿 모드</div>
  <div class="muted">자소서/면접 목적일 때 특히 효과가 큼. 레퍼런스 구조를 템플릿으로 뽑아 '틀'에 채우는 방식.</div>
</div>
""",
    unsafe_allow_html=True
)

c1, c2, c3 = st.columns([1.1, 1.1, 1.2], gap="large")

with c1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🏢 지원 정보</div>', unsafe_allow_html=True)
    st.session_state.company_target = st.text_input("지원 회사", value=st.session_state.company_target, placeholder="예: 삼성전자")
    st.session_state.role_target = st.text_input("지원 직무", value=st.session_state.role_target, placeholder="예: 데이터 분석 / PM / SW")
    st.caption("※ 사실(성과/기간/직무경험)은 원문에서만 가져오고, 회사/직무는 '표현 방향'에만 사용")
    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🧠 레퍼런스 → 템플릿 추출</div>', unsafe_allow_html=True)

    tpl_mode = st.radio(
        "리라이팅 방식",
        ["레퍼런스 모사(기존)", "템플릿 채움(안정적)"],
        index=1,
        horizontal=False
    )

    tpl_btn = st.button("현재 레퍼런스로 템플릿 만들기")
    if tpl_btn:
        if not st.session_state.reference_text.strip():
            st.warning("레퍼런스를 먼저 설정해줘.")
        else:
            with st.spinner("템플릿 분석 중..."):
                tpl = extract_template_with_llm(api_key, model, st.session_state.reference_text)
            st.session_state.reference_template = tpl or {}
            st.success("템플릿을 생성했습니다.")

    if st.session_state.reference_template:
        st.text_area("템플릿 미리보기", render_template_preview(st.session_state.reference_template), height=220)
    else:
        st.caption("템플릿이 아직 없습니다. 버튼을 눌러 생성하세요.")

    st.markdown("</div>", unsafe_allow_html=True)

with c3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">⭐ 레퍼런스 라이브러리</div>', unsafe_allow_html=True)
    lib_name = st.text_input("저장 이름", placeholder="예: 삼성 합격 자소서 템플릿 A")
    save_btn = st.button("현재 레퍼런스 저장")
    clear_lib_btn = st.button("라이브러리 전체 삭제")

    if save_btn:
        if not st.session_state.reference_text.strip():
            st.warning("저장할 레퍼런스가 없습니다.")
        else:
            # ensure template exists (rule-based if not created)
            tpl = st.session_state.reference_template or simple_structure_guess(st.session_state.reference_text)
            item = {
                "name": lib_name.strip() or f"Reference {len(st.session_state.reference_library)+1}",
                "text": st.session_state.reference_text,
                "meta": st.session_state.reference_meta or {},
                "template": tpl
            }
            st.session_state.reference_library.append(item)
            st.success("라이브러리에 저장했습니다.")

    if clear_lib_btn:
        st.session_state.reference_library = []
        st.success("라이브러리를 비웠습니다.")

    if st.session_state.reference_library:
        names = [it["name"] for it in st.session_state.reference_library]
        pick_idx = st.selectbox("불러오기", list(range(len(names))), format_func=lambda i: names[i])
        colx, coly = st.columns(2)
        with colx:
            load_btn = st.button("선택 레퍼런스 로드")
        with coly:
            del_btn = st.button("선택 삭제")

        if load_btn:
            it = st.session_state.reference_library[pick_idx]
            st.session_state.reference_text = it["text"]
            st.session_state.reference_meta = it.get("meta") or {}
            st.session_state.reference_template = it.get("template") or {}
            st.success("레퍼런스를 로드했습니다.")

        if del_btn:
            st.session_state.reference_library.pop(pick_idx)
            st.success("삭제했습니다.")
    else:
        st.caption("아직 저장된 레퍼런스가 없습니다.")

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# A/B Compare (Two reference templates)
# -----------------------------
st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
st.markdown(
    """
<div class="card">
  <div class="card-title">🆚 A/B 비교 리라이팅</div>
  <div class="muted">레퍼런스 두 개(또는 템플릿 두 개)를 골라 결과를 나란히 비교합니다.</div>
</div>
""",
    unsafe_allow_html=True
)

if st.session_state.reference_library:
    ab_col1, ab_col2, ab_col3 = st.columns([1, 1, 1], gap="large")
    lib = st.session_state.reference_library
    names = [it["name"] for it in lib]

    with ab_col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        idxA = st.selectbox("A 레퍼런스", list(range(len(names))), format_func=lambda i: names[i], key="abA")
        useA_tpl = st.checkbox("A는 템플릿 채움 사용", value=True, key="abA_tpl")
        st.markdown("</div>", unsafe_allow_html=True)

    with ab_col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        idxB = st.selectbox("B 레퍼런스", list(range(len(names))), format_func=lambda i: names[i], key="abB")
        useB_tpl = st.checkbox("B는 템플릿 채움 사용", value=True, key="abB_tpl")
        st.markdown("</div>", unsafe_allow_html=True)

    with ab_col3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        ab_run = st.button("A/B 변환 실행")
        st.caption("원문/설정은 동일, 레퍼런스만 다르게 적용")
        st.markdown("</div>", unsafe_allow_html=True)

    if ab_run:
        if not api_key.strip():
            st.error("API Key를 입력해줘.")
        elif not st.session_state.get("original_text", "").strip():
            st.error("원본 텍스트를 입력해줘.")
        else:
            base_payload = {
                "text": st.session_state.get("original_text", ""),
                "major": major,
                "minor": minor,
                "tone": tone,
                "style": style,
                "audience": audience,
                "length": LENGTH_PRESET[length_key],
                "edit": edit_level,
                "company": st.session_state.company_target,
                "role": st.session_state.role_target
            }

            # A
            refA = lib[idxA]
            if useA_tpl:
                tplA = refA.get("template") or simple_structure_guess(refA.get("text",""))
                sysA, usrA = build_prompt_template_fill({**base_payload}, tplA)
            else:
                sysA, usrA = build_prompt({**base_payload, "reference_text": refA.get("text","")})

            # B
            refB = lib[idxB]
            if useB_tpl:
                tplB = refB.get("template") or simple_structure_guess(refB.get("text",""))
                sysB, usrB = build_prompt_template_fill({**base_payload}, tplB)
            else:
                sysB, usrB = build_prompt({**base_payload, "reference_text": refB.get("text","")})

            with st.spinner("A/B 변환 중..."):
                rawA = call_openai(api_key, model, sysA, usrA, temperature)
                rawB = call_openai(api_key, model, sysB, usrB, temperature)

            dataA = safe_json(rawA)
            dataB = safe_json(rawB)

            st.session_state.ab_variant = {
                "A": dataA.get("rewritten_text", ""),
                "B": dataB.get("rewritten_text", "")
            }

    A_txt = st.session_state.ab_variant.get("A","").strip()
    B_txt = st.session_state.ab_variant.get("B","").strip()

    if A_txt or B_txt:
        ca, cb = st.columns(2, gap="large")
        with ca:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">A 결과</div>', unsafe_allow_html=True)
            st.text_area("A", A_txt, height=320)
            st.download_button("A TXT 다운로드", A_txt, file_name="result_A.txt")
            st.markdown("</div>", unsafe_allow_html=True)

        with cb:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">B 결과</div>', unsafe_allow_html=True)
            st.text_area("B", B_txt, height=320)
            st.download_button("B TXT 다운로드", B_txt, file_name="result_B.txt")
            st.markdown("</div>", unsafe_allow_html=True)
else:
    st.caption("A/B 비교는 레퍼런스 라이브러리에 최소 1개 이상 저장되어야 사용할 수 있어요.")


# -----------------------------
# Patch the main '변환 실행' behavior to support template-fill mode
# (We keep your original UI intact; this adds a "템플릿 채움" 실행 버튼만 추가)
# -----------------------------
st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
st.markdown(
    """
<div class="card">
  <div class="card-title">⚡ 템플릿 채움으로 단일 실행</div>
  <div class="muted">현재 레퍼런스를 템플릿으로 만든 뒤, 그 틀에 맞춰 바로 리라이팅합니다.</div>
</div>
""",
    unsafe_allow_html=True
)

btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2], gap="large")
with btn_col1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    make_and_run = st.button("템플릿 생성+변환", key="make_and_run")
    st.markdown("</div>", unsafe_allow_html=True)

with btn_col2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    run_with_tpl = st.button("템플릿으로 변환", key="run_with_tpl")
    st.markdown("</div>", unsafe_allow_html=True)

with btn_col3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.caption("팁) 자소서라면 '지원 회사/직무'를 입력하고, 레퍼런스는 합격 자소서 1개를 추천.")
    st.markdown("</div>", unsafe_allow_html=True)

def do_template_fill_run(make_template_first: bool):
    if not api_key.strip():
        st.error("API Key를 입력해줘.")
        return
    origin = st.session_state.get("original_text", "") or ""
    if not origin.strip():
        st.error("원본 텍스트를 입력해줘.")
        return
    if not st.session_state.reference_text.strip():
        st.error("레퍼런스를 먼저 설정해줘.")
        return

    if make_template_first or not st.session_state.reference_template:
        with st.spinner("템플릿 분석 중..."):
            tpl = extract_template_with_llm(api_key, model, st.session_state.reference_text)
        st.session_state.reference_template = tpl or {}

    payload = {
        "text": origin,
        "major": major,
        "minor": minor,
        "tone": tone,
        "style": style,
        "audience": audience,
        "length": LENGTH_PRESET[length_key],
        "edit": edit_level,
        "company": st.session_state.company_target,
        "role": st.session_state.role_target
    }

    sys, usr = build_prompt_template_fill(payload, st.session_state.reference_template)

    with st.spinner("템플릿 채움 리라이팅 중..."):
        raw = call_openai(api_key, model, sys, usr, temperature)

    data = safe_json(raw)
    rewritten = data.get("rewritten_text", "")

    # Reuse your existing render pipeline
    st.session_state.last_raw = raw
    st.session_state.last_data = data
    st.session_state.last_rewritten = rewritten
    st.success("템플릿 채움 리라이팅 완료! (상단 '✅ 변환 결과' 카드에서 확인)")


if make_and_run:
    do_template_fill_run(make_template_first=True)

if run_with_tpl:
    do_template_fill_run(make_template_first=False)
