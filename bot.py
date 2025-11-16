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
GLOBAL_DEFAULT_MODE = "serious" # CHANGED: Default mode is now "serious"

# -----------------------------
# ⭐ NEW RATE LIMIT SYSTEM ⭐
# -----------------------------
RATE_WINDOW_SECONDS = 60

RATE_LIMITS = {
    "serious": 6,    # CHANGED: 1 msg per 10 sec = 6 msg/min
    "funny": 6       # 1 msg per 10 sec = 6 msg/min
}
# BOT_CHANNEL_LIMIT removed
rate_buckets = {} # guild_id -> deque timestamps
# -----------------------------

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
    "Do not attempt humor, sarcasm, or roasting, and never mention users by name or nickname. "
    "Do act like a moderator or admin. Maintain a serious but helpful tone."
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


def is_owner_id(ctx):
    return ctx.author.id in OWNER_IDS


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
        f"Never mention @ in your replies neither mention somebody or mention last message when you reply."
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
                    print(f"Hugging Face API Error: {resp.status}, {await resp.text()}")
                    return "⚠️ AI failed to respond due to an API error."
    except Exception as e:
        print(f"API Request Exception: {e}")
        return "⚠️ AI failed to respond due to a connection error."


# -----------------------------
# ⭐ NEW RATE LIMIT FUNCTION ⭐
# -----------------------------
def can_send_in_guild(guild_id: int, mode: str, channel_id: int) -> bool:
    """
    Updated: limit is now 1 msg per 10 sec (6 msg/min) for all channels.
    """
    now = datetime.now(timezone.utc)
    bucket = rate_buckets.setdefault(guild_id, deque())

    # purge timestamps older than 1 min
    while bucket and (now - bucket[0]).total_seconds() > RATE_WINDOW_SECONDS:
        bucket.popleft()

    # Fallback uses 'serious' limit since it's the new default
    limit = RATE_LIMITS.get(mode, RATE_LIMITS["serious"])

    if len(bucket) < limit:
        bucket.append(now)
        return True

    return False
# -----------------------------


async def is_addressed(message: discord.Message) -> bool:
    try:
        # Respond if bot is mentioned
        if bot.user in message.mentions:
            return True

        # Respond if the message is a reply to the bot's last message
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
        
        # Removed the logic checking for recent bot messages in history
        return False
    except:
        return False


# --- SLASH COMMANDS ---
@bot.tree.command(name="members", description="Displays the total member count in the server.")
async def members_slash(interaction: discord.Interaction):
    member_count = interaction.guild.member_count
    await interaction.response.send_message(f"👥 We got **{member_count}** members! Wowie, such a crowd! 😂", ephemeral=False)


# --- PREFIX COMMANDS ---
@bot.command(name='si')
@commands.check(check_if_admin)
async def set_serious_mode(ctx):
    server_modes[ctx.guild.id] = "serious"
    await ctx.send("Bot Mode Switched for this server: I am now in **Serious/Friendly** operating mode.")


@bot.command(name='fi')
@commands.check(check_if_admin)
async def set_funny_mode(ctx):
    server_modes[ctx.guild.id] = "funny"
    await ctx.send("Bot Mode Switched for this server: I am back to my old **Funny/Roasting** self. Mate, what a relief.")


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
            await ctx.send("⚠️ Invalid duration format.")
    resume_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    shushed_channels[ctx.channel.id] = resume_time

    resume_time_str = discord.utils.format_dt(resume_time, 'T')
    await ctx.send(f"🔇 Admin Mute: I'll be quiet until **{resume_time_str}** ({duration_display}).")


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
        print(f"Failed to sync commands: {e}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        if ctx.command and ctx.command.name in ['shush', 'si', 'fi']:
            await ctx.send("🚫 You do not have permission to change my mode.")
        else:
            await ctx.send("🚫 You do not have permission.")
    else:
        print(f"Unhandled: {error}")
        await commands.Bot.on_command_error(bot, ctx, error)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    if message.content.startswith('/'):
        return

    channel_id = message.channel.id
    clean_msg = message.content.strip()
    is_admin_user = is_admin(message.author)

    # 3-min user mute
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
    channel_memory[channel_id].append(f"{message.author.display_name}: {message.content}")

    mod_actions = {
        "timeout": (
            lambda target, duration: target.timeout(discord.utils.utcnow() + discord.timedelta(seconds=duration)) if duration else None,
            lambda target, duration, time_str: f"⏳ Timed out {target} {time_str}"
        ),
        "kick": (
            lambda target, _: target.kick(reason="AI admin command"),
            lambda target, duration, time_str: f"✅ Kicked {target}"
        ),
        "ban": (
            lambda target, _: target.ban(reason="AI admin command"),
            lambda target, duration, time_str: f"✅ Banned {target}"
        ),
        "delete": (
            lambda target, amount: message.channel.purge(limit=amount + 1) if amount else None,
            lambda target, amount, time_str: f"🧹 Deleted {amount} messages."
        )
    }

    action_found = False
    for keyword, (action_func, response_func) in mod_actions.items():
        if keyword in clean_msg.lower():
            action_found = True

            if not is_admin_user:
                return await message.channel.send("❌ U r not an Admin lol")

            target = await extract_target_user(message)
            duration_or_amount = None

            if keyword == "delete":
                nums = re.findall(r"\d+", clean_msg)
                duration_or_amount = int(nums[0]) if nums else None
            elif keyword == "timeout":
                duration_or_amount = extract_time(clean_msg)

            if target or keyword == "delete":
                try:
                    if keyword == "delete":
                        if duration_or_amount:
                            await action_func(target, duration_or_amount)
                            return await message.channel.send(response_func(target, duration_or_amount, duration_or_amount))
                        else:
                            return await message.channel.send("❌ Need a number.")

                    elif target:
                        await action_func(target, duration_or_amount)
                        time_str = clean_msg.split()[-1] if duration_or_amount else ""
                        return await message.channel.send(response_func(target, duration_or_amount, time_str))

                    else:
                        return await message.channel.send(f"❌ No target.")
                except:
                    return await message.channel.send(f"❌ Failed to perform {keyword}.")

    if action_found:
        return

    should_reply = await is_addressed(message)
    if not should_reply:
        return

    guild_id = message.guild.id if message.guild else None
    mode = server_modes.get(guild_id, current_mode_global)

    # Rate-limit check
    if guild_id is not None and not can_send_in_guild(guild_id, mode, channel_id):
        return

    reply = await fetch_ai_response(clean_msg, message.guild, message.channel, message.author)
    await message.channel.send(reply)


if TOKEN:
    bot.run(TOKEN)
else:
    print("Error: DISCORD_TOKEN not set.")
