"""Save and load game state.

Serialises player and run data to JSON so a run can be resumed after
closing the game.  A completed run is archived (not deleted) so stats
can be reviewed from the main menu.
"""

import json
import os

from ui import typewriter


def save_game(player, run_state: dict, save_path: str = "savegame.json") -> None:
    """Serialise and write the current run to a JSON file.

    Captures all player stats, inventory item names (class names are used to
    reconstruct items on load), and run progression.

    Args:
        player:     The MainCharacter instance to serialise.
        run_state:  Dict with keys: ``tier``, ``battles_won``, ``nodes_cleared``.
        save_path:  File path for the save data.
    """
    data = {
        "player": {
            # ── Core stats ──────────────────────────────────────────────────
            "name":            player.name,
            "max_hp":          player.max_hp,
            "hp":              player.hp,
            "atk":             player.atk,
            "defense":         player.defense,
            "spd":             player.spd,
            "wisdom":          player.wisdom,
            "crit_chance":     player.crit_chance,
            "crit_multiplier": player.crit_multiplier,

            # ── Class / modifier metadata ──────────────────────────────────
            "class_name":    getattr(player, "class_name",    ""),
            "class_passive": getattr(player, "class_passive", ""),
            "run_modifier":  getattr(player, "run_modifier",  ""),
            "debug_mode":    getattr(player, "debug_mode",    False),

            # ── Progression ────────────────────────────────────────────────
            "lvl":        player.lvl,
            "exp":        player.exp,
            "xp_to_next": player.xp_to_next,
            "gold":       player.gold,

            # ── Combat state ───────────────────────────────────────────────
            "streak":         player.streak,
            "longest_streak": player.longest_streak,
            "focus":          player.focus,
            "max_focus":      player.max_focus,

            # ── Learning ───────────────────────────────────────────────────
            "mastery":       player.mastery,
            "action_points": player.max_action_points,

            # ── Inventory stored as (name, price) pairs ────────────────────
            # Items are reconstructed from their class name on load via
            # the name_to_class mapping in restore_player() (main.py)
            "inventory": [
                {"name": item.name, "price": item.price}
                for item in player.inventory
            ],
        },
        "run": {
            "tier":          run_state["tier"],
            "battles_won":   run_state["battles_won"],
            "nodes_cleared": run_state["nodes_cleared"],
        },
    }

    try:
        with open(save_path, "w") as f:
            json.dump(data, f, indent=2)
        typewriter("Game saved.")
    except Exception as exc:
        typewriter(f"Save failed: {exc}")


def load_game(save_path: str = "savegame.json") -> tuple:
    """Read and return saved player and run data from disk.

    Args:
        save_path: Path to the JSON save file.

    Returns:
        tuple[dict | None, dict | None]:
            (player_data, run_data) on success, (None, None) on failure.
    """
    if not os.path.exists(save_path):
        return None, None   # no save file — nothing to load

    try:
        with open(save_path, "r") as f:
            data = json.load(f)
        typewriter("Save file found.")
        return data["player"], data["run"]
    except Exception as exc:
        typewriter(f"Load failed: {exc}")
        return None, None


def delete_save(save_path: str = "savegame.json") -> None:
    """Archive the completed run, then delete the active save file.

    Instead of discarding data, the save is copied to ``*_completed.json``
    so the player can review stats from the main menu via load_completed_run().

    Args:
        save_path: Path to the active save file.
    """
    if not os.path.exists(save_path):
        return   # nothing to delete

    # Derive archive path: e.g. "savegame.json" → "savegame_completed.json"
    archive_path = save_path.replace(".json", "_completed.json")

    try:
        with open(save_path, "r") as f:
            data = json.load(f)
        with open(archive_path, "w") as f:
            json.dump(data, f, indent=2)
        typewriter("Run archived. View completion stats in the main menu.")
    except Exception as exc:
        typewriter(f"Archive failed: {exc}")

    # Always attempt removal even if archiving failed to clean up the active save
    try:
        os.remove(save_path)
    except OSError:
        pass


def load_completed_run(save_path: str = "savegame.json") -> tuple:
    """Load the archived last-completed-run data.

    Args:
        save_path: Base path used when the run was saved (``_completed``
                   suffix is appended automatically).

    Returns:
        tuple[dict | None, dict | None]:
            (player_data, run_data) on success, (None, None) otherwise.
    """
    archive_path = save_path.replace(".json", "_completed.json")

    if not os.path.exists(archive_path):
        return None, None

    try:
        with open(archive_path, "r") as f:
            data = json.load(f)
        return data["player"], data["run"]
    except Exception as exc:
        typewriter(f"Failed to load completed run: {exc}")
        return None, None


def save_exists(save_path: str = "savegame.json") -> bool:
    """Return True if an active save file exists at save_path.

    Args:
        save_path: Path to check.

    Returns:
        bool: True if the file exists.
    """
    return os.path.exists(save_path)