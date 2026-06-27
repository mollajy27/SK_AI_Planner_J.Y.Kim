import streamlit as st
from openai import OpenAI
import pandas as pd
import json
from datetime import datetime

st.set_page_config(page_title="AI 유연한 일정 관리 비서", layout="wide") # 대시보드 형태를 위해 wide 모드로 설정

# 1. API 키 불러오기 및 초기화
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except KeyError:
    st.error("Streamlit Cloud 설정에서 OPENAI_API_KEY를 등록해 주세요!")
    st.stop()

client = OpenAI(api_key=api_key)

# 2. 데이터 저장을 위한 Session State(임시 데이터베이스) 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "system", 
            "content": """당신은 기존 플래너의 한계를 극복하는 '유연한 일정 관리 에이전트'입니다.
사용자와 대화하며 일정을 조율해 주세요. 
만약 사용자의 요청으로 일정이 최종 확정되거나 대화 중에 저장할 만한 일정이 도출되면, 
답변 맨 마지막 줄에 반드시 아래와 같은 [JSON_DATA] 포맷을 포함하여 출력해야 합니다. 
이 텍스트 데이터는 시스템이 자동으로 파싱하여 일정 표에 등록할 것입니다.
텍스트 설명과 [JSON_DATA] 사이에는 줄바꿈을 두 번 하세요.

포맷 예시 (반드시 이 형식을 엄수하고, JSON 외의 다른 글자는 이 태그 안에 넣지 마세요):
[JSON_DATA]
[
  {"카테고리": "고정 일정", "일시": "2026-06-29 09:00", "내용": "데이터베이스 전공 수업", "비고": "공학관 301호"},
  {"카테고리": "유연한 작업", "일시": "2026-06-29 15:00", "내용": "헬스장 운동", "비고": "가볍게 등 운동 1시간"}
]
[/JSON_DATA]"""
        }
    ]

# 사용자가 확정한 일정 목록 리스트
if "confirmed_events" not in st.session_state:
    st.session_state.confirmed_events = [
        {"카테고리": "예시", "일시": "2026-06-27 14:00", "내용": "AI 플래너 과제 테스트", "비고": "작동 확인용 예시 데이터"}
    ]

# 3. 화면 상단 탭 구성 (구글/갤럭시 캘린더 스타일 대시보드)
tab1, tab2 = st.tabs(["🤖 AI 비서와 실시간 조율", "📅 나의 확정 일정표 (List-up)"])

# ----------------- [Tab 1: AI 대화 창] -----------------
with tab1:
    st.subheader("💬 AI 에이전트에게 일정을 말해보세요")
    st.write("돌발 상황이나 누락된 작업을 말하면 즉시 비서가 판단하여 반영합니다.")
    
    # 기존 대화 기록 출력
    for message in st.session_state.messages:
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                # 사용자 화면에는 복잡한 JSON 태그를 숨기고 순수 답변만 렌더링
                clean_content = message["content"].split("[JSON_DATA]")[0].strip()
                st.write(clean_content)

    # 사용자 입력 처리
    if user_input := st.chat_input("예: '월요일 오전 9시 전공수업, 오후 3시에 운동 갈래. 일정표에 넣어줘.'"):
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=st.session_state.messages
            )
            
            raw_response = completion.choices[0].message.content
            
            # 💡 비밀 작동: AI 답변 속에 [JSON_DATA]가 들어있는지 검사하고 데이터베이스에 실시간 적재
            if "[JSON_DATA]" in raw_response:
                try:
                    data_part = raw_response.split("[JSON_DATA]")[1].split("[/JSON_DATA]")[0].strip()
                    new_events = json.loads(data_part)
                    if isinstance(new_events, list):
                        st.session_state.confirmed_events.extend(new_events)
                        st.success("💡 신규 일정이 확정되어 '나의 확정 일정표' 탭에 자동 동기화되었습니다!")
                except Exception as e:
                    pass # 파싱 실패 시 조용히 넘어감
            
            # 사용자 화면에는 정제된 대답만 노출
            clean_response = raw_response.split("[JSON_DATA]")[0].strip()
            response_placeholder.write(clean_response)
            
        st.session_state.messages.append({"role": "assistant", "content": raw_response})

# ----------------- [Tab 2: 확정 일정 리스트 및 달력] -----------------
with tab2:
    st.subheader("📋 실시간 동기화된 타임라인 목록")
    
    if st.session_state.confirmed_events:
        # 데이터프레임(표)으로 변환
        df = pd.DataFrame(st.session_state.confirmed_events)
        
        # 1. 표(Table)로 List-up 노출
        st.dataframe(
            df, 
            use_container_width=True,
            column_config={
                "일시": st.column_config.DatetimeColumn("일시", format="YYYY-MM-DD HH:mm"),
            }
        )
        
        # 2. 갤럭시 달력 간이 시각화 기능 (날짜별 요약 리스트)
        st.markdown("---")
        st.subheader("📆 날짜별 달력 뷰 (일별 간이 리스트)")
        
        # 일시 정렬을 위해 변환
        df['날짜'] = df['일시'].apply(lambda x: x.split(" ")[0] if " " in str(x) else str(x))
        unique_dates = sorted(df['날짜'].unique())
        
        # 갤럭시 달력에서 날짜를 누르면 하단에 뜨는 것처럼 렌더링
        for date in unique_dates:
            with st.expander(f"📅 {date} 일자 계획 확인하기"):
                day_df = df[df['날짜'] == date]
                for _, row in day_df.iterrows():
                    time_str = row['일시'].split(" ")[1] if " " in str(row['일시']) else "하루 종일"
                    st.markdown(f"**[{row['카테고리']}]** ⏰ {time_str} - **{row['내용']}** ({row['비고']})")
                    
        # 데이터 초기화 버튼 (테스트용)
        if st.button("🧹 일정표 전체 초기화"):
            st.session_state.confirmed_events = []
            st.rerun()
    else:
        st.info("아직 확정된 일정이 없습니다. AI 비서 탭에서 일정을 조율해 보세요!")