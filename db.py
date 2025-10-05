import sqlite3
from datetime import datetime, timedelta
import logging

DB_NAME = "nakbot.db"
EXPIRATION_HOURS = 0
EXPIRATION_MINUTES = 1

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
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                answer TEXT NOT NULL,
                is_correct INTEGER DEFAULT 0 CHECK(is_correct IN (0,1)),
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(question_id, user_id),
                FOREIGN KEY (question_id) REFERENCES trivia_questions(id)
                    ON DELETE CASCADE
            )
        """)

        # Leaderboard table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                points INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        """)

        # Guild Configuration table | Admins can set which channel to have trivia questions sent in
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                mention_role_id INTEGER NULL
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

def set_trivia_role(guild_id: int, role_id: int | None):
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            # Only UPDATE here, A row should already exist from setting the channel.
            res = connection.execute("""
                UPDATE guild_config SET mention_role_id = ? WHERE guild_id = ?
            """, (role_id, guild_id))
            return res.rowcount > 0 # Returns True if a row was updated, False otherwise
    except sqlite3.OperationalError as e:
        logger.error(f"DB error while setting trivia role for guild {guild_id}:\n{e}", exc_info=True)
        return False


def get_all_guild_configs():
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            res = cursor.execute("SELECT guild_id, channel_id, mention_role_id FROM guild_config")
            return res.fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"DB error while fetching all guild configs:\n{e}", exc_info=True)
        return []

def get_channel_for_guild(guild_id: int):
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            res = cursor.execute("SELECT channel_id FROM guild_config WHERE guild_id = ?", (guild_id,))
            
            config = res.fetchone() # Fetch just one result
            if config:
                return config['channel_id']
            return None # Return None if no config is found

    except sqlite3.OperationalError as e:
        logger.error(f"DB error while fetching channel for guild {guild_id}:\n{e}", exc_info=True)
        return None

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
            question_dict = dict(question)
            question_dict['expires_at'] = expires_at
            return question_dict

    except sqlite3.OperationalError as e:
        logger.error(f"DB error while pulling random question:\n{e}", exc_info=True)
        return None

def get_active_question(guild_id: int):
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            now = datetime.utcnow()

            res = cursor.execute("""
                SELECT *
                FROM trivia_questions
                WHERE guild_id = ?
                  AND asked_at IS NOT NULL
                  AND closed = 0
                  AND expires_at > ?
                ORDER BY asked_at DESC
                LIMIT 1
            """, (guild_id, now))

            question = res.fetchone()

            if not question:
                logger.info(f"No active question found for guild: {guild_id}")
                return None
            
            return dict(question)
            
    except sqlite3.OperationalError as e:
        logger.error(f"DB error while pulling active question in guild {guild_id}")

def store_answer(question_id: int, guild_id: int, user_id: int, answer: str):
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("""
            INSERT INTO user_answers (question_id, guild_id, user_id, answer)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(question_id, user_id) DO UPDATE SET
                answer = excluded.answer,
                submitted_at = CURRENT_TIMESTAMP
            """, (question_id, guild_id, user_id, answer))
    except sqlite3.OperationalError as e:
        logger.error(f"DB error while inserting answer from user {user_id} for question {question_id}\n{e}", exc_info=True)

def mark_answer_correct(answer_id: int):
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.execute("UPDATE user_answers SET is_correct = 1 WHERE id = ?", (answer_id,))
    except sqlite3.OperationalError as e:
        logger.error(f"DB error marking answer {answer_id} as correct:\n{e}", exc_info=True)

def get_expired_questions():
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            now = datetime.utcnow()
            res = cursor.execute("""
                SELECT * FROM trivia_questions
                WHERE expires_at <= ? AND closed = 0
            """, (now,))
            return res.fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"DB error while fetching expired questions:\n{e}", exc_info=True)
        return []

def get_answers_for_question(question_id: int):
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            res = cursor.execute("""
                SELECT id, user_id, answer FROM user_answers WHERE question_id = ?
            """, (question_id,))
            return res.fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"DB error fetching answers for question {question_id}:\n{e}", exc_info=True)
        return []

def update_leaderboard(guild_id: int, user_id: int, points: int):
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.execute("""
                INSERT INTO leaderboard (guild_id, user_id, points) VALUES (?, ?, ?)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET points = points + excluded.points
            """, (guild_id, user_id, points))
    except sqlite3.OperationalError as e:
        logger.error(f"DB error updating leaderboard for user {user_id}:\n{e}", exc_info=True)

def close_question(question_id: int):
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.execute("UPDATE trivia_questions SET closed = 1 WHERE id = ?", (question_id,))
    except sqlite3.OperationalError as e:
        logger.error(f"DB error closing question {question_id}:\n{e}", exc_info=True)

def get_leaderboard(guild_id: int):
    try:
        with sqlite3.connect(DB_NAME, timeout=3) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            res = cursor.execute("""
                SELECT user_id, points FROM leaderboard
                WHERE guild_id = ?
                ORDER BY points DESC
                LIMIT 10
            """, (guild_id,))
            return res.fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"DB error fetching leaderboard for guild {guild_id}:\n{e}", exc_info=True)
        return []