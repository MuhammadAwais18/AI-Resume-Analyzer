<div align="center">

# 📄 AI Resume Analyzer

**Recruiter-grade resume intelligence — a weighted ATS engine, a 568-skill detection catalog and grounded AI review, in a premium Streamlit dashboard.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.60-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/tests-306%20passing-10B981)](#-testing)
[![Ruff](https://img.shields.io/badge/lint-ruff%20clean-6366F1)](https://docs.astral.sh/ruff/)
[![License](https://img.shields.io/badge/license-MIT-64748B)](LICENSE)

</div>

---

## Overview

Most resume tools count keyword overlap and call it a score. Real applicant tracking systems don't work that way — they weight *must-have* skills far above *nice-to-haves*, gate on seniority and education, and filter candidates with hard capability gaps before a human ever reads the file.

**AI Resume Analyzer** reproduces that behaviour. Upload a resume, paste a job description, and get a transparent, explainable ATS score, a full skill-gap analysis, and an AI review that is grounded in the deterministic results so it cannot invent facts.

> **Design principle:** the AI is an *enhancement*, never a dependency. Every feature — scoring, parsing, charts, PDF export — works with the language model switched off.

---

## ✨ Features

### Analysis engine
- **Weighted ATS scoring** across six explainable components, each reporting its own sub-score and rationale
- **Required vs. preferred skill detection** — reads the sentence a skill appears in (`"must have"` vs. `"nice to have"`)
- **Knock-out rule** capping candidates who miss most must-have skills, as commercial ATS platforms do
- **Semantic similarity** via TF-IDF cosine + bigram Jaccard — no 400 MB transformer download
- **Experience & education gating** against the seniority bar stated in the posting

### Resume parsing
- Extracts **14 fields**: name, email, phone, LinkedIn, GitHub, portfolio, location, skills, experience, education, certifications, projects, awards, achievements and languages
- Reads **PDF and DOCX**, including DOCX tables, headers and footers
- **Section-aware**: detects headings and table-style `SKILLS | Python, Go` layouts
- Handles **scanned, corrupt, encrypted and malformed** files with friendly, typed errors
- **spaCy is optional** — improves name detection when installed, degrades gracefully when not

### Skill intelligence
- **568 skills** across 22 categories with **1,284 lookup terms**
- **Synonym matching**: `k8s` → Kubernetes, `postgres` → PostgreSQL, `golang` → Go
- **Context gating** so `"I like to go to the office"` doesn't register as Go
- **Adjacent-technology suggestions** from a 67-node related-skills graph

### AI review
- Ten sections: executive summary, ATS review, strengths, weaknesses, missing skills, improvements, recruiter impression, interview readiness, rating and career advice
- **Grounded** in the deterministic analysis to suppress hallucination
- **Prompt-injection hardened** — resume text is framed as untrusted data
- **Salvages** markdown answers from models that ignore the JSON schema
- Falls back to a full deterministic review on timeout, rate limit, network or auth failure

### Experience
- Premium dark dashboard: glassmorphism, layered depth, animated gradients, micro-interactions
- Ten interactive Plotly visualisations, all with graceful empty states
- Branded multi-page **PDF report** with a gradient cover and vector charts
- **History analytics** with trend tracking and summary statistics
- Accessible: honours `prefers-reduced-motion`, responsive down to mobile

---

## 🏛 Architecture

The codebase is layered, and dependencies point strictly inward. Nothing below the UI layer imports Streamlit, which keeps the entire core testable and reusable from a CLI, an API or a batch job.

```
┌──────────────────────────────────────────────────────────────┐
│  app.py — composition root (Streamlit)                       │
│  page config · session state · caching · error boundaries    │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  ui/            theme · components · charts · dashboard      │  ← only layer
│                 design tokens, escaped HTML, Plotly figures  │    importing
└───────────────────────────┬──────────────────────────────────┘    Streamlit
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  services/      analysis_service — pipeline orchestration    │
└───────────────────────────┬──────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┬──────────────┐
        ▼                   ▼                   ▼              ▼
┌──────────────┐   ┌─────────────────┐   ┌────────────┐  ┌──────────┐
│  parsing/    │   │  scoring/       │   │  skills/   │  │  ai/     │
│  document    │   │  ats_engine     │   │  catalog   │  │  prompts │
│  resume_     │   │  job_parser     │   │  registry  │  │  reviewer│
│  parser      │   │  similarity     │   │  (568)     │  │          │
│  patterns    │   │                 │   │            │  │          │
│  nlp (opt.)  │   │                 │   │            │  │          │
└──────────────┘   └─────────────────┘   └────────────┘  └──────────┘
        │                   │                   │              │
        └───────────────────┴─────────┬─────────┴──────────────┘
                                      ▼
┌──────────────────────────────────────────────────────────────┐
│  domain/  typed dataclasses  ·  exceptions  ·  utils_text    │
└───────────────────────────┬──────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐   ┌─────────────────┐   ┌──────────────┐
│ persistence/ │   │  reporting/     │   │  analytics/  │
│ SQLite + WAL │   │  PDF (ReportLab)│   │  statistics  │
└──────────────┘   └─────────────────┘   └──────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  config/   settings (env + st.secrets) · constants · logging │
└──────────────────────────────────────────────────────────────┘
```

### Data flow

```
Upload ──▶ validate ──▶ extract text ──▶ parse profile ──┐
                                                          ├──▶ score ──▶ AI review ──▶ dashboard
Job description ──▶ parse requirements ───────────────────┘         │
                                                                     └──▶ persist ──▶ PDF report
```

---

## 🧮 How the ATS score works

| Component | Weight | What it measures |
|---|---:|---|
| **Required Skills** | 40% | Market-weighted coverage of must-have skills |
| **Semantic Match** | 15% | Topical alignment between resume and posting |
| **Experience** | 14% | Years detected vs. the stated minimum |
| **Keyword Relevance** | 13% | Distinctive job terms present in the resume |
| **Preferred Skills** | 10% | Coverage of nice-to-have skills |
| **Education** | 8% | Degree level vs. the requirement |

Skills carry individual **market weights** (Kubernetes 1.4, jQuery 0.7), so matching a high-demand skill moves the score more than matching a commodity one.

**Knock-out rule:** below 30% required-skill coverage the score is capped at 48, so polished prose can never mask a hard capability gap.

**Calibration** (verified by property-based tests):

| Candidate | Score | Verdict |
|---|---:|---|
| All required + preferred skills, 8 yrs, MSc | 86 | Excellent Match |
| All required skills, 6 yrs, BSc | 77 | Good Match |
| Same skills written only as synonyms | 68 | Good Match |
| Partial skills, 3 yrs | 29 | Low Match |
| Unrelated field (pastry chef) | 20 | Low Match |

---

## 🚀 Installation

**Prerequisites:** Python 3.10+

```bash
git clone https://github.com/MuhammadAwais18/AI-Resume-Analyzer.git
cd AI-Resume-Analyzer

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://openrouter.ai/api/v1
MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
```

> The app runs **without** an API key — AI review falls back to the deterministic engine and every other feature is unaffected.

Run it:

```bash
streamlit run app.py
```

Open <http://localhost:8501>.

### Optional: enhanced name detection

```bash
python -m spacy download en_core_web_sm
```

spaCy is loaded lazily. If the model is absent the parser uses regex heuristics and logs a single informational line.

---

## 🗂 Project structure

```
AI-Resume-Analyzer/
├── app.py                          # Streamlit composition root
├── resume_analyzer/
│   ├── config/
│   │   ├── settings.py             # Immutable settings, env + st.secrets
│   │   ├── constants.py            # Thresholds, limits, palette
│   │   └── logging_config.py       # Rerun-safe logging
│   ├── domain/models.py            # Typed dataclasses
│   ├── exceptions.py               # Error hierarchy with user-safe messages
│   ├── utils_text.py               # Pure text helpers
│   ├── parsing/
│   │   ├── document.py             # PDF/DOCX extraction + validation
│   │   ├── resume_parser.py        # 14-field structured extraction
│   │   ├── patterns.py             # Compiled regexes and vocabularies
│   │   └── nlp.py                  # Optional spaCy integration
│   ├── skills/
│   │   ├── catalog.py              # 568-skill taxonomy
│   │   └── registry.py             # Detection, synonyms, context gating
│   ├── scoring/
│   │   ├── ats_engine.py           # Weighted six-component scorer
│   │   ├── job_parser.py           # Required vs. preferred extraction
│   │   └── similarity.py           # TF-IDF + bigram similarity
│   ├── ai/
│   │   ├── prompts.py              # Grounded, injection-hardened prompts
│   │   └── reviewer.py             # Retries, salvage, fallback review
│   ├── services/analysis_service.py# Pipeline orchestration
│   ├── persistence/repository.py   # SQLite + WAL + migrations
│   ├── reporting/pdf_report.py     # Branded PDF with vector charts
│   ├── analytics/statistics.py     # Readability metrics
│   └── ui/
│       ├── theme.py                # Design tokens + stylesheet
│       ├── components.py           # Escaped HTML components
│       ├── charts.py               # 10 Plotly figures
│       └── dashboard.py            # Section views
├── utils/                          # v1 backwards-compatible facades
├── tests/                          # 306 tests
├── requirements.txt
└── pyproject.toml                  # Ruff + pytest configuration
```

### `utils/` — why it still exists

The original v1 modules are preserved as thin, documented facades that delegate to the new package and return the exact v1 shapes. Any existing script, notebook or fork that does `from utils.scorer import calculate_score` keeps working unchanged. New code should import from `resume_analyzer` directly.

---

## 🧪 Testing

```bash
pip install pytest ruff
pytest              # 306 tests, ~5 seconds
ruff check .        # lint
```

| Suite | Focus |
|---|---|
| `test_parser.py` · `test_parser_real_world.py` | Extraction from generated PDF/DOCX, international phones, degree disambiguation, malformed files |
| `test_scorer.py` · `test_ats_calibration.py` | Score bounds, component reconstruction, strict candidate ranking, knock-out rule |
| `test_skills.py` · `test_skills_catalog.py` | Recall per category, precision on prose, alias collisions, detection latency |
| `test_ai.py` · `test_ai_resilience.py` | JSON parsing, markdown salvage, timeout/rate-limit/network handling, prompt injection |
| `test_database.py` | CRUD, filtering, aggregates, **v1 → v2 schema migration** |
| `test_ui.py` | HTML escaping (XSS), chart integrity, empty states |
| `test_report.py` | PDF sections, glyph artifacts, escaping, edge cases |

Tests assert **behavioural properties** (e.g. "a better candidate always outranks a weaker one") rather than magic numbers, so the engine can be tuned without churning the suite.

---

## ⚡ Performance

| Operation | Time |
|---|---:|
| Cold start (imports + compiling 568 skill patterns) | ~370 ms |
| Warm analysis (parse + score + statistics) | **~48 ms** |
| PDF report generation | ~33 ms |
| Full test suite | ~5 s |

**Techniques used**
- `st.cache_resource` for the one-time bootstrap (DB migration, pattern compilation)
- `st.cache_data` so the PDF is built once per analysis, not on every rerun
- `functools.lru_cache` on pattern compilation, settings and tokenisation
- Session state so interacting with the page never re-runs the pipeline
- Skill patterns compiled once per process, not per call
- SQLite WAL mode with indexes on the queried columns

---

## 🛡 Error handling

Every failure path raises a typed exception carrying a `user_message`. Stack traces and provider payloads go to the logs; users only ever see plain language.

| Situation | What the user sees |
|---|---|
| Non-PDF/DOCX upload | *Unsupported file type. Please upload a PDF or DOCX resume.* |
| Scanned image PDF | *No readable text was found… please upload a text-based PDF or DOCX.* |
| Corrupt / encrypted file | *This file appears to be corrupted or password protected.* |
| Missing job description | *Please paste a job description to compare against.* |
| AI timeout | *The AI reviewer took too long to respond.* + full deterministic review |
| AI rate limited | *The AI reviewer is rate limited at the moment.* + full deterministic review |
| No API key | *AI review is not configured…* + full deterministic review |

---

## 🚢 Deployment

### Streamlit Community Cloud

1. Push to GitHub.
2. Create an app at [share.streamlit.io](https://share.streamlit.io) pointing at `app.py`.
3. Add secrets under **App settings → Secrets**:

```toml
OPENAI_API_KEY = "your_api_key_here"
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
```

Settings resolve from environment variables **and** `st.secrets`, so the same code runs locally and in the cloud with no changes.

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

> **Note on persistence:** analysis history is stored in `data/resume_history.db`. On ephemeral hosts this resets on redeploy — mount a volume, or point `RESUME_DB_PATH` at durable storage.

---

## 🧭 Roadmap

- [ ] OCR fallback (Tesseract) so scanned resumes are readable
- [ ] Multi-resume comparison and candidate ranking
- [ ] Optional sentence-transformer embeddings behind a feature flag
- [ ] Cover-letter generation from the gap analysis
- [ ] Job-board integrations (LinkedIn, Indeed) for one-click imports
- [ ] FastAPI service exposing the core as a REST API (the layering already allows it)
- [ ] Postgres backend for multi-user deployments
- [ ] i18n for non-English resumes

---

## 🔧 Tech stack

| Layer | Technology |
|---|---|
| UI | Streamlit, custom CSS design system, Plotly |
| Parsing | pdfplumber, python-docx, spaCy *(optional)* |
| AI | OpenAI-compatible API (OpenRouter) |
| Reporting | ReportLab (vector charts, no browser dependency) |
| Storage | SQLite (WAL) |
| Tooling | pytest, Ruff |

---

## 🤝 Contributing

```bash
pytest && ruff check .
```

Both must pass. Adding a skill is a one-line change to `resume_analyzer/skills/catalog.py` — no code changes required.

---

## 📄 License

MIT — see [LICENSE](LICENSE).

<div align="center">
<sub>Built with an emphasis on correctness, explainability and graceful degradation.</sub>
</div>
