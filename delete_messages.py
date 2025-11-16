import requests
import time
import os

TOKEN = os.getenv("DISCORD_TOKEN")
TARGET_USER = os.getenv("TARGET_USER")
TARGET_GUILD = os.getenv("TARGET_GUILD")

headers = {
    "Authorization": f"Bot {TOKEN}"
}

def get_channels(guild_id):
    r = requests.get(f"https://discord.com/api/v10/guilds/{guild_id}/channels", headers=headers)
    try:
        return r.json()
    except:
        return []

def delete_message(channel_id, message_id):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
    requests.delete(url, headers=headers)

def scan_channel(channel_id):
    last_id = None
    while True:
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=100"
        if last_id:
            url += f"&before={last_id}"

        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            print(f"Cannot read channel {channel_id}, skipping.")
            break

        messages = r.json()
        if not messages:
            break

        for msg in messages:
            last_id = msg["id"]
            if msg.get("author", {}).get("id") == TARGET_USER:
                print(f"Deleting {msg['id']} in channel {channel_id}")
                delete_message(channel_id, msg["id"])
                time.sleep(0.5)

        time.sleep(0.3)

def main():
    print(f"Scanning guild: {TARGET_GUILD}")
    channels = get_channels(TARGET_GUILD)
    for ch in channels:
        if ch["type"] == 0:  # text channels
            cid = ch["id"]
            print(f"Scanning channel: {cid}")
            scan_channel(cid)
            time.sleep(0.5)

if __name__ == "__main__":
    main()
