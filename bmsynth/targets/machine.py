"""REFERENCE blackboxes for the plan's machine parts (M1-M3), as boxes: Net(f, n_in, n_out) (net.py).

Each one says WHAT the net must produce, never how. None of them is placed in the net. A number travels on a bit
line and a valid line, as in ops.py. M2 and M3 run another part: they send it a number on `go` and read its
answer on `back`; the part is wired outside the box.

    M1 register   in: w (number), read (one line, a rise asks)    out: r (the last w, however much later)
    M2 loop       in: k, s, back (numbers)                        out: go, result
                  sends s on go, takes back as the new s, k times; then sends s on result
    M3 call       in: arg, back (numbers)                         out: go, result
                  sends arg on go; the part's answer on back comes out on result
    MACHINE       {name: (make the box, reference, needs)}
"""
from ops import Net, In, bits, send


def m1_register():
    w, st = In(), {'v': 0, 'last': 0, 'out': []}

    def f(wb, wv, rd):
        x = w.feed(wb, wv)
        if x is not None: st['v'] = x
        if rd and not st['last']: st['out'][:] = bits(st['v'])
        st['last'] = rd
        return send([st['out']])
    return Net(f, 3, 2)


def m2_loop_box():
    k, s, back = In(), In(), In()
    st = {'k': None, 's': None, 'run': 0, 'busy': 0, 'left': 0, 'go': [], 'res': []}

    def f(kb, kv, sb, sv, bb, bv):
        a, b, c = k.feed(kb, kv), s.feed(sb, sv), back.feed(bb, bv)
        if a is not None: st['k'] = a
        if b is not None: st['s'] = b
        if c is not None and st['busy']: st['s'], st['left'], st['busy'] = c, st['left'] - 1, 0
        if not st['run'] and st['k'] is not None and st['s'] is not None: st['run'], st['left'] = 1, st['k']
        if st['run'] and not st['busy']:
            if st['left'] == 0:
                st['res'][:] = bits(st['s'])
                st['run'], st['k'], st['s'] = 0, None, None
            else:
                st['go'][:] = bits(st['s'])
                st['busy'] = 1
        return send([st['go'], st['res']])
    return Net(f, 6, 4)


def m3_call_box():
    a, back, st = In(), In(), {'go': [], 'res': []}

    def f(ab, av, bb, bv):
        x, y = a.feed(ab, av), back.feed(bb, bv)
        if x is not None: st['go'][:] = bits(x)
        if y is not None: st['res'][:] = bits(y)
        return send([st['go'], st['res']])
    return Net(f, 4, 4)


# The same parts as plain Python (used by plan_targets.check to test the chain links in big.py)
class M1Register:
    """REFERENCE M1 register: write(v) keeps v; read() gives back the last v written, however many steps later."""
    def __init__(self): self.v = 0
    def write(self, v): self.v = v
    def read(self): return self.v


def m2_loop(body, k, state):
    """REFERENCE M2 loop: apply body to state k times. body is any earlier found part (state -> state)."""
    for _ in range(k):
        state = body(state)
    return state


def m3_call(program, *args):
    """REFERENCE M3 call: a kept program runs as one operator; the result equals running the program itself."""
    return program(*args)


# name -> (make the box, reference, needs); needs = earlier targets (targets/rules.md)
MACHINE = {
    'M1': (m1_register, M1Register, ['O1']),
    'M2': (m2_loop_box, m2_loop, ['M1', 'O4']),
    'M3': (m3_call_box, m3_call, ['M1']),
}
