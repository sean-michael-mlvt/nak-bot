import discord
from discord.ui import View, button

# Confirm or cancel the submission of a trivia question
class ConfirmationView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=25)
        self.value = None  # Will be True (confirmed), False (cancelled), or None (timeout)

    @button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:

        self.value = True
        await interaction.response.edit_message(content="✅ Submission Confirmed! - Storing Question...", view=None, embed=None)
        self.stop()

    @button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:

        self.value = False
        await interaction.response.edit_message(content="❌ Submission Cancelled.", view=None, embed=None)
        self.stop()