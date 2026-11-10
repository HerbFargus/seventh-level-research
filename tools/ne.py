"""Minimal NE reader: ne.py FILE -> segment table; ne.seg(file, n) returns bytes."""
import struct, sys
def segments(path):
    d = open(path, 'rb').read()
    ne = struct.unpack_from('<H', d, 0x3c)[0]
    cnt = struct.unpack_from('<H', d, ne + 0x1c)[0]
    segtab = ne + struct.unpack_from('<H', d, ne + 0x22)[0]
    shift = struct.unpack_from('<H', d, ne + 0x32)[0]
    out = []
    for i in range(cnt):
        off, size, flags, alloc = struct.unpack_from('<HHHH', d, segtab + i * 8)
        size = size or 0x10000
        out.append((off << shift, size, flags, alloc))
    return d, out
def seg(path, n):
    d, s = segments(path)
    off, size, flags, alloc = s[n - 1]
    return d[off:off + size] if off else bytes(alloc)
if __name__ == '__main__':
    d, s = segments(sys.argv[1])
    for i, x in enumerate(s, 1):
        print(i, hex(x[0]), hex(x[1]), hex(x[2]), 'DATA' if x[2] & 1 else 'CODE')
