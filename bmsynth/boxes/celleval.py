"""Box file: cell-circuit boxes. Placed only through the net (net.place_box('celleval.NAME', ..., **params)):

  CELLEVAL  stands in for running a block of small cell circuits over time and comparing their output stream
            with a target. Speed only: it is the cell rule itself, run on B candidates at once.
  STORE     called every period across lanes: writes each behaviour's best find into the library ports.
  DICT      the dictionary node: copies library entries into the paste ports of programmable slots.

What these boxes know (generic, nothing per behaviour):
  * a candidate number g is a circuit of m cells, smallest first (the `stages`, each m cells with K
    pairs per cell). Every pair reads two sources one tick earlier: constant 0, constant 1, an input,
    or any cell of the circuit (itself included), so feedback is allowed. All cells start at 0.
  * the output is the last cell.
  * a library entry (one port word): bits 0-1 kind (1 = cell circuit), bits 2-3 inputs, bits 4-7 group
    (which behaviour found it), bits 8.. g. Other kinds are left alone.
  * a slot's paste port (layout given by the experiment that built the slot: M cells, P pairs per cell, NI
    inputs): per cell z (1 bit), then per pair a, b (SB bits each); source numbers 0, 1, 2..2+NI-1 inputs,
    2+NI+j slot cell j. A circuit of m cells sits in the last m slot cells; 0 = pair off.
"""
import math
import numpy as np


_CELL = 1


def _kind(v): return int(v) & 3


def _encode(n_inputs, group, g): return _CELL | n_inputs << 2 | group << 4 | int(g) << 8


def _decode(v):
    v = int(v)
    return (v >> 2) & 3, (v >> 4) & 15, v >> 8                  # inputs, group, g


class _CellSpace:
    def __init__(self, n_inputs, stages, max_bits=22):
        self.n_inputs = n_inputs
        self.stages = []
        for m, K in stages:
            nsrc = 2 + n_inputs + m
            sb = max(1, math.ceil(math.log2(nsrc)))
            bits = sum(1 + 2 * sb * k for k in K)
            if bits <= max_bits: self.stages.append((m, list(K), sb, bits))

    def sizes(self): return [1 << bits for *_, bits in self.stages]

    def total(self): return sum(self.sizes())

    def locate(self, g):
        for st, size in zip(self.stages, self.sizes()):
            if g < size: return st, g
            g -= size
        return None, None

    def fields(self, st, cfg):
        """Per cell: (z, [(a, b), ...]) with source numbers 0, 1, 2.. inputs, 2+n_inputs.. cells; out of range = 0."""
        m, K, sb, _ = st
        nsrc, bit, cells = 2 + self.n_inputs + m, 0, []
        take = lambda n: (cfg >> n) & ((1 << sb) - 1)
        for j in range(m):
            z = (cfg >> bit) & 1; bit += 1
            pairs = []
            for _ in range(K[j]):
                a, b = take(bit), take(bit + sb); bit += 2 * sb
                pairs.append((np.where(a < nsrc, a, 0), np.where(b < nsrc, b, 0)))
            cells.append((z, pairs))
        return cells

    def decode(self, g):
        """The circuit as plain numbers: (m, [(z, [(a, b), ...]) per cell])."""
        st, cfg = self.locate(g)
        return st[0], [(int(z), [(int(a), int(b)) for a, b in pairs]) for z, pairs in self.fields(st, cfg)]

    def run_block(self, st, start, count, stim):
        """Output streams (count, T) of configs start..start+count for one stimulus (T, n_inputs)."""
        m = st[0]
        cfg = np.arange(start, start + count, dtype=np.int64)
        cells = self.fields(st, cfg)
        T = len(stim)
        state = np.zeros((m, count), bool)
        out = np.zeros((count, T), bool)
        ar = np.arange(count)
        for t in range(T):
            S = np.concatenate([np.zeros((1, count), bool), np.ones((1, count), bool),
                                np.repeat(np.asarray(stim[t], bool).reshape(-1, 1), count, 1).reshape(self.n_inputs, count), state])
            new = np.empty_like(state)
            for j, (z, pairs) in enumerate(cells):
                acc = np.zeros(count, bool)
                for a, b in pairs: acc |= S[a, ar] & S[b, ar]
                new[j] = (z == 1) == acc
            state = new
            out[:, t] = state[m - 1]
        return out


def CELLEVAL(stages, T, B=1 << 16, max_inputs=3, K=64, max_bits=22):
    # RULE VIOLATION (PEIXUAN, 2026-10-16): hand-written from scratch; it does not replace cells already found in the net.
    """CELLEVAL(lanes, q, *K library words, n_inputs, *max_inputs stimulus words, target, care) -> (res, end, ans).
    Each lane has its own number of inputs, so one net can search behaviours of every arity; ans is the found
    circuit as a library entry (bits 0-1 kind = 1, 2-3 inputs, 4-7 group, 8.. g)."""
    spaces = [_CellSpace(n, stages, max_bits) for n in range(max_inputs + 1)]
    cache = {}

    def block(space, q, stim):
        key = (space.n_inputs, q, stim.tobytes())
        if key not in cache:
            if len(cache) > 64: cache.clear()
            g0, g1, base, outs = q * B, min((q + 1) * B, space.total()), 0, []
            for st, size in zip(space.stages, space.sizes()):
                lo, hi = max(g0, base), min(g1, base + size)
                if lo < hi: outs.append(space.run_block(st, lo - base, hi - lo, stim))
                base += size
            cache[key] = np.concatenate(outs)
        return cache[key]

    bits = lambda v: np.array([(int(v) >> t) & 1 for t in range(T)], bool)

    def CELLEVAL(lanes, q, *words):
        nin, stims, tgt, care = words[K], words[K + 1:K + 1 + max_inputs], words[-2], words[-1]
        res, end, ans = np.zeros(len(q), np.int64), np.zeros(len(q), np.int64), np.zeros(len(q), np.int64)
        for i in range(len(q)):
            space = spaces[int(nin[i])]
            if int(q[i]) * B >= space.total(): end[i] = 1; continue
            stim = np.stack([bits(w[i]) for w in stims[:space.n_inputs]], 1) if space.n_inputs else np.zeros((T, 0), bool)
            out = block(space, int(q[i]), stim)
            hit = np.flatnonzero(~((out != bits(tgt[i])[None, :]) & bits(care[i])[None, :]).any(1))
            if len(hit):
                res[i] = hit[0] + 1
                ans[i] = _encode(space.n_inputs, 0, int(q[i]) * B + int(hit[0]))
        return res, end, ans

    return CELLEVAL


def STORE(K=64):
    # RULE VIOLATION (PEIXUAN, 2026-10-16): hand-written from scratch; it does not replace cells already found in the net.
    """STORE(lanes, ans, res, group, rank, *K library words) -> *K library words.
    Called every period across all lanes: for each group of lanes (one behaviour), the smallest circuit found (then the smallest rank)
    goes into a free library slot, tagged with the group."""
    def STORE(lanes, ans, res, group, rank, *words):
        words = [int(w[0]) for w in words]
        best = {}
        for a, r, gp, rk in zip(ans, res, group, rank):
            if r:
                nin, _, g = _decode(a)
                best[int(gp)] = min(best.get(int(gp), (g, int(rk), nin)), (g, int(rk), nin))
        have = {_decode(v)[1] for v in words if _kind(v) == _CELL}
        free = iter(k for k, v in enumerate(words) if v == 0)
        for gp, (g, rk, nin) in sorted(best.items()):
            if gp not in have: words[next(free)] = _encode(nin, gp, g)
        return tuple(np.full(len(lanes), v, np.int64) for v in words)
    return STORE


def DICT(stages, n_ports, K=64, max_inputs=3, M=3, P=2, NI=3):
    # RULE VIOLATION (PEIXUAN, 2026-10-16): hand-written from scratch; it does not replace cells already found in the net.
    """DICT(lanes, *K library words, *n_ports select words) -> n_ports paste-port words.
    Each select word names a behaviour (group tag); the entry with that tag is written into the paste port in the
    slot layout (M, P, NI) as wiring; 0 if the library has no such entry."""
    spaces = [_CellSpace(n, stages) for n in range(max_inputs + 1)]
    SB = math.ceil(math.log2(2 + NI + M)); CB = 1 + 2 * P * SB

    def config(space, g):
        m, cells = space.decode(g)
        assert m <= M and all(len(p) <= P for _, p in cells)
        shift = M - m
        src = lambda s: s if s < 2 + space.n_inputs else 2 + NI + shift + (s - 2 - space.n_inputs)
        v = 0
        for j, (z, pairs) in enumerate(cells):
            f = z
            for k, (a, b) in enumerate(pairs):
                if 0 in (a, b): continue
                f |= (src(a) | src(b) << SB) << (1 + 2 * SB * k)
            v |= f << (CB * (j + shift))
        return v

    def run(lanes, *words):
        lib, sel = words[:K], words[K:]
        out = [np.zeros(len(lanes), np.int64) for _ in range(n_ports)]
        for i in range(len(lanes)):
            by_group = {}
            for w in lib:
                if _kind(w[i]) == _CELL:
                    nin, gp, g = _decode(w[i])
                    by_group.setdefault(gp, (nin, g))
            for p in range(n_ports):
                hit = by_group.get(int(sel[p][i]))
                if hit: out[p][i] = config(spaces[hit[0]], hit[1])
        return tuple(out)
    return run
