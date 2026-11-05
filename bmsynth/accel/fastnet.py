"""FastNet: the same net as net.py, ticked faster (accel/: speed only, the function is unchanged).

net.py rebuilds every cell's terms from the edge list on every tick. FastNet turns the edges into arrays once
(and again after cp or cn changes them), and works out each tick's new bits in compiled code (numba). Boxes,
cp and cn run exactly as in net.py. Check:  python3 accel/fastnet.py  (runs both on random nets and compares).
"""
import numpy as np
from numba import njit
from net import Net


@njit(cache=True)
def _step(ys, new, tptr, tsrc, tdst, zsrc):
    """new = the rule for every cell, from the bits ys."""
    n = ys.shape[0]
    hit = np.zeros(n, np.uint8)
    for t in range(tdst.shape[0]):
        v = 1
        for q in range(tptr[t], tptr[t + 1]):
            v &= ys[tsrc[q]]
        if v: hit[tdst[t]] = 1
    for d in range(n):
        z = 1 if zsrc[d] < 0 else ys[zsrc[d]]
        new[d] = 1 ^ z ^ hit[d]


class FastNet(Net):
    @staticmethod
    def _empty():
        n = FastNet(); n.ys, n.inputs, n.outputs = [], [], []
        return n

    def _compile(self):
        n = len(self.ys)
        terms, zsrc, sig = {}, np.full(n, -1, np.int64), {}
        for s, d, p, t in self.edges:
            if p == 'x': terms.setdefault((d, t), []).append(s)
            elif p == 'z': zsrc[d] = s
            elif p in ('cp', 'cn'): sig[d, p] = s
        keys = list(terms)
        self._tdst = np.array([d for d, t in keys], np.int64)
        self._tptr = np.cumsum([0] + [len(terms[k]) for k in keys]).astype(np.int64)
        self._tsrc = np.array([s for k in keys for s in terms[k]], np.int64)
        self._zsrc, self._sig = zsrc, list(sig.items())
        self._ssrc = np.array([s for (d, p), s in self._sig], np.int64)
        self._arr = np.array(self.ys, np.uint8)

    def __call__(self, ticks=None):
        self._compile()
        k = 0
        while ticks is None or k < ticks:
            k += 1
            ys = self._arr
            new = np.empty_like(ys)
            _step(ys, new, self._tptr, self._tsrc, self._tdst, self._zsrc)
            for f, ins, outs in self.boxes:
                for o, v in zip(outs, f(*[int(ys[i]) for i in ins])): new[o] = int(v)
            self._arr = new
            if not len(self._sig): continue
            moved = np.nonzero(ys[self._ssrc] != new[self._ssrc])[0]
            if not len(moved): continue
            self.ys = new.tolist()
            for j in moved:
                (d, p), s = self._sig[j]
                if p == 'cp' and new[s]: self._cp(d)
                if p == 'cn': self._cn(d, int(new[s]))
            self._compile()
        self.ys = self._arr.tolist()


if __name__ == '__main__':
    import random
    rnd = random.Random(0)
    for trial in range(200):
        N = rnd.randint(3, 12)
        a = Net._empty(); a.ys = [rnd.randint(0, 1) for _ in range(N)]
        for _ in range(rnd.randint(0, 3 * N)):
            a._link(rnd.randrange(N), rnd.randrange(N), rnd.choice(['x', 'x', 'x', 'z', 'cp', 'cn']),
                    rnd.choice([None, 0, 1]))
        b = FastNet._empty()
        b.ys, b.edges = list(a.ys), list(a.edges)
        for _ in range(30):
            if len(a.ys) > 300: break                     # cp can double a net every tick
            a(ticks=1); b(ticks=1)
            assert a.ys == b.ys and sorted(a.edges) == sorted(b.edges), trial
    print('FastNet matches Net on 200 random nets x 30 ticks')
