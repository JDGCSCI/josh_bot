from discord.ext import commands
from googletrans import Translator
import googletrans
import discord

class Translate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.translator = Translator()

    @commands.command()
    async def translate(self, ctx, language_config, *args):
        language_config = language_config.split("->")
        source_language = language_config[0]
        destination_language = language_config[1]
        source_sentence = " ".join(args)
        
        translation = self.translator.translate(text = source_sentence, src = source_language, dest = destination_language)

        translate_embed = discord.Embed(
            title = translation.text,
            description = source_sentence,
            colour = discord.Colour.purple()
        )

        translate_embed.set_footer(text = "Powered by Google Translate")
        translate_embed.set_thumbnail(url = "https://cdn3.iconfinder.com/data/icons/google-suits-1/32/18_google_translate_text_language_translation-512.png")
        translate_embed.set_author(name = ctx.author, icon_url = ctx.author.avatar_url)

        await ctx.send(embed = translate_embed)

    @commands.command()
    async def languages(self, ctx):
        languages_embed = discord.Embed(
            colour = discord.Colour.purple()
        )

        languages_embed.set_footer(text = "Powered by Google Translate")
        languages_embed.set_author(name = "Languages", icon_url = "https://tl.vhv.rs/dpng/s/444-4449499_earth-globe-transparent-background-transparent-background-world-globe.png")

        languages_embed.add_field(name = "Language", value = '\n'.join(googletrans.LANGUAGES.values()), inline = True)
        languages_embed.add_field(name = '\u200b', value = '\u200b', inline = True)
        languages_embed.add_field(name = "Code", value = '\n'.join(googletrans.LANGUAGES.keys()), inline = True)
        
        await ctx.send(embed = languages_embed)

def setup(bot):
    bot.add_cog(Translate(bot))