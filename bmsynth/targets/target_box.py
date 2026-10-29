"""The target box: a black box that plays the targets to the seed, one after another, and checks the results.
It stands for the outside world (what is wanted); the seed's cells do the searching and the making.

Search target: the box drives the candidate's inputs x0..x3 with the sources' sample values, step by step, with
the wanted value and a strobe for the seed's checker; at the end of a try it pulses dec (and ndec = NOT dec).
The seed then steps its counter (a mismatch) or makes the found cell or row (passed). Meanwhile the box holds op
(1 cell, 2 row) and the sources' places for the maker: (address, rel, lane), see core/maker.py.
Check target: the box has the maker wire its probe inputs to the named cell or row (op 3, on an `act` pulse),
drives T, A and B with each sample for a while and compares the probes with the wanted word.
Copy target: the box has the maker copy a block (op 4, on an `act` pulse); block names then mean the top copy.
Place and run targets: see box_runs.py.
Fixed places, by the seed's convention: 0 = the zero cell, 1 = T, 2 = TEST, 3.. = row A, 3+W.. = row B, 3+2W = GO.
Times: put(h, ...) sets outputs for the next h ticks and returns the inputs seen on the last of them; many([(h,
{...}), ...]) does the same for several stretches in a row.
"""
from collections import deque
from box import Box
from box_runs import Runs

AW, RW, LW = 20, 2, 6                                    # bits of an address, a rel, a lane
R = 8                                                     # ticks of reset before each try
NONE = (0, 2, 0)                                          # an unused source: cell 0


def bits(v, n):
    return [v >> i & 1 for i in range(n)]


class Play(Runs):
    """The box's f. Each call is one tick; for `left` more ticks the outputs stay the same and inputs are ignored,
    and so they are for the (outputs, ticks) waiting in `queue`."""
    def __init__(self, targets, W, samples):
        self.W, self.targets, self.samples = W, targets, samples
        self.OUT = [('x', 4), ('nrst', 1), ('want', 1), ('strobe', 1), ('dec', 1), ('ndec', 1), ('clr', 1),
                    ('act', 1), ('op', 3), ('src', 4 * (AW + RW + LW)), ('T', 1), ('TEST', 1), ('A', W), ('B', W), ('GO', 1)]
        self.IN = [('passed', 1), ('fdone', 1), ('addr', AW), ('probe', W)]
        self.o = {n: 0 for n, _ in self.OUT}
        self.o.update(ndec=1, src=[NONE] * 4)
        self.enc = {n: self.code(n) for n, _ in self.OUT}
        self.place = {'T': (1, 'cell'), 'TEST': (2, 'cell'), 'A': (3, 'row'), 'B': (3 + W, 'row'), 'GO': (3 + 2 * W, 'cell')}
        self.log, self.now, self.left, self.done = [], 0, 0, False
        self.gen, self.out, self.queue = self.play(), None, deque()

    def __call__(self, *ins):
        if self.left:
            self.left -= 1
            return self.out
        if not self.queue:
            got = next(self.gen) if self.out is None else self.gen.send(ins)
            self.queue.extend(got if isinstance(got, list) else [got])
        self.out, h = self.queue.popleft()
        self.left = h - 1
        return self.out

    def code(self, name):
        x, n = self.o[name], dict(self.OUT)[name]
        return [b for a, r, l in x for b in bits(a, AW) + bits(r, RW) + bits(l, LW)] if name == 'src' else bits(x, n)

    def put(self, h, **kv):
        return (yield from self.many([(h, kv)]))

    def many(self, segs):
        out = []
        for h, kv in segs:
            for k, v in kv.items():
                if self.o[k] != v: self.o[k] = v; self.enc[k] = self.code(k)
            self.now += h
            out.append(([b for n, _ in self.OUT for b in self.enc[n]], h))
        ins, i, d = (yield out), 0, {}
        for name, n in self.IN:
            d[name] = list(ins[i:i + n]); i += n
        d['addr'] = sum(b << k for k, b in enumerate(d['addr']))
        return d

    def play(self):
        yield from self.put(4)
        for t in self.targets:
            start = self.now
            ok, n = yield from getattr(self, dict(cell='search', row='search', place='place_').get(t['kind'], t['kind']))(t)
            self.log.append(dict(name=t['name'], kind=t['kind'], ok=ok, tries=n, ticks=self.now - start,
                                 addr=self.place.get(t['name'], (None,))[0]))
        self.done = True
        while True:
            yield from self.put(1 << 30)

    def where(self, s, me=None):
        """(address, rel, lane) of a source name, as the maker reads it; `me` is the row being made."""
        if isinstance(s, tuple) and s[0] == me: return (0, 3, 0)
        if isinstance(s, tuple) and len(s) == 4:                 # lanes from s[1] on; past s[3]: 0 or sign
            return (self.place[s[0]][0] + s[1], 0, s[3] + (32 if s[2] == 'z' else 0))
        if isinstance(s, tuple):
            a = self.place[s[0]][0]
            return (a, 1, 0) if s[1] == 'L' else (a, 2, s[1])
        a, kind = self.place[s]
        return (a, 0, 0) if kind == 'row' else (a, 2, 0)

    def search(self, t):
        xs, ys = self.samples(t)
        src = [self.where(s, t['name']) for s in t['srcs']] + [NONE] * (4 - len(t['srcs']))
        yield from self.put(1, clr=1, op=1 if t['kind'] == 'cell' else 2, src=src)
        yield from self.put(1, clr=0)
        n, m = 0, len(xs)
        segs = [(R, dict(x=0, nrst=0, want=0, strobe=0))]
        for i in range(m + 2):                        # step i: x_i, and y_(i-1) wanted; checked 2 ticks late
            x = sum(b << j for j, b in enumerate(xs[i])) if i < m else 0
            kv = dict(x=x, nrst=int(i >= 1), want=ys[i - 1] if 1 <= i <= m else 0)
            if i in (1, m + 1):                       # the strobe is on from 2 ticks into step 1 to 2 ticks into m+1
                segs += [(2, kv), (1, dict(strobe=int(i == 1)))]
            else:
                segs.append((3, kv))
        segs += [(1, dict(dec=1, ndec=0, x=0, nrst=0, want=0, strobe=0)), (1, dict(dec=0, ndec=1)), (1, {})]
        while True:
            n += 1
            passed = (yield from self.many(segs))['passed'][0]
            d = yield from self.put(1)                # the counter's done, the maker's new address
            if passed or d['fdone'][0]:
                if passed: self.place[t['name']] = (d['addr'], t['kind'])
                self.o['op'] = 0; self.enc['op'] = self.code('op')
                return bool(passed), n


def target_box(targets, W, samples):
    """The box, with box.o / box.i: its output / input cells by name."""
    f = Play(targets, W, samples)
    b = Box(f, sum(n for _, n in f.IN), sum(n for _, n in f.OUT))
    for side, cells, layout in (('o', b.outputs, f.OUT), ('i', b.inputs, f.IN)):
        d, k = {}, 0
        for name, n in layout:
            d[name] = cells[k:k + n]; k += n
        setattr(b, side, d)
    return b
