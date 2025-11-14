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
# 🧠 MAIN AI REQUEST FUNCTION
# ------------------------------------------
async def fetch_ai_response(user_msg: str):
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": user_msg}],
        "max_tokens": 200
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
                        return "⚠️ AI responded with invalid JSON."

                print(f"[AI DEBUG] Attempt {attempt}: HTTP {resp.status} - {text}")
                await asyncio.sleep(1)

        return None  # All attempts failed


# ------------------------------------------
# 🤖 DISCORD EVENTS
# ------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await check_api_health()


# ------------------------------------------
# 💬 REPLY TO ALL MESSAGES + MENTION
# ------------------------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Text the user sent
    user_msg = message.content.strip()

    # Remove mention if included
    mention_text = f"<@{bot.user.id}>"
    mention_text_alt = f"<@!{bot.user.id}>"

    if mention_text in user_msg:
        user_msg = user_msg.replace(mention_text, "").strip()

    if mention_text_alt in user_msg:
        user_msg = user_msg.replace(mention_text_alt, "").strip()

    # If user sends an empty message (only mention), add default prompt
    if user_msg == "":
        user_msg = "Hello!"

    # Generate AI response
    ai_reply = await fetch_ai_response(user_msg)

    if ai_reply is None:
        await message.reply("⚠️ AI service is busy or unreachable. Please try again.")
    else:
        await message.reply(ai_reply)

    await bot.process_commands(message)


# ------------------------------------------
# ▶️ RUN THE BOT
# ------------------------------------------
bot.run(TOKEN)
