import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="AI 유연한 일정 관리 비서", layout="centered")
st.title("📅 AI 기반 우선순위 플래너")
st.write("기존 엑셀 플래너의 번거로움을 해결하는 유연한 일정 재배치 에이전트입니다.")

# 💡 [수정된 부분] 다른 사람이 키를 입력할 필요 없이, 시스템 내부 비밀 금고에서 키를 꺼내옵니다.
# (Streamlit Cloud의 Secrets 기능을 연동할 것입니다)
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except KeyError:
    st.error("Streamlit Cloud 설정에서 OPENAI_API_KEY를 등록해 주세요!")
    st.stop()

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=api_key)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "당신은 사용자의 일정을 효율적으로 관리하고 조율해 주는 전문 비서 에이전트입니다. 사용자가 고정 일정과 유연한 작업을 말하면, 우선순위와 마감일을 고려해 최적의 타임라인을 추천해 주세요. 일정 변경 요청 시 유연하게 재배치해야 합니다. 가독성 좋게 이모지와 불릿 포인트를 사용하세요."}
    ]

for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.write(message["content"])

if user_input := st.chat_input("예: '이번 주 목요일 전공 시험이야. 일정 좀 짜줘.'"):
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state.messages
        )
        
        ai_response = completion.choices[0].message.content
        response_placeholder.write(ai_response)
        
    st.session_state.messages.append({"role": "assistant", "content": ai_response})