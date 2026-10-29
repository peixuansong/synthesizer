"""Targets for the program machine, parts D to H (notes/targets-2-datapath.md, targets-3-control.md): decode, read
ports, ALU result, the clocked control (loops with LODA's rule, calls, the runner), each state's load pair and
data, and the places that wire the blanks of cpu_targets.py. Only descriptions, no nets.
Levels: TP is a one-tick pulse; every load pulse X comes with its twin NX computed from the same inputs, so they
change on the same tick. Data is taken from settled signals (conditions), never from pulses.
"""
from machine_targets import W, NOT1, COPY, XNOR, MAJ, L
from cpu_targets import AND, NAND, OR, NOR, AO, OA, GATE, OPB, TB, SB, MD, c, r, mux, bit, tree, LOADS

NI = lambda k: f'NIR{k}'                                      # the NOT cell of IR lane k
place = lambda dst, src: dict(name=f'place {dst}', kind='place', dst=dst, src=src)
pair = lambda n, a, b, f, nf: [c(n, [a, b], f), c('N' + n, [a, b], nf)]       # a load pulse and its twin

TARGETS_E = [
    # decode
    c('HW', [NI(10), NI(11)], AND),                           # OP < 8: built in
    c('U10', [OPB(4), NI(10)], AND), c('U11', [OPB(4), OPB(3)], AND),
    c('O21', [OPB(2), OPB(1)], AND), c('Z21', [NI(9), NI(8)], AND),
    c('LPX', ['U10', 'O21'], AND), c('LPB', ['LPX', NI(7)], AND), c('LPE', ['LPX', OPB(0)], AND),
    c('Z210', ['Z21', NI(7)], AND), c('SEQ', ['U11', 'Z210'], AND),
    c('O210', ['O21', OPB(0)], AND), c('END', ['U11', 'O210'], AND),
    c('OPHI', ['U11', 'LPX'], OR), c('FOUND', ['HW', 'OPHI'], NOR), c('NFOUND', ['FOUND'], NOT1),
    c('CALLOP', ['SEQ', 'FOUND'], OR), c('NCALLOP', ['CALLOP'], NOT1),
    c('DM', [OPB(2), NI(8)], AND), c('DIVOP', ['HW', 'DM'], AND),
] + [c(f'TM{q}', [bit(TB, 0, q), bit(TB, 1, q)], AND) for q in range(4)] + [
    c(f'TT{j}', [f'TM{j & 3}', bit(TB, 2, j)], AND) for j in range(8)] + [
    # read ports, then the blanks APORT and BPORT of part B are placed: the word ops now read registers
] + tree('AP', TB, lambda k: NI(12 + k), [f'REG{j}' for j in range(8)]) + tree(
    'BR', SB, lambda k: NI(k), [f'REG{j}' for j in range(8)]) + [
    mux('BP', MD, NI(15), ('IR', 0, 's', 7), 'BR'),
    place('APORT', 'AP'), place('BPORT', 'BP'),
    # ALU result; a call's result (RV) after it returns
] + tree('RESA', OPB, lambda k: NI(7 + k), ['PB', 'ADD', 'SUB', 'MUL', 'DIV', 'MOD', 'MIN', 'MAX']) + [
    mux('RES', 'CALLOP', 'NCALLOP', 'RV', 'RESA'),
    r('FB', ['PB', 'FOUND'], AND),                            # a found op's second input
    mux('CPID', 'FOUND', 'NFOUND', ('IR', 7, 'z', 5), ('IR', 0, 's', 7)),   # the program a call runs
    # clocked control
    c('TPX', ['TP', 'RUNS'], AND), c('INIT', ['GO', 'TP'], AND),
    c('WALUC', ['HW', 'CALLOP', 'RETD'], OA), c('WG', ['WALUC', 'TPX'], AND),
] + [c(f'WSEL{j}', [f'TT{j}', 'WALUC'], AND) for j in range(8)] + [
    c(f'WT{j}', [f'TT{j}', 'WG'], AND) for j in range(8)] + [
    c('NRETD', ['RETD'], NOT1), c('CALLC', ['CALLOP', 'NRETD'], AND), c('CALLP', ['CALLC', 'TPX'], AND),
    c('NCD0', ['CD0'], NOT1), c('EN0', ['END', 'NCD0'], AND),
    *pair('RETP', 'EN0', 'TPX', AND, NAND),
    c('EH', ['END', 'CD0'], AND), c('HALTP', ['EH', 'TPX'], AND),
    # loops: lpe's T names the counter, so APORT is its new value
    c('NLD2', ['LD2'], NOT1), mux('LOLDT', 'LD2', 'NLD2', 'LOLD1', 'LOLD0'),
    r('NAP', ['APORT'], NOT1), r('CXC', ['NAP', 'LOLDT', L('CXC')], MAJ), c('CLT', [('CXC', W - 1)], COPY),
    c('SA', [('APORT', W - 1)], COPY), c('NSA', ['SA'], NOT1), c('SO', [('LOLDT', W - 1)], COPY),
    c('NSO', ['SO'], NOT1), c('SXL', ['SA', 'NSO'], XNOR), c('NSXL', ['SXL'], NOT1),
    mux('LTL', 'SXL', 'NSXL', 'SA', 'CLT', 'cell'), c('CONT', ['LTL', 'NSA'], AND), c('NCONT', ['CONT'], NOT1),
    c('LPC2', ['LPE', 'CONT'], AND), c('LPN2', ['LPE', 'NCONT'], AND),
    c('PUSHP', ['LPB', 'TPX'], AND), c('AGAINP', ['LPC2', 'TPX'], AND), c('POPP', ['LPN2', 'TPX'], AND),
    mux('LPCT', 'LD2', 'NLD2', 'LPC1', 'LPC0'),
] + [mux(f'LFRT{j}', 'LD2', 'NLD2', f'LFR1_{j}', f'LFR0_{j}') for j in range(8)] + [
    *pair('PL0', 'PUSHP', 'LD0', AND, NAND), *pair('PL1', 'PUSHP', 'LD1', AND, NAND),
    c('AL0', ['AGAINP', 'LD1'], AND), c('AL1', ['AGAINP', 'LD2'], AND),
    *pair('LFL0', 'PL0', 'AL0', OR, NOR), *pair('LFL1', 'PL1', 'AL1', OR, NOR),
    # failures: loop or call too deep, division by 0
    c('LOVF', ['LD2', 'PUSHP'], AND), c('COVF', ['CD3', 'CALLP'], AND),
    c('DZ', ['DIVOP', 'ZB'], AND), c('DIVZP', ['DZ', 'TPX'], AND),
    c('BADP', ['LOVF', 'COVF', 'DIVZP'], OR), c('HB', ['HALTP', 'BADP'], OR),
    # load pairs
    c('EV1', ['POPP', 'CALLP'], OR), c('EV2', ['RETP', 'INIT'], OR), c('EVA', ['EV1', 'EV2'], OR),
] + [x for j in range(8) for x in pair(f'LR{j}', f'WT{j}', 'EVA', OR, NOR)] + [
    *pair('LCLK', 'TPX', 'INIT', OR, NOR),
    c('EV3', ['CALLP', 'RETP'], OR), *pair('LPIDS', 'EV3', 'INIT', OR, NOR),
    c('LEV', ['PUSHP', 'POPP'], OR), *pair('LLDS', 'LEV', 'INIT', OR, NOR),
    *pair('LRUNS', 'INIT', 'HB', OR, NOR), *pair('LHALTS', 'INIT', 'HALTP', OR, NOR),
    *pair('LBADS', 'INIT', 'BADP', OR, NOR),
] + [x for f in range(3) for x in pair(f'CFL{f}', 'CALLP', f'CD{f}', AND, NAND)] + [
    # data: the top call frame, registers, PC, PID, flags
] + [x for n in [f'{j}' for j in range(8)] + ['PC', 'PID'] for x in (
    r(f'FT1{n}', ['CD1', f'FR0_{n}' if n.isdigit() else f'F{n}0', 'CD2', f'FR1_{n}' if n.isdigit() else f'F{n}1'], AO),
    r(f'FRT{n}', [f'FT1{n}', 'CD3', f'FR2_{n}' if n.isdigit() else f'F{n}2'], OA))] + [
    r(f'DA{j}', [f'WSEL{j}', 'RES', 'LPN2', f'LFRT{j}'], AO) for j in range(8)] + [
    r('DB0', ['CALLC', 'APORT', 'EN0', 'FRT0'], AO), r('DB1', ['CALLC', 'FB', 'EN0', 'FRT1'], AO)] + [
    r(f'DB{j}', ['EN0', f'FRT{j}'], AND) for j in range(2, 8)] + [
    r(f'DR{j}', [f'DA{j}', f'DB{j}', 'NGO'], GATE) for j in range(8)] + [
    r('DIN0', ['DR0', 'GO', 'A'], OA),                        # INIT: $0 = n (the box drives A)
    c('JR', ['LPC2', 'EN0'], OR), c('NORMC', ['JR', 'CALLC'], NOR),
    r('PD1', ['LPC2', 'LPCT', 'EN0', 'FRTPC'], AO), r('PD2', ['NORMC', 'PCN'], AND),
    r('DPCR', ['PD1', 'PD2', 'NGO'], GATE),                   # a call (and INIT) starts at PC 0
    r('PID1', ['CALLC', 'CPID', 'EN0', 'FRTPID'], AO), r('DPIDR', ['PID1', 'NGO'], AND),
    c('DRETD', ['EN0', 'NGO'], AND),
    c('DC0', ['GO', 'CD1', 'EN0'], OA), c('DC1A', ['CD0', 'CALLC', 'CD2', 'EN0'], AO), c('DC1', ['DC1A', 'NGO'], AND),
    c('DC2A', ['CD1', 'CALLC', 'CD3', 'EN0'], AO), c('DC2', ['DC2A', 'NGO'], AND),
    c('DC3A', ['CD2', 'CALLC'], AND), c('DC3', ['DC3A', 'NGO'], AND),
    c('DL0', ['GO', 'LD1', 'LPN2'], OA), c('DL1A', ['LD0', 'LPB', 'LD2', 'LPN2'], AO), c('DL1', ['DL1A', 'NGO'], AND),
    c('DL2A', ['LD1', 'LPB'], AND), c('DL2', ['DL2A', 'NGO'], AND),
    r('STAT', ['ONE', 'HALTED', 'TWO', 'BADF'], AO),          # lane 0: halted, lane 1: failed (the box reads it)
]
SRC = dict(zip(LOADS, [(f'LR{j}', f'NLR{j}') for j in range(8)] + [
    ('LCLK', 'NLCLK'), ('LPIDS', 'NLPIDS'), ('LLDS', 'NLLDS'), ('LRUNS', 'NLRUNS'), ('LHALTS', 'NLHALTS'),
    ('LBADS', 'NLBADS'), ('RETP', 'NRETP'), ('LFL0', 'NLFL0'), ('LFL1', 'NLFL1'), ('PL0', 'NPL0'), ('PL1', 'NPL1'),
    ('CFL0', 'NCFL0'), ('CFL1', 'NCFL1'), ('CFL2', 'NCFL2')]))
TARGETS_E += [place(f'{p}_{g}', s) for g, (a, b) in SRC.items() for p, s in (('L', a), ('NL', b))] + [
    place('D_R0', 'DIN0')] + [place(f'D_R{j}', f'DR{j}') for j in range(1, 8)] + [
    place('D_PC', 'DPCR'), place('D_PID', 'DPIDR'), place('D_RETD', 'DRETD')] + [
    place(f'D_CD{k}', f'DC{k}') for k in range(4)] + [place(f'D_LD{k}', f'DL{k}') for k in range(3)]
