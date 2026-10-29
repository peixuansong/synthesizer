"""Part K (notes/targets-4-oeis.md): machine checks. The box writes a fixed LODA program into WORK and runs it on
each n; the net must give the wanted value (or fail, where want is None). Only descriptions, no nets.
The programs are written in LODA and encoded here into instruction words (cpu_targets.py): lpe gets the T of its
lpb (the machine reads the counter through T), `seq $t,k` calls library program k, end is OP 31.
Library ids: 8..21 are kept for the found ops (a found op calls the program with its own OP code); checks use 40..47.
"""
OPS = dict(mov=0, add=1, sub=2, mul=3, div=4, mod=5, min=6, max=7, lpb=22, lpe=23, seq=24)


def encode(text):
    """LODA lines -> instruction words (W = 16: S lanes 0-6, OP 7-11, T 12-14, MD 15)."""
    words, open_ = [], []
    for line in text.strip().splitlines():
        line = line.split(';')[0].strip()
        if not line: continue
        op, _, args = line.partition(' ')
        a = [x.strip() for x in args.split(',')] if args else []
        t = int(a[0][1:]) if a else 0
        if op == 'lpb': open_.append(t)
        if op == 'lpe': t = open_.pop()
        md, s = (0, 0) if len(a) < 2 else (0, int(a[1][1:])) if a[1].startswith('$') else (1, int(a[1]))
        assert -64 <= s < 64 and t < 8, line
        words.append((s & 127) | OPS[op] << 7 | t << 12 | md << 15)
    return words + [31 << 7]


def run(name, prog, cases, lib=None, **k):
    return dict(name=name, kind='run', words=encode(prog), cases=cases,
                lib={i: encode(p) for i, p in (lib or {}).items()}, **k)


fact = lambda n: 1 if n < 2 else n * fact(n - 1)
TARGETS_K = [
    run('K1 add', 'add $0,1', [(n, n + 1) for n in range(4)]),
    run('K2 factorial', '''mov $1,1
        lpb $0
          mul $1,$0
          sub $0,1
        lpe
        mov $0,$1''', [(n, fact(n)) for n in range(6)]),
    run('K3 call', 'seq $0,40', [(n, n) for n in range(3)], lib={40: ''}),
    run('K4 div by 0', 'div $0,0', [(3, None)]),
    run('K5 call depth', 'seq $0,41', [(n, n) for n in range(2)], lib={41: 'seq $0,42', 42: 'seq $0,43', 43: ''}),
    run('K5 too deep', 'seq $0,44', [(1, None)], lib={44: 'seq $0,45', 45: 'seq $0,46', 46: 'seq $0,47', 47: ''}),
    run('K6 two loops', '''lpb $0
          mov $2,$0
          lpb $2
            add $1,$0
            sub $2,1
          lpe
          sub $0,1
        lpe
        mov $0,$1''', [(n, sum(i * i for i in range(n + 1))) for n in range(5)]),
]
