import sqlite3

DB_NAME = "nakbot.db"

def init_db():
    with sqlite3.connect(DB_NAME) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS trivia_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                question_type TEXT CHECK(question_type IN ('TF', 'QA')) NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                difficulty INTEGER CHECK(difficulty BETWEEN 1 AND 5),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                asked_at TIMESTAMP
            )
        """)


def store_question(guild_id: int, q_type: str, question: str, answer: str, difficulty: int):
    with sqlite3.connect(DB_NAME) as connection:
        connection.execute("""
        INSERT INTO trivia_questions (guild_id, question_type, question, answer, difficulty)
        VALUES (?, ?, ?, ?, ?)
        """, (str(guild_id), q_type, question, answer, difficulty))
