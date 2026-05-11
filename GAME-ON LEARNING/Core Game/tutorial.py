"""Tutorial system - first-run interactive guide for new players."""

import json
import os
import time

from ui import typewriter, input_handler
from config import BASE_DIR

TUTORIAL_STATE_FILE = os.path.join(BASE_DIR, "tutorial_completed.json")


class Tutorial:
    """Interactive tutorial system for first-time players."""
    
    def __init__(self):
        self.completed = self._load_completion()
    
    def _load_completion(self):
        """Check if tutorial has been completed."""
        if os.path.exists(TUTORIAL_STATE_FILE):
            try:
                with open(TUTORIAL_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("completed", False)
            except Exception:
                return False
        return False
    
    def _save_completion(self):
        """Mark tutorial as completed."""
        try:
            with open(TUTORIAL_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({"completed": True}, f)
        except Exception:
            pass
    
    def is_completed(self):
        """Check if player has completed tutorial."""
        return self.completed
    
    def run(self):
        """Run the interactive tutorial."""
        if self.completed:
            return
        
        typewriter("\n" + "=" * 60)
        typewriter("         WELCOME TO GAME-ON LEARNING!")
        typewriter("=" * 60)
        typewriter("\nYou are a brave adventurer who learns through combat.")
        typewriter("Every enemy you face challenges your knowledge!")
        time.sleep(2)
        
        typewriter("\n┌─ CHAPTER 1: THE BASICS ─────────────────────────┐")
        typewriter("│                                                 │")
        typewriter("│ Combat Challenges work like this:               │")
        typewriter("│                                                 │")
        typewriter("│ 1. Face an enemy                                │")
        typewriter("│ 2. Answer a question correctly to damage it     │")
        typewriter("│ 3. Wrong answers cost you HP                    │")
        typewriter("│ 4. Defeat the enemy to earn rewards             │")
        typewriter("│                                                 │")
        typewriter("└─────────────────────────────────────────────────┘")
        time.sleep(3)
        
        choice = input_handler.ask_choice(
            [{"label": "Continue", "value": "1"}],
            "> "
        )
        
        typewriter("\n┌─ CHAPTER 2: YOUR STATS ──────────────────────────┐")
        typewriter("│                                                 │")
        typewriter("│ ATK - Attack: Damage dealt per hit              │")
        typewriter("│ DEF - Defense: Reduces enemy damage             │")
        typewriter("│ SPD - Speed: Affects dodge chance               │")
        typewriter("│ WIS - Wisdom: Scales damage from correct answers│")
        typewriter("│ CRIT - Critical: Chance for double damage       │")
        typewriter("│                                                 │")
        typewriter("└─────────────────────────────────────────────────┘")
        time.sleep(3)
        
        choice = input_handler.ask_choice(
            [{"label": "Continue", "value": "1"}],
            "> "
        )
        
        typewriter("\n┌─ CHAPTER 3: MECHANICS ───────────────────────────┐")
        typewriter("│                                                 │")
        typewriter("│ Focus - Builds on correct answers (max 100)     │")
        typewriter("│ Focus reaches 100? Trigger a special attack!    │")
        typewriter("│                                                 │")
        typewriter("│ Streak - Consecutive correct answers            │")
        typewriter("│ Higher streak = more damage multiplier          │")
        typewriter("│                                                 │")
        typewriter("│ Items - Found after combat                      │")
        typewriter("│ Use in shop or before/during encounters         │")
        typewriter("│                                                 │")
        typewriter("└─────────────────────────────────────────────────┘")
        time.sleep(3)
        
        choice = input_handler.ask_choice(
            [{"label": "Continue", "value": "1"}],
            "> "
        )
        
        typewriter("\n┌─ CHAPTER 4: PROGRESSION ──────────────────────────┐")
        typewriter("│                                                 │")
        typewriter("│ Your goal: Clear 3 Tiers and defeat the Boss    │")
        typewriter("│                                                 │")
        typewriter("│ Each tier gets harder:                          │")
        typewriter("│ • Stronger enemies                              │")
        typewriter("│ • More challenging questions                    │")
        typewriter("│ • Better rewards                                │")
        typewriter("│                                                 │")
        typewriter("│ You have 15 nodes per tier. Choose your path!   │")
        typewriter("│                                                 │")
        typewriter("└─────────────────────────────────────────────────┘")
        time.sleep(3)
        
        choice = input_handler.ask_choice(
            [{"label": "Continue", "value": "1"}],
            "> "
        )
        
        typewriter("\n┌─ CHAPTER 5: TIPS & TRICKS ────────────────────────┐")
        typewriter("│                                                 │")
        typewriter("│ Pro Tips:                                       │")
        typewriter("│ • Visit shops to stock up on items              │")
        typewriter("│ • Rest nodes restore 30% of your max HP         │")
        typewriter("│ • Gold is useful - don't spend it all           │")
        typewriter("│ • Your mastery tracks knowledge in each subject │")
        typewriter("│ • Achievements unlock special perks             │")
        typewriter("│                                                 │")
        typewriter("│ Good luck, adventurer!                          │")
        typewriter("│                                                 │")
        typewriter("└─────────────────────────────────────────────────┘")
        
        typewriter("\n" + "=" * 60)
        typewriter("        Tutorial Complete! Ready to begin?")
        typewriter("=" * 60)
        
        choice = input_handler.ask_choice(
            [{"label": "Start Game", "value": "yes"}],
            "> "
        )
        
        self.completed = True
        self._save_completion()
        
        typewriter("\nGood luck! The journey begins...\n")
        time.sleep(1)


def get_tutorial():
    """Get or create tutorial instance."""
    return Tutorial()
