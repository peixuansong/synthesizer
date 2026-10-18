# Plan: Binary Matrix Net (BMN) and an embedded learner

Planning only. Nothing in the Synthesizer folder has been changed.

## 1. What plan.rst and the code tell us

- plan.rst's next rung is single gates (AND, NOT, XOR, NAND) via a **grid search synthesizer built from cells**: a ripple counter enumerates `x * (z + W)` combinations and a comparator checks Y against the truth table. Later rungs want dynamic nets (birth/death/rewire), sequential logic, and eventually synthesizers that synthesize synthesizers.
- `Cell.__call__` (cell.py) computes `y = (z == any(x AND w))`. So with `z=1` a cell is a **masked OR**, with `z=0` a **masked NOR**. NOR is universal, so every cell is already a row of a boolean (OR-of-ANDs) matrix product.
- `Net.__call__` is synchronous: every axon copies last step's `y` into a port, then every cell fires. That is exactly `s(t+1) = F(s(t))`, i.e. one matrix step per tick. Recurrent nets (clock, SR flip-flop, ripple counter) are just repeated steps.
- Axons can drive `w` and `z`, not only `x` (sr_flip_flop wires Q into a `w` port; test_sgd drives weights from SGD cells). So weights are ordinary state, which is what lets a learner live inside the net.
- Found while reading: cell.py does not currently import. Line 14 has a stray `if type == 'x': return val + 1` and the `port()` helper that common.py and blackbox.py import is gone. Step 0 below restores it.

## 2. The representation: gather-AND-OR-XNOR over a bit state

State: a vector `s` of N bits, one per cell output, plus two constant nodes `s[0]=0`, `s[1]=1`, plus input nodes.

A whole net is three integer arrays (fan-in K = max slots per cell):

```
A : N x K   index of the node feeding x-slot k of cell i
B : N x K   index of the node feeding w-slot k of cell i   (constant w=1 -> index 1, w=0 -> index 0)
C : N       index of the node feeding z of cell i           (constant z -> index 0 or 1)

y_i = s[C_i]  XNOR  OR_k ( s[A_ik] AND s[B_ik] )
```

This is an exact re-encoding of Cell/Net: a constant weight is a pointer to node 1/0, a wired weight is a pointer to another cell, an unused slot points at node 0. It is "matrix multiplication-like" because when every B is constant it collapses to the boolean product `y = NOT^z (M ⊗ s)` with M a 0/1 adjacency matrix.

Compression: dense M costs N² bits; the gather form costs about `N·(2K+1)·log2 N` bits, which is far smaller for the sparse, low-fan-in nets this project builds. A net becomes three small arrays that are trivial to hash, mutate, diff and compare (useful later for plan.rst's similarity/redundancy pruner).

Speed, via bit-slicing: store each node as a `uint64` word whose 64 bits are 64 independent **lanes**. One step is

```
y = s[C] ^ ~bitwise_or.reduce(s[A] & s[B], axis=1)      # numpy, fully vectorized
```

Lanes can be (a) all 2^n rows of a truth table, so a 6-input function is checked in one step, or (b) 64 different candidate nets/weight settings, so a search evaluates a population per step. Expected cost is N·K word ops per step versus the current Python loop over axons and cells; I'll measure the speedup rather than promise a number. numba/CUDA is an optional later step, not part of this plan.

Two caveats I'll handle explicitly: axons that copy from an x/w/z port instead of a y port (only test_sgd does this) get compiled into an extra node; SGDCell is not a gate, so it is either expanded into gates (that is the README's "Synthesize an SGD cell" milestone) or kept as a native special node at first.

## 3. Embedding a learner inside the matrix

Principle: the learning algorithm is itself cells in the same A/B/C arrays, not Python outside it. Weight bits are latch cells; the learner sub-circuit writes to them through the wired-`w` mechanism the code already supports. Training is then just running the net while (input, target) bits are streamed onto input nodes. This is the closure plan.rst asks for: the synthesizer runs on the same substrate as what it synthesizes.

Layout of the state vector:

```
[ const | inputs x, target t | weight latches | model cells | learner cells | (later) LFSR / counter ]
```

Two learners, in increasing difficulty:

**L1, elimination rule (single cell, provably convergent).** A z=0 cell is NOR over masked literals, i.e. an AND of negated literals. Feed both x_j and NOT x_j as literals. Start with all weights 1; on every positive example (t=1) where the cell is wrong, clear each weight whose literal is 1: `w_j' = w_j AND NOT(err AND lit_j)`. This is Valiant's conjunction-learning rule, it is a few gates per weight, and it is the same shape as SGDCell's `if x and f and y != t` rule. With z selectable it covers AND, NAND, OR, NOR, NOT, repeater, nullifier.

**L2, in-circuit stochastic flip search (multi-cell, for XOR).** XOR needs two layers, and a local bit-flip rule has no credit assignment (claude_plan.rst flags exactly this). So the learner is plan.rst's grid-search idea built from cells: an LFSR (or the existing ripple counter, for exhaustive enumeration) picks a weight bit to flip; the model is evaluated on all 4 truth-table rows in parallel lanes; a popcount-and-comparator block compares error to the stored best; a latch keeps the flip or reverts it. Every block is gates, so it compiles to A/B/C rows.

Development order for each learner: write it first as a short numpy routine acting on the BMN arrays (fast to debug), confirm it learns, then build the gate-level version from cells and check it reproduces the numpy version bit-for-bit. Only the gate-level version counts as "embedded".

Baseline for comparison (optional, small): a differentiable relaxation (soft OR `1 - prod(1 - w·x)`) trained with PyTorch and then binarized, reusing plastic_net.py's setup. This tells us whether the in-circuit learners are competitive.

## 4. Toy tasks and what success looks like

- T1: learn each 2-input gate (AND, OR, NAND, NOR, NOT) with L1 inside one net. Pass = correct on the full truth table, over 20 random seeds/orderings.
- T2: learn XOR with a 2-layer, 3-cell model and the L2 learner inside the net. Report success rate and ticks-to-solve over seeds.
- T3 (stretch): one net learns any of the 16 2-input functions, chosen only by the target stream.
- Speed: patterns × cells per second for the BMN vs the current `Net.__call__` on ripple_counter.

## 5. Steps

0. Restore `port()` in cell.py and delete the stray line so the existing code imports.
1. `bmn.py`: BMN arrays, `step`, `run`, bit-sliced truth-table eval, lane populations.
2. `compile_net(Net) -> BMN` and `to_net(BMN) -> Net` (so visualizer.py still draws them).
3. Equivalence tests: clock, sr_flip_flop, ripple_counter, the AND/OR nets in test_sgd.py, stepped side by side for many ticks with identical states.
4. Benchmark the speedup.
5. L1 in numpy, then as cells; run T1.
6. L2 in numpy, then as cells (LFSR, popcount, comparator, keep/revert latch); run T2.
7. Optional: differentiable baseline; T3.
8. Tick the "AND, NOT, XOR, NAND" README milestone if T1 and T2 pass.

New files only (bmn.py, learners.py, test_bmn.py), plus the one-line repair to cell.py. Existing classes keep working.

## 6. Decisions I picked (say if you want otherwise)

- Gather form (A/B/C) as the primary representation, dense matrix only as a derived fast path.
- numpy + uint64 bit-slicing; no CUDA yet.
- Weights live inside the net as latch cells, learners are gates; Python learners are only scaffolding.
