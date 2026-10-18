"""Box file: word-wiring boxes, placed only through the net (net.place_box('wordeval.NAME', ..., **params)).

  EVAL    stands in for running blocks of word wirings and comparing them with each lane's target terms.
          Speed only: numpy over a block of B candidates at once, on every core.
  GLOBAL  called every period across all lanes: ranks every unit found by how many answers use it and writes the
          most used into the global library ports (64 slots, minus slots holding cell circuits).
  RUN     runs each lane's answer wiring for T periods on exact integers (used to check results on all known terms).
  TRACE   runs each lane's answer wiring with its units expanded and gives every node's value per period (observation).

What these boxes know (generic, nothing per target):
  * units: every lane's answer port is a unit once the lane is solved (its res > 0). Together the answer ports are
    the store of all units found, inside the net; a unit is named by its lane number.
  * a wiring is m word nodes; node j = (type, src_a, src_b, start). Sources: 0, 1, or any node's value one period
    earlier (itself included). Types: the word ops below, or a unit (its output is its last node; it has its own
    state; a unit's own units are expanded when it runs). The output of a wiring is its last node.
  * two breadth-first walks with no end, in equal ticks (blocks alternate): one whose node types are the word ops
    and the units in the global library ports, one whose node types are the word ops and every unit found.
    Each walks all wirings of 1 node, then 2, then 3, ...; a unit that newly joins its library adds its own wirings
    at every depth already walked. Nothing is walked twice; only the net's run time limits how far they get.
  * a wiring word (answer or library): bits 0-1 kind (2 = word wiring), bits 2-5 node count, then 21 bits per node:
    op (12), a (4), b (4), start (1). op < 7 is a word op; op = 7 + u is unit u (lane u's answer).
A match is the candidate's output equal to the lane's R terms, starting at period 0..LAGS-1.
"""
import os
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from arith import _SCALAR, _signed               # the word ops are defined once, in arith.py

_OPS = list(_SCALAR)                             # ADD SUB MUL DIV MOD MIN MAX
_NB = len(_OPS)
_COMMUTATIVE = (0, 2, 5, 6)
_LIM = 1 << 47
_HP = np.uint64(0x9E3779B97F4A7C15)


def _apply(o, x, y, ok):
    if o == 0: return x + y
    if o == 1: return x - y
    if o == 2:
        ok &= ~(np.abs(x.astype(float) * y) >= _LIM); return x * y
    if o in (3, 4):
        ok &= y != 0
        yy = np.where(y == 0, 1, y)
        return np.floor_divide(x, yy) if o == 3 else np.mod(x, yy)
    if o == 5: return np.minimum(x, y)
    return np.maximum(x, y)


def _exact(o, x, y):
    if o in (3, 4) and y == 0: return None
    return _SCALAR[_OPS[o]](x, y)


# ------------------------------------------------------------------- library words
_WORD = 2
_NODE = 21


def _kind(v): return int(v) & 3


def _fits(nodes, EW): return len(nodes) <= 11 and 6 + _NODE * len(nodes) <= EW


def _encode(nodes):
    v = _WORD | len(nodes) << 2
    for j, (op, a, b, init) in enumerate(nodes):
        v |= (op | a << 12 | b << 16 | init << 20) << (6 + _NODE * j)
    return v


def _decode(v):
    v = int(v)
    out = []
    for j in range((v >> 2) & 15):
        f = v >> (6 + _NODE * j)
        out.append((f & 4095, (f >> 12) & 15, (f >> 16) & 15, (f >> 20) & 1))
    return out


def _flat(u, units, cache):
    """Unit u expanded to word ops only, as an entry: sources 0, 1, 4 + j (entry node j)."""
    if u in cache: return cache[u]
    nodes = units[u]
    ents = [_flat(op - _NB, units, cache) if op >= _NB else None for op, *_ in nodes]
    size = [len(e) if e else 1 for e in ents]
    last = list(np.cumsum(size) - 1)
    src = lambda s: s if s < 2 else 4 + int(last[s - 2])
    out = []
    for (op, a, b, init), e in zip(nodes, ents):
        if e is None:
            out.append((op, src(a), src(b), init))
        else:
            base = len(out)
            inner = lambda s: s if s < 2 else src(a) if s == 2 else src(b) if s == 3 else 4 + base + (s - 4)
            out.extend((eo, inner(ea), inner(eb), ei) for eo, ea, eb, ei in e)
    cache[u] = tuple(out)
    return cache[u]


class _Lib:
    """The node types of one shell beyond the word ops: their expanded entries, in type order."""

    def __init__(self, entries):
        self.entries = [tuple(map(tuple, e)) for e in entries]
        self.reads = [(any(2 in (a, b) for _, a, b, _ in e), any(3 in (a, b) for _, a, b, _ in e)) for e in self.entries]

    def run_exact(self, nodes, T):
        """One wiring (local type numbers) on Python ints (no width limit); None if it divides by zero."""
        st = [[e[3] for e in self.entries[op - _NB]] if op >= _NB else [init] for op, a, b, init in nodes]
        out = [st[-1][-1]]
        for _ in range(T - 1):
            val = [0, 1] + [s[-1] for s in st]
            new = []
            for (op, a, b, _), s in zip(nodes, st):
                x, y = val[a], val[b]
                if op < _NB: r = [_exact(op, x, y)]
                else:
                    loc = [0, 1, x, y] + s
                    r = [_exact(eo, loc[ea], loc[eb]) for eo, ea, eb, _ in self.entries[op - _NB]]
                if None in r: return None
                new.append(r)
            st = new
            out.append(st[-1][-1])
        return out


def _units(ans, res, lanes):
    """{unit (lane number): nodes} for every solved lane whose answer is a word wiring."""
    return {int(l): _decode(a) for l, a, r in zip(lanes, ans, res) if r and _kind(a) == _WORD}


# ------------------------------------------------------------------- shells: the breadth-first walk
# A shell (m, units, new): all wirings of m nodes whose types are the word ops and `units` (types 7, 8, ...);
# with new = True only those that use the last unit.
def _shell_size(m, n, new):
    U = (2 + m) ** 2 * 2
    return ((n * U) ** m - ((n - 1) * U) ** m) if new else (n * U) ** m


def _shell_decode(m, n, new, idx):
    """Node fields, each an (m, count) array, of positions idx in a shell."""
    S, U = 2 + m, (2 + m) ** 2 * 2
    idx = np.asarray(idx, np.int64)
    op = np.empty((m, len(idx)), np.int64); a = np.empty_like(op); b = np.empty_like(op); init = np.empty_like(op)
    if not new:
        r = idx.copy()
        for j in range(m):
            r, init[j] = np.divmod(r, 2); r, b[j] = np.divmod(r, S); r, a[j] = np.divmod(r, S); r, op[j] = np.divmod(r, n)
        return op, a, b, init
    # js = the first node of type n - 1; nodes before it use types < n - 1, nodes after it any type < n
    r, js = idx.copy(), np.full(len(idx), -1, np.int64)
    for j in range(m):
        cnt = (n - 1) ** j * n ** (m - 1 - j) * U ** m
        js[(js < 0) & (r < cnt)] = j
        r = np.where(js < 0, r - cnt, r)
    pos, r = r // (U ** m), r % (U ** m)
    for j in range(m):
        r, init[j] = np.divmod(r, 2); r, b[j] = np.divmod(r, S); r, a[j] = np.divmod(r, S)
    for j in range(m):
        pos, digit = np.divmod(pos, np.where(j == js, 1, np.where(j < js, n - 1, n)))
        op[j] = np.where(j == js, n - 1, digit)
    return op, a, b, init


def _canonical(lib, op, a, b, init):
    """False for a wiring with an earlier twin: a commutative op with a > b, an entry node's unused start bit,
    or a source given to an input the entry never reads."""
    keep = np.ones(op.shape[1], bool)
    for j in range(op.shape[0]):
        keep &= ~(np.isin(op[j], _COMMUTATIVE) & (a[j] > b[j]))
        keep &= ~((op[j] >= _NB) & (init[j] == 1))
        for e, (rp, rq) in enumerate(lib.reads):
            sel = op[j] == _NB + e
            if not rp: keep &= ~(sel & (a[j] != 0))
            if not rq: keep &= ~(sel & (b[j] != 0))
    return keep


def _run(lib, op, a, b, init, T):
    m, count = op.shape
    K = max([len(e) for e in lib.entries] or [1])
    ist = np.zeros((m, K, count), np.int64)
    v = np.where(op < _NB, init, 0)
    for j in range(m):
        for e in np.unique(op[j][op[j] >= _NB]):
            ent, sel = lib.entries[e - _NB], op[j] == e
            for k, (_, _, _, i0) in enumerate(ent): ist[j, k, sel] = i0
            v[j, sel] = ent[-1][3]
    ok = np.ones(count, bool)
    out = np.empty((count, T), np.int64); out[:, 0] = v[m - 1]
    ar = np.arange(count)
    for t in range(1, T):
        srcs = np.concatenate([np.zeros((1, count), np.int64), np.ones((1, count), np.int64), v])
        nv = np.zeros_like(v); nist = ist.copy()
        for j in range(m):
            x = srcs[a[j], ar]; y = srcs[b[j], ar]
            for o in np.unique(op[j]):
                sel = op[j] == o
                okk = np.ones(sel.sum(), bool)
                if o < _NB:
                    nv[j, sel] = _apply(o, x[sel], y[sel], okk)
                else:
                    ent = lib.entries[o - _NB]
                    n = sel.sum()
                    loc = [np.zeros(n, np.int64), np.ones(n, np.int64), x[sel], y[sel]] + [ist[j, k, sel] for k in range(len(ent))]
                    for k, (eo, ea, eb, _) in enumerate(ent):
                        nist[j, k, sel] = _apply(eo, loc[ea], loc[eb], okk)
                    nv[j, sel] = nist[j, len(ent) - 1, sel]
                ok[sel] &= okk
        ok &= (np.abs(nv) < _LIM).all(0)
        v = np.where(ok, nv, 0); ist = np.where(ok, nist, 0)
        out[:, t] = v[m - 1]
    return out, ok


def _hash(rows):
    h = np.zeros(rows.shape[0], np.uint64)
    with np.errstate(over='ignore'):
        for k in range(rows.shape[1]):
            h = h * _HP + rows[:, k].astype(np.uint64)
    return h


def _block(entries, shell, lo, hi, R, LAGS):
    """Candidates lo..hi of a shell, run and indexed by hash (one table per lag)."""
    lib = _Lib(entries)
    m, units, new = shell
    fields = _shell_decode(m, _NB + len(units), new, np.arange(lo, hi, dtype=np.int64))
    keep = _canonical(lib, *fields)
    out = np.zeros((hi - lo, R + LAGS), np.int64); ok = np.zeros(hi - lo, bool)
    if keep.any():
        o, k = _run(lib, *[f[:, keep] for f in fields], R + LAGS)
        out[keep], ok[keep] = o, k
    tables = []
    for L in range(LAGS):
        h = np.where(ok, _hash(out[:, L:L + R]), np.uint64(0))
        order = np.argsort(h, kind='stable')
        tables.append((h[order], order))
    return out, ok, tables


# ------------------------------------------------------------------- the boxes
class _Walk:
    """One breadth-first walk: a schedule of shells, extended as it goes."""

    def __init__(self, B):
        self.B, self.depth, self.sched, self.queue, self.blocks, self.known = B, 0, [], [], 0, []

    def add(self, u, current):
        """Unit u joins this walk's library; `current` = the units it has now, in order (u last)."""
        if u in self.known: return
        self.known.append(u)
        self.queue.extend((m, tuple(current), True) for m in range(1, self.depth + 1))

    def where(self, b, current):
        while self.blocks <= b:
            if self.queue:
                self.queue.sort(key=lambda s: (s[0], len(s[1]))); shell = self.queue.pop(0)
            else:
                self.depth += 1; shell = (self.depth, tuple(current), False)
            size = _shell_size(shell[0], _NB + len(shell[1]), shell[2])
            nb = (size + self.B - 1) // self.B
            self.sched.append((self.blocks, self.blocks + nb, shell, size)); self.blocks += nb
        for b0, b1, shell, size in reversed(self.sched):
            if b0 <= b < b1: return shell, (b - b0) * self.B, min((b - b0 + 1) * self.B, size), b1


def EVAL(R=16, W=48, LAGS=3, B=1 << 16, K=64, EW=256, workers=None, status=False):
    # RULE VIOLATION (PEIXUAN, 2026-10-16): hand-written from scratch; it does not replace cells already found in the net.
    """EVAL(lanes, q, go, res, ans, *K global-library unit words, *R target words) -> (res, end, ans).
    Called in every lane each period (it reads every lane's answer: the store of all units); lanes with go = 1
    search block q (even q: the global-library walk, odd q: the all-units walk, block q // 2 of it); other lanes
    keep their res and ans. A unit word in the global library is 1 + the unit's lane number (0 = empty).
    status: 6 more outputs per walk (observation ports): node count m of the shell holding its latest block, units in
    that shell, new flag, blocks of that shell walked, blocks in that shell, blocks walked in all."""
    workers = workers or os.cpu_count() or 1
    pool = ProcessPoolExecutor(workers) if workers > 1 else None
    st = dict(cache={}, units={}, flat={}, walks=(_Walk(B), _Walk(B)), order=[], glob=[], last=[-1, -1])

    def stat(n):
        out = []
        for s in (0, 1):
            b, w = st['last'][s], st['walks'][s]
            if b < 0: out += [0] * 6; continue
            for b0, b1, (m, us, new), _ in w.sched:
                if b0 <= b < b1: out += [m, len(us), int(new), b - b0 + 1, b1 - b0, b + 1]; break
        return tuple(np.full(n, v, np.int64) for v in out)

    def entries(shell):
        return [_flat(u, st['units'], st['flat']) for u in shell[1]]

    def get(s, b, current):
        c, w = st['cache'], st['walks'][s]
        for k in [k for k in c if k[0] == s and k[1] < b]: del c[k]
        if (s, b) not in c:
            _, _, _, b1 = w.where(b, current)
            for k in range(b, min(b + 2 * workers, b1) if pool else b + 1):
                if (s, k) in c: continue
                sh, lo, hi, _ = w.where(k, current)
                c[(s, k)] = (sh, lo, pool.submit(_block, entries(sh), sh, lo, hi, R, LAGS) if pool else _block(entries(sh), sh, lo, hi, R, LAGS))
        sh, lo, v = c[(s, b)]
        if hasattr(v, 'result'): v = v.result(); c[(s, b)] = (sh, lo, v)
        return sh, lo, v

    def run(lanes, q, go, res, ans, *rest):
        glob_words, terms = rest[:K], rest[K:]
        units = _units(ans, res, lanes)
        for u in sorted(units):                                     # newly found units join the all-units walk
            if u not in st['units']:
                st['units'][u] = units[u]; st['order'].append(u)
                st['walks'][1].add(u, st['order'])
        glob = [int(w[0]) - 1 for w in glob_words if 0 < int(w[0]) and int(w[0]) - 1 in st['units']]
        for i, u in enumerate(glob):                                # units newly in the global library join that walk
            st['walks'][0].add(u, glob[:i + 1] if u not in st['walks'][0].known else glob)
        st['glob'] = glob
        res_out, ans_out = np.array(res, np.int64), np.array(ans, dtype=object)
        end = np.zeros(len(lanes), np.int64)
        srch = np.flatnonzero(np.asarray(go) != 0)
        tail = stat(len(lanes)) if status else ()
        if not len(srch): return (res_out, end, ans_out) + tail
        tgt = np.stack([_signed(np.asarray(t)[srch], W) for t in terms], 1)
        th = _hash(tgt)
        qs = np.asarray(q, np.int64)[srch]
        for qq in np.unique(qs):
            s, b = int(qq) % 2, int(qq) // 2
            st['last'][s] = max(st['last'][s], b)
            current = st['glob'] if s == 0 else st['order']
            (m, us, new), lo0, (out, ok, tables) = get(s, b, current)
            sel = np.flatnonzero(qs == qq)
            if not _fits([0] * m, EW): end[srch[sel]] = 1; continue
            best = np.full(len(sel), -1, np.int64)
            for L, (hs, order) in enumerate(tables):
                lo = np.searchsorted(hs, th[sel], 'left'); hi = np.searchsorted(hs, th[sel], 'right')
                for i in np.flatnonzero(hi > lo):
                    for p in range(lo[i], hi[i]):
                        j = order[p]
                        if ok[j] and np.array_equal(out[j, L:L + R], tgt[sel[i]]) and (best[i] < 0 or j < best[i]): best[i] = j
            res_out[srch[sel]] = best + 1
            for i in np.flatnonzero(best >= 0):
                f = _shell_decode(m, _NB + len(us), new, [lo0 + int(best[i])])
                nodes = [tuple(int(x[j, 0]) for x in f) for j in range(m)]
                ans_out[srch[sel[i]]] = _encode([(op if op < _NB else _NB + us[op - _NB], a, b_, i0) for op, a, b_, i0 in nodes])
        return (res_out, end, ans_out) + (stat(len(lanes)) if status else ())

    run.close = lambda: pool and pool.shutdown(cancel_futures=True)
    return run


def GLOBAL(K=64):
    # RULE VIOLATION (PEIXUAN, 2026-10-16): hand-written from scratch; it does not replace cells already found in the net.
    """GLOBAL(lanes, ans, res, *K library words) -> (*K library words, *K unit words, *K use counts).
    Called every period across all lanes. Uses of a unit = the answers that have it as a node. The most used units
    (ties: lowest lane first) fill the library slots that do not hold a cell circuit (kind 1); the unit word of a
    slot is 1 + the unit's lane number (0 = none). The library word is the unit's own wiring word."""
    def run(lanes, ans, res, *words):
        words = [int(w[0]) for w in words]
        units = _units(ans, res, lanes)
        uses = {u: 0 for u in units}
        for nodes in units.values():
            for u in {op - _NB for op, *_ in nodes if op >= _NB}:
                if u in uses: uses[u] += 1
        ranked = sorted(units, key=lambda u: (-uses[u], u))
        lane_of = {int(l): i for i, l in enumerate(lanes)}
        lib, uid, cnt = list(words), [0] * K, [0] * K
        free = [k for k, v in enumerate(words) if _kind(v) != 1]
        for k in free: lib[k] = 0
        for k, u in zip(free, ranked):
            lib[k], uid[k], cnt[k] = int(ans[lane_of[u]]), u + 1, uses[u]
        n = len(lanes)
        return tuple(np.full(n, v, dtype=object) for v in lib) + tuple(np.full(n, v, np.int64) for v in uid + cnt)
    return run


def RUN(T):
    # RULE VIOLATION (PEIXUAN, 2026-10-16): hand-written from scratch; it does not replace cells already found in the net.
    """RUN(lanes, ans, res) -> (ok, *T words): each solved lane's answer wiring run for T periods on exact integers,
    its units taken from the other lanes' answers (ok = 0 if it divides by zero or the lane is unsolved)."""
    def run(lanes, ans, res):
        units = _units(ans, res, lanes)
        cache = {}
        ok = np.zeros(len(lanes), np.int64); out = np.zeros((T, len(lanes)), dtype=object)
        for i, l in enumerate(lanes):
            if int(l) not in units: continue
            seq = _Lib([_flat(int(l), units, cache)]).run_exact([(_NB, 0, 0, 0)], T)
            if seq is not None: ok[i] = 1; out[:, i] = seq
        return (ok,) + tuple(out)
    return run


def TRACE(T, N):
    # RULE VIOLATION (PEIXUAN, 2026-10-16): hand-written from scratch; it does not replace cells already found in the net.
    """TRACE(lanes, ans, res) -> (n, flat, *N*T words): each solved lane's answer with its units expanded to word
    ops (n nodes; flat = that wiring as a word, sources 0, 1, 4 + j for node j; n = 0 if more than N nodes), and
    node j's value at period t in output 2 + t*N + j, on exact integers (observation: how the wiring makes its terms;
    values after a division by zero stay 0)."""
    def run(lanes, ans, res):
        units = _units(ans, res, lanes)
        cache = {}
        nn = np.zeros(len(lanes), np.int64); fw = np.zeros(len(lanes), dtype=object)
        out = np.zeros((T * N, len(lanes)), dtype=object)
        for i, l in enumerate(lanes):
            if int(l) not in units: continue
            e = _flat(int(l), units, cache)
            if len(e) > N: continue
            nn[i], fw[i] = len(e), _encode(e)
            v = [init for *_, init in e]
            for t in range(T):
                for j in range(len(e)): out[t * N + j, i] = v[j]
                loc = [0, 1, 0, 0] + v
                nv = [_exact(op, loc[a], loc[b]) for op, a, b, _ in e]
                if None in nv: break
                v = nv
        return (nn, fw) + tuple(out)
    return run
