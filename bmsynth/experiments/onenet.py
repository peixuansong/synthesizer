"""The main experiment: behaviours -> word register -> OEIS as ONE net run, sharing one flat library.

One net, built by hand from the core API, then run until it halts by itself (or the wall-clock budget ends).
Lanes: item 1's behaviour lanes (29) and the OEIS targets, side by side in the same net.

  phase 1  searcher A (CELLEVAL + STORE) finds small cell circuits from their specs and stores them in the
           library ports. OEIS lanes are `off` for A. When every lane is done, A halts.
  phase 2  A halting starts (via a rising-edge cell) the dictionary node: it pastes the library's pulse,
           delay, inverted delay and memory bit into 19 programmable slots, which become a clock and a 16-bit
           register (item 2). An ADD box (arith.OP) on the pulse writes reg+3 back, so the register counts.
  phase 3  the same edge starts searcher B (EVAL + GLOBAL): word wirings for the OEIS targets, breadth first with
           no end. Every lane's answer is a unit as soon as it is found (the store of all units); GLOBAL keeps the
           most used units in the library ports (the global library). EVAL walks wirings over the global library and
           over all units in equal ticks (no rounds). Behaviour lanes
           are `off` for B.
Usage: onenet.py [n_targets (0 = all)] [seconds]   (the run time is the only limit)
"""
import sys, json, time
import _setup, _build, _wordrun as WR
import behaviours as I1, word_register as I2, oeis
from lanes import LaneBoxNet as Net
import _observe as O


# cell search settings (how CELLEVAL numbers candidate circuits): circuit sizes tried, smallest first, as
# (cells, pairs per cell); candidates per CELLEVAL call
STAGES = [(1, [1]), (1, [2]), (2, [1, 1]), (2, [1, 2]), (3, [1, 1, 1])]
B = 1 << 16


def snapshot(net, s, Bn, tg, nb, ticks, sec, solved_at):
    """Observation while the net runs: solved count, where each walk is, and the circuits emitted since last time."""
    res, ans = net.read(s, Bn['res']), net.read(s, Bn['ans'])
    name = lambda u: f"A{tg[u - nb]['n']:06d}" if 0 <= u - nb < len(tg) else f'U{u}'
    new = []
    for l in range(len(tg)):
        if res[nb + l] and l not in solved_at:
            solved_at[l] = ticks
            new.append(dict(A=f"A{tg[l]['n']:06d}", wiring=O.describe_wiring(O.word_nodes(ans[nb + l]), name)))
    q = net.read(s, Bn['q'])[nb:]
    return dict(tick=ticks, sec=round(sec, 1), solved=len(solved_at), q=int(q.max()), walks=WR.walk_state(net, s, Bn), new=new)


def main(n=0, seconds=150):
    tg = oeis.oeis_targets(WR.R, WR.W)[:n or None]
    blanes = [(gi, sp, L, tgt, care) for gi, sp in enumerate(I1.SPECS) for L, tgt, care in I1.variants(sp[3], I1.STIM[sp[2]], sp[4])]
    nb, nw = len(blanes), len(tg)
    net = Net(nb + nw)
    lib = _build.library(net)
    offA, offB = net.add_port('offA'), net.add_port('offB')

    # phase 1: behaviour search
    nin_w, group_w, rank_w = _build.ports(net, 2, 'inputs'), _build.ports(net, 4, 'group'), _build.ports(net, 4, 'rank')
    stim_w = [_build.ports(net, I1.T, f'stim{i}.') for i in range(3)]
    tgt_w, care_w = _build.ports(net, I1.T, 'tgt'), _build.ports(net, I1.T, 'care')
    A = _build.searcher(net, ('celleval.CELLEVAL', dict(stages=STAGES, T=I1.T, B=B)), [nin_w] + stim_w + [tgt_w, care_w], lib,
                        ('celleval.STORE', {}), [group_w, rank_w], off=offA)
    go = _build.rising(net, A['halt'], name='phase2')

    # phase 2: the register: clock slots filled from the library by the dictionary node, and the memory bit
    # duplicated W times by the duplicator box (behaviour lanes only)
    boot, rst = _build.boot(net, start=go)
    d = [net.add_port(f'd{i}') for i in range(I2.W)]
    sels, cfgs = [], []
    def place(behaviour, ins, tag):
        cfg, out, _ = _build.slot(net, ins, rst, tag)
        sels.append((_build.ports(net, 4, tag + '.sel'), I2.GROUP[behaviour])); cfgs.append(cfg)
        return out
    p = place('pulse4', [], 'pulse')
    load, nload = place('delay', [p], 'load'), place('idelay', [p], 'nload')
    net.place_box('celleval.DICT', boot, lib + [s for s, _ in sels], cfgs, stages=STAGES, n_ports=len(cfgs), **_build.SLOT)
    reg, mem_sel = _build.ports(net, I2.W, 'reg'), _build.ports(net, 4, 'reg.sel')
    net.place_box('duplicator.DUPLICATE', _build.NOT(net, offA), lib + [mem_sel, d, [load], [nload]], [reg],
                  stages=STAGES, n=I2.W, share='wss')
    three = _build.ports(net, 2, 'three')
    net.place_box('arith.OP', p, [reg, three], [d], name='ADD')

    # phase 3: word search for the OEIS targets
    Bn = WR.word_search(net, lib, tg, pre=nb, off=offB, start=go)
    T = Bn['T']

    s = net.state()
    net.load(s, [offA], [0] * nb + [1] * nw); net.load(s, [offB], [1] * nb + [0] * nw)
    stims = [I1.STIM[sp[2]] for _, sp, *_ in blanes]
    pad = lambda v: list(v) + [0] * nw
    net.load(s, nin_w, pad(len(st[0]) for st in stims)); net.load(s, group_w, pad(x[0] for x in blanes)); net.load(s, rank_w, pad(x[2] for x in blanes))
    for i in range(3): net.load(s, stim_w[i], pad(sum(st[t][i] << t for t in range(I1.T)) if i < len(st[0]) else 0 for st in stims))
    net.load(s, tgt_w, pad(x[3] for x in blanes)); net.load(s, care_w, pad(x[4] for x in blanes))
    for sel, gp in sels: net.load(s, sel, [gp])
    net.load(s, mem_sel, [I2.GROUP['memory']])
    net.load(s, three, [3])
    for k in range(WR.R): net.load(s, T[k], [0] * nb + [t['terms'][k] for t in tg])
    print(f'one net: {nb} behaviour lanes + {nw} OEIS lanes, {len(net.cells):,} cells, {len(net.boxes)} boxes', flush=True)

    # run: tick until searcher B halts in every lane, or the budget ends; note when phase 1 ends and watch the
    # register tick by tick for 200 ticks after that (observation)
    t0, ticks, marks, seen, watch, solved_at = time.time(), 0, {}, [], [], {}
    while True:
        s, ran = net.run(s, 80, stop=Bn['halt'], every=8)
        ticks += ran
        if 'phase2' not in marks and int(net.read(s, [A['halt']])[0]):
            marks['phase2'] = (ticks, round(time.time() - t0, 1)); print(f'  phase 1 done: tick {ticks}, {marks["phase2"][1]} s', flush=True)
            for _ in range(200):
                s, _ = net.run(s, 1); ticks += 1; seen.append(int(net.read(s, reg)[0]))
        watch.append(snapshot(net, s, Bn, tg, nb, ticks, time.time() - t0, solved_at))
        if ran < 80 or time.time() - t0 > seconds: break
        if ticks % 800 < 80: print(watch[-1]['walks'], flush=True)
        if ticks % 4000 < 80: print(f"  tick {ticks}  OEIS solved {int((net.read(s, Bn['res'])[nb:] > 0).sum())}  {time.time() - t0:.0f}s", flush=True)
    sec = round(time.time() - t0, 1); net.close()

    # observation
    words = [int(net.read(s, w)[0]) for w in lib]
    entries = {f'L{k}': f'cell: {I1.SPECS[gi][1]}: ' + O.describe_cells(circ, nin) for k, (nin, gi, circ) in O.cell_circuits(words, STAGES).items()}
    ob = WR.observe(net, s, Bn, tg)
    entries.update(ob['library'])
    reg_vals = [v for i, v in enumerate(seen) if i == 0 or v != seen[i - 1]]
    step = I2.TARGETS['add3']
    reg_ok = len(reg_vals) > 2 and all(step(a) & ((1 << I2.W) - 1) == b for a, b in zip(reg_vals, reg_vals[1:]))   # watched from mid-run
    mined = [r for r in ob['rows'] if r.get('uses_units')]
    out = dict(lanes=dict(behaviour=nb, oeis=nw), cells=len(net.cells), boxes=len(net.boxes), seconds=sec, ticks=ticks,
               phase1_end=marks.get('phase2'), halted=bool(int(net.read(s, [Bn['halt']])[0])),
               library=entries, register=dict(values=reg_vals[:20], counts_by_3=reg_ok),
               oeis=dict(found=ob['found'], exact=ob['exact'], using_units=[dict(A=r['A'], name=r['name'][:80], wiring=r['wiring'], exact=r['all_terms_ok']) for r in mined]),
               rows=ob['rows'])
    json.dump(out, open(_setup.res('onenet.json'), 'w'), indent=1)
    json.dump(watch, open(_setup.res('onenet_watch.json'), 'w'), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ('oeis', 'rows')}, indent=1)); print('OEIS found', ob['found'], 'exact', ob['exact'], 'in', sec, 's')


if __name__ == '__main__':
    a = sys.argv[1:]
    main(int(a[0]) if a else 0, float(a[1]) if len(a) > 1 else 150)
