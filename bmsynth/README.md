# bmsynth

A synthesizer built on one cell rule, where the search for programs runs inside the net.

    y(t+1) = s[z] XNOR OR_k ( s[a_k] AND s[b_k] )        node 0 = constant 0, node 1 = constant 1

## Layout

### `core/`: the substrate, and the only API anything else may use on a net
| File | What it is |
|---|---|
| `net.py` | `Net`: run it (`state`, `load`, `run`, `read`), add/remove cells (`add_cell`, `remove_cell`, `set_init`), add/remove connections (`connect`, `disconnect`, `set_z`), ports (`add_port`, `remove_port`), copy/paste (`copy` → `Circuit`, `paste`), black boxes (`place_box`, `remove_box`, `close`). Lanes are bits of uint64 words; each lane is an independent copy of the net. |
| `tick.py` | One tick of every cell, compiled with numba. |

A black box has a call wire, input words and output ports. In each lane where the call wire is 1 it reads its inputs at tick t and its outputs appear at t+1, like a cell. A box is placed by name, `net.place_box('module.NAME', call, ins, outs, **params)`: core loads the box file and asks its factory `NAME(**params)` for the box; only `Net.run` ever calls it, as `box(lanes, *in_words) -> tuple of out_words`. Nothing in core is specific to any task.

### `boxes/`: hand-written Python, invoked only as black boxes inside a net
| File | Boxes |
|---|---|
| `arith.py` | OP(name): ADD, SUB, MUL, DIV, MOD, MIN, MAX on words. The one definition of these ops (wordeval uses it). |
| `duplicator.py` | DUPLICATE: a library circuit duplicated n times side by side, inputs wired by hand (per-copy bit or shared); stands in for n pasted copies |
| `celleval.py` | CELLEVAL: runs a block of small cell circuits over time, returns the first whose output matches the lane's target stream. STORE: writes each behaviour's best find into the library ports. DICT: writes library entries into slot paste ports |
| `wordeval.py` | EVAL: runs a block of word wirings (ops and found sequences as nodes), returns the first that matches the lane's target terms. GLOBAL: ranks found sequences by use into the global library. RUN, TRACE: run / trace an answer (observation nets) |

Every box above is marked `RULE VIOLATION` in its code: boxes may only replace cells already found in the net, and all of these were hand-written from scratch. onenet is the only place a net is run (the small observation nets in `_observe.py` still break this). Known rule conflicts, open: CELLEVAL and EVAL define their search spaces inside the box, and both are exhaustive grid searches; the ops in `arith.py` are given, not discovered.

### `experiments/`: nets built by hand with the core API, then run
| File | Run |
|---|---|
| `onenet.py` | The main experiment: behaviours → word register → OEIS, as one net run |
| `_build.py` | Gates, library ports, programmable slots, start-up cells, the seed searcher, and ALL (the box that tells every lane whether all lanes are done) |
| `_wordrun.py` | The word searcher (EVAL + GLOBAL) and reading its results |
| `_observe.py` | Observation after a run: decodes ports; asks boxes (DICT, RUN, TRACE) only by placing them in small observation nets |
| `_setup.py` | Paths, OEIS targets |
| `results/` | `onenet.json`, `onenet_watch.json` |

Run e.g. `python3 experiments/onenet.py [n_targets] [seconds]`.

### `targets/`: hand-built target datasets
| File | Targets |
|---|---|
| `behaviours.py` | Common sequential circuits (square waves, pulses, delay, inverted delay, memory bit, latch) as input/output streams |
| `word_register.py` | Target only: a 16-bit register that must step reg+3 (or 5·reg+1) each clock period |
| `oeis.py` | Loads the OEIS sequences from `data/oeis/top2000.jsonl` |

### `data/oeis/`
`top2000.jsonl`: terms of the 2,000 most interesting OEIS entries.

## What is still written by hand
The cell rule and `core/`; everything in `boxes/`; the targets; the seed searcher in `_build.py`. Everything else (clock ring for word search, memory bit, word register, counters, recurrences, library entries) is found.
