/*
 * Game On Learning - Educational RPG (C++ Port)
 * Converted from Python compact console build.
 * Compile: g++ -std=c++17 -o game_rpg game_rpg.cpp
 */

#include <algorithm>
#include <chrono>
#include <ctime>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <vector>
#include <cctype>

#ifdef _WIN32
#include <windows.h>
#define CLEAR_CMD "cls"
#else
#define CLEAR_CMD "clear"
#endif

// ─────────────────────── RNG ────────────────────────────────────────────────
std::mt19937& rng() {
    static std::mt19937 gen(std::random_device{}());
    return gen;
}
int randInt(int lo, int hi) {
    return std::uniform_int_distribution<int>(lo, hi)(rng());
}
double randReal() {
    return std::uniform_real_distribution<double>(0.0, 1.0)(rng());
}
template <typename T>
T& randChoice(std::vector<T>& v) {
    return v[randInt(0, (int)v.size() - 1)];
}
template <typename T>
const T& randChoice(const std::vector<T>& v) {
    return v[randInt(0, (int)v.size() - 1)];
}

// ─────────────────────── GLOBALS ────────────────────────────────────────────
double TEXT_SPEED   = 0.015;
bool   ANIMATIONS   = true;

const std::string SAVE_FILE = "compact_save.json";

const std::map<std::string, std::string> QUESTION_FILES = {
    {"TF", "notes/TorF.txt"},
    {"MC", "notes/MCQ.txt"},
    {"AR", "notes/Math.txt"},
    {"ID", "notes/Identify.txt"},
    {"FB", "notes/FillBlanks.txt"},
    {"OD", "notes/OD.txt"},
};
const std::map<std::string, int> QUESTION_DIFFICULTY = {
    {"TF", 1}, {"MC", 2}, {"AR", 2}, {"ID", 3}, {"FB", 2}, {"OD", 3}
};
const std::map<std::string, std::string> NODE_ICONS = {
    {"battle", "[B]"}, {"elite", "[E]"}, {"shop", "[S]"},
    {"trial", "[T]"},  {"rest",  "[R]"}, {"boss", "[!]"}
};
const std::map<std::string, std::pair<std::string, std::string>> SKILLS = {
    {"TF", {"Truth Guard",    "Start battles with +5 shield."}},
    {"MC", {"Eliminate One", "Removes one wrong multiple-choice option."}},
    {"AR", {"Precision",     "Arithmetic mastery adds extra attack damage."}},
    {"ID", {"Recall",        "Identification mastery improves healing."}},
    {"FB", {"Composure",     "First wrong answer in battle does not break streak."}},
    {"OD", {"Tactical Read", "Ordering mastery can dodge the next enemy attack."}},
};
const std::map<std::string, std::string> ACHIEVEMENTS = {
    {"First Victory",   "Win your first battle."},
    {"Node Walker",     "Clear 5 nodes."},
    {"Elite Breaker",   "Defeat an elite."},
    {"Scholar Streak",  "Reach a streak of 10."},
    {"Master Student",  "Reach 10 mastery in any question type."},
    {"Boss Clear",      "Defeat the final boss."},
};

struct ClassBuild {
    std::string name, passive;
    int hp, atk, def, spd, wisdom;
    double crit;
    std::string desc;
};
const std::vector<ClassBuild> CLASS_BUILDS = {
    {"Berserker", "bloodlust",  70, 14, 5, 4, 5,  0.12, "gains ATK after correct answers"},
    {"Duelist",   "momentum",   55, 11, 4, 9, 5,  0.25, "correct answers boost next crit chance"},
    {"Arcanist",  "insight",    50,  9, 4, 5, 25, 0.10, "gains extra focus from correct answers"},
    {"Sentinel",  "fortress",   90,  9, 9, 2, 5,  0.08, "wrong answers grant shield"},
};

struct RunModifier { std::string label, key, desc; };
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
    Sleep(ms);
#else
    std::this_thread::sleep_for(std::chrono::milliseconds(ms));
#endif
}
void typeText(const std::string& text, double speed = -1, bool newline = true) {
    double s = (speed < 0) ? TEXT_SPEED : speed;
    for (char c : text) {
        std::cout << c << std::flush;
        if (s > 0) sleepMs((int)(s * 1000));
    }
    if (newline) std::cout << '\n';
}
void loading(const std::string& msg, int steps = 3) {
    std::cout << msg << std::flush;
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
    if (!ANIMATIONS || TEXT_SPEED == 0) { typeText(msg); return; }
    for (int i = 0; i < repeats; ++i) {
        std::cout << '\r' << msg << std::flush; sleepMs(180);
        std::cout << '\r' << std::string(msg.size(), ' ') << std::flush; sleepMs(100);
    }
    std::cout << '\r' << msg << '\n';
}
void clearScreen() { system(CLEAR_CMD); }
void pause() { std::cout << "\nPress Enter to continue..."; std::cin.ignore(10000, '\n'); }

std::string bar(int cur, int max, int size = 20) {
    int filled = (max > 0) ? (int)(size * std::max(0, cur) / std::max(1, max)) : 0;
    std::string b = "[";
    b += std::string(filled, '#');
    b += std::string(size - filled, '-');
    b += "] " + std::to_string(cur) + "/" + std::to_string(max);
    return b;
}
void animatedBar(const std::string& label, int cur, int max, int size = 20) {
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

// trim whitespace
std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}
std::string toLower(std::string s) {
    for (char& c : s) c = (char)tolower(c);
    return s;
}

// ─────────────────────── INPUT HELPERS ──────────────────────────────────────
std::string askRaw(const std::string& prompt) {
    std::cout << prompt << std::flush;
    std::string line;
    std::getline(std::cin, line);
    return trim(line);
}
std::string ask(const std::string& prompt,
                const std::vector<std::string>& valid = {}) {
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
    return ask(prompt + " (y/n)> ", {"y", "n"}) == "y";
}
template <typename T>
void printNumbered(const std::vector<T>& items,
                   std::function<std::string(const T&)> label = nullptr) {
    for (int i = 0; i < (int)items.size(); ++i) {
        std::string lbl = label ? label(items[i]) : [&]() -> std::string {
            std::ostringstream oss; oss << items[i]; return oss.str();
        }();
        std::cout << (i + 1) << ". " << lbl << '\n';
    }
}

// ─────────────────────── DATA STRUCTURES ─────────────────────────────────────
struct Question {
    std::string qtype, text, answer;
    int difficulty = 1;
    std::vector<std::string> options;   // MC
    std::vector<std::string> items;     // OD
};

struct Effects {
    std::map<std::string, int> data;
    int get(const std::string& k) const {
        auto it = data.find(k); return it != data.end() ? it->second : 0;
    }
    void set(const std::string& k, int v) { data[k] = v; }
    int pop(const std::string& k) {
        auto it = data.find(k); if (it == data.end()) return 0;
        int v = it->second; data.erase(it); return v;
    }
    void tick() {
        std::vector<std::string> expired;
        for (auto& [k, v] : data) { --v; if (v <= 0) expired.push_back(k); }
        for (auto& k : expired) data.erase(k);
    }
    std::string list() const {
        std::string s;
        for (auto& [k, v] : data) s += k + "(" + std::to_string(v) + ") ";
        return s.empty() ? "none" : s;
    }
};

struct Fighter {
    std::string name;
    int max_hp, atk, defense, spd;
    double crit, crit_mult = 1.5;
    int hp = 0, shield = 0;
    std::string behavior = "neutral";
    Effects effects;

    Fighter() = default;
    Fighter(std::string n, int mhp, int a, int d, int sp, double cr, std::string beh = "neutral")
        : name(std::move(n)), max_hp(mhp), atk(a), defense(d), spd(sp), crit(cr), behavior(std::move(beh)) {
        hp = max_hp;
    }
    bool alive() const { return hp > 0; }
    void takeDamage(int amount) {
        if (shield > 0) {
            int blocked = std::min(shield, amount);
            shield -= blocked; amount -= blocked;
            if (blocked) typeText(name + "'s shield blocks " + std::to_string(blocked) + " damage.");
        }
        hp = std::max(0, hp - amount);
    }
    void heal(int amount) { hp = std::min(max_hp, hp + amount); }
};

struct Player : Fighter {
    std::string class_name = "Adventurer", passive, run_modifier;
    int wisdom = 5, level = 1, exp = 0, next_exp = 100;
    int gold = 20, streak = 0, best_streak = 0, focus = 0;
    bool hint_ready = false, dodge_next = false, streak_guard = false;
    int bloodlust_stacks = 0;
    int correct_answers = 0, total_answers = 0;
    std::vector<std::string> skills;
    std::map<std::string, int> mastery = {
        {"TF",0},{"MC",0},{"AR",0},{"ID",0},{"FB",0},{"OD",0}
    };
    std::vector<std::string> inventory = {"Potion", "Attack Tonic", "Hint"};

    Player() : Fighter() {}
    Player(std::string n, int mhp, int a, int d, int sp, double cr, int wis = 5)
        : Fighter(std::move(n), mhp, a, d, sp, cr), wisdom(wis) {}
};

struct RunState {
    int tier = 1, nodes = 0, battles_won = 0, elites_won = 0;
    bool boss_won = false;
    std::map<std::string, std::map<std::string, int>> bestiary;
    std::vector<std::string> achievements;
    std::vector<std::string> journal;
};

// ─────────────────────── ITEMS ───────────────────────────────────────────────
struct Item { std::string name, kind; int price, value; };
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
    std::vector<std::string> v;
    for (auto& [k, _] : ITEMS) v.push_back(k);
    return v;
}

// ─────────────────────── ENEMIES ─────────────────────────────────────────────
struct EnemyTemplate {
    std::string name, behavior;
    int hp, atk, def, spd;
    double crit;
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
    auto it = ENEMIES.find(std::min(3, tier));
    const auto& pool = it != ENEMIES.end() ? it->second : ENEMIES.at(1);
    const auto& tmpl = randChoice(pool);
    Fighter f(tmpl.name, tmpl.hp, tmpl.atk, tmpl.def, tmpl.spd, tmpl.crit, tmpl.behavior);
    if (elite) {
        f.name = "Elite " + f.name;
        f.max_hp = (int)(f.max_hp * 1.5); f.hp = f.max_hp;
        f.atk = (int)(f.atk * 1.3); f.defense += 2;
        std::vector<std::string> behs = {"aggressive","defensive","evasive"};
        f.behavior = randChoice(behs);
    }
    if (boss) {
        f.name = "Boss " + f.name;
        f.max_hp = (int)(f.max_hp * 2.2); f.hp = f.max_hp;
        f.atk = (int)(f.atk * 1.5); f.defense += 4;
        f.crit = std::min(0.5, f.crit + 0.08);
        f.behavior = "boss";
    }
    return f;
}

// ─────────────────────── LEARNING ENGINE ────────────────────────────────────
// Minimal JSON parser for our specific line formats
// MC/OD lines are JSON objects. We parse them ourselves to avoid dependencies.

bool parseJsonString(const std::string& json, const std::string& key, std::string& out) {
    std::string search = "\"" + key + "\"";
    auto pos = json.find(search);
    if (pos == std::string::npos) return false;
    pos = json.find(':', pos); if (pos == std::string::npos) return false;
    pos = json.find('"', pos + 1); if (pos == std::string::npos) return false;
    size_t end = json.find('"', pos + 1);
    if (end == std::string::npos) return false;
    out = json.substr(pos + 1, end - pos - 1);
    return true;
}
std::vector<std::string> parseJsonArray(const std::string& json, const std::string& key) {
    std::vector<std::string> result;
    std::string search = "\"" + key + "\"";
    auto pos = json.find(search);
    if (pos == std::string::npos) return result;
    pos = json.find('[', pos); if (pos == std::string::npos) return result;
    size_t end = json.find(']', pos);
    if (end == std::string::npos) return result;
    std::string arr = json.substr(pos + 1, end - pos - 1);
    std::istringstream ss(arr);
    std::string token;
    while (std::getline(ss, token, ',')) {
        std::string t = trim(token);
        if (t.size() >= 2 && t.front() == '"' && t.back() == '"')
            t = t.substr(1, t.size() - 2);
        if (!t.empty()) result.push_back(t);
    }
    return result;
}

struct LearningEngine {
    std::vector<Question> questions;
    std::vector<Question> wrong;

    void loadAll() {
        for (auto& [qtype, relpath] : QUESTION_FILES) {
            int diff = QUESTION_DIFFICULTY.at(qtype);
            loadFile(relpath, qtype, diff);
        }
        std::cout << "Loaded " << questions.size() << " questions.\n";
    }

    void loadFile(const std::string& path, const std::string& qtype, int difficulty) {
        std::ifstream f(path);
        if (!f.is_open()) {
            std::cout << "Missing question file: " << path << '\n';
            return;
        }
        std::string line;
        while (std::getline(f, line)) {
            line = trim(line);
            if (line.empty()) continue;
            Question q;
            q.qtype = qtype;
            q.difficulty = difficulty;
            if (qtype == "TF" || qtype == "AR" || qtype == "ID" || qtype == "FB") {
                auto eq = line.find('=');
                if (eq == std::string::npos) continue;
                q.text   = trim(line.substr(0, eq));
                q.answer = trim(line.substr(eq + 1));
                questions.push_back(q);
            } else if (qtype == "MC") {
                if (!parseJsonString(line, "question", q.text)) continue;
                if (!parseJsonString(line, "answer",   q.answer)) continue;
                q.options = parseJsonArray(line, "options");
                if (q.options.empty()) continue;
                questions.push_back(q);
            } else if (qtype == "OD") {
                if (!parseJsonString(line, "question", q.text)) continue;
                if (!parseJsonString(line, "answer",   q.answer)) continue;
                q.items = parseJsonArray(line, "items");
                if (q.items.empty()) continue;
                questions.push_back(q);
            }
        }
    }

    Question* pick(int difficulty = -1) {
        std::vector<Question*> pool;
        for (auto& q : questions)
            if (difficulty < 0 || q.difficulty == difficulty)
                pool.push_back(&q);
        if (pool.empty() && difficulty >= 0) {
            for (auto& q : questions) pool.push_back(&q);
        }
        if (pool.empty()) return nullptr;
        std::set<std::string> missed;
        for (auto& q : wrong) missed.insert(q.text);
        std::vector<int> weights;
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
    for (auto& [qtype, mastery] : p.mastery) {
        if (mastery >= 5 && std::find(p.skills.begin(), p.skills.end(), qtype) == p.skills.end()) {
            p.skills.push_back(qtype);
            auto& [name, desc] = SKILLS.at(qtype);
            typeText("Skill unlocked: " + name + " - " + desc);
        }
    }
}

int effectiveAtk(const Fighter& f) {
    int total = f.atk;
    if (f.effects.get("attack_up") > 0) total += 5;
    if (f.effects.get("weakness")  > 0) total -= 5;
    return std::max(1, total);
}
int effectiveDef(const Fighter& f) {
    int total = f.defense;
    if (f.effects.get("defense_up") > 0) total += 5;
    return std::max(0, total);
}

std::pair<int, bool> calcDamage(Fighter& attacker, const Fighter& defender,
                                int mastery_bonus = 0,
                                const Player* player_hint = nullptr) {
    int base = effectiveAtk(attacker) - effectiveDef(defender) + randInt(-2, 3);
    base = std::max(1, base);
    base += mastery_bonus / 5;
    if (player_hint) {
        base += player_hint->streak / 4;
        base = (int)(base * (1.0 + player_hint->wisdom * 0.01));
    }
    double crit_bonus = (attacker.effects.pop("momentum") > 0) ? 0.20 : 0.0;
    bool crit = randReal() < attacker.crit + crit_bonus;
    if (crit) base = (int)(base * attacker.crit_mult);
    return {base, crit};
}

void tickEffects(Fighter& f) {
    if (f.effects.get("poison") > 0) {
        f.takeDamage(5);
        typeText(f.name + " takes 5 poison damage.");
    }
    f.effects.tick();
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
        answer = ask("(true/false)> ", {"true", "false"});
    } else if (q.qtype == "MC") {
        auto options = q.options;
        if (std::find(p.skills.begin(), p.skills.end(), "MC") != p.skills.end()) {
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
        // Build correct order from q.answer indices
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
    p.total_answers++;
    if (correct) {
        typeText("Correct.");
        p.correct_answers++;
        p.mastery[q.qtype]++;
        p.streak++;
        p.best_streak = std::max(p.best_streak, p.streak);
        int focus_gain = 10 + p.wisdom / 5;
        if (p.passive == "insight") focus_gain += 5;
        p.focus = std::min(100, p.focus + focus_gain);
        if (p.passive == "bloodlust" && p.bloodlust_stacks < 10) {
            p.atk++; p.bloodlust_stacks++;
            typeText("[Bloodlust] ATK rises by 1.");
        }
        if (p.passive == "momentum") p.effects.set("momentum", 1);
        if (q.qtype == "OD" &&
            std::find(p.skills.begin(), p.skills.end(), "OD") != p.skills.end() &&
            randReal() < 0.25) {
            p.dodge_next = true;
            typeText("[Tactical Read] Next attack may be dodged.");
        }
        unlockSkills(p);
    } else {
        typeText("Wrong. Correct answer: " + q.answer);
        engine.wrong.push_back(q);
        if (p.streak_guard) {
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
            p.takeDamage(10);
            typeText("[Cursed Knowledge] You lose 10 HP.");
        }
    }
    return {correct, q.qtype};
}

// ─────────────────────── MASTERY SKILL USE ───────────────────────────────────
void useMasterySkill(Player& p, Fighter& enemy) {
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
    if (item.kind == "poison")   { enemy.effects.set("poison", 4); typeText(enemy.name + " is poisoned for 4 turns."); return true; }
    if (item.kind == "freeze")   { enemy.effects.set("freeze", item.value); typeText(enemy.name + " is frozen."); return true; }
    if (item.kind == "weakness") { enemy.effects.set("weakness", 3); typeText(enemy.name + "'s ATK is reduced for 3 turns."); return true; }
    return false;
}
void useItem(Player& p, Fighter& enemy) {
    if (p.inventory.empty()) { typeText("Inventory empty."); return; }
    std::cout << "0. Cancel\n";
    for (int i = 0; i < (int)p.inventory.size(); ++i)
        std::cout << (i+1) << ". " << p.inventory[i] << '\n';
    int idx = chooseIndex("Use which item? ", (int)p.inventory.size());
    if (idx < 0) return;
    std::string iname = p.inventory[idx];
    p.inventory.erase(p.inventory.begin() + idx);
    auto it = ITEMS.find(iname);
    if (it == ITEMS.end()) { typeText("Unknown item."); return; }
    const Item& item = it->second;
    if (!applyPlayerItem(p, item) && !applyEnemyItem(enemy, item))
        enemy.takeDamage(item.value);
}

// ─────────────────────── COMBAT STATS DISPLAY ────────────────────────────────
void showStats(const Player& p, const Fighter& enemy) {
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
    showStats(p, enemy);
    std::cout << "1. Answer/Attack\n";
    std::cout << "2. Use Item\n";
    std::cout << (p.focus >= 100 ? "3. Focus Skill\n" : "3. Focus Skill (not ready)\n");
    std::cout << (boss ? "4. Guard\n" : "4. Run\n");
    std::cout << "5. Mastery Skill\n";
    std::string choice = ask("> ", {"1","2","3","4","5"});

    if (choice == "1") {
        auto [correct, qtype] = askQuestion(engine, p, boss ? 3 : -1);
        if (correct) {
            int mastery = p.mastery.count(qtype) ? p.mastery.at(qtype) : 0;
            if (enemy.effects.get("evasive") > 0 && randReal() < 0.30) {
                typeText(enemy.name + " evades your attack.");
                return "continue";
            }
            auto [amount, crit] = calcDamage(p, enemy, mastery, &p);
            if (p.run_modifier == "scholar") amount *= 2;
            enemy.takeDamage(amount);
            typeText(p.name + " hits for " + std::to_string(amount) + " damage." +
                     (crit ? " Critical!" : ""));
        }
        return "continue";
    }
    if (choice == "2") { useItem(p, enemy); return "continue"; }
    if (choice == "3") {
        if (p.focus >= 100) {
            p.focus = 0;
            int amt = p.atk * 2 + p.wisdom;
            enemy.takeDamage(amt); p.heal(10);
            typeText("Focus burst deals " + std::to_string(amt) + " damage and restores 10 HP.");
        } else { typeText("Focus is not ready."); }
        return "continue";
    }
    if (choice == "5") { useMasterySkill(p, enemy); return "continue"; }
    // choice == "4"
    if (boss) { p.defense += 3; typeText("You guard. DEF +3."); return "continue"; }
    if (p.run_modifier == "ironwill") { typeText("[Iron Will] You cannot run from battle."); return "continue"; }
    return (randReal() < 0.55) ? "escape" : "continue";
}

// ─────────────────────── ENEMY TURN ──────────────────────────────────────────
void enemyTurn(Fighter& enemy, Player& p) {
    if (enemy.effects.get("freeze") > 0) { typeText(enemy.name + " is frozen and skips the turn."); return; }
    if (p.dodge_next) { p.dodge_next = false; typeText(p.name + " reads the attack and dodges."); return; }
    if (enemy.behavior == "defensive" && randReal() < 0.35) {
        enemy.shield += 10; enemy.effects.set("defense_up", 2);
        typeText(enemy.name + " braces behind a shield."); return;
    }
    if (enemy.behavior == "evasive" && randReal() < 0.30) {
        enemy.effects.set("evasive", 1);
        typeText(enemy.name + " shifts into an evasive stance."); return;
    }
    double dodge_chance = std::min(0.35, p.spd * 0.02 + p.streak * 0.003);
    if (randReal() < dodge_chance) { typeText(p.name + " dodges."); return; }

    int hits = (enemy.behavior == "aggressive") ? 2 : 1;
    for (int h = 0; h < hits; ++h) {
        if (!p.alive()) return;
        auto [amount, crit] = calcDamage(enemy, p);
        if (hits == 2) amount = std::max(1, amount / 2);
        p.takeDamage(amount);
        typeText(enemy.name + " hits for " + std::to_string(amount) + " damage." +
                 (crit ? " Critical!" : ""));
    }
}

// ─────────────────────── BESTIARY ────────────────────────────────────────────
void recordBestiary(RunState& state, const std::string& ename, bool killed = false) {
    auto& entry = state.bestiary[ename];
    if (!killed) entry["seen"]++;
    else         entry["kills"]++;
}

// ─────────────────────── EXP ─────────────────────────────────────────────────
void gainExp(Player& p, int amount) {
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
    Fighter enemy = enemyFor(tier, elite, boss);
    recordBestiary(state, enemy.name);
    clearScreen();
    loading("Entering encounter");
    divider("Encounter");
    flashMessage(enemy.name + " appears!", boss || elite ? 3 : 2);

    if (std::find(p.skills.begin(), p.skills.end(), "TF") != p.skills.end()) {
        p.shield += 5; typeText("[Truth Guard] Battle shield +5.");
    }
    if (std::find(p.skills.begin(), p.skills.end(), "FB") != p.skills.end()) {
        p.streak_guard = true;
    }

    int phase = 1;
    while (p.alive() && enemy.alive()) {
        if (boss) {
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
        tickEffects(enemy);
        tickEffects(p);
    }

    if (p.alive()) {
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
    divider("Shop");
    auto names = itemNames();
    std::shuffle(names.begin(), names.end(), rng());
    std::vector<const Item*> stock;
    for (int i = 0; i < 3 && i < (int)names.size(); ++i)
        stock.push_back(&ITEMS.at(names[i]));

    while (true) {
        std::cout << "\nGold: " << p.gold << "\n0. Leave\n";
        for (int i = 0; i < (int)stock.size(); ++i)
            std::cout << (i+1) << ". " << stock[i]->name << " - " << stock[i]->price << "g\n";
        std::string choice = askRaw("> ");
        if (toLower(choice) == "0" || toLower(choice) == "leave") return;
        if (!choice.empty() && std::all_of(choice.begin(), choice.end(), ::isdigit)) {
            int n = std::stoi(choice);
            if (n >= 1 && n <= (int)stock.size()) {
                const Item* item = stock[n-1];
                if (p.gold >= item->price) {
                    p.gold -= item->price;
                    p.inventory.push_back(item->name);
                    typeText("Bought " + item->name + ".");
                } else { typeText("Not enough gold."); }
                continue;
            }
        }
        typeText("Invalid choice.");
    }
}

void trial(Player& p, LearningEngine& engine) {
    divider("Knowledge Trial");
    typeText("Answer 3 questions. Correct answers give rewards.");
    int correct = 0;
    for (int i = 0; i < 3; ++i) {
        auto [ok, _] = askQuestion(engine, p);
        if (ok) correct++;
    }
    int ex = correct * 20, gld = correct * 10;
    gainExp(p, ex);
    p.gold += gld;
    typeText("Trial complete: +" + std::to_string(ex) + " EXP, +" + std::to_string(gld) + " gold.");
}

void rest(Player& p) {
    int amount = std::max(10, p.max_hp / 3);
    if (std::find(p.skills.begin(), p.skills.end(), "ID") != p.skills.end())
        amount += p.mastery.at("ID");
    animatedBar("Before rest", p.hp, p.max_hp);
    p.heal(amount);
    sleepMs(250);
    animatedBar("After rest", p.hp, p.max_hp);
    typeText("You rest and recover " + std::to_string(amount) + " HP.");
}

// ─────────────────────── ACHIEVEMENTS ────────────────────────────────────────
void awardAchievement(RunState& s, const std::string& name) {
    if (std::find(s.achievements.begin(), s.achievements.end(), name) == s.achievements.end()) {
        s.achievements.push_back(name);
        typeText("*** Achievement unlocked: " + name + " ***");
    }
}
void checkAchievements(Player& p, RunState& s) {
    if (s.battles_won >= 1) awardAchievement(s, "First Victory");
    if (s.nodes >= 5)       awardAchievement(s, "Node Walker");
    if (s.elites_won >= 1)  awardAchievement(s, "Elite Breaker");
    if (p.best_streak >= 10)awardAchievement(s, "Scholar Streak");
    for (auto& [k, v] : p.mastery) if (v >= 10) { awardAchievement(s, "Master Student"); break; }
    if (s.boss_won)         awardAchievement(s, "Boss Clear");
}

// ─────────────────────── RANDOM EVENTS ───────────────────────────────────────
void randomEvent(Player& p) {
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
    std::cout << "\n=== Bestiary ===\n";
    if (s.bestiary.empty()) std::cout << "No enemies recorded yet.\n";
    for (auto& [name, data] : s.bestiary)
        std::cout << name << ": seen " << data["seen"] << ", defeated " << data["kills"] << '\n';
    pause();
}

void viewAchievements(RunState& s) {
    std::cout << "\n=== Achievements ===\n";
    for (auto& [name, desc] : ACHIEVEMENTS) {
        bool unlocked = std::find(s.achievements.begin(), s.achievements.end(), name) != s.achievements.end();
        std::cout << "[" << (unlocked ? "X" : " ") << "] " << name << " - " << desc << '\n';
    }
    pause();
}

// ─────────────────────── MAP / NODE ──────────────────────────────────────────
std::string drawMap(const RunState& s) {
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
    std::vector<std::string> types = {"battle","elite","shop","trial","rest"};
    if (s.tier >= 3 && s.nodes >= 10) types.push_back("boss");
    std::shuffle(types.begin(), types.end(), rng());
    int count = randInt(2, 3);
    types.resize(std::min(count, (int)types.size()));
    return types;
}

void quickStatus(const Player& p, const RunState& s) {
    std::cout << p.name << " | HP " << p.hp << "/" << p.max_hp
              << " | Lv " << p.level << " | Gold " << p.gold
              << " | Tier " << s.tier << " Node " << s.nodes << '\n';
}

// ─────────────────────── SAVE / LOAD (simple text format) ────────────────────
// We use a hand-rolled key=value format to avoid external JSON deps.

void saveGame(const Player& p, const RunState& s, bool quiet = false) {
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
    std::vector<std::string> out;
    std::istringstream ss(s);
    std::string tok;
    while (std::getline(ss, tok, delim)) out.push_back(trim(tok));
    return out;
}

bool loadGame(Player& p, RunState& s) {
    std::ifstream f(SAVE_FILE);
    if (!f) { typeText("No save file found."); return false; }
    // Reset
    p = Player("Hero", 60, 10, 4, 5, 0.10);
    s = RunState();
    std::string line;
    while (std::getline(f, line)) {
        line = trim(line);
        auto eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string key = trim(line.substr(0, eq));
        std::string val = trim(line.substr(eq + 1));
        if (key == "name")         p.name = val;
        else if (key == "class_name")   p.class_name = val;
        else if (key == "passive")      p.passive = val;
        else if (key == "run_modifier") p.run_modifier = val;
        else if (key == "max_hp")   p.max_hp = std::stoi(val);
        else if (key == "hp")       p.hp = std::stoi(val);
        else if (key == "atk")      p.atk = std::stoi(val);
        else if (key == "defense")  p.defense = std::stoi(val);
        else if (key == "spd")      p.spd = std::stoi(val);
        else if (key == "crit")     p.crit = std::stod(val);
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
            if (!val.empty()) for (auto& s2 : splitStr(val, ',')) if (!s2.empty()) p.inventory.push_back(s2);
        } else if (key == "skills") {
            p.skills.clear();
            if (!val.empty()) for (auto& s2 : splitStr(val, ',')) if (!s2.empty()) p.skills.push_back(s2);
        } else if (key.substr(0, 8) == "mastery_") {
            std::string qt = key.substr(8);
            p.mastery[qt] = std::stoi(val);
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
    std::cout << "\n=== Help / Controls ===\n"
              << "Title Menu: 1=new, 2=load, 3=practice, 4=achievements, 5=settings, 6=help, 7=exit.\n"
              << "Node Menu: choose a path number, or c=character, i=inventory,\n"
              << "  b=bestiary, a=achievements, t=settings, s=save, q=save&quit.\n"
              << "Combat: answer questions to attack, use items, spend focus, or mastery skills.\n"
              << "Tip: mastery skills unlock at 5 correct answers in a question type.\n";
    pause();
}

void setTextSpeed() {
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
    clearScreen();
    std::cout << TITLE_ART << '\n';
    typeText("        A C++ Educational RPG - Console Build", 0.01);
    typeText("        Answer. Battle. Learn. Survive the node path.", 0.01);
    std::cout << std::string(78, '=') << '\n';
}

std::string titleMenu(LearningEngine& engine) {
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
    while (true) {
        auto nodes = makeNodes(s);
        divider("Tier " + std::to_string(s.tier) + " | Node " + std::to_string(s.nodes));
        quickStatus(p, s);
        // animate map
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
        s.tier = std::min(3, s.tier + 1);
        typeText("\nTier increased to " + std::to_string(s.tier) + ".");
    }
    p.heal(std::max(1, p.max_hp / 20));
    randomEvent(p);
    checkAchievements(p, s);
    saveGame(p, s, true);
    return true;
}

// ─────────────────────── RUN SUMMARY ─────────────────────────────────────────
void printRunSummary(const Player& p, const RunState& s, const LearningEngine& engine) {
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
    SetConsoleOutputCP(CP_UTF8);
#endif
    showTitle();
    LearningEngine engine;
    engine.loadAll();

    std::string choice = titleMenu(engine);
    if (choice == "7") return 0;

    Player player;
    RunState state;
    bool loaded = false;
    if (choice == "2") loaded = loadGame(player, state);
    if (loaded) {
        typeText("Save loaded.");
    } else {
        player = newPlayer();
        state  = RunState();
        chooseRunModifier(player);
    }

    bool alive = true;
    bool savedAndQuit = false;
    while (alive) {
        std::string node = chooseNode(state, player);
        alive = runNode(player, engine, state, node);
        if (node == "quit") { savedAndQuit = true; break; }
        if (node == "boss" && alive) break;
    }

    if (savedAndQuit) typeText("Saved. See you next run.");
    else printRunSummary(player, state, engine);
    return 0;
}