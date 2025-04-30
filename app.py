import streamlit as st
import os
import tempfile
import requests
import time
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import av
import numpy as np
from pydub import AudioSegment
from fpdf import FPDF

# Load API keys
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY")
JOOOBLE_API_KEY = os.getenv("JOOOBLE_API_KEY")

st.set_page_config(page_title="AI Interviewer", layout="centered")
st.title("🌐 Multilingual AI Interviewer with Feedback")

# Initialize session state
if "started_interview" not in st.session_state:
    st.session_state.started_interview = False
if "questions" not in st.session_state:
    st.session_state.questions = []
if "transcriptions" not in st.session_state:
    st.session_state.transcriptions = {}
if "feedbacks" not in st.session_state:
    st.session_state.feedbacks = {}
if "jobs" not in st.session_state:
    st.session_state.jobs = []
if "audio_frames" not in st.session_state:
    st.session_state.audio_frames = {}
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""

# Language code mapping for AssemblyAI
language_map = {
    "English": "en",
    "Hindi": "hi",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Chinese": "zh"
}

# ------------------------- Resume Upload -------------------------
def parse_resume(uploaded_file):
    try:
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return ""

uploaded_file = st.file_uploader("📄 Upload your Resume (PDF)", type="pdf")
if uploaded_file:
    st.session_state.resume_text = parse_resume(uploaded_file)
    if st.session_state.resume_text:
        st.success("Resume uploaded successfully!")

# ------------------------- Role and Language Selection -------------------------
if st.session_state.resume_text:
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
            try:
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                prompt = f"""You are an AI Interviewer. Generate exactly 3 interview questions in {language} for a candidate applying to the role of {role}. Format as:
1. Question 1
2. Question 2
3. Question 3
Resume: {st.session_state.resume_text[:1000]}"""

                data = {
                    "model": "llama3-8b-8192",
                    "messages": [
                        {"role": "system", "content": "You are a multilingual AI interviewer."},
                        {"role": "user", "content": prompt}
                    ]
                }
                response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                # Parse questions into a list
                st.session_state.questions = [q.strip() for q in content.split("\n") if q.strip().startswith(tuple("123")) and len(q.strip()) > 2]
                st.session_state.started_interview = True
                st.session_state.transcriptions = {i: "" for i in range(len(st.session_state.questions))}
                st.session_state.feedbacks = {i: "" for i in range(len(st.session_state.questions))}
                st.session_state.audio_frames = {i: [] for i in range(len(st.session_state.questions))}
            except requests.RequestException as e:
                st.error(f"Error generating questions: {e}")

# ---------------------- Render Interview UI -------------------------
if st.session_state.started_interview:
    st.markdown("### 🤖 Interview Questions")
    for i, question in enumerate(st.session_state.questions):
        st.write(f"**{question}**")

        # ---------------------- Voice Interview ----------------------
        st.markdown(f"### 🎙️ Record Your Answer for Question {i+1}")

        class AudioProcessor:
            def __init__(self, question_idx):
                self.question_idx = question_idx

            def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
                audio = frame.to_ndarray()
                st.session_state.audio_frames[self.question_idx].append(audio)
                return frame

        audio_processor = AudioProcessor(i)
        ctx = webrtc_streamer(
            key=f"audio-{i}",
            mode=WebRtcMode.SENDONLY,
            media_stream_constraints={"audio": True, "video": False},
            audio_receiver_size=1024,
            audio_frame_callback=audio_processor.recv,
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
        )

        # Save and Transcribe
        if st.button(f"✅ Save & Transcribe Answer for Question {i+1}", key=f"transcribe-{i}"):
            if not st.session_state.audio_frames[i]:
                st.error("⚠️ No audio recorded. Please speak after allowing mic access.")
            else:
                with st.spinner("Saving audio..."):
                    try:
                        # Convert audio frames to WAV using pydub
                        audio_data = np.concatenate(st.session_state.audio_frames[i])
                        audio = AudioSegment(
                            audio_data.tobytes(),
                            sample_width=2,
                            frame_rate=48000,
                            channels=1
                        )
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                            wav_path = f.name
                            audio.export(wav_path, format="wav")

                        # Transcribe audio
                        def transcribe_audio(filepath):
                            try:
                                headers = {'authorization': ASSEMBLY_API_KEY}
                                with open(filepath, 'rb') as f:
                                    upload_response = requests.post(
                                        'https://api.assemblyai.com/v2/upload',
                                        headers=headers,
                                        files={'file': f}
                                    )
                                    upload_response.raise_for_status()
                                upload_url = upload_response.json()['upload_url']
                                json_data = {'audio_url': upload_url, 'language_code': language_map[language]}
                                transcript_response = requests.post(
                                    'https://api.assemblyai.com/v2/transcript',
                                    json=json_data,
                                    headers=headers
                                )
                                transcript_response.raise_for_status()
                                transcript_id = transcript_response.json()['id']

                                while True:
                                    polling = requests.get(
                                        f'https://api.assemblyai.com/v2/transcript/{transcript_id}',
                                        headers=headers
                                    )
                                    polling.raise_for_status()
                                    status = polling.json()['status']
                                    if status == 'completed':
                                        return polling.json()['text']
                                    elif status == 'error':
                                        return "❌ Transcription failed."
                                    time.sleep(3)
                            except requests.RequestException as e:
                                return f"Error during transcription: {e}"

                        with st.spinner("Transcribing..."):
                            st.session_state.transcriptions[i] = transcribe_audio(wav_path)
                            st.success(f"🗣️ Your Transcribed Answer for Question {i+1}:")
                            st.write(st.session_state.transcriptions[i])
                            st.session_state.audio_frames[i] = []  # Clear frames

                        # ---------------------- Feedback Scoring ----------------------
                        with st.spinner("Generating feedback..."):
                            try:
                                headers = {
                                    "Authorization": f"Bearer {GROQ_API_KEY}",
                                    "Content-Type": "application/json"
                                }
                                feedback_prompt = f"""Evaluate the following interview response for the role of {role}:
Question: {question}
Response: {st.session_state.transcriptions[i]}
Provide a score out of 10 and a brief feedback in {language}."""

                                feedback_data = {
                                    "model": "llama3-8b-8192",
                                    "messages": [
                                        {"role": "system", "content": "You are a multilingual interview evaluator."},
                                        {"role": "user", "content": feedback_prompt}
                                    ]
                                }
                                feedback_response = requests.post(
                                    "https://api.groq.com/openai/v1/chat/completions",
                                    headers=headers,
                                    json=feedback_data
                                )
                                feedback_response.raise_for_status()
                                st.session_state.feedbacks[i] = feedback_response.json()["choices"][0]["message"]["content"]
                                st.markdown(f"### 🧠 Feedback & Score for Question {i+1}")
                                st.write(st.session_state.feedbacks[i])
                            except requests.RequestException as e:
                                st.error(f"Error generating feedback: {e}")

                    except Exception as e:
                        st.error(f"Error saving audio: {e}")

    # ---------------------- Job Suggestions ----------------------
    st.markdown("### 💼 Job Recommendations")
    location = st.text_input("Enter your preferred job location:", "Remote")
    if st.button("🔍 Suggest Jobs"):
        try:
            jooble_url = f"https://jooble.org/api/{JOOOBLE_API_KEY}"
            payload = {
                "keywords": role,
                "location": location
            }
            response = requests.post(jooble_url, json=payload)
            response.raise_for_status()
            st.session_state.jobs = response.json().get("jobs", [])[:5]

            if st.session_state.jobs:
                for job in st.session_state.jobs:
                    st.markdown(f"""
                    **{job['title']}**  
                    📍 {job['location']}  
                    🔗 [View Job]({job['link']})  
                    🕒 Posted: {job.get('updated', 'N/A')}  
                    """)
            else:
                st.info("No jobs found. Try a different role or location.")
        except requests.RequestException as e:
            st.error(f"Error fetching jobs: {e}")

    # ---------------------- PDF Download ----------------------
    def generate_pdf(questions, transcriptions, feedbacks, job_suggestions):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="AI Interview Summary", ln=True, align='C')
        for i, (q, t, f) in enumerate(zip(questions, transcriptions.values(), feedbacks.values())):
            pdf.multi_cell(0, 10, txt=f"\nQuestion {i+1}: {q}")
            pdf.multi_cell(0, 10, txt=f"\nAnswer: {t or 'No answer provided'}")
            pdf.multi_cell(0, 10, txt=f"\nFeedback: {f or 'No feedback available'}")
        pdf.multi_cell(0, 10, txt="\nJob Suggestions:")
        if job_suggestions:
            for job in job_suggestions:
                pdf.multi_cell(0, 10, txt=f"- {job['title']} ({job['location']})\nLink: {job['link']}")
        else:
            pdf.multi_cell(0, 10, txt="No job suggestions available.")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            pdf.output(tmp_pdf.name)
            return tmp_pdf.name

    if any(st.session_state.transcriptions.values()) and any(st.session_state.feedbacks.values()):
        pdf_path = generate_pdf(
            st.session_state.questions,
            st.session_state.transcriptions,
            st.session_state.feedbacks,
            st.session_state.jobs
        )
        with open(pdf_path, "rb") as f:
            st.download_button(
                "📄 Download Interview Summary (PDF)",
                f,
                file_name="interview_summary.pdf"
            )
