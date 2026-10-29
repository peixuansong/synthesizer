"""Watch the main net: build the seed as main.py does, run net() for at most `seconds`, and only look.
It prints the target box's record (what passed, tries, ticks) and how each made cell is wired.
Run:  python3 experiments/watch.py [seconds]
"""
import sys, time
import _setup
from cell import Cell
import main


def names(play, net):
    """The name of each placed cell: 'ADD.3' for lane 3 of row ADD, 'T' for a spine cell."""
    m = {0: '0'}
    made = {r['name']: (r['addr'], r['kind']) for r in play.log if r['kind'] in ('cell', 'row')}
    for name, (a, kind) in list(made.items()) + list(play.place.items()):
        if a is None: continue
        if kind == 'row': m.update({a + k: f'{name}.{k}' for k in range(play.W)})
        else: m[a] = name
    ix = {id(c): i for i, c in enumerate(net.cells)}
    return lambda c: m.get(ix.get(id(c)), f'#{ix.get(id(c))}')


def rule(c, nm):
    z = nm(c.z) if isinstance(c.z, Cell) else c.z
    if isinstance(c.z, Cell) and c.z.terms and nm(c.z).startswith('#'):
        z = 'OR(' + ', '.join(nm(t[0]) for t in c.z.terms) + ')'
    terms = ', '.join('.'.join(nm(x) for x in t) for t in c.terms) or '-'
    return f"y' = {z} XNOR OR({terms})"


def run(seconds=170):
    t0 = time.time()
    net = main.seed()
    play = net.nets[0].f
    print(f'seed: {len(net.cells)} cells in the net, box: {len(net.nets[0].cells)} port cells, '
          f'{len(play.targets)} targets, W = {play.W}', flush=True)
    seen = [0]

    def look(net):
        for r in play.log[seen[0]:]:
            print(f"  {time.time() - t0:6.1f} s  {r['name']:<10} {r['kind']:<5} {'pass' if r['ok'] else 'FAIL'}"
                  f"  tries {r['tries']:<5} ticks {r['ticks']}", flush=True)
        seen[0] = len(play.log)
        return play.done

    net(seconds=seconds, observe=look)
    look(net)
    took = time.time() - t0
    print(f'ran {net.ticks} ticks in {took:.1f} s ({net.ticks / took:,.0f} ticks/s); net now {len(net.cells)} cells;'
          f" {sum(r['ok'] for r in play.log)}/{len(play.log)} passed of {len(play.targets)}")
    for name, n, want, st, got, steps in getattr(play, 'trace', []):
        print(f"  run {name:<14} n={n:<3} want {want}  got {got}  {['running', 'halted', 'failed'][min(st, 2)]}"
              f" after {steps} clocks")
    nm = names(play, net)
    for r in play.log:
        if r['kind'] in ('cell', 'row') and r['ok']:
            a = r['addr']
            c = net.cells[a + (1 if r['kind'] == 'row' and play.W > 1 else 0)]
            print(f"  {r['name']:<6} at {a:<5} {'lane 1: ' if r['kind'] == 'row' else ''}{rule(c, nm)}")


if __name__ == '__main__':
    run(float(sys.argv[1]) if len(sys.argv) > 1 else 170)
