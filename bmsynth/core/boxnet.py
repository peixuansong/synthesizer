"""Ports and black boxes, on top of the lane net in lanes.py.

    port   a wire nothing in the net drives; it holds its value unless a black box writes it
           (or it is loaded once from outside before the run, e.g. a target)

A black-box node has input wires (words of nodes), output wires (words of ports) and a call
wire. On a tick where the call wire is 1 in a lane, the box reads its inputs from that tick
and its outputs appear one tick later, like a cell. What happens inside the box (combinational
or with its own state) is invisible to the net.

API (added to lanes.py's):
    wires nothing drives   add_port(), remove_port(), load()
    black boxes            place_box(), remove_box(), close()

A black box is named, not handed over: place_box('module.NAME', ...) loads box file `module` (from the import
path) and asks its factory NAME(**params) for the box. Box functions are only ever called by run().
"""
import importlib
import numpy as np
from lanes import LaneNet, ALL, _read


class _Box:
    def __init__(self, box, call, ins, outs):
        self.box, self.call, self.ins, self.outs = box, call, [list(w) for w in ins], [list(w) for w in outs]


class BoxNet(LaneNet):
    def __init__(self, lanes=1):
        super().__init__(lanes)
        self.boxes = {}
        self._nbox = 0

    def add_port(self, name=None):
        return self._new('port', name)

    def remove_port(self, i):
        assert self.kind.get(i) == 'port'
        del self.kind[i]; self.names.pop(i, None); self._compiled = None

    def place_box(self, box, call, ins, outs, **params):
        """box: 'module.NAME', a factory in a box file; NAME(**params) gives the box,
        box(lanes, *in_words) -> tuple of out_words. ins/outs are lists of words (lists of nodes, bit 0 first).
        Output nodes must be ports."""
        for w in outs:
            for n in w: assert self.kind.get(n) == 'port', 'box outputs must be ports'
        mod, name = box.rsplit('.', 1)
        fn = getattr(importlib.import_module(mod), name)(**params)
        h = self._nbox; self._nbox += 1
        self.boxes[h] = _Box(fn, call, ins, outs)
        return h

    def remove_box(self, h):
        del self.boxes[h]

    def close(self):
        """Let every box release what it holds (worker processes etc.)."""
        for bx in self.boxes.values():
            if hasattr(bx.box, 'close'): bx.box.close()

    def load(self, s, word, values):
        """Write one integer per lane into a word of ports (from outside, before the run: the spec)."""
        assert all(self.kind.get(n) == 'port' for n in word)
        v = _as_ints(np.array(values, dtype=object).reshape(-1)); _write(s, word, np.broadcast_to(v, (self.lanes,)).copy(), np.ones(self.lanes, bool), self.lanes)

    def _read_cached(self, s, word):
        """_read, remembered per word while its bits do not change (wide words are slow to turn into ints)."""
        if len(word) <= 62: return _read(s, word, self.lanes)
        cache = self.__dict__.setdefault('_rc', {})
        key, raw = tuple(word), s[list(word)].tobytes()
        hit = cache.get(key)
        if hit is None or hit[0] != raw:
            hit = cache[key] = (raw, _read(s, word, self.lanes))
        return hit[1]

    def _tick(self, s):
        """One tick of every cell, then every box whose call wire is 1."""
        new = super()._tick(s)
        for bx in self.boxes.values():
            go = _bits(s[bx.call], self.lanes)
            if not go.any(): continue
            lanes = np.flatnonzero(go)
            args = [self._read_cached(s, w)[lanes] for w in bx.ins]
            res = bx.box(lanes, *args)
            if not isinstance(res, tuple): res = (res,)
            for w, val in zip(bx.outs, res):
                val = _as_ints(val)
                full = np.zeros(self.lanes, val.dtype)
                full[lanes] = val
                _write(new, w, full, go, self.lanes)
        if self._compiled is None:                  # a box edited the net this tick: tick the new wiring from now on
            if new.shape[0] < self._next:
                grow = np.zeros((self._next - new.shape[0], self.words), np.uint64)
                for i in range(new.shape[0], self._next):
                    if i in self.cells and self.cells[i][2]: grow[i - new.shape[0]] = ALL
                new = np.concatenate([new, grow])
        return new


# ------------------------------------------------------------------- bit helpers
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
