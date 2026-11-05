"""A fewest-first counter, made only of cells. It lists the sets of 0, then 1, 2 and 3 setting bits (connections),
one set per try, so every wiring with fewer connections comes before any wiring with more.

Words:
    pointer   a row of B cells with at most one 1: the position of one chosen setting bit. Three pointers,
              P1 < P2 < P3; a set of c connections uses the first c pointers
    level     how many pointers are in use: cells L0..L3, exactly one of them is 1
    end       a pointer at the last position it may take (the later pointers still need room above it)
    next      cells N that always show the set after the current one (steady during a try); on `go` the
              pointers copy N, on `clr` they empty (level 0)
The set after (P1, P2, P3): move the last pointer up one; if it is at its end, move the one before it up one
and put the later ones just above it; if all are at their ends, use one more pointer (at 0, 1, 2).
After 3 pointers at their ends: done.
"""
from cell import Cell
import gridsearcher as G


def fewest(net, go, clr, B):
    """go, clr: one-tick pulses. Returns (settings: B cells, setting k = 1 when a pointer is at k;
    done: one tick when every set of up to 3 has been listed)."""
    c = lambda **k: G.cell(net, **k)
    P = [[Cell() for _ in range(B)] for _ in range(3)]
    L = [Cell(y=int(v == 0)) for v in range(4)]
    no = lambda x: c(z=0, terms=[x])
    # the step to take, from the level and the ends (depth <= 3, steady between tries)
    a3, a2 = c(terms=[(L[3], P[2][B - 1])]), c(terms=[(L[2], P[1][B - 1])])
    b3 = c(terms=[(a3, P[1][B - 2])])
    m = dict(s33=c(terms=[(L[3], no(P[2][B - 1]))]), s32=c(terms=[(a3, no(P[1][B - 2]))]),
             s31=c(terms=[(b3, no(P[0][B - 3]))]), done=c(terms=[(b3, P[0][B - 3])]),
             s22=c(terms=[(L[2], no(P[1][B - 1]))]), s21=c(terms=[(a2, no(P[0][B - 2]))]),
             up2=c(terms=[(a2, P[0][B - 2])]), s11=c(terms=[(L[1], no(P[0][B - 1]))]),
             up1=c(terms=[(L[1], P[0][B - 1])]), up0=G.delay(net, L[0]))
    any_ = lambda *ks: c(terms=[m[k] for k in ks])
    shift = [any_('s31', 's21', 's11'), any_('s32', 's22'), m['s33']]        # pointer r moves up one
    from_prev = [None, any_('s31', 's21'), m['s32']]                        # r goes 2 above pointer r-1
    from_p1 = [None, None, m['s31']]                                        # P3 goes 3 above P1
    start = [any_('up0', 'up1', 'up2'), any_('up1', 'up2'), m['up2']]       # r restarts at position r
    keep = [no(any_('s31', 's21', 's11', 'up0', 'up1', 'up2')),
            no(any_('s32', 's22', 's31', 's21', 'up1', 'up2')), no(any_('s33', 's32', 's31', 'up2'))]
    # next pointers N (steady), then P' = P while no pulse, N on go, 0 on clr
    load, hold = G.delay(net, go), c(z=0, y=1, terms=[go, clr])          # hold starts at 1: keep the start state
    for r in range(3):
        for k in range(B):
            t = [(keep[r], P[r][k]), (shift[r], P[r][k - 1]) if k else None]
            if from_prev[r] and k >= 2: t.append((from_prev[r], P[r - 1][k - 2]))
            if from_p1[r] and k >= 3: t.append((from_p1[r], P[0][k - 3]))
            if k == r: t.append(start[r])
            n = c(terms=[x for x in t if x is not None])
            p = P[r][k]; (p, hold) >> p; (n, load) >> p; net += p
    nl = [no(m['up0']), c(terms=[m['up0'], (L[1], no(m['up1']))]),
          c(terms=[m['up1'], (L[2], no(m['up2']))]), c(terms=[m['up2'], (L[3], no(m['done']))])]
    for v in range(4):
        (L[v], hold) >> L[v]; (nl[v] if v else c(terms=[(L[0], nl[0])]), load) >> L[v]
        net += L[v]
    G.delay(net, clr) >> L[0]
    settings = [c(terms=[P[0][k], P[1][k], P[2][k]]) for k in range(B)]
    return settings, c(terms=[(go, m['done'])])
