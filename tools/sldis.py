"""Disassemble 7th Level scripts: sldis.py FILE.BIN [script#...]"""
import struct, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import sl
import slscript as S

EXPR_NAMES = {1: 'imm', 2: 'var', 3: 'idx', 4: 'addr', 5: 'deref', 6: 'idxaddr', 8: 'assign',
              0x0c: 'builtin', 0x0d: 'call', 0x0e: 'neg', 0x0f: 'not', 0x10: 'compl', 0x11: '+', 0x12: '-',
              0x13: '*', 0x14: '/', 0x15: '%', 0x16: '==', 0x17: '<=', 0x18: '<', 0x19: '>=', 0x1a: '>',
              0x1b: '!=', 0x1c: '&&', 0x1d: '||', 0x1e: '&', 0x1f: '|', 0x20: '^', 0x21: '++pre',
              0x22: 'post++', 0x23: '--pre', 0x24: 'post--', 0x25: 'jtrue', 0x26: 'jfalse', 0x27: 'dup'}


def ref(v):
    if v < 0x13FE:
        return 'g%d' % v
    if v < 0x159F:
        return 'l%d' % (v - 0x13FE)
    return '#%d' % ((v + 0x7531) & 0xFFFF if (v + 0x7531) & 0xFFFF < 0x8000 else ((v + 0x7531) & 0xFFFF) - 0x10000)


def expr(b, i):
    out = []
    while b[i]:
        op = S.expr_op(b[i])
        n = S.EXPR_LEN.get(op, 1)
        name = EXPR_NAMES.get(op, 'x%02x' % op)
        if n == 3:
            v = struct.unpack_from('<H', b, i + 1)[0]
            out.append('%s %s' % (name, ref(v) if op in (2, 4) else v if op != 1 else '%d' % struct.unpack_from('<h', b, i + 1)[0]))
        elif n == 5:
            a, c = struct.unpack_from('<HH', b, i + 1)
            out.append('%s(%d,%d)' % (name, a, c))
        else:
            out.append(name)
        i += n
    return '[' + '; '.join(out) + ']'


def dis(b, table):
    S.TABLE = table
    i = 0
    lines = []
    while i < len(b):
        op, n = S.length(b, i)
        if n == 0:
            lines.append('%04x: ?? %04x  %s' % (i, op, b[i:i + 16].hex(' ')))
            break
        words = [struct.unpack_from('<H', b, i + k)[0] for k in range(2, min(n, 20), 2) if i + k + 2 <= len(b)]
        txt = ''
        if op == 0x4c:
            txt = expr(b, i + 4)
        elif op in (0x4d, 0x4f):
            txt = 'else->%04x end->%04x %s' % (i + words[0], i + words[1], expr(b, i + 6))
        elif op == 0x59:
            txt = 'return ' + expr(b, i + 4)
        elif op == 0x25:
            txt = '-> %04x' % ((i + (words[0] if words[0] < 0x8000 else words[0] - 0x10000)) & 0xffff)
        elif op == 0x4e:
            txt = 'switch tbl %04x def %04x n%d %s' % (i + words[1], i + words[2], words[3] & 0xff, expr(b, i + 10))
        elif op == 0x71:
            txt = 'case %d -> +%d' % (words[0], words[1])
        elif op == 0x12 or op == 0x77:
            txt = repr(b[i + 2:i + n].split(b'\0')[0].decode('latin1'))
        else:
            txt = ' '.join(ref(w) for w in words)
        lines.append('%04x: %02x %s' % (i, op, txt))
        i += n
    return lines


if __name__ == '__main__':
    lib = sl.Library(sys.argv[1])
    st = 16 if lib.version >= 0x140 else 14
    table = S.L142 if lib.version >= 0x140 else S.L
    S.V142 = lib.version >= 0x140
    want = [int(x) for x in sys.argv[2:]]
    for k, (t, _, _) in enumerate(lib.index):
        if t != st or (want and k not in want):
            continue
        print('== script %d' % k)
        for l in dis(lib.raw(k), table):
            print('  ' + l)
