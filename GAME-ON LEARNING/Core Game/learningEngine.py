"""Learning engine and question management.

Manages question loading, validation, quiz presentation, answer processing,
and integration with the combat and progression systems.
"""

import json
import random
import time
from ui import typewriter, input_handler

def validate_notes(filepath, qtype):
    errors = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        typewriter(f"[Validator] File not found: {filepath}")
        return False

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        if qtype in ("TF", "AR", "FB", "ID"):
            if "=" not in line:
                errors.append(f"  Line {i}: missing '=' separator → {line!r}")
            else:
                parts = line.split("=", 1)
                if not parts[0].strip():
                    errors.append(f"  Line {i}: empty question → {line!r}")
                if not parts[1].strip():
                    errors.append(f"  Line {i}: empty answer → {line!r}")
                if qtype == "TF":
                    ans = parts[1].strip().lower()
                    if ans not in ("true", "false"):
                        errors.append(f"  Line {i}: TF answer must be 'True' or 'False' → {ans!r}")

        elif qtype == "MC":
            try:
                data = json.loads(line)
                for key in ("question", "options", "answer"):
                    if key not in data:
                        errors.append(f"  Line {i}: missing key '{key}'")
                if "options" in data and data.get("answer") not in data["options"]:
                    errors.append(f"  Line {i}: answer not in options list")
            except json.JSONDecodeError:
                errors.append(f"  Line {i}: invalid JSON → {line!r}")

    if errors:
        typewriter(f"[Validator] Issues in {filepath}:")
        for err in errors:
            typewriter(err)
        return False

    typewriter(f"[Validator] {filepath} — OK ({len(lines)} lines)")
    return True


class LearningEngine:
    def __init__(self):
        self.questions = []
        self.wrong_answers = []

    def record_wrong(self, question_data):
        self.wrong_answers.append({
            "question": question_data["question"],
            "correct_answer": question_data["answer"],
            "type": question_data["type"],
        })

    def get_weak_areas(self):
        from collections import Counter
        counts = Counter(q["type"] for q in self.wrong_answers)
        return counts.most_common()

    def print_review(self):
        if not self.wrong_answers:
            typewriter("\nYou answered every question correctly. Excellent!")
            return
        typewriter(f"\n--- Review: {len(self.wrong_answers)} missed questions ---")
        for entry in self.wrong_answers[-10:]:
            typewriter(f"  Q: {entry['question']}")
            typewriter(f"  A: {entry['correct_answer']}")
            typewriter("")
        typewriter("Weak areas this run:")
        for qtype, count in self.get_weak_areas():
            category = {"TF": "True/False", "MC": "Multiple Choice",
                        "AR": "Arithmetic", "ID": "Identification", 
                        "FB": "Fill in the Blanks", "OD": "Ordering"}.get(qtype, qtype)
            typewriter(f"  {category}: {count} wrong")

    def get_consecutive_wrong(self):
        if len(self.wrong_answers) >= 2:
            last   = self.wrong_answers[-1]["question"]
            second = self.wrong_answers[-2]["question"]
            if last == second:
                return self.wrong_answers[-1]
        return None

    def load_notes(self, filepath, qtype="TF", difficulty=1):
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                lines = file.readlines()

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if qtype in ("TF", "AR", "FB", "ID"):
                    if "=" not in line:
                        continue
                    statement, answer = line.split("=", 1)
                    self.questions.append({
                        "type": qtype,
                        "question": statement.strip(),
                        "answer": answer.strip(),
                        "difficulty": difficulty
                    })

                elif qtype == "MC":
                    try:
                        data = json.loads(line)
                        if "question" in data and "options" in data and "answer" in data:
                            data["type"] = "MC"
                            data["difficulty"] = difficulty
                            self.questions.append(data)
                    except json.JSONDecodeError:
                        continue

                elif qtype == "OD":
                    try:
                        data = json.loads(line)
                        if "question" in data and "items" in data and "answer" in data:
                            data["type"] = "OD"
                            data["difficulty"] = difficulty
                            self.questions.append(data)
                    except json.JSONDecodeError:
                        continue

        except FileNotFoundError:
            typewriter(f"Notes file not found: {filepath}")

    def get_question(self, difficulty=None):
        if not self.questions:
            return None
        pool = self.questions
        if difficulty is not None:
            filtered = [q for q in self.questions if q.get("difficulty") == difficulty]
            if filtered:
                pool = filtered

        wrong_questions = {q["question"] for q in self.wrong_answers}
        weights = [3 if q["question"] in wrong_questions else 1 for q in pool]
        return random.choices(pool, weights=weights, k=1)[0]

    def get_random_question(self):
        return self.get_question()


def random_item_pool(num_rewards=1):
    from items import AllItems
    rewards = []
    for _ in range(num_rewards):
        drop = random.randint(0, 100)
        if drop < 30:
            rarity = "common"
        elif drop < 60:
            rarity = "uncommon"
        elif drop < 95:
            rarity = "rare"
        else:
            rarity = "legendary"
        possibilities = [i for i in AllItems if i["rarity"] == rarity]
        if possibilities:
            item_data = random.choice(possibilities)
            rewards.append(item_data["class"]())
    return rewards


def combat_item_drop(tier=1):
    from items import AllItems
    drop_chance = 0.3 + (tier * 0.1)
    if random.random() > drop_chance:
        return None
    if tier == 1:
        weights = [60, 30, 10, 0]
    elif tier == 2:
        weights = [30, 40, 25, 5]
    else:
        weights = [10, 30, 45, 15]
    rarities = ["common", "uncommon", "rare", "legendary"]
    rarity = random.choices(rarities, weights=weights, k=1)[0]
    possibilities = [i for i in AllItems if i["rarity"] == rarity]
    if not possibilities:
        return None
    return random.choice(possibilities)["class"]()


def _ask_answer(question_data, extra_choices=None):
    q_type = question_data.get("type", "")
    extra_choices = extra_choices or []

    if q_type == "TF":
        return input_handler.ask_choice(
            [
                {"label": "True", "value": "True"},
                {"label": "False", "value": "False"},
            ] + list(extra_choices),
            "(True/False) > ",
        ).strip()

    if q_type == "MC":
        options = list(question_data.get("options", []))
        for i, opt in enumerate(options, 1):
            typewriter(f"  {i}. {opt}")

        raw = input_handler.ask_choice(
            [
                {"label": f"{i}. {opt}", "value": opt, "log": f"{i}. {opt}"}
                for i, opt in enumerate(options, 1)
            ] + list(extra_choices),
            "> ",
        ).strip()

        if raw.isdigit():
            try:
                return options[int(raw) - 1]
            except (ValueError, IndexError):
                return ""
        return raw

    return input_handler.ask("> ").strip()


def quiz_trial(player, engine):
    """Dynamic choice-driven trial puzzle."""
    # Debug mode: skip quiz trial
    if getattr(player, "debug_mode", False):
        typewriter("[DEBUG AUTO-PLAY] Completing maze trial...")
        player.gain_xp(50)
        time.sleep(0.3)
        return
    
    typewriter("\n=== Trial Exploration Challenge ===")
    time.sleep(1)
    typewriter("\nYou enter a mysterious labyrinth. Choose your paths wisely!")
    time.sleep(1)

    base_rewards = {"exp": 10, "gold": 5}
    accumulated_rewards = {"exp": 0, "gold": 0, "aid": []}
    moves = 0
    in_maze = True
    maze_map = []

    while in_maze:
        moves += 1

        typewriter("\nMaze Map: " + " > ".join(maze_map) if maze_map else "Trial Map: Start")
        time.sleep(0.5)

        num_paths = random.choice([2, 3])
        paths = [chr(65 + i) for i in range(num_paths)]
        typewriter(f"\nYou are at a crossroads! Choose your path: {', '.join(paths)}")
        choice = input_handler.ask_choice(
            [{"label": f"Path {path}", "value": path} for path in paths],
            "> ",
        ).strip().upper()

        if choice not in paths:
            typewriter("Invalid path! You hesitate and lose a turn.")
            time.sleep(1)
            continue

        maze_map.append(choice)
        typewriter(f"You chose path {choice}...")
        time.sleep(1)

        maze_difficulty = 1 if moves <= 2 else (2 if moves <= 4 else 3)
        q_data = engine.get_question(difficulty=maze_difficulty) or engine.get_question()
        if q_data is None:
            typewriter("No questions available! Skipping this move...")
            time.sleep(1)
            continue

        typewriter(f"\nQuestion: {q_data['question']}")
        player_answer = _ask_answer(q_data).lower()
        correct_answer = q_data["answer"].strip().lower()
        time.sleep(0.5)

        if player_answer == correct_answer:
            typewriter("Correct! You proceed safely.")
            time.sleep(0.5)
            accumulated_rewards["exp"]  += base_rewards["exp"]
            accumulated_rewards["gold"] += base_rewards["gold"]

            bonus_options = ["gold", "exp", "aid", "none"]
            bonus_choices = random.sample(bonus_options, random.choice([1, 2]))
            for bonus in bonus_choices:
                if bonus == "gold":
                    bonus_amount = random.randint(3, 10)
                    accumulated_rewards["gold"] += bonus_amount
                    typewriter(f"You found +{bonus_amount} gold!")
                    time.sleep(0.5)
                elif bonus == "exp":
                    bonus_amount = random.randint(5, 15)
                    accumulated_rewards["exp"] += bonus_amount
                    typewriter(f"You gained +{bonus_amount} experience!")
                    time.sleep(0.5)
                elif bonus == "aid":
                    aid = random_item_pool(num_rewards=1)
                    accumulated_rewards["aid"].extend(aid)
                    for a in aid:
                        typewriter(f"You discovered an aid: {a.name}!")
                    time.sleep(0.5)
        else:
            typewriter(f"Incorrect! The correct answer was: {q_data['answer']}")
            time.sleep(0.5)
            player.streak = max(0, player.streak - 1)
            typewriter("Your streak decreased!")
            time.sleep(0.5)
            if random.random() < 0.3:
                lost_gold = min(accumulated_rewards["gold"], random.randint(2, 8))
                accumulated_rewards["gold"] -= lost_gold
                typewriter(f"You triggered a trap and lost {lost_gold} gold!")
                time.sleep(1)

        special_event = random.random()
        if special_event < 0.2:
            chest_gold = random.randint(10, 25)
            chest_exp  = random.randint(10, 25)
            accumulated_rewards["gold"] += chest_gold
            accumulated_rewards["exp"]  += chest_exp
            typewriter(f"\nYou found a chest! +{chest_gold} gold, +{chest_exp} exp!")
            time.sleep(1)
            if random.random() < 0.2:
                from statusEffects import DoubleGold
                player.status_effects.append(DoubleGold(duration=5))
                typewriter("Lucky bonus! You received Double Gold buff for 5 turns!")
                time.sleep(1)
        elif special_event < 0.25:
            typewriter("\nYou stumble into a trap! Answer correctly to escape.")
            time.sleep(0.5)
            trap_q = engine.get_random_question()
            typewriter(f"{trap_q['question']}")
            trap_answer = _ask_answer(trap_q).lower()
            if trap_answer != trap_q["answer"].strip().lower():
                typewriter("Wrong! You are ejected from the trial!")
                in_maze = False
                break
            else:
                typewriter("Correct! You escape the trap safely.")
                time.sleep(0.5)

        if moves >= 5 and random.random() < 0.3:
            typewriter("\nYou find the exit of the maze. Trial completed!")
            in_maze = False
            break

    player.apply_gold(accumulated_rewards["gold"])
    player.gain_xp(accumulated_rewards["exp"])
    for aid in accumulated_rewards["aid"]:
        player.inventory.append(aid)

    typewriter(f"\nTrial Rewards Summary:")
    typewriter(f"- Gold: {accumulated_rewards['gold']}")
    typewriter(f"- Exp: {accumulated_rewards['exp']}")
    if accumulated_rewards["aid"]:
        typewriter("- Aid:")
        for aid in accumulated_rewards["aid"]:
            typewriter(f"  - {aid.name}")
    time.sleep(1)


def practice_mode(engine):
    """Standalone question drill outside of combat."""
    typewriter("\n=== Practice Mode ===")
    typewriter("Answer questions to review your material.")
    typewriter("Type 'quit' at any time to return to the menu.\n")

    correct = 0
    total   = 0
    wrong_log = []

    while True:
        q = engine.get_question()
        if q is None:
            typewriter("No questions loaded.")
            break

        q_type  = q["type"]
        answer  = q["answer"]
        category = {"TF": "True/False", "MC": "Multiple Choice",
                    "AR": "Arithmetic", "ID": "Identification", 
                    "FB": "Fill in the Blanks", "OD": "Ordering"}.get(q_type, q_type)

        typewriter(f"\n[{category}] {q['question']}")
        raw = _ask_answer(q, extra_choices=[{"label": "Quit", "value": "quit"}])

        if raw.lower() == "quit":
            break

        if raw.lower() == answer.lower():
            typewriter("Correct!")
            correct += 1
        else:
            typewriter(f"Wrong. The answer was: {answer}")
            wrong_log.append(q)

        total += 1
        typewriter(f"Score: {correct}/{total}")
        time.sleep(0.5)

    typewriter(f"\nPractice complete. Final score: {correct}/{total}")
    if wrong_log:
        typewriter("\nYou missed these:")
        for q in wrong_log:
            typewriter(f"  Q: {q['question']}")
            typewriter(f"  A: {q['answer']}")
    time.sleep(1)
