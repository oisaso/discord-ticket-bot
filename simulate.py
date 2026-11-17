"""Run the ticket bot without Discord - scripted demo or interactive REPL.

    python simulate.py --demo          # scripted scenario (for the gig video)
    python simulate.py                 # interactive: type messages as "alice"
    python simulate.py --as bob        # interactive with the Staff role

No token, no network, no third-party packages.
"""

import argparse
import json
import tempfile
import time
from pathlib import Path

from bot_core import CommandError, TicketStore, handle_command, load_config

ROLES = {
    "alice": set(),
    "carol": set(),
    "bob": {"Staff"},
}


def make_store(tmp: str, config: dict) -> TicketStore:
    return TicketStore(str(Path(tmp) / "tickets.json"), max_open=config["max_open_per_user"])


def say(store: TicketStore, config: dict, author: str, text: str) -> None:
    print(f"  {author}: {text}")
    try:
        reply = handle_command(store, config, author, ROLES.get(author, set()), text)
    except CommandError as exc:
        print(f"  bot: error: {exc}")
        return
    if reply is None:
        return
    for line in reply.splitlines():
        print(f"  bot: {line}")


def demo(store: TicketStore, config: dict, slow: float = 0.0) -> None:
    brand = config.get("brand", "support")
    print(f"=== {brand} ticket bot - scripted demo (no Discord needed) ===\n")
    script = [
        ("alice", "!ticket open My invoice shows the wrong total"),
        ("carol", "!ticket open The login page loops forever"),
        ("bob", "!ticket list"),
        ("bob", "!ticket claim 1"),
        ("alice", "!ticket close 1"),          # non-staff: shows the role gate
        ("bob", "!ticket close 1"),
        ("carol", "!ticket list"),
        ("bob", "!help"),
    ]
    for author, text in script:
        say(store, config, author, text)
        print()
        if slow:
            time.sleep(slow)


def repl(store: TicketStore, config: dict, author: str) -> None:
    print(f"interactive mode as '{author}' ({'Staff' if 'Staff' in ROLES.get(author, set()) else 'customer'})")
    print("type a command, blank line to quit\n")
    while True:
        try:
            text = input(f"{author}: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            break
        say(store, config, author, text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo the ticket bot without Discord.")
    parser.add_argument("--demo", action="store_true", help="run the scripted scenario")
    parser.add_argument("--as", dest="author", default="alice", help="your name in interactive mode")
    parser.add_argument("--slow", type=float, default=0.0, help="pause between demo lines (for screen recording)")
    args = parser.parse_args()

    base = Path(__file__).parent
    with tempfile.TemporaryDirectory() as tmp:
        config = load_config(base / "config.json")
        config["storage_path"] = str(Path(tmp) / "tickets.json")
        config["transcript_path"] = str(Path(tmp) / "transcripts.jsonl")
        store = make_store(tmp, config)

        if args.demo:
            demo(store, config, slow=args.slow)
            transcript = Path(config["transcript_path"])
            if transcript.exists():
                last = json.loads(transcript.read_text(encoding="utf-8").strip().splitlines()[-1])
                print(f"transcript: {last['event']} #{last['id']} by {last['closed_by']} at {last['closed_at']}")
        else:
            ROLES.setdefault(args.author, set())
            repl(store, config, args.author)


if __name__ == "__main__":
    main()
