from discord.ext import commands
import os
import json

with open("credentials.json") as json_file:
    CREDENTIALS = json.load(json_file)

bot = commands.Bot(command_prefix=".")

@bot.event
async def on_ready():
    print("[JoshBot] Bot is ready for action!")

if __name__ == "__main__":
    # Load the cogs
    print("[JoshBot] Loading cogs...")

    for filename in os.listdir("./cogs"):    
        if filename.endswith(".py"):
            extension = filename[:-3]  # Remove the .py from the filename

            try:
                bot.load_extension("cogs." + extension)

                print("[JoshBot] {} successfully loaded!".format(extension))
            except Exception as error:
                print("[JoshBot] {} cannot be loaded. [{}]".format(extension, error))

    bot.run(CREDENTIALS["DISCORD_BOT_TOKEN"])