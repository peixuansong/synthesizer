# Net-driven synthesis: plan (awaiting PEIXUAN's go per step)

Rule: the run starts in the net and ends in the net. Outside the net there is only
(a) the tick, (b) loading a target into input ports, (c) reading observation ports.
Python functions are leaf black boxes the net calls (word ops, evaluation). They need no
cell twin in the dictionary; it is enough that they could in principle be cells.
What must live in the net is the orchestration: which candidate to try, calling the
black boxes, comparing to the target, stopping, and adding solutions to the library.

## Step 1: the black-box node (simplest possible)
- A node with input wires (one w-bit word per argument), output wires, and one `call` wire.
- On a tick where `call` is 1, the wrapper reads the input bits, runs the Python function,
  and writes the result onto the output wires. Otherwise the outputs hold.
- No cell twin is built or checked.
- Demo: a tiny net whose own cell counter calls a Python ADD black box every tick and feeds
  the result back into cells. Python only reads one observation port.

## Step 2: the net calls a chain of black boxes
- Same counter, now driving MUL then ADD (n*n+1), with call wires sequenced by cells.

## Step 3: the net checks a target by itself
- Target terms loaded into input ports; mismatch and "found" latches are cells.

## Step 4: the net walks candidates by itself
- A cell counter picks which black box to call and with which inputs. The net stops
  when the found latch sets. This is the old search, with the search loop in cells.

Later steps (library entries with ports, searcher as an entry, sub-circuit mining)
are re-planned only after step 4 works.

## Where the existing Python scripts go
| Script | Role now | Becomes |
|---|---|---|
| fetch_*.py | downloads targets | stays outside: it only fills input ports |
| bfs.py search loop | Python loop over templates | cells: counter + select (step 4) |
| bfs.py word ops (ADD, MUL, DIV, ...) | Python ints | black boxes, each with its dictionary twin |
| check() | Python compare | cells: mismatch + found latches (step 3) |
| loda.py interpreter | feasibility check only | not used by the synthesizer |
| rank.py, failures.py, examples.py | reports | observation side only, read from ports |
