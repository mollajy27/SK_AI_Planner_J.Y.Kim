import streamlit as st
from openai import OpenAI
import pandas as pd
import json
from datetime import datetime

# 대시보드 형태로 넓게 보기 위해 wide 모드로 설정
st.set_page_config(page_title="AI 유연한 일정 관리 비서", layout="wide")

# 1. API 키 불러오기 및 초기화
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    st.error("Streamlit Cloud 설정에서 OPENAI_API_KEY를 등록해 주세요!")
    st.stop()

client = OpenAI(api_key=api_key)

# 실시간 현재 날짜 및 요일 계산
now = datetime.now()
current_time_str = now.strftime("%Y-%m-%d %H:%M")
weekday_list = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
current_weekday = weekday_list[now.weekday()]

# AI 에이전트에게 주입할 시스템 프롬프트
system_instruction = f"""당신은 기존 플래너의 한계를 극복하는 '유연한 일정 관리 에이전트'입니다.
사용자와 대화하며 일정을 조율해 주세요.

★ 매우 중요 (정확한 달력 계산 가이드):
- 현재 사용자의 기준 시각은 [{current_time_str}] 이며, 오늘은 [{current_weekday}] 입니다.
- 6월은 30일까지 있으며, 7월 1일은 수요일입니다.
- 사용자가 '오늘', '내일', '다음 주 수요일', '7시' 등 상대적인 시간 표현을 쓰면, 반드시 이 기준 시각을 바탕으로 정확한 날짜를 계산해야 합니다.
- 모든 일정은 반드시 **시작시간**과 **종료시간**을 'YYYY-MM-DD HH:mm' 형식으로 각각 명확히 분리하여 기록해야 합니다. (예: 10:00~18:00 연수라면 시작시간은 10:00, 종료시간은 18:00)

새로운 일정 요청이나 재배치 요청이 들어오면, 사용자의 '전체 최신 일정 목록'을 판단하여 
답변 맨 마지막 줄에 반드시 [JSON_DATA] 포맷으로 누적하여 한꺼번에 출력해야 합니다.
텍스트 설명과 [JSON_DATA] 사이에는 줄바꿈을 두 번 하세요.

포맷 예시 (형식을 엄수하세요):
[JSON_DATA]
[
  {{"카테고리": "고정 일정", "시작시간": "2026-07-01 10:00", "종료시간": "2026-07-01 18:00", "내용": "회사 연수(1일차)", "비고": "연수원 강당"}}
]
[/JSON_DATA]"""

# Session State 초기화
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "confirmed_events" not in st.session_state:
    st.session_state.confirmed_events = []

# 화면 상단 탭 구성
tab1, tab2 = st.tabs(["🤖 AI 비서와 실시간 조율", "📅 나의 확정 일정표 (List-up)"])

# ----------------- [Tab 1: AI 대화 창] -----------------
with tab1:
    st.subheader("💬 AI 에이전트에게 일정을 말해보세요")
    st.caption(f"🕒 현재 시스템 인지 시각: {current_time_str} ({current_weekday})")
    
    # 프롬프트 입력창을 대화 목록보다 맨 위에 강제 고정
    user_input = st.chat_input("예: '오늘 7시에 신촌에서 약속이 있어. 일정표에 넣어줘.'", key="top_chat_input")

    if user_input:
        # 사용자 입력을 먼저 화면에 기록하기 위해 저장
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        api_messages = [{"role": "system", "content": system_instruction}] + st.session_state.chat_messages

        # 💡 에러 방지를 위해 로딩 스피너 작동
        with st.spinner("AI 비서가 일정을 연산하고 있습니다..."):
            try:
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=api_messages
                )
                raw_response = completion.choices[0].message.content
                
                # 비밀 작동: [JSON_DATA] 동기화 및 덮어쓰기(중복 방지)
                if "[JSON_DATA]" in raw_response:
                    try:
                        data_part = raw_response.split("[JSON_DATA]")[1].split("[/JSON_DATA]")[0].strip()
                        new_events = json.loads(data_part)
                        if isinstance(new_events, list):
                            st.session_state.confirmed_events = new_events
                    except Exception as json_err:
                        pass
                        
                st.session_state.chat_messages.append({"role": "assistant", "content": raw_response})
            except Exception as api_err:
                st.error(f"OpenAI API 호출 중 오류가 발생했습니다. 잔액을 확인해 보시거나 잠시 후 다시 시도해 주세요. ({str(api_err)})")
        
        st.rerun()

    st.markdown("---")
    # 대화 기록을 최신순(역순)으로 출력
    for message in reversed(st.session_state.chat_messages):
        with st.chat_message(message["role"]):
            clean_content = message["content"].split("[JSON_DATA]")[0].strip()
            st.write(clean_content)

# ----------------- [Tab 2: 확정 일정 리스트 및 달력] -----------------
with tab2:
    if st.session_state.confirmed_events:
        df = pd.DataFrame(st.session_state.confirmed_events)
        
        # 안전한 정렬을 위해 '시작시간' 컬럼이 존재할 때만 정렬 진행
        if "시작시간" in df.columns:
            df = df.sort_values(by="시작시간", ascending=True).reset_index(drop=True)
        
        # 💡 실시간 동기화된 타임라인 목록 표를 기본적으로 '접어놓기(expanded=False)'
        with st.expander("📋 실시간 동기화된 타임라인 전체 목록 (표 형태로 보기)", expanded=False):
            display_cols = [c for c in ["카테고리", "시작시간", "종료시간", "내용", "비고"] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True)
        
        st.markdown("---")
        st.subheader("📆 날짜별 달력 뷰")
        
        if "시작시간" in df.columns:
            df['날짜'] = df['시작시간'].apply(lambda x: str(x).split(" ")[0] if " " in str(x) else str(x))
            unique_dates = sorted(df['날짜'].unique())
            
            for date in unique_dates:
                # 💡 날짜별 달력 뷰 토글 박스를 기본적으로 '펴놓기(expanded=True)'
                with st.expander(f"📅 {date} 일자 계획 확인하기", expanded=True):
                    day_df = df[df['날짜'] == date]
                    if "시작시간" in day_df.columns:
                        day_df = day_df.sort_values(by="시작시간", ascending=True)
                    
                    for _, row in day_df.iterrows():
                        start_time = str(row.get('시작시간', '00:00')).split(" ")[1] if " " in str(row.get('시작시간', '')) else "00:00"
                        end_time = str(row.get('종료시간', '23:59')).split(" ")[1] if " " in str(row.get('종료시간', '')) else "23:59"
                        
                        # 💡 비고 내용이 공백이거나 없는 경우 괄호() 생략 로직
                        note_content = str(row.get('비고', '')).strip()
                        if note_content and note_content != "None" and note_content != "nan":
                            note_str = f" ({note_content})"
                        else:
                            note_str = ""
                            
                        st.markdown(f"**[{row.get('카테고리', '일정')}]** ⏰ {start_time} ~ {end_time} - **{row.get('내용', '내용 없음')}**{note_str}")
    else:
        st.info("아직 확정된 일정이 없습니다. AI 비서 탭에서 일정을 조율해 보세요!")
        
    st.markdown("---")
    if st.button("🚨 시스템 전체 초기화 (대화 내역 + 일정표)"):
        st.session_state.chat_messages = []
        st.session_state.confirmed_events = []
        st.rerun()