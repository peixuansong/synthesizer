"""A grid searcher made only of cells (core/cell.py), to be added into one net (core/net.py).

Words used here:
    hold       a stretch of H ticks during which the inputs keep one pattern
    cycle      one settling hold (pattern 0) followed by one hold per input pattern
    slot       a programmable cell: y = cfg[0] XNOR OR( cfg[k+1] AND source k ), so its config bits pick
               OR / NOR (cfg[0]) and which sources it reads
    candidate  two layers of slots; its config is the counter's bits, so every count is one candidate wiring
    counter    a binary counter of cells that steps to the next candidate after a cycle with a mismatch

Every cycle the candidate and the target see the same inputs; a checker compares their outputs near the end of
each hold. A mismatch moves the counter on; a cycle with no mismatch sets `found`, and the counter stops.
"""
from cell import Cell


def cell(net, z=1, y=0, terms=()):
    """A new cell in net: z, start bit y, and terms (a cell, or a pair of cells = their AND)."""
    c = Cell(z=z, y=y)
    for t in terms: (t if isinstance(t, tuple) else (t,)) >> c
    net += c
    return c


def delay(net, x): return cell(net, terms=[x])
def NOT(net, x): return cell(net, z=0, terms=[x])


def stimulus(net, n_in, H):
    """A ring of cells drives the inputs through every pattern, each held H ticks, after one settling hold.
    Returns (inputs, strobe = 1 once at the end of each tested hold, end = 1 when a new cycle starts)."""
    L = ((1 << n_in) + 1) * H
    ring = [cell(net, y=int(k == 0)) for k in range(L)]
    for k, r in enumerate(ring): ring[k - 1] >> r
    pattern = lambda k: k // H - 1                          # -1 = the settling hold
    x = [cell(net, terms=[r for k, r in enumerate(ring) if pattern(k) >= 0 and pattern(k) >> i & 1]) for i in range(n_in)]
    strobe = cell(net, terms=[ring[k] for k in range(H, L) if k % H == H - 1])
    end = cell(net, terms=[ring[L - 1]])
    return x, strobe, end


def sources(net, u):
    """Each cell of u delayed one tick, and the AND of every pair of them (also one tick): same timing for all."""
    return [delay(net, a) for a in u] + [cell(net, terms=[(a, b)]) for i, a in enumerate(u) for b in u[i + 1:]]


def slot(net, srcs, cfg):
    return cell(net, z=cfg[0], terms=list(zip(cfg[1:], srcs)))


def candidate(net, x, cfg, hidden=2):
    """Layer 1: `hidden` slots over sources(x). Layer 2: one slot over sources(layer 1). cfg: the config bit cells."""
    s1 = sources(net, x); w1 = 1 + len(s1)
    h = [slot(net, s1, cfg[i * w1:(i + 1) * w1]) for i in range(hidden)]
    s2 = sources(net, h)
    return slot(net, s2, cfg[hidden * w1:hidden * w1 + 1 + len(s2)])


def n_cfg(n_in, hidden=2):
    """How many config bits candidate() reads."""
    w = lambda n: 1 + n + n * (n - 1) // 2
    return hidden * w(n_in) + w(hidden)


def counter(net, go_a, go_b, n):
    """n-bit binary counter, +1 on each tick where go_a AND go_b. Each bit b has a twin nb = NOT b so that it
    toggles in one tick: b' = (b AND NOT c) OR (NOT b AND c), c = the bit's carry (with its twin nc = NOT c).
    Twins start at 1, since their partner starts at 0."""
    c, nc = cell(net, terms=[(go_a, go_b)]), cell(net, z=0, y=1, terms=[(go_a, go_b)])
    bits = []
    for _ in range(n):
        b, nb = Cell(y=0), Cell(y=1)
        (b, nc) >> b; (nb, c) >> b; (nb, nc) >> nb; (b, c) >> nb
        net += b; net += nb
        bits.append(b)
        c, nc = cell(net, terms=[(c, b)]), cell(net, z=0, y=1, terms=[(c, b)])
    return bits


def searcher(net, stim, target, hidden=2):
    """The whole grid searcher around the target's output cell. stim = stimulus(...), whose inputs also feed
    the target. Returns (found, config bits, candidate output)."""
    x, strobe, end = stim
    n = n_cfg(len(x), hidden)
    W = Cell(); net += W                                   # 1 once this cycle saw a mismatch
    d2 = delay(net, delay(net, end))
    dec, ndec = cell(net, terms=[d2]), cell(net, z=0, y=1, terms=[d2])   # decide 3 ticks after the cycle ends
    bits = counter(net, dec, W, n)                         # step on: decide AND mismatch seen
    out = candidate(net, x, bits, hidden)
    eq = cell(net, z=out, terms=[target])                  # out XNOR target
    neq = NOT(net, eq)
    s2 = delay(net, delay(net, strobe))                    # strobe, delayed like neq
    (W, ndec) >> W; (s2, neq) >> W                         # keep, cleared after deciding; set on a mismatch
    passed = cell(net, z=0, terms=[ndec, W])               # NOR(not decide, W) = decide AND no mismatch
    found = Cell(); found >> found; passed >> found; net += found
    return found, bits, out
