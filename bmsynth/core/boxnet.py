"""Ports and black boxes, on top of the cell net in net.py. Concept only: one bit per node (lanes are in accel/).

    port   a wire nothing in the net drives; it holds its value unless a black box writes it
           (or it is loaded once from outside before the run, e.g. a target)

A black-box node has input wires (words of nodes), output wires (words of ports) and a call
wire. On a tick where the call wire is 1, the box reads its inputs from that tick
and its outputs appear one tick later, like a cell. What happens inside the box (combinational
or with its own state) is invisible to the net.

API (added to net.py's):
    wires nothing drives   add_port(), remove_port(), load()
    black boxes            place_box(), remove_box(), close()

A black box is named, not handed over: place_box('module.NAME', ...) loads box file `module` (from the import
path) and asks its factory NAME(**params) for the box. Box functions are only ever called by run().
"""
import importlib
import numpy as np
from net import Net


class _Box:
    def __init__(self, box, call, ins, outs):
        self.box, self.call, self.ins, self.outs = box, call, [list(w) for w in ins], [list(w) for w in outs]


class BoxNet(Net):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.boxes = {}
        self._nbox = 0

    def add_port(self, name=None):
        return self._new('port', name)

    def remove_port(self, i):
        assert self.kind.get(i) == 'port'
        del self.kind[i]; self.names.pop(i, None); self._changed()

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

    def load(self, s, word, value):
        """Write an integer into a word of ports (from outside, before the run: the spec)."""
        assert all(self.kind.get(n) == 'port' for n in word)
        self._write_lanes(s, word, np.array([0]), np.array([int(np.asarray(value).reshape(-1)[0])], dtype=object))

    # ---------------------------------------------------------------- how a box sees the state
    # A box is called as box(lanes, *in_values) with one entry per calling lane; here there is one lane, lane 0.
    def _calling(self, s, node):
        """The lanes in which `node` is 1."""
        return np.array([0]) if s[node] else np.array([], np.int64)

    def _read_lanes(self, s, word):
        return np.array([self.read(s, word)])

    def _write_lanes(self, s, word, lanes, values):
        """Write values[j] (two's complement for negatives) into a word of nodes, in lane lanes[j]."""
        v = int(np.asarray(values).reshape(-1)[0])
        for k, n in enumerate(word): s[n] = (v >> k) & 1

    def _tick(self, s):
        """One tick of every cell, then every box whose call wire is 1 (box outputs appear in the new state)."""
        new = super()._tick(s)
        for bx in self.boxes.values():
            lanes = self._calling(s, bx.call)
            if not len(lanes): continue
            args = [self._read_lanes(s, w)[lanes] for w in bx.ins]
            res = bx.box(lanes, *args)
            if not isinstance(res, tuple): res = (res,)
            for w, val in zip(bx.outs, res): self._write_lanes(new, w, lanes, val)
        return self._grow(new)                     # a box may have added nodes this tick
