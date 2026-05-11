"""Compact console version of the Educational RPG.

This file keeps the main systems from the full project in one place:
- question file loading
- turn based combat
- map/node progression
- shop, rest, trial, save/load

It is intentionally written in a simple, C++-friendly style: small data
classes, plain functions, and direct console input/output.
"""

from __future__ import annotations

import json
import os
import random
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field, fields
from typing import TypeVar


BASE_DIR = os.path.dirname(__file__)
T = TypeVar("T")
SAVE_FILE = os.path.join(BASE_DIR, "compact_save.json")
QUESTION_FILES = {
    "TF": "notes/TorF.txt",
    "MC": "notes/MCQ.txt",
    "AR": "notes/Math.txt",
    "ID": "notes/Identify.txt",
    "FB": "notes/FillBlanks.txt",
    "OD": "notes/OD.txt",
}
QUESTION_DIFFICULTY = {"TF": 1, "MC": 2, "AR": 2, "ID": 3, "FB": 2, "OD": 3}
NODE_TYPES = ["battle", "elite", "shop", "trial", "rest"]
TEXT_SPEED = 0.015
TEXT_SPEEDS = {"instant": 0.0, "fast": 0.005, "normal": 0.015, "slow": 0.035}
ANIMATIONS_ON = True
NODE_ICONS = {"battle": "[B]", "elite": "[E]", "shop": "[S]", "trial": "[T]", "rest": "[R]", "boss": "[!]"}

SKILLS = {
    "TF": ("Truth Guard", "Start battles with +5 shield."),
    "MC": ("Eliminate One", "Removes one wrong multiple-choice option."),
    "AR": ("Precision", "Arithmetic mastery adds extra attack damage."),
    "ID": ("Recall", "Identification mastery improves healing."),
    "FB": ("Composure", "First wrong answer in battle does not break streak."),
    "OD": ("Tactical Read", "Ordering mastery can dodge the next enemy attack."),
}

ACHIEVEMENTS = {
    "First Victory": "Win your first battle.",
    "Node Walker": "Clear 5 nodes.",
    "Elite Breaker": "Defeat an elite.",
    "Scholar Streak": "Reach a streak of 10.",
    "Master Student": "Reach 10 mastery in any question type.",
    "Boss Clear": "Defeat the final boss.",
}

CLASS_BUILDS = [
    ("Berserker", "bloodlust", 70, 14, 5, 4, 0.12, 5, "gains ATK after correct answers"),
    ("Duelist", "momentum", 55, 11, 4, 9, 0.25, 5, "correct answers boost next crit chance"),
    ("Arcanist", "insight", 50, 9, 4, 5, 0.10, 25, "gains extra focus from correct answers"),
    ("Sentinel", "fortress", 90, 9, 9, 2, 0.08, 5, "wrong answers grant shield"),
]

RUN_MODIFIERS = [
    ("Standard Run", "", "no modifier"),
    ("Scholar's Burden", "scholar", "correct attacks deal double damage"),
    ("Cursed Knowledge", "cursed", "wrong answers also cost 10 HP"),
    ("Iron Will", "ironwill", "cannot escape, but combat rewards are higher"),
]


TITLE_ART = r"""
  ____                        ___        _                           _
 / ___| __ _ _ __ ___   ___  / _ \ _ __ | |     ___  __ _ _ __ _ __ (_)_ __   __ _
| |  _ / _` | '_ ` _ \ / _ \| | | | '_ \| |    / _ \/ _` | '__| '_ \| | '_ \ / _` |
| |_| | (_| | | | | | |  __/| |_| | | | | |___|  __/ (_| | |  | | | | | | | | (_| |
 \____|\__,_|_| |_| |_|\___| \___/|_| |_|_____\___|\__,_|_|  |_| |_|_|_| |_|\__, |
                                                                               |___/
"""


def type_text(text: str = "", speed: float = TEXT_SPEED, end: str = "\n") -> None:
    """Print text one character at a time; easy to replace with cout loops in C++."""
    for char in text:
        print(char, end="", flush=True)
        if speed > 0:
            time.sleep(speed)
    print(end=end, flush=True)


def sleep_anim(seconds: float) -> None:
    if ANIMATIONS_ON and TEXT_SPEED > 0:
        time.sleep(seconds)


def loading(message: str, steps: int = 3) -> None:
    print(message, end="", flush=True)
    if not ANIMATIONS_ON or TEXT_SPEED == 0:
        print()
        return
    for _ in range(steps):
        time.sleep(0.25)
        print(".", end="", flush=True)
    print()


def divider(title: str = "") -> None:
    line = "=" * 58
    if not title:
        print(line)
        return
    print("\n" + line)
    type_text(f"  {title}", 0.005)
    print(line)


def flash_message(message: str, repeats: int = 2) -> None:
    if not ANIMATIONS_ON or TEXT_SPEED == 0:
        type_text(message)
        return
    for _ in range(repeats):
        print(f"\r{message}", end="", flush=True)
        time.sleep(0.18)
        print("\r" + " " * len(message), end="", flush=True)
        time.sleep(0.10)
    print(f"\r{message}")


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def show_title() -> None:
    clear_screen()
    print(TITLE_ART)
    type_text("        A Python-Based Educational RPG - Compact Console Build", 0.01)
    type_text("        Answer. Battle. Learn. Survive the node path.", 0.01)
    print("=" * 78)


def pause() -> None:
    input("\nPress Enter to continue...")


def set_text_speed() -> None:
    global ANIMATIONS_ON, TEXT_SPEED
    while True:
        print("\nSettings:")
        print("1. Text Speed")
        print(f"2. Animations: {'On' if ANIMATIONS_ON else 'Off'}")
        print("0. Back")
        choice = ask("> ", ["0", "1", "2"])
        if choice == "0":
            return
        if choice == "2":
            ANIMATIONS_ON = not ANIMATIONS_ON
            type_text(f"Animations {'enabled' if ANIMATIONS_ON else 'disabled'}.")
            continue
        options = list(TEXT_SPEEDS)
        print_numbered(options, lambda name: f"{name.title()} ({TEXT_SPEEDS[name]}s)")
        index = choose_index("> ", len(options))
        if index is None:
            continue
        TEXT_SPEED = TEXT_SPEEDS[options[index]]
        type_text(f"Text speed set to {options[index]}.")


def show_help() -> None:
    print("\n=== Help / Controls ===")
    print("Title Menu: start, load, practice, achievements, settings, exit.")
    print("Node Menu: choose a path number, or use:")
    print("  ? = help")
    print("  c = character sheet")
    print("  i = inventory")
    print("  b = bestiary")
    print("  a = achievements")
    print("  t = text/settings")
    print("  s = save")
    print("  q = save and quit")
    print("Combat: answer questions to attack, use items, spend focus, or use mastery skills.")
    print("Tip: mastery skills unlock at 5 correct answers in a question type.")
    pause()


def ask(prompt: str, valid: list[str] | None = None) -> str:
    while True:
        value = input(prompt).strip()
        if valid is None or value.lower() in valid:
            return value
        type_text("Invalid choice.")


def choose_index(prompt: str, count: int) -> int | None:
    """Ask for a 1-based option number and return a 0-based index."""
    raw = ask(prompt)
    if raw.lower() in ("0", "b", "back", "cancel"):
        return None
    if raw.isdigit() and 1 <= int(raw) <= count:
        return int(raw) - 1
    type_text("Invalid choice. Enter a number, or 0 to cancel.")
    return None


def print_numbered(items: Sequence[T], label_func: Callable[[T], str] | None = None) -> None:
    for i, item in enumerate(items, 1):
        label = label_func(item) if label_func else str(item)
        print(f"{i}. {label}")


def confirm(prompt: str) -> bool:
    return ask(f"{prompt} (y/n)> ", ["y", "n"]) == "y"


def bar(current: int, maximum: int, size: int = 20) -> str:
    filled = int(size * max(0, current) / max(1, maximum))
    return "[" + "#" * filled + "-" * (size - filled) + f"] {current}/{maximum}"


def animated_bar(label: str, current: int, maximum: int, size: int = 20) -> None:
    if not ANIMATIONS_ON or TEXT_SPEED == 0:
        print(f"{label}: {bar(current, maximum, size)}")
        return
    filled = int(size * max(0, current) / max(1, maximum))
    print(f"{label}: [", end="", flush=True)
    for i in range(size):
        print("#" if i < filled else "-", end="", flush=True)
        time.sleep(0.008)
    print(f"] {current}/{maximum}")


def animate_map(map_text: str) -> None:
    print("Map: ", end="", flush=True)
    for char in map_text:
        print(char, end="", flush=True)
        if ANIMATIONS_ON and TEXT_SPEED > 0 and char in "-[]!*":
            time.sleep(0.025)
    print()


@dataclass
class Question:
    qtype: str
    text: str
    answer: str
    difficulty: int = 1
    options: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)


@dataclass
class Fighter:
    name: str
    max_hp: int
    atk: int
    defense: int
    spd: int
    crit: float
    crit_mult: float = 1.5
    hp: int = 0
    behavior: str = "neutral"
    shield: int = 0
    effects: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.hp <= 0:
            self.hp = self.max_hp

    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> None:
        if self.shield > 0:
            blocked = min(self.shield, amount)
            self.shield -= blocked
            amount -= blocked
            if blocked:
                type_text(f"{self.name}'s shield blocks {blocked} damage.")
        self.hp = max(0, self.hp - amount)

    def heal(self, amount: int) -> None:
        self.hp = min(self.max_hp, self.hp + amount)


@dataclass
class Item:
    name: str
    price: int
    kind: str
    value: int


@dataclass
class Player(Fighter):
    class_name: str = "Adventurer"
    passive: str = ""
    run_modifier: str = ""
    wisdom: int = 5
    level: int = 1
    exp: int = 0
    next_exp: int = 100
    gold: int = 20
    streak: int = 0
    best_streak: int = 0
    focus: int = 0
    hint_ready: bool = False
    bloodlust_stacks: int = 0
    dodge_next: bool = False
    streak_guard: bool = False
    correct_answers: int = 0
    total_answers: int = 0
    skills: list[str] = field(default_factory=list)
    mastery: dict[str, int] = field(default_factory=lambda: {
        "TF": 0, "MC": 0, "AR": 0, "ID": 0, "FB": 0, "OD": 0
    })
    inventory: list[str] = field(default_factory=lambda: [
        "Potion", "Attack Tonic", "Hint"
    ])


@dataclass
class RunState:
    tier: int = 1
    nodes: int = 0
    battles_won: int = 0
    elites_won: int = 0
    boss_won: bool = False
    bestiary: dict[str, dict[str, int]] = field(default_factory=dict)
    achievements: list[str] = field(default_factory=list)
    journal: list[str] = field(default_factory=list)


ITEMS = {
    "Potion": Item("Potion", 15, "heal", 25),
    "Mega Potion": Item("Mega Potion", 35, "heal", 60),
    "Attack Tonic": Item("Attack Tonic", 25, "atk", 5),
    "Shield Tonic": Item("Shield Tonic", 25, "def", 5),
    "Poison Bomb": Item("Poison Bomb", 30, "poison", 5),
    "Freeze Scroll": Item("Freeze Scroll", 35, "freeze", 1),
    "Weakness Curse": Item("Weakness Curse", 30, "weakness", 5),
    "Gold Charm": Item("Gold Charm", 40, "gold", 0),
    "Hint": Item("Hint", 20, "hint", 0),
}

ENEMIES = {
    1: [
        ("Bug", 35, 8, 1, 4, 0.05, "neutral"),
        ("Bandit", 45, 10, 3, 4, 0.10, "aggressive"),
        ("Syntax Slime", 50, 9, 2, 2, 0.05, "defensive"),
    ],
    2: [
        ("Logic Brute", 75, 14, 4, 3, 0.08, "aggressive"),
        ("Array Shade", 60, 16, 2, 7, 0.15, "evasive"),
        ("Stone Compiler", 90, 12, 7, 1, 0.05, "defensive"),
    ],
    3: [
        ("Runtime Reaper", 110, 21, 4, 7, 0.20, "evasive"),
        ("Ancient Algorithm", 145, 18, 8, 3, 0.10, "defensive"),
        ("Final Debugger", 170, 22, 8, 5, 0.18, "aggressive"),
    ],
}


class LearningEngine:
    def __init__(self) -> None:
        self.questions: list[Question] = []
        self.wrong: list[Question] = []

    def load_all(self) -> None:
        for qtype, relative_path in QUESTION_FILES.items():
            path = os.path.join(BASE_DIR, relative_path)
            self.load_file(path, qtype, QUESTION_DIFFICULTY[qtype])
        print(f"Loaded {len(self.questions)} questions.")

    def load_file(self, path: str, qtype: str, difficulty: int) -> None:
        if not os.path.exists(path):
            print(f"Missing question file: {path}")
            return
        with open(path, "r", encoding="utf-8") as file:
            for raw in file:
                line = raw.strip()
                if not line:
                    continue
                try:
                    if qtype in ("TF", "AR", "ID", "FB"):
                        if "=" not in line:
                            continue
                        text, answer = line.split("=", 1)
                        self.questions.append(Question(qtype, text.strip(), answer.strip(), difficulty))
                    elif qtype == "MC":
                        data = json.loads(line)
                        self.questions.append(Question(
                            "MC", data["question"], data["answer"], difficulty, options=data["options"]
                        ))
                    elif qtype == "OD":
                        data = json.loads(line)
                        self.questions.append(Question(
                            "OD", data["question"], data["answer"], difficulty, items=data["items"]
                        ))
                except (KeyError, json.JSONDecodeError):
                    print(f"Skipped bad question line: {line}")

    def pick(self, difficulty: int | None = None) -> Question | None:
        pool = self.questions
        if difficulty is not None:
            filtered = [q for q in pool if q.difficulty == difficulty]
            if filtered:
                pool = filtered
        if not pool:
            return None
        missed = {q.text for q in self.wrong}
        weights = [3 if q.text in missed else 1 for q in pool]
        return random.choices(pool, weights=weights, k=1)[0]


def ask_question(engine: LearningEngine, player: Player, difficulty: int | None = None) -> tuple[bool, str]:
    q = engine.pick(difficulty)
    if q is None:
        print("No questions loaded. The action fails.")
        return False, ""

    print(f"\n[{q.qtype} | difficulty {q.difficulty}]")
    print(q.text)
    if player.hint_ready:
        if q.qtype == "MC":
            wrong = [option for option in q.options if option.lower() != q.answer.lower()]
            if wrong:
                type_text(f"Hint: remove '{random.choice(wrong)}' from consideration.")
        elif q.answer:
            type_text(f"Hint: starts with '{q.answer[0]}' and has {len(q.answer)} character(s).")
        player.hint_ready = False

    if q.qtype == "TF":
        answer = ask("(true/false)> ", ["true", "false"])
    elif q.qtype == "MC":
        options = q.options[:]
        if "MC" in player.skills:
            wrong = [option for option in options if option.lower() != q.answer.lower()]
            if wrong and len(options) > 2:
                removed = random.choice(wrong)
                options.remove(removed)
                type_text(f"[Eliminate One] Removed: {removed}")
        print_numbered(options)
        index = choose_index("> ", len(options))
        answer = options[index] if index is not None else ""
    elif q.qtype == "OD":
        shown = q.items[:]
        random.shuffle(shown)
        print_numbered(shown)
        raw = ask("Order as numbers, example 2,1,3> ")
        try:
            chosen = [shown[int(x.strip()) - 1] for x in raw.split(",")]
            correct = [q.items[int(x.strip()) - 1] for x in q.answer.split(",")]
            answer = ",".join(chosen)
            is_correct = chosen == correct
            return finish_question(is_correct, engine, player, q)
        except (ValueError, IndexError):
            answer = ""
    else:
        answer = ask("> ")

    return finish_question(answer.lower() == q.answer.lower(), engine, player, q)


def finish_question(correct: bool, engine: LearningEngine, player: Player, q: Question) -> tuple[bool, str]:
    player.total_answers += 1
    if correct:
        type_text("Correct.")
        player.correct_answers += 1
        player.mastery[q.qtype] += 1
        player.streak += 1
        player.best_streak = max(player.best_streak, player.streak)
        focus_gain = 10 + player.wisdom // 5
        if player.passive == "insight":
            focus_gain += 5
        player.focus = min(100, player.focus + focus_gain)
        if player.passive == "bloodlust" and player.bloodlust_stacks < 10:
            player.atk += 1
            player.bloodlust_stacks += 1
            type_text("[Bloodlust] ATK rises by 1.")
        if player.passive == "momentum":
            player.effects["momentum"] = 1
        if q.qtype == "OD" and "OD" in player.skills and random.random() < 0.25:
            player.dodge_next = True
            type_text("[Tactical Read] Next attack may be dodged.")
        unlock_skills(player)
    else:
        type_text(f"Wrong. Correct answer: {q.answer}")
        engine.wrong.append(q)
        if player.streak_guard:
            player.streak_guard = False
            type_text("[Composure] Streak protected.")
        else:
            player.streak = max(0, player.streak // 2)
        player.focus = max(0, player.focus - 10)
        if player.passive == "fortress":
            player.shield += 8
            type_text("[Fortress] Shield +8.")
        if player.run_modifier == "cursed":
            player.take_damage(10)
            type_text("[Cursed Knowledge] You lose 10 HP.")
    return correct, q.qtype


def unlock_skills(player: Player) -> None:
    for qtype, mastery in player.mastery.items():
        if mastery >= 5 and qtype not in player.skills:
            player.skills.append(qtype)
            name, desc = SKILLS[qtype]
            type_text(f"Skill unlocked: {name} - {desc}")


def effective_atk(fighter: Fighter) -> int:
    total = fighter.atk
    if fighter.effects.get("attack_up", 0) > 0:
        total += 5
    if fighter.effects.get("weakness", 0) > 0:
        total -= 5
    return max(1, total)


def effective_defense(fighter: Fighter) -> int:
    total = fighter.defense
    if fighter.effects.get("defense_up", 0) > 0:
        total += 5
    return max(0, total)


def damage(attacker: Fighter, defender: Fighter, mastery_bonus: int = 0) -> tuple[int, bool]:
    base = effective_atk(attacker) - effective_defense(defender) + random.randint(-2, 3)
    base = max(1, base)
    base += mastery_bonus // 5
    if isinstance(attacker, Player):
        base += attacker.streak // 4
        base = int(base * (1 + attacker.wisdom * 0.01))
    crit_bonus = 0.20 if attacker.effects.pop("momentum", 0) > 0 else 0
    crit = random.random() < attacker.crit + crit_bonus
    if crit:
        base = int(base * attacker.crit_mult)
    return base, crit


def tick_effects(fighter: Fighter) -> None:
    if fighter.effects.get("poison", 0) > 0:
        fighter.take_damage(5)
        type_text(f"{fighter.name} takes 5 poison damage.")
    expired = []
    for name in fighter.effects:
        fighter.effects[name] -= 1
        if fighter.effects[name] <= 0:
            expired.append(name)
    for name in expired:
        del fighter.effects[name]


def enemy_for(tier: int, elite: bool = False, boss: bool = False) -> Fighter:
    data = random.choice(ENEMIES[min(3, tier)])
    name, hp, atk, defense, spd, crit, behavior = data
    if elite:
        name = "Elite " + name
        hp = int(hp * 1.5)
        atk = int(atk * 1.3)
        defense += 2
        behavior = random.choice(["aggressive", "defensive", "evasive"])
    if boss:
        name = "Boss " + name
        hp = int(hp * 2.2)
        atk = int(atk * 1.5)
        defense += 4
        crit += 0.08
        behavior = "boss"
    return Fighter(name, hp, atk, defense, spd, crit, behavior=behavior)


def show_stats(player: Player, enemy: Fighter) -> None:
    print()
    divider("Combat")
    animated_bar(player.name, player.hp, player.max_hp)
    print(f"Gold {player.gold} | Lv {player.level} | EXP {player.exp}/{player.next_exp}")
    print(f"Streak {player.streak} | Focus {player.focus}/100")
    print(f"Class {player.class_name} | Shield {player.shield} | Effects {list(player.effects)}")
    animated_bar(enemy.name, enemy.hp, enemy.max_hp)
    print(f"Behavior {enemy.behavior} | Shield {enemy.shield} | Effects {list(enemy.effects)}")
    print("=" * 58)


def apply_player_item(player: Player, item: Item) -> bool:
    if item.kind == "heal":
        heal = item.value + (player.mastery["ID"] if "ID" in player.skills else 0)
        player.heal(heal)
        type_text(f"Healed {heal} HP.")
        return True
    if item.kind == "atk":
        player.effects["attack_up"] = 3
        type_text(f"ATK +{item.value} for 3 turns.")
        return True
    if item.kind == "def":
        player.effects["defense_up"] = 3
        player.shield += 10
        type_text(f"DEF +{item.value} for 3 turns. Shield +10.")
        return True
    if item.kind == "hint":
        player.hint_ready = True
        type_text("Your next question will show a hint.")
        return True
    if item.kind == "gold":
        player.effects["double_gold"] = 3
        type_text("Gold rewards doubled for 3 turns.")
        return True
    return False


def apply_enemy_item(enemy: Fighter, item: Item) -> bool:
    if item.kind == "poison":
        enemy.effects["poison"] = 4
        type_text(f"{enemy.name} is poisoned for 4 turns.")
    elif item.kind == "freeze":
        enemy.effects["freeze"] = item.value
        type_text(f"{enemy.name} is frozen.")
    elif item.kind == "weakness":
        enemy.effects["weakness"] = 3
        type_text(f"{enemy.name}'s ATK is reduced for 3 turns.")
    else:
        return False
    return True


def use_item(player: Player, enemy: Fighter) -> None:
    if not player.inventory:
        type_text("Inventory empty.")
        return
    print("0. Cancel")
    print_numbered(player.inventory)
    index = choose_index("Use which item? ", len(player.inventory))
    if index is None:
        return
    name = player.inventory.pop(index)
    item = ITEMS.get(name)
    if item is None:
        type_text("Unknown item.")
    elif apply_player_item(player, item):
        return
    elif apply_enemy_item(enemy, item):
        return
    else:
        enemy.take_damage(item.value)
        type_text(f"{enemy.name} takes {item.value} item damage.")


def player_turn(player: Player, enemy: Fighter, engine: LearningEngine, boss: bool = False) -> str:
    show_stats(player, enemy)
    print("1. Answer/Attack")
    print("2. Use Item")
    print("3. Focus Skill" if player.focus >= 100 else "3. Focus Skill (not ready)")
    print("4. Run" if not boss else "4. Guard")
    print("5. Mastery Skill")
    choice = ask("> ", ["1", "2", "3", "4", "5"])

    if choice == "1":
        correct, qtype = ask_question(engine, player, difficulty=3 if boss else None)
        if correct:
            mastery = player.mastery.get(qtype, 0)
            if enemy.effects.get("evasive", 0) > 0 and random.random() < 0.30:
                type_text(f"{enemy.name} evades your attack.")
                return "continue"
            amount, crit = damage(player, enemy, mastery)
            if player.run_modifier == "scholar":
                amount *= 2
            enemy.take_damage(amount)
            type_text(f"{player.name} hits for {amount} damage." + (" Critical!" if crit else ""))
        return "continue"
    if choice == "2":
        use_item(player, enemy)
        return "continue"
    if choice == "3":
        if player.focus >= 100:
            player.focus = 0
            amount = player.atk * 2 + player.wisdom
            enemy.take_damage(amount)
            player.heal(10)
            type_text(f"Focus burst deals {amount} damage and restores 10 HP.")
        else:
            type_text("Focus is not ready.")
        return "continue"
    if choice == "5":
        use_mastery_skill(player, enemy)
        return "continue"
    if boss:
        player.defense += 3
        type_text("You guard. DEF +3.")
        return "continue"
    if player.run_modifier == "ironwill":
        type_text("[Iron Will] You cannot run from battle.")
        return "continue"
    return "escape" if random.random() < 0.55 else "continue"


def use_mastery_skill(player: Player, enemy: Fighter) -> None:
    if not player.skills:
        type_text("No mastery skills unlocked yet.")
        return
    print("\nUnlocked Skills:")
    print("0. Cancel")
    def skill_label(qtype: str) -> str:
        name, desc = SKILLS[qtype]
        return f"{name} [{qtype}] - {desc}"

    print_numbered(player.skills, skill_label)
    index = choose_index("> ", len(player.skills))
    if index is None:
        return
    qtype = player.skills[index]
    if qtype == "TF":
        player.shield += 12
        type_text("Truth Guard raises a shield.")
    elif qtype == "MC":
        player.hint_ready = True
        type_text("Eliminate One prepares your next question.")
    elif qtype == "AR":
        amount = 10 + player.mastery["AR"]
        enemy.take_damage(amount)
        type_text(f"Precision deals {amount} direct damage.")
    elif qtype == "ID":
        heal = 12 + player.mastery["ID"]
        player.heal(heal)
        type_text(f"Recall restores {heal} HP.")
    elif qtype == "FB":
        player.streak_guard = True
        type_text("Composure will protect your streak once.")
    elif qtype == "OD":
        player.dodge_next = True
        type_text("Tactical Read prepares a dodge.")


def enemy_turn(enemy: Fighter, player: Player) -> None:
    if enemy.effects.get("freeze", 0) > 0:
        type_text(f"{enemy.name} is frozen and skips the turn.")
        return
    if player.dodge_next:
        player.dodge_next = False
        type_text(f"{player.name} reads the attack and dodges.")
        return
    if enemy.behavior == "defensive" and random.random() < 0.35:
        enemy.shield += 10
        enemy.effects["defense_up"] = 2
        type_text(f"{enemy.name} braces behind a shield.")
        return
    if enemy.behavior == "evasive" and random.random() < 0.30:
        enemy.effects["evasive"] = 1
        type_text(f"{enemy.name} shifts into an evasive stance.")
        return
    dodge = random.random() < min(0.35, player.spd * 0.02 + player.streak * 0.003)
    if dodge:
        type_text(f"{player.name} dodges.")
        return
    hits = 2 if enemy.behavior == "aggressive" else 1
    for _ in range(hits):
        if not player.alive():
            return
        amount, crit = damage(enemy, player)
        if hits == 2:
            amount = max(1, amount // 2)
        player.take_damage(amount)
        type_text(f"{enemy.name} hits for {amount} damage." + (" Critical!" if crit else ""))


def record_bestiary(state: RunState, enemy_name: str, killed: bool = False) -> None:
    entry = state.bestiary.setdefault(enemy_name, {"seen": 0, "kills": 0})
    if not killed:
        entry["seen"] += 1
    if killed:
        entry["kills"] += 1


def combat(player: Player, engine: LearningEngine, state: RunState, tier: int, elite: bool = False, boss: bool = False) -> str:
    enemy = enemy_for(tier, elite, boss)
    record_bestiary(state, enemy.name)
    clear_screen()
    loading("Entering encounter")
    divider("Encounter")
    flash_message(f"{enemy.name} appears!", repeats=3 if boss or elite else 2)
    if "TF" in player.skills:
        player.shield += 5
        type_text("[Truth Guard] Battle shield +5.")
    if "FB" in player.skills:
        player.streak_guard = True
    phase = 1
    while player.alive() and enemy.alive():
        if boss:
            ratio = enemy.hp / enemy.max_hp
            if phase == 1 and ratio <= 0.66:
                phase = 2
                enemy.atk += 5
                flash_message(f"{enemy.name} enters Phase 2. ATK rises.", repeats=3)
            elif phase == 2 and ratio <= 0.33:
                phase = 3
                enemy.atk += 5
                enemy.crit = min(0.5, enemy.crit + 0.15)
                flash_message(f"{enemy.name} enters Phase 3. Critical chance rises.", repeats=3)
            type_text(random.choice([
                "The boss winds up for a heavy blow...",
                "The boss leaves itself exposed for a moment...",
                "Dark energy gathers around the boss...",
            ]))
        result = player_turn(player, enemy, engine, boss)
        if result == "escape":
            type_text("You escaped.")
            return "escaped"
        if enemy.alive():
            enemy_turn(enemy, player)
        tick_effects(enemy)
        tick_effects(player)

    if player.alive():
        type_text(f"{enemy.name} defeated.")
        record_bestiary(state, enemy.name, killed=True)
        reward_exp = 40 if elite else 25
        reward_gold = 35 if elite else 15
        if boss:
            reward_exp, reward_gold = 150, 100
        if player.run_modifier == "ironwill":
            reward_exp = int(reward_exp * 1.5)
            reward_gold = int(reward_gold * 1.5)
        gain_exp(player, reward_exp + tier * 10)
        gold = reward_gold + tier * 5
        if player.effects.get("double_gold", 0) > 0:
            gold *= 2
        player.gold += gold
        type_text(f"Gained {gold} gold.")
        if random.random() < 0.35:
            drop = random.choice(list(ITEMS))
            player.inventory.append(drop)
            type_text(f"Found item: {drop}")
        return "win"
    return "death"


def gain_exp(player: Player, amount: int) -> None:
    player.exp += amount
    type_text(f"Gained {amount} EXP.")
    while player.exp >= player.next_exp:
        player.exp -= player.next_exp
        player.level += 1
        player.next_exp = int(player.next_exp * 1.3)
        player.max_hp += 8
        player.hp = player.max_hp
        player.atk += 2
        player.defense += 1
        flash_message(f"LEVEL UP! Now level {player.level}.", repeats=4)


def shop(player: Player) -> None:
    divider("Shop")
    stock = random.sample(list(ITEMS.values()), 3)
    while True:
        print(f"\nGold: {player.gold}")
        print("0. Leave")
        print_numbered(stock, lambda item: f"{item.name} - {item.price}g")
        choice = ask("> ")
        if choice.lower() in ("0", "b", "back", "leave"):
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(stock):
            type_text("Invalid choice.")
            continue
        item = stock[int(choice) - 1]
        if player.gold >= item.price:
            player.gold -= item.price
            player.inventory.append(item.name)
            type_text(f"Bought {item.name}.")
        else:
            type_text("Not enough gold.")


def trial(player: Player, engine: LearningEngine) -> None:
    divider("Knowledge Trial")
    type_text("Answer 3 questions. Correct answers give rewards.")
    correct = 0
    for _ in range(3):
        ok, _ = ask_question(engine, player)
        if ok:
            correct += 1
    exp = correct * 20
    gold = correct * 10
    gain_exp(player, exp)
    player.gold += gold
    type_text(f"Trial complete: +{exp} EXP, +{gold} gold.")


def practice_mode(engine: LearningEngine) -> None:
    divider("Practice Mode")
    type_text("Answer questions without combat pressure.")
    correct = 0
    total = 0
    dummy = Player("Practice", 50, 8, 3, 5, 0.1)
    while True:
        if engine.pick() is None:
            type_text("No questions loaded.")
            break
        type_text("\nPractice question:")
        ok, _ = ask_question(engine, dummy)
        total += 1
        if ok:
            correct += 1
        type_text(f"Practice score: {correct}/{total}")
        if ask("Continue practice? (y/n)> ", ["y", "n"]) == "n":
            break


def rest(player: Player) -> None:
    amount = max(10, player.max_hp // 3)
    if "ID" in player.skills:
        amount += player.mastery["ID"]
    animated_bar("Before rest", player.hp, player.max_hp)
    player.heal(amount)
    sleep_anim(0.25)
    animated_bar("After rest", player.hp, player.max_hp)
    type_text(f"You rest and recover {amount} HP.")


def quick_status(player: Player, state: RunState) -> None:
    print(
        f"{player.name} | HP {player.hp}/{player.max_hp} | "
        f"Lv {player.level} | Gold {player.gold} | "
        f"Tier {state.tier} Node {state.nodes}"
    )


def make_nodes(state: RunState) -> list[str]:
    if state.tier >= 3 and state.nodes >= 10:
        return random.sample(["battle", "elite", "shop", "trial", "rest", "boss"], 3)
    return random.sample(NODE_TYPES, random.choice([2, 3]))


def view_character(player: Player) -> None:
    print("\n=== Character Sheet ===")
    print(f"{player.name} the {player.class_name}")
    print(f"HP: {bar(player.hp, player.max_hp)}  Shield: {player.shield}")
    print(f"ATK {player.atk} | DEF {player.defense} | SPD {player.spd} | WIS {player.wisdom}")
    print(f"Crit {int(player.crit * 100)}% x{player.crit_mult}")
    print(f"Level {player.level} | EXP {player.exp}/{player.next_exp} | Gold {player.gold}")
    print(f"Streak {player.streak} | Best {player.best_streak} | Focus {player.focus}/100")
    print(f"Passive: {player.passive or 'none'} | Modifier: {player.run_modifier or 'none'}")
    print("Mastery: " + ", ".join(f"{key}:{value}" for key, value in player.mastery.items()))
    print("Inventory: " + (", ".join(player.inventory) if player.inventory else "empty"))
    if player.skills:
        print("Skills: " + ", ".join(SKILLS[qtype][0] for qtype in player.skills))
    else:
        print("Skills: none")
    pause()


def view_inventory(player: Player) -> None:
    print("\n=== Inventory ===")
    if not player.inventory:
        print("Inventory is empty.")
        pause()
        return
    print("0. Back")
    print_numbered(player.inventory)
    print("\nUse healing items here, or save offensive items for combat.")
    index = choose_index("Use item? ", len(player.inventory))
    if index is None:
        return
    name = player.inventory[index]
    item = ITEMS.get(name)
    if item is None:
        type_text("Unknown item.")
    elif item.kind in ("heal", "hint", "gold"):
        player.inventory.pop(index)
        apply_player_item(player, item)
    else:
        type_text("That item is only useful in combat.")
    pause()


def view_bestiary(state: RunState) -> None:
    print("\n=== Bestiary ===")
    if not state.bestiary:
        print("No enemies recorded yet.")
    for name, data in sorted(state.bestiary.items()):
        print(f"{name}: seen {data.get('seen', 0)}, defeated {data.get('kills', 0)}")
    pause()


def view_achievements(state: RunState) -> None:
    print("\n=== Achievements ===")
    for name, desc in ACHIEVEMENTS.items():
        marker = "X" if name in state.achievements else " "
        print(f"[{marker}] {name} - {desc}")
    pause()


def draw_map(state: RunState) -> str:
    history = [NODE_ICONS.get(node, "[?]") for node in state.journal[-8:]]
    return "--".join(history + ["[*]"])


def choose_node(state: RunState, player: Player) -> str:
    while True:
        nodes = make_nodes(state)
        divider(f"Tier {state.tier} | Node {state.nodes}")
        quick_status(player, state)
        animate_map(draw_map(state))
        print_numbered(nodes, lambda node: f"{NODE_ICONS.get(node, '[?]')} {node.title()}")
        print("c. Character | i. Inventory | b. Bestiary | a. Achievements")
        print("?. Help | t. Settings | s. Save | q. Save and Quit")
        choice = ask("> ").lower()
        if choice in ("?", "h", "help"):
            show_help()
        elif choice == "c":
            view_character(player)
        elif choice == "i":
            view_inventory(player)
        elif choice == "b":
            view_bestiary(state)
        elif choice == "a":
            view_achievements(state)
        elif choice == "t":
            set_text_speed()
        elif choice == "s":
            return "save"
        elif choice == "q":
            if confirm("Save and quit"):
                return "quit"
        elif choice.isdigit() and 1 <= int(choice) <= len(nodes):
            return nodes[int(choice) - 1]
        else:
            type_text("Invalid choice.")


def run_node(player: Player, engine: LearningEngine, state: RunState, node: str) -> bool:
    if node in ("save", "quit"):
        save_game(player, state)
        return node != "quit"
    if node == "battle":
        loading("Walking toward battle")
        result = combat(player, engine, state, state.tier)
        if result == "death":
            return False
        if result == "win":
            state.battles_won += 1
    elif node == "elite":
        loading("A powerful presence approaches")
        result = combat(player, engine, state, state.tier, elite=True)
        if result == "death":
            return False
        if result == "win":
            state.battles_won += 1
            state.elites_won += 1
            player.max_hp += 5
    elif node == "boss":
        loading("The final gate opens", 5)
        result = combat(player, engine, state, 3, boss=True)
        if result == "win":
            state.boss_won = True
            state.journal.append("boss")
            type_text("\nFinal boss defeated. You win the run.")
            check_achievements(player, state)
        return result == "win"
    elif node == "shop":
        loading("Following the lantern light")
        shop(player)
    elif node == "trial":
        loading("Entering the trial chamber")
        trial(player, engine)
    elif node == "rest":
        loading("Finding a quiet place")
        rest(player)

    state.nodes += 1
    state.journal.append(node)
    if state.nodes % 5 == 0:
        state.tier = min(3, state.tier + 1)
        type_text(f"\nTier increased to {state.tier}.")
    player.heal(max(1, player.max_hp // 20))
    random_event(player)
    check_achievements(player, state)
    save_game(player, state, quiet=True)
    return True


def award_achievement(state: RunState, name: str) -> None:
    if name not in state.achievements:
        state.achievements.append(name)
        type_text(f"*** Achievement unlocked: {name} ***")


def check_achievements(player: Player, state: RunState) -> None:
    if state.battles_won >= 1:
        award_achievement(state, "First Victory")
    if state.nodes >= 5:
        award_achievement(state, "Node Walker")
    if state.elites_won >= 1:
        award_achievement(state, "Elite Breaker")
    if player.best_streak >= 10:
        award_achievement(state, "Scholar Streak")
    if any(value >= 10 for value in player.mastery.values()):
        award_achievement(state, "Master Student")
    if state.boss_won:
        award_achievement(state, "Boss Clear")


def random_event(player: Player) -> None:
    roll = random.random()
    if roll > 0.20:
        return
    type_text("\nA small event interrupts the path...")
    if roll < 0.05:
        found = random.choice(list(ITEMS))
        player.inventory.append(found)
        type_text(f"You find a forgotten cache: {found}.")
    elif roll < 0.10:
        coins = random.randint(8, 20)
        player.gold += coins
        type_text(f"You discover {coins} gold.")
    elif roll < 0.15:
        player.take_damage(8)
        type_text("A trap clips you for 8 damage.")
    else:
        player.focus = min(100, player.focus + 15)
        type_text("A quiet insight restores 15 focus.")


def new_player() -> Player:
    name = ask("Character name: ") or "Hero"
    print("\nChoose a class:")
    print_numbered(CLASS_BUILDS, lambda build: f"{build[0]} - {build[8]}")
    index = choose_index("> ", len(CLASS_BUILDS))
    if index is None:
        index = 0
    class_name, passive, hp, atk, defense, spd, crit, wisdom, _ = CLASS_BUILDS[index]
    player = Player(name, hp, atk, defense, spd, crit, wisdom=wisdom)
    player.class_name = class_name
    player.passive = passive
    return player


def choose_run_modifier(player: Player) -> None:
    print("\nChoose a run modifier:")
    print_numbered(RUN_MODIFIERS, lambda mod: f"{mod[0]} - {mod[2]}")
    index = choose_index("> ", len(RUN_MODIFIERS))
    if index is None:
        index = 0
    player.run_modifier = RUN_MODIFIERS[index][1]
    if player.run_modifier:
        type_text(f"Modifier active: {player.run_modifier}.")


def save_game(player: Player, state: RunState, quiet: bool = False) -> None:
    data = {"player": asdict(player), "state": asdict(state)}
    with open(SAVE_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
    if not quiet:
        type_text("Game saved.")
    elif ANIMATIONS_ON:
        print("[autosaved]")


def dataclass_field_names(cls) -> set[str]:
    return {item.name for item in fields(cls)}


def restore_dataclass(cls, data: dict):
    allowed = dataclass_field_names(cls)
    clean = {key: value for key, value in data.items() if key in allowed}
    return cls(**clean)


def load_game() -> tuple[Player, RunState] | None:
    if not os.path.exists(SAVE_FILE):
        type_text("No save file found.")
        return None
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        player = restore_dataclass(Player, data["player"])
        state = restore_dataclass(RunState, data["state"])
        return player, state
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        type_text(f"Save file could not be loaded: {exc}")
        return None


def title_menu(engine: LearningEngine) -> str:
    while True:
        loading("Ready")
        print()
        type_text("1. New Game", 0.005)
        type_text("2. Load Game", 0.005)
        type_text("3. Practice Mode", 0.005)
        type_text("4. View Saved Achievements", 0.005)
        type_text("5. Settings", 0.005)
        type_text("6. Help", 0.005)
        type_text("7. Exit", 0.005)
        choice = ask("> ", ["1", "2", "3", "4", "5", "6", "7"])
        if choice == "3":
            practice_mode(engine)
            show_title()
            continue
        if choice == "4":
            loaded = load_game()
            view_achievements(loaded[1] if loaded else RunState())
            show_title()
            continue
        if choice == "5":
            set_text_speed()
            show_title()
            continue
        if choice == "6":
            show_help()
            show_title()
            continue
        return choice


def print_run_summary(player: Player, state: RunState, engine: LearningEngine) -> None:
    print("\n=== Run Summary ===")
    print(f"Name: {player.name}")
    print(f"Level: {player.level}")
    print(f"Nodes cleared: {state.nodes}")
    print(f"Battles won: {state.battles_won}")
    print(f"Gold: {player.gold}")
    print(f"Best streak: {player.best_streak}")
    accuracy = int((player.correct_answers / max(1, player.total_answers)) * 100)
    print(f"Accuracy: {player.correct_answers}/{player.total_answers} ({accuracy}%)")
    print("Mastery: " + ", ".join(f"{key}:{value}" for key, value in player.mastery.items()))
    if state.achievements:
        print("Achievements: " + ", ".join(state.achievements))
    if state.bestiary:
        print("\nBestiary Summary:")
        for name, data in sorted(state.bestiary.items()):
            print(f"- {name}: seen {data.get('seen', 0)}, defeated {data.get('kills', 0)}")
    if engine.wrong:
        print("\nReview missed questions:")
        for q in engine.wrong[-5:]:
            print(f"- {q.text} = {q.answer}")


def main() -> None:
    show_title()
    engine = LearningEngine()
    engine.load_all()
    choice = title_menu(engine)
    if choice == "7":
        return

    loaded = load_game() if choice == "2" else None
    if loaded:
        player, state = loaded
        type_text("Save loaded.")
    else:
        player, state = new_player(), RunState()
        choose_run_modifier(player)

    alive = True
    saved_and_quit = False
    while alive:
        node = choose_node(state, player)
        alive = run_node(player, engine, state, node)
        if node == "quit":
            saved_and_quit = True
            break
        if node == "boss" and alive:
            break

    if saved_and_quit:
        type_text("Saved. See you next run.")
    else:
        print_run_summary(player, state, engine)


if __name__ == "__main__":
    main()
