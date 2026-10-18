# What lives inside the net, and what stays outside

Plan only (2026-10-13). Nothing here is built yet.

The question has two directions:

- **Embed**: move a piece of the Python into cells, so it stops costing Python bytes.
- **Extract**: pull a short description back out of a big net (the 20,304-cell sine
  net is really ~330 bits of choices plus a builder).

For each part of `bmsynth/` this says where it can live, how it would get there, and
whether the method used is itself something a net can do.

---

## 1. Inventory: every part, and where it can live

Sizes are gzip -9 of the module (rough cost of keeping it in Python).

| Part | Where it is now | Can it be in the net? | Why |
|---|---|---|---|
| **Cell rule + tick** (`Net.step`, `bmn.py`, 2.9 KB) | Python | **No. Stays outside.** | Something has to apply the rule. A net can *interpret* another net, but the outermost tick is always outside. This is the fixed kernel; shrink it, never remove it. |
| **Spec / targets** (truth tables for ADD, MUL…, sine sample values from `math.sin`) | Python | **No. Stays outside.** | The target is what the user asks for. It is input, not mechanism. Count its bits; don't embed it. (Exception: targets derived from earlier results, e.g. "same as ADD but wider", can be generated in-net.) |
| **Observation** (`unpack`, `snapshot`, `describe`, JSON, log/anatomy pages) | Python | **No need.** | Reading the state for people. Not part of the computation, so it is not counted. |
| **Search circuit** (counter, decoders, candidate, mismatch, found latch) | **Already cells** (`gridsearch.py` builds it) | Yes, done | Only the *builder* that lays it out is Python. |
| **Dictionary ROM + paste sockets** (`paste.py`, `constructor.py`) | **Already cells** | Yes, done | Same: built by Python, but runs as cells. |
| **Search driver** (`SearchCircuit.run`: tick loop, "all lanes done?", read best cfg, pick min across lanes) | Python | **Partly** | Per-lane "done" is already the `found`/`exhausted` latches. Anything that compares *across lanes* can't be cells today (see §3, lanes). |
| **Clock period P** (`depth()` static analysis) | Python, at build time | Yes | Replace with a worst-case ring length set by a formula, or an in-net "nothing changed" detector. |
| **Builders / expanders**: `Builder.instance`, `Template.build_row`, `ChainTemplate`, `ArrayTemplate` (tiles), `LoopTemplate`, `ProgramSocket`, `ExprTemplate`, `SeriesTemplate`, all `to_net()` (~18.5 KB) | Python | **Yes. Main target.** | They are all "stamp the same tile N times with one wiring rule". That is a counter plus an adder plus a ROM, which the dictionary already has. |
| **Dictionary updates** (`Dictionary.add`: store a found circuit, dedupe by canonical truth table, keep the cheaper) | Python | **Yes** | Storing = copying the found counter value into latches (make the ROM writable). Dedupe = compare truth tables, which is the mismatch block again. Dedupe is optional (an optimisation). |
| **Checks** (`brute_force`, `eval_row`, `truth`, `prog.run`, `Fixed.fmul`, scaling to 8/16/32 bits with random inputs) | Python | **Yes, or drop** | These re-implement the semantics in Python as a second opinion. Generalisation check = build wider net + feed inputs + compare = expander + LFSR + mismatch block. Brute force stays as a test oracle outside the synthesis path. |
| **Curriculum** (step scripts: which template, which target, what width, in what order, f=8, w=14) | Python + human choice | **Yes as a program; the choice itself is bits** | A sequencer net with a program ROM can issue SEARCH / STORE / CHECK commands. The *content* of the curriculum (the order) is data we count, until a search finds it (§4, Phase 5). |

So three things stay outside for good: **the tick**, **the spec**, **the observer**.
Everything else is either already cells or is regular enough to become cells.

---

## 2. How each part gets embedded

### 2a. Builders → an *expander net* (the main work)

Two ways a net can build a net. Recommended default: use both, for different jobs.

**(i) Virtual wiring (exists today).** A fixed pool of generic cells whose wiring is
set by latches; PASTE/WIRE commands write the latches (`Socket`, `Fabric`). Pure cell
rule, nothing new. Cost: every input slot needs a mux over all addresses, so a socket
is ~10–50× bigger than what it hosts. Good for the *inner loop* (search candidates
swap many times per second). Bad for a 20,000-cell result.

**(ii) Emission (new).** The expander net *outputs* a net description: one cell per
group of ticks, as (A, B, C) indices on its output wires. A fixed loader outside
(~5 lines: read the bits each tick, append a row to A/B/C) turns that stream into a
runnable net. Cost: cells proportional to the *rule*, not to the result. Good for
*expansion* (word rules → 14-bit multiplier → T blocks → sine).

The loader joins the tick as fixed kernel. It is tiny and generic; it knows nothing
about tiles, loops or series.

Expander net, built from parts already in the dictionary:

```
 program word (from ROM) ──► sequencer: nested counters  i < W, j < R, k < N
                                   │
                                   ▼
                         address arithmetic: base + i·stride   (ADD / MUL macros)
                                   │
                                   ▼
             rule ROM: pin p of tile (i,j) ← source s   (the found rule, as data)
                                   │
                                   ▼
                   emit (A, B, C) for the next cell   ──►  loader
```

Order of conversion, simplest first, each one checked by comparing the emitted net
against the Python-built net cell for cell (or by truth table where cell order differs):

1. `ChainTemplate` (one counter, one rule) — adders, bitwise ops.
2. `ArrayTemplate` with R = W (two counters) — multiplier.
3. `LoopTemplate` / program words (unroll N steps of FOLD/WHILE/BITS).
4. `ExprTemplate` (T = DIV(POW, FACT)) — nested expansion: a program pastes a macro
   which pastes an entry; the emitter recurses by keeping a small return stack in latches.
5. `SeriesTemplate` — sine. Done when the 330-bit description + expander net + loader
   + tick reproduces the 20,304-cell net.

### 2b. Search driver → controller cells

- "This lane is done" is already the `found`/`exhausted` latches.
- "Read the answer" = the counter value; route it to output wires or into
  dictionary RAM (2c) instead of having Python unpack it.
- The clock period P: computed by a formula at build time (no graph walk), or
  generous fixed P. Optional later: a settle detector (each node XOR its previous
  value, one big NOR). It doubles cells, so only for small nets.

### 2c. Dictionary updates → writable ROM

Today the ROM is constant wiring (an entry costs zero cells, one OR per code bit).
Make one row of it latches: STORE copies the found config (or the code word of the
found circuit) into that row with the same paste-latch formula sockets already use.
Dedupe and "keep the cheaper" are a mismatch block plus a cell-count compare;
schedule them last, because they only save space.

### 2d. Checks → LFSR + mismatch

Generalisation check = emit the wider net (2a), drive it with an LFSR (a few cells)
for random inputs, compare with the spec through the existing mismatch block.
`brute_force` and the Python `eval_row`s stay outside, as test oracles only.

### 2e. Curriculum → a sequencer program

A small controller: program counter + command ROM + the SEARCH / STORE / EXPAND /
CHECK operations above. Step 6 and step 7 become ROM contents, not Python scripts.
The f=8, w=14 choices become fields of that ROM.

---

## 3. What extraction means, and how

Extraction goes the other way: big net in, short description out.

| What is extracted | From | Method |
|---|---|---|
| **Dead cells** (16,676 of 20,304 don't affect sine) | the expanded net | Backward reachability from the outputs, then constant folding. A net can do it: one "live" bit per cell, live = OR of the live bits of every reader (one tick per layer). |
| **Repeated tiles** → dictionary entry + rule | any flat net | Look for a tile + rule that reproduces the subnet. That *is* the grid search with the subnet's truth table as target. |
| **The whole description** (decompile 20k cells back to ~330 bits) | the sine net | Search over (program word, series word) whose expansion matches the net's function. Same search circuit, the expander from §2a inside the candidate. |
| **Python semantics** (`eval_row`, `prog.run`, `Fixed`) | the synthesis path | Delete from the path once the in-net checks (§2d) exist; keep as oracles. |

---

## 4. Is the method itself embeddable?

| Method | Embeddable? | Note |
|---|---|---|
| Virtual wiring (paste) | **Yes, already cells** | But a socket can only host something much smaller than itself, so it can't host its own builder. |
| Emission + loader | **Yes** | The expander is counters, adders and a ROM, all dictionary entries. A net can emit its own description (a quine is just ROM + counter), so the expander can rebuild itself. This is how the builder gets inside without an infinite regress. |
| Search | **Yes, already cells** | And it can search over *expander rules* or *curricula*, because those are just bits. That is the README's last rung: the synthesizer synthesizing parts of itself. |
| Extraction (dead cells, rule finding, decompile) | **Yes** | Reachability is one bit per cell; rule finding and decompiling are the same search. |
| Cross-lane operations (min over lanes, "all lanes done", the `split` speed-up's final pick) | **Not with today's cell rule** | A cell only sees its own lane. Two options: (a) move those lanes into separate nodes (costs cells, rule unchanged), or (b) add one primitive to the rule: OR across lanes. **Default: (a)**, to keep the rule pure; (b) is noted if (a) gets too big. |
| The tick | **No** | A net can run an interpreter for another net, but someone has to run the outer one. This is the fixed point: cell rule + tick + loader. |
| The spec | **No** | Input by definition. |

---

## 5. Phases (each ends with a visual check-in)

| Phase | What | Shows | Done when |
|---|---|---|---|
| 0 | Boundary map: tag every Python function as tick / spec / observer / builder / driver / checker / curriculum, with gzip bytes | One diagram, bytes on each side of the line | Every function has a tag; totals match the 18.5 KB + 2.9 KB already measured |
| 1 | Emission format + loader; ChainTemplate expander net | Emitted adder next to the Python-built adder, cell for cell | 8- and 32-bit adders emitted by a net match |
| 2 | Array, loop, program, expr expanders | Same side-by-side for MUL, POW, DIV, T | All step-6/7 macros emitted by nets |
| 3 | Series expander → sine | Sine from 330 bits + expander net + loader + tick | Same function as the 20,304-cell net |
| 4 | Driver, writable dictionary, LFSR check, curriculum ROM | Step 6 rerun with no step script: the controller net does it | Same dictionary as `out/dictionary.json` |
| 5 | Extraction + self-application: dead-cell pass in-net; search finds a shorter expander rule or curriculum | New description-length bar: what's outside vs inside | Python outside the net = tick + loader + spec + observer only |

New description-length line after Phase 4, for comparison with today's
"330 bits + 18.5 KB expander + 2.9 KB simulator":
**330 bits + expander/controller net bits + tick + loader.**

## Defaults picked (say if you want otherwise)

1. Emission (ii) for expansion, virtual wiring (i) kept for the search inner loop.
2. No change to the cell rule; cross-lane work moves to nodes.
3. Dedupe in the dictionary is last priority.

Doesn't touch the files of the "Binary matrix representation plan" thread's OEIS check.
