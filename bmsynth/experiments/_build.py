"""Hand-building by the core API only: a few gate shorthands and the seed searcher.

Gates are single cells of the BMN rule  y' = s[z] XNOR OR_k(s[a_k] AND s[b_k]):
    OR(x..)  z = 1, one pair (x, 1) per input        NOR(x..)  the same with z = 0
    AND(x, y)  z = 1, the pair (x, y)                 NOT(x)    z = 0, the pair (x, 1)
"""
import numpy as np
import _setup
from net import ONE, ZERO
from part import paste
import math

LIB_K, LIB_EW = 64, 256                 # the flat library: 64 entries, one 256-bit word of ports each
SLOT = dict(M=3, P=2, NI=3)             # programmable slot: 3 cells, 2 pairs per cell, 3 inputs
SLOT_SB = math.ceil(math.log2(2 + SLOT['NI'] + SLOT['M']))      # bits per source field
SLOT_CB = 1 + 2 * SLOT['P'] * SLOT_SB                           # paste-port bits per slot cell
SLOT_CW = SLOT['M'] * SLOT_CB                                   # paste-port width


def cell(net, pairs, z=ONE, init=0, name=None):
    c = net.add_cell(z=z, init=init, name=name)
    for a, b in pairs: net.connect(c, a, b)
    return c


OR = lambda net, *xs, **k: cell(net, [(x, ONE) for x in xs], ONE, **k)
NOR = lambda net, *xs, **k: cell(net, [(x, ONE) for x in xs], ZERO, **k)
AND = lambda net, x, y, **k: cell(net, [(x, y)], ONE, **k)
NOT = lambda net, x, **k: cell(net, [(x, ONE)], ZERO, **k)


def ports(net, n, name):
    return [net.add_port(f'{name}{i}') for i in range(n)]


def ring(net, P, delay=None):
    """P cells passing one 1 around, cell P-1 starts at 1. With `delay` (a found 1-cell delay Part),
    the ring is P pasted copies of it closed into a loop; otherwise P hand cells r_i' = r_{i-1}."""
    if delay is None:
        r = [net.add_cell(init=int(i == P - 1), name=f'r{i}') for i in range(P)]
        for i in range(P): net.connect(r[i], r[i - 1])
        return r
    tmp = net.add_port()
    r = [paste(net, delay, [tmp], prefix=f'r{i}.')[0] for i in range(P)]
    for i in range(P):                                          # close the loop: the open end of copy i reads copy i-1
        prs, z = net.pairs(r[i])
        for a, b in prs:
            if tmp in (a, b):
                net.disconnect(r[i], a, b); net.connect(r[i], r[i - 1] if a == tmp else a, r[i - 1] if b == tmp else b)
        if z == tmp: net.set_z(r[i], r[i - 1])
    net.remove_port(tmp)
    net.set_init(r[P - 1], 1)                                   # the one token
    return r


def library(net, K=LIB_K):
    """The flat library: K words of ports (0 = empty), the same value in every lane."""
    return [ports(net, LIB_EW, f'lib{k}.') for k in range(K)]


def searcher(net, EVAL, eval_ins, lib, ROUND=None, round_ins=(), QB=32, OB=17, P=8, off=None, start=None, bus=False,
             round_lib=None, round_outs=None, eval_outs=()):
    """The seed searcher, all control in cells. Each period of P ticks, in every lane still searching:
        call EVAL(q, library, ...)  -> res (1 + position of the first hit in block q, 0 = none), end (q past the space),
                                       ans (the hit, written so it keeps its meaning as the library grows)
        go = NOR(res, end)          -> q <- q + 1 (ADD box) while go
    and across lanes, every period (no rounds):
        ROUND(ans, res, ..., library) -> library    (e.g. append every find so far to the library)
        ALL(done)                     -> all; all -> halt (every lane solved, out of candidates, or off)
    Nothing else limits the search: the run is stopped from outside by a tick or time cap.
    off (optional node): 1 in lanes that take no part in this search (they count as done).
    start (optional node): the ring holds no token until start pulses, so the searcher waits for it.
    EVAL, ROUND: (box name, params), placed with net.place_box. lib: the library words EVAL reads.
    bus: EVAL is called in every lane each period with go, res and ans as inputs (so it can read every lane's
         answer); lanes with go = 0 keep their res and ans.
    round_lib / round_outs: the library words ROUND reads / the words it writes (default: lib / lib).
    eval_outs: more words EVAL writes after (res, end, ans) (e.g. observation ports).
    Returns the nodes to observe."""
    r = ring(net, P)
    if start is not None:
        net.set_init(r[P - 1], 0); net.connect(r[0], start)
    elif off is not None:                                       # token one cell back, so the first call sees go computed with off
        net.set_init(r[P - 1], 0); net.set_init(r[P - 2], 1)
    x = [off] if off is not None else []
    q, res, end = ports(net, QB, 'q'), ports(net, OB, 'res'), net.add_port('end')
    ans = ports(net, LIB_EW, 'ans')
    allp = net.add_port('all')
    go = NOR(net, *res, end, *x, init=1, name='go')
    done = OR(net, *res, end, *x, name='done')
    call = r[P - 1] if bus else AND(net, r[P - 1], go, name='call')
    adv = AND(net, r[2], go, name='advance')
    halt = cell(net, [(r[0], allp)], name='halt'); net.connect(halt, halt)
    nh = NOT(net, halt, init=1)                                 # a halted searcher stops: its token is dropped
    for a, b in net.pairs(r[0])[0]:
        if r[P - 1] in (a, b) and ONE in (a, b):
            net.disconnect(r[0], a, b); net.connect(r[0], r[P - 1], nh)
    net.place_box(EVAL[0], call, ([q, [go], res, ans] if bus else [q]) + lib + eval_ins, [res, [end], ans] + list(eval_outs), **EVAL[1])
    net.place_box('arith.OP', adv, [q, [ONE]], [q], name='ADD')
    net.place_box('_build.ALL', r[5], [[done]], [[allp]])
    if ROUND: net.place_box(ROUND[0], r[6], [ans, res] + list(round_ins) + (round_lib or lib), round_outs or lib, **ROUND[1])
    return dict(q=q, res=res, end=end, ans=ans, lib=lib, halt=halt, done=done, ring=r, P=P)



def ALL():
    # RULE VIOLATION (PEIXUAN, 2026-10-16): hand-written from scratch; it does not replace cells already found in the net.
    """Box placed by the searcher (net.place_box('_build.ALL', ...)): 1 in every calling lane if `done` is 1 in all
    of them. Lanes share one set of cells, so no cell can read another lane; this reads them all."""
    def run(lanes, x):
        return np.full(len(lanes), int(np.all(np.asarray(x) != 0)), np.int64),
    return run

def boot(net, start=None):
    """Start-up cells: `boot` is 1 on tick 0 only (or one tick after `start` pulses; it calls the dictionary node);
    `rst` is 1 until then and for 3 more ticks, while the paste ports are written and decoded."""
    b = cell(net, [] if start is None else [(start, ONE)], ONE, init=int(start is None), name='boot')
    r1 = cell(net, [(b, ONE)]); r2 = cell(net, [(r1, ONE)])
    started = cell(net, [(b, ONE)], name='started'); net.connect(started, started)
    waiting = NOT(net, started, init=1)                         # slots are held at 0 until the dictionary node has run
    return b, OR(net, b, r1, r2, waiting, init=1, name='rst')


def slot(net, ins, rst, name='slot'):
    """A programmable slot (generic cells): its paste port (a config word in the layout SLOT; celleval.DICT writes it) switches
    which sources each of its M cells reads, so it behaves as any circuit up to M cells, P pairs per cell, NI
    inputs. It runs at half speed: a mux layer picks each pair's sources, then the slot cell combines them, so
    one step of the circuit takes 2 ticks. While rst is 1 the slot is held at 0. Returns (paste port, output, cells)."""
    M, P, NI, SB, CB = SLOT['M'], SLOT['P'], SLOT['NI'], SLOT_SB, SLOT_CB
    cfg = ports(net, SLOT_CW, name + '.cfg')
    u = [net.add_cell(name=f'{name}.u{j}') for j in range(M)]
    src = [ZERO, ONE] + list(ins) + [ZERO] * (NI - len(ins)) + u
    nots = [NOT(net, c) for c in cfg]
    def mux(field):                                         # field: SB config ports; one-hot decode, then select
        terms = []
        for s in range(1, len(src)):
            lits = [nots[field[k]] if (s >> k) & 1 else cfg[field[k]] for k in range(SB)]
            d = NOR(net, *lits, rst)                        # 1 iff the field says s (and not in reset)
            terms.append((src[s], d))
        return cell(net, terms, ONE)
    for j in range(M):
        base = j * CB
        z1 = OR(net, cfg[base], rst, init=1); z = cell(net, [(z1, ONE)], init=1)   # z delayed to line up with the mux layer
        net.set_z(u[j], z)
        for k in range(P):
            fa = [base + 1 + 2 * SB * k + i for i in range(SB)]
            fb = [f + SB for f in fa]
            net.connect(u[j], mux(fa), mux(fb))
    return cfg, u[-1], u


def rising(net, x, name=None):
    """1 for one tick after x turns from 0 to 1."""
    was_not = NOT(net, x, init=1)                               # at tick t: not x(t-1)
    return cell(net, [(x, was_not)], name=name)
