import os
import streamlit as st
from dotenv import load_dotenv
import requests
import fitz  # PyMuPDF
import time
from datetime import datetime

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY")
JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")

st.set_page_config(page_title="AI Mock Interviewer", layout="centered")
st.title("🧠 AI Mock Interviewer")

# ---------- Resume Upload ----------
st.subheader("📄 Upload Your Resume (PDF)")
resume_file = st.file_uploader("Upload your resume to start the mock interview", type=["pdf"])
parsed_resume_text = ""

def extract_text_from_resume(pdf_file):
    text = ""
    try:
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        return f"⚠️ Error extracting resume text: {e}"

if resume_file:
    with st.spinner("Parsing resume..."):
        parsed_resume_text = extract_text_from_resume(resume_file)
        if parsed_resume_text.startswith("⚠️"):
            st.error(parsed_resume_text)
        else:
            st.success("✅ Resume parsed successfully.")
            st.text_area("📄 Parsed Resume Text", parsed_resume_text, height=250)

# ---------- Job Role Selection ----------
st.subheader("🎯 Select or Confirm Job Role")
job_roles = ["Data Scientist", "Frontend Developer", "Backend Developer", "AI/ML Engineer"]
job_role = st.selectbox("Choose job role for interview:", job_roles)

# ---------- Interview Question Generation ----------
st.subheader("🧪 AI Interview Questions")
if st.button("Generate Questions"):
    prompt = f"Generate 5 interview questions for the role of {job_role} based on this resume:\n{parsed_resume_text}"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": "You are an expert interviewer."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
    if response.status_code == 200:
        questions = response.json()["choices"][0]["message"]["content"].split("\n")
        st.session_state["questions"] = [q for q in questions if q.strip()]
        st.success("Questions generated!")
    else:
        st.error("Failed to generate questions.")

# ---------- Interview Answer Recording (Simulated with text input) ----------
if "questions" in st.session_state:
    st.subheader("🎙️ Your Responses")
    st.session_state.answers = []
    for i, question in enumerate(st.session_state["questions"]):
        answer = st.text_area(f"{question}", key=f"answer_{i}")
        if answer:
            st.session_state.answers.append((question, answer))

# ---------- Job Suggestion (Experience based) ----------
def suggest_jobs_from_jooble(role):
    api_url = f"https://jooble.org/api/{JOOBLE_API_KEY}"
    payload = {
        "keywords": role,
        "location": "India",
        "experience": 2
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(api_url, json=payload, headers=headers)
    if response.status_code == 200:
        jobs = response.json().get("jobs", [])
        return jobs[:3]  # top 3 jobs
    else:
        return []

st.subheader("💼 Job Suggestions")
if st.button("Suggest Jobs"):
    jobs = suggest_jobs_from_jooble(job_role)
    if jobs:
        for job in jobs:
            st.markdown(f"**{job['title']}** at *{job['company']}*\n
📍 {job['location']}\n
🔗 [Apply here]({job['link']})")
    else:
        st.info("No jobs found or Jooble API error.")

# ---------- Downloadable Feedback Report ----------
from datetime import datetime
if st.button("📄 Generate Feedback Report"):
    if "answers" in st.session_state and st.session_state.answers:
        report_lines = [
            "Mock Interview Feedback Report",
            f"Candidate Role: {job_role}",
            f"Interview Date: {datetime.now().strftime('%Y-%m-%d')}",
            "-"*40
        ]
        for i, (q, a) in enumerate(st.session_state.answers):
            report_lines.append(f"Q{i+1}: {q}")
            report_lines.append(f"A{i+1}: {a}")
            report_lines.append("-" * 20)

        report_text = "\n".join(report_lines)
        st.download_button(
            label="📥 Download Report (.txt)",
            data=report_text,
            file_name="interview_report.txt",
            mime="text/plain"
        )
