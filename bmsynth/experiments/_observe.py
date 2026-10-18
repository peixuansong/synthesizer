"""Observation only: reading what a run left in its ports, after the run. Nothing here is called by a net.

Reading the port formats the experiments built (the library word layout and the slot paste-port layout) is done
here, by the experiment; anything that needs a box's own knowledge (which circuit a cell-library entry is, what a
word wiring outputs) is asked of the box the only allowed way: by placing it in a small observation net and running it.
"""
import _setup, _build
from net import ONE, ZERO
from lanes import LaneBoxNet as Net

OPS = ['ADD', 'SUB', 'MUL', 'DIV', 'MOD', 'MIN', 'MAX']      # word op numbers in the library word layout
CELL, WORD, NOP = 1, 2, 7


def kind(v): return int(v) & 3


def cell_entry(v):
    """A cell-library word: (inputs, group, rest) - rest identifies the circuit, only celleval knows how."""
    v = int(v); return (v >> 2) & 3, (v >> 4) & 15, v >> 8


def word_nodes(v):
    """A wiring word (answer or global library): its nodes (op, a, b, start); op >= 7 is unit op - 7 (lane op - 7's answer).
    Layout: bits 0-1 kind, 2-5 node count, then 21 bits per node: op (12), a (4), b (4), start (1)."""
    v = int(v); out = []
    for j in range((v >> 2) & 15):
        f = v >> (6 + 21 * j)
        out.append((f & 4095, (f >> 12) & 15, (f >> 16) & 15, (f >> 20) & 1))
    return out


def opname(op, unit=None): return OPS[op] if op < NOP else (unit(op - NOP) if unit else f'U{op - NOP}')


def describe_wiring(nodes, unit=None):
    """unit(u) -> a name for unit u (e.g. its target's A-number)."""
    nm = lambda s: str(s) if s < 2 else 'xyzwvutsrqp'[s - 2]
    return '; '.join(f"{'xyzwvutsrqp'[j]}' = {opname(op, unit)}" + (f"({nm(a)}, {nm(b)}) [start {i}]" if op < NOP else '')
                     for j, (op, a, b, i) in enumerate(nodes)) + f"; out = {'xyzwvutsrqp'[len(nodes) - 1]}"


def describe_library(words, uids, counts, unit=None):
    """The global library: per slot holding a unit, its name, use count and wiring."""
    out = {}
    for k, (v, u, c) in enumerate(zip(words, uids, counts)):
        if kind(v) == WORD and u: out[f'G{k}'] = f'{unit(u - 1) if unit else u - 1} (used {c}x): ' + describe_wiring(word_nodes(v), unit)
    return out


# ------------------------------------------------------------------ cell circuits, via DICT in an observation net
def slot_circuit(cfg, n_inputs):
    """A slot paste-port value (layout _build.SLOT) as a plain circuit: (m, [(z, [(a, b), ...]) per cell]),
    sources 0, 1, 2.. inputs, 2+n_inputs.. cells; only the cells the output depends on."""
    M, P, NI, SB, CB = _build.SLOT['M'], _build.SLOT['P'], _build.SLOT['NI'], _build.SLOT_SB, _build.SLOT_CB
    cells = []
    for j in range(M):
        f = int(cfg) >> (CB * j)
        pairs = [((f >> (1 + 2 * SB * k)) & ((1 << SB) - 1), (f >> (1 + 2 * SB * k + SB)) & ((1 << SB) - 1)) for k in range(P)]
        cells.append((f & 1, [p for p in pairs if 0 not in p]))
    used, need = {M - 1}, [M - 1]
    while need:
        for a, b in cells[need.pop()][1]:
            for s in (a, b):
                if s >= 2 + NI and s - 2 - NI not in used: used.add(s - 2 - NI); need.append(s - 2 - NI)
    keep = sorted(used); pos = {c: i for i, c in enumerate(keep)}
    src = lambda s: s if s < 2 + NI else 2 + n_inputs + pos[s - 2 - NI]
    return len(keep), [(cells[c][0], [(src(a), src(b)) for a, b in cells[c][1]]) for c in keep]


def cell_circuits(words, stages):
    """{library slot: (inputs, group, (m, cells))} for every cell entry: DICT pastes each into a paste port of an
    observation net; the paste ports are then read back."""
    ents = [(k, cell_entry(v)) for k, v in enumerate(words) if kind(v) == CELL]
    if not ents: return {}
    net = Net(len(ents))                                       # one lane per entry, only that entry in its library
    lib = _build.library(net)
    boot, _ = _build.boot(net)
    sel, cfg = _build.ports(net, 4, 'sel'), _build.ports(net, _build.SLOT_CW, 'cfg')
    net.place_box('celleval.DICT', boot, lib + [sel], [cfg], stages=stages, n_ports=1, K=_build.LIB_K, **_build.SLOT)
    s = net.state()
    for k in range(_build.LIB_K): net.load(s, lib[k], [words[k] if k == kk else 0 for kk, _ in ents])
    net.load(s, sel, [e[1] for _, e in ents])
    s, _ = net.run(s, 1)
    got = net.read(s, cfg)
    return {k: (e[0], e[1], slot_circuit(got[i], e[0])) for i, (k, e) in enumerate(ents)}


def describe_cells(circ, n_inputs, in_names='abcdefgh'):
    m, cells = circ
    nm = lambda s: str(s) if s < 2 else in_names[s - 2] if s < 2 + n_inputs else f'u{s - 2 - n_inputs}'
    out = []
    for j, (z, pairs) in enumerate(cells):
        terms = []
        for a, b in pairs:
            if a == 1 and b == 1: terms.append('1')
            elif a == 1 or b == 1 or a == b: terms.append(nm(b if a == 1 else a))
            else: terms.append(f'{nm(a)}∧{nm(b)}')
        body = ' ∨ '.join(dict.fromkeys(terms)) or '0'
        out.append(f"u{j}' = " + (body if z else f'¬({body})'))
    return '; '.join(out)



# ------------------------------------------------------------------ word answers, via RUN in an observation net
def run_answers(ans, res, T, width=256):
    """Every solved lane's answer run for T periods by the RUN box in an observation net with the same lanes (units
    are other lanes' answers): list of term lists (None if unsolved or invalid)."""
    net = Net(len(ans))
    boot, _ = _build.boot(net)
    a, r, ok = _build.ports(net, _build.LIB_EW, 'ans'), _build.ports(net, 17, 'res'), net.add_port('ok')
    outs = [_build.ports(net, width, f'o{t}.') for t in range(T)]
    net.place_box('wordeval.RUN', boot, [a, r], [[ok]] + outs, T=T)
    s = net.state()
    net.load(s, a, list(ans)); net.load(s, r, list(res))
    s, _ = net.run(s, 1)
    okv = net.read(s, [ok])
    signed = lambda v: int(v) - (1 << width) if int(v) >> (width - 1) else int(v)
    cols = [net.read(s, w) for w in outs]
    return [[signed(c[i]) for c in cols] if okv[i] else None for i in range(len(ans))]


def trace_answers(ans, res, T, N=15, width=256):
    """Every solved lane's answer with units expanded, run by the TRACE box in an observation net: per lane
    (flat nodes, values[t][j]) or None (unsolved or more than N nodes)."""
    net = Net(len(ans))
    boot, _ = _build.boot(net)
    a, r = _build.ports(net, _build.LIB_EW, 'ans'), _build.ports(net, 17, 'res')
    n, fw = _build.ports(net, 8, 'n'), _build.ports(net, 6 + 21 * N, 'flat')
    outs = [_build.ports(net, width, f'v{k}.') for k in range(T * N)]
    net.place_box('wordeval.TRACE', boot, [a, r], [n, fw] + outs, T=T, N=N)
    s = net.state()
    net.load(s, a, list(ans)); net.load(s, r, list(res))
    s, _ = net.run(s, 1)
    nv, fwv = net.read(s, n), net.read(s, fw)
    signed = lambda v: int(v) - (1 << width) if int(v) >> (width - 1) else int(v)
    cols = [net.read(s, w) for w in outs]
    res_ = []
    for i in range(len(ans)):
        k = int(nv[i])
        if not k: res_.append(None); continue
        res_.append((word_nodes(fwv[i]), [[signed(cols[t * N + j][i]) for j in range(k)] for t in range(T)]))
    return res_


def describe_flat(nodes):
    """A wiring with units expanded (sources 0, 1, 4 + j): node j is v_j; out = the last node."""
    nm = lambda s: str(s) if s < 2 else f'v{s - 4}'
    return '; '.join(f"v{j}' = {OPS[op]}({nm(a)}, {nm(b)}) [start {i}]" for j, (op, a, b, i) in enumerate(nodes)) + f"; out = v{len(nodes) - 1}"
