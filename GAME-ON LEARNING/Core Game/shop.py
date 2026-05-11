"""Shop and merchant system.

Manages the in-game shop, item inventory, purchasing, pricing, and merchant interactions
during runs. Uses GUI buttons for all choices.
"""

import random
import time

from ui import typewriter, clear_screen, input_handler, emit_player_stats
from items import (
    HealingPotion, AttackBoost, HintPotion,
    DefenseBoost, MegaHealingPotion, SpeedBoost,
    PoisonBomb, FreezeScroll, WeaknessCurse,
    DoubleGoldCharm, RevivalStone, AllItems
)

ITEM_POOL = [
    HealingPotion,
    AttackBoost,
    HintPotion,
    DefenseBoost,
    MegaHealingPotion,
    SpeedBoost,
    PoisonBomb,
    FreezeScroll,
    WeaknessCurse,
    DoubleGoldCharm,
    RevivalStone
]


def get_merchant_greeting(player):
    if player.streak >= 10:
        return "\"Ah, a scholar of great wisdom! I'll give you my finest.\""
    elif player.hp < player.max_hp * 0.3:
        return "\"You look terrible. Buy something before you die.\""
    elif player.gold > 100:
        return "\"A wealthy traveler! Everything's full price for you.\""
    else:
        return "\"Welcome, wanderer. Browse at your leisure.\""


def _build_stock(player):
    stock = []
    num_items = min(5, len(ITEM_POOL))
    selected_classes = random.sample(ITEM_POOL, k=num_items)

    for item_class in selected_classes:
        base_price = random.randint(30, 120)
        final_price = player.shop_discount(base_price)
        stock.append({
            "item": item_class(),
            "price": final_price,
            "sold": False,
            "mystery": False,
        })

    mystery_class = random.choice(ITEM_POOL)
    mystery_instance = mystery_class()
    base_mystery_price = random.randint(15, 60)
    mystery_price = int(player.shop_discount(base_mystery_price) * 0.8)
    stock.append({
        "item": mystery_instance,
        "price": max(5, mystery_price),
        "sold": False,
        "mystery": True,
    })

    return stock


def _get_rarity(item_instance):
    for entry in AllItems:
        if isinstance(item_instance, entry["class"]):
            return entry["rarity"]
    return "unknown"


def _display_stock(stock, player):
    typewriter("\n=== Welcome to the Shop ===")
    typewriter(f"HP:   {player.hp}/{player.max_hp}")
    typewriter(f"Gold: {player.gold}")
    time.sleep(0.3)

    typewriter("\nItems for sale:")
    slot_map = {}
    display_num = 1

    for i, slot in enumerate(stock):
        if slot["sold"]:
            label = "???" if slot["mystery"] else slot["item"].name
            typewriter(f"  -. {label} — SOLD OUT")
        elif slot["mystery"]:
            rarity = _get_rarity(slot["item"])
            typewriter(f"  {display_num}. ??? [{rarity}] — {slot['price']} gold  (mystery item)")
            slot_map[display_num] = i
            display_num += 1
        else:
            desc = getattr(slot["item"], "description", "")
            typewriter(f"  {display_num}. {slot['item'].name} — {slot['price']} gold")
            if desc:
                typewriter(f"      {desc}")
            slot_map[display_num] = i
            display_num += 1

    sell_num  = display_num
    leave_num = display_num + 1
    typewriter(f"  {sell_num}. Sell an item")
    typewriter(f"  {leave_num}. Leave shop")

    return slot_map, sell_num, leave_num


def shop(player):
    """Roguelite shop — uses ask_choice() for GUI button support."""
    # Debug mode: skip shop
    if getattr(player, "debug_mode", False):
        typewriter("[DEBUG AUTO-PLAY] Skipping shop...")
        time.sleep(0.3)
        return
    
    typewriter(get_merchant_greeting(player))
    time.sleep(0.5)

    stock = _build_stock(player)

    while True:
        available = [s for s in stock if not s["sold"]]
        if not available:
            typewriter("\nThe merchant shrugs. \"Sold out — come back next time.\"")
            time.sleep(1.5)
            return

        slot_map, sell_num, leave_num = _display_stock(stock, player)

        # ── BUG FIX: build ask_choice options dynamically ──────────────────
        options = []
        display_num = 1
        for i, slot in enumerate(stock):
            if slot["sold"]:
                continue
            if slot["mystery"]:
                rarity = _get_rarity(slot["item"])
                label = f"{display_num}. ??? [{rarity}] — {slot['price']}g"
            else:
                label = f"{display_num}. {slot['item'].name} — {slot['price']}g"
            options.append({"label": label, "value": str(display_num)})
            display_num += 1

        options.append({"label": f"{sell_num}. Sell an item", "value": str(sell_num)})
        options.append({"label": f"{leave_num}. Leave shop",  "value": str(leave_num)})

        raw = input_handler.ask_choice(options, "\n> ")
        try:
            choice = int(raw)
        except ValueError:
            typewriter("Invalid choice.")
            time.sleep(0.5)
            continue
        # ──────────────────────────────────────────────────────────────────

        if choice == leave_num:
            typewriter("Leaving shop...")
            time.sleep(0.5)
            return

        if choice == sell_num:
            _sell_item(player)
            continue

        if choice in slot_map:
            stock_index = slot_map[choice]
            slot = stock[stock_index]

            if player.gold >= slot["price"]:
                player.gold -= slot["price"]
                player.inventory.append(slot["item"])
                slot["sold"] = True

                if slot["mystery"]:
                    typewriter(f"You unwrap the mystery item...")
                    time.sleep(0.8)
                    typewriter(f"It's a {slot['item'].name}!")
                    desc = getattr(slot["item"], "description", "")
                    if desc:
                        typewriter(f"  {desc}")
                else:
                    typewriter(f"You bought {slot['item'].name}!")

                typewriter(f"Gold remaining: {player.gold}")
                emit_player_stats(player)
                time.sleep(0.5)
            else:
                typewriter("Not enough gold!")
                time.sleep(0.5)
        else:
            typewriter("Invalid choice.")
            time.sleep(0.5)


def _sell_item(player):
    """Sell menu — uses ask_choice() for GUI button support."""
    if not player.inventory:
        typewriter("You have nothing to sell.")
        return

    typewriter("\nYour inventory (sell for half price):")
    for i, item in enumerate(player.inventory, 1):
        sell_price = item.price // 2
        desc = getattr(item, "description", "")
        typewriter(f"  {i}. {item.name} — sells for {sell_price} gold")
        if desc:
            typewriter(f"      {desc}")
    cancel_num = len(player.inventory) + 1
    typewriter(f"  {cancel_num}. Cancel")

    # ── BUG FIX: use ask_choice so GUI renders buttons ─────────────────────
    options = [
        {"label": f"{i}. {item.name}  ({item.price // 2}g)",
         "value": str(i)}
        for i, item in enumerate(player.inventory, 1)
    ]
    options.append({"label": f"{cancel_num}. Cancel", "value": str(cancel_num)})

    raw = input_handler.ask_choice(options, "> ")
    try:
        choice = int(raw)
    except ValueError:
        typewriter("Invalid choice.")
        return
    # ──────────────────────────────────────────────────────────────────────

    if choice == cancel_num:
        typewriter("Cancelled.")
        return

    if 1 <= choice <= len(player.inventory):
        item = player.inventory.pop(choice - 1)
        sell_price = item.price // 2
        player.gold += sell_price
        typewriter(f"Sold {item.name} for {sell_price} gold.")
        typewriter(f"Gold: {player.gold}")
        emit_player_stats(player)
    else:
        typewriter("Invalid choice.")