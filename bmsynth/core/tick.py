"""One tick of every cell, compiled with numba. Lanes are the bits of uint64 words.

    new[ids[i]] = s[C[i]] XNOR OR_{p in ptr[i]..ptr[i+1]} ( s[A[p]] AND s[B[p]] )
"""
import numpy as np
import numba as nb


@nb.njit(parallel=True, cache=True)
def step_cells(s, new, ids, ptr, A, B, C):
    W = s.shape[1]; n = ids.shape[0]
    for i in nb.prange(n):
        for w in range(W):
            acc = np.uint64(0)
            for p in range(ptr[i], ptr[i + 1]):
                acc |= s[A[p], w] & s[B[p], w]
            new[ids[i], w] = ~(s[C[i], w] ^ acc)
