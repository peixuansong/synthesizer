"""The evaluators of plan step 2: two IO boxes for sequence targets.

Numbers travel as bits, lowest first, one per tick, with a `valid` line that is 1 while a number's bits flow.
Sizes are dynamic: 0 is one bit (0); other numbers use as many bits as they need. If a sequence has a negative
term, all its terms are sent in two's complement with a sign bit.

    sequence_box(terms, offset)   inputs: index bit, index valid, signal. Outputs: bit, valid. On a rise of signal
                              it sends term a(n) for the index n it was last sent.
    checker_box(n_terms, D, offset)
        inputs: target bit, target valid, candidate bit, candidate valid
        outputs: index bit, index valid, signal, pass, fail
        For each term k: it sends the index n = offset + k (bits + valid), then one signal pulse. It records the
        target's stream and checks that the candidate sends the same stream D ticks later. A mismatch makes `fail`
        1 for one tick and starts again from term 0. After all n_terms terms match, `pass` stays 1.
"""
from net import Net


def bits(v, signed=False):
    """v as bits, lowest first: the fewest bits that hold v (with a sign bit if signed)."""
    n = 1
    while not (-(1 << (n - 1)) <= v < (1 << (n - 1)) if signed else v < (1 << n)): n += 1
    return [(v >> i) & 1 for i in range(n)]


def value(bs, signed=False):
    """The number that bits bs (lowest first) hold."""
    v = sum(b << i for i, b in enumerate(bs))
    return v - (1 << len(bs)) if signed and bs and bs[-1] else v


def sequence_box(terms, offset=0):
    signed = any(t < 0 for t in terms)
    st = {'n': [], 'iv': 0, 'out': [], 'last': 0}

    def f(i, iv, signal):
        if iv and not st['iv']: st['n'] = []                 # a new index starts
        if iv: st['n'].append(i)
        st['iv'] = iv
        if signal and not st['last']:
            k = value(st['n'], offset < 0) - offset
            st['out'] = bits(terms[k], signed) if 0 <= k < len(terms) else []
        st['last'] = signal
        return (st['out'].pop(0), 1) if st['out'] else (0, 0)
    return Net(f, 3, 2)


def checker_box(n_terms, D=0, offset=0):
    st = {'k': 0, 'plan': [], 'want': [], 'got': [], 'seen': 0, 'ended': 0, 'pass': 0}

    def restart(k):
        st['k'], st['want'], st['got'], st['seen'], st['ended'] = k, [], [], 0, 0
        n = offset + k
        st['plan'] = [(b, 1, 0) for b in bits(n, offset < 0)] + [(0, 0, 0), (0, 0, 1)]   # index bits, gap, signal

    restart(0)

    def f(tb, tv, cb, cv):
        if st['pass']: return 0, 0, 0, 1, 0
        if st['plan']:
            i, iv, sig = st['plan'].pop(0)
            return i, iv, sig, 0, 0
        if not st['ended']:
            st['want'].append((tb, tv) if tv else (0, 0))
            st['seen'] |= tv
            st['ended'] = st['seen'] and not tv              # the target finished this term
        st['got'].append((cb, cv) if cv else (0, 0))
        if not st['ended'] or len(st['got']) < len(st['want']) + D: return 0, 0, 0, 0, 0
        if st['got'][D:] != st['want']:
            restart(0)
            return 0, 0, 0, 0, 1
        if st['k'] + 1 >= n_terms:
            st['pass'] = 1
            return 0, 0, 0, 1, 0
        restart(st['k'] + 1)
        return 0, 0, 0, 0, 0
    return Net(f, 4, 5)
