import streamlit as st
from openai import OpenAI

# 1. 웹 페이지 제목 및 안내
st.set_page_config(page_title="AI 유연한 일정 관리 비서", layout="centered")
st.title("📅 AI 기반 우선순위 플래너")
st.write("기존 엑셀 플래너의 번거로움을 해결하는 유연한 일정 재배치 에이전트입니다.")

# 2. OpenAI API 키 설정 (과제 시 발급받은 키를 넣거나 입력받는 창을 만듭니다)
# 임시로 입력창 형태로 구성
api_key = st.sidebar.text_input("OpenAI API Key를 입력하세요", type="password")

if api_key:
    client = OpenAI(api_key=api_key)

    # 3. 챗봇 대화 기록 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": "당신은 사용자의 일정을 효율적으로 관리하고 조율해 주는 전문 비서 에이전트입니다. 사용자가 고정 일정과 유연한 작업을 말하면, 우선순위와 마감일을 고려해 최적의 타임라인을 추천해 주세요. 일정 변경 요청 시 유연하게 재배치해야 합니다."}
        ]

    # 4. 기존 대화 내용 화면에 표시
    for message in st.session_state.messages:
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                st.write(message["content"])

    # 5. 사용자 입력 받기
    if user_input := st.chat_input("예: '이번 주 일요일까지 보고서 써야 해. 중간에 운동 3번 가고 싶어.'"):
        # 사용자 메시지 화면에 표시 및 저장
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        # AI 답변 생성
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            
            # API 호출
            completion = client.chat.completions.create(
                model="gpt-4o-mini", # 비용이 저렴하고 빠른 모델 추천
                messages=st.session_state.messages
            )
            
            ai_response = completion.choices[0].message.content
            response_placeholder.write(ai_response)
            
        # AI 메시지 저장
        st.session_state.messages.append({"role": "assistant", "content": ai_response})
else:
    st.info("시작하려면 왼쪽 사이드바에 OpenAI API Key를 입력해 주세요.")