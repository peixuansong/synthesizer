"""Rules for changes here: a change must fundamentally make sense, remain small and succinct, and avoid piling up
jugaads. Core must be generic: it must not be overfit to any task. Turing completeness.

A net: any collection of cells, and the connections between them. A cell is one bit, net.ys[i]; it is known
by its number i. All a cell does is the computation in __call__ below.

    net.edges      the connections, one wire each: (src, dst, port, term); port is 'x', 'z', 'cp' or 'cn'.
                   A term of dst is all its x wires with the same term number: the AND of their srcs. A cell
                   with no z edge has z = 1; no cp or cn edge, 0
    net.inputs     the distinguished input cells (numbers); net.outputs the output cells
    net.boxes      (f, inputs, outputs): outputs get f of the inputs' bits each tick
    Net()          a solo net: one cell (bit 0), which is its input and its output
    Net(f, n_in, n_out)   a box: a net whose inside is the function f instead of cells (it replaces a part of a
                   cell net to make it faster): n_in input cells, n_out output cells; outputs get f(*input bits)
                   one tick later. It connects like any net
    a + b          a new net: copies of a and b side by side (b's numbers move up by len(a.ys)), inputs a's then
                   b's, outputs a's then b's
    a >> b         a new net: copies of the nets a and b, a's outputs feeding b's inputs in order (x edges);
                   its inputs are a's, its outputs b's. a >> (b, port) feeds port 'z', 'cp' or 'cn' instead
    (a1, a2) >> b  the same, a1's outputs AND a2's outputs feeding b's inputs (one term)
    net[d]         d's inputs: the cells of its x edges, in order, each once
    net()          run the net forever; net(ticks=n) runs n ticks

Every tick the net runs two operations for its cells (both start from a cell c's inputs: the cells of its x edges,
in order, each once):
    cp   copy: when c's cp turns from 0 to 1, c's inputs and the connections between them become a net that is
         added to this one (its interface stays the same); connections into them from other cells are kept
         on the copies too
    cn   connect: inputs 0 and 1 are A and B, the bits of the others code the port (input 2 is its lowest bit:
         0 x, 1 z, 2 cp, 3 cn). When c's cn turns from 0 to 1, A is linked to B at that port; from 1 to 0, unlinked
"""
PORTS = ['x', 'z', 'cp', 'cn']


class Net:
    def __init__(self, f=None, n_in=0, n_out=0):
        self.edges, self.boxes = [], []
        self.ys, self.inputs, self.outputs = [0], [0], [0]
        if f:
            self.ys = [0] * (n_in + n_out)
            self.inputs, self.outputs = list(range(n_in)), list(range(n_in, n_in + n_out))
            self.boxes = [(f, self.inputs, self.outputs)]

    def __add__(self, x):
        c = Net._empty(); c._put(self); k = c._put(x)
        c.inputs = self.inputs + [i + k for i in x.inputs]
        c.outputs = self.outputs + [o + k for o in x.outputs]
        return c

    @staticmethod
    def _empty():
        n = Net(); n.ys, n.inputs, n.outputs = [], [], []
        return n

    def _put(self, x):
        """Put a copy of x's cells, edges and boxes into this net (its interface stays); returns x's offset."""
        k = len(self.ys)
        self.ys += x.ys
        self.edges += [(s + k, d + k, p, t) for s, d, p, t in x.edges]
        self.boxes += [(f, [i + k for i in ins], [o + k for o in outs]) for f, ins, outs in x.boxes]
        return k

    def __rshift__(self, b):
        b, port = b if isinstance(b, tuple) else (b, 'x')
        return Net._join([self], b, port)

    def __rrshift__(self, pair):
        return Net._join(list(pair), self, 'x')

    @staticmethod
    def _join(srcs, b, port):
        """A new net: copies of the nets srcs and b; output j of each src (ANDed when two) feeds b's input j."""
        c, outs = Net._empty(), []
        for a in srcs:
            k = c._put(a)
            outs.append([o + k for o in a.outputs]); c.inputs += [i + k for i in a.inputs]
        k = c._put(b)
        for j, i in enumerate(b.inputs):
            t = c._term(i + k)
            for o in outs: c._link(o[j], i + k, port, t)
        c.outputs = [o + k for o in b.outputs]
        return c

    def _term(self, d):
        """A term number not yet used by d."""
        return 1 + max([t for s, e, p, t in self.edges if e == d], default=-1)

    def _link(self, s, d, port='x', term=None):
        if port != 'x': self.edges = [e for e in self.edges if not (e[1] == d and e[2] == port)]   # one bit
        self.edges.append((s, d, port, self._term(d) if term is None else term))

    def _unlink(self, s, d, port='x'):
        self.edges = [e for e in self.edges if e[:3] != (s, d, port)]

    def __getitem__(self, d):
        return list(dict.fromkeys(s for s, e, p, t in self.edges if e == d and p == 'x'))

    def __call__(self, ticks=None):
        """Run `ticks` ticks (forever if None). Each tick, in lock step: every cell works out its next bit from
        the current bits, then all are written at once; then cp and cn run for every cell whose signal changed."""
        n = 0
        while ticks is None or n < ticks:
            n += 1
            ys = self.ys
            z, xs, sig = [1] * len(ys), [{} for _ in ys], {}
            for s, d, p, t in self.edges:
                if p == 'x': xs[d][t] = xs[d].get(t, 1) & ys[s]
                elif p == 'z': z[d] = ys[s]
                else: sig[d, p] = s
            # A cell: y' = z XNOR OR( terms ). z is one bit (1 if no z edge); a term is the AND of the x wires
            # with one term number. So z = 1 gives OR, z = 0 gives NOR; a cell with no edges is always 0.
            new = [1 ^ z[i] ^ int(any(xs[i].values())) for i in range(len(ys))]
            for f, ins, outs in self.boxes:
                for o, v in zip(outs, f(*[ys[i] for i in ins])): new[o] = int(v)
            self.ys = new
            for (d, p), s in list(sig.items()):
                if ys[s] == new[s]: continue
                if p == 'cp' and new[s]: self._cp(d)
                if p == 'cn': self._cn(d, new[s])

    def _cp(self, d):
        """Copy d's inputs and the connections between them as a net, add it; outside feeds are kept too."""
        ins = self[d]
        pos = {c: i for i, c in enumerate(ins)}
        m = Net._empty(); m.ys = [self.ys[c] for c in ins]
        k, outside = len(self.ys), []
        for s, d, p, t in self.edges:
            if d not in pos: continue
            if s in pos: m.edges.append((pos[s], pos[d], p, t))
            else: outside.append((s, pos[d] + k, p, t))
        self._put(m)
        self.edges += outside

    def _cn(self, d, on):
        """Link (on = 1) or unlink (on = 0) d's inputs 0 and 1 at the port its other inputs code."""
        ins = self[d]
        if len(ins) < 2: return
        a, b = ins[0], ins[1]
        port = PORTS[sum(self.ys[c] << i for i, c in enumerate(ins[2:])) % len(PORTS)]
        if on: self._link(a, b, port)
        else: self._unlink(a, b, port)
