"""Discord adapter - thin shell over bot_core.

Run:  set DISCORD_TOKEN=...  &&  python bot.py
Needs: pip install -U discord.py
"""

import os
import sys

try:
    import discord
except ImportError:
    raise SystemExit("discord.py not installed. Run: pip install -U discord.py")

from bot_core import CommandError, TicketStore, handle_command, load_config


def main() -> None:
    config = load_config("config.json")
    store = TicketStore(config["storage_path"], max_open=config["max_open_per_user"])

    intents = discord.Intents.default()
    intents.message_content = True  # required for reading message text
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"logged in as {client.user} | prefix {config['prefix']} | {len(store.tickets)} tickets loaded")

    @client.event
    async def on_message(message: discord.Message):
        if message.author.bot:
            return
        roles = {role.name for role in getattr(message.author, "roles", [])}
        try:
            reply = handle_command(store, config, str(message.author), roles, message.content)
        except CommandError as exc:
            reply = f"error: {exc}"
        if reply is None:
            return
        await message.reply(reply)

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set the DISCORD_TOKEN environment variable first.")
    client.run(token)


if __name__ == "__main__":
    main()
