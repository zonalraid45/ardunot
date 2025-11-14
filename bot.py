import os
import discord
import requests
from discord.ext import commands

HF_API_KEY = os.getenv("OPENROUTER_API_KEY")  # using your existing env variable
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

HF_MODEL = "google/gemma-2-2b-it"  # free chat model


# ------------------------------------------------------------
# HuggingFace Chat Completion API (new)
# ------------------------------------------------------------
def ask_ai(message):
    url = "https://router.huggingface.co/hf-inference/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": HF_MODEL,
        "messages": [
            {"role": "user", "content": message}
        ],
        "max_tokens": 200
    }

    for attempt in range(1, 4):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=20)

            print(f"[AI DEBUG] Attempt {attempt}: {r.text}")

            if r.status_code != 200:
                print(f"[AI ERROR] HTTP {r.status_code} (Attempt {attempt})")
                continue

            response = r.json()
            return response["choices"][0]["message"]["content"]

        except Exception as e:
            print(f"[AI EXCEPTION] Attempt {attempt} → {e}")

    return "⚠️ AI service is busy or unreachable. Please try again."


# ------------------------------------------------------------
# BOT EVENTS
# ------------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # bot replies when mentioned
    if bot.user.mentioned_in(message):
        user_msg = message.content.replace(f"<@{bot.user.id}>", "").strip()

        await message.channel.typing()
        reply = ask_ai(user_msg)
        await message.reply(reply)
        return

    await bot.process_commands(message)


# ------------------------------------------------------------
# COMMAND: !ask
# ------------------------------------------------------------
@bot.command()
async def ask(ctx, *, question):
    await ctx.channel.typing()
    reply = ask_ai(question)
    await ctx.send(reply)


# ------------------------------------------------------------
# RUN BOT
# ------------------------------------------------------------
bot.run(DISCORD_TOKEN)

