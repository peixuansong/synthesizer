"""Black boxes for the ladder's targets (targets/ladder.py). Each says only WHAT to produce, never how.

    make() returns a fresh f(*input bits) -> output bits, called once per tick.

Kinds:
    gate(k)           2 inputs a, b -> 1 output; bit (2a + b) of k
    stateful(...)     a target with one state, e.g. DELAY, TOGGLE, LATCH, serial add
    word(fn, arity)   numbers as bits, lowest first. Inputs: one bit per operand, and valid (1 while the operands'
                      bits flow; all operands are padded to the same length). When valid falls, it sends fn(...)'s
                      bits on `bit`, with `valid` = 1 while they last. Outputs: bit, valid
    register()        inputs bit, valid, read: keeps the last number sent in; on a rise of read, sends it back
    counter()         input tick: on each rise, sends the count so far (1, 2, 3 ...) as a word
"""
from math import comb, factorial, gcd, isqrt


def bits(v):
    """v >= 0 as bits, lowest first; 0 is one bit."""
    out = [v & 1]; v >>= 1
    while v: out.append(v & 1); v >>= 1
    return out


def gate(k):
    return lambda: (lambda a, b: (k >> (2 * a + b) & 1,))


def stateful(step, s0):
    """step(s, *bits) -> (new s, output bits)."""
    def make():
        st = [s0]
        def f(*b):
            st[0], out = step(st[0], *b)
            return out
        return f
    return make


def _sender():
    st = {'out': []}
    def send(v): st['out'] = bits(v)
    def next_out(): return (st['out'].pop(0), 1) if st['out'] else (0, 0)
    return send, next_out


def word(fn, arity):
    def make():
        st = {'ops': [[] for _ in range(arity)], 'v': 0}
        send, next_out = _sender()
        def f(*b):
            *xs, v = b
            if v:
                for o, x in zip(st['ops'], xs): o.append(x)
            elif st['v']:
                send(max(0, fn(*[sum(x << i for i, x in enumerate(o)) for o in st['ops']])))
                st['ops'] = [[] for _ in range(arity)]
            st['v'] = v
            return next_out()
        return f
    return make


def register():
    def make():
        st = {'keep': [], 'new': [], 'v': 0, 'r': 0}
        send, next_out = _sender()
        def f(b, v, r):
            if v: st['new'].append(b)
            elif st['v']: st['keep'], st['new'] = st['new'], []
            if r and not st['r']: send(sum(x << i for i, x in enumerate(st['keep'])))
            st['v'], st['r'] = v, r
            return next_out()
        return f
    return make


def counter():
    def make():
        st = {'n': 0, 't': 0}
        send, next_out = _sender()
        def f(t):
            if t and not st['t']: st['n'] += 1; send(st['n'])
            st['t'] = t
            return next_out()
        return f
    return make


# LODA's ops as word targets (fn on non-negative words; a negative result is sent as 0)
OPS = {
    'ADD': (lambda a, b: a + b, 2), 'SUB': (lambda a, b: a - b, 2), 'MUL': (lambda a, b: a * b, 2),
    'DIV': (lambda a, b: a // b if b else 0, 2), 'MOD': (lambda a, b: a % b if b else 0, 2),
    'MIN': (min, 2), 'MAX': (max, 2), 'POW': (lambda a, b: a ** min(b, 64), 2),
    'BIN': (lambda a, b: comb(a, b), 2), 'GCD': (gcd, 2), 'FAC': (lambda a: factorial(min(a, 100)), 1),
    'NRT': (lambda a, b: round(a ** (1 / b)) if b else 0, 2), 'SQRT': (isqrt, 1),
    'EQU': (lambda a, b: int(a == b), 2), 'NEQ': (lambda a, b: int(a != b), 2),
}
