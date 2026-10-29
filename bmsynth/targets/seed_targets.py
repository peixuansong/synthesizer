"""Targets for the seed (generation 1 of notes/growth-plan.md), described only by samples (no nets).

They are the parts the searchers themselves are made of, each a rule y' = f(x, y) on up to 3 input bits
(x = the inputs this step, y = the output of the step before, 0 at the start). The seed searches them in
this order. Adding a target = appending it here.

Some parts come with a twin, a cell that is always the NOT of another. Such a target gets the twin as an input:
twin = {input index: ('x', i)} means that input is NOT input i.
"""

TARGETS = [
    dict(name='delay', used_as='ring cell, source, decide', f=lambda x, y: x[0]),
    dict(name='delay x1', used_as='the same, on input x1', f=lambda x, y: x[1]),
    dict(name='delay x2', used_as='the same, on input x2', f=lambda x, y: x[2]),
    dict(name='not', used_as='neq, ndec', f=lambda x, y: 1 - x[0]),
    dict(name='or2', used_as='OR of two signals', f=lambda x, y: x[0] | x[1]),
    dict(name='nor2', used_as='passed = NOR(ndec, W)', f=lambda x, y: 1 - (x[0] | x[1])),
    dict(name='or3', used_as='input lines, strobe', f=lambda x, y: x[0] | x[1] | x[2]),
    dict(name='and2', used_as='source pair, counter carry', f=lambda x, y: x[0] & x[1]),
    dict(name='nand2', used_as='NOT of a pair', f=lambda x, y: 1 - (x[0] & x[1])),
    dict(name='latch', used_as='found / not-found cells: set by x0, kept while x1', f=lambda x, y: x[0] | (x[1] & y)),
    dict(name='mismatch latch', used_as='W: kept by x0, set by x1 AND x2',
         f=lambda x, y: (y & x[0]) | (x[1] & x[2])),
    dict(name='hold', used_as='store bit: takes x0 when x1 is 1', twin={2: ('x', 1)},
         f=lambda x, y: (x[1] & x[0]) | (x[2] & y)),
    dict(name='majority', used_as='adder carry (generation 2)', f=lambda x, y: (x[0] & x[1]) | (x[0] & x[2]) | (x[1] & x[2])),
    dict(name='carry', used_as='serial add carry: majority of x0, x1 and itself', f=lambda x, y: (x[0] & x[1]) | (x[0] & y) | (x[1] & y)),
    dict(name='xnor2', used_as='compare: eq = out XNOR target', f=lambda x, y: 1 - (x[0] ^ x[1])),
    # generation 2: one new cell over the running copies of the finds above
    dict(name='xor2', used_as='odd number of x0, x1', f=lambda x, y: x[0] ^ x[1]),
    dict(name='xor3', used_as='serial add sum bit (without carry)', f=lambda x, y: x[0] ^ x[1] ^ x[2]),
    dict(name='toggle', used_as='counter bit: flips when x0 is 1', twin={2: ('x', 0)}, f=lambda x, y: y ^ x[0]),
]


def debruijn(k=8):
    """Every ordered pair of k symbols once, as one sequence of k*k + 1 symbols (a de Bruijn sequence)."""
    a, seq = [0] * 4, []
    def db(t, p):
        if t > 2:
            if 2 % p == 0: seq.extend(a[1:p + 1])
        else:
            a[t] = a[t - p]; db(t + 1, p)
            for j in range(a[t - p] + 1, k): a[t] = j; db(t + 1, t)
    db(1, 1)
    return seq + seq[:1]


def samples(t):
    """(input bits, expected output) per step: an all-0 step, then the 8 input patterns in an order where every
    pattern follows every pattern once (66 steps), so a rule that looks at this step and the step before is
    told apart from every other such rule. Twin inputs are set from what they are the NOT of."""
    raw = [(0, 0, 0)] + [tuple(p >> i & 1 for i in range(3)) for p in debruijn()]
    xs, ys, y = [], [], 0
    for r in raw:
        x = list(r)
        for i, src in t.get('twin', {}).items():
            x[i] = 1 - x[src[1]]
        y = t['f'](x, y)
        xs.append(tuple(x)); ys.append(y)
    return xs, ys
