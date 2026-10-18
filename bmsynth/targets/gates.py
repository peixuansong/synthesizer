"""Targets: the 16 two-input gates, as truth tables. Bit s of the table is the output for x0 = s & 1, x1 = s >> 1."""

GATES = {
    'FALSE': 0b0000, 'AND': 0b1000, 'x0 AND NOT x1': 0b0010, 'x0': 0b1010,
    'NOT x0 AND x1': 0b0100, 'x1': 0b1100, 'XOR': 0b0110, 'OR': 0b1110,
    'NOR': 0b0001, 'XNOR': 0b1001, 'NOT x1': 0b0011, 'x0 OR NOT x1': 0b1011,
    'NOT x0': 0b0101, 'NOT x0 OR x1': 0b1101, 'NAND': 0b0111, 'TRUE': 0b1111,
}
