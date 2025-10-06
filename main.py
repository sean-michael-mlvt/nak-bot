from __future__ import annotations
import discord
from discord import Embed, Colour
from dotenv import load_dotenv
import os
import sys
import logging
import asyncio
from views import ConfirmationView

# Imports for commands
from discord.ext import commands
from discord import app_commands
from discord.ext import tasks
from datetime import time, timezone, datetime

# Database Imports
from db import init_db, store_question, pull_random_trivia, set_trivia_channel, get_all_guild_configs, get_active_question, store_answer, mark_answer_correct
from db import get_expired_questions, get_answers_for_question, get_channel_for_guild, update_leaderboard, close_question, get_leaderboard, set_trivia_role

# Load Environment Variables
load_dotenv()
token = os.getenv('DISCORD_TOKEN')
# testServerID = os.getenv('DEV_SERVER_ID')       # Testing Only
# testChannelID = os.getenv('DEV_CHANNEL_ID')     # Testing Only
TRIVIA_INTERVAL = 8                              # Minutes between trivia questions
# guild = discord.Object(id=testServerID)

# Logging setup
# handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Enabling Necessary Intents - https://discordpy.readthedocs.io/en/stable/intents.html
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Client represents a client connection to Discord
class Client(commands.Bot):

    async def setup_hook(self):
        init_db()

        if not daily_trivia.is_running():
            daily_trivia.start()
        if not check_for_expired_trivia.is_running():
            check_for_expired_trivia.start()

    async def on_ready(self):
        logging.info(f"Logged on as {self.user}!")

        try:
            synced = await self.tree.sync()
            logging.info(f'Synced {len(synced)} commands globally')

        except Exception as e:
            logging.error(f'Error syncing commands: {e}')

client = Client(command_prefix="&", intents=intents)

# +-+-+-+-+-+-+-+-+-+-+-+-+-+ 
#  U S E R   C O M M A N D S  
# +-+-+-+-+-+-+-+-+-+-+-+-+-+ 

# Add True or False
@client.tree.command(name="addtf", description="Add a True or False trivia question to the database")
@app_commands.describe(
    statement="A trivia statement about yourself",
    answer="Whether or not the trivia statement is true or false",
)
async def addTF(interaction: discord.Interaction, statement: str, answer: bool):

    # Package the data for the view
    submission_data = {
        'guild_id': interaction.guild_id,
        'user_id': interaction.user.id,
        'q_type': "TF",
        'question': statement.strip(),
        'answer': str(answer),
        'difficulty': 2
    }

    embed = Embed(title="Please Confirm Submission", description=f"**Statement:** {statement}\n**Answer:** {answer}")
    view = ConfirmationView(submission_data=submission_data)

    await interaction.response.send_message(
        # f"**Please Confirm:** \n**Question:** {question}\n**Answer:** {answer}",
        embed=embed,
        ephemeral=True,
        view=view
    )

# Add Question & Answer
@client.tree.command(name="addqa", description="Add a Question and Answer trivia question to the database")
@app_commands.choices(
    difficulty=[
        app_commands.Choice(name="1 (Very Easy)", value=1),
        app_commands.Choice(name="2 (Easy)", value=2),
        app_commands.Choice(name="3 (Medium)", value=3),
        app_commands.Choice(name="4 (Hard)", value=4),
        app_commands.Choice(name="5 (Very Hard)", value=5),
    ]
)
@app_commands.describe(
    question="A trivia question about yourself",
    answer="The correct answer for the trivia question",
    difficulty="Difficulty level (1-5) with 5 being the hardest"
)
async def addQA(interaction: discord.Interaction, question: str, answer: str, difficulty: app_commands.Choice[int]):

    # Package the data for confirmation
    submission_data = {
        'guild_id': interaction.guild_id,
        'user_id': interaction.user.id,
        'q_type': "QA",
        'question': question.strip(),
        'answer': answer.strip(),
        'difficulty': difficulty.value
    }

    embed = Embed(title="Please Confirm Submission", description=f"**Question:** {question}\n**Answer:** {answer}\n**Difficulty:** {difficulty.value}/5")
    view = ConfirmationView(submission_data=submission_data)

    await interaction.response.send_message(
        # f"**Please Confirm:** \n**Question:** {question}\n**Answer:** {answer}\n**Difficulty: **{difficulty.value}/5",
        embed=embed,
        ephemeral=True,
        view=view
    )

@client.tree.command(name="settriviachannel", description="Sets this channel as the one for daily trivia questions.")
@app_commands.checks.has_permissions(administrator=True) # Only admins can run this
async def set_trivia_channel_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    guild_id = interaction.guild_id
    channel_id = interaction.channel_id
    
    set_trivia_channel(guild_id, channel_id)

    await interaction.edit_original_response(
        content=f"Trivia channel has been set to this channel (`{interaction.channel.name}`)."
    )

@set_trivia_channel_command.error
async def on_set_channel_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.edit_original_response(content="Error: You must be an administrator to use this command.")
    else:
        raise error

@client.tree.command(name="settriviarole", description="Sets a role to be mentioned when a new trivia question is announced.")
@app_commands.describe(role="The role to mention. Leave blank to clear the current setting.")
@app_commands.checks.has_permissions(administrator=True)
async def set_trivia_role_command(interaction: discord.Interaction, role: discord.Role = None):
    await interaction.response.defer(ephemeral=True)

    guild_id = interaction.guild_id
    role_id = role.id if role else None

    success = set_trivia_role(guild_id, role_id)
    
    if success:
        if role:
            await interaction.edit_original_response(
                content=f"The trivia mention role has been set to `{role.name}`."
            )
        else:
            await interaction.edit_original_response(
                content="The trivia mention role has been cleared."
            )
    else:
        await interaction.edit_original_response(
            content="Error: Could not set trivia role. Please set a trivia channel first using `/settriviachannel`."
        )

@set_trivia_role_command.error
async def on_set_role_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.edit_original_response(
            content="Error: You must be an administrator to use this command."
        )
    else:
        raise error

@client.tree.command(name="answer", description="Submit an answer for the most recent trivia question asked.")
@app_commands.describe(
    answer="QA Questions: Your answer to the most recent question. \n TF Questions: \"True\" or \"False\". "
)
async def submit_answer(interaction: discord.Interaction, answer: str):
    await interaction.response.defer(ephemeral=True)

    guild_id = interaction.guild_id
    user_id = interaction.user.id

    active_question = get_active_question(guild_id=guild_id)
    
    if not active_question:
        await interaction.edit_original_response(
            content="There is no active trivia question to answer right now."
        )
        return

    question_author_id = active_question['user_id']
    if user_id == question_author_id:
        await interaction.edit_original_response(
            content="You can't answer your own trivia question!"
        )
        return

    question_id = active_question['id']
    store_answer(question_id, guild_id, user_id, answer.strip())

    await interaction.edit_original_response(
        content="Your answer has been recorded! You can update it by using the /answer command again."
    )

@client.tree.command(name="leaderboard", description="Displays the top 10 trivia players for this server.")
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    logging.info("Pulling Leaderboard")
    guild_id = interaction.guild_id
    board = get_leaderboard(guild_id=guild_id)
    
    if not board:
        await interaction.edit_original_response(content="The leaderboard is currently empty.")
        return
        
    rankings = []
    
    for i, entry in enumerate(board):
        user_id = entry['user_id']
        points = entry['points']
        rank_icon = f"**{i + 1}.**"
        
        rankings.append(f"{rank_icon} <@{user_id}> `{points}` points")
        
    embed = discord.Embed(
        title=f"Top 10 Nak-Knowers in {interaction.guild.name}",
        description="\n".join(rankings),
        color=discord.Color.gold()
    )
    
    await interaction.edit_original_response(embed=embed)

# +-+-+-+-+-+-+-+-+-+
#  B O T   T A S K S  
# +-+-+-+-+-+-+-+-+-+ 

@tasks.loop(minutes=TRIVIA_INTERVAL)
async def daily_trivia():

    now_utc = datetime.now(timezone.utc)

    # Check if the current hour is between 2:00 and 5:00 EDT
    if 5 <= now_utc.hour <= 9:
        logging.info("Skipping trivia task during quiet hours (2:00-5:00 UTC).")
        return

    # Get all guilds that have a trivia channel configured
    guild_configs = get_all_guild_configs()

    for config in guild_configs:
        guild_id = config['guild_id']
        channel_id = config['channel_id']
        mention_role_id = config['mention_role_id']

        # Pull random trivia question from database
        question = pull_random_trivia(guild_id=guild_id)

        # If no question is found for this guild, skip to the next one
        if not question:
            logging.info(f"No questions available for guild {guild_id}. Skipping.")
            continue

        # Get username from user_id of the user who submitted the question
        authorName = "Unknown Author"
        authorIcon = None
        try:
            user = await client.fetch_user(question["user_id"])
            authorName = user.display_name
            authorIcon = user.avatar.url
        except discord.NotFound:
            logging.debug(f"User with id {question["user_id"]} not found.")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")

        # Build Embed for announcing question
        mention_string = ""
        if mention_role_id:
            mention_string = f"<@&{mention_role_id}>"
        trivia_heading = f"### New Trivia Question! {mention_string}"
        title_ender = "?" if (question["question_type"]=="QA" and not question["question"].endswith("?")) else ""
        stars = "⭐ " * question["difficulty"] + "➖ " * (5 - question["difficulty"])
        embed = discord.Embed(
            title=f"{question["question"]}" + title_ender,
            # description=f"**Difficulty:** {stars}\n**Question Type:** {question["question_type"]}\nUse /answer to submit your answer!",
            # description="Use /answer to submit your answer!",
            color=discord.Color.blue()
        )
        embed.set_author(name=f"{authorName}", icon_url=authorIcon)
        embed.add_field(name="Difficulty", value=f"{stars}", inline=False)
        embed.add_field(name="Question Type", value=f"{question["question_type"]}", inline=False)
        expire_ts = int(question['expires_at'].replace(tzinfo=timezone.utc).timestamp())
        embed.add_field(name="Expires", value=f"<t:{expire_ts}:R>")
        embed.set_footer(text="Use /answer to submit your answer!")

        # Send message to the configured channel for the guild
        channel = client.get_channel(channel_id)
        if channel:
            await channel.send(content=trivia_heading, embed=embed)
        else: 
            logging.error(f"Could not find configured channel with ID {channel_id} for guild {guild_id}")
    
@daily_trivia.before_loop
async def before_daily_trivia():
    await client.wait_until_ready()
    await asyncio.sleep(60)

@tasks.loop(minutes=2)
async def check_for_expired_trivia():
    expired_questions = get_expired_questions()
    
    for question in expired_questions:

        # Mark the question as processed
        close_question(question['id'])

        logging.info(f"Processing question from user {question["user_id"]}:\n{question["question"]}")
        submissions = get_answers_for_question(question['id'])
        correct_answer = question['answer'].lower().strip()
        points_to_award = 10 * question['difficulty']
        
        winners = []
        for sub in submissions:
            user_answer = sub['answer'].lower().strip()
            is_correct = False
            
            if question['question_type'] == 'TF' and user_answer == correct_answer:
                is_correct = True
            elif question['question_type'] == 'QA' and (correct_answer in user_answer or user_answer in correct_answer):
                is_correct = True
            
            if is_correct:
                mark_answer_correct(sub['id'])
                update_leaderboard(question['guild_id'], sub['user_id'], points_to_award)
                winners.append(f"<@{sub['user_id']}>")

        # Announce the results in the set trivia channel
        channel_id = get_channel_for_guild(question['guild_id'])
        
        if channel_id:
            channel = client.get_channel(channel_id)
            if channel:
                results_embed = discord.Embed(color=discord.Color.gold())
                results_embed.add_field(name="Question", value=question['question'], inline=False)
                results_embed.add_field(name="Correct Answer", value=question['answer'], inline=False)
                
                # Get username from user_id of the user who submitted the question
                authorName = "Unknown Author"
                authorIcon = None
                try:
                    user = await client.fetch_user(question["user_id"])
                    authorName = user.display_name
                    authorIcon = user.avatar.url
                except discord.NotFound:
                    logging.error(f"User with id {question["user_id"]} not found.")
                except Exception as e:
                    logging.error(f"An unexpected error occurred: {e}")
                results_embed.set_author(name=f"{authorName}", icon_url=authorIcon)

                resultsHeading = "### New Trivia Results!"

                if winners:
                    winner_str = ", ".join(winners)
                    results_embed.add_field(name=f"🏆 Winners (+{points_to_award} points)", value=winner_str, inline=False)
                else:
                    results_embed.add_field(name="🏆 Winners", value="No one answered correctly.", inline=False)
                
                await channel.send(content=resultsHeading, embed=results_embed)


@check_for_expired_trivia.before_loop
async def before_check_expired():
    await client.wait_until_ready()
    await asyncio.sleep(90)

# +-+-+-+-+-+-+-+-+-+
#  E X E C U T I O N
# +-+-+-+-+-+-+-+-+-+

# Running Bot with an instance of Client and logging debug messages to discord.log
# client.run(token, log_handler=handler, log_level=logging.DEBUG)

# Running Bot with an instance of Client
client.run(token)