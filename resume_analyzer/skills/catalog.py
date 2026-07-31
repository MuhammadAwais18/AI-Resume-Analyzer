"""Skill taxonomy.

Each entry is ``(canonical name, category, market weight, aliases)``.

* **weight** expresses relative market importance and drives the weighted ATS
  score. ``1.0`` is the baseline; ``1.4`` marks high-demand specialisations.
* **aliases** capture the spellings recruiters and candidates actually use
  (``"js"``, ``"node"``, ``"postgres"``), which is what makes synonym matching
  work.

Phase 1 seeds the registry with the core catalog; Phase 4 expands it to the
full enterprise database.
"""

from __future__ import annotations

from typing import Final

from resume_analyzer.domain.models import SkillCategory

SkillSpec = tuple[str, SkillCategory, float, tuple[str, ...]]

C = SkillCategory

SKILL_CATALOG: Final[tuple[SkillSpec, ...]] = (
    # -- Programming languages ---------------------------------------------
    ("Python", C.PROGRAMMING_LANGUAGE, 1.3, ("python3", "py")),
    ("JavaScript", C.PROGRAMMING_LANGUAGE, 1.3, ("js", "ecmascript", "es6")),
    ("TypeScript", C.PROGRAMMING_LANGUAGE, 1.3, ("ts",)),
    ("Java", C.PROGRAMMING_LANGUAGE, 1.2, ("java se", "java ee", "j2ee")),
    ("C++", C.PROGRAMMING_LANGUAGE, 1.1, ("cpp", "c plus plus")),
    ("C#", C.PROGRAMMING_LANGUAGE, 1.1, ("csharp", "c sharp", ".net c#")),
    ("C", C.PROGRAMMING_LANGUAGE, 1.0, ()),
    ("Go", C.PROGRAMMING_LANGUAGE, 1.2, ("golang",)),
    ("Rust", C.PROGRAMMING_LANGUAGE, 1.2, ()),
    ("Ruby", C.PROGRAMMING_LANGUAGE, 1.0, ()),
    ("PHP", C.PROGRAMMING_LANGUAGE, 0.9, ()),
    ("Swift", C.PROGRAMMING_LANGUAGE, 1.1, ()),
    ("Kotlin", C.PROGRAMMING_LANGUAGE, 1.1, ()),
    ("Scala", C.PROGRAMMING_LANGUAGE, 1.1, ()),
    ("R", C.PROGRAMMING_LANGUAGE, 1.0, ("r language",)),
    ("SQL", C.PROGRAMMING_LANGUAGE, 1.3, ("structured query language",)),
    ("Bash", C.PROGRAMMING_LANGUAGE, 1.0, ("shell scripting", "shell", "sh")),
    # -- Frontend -----------------------------------------------------------
    ("React", C.FRONTEND, 1.3, ("react.js", "reactjs")),
    ("Next.js", C.FRONTEND, 1.2, ("nextjs", "next js")),
    ("Angular", C.FRONTEND, 1.1, ("angularjs", "angular 2+")),
    ("Vue.js", C.FRONTEND, 1.1, ("vue", "vuejs")),
    ("HTML", C.FRONTEND, 0.8, ("html5",)),
    ("CSS", C.FRONTEND, 0.8, ("css3",)),
    ("Tailwind CSS", C.FRONTEND, 1.0, ("tailwind", "tailwindcss")),
    ("Redux", C.FRONTEND, 1.0, ("redux toolkit",)),
    # -- Backend ------------------------------------------------------------
    ("Node.js", C.BACKEND, 1.2, ("nodejs", "node")),
    ("Django", C.BACKEND, 1.2, ()),
    ("Flask", C.BACKEND, 1.1, ()),
    ("FastAPI", C.BACKEND, 1.2, ("fast api",)),
    ("Spring Boot", C.BACKEND, 1.2, ("springboot", "spring")),
    ("Express.js", C.BACKEND, 1.0, ("express", "expressjs")),
    ("GraphQL", C.BACKEND, 1.1, ()),
    ("REST API", C.BACKEND, 1.2, ("rest", "restful", "restful api", "rest apis")),
    ("Microservices", C.BACKEND, 1.2, ("microservice architecture",)),
    # -- Databases ----------------------------------------------------------
    ("PostgreSQL", C.DATABASE, 1.2, ("postgres", "psql")),
    ("MySQL", C.DATABASE, 1.1, ()),
    ("MongoDB", C.DATABASE, 1.1, ("mongo",)),
    ("Redis", C.DATABASE, 1.1, ()),
    ("SQLite", C.DATABASE, 0.9, ()),
    ("Elasticsearch", C.DATABASE, 1.1, ("elastic search", "elk")),
    # -- Cloud --------------------------------------------------------------
    ("AWS", C.CLOUD, 1.4, ("amazon web services",)),
    ("Microsoft Azure", C.CLOUD, 1.3, ("azure",)),
    ("Google Cloud Platform", C.CLOUD, 1.3, ("gcp", "google cloud")),
    # -- DevOps & containers -------------------------------------------------
    ("Docker", C.CONTAINERIZATION, 1.3, ("dockerize", "containerization")),
    ("Kubernetes", C.CONTAINERIZATION, 1.4, ("k8s",)),
    ("Terraform", C.DEVOPS, 1.3, ()),
    ("Jenkins", C.DEVOPS, 1.1, ()),
    ("CI/CD", C.DEVOPS, 1.2, ("cicd", "continuous integration", "ci cd")),
    ("GitHub Actions", C.DEVOPS, 1.1, ("gh actions",)),
    ("Linux", C.OPERATING_SYSTEM, 1.1, ("ubuntu", "unix", "debian")),
    # -- Version control ------------------------------------------------------
    ("Git", C.VERSION_CONTROL, 1.1, ()),
    ("GitHub", C.VERSION_CONTROL, 1.0, ()),
    # -- Data / AI ------------------------------------------------------------
    ("Machine Learning", C.MACHINE_LEARNING, 1.4, ("ml", "machine-learning")),
    ("Deep Learning", C.DEEP_LEARNING, 1.4, ("dl", "neural networks")),
    ("Natural Language Processing", C.NLP, 1.3, ("nlp",)),
    ("TensorFlow", C.DEEP_LEARNING, 1.2, ("tf", "tensorflow 2")),
    ("PyTorch", C.DEEP_LEARNING, 1.3, ("torch",)),
    ("scikit-learn", C.MACHINE_LEARNING, 1.2, ("sklearn", "scikit learn")),
    ("Pandas", C.DATA_SCIENCE, 1.1, ()),
    ("NumPy", C.DATA_SCIENCE, 1.0, ()),
    ("Apache Spark", C.DATA_ENGINEERING, 1.3, ("spark", "pyspark")),
    ("Power BI", C.DATA_SCIENCE, 1.0, ("powerbi", "power-bi")),
    ("Tableau", C.DATA_SCIENCE, 1.0, ()),
    ("Excel", C.TOOL, 0.7, ("microsoft excel", "ms excel")),
    # -- Testing ---------------------------------------------------------------
    ("pytest", C.TESTING, 1.0, ("py.test",)),
    ("Unit Testing", C.TESTING, 1.0, ("unit tests", "unittest")),
    ("Selenium", C.TESTING, 0.9, ()),
    # -- Tools ------------------------------------------------------------------
    ("Streamlit", C.FRAMEWORK, 1.0, ()),
    ("Jira", C.TOOL, 0.8, ()),
    ("Agile", C.TOOL, 0.9, ("scrum", "kanban", "agile methodology")),
)
