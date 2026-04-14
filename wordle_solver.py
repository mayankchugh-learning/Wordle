"""
Votee Wordle Solver
====================
Automatically solves Wordle puzzles via the Votee API.
API: https://wordle.votee.dev:8000

Endpoints used:
  GET /random?guess=WORD&seed=42   — guess against a random word
  GET /daily?guess=WORD            — guess against today's daily word
  GET /word/{target}?guess=WORD    — guess against a specific word

Author: Mayank Chugh
"""

import requests
import urllib.request
import sys
from collections import Counter


def _stdout_accepts_unicode() -> bool:
    """True if stdout can encode emoji; False for cp1252 etc. (use ASCII fallback)."""
    stream = sys.stdout
    if stream is None:
        return False
    enc = getattr(stream, "encoding", None)
    if not enc:
        return False
    enc_l = enc.lower()
    if enc_l in ("utf-8", "utf8"):
        return True
    try:
        "\U0001f7e9\U0001f7e8\u2b1b\u2705\u274c".encode(enc)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


_USE_UNICODE = _stdout_accepts_unicode()


# ── CONFIG ──────────────────────────────────────────────────────────────────
BASE_URL = "https://wordle.votee.dev:8000"
WORD_SIZE = 5
MAX_GUESSES = 6

# Best opening words — chosen for maximum letter coverage
OPENING_WORDS = ["crane", "lousy", "might"]


# ── LOAD WORD LIST ───────────────────────────────────────────────────────────
def load_words():
    """
    Load 5-letter English words.
    First tries local system dictionary,
    then downloads from GitHub if not available (Windows).
    """
    # Try system dictionary (Mac/Linux)
    try:
        with open("/usr/share/dict/words", "r") as f:
            words = [
                w.strip().lower() for w in f
                if len(w.strip()) == WORD_SIZE
                and w.strip().isalpha()
                and w.strip().isascii()
            ]
            if words:
                print(f"Dictionary loaded from system: {len(words)} words")
                return words
    except FileNotFoundError:
        pass

    # Download and merge multiple online lists for better API coverage.
    print("Downloading word lists...")
    urls = [
        "https://raw.githubusercontent.com/tabatkins/wordle-list/main/words",
        "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt",
    ]
    merged = set()
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                content = response.read().decode()
                downloaded = {
                    w.strip().lower() for w in content.splitlines()
                    if len(w.strip()) == WORD_SIZE
                    and w.strip().isalpha()
                }
                merged.update(downloaded)
                print(f"Loaded {len(downloaded)} words from: {url}")
        except Exception as e:
            print(f"Download failed for {url}: {e}")

    if merged:
        words = sorted(merged)
        print(f"Merged dictionary loaded: {len(words)} words")
        return words

    # Last resort — hardcoded common words
    words = [
        "crane", "slate", "audio", "raise", "stare", "arose", "least",
        "snare", "tried", "storm", "light", "house", "place", "round",
        "found", "sound", "group", "plant", "point", "right", "study",
        "still", "learn", "world", "every", "great", "never", "those",
        "small", "large", "often", "might", "after", "think", "heart"
    ]
    print(f"Using fallback list: {len(words)} words")
    return words


# ── API CALLS ────────────────────────────────────────────────────────────────
def guess_random(guess, seed=42):
    """Guess against a random word (fixed by seed)."""
    url = f"{BASE_URL}/random"
    params = {"guess": guess.lower(), "seed": seed, "size": WORD_SIZE}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def guess_daily(guess):
    """Guess against today's daily word."""
    url = f"{BASE_URL}/daily"
    params = {"guess": guess.lower(), "size": WORD_SIZE}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def guess_word(target, guess):
    """Guess against a specific known word (for testing)."""
    url = f"{BASE_URL}/word/{target}"
    params = {"guess": guess.lower()}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


# ── FILTER WORD LIST ─────────────────────────────────────────────────────────
def evaluate_guess(guess, target):
    """
    Return Wordle feedback results for a guess against a target.
    Handles duplicate letters with standard two-pass logic.
    """
    guess = guess.lower()
    target = target.lower()

    results = ["absent"] * WORD_SIZE
    remaining = Counter(target)

    # Pass 1: mark correct letters and consume them.
    for i, letter in enumerate(guess):
        if letter == target[i]:
            results[i] = "correct"
            remaining[letter] -= 1

    # Pass 2: mark present letters where counts remain.
    for i, letter in enumerate(guess):
        if results[i] != "absent":
            continue
        if remaining[letter] > 0:
            results[i] = "present"
            remaining[letter] -= 1

    return results


def filter_words(words, feedback):
    """
    Keep only words that would produce the exact same feedback pattern.
    This is the most reliable way to handle duplicate-letter cases.
    """
    ordered = sorted(feedback, key=lambda x: x["slot"])
    guess = "".join(item["guess"].lower() for item in ordered)
    expected = [item["result"] for item in ordered]
    return [word for word in words if evaluate_guess(guess, word) == expected]


# ── PICK BEST GUESS ──────────────────────────────────────────────────────────
def get_cluster_signature(words):
    """
    Detect near-identical candidate clusters.
    Returns (fixed_positions, varying_positions) when 4+ positions are fixed.
    """
    if not words:
        return None

    fixed_positions = {}
    varying_positions = {}
    for idx in range(WORD_SIZE):
        chars = {word[idx] for word in words}
        if len(chars) == 1:
            fixed_positions[idx] = next(iter(chars))
        else:
            varying_positions[idx] = chars

    if len(fixed_positions) >= 4 and varying_positions:
        return fixed_positions, varying_positions
    return None


def pick_best_guess(words, attempt, guessed, all_words=None):
    # Fixed opening word for attempt 1
    if attempt == 0:
        return "crane" if "crane" in words else words[0]

    if not words:
        return None

    # From attempt 2 onward, guesses must come strictly from candidates.
    candidate_pool = [w for w in words if w not in guessed]
    if not candidate_pool:
        candidate_pool = words
    if len(candidate_pool) == 1:
        return candidate_pool[0]

    # Base score: favor guesses with high unique-letter coverage
    letter_freq = {}
    for word in words:
        for letter in set(word):
            letter_freq[letter] = letter_freq.get(letter, 0) + 1

    def coverage_score(word):
        unique_bonus = 5 if len(set(word)) == len(word) else 0
        return sum(letter_freq.get(l, 0) for l in set(word)) + unique_bonus

    # Sacrifice guess strategy:
    # For 4+ fixed-letter clusters, play one high-information probe outside
    # candidates to collapse the cluster quickly.
    if len(words) <= 10 and attempt < (MAX_GUESSES - 1) and all_words:
        cluster = get_cluster_signature(words)
        if cluster:
            _, varying_positions = cluster
            differing_letters = set().union(*varying_positions.values())
            sacrifice_pool = [
                w for w in all_words
                if w not in words and w not in guessed
            ]

            if sacrifice_pool:
                def sacrifice_score(word):
                    letters = set(word)
                    overlap = len(letters & differing_letters)
                    positional_hits = sum(
                        1 for idx, chars in varying_positions.items()
                        if word[idx] in chars
                    )
                    return (overlap, positional_hits, coverage_score(word))

                best_sacrifice = max(sacrifice_pool, key=sacrifice_score)
                if len(set(best_sacrifice) & differing_letters) > 0:
                    return best_sacrifice

    # Endgame strategy: when few candidates remain, choose the word that best
    # overlaps with the whole candidate pool while still favoring frequent letters.
    if len(words) <= 10:
        def endgame_score(word):
            word_letters = set(word)
            shared_letters = sum(
                len(word_letters & set(candidate))
                for candidate in words
            )
            frequency_score = sum(letter_freq.get(letter, 0) for letter in word_letters)
            return (shared_letters, frequency_score, coverage_score(word))

        return max(candidate_pool, key=endgame_score)

    # For early/mid game on a narrowed list, maximize partition diversity.
    # This improves attempt 2/3 quality while still guessing from candidates only.
    if len(words) <= 200:
        def partition_score(guess):
            buckets = {}
            for target in words:
                pattern = tuple(evaluate_guess(guess, target))
                buckets[pattern] = buckets.get(pattern, 0) + 1
            # Better split => lower worst bucket and lower expected bucket size
            worst_bucket = max(buckets.values())
            expected_bucket = sum(v * v for v in buckets.values()) / len(words)
            return (-worst_bucket, -expected_bucket, coverage_score(guess))

        return max(candidate_pool, key=partition_score)

    return max(candidate_pool, key=coverage_score)

# ── DISPLAY HELPERS ──────────────────────────────────────────────────────────
def feedback_to_display(feedback):
    """Convert feedback to a row of symbols (emoji on UTF-8 consoles, ASCII otherwise)."""
    if _USE_UNICODE:
        sym = {"correct": "🟩", "present": "🟨", "absent": "⬛"}
    else:
        sym = {"correct": "G", "present": "Y", "absent": "."}
    return "".join(
        sym[item["result"]]
        for item in sorted(feedback, key=lambda x: x["slot"])
    )


# ── MAIN SOLVER ──────────────────────────────────────────────────────────────
def solve(mode="random", seed=42, target=None):
    """
    Main solving loop.

    Args:
        mode:   "random" | "daily" | "word"
        seed:   integer seed for /random mode (keeps same word across runs)
        target: specific word for /word mode
    """
    if _USE_UNICODE:
        print(f"\n🟩 Votee Wordle Solver")
    else:
        print("\n== Votee Wordle Solver ==")
    print(f"   Mode: {mode.upper()}" + (f" | Seed: {seed}" if mode == "random" else ""))
    print("=" * 45)

    all_words = load_words()
    candidates = all_words.copy()
    guessed = []
    solved = False

    for attempt in range(MAX_GUESSES):
        if not candidates:
            # Fallback recovery: broaden search instead of giving up.
            if _USE_UNICODE:
                print("⚠️  Candidates dropped to 0 — resetting to full dictionary fallback.")
            else:
                print("[!] Candidates dropped to 0 — resetting to full dictionary fallback.")
            candidates = all_words.copy()

        guess = pick_best_guess(candidates, attempt, guessed, all_words=all_words)
        guessed.append(guess)

        print(f"\nAttempt {attempt + 1}/{MAX_GUESSES}: Guessing '{guess.upper()}'")

        # Call the right endpoint
        if mode == "random":
            feedback = guess_random(guess, seed=seed)
        elif mode == "daily":
            feedback = guess_daily(guess)
        elif mode == "word":
            feedback = guess_word(target, guess)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        # Show result
        print(f"Result:  {feedback_to_display(feedback)}")

        # Check win
        if all(item["result"] == "correct" for item in feedback):
            if _USE_UNICODE:
                print(f"\n✅ SOLVED in {attempt + 1} guess(es)! Word: '{guess.upper()}'")
            else:
                print(f"\n[OK] SOLVED in {attempt + 1} guess(es)! Word: '{guess.upper()}'")
            solved = True
            break

        # Filter candidates
        candidates = filter_words(candidates, feedback)
        print(f"Remaining candidates: {len(candidates)}")
        if 0 < len(candidates) <= 10:
            print(f"Top candidates: {candidates[:10]}")

    if not solved:
        if _USE_UNICODE:
            print(f"\n❌ Could not solve in {MAX_GUESSES} guesses.")
        else:
            print(f"\n[X] Could not solve in {MAX_GUESSES} guesses.")

    return solved


# ── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Default: solve a random word with seed 42
    # You can change mode and seed here

    # Solve random word (same word each run with same seed)
    solve(mode="random", seed=42)

    # Uncomment to solve today's daily puzzle:
    # solve(mode="daily")

    # Uncomment to solve a specific known word (for testing):
    # solve(mode="word", target="crane")