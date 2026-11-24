"""The target list (plan: targets ladder), in order. Each target is a black box (targets/blocks.py) plus the
earlier targets it is built from (targets/rules.md: when its dependencies exist in the net, it is reachable).

    TARGETS     [(name, n_in, n_out, make, deps)]; an OEIS target has make = None (the sequence box plays it)
    missing()   dependencies that no target defines (those targets can't be reached yet)

Rungs: 1 gates, 2 memory, 3 adders, 4 serial, 5 easy OEIS streams, 6 words (LODA's ops), 7 the other OEIS
entries, ordered by LODA program length (no program: last).
"""
import csv, os
import oeis
from blocks import gate, stateful, word, register, counter, OPS

G = {0: 'ZERO', 1: 'NOR', 2: 'B_AND_NOT_A', 3: 'NOT_A', 4: 'A_AND_NOT_B', 5: 'NOT_B', 6: 'XOR', 7: 'NAND',
     8: 'AND', 9: 'XNOR', 10: 'B', 11: 'A_IMPLIES_B', 12: 'A', 13: 'B_IMPLIES_A', 14: 'OR', 15: 'ONE'}
GATES = [(G[k], 2, 1, gate(k), []) for k in range(16)]


def _keep(v): return v, (v,)
def _inc(c, x, s): c = 1 if s else c; return x & c, (x ^ c,)
def _add(c, a, b, s): c = 0 if s else c; return (a & b) | (c & (a ^ b)), (a ^ b ^ c,)
def _sub(c, a, b, s): c = 1 if s else c; nb = 1 - b; return (a & nb) | (c & (a ^ nb)), (a ^ nb ^ c,)


MEMORY = [
    ('DELAY', 1, 1, stateful(lambda s, x: (x, (s,)), 0), []),
    ('TOGGLE', 1, 1, stateful(lambda s, t: _keep(s ^ t), 0), ['XOR']),
    ('LATCH', 2, 1, stateful(lambda s, st, r: _keep((s | st) & (1 - r)), 0), ['OR', 'AND', 'NOT_B']),
]
ADDERS = [
    ('HALF_ADD', 2, 2, lambda: (lambda a, b: (a ^ b, a & b)), ['XOR', 'AND']),
    ('FULL_ADD', 3, 2, lambda: (lambda a, b, c: (a ^ b ^ c, (a & b) | (c & (a ^ b)))), ['HALF_ADD', 'OR']),
]
SERIAL = [
    ('SERIAL_INC', 2, 1, stateful(_inc, 0), ['HALF_ADD', 'LATCH']),
    ('SERIAL_ADD', 3, 1, stateful(_add, 0), ['FULL_ADD', 'LATCH']),
    ('SERIAL_SUB', 3, 1, stateful(_sub, 0), ['FULL_ADD', 'LATCH', 'NOT_A']),
]
EASY = [('A000004', []), ('A000012', []), ('A001477', []), ('A000027', []), ('A000035', ['AND']),
        ('A005843', ['DELAY']), ('A005408', ['A005843', 'OR']), ('A000007', ['LATCH', 'NOR'])]

WORD_DEPS = {
    'ADD': ['SERIAL_ADD'], 'SUB': ['SERIAL_SUB'], 'MIN': ['SUB', 'REGISTER'], 'MAX': ['SUB', 'REGISTER'],
    'MUL': ['ADD', 'REGISTER', 'COUNTER'], 'DIV': ['SUB', 'REGISTER', 'COUNTER'], 'MOD': ['DIV', 'SUB', 'MUL'],
    'POW': ['MUL', 'COUNTER'], 'FAC': ['MUL', 'COUNTER'], 'BIN': ['MUL', 'DIV', 'FAC'], 'GCD': ['MOD', 'REGISTER'],
    'SQRT': ['MUL', 'SUB', 'COUNTER'], 'NRT': ['POW', 'SUB', 'COUNTER'], 'EQU': ['XOR', 'LATCH'], 'NEQ': ['EQU'],
}
WORDS = ([('REGISTER', 3, 2, register(), ['LATCH']), ('COUNTER', 1, 2, counter(), ['SERIAL_INC', 'REGISTER'])]
         + [(op, arity + 1, 2, word(fn, arity), WORD_DEPS[op]) for op, (fn, arity) in OPS.items()])

LODA = {'pow': 'POW', 'bin': 'BIN', 'gcd': 'GCD', 'fac': 'FAC', 'nrt': 'NRT', 'equ': 'EQU', 'neq': 'NEQ'}
BASIC = ['ADD', 'SUB', 'MUL', 'DIV', 'MOD', 'MIN', 'MAX']


def oeis_targets():
    """The top-2000 entries: the easy ones, then by LODA program length; deps from the program's ops."""
    have = {f"A{d['n']:06d}" for d in oeis.oeis_targets(R=1, W=1 << 10)}
    rows = list(csv.DictReader(open(os.path.join(oeis._setup.DATA, 'oeis', 'loda-top2000.csv'))))
    rows.sort(key=lambda r: (r['has_program'] != 'yes', int(r['length'] or 0), int(r['rank'])))
    out = [(a, 3, 2, None, deps) for a, deps in EASY]
    for r in rows:
        a = r['anumber']
        if a not in have or a in dict(EASY): continue
        if r['has_program'] != 'yes': deps = ['NO_PROGRAM']
        else:
            deps = BASIC + [LODA.get(o, 'OP_' + o.upper()) for o in r['ops_outside_basic'].split()]
            deps += ['LOOP'] * (r['loop'] == '1') + ['CALLED_SEQUENCES'] * (r['calls'] not in ('', '0'))
        out.append((a, 3, 2, None, deps))
    return out


TARGETS = GATES + MEMORY + ADDERS + SERIAL + WORDS + oeis_targets()


def missing():
    names = {t[0] for t in TARGETS}
    count = {}
    for t in TARGETS:
        for d in t[4]:
            if d not in names: count[d] = count.get(d, 0) + 1
    return count
