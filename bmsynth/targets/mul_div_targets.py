"""Targets for part C (notes/targets-1-seed-and-ops.md): signed MUL, DIV, MOD on A, B. Only descriptions, no nets.

New kind here, 'copy': the maker copies the block, every cell from the target `block` up to the newest, `n` times
upward. A read that points into the block's own length below it moves up with each copy, so a block reading the
rows just below it (here BS0, ACC0) reads the copy before it. The carried rows (BS, ACC) are made last in the
block, in the same order as the start rows just below it. After the copy a block name means its top copy.
Ops read PA and PB (part B). MIN and MAX are signed, as in LODA, so they come here after the sign cells.
DIV and MOD are checked only where B != 0 (LODA treats division by 0 as a failed run).
"""
from machine_targets import W, M, NOT1, COPY, XNOR, MAJ, MUX, L, s16, PAIRS, check

ZERO1 = lambda x, y: 0
OR_AND = lambda x, y: x[0] | (x[1] & x[2])                     # x0 OR (x1 AND x2)
SETTLE = 4 * W * W + 12                                         # ticks a check holds each sample (copies ripple)
NZ = [p for p in PAIRS if p[1]]
ab = lambda ps: dict(A=lambda s: ps[s][0], B=lambda s: ps[s][1])
chk = lambda name, out, want, ps=PAIRS: dict(check(name, out, want, ab(ps)), n=len(ps), hold=SETTLE,
                                             want=lambda s: want(*ps[s]) & M)
uabs = lambda w: abs(s16(w))
tdiv = lambda a, b: int(abs(a) // abs(b)) * (1 if (a < 0) == (b < 0) else -1)   # LODA: toward 0


def negate(p, src):
    """-src as rows: N = NOT src, XN, CN (a carry chain), NEG. p = name prefix."""
    return [dict(name=f'N{p}', kind='row', srcs=[src], f=NOT1),
            dict(name=f'XN{p}', kind='row', srcs=[f'N{p}', 'ONE'], f=XNOR),
            dict(name=f'CN{p}', kind='row', srcs=[f'N{p}', 'ONE', L(f'CN{p}')], f=MAJ),
            dict(name=f'NEG{p}', kind='row', srcs=[f'XN{p}', L(f'CN{p}')], f=XNOR)]


TARGETS_C = negate('B', 'PB') + [
    # C1: |B| and B = 0
    dict(name='SGB', kind='cell', srcs=[('PB', W - 1)], f=COPY),
    dict(name='NSGB', kind='cell', srcs=['SGB'], f=NOT1),
    dict(name='ABSB', kind='row', srcs=['SGB', 'NEGB', 'PB', 'NSGB'], twin={3: 0}, f=MUX),
    chk('check ABSB', 'ABSB', lambda a, b: uabs(b)),
    dict(name='ORB', kind='row', srcs=['PB', L('ORB')], f=lambda x, y: x[0] | x[1]),
    dict(name='ZB', kind='cell', srcs=[('ORB', W - 1)], f=NOT1),
    chk('check ZB', 'ZB', lambda a, b: int(b == 0)),
    # C2: |A| x |B|, most significant bit first: one step block, then W-1 copies
    dict(name='BS0', kind='row', srcs=['ABSB'], f=COPY),
    dict(name='ACC0', kind='row', srcs=[], f=ZERO1),
    dict(name='BB', kind='cell', srcs=[('BS0', W - 1)], f=COPY),
    dict(name='ACCSH', kind='row', srcs=[L('ACC0')], f=COPY),
    dict(name='PP', kind='row', srcs=['ABS', 'BB'], f=lambda x, y: x[0] & x[1]),
    dict(name='MX', kind='row', srcs=['ACCSH', 'PP'], f=XNOR),
    dict(name='MC', kind='row', srcs=['ACCSH', 'PP', L('MC')], f=MAJ),
    dict(name='BS', kind='row', srcs=[L('BS0')], f=COPY),
    dict(name='ACC', kind='row', srcs=['MX', L('MC')], f=XNOR),
    dict(name='MULU copy', kind='copy', block='BB', n=W - 1),
    chk('check MULU', 'ACC', lambda a, b: uabs(a) * uabs(b)),
    # C3: the sign of the product
    dict(name='SGX', kind='cell', srcs=['SG', 'NSGB'], f=XNOR),
    dict(name='NSGX', kind='cell', srcs=['SGX'], f=NOT1),
    dict(name='LTS', kind='cell', srcs=['SGX', 'SG', 'LTU', 'NSGX'], twin={3: 0}, f=MUX),   # PA < PB, signed
    dict(name='NLTS', kind='cell', srcs=['LTS'], f=NOT1),
    dict(name='MIN', kind='row', srcs=['LTS', 'PA', 'PB', 'NLTS'], twin={3: 0}, f=MUX),
    chk('check MIN', 'MIN', lambda a, b: min(s16(a), s16(b))),
    dict(name='MAX', kind='row', srcs=['LTS', 'PB', 'PA', 'NLTS'], twin={3: 0}, f=MUX),
    chk('check MAX', 'MAX', lambda a, b: max(s16(a), s16(b))),
] + negate('P', 'ACC') + [
    dict(name='MUL', kind='row', srcs=['SGX', 'NEGP', 'ACC', 'NSGX'], twin={3: 0}, f=MUX),
    chk('check MUL', 'MUL', lambda a, b: s16(a) * s16(b)),
    # C4: |A| / |B|, restoring division: one step block, then W-1 copies
    dict(name='AS0', kind='row', srcs=['ABS'], f=COPY),
    dict(name='R0', kind='row', srcs=[], f=ZERO1),
    dict(name='Q0', kind='row', srcs=[], f=ZERO1),
    dict(name='ABIT', kind='cell', srcs=[('AS0', W - 1)], f=COPY),
    dict(name='RS', kind='row', srcs=[L('R0'), 'ABIT', 'ONE'], f=OR_AND),
    dict(name='NRS', kind='row', srcs=['RS'], f=NOT1),
    dict(name='DX', kind='row', srcs=['NRS', 'ABSB'], f=XNOR),
    dict(name='DC', kind='row', srcs=['NRS', 'ABSB', L('DC')], f=MAJ),
    dict(name='DS', kind='row', srcs=['DX', L('DC')], f=XNOR),
    dict(name='DT', kind='row', srcs=['DS'], f=NOT1),
    dict(name='FIT', kind='cell', srcs=[('DC', W - 1)], f=NOT1),
    dict(name='NFIT', kind='cell', srcs=['FIT'], f=NOT1),
    dict(name='AS', kind='row', srcs=[L('AS0')], f=COPY),
    dict(name='R', kind='row', srcs=['FIT', 'DT', 'RS', 'NFIT'], twin={3: 0}, f=MUX),
    dict(name='Q', kind='row', srcs=[L('Q0'), 'FIT', 'ONE'], f=OR_AND),
    dict(name='DIVU copy', kind='copy', block='ABIT', n=W - 1),
    chk('check DIVU', 'Q', lambda a, b: uabs(a) // uabs(b), NZ),
    # C5: signs, truncating toward 0 as LODA does; the remainder takes the dividend's sign
] + negate('Q', 'Q') + [
    dict(name='DIV', kind='row', srcs=['SGX', 'NEGQ', 'Q', 'NSGX'], twin={3: 0}, f=MUX),
    chk('check DIV', 'DIV', lambda a, b: tdiv(s16(a), s16(b)), NZ),
] + negate('R', 'R') + [
    dict(name='MOD', kind='row', srcs=['SG', 'NEGR', 'R', 'NSG'], twin={3: 0}, f=MUX),
    chk('check MOD', 'MOD', lambda a, b: s16(a) - s16(b) * tdiv(s16(a), s16(b)), NZ),
]
