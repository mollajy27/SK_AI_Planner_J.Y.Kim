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

# 날짜 검색용 데이터 사전 생성 (파이썬이 직접 계산)
date_mapping = {}
for i in range(1, 15):
    future_date = now + timedelta(days=i)
    day_name = weekday_list[future_date.weekday()]
    date_mapping[f"{future_date.strftime('%Y-%m-%d')} ({day_name})"] = future_date.strftime('%Y-%m-%d')

# 2. AI 에이전트 시스템 프롬프트 (최종 고도화 버전)
system_instruction = f"""당신은 제공된 '날짜 데이터 사전'을 검색하여 정확한 날짜를 매칭하는 일정 관리 비서입니다.

★ 날짜 인식 및 계산 절대 규칙:
- 계산하지 마세요. 아래 [향후 2주간의 날짜 데이터 사전]을 보고 사용자가 말하는 요일과 날짜를 매칭하세요.
- 오늘 날짜: {now.strftime('%Y-%m-%d')} ({current_weekday})

[향후 2주간의 날짜 데이터 사전]
{json.dumps(date_mapping, ensure_ascii=False, indent=2)}

★ 유연한 맥락 이해 및 연쇄 일정 처리 규칙:
1. 메인 일정의 '취소/이동' 요청 시, 전후의 종속 일정(셔틀버스 등)도 함께 연쇄 삭제/이동하세요.
2. [이동시]: 기존 날짜의 종속 일정은 삭제하고, 새로운 날짜의 메인 일정 시작 시간에 맞춰 적절한 시차를 계산해 종속 일정을 새로 생성하세요.
3. [상황 인지]: 9시~22시가 가득 찼다면 무리하게 배치하지 말고 대안을 제시하세요.
4. [시간 포맷]: 사용자가 종료시간을 명시하지 않은 일정(예: 셔틀 탑승)은 종료시간을 시작시간과 동일하게 기록하세요.

★ JSON 데이터 출력의 절대 규칙:
- [JSON_DATA]와 [/JSON_DATA] 마커 안에 순수 JSON 데이터만 출력하세요.
- 백틱(```)이나 'json' 문자를 절대 붙이지 마세요.
"""

if "chat_messages" not in st.session_state: st.session_state.chat_messages = []
if "confirmed_events" not in st.session_state: st.session_state.confirmed_events = []
if "custom_categories" not in st.session_state: st.session_state.custom_categories = ["카테고리 없음", "회사", "여가", "개인"]

def update_category_callback(target_idx, select_key, toggle_key):
    if select_key in st.session_state:
        st.session_state.confirmed_events[target_idx]['카테고리'] = st.session_state[select_key]
        st.session_state[toggle_key] = False

tab1, tab2 = st.tabs(["🤖 AI 비서와 실시간 조율", "📅 나의 확정 일정표 (List-up)"])

with tab1:
    st.subheader("💬 AI 에이전트에게 일정을 말해보세요")
    user_input = st.chat_input("예: '다음주 월요일 13:30 셔틀버스 타야 해.'")
    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        api_messages = [{"role": "system", "content": system_instruction}] + st.session_state.chat_messages
        with st.spinner("AI 비서가 연산 중..."):
            completion = client.chat.completions.create(model="gpt-4o-mini", messages=api_messages, temperature=0.0)
            raw_response = completion.choices[0].message.content
            if "[JSON_DATA]" in raw_response:
                try:
                    data_part = raw_response.split("[JSON_DATA]")[1].split("[/JSON_DATA]")[0].strip()
                    new_data = json.loads(data_part)
                    
                    # 💡 핵심 방어 코드: 단일 딕셔너리면 리스트로 감싸고, 이미 리스트면 그대로 유지
                    if isinstance(new_data, dict):
                        st.session_state.confirmed_events = [new_data]
                    elif isinstance(new_data, list):
                        st.session_state.confirmed_events = new_data
                        
                except Exception as e:
                    st.error(f"데이터 파싱 오류: {e}")
            st.session_state.chat_messages.append({"role": "assistant", "content": raw_response})
        st.rerun()
    for message in reversed(st.session_state.chat_messages):
        with st.chat_message(message["role"]): st.write(message["content"].split("[JSON_DATA]")[0])

with tab2:
    if st.session_state.confirmed_events:
        df = pd.DataFrame(st.session_state.confirmed_events)
        df = df.sort_values(by="시작시간").reset_index(drop=True)
        # 데이터프레임이 변경될 때마다 session_state 동기화
        st.session_state.confirmed_events = df.to_dict(orient="records")
        
        unique_dates = sorted(df['시작시간'].apply(lambda x: x.split(" ")[0]).unique())
        
        for date in unique_dates:
            with st.expander(f"📅 {date} 일자 계획 확인", expanded=True):
                day_df = df[df['시작시간'].str.contains(date)]
                
                for idx, row in day_df.iterrows():
                    # 안전한 키 생성: 인덱스와 시간 정보를 조합
                    event_key = f"sel_{date}_{idx}"
                    toggle_key = f"tog_{date}_{idx}"
                    
                    # session_state에 키가 없으면 초기화
                    if toggle_key not in st.session_state: st.session_state[toggle_key] = False
                    
                    s_t = datetime.strptime(row['시작시간'], "%Y-%m-%d %H:%M")
                    e_t = datetime.strptime(row['종료시간'], "%Y-%m-%d %H:%M")
                    time_display = f"⏰ {s_t.strftime('%H:%M')}" if s_t >= e_t else f"⏰ {s_t.strftime('%H:%M')} ~ {e_t.strftime('%H:%M')}"
                    
                    c1, c2 = st.columns([2, 8])
                    with c1:
                        # 키를 안정적으로 호출
                        is_edit = st.checkbox(f"🏷️ {row.get('카테고리', '카테고리 없음')}", key=toggle_key)
                    
                    with c2:
                        if is_edit:
                            st.selectbox("변경", st.session_state.custom_categories, 
                                         index=st.session_state.custom_categories.index(row.get('카테고리', '카테고리 없음')),
                                         key=event_key, on_change=update_category_callback, 
                                         args=(idx, event_key, toggle_key))
                        else:
                            st.markdown(f"**{time_display} - {row['내용']}**")
    else:
        st.info("일정이 없습니다.")
        
    if st.button("🚨 시스템 전체 초기화"):
        st.session_state.chat_messages = []
        st.session_state.confirmed_events = []
        st.rerun()