import streamlit as st
from openai import OpenAI
import pandas as pd
import json
from datetime import datetime, timedelta

st.set_page_config(page_title="AI 유연한 일정 관리 비서", layout="wide")

# API 설정
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except KeyError:
    st.error("Streamlit Cloud 설정에서 OPENAI_API_KEY를 등록해 주세요!")
    st.stop()

client = OpenAI(api_key=api_key)

# 1. 시간 및 날짜 사전 생성 (파이썬이 직접 계산하여 AI에게 정답 제공)
now = datetime.now() + timedelta(hours=9)
weekday_list = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
date_mapping = {}

for i in range(1, 15):
    future_date = now + timedelta(days=i)
    day_name = weekday_list[future_date.weekday()]
    # AI가 직관적으로 매칭할 수 있도록 고정 키 생성
    key_name = f"이번주 {day_name}" if i <= 7 else f"다음주 {day_name}"
    date_mapping[key_name] = future_date.strftime('%Y-%m-%d')

# 2. 시스템 프롬프트 (최종 고도화: 날짜 사전 기반 검색형)
system_instruction = f"""당신은 제공된 '날짜 데이터 사전'에서 날짜를 검색하여 대답하는 일정 관리 비서입니다.

★ 날짜 인식 규칙 (절대 준수):
1. 사용자가 날짜(다음 주 화요일 등)를 물으면, 아래 [날짜 데이터 사전]에서 해당 키를 찾아 값을 답변하세요.
2. 절대 달력을 직접 계산하지 마세요. (계산은 파이썬이 완료한 데이터를 믿으세요.)
3. 종료시간 미지정 시 시작시간과 종료시간을 동일하게 JSON에 담으세요.

[날짜 데이터 사전]
{json.dumps(date_mapping, ensure_ascii=False, indent=2)}

★ 데이터 출력 규칙:
- [JSON_DATA]와 [/JSON_DATA] 마커 안에 순수 JSON 리스트만 출력하세요.
"""

# 세션 초기화
if "chat_messages" not in st.session_state: st.session_state.chat_messages = []
if "confirmed_events" not in st.session_state: st.session_state.confirmed_events = []
if "custom_categories" not in st.session_state: st.session_state.custom_categories = ["카테고리 없음", "회사", "여가", "개인"]

def update_category_callback(target_idx, select_key, toggle_key):
    if select_key in st.session_state:
        st.session_state.confirmed_events[target_idx]['카테고리'] = st.session_state[select_key]
        st.session_state[toggle_key] = False

tab1, tab2 = st.tabs(["🤖 AI 비서와 실시간 조율", "📅 나의 확정 일정표"])

with tab1:
    user_input = st.chat_input("일정을 말씀해 주세요.")
    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        api_messages = [{"role": "system", "content": system_instruction}] + st.session_state.chat_messages
        
        with st.spinner("AI가 계산 중..."):
            completion = client.chat.completions.create(model="gpt-4o-mini", messages=api_messages, temperature=0.0)
            raw_response = completion.choices[0].message.content
            st.session_state.chat_messages.append({"role": "assistant", "content": raw_response})
            
            if "[JSON_DATA]" in raw_response:
                try:
                    data_part = raw_response.split("[JSON_DATA]")[1].split("[/JSON_DATA]")[0].strip()
                    new_data = json.loads(data_part)
                    st.session_state.confirmed_events = [new_data] if isinstance(new_data, dict) else new_data
                except: pass
        st.rerun()

    for message in reversed(st.session_state.chat_messages):
        with st.chat_message(message["role"]): st.markdown(message["content"].split("[JSON_DATA]")[0])

with tab2:
    if st.session_state.confirmed_events:
        valid_events = [e for e in st.session_state.confirmed_events if isinstance(e, dict) and '시작시간' in e]
        df = pd.DataFrame(valid_events).sort_values(by="시작시간").reset_index(drop=True)
        st.session_state.confirmed_events = df.to_dict(orient="records")
        
        for date in sorted(df['시작시간'].apply(lambda x: x.split(" ")[0]).unique()):
            with st.expander(f"📅 {date} 계획", expanded=True):
                day_df = df[df['시작시간'].str.contains(date)]
                for idx, row in day_df.iterrows():
                    event_key, toggle_key = f"sel_{date}_{idx}", f"tog_{date}_{idx}"
                    if toggle_key not in st.session_state: st.session_state[toggle_key] = False
                    
                    s_t, e_t = datetime.strptime(row['시작시간'], "%Y-%m-%d %H:%M"), datetime.strptime(row['종료시간'], "%Y-%m-%d %H:%M")
                    time_display = f"⏰ {s_t.strftime('%H:%M')}" if s_t >= e_t else f"⏰ {s_t.strftime('%H:%M')} ~ {e_t.strftime('%H:%M')}"
                    
                    c1, c2 = st.columns([2, 8])
                    with c1: is_edit = st.checkbox(f"🏷️ {row.get('카테고리', '카테고리 없음')}", key=toggle_key)
                    with c2:
                        if is_edit: st.selectbox("변경", st.session_state.custom_categories, index=st.session_state.custom_categories.index(row.get('카테고리', '카테고리 없음')), key=event_key, on_change=update_category_callback, args=(idx, event_key, toggle_key))
                        else: st.markdown(f"**{time_display} - {row.get('내용', '내용 없음')}**")
    
    if st.button("🚨 시스템 전체 초기화"):
        st.session_state.chat_messages = []; st.session_state.confirmed_events = []
        st.rerun()