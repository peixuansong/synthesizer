"""Speed-up: lanes. N independent runs of one net's wiring, ticked together.

Each node holds a row of uint64 words instead of one bit; bit k of every row is that node's value in lane k.
The cell rule is applied with bitwise word operations, so up to 64 lanes tick for the cost of one. Inside the
cells lanes never meet (bit k only combines with bit k); this is the same as N separate copies of the net.

    LaneNet(lanes)      CompiledNet with lanes: read() gives one integer per lane; run(stop=node) ends once
                        the node is 1 in every lane.
    LaneBoxNet(lanes)   BoxNet (core/boxnet.py) on LaneNet: each box is called once per tick with every calling lane.
"""
import numpy as np
import numba as nb
from compiled import CompiledNet
from boxnet import BoxNet

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


class LaneNet(CompiledNet):
    _one = ALL

    def __init__(self, lanes=1):
        super().__init__()
        self.lanes = lanes
        self.words = max(1, (lanes + 63) // 64)
        self._mask = _lane_mask(lanes, self.words)

    def _empty(self, rows):
        return np.zeros((rows, self.words), np.uint64)

    def read(self, s, word):
        """One integer per lane from a word of nodes (observation)."""
        return _read(s, word, self.lanes)

    def _tick(self, s):
        new = s.copy()
        step_lanes(s, new, *self._compile())
        return new

    def _is_one(self, s, node):
        return ((s[node] & self._mask) == self._mask).all()


class LaneBoxNet(BoxNet, LaneNet):
    def load(self, s, word, values):
        """Write one integer per lane into a word of ports (from outside, before the run: the spec)."""
        assert all(self.kind.get(n) == 'port' for n in word)
        v = _as_ints(np.array(values, dtype=object).reshape(-1)); _write(s, word, np.broadcast_to(v, (self.lanes,)).copy(), np.ones(self.lanes, bool), self.lanes)

    def _calling(self, s, node):
        return np.flatnonzero(_bits(s[node], self.lanes))

    def _read_lanes(self, s, word):
        """_read, remembered per word while its bits do not change (wide words are slow to turn into ints)."""
        if len(word) <= 62: return _read(s, word, self.lanes)
        cache = self.__dict__.setdefault('_rc', {})
        key, raw = tuple(word), s[list(word)].tobytes()
        hit = cache.get(key)
        if hit is None or hit[0] != raw:
            hit = cache[key] = (raw, _read(s, word, self.lanes))
        return hit[1]

    def _write_lanes(self, s, word, lanes, values):
        val = _as_ints(values)
        full = np.zeros(self.lanes, val.dtype); full[lanes] = val
        go = np.zeros(self.lanes, bool); go[lanes] = True
        _write(s, word, full, go, self.lanes)


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


def _bits(row, lanes):
    return np.unpackbits(row.view(np.uint8), bitorder='little')[:lanes].astype(bool)


def _as_ints(val):
    val = np.asarray(val)
    if val.dtype == object:
        try: return val.astype(np.int64)
        except OverflowError: return val
    return val.astype(np.int64)


def _write(s, word, values, mask, lanes):
    """Write values (two's complement for negatives) into a word of nodes, in the lanes where mask is set."""
    values = np.asarray(values)
    n = len(word)
    if values.dtype == object:
        first = values[0] if len(values) else 0
        if all(v == first for v in values):                    # the same value everywhere (e.g. a library word)
            bits = np.repeat(np.array([(int(first) >> i) & 1 for i in range(n)], bool)[:, None], len(values), 1)
        else:
            nb = (n + 7) // 8; m = (1 << (8 * nb)) - 1
            by = np.frombuffer(b''.join((int(v) & m).to_bytes(nb, 'little') for v in values), np.uint8).reshape(len(values), nb)
            bits = np.unpackbits(by, axis=1, bitorder='little')[:, :n].T.astype(bool)
    else:
        v = values.view(np.int64) if values.dtype == np.uint64 else values.astype(np.int64)
        bits = ((v[None, :] >> np.minimum(np.arange(n), 63)[:, None]) & 1).astype(bool)
    old = np.unpackbits(s[list(word)].view(np.uint8), axis=1, bitorder='little').astype(bool)
    old[:, :lanes] = np.where(mask[None, :], bits, old[:, :lanes])
    s[list(word)] = np.packbits(old, axis=1, bitorder='little').view(np.uint64)
