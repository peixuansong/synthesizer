"""The target list (plan step 4a), easiest first. Each target is a black box: inputs in, outputs out, one tick at a
time. It says only WHAT to produce, never how. The order is the dependency order; it may be changed, and targets
may be added or removed.

    TARGETS      [(name, n_in, n_out, make)]: make() returns a fresh f(*input bits) -> output bits
    box(t)       the target as a net box: Net(make(), n_in, n_out)

Rungs:
    1 gates      the 16 functions of two bits a, b
    2 memory     one bit kept across ticks
    3 serial     numbers as bits, lowest first; `start` = 1 on a number's first bit
    4 OEIS       the sequence box of plan step 2 (boxes/, not written yet), the easiest OEIS entries first,
                 then every other top-2000 entry in rank order
"""
import oeis
from net import Net


def gate(k):
    """Gate k: bit (2a + b) of k is the output for inputs a, b. 1 = NOR, 6 = XOR, 8 = AND, 14 = OR..."""
    return lambda: (lambda a, b: (k >> (2 * a + b) & 1,))


GATE_NAMES = {0: 'ZERO', 1: 'NOR', 2: 'B_AND_NOT_A', 3: 'NOT_A', 4: 'A_AND_NOT_B', 5: 'NOT_B', 6: 'XOR',
              7: 'NAND', 8: 'AND', 9: 'XNOR', 10: 'B', 11: 'A_IMPLIES_B', 12: 'A', 13: 'B_IMPLIES_A', 14: 'OR',
              15: 'ONE'}


def stateful(step, s0):
    """A target with one state s: step(s, *bits) -> (new s, output bits)."""
    def make():
        st = [s0]
        def f(*bits):
            st[0], out = step(st[0], *bits)
            return out
        return f
    return make


def _latch(v): return v, (v,)


MEMORY = [
    ('DELAY', 1, 1, stateful(lambda s, x: (x, (s,)), 0)),                       # y = x of the tick before
    ('TOGGLE', 1, 1, stateful(lambda s, t: (s ^ t, (s ^ t,)), 0)),             # flips when t = 1
    ('LATCH', 2, 1, stateful(lambda s, st, r: _latch((s | st) & (1 - r)), 0)), # set by st, cleared by r
]


def _inc(c, x, start):                       # carry c; x + 1, so the carry starts at 1 on each first bit
    c = 1 if start else c
    return x & c, (x ^ c,)


def _add(c, a, b, start):                    # a + b; the carry starts at 0 on each first bit
    c = 0 if start else c
    return (a & b) | (c & (a ^ b)), (a ^ b ^ c,)


SERIAL = [
    ('SERIAL_INC', 2, 1, stateful(lambda c, x, s: _inc(c, x, s), 0)),
    ('SERIAL_ADD', 3, 1, stateful(lambda c, a, b, s: _add(c, a, b, s), 0)),
]

# The easiest top-2000 entries (constant, linear, periodic), then the rest in rank order. make = None: the
# sequence box of plan step 2 plays them.
EASY_OEIS = ['A000004', 'A000012', 'A000007', 'A000035', 'A001477', 'A000027', 'A005843', 'A005408']


def oeis_list():
    rest = [f"A{d['n']:06d}" for d in sorted(oeis.oeis_targets(R=1, W=1 << 10), key=lambda d: d['rank'])]
    return EASY_OEIS + [a for a in rest if a not in EASY_OEIS]


TARGETS = ([(GATE_NAMES[k], 2, 1, gate(k)) for k in range(16)] + MEMORY + SERIAL
           + [(a, None, None, None) for a in oeis_list()])


def box(t):
    name, n_in, n_out, make = t
    return Net(make(), n_in, n_out)
