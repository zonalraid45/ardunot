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
OWNER_IDS = {1020353220641558598, 1167443519070290051}  # Realboy9000 & Theolego

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
    if not match: return None
    num, unit = int(match.group(1)), match.group(2)
    return num * {"s":1,"m":60,"h":3600,"d":86400}[unit]

# -----------------------------
# AI REQUEST
# -----------------------------
async def fetch_ai_response(user_msg: str, guild: discord.Guild, channel: discord.TextChannel):
    headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}

    # Get last 30 messages for context
    mem = channel_memory.get(channel.id, deque(maxlen=MAX_MEMORY))
    chat_history = "\n".join(mem)

    member_data = ", ".join([member.name for member in guild.members])

    system_prompt = (
        f"You are Ardunot-v2, a smart Discord moderator bot in server '{guild.name}'. "
        f"You know all members: {member_data}. You are in channel: #{channel.name}. "
        f"Only reply when mentioned or when someone replies to your last message. "
        f"Recent chat history:\n{chat_history}"
    )

    payload = {
        "model": MODEL,
        "messages": [
            {"role":"system","content":system_prompt},
            {"role":"user","content":user_msg}
        ],
        "max_tokens":220
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

    # --- store memory ---
    channel_id = message.channel.id
    if channel_id not in channel_memory:
        channel_memory[channel_id] = deque(maxlen=MAX_MEMORY)
    channel_memory[channel_id].append(f"{message.author.display_name}: {message.content}")

    # --- detect mention or reply to bot ---
    mentioned = bot.user.mention in message.content
    reply_to_bot = message.reference and isinstance(message.reference.resolved, discord.Message) \
                   and message.reference.resolved.author == bot.user

    if mentioned or reply_to_bot:
        clean_msg = message.content.replace(bot.user.mention, "").strip() if mentioned else message.content

        # --- MODERATION COMMANDS ---
        if is_admin(message.author):
            if "timeout" in clean_msg.lower():
                target = await extract_target_user(message)
                duration = extract_time(clean_msg)
                if target and duration:
                    try:
                        await target.timeout(discord.utils.utcnow() + discord.timedelta(seconds=duration))
                        return await message.reply(f"⏳ Timed out {target} for {clean_msg.split()[-1]}")
                    except: return await message.reply("❌ Could not timeout user.")
            if "kick" in clean_msg.lower():
                target = await extract_target_user(message)
                if target:
                    try: await target.kick(reason="AI admin command")
                    except: return await message.reply("❌ Could not kick user.")
            if "ban" in clean_msg.lower():
                target = await extract_target_user(message)
                if target:
                    try: await target.ban(reason="AI admin command")
                    except: return await message.reply("❌ Could not ban user.")
            if "delete" in clean_msg.lower():
                nums = re.findall(r"\d+", clean_msg)
                if nums:
                    amount = int(nums[0])
                    try:
                        await message.channel.purge(limit=amount+1)
                        await message.channel.send(f"🧹 Deleted {amount} messages.")
                    except: await message.reply("❌ Could not delete messages.")
        else:
            if any(word in clean_msg.lower() for word in ["timeout","kick","ban","delete"]):
                return await message.reply("❌ You are not an Admin.")

        # --- AI REPLY ---
        reply = await fetch_ai_response(clean_msg, message.guild, message.channel)
        await message.reply(reply)

    await bot.process_commands(message)

bot.run(TOKEN)
