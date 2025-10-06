import discord
from discord.ui import View, button
from db import store_question

# Confirm or cancel the submission of a trivia question
class ConfirmationView(discord.ui.View):

    def __init__(self, submission_data: dict):
        super().__init__(timeout=25)
        self.submission_data = submission_data
        self.value = None  # Will be True (confirmed), False (cancelled), or None (timeout)

    @button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        store_question(**self.submission_data)

        await interaction.response.edit_message(content="✅ Submission Confirmed!", view=None, embed=None)
        self.value = True
        self.stop()

    @button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:

        await interaction.response.edit_message(content="❌ Submission Cancelled.", view=None, embed=None)
        self.value = False
        self.stop()