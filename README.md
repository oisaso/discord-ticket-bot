# Support ticket bot — portfolio demo

**What it proves:** a complete, role-gated ticket bot with persistence and
transcripts. The platform-agnostic core is fully testable without Discord, so
the demo runs on a clean machine with **zero packages installed** — and the
same core powers the live bot.

## Run the demo (no token, no network)

```bash
python simulate.py --demo        # scripted scenario, ~15 seconds
python simulate.py               # interactive, you are "alice"
python simulate.py --as bob      # interactive, you have the Staff role
python -m unittest -v            # 6 tests, all green
```

The scripted demo shows the full lifecycle: open, list, claim, role-gated
close, transcript written. It is built to be screen-recorded for the gig GIF.

## Commands

| Command | Who | Effect |
|---|---|---|
| `!ticket open <subject>` | anyone | opens a ticket, max 2 open per user |
| `!ticket list` | anyone | open tickets, status, claimer |
| `!ticket claim <id>` | Staff | assigns the ticket |
| `!ticket close <id>` | Staff | closes, appends JSONL transcript |
| `!help` | anyone | command list |

## Live bot in four steps

1. Create an application at discord.com/developers, add a Bot, copy the token.
2. Enable **Message Content Intent** on the Bot page.
3. Invite it with scopes `bot` + `applications.commands` and permission
   `Send Messages` / `Read Message History`.
4. `pip install -U discord.py`, then:
   ```bash
   set DISCORD_TOKEN=your-token-here   # Windows
   python bot.py
   ```

Hosting: any $5 VPS or free-tier container host. No database needed — ticket
state is a JSON file the bot owns.

## Layout

| File | Role |
|---|---|
| `bot_core.py` | all logic: store, state machine, command router, transcript |
| `bot.py` | ~30-line discord.py adapter |
| `simulate.py` | mock harness: scripted + interactive, no Discord |
| `test_bot_core.py` | 6 unit tests |
| `config.json` | prefix, staff role, limits, storage paths |

## How it maps to the gig

Bought as "Discord bot / API integration." The differentiator a buyer
understands immediately: *the demo needs nothing installed, and the live bot
is the same code with a 30-line adapter.* Low risk in their eyes.
