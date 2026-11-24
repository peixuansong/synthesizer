# bmsynth

A synthesizer built on one cell rule: y' = z XNOR OR(xs), where an x is a cell or a pair of cells (AND).
A net holds the cells and their connections; cells can copy their inputs (cp) and connect cells (cn), see `net.py`.

| folder | what |
|---|---|
| `net.py` | the concept: Net (cells, connections, the rule, cp and cn); a box is Net(f, n_in, n_out) |
| `accel/` | speed only (none yet) |
| `boxes/` | hand-written boxes (none yet) |
| `targets/` | targets only, as boxes: `ops.py` (O1-O11), `machine.py` (M1-M3), `big.py` (B1-B10), `seqs.py` (OEIS), `plan_targets.py` (all + check) |
| `seed/` | `main.py` (the seed) |
| `data/oeis/` | the top-2000 OEIS sequences |

Each folder's `rules.md` says what a change there may do. `seed/main.py` does not run until the new
seed (plan step 4b) replaces it.
