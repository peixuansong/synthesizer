"""Targets for the program machine, part 2 (clock, constants) and part 3 (word ops); see notes/oeis-dep-machine.md.
Only descriptions: what each new cell reads (its sources) and what it must output. No nets here.

Words:
    W         lanes per word (bit k of a word sits in lane k)
    row       a word: W cells; a row target is searched once (as lane 0) and its find is copied into every lane
    source    a name: a spine cell ('T'), a row in the same lane ('A'), the lane to the left (('CY', 'L')),
              or one fixed lane of a row (('CYS', W - 1))
    driven    T, A, B: set by the target box (only while a check target runs)
A search target: f(x, y) = the wanted output, x = its sources' values this step, y = its own value last step.
twin {i: j}: source i is NOT source j (the box drives them so). A check target searches nothing: the box drives
`drive` and the seed checks the named row (or cell) against `want`, sample by sample.
"""
import random

W = 16
M = (1 << W) - 1
NOT1 = lambda x, y: 1 - x[0]
COPY = lambda x, y: x[0]
XNOR = lambda x, y: 1 - (x[0] ^ x[1])
MAJ = lambda x, y: (x[0] & x[1]) | (x[0] & x[2]) | (x[1] & x[2])
MUX = lambda x, y: x[1] if x[0] else x[2]                       # sources: s, u, v, NOT s
L = lambda r: (r, 'L')
s16 = lambda w: w - (1 << W) if w >> (W - 1) else w              # a word read as signed

random.seed(1)
PAIRS = [(0, 0), (M, 1), (5, 3), (3, 5), (M, M), (1 << (W - 1), 1)] + \
        [(random.randrange(1 << W), random.randrange(1 << W)) for _ in range(10)]
AB = dict(A=lambda s: PAIRS[s][0], B=lambda s: PAIRS[s][1])
check = lambda name, out, want, drive=AB: dict(name=name, kind='check', out=out, drive=drive, n=len(PAIRS),
                                               want=lambda s: want(*PAIRS[s]))

TARGETS = [
    # part 2: clock and constants
    dict(name='NT', kind='cell', srcs=['T'], f=NOT1),
    dict(name='TP', kind='cell', srcs=['T', 'NT'], f=lambda x, y: x[0] & x[1]),     # NT is T one step late
    dict(name='NTP', kind='cell', srcs=['TP'], f=NOT1),
    check('check NT', 'NT', lambda a, b: 1 - (a & 1), drive=dict(T=lambda s: PAIRS[s][0] & 1)),
    dict(name='H', kind='row', srcs=[], f=lambda x, y: 1),
    dict(name='ONE', kind='row', srcs=[L('H')], f=NOT1),
    check('check ONE', 'ONE', lambda a, b: 1),
    # part 3: word ops, on PA and PB (the box's A and B while TEST = 1, the machine's ports otherwise)
    dict(name='TESTN', kind='cell', srcs=['TEST'], f=NOT1),
    dict(name='APORT', kind='row', srcs=[], f=lambda x, y: 0),                     # blank until the machine
    dict(name='BPORT', kind='row', srcs=[], f=lambda x, y: 0),                     # places its read ports
    dict(name='PA', kind='row', srcs=['TEST', 'A', 'APORT', 'TESTN'], twin={3: 0}, f=MUX),
    dict(name='PB', kind='row', srcs=['TEST', 'B', 'BPORT', 'TESTN'], twin={3: 0}, f=MUX),
    dict(name='X', kind='row', srcs=['PA', 'PB'], f=XNOR),
    dict(name='CY', kind='row', srcs=['PA', 'PB', L('CY')], f=MAJ),
    dict(name='ADD', kind='row', srcs=['X', L('CY')], f=XNOR),
    check('check ADD', 'ADD', lambda a, b: (a + b) & M),
    dict(name='NA', kind='row', srcs=['PA'], f=NOT1),
    dict(name='XS', kind='row', srcs=['NA', 'PB'], f=XNOR),
    dict(name='CYS', kind='row', srcs=['NA', 'PB', L('CYS')], f=MAJ),
    dict(name='SS', kind='row', srcs=['XS', L('CYS')], f=XNOR),
    dict(name='SUB', kind='row', srcs=['SS'], f=NOT1),
    check('check SUB', 'SUB', lambda a, b: (a - b) & M),
    dict(name='LTU', kind='cell', srcs=[('CYS', W - 1)], f=COPY),
    check('check LTU', 'LTU', lambda a, b: int(a < b)),
    dict(name='NLTU', kind='cell', srcs=['LTU'], f=NOT1),
    dict(name='OR', kind='row', srcs=['PA', L('OR')], f=lambda x, y: x[0] | x[1]),
    dict(name='ZERO', kind='cell', srcs=[('OR', W - 1)], f=NOT1),
    check('check ZERO', 'ZERO', lambda a, b: int(a == 0)),
    dict(name='XN', kind='row', srcs=['NA', 'ONE'], f=XNOR),
    dict(name='CN', kind='row', srcs=['NA', 'ONE', L('CN')], f=MAJ),
    dict(name='NEG', kind='row', srcs=['XN', L('CN')], f=XNOR),
    check('check NEG', 'NEG', lambda a, b: -a & M),
    dict(name='SG', kind='cell', srcs=[('PA', W - 1)], f=COPY),
    dict(name='NSG', kind='cell', srcs=['SG'], f=NOT1),
    dict(name='ABS', kind='row', srcs=['SG', 'NEG', 'PA', 'NSG'], twin={3: 0}, f=MUX),
    check('check ABS', 'ABS', lambda a, b: abs(s16(a)) & M),
]


def debruijn(k):
    """Every ordered pair of k symbols once: k*k + 1 symbols (a de Bruijn sequence)."""
    a, seq = [0] * 3, []
    def db(t, p):
        if t > 2:
            if 2 % p == 0: seq.extend(a[1:p + 1])
        else:
            a[t] = a[t - p]; db(t + 1, p)
            for j in range(a[t - p] + 1, k): a[t] = j; db(t + 1, t)
    db(1, 1)
    return seq + seq[:1]


def samples(t):
    """Search target: (inputs, wanted) per step. An all-0 step, then every pair of patterns of the free sources
    (twins follow), so the rule is told apart from every rule on this step and the step before."""
    n, tw = len(t['srcs']), t.get('twin', {})
    free = [i for i in range(n) if i not in tw]
    xs, ys, y = [], [], 0
    for p in [None] + debruijn(1 << len(free)):
        x = [0] * n
        for j, i in enumerate(free): x[i] = 0 if p is None else p >> j & 1
        for i, j in tw.items(): x[i] = 1 - x[j]
        y = t['f'](x, y)
        xs.append(tuple(x)); ys.append(y)
    return xs, ys
