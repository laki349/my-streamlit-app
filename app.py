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
    page_title="REPURPOSE | 목적 기반 텍스트 변환",
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
ss_init("last_original", "")
ss_init("last_run_context", {})  # 어디서 돌렸는지(major/minor/mode) 기록용(설명/디버그)
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

def normalize_rewritten(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value

    # dict -> sections면 합치고, 아니면 json dump
    if isinstance(value, dict):
        if isinstance(value.get("sections"), list):
            parts = []
            for sec in value["sections"]:
                if not isinstance(sec, dict):
                    continue
                h = (sec.get("heading") or "").strip()
                c = (sec.get("content") or sec.get("text") or "").strip()
                if h and c:
                    parts.append(f"### {h}\n{c}")
                elif c:
                    parts.append(c)
            return "\n\n".join(parts).strip()
        return json.dumps(value, ensure_ascii=False, indent=2)

    # list면 줄바꿈으로
    if isinstance(value, list):
        return "\n".join([str(v) for v in value]).strip()

    return str(value)

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

def render_result_panel(original_text: str, rewritten: str, data: Dict[str, Any], major: str, minor: str):
    """
    작성 탭/레퍼런스 탭 어디서든 동일한 결과 UI를 재사용하기 위한 패널 렌더러.
    (기존 작성 탭 UI 구성 그대로 재사용)
    """
    original_text = (original_text or "").strip()
    rewritten = (rewritten or "").strip()
    data = data or {}

    if not (original_text and rewritten):
        st.caption("변환 실행 후 결과가 표시됩니다.")
        return

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
# SNS Marketing Helpers (NEW)
# - 레퍼런스 텍스트에서 캡션/대본 스타일 특징 분석
# - 분석 결과를 프롬프트에 넣어 "결"을 맞추는 생성
# ============================================================

def clamp_text(t: str, max_chars: int = 12000) -> str:
    t = (t or "").strip()
    return t[:max_chars]

def split_paragraphs(text: str) -> List[str]:
    paras = re.split(r"\n\s*\n", (text or "").strip())
    return [p.strip() for p in paras if p.strip()]

def rough_sentence_split(text: str) -> List[str]:
    # 한국어/영어 혼합 대응: 문장부호 + 줄바꿈 기반
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return []
    parts = re.split(r"(?<=[\.\!\?\。])\s+|(?<=[다요죠]\.)\s+|\n+", t)
    parts = [p.strip() for p in parts if p.strip()]
    return parts

def analyze_sns_style(reference_text: str) -> Dict[str, Any]:
    """
    레퍼런스에서 SNS 톤/구조 특징을 뽑아내는 간단한 휴리스틱 분석기
    """
    ref = (reference_text or "").strip()
    if not ref:
        return {
            "hashtag_count": 0,
            "emoji_density": 0.0,
            "avg_sentence_len": 0,
            "avg_paragraph_len": 0,
            "cta_phrases": [],
            "structure_guess": [],
            "tone_guess": "보통",
            "platform_hint": "unknown"
        }

    emojis = re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", ref)
    hashtag = re.findall(r"#\w+", ref)
    sentences = rough_sentence_split(ref)
    paras = split_paragraphs(ref)

    avg_sentence_len = int(sum(len(s) for s in sentences) / max(1, len(sentences)))
    avg_paragraph_len = int(sum(len(p) for p in paras) / max(1, len(paras)))
    emoji_density = round(len(emojis) / max(1, len(ref)), 4)

    # CTA 추정 (한국/인스타/블로그 공통)
    cta_candidates = [
        "저장", "공유", "팔로우", "댓글", "DM", "문의", "링크", "프로필", "예약",
        "지금", "바로", "확인", "참고", "추천", "방문", "체험"
    ]
    found_cta = []
    for c in cta_candidates:
        if c in ref:
            found_cta.append(c)
    found_cta = list(dict.fromkeys(found_cta))[:8]

    # 구조 추정: 후킹/정보/후기/CTA/해시태그
    structure = []
    # 첫 문장이 짧고 감탄/질문이면 후킹
    if sentences:
        first = sentences[0]
        if len(first) <= 40 or "?" in first or "!" in first:
            structure.append("후킹(짧은 첫 문장/질문/감탄)")
    if any(k in ref for k in ["가격", "메뉴", "위치", "영업", "주차", "웨이팅", "예약", "시간"]):
        structure.append("정보(가격/위치/운영/팁)")
    if any(k in ref for k in ["맛", "식감", "분위기", "서비스", "재방문", "추천"]):
        structure.append("후기(경험 기반 평가)")
    if found_cta:
        structure.append("CTA(저장/팔로우/문의 등)")
    if hashtag:
        structure.append("해시태그")

    # 톤 추정
    # 존댓말/친근/단호 대충 분류
    tone_guess = "보통"
    if re.search(r"(해요|했어요|입니다|합니다|주세요)", ref):
        tone_guess = "친근한" if "해요" in ref or "했어요" in ref else "격식체"
    if "무조건" in ref or "필수" in ref:
        tone_guess = "단호한"

    # 플랫폼 힌트
    platform_hint = "instagram" if len(hashtag) >= 3 or "릴스" in ref or "스토리" in ref else "blog"

    return {
        "hashtag_count": len(hashtag),
        "emoji_density": emoji_density,
        "avg_sentence_len": avg_sentence_len,
        "avg_paragraph_len": avg_paragraph_len,
        "cta_phrases": found_cta,
        "structure_guess": structure[:6],
        "tone_guess": tone_guess,
        "platform_hint": platform_hint
    }

def build_sns_generate_prompt(
    api_payload: Dict[str, Any],
    reference_text: str,
    style_profile: Dict[str, Any],
    platform: str,
    niche: str,
    goal: str,
    output_type: str,
    constraints: Dict[str, Any],
) -> Tuple[str, str]:
    """
    SNS 전용 생성 프롬프트 (캡션/대본)
    - reference_text: 레퍼런스(블로그 글/인스타 캡션/대본)
    - style_profile: analyze_sns_style 결과
    """
    ref = clamp_text(reference_text, 6500)
    sp = style_profile or {}

    # 사용자가 입력한 핵심 정보 (맛집/홍보에 유용한 필드)
    # api_payload["text"] = 사용자가 '원본'에 넣은 내용 (가게 소개/후기/메모 등)
    base_text = (api_payload.get("text") or "").strip()

    # constraints
    hashtag_mode = constraints.get("hashtag_mode", "자동(추천)")
    hashtag_count = int(constraints.get("hashtag_count", 8))
    emoji_level = constraints.get("emoji_level", "중간")
    cta_mode = constraints.get("cta_mode", "가볍게")
    length_mode = constraints.get("length_mode", "보통")
    custom_hashtags = (constraints.get("custom_hashtags") or "").strip()

    system = (
        "너는 SNS 마케팅 카피라이터 겸 숏폼 대본 작가다. "
        "주어진 원본을 바탕으로, 지정된 플랫폼/목표/니치에 맞게 캡션 또는 대본을 작성한다. "
        "레퍼런스가 있으면 그 문체/리듬/구조/표현 습관을 모사한다. "
        "단, 원본에 없는 사실(가격/주소/영업시간/예약 링크/수치)을 지어내지 마라. "
        "출력은 반드시 JSON만 반환한다."
    )

    user = f"""
[플랫폼]
{platform}

[니치/콘셉트]
{niche}

[마케팅 목표]
{goal}

[출력 타입]
{output_type}  # caption or script

[원본(사용자 입력)]
{base_text}

[레퍼런스(가능하면 모사)]
{ref if ref else "(레퍼런스 없음)"}

[레퍼런스 스타일 프로필]
- tone_guess: {sp.get("tone_guess")}
- structure_guess: {sp.get("structure_guess")}
- avg_sentence_len: {sp.get("avg_sentence_len")}
- emoji_density: {sp.get("emoji_density")}
- hashtag_count: {sp.get("hashtag_count")}
- cta_phrases: {sp.get("cta_phrases")}
- platform_hint: {sp.get("platform_hint")}

[작성 규칙]
- 플랫폼별 최적화:
  - instagram: 첫 2줄 후킹 강하게, 짧은 문장, 줄바꿈 적극, CTA 1개, 해시태그 포함 가능
  - blog: 소제목/문단 구성, 정보(메뉴/위치/팁) 정리, 과한 해시태그 금지
- 길이: {length_mode}
- 이모지: {emoji_level}
- CTA: {cta_mode}
- 해시태그: {hashtag_mode} (개수 목표: {hashtag_count})
- 사용자가 직접 입력한 해시태그: {custom_hashtags if custom_hashtags else "(없음)"}
- hashtag_mode가 "직접 입력"이면, 위 해시태그를 결과 맨 아래에 그대로 붙여라(수정/재생성 금지).

[출력 JSON 스키마]
{{
  "rewritten_text": "",              // 생성 결과(캡션 또는 대본)
  "change_points": [],               // 생성/수정 핵심 포인트(문장)
  "highlight_reasons": [],           // 왜 이렇게 썼는지(짧은 bullet)
  "detected_original_traits": [],    // 원본 특징(짧은 bullet)
  "suggested_repurposes": []         // 재활용 추천
}}
"""
    return system, user

def run_sns_generation(
    api_key: str,
    model: str,
    temperature: float,
    base_payload: Dict[str, Any],
    platform: str,
    niche: str,
    goal: str,
    output_type: str,
    constraints: Dict[str, Any],
) -> Dict[str, Any]:
    """
    SNS 생성 실행: 레퍼런스 + 스타일 분석 기반
    """
    ref_text = (st.session_state.reference_text or "").strip()
    style_profile = analyze_sns_style(ref_text) if ref_text else {}
    system, user = build_sns_generate_prompt(
        api_payload=base_payload,
        reference_text=ref_text,
        style_profile=style_profile,
        platform=platform,
        niche=niche,
        goal=goal,
        output_type=output_type,
        constraints=constraints,
    )
    raw = call_openai(api_key, model, system, user, temperature)
    data = safe_json(raw)
    return data

# ============================================================
# Template & Library Helpers (NEW/REFINED)
# - 레퍼런스 -> 템플릿 추출 (LLM optional + fallback)
# - 템플릿 채움 리라이팅 (안정형)
# - 라이브러리 저장/불러오기
# ============================================================

def simple_structure_guess(text: str) -> Dict[str, Any]:
    t = (text or "").strip()
    if not t:
        return {"type": "unknown", "sections": [], "style_rules": {}}

    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    headings = []
    for ln in lines:
        if re.match(r"^(#{1,4}\s+)", ln) or re.match(r"^(\d+[\.\)]\s+)", ln) or re.match(r"^(\(\d+\)\s+)", ln):
            headings.append(ln)

    lower = t.lower()
    is_paperish = any(k in lower for k in ["abstract", "introduction", "method", "results", "conclusion"]) or any(k in t for k in ["본 연구", "본 논문", "연구 목적"])
    is_resumeish = any(k in t for k in ["지원동기", "직무", "역량", "경험", "성과", "프로젝트", "팀", "협업", "문제", "해결"])

    if headings:
        sections = [{"heading": h.replace("#", "").strip(), "slot": f"sec_{i+1}", "guidance": ""} for i, h in enumerate(headings[:8])]
        return {
            "type": "paper" if is_paperish else ("resume" if is_resumeish else "generic"),
            "sections": sections,
            "style_rules": {
                "heading_style": "use_detected_headings",
                "bullet_style": "dash",
                "tone_hint": "match_reference",
                "signature_patterns": []
            }
        }

    if is_paperish:
        return {
            "type": "paper",
            "sections": [
                {"heading": "배경", "slot": "background", "guidance": "주제의 맥락과 중요성"},
                {"heading": "문제/한계", "slot": "problem", "guidance": "기존 접근의 한계"},
                {"heading": "연구 공백", "slot": "gap", "guidance": "왜 아직 해결되지 않았는지"},
                {"heading": "목적/기여", "slot": "purpose", "guidance": "무엇을 제안/검증하는지"},
                {"heading": "시사점", "slot": "implication", "guidance": "의의/적용/향후 연구"},
            ],
            "style_rules": {"heading_style": "###", "bullet_style": "none", "tone_hint": "academic", "signature_patterns": []}
        }

    if is_resumeish:
        return {
            "type": "resume",
            "sections": [
                {"heading": "상황", "slot": "situation", "guidance": "문제/맥락을 2~3문장으로"},
                {"heading": "행동", "slot": "action", "guidance": "내 역할/행동/의사결정/협업"},
                {"heading": "성과", "slot": "result", "guidance": "수치/결과/임팩트 (없으면 정성적 효과)"},
                {"heading": "배운 점", "slot": "learning", "guidance": "인사이트/원리/재현성"},
                {"heading": "직무 연결", "slot": "fit", "guidance": "지원 직무/회사에 기여 연결"},
            ],
            "style_rules": {"heading_style": "###", "bullet_style": "dash", "tone_hint": "professional", "signature_patterns": []}
        }

    return {
        "type": "generic",
        "sections": [
            {"heading": "도입", "slot": "intro", "guidance": "핵심 메시지"},
            {"heading": "핵심 내용", "slot": "body", "guidance": "논리 전개"},
            {"heading": "마무리", "slot": "close", "guidance": "요약 + 다음 행동"},
        ],
        "style_rules": {"heading_style": "###", "bullet_style": "none", "tone_hint": "match_reference", "signature_patterns": []}
    }


def build_template_prompt(reference_text: str) -> Tuple[str, str]:
    system = (
        "너는 글 구조 분석가다. 입력된 레퍼런스 텍스트의 구조를 템플릿(JSON)으로 추출하라. "
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
    "heading_style": "### | numbering | none",
    "bullet_style": "dash | dot | none",
    "sentence_rhythm": "짧게/보통/길게 + 예시(간단)",
    "tone_hint": "academic/professional/friendly",
    "signature_patterns": ["반복 표현 패턴 2~5개"]
  }}
}}
"""
    return system, user


def extract_template(api_key: str, model: str, reference_text: str) -> Dict[str, Any]:
    ref = (reference_text or "").strip()
    if not ref:
        return {"type": "unknown", "sections": [], "style_rules": {}}

    if not api_key.strip():
        return simple_structure_guess(ref)

    try:
        system, user = build_template_prompt(ref)
        raw = call_openai(api_key, model, system, user, temperature=0.2)
        tpl = safe_json(raw)
        if isinstance(tpl, dict) and tpl.get("sections"):
            return tpl
    except Exception:
        pass

    return simple_structure_guess(ref)


def build_prompt_template_fill(p: Dict[str, Any], template: Dict[str, Any]) -> Tuple[str, str]:
    template = template or {"type": "generic", "sections": [], "style_rules": {}}
    sections = (template.get("sections") or [])[:10]
    rules = template.get("style_rules") or {}

    company = (p.get("company") or "").strip()
    role = (p.get("role") or "").strip()
    anchor = ""
    if company or role:
        anchor = f"""
[지원 정보]
- 지원 회사: {company or "(미기입)"}
- 지원 직무: {role or "(미기입)"}
- 회사/직무는 표현 방향에만 사용하고, 사실은 원문에서만 가져와라.
"""

    system = (
        "너는 목적 기반 리라이팅 전문가다. "
        "입력된 원문을 '주어진 템플릿 구조'에 맞춰 재작성하라. "
        "원문의 사실(회사명/기간/수치/역할/성과)은 변경 금지. "
        "출력은 반드시 JSON만."
    )

    user = f"""
{anchor}

[템플릿]
{json.dumps({'type': template.get('type','generic'), 'sections': sections, 'style_rules': rules}, ensure_ascii=False, indent=2)}

[원문]
{p["text"]}

[목적]
{p["major"]} → {p["minor"]}

[편집 조건]
편집 강도: {EDIT_INTENSITY[p["edit"]]}
톤: {p["tone"]}, 스타일: {p["style"]}, 독자: {p["audience"]}
분량: {p["length"]}자 근처 (±15%)

[작성 규칙]
- 섹션 헤딩을 템플릿대로 사용(heading_style)
- guidance를 충족
- signature_patterns가 있으면 리듬만 반영(과하게 복붙 금지)
- 원문에 없는 수치/기간/주소/가격/링크를 지어내지 마라

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


def library_add(name: str, major: str, minor: str, ref_text: str, ref_meta: Dict[str, Any], template: Dict[str, Any]):
    item = {
        "name": name,
        "major": major,
        "minor": minor,
        "text": ref_text,
        "meta": ref_meta or {},
        "template": template or {}
    }
    st.session_state.reference_library.append(item)


def library_items_for_major(major: str) -> List[Dict[str, Any]]:
    return [it for it in (st.session_state.reference_library or []) if it.get("major") == major]


def render_library_label(it: Dict[str, Any]) -> str:
    nm = it.get("name", "Untitled")
    mn = it.get("minor", "")
    return f"{nm}  ·  {mn}"
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

def run_transform(
    *,
    api_key: str,
    model: str,
    temperature: float,
    payload: Dict[str, Any],
    mode: str = "reference",  # "reference" | "template"
    template: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], str]:
    """
    공용 변환 실행기.
    - mode="reference": build_prompt(payload)
    - mode="template": build_prompt_template_fill(payload, template)
    실행 결과를 session_state에 일관되게 저장한다.
    """
    if mode == "template":
        ref_text = (payload.get("reference_text") or st.session_state.reference_text or "")
        tpl = template or simple_structure_guess(ref_text)
        sys, usr = build_prompt_template_fill(payload, tpl)
    else:
        sys, usr = build_prompt(payload)

    raw = call_openai(api_key, model, sys, usr, temperature)
    data = safe_json(raw)
    val = data.get("rewritten_text", None)
    rewritten = normalize_rewritten(val if val is not None else data)

    # ✅ 공용 저장 (어디서 실행해도 작성탭/다른 탭에서 동일하게 결과 접근 가능)
    st.session_state.last_raw = raw
    st.session_state.last_data = data
    st.session_state.last_rewritten = rewritten
    st.session_state.last_original = (payload.get("text") or "").strip()
    st.session_state.last_run_context = context or {}

    return data, rewritten

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
  <div class="title">REPURPOSE — 목적 기반 텍스트 리라이팅 워크스페이스</div>
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

                    with st.spinner("변환 중..."):
                        data, rewritten = run_transform(
                            api_key=api_key,
                            model=model,
                            temperature=temperature,
                            payload=payload,
                            mode="reference",
                            context={
                                "where": "write_tab",
                                "mode": "reference",
                                "major": major,
                                "minor": minor
                            }
                        )

            data = st.session_state.last_data or {}
            rewritten = st.session_state.last_rewritten or ""
            original_for_view = (original_text or "").strip() or (st.session_state.last_original or "").strip()

            if isinstance(rewritten, str) and rewritten.strip() and original_for_view.strip():
                st.markdown("**하이라이트(변경점 표시)**")
                st.markdown(render_diff_html(original_for_view, rewritten), unsafe_allow_html=True)

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
                change_points = data.get("change_points") or derive_change_points(original_for_view, rewritten)
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
        # =====================================================
        # 자소서/면접 전용: 단계형 UX
        # Step 1) 레퍼런스 설정
        # Step 2) 템플릿 생성/저장(라이브러리)
        # Step 3) 변환 실행(기본 모사 / 템플릿 채움) + A/B
        # =====================================================
        with st.container(border=True):
            st.subheader("🏢 자소서 템플릿 워크플로우")
            st.caption("자소서/면접 목적에서만 보입니다. 필요한 기능만 단계적으로 노출합니다.")

            step = st.radio("단계", ["1) 레퍼런스 설정", "2) 템플릿/라이브러리", "3) 변환/A·B 비교"], horizontal=True)

        # ——————————————
        # Step 1: reference set
        # ——————————————
        if step == "1) 레퍼런스 설정":
            with st.container(border=True):
                st.markdown("### 1) 합격 자소서 레퍼런스 설정")
                c1, c2 = st.columns([1, 1], gap="large")

                with c1:
                    st.markdown("#### 지원 정보")
                    st.session_state.company_target = st.text_input("지원 회사", value=st.session_state.company_target, placeholder="예: 삼성전자")
                    st.session_state.role_target = st.text_input("지원 직무", value=st.session_state.role_target, placeholder="예: 데이터분석 / SW / PM")
                    st.info("회사/직무는 표현 방향에만 사용합니다(사실/성과는 원문에서만).")

                with c2:
                    st.markdown("#### 레퍼런스 가져오기")
                    ref_mode = st.radio("방식", ["URL", "PDF", "직접 붙여넣기"], horizontal=True)

                    if ref_mode == "URL":
                        url = st.text_input("합격 자소서 URL", placeholder="공개된 합격 자소서/블로그 글 URL")
                        if st.button("가져오기", key="resume_ref_url"):
                            with st.spinner("추출 중..."):
                                txt, meta = fetch_url_text(url.strip())
                            if txt.strip():
                                st.session_state.reference_text = txt
                                st.session_state.reference_meta = meta
                                st.success("레퍼런스를 설정했습니다.")
                            else:
                                st.warning("추출 실패(차단/로그인 가능). PDF 업로드나 직접 붙여넣기를 추천.")
                    elif ref_mode == "PDF":
                        pdf = st.file_uploader("PDF 업로드", type=["pdf"], key="resume_pdf")
                        if st.button("PDF 텍스트 추출", key="resume_pdf_extract") and pdf is not None:
                            with st.spinner("PDF 추출 중..."):
                                txt = extract_pdf_text(pdf.read())
                            if txt.strip():
                                st.session_state.reference_text = txt
                                st.session_state.reference_meta = {"source": "pdf", "name": pdf.name}
                                st.success("레퍼런스를 설정했습니다.")
                            else:
                                st.warning("PDF 추출 실패")
                    else:
                        pasted = st.text_area("레퍼런스 텍스트", height=200, key="resume_paste")
                        if st.button("레퍼런스로 설정", key="resume_apply"):
                            st.session_state.reference_text = pasted or ""
                            st.session_state.reference_meta = {"source": "pasted"}
                            st.success("레퍼런스를 설정했습니다.")

                st.divider()
                st.markdown("#### 현재 레퍼런스 미리보기")
                if st.session_state.reference_text.strip():
                    st.text_area("preview", st.session_state.reference_text[:7000], height=260, label_visibility="collapsed")
                    colx, coly = st.columns(2)
                    with colx:
                        if st.button("레퍼런스 비우기", key="resume_clear"):
                            st.session_state.reference_text = ""
                            st.session_state.reference_meta = {}
                            st.success("레퍼런스를 비웠습니다.")
                    with coly:
                        st.caption("다음 단계에서 템플릿을 만들 수 있어요.")
                else:
                    st.info("레퍼런스를 설정하면 다음 단계에서 템플릿 생성이 가능합니다.")

        # -----------------------------
        # Step 2: template & library
        # -----------------------------
        elif step == "2) 템플릿/라이브러리":
            with st.container(border=True):
                st.markdown("### 2) 템플릿 생성 & 라이브러리 저장")

                if not st.session_state.reference_text.strip():
                    st.warning("먼저 1단계에서 레퍼런스를 설정해줘.")
                else:
                    a, b = st.columns([1, 1], gap="large")
                    with a:
                        st.markdown("#### 템플릿 생성")
                        if st.button("레퍼런스로 템플릿 만들기", key="resume_make_tpl"):
                            with st.spinner("템플릿 분석 중..."):
                                tpl = extract_template(api_key, model, st.session_state.reference_text)
                            st.session_state.reference_template = tpl or {}
                            st.success("템플릿을 생성했습니다.")

                        tpl = st.session_state.reference_template or {}
                        if tpl:
                            st.text_area("템플릿 미리보기", json.dumps(tpl, ensure_ascii=False, indent=2), height=260)
                        else:
                            st.caption("아직 템플릿이 없습니다. 버튼을 눌러 생성하세요.")

                    with b:
                        st.markdown("#### 라이브러리 저장/불러오기")
                        lib_name = st.text_input("저장 이름", placeholder="예: 삼성 합격 자소서 템플릿 A", key="resume_lib_name")
                        save_btn = st.button("현재 레퍼런스 저장", key="resume_lib_save")

                        if save_btn:
                            if not st.session_state.reference_template:
                                tpl = simple_structure_guess(st.session_state.reference_text)
                            else:
                                tpl = st.session_state.reference_template

                            library_add(
                                name=lib_name.strip() or f"자소서 템플릿 {len(st.session_state.reference_library)+1}",
                                major="자소서/면접",
                                minor=minor,
                                ref_text=st.session_state.reference_text,
                                ref_meta=st.session_state.reference_meta,
                                template=tpl
                            )
                            st.success("라이브러리에 저장했습니다.")

                        st.divider()
                        items = library_items_for_major("자소서/면접")
                        if items:
                            idx = st.selectbox("저장된 템플릿", list(range(len(items))), format_func=lambda i: render_library_label(items[i]), key="resume_pick")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("로드", key="resume_load"):
                                    it = items[idx]
                                    st.session_state.reference_text = it.get("text","")
                                    st.session_state.reference_meta = it.get("meta") or {}
                                    st.session_state.reference_template = it.get("template") or {}
                                    st.success("라이브러리 템플릿을 로드했습니다.")
                            with col2:
                                if st.button("삭제", key="resume_delete"):
                                    # 실제 저장 리스트에서 제거
                                    target = items[idx]
                                    st.session_state.reference_library.remove(target)
                                    st.success("삭제했습니다.")
                        else:
                            st.caption("저장된 자소서 레퍼런스가 없습니다.")

        # -----------------------------
        # Step 3: run + A/B
        # -----------------------------
        else:
            with st.container(border=True):
                st.markdown("### 3) 변환 실행 / A·B 비교")
                st.caption("작성 탭의 원본 텍스트를 기반으로 변환합니다. 레퍼런스 모사 vs 템플릿 채움 중 선택.")

                mode = st.radio("변환 방식", ["레퍼런스 모사(기존)", "템플릿 채움(안정적)"], horizontal=True)

                run_one = st.button("단일 변환 실행", key="resume_run_one")

                if run_one:
                    base_text = st.session_state.get("original_text", "").strip()
                    if not api_key.strip():
                        st.error("API Key를 입력해줘.")
                    elif not base_text:
                        st.error("작성 탭의 원본 텍스트를 먼저 입력해줘.")
                    else:
                        payload = {
                            "text": base_text,
                            "major": major,
                            "minor": minor,
                            "tone": tone,
                            "style": style,
                            "audience": audience,
                            "length": LENGTH_PRESET[length_key],
                            "edit": edit_level,
                            "reference_text": st.session_state.reference_text,
                            "company": st.session_state.company_target,
                            "role": st.session_state.role_target
                        }

                        with st.spinner("변환 중..."):
                            if mode == "템플릿 채움(안정적)":
                                tpl = st.session_state.reference_template or simple_structure_guess(st.session_state.reference_text)
                                data, rewritten = run_transform(
                                    api_key=api_key,
                                    model=model,
                                    temperature=temperature,
                                    payload=payload,
                                    mode="template",
                                    template=tpl,
                                    context={
                                        "where": "resume_step3_single",
                                        "mode": "template",
                                        "major": major,
                                        "minor": minor
                                    }
                                )
                            else:
                                data, rewritten = run_transform(
                                    api_key=api_key,
                                    model=model,
                                    temperature=temperature,
                                    payload=payload,
                                    mode="reference",
                                    context={
                                        "where": "resume_step3_single",
                                        "mode": "reference",
                                        "major": major,
                                        "minor": minor
                                    }
                                )

                        st.success("완료! 아래에서 바로 결과를 확인할 수 있어요.")

                st.divider()
                st.markdown("#### A/B 비교 (라이브러리 2개 이상 필요)")
                st.info(
    "A/B 비교는 **'원본 텍스트는 동일하게 두고'**, 라이브러리에서 선택한 **템플릿 A vs 템플릿 B**를 각각 적용해 "
    "결과를 나란히 보여주는 기능입니다.\n\n"
    "- 즉, **템플릿 구조/문체 규칙 차이**가 결과에 어떤 영향을 주는지 '템플릿 자체를 정확히 비교'할 수 있습니다.\n"
    "- 설정(톤/스타일/독자/분량/편집강도/temperature)은 동일하게 유지됩니다."
)
                items = library_items_for_major("자소서/면접")
                if len(items) < 2:
                    st.info("A/B 비교를 하려면 2단계에서 템플릿을 2개 이상 저장해줘.")
                else:
                    colA, colB, colRun = st.columns([1, 1, 1])
                    with colA:
                        idxA = st.selectbox("A", list(range(len(items))), format_func=lambda i: render_library_label(items[i]), key="abA_resume")
                    with colB:
                        idxB = st.selectbox("B", list(range(len(items))), format_func=lambda i: render_library_label(items[i]), key="abB_resume")
                    with colRun:
                        ab_btn = st.button("A/B 실행", key="ab_resume_run")

                    if ab_btn:
                        base_text = st.session_state.get("original_text", "").strip()
                        if not api_key.strip():
                            st.error("API Key를 입력해줘.")
                        elif not base_text:
                            st.error("작성 탭의 원본 텍스트를 먼저 입력해줘.")
                        else:
                            payload = {
                                "text": base_text,
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
                            itA, itB = items[idxA], items[idxB]
                            tplA = itA.get("template") or simple_structure_guess(itA.get("text",""))
                            tplB = itB.get("template") or simple_structure_guess(itB.get("text",""))

                            sysA, usrA = build_prompt_template_fill(payload, tplA)
                            sysB, usrB = build_prompt_template_fill(payload, tplB)

                            with st.spinner("A/B 변환 중..."):
                                rawA = call_openai(api_key, model, sysA, usrA, temperature)
                                rawB = call_openai(api_key, model, sysB, usrB, temperature)

                            dataA, dataB = safe_json(rawA), safe_json(rawB)

                            A_val = dataA.get("rewritten_text", None)
                            B_val = dataB.get("rewritten_text", None)

                            A_txt = normalize_rewritten(A_val if A_val is not None else dataA)
                            B_txt = normalize_rewritten(B_val if B_val is not None else dataB)
                            
                            ca, cb = st.columns(2, gap="large")
                            with ca:
                                with st.container(border=True):
                                    st.markdown("**A 결과 (템플릿 A 적용)**")
                                    st.text_area("A", A_txt, height=280, label_visibility="collapsed")
                                    st.download_button("A 다운로드", A_txt, file_name="result_A.txt")
                            with cb:
                                with st.container(border=True):
                                    st.markdown("**B 결과 (템플릿 B 적용)**")
                                    st.text_area("B", B_txt, height=280, label_visibility="collapsed")
                                    st.download_button("B 다운로드", B_txt, file_name="result_B.txt")
                                
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
        # =====================================================
        # 논문 전용: 단계형 UX
        # Step 1) 레퍼런스(초록/서론/논문) 설정
        # Step 2) 템플릿 생성/저장
        # Step 3) 변환 실행(특히 서론/결론 안정화)
        # =====================================================
        with st.container(border=True):
            st.subheader("📄 논문 템플릿 워크플로우")
            st.caption("학술/논문 목적에서만 보입니다. 서론/결론을 논문 톤으로 안정적으로 만들기 위해 템플릿 채움을 권장합니다.")
            step = st.radio(
                "단계",
                ["1) 레퍼런스 설정", "2) 템플릿/라이브러리", "3) 변환 실행"],
                horizontal=True,
                key="paper_step",
            )

        # -----------------------------
        # Step 1: reference set
        # -----------------------------
        if step == "1) 레퍼런스 설정":
            with st.container(border=True):
                st.markdown("### 1) 논문 레퍼런스 설정(초록/서론/관련연구)")
                ref_mode = st.radio("방식", ["URL", "PDF", "직접 붙여넣기"], horizontal=True, key="paper_ref_mode")

                if ref_mode == "URL":
                    url = st.text_input("논문 URL", placeholder="arXiv/오픈 논문 페이지/학회 페이지", key="paper_url")
                    if st.button("가져오기", key="paper_ref_url"):
                        with st.spinner("추출 중..."):
                            txt, meta = fetch_url_text(url.strip())
                        if txt.strip():
                            st.session_state.reference_text = txt
                            st.session_state.reference_meta = meta
                            st.success("레퍼런스를 설정했습니다.")
                        else:
                            st.warning("추출 실패(유료/차단 가능). PDF 업로드 또는 직접 붙여넣기를 추천.")

                elif ref_mode == "PDF":
                    pdf = st.file_uploader("PDF 업로드", type=["pdf"], key="paper_pdf")
                    if st.button("PDF 텍스트 추출", key="paper_pdf_extract") and pdf is not None:
                        with st.spinner("PDF 추출 중..."):
                            txt = extract_pdf_text(pdf.read())
                        if txt.strip():
                            st.session_state.reference_text = txt
                            st.session_state.reference_meta = {"source": "pdf", "name": pdf.name}
                            st.success("레퍼런스를 설정했습니다.")
                        else:
                            st.warning("PDF 추출 실패")

                else:
                    pasted = st.text_area("레퍼런스 텍스트", height=220, key="paper_paste")
                    if st.button("레퍼런스로 설정", key="paper_apply"):
                        st.session_state.reference_text = pasted or ""
                        st.session_state.reference_meta = {"source": "pasted"}
                        st.success("레퍼런스를 설정했습니다.")

                st.divider()
                st.markdown("#### 현재 레퍼런스 미리보기")
                if st.session_state.reference_text.strip():
                    st.text_area("preview", st.session_state.reference_text[:7000], height=260, label_visibility="collapsed", key="paper_preview")
                    if st.button("레퍼런스 비우기", key="paper_clear"):
                        st.session_state.reference_text = ""
                        st.session_state.reference_meta = {}
                        st.success("레퍼런스를 비웠습니다.")
                else:
                    st.info("레퍼런스를 설정하면 다음 단계에서 템플릿 생성이 가능합니다.")

        # -----------------------------
        # Step 2: template & library
        # -----------------------------
        elif step == "2) 템플릿/라이브러리":
            with st.container(border=True):
                st.markdown("### 2) 템플릿 생성 & 라이브러리 저장")

                if not st.session_state.reference_text.strip():
                    st.warning("먼저 1단계에서 레퍼런스를 설정해줘.")
                else:
                    a, b = st.columns([1, 1], gap="large")

                    with a:
                        st.markdown("#### 템플릿 생성")
                        if st.button("레퍼런스로 템플릿 만들기", key="paper_make_tpl"):
                            with st.spinner("템플릿 분석 중..."):
                                tpl = extract_template(api_key, model, st.session_state.reference_text)
                            st.session_state.reference_template = tpl or {}
                            st.success("템플릿을 생성했습니다.")

                        tpl = st.session_state.reference_template or {}
                        if tpl:
                            st.text_area("템플릿 미리보기", json.dumps(tpl, ensure_ascii=False, indent=2), height=260, key="paper_tpl_preview")
                        else:
                            st.caption("아직 템플릿이 없습니다. 버튼을 눌러 생성하세요.")

                    with b:
                        st.markdown("#### 라이브러리 저장/불러오기")
                        lib_name = st.text_input("저장 이름", placeholder="예: RL 논문 서론 템플릿 A", key="paper_lib_name")
                        save_btn = st.button("현재 레퍼런스 저장", key="paper_lib_save")

                        if save_btn:
                            tpl = st.session_state.reference_template or simple_structure_guess(st.session_state.reference_text)
                            library_add(
                                name=lib_name.strip() or f"논문 템플릿 {len(st.session_state.reference_library)+1}",
                                major="학술/논문",
                                minor=minor,
                                ref_text=st.session_state.reference_text,
                                ref_meta=st.session_state.reference_meta,
                                template=tpl
                            )
                            st.success("라이브러리에 저장했습니다.")

                        st.divider()
                        items = library_items_for_major("학술/논문")
                        if items:
                            idx = st.selectbox(
                                "저장된 템플릿",
                                list(range(len(items))),
                                format_func=lambda i: render_library_label(items[i]),
                                key="paper_pick"
                            )
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("로드", key="paper_load"):
                                    it = items[idx]
                                    st.session_state.reference_text = it.get("text", "")
                                    st.session_state.reference_meta = it.get("meta") or {}
                                    st.session_state.reference_template = it.get("template") or {}
                                    st.success("라이브러리 템플릿을 로드했습니다.")
                            with col2:
                                if st.button("삭제", key="paper_delete"):
                                    target = items[idx]
                                    st.session_state.reference_library.remove(target)
                                    st.success("삭제했습니다.")
                        else:
                            st.caption("저장된 논문 레퍼런스가 없습니다.")

        # -----------------------------
        # Step 3: run transform
        # -----------------------------
        else:
            with st.container(border=True):
                st.markdown("### 3) 변환 실행(논문)")
                st.caption("작성 탭의 원문 텍스트를 논문 톤으로 변환합니다. 템플릿 채움(안정적)을 권장합니다.")

                mode = st.radio(
                    "변환 방식",
                    ["레퍼런스 모사(기존)", "템플릿 채움(안정적)"],
                    horizontal=True,
                    key="paper_mode"
                )
                run_one = st.button("변환 실행", key="paper_run")

                if run_one:
                    base_text = st.session_state.get("original_text", "").strip()

                    if not api_key.strip():
                        st.error("API Key를 입력해줘.")
                    elif not base_text:
                        st.error("작성 탭의 원본 텍스트를 먼저 입력해줘.")
                    else:
                        payload = {
                            "text": base_text,
                            "major": major,
                            "minor": minor,
                            "tone": tone,
                            "style": style,
                            "audience": audience,
                            "length": LENGTH_PRESET[length_key],
                            "edit": edit_level,
                            "reference_text": st.session_state.reference_text
                        }

                        with st.spinner("변환 중..."):
                            if mode == "템플릿 채움(안정적)":
                                tpl = st.session_state.reference_template or simple_structure_guess(st.session_state.reference_text)
                                data, rewritten = run_transform(
                                    api_key=api_key,
                                    model=model,
                                    temperature=temperature,
                                    payload=payload,
                                    mode="template",
                                    template=tpl,
                                    context={
                                        "where": "paper_step3_single",
                                        "mode": "template",
                                        "major": major,
                                        "minor": minor
                                    }
                                )
                            else:
                                data, rewritten = run_transform(
                                    api_key=api_key,
                                    model=model,
                                    temperature=temperature,
                                    payload=payload,
                                    mode="reference",
                                    context={
                                        "where": "paper_step3_single",
                                        "mode": "reference",
                                        "major": major,
                                        "minor": minor
                                    }
                                )

                        st.success("완료! 아래에서 바로 결과를 확인할 수 있어요.")

                        st.divider()
                        st.markdown("#### ✅ 이번 실행 결과(바로 보기)")
                        render_result_panel(
                            original_text=st.session_state.last_original,
                            rewritten=st.session_state.last_rewritten,
                            data=st.session_state.last_data,
                            major=major,
                            minor=minor
                        )

            st.divider()
            st.subheader("📌 현재 레퍼런스 미리보기")
            if st.session_state.reference_text.strip():
                st.text_area("reference", st.session_state.reference_text[:7000], height=240, label_visibility="collapsed", key="paper_ref_preview_bottom")
                if st.button("레퍼런스 비우기", key="paper_clear_bottom"):
                    st.session_state.reference_text = ""
                    st.session_state.reference_meta = {}
                    st.success("레퍼런스를 비웠습니다.")
            else:
                st.caption("레퍼런스를 설정하면 여기에서 확인할 수 있어요.")
    elif major == "SNS/콘텐츠":
        # ===========================
        # SNS 전용 화면 (깔끔하게 3단 구성)
        # 1) 레퍼런스 가져오기(블로그/인스타)
        # 2) 스타일 분석(자동)
        # 3) 캡션/대본 생성 설정 + 실행
        # ===========================
        with st.container(border=True):
            st.subheader("📣 SNS 마케팅 레퍼런스 & 생성")
            st.caption("SNS/콘텐츠 목적일 때만 표시됩니다. 블로그/인스타 레퍼런스를 참고해 캡션/대본을 쉽게 생성합니다.")

            # --- 1) 플랫폼/니치 선택 ---
            topA, topB, topC = st.columns([1, 1, 1], gap="large")
            with topA:
                sns_platform = st.selectbox("플랫폼", ["instagram", "blog"], index=0, help="instagram=캡션/릴스 중심, blog=포스팅/정보성 중심")
            with topB:
                sns_niche = st.selectbox("콘셉트(니치)", ["맛집 블로거", "맛집 홍보 인스타", "카페 홍보", "제품 리뷰", "브랜드 계정(일반)"], index=1)
            with topC:
                sns_goal = st.selectbox("목표", ["홍보(방문/예약 유도)", "후기(신뢰/공감)", "정보(가이드/팁)", "이벤트/프로모션"], index=0)

            st.divider()

            # --- 2) 레퍼런스 가져오기 ---
            left_ref, right_ref = st.columns([1.05, 1.15], gap="large")

            with left_ref:
                st.markdown("#### 1) 레퍼런스(템플릿) 가져오기")
                ref_mode = st.radio("가져오기 방식", ["URL 붙여넣기", "직접 붙여넣기"], horizontal=True)

                if ref_mode == "URL 붙여넣기":
                    ref_url = st.text_input(
                        "레퍼런스 URL",
                        placeholder="예: 맛집 블로그 글 링크 / 공개 인스타 캡션 페이지 링크",
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        load_ref = st.button("가져오기", key="sns_ref_load")
                    with c2:
                        clear_ref = st.button("비우기", key="sns_ref_clear")

                    if load_ref and ref_url.strip():
                        with st.spinner("레퍼런스 추출 중..."):
                            txt, meta = fetch_url_text(ref_url.strip())
                        if txt.strip():
                            st.session_state.reference_text = txt
                            st.session_state.reference_meta = meta
                            st.success("레퍼런스를 설정했습니다.")
                        else:
                            st.warning("추출 실패(인스타/차단 페이지일 수 있음). '직접 붙여넣기'를 추천합니다.")

                    if clear_ref:
                        st.session_state.reference_text = ""
                        st.session_state.reference_meta = {}
                        st.success("레퍼런스를 비웠습니다.")

                else:
                    pasted = st.text_area(
                        "레퍼런스 텍스트",
                        height=220,
                        placeholder="블로그 글 일부(소제목+본문) 또는 인스타 캡션/릴스 대본을 붙여넣기"
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        apply_ref = st.button("레퍼런스로 설정", key="sns_ref_apply")
                    with c2:
                        clear_ref = st.button("비우기", key="sns_ref_clear2")
                    if apply_ref:
                        st.session_state.reference_text = pasted or ""
                        st.session_state.reference_meta = {"source": "pasted"}
                        st.success("레퍼런스를 설정했습니다.")
                    if clear_ref:
                        st.session_state.reference_text = ""
                        st.session_state.reference_meta = {}
                        st.success("레퍼런스를 비웠습니다.")

                st.caption("⚠️ 인스타는 본문 추출이 자주 막힙니다. 그럴 땐 캡션/대본을 복사해서 붙여넣는 방식이 가장 안정적입니다.")

            with right_ref:
                st.markdown("#### 2) 레퍼런스 미리보기 & 스타일 분석")
                if st.session_state.reference_text.strip():
                    st.text_area("Reference Preview", st.session_state.reference_text[:6000], height=220, label_visibility="collapsed")

                    profile = analyze_sns_style(st.session_state.reference_text)
                    st.markdown("**스타일 프로필(자동 분석)**")
                    p1, p2, p3 = st.columns(3)
                    p1.metric("해시태그 수", profile.get("hashtag_count", 0))
                    p2.metric("평균 문장 길이", profile.get("avg_sentence_len", 0))
                    p3.metric("이모지 밀도", profile.get("emoji_density", 0.0))
                    st.write("• 톤 추정:", profile.get("tone_guess"))
                    st.write("• 구조 추정:", ", ".join(profile.get("structure_guess") or []) or "-")
                    cta = profile.get("cta_phrases") or []
                    st.write("• CTA 단서:", ", ".join(cta) if cta else "-")
                else:
                    st.info("레퍼런스를 설정하면 자동으로 스타일 프로필을 뽑아줍니다.")

            st.divider()

            # --- 3) 생성 옵션 + 실행 ---
            st.markdown("#### 3) 캡션 / 릴스 대본 생성")
            st.caption("원본 텍스트(작성 탭의 원문)를 기반으로, 레퍼런스 스타일을 반영해 생성합니다.")

            optA, optB, optC, optD = st.columns([1, 1, 1, 1], gap="large")
            with optA:
                output_type = st.selectbox("출력", ["caption", "script"], index=0, help="caption=캡션, script=릴스/숏폼 대본")
            with optB:
                length_mode = st.selectbox("길이", ["짧게", "보통", "길게"], index=1)
            with optC:
                emoji_level = st.selectbox("이모지", ["없음", "약하게", "중간", "많이"], index=2)
            with optD:
                cta_mode = st.selectbox("CTA", ["없음", "가볍게", "강하게"], index=1)

            h1, h2 = st.columns([1, 1], gap="large")
            with h1:
                hashtag_mode = st.selectbox("해시태그", ["없음", "자동(추천)", "직접 입력"], index=1)
            with h2:
                hashtag_count = st.slider("해시태그 개수", 0, 25, 10)

            custom_hashtags = ""
            if hashtag_mode == "직접 입력":
                custom_hashtags = st.text_input("해시태그 직접 입력", placeholder="#맛집 #서울맛집 #데이트 ...")

            # 실행 버튼
            gen_col1, gen_col2 = st.columns([1, 2], gap="large")
            with gen_col1:
                gen_btn = st.button("SNS 생성 실행", key="sns_generate_run")

            with gen_col2:
                st.caption("팁) 레퍼런스가 없으면 기본 템플릿으로도 생성되지만, 레퍼런스가 있으면 '결'이 훨씬 비슷해집니다.")

            if gen_btn:
                # 작성 탭 원문을 기반으로 생성
                base_text = st.session_state.get("original_text", "").strip()
                if not api_key.strip():
                    st.error("API Key를 입력해줘.")
                elif not base_text:
                    st.error("작성 탭의 '원본 텍스트'를 먼저 입력해줘.")
                else:
                    constraints = {
                        "length_mode": length_mode,
                        "emoji_level": emoji_level,
                        "cta_mode": cta_mode,
                        "hashtag_mode": hashtag_mode,
                        "hashtag_count": hashtag_count,
                        "custom_hashtags": custom_hashtags
                    }

                    payload = {
                        "text": base_text,
                        "major": major,
                        "minor": minor,
                        "tone": tone,
                        "style": style,
                        "audience": audience,
                        "length": LENGTH_PRESET[length_key],
                        "edit": edit_level,
                    }

                    with st.spinner("SNS 생성 중..."):
                        data = run_sns_generation(
                            api_key=api_key,
                            model=model,
                            temperature=temperature,
                            base_payload=payload,
                            platform=sns_platform,
                            niche=sns_niche,
                            goal=sns_goal,
                            output_type=output_type,
                            constraints=constraints
                        )

                    rewritten = data.get("rewritten_text", "") or ""
                    if hashtag_mode == "직접 입력" and custom_hashtags.strip():
                        if custom_hashtags.strip() not in rewritten:
                            rewritten = rewritten.rstrip() + "\n\n" + custom_hashtags.strip()
                    # 기존 파이프라인에 얹기(기능 유지)
                    st.session_state.last_data = data
                    st.session_state.last_rewritten = rewritten
                    st.session_state.last_original = base_text
                    st.session_state.last_run_context = {"where": "sns_generate", "mode": "sns", "major": major, "minor": minor}

                    st.success("생성 완료! 작성 탭의 '✅ 변환 결과'에서도 확인할 수 있어요.")
                    st.text_area("생성 결과 미리보기", rewritten, height=240)

                    # 다운로드 빠른 제공
                    d1, d2 = st.columns(2)
                    with d1:
                        st.download_button("TXT 다운로드", rewritten, file_name="sns_result.txt")
                    with d2:
                        st.download_button("MD 다운로드", rewritten, file_name="sns_result.md")

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

