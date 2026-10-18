"""The word-wiring searcher, shared by onenet: built by hand from the core API around the boxes wordeval.EVAL
and wordeval.GLOBAL (placed by name), plus reading its results.

Lanes: one OEIS target each (R terms in ports, W-bit two's complement).
Observation afterwards: each lane's answer and the global library are read from ports; the answers are run on all
known terms by the wordeval.RUN box and traced by the wordeval.TRACE box, each in an observation net.
"""
import _setup, _build
from lanes import LaneBoxNet as Net
import _observe as O

R, W, LAGS, B = 16, 48, 3, 1 << 16
WALK = ('nodes', 'units', 'new', 'shell_done', 'shell_blocks', 'blocks')   # EVAL's status ports, per walk


def word_search(net, lib, tg, pre=0, **kw):
    """The word searcher: target ports, the global library's unit and use-count ports, EVAL (bus mode) and GLOBAL.
    pre: lanes before the targets (other tasks' lanes) in the same net."""
    T = [_build.ports(net, W, f'T{k}_') for k in range(R)]
    uid = [_build.ports(net, 12, f'G{k}.unit') for k in range(_build.LIB_K)]
    cnt = [_build.ports(net, 16, f'G{k}.uses') for k in range(_build.LIB_K)]
    walk = [_build.ports(net, 40, f'walk{s}.{f}') for s in (0, 1) for f in WALK]      # observation ports
    nd = _build.searcher(net, ('wordeval.EVAL', dict(R=R, W=W, LAGS=LAGS, B=B, K=_build.LIB_K, EW=_build.LIB_EW, status=True)), T, uid,
                         ('wordeval.GLOBAL', dict(K=_build.LIB_K)), bus=True, round_lib=lib, round_outs=lib + uid + cnt,
                         eval_outs=walk, **kw)
    nd.update(T=T, uid=uid, cnt=cnt, glib=lib, pre=pre, walk=walk)
    return nd


def observe(net, s, nd, tg):
    """Rows per target: found, wiring, and whether it gives every known term (run by wordeval.RUN in an
    observation net); the global library with use counts."""
    pre = nd['pre']
    res, ans = net.read(s, nd['res']), net.read(s, nd['ans'])
    name = lambda u: f"A{tg[u - pre]['n']:06d}" if 0 <= u - pre < len(tg) else f'U{u}'
    hit = [l for l in range(len(tg)) if res[pre + l]]
    seqs = O.run_answers(ans, res, max(len(t['terms']) for t in tg) + LAGS) if hit else []
    rows = [dict(A=d['n'], rank=d['rank'], name=d['name'][:100], found=bool(res[pre + l])) for l, d in enumerate(tg)]
    for l in hit:
        seq, terms = seqs[pre + l], tg[l]['terms']
        lag = next((k for k in range(LAGS) if seq and seq[k:k + R] == terms[:R]), 0)
        nodes = O.word_nodes(ans[pre + l])
        rows[l].update(nodes=len(nodes), decoded=nodes, wiring=O.describe_wiring(nodes, name), lag=lag,
                       uses_units=any(op >= O.NOP for op, *_ in nodes),
                       all_terms_ok=seq is not None and seq[lag:lag + len(terms)] == terms)
        if seq is not None:
            got = seq[lag:lag + len(terms)]
            bad = next((k for k, (x, y) in enumerate(zip(got, terms)) if x != y), None)
            rows[l].update(known_terms=len(terms), first_wrong=None if bad is None else dict(term=bad, expected=terms[bad], got=got[bad]))
    traces = O.trace_answers(ans, res, 10) if hit else []
    for l in hit:
        tr = traces[pre + l]
        if tr: rows[l].update(flat=O.describe_flat(tr[0]), trace=tr[1])
    words = [int(net.read(s, w)[0]) for w in nd['glib']]
    uids = [int(net.read(s, w)[0]) for w in nd['uid']]; cnts = [int(net.read(s, w)[0]) for w in nd['cnt']]
    return dict(found=len(hit), exact=sum(r.get('all_terms_ok', False) for r in rows),
                library=O.describe_library(words, uids, cnts, name), rows=rows)


def walk_state(net, s, nd):
    """Observation: where each walk is (read from EVAL's status ports)."""
    v = [int(net.read(s, w)[0]) for w in nd['walk']]
    return {name: dict(zip(WALK, v[6 * k:6 * k + 6])) for k, name in enumerate(('global', 'units'))}
