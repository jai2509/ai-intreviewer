import os
import streamlit as st
from dotenv import load_dotenv
import requests
import docx2txt
import json
from datetime import datetime
from io import BytesIO
from fpdf import FPDF

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

st.set_page_config(page_title="AI Mock Interviewer", layout="centered")
st.title("🧠 AI-Based Mock Interviewer")

# 1. Upload Resume
st.subheader("📄 Upload Your Resume (DOCX or TXT)")
resume_file = st.file_uploader("Upload resume", type=["docx", "txt"])

def extract_resume_text(file):
    if file.name.endswith(".docx"):
        return docx2txt.process(file)
    return file.read().decode("utf-8")

def extract_experience(resume_text):
    for line in resume_text.splitlines():
        if "year" in line.lower():
            digits = [int(s) for s in line.split() if s.isdigit()]
            if digits:
                return digits[0]
    return 1  # Default

# 2. Choose Job Role
job_role = None
if resume_file:
    resume_text = extract_resume_text(resume_file)
    st.success("Resume uploaded successfully.")
    experience = extract_experience(resume_text)
    st.markdown(f"🔍 **Estimated Experience:** {experience} years")

    # Choose job role from resume
    if "data" in resume_text.lower():
        job_role = "Data Scientist"
    elif "machine learning" in resume_text.lower():
        job_role = "ML Engineer"
    elif "frontend" in resume_text.lower():
        job_role = "Frontend Developer"
    else:
        job_role = st.selectbox("Choose your preferred job role:", ["Data Scientist", "ML Engineer", "Backend Developer", "Frontend Developer", "Full Stack Developer"])

# 3. Generate Questions using Groq
if job_role:
    st.subheader(f"🧑‍💻 Interview: {job_role}")
    if st.button("Generate Questions"):
        prompt = f"Act as an interviewer and ask 5 technical questions for a {job_role} position. Include diverse difficulty."
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "llama3-8b-8192", "messages": [{"role": "system", "content": "Be a professional interviewer."}, {"role": "user", "content": prompt}]}
        )
        questions = response.json()["choices"][0]["message"]["content"]
        st.session_state.questions = questions.split("\n")
        st.session_state.answers = []
        st.success("Questions generated!")

# 4. Voice Response Input
if "questions" in st.session_state:
    st.subheader("🎙️ Answer Interview Questions (Voice)")
    for i, q in enumerate(st.session_state.questions):
        if not q.strip():
            continue
        st.markdown(f"**Q{i+1}:** {q}")
        audio = st.file_uploader(f"Upload answer for Q{i+1} (WAV/MP3)", type=["wav", "mp3"], key=f"audio{i}")
        if audio:
            upload_url = "https://api.assemblyai.com/v2/upload"
            headers = {"authorization": ASSEMBLYAI_API_KEY}
            upload_response = requests.post(upload_url, headers=headers, data=audio)
            audio_url = upload_response.json()["upload_url"]

            # Transcribe
            transcript_req = {"audio_url": audio_url}
            transcript_url = "https://api.assemblyai.com/v2/transcript"
            transcript_response = requests.post(transcript_url, headers=headers, json=transcript_req)
            transcript_id = transcript_response.json()["id"]

            # Poll for result
            status = "queued"
            while status not in ["completed", "error"]:
                poll = requests.get(f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers=headers)
                result = poll.json()
                status = result["status"]
            if status == "completed":
                answer = result["text"]
                st.markdown(f"📜 **Transcript:** {answer}")
                st.session_state.answers.append((q, answer))
            else:
                st.error("Transcription failed.")

# 5. Generate Feedback Report
if st.button("📄 Generate Feedback Report"):
    if "answers" in st.session_state:
        report_lines = ["Mock Interview Report", f"Candidate Role: {job_role}", "", f"Date: {datetime.now().strftime('%Y-%m-%d')}"]
        for i, (q, a) in enumerate(st.session_state.answers):
            report_lines.append(f"Q{i+1}: {q}")
            report_lines.append(f"A{i+1}: {a}")
            report_lines.append("")

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        for line in report_lines:
            pdf.multi_cell(0, 10, line)
        buf = BytesIO()
        pdf.output(buf)
        st.download_button("Download Report", data=buf.getvalue(), file_name="interview_report.pdf")

# 6. Job Suggestions
if job_role and "experience" in locals():
    st.subheader("💼 Job Suggestions")
    location = st.text_input("Enter your location for job filtering (e.g., 'India')", "India")
    if st.button("Find Jobs"):
        jooble_url = f"https://jooble.org/api/{JOOBLE_API_KEY}"
        payload = {"keywords": job_role, "location": location}
        headers = {"Content-Type": "application/json"}
        job_response = requests.post(jooble_url, headers=headers, data=json.dumps(payload))

        if job_response.ok:
            jobs = job_response.json().get("jobs", [])[:5]
            if jobs:
                for job in jobs:
                    st.markdown(f"🔹 **{job['title']}** at *{job['company']}, {job['location']}*")
                    st.markdown(f"[Apply]({job['link']})")
            else:
                st.info("No matching jobs found.")
        else:
            st.error("Job search failed. Check Jooble API key.")
