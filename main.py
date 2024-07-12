import datetime
import os
from random import randint
from dotenv import load_dotenv
from unidecode import unidecode
import discord
from PIL import Image
import index_spritesheet

BOT_CHANNEL_NAME = "bot-stuff"
MON_SPRITE_CHANNEL_NAME = "garticmon"
MON_SPRITE_FOLDER = "garticmon"
PROCESSED_SPRITE_FOLDER = "processed"
MAX_MESSAGES = 10

BATTLE_SPRITE_WIDTH = 256
BOX_ICON_WIDTH = 32

MON_SPRITE_SUCCESS_MESSAGES = [
    "Good job {user}, the sprites for {mon} look solid!",
    "Wow you got the sprites right for {mon} on your first try, {user}!",
    "Everyone give {user} some dancing Binglys for their perfect {mon} sprites!",
]
MON_SPRITE_ISSUE_MESSAGES = [
    "Hmm, not so sure about the sprites for {mon}, take a look at these issues {user}:",
    "Those {mon} pixels look pretty sharp but I have a few pointers for you, {user}:",
    "They can't all be winners, {user}, but {mon} can get back in the game after you fix this:",
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
        last_post_time = None #await get_last_post_time(bot_channel)
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
        print(message.content)
        # Download any images in the message
        mon_name = message.content.split(" ")[0] or "default"
        folder_name = unidecode(mon_name).lower().replace(" ", "-")
        base_path = os.path.join(MON_SPRITE_FOLDER, folder_name)
        os.makedirs(base_path, exist_ok=True)
        print("Saving images to", base_path)
        for attachment in message.attachments:
            if attachment.content_type.startswith("image/"):
                filename = os.path.join(base_path, attachment.filename)
                await attachment.save(filename)
                with Image.open(filename) as img:
                    if(img.width == BATTLE_SPRITE_WIDTH):
                        success = await test_battle_sprite(server, filename, mon_name, message)
                        if success:
                            await message.remove_reaction(rejected_emoji, client.user)
                        else:
                            await message.add_reaction(rejected_emoji)
                    elif(img.width == BOX_ICON_WIDTH):
                        await test_box_icon(server, filename, base_path)

async def test_battle_sprite(server: discord.Guild, filename: str, mon: str, original_message: discord.Message):
    print("Testing battle sprite", filename)
    folder_name = unidecode(mon).lower().replace(" ", "-")
    folder_name = os.path.join(PROCESSED_SPRITE_FOLDER, folder_name, "")
    os.makedirs(folder_name, exist_ok=True)
    result = index_spritesheet.process_image(filename, folder_name)
    user_tag = original_message.author.mention
    msg_content = ""
    msg_files = []
    if result["success"]:
        msg_content = MON_SPRITE_SUCCESS_MESSAGES[randint(0, len(MON_SPRITE_SUCCESS_MESSAGES)-1)].format(user=user_tag, mon=mon)
        return True
    else:
        msg_content = MON_SPRITE_ISSUE_MESSAGES[randint(0, len(MON_SPRITE_ISSUE_MESSAGES)-1)].format(user=user_tag, mon=mon)
        msg_content += "\n\n" + "\n\n".join(result["issues"])
        if result["diff_filename"] is not None:
            msg_files.append(discord.File(result["diff_filename"]))
    # print(msg_content)
    bot_channel = get_bot_channel(server)
    await bot_channel.send(msg_content, files=msg_files)
    return False
        

async def test_box_icon(server: discord.Guild, filename: str, folder_name: str):
    print("Testing box icon", filename)

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
