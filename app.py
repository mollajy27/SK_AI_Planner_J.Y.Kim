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

# 2. AI 에이전트 시스템 프롬프트 (맥락 이해 및 연쇄 취소 규칙 강화)
system_instruction = f"""당신은 기존 플래너의 한계를 극복하는 '유연한 일정 관리 에이전트'입니다.
사용자와 대화하며 일정을 조율해 주세요.

★ 매우 중요 (날짜 계산 가이드):
- 현재 사용자 기준 시각: [{current_time_str}] / 오늘 요일: [{current_weekday}]
- 사용자가 '다음 주 월요일'이나 '다음 주 평일'을 언급할 때, 오늘이 주말(금, 토, 일)이라면 그것은 2주 뒤가 아니라 **바로 다가오는 직근 평일(돌아오는 가장 가까운 월요일)**을 의미합니다. 절대 오해하지 마세요.
- 임의 계산 금지. 반드시 아래의 [정확한 날짜 및 요일 테이블]에서 오늘 날짜와 가장 가까운 미래의 요일을 매칭하세요.

[정확한 날짜 및 요일 테이블]
{calendar_hint}

★ 유연한 맥락 이해 및 연쇄 일정 처리 규칙 (★신규 추가):
1. 사용자가 특정 메인 일정(예: 운전 연수, 외근, 병원 진료 등)의 '취소'나 '변경'을 요청할 때, 그 일정을 위해 존재하는 선행/후행 일정(예: 셔틀버스 탑승, 이동 시간, 준비 시간 등)이 목록에 있다면 이를 인간의 상식선에서 한 세트로 판단하세요.
2. 예컨대 '운전 연수가 취소되었다'고 하면, 그 연수에 참석하기 위해 전후로 붙어 있는 '운전학원 셔틀버스 탑승' 일정 역시 자동으로 함께 취소(삭제)하여 JSON 데이터에 반영해야 합니다. 사용자가 두 번 말하게 하지 마세요.

★ JSON 데이터 출력의 절대 규칙 (반드시 준수):
1. 모든 일정은 시작시간과 종료시간을 'YYYY-MM-DD HH:mm' 형식으로 명확히 기록하세요.
2. '카테고리' 값은 항상 "카테고리 없음"으로 통일하세요.
3. 사용자가 새로운 일정을 말하거나 수정하면, 누적된 최신 전체 일정 목록을 답변 맨 마지막 줄에 단 한 번만 아래 포맷으로 출력하세요.
4. 중요: [JSON_DATA]와 [/JSON_DATA] 마커 안팎에 백틱(```)이나 'json' 문자를 절대 붙이지 마세요. 순수한 텍스트 문자열 형태로만 위치시켜야 시스템이 파싱할 수 있습니다.

[출력 포맷 예시]
(사용자에게 친절히 안내하는 대화 내용 입력)
[JSON_DATA][{{"시작시간": "2026-06-29 13:30", "종료시간": "2026-06-29 14:30", "내용": "셔틀버스 탑승", "비고": "", "카테고리": "카테고리 없음"}}][/JSON_DATA]
"""

# Session State 초기화
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "confirmed_events" not in st.session_state:
    st.session_state.confirmed_events = []

if "custom_categories" not in st.session_state:
    st.session_state.custom_categories = ["카테고리 없음", "회사", "여가", "개인"]

# 💡 [안정성 확보]: 카테고리 변경 시 안전하게 데이터를 처리하고 편집창을 닫는 콜백 함수
def update_category_callback(target_idx, select_key, toggle_key):
    if select_key in st.session_state:
        chosen_cat = st.session_state[select_key]
        # 데이터프레임 순서에 맞춰 해당 행의 카테고리 업데이트
        st.session_state.confirmed_events[target_idx]['카테고리'] = chosen_cat
        # 수정을 완료했으므로 체크박스 상태를 강제로 꺼짐(False) 처리
        st.session_state[toggle_key] = False

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
                    messages=api_messages,
                    temperature=0.0
                )
                raw_response = completion.choices[0].message.content
                
                if "[JSON_DATA]" in raw_response and "[/JSON_DATA]" in raw_response:
                    try:
                        data_part = raw_response.split("[JSON_DATA]")[1].split("[/JSON_DATA]")[0].strip()
                        data_part = data_part.replace("```json", "").replace("```", "").strip()
                        
                        new_events = json.loads(data_part)
                        if isinstance(new_events, list):
                            # [데이터 보존 기존 로직 유지]
                            current_memory = {f"{ev.get('시작시간')}_{ev.get('내용')}": ev.get('카테고리') for ev in st.session_state.confirmed_events if ev.get('카테고리') != "카테고리 없음"}
                            
                            for new_ev in new_events:
                                match_key = f"{new_ev.get('시작시간')}_{new_ev.get('내용')}"
                                if match_key in current_memory:
                                    new_ev['카테고리'] = current_memory[match_key]
                                    
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
        # 데이터 정렬 후 session_state에 리스트 형태로 즉시 재반영 (인덱스 일치를 위함)
        df = pd.DataFrame(st.session_state.confirmed_events)
        if "카테고리" not in df.columns:
            df["카테고리"] = "카테고리 없음"
        if "시작시간" in df.columns:
            df = df.sort_values(by="시작시간", ascending=True).reset_index(drop=True)
        st.session_state.confirmed_events = df.to_dict(orient="records")
        
        # 1. 실시간 데이터프레임 원본 표 보기
        with st.expander("📋 실시간 동기화된 타임라인 전체 목록 (표 형태로 보기)", expanded=False):
            display_cols = [c for c in ["카테고리", "시작시간", "종료시간", "내용", "비고"] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True)
        
        st.markdown("---")
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
            
        # 날짜 분리 알고리즘
        df_render = pd.DataFrame(st.session_state.confirmed_events)
        df_render['날짜'] = df_render['시작시간'].apply(lambda x: str(x).split(" ")[0] if " " in str(x) else str(x))
        unique_dates = sorted(df_render['날짜'].unique())
        
        for date in unique_dates:
            with st.expander(f"📅 {date} 일자 계획 확인하기", expanded=True):
                # 💡 원본 리스트(confirmed_events)와 동기화하기 위해 원본의 index 값을 유지한 채 렌더링
                day_df = df_render[df_render['날짜'] == date]
                
                for idx, row in day_df.iterrows():
                    event_key = f"select_{row['시작시간']}_{idx}"
                    toggle_key = f"toggle_{row['시작시간']}_{idx}"
                    
                    start_time = str(row.get('시작시간', '00:00')).split(" ")[1] if " " in str(row.get('시작시간', '')) else "00:00"
                    end_time = str(row.get('종료시간', '23:59')).split(" ")[1] if " " in str(row.get('종료시간', '')) else "23:59"
                    
                    note_content = str(row.get('비고', '')).strip()
                    note_str = f" ({note_content})" if note_content and note_content not in ["None", "nan", ""] else ""
                        
                    current_val = row['카테고리'] if row['카테고리'] in st.session_state.custom_categories else "카테고리 없음"
                    
                    # 수정을 위해 체크박스가 활성화되었을 때만 3열 레이아웃 구성
                    if st.session_state.get(toggle_key, False):
                        c_btn, c_select, c_txt = st.columns([1.5, 2.0, 5.5])
                    else:
                        c_btn, c_txt = st.columns([1.5, 7.5])
                    
                    with c_btn:
                        is_edit_mode = st.checkbox(f"🏷️ [{current_val}]", key=toggle_key, help="클릭하여 카테고리 수정")
                        
                    if is_edit_mode:
                        with c_select:
                            # 💡 [정석적 닫기 처리]: on_change와 args를 활용해 변경 즉시 안전하게 백엔드 데이터를 바꾸고 창을 닫음
                            st.selectbox(
                                "변경",
                                options=st.session_state.custom_categories,
                                index=st.session_state.custom_categories.index(current_val),
                                key=event_key,
                                label_visibility="collapsed",
                                on_change=update_category_callback,
                                args=(idx, event_key, toggle_key)
                            )
                            
                    with c_txt:
                        text_html = f"""
                        <div style='display: flex; align-items: center; min-height: 40px; font-size: 16px;'>
                            <span>⏰ {start_time} ~ {end_time} - <b>{row.get('내용', '내용 없음')}</b>{note_str}</span>
                        </div>
                        """
                        st.markdown(text_html, unsafe_allow_html=True)

    else:
        st.info("아직 확정된 일정이 없습니다. AI 비서 탭에서 일정을 조율해 보세요!")
        
    st.markdown("---")
    if st.button("🚨 시스템 전체 초기화 (대화 내역 + 일정표)"):
        st.session_state.chat_messages = []
        st.session_state.confirmed_events = []
        st.session_state.custom_categories = ["카테고리 없음", "회사", "여가", "개인"]
        st.rerun()