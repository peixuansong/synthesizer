"""The main experiment, version 2: the single instance of a net.

All searchers share one input pair x0 x1, driven by cells: a ring of 4·HOLD cells with one token; x0 and x1 are ORs of
ring cells, so the inputs step through 0, 1, 2, 3, each held HOLD ticks, forever.

Stage 1, single cell: one searcher per two-input gate (targets/gates.py). Each has a blank cell y, a SEARCH box
(boxes/searcher.py) and a BUILD box (boxes/builder.py). SEARCH picks y's z (ZERO, ONE, x0, x1) and which of the
pairs x0∧x1, x0, x1 it gets: 32 candidates.

Stage 2, mesh of 2 cells: starts when every stage-1 searcher is done, only for the gates stage 1 did not find. Each has
two blank cells c0, c1 (output c1). In-cell search (inner loop): each cell's z and pairs from ONE, x0, x1, as in
stage 1 (32 × 32). Graph search (outer loop): any subset of the 14 connections that read a cell (c0, c1, c∧x0, c∧x1,
c0∧c1 into c0 or c1, so loops are allowed), smallest subsets first. No cap; the only limit is wall-clock time.

Both boxes are RULE VIOLATIONS (stopgaps / primers).
"""
import time
import _setup
from net import ZERO, ONE
from lanes import LaneBoxNet as Net
from gates import GATES

HOLD = 4
LIMIT = 180                                          # seconds of wall-clock time


def ports(net, n): return [net.add_port() for _ in range(n)]


def NOT(net, a, init=0):
    c = net.add_cell(z=ZERO, init=init); net.connect(c, a); return c


def AND(net, nodes, name=None):
    """1 when every node is 1: NOT OR(NOT node), two cells deep (the NOTs start at 1 so it starts at 0)."""
    c = net.add_cell(z=ZERO, name=name)
    for n in nodes: net.connect(c, NOT(net, n, init=1))
    return c


def stimulus(net, n_in, hold):
    ring = [net.add_cell(init=int(k == 0)) for k in range(hold << n_in)]
    for k, r in enumerate(ring): net.connect(r, ring[k - 1])
    x = []
    for i in range(n_in):
        c = net.add_cell(name=f'x{i}')
        for k, r in enumerate(ring):
            if (k // hold) >> i & 1: net.connect(c, r)
        x.append(c)
    return x


def in_cell(c):
    """The in-cell slots for table position c: z from ZERO ONE x0 x1 (table 0..3), and each of x0∧x1, x0, x1 on or off."""
    return [(4, c, [(0, 0), (1, 0), (2, 0), (3, 0)]), (2, c, [None, (2, 3)]), (2, c, [None, (2, 1)]), (2, c, [None, (3, 1)])]


def searcher(net, call, x, cells, slots, graph, name):
    """Blank cells wired by a SEARCH + BUILD pair; BUILD's table is ZERO ONE x0 x1, then the cells. Output = last cell."""
    cs = [net.add_cell(name=f'{name}.c{i}') for i in range(cells)]
    tt = ports(net, 4)
    W = (4 + cells).bit_length()
    op, cell, a, b, done, found, cand = ports(net, 3), ports(net, W), ports(net, W), ports(net, W), ports(net, 1), ports(net, 1), ports(net, 32)
    net.place_box('builder.BUILD', ONE, [op, cell, a, b], [ports(net, 4)], net=net, source=[], nodes=[ZERO, ONE, *x, *cs])
    net.place_box('searcher.SEARCH', call, [[cs[-1]], tt, x], [op, cell, a, b, done, found, cand], slots=slots, graph=graph, n_in=2, hold=HOLD)
    return dict(cells=cs, y=cs[-1], tt=tt, done=done[0], found=found[0], cand=cand)


def observe(net, st, x, S, ticks=8 * HOLD):
    """Watch every searcher's output on every tick for two full input cycles: wrong = a tick where x has been steady
    for 3+ ticks and y differs from the truth table (stricter than SEARCH's checker, which looks once per hold)."""
    wrong, steady, last = {g: 0 for g in S}, 0, None
    for _ in range(ticks):
        st, _ = net.run(st, 1)
        xv = int(net.read(st, x)[0]); steady = steady + 1 if xv == last else 1; last = xv
        if steady >= 3:
            for g, s in S.items():
                if int(net.read(st, [s['y']])[0]) != GATES[g] >> xv & 1: wrong[g] += 1
    return st, wrong


def main(limit=LIMIT):
    net = Net(lanes=1)
    x = stimulus(net, 2, HOLD)

    S1 = {}
    for g in GATES:                                  # stage 1: one cell; SEARCH is called until it is done
        call = net.add_cell(z=ZERO, init=1)
        S1[g] = searcher(net, call, x, 1, in_cell(4), (), g)
        net.connect(call, S1[g]['done'])
    stage1 = AND(net, [s['done'] for s in S1.values()], 'stage1 done')

    graph = [(t, *p) for t in (4, 5) for p in ((4, 1), (5, 1), (4, 2), (4, 3), (5, 2), (5, 3), (4, 5))]
    S2 = {}
    for g in GATES:                                  # stage 2: mesh of 2 cells, only if stage 1 did not find it
        call = net.add_cell(); net.connect(call, stage1, NOT(net, S1[g]['found']))
        S2[g] = searcher(net, call, x, 2, in_cell(4) + in_cell(5), graph, f'{g} mesh')
    ok = []
    for g in GATES:
        c = net.add_cell(); net.connect(c, S1[g]['found']); net.connect(c, S2[g]['done']); ok.append(c)
    alldone = AND(net, ok, 'all done')

    print(f'one net: {len(net.cells)} cells, {len(net.boxes)} boxes; mesh space: 2^{len(graph)} graphs x 1024 in-cell = {2 ** len(graph) * 1024:,} candidates')
    st = net.state()
    for g, t in GATES.items():
        net.load(st, S1[g]['tt'], t); net.load(st, S2[g]['tt'], t)
    t0, ticks = time.time(), 0
    while True:
        st, t = net.run(st, 2000, stop=alldone); ticks += t
        if t < 2000 or time.time() - t0 > limit: break
    print(f'stopped after {ticks:,} ticks, {time.time() - t0:.0f} s ({"all done" if t < 2000 else "wall-clock limit"})\n')

    name = {ZERO: 'ZERO', ONE: 'ONE', x[0]: 'x0', x[1]: 'x1'}
    def wiring(c):
        p, z = net.pairs(c)
        return f"{name[z]} XNOR OR({', '.join(name[a] if b == ONE else name[a] + '∧' + name[b] for a, b in p) or '–'})"
    shown = {}
    for g in GATES:
        s1, s2 = S1[g], S2[g]
        if int(net.read(st, [s1['found']])[0]):
            name[s1['y']] = 'y'; shown[g] = s1
            print(f"{g:>15}  stage 1, candidate {int(net.read(st, s1['cand'])[0]):>6}:  y' = {wiring(s1['y'])}")
            continue
        n = int(net.read(st, s2['cand'])[0])
        name.update({s2['cells'][0]: 'c0', s2['cells'][1]: 'c1'})
        if int(net.read(st, [s2['found']])[0]):
            shown[g] = s2
            print(f"{g:>15}  mesh,    candidate {n:>6}:  c0' = {wiring(s2['cells'][0])};  c1' = {wiring(s2['cells'][1])}")
        else:
            print(f"{g:>15}  {'mesh gave up' if int(net.read(st, [s2['done']])[0]) else 'still searching'} after {n:,} candidates")
    st, wrong = observe(net, st, x, shown)
    bad = [g for g, w in wrong.items() if w]
    print(f'\nobservation over 2 more input cycles, every steady tick: {"all found circuits correct" if not bad else "WRONG: " + ", ".join(bad)}')
    return net


if __name__ == '__main__':
    main()
