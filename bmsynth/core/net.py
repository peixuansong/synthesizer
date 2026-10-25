"""A net: its cells and their state, the connections, the input cells and the output cells.

    net.cells      the cells; each holds its bit (state) and its connections (cell.py)
    net.nets       nets placed inside this net (e.g. by a(b) below); they tick with it
    net.inputs     the distinguished input cells
    net.outputs    the distinguished output cells
    net + c        add the cell c (adding a net: later); net += c works too
    net()          run the net forever
    a(b)           a new net holding copies of b and a, b's outputs feeding a's inputs in order
    a(b1, b2)      b1's outputs fill a's first inputs, b2's the next ones
    a(1, 0)        a number is a constant: a cell holding that bit feeds the input
                   so a(b(1, 0)) ties b's inputs to 1, 0 and a's inputs to b's outputs; a(b(1, 0))() runs it
"""
from cell import Cell


class Net:
    def __init__(self):
        self.cells = []
        self.nets = []
        self.inputs = []
        self.outputs = []

    def __add__(self, x):
        if isinstance(x, Cell):
            self.cells.append(x)
            return self
        return NotImplemented

    def __call__(self, *args):
        if not args:
            while True:
                self._tick()
        return self._compose(args)

    def _compose(self, args):
        """A new net: copies of the argument nets (or constant cells), then a copy of self reading them."""
        c, srcs = Net(), []
        for x in args:
            if isinstance(x, Net):
                x = x.copy()
                c.nets.append(x); c.inputs += x.inputs; srcs += x.outputs
            else:
                k = Cell(y=int(x)); k >> k                    # holds its bit: y' = OR(y) = y
                c += k; srcs.append(k)
        a = self.copy()
        assert len(srcs) == len(a.inputs), f'{len(srcs)} values for {len(a.inputs)} inputs'
        for s, i in zip(srcs, a.inputs): s >> i
        c.nets.append(a); c.outputs = a.outputs
        return c

    # ---------------------------------------------------------------- copy
    def copy(self):
        """A new net with a copy of every cell (also in its inner nets); connections, z and arms point at the
        copies (a reference to a cell outside this net is kept as it is)."""
        m = {}
        self._make(m)
        return self._fill(m)

    def _make(self, m):
        for c in self.cells: m[id(c)] = Cell(c.z, c.y, c.port)
        for n in self.nets: n._make(m)

    def _fill(self, m):
        f = lambda c: m.get(id(c), c)
        for c in self.cells:
            n = m[id(c)]
            n.terms = [tuple(f(x) for x in t) for t in c.terms]
            n.z = f(c.z) if isinstance(c.z, Cell) else c.z
            n.froms, n.tos = [f(x) for x in c.froms], [f(x) for x in c.tos]
        new = self._blank()
        new.cells, new.nets = [f(c) for c in self.cells], [n._fill(m) for n in self.nets]
        new.inputs, new.outputs = [f(c) for c in self.inputs], [f(c) for c in self.outputs]
        return new

    def _blank(self):
        """An empty net of the same kind (a box keeps its function)."""
        return Net()

    # ---------------------------------------------------------------- tick
    def _tick(self):
        """One tick, in lock step: every cell (also in inner nets) works out its next bit from the current bits,
        then all are written at once; then every cell whose bit just turned from 0 to 1 makes its edit
        (triangle connect, cell.py)."""
        new = self._compute()
        rose = [c for c, y in new if y and not c.y]
        for c, y in new: c.y = y
        for c in rose: c.edit()

    def _compute(self):
        """(cell, next bit) for every cell of this net and its inner nets, from the current bits."""
        return [(c, c.next()) for c in self.cells] + [p for n in self.nets for p in n._compute()]
