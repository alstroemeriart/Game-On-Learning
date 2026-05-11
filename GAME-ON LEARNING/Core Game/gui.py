"""
Game-On Learning — Redesigned GUI
- Left:   Character portrait + animated stat bars + hoverable attribute panel
- Center: World log + ALL choices rendered as buttons in-panel + text input
- Right:  Enemy panel
"""

from __future__ import annotations

import tkinter as tk
import threading
import queue
import os
import math
from typing import Any, Callable, Optional

# ── Palette ──────────────────────────────────────────────────────────────────
C = {
    "bg":           "#0d1117",
    "panel":        "#161b22",
    "panel2":       "#1c2128",
    "panel3":       "#21262d",
    "border":       "#30363d",
    "highlight":    "#58a6ff",
    "accent":       "#f78166",
    "accent2":      "#7ee787",
    "accent3":      "#e3b341",
    "text":         "#e6edf3",
    "text_dim":     "#8b949e",
    "text_muted":   "#484f58",
    "hp_high":      "#3fb950",
    "hp_mid":       "#d29922",
    "hp_low":       "#f85149",
    "focus_fill":   "#58a6ff",
    "streak_fill":  "#f78166",
    "exp_fill":     "#bc8cff",
    "btn_bg":       "#21262d",
    "btn_hover":    "#30363d",
    "btn_border":   "#30363d",
    "btn_active":   "#388bfd",
    "correct":      "#3fb950",
    "wrong":        "#f85149",
    "gold":         "#e3b341",
    "boss_color":   "#f85149",
    "elite_color":  "#e3b341",
    "node_future":  "#388bfd",
    "node_done":    "#3fb950",
    "node_current": "#f78166",
}

TOOLTIP_DEFS = {
    "ATK":    "Attack — determines base damage dealt to enemies.",
    "DEF":    "Defense — reduces incoming damage from enemy attacks.",
    "SPD":    "Speed — affects dodge chance. Higher SPD = harder to hit.",
    "WIS":    "Wisdom — scales damage and focus gain from correct answers.",
    "CRIT":   "Critical Chance — probability of landing a critical hit (double damage).",
    "Shield": "Shield — absorbs damage before HP is reduced.",
    "Level":  "Your current level. Level up by gaining enough EXP.",
    "Gold":   "Gold — currency used in the shop to buy aid items.",
    "HP":     "Hit Points — reach 0 and the run ends.",
    "Focus":  "Focus — fills on correct answers. At 100, use a special ability!",
    "Streak": "Streak — consecutive correct answers. Higher = more power.",
    "EXP":    "Experience — gain enough to level up and boost your stats.",
}


# ── Animated Bar Widget ───────────────────────────────────────────────────────

class AnimatedBar:
    """Canvas-based horizontal bar that smoothly interpolates to target values.
    
    Used for HP, Focus, EXP, and Streak bars. Displays current/max values and includes
    a subtle glossy highlight effect. Animations use 16ms step intervals for smooth motion.
    
    Attributes:
        canvas (tk.Canvas): Parent canvas to draw the bar on
        x, y, w, h (int): Position and dimensions of the bar
        fill (str): Hex color for the fill portion
        bg (str): Hex color for the empty/background portion
        label (str): Optional label text
        show_text (bool): Whether to display current/max text overlay
        _current (float): Current fill ratio (0.0-1.0), animated
        _target (float): Target fill ratio to animate toward
        _animating (bool): Whether animation is in progress
    """

    def __init__(self, canvas: tk.Canvas, x: int, y: int, w: int, h: int,
                 fill_color: str, bg_color: str = "#21262d", label: str = "",
                 show_text: bool = True):
        self.canvas = canvas
        self.x, self.y, self.w, self.h = x, y, w, h
        self.fill = fill_color
        self.bg = bg_color
        self.label = label
        self.show_text = show_text

        self._current = 0.0
        self._target  = 0.0
        self._val_str = ""
        self._animating = False

        # draw initial state
        self._draw(0.0)

    def set_value(self, current: float, maximum: float):
        """Update bar to show current/maximum values with smooth animation.
        
        Calculates the fill ratio and starts animation if needed. Automatically clips
        ratio to [0.0, 1.0] range to prevent over-filling.
        
        Args:
            current (float): Current value (numerator)
            maximum (float): Maximum value (denominator). Clamped to >= 1.
            
        Example:
            bar.set_value(75, 100)  # 75% full, displays "75/100"
        """
        ratio = current / max(1, maximum)
        self._target  = max(0.0, min(1.0, ratio))
        self._val_str = f"{int(current)}/{int(maximum)}"
        if not self._animating:
            self._animating = True
            self._step()

    def _step(self):
        diff = self._target - self._current
        if abs(diff) < 0.005:
            self._current = self._target
            self._draw(self._current)
            self._animating = False
            return
        self._current += diff * 0.18
        self._draw(self._current)
        self.canvas.after(16, self._step)

    def _draw(self, ratio: float):
        """Render the bar at a specific fill ratio.
        
        Draws three layers (bottom to top):
        1. Background track in bg_color with border
        2. Fill rectangle from 0 to ratio*width
        3. Glossy highlight stripe at top of fill
        4. Text overlay (current/max) centered on bar
        
        Uses unique tag f"bar_{id(self)}" to prevent overlapping previous renders.
        
        Args:
            ratio (float): Fill ratio from 0.0 (empty) to 1.0 (full)
        """
        c = self.canvas
        x, y, w, h = self.x, self.y, self.w, self.h

        c.delete(f"bar_{id(self)}")
        # background track
        c.create_rectangle(x, y, x + w, y + h,
                            fill=self.bg, outline=C["border"], width=1,
                            tags=f"bar_{id(self)}")
        # fill
        fw = max(0, int(w * ratio))
        if fw > 2:
            c.create_rectangle(x + 1, y + 1, x + fw - 1, y + h - 1,
                                fill=self.fill, outline="",
                                tags=f"bar_{id(self)}")
            # gloss highlight
            c.create_rectangle(x + 1, y + 1, x + fw - 1, y + 3,
                                fill=self._lighten(self.fill), outline="",
                                tags=f"bar_{id(self)}")
        # text
        if self.show_text and self._val_str:
            c.create_text(x + w // 2, y + h // 2,
                          text=self._val_str,
                          fill=C["text"], font=("Courier New", 8, "bold"),
                          tags=f"bar_{id(self)}")

    @staticmethod
    def _lighten(hex_color: str) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = min(255, r + 40)
        g = min(255, g + 40)
        b = min(255, b + 40)
        return f"#{r:02x}{g:02x}{b:02x}"


# ── Tooltip ───────────────────────────────────────────────────────────────────

class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text   = text
        self._tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event=None):
        if self._tip:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        frame = tk.Frame(self._tip, bg=C["panel3"],
                         highlightthickness=1, highlightbackground=C["highlight"])
        frame.pack()
        tk.Label(frame, text=self.text, bg=C["panel3"], fg=C["text"],
                 font=("Courier New", 9), padx=10, pady=6,
                 wraplength=220, justify="left").pack()

    def _hide(self, event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


# ── Portrait Canvas ───────────────────────────────────────────────────────────

class PortraitCanvas:
    """Animated placeholder portrait with idle animation."""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self._frame = 0
        self._class_name = ""
        self._animate()

    def set_class(self, class_name: str):
        self._class_name = class_name

    def _animate(self):
        self._frame += 1
        self._draw()
        self.canvas.after(80, self._animate)

    def _draw(self):
        c = self.canvas
        c.delete("all")
        W, H = int(c["width"]), int(c["height"])
        t = self._frame * 0.05

        # Animated background glow
        r_glow = 55 + math.sin(t) * 8
        c.create_oval(W//2 - r_glow, H//2 - r_glow,
                      W//2 + r_glow, H//2 + r_glow,
                      fill="#1a2a1a", outline=C["accent2"], width=1)

        # Body silhouette
        body_y = int(H * 0.55 + math.sin(t * 0.7) * 2)
        c.create_oval(W//2 - 22, H//2 - 45, W//2 + 22, H//2 - 5,
                      fill=C["panel3"], outline=C["border"])
        c.create_rectangle(W//2 - 28, body_y - 10, W//2 + 28, H - 20,
                            fill=C["panel3"], outline=C["border"])

        # Face
        c.create_oval(W//2 - 18, H//2 - 42, W//2 + 18, H//2 - 10,
                      fill="#2d2520", outline=C["border"])
        # Eyes — blink occasionally
        blink = (self._frame % 60 < 3)
        ey = H//2 - 30
        if blink:
            c.create_line(W//2 - 8, ey, W//2 - 3, ey, fill=C["text"], width=2)
            c.create_line(W//2 + 3, ey, W//2 + 8, ey, fill=C["text"], width=2)
        else:
            c.create_oval(W//2 - 10, ey - 4, W//2 - 4, ey + 4,
                          fill=C["highlight"], outline="")
            c.create_oval(W//2 + 4,  ey - 4, W//2 + 10, ey + 4,
                          fill=C["highlight"], outline="")

        # Class indicator pulse
        class_col = C["accent2"] if self._class_name else C["text_muted"]
        c.create_text(W//2, H - 12,
                      text=self._class_name or "? ? ?",
                      fill=class_col,
                      font=("Courier New", 8, "bold"))

        # Corner decorations
        for cx2, cy2, anch in [(4, 4, "nw"), (W-4, 4, "ne"),
                               (4, H-4, "sw"), (W-4, H-4, "se")]:
            c.create_text(cx2, cy2, text="◆", anchor=anch,  # type: ignore
                          fill=C["border"], font=("Courier New", 7))


# ── Enemy Canvas ──────────────────────────────────────────────────────────────

class EnemyCanvas:
    """Animated enemy silhouette with enhanced animations."""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self._frame = 0
        self._role  = "idle"
        self._name  = ""
        self._alive = False
        self._hit_flash = 0  # Frames remaining for hit flash
        self._knockback_x = 0  # Knockback offset
        self._knockback_timer = 0
        self._animate()

    def set_enemy(self, role: str, name: str):
        self._role  = role
        self._name  = name
        self._alive = True

    def clear(self):
        self._alive = False
        self._role  = "idle"
        self._name  = ""
    
    def trigger_hit(self):
        """Trigger visual hit feedback."""
        self._hit_flash = 6  # Flash for 6 frames
        self._knockback_x = -15
        self._knockback_timer = 8

    def _animate(self):
        self._frame += 1
        self._draw()
        self.canvas.after(80, self._animate)

    def _draw(self):
        c = self.canvas
        c.delete("all")
        W, H = int(c["width"]), int(c["height"])
        t = self._frame * 0.06

        accent = {"boss":  C["boss_color"],
                  "elite": C["elite_color"],
                  "enemy": C["highlight"]}.get(self._role, C["text_muted"])

        # Background
        bg_color = C["panel2"]
        if self._hit_flash > 0:
            # Flash white on hit
            flash_intensity = self._hit_flash / 6.0
            r, g, b = int(255 * flash_intensity), int(255 * flash_intensity), int(255 * flash_intensity)
            bg_color = f"#{r:02x}{g:02x}{b:02x}"
            self._hit_flash -= 1
        
        c.create_rectangle(0, 0, W, H, fill=bg_color, outline="")

        if not self._alive:
            c.create_text(W//2, H//2, text="No enemy\nencountered",
                          fill=C["text_muted"], font=("Courier New", 9),
                          justify="center")
            return

        # Apply knockback offset
        x_offset = 0
        if self._knockback_timer > 0:
            progress = 1 - (self._knockback_timer / 8.0)
            x_offset = int(self._knockback_x * (1 - progress * progress))  # Ease out
            self._knockback_timer -= 1

        # Glow
        r_glow = 50 + math.sin(t) * 6
        c.create_oval(W//2 - r_glow + x_offset, H//2 - r_glow + 5,
                      W//2 + r_glow + x_offset, H//2 + r_glow + 5,
                      fill="", outline=accent, width=1)

        float_y = int(math.sin(t * 0.8) * 4)

        if self._role == "boss":
            # Large menacing boss shape
            c.create_oval(W//2 - 35 + x_offset, H//2 - 55 + float_y,
                          W//2 + 35 + x_offset, H//2 - 5 + float_y,
                          fill="#2a0a0a", outline=accent, width=2)
            # Horns
            for dx in (-28, 22):
                c.create_polygon(W//2 + dx + x_offset, H//2 - 52 + float_y,
                                 W//2 + dx + 8 + x_offset, H//2 - 70 + float_y,
                                 W//2 + dx + 16 + x_offset, H//2 - 52 + float_y,
                                 fill=accent, outline="")
            # Eyes (glowing)
            ey = H//2 - 35 + float_y
            blink = (self._frame % 40 < 2)
            if not blink:
                c.create_oval(W//2 - 22 + x_offset, ey - 5, W//2 - 10 + x_offset, ey + 5,
                              fill=accent, outline="")
                c.create_oval(W//2 + 10 + x_offset,  ey - 5, W//2 + 22 + x_offset, ey + 5,
                              fill=accent, outline="")
            # Body
            c.create_rectangle(W//2 - 30 + x_offset, H//2 - 10 + float_y,
                                W//2 + 30 + x_offset, H//2 + 40 + float_y,
                                fill="#1a0808", outline=accent, width=1)
        elif self._role == "elite":
            # Armored elite shape
            c.create_oval(W//2 - 25 + x_offset, H//2 - 48 + float_y,
                          W//2 + 25 + x_offset, H//2 - 8 + float_y,
                          fill="#1a1a0a", outline=accent, width=2)
            ey = H//2 - 32 + float_y
            c.create_oval(W//2 - 14 + x_offset, ey - 4, W//2 - 5 + x_offset, ey + 4,
                          fill=accent, outline="")
            c.create_oval(W//2 + 5 + x_offset,  ey - 4, W//2 + 14 + x_offset, ey + 4,
                          fill=accent, outline="")
            c.create_rectangle(W//2 - 22 + x_offset, H//2 - 10 + float_y,
                                W//2 + 22 + x_offset, H//2 + 32 + float_y,
                                fill="#141408", outline=accent, width=1)
        else:
            # Standard enemy
            c.create_oval(W//2 - 20 + x_offset, H//2 - 42 + float_y,
                          W//2 + 20 + x_offset, H//2 - 6 + float_y,
                          fill=C["panel3"], outline=accent, width=1)
            ey = H//2 - 28 + float_y
            c.create_oval(W//2 - 12 + x_offset, ey - 3, W//2 - 5 + x_offset, ey + 3,
                          fill=accent, outline="")
            c.create_oval(W//2 + 5 + x_offset,  ey - 3, W//2 + 12 + x_offset, ey + 3,
                          fill=accent, outline="")
            c.create_rectangle(W//2 - 18 + x_offset, H//2 - 8 + float_y,
                                W//2 + 18 + x_offset, H//2 + 28 + float_y,
                                fill=C["panel2"], outline=accent, width=1)

        # Name tag
        c.create_rectangle(0, H - 22, W, H, fill="#1a1a1a", outline="")
        c.create_text(W//2, H - 11, text=self._name,
                      fill=accent, font=("Courier New", 9, "bold"))


# ── Choice Button Row ─────────────────────────────────────────────────────────

def _make_choice_btn(parent: tk.Widget, label: str,
                     cmd: Callable, width: int = 0) -> tk.Button:
    btn = tk.Button(
        parent, text=label, command=cmd,
        bg=C["btn_bg"], fg=C["text"],
        activebackground=C["btn_active"], activeforeground="#ffffff",
        relief="flat", cursor="hand2",
        font=("Courier New", 10, "bold"),
        bd=0, padx=10, pady=8,
        highlightthickness=1,
        highlightbackground=C["btn_border"],
        highlightcolor=C["highlight"],
    )
    if width:
        btn.config(width=width)

    def _on_enter(e):
        if str(btn["state"]) == "normal":
            btn.config(bg=C["btn_hover"],
                       highlightbackground=C["highlight"])

    def _on_leave(e):
        btn.config(bg=C["btn_bg"],
                   highlightbackground=C["btn_border"])

    btn.bind("<Enter>", _on_enter)
    btn.bind("<Leave>", _on_leave)
    return btn


# ── Main Window ───────────────────────────────────────────────────────────────

class GameGUI:
    """Main GUI window for Game-On Learning.
    
    Three-panel layout:
    - Left (210px): Character portrait, animated stat bars, attribute tooltips
    - Center (1:weight): Narrative log, action buttons, text input
    - Right (240px): Enemy stats panel, branching tree map
    
    Runs on main thread, communicates with game loop via threadsafe queue.
    Processes events from queue with _poll() loop (60 FPS).
    Handles keyboard shortcuts (I=inventory, ?=help, Esc=pause hint).
    
    Attributes:
        root (tk.Tk): Main window
        _q (queue.Queue): Threadsafe queue for game->GUI events
        _player (dict): Current player stats (name, hp, gold, etc)
        _enemy (dict): Current enemy stats
        _choices_active (bool): Whether action buttons are clickable
        _map_history (list[str]): Cleared node types in order
        _map_pending (list[str]): Available next node choices
        _animation_managers (dict): AnimationManager per GUI element
    """
    def __init__(self, root: tk.Tk, last_run_path: str = "last_run.txt") -> None:
        self.root = root
        self.root.title("Game-On Learning")
        self.root.configure(bg=C["bg"])
        self.root.geometry("1366x768")
        self.root.minsize(1024, 640)

        self._q: queue.Queue[Any] = queue.Queue()
        self._player: dict[str, Any] = {}
        self._enemy:  dict[str, Any] = {}
        self._last_run_path  = last_run_path
        self._choices_active = False

        # Map state
        self._map_history: list[str] = []
        self._map_pending:  list[str] = []

        self._build_ui()
        self._setup_keyboard_shortcuts()
        self._poll()
        
        # Trigger initial title screen display
        self._q.put(("title_screen",))

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construct the three-panel layout.
        
        Creates column/row grid configuration with proper weights:
        - Column 0 (Left): Fixed 210px
        - Column 1 (Center): Flexible (weight=1)
        - Column 2 (Right): Fixed 240px
        
        Calls _build_left(), _build_center(), _build_right() to populate each panel.
        """
        self.root.columnconfigure(0, weight=0, minsize=210)
        self.root.columnconfigure(1, weight=1)
        self.root.columnconfigure(2, weight=0, minsize=240)
        self.root.rowconfigure(0, weight=1)

        self._build_left()
        self._build_center()
        self._build_right()

    def _setup_keyboard_shortcuts(self) -> None:
        """Set up global keyboard shortcuts for the game.
        
        Shortcuts:
        - 'I': Show inventory list
        - '?': Show help (keyboard shortcuts)
        - 'Esc': Show pause menu hint
        
        Each shortcut displays output to the narrative log via ui.bus.say().
        """
        import ui as _ui
        
        def _show_inventory(event=None):
            """Show inventory list on 'I' key."""
            if self._player:
                inventory = self._player.get("inventory", [])
                if inventory:
                    _ui.bus.say(f"\n=== INVENTORY ({len(inventory)} items) ===")
                    for i, item in enumerate(inventory, 1):
                        item_name = item.get('name', 'Unknown') if isinstance(item, dict) else getattr(item, 'name', 'Unknown')
                        _ui.bus.say(f"  {i}. {item_name}")
                    _ui.bus.say("=" * 40)
                else:
                    _ui.bus.say("\nYour inventory is empty.")
            return "break"
        
        def _show_help(event=None):
            """Show keyboard shortcuts on '?' key."""
            from main import KEYBOARD_SHORTCUTS
            _ui.bus.say("\n" + "=" * 50)
            _ui.bus.say("      KEYBOARD SHORTCUTS")
            _ui.bus.say("=" * 50)
            for key, (name, desc) in KEYBOARD_SHORTCUTS.items():
                _ui.bus.say(f"  {key:15} — {name}")
                _ui.bus.say(f"  {'':15}   {desc}")
            _ui.bus.say("=" * 50)
            return "break"
        
        def _show_pause_hint(event=None):
            """Show pause menu hint on 'Escape' key."""
            _ui.bus.say("\n[Pause Menu Hint] You cannot pause during combat!")
            _ui.bus.say("  You can use '?' for help or 'I' to check inventory.")
            return "break"
        
        self.root.bind('<i>', _show_inventory, add='+')
        self.root.bind('<I>', _show_inventory, add='+')
        self.root.bind('<?>', _show_help, add='+')
        self.root.bind('<question>', _show_help, add='+')
        self.root.bind('<Escape>', _show_pause_hint, add='+')

    # ── LEFT PANEL ───────────────────────────────────────────────────────────

    def _build_left(self) -> None:
        """Construct left panel: character portrait + stat bars + attribute tooltips.
        
        Layout (top to bottom):
        1. Character portrait placeholder (50x50 circle)
        2. Character name label
        3. Animated bars: HP, Focus, EXP
        4. Stat grid: ATK, DEF, SPD, WIS, CRIT (with tooltips)
        5. Streak/Gold/Level display
        
        All widgets populated by _update_player_stats() during gameplay.
        """
        outer = tk.Frame(self.root, bg=C["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=(6, 3), pady=6)
        outer.rowconfigure(0, weight=0)
        outer.rowconfigure(1, weight=0)
        outer.rowconfigure(2, weight=1)
        outer.columnconfigure(0, weight=1)

        # ── Portrait ──────────────────────────────────────────────────────
        port_frame = tk.Frame(outer, bg=C["panel"],
                              highlightthickness=1,
                              highlightbackground=C["border"])
        port_frame.grid(row=0, column=0, sticky="ew", pady=(0, 3))

        tk.Label(port_frame, text="CHARACTER", bg=C["panel"], fg=C["text_dim"],
                 font=("Courier New", 8, "bold")).pack(pady=(6, 2))

        self.lbl_name = tk.Label(port_frame, text="—", bg=C["panel"], fg=C["text"],
                                 font=("Courier New", 12, "bold"))
        self.lbl_name.pack()

        self.lbl_class = tk.Label(port_frame, text="", bg=C["panel"],
                                  fg=C["highlight"], font=("Courier New", 9))
        self.lbl_class.pack(pady=(0, 4))

        portrait_cv = tk.Canvas(port_frame, width=160, height=140,
                                bg=C["panel2"],
                                highlightthickness=1,
                                highlightbackground=C["border"])
        portrait_cv.pack(padx=8, pady=(0, 8))
        self._portrait = PortraitCanvas(portrait_cv)

        # ── Animated Stat Bars ────────────────────────────────────────────
        bars_frame = tk.Frame(outer, bg=C["panel"],
                              highlightthickness=1,
                              highlightbackground=C["border"])
        bars_frame.grid(row=1, column=0, sticky="ew", pady=(0, 3))

        tk.Label(bars_frame, text="VITALS", bg=C["panel"], fg=C["text_dim"],
                 font=("Courier New", 8, "bold")).pack(pady=(6, 4), padx=8, anchor="w")

        bars_cv = tk.Canvas(bars_frame, bg=C["panel"], height=140,
                            highlightthickness=0)
        bars_cv.pack(fill="x", padx=10, pady=(0, 10))

        # We'll draw labels inline via canvas text
        self._bars_cv = bars_cv
        self._hp_bar     = None
        self._focus_bar  = None
        self._streak_bar = None
        self._exp_bar    = None
        bars_cv.bind("<Configure>", self._init_bars)

        # ── Attribute Grid ────────────────────────────────────────────────
        attrs_frame = tk.Frame(outer, bg=C["panel"],
                               highlightthickness=1,
                               highlightbackground=C["border"])
        attrs_frame.grid(row=2, column=0, sticky="nsew")

        tk.Label(attrs_frame, text="ATTRIBUTES", bg=C["panel"], fg=C["text_dim"],
                 font=("Courier New", 8, "bold")).pack(pady=(6, 4), padx=8, anchor="w")

        self._attr_grid = tk.Frame(attrs_frame, bg=C["panel"])
        self._attr_grid.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._attr_labels: dict[str, tk.Label] = {}
        self._build_attr_grid()

    def _init_bars(self, event=None):
        """Create AnimatedBar instances once the canvas has a real width."""
        cv  = self._bars_cv
        w   = cv.winfo_width() or 180
        bar_w = w - 4
        row_h = 32

        def make_row(label: str, y: int, fill: str) -> AnimatedBar:
            cv.create_text(0, y, text=label, anchor="nw",
                           font=("Courier New", 8, "bold"),
                           fill=C["text_dim"], tags="label")
            bar = AnimatedBar(cv, 0, y + 14, bar_w, 12, fill)
            return bar

        self._hp_bar     = make_row("HP",     0,        C["hp_high"])
        self._focus_bar  = make_row("FOCUS",  row_h,    C["focus_fill"])
        self._streak_bar = make_row("STREAK", row_h*2,  C["streak_fill"])
        self._exp_bar    = make_row("EXP",    row_h*3,  C["exp_fill"])
        cv.config(height=row_h * 4 + 4)
        cv.unbind("<Configure>")

        # tooltips on bar labels via invisible rectangles
        # (tooltips work via label widgets below)

    def _build_attr_grid(self):
        attrs = [
            ("Level", "1"),  ("Gold",  "0"),
            ("ATK",   "0"),  ("DEF",   "0"),
            ("SPD",   "0"),  ("WIS",   "0"),
            ("CRIT",  "0%"), ("Shield","0"),
        ]
        for i, (key, val) in enumerate(attrs):
            r, c = divmod(i, 2)
            cell = tk.Frame(self._attr_grid, bg=C["panel2"],
                            highlightthickness=1,
                            highlightbackground=C["border"])
            cell.grid(row=r, column=c, padx=2, pady=2, sticky="ew")
            self._attr_grid.columnconfigure(c, weight=1)

            tk.Label(cell, text=key, bg=C["panel2"], fg=C["text_dim"],
                     font=("Courier New", 7, "bold")).pack(side="left", padx=(6, 2))
            lbl = tk.Label(cell, text=val, bg=C["panel2"], fg=C["text"],
                           font=("Courier New", 10, "bold"))
            lbl.pack(side="right", padx=(2, 6))
            self._attr_labels[key] = lbl

            tip_text = TOOLTIP_DEFS.get(key, "")
            if tip_text:
                Tooltip(cell, tip_text)
                cell.config(cursor="question_arrow")

    # ── CENTER PANEL ─────────────────────────────────────────────────────────

    def _build_center(self) -> None:
        outer = tk.Frame(self.root, bg=C["bg"])
        outer.grid(row=0, column=1, sticky="nsew", padx=3, pady=6)
        outer.rowconfigure(0, weight=1)
        outer.rowconfigure(1, weight=0)
        outer.rowconfigure(2, weight=0)
        outer.columnconfigure(0, weight=1)

        # Title bar
        title_bar = tk.Frame(outer, bg=C["panel"],
                             highlightthickness=1,
                             highlightbackground=C["border"])
        title_bar.grid(row=0, column=0, sticky="nsew", pady=(0, 3))
        title_bar.rowconfigure(0, weight=1)
        title_bar.columnconfigure(0, weight=1)

        # Scrolled text log
        log_frame = tk.Frame(title_bar, bg=C["bg"])
        log_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log = tk.Text(
            log_frame,
            wrap=tk.WORD, state="disabled",
            bg=C["bg"], fg=C["text"],
            font=("Courier New", 11),
            insertbackground=C["text"],
            relief="flat", bd=0,
            padx=14, pady=10,
            selectbackground=C["panel2"],
        )
        sb = tk.Scrollbar(log_frame, command=self.log.yview,
                          bg=C["panel2"], troughcolor=C["bg"],
                          relief="flat", bd=0)
        self.log.config(yscrollcommand=sb.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        # Text color tags
        for tag, col, bold in [
            ("correct",  C["correct"],      True),
            ("wrong",    C["wrong"],         True),
            ("gold",     C["gold"],          False),
            ("system",   C["highlight"],     True),
            ("dim",      C["text_dim"],      False),
            ("streak",   C["streak_fill"],   True),
            ("hp_low",   C["hp_low"],        True),
            ("accent",   C["accent"],        True),
            ("boss",     C["boss_color"],    True),
            ("elite",    C["elite_color"],   True),
        ]:
            fnt = ("Courier New", 11, "bold") if bold else ("Courier New", 11)
            self.log.tag_config(tag, foreground=col, font=fnt)
        self.log.tag_config("separator",
                            foreground=C["border"],
                            font=("Courier New", 6))

        # ── Input row ─────────────────────────────────────────────────────
        inp_frame = tk.Frame(outer, bg=C["panel"],
                             highlightthickness=1,
                             highlightbackground=C["border"])
        inp_frame.grid(row=1, column=0, sticky="ew", pady=(0, 3))
        inp_frame.columnconfigure(0, weight=1)

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(
            inp_frame,
            textvariable=self.entry_var,
            bg=C["panel2"], fg=C["text"],
            insertbackground=C["highlight"],
            relief="flat",
            font=("Courier New", 11),
            bd=0,
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(10, 4), pady=8, ipady=6)
        self.entry.bind("<Return>", lambda _: self._submit())
        self.entry.focus_set()

        self.submit_btn = _make_choice_btn(inp_frame, "SUBMIT", self._submit, width=8)
        self.submit_btn.grid(row=0, column=1, padx=(0, 4), pady=8)

        # Auto-play button
        self.auto_play_btn = _make_choice_btn(inp_frame, "AUTO", self._toggle_auto_play, width=6)
        self.auto_play_btn.grid(row=0, column=2, padx=(0, 10), pady=8)
        self._auto_play_active = False
        self._update_auto_play_btn_style()

        # ── Choice area (ALL choices go here) ─────────────────────────────
        self.choice_outer = tk.Frame(outer, bg=C["panel"],
                                     highlightthickness=1,
                                     highlightbackground=C["border"])
        self.choice_outer.grid(row=2, column=0, sticky="ew")
        self.choice_outer.columnconfigure(0, weight=1)

        self._choice_label = tk.Label(
            self.choice_outer,
            text="",
            bg=C["panel"], fg=C["text_dim"],
            font=("Courier New", 8, "bold"),
        )
        self._choice_label.pack(anchor="w", padx=10, pady=(6, 0))

        self.choice_inner = tk.Frame(self.choice_outer, bg=C["panel"])
        self.choice_inner.pack(fill="x", padx=8, pady=(4, 8))

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────

    def _build_right(self) -> None:
        outer = tk.Frame(self.root, bg=C["bg"])
        outer.grid(row=0, column=2, sticky="nsew", padx=(3, 6), pady=6)
        outer.rowconfigure(0, weight=0)
        outer.rowconfigure(1, weight=0)
        outer.rowconfigure(2, weight=1)
        outer.columnconfigure(0, weight=1)

        # ── Enemy panel ───────────────────────────────────────────────────
        enemy_frame = tk.Frame(outer, bg=C["panel"],
                               highlightthickness=1,
                               highlightbackground=C["border"])
        enemy_frame.grid(row=0, column=0, sticky="ew", pady=(0, 3))

        tk.Label(enemy_frame, text="ENCOUNTER", bg=C["panel"],
                 fg=C["text_dim"], font=("Courier New", 8, "bold")).pack(
            pady=(6, 2), padx=8, anchor="w")

        self.lbl_enemy_name = tk.Label(enemy_frame, text="No encounter",
                                        bg=C["panel"], fg=C["text"],
                                        font=("Courier New", 11, "bold"))
        self.lbl_enemy_name.pack()

        enemy_cv = tk.Canvas(enemy_frame, width=220, height=140,
                             bg=C["panel2"],
                             highlightthickness=1,
                             highlightbackground=C["border"])
        enemy_cv.pack(padx=8, pady=4)
        self._enemy_canvas_obj = EnemyCanvas(enemy_cv)

        # Enemy stat bars
        self._enemy_bars_cv = tk.Canvas(enemy_frame, bg=C["panel"],
                                         height=90, highlightthickness=0)
        self._enemy_bars_cv.pack(fill="x", padx=10, pady=(0, 6))
        self._enemy_hp_bar  = None
        self._enemy_bars_cv.bind("<Configure>", self._init_enemy_bars)

        # Enemy text stats (ATK / DEF / CRIT)
        self.lbl_enemy_stats = tk.Label(enemy_frame, text="",
                                         bg=C["panel"], fg=C["text_dim"],
                                         font=("Courier New", 8),
                                         justify="left")
        self.lbl_enemy_stats.pack(padx=8, anchor="w", pady=(0, 6))

        # ── Inventory ───────────────────────────────────────────────────
        inventory_frame = tk.Frame(outer, bg=C["panel"],
                                   highlightthickness=1,
                                   highlightbackground=C["border"])
        inventory_frame.grid(row=1, column=0, sticky="nsew")
        inventory_frame.rowconfigure(1, weight=1)
        inventory_frame.columnconfigure(0, weight=1)

        header = tk.Frame(inventory_frame, bg=C["panel"])
        header.pack(fill="x")
        tk.Label(header, text="INVENTORY", bg=C["panel"],
                 fg=C["text_dim"], font=("Courier New", 8, "bold")).pack(
            side="left", padx=8, pady=(6, 2))
        self.lbl_inventory_count = tk.Label(header, text="0 items",
                                            bg=C["panel"], fg=C["highlight"],
                                            font=("Courier New", 8, "bold"))
        self.lbl_inventory_count.pack(side="right", padx=8, pady=(6, 2))

        # Inventory listbox with scrollbar
        inventory_container = tk.Frame(inventory_frame, bg=C["panel"])
        inventory_container.pack(fill="both", expand=True, padx=8, pady=(2, 8))

        scrollbar = tk.Scrollbar(inventory_container, bg=C["panel2"])
        scrollbar.pack(side="right", fill="y")

        self.inventory_listbox = tk.Listbox(
            inventory_container,
            bg=C["panel2"],
            fg=C["text"],
            selectbackground=C["highlight"],
            selectforeground="#000000",
            font=("Courier New", 8),
            highlightthickness=1,
            highlightbackground=C["border"],
            yscrollcommand=scrollbar.set
        )
        self.inventory_listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self.inventory_listbox.yview)

        # Bind double-click to use item
        self.inventory_listbox.bind('<Double-Button-1>', self._use_inventory_item)

    def _init_enemy_bars(self, _event=None):
        cv  = self._enemy_bars_cv
        w   = cv.winfo_width() or 200
        bar_w = w - 4
        row_h = 28

        def make_row(label: str, y: int, fill: str) -> AnimatedBar:
            cv.create_text(0, y, text=label, anchor="nw",
                           font=("Courier New", 7, "bold"),
                           fill=C["text_dim"], tags="el")
            return AnimatedBar(cv, 0, y + 12, bar_w, 10, fill)

        self._enemy_hp_bar   = make_row("HP",   0,        C["hp_high"])
        cv.config(height=row_h + 4)
        cv.unbind("<Configure>")

    # ── Log helpers ───────────────────────────────────────────────────────────

    def _trigger_message_animations(self, text: str) -> None:
        """Parse message content and trigger appropriate animations."""
        low = text.lower()
        
        # Skip if message is system/separator
        if text.startswith(("=", "*", "-", "  TIER", "  BOSS", "  RUN", "***")):
            return
        
        # Extract numeric values from message
        import re
        numbers = re.findall(r'\d+', text)
        amount = int(numbers[0]) if numbers else 0
        
        # Trigger animations based on keywords
        animation_types = {
            ("correct!", "flawless", "knowledge applied"): ("correct", {}),
            ("incorrect!", "wrong!", "failed", "no dodge", "incorrect"): ("incorrect", {}),
            ("found", "earned", "gained"): ("gold_gained", {"amount": amount}) if "gold" in low else None,
            ("critical hit", "heavy hit"): ("critical", {}),
            ("dodge", "avoided", "evade"): ("dodge", {}),
            ("focus",): ("focus_gain", {"amount": amount}),
            ("streak",): ("streak_gain", {"streak": amount}),
            ("level up", "level increased", "leveled"): ("level_up", {"level": amount}),
            ("heal", "restore", "recover"): ("heal", {"amount": amount}),
            ("poison", "burn", "freeze", "stun"): ("status_applied", {}),
            ("shield", "protect", "guard"): ("shield_gained", {"amount": amount}),
            ("defeated", "victory", "won"): ("enemy_defeated", {}),
            ("game over", "you were defeated"): ("player_defeated", {}),
            ("boss", "phase"): ("boss_event", {}),
            ("mastery",): ("mastery_milestone", {}),
            ("skill", "unlock"): ("skill_unlocked", {}),
        }
        
        for keywords, animation_info in animation_types.items():
            if animation_info and any(kw in low for kw in keywords):
                anim_type, data = animation_info
                data["message"] = text
                self._q.put(("combat_anim", anim_type, data))
                break

    def _do_log(self, text: str, tag: Optional[str]) -> None:
        self.log.config(state="normal")
        self.log.insert("end", text + "\n", tag or "")
        self.log.see("end")
        self.log.config(state="disabled")
        
        # Trigger animations based on message content
        self._trigger_message_animations(text)

    def _do_clear(self) -> None:
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    @staticmethod
    def _classify(text: str) -> Optional[str]:
        low = text.lower()
        if any(w in low for w in ("correct!", "flawless", "knowledge applied")):
            return "correct"
        if any(w in low for w in ("incorrect!", "wrong!", "failed", "no dodge")):
            return "wrong"
        if "gold" in low and any(w in low for w in ("found", "earned", "gained")):
            return "gold"
        if any(w in low for w in ("critical hit", "heavy hit", "critical strike")):
            return "accent"
        if "streak:" in low or "streak →" in low or "streak ✦" in low:
            return "streak"
        if any(w in low for w in ("defeated", "game over", "you were defeated")):
            return "hp_low"
        if any(w in low for w in ("boss", "phase")):
            return "boss"
        if "elite" in low:
            return "elite"
        if text.startswith(("=", "*", "  TIER", "  BOSS", "  RUN", "***")):
            return "system"
        if text.startswith("---") or text.startswith("==="):
            return "separator"
        return None

    # ── Player update ─────────────────────────────────────────────────────────

    def _do_update_player(self, d: dict[str, Any]) -> None:
        self._player.update(d)
        p = self._player

        self.lbl_name.config(text=p.get("name", "—"))
        self.lbl_class.config(text=p.get("class_name", ""))
        self._portrait.set_class(p.get("class_name", ""))

        hp     = int(p.get("hp", 1))
        mhp    = int(p.get("max_hp", 1))
        focus  = int(p.get("focus", 0))
        mfocus = int(p.get("max_focus", 100))
        streak = int(p.get("streak", 0))
        exp    = int(p.get("exp", 0))
        mexp   = int(p.get("xp_to_next", 100))

        hp_color = C["hp_high"] if hp / max(1, mhp) > 0.5 else \
                   C["hp_mid"]  if hp / max(1, mhp) > 0.25 else C["hp_low"]

        # Update bar colors dynamically
        if self._hp_bar:
            self._hp_bar.fill = hp_color
            self._hp_bar.set_value(hp, mhp)
        if self._focus_bar:
            self._focus_bar.set_value(focus, mfocus)
        if self._streak_bar:
            self._streak_bar.set_value(min(streak, 25), 25)
            self._streak_bar._val_str = str(streak)
        if self._exp_bar:
            self._exp_bar.set_value(exp, mexp)

        # Attribute grid
        attr_vals = {
            "Level":  str(p.get("lvl", 1)),
            "Gold":   str(p.get("gold", 0)),
            "ATK":    str(p.get("atk", 0)),
            "DEF":    str(p.get("defense", 0)),
            "SPD":    str(p.get("spd", 0)),
            "WIS":    str(p.get("wisdom", 0)),
            "CRIT":   f"{int(p.get('crit_chance', 0) * 100)}%",
            "Shield": str(p.get("shield", 0)),
        }
        for key, val in attr_vals.items():
            if key in self._attr_labels:
                # Color-code important attrs
                col = C["text"]
                if key == "Gold":
                    col = C["gold"]
                elif key == "CRIT" and p.get("crit_chance", 0) > 0.3:
                    col = C["accent"]
                self._attr_labels[key].config(text=val, fg=col)

        # Update inventory display
        self._update_inventory_display()

    # ── Enemy update ──────────────────────────────────────────────────────────

    def _do_update_enemy(self, data: dict[str, Any]) -> None:
        self._enemy = dict(data)
        role = str(data.get("role", "enemy"))
        name = str(data.get("target_name", "Unknown"))
        hp   = int(data.get("hp", 0))
        mhp  = int(data.get("max_hp", 1))
        atk  = int(data.get("atk", 0))
        defn = int(data.get("defense", 0))
        crit = int(float(data.get("crit_chance", 0)) * 100)

        role_labels = {"enemy": "Enemy", "elite": "⚡ ELITE", "boss": "☠ BOSS"}
        color = {"enemy": C["text"], "elite": C["elite_color"],
                 "boss": C["boss_color"]}.get(role, C["text"])

        self.lbl_enemy_name.config(
            text=f"{role_labels.get(role, '')} {name}", fg=color)

        self._enemy_canvas_obj.set_enemy(role, name)

        if self._enemy_hp_bar:
            hp_col = C["hp_high"] if hp / max(1, mhp) > 0.5 else \
                     C["hp_mid"]  if hp / max(1, mhp) > 0.25 else C["hp_low"]
            self._enemy_hp_bar.fill = hp_col
            self._enemy_hp_bar.set_value(hp, mhp)

        status_list = data.get("status_effects", [])
        status_str  = ("  " + " | ".join(status_list)) if status_list else "  None"
        self.lbl_enemy_stats.config(
            text=f"  ATK {atk}  DEF {defn}  CRIT {crit}%\n  Status: {status_str}")

    def _do_clear_enemy(self) -> None:
        self._enemy = {}
        self.lbl_enemy_name.config(text="No encounter", fg=C["text_dim"])
        self._enemy_canvas_obj.clear()
        if self._enemy_hp_bar:
            self._enemy_hp_bar.set_value(0, 1)
        self.lbl_enemy_stats.config(text="")

    # ── Choice area (ALL choices go here now) ─────────────────────────────────

    def _do_show_choices(self, options: list[Any], prompt: str = "", auto_selected: dict | None = None) -> None:
        for w in self.choice_inner.winfo_children():
            w.destroy()

        has_choices = bool(options)
        self._choices_active = has_choices
        self._set_input_enabled(not has_choices)

        self._choice_label.config(text=prompt.upper() if prompt else
                                  ("SELECT AN OPTION" if has_choices else ""))

        if not has_choices:
            return

        # Determine layout: if many options, use 2 columns; short options single row
        columns = 1
        if len(options) > 3:
            columns = 2
        if len(options) <= 6 and all(
            len(str(o.get("label", o) if isinstance(o, dict) else o)) < 25
            for o in options
        ):
            columns = min(len(options), 3)

        for col in range(columns):
            self.choice_inner.columnconfigure(col, weight=1)

        for idx, opt in enumerate(options):
            if isinstance(opt, dict):
                label = str(opt.get("label", opt.get("value", "")))
                value = str(opt.get("value", label))
                log   = str(opt.get("log", label))
            else:
                label = str(opt)
                value = label
                log   = label

            row = idx // columns
            col = idx % columns

            btn = _make_choice_btn(
                self.choice_inner, label,
                lambda v=value, shown=log: self._choice(v, shown),
            )
            
            # Highlight auto-selected choice
            if auto_selected and value == auto_selected.get("value"):
                btn.config(bg=C["accent3"], fg="#000000")
            
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="ew")

    def _choice(self, value: str, shown: Optional[str] = None) -> None:
        self._do_log(f"  > {shown or value}", "dim")
        import ui as _ui
        _ui.input_handler.push_answer(value)
        self._do_show_choices([])

    def _set_input_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.entry.config(state=state)
        self.submit_btn.config(state=state)
        if enabled:
            self.entry.focus_set()
        else:
            self.entry_var.set("")

    def _submit(self) -> None:
        text = self.entry_var.get().strip()
        # Allow empty submissions (just pressing Enter to continue)
        self.entry_var.set("")
        if text:
            self._do_log(f"  > {text}", "dim")
        import ui as _ui
        _ui.input_handler.push_answer(text)

    def _toggle_auto_play(self) -> None:
        """Toggle auto-play mode on/off."""
        import ui as _ui
        self._auto_play_active = _ui.input_handler.toggle_auto_play()
        self._update_auto_play_btn_style()
        status = "AUTO-PLAY ENABLED" if self._auto_play_active else "Auto-play disabled"
        self._do_log(f"\n[{status}]", "system")

    def _update_auto_play_btn_style(self) -> None:
        """Update auto-play button styling based on active state."""
        if self._auto_play_active:
            self.auto_play_btn.config(
                bg=C["accent2"],
                activebackground=C["accent2"],
                fg="#000000",
                activeforeground="#000000"
            )
        else:
            self.auto_play_btn.config(
                bg=C["btn_bg"],
                activebackground=C["btn_active"],
                fg=C["text"],
                activeforeground="#ffffff"
            )

    # ── Map update ────────────────────────────────────────────────────────────

    def _do_map_update(self, text: str, history: list[str] | None = None, pending: list[str] | None = None) -> None:
        # Parse tier from map update text (keeping for compatibility)
        tier_str = "1"
        if "Tier" in text:
            try:
                tier_str = text.split("Tier")[1].split("/")[0].strip()
            except Exception:
                pass
        # Tier label removed with TreeMap, but keeping parsing for compatibility

    # ── Inventory management ─────────────────────────────────────────────────

    def _update_inventory_display(self) -> None:
        """Update the inventory listbox with current player inventory."""
        self.inventory_listbox.delete(0, tk.END)
        
        if not hasattr(self, '_player') or not self._player:
            self.lbl_inventory_count.config(text="0 items")
            return
            
        inventory = self._player.get("inventory", [])
        self.lbl_inventory_count.config(text=f"{len(inventory)} items")
        
        for i, item in enumerate(inventory, 1):
            # Handle both dict and object formats
            if isinstance(item, dict):
                item_name = item.get('name', 'Unknown')
                item_desc = item.get('description', 'No description')
            else:
                item_name = getattr(item, 'name', 'Unknown')
                item_desc = getattr(item, 'description', 'No description')
            
            display_text = f"{i}. {item_name} - {item_desc}"
            self.inventory_listbox.insert(tk.END, display_text)

    def _use_inventory_item(self, event=None) -> None:
        """Handle double-click on inventory item to use it."""
        selection = self.inventory_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        if not hasattr(self, '_player') or not self._player:
            return
            
        inventory = self._player.get("inventory", [])
        if 0 <= index < len(inventory):
            item = inventory[index]
            # Handle both dict and object formats
            if isinstance(item, dict):
                item_name = item.get('name', 'Unknown')
                item_desc = item.get('description', 'No description')
            else:
                item_name = getattr(item, 'name', 'Unknown')
                item_desc = getattr(item, 'description', 'No description')
            
            # For now, just show item info. Full usage would need integration with combat system
            self._q.put(("log", f"Selected: {item_name} - {item_desc}", None))

    # ── Title screen overlay ─────────────────────────────────────────────────

    def show_title_screen(self, on_choice: Callable[[str], Any]) -> None:
        overlay = tk.Frame(self.root, bg=C["bg"])
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Animated title canvas
        title_cv = tk.Canvas(overlay, bg=C["bg"], height=120,
                             highlightthickness=0)
        title_cv.pack(fill="x", padx=60, pady=(50, 0))

        frame_ref = [0]

        def _animate_title():
            title_cv.delete("all")
            t = frame_ref[0] * 0.04
            frame_ref[0] += 1
            W = title_cv.winfo_width() or 800

            title_cv.create_text(
                W // 2, 55,
                text="GAME-ON LEARNING",
                fill=C["highlight"],
                font=("Courier New", 28, "bold"),
            )
            title_cv.create_text(
                W // 2, 90,
                text="▸ A KNOWLEDGE COMBAT ROGUELITE ◂",
                fill=C["text_dim"],
                font=("Courier New", 10),
            )
            # Scanline decoration (placeholder for future use)
            title_cv.after(50, _animate_title)

        _animate_title()

        tk.Frame(overlay, height=1, bg=C["border"]).pack(fill="x", padx=60, pady=16)

        # Last run info
        if os.path.exists(self._last_run_path):
            try:
                last = open(self._last_run_path).read().strip()
                tk.Label(overlay, text="LAST RUN", bg=C["bg"],
                         fg=C["text_dim"], font=("Courier New", 8, "bold")).pack()
                tk.Label(overlay, text=last, bg=C["bg"], fg=C["text_dim"],
                         font=("Courier New", 9), justify="center").pack()
                tk.Frame(overlay, height=1, bg=C["border"]).pack(
                    fill="x", padx=80, pady=10)
            except Exception:
                pass

        btn_frame = tk.Frame(overlay, bg=C["bg"])
        btn_frame.pack()

        menu_items = [
            ("1. Start Game",          "start",         C["highlight"]),
            ("2. Practice Mode",       "practice",      C["btn_bg"]),
            ("3. Change Notes Files",  "reconfigure",   C["btn_bg"]),
            ("4. View Achievements",   "achievements",  C["btn_bg"]),
            ("5. Exit",                "exit",          C["hp_low"]),
        ]

        def pick(action: str) -> None:
            overlay.destroy()
            on_choice(action)

        for lbl, action, bg in menu_items:
            b = _make_choice_btn(btn_frame, lbl, lambda a=action: pick(a))
            b.config(bg=bg, width=28)
            b.pack(pady=5, ipady=6)

        for key, action in {"1": "start", "2": "practice", "3": "reconfigure",
                            "4": "achievements", "5": "exit"}.items():
            overlay.bind(key, lambda _, a=action: pick(a))

        overlay.focus_set()

    # ── Game over overlay ─────────────────────────────────────────────────────

    def show_game_over_screen(self, won: bool, on_choice: Callable[[bool], Any]) -> None:
        overlay = tk.Frame(self.root, bg=C["bg"])
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        art   = "✦  V I C T O R Y  ✦" if won else "✦  D E F E A T E D  ✦"
        sub   = "The Gauntlet has been conquered." if won else "Knowledge was not enough this time."
        color = C["correct"] if won else C["hp_low"]

        tk.Label(overlay, text=art, font=("Courier New", 26, "bold"),
                 bg=C["bg"], fg=color).pack(pady=(100, 8))
        tk.Label(overlay, text=sub, font=("Courier New", 11),
                 bg=C["bg"], fg=C["text_dim"]).pack()
        tk.Frame(overlay, height=1, bg=C["border"]).pack(
            fill="x", padx=120, pady=20)

        btn_frame = tk.Frame(overlay, bg=C["bg"])
        btn_frame.pack(pady=10)

        def pick(restart: bool) -> None:
            overlay.destroy()
            on_choice(restart)

        b1 = _make_choice_btn(btn_frame, "1. Play Again", lambda: pick(True), width=22)
        b1.config(bg=C["correct"])
        b1.pack(pady=6, ipady=8)

        b2 = _make_choice_btn(btn_frame, "2. Main Menu", lambda: pick(False), width=22)
        b2.pack(pady=6, ipady=8)

        overlay.bind("1", lambda _: pick(True))
        overlay.bind("2", lambda _: pick(False))
        overlay.focus_set()

    # ── Event bus listener ────────────────────────────────────────────────────

    def on_event(self, event: dict[str, Any]) -> None:
        t = event.get("type")

        if t == "text":
            content = str(event.get("content", ""))
            self._q.put(("log", content, self._classify(content)))

        elif t == "stat_update":
            self._q.put(("player", dict(event)))

        elif t == "combat":
            # Animation trigger for combat events
            name = event.get("name", "")
            self._q.put(("combat_anim", name, dict(event)))

        elif t == "game":
            name = event.get("name", "")
            if name == "clear_log":
                self._q.put(("clear",))
            elif name == "map_update":
                self._q.put(("map", 
                            str(event.get("text", "")),
                            list(event.get("history", [])),
                            list(event.get("pending", []))))
            elif name == "enemy_update":
                self._q.put(("enemy", dict(event)))
            elif name == "enemy_clear":
                self._q.put(("enemy_clear",))
            elif name == "show_choices":
                opts   = list(event.get("options", []))
                prompt = str(event.get("prompt", ""))
                auto_selected = event.get("auto_selected", None)
                self._q.put(("choices", opts, prompt, auto_selected))
            elif name == "hide_choices":
                self._q.put(("choices", [], ""))
            elif name == "waiting_for_input":
                prompt = str(event.get("prompt", ""))
                if prompt:
                    self._q.put(("log", prompt, None))
                # Always enable input, even with empty prompt (just press enter to continue)
                self._q.put(("input_enabled",))
            elif name == "game_over":
                self._q.put(("game_over", bool(event.get("won", False))))
            elif name == "title_screen":
                self._q.put(("title_screen",))
            # Legacy: action_buttons and boss_actions are now ignored
            # (all choices go through the center choice panel)

    # ── Poll queue ────────────────────────────────────────────────────────────

    def _poll(self) -> None:
        try:
            while True:
                msg = self._q.get_nowait()
                cmd = msg[0]
                if cmd == "log":
                    self._do_log(msg[1], msg[2])
                elif cmd == "clear":
                    self._do_clear()
                elif cmd == "player":
                    self._do_update_player(msg[1])
                elif cmd == "map":
                    self._do_map_update(msg[1], 
                                       msg[2] if len(msg) > 2 else [],
                                       msg[3] if len(msg) > 3 else [])
                elif cmd == "enemy":
                    self._do_update_enemy(msg[1])
                elif cmd == "enemy_clear":
                    self._do_clear_enemy()
                elif cmd == "choices":
                    self._do_show_choices(msg[1],
                                         msg[2] if len(msg) > 2 else "",
                                         msg[3] if len(msg) > 3 else None)
                elif cmd == "input_enabled":
                    self._set_input_enabled(True)
                elif cmd == "game_over":
                    self._handle_game_over(msg[1])
                elif cmd == "title_screen":
                    self._handle_title_screen()
        except queue.Empty:
            pass
        self.root.after(30, self._poll)

    def _handle_title_screen(self) -> None:
        import ui as _ui
        self.show_title_screen(lambda action: _ui.input_handler.push_answer(action))

    def _handle_game_over(self, won: bool) -> None:
        import ui as _ui
        self.show_game_over_screen(
            won,
            lambda restart: _ui.input_handler.push_answer("1" if restart else "2"),
        )


# ── Launch helper ─────────────────────────────────────────────────────────────

def launch_gui(game_main_fn: Callable[[], Any], last_run_path: str = "last_run.txt") -> None:
    import ui as _ui
    from tkinter import messagebox

    root = tk.Tk()
    root.deiconify()  # Ensure the window is visible
    gui  = GameGUI(root, last_run_path=last_run_path)

    def _on_closing():
        """Handle window close - ask for confirmation if game is running."""
        if messagebox.askyesno("Quit Game", "Are you sure? Your current run will be lost!"):
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_closing)

    _ui.bus.unsubscribe(_ui._terminal_listener)
    _ui.bus.subscribe(gui.on_event)

    _ui.input_handler.gui_mode = True

    def _run() -> None:
        try:
            game_main_fn()
        except SystemExit:
            pass
        except Exception as exc:
            import traceback
            _ui.bus.say(f"\n[Fatal Error] {exc}")
            traceback.print_exc()

    threading.Thread(target=_run, daemon=True).start()
    root.update()  # Force window rendering before entering main loop
    root.mainloop()