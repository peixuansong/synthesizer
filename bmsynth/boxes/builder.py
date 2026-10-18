"""Box file: the builder. Placed only through the net:
    net.place_box('builder.BUILD', call, [op, cell, a, b], [made], net=net, source=[...], nodes=[...])

  BUILD  lets the net change itself during a run: on a tick where it is called it either pastes a new copy of the
         `source` cells, adds / removes one pair (a AND b) on a cell, or sets a cell's z input.

The table: every node the box can name. It starts as `nodes` (given at placement) and every cell the box pastes is
appended to it, in order. The ports cell, a, b are positions in this table.

    op  0  nothing
        1  paste a copy of `source` (wired to whatever `source` reads); the new cells are appended to the table
        2  connect     add the pair (table[a] AND table[b]) to cell table[cell]
        3  disconnect  remove that pair (nothing happens if the cell does not have it)
        4  set z       the cell's z input becomes table[a]
    made   output: how many copies have been pasted so far.

An edit changes the net itself, so it is the same for every lane: all calling lanes must ask for the same edit.
"""
import numpy as np


def BUILD(net, source, nodes):
    # RULE VIOLATION (PEIXUAN, 2026-10-17): hand-written from scratch, and it edits the net from inside a run
    # (boxes must not touch the net). Agreed as a stopgap until cells can make and connect cells themselves.
    """BUILD(lanes, op, cell, a, b) -> (made,)."""
    source, table, made = list(source), list(nodes), [0]

    def run(lanes, op, cell, a, b):
        req = {(int(o), int(c), int(x), int(y)) for o, c, x, y in zip(op, cell, a, b)}
        assert len(req) == 1, 'BUILD: lanes asked for different edits'
        o, c, x, y = req.pop()
        if o == 1:
            circ = net.copy(source)
            table.extend(net.paste(circ, circ.ends))
            made[0] += 1
        elif o in (2, 3) and max(c, x, y) < len(table):
            cell_, pair = table[c], (table[x], table[y])
            if o == 2:
                net.connect(cell_, *pair)
            elif pair in net.pairs(cell_)[0]:
                net.disconnect(cell_, *pair)
        elif o == 4 and max(c, x) < len(table):
            net.set_z(table[c], table[x])
        return (np.full(len(lanes), made[0], np.int64),)
    return run
