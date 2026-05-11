# ui.py
import os
import time
import random


def clear_screen():
    """Clear the screen or narrative log.
    
    In GUI mode: emits 'clear_log' event to GUI to clear narrative text area.
    In terminal mode: executes 'cls' (Windows) or 'clear' (Unix/Linux).
    """
    if _gui_active():
        bus.game_event("clear_log")
    else:
        os.system("cls" if os.name == "nt" else "clear")


def typewriter(text, delay=0.005):
    """Display text character-by-character for dramatic effect.
    
    In GUI mode: emits text through event bus (no character delay).
    In terminal mode: prints each character with delay (default 5ms) for typewriter effect.
    Includes Unicode fallback for systems that don't support console Unicode.
    
    All game modules call this directly. No patching needed for GUI/terminal switching.
    
    Args:
        text: String or object to display (converted to str)
        delay (float): Milliseconds between characters (terminal only). Defaults to 0.005.
    
    Unicode Fallbacks (terminal mode):
        '→' -> '->'
        '★' -> '*'
        '█' -> '#'
        etc. (see replacements dict)
    """
    if _gui_active():
        bus.say(str(text))
    else:
        try:
            for char in str(text):
                print(char, end="", flush=True)
                time.sleep(delay)
        except UnicodeEncodeError:
            # Fallback for systems that don't support Unicode in console
            for char in str(text):
                try:
                    print(char, end="", flush=True)
                except UnicodeEncodeError:
                    # Replace problematic characters with ASCII alternatives
                    replacements = {'→': '->', '←': '<-', '█': '#', '▓': '%', '░': '=', '♥': '*', '★': '*'}
                    safe_char = replacements.get(char, '?')
                    print(safe_char, end="", flush=True)
                time.sleep(delay)
        print()


def hp_bar(current, maximum, length=20):
    """Create an ASCII HP bar visualization.
    
    Displays a horizontal bar filled with '#' for health and '-' for damage.
    Also shows current/max HP and health status (healthy/wounded/critical).
    
    Args:
        current (float): Current HP value
        maximum (float): Maximum HP value
        length (int): Width of the bar in characters. Defaults to 20.
        
    Returns:
        str: Formatted bar like "[#####-----------] 25/40 (wounded)"
        
    Status Colors (terminal only):
        > 50%: "healthy" (green in GUI)
        25-50%: "wounded" (orange in GUI)
        < 25%: "critical" (red in GUI)
    """
    if maximum <= 0:
        return "[--------------------] 0/0"
    filled = max(0, min(length, int((current / maximum) * length)))
    bar = "#" * filled + "-" * (length - filled)
    ratio = current / maximum
    status = "healthy" if ratio > 0.5 else ("wounded" if ratio > 0.25 else "critical")
    return f"[{bar}] {current}/{maximum} ({status})"


# ── Event bus ────────────────────────────────────────────────────────────────

class EventBus:
    """Publish-subscribe event system for game -> GUI communication.
    
    Single EventBus instance (module-level 'bus') is shared across all modules.
    Game code emits events, GUI subscribes to listen. Threadsafe via thread-local
    event queues (not used directly here, but wrapped at GUI level).
    
    Event Types:
        - 'text': Narrative text to display
        - 'stat_update': Player/enemy stat changes
        - 'combat': Combat-specific events (damage, heal, miss, etc)
        - 'game': General game events (clear_log, map_update, title_screen, etc)
    
    Attributes:
        _listeners (list[callable]): Callbacks subscribed to all events
    """
    def __init__(self):
        self._listeners = []

    def subscribe(self, fn):
        """Register a callback to receive all events.
        
        Args:
            fn: Callable that accepts (event: dict) where event has keys:
                - 'type': Event type string
                - Additional keys depend on event type
                
        Example:
            def my_listener(event):
                if event['type'] == 'text':
                    print(event['content'])
            bus.subscribe(my_listener)
        """
        if fn not in self._listeners:
            self._listeners.append(fn)

    def unsubscribe(self, fn):
        """Remove a listener callback.
        
        Args:
            fn: The callback to stop listening
        """
        self._listeners = [l for l in self._listeners if l is not fn]

    def emit(self, event_type, **data):
        """Emit an event to all subscribed listeners.
        
        Catches and ignores exceptions in individual listener callbacks to prevent
        one broken listener from crashing the event system.
        
        Args:
            event_type (str): Type identifier for this event
            **data: Additional key-value pairs attached to the event
            
        Example:
            bus.emit('combat', action='hit', damage=25, attacker='player')
        """
        event = {"type": event_type, **data}
        for fn in list(self._listeners):
            try:
                fn(event)
            except Exception:
                pass

    def say(self, text):
        """Emit a text display event.
        
        Shorthand for emit('text', content=str(text)). Used to display narrative
        messages, combat logs, menu text, etc.
        
        Args:
            text: Text to display (converted to string)
        """
        self.emit("text", content=str(text))

    def stat_update(self, **data):
        """Emit a player/enemy stat change event.
        
        Used to update GUI stat displays (HP bar, gold, streak, etc) in real-time.
        GUI listens to these and updates animated bars/labels accordingly.
        
        Args:
            **data: Player or enemy stat keys and values
            
        Example:
            bus.stat_update(player_hp=50, player_max_hp=100, gold=250)
        """
        self.emit("stat_update", **data)

    def combat_event(self, name, **data):
        """Emit a combat-specific event (damage, heal, miss, dodge, etc).
        
        Used to display combat feedback and play animations. GUI listens for these
        to show floating text (damage numbers), color flashes, etc.
        
        Args:
            name (str): Combat action type ('damage', 'heal', 'miss', 'dodge', 'crit')
            **data: Additional context (damage amount, who attacked, etc)
            
        Example:
            bus.combat_event('damage', attacker='enemy', defender='player', amount=15, crit=False)
        """
        self.emit("combat", name=name, **data)

    def game_event(self, name, **data):
        """Emit a high-level game event (run state changes, screen transitions, etc).
        
        Used to show title screens, game-over screens, update maps, clear logs, etc.
        
        Args:
            name (str): Game event type ('title_screen', 'game_over', 'map_update', etc)
            **data: Event-specific parameters
            
        Example:
            bus.game_event('title_screen')  # Show title screen overlay
            bus.game_event('map_update', text="Tier 2/3 | Node 5...", history=[...])
        """
        self.emit("game", name=name, **data)


def _terminal_listener(event):
    """Default listener — prints text events to the terminal.
    
    Displays incoming text events character-by-character (0.5ms per char) when
    game is running in terminal mode. This is the fallback when no GUI is active.
    
    Ignored in GUI mode (GUI has its own listeners registered).
    
    Args:
        event (dict): Event dict with keys like 'type', 'content'
    """
    if event["type"] == "text":
        content = event.get("content", "")
        for char in str(content):
            print(char, end="", flush=True)
            time.sleep(0.005)
        print()


bus = EventBus()
bus.subscribe(_terminal_listener)


# ── GUI mode flag ─────────────────────────────────────────────────────────────

def _gui_active():
    """Returns True once the GUI has been initialised.
    
    Checks input_handler.gui_mode flag, which is set by the GUI thread when
    the GameGUI window is fully constructed.
    
    Returns:
        bool: True if GUI is active, False if in terminal mode
    """
    return input_handler.gui_mode


# ── Input handler ─────────────────────────────────────────────────────────────

class InputHandler:
    """Single point for ALL player input (both terminal and GUI modes).
    
    Terminal mode: Calls input() directly from the game thread.
    GUI mode: Blocks game thread and waits for GUI thread to call push_answer().
    
    Handles both free-form text input (ask) and multiple-choice selections (ask_choice).
    Auto-play mode can skip player input entirely for testing/demo purposes.
    
    Attributes:
        _pending: Current user response, set by push_answer()
        gui_mode (bool): True if GUI is active and running
        auto_play_mode (bool): True to auto-answer questions (for testing)
        in_combat_question (bool): True if currently answering a combat question
    """

    def __init__(self):
        self._pending = None
        self.gui_mode = False
        self.auto_play_mode = False
        self.in_combat_question = False

    def _wait_for_pending(self):
        while self._pending is None:
            time.sleep(0.02)
        result = self._pending
        self._pending = None
        return result

    def ask(self, prompt=""):
        """Request free-form text input from the player.
        
        Terminal mode: Displays prompt and returns input().
        GUI mode: Hides choice buttons, displays prompt in GUI, blocks until push_answer() called.
        
        Args:
            prompt (str): Optional prompt text to display
            
        Returns:
            str: The user's input, stripped of leading/trailing whitespace
            
        Example:
            name = input_handler.ask("Enter your name: ")
        """
        if not self.gui_mode:
            return input(prompt).strip()
        bus.game_event("hide_choices")
        if prompt:
            bus.game_event("waiting_for_input", prompt=str(prompt))
        return self._wait_for_pending()

    def ask_choice(self, choices, prompt=""):
        """Request a multiple-choice selection from the player.
        
        Terminal mode: Displays prompt, returns user's input.
        GUI mode: Displays choices as buttons, blocks until user clicks one.
        
        Normalizes choice input formats:
        - dict: {"label": "...", "value": "...", "log": "..."}
        - tuple/list: (label, value, log)
        - string: Used as both label and value
        
        Args:
            choices (list): List of choices in any supported format
            prompt (str): Optional prompt before choices
            
        Returns:
            str: The 'value' of the selected choice
            
        Example:
            choice = input_handler.ask_choice([
                {"label": "Attack", "value": "attack"},
                {"label": "Defend", "value": "defend"},
            ], "Choose action: ")
        """
        if not self.gui_mode:
            return input(prompt).strip()

        normalized = []
        for choice in choices:
            if isinstance(choice, dict):
                label = str(choice.get("label", choice.get("value", "")))
                value = str(choice.get("value", label))
                log = str(choice.get("log", label))
            elif isinstance(choice, (tuple, list)) and len(choice) >= 2:
                label = str(choice[0])
                value = str(choice[1])
                log = label
            else:
                label = str(choice)
                value = label
                log = label
            normalized.append({"label": label, "value": value, "log": log})

        if not normalized:
            return self.ask(prompt)

        # Auto-play mode: randomly select (unless in combat question)
        if self.auto_play_mode and not self.in_combat_question:
            selected = random.choice(normalized)
            bus.game_event("show_choices", options=normalized, auto_selected=selected)
            time.sleep(0.3)  # Brief delay for visibility
            return selected["value"]

        bus.game_event("show_choices", options=normalized)
        return self._wait_for_pending()

    def push_answer(self, answer):
        self._pending = str(answer)

    def toggle_auto_play(self):
        """Toggle auto-play mode on/off and broadcast the state."""
        self.auto_play_mode = not self.auto_play_mode
        bus.game_event("auto_play_toggled", enabled=self.auto_play_mode)
        return self.auto_play_mode

    def set_in_combat_question(self, in_question: bool):
        """Set whether we're currently asking a question in combat."""
        self.in_combat_question = in_question


input_handler = InputHandler()


# ── Player stats broadcast ────────────────────────────────────────────────────

def emit_player_stats(player):
    """Broadcast full player state so the GUI can refresh every panel."""
    bus.stat_update(
        name=player.name,
        class_name=getattr(player, "class_name", ""),
        lvl=player.lvl,
        hp=player.hp,
        max_hp=player.max_hp,
        exp=player.exp,
        xp_to_next=player.xp_to_next,
        gold=player.gold,
        focus=player.focus,
        max_focus=player.max_focus,
        streak=player.streak,
        longest_streak=player.longest_streak,
        atk=player.atk,
        defense=player.defense,
        spd=player.spd,
        wisdom=player.wisdom,
        crit_chance=player.crit_chance,
        shield=getattr(player, "shield", 0),
        inventory=[getattr(i, "name", str(i)) for i in player.inventory],
        status_effects=[e.name for e in player.status_effects],
        run_modifier=getattr(player, "run_modifier", ""),
        class_passive=getattr(player, "class_passive", ""),
    )


# ── ASCII art ─────────────────────────────────────────────────────────────────

GAME_TITLE = r"""
  ____                        ___        _                           _
 / ___| __ _ _ __ ___   ___  / _ \ _ __ | |     ___  __ _ _ __ _ __ (_)_ __   __ _
| |  _ / _` | '_ ` _ \ / _ \| | | | '_ \| |    / _ \/ _` | '__| '_ \| | '_ \ / _` |
| |_| | (_| | | | | | |  __/| |_| | | | | |___|  __/ (_| | |  | | | | | | | | (_| |
 \____|\__,_|_| |_| |_|\___| \___/|_| |_|_____\___|\__,_|_|  |_| |_|_|_| |_|\__, |
                                                                               |___/
"""

GAME_OVER_ART = r"""
  ____                        ___
 / ___| __ _ _ __ ___   ___  / _ \__   _____ _ __
| |  _ / _` | '_ ` _ \ / _ \| | | \ \ / / _ \ '__|
| |_| | (_| | | | | | |  __/| |_| |\ V /  __/ |
 \____|\__,_|_| |_| |_|\___| \___/  \_/ \___|_|
"""


# ── Terminal screens ──────────────────────────────────────────────────────────

def title_screen(last_run_path="last_run.txt"):
    while True:
        clear_screen()
        print("=" * 60)
        print(GAME_TITLE)
        print("=" * 60)
        if os.path.exists(last_run_path):
            try:
                print("\n--- Last Run ---")
                print(open(last_run_path).read().strip())
                print()
            except Exception:
                pass
        typewriter("\n1. Start Game",       0.03)
        typewriter("2. Practice Mode",      0.03)
        typewriter("3. Change Notes Files", 0.03)
        typewriter("4. View Achievements",  0.03)
        typewriter("5. Exit\n",             0.03)
        print("=" * 60)
        m = {"1": "start", "2": "practice", "3": "reconfigure",
             "4": "achievements", "5": "exit"}
        c = input("Enter your choice: ").strip()
        if c in m:
            return m[c]
        typewriter("Invalid choice.", 0.03)
        time.sleep(1)


def game_over_screen():
    while True:
        clear_screen()
        print("=" * 60)
        print(GAME_OVER_ART)
        print("=" * 60)
        typewriter("\n1. Restart", 0.03)
        typewriter("2. Exit\n",   0.03)
        print("=" * 60)
        c = input("Enter your choice: ").strip()
        if c == "1": return True
        if c == "2": return False
        typewriter("Invalid choice.", 0.03)
        time.sleep(1)
