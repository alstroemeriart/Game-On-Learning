"""Character and entity spawning system.

Defines the base Spawn class and MainCharacter entity with stats, inventory,
progression tracking, and class-specific mechanics.
"""

import random
from dataclasses import dataclass, field
from typing import List
from statusEffects import StatusEffect
from items import HealingPotion, AttackBoost, HintPotion
from ui import typewriter, input_handler, emit_player_stats


@dataclass
class Spawn:
    """Base entity class shared by both players and enemies.

    Uses Python's @dataclass to auto-generate __init__ from the annotated
    class attributes.  hp and shield are derived fields (not constructor args).

    Attributes:
        name:           Entity's display name.
        max_hp:         Maximum hit points.
        atk:            Attack damage stat.
        defense:        Damage reduction applied to incoming hits.
        spd:            Speed stat; affects dodge chance in combatCalc.
        gold:           Currency (enemies carry this as a reward amount).
        hp:             Current hit points — initialised to max_hp in __post_init__.
        status_effects: List of active StatusEffect instances.
        shield:         Damage-absorbing pool that depletes before HP does.
    """
    name:   str
    max_hp: int
    atk:    int
    defense: int
    spd:    int
    gold:   int

    # Fields populated after the dataclass __init__ runs
    hp:             int = field(init=False)
    status_effects: List["StatusEffect"] = field(default_factory=list)

    def __post_init__(self):
        """Set derived fields that depend on the primary constructor args."""
        self.hp     = self.max_hp   # start at full HP
        self.shield = 0             # no shield until a buff grants one

    def take_dmg(self, dmg: int):
        """Reduce HP by dmg, first draining any shield pool.

        Shield absorbs damage point-for-point before HP is touched.  Once
        the shield reaches 0 the remaining damage flows through to HP.

        Args:
            dmg: Raw damage amount to apply.
        """
        if self.shield > 0:
            # Absorb as much as the shield allows
            absorbed    = min(self.shield, dmg)
            self.shield -= absorbed
            dmg         -= absorbed
            if absorbed > 0:
                typewriter(f"{self.name}'s shield absorbs {absorbed} damage!")

        # Any damage not absorbed by shield reduces HP (minimum 0)
        self.hp = max(0, self.hp - dmg)

    def is_alive(self) -> bool:
        """Return True while the entity still has HP remaining."""
        return self.hp > 0

    def heal(self, amount: int):
        """Restore hit points, clamped to max_hp to prevent over-healing.

        Args:
            amount: HP to restore.
        """
        self.hp = min(self.max_hp, self.hp + amount)


class MainCharacter(Spawn):
    """Player character entity with progression, inventory, and specialised mechanics.

    Extends Spawn with:
      • Wisdom and crit stats
      • Experience / levelling
      • Starting inventory
      • Streak counter and streak-based bonuses
      • Focus bar for special abilities
      • Per-question-type mastery tracking
      • Class passive support
      • Debug/God-mode flag
    """

    def __init__(self, name, max_hp, atk, defense, spd,
                 wisdom, crit_chance, crit_multiplier):
        # Initialise the Spawn base with gold=0 (player earns gold dynamically)
        super().__init__(name, max_hp, atk, defense, spd, gold=0)

        # ── Combat stats beyond what Spawn provides ────────────────────────
        self.wisdom          = wisdom          # scales damage & focus gain per correct answer
        self.crit_chance     = crit_chance     # probability of a critical hit (0.0–1.0)
        self.crit_multiplier = crit_multiplier # damage multiplier when crit triggers

        # ── Class metadata (set after creation in create_character()) ──────
        self.class_name    = ""    # display name shown in UI
        self.class_passive = ""    # passive ability key (e.g. "bloodlust", "fortress")
        self.run_modifier  = ""    # run-wide challenge modifier (e.g. "cursed", "scholar")

        # ── Progression ───────────────────────────────────────────────────
        self.lvl        = 1
        self.exp        = 0
        self.xp_to_next = 100   # threshold scales by ×1.3 on each level-up

        # ── Starting inventory: one of each basic aid ──────────────────────
        self.inventory = [HealingPotion(), AttackBoost(), HintPotion()]
        self.gold      = 10   # small starting gold for early-node shops

        # ── Combat state ──────────────────────────────────────────────────
        self.streak           = 0      # consecutive correct answers this combat
        self.longest_streak   = 0      # all-time best streak (tracked for achievements)
        self.focus            = 0      # fills on correct answers; triggers ability at max
        self.max_focus        = 100
        self.streak_protected = False  # if True, next wrong answer won't halve streak
        self.action_points    = 2      # AP available on player's turn
        self.max_action_points = 2
        self.bloodlust_stacks  = 0     # Berserker: counts permanent ATK boosts (cap 10)
        self.dodge_next        = False # set by boss "Evade" action to guarantee one dodge
        self._momentum_bonus   = 0.0   # Duelist: one-time crit bonus, read by check_critical

        # ── Mastery / skills ──────────────────────────────────────────────
        # One counter per question type; used by mastery_multiplier() and skill conditions
        self.mastery = {"TF": 0, "MC": 0, "AR": 0, "ID": 0, "FB": 0, "OD": 0}
        self.skills  = []   # populated by create_skill_pool() at run start

        # ── Flags and modifiers ───────────────────────────────────────────
        self.hint_active      = False  # if True, next question shows a hint
        self.status_effects   = []
        self.is_stunned       = False  # set/cleared by Stun / Freeze effects
        self.gold_multiplier  = 1.0   # multiplied by DoubleGold / GoldBoost effects
        self.has_streak_guard = False  # set by StreakGuard effect
        self.mc_eliminate     = 0     # >0: Eliminate One skill removes a wrong MC option
        self.debug_mode       = False  # God-mode / auto-play flag (code "143" at login)
        self.dodge_modifier   = 0.0   # flat dodge modifier; adjusted by status effects

        # ── GUI back-references (set externally when GUI is active) ───────
        self.engine_ref    = None   # LearningEngine reference for mid-turn queries
        self.session_stats = None   # SessionStats reference for accuracy tracking

    # ── Streak-based bonus methods ────────────────────────────────────────

    def streak_attack_bonus(self) -> int:
        """Extra ATK from current streak: 1% of base ATK per streak point.

        Returns:
            int: Bonus attack damage (can be 0 if streak is 0).
        """
        return int(self.atk * 0.01 * self.streak)

    def streak_dodge_bonus(self) -> float:
        """Extra dodge chance from streak, hard-capped at 25%.

        Returns:
            float: Additional dodge probability (0.0–0.25).
        """
        return min(0.005 * self.streak, 0.25)

    def shop_discount(self, base_price: int) -> int:
        """Price after applying streak-based discount (max 25% off).

        1% discount per 5 streak points, capped at 25%.

        Args:
            base_price: Original item price in gold.

        Returns:
            int: Discounted price.
        """
        discount = min(0.01 * (self.streak // 5), 0.25)
        return int(base_price * (1 - discount))

    def apply_gold(self, amount: int) -> int:
        """Add gold after applying the current gold multiplier.

        The multiplier is normally 1.0 but can be raised by DoubleGold or
        GoldBoost status effects.

        Args:
            amount: Base gold amount before multiplier.

        Returns:
            int: Actual gold added to the player's total.
        """
        actual      = int(amount * self.gold_multiplier)
        self.gold  += actual
        return actual

    def puzzle_bonus(self) -> float:
        """Reduce puzzle difficulty based on streak (max 30% reduction).

        Used by the maze trial system to scale question difficulty down
        for high-streak players.

        Returns:
            float: Difficulty reduction (0.0–0.30).
        """
        return min(0.02 * self.streak, 0.30)

    # ── Alive check (override so Spawn.is_alive also works for player) ────

    def is_alive(self):
        return self.hp > 0

    # ── Experience / levelling ────────────────────────────────────────────

    def gain_xp(self, amount: int):
        """Add XP and automatically trigger level-up(s) if threshold crossed.

        Supports multi-level gains in a single call (while loop handles it).

        Args:
            amount: XP to add.
        """
        self.exp += amount
        typewriter(f"Gained {amount} XP! ({self.exp}/{self.xp_to_next})")
        # keep levelling up as long as we have enough XP accumulated
        while self.exp >= self.xp_to_next:
            self.level_up()
        emit_player_stats(self)   # refresh GUI bars after XP gain

    def level_up(self):
        """Advance one level, grant stat choice, and scale the XP threshold.

        XP threshold grows by ×1.3 per level to create an exponential curve.
        Player always heals to full HP on level-up as a reward.
        """
        self.exp        -= self.xp_to_next             # carry over excess XP
        self.lvl        += 1
        self.xp_to_next  = int(self.xp_to_next * 1.3) # steeper curve each level
        self.max_hp     += 5
        self.hp          = self.max_hp                 # full heal on level-up

        typewriter(f"\n*** LEVEL UP! You are now Level {self.lvl}! ***")
        typewriter("Choose a stat to boost:")
        typewriter("1. ATK +3")
        typewriter("2. DEF +3")
        typewriter("3. SPD +2")
        typewriter("4. WIS +5")

        # ask_choice works in both terminal and GUI modes
        choice = input_handler.ask_choice(
            [
                {"label": "1. ATK +3", "value": "1"},
                {"label": "2. DEF +3", "value": "2"},
                {"label": "3. SPD +2", "value": "3"},
                {"label": "4. WIS +5", "value": "4"},
            ],
            "> ",
        )

        # Map choice string → (attribute name, boost amount)
        boosts = {
            "1": ("atk",     3),
            "2": ("defense", 3),
            "3": ("spd",     2),
            "4": ("wisdom",  5),
        }
        # Default to ATK if the player sends an unexpected value
        stat, amt = boosts.get(choice, ("atk", 3))
        setattr(self, stat, getattr(self, stat) + amt)
        typewriter(f"{stat.upper()} increased by {amt}!")
        emit_player_stats(self)


class Enemy(Spawn):
    """NPC enemy entity with AI combat behavior.

    Extends Spawn with crit stats and a behavior string that determines
    how enemy_turn() in combatSystem.py selects its action each round.

    Behavior options (checked in enemy_turn):
        "neutral"    – standard single attack
        "aggressive" – two weaker attacks per turn
        "evasive"    – occasionally boosts own dodge instead of attacking
        "defensive"  – occasionally raises own defense before attacking

    Attributes:
        crit_chance:    Probability of landing a critical hit (0.0–1.0).
        crit_multiplier: Damage multiplier on critical hits (fixed 1.5).
        behavior:       AI pattern string used in enemy_turn().
        defense_bonus:  Temporary defense added during "defensive" behaviour;
                        tracked separately so it can be removed next turn.
        dodge_modifier: Temporary dodge adjustment for "evasive" enemies.
        is_stunned:     True while a Stun/Freeze effect is active.
    """

    def __init__(self, name, hp, atk, defense, spd,
                 crit_chance, behavior="neutral"):
        # gold=0: enemies don't carry gold directly; rewards come from main.py
        super().__init__(name, hp, atk, defense, spd, gold=0)
        self.crit_chance     = crit_chance
        self.crit_multiplier = 1.5       # all enemies use the same crit multiplier
        self.behavior        = behavior
        self.defense_bonus   = 0         # set during "defensive" turn; cleared next turn
        self.dodge_modifier  = 0.0       # set during "evasive" turn; decays each turn
        self.is_stunned      = False     # set/cleared by Stun and Freeze effects


@dataclass
class RunState:
    """Snapshot of run progression saved alongside player data.

    Attributes:
        tier:          Current difficulty tier (1–3).
        battles_won:   Enemies defeated this run.
        nodes_cleared: Map nodes explored this run.
    """
    tier:          int = 1
    battles_won:   int = 0
    nodes_cleared: int = 0