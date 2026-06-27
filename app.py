import streamlit as st
from openai import OpenAI
import pandas as pd
import json
from datetime import datetime, timedelta
import calendar

st.set_page_config(page_title="AI 유연한 일정 관리 비서", layout="wide")

try:
    api_key = st.secrets["OPENAI_API_KEY"]
except KeyError:
    st.error("Streamlit Cloud 설정에서 OPENAI_API_KEY를 등록해 주세요!")
    st.stop()

client = OpenAI(api_key=api_key)

# 1. 대한민국 표준시(KST) 기준 시각 및 요일 계산
now = datetime.now() + timedelta(hours=9)
current_time_str = now.strftime("%Y-%m-%d %H:%M")
weekday_list = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
current_weekday = weekday_list[now.weekday()]

# 가변형 전체 달력 주입
calendar_hint = ""
current_year = now.year
current_month = now.month

for m_offset in [0, 1]:
    target_month = current_month + m_offset
    target_year = current_year
    if target_month > 12:
        target_month -= 12
        target_year += 12
        
    _, last_day = calendar.monthrange(target_year, target_month)
    
    for day in range(1, last_day + 1):
        date_obj = datetime(target_year, target_month, day)
        date_str = date_obj.strftime("%Y-%m-%d")
        day_name = weekday_list[date_obj.weekday()]
        calendar_hint += f"- {date_str} ({day_name})\n"

# 2. AI 에이전트 시스템 프롬프트
system_instruction = f"""당신은 기존 플래너의 한계를 극복하는 '유연한 일정 관리 에이전트'입니다.
사용자와 대화하며 일정을 조율해 주세요.

★ 매우 중요 (날짜 계산 가이드):
- 현재 사용자 기준 시각: [{current_time_str}] / 오늘 요일: [{current_weekday}]
- 사용자가 '다음 주 월요일'이나 '다음 주 평일'을 언급할 때, 오늘이 주말(금, 토, 일)이라면 그것은 2주 뒤가 아니라 **바로 다가오는 직근 평일(돌아오는 가장 가까운 월요일)**을 의미합니다. 절대 오해하지 마세요.
- 임의 계산 금지. 반드시 아래의 [정확한 날짜 및 요일 테이블]에서 오늘 날짜와 가장 가까운 미래의 요일을 매칭하세요.

[정확한 날짜 및 요일 테이블]
{calendar_hint}

★ JSON 출력 규칙 (필수 준수):
- 모든 일정은 반드시 **시작시간**과 **종료시간**을 'YYYY-MM-DD HH:mm' 형식으로 명확히 분리하여 기록해야 합니다.
- '카테고리' 키값은 항상 "카테고리 없음"으로 통일하여 설정하세요. 사용자가 화면에서 직접 수정할 것입니다.
- 새로운 일정 요청이나 변경이 들어오면, 사용자의 '전체 최신 일정 목록'을 반영하여 답변 맨 마지막 줄에 반드시 [JSON_DATA] 포맷으로 누적하여 출력해야 합니다.
"""

# Session State 초기화
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "confirmed_events" not in st.session_state:
    st.session_state.confirmed_events = []

if "custom_categories" not in st.session_state:
    st.session_state.custom_categories = ["카테고리 없음", "회사", "여가", "개인"]

tab1, tab2 = st.tabs(["🤖 AI 비서와 실시간 조율", "📅 나의 확정 일정표 (List-up)"])

# ----------------- [Tab 1: AI 대화 창] -----------------
with tab1:
    st.subheader("💬 AI 에이전트에게 일정을 말해보세요")
    st.caption(f"🕒 현재 시스템 인지 시각: {current_time_str} ({current_weekday})")
    
    user_input = st.chat_input("예: '다음주 월요일 13시 30분에 셔틀버스 타야 해.'", key="top_chat_input")

    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        api_messages = [{"role": "system", "content": system_instruction}] + st.session_state.chat_messages

        with st.spinner("AI 비서가 일정을 연산하고 있습니다..."):
            try:
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=api_messages
                )
                raw_response = completion.choices[0].message.content
                
                if "[JSON_DATA]" in raw_response and "[/JSON_DATA]" in raw_response:
                    try:
                        data_part = raw_response.split("[JSON_DATA]")[1].split("[/JSON_DATA]")[0].strip()
                        new_events = json.loads(data_part)
                        if isinstance(new_events, list):
                            st.session_state.confirmed_events = new_events
                    except Exception as json_err:
                        pass
                        
                st.session_state.chat_messages.append({"role": "assistant", "content": raw_response})
            except Exception as api_err:
                st.error(f"오류가 발생했습니다: {str(api_err)}")
        
        st.rerun()

    st.markdown("---")
    for message in reversed(st.session_state.chat_messages):
        with st.chat_message(message["role"]):
            clean_content = message["content"].split("[JSON_DATA]")[0].strip()
            st.write(clean_content)

# ----------------- [Tab 2: 확정 일정표 및 카테고리 관리] -----------------
with tab2:
    if st.session_state.confirmed_events:
        df = pd.DataFrame(st.session_state.confirmed_events)
        
        if "카테고리" not in df.columns:
            df["카테고리"] = "카테고리 없음"
        
        if "시작시간" in df.columns:
            df = df.sort_values(by="시작시간", ascending=True).reset_index(drop=True)
        
        # 1. 실시간 데이터프레임 원본 표 보기
        with st.expander("📋 실시간 동기화된 타임라인 전체 목록 (표 형태로 보기)", expanded=False):
            display_cols = [c for c in ["카테고리", "시작시간", "종료시간", "내용", "비고"] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True)
        
        st.markdown("---")
        
        # 💡 [구조 최적화]: '달력 뷰 대제목'을 선언한 뒤, 그 바로 아랫단에 설정 메뉴와 일정을 일체형으로 배치
        st.subheader("📆 날짜별 달력 뷰 및 관리")
        
        with st.expander("⚙️ 나만의 커스텀 카테고리 태그 추가/관리하기", expanded=False):
            c_input, c_btn = st.columns([3, 1])
            with c_input:
                new_cat = st.text_input("➕ 카테고리 추가", placeholder="예: 운동, 알바, 공부 등", label_visibility="collapsed")
            with c_btn:
                if st.button("태그 추가 등록", use_container_width=True):
                    if new_cat and new_cat not in st.session_state.custom_categories:
                        st.session_state.custom_categories.append(new_cat)
                        st.toast(f"'{new_cat}' 태그가 등록되었습니다!")
                        st.rerun()
            
            st.markdown("  \n".join([f"- 현재 사용 가능한 태그 목록: {', '.join([f'`{c}`' for c in st.session_state.custom_categories])}"]))
            
        # 💡 구분선(---)을 없애고 바로 달력 아코디언이 이어지도록 유도
        if "시작시간" in df.columns:
            df['날짜'] = df['시작시간'].apply(lambda x: str(x).split(" ")[0] if " " in str(x) else str(x))
            unique_dates = sorted(df['날짜'].unique())
            
            updated_events = []
            
            for date in unique_dates:
                with st.expander(f"📅 {date} 일자 계획 확인하기", expanded=True):
                    day_df = df[df['날짜'] == date].sort_values(by="시작시간", ascending=True)
                    
                    for idx, row in day_df.iterrows():
                        event_key = f"cat_{row['시작시간']}_{idx}"
                        toggle_key = f"toggle_{row['시작시간']}_{idx}"
                        
                        start_time = str(row.get('시작시간', '00:00')).split(" ")[1] if " " in str(row.get('시작시간', '')) else "00:00"
                        end_time = str(row.get('종료시간', '23:59')).split(" ")[1] if " " in str(row.get('종료시간', '')) else "23:59"
                        
                        note_content = str(row.get('비고', '')).strip()
                        if note_content and note_content != "None" and note_content != "nan":
                            note_str = f" ({note_content})"
                        else:
                            note_str = ""
                            
                        current_val = row['카테고리'] if row['카테고리'] in st.session_state.custom_categories else "카테고리 없음"
                        
                        if st.session_state.get(toggle_key, False):
                            c_btn, c_select, c_txt = st.columns([1.5, 2.0, 5.5])
                        else:
                            c_btn, c_txt = st.columns([1.5, 7.5])
                        
                        with c_btn:
                            is_edit_mode = st.checkbox(f"🏷️ [{current_val}]", key=toggle_key, help="클릭하여 카테고리 수정")
                            
                        if is_edit_mode:
                            with c_select:
                                selected_cat = st.selectbox(
                                    "변경",
                                    options=st.session_state.custom_categories,
                                    index=st.session_state.custom_categories.index(current_val),
                                    key=event_key,
                                    label_visibility="collapsed"
                                )
                                row['car_category'] = selected_cat # 내부 데이터 정합성 유지
                                row['카테고리'] = selected_cat
                        else:
                            selected_cat = current_val
                                
                        with c_txt:
                            st.markdown(f"⏰ {start_time} ~ {end_time} - **{row.get('내용', '내용 없음')}**{note_str}")
                        
                        updated_events.append(row.to_dict())
            
            st.session_state.confirmed_events = updated_events

    else:
        st.info("아직 확정된 일정이 없습니다. AI 비서 탭에서 일정을 조율해 보세요!")
        
    st.markdown("---")
    if st.button("🚨 시스템 전체 초기화 (대화 내역 + 일정표)"):
        st.session_state.chat_messages = []
        st.session_state.confirmed_events = []
        st.session_state.custom_categories = ["카테고리 없음", "회사", "여가", "개인"]
        st.rerun()