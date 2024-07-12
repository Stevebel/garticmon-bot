import datetime
import os
from random import randint
from dotenv import load_dotenv
import pytz
from index_icon import test_icon
from unidecode import unidecode
import discord
from PIL import Image
import index_spritesheet

DEBUG_MODE = False

BOT_CHANNEL_NAME = "bot-stuff"
MON_SPRITE_CHANNEL_NAME = "garticmon"
MON_SPRITE_FOLDER = "garticmon"
PROCESSED_SPRITE_FOLDER = "processed"
MAX_MESSAGES = 1000

BATTLE_SPRITE_WIDTH = 256
BOX_ICON_WIDTH = 32

MON_SPRITE_SUCCESS_MESSAGES = [
    "Good job {user}, the sprites for {mon} look solid!",
    "Wow you got the sprites right for {mon} on your first try, {user}!",
    "Everyone give {user} some dancing Binglys for their perfect {mon} sprites!",
    "You're on fire, {user}! Those {mon} sprites are flawless!",
    "Boom! {user} did it again, the sprites for {mon} are perfect!",
    "The sprites for {mon} are ready to be dropped into the game, {user}!",
    "{mon}'s sprites are good to go, bet you weren't expecting that {user}!",
    "Hmm, not sure about the sprites for {mon}... they might be my favorite yet, {user}! Keep it up!",
    "Blessu has blessed you with those flawless {mon} sprites, {user}!",
    "...\n\n...\n\n(Hector approves of your sprites for {mon}, {user})",
]
MON_SPRITE_ISSUE_MESSAGES = [
    "Hmm, not so sure about the sprites for {mon}, take a look at these issues {user}:",
    "Those {mon} pixels look pretty sharp but I have a few pointers for you, {user}:",
    "They can't all be winners, {user}, but {mon} can get back in the game after you fix this:",
    "You might have seen this coming, {user}, I found some issues with the sprites for {mon}:",
    "Oops, think you misplaced a pixel, {user}. Here's what I found with the sprites for {mon}:",
    "Hey {user}, how's your day going? Great. Anyway, unrelated, I found some issues with the sprites for {mon}:",
    "Great work {user}! The sprites for {mon} look perfect... except for these issues:",
    "Wow, so many pixels in the sprites for {mon}, no wonder you missed these issues {user}:",
    "You know the problem with the GBA? It's dumb, {user}, it can't handle the sprites for {mon} unless you fix these issues:",
    "{user} your horoscope for the {mon} sprites is in, here's what it says:",
    "Life would be boring without any challenges, {user}. On that note, I found some issues with the sprites for {mon}:",
]

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print("We have logged in as {0}".format(client.user))
    servers = client.guilds
    for server in servers:
        mon_sprite_channel = get_mon_sprite_channel(server)
        if mon_sprite_channel is None:
            continue
        bot_channel = get_bot_channel(server)
        if bot_channel is None:
            continue
        utc = pytz.timezone('UTC')
        last_post_time = utc.localize(datetime.datetime.now()) - datetime.timedelta(days=100) #await get_last_post_time(bot_channel)
        print(last_post_time)
        await check_mon_sprites(server, mon_sprite_channel, last_post_time)

def get_bot_channel(server):
    for c in server.channels:
        if c.name == BOT_CHANNEL_NAME:
            return c
    return None

def get_mon_sprite_channel(server):
    for c in server.channels:
        if c.name == MON_SPRITE_CHANNEL_NAME:
            return c
    return None

async def get_last_post_time(bot_channel: discord.TextChannel) -> datetime:
    last_post_time = None
    # Find the last post made by the bot
    def authored_by_bot(m: discord.Message):
        return m.author == client.user
    last_post = await anext((m async for m in bot_channel.history() if authored_by_bot(m)), None)
    if last_post:
        last_post_time = last_post.created_at
    return last_post_time

async def check_mon_sprites(server: discord.Guild, channel: discord.TextChannel, start_time: datetime = None):
    # print(server.emojis)
    # Find the emoji with the name "zapindead"
    rejected_emoji = next(e for e in server.emojis if e.name == "zapindead")
    # Fetch the most recent messages after the start time
    async for message in channel.history(limit=MAX_MESSAGES):
        if start_time is not None and (message.edited_at or message.created_at) <= start_time:
            continue
        if message.author.bot:
            continue
        # Download any images in the message
        mon_name = message.content.split(" ")[0] or "default"
        folder_name = unidecode(mon_name).lower().replace(" ", "-")
        base_path = os.path.join(MON_SPRITE_FOLDER, folder_name)
        os.makedirs(base_path, exist_ok=True)
        for attachment in message.attachments:
            filenames = []
            if attachment.content_type.startswith("image/"):
                filename = os.path.join(base_path, attachment.filename)
                await attachment.save(filename)
                filenames.append(filename)
            battle_filename = None
            icon_filename = None
            for filename in filenames:
                with Image.open(filename) as img:
                    if(img.width == BATTLE_SPRITE_WIDTH):
                        battle_filename = filename
                    elif(img.width == BOX_ICON_WIDTH):
                        icon_filename = filename
            if battle_filename is not None:
                success = await test_battle_sprite(server, battle_filename, icon_filename, mon_name, message)
                if success:
                    await message.remove_reaction(rejected_emoji, client.user)
                else:
                    await message.add_reaction(rejected_emoji)

async def test_battle_sprite(server: discord.Guild, filename: str, icon_filename: str, mon: str, original_message: discord.Message):
    print("Testing battle sprite", filename)
    folder_name = unidecode(mon).lower().replace(" ", "-")
    folder_name = os.path.join(PROCESSED_SPRITE_FOLDER, folder_name, "")
    os.makedirs(folder_name, exist_ok=True)
    result = index_spritesheet.process_image(filename, folder_name)
    user_tag = original_message.author.mention
    msg_content = ""
    msg_files = []
    bot_channel = get_bot_channel(server)
    if result["success"]:
        issues = icon_filename and test_icon(icon_filename, result["front_file_name"]) or []
        if len(issues) > 0:
            await send_sprite_issue_message(bot_channel, issues, mon, user_tag)
            return False
        msg_content = MON_SPRITE_SUCCESS_MESSAGES[randint(0, len(MON_SPRITE_SUCCESS_MESSAGES)-1)].format(user=user_tag, mon=mon)
        # await send_message(bot_channel, msg_content)
        return True
    
    if result["diff_filename"]:
        msg_files.append(discord.File(result["diff_filename"]))
    await send_sprite_issue_message(bot_channel, result["issues"], mon, user_tag, files=msg_files)
    return False

async def send_sprite_issue_message(channel: discord.TextChannel, issues: list[str], mon: str, user_tag: str, files: list[discord.File] = None):
    msg_content = MON_SPRITE_ISSUE_MESSAGES[randint(0, len(MON_SPRITE_ISSUE_MESSAGES)-1)].format(user=user_tag, mon=mon)
    msg_content += "\n\n> " + "\n\n> ".join(issues)
    await send_message(channel, msg_content, files)

        
async def send_message(channel: discord.TextChannel, content: str, files: list[discord.File] = None):
    if DEBUG_MODE:
        print("[DEBUG] Not sending message:", content)
    else:
        await channel.send(content, files=files)

try:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN") or ""
    if token == "":
        raise Exception("Please add DISCORD_TOKEN to your environment variables")
    client.run(token)
except discord.HTTPException as e:
    if e.status == 429:
        print("The Discord servers denied the connection for making too many requests")
        print(
            "Get help from https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests"
        )
    else:
        raise e
