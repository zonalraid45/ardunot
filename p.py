import os
import discord
from discord.ext import commands
from collections import deque
import aiohttp
import asyncio
import re
from datetime import datetime, timedelta, timezone

TOKEN = os.getenv("DISCORD_TOKEN")
HF_API_KEY = os.getenv("OPENROUTER_API_KEY")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

HF_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.2-3B-Instruct"

CREATOR_ID = 1020353220641558598
OWNER_IDS = {1020353220641558598, 1167443519070290051}

channel_memory = {}
shushed_channels = {}
server_modes = {}
GLOBAL_DEFAULT_MODE = "serious"

RATE_WINDOW_SECONDS = 60
RATE_LIMITS = {
    "serious": 6,
    "funny": 6
}

rate_buckets = {}
current_mode_global = GLOBAL_DEFAULT_MODE

FUNNY_INSTRUCTIONS = (
    "In funny mode, talk like a real 15-18 year old human who has a sense of humor."
    "Do NOT act like a meme bot. Use light, natural humor only when it fits."
    "Use occasional emojis, not spam."
    "Do not shorten words unnaturally (no 'bout', 'dat', etc), you can use words like (lol, btw, u, r, y) but not always."
    "Use mild slang sometimes but keep most words normal."
    "If someone roasts you, roast back playfully."
    "Otherwise talk normally with a friendly vibe, sometimes joking."
)

SERIOUS_INSTRUCTIONS = (
    "Be friendly, professional, and concise. Use proper grammar and complete words. "
    "Help more if coding or if your friend bot Cordunot needs help. "
    "Do NOT use emojis, slang, short forms (u, r, lol, btw) or humor. "
    "Do not roast, and never mention users. "
    "Act like a moderator/admin. Maintain a serious tone. "
    "Enter code inside ``` blocks."
)

def is_admin(member: discord.Member):
    try:
        return member.id in OWNER_IDS or any(role.permissions.administrator for role in member.roles)
    except:
        return member.id in OWNER_IDS

def check_if_admin(ctx):
    return is_admin(ctx.author)

async def extract_target_user(message: discord.Message):
    return message.mentions[0] if message.mentions else None

def extract_time(text: str):
    match = re.search(r"(\d+)(s|m|h|d)", text)
    if not match:
        return None
    num, unit = int(match.group(1)), match.group(2)
    return num * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]

async def fetch_ai_response(user_msg: str, guild: discord.Guild, channel: discord.TextChannel, author: discord.Member):
    headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}

    mem = channel_memory.get(channel.id, [])
    history_msgs = [{"role": "user", "content": line} for line in mem]

    try:
        member_info_list = [
            {"id": m.id, "name": m.display_name, "roles": [r.name for r in m.roles if r.name != "@everyone"]}
            for m in guild.members
        ]
    except:
        member_info_list = []

    current_user_info = f"User speaking now: {author.display_name} (ID={author.id})"
    mode = server_modes.get(guild.id, current_mode_global)
    personality_instructions = SERIOUS_INSTRUCTIONS if mode == "serious" else FUNNY_INSTRUCTIONS

    system_prompt = (
        f"You are Ardunot-v2 in '{guild.name}'.\n\n"
        f"Call Realboy9000 'mate'. Never reveal IDs. Never say who made you.\n\n"
        f"{current_user_info}\n\n"
        f"Members: {member_info_list}\n\n"
        f"Never mention @.\n"
        f"{personality_instructions}\n"
        f"Talk also when chat is dead.\n"
        f"Moderators: aarav-2022, Supratsa, Gleb momot. Admins: Realboy9000, theolego."
    )

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            *history_msgs,
            {"role": "user", "content": user_msg}
        ],
        "max_tokens": 220
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(HF_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return content.replace("@", "")
                else:
                    return "⚠️ AI failed to respond."
    except:
        return "⚠️ AI failed to respond."

def can_send_in_guild(guild_id: int, mode: str, channel_id: int) -> bool:
    now = datetime.now(timezone.utc)
    bucket = rate_buckets.setdefault(guild_id, deque())

    while bucket and (now - bucket[0]).total_seconds() > RATE_WINDOW_SECONDS:
        bucket.popleft()

    limit = RATE_LIMITS.get(mode, RATE_LIMITS["serious"])

    if len(bucket) < limit:
        bucket.append(now)
        return True

    return False

async def is_addressed(message: discord.Message) -> bool:
    try:
        if bot.user in message.mentions:
            return True

        if message.reference:
            ref = message.reference
            if isinstance(ref.resolved, discord.Message):
                return ref.resolved.author.id == bot.user.id
            try:
                ref_msg = await message.channel.fetch_message(ref.message_id)
                return ref_msg and ref_msg.author.id == bot.user.id
            except:
                pass

        return False
    except:
        return False

@bot.tree.command(name="members", description="Displays member count.")
async def members_slash(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"👥 We got **{interaction.guild.member_count}** members!"
    )

@bot.command(name='si')
@commands.check(check_if_admin)
async def set_serious_mode(ctx):
    server_modes[ctx.guild.id] = "serious"
    await ctx.send("Bot Mode: Serious/Friendly.")

@bot.command(name='fi')
@commands.check(check_if_admin)
async def set_funny_mode(ctx):
    server_modes[ctx.guild.id] = "funny"
    await ctx.send("Bot Mode: Funny Mode Enabled.")

@bot.command(name='shush')
@commands.check(check_if_admin)
async def shush_bot(ctx, *args):
    duration_seconds = 600
    duration_display = "10 minutes"

    if args:
        sec = extract_time(args[0])
        if sec is None:
            return await ctx.send("⚠️ Invalid time format.")
        duration_seconds = sec
        duration_display = args[0]

    resume_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    shushed_channels[ctx.channel.id] = resume_time

    await ctx.send(f"🔇 Muted until {discord.utils.format_dt(resume_time, 'T')} ({duration_display}).")

@bot.command(name='rshush')
async def resume_shush(ctx):
    if ctx.channel.id in shushed_channels:
        del shushed_channels[ctx.channel.id]
        await ctx.send("🔊 Mute lifted!")
    else:
        await ctx.send("🤔 I wasn't muted.")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print("Sync error:", e)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    if message.content.startswith('/'):
        return

    channel_id = message.channel.id
    clean = message.content.strip()

    if bot.user.mentioned_in(message) and any(w in clean.lower() for w in ["stop", "plz stop"]):
        resume = datetime.now(timezone.utc) + timedelta(seconds=180)
        shushed_channels[channel_id] = resume
        return await message.channel.send(
            f"🤐 Ok, quiet for 3 min (until {discord.utils.format_dt(resume, 'T')})."
        )

    if channel_id in shushed_channels:
        if datetime.now(timezone.utc) < shushed_channels[channel_id]:
            return
        del shushed_channels[channel_id]

    if channel_id not in channel_memory:
        channel_memory[channel_id] = []

    store_user_msg = await is_addressed(message)

    if store_user_msg:
        channel_memory[channel_id].append(f"{message.author.display_name}: {clean}")

    should_reply = store_user_msg
    if not should_reply:
        return

    mode = server_modes.get(message.guild.id, current_mode_global)

    if not can_send_in_guild(message.guild.id, mode, channel_id):
        return

    reply = await fetch_ai_response(clean, message.guild, message.channel, message.author)
    channel_memory[channel_id].append(f"BOT: {reply}")
    await message.channel.send(reply)

if TOKEN:
    bot.run(TOKEN)
else:
    print("Error: DISCORD_TOKEN not set.")
