"""Target dataset: OEIS sequences (data/oeis/top2000.jsonl, the 2,000 most interesting entries)."""
import os, json
import _setup


def oeis_targets(R=16, W=48):
    """Top-2000 OEIS entries with at least R terms that fit in W-bit two's complement."""
    tops = [json.loads(l) for l in open(os.path.join(_setup.DATA, 'oeis', 'top2000.jsonl'))]
    return [d for d in tops if len(d['terms']) >= R and all(abs(t) < (1 << (W - 1)) for t in d['terms'][:R])]
