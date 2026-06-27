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

# 매 턴마다 현재 시간이 갱신된 최신 시스템 프롬프트를 사용하기 위해 구조를 분리합니다.
# 💡 [수정된 부분] 현재 날짜와 '요일'까지 파이썬이 정확히 계산해서 AI에게 넘겨줍니다.
now = datetime.now()
current_time_str = now.strftime("%Y-%m-%d %H:%M")
weekday_list = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
current_weekday = weekday_list[now.weekday()] # 오늘 실제 요일 추출

system_instruction = f"""당신은 기존 플래너의 한계를 극복하는 '유연한 일정 관리 에이전트'입니다.
사용자와 대화하며 일정을 조율해 주세요.

★ 매우 중요 (정확한 달력 계산 가이드):
- 현재 사용자의 기준 시각은 [{current_time_str}] 이며, 오늘은 [{current_weekday}] 입니다.
- 6월은 30일까지 있으며, 7월 1일은 수요일입니다.
- 사용자가 '다음 주 수요일'이라고 하면, 오늘인 {current_time_str} ({current_weekday})을 기준으로 달력을 정확히 계산하여 [2026-07-01]로 인지해야 합니다. 절대로 날짜와 요일을 매칭할 때 환각(오류)을 일으키지 마세요.

새로운 일정 요청이나 재배치 요청이 들어오면, 사용자의 '전체 최신 일정 목록'을 판단하여 
답변 맨 마지막 줄에 반드시 [JSON_DATA] 포맷으로 누적하여 한꺼번에 출력해야 합니다.
텍스트 설명과 [JSON_DATA] 사이에는 줄바꿈을 두 번 하세요.

포맷 예시:
[JSON_DATA]
[
  {{"카테고리": "고정 일정", "일시": "2026-07-01 09:00", "내용": "데이터베이스 전공 수업", "비고": "공학관 301호"}}
]
[/JSON_DATA]"""

# 대화 기록 관리를 위한 세션 상태 저장 (메시지 배열에는 유저/어시스턴트 문답만 순수하게 유지)
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "confirmed_events" not in st.session_state:
    st.session_state.confirmed_events = []

tab1, tab2 = st.tabs(["🤖 AI 비서와 실시간 조율", "📅 나의 확정 일정표 (List-up)"])

# ----------------- [Tab 1: AI 대화 창 (최신순 상단 배치)] -----------------
with tab1:
    st.subheader("💬 AI 에이전트에게 일정을 말해보세요")
    st.caption(f"🕒 현재 시스템 인지 시각: {current_time_str}") # 상단에 현재 시간 노출
    
    user_input = st.chat_input("예: '오늘 7시에 신촌에서 약속이 있어. 일정표에 넣어줘.'", key="top_chat_input")

    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})

        # API를 호출할 때, 실시간으로 갱신된 system_instruction을 맨 앞에 조립해서 보냅니다.
        api_messages = [{"role": "system", "content": system_instruction}] + st.session_state.chat_messages

        # OpenAI 답변 생성
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=api_messages
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
                
        st.session_state.chat_messages.append({"role": "assistant", "content": raw_response})
        st.rerun()

    st.markdown("---")
    
    # 대화 기록 최신순 역순 출력
    for message in reversed(st.session_state.chat_messages):
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