# app.py
import os
import streamlit as st
import tempfile
import fitz  # PyMuPDF
import docx2txt
import requests
import smtplib
import speech_recognition as sr
from email.message import EmailMessage
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
import whisper
import openai
import re

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Load Whisper model for transcription
st.session_state.whisper_model = whisper.load_model("base")

st.set_page_config(page_title="AI Mock Interviewer")
st.title("🎤 AI Mock Interviewer")
st.markdown("Upload your resume and prepare for an AI-powered interview")

# 1. Resume Parsing
def parse_resume(file):
    if file.name.endswith(".pdf"):
        doc = fitz.open(stream=file.read(), filetype="pdf")
        return " ".join([page.get_text() for page in doc])
    elif file.name.endswith(".docx"):
        return docx2txt.process(file)
    return ""

# 2. Extract Skills (basic regex or keywords)
def extract_skills(text):
    keywords = ["python", "machine learning", "data analysis", "sql", "deep learning", "nlp"]
    return [kw for kw in keywords if kw.lower() in text.lower()]

# 3. Jooble API integration
@st.cache_data
def fetch_job_roles(skills):
    url = "https://jooble.org/api/" + JOOBLE_API_KEY
    body = {"keywords": ", ".join(skills), "location": "India"}
    res = requests.post(url, json=body)
    jobs = res.json().get("jobs", [])
    return list(set([job["title"] for job in jobs]))[:5] or ["Data Scientist", "ML Engineer"]

# 4. Generate interview questions via Groq
@st.cache_data
def generate_questions(role):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": "Generate 5 technical interview questions for a " + role},
        ],
        "temperature": 0.7
    }
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
    return response.json()["choices"][0]["message"]["content"]

# 5. Evaluate response
def evaluate_answer(answer, question):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt = f"Evaluate the following answer for the question '{question}' in terms of technical accuracy, clarity, and confidence. Give detailed feedback:\nAnswer: {answer}"
    data = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": "You are a technical interviewer."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7
    }
    res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
    return res.json()["choices"][0]["message"]["content"]

# 6. Send feedback report
def send_email(to_email, feedback):
    msg = EmailMessage()
    msg["Subject"] = "Your AI Interview Feedback Report"
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg.set_content(feedback)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)

# UI Components
resume_file = st.file_uploader("📄 Upload your resume (PDF/DOCX)", type=["pdf", "docx"])
email = st.text_input("📧 Enter your email for the report")

if resume_file and email:
    with st.spinner("Extracting resume content..."):
        resume_text = parse_resume(resume_file)
        skills = extract_skills(resume_text)
        st.success(f"Extracted skills: {', '.join(skills)}")
        job_roles = fetch_job_roles(skills)

    selected_role = st.selectbox("🎯 Choose a job role for interview", job_roles)
    if st.button("Generate Interview Questions"):
        questions = generate_questions(selected_role)
        st.session_state.questions = questions.split("\n")

if "questions" in st.session_state:
    st.markdown("### 🎙️ Answer these questions below")
    feedbacks = []
    for q in st.session_state.questions:
        if not q.strip():
            continue
        st.markdown(f"**{q}**")
        audio_file = st.file_uploader("Upload answer audio", type=["wav", "mp3"], key=q)
        if audio_file:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(audio_file.read())
                tmp_path = tmp.name
            transcript = st.session_state.whisper_model.transcribe(tmp_path)["text"]
            st.markdown(f"📝 Transcribed: {transcript}")
            with st.spinner("Evaluating answer..."):
                feedback = evaluate_answer(transcript, q)
                feedbacks.append((q, transcript, feedback))
                st.markdown(f"✅ Feedback: {feedback}")

    if st.button("📨 Send Feedback Report"):
        report = ""
        for q, a, fb in feedbacks:
            report += f"Q: {q}\nA: {a}\nFeedback: {fb}\n\n"
        send_email(email, report)
        st.success("Feedback report sent to your email!")
