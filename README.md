# Votee Wordle Solver

**Candidate:** Mayank Chugh  
**Role:** Forward Deployed Engineer (AI & Infrastructure) [VT26-FDE] [Hong Kong] [Full Time]  
**Submitted to:** jacky@votee.com  

---

## What This Is

A Python program that automatically solves Wordle puzzles by connecting to the Votee API. The solver makes intelligent guesses, reads the feedback from the API, eliminates impossible words, and repeats until it finds the answer — typically in 3 to 5 guesses.

---

## How Wordle Works

Wordle is a word guessing game. There is a secret 5-letter word. You have 6 attempts to guess it. After each guess, the game tells you:

- 🟩 **Correct** — right letter, right position
- 🟨 **Present** — right letter, wrong position
- ⬛ **Absent** — letter not in the word at all

Example: Secret word is **WROTE**
- You guess **CRANE** → ⬛🟩⬛⬛🟩
- Meaning: C=no, R=yes at position 2, A=no, N=no, E=yes at position 5

---

## How the Solver Works — 4 Steps

```
Step 1: Load ~16,000 five-letter English words (the candidate pool)

Step 2: Make a guess → send it to the Votee API → receive feedback

Step 3: Filter the candidate pool
        Remove every word that contradicts the feedback
        (e.g. if C is grey, remove all words containing C)

Step 4: Pick the best next guess from remaining candidates
        Repeat from Step 2 until solved or 6 guesses used
```

---

## API Used

**Base URL:** `https://wordle.votee.dev:8000`

| Endpoint | Purpose | Key Parameters |
|---|---|---|
| `GET /random` | Guess against a random word | `guess`, `seed`, `size` |
| `GET /daily` | Guess against today's daily word | `guess`, `size` |
| `GET /word/{word}` | Guess against a specific word | `word` (path), `guess` |

**Response format** (array of per-letter results):
```json
[
  {"slot": 0, "guess": "c", "result": "absent"},
  {"slot": 1, "guess": "r", "result": "correct"},
  {"slot": 2, "guess": "a", "result": "absent"},
  {"slot": 3, "guess": "n", "result": "absent"},
  {"slot": 4, "guess": "e", "result": "correct"}
]
```

---

## Algorithm Design

### Word Filtering (`filter_words`)

The most critical function. After each guess, it removes words that cannot possibly be the answer.

**The three rules applied:**
1. **Correct (green):** the letter MUST appear at this exact position in every remaining candidate
2. **Present (yellow):** the letter MUST appear somewhere in the word, but NOT at this position
3. **Absent (grey):** the letter must NOT appear anywhere in the word

**Key implementation detail — duplicate letter handling:**

Standard approaches fail on words like SPEED (two E's). This solver uses a two-pass evaluation:
- Pass 1: mark all exact position matches (green) and consume those letters
- Pass 2: mark remaining letters as present/absent based on what's left

This matches the official Wordle rules precisely.

**Filtering approach:** Rather than applying rules procedurally, the solver simulates what feedback each candidate word *would* produce if it were the answer, and keeps only words that would produce the exact same feedback pattern as received. This is mathematically equivalent but handles all edge cases cleanly.

### Guess Selection (`pick_best_guess`)

**Attempt 1:** Always guess `CRANE`
- Covers 5 common letters: C, R, A, N, E
- Statistically one of the best opening words

**Attempts 2+:** Score remaining candidates by letter frequency
- Count how often each letter appears across all remaining candidates
- Score each word by the sum of its letters' frequencies
- Prefer words with all unique letters (more information per guess)
- **Always pick from remaining candidates only** — never guess outside the filtered pool

**Endgame strategy (≤10 candidates):** When few candidates remain, score by overlap with the entire candidate pool — pick the word that shares the most letters with all remaining words simultaneously.

**Sacrifice guess strategy:** When candidates form a tight cluster (4+ positions identical, only 1-2 positions varying — e.g. FAINT/SAINT/PAINT/TAINT), the solver plays a word outside the candidate list that covers the maximum number of differing letters. This "sacrifices" one guess to collapse the cluster efficiently.

**Mid-game strategy (≤200 candidates):** Uses partition scoring — simulates the feedback each candidate would produce against all other candidates and picks the guess that creates the most even split (minimises worst-case remaining bucket).

### Word List

Downloads and merges two sources for maximum API coverage:
- Official Wordle word list (tabatkins/wordle-list) — 2,309 real Wordle words
- Extended English word list (dwyl/english-words) — 15,000+ five-letter words
- Merged, deduplicated, sorted — ~16,000 total candidates
- Cached locally as `wordle_words.txt` after first download

---

## Installation

```bash
# Clone the repository
git clone https://github.com/mayankchugh-learning/Wordle.git
cd wordle-votee

# Install dependencies
pip install requests

# Run the solver
python wordle_solver.py
```

**Requirements:**
- Python 3.7+
- `requests` library
- Internet connection (first run downloads word list)

---

## Usage

```python
# Solve a random word (seed fixes the word for reproducible testing)
solve(mode="random", seed=42)

# Solve today's daily puzzle
solve(mode="daily")

# Solve a specific known word (useful for testing)
solve(mode="word", target="crane")
```

**Run multiple seeds from command line:**
```bash
python -c "from wordle_solver import solve; solve(mode='random', seed=1)"
python -c "from wordle_solver import solve; solve(mode='random', seed=7)"
python -c "from wordle_solver import solve; solve(mode='daily')"
```

---

## Test Results

| Mode | Word | Result | Guesses |
|---|---|---|---|
| `seed=42` | WROTE | ✅ Solved | 5 |
| `seed=1` | FIERY | ✅ Solved | 4 |
| `seed=7` | ARSON | ✅ Solved | 4 |
| `seed=99` | CODEX | ✅ Solved | 3 |
| `daily` | (today's word) | tested | varies |

---

## Design Decisions — Why I Built It This Way

**Why CRANE as the opening word?**
CRANE covers 5 high-frequency letters and has no repeated letters. Statistically it eliminates more candidates per guess than most alternatives. Other strong openers (SLATE, AUDIO) were tested — CRANE performed most consistently.

**Why letter frequency scoring instead of pure minimax?**
Minimax (optimise worst-case remaining candidates) is theoretically optimal but computationally expensive. Letter frequency scoring is fast, explainable, and achieves 4-5 guess average in practice. For a Forward Deployed role where I need to explain the solution to clients, simplicity and explainability matter as much as theoretical optimality.

**Why merge two word lists?**
The Votee API uses a word set that doesn't perfectly match any single public list. By merging the official Wordle list with a broader English dictionary, we maximise coverage and avoid candidates dropping to zero mid-game.

**Why a sacrifice guess strategy?**
Tight clusters like FAINT/SAINT/PAINT/TAINT are the hardest Wordle case — all share 4 positions, only position 0 varies. Without a sacrifice, the solver burns 4-5 guesses cycling through candidates. A single sacrifice guess on a word containing F, S, P, T simultaneously collapses the cluster in one move.

**Why candidate-only guessing from attempt 2?**
Early versions sometimes guessed words outside the filtered candidate list. While this can theoretically provide more information, it risks wasting guesses on words that cannot be the answer. Restricting to candidates ensures every guess has a chance of being correct.

---

## File Structure

```
wordle-votee/
├── wordle_solver.py    # Main solver — all logic in one file
├── README.md           # This file
└── wordle_words.txt    # Auto-generated word cache (created on first run)
```

---

## Notes

- The solver runs cleanly on both Windows (cp1252) and Unix (UTF-8) terminals
- On Windows without UTF-8 encoding, emoji automatically fall back to ASCII: G/Y/.
- The `seed` parameter is for testing only — it fixes the random word for reproducibility
- All API calls include a 10-second timeout and proper error handling

---

*Built by Mayank Chugh — Enterprise Architect & AI Engineer*  
*linkedin.com/in/mchugh77 | mayankchugh-learning.github.io*