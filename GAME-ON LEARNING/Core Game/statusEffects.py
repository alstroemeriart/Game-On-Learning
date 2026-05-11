"""Status effects system.

Defines the base StatusEffect class and all concrete effect types
(buffs, debuffs, damage-over-time, utility effects).

Lifecycle hooks (called by combatSystem.process_status_effects):
    on_apply      → called once when first applied to an entity
    on_turn_start → called at the beginning of the affected entity's turn
    on_turn_end   → called at the end of the turn; default decrements duration
    on_expire     → called once when duration reaches 0, before removal
"""

from ui import typewriter


class StatusEffect:
    """Base class for all status effects.

    Subclasses override only the lifecycle hooks they need.
    Any hook not overridden is a no-op so subclasses stay minimal.

    Attributes:
        name     (str): Display name shown to the player.
        duration (int): Remaining turns; decremented each on_turn_end call.
    """

    def __init__(self, name: str, duration: int) -> None:
        self.name     = name
        self.duration = duration

    # ── Lifecycle hooks ───────────────────────────────────────────────────

    def on_apply(self, entity) -> None:
        """Called once when the effect is first applied to entity."""
        pass

    def on_turn_start(self, entity) -> None:
        """Called at the start of each of entity's turns (e.g. DOT damage)."""
        pass

    def on_turn_end(self, entity) -> None:
        """Called at the end of entity's turn. Always decrements duration."""
        self.duration -= 1

    def on_expire(self, entity) -> None:
        """Called once when duration hits 0, right before removal from entity."""
        pass

    def is_expired(self) -> bool:
        """Return True once all turns have been consumed."""
        return self.duration <= 0


# ─────────────────────────────────────────────────────────────────────────────
# BUFFS  (positive effects that help the entity they are applied to)
# ─────────────────────────────────────────────────────────────────────────────

class AttackBuff(StatusEffect):
    """Temporarily increase an entity's ATK stat.

    The boost is applied immediately on on_apply and reverted on on_expire
    so the stat is always correct regardless of how early the effect ends.

    Args:
        amount   (int): ATK points to add.
        duration (int): Turns the buff lasts.
    """

    def __init__(self, amount: int, duration: int) -> None:
        super().__init__("Attack Buff", duration)
        self.amount = amount  # store so we can subtract the same value on expire

    def on_apply(self, entity) -> None:
        entity.atk += self.amount
        typewriter(f"{entity.name}'s ATK increased by {self.amount}!")

    def on_expire(self, entity) -> None:
        entity.atk -= self.amount          # undo the buff exactly
        typewriter(f"{entity.name}'s Attack Buff has worn off!")


class DefenseBuff(StatusEffect):
    """Temporarily increase an entity's DEF stat.

    Args:
        amount   (int): DEF points to add.
        duration (int): Turns the buff lasts.
    """

    def __init__(self, amount: int, duration: int) -> None:
        super().__init__("Defense Buff", duration)
        self.amount = amount

    def on_apply(self, entity) -> None:
        entity.defense += self.amount
        typewriter(f"{entity.name}'s DEF increased by {self.amount}!")

    def on_expire(self, entity) -> None:
        entity.defense -= self.amount      # restore original defense
        typewriter(f"{entity.name}'s Defense Buff has worn off!")


class SpeedBuff(StatusEffect):
    """Temporarily increase an entity's SPD stat.

    Higher SPD improves dodge chance via check_dodge() in combatCalc.

    Args:
        amount   (int): SPD points to add.
        duration (int): Turns the buff lasts.
    """

    def __init__(self, amount: int, duration: int) -> None:
        super().__init__("Speed Buff", duration)
        self.amount = amount

    def on_apply(self, entity) -> None:
        entity.spd += self.amount
        typewriter(f"{entity.name}'s Speed increased by {self.amount}!")

    def on_expire(self, entity) -> None:
        entity.spd -= self.amount          # restore original speed
        typewriter(f"{entity.name}'s Speed Buff has worn off!")


class Regen(StatusEffect):
    """Restore HP at the start of each turn (heal-over-time).

    Healing is capped at max_hp so it never over-heals.

    Args:
        amount   (int): HP restored per turn.
        duration (int): Turns the regeneration lasts.
    """

    def __init__(self, amount: int, duration: int) -> None:
        super().__init__("Regeneration", duration)
        self.amount = amount

    def on_turn_start(self, entity) -> None:
        # Clamp HP so regen never exceeds the entity's maximum
        entity.hp = min(entity.max_hp, entity.hp + self.amount)
        typewriter(f"{entity.name} regenerates {self.amount} HP!")

    def on_expire(self, entity) -> None:
        typewriter(f"{entity.name}'s regeneration faded.")


class Shield(StatusEffect):
    """Grant a temporary shield that absorbs incoming damage before HP.

    entity.shield is a flat absorption pool decremented in Spawn.take_dmg().
    On expire we only subtract what *this* effect added; other sources of
    shield (items, skills) are left untouched.

    Args:
        amount   (int): Shield points granted.
        duration (int): Turns before the shield expires.
    """

    def __init__(self, amount: int, duration: int) -> None:
        super().__init__("Shield", duration)
        self.amount = amount

    def on_apply(self, entity) -> None:
        entity.shield += self.amount
        typewriter(f"{entity.name} gains a shield of {self.amount}!")

    def on_expire(self, entity) -> None:
        # Only remove what we added; clamp to 0 if already partially consumed
        entity.shield = max(0, entity.shield - self.amount)
        typewriter(f"{entity.name}'s shield expired.")


class GoldBoost(StatusEffect):
    """Multiply gold earned by a factor for a set number of turns.

    Uses multiplicative stacking so two GoldBoost effects combine correctly
    (e.g. x1.5 × x2.0 = x3.0).  Reversed by dividing on expire to avoid
    floating-point drift from repeated addition/subtraction.

    Args:
        multiplier (float): Gold multiplier, e.g. 1.5 for +50%.
        duration   (int):   Turns the boost lasts.
    """

    def __init__(self, multiplier: float, duration: int) -> None:
        super().__init__("Gold Boost", duration)
        self.multiplier = multiplier

    def on_apply(self, entity) -> None:
        entity.gold_multiplier *= self.multiplier
        typewriter(f"{entity.name}'s gold gain increased!")

    def on_expire(self, entity) -> None:
        # Division reverses the multiplication precisely
        entity.gold_multiplier /= self.multiplier
        typewriter("Gold boost has expired.")


class DoubleGold(StatusEffect):
    """Double all gold earned for the duration.

    Convenience wrapper around a x2 GoldBoost.  Kept separate so the
    display name and flavor text differ from generic GoldBoost.

    Args:
        duration (int): Turns the bonus lasts.
    """

    def __init__(self, duration: int) -> None:
        super().__init__("Double Gold", duration)

    def on_apply(self, entity) -> None:
        entity.gold_multiplier *= 2       # stack multiplicatively with other gold effects
        typewriter(f"{entity.name} will earn DOUBLE gold!")

    def on_expire(self, entity) -> None:
        entity.gold_multiplier /= 2       # undo the doubling
        typewriter("Double Gold has expired.")


class StreakGuard(StatusEffect):
    """Protect the player's streak from being halved on the next wrong answer.

    Sets a boolean flag that the combat system reads and clears when triggered.
    Duration of 1 means it lasts until the next turn_end, which is fine since
    the flag itself controls when it's consumed.
    """

    def __init__(self) -> None:
        super().__init__("Streak Guard", 1)

    def on_apply(self, entity) -> None:
        entity.has_streak_guard = True    # flag checked in _apply_incorrect()
        typewriter("Your next streak loss will be prevented!")

    def on_expire(self, entity) -> None:
        entity.has_streak_guard = False   # clear flag when the effect expires
        typewriter("Streak Guard has been used.")


# ─────────────────────────────────────────────────────────────────────────────
# DEBUFFS  (negative effects applied to enemies or the player as punishment)
# ─────────────────────────────────────────────────────────────────────────────

class Poison(StatusEffect):
    """Deal fixed damage at the start of each turn (damage-over-time).

    Uses take_dmg() so shield absorption is respected.

    Args:
        damage   (int): Damage dealt per turn.
        duration (int): Turns the poison lasts.
    """

    def __init__(self, damage: int, duration: int) -> None:
        super().__init__("Poison", duration)
        self.damage = damage

    def on_turn_start(self, entity) -> None:
        entity.take_dmg(self.damage)      # respects shield pool
        typewriter(f"{entity.name} takes {self.damage} poison damage!")

    def on_expire(self, entity) -> None:
        typewriter(f"{entity.name} is no longer poisoned!")


class Burn(StatusEffect):
    """Deal burn damage at the start of each turn.

    Functionally identical to Poison but kept separate for flavor and
    potential future differentiation (e.g. burn ignores shields).

    Args:
        damage   (int): Damage dealt per turn.
        duration (int): Turns the burn lasts.
    """

    def __init__(self, damage: int, duration: int) -> None:
        super().__init__("Burn", duration)
        self.damage = damage

    def on_turn_start(self, entity) -> None:
        entity.take_dmg(self.damage)
        typewriter(f"{entity.name} takes {self.damage} burn damage!")

    def on_expire(self, entity) -> None:
        typewriter(f"{entity.name} is no longer burning!")


class Stun(StatusEffect):
    """Prevent the entity from acting for the duration.

    Sets entity.is_stunned = True; the player_turn() and enemy_turn()
    functions check this flag and skip the turn if it is set.

    Args:
        duration (int): Number of turns stunned.
    """

    def __init__(self, duration: int) -> None:
        super().__init__("Stun", duration)

    def on_apply(self, entity) -> None:
        entity.is_stunned = True           # read by player_turn / enemy_turn

    def on_expire(self, entity) -> None:
        entity.is_stunned = False          # restore action ability
        typewriter(f"{entity.name} is no longer stunned!")


class Freeze(StatusEffect):
    """Stun the entity AND temporarily lower its defense.

    Stronger variant of Stun used by the Freeze Scroll item.
    Defense is restored precisely on expire to avoid permanent stat loss.

    Args:
        duration          (int): Turns frozen.
        defense_reduction (int): DEF points removed while frozen. Default 2.
    """

    def __init__(self, duration: int, defense_reduction: int = 2) -> None:
        super().__init__("Freeze", duration)
        self.defense_reduction = defense_reduction

    def on_apply(self, entity) -> None:
        entity.is_stunned  = True
        entity.defense    -= self.defense_reduction   # lower defense while frozen
        typewriter(f"{entity.name} is frozen solid!")

    def on_expire(self, entity) -> None:
        entity.is_stunned  = False
        entity.defense    += self.defense_reduction   # restore the defense we took
        typewriter(f"{entity.name} thawed out!")


class AttackDebuff(StatusEffect):
    """Temporarily reduce an entity's ATK stat.

    Used by WeaknessCurse items and as a punishment for abstaining in combat.
    ATK is fully restored on expire.

    Args:
        amount   (int): ATK points to remove.
        duration (int): Turns the debuff lasts.
    """

    def __init__(self, amount: int, duration: int) -> None:
        super().__init__("Attack Down", duration)
        self.amount = amount

    def on_apply(self, entity) -> None:
        entity.atk -= self.amount
        typewriter(f"{entity.name}'s ATK decreased by {self.amount}!")

    def on_expire(self, entity) -> None:
        entity.atk += self.amount          # undo the ATK reduction
        typewriter(f"{entity.name}'s Attack returned to normal!")


class Vulnerable(StatusEffect):
    """Reduce the entity's dodge chance, making it easier to hit.

    Modifies entity.dodge_modifier, which is summed into dodge probability
    inside check_dodge() in combatCalc.py.  Initialises the attribute if
    the entity doesn't already have it (defensive coding for enemies).

    Args:
        duration      (int):   Turns the debuff lasts.
        dodge_penalty (float): Dodge chance reduction. Default 0.2 (20%).
    """

    def __init__(self, duration: int, dodge_penalty: float = 0.2) -> None:
        super().__init__("Vulnerable", duration)
        self.dodge_penalty = dodge_penalty

    def on_apply(self, entity) -> None:
        # Guard: enemies may not have dodge_modifier initialised yet
        if not hasattr(entity, "dodge_modifier"):
            entity.dodge_modifier = 0
        entity.dodge_modifier -= self.dodge_penalty   # negative = harder to dodge
        typewriter(
            f"{entity.name} feels exposed! "
            f"Dodge reduced by {int(self.dodge_penalty * 100)}% "
            f"for {self.duration} turns."
        )

    def on_expire(self, entity) -> None:
        entity.dodge_modifier += self.dodge_penalty   # restore dodge chance
        typewriter(f"{entity.name} is no longer vulnerable.")