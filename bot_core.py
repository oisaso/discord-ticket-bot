"""Support-ticket bot core - pure Python, no discord.py required.

The Discord layer (bot.py) is a thin adapter; every decision lives here so it
can be tested and demoed without a token, a server, or a network.

Design notes
- staff commands are gated on a role name from config
- ticket storage uses atomic writes (temp file + os.replace)
- closed tickets append one JSON line to a transcript file
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CONFIG = {
    "prefix": "!",
    "staff_role": "Staff",
    "max_open_per_user": 2,
    "storage_path": "data/tickets.json",
    "transcript_path": "data/transcripts.jsonl",
}

HELP_TEXT = """Commands:
  {prefix}ticket open <subject>   open a support ticket
  {prefix}ticket list             list open tickets
  {prefix}ticket claim <id>       claim a ticket (staff only)
  {prefix}ticket close <id>       close a ticket (staff only)
  {prefix}help                    show this message"""


class CommandError(Exception):
    """User-facing problem. The message is safe to show in chat."""


@dataclass
class Ticket:
    id: int
    author: str
    subject: str
    status: str = "open"  # open | claimed | closed
    claimed_by: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


class TicketStore:
    def __init__(self, path: str | Path, max_open: int = 2) -> None:
        self.path = Path(path)
        self.max_open = max_open
        self.tickets: list[Ticket] = []
        self._load()

    # -- persistence -----------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as f:
            self.tickets = [Ticket(**row) for row in json.load(f)]

    def _save(self) -> None:
        # atomic write: a crash leaves the old file intact, never a half file
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=self.path.name, suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump([asdict(t) for t in self.tickets], f, ensure_ascii=False, indent=2)
            os.replace(tmp_name, self.path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    # -- lookups ---------------------------------------------------------

    def _next_id(self) -> int:
        return max((t.id for t in self.tickets), default=0) + 1

    def get(self, ticket_id: int) -> Ticket:
        for ticket in self.tickets:
            if ticket.id == ticket_id:
                return ticket
        raise CommandError(f"No ticket #{ticket_id}.")

    def list_open(self) -> list[Ticket]:
        return [t for t in self.tickets if t.status != "closed"]

    # -- actions ---------------------------------------------------------

    def open_ticket(self, author: str, subject: str) -> Ticket:
        open_count = sum(
            1 for t in self.tickets if t.author == author and t.status != "closed"
        )
        if open_count >= self.max_open:
            raise CommandError(
                f"You already have {self.max_open} open tickets. Close one first."
            )
        ticket = Ticket(id=self._next_id(), author=author, subject=subject)
        self.tickets.append(ticket)
        self._save()
        return ticket

    def claim_ticket(self, ticket_id: int, staff: str) -> Ticket:
        ticket = self.get(ticket_id)
        if ticket.status == "closed":
            raise CommandError(f"Ticket #{ticket_id} is already closed.")
        if ticket.claimed_by:
            raise CommandError(f"Ticket #{ticket_id} is already claimed by {ticket.claimed_by}.")
        ticket.claimed_by = staff
        ticket.status = "claimed"
        self._save()
        return ticket

    def close_ticket(self, ticket_id: int, staff: str, transcript_path: str) -> Ticket:
        ticket = self.get(ticket_id)
        if ticket.status == "closed":
            raise CommandError(f"Ticket #{ticket_id} is already closed.")
        ticket.status = "closed"
        ticket.claimed_by = ticket.claimed_by or staff
        self._save()
        self._append_transcript(ticket, staff, transcript_path)
        return ticket

    def _append_transcript(self, ticket: Ticket, closed_by: str, path: str) -> None:
        file = Path(path)
        file.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "event": "ticket_closed",
            "closed_by": closed_by,
            "closed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **asdict(ticket),
        }
        with open(file, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# -- command layer --------------------------------------------------------


def load_config(path: str | Path = "config.json") -> dict:
    config = dict(DEFAULT_CONFIG)
    file = Path(path)
    if file.exists():
        with open(file, encoding="utf-8") as f:
            config.update(json.load(f))
    return config


def _require_staff(config: dict, roles: set[str]) -> None:
    if config["staff_role"] not in roles:
        raise CommandError(
            f"Only members with the **{config['staff_role']}** role can do that."
        )


def _parse_ticket_id(argument: str, prefix: str) -> int:
    cleaned = argument.lstrip("#").strip()
    if not cleaned.isdigit():
        raise CommandError(f"Pass a ticket number, e.g. `{prefix}ticket close 3`.")
    return int(cleaned)


def handle_command(
    store: TicketStore,
    config: dict,
    author: str,
    roles: set[str],
    text: str,
) -> str | None:
    """Route one chat message. Returns the reply text, or None if not a command."""
    prefix = config["prefix"]
    if not text.startswith(prefix):
        return None
    body = text[len(prefix) :].strip()
    if not body:
        return None

    command, _, rest = body.partition(" ")
    command = command.lower()

    if command == "help":
        return HELP_TEXT.format(prefix=prefix)
    if command == "ticket":
        return _ticket_command(store, config, author, roles, rest.strip())
    return f"Unknown command `{prefix}{command}`. Try `{prefix}help`."


def _ticket_command(
    store: TicketStore,
    config: dict,
    author: str,
    roles: set[str],
    rest: str,
) -> str:
    prefix = config["prefix"]
    action, _, argument = rest.partition(" ")
    action = action.lower()
    argument = argument.strip()

    if action == "open":
        if not argument:
            raise CommandError(f"Usage: `{prefix}ticket open <subject>`")
        subject = argument[:200]
        ticket = store.open_ticket(author, subject)
        return (
            f"Ticket #{ticket.id} opened for **{author}**.\n"
            f"Subject: {ticket.subject}\n"
            f"Staff will reply here. `{prefix}ticket close {ticket.id}` when resolved."
        )

    if action == "list":
        tickets = store.list_open()
        if not tickets:
            return "No open tickets."
        lines = [f"Open tickets ({len(tickets)}):"]
        for t in tickets:
            claimed = f" (claimed by {t.claimed_by})" if t.claimed_by else ""
            lines.append(f"  #{t.id:<3} [{t.status}]{claimed}  {t.author}: {t.subject[:70]}")
        return "\n".join(lines)

    if action == "claim":
        _require_staff(config, roles)
        ticket = store.claim_ticket(_parse_ticket_id(argument, prefix), author)
        return f"Ticket #{ticket.id} claimed by **{author}**. Subject: {ticket.subject}"

    if action == "close":
        _require_staff(config, roles)
        ticket = store.close_ticket(
            _parse_ticket_id(argument, prefix), author, config["transcript_path"]
        )
        return f"Ticket #{ticket.id} closed by **{author}**. Transcript saved."

    raise CommandError(f"Unknown action `{action}`. Try `{prefix}help`.")
