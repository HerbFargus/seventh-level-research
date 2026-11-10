"""Compare engine viewer screenshots against tools/sl.py decodes, pixel for pixel."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import sl
from PIL import Image
# Usage: cmpshot.py GAMES_DIR SHOTS_DIR
G = os.path.join(sys.argv[1], '')
S = os.path.join(sys.argv[2], '')
SYS = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
       (192, 220, 192), (166, 202, 240), (255, 251, 240), (160, 160, 164), (128, 128, 128), (255, 0, 0), (0, 255, 0),
       (255, 255, 0), (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)]
for f, res, shot in [('Timon and Pumbaa/JUNGLE/JUNGPINB.BIN', 46, 'pinb46'),
                     ('Topsy Turvy/TOPSY/TOPSMAIN.BIN', 6815, 'topsmain6815'),
                     ('Timon and Pumbaa/JUNGLE/JUNGHIPP.BIN', 53, 'hipp53')]:
    lib = sl.Library(G + f)
    bm = sl.bitmap(lib.raw(res), lib.rle_flag)
    pal = [(0, 0, 0)] * 256
    for i in range(10):
        pal[i], pal[246 + i] = SYS[i], SYS[10 + i]
    for k, c in enumerate(lib.palette[:236]):
        pal[10 + k] = c
    w, h, s, px = bm['width'], bm['height'], bm['stride'], bm['pixels']
    x0, y0 = max(0, (640 - w) // 2), max(0, (480 - h) // 2)
    img = Image.open(S + shot + '.png').convert('RGB').load()
    diff = n = 0
    for y in range(min(h, 468 - y0)):
        row = px[(h - 1 - y) * s:(h - 1 - y) * s + w]
        for x in range(min(w, 640 - x0)):
            n += 1
            diff += img[x0 + x, y0 + y] != pal[row[x]]
    print('%-14s %dx%d  %d pixels compared, %d differ' % (shot, w, h, n, diff))
