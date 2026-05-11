"""Configuration and setup management.

Handles loading/saving game configuration, managing note file paths,
save file locations, and the initial setup wizard.
"""

import json
import os
from ui import typewriter, input_handler

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print("[Config] No config.json found — running setup wizard.")
        return setup_wizard()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[Config] config.json has a formatting error: {e}")
        print("Delete config.json and restart to run setup again.")
        input("Press Enter to exit.")
        raise SystemExit

    if not config.get("notes"):
        print("[Config] No notes files configured — running setup wizard.")
        return setup_wizard()

    return config


def resolve_path(relative_path):
    return os.path.join(BASE_DIR, relative_path)


def get_notes_paths(config):
    paths = {}
    notes = config.get("notes", {})
    for qtype, relative_path in notes.items():
        absolute = resolve_path(relative_path)
        if not os.path.exists(absolute):
            print(f"[Config] Warning: notes file not found — {absolute}")
        paths[qtype] = absolute
    return paths


def get_save_path(config):
    return resolve_path(config.get("save_file", "savegame.json"))


def get_last_run_path(config):
    return resolve_path(config.get("last_run_file", "last_run.txt"))


def browse_for_file(prompt):
    """
    Ask the user to type or paste a file path.
    Uses input_handler so it works in both terminal and GUI modes.
    Returns the absolute path string, or None if skipped.
    """
    typewriter(prompt)
    typewriter("(Press Enter without typing to skip this question type)")

    while True:
        raw = input_handler.ask("> ").strip().strip('"').strip("'")

        if raw == "":
            return None

        path = os.path.normpath(raw)

        if os.path.isfile(path):
            return path
        else:
            typewriter(f"File not found: {path}")
            typewriter("Please check the path and try again, or press Enter to skip.")


def setup_wizard():
    """
    Interactive setup that asks the user to locate notes files
    and saves the result to config.json.
    """
    typewriter("\n" + "="*50)
    typewriter("  GAME-ON LEARNING — FIRST TIME SETUP")
    typewriter("="*50)
    typewriter("\nThis wizard will help you load your study notes.")
    typewriter("Paste full file paths when prompted.\n")

    question_types = {
        "TF": {
            "label": "True/False questions",
            "format": "Each line: Statement = True  or  Statement = False",
        },
        "MC": {
            "label": "Multiple Choice questions",
            "format": 'Each line: {"question":"...","options":["A","B","C"],"answer":"A"}',
        },
        "AR": {
            "label": "Arithmetic / Short Answer questions",
            "format": "Each line: Question = Answer",
        },
        "ID": {
            "label": "Identification questions",
            "format": "Each line: Question = Answer",
        },
        "FB": {
            "label": "Fill in the Blanks questions",
            "format": "Each line: Question with _______ = Answer",
        },
        "OD": {
            "label": "Ordering questions",
            "format": 'Each line: {"question":"...","items":["A","B","C"],"answer":"1,2,3"}',
        },
    }

    notes_config = {}

    for qtype, info in question_types.items():
        typewriter(f"\n--- {info['label']} ({qtype}) ---")
        typewriter(f"Expected format: {info['format']}")
        path = browse_for_file(f"Path to your {info['label']} file:")

        if path:
            try:
                rel = os.path.relpath(path, BASE_DIR)
                notes_config[qtype] = rel
            except ValueError:
                notes_config[qtype] = path
            typewriter(f"Loaded: {path}")
        else:
            typewriter(f"Skipped {qtype}.")

    if not notes_config:
        typewriter("\nNo files were loaded. The game needs at least one notes file.")
        typewriter("Re-run the game to try again.")
        input_handler.ask("Press Enter to exit.")
        raise SystemExit

    config = {
        "notes": notes_config,
        "save_file": "savegame.json",
        "last_run_file": "last_run.txt",
    }

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        typewriter(f"\nSetup saved to {CONFIG_FILE}")
        typewriter("You can edit this file directly any time to change your notes.\n")
    except Exception as e:
        typewriter(f"Could not save config: {e}")
        input_handler.ask("Press Enter to exit.")
        raise SystemExit

    return config