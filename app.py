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
from fpdf import FPDF

# Load API keys
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY")
JOOOBLE_API_KEY = os.getenv("JOOOBLE_API_KEY")

st.set_page_config(page_title="AI Interviewer", layout="centered")
st.title("🌐 Multilingual AI Interviewer with Feedback")

# ------------------------- Resume Upload -------------------------
uploaded_file = st.file_uploader("📄 Upload your Resume (PDF)", type="pdf")
resume_text = ""

if uploaded_file:
    reader = PdfReader(uploaded_file)
    for page in reader.pages:
        resume_text += page.extract_text()

# ------------------------- Role and Language Selection -------------------------
if resume_text:
    role = st.selectbox("🎯 Select the Role You Are Applying For", [
        "Data Scientist", "Software Engineer", "Machine Learning Engineer",
        "Frontend Developer", "Backend Developer", "Data Analyst"
    ])
    language = st.selectbox("🌍 Interview Language", [
        "English", "Hindi", "Spanish", "French", "German", "Chinese"
    ])

    # ---------------------- Generate Interview Questions ----------------------
    if st.button("🎤 Start Interview"):
        with st.spinner("Generating interview questions..."):
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            prompt = f"""You are an AI Interviewer. Ask 3 interview questions in {language} for a candidate applying to the role of {role}.
Resume: {resume_text}"""

            data = {
                "model": "llama3-8b-8192",
                "messages": [
                    {"role": "system", "content": "You are a multilingual AI interviewer."},
                    {"role": "user", "content": prompt}
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
                        upload_response = requests.post(
                            'https://api.assemblyai.com/v2/upload',
                            headers=headers,
                            files={'file': f}
                        )
                    upload_url = upload_response.json()['upload_url']
                    json_data = {'audio_url': upload_url, 'language_code': language.lower()[:2]}
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

                # ---------------------- Feedback Scoring ----------------------
                with st.spinner("Generating feedback..."):
                    feedback_prompt = f"""Evaluate the following interview response for the role of {role}:
Response: {transcription}
Provide a score out of 10 and a brief feedback in {language}."""

                    feedback_data = {
                        "model": "llama3-8b-8192",
                        "messages": [
                            {"role": "system", "content": "You are a multilingual interview evaluator."},
                            {"role": "user", "content": feedback_prompt}
                        ]
                    }
                    feedback_response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=feedback_data)
                    feedback = feedback_response.json()["choices"][0]["message"]["content"]

                    st.markdown("### 🧠 Feedback & Score")
                    st.write(feedback)

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

                # ---------------------- PDF Download ----------------------
                def generate_pdf(transcription, questions, job_suggestions, feedback):
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", size=12)
                    pdf.cell(200, 10, txt="AI Interview Summary", ln=True, align='C')
                    pdf.multi_cell(0, 10, txt=f"\nInterview Questions:\n{questions}")
                    pdf.multi_cell(0, 10, txt=f"\nYour Transcribed Answer:\n{transcription}")
                    pdf.multi_cell(0, 10, txt=f"\nFeedback:\n{feedback}")
                    pdf.multi_cell(0, 10, txt="\nJob Suggestions:")
                    for job in job_suggestions:
                        pdf.multi_cell(0, 10, txt=f"- {job['title']} ({job['location']})\nLink: {job['link']}")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                        pdf.output(tmp_pdf.name)
                        return tmp_pdf.name

                if jobs:
                    pdf_path = generate_pdf(transcription, questions, jobs, feedback)
                    with open(pdf_path, "rb") as f:
                        st.download_button("📄 Download Interview Summary (PDF)", f, file_name="interview_summary.pdf")
