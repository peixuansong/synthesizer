"""Speed only: steps a core Net (core/net.py) with the same rule, tick for tick, compiled with numba.

The wiring is packed into arrays once: per cell its z (a constant or a cell) and its terms (a cell, or a pair
of cells). Each tick:  new[i] = 1 XOR z[i] XOR OR(terms of i);  then every cell takes its new bit at once.
Triangle connect (cells that rewire cells) is not supported here: FastRun refuses a net that uses it.
The bits live in the array while running; sync() writes them back into the Cell objects.
"""
import numpy as np
import numba as nb
from cell import Cell


@nb.njit(cache=True)
def _run(y, zc, zi, ptr, A, B, watch, until, n):
    """Up to n ticks; stops early once y[watch] == until. Returns the ticks done."""
    new = np.empty_like(y)
    for t in range(n):
        if y[watch] == until: return t
        for i in range(y.shape[0]):
            acc = 0
            for p in range(ptr[i], ptr[i + 1]):
                if y[A[p]] & y[B[p]]:
                    acc = 1
                    break
            z = zc[i] if zi[i] < 0 else y[zi[i]]
            new[i] = 1 ^ z ^ acc
        y[:] = new
    return n


def _cells(net):
    return list(net.cells) + [c for m in net.nets for c in _cells(m)]


def _nets(net):
    return [m for n in net.nets for m in [n] + _nets(n)]


class FastRun:
    def __init__(self, net):
        self.cells = _cells(net)
        self.ix = {id(c): i for i, c in enumerate(self.cells)}
        assert not any(c.froms or c.tos for c in self.cells), 'triangle connect is not supported by FastRun'
        assert all(type(m)._compute is type(net)._compute for m in _nets(net)), 'boxes are not supported by FastRun'
        ix = self.ix
        self.y = np.array([c.y for c in self.cells], np.uint8)
        self.zc = np.array([0 if isinstance(c.z, Cell) else c.z for c in self.cells], np.uint8)
        self.zi = np.array([ix[id(c.z)] if isinstance(c.z, Cell) else -1 for c in self.cells], np.int64)
        terms = [[(ix[id(t[0])], ix[id(t[-1])]) for t in c.terms] for c in self.cells]
        self.ptr = np.concatenate([[0], np.cumsum([len(t) for t in terms])]).astype(np.int64)
        self.A = np.array([a for t in terms for a, _ in t], np.int64)
        self.B = np.array([b for t in terms for _, b in t], np.int64)

    def until_zero(self, cell, n):
        """Run up to n ticks, stopping once `cell` is 0. Returns the ticks done."""
        return _run(self.y, self.zc, self.zi, self.ptr, self.A, self.B, self.ix[id(cell)], 0, n)

    def get(self, cell):
        return int(self.y[self.ix[id(cell)]])

    def sync(self):
        for c, v in zip(self.cells, self.y): c.y = int(v)
