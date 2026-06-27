import streamlit as st
from openai import OpenAI
import pandas as pd
import json
from datetime import datetime, timedelta

st.set_page_config(page_title="AI 일정 비서", layout="wide")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# 1. 고정된 현재 시간 정보
now = datetime.now() + timedelta(hours=9)
today_str = now.strftime("%Y-%m-%d")
today_weekday = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"][now.weekday()]

# 2. 아주 단순한 프롬프트
system_instruction = f"""당신은 일정 관리 비서입니다.
오늘 날짜: {today_str}, 요일: {today_weekday}
사용자가 날짜를 물으면 오늘로부터 계산하여 정확한 날짜를 답변하세요.
모든 일정은 [JSON_DATA] 안에 JSON 리스트 형식으로만 출력하세요.
"""

if "confirmed_events" not in st.session_state: st.session_state.confirmed_events = []

tab1, tab2 = st.tabs(["채팅", "일정표"])

with tab1:
    user_input = st.chat_input("일정을 입력하세요")
    if user_input:
        messages = [{"role": "system", "content": system_instruction}] + [{"role": "user", "content": user_input}]
        res = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
        content = res.choices[0].message.content
        
        st.write(content.split("[JSON_DATA]")[0])
        if "[JSON_DATA]" in content:
            try:
                data = json.loads(content.split("[JSON_DATA]")[1].split("[/JSON_DATA]")[0])
                st.session_state.confirmed_events = data if isinstance(data, list) else [data]
            except: pass

with tab2:
    if st.session_state.confirmed_events:
        for event in st.session_state.confirmed_events:
            st.write(f"{event.get('시작시간')} - {event.get('내용')}")
    if st.button("초기화"):
        st.session_state.confirmed_events = []
        st.rerun()