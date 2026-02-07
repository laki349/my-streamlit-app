diff --git a/app.py b/app.py
index b2d633619b663357e3ce907384856c297493e0eb..7083ed51fc79a6ebecaec620354cddd58587fd2d 100644
--- a/app.py
+++ b/app.py
@@ -51,145 +51,205 @@ STRUCTURE_TEMPLATES = {
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
 
+# -----------------------------
+# Insight Helpers
+# -----------------------------
+def derive_change_points(original, rewritten):
+    points = []
+    if not original.strip() or not rewritten.strip():
+        return points
+
+    length_delta = len(rewritten) - len(original)
+    if abs(length_delta) >= 50:
+        direction = "확장" if length_delta > 0 else "축약"
+        points.append(f"분량이 약 {abs(length_delta)}자 {direction}되었습니다.")
+
+    original_lines = [line.strip() for line in original.splitlines() if line.strip()]
+    rewritten_lines = [line.strip() for line in rewritten.splitlines() if line.strip()]
+    if len(rewritten_lines) != len(original_lines):
+        points.append("문장 구성이 재배열되어 흐름이 다듬어졌습니다.")
+
+    if not points:
+        points.append("핵심 표현을 유지하면서 문장을 매끄럽게 다듬었습니다.")
+    return points
+
+def derive_repurpose_suggestions(major, minor):
+    suggestions = []
+    for item in MAJOR_PURPOSES.get(major, []):
+        if item != minor:
+            suggestions.append({"major_purpose": major, "minor_purpose": item})
+    if len(suggestions) < 2:
+        for other_major, minors in MAJOR_PURPOSES.items():
+            if other_major == major:
+                continue
+            suggestions.append({"major_purpose": other_major, "minor_purpose": minors[0]})
+            if len(suggestions) >= 3:
+                break
+    return suggestions
+
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
    "추론 설명 없이 결과만 JSON으로 반환하라."
     )
 
+    expansion_instruction = ""
+    if p.get("expand"):
+        expansion_instruction = (
+            "\n- expanded_text에는 원문 사실을 해치지 않되 목적에 맞게 "
+            "의미를 보강한 문장을 추가로 포함하라. "
+            "예시처럼 '경험 → 목적/제안'의 논리를 자연스럽게 연결한다."
+        )
+
     user = f"""
 원본:
 {p["text"]}
 
 목적: {p["major"]} → {p["minor"]}
 구조: {template}
 편집 강도: {EDIT_INTENSITY[p["edit"]]}
 톤: {p["tone"]}, 스타일: {p["style"]}, 독자: {p["audience"]}
 분량: {p["length"]}자
+{expansion_instruction}
 
 JSON:
 {{
  "rewritten_text": "",
+ "expanded_text": "",
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
+    expand_text = st.checkbox("내용 확장(목적에 맞게 살을 붙임)", value=True)
 
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
-        "edit": edit_level
+        "edit": edit_level,
+        "expand": expand_text
     }
 
     system, user = build_prompt(payload)
 
     with st.spinner("변환 중..."):
         raw = call_openai(api_key, model, system, user, temperature)
 
     data = safe_json(raw)
     rewritten = data.get("rewritten_text", "")
+    expanded = data.get("expanded_text", "")
 
     st.subheader("✅ 변환 결과 (하이라이트)")
     st.markdown(render_diff_html(original_text, rewritten), unsafe_allow_html=True)
 
+    if expand_text and expanded:
+        st.subheader("✨ 확장 결과 (목적 중심 보강)")
+        st.write(expanded)
+
     st.subheader("🔍 변경 포인트")
-    for c in data.get("change_points", []):
+    change_points = data.get("change_points", []) or derive_change_points(original_text, rewritten)
+    for c in change_points:
         st.write("-", c)
 
     st.subheader("💡 재활용 추천")
-    for r in data.get("suggested_repurposes", []):
-        st.write(f"{r['major_purpose']} → {r['minor_purpose']}")
+    suggested = data.get("suggested_repurposes", []) or derive_repurpose_suggestions(major, minor)
+    for r in suggested:
+        if isinstance(r, dict):
+            major_purpose = r.get("major_purpose", "기타")
+            minor_purpose = r.get("minor_purpose", "추천")
+            st.write(f"{major_purpose} → {minor_purpose}")
+        else:
+            st.write(f"{r}")
 
     # AI Score (simple heuristic)
     st.subheader("📈 품질 점수")
     score = min(95, 60 + len(rewritten)//200)
     st.progress(score/100)
     st.write(f"{score}/100")
 
     # Downloads
     st.download_button("TXT 다운로드", rewritten, file_name="result.txt")
     st.download_button("MD 다운로드", rewritten, file_name="result.md")
