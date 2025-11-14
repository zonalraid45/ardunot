import os
import discord
from discord.ext import commands
import aiohttp
import asyncio
import re

# ----------------------------------
# ENV
# ----------------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
HF_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ----------------------------------
# BOT SETUP
# ----------------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

HF_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.2-3B-Instruct"

# Owners
OWNER_IDS = {1020353220641558598, 1167443519070290051}

# ----------------------------------
# HELPERS
# ----------------------------------

def is_admin(member: discord.Member):
    """User is allowed if admin OR in owner list."""
    if member.id in OWNER_IDS:
        return True
    if any(role.permissions.administrator for role in member.roles):
        return True
    return False


async def extract_target_user(message: discord.Message):
    """Find a mentioned user in message."""
    if message.mentions:
        return message.mentions[0]  # first mentioned user
    return None


def extract_time(text: str):
    """Extract 10m, 1h, 2d style times."""
    match = re.search(r"(\d+)(s|m|h|d)", text)
    if not match:
        return None

    num = int(match.group(1))
    unit = match.group(2)

    if unit == "s": return num
    if unit == "m": return num * 60
    if unit == "h": return num * 60 * 60
    if unit == "d": return num * 60 * 60 * 24

    return None


# ----------------------------------
# AI REQUEST
# ----------------------------------
async def fetch_ai_response(user_msg: str, guild: discord.Guild, channel: discord.TextChannel):
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    # Build member list
    member_data = ", ".join([member.name for member in guild.members])

    system_prompt = (
        f"You are **Ardunot-v2**, a smart Discord moderator bot "
        f"in the server '{guild.name}'. "
        f"You know all members: {member_data}. "
        f"You are currently in channel: #{channel.name}. "
        f"Only reply when mentioned. "
        f"You speak casually but clearly. "
        f"Creator: Realboy9000. "
        f"This is a chess community server."
        f"Reply when somebody reply your last message."
    )

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ],
        "max_tokens": 220
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(HF_URL, headers=headers, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
            return "AI failed to respond."


# ----------------------------------
# EVENTS
# ----------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    mention_1 = f"<@{bot.user.id}>"
    mention_2 = f"<@!{bot.user.id}>"

    mentioned = mention_1 in message.content or mention_2 in message.content

    if mentioned:
        # Clean message
        clean_msg = (
            message.content
            .replace(mention_1, "")
            .replace(mention_2, "")
            .strip()
        )

        # ---------------------------------------------------
        # MODERATION COMMANDS
        # ---------------------------------------------------
        if is_admin(message.author):

            # TIMEOUT
            if "timeout" in clean_msg.lower():
                target = await extract_target_user(message)
                duration = extract_time(clean_msg)

                if target and duration:
                    try:
                        await target.timeout(discord.utils.utcnow() + discord.timedelta(seconds=duration))
                        return await message.reply(f"⏳ Timed out **{target}** for {clean_msg.split()[-1]}.")
                    except:
                        return await message.reply("❌ I couldn't timeout that user.")

            # KICK
            if "kick" in clean_msg.lower():
                target = await extract_target_user(message)
                if target:
                    try:
                        await target.kick(reason="AI command by admin")
                        return await message.reply(f"👢 Kicked **{target}**.")
                    except:
                        return await message.reply("❌ I couldn't kick that user.")

            # BAN
            if "ban" in clean_msg.lower():
                target = await extract_target_user(message)
                if target:
                    try:
                        await target.ban(reason="AI command by admin")
                        return await message.reply(f"🔨 Banned **{target}**.")
                    except:
                        return await message.reply("❌ I couldn't ban that user.")

            # DELETE MESSAGES
            if "delete" in clean_msg.lower():
                nums = re.findall(r"\d+", clean_msg)
                if nums:
                    amount = int(nums[0])
                    try:
                        await message.channel.purge(limit=amount + 1)
                        return await message.channel.send(f"🧹 Deleted {amount} messages.")
                    except:
                        return await message.reply("❌ Unable to delete messages.")

        else:
            # If non-admin tries to use moderation
            if any(word in clean_msg.lower() for word in ["timeout","ban","kick","delete"]):
                return await message.reply("❌ You are **not an Admin**, so I can't do that.")

        # ---------------------------------------------------
        # NORMAL AI REPLY
        # ---------------------------------------------------
        reply = await fetch_ai_response(clean_msg, message.guild, message.channel)
        await message.reply(reply)

    await bot.process_commands(message)


bot.run(TOKEN)
