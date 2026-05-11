"""Character progression and skill system.

Handles mastery growth, mastery-based damage multipliers, skill definitions,
skill unlocking, and applying skill effects during combat.
"""


# ─────────────────────────────────────────────────────────────────────────────
# MASTERY SYSTEM
# Each of the 6 question types (TF, MC, AR, ID, FB, OD) has its own mastery
# counter that grows by 1 per correct answer. High mastery unlocks skills and
# boosts damage through the mastery_multiplier() formula.
# ─────────────────────────────────────────────────────────────────────────────

def gain_mastery(player, q_type: str, amount: int = 1) -> None:
    """Increase the player's mastery in a specific question type.

    Silently ignores unknown question types so new types can be introduced
    without breaking existing save files or raising KeyErrors.

    Args:
        player: MainCharacter instance with a ``mastery`` dict attribute.
        q_type: Question-type key, e.g. ``"TF"``, ``"MC"``, ``"AR"``.
        amount: Mastery points to add (default 1).
    """
    if q_type not in player.mastery:
        return   # unknown type — ignore safely rather than crash
    player.mastery[q_type] += amount


def mastery_multiplier(player, q_type: str) -> float:
    """Calculate the damage multiplier granted by mastery in a question type.

    Uses linear scaling: every mastery point adds 1.5% bonus damage.
    At mastery 50 this yields a ×1.75 multiplier (+75% damage).

    Args:
        player: MainCharacter with a ``mastery`` dict.
        q_type: Question-type key to look up.

    Returns:
        float: Multiplier ≥ 1.0 (e.g. 1.75 at mastery 50).
    """
    return 1 + (player.mastery.get(q_type, 0) * 0.015)


# ─────────────────────────────────────────────────────────────────────────────
# SKILL SYSTEM
# Skills are passive combat bonuses tied to question-type mastery trees.
# Each skill starts locked and becomes available once the player's mastery
# in that tree reaches the required threshold (≥ 5 by default).
# ─────────────────────────────────────────────────────────────────────────────

class Skill:
    """A learnable combat skill tied to a specific question-type mastery tree.

    Attributes:
        name      (str):      Display name shown to the player.
        tree      (str):      Associated question type (e.g. ``"TF"``).
        effect    (callable): ``effect(player, context)`` — modifies combat context in place.
        condition (callable): ``condition(player) -> bool`` — True when skill can unlock.
        unlocked  (bool):     Whether this skill has been unlocked yet.
    """

    def __init__(self, name: str, tree: str, effect, condition) -> None:
        self.name      = name
        self.tree      = tree
        self.effect    = effect
        self.condition = condition
        self.unlocked  = False   # all skills start locked; unlock via unlock_skills()


# ── Individual skill effect functions ────────────────────────────────────────
# Each function receives (player, context) and modifies context or player in place.
# context is a dict with keys: type, q_type, damage, heal, correct.

def reflex_dodge_effect(player, context: dict) -> None:
    """Skill: Reflex Dodge — add +10% dodge chance after a correct TF answer.

    Modifies player.dodge_modifier, which is summed inside check_dodge().

    Args:
        player:  MainCharacter instance.
        context: Combat context dict (needs ``type`` and ``correct`` keys).
    """
    if context.get("type") == "dodge" and context.get("correct"):
        # Ensure attribute exists before incrementing (enemies lack it by default)
        player.dodge_modifier = getattr(player, "dodge_modifier", 0) + 0.1


def mc_eliminate_effect(player, context: dict) -> None:
    """Skill: Eliminate One — remove a wrong MC option before the question is shown.

    Sets player.mc_eliminate to 1; _ask_question() reads and clears this flag.

    Args:
        player:  MainCharacter instance.
        context: Combat context dict (needs ``q_type`` key).
    """
    if context.get("q_type") == "MC":
        player.mc_eliminate = 1   # flag consumed in _ask_question() → MC branch


def ar_bonus_damage(player, context: dict) -> None:
    """Skill: Bonus Damage — deal +20% damage after a correct Arithmetic answer.

    Modifies context["damage"] in place so the caller automatically uses the
    boosted value without needing to know this skill exists.

    Args:
        player:  MainCharacter instance (unused here, kept for interface parity).
        context: Combat context dict (needs ``type``, ``q_type``, ``correct``, ``damage``).
    """
    if (
        context.get("type") == "attack"
        and context.get("q_type") == "AR"
        and context.get("correct")
    ):
        context["damage"] = int(context["damage"] * 1.2)   # 20% damage bonus


def id_heal_bonus(player, context: dict) -> None:
    """Skill: Efficient Healing — increase healing by 20% after a correct ID answer.

    Modifies context["heal"] in place.

    Args:
        player:  MainCharacter instance (unused here, kept for interface parity).
        context: Combat context dict (needs ``type``, ``q_type``, ``heal``).
    """
    if context.get("type") == "heal" and context.get("q_type") == "ID":
        context["heal"] = int(context["heal"] * 1.2)   # 20% healing bonus


# ── Public API ────────────────────────────────────────────────────────────────

def apply_skills(player, context: dict) -> None:
    """Run every *unlocked* skill's effect against the current combat context.

    Called once per combat action so skills can modify damage, healing,
    or dodge chance before the result is applied to the game state.

    Args:
        player:  MainCharacter with a ``skills`` list attribute.
        context: Mutable dict describing the current action. Common keys:
                   ``type``    – ``"attack"``, ``"dodge"``, or ``"heal"``
                   ``q_type``  – Question type that triggered the action
                   ``damage``  – Damage amount (may be modified by skills)
                   ``correct`` – Whether the answer was correct
    """
    for skill in player.skills:
        if skill.unlocked:
            skill.effect(player, context)   # each skill modifies context in place


def unlock_skills(player) -> None:
    """Unlock any skills whose mastery conditions are now satisfied.

    Safe to call after every mastery gain — it's idempotent and only
    flips ``unlocked`` for skills that are currently locked and now meet
    their condition.

    Args:
        player: MainCharacter with a ``skills`` list attribute.
    """
    if not hasattr(player, "skills"):
        return   # guard for entities that don't have a skill list

    for skill in player.skills:
        if not skill.unlocked and skill.condition(player):
            skill.unlocked = True   # condition met → permanently unlock


def create_skill_pool() -> list:
    """Build and return the full list of available Skill objects for a new run.

    All skills start locked; they unlock once the player's mastery in the
    associated tree reaches ≥ 5.

    Returns:
        list[Skill]: Fresh skill pool (one per supported question type).
    """
    return [
        Skill(
            name="Reflex Dodge",
            tree="TF",
            effect=reflex_dodge_effect,
            # Unlock condition: TF mastery must reach 5
            condition=lambda p: p.mastery["TF"] >= 5,
        ),
        Skill(
            name="Eliminate One",
            tree="MC",
            effect=mc_eliminate_effect,
            # Unlock condition: MC mastery must reach 5
            condition=lambda p: p.mastery["MC"] >= 5,
        ),
        Skill(
            name="Bonus Damage",
            tree="AR",
            effect=ar_bonus_damage,
            # Unlock condition: AR mastery must reach 5
            condition=lambda p: p.mastery["AR"] >= 5,
        ),
        Skill(
            name="Efficient Healing",
            tree="ID",
            effect=id_heal_bonus,
            # Unlock condition: ID mastery must reach 5
            condition=lambda p: p.mastery["ID"] >= 5,
        ),
    ]