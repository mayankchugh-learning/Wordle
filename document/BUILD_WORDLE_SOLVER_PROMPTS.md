# Prompt Pack to Rebuild `wordle_solver.py`

Use these prompts in order with your coding AI (ChatGPT/Cursor/Claude) to recreate the solver step by step.

---

## Prompt 1 — Create the skeleton

```text
Create a Python file named `wordle_solver.py` for a Votee Wordle solver.

Requirements:
- Keep all logic in one file.
- Add imports: `requests`, `urllib.request`, `sys`, `Counter` from `collections`, and `argparse`.
- Add module constants:
  - `BASE_URL = "https://wordle.votee.dev:8000"`
  - `WORD_LIST_URLS` with:
    1) `https://raw.githubusercontent.com/tabatkins/wordle-list/main/words`
    2) `https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt`
  - `WORD_SIZE = 5`
  - `MAX_GUESSES = 6`
  - `OPENING_WORDS = ["crane", "lousy", "might"]`
- Add clear section comments for config, loading words, API calls, filtering, guess strategy, display, main solver, and CLI entrypoint.
```

## Prompt 2 — Add Unicode-safe display support

```text
In `wordle_solver.py`, add a helper `_stdout_accepts_unicode() -> bool` that:
- checks `sys.stdout` and encoding,
- returns True for UTF-8,
- tries encoding symbols like green/yellow/black squares and check/cross marks,
- returns False on Unicode encode errors.

Then add `_USE_UNICODE = _stdout_accepts_unicode()`.
```

## Prompt 3 — Add robust word list loading

```text
Implement `load_words()` in `wordle_solver.py`.

Behavior:
1) Try local dictionary `/usr/share/dict/words` first.
2) If unavailable, download and merge all URLs in `WORD_LIST_URLS`.
3) Keep only lowercase alphabetic 5-letter words.
4) If downloads fail, use a short hardcoded fallback word list.
5) Print useful status logs (how many words loaded and from where).
6) Return a sorted list.
```

## Prompt 4 — Add API client functions

```text
Add three functions with request timeout and `raise_for_status()`:

1) `guess_random(guess, seed=42)`
   - GET `{BASE_URL}/random`
   - params: `guess`, `seed`, `size=WORD_SIZE`

2) `guess_daily(guess)`
   - GET `{BASE_URL}/daily`
   - params: `guess`, `size=WORD_SIZE`

3) `guess_word(target, guess)`
   - GET `{BASE_URL}/word/{target}`
   - params: `guess`

Each should return parsed JSON from the API.
```

## Prompt 5 — Implement exact Wordle evaluation logic

```text
Add `evaluate_guess(guess, target)` that returns a list of 5 results using:
- `"correct"` for right letter/right slot,
- `"present"` for right letter/wrong slot,
- `"absent"` otherwise.

Use a two-pass algorithm with `Counter` to handle duplicate letters correctly:
1) mark and consume all `"correct"` letters,
2) then mark `"present"` only when remaining counts allow.
```

## Prompt 6 — Filter candidates from API feedback

```text
Implement `filter_words(words, feedback)`.

Given API feedback items (`slot`, `guess`, `result`):
- sort feedback by `slot`,
- reconstruct the guess string and expected result pattern,
- keep only words where `evaluate_guess(reconstructed_guess, candidate) == expected_pattern`.

This must correctly handle repeated-letter edge cases.
```

## Prompt 7 — Add cluster detection for hard endgames

```text
Implement `get_cluster_signature(words)` that identifies near-identical candidate clusters.

Output:
- `fixed_positions`: index->char where all candidates share same letter
- `varying_positions`: index->set(chars) where they differ

Return `(fixed_positions, varying_positions)` only when there are at least 4 fixed positions and at least one varying position; otherwise return `None`.
```

## Prompt 8 — Implement adaptive guess selection

```text
Implement `pick_best_guess(words, attempt, guessed, all_words=None)` with this strategy:

1) Attempt 0:
   - return `"crane"` if available, else first candidate.

2) If one candidate left:
   - return it.

3) Build letter-frequency map over remaining candidates and a `coverage_score(word)`:
   - score by frequency sum of unique letters,
   - add bonus if all letters are unique.

4) Sacrifice guess strategy:
   - if candidate count <= 10, not last attempt, and `all_words` exists:
   - call `get_cluster_signature`.
   - when a tight cluster exists, choose a non-candidate probe word maximizing:
     - overlap with differing letters,
     - positional hits in varying positions,
     - coverage score.
   - use sacrifice only if it tests at least one differing letter.

5) Endgame (<=10 candidates):
   - pick candidate with best tuple:
     - shared letters across all candidates,
     - frequency score,
     - coverage score.

6) Mid game (<=200 candidates):
   - use partition scoring:
     - simulate feedback patterns against all targets,
     - minimize worst bucket and expected bucket size,
     - break ties with coverage score.

7) Otherwise:
   - return candidate with max coverage score.
```

## Prompt 9 — Add feedback rendering helper

```text
Add `feedback_to_display(feedback)`:
- if `_USE_UNICODE` use:
  - `"correct"` -> 🟩
  - `"present"` -> 🟨
  - `"absent"` -> ⬛
- else fallback:
  - `"correct"` -> G
  - `"present"` -> Y
  - `"absent"` -> .

Sort feedback by `slot` before building output string.
```

## Prompt 10 — Build the main solve loop

```text
Implement `solve(mode="random", seed=42, target=None, preloaded_words=None) -> bool`.

Requirements:
- Print game header and mode information.
- Load dictionary using `preloaded_words` when provided.
- Maintain:
  - `candidates`,
  - `guessed`,
  - `solved`.
- Loop for `MAX_GUESSES` attempts:
  1) if candidates empty, reset to full dictionary with warning.
  2) choose guess via `pick_best_guess(...)`.
  3) call API based on mode (`random`, `daily`, `word`).
  4) print visual result via `feedback_to_display`.
  5) if all results are `"correct"`, print solved message and return True.
  6) otherwise filter candidates and print remaining count.
  7) if remaining <= 10, print top candidates preview.
- If unsolved after all attempts, print failure message and return False.
- Raise `ValueError` for unknown mode.
```

## Prompt 11 — Add CLI argument parsing and multi-game runner

```text
Add:

1) `parse_args()` with argparse:
   - `--mode` choices: random/daily/word (default random)
   - `--seed` int default 42
   - `--target` optional string
   - `--games` int default 1

2) `run_multiple_games(n, mode="random")`:
   - load words once,
   - run `n` games with seed = game index,
   - track wins,
   - print final win-rate summary.
```

## Prompt 12 — Finalize entrypoint and quality pass

```text
Finish `wordle_solver.py` with:

if __name__ == "__main__":
    args = parse_args()
    if args.games > 1:
        run_multiple_games(args.games, args.mode)
    else:
        solve(mode=args.mode, seed=args.seed, target=args.target)

Then run a quick code-quality pass:
- Keep function names and signatures exactly as designed.
- Ensure no inline imports.
- Ensure all API calls have timeouts.
- Ensure duplicate letters are handled correctly.
- Ensure Windows terminals without UTF-8 use ASCII fallback symbols.
```

---

## Prompt 13 — Add average-guesses statistics for `--games`

```text
Enhance `run_multiple_games(n, mode="random")` to report average guesses for solved games.

Requirements:
- Track guesses used per game (only count solved games).
- Keep existing win counting.
- Print:
  - total solved: `wins/n`
  - win rate %
  - average guesses on solved games (e.g. `avg guesses (solved): 4.33`)
- If no games are solved, print a safe fallback message instead of dividing by zero.

Implementation notes:
- Update `solve(...)` to optionally return both:
  - solved status
  - guesses used
- A clean way is `solve(..., return_details=False)`:
  - default behavior unchanged when False
  - when True, return tuple `(solved: bool, guesses_used: int)`
```

## Prompt 14 — Show solve time per game

```text
Add timing metrics for each game and summary timing across `--games`.

Requirements:
- Use `time.perf_counter()` to measure elapsed seconds.
- For single-game `solve(...)`:
  - measure full solve duration,
  - print `Solve time: X.XXXs` at end of game.
- For `run_multiple_games(...)`:
  - print per-game duration (e.g. `Game 2 time: 1.284s`),
  - print aggregate timing summary:
    - total time for all games,
    - average time per game.
- Keep output readable and consistent with existing console style.
```

## Prompt 15 — Add `validate_word_input` helper

```text
Implement `validate_word_input(word, field_name="word")` and integrate it everywhere user-provided words are accepted.

Validation rules:
- Reject `None`.
- Reject non-string values.
- Strip whitespace and lowercase input before use.
- Must be exactly `WORD_SIZE` characters long.
- Must be alphabetic only (`isalpha()`).

Behavior:
- Return normalized valid word string.
- Raise `ValueError` with clear, user-friendly message on invalid input.

Integration points:
- Validate `--target` when `--mode word` is used.
- Validate `guess` argument in API guess wrapper functions before sending requests.
- Keep error messages explicit (what failed and expected format).
```

## Prompt 16 — Implement `--verbose` flag

```text
Add a CLI flag `--verbose` to control logging detail.

Requirements:
- In `parse_args()`, add:
  - `--verbose`, action=`store_true`, default False.
- Thread a `verbose` parameter through:
  - `solve(...)`
  - `run_multiple_games(...)`
  - helper functions where extra debug output is useful.
- Default mode (non-verbose):
  - keep concise output: attempts, result row, remaining candidates, final summary.
- Verbose mode:
  - include extra diagnostics such as:
    - selected strategy path (endgame/partition/sacrifice),
    - top scored candidate previews,
    - filtering deltas (before/after candidate count),
    - timing details per attempt if available.
- Ensure existing behavior stays backward compatible when flag is not provided.
```

---

## One-shot prompt (alternative)

If you want a single big prompt instead of 12 incremental prompts:

```text
Build a single-file Python project `wordle_solver.py` that solves Wordle using Votee API endpoints:
- `GET /random?guess=WORD&seed=42&size=5`
- `GET /daily?guess=WORD&size=5`
- `GET /word/{target}?guess=WORD`
Base URL: `https://wordle.votee.dev:8000`.

Must include:
1) constants for URLs and game settings (`WORD_SIZE=5`, `MAX_GUESSES=6`).
2) robust `load_words()` (system dictionary fallback, online merge fallback, hardcoded emergency list).
3) API wrappers `guess_random`, `guess_daily`, `guess_word` with timeout + `raise_for_status`.
4) `evaluate_guess` with two-pass duplicate-letter logic.
5) `filter_words` that reconstructs guess/result from API feedback and keeps only exact pattern matches.
6) adaptive `pick_best_guess`:
   - opener `crane`,
   - coverage scoring by letter frequencies + unique-letter bonus,
   - endgame strategy for <=10,
   - partition strategy for <=200,
   - sacrifice probe strategy for tight clusters via `get_cluster_signature`.
7) Unicode-safe display helper with emoji/ASCII fallback.
8) `solve()` game loop with candidate tracking and printed progress.
9) CLI args (`--mode`, `--seed`, `--target`, `--games`), plus `run_multiple_games`.
10) executable `if __name__ == "__main__"` entrypoint.

Keep code clear, documented, and production-safe for Windows and Unix terminals.
```
