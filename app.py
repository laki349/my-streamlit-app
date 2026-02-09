import os
import json
import re
import difflib
from typing import Dict, Any
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
# Global CSS (깔끔한 워크스페이스 UI)
# -----------------------------
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"]{
    background:#F7F8FA;
}

.workspace-header{
  margin-bottom: 18px;
}
.workspace-header h1{
  margin:0;
  font-size:1.8rem;
}
.workspace-header p{
  color:#6B7280;
  margin-top:4px;
}

.editor-card{
  background:white;
  border-radius:18px;
  padding:22px 24px;
  box-shadow:0 10px 28px rgba(0,0,0,.06);
  border:1px solid #E5E7EB;
  height:100%;
}

.stButton > button{
  width:100%;
  padding:14px;
  border-radius:14px;
  background:#111827;
  color:white;
  font-weight:700;
  border:none;
}
</style>
""", unsafe_allow_html=True)

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
EDIT_INTENSITY = ["유지 위주", "균형 조정", "적극 재구성", "완전 리라이팅"]

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
            out.append(f"<mark style='background:#FEF3C7'>{' '.join(b[j1:j2])}</mark>")
        elif tag == "replace":
            out.append(f"<mark style='background:#DCFCE7'>{' '.join(b[j1:j2])}</mark>")
        elif tag == "delete":
            out.append(f"<span style='text-decoration:line-through;color:#991B1B'>{' '.join(a[i1:i2])}</span>")

    return f"<div style='line-height:1.9'>{' '.join(out)}</div>"

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
            {"role": "user", "content": user_prompt}
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
# Sidebar (설정 패널)
# -----------------------------
with st.sidebar:
    st.header("⚙️ 설정")

    api_key = st.text_input("OpenAI API Key", type="password")
    model = st.selectbox("모델", ["gpt-4o-mini", "gpt-4.1-mini"])

    major = st.selectbox("대목적", list(MAJOR_PURPOSES.keys()))
    minor = st.selectbox("소목적", MAJOR_PURPOSES[major])

    tone = st.selectbox("톤", TONE)
    style = st.selectbox("스타일", STYLE)
    audience = st.selectbox("독자", AUDIENCE)

    length_key = st.select_slider("분량", list(LENGTH_PRESET.keys()))
    edit_level = st.select_slider("편집 강도", EDIT_INTENSITY)

    temperature = st.slider("창의성", 0.0, 1.0, 0.5)

# -----------------------------
# Prompt Builder
# -----------------------------
def build_prompt(payload):
    system = "너는 목적 기반 전문 텍스트 리라이팅 편집자다. 결과만 JSON으로 반환하라."

    user = f"""
원본:
{payload["text"]}

목적: {payload["major"]} → {payload["minor"]}
톤: {payload["tone"]}
스타일: {payload["style"]}
독자: {payload["audience"]}
편집 강도: {payload["edit"]}
분량: {payload["length"]}

JSON 형식:
{{
 "rewritten_text": ""
}}
"""
    return system, user

# -----------------------------
# Main Workspace
# -----------------------------
st.markdown("""
<div class="workspace-header">
  <h1>🛠 RePurpose</h1>
  <p>원문을 목적에 맞는 고품질 텍스트로 즉시 변환합니다</p>
</div>
""", unsafe_allow_html=True)

left_editor, right_editor = st.columns(2)

with left_editor:
    st.markdown("<div class='editor-card'>", unsafe_allow_html=True)
    st.markdown("### 원본 텍스트")
    original_text = st.text_area("", height=340)
    st.markdown("</div>", unsafe_allow_html=True)

with right_editor:
    st.markdown("<div class='editor-card'>", unsafe_allow_html=True)
    st.markdown("### 변환 결과")

    if "rewritten" in st.session_state:
        st.markdown(
            render_diff_html(original_text, st.session_state.rewritten),
            unsafe_allow_html=True
        )
    else:
        st.caption("변환 버튼을 누르면 결과가 여기에 표시됩니다.")

    st.markdown("</div>", unsafe_allow_html=True)

run = st.button("변환 실행")

# -----------------------------
# Run Logic
# -----------------------------
if run and api_key and original_text.strip():
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

        st.session_state.rewritten = data.get("rewritten_text", "")
