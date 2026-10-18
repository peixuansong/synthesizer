"""Path setup shared by the experiments: core/, accel/, boxes/ and targets/ on the import path, result and data folders."""
import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
for p in ('core', 'accel', 'boxes', 'targets'):
    if os.path.join(ROOT, p) not in sys.path: sys.path.insert(0, os.path.join(ROOT, p))
RES = os.path.join(ROOT, 'experiments', 'results')
DATA = os.path.join(ROOT, 'data')
res = lambda name: os.path.join(RES, name)

