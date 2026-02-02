import streamlit as st
import requests
from collections import defaultdict

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(
    page_title="🎬 OTT + 취향 기반 영화 추천",
    page_icon="🍿",
    layout="wide"
)

st.title("🍿 내가 구독한 OTT + 취향으로 영화 추천")

# -----------------------------
# 사이드바
# -----------------------------
st.sidebar.title("⚙️ 설정")

tmdb_api_key = st.sidebar.text_input(
    "TMDB Open API Key",
    type="password"
)

st.sidebar.markdown("### 📺 구독 중인 OTT")

OTT_PROVIDERS = {
    "Netflix": 8,
    "Watcha": 97,
    "Disney Plus": 337,
    "Wavve": 356,
    "Apple TV+": 350,
    "Amazon Prime Video": 119
}

selected_otts = st.sidebar.multiselect(
    "구독 중인 OTT 선택",
    options=list(OTT_PROVIDERS.keys())
)

st.sidebar.markdown("### ⭐ 평점 범위")
min_rating = st.sidebar.slider("최소 평점", 0.0, 10.0, 6.5, 0.1)
max_rating = st.sidebar.slider("최대 평점", 0.0, 10.0, 10.0, 0.1)

# -----------------------------
# 🔥 영화 나열 방식 선택 (추가)
# -----------------------------
st.sidebar.markdown("### 🗂 영화 나열 방식")

sort_option = st.sidebar.selectbox(
    "정렬 기준 선택",
    [
        "🔥 인기순",
        "⭐ 평점 높은 순",
        "🆕 최신 개봉 순",
        "🎯 평점 + 인기 균형 추천"
    ]
)

SORT_MAP = {
    "🔥 인기순": "popularity.desc",
    "⭐ 평점 높은 순": "vote_average.desc",
    "🆕 최신 개봉 순": "primary_release_date.desc",
    "🎯 평점 + 인기 균형 추천": "popularity.desc"  # 1차 정렬
}

# -----------------------------
# 심리 테스트 질문
# -----------------------------
st.markdown("## 🧠 간단 취향 테스트")

questions = {
    "주말에 가장 하고 싶은 것은?": {
        "집에서 휴식": "드라마",
        "친구와 놀기": "코미디",
        "새로운 곳 탐험": "액션",
        "혼자 취미생활": "로맨스"
    },
    "스트레스를 받으면?": {
        "혼자 있기": "드라마",
        "수다 떨기": "코미디",
        "운동하기": "액션",
        "맛있는 거 먹기": "코미디"
    },
    "영화에서 가장 중요한 것은?": {
        "감동 스토리": "드라마",
        "시각적 영상미": "SF",
        "깊은 메시지": "SF",
        "웃는 재미": "코미디"
    },
    "여행 스타일은?": {
        "계획적": "드라마",
        "즉흥적": "액션",
        "액티비티": "액션",
        "힐링": "로맨스"
    },
    "친구 사이에서 나는?": {
        "듣는 역할": "드라마",
        "주도하기": "액션",
        "분위기 메이커": "코미디",
        "필요할 때 나타남": "판타지"
    }
}

answers = []
for i, (q, opts) in enumerate(questions.items(), 1):
    ans = st.radio(f"{i}️⃣ {q}", list(opts.keys()))
    answers.append(opts[ans])

# -----------------------------
# 장르 ID
# -----------------------------
GENRE_ID = {
    "액션": 28,
    "코미디": 35,
    "드라마": 18,
    "SF": 878,
    "로맨스": 10749,
    "판타지": 14
}

# -----------------------------
# 추천 버튼
# -----------------------------
if st.button("🎯 추천 받기"):
    if not tmdb_api_key:
        st.error("TMDB API Key를 입력해주세요.")
    elif not selected_otts:
        st.warning("최소 1개의 OTT를 선택해주세요.")
    else:
        with st.spinner("🎥 취향 + OTT 분석 중..."):

            # 1️⃣ 취향 점수 계산
            score = defaultdict(int)
            for g in answers:
                score[g] += 1

            ranked = sorted(score.items(), key=lambda x: x[1], reverse=True)
            top_genres = [g for g, _ in ranked[:2]]

            genre_ids = [str(GENRE_ID[g]) for g in top_genres]
            provider_ids = [str(OTT_PROVIDERS[o]) for o in selected_otts]

            params = {
                "api_key": tmdb_api_key,
                "language": "ko-KR",
                "region": "KR",
                "sort_by": SORT_MAP[sort_option],
                "vote_average.gte": min_rating,
                "vote_average.lte": max_rating,
                "with_genres": ",".join(genre_ids),
                "with_watch_providers": "|".join(provider_ids),
                "watch_region": "KR"
            }

            res = requests.get(
                "https://api.themoviedb.org/3/discover/movie",
                params=params
            )

            movies = res.json().get("results", [])

            # 🎯 평점 + 인기 균형 추천 후처리
            if sort_option == "🎯 평점 + 인기 균형 추천":
                movies = sorted(
                    movies,
                    key=lambda m: (m["vote_average"] * 2 + m["popularity"]),
                    reverse=True
                )

            movies = movies[:9]

        # -----------------------------
        # 결과 출력
        # -----------------------------
        st.divider()
        st.markdown(
            f"### 🎯 당신의 취향 장르: **{', '.join(top_genres)}**"
        )
        st.caption(f"📌 정렬 기준: {sort_option}")

        if not movies:
            st.info("조건에 맞는 영화가 없습니다.")
        else:
            cols = st.columns(3)
            for i, m in enumerate(movies):
                with cols[i % 3]:
                    if m.get("poster_path"):
                        st.image(
                            f"https://image.tmdb.org/t/p/w500{m['poster_path']}",
                            use_container_width=True
                        )

                    st.markdown(f"### 🎬 {m['title']}")
                    st.write(f"⭐ 평점: {m['vote_average']}")

                    with st.expander("📖 상세 보기"):
                        st.write(
                            m.get("overview", "줄거리 정보 없음")
                        )
                        st.caption("✔ 구독 중인 OTT에서 시청 가능")
