import os
import discord
from discord.ext import commands
from collections import deque
import aiohttp
import asyncio
import re

# --- CONFIGURATION ---
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

# --- BOT STATE VARIABLE ---
# Default mode is 'funny'
current_mode = "funny"

# --- PERSONALITY PROMPTS (UPDATED: Removed word limit from SERIOUS_INSTRUCTIONS) ---
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
    # Removed: "Keep responses under 50 characters."
)
# -----------------------------


# --- UTILITY FUNCTIONS ---
def is_admin(member: discord.Member):
    return member.id in OWNER_IDS or any(role.permissions.administrator for role in member.roles)

# Custom check for the command to ensure only OWNER_IDS can use it
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
    global current_mode
    headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}

    mem = channel_memory.get(channel.id, deque(maxlen=MAX_MEMORY))
    history_messages = [{"role": "user", "content": line} for line in mem]

    member_info_list = [{"id": m.id, "name": m.display_name, "roles": [r.name for r in m.roles if r.name != "@everyone"]} for m in guild.members]
    current_user_info = f"User speaking now: {author.display_name} (ID={author.id}, Roles={[r.name for r in author.roles if r.name != '@everyone']})"
    
    # Select the instructions based on the current mode
    personality_instructions = SERIOUS_INSTRUCTIONS if current_mode == "serious" else FUNNY_INSTRUCTIONS

    # Adjust the roasting instruction based on the mode
    roast_instruction = ""
    # ONLY applies the roast instruction when in FUNNY mode
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

    async with aiohttp.ClientSession() as session:
        async with session.post(HF_URL, headers=headers, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                # Remove the @ symbol from the content to prevent any mentions from the AI.
                return content.replace('@', '') 

    return "⚠️ AI failed to respond."

# --- SLASH COMMANDS (for /members) ---
@bot.tree.command(name="members", description="Displays the total member count in the server.")
async def members_slash(interaction: discord.Interaction):
    """Replies with the total number of members in the guild."""
    member_count = interaction.guild.member_count
    await interaction.response.send_message(f"👥 We got **{member_count}** members! Wowie, such a crowd! 😂", ephemeral=False)

# --- PREFIX COMMANDS (!si and !fi) ---
@bot.command(name='si')
@commands.check(is_owner_id)
async def set_serious_mode(ctx):
    """Sets the bot to Serious/Friendly mode (!si). Only for OWNER_IDS."""
    global current_mode
    current_mode = "serious"
    await ctx.send("Bot Mode Switched: I am now in Serious/Friendly operating mode.")

@bot.command(name='fi')
@commands.check(is_owner_id)
async def set_funny_mode(ctx):
    """Sets the bot back to Funny/Roasting mode (!fi). Only for OWNER_IDS."""
    global current_mode
    current_mode = "funny"
    await ctx.send("Bot Mode Switched: I am back to my old Funny/Roasting self. Mate, what a relief.")

# --- BOT EVENTS ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    # Sync global commands.
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Error handler for permission checks on !si and !fi
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        # Only responds to the user for permission errors
        await ctx.send("🚫 You do not have permission to change my personality mode, mate. Only the Owner can do that.")
    else:
        # Default error handling for other command errors
        await commands.Bot.on_command_error(bot, ctx, error)

@bot.event
async def on_message(message):
    # Prevents infinite loop and ensures other bots can reply
    if message.author == bot.user:
        return
        
    # Process prefix commands (!si, !fi) and ensure they are handled first.
    await bot.process_commands(message)

    # Skip AI chat logic if it was a slash command (which starts with /)
    if message.content.startswith('/'):
        return

    channel_id = message.channel.id
    if channel_id not in channel_memory:
        channel_memory[channel_id] = deque(maxlen=MAX_MEMORY)
    channel_memory[channel_id].append(f"{message.author.display_name}: {message.content}")

    clean_msg = message.content.strip()

    # --- ADMIN COMMANDS (Text Triggers) ---
    if is_admin(message.author):
        if "timeout" in clean_msg.lower():
            target = await extract_target_user(message)
            duration = extract_time(clean_msg)
            if target and duration:
                try:
                    await target.timeout(discord.utils.utcnow() + discord.timedelta(seconds=duration))
                    return await message.channel.send(f"⏳ Timed out {target} for {clean_msg.split()[-1]}")
                except:
                    return await message.channel.send("❌ Could not timeout user.")
        if "kick" in clean_msg.lower():
            target = await extract_target_user(message)
            if target:
                try:
                    await target.kick(reason="AI admin command")
                    return await message.channel.send(f"✅ Kicked {target}")
                except:
                    return await message.channel.send("❌ Could not kick user.")
        if "ban" in clean_msg.lower():
            target = await extract_target_user(message)
            if target:
                try:
                    await target.ban(reason="AI admin command")
                    return await message.channel.send(f"✅ Banned {target}")
                except:
                    return await message.channel.send("❌ Could not ban user.")
        if "delete" in clean_msg.lower():
            nums = re.findall(r"\d+", clean_msg)
            if nums:
                amount = int(nums[0])
                try:
                    await message.channel.purge(limit=amount + 1)
                    return await message.channel.send(f"🧹 Deleted {amount} messages.")
                except:
                    return await message.channel.send("❌ Could not delete messages.")
    else:
        if any(word in clean_msg.lower() for word in ["timeout", "kick", "ban", "delete"]):
            return await message.channel.send("❌ U r not an Admin lol")

    # --- AI CHAT RESPONSE ---
    reply = await fetch_ai_response(clean_msg, message.guild, message.channel, message.author)
    await message.channel.send(reply)

bot.run(TOKEN)
