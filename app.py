import streamlit as st
import os
import tempfile
import requests
import time
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from streamlit_webrtc import webrtc_streamer
import av
import numpy as np
import wave

# Load API keys
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY")
JOOOBLE_API_KEY = os.getenv("JOOOBLE_API_KEY")

st.set_page_config(page_title="AI Interviewer", layout="centered")
st.title("🧠 AI Interviewer with Voice & Job Suggestions")

# ------------------------- Resume Upload -------------------------
uploaded_file = st.file_uploader("📄 Upload your Resume (PDF)", type="pdf")
resume_text = ""

if uploaded_file:
    reader = PdfReader(uploaded_file)
    for page in reader.pages:
        resume_text += page.extract_text()

# ------------------------- Role Selection -------------------------
if resume_text:
    role = st.selectbox("🎯 Select the Role You Are Applying For", [
        "Data Scientist", "Software Engineer", "Machine Learning Engineer",
        "Frontend Developer", "Backend Developer", "Data Analyst"
    ])

    # ---------------------- Generate Interview Questions ----------------------
    if st.button("🎤 Start Interview"):
        with st.spinner("Generating interview questions..."):
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "llama3-8b-8192",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an AI Interviewer. Ask 3 role-specific questions based on the user's resume."
                    },
                    {
                        "role": "user",
                        "content": f"My resume: {resume_text}\nRole: {role}"
                    }
                ]
            }
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
            questions = response.json()["choices"][0]["message"]["content"]

        st.markdown("### 🤖 Interview Questions")
        st.write(questions)

        # ---------------------- Voice Interview ----------------------
        st.markdown("### 🎙️ Record Your Answer")
        
        class AudioProcessor:
            def __init__(self):
                self.frames = []

            def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
                audio = frame.to_ndarray()
                self.frames.append(audio)
                return frame

        audio_processor = AudioProcessor()
        ctx = webrtc_streamer(
            key="audio",
            mode="SENDONLY",
            media_stream_constraints={"audio": True, "video": False},
            audio_receiver_size=1024,
            audio_frame_callback=audio_processor.recv,
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
        )

        # Save and Transcribe
        if st.button("✅ Save & Transcribe Answer"):
            if not audio_processor.frames:
                st.error("⚠️ No audio recorded. Please speak after allowing mic access.")
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                    wav_path = f.name
                    wf = wave.open(wav_path, 'wb')
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(48000)
                    for frame in audio_processor.frames:
                        wf.writeframes(frame.tobytes())
                    wf.close()

                def transcribe_audio(filepath):
                    headers = {'authorization': ASSEMBLY_API_KEY}
                    with open(filepath, 'rb') as f:
                        files = {
                            'file': ('response.wav', f, 'audio/wav')
                        }
                        response = requests.post('https://api.assemblyai.com/v2/upload', headers=headers, files=files)
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
                            return "❌ Transcription failed."
                        time.sleep(3)

                with st.spinner("Transcribing..."):
                    transcription = transcribe_audio(wav_path)
                    st.success("🗣️ Your Transcribed Answer:")
                    st.write(transcription)

                # ---------------------- Job Suggestions ----------------------
                st.markdown("### 💼 Job Recommendations")
                location = st.text_input("Enter your preferred job location:", "Remote")
                if st.button("🔍 Suggest Jobs"):
                    jooble_url = f"https://jooble.org/api/{JOOOBLE_API_KEY}"
                    payload = {
                        "keywords": role,
                        "location": location
                    }
                    response = requests.post(jooble_url, json=payload)
                    jobs = response.json().get("jobs", [])[:5]

                    if jobs:
                        for job in jobs:
                            st.markdown(f"""
                            **{job['title']}**  
                            📍 {job['location']}  
                            🔗 [View Job]({job['link']})  
                            🕒 Posted: {job.get('updated', 'N/A')}  
                            """)
                    else:
                        st.info("No jobs found. Try a different role or location.")
