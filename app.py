import os
import json
import re
import difflib
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple

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
# Constants / Options
# -----------------------------
PERSONA_OPTIONS = ["대학생", "취준생", "기획자", "마케팅/콘텐츠 담당자", "연구/학술", "기타(직접 입력)"]

MAJOR_PURPOSES = {
    "자소서/면접": ["자기소개", "지원동기", "직무역량", "성격/가치관", "갈등/실패", "면접 1분 스피치"],
    "기획/비즈니스": ["서비스 기획서", "PRD", "원페이저", "제안서", "회의록→액션아이템", "요약/브리핑"],
    "SNS/콘텐츠": ["인스타 캡션", "릴스/쇼츠 대본", "블로그 글", "유튜브 스크립트", "홍보문구(카피)"],
    "발표/프레젠테이션": ["발표 대본", "슬라이드용 요약", "Q&A 예상답변", "피치덱 내러티브"],
    "학술/논문": ["서론", "관련연구", "방법", "결과", "논의/결론", "초록(ABSTRACT)"],
    "기타": ["요약", "공식 이메일", "공지문", "설득문", "보고서"]
}

TONE = ["격식체", "보통", "친근한", "단호한", "유머러스", "감성적인", "차분한", "열정적인"]
STYLE = ["간결", "설득형", "스토리텔링", "논리형", "데이터/근거 중심", "문학적(은유/이미지)"]
AUDIENCE = ["평가자/면접관", "팀/동료", "일반 대중", "고객/사용자", "교수/연구자", "투자자"]

LENGTH_PRESET = {
    "짧게": {"target_chars": 600, "desc": "핵심만 압축"},
    "보통": {"target_chars": 1200, "desc": "균형 있게"},
    "길게": {"target_chars": 2200, "desc": "맥락/근거 포함"},
    "아주 길게": {"target_chars": 3500, "desc": "상세 버전"}
}

# -----------------------------
# Helpers: diff highlight
# -----------------------------
def _tokenize_for_diff(text: str) -> List[str]:
    # Preserve Korean/English words + punctuation as separate tokens
    # This gives nicer highlighting than per-character.
    return re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)

def render_diff_html(original: str, revised: str) -> str:
    """
    Returns HTML where additions in revised are highlighted with <mark>,
    deletions are not shown (since we're displaying revised), but we can optionally show them.
    """
    a = _tokenize_for_diff(original)
    b = _tokenize_for_diff(revised)
    sm = difflib.SequenceMatcher(a=a, b=b)

    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        chunk = b[j1:j2]
        if tag == "equal":
            out.append(" ".join(chunk))
        elif tag in ("replace", "insert"):
            out.append(f"<mark>{' '.join(chunk)}</mark>")
        elif tag == "delete":
            # deletion in revised -> nothing to add
            pass

    html = " ".join(out)
    # Fix spacing around punctuation a bit
    html = html.replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
    html = html.replace(" )", ")").replace("( ", "(")
    html = html.replace(" :", ":").replace(" ;", ";")
    return f"<div style='line-height:1.8; font-size: 0.98rem;'>{html}</div>"

def basic_change_stats(original: str, revised: str) -> Dict[str, Any]:
    a = _tokenize_for_diff(original)
    b = _tokenize_for_diff(revised)
    sm = difflib.SequenceMatcher(a=a, b=b)
    inserts = replaces = deletes = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "insert":
            inserts += (j2 - j1)
        elif tag == "delete":
            deletes += (i2 - i1)
        elif tag == "replace":
            replaces += max(i2 - i1, j2 - j1)
    return {
        "원본 토큰 수": len(a),
        "결과 토큰 수": len(b),
        "추가/강조 토큰(대략)": inserts,
        "교체 토큰(대략)": replaces,
        "삭제 토큰(대략)": deletes,
        "변경률(대략)": round((inserts + replaces + deletes) / max(1, len(a)) * 100, 1)
    }

# -----------------------------
# OpenAI caller (supports openai>=1.0)
# -----------------------------
def call_openai(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.5
) -> str:
    """
    Uses the OpenAI Python SDK (v1+). If not available, raise a helpful error.
    """
    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError(
            "openai 패키지가 필요합니다. `pip install openai` 후 실행하세요."
        ) from e

    client = OpenAI(api_key=api_key)

    # Prefer Responses API if available (OpenAI SDK v1)
    # We'll keep it simple and robust: request plain text JSON.
    resp = client.responses.create(
        model=model,
        temperature=temperature,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    return resp.output_text

def safe_json_loads(text: str) -> Dict[str, Any]:
    """
    Extract JSON object from a possibly messy output.
    """
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to extract JSON block
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        block = m.group(0)
        try:
            return json.loads(block)
        except Exception:
            pass

    # Give fallback structure
    return {
        "rewritten_text": text,
        "change_points": ["(모델 JSON 파싱 실패) 출력 텍스트를 그대로 표시했습니다."],
        "suggested_repurposes": [],
        "reference_suggestions": [],
        "detected_original_traits": []
    }

# -----------------------------
# Prompt builder (core requirements from PDF)
# -----------------------------
def build_prompts(payload: Dict[str, Any]) -> Tuple[str, str]:
    """
    System: editor role (per PDF)
    User: includes constraints & sliders
    """
    system_prompt = (
        "너는 '글을 대신 써주는 AI'가 아니라, "
        "'같은 내용을 서로 다른 목적의 콘텐츠로 재구성해주는 편집자' 역할이다. "
        "원본에 없는 새로운 경험/사실을 만들지 말고, 사실관계와 핵심 경험은 유지하라. "
        "목적에 부합하지 않는 감정 표현/설명은 축약 또는 제거할 수 있다. "
        "선택된 목적의 독자(평가자/대중/교수 등)를 상정해 구조와 문체를 조정하라. "
        "출력은 반드시 JSON 단일 객체로만 반환하라(설명 텍스트 금지)."
    )

    # Strong steering: major/minor purpose, persona, custom traits, tone/style/audience
    user_prompt = f"""
[원본 텍스트]
{payload["original_text"]}

[사용자 프로필]
- 대표 특성(선택): {payload["persona"]}
- 기타(직업/특성): {payload["custom_persona"]}
- 성별: {payload["gender"]}
- 나이: {payload["age"]}

[목적 설정]
- 대목적: {payload["major_purpose"]}
- 소목적: {payload["minor_purpose"]}

[문체/어조/감성]
- 톤(말투): {payload["tone"]}
- 스타일(전개): {payload["style"]}
- 독자(타깃): {payload["audience"]}

[분량]
- 목표 글자수(대략): {payload["target_chars"]}자

[반드시 지켜라]
1) 원본에 없는 새로운 사실/경험/수치/성과/기관명을 추가하지 말 것.
2) 원본 내용 중 '핵심 메시지'는 보존하되, 목적에 맞게 구조/강조점을 바꿀 것.
3) 기타(직업/특성) 입력을 결과에 구체적으로 반영할 것(문체/포인트/어휘 선택에 반영).
4) 결과물 외에, 원본 대비 '강화/약화/삭제/재배치'된 핵심 포인트를 정확히 짚을 것.
5) 원본 텍스트의 성격을 분석해, 추가로 활용 가능한 목적(2~4개)을 추천할 것.

[추가 요구: 정확성/자료조사(해당 시)]
- 만약 대목적이 '학술/논문' 또는 '자소서/면접'이면,
  (a) 사용자가 나중에 확인/인용할 수 있도록 '참고자료 후보(키워드/출처 유형/검증 팁)'를 제안하라.
  (b) 지금은 외부 웹페이지 내용을 단정적으로 인용하지 말고, '확인 필요'로 표시하라.

[출력 JSON 스키마]
{{
  "rewritten_text": "목적에 맞게 재구성된 결과물(문단 포함)",
  "change_points": [
    "원본 대비 변경 포인트 요약 1",
    "요약 2",
    "요약 3"
  ],
  "detected_original_traits": [
    "원본 텍스트의 성격/톤/서사 구조 특징 1~5개"
  ],
  "suggested_repurposes": [
    {{
      "major_purpose": "추천 대목적",
      "minor_purpose": "추천 소목적",
      "why": "추천 이유(1~2문장)"
    }}
  ],
  "reference_suggestions": [
    {{
      "use_case": "학술/자소서 등",
      "keywords": ["검색 키워드1", "키워드2"],
      "source_types": ["DBpia", "Google Scholar", "링커리어", "공식 통계/보고서 등"],
      "verification_tips": ["검증 팁 1", "팁 2"]
    }}
  ]
}}
"""
    return system_prompt, user_prompt

# -----------------------------
# UI
# -----------------------------
st.title("🛠️ RePurpose — 목적 기반 텍스트 변환")
st.caption("원본 텍스트를 목적(자소서·기획·SNS·발표·학술 등)에 맞게 재구성하고, 변경 포인트와 재활용 추천까지 제공합니다.")

with st.sidebar:
    st.header("⚙️ 설정")

    api_key = st.text_input("OpenAI API Key", type="password", help="예: sk-... (키는 저장되지 않습니다)")
    model = st.selectbox("모델", ["gpt-4.1-mini", "gpt-4o-mini", "gpt-4.1"], index=0)

    st.divider()

    persona = st.selectbox("사용자 특성", PERSONA_OPTIONS, index=0)
    custom_persona = ""
    if persona == "기타(직접 입력)":
        custom_persona = st.text_input("기타(직업/특성) 직접 입력", placeholder="예: 스타트업 PM 지망, 데이터 기반 글 선호, 포트폴리오용 톤")
    else:
        custom_persona = st.text_input("추가 특성(선택)", placeholder="예: 지원 직무, 업계, 강점/약점, 선호하는 표현 등")

    st.divider()

    major_purpose = st.selectbox("대목적", list(MAJOR_PURPOSES.keys()), index=0)
    minor_purpose = st.selectbox("소목적", MAJOR_PURPOSES[major_purpose], index=0)

    st.divider()

    tone = st.selectbox("말투/톤", TONE, index=1)
    style = st.selectbox("스타일", STYLE, index=1)
    audience = st.selectbox("독자(타깃)", AUDIENCE, index=0)

    st.divider()

    gender = st.selectbox("성별", ["미입력", "남성", "여성", "기타/응답거부"], index=0)
    age = st.number_input("나이", min_value=0, max_value=120, value=0, help="모르면 0으로 둬도 됨")

    st.divider()

    length_key = st.select_slider(
        "분량",
        options=list(LENGTH_PRESET.keys()),
        value="보통",
        help="목표 글자수는 '대략'이며, 내용에 따라 약간 달라질 수 있어요."
    )
    target_chars = LENGTH_PRESET[length_key]["target_chars"]

    temperature = st.slider("창의성(temperature)", 0.0, 1.0, 0.5, 0.1)

st.write("")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📥 원본 텍스트")
    original_text = st.text_area(
        "원본을 붙여넣으세요",
        height=320,
        placeholder="여기에 원본 텍스트를 입력하세요..."
    )

with col2:
    st.subheader("🚀 실행")
    run = st.button("목적에 맞게 변환하기", type="primary", use_container_width=True)

# -----------------------------
# Run
# -----------------------------
if run:
    if not api_key:
        st.error("OpenAI API Key를 입력해 주세요.")
        st.stop()
    if not original_text.strip():
        st.error("원본 텍스트를 입력해 주세요.")
        st.stop()

    payload = {
        "original_text": original_text.strip(),
        "persona": persona,
        "custom_persona": (custom_persona or "").strip(),
        "gender": gender,
        "age": int(age),
        "major_purpose": major_purpose,
        "minor_purpose": minor_purpose,
        "tone": tone,
        "style": style,
        "audience": audience,
        "target_chars": target_chars
    }

    system_prompt, user_prompt = build_prompts(payload)

    with st.spinner("변환 중..."):
        try:
            raw = call_openai(
                api_key=api_key,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature
            )
        except Exception as e:
            st.error(f"모델 호출 실패: {e}")
            st.stop()

    data = safe_json_loads(raw)

    rewritten = (data.get("rewritten_text") or "").strip()
    change_points = data.get("change_points") or []
    detected_traits = data.get("detected_original_traits") or []
    suggested_repurposes = data.get("suggested_repurposes") or []
    reference_suggestions = data.get("reference_suggestions") or []

    if not rewritten:
        st.warning("결과 텍스트가 비어 있습니다. 원본이 너무 짧거나 설정이 과도할 수 있어요.")
        st.stop()

    st.divider()

    # Output area
    left, right = st.columns([1.2, 0.8])

    with left:
        st.subheader("✅ 변환 결과 (하이라이트)")
        diff_html = render_diff_html(original_text, rewritten)
        st.markdown(
            """
            <style>
            mark { background-color: #FFF3A3; padding: 0.12em 0.22em; border-radius: 0.25em; }
            </style>
            """,
            unsafe_allow_html=True
        )
        st.markdown(diff_html, unsafe_allow_html=True)

        with st.expander("📄 변환 결과(복사용 원문)"):
            st.text_area("Rewritten", rewritten, height=260)

    with right:
        st.subheader("🔎 변경 포인트 요약")
        if change_points:
            for i, cp in enumerate(change_points[:6], 1):
                st.write(f"{i}. {cp}")
        else:
            st.write("- (모델 요약 없음)")

        st.subheader("📊 변경 통계(대략)")
        stats = basic_change_stats(original_text, rewritten)
        for k, v in stats.items():
            st.write(f"- **{k}**: {v}")

        if detected_traits:
            st.subheader("🧠 원본 텍스트 성격 분석")
            for t in detected_traits[:6]:
                st.write(f"- {t}")

    st.divider()

    # Recommendations
    st.subheader("💡 추가 재활용 추천")
    if suggested_repurposes:
        for rec in suggested_repurposes[:4]:
            mp = rec.get("major_purpose", "—")
            sp = rec.get("minor_purpose", "—")
            why = rec.get("why", "")
            st.write(f"**{mp} → {sp}**")
            if why:
                st.caption(why)
    else:
        st.caption("추천이 비어 있습니다. (원본이 짧거나 목적이 매우 특정한 경우 그럴 수 있어요.)")

    # Reference suggestions (only show if relevant or if present)
    if reference_suggestions:
        st.subheader("📚 참고자료 후보/키워드(검증용)")
        st.caption("※ 아래는 '인용'이 아니라, 사용자가 직접 확인/검증할 수 있도록 돕는 후보입니다.")
        for rs in reference_suggestions[:3]:
            use_case = rs.get("use_case", "")
            keywords = rs.get("keywords", [])
            source_types = rs.get("source_types", [])
            tips = rs.get("verification_tips", [])

            with st.expander(f"🔗 {use_case or '참고자료 추천'}"):
                if keywords:
                    st.write("**검색 키워드**")
                    st.write(", ".join(keywords))
                if source_types:
                    st.write("**추천 출처 유형**")
                    st.write(", ".join(source_types))
                if tips:
                    st.write("**검증 팁**")
                    for tip in tips:
                        st.write(f"- {tip}")

    # Debug
    with st.expander("🧩 원본 모델 JSON(디버그)"):
        st.code(raw, language="json")
