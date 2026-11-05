"""The target player: an IO box that plays the targets of targets/ladder.py in turn, inside the net.

    player_box(targets, settle, D)
        inputs:  bit, valid (the candidate's two outputs), overflow (the counter has tried every wiring)
        outputs: i0, i1, i2 (the candidate's inputs), step (1 tick: try the next wiring), reset (1 tick: clear
                 the counter, a new target starts), found (1 tick, with reset, when the target was found)
    One try: `settle` ticks with all inputs 0 (the wiring changes), then one input vector per tick. The
    candidate must answer each vector D ticks later. A mismatch ends the try with `step`. Every answer right:
    the target is found, `reset`, next target. `overflow`: not found, `reset`, next target.
    Vectors and answers:
        gate       its 4 patterns on i0, i1; the answer is `bit` (valid is not checked)
        with state 32 random vectors (fixed seed); the answer is `bit`
        OEIS       for every stored term a(n): n's bits on i0, lowest first, with i1 = 1 while they last and
                   i2 = 1 on the first; the answer is a(n)'s bits on `bit`, from the same tick, with valid = 1
                   while they last, then valid = 0; 2 quiet ticks between terms. Sizes are dynamic
    box.log: [(name, 'found' | 'not found', tries, tick)]
"""
import random
from net import Net
from sequence import bits


def stream(t):
    """[(input vector, (wanted bit, wanted valid or None))] for one try of target t."""
    name, n_in, n_out, make = t
    if isinstance(make, tuple):                       # OEIS
        _, offset, terms = make
        signed, out = any(v < 0 for v in terms), []
        for k, v in enumerate(terms):
            if offset + k < 0: continue
            ix, ab = bits(offset + k), bits(v, signed)
            for j in range(max(len(ix), len(ab)) + 1):
                out.append(((ix[j] if j < len(ix) else 0, int(j < len(ix)), int(j == 0)),
                            (ab[j] if j < len(ab) else 0, int(j < len(ab)))))
            out += [((0, 0, 0), (0, 0))] * 2
        return out
    f = make()
    if n_in == 2 and not name.startswith(('DELAY', 'TOGGLE', 'LATCH', 'SERIAL')):
        vs = [(a, b) for a in (0, 1) for b in (0, 1)]
    else:
        rnd = random.Random(1)
        vs = [tuple(rnd.randint(0, 1) for _ in range(n_in)) for _ in range(32)]
    return [(tuple(v) + (0,) * (3 - len(v)), (f(*v)[0], None)) for v in vs]


def player_box(targets, settle=24, D=3):
    st = {'k': 0, 'tick': 0, 'tries': 0, 'done': False}
    log = []

    def start_try():
        st['s'], st['n'], st['t0'] = stream(targets[st['k']]), 0, None
        st['tries'] += 1

    def next_target(result):
        log.append((targets[st['k']][0], result, st['tries'], st['tick']))
        st['k'] += 1; st['tries'] = 0
        if st['k'] >= len(targets): st['done'] = True
        else: start_try()

    start_try()

    def f(bit, valid, overflow):
        st['tick'] += 1
        if st['done']: return 0, 0, 0, 0, 0, 0
        if overflow:
            next_target('not found'); return 0, 0, 0, 0, 1, 0
        if st['t0'] is None:
            st['n'] += 1
            if st['n'] < settle: return 0, 0, 0, 0, 0, 0
            st['t0'] = st['tick']
        s, i = st['s'], st['tick'] - st['t0'] - D     # the vector the candidate answers now
        if 0 <= i < len(s):
            wb, wv = s[i][1]
            if (wv is None and bit != wb) or (wv is not None and (valid != wv or (wv and bit != wb))):
                start_try(); return 0, 0, 0, 1, 0, 0
        if i >= len(s) - 1:
            next_target('found'); return 0, 0, 0, 0, 1, 1
        n = st['tick'] - st['t0']
        return (s[n][0] if n < len(s) else (0, 0, 0)) + (0, 0, 0)
    box = Net(f, 3, 6)
    box.log = log
    return box
