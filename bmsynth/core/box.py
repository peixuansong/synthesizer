"""A box: a net whose inside is a Python function instead of cells. It replaces a part of a cell net
to make it faster, and offers only what a net offers: inputs, outputs, box() runs it forever, and it
connects like any net (a(box), box(b, 1, 0)). It ticks in lock step with the net it sits in."""
from cell import Cell
from net import Net


class Box(Net):
    def __init__(self, f, n_in, n_out):
        """f(*input bits) -> output bits (one per output cell). Inputs and outputs are cells, as in any net."""
        super().__init__()
        self.f = f
        self.inputs = [Cell() for _ in range(n_in)]
        self.outputs = [Cell() for _ in range(n_out)]
        for c in self.inputs + self.outputs: self += c

    def _compute(self):
        """Inputs tick like cells; outputs get f of the current input bits (so they appear one tick later)."""
        out = [int(y) for y in self.f(*[c.y for c in self.inputs])]
        return [(c, c.next()) for c in self.inputs] + list(zip(self.outputs, out))

    def _blank(self):
        b = Box.__new__(Box)
        Net.__init__(b)
        b.f = self.f
        return b
