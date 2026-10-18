# bmsynth file map (2026-10-14, 13:05 UTC)

Read-only snapshot taken while the other thread is working. "Live" = imported by, or edited for,
the current v2 / structure-discovery work. Evidence: import lines and file times.

## 1. Core framework (everything else stands on these)

| File | What it is | Status |
|---|---|---|
| `bmn.py` | Cell rule, `Net.step`, `Builder`, `instance()` (the paste) | Live: every v2 file imports it |
| `gridsearch.py` | `Template` + `SearchCircuit` (counter, decoders, mismatch, found latch) | Live: edited today 12:31; `timetemplate` and `item1` use it |
| `v2/blackbox.py` | `BlackBox` / `BoxNet`: a net calls a Python function on a call wire | Live: used by step1-4 and item2/3 |
| `v2/netparts.py` | Hand-written cell blocks: clock ring, registers, +1 | Live: used by step2-4 and item3 |
| `v2/fastnet.py` | Numba version of the same tick | **Not imported anywhere.** Built but unused (or only for timing) |

## 2. Templates: search spaces someone wrote (they decide what can be found)

| File | Search space | Status |
|---|---|---|
| `v2/timetemplate.py` | Cells with feedback, judged over time (delay, toggle, counter bit) | Live (today 12:31) |
| `v2/wordtemplate.py` | Word nodes `op(src_a, src_b)` with feedback; ops ADD..MAX | Live (today 12:58) |
| `v2/step4_walk.py` | Fixed 11-bit shape `op2(op1(X1,Y1),Y2)` | Superseded by `item3_wiring` |
| `chain.py`, `tiles.py` | One tile × W with one wiring rule (adders, MUL array) | v1, sine line only |
| `loop.py`, `prog.py` | FOLD / WHILE / BITS program word | v1, sine line only |
| `series.py` | Signed sum of T terms, fixed point | v1, sine line only |
| `dictionary.py` `BlockTemplate` / `SocketTemplate` | Wire dictionary entries | v1, sine line only |

## 3. Black boxes: Python functions the net calls as leaves

| Where | Box | Note |
|---|---|---|
| `v2/step1-4` | ADD, SUB, MUL, PASS (Python lambdas) | Generic arithmetic |
| `v2/item3_wiring.py` | `EVAL(q, terms)`: runs the whole WordTemplate block in numpy and matches by hash | **Not a leaf op.** It is the template interpreter plus the comparison, so most of the search runs here, not in cells. The net's job is reduced to: count q, call EVAL, latch the result |
| `v2/item2_lift.py` | `f(reg)` test box | Test harness, observation side |

## 4. Steps and drivers (runs that write json)

| File | Status |
|---|---|
| `v2/item1_behaviours.py`, `item2_lift.py`, `item3_wiring.py` | **Active now** (12:54–13:01 today) |
| `v2/step1_demo` … `step4_walk` + `step*.json` | Done 2026-10-13; kept as the record behind the Net-Driven Synthesis page |
| `step1_substrate` … `step7_sine` + `out/*.json` | Done 2026-10-13; v1 sine record |

## 5. Stale (nothing current imports or runs them)

| File(s) | Why stale |
|---|---|
| `dictionary.py`, `paste.py`, `constructor.py` | v1 dictionary ROM, sockets, PASTE/WIRE fabric. v2 pastes with `Builder.instance` instead and has no dictionary file yet |
| `chain.py`, `tiles.py`, `loop.py`, `prog.py`, `series.py` | v1 hand-written templates. PEIXUAN asked for structures to be found, not designed |
| `anatomy.py`, `make_anatomy.py`, `make_log.py`, `*_template.html`, `out/*.html` | Pages for the v1 sine work |
| `reference.py` | Not imported |
| `plans/embed-extract-plan.md` (mine) | Written for the v1 builders; v2 took the black-box route instead |
| `plans/main-net.md` | Replaced by `structure-discovery.md` (says so itself) |
| `oeis/` (`bfs.py`, `failures.py`, `examples.py`, `rank.py`, `loda.py` …) | Feasibility study and target fetching. `bfs.py` is the hand-template search PEIXUAN rejected. Only the target data (`top2000.jsonl`, metadata) still feeds v2 |
| `__pycache__/` folders | Build leftovers |
| `Synthesizer/` | Your original code. bmsynth doesn't use it, by your rule |

## Live plans
`plans/net-driven-plan.md` (steps 1-4 done) → `plans/structure-discovery.md` (items 1-3 under way now).
