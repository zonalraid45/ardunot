import os
import discord
import requests
from discord.ext import commands

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

MODEL = "mistral-nemo"  # Free model


# -----------------------------
# AI REQUEST FUNCTION (Updated)
# -----------------------------
def ask_ai(message):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": message}]
    }

    try:
        r = requests.post(url, json=data, headers=headers, timeout=15)

        # Non-200 HTTP codes handled
        if r.status_code != 200:
            return "⚠️ AI service is busy or unreachable. Please try again."

        response = r.json()

        # Try to get AI response
        return response["choices"][0]["message"]["content"]

    except Exception:
        # ANY failure = friendly fallback
        return "⚠️ Sorry, I couldn't fetch a reply from the AI. Try again shortly!"


# -----------------------------
# BOT EVENTS
# -----------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Chat when bot is mentioned
    if bot.user.mentioned_in(message):
        user_msg = message.content.replace(f"<@{bot.user.id}>", "").strip()

        await message.channel.trigger_typing()
        reply = ask_ai(user_msg)

        await message.reply(reply)
        return

    await bot.process_commands(message)


# -----------------------------
# OPTIONAL COMMAND
# -----------------------------
@bot.command()
async def ask(ctx, *, question):
    await ctx.channel.trigger_typing()
    reply = ask_ai(question)
    await ctx.send(reply)


# -----------------------------
# RUN BOT
# -----------------------------
bot.run(DISCORD_TOKEN)
