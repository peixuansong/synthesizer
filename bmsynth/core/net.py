"""The core: one cell rule, and the only API anything outside core/ may use.

A net is a set of nodes. Node 0 is constant 0, node 1 is constant 1. Every other node is a
    cell   y(t+1) = s(t)[z] XNOR OR_k ( s(t)[a_k] AND s(t)[b_k] )
Each node holds one bit.

API (nothing else is offered):
    run                    state(), run(), read()
    cells                  add_cell(), remove_cell(), set_init(), pairs()
    connections            connect(), disconnect(), set_z()
    copy / paste           copy() -> Circuit, paste()

Lanes are in lanes.py; ports and black boxes in boxnet.py.
"""
import numpy as np
from tick import step_cells

ZERO, ONE = 0, 1


class Circuit:
    """A copied group of cells. References are ('c', i) internal cell, ('k', 0/1) constant, ('e', j) open end."""

    def __init__(self, cells, n_ends, names=None):
        self.cells, self.n_ends, self.names = cells, n_ends, names or {}


class Net:
    def __init__(self):
        self.kind = {ZERO: 'const', ONE: 'const'}
        self.cells = {}                      # id -> [pairs list, z, init]
        self.names = {}
        self._next, self._compiled = 2, None

    # ---------------------------------------------------------------- cells
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
        """One bit per node, at tick 0."""
        s = np.zeros(self._next, np.uint8)
        s[ONE] = 1
        for i, (_, _, init) in self.cells.items():
            if init: s[i] = 1
        return s

    def read(self, s, word):
        """An integer from a word of nodes, bit 0 first (observation)."""
        return sum(int(s[n]) << k for k, n in enumerate(word))

    def _tick(self, s):
        """One tick of every cell."""
        new = s.copy()
        step_cells(s, new, *self._compile())
        return new

    def _is_one(self, s, node):
        return s[node] == 1

    def run(self, s, ticks, stop=None, every=1):
        """Tick up to `ticks` times. If `stop` (a node) is given, end early once it is 1."""
        if s.shape[0] < self._next:                 # nodes added since state(): they start at 0
            s = np.concatenate([s, np.zeros((self._next - s.shape[0],) + s.shape[1:], s.dtype)])
        for t in range(ticks):
            s = self._tick(s)
            if stop is not None and (t + 1) % every == 0 and self._is_one(s, stop):
                return s, t + 1
        return s, ticks

