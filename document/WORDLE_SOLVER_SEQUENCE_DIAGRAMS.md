# Wordle Solver — Sequence & Flow Diagrams

View this file in VS Code (Markdown Preview) or GitHub to render **Mermaid** diagrams.

## Quick index

| Topic | Flowchart | Sequence |
|-------|-----------|----------|
| `solve` | [§0](#0-solve-high-level-flowchart) | [§1](#1-end-to-end-one-full-game-solve) |
| `load_words` | [§9](#9-load_words-flowchart) | [§10](#10-load_words-sequence) |
| Votee API | — | [§11](#11-votee-api-guess-requests) |
| `filter_words` | [§12](#12-filter_words-flowchart) | [§3](#3-filter_words-how-consistency-is-checked) |
| `pick_best_guess` | [§4](#4-pick_best_guess-decision-flow-activity-diagram) | [§5–6](#5-pick_best_guess-partition-step-mid-size-pool) |
| Sacrifice logic | [§13](#13-sacrifice-guess-explained-with-example) | [§6](#6-pick_best_guess-sacrifice--cluster-step-optional-probe) |
| `evaluate_guess` | [§7](#7-evaluate_guess-flowchart-duplicate-letter-safe-logic) | [§8](#8-evaluate_guess-sequence-diagram-what-changes-each-pass) |

---

## 0) `solve`: high-level flowchart

Use this as a **single-page mental model** before diving into API vs filter details.

```mermaid
flowchart TD
    Start([start solve]) --> Load{preloaded_words?}
    Load -->|yes| A1[all_words = preloaded_words]
    Load -->|no| LW[load_words]
    LW --> A1
    A1 --> Init[candidates = copy all_words<br/>guessed = empty<br/>solved = False]
    Init --> Loop{attempt in 0..MAX_GUESSES-1?}
    Loop -->|no| Final{not solved?}
    Final -->|yes| Fail[print could not solve]
    Final -->|no| End([return solved])
    Fail --> End
    Loop -->|yes| Empty{candidates empty?}
    Empty -->|yes| Reset[candidates = all_words fallback]
    Empty -->|no| StepPick
    Reset --> StepPick[pick_best_guess → append guessed]
    StepPick --> Guess[print attempt + guess]
    Guess --> API{mode}
    API -->|random| R[guess_random]
    API -->|daily| D[guess_daily]
    API -->|word| W[guess_word]
    API -->|else| Bad[raise ValueError unknown mode]
    R --> FB[feedback]
    D --> FB
    W --> FB
    FB --> Win{all slots correct?}
    Win -->|yes| Solved[solved = True, break loop]
    Solved --> End
    Win -->|no| Filt[filter_words → print count]
    Filt --> Loop
```

---

## 1) End-to-end: one full game (`solve`)

Shows how the main loop ties together loading words, picking a guess, calling the API, and filtering candidates.

```mermaid
sequenceDiagram
    autonumber
    actor User as CLI / caller
    participant Solve as solve()
    participant Load as load_words()
    participant Pick as pick_best_guess()
    participant API as Votee API<br/>(random / daily / word)
    participant Filter as filter_words()

    User->>Solve: solve(mode, seed, target, preloaded_words?)
    alt preloaded_words is None
        Solve->>Load: load_words()
        Load-->>Solve: all_words
    else preloaded_words provided
        Solve->>Solve: all_words = preloaded_words
    end
    Solve->>Solve: candidates = copy(all_words)

    loop Up to MAX_GUESSES attempts
        alt candidates empty
            Solve->>Solve: reset candidates = all_words (fallback)
        end
        Solve->>Pick: pick_best_guess(candidates, attempt, guessed, all_words)
        Pick-->>Solve: guess

        alt mode == random
            Solve->>API: GET /random (guess, seed)
        else mode == daily
            Solve->>API: GET /daily (guess)
        else mode == word
            Solve->>API: GET /word/{target} (guess)
        end
        API-->>Solve: feedback (per-slot results)

        alt all letters correct
            Solve->>User: solved = True, stop
        else not solved
            Solve->>Filter: filter_words(candidates, feedback)
            Filter->>Filter: rebuild guess + expected pattern<br/>simulate with evaluate_guess
            Filter-->>Solve: narrowed candidates
        end
    end
    Solve-->>User: return solved (bool)
```

---

## 2) Single guess: API + filter (detail)

Use this when explaining **one iteration** of the loop.

```mermaid
sequenceDiagram
    autonumber
    participant Solve as solve()
    participant Pick as pick_best_guess()
    participant API as Votee API
    participant Filter as filter_words()
    participant Eval as evaluate_guess()

    Solve->>Pick: pick_best_guess(...)
    Pick-->>Solve: guess
    Solve->>API: submit guess
    API-->>Solve: feedback[]
    Solve->>Filter: filter_words(candidates, feedback)
    loop each word w in candidates
        Filter->>Eval: evaluate_guess(guess, w)
        Eval-->>Filter: pattern[]
    end
    Filter-->>Solve: words matching expected pattern
```

---

## 3) `filter_words`: how consistency is checked

```mermaid
sequenceDiagram
    autonumber
    participant Filter as filter_words()
    participant Eval as evaluate_guess()

    Filter->>Filter: sort feedback by slot
    Filter->>Filter: guess = join guessed letters
    Filter->>Filter: expected = list of results
    loop each candidate word
        Filter->>Eval: evaluate_guess(guess, word)
        Eval-->>Filter: simulated pattern
        Filter->>Filter: keep word if pattern == expected
    end
    Filter-->>Filter: return filtered list
```

---

## 4) `pick_best_guess`: decision flow (activity diagram)

Strict “sequence between objects” is awkward here because almost everything is **branching inside one function**. An **activity / flowchart** matches the code order and is easier to follow step by step.

```mermaid
flowchart TD
    A([start pick_best_guess]) --> B{attempt == 0?}
    B -->|yes| B1[return crane if in words else words[0]]
    B1 --> Z([end])
    B -->|no| C{words empty?}
    C -->|yes| C1[return None]
    C1 --> Z
    C -->|no| D[build candidate_pool = unguessed words]
    D --> E{candidate_pool empty?}
    E -->|yes| F[candidate_pool = words]
    E -->|no| G{len candidate_pool == 1?}
    F --> G
    G -->|yes| G1[return that word]
    G1 --> Z
    G -->|no| H[compute letter_freq over words]
    H --> I{len words <= 10 AND attempt < last AND all_words?}
    I -->|yes| J[get_cluster_signature]
    J --> K{cluster exists?}
    K -->|no| N1
    K -->|yes| L[sacrifice_pool from all_words]
    L --> M{sacrifice_pool non-empty?}
    M -->|no| N1
    M -->|yes| SacPick[best_sacrifice = max sacrifice_score]
    SacPick --> SacHit{best_sacrifice hits a differing letter?}
    SacHit -->|yes| P1[return best_sacrifice]
    P1 --> Z
    SacHit -->|no| N1
    I -->|no| N1
    N1{len words <= 10?}
    N1 -->|yes| Endgame[endgame_score: max over candidate_pool]
    Endgame --> Z
    N1 -->|no| N2{len words <= 200?}
    N2 -->|yes| Part[partition_score using evaluate_guess buckets]
    Part --> Z
    N2 -->|no| Cov[coverage_score only: max over candidate_pool]
    Cov --> Z
```

---

## 5) `pick_best_guess`: partition step (mid-size pool)

Explains what happens inside the `len(words) <= 200` branch.

```mermaid
sequenceDiagram
    autonumber
    participant Pick as pick_best_guess()
    participant Eval as evaluate_guess()

    Note over Pick: candidate_pool already chosen
    loop for each trial guess in candidate_pool
        Pick->>Pick: partition_score(guess)
        loop for each target in words (current candidates)
            Pick->>Eval: evaluate_guess(guess, target)
            Eval-->>Pick: pattern tuple
            Pick->>Pick: bucket counts by pattern
        end
        Pick->>Pick: score = f(worst_bucket, expected_size, coverage)
    end
    Pick->>Pick: return guess with best partition_score
```

---

## 6) `pick_best_guess`: sacrifice / cluster step (optional probe)

```mermaid
sequenceDiagram
    autonumber
    participant Pick as pick_best_guess()
    participant Cluster as get_cluster_signature()
    participant Sacrifice as sacrifice_pool<br/>(from all_words)

    Pick->>Cluster: get_cluster_signature(words)
    Cluster->>Cluster: per index: fixed vs varying letters
    Cluster-->>Pick: None OR (fixed_positions, varying_positions)

    alt cluster is None
        Pick->>Pick: skip sacrifice block
    else cluster found
        Pick->>Pick: differing_letters from varying slots
        Pick->>Sacrifice: filter: not in words, not guessed
        Sacrifice-->>Pick: sacrifice_pool
        alt sacrifice_pool empty
            Pick->>Pick: skip return
        else
            Pick->>Pick: best_sacrifice = max by sacrifice_score
            alt overlaps differing letters
                Pick-->>Pick: return best_sacrifice
            end
        end
    end
```

---

## 7) `evaluate_guess`: flowchart (duplicate-letter safe logic)

Use this to explain why the solver handles duplicate letters correctly.

```mermaid
flowchart TD
    A([start evaluate_guess guess target]) --> B[normalize: guess lower, target lower]
    B --> C[results = absent x WORD_SIZE]
    C --> D[remaining = Counter target]
    D --> E[Pass 1: iterate i, letter in guess]
    E --> F{letter == target i?}
    F -->|yes| G[results i = correct<br/>remaining letter minus 1]
    F -->|no| H[leave as absent]
    G --> I{more letters in pass 1?}
    H --> I
    I -->|yes| E
    I -->|no| J[Pass 2: iterate i, letter in guess]
    J --> K{results i != absent?}
    K -->|yes| L[skip this index]
    K -->|no| M{remaining letter > 0?}
    M -->|yes| N[results i = present<br/>remaining letter minus 1]
    M -->|no| O[keep absent]
    L --> P{more letters in pass 2?}
    N --> P
    O --> P
    P -->|yes| J
    P -->|no| Q[return results]
    Q --> R([end])
```

---

## 8) `evaluate_guess`: sequence diagram (what changes each pass)

```mermaid
sequenceDiagram
    autonumber
    participant Caller as filter_words / pick logic
    participant Eval as evaluate_guess()
    participant Remaining as remaining Counter
    participant Results as results list

    Caller->>Eval: evaluate_guess(guess, target)
    Eval->>Eval: normalize guess + target to lowercase
    Eval->>Results: initialize all slots as "absent"
    Eval->>Remaining: initialize Counter(target)

    Note over Eval: Pass 1 (greens): exact position matches
    loop each index i
        Eval->>Eval: compare guess[i] with target[i]
        alt exact match
            Eval->>Results: set results[i] = "correct"
            Eval->>Remaining: decrement count for that letter
        else no exact match
            Eval->>Results: keep "absent" for now
        end
    end

    Note over Eval: Pass 2 (yellows): misplaced matches using remaining counts
    loop each index i
        alt results[i] already "correct"
            Eval->>Eval: continue
        else results[i] is "absent"
            Eval->>Remaining: check remaining count for guess[i]
            alt count > 0
                Eval->>Results: set results[i] = "present"
                Eval->>Remaining: decrement count
            else count == 0
                Eval->>Results: keep "absent"
            end
        end
    end

    Eval-->>Caller: results ["correct"/"present"/"absent"...]
```

---

## 9) `load_words`: flowchart

Shows the three-tier fallback: system dictionary → download URLs → hardcoded list.

```mermaid
flowchart TD
    LW([start load_words]) --> TryOpen[try open /usr/share/dict/words]
    TryOpen --> HasSys{read lines, filter 5-letter alpha?}
    HasSys -->|got words| RetSys[return sorted system words]
    HasSys -->|FileNotFound or empty| DL[print Downloading word lists]
    DL --> Merge[merged = empty set]
    Merge --> LoopURL[for each URL in WORD_LIST_URLS]
    LoopURL --> Fetch[urllib urlopen, read decode]
    Fetch --> Parse[keep 5-letter alpha lines → set]
    Parse --> Merge
    LoopURL --> AfterURLs{merged non-empty?}
    AfterURLs -->|yes| RetMerge[return sorted merged]
    AfterURLs -->|no| Fallback[return small hardcoded word list]
    RetSys --> End([end])
    RetMerge --> End
    Fallback --> End
```

---

## 10) `load_words`: sequence

```mermaid
sequenceDiagram
    autonumber
    participant Caller as solve / run_multiple_games
    participant Load as load_words()
    participant FS as local filesystem
    participant Net as remote URLs

    Caller->>Load: load_words()
    Load->>FS: try read /usr/share/dict/words
    alt file exists and has 5-letter words
        FS-->>Load: lines
        Load-->>Caller: list of words
    else not available
        Load->>Net: GET each WORD_LIST_URLS
        Net-->>Load: text bodies
        Load->>Load: merge sets, filter length 5
        alt merged non-empty
            Load-->>Caller: sorted merged list
        else all downloads failed or empty
            Load-->>Caller: built-in fallback list
        end
    end
```

---

## 11) Votee API: guess requests

All endpoints share `BASE_URL` and return JSON feedback (list of `{slot, guess, result}`).

```mermaid
sequenceDiagram
    autonumber
    participant Solve as solve()
    participant GR as guess_random()
    participant GD as guess_daily()
    participant GW as guess_word()
    participant API as Votee API<br/>wordle.votee.dev:8000

    Note over Solve: branch on mode
    Solve->>GR: guess, seed
    GR->>API: GET /random?guess=&seed=&size=5
    API-->>GR: JSON feedback
    GR-->>Solve: feedback

    Solve->>GD: guess
    GD->>API: GET /daily?guess=&size=5
    API-->>GD: JSON feedback
    GD-->>Solve: feedback

    Solve->>GW: target, guess
    GW->>API: GET /word/{target}?guess=
    API-->>GW: JSON feedback
    GW-->>Solve: feedback
```

---

## 12) `filter_words`: flowchart

Complements the sequence in **§3**: same logic, shown as a decision tree.

```mermaid
flowchart TD
    F([start filter_words words, feedback]) --> Sort[sort feedback by slot]
    Sort --> G[guess = join guess letters]
    G --> E[expected = list of result strings]
    E --> Out[output = empty list]
    Out --> Loop{for each word in words?}
    Loop -->|no| Ret[return output]
    Loop -->|yes| Sim[simulated = evaluate_guess guess, word]
    Sim --> Match{simulated == expected?}
    Match -->|yes| Add[append word to output]
    Match -->|no| Loop
    Add --> Loop
    Ret --> Z([end])
```

---

## 13) Sacrifice guess: explained (with example)

### Why sacrifice exists

Sometimes the remaining answers are **almost the same word** — they agree on 4 positions and only differ in 1–2 slots (a tight **cluster**). Guessing only from that small set can waste turns: each guess might eliminate only one word. A **sacrifice guess** is a word **outside** the current candidate list (but from the full dictionary) chosen to **test letters** that distinguish those answers, so one feedback round splits the cluster faster.

### When it runs (code gates)

All must be true:

- `len(words) <= 10` (small candidate pool)
- `attempt < MAX_GUESSES - 1` (not the last allowed guess)
- `all_words` is provided (full dictionary for probes)
- `get_cluster_signature(words)` returns a cluster: **at least 4 positions fixed** across all candidates, and **at least one varying position** (so not already solved)

### What `get_cluster_signature` does

For each index `0..4`, it looks at which letters appear in that position across **all** current candidates:

- If every candidate has the **same** letter there → that index is **fixed**.
- If candidates disagree → that index is **varying** (a set of possible letters).

If there are **4+ fixed** indices and **some varying** indices, you have a **cluster** (many words share a long prefix/suffix pattern).

### Toy example (pattern only)

Imagine candidates are like `*_IGHT` family words that all share `I G H T` in the last four positions but differ in the first letter. Then positions 1–4 might look “fixed” in the code’s view depending on overlap — the **varying** slot contributes **differing letters**. The sacrifice pool picks words from `all_words` that are **not** in the current `words` list, scores them by how many of those **differing** letters they include and whether they place them in **varying** slots, and may return the best probe **if** it touches at least one differing letter.

### Flowchart: cluster detection + sacrifice decision

```mermaid
flowchart TD
    S([sacrifice block inside pick_best_guess]) --> G1{len words <= 10<br/>and attempt < last<br/>and all_words?}
    G1 -->|no| Skip[skip sacrifice]
    G1 -->|yes| GS[get_cluster_signature words]
    GS --> G2{cluster found?<br/>4+ fixed and varying}
    G2 -->|no| Skip
    G2 -->|yes| DL[collect differing_letters from varying slots]
    DL --> SP[sacrifice_pool = words in all_words<br/>not in words, not guessed]
    SP --> G3{sacrifice_pool empty?}
    G3 -->|yes| Skip
    G3 -->|no| Best[max by sacrifice_score:<br/>overlap with differing letters,<br/>positional hits in varying slots,<br/>then coverage_score]
    Best --> G4{best_sacrifice uses<br/>any differing letter?}
    G4 -->|no| Skip
    G4 -->|yes| Ret[return best_sacrifice]
    Skip --> Next[endgame or partition or coverage]
    Ret --> Z([end branch])
```

### Mental model (one sentence)

> **Sacrifice = optional probe from the full dictionary when candidates form a tight cluster, to learn which distinguishing letter is correct without burning guesses only cycling through near-identical answers.**

---

## Tips for your interview

- **§0 + §1** together tell the `solve` story: flowchart for structure, sequence for interactions.
- **`load_words`**: **§9–10** — three-tier fallback and who calls it.
- **Votee API**: **§11** — three GET shapes; mention `raise_for_status()` in code if asked.
- **`filter_words`**: **§3** sequence + **§12** flowchart — same logic, pick one style.
- **`pick_best_guess`**: **§4** main flowchart; **§5** partition; **§6** sacrifice sequence; **§13** sacrifice prose + cluster flowchart if you struggle with it.
- **`evaluate_guess`**: **§7–8** — duplicate-letter safety.
- If asked **partition vs sacrifice**: partition splits **mid-size** pools by feedback patterns; sacrifice breaks **tiny near-duplicate** clusters using **non-candidate** probes.
