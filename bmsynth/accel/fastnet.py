"""Speed only: net() for a core net, compiled with numba. The same rule, tick for tick, as core/net.py and core/box.py.

    FastNet      a Net whose net() runs compiled; build the main net as a FastNet instead of a Net
    net()        runs forever, as Net does. net(seconds=s, observe=f) stops after s seconds, or when f(net) returns
                 True; f is called about once a second and may only look
Only cells whose inputs changed on the last tick are worked out again (the others would come out the same), so a
big settled net costs little. A cell's inputs are its terms and its z.
Boxes: a box's f is called from Python. If f has `left`, its outputs stay the same and it ignores its inputs for
`left` more ticks (box.py calls f every tick and f counts those down itself), so those ticks run compiled in one go.
If f also has a `queue` of (outputs, ticks) that follow, ignoring inputs too, a lone box's queue runs compiled.
A box output is packed as a cell with no terms and z = NOT its value, so it shows that value on the next tick.
Edits: a cell with its own edit() (a maker) or with arms (triangle connect) is watched. On the tick it turns from 0
to 1 the compiled run stops, the bits are written back into the cells, edit() runs, and the net is packed again.
"""
import time
import numpy as np
import numba as nb
from cell import Cell
from net import Net
from box import Box

CHUNK = 1 << 16                                          # the most ticks run before Python looks again


@nb.njit
def _run(y, zc, zi, ptr, A, B, fp, fan, wpos, rose, dirty, isd, nd, n):
    """Up to n ticks; stops after a tick on which a watched cell turned from 0 to 1. Returns the ticks done.
    dirty[:nd[0]] are the cells to work out on the next tick (isd marks them)."""
    chg, val = np.empty(y.shape[0], np.int64), np.empty(y.shape[0], np.uint8)
    for t in range(n):
        m = 0
        for d in range(nd[0]):
            i, acc = dirty[d], 0
            isd[i] = 0
            for p in range(ptr[i], ptr[i + 1]):
                if y[A[p]] & y[B[p]]:
                    acc = 1
                    break
            z = zc[i] if zi[i] < 0 else y[zi[i]]
            v = 1 ^ z ^ acc
            if v != y[i]:
                chg[m] = i; val[m] = v; m += 1
        nd[0], hit = 0, False
        for c in range(m):
            i = chg[c]; y[i] = val[c]
            if wpos[i] >= 0 and val[c] == 1:
                rose[wpos[i]] = 1; hit = True
            for p in range(fp[i], fp[i + 1]):
                f = fan[p]
                if not isd[f]:
                    isd[f] = 1; dirty[nd[0]] = f; nd[0] += 1
        if hit: return t + 1
    return n


@nb.njit
def _plan(y, zc, zi, ptr, A, B, fp, fan, wpos, rose, dirty, isd, nd, outs, P, H):
    """Run a box's planned outputs: segment s holds outputs P[s] for H[s] ticks. Stops like _run.
    Returns (segment reached, ticks done in it)."""
    for s in range(P.shape[0]):
        for o in range(outs.shape[0]):
            i = outs[o]
            zc[i] = 1 - P[s, o]
            if P[s, o] != y[i] and not isd[i]:
                isd[i] = 1; dirty[nd[0]] = i; nd[0] += 1
        k = _run(y, zc, zi, ptr, A, B, fp, fan, wpos, rose, dirty, isd, nd, H[s])
        if rose.any(): return s, k
    return P.shape[0], 0


def _nets(net): return [m for n in net.nets for m in [n] + _nets(n)]


class FastNet(Net):
    def _blank(self): return FastNet()

    def _pack(self):
        nets = [self] + _nets(self)
        cs = self.all = [c for n in nets for c in n.cells]; N = len(cs)
        self.boxes = [n for n in nets if isinstance(n, Box)]
        ix = {id(c): i for i, c in enumerate(cs)}
        held = {id(c) for b in self.boxes for c in b.outputs}
        cz = lambda c: isinstance(c.z, Cell) and id(c) not in held
        self.y = np.array([c.y for c in cs], np.uint8)
        self.zc = np.array([1 - c.y if id(c) in held else 0 if cz(c) else c.z for c in cs], np.uint8)
        self.zi = np.array([ix[id(c.z)] if cz(c) else -1 for c in cs], np.int64)
        terms = [[] if id(c) in held else [(ix[id(t[0])], ix[id(t[-1])]) for t in c.terms] for c in cs]
        self.ptr = np.concatenate([[0], np.cumsum([len(t) for t in terms])]).astype(np.int64)
        self.A = np.array([a for t in terms for a, _ in t], np.int64)
        self.B = np.array([b for t in terms for _, b in t], np.int64)
        fan = [set() for _ in range(N)]                  # who reads each cell
        for i, a, b in ((i, a, b) for i, t in enumerate(terms) for a, b in t): fan[a].add(i); fan[b].add(i)
        for i in np.nonzero(self.zi >= 0)[0]: fan[self.zi[i]].add(int(i))
        self.fp = np.concatenate([[0], np.cumsum([len(f) for f in fan])]).astype(np.int64)
        self.fan = np.array([j for f in fan for j in sorted(f)], np.int64)
        self.watched = [c for c in cs if c.froms or c.tos or type(c).edit is not Cell.edit]
        self.wpos = np.full(N, -1, np.int64)
        for w, c in enumerate(self.watched): self.wpos[ix[id(c)]] = w
        self.rose = np.zeros(len(self.watched), np.uint8)
        self.dirty, self.isd, self.nd = np.arange(N, dtype=np.int64), np.ones(N, np.uint8), np.array([N], np.int64)
        self.io = [tuple(np.array([ix[id(c)] for c in x], np.int64) for x in (b.inputs, b.outputs)) for b in self.boxes]
        self.args = (self.y, self.zc, self.zi, self.ptr, self.A, self.B, self.fp, self.fan, self.wpos, self.rose,
                     self.dirty, self.isd, self.nd)

    def _boxes(self):                                    # call every box once; ticks its outputs all stay the same
        h = CHUNK
        for b, (ins, outs) in zip(self.boxes, self.io):
            self.zc[outs] = 1 - np.array(b.f(*self.y[ins].tolist()), np.uint8)
            new = outs[((1 ^ self.zc[outs]) != self.y[outs]) & (self.isd[outs] == 0)]   # outputs that change
            self.dirty[self.nd[0]:self.nd[0] + len(new)] = new; self.isd[new] = 1; self.nd[0] += len(new)
            h = min(h, 1 + getattr(b.f, 'left', 0))
        for b in self.boxes:
            if hasattr(b.f, 'left'): b.f.left -= h - 1
        return h

    def _queue(self, f, h):                              # f's outputs and queue, compiled; returns ticks left over
        segs = [(f.out, h)] + list(f.queue); f.queue.clear()
        P = np.array([v for v, _ in segs], np.uint8); H = np.array([t for _, t in segs], np.int64)
        s, k = _plan(*self.args, self.io[0][1], P, H)
        self.ticks += int(H[:s].sum()) + k
        if s == len(segs): return 0
        f.queue.extend(segs[s + 1:]); f.out = segs[s][0]; self._edit()
        return int(H[s]) - k

    def _edit(self):
        self.sync()
        for c, r in zip(self.watched, list(self.rose)):
            if r: c.edit()
        self._pack()

    def sync(self):                                      # write the bits back into the cells, to look at them
        for c, v in zip(self.all, self.y): c.y = int(v)

    def __call__(self, *args, seconds=None, observe=None):
        if args: return self._compose(args)
        self._pack(); self.ticks = getattr(self, 'ticks', 0)
        t0 = last = time.time()
        while True:
            h = self._boxes()
            f = self.boxes[0].f if len(self.boxes) == 1 else None
            if getattr(f, 'queue', None): h = self._queue(f, h)
            while h:
                k = _run(*self.args, h)
                self.ticks += k; h -= k
                if self.rose.any(): self._edit()
            now = time.time()
            if observe and now - last >= 1:
                last = now; self.sync()
                if observe(self): return
            if seconds and now - t0 >= seconds: self.sync(); return
