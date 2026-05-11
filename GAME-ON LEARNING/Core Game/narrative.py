"""Narrative and flavor text system.

Provides story text, narrative flavor descriptions, tier narratives,
battle scenarios, and branching narrative elements.
"""

import random
import time
from ui import typewriter

# Opening lore shown once at the start of a new run
OPENING_LORE = [
    "The world does not reward the ignorant.",
    "Knowledge is the only weapon that grows stronger the more you use it.",
    "You have entered the Gauntlet — a place where only the learned survive.",
    "Each enemy you face is a test. Each question, a challenge.",
    "Your streak is your power. Your mastery, your armor.",
    "Learn. Fight. Grow. Or fall like all the rest.",
]

# Node transition flavor — shown when moving between nodes
NODE_FLAVOR = {
    "battle": [
        "The ground shifts beneath you. Something stirs.",
        "A shadow crosses your path.",
        "The air grows cold. You are not alone.",
        "You hear footsteps. Heavy ones.",
    ],
    "elite": [
        "The temperature drops sharply.",
        "An oppressive aura fills the corridor.",
        "Even the walls seem to shrink away from what waits ahead.",
        "Your instincts have never been wrong before. Turn back.",
    ],
    "shop": [
        "A warm light flickers ahead.",
        "The smell of something familiar drifts toward you.",
        "Someone has made camp here. They look friendly enough.",
    ],
    "rest": [
        "A rare moment of silence. Take it.",
        "The chaos fades, if only briefly.",
        "Your body knows before your mind does — rest here.",
    ],
    "boss": [
        "This is it.",
        "Everything you have learned has led to this moment.",
        "The ground itself seems to tremble with anticipation.",
        "There is no turning back from here.",
    ],
    "maze": [
        "The walls hum with a strange energy.",
        "Knowledge is the only map that works in here.",
        "Many have entered. Fewer remember the way out.",
    ],
}

# Mid-run check-in lines based on streak
STREAK_COMMENTARY = [
    (25, "Remarkable. Your streak is the stuff of legend."),
    (15, "You're on fire. The questions bow to you."),
    (10, "Double digits. The enemies grow nervous."),
    (5,  "A solid streak building. Keep it going."),
]

# Wrong answer flavor — shown occasionally after wrong answers
WRONG_FLAVOR = [
    "The gap in your knowledge costs you.",
    "A weakness revealed. Remember this.",
    "Your enemy smiles. That answer was wrong.",
    "Not every battle is won with force.",
    "The correct answer was there. It will return.",
]

# Correct answer flavor — shown occasionally
CORRECT_FLAVOR = [
    "Knowledge applied. Power gained.",
    "Your mastery grows.",
    "The right answer at the right time.",
    "Understanding is its own form of strength.",
]

# Tier transition narrative
TIER_NARRATIVE = {
    2: [
        "The gauntlet deepens. Enemies grow bolder.",
        "Tier 2. The comfortable days are behind you.",
        "Whatever was testing you before — it's taking you seriously now.",
    ],
    3: [
        "This is the final stretch.",
        "Tier 3. Only the most prepared reach this point.",
        "The boss can sense you approaching. Prove you belong here.",
    ],
}

def show_opening(player_name, class_name):
    """Display opening narrative for a new run."""
    typewriter(f"\n{player_name}.")
    time.sleep(0.8)
    typewriter(f"A {class_name} enters the Gauntlet.\n")
    time.sleep(0.5)
    for line in OPENING_LORE:
        typewriter(f"  {line}")
        time.sleep(0.4)
    typewriter("")
    time.sleep(1)

def show_node_flavor(node_type):
    """Show a flavor line before entering a node."""
    lines = NODE_FLAVOR.get(node_type, [])
    if lines:
        typewriter(f"\n  {random.choice(lines)}")
        time.sleep(0.8)

def show_streak_comment(streak):
    """Show commentary when streak hits milestones."""
    for threshold, comment in STREAK_COMMENTARY:
        if streak == threshold:
            typewriter(f"\n  [{comment}]")
            time.sleep(0.5)
            break

def show_wrong_flavor():
    """Occasionally show flavor after wrong answers."""
    if random.random() < 0.4:
        typewriter(f"\n  {random.choice(WRONG_FLAVOR)}")
        time.sleep(0.3)

def show_correct_flavor():
    """Occasionally show flavor after correct answers."""
    if random.random() < 0.3:
        typewriter(f"\n  {random.choice(CORRECT_FLAVOR)}")
        time.sleep(0.3)

def show_tier_narrative(tier):
    """Show narrative when a new tier is reached."""
    lines = TIER_NARRATIVE.get(tier, [])
    if lines:
        typewriter(f"\n  {random.choice(lines)}")
        time.sleep(1)

def show_death_narrative(player_name, battles_won, longest_streak):
    """Show a personalized death message."""
    typewriter(f"\n  {player_name} has fallen.")
    time.sleep(0.5)
    if battles_won == 0:
        typewriter("  The Gauntlet claimed another unprepared soul.")
    elif longest_streak >= 10:
        typewriter(f"  A streak of {longest_streak}. The Gauntlet remembers those who reached that far.")
    else:
        typewriter(f"  {battles_won} battles won. Not enough.")
    time.sleep(1)

def show_victory_narrative(player_name, battles_won, longest_streak):
    """Show victory narrative after boss defeat."""
    typewriter(f"\n  {player_name}.")
    time.sleep(0.8)
    typewriter("  The Gauntlet is silent.")
    time.sleep(0.5)
    typewriter(f"  {battles_won} battles. A streak of {longest_streak}.")
    time.sleep(0.5)
    typewriter("  Knowledge was your weapon.")
    time.sleep(0.5)
    typewriter("  You proved it.")
    time.sleep(1)

