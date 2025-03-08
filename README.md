# MCQ Generator Using Google Gemini LLM 📚

A streamlined Multiple Choice Question (MCQ) generator that uses Google's Gemini LLM to create questions from PDF lecture slides.

## Live Demo 🌐

Try it out here: [MCQ Generator App](https://mcq-generate.streamlit.app/)

## Features 🌟

- **PDF Processing**: Upload and extract text from lecture slides
- **AI-Powered Question Generation**: Utilizes Google Gemini LLM for creating relevant MCQs
- **Difficulty Levels**: Choose between Easy, Medium, and Hard questions
- **Interactive Practice Mode**: Take the quiz and get instant feedback
- **Detailed Results**: Review your answers with explanations
- **PDF Export**: Download your quiz results in a well-formatted PDF
- **Add New Questions**: Generate additional unique questions on demand

## Installation 🛠️

1. Clone the repository:
```bash
git clone https://github.com/rebel47/mcq-generator.git
cd mcq-generator
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # For Linux/Mac
# OR
.venv\Scripts\activate  # For Windows
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root and add your Google API key:
```env
GOOGLE_API_KEY=your_api_key_here
```

## Required Packages 📦

```text
streamlit
pdfplumber
python-dotenv
google-generativeai
pandas
reportlab
```

## Usage 🚀

1. Run the Streamlit app locally:
```bash
streamlit run app.py
```

2. Or visit the deployed version: [https://mcq-generate.streamlit.app/](https://mcq-generate.streamlit.app/)

3. Upload your PDF lecture slides

4. Configure your preferences:
   - Select difficulty level (Easy/Medium/Hard)
   - Choose number of questions (1-30)

5. Click "Start Practice Mode" to generate questions

6. Answer the questions and submit to see your results

7. Download results as PDF or generate new questions as needed

## Features in Detail 📋

### PDF Processing
- Supports text-based PDF files
- Extracts content while maintaining readability
- Error handling for scanned or image-based PDFs

### Question Generation
- AI-powered question creation using Google Gemini
- Contextually relevant questions based on content
- Multiple difficulty levels
- Automatic answer and explanation generation

### Practice Mode
- Interactive quiz interface
- Real-time feedback
- Score calculation
- Detailed explanations for each question

### Results and Export
- Comprehensive score summary
- Question-by-question review
- Color-coded correct/incorrect answers
- PDF export with formatted results

## Contributing 🤝

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements 🙏

- Google Gemini LLM for powering the question generation
- Streamlit for the web interface
- ReportLab for PDF generation
- All contributors and supporters of the project

## Contact 📧

Developer: [@rebel47](https://github.com/rebel47)

Project Links:
- GitHub Repository: [https://github.com/rebel47/mcq-generator](https://github.com/rebel47/mcq-generator)
- Live Demo: [https://mcq-generate.streamlit.app/](https://mcq-generate.streamlit.app/)

## Last Updated 🕒

- **Date**: 2025-03-08 13:50:01 UTC
- **Current Version**: 1.0.0
- **Deployment Status**: [![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://mcq-generate.streamlit.app/)
