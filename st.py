import subprocess
import streamlit as st
from threading import Thread
from queue import Queue, Empty

# Streamlit 제목 설정
st.title("Real-Time Terminal Interaction in Streamlit")

# Python 스크립트 실행 경로
script_path = "main.py"

# Streamlit 상태 초기화
if "logs" not in st.session_state:
    st.session_state.logs = []
if "terminal_input" not in st.session_state:
    st.session_state.terminal_input = ""
if "input_queue" not in st.session_state:
    st.session_state.input_queue = Queue()
if "process_running" not in st.session_state:
    st.session_state.process_running = False

# Streamlit의 로그 영역
log_area = st.empty()

# 터미널 입력 영역
user_input = st.text_input("Enter your terminal input:", key="terminal_input", placeholder="Type your input and press enter...")

# 로그 데이터를 읽어오는 함수
def stream_logs(process, log_queue, input_queue):
    while True:
        output = process.stdout.readline()
        if output == "" and process.poll() is not None:
            break
        if output:
            log_queue.put(output.strip())  # 로그 데이터를 Queue에 추가

        # 사용자 입력이 있을 경우 처리
        try:
            user_input = input_queue.get_nowait()
            if user_input:
                process.stdin.write(user_input + "\n")
                process.stdin.flush()
        except Empty:
            continue

# 워크플로우 실행 버튼
if st.button("Run Workflow", key="run_workflow") and not st.session_state.process_running:
    st.session_state.process_running = True

    # 로그와 입력을 위한 큐 생성
    log_queue = Queue()
    input_queue = st.session_state.input_queue

    # Subprocess 실행
    process = subprocess.Popen(
        ["python", script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        text=True,
        bufsize=1,  # 실시간 출력 버퍼 설정
    )

    # 로그 스트리밍 쓰레드 시작
    log_thread = Thread(target=stream_logs, args=(process, log_queue, input_queue), daemon=True)
    log_thread.start()

    # 로그를 UI에 실시간으로 업데이트
    while process.poll() is None or not log_queue.empty():
        try:
            # 로그를 읽어 Streamlit UI에 업데이트
            log_line = log_queue.get(timeout=0.1)
            st.session_state.logs.append(log_line)
            log_area.text("\n".join(st.session_state.logs))
        except Empty:
            pass

    # 프로세스 종료 상태 확인
    return_code = process.wait()
    if return_code == 0:
        st.success("Workflow execution completed successfully!")
    else:
        st.error(f"Workflow execution failed with return code {return_code}.")

# 사용자 입력 제출 버튼
if st.button("Submit Input", key="submit_input"):
    st.session_state.input_queue.put(st.session_state.terminal_input)
    st.session_state.terminal_input = ""  # 입력 필드 초기화
