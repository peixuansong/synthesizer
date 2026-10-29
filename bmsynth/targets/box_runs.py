"""The target box's maker actions and its checks (part of target_box.Play; see there for put, many and where).

    copy    the maker copies a block (op 4); the block's names then mean its top copy
    check   the maker wires the probes to a cell or row (op 3); the box drives T, A, B with each sample, holds it
            `hold` ticks and compares the probes with the wanted word
    place   the maker wires a blank to read a part made later (op 5)
    run     a machine check: the box writes programs (already encoded as words) into WORK through A, B and T while
            TEST = 1, has the maker freeze library programs (op 6) under their ids, writes the main program, then
            for each case n: A = n, GO = 1 for one clock (INIT), and clocks T with period `period` until STAT shows
            halted (lane 0) or failed (lane 1), at most `limit` clocks; then it reads REG0. want None = must fail.
"""
NONE = (0, 2, 0)


def bits(v, n):
    return [v >> i & 1 for i in range(n)]


class Runs:
    def act(self, op, src):
        """One maker action; returns the address it writes."""
        yield from self.put(1, op=op, src=src + [NONE] * (4 - len(src)), act=1)
        yield from self.put(1, act=0)
        return (yield from self.put(1, op=0))['addr']

    def copy(self, t):
        a, n = self.place[t['block']][0], t['n']
        top = yield from self.act(4, [(a, 2, 0), (n, 2, 0)])
        L = (top - a) // n
        for name, (p, kind) in self.place.items():
            if p >= a: self.place[name] = (p + n * L, kind)
        return L > 0, n

    def check(self, t):
        a, kind = self.place[t['out']]
        yield from self.act(3, [(a, 0 if kind == 'row' else 2, 0)])
        ok, M = True, (1 << self.W) - 1
        for s in range(t['n']):
            d = {k: f(s) & M for k, f in t['drive'].items()}
            got = (yield from self.put(t.get('hold', 3 * self.W + 12), T=d.get('T', 0), A=d.get('A', 0),
                                       B=d.get('B', 0), TEST=1))['probe']
            got = got if kind == 'row' else got[:1]
            ok = ok and got == bits(t['want'](s), len(got))
        yield from self.put(1, T=0, A=0, B=0, TEST=0)
        return ok, t['n']

    def place_(self, t):
        a, kind = self.place[t['dst']]
        yield from self.act(5, [self.where(t['src']), (a, 0 if kind == 'row' else 2, 0)])
        return True, 1

    def load(self, words, q=16):
        """Write 32 slots of WORK (missing slots: end)."""
        words = list(words) + [31 << 7] * (32 - len(words))
        segs = [x for s, w in enumerate(words) for x in ((q, dict(TEST=1, T=0, A=w, B=s)), (q, dict(T=1)))]
        yield from self.many(segs + [(q, dict(T=0))])

    def run(self, t):
        W, M = self.W, (1 << self.W) - 1
        P, limit = t.get('period', 4 * W * W + 64), t.get('limit', 400)
        at = lambda n: self.place[n][0]
        for pid, words in t.get('lib', {}).items():
            yield from self.load(words)
            yield from self.act(6, [(at('SLOT0'), 2, 0), (at('BUS0'), 2, 32), (at('PID'), 2, 11), (pid, 2, 0)])
        yield from self.load(t['words'])
        yield from self.put(16, TEST=0, A=0, B=0)
        ok, self.trace = True, getattr(self, 'trace', [])
        for n, want in t['cases']:
            yield from self.act(3, [(at('STAT'), 0, 0)])
            yield from self.many([(P // 2, dict(T=0, GO=1, A=n & M)), (P - P // 2, dict(T=1))])
            for steps in range(1, limit + 1):
                d = yield from self.many([(P // 2, dict(T=0, GO=0)), (P - P // 2, dict(T=1))])
                st = d['probe'][0] + 2 * d['probe'][1]
                if st: break
            yield from self.act(3, [(at('REG0'), 0, 0)])
            got = sum(b << k for k, b in enumerate((yield from self.put(4))['probe']))
            good = st == 2 if want is None else st == 1 and got == want & M
            self.trace.append((t['name'], n, want, st, got, steps))
            ok = ok and good
        yield from self.put(1, T=0, A=0)
        return ok, len(t['cases'])
