import sqlite3

DB_PATH = "data/resume_history.db"


def create_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_name TEXT,
            score INTEGER,
            analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_analysis(resume_name, score):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO history
        (resume_name, score)
        VALUES (?, ?)
        """,
        (resume_name, score)
    )

    conn.commit()
    conn.close()


def get_history():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT resume_name, score, analysis_date
        FROM history
        ORDER BY analysis_date DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return rows