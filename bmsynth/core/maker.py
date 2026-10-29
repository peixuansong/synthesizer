"""A maker: a cell that makes cells. Generic to any net: it only reads cells and adds or wires cells.

On the tick its bit turns from 0 to 1 it reads its control cells and edits the net it belongs to:
    op 1   make one new cell
    op 2   make a row: `width` new cells side by side (lane k = the k-th new cell)
    op 3   probe: wire each probe cell k to read lane k of source 0 (its old terms are dropped)
    op 4   copy: the block = every cell from source 0's address to the newest; append n copies of it, n = source
           1's address. Each copy is made from the one before; its reads into the block's own length below it
           (and into itself) move up by that length, other reads stay. The addr cells get the last copy's start.
    op 5   place: the cell at source 1 (rel 2), or each lane of the row there (rel 0), drops its terms and copies
           lane k of source 0 (one tick late): a blank made earlier now reads a part made later
    op 6   freeze: make one match cell, 1 when the n cells at source 2 show the number m (n = source 2's lane, m =
           source 3's address; the row after them must hold their NOTs). Then for each cell of the block at
           source 0 that is 1 now, add the match cell as a term to the cell at the same offset from source 1
           (block length = source 1's lane x width).
The new cell is wired from switch bits laid out like the seed's candidate (NAMES): nor; a term on each of
x0..x3 and y; a term on each pair of those 5; z from each of those 5. If no z is chosen, z = 0 when nor is set,
else 1. x_j is a real cell named by source j: an address (the cell's place in net.cells) and how to read it:
    rel 0  the same lane (address + k); with lane n = 1..31, lanes from n on read lane n-1 (sign extend);
           with lane 32 + n, lanes from n on read cell 0 (zero fill)
    rel 1  the lane to the left (lane 0 reads cell 0, which is 0)
    rel 2  one fixed lane (address + lane), for every lane
    rel 3  the lane to the left in the row being made (a carry chain); lane 0 reads cell 0
y is the new cell itself. After making, the maker writes the address of the first new cell into its addr cells.
"""
from cell import Cell

BASE = ['x0', 'x1', 'x2', 'x3', 'y']
PAIRS = [(i, j) for i in range(5) for j in range(i + 1, 5)]
NAMES = ['nor'] + BASE + [f'{BASE[i]}.{BASE[j]}' for i, j in PAIRS] + [f'z={a}' for a in BASE]


def num(cells):
    return sum(c.y << i for i, c in enumerate(cells))


class Maker(Cell):
    def __init__(self, net, op, bits, srcs, addr, probes, width):
        """op: 3 cells; bits: 21 switch cells (NAMES); srcs: 4 triples (address cells, rel cells, lane cells);
        addr: cells that get the new address; probes: the probe cells; width: cells in a row."""
        super().__init__()
        self.net, self.op, self.bits, self.srcs = net, op, bits, srcs
        self.addr, self.probes, self.width = addr, probes, width

    def source(self, j, k, new=()):
        a, rel, lane = (num(x) for x in self.srcs[j])
        cells = self.net.cells
        if rel == 3: return new[k - 1] if k else cells[0]
        if rel == 0:
            n = lane & 31
            if not n or k < n: return cells[a + k]
            return cells[0] if lane & 32 else cells[a + n - 1]
        if rel == 1: return cells[a + k - 1] if k else cells[0]
        return cells[a + lane]

    def edit(self):
        op = num(self.op)
        if op == 3:
            for k, p in enumerate(self.probes): p.terms = [(self.source(0, k),)]
        elif op == 4: self.copy(num(self.srcs[0][0]), num(self.srcs[1][0]))
        elif op == 5:
            d, rel = num(self.srcs[1][0]), num(self.srcs[1][1])
            for k in range(self.width if rel == 0 else 1):
                c = self.net.cells[d + k]; c.terms, c.z = [(self.source(0, k),)], 1
        elif op == 6: self.freeze()
        elif op in (1, 2): self.make(op)

    def make(self, op):
        n, b = (1 if op == 1 else self.width), [c.y for c in self.bits]
        base = len(self.net.cells)
        new = [Cell() for _ in range(n)]
        for c in new: self.net += c
        for k, c in enumerate(new):
            g = [self.source(j, k, new) for j in range(4)] + [c]
            c.terms = [(g[i],) for i in range(5) if b[1 + i]] + [(g[i], g[j]) for p, (i, j) in enumerate(PAIRS) if b[6 + p]]
            zs = [g[i] for i in range(5) if b[16 + i]]
            if not zs: c.z = 0 if b[0] else 1
            elif len(zs) == 1: c.z = zs[0]
            elif not c.terms: c.z, c.terms = 0, [(s,) for s in zs]      # OR(zs) XNOR 0 = NOR(zs), exactly
            else:                                            # z sources and terms: an extra OR cell (one tick later)
                h = Cell(); h.terms = [(s,) for s in zs]; self.net += h; c.z = h
        self.tell(base)

    def copy(self, a, n):
        cells = self.net.cells
        L = len(cells) - a
        for i in range(n):
            b = a + i * L
            pos = {id(c): p for p, c in enumerate(cells[b - L:b + L])}
            new = [Cell(c.z, c.y, c.port) for c in cells[b:b + L]]
            up = lambda x: x if id(x) not in pos else cells[b + pos[id(x)]] if pos[id(x)] < L else new[pos[id(x)] - L]
            for c, d in zip(cells[b:b + L], new):
                d.terms = [tuple(up(x) for x in t) for t in c.terms]
                d.z = up(c.z) if isinstance(c.z, Cell) else c.z
                d.froms, d.tos = [up(x) for x in c.froms], [up(x) for x in c.tos]
            for d in new: self.net += d
        self.tell(a + n * L)

    def freeze(self):
        cells = self.net.cells
        (src, _, _), (dst, _, rows), (pat, _, n), (m, _, _) = [[num(x) for x in s] for s in self.srcs]
        match = Cell(z=0)                                    # NOR of the cells that differ from m
        match.terms = [(cells[pat + self.width + i],) if m >> i & 1 else (cells[pat + i],) for i in range(n)]
        self.net += match
        for k in range(rows * self.width):
            if cells[src + k].y: cells[dst + k].terms.append((match,))
        self.tell(len(cells) - 1)

    def tell(self, address):
        for i, a in enumerate(self.addr): a.y = address >> i & 1
