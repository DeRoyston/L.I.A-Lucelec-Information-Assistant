import streamlit as st


def main():
    st.markdown("""
    <style>
    .voice-recorder-box {
        border: 1px solid #cbd5e1;
        border-radius: 10px;
        padding: 12px;
        background: #f8fafc;
        margin-bottom: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="voice-recorder-box">', unsafe_allow_html=True)
    st.write("Click the button below to record a short message using your browser microphone.")

    transcript = st.text_input("Voice draft", key="voice_recorder_input", placeholder="Speech will appear here")
    if transcript:
        st.session_state.voice_recorder_result = transcript

    st.button("Start voice capture", key="voice_recorder_button")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("Use captured text", key="voice_recorder_use"):
        st.session_state.voice_recorder_result = st.session_state.get("voice_recorder_input", "")

    if "voice_recorder_result" in st.session_state:
        st.session_state.voice_recorder_output = st.session_state.voice_recorder_result

    st.write("Tip: if your browser does not allow microphone access, type your question manually instead.")


if __name__ == "__main__":
    main()
