"""Bestiary system — tracks all enemies encountered with kill counts.

Persists encounter and kill data across all runs so players can review
the full history of every enemy they have faced.
"""

import json
import os
from datetime import datetime

from config import BASE_DIR

# Stored alongside the game executable so data survives between sessions
BESTIARY_FILE = os.path.join(BASE_DIR, "bestiary.json")


class Bestiary:
    """Tracks enemy encounters and kill counts across all runs.

    Internal data structure (self.entries):
        {
            "Goblin": {
                "kills":      4,
                "first_seen": "2024-01-01",
                "last_seen":  "2024-01-03"
            },
            ...
        }

    Encounters are recorded when the player first sees an enemy; kills are
    recorded when the enemy is defeated.  An enemy can be encountered without
    being killed (e.g. the player escapes).
    """

    def __init__(self) -> None:
        # Dict keyed by enemy name; each value is a stat block dict
        self.entries: dict = {}
        self.load()   # populate from disk on construction

    # ── Persistence ──────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load bestiary data from the JSON file.

        Starts with an empty dict if the file doesn't exist or is corrupted
        so the game always initialises cleanly even on a fresh install.
        """
        if os.path.exists(BESTIARY_FILE):
            try:
                with open(BESTIARY_FILE, "r", encoding="utf-8") as f:
                    self.entries = json.load(f)
            except Exception:
                # File corrupted or unreadable — start fresh rather than crash
                self.entries = {}
        else:
            self.entries = {}

    def save(self) -> None:
        """Write bestiary data to the JSON file.

        Silently swallows errors so a save failure never crashes the game.
        """
        try:
            with open(BESTIARY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, indent=2, ensure_ascii=False)
        except Exception:
            pass   # non-fatal: data won't persist but the game can continue

    # ── Recording ─────────────────────────────────────────────────────────────

    def record_encounter(self, enemy_name: str) -> None:
        """Record that an enemy has been seen (not necessarily defeated).

        Creates a new entry on first encounter; updates ``last_seen`` on
        subsequent encounters so we always know the most recent date.

        Args:
            enemy_name: The display name of the encountered enemy.
        """
        today = self._get_date()

        if enemy_name not in self.entries:
            # First time: initialise entry with kills=0
            self.entries[enemy_name] = {
                "kills":      0,
                "first_seen": today,
                "last_seen":  today,
            }
        else:
            # Seen before: just update the last-seen date
            self.entries[enemy_name]["last_seen"] = today

    def record_kill(self, enemy_name: str) -> None:
        """Record that an enemy was defeated and immediately persist to disk.

        Calls record_encounter internally so a kill always has a valid entry
        even if encounter was never explicitly recorded (defensive coding).

        Args:
            enemy_name: The display name of the defeated enemy.
        """
        # Ensure the entry exists before incrementing the kill counter
        if enemy_name not in self.entries:
            self.record_encounter(enemy_name)

        self.entries[enemy_name]["kills"]     += 1
        self.entries[enemy_name]["last_seen"]  = self._get_date()
        self.save()   # persist after every kill so data survives crashes

    # ── Statistics ────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return aggregate bestiary statistics.

        Returns:
            dict with keys:
                ``total_entries`` (int): Unique enemy types encountered.
                ``total_kills``   (int): Combined kill count across all enemies.
                ``entries``       (dict): The full raw entries dict.
        """
        total_kills = sum(e.get("kills", 0) for e in self.entries.values())
        return {
            "total_entries": len(self.entries),
            "total_kills":   total_kills,
            "entries":       self.entries,
        }

    def format_bestiary(self) -> str:
        """Build a formatted multi-line string for display in the UI.

        Sorts enemies by kill count descending so the most-defeated enemies
        appear at the top of the list.

        Returns:
            str: Formatted bestiary text, or a short message if empty.
        """
        if not self.entries:
            return "No enemies encountered yet."

        lines = [
            "══════════════════════════════════════════════",
            "                  BESTIARY                    ",
            "══════════════════════════════════════════════\n",
        ]

        # Sort by kills descending so the hardest-fought enemies show first
        sorted_entries = sorted(
            self.entries.items(),
            key=lambda x: x[1].get("kills", 0),
            reverse=True,
        )

        for name, data in sorted_entries:
            kills = data.get("kills", 0)
            last  = data.get("last_seen", "Unknown")
            # Fixed-width columns for clean alignment
            lines.append(f"{name:20} | Kills: {kills:3} | Last: {last}")

        lines += [
            "\n══════════════════════════════════════════════",
            f"Total Unique Enemies : {self.get_stats()['total_entries']}",
            f"Total Kills          : {self.get_stats()['total_kills']}",
            "══════════════════════════════════════════════",
        ]

        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _get_date() -> str:
        """Return today's date formatted as YYYY-MM-DD for consistent storage."""
        return datetime.now().strftime("%Y-%m-%d")


def get_bestiary() -> Bestiary:
    """Convenience factory — create and return a freshly loaded Bestiary.

    Returns:
        Bestiary: Loaded and ready-to-use instance.
    """
    return Bestiary()