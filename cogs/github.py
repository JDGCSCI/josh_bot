from discord.ext import commands
import discord
from disputils import BotEmbedPaginator

class GitHub(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def github(self, ctx):
        await ctx.send("https://github.com/JDGCSCI/josh_bot")

def setup(bot):
    bot.add_cog(GitHub(bot))