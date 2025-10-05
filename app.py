import streamlit as st
import pdfplumber
import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
import pandas as pd
from typing import List, Dict, Optional, Tuple
import tempfile
from datetime import datetime
import warnings
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from io import BytesIO
import re
import hashlib

# Suppress warnings
warnings.filterwarnings('ignore')

# Load environment variables and configure API
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Validate API key
if not GOOGLE_API_KEY:
    st.error("⚠️ Google API Key not found! Please add it to your .env file.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# Initialize session state with default values
def initialize_session_state():
    """Initialize all session state variables"""
    defaults = {
        'questions': [],
        'practice_mode': False,
        'user_answers': {},
        'submitted': False,
        'selected_answers': {},
        'pdf_content': None,
        'generation_count': 0,
        'used_questions': set()
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

def extract_text_from_pdf(pdf_file) -> str:
    """Extract text from PDF with enhanced error handling"""
    try:
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            total_pages = len(pdf.pages)
            
            if total_pages == 0:
                st.error("The PDF appears to be empty.")
                return ""
            
            progress_bar = st.progress(0)
            for idx, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                progress_bar.progress((idx + 1) / total_pages)
            
            progress_bar.empty()
            
        if len(text.strip()) < 100:
            st.warning("⚠️ Very little text extracted. The PDF might be image-based or scanned.")
        
        return text.strip()
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return ""

def clean_json_response(response_text: str) -> str:
    """Clean and extract JSON from LLM response"""
    # Remove markdown code blocks
    response_text = re.sub(r'```json\s*', '', response_text)
    response_text = re.sub(r'```\s*', '', response_text)
    
    # Find JSON boundaries
    start_idx = response_text.find('{')
    end_idx = response_text.rfind('}') + 1
    
    if start_idx == -1 or end_idx == 0:
        raise ValueError("No valid JSON found in response")
    
    return response_text[start_idx:end_idx]

def generate_mcqs(content: str, num_questions: int, difficulty: str, exclude_questions: set = None) -> List[Dict]:
    """Generate MCQs with improved error handling and validation"""
    if not content or len(content.strip()) < 50:
        st.error("Not enough content to generate questions.")
        return []
    
    try:
        exclude_text = ""
        if exclude_questions:
            exclude_text = f"\n\nIMPORTANT: Do not generate questions similar to these already used questions:\n{list(exclude_questions)}"
        
        prompt = f"""
        Generate exactly {num_questions} multiple choice questions based on the following content.
        Difficulty level: {difficulty}
        
        {exclude_text}

        Rules:
        1. Each question must have exactly one correct answer
        2. All options must be relevant and plausible
        3. Questions should test understanding, not just memorization
        4. Avoid ambiguous or trick questions
        5. Make distractors (wrong answers) reasonable but clearly incorrect
        6. Return ONLY valid JSON format, no markdown or additional text

        Format (strict JSON):
        {{
            "questions": [
                {{
                    "question": "Clear, specific question text here?",
                    "options": {{
                        "A": "First option",
                        "B": "Second option",
                        "C": "Third option",
                        "D": "Fourth option"
                    }},
                    "correct_answer": "A",
                    "explanation": "Detailed explanation of why A is correct and others are wrong"
                }}
            ]
        }}

        Content:
        {content[:4000]}
        """
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                top_p=0.8,
                top_k=40,
            )
        )
        
        json_str = clean_json_response(response.text)
        questions_data = json.loads(json_str)
        
        # Validate questions
        if 'questions' not in questions_data:
            raise ValueError("Invalid response format: missing 'questions' key")
        
        validated_questions = []
        for q in questions_data['questions']:
            if validate_question(q):
                validated_questions.append(q)
        
        if len(validated_questions) < num_questions:
            st.warning(f"⚠️ Only generated {len(validated_questions)} valid questions out of {num_questions} requested.")
        
        return validated_questions
            
    except json.JSONDecodeError as e:
        st.error(f"❌ Failed to parse questions. Please try again.")
        st.error(f"JSON Error: {str(e)}")
        return []
    except Exception as e:
        st.error(f"❌ Error generating questions: {str(e)}")
        return []

def validate_question(question: Dict) -> bool:
    """Validate question structure and content"""
    required_keys = ['question', 'options', 'correct_answer', 'explanation']
    
    # Check all required keys exist
    if not all(key in question for key in required_keys):
        return False
    
    # Check options structure
    if not isinstance(question['options'], dict):
        return False
    
    # Check if we have 4 options
    if len(question['options']) != 4:
        return False
    
    # Check if correct_answer is one of the options
    if question['correct_answer'] not in question['options']:
        return False
    
    # Check for minimum content length
    if len(question['question']) < 10 or len(question['explanation']) < 20:
        return False
    
    return True

def draw_wrapped_text(c, text, x, y, max_width, font_size=12):
    """Draw wrapped text on PDF canvas"""
    c.setFont("Helvetica", font_size)
    words = text.split()
    lines = []
    line = ""
    
    for word in words:
        test_line = line + word + " "
        if c.stringWidth(test_line) < max_width:
            line = test_line
        else:
            if line:
                lines.append(line.strip())
            line = word + " "
    
    if line:
        lines.append(line.strip())
    
    for line in lines:
        if y < 50:  # Check if we need a new page
            c.showPage()
            y = 750
            c.setFont("Helvetica", font_size)
        c.drawString(x, y, line)
        y -= (font_size + 3)
    
    return y

def generate_pdf(questions, user_answers, correct, total, score_percentage):
    """Generate enhanced PDF with better formatting"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 50
    max_width = width - 2 * margin
    y = height - margin

    # Header with better styling
    c.setFont("Helvetica-Bold", 20)
    c.drawString(margin, y, "MCQ Quiz Results")
    y -= 25
    
    c.setFont("Helvetica", 10)
    c.drawString(margin, y, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 35

    # Score summary box
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, f"Final Score: {correct}/{total} ({score_percentage:.1f}%)")
    
    if score_percentage >= 80:
        status = "Excellent! 🌟"
    elif score_percentage >= 60:
        status = "Good job! 👍"
    else:
        status = "Keep practicing! 💪"
    
    c.setFont("Helvetica", 12)
    c.drawString(margin, y - 20, f"Status: {status}")
    y -= 50

    # Questions
    for i, q in enumerate(questions):
        user_answer = user_answers.get(i, "Not answered")
        is_correct = user_answer == q['correct_answer']

        if y < 150:  # Check if we need a new page
            c.showPage()
            y = height - margin

        # Question header
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, f"Question {i+1}:")
        y -= 20
        
        # Question text
        c.setFont("Helvetica", 11)
        y = draw_wrapped_text(c, q['question'], margin + 10, y, max_width - 10, 11)
        y -= 10

        # Options
        c.setFont("Helvetica", 10)
        for opt, text in sorted(q['options'].items()):
            if y < 80:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica", 10)
            
            # Color coding
            if opt == user_answer:
                if is_correct:
                    c.setFillColorRGB(0, 0.6, 0)  # Green
                else:
                    c.setFillColorRGB(0.8, 0, 0)  # Red
            elif opt == q['correct_answer'] and not is_correct:
                c.setFillColorRGB(0, 0.6, 0)  # Green
            else:
                c.setFillColorRGB(0, 0, 0)  # Black

            option_text = f"   {opt}. {text}"
            if opt == user_answer:
                option_text += " ← Your answer"
            if opt == q['correct_answer']:
                option_text += " ✓ Correct"
                
            y = draw_wrapped_text(c, option_text, margin + 20, y, max_width - 40, 10)
            y -= 3

        # Explanation
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 10)
        y -= 10
        if y < 60:
            c.showPage()
            y = height - margin
        c.drawString(margin + 10, y, "Explanation:")
        c.setFont("Helvetica-Oblique", 9)
        y -= 15
        y = draw_wrapped_text(c, q['explanation'], margin + 20, y, max_width - 40, 9)
        y -= 25

    c.save()
    buffer.seek(0)
    return buffer.getvalue()

def calculate_score():
    """Calculate quiz score with detailed statistics"""
    correct = 0
    total = len(st.session_state.questions)
    unanswered = 0
    
    for i, q in enumerate(st.session_state.questions):
        if i in st.session_state.user_answers and st.session_state.user_answers[i]:
            if st.session_state.user_answers[i] == q['correct_answer']:
                correct += 1
        else:
            unanswered += 1
    
    return correct, total, unanswered

def reset_quiz():
    """Reset quiz state"""
    st.session_state.practice_mode = False
    st.session_state.submitted = False
    st.session_state.user_answers = {}
    st.session_state.selected_answers = {}
    st.session_state.questions = []
    st.session_state.generation_count = 0
    st.session_state.used_questions = set()

def main():
    st.set_page_config(
        page_title="MCQ Generator",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Sidebar with info
    with st.sidebar:
        st.title("ℹ️ About")
        st.write("**MCQ Generator** helps you create practice questions from your lecture slides.")
        st.write("**Features:**")
        st.write("- 📄 PDF text extraction")
        st.write("- 🤖 AI-powered questions")
        st.write("- 📊 Instant feedback")
        st.write("- 📥 PDF export")
        st.write("---")
        st.write("**Created by:**")
        st.write("Mohammad Ayaz Alam")
        st.write("---")
        
        if st.session_state.practice_mode:
            st.write("**Current Session:**")
            st.write(f"Questions: {len(st.session_state.questions)}")
            st.write(f"Generation count: {st.session_state.generation_count}")
            if st.button("🔄 Reset Quiz", use_container_width=True):
                reset_quiz()
                st.rerun()
    
    # Page Header
    st.title("📚 Lecture Slides MCQ Generator")
    st.markdown("Upload your lecture slides and generate AI-powered multiple choice questions!")
    st.divider()

    # File Upload Section
    uploaded_file = st.file_uploader(
        "Upload your lecture slides (PDF format)",
        type=['pdf'],
        help="Upload a text-based PDF file. Scanned PDFs may not work properly."
    )
    
    if uploaded_file:
        # Save PDF content to session state
        if st.session_state.pdf_content is None:
            st.session_state.pdf_content = uploaded_file
        
        # Configuration Options
        st.subheader("⚙️ Configuration")
        col1, col2 = st.columns(2)
        
        with col1:
            difficulty = st.select_slider(
                "Select difficulty level",
                options=["Easy", "Medium", "Hard"],
                value="Medium",
                help="Easy: Basic recall | Medium: Understanding | Hard: Application & Analysis"
            )
        
        with col2:
            num_questions = st.number_input(
                "Number of questions",
                min_value=1,
                max_value=25,
                value=10,
                help="Maximum 25 questions per generation"
            )

        st.divider()

        # Action Button
        if not st.session_state.practice_mode:
            if st.button("🚀 Start Practice Mode", use_container_width=True, type="primary"):
                with st.spinner("🔄 Processing slides and generating questions..."):
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_file_path = tmp_file.name

                        text_content = extract_text_from_pdf(tmp_file_path)
                        os.unlink(tmp_file_path)

                        if not text_content.strip():
                            st.error("❌ Could not extract text from the PDF. Please ensure it's not scanned or image-based.")
                            return
                        
                        if len(text_content.strip()) < 100:
                            st.error("❌ Insufficient content extracted from PDF. Please try a different file.")
                            return

                        questions = generate_mcqs(text_content, num_questions, difficulty)
                        if questions:
                            st.session_state.questions = questions
                            st.session_state.practice_mode = True
                            st.session_state.generation_count += 1
                            st.session_state.pdf_content = text_content
                            
                            # Store question signatures to avoid duplicates
                            for q in questions:
                                st.session_state.used_questions.add(q['question'][:50])
                            
                            st.success(f"✅ Generated {len(questions)} questions successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to generate questions. Please try again.")

                    except Exception as e:
                        st.error(f"❌ An error occurred: {str(e)}")
                        st.exception(e)

    # Practice Mode Section
    if st.session_state.practice_mode and st.session_state.questions:
        if not st.session_state.submitted:
            st.subheader("📝 Practice Mode")
            st.info(f"Answer all {len(st.session_state.questions)} questions below and submit to see your score!")
            st.divider()
            
            # Display Questions with better formatting
            for i, q in enumerate(st.session_state.questions):
                with st.container():
                    st.markdown(f"### Question {i+1}")
                    st.markdown(f"**{q['question']}**")
                    
                    options = {opt: text for opt, text in sorted(q['options'].items())}
                    
                    selected_answer = st.radio(
                        "Select your answer:",
                        list(options.keys()),
                        key=f"q_{i}",
                        format_func=lambda x: f"{x}. {options[x]}",
                        index=None,
                        help="Choose the best answer"
                    )
                    st.session_state.user_answers[i] = selected_answer
                    st.divider()
            
            # Submit Button
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("✅ Submit Answers", use_container_width=True, type="primary"):
                    # Check if all questions are answered
                    unanswered = [i+1 for i in range(len(st.session_state.questions)) 
                                 if i not in st.session_state.user_answers or st.session_state.user_answers[i] is None]
                    
                    if unanswered:
                        st.warning(f"⚠️ Please answer all questions before submitting. Unanswered: {', '.join(map(str, unanswered))}")
                    else:
                        st.session_state.submitted = True
                        st.rerun()

        # Show Results
        if st.session_state.submitted:
            correct, total, unanswered = calculate_score()
            score_percentage = (correct / total) * 100 if total > 0 else 0
            
            st.subheader("📊 Quiz Results")
            
            # Score metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Questions", total)
            with col2:
                st.metric("Correct Answers", correct, delta=f"{correct}/{total}")
            with col3:
                st.metric("Score", f"{score_percentage:.1f}%")
            with col4:
                if score_percentage >= 80:
                    st.success("Excellent! 🌟")
                elif score_percentage >= 60:
                    st.info("Good job! 👍")
                else:
                    st.warning("Keep practicing! 💪")
            
            st.divider()

            # Detailed Review
            st.subheader("📖 Detailed Review")
            
            for i, q in enumerate(st.session_state.questions):
                user_answer = st.session_state.user_answers.get(i, None)
                is_correct = user_answer == q['correct_answer']
                
                status = "✅ Correct" if is_correct else "❌ Incorrect"
                expander_type = "🟢" if is_correct else "🔴"
                
                with st.expander(f"{expander_type} Question {i+1} - {status}"):
                    st.markdown(f"**Question:** {q['question']}")
                    st.markdown("**Options:**")
                    
                    for opt, text in sorted(q['options'].items()):
                        if opt == user_answer:
                            if is_correct:
                                st.success(f"✅ {opt}. {text} (Your answer - Correct!)")
                            else:
                                st.error(f"❌ {opt}. {text} (Your answer - Incorrect)")
                        elif opt == q['correct_answer'] and not is_correct:
                            st.success(f"✓ {opt}. {text} (Correct answer)")
                        else:
                            st.write(f"{opt}. {text}")
                    
                    st.markdown("**Explanation:**")
                    st.info(q['explanation'])
            
            st.divider()
            
            # Action buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("➕ Add New Question", use_container_width=True):
                    with st.spinner("🔄 Generating a new unique question..."):
                        try:
                            if st.session_state.pdf_content:
                                new_questions = generate_mcqs(
                                    st.session_state.pdf_content,
                                    1,
                                    difficulty,
                                    st.session_state.used_questions
                                )
                                if new_questions:
                                    st.session_state.questions.append(new_questions[0])
                                    st.session_state.used_questions.add(new_questions[0]['question'][:50])
                                    st.session_state.submitted = False
                                    st.success("✅ New question added!")
                                    st.rerun()
                                else:
                                    st.error("❌ Could not generate new question")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")

            with col2:
                pdf_data = generate_pdf(
                    st.session_state.questions,
                    st.session_state.user_answers,
                    correct,
                    total,
                    score_percentage
                )
                st.download_button(
                    label="📥 Download PDF Report",
                    data=pdf_data,
                    file_name=f"quiz_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            with col3:
                if st.button("🔄 Start New Quiz", use_container_width=True):
                    reset_quiz()
                    st.rerun()

if __name__ == "__main__":
    main()