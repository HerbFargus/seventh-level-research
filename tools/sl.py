"""7th Level Runtime Player 1.2 resource library (.BIN, magic '7L') reader.

Usage:
  sl.py info FILE.BIN               header, tables, resource type counts
  sl.py dump FILE.BIN OUTDIR [N]    write the first N (default all) bitmaps as PNG
"""
import os, struct, sys, zlib, collections

TYPE_NAMES = {1: 'bitmap', 4: 'midi', 7: 'wave'}


class Library:
    def __init__(self, path):
        self.path = path
        self.d = d = open(path, 'rb').read()
        magic, self.version, self.fmt = struct.unpack_from('<HHH', d, 0)
        assert magic == 0x4C37, 'not a 7th Level library'
        # Topsy Turvy (0x142) has 0x24 more header bytes before the tables
        new = self.version >= 0x140
        self.shift = 0x24 if new else 0
        # key resources (held in memory, table 6) are types 8..16 in 0x11e, 10..18 in 0x142
        self.key_types = range(10, 19) if new else range(8, 17)
        # flag marking a bitmap stored as row RLE (sprite)
        self.rle_flag = 0x0080 if new else 0x8000
        t = 0xB6 + self.shift
        self.tables = [struct.unpack_from('<II', d, t + i * 8) for i in range(8)]
        ioff, isize = self.tables[1]
        self.index = [struct.unpack_from('<HII', d, ioff + i * 10) for i in range(isize // 10)]
        poff, psize = self.tables[7]
        self.palette = [tuple(d[poff + i * 4:poff + i * 4 + 3]) for i in range(psize // 4)]
        self.key_base = self.tables[6][0]   # types 8..16 live in the in-memory key block

    def raw(self, i):
        t, off, size = self.index[i]
        base = self.key_base if t in self.key_types else 0
        return self.d[base + off:base + off + size]


# ---- decompression (JUNGR01.DLL 1000:218c and friends) ----

def lzw(src, width, outlen_hint=None):
    """MSB-first LZW, codes start at 0x100, end code 2^w-1, no clear code."""
    end = (1 << width) - 1
    maxent = end - 1
    prefix, suffix, first = {}, {}, {}
    pos, bitbuf, bits = 0, 0, 0

    def code():
        nonlocal pos, bitbuf, bits
        while bits < width:
            bitbuf = (bitbuf << 8) | src[pos]
            pos += 1
            bits += 8
        bits -= width
        c = (bitbuf >> bits) & end
        bitbuf &= (1 << bits) - 1
        return c

    def string(c):
        out = bytearray()
        while c >= 0x100:
            out.append(suffix[c])
            c = prefix[c]
        out.append(c)
        out.reverse()
        return out

    out = bytearray()
    prev = code()
    out.append(prev)
    nxt = 0x100
    while True:
        c = code()
        if c == end:
            return out
        if c < nxt:
            s = string(c)
        else:
            s = string(prev)
            s.append(s[0])
        out += s
        if nxt <= maxent:
            prefix[nxt], suffix[nxt] = prev, s[0]
            nxt += 1
        prev = c


def rle(src):
    out = bytearray()
    i = 0
    while i < len(src):
        b = src[i]; i += 1
        if b == 0:
            v = struct.unpack_from('<h', src, i)[0]; i += 2
            if v < 0:
                n = -v; out += src[i:i + n]; i += n
            else:
                out += bytes([src[i]]) * v; i += 1
        elif b < 0xC9:
            out += bytes([src[i]]) * b; i += 1
        else:
            n = b - 0xC8; out += src[i:i + n]; i += n
    return out


def decompress(src):
    out = bytearray()
    i = 0
    while True:
        h = struct.unpack_from('<H', src, i)[0]; i += 2
        kind, n = h & 0xE000, h & 0x1FFF
        chunk = src[i:i + n]; i += n
        if kind == 0xE000:
            return bytes(out)
        if kind == 0:
            out += chunk
        elif kind == 0x2000:
            out += rle(chunk)
        elif kind in (0x4000, 0x6000, 0x8000):
            width = {0x4000: 10, 0x6000: 11, 0x8000: 12}[kind]
            j = 0
            while j < n:
                sl = struct.unpack_from('<H', chunk, j)[0]
                out += lzw(chunk[j + 2:j + 2 + sl], width)
                j += 2 + sl
        else:
            raise ValueError('bad chunk %04x' % h)


def sprite_rle(data, width, stride, height):
    """Row RLE used by bitmaps with flag 0x8000 (JUNGR01 1000:0230)."""
    out = bytearray(stride * height)
    i = height * 2          # skip the row offset table
    o = 0
    row = 0
    while row < height:
        start = row * stride
        o = start
        while True:
            b = data[i]; i += 1
            if b == 0:
                break
            if b < 0x80:
                v = data[i]; i += 1
                out[o:o + b] = bytes([v]) * b; o += b
            else:
                n = b ^ 0xFF
                if b == 0xFF:
                    n = data[i]; i += 1
                out[o:o + n] = data[i:i + n]; i += n; o += n
        row += 1
        if i >= len(data) or data[i] == 0 and row >= height:
            break
    return bytes(out)


def bitmap(raw, rle_flag=0x8000):
    hsize, width, stride, height, flags, hx, hy = struct.unpack_from('<HHHHHhh', raw, 0)
    body = raw[hsize:]
    if flags & rle_flag:
        pix = sprite_rle(body, width, stride, height)
    else:
        pix = decompress(body)
    return dict(width=width, stride=stride, height=height, flags=flags, hot=(hx, hy), pixels=pix)


def write_png(path, w, h, rows_rgb):
    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    raw = b''.join(b'\0' + r for r in rows_rgb)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')
    open(path, 'wb').write(png)


def save_bitmap(lib, bm, path):
    # library palettes hold the 236 non-system colours: index 10..245
    pal = [(0, 0, 0)] * 256
    for k, c in enumerate(lib.palette):
        pal[10 + k] = c
    pal[0] = (255, 0, 255)
    w, s, h, px = bm['width'], bm['stride'], bm['height'], bm['pixels']
    rows = []
    for y in range(h - 1, -1, -1):   # DIB rows are bottom-up
        r = px[y * s:y * s + w]
        rows.append(b''.join(bytes(pal[p]) for p in r))
    write_png(path, w, h, rows)


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    lib = Library(path)
    if cmd == 'info':
        print('version %#x fmt %d shift %#x' % (lib.version, lib.fmt, lib.shift))
        for i, (o, s) in enumerate(lib.tables):
            print('  table %d: off %#x size %#x' % (i, o, s))
        c = collections.Counter(t for t, _, _ in lib.index)
        print('  resources:', len(lib.index), dict(sorted(c.items())))
        print('  palette entries:', len(lib.palette))
    elif cmd == 'check':
        bad = 0
        for i, (t, _, _) in enumerate(lib.index):
            if t != 1:
                continue
            try:
                bm = bitmap(lib.raw(i), lib.rle_flag)
                if len(bm['pixels']) != bm['stride'] * bm['height']:
                    bad += 1; print('  res %d: %d bytes, want %d' % (i, len(bm['pixels']), bm['stride'] * bm['height']))
            except Exception as e:
                bad += 1; print('  res %d: %r' % (i, e))
        print('%s: %d bad' % (os.path.basename(path), bad))
    elif cmd == 'dump':
        out = sys.argv[3]
        lim = int(sys.argv[4]) if len(sys.argv) > 4 else 1 << 30
        os.makedirs(out, exist_ok=True)
        n = 0
        for i, (t, _, _) in enumerate(lib.index):
            if t != 1:
                continue
            try:
                bm = bitmap(lib.raw(i), lib.rle_flag)
                save_bitmap(lib, bm, os.path.join(out, '%04d_%dx%d.png' % (i, bm['width'], bm['height'])))
            except Exception as e:
                print('res %d: %s' % (i, e))
            n += 1
            if n >= lim:
                break
        print('wrote', n)


if __name__ == '__main__':
    main()


# ---- audio (JUNGA01.DLL 1000:3f10: IMA ADPCM via a precomputed 89x8 delta table) ----

IMA_STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66,
            73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449,
            494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272,
            2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493,
            10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767]
IMA_INDEX = [-1, -1, -1, -1, 2, 4, 6, 8]


def ima_decode(data):
    out = bytearray()
    pred, idx = 0, 0
    for b in data:
        for n in (b & 0xF, b >> 4):
            step = IMA_STEP[idx]
            diff = step >> 3
            if n & 4: diff += step
            if n & 2: diff += step >> 1
            if n & 1: diff += step >> 2
            pred = max(-32768, min(32767, pred - diff if n & 8 else pred + diff))
            idx = max(0, min(88, idx + IMA_INDEX[n & 7]))
            out += struct.pack('<h', pred)
    return bytes(out)


def wave(raw):
    size, _, comp, _, rid = struct.unpack_from('<IHHHH', raw, 0)
    tag, ch, rate, bps, align, bits = struct.unpack_from('<HHIIHH', raw, 12)
    return dict(id=rid, comp=comp, channels=ch, rate=rate, bits=bits, data=raw[28:28 + size])


def write_wav(path, ch, rate, pcm16):
    hdr = struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', 36 + len(pcm16), b'WAVE', b'fmt ', 16, 1, ch, rate,
                      rate * ch * 2, ch * 2, 16, b'data', len(pcm16))
    open(path, 'wb').write(hdr + pcm16)
