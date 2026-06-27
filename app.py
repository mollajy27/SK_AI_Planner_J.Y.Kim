import streamlit as st
from openai import OpenAI
import pandas as pd
import json
from datetime import datetime

st.set_page_config(page_title="AI 유연한 일정 관리 비서", layout="wide")

try:
    api_key = st.secrets["OPENAI_API_KEY"]
except KeyError:
    st.error("Streamlit Cloud 설정에서 OPENAI_API_KEY를 등록해 주세요!")
    st.stop()

client = OpenAI(api_key=api_key)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "system", 
            "content": """당신은 기존 플래너의 한계를 극복하는 '유연한 일정 관리 에이전트'입니다.
사용자와 대화하며 일정을 조율해 주세요. 
새로운 일정 요청이나 재배치 요청이 들어오면, 사용자의 '전체 최신 일정 목록'을 판단하여 
답변 맨 마지막 줄에 반드시 [JSON_DATA] 포맷으로 누적하여 한꺼번에 출력해야 합니다.
텍스트 설명과 [JSON_DATA] 사이에는 줄바꿈을 두 번 하세요.

포맷 예시:
[JSON_DATA]
[
  {"카테고리": "고정 일정", "일시": "2026-06-29 09:00", "내용": "데이터베이스 전공 수업", "비고": "공학관 301호"},
  {"카테고리": "유연한 작업", "일시": "2026-06-29 15:00", "내용": "헬스장 운동", "비고": "가볍게 등 운동 1시간"}
]
[/JSON_DATA]"""
        }
    ]

if "confirmed_events" not in st.session_state:
    st.session_state.confirmed_events = []

tab1, tab2 = st.tabs(["🤖 AI 비서와 실시간 조율", "📅 나의 확정 일정표 (List-up)"])

# ----------------- [Tab 1: AI 대화 창 (최신순 상단 배치)] -----------------
with tab1:
    st.subheader("💬 AI 에이전트에게 일정을 말해보세요")
    
    # 💡 [구조 변경 1] 프롬프트 입력창을 대화 목록보다 맨 위에 강제 고정합니다.
    user_input = st.chat_input("예: '월요일 오전 9시 전공수업, 오후 3시에 운동 갈래.'", key="top_chat_input")

    # 입력값이 들어왔을 때 로직을 먼저 처리합니다.
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        # OpenAI 답변 생성
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state.messages
        )
        raw_response = completion.choices[0].message.content
        
        # JSON 데이터 동기화
        if "[JSON_DATA]" in raw_response:
            try:
                data_part = raw_response.split("[JSON_DATA]")[1].split("[/JSON_DATA]")[0].strip()
                new_events = json.loads(data_part)
                if isinstance(new_events, list):
                    st.session_state.confirmed_events = new_events
            except Exception as e:
                pass
                
        st.session_state.messages.append({"role": "assistant", "content": raw_response})
        st.rerun() # 화면을 즉시 새로고침하여 상단에 반영되도록 합니다.

    st.markdown("---")
    
    # 💡 [구조 변경 2] 대화 리스트를 뒤집어서([::-1]) 최신 문답이 맨 위로 오게 출력합니다.
    # 단, 시스템 프롬프트(index 0)는 출력에서 제외합니다.
    chat_history = [m for m in st.session_state.messages if m["role"] != "system"]
    
    for message in reversed(chat_history):
        with st.chat_message(message["role"]):
            clean_content = message["content"].split("[JSON_DATA]")[0].strip()
            st.write(clean_content)

# ----------------- [Tab 2: 확정 일정 리스트 및 달력] -----------------
with tab2:
    st.subheader("📋 실시간 동기화된 타임라인 목록")
    
    if st.session_state.confirmed_events:
        df = pd.DataFrame(st.session_state.confirmed_events)
        df = df.sort_values(by="일시", ascending=True).reset_index(drop=True)
        
        st.dataframe(
            df, 
            use_container_width=True,
            column_config={
                "일시": st.column_config.DatetimeColumn("일시", format="YYYY-MM-DD HH:mm"),
            }
        )
        
        st.markdown("---")
        st.subheader("📆 날짜별 달력 뷰 (일별 간이 리스트)")
        
        df['날짜'] = df['일시'].apply(lambda x: x.split(" ")[0] if " " in str(x) else str(x))
        unique_dates = sorted(df['날짜'].unique())
        
        for date in unique_dates:
            with st.expander(f"📅 {date} 일자 계획 확인하기"):
                day_df = df[df['날짜'] == date]
                day_df = day_df.sort_values(by="일시", ascending=True)
                for _, row in day_df.iterrows():
                    time_str = row['일시'].split(" ")[1] if " " in str(row['일시']) else "하루 종일"
                    st.markdown(f"**[{row['카테고리']}]** ⏰ {time_str} - **{row['내용']}** ({row['비고']})")
                    
        if st.button("🧹 일정표 전체 초기화"):
            st.session_state.confirmed_events = []
            st.rerun()
    else:
        st.info("아직 확정된 일정이 없습니다. AI 비서 탭에서 일정을 조율해 보세요!")