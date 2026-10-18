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

    def state(self):
        return self._grow(self._empty(0))

    def _grow(self, s):
        if s.shape[0] >= self._next: return s
        add = self._empty(self._next - s.shape[0])
        for k, i in enumerate(range(s.shape[0], self._next)):
            if self._start(i): add[k] = self._one
        return np.concatenate([s, add])

    def read(self, s, word):
        return sum(int(s[n]) << k for k, n in enumerate(word))

    def _tick(self, s):
        new = s.copy()
        step_cells(s, new, *self._compile())
        return new
