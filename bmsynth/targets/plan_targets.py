"""All the plan's targets (notes/plan.md) as REFERENCE blackboxes (boxes: Net(f, n_in, n_out)), with their needs.

    TARGETS     {name: (make the box, reference, needs)}, in the plan's order: O, M, B, Q
    missing()   needs that no target defines (should be empty)
    check()     feeds numbers as bits into every box and compares what comes out with the reference

Left out: P1-P7, because the plan says their list needs PEIXUAN's acceptance first (rule 3).
Q needs every O, M and B target: which of them a sequence uses is for the net to find (plan: "the order comes
only from the net's own finds").

Run this file to check every target (seconds): python3 bmsynth/targets/plan_targets.py
"""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ops import OPS, In, bits
from machine import MACHINE, m2_loop
from big import BIG
from seqs import SEQS

TARGETS = {**OPS, **MACHINE, **BIG}
_TOOLS = list(TARGETS)
TARGETS.update({a: (s.box, s, _TOOLS) for a, s in SEQS.items()})


def missing():
    return sorted({d for _, _, needs in TARGETS.values() for d in needs if d not in TARGETS})


def num(x, signed=False):
    """The two input lines of number x: its bits, and a valid line of 1s."""
    b = bits(x, signed)
    return [b, [1] * len(b)]


def run(box, lines, ticks, signed=False):
    """Drive the first input cells of box with `lines` (one bit per tick, then 0) and return, for each output pair
    (bit, valid), the numbers it sent. Input cells that are not driven keep their own wiring."""
    outs, got = [In(signed) for _ in box.outputs[::2]], [[] for _ in box.outputs[::2]]
    for t in range(ticks):
        for c, q in zip(box.inputs, lines): box.ys[c] = q[t] if t < len(q) else 0
        box(ticks=1)
        for j, o in enumerate(outs):
            v = o.feed(box.ys[box.outputs[2 * j]], box.ys[box.outputs[2 * j + 1]])
            if v is not None: got[j].append(v)
    return got


def with_part(make, n_in, part):
    """A loop or call box wired to a part: its go outputs feed the part, the part's answer feeds its back inputs."""
    c = make() + part
    o, i = c.outputs, c.inputs
    for s, d in ((o[0], i[n_in]), (o[1], i[n_in + 1]), (o[4], i[n_in - 2]), (o[5], i[n_in - 1])): c._link(s, d)
    return c


def check(tries=30, top=32):
    """Every box against its reference, on random numbers below `top`; then the chain links in big.py."""
    R = random.Random(0)
    for name, (make, fn, _) in {**OPS, **BIG}.items():
        for _ in range(tries):
            box = make()
            xs = [R.randrange(top) for _ in box.inputs[::2]]
            want = fn(*xs)
            want = list(want) if isinstance(want, tuple) else [want]
            got = run(box, sum((num(x) for x in xs), []), 30 + max(len(bits(w)) for w in want))
            assert [g[:1] for g in got] == [[w] for w in want], (name, xs, got, want)
    for _ in range(tries):
        v, k, s = R.randrange(top), R.randrange(5), R.randrange(top)
        assert run(MACHINE['M1'][0](), num(v) + [[0] * 20 + [1]], 60)[0] == [v]
        got = run(with_part(MACHINE['M2'][0], 6, OPS['O8'][0]()), num(k) + num(s), 40 + 30 * k)
        assert got[1] == [m2_loop(lambda x: 2 * x, k, s)], ('M2', k, s, got)
        got = run(with_part(MACHINE['M3'][0], 4, OPS['O8'][0]()), num(s), 60)
        assert got[1] == [2 * s], ('M3', s, got)
    for s in SEQS.values():
        n = s.offset + R.randrange(len(s.terms))
        idx, sg = num(n, s.offset < 0), any(t < 0 for t in s.terms)
        lines = idx + [[0] * (len(idx[0]) + 1) + [1]]
        assert run(s.box(), lines, len(idx[0]) + 10 + len(bits(s.a(n), sg)), sg)[0] == [s.a(n)], s
    # Chain links: B1.3b repeated `bits` times from r = 0 gives B1.4; B2.2 repeated gives B2.3 and B3
    f = lambda n: BIG[n][1]
    for _ in range(2000):
        a, b = R.randrange(1 << 16), R.randrange(1 << 16)
        r, x, y = m2_loop(lambda s: f('B1.3b')(*s), 16, (0, a, b))
        assert r == f('B1.4')(a, b) == a * b
        assert m2_loop(lambda r: f('B1.2')(r, a, 1), b % 64, 0) == f('B1.1')(a, b % 64)
        if b:
            a2 = a % 512
            r, q = m2_loop(lambda s: f('B2.2')(s[0], b, s[1]), a2, (a2, 0))
            assert (q, r) == (f('B2.3')(a2, b), f('B3')(a2, b)) == (a2 // b, a2 % b)
        n = R.randrange(1, 6)
        k = f('B7')(a, n); assert k ** n <= a < (k + 1) ** n
        if a and b > 1:
            k = f('B8')(a, b); assert b ** k <= a < b ** (k + 1)
    return True


if __name__ == '__main__':
    assert not missing(), missing()
    check()
    q = list(SEQS.values())
    print(f"O {len(OPS)}, M {len(MACHINE)}, B {len(BIG)} (links included), Q {len(q)}: {len(TARGETS)} targets")
    print("Q that fit in 8/16/32/64 bits:", *[sum(s.fits(w) for s in q) for w in (8, 16, 32, 64)])
    print("missing needs:", missing() or "none", "| check: passed (every box matches its reference)")
