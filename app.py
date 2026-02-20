import os
import json
import re
import difflib
from typing import Dict, Any, List, Tuple, Optional

import streamlit as st
import requests

# optional libs
try:
    import trafilatura
except Exception:
    trafilatura = None

try:
    import pdfplumber
except Exception:
    pdfplumber = None


# ============================================================
# Page config
# ============================================================
st.set_page_config(
    page_title="RePurpose | 목적 기반 텍스트 변환",
    page_icon="🛠️",
    layout="wide"
)

# ============================================================
# CSS: "하얀 바" 원인 제거를 위해 HTML 카드 래핑을 없애고
# st.container(border=True)만 카드로 스타일링
# ============================================================
st.markdown(
    """
<style>
:root{
  --bg: #F5F6FA;
  --panel: rgba(255,255,255,.88);
  --ink: #0B1020;
  --muted: #5B647A;
  --line: rgba(15, 23, 42, .10);
  --brandA: #6A5CFF;
  --brandB: #9B8CFF;
  --shadow: 0 14px 40px rgba(16, 24, 40, 0.10);
  --shadow-sm: 0 10px 24px rgba(16, 24, 40, 0.08);
  --radius-xl: 22px;
  --radius-lg: 18px;
  --radius-md: 14px;
}

html, body, [data-testid="stAppViewContainer"]{
  background:
    radial-gradient(1100px 600px at 20% 0%, rgba(106,92,255,.14), transparent 55%),
    radial-gradient(900px 500px at 100% 10%, rgba(155,140,255,.12), transparent 60%),
    var(--bg) !important;
  color: var(--ink);
}

[data-testid="stHeader"]{ background: transparent; }

.block-container{
  padding-top: 18px;
  padding-bottom: 80px;
  max-width: 1280px;
}

/* Streamlit border container -> 카드화 */
div[data-testid="stVerticalBlockBorderWrapper"]{
  background: var(--panel);
  border: 1px solid rgba(255,255,255,.55);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

/* 사이드바 카드화 */
[data-testid="stSidebar"]{
  background: transparent;
}
[data-testid="stSidebar"] > div:first-child{
  background: rgba(255,255,255,.80);
  border: 1px solid rgba(255,255,255,.55);
  border-radius: var(--radius-xl);
  margin: 14px;
  padding: 14px 14px 18px;
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

/* 버튼 */
.stButton > button{
  background: linear-gradient(120deg, var(--brandA), var(--brandB));
  border: none;
  color: white;
  padding: 0.85rem 1.2rem;
  border-radius: 14px;
  font-weight: 800;
  box-shadow: 0 12px 26px rgba(106,92,255,.22);
}
.stButton > button:hover{ filter: brightness(1.02); }

/* secondary 버튼 느낌 */
button[kind="secondary"]{
  border-radius: 14px !important;
}

/* 텍스트 입력 둥글게 */
textarea, input{
  border-radius: 14px !important;
}

small, .muted { color: var(--muted); }

/* Hero */
.hero{
  background: linear-gradient(120deg, var(--brandA), var(--brandB));
  border-radius: var(--radius-xl);
  padding: 18px 20px;
  color: white;
  box-shadow: var(--shadow);
  margin-bottom: 14px;
}
.hero .title{
  font-size: 1.85rem;
  font-weight: 900;
  margin: 0 0 6px 0;
  line-height: 1.15;
}
.hero .sub{
  margin: 0;
  opacity: .92;
  font-size: .98rem;
}

/* 탭 라벨 살짝 앱처럼 */
div[data-testid="stTabs"] button{
  border-radius: 999px !important;
}
</style>
""",
    unsafe_allow_html=True
)

# ============================================================
# Constants (너 기존 그대로)
# ============================================================
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

LENGTH_PRESET = {"짧게": 600, "보통": 1200, "길게": 2200}

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

# ============================================================
# Session State (필수)
# ============================================================
def ss_init(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

ss_init("show_sidebar", True)
ss_init("reference_text", "")
ss_init("reference_meta", {})
ss_init("reference_template", {})
ss_init("reference_library", [])
ss_init("company_target", "")
ss_init("role_target", "")

ss_init("last_raw", "")
ss_init("last_data", {})
ss_init("last_rewritten", "")

# ============================================================
# Helpers (diff / json)
# ============================================================
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

def safe_json(text):
    try:
        return json.loads(text)
    except:
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group()) if m else {}

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

# ============================================================
# Reference fetchers (유지)
# ============================================================
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_url_text(url: str, timeout: int = 12) -> Tuple[str, Dict[str, Any]]:
    meta = {"url": url}
    try:
        r = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"
        })
        meta["status_code"] = r.status_code
        html = r.text
    except Exception as e:
        return "", {"url": url, "error": str(e)}

    if trafilatura:
        try:
            downloaded = trafilatura.extract(html, include_comments=False, include_tables=False)
            if downloaded and len(downloaded.strip()) > 200:
                return downloaded.strip(), meta
        except Exception as e:
            meta["trafilatura_error"] = str(e)

    text = re.sub(r"<script[\s\S]*?</script>", " ", html)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 2000:
        text = text[:20000]
        meta["truncated"] = True
    return text, meta

def extract_pdf_text(file_bytes: bytes, max_pages: int = 12) -> str:
    if not pdfplumber:
        return "PDF 텍스트 추출을 위해 pdfplumber 설치가 필요합니다. (pip install pdfplumber)"
    out = []
    try:
        import io
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages[:max_pages]:
                txt = page.extract_text() or ""
                if txt.strip():
                    out.append(txt.strip())
    except Exception as e:
        return f"PDF 추출 실패: {e}"
    return "\n\n".join(out).strip()

# ============================================================
# OpenAI call (유지)
# ============================================================
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

# ============================================================
# Prompt Builder (레퍼런스 기반 유지)
# ============================================================
def build_prompt(p: Dict[str, Any]):
    template = STRUCTURE_TEMPLATES.get(p["minor"], "논리적 구조로 구성")

    ref_text = (p.get("reference_text") or "").strip()
    ref_block = ""
    if ref_text:
        ref_short = ref_text[:6000]
        ref_block = f"""
[참고 레퍼런스(템플릿)]
- 아래 레퍼런스의 '구조/문단 길이/문장 톤/헤딩 스타일/불릿 패턴'을 강하게 모사하되,
  원문 사실은 절대 왜곡하지 마라.

[레퍼런스 본문]
{ref_short}
"""

    system = (
        "너는 전문 텍스트 편집자이자 목적 기반 리라이팅 전문가다. "
        "모든 사실 정보는 유지하되, 표현 방식만 목적에 맞는 언어 영역(register)으로 변환하라. "
        "추론 설명 없이 결과만 JSON으로 반환하라. "
        "단, 사실관계(회사명/기간/수치/역할/성과)는 원문에서 벗어나지 마라. "
        "반드시 선택된 목적에 대응하는 구조 템플릿을 사용해 글을 재구성하라."
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

# ============================================================
# UI: Header + Sidebar Toggle
# ============================================================
st.markdown(
    """
<div class="hero">
  <div class="title">목적 기반 텍스트 리라이팅 워크스페이스</div>
  <p class="sub">원문을 붙여넣고, 목적에 맞게 리라이팅합니다. 자소서/논문/기획/SNS는 목적에 따라 화면이 자동으로 단순화됩니다.</p>
</div>
""",
    unsafe_allow_html=True
)

top_left, top_right = st.columns([1, 1])
with top_left:
    if st.button("🧭 사이드바 토글"):
        st.session_state.show_sidebar = not st.session_state.show_sidebar

# 사이드바 숨김 CSS
if not st.session_state.show_sidebar:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none; }
        /* 사이드바가 사라지면 메인 여백 줄이기 */
        section.main { margin-left: 0rem !important; }
        </style>
        """,
        unsafe_allow_html=True
    )

# ============================================================
# Sidebar: "최소 설정만" 남기고, 나머지는 목적별 화면에서만 노출
# ============================================================
with st.sidebar:
    st.markdown("### ⚙️ 기본 설정")
    api_key = st.text_input("API Key", type="password")
    model = st.selectbox("모델", ["gpt-4o-mini", "gpt-4.1-mini"])

    st.markdown("---")
    st.markdown("### 🎯 목적 설정")
    major = st.selectbox("대목적", list(MAJOR_PURPOSES.keys()))
    minor = st.selectbox("소목적", MAJOR_PURPOSES[major])

    tone = st.selectbox("톤", TONE)
    style = st.selectbox("스타일", STYLE)
    audience = st.selectbox("독자", AUDIENCE)

    length_key = st.select_slider("분량", list(LENGTH_PRESET.keys()))
    edit_level = st.select_slider("편집 강도", list(EDIT_INTENSITY.keys()))
    temperature = st.slider("창의성", 0.0, 1.0, 0.5)

    st.markdown("---")
    st.caption("레퍼런스/템플릿 설정은 '대목적'에 따라 메인 화면에서만 표시됩니다.")


# ============================================================
# Main Layout: 탭 2개로 단순화
# - [작성] 원문 입력 + 결과
# - [레퍼런스] (자소서/논문/SNS일 때만) 관련 설정 노출
# ============================================================
tab_write, tab_ref = st.tabs(["✍️ 작성", "📚 레퍼런스/템플릿"])

# ============================================================
# Tab: 작성
# ============================================================
with tab_write:
    left, right = st.columns([1.05, 1.15], gap="large")

    with left:
        with st.container(border=True):
            st.subheader("🧾 원본 텍스트")
            original_text = st.text_area("원본", height=320, key="original_text", label_visibility="collapsed")
            run = st.button("변환 실행")

            st.divider()
            st.caption("💡 팁) 레퍼런스를 설정하면 결과가 더 '합격 자소서/논문' 결에 가까워져요.")

    with right:
        with st.container(border=True):
            st.subheader("✅ 변환 결과")

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

            data = st.session_state.last_data or {}
            rewritten = st.session_state.last_rewritten or ""

            if rewritten.strip() and original_text.strip():
                st.markdown("**하이라이트(변경점 표시)**")
                st.markdown(render_diff_html(original_text, rewritten), unsafe_allow_html=True)

                st.divider()

                highlight_reasons = data.get("highlight_reasons") or data.get("change_points", [])
                st.markdown("**하이라이트 이유**")
                if highlight_reasons:
                    for reason in highlight_reasons:
                        st.write("-", reason)
                else:
                    st.caption("표시할 이유가 없습니다.")

                st.divider()

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

                st.divider()

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**💡 재활용 추천**")
                    suggested = data.get("suggested_repurposes") or derive_repurpose_suggestions(major, minor)
                    for r in suggested:
                        if isinstance(r, dict):
                            st.write(f"{r.get('major_purpose','기타')} → {r.get('minor_purpose','기타')}")
                        else:
                            st.write(r)

                with col2:
                    st.markdown("**📈 품질 점수**")
                    score = min(95, 60 + len(rewritten)//200)
                    st.progress(score/100)
                    st.write(f"{score}/100")

                st.divider()

                d1, d2 = st.columns(2)
                with d1:
                    st.download_button("TXT 다운로드", rewritten, file_name="result.txt")
                with d2:
                    st.download_button("MD 다운로드", rewritten, file_name="result.md")

            else:
                st.caption("변환 실행 후 결과가 표시됩니다.")


# ============================================================
# Tab: 레퍼런스/템플릿 (대목적에 따라 필요한 UI만 보여줌)
# - 자소서/면접: 자소서 레퍼런스 설정 + 회사/직무 입력 (템플릿 기능은 2/3에서 더 정리)
# - 학술/논문: 논문 레퍼런스 설정
# - SNS/콘텐츠: SNS 레퍼런스 설정 (2/3에서 '블로그/인스타' 추출 + 스타일 분석 붙임)
# - 그 외: 깔끔하게 "레퍼런스 없음" 안내
# ============================================================
with tab_ref:
    if major == "자소서/면접":
        with st.container(border=True):
            st.subheader("🏢 자소서 레퍼런스/지원 정보")
            st.caption("자소서/면접 목적일 때만 이 화면이 나타납니다.")

            c1, c2 = st.columns([1, 1], gap="large")
            with c1:
                st.session_state.company_target = st.text_input("지원 회사", value=st.session_state.company_target, placeholder="예: 삼성전자")
                st.session_state.role_target = st.text_input("지원 직무", value=st.session_state.role_target, placeholder="예: 데이터분석 / SW / PM")
                st.info("※ 회사/직무는 '표현 방향'에만 사용(사실/성과는 원문에서만).")

            with c2:
                ref_mode = st.radio(
                    "레퍼런스 가져오기",
                    ["URL 붙여넣기", "PDF 업로드", "직접 붙여넣기"],
                    horizontal=True
                )
                if ref_mode == "URL 붙여넣기":
                    url = st.text_input("레퍼런스 URL", placeholder="공개된 합격 자소서/블로그 글 URL")
                    if st.button("가져오기"):
                        with st.spinner("추출 중..."):
                            txt, meta = fetch_url_text(url.strip())
                        if txt.strip():
                            st.session_state.reference_text = txt
                            st.session_state.reference_meta = meta
                            st.success("레퍼런스를 설정했습니다.")
                        else:
                            st.warning("추출 실패(로그인/차단/유료일 수 있음). PDF 업로드/직접 붙여넣기를 추천.")
                elif ref_mode == "PDF 업로드":
                    pdf = st.file_uploader("PDF", type=["pdf"])
                    if st.button("PDF 텍스트 추출") and pdf is not None:
                        with st.spinner("PDF 추출 중..."):
                            txt = extract_pdf_text(pdf.read())
                        if txt.strip():
                            st.session_state.reference_text = txt
                            st.session_state.reference_meta = {"source": "pdf", "name": pdf.name}
                            st.success("레퍼런스를 설정했습니다.")
                        else:
                            st.warning("PDF 추출 실패")
                else:
                    pasted = st.text_area("레퍼런스 텍스트 붙여넣기", height=160)
                    if st.button("레퍼런스로 설정"):
                        st.session_state.reference_text = pasted or ""
                        st.session_state.reference_meta = {"source": "pasted"}
                        st.success("레퍼런스를 설정했습니다.")

            st.divider()
            st.subheader("📌 현재 레퍼런스 미리보기")
            if st.session_state.reference_text.strip():
                st.text_area("reference", st.session_state.reference_text[:7000], height=240, label_visibility="collapsed")
                if st.button("레퍼런스 비우기"):
                    st.session_state.reference_text = ""
                    st.session_state.reference_meta = {}
                    st.success("레퍼런스를 비웠습니다.")
            else:
                st.caption("레퍼런스를 설정하면 여기에서 확인할 수 있어요.")

    elif major == "학술/논문":
        with st.container(border=True):
            st.subheader("📄 논문 레퍼런스")
            st.caption("학술/논문 목적일 때만 이 화면이 나타납니다.")
            ref_mode = st.radio(
                "레퍼런스 가져오기",
                ["URL 붙여넣기", "PDF 업로드", "직접 붙여넣기"],
                horizontal=True
            )
            if ref_mode == "URL 붙여넣기":
                url = st.text_input("논문 URL", placeholder="오픈된 논문 페이지 / arXiv / 학회 페이지")
                if st.button("가져오기"):
                    with st.spinner("추출 중..."):
                        txt, meta = fetch_url_text(url.strip())
                    if txt.strip():
                        st.session_state.reference_text = txt
                        st.session_state.reference_meta = meta
                        st.success("레퍼런스를 설정했습니다.")
                    else:
                        st.warning("추출 실패(유료/차단 가능). PDF 업로드/직접 붙여넣기를 추천.")
            elif ref_mode == "PDF 업로드":
                pdf = st.file_uploader("PDF", type=["pdf"])
                if st.button("PDF 텍스트 추출") and pdf is not None:
                    with st.spinner("PDF 추출 중..."):
                        txt = extract_pdf_text(pdf.read())
                    if txt.strip():
                        st.session_state.reference_text = txt
                        st.session_state.reference_meta = {"source": "pdf", "name": pdf.name}
                        st.success("레퍼런스를 설정했습니다.")
                    else:
                        st.warning("PDF 추출 실패")
            else:
                pasted = st.text_area("레퍼런스 텍스트 붙여넣기", height=160)
                if st.button("레퍼런스로 설정"):
                    st.session_state.reference_text = pasted or ""
                    st.session_state.reference_meta = {"source": "pasted"}
                    st.success("레퍼런스를 설정했습니다.")

            st.divider()
            st.subheader("📌 현재 레퍼런스 미리보기")
            if st.session_state.reference_text.strip():
                st.text_area("reference", st.session_state.reference_text[:7000], height=240, label_visibility="collapsed")
                if st.button("레퍼런스 비우기"):
                    st.session_state.reference_text = ""
                    st.session_state.reference_meta = {}
                    st.success("레퍼런스를 비웠습니다.")
            else:
                st.caption("레퍼런스를 설정하면 여기에서 확인할 수 있어요.")

    elif major == "SNS/콘텐츠":
        with st.container(border=True):
            st.subheader("📣 SNS 레퍼런스")
            st.caption("SNS/콘텐츠 목적일 때만 이 화면이 나타납니다. (2/3에서 블로그/인스타 전용 추출+분석 기능이 추가됩니다)")
            ref_mode = st.radio(
                "레퍼런스 가져오기",
                ["URL 붙여넣기", "직접 붙여넣기"],
                horizontal=True
            )
            if ref_mode == "URL 붙여넣기":
                url = st.text_input("레퍼런스 URL", placeholder="블로그 글 / 인스타 게시물(가능하면 공개) 링크")
                if st.button("가져오기"):
                    with st.spinner("추출 중..."):
                        txt, meta = fetch_url_text(url.strip())
                    if txt.strip():
                        st.session_state.reference_text = txt
                        st.session_state.reference_meta = meta
                        st.success("레퍼런스를 설정했습니다.")
                    else:
                        st.warning("추출 실패(인스타는 자주 막힘). '직접 붙여넣기'를 추천.")
            else:
                pasted = st.text_area("레퍼런스 텍스트 붙여넣기", height=200)
                if st.button("레퍼런스로 설정"):
                    st.session_state.reference_text = pasted or ""
                    st.session_state.reference_meta = {"source": "pasted"}
                    st.success("레퍼런스를 설정했습니다.")

            st.divider()
            st.subheader("📌 현재 레퍼런스 미리보기")
            if st.session_state.reference_text.strip():
                st.text_area("reference", st.session_state.reference_text[:7000], height=240, label_visibility="collapsed")
                if st.button("레퍼런스 비우기"):
                    st.session_state.reference_text = ""
                    st.session_state.reference_meta = {}
                    st.success("레퍼런스를 비웠습니다.")
            else:
                st.caption("레퍼런스를 설정하면 여기에서 확인할 수 있어요.")

    else:
        with st.container(border=True):
            st.subheader("📚 레퍼런스/템플릿")
            st.caption("현재 대목적에서는 레퍼런스 기능이 필수는 아니어서 숨겨져 있어요.")
            st.info("대목적을 '자소서/면접', '학술/논문', 'SNS/콘텐츠'로 바꾸면 해당 전용 화면이 나타납니다.")

