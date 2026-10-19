"""A net: its cells and their state, the connections, the input cells and the output cells.

    net.cells      the cells; each holds its bit (state) and its connections (cell.py)
    net.inputs     the distinguished input cells
    net.outputs    the distinguished output cells
    net + c        add the cell c (adding a net: later); net += c works too
    net()          run the net forever
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

    def __call__(self):
        while True:
            self._tick()

    def _tick(self):
        """One tick: every cell's next bit from the current bits, then all written together."""
        new = [c.next() for c in self.cells]
        for c, y in zip(self.cells, new): c.y = y
