import os
import json
import re
import difflib
import streamlit as st

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="RePurpose | 목적 기반 텍스트 변환",
    page_icon="🛠️",
    layout="wide"
)

# -----------------------------
# Constants
# -----------------------------
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
    "서론": "배경 → 한계 → 공백 → 목적",
    "기획서": "문제 → 해결 → 차별성 → 효과"
}

# -----------------------------
# Diff Helper
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
            out.append(f"<span style='background:#C8FACC'>{' '.join(b[j1:j2])}</span>")
        elif tag == "replace":
            out.append(f"<span style='background:#FFF3A3'>{' '.join(b[j1:j2])}</span>")
        elif tag == "delete":
            out.append(f"<span style='color:#E74C3C;text-decoration:line-through'>{' '.join(a[i1:i2])}</span>")

    return f"<div style='line-height:1.8'>{' '.join(out)}</div>"

# -----------------------------
# Fallback logic
# -----------------------------
def derive_change_points(original, rewritten):
    points = []
    if len(rewritten) - len(original) > 50:
        points.append("내용이 확장되며 설명이 강화되었습니다.")
    if not points:
        points.append("문장이 자연스럽게 정제되었습니다.")
    return points

def derive_repurpose_suggestions(major, minor):
    results = []
    for m in MAJOR_PURPOSES.get(major, []):
        if m != minor:
            results.append({"major_purpose": major, "minor_purpose": m})
    return results[:3]

# -----------------------------
# OpenAI Call
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
    template = STRUCTURE_TEMPLATES.get(p["minor"], "논리적 구조")

    system = (
        "너는 전문 텍스트 편집자이자 목적 기반 리라이팅 전문가다. "
        "사실 정보는 유지하고 표현만 목적에 맞는 언어 영역으로 변환하라. "
        "문체 다양성을 유지하며 획일화하지 마라. "
        "부적절한 표현은 삭제하지 말고 치환하라. "
        "결과는 JSON만 반환하라."
    )

    user = f"""
원본:
{p["text"]}

목적: {p["major"]} → {p["minor"]}
구조: {template}
편집 강도: {EDIT_INTENSITY[p["edit"]]}
톤: {p["tone"]}
스타일: {p["style"]}
독자: {p["audience"]}
분량: {p["length"]}자

JSON:
{{
 "rewritten_text": "",
 "expanded_text": "",
 "change_points": [],
 "suggested_repurposes": []
}}
"""

    return system, user

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    api_key = st.text_input("API Key", type="password")
    model = st.selectbox("모델", ["gpt-4o-mini", "gpt-4.1-mini"])
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
st.title("🛠️ RePurpose")

original_text = st.text_area("원본 텍스트", height=280)

if st.button("변환"):
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

    raw = call_openai(api_key, model, system, user, temperature)
    data = safe_json(raw)

    rewritten = data.get("rewritten_text", "")

    st.subheader("✅ 변환 결과")
    st.markdown(render_diff_html(original_text, rewritten), unsafe_allow_html=True)

    st.subheader("🔍 변경 포인트")
    for c in data.get("change_points", []) or derive_change_points(original_text, rewritten):
        st.write("-", c)

    st.subheader("💡 재활용 추천")
    suggested = data.get("suggested_repurposes", []) or derive_repurpose_suggestions(major, minor)

    for r in suggested:
        if isinstance(r, dict):
            st.write(f"{r.get('major_purpose')} → {r.get('minor_purpose')}")
        else:
            st.write(str(r))
