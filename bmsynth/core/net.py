"""The core: one cell rule, and the only API anything outside core/ may use.

A net is a set of nodes. Node 0 is constant 0, node 1 is constant 1. Every other node is a
    cell   y(t+1) = s(t)[z] XNOR OR_k ( s(t)[a_k] AND s(t)[b_k] )
    port   a wire nothing in the net drives; it holds its value unless a black box writes it
           (or it is loaded once from outside before the run, e.g. a target)
Each node holds one bit per lane; lanes are independent copies of the same net.

A black-box node has input wires (words of nodes), output wires (words of ports) and a call
wire. On a tick where the call wire is 1 in a lane, the box reads its inputs from that tick
and its outputs appear one tick later, like a cell. What happens inside the box (combinational
or with its own state) is invisible to the net.

API (nothing else is offered):
    run                    state(), load(), run(), read()
    cells                  add_cell(), remove_cell(), set_init(), pairs()
    connections            connect(), disconnect(), set_z()
    wires nothing drives   add_port(), remove_port()
    copy / paste           copy() -> Circuit, paste()
    black boxes            place_box(), remove_box(), close()

A black box is named, not handed over: place_box('module.NAME', ...) loads box file `module` (from the import
path) and asks its factory NAME(**params) for the box. Box functions are only ever called by run().
"""
import importlib
import numpy as np
from tick import step_cells

ZERO, ONE = 0, 1
ALL = np.uint64(0xFFFFFFFFFFFFFFFF)


class Circuit:
    """A copied group of cells. References are ('c', i) internal cell, ('k', 0/1) constant, ('e', j) open end."""

    def __init__(self, cells, n_ends, names=None):
        self.cells, self.n_ends, self.names = cells, n_ends, names or {}


class _Box:
    def __init__(self, box, call, ins, outs):
        self.box, self.call, self.ins, self.outs = box, call, [list(w) for w in ins], [list(w) for w in outs]


class Net:
    def __init__(self, lanes=1):
        self.lanes = lanes
        self.words = max(1, (lanes + 63) // 64)
        self.kind = {ZERO: 'const', ONE: 'const'}
        self.cells = {}                      # id -> [pairs list, z, init]
        self.names = {}
        self.boxes = {}
        self._next, self._nbox, self._compiled = 2, 0, None

    # ---------------------------------------------------------------- cells and wires
    def add_cell(self, z=ONE, init=0, name=None):
        i = self._new('cell', name)
        self.cells[i] = [[], z, int(init)]
        return i

    def remove_cell(self, i):
        """Remove a cell; every connection that read it is removed too (a z input falls back to 1)."""
        assert self.kind.get(i) == 'cell'
        del self.cells[i]; del self.kind[i]; self.names.pop(i, None)
        for c in self.cells.values():
            c[0] = [p for p in c[0] if i not in p]
            if c[1] == i: c[1] = ONE
        self._compiled = None

    def connect(self, cell, a, b=ONE):
        """Add the term (a AND b) to a cell."""
        assert self.kind.get(cell) == 'cell' and a in self.kind and b in self.kind
        self.cells[cell][0].append((a, b)); self._compiled = None

    def disconnect(self, cell, a, b=ONE):
        self.cells[cell][0].remove((a, b)); self._compiled = None

    def set_init(self, cell, value):
        """The cell's value at tick 0."""
        self.cells[cell][2] = int(value)

    def pairs(self, cell):
        """Read a cell's wiring: (list of (a, b) pairs, z)."""
        return list(self.cells[cell][0]), self.cells[cell][1]

    def set_z(self, cell, node):
        assert node in self.kind
        self.cells[cell][1] = node; self._compiled = None

    def add_port(self, name=None):
        return self._new('port', name)

    def remove_port(self, i):
        assert self.kind.get(i) == 'port'
        del self.kind[i]; self.names.pop(i, None); self._compiled = None

    def _new(self, kind, name):
        i = self._next; self._next += 1
        self.kind[i] = kind
        if name: self.names[i] = name
        self._compiled = None
        return i

    # ---------------------------------------------------------------- copy / paste
    def copy(self, ids, ends=()):
        """The cells `ids` as a Circuit. Nodes they read that are not in `ids` become open ends: `ends` first,
        in the order given, then any others in order of first use."""
        ids = list(ids)
        pos = {g: k for k, g in enumerate(ids)}
        ends = list(ends)
        def ref(n):
            if n in (ZERO, ONE): return ('k', n)
            if n in pos: return ('c', pos[n])
            if n not in ends: ends.append(n)
            return ('e', ends.index(n))
        cells = []
        for g in ids:
            pairs, z, init = self.cells[g]
            cells.append(dict(pairs=[(ref(a), ref(b)) for a, b in pairs], z=ref(z), init=init))
        circ = Circuit(cells, len(ends), {k: self.names[g] for k, g in enumerate(ids) if g in self.names})
        circ.ends = ends
        return circ

    def paste(self, circ, ends, prefix=''):
        """New cells for the circuit, open end j wired to node ends[j]. Returns their ids, in circuit order."""
        assert len(ends) == circ.n_ends
        new = [self.add_cell(init=c['init'], name=prefix + circ.names[k] if k in circ.names else None) for k, c in enumerate(circ.cells)]
        def node(r):
            t, v = r
            return v if t == 'k' else new[v] if t == 'c' else ends[v]
        for k, c in enumerate(circ.cells):
            for a, b in c['pairs']: self.connect(new[k], node(a), node(b))
            self.set_z(new[k], node(c['z']))
        return new

    # ---------------------------------------------------------------- black boxes
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

    # ---------------------------------------------------------------- run
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

    def state(self):
        s = np.zeros((self._next, self.words), np.uint64)
        s[ONE] = ALL
        for i, (_, _, init) in self.cells.items():
            if init: s[i] = ALL
        return s

    def load(self, s, word, values):
        """Write one integer per lane into a word of ports (from outside, before the run: the spec)."""
        assert all(self.kind.get(n) == 'port' for n in word)
        v = _as_ints(np.array(values, dtype=object).reshape(-1)); _write(s, word, np.broadcast_to(v, (self.lanes,)).copy(), np.ones(self.lanes, bool), self.lanes)

    def read(self, s, word):
        """One integer per lane from a word of nodes (observation)."""
        return _read(s, word, self.lanes)

    def _read_cached(self, s, word):
        """_read, remembered per word while its bits do not change (wide words are slow to turn into ints)."""
        if len(word) <= 62: return _read(s, word, self.lanes)
        cache = self.__dict__.setdefault('_rc', {})
        key, raw = tuple(word), s[list(word)].tobytes()
        hit = cache.get(key)
        if hit is None or hit[0] != raw:
            hit = cache[key] = (raw, _read(s, word, self.lanes))
        return hit[1]

    def run(self, s, ticks, stop=None, every=1):
        """Tick up to `ticks` times. If `stop` (a node) is given, end early once it is 1 in every lane."""
        ids, ptr, A, B, C = self._compile()
        if s.shape[0] < self._next:
            s = np.concatenate([s, np.zeros((self._next - s.shape[0], self.words), np.uint64)])
        lanes_mask = _lane_mask(self.lanes, self.words)
        for t in range(ticks):
            new = s.copy()
            step_cells(s, new, ids, ptr, A, B, C)
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
                ids, ptr, A, B, C = self._compile()
                if new.shape[0] < self._next:
                    grow = np.zeros((self._next - new.shape[0], self.words), np.uint64)
                    for i in range(new.shape[0], self._next):
                        if i in self.cells and self.cells[i][2]: grow[i - new.shape[0]] = ALL
                    new = np.concatenate([new, grow])
            s = new
            if stop is not None and (t + 1) % every == 0 and ((s[stop] & lanes_mask) == lanes_mask).all():
                return s, t + 1
        return s, ticks


# ------------------------------------------------------------------- bit helpers
def _lane_mask(lanes, words):
    m = np.zeros(words, np.uint64)
    for w in range(words):
        n = min(64, lanes - 64 * w)
        m[w] = ALL if n == 64 else np.uint64((1 << n) - 1)
    return m


def _bits(row, lanes):
    return np.unpackbits(row.view(np.uint8), bitorder='little')[:lanes].astype(bool)


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
