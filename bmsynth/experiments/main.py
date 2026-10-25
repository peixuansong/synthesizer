"""The main net: a target net from core/test_demo.py and a grid searcher (gridsearcher.py), in ONE net.

The searcher tries candidate wirings one after another until one gives the same outputs as the target on every
input pattern. Run:  python3 experiments/main.py [TARGET] [SECONDS]     (TARGET: AND OR NOR NAND XOR; default XOR)
net() runs forever and has no way to stop or report, so this file steps the net with net._tick() and watches
the `found` cell itself (see the note in the thread: this is an architectural gap in core/net.py).
"""
import sys, time
import _setup
from net import Net
import gridsearcher as G

H = 10                                                       # ticks per hold


def target(net, name, a, b):
    """The gate nets of test_demo.gates(), built on inputs a, b. Returns the output cell."""
    c = lambda **k: G.cell(net, **k)
    if name == 'AND': return c(terms=[(a, b)])
    if name == 'OR': return c(terms=[a, b])
    if name == 'NOR': return c(z=0, terms=[a, b])
    if name == 'NAND': return c(z=0, terms=[(a, b)])
    na, nb = G.NOT(net, a), G.NOT(net, b)                    # XOR: (a AND NOT b) OR (NOT a AND b)
    return c(terms=[(a, nb), (na, b)])


TRUTH = dict(AND=lambda a, b: a & b, OR=lambda a, b: a | b, NOR=lambda a, b: 1 - (a | b),
             NAND=lambda a, b: 1 - (a & b), XOR=lambda a, b: a ^ b)


def describe(bits):
    """The candidate a config spells out (observation only)."""
    v = [b.y for b in bits]
    def one(cfg, names):
        used = [n for n, on in zip(names, cfg[1:]) if on]
        return f"{'OR' if cfg[0] else 'NOR'}({', '.join(used) or '-'})"
    h0, h1, out = v[0:4], v[4:8], v[8:12]
    return f"h0 = {one(h0, ['a', 'b', 'a.b'])};  h1 = {one(h1, ['a', 'b', 'a.b'])};  y = {one(out, ['h0', 'h1', 'h0.h1'])}"


def check(bits, name):
    """Independent check: a fresh small net with the found config held fixed, probed on all 4 inputs."""
    for a_bit in (0, 1):
        for b_bit in (0, 1):
            net = Net()
            a, b = G.cell(net, y=a_bit), G.cell(net, y=b_bit)
            a >> a; b >> b
            cfg = [G.cell(net, y=k.y) for k in bits]
            for k in cfg: k >> k
            y = G.candidate(net, [a, b], cfg)
            for _ in range(6): net._tick()
            if y.y != TRUTH[name](a_bit, b_bit): return False
    return True


def main(name='XOR', seconds=150):
    net = Net()
    stim = G.stimulus(net, 2, H)
    a, b = stim[0]
    net.inputs += [a, b]
    t_out = target(net, name, a, b)
    found, bits, out = G.searcher(net, stim, t_out)
    net.outputs += [found]
    cycle = 5 * H
    print(f'main net: {len(net.cells)} cells; target {name}; {1 << len(bits)} candidates, {cycle} ticks each')
    t0, ticks = time.time(), 0
    while not found.y and time.time() - t0 < seconds:
        net._tick(); ticks += 1
    sec = time.time() - t0
    count = sum(b.y << k for k, b in enumerate(bits))
    if not found.y:
        print(f'not found after {ticks:,} ticks, {sec:.0f} s (at candidate {count})'); return
    print(f'found at tick {ticks:,} ({sec:.1f} s), candidate {count}:  {describe(bits)}')
    print('independent check on all 4 inputs:', 'correct' if check(bits, name) else 'WRONG')


if __name__ == '__main__':
    main(*(sys.argv[1:2] or ['XOR']), *[float(s) for s in sys.argv[2:3]])
