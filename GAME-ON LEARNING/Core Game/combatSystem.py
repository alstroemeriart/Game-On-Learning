"""Combat system module.

Manages turn-based combat flow including player/enemy turns, damage
calculation, status effect processing, and question resolution in combat.
"""

import random
import time

from ui import (
    typewriter, clear_screen, hp_bar, bus,
    input_handler, emit_player_stats
)
from combatCalc import calculate_damage, check_dodge, check_critical
from progression import (
    gain_mastery, mastery_multiplier, apply_skills, unlock_skills
)

# ── Combat result constants ────────────────────────────────────────────────────
# Returned by player_turn(), enemy_turn(), and the *_combat() functions
# so main.py can branch on the outcome without importing strings directly.
CONTINUE = "continue"
ESCAPED  = "escaped"
WIN      = "win"
DEATH    = "death"

# Maps short question-type codes to human-readable category names
CATEGORY_NAMES = {
    "TF": "True/False",
    "MC": "Multiple Choice",
    "AR": "Arithmetic",
    "ID": "Identification",
    "FB": "Fill in the Blanks",
    "OD": "Ordering",
}


# ── GUI helper functions ──────────────────────────────────────────────────────

def _set_action_ui(action=False, boss=False):
    """Enable or disable the action/boss button groups in the GUI.

    Emits bus events that the GUI listens for to show/hide the relevant
    button rows in the center panel.

    Args:
        action (bool): Whether to show standard action buttons (Attack, Ask, Aid, etc.).
        boss   (bool): Whether to show boss-specific action buttons.
    """
    bus.game_event("action_buttons", enabled=action)
    bus.game_event("boss_actions",   enabled=boss)


def _emit_enemy_panel(entity, role="enemy"):
    """Push the current enemy's full stat block to the GUI right panel.

    Called after any combat action that may change enemy stats so the GUI
    always reflects live data.

    Args:
        entity: Enemy, elite, or boss being displayed.
        role   (str): Label for theming — "enemy", "elite", or "boss".
    """
    bus.game_event(
        "enemy_update",
        target_name  = entity.name,
        role         = role,
        hp           = entity.hp,
        max_hp       = entity.max_hp,
        atk          = entity.atk,
        defense      = entity.defense,
        spd          = entity.spd,
        crit_chance  = getattr(entity, "crit_chance", 0),
        shield       = getattr(entity, "shield", 0),
        behavior     = getattr(entity, "behavior", ""),
        # List only effect names; the GUI doesn't need full objects
        status_effects=[e.name for e in getattr(entity, "status_effects", [])],
    )


def _clear_enemy_panel():
    """Clear the right-panel enemy display at the end of combat."""
    bus.game_event("enemy_clear")


# ── Display helpers ───────────────────────────────────────────────────────────

def damage_line(attacker_name, target, dmg):
    """Display a damage action with severity-based messaging.

    Thresholds:
      ≥ 25% max HP → "HEAVY HIT"
      ≥ 10% max HP → normal hit
      < 10% max HP → graze / glancing blow

    Args:
        attacker_name (str): Name of the attacking entity.
        target:              Entity taking damage (needs max_hp attribute).
        dmg:                 Damage amount dealt.
    """
    ratio = dmg / max(1, target.max_hp)

    if ratio >= 0.25:
        msg = f"HEAVY HIT! {attacker_name} deals {dmg} damage!"
    elif ratio >= 0.10:
        msg = f"{attacker_name} deals {dmg} damage."
    else:
        msg = f"{attacker_name} grazes for {dmg} damage."

    bus.say(msg)
    bus.combat_event(
        "damage",
        attacker = attacker_name,
        target   = target.name,
        amount   = dmg,
        severity = "heavy" if ratio >= 0.25 else "normal",
    )
    # Refresh the enemy panel after damage so HP bar updates
    if not hasattr(target, "streak"):   # enemies lack "streak"; players have it
        _emit_enemy_panel(target, role=getattr(target, "_panel_role", "enemy"))


def display_entity_stats(entity, role=None):
    """Print a full stat block for an entity to the narrative log.

    Also updates the enemy panel if a role is provided (so the GUI right
    panel matches the text log).

    Args:
        entity: Player or enemy character to display.
        role   (str, optional): GUI panel role ("enemy", "boss", "elite").
    """
    typewriter(f"\n--- {entity.name} ---")
    typewriter(f"HP:  {hp_bar(entity.hp, entity.max_hp)}")

    if entity.shield > 0:
        typewriter(f"Shield: {entity.shield}")

    typewriter(f"ATK: {entity.atk} | DEF: {entity.defense} | SPD: {entity.spd}")
    typewriter(f"CRIT: {int(entity.crit_chance * 100)}%")

    # Player-only fields
    if hasattr(entity, "streak"):
        typewriter(f"Streak: {entity.streak} (Longest: {entity.longest_streak})")
        typewriter(f"Focus:  {hp_bar(entity.focus, entity.max_focus, length=10)}")
    if hasattr(entity, "gold"):
        typewriter(f"Gold: {entity.gold}")

    # Status effects — show name and remaining duration
    if entity.status_effects:
        effects = ", ".join(f"{e.name}({e.duration})" for e in entity.status_effects)
        typewriter(f"Status: {effects}")
    else:
        typewriter("Status: None")

    if role is not None:
        # Store the role on the entity so damage_line() can reuse it
        setattr(entity, "_panel_role", role)
        _emit_enemy_panel(entity, role=role)

    time.sleep(0.3)


def _view_skills(player):
    """Display all player skills with their unlock status.

    Locked skills show current mastery progress toward the unlock threshold.

    Args:
        player: The MainCharacter instance.
    """
    typewriter("\n--- Your Skills ---")
    if not player.skills:
        typewriter("No skills available.")
        return

    for skill in player.skills:
        if skill.unlocked:
            typewriter(f"  [UNLOCKED] {skill.name} ({skill.tree} tree)")
        else:
            current = player.mastery.get(skill.tree, 0)
            # All skills unlock at mastery 5; show progress toward that threshold
            typewriter(f"  [locked]   {skill.name} ({skill.tree} mastery: {current}/5)")

    time.sleep(0.3)


# ── Question-asking logic ─────────────────────────────────────────────────────

def _ask_question(question_data, player):
    """Present one question to the player and return whether they answered correctly.

    Handles all 6 question types:
      TF  – True/False toggle
      MC  – Multiple choice with optional skill-based elimination
      AR  – Short numeric/text answer
      ID  – Identification (short text)
      FB  – Fill-in-the-blank phrase
      OD  – Ordering (arrange items by entering index sequence)

    Skill interactions:
      mc_eliminate  → removes one wrong option before the question is shown
      hint_active   → reveals the first character and length of the answer

    Debug mode skips all input and auto-answers correctly.

    Args:
        question_data (dict): Keys: type, question, answer, options (MC),
                              items (OD), difficulty.
        player:               MainCharacter instance.

    Returns:
        bool: True if the player's answer matches the correct answer.
    """
    # Block GUI auto-play while a combat question is active so the
    # auto-play button can't accidentally submit answers mid-question
    input_handler.set_in_combat_question(True)

    q_type   = question_data["type"]
    question = question_data["question"]
    answer   = question_data["answer"]

    # ── Debug / God-mode: always answer correctly without prompting ────────
    if getattr(player, "debug_mode", False):
        diff_label  = {1: "easy", 2: "medium", 3: "hard"}.get(
            question_data.get("difficulty", 1), "?")
        mastery_val = player.mastery.get(q_type, 0)
        next_ms     = ((mastery_val // 5) + 1) * 5
        typewriter(
            f"\n[{CATEGORY_NAMES.get(q_type, q_type)} | "
            f"Mastery: {mastery_val} → {next_ms} | {diff_label}]"
        )
        typewriter(f"[DEBUG AUTO-ANSWER] {question}")
        typewriter(f"[Correct Answer: {answer}]")
        input_handler.set_in_combat_question(False)
        return True

    # ── Show category / mastery header ────────────────────────────────────
    diff_label  = {1: "easy", 2: "medium", 3: "hard"}.get(
        question_data.get("difficulty", 1), "?")
    mastery_val = player.mastery.get(q_type, 0)
    next_ms     = ((mastery_val // 5) + 1) * 5
    typewriter(
        f"\n[{CATEGORY_NAMES.get(q_type, q_type)} | "
        f"Mastery: {mastery_val} → {next_ms} | {diff_label}]"
    )

    correct = False

    # ── True / False ──────────────────────────────────────────────────────
    if q_type == "TF":
        if player.hint_active:
            typewriter("[Hint: think carefully about whether this is always true]")
            player.hint_active = False

        typewriter(question)
        raw = input_handler.ask_choice(
            [
                {"label": "True",  "value": "True"},
                {"label": "False", "value": "False"},
            ],
            "(True/False) > ",
        )
        correct = raw.lower() == answer.lower()

    # ── Multiple Choice ───────────────────────────────────────────────────
    elif q_type == "MC":
        options = list(question_data["options"])

        # Skill: Eliminate One — remove one wrong option before display
        if getattr(player, "mc_eliminate", 0) > 0:
            wrong = [o for o in options if o != answer]
            if wrong:
                eliminated = random.choice(wrong)
                options.remove(eliminated)
                player.mc_eliminate = 0   # consume the one-time flag
                typewriter(f"[Skill] Eliminated: {eliminated}")

        # Hint: also eliminates one wrong option
        if player.hint_active:
            wrong = [o for o in options if o != answer]
            if wrong:
                eliminated = random.choice(wrong)
                options    = [o for o in options if o != eliminated]
                typewriter(f"[Hint: '{eliminated}' has been eliminated]")
            player.hint_active = False

        typewriter(question)
        for i, opt in enumerate(options, 1):
            typewriter(f"{i}. {opt}")

        raw = input_handler.ask_choice(
            [
                {"label": f"{i}. {opt}", "value": opt, "log": f"{i}. {opt}"}
                for i, opt in enumerate(options, 1)
            ],
            "> ",
        )

        # Allow numeric index as input (e.g. "2" instead of the option text)
        if raw.isdigit():
            try:
                raw = options[int(raw) - 1]
            except (ValueError, IndexError):
                raw = ""   # invalid index → empty string → wrong answer

        correct = raw.lower() == answer.lower()

    # ── Arithmetic / Identification (both accept typed text answers) ──────
    elif q_type in ("AR", "ID"):
        if player.hint_active:
            typewriter(f"[Hint: starts with '{answer[0]}', {len(answer)} character(s)]")
            player.hint_active = False
        raw     = input_handler.ask(f"{question} > ")
        correct = raw.lower() == answer.lower()

    # ── Fill in the Blank ─────────────────────────────────────────────────
    elif q_type == "FB":
        if player.hint_active:
            typewriter(f"[Hint: starts with '{answer[0]}', {len(answer)} character(s)]")
            player.hint_active = False
        typewriter(question)
        raw     = input_handler.ask("> ")
        correct = raw.lower() == answer.lower()

    # ── Ordering ──────────────────────────────────────────────────────────
    elif q_type == "OD":
        items    = question_data["items"]
        shuffled = items[:]
        random.shuffle(shuffled)   # randomise display order every time

        typewriter(question)
        for i, item in enumerate(shuffled, 1):
            typewriter(f"  {i}. {item}")
        typewriter("Enter the correct order as numbers (e.g. 3,1,4,2):")

        try:
            raw   = input_handler.ask("> ")
            # Convert "3,1,4,2" → [2, 0, 3, 1] (0-indexed)
            order = [int(x.strip()) - 1 for x in raw.split(",")]
            if len(order) != len(items):
                correct = False   # wrong number of entries → auto-wrong
            else:
                player_seq  = [shuffled[i] for i in order]
                # The stored answer is a comma-separated list of 1-based indices
                correct_seq = [items[int(i) - 1] for i in answer.split(",")]
                correct     = (player_seq == correct_seq)
        except (ValueError, IndexError):
            correct = False   # malformed input → treat as wrong

    else:
        # Unknown question type — skip gracefully rather than crashing
        typewriter(f"[Warning] Unknown question type '{q_type}' — skipping.")
        input_handler.set_in_combat_question(False)
        return False

    # Re-enable GUI auto-play after the question is resolved
    input_handler.set_in_combat_question(False)
    return correct


def _apply_correct(player, q_type, enemy, engine):
    """Handle all consequences of a correct answer.

    In order:
      1. Gain mastery + increment streak
      2. Gain focus (scales with WIS)
      3. Check for skill unlocks at mastery milestones
      4. Apply class-specific passive bonus
      5. Calculate and deal damage to the enemy (with skill modifiers)

    Args:
        player: MainCharacter instance.
        q_type: Question type that was answered correctly.
        enemy:  Current enemy (may be None in practice mode).
        engine: LearningEngine (used to check for bonus skill events).
    """
    typewriter("Correct!")

    # ── Mastery + streak ──────────────────────────────────────────────────
    gain_mastery(player, q_type)
    player.streak        = player.streak + 1
    player.longest_streak = max(player.longest_streak, player.streak)
    unlock_skills(player)   # check if any skills just crossed their mastery threshold

    # ── Focus gain (correct answers fill the focus bar) ───────────────────
    focus_gain  = 10 + int(player.wisdom * 0.2)   # WIS scales how fast focus fills
    player.focus = min(player.max_focus, player.focus + focus_gain)
    typewriter(f"Streak: {player.streak} | Focus: {player.focus}/{player.max_focus}")

    # Optional narrative flavor text and streak commentary
    try:
        from narrative import show_streak_comment, show_correct_flavor
        show_streak_comment(player.streak)
        show_correct_flavor()
    except ImportError:
        pass

    # ── Class passives ────────────────────────────────────────────────────
    passive = getattr(player, "class_passive", "")

    if passive == "bloodlust":
        # Berserker: permanently gain +1 ATK per correct answer, up to 10 stacks
        if player.bloodlust_stacks < 10:
            player.atk             += 1
            player.bloodlust_stacks += 1
            typewriter(f"[Bloodlust] ATK permanently increased to {player.atk}!")

    elif passive == "momentum":
        # Duelist: crit bonus scales with streak; consumed by next check_critical() call
        bonus                 = min(0.02 * player.streak, 0.30)
        player._momentum_bonus = bonus
        typewriter(f"[Momentum] Crit bonus this strike: +{int(bonus * 100)}%")

    elif passive == "luck":
        # Gambler: chain of independent low-probability procs
        if random.random() < 0.05:
            gold = random.randint(5, 30)
            player.gold += gold
            typewriter(f"[Luck] Found {gold} gold!")
        if random.random() < 0.03:
            player.hint_active = True
            typewriter("[Luck] Next question has a hint!")
        if random.random() < 0.02:
            player.streak += 1
            typewriter("[Luck] Streak +1!")
        if random.random() < 0.01:
            player.focus = min(player.max_focus, player.focus + 20)
            typewriter("[Luck] Focus +20!")
        if random.random() < 0.005 and enemy is not None and enemy.is_alive():
            typewriter("[Luck] Chance strikes your enemy!")
            enemy.take_dmg(max(1, int(enemy.max_hp * 0.05)))
            _emit_enemy_panel(enemy, role=getattr(enemy, "_panel_role", "enemy"))

    # ── Mastery milestone notification ────────────────────────────────────
    mastery_val = player.mastery.get(q_type, 0)
    if mastery_val > 0 and mastery_val % 5 == 0:
        typewriter(f"Mastery milestone! {CATEGORY_NAMES.get(q_type, q_type)}: {mastery_val}")

    emit_player_stats(player)

    # ── Deal damage to enemy ──────────────────────────────────────────────
    if enemy is not None and not check_dodge(player, enemy):
        # Base damage calculation (slightly higher variance for player attacks)
        dmg, is_crit = calculate_damage(player, enemy, 1, 5)

        # Apply mastery damage multiplier for this question type
        dmg = int(dmg * mastery_multiplier(player, q_type))

        # Pass through skill system in case any unlocked skill modifies damage
        ctx = {"type": "attack", "q_type": q_type, "damage": dmg, "correct": True}
        apply_skills(player, ctx)
        dmg = ctx["damage"]   # retrieve (possibly modified) damage from context

        # Scholar's Burden run modifier doubles all attack damage
        if getattr(player, "run_modifier", "") == "scholar":
            dmg = int(dmg * 2)
            typewriter("[Scholar's Burden] Knowledge empowers your strike!")

        enemy.take_dmg(dmg)
        if is_crit:
            typewriter("CRITICAL HIT!")
        damage_line(player.name, enemy, dmg)

    elif enemy is not None:
        typewriter(f"{enemy.name} dodged the empowered strike!")


def _apply_incorrect(player, q_type, enemy, engine, question_data):
    """Handle streak penalty, focus loss, and punishment attack after a wrong answer.

    Args:
        player:        MainCharacter instance.
        q_type:        Question type that was answered incorrectly.
        enemy:         Current enemy (may be None).
        engine:        LearningEngine (used to record wrong answers for review).
        question_data: Full question dict (needed by engine.record_wrong).
    """
    typewriter("Incorrect!")

    # Record in learning engine and check for repeat-wrong review prompt
    if engine is not None:
        engine.record_wrong(question_data)
        repeat = engine.get_consecutive_wrong()
        if repeat:
            # Two consecutive wrong answers on the same question → show the answer
            typewriter("\n[This question came up twice in a row.]")
            typewriter(f"  Q: {repeat['question']}")
            typewriter(f"  A: {repeat['correct_answer']}")
            typewriter("[Take a moment to remember it.]")
            time.sleep(1.5)

    # Optional wrong-answer flavor text
    try:
        from narrative import show_wrong_flavor
        show_wrong_flavor()
    except ImportError:
        pass

    passive = getattr(player, "class_passive", "")

    if passive == "fortress":
        # Sentinel: wrong answers never trigger a punishment attack
        typewriter("[Fortress] Your defenses hold — no punishment attack.")
    else:
        # Cursed Knowledge modifier deals extra HP damage on wrong answers
        if getattr(player, "run_modifier", "") == "cursed":
            player.take_dmg(10)
            typewriter("[Cursed Knowledge] -10 HP for wrong answer!")

        # Halve the streak unless a StreakGuard is active
        if player.streak_protected:
            typewriter("Your streak was protected!")
            player.streak_protected = False   # consume the protection
        else:
            player.streak = player.streak // 2   # integer division floors automatically

        # Focus also decreases on wrong answers to slow focus-ability access
        player.focus = max(0, player.focus - 15)
        typewriter(f"Streak → {player.streak} | Focus → {player.focus}/{player.max_focus}")

        # Enemy counter-attacks (unless the player dodges)
        if enemy is not None and not check_dodge(enemy, player):
            dmg, is_crit = calculate_damage(enemy, player, 0, 3)
            player.take_dmg(dmg)
            if is_crit:
                typewriter("Enemy CRITICAL HIT!")
            damage_line(enemy.name, player, dmg)
        else:
            typewriter("You dodged the punishment attack!")

    emit_player_stats(player)

    # Track accuracy stats for the session summary
    stats = getattr(player, "session_stats", None)
    if stats:
        stats.record(q_type, False)


# ── Player action helpers ─────────────────────────────────────────────────────

def choice_attack(player, enemy):
    """Direct physical attack that costs 2 AP but needs no question.

    Args:
        player: MainCharacter attacking.
        enemy:  Target enemy.
    """
    typewriter(f"\n{player.name} attacks {enemy.name}!")
    time.sleep(0.5)

    if check_dodge(player, enemy):
        typewriter(f"{enemy.name} dodged the attack!")
        return

    dmg, is_crit = calculate_damage(player, enemy)
    enemy.take_dmg(dmg)
    if is_crit:
        typewriter("CRITICAL HIT!")
    damage_line(player.name, enemy, dmg)
    time.sleep(1)


def choice_ask(player, enemy, engine):
    """Fetch a question, resolve it, then apply correct/incorrect consequences.

    Costs 1 AP.  The player can ask multiple questions per turn.

    Args:
        player: MainCharacter instance.
        enemy:  Current enemy.
        engine: LearningEngine providing the question.
    """
    question_data = engine.get_random_question()
    if not question_data:
        typewriter("No questions loaded.")
        return

    q_type  = question_data["type"]
    correct = _ask_question(question_data, player)

    if correct:
        _apply_correct(player, q_type, enemy, engine)
        # Track for session summary
        stats = getattr(player, "session_stats", None)
        if stats:
            stats.record(q_type, True)
    else:
        _apply_incorrect(player, q_type, enemy, engine, question_data)

    # Trigger focus ability if the bar just hit max
    if correct and player.focus >= player.max_focus:
        _use_focus_ability(player, enemy)


def _use_focus_ability(player, enemy):
    """Let the player choose one of three focus abilities when the bar is full.

    Abilities:
      1. Massive Strike — double-damage attack
      2. Heal 20% HP
      3. Protect Streak — next wrong answer won't halve streak

    Args:
        player: MainCharacter with a full focus bar.
        enemy:  Current enemy target.
    """
    typewriter("\nFocus Ability Ready!")
    typewriter("1. Massive Strike (2x dmg)")
    typewriter("2. Heal 20% HP")
    typewriter("3. Protect Streak")

    # Debug: always pick Massive Strike to maximise damage in testing
    if getattr(player, "debug_mode", False):
        ability = "1"
        typewriter("[DEBUG AUTO-PLAY] Choosing: 1. Massive Strike")
    else:
        ability = input_handler.ask_choice(
            [
                {"label": "1. Massive Strike (2x dmg)", "value": "1"},
                {"label": "2. Heal 20% HP",             "value": "2"},
                {"label": "3. Protect Streak",           "value": "3"},
            ],
            "> ",
        )

    if ability == "1":
        dmg, _ = calculate_damage(player, enemy, 1, 5)
        dmg   *= 2                              # double damage
        enemy.take_dmg(dmg)
        player.focus = 0                        # consume all focus
        damage_line("Massive Strike", enemy, dmg)

    elif ability == "2":
        heal         = int(player.max_hp * 0.2)
        player.hp    = min(player.max_hp, player.hp + heal)
        player.focus = 0
        typewriter(f"You healed {heal} HP!")

    elif ability == "3":
        player.streak_protected = True
        player.focus            = 0
        typewriter("Your next wrong answer will not reduce streak.")

    emit_player_stats(player)


def choice_aid(player):
    """Open the inventory and let the player use one item.

    Costs 1 AP.  Items that require a target (e.g. PoisonBomb) are passed
    None for target here because combat items are handled through their own
    use() method which is target-aware in the items module.

    Args:
        player: MainCharacter instance.
    """
    if not player.inventory:
        typewriter("You have no aid!")
        return

    typewriter("\nYour Inventory:")
    for i, aid in enumerate(player.inventory, 1):
        desc = getattr(aid, "description", "")
        typewriter(f"{i}. {aid.name} — {desc}")
    typewriter(f"{len(player.inventory) + 1}. Cancel")

    try:
        choice = int(input_handler.ask_choice(
            [
                {"label": f"{i}. {aid.name}", "value": str(i)}
                for i, aid in enumerate(player.inventory, 1)
            ] + [
                {"label": f"{len(player.inventory) + 1}. Cancel",
                 "value": str(len(player.inventory) + 1)},
            ],
            "Choose an aid: ",
        ))
    except ValueError:
        typewriter("Invalid choice.")
        return

    if choice == len(player.inventory) + 1:
        typewriter("Cancelled.")
        return

    if 1 <= choice <= len(player.inventory):
        aid = player.inventory.pop(choice - 1)   # remove from inventory on use
        typewriter(aid.use(player))
        emit_player_stats(player)
    else:
        typewriter("Invalid choice.")


def choice_abstain(player, enemy):
    """Attempt to flee the battle at the cost of gold, streak, and status debuffs.

    Success probability: 50% + SPD difference × 3%, capped at [10%, 90%].
    Iron Will run modifier blocks all escape attempts.

    Args:
        player: MainCharacter instance.
        enemy:  Current enemy (used for SPD comparison).

    Returns:
        str: ESCAPED if successful, CONTINUE otherwise.
    """
    typewriter("\nAbstaining has consequences:")
    typewriter("  - Lose 5-15 gold")
    typewriter("  - Streak is halved")
    typewriter("  - Vulnerable and Attack Down for 2 turns")

    confirm = input_handler.ask_choice(
        [
            {"label": "Yes", "value": "y"},
            {"label": "No",  "value": "n"},
        ],
        "Are you sure? (y/n) > ",
    )
    if confirm.lower() != "y":
        typewriter("You hold your ground.")
        return CONTINUE

    # Iron Will modifier forbids escaping
    if getattr(player, "run_modifier", "") == "ironwill":
        typewriter("[Iron Will] You cannot escape. Face your enemy!")
        return CONTINUE

    typewriter(f"\n{player.name} attempts to abstain away...")
    time.sleep(1)

    # Escape chance: base 50%, +/- 3% per SPD difference, bounded to [10%, 90%]
    run_chance = min(0.9, max(0.1, 0.5 + (player.spd - enemy.spd) * 0.03))

    if random.random() < run_chance:
        typewriter("You escaped, but at a cost!")
        lost_gold    = min(player.gold, random.randint(5, 15))
        player.gold -= lost_gold
        player.streak = max(0, player.streak // 2)

        # Apply punishment debuffs
        from statusEffects import AttackDebuff, Vulnerable
        for effect in [AttackDebuff(5, 2), Vulnerable(2)]:
            effect.on_apply(player)
            player.status_effects.append(effect)

        typewriter(f"Lost {lost_gold} gold! Streak halved! Vulnerable for 2 turns.")
        emit_player_stats(player)
        time.sleep(1)
        return ESCAPED
    else:
        typewriter("Failed to escape!")
        # Enemy gets a free counter-attack on failed escape
        if not check_dodge(enemy, player):
            dmg, is_crit = calculate_damage(enemy, player, 0, 3)
            player.take_dmg(dmg)
            if is_crit:
                typewriter("Enemy CRITICAL HIT!")
            damage_line(enemy.name, player, dmg)
        else:
            typewriter("You dodged the enemy's counterattack!")
        emit_player_stats(player)
        time.sleep(1)
        return CONTINUE


# ── Player turn ────────────────────────────────────────────────────────────────

def player_turn(player, enemy, learning_engine):
    """Run the player's full turn loop until all AP are spent or combat ends.

    Action costs:
      1 – Attack   (2 AP)
      2 – Ask      (1 AP, can act again afterward)
      3 – Aid      (1 AP)
      4 – Abstain  (0 AP, exits turn)
      5 – Skills   (free, view only)

    Returns:
        str: CONTINUE, ESCAPED, or (implicitly) falls through on enemy death.
    """
    # Stunned players skip their entire turn
    if getattr(player, "is_stunned", False):
        _set_action_ui(False, False)
        typewriter(f"{player.name} is stunned and cannot act!")
        return CONTINUE

    player.action_points = player.max_action_points   # refresh AP at turn start

    while player.action_points > 0:
        typewriter(f"\n{player.name}'s turn! AP: {player.action_points}/{player.max_action_points}")
        typewriter("1. Attack  (costs 2 AP)")
        typewriter("2. Ask     (costs 1 AP — can act again after)")
        typewriter(f"3. Aid     (costs 1 AP) [{len(player.inventory)} available]")
        typewriter("4. Abstain (costs 0 AP — escape with penalty)")
        typewriter("5. Skills  (free — view unlocked abilities)")

        # Debug mode: bias toward Ask (answer questions) with some Attack variety
        if getattr(player, "debug_mode", False):
            choice = "2" if random.random() < 0.6 else "1"
            typewriter(f"[DEBUG AUTO-PLAY] Choosing: {choice}")
            time.sleep(0.3)
        else:
            _set_action_ui(True, False)    # show action buttons in GUI
            choice = input_handler.ask("> ")
            _set_action_ui(False, False)   # hide buttons while processing

        if choice == "1":
            if player.action_points < 2:
                typewriter("Not enough AP! (need 2)")
                continue
            choice_attack(player, enemy)
            player.action_points = 0      # Attack costs all remaining AP

        elif choice == "2":
            choice_ask(player, enemy, learning_engine)
            player.action_points -= 1     # Ask costs 1 AP; player may act again

        elif choice == "3":
            choice_aid(player)
            player.action_points -= 1

        elif choice == "4":
            return choice_abstain(player, enemy)   # may return ESCAPED

        elif choice == "5":
            _view_skills(player)
            continue   # viewing skills is free; don't decrement AP

        else:
            typewriter("Invalid choice. Enter 1-5.")
            continue

        # Exit the AP loop early if either combatant is already dead
        if enemy.hp <= 0 or player.hp <= 0:
            break

    return CONTINUE


# ── Enemy turn ────────────────────────────────────────────────────────────────

def enemy_turn(enemy, player):
    """Run the enemy's turn based on its behavior pattern.

    Behavior patterns:
      aggressive – two weaker hits per turn
      evasive    – 30% chance to boost dodge instead of attacking
      defensive  – 40% chance to raise defense before attacking
      neutral    – single standard attack

    Defense and dodge bonuses set in this turn are cleared at the top of
    the *next* enemy turn to keep the bonuses short-lived.

    Returns:
        str: Always CONTINUE (enemies can't escape or die during their own turn).
    """
    typewriter(f"\n{enemy.name}'s turn...")
    time.sleep(1)

    # Clear any temporary defense/dodge bonuses from the previous turn
    if enemy.defense_bonus > 0:
        enemy.defense      -= enemy.defense_bonus
        enemy.defense_bonus = 0
    if enemy.behavior == "evasive" and enemy.dodge_modifier > 0:
        enemy.dodge_modifier = max(0.0, enemy.dodge_modifier - 0.2)

    # Stunned enemies skip their turn completely
    if getattr(enemy, "is_stunned", False):
        typewriter(f"{enemy.name} is stunned and cannot act!")
        return CONTINUE

    behavior = enemy.behavior

    # ── Aggressive: two half-strength hits ────────────────────────────────
    if behavior == "aggressive":
        typewriter(f"{enemy.name} attacks furiously!")
        for _ in range(2):
            if player.hp <= 0:
                break
            if not check_dodge(enemy, player):
                dmg, is_crit = calculate_damage(enemy, player, -1, 1)
                dmg          = max(1, dmg // 2)   # half-damage per hit
                player.take_dmg(dmg)
                if is_crit:
                    typewriter("CRITICAL HIT!")
                damage_line(enemy.name, player, dmg)
            else:
                typewriter(f"{player.name} sidesteps the flurry!")
        emit_player_stats(player)
        return CONTINUE

    # ── Evasive: 30% chance to boost own dodge ────────────────────────────
    if behavior == "evasive" and random.random() < 0.3:
        typewriter(f"{enemy.name} shifts into a defensive stance!")
        enemy.dodge_modifier += 0.2   # +20% dodge for this turn
        return CONTINUE

    # ── Defensive: 40% chance to add temporary defense ───────────────────
    if behavior == "defensive" and random.random() < 0.4:
        typewriter(f"{enemy.name} braces for impact!")
        enemy.defense      += 3
        enemy.defense_bonus = 3   # track so it's removed next turn

    # ── Standard single attack (shared by all behaviors as fallback) ──────
    if check_dodge(enemy, player):
        typewriter(f"{player.name} dodged the attack!")
        return CONTINUE

    dmg, is_crit = calculate_damage(enemy, player, -1, 2)
    player.take_dmg(dmg)
    if is_crit:
        typewriter("Enemy lands a CRITICAL HIT!")
    damage_line(enemy.name, player, dmg)
    emit_player_stats(player)
    time.sleep(1)
    return CONTINUE


# ── Status effect processor ───────────────────────────────────────────────────

def process_status_effects(entity):
    """Advance all active status effects on entity by one turn.

    Iterates a *copy* of the list so effects that remove themselves during
    on_expire don't corrupt the iteration.

    Args:
        entity: Any Spawn-derived entity with a status_effects list.
    """
    for effect in entity.status_effects[:]:   # iterate copy to allow safe removal
        effect.on_turn_start(entity)
        effect.on_turn_end(entity)
        if effect.is_expired():
            effect.on_expire(entity)
            entity.status_effects.remove(effect)


# ── Standard combat loop ──────────────────────────────────────────────────────

def _combat_loop(player, enemy, learning_engine):
    """Run a full standard combat until one side dies or the player escapes.

    Returns:
        tuple[str, bool]: (result_constant, no_damage_taken)
    """
    hp_before = player.hp   # track for "no damage" flawless victory check

    while True:
        display_entity_stats(player)
        display_entity_stats(enemy, role="enemy")

        result = player_turn(player, enemy, learning_engine)

        if result == ESCAPED:
            _set_action_ui(False, False)
            _clear_enemy_panel()
            return ESCAPED, False

        if enemy.hp <= 0 or player.hp <= 0:
            break

        process_status_effects(player)
        emit_player_stats(player)
        if enemy.hp <= 0 or player.hp <= 0:
            break

        enemy_turn(enemy, player)
        process_status_effects(enemy)
        if enemy.hp <= 0 or player.hp <= 0:
            break

    if player.hp <= 0:
        _set_action_ui(False, False)
        _clear_enemy_panel()
        typewriter("You were defeated...")
        time.sleep(1)
        return DEATH, False

    _set_action_ui(False, False)
    _clear_enemy_panel()
    typewriter(f"{enemy.name} defeated!")
    time.sleep(1)

    no_damage = (player.hp >= hp_before)   # True only if HP never dropped

    typewriter(f"\n--- Battle Summary ---")
    typewriter(f"HP: {player.hp}/{player.max_hp} | Streak: {player.streak}")
    if no_damage:
        typewriter("Flawless victory! No damage taken.")
    time.sleep(0.5)

    return WIN, no_damage


# ── Elite combat (multi-phase) ────────────────────────────────────────────────

def elite_combat(player, enemy, learning_engine, bestiary=None):
    """Three-phase elite combat that scales the enemy at HP thresholds.

    Phase 1: normal stats
    Phase 2 (HP ≤ 66%): ATK +4
    Phase 3 (HP ≤ 33%): DEF +3

    Returns:
        str: WIN, DEATH, or ESCAPED constant.
    """
    phase = 1
    typewriter(f"\n*** ELITE ENCOUNTER: {enemy.name}! ***")
    typewriter("Watch for phase shifts!")
    time.sleep(1)

    while enemy.is_alive() and player.is_alive():
        hp_ratio = enemy.hp / enemy.max_hp

        # Phase transitions — only trigger once each
        if phase == 1 and hp_ratio <= 0.66:
            phase     = 2
            enemy.atk += 4
            typewriter(f"\n{enemy.name} enters a RAGE! ATK increased!")
            time.sleep(1)
        elif phase == 2 and hp_ratio <= 0.33:
            phase          = 3
            enemy.defense += 3
            typewriter(f"\n{enemy.name} is DESPERATE! Defense hardened!")
            time.sleep(1)

        display_entity_stats(player)
        display_entity_stats(enemy, role="elite")

        result = player_turn(player, enemy, learning_engine)
        emit_player_stats(player)

        if result == ESCAPED:
            _set_action_ui(False, False)
            _clear_enemy_panel()
            typewriter("You escaped the elite battle!")
            return ESCAPED

        if enemy.hp <= 0:
            _set_action_ui(False, False)
            _clear_enemy_panel()
            typewriter(f"{enemy.name} defeated!")
            if bestiary:
                bestiary.record_kill(enemy.name)
            time.sleep(1)
            return WIN

        if player.hp <= 0:
            _set_action_ui(False, False)
            _clear_enemy_panel()
            typewriter("You were defeated...")
            time.sleep(1)
            return DEATH

        enemy_turn(enemy, player)
        process_status_effects(player)
        process_status_effects(enemy)

        if enemy.hp <= 0:
            _set_action_ui(False, False)
            _clear_enemy_panel()
            if bestiary:
                bestiary.record_kill(enemy.name)
            return WIN

        if player.hp <= 0:
            _set_action_ui(False, False)
            _clear_enemy_panel()
            return DEATH

    # Fallback in case the while condition exits without a return
    _set_action_ui(False, False)
    _clear_enemy_panel()
    if enemy.hp <= 0 and bestiary:
        bestiary.record_kill(enemy.name)
    return WIN if enemy.hp <= 0 else DEATH


# ── Boss combat (question-gated actions) ──────────────────────────────────────

def boss_combat(player, boss, learning_engine, bestiary=None):
    """Boss fight where every player action requires answering a question.

    Three phases triggered by boss HP thresholds:
      Phase 2 (HP ≤ 66%): boss ATK +5
      Phase 3 (HP ≤ 33%): boss ATK +5, CRIT +15% (capped at 50%)

    Boss tells hint at the ideal action for maximum damage/safety but
    answering correctly is always required to execute.

    Returns:
        str: WIN or DEATH constant.
    """
    typewriter(f"\n{'='*50}")
    typewriter(f"  BOSS ENCOUNTER: {boss.name}")
    typewriter(f"{'='*50}")
    typewriter("Every action requires answering a question.")
    typewriter("Answer correctly to act. Answer wrong — face the consequences.")
    time.sleep(2)

    # Each tell is (flavor_text, ideal_choice_number)
    # ideal_choice is the mechanically best response to that tell
    BOSS_TELLS = [
        ("The boss winds up for a devastating blow...", "2"),   # Evade is ideal
        ("The boss looks exposed and off-balance...",   "1"),   # Strike is ideal
        ("Dark energy charges around the boss...",      "1"),
        ("The boss begins to slowly regenerate...",     "1"),
        ("The boss locks eyes on you, unblinking...",   "2"),
        ("The boss staggers — now is your chance!",     "1"),
    ]

    phase            = 1
    player.dodge_next = False

    while boss.is_alive() and player.is_alive():
        hp_ratio = boss.hp / boss.max_hp

        # Phase escalation
        if phase == 1 and hp_ratio <= 0.66:
            phase    = 2
            boss.atk += 5
            typewriter(f"\n{boss.name} PHASE 2: grows more powerful!")
            time.sleep(1)
        elif phase == 2 and hp_ratio <= 0.33:
            phase              = 3
            boss.atk          += 5
            boss.crit_chance   = min(boss.crit_chance + 0.15, 0.5)   # cap at 50%
            typewriter(f"\n{boss.name} PHASE 3: final form unleashed!")
            time.sleep(1)

        tell_text, ideal = random.choice(BOSS_TELLS)
        typewriter(f"\n{tell_text}")
        time.sleep(0.5)

        display_entity_stats(player)
        display_entity_stats(boss, role="boss")

        typewriter(f"\n{player.name}'s turn:")
        typewriter("1. Strike  — deal damage")
        typewriter("2. Evade   — dodge next attack")
        typewriter("3. Restore — heal 15% HP")
        typewriter("4. Focus   — use Focus ability")

        _set_action_ui(False, True)    # show boss-specific action buttons
        choice = input_handler.ask("> ")
        _set_action_ui(False, False)

        if choice not in ("1", "2", "3", "4"):
            typewriter("Invalid choice. You hesitate — boss attacks!")
            _boss_attack(boss, player)
            emit_player_stats(player)
            continue

        # Always ask a hard (difficulty 3) question for boss actions
        q = learning_engine.get_question(difficulty=3) or learning_engine.get_question()
        if q is None:
            typewriter("No questions loaded. Boss attacks.")
            _boss_attack(boss, player)
            emit_player_stats(player)
            continue

        correct      = _ask_question(q, player)
        tell_matched = (choice == ideal)   # True if player read the tell correctly

        # Apply streak/focus changes regardless of which action was chosen
        if correct:
            player.streak         = player.streak + 1
            player.longest_streak = max(player.longest_streak, player.streak)
            focus_gain            = 10 + int(player.wisdom * 0.2)
            player.focus          = min(player.max_focus, player.focus + focus_gain)
            typewriter(f"Correct! Streak: {player.streak} | Focus: {player.focus}/{player.max_focus}")
        else:
            typewriter(f"Wrong! The answer was: {q['answer']}")
            if player.streak_protected:
                typewriter("Streak protected!")
                player.streak_protected = False
            else:
                player.streak = player.streak // 2
            player.focus = max(0, player.focus - 10)

        emit_player_stats(player)

        # ── Resolve the chosen action ──────────────────────────────────────
        if choice == "1":   # Strike
            if correct:
                dmg, is_crit = calculate_damage(player, boss,
                                                variance_low=2, variance_high=6)
                dmg = int(dmg * 1.5)   # bonus damage for boss fights
                if tell_matched:
                    dmg = int(dmg * 1.3)   # extra bonus for reading the tell
                    typewriter("Perfect read! Bonus damage!")
                boss.take_dmg(dmg)
                if is_crit:
                    typewriter("CRITICAL STRIKE!")
                damage_line(player.name, boss, dmg)
            else:
                typewriter("Your strike misses!")
                if tell_matched:
                    typewriter("(Good read, wrong answer.)")
                _boss_attack(boss, player)   # boss punishes the miss

        elif choice == "2":   # Evade
            if correct:
                player.dodge_next = True   # will block the next boss_attack call
                msg = "Perfect read! Next attack will be dodged!" if tell_matched \
                      else "You prepare a dodge."
                typewriter(msg)
            else:
                typewriter("No dodge!")
                if tell_matched:
                    typewriter("(Good read, wrong answer.)")

        elif choice == "3":   # Restore
            if correct:
                heal = int(player.max_hp * 0.15)
                player.heal(heal)
                typewriter(f"You recover {heal} HP! ({player.hp}/{player.max_hp})")
            else:
                typewriter("Your concentration breaks. No healing!")

        elif choice == "4":   # Focus ability
            if player.focus >= player.max_focus:
                if correct:
                    _use_focus_ability(player, boss)
                else:
                    typewriter("Focus broken! No ability.")
            else:
                typewriter(f"Focus not ready ({player.focus}/{player.max_focus}).")

        emit_player_stats(player)

        # Check win/loss after player's action
        if boss.hp <= 0:
            _clear_enemy_panel()
            typewriter(f"\n{boss.name} has been defeated!")
            if bestiary:
                bestiary.record_kill(boss.name)
            time.sleep(1)
            return WIN

        if player.hp <= 0:
            _clear_enemy_panel()
            typewriter("\nYou were defeated by the boss...")
            time.sleep(1)
            return DEATH

        # Boss counter-attack at end of each round
        process_status_effects(player)
        emit_player_stats(player)

        if player.hp <= 0:
            _clear_enemy_panel()
            return DEATH
        if boss.hp <= 0:
            _clear_enemy_panel()
            if bestiary:
                bestiary.record_kill(boss.name)
            return WIN

        _boss_attack(boss, player)
        emit_player_stats(player)
        process_status_effects(boss)

        if player.hp <= 0:
            _clear_enemy_panel()
            return DEATH

    _set_action_ui(False, False)
    _clear_enemy_panel()
    return WIN if boss.hp <= 0 else DEATH


def _boss_attack(boss, player):
    """Execute a single boss attack, respecting dodge_next and check_dodge.

    dodge_next is consumed by this call so it only blocks one attack.

    Args:
        boss:   The boss entity attacking.
        player: MainCharacter being attacked.
    """
    # Player pre-set a guaranteed dodge (from the Evade action)
    if player.dodge_next:
        typewriter(f"You dodge {boss.name}'s attack!")
        player.dodge_next = False   # consume the one-time dodge
        return

    # Normal dodge roll
    if check_dodge(boss, player):
        typewriter(f"You narrowly dodge {boss.name}'s strike!")
        return

    dmg, is_crit = calculate_damage(boss, player, variance_low=0, variance_high=4)
    player.take_dmg(dmg)
    if is_crit:
        typewriter(f"{boss.name} lands a CRITICAL HIT!")
    damage_line(boss.name, player, dmg)
    typewriter(f"({player.hp}/{player.max_hp} HP remaining)")
    emit_player_stats(player)
    time.sleep(0.5)