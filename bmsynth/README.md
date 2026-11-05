# bmsynth

A synthesizer built on one cell rule: y' = z XNOR OR(xs), where an x is a cell or a pair of cells (AND).
A net holds the cells and their connections; cells can copy their inputs (cp) and connect cells (cn), see `net.py`.

| folder | what |
|---|---|
| `net.py` | the concept: Net (cells, connections, the rule, cp and cn); a box is Net(f, n_in, n_out) |
| `accel/` | speed only: `fastnet.py` (the same net, ticked with numba) |
| `boxes/` | hand-written IO boxes: `player.py` (plays the targets in turn), `sequence.py` (OEIS evaluators) |
| `targets/` | targets only: `ladder.py` (the ordered list: gates, memory, serial, OEIS), `oeis.py` |
| `experiments/` | `main.py`: the seed and one net run |
| `data/oeis/` | the top-2000 OEIS sequences |

Run: `python3 experiments/main.py [seconds]` (needs numpy and numba). Each folder's `rules.md` says what a
change there may do.
