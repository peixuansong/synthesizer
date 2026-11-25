"""REFERENCE blackboxes for the plan's big operators (B1-B10) and the chain links that lead to them, as boxes.

Each function is a reference: it says WHAT the net must produce, never how. None of them is placed in the net.
Numbers are whole numbers >= 0. Division or remainder by 0 gives 0.
A link with several outputs returns a tuple. Each box is ops.serial_box(function): numbers in and out as bits.
TICKS gives the tick limit the checker (BOXO) uses, as a function of the bit size; None = not set in the plan yet.
"""
from math import comb, factorial, gcd
from ops import target


def _step_mul(r, a, b):
    return r + (a if b % 2 else 0)


# B1 multiply
def b1_1_slow_mul(a, b):
    """REFERENCE B1.1 slow multiply: a * b (no tick limit)."""
    return a * b


def b1_2_step(r, a, b):
    """REFERENCE B1.2 one step: r + (a if the low bit of b is 1, else 0)."""
    return _step_mul(r, a, b)


def b1_3a_step_double(r, a, b):
    """REFERENCE B1.3a: (B1.2's r, 2a)."""
    return _step_mul(r, a, b), 2 * a


def b1_3b_step_shift(r, a, b):
    """REFERENCE B1.3b: (B1.2's r, 2a, b // 2)."""
    return _step_mul(r, a, b), 2 * a, b // 2


def b1_4_fast_mul(a, b):
    """REFERENCE B1.4 fast multiply: a * b, within bits^2 ticks."""
    return a * b


# B2 divide, B3 remainder
def b2_1_ge(r, b):
    """REFERENCE B2.1: 1 if r >= b, else 0."""
    return int(r >= b)


def b2_2_step(r, b, q):
    """REFERENCE B2.2 one step: with c = (r >= b): (r - (b if c else 0), q + c)."""
    c = int(r >= b)
    return r - (b if c else 0), q + c


def b2_3_slow_div(a, b):
    """REFERENCE B2.3 slow divide: a // b (no tick limit)."""
    return a // b if b else 0


def b2_4_fast_div(a, b):
    """REFERENCE B2.4 fast divide: a // b, within bits^2 ticks."""
    return a // b if b else 0


def b3_mod(a, b):
    """REFERENCE B3 remainder: a mod b."""
    return a % b if b else 0


# The others
def b4_pow(a, b):
    """REFERENCE B4 power: a ** b."""
    return a ** b


def b5_gcd(a, b):
    """REFERENCE B5 gcd: greatest common divisor (gcd(0, 0) = 0)."""
    return gcd(a, b)


def b6_binomial(n, k):
    """REFERENCE B6 binomial: n choose k (0 when k > n)."""
    return comb(n, k)


def b7_root(a, n):
    """REFERENCE B7 n-th root: the largest k with k ** n <= a (n = 0 gives 0)."""
    if n == 0: return 0
    k = int(round(a ** (1 / n)))
    while k ** n > a: k -= 1
    while (k + 1) ** n <= a: k += 1
    return k


def b8_log(a, b):
    """REFERENCE B8 log: the largest k with b ** k <= a (a = 0 or b < 2 gives 0)."""
    if a == 0 or b < 2: return 0
    k = 0
    while b ** (k + 1) <= a: k += 1
    return k


def b9_factorial(n):
    """REFERENCE B9 factorial: n!."""
    return factorial(n)


def b10_digit_sum(a):
    """REFERENCE B10 digit sum: the sum of a's decimal digits."""
    return sum(int(c) for c in str(a))


# name -> (make the box, reference function, needs); needs = earlier targets (targets/rules.md), from the plan
BIG = {
    'B1.1': target(b1_1_slow_mul, 2, ['M2', 'O2']),
    'B1.2': target(b1_2_step, 3, ['O2', 'O10', 'O11']),
    'B1.3a': target(b1_3a_step_double, 3, ['B1.2', 'O8'], 2),
    'B1.3b': target(b1_3b_step_shift, 3, ['B1.3a', 'O9'], 3),
    'B1.4': target(b1_4_fast_mul, 2, ['B1.3b', 'M2']),
    'B2.1': target(b2_1_ge, 2, ['O4']),
    'B2.2': target(b2_2_step, 3, ['B2.1', 'O3', 'O11', 'O2'], 2),
    'B2.3': target(b2_3_slow_div, 2, ['B2.2', 'M2']),
    'B2.4': target(b2_4_fast_div, 2, ['B2.3', 'O8', 'O9']),
    'B3': target(b3_mod, 2, ['B2.4']),
    'B4': target(b4_pow, 2, ['B1.4', 'M2', 'M3']),
    'B5': target(b5_gcd, 2, ['B3', 'M2', 'M3']),
    'B6': target(b6_binomial, 2, ['B9', 'B2.4', 'M3']),
    'B7': target(b7_root, 2, ['B4', 'O4', 'M2', 'M3']),
    'B8': target(b8_log, 2, ['B4', 'O4', 'M2', 'M3']),
    'B9': target(b9_factorial, 1, ['B1.4', 'O2', 'M2', 'M3']),
    'B10': target(b10_digit_sum, 1, ['B3', 'B2.4', 'O2', 'M2', 'M3']),
}
TICKS = {'B1.4': lambda bits: bits * bits, 'B2.4': lambda bits: bits * bits}
