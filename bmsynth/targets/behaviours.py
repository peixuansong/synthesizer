"""Target dataset: common sequential circuits (square waves, pulses, delay, inverted delay, memory bit, latch).

Each target is only a spec: an input stimulus and the output it should produce, tick by tick.
Generic slack, the same for every spec:
  lag      the output may lag the spec by 0..3 ticks (one variant per lag)
  phase    a periodic spec may start at any phase (one variant per phase)
  warm-up  the first 4 ticks are not judged, so start-up transients are free
"""
import random

T, WARM, LMAX = 64, 4, 3                  # ticks per target stream, unjudged warm-up ticks, largest lag


def periodic(pat): return lambda stim, t: pat[t % len(pat)]
def delayed(f): return lambda stim, t: f(stim[t - 1]) if t >= 1 else None


def sample_hold(stim, t):
    """d as it was on the most recent tick u < t where load (input 1) was 1."""
    for u in range(t - 1, -1, -1):
        if stim[u][1]: return stim[u][0]
    return None


def setreset(stim, t):
    """1 after a set (input 0), 0 after a reset (input 1), held otherwise."""
    for u in range(t - 1, -1, -1):
        if stim[u][0] and not stim[u][1]: return 1
        if stim[u][1] and not stim[u][0]: return 0
    return None


def stimuli(n, seed):
    r = random.Random(seed)
    load = [int(t % 4 == 1) for t in range(n)]
    return dict(none=[[] for _ in range(n)], one=[[r.randint(0, 1)] for _ in range(n)],
                dlh=[[r.randint(0, 1), load[t], 1 - load[t]] for t in range(n)],
                sr=[[int(r.random() < .25), int(r.random() < .25)] for _ in range(n)])


STIM = stimuli(T, 7)
SPECS = [  # file name, title, stimulus, spec(stim, t) -> output wanted at tick t (None = not judged), period
    ('square2', 'square wave, period 2', 'none', periodic([1, 0]), 2),
    ('square4', 'square wave, period 4', 'none', periodic([1, 1, 0, 0]), 4),
    ('pulse3', 'pulse every 3 ticks', 'none', periodic([1, 0, 0]), 3),
    ('pulse4', 'pulse every 4 ticks', 'none', periodic([1, 0, 0, 0]), 4),
    ('delay', 'delay', 'one', delayed(lambda x: x[0]), None),
    ('idelay', 'inverted delay', 'one', delayed(lambda x: 1 - x[0]), None),
    ('memory', 'memory bit (d, load, ¬load)', 'dlh', sample_hold, None),
    ('setreset', 'set/reset latch (s, r)', 'sr', setreset, None),
]


def variants(spec, stim, period):
    """(lag, target bits, care bits): bit r is the output after tick r, i.e. at tick r+1."""
    out = []
    for L in (range(period) if period else range(LMAX + 1)):
        tgt = care = 0
        for r in range(T):
            t = r + 1 - (0 if period else L)
            v = spec(stim, t + (L if period else 0)) if t >= 0 else None
            if v is not None and r >= WARM: care |= 1 << r
            tgt |= int(v or 0) << r
        out.append((L, tgt, care))
    return out
