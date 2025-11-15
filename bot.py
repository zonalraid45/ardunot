import os
import discord
from discord.ext import commands
from collections import deque
import aiohttp
import asyncio
import re
from datetime import datetime, timedelta, timezone

# --- CONFIGURATION ---
# Ensure these environment variables are set in your execution environment
TOKEN = os.getenv("DISCORD_TOKEN")
HF_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Intents MUST include Message Content and Members for this structure to work.
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

HF_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.2-3B-Instruct"

CREATOR_ID = 1020353220641558598
OWNER_IDS = {1020353220641558598, 1167443519070290051}

MAX_MEMORY = 30
channel_memory = {}
shushed_channels = {} # {channel_id: datetime_to_resume}

# --- BOT STATE VARIABLE ---
# Default mode is 'funny'
current_mode = "funny"

# --- PERSONALITY PROMPTS ---
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
# -----------------------------


# --- UTILITY FUNCTIONS ---
def is_admin(member: discord.Member):
    """Checks if a member is an owner or has administrator permissions."""
    return member.id in OWNER_IDS or any(role.permissions.administrator for role in member.roles)

# Custom check for the command to ensure only OWNER_IDS can use it
def is_owner_id(ctx):
    """Checks if the command author is an owner ID."""
    return ctx.author.id in OWNER_IDS

async def extract_target_user(message: discord.Message):
    """Extracts the first mentioned user from a message."""
    return message.mentions[0] if message.mentions else None

def extract_time(text: str):
    """Extracts a time duration (e.g., 5m, 1h) from text and returns seconds."""
    match = re.search(r"(\d+)(s|m|h|d)", text)
    if not match:
        return None
    num, unit = int(match.group(1)), match.group(2)
    return num * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]

async def fetch_ai_response(user_msg: str, guild: discord.Guild, channel: discord.TextChannel, author: discord.Member):
    """Fetches a response from the AI model."""
    global current_mode
    headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}

    mem = channel_memory.get(channel.id, deque(maxlen=MAX_MEMORY))
    history_messages = [{"role": "user", "content": line} for line in mem]

    member_info_list = [{"id": m.id, "name": m.display_name, "roles": [r.name for r in m.roles if r.name != "@everyone"]} for m in guild.members]
    current_user_info = f"User speaking now: {author.display_name} (ID={author.id}, Roles={[r.name for r in author.roles if r.name != '@everyone']})"
    
    personality_instructions = SERIOUS_INSTRUCTIONS if current_mode == "serious" else FUNNY_INSTRUCTIONS

    roast_instruction = ""
    if current_mode == "funny":
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
        f"{personality_instructions}\n" # Insert dynamic instructions
        f"{roast_instruction}\n" # Insert dynamic roasting instruction
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
                    # Remove the @ symbol from the content to prevent any mentions from the AI.
                    return content.replace('@', '')
                else:
                    print(f"Hugging Face API Error: {resp.status}, {await resp.text()}")
                    return "⚠️ AI failed to respond due to an API error."
    except Exception as e:
        print(f"API Request Exception: {e}")
        return "⚠️ AI failed to respond due to a connection error."


# --- SLASH COMMANDS (for /members) ---
@bot.tree.command(name="members", description="Displays the total member count in the server.")
async def members_slash(interaction: discord.Interaction):
    """Replies with the total number of members in the guild."""
    member_count = interaction.guild.member_count
    await interaction.response.send_message(f"👥 We got **{member_count}** members! Wowie, such a crowd! 😂", ephemeral=False)

# ------------------------------------
# --- PREFIX COMMANDS (!si, !fi, and !shush) ---
# ------------------------------------

@bot.command(name='si')
@commands.check(is_owner_id)
async def set_serious_mode(ctx):
    """Sets the bot to Serious/Friendly mode (!si). Only for OWNER_IDS."""
    global current_mode
    current_mode = "serious"
    await ctx.send("Bot Mode Switched: I am now in **Serious/Friendly** operating mode.")

@bot.command(name='fi')
@commands.check(is_owner_id)
async def set_funny_mode(ctx):
    """Sets the bot back to Funny/Roasting mode (!fi). Only for OWNER_IDS."""
    global current_mode
    current_mode = "funny"
    await ctx.send("Bot Mode Switched: I am back to my old **Funny/Roasting** self. Mate, what a relief.")

@bot.command(name='shush')
@commands.check(is_admin) # <-- RE-ADDED ADMIN CHECK HERE
async def shush_bot(ctx, *args):
    """
    Shushes the bot in the current channel for a specified duration (default 10m).
    Only Admins or Owners can use this command.
    Example: !shush 10m, !shush 1h
    """
    # This check ensures only Admins/Owners can use !shush
    # The commands.check(is_admin) decorator handles the permission error.
    
    # Default duration is 10 minutes (600 seconds)
    duration_seconds = 600
    duration_display = "10 minutes"
    
    # Check for a specific duration in the arguments
    if args:
        time_seconds = extract_time(args[0])
        if time_seconds is not None:
            duration_seconds = time_seconds
            duration_display = args[0]
        else:
            await ctx.send("⚠️ Invalid duration format. Using default 10 minutes. Use formats like `10m`, `1h`.")

    # Set the time the bot should resume talking
    resume_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    shushed_channels[ctx.channel.id] = resume_time
    
    # Format the resume time for the user
    resume_time_str = discord.utils.format_dt(resume_time, 'T') # T = short time
    
    await ctx.send(f"🔇 Admin Mute: I'll be quiet in this channel until **{resume_time_str}** ({duration_display}).")

# ------------------------------------
# --- BOT EVENTS ---
# ------------------------------------

@bot.event
async def on_ready():
    """Event triggered when the bot successfully connects."""
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Error handler for permission checks on !si, !fi, and !shush
@bot.event
async def on_command_error(ctx, error):
    """Handles errors from bot commands."""
    if isinstance(error, commands.CheckFailure):
        # Specific message for !shush or !si/!fi
        if ctx.command.name in ['shush', 'si', 'fi']:
            await ctx.send("🚫 You do not have permission to change my personality mode or force me to hush, mate. Only the Owner/Admin can do that.")
        else:
            await ctx.send("🚫 You do not have permission to use that command.")
    else:
        await commands.Bot.on_command_error(bot, ctx, error)

@bot.event
async def on_message(message):
    """Handles every incoming message for chat memory, commands, and AI responses."""
    # Prevents infinite loop
    if message.author == bot.user:
        return
        
    # Process prefix commands (!si, !fi, !shush, etc.) first.
    await bot.process_commands(message)

    # Skip AI chat logic if it was a slash command (which starts with /)
    if message.content.startswith('/'):
        return

    channel_id = message.channel.id
    clean_msg = message.content.strip()
    is_admin_user = is_admin(message.author)
    
    # ----------------------------------------------------
    # --- MUTE BOT FOR 10M BY ANY MEMBER (Mention + Keyword) ---
    # ----------------------------------------------------
    # Check if bot is mentioned AND the message contains the word "stop" or "plz stop" (case-insensitive)
    if bot.user.mentioned_in(message) and any(word in clean_msg.lower() for word in ["stop", "plz stop"]):
        
        # Mute duration is fixed at 10 minutes (600 seconds) for ordinary users
        duration_seconds = 600 
        resume_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        shushed_channels[channel_id] = resume_time
        
        resume_time_str = discord.utils.format_dt(resume_time, 'T') # T = short time
        
        # Stop further processing and send the confirmation reply
        return await message.channel.send(f"🤐 Ok, I hear u, I'll be quiet for **10 minutes** in this channel (until {resume_time_str}).")


    # ----------------------------------------------------
    # --- SHUSH/MUTE CHECK (Prevents AI response) ---
    # ----------------------------------------------------
    if channel_id in shushed_channels:
        if datetime.now(timezone.utc) < shushed_channels[channel_id]:
            # The channel is currently muted. Do not respond to any AI chat or save memory.
            return
        else:
            # The shush period has expired, clear the mute status.
            del shushed_channels[channel_id]
    
    # --- CHAT MEMORY UPDATE (Only save memory if the bot isn't shushed) ---
    if channel_id not in channel_memory:
        channel_memory[channel_id] = deque(maxlen=MAX_MEMORY)
    channel_memory[channel_id].append(f"{message.author.display_name}: {message.content}")


    # ----------------------------------------------------
    # --- ADMIN COMMANDS (Text Triggers) ---
    # ----------------------------------------------------
    mod_actions = {
        "timeout": (lambda target, duration: target.timeout(discord.utils.utcnow() + discord.timedelta(seconds=duration)) if duration else None, 
                    lambda target, duration, time_str: f"⏳ Timed out {target} for {time_str}"),
        "kick": (lambda target, _: target.kick(reason="AI admin command"), 
                 lambda target, duration, time_str: f"✅ Kicked {target}"),
        "ban": (lambda target, _: target.ban(reason="AI admin command"), 
                lambda target, duration, time_str: f"✅ Banned {target}"),
        "delete": (lambda target, amount: message.channel.purge(limit=amount + 1) if amount else None, 
                   lambda target, amount, time_str: f"🧹 Deleted {amount} messages.")
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
                    # Execute the action
                    if keyword == "delete":
                        if duration_or_amount:
                             await action_func(target, duration_or_amount)
                             return await message.channel.send(response_func(target, duration_or_amount, duration_or_amount))
                        else:
                            return await message.channel.send("❌ Need a number of messages to delete.")
                    elif target:
                        await action_func(target, duration_or_amount)
                        time_str = clean_msg.split()[-1] if keyword == "timeout" and duration_or_amount else ""
                        return await message.channel.send(response_func(target, duration_or_amount, time_str))
                    else:
                        return await message.channel.send(f"❌ Could not find target user for {keyword}.")
                except:
                    return await message.channel.send(f"❌ Could not perform {keyword} action.")

    if action_found and not is_admin_user:
        return 

    # ----------------------------------------------------
    # --- AI CHAT RESPONSE ---
    # ----------------------------------------------------
    reply = await fetch_ai_response(clean_msg, message.guild, message.channel, message.author)
    await message.channel.send(reply)

# Ensure the bot runs with the token
if TOKEN:
    bot.run(TOKEN)
else:
    print("Error: DISCORD_TOKEN environment variable not set.")
