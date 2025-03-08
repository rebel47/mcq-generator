import streamlit as st
import pdfplumber
import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
import pandas as pd
from typing import List, Dict
import tempfile
from datetime import datetime
import warnings
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

# Suppress warnings
warnings.filterwarnings('ignore')

# Load environment variables and configure API
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# Initialize session state
if 'questions' not in st.session_state:
    st.session_state.questions = []
if 'practice_mode' not in st.session_state:
    st.session_state.practice_mode = False
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
if 'selected_answers' not in st.session_state:
    st.session_state.selected_answers = {}

def extract_text_from_pdf(pdf_file) -> str:
    try:
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return ""

def generate_mcqs(content: str, num_questions: int, difficulty: str) -> List[Dict]:
    try:
        prompt = f"""
        Generate exactly {num_questions} multiple choice questions based on the following content.
        Difficulty level: {difficulty}

        Rules:
        1. Each question must have exactly one correct answer
        2. All options must be relevant to the question
        3. Return ONLY valid JSON format

        Format:
        {{
            "questions": [
                {{
                    "question": "Question text here?",
                    "options": {{
                        "A": "First option",
                        "B": "Second option",
                        "C": "Third option",
                        "D": "Fourth option"
                    }},
                    "correct_answer": "A",
                    "explanation": "Brief explanation here"
                }}
            ]
        }}

        Content:
        {content}
        """
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        json_str = response_text[start_idx:end_idx]
        questions_data = json.loads(json_str)
        
        return questions_data['questions']
            
    except Exception as e:
        st.error(f"❌ Error generating questions: {str(e)}")
        return []

def draw_wrapped_text(c, text, x, y, max_width):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        if c.stringWidth(line + word) < max_width:
            line += word + " "
        else:
            lines.append(line)
            line = word + " "
    lines.append(line)
    for line in lines:
        c.drawString(x, y, line.strip())
        y -= 15
    return y

def generate_pdf(questions, user_answers, correct, total, score_percentage):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 50
    max_width = width - 2 * margin
    y = height - margin

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, "MCQ Quiz Results")
    y -= 20

    # Score
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, f"Final Score: {correct}/{total} ({score_percentage:.1f}%)")
    y -= 30

    # Questions
    for i, q in enumerate(questions):
        user_answer = user_answers.get(i, "Not answered")
        is_correct = user_answer == q['correct_answer']

        if y < 100:  # Check if we need a new page
            c.showPage()
            y = height - margin
            c.setFont("Helvetica", 12)

        # Question
        c.setFont("Helvetica-Bold", 12)
        text = f"Question {i+1}:"
        c.drawString(margin, y, text)
        y -= 20
        
        c.setFont("Helvetica", 12)
        y = draw_wrapped_text(c, q['question'], margin, y, max_width)
        y -= 15

        # Options
        for opt, text in q['options'].items():
            if opt == user_answer:
                if is_correct:
                    c.setFillColorRGB(0, 0.5, 0)  # Green
                else:
                    c.setFillColorRGB(1, 0, 0)  # Red
            elif opt == q['correct_answer'] and not is_correct:
                c.setFillColorRGB(0, 0.5, 0)  # Green
            else:
                c.setFillColorRGB(0, 0, 0)  # Black

            option_text = f"{opt}. {text}"
            if opt == user_answer:
                option_text += " (Your answer)"
            if opt == q['correct_answer']:
                option_text += " (Correct answer)"
                
            y = draw_wrapped_text(c, option_text, margin + 20, y, max_width - 20)
            y -= 5

        # Explanation
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 10)
        y -= 10
        c.drawString(margin, y, "Explanation:")
        c.setFont("Helvetica", 10)
        y -= 15
        y = draw_wrapped_text(c, q['explanation'], margin + 20, y, max_width - 20)
        y -= 30

    c.save()
    buffer.seek(0)
    return buffer.getvalue()

def main():
    st.set_page_config(page_title="MCQ Generator", page_icon="📚")
    
    # Page Header
    st.title("📚 Lecture Slides MCQ Generator")
    st.write("Upload your lecture slides and generate multiple choice questions!")
    st.write("Created by: Mohammad Ayaz Alam")

    # File Upload Section
    uploaded_file = st.file_uploader("Upload your lecture slides (PDF format)", type=['pdf'])
    
    if uploaded_file:
        # Configuration Options
        col1, col2 = st.columns(2)
        with col1:
            difficulty = st.select_slider(
                "Select difficulty level",
                options=["Easy", "Medium", "Hard"],
                value="Medium"
            )
        with col2:
            num_questions = st.number_input(
                "Number of questions to generate",
                min_value=1,
                max_value=25,
                value=10,
                help="Maximum 25 questions can be generated at once"
            )

        # Action Button
        practice_button = st.button("Start Practice Mode", use_container_width=True)

        # Generate Questions
        if practice_button:
            with st.spinner("Processing slides and generating questions..."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_file_path = tmp_file.name

                    text_content = extract_text_from_pdf(tmp_file_path)
                    os.unlink(tmp_file_path)

                    if not text_content.strip():
                        st.error("Could not extract text from the PDF. Please make sure it's not scanned or image-based.")
                        return

                    questions = generate_mcqs(text_content, num_questions, difficulty)
                    if questions:
                        st.session_state.questions = questions
                        st.session_state.practice_mode = True
                        st.rerun()

                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

    # Practice Mode Section
    if st.session_state.practice_mode and st.session_state.questions:
        if not st.session_state.submitted:
            st.subheader("Practice Mode")
            st.write("Select your answers and submit to see your score!")
            
            # Display Questions
            for i, q in enumerate(st.session_state.questions):
                st.write(f"\n**Question {i+1}:** {q['question']}")
                options = {opt: text for opt, text in q['options'].items()}
                
                selected_answer = st.radio(
                    f"Select your answer for Question {i+1}:",
                    list(options.keys()),
                    key=f"q_{i}",
                    format_func=lambda x: f"{x}. {options[x]}",
                    index=None
                )
                st.session_state.user_answers[i] = selected_answer
            
            # Submit Button
            if st.button("Submit Answers"):
                st.session_state.submitted = True
                st.rerun()

        # Show Results
        if st.session_state.submitted:
            correct, total = calculate_score()
            score_percentage = (correct / total) * 100
            
            st.subheader("Quiz Results")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Correct Answers", f"{correct}/{total}")
            with col2:
                st.metric("Score", f"{score_percentage:.1f}%")
            with col3:
                if score_percentage >= 80:
                    st.success("Excellent! 🌟")
                elif score_percentage >= 60:
                    st.info("Good job! 👍")
                else:
                    st.warning("Keep practicing! 💪")

            # Detailed Review
            st.subheader("Detailed Review")
            for i, q in enumerate(st.session_state.questions):
                user_answer = st.session_state.user_answers.get(i, "Not answered")
                is_correct = user_answer == q['correct_answer']
                
                with st.expander(f"Question {i+1} - {'✅ Correct' if is_correct else '❌ Incorrect'}"):
                    st.write("**Question:**", q['question'])
                    st.write("\n**Options:**")
                    for opt, text in q['options'].items():
                        if opt == user_answer:
                            if is_correct:
                                st.success(f"{opt}. {text} (Your answer ✅)")
                            else:
                                st.error(f"{opt}. {text} (Your answer ❌)")
                        elif opt == q['correct_answer'] and not is_correct:
                            st.success(f"{opt}. {text} (Correct answer)")
                        else:
                            st.write(f"{opt}. {text}")
                    st.write("**Explanation:**", q['explanation'])
            
            col1, col2 = st.columns(2)
            with col1:
                # Button to generate new unique question
                if st.button("Generate New Unique Question"):
                    with st.spinner("Generating a new unique question..."):
                        try:
                            text_content = extract_text_from_pdf(uploaded_file)
                            new_question = generate_mcqs(text_content, 1, difficulty)[0]
                            st.session_state.questions.append(new_question)
                            st.session_state.submitted = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")

            with col2:
                # Button to download results as PDF
                if st.button("Download Results as PDF"):
                    pdf_data = generate_pdf(st.session_state.questions, st.session_state.user_answers, correct, total, score_percentage)
                    st.download_button(
                        label="Download PDF",
                        data=pdf_data,
                        file_name=f"quiz_results.pdf",
                        mime="application/pdf"
                    )

def calculate_score():
    correct = 0
    total = len(st.session_state.questions)
    for i, q in enumerate(st.session_state.questions):
        if i in st.session_state.user_answers:
            if st.session_state.user_answers[i] == q['correct_answer']:
                correct += 1
    return correct, total

if __name__ == "__main__":
    main()
