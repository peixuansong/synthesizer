"""The main net: the seed, then one net run. Run:  python3 experiments/main.py [seconds]

Words used here:
    player     boxes/player.py, an IO box: it plays every target of targets/ladder.py in turn, drives the
               candidate's inputs i0, i1, i2, and says `step` (try the next wiring) or `reset` (next target)
    region     the cells being wired: r0 (the candidate's `bit` output) and r1 (its `valid` output)
    wire       one possible connection into a region cell: x from i0, i1, i2 or the other region cell; z from
               ZERO, i0, i1 or the other region cell (r0's wires come first in the count)
    connect    one cell per wire. Its inputs are the wire's two ends (and ONE when the wire is a z wire), so
               net.py's cn links them when its cn signal rises and unlinks them when it falls
    counter    one bit per wire, driving that wire's connect cell: each count is one candidate wiring;
               `step` adds 1, `reset` clears it, and its last carry is `overflow` (every wiring tried)

Not yet in the seed: self wires (net.py's cn can't link a cell to itself) and more cells (needs copy).
"""
import sys, time
import _setup
from fastnet import FastNet
import ladder
from player import player_box


def seed():
    n = FastNet._empty()                                      # accel/: the same net, ticked faster

    def cell(y=0, x=(), z=None, terms=()):
        n.ys.append(y); c = len(n.ys) - 1
        for s in x: n._link(s, c)
        for t in terms:
            k = n._term(c)
            for s in t: n._link(s, c, 'x', k)
        if z is not None: n._link(z, c, 'z')
        return c
    ZERO = cell(); ONE = cell(z=ZERO)
    box = player_box(ladder.TARGETS, settle=20)
    pb = n._put(box)                                          # inputs pb .. pb+2; outputs pb+3 .. pb+7
    ins, step, reset = [pb + 3, pb + 4, pb + 5], pb + 6, pb + 7
    R = [cell(), cell()]
    n._link(R[0], pb); n._link(R[1], pb + 1)                  # the candidate's outputs go to the player
    wires = []
    for r, o in ((R[0], R[1]), (R[1], R[0])):
        wires += [(s, r, 'x') for s in ins + [o]] + [(s, r, 'z') for s in [ZERO] + ins[:2] + [o]]
    nreset = cell(x=[reset], z=ZERO, y=1)
    c, nc = cell(x=[step]), cell(x=[step], z=ZERO, y=1)
    bits = []
    for src, r, port in wires:
        b, nb = cell(), cell(y=1)
        for t in ((b, nc, nreset), (nb, c, nreset)): k = n._term(b); [n._link(s, b, 'x', k) for s in t]
        for t in ((nb, nc), (b, c), (reset,)): k = n._term(nb); [n._link(s, nb, 'x', k) for s in t]
        bits.append(b)
        c, nc = cell(terms=[(c, b)]), cell(terms=[(c, b)], z=ZERO, y=1)
        con = cell(x=[src, r] + ([ONE] if port == 'z' else []))   # the connect cell for this wire
        n._link(b, con, 'cn')
    n._link(c, pb + 2)                                        # the last carry: overflow
    return n, box, len(n.ys)


def main(seconds=180):
    n, box, size = seed()
    print(f'seed: {size} cells; {len(ladder.TARGETS)} targets', flush=True)
    t0, seen = time.time(), 0
    while time.time() - t0 < seconds and not (box.log and box.log[-1][1] == 'cannot play'):
        n(ticks=1000)
        for name, result, tries, tick in box.log[seen:]:
            print(f'{time.time() - t0:6.1f} s  tick {tick:7}  {name:12} {result:11} after {tries} tries', flush=True)
        seen = len(box.log)
    print(f'{time.time() - t0:.1f} s: {sum(r == "found" for _, r, _, _ in box.log)} found of {len(box.log)} played')


if __name__ == '__main__':
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 180)
