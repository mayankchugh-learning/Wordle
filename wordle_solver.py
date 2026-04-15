"""
Votee Wordle Solver
====================
Automatically solves Wordle puzzles via the Votee API.
API and word-list sources are configured as constants in this file.

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
import argparse

def _stdout_accepts_unicode() -> bool:
    """
    Check whether the current terminal can print Unicode symbols.

    Inputs:
        None.

    Returns:
        bool: True when stdout encoding can handle emoji/symbol characters,
        False when the terminal uses a limited encoding (for example cp1252).
    """
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
WORD_LIST_URLS = [
    "https://raw.githubusercontent.com/tabatkins/wordle-list/main/words",
    "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt",
]
WORD_SIZE = 5
MAX_GUESSES = 6

# Best opening words — chosen for maximum letter coverage
OPENING_WORDS = ["crane", "lousy", "might"]


# ── LOAD WORD LIST ───────────────────────────────────────────────────────────
def load_words():
    """
    Build the solver dictionary of valid 5-letter words.

    Inputs:
        None. Uses global settings (`WORD_SIZE`, `WORD_LIST_URLS`).

    Returns:
        list[str]: A sorted list of lowercase candidate words.

    Behavior:
        1) Try local system dictionary first.
        2) If unavailable, download and merge online word lists.
        3) If all downloads fail, fall back to a built-in short list.
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
    merged = set()
    for url in WORD_LIST_URLS:
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
    """
    Send one guess to the API random endpoint.

    Inputs:
        guess (str): Proposed 5-letter word.
        seed (int): Seed used by the API so runs are repeatable.

    Returns:
        list[dict]: Feedback records from the API, one per letter slot.
    """
    url = f"{BASE_URL}/random"
    params = {"guess": guess.lower(), "seed": seed, "size": WORD_SIZE}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def guess_daily(guess):
    """
    Send one guess to the API daily endpoint.

    Inputs:
        guess (str): Proposed 5-letter word.

    Returns:
        list[dict]: Feedback records from the API, one per letter slot.
    """
    url = f"{BASE_URL}/daily"
    params = {"guess": guess.lower(), "size": WORD_SIZE}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def guess_word(target, guess):
    """
    Send one guess to the API endpoint for a specific target word.

    Inputs:
        target (str): Explicit answer word used for testing.
        guess (str): Proposed 5-letter word.

    Returns:
        list[dict]: Feedback records from the API, one per letter slot.
    """
    url = f"{BASE_URL}/word/{target}"
    params = {"guess": guess.lower()}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


# ── FILTER WORD LIST ─────────────────────────────────────────────────────────
def evaluate_guess(guess, target):
    """
    Simulate Wordle feedback for a `guess` against a candidate `target`.

    Inputs:
        guess (str): The guessed word.
        target (str): The candidate answer word.

    Returns:
        list[str]: Per-position results using "correct", "present", "absent".

    Key logic:
        - Pass 1 marks exact matches (greens) and consumes letter counts.
        - Pass 2 marks misplaced matches (yellows) only when count remains.
        - This two-pass design prevents duplicate-letter overcounting.
    """
    guess = guess.lower()
    target = target.lower()

    results = ["absent"] * WORD_SIZE
    remaining = Counter(target)

    # Pass 1 (green check):
    # Mark letters that are correct in both character and position.
    # Each green letter consumes one count from `remaining` so it cannot
    # be reused again in pass 2.
    for i, letter in enumerate(guess):
        if letter == target[i]:
            results[i] = "correct"
            remaining[letter] -= 1

    # Pass 2 (yellow check):
    # For letters not already green, mark as "present" only if that letter
    # still has unused occurrences in the target.
    for i, letter in enumerate(guess):
        if results[i] != "absent":
            continue
        if remaining[letter] > 0:
            results[i] = "present"
            remaining[letter] -= 1

    return results


def filter_words(words, feedback):
    """
    Reduce candidate words to only those consistent with API feedback.

    Inputs:
        words (list[str]): Current candidate pool.
        feedback (list[dict]): API response for the latest guess.
            Each item is expected to include:
            - "slot": index position
            - "guess": guessed letter at that slot
            - "result": one of "correct", "present", "absent"

    Returns:
        list[str]: Filtered candidate pool that still matches all clues.

    Key logic:
        - Reconstruct the full guess string from feedback records.
        - Reconstruct expected per-slot result labels in slot order.
        - Keep only words where simulated feedback exactly matches expected.
        - Exact-pattern matching is robust for repeated-letter edge cases.
    """
    # API feedback may arrive unsorted; sort to align with word positions.
    ordered = sorted(feedback, key=lambda x: x["slot"])
    # Rebuild the guessed word and expected result pattern.
    guess = "".join(item["guess"].lower() for item in ordered)
    expected = [item["result"] for item in ordered]
    # Keep candidates that produce the exact same pattern if they were target.
    return [word for word in words if evaluate_guess(guess, word) == expected]


# ── PICK BEST GUESS ──────────────────────────────────────────────────────────
def get_cluster_signature(words):
    """
    Detect whether candidates form a near-identical cluster.

    Inputs:
        words (list[str]): Candidate words currently possible.

    Returns:
        tuple[dict[int, str], dict[int, set[str]]] | None:
        - fixed_positions: indexes where all candidates share one letter
        - varying_positions: indexes where candidates differ
        Returns None when no strong cluster is found.

    Purpose:
        Helps trigger a "sacrifice guess" when many candidates only vary
        in one small area (for example _IGHT family words).
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
    """
    Choose the next guess using stage-aware heuristics.

    Inputs:
        words (list[str]): Current valid candidates.
        attempt (int): Zero-based attempt number (0..MAX_GUESSES-1).
        guessed (list[str]): Words already used in earlier attempts.
        all_words (list[str] | None): Full dictionary for optional probe words.

    Returns:
        str | None: Selected next guess, or None if no words are available.

    Strategy overview:
        1) First move: fixed strong opener.
        2) Small pools: use endgame heuristics (and occasional sacrifice probe).
        3) Mid pools: maximize partition quality.
        4) Large pools: maximize letter coverage/frequency.
    """
    # Attempt 1 uses a consistent opener for strong general information.
    if attempt == 0:
        return "crane" if "crane" in words else words[0]

    if not words:
        return None

    # Prefer unguessed candidates to avoid wasting turns.
    candidate_pool = [w for w in words if w not in guessed]
    if not candidate_pool:
        # If all candidates were already guessed (rare), allow repeats as fallback.
        candidate_pool = words
    if len(candidate_pool) == 1:
        # Only one plausible word remains, so play it directly.
        return candidate_pool[0]

    # Build letter frequencies across current candidates.
    # This captures which letters are currently most informative.
    letter_freq = {}
    for word in words:
        for letter in set(word):
            letter_freq[letter] = letter_freq.get(letter, 0) + 1

    def coverage_score(word):
        """
        Score words by informative letter coverage.

        Inputs:
            word (str): Candidate guess to score.

        Returns:
            int: Higher is better.
        """
        # Bonus for all-unique letters because duplicates reveal less information.
        unique_bonus = 5 if len(set(word)) == len(word) else 0
        return sum(letter_freq.get(l, 0) for l in set(word)) + unique_bonus

    # Sacrifice guess strategy:
    # For 4+ fixed-letter clusters, play one high-information probe outside
    # candidates to collapse the cluster quickly.
    if len(words) <= 10 and attempt < (MAX_GUESSES - 1) and all_words:
        cluster = get_cluster_signature(words)
        if cluster:
            _, varying_positions = cluster
            # Collect letters that distinguish one cluster candidate from another.
            differing_letters = set().union(*varying_positions.values())
            # Probe words can be outside candidate list; they are used to gather info.
            sacrifice_pool = [
                w for w in all_words
                if w not in words and w not in guessed
            ]

            if sacrifice_pool:
                def sacrifice_score(word):
                    """
                    Score a non-candidate probe that can break a tight cluster.

                    Inputs:
                        word (str): Probe word not necessarily a valid answer now.

                    Returns:
                        tuple[int, int, int]: Lexicographic score tuple.
                    """
                    letters = set(word)
                    # Count how many key distinguishing letters the probe touches.
                    overlap = len(letters & differing_letters)
                    # Reward probes that place those letters in the uncertain slots.
                    positional_hits = sum(
                        1 for idx, chars in varying_positions.items()
                        if word[idx] in chars
                    )
                    return (overlap, positional_hits, coverage_score(word))

                best_sacrifice = max(sacrifice_pool, key=sacrifice_score)
                # Use the sacrifice only if it actually tests at least one key letter.
                if len(set(best_sacrifice) & differing_letters) > 0:
                    return best_sacrifice

    # Endgame strategy: when few candidates remain, choose the word that best
    # overlaps with the whole candidate pool while still favoring frequent letters.
    if len(words) <= 10:
        def endgame_score(word):
            """
            Score endgame candidates when only a few answers remain.

            Inputs:
                word (str): Candidate guess.

            Returns:
                tuple[int, int, int]: Lexicographic score tuple.
            """
            word_letters = set(word)
            # Prefer guesses that overlap letters with many remaining candidates.
            shared_letters = sum(
                len(word_letters & set(candidate))
                for candidate in words
            )
            # Secondary preference: globally frequent letters in this pool.
            frequency_score = sum(letter_freq.get(letter, 0) for letter in word_letters)
            return (shared_letters, frequency_score, coverage_score(word))

        return max(candidate_pool, key=endgame_score)

    # For early/mid game on a narrowed list, maximize partition diversity.
    # This improves attempt 2/3 quality while still guessing from candidates only.
    if len(words) <= 200:
        def partition_score(guess):
            """
            Score guesses by how evenly they split candidate outcomes.

            Inputs:
                guess (str): Candidate guess to evaluate.

            Returns:
                tuple[float, float, int]: Lexicographic score tuple.
            """
            buckets = {}
            for target in words:
                # Group targets by the feedback pattern they would produce.
                pattern = tuple(evaluate_guess(guess, target))
                buckets[pattern] = buckets.get(pattern, 0) + 1
            # Better split means:
            # - the largest bucket is small (worst-case is better),
            # - the expected remaining bucket size is small.
            worst_bucket = max(buckets.values())
            expected_bucket = sum(v * v for v in buckets.values()) / len(words)
            return (-worst_bucket, -expected_bucket, coverage_score(guess))

        return max(candidate_pool, key=partition_score)

    return max(candidate_pool, key=coverage_score)

# ── DISPLAY HELPERS ──────────────────────────────────────────────────────────
def feedback_to_display(feedback):
    """
    Convert raw API feedback into a compact human-readable string.

    Inputs:
        feedback (list[dict]): API feedback objects with "slot" and "result".

    Returns:
        str: A visual row using emoji squares or ASCII fallbacks.
    """
    if _USE_UNICODE:
        sym = {"correct": "🟩", "present": "🟨", "absent": "⬛"}
    else:
        sym = {"correct": "G", "present": "Y", "absent": "."}
    return "".join(
        sym[item["result"]]
        for item in sorted(feedback, key=lambda x: x["slot"])
    )


# ── MAIN SOLVER ──────────────────────────────────────────────────────────────
def solve(mode="random", seed=42, target=None, preloaded_words=None):
    """
    Run one full Wordle game until solved or attempts are exhausted.

    Inputs:
        mode (str): "random", "daily", or "word".
        seed (int): Seed used in random mode for repeatable puzzles.
        target (str | None): Exact target word for "word" mode.
        preloaded_words (list[str] | None): Optional pre-fetched dictionary.
            When provided, avoids re-loading/downloading word lists each game.

    Returns:
        bool: True if solved within MAX_GUESSES, otherwise False.

    Key loop steps:
        1) Choose next guess from current candidates.
        2) Send guess to API endpoint for selected mode.
        3) Check for win condition.
        4) Filter candidate pool using returned feedback.
        5) Repeat until solved or out of attempts.
    """
    if _USE_UNICODE:
        print(f"\n🟩 Votee Wordle Solver")
    else:
        print("\n== Votee Wordle Solver ==")
    print(f"   Mode: {mode.upper()}" + (f" | Seed: {seed}" if mode == "random" else ""))
    print("=" * 45)

    # Reuse a preloaded dictionary when available (important for batch runs).
    all_words = preloaded_words if preloaded_words is not None else load_words()
    # Start with every known word as potentially valid.
    candidates = all_words.copy()
    # Track played guesses to avoid repeats where possible.
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

        # Select guess based on attempt number and candidate pool shape.
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

        # Keep only words that remain consistent with the new feedback.
        candidates = filter_words(candidates, feedback)
        print(f"Remaining candidates: {len(candidates)}")
        # Show a short preview when the list is small enough to inspect.
        if 0 < len(candidates) <= 10:
            print(f"Top candidates: {candidates[:10]}")

    if not solved:
        if _USE_UNICODE:
            print(f"\n❌ Could not solve in {MAX_GUESSES} guesses.")
        else:
            print(f"\n[X] Could not solve in {MAX_GUESSES} guesses.")

    return solved


# ── ENTRY POINT ──────────────────────────────────────────────────────────────
def parse_args():
    """
    Parse command-line options for running the solver.

    Inputs:
        None directly (reads from process argv).

    Returns:
        argparse.Namespace: Parsed values for mode, seed, target, and games.
    """
    parser = argparse.ArgumentParser(
        description="Votee Wordle Solver — automatically solves Wordle via API"
    )
    parser.add_argument(
        "--mode",
        choices=["random", "daily", "word"],
        default="random",
        help="Game mode: random (default), daily, or word"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for random mode (default: 42)"
    )
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="Target word for word mode (e.g. --target crane)"
    )
    parser.add_argument(
        "--games",
        type=int,
        default=1,
        help="Number of games to play in random mode (default: 1)"
    )
    return parser.parse_args()


def run_multiple_games(n, mode="random"):
    """
    Execute multiple games and print aggregate win statistics.

    Inputs:
        n (int): Number of games to run.
        mode (str): Game mode to use for each run.

    Returns:
        None. Prints per-game progress and final summary stats.
    """
    print(f"\nRunning {n} games in {mode.upper()} mode...")
    print("=" * 45)

    # Load once and reuse across all games to avoid repeated downloads.
    shared_words = load_words()

    wins = 0
    for i in range(n):
        # Use deterministic changing seeds so each random game differs.
        seed = i
        print(f"\n--- Game {i+1}/{n} | seed={seed} ---")
        result = solve(mode=mode, seed=seed, preloaded_words=shared_words)
        if result:
            wins += 1

    print("\n" + "=" * 45)
    print(f"Final Results: {wins}/{n} solved ({100*wins//n}% win rate)")


if __name__ == "__main__":
    args = parse_args()

    if args.games > 1:
        run_multiple_games(args.games, args.mode)
    else:
        solve(mode=args.mode, seed=args.seed, target=args.target)