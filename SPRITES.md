# S01 sprite library (JUNGS01.DLL) notes

## Stage ("world", 0xb84 bytes, created by S_026(hwnd, dc))

- Origin is the screen centre: `SetViewportOrg(w/2, h/2)`; `+0x884/+0x886`
  = (w-1)/2, (h-1)/2. Sprite and rect coordinates are centre-relative.
- `+0x862..0x868` visible rect (from screen metrics or the background bitmap),
  `+0x86a..0x870` clip rect (S_056).
- Background: `S_031(rect*, lo, hi)`: (-1,-1) none, (c,0) solid colour c,
  else a far pointer to a bitmap (centred).
- Sprite list `+4` (array of near ptrs, count `+0x87c`), sorted by layer
  `+0x38`. `+6` = topmost "dragged" sprite (S_042 moves it to the end, layer
  0xffff).
- Callbacks: `+0x0c` motion notify (types 0x13/0x14/0x15), `+0x10` per-tick
  hook and type 0x16, `+0x14` image loader (image ids with a zero segment),
  `+0x18` hook run before each sprite update.
- `+0x44c` far pointer to the script variable table (S_052): motion record
  fields < 0x159f are variable refs, >= 0x159f constants (v + 0x7531).
- `+0xa7e` "draw only over non-zero pixels" mode (S_032), `+0xa80` updates
  disabled (S_061), `+0xa81` stretch (S_053 zoom), `+0xa82`.
- Palette: 0x462 PALETTEENTRY[256]; S_037 set all, S_024 copy range in,
  S_021 fade range by num/den (AnimatePalette), S_005 set range.

## Sprite (0x5f bytes)

| off | meaning |
|---|---|
| 0,2 | x, y (centre-relative position) |
| 4..a | bounds l,t,r,b (from image w/h and hot spot) |
| c..12 | previous bounds |
| 14 | u32 next frame time; 1c u32 frame delay (S_041) |
| 18 | u32 next move time; 20 u32 move delay (S_036) |
| 28 | far ptr current image |
| 2c | image cache: 20 x {far ptr, id} for lazily loaded ids |
| 2e | composite cel list (count 4c): 12-byte {far img, rect} |
| 30 | image list: count 40 x {u16 id/off, u16 seg} (seg 0 = id) |
| 32..36 | motion program buffer start / current record / end |
| 38 | layer (sort key) |
| 3a | flip flags: lo byte = h flip, hi byte = v flip |
| 3c | owner (script resource id), 3e user word |
| 44 | current frame, 46 next frame, 48/4a frame range from/to |
| 4e | shown, 4f moved, 50 notify on frame, 51 frame due |
| 53 | forward, 55 animating (range has > 1 frame), 56 drawn |
| 58 | sync timers, 5a, 5b enabled, 5c paused (S_072) |
| 5d/5e | hit-test flags: 5d hit even when hidden, 5e rect-only hit |

Hot spot: left = x + (1-w)/2 + hotx; top = y - ((h-1)/2 - hoty)
(mirrored for flips).

## Motion records (u16 type + args; sizes in 0xbce table)

| type | size | meaning |
|---|---|---|
| 1 | 10 | frame range {from, to, (count), delay}: play frames |
| 2 | 14 | composite cel set: up to 4 image refs + delay |
| 4 | 2 | erase |
| 5 | 30 | quadratic curve move to (x2,y2) via (x1,y1) in n steps |
| 6 | 8 | loop {counter, count, target offset} |
| 7 | 10 | set flips (h, v) |
| 8 | 2 | hide |
| 9 | 22 | linear move to (x,y) over n steps (or speed if flag) |
| 10 | 8 | continuous move by (dx,dy) |
| 11 | 6 | wait n ms |
| 12 | 8 | set position (x,y, relative) |
| 13 | 4 | sync flag |
| 14 | 4 | set move delay |
| 15 | 8 | set frame range |
| 16 | 6 | set frame delay (+ move delay) |
| 17 | 4 | set frame |
| 19/21 | 2/14 | notify player (callback +0x0c) |
| 20 | var | notify with payload |
| 22 | 12 | callback +0x10 (image swap) |

S_069 queues a record (values re-biased by -0x7531 so they are constants),
S_067 applies it now. S_001 = tick: for each enabled, unpaused sprite with a
motion program, run 4b16 (the current record) and advance (45b2) when done.
