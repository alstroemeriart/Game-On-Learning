"""Item and aid system.

Defines all consumable and utility items including healing potions, stat boosts,
status effect items, and special utility items used in combat and exploration.
"""

from statusEffects import StatusEffect
from ui import typewriter
import random


class Aid:
    """Base class for all consumable and utility items.

    All items share a name, description, price, and use() method.
    Subclasses override use() to implement their specific effect.

    Attributes:
        name:          Display name shown in inventory and shop.
        description:   Short effect summary shown in menus.
        price:         Base gold cost in the shop (may be discounted).
        flavor_texts:  List of drop-message templates; {name} is substituted.
    """
    name         = "Generic Aid"
    description  = "Does something."
    price        = 10
    flavor_texts = ["You found a {name}!"]

    def use(self, user, target=None) -> str:
        """Apply the item's effect to user (and optionally target).

        Args:
            user:   The character consuming the item.
            target: Optional secondary target (used by offensive items).

        Returns:
            str: Message describing what happened.
        """
        return ""

    def get_drop_message(self) -> str:
        """Return a random flavor text for when this item drops after combat."""
        message = random.choice(self.flavor_texts)
        return message.format(name=self.name)


# ─────────────────────────────────────────────────────────────────────────────
# HEALING ITEMS
# ─────────────────────────────────────────────────────────────────────────────

class HealingPotion(Aid):
    """Restore 20 HP.  Entry-level aid for early runs."""
    name        = "Healing Potion"
    description = "Restores 20 HP."
    price       = 15
    flavor_texts = [
        "The air smells of herbs. A {name} materializes.",
        "A glowing vial of {name} drops before you.",
        "Lucky! A {name} appears!",
    ]

    def __init__(self, heal_amount: int = 20):
        self.heal_amount = heal_amount

    def use(self, user, target=None) -> str:
        user.heal(self.heal_amount)
        return f"{user.name} heals {self.heal_amount} HP!"


class MegaHealingPotion(Aid):
    """Restore 50 HP.  Stronger, rarer healing option for mid/late game."""
    name        = "Mega Healing Potion"
    description = "Restores 50 HP."
    price       = 35
    flavor_texts = [
        "A surge of magical energy! {name} materializes!",
        "You feel incredibly lucky... {name} drops!",
        "The gods smile upon you. {name} appears!",
    ]

    def __init__(self, heal_amount: int = 50):
        self.heal_amount = heal_amount

    def use(self, user, target=None) -> str:
        user.heal(self.heal_amount)
        return f"{user.name} restores {self.heal_amount} HP!"


# ─────────────────────────────────────────────────────────────────────────────
# BUFF ITEMS — apply positive status effects to the player
# ─────────────────────────────────────────────────────────────────────────────

class AttackBoost(Aid):
    """Grant ATK +5 for 3 turns via the AttackBuff status effect."""
    name        = "Attack Boost"
    description = "ATK +5 for 3 turns."
    price       = 25
    flavor_texts = [
        "Your muscles tingle... {name} drops.",
        "Power surges through the air. {name} appears!",
        "A fierce aura materializes. {name} emerges!",
    ]

    def __init__(self, boost_amount: int = 5, duration: int = 3):
        self.boost_amount = boost_amount
        self.duration     = duration

    def use(self, user, target=None) -> str:
        from statusEffects import AttackBuff
        buff = AttackBuff(self.boost_amount, self.duration)
        user.status_effects.append(buff)
        buff.on_apply(user)   # immediately apply the stat change
        return f"ATK +{self.boost_amount} for {self.duration} turns!"


class DefenseBoost(Aid):
    """Grant DEF +5 for 3 turns via the DefenseBuff status effect."""
    name        = "Defense Boost"
    description = "DEF +5 for 3 turns."
    price       = 25
    flavor_texts = [
        "A barrier crystallizes before you. {name} appears!",
        "Stone and steel shimmer... {name} drops.",
        "An impenetrable aura surrounds you. {name} materializes!",
    ]

    def __init__(self, boost_amount: int = 5, duration: int = 3):
        self.boost_amount = boost_amount
        self.duration     = duration

    def use(self, user, target=None) -> str:
        from statusEffects import DefenseBuff
        buff = DefenseBuff(self.boost_amount, self.duration)
        user.status_effects.append(buff)
        buff.on_apply(user)
        return f"DEF +{self.boost_amount} for {self.duration} turns!"


class SpeedBoost(Aid):
    """Grant SPD +3 for 3 turns; higher SPD improves dodge chance."""
    name        = "Speed Boost"
    description = "SPD +3 for 3 turns. Improves dodge."
    price       = 30
    flavor_texts = [
        "Everything blurs into motion. {name} appears!",
        "Wind swirls around you... {name} drops!",
        "The world slows down. {name} materializes!",
    ]

    def __init__(self, boost_amount: int = 3, duration: int = 3):
        self.boost_amount = boost_amount
        self.duration     = duration

    def use(self, user, target=None) -> str:
        from statusEffects import SpeedBuff
        buff = SpeedBuff(self.boost_amount, self.duration)
        user.status_effects.append(buff)
        buff.on_apply(user)
        return f"SPD +{self.boost_amount} for {self.duration} turns!"


# ─────────────────────────────────────────────────────────────────────────────
# DEBUFF ITEMS — apply negative status effects to an enemy target
# ─────────────────────────────────────────────────────────────────────────────

class PoisonBomb(Aid):
    """Inflict Poison on the target: 5 damage per turn for 4 turns.

    Requires a target; returns an error message if none is provided.
    """
    name        = "Poison Bomb"
    description = "Poisons enemy for 4 turns (5 dmg/turn)."
    price       = 30
    flavor_texts = [
        "A sickly purple haze settles... {name} drops!",
        "The stench of corruption fills the air. {name} appears!",
        "Toxic fumes swirl about. {name} materializes!",
    ]

    def __init__(self, damage_per_turn: int = 5, duration: int = 4):
        self.damage_per_turn = damage_per_turn
        self.duration        = duration

    def use(self, user, target=None) -> str:
        if target is None:
            return "No target selected!"
        from statusEffects import Poison
        poison = Poison(self.damage_per_turn, self.duration)
        target.status_effects.append(poison)
        poison.on_apply(target)
        return f"{target.name} is poisoned for {self.duration} turns!"


class FreezeScroll(Aid):
    """Stun the target AND lower its defense for 1 turn (Freeze effect)."""
    name        = "Freeze Scroll"
    description = "Stuns enemy and lowers their DEF for 1 turn."
    price       = 35
    flavor_texts = [
        "Ice crystals form before you. {name} appears!",
        "Everything freezes in an instant... {name} drops!",
        "A chilling wind blows. {name} materializes!",
    ]

    def __init__(self, duration: int = 1):
        self.duration = duration

    def use(self, user, target=None) -> str:
        if target is None:
            return "No target selected!"
        from statusEffects import Freeze
        freeze = Freeze(self.duration)
        target.status_effects.append(freeze)
        freeze.on_apply(target)
        return f"{target.name} is frozen and skips {self.duration} turn(s)!"


class WeaknessCurse(Aid):
    """Reduce the target's ATK by 5 for 3 turns."""
    name        = "Weakness Curse"
    description = "Reduces enemy ATK by 5 for 3 turns."
    price       = 30
    flavor_texts = [
        "A dark curse spreads... {name} drops!",
        "Weakness seeps into your enemy. {name} appears!",
        "The enemy's strength fades. {name} materializes!",
    ]

    def __init__(self, reduction: int = 5, duration: int = 3):
        self.reduction = reduction
        self.duration  = duration

    def use(self, user, target=None) -> str:
        if target is None:
            return "No target selected!"
        from statusEffects import AttackDebuff
        debuff = AttackDebuff(self.reduction, self.duration)
        target.status_effects.append(debuff)
        debuff.on_apply(target)
        return f"{target.name}'s ATK reduced by {self.reduction} for {self.duration} turns!"


# ─────────────────────────────────────────────────────────────────────────────
# SPECIAL / UTILITY ITEMS
# ─────────────────────────────────────────────────────────────────────────────

class HintPotion(Aid):
    """Activate the hint flag so the next combat question shows a hint."""
    name        = "Hint Potion"
    description = "Gives a hint on your next question."
    price       = 20
    flavor_texts = [
        "Clarity shines brightly... {name} drops!",
        "Knowledge whispers around you. {name} appears!",
        "The path forward becomes clear. {name} materializes!",
    ]

    def use(self, user, target=None) -> str:
        # hint_active is checked in _ask_question() and cleared after use
        user.hint_active = True
        return "Your next question will come with a hint!"


class DoubleGoldCharm(Aid):
    """Apply the DoubleGold status effect for 3 turns of 2× gold income."""
    name        = "Double Gold Charm"
    description = "Doubles gold earned for 3 turns."
    price       = 40
    flavor_texts = [
        "Gold glimmers in the light... {name} drops!",
        "Prosperity blooms around you. {name} appears!",
        "Riches are yours to claim! {name} materializes!",
    ]

    def __init__(self, duration: int = 3):
        self.duration = duration

    def use(self, user, target=None) -> str:
        from statusEffects import DoubleGold
        buff = DoubleGold(self.duration)
        user.status_effects.append(buff)
        buff.on_apply(user)
        return f"Gold rewards doubled for {self.duration} turns!"


class RevivalStone(Aid):
    """Fully restore HP to max — the most powerful and rarest item."""
    name        = "Revival Stone"
    description = "Fully restores your HP."
    price       = 50
    flavor_texts = [
        "A legendary stone of resurrection appears!",
        "The gods grant you a second chance. {name} materializes!",
        "Rebirth energy flows... {name} drops!",
    ]

    def use(self, user, target=None) -> str:
        healed  = user.max_hp - user.hp   # record how much was actually healed
        user.hp = user.max_hp
        return f"{user.name} is fully restored! ({healed} HP recovered)"


# ── Master item registry ──────────────────────────────────────────────────────
# Used by learningEngine.random_item_pool() and shop._build_stock() to randomly
# select items weighted by rarity.
# Rarities: common → uncommon → rare → legendary
AllItems = [
    {"class": HealingPotion,     "name": "Healing Potion",     "rarity": "common"},
    {"class": MegaHealingPotion, "name": "Mega Healing Potion", "rarity": "uncommon"},
    {"class": AttackBoost,       "name": "Attack Boost",        "rarity": "uncommon"},
    {"class": DefenseBoost,      "name": "Defense Boost",       "rarity": "uncommon"},
    {"class": SpeedBoost,        "name": "Speed Boost",         "rarity": "uncommon"},
    {"class": PoisonBomb,        "name": "Poison Bomb",         "rarity": "rare"},
    {"class": FreezeScroll,      "name": "Freeze Scroll",       "rarity": "rare"},
    {"class": WeaknessCurse,     "name": "Weakness Curse",      "rarity": "rare"},
    {"class": HintPotion,        "name": "Hint Potion",         "rarity": "common"},
    {"class": DoubleGoldCharm,   "name": "Double Gold Charm",   "rarity": "rare"},
    {"class": RevivalStone,      "name": "Revival Stone",       "rarity": "legendary"},
]