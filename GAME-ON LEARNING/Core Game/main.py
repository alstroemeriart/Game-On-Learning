"""Main game loop and character creation.

Handles game initialization, character creation, the main game loop,
turn-based combat orchestration, item/shop interactions, and run progression.
"""

import os
import random
import time
from Spawns import MainCharacter
from progression import create_skill_pool
from combatSystem import (
    player_turn,
    enemy_turn,
    process_status_effects,
    display_entity_stats,
    ESCAPED, WIN, DEATH
)
from ui import (
    title_screen, game_over_screen, typewriter, hp_bar,
    input_handler, EventBus
)
from enemyPool import generate_random_enemy, scale_enemy
from learningEngine import (
    LearningEngine, quiz_trial, combat_item_drop, validate_notes
)
from shop import shop
from saveLoad import save_game, load_game, delete_save, save_exists, load_completed_run
from config import (
    load_config, get_notes_paths, get_save_path, get_last_run_path
)
from achievements import (
    load_achievements, save_achievements, check_achievements,
    print_achievements
)
bus = EventBus()
from narrative import (show_opening, show_node_flavor,
                       show_tier_narrative, show_death_narrative,
                       show_victory_narrative)
from bestiary import get_bestiary
from tutorial import get_tutorial

CONFIG = load_config()
NOTE_PATHS = get_notes_paths(CONFIG)
SAVE_PATH = get_save_path(CONFIG)
LAST_RUN_PATH = get_last_run_path(CONFIG)

# Difficulty assignment per question type
NOTE_DIFFICULTIES = {
    "TF": 1,
    "MC": 2,
    "AR": 2,
    "ID": 3,
    "FB": 2,
    "OD": 3,
}

# Validate and load notes
engine = LearningEngine()
for qtype, path in NOTE_PATHS.items():
    validate_notes(path, qtype)
    engine.load_notes(path, qtype=qtype, difficulty=NOTE_DIFFICULTIES.get(qtype, 1))

def emit_player_stats(player):
    """Emit player stats update to the GUI bus.
    
    Sends a game event to update all GUI elements displaying player stats
    (HP bar, resources, etc). Called after combat actions and resource changes.
    
    Args:
        player: The MainCharacter instance to broadcast updates for.
    """
    bus.game_event("player_stats", player=player)

class PathNode:
    """Represents a single node on the run map.
    
    Attributes:
        node_type (str): Type of node (battle, elite, shop, maze, rest, boss, trial, unknown)
        tier (int): Difficulty tier of the node (1-3). Elite/Boss nodes are tier+1.
    """
    def __init__(self, node_type, tier=1):
        """Initialize a PathNode with a type and tier.
        
        Args:
            node_type (str): The type of encounter at this node
            tier (int, optional): Difficulty tier. Defaults to 1.
        """
        self.node_type = node_type
        self.tier = tier

    def describe(self):
        """Return a random atmospheric description for this node type.
        
        Returns:
            str: A flavor-text description of what the player encounters at this node.
        """
        descriptions = {
            "battle": [
                "A hostile presence lurks ahead...",
                "You hear movement in the shadows.",
                "Something is waiting around the corner.",
                "The path ahead smells of danger.",
            ],
            "elite": [
                "A powerful elite enemy blocks your path.",
                "The air feels heavier here. Something strong is near.",
                "A fearsome silhouette stands between you and the exit.",
                "Your instincts scream at you to turn back.",
            ],
            "shop": [
                "A wandering merchant appears.",
                "The smell of a campfire and commerce drifts toward you.",
                "Someone has set up a makeshift stall ahead.",
            ],
            "maze": [
                "A mysterious maze entrance glows faintly.",
                "A labyrinth stretches before you, humming with energy.",
                "The walls here seem to shift when you're not looking.",
            ],
            "rest": [
                "A quiet sanctuary for recovery.",
                "A warm alcove offers a moment of peace.",
                "The fighting fades here. You can breathe.",
            ],
            "boss": [
                "An overwhelming darkness fills the corridor...",
                "The ground trembles faintly with each step forward.",
                "Everything here feels wrong. Something enormous is ahead.",
            ],
        }
        options = descriptions.get(self.node_type, ["An unknown path."])
        return random.choice(options)

def draw_run_map(nodes_cleared, current_tier, run_log, next_node_type=None):
    """Display a visual map of run progression — sends to GUI map label via bus.
    
    Creates and displays a compact ASCII map of the player's run so far, including
    past nodes, current position, and the next node if known. Updates both the
    GUI via event bus and the terminal narrative log.
    
    Args:
        nodes_cleared (int): Total number of nodes cleared in this run
        current_tier (int): Current difficulty tier (1-3)
        run_log (list): History of run events as strings
        next_node_type (str, optional): Type of the upcoming node. Defaults to None.
    
    Side effects:
        - Emits 'enemy_clear' and 'map_update' events to the GUI bus
        - Prints formatted map to terminal via typewriter()
    """
    icons = {
        "battle": "[B]",
        "elite":  "[E]",
        "shop":   "[S]",
        "maze":   "[M]",
        "rest":   "[R]",
        "boss":   "[!]",
        "unknown":"[?]",
    }
    bus.game_event("enemy_clear")

    past_nodes = []
    for entry in run_log:
        if "Defeated enemy" in entry:
            past_nodes.append("battle")
        elif "ELITE" in entry:
            past_nodes.append("elite")
        elif "shop" in entry.lower():
            past_nodes.append("shop")
        elif "maze" in entry.lower():
            past_nodes.append("maze")
        elif "Rested" in entry:
            past_nodes.append("rest")
        elif "BOSS" in entry:
            past_nodes.append("boss")
        elif "Fled" in entry:
            past_nodes.append("battle")

    map_line = ""
    for node_type in past_nodes:
        map_line += f"{icons.get(node_type, '[?]')}--"
    map_line += "[*]"
    if next_node_type:
        map_line += f"--{icons.get(next_node_type, '[?]')}?"

    # Push the compact map string to the GUI map label
    bus.game_event("map_update", 
                   text=f"Tier {current_tier}/3 | Node {nodes_cleared}   {map_line}",
                   history=past_nodes,
                   pending=[next_node_type] if next_node_type else [])

    # Also log a human-readable version in the narrative log
    typewriter(f"\n{'='*50}")
    typewriter(f"  RUN MAP  |  Tier {current_tier}/3  |  Node {nodes_cleared}")
    typewriter(f"{'='*50}")
    typewriter(f"\n  {map_line}")
    typewriter("\n  Legend: [B]attle [E]lite [S]hop [M]aze [R]est [!]Boss [*]You")
    tier_fill = "#" * (nodes_cleared % 5) + "-" * (5 - (nodes_cleared % 5))
    nodes_to_next = 5 - (nodes_cleared % 5)
    typewriter(f"\n  Tier progress: [{tier_fill}] {nodes_to_next} nodes to Tier {min(current_tier+1, 3)}")
    typewriter(f"{'='*50}\n")
    time.sleep(1)

def _check_mastery_bonus_node(player):
    """Check if player has mastered any skill category (15+ mastery).
    
    Used to determine if special bonus trial nodes can appear in the run.
    
    Args:
        player: The MainCharacter instance
        
    Returns:
        bool: True if any mastery category >= 15, False otherwise
    """
    for _, val in player.mastery.items():
        if val >= 15:
            return True
    return False

def generate_next_nodes(current_tier, player, nodes_cleared=0):
    """Generate 2-3 random node options for the player to choose from.
    
    Uses weighted probability to ensure bosses only appear late in the run (node 10+, tier 3+).
    Bonus trial nodes can appear if player has mastered a skill (mastery >= 15).
    Elite and Boss nodes are scaled to tier+1 difficulty.
    
    Args:
        current_tier (int): Current difficulty tier (1-3)
        player: The MainCharacter instance (used to check mastery bonuses)
        nodes_cleared (int, optional): Number of nodes cleared so far. Defaults to 0.
        
    Returns:
        list: 2-3 PathNode objects representing the available next choices
    """
    node_count = random.choice([2, 3])
    nodes = []

    for _ in range(node_count):
        boss_eligible = current_tier >= 3 and nodes_cleared >= 10

        if boss_eligible:
            types = ["battle", "elite", "shop", "maze", "rest", "boss"]
            weights = [35, 15, 15, 15, 10, 10]
        else:
            types = ["battle", "elite", "shop", "maze", "rest"]
            weights = [50, 10, 15, 15, 10]

        node_type = random.choices(types, weights=weights, k=1)[0]
        tier = current_tier
        if node_type in ("elite", "boss"):
            tier += 1

        if _check_mastery_bonus_node(player) and random.random() < 0.08:
            nodes.append(PathNode("trial", tier=current_tier))

        nodes.append(PathNode(node_type, tier=tier))

    return nodes

def choose_next_path(current_tier, player, nodes_cleared=0):
    """Present player with node choices and handle meta-actions (character sheet, save/load).
    
    Displays 2-3 generated node options with atmospheric descriptions. Allows player to:
    - View character sheet (c)
    - Save game (s) 
    - Load game (l) [displays info about resuming mid-run]
    - Choose a node (1-3)
    
    Args:
        current_tier (int): Current difficulty tier (1-3)
        player: The MainCharacter instance
        nodes_cleared (int, optional): Number of nodes cleared so far. Defaults to 0.
        
    Returns:
        PathNode: The selected node, or a new node if player saved/viewed character
    """
    nodes = generate_next_nodes(current_tier, player, nodes_cleared)
    node_descriptions = [f"{node.describe()} ({node.node_type.upper()})" for node in nodes]

    typewriter("\nChoose your next destination:")
    typewriter("(Type 'c' for Character Sheet, 's' to Save, 'l' to Load)")
    time.sleep(0.3)

    for i, description in enumerate(node_descriptions, 1):
        typewriter(f"{i}. {description}")
        time.sleep(0.2)

    while True:
        choice = input_handler.ask_choice(
            [
                {"label": f"{i}. {description}", "value": str(i)}
                for i, description in enumerate(node_descriptions, 1)
            ] + [
                {"label": "Character Sheet", "value": "c"},
                {"label": "Save Game", "value": "s"},
                {"label": "Load Game", "value": "l"},
            ],
            "> ",
        ).strip().lower()

        if choice == "c":
            view_character(player)
            for i, description in enumerate(node_descriptions, 1):
                typewriter(f"{i}. {description}")
            continue

        if choice == "s":
            # Save manually
            run_state = {
                "tier": current_tier,
                "battles_won": getattr(player, "_battles_won", 0),
                "nodes_cleared": nodes_cleared,
            }
            save_game(player, run_state, SAVE_PATH)
            typewriter("\nGame saved!")
            time.sleep(1)
            for i, description in enumerate(node_descriptions, 1):
                typewriter(f"{i}. {description}")
            continue

        if choice == "l":
            typewriter("\nLoading from save...")
            time.sleep(1)
            typewriter("(Cannot load mid-run. Restart the game to load a saved run.)")
            time.sleep(1)
            for i, description in enumerate(node_descriptions, 1):
                typewriter(f"{i}. {description}")
            continue

        if choice.isdigit():
            c = int(choice)
            if 1 <= c <= len(nodes):
                return nodes[c - 1]

        typewriter("Invalid choice. Select a valid number, 'c' for character, 's' to save, or 'l' to load.")

def create_character():
    """Interactive character creation flow with class presets and custom builds.
    
    Prompts player for name and class selection. Offers 6 options:
    1. Berserker (Glass Cannon) - High ATK/CRIT, Low DEF
    2. Duelist (Rogue) - High SPD/CRIT, Low ATK  
    3. Sentinel (Tank) - High HP/DEF, Low SPD
    4. Arcanist (Caster) - High WIS/CRIT, Learning focus
    5. Gambler (Unpredictable) - Random stats, high variance
    6. Custom Build - Manual stat point allocation
    
    Debug: Code '143' enables God Mode for playtesting.
    
    Returns:
        MainCharacter: Initialized player character with class traits set
    """
    typewriter("\n=== Character Creation ===")
    typewriter("Enter your character name:")
    name = input_handler.ask("> ").strip() or "Hero"

    typewriter("\nChoose a GOL Class:")
    typewriter("1. Berserker (Glass Cannon) - High ATK, Low DEF")
    typewriter("2. Duelist (Speedy Rogue) - High SPD, High CRIT, Low ATK")
    typewriter("3. Sentinel (Average Sustain) - High HP, High DEF, Low SPD")
    typewriter("4. Arcanist (Learning Focus) - High WIS, High Crit")
    typewriter("5. Gambler (High Risk/Reward) - Variance in all stats")
    typewriter("6. Custom Build - Distribute your own stat points")

    choice = input_handler.ask("> ").strip()

    if choice == "1":
        player = MainCharacter(name, 30, 15, 5, 10, 5, 0.3, 2.5)
        player.class_name = "Berserker"
        player.class_passive = "bloodlust"
        return player
    elif choice == "2":
        player = MainCharacter(name, 50, 5, 10, 10, 5, 0.8, 2.5)
        player.class_name = "Duelist"
        player.class_passive = "momentum"
        return player
    elif choice == "3":
        player = MainCharacter(name, 80, 5, 15, 5, 5, 0.3, 1.5)
        player.class_name = "Sentinel"
        player.class_passive = "fortress"
        return player
    elif choice == "4":
        player = MainCharacter(name, 40, 5, 5, 7, 30, 1, 3.0)
        player.class_name = "Arcanist"
        player.class_passive = "insight"
        return player
    elif choice == "5":
        player = MainCharacter(name,
            random.randint(30, 100), random.randint(5, 40),
            random.randint(2, 15),  random.randint(3, 20),
            random.randint(5, 25),  random.randint(0, 1),
            random.uniform(0.5, 5))
        player.class_name = "Gambler"
        player.class_passive = "luck"
        return player
    elif choice == "6":
        return custom_build(name)
    elif choice == "143":
        typewriter("Welcome home, Rynier. Let's get you ready for testing.")
        typewriter("🔧 AUTO-PLAY DEBUG MODE ENABLED 🔧")
        typewriter("Auto-playing: combat, navigation, and quiz questions.")
        player = MainCharacter(name, 999, 999, 999, 999, 999, 1, 10)
        player.class_name = "God Mode"
        player.debug_mode = True
        return player
    else:
        typewriter("Invalid choice. Defaulting to Berserker.")
        player = MainCharacter(name, 30, 25, 2, 10, 5, 0.3, 2.5)
        player.class_name = "Berserker"
        player.class_passive = "bloodlust"
        return player

def custom_build(name):
    """Allow player to manually allocate 100 stat points across character stats.
    
    Distributes points to:
    - HP (base 20)
    - ATK (base 5)
    - DEF (base 5) 
    - SPD (base 5)
    - WISDOM (base 5)
    - CRIT_CHANCE (converted from points to percentage: points/100)
    - CRIT_MULTIPLIER (converted from points: points/10)
    
    Args:
        name (str): The character's name
        
    Returns:
        MainCharacter: Newly created character with custom stat distribution
    """
    typewriter("\nYou have 100 stat points to distribute.")
    points = 100

    def allocate(stat_name):
        nonlocal points
        while True:
            typewriter(f"{stat_name} (Remaining points: {points}):")
            value = input_handler.ask("> ")
            try:
                value = int(value)
                if 0 <= value <= points:
                    points -= value
                    return value
            except ValueError:
                pass
            typewriter("Invalid amount.")

    max_hp        = 20 + allocate("HP")
    atk           = 5  + allocate("ATK")
    defense       = 5  + allocate("DEF")
    spd           = 5  + allocate("SPD")
    wisdom        = 5  + allocate("WISDOM")
    crit_chance   = allocate("CRIT_CHANCE") / 100
    crit_mult     = allocate("CRIT_MULTIPLIER") / 10

    player = MainCharacter(name, max_hp, atk, defense, spd, wisdom, crit_chance, crit_mult)
    player.class_name = "Custom"
    return player

def view_character(player):
    """Display full character stats and progression."""
    typewriter(f"\n{'='*40}")
    typewriter(f"  {player.name}  |  Level {player.lvl}")
    typewriter(f"{'='*40}")
    typewriter(f"HP:      {hp_bar(player.hp, player.max_hp)}")
    typewriter(f"Focus:   {hp_bar(player.focus, player.max_focus, length=10)}")
    typewriter(f"Shield:  {player.shield}")
    typewriter(f"Gold:    {player.gold}")
    typewriter(f"EXP:     {player.exp}/{player.xp_to_next}")
    typewriter(f"\nStats:")
    typewriter(f"  ATK: {player.atk}  DEF: {player.defense}")
    typewriter(f"  SPD: {player.spd}  WIS: {player.wisdom}")
    typewriter(f"  CRIT: {int(player.crit_chance*100)}%  x{player.crit_multiplier}")
    typewriter(f"\nMastery:")
    for q_type, val in player.mastery.items():
        next_ms = ((val // 5) + 1) * 5
        category = {"TF": "True/False", "MC": "Multi-Choice",
                    "AR": "Arithmetic", "ID": "Identification"}.get(q_type, q_type)
        typewriter(f"  {category}: {val} (next skill at {next_ms})")
    typewriter(f"\nSkills:")
    if hasattr(player, "skills") and player.skills:
        for skill in player.skills:
            status = "UNLOCKED" if skill.unlocked else f"locked ({skill.tree} mastery 5)"
            typewriter(f"  {skill.name} [{skill.tree}] — {status}")
    else:
        typewriter("  No skills loaded.")
    typewriter(f"\nInventory ({len(player.inventory)} items):")
    if player.inventory:
        for item in player.inventory:
            desc = getattr(item, "description", "")
            typewriter(f"  {item.name} — {desc}")
    else:
        typewriter("  Empty.")
    typewriter(f"\nStreak: {player.streak} (Longest: {player.longest_streak})")
    typewriter(f"Action Points: {player.max_action_points}/turn")
    time.sleep(0.3)
    typewriter("\n(Press Enter to continue...)")
    input_handler.ask("")

class RunStats:
    """Detailed statistics for a completed run."""
    
    def __init__(self, player, run_context, session_stats):
        self.player = player
        self.run_context = run_context
        self.session_stats = session_stats
        self.final_level = player.lvl
        self.final_gold = player.gold
        self.final_hp = player.hp
        self.final_streak = player.streak
        self.longest_streak = player.longest_streak
        self.inventory_count = len(player.inventory)
        self.battles_won = run_context.get("battles_won", 0)
        self.nodes_cleared = run_context.get("nodes_cleared", 0)
        self.beat_boss = run_context.get("beat_boss", False)
        self.xp_earned = player.exp  # This should be tracked separately
    
    def display_detailed_stats(self):
        """Display comprehensive end-of-run statistics."""
        typewriter("\n" + "=" * 60)
        typewriter("                ═══ RUN SUMMARY ═══")
        typewriter("=" * 60)
        
        # Character performance
        typewriter("\n┌─ CHARACTER PERFORMANCE ─────────────────────────────┐")
        typewriter(f"│ Final Level:        {self.final_level:>40} │")
        typewriter(f"│ Battles Won:        {self.battles_won:>40} │")
        typewriter(f"│ Nodes Cleared:      {self.nodes_cleared:>40} │")
        typewriter(f"│ Boss Defeated:      {'YES' if self.beat_boss else 'NO':>40} │")
        typewriter("└────────────────────────────────────────────────────┘")
        
        # Combat statistics
        typewriter("\n┌─ COMBAT STATISTICS ─────────────────────────────────┐")
        typewriter(f"│ Current HP:         {self.final_hp}/{self.player.max_hp:>37} │")
        typewriter(f"│ Final Streak:       {self.final_streak:>40} │")
        typewriter(f"│ Best Streak:        {self.longest_streak:>40} │")
        typewriter("└────────────────────────────────────────────────────┘")
        
        # Learning statistics
        accuracy = self.session_stats.accuracy()
        total_questions = (self.session_stats.correct + 
                          self.session_stats.wrong)
        typewriter("\n┌─ LEARNING STATISTICS ───────────────────────────────┐")
        typewriter(f"│ Questions Answered: {total_questions:>40} │")
        typewriter(f"│ Correct:            {self.session_stats.correct:>40} │")
        typewriter(f"│ Incorrect:          {self.session_stats.wrong:>40} │")
        typewriter(f"│ Accuracy:           {accuracy:>38}% │")
        typewriter("└────────────────────────────────────────────────────┘")
        
        # Rewards
        typewriter("\n┌─ REWARDS ───────────────────────────────────────────┐")
        typewriter(f"│ Gold Earned:        {self.final_gold:>40} │")
        typewriter(f"│ Items Found:        {self.inventory_count:>40} │")
        typewriter("└────────────────────────────────────────────────────┘")
        
        typewriter("\n" + "=" * 60)
        typewriter("\n(Press Enter to continue...)")
        time.sleep(1)


class SessionStats:
    """Tracks learning statistics for the current run."""
    def __init__(self):
        self.correct = 0
        self.wrong = 0
        self.by_type = {t: {"correct": 0, "wrong": 0} for t in ["TF", "MC", "AR", "ID", "FB", "OD"]}

    def record(self, q_type, was_correct):
        if was_correct:
            self.correct += 1
            self.by_type.setdefault(q_type, {"correct": 0, "wrong": 0})["correct"] += 1
        else:
            self.wrong += 1
            self.by_type.setdefault(q_type, {"correct": 0, "wrong": 0})["wrong"] += 1

    def accuracy(self):
        total = self.correct + self.wrong
        return int((self.correct / total) * 100) if total > 0 else 0

    def print_summary(self):
        total = self.correct + self.wrong
        typewriter(f"\n--- Learning Summary ---")
        typewriter(f"  Questions answered: {total}")
        typewriter(f"  Correct: {self.correct} | Wrong: {self.wrong}")
        typewriter(f"  Accuracy: {self.accuracy()}%")
        typewriter(f"\n  By category:")
        for q_type, counts in self.by_type.items():
            t = counts["correct"] + counts["wrong"]
            if t == 0:
                continue
            acc = int((counts["correct"] / t) * 100)
            bar = "#" * (acc // 10) + "-" * (10 - acc // 10)
            category = {"TF": "True/False", "MC": "Multi-Choice",
                        "AR": "Arithmetic", "ID": "Identification",
                        "OD": "Ordering"}.get(q_type, q_type)
            typewriter(f"  {category:15} [{bar}] {acc}% ({t} answered)")


KEYBOARD_SHORTCUTS = {
    "I": ("Inventory", "Show item count and list"),
    "Esc": ("Pause Menu", "Open pause menu (hint: you can't escape in combat!)"),
    "?": ("Help", "Show keyboard shortcuts"),
}


def print_keyboard_shortcuts():
    """Display available keyboard shortcuts."""
    typewriter("\n" + "=" * 50)
    typewriter("      KEYBOARD SHORTCUTS")
    typewriter("=" * 50)
    for key, (name, desc) in KEYBOARD_SHORTCUTS.items():
        typewriter(f"\n{key:>5} - {name}")
        typewriter(f"        {desc}")
    typewriter("\n" + "=" * 50)
    typewriter("\n(Press Enter to close...)")


def start_combat(player, learning_engine, tier, nodes_cleared=1, bestiary=None):
    """Full combat loop handling turns, status effects, escape, and victory.
    
    Generates a random enemy scaled to tier/node progression, then runs repeated
    turns of combat. Each turn:
    1. Display entity stats
    2. Player takes action (answer question, use item, escape)
    3. Process player status effects
    4. Check for victory/defeat
    5. Enemy takes turn
    6. Process enemy status effects
    7. Check for victory/defeat
    
    Records enemy encounters in bestiary and tracks flawless victories (no damage taken).
    
    Args:
        player: The MainCharacter instance
        learning_engine: LearningEngine for question generation
        tier (int): Difficulty tier for enemy scaling
        nodes_cleared (int, optional): Nodes cleared so far (affects scaling). Defaults to 1.
        bestiary (optional): Bestiary instance to record encounters. Defaults to None.
        
    Returns:
        tuple: (result, no_damage) where:
            - result: ESCAPED, WIN, or DEATH (constants from combatSystem)
            - no_damage: bool, True if player took 0 damage in combat
    """
    enemy = generate_random_enemy(tier=tier)
    enemy = scale_enemy(enemy, nodes_cleared, tier)
    if bestiary:
        bestiary.record_encounter(enemy.name)
    typewriter(f"\nA wild {enemy.name} appears!")
    time.sleep(1)

    hp_before = player.hp

    while True:
        display_entity_stats(player)
        display_entity_stats(enemy)
        emit_player_stats(player)

        result = player_turn(player, enemy, learning_engine)
        emit_player_stats(player)

        if result == ESCAPED:
            typewriter("You successfully escaped the battle!")
            time.sleep(1)
            return ESCAPED, False

        if enemy.hp <= 0:
            typewriter(f"{enemy.name} defeated!")
            if bestiary:
                bestiary.record_kill(enemy.name)
            time.sleep(1)
            typewriter(f"\n--- Battle Summary ---")
            typewriter(f"HP remaining: {player.hp}/{player.max_hp}")
            typewriter(f"Streak: {player.streak} | Focus: {player.focus}/{player.max_focus}")
            no_damage = (player.hp >= hp_before)
            if no_damage:
                typewriter("Flawless victory! No damage taken.")
            time.sleep(0.5)
            emit_player_stats(player)
            return WIN, no_damage

        if player.hp <= 0:
            typewriter("You were defeated...")
            time.sleep(1)
            return DEATH, False

        process_status_effects(player)
        emit_player_stats(player)

        if enemy.hp <= 0:
            typewriter(f"{enemy.name} defeated!")
            time.sleep(1)
            xp_gain = 20 + (tier * 10)
            player.gain_xp(xp_gain)
            typewriter(f"Gained {xp_gain} XP!")
            emit_player_stats(player)
            return WIN, False

        if player.hp <= 0:
            typewriter("You were defeated...")
            time.sleep(1)
            return DEATH, False

        enemy_turn(enemy, player)
        emit_player_stats(player)
        process_status_effects(enemy)

        if player.hp <= 0:
            typewriter("You were defeated...")
            time.sleep(1)
            return DEATH, False

        if enemy.hp <= 0:
            typewriter(f"{enemy.name} defeated!")
            time.sleep(1)
            xp_gain = 20 + (tier * 10)
            player.gain_xp(xp_gain)
            typewriter(f"Gained {xp_gain} XP!")
            emit_player_stats(player)
            return WIN, False

def random_event(player):
    """Trigger small random events between nodes (~20% chance).
    
    Events include:
    - 7%: Wounded traveler heals 10% HP
    - 6%: Find 5-20 gold
    - 4%: Strange fog reduces streak by 2
    - 3%: Abandoned satchel with random item(s)
    
    Args:
        player: The MainCharacter instance to apply effects to
        
    Side effects:
        - Modifies player HP, gold, streak, or inventory
        - Emits player_stats updates to GUI bus
        - Displays flavor text via typewriter()
    """
    roll = random.random()

    if roll < 0.07:
        typewriter("\nA wounded traveler shares their supplies with you.")
        heal = int(player.max_hp * 0.1)
        player.heal(heal)
        typewriter(f"Recovered {heal} HP.")
        emit_player_stats(player)

    elif roll < 0.13:
        typewriter("\nYou find a small coin pouch on the ground.")
        bonus = random.randint(5, 20)
        player.gold += bonus
        typewriter(f"Found {bonus} gold!")
        emit_player_stats(player)

    elif roll < 0.17:
        typewriter("\nA strange fog rolls in. You feel disoriented.")
        player.streak = max(0, player.streak - 2)
        typewriter("Streak reduced by 2.")
        time.sleep(1)
        emit_player_stats(player)

    elif roll < 0.20:
        typewriter("\nYou stumble upon an abandoned satchel.")
        from learningEngine import random_item_pool
        reward = random_item_pool(num_rewards=1)
        if reward:
            player.inventory.extend(reward)
            for item in reward:
                typewriter(f"Found: {item.name}!")
            emit_player_stats(player)
        time.sleep(1)


def _gui_title_screen(last_run_path):
    """Show title screen with mode-specific handling (GUI vs terminal).
    
    In GUI mode: fires a bus event so the GUI shows the title overlay overlay,
    then blocks until the player clicks a menu option.
    In terminal mode: falls back to the original title_screen().
    
    Args:
        last_run_path (str): Path to last run log file (passed to terminal mode)
        
    Returns:
        str: User's action selection ('continue', 'new', 'load', 'stats', or 'quit')
    """
    from ui import input_handler as _ih
    if not _ih.gui_mode:
        return title_screen(last_run_path)

    bus.game_event("title_screen")
    # The GUI overlay calls input_handler.push_answer(action_str)
    action = _ih.ask("")   # blocks until overlay button pressed
    return action


def _gui_game_over_screen(won=False):
    """Show game-over screen with mode-specific handling (GUI vs terminal).
    
    In GUI mode: fires a bus event so the GUI shows the game-over overlay,
    then blocks until the player clicks Restart or Main Menu.
    In terminal mode: falls back to the original game_over_screen().
    
    Args:
        won (bool, optional): Whether the player won. Defaults to False (loss).
        
    Returns:
        bool: True if player chose to restart, False for main menu
    """
    from ui import input_handler as _ih
    if not _ih.gui_mode:
        return game_over_screen()

    bus.game_event("game_over", won=won)
    raw = _ih.ask("")   # "1" = restart, "2" = main menu
    return raw == "1"


def main_game():
    """Runs a full RPG loop until player dies or beats the boss.
    
    Full game flow:
    1. Load achievements and bestiary
    2. Check for saved run (offer to continue)
    3. Character creation (if new run)
    4. Display intro narrative
    5. Run tier loop (3 tiers total):
       - Generate and present node choices
       - Handle node-specific events (battle, shop, maze, etc.)
       - Update run stats, achievements, UI
    6. Victory/Defeat screen
    
    Handles:
    - Turn-by-turn combat via start_combat()
    - Shop interactions
    - Maze navigation
    - Item drops and rewards
    - Status effect processing
    - Achievement checks
    - Save/load functionality
    - GUI event bus communication
    
    Returns:
        When run ends (player death or boss defeat)
    """

    unlocked_achievements = load_achievements()
    bestiary = get_bestiary()
    session_stats = SessionStats()
    tutorial = get_tutorial()
    run_context = {
        "battles_won": 0,
        "nodes_cleared": 0,
        "beat_boss": False,
        "no_damage_battle": False,
        "visited_shop_broke": False,
    }

    current_tier = 1
    battles_won = 0
    nodes_cleared = 0
    run_log = []
    player = None

    if save_exists(SAVE_PATH):
        typewriter("A saved run was found. Continue? (y/n)")
        if input_handler.ask_choice(
            [
                {"label": "Yes", "value": "y"},
                {"label": "No", "value": "n"},
            ],
            "> ",
        ).strip().lower() == "y":
            pdata, rdata = load_game(SAVE_PATH)
            if pdata and rdata:
                player = restore_player(pdata)
                current_tier = rdata["tier"]
                battles_won = rdata["battles_won"]
                nodes_cleared = rdata["nodes_cleared"]
                run_context["battles_won"] = battles_won
                run_context["nodes_cleared"] = nodes_cleared
                typewriter(f"Welcome back, {player.name}!")
                emit_player_stats(player)
                time.sleep(1)

    if player is None:
        player = create_character()
        player.gold = 50
        player.exp = 0
        player.streak = 0
        player.skills = create_skill_pool()
        engine.wrong_answers.clear()
        choose_run_modifier(player)
        emit_player_stats(player)
        show_opening(player.name, getattr(player, "class_name", "Adventurer"))
        
        # Show tutorial on first run
        if not tutorial.is_completed():
            tutorial.run()
            tutorial._save_completion()

    typewriter("=" * 60)
    typewriter("\nWelcome to the Game-on Learning demo!")
    typewriter("Use knowledge and strategy to defeat enemies and gain rewards.")
    typewriter("Gold earned can be used in the shop to buy aid.")
    typewriter("=" * 60)
    time.sleep(2)
    typewriter("Loading Combat...")
    time.sleep(1)

    typewriter("=== ROGUELITE RUN STARTED ===")
    typewriter("\nYour goal: Clear 3 tiers and defeat the boss.")
    typewriter(f"Current Tier: {current_tier}/3")
    time.sleep(1)

    run_active = True
    while run_active and player.is_alive():

        nodes_cleared += 1

        # Guaranteed boss at node 15
        if nodes_cleared == 15:
            typewriter("\n" + "="*50)
            typewriter("  A darkness unlike anything before stirs ahead.")
            typewriter("  You sense this is where it all ends.")
            typewriter("="*50)
            time.sleep(2)
            next_node = PathNode("boss", tier=current_tier + 1)
        elif nodes_cleared == 1:
            next_node = PathNode("battle", tier=current_tier)
        elif nodes_cleared == 2:
            next_node = PathNode(random.choice(["battle", "rest"]), tier=current_tier)
        else:
            next_node = choose_next_path(current_tier, player)
        
        # Debug mode: auto-choose battles for faster testing
        if getattr(player, "debug_mode", False) and next_node.node_type not in ["battle", "boss", "elite"]:
            # Heavily favor battles to get to boss faster
            if random.random() < 0.8:
                next_node = PathNode("battle", tier=current_tier)
            else:
                next_node = PathNode(random.choice(["rest", "shop"]), tier=current_tier)

        draw_run_map(nodes_cleared, current_tier, run_log, next_node.node_type)
        show_node_flavor(next_node.node_type)
        typewriter(f"You proceed toward: {next_node.node_type.upper()}")
        time.sleep(0.5)

        # ── Battle ────────────────────────────────────────────────────────────
        if next_node.node_type == "battle":
            result, no_damage = start_combat(player, engine, next_node.tier, nodes_cleared, bestiary)
            if no_damage and result == WIN:
                run_context["no_damage_battle"] = True

            if result == DEATH:
                show_death_narrative(player.name, battles_won, player.longest_streak)
                typewriter("\n=== GAME OVER ===")
                run_stats = RunStats(player, run_context, session_stats)
                run_stats.display_detailed_stats()
                _gui_game_over_screen(won=False)
                return

            elif result == ESCAPED:
                typewriter("You escaped the battle — no rewards gained!")
                lost_gold = min(player.gold, random.randint(5, 15))
                player.gold -= lost_gold
                typewriter(f"Running costs you {lost_gold} gold!")
                emit_player_stats(player)
                time.sleep(1)
                run_log.append(f"Node {nodes_cleared}: Fled from battle (lost gold)")
                continue

            else:
                battles_won += 1
                xp_reward = 20 + (next_node.tier * 10)
                gold_reward = 10 + (next_node.tier * 5)
                player.gain_xp(xp_reward)
                gold_earned = player.apply_gold(gold_reward)
                typewriter(f"You gained {xp_reward} XP and {gold_earned} Gold!")
                emit_player_stats(player)

                drop = combat_item_drop(tier=current_tier)
                if drop:
                    player.inventory.append(drop)
                    typewriter(drop.get_drop_message())
                    typewriter(f"  ({getattr(drop, 'description', '')})")
                    emit_player_stats(player)

                run_context["battles_won"] = battles_won
                run_context["nodes_cleared"] = nodes_cleared
                newly = check_achievements(player, run_context, unlocked_achievements)
                for name in newly:
                    typewriter(f"\n*** ACHIEVEMENT UNLOCKED: {name} ***")
                    time.sleep(0.5)
                save_achievements(unlocked_achievements)
                run_log.append(f"Node {nodes_cleared}: Defeated enemy at Tier {current_tier}")
                time.sleep(1)

        # ── Elite ─────────────────────────────────────────────────────────────
        elif next_node.node_type == "elite":
            from enemyPool import generate_random_enemy
            from combatSystem import elite_combat
            elite_enemy = generate_random_enemy(tier=next_node.tier + 1, elite_chance=1.0)
            bestiary.record_encounter(elite_enemy.name)
            result = elite_combat(player, elite_enemy, engine, bestiary)
            emit_player_stats(player)

            if result == DEATH:
                typewriter("\n=== GAME OVER ===")
                run_stats = RunStats(player, run_context, session_stats)
                run_stats.display_detailed_stats()
                _gui_game_over_screen(won=False)
                return

            elif result == ESCAPED:
                typewriter("You escaped the elite — cowardly, but alive.")
                lost_gold = min(player.gold, random.randint(10, 25))
                player.gold -= lost_gold
                typewriter(f"You lost {lost_gold} gold fleeing!")
                emit_player_stats(player)
                time.sleep(1)
                continue

            else:
                battles_won += 1
                xp_reward  = 50 + (current_tier * 10)
                gold_reward = 40 + (current_tier * 10)
                player.max_hp += 5
                typewriter("Permanent +5 Max HP for defeating an elite!")
                player.gain_xp(xp_reward)
                gold_earned = player.apply_gold(gold_reward)
                typewriter(f"You gained {xp_reward} XP and {gold_earned} Gold!")
                emit_player_stats(player)

                drop = combat_item_drop(tier=current_tier)
                if drop:
                    player.inventory.append(drop)
                    typewriter(drop.get_drop_message())
                    typewriter(f"  ({getattr(drop, 'description', '')})")
                    emit_player_stats(player)

                run_context["battles_won"] = battles_won
                run_context["nodes_cleared"] = nodes_cleared
                newly = check_achievements(player, run_context, unlocked_achievements)
                for name in newly:
                    typewriter(f"\n*** ACHIEVEMENT UNLOCKED: {name} ***")
                    time.sleep(0.5)
                save_achievements(unlocked_achievements)
                run_log.append(f"Node {nodes_cleared}: Defeated ELITE at Tier {current_tier}")
                time.sleep(1)

        # ── Boss ──────────────────────────────────────────────────────────────
        elif next_node.node_type == "boss":
            from enemyPool import generate_random_enemy
            from combatSystem import boss_combat
            boss_enemy = generate_random_enemy(tier=3, elite_chance=1.0)
            bestiary.record_encounter(boss_enemy.name)
            boss_enemy.hp     = int(boss_enemy.hp * 2)
            boss_enemy.max_hp = boss_enemy.hp
            boss_enemy.atk    = int(boss_enemy.atk * 1.5)
            result = boss_combat(player, boss_enemy, engine, bestiary)
            emit_player_stats(player)

            if result == DEATH:
                typewriter("\n=== YOU WERE DEFEATED BY THE BOSS ===")
                _gui_game_over_screen(won=False)
                return
            else:
                battles_won += 1
                show_victory_narrative(player.name, battles_won, player.longest_streak)
                typewriter("\n*** BOSS DEFEATED — YOU WIN THE RUN! ***")
                player.gain_xp(200 + current_tier * 20)
                player.apply_gold(100 + current_tier * 20)
                emit_player_stats(player)
                time.sleep(2)
                run_log.append(f"Node {nodes_cleared}: Defeated the BOSS — run complete!")
                run_context["beat_boss"] = True
                run_stats = RunStats(player, run_context, session_stats)
                run_stats.display_detailed_stats()
                break

        # ── Shop ──────────────────────────────────────────────────────────────
        elif next_node.node_type == "shop":
            if player.gold == 0:
                run_context["visited_shop_broke"] = True
            shop(player)
            emit_player_stats(player)
            run_log.append(f"Node {nodes_cleared}: Visited shop (Gold: {player.gold})")

        # ── Maze ──────────────────────────────────────────────────────────────
        elif next_node.node_type == "maze":
            quiz_trial(player, engine)
            emit_player_stats(player)
            run_log.append(f"Node {nodes_cleared}: Completed maze trial")

        # ── Rest ──────────────────────────────────────────────────────────────
        elif next_node.node_type == "rest":
            heal_amount = int(player.max_hp * 0.3)
            player.hp = min(player.max_hp, player.hp + heal_amount)
            typewriter(f"You rest and recover {heal_amount} HP.")
            emit_player_stats(player)
            time.sleep(1)
            run_log.append(f"Node {nodes_cleared}: Rested (+HP)")

        elif next_node.node_type == "trial":
            typewriter("\nA Knowledge Trial appears — a chance to prove your mastery.")
            quiz_trial(player, engine)
            emit_player_stats(player)
            run_log.append(f"Node {nodes_cleared}: Completed Knowledge Trial")

        save_game(player, {
            "tier": current_tier,
            "battles_won": battles_won,
            "nodes_cleared": nodes_cleared,
        }, SAVE_PATH)

        # Between-node random event
        random_event(player)

        # Difficulty scaling & passive recovery
        if nodes_cleared % 5 == 0:
            current_tier = min(current_tier + 1, 3)
            typewriter(f"\n{'='*40}")
            typewriter(f"  TIER {current_tier} REACHED")
            typewriter(f"  Enemies grow stronger from here.")
            typewriter(f"{'='*40}")
            show_tier_narrative(current_tier)
            time.sleep(1.5)

        player.hp = min(player.max_hp, player.hp + int(player.max_hp * 0.05))
        typewriter(f"Current HP: {player.hp}/{player.max_hp}")
        typewriter(f"Gold: {player.gold} | EXP: {player.exp}")
        emit_player_stats(player)
        time.sleep(0.5)

    # ── Run Summary ───────────────────────────────────────────────────────────
    typewriter("\n=== RUN ENDED ===")
    typewriter(f"Battles Won: {battles_won}")
    typewriter(f"Nodes Cleared: {nodes_cleared}")
    typewriter(f"Final Gold: {player.gold}")
    typewriter(f"Highest Streak: {player.longest_streak}")

    if run_log:
        time.sleep(1)
        typewriter("\n--- Run Journal ---")
        for entry in run_log:
            typewriter(f"  {entry}")
            time.sleep(0.05)

    try:
        with open(LAST_RUN_PATH, "w") as f:
            f.write(f"Battles Won: {battles_won}\n")
            f.write(f"Nodes Cleared: {nodes_cleared}\n")
            f.write(f"Highest Streak: {player.longest_streak}\n")
            f.write(f"Final Gold: {player.gold}\n")
            f.write(f"Final Level: {player.lvl}\n")
    except (IOError, OSError):
        pass

    delete_save(SAVE_PATH)

    won = run_context.get("beat_boss", False)
    _gui_game_over_screen(won=won)


def restore_player(pdata):
    """Reconstruct a MainCharacter from saved player data."""
    from items import (HealingPotion, MegaHealingPotion, AttackBoost,
                       DefenseBoost, SpeedBoost, PoisonBomb, FreezeScroll,
                       WeaknessCurse, HintPotion, DoubleGoldCharm, RevivalStone)

    name_to_class = {
        "Healing Potion": HealingPotion,
        "Mega Healing Potion": MegaHealingPotion,
        "Attack Boost": AttackBoost,
        "Defense Boost": DefenseBoost,
        "Speed Boost": SpeedBoost,
        "Poison Bomb": PoisonBomb,
        "Freeze Scroll": FreezeScroll,
        "Weakness Curse": WeaknessCurse,
        "Hint Potion": HintPotion,
        "Double Gold Charm": DoubleGoldCharm,
        "Revival Stone": RevivalStone,
    }

    player = MainCharacter(
        pdata["name"],
        pdata["max_hp"],
        pdata["atk"],
        pdata["defense"],
        pdata["spd"],
        pdata["wisdom"],
        pdata["crit_chance"],
        pdata["crit_multiplier"],
    )
    player.hp              = pdata["hp"]
    player.lvl             = pdata["lvl"]
    player.exp             = pdata["exp"]
    player.xp_to_next      = pdata["xp_to_next"]
    player.gold            = pdata["gold"]
    player.streak          = pdata["streak"]
    player.longest_streak  = pdata["longest_streak"]
    player.focus           = pdata["focus"]
    player.max_focus       = pdata["max_focus"]
    player.mastery         = pdata["mastery"]
    player.max_action_points = pdata["action_points"]
    player.inventory = [
        name_to_class[i["name"]]()
        for i in pdata["inventory"]
        if i["name"] in name_to_class
    ]
    player.class_name   = pdata.get("class_name", "")
    player.class_passive = pdata.get("class_passive", "")
    player.run_modifier  = pdata.get("run_modifier", "")
    player.debug_mode    = pdata.get("debug_mode", False)
    player.skills        = create_skill_pool()
    return player


RUN_MODIFIERS = [
    {
        "name": "Scholar's Burden",
        "description": "All questions are harder, but correct answers deal double damage.",
        "apply": lambda p: setattr(p, "run_modifier", "scholar")
    },
    {
        "name": "Cursed Knowledge",
        "description": "Wrong answers cost 10 HP in addition to streak penalty.",
        "apply": lambda p: setattr(p, "run_modifier", "cursed")
    },
    {
        "name": "Iron Will",
        "description": "You cannot escape any battle. Rewards are 50% higher.",
        "apply": lambda p: setattr(p, "run_modifier", "ironwill")
    },
    {
        "name": "Lucky Start",
        "description": "Begin with a random rare item and 20 extra gold.",
        "apply": lambda p: _apply_lucky_start(p)
    },
    {
        "name": "No modifier",
        "description": "Standard run.",
        "apply": lambda p: setattr(p, "run_modifier", "")
    },
]

def _apply_lucky_start(player):
    from learningEngine import random_item_pool
    bonus = random_item_pool(num_rewards=1)
    player.inventory.extend(bonus)
    player.gold += 20
    player.run_modifier = "lucky"

def choose_run_modifier(player):
    typewriter("\nBefore you begin — choose a run modifier:")
    time.sleep(0.5)
    for i, mod in enumerate(RUN_MODIFIERS, 1):
        typewriter(f"{i}. {mod['name']}")
        typewriter(f"   {mod['description']}")
    while True:
        choice = input_handler.ask_choice(
            [
                {"label": f"{i}. {mod['name']}", "value": str(i)}
                for i, mod in enumerate(RUN_MODIFIERS, 1)
            ],
            "> ",
        ).strip()
        if choice.isdigit() and 1 <= int(choice) <= len(RUN_MODIFIERS):
            selected = RUN_MODIFIERS[int(choice) - 1]
            selected["apply"](player)
            typewriter(f"\nModifier selected: {selected['name']}")
            time.sleep(1)
            return
        typewriter("Invalid choice.")


def _gui_main_loop():
    """
    Top-level loop that replaces the terminal while-loop in __main__.
    Runs entirely through the GUI — title screen is an overlay,
    game-over is an overlay, everything stays in the window.
    """
    global CONFIG, NOTE_PATHS, SAVE_PATH, LAST_RUN_PATH
    while True:
        action = _gui_title_screen(LAST_RUN_PATH)

        if action == "start":
            main_game()
            # After main_game() returns the game-over overlay has already
            # been shown and dismissed — loop back to title.

        elif action == "practice":
            from learningEngine import practice_mode
            practice_mode(engine)

        elif action == "last_run":
            pdata, rdata = load_completed_run(SAVE_PATH)
            if pdata and rdata:
                player = restore_player(pdata)
                typewriter("\n=== LAST COMPLETED RUN ===")
                typewriter(f"Character: {player.name} ({pdata.get('class_name', 'Unknown')})")
                typewriter(f"Final Level: {player.lvl}")
                typewriter(f"Final Gold: {player.gold}")
                typewriter(f"Longest Streak: {player.longest_streak}")
                typewriter(f"Tier Reached: {rdata['tier']}/3")
                typewriter(f"Battles Won: {rdata['battles_won']}")
                typewriter(f"Nodes Cleared: {rdata['nodes_cleared']}")
                typewriter(f"\nPress Enter to return to menu...")
                input_handler.ask("")
            else:
                typewriter("\nNo completed run found.")
                time.sleep(2)

        elif action == "achievements":
            unlocked = load_achievements()
            print_achievements(unlocked)
            typewriter("\n(Press Enter to return to menu...)")
            input_handler.ask("")

        elif action == "reconfigure":
            from config import setup_wizard, CONFIG_FILE
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
            CONFIG = setup_wizard()
            NOTE_PATHS = get_notes_paths(CONFIG)
            SAVE_PATH  = get_save_path(CONFIG)
            LAST_RUN_PATH = get_last_run_path(CONFIG)
            engine.questions.clear()
            engine.wrong_answers.clear()
            for qtype, path in NOTE_PATHS.items():
                validate_notes(path, qtype)
                engine.load_notes(path, qtype=qtype,
                                  difficulty=NOTE_DIFFICULTIES.get(qtype, 1))
            typewriter("Notes reloaded. Returning to menu...")
            time.sleep(1)

        elif action == "exit":
            import sys
            sys.exit(0)


if __name__ == "__main__":
    from gui import launch_gui
    launch_gui(_gui_main_loop, last_run_path=LAST_RUN_PATH)
else:
    # Terminal fallback
    while True:
        action = title_screen(LAST_RUN_PATH)
        if action == "start":
            main_game()
            restart = game_over_screen()
            if not restart:
                break
        elif action == "practice":
            from learningEngine import practice_mode
            practice_mode(engine)
        elif action == "achievements":
            unlocked = load_achievements()
            print_achievements(unlocked)
            input("\nPress Enter to return to menu...")
        elif action == "reconfigure":
            from config import setup_wizard, CONFIG_FILE
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
            CONFIG = setup_wizard()
            NOTE_PATHS  = get_notes_paths(CONFIG)
            SAVE_PATH   = get_save_path(CONFIG)
            LAST_RUN_PATH = get_last_run_path(CONFIG)
            engine.questions.clear()
            engine.wrong_answers.clear()
            for qtype, path in NOTE_PATHS.items():
                validate_notes(path, qtype)
                engine.load_notes(path, qtype=qtype,
                                  difficulty=NOTE_DIFFICULTIES.get(qtype, 1))
            typewriter("Notes reloaded. Returning to menu...")
            time.sleep(1)
        elif action == "exit":
            break
