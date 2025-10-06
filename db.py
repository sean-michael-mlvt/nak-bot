import os
import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import logging
import sys

DATABASE_URL = os.getenv('DATABASE_URL')

# Create a global connection pool
pool = SimpleConnectionPool(minconn=1, maxconn=10, dsn=DATABASE_URL, sslmode='require')

EXPIRATION_HOURS = 0
EXPIRATION_MINUTES = 5

# logger = logging.getLogger("discord")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

@contextmanager
def get_connection():
    # Get a connection from the pool and return it when done
    connection = pool.getconn()
    try:
        yield connection
    finally:
        pool.putconn(connection)

def init_db():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            # Trivia questions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trivia_questions (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NULL,
                    user_id BIGINT NULL,
                    question_type TEXT CHECK(question_type IN ('TF', 'QA')) NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    difficulty INTEGER CHECK(difficulty BETWEEN 1 AND 5),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    asked_at TIMESTAMPTZ,
                    expires_at TIMESTAMPTZ,
                    closed BOOLEAN DEFAULT FALSE NOT NULL
                )
            """)

            # User answers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_answers (
                    id SERIAL PRIMARY KEY,
                    question_id INTEGER NOT NULL,
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    answer TEXT NOT NULL,
                    is_correct BOOLEAN DEFAULT FALSE NOT NULL,
                    submitted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(question_id, user_id),
                    FOREIGN KEY (question_id) REFERENCES trivia_questions(id)
                        ON DELETE CASCADE
                )
            """)

            # Leaderboard table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leaderboard (
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    points INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)

            # Guild Configuration table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id BIGINT PRIMARY KEY,
                    channel_id BIGINT NOT NULL,
                    mention_role_id BIGINT NULL
                )
            """)
        connection.commit()
    logging.info("Database initialized successfully.")

def set_trivia_channel(guild_id: int, channel_id: int):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO guild_config (guild_id, channel_id) VALUES (%s, %s)
                    ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
                """, (guild_id, channel_id))
            connection.commit()
    except psycopg2.Error as e:
        logging.error(f"DB error while setting trivia channel for guild {guild_id}:\n{e}", exc_info=True)


def set_trivia_role(guild_id: int, role_id: int | None):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE guild_config SET mention_role_id = %s WHERE guild_id = %s
                """, (role_id, guild_id))
                connection.commit()
                return cursor.rowcount > 0
    except psycopg2.Error as e:
        logging.error(f"DB error while setting trivia role for guild {guild_id}:\n{e}", exc_info=True)
        return False


def get_all_guild_configs():
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT guild_id, channel_id, mention_role_id FROM guild_config")
                return cursor.fetchall()
    except psycopg2.Error as e:
        logging.error(f"DB error while fetching all guild configs:\n{e}", exc_info=True)
        return []


def get_channel_for_guild(guild_id: int):
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT channel_id FROM guild_config WHERE guild_id = %s", (guild_id,))
                config = cursor.fetchone()
                return config['channel_id'] if config else None
    except psycopg2.Error as e:
        logging.error(f"DB error while fetching channel for guild {guild_id}:\n{e}", exc_info=True)
        return None


def store_question(guild_id: int, user_id: int, q_type: str, question: str, answer: str, difficulty: int):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                INSERT INTO trivia_questions (guild_id, user_id, question_type, question, answer, difficulty)
                VALUES (%s, %s, %s, %s, %s, %s)
                """, (guild_id, user_id, q_type, question, answer, difficulty))
            connection.commit()
    except psycopg2.Error as e:
        logging.error(f"DB error while inserting {question}\n{e}", exc_info=True)


def pull_random_trivia(guild_id: int):
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                SELECT * FROM trivia_questions
                WHERE asked_at IS NULL AND guild_id = %s
                ORDER BY RANDOM() LIMIT 1
                """, (guild_id,))

                question = cursor.fetchone()
                if not question:
                    logging.info("No unasked trivia question found")
                    return None

                now = datetime.now(timezone.utc)
                expires_at = now + timedelta(hours=EXPIRATION_HOURS, minutes=EXPIRATION_MINUTES)

                cursor.execute("""
                    UPDATE trivia_questions
                    SET asked_at = %s, expires_at = %s
                    WHERE id = %s
                """, (now, expires_at, question["id"]))

                connection.commit()

                logging.info(f"Trivia question {question['id']} marked as asked (expires at {expires_at}).")
                question_dict = dict(question)
                question_dict['expires_at'] = expires_at
                return question_dict
    except psycopg2.Error as e:
        logging.error(f"DB error while pulling random question:\n{e}", exc_info=True)
        return None

def get_active_question(guild_id: int):
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                now = datetime.now(timezone.utc)
                cursor.execute("""
                    SELECT * FROM trivia_questions
                    WHERE guild_id = %s AND asked_at IS NOT NULL
                      AND closed = FALSE AND expires_at > %s
                    ORDER BY asked_at DESC LIMIT 1
                """, (guild_id, now))
                question = cursor.fetchone()
                return dict(question) if question else None
    except psycopg2.Error as e:
        logging.error(f"DB error while pulling active question in guild {guild_id}:\n{e}", exc_info=True)
        return None

def store_answer(question_id: int, guild_id: int, user_id: int, answer: str):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                INSERT INTO user_answers (question_id, guild_id, user_id, answer)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(question_id, user_id) DO UPDATE SET
                    answer = excluded.answer,
                    submitted_at = CURRENT_TIMESTAMP
                """, (question_id, guild_id, user_id, answer))
            connection.commit()
    except psycopg2.Error as e:
        logging.error(f"DB error inserting answer from user {user_id} for question {question_id}\n{e}", exc_info=True)

def mark_answer_correct(answer_id: int):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE user_answers SET is_correct = TRUE WHERE id = %s", (answer_id,))
            connection.commit()
    except psycopg2.Error as e:
        logging.error(f"DB error marking answer {answer_id} as correct:\n{e}", exc_info=True)


def get_expired_questions():
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                now = datetime.now(timezone.utc)
                cursor.execute("SELECT * FROM trivia_questions WHERE expires_at <= %s AND closed = FALSE", (now,))
                return cursor.fetchall()
    except psycopg2.Error as e:
        logging.error(f"DB error while fetching expired questions:\n{e}", exc_info=True)
        return []

def get_answers_for_question(question_id: int):
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, user_id, answer FROM user_answers WHERE question_id = %s", (question_id,))
                return cursor.fetchall()
    except psycopg2.Error as e:
        logging.error(f"DB error fetching answers for question {question_id}:\n{e}", exc_info=True)
        return []

def update_leaderboard(guild_id: int, user_id: int, points: int):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO leaderboard (guild_id, user_id, points) VALUES (%s, %s, %s)
                    ON CONFLICT(user_id, guild_id) DO UPDATE SET points = leaderboard.points + excluded.points
                """, (guild_id, user_id, points))
            connection.commit()
    except psycopg2.Error as e:
        logging.error(f"DB error updating leaderboard for user {user_id}:\n{e}", exc_info=True)

def close_question(question_id: int):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE trivia_questions SET closed = TRUE WHERE id = %s", (question_id,))
            connection.commit()
    except psycopg2.Error as e:
        logging.error(f"DB error closing question {question_id}:\n{e}", exc_info=True)

def get_leaderboard(guild_id: int):
    try:
        with get_connection() as connection:
            with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT user_id, points FROM leaderboard
                    WHERE guild_id = %s ORDER BY points DESC LIMIT 10
                """, (guild_id,))
                return cursor.fetchall()
    except psycopg2.Error as e:
        logging.error(f"DB error fetching leaderboard for guild {guild_id}:\n{e}", exc_info=True)
        return []