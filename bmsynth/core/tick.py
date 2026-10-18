"""One tick of every cell, compiled with numba. One bit (0/1, uint8) per node.

    new[ids[i]] = s[C[i]] XNOR OR_{p in ptr[i]..ptr[i+1]} ( s[A[p]] AND s[B[p]] )
"""
import numpy as np
import numba as nb


@nb.njit(cache=True)
def step_cells(s, new, ids, ptr, A, B, C):
    for i in range(ids.shape[0]):
        acc = np.uint8(0)
        for p in range(ptr[i], ptr[i + 1]):
            acc |= s[A[p]] & s[B[p]]
        new[ids[i]] = np.uint8(1) ^ s[C[i]] ^ acc
