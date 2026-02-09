import os
import json
import re
import difflib
from typing import Dict, Any, List, Tuple
import streamlit as st

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="RePurpose | 목적 기반 텍스트 변환",
    page_icon="🛠️",
    layout="wide"
)

st.markdown(
    """
    <style>
        :root {
            --primary-start: #6A5CFF;
            --primary-end: #9B8CFF;
            --accent-soft: #E9E6FF;
            --card-shadow: 0 8px 20px rgba(17, 24, 39, 0.08);
            --card-radius: 20px;
            --border-subtle: #E8EAF3;
        }

        .stApp {
            background: #F6F7FB;
        }

        .main-wrap {
            max-width: 1200px;
            margin: 0 auto;
            padding: 28px 32px 80px;
        }

        .header-card {
            background: linear-gradient(120deg, var(--primary-start), var(--primary-end));
            border-radius: var(--card-radius);
            padding: 28px 32px;
            color: white;
            box-shadow: var(--card-shadow);
            margin-bottom: 28px;
            position: sticky;
            top: 16px;
            z-index: 5;
        }

        .header-card h1 {
            font-size: 2.4rem;
            margin-bottom: 6px;
        }

        .header-subtitle {
            font-size: 1rem;
            opacity: 0.85;
            margin: 0;
        }

        .content-card {
            background: white;
            border-radius: var(--card-radius);
            padding: 28px 32px;
            box-shadow: var(--card-shadow);
            margin-bottom: 28px;
            border: 1px solid var(--border-subtle);
        }

        .content-card h3,
        .content-card h4 {
            margin-top: 0;
        }

        .stButton {
            display: flex;
            justify-content: center;
            margin: 10px 0 30px;
        }

        .stButton > button {
            background: linear-gradient(120deg, var(--primary-start), var(--primary-end));
            color: white;
            border: none;
            padding: 0.9rem 2.4rem;
            border-radius: 16px;
            font-size: 1.02rem;
            font-weight: 600;
            box-shadow: 0 10px 24px rgba(106, 92, 255, 0.24);
        }

        .stButton > button:hover {
            filter: brightness(1.02);
        }

        .stDownloadButton > button {
            background: #F5F6FF;
            color: #4A3DEB;
            border: 1px solid #D9D4FF;
            border-radius: 14px;
            padding: 0.55rem 1.4rem;
        }

        [data-testid="stSidebar"] {
            background: transparent;
        }

        [data-testid="stSidebar"] > div:first-child {
            background: white;
            border-radius: var(--card-radius);
            margin: 16px;
            padding: 20px 20px 28px;
            box-shadow: var(--card-shadow);
            border: 1px solid var(--border-subtle);
        }

        .sidebar-header {
            font-weight: 700;
            font-size: 1.1rem;
            margin-bottom: 12px;
        }

    </style>
    """,
    unsafe_allow_html=True
)

# -----------------------------
# Constants
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
    "서론": "배경 → 한계 → 공백 → 목적",
    "기획서": "문제 → 해결 → 차별성 → 효과"
}

# -----------------------------
# Diff Helpers
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
            out.append(f"<span style='background:#FDE2E2;color:#B91C1C;text-decoration:line-through'>{' '.join(a[i1:i2])}</span>")

    return f"<div style='line-height:1.8'>{' '.join(out)}</div>"

# -----------------------------
# Insight Helpers
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
# Prompt Builder
# -----------------------------
def build_prompt(p):
    template = STRUCTURE_TEMPLATES.get(p["minor"], "논리적 구조로 구성")

    system = (
        "너는 전문 텍스트 편집자이자 목적 기반 리라이팅 전문가다. "
        "모든 사실 정보는 유지하되, 표현 방식만 목적에 맞는 언어 영역(register)으로 변환하라. "
        "학술, 비즈니스, SNS, 자기소개서 각각의 문체 차이를 엄격히 구분하여 적용하라. "
        "부적절한 관용구, 도메인 표현, 톤은 제거하지 말고 반드시 목적에 맞게 치환하라. "
        "문체의 다양성과 리듬은 유지하고 문장을 획일화하지 마라. "
        "추론 설명 없이 결과만 JSON으로 반환하라. "
        "원문에 없는 정보라도 목적에 어울리는 홍보/설명/맥락 요소를 자의적으로 추가할 수 있다. "
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
        "모든 문장을 획일화하지 말고 문체적 리듬과 개성은 남겨라. "
        "각 문장을 목적 적합/부분 충돌/완전 충돌로 분류해 "
        "유지 또는 고급화/치환/구조 재서술로 처리하라. "
        "결과물에는 목적 언어 영역만 존재하도록 정제하라."
        "너는 반드시 선택된 목적에 대응하는 구조 템플릿을 사용해 글을 재구성하라."
        "[논문 템플릿]배경 -> 문제 -> 연구 공백 -> 목적 -> 시사점"
        "[기획서 템플릿] 문제 -> 원인 -> 해결 -> 차별성 -> 효과"
        "[자소서 템플릿] 상황 -> 행동 -> 역량 -> 결과 -> 연결"
        "[SNS 템플릿] 후킹 -> 공감 -> 메시지 -> 행동 유도"

    )

    user = f"""
원본:
{p["text"]}

목적: {p["major"]} → {p["minor"]}
구조: {template}
편집 강도: {EDIT_INTENSITY[p["edit"]]}
톤: {p["tone"]}, 스타일: {p["style"]}, 독자: {p["audience"]}
분량: {p["length"]}자

JSON:
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
# UI Sidebar
# -----------------------------
with st.sidebar:
    st.markdown("<div class='sidebar-header'>⚙️ 설정</div>", unsafe_allow_html=True)
    api_key = st.text_input("API Key", type="password")
    model = st.selectbox("모델", ["gpt-4o-mini", "gpt-4.1-mini"])
    persona = st.selectbox("특성", PERSONA_OPTIONS)
    major = st.selectbox("대목적", MAJOR_PURPOSES.keys())
    minor = st.selectbox("소목적", MAJOR_PURPOSES[major])
    tone = st.selectbox("톤", TONE)
    style = st.selectbox("스타일", STYLE)
    audience = st.selectbox("독자", AUDIENCE)
    length_key = st.select_slider("분량", LENGTH_PRESET.keys())
    edit_level = st.select_slider("편집 강도", EDIT_INTENSITY.keys())
    temperature = st.slider("창의성", 0.0, 1.0, 0.5)

# -----------------------------
# Main
# -----------------------------
st.markdown("<div class='main-wrap'>", unsafe_allow_html=True)
st.markdown("<div class='header-card'>", unsafe_allow_html=True)
st.title("🛠️ RePurpose")
st.markdown(
    "<p class='header-subtitle'>목적 기반 텍스트 리라이팅을 위한 스마트 편집 워크스페이스</p>",
    unsafe_allow_html=True
)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='content-card'>", unsafe_allow_html=True)
st.markdown("<h3>원본 텍스트 입력</h3>", unsafe_allow_html=True)
original_text = st.text_area("원본 텍스트", height=280)
st.markdown("</div>", unsafe_allow_html=True)

run = st.button("변환")

if run:
    payload = {
        "text": original_text,
        "major": major,
        "minor": minor,
        "tone": tone,
        "style": style,
        "audience": audience,
        "length": LENGTH_PRESET[length_key],
        "edit": edit_level
    }

    system, user = build_prompt(payload)

    with st.spinner("변환 중..."):
        raw = call_openai(api_key, model, system, user, temperature)

    data = safe_json(raw)
    rewritten = data.get("rewritten_text", "")

    st.markdown("<div class='content-card'>", unsafe_allow_html=True)
    st.markdown("<h3>✅ 변환 결과 (하이라이트)</h3>", unsafe_allow_html=True)
    highlight_reasons = data.get("highlight_reasons") or data.get("change_points", [])
    result_col, reason_col = st.columns([2, 1])
    with result_col:
        st.markdown(render_diff_html(original_text, rewritten), unsafe_allow_html=True)
    with reason_col:
        st.markdown("**하이라이트 이유**")
        if highlight_reasons:
            for reason in highlight_reasons:
                st.write("-", reason)
        else:
            st.caption("표시할 이유가 없습니다.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='content-card'>", unsafe_allow_html=True)
    st.markdown("<h3>🔍 변경 포인트</h3>", unsafe_allow_html=True)

    change_points = data.get("change_points") or derive_change_points(original_text, rewritten)

    for c in change_points:
        if isinstance(c, dict):
            st.markdown(
                f"**원문:** {c.get('original','')}\n\n"
                f"➡️ **변경:** {c.get('rewritten','')}"
            )
        else:
            st.write("•", c)
    st.markdown("</div>", unsafe_allow_html=True)

if run:
    data = safe_json(raw)
    rewritten = data.get("rewritten_text", "")

    card_col_left, card_col_right = st.columns(2)
    with card_col_left:
        st.markdown("<div class='content-card'>", unsafe_allow_html=True)
        st.markdown("<h3>💡 재활용 추천</h3>", unsafe_allow_html=True)

        suggested = data.get("suggested_repurposes") or derive_repurpose_suggestions(major, minor)

        if suggested:
            for r in suggested:
                if isinstance(r, dict):
                    major_purpose = r.get("major_purpose", "기타")
                    minor_purpose = r.get("minor_purpose", "기타")
                    st.write(f"{major_purpose} → {minor_purpose}")
                else:
                    st.write(r)
        else:
            st.caption("추천 항목이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)



    # AI Score (simple heuristic)
    with card_col_right:
        st.markdown("<div class='content-card'>", unsafe_allow_html=True)
        st.markdown("<h3>📈 품질 점수</h3>", unsafe_allow_html=True)
        score = min(95, 60 + len(rewritten)//200)
        st.progress(score/100)
        st.write(f"{score}/100")
        st.markdown("</div>", unsafe_allow_html=True)

    # Downloads
    st.markdown("<div class='content-card'>", unsafe_allow_html=True)
    st.markdown("<h3>⬇️ 다운로드</h3>", unsafe_allow_html=True)
    download_col1, download_col2 = st.columns(2)
    with download_col1:
        st.download_button("TXT 다운로드", rewritten, file_name="result.txt")
    with download_col2:
        st.download_button("MD 다운로드", rewritten, file_name="result.md")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
