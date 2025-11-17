import discord
from discord.ext import commands
import requests
import random
import os
from datetime import datetime, timezone
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

DISCORD_TOKEN       = os.getenv("DISCORD_TOKEN")
WEBHOOK_START       = os.getenv("WEBHOOK_START")
WEBHOOK_STOP        = os.getenv("WEBHOOK_STOP")
AZURE_TENANT_ID     = os.getenv("AZURE_TENANT_ID")
AZURE_CLIENT_ID     = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
AZURE_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
RESOURCE_GROUP      = os.getenv("RESOURCE_GROUP")
VM_NAME             = os.getenv("VM_NAME")

# ============================================================
# BOT INITIALISATION
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

last_started = None
last_stopped = None

AWAKE_QUOTES = [
    "‘It is not wise to leave a dragon out of your calculations…’",
    "‘All we have to decide is what to do with the time that is given to us.’",
    "‘Mischief is afoot, and the Realm awakens at your call!’",
    "‘By thunder and torchlight, the portals stir once more!’",
]

SLEEP_QUOTES = [
    "‘Even the smallest person can change the course of the future.’",
    "‘Night falls upon the land. Mischief… managed.’",
    "‘The fires dim, and the song of the realm grows still.’",
    "‘Another adventure ends. Rest well, noble traveler.’",
]

# ============================================================
# AZURE AUTHENTICATION
# ============================================================
def azure_token():
    """Authenticate to Azure using client credentials (v2.0 endpoint)."""
    url = f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID')}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("AZURE_CLIENT_ID"),
        "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
        "scope": "https://management.azure.com/.default"
    }
    r = requests.post(url, data=data)
    if r.status_code != 200:
        raise RuntimeError(f"Azure auth failed: {r.status_code} {r.text}")
    return r.json()["access_token"]

def get_vm_status():
    """Return Azure VM power state string or raise a clean exception."""
    token = azure_token()
    sub = os.getenv("AZURE_SUBSCRIPTION_ID")
    rg = os.getenv("RESOURCE_GROUP")
    vm = os.getenv("VM_NAME")

    url = f"https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{vm}/instanceView?api-version=2023-09-01"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"VM query failed: {r.status_code} {r.text}")

    statuses = r.json().get("statuses", [])
    for s in statuses:
        if s.get("code", "").startswith("PowerState/"):
            return s.get("displayStatus", "Unknown")
    return "Unknown"

def format_duration(dt):
    """Return human-readable time difference."""
    delta = datetime.now(timezone.utc) - dt
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes}m"

# ============================================================
# BOT EVENTS & COMMANDS
# ============================================================
@bot.event
async def on_ready():
    print(f"{bot.user} has joined the realm!")

# ------------------------------------------------------------
# !server on/off/status
# ------------------------------------------------------------
@bot.command(aliases=["realm", "mischief"])
async def server(ctx, action: str):
    global last_started, last_stopped
    action = action.lower()
    user = ctx.author.display_name

    try:
        if action in ["on", "start", "awake", "awaken"]:
            requests.post(WEBHOOK_START, headers={"Content-Length": "0"})
            last_started = datetime.now(timezone.utc)
            quote = random.choice(AWAKE_QUOTES)

            embed = discord.Embed(
                title="🪄 The Realm Awakens",
                description=f"{quote}\n\nThe great engines stir at the command of **{user}**.",
                colour=discord.Colour.green(),
            )
            embed.set_footer(text="Mischief Manager | Server Status: Online")
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/10033/10033454.png")
            await ctx.send(embed=embed)

        elif action in ["off", "stop", "sleep", "slumber", "managed"]:
            requests.post(WEBHOOK_STOP, headers={"Content-Length": "0"})
            last_stopped = datetime.now(timezone.utc)
            quote = random.choice(SLEEP_QUOTES)

            embed = discord.Embed(
                title="💤 Mischief Managed",
                description=f"{quote}\n\nThe realm now rests, by order of **{user}**.",
                colour=discord.Colour.dark_grey(),
            )
            embed.set_footer(text="Mischief Manager | Server Status: Offline")
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/15468/15468253.png")
            await ctx.send(embed=embed)

        elif action in ["status", "check"]:
            try:
                state = get_vm_status()
            except Exception as e:
                await ctx.send(f"⚠️ *The scrying crystal flickers... I cannot see the realm right now.*\n```{e}```")
                return

            if state == "VM running":
                colour = discord.Colour.green()
                status_text = "The realm hums with power."
                if last_started:
                    status_text += f"\nIt has been awake for **{format_duration(last_started)}**."
            elif state == "VM deallocated":
                colour = discord.Colour.dark_grey()
                status_text = "The realm slumbers in quiet repose."
                if last_stopped:
                    status_text += f"\nIt has been asleep for **{format_duration(last_stopped)}**."
            else:
                colour = discord.Colour.orange()
                status_text = f"The realm is in an uncertain state: `{state}`."

            embed = discord.Embed(
                title="🔮 Realm Status",
                description=status_text,
                colour=colour,
            )
            embed.set_footer(text=f"Mischief Manager | Azure VM Status: {state}")
            await ctx.send(embed=embed)

        else:
            embed = discord.Embed(
                title="⚠️ Invalid incantation",
                description="Try `!server on`, `!server off`, or `!server status`.",
                colour=discord.Colour.orange(),
            )
            await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"⚠️ *The spell faltered...* An error occurred:\n```{e}```")

# ------------------------------------------------------------
# !help
# ------------------------------------------------------------
@bot.command(aliases=["helpme", "guide", "manual"])
async def help(ctx):
    embed = discord.Embed(
        title="📜 Mischief Manager's Codex",
        description=(
            "Welcome, traveller. I am **The Keeper of Mischief**, steward of the realm.\n\n"
            "You may command me thus:\n"
            "• `!server on` — Awaken the realm.\n"
            "• `!server off` — Let it slumber.\n"
            "• `!server status` — See if the portal hums with life.\n"
            "• `!help` — Summon this tome again.\n\n"
            "_Whisper your commands with care, for magic is fickle._"
        ),
        colour=discord.Colour.purple(),
    )
    embed.set_footer(text="Mischief Manager | Bound by runes of redstone")
    await ctx.send(embed=embed)
    
@bot.command() 
async def intro(ctx):
    embed = discord.Embed(
        title="🪄 Welcome, traveller!",
        description=(
            "Use this channel to control the Minecraft server through our resident keeper, "
            "**Mischief Manager** (*a.k.a.* **The Keeper of Mischief**).\n\n"
            "__**Commands**__\n"
            "`!server on` — Awaken the realm (starts the Minecraft server)\n"
            "`!server off` — Let it slumber (safely stops it)\n"
            "`!server status` — Check whether the realm is awake or dreaming\n"
            "`!help` — Summon the Keeper’s codex of incantations\n\n"
            "__**Tips for Mortals**__\n"
            "⏳ Wait ~1–2 minutes after `!server on` before joining — the portals take time to stabilise.\n"
            "💭 If the Keeper says “The scrying crystal flickers…”, Azure may be sleepy or credentials need a refresh.\n"
            "⚡ Never run `!server off` while players are inside unless you enjoy smiting the innocent.\n"
            "🌙 The realm sleeps automatically when mischief wanes (or when commanded)."
        ),
        colour=discord.Colour.purple()
    )
    embed.set_footer(text="Mischief Manager | Bound by runes of redstone")
    await ctx.send(embed=embed)


# ------------------------------------------------------------
# Random playful replies
# ------------------------------------------------------------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if "keeper" in message.content.lower() and "?" in message.content:
        replies = [
            "I see your curiosity burns bright, young wizard.",
            "You dare question the Keeper of Mischief?",
            "Ah, knowledge seeks you — as do all lost travellers.",
        ]
        await message.channel.send(random.choice(replies))
    await bot.process_commands(message)

# ============================================================
# STARTUP
# ============================================================
if __name__ == "__main__":
    print("Connecting to Discord...")
    bot.run(DISCORD_TOKEN)
