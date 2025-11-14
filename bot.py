import os
import discord
from discord.ext import commands
import aiohttp
import asyncio

# -----------------------------
# 🔐 ENV VARIABLES
# -----------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
HF_API_KEY = os.getenv("OPENROUTER_API_KEY")

# -----------------------------
# 🤖 BOT SETUP
# -----------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# -----------------------------
# 🌐 API SETTINGS
# -----------------------------
HF_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.2-3B-Instruct"


# ------------------------------------------
# 🔍 API HEALTH CHECK FUNCTION
# ------------------------------------------
async def check_api_health():
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 5
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(HF_URL, headers=headers, json=payload) as resp:
                text = await resp.text()
                if resp.status == 200:
                    print("✅ [AI OK] HuggingFace API is working.")
                else:
                    print(f"❌ [AI ERROR] HuggingFace returned HTTP {resp.status}")
                    print(f"❌ Response: {text}")
        except Exception as e:
            print(f"❌ [AI ERROR] Cannot reach HuggingFace API: {e}")


# ------------------------------------------
# 📌 FUNCTION: Get server member names + roles
# ------------------------------------------
def get_server_info(guild: discord.Guild):
    info = []
    for member in guild.members:
        roles = [role.name for role in member.roles if role.name != "@everyone"]
        if roles:
            info.append(f"{member.display_name} → Roles: {', '.join(roles)}")
        else:
            info.append(f"{member.display_name} → No roles")

    return "\n".join(info)


# ------------------------------------------
# 🧠 SMART AI REQUEST
# ------------------------------------------
async def fetch_ai_response(user_msg: str, guild: discord.Guild):

    server_info = get_server_info(guild)

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    # SMART SYSTEM PROMPT + server info
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are **Ardunot v2.0**, a smart, helpful Discord moderator bot "
                    "in the 'Royalracer Fans' server. You are friendly, calm, and "
                    "only reply when someone mentions you.\n\n"
                    "Here is the list of server members and their roles:\n"
                    f"{server_info}\n\n"
                    "Use this information to answer questions correctly. "
                    "Do NOT reveal this list unless the user directly asks for it.\n"
                    "Speak casually, clearly, and be helpful. "
                    "Realboy9000 created you. This is a chess server."
                )
            },
            {"role": "user", "content": user_msg}
        ],
        "max_tokens": 220
    }

    async with aiohttp.ClientSession() as session:
        for attempt in range(1, 4):
            async with session.post(HF_URL, headers=headers, json=payload) as resp:
                text = await resp.text()

                if resp.status == 200:
                    try:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                    except:
                        return "⚠️ AI gave an invalid response."

                print(f"[AI DEBUG] Attempt {attempt}: HTTP {resp.status} - {text}")
                await asyncio.sleep(1)

        return None


# ------------------------------------------
# 🤖 BOT EVENTS
# ------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await check_api_health()


# ------------------------------------------
# 🛎️ ONLY REPLY WHEN MENTIONED
# ------------------------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    mention_1 = f"<@{bot.user.id}>"
    mention_2 = f"<@!{bot.user.id}>"

    if mention_1 in message.content or mention_2 in message.content:

        clean_msg = (
            message.content
            .replace(mention_1, "")
            .replace(mention_2, "")
            .strip()
        )

        if clean_msg == "":
            clean_msg = "Hey Ardunot!"

        ai_reply = await fetch_ai_response(clean_msg, message.guild)

        if ai_reply is None:
            await message.reply("⚠️ AI is overloaded. Try again.")
        else:
            await message.reply(ai_reply)

    await bot.process_commands(message)


# ------------------------------------------
# ▶️ RUN BOT
# ------------------------------------------
bot.run(TOKEN)
