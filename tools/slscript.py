"""Walk 7th Level script resources with the player's instruction-length table
(JUNGLE.EXE 1008:c298) and count opcodes.  slscript.py FILE.BIN [...]"""
import struct, sys, collections, os
sys.path.insert(0, os.path.dirname(__file__))
import sl

L = {}
for n, ops in {4: [2, 3, 9, 10, 0xb, 0xe, 0x15, 0x1d, 0x1f, 0x23, 0x25, 0x35, 0x40, 0x43, 0x51, 0x5d, 0x60, 0x6a],
               0x12: [4, 0x12, 0x16, 0x17, 0x21],
               8: [5, 0xf, 0x1e, 0x24, 0x27, 0x28, 0x29, 0x2e, 0x34, 0x39, 0x3a, 0x3f, 0x55],
               0xe: [6, 0x11, 0x5c], 10: [7, 0x22, 0x2a, 0x30, 0x3b, 0x3c, 0x46, 0x50, 0x53, 0x58],
               0x1c: [8], 0xc: [0xc, 0x13, 0x18, 0x31, 0x36, 0x37, 0x4b, 0x61],
               2: [0xd, 0x2c, 0x2d, 0x45], 0x18: [0x10],
               6: [0x14, 0x19, 0x1a, 0x1b, 0x1c, 0x20, 0x2f, 0x41, 0x42, 0x44, 0x47, 0x48, 0x49, 0x54, 0x57, 0x5e],
               0x14: [0x32], 0x20: [0x38], 0x10: [0x3d, 0x52, 0x56, 0x77], 0x16: [0x3e]}.items():
    for o in ops:
        L[o] = n


EXPR_LEN = {1: 3, 2: 3, 4: 3, 0x0c: 5, 0x0d: 5, 0x25: 3, 0x26: 3}
EXPR = collections.Counter()


# v0x142 drops expression op 0x0c: its ops from 0x0d are v0x11E's one higher
V142 = False


def expr_op(op):
    return op - 1 if V142 and op >= 0x0d else op


def expr_len(b, i):
    j = i
    while b[j] != 0:
        EXPR[expr_op(b[j])] += 1
        j += EXPR_LEN.get(expr_op(b[j]), 1)
    return j + 1 - i


# format 0x142 (Topsy Turvy, TOPSY.EXE 1008:c956): two new ops, six longer forms
L142 = dict(L)
L142.update({0x8d: 6, 0x8f: 6, 4: 0x14, 0x12: 0x14, 6: 0x10, 0x4b: 0x18, 0x3d: 0x16, 0x77: 0x12})
TABLE = L


def length(b, i):
    L = TABLE
    op = struct.unpack_from('<H', b, i)[0]
    if op == 1:
        return op, (b[i + 5] + 3) * 2
    if op == 0x4c:
        return op, struct.unpack_from('<H', b, i + 2)[0]
    if op in (0x4d, 0x4f):          # if / while: {op, jfalse, jtrue, expr}
        return op, struct.unpack_from('<H', b, i + 4)[0]
    if op == 0x26:                  # compare a b cmp, branch: {op, jfalse, a, b, cmp}
        return op, 10
    if op == 0x2b:                  # switch on var: {op, var, tableoff, default, count}
        return op, 10
    if op == 0x4e:                  # switch on expr: {op, -, tableoff, default, count, expr}
        return op, (10 + expr_len(b, i + 10) + 1) & ~1  # padded to a word
    if op == 0x71:                  # switch table entry {op, value, jump}
        return op, 6
    if op == 0x59:                  # return expr: {op, len, expr}
        return op, struct.unpack_from('<H', b, i + 2)[0]
    return op, L.get(op, 0)


def walk(b):
    i, ops = 0, []
    while i < len(b):
        op, n = length(b, i)
        if n == 0:
            return ops, i, op
        ops.append(op)
        i += n
    return ops, i, None


if __name__ == '__main__':
    total = collections.Counter()
    for f in sys.argv[1:]:
        lib = sl.Library(f)
        st = 16 if lib.version >= 0x140 else 14
        TABLE = L142 if lib.version >= 0x140 else L
        ok = bad = 0
        badops = collections.Counter()
        for k, (t, _, _) in enumerate(lib.index):
            if t != st:
                continue
            ops, end, stop = walk(lib.raw(k))
            total.update(ops)
            if stop is None and end == len(lib.raw(k)):
                ok += 1
            else:
                bad += 1
                badops[stop] += 1
        print('%-14s scripts ok %4d bad %3d %s' % (os.path.basename(f), ok, bad, dict(badops.most_common(5)) if bad else ''))
    print('opcodes used:', len(total))
    print(' '.join('%02x:%d' % kv for kv in sorted(total.items())))
    print('expression ops:', len(EXPR))
    print(' '.join('%02x:%d' % kv for kv in sorted(EXPR.items())))
