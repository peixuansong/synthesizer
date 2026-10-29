"""Speed-up: the cell rule of core/net.py compiled with numba. Same result as Net, tick for tick.

The wiring is packed into arrays (ids, ptr, A, B, C), re-packed after any change, and each tick is
    new[ids[i]] = s[C[i]] XNOR OR_{p in ptr[i]..ptr[i+1]} ( s[A[p]] AND s[B[p]] )
"""
import numpy as np
import numba as nb
from net import Net, ZERO


@nb.njit(cache=True)
def step_cells(s, new, ids, ptr, A, B, C):
    for i in range(ids.shape[0]):
        acc = np.uint8(0)
        for p in range(ptr[i], ptr[i + 1]):
            acc |= s[A[p]] & s[B[p]]
        new[ids[i]] = np.uint8(1) ^ s[C[i]] ^ acc


class CompiledNet(Net):
    """Net with one uint8 per node and the compiled tick."""
    _compiled = None

    def _changed(self):
        self._compiled = None

    def _compile(self):
        if self._compiled is None:
            ids = np.array(sorted(self.cells), np.int64)
            pairs = [[p for p in self.cells[i][0] if ZERO not in p] for i in ids]
            ptr = np.concatenate([[0], np.cumsum([len(p) for p in pairs])]).astype(np.int64)
            A = np.array([a for p in pairs for a, _ in p], np.int64)
            B = np.array([b for p in pairs for _, b in p], np.int64)
            C = np.array([self.cells[i][1] for i in ids], np.int64)
            self._compiled = (ids, ptr, A, B, C)
        return self._compiled

    _one = np.uint8(1)                   # what a node's row holds when its bit is 1

    def _empty(self, rows):
        return np.zeros(rows, np.uint8)

    def __init__(self):
        super().__init__()
        self.s = self._empty(0)

    def _new(self, bit=0):
        row = self._empty(1)
        if bit: row[0] = self._one
        self.s = np.concatenate([self.s, row])
        return len(self.s) - 1

    def _join(self, s, extra):
        return np.concatenate([s, extra])

    def read(self, word):
        return sum(int(self.s[n]) << k for k, n in enumerate(word))

    def _tick(self, s):
        new = s.copy()
        step_cells(s, new, *self._compile())
        return new
