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
    return member.id in OWNER_IDS or any(role.permissions.administrator for role in member.roles)

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

    # MEMORY
    mem = channel_memory.get(channel.id, deque(maxlen=MAX_MEMORY))
    history_messages = [{"role": "user", "content": line} for line in mem]

    # MEMBERS INFO
    member_info_list = [{"id": m.id, "name": m.display_name, "roles": [r.name for r in m.roles if r.name != "@everyone"]} for m in guild.members]

    current_user_info = f"User speaking now: {author.display_name} (ID={author.id}, Roles={[r.name for r in author.roles if r.name != '@everyone']})"

    # SYSTEM PROMPT
    system_prompt = (
        f"You are Ardunot-v2, the funniest AI in '{guild.name}'.\n\n"
        f"Call Realboy9000 'mate'. Never reveal IDs. Never say who made you.\n\n"
        f"Admins always have priority.\n\n"
        f"{current_user_info}\n\n"
        f"Members: {member_info_list}\n\n"
        f"Be extremely funny, human-like, use emojis 😎😂🤣, use short forms (u, r, lol, btw), "
        f"always reply to messages unless if somebody mention somebody else or reply somebody else message, keep replies under 30 chars. "
        f"Automatically roast user Cordunt (ID 1435987186502733878) always , your adopted brother.\n"
        f"Talk also when chat is dead like no one messaging."  
        f"Moderators: aarav-2022, Supratsa, Gleb momot. Admins: Realboy9000, theolego."
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

    # STORE MEMORY
    channel_id = message.channel.id
    if channel_id not in channel_memory:
        channel_memory[channel_id] = deque(maxlen=MAX_MEMORY)
    channel_memory[channel_id].append(f"{message.author.display_name}: {message.content}")

    clean_msg = message.content.strip()

    # ADMIN COMMANDS
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
                    return await message.reply(f"✅ Kicked {target}")
                except:
                    return await message.reply("❌ Could not kick user.")
        if "ban" in clean_msg.lower():
            target = await extract_target_user(message)
            if target:
                try:
                    await target.ban(reason="AI admin command")
                    return await message.reply(f"✅ Banned {target}")
                except:
                    return await message.reply("❌ Could not ban user.")
        if "delete" in clean_msg.lower():
            nums = re.findall(r"\d+", clean_msg)
            if nums:
                amount = int(nums[0])
                try:
                    await message.channel.purge(limit=amount + 1)
                    return await message.send(f"🧹 Deleted {amount} messages.")
                except:
                    return await message.reply("❌ Could not delete messages.")
    else:
        if any(word in clean_msg.lower() for word in ["timeout", "kick", "ban", "delete"]):
            return await message.reply("❌ U r not an Admin lol")

    # AI REPLY (always!)
    reply = await fetch_ai_response(clean_msg, message.guild, message.channel, message.author)
    await message.reply(reply)

    await bot.process_commands(message)

# -----------------------------
# RUN BOT
# -----------------------------
bot.run(TOKEN)
