# The main net: structure, and how it reaches the sequences not yet found

Status: proposal (2026-10-13). Nothing below is built beyond steps 1-4.

## Ground rules
- Cells hold all control: the clock, which candidate to try next, when to call what, compare, stop, rounds, writing to the library.
- Any slow part may be replaced by a Python black box for speed, as long as it is **generic**: the same box serves every target. Arithmetic, a program interpreter, a bus and a compressor are generic. "Is prime", "binomial" or "Tribonacci" written by me would be overfitting and are not allowed. Those must be *found* by the net and stored in its library.
- Outside the net: ticking, loading targets into ports, reading observation ports.

## Blocks of the main net

| Block | What it is | Cells or box |
|---|---|---|
| A. Sequencer | Clock ring and phase gates, as in steps 1-4 | cells |
| B. Candidate generator | A counter over (length, q), so shorter programs come first. This makes the net prefer the shortest description (fixes answers like `(n − n) + n`) | cells |
| C. Program machine | K registers that persist from term to term (so `a(n−1)`, `a(n−2)`, … are just registers). A candidate q is L slots; each slot's bits select an op, two source registers and a destination. Decoders turn q into call wires and mux selects, as in step 4. Sources include n, small constants and every register. A **loop slot** repeats the next slots a register's number of times, with its own counter k available as a source. A **search slot** finds the next m > register for which a stored test program returns non-zero | cells; may be accelerated as one generic interpreter box: `run(q, registers, library) → registers` |
| D. Operation boxes | Generic arithmetic leaves: ADD, SUB, MUL, DIV, MOD, POW, MIN, MAX, LT, EQ, SELECT(c, x, y). Plus **CALL(i, x)**: run library entry i on input x | boxes |
| E. Checker | Target ports, term picked by n, compare, early exit on first mismatch, found latch (step 3/4) | cells |
| F. Library memory | A bank of stored program words. On `found`, the lane's q is written into the next free slot, and CALL can use it from then on | cells, plus a generic **bus** box that copies found programs between lanes, since cells cannot see across lanes |
| G. Round controller | Breadth-first rounds over all targets at once: every lane searches up to a length budget, found programs go into the library, then the budget grows and the next round starts with a richer library | cells |
| H. Fragment miner | Finds sub-programs that recur across stored programs and stores them as new entries with open inputs (holes) | generic compression box |

Observation ports: found, q, library contents, call counts.

Speed: block C+E as one interpreter box is the main acceleration. It runs the whole candidate on all terms with early exit in compiled code, roughly 10^7–10^8 candidate-terms per second instead of one per period of cells. A second generic speed-up is **behaviour pruning**: skip a candidate whose first terms equal an earlier candidate's (the net keeps a hash of seen output vectors). This is generic and shrinks the space a lot.

Other fixes from step 4:
- Load more terms (all known terms that fit in 64 bits) so coincidences like palindromes ≈ n are rejected.
- Feed the OEIS offset in as data, so n starts where the sequence starts.

## How each group of unsolved sequences becomes reachable
Counts are from the earlier failure analysis (1,711 unsolved of the top 2,000).

| Group (count) | What was missing | What in the main net reaches it | Example |
|---|---|---|---|
| Recurrences of order 3–10 (149) | only a(n−1), a(n−2) | K registers that shift each term | Tribonacci: 3 registers, 2 ADDs, length 3 |
| Bigger coefficients (76) | coefficients fixed to small sets | constants come from ops and registers, and short programs make them (2·2+1 …) | a(n) = 5a(n−1) − 6a(n−2) |
| n-dependent coefficients (61) | n only as a direct input | n is a source to every slot, so programs like `a·(4n−2)/(n+1)` are length 4–5 | Catalan, factorials, double factorials |
| Binomial (229) | no second index | the loop slot gives an inner index k; once a binomial program is found it is a library entry that CALL reuses | central binomial, Catalan via binomial |
| gcd (75) | no "repeat until zero" | loop slot plus MOD; gcd is found once and stored | gcd(n, k) families |
| Integer root (65) | no search | search slot: smallest m with m·m > n | ⌊√n⌋ |
| Selection (101) | no "n-th number with property" | search slot with a stored test program. The test is learned first, from an OEIS characteristic sequence, which is itself a target | primes: first learn A010051 (1 if n is prime), then search for the next m where it is 1 |
| Conditionals (60) | no branch | SELECT and LT/EQ boxes | a(n) = n even ? n/2 : 3n+1 |
| Nested loops (53) | one loop level | loop slots can nest; inner programs come from the library | sums of divisors |
| Long programs (158) | fixed two-call shape | CALL to stored entries, plus mined fragments: a long program becomes short over a richer library | many built from already-solved sequences |
| No program, no structure (411) | | some become reachable via digits (DIV/MOD 10 in a loop); many will stay out of reach | |
| Too few terms (179) | | not searchable without more data | |

The OEIS set supplies its own curriculum: simple sequences (characteristic functions, divisor counts, binomials) are targets too, and once found they become library entries for harder ones. None of those entries are written by hand.

## Order of work (each explained before it is built)
1. Register file (K = 3) and variable length up to 3, with the generic interpreter box for speed and behaviour pruning. Expected to reach low-order recurrences (Fibonacci, Tribonacci, Pell, …) and to report shortest forms.
2. More terms and the offset as data.
3. Library memory + CALL + bus + round controller (breadth-first rounds).
4. Loop slot.
5. Search slot (selection, integer root).
6. Fragment miner.
