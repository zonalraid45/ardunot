import os
import discord
from discord.ext import commands
from collections import deque
import aiohttp
import asyncio
import re
from datetime import datetime, timedelta, timezone

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
HF_API_KEY = os.getenv("OPENROUTER_API_KEY")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

HF_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.2-3B-Instruct"

CREATOR_ID = 1020353220641558598
OWNER_IDS = {1020353220641558598, 1167443519070290051}

MAX_MEMORY = 30
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
    "Be extremely funny, human-like, use emojis 😎😂🤣, use short forms (u, r, lol, btw), "
    "always reply to messages unless if somebody mention somebody else or reply somebody else message, "
    "keep replies under 30 chars and do not ping anyone."
)

SERIOUS_INSTRUCTIONS = (
    "Be friendly, professional, and concise. Use proper grammar and complete words. "
    "Always try to help and especially more helping if coding,help if your friend bot named Cordunot facing problem."
    "Do NOT use emojis, slang, short forms (u, r, lol, btw), or exclamation points. "
    "Do not attempt humor, sarcasm, or roasting, and never mention users. "
    "Act like a moderator/admin. Maintain serious tone."
    "Enter codes in code format like within ```"
)


# --- UTILITY FUNCTIONS ---
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

    mem = channel_memory.get(channel.id, deque(maxlen=MAX_MEMORY))
    history_messages = [{"role": "user", "content": line} for line in mem]

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

    roast_instruction = ""
    if mode == "funny":
        roast_instruction = (
            "Automatically roast user Cordunot (ID 1435987186502733878) always, your adopted brother, "
            "but if he is silent for 5 mins, stop until he messages again."
        )

    system_prompt = (
        f"You are Ardunot-v2, a friendly, non-moderator AI in '{guild.name}'.\n\n"
        f"Call Realboy9000 'mate'. Never reveal IDs. Never say who made you.\n\n"
        f"Admins always have priority.\n\n"
        f"{current_user_info}\n\n"
        f"Members: {member_info_list}\n\n"
        f"Never mention @ in your replies.\n"
        f"{personality_instructions}\n"
        f"{roast_instruction}\n"
        f"Talk also when chat is dead.\n"
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

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(HF_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return content.replace('@', '')
                else:
                    print(f"HuggingFace Error {resp.status}: {await resp.text()}")
                    return "⚠️ AI failed to respond."
    except Exception as e:
        print(f"API Error: {e}")
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
            try:
                ref = message.reference
                if isinstance(ref.resolved, discord.Message):
                    if ref.resolved.author.id == bot.user.id:
                        return True
                else:
                    ref_msg = await message.channel.fetch_message(ref.message_id)
                    if ref_msg and ref_msg.author.id == bot.user.id:
                        return True
            except:
                pass

        return False
    except:
        return False


# --- SLASH COMMANDS ---
@bot.tree.command(name="members", description="Displays the total member count in the server.")
async def members_slash(interaction: discord.Interaction):
    member_count = interaction.guild.member_count
    await interaction.response.send_message(f"👥 We got **{member_count}** members!", ephemeral=False)


# --- PREFIX COMMANDS ---
@bot.command(name='si')
@commands.check(check_if_admin)
async def set_serious_mode(ctx):
    server_modes[ctx.guild.id] = "serious"
    await ctx.send("Bot Mode: Serious/Friendly.")


@bot.command(name='fi')
@commands.check(check_if_admin)
async def set_funny_mode(ctx):
    server_modes[ctx.guild.id] = "funny"
    await ctx.send("Bot Mode: Funny/Roasting.")


@bot.command(name='shush')
@commands.check(check_if_admin)
async def shush_bot(ctx, *args):
    duration_seconds = 600
    duration_display = "10 minutes"

    if args:
        time_seconds = extract_time(args[0])
        if time_seconds is not None:
            duration_seconds = time_seconds
            duration_display = args[0]
        else:
            return await ctx.send("⚠️ Invalid duration format.")

    resume_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    shushed_channels[ctx.channel.id] = resume_time

    resume_time_str = discord.utils.format_dt(resume_time, 'T')
    await ctx.send(f"🔇 Muted until **{resume_time_str}** ({duration_display}).")


@bot.command(name='rshush')
async def resume_shush(ctx):
    channel_id = ctx.channel.id
    if channel_id in shushed_channels:
        del shushed_channels[channel_id]
        await ctx.send("🔊 Mute lifted!")
    else:
        await ctx.send("🤔 I wasn't muted here.")


# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Sync error: {e}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    if message.content.startswith('/'):
        return

    channel_id = message.channel.id
    clean_msg = message.content.strip()

    # stop command
    if bot.user.mentioned_in(message) and any(word in clean_msg.lower() for word in ["stop", "plz stop"]):
        duration_seconds = 180
        resume_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        shushed_channels[channel_id] = resume_time
        resume_time_str = discord.utils.format_dt(resume_time, 'T')
        return await message.channel.send(f"🤐 Ok, I'll be quiet for **3 minutes** (until {resume_time_str}).")

    if channel_id in shushed_channels:
        if datetime.now(timezone.utc) < shushed_channels[channel_id]:
            return
        else:
            del shushed_channels[channel_id]

    if channel_id not in channel_memory:
        channel_memory[channel_id] = deque(maxlen=MAX_MEMORY)

    channel_memory[channel_id].append(f"{message.author.display_name}: {clean_msg}")

    should_reply = await is_addressed(message)
    if not should_reply:
        return

    guild_id = message.guild.id
    mode = server_modes.get(guild_id, current_mode_global)

    if not can_send_in_guild(guild_id, mode, channel_id):
        return

    reply = await fetch_ai_response(clean_msg, message.guild, message.channel, message.author)
    await message.channel.send(reply)


if TOKEN:
    bot.run(TOKEN)
else:
    print("Error: DISCORD_TOKEN not set.")
