"""REFERENCE blackboxes for the plan's target sequences (Q): one per OEIS entry in data/oeis/top2000.jsonl.

Each blackbox is a reference: it only plays back the OEIS terms stored in the repo. It does not compute the
sequence and holds no formula or program. No LODA file is read.

    SEQS                  {'A000045': Seq, ...}, all 2,000 entries, in the stored (rank) order
    Seq.a(n)              the stored term a(n); None when n is outside the stored terms
    Seq.fits(bits)        True when every stored term fits in `bits`-bit two's complement
    Seq.box()             the box: boxes/sequence.py sequence_box(terms, offset)
"""
import os, json
import ops                                   # puts bmsynth/ and boxes/ on the import path
from sequence import sequence_box

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'oeis', 'top2000.jsonl')


class Seq:
    """REFERENCE target: one OEIS sequence, as its stored terms only."""
    def __init__(self, d):
        self.name = f"A{d['n']:06d}"
        self.title, self.rank, self.offset, self.terms = d['name'], d['rank'], d['offset'], d['terms']

    def a(self, n):
        i = n - self.offset
        return self.terms[i] if 0 <= i < len(self.terms) else None

    def box(self):
        return sequence_box(self.terms, self.offset)

    def fits(self, bits):
        return all(abs(t) < (1 << (bits - 1)) for t in self.terms)

    def __repr__(self):
        return f"{self.name} ({len(self.terms)} stored terms from n={self.offset}): {self.title[:60]}"


SEQS = {s.name: s for s in (Seq(json.loads(l)) for l in open(DATA))}
