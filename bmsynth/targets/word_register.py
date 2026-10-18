"""Target: a 16-bit word register that steps reg <- f(reg) once per clock period, built in the net from the
circuits found for the sequential-circuit targets (targets/behaviours.py): clock = pulse -> delay / inverted delay,
register = the memory bit duplicated W times (boxes/duplicator.py), f = arithmetic boxes on the pulse."""
from behaviours import SPECS

W = 16
GROUP = {sp[0]: gi for gi, sp in enumerate(SPECS)}         # circuit name -> the group tag its library entry carries
TARGETS = {'add3': lambda x: x + 3, 'mul5add1': lambda x: 5 * x + 1}   # the register should step through f(0), f(f(0)), ...
