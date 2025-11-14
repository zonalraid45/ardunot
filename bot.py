import os
import discord
import requests
from discord.ext import commands

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

MODEL = "mistralai/mistral-nemo"   # Free + stable model


# ---------------------------------------------------------------------
# AI REQUEST (with retries, logs, correct headers)
# ---------------------------------------------------------------------
def ask_ai(message):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/test/test",  # REQUIRED by OpenRouter
        "X-Title": "DiscordBot"                          # REQUIRED by OpenRouter
    }

    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": message}]
    }

    for attempt in range(1, 4):
        try:
            r = requests.post(url, json=data, headers=headers, timeout=15)

            # Debug log
            print(f"[AI DEBUG] Attempt {attempt}: {r.text}")

            if r.status_code != 200:
                print(f"[AI ERROR] HTTP {r.status_code} (attempt {attempt})")
                continue

            response = r.json()
            return response["choices"][0]["message"]["content"]

        except Exception as e:
            print(f"[AI EXCEPTION] attempt {attempt} → {e}")

    return "⚠️ AI service is busy or unreachable. Please try again."


# ---------------------------------------------------------------------
# BOT EVENTS
# ---------------------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Bot replies when mentioned
    if bot.user.mentioned_in(message):
        user_msg = message.content.replace(f"<@{bot.user.id}>", "").strip()

        # Show typing
        await message.channel.typing()

        reply = ask_ai(user_msg)
        await message.reply(reply)
        return

    await bot.process_commands(message)


# ---------------------------------------------------------------------
# COMMAND: !ask
# ---------------------------------------------------------------------
@bot.command()
async def ask(ctx, *, question):
    await ctx.channel.typing()
    reply = ask_ai(question)
    await ctx.send(reply)


# ---------------------------------------------------------------------
# RUN BOT
# ---------------------------------------------------------------------
bot.run(DISCORD_TOKEN)

