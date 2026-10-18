"""Box file: the searcher. Placed only through the net:
    net.place_box('searcher.SEARCH', call, [y, truth, x], [op, cell, a, b, done, found, cand], slots=..., graph=..., n_in=...)

  SEARCH  a grid search that edits the net through BUILD (boxes/builder.py). It drives BUILD's op/cell/a/b ports and
          reads the candidate's output y, the target's truth table, and the input word x (driven by the net).

  in-cell slots  (op, cell, options): settings inside one cell; each option is an (a, b) pair of table positions, or
                 None = no edit. op 2 = connect the pair, op 4 = set z to a. One option per slot (mixed radix).
  graph          a list of connections between cells (cell, a, b); any subset of them may be on.
  order          the graph is the outer loop: no graph connections, then each single one, then each two, ... up to
                 all of them; for every graph subset, every combination of the in-cell slots (the inner, fast loop).
                 There is no cap: it goes through the whole space unless something stops the run.
  per candidate, one tick each:
     edit       only what differs from the previous candidate: disconnect pairs no longer wanted, connect new ones,
                set z where it changed
     settle     `settle` ticks of nothing
     test       watch x; each time x has stayed the same for `hold` ticks, the checker compares y with bit x of the
                truth table, until every input value 0 .. 2^n_in - 1 has been checked (or one fails)
     halt       all matched: done = found = 1, cand = candidate number, the edits stay and the search stops
  When every candidate failed: done = 1, found = 0.
"""
import numpy as np
from math import prod
from itertools import combinations


def SEARCH(slots, n_in, graph=(), hold=4, settle=2):
    # RULE VIOLATION (PEIXUAN, 2026-10-17): hand-written from scratch, a primer for building the counter, checker and
    # halt out of cells later; it does not replace cells already found in the net.
    """SEARCH(lanes, y, truth, x) -> (op, cell, a, b, done, found, cand). One lane."""
    inner = prod(len(o) for _, _, o in slots)

    def wanted(G, v):
        z, pairs = {}, set()
        for op, cell, opts in slots:
            v, i = divmod(v, len(opts))
            if opts[i] is None: continue
            if op == 4: z[cell] = opts[i][0]
            else: pairs.add((cell, *opts[i]))
        pairs.update(graph[g] for g in G)
        return z, pairs

    def candidates():
        for k in range(len(graph) + 1):
            for G in combinations(range(len(graph)), k):
                for v in range(inner): yield G, v

    def machine():
        idle = (0, 0, 0, 0)
        y, tt, x = yield None
        cur_z, cur_p, n = {}, set(), 0
        for n, (G, v) in enumerate(candidates()):
            z, p = wanted(G, v)
            ed = [(3, *e) for e in sorted(cur_p - p)] + [(2, *e) for e in sorted(p - cur_p)]
            ed += [(4, c, a, 0) for c, a in sorted(z.items()) if cur_z.get(c) != a]
            cur_z.update(z); cur_p = p
            for e in ed: y, tt, x = yield (*e, 0, 0, n)
            for _ in range(settle): y, tt, x = yield (*idle, 0, 0, n)
            seen, ok, last, run = set(), True, None, 0
            while ok and len(seen) < 2 ** n_in:
                run = run + 1 if x == last else 1
                last = x
                if run == hold and x not in seen:
                    seen.add(x)
                    ok = (y & 1) == (tt >> x & 1)
                y, tt, x = yield (*idle, 0, 0, n)
            if ok:
                while True: yield (*idle, 1, 1, n)
        while True: yield (*idle, 1, 0, n + 1)

    m = machine(); next(m)

    def run(lanes, y, truth, x):
        assert len(lanes) == 1, 'SEARCH runs on one lane'
        return tuple(np.array([v], np.int64) for v in m.send((int(y[0]), int(truth[0]), int(x[0]))))
    return run
