import os
import asyncio
import discord
import psycopg2
from dotenv import load_dotenv

# Script for Populating the current active users (those who've submitted or answered a question) into the discord_users table

# --- Configuration ---
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
# ---------------------

def get_all_user_ids_from_db():
    """Fetches a unique list of all user IDs from the database."""
    all_user_ids = set()
    query = """
        SELECT user_id FROM leaderboard
        UNION
        SELECT user_id FROM trivia_questions;
    """
    try:
        with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                for row in results:
                    # Filter out any potential None values from the DB
                    if row[0]:
                        all_user_ids.add(row[0])
        print(f"Found {len(all_user_ids)} unique user IDs in the database.")
        return list(all_user_ids)
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return []

def upsert_user_in_db(user_id: int, display_name: str):
    """Inserts or updates a user's display name in the discord_users table."""
    try:
        with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO discord_users (user_id, display_name, last_updated)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        display_name = excluded.display_name,
                        last_updated = CURRENT_TIMESTAMP
                """, (user_id, display_name))
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB error while upserting user {user_id}: {e}")

async def main():
    if not DATABASE_URL or not DISCORD_TOKEN:
        print("Error: DATABASE_URL and DISCORD_TOKEN must be set in your .env file.")
        return

    # Step 1: Get all unique user IDs from your existing tables
    user_ids = get_all_user_ids_from_db()
    if not user_ids:
        print("No user IDs found to process.")
        return

    # Step 2: Log into Discord to use the API
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    async with client:
        await client.login(DISCORD_TOKEN)
        print("Logged into Discord. Fetching user profiles...")

        # Step 3: Loop through IDs, fetch profiles, and update DB
        for user_id in user_ids:
            try:
                user = await client.fetch_user(user_id)
                print(f"  -> Found: {user.global_name} ({user.id})")
                upsert_user_in_db(user.id, user.global_name)
            except discord.NotFound:
                print(f"  -> User with ID {user_id} not found. They may have deleted their account.")
            except Exception as e:
                print(f"An unexpected error occurred for user ID {user_id}: {e}")

    print("\nScript finished. The `discord_users` table has been populated.")

if __name__ == "__main__":
    asyncio.run(main())