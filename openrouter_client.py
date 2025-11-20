import aiohttp
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SESSION: aiohttp.ClientSession | None = None

async def get_session():
    global SESSION
    if SESSION is None or SESSION.closed:
        SESSION = aiohttp.ClientSession()
    return SESSION

async def call_openrouter(
    prompt: str,
    model: str,
    temperature: float = 0.6,
    retries: int = 4
) -> str:

    if not OPENROUTER_API_KEY:
        return "⚠️ OpenRouter API key missing."

    session = await get_session()

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",
        "X-Title": "Discord Bot"
    }

    backoff = 1

    for _ in range(retries):
        try:
            async with session.post(OPENROUTER_URL, headers=headers, json=payload, timeout=20) as r:
                if r.status == 200:
                    data = await r.json()
                    return data["choices"][0]["message"]["content"]
                elif r.status == 429:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 8)
                else:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 8)
        except:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 8)

    return "⚠️ I'm having trouble responding right now."
