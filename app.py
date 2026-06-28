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

# 2. AI 에이전트 시스템 프롬프트 (일정 이동/변경 연쇄 연산 로직 추가)
system_instruction = f"""당신은 기존 플래너의 한계를 극복하는 '유연한 일정 관리 에이전트'입니다.
사용자와 대화하며 일정을 조율해 주세요.

★ [강제 준수] 날짜 및 요일 계산 알고리즘:
1. 기준점 인지: 항상 [현재 시스템 인지 시각]을 기준으로 삼으세요.
2. 상대적 표현 해석 원칙:
   - "이번 주 [요일]": 현재 날짜가 포함된 주의 해당 요일을 의미함.
   - "다음 주 [요일]": 현재 날짜가 포함된 주의 다음 주에 위치한 해당 요일을 의미함.
3. 2단계 검증 로직 (반드시 수행):
   - STEP 1: 제공된 [정확한 날짜 및 요일 테이블]에서 [현재 시스템 인지 시각]의 요일 위치를 찾으세요.
   - STEP 2: 사용자가 말한 요일을 테이블에서 찾아, STEP 1의 날짜보다 이후에 나타나는 첫 번째(이번 주) 혹은 두 번째(다음 주) 해당 요일을 확정하세요.
   - STEP 3: 절대 머릿속으로 '오늘 + 7일' 같은 계산을 하지 마세요. 오직 테이블상의 날짜 매칭값만 정답으로 채택하세요.
4. 만약 테이블에 날짜가 없다면 "제공된 달력 범위 내에 없습니다"라고 답변하고, 임의로 날짜를 생성(환각)하지 마세요.

[정확한 날짜 및 요일 테이블 - AI 전용 참조 자료]
(이 테이블을 위에서부터 차례대로 스캔하여 날짜를 매칭하세요.)
{calendar_hint}

★ [일정 충돌 방지 및 검증 규칙 - 필수]:
1. 새로운 일정을 생성하거나 이동할 때, 반드시 제공된 기존 일정 목록(confirmed_events)을 먼저 확인하세요.
2. 기존 일정과 시간이 겹치면 무조건 "충돌 발생"을 알리고, 대안을 제시하며 사용자의 승인을 받으세요. 
3. [금지]: 사용자의 요청이라도 기존 일정을 마음대로 삭제하거나 덮어쓰지 마세요. 반드시 충돌 상황을 먼저 보고하세요.

★ [강제 검증 루틴 - 절대로 생략 금지]:
1. 사용자가 일정을 '추가'하거나 '이동' 요청을 하면, 즉시 [현재 확정된 일정 목록]과 시간을 대조하세요.
2. [충돌 체크]: 
    - 겹치는 시간대가 1분이라도 있다면 즉시 작업을 멈추세요.
    - "충돌 감지: 목요일 15:00~16:00에 외부 미팅이 있습니다."와 같이 구체적으로 보고하세요.
3. [대안 제시]: 
    - 충돌 시, 사용자가 요청한 일정을 수정할 대안(시간 변경, 기존 일정 삭제 등)을 먼저 물어보세요.
4. [데이터 기록]: 
    - 사용자가 명확히 "괜찮아, 덮어써" 또는 "기존 일정 삭제하고 옮겨"라고 승인하기 전까지는 [JSON_DATA]를 절대 출력하지 마세요.

★ [필수 데이터 보존 및 업데이트 규칙]:
1. 작업 수행 시, 항상 [현재 확정된 일정 목록] 전체를 수정/유지해야 합니다.
2. 특정 일정을 옮기거나 수정하더라도, [현재 확정된 일정 목록]에 포함된 나머지 기존 일정들은 절대로 삭제하거나 누락하지 마세요.
3. 결과물(JSON)을 생성할 때는 반드시 기존 일정 리스트 전체를 포함하여 작성하세요. 
4. 특정 날짜의 일정을 변경한다고 해서 다른 날짜의 일정을 초기화하는 것은 절대 금지입니다.

★ 유연한 맥락 이해 및 연쇄 일정 처리 규칙 (★변경 및 이동 로직 강화):
1. 사용자가 특정 메인 일정(예: 운전 연수, 외근, 세미나 등)의 '취소'를 요청하면, 그 일정을 위해 전후로 존재하던 종속 일정(예: 셔틀버스 탑승, 이동 시간 등)도 함께 연쇄 삭제하세요.
2. [핵심 - 일정 이동시]: 사용자가 메인 일정을 다른 날짜나 시간으로 '변경/이동'하는 경우(예: 월요일 운전 연수 ➡️ 화요일 이동), AI는 다음의 세트 연산을 자동으로 수행해야 합니다.
   - ⓐ 기존 날짜(월요일)에 남겨진 연관 종속 일정(셔틀버스 등)은 귀신같이 찾아내어 함께 **삭제**합니다.
   - ⓑ 새로운 날짜(화요일)의 메인 일정 시작 시간에 맞춰, 기존 시간 간격을 고려한 새로운 종속 일정(화요일 셔틀버스 탑승 등)을 **자동으로 연산하여 생성**하세요. (예: 연수가 2시 15분 시작인데 셔틀버스가 45분 전이었다면, 새로운 화요일 일정에도 연수 시작 45분 전에 셔틀버스 일정을 알아서 계산해 추가합니다.)

★ 인간 중심의 상황 인지 스케줄링 규칙 (필수 준수):
1. [이동 시간 및 완충 시간]: 두 일정의 장소나 성격이 다를 경우, 최소 30분~1시간의 '완충 시간'을 자동으로 확보하고 일정을 추천하세요. (빽빽한 일정은 사용자에게 피로감을 줍니다.)
2. [생체 리듬 기반 배분]: 사용자가 명시하지 않았더라도, 가급적 아침 일찍이나 밤늦은 시간의 작업은 '중요도'가 매우 높은 경우에만 추천하세요. 일상적인 일정은 사용자의 일반적인 활동 시간 내에 배치하세요.
3. [가용 자원 판단]: 9시~22시가 이미 가득 찬 경우, 2시간의 추가 일정을 무리하게 넣기 전에 반드시 사용자에게 '대안'을 제시하세요.
   - 제안 형식: "현재 일정이 꽉 찼습니다. 아침 6시부터 시작하시거나, 밤 11시 이후의 심야 작업이 가능하신가요? 혹은 기존 일정 중 중요도가 낮은 것을 미룰까요?"
4. [최소 수면 보장]: 만약 심야 시간(22시 이후)에 일정을 추가해야 한다면, 다음 날 오전 첫 일정의 시작 시간을 조정할 필요가 있는지 먼저 확인하고 추천하세요.

★ JSON 데이터 출력의 절대 규칙 (반드시 준수):
1. 전체 리스트를 출력하지 마세요. 대신 아래 형식의 '명령어'를 출력하세요.
2. [JSON_DATA]{{"action": "create", "event": {{"시작시간": "YYYY-MM-DD HH:mm", "종료시간": "...", "내용": "..."}}}}[/JSON_DATA]
   또는 [JSON_DATA]{{"action": "delete", "target_keyword": "삭제할 일정 내용"}}[/JSON_DATA]
3. 'target_keyword'를 지정하면 파이썬이 해당 내용이 포함된 일정을 찾아 삭제합니다.
4. 절대 백틱(```)이나 json 문자를 포함하지 마세요.
5. 여러 개의 일정을 생성해야 하는 경우, 각 일정마다 [JSON_DATA] ... [/JSON_DATA]를 개별적으로 작성하여 총 여러 번 출력하세요.

[출력 포맷 예시]
- 새 일정 추가 시 (단일 일정): [JSON_DATA]{{"action": "create", "event": {{"시작시간": "2026-07-06 09:00", "종료시간": "2026-07-06 11:00", "내용": "회사 회의", "비고": "", "카테고리": "카테고리 없음"}}}}[/JSON_DATA]
- 일정 삭제 시: [JSON_DATA]{{"action": "delete", "target_keyword": "세미나"}}[/JSON_DATA]
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
                
# --- [수정된 부분: 모든 JSON 블록을 반복 처리] ---
                if "[JSON_DATA]" in raw_response:
                    # 답변 전체를 [JSON_DATA] 기준으로 쪼갭니다.
                    parts = raw_response.split("[JSON_DATA]")
                    
                    # 0번 인덱스는 일반 텍스트이므로 1번부터 끝까지 루프
                    for part in parts[1:]:
                        if "[/JSON_DATA]" in part:
                            data_part = part.split("[/JSON_DATA]")[0].strip()
                            data_part = data_part.replace("```json", "").replace("```", "").strip()
                            
                            try:
                                action_data = json.loads(data_part)
                                action = action_data.get("action")
                                
                                if action == "create":
                                    new_ev = action_data.get("event")
                                    if new_ev:
                                        # 필드 정합성 체크
                                        if "시작시간" in new_ev and "내용" in new_ev:
                                            new_ev["카테고리"] = "카테고리 없음"
                                            st.session_state.confirmed_events.append(new_ev)
                                
                                elif action == "delete":
                                    target_keyword = action_data.get("target_keyword")
                                    if target_keyword:
                                        st.session_state.confirmed_events = [
                                            ev for ev in st.session_state.confirmed_events 
                                            if target_keyword not in ev.get("내용", "")
                                        ]
                            except Exception as json_err:
                                st.error(f"데이터 처리 오류: {json_err}")
                # ---------------------------------------------
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
                day_df = df_render[df_render['날짜'] == date]
                
                for idx, row in day_df.iterrows():
                    event_key = f"select_{row['시작시간']}_{idx}"
                    toggle_key = f"toggle_{row['시작시간']}_{idx}"
                    
                    # 💡 [시간 표시 로직 보정]: 종료시간이 명시되지 않거나 시작시간과 같을 때를 감지
                    start_time_obj = datetime.strptime(str(row.get('시작시간', '2026-01-01 00:00')), "%Y-%m-%d %H:%M")
                    end_time_obj = datetime.strptime(str(row.get('종료시간', '2026-01-01 23:59')), "%Y-%m-%d %H:%M")
                    
                    start_str = start_time_obj.strftime("%H:%M")
                    end_str = end_time_obj.strftime("%H:%M")
                    
                    # 시작시간과 종료시간이 같으면 시간만, 다르면 범위 표시
                    if start_time_obj >= end_time_obj:
                        time_display = f"⏰ {start_str}"
                    else:
                        time_display = f"⏰ {start_str} ~ {end_str}"
                    
                    note_content = str(row.get('비고', '')).strip()
                    note_str = f" ({note_content})" if note_content and note_content not in ["None", "nan", ""] else ""
                        
                    current_val = row['카테고리'] if row['카테고리'] in st.session_state.custom_categories else "카테고리 없음"
                    
                    if st.session_state.get(toggle_key, False):
                        c_btn, c_select, c_txt = st.columns([1.5, 2.0, 5.5])
                    else:
                        c_btn, c_txt = st.columns([1.5, 7.5])
                    
                    with c_btn:
                        is_edit_mode = st.checkbox(f"🏷️ [{current_val}]", key=toggle_key, help="클릭하여 카테고리 수정")
                        
                    if is_edit_mode:
                        with c_select:
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
                        # 💡 여기에 위에서 계산한 time_display 변수를 적용
                        text_html = f"""
                        <div style='display: flex; align-items: center; min-height: 40px; font-size: 16px;'>
                            <span>{time_display} - <b>{row.get('내용', '내용 없음')}</b>{note_str}</span>
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