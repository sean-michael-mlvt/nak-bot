import sqlite3
import logging

DB_NAME = "nakbot.db"

logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

def init_db():
    with sqlite3.connect(DB_NAME, timeout=3) as connection:
        cursor = connection.cursor()

        # Trivia questions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trivia_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                question_type TEXT CHECK(question_type IN ('TF', 'QA')) NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                difficulty INTEGER CHECK(difficulty BETWEEN 1 AND 5),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                asked_at TIMESTAMP,
                expires_at TIMESTAMP,
                closed INTEGER DEFAULT 0 CHECK(closed IN (0,1))
            )
        """)

        # User answers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                answer TEXT NOT NULL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(question_id, user_id)
            )
        """)

        # Leaderboard table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard (
                user_id TEXT PRIMARY KEY,
                points INTEGER DEFAULT 0
            )
        """)


def store_question(guild_id: int, q_type: str, question: str, answer: str, difficulty: int):
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.execute("""
            INSERT INTO trivia_questions (guild_id, question_type, question, answer, difficulty)
            VALUES (?, ?, ?, ?, ?)
            """, (str(guild_id), q_type, question, answer, difficulty))
    except sqlite3.OperationalError as e:
        logger.error(f"DB error while inserting {question}\n{e}", exc_info=True)
