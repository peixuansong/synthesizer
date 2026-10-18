# How the structures get discovered instead of designed

Status: proposal (2026-10-13). Replaces the "blocks" part of main-net.md: there, registers, loop slots, search slots and CALL were picked by me.

## The point
Every structure in main-net.md is already a small circuit:

| My designed structure | As a circuit |
|---|---|
| register a(n−1) | a feedback edge through a delay (a latch cell per bit) |
| higher-order recurrence | a chain of delays |
| counter n | a delay whose input is its own output + 1 |
| loop slot / fold | the step 1 net: an accumulator fed back through a call (acc ← f(acc, k)) with its own counter |
| search slot | the step 4 net: a counter, a call, a compare, a found latch, with the thing being tested left as an open port |
| CALL | a paste signal: instantiate a stored entry where it is needed (the dictionary rule from the first project) |

So no slot machine is needed. The search should be over **wirings of dictionary entries, feedback allowed**. Registers, loops and searches then appear as patterns in found wirings, and the ones that recur are stored as entries.

## What is seeded (written by me), stated plainly
1. The cell rule.
2. The generic black boxes, for speed only: word ADD, SUB, MUL, DIV, MOD, compare. (Later these could be replaced by the cell circuits the gate steps already found.)
3. One seed searcher: the step 4 walker, generalized from "walk an 11-bit q" to "walk wirings in order of description length". It is a circuit and is itself stored as a dictionary entry.
4. The paste signal (instantiate an entry with its ports wired).
5. The targets: OEIS sequences plus small behaviour targets (below), and the cost order (shortest description first).

Everything else is found.

## How each kind of structure is found

1. **From cells, as behaviour targets.** The gate-level grid search already finds small circuits from a truth table. The same search, given a behaviour over time instead of a table, finds a 1-bit delay (out(t+1) = in(t)), a toggle, a counter bit (carry in, carry out) and a phase ring. These are targets in a curriculum, not things I wire.
2. **Lifting to words.** A found 1-bit circuit is pasted W times side by side with the carry ports chained. That gives a word delay and a word counter. The replicate step is a generic paste pattern, the same for any 1-bit entry.
3. **From targets, by wiring search.** The seed searcher wires entries (delay, counter, ADD, MUL, constants, found sequences) into small graphs, feedback allowed, and checks the output against each target. Fibonacci is two delays and one ADD in a loop. Tribonacci is three delays and two ADDs. Nobody designed "K registers"; the search used as many delays as the target needed.
4. **By compression.** After a round, sub-graphs that recur across solutions are cut out with their open edges as ports and stored. Examples that should appear: "delay chain of length k", "accumulator" (the fold), "counter + compare + latch" (the search). That is how a loop slot or search slot would come about: as a recurring fragment of solutions, not as a block I add.
5. **The searcher as an entry.** Because the seed searcher is itself a stored circuit with an open "test" port, a wiring may paste it inside a candidate. That is a search inside a search: "the next m whose test is true", which covers primes, integer roots and other selection sequences. Like any other entry, it is used only when the wiring search finds that it helps.

## Order of work (each explained before it is built)
1. Behaviour targets over time from cells: find delay, toggle, counter bit and phase ring with the existing grid search, and store them.
2. Lift them to 16-bit words by replication, and store.
3. Generalize the step 4 walker to walk small wirings (up to ~5 entries, feedback allowed), shortest first, using a generic graph-evaluator black box for speed. Run it on the top-2000 targets and show which delay/loop patterns it used.
4. Compression: cut recurring sub-graphs out of the solutions and store them as entries; next round.
5. Make the searcher pasteable inside candidates.

The open question for you: is the seed searcher (item 3 in "What is seeded") acceptable as the one hand-built search circuit? The alternative is to bootstrap it too, by having the net search for a better searcher, which is the last rung of the ladder in the README.
