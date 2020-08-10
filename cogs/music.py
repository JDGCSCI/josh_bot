from discord.ext import commands
from disputils import BotEmbedPaginator
from collections import deque
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import discord
import urllib.parse
import requests
import re
import youtube_dl
import asyncio
import json

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.song_queue = deque()
        self.stopped = False
        self.currently_playing = None

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("headless")
        chrome_options.add_argument('log-level=3')
        self.driver = webdriver.Chrome(options = chrome_options)

    def get_audio_source(self, youtube_search):
        # Check to see if the search was a query or a youtube url
        url_pattern = re.compile(r'https://www.youtube.com/watch\?v=.{11}')

        # If the search is a youtube url, save the url; else get the url from the query
        if url_pattern.match(youtube_search):
            video_url = youtube_search
        else:
            query_string = urllib.parse.urlencode({"search_query": youtube_search})
            r = requests.get("http://www.youtube.com/results?" + query_string)
            search_result = re.search(r"/watch\?v=(.{11})", r.text)
            video_url = "http://www.youtube.com/watch?v=" + search_result.group(1)
        
        # Get the audio source from the youtube url
        ytdl_options = {}

        with youtube_dl.YoutubeDL(ytdl_options) as ydl:
            video_data = ydl.extract_info(video_url, download = False)

        # Get the best format for audio (I determined it to be 251)
        for format_type in video_data["formats"]:
            if format_type["format_id"] == "251":
                best_format_type = format_type
                break

        audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(best_format_type["url"], before_options = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"))

        return audio_source, video_data

    def find_lyrics(self, query):
        # Get the url for the lyrics page
        formatted_query = "%20".join(query.lower().split(" "))
        url = "https://genius.com/search?q=" + formatted_query
        self.driver.get(url)

        wait = WebDriverWait(self.driver, 5)
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div[ng-repeat="section in $ctrl.sections"]')))

        # Get correct section (section 0 = top result, section 1 = top songs)
        sections = self.driver.find_elements_by_css_selector('div[ng-repeat="section in $ctrl.sections"]')

        # Get the lyrics url and the thumbnail image url
        section_html = BeautifulSoup(sections[1].get_attribute("outerHTML"), "html.parser")
        lyrics_url = section_html.find("a", class_ = "mini_card")["href"]
        thumbnail_url = re.findall('background-image: url\("(.*?)"\);', section_html.find("div", class_ = "mini_card-thumbnail")["style"])[0]

        # Get the lyrics and title from the lyrics url
        lyrics_r = requests.get(lyrics_url)
        lyrics_html = BeautifulSoup(lyrics_r.text, "html.parser")
        lyrics = lyrics_html.find("div", class_ = "lyrics").get_text().strip()
        title = lyrics_html.find("title").get_text().replace(" Lyrics | Genius Lyrics", '').strip()

        # Split the lyrics into 2000 character chunks so it can be sent to discord
        current_chunk = ""
        chunks = []

        for line in lyrics.split('\n'):
            if len(line) + len(current_chunk) <= 2000:
                current_chunk += line + '\n'
            else:
                chunks.append(current_chunk.strip())
                current_chunk = line + '\n'

        chunks.append(current_chunk)

        return {"lyrics_chunks": chunks, "thumbnail_url": thumbnail_url, "title": title, "url": lyrics_url}

    def get_yt_song_and_artist(self, youtube_url):
        song_name = None
        artist_name = None

        r = requests.get(youtube_url)
        
        raw_matches = re.findall('(\{"metadataRowRenderer":.*?\})(?=,{"metadataRowRenderer")', r.text)

        json_objects = [json.loads(m) for m in raw_matches if '{"simpleText":"Song"}' in m or '{"simpleText":"Artist"}' in m] # [Song Data, Artist Data]

        if len(json_objects) == 2:
            song_contents = json_objects[0]["metadataRowRenderer"]["contents"][0]
            artist_contents = json_objects[1]["metadataRowRenderer"]["contents"][0]

            if "runs" in song_contents:
                song_name = song_contents["runs"][0]["text"]
            else:
                song_name = song_contents["simpleText"]
                
            if "runs" in artist_contents:
                artist_name = artist_contents["runs"][0]["text"]
            else:
                artist_name = artist_contents["simpleText"]

        return song_name, artist_name

    async def play_song(self, ctx, youtube_search):
        voice_client = ctx.voice_client

        # Get the audio source and place at the beginning of the queue
        audio_source, video_data = self.get_audio_source(youtube_search)
        self.song_queue.appendleft({"source": audio_source, "title": video_data["title"], "url": video_data["webpage_url"], "thumbnail_url": video_data["thumbnails"][3]["url"], "added_by": ctx.author})

        # If a song is currently playing, stop it so the new song can play
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
        else:
            self.play_next_song(ctx)
    
    def play_next_song(self, ctx):
        if not self.stopped:
            voice_client = ctx.voice_client

            if len(self.song_queue) >= 1:
                self.currently_playing = self.song_queue.popleft()

                voice_client.play(self.currently_playing["source"], after = lambda e: self.play_next_song(ctx))

                now_playing_embed = discord.Embed(
                    title = self.currently_playing["title"],
                    url = self.currently_playing["url"],
                    colour = discord.Colour.purple()
                )

                now_playing_embed.set_author(name = "Now Playing", icon_url = "https://p1.hiclipart.com/preview/989/591/761/iconlab-itunes-itunes-glow-music-icon.jpg")
                now_playing_embed.set_thumbnail(url = self.currently_playing["thumbnail_url"])
                now_playing_embed.set_footer(text = "Added By {}".format(self.currently_playing["added_by"]), icon_url = self.currently_playing["added_by"].avatar_url)

                asyncio.run_coroutine_threadsafe(ctx.send(embed = now_playing_embed), loop = self.bot.loop)

    @commands.command()
    async def join(self, ctx):
        voice = ctx.author.voice
        voice_client = ctx.voice_client

        if voice is None:
            await ctx.send("You are not in a voice channel!")
            return

        if voice_client is None:
            await voice.channel.connect()
        else:
            if voice.channel.id != voice_client.channel.id:
                await voice_client.disconnect()
                await voice.channel.connect()
            else:
                await ctx.send("I am already in your channel!")

    @commands.command()
    async def leave(self, ctx):
        voice_client = ctx.voice_client

        if voice_client is not None:
            await voice_client.disconnect()
        else:
            await ctx.send("I am not in a voice channel!")

    @commands.command()
    async def play(self, ctx, *args):
        voice = ctx.author.voice
        voice_client = ctx.voice_client

        # Join the channel if the bot is not in the requested channel
        if voice is None:
            await ctx.send("You are not in a voice channel!")
            return

        self.stopped = False

        if voice_client is None:
            await voice.channel.connect()
        else:
            if voice.channel.id != voice_client.channel.id:
                await voice_client.disconnect()
                await voice.channel.connect()

        # Update the voice client
        voice_client = ctx.voice_client

        # If arguments were provided, then just play the song immediately
        if len(args) > 0:
            youtube_search = " ".join(args)
            await self.play_song(ctx, youtube_search)
        else: # If no arguments were provided, kick off the songs in the queue if available
            if voice_client.is_playing() or voice_client.is_paused():
                await ctx.send("The queue is already playing!")
                return

            if len(self.song_queue) == 0:
                await ctx.send("The queue is empty!")
            else:
                self.play_next_song(ctx)

    @commands.command()
    async def stop(self, ctx):
        voice_client = ctx.voice_client

        if voice_client is not None:
            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()
                self.stopped = True
            else:
                await ctx.send("There is nothing playing!")
        else:
            await ctx.send("I am not in a voice channel!")

    @commands.command()
    async def pause(self, ctx):
        voice_client = ctx.voice_client

        if voice_client is not None:
            if not voice_client.is_paused():
                voice_client.pause()
            else:
                await ctx.send("There is nothing playing!")
        else:
            await ctx.send("I am not in a voice channel!")

    @commands.command()
    async def resume(self, ctx):
        voice_client = ctx.voice_client

        if voice_client is not None:
            if voice_client.is_paused():
                voice_client.resume()
            else:
                await ctx.send("I am already playing!")
        else:
            await ctx.send("I am not in a voice channel!")

    @commands.command()
    async def add(self, ctx, *, youtube_search):
        audio_source, video_data = self.get_audio_source(youtube_search)

        self.song_queue.append({"source": audio_source, "title": video_data["title"], "url": video_data["webpage_url"], "thumbnail_url": video_data["thumbnails"][3]["url"], "added_by": ctx.author})

        song_added_embed = discord.Embed(
            title = video_data["title"],
            url = video_data["webpage_url"],
            colour = discord.Colour.purple()
        )

        song_added_embed.set_author(name = "Added To Queue", icon_url = "https://cdn4.iconfinder.com/data/icons/meBaze-Freebies/512/add.png")
        song_added_embed.set_thumbnail(url = video_data["thumbnails"][3]["url"])
        song_added_embed.set_footer(text = "Added By {}".format(ctx.author), icon_url = ctx.author.avatar_url)

        await ctx.send(embed = song_added_embed)

    @commands.command()
    async def skip(self, ctx):
        voice_client = ctx.voice_client

        if voice_client is not None:
            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()
            else:
                await ctx.send("There is nothing playing!")
        else:
            await ctx.send("I am not in a voice channel!")

    @commands.command()
    async def queue(self, ctx):
        if len(self.song_queue) >= 1:
            queue_embeds = []

            for song in self.song_queue:
                queue_embed = discord.Embed(
                    title = song["title"],
                    url = song["url"],
                    colour = discord.Colour.purple()
                )

                queue_embed.set_author(name = "Queue", icon_url = "https://cdn0.iconfinder.com/data/icons/audio-visual-material-design-icons/512/queue-music-512.png")
                queue_embed.set_thumbnail(url = song["thumbnail_url"])
                queue_embed.set_footer(text = "Added By {}".format(song["added_by"]), icon_url = song["added_by"].avatar_url)

                queue_embeds.append(queue_embed)

            paginator = BotEmbedPaginator(ctx, queue_embeds)
            
            server_members_exclude_bots = []

            for member in ctx.guild.members:
                if not member.bot:
                    server_members_exclude_bots.append(member)
            
            await paginator.run(users = server_members_exclude_bots)
        else:
            await ctx.send("The queue is empty!")

    @commands.command()
    async def removelast(self, ctx):
        if len(self.song_queue) >= 1:
            removed_song = self.song_queue.pop()

            song_removed_embed = discord.Embed(
                title = removed_song["title"],
                url = removed_song["url"],
                colour = discord.Colour.purple()
            )

            song_removed_embed.set_author(name = "Removed From Queue", icon_url = "https://cdn1.iconfinder.com/data/icons/user-interface-44/48/Remove-512.png")
            song_removed_embed.set_thumbnail(url = removed_song["thumbnail_url"])
            song_removed_embed.set_footer(text = "Removed By {}".format(ctx.author), icon_url = ctx.author.avatar_url)

            await ctx.send(embed = song_removed_embed)
        else:
            await ctx.send("The queue is empty!")

    @commands.command()
    async def removefirst(self, ctx):
        if len(self.song_queue) >= 1:
            removed_song = self.song_queue.popleft()

            song_removed_embed = discord.Embed(
                title = removed_song["title"],
                url = removed_song["url"],
                colour = discord.Colour.purple()
            )

            song_removed_embed.set_author(name = "Removed From Queue", icon_url = "https://cdn1.iconfinder.com/data/icons/user-interface-44/48/Remove-512.png")
            song_removed_embed.set_thumbnail(url = removed_song["thumbnail_url"])
            song_removed_embed.set_footer(text = "Removed By {}".format(ctx.author), icon_url = ctx.author.avatar_url)

            await ctx.send(embed = song_removed_embed)
        else:
            await ctx.send("The queue is empty!")

    @commands.command()
    async def playing(self, ctx):
        voice_client = ctx.voice_client

        if voice_client is None:
            await ctx.send("I am not in a voice channel!")
            return
            
        if voice_client.is_playing or voice_client.is_paused():
            currently_playing_embed = discord.Embed(
                title = self.currently_playing["title"],
                url = self.currently_playing["url"],
                colour = discord.Colour.purple()
            )

            currently_playing_embed.set_author(name = "Currently Playing", icon_url = "https://p1.hiclipart.com/preview/989/591/761/iconlab-itunes-itunes-glow-music-icon.jpg")
            currently_playing_embed.set_thumbnail(url = self.currently_playing["thumbnail_url"])
            currently_playing_embed.set_footer(text = "Added By {}".format(self.currently_playing["added_by"]), icon_url = self.currently_playing["added_by"].avatar_url)

            await ctx.send(embed = currently_playing_embed)
        else:
            await ctx.send("There is nothing playing!")

    @commands.command()
    async def lyrics(self, ctx, *args):
        voice_client = ctx.voice_client
        lyric_query = ""

        if len(args) > 0: # If the user provides arguments, find lyrics based off of arguments
            lyric_query = " ".join(args)
        else: # If the user doesn't provide arguments, find lyrics based off currently playing song
            if voice_client is None:
                await ctx.send("I am not in a channel!")
                return

            if voice_client.is_playing() or voice_client.is_paused():
                song_name, artist_name = self.get_yt_song_and_artist(self.currently_playing["url"])

                if song_name is not None and artist_name is not None:
                    lyric_query = "{} {}".format(artist_name, song_name)
                else:
                    print("Youtube metadata not found, querying the title of the video instead.") # Debugging purposes

                    lyric_query = self.currently_playing["title"]
            else:
                await ctx.send("There is nothing playing!")
                return

        if lyric_query != "":
            print("Searching for: {}".format(lyric_query)) # Debugging purposes

            lyric_data = self.find_lyrics(lyric_query)
            
            if lyric_data["lyrics_chunks"]:
                song_lyrics_embeds = []

                for chunk in lyric_data["lyrics_chunks"]:
                    song_lyric_embed = discord.Embed(
                        title = lyric_data["title"],
                        url = lyric_data["url"],
                        description = chunk,
                        colour = discord.Colour.purple()
                    )

                    song_lyric_embed.set_thumbnail(url = lyric_data["thumbnail_url"])
                    song_lyric_embed.set_author(name = "Lyrics By Genius", icon_url = "https://images.genius.com/8ed669cadd956443e29c70361ec4f372.1000x1000x1.png")
                    song_lyric_embed.set_footer(text = "Requested By {}".format(ctx.author), icon_url = ctx.author.avatar_url)

                    song_lyrics_embeds.append(song_lyric_embed)

                paginator = BotEmbedPaginator(ctx, song_lyrics_embeds)
                
                server_members_exclude_bots = []

                for member in ctx.guild.members:
                    if not member.bot:
                        server_members_exclude_bots.append(member)
                
                await paginator.run(users = server_members_exclude_bots)
            else:
                await ctx.send("I could not find the lyrics.")

def setup(bot):
    bot.add_cog(Music(bot))