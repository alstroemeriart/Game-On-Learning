#include <algorithm>  // Provides helpers like find, shuffle, all_of, remove, min, and max.
#include <chrono>     // Provides time durations used by sleep_for on non-Windows systems.
#include <ctime>      // Provides C-style time utilities; kept available for time-based features.
#include <fstream>    // Provides ifstream/ofstream for loading questions and saving games.
#include <functional> // Provides std::function for optional menu label callbacks.
#include <iomanip>    // Provides output formatting tools; available for aligned console output.
#include <iostream>   // Provides cin/cout for all console input and output.
#include <map>        // Provides key-value containers for items, skills, effects, and saves.
#include <numeric>    // Provides numeric algorithms; kept available for score/stat calculations.
#include <random>     // Provides mt19937 and random distributions for game randomness.
#include <set>        // Provides unique collections, used for remembered missed questions.
#include <sstream>    // Provides string streams for parsing save fields and player input.
#include <string>     // Provides std::string for text, names, answers, and commands.
#include <thread>     // Provides sleep_for so animations can pause between characters.
#include <vector>     // Provides dynamic lists for inventory, questions, nodes, and enemies.
#include <cctype>     // Provides character checks/conversions like isdigit and tolower.

/*
    Game-On Learning - C++ console version

    This single file contains the whole educational RPG:
    - global data tables define question files, classes, skills, items, and enemies;
    - LearningEngine loads questions from text files and chooses questions during play;
    - combat connects correct answers to attacks, mastery, focus, and rewards;
    - the node loop lets the player choose battles, shops, trials, rests, and the boss;
    - save/load stores the important run data in a small key=value text file.

    Most comments below explain the purpose of each section and the non-obvious
    decisions inside the logic, especially where game mechanics affect each other.
*/

#ifdef _WIN32
#include <windows.h>  // Provides Windows-only console APIs such as Sleep and SetConsoleOutputCP.
#define CLEAR_CMD "cls" // Windows terminal command for clearing the console screen.
#else
#define CLEAR_CMD "clear" // Unix-like terminal command for clearing the console screen.
#endif

// ─────────────────────── RNG ────────────────────────────────────────────────
std::mt19937& rng() {
    // One shared random engine keeps random behavior consistent across the game.
    static std::mt19937 gen(std::random_device{}());
    return gen;
}
int randInt(int lo, int hi) {
    // Inclusive integer roll, used for damage variance, rewards, and menu generation.
    return std::uniform_int_distribution<int>(lo, hi)(rng());
}
double randReal() {
    // Probability roll in the range [0.0, 1.0), used for crits and random events.
    return std::uniform_real_distribution<double>(0.0, 1.0)(rng());
}
template <typename T>
T& randChoice(std::vector<T>& v) {
    // Returns a mutable random element from a non-empty vector.
    return v[randInt(0, (int)v.size() - 1)];
}
template <typename T>
const T& randChoice(const std::vector<T>& v) {
    // Const overload lets read-only vectors use the same random choice helper.
    return v[randInt(0, (int)v.size() - 1)];
}

// ─────────────────────── GLOBALS ────────────────────────────────────────────
double TEXT_SPEED   = 0.015; // Delay per printed character; smaller means faster text.
bool   ANIMATIONS   = true;  // Master switch for loading dots, blinking text, and animated bars.

// Save file is written beside the executable/current working directory.
const std::string SAVE_FILE = "compact_save.json"; // File where saveGame writes run progress.

// Each question type maps to the notes file that stores its questions.
const std::map<std::string, std::string> QUESTION_FILES = {
    {"TF", "notes/TorF.txt"},       // True/false questions.
    {"MC", "notes/MCQ.txt"},        // Multiple-choice questions stored as simple JSON lines.
    {"AR", "notes/Math.txt"},       // Arithmetic questions using prompt=answer lines.
    {"ID", "notes/Identify.txt"},   // Identification questions using prompt=answer lines.
    {"FB", "notes/FillBlanks.txt"}, // Fill-in-the-blank questions using prompt=answer lines.
    {"OD", "notes/OD.txt"},         // Ordering questions stored as simple JSON lines.
};
const std::map<std::string, int> QUESTION_DIFFICULTY = {
    {"TF", 1}, {"MC", 2}, {"AR", 2}, {"ID", 3}, {"FB", 2}, {"OD", 3} // Higher number means harder.
};
// Small icons keep the generated path readable in a plain console.
const std::map<std::string, std::string> NODE_ICONS = {
    {"battle", "[B]"}, {"elite", "[E]"}, {"shop", "[S]"},
    {"trial", "[T]"},  {"rest",  "[R]"}, {"boss", "[!]"}
};
// Mastery skills unlock when a player answers enough of a question type correctly.
const std::map<std::string, std::pair<std::string, std::string>> SKILLS = {
    {"TF", {"Truth Guard",    "Start battles with +5 shield."}},
    {"MC", {"Eliminate One", "Removes one wrong multiple-choice option."}},
    {"AR", {"Precision",     "Arithmetic mastery adds extra attack damage."}},
    {"ID", {"Recall",        "Identification mastery improves healing."}},
    {"FB", {"Composure",     "First wrong answer in battle does not break streak."}},
    {"OD", {"Tactical Read", "Ordering mastery can dodge the next enemy attack."}},
};
// Achievement names are also used as stable keys in RunState::achievements.
const std::map<std::string, std::string> ACHIEVEMENTS = {
    {"First Victory",   "Win your first battle."},
    {"Node Walker",     "Clear 5 nodes."},
    {"Elite Breaker",   "Defeat an elite."},
    {"Scholar Streak",  "Reach a streak of 10."},
    {"Master Student",  "Reach 10 mastery in any question type."},
    {"Boss Clear",      "Defeat the final boss."},
};

struct ClassBuild {
    // Template stats copied into a Player when a new character is created.
    std::string name, passive; // Display name and passive keyword checked by combat logic.
    int hp, atk, def, spd, wisdom; // Starting HP, attack, defense, speed, and learning power.
    double crit; // Starting critical-hit chance as a decimal, such as 0.12 for 12%.
    std::string desc; // Short class description shown in the class selection menu.
};
const std::vector<ClassBuild> CLASS_BUILDS = {
    {"Berserker", "bloodlust",  70, 14, 5, 4, 5,  0.12, "gains ATK after correct answers"},
    {"Duelist",   "momentum",   55, 11, 4, 9, 5,  0.25, "correct answers boost next crit chance"},
    {"Arcanist",  "insight",    50,  9, 4, 5, 25, 0.10, "gains extra focus from correct answers"},
    {"Sentinel",  "fortress",   90,  9, 9, 2, 5,  0.08, "wrong answers grant shield"},
};

struct RunModifier { std::string label, key, desc; }; // Menu label, mechanic key, and explanation.
const std::vector<RunModifier> RUN_MODIFIERS = {
    {"Standard Run",       "",         "no modifier"},
    {"Scholar's Burden",   "scholar",  "correct attacks deal double damage"},
    {"Cursed Knowledge",   "cursed",   "wrong answers also cost 10 HP"},
    {"Iron Will",          "ironwill", "cannot escape, but combat rewards are higher"},
};

const std::string TITLE_ART = R"(
  ____                        ___        _                           _
 / ___| __ _ _ __ ___   ___  / _ \ _ __ | |     ___  __ _ _ __ _ __ (_)_ __   __ _
| |  _ / _` | '_ ` _ \ / _ \| | | | '_ \| |    / _ \/ _` | '__| '_ \| | '_ \ / _` |
| |_| | (_| | | | | | |  __/| |_| | | | | |___|  __/ (_| | |  | | | | | | | | (_| |
 \____|\__,_|_| |_| |_|\___| \___/|_| |_|_____\___|\__,_|_|  |_| |_|_|_| |_|\__,  |
                                                                             |___/
)";

// ─────────────────────── UI HELPERS ─────────────────────────────────────────
void sleepMs(int ms) {
#ifdef _WIN32
    // Windows uses Sleep from windows.h and expects milliseconds.
    Sleep(ms);
#else
    // Other platforms use the standard C++ thread sleep helper.
    std::this_thread::sleep_for(std::chrono::milliseconds(ms));
#endif
}
void typeText(const std::string& text, double speed = -1, bool newline = true) {
    // Negative speed means "use the global setting" instead of overriding it.
    double s = (speed < 0) ? TEXT_SPEED : speed;
    for (char c : text) {
        std::cout << c << std::flush;
        if (s > 0) sleepMs((int)(s * 1000));
    }
    if (newline) std::cout << '\n';
}
void loading(const std::string& msg, int steps = 3) {
    std::cout << msg << std::flush;
    // Instant mode also disables waiting so menus stay quick.
    if (!ANIMATIONS || TEXT_SPEED == 0) { std::cout << '\n'; return; }
    for (int i = 0; i < steps; ++i) { sleepMs(250); std::cout << '.' << std::flush; }
    std::cout << '\n';
}
void divider(const std::string& title = "") {
    std::string line(58, '=');
    if (title.empty()) { std::cout << line << '\n'; return; }
    std::cout << '\n' << line << '\n';
    typeText("  " + title, 0.005);
    std::cout << line << '\n';
}
void flashMessage(const std::string& msg, int repeats = 2) {
    // Rewrites the same console line to create a simple blinking effect.
    if (!ANIMATIONS || TEXT_SPEED == 0) { typeText(msg); return; }
    for (int i = 0; i < repeats; ++i) {
        std::cout << '\r' << msg << std::flush; sleepMs(180);
        std::cout << '\r' << std::string(msg.size(), ' ') << std::flush; sleepMs(100);
    }
    std::cout << '\r' << msg << '\n';
}
void clearScreen() { system(CLEAR_CMD); } // Runs the platform-specific clear command.
void pause() { std::cout << "\nPress Enter to continue..."; std::cin.ignore(10000, '\n'); } // Waits for Enter before returning.

std::string bar(int cur, int max, int size = 20) {
    // Clamp current HP at zero so the bar never gets a negative filled count.
    int filled = (max > 0) ? (int)(size * std::max(0, cur) / std::max(1, max)) : 0;
    std::string b = "[";
    b += std::string(filled, '#');
    b += std::string(size - filled, '-');
    b += "] " + std::to_string(cur) + "/" + std::to_string(max);
    return b;
}
void animatedBar(const std::string& label, int cur, int max, int size = 20) {
    // Falls back to a normal bar when animations are turned off.
    if (!ANIMATIONS || TEXT_SPEED == 0) {
        std::cout << label << ": " << bar(cur, max, size) << '\n';
        return;
    }
    int filled = (max > 0) ? (int)(size * std::max(0, cur) / std::max(1, max)) : 0;
    std::cout << label << ": [" << std::flush;
    for (int i = 0; i < size; ++i) {
        std::cout << (i < filled ? '#' : '-') << std::flush;
        sleepMs(8);
    }
    std::cout << "] " << cur << "/" << max << '\n';
}

// Removes leading and trailing whitespace from file lines and player input.
std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n"); // First character that is not whitespace.
    if (a == std::string::npos) return "";      // All-whitespace strings trim to empty.
    size_t b = s.find_last_not_of(" \t\r\n");  // Last character that is not whitespace.
    return s.substr(a, b - a + 1);              // Return only the non-whitespace middle.
}
std::string toLower(std::string s) {
    // Normalizes answers and commands so capitalization does not matter.
    for (char& c : s) c = (char)tolower(c);
    return s;
}

// ─────────────────────── INPUT HELPERS ──────────────────────────────────────
std::string askRaw(const std::string& prompt) {
    // Reads the entire line so answers can contain spaces.
    std::cout << prompt << std::flush;
    std::string line;
    std::getline(std::cin, line);
    return trim(line);
}
std::string ask(const std::string& prompt,
                const std::vector<std::string>& valid = {}) {
    // Keeps asking until the user enters one of the allowed choices.
    while (true) {
        std::string v = askRaw(prompt);
        if (valid.empty()) return v;
        std::string lo = toLower(v);
        for (auto& opt : valid) if (toLower(opt) == lo) return lo;
        typeText("Invalid choice.");
    }
}
// Returns 0-based index, or -1 for cancel
int chooseIndex(const std::string& prompt, int count) {
    // Menus are displayed as 1-based numbers, but vectors are accessed by 0-based index.
    std::string raw = askRaw(prompt);
    std::string lo = toLower(raw);
    if (lo == "0" || lo == "b" || lo == "back" || lo == "cancel") return -1;
    if (!raw.empty() && std::all_of(raw.begin(), raw.end(), ::isdigit)) {
        int n = std::stoi(raw);
        if (n >= 1 && n <= count) return n - 1;
    }
    typeText("Invalid choice. Enter a number, or 0 to cancel.");
    return -1;
}
bool confirm(const std::string& prompt) {
    return ask(prompt + " (y/n)> ", {"y", "n"}) == "y"; // Converts a validated y/n prompt into true/false.
}
template <typename T>
void printNumbered(const std::vector<T>& items,
                   std::function<std::string(const T&)> label = nullptr) {
    // Optional label function lets complex objects decide how they appear in menus.
    for (int i = 0; i < (int)items.size(); ++i) {
        std::string lbl = label ? label(items[i]) : [&]() -> std::string {
            std::ostringstream oss; oss << items[i]; return oss.str();
        }();
        std::cout << (i + 1) << ". " << lbl << '\n';
    }
}

// ─────────────────────── DATA STRUCTURES ─────────────────────────────────────
struct Question {
    // Shared question model; only MC uses options and only OD uses items.
    std::string qtype, text, answer;      // Type code, question prompt, and correct answer.
    int difficulty = 1;                   // Difficulty tier used when selecting questions.
    std::vector<std::string> options;     // Multiple-choice answer options.
    std::vector<std::string> items;       // Ordering-question items before the player reorders them.
};

struct Effects {
    // Tracks timed status effects by name, where the value is turns remaining.
    std::map<std::string, int> data;
    int get(const std::string& k) const {
        // Missing effects count as zero turns remaining.
        auto it = data.find(k); return it != data.end() ? it->second : 0;
    }
    void set(const std::string& k, int v) { data[k] = v; } // Starts or refreshes an effect duration.
    int pop(const std::string& k) {
        // Consumes one-shot effects such as momentum.
        auto it = data.find(k); if (it == data.end()) return 0;
        int v = it->second; data.erase(it); return v; // Return old duration after removing the effect.
    }
    void tick() {
        // Decrease all active timers, then erase expired effects after iteration.
        std::vector<std::string> expired;
        for (auto& [k, v] : data) { --v; if (v <= 0) expired.push_back(k); } // Count down each timer.
        for (auto& k : expired) data.erase(k); // Remove expired keys after the map loop finishes.
    }
    std::string list() const {
        std::string s;
        for (auto& [k, v] : data) s += k + "(" + std::to_string(v) + ") "; // Format each active effect.
        return s.empty() ? "none" : s; // Show "none" instead of a blank status line.
    }
};

struct Fighter {
    // Base combatant model shared by player and enemies.
    std::string name;                  // Combatant display name.
    int max_hp, atk, defense, spd;     // Core stats: health cap, damage, damage reduction, dodge speed.
    double crit, crit_mult = 1.5;      // Critical chance and critical damage multiplier.
    int hp = 0, shield = 0;            // Current health and temporary damage absorption.
    std::string behavior = "neutral";  // Enemy AI style; players usually keep neutral behavior.
    Effects effects;                   // Timed buffs/debuffs currently affecting this fighter.

    Fighter() = default;
    Fighter(std::string n, int mhp, int a, int d, int sp, double cr, std::string beh = "neutral")
        : name(std::move(n)), max_hp(mhp), atk(a), defense(d), spd(sp), crit(cr), behavior(std::move(beh)) {
        hp = max_hp; // New fighters start at full health.
    }
    bool alive() const { return hp > 0; } // True while this fighter can still act.
    void takeDamage(int amount) {
        // Shield absorbs damage first, then remaining damage lowers HP.
        if (shield > 0) {
            int blocked = std::min(shield, amount); // Shield can block only up to its current value.
            shield -= blocked; amount -= blocked;   // Remove blocked damage from shield and incoming hit.
            if (blocked) typeText(name + "'s shield blocks " + std::to_string(blocked) + " damage.");
        }
        hp = std::max(0, hp - amount); // Clamp HP at zero so it never becomes negative.
    }
    void heal(int amount) { hp = std::min(max_hp, hp + amount); } // Heal without exceeding max HP.
};

struct Player : Fighter {
    // Player adds RPG progression, learning progress, inventory, and class passives.
    std::string class_name = "Adventurer", passive, run_modifier; // Chosen class and run-rule keywords.
    int wisdom = 5, level = 1, exp = 0, next_exp = 100;           // Learning stat and leveling progress.
    int gold = 20, streak = 0, best_streak = 0, focus = 0;        // Economy, answer streak, and focus meter.
    bool hint_ready = false, dodge_next = false, streak_guard = false; // One-use tactical flags.
    int bloodlust_stacks = 0;                                     // Caps Berserker passive attack growth.
    int correct_answers = 0, total_answers = 0;                   // Accuracy counters for run summary.
    std::vector<std::string> skills;                              // Unlocked mastery skill type codes.
    std::map<std::string, int> mastery = {
        {"TF",0},{"MC",0},{"AR",0},{"ID",0},{"FB",0},{"OD",0}   // Correct-answer counts per question type.
    };
    std::vector<std::string> inventory = {"Potion", "Attack Tonic", "Hint"}; // Starting items by item name.

    Player() : Fighter() {}
    Player(std::string n, int mhp, int a, int d, int sp, double cr, int wis = 5)
        : Fighter(std::move(n), mhp, a, d, sp, cr), wisdom(wis) {}
};

struct RunState {
    // RunState stores progress that belongs to the whole run, not just the player.
    int tier = 1, nodes = 0, battles_won = 0, elites_won = 0; // Path progress and combat milestones.
    bool boss_won = false; // Marks final victory so Boss Clear can unlock.
    std::map<std::string, std::map<std::string, int>> bestiary; // Enemy name -> seen/kills counters.
    std::vector<std::string> achievements; // Names of achievements already unlocked.
    std::vector<std::string> journal;      // Recent node history used by the map display and save file.
};

// ─────────────────────── ITEMS ───────────────────────────────────────────────
struct Item { std::string name, kind; int price, value; };
// Item kind decides whether the effect targets the player, the enemy, or rewards.
const std::map<std::string, Item> ITEMS = {
    {"Potion",         {"Potion",         "heal",    15, 25}},
    {"Mega Potion",    {"Mega Potion",     "heal",    35, 60}},
    {"Attack Tonic",   {"Attack Tonic",    "atk",     25,  5}},
    {"Shield Tonic",   {"Shield Tonic",    "def",     25,  5}},
    {"Poison Bomb",    {"Poison Bomb",     "poison",  30,  5}},
    {"Freeze Scroll",  {"Freeze Scroll",   "freeze",  35,  1}},
    {"Weakness Curse", {"Weakness Curse",  "weakness",30,  5}},
    {"Gold Charm",     {"Gold Charm",      "gold",    40,  0}},
    {"Hint",           {"Hint",            "hint",    20,  0}},
};
std::vector<std::string> itemNames() {
    // Converts the item map keys into a list that can be shuffled or randomly chosen.
    std::vector<std::string> v;
    for (auto& [k, _] : ITEMS) v.push_back(k);
    return v;
}

// ─────────────────────── ENEMIES ─────────────────────────────────────────────
struct EnemyTemplate {
    // Templates are copied into live Fighter objects when encounters begin.
    std::string name, behavior; // Enemy display name and AI behavior keyword.
    int hp, atk, def, spd;      // Base enemy stats copied into Fighter.
    double crit;                // Base critical-hit chance.
};
const std::map<int, std::vector<EnemyTemplate>> ENEMIES = {
    {1, {{"Bug",             "neutral",   35,  8, 1, 4, 0.05},
         {"Bandit",          "aggressive",45, 10, 3, 4, 0.10},
         {"Syntax Slime",    "defensive", 50,  9, 2, 2, 0.05}}},
    {2, {{"Logic Brute",     "aggressive",75, 14, 4, 3, 0.08},
         {"Array Shade",     "evasive",   60, 16, 2, 7, 0.15},
         {"Stone Compiler",  "defensive", 90, 12, 7, 1, 0.05}}},
    {3, {{"Runtime Reaper",  "evasive",  110, 21, 4, 7, 0.20},
         {"Ancient Algorithm","defensive",145, 18, 8, 3, 0.10},
         {"Final Debugger",  "aggressive",170, 22, 8, 5, 0.18}}},
};

Fighter enemyFor(int tier, bool elite = false, bool boss = false) {
    // Tier is capped so later encounters reuse the strongest enemy pool.
    auto it = ENEMIES.find(std::min(3, tier));
    const auto& pool = it != ENEMIES.end() ? it->second : ENEMIES.at(1); // Use tier pool, or tier 1 as fallback.
    const auto& tmpl = randChoice(pool); // Pick one template randomly from that tier.
    Fighter f(tmpl.name, tmpl.hp, tmpl.atk, tmpl.def, tmpl.spd, tmpl.crit, tmpl.behavior); // Convert template to live enemy.
    if (elite) {
        // Elite fights are upgraded normal enemies with stronger stats and a random style.
        f.name = "Elite " + f.name;
        f.max_hp = (int)(f.max_hp * 1.5); f.hp = f.max_hp; // Elite gets more max HP and refills to it.
        f.atk = (int)(f.atk * 1.3); f.defense += 2;        // Elite gets stronger offense and defense.
        std::vector<std::string> behs = {"aggressive","defensive","evasive"}; // Possible elite AI styles.
        f.behavior = randChoice(behs); // Elite behavior is randomized for variety.
    }
    if (boss) {
        // Boss fights are the final scaling pass over the chosen template.
        f.name = "Boss " + f.name;
        f.max_hp = (int)(f.max_hp * 2.2); f.hp = f.max_hp; // Boss has much more HP and starts full.
        f.atk = (int)(f.atk * 1.5); f.defense += 4;        // Boss hits harder and takes less damage.
        f.crit = std::min(0.5, f.crit + 0.08);             // Raise crit chance but cap it at 50%.
        f.behavior = "boss";                               // Boss behavior enables phase logic in combat.
    }
    return f;
}

// ─────────────────────── LEARNING ENGINE ────────────────────────────────────
// Minimal JSON parser for our specific line formats
// MC/OD lines are JSON objects. We parse them ourselves to avoid dependencies.

bool parseJsonString(const std::string& json, const std::string& key, std::string& out) {
    // Finds "key": "value" in the simple one-line JSON used by MC and OD files.
    std::string search = "\"" + key + "\""; // Build the literal key text, for example "answer".
    auto pos = json.find(search);            // Find where that key appears in the line.
    if (pos == std::string::npos) return false; // Key missing means this line is not usable.
    pos = json.find(':', pos); if (pos == std::string::npos) return false; // Move to the key/value separator.
    pos = json.find('"', pos + 1); if (pos == std::string::npos) return false; // Find opening quote of value.
    size_t end = json.find('"', pos + 1); // Find closing quote of value.
    if (end == std::string::npos) return false; // Missing close quote means malformed JSON-like text.
    out = json.substr(pos + 1, end - pos - 1); // Copy the value between the quotes.
    return true;
}
std::vector<std::string> parseJsonArray(const std::string& json, const std::string& key) {
    // Parses a flat string array such as "options": ["A", "B", "C"].
    std::vector<std::string> result;
    std::string search = "\"" + key + "\""; // Build the literal key text, for example "options".
    auto pos = json.find(search);            // Find the requested array key.
    if (pos == std::string::npos) return result; // Missing key returns an empty list.
    pos = json.find('[', pos); if (pos == std::string::npos) return result; // Find start of array.
    size_t end = json.find(']', pos); // Find end of array.
    if (end == std::string::npos) return result; // Malformed array returns empty.
    std::string arr = json.substr(pos + 1, end - pos - 1); // Extract contents between brackets.
    std::istringstream ss(arr);
    std::string token;
    while (std::getline(ss, token, ',')) {
        std::string t = trim(token); // Clean spaces around each comma-separated value.
        if (t.size() >= 2 && t.front() == '"' && t.back() == '"')
            t = t.substr(1, t.size() - 2); // Remove surrounding quotes from string entries.
        if (!t.empty()) result.push_back(t); // Keep only non-empty parsed values.
    }
    return result;
}

struct LearningEngine {
    // Owns all loaded questions and remembers missed questions for review/weighting.
    std::vector<Question> questions;
    std::vector<Question> wrong;

    void loadAll() {
        // Load every configured question file using that type's default difficulty.
        for (auto& [qtype, relpath] : QUESTION_FILES) {
            int diff = QUESTION_DIFFICULTY.at(qtype);
            loadFile(relpath, qtype, diff);
        }
        std::cout << "Loaded " << questions.size() << " questions.\n";
    }

    void loadFile(const std::string& path, const std::string& qtype, int difficulty) {
        std::ifstream f(path);
        if (!f.is_open()) {
            // Missing files do not stop the game; they simply reduce the question pool.
            std::cout << "Missing question file: " << path << '\n';
            return;
        }
        std::string line;
        while (std::getline(f, line)) {
            line = trim(line);
            if (line.empty()) continue;
            Question q;
            // Every loaded question keeps its type so mastery can be awarded later.
            q.qtype = qtype;
            q.difficulty = difficulty;
            if (qtype == "TF" || qtype == "AR" || qtype == "ID" || qtype == "FB") {
                // Simple question files use "prompt = answer" lines.
                auto eq = line.find('=');
                if (eq == std::string::npos) continue;
                q.text   = trim(line.substr(0, eq));
                q.answer = trim(line.substr(eq + 1));
                questions.push_back(q);
            } else if (qtype == "MC") {
                // Multiple choice needs a prompt, an answer, and display options.
                if (!parseJsonString(line, "question", q.text)) continue;
                if (!parseJsonString(line, "answer",   q.answer)) continue;
                q.options = parseJsonArray(line, "options");
                if (q.options.empty()) continue;
                questions.push_back(q);
            } else if (qtype == "OD") {
                // Ordering questions store items plus the correct index order.
                if (!parseJsonString(line, "question", q.text)) continue;
                if (!parseJsonString(line, "answer",   q.answer)) continue;
                q.items = parseJsonArray(line, "items");
                if (q.items.empty()) continue;
                questions.push_back(q);
            }
        }
    }

    Question* pick(int difficulty = -1) {
        // Build a pool matching requested difficulty, or all questions if difficulty is -1.
        std::vector<Question*> pool;
        for (auto& q : questions)
            if (difficulty < 0 || q.difficulty == difficulty)
                pool.push_back(&q);
        if (pool.empty() && difficulty >= 0) {
            // If no exact difficulty exists, fall back to all questions so combat can continue.
            for (auto& q : questions) pool.push_back(&q);
        }
        if (pool.empty()) return nullptr;
        std::set<std::string> missed;
        for (auto& q : wrong) missed.insert(q.text);
        std::vector<int> weights;
        // Missed questions are weighted higher to encourage spaced review.
        for (auto* q : pool) weights.push_back(missed.count(q->text) ? 3 : 1);
        int total = 0; for (int w : weights) total += w;
        int r = randInt(0, total - 1);
        int cum = 0;
        for (int i = 0; i < (int)pool.size(); ++i) {
            cum += weights[i];
            if (r < cum) return pool[i];
        }
        return pool.back();
    }
};

// ─────────────────────── SKILLS / EFFECTS ────────────────────────────────────
void unlockSkills(Player& p) {
    // A mastery skill unlocks once per question type at 5 correct answers.
    for (auto& [qtype, mastery] : p.mastery) {
        if (mastery >= 5 && std::find(p.skills.begin(), p.skills.end(), qtype) == p.skills.end()) {
            p.skills.push_back(qtype);
            auto& [name, desc] = SKILLS.at(qtype);
            typeText("Skill unlocked: " + name + " - " + desc);
        }
    }
}

int effectiveAtk(const Fighter& f) {
    // Temporary effects modify the stored base attack without permanently changing it.
    int total = f.atk; // Start from the fighter's permanent attack stat.
    if (f.effects.get("attack_up") > 0) total += 5; // Attack tonic temporarily adds damage.
    if (f.effects.get("weakness")  > 0) total -= 5; // Weakness curse temporarily lowers damage.
    return std::max(1, total); // Attack must stay at least 1 so damage math remains usable.
}
int effectiveDef(const Fighter& f) {
    // Defense buffs are calculated here so all damage calls use the same rules.
    int total = f.defense; // Start from permanent defense.
    if (f.effects.get("defense_up") > 0) total += 5; // Shield tonic/defensive behavior adds defense.
    return std::max(0, total); // Defense cannot go below zero.
}

std::pair<int, bool> calcDamage(Fighter& attacker, const Fighter& defender,
                                int mastery_bonus = 0,
                                const Player* player_hint = nullptr) {
    // Base damage uses attack minus defense plus a small random swing.
    int base = effectiveAtk(attacker) - effectiveDef(defender) + randInt(-2, 3); // Core damage formula.
    base = std::max(1, base); // Every successful hit deals at least 1 damage.
    // Mastery and player learning stats can add extra damage for correct answers.
    base += mastery_bonus / 5; // Every 5 mastery points add 1 bonus damage.
    if (player_hint) {
        base += player_hint->streak / 4; // Strong answer streaks add damage.
        base = (int)(base * (1.0 + player_hint->wisdom * 0.01)); // Wisdom gives a percent damage boost.
    }
    double crit_bonus = (attacker.effects.pop("momentum") > 0) ? 0.20 : 0.0; // Duelist bonus if active.
    // pop("momentum") makes the Duelist bonus apply to only one attack.
    bool crit = randReal() < attacker.crit + crit_bonus; // Roll whether this hit is critical.
    if (crit) base = (int)(base * attacker.crit_mult); // Critical hits multiply final damage.
    return {base, crit};
}

void tickEffects(Fighter& f) {
    // Damage-over-time effects happen before their duration is reduced.
    if (f.effects.get("poison") > 0) {
        f.takeDamage(5); // Poison always deals 5 damage per tick.
        typeText(f.name + " takes 5 poison damage.");
    }
    f.effects.tick(); // Reduce remaining durations after applying tick effects.
}

// ─────────────────────── QUESTIONS ───────────────────────────────────────────
std::pair<bool, std::string> finishQuestion(bool correct, LearningEngine& engine,
                                            Player& p, const Question& q);

std::pair<bool, std::string> askQuestion(LearningEngine& engine, Player& p,
                                         int difficulty = -1) {
    Question* qp = engine.pick(difficulty);
    if (!qp) {
        typeText("No questions loaded. The action fails.");
        return {false, ""};
    }
    const Question& q = *qp;
    std::cout << "\n[" << q.qtype << " | difficulty " << q.difficulty << "]\n";
    typeText(q.text, 0.005);

    if (p.hint_ready) {
        // Hint is a one-use flag set by items or mastery skills.
        if (q.qtype == "MC" && !q.options.empty()) {
            std::vector<std::string> wrong;
            for (auto& o : q.options)
                if (toLower(o) != toLower(q.answer)) wrong.push_back(o);
            if (!wrong.empty())
                typeText("Hint: remove '" + randChoice(wrong) + "' from consideration.");
        } else if (!q.answer.empty()) {
            typeText("Hint: starts with '" + std::string(1, q.answer[0]) +
                     "' and has " + std::to_string(q.answer.size()) + " character(s).");
        }
        p.hint_ready = false;
    }

    std::string answer;
    if (q.qtype == "TF") {
        // True/false answers are restricted so spelling variants do not enter the check.
        answer = ask("(true/false)> ", {"true", "false"});
    } else if (q.qtype == "MC") {
        auto options = q.options;
        if (std::find(p.skills.begin(), p.skills.end(), "MC") != p.skills.end()) {
            // Eliminate One removes a wrong option before the player chooses.
            std::vector<std::string> wrng;
            for (auto& o : options) if (toLower(o) != toLower(q.answer)) wrng.push_back(o);
            if (!wrng.empty() && options.size() > 2) {
                auto& rem = randChoice(wrng);
                options.erase(std::remove(options.begin(), options.end(), rem), options.end());
                typeText("[Eliminate One] Removed: " + rem);
            }
        }
        for (int i = 0; i < (int)options.size(); ++i)
            std::cout << (i+1) << ". " << options[i] << '\n';
        int idx = chooseIndex("> ", (int)options.size());
        answer = (idx >= 0) ? options[idx] : "";
    } else if (q.qtype == "OD") {
        // Ordering questions show items shuffled, then compare chosen item order.
        auto shown = q.items;
        std::shuffle(shown.begin(), shown.end(), rng());
        for (int i = 0; i < (int)shown.size(); ++i)
            std::cout << (i+1) << ". " << shown[i] << '\n';
        std::string raw = askRaw("Order as numbers, example 2,1,3> ");
        std::vector<std::string> chosen, correct_items;
        std::istringstream ss(raw); std::string tok;
        while (std::getline(ss, tok, ',')) {
            tok = trim(tok);
            if (!tok.empty() && std::all_of(tok.begin(), tok.end(), ::isdigit)) {
                int idx2 = std::stoi(tok) - 1;
                if (idx2 >= 0 && idx2 < (int)shown.size()) chosen.push_back(shown[idx2]);
            }
        }
        // Build correct order from q.answer indices.
        std::istringstream sa(q.answer); std::string ta;
        while (std::getline(sa, ta, ',')) {
            ta = trim(ta);
            if (!ta.empty() && std::all_of(ta.begin(), ta.end(), ::isdigit)) {
                int idx3 = std::stoi(ta) - 1;
                if (idx3 >= 0 && idx3 < (int)q.items.size()) correct_items.push_back(q.items[idx3]);
            }
        }
        bool ok = (chosen == correct_items);
        return finishQuestion(ok, engine, p, q);
    } else {
        answer = askRaw("> ");
    }
    return finishQuestion(toLower(answer) == toLower(q.answer), engine, p, q);
}

std::pair<bool, std::string> finishQuestion(bool correct, LearningEngine& engine,
                                            Player& p, const Question& q) {
    // Centralizes all learning rewards/penalties so every question type updates stats equally.
    p.total_answers++;
    if (correct) {
        typeText("Correct.");
        p.correct_answers++;
        p.mastery[q.qtype]++;
        p.streak++;
        p.best_streak = std::max(p.best_streak, p.streak);
        int focus_gain = 10 + p.wisdom / 5;
        // Arcanist gets extra focus because its passive is built around frequent focus use.
        if (p.passive == "insight") focus_gain += 5;
        p.focus = std::min(100, p.focus + focus_gain);
        if (p.passive == "bloodlust" && p.bloodlust_stacks < 10) {
            // Bloodlust is capped so attack cannot grow forever in one run.
            p.atk++; p.bloodlust_stacks++;
            typeText("[Bloodlust] ATK rises by 1.");
        }
        if (p.passive == "momentum") p.effects.set("momentum", 1);
        if (q.qtype == "OD" &&
            std::find(p.skills.begin(), p.skills.end(), "OD") != p.skills.end() &&
            randReal() < 0.25) {
            // Ordering mastery occasionally converts a correct answer into a future dodge.
            p.dodge_next = true;
            typeText("[Tactical Read] Next attack may be dodged.");
        }
        unlockSkills(p);
    } else {
        typeText("Wrong. Correct answer: " + q.answer);
        engine.wrong.push_back(q);
        if (p.streak_guard) {
            // Composure protects the streak once, then consumes the guard.
            p.streak_guard = false;
            typeText("[Composure] Streak protected.");
        } else {
            p.streak = std::max(0, p.streak / 2);
        }
        p.focus = std::max(0, p.focus - 10);
        if (p.passive == "fortress") {
            p.shield += 8;
            typeText("[Fortress] Shield +8.");
        }
        if (p.run_modifier == "cursed") {
            // Cursed Knowledge turns wrong answers into direct HP pressure.
            p.takeDamage(10);
            typeText("[Cursed Knowledge] You lose 10 HP.");
        }
    }
    return {correct, q.qtype};
}

// ─────────────────────── MASTERY SKILL USE ───────────────────────────────────
void useMasterySkill(Player& p, Fighter& enemy) {
    // Active mastery skills give the player tactical options besides answering.
    if (p.skills.empty()) { typeText("No mastery skills unlocked yet."); return; }
    std::cout << "\nUnlocked Skills:\n0. Cancel\n";
    for (int i = 0; i < (int)p.skills.size(); ++i) {
        auto& [name, desc] = SKILLS.at(p.skills[i]);
        std::cout << (i+1) << ". " << name << " [" << p.skills[i] << "] - " << desc << '\n';
    }
    int idx = chooseIndex("> ", (int)p.skills.size());
    if (idx < 0) return;
    const std::string& qt = p.skills[idx];
    if (qt == "TF") { p.shield += 12; typeText("Truth Guard raises a shield."); }
    else if (qt == "MC") { p.hint_ready = true; typeText("Eliminate One prepares your next question."); }
    else if (qt == "AR") { int amt = 10 + p.mastery["AR"]; enemy.takeDamage(amt); typeText("Precision deals " + std::to_string(amt) + " direct damage."); }
    else if (qt == "ID") { int h = 12 + p.mastery["ID"]; p.heal(h); typeText("Recall restores " + std::to_string(h) + " HP."); }
    else if (qt == "FB") { p.streak_guard = true; typeText("Composure will protect your streak once."); }
    else if (qt == "OD") { p.dodge_next = true; typeText("Tactical Read prepares a dodge."); }
}

// ─────────────────────── ITEMS IN COMBAT ─────────────────────────────────────
bool applyPlayerItem(Player& p, const Item& item) {
    // Player-targeting items heal, buff, or prepare non-damaging advantages.
    if (item.kind == "heal") {
        int h = item.value + (std::find(p.skills.begin(), p.skills.end(), "ID") != p.skills.end() ? p.mastery.at("ID") : 0);
        p.heal(h); typeText("Healed " + std::to_string(h) + " HP."); return true;
    }
    if (item.kind == "atk")  { p.effects.set("attack_up", 3); typeText("ATK +5 for 3 turns."); return true; }
    if (item.kind == "def")  { p.effects.set("defense_up", 3); p.shield += 10; typeText("DEF +5 for 3 turns. Shield +10."); return true; }
    if (item.kind == "hint") { p.hint_ready = true; typeText("Your next question will show a hint."); return true; }
    if (item.kind == "gold") { p.effects.set("double_gold", 3); typeText("Gold rewards doubled for 3 turns."); return true; }
    return false;
}
bool applyEnemyItem(Fighter& enemy, const Item& item) {
    // Enemy-targeting items apply debuffs that combat effects will read later.
    if (item.kind == "poison")   { enemy.effects.set("poison", 4); typeText(enemy.name + " is poisoned for 4 turns."); return true; }
    if (item.kind == "freeze")   { enemy.effects.set("freeze", item.value); typeText(enemy.name + " is frozen."); return true; }
    if (item.kind == "weakness") { enemy.effects.set("weakness", 3); typeText(enemy.name + "'s ATK is reduced for 3 turns."); return true; }
    return false;
}
void useItem(Player& p, Fighter& enemy) {
    // Inventory stores item names, so this function looks up each name in ITEMS.
    if (p.inventory.empty()) { typeText("Inventory empty."); return; }
    std::cout << "0. Cancel\n";
    for (int i = 0; i < (int)p.inventory.size(); ++i)
        std::cout << (i+1) << ". " << p.inventory[i] << '\n';
    int idx = chooseIndex("Use which item? ", (int)p.inventory.size());
    if (idx < 0) return;
    std::string iname = p.inventory[idx];
    // Remove the item before applying it so combat items are single-use.
    p.inventory.erase(p.inventory.begin() + idx);
    auto it = ITEMS.find(iname);
    if (it == ITEMS.end()) { typeText("Unknown item."); return; }
    const Item& item = it->second;
    if (!applyPlayerItem(p, item) && !applyEnemyItem(enemy, item))
        enemy.takeDamage(item.value);
}

// ─────────────────────── COMBAT STATS DISPLAY ────────────────────────────────
void showStats(const Player& p, const Fighter& enemy) {
    // Prints both combatants each turn so the player can make an informed choice.
    std::cout << '\n';
    divider("Combat");
    animatedBar(p.name, p.hp, p.max_hp);
    std::cout << "Gold " << p.gold << " | Lv " << p.level
              << " | EXP " << p.exp << "/" << p.next_exp << '\n';
    std::cout << "Streak " << p.streak << " | Focus " << p.focus << "/100\n";
    std::cout << "Class " << p.class_name << " | Shield " << p.shield
              << " | Effects " << p.effects.list() << '\n';
    animatedBar(enemy.name, enemy.hp, enemy.max_hp);
    std::cout << "Behavior " << enemy.behavior << " | Shield " << enemy.shield
              << " | Effects " << enemy.effects.list() << '\n';
    std::cout << std::string(58, '=') << '\n';
}

// ─────────────────────── PLAYER TURN ─────────────────────────────────────────
std::string playerTurn(Player& p, Fighter& enemy, LearningEngine& engine, bool boss = false) {
    // Returns a combat command result such as "continue" or "escape".
    showStats(p, enemy);
    std::cout << "1. Answer/Attack\n";
    std::cout << "2. Use Item\n";
    std::cout << (p.focus >= 100 ? "3. Focus Skill\n" : "3. Focus Skill (not ready)\n");
    std::cout << (boss ? "4. Guard\n" : "4. Run\n");
    std::cout << "5. Mastery Skill\n";
    std::string choice = ask("> ", {"1","2","3","4","5"});

    if (choice == "1") {
        // Answering correctly is the normal attack action.
        auto [correct, qtype] = askQuestion(engine, p, boss ? 3 : -1); // Boss forces hardest questions.
        if (correct) {
            int mastery = p.mastery.count(qtype) ? p.mastery.at(qtype) : 0; // Read mastery for answered type.
            if (enemy.effects.get("evasive") > 0 && randReal() < 0.30) {
                // Evasive stance can cancel the player's successful attack.
                typeText(enemy.name + " evades your attack.");
                return "continue";
            }
            auto [amount, crit] = calcDamage(p, enemy, mastery, &p);
            // Scholar's Burden makes the run easier on correct answers but changes balance.
            if (p.run_modifier == "scholar") amount *= 2;
            enemy.takeDamage(amount); // Apply final calculated damage to enemy HP/shield.
            typeText(p.name + " hits for " + std::to_string(amount) + " damage." +
                     (crit ? " Critical!" : ""));
        }
        return "continue";
    }
    if (choice == "2") { useItem(p, enemy); return "continue"; }
    if (choice == "3") {
        // Focus is a meter-based burst that spends 100 focus at once.
        if (p.focus >= 100) {
            p.focus = 0; // Spend the full meter.
            int amt = p.atk * 2 + p.wisdom; // Focus damage scales with combat and learning stats.
            enemy.takeDamage(amt); p.heal(10); // Burst both damages enemy and slightly heals player.
            typeText("Focus burst deals " + std::to_string(amt) + " damage and restores 10 HP.");
        } else { typeText("Focus is not ready."); }
        return "continue";
    }
    if (choice == "5") { useMasterySkill(p, enemy); return "continue"; }
    // choice == "4"
    // Boss battles do not allow running, so choice 4 becomes Guard.
    if (boss) { p.defense += 3; typeText("You guard. DEF +3."); return "continue"; }
    if (p.run_modifier == "ironwill") { typeText("[Iron Will] You cannot run from battle."); return "continue"; }
    return (randReal() < 0.55) ? "escape" : "continue"; // Normal escape has a 55% success chance.
}

// ─────────────────────── ENEMY TURN ──────────────────────────────────────────
void enemyTurn(Fighter& enemy, Player& p) {
    // Enemy behavior can replace a normal attack with a defensive/evasive action.
    if (enemy.effects.get("freeze") > 0) { typeText(enemy.name + " is frozen and skips the turn."); return; } // Freeze skips enemy action.
    if (p.dodge_next) { p.dodge_next = false; typeText(p.name + " reads the attack and dodges."); return; } // One prepared dodge is consumed.
    if (enemy.behavior == "defensive" && randReal() < 0.35) {
        enemy.shield += 10; enemy.effects.set("defense_up", 2); // Defensive enemy gains shield and DEF.
        typeText(enemy.name + " braces behind a shield."); return;
    }
    if (enemy.behavior == "evasive" && randReal() < 0.30) {
        enemy.effects.set("evasive", 1); // Evasive stance can avoid the next player hit.
        typeText(enemy.name + " shifts into an evasive stance."); return;
    }
    double dodge_chance = std::min(0.35, p.spd * 0.02 + p.streak * 0.003);
    // Speed and learning streak both help the player avoid incoming attacks.
    if (randReal() < dodge_chance) { typeText(p.name + " dodges."); return; }

    int hits = (enemy.behavior == "aggressive") ? 2 : 1;
    // Aggressive enemies split their damage across two hits.
    for (int h = 0; h < hits; ++h) {
        if (!p.alive()) return;
        auto [amount, crit] = calcDamage(enemy, p); // Enemy uses the same damage formula as player.
        if (hits == 2) amount = std::max(1, amount / 2); // Split two-hit attacks into smaller hits.
        p.takeDamage(amount); // Apply enemy damage to player shield/HP.
        typeText(enemy.name + " hits for " + std::to_string(amount) + " damage." +
                 (crit ? " Critical!" : ""));
    }
}

// ─────────────────────── BESTIARY ────────────────────────────────────────────
void recordBestiary(RunState& state, const std::string& ename, bool killed = false) {
    // Bestiary entries are created automatically the first time an enemy is seen.
    auto& entry = state.bestiary[ename];
    if (!killed) entry["seen"]++;
    else         entry["kills"]++;
}

// ─────────────────────── EXP ─────────────────────────────────────────────────
void gainExp(Player& p, int amount) {
    // Multiple level-ups can happen if a large reward crosses more than one threshold.
    p.exp += amount;
    typeText("Gained " + std::to_string(amount) + " EXP.");
    while (p.exp >= p.next_exp) {
        p.exp -= p.next_exp;
        p.level++;
        p.next_exp = (int)(p.next_exp * 1.3);
        p.max_hp += 8; p.hp = p.max_hp;
        p.atk += 2; p.defense++;
        flashMessage("LEVEL UP! Now level " + std::to_string(p.level) + ".", 4);
    }
}

// ─────────────────────── COMBAT ──────────────────────────────────────────────
std::string combat(Player& p, LearningEngine& engine, RunState& state,
                   int tier, bool elite = false, bool boss = false) {
    /*
        Full encounter loop:
        1. Create and reveal the enemy.
        2. Apply start-of-battle mastery bonuses.
        3. Alternate player and enemy turns until someone falls or the player escapes.
        4. Pay rewards and record bestiary progress on victory.
    */
    Fighter enemy = enemyFor(tier, elite, boss);
    recordBestiary(state, enemy.name);
    clearScreen();
    loading("Entering encounter");
    divider("Encounter");
    flashMessage(enemy.name + " appears!", boss || elite ? 3 : 2);

    if (std::find(p.skills.begin(), p.skills.end(), "TF") != p.skills.end()) {
        // Truth Guard is passive at battle start, unlike the active mastery menu use.
        p.shield += 5; typeText("[Truth Guard] Battle shield +5.");
    }
    if (std::find(p.skills.begin(), p.skills.end(), "FB") != p.skills.end()) {
        p.streak_guard = true;
    }

    int phase = 1;
    while (p.alive() && enemy.alive()) {
        if (boss) {
            // Boss phases make the final fight escalate as HP drops.
            double ratio = (double)enemy.hp / enemy.max_hp;
            if (phase == 1 && ratio <= 0.66) {
                phase = 2; enemy.atk += 5;
                flashMessage(enemy.name + " enters Phase 2. ATK rises.", 3);
            } else if (phase == 2 && ratio <= 0.33) {
                phase = 3; enemy.atk += 5;
                enemy.crit = std::min(0.5, enemy.crit + 0.15);
                flashMessage(enemy.name + " enters Phase 3. Critical chance rises.", 3);
            }
            std::vector<std::string> lines = {
                "The boss winds up for a heavy blow...",
                "The boss leaves itself exposed for a moment...",
                "Dark energy gathers around the boss...",
            };
            typeText(randChoice(lines));
        }
        std::string result = playerTurn(p, enemy, engine, boss);
        if (result == "escape") { typeText("You escaped."); return "escaped"; }
        if (enemy.alive()) enemyTurn(enemy, p);
        // Effects tick after both sides have acted for the round.
        tickEffects(enemy);
        tickEffects(p);
    }

    if (p.alive()) {
        // Victory branch handles all post-combat rewards.
        typeText(enemy.name + " defeated.");
        recordBestiary(state, enemy.name, true);
        int reward_exp  = boss ? 150 : (elite ? 40 : 25);
        int reward_gold = boss ? 100 : (elite ? 35 : 15);
        if (p.run_modifier == "ironwill") {
            reward_exp  = (int)(reward_exp  * 1.5);
            reward_gold = (int)(reward_gold * 1.5);
        }
        gainExp(p, reward_exp + tier * 10);
        int gold = reward_gold + tier * 5;
        if (p.effects.get("double_gold") > 0) gold *= 2;
        p.gold += gold;
        typeText("Gained " + std::to_string(gold) + " gold.");
        if (randReal() < 0.35) {
            // Item drops are intentionally broad: any item in the table can drop.
            auto names = itemNames();
            std::string drop = randChoice(names);
            p.inventory.push_back(drop);
            typeText("Found item: " + drop);
        }
        return "win";
    }
    return "death";
}

// ─────────────────────── SHOP / TRIAL / REST ──────────────────────────────────
void shop(Player& p) {
    // Shop offers a random three-item stock each visit.
    divider("Shop");
    auto names = itemNames(); // Start from every item name in the item table.
    std::shuffle(names.begin(), names.end(), rng()); // Randomize shop stock order.
    std::vector<const Item*> stock;
    for (int i = 0; i < 3 && i < (int)names.size(); ++i)
        stock.push_back(&ITEMS.at(names[i])); // Store pointers to the selected shop items.

    while (true) {
        std::cout << "\nGold: " << p.gold << "\n0. Leave\n";
        for (int i = 0; i < (int)stock.size(); ++i)
            std::cout << (i+1) << ". " << stock[i]->name << " - " << stock[i]->price << "g\n";
        std::string choice = askRaw("> ");
        if (toLower(choice) == "0" || toLower(choice) == "leave") return;
        if (!choice.empty() && std::all_of(choice.begin(), choice.end(), ::isdigit)) {
            int n = std::stoi(choice);
            if (n >= 1 && n <= (int)stock.size()) {
                const Item* item = stock[n-1]; // Convert menu number to chosen stock item.
                if (p.gold >= item->price) {
                    p.gold -= item->price; // Pay item cost.
                    p.inventory.push_back(item->name); // Inventory stores item names, not Item objects.
                    typeText("Bought " + item->name + ".");
                } else { typeText("Not enough gold."); }
                continue;
            }
        }
        typeText("Invalid choice.");
    }
}

void trial(Player& p, LearningEngine& engine) {
    // A trial is a safe reward node: three questions, no enemy turns.
    divider("Knowledge Trial");
    typeText("Answer 3 questions. Correct answers give rewards.");
    int correct = 0; // Counts how many of the three trial questions were answered correctly.
    for (int i = 0; i < 3; ++i) {
        auto [ok, _] = askQuestion(engine, p);
        if (ok) correct++;
    }
    int ex = correct * 20, gld = correct * 10; // Rewards scale directly with correct answers.
    gainExp(p, ex); // Trial EXP still uses normal level-up logic.
    p.gold += gld;  // Add trial gold directly.
    typeText("Trial complete: +" + std::to_string(ex) + " EXP, +" + std::to_string(gld) + " gold.");
}

void rest(Player& p) {
    // Rest healing scales with max HP and gets better with ID mastery.
    int amount = std::max(10, p.max_hp / 3); // Heal at least 10, or one third of max HP.
    if (std::find(p.skills.begin(), p.skills.end(), "ID") != p.skills.end())
        amount += p.mastery.at("ID"); // Identification mastery improves healing.
    animatedBar("Before rest", p.hp, p.max_hp);
    p.heal(amount); // Apply capped healing.
    sleepMs(250);
    animatedBar("After rest", p.hp, p.max_hp);
    typeText("You rest and recover " + std::to_string(amount) + " HP.");
}

// ─────────────────────── ACHIEVEMENTS ────────────────────────────────────────
void awardAchievement(RunState& s, const std::string& name) {
    // Prevent duplicate achievements while keeping unlock order.
    if (std::find(s.achievements.begin(), s.achievements.end(), name) == s.achievements.end()) {
        s.achievements.push_back(name);
        typeText("*** Achievement unlocked: " + name + " ***");
    }
}
void checkAchievements(Player& p, RunState& s) {
    // Called after meaningful progress so achievements unlock during the run.
    if (s.battles_won >= 1) awardAchievement(s, "First Victory");
    if (s.nodes >= 5)       awardAchievement(s, "Node Walker");
    if (s.elites_won >= 1)  awardAchievement(s, "Elite Breaker");
    if (p.best_streak >= 10)awardAchievement(s, "Scholar Streak");
    for (auto& [k, v] : p.mastery) if (v >= 10) { awardAchievement(s, "Master Student"); break; }
    if (s.boss_won)         awardAchievement(s, "Boss Clear");
}

// ─────────────────────── RANDOM EVENTS ───────────────────────────────────────
void randomEvent(Player& p) {
    // Only 20% of cleared nodes trigger an extra event.
    double roll = randReal();
    if (roll > 0.20) return;
    typeText("\nA small event interrupts the path...");
    if (roll < 0.05) {
        auto names = itemNames();
        std::string found = randChoice(names);
        p.inventory.push_back(found);
        typeText("You find a forgotten cache: " + found + ".");
    } else if (roll < 0.10) {
        int coins = randInt(8, 20); p.gold += coins;
        typeText("You discover " + std::to_string(coins) + " gold.");
    } else if (roll < 0.15) {
        p.takeDamage(8);
        typeText("A trap clips you for 8 damage.");
    } else {
        p.focus = std::min(100, p.focus + 15);
        typeText("A quiet insight restores 15 focus.");
    }
}

// ─────────────────────── VIEWS ───────────────────────────────────────────────
void viewCharacter(Player& p) {
    // Shows long-term player state outside combat.
    std::cout << "\n=== Character Sheet ===\n";
    std::cout << p.name << " the " << p.class_name << '\n';
    std::cout << "HP: " << bar(p.hp, p.max_hp) << "  Shield: " << p.shield << '\n';
    std::cout << "ATK " << p.atk << " | DEF " << p.defense << " | SPD " << p.spd << " | WIS " << p.wisdom << '\n';
    std::cout << "Crit " << (int)(p.crit * 100) << "% x" << p.crit_mult << '\n';
    std::cout << "Level " << p.level << " | EXP " << p.exp << "/" << p.next_exp << " | Gold " << p.gold << '\n';
    std::cout << "Streak " << p.streak << " | Best " << p.best_streak << " | Focus " << p.focus << "/100\n";
    std::cout << "Passive: " << (p.passive.empty() ? "none" : p.passive)
              << " | Modifier: " << (p.run_modifier.empty() ? "none" : p.run_modifier) << '\n';
    std::cout << "Mastery: ";
    for (auto& [k, v] : p.mastery) std::cout << k << ":" << v << " ";
    std::cout << '\n';
    std::cout << "Inventory: ";
    if (p.inventory.empty()) std::cout << "empty";
    else for (auto& i : p.inventory) std::cout << i << " ";
    std::cout << '\n';
    std::cout << "Skills: ";
    if (p.skills.empty()) std::cout << "none";
    else for (auto& s : p.skills) std::cout << SKILLS.at(s).first << " ";
    std::cout << '\n';
    pause();
}

void viewInventory(Player& p) {
    // Non-combat inventory view allows only items that make sense outside combat.
    std::cout << "\n=== Inventory ===\n";
    if (p.inventory.empty()) { std::cout << "Inventory is empty.\n"; pause(); return; }
    std::cout << "0. Back\n";
    for (int i = 0; i < (int)p.inventory.size(); ++i)
        std::cout << (i+1) << ". " << p.inventory[i] << '\n';
    std::cout << "\nUse healing items here, or save offensive items for combat.\n";
    int idx = chooseIndex("Use item? ", (int)p.inventory.size());
    if (idx < 0) { pause(); return; }
    std::string iname = p.inventory[idx];
    auto it = ITEMS.find(iname);
    if (it == ITEMS.end()) { typeText("Unknown item."); }
    else if (it->second.kind == "heal" || it->second.kind == "hint" || it->second.kind == "gold") {
        p.inventory.erase(p.inventory.begin() + idx);
        applyPlayerItem(p, it->second);
    } else { typeText("That item is only useful in combat."); }
    pause();
}

void viewBestiary(RunState& s) {
    // Shows enemies that were seen or defeated in this save/run.
    std::cout << "\n=== Bestiary ===\n";
    if (s.bestiary.empty()) std::cout << "No enemies recorded yet.\n";
    for (auto& [name, data] : s.bestiary)
        std::cout << name << ": seen " << data["seen"] << ", defeated " << data["kills"] << '\n';
    pause();
}

void viewAchievements(RunState& s) {
    // Compares saved achievements against the complete achievement catalog.
    std::cout << "\n=== Achievements ===\n";
    for (auto& [name, desc] : ACHIEVEMENTS) {
        bool unlocked = std::find(s.achievements.begin(), s.achievements.end(), name) != s.achievements.end();
        std::cout << "[" << (unlocked ? "X" : " ") << "] " << name << " - " << desc << '\n';
    }
    pause();
}

// ─────────────────────── MAP / NODE ──────────────────────────────────────────
std::string drawMap(const RunState& s) {
    // Shows only recent nodes so the console map stays compact.
    auto recent = s.journal;
    if ((int)recent.size() > 8) recent = std::vector<std::string>(recent.end() - 8, recent.end());
    std::string result;
    for (auto& n : recent) {
        auto it = NODE_ICONS.find(n);
        result += (it != NODE_ICONS.end() ? it->second : "[?]") + "--";
    }
    result += "[*]";
    return result;
}

std::vector<std::string> makeNodes(const RunState& s) {
    // Generate two or three possible next nodes, with boss unlocked late in tier 3.
    std::vector<std::string> types = {"battle","elite","shop","trial","rest"};
    if (s.tier >= 3 && s.nodes >= 10) types.push_back("boss");
    std::shuffle(types.begin(), types.end(), rng());
    int count = randInt(2, 3);
    types.resize(std::min(count, (int)types.size()));
    return types;
}

void quickStatus(const Player& p, const RunState& s) {
    // Single-line summary printed above node choices.
    std::cout << p.name << " | HP " << p.hp << "/" << p.max_hp
              << " | Lv " << p.level << " | Gold " << p.gold
              << " | Tier " << s.tier << " Node " << s.nodes << '\n';
}

// ─────────────────────── SAVE / LOAD (simple text format) ────────────────────
// We use a hand-rolled key=value format to avoid external JSON deps.

void saveGame(const Player& p, const RunState& s, bool quiet = false) {
    /*
        Save format:
        - scalar fields are written as key=value lines;
        - vector fields are comma-separated on one line;
        - bestiary entries are repeated lines with name:seen:kills.

        This is not full JSON despite the filename; it is a compact custom format.
    */
    std::ofstream f(SAVE_FILE);
    if (!f) { typeText("Could not save."); return; }
    // Player
    f << "name=" << p.name << '\n'
      << "class_name=" << p.class_name << '\n'
      << "passive=" << p.passive << '\n'
      << "run_modifier=" << p.run_modifier << '\n'
      << "max_hp=" << p.max_hp << '\n'
      << "hp=" << p.hp << '\n'
      << "atk=" << p.atk << '\n'
      << "defense=" << p.defense << '\n'
      << "spd=" << p.spd << '\n'
      << "crit=" << p.crit << '\n'
      << "wisdom=" << p.wisdom << '\n'
      << "level=" << p.level << '\n'
      << "exp=" << p.exp << '\n'
      << "next_exp=" << p.next_exp << '\n'
      << "gold=" << p.gold << '\n'
      << "streak=" << p.streak << '\n'
      << "best_streak=" << p.best_streak << '\n'
      << "focus=" << p.focus << '\n'
      << "correct_answers=" << p.correct_answers << '\n'
      << "total_answers=" << p.total_answers << '\n';
    // inventory
    f << "inventory=";
    for (int i = 0; i < (int)p.inventory.size(); ++i) {
        if (i) f << ',';
        f << p.inventory[i];
    }
    f << '\n';
    // skills
    f << "skills=";
    for (int i = 0; i < (int)p.skills.size(); ++i) { if (i) f << ','; f << p.skills[i]; }
    f << '\n';
    // mastery
    for (auto& [k, v] : p.mastery) f << "mastery_" << k << "=" << v << '\n';
    // RunState
    f << "tier=" << s.tier << '\n'
      << "nodes=" << s.nodes << '\n'
      << "battles_won=" << s.battles_won << '\n'
      << "elites_won=" << s.elites_won << '\n'
      << "boss_won=" << (s.boss_won ? 1 : 0) << '\n';
    f << "achievements=";
    for (int i = 0; i < (int)s.achievements.size(); ++i) { if (i) f << ','; f << s.achievements[i]; }
    f << '\n';
    f << "journal=";
    for (int i = 0; i < (int)s.journal.size(); ++i) { if (i) f << ','; f << s.journal[i]; }
    f << '\n';
    // bestiary: one line per entry
    for (auto& [name, data] : s.bestiary) {
        int seen = data.count("seen") ? data.at("seen") : 0;
        int kills = data.count("kills") ? data.at("kills") : 0;
        f << "bestiary=" << name << ":" << seen << ":" << kills << '\n';
    }
    if (!quiet) typeText("Game saved.");
    else if (ANIMATIONS) std::cout << "[autosaved]\n";
}

std::vector<std::string> splitStr(const std::string& s, char delim) {
    // Helper for reading comma-separated and colon-separated fields from the save file.
    std::vector<std::string> out;
    std::istringstream ss(s);
    std::string tok;
    while (std::getline(ss, tok, delim)) out.push_back(trim(tok));
    return out;
}

bool loadGame(Player& p, RunState& s) {
    // Rebuilds Player and RunState from the key=value save format used by saveGame.
    std::ifstream f(SAVE_FILE);
    if (!f) { typeText("No save file found."); return false; }
    // Reset to a valid baseline before applying saved fields.
    p = Player("Hero", 60, 10, 4, 5, 0.10);
    s = RunState();
    std::string line;
    while (std::getline(f, line)) {
        line = trim(line);
        auto eq = line.find('='); // Save lines are split at the first equals sign.
        // Ignore malformed lines instead of failing the whole load.
        if (eq == std::string::npos) continue;
        std::string key = trim(line.substr(0, eq));     // Left side is the saved field name.
        std::string val = trim(line.substr(eq + 1));    // Right side is the saved field value.
        if (key == "name")         p.name = val;        // Text fields can be copied directly.
        else if (key == "class_name")   p.class_name = val;
        else if (key == "passive")      p.passive = val;
        else if (key == "run_modifier") p.run_modifier = val;
        else if (key == "max_hp")   p.max_hp = std::stoi(val); // Numeric fields are converted from text.
        else if (key == "hp")       p.hp = std::stoi(val);
        else if (key == "atk")      p.atk = std::stoi(val);
        else if (key == "defense")  p.defense = std::stoi(val);
        else if (key == "spd")      p.spd = std::stoi(val);
        else if (key == "crit")     p.crit = std::stod(val); // Crit uses a decimal number.
        else if (key == "wisdom")   p.wisdom = std::stoi(val);
        else if (key == "level")    p.level = std::stoi(val);
        else if (key == "exp")      p.exp = std::stoi(val);
        else if (key == "next_exp") p.next_exp = std::stoi(val);
        else if (key == "gold")     p.gold = std::stoi(val);
        else if (key == "streak")   p.streak = std::stoi(val);
        else if (key == "best_streak") p.best_streak = std::stoi(val);
        else if (key == "focus")    p.focus = std::stoi(val);
        else if (key == "correct_answers") p.correct_answers = std::stoi(val);
        else if (key == "total_answers")   p.total_answers = std::stoi(val);
        else if (key == "inventory") {
            p.inventory.clear();
            if (!val.empty()) for (auto& s2 : splitStr(val, ',')) if (!s2.empty()) p.inventory.push_back(s2); // Rebuild item-name list.
        } else if (key == "skills") {
            p.skills.clear();
            if (!val.empty()) for (auto& s2 : splitStr(val, ',')) if (!s2.empty()) p.skills.push_back(s2); // Rebuild unlocked skill codes.
        } else if (key.substr(0, 8) == "mastery_") {
            std::string qt = key.substr(8); // Remove "mastery_" prefix to get the question type.
            p.mastery[qt] = std::stoi(val); // Restore that question type's mastery count.
        } else if (key == "tier")         s.tier = std::stoi(val);
        else if (key == "nodes")          s.nodes = std::stoi(val);
        else if (key == "battles_won")    s.battles_won = std::stoi(val);
        else if (key == "elites_won")     s.elites_won = std::stoi(val);
        else if (key == "boss_won")       s.boss_won = std::stoi(val) != 0;
        else if (key == "achievements") {
            s.achievements.clear();
            if (!val.empty()) for (auto& a : splitStr(val, ',')) if (!a.empty()) s.achievements.push_back(a);
        } else if (key == "journal") {
            s.journal.clear();
            if (!val.empty()) for (auto& j : splitStr(val, ',')) if (!j.empty()) s.journal.push_back(j);
        } else if (key == "bestiary") {
            auto parts = splitStr(val, ':');
            if (parts.size() == 3) {
                s.bestiary[parts[0]]["seen"]  = std::stoi(parts[1]);
                s.bestiary[parts[0]]["kills"] = std::stoi(parts[2]);
            }
        }
    }
    return true;
}

// ─────────────────────── SETTINGS / HELP ─────────────────────────────────────
void showHelp() {
    // Central place for command reminders used from both title and node menus.
    std::cout << "\n=== Help / Controls ===\n"
              << "Title Menu: 1=new, 2=load, 3=practice, 4=achievements, 5=settings, 6=help, 7=exit.\n"
              << "Node Menu: choose a path number, or c=character, i=inventory,\n"
              << "  b=bestiary, a=achievements, t=settings, s=save, q=save&quit.\n"
              << "Combat: answer questions to attack, use items, spend focus, or mastery skills.\n"
              << "Tip: mastery skills unlock at 5 correct answers in a question type.\n";
    pause();
}

void setTextSpeed() {
    // Settings mutate the global display controls used by all text helpers.
    const std::map<std::string, double> speeds = {
        {"instant",0.0},{"fast",0.005},{"normal",0.015},{"slow",0.035}
    };
    while (true) {
        std::cout << "\nSettings:\n1. Text Speed\n"
                  << "2. Animations: " << (ANIMATIONS ? "On" : "Off") << '\n'
                  << "0. Back\n";
        std::string choice = ask("> ", {"0","1","2"});
        if (choice == "0") return;
        if (choice == "2") {
            ANIMATIONS = !ANIMATIONS;
            typeText(ANIMATIONS ? "Animations enabled." : "Animations disabled.");
            continue;
        }
        std::cout << "1. Instant  2. Fast  3. Normal  4. Slow\n";
        std::string sc = ask("> ", {"1","2","3","4"});
        if (sc == "1") TEXT_SPEED = 0.0;
        else if (sc == "2") TEXT_SPEED = 0.005;
        else if (sc == "3") TEXT_SPEED = 0.015;
        else TEXT_SPEED = 0.035;
        typeText("Text speed updated.");
    }
}

// ─────────────────────── PRACTICE MODE ───────────────────────────────────────
void practiceMode(LearningEngine& engine) {
    // Practice reuses the same question code but a dummy player absorbs stat changes.
    divider("Practice Mode");
    typeText("Answer questions without combat pressure.");
    int correct = 0, total = 0;
    Player dummy("Practice", 50, 8, 3, 5, 0.1);
    while (true) {
        if (!engine.pick()) { typeText("No questions loaded."); break; }
        typeText("\nPractice question:");
        auto [ok, _] = askQuestion(engine, dummy);
        total++;
        if (ok) correct++;
        typeText("Practice score: " + std::to_string(correct) + "/" + std::to_string(total));
        if (ask("Continue practice? (y/n)> ", {"y","n"}) == "n") break;
    }
}

// ─────────────────────── NEW PLAYER / MODIFIER ───────────────────────────────
Player newPlayer() {
    // Creates a Player from the chosen ClassBuild template.
    std::string name = askRaw("Character name: ");
    if (name.empty()) name = "Hero";
    std::cout << "\nChoose a class:\n";
    for (int i = 0; i < (int)CLASS_BUILDS.size(); ++i)
        std::cout << (i+1) << ". " << CLASS_BUILDS[i].name << " - " << CLASS_BUILDS[i].desc << '\n';
    int idx = chooseIndex("> ", (int)CLASS_BUILDS.size());
    if (idx < 0) idx = 0;
    const ClassBuild& cb = CLASS_BUILDS[idx];
    Player p(name, cb.hp, cb.atk, cb.def, cb.spd, cb.crit, cb.wisdom);
    p.class_name = cb.name;
    p.passive    = cb.passive;
    return p;
}

void chooseRunModifier(Player& p) {
    // Stores only the modifier key; specific mechanics check the key later.
    std::cout << "\nChoose a run modifier:\n";
    for (int i = 0; i < (int)RUN_MODIFIERS.size(); ++i)
        std::cout << (i+1) << ". " << RUN_MODIFIERS[i].label << " - " << RUN_MODIFIERS[i].desc << '\n';
    int idx = chooseIndex("> ", (int)RUN_MODIFIERS.size());
    if (idx < 0) idx = 0;
    p.run_modifier = RUN_MODIFIERS[idx].key;
    if (!p.run_modifier.empty()) typeText("Modifier active: " + p.run_modifier + ".");
}

// ─────────────────────── TITLE SCREEN ────────────────────────────────────────
void showTitle() {
    // Title redraw is called after returning from submenus.
    clearScreen();
    std::cout << TITLE_ART << '\n';
    typeText("        A C++ Educational RPG - Console Build", 0.01);
    typeText("        Answer. Battle. Learn. Survive the node path.", 0.01);
    std::cout << std::string(78, '=') << '\n';
}

std::string titleMenu(LearningEngine& engine) {
    // Returns the choice that should leave the title screen: new, load, or exit.
    while (true) {
        loading("Ready");
        std::cout << '\n';
        typeText("1. New Game", 0.005);
        typeText("2. Load Game", 0.005);
        typeText("3. Practice Mode", 0.005);
        typeText("4. View Saved Achievements", 0.005);
        typeText("5. Settings", 0.005);
        typeText("6. Help", 0.005);
        typeText("7. Exit", 0.005);
        std::string choice = ask("> ", {"1","2","3","4","5","6","7"});
        if (choice == "3") { practiceMode(engine); showTitle(); continue; }
        if (choice == "4") {
            Player tmp; RunState s;
            if (loadGame(tmp, s)) viewAchievements(s);
            else { RunState empty; viewAchievements(empty); }
            showTitle(); continue;
        }
        if (choice == "5") { setTextSpeed(); showTitle(); continue; }
        if (choice == "6") { showHelp(); showTitle(); continue; }
        return choice;
    }
}

// ─────────────────────── NODE LOOP ───────────────────────────────────────────
std::string chooseNode(RunState& s, Player& p) {
    /*
        Node menu loop:
        - generate the current choices;
        - let the player inspect side screens or settings without advancing;
        - return a node/action string once the player chooses progress, save, or quit.
    */
    while (true) {
        auto nodes = makeNodes(s);
        divider("Tier " + std::to_string(s.tier) + " | Node " + std::to_string(s.nodes));
        quickStatus(p, s);
        // Animate the map one character at a time when animations are enabled.
        std::string mapStr = drawMap(s);
        std::cout << "Map: " << std::flush;
        for (char c : mapStr) {
            std::cout << c << std::flush;
            if (ANIMATIONS && TEXT_SPEED > 0 && (c == '-' || c == '[' || c == ']' || c == '!' || c == '*'))
                sleepMs(25);
        }
        std::cout << '\n';
        for (int i = 0; i < (int)nodes.size(); ++i) {
            auto it = NODE_ICONS.find(nodes[i]);
            std::string icon = (it != NODE_ICONS.end()) ? it->second : "[?]";
            std::cout << (i+1) << ". " << icon << " " << nodes[i] << '\n';
        }
        std::cout << "c. Character | i. Inventory | b. Bestiary | a. Achievements\n";
        std::cout << "?. Help | t. Settings | s. Save | q. Save and Quit\n";
        std::string choice = toLower(askRaw("> "));

        if (choice == "?" || choice == "h" || choice == "help") showHelp();
        else if (choice == "c") viewCharacter(p);
        else if (choice == "i") viewInventory(p);
        else if (choice == "b") viewBestiary(s);
        else if (choice == "a") viewAchievements(s);
        else if (choice == "t") setTextSpeed();
        else if (choice == "s") return "save";
        else if (choice == "q") {
            if (confirm("Save and quit")) return "quit";
        } else if (!choice.empty() && std::all_of(choice.begin(), choice.end(), ::isdigit)) {
            int n = std::stoi(choice);
            if (n >= 1 && n <= (int)nodes.size()) return nodes[n-1];
            else typeText("Invalid choice.");
        } else { typeText("Invalid choice."); }
    }
}

bool runNode(Player& p, LearningEngine& engine, RunState& s, const std::string& node) {
    // Executes the selected node and returns whether the run should continue.
    if (node == "save" || node == "quit") {
        saveGame(p, s);
        return node != "quit";
    }
    if (node == "battle") {
        loading("Walking toward battle");
        std::string result = combat(p, engine, s, s.tier);
        if (result == "death") return false;
        if (result == "win") s.battles_won++;
    } else if (node == "elite") {
        loading("A powerful presence approaches");
        std::string result = combat(p, engine, s, s.tier, true);
        if (result == "death") return false;
        if (result == "win") { s.battles_won++; s.elites_won++; p.max_hp += 5; }
    } else if (node == "boss") {
        loading("The final gate opens");
        std::string result = combat(p, engine, s, 3, false, true);
        if (result == "win") {
            s.boss_won = true;
            s.journal.push_back("boss");
            typeText("\nFinal boss defeated. You win the run.");
            checkAchievements(p, s);
        }
        return result == "win";
    } else if (node == "shop") {
        loading("Following the lantern light");
        shop(p);
    } else if (node == "trial") {
        loading("Entering the trial chamber");
        trial(p, engine);
    } else if (node == "rest") {
        loading("Finding a quiet place");
        rest(p);
    }

    s.nodes++;
    s.journal.push_back(node);
    if (s.nodes % 5 == 0) {
        // Every five cleared nodes increases tier, up to tier 3.
        s.tier = std::min(3, s.tier + 1);
        typeText("\nTier increased to " + std::to_string(s.tier) + ".");
    }
    p.heal(std::max(1, p.max_hp / 20));
    // Small automatic recovery and events keep the path from being only combat.
    randomEvent(p);
    checkAchievements(p, s);
    saveGame(p, s, true);
    return true;
}

// ─────────────────────── RUN SUMMARY ─────────────────────────────────────────
void printRunSummary(const Player& p, const RunState& s, const LearningEngine& engine) {
    // End-of-run summary includes learning stats and a short review list.
    std::cout << "\n=== Run Summary ===\n"
              << "Name: " << p.name << '\n'
              << "Level: " << p.level << '\n'
              << "Nodes cleared: " << s.nodes << '\n'
              << "Battles won: " << s.battles_won << '\n'
              << "Gold: " << p.gold << '\n'
              << "Best streak: " << p.best_streak << '\n';
    int acc = (int)((double)p.correct_answers / std::max(1, p.total_answers) * 100);
    std::cout << "Accuracy: " << p.correct_answers << "/" << p.total_answers << " (" << acc << "%)\n";
    std::cout << "Mastery: ";
    for (auto& [k, v] : p.mastery) std::cout << k << ":" << v << " ";
    std::cout << '\n';
    if (!s.achievements.empty()) {
        std::cout << "Achievements: ";
        for (auto& a : s.achievements) std::cout << a << "  ";
        std::cout << '\n';
    }
    if (!engine.wrong.empty()) {
        std::cout << "\nReview missed questions:\n";
        int start = std::max(0, (int)engine.wrong.size() - 5);
        for (int i = start; i < (int)engine.wrong.size(); ++i)
            std::cout << "- " << engine.wrong[i].text << " = " << engine.wrong[i].answer << '\n';
    }
}

// ─────────────────────── MAIN ────────────────────────────────────────────────
int main() {
#ifdef _WIN32
    // Allows Windows console to display UTF-8 title art and symbols correctly.
    SetConsoleOutputCP(CP_UTF8);
#endif
    // Initialize the title screen and question database before the player chooses a mode.
    showTitle(); // Draw opening title art and subtitle.
    LearningEngine engine; // Holds all loaded questions and missed-question review data.
    engine.loadAll(); // Read question files into memory.

    std::string choice = titleMenu(engine); // Ask whether to start, load, practice, or exit.
    if (choice == "7") return 0; // Exit immediately when the player chooses Exit.

    Player player; // Main player object for this run.
    RunState state; // Main run progress object for this run.
    bool loaded = false; // Tracks whether loadGame succeeded.
    // Load existing save only for menu choice 2; otherwise start a fresh run.
    if (choice == "2") loaded = loadGame(player, state);
    if (loaded) {
        typeText("Save loaded.");
    } else {
        player = newPlayer(); // Build a new player from name and class selection.
        state  = RunState();  // Fresh run starts from default tier/node values.
        chooseRunModifier(player); // Optional rule modifier is stored on the player.
    }

    bool alive = true; // Controls whether the run loop should continue.
    bool savedAndQuit = false; // Distinguishes quitting from death/victory summary.
    while (alive) {
        // Main run loop: choose a node, run it, and stop on death, quit, or boss victory.
        std::string node = chooseNode(state, player); // Let player choose next path action.
        alive = runNode(player, engine, state, node); // Execute the selected action.
        if (node == "quit") { savedAndQuit = true; break; } // Stop cleanly after save-and-quit.
        if (node == "boss" && alive) break; // Boss victory ends the run.
    }

    if (savedAndQuit) typeText("Saved. See you next run."); // Quit message when player saved.
    else printRunSummary(player, state, engine); // Death or victory shows final stats.
    return 0; // Tell the operating system the program ended successfully.
}
