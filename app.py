import streamlit as st
import PyPDF2
import os
import requests
import base64
from dotenv import load_dotenv
import openai
import json
import time
import speech_recognition as sr
import tempfile

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")
ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY")

st.set_page_config(page_title="AI Interviewer", layout="centered")

st.title("🧠 AI Interviewer - Resume to Job")

# 1. Resume Upload and Parsing
st.header("📄 Upload Your Resume")
uploaded_file = st.file_uploader("Upload your resume (PDF)", type="pdf")

def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

resume_text = ""
if uploaded_file is not None:
    resume_text = extract_text_from_pdf(uploaded_file)
    st.success("Resume parsed successfully.")
    st.text_area("📄 Extracted Resume Text:", resume_text, height=200)

# 2. Role Selection
st.header("🎯 Choose a Role to Apply")
suggested_roles = ["Data Scientist", "Software Engineer", "Frontend Developer", "Backend Developer", "ML Engineer"]
selected_role = st.selectbox("Select the Role:", suggested_roles)

# 3. Interview Question Generation using GROQ
def generate_questions_groq(role, skills):
    prompt = f"Generate 5 technical interview questions for a {role}. Skills: {skills}. Keep them short and relevant."
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }
    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
    questions = response.json()["choices"][0]["message"]["content"].strip().split("\n")
    return [q.strip("- ").strip() for q in questions if q.strip()]

interview_questions = []
if st.button("Generate Interview Questions"):
    interview_questions = generate_questions_groq(selected_role, resume_text)
    st.session_state["questions"] = interview_questions
    st.success("Questions Generated Successfully!")
    for i, q in enumerate(interview_questions, 1):
        st.write(f"**Q{i}:** {q}")

# 4. Voice Interview (AssemblyAI)
st.header("🎙️ Voice Interview")
if "questions" in st.session_state:
    for idx, question in enumerate(st.session_state["questions"]):
        st.subheader(f"Q{idx+1}: {question}")
        audio_file = st.file_uploader(f"Upload your answer for Q{idx+1} (WAV/MP3)", type=["wav", "mp3"], key=f"audio_{idx}")
        if audio_file:
            def transcribe_audio(audio_file):
                headers = {'authorization': ASSEMBLY_API_KEY}
                upload_response = requests.post('https://api.assemblyai.com/v2/upload', headers=headers, files={'file': audio_file})
                upload_url = upload_response.json()['upload_url']

                json_data = {'audio_url': upload_url}
                transcript_response = requests.post('https://api.assemblyai.com/v2/transcript', json=json_data, headers=headers)
                transcript_id = transcript_response.json()['id']

                # Polling
                while True:
                    polling = requests.get(f'https://api.assemblyai.com/v2/transcript/{transcript_id}', headers=headers)
                    status = polling.json()['status']
                    if status == 'completed':
                        return polling.json()['text']
                    elif status == 'error':
                        return "Transcription failed."
                    time.sleep(3)

            transcription = transcribe_audio(audio_file)
            st.write(f"🗣️ Your Answer: {transcription}")
            st.session_state[f"answer_{idx}"] = transcription

# 5. Evaluate Interview (GROQ)
if st.button("🧠 Evaluate My Interview"):
    all_qas = ""
    for i, q in enumerate(st.session_state["questions"]):
        a = st.session_state.get(f"answer_{i}", "No answer")
        all_qas += f"Q{i+1}: {q}\nA: {a}\n\n"

    prompt = f"Evaluate the following interview conversation. Give a score out of 10 and brief feedback:\n\n{all_qas}"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
    evaluation = response.json()["choices"][0]["message"]["content"]
    st.subheader("📊 Interview Evaluation")
    st.write(evaluation)
    st.session_state["feedback"] = evaluation

# 6. Jooble API Integration
st.header("💼 Job Recommendations")
if st.button("Get Job Suggestions"):
    if resume_text:
        payload = {
            "keywords": selected_role,
            "location": "remote"
        }
        response = requests.post(
            f"https://jooble.org/api/{JOOBLE_API_KEY}",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        jobs = response.json().get("jobs", [])[:5]
        if jobs:
            for job in jobs:
                st.markdown(f"**{job['title']}** - {job['location']}")
                st.write(job["snippet"])
                st.markdown(f"[Apply Here]({job['link']})")
        else:
            st.warning("No jobs found.")
    else:
        st.error("Please upload your resume first.")
