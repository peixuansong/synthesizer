"""One cell: holds one bit, y, and ticks by
    y' = z XNOR OR( terms )
A term is one cell (its bit) or a pair of cells (their AND). z is 0, 1 or a cell (its bit).
So z = 1 gives OR, z = 0 gives NOR.

Connect:   a >> b         a feeds b (adds the term a to b)
           (a, b) >> c    a AND b feeds c
           c.z = a        a is c's z
"""


class Cell:
    def __init__(self, z=1, y=0):
        self.y = int(y)                      # the cell's bit: its state
        self.z = z
        self.terms = []                      # list of (a,) or (a, b), each a Cell

    def next(self):
        """This cell's bit after one tick, from the current bits."""
        zv = self.z.y if isinstance(self.z, Cell) else self.z
        return 1 ^ zv ^ int(any(all(c.y for c in t) for t in self.terms))

    def __rshift__(self, other):
        """self >> other: self feeds other. Returns other, so a >> b >> c chains."""
        other.terms.append((self,))
        return other

    def __rrshift__(self, pair):
        """(a, b) >> self: a AND b feeds self."""
        self.terms.append(tuple(pair))
        return self
