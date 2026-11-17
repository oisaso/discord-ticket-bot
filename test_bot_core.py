"""Unit tests for the bot core. No Discord, no token, no network.

Run: python -m unittest -v
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bot_core import (
    CommandError,
    DEFAULT_CONFIG,
    TicketStore,
    handle_command,
)


class BotCoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        root = Path(self._tmp.name)
        self.config = dict(DEFAULT_CONFIG)
        self.config["storage_path"] = str(root / "tickets.json")
        self.config["transcript_path"] = str(root / "transcripts.jsonl")
        self.store = TicketStore(self.config["storage_path"], max_open=2)

    def tearDown(self):
        self._tmp.cleanup()

    def test_per_user_open_limit(self):
        self.store.open_ticket("alice", "first")
        self.store.open_ticket("alice", "second")
        with self.assertRaises(CommandError):
            self.store.open_ticket("alice", "third")
        # a different user is not affected
        self.store.open_ticket("carol", "someone else's")

    def test_staff_gate_on_close(self):
        ticket = self.store.open_ticket("alice", "help")
        with self.assertRaises(CommandError):
            handle_command(self.store, self.config, "alice", set(), f"!ticket close {ticket.id}")
        reply = handle_command(self.store, self.config, "bob", {"Staff"}, f"!ticket close {ticket.id}")
        self.assertIn("closed", reply)
        self.assertEqual(self.store.get(ticket.id).status, "closed")

    def test_claim_sets_owner(self):
        ticket = self.store.open_ticket("alice", "help")
        handle_command(self.store, self.config, "bob", {"Staff"}, f"!ticket claim {ticket.id}")
        claimed = self.store.get(ticket.id)
        self.assertEqual(claimed.status, "claimed")
        self.assertEqual(claimed.claimed_by, "bob")

    def test_persistence_across_instances(self):
        self.store.open_ticket("alice", "one")
        self.store.open_ticket("carol", "two")
        reopened = TicketStore(self.config["storage_path"], max_open=2)
        self.assertEqual(len(reopened.tickets), 2)
        self.assertEqual(reopened.tickets[0].subject, "one")

    def test_close_writes_transcript(self):
        ticket = self.store.open_ticket("alice", "help")
        handle_command(self.store, self.config, "bob", {"Staff"}, f"!ticket close {ticket.id}")
        transcript = Path(self.config["transcript_path"])
        self.assertTrue(transcript.exists())
        row = json.loads(transcript.read_text(encoding="utf-8").strip())
        self.assertEqual(row["event"], "ticket_closed")
        self.assertEqual(row["id"], ticket.id)
        self.assertEqual(row["closed_by"], "bob")

    def test_non_commands_are_ignored(self):
        self.assertIsNone(handle_command(self.store, self.config, "alice", set(), "hello there"))


if __name__ == "__main__":
    unittest.main()
