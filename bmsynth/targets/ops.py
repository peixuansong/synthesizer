"""REFERENCE blackboxes for the plan's cell operators (O1-O11), as boxes: Net(f, n_in, n_out) (net.py).

Each function is a reference: it says WHAT the net must produce, never how. None of them is placed in the net.
Numbers are whole numbers >= 0. A result that would be negative is 0 (as in targets/blocks.py).

A number travels on two cells, as in boxes/sequence.py: a bit line (lowest bit first, one bit per tick) and a valid
line (1 while the bits flow). A number ends when its valid line falls.
    serial_box(fn, n_in, n_out)   the box for fn: inputs (bit, valid) per operand, outputs (bit, valid) per result.
                                  Once every operand has ended, it sends fn's result(s), then waits again.
    OPS                           {name: (make the box, reference function, needs)}
"""
import os, sys
_B = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
for _p in (_B, os.path.join(_B, 'boxes')):
    if _p not in sys.path: sys.path.insert(0, _p)
from net import Net
from sequence import bits, value


class In:
    """Reads one number line pair: feed(bit, valid) gives the number on the tick its valid line falls, else None."""
    def __init__(self, signed=False): self.bs, self.on, self.signed = [], 0, signed

    def feed(self, b, v):
        if v: self.bs.append(b)
        end, self.on = self.on and not v, v
        if end:
            x, self.bs = value(self.bs, self.signed), []
            return x


def send(queues):
    """One tick of output: for each queue of bits, (next bit, 1), or (0, 0) when it is empty."""
    return [y for q in queues for y in ((q.pop(0), 1) if q else (0, 0))]


def serial_box(fn, n_in, n_out=1):
    ins, got, out = [In() for _ in range(n_in)], [None] * n_in, [[] for _ in range(n_out)]

    def f(*x):
        for j, r in enumerate(ins):
            v = r.feed(x[2 * j], x[2 * j + 1])
            if v is not None: got[j] = v
        if None not in got:
            y = fn(*got)
            out[:] = [bits(v) for v in (y if isinstance(y, tuple) else (y,))]
            got[:] = [None] * n_in
        return send(out)
    return Net(f, 2 * n_in, 2 * n_out)


def target(fn, n_in, needs, n_out=1):
    """(make the box, reference function, needs) for one target."""
    return (lambda: serial_box(fn, n_in, n_out)), fn, needs


# O. Cell operators (plan: found by S0 over cell wirings, checked by BOXO)

def o1_copy(x):
    """REFERENCE O1 bit copy: x."""
    return x


def o2_add(a, b):
    """REFERENCE O2 add: a + b."""
    return a + b


def o3_sub(a, b):
    """REFERENCE O3 subtract: a - b, or 0 when b > a."""
    return max(a - b, 0)


def o4_compare(a, b):
    """REFERENCE O4 compare: 1 if a >= b, else 0."""
    return int(a >= b)


def o5_equal(a, b):
    """REFERENCE O5 equal: 1 if a == b, else 0."""
    return int(a == b)


def o6_min(a, b):
    """REFERENCE O6 min."""
    return min(a, b)


def o7_max(a, b):
    """REFERENCE O7 max."""
    return max(a, b)


def o8_double(x):
    """REFERENCE O8 double: 2x."""
    return 2 * x


def o9_halve(x):
    """REFERENCE O9 halve: x // 2 (drops the low bit)."""
    return x // 2


def o10_lowbit(x):
    """REFERENCE O10 low bit: x mod 2."""
    return x % 2


def o11_mask(x, bit):
    """REFERENCE O11 mask: x if bit is 1, else 0."""
    return x if bit else 0


# name -> (make the box, reference function, needs); needs = earlier targets (targets/rules.md)
OPS = {
    'O1': target(o1_copy, 1, []), 'O2': target(o2_add, 2, []), 'O3': target(o3_sub, 2, []),
    'O4': target(o4_compare, 2, []), 'O5': target(o5_equal, 2, []), 'O6': target(o6_min, 2, []),
    'O7': target(o7_max, 2, []), 'O8': target(o8_double, 1, []), 'O9': target(o9_halve, 1, []),
    'O10': target(o10_lowbit, 1, []), 'O11': target(o11_mask, 2, []),
}
