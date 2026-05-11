# Game-On Learning 🎮📚

> A turn-based educational RPG where you battle enemies by answering questions from your own study notes.
> Answer correctly to attack. Answer wrong and take the hit.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Versions](#project-versions)
- [Python Version — Setup](#python-version--setup)
- [C++ Version — Setup](#c-version--setup)
- [Question File Format](#question-file-format)
- [Gameplay Guide](#gameplay-guide)
- [Classes & Modifiers](#classes--modifiers)
- [Project Structure](#project-structure)
- [Tips](#tips)

---

## Overview

Game-On Learning is a roguelite RPG built around active recall. Instead of pressing an attack button, you answer questions from your own study notes to deal damage, gain streak bonuses, and unlock passive skills. The harder the question type, the higher the difficulty — and the greater the reward.

The game supports six question formats, a node-based run map with shops, trials, rest stops, elite encounters, and a multi-phase boss fight.

---

## Features

- **Six question types** — True/False, Multiple Choice, Arithmetic, Identification, Fill in the Blanks, Ordering
- **Turn-based combat** — answer questions to attack; wrong answers trigger enemy counter-attacks
- **Streak system** — consecutive correct answers boost damage, dodge chance, and shop discounts
- **Mastery skills** — reach 5 correct answers in a type to unlock a passive ability for that category
- **Node map** — choose your own path through battles, elites, shops, rest nodes, trials, and a final boss
- **Four classes** — Berserker, Duelist, Arcanist, Sentinel, each with a unique passive
- **Run modifiers** — optional challenge rules (Scholar's Burden, Cursed Knowledge, Iron Will)
- **Save/load** — run progress is autosaved after every node
- **Bestiary & achievements** — track every enemy you've encountered and defeated

---

## Project Versions

| Version | Language | File(s) | Best for |
|---|---|---|---|
| Full | Python | Multiple modules (`main.py`, `combatSystem.py`, etc.) | Feature-complete with GUI support |
| Compact | Python | `gol_compact.py` (single file) | Clean reference; easy to read and modify |
| C++ | C++ | `main.cpp` (single file) | Console build; portable; no dependencies |

All three versions share the same question file format and core gameplay systems.

---

## Python Version — Setup

### Requirements

- Python **3.10 or higher**
- No external packages required — standard library only

Check your version:
```bash
python --version
```

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/your-username/game-on-learning.git
cd game-on-learning
```

**2. Create your `notes/` folder and add question files**

The game looks for question files inside a `notes/` folder next to the script.
See [Question File Format](#question-file-format) for how to write them.

```
game-on-learning/
├── gol_compact.py
└── notes/
    ├── TorF.txt
    ├── MCQ.txt
    ├── Math.txt
    ├── Identify.txt
    ├── FillBlanks.txt
    └── OD.txt
```

**3. Configure the note file paths**

Open `gol_compact.py` and find the `Q_FILES()` function near the top. Update the paths to match your folder layout:

```python
def Q_FILES():
    return {
        "TF": "notes/TorF.txt",
        "MC": "notes/MCQ.txt",
        "AR": "notes/Math.txt",
        "ID": "notes/Identify.txt",
        "FB": "notes/FillBlanks.txt",
        "OD": "notes/OD.txt",
    }
```

You can skip any question type by removing its entry — the engine will warn you it is missing but continue loading the rest.

**4. Run the game**
```bash
python gol_compact.py
```

---

### Running the Full Multi-Module Version

The full version (`main.py`) uses multiple modules. Run it from the project root:

```bash
python main.py
```

On first launch a setup wizard will ask you to locate each question file interactively. The paths are saved to `config.json` and reused on future runs.

To re-run the wizard at any time (e.g. to point to new notes):
```bash
# Windows
del config.json

# Linux / macOS
rm config.json

python main.py
```

---

## C++ Version — Setup

### Requirements

A C++17-compatible compiler. Pick the one that matches your system:

| System | Recommended compiler | How to get it |
|---|---|---|
| Windows | MinGW-w64 (`g++`) | [winlibs.com](https://winlibs.com/) or install via [MSYS2](https://www.msys2.org/) |
| Windows | MSVC | Install [Visual Studio](https://visualstudio.microsoft.com/) with the "Desktop development with C++" workload |
| Linux | `g++` | `sudo apt install g++` (Ubuntu/Debian) or equivalent |
| macOS | `clang++` | Run `xcode-select --install` in Terminal |

No external libraries are needed. Everything uses the C++ standard library.

**Verify you have a compiler:**
```bash
g++ --version
# or
clang++ --version
```

---

### Step 1 — Clone the repository

```bash
git clone https://github.com/your-username/game-on-learning.git
cd game-on-learning/cpp
```

---

### Step 2 — Linux / macOS only: fix the screen-clear call

Open `main.cpp` and find the `clearScreen()` function (around line 72).

Change:
```cpp
inline void clearScreen() { std::system("cls"); }
```
To:
```cpp
inline void clearScreen() { std::system("clear"); }
```

Windows users leave it as `"cls"`.

---

### Step 3 — Compile

**Linux / macOS (`g++` or `clang++`)**
```bash
g++ -std=c++17 -O2 -o gol main.cpp
```

**Windows — MinGW / g++ (run in a regular terminal or MSYS2)**
```bash
g++ -std=c++17 -O2 -o gol.exe main.cpp
```

**Windows — MSVC (run in a Visual Studio Developer Command Prompt)**
```
cl /std:c++17 /EHsc /O2 main.cpp /Fe:gol.exe
```

A successful compile produces no errors. One harmless warning about the return value of `system()` may appear — it is safe to ignore.

> ⚠️ The `-std=c++17` flag is required. The code uses structured bindings (`auto [ok, type] = ...`) which are a C++17 feature and will not compile on C++14 or earlier.

---

### Step 4 — Add your question files

Create a `notes/` folder next to the compiled binary and place your question files inside it:

```
cpp/
├── main.cpp
├── gol.exe          ← Windows binary
├── gol              ← Linux/macOS binary
└── notes/
    ├── TorF.txt
    ├── MCQ.txt
    ├── Math.txt
    ├── Identify.txt
    ├── FillBlanks.txt
    └── OD.txt
```

The file paths are defined in the `Q_FILES()` function inside `main.cpp`. Edit them if your layout is different:

```cpp
inline std::map<std::string,std::string> Q_FILES() {
    return {
        {"TF", "notes/TorF.txt"},
        {"MC", "notes/MCQ.txt"},
        {"AR", "notes/Math.txt"},
        {"ID", "notes/Identify.txt"},
        {"FB", "notes/FillBlanks.txt"},
        {"OD", "notes/OD.txt"},
    };
}
```

---

### Step 5 — Run

**Linux / macOS:**
```bash
./gol
```

**Windows:**
```bash
gol.exe
```

---

## Question File Format

All question files are plain `.txt` files — one question per line. Blank lines are ignored. You can use any subject matter.

---

### True / False — `TorF.txt`

```
The mitochondria is the powerhouse of the cell = True
Sound travels faster than light = False
The Great Wall of China is visible from space = False
Water boils at 100 degrees Celsius at sea level = True
```

Format: `Question text = True` or `Question text = False`

---

### Multiple Choice — `MCQ.txt`

Each line is a single JSON object on one line:

```json
{"question":"What is the powerhouse of the cell?","options":["Nucleus","Mitochondria","Ribosome","Golgi body"],"answer":"Mitochondria"}
{"question":"Which planet is closest to the Sun?","options":["Venus","Earth","Mercury","Mars"],"answer":"Mercury"}
{"question":"What does CPU stand for?","options":["Central Processing Unit","Computer Personal Unit","Core Processing Utility","Central Program Uplink"],"answer":"Central Processing Unit"}
```

> ⚠️ The `answer` value must exactly match one of the strings in `options`, including capitalisation.

---

### Arithmetic / Short Answer — `Math.txt`

```
What is 12 x 8 = 96
Solve for x: 2x + 4 = 12 = 4
Square root of 144 = 12
What is 15% of 200 = 30
```

Format: `Question = Answer`

---

### Identification — `Identify.txt`

```
Who wrote Romeo and Juliet = Shakespeare
What element has the symbol Au = Gold
The study of fungi is called = Mycology
Who painted the Mona Lisa = Leonardo da Vinci
```

Format: `Question = Answer`

---

### Fill in the Blanks — `FillBlanks.txt`

```
The process by which plants convert sunlight to food is called _______ = Photosynthesis
Newton's first law is also known as the law of _______ = Inertia
The speed of light is approximately _______ km/s = 300000
```

Format: `Statement with blank = Answer` — the blank can be written any way you like; only the part after `=` is checked.

---

### Ordering — `OD.txt`

Each line is a single JSON object. The `answer` field contains the **1-based indices** of `items` in the correct order:

```json
{"question":"Order these planets by distance from the Sun (nearest first)","items":["Earth","Mars","Mercury","Venus"],"answer":"3,4,1,2"}
{"question":"Order the steps of the scientific method","items":["Hypothesis","Observation","Experiment","Conclusion"],"answer":"2,1,3,4"}
```

**How to write the answer:**

Given `"items":["Earth","Mars","Mercury","Venus"]`, the items are numbered:
- 1 = Earth
- 2 = Mars
- 3 = Mercury
- 4 = Venus

Correct order (nearest to farthest from Sun) is Mercury, Venus, Earth, Mars → indices `3,4,1,2`.

---

## Gameplay Guide

### Combat Loop

On your turn you choose one of:

| Option | AP Cost | Effect |
|---|---|---|
| **Answer / Attack** | 1 AP | Answer a question. Correct = deal damage to enemy. Wrong = enemy hits back and streak is halved. |
| **Use Item** | 1 AP | Use a consumable from your inventory. |
| **Focus Skill** | Free (bar must be full) | Burst attack + small self-heal. Empties the Focus bar. |
| **Mastery Skill** | Free | Actively trigger an unlocked skill effect. |
| **Run** | Free | 55% chance to escape. Costs gold and halves streak on success. |

After your turn the enemy acts based on its behavior pattern (aggressive, defensive, evasive, neutral).

---

### Streak

Consecutive correct answers build your streak. Streak bonus effects:

- **Damage** — each streak point adds a small flat bonus to attack
- **Dodge** — higher streak slightly increases your dodge chance (capped at 25%)
- **Shop discount** — every 5 streak = 1% discount at the shop (capped at 25% off)

A wrong answer **halves** your streak (rounded down). The **Composure** mastery skill (Fill in the Blanks) protects it once per battle.

---

### Focus Bar

Fills by 10–15 points per correct answer (scales with Wisdom stat). At 100 you can use a **Focus Burst**:
- Deals 2× ATK + Wisdom as damage
- Restores 10 HP
- Resets the bar to 0

---

### Mastery Skills

Answer 5 questions correctly in any category to permanently unlock that skill for the rest of the run:

| Category | Skill | Effect |
|---|---|---|
| True / False | **Truth Guard** | Start every battle with +5 shield |
| Multiple Choice | **Eliminate One** | Automatically remove one wrong MC option before the question displays |
| Arithmetic | **Precision** | Actively deal bonus damage equal to 10 + AR mastery |
| Identification | **Recall** | Actively heal for 12 + ID mastery HP |
| Fill in the Blanks | **Composure** | Once per battle, a wrong answer will not halve your streak |
| Ordering | **Tactical Read** | After a correct OD answer, 25% chance to pre-dodge the next enemy hit |

---

### Node Map

You choose your path at each step. Available node types:

| Icon | Type | What happens |
|---|---|---|
| `[B]` | **Battle** | Fight a random enemy scaled to the current tier |
| `[E]` | **Elite** | Tougher enemy with phase shifts; win for permanent Max HP +5 |
| `[S]` | **Shop** | Spend gold on items (3 random items in stock) |
| `[T]` | **Trial** | Answer 3 questions for EXP and gold rewards |
| `[R]` | **Rest** | Recover 30% of your max HP |
| `[!]` | **Boss** | Multi-phase boss; every action requires a correct question answer |

The run tier increases every 5 nodes (max tier 3, enemies scale up). The boss is guaranteed at **node 15**.

---

## Classes & Modifiers

### Classes

| Class | HP | ATK | DEF | SPD | WIS | Passive |
|---|---|---|---|---|---|---|
| **Berserker** | 70 | 14 | 5 | 4 | 5 | **Bloodlust** — each correct answer permanently raises ATK by 1, up to +10 |
| **Duelist** | 55 | 11 | 4 | 9 | 5 | **Momentum** — correct answers add a one-time +20% crit chance to the next strike |
| **Arcanist** | 50 | 9 | 4 | 5 | 25 | **Insight** — gains extra Focus per correct answer; high Wisdom amplifies all damage |
| **Sentinel** | 90 | 9 | 9 | 2 | 5 | **Fortress** — wrong answers grant +8 shield instead of triggering a punishment attack |

---

### Run Modifiers

Chosen once at the start of each run. All are optional — pick Standard for a normal experience.

| Modifier | Effect |
|---|---|
| **Standard Run** | No changes |
| **Scholar's Burden** | Correct attacks deal **2× damage**, but question difficulty is weighted harder |
| **Cursed Knowledge** | Wrong answers also cost **10 HP** on top of the streak penalty |
| **Iron Will** | You **cannot escape** any battle; all combat rewards are **1.5× higher** |

---

## Project Structure

### Python — Compact (single file)
```
gol_compact.py         Main script — all systems in one file
notes/                 Your question files
save.json              Created automatically on first save
```

### Python — Full (multi-module)
```
main.py                Entry point and game loop
combatSystem.py        Turn-based combat logic and player/enemy turns
combatCalc.py          Damage, dodge, and critical hit formulas
learningEngine.py      Question loading, parsing, and quiz presentation
enemyPool.py           Enemy templates and stat scaling
Spawns.py              Player (MainCharacter) and Enemy classes
items.py               All consumable items
shop.py                Merchant and selling system
statusEffects.py       Buffs and debuffs (Poison, Freeze, AttackBuff, etc.)
progression.py         Mastery tracking, skill unlocks, levelling
saveLoad.py            Save and load game state to JSON
config.py              First-time setup wizard and config file management
ui.py                  I/O helpers, EventBus, and terminal/GUI output layer
achievements.py        Achievement definitions and unlock checks
bestiary.py            Enemy encounter and kill log
narrative.py           Flavor text for nodes, streaks, and deaths
tutorial.py            New player tutorial sequence
notes/                 Your question files
config.json            Created on first run by the setup wizard
savegame.json          Created automatically on first save
```

### C++ — Single file
```
main.cpp               Everything in one file (~900 lines, C++17)
notes/                 Your question files
save.json              Created automatically on first save
gol.exe / gol          Compiled binary
```

---

## Tips

- **Missed questions are weighted 3×** — the engine shows you questions you got wrong more often until you answer them correctly.
- **Keep your streak before shopping** — at streak 25+ you get a meaningful discount at the shop (caps at 25% off).
- **Bring Hint Potions to the boss** — every boss action requires a difficulty-3 question. Hints make them survivable.
- **Elite fights escalate** — elites gain ATK at 66% HP and DEF at 33% HP. Burst them down before the third phase if possible.
- **Sentinel + Iron Will** — the tankiest combination. You cannot run but your high DEF and Fortress passive let you absorb punishments while grinding mastery.
- **Arcanist snowballs** — high Wisdom means the damage and focus formulas both scale hard with correct answers. It is the slowest starter but the strongest finisher.
- **Check your wrong answers at the end of a run** — the run summary lists every question you missed. Use it to update your notes.

---

## License

MIT License — free to use, modify, and distribute for personal or educational purposes.

---

## Contributing

Pull requests are welcome.

If you add a new question type:
1. Add the file path to `Q_FILES()` in both the Python and C++ versions
2. Add a parser branch to `LearningEngine.load_file()` (Python) and `LearningEngine::loadFile()` (C++)
3. Add the format to this README under [Question File Format](#question-file-format)
