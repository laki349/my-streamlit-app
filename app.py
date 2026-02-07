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
            out.append(f"<span style='background:#C8FACC'>{' '.join(b[j1:j2])}</span>")
        elif tag == "replace":
            out.append(f"<span style='background:#FFF3A3'>{' '.join(b[j1:j2])}</span>")
        elif tag == "delete":
            out.append(f"<span style='color:#E74C3C;text-decoration:line-through'>{' '.join(a[i1:i2])}</span>")

    return f"<div style='line-height:1.8'>{' '.join(out)}</div>"

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
        "너는 편집자다. 사실을 유지하며 목적에 맞게 글을 재구성하라. "
        "출력은 JSON만 반환하라."
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
 "detected_original_traits": [],
 "suggested_repurposes": []
}}
"""
    return system, user

# -----------------------------
# UI Sidebar
# -----------------------------
with st.sidebar:
    st.header("⚙️ 설정")
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
st.title("🛠️ RePurpose")

original_text = st.text_area("원본 텍스트", height=280)
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

    st.subheader("✅ 변환 결과 (하이라이트)")
    st.markdown(render_diff_html(original_text, rewritten), unsafe_allow_html=True)

    st.subheader("🔍 변경 포인트")
    for c in data.get("change_points", []):
        st.write("-", c)

    st.subheader("💡 재활용 추천")
    for r in data.get("suggested_repurposes", []):
        st.write(f"{r['major_purpose']} → {r['minor_purpose']}")

    # AI Score (simple heuristic)
    st.subheader("📈 품질 점수")
    score = min(95, 60 + len(rewritten)//200)
    st.progress(score/100)
    st.write(f"{score}/100")

    # Downloads
    st.download_button("TXT 다운로드", rewritten, file_name="result.txt")
    st.download_button("MD 다운로드", rewritten, file_name="result.md")
