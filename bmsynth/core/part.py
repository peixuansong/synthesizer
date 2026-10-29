"""Copy and paste: taking cells out of a net and putting copies of them into a net.

A part is a net plus a list of its ends. An end is a distinguished cell of that net: it stands for an input from
outside, and is replaced by a real node when the part is pasted.

    copy(net, ids)          -> Part   the cells `ids` in a new net; each outside node they read becomes an end
    paste(net, part, ends)  -> ids    new cells in `net` for the part's other cells; end j is read as node ends[j]
"""
from net import Net, ZERO, ONE


class Part:
    def __init__(self, net, ends, outside=()):
        self.net = net                       # the cells
        self.ends = list(ends)               # cells of self.net that stand for inputs from outside
        self.outside = list(outside)         # the nodes the ends stood for where the part was copied from


def copy(net, ids, ends=()):
    """The cells `ids` as a Part. The outside nodes they read become its ends: `ends` first, in the order given,
    then any others in order of first use."""
    ids, outside = list(ids), list(ends)
    for g in ids:
        prs, z = net.pairs(g)
        for n in [x for p in prs for x in p] + [z]:
            if n not in (ZERO, ONE) and n not in ids and n not in outside: outside.append(n)
    part = Net()
    e = [part.add_cell() for _ in outside]
    new = [part.add_cell(init=net.cells[g][2]) for g in ids]
    _wire(net, ids, part, new, {**dict(zip(outside, e)), **dict(zip(ids, new))})
    return Part(part, e, outside)


def paste(net, part, ends):
    """New cells in `net` for every cell of the part that is not an end; a read of end j becomes a read of node
    ends[j]. Returns the new cells' ids, in the part's order."""
    assert len(ends) == len(part.ends)
    src = part.net
    body = [i for i in sorted(src.cells) if i not in part.ends]
    new = [net.add_cell(init=src.cells[i][2]) for i in body]
    _wire(src, body, net, new, {**dict(zip(part.ends, ends)), **dict(zip(body, new))})
    return new


def _wire(src, ids, dst, new, m):
    """Give each cell new[k] in dst the wiring of cell ids[k] in src, every node renamed through m (constants stay)."""
    m = {ZERO: ZERO, ONE: ONE, **m}
    for g, c in zip(ids, new):
        prs, z = src.pairs(g)
        for a, b in prs: dst.connect(c, m[a], m[b])
        dst.set_z(c, m[z])
