📄 AI Resume Analyzer

An AI-powered Resume Analyzer built with Python, Streamlit, and OpenRouter AI. The application analyzes resumes against a job description, calculates an ATS match score, detects important resume information, generates AI-powered feedback, and exports a professional PDF report.

⸻

🚀 Features

* 📄 Upload Resume (PDF & DOCX)
* 🎯 ATS Match Score
* 🤖 AI Resume Review
* 📊 Interactive ATS Score Chart
* 📈 Resume Statistics
* 📧 Email Detection
* 📞 Phone Number Detection
* 🎓 Education Detection
* 💼 Experience Detection
* 🛠 Skills Detection
* ✅ Matched Skills Analysis
* ❌ Missing Skills Analysis
* 📑 Resume Preview
* 📄 PDF Report Generation
* 🗂 Analysis History (SQLite Database)

⸻

🛠 Tech Stack

* Python
* Streamlit
* OpenRouter API
* Plotly
* SQLite
* pdfplumber
* python-docx
* ReportLab
* spaCy
* Pandas

⸻

📂 Project Structure

AI-Resume-Analyzer/
│
├── assets/
├── data/
├── utils/
│   ├── ai.py
│   ├── parser.py
│   ├── scorer.py
│   ├── stats.py
│   ├── charts.py
│   ├── database.py
│   ├── nlp_parser.py
│   └── pdf_report.py
│
├── app.py
├── requirements.txt
├── .env
├── .gitignore
└── README.md

⸻

⚙️ Installation

Clone the repository:

git clone https://github.com/YOUR_USERNAME/AI-Resume-Analyzer.git

Open the project:

cd AI-Resume-Analyzer

Create a virtual environment:

python -m venv venv

Activate the virtual environment.

Install dependencies:

pip install -r requirements.txt

⸻

🔑 Environment Variables

Create a .env file:

OPENAI_API_KEY=YOUR_API_KEY
OPENAI_BASE_URL=https://openrouter.ai/api/v1
MODEL=YOUR_MODEL

⸻

▶️ Run the Application

streamlit run app.py

⸻

📸 Screenshots

Add screenshots of:

* Home Page
* ATS Score Dashboard
* AI Resume Review
* PDF Report

⸻

🗺 Roadmap

* Resume Comparison
* Advanced ATS Scoring
* Search & Filter History
* Streamlit Cloud Deployment
* Docker Support
* GitHub Actions
* Unit Tests

⸻

🤝 Contributing

Contributions, suggestions, and feature requests are welcome.

⸻

📄 License

This project is licensed under the MIT License.

⸻

👤 Author

Muhammad Awais

If you found this project useful, consider giving it a ⭐ on GitHub.