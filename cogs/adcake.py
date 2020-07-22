from discord.ext import commands
import requests
import random
import discord
import os

class ADCake(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def adcake(self, ctx):
        header = {"Client-ID": os.environ["TWITCH_API_CLIENT_ID"], "Authorization": "Bearer " + os.environ["TWITCH_API_APP_TOKEN"]}
        r = requests.get("https://api.twitch.tv/helix/clips?broadcaster_id=83294945&first=100", headers = header)
        data = r.json()

        clips = data["data"]
        random_clip = random.choice(clips)

        await ctx.send(random_clip["url"])

def setup(bot):
    bot.add_cog(ADCake(bot))