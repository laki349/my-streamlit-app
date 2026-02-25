# REPURPOSE

> Structure-based Text Repurposing Platform  
> 목적 기반 구조 재설계 AI 도구

---

## 📌 Overview

REPURPOSE는 단순 문장 수정이 아닌,  
**레퍼런스 구조를 학습하여 텍스트를 목적에 맞게 재설계하는 웹 애플리케이션**입니다.

같은 원문이라도 자소서, 논문, SNS, 기획서 등  
각 목적에 맞는 구조로 자동 변환할 수 있습니다.

---

## 🎯 Problem

우리는 같은 내용을 여러 번 다시 씁니다.

- 자소서용으로 다시 작성
- 논문 형식으로 재구성
- SNS용으로 변환
- 기획 문서로 재정리

기존 AI 도구는 문장을 고쳐주지만,  
**구조를 재설계하지는 않습니다.**

---

## 🚀 Solution

REPURPOSE는 다음 과정을 통해 구조 기반 변환을 수행합니다:

1. 사용자가 목적(대/소), 톤, 스타일 선택
2. 레퍼런스 텍스트 분석
3. 구조를 JSON 템플릿으로 추출
4. 원문을 해당 구조에 맞게 재배열
5. 목적에 맞는 톤으로 재작성

즉, 단순 생성이 아닌 **구조 학습 기반 재구성**입니다.

---

## 🧠 Core Features

### 1️⃣ 목적 기반 리라이팅
- 자소서 / 논문 / SNS / 기획서 등 변환
- 톤 & 스타일 제어 가능

### 2️⃣ 레퍼런스 템플릿 생성
- 우수 글에서 구조 추출
- JSON 템플릿 자동 생성
- 템플릿 기반 재작성 지원

### 3️⃣ 구조화된 JSON 출력
- rewritten_text
- change_points
- highlight_reasons
- suggested_repurposes

### 4️⃣ Diff 하이라이트
- 원문 대비 변경점 시각화

### 5️⃣ 세션 기반 히스토리 복원

---

## 🏗 Architecture

Pipeline:

Prompt Construction  
→ OpenAI API Call  
→ Structured JSON Response  
→ Python Parsing & Validation  
→ Template-based Restructuring  

Built with:
- Python
- Streamlit
- OpenAI API

---

## 📂 Project Structure


Main logic includes:
- prompt builders
- template extraction
- JSON parsing (safe_json)
- result normalization
- UI rendering & history management

---

## 💡 Future Vision

REPURPOSE는 단순 생성기가 아닌  
**구조 기반 글쓰기 플랫폼**으로 확장될 수 있습니다.

Planned directions:

- Template library 저장 기능
- 구조 유사도 분석
- A/B 구조 비교
- 개인화 구조 추천
- 조직 문서 표준화 도구로 확장

---

## 🖥 How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
