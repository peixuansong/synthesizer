"""A net: its cells and their state, the connections, the input cells and the output cells.

    net.cells      the cells; each holds its bit (state) and its connections (cell.py)
    net.inputs     the distinguished input cells
    net.outputs    the distinguished output cells
    net + c        add the cell c (adding a net: later); net += c works too
    net()          run the net forever
    a(b)           a new net: copies of b and a, b's outputs feeding a's inputs in order
    a(b1, b2)      b1's outputs fill a's first inputs, b2's the next ones
    a(1, 0)        a number is a constant: a cell holding that bit feeds the input
                   so a(b(1, 0)) ties b's inputs to 1, 0 and a's inputs to b's outputs; a(b(1, 0))() runs it
"""
from cell import Cell


class Net:
    def __init__(self):
        self.cells = []
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
                c.cells += x.cells; c.inputs += x.inputs; srcs += x.outputs
            else:
                k = Cell(y=int(x)); k >> k                    # holds its bit: y' = OR(y) = y
                c += k; srcs.append(k)
        a = self.copy()
        assert len(srcs) == len(a.inputs), f'{len(srcs)} values for {len(a.inputs)} inputs'
        for s, i in zip(srcs, a.inputs): s >> i
        c.cells += a.cells; c.outputs = a.outputs
        return c

    def copy(self):
        """A new net with a copy of every cell; connections, z and arms point at the copies
        (a reference to a cell outside this net is kept as it is)."""
        m = {id(c): Cell(c.z, c.y, c.port) for c in self.cells}
        f = lambda c: m.get(id(c), c)
        for c in self.cells:
            n = m[id(c)]
            n.terms = [tuple(f(x) for x in t) for t in c.terms]
            n.z = f(c.z) if isinstance(c.z, Cell) else c.z
            n.froms, n.tos = [f(x) for x in c.froms], [f(x) for x in c.tos]
        new = Net()
        new.cells = [f(c) for c in self.cells]
        new.inputs, new.outputs = [f(c) for c in self.inputs], [f(c) for c in self.outputs]
        return new

    def _tick(self):
        """One tick: every cell's next bit from the current bits, then all written together;
        then every cell whose bit just turned from 0 to 1 makes its edit (triangle connect, cell.py)."""
        new = [c.next() for c in self.cells]
        rose = [c for c, y in zip(self.cells, new) if y and not c.y]
        for c, y in zip(self.cells, new): c.y = y
        for c in rose: c.edit()
