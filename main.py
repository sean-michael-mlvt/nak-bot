from __future__ import annotations
import discord
from discord import Embed, Colour
from dotenv import load_dotenv
import os
import logging

#Development imports
import asyncio

# Imports for slash commands
from discord.ext import commands
from discord import app_commands

# Load Environment Variables
load_dotenv()
token = os.getenv('DISCORD_TOKEN')
testServerID = os.getenv('DEV_SERVER_ID')
guild = discord.Object(id=testServerID)

# Logging setup
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

# Enabling Necessary Intents - https://discordpy.readthedocs.io/en/stable/intents.html
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Client represents a client connection to Discord
class Client(commands.Bot):

    async def on_ready(self):
        print(f"Logged on as {self.user}!")

        try:
            synced = await self.tree.sync(guild=guild)
            print(f'Synced {len(synced)} commands to guild {guild.id}')

        except Exception as e:
            print(f'Error syncing commands: {e}')

client = Client(command_prefix="&", intents=intents)

# +-+-+-+-+-+
#  V I E W S
# +-+-+-+-+-+

# Confirm or cancel the submission of a trivia question
class ConfirmationView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=25)
        self.value = None  # Will be True (confirmed), False (cancelled), or None (timeout)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button[ConfirmationView]) -> None:

        self.value = True
        await interaction.response.edit_message(content="✅ Submission Confirmed! - Storing Question...", view=None, embed=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button[ConfirmationView]) -> None:

        self.value = False
        await interaction.response.edit_message(content="❌ Submission Cancelled.", view=None, embed=None)
        self.stop()



# +-+-+-+-+-+-+-+-+
#  C O M M A N D S
# +-+-+-+-+-+-+-+-+ 

# Add True or False
@client.tree.command(name="addtf", description="Add a True or False trivia question to the database", guild=guild)
@app_commands.describe(
    question="A trivia question about yourself",
    answer="The correct (True or False) answer for the trivia question",
)
async def addTF(interaction: discord.Interaction, question: str, answer: bool):

    embed = Embed(title="Please Confirm Submission", description=f"**Question:** {question}\n**Answer:** {answer}")
    view = ConfirmationView()

    await interaction.response.send_message(
        # f"**Please Confirm:** \n**Question:** {question}\n**Answer:** {answer}",
        embed=embed,
        ephemeral=True,
        view=view
    )
    # Wait for a button click or timeout
    await view.wait()

    # Handle Confirmation, Cancelation, or Timeout
    if view.value is None:
        await interaction.edit_original_response(content="Submission timed out, no confirmation.", view=None, embed=None)
    elif view.value:
        # TODO: Save True/False Question to SQLite Database
        await asyncio.sleep(3)
        await interaction.edit_original_response(content="✅ Question Submitted Successfully!", view=None, embed=None)
        pass



# Add Question & Answer
@client.tree.command(name="addqa", description="Add a Question and Answer trivia question to the database", guild=guild)
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

    embed = Embed(title="Please Confirm Submission", description=f"**Question:** {question}\n**Answer:** {answer}\n**Difficulty:** {difficulty.value}/5")
    view = ConfirmationView()

    await interaction.response.send_message(
        # f"**Please Confirm:** \n**Question:** {question}\n**Answer:** {answer}\n**Difficulty: **{difficulty.value}/5",
        embed=embed,
        ephemeral=True,
        view=view
    )
    # Wait for a button click or timeout
    await view.wait()

    # Handle Confirmation, Cancelation, or Timeout
    if view.value is None:
        await interaction.edit_original_response(content="Submission timed out, no confirmation.", view=None, embed=None)
    elif view.value:
        # TODO: Save True/False Question to SQLite Database
        await asyncio.sleep(3)
        await interaction.edit_original_response(content=" ✅ Question Submitted Successfully!", view=None, embed=None)
        pass



# +-+-+-+-+-+-+-+-+-+
#  E X E C U T I O N
# +-+-+-+-+-+-+-+-+-+

# Running Bot with an instance of Client and logging debug messages to discord.log
client.run(token, log_handler=handler, log_level=logging.DEBUG)
