"""Targets for the program machine, parts D and E (notes/targets-2-datapath.md): states, program store, fetch,
decode, read ports. Only descriptions, no nets. The machine runs one LODA instruction per clock pulse TP (the box
drives T); every part settles within the clock period. cpu_control.py has the rest; cpu_runs.py checks it.

Instruction row (W = 16 lanes): S lanes 0-6 (a register in 0-2, or a constant -64..63), OP 7-11, T 12-14, MD 15.
OP: 0 mov 1 add 2 sub 3 mul 4 div 5 mod 6 min 7 max, 8-21 found ops, 22 lpb 23 lpe 24 seq 31 end.
A state is a hold: srcs (load, data, NOT load), it takes the data on a load pulse. Its load pair and its data are
blanks at first (f = 0) and are placed at the end (kind 'place'), once the parts they read exist: the machine
has loops (a state's data depends on states), and a target can only read what exists.
Source forms: ('X', 'L') the lane to the left; ('X', j) lane j; ('X', 7, 'z', 5) lane k reads lane 7 + k, and
from lane 5 on reads 0 ('s' instead: reads the last lane, a sign extend).
"""
from machine_targets import W, NOT1, COPY, MUX, L

Z = lambda x, y: 0
AND = lambda x, y: x[0] & x[1]
NAND = lambda x, y: 1 - (x[0] & x[1])
OR = lambda x, y: int(any(x))
NOR = lambda x, y: 1 - int(any(x))
AO = lambda x, y: (x[0] & x[1]) | (x[2] & x[3])
HOLD = lambda x, y: x[1] if x[0] else y              # srcs: load, data, NOT load (its twin)
OA = lambda x, y: x[0] | (x[1] & x[2])
GATE = lambda x, y: (x[0] | x[1]) & x[2]
IR = lambda k: ('IR', k)
OPB, TB, SB, MD = (lambda k: IR(7 + k)), (lambda k: IR(12 + k)), (lambda k: IR(k)), IR(15)


def c(name, srcs, f, **k): return dict(name=name, kind='cell', srcs=srcs, f=f, **k)
def r(name, srcs, f, **k): return dict(name=name, kind='row', srcs=srcs, f=f, **k)
def mux(name, s, ns, u, v, kind='row'): return dict(name=name, kind=kind, srcs=[s, u, v, ns], twin={3: 0}, f=MUX)
def hold(name, ld, d, kind='row'): return dict(name=name, kind=kind, srcs=[f'L_{ld}', d, f'NL_{ld}'], twin={2: 0}, f=HOLD)
def bit(s, k, j): return s(k) if j >> k & 1 else f'N{s(k)[0]}{s(k)[1]}'      # bit k of j, or its NOT cell
def tree(name, s, ns, ins):
    """A mux tree: ins[i] selected by the bits s(0), s(1), ...; returns targets, the last one is `name`."""
    out, lvl, k = [], ins, 0
    while len(lvl) > 1:
        nxt = [f'{name}{k}_{i}' if len(lvl) > 2 else name for i in range(len(lvl) // 2)]
        out += [mux(n, s(k), ns(k), lvl[2 * i + 1], lvl[2 * i]) for i, n in enumerate(nxt)]
        lvl, k = nxt, k + 1
    return out


LOADS = [f'R{j}' for j in range(8)] + ['CLK', 'PID', 'LD', 'RUN', 'HALT', 'BAD', 'RV', 'LF0', 'LF1', 'LP0',
                                       'LP1', 'CF0', 'CF1', 'CF2']
DATA_ROWS = [f'D_R{j}' for j in range(8)] + ['D_PC', 'D_PID']
DATA_CELLS = ['D_RETD'] + [f'D_CD{k}' for k in range(4)] + [f'D_LD{k}' for k in range(3)]
nots = lambda name, s, n: [c(f'N{s(k)[0]}{s(k)[1]}', [s(k)], NOT1) for k in range(n)]

TARGETS_D = [
    c('NGO', ['GO'], NOT1),
    r('TWO', [L('ONE')], COPY),
    # blanks, placed at the end (cpu_control.py)
] + [c(f'{p}_{g}', [], Z) for g in LOADS for p in ('L', 'NL')] + [r(n, [], Z) for n in DATA_ROWS] + [
    c(n, [], Z) for n in DATA_CELLS] + [
    # states
] + [hold(f'REG{j}', f'R{j}', f'D_R{j}') for j in range(8)] + [
    hold('PC', 'CLK', 'D_PC'),
    r('CP', [L('CP'), L('PC'), 'ONE'], lambda x, y: (x[0] & x[1]) | x[2]),   # carry into each lane of PC + 1
    r('NCP', ['CP'], NOT1),
    r('PCN', ['PC', 'NCP'], lambda x, y: 1 - (x[0] ^ x[1])),     # PC + 1 = PC XOR CP
    hold('PID', 'PID', 'D_PID'),
    r('NPID', ['PID'], NOT1),                                     # must follow PID (the store reads both)
    hold('RETD', 'CLK', 'D_RETD', 'cell'),
    hold('RUNS', 'RUN', 'GO', 'cell'), hold('HALTED', 'HALT', 'NGO', 'cell'), hold('BADF', 'BAD', 'NGO', 'cell'),
] + [hold(f'CD{k}', 'PID', f'D_CD{k}', 'cell') for k in range(4)] + [
    hold(f'LD{k}', 'LD', f'D_LD{k}', 'cell') for k in range(3)] + [
    hold(f'LOLD{l}', f'LF{l}', 'APORT') for l in range(2)] + [
    hold(f'LFR{l}_{j}', f'LF{l}', f'REG{j}') for l in range(2) for j in range(8)] + [
    hold(f'LPC{l}', f'LP{l}', 'PCN') for l in range(2)] + [
    hold(f'FR{f}_{j}', f'CF{f}', f'REG{j}') for f in range(3) for j in range(8)] + [
    hold(f'FPC{f}', f'CF{f}', 'PC') for f in range(3)] + [hold(f'FPID{f}', f'CF{f}', 'PID') for f in range(3)] + [
    hold('RV', 'RV', 'REG0'),
    # program store WORK: 32 slots, written by the box (TEST = 1) or later by the searcher (blank EDS, EDA, EWW)
    r('EDS', [], Z), c('EWW', [], Z),
] + [c(f'EDA{k}', [], Z) for k in range(5)] + [
    mux('EDROW', 'TEST', 'TESTN', 'A', 'EDS'),
    mux('WWR', 'TEST', 'TESTN', 'TP', 'EWW', 'cell'),
] + [mux(f'WA{k}', 'TEST', 'TESTN', ('B', k), f'EDA{k}', 'cell') for k in range(5)] + [
    c(f'NWA{k}', [f'WA{k}'], NOT1) for k in range(5)] + [
    c(f'LO{q}', [f'WA0' if q & 1 else 'NWA0', f'WA1' if q & 2 else 'NWA1'], AND) for q in range(4)] + [
    c(f'MQ{q}', [f'WA2' if q & 1 else 'NWA2', f'WA3' if q & 2 else 'NWA3'], AND) for q in range(4)] + [
    c(f'HQ{h}', [f'MQ{h & 3}', 'WA4' if h & 4 else 'NWA4'], AND) for h in range(8)] + [
    c(f'HW{h}', [f'HQ{h}', 'WWR'], AND) for h in range(8)] + [
    c(f'{p}WS{s}', [f'LO{s & 3}', f'HW{s >> 2}'], f) for s in range(32) for p, f in (('', AND), ('N', NAND))] + [
    dict(hold(f'SLOT{s}', 'X', 'EDROW'), srcs=[f'WS{s}', 'EDROW', f'NWS{s}']) for s in range(32)] + [
    r('POR', [('PID', 0, 'z', 11), L('POR')], OR),               # lane W-1: any of PID's lanes 0..10 is 1
    c('MATCH0', [('POR', W - 1)], NOT1),                          # PID = 0: run WORK
] + [r(f'BUS{s}', ['MATCH0', f'SLOT{s}'], AND) for s in range(32)] + [   # the store adds library programs here
    c(f'NPC{k}', [('PC', k)], NOT1) for k in range(5)] + tree('IR', lambda k: ('PC', k), lambda k: f'NPC{k}',
                                                              [f'BUS{s}' for s in range(32)]) + [
    # decode
] + nots('OP', OPB, 5) + nots('T', TB, 3) + nots('S', SB, 3) + [c('NIR15', [MD], NOT1)]
