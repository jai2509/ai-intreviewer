import streamlit as st
import requests
import os
import time
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from streamlit_webrtc import webrtc_streamer
import av
import tempfile
import wave

load_dotenv()

# API KEYS
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY")
JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")

# App Title
st.set_page_config(page_title="AI Interviewer")
st.title("🤖 AI Interviewer - Voice Based Job Interview")

# Resume Parsing
st.header("📄 Upload Your Resume (PDF)")
uploaded_file = st.file_uploader("Upload Resume", type=["pdf"])
resume_text = ""

if uploaded_file is not None:
    reader = PdfReader(uploaded_file)
    resume_text = ""
    for page in reader.pages:
        resume_text += page.extract_text()
    st.success("✅ Resume uploaded and parsed successfully!")

# Role Selection
roles = ["Data Scientist", "Machine Learning Engineer", "Backend Developer", "Frontend Developer", "Product Manager"]
selected_role = st.selectbox("🎯 Select the role you're applying for:", roles)

# Generate Interview Questions
def generate_questions(resume_text, role):
    prompt = f"""You are an AI Interviewer. Based on the candidate's resume and their selected role "{role}", generate 3 job-specific interview questions.

Resume:
{resume_text}
"""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "model": "llama3-8b-8192"
    }
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
    return response.json()['choices'][0]['message']['content'].strip().split("\n")

if st.button("🧠 Generate Interview Questions"):
    if resume_text and selected_role:
        questions = generate_questions(resume_text, selected_role)
        st.session_state["questions"] = [q for q in questions if q.strip()]
        st.success("Interview questions generated successfully!")
    else:
        st.error("Please upload a resume and select a role.")

# 🎤 Audio Recorder Class
class AudioRecorder:
    def __init__(self):
        self.frames = []

    def recv(self, frame: av.AudioFrame):
        audio = frame.to_ndarray()
        self.frames.append(audio)
        return frame

# Transcription with AssemblyAI
def transcribe_audio(filepath):
    headers = {'authorization': ASSEMBLY_API_KEY}
    with open(filepath, 'rb') as f:
        response = requests.post('https://api.assemblyai.com/v2/upload', headers=headers, files={'file': f})
        upload_url = response.json()['upload_url']

    json_data = {'audio_url': upload_url}
    transcript_response = requests.post('https://api.assemblyai.com/v2/transcript', json=json_data, headers=headers)
    transcript_id = transcript_response.json()['id']

    while True:
        polling = requests.get(f'https://api.assemblyai.com/v2/transcript/{transcript_id}', headers=headers)
        status = polling.json()['status']
        if status == 'completed':
            return polling.json()['text']
        elif status == 'error':
            return "Transcription failed."
        time.sleep(3)

# 🎙️ Interview Interface
if "questions" in st.session_state:
    st.header("🎙️ Voice Interview")
    for idx, question in enumerate(st.session_state["questions"]):
        st.subheader(f"Q{idx+1}: {question}")
        st.info("🎤 Record your answer below and then click Submit")

        recorder = AudioRecorder()
        webrtc_ctx = webrtc_streamer(
            key=f"interview_audio_{idx}",
            audio_receiver_size=1024,
            sendback_audio=False,
            media_stream_constraints={"audio": True, "video": False},
            audio_frame_callback=recorder.recv,
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
        )

        if st.button(f"✅ Submit Answer for Q{idx+1}", key=f"submit_{idx}"):
            if not recorder.frames:
                st.error("No audio recorded.")
            else:
                # Save WAV
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                    wav_path = f.name
                    wf = wave.open(wav_path, 'wb')
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(48000)
                    for frame in recorder.frames:
                        wf.writeframes(frame.tobytes())
                    wf.close()

                transcription = transcribe_audio(wav_path)
                st.write(f"🗣️ Your Answer: {transcription}")
                st.session_state[f"answer_{idx}"] = transcription

# Suggest Jobs using Jooble API
def suggest_jobs(resume_text):
    url = f"https://jooble.org/api/{JOOBLE_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "keywords": selected_role,
        "location": "",
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("jobs", [])[:5]
    else:
        return []

if st.button("📌 Suggest Jobs"):
    jobs = suggest_jobs(resume_text)
    if jobs:
        st.subheader("Top Job Recommendations:")
        for job in jobs:
            st.markdown(f"""
                **{job['title']}**  
                🌍 {job['location']}  
                🔗 [Apply Here]({job['link']})  
                """)
    else:
        st.error("Could not fetch job recommendations.")
