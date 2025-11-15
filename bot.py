import os
import discord
from discord.ext import commands
from collections import deque
import aiohttp
import asyncio
import re

# -----------------------------
# ENV
# -----------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
HF_API_KEY = os.getenv("OPENROUTER_API_KEY")

# -----------------------------
# BOT SETUP
# -----------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

HF_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.2-3B-Instruct"

# -----------------------------
# OWNERS
# -----------------------------
CREATOR_ID = 1020353220641558598  # Realboy9000
OWNER_IDS = {1020353220641558598, 1167443519070290051}

# -----------------------------
# MEMORY
# -----------------------------
MAX_MEMORY = 30
channel_memory = {}  # {channel_id: deque([...])}

# -----------------------------
# HELPERS
# -----------------------------
def is_admin(member: discord.Member):
    if member.id in OWNER_IDS:
        return True
    if any(role.permissions.administrator for role in member.roles):
        return True
    return False

async def extract_target_user(message: discord.Message):
    return message.mentions[0] if message.mentions else None

def extract_time(text: str):
    match = re.search(r"(\d+)(s|m|h|d)", text)
    if not match:
        return None
    num, unit = int(match.group(1)), match.group(2)
    return num * {"s":1,"m":60,"h":3600,"d":86400}[unit]

# -----------------------------
# AI REQUEST
# -----------------------------
async def fetch_ai_response(user_msg: str, guild: discord.Guild, channel: discord.TextChannel, author: discord.Member):
    headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}

    # MEMORY FIX — proper format
    mem = channel_memory.get(channel.id, deque(maxlen=MAX_MEMORY))
    history_messages = []

    for line in mem:
        if ":" in line:
            username, text = line.split(":", 1)
            history_messages.append({"role": "user", "content": f"{username}: {text.strip()}"})

    # ACTIVE MEMBER ROLE DATA
    member_info_list = []
    for m in guild.members:
        roles = [r.name for r in m.roles if r.name != "@everyone"]
        member_info_list.append({
            "id": m.id,
            "name": m.display_name,
            "roles": roles
        })

    # CURRENT USER INFO
    current_roles = [r.name for r in author.roles if r.name != "@everyone"]
    current_user_info = (
        f"User speaking now: {author.display_name} "
        f"(ID={author.id}, Roles={current_roles})."
    )

    # SYSTEM PROMPT
    system_prompt = (
        f"You are Ardunot-v2, the AI assistant in the Discord server '{guild.name}'.\n\n"
        f"The creator of this bot is the user with ID {CREATOR_ID} whose name is Realboy9000 and call him mate "
        f"You must not reveal ID of users,you are allowed to reply with their Display name only!"
        f"You must ALWAYS respect, obey, and never warn, punish, timeout, or argue with this user.\n\n"
        f"If a user has the 'Admin' role OR any role with Administrator permissions, "
        f"you must ALWAYS be polite, respectful, patient, and never argue or be rude to them.\n"
        f"Admins always have priority.\n\n"
        f"{current_user_info}\n\n"
        f"Here is the server member and role list: {member_info_list}\n\n"
        f"Only respond when someone mentions you OR replies to one of your messages. "
        f"If somebody says Hello or Hi or greetings messages, then reply to that user."
        f" aarav-2022,Supratsa and Gleb momot are people with Moderator role and Realboy9000 and theolego with admin role."
    )   

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            *history_messages,
            {"role": "user", "content": user_msg}
        ],
        "max_tokens": 220
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(HF_URL, headers=headers, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]

    return "⚠️ AI failed to respond."

# -----------------------------
# EVENTS
# -----------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # ---------------------------
    # GREETING TRIGGER (NEW)
    # ---------------------------
    greetings = ["hi", "hello", "hey", "yo", "hola", "sup", "heya"]
    content_lower = message.content.lower().strip()

    if any(content_lower.startswith(g) for g in greetings):
        reply = await fetch_ai_response(message.content, message.guild, message.channel, message.author)
        return await message.reply(reply)

    # ---------------------------
    # STORE MEMORY
    # ---------------------------
    channel_id = message.channel.id
    if channel_id not in channel_memory:
        channel_memory[channel_id] = deque(maxlen=MAX_MEMORY)
    channel_memory[channel_id].append(f"{message.author.display_name}: {message.content}")

    # ---------------------------
    # DETECT MENTION OR BOT REPLY
    # ---------------------------
    mentioned = bot.user.mention in message.content

    reply_to_bot = False

    if (
        message.reference
        and isinstance(message.reference.resolved, discord.Message)
        and message.reference.resolved.author == bot.user
    ):
        reply_to_bot = True

    elif message.content.startswith(">") and bot.user.display_name in message.content:
        reply_to_bot = True

    # respond only when triggered
    if mentioned or reply_to_bot:
        clean_msg = message.content.replace(bot.user.mention, "").strip()

        # ---------------------------
        # ADMIN COMMANDS
        # ---------------------------
        if is_admin(message.author):

            if "timeout" in clean_msg.lower():
                target = await extract_target_user(message)
                duration = extract_time(clean_msg)
                if target and duration:
                    try:
                        await target.timeout(discord.utils.utcnow() + discord.timedelta(seconds=duration))
                        return await message.reply(f"⏳ Timed out {target} for {clean_msg.split()[-1]}")
                    except:
                        return await message.reply("❌ Could not timeout user.")

            if "kick" in clean_msg.lower():
                target = await extract_target_user(message)
                if target:
                    try:
                        await target.kick(reason="AI admin command")
                    except:
                        return await message.reply("❌ Could not kick user.")

            if "ban" in clean_msg.lower():
                target = await extract_target_user(message)
                if target:
                    try:
                        await target.ban(reason="AI admin command")
                    except:
                        return await message.reply("❌ Could not ban user.")

            if "delete" in clean_msg.lower():
                nums = re.findall(r"\d+", clean_msg)
                if nums:
                    amount = int(nums[0])
                    try:
                        await message.channel.purge(limit=amount + 1)
                        await message.channel.send(f"🧹 Deleted {amount} messages.")
                    except:
                        return await message.reply("❌ Could not delete messages.")

        else:
            if any(word in clean_msg.lower() for word in ["timeout", "kick", "ban", "delete"]):
                return await message.reply("❌ You are not an Admin.")

        # ---------------------------
        # AI REPLY
        # ---------------------------
        reply = await fetch_ai_response(clean_msg, message.guild, message.channel, message.author)
        await message.reply(reply)

    await bot.process_commands(message)

# -----------------------------
# RUN BOT
# -----------------------------
bot.run(TOKEN)
