"""One cell: holds one bit, y, and ticks by
    y' = z XNOR OR( terms )
A term is one cell (its bit) or a pair of cells (their AND). z is 0, 1 or a cell (its bit).
So z = 1 gives OR, z = 0 gives NOR.

Every cell can also rewire other cells (triangle connect). On the tick its bit turns from 0 to 1 it takes
its from arms that are 1 and puts them into each of its to arms that is 1, at its port:
    term   toggle the term (A,) - or (A, C) when two from arms are 1 - in B's terms
    z      set B's z to A
    from   toggle A in B's from arms
    to     toggle A in B's to arms
A cell with no arms is a plain cell.

Connect:   a >> b         a feeds b (adds the term a to b)
           (a, b) >> c    a AND b feeds c
           c.z = a        a is c's z
"""


class Cell:
    def __init__(self, z=1, y=0, port='term'):
        self.y = int(y)                      # the cell's bit: its state
        self.z = z
        self.terms = []                      # list of (a,) or (a, b), each a Cell
        self.froms = []                      # from arms: cells it can put somewhere
        self.tos = []                        # to arms: cells it can put them into
        self.port = port                     # 'term', 'z', 'from' or 'to'

    def next(self):
        """This cell's bit after one tick, from the current bits."""
        zv = self.z.y if isinstance(self.z, Cell) else self.z
        return 1 ^ zv ^ int(any(all(c.y for c in t) for t in self.terms))

    __call__ = next                          # cell() is the same as cell.next()

    def edit(self):
        """Triangle connect, run on the tick this cell's bit turned from 0 to 1."""
        src = [a for a in self.froms if a.y][:2]            # only the first two active from arms count
        if not src: return
        for b in [b for b in self.tos if b.y]:
            if self.port == 'term':
                _toggle(b.terms, tuple(src))
            elif self.port == 'z':
                b.z = src[0]
            else:
                for a in src: _toggle(b.froms if self.port == 'from' else b.tos, a)

    def __rshift__(self, other):
        """self >> other: self feeds other. Returns other, so a >> b >> c chains."""
        other.terms.append((self,))
        return other

    def __rrshift__(self, pair):
        """(a, b) >> self: a AND b feeds self."""
        self.terms.append(tuple(pair))
        return self


def _toggle(lst, x):
    """Add x to lst, or remove it if it is already there."""
    if x in lst: lst.remove(x)
    else: lst.append(x)
