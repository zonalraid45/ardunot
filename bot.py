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
# 🧠 SMART AI REQUEST
# ------------------------------------------
async def fetch_ai_response(user_msg: str):
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    # SMART SYSTEM PROMPT
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are **Ardunot v2.0**, a smart and helpful Discord moderator bot "
                    "in the 'Royalracer Fans' server. You are friendly, calm, and "
                    "answer only when someone *directly mentions you*. Your replies "
                    "should be smart, helpful, and feel like a real conversation. "
                    "Speak casually but clearly. Keep things short unless the user "
                    "asks for detailed help.Realboy9000 made you."
                    "This is a chess server"
                )
            },
            {
                "role": "user",
                "content": user_msg
            }
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
                        return "⚠️ AI gave invalid response."

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

    # Bot's mention formats
    mention_1 = f"<@{bot.user.id}>"
    mention_2 = f"<@!{bot.user.id}>"

    # CHECK IF BOT IS MENTIONED
    if mention_1 in message.content or mention_2 in message.content:

        # Remove mention text
        clean_msg = (
            message.content
            .replace(mention_1, "")
            .replace(mention_2, "")
            .strip()
        )

        # Fallback if nothing after mention
        if clean_msg == "":
            clean_msg = "Hey Ardunot!"

        # Generate smart reply
        ai_reply = await fetch_ai_response(clean_msg)

        if ai_reply is None:
            await message.reply("⚠️ AI is busy. Try again.")
        else:
            await message.reply(ai_reply)

    await bot.process_commands(message)


# ------------------------------------------
# ▶️ RUN BOT
# ------------------------------------------
bot.run(TOKEN)
