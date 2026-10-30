# bmsynth

A synthesizer built on one cell rule: y' = z XNOR OR(terms), where a term is a cell or a pair of cells (AND).

`experiments/main.py` builds a small seed (278 cells) and runs `net()`. The net grows itself from targets into a
single-cycle LODA machine (9,483 cells, 767 targets, about 60 s). What it builds is described in
`notes/machine-built.md` (in the project's shared notes); the run log is `experiments/results/main_v4_partsA-K.txt`.

| folder | what |
|---|---|
| `core/` | the concept: `cell.py` (the rule), `net.py` (Net), `box.py` (a box is a net), `maker.py` (a cell that makes cells) |
| `accel/` | speed only: `fastnet.py` (numba, event-driven, same result tick for tick) |
| `targets/` | descriptions of targets only, no nets: the target box and parts A to K |
| `experiments/` | `main.py` (the seed), `watch.py` (observer), `fewest.py` and `gridsearcher.py` (seed helpers) |
| `data/oeis/` | the top-2000 OEIS sequences, for the parts still to come |

Run: `python3 experiments/main.py`, or `python3 experiments/watch.py [seconds]` to watch it.
