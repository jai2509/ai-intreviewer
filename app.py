import streamlit as st
import requests
import fitz  # PyMuPDF
import io
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY")
JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")

st.set_page_config(page_title="AI Interviewer", layout="centered")
st.title("🧠 AI-Based Mock Interviewer")
st.markdown("Upload your resume and start a mock interview tailored to your job role.")

# ========== Resume Upload ==========
st.header("📄 Upload Your Resume (PDF)")
resume_file = st.file_uploader("Upload PDF Resume", type=["pdf"])

def extract_text_from_pdf(file):
    try:
        text = ""
        pdf = fitz.open(stream=file.read(), filetype="pdf")
        for page in pdf:
            text += page.get_text()
        return text
    except Exception as e:
        return f"Error reading PDF: {e}"

if resume_file:
    with st.spinner("Extracting information from resume..."):
        resume_text = extract_text_from_pdf(resume_file)
        st.success("Resume parsed successfully!")
        st.text_area("📄 Resume Content", resume_text[:2000], height=300)

        # ========== Select Job Role ==========
        st.subheader("🧑‍💼 Select Target Job Role")
        job_roles = ["Data Scientist", "Backend Developer", "Frontend Developer", "Machine Learning Engineer", "DevOps Engineer"]
        selected_role = st.selectbox("Choose a role:", job_roles)

        # ========== Generate Interview Questions ==========
        st.subheader("🎯 AI-Generated Interview Questions")
        if st.button("Generate Questions"):
            groq_url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "llama3-8b-8192",
                "messages": [
                    {"role": "system", "content": f"You are a professional interviewer for the role of {selected_role}. Ask 5 technical questions relevant to the resume:\n{resume_text[:1500]}"},
                    {"role": "user", "content": f"Please generate 5 technical interview questions for a {selected_role} based on my resume."}
                ]
            }
            response = requests.post(groq_url, headers=headers, json=data)
            if response.status_code == 200:
                questions = response.json()["choices"][0]["message"]["content"]
                st.session_state.questions = questions.split("\n")
                for q in st.session_state.questions:
                    st.markdown(f"**❓ {q}**")
            else:
                st.error("Failed to fetch questions from Groq.")

# ========== Mock Interview ==========
if "questions" in st.session_state:
    st.subheader("🎤 Answer the Questions (Text Simulation)")
    answers = []
    for idx, question in enumerate(st.session_state.questions):
        answer = st.text_area(f"Answer {idx+1}", key=f"answer_{idx}")
        answers.append(answer)

    if st.button("📝 Generate Feedback Report"):
        # Combine Q&A and send to Groq for evaluation
        qna = "\n".join([f"Q: {st.session_state.questions[i]}\nA: {answers[i]}" for i in range(len(answers))])
        feedback_prompt = f"""Evaluate this mock interview technically and give feedback with score (out of 10), strong points, and areas for improvement:\n{qna}"""

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama3-8b-8192",
                "messages": [
                    {"role": "system", "content": "You are an expert technical interviewer and feedback generator."},
                    {"role": "user", "content": feedback_prompt}
                ]
            }
        )

        if response.status_code == 200:
            feedback = response.json()["choices"][0]["message"]["content"]
            st.success("✅ Interview feedback generated!")
            st.download_button("📥 Download Feedback Report", feedback, file_name="interview_feedback.txt")
            st.text_area("📋 Feedback Preview", feedback, height=300)
        else:
            st.error("Failed to generate feedback.")

# ========== Job Suggestions ==========
st.header("💼 Job Suggestions (Experience Based)")
experience = st.slider("Select your experience (in years):", 0, 15, 2)
location = st.text_input("Preferred Job Location", "India")
keywords = st.text_input("Job Keywords (comma-separated)", "data science,python")

if st.button("🔍 Find Jobs"):
    jooble_url = "https://jooble.org/api/"
    payload = {
        "keywords": keywords,
        "location": location,
        "experience": experience
    }
    headers = {"Content-Type": "application/json"}

    response = requests.post(f"{jooble_url}{JOOBLE_API_KEY}", json=payload, headers=headers)

    if response.status_code == 200:
        data = response.json()
        jobs = data.get("jobs", [])[:5]
        if not jobs:
            st.warning("No jobs found for given filters.")
        for job in jobs:
            st.markdown(f"""**{job['title']}** at *{job['company']}*\n{job['location']}\n[More Info]({job['link']})""")
    else:
        st.error("Failed to fetch jobs from Jooble.")
