"""Combat calculation utilities.

Pure functions for damage, dodge, and critical-hit resolution.
No side effects — all randomness is isolated here so the rest of the
combat system can stay deterministic given the same RNG state.
"""

import random


def check_dodge(attacker, defender) -> bool:
    """Determine whether the defender dodges an incoming attack.

    Dodge chance is derived from the defender's SPD stat plus any
    temporary bonuses (streak-based or flat modifiers from status effects).

    Args:
        attacker: The entity performing the attack (kept for API symmetry;
                  attacker-side accuracy stats could be added here later).
        defender: The entity attempting to dodge.

    Returns:
        bool: True if the dodge succeeds.
    """
    # Base dodge chance: each point of SPD contributes 2%
    base_chance = defender.spd * 0.02

    # Streak-based dodge bonus — only MainCharacter has this method
    if hasattr(defender, "streak_dodge_bonus"):
        base_chance += defender.streak_dodge_bonus()

    # Flat modifier added/removed by status effects (e.g. Vulnerable subtracts)
    if hasattr(defender, "dodge_modifier"):
        base_chance += defender.dodge_modifier

    # random.random() returns [0.0, 1.0); True means the dodge succeeds
    return random.random() < base_chance


def check_critical(attacker) -> bool:
    """Determine whether the attacker lands a critical hit.

    Reads and immediately clears any one-time momentum bonus granted by
    the Momentum passive so the bonus only applies to a single attack.

    Args:
        attacker: The entity attacking.

    Returns:
        bool: True if this attack is a critical hit.
    """
    # Pop the one-time momentum bonus (default 0 if the attribute is absent)
    bonus = getattr(attacker, "_momentum_bonus", 0)
    attacker._momentum_bonus = 0   # reset so it never applies twice

    return random.random() < (attacker.crit_chance + bonus)


def calculate_damage(
    attacker,
    defender,
    variance_low: int = -2,
    variance_high: int = 2,
) -> tuple:
    """Calculate the final damage dealt from attacker to defender.

    Damage pipeline (applied in order):
        1. Base ATK   (+ streak attack bonus for the player)
        2. × Wisdom scaling:    1 + (WIS × 0.01)
        3. × Mastery scaling:   1 + (total_mastery × 0.002)
        4. + Random variance    [variance_low … variance_high]
        5. − Defender's defense  (minimum 1 so damage is never 0)
        6. × Crit multiplier    (only if a crit was rolled)

    Args:
        attacker:       The entity dealing damage.
        defender:       The entity receiving damage.
        variance_low:   Minimum random variance added to raw damage (default -2).
        variance_high:  Maximum random variance added to raw damage (default +2).

    Returns:
        tuple[int, bool]: (final_damage, is_critical)
    """
    # ── Step 1: Raw attack (optional streak bonus for player characters) ──
    raw = attacker.atk
    if hasattr(attacker, "streak_attack_bonus"):
        raw += attacker.streak_attack_bonus()   # scales with consecutive correct answers

    # ── Step 2: Wisdom scaling ─────────────────────────────────────────────
    wisdom       = getattr(attacker, "wisdom", 0)
    wisdom_bonus = 1 + (wisdom * 0.01)          # e.g. 30 WIS → ×1.30

    # ── Step 3: Mastery scaling (cumulative learning bonus) ───────────────
    mastery_bonus = 1.0
    if hasattr(attacker, "mastery"):
        total_mastery  = sum(attacker.mastery.values())
        mastery_bonus += total_mastery * 0.002  # e.g. 100 total mastery → ×1.20

    # ── Step 4: Random variance (keeps combat unpredictable) ──────────────
    variance = random.randint(variance_low, variance_high)

    # ── Step 5: Subtract defense, floor at 1 to prevent 0-damage hits ────
    base = max(1, raw - defender.defense + variance)
    base = int(base * wisdom_bonus * mastery_bonus)

    # ── Step 6: Critical hit check and multiplier ─────────────────────────
    is_crit = check_critical(attacker)
    if is_crit:
        base = int(base * attacker.crit_multiplier)   # e.g. ×1.5 or ×2.5

    return base, is_crit