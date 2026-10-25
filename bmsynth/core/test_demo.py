"""Demo: build small nets by hand, tick them, and probe the cells' bits.

Run:  python3 core/test_demo.py      (prints what it sees; an assert fails if a result is wrong)
net() runs forever, so the demo steps the net one tick at a time with net._tick().
"""
from cell import Cell
from net import Net


def hold(net, bit):
    """An input cell that keeps its bit: it feeds itself (z = 1, so y' = OR(y) = y)."""
    c = Cell(y=bit)
    c >> c
    net += c
    net.inputs.append(c)
    return c


def oscillator():
    """One NOR cell feeding itself: y' = NOT y, so it flips every tick."""
    net = Net()
    c = Cell(z=0)
    c >> c
    net += c
    seen = []
    for _ in range(6):
        net._tick()
        seen.append(c.y)
    print('oscillator     ', seen)
    assert seen == [1, 0, 1, 0, 1, 0]


def gates():
    """Two held inputs a, b and six gate cells; after one tick each gate shows its truth table.
    XOR needs two layers (NOT cells first), so it is read after the second tick."""
    print('a b | AND OR NOR NAND | XOR')
    for a_bit in (0, 1):
        for b_bit in (0, 1):
            net = Net()
            a, b = hold(net, a_bit), hold(net, b_bit)
            AND = Cell(); (a, b) >> AND
            OR = Cell(); a >> OR; b >> OR
            NOR = Cell(z=0); a >> NOR; b >> NOR
            NAND = Cell(z=0); (a, b) >> NAND
            na = Cell(z=0); a >> na                       # NOT a
            nb = Cell(z=0); b >> nb                       # NOT b
            XOR = Cell(); (a, nb) >> XOR; (na, b) >> XOR  # (a AND NOT b) OR (NOT a AND b)
            for c in (AND, OR, NOR, NAND, na, nb, XOR): net += c
            net.outputs += [AND, OR, NOR, NAND, XOR]
            assert AND() == (a_bit & b_bit)               # probe with cell(): the bit after the next tick
            net._tick()
            net._tick()
            out = [c.y for c in net.outputs]
            print(f'{a_bit} {b_bit} |  {out[0]}   {out[1]}   {out[2]}   {out[3]}   |  {out[4]}')
            assert out == [a_bit & b_bit, a_bit | b_bit, 1 - (a_bit | b_bit), 1 - (a_bit & b_bit), a_bit ^ b_bit]


def delay_line():
    """A pulse travelling down a chain of 4 cells: each cell copies the one before, one tick later."""
    net = Net()
    chain = [Cell(y=1)] + [Cell() for _ in range(3)]
    for prev, c in zip(chain, chain[1:]): prev >> c
    for c in chain: net += c
    rows = []
    for _ in range(4):
        rows.append([c.y for c in chain])
        net._tick()
    print('delay line     ', rows)
    assert rows == [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def z_from_a_cell():
    """z can be a cell: y' = x XNOR a. With a held at 0 the cell is NOT a; with a held at 1 it copies x."""
    for a_bit in (0, 1):
        net = Net()
        a, x = hold(net, a_bit), hold(net, 1)
        y = Cell(z=a); x >> y
        net += y
        net._tick()
        print(f'z = a = {a_bit}, x = 1  ->  y = {y.y}')
        assert y.y == 1 ^ a_bit ^ 1


if __name__ == '__main__':
    oscillator()
    gates()
    delay_line()
    z_from_a_cell()
    print('all checks passed')
