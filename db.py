import sqlite3
from datetime import datetime, timedelta
import logging

DB_NAME = "nakbot.db"
EXPIRATION_HOURS = 0
EXPIRATION_MINUTES = 5

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
                guild_id INTEGER NULL,
                user_id INTEGER NULL,
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
                guild_id INTEGER NULL,
                user_id INTEGER NOT NULL,
                answer TEXT NOT NULL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(question_id, user_id),
                FOREIGN KEY (question_id) REFERENCES trivia_questions(id)
                    ON DELETE CASCADE
            )
        """)

        # Leaderboard table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard (
                user_id INTEGER PRIMARY KEY,
                points INTEGER DEFAULT 0
            )
        """)

        # Guild Configuration table | Admins can set which channel to have trivia questions sent
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL
            )
        """)

def set_trivia_channel(guild_id: int, channel_id: int):
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.execute("""
                INSERT INTO guild_config (guild_id, channel_id) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
            """, (guild_id, channel_id))
    except sqlite3.OperationalError as e:
        logger.error(f"DB error while setting trivia channel for guild {guild_id}:\n{e}", exc_info=True)

def get_all_guild_configs():
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            res = cursor.execute("SELECT guild_id, channel_id FROM guild_config")
            return res.fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"DB error while fetching all guild configs:\n{e}", exc_info=True)
        return []

def store_question(guild_id: int, user_id: int, q_type: str, question: str, answer: str, difficulty: int):
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.execute("""
            INSERT INTO trivia_questions (guild_id, user_id, question_type, question, answer, difficulty)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, user_id, q_type, question, answer, difficulty))
    except sqlite3.OperationalError as e:
        logger.error(f"DB error while inserting {question}\n{e}", exc_info=True)

def pull_random_trivia(guild_id: int):
    try:
        
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()

            res = cursor.execute("""
            SELECT *
            FROM trivia_questions
            WHERE asked_at IS NULL AND guild_id = ?
            ORDER BY RANDOM()
            LIMIT 1
            """, (guild_id,))

            question = res.fetchone()

            if not question:
                logger.info("No unasked trivia question found")
                return None
            
            now = datetime.utcnow()
            expires_at = now + timedelta(hours=EXPIRATION_HOURS, minutes=EXPIRATION_MINUTES)

            cursor.execute("""
                UPDATE trivia_questions
                SET asked_at = ?, expires_at = ?
                WHERE id = ?
            """, (now, expires_at, question["id"]))

            logger.info(f"Trivia question {question['id']} marked as asked (expires at {expires_at}).")
            return dict(question)

    except sqlite3.OperationalError as e:
        logger.error(f"DB error while pulling random question:\n{e}", exc_info=True)
        return None
