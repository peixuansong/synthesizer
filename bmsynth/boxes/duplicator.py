"""Box file: the duplicator. Placed only through the net (net.place_box('duplicator.DUPLICATE', ..., **params)).

  DUPLICATE  takes a circuit from the library, duplicates it n times side by side and wires the copies' inputs by
             hand (each input either one bit per copy or one bit shared by all copies); the copies' outputs form
             one word. It stands in for n pasted copies of that circuit, one tick per call, using the cell rule.

Hand-written: which circuit, how many copies and how the inputs are shared are given by whoever places it.
"""
import numpy as np
from celleval import _CellSpace, _decode, _kind, _CELL         # the library-entry format is defined once, in celleval


def DUPLICATE(stages, n, share, K=64, max_inputs=3):
    # RULE VIOLATION (PEIXUAN, 2026-10-16): hand-written from scratch; it does not replace cells already found in the net.
    """DUPLICATE(lanes, *K library words, select word, *inputs) -> (out word,).
    select: the group tag of the library entry to duplicate (0 copies run until that entry exists).
    share: one letter per circuit input, 'w' = copy i reads bit i of that input word, 's' = every copy reads bit 0.
    State: each lane keeps the cells of its n copies (all start at 0); one call = one tick of every copy."""
    spaces = [_CellSpace(k, stages) for k in range(max_inputs + 1)]
    state, circ = {}, {}

    def circuit(entry):
        if entry not in circ:
            nin, _, g = _decode(entry)
            circ[entry] = (nin, spaces[nin].decode(g))
        return circ[entry]

    def run(lanes, *words):
        lib, sel, ins = words[:K], words[K], words[K + 1:]
        out = np.zeros(len(lanes), dtype=object)
        bits = np.arange(n, dtype=object)
        for i, l in enumerate(lanes):
            entry = next((int(w[i]) for w in lib if _kind(w[i]) == _CELL and _decode(w[i])[1] == int(sel[i])), None)
            if entry is None: continue
            nin, (m, cells) = circuit(entry)
            u = state.setdefault((int(l), entry), np.zeros((m, n), bool))
            x = [np.array([(int(ins[j][i]) >> (b if share[j] == 'w' else 0)) & 1 for b in range(n)], bool) for j in range(nin)]
            src = [np.zeros(n, bool), np.ones(n, bool)] + x + list(u)
            new = np.empty_like(u)
            for j, (z, pairs) in enumerate(cells):
                acc = np.zeros(n, bool)
                for a, b in pairs: acc |= src[a] & src[b]
                new[j] = (z == 1) == acc
            state[(int(l), entry)] = new
            out[i] = int(sum(int(v) << int(b) for b, v in zip(bits, new[m - 1])))
        return (out,)
    return run
