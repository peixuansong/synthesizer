"""Box file: word arithmetic. Injected knowledge: what +, -, *, //, %, min, max do.

Placed only through the net: net.place_box('arith.OP', call, ins, outs, name='ADD', W=None).
Input words arrive unsigned; with W given they are read as W-bit two's complement. The net keeps the
low bits of the result, so everything wraps at the width of the output word.
"""
import numpy as np

_SCALAR = {                                     # the word ops (wordeval uses these too, in this order)
    'ADD': lambda x, y: x + y, 'SUB': lambda x, y: x - y, 'MUL': lambda x, y: x * y,
    'DIV': lambda x, y: x // y if y else 0, 'MOD': lambda x, y: x % y if y else 0,
    'MIN': min, 'MAX': max,
}


def _signed(v, W):
    v = np.asarray(v).astype(np.int64)
    return np.where(v >> (W - 1) & 1, v - (np.int64(1) << W), v) if W < 64 else v


def OP(name, W=None):
    # RULE VIOLATION (PEIXUAN, 2026-10-16): hand-written from scratch; it does not replace cells already found in the net.
    """The op over one or two input words (one input: the op applied to it twice)."""
    f = _SCALAR[name]
    def run(lanes, *xs):
        if W: xs = [_signed(x, W) for x in xs]
        if len(xs) == 1: xs = (xs[0], xs[0])
        return (np.array([f(int(a), int(b)) for a, b in zip(*xs)], dtype=object),)
    run.__name__ = name
    return run
