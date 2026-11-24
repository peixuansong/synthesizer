"""The main net: the small seed, then net(). Nothing else runs.

The seed (notes/targets-1-seed-and-ops.md):
    fixed cells    0 = always 0, 1 = T, 2 = TEST, rows A and B, GO: copies of what the target box drives
    candidate      one cell y with 21 switch bits (core/maker.py NAMES); every input reaches it 3 ticks late
    counter        fewest.py: sets of 0..3 switch bits, fewest first; `go` steps it, `clr` restarts it
    checker        a latch that is set when y differs from the wanted bit at a strobe; passed = the try ended
                   (dec) with no mismatch
    maker          on passed, makes the found cell or row from the switch bits, wired to the real sources the box
                   names; on the box's act pulse, wires the box's probe inputs to a cell or row, or copies a block
    target box     targets/target_box.py: plays every target in turn (a black box, inside the net)
The net only grows by what it finds. Run:  python3 experiments/main.py   (it may never end; watch.py looks)
"""
import _setup
from cell import Cell
from fastnet import FastNet
from maker import Maker, NAMES
from fewest import fewest
from target_box import target_box, AW
from machine_targets import TARGETS, W, samples
from mul_div_targets import TARGETS_C
from cpu_targets import TARGETS_D
from cpu_control import TARGETS_E
from cpu_runs import TARGETS_K
import gridsearcher as G


def wire(net, y, bits, g):
    """Cell y reads g (4 sources and its own value, each already one tick late) through the switch bits."""
    srcs = [G.delay(net, a) for a in g] + [G.cell(net, terms=[(a, b)]) for i, a in enumerate(g) for b in g[i + 1:]]
    zb = bits[16:21]
    nz = G.cell(net, z=0, terms=[bits[0]] + zb)                               # no z source and not nor
    y.z = G.cell(net, terms=[nz] + list(zip(zb, g)))
    for b, s in zip(bits[1:16], srcs): (b, s) >> y
    net += y


def seed():
    net, box = FastNet(), target_box(TARGETS + TARGETS_C + TARGETS_D + TARGETS_E + TARGETS_K, W, samples)
    o, i = box.o, box.i
    c = lambda **k: G.cell(net, **k)
    net += Cell()                                                             # place 0: always 0
    for name in ('T', 'TEST', 'A', 'B', 'GO'):
        for x in o[name]: G.delay(net, x)                                     # places 1, 2, 3.., 3+W.., 3+2W
    net.nets.append(box)
    mism = Cell(); net += mism                                                # a mismatch seen in this try
    dec, ndec = o['dec'][0], o['ndec'][0]
    passed = c(z=0, terms=[ndec, mism])                                       # dec AND no mismatch
    bits, done = fewest(net, c(terms=[(dec, mism)]), o['clr'][0], len(NAMES))
    y = Cell()
    wire(net, y, bits, [G.delay(net, x) for x in o['x']] + [c(terms=[(y, o['nrst'][0])])])
    neq = G.NOT(net, c(z=y, terms=[o['want'][0]]))                            # y differs from the wanted bit
    (o['strobe'][0], neq) >> mism; (mism, ndec) >> mism
    addr = [c() for _ in range(AW)]
    for a, b in zip(addr, i['addr']): a >> a; a >> b                          # holds the maker's last address
    srcs = [(s[:AW], s[AW:AW + 2], s[AW + 2:AW + 8]) for s in (o['src'][k * 28:(k + 1) * 28] for k in range(4))]
    mk = Maker(net, o['op'], bits, srcs, addr, i['probe'], W)
    passed >> mk; o['act'][0] >> mk; net += mk
    passed >> i['passed'][0]; done >> i['fdone'][0]
    return net


if __name__ == '__main__':
    seed()()
