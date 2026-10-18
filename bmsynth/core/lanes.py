"""Lanes: N independent runs of one net's wiring, ticked together. A speed-up only.

Each node holds a row of uint64 words instead of one bit; bit k of every row is that node's value in lane k.
The cell rule is applied with bitwise word operations, so up to 64 lanes tick for the cost of one. Inside the
cells lanes never meet (bit k only combines with bit k); this is the same as N separate copies of the net.

API (net.py's, with these changes):
    LaneNet(lanes)   state() gives one row of words per node; read() gives one integer per lane;
                     run(stop=node) ends once the node is 1 in every lane.
"""
import numpy as np
import numba as nb
from net import Net, ONE

ALL = np.uint64(0xFFFFFFFFFFFFFFFF)


@nb.njit(parallel=True, cache=True)
def step_lanes(s, new, ids, ptr, A, B, C):
    """new[ids[i]] = s[C[i]] XNOR OR_p ( s[A[p]] AND s[B[p]] ), one uint64 word (64 lanes) at a time."""
    W = s.shape[1]; n = ids.shape[0]
    for i in nb.prange(n):
        for w in range(W):
            acc = np.uint64(0)
            for p in range(ptr[i], ptr[i + 1]):
                acc |= s[A[p], w] & s[B[p], w]
            new[ids[i], w] = ~(s[C[i], w] ^ acc)


class LaneNet(Net):
    def __init__(self, lanes=1):
        super().__init__()
        self.lanes = lanes
        self.words = max(1, (lanes + 63) // 64)
        self._mask = _lane_mask(lanes, self.words)

    def state(self):
        s = np.zeros((self._next, self.words), np.uint64)
        s[ONE] = ALL
        for i, (_, _, init) in self.cells.items():
            if init: s[i] = ALL
        return s

    def read(self, s, word):
        """One integer per lane from a word of nodes (observation)."""
        return _read(s, word, self.lanes)

    def _tick(self, s):
        new = s.copy()
        step_lanes(s, new, *self._compile())
        return new

    def _is_one(self, s, node):
        return ((s[node] & self._mask) == self._mask).all()


# ------------------------------------------------------------------- bit helpers
def _lane_mask(lanes, words):
    m = np.zeros(words, np.uint64)
    for w in range(words):
        n = min(64, lanes - 64 * w)
        m[w] = ALL if n == 64 else np.uint64((1 << n) - 1)
    return m


def _read(s, word, lanes):
    """One integer per lane (int64 up to 62 bits, Python ints above that)."""
    if not len(word): return np.zeros(lanes, np.int64)
    bits = np.unpackbits(s[list(word)].view(np.uint8), axis=1, bitorder='little')[:, :lanes]
    if len(word) <= 62:
        return (np.int64(1) << np.arange(len(word), dtype=np.int64)) @ bits.astype(np.int64)
    by = np.ascontiguousarray(np.packbits(bits, axis=0, bitorder='little').T)      # (lanes, bytes)
    out = np.empty(lanes, dtype=object)
    for i in range(lanes): out[i] = int.from_bytes(by[i].tobytes(), 'little')
    return out
