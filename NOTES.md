# 7th Level Runtime Player: M0 survey (2026-10-19)

Goal: a ScummVM engine for the 7th Level "Runtime Player 1.2" games, starting
with the two Disney titles. Upstream
ScummVM has no 7th Level engine (only an old forum thread floating the idea).

## What's on the discs

| Game | Year | Player | Data | Format |
|---|---|---|---|---|
| Timon & Pumbaa's Jungle Games | 1995 | JUNGLE.EXE 116 KB | 13 x `JUNG*.BIN` (60 MB) | `7L` v0x11E |
| Hunchback: Topsy Turvy Games | 1996 | TOPSY.EXE 95 KB | 12 x `TOPS*.BIN` (92 MB) | `7L` v0x142 |
| Jungle Games demo (on the Topsy CD) | 1996 | T&PDEMPC.EXE | 17 x `JUNG*.BIN` incl. `*X` teasers | `7L` v0x142 |

All three players are 16-bit Win16 NE, MSVC, plus four shared DLLs:
`*A01` Audio Library 2.2, `*R01` Resource Library 1.2, `*S01` Sprite
Library 1.2, `*U01` Utils Library 1.2 (maths, SmartHeap). No game-specific
DLLs: every bit of game logic is script in the `.BIN` files.

Ghidra: `re/seventh.rep` (project `seventh`); full decompiles in
`re/<FILE>.c` via `tools/ghidra/DumpNE.java`, single functions with
`tools/fn.py re/JUNGLE.EXE.c 1008:c724`.

## .BIN resource library (CONFIRMED, both versions, 42 files)

```
0x000  u16 '7L' (0x4C37)   u16 version (0x11E / 0x142)   u16 2
...    header fields (screen size, counts; v0x142 has 0x24 more bytes)
0x0B6  8 x {u32 offset, u32 size}   (0x0DA in v0x142)
       [1] resource index: N x {u16 type, u32 offset, u32 size}
       [4] variable table: {u16 id, u16 initial value}
       [5] const strings, NUL separated (INI keys, format strings, names)
       [6] key block: small resources, loaded into memory at open
       [7] palette: 236 x RGBQUAD = system palette entries 10..245
```

Offsets are absolute for big resources and relative to the key block for key
types (8..16 in v0x11E, 10..18 in v0x142, see `RESLOADRESOURCE`).
`tools/sl.py info FILE.BIN` prints all of this.

Resource types (v0x11E numbering; v0x142 shifts the key types by +2):

| type | what | notes |
|---|---|---|
| 1 | bitmap | 20-byte header {hdrsize, w, stride, h, flags, hotx, hoty, id, ptr}, rows bottom-up |
| 4 | MIDI | 7th Level event stream (`RESCREATEMIDIEVENT`), not SMF: still to decode |
| 7 | wave | 28-byte header {u32 size, ?, comp, ?, id, WAVEFORMAT} + IMA ADPCM |
| 14 | script | see below (16 in v0x142) |
| 9,10,11,13,15,16 | small key records | 6-60 bytes: sprite/animation/hit-region tables, still to map |

v0x142 adds type 2 (a 2.6 MB stream, probably music/long audio) and a
reshuffled audio set (types 9/10/17): not decoded yet.

### Bitmap compression (CONFIRMED: every bitmap in all 42 files decodes)

- **Sprite RLE** (flag 0x8000 in v0x11E, 0x0080 in v0x142): u16 row table,
  then per row: `0` = end of row, `<0x80` = run of next byte, `0xFF n` /
  `>=0x80` = literal run of `n` / `~b` bytes. Drawn transparently by the
  sprite library (index 0 = clear).
- **Chunked** (everything else, `R01 1000:218c`): repeated
  `u16 {kind:3, len:13}` chunks until kind 7: 0 = stored, 1 = byte RLE
  (`1000:26b4`), 2/3/4 = LZW with 10/11/12-bit codes (MSB-first, first code
  0x100, end code 2^n-1, no clear code, table freezes when full; each chunk
  is a list of `u16 len` sub-blocks, each a fresh dictionary).

`tools/sl.py check|dump FILE.BIN` validates or writes PNGs;
`m0-contact-sheet.png` has samples from both games. Topsy's large
"outline" bitmaps look like separate ink layers (cel ink over paint):
confirm once compositing works.

### Audio (wave CONFIRMED on Jungle Games)

`A01 1000:3f10` is IMA ADPCM with a precomputed 89 x 8 delta table, low
nibble first, starting at predictor 0 / index 0. Standard IMA decode gives
clean output: no clipping, and every effect ends exactly on 0
(`tools/sl.py`, `dump/wav/`). 22050 Hz 16-bit mono. ScummVM's
`Audio::makeADPCMStream(kADPCMIma)` or a 20-line decoder covers it. The
A01 library also does its own mixing, volume fades and 8/16-bit, mono/stereo
conversion: ScummVM's mixer replaces all of that.

## Scripts (CONFIRMED: 3,321/3,321 Jungle and 8,147/8,152 Topsy walk exactly)

Each script is a flat list of commands `{u16 opcode, operands}`. Operands are
**value refs**: `< 0x13FE` global variable, `0x13FE..0x159E` local (frame
relative), `>= 0x159F` constant (`v + 0x7531`, i.e. biased signed).

- **Command opcodes:** ~100 in the player (`JUNGLE.EXE 1008:c724`, lengths
  in `1008:c298`); 67 used by Jungle Games, 68 by Topsy. v0x142 adds
  0x8D/0x8F and lengthens six forms (`tools/slscript.py` has both tables).
  Commands drive the subsystems: show/hide/move sprites, play
  animations/sounds/MIDI, load scene (`0x12 "jungburp.bin"`), cursor/input
  regions, timers, palette fades, scores and INI save, print.
- **Control flow:** 0x25 jump, 0x26 compare-and-branch, 0x4D if/else and
  0x4F while on expressions, 0x2B/0x4E switch (case bodies inline, table of
  `0x71 {value, jump}` entries at the end), 0x59 return value.
- **Expressions** (`1008:1bf2`, 35 ops, NUL-terminated byte code, stack
  machine): push imm/var/address, array index, assign, ++/--, + - * / %,
  comparisons, & | ^ ~ !, short-circuit && ||, `0x0D` call script procedure
  (with a locals frame), `0x0C` call builtin.
- **Builtins** (`1008:0c52`, 51 in Jungle, 70 in Topsy, ids < 0x8D):
  sprintf/strcmp/strlen/strcpy, sin/cos/angle/sqrt/distance, `COLLIDE`,
  `REFLECTANGLE`, quadrant, key state, sprite queries (`S_0xx`). Ids >= 0x8D
  would go to an external DLL via `EXTERNALCALL`, but no scene names one.
- `RT_001..RT_040` exports are thin wrappers over the same handlers (a plug-in
  API): nothing to port.

So the pinball physics, hippo hopping, bug drop and so on are all script
code over generic maths and sprite primitives. The engine is a VM plus
subsystems, not per-game C.

## Native code still to port

| Piece | Size | Notes |
|---|---|---|
| Interpreter + expression VM | ~100 cmds, 35 expr ops, 70 builtins | handlers average ~30 lines |
| Sprite library (S01) | 80 exports, ~250 KB of decompile | animation sequences, z-order, hit tests, dirty rects: the biggest unknown |
| Resource / decompression | done in Python | port to C++ |
| Audio | IMA done; MIDI event format to do | the MIDI stream is short dwords {status, data} + flagged deltas |
| Input, timers, INI scores, print | small | joystick optional; print can be stubbed |

## Effort estimate

**Light-to-medium, about the same as Big Tuna and well below Nightmare
Ned.** Both are a small generic player running compiled bytecode. Here the
container and compression are already solved, the VM is a regular switch,
and the per-game logic is all data. Rough plan:

1. **M1 resources + display (1 session):** `.BIN` loader, bitmaps, palette,
   detection for both games plus the demo.
2. **M2 VM (2 sessions):** commands, expressions, builtins, variables, scene
   loading; boot the Jungle Games main menu.
3. **M3 sprites + input (1-2 sessions):** S01 semantics, mouse and keys,
   the five Jungle minigames playable.
4. **M4 audio (1 session):** IMA effects plus the MIDI event stream through
   ScummVM's MIDI driver.
5. **M5 Topsy Turvy (1 session):** v0x142 deltas, the new audio types, its
   extra builtins.

About 6-7 sessions in total. Risks: the sprite library is large and
undocumented, and the arcade games need exact timing and integer maths.
The `SlowCpu` and `LoMem` INI keys suggest frame pacing depends on machine
speed. The physics runs in script with integer maths, though, so it should
reproduce exactly once the VM is right.

## Open items

- Types 9/10/11/13/15/16 record layouts (sprite and animation tables).
- MIDI event stream format.
- Topsy audio: type 2 stream and types 10/17.
- R01 has a chunked "CD build" read path (0xFFC blocks + 4-byte link,
  `1000:0984`); no file seen so far uses it.
- One rare v0x142 opcode length (5 Topsy scripts misalign at a 0x4C).
- Other 7th Level titles (Monty Python, Tuneland, Arcade America,
  Battle Beast) may share the player: check for `7L` data files.

## M1 DONE (2026-10-19): engine skeleton

Branch `seventh` (local, not pushed), worktree
`magic-school-bus/scummvm-seventh`, commit c8ba31e204 on upstream 912d1eb98a.
Tooling is in `magic-school-bus/tools-seventh/`: make.sh (run once with
`CONFIGURE=1`, or run configure under MSYS2 by hand if CONFIGURE gets lost),
boot.sh and play.sh `<jungle|demo|topsy>`.

- Detection: `junglegames`, `junglegames` Demo (T&PDEMPC on the Topsy CD) and
  `topsyturvy`, from the CD root (directory globs `jungle`, `topsy`) or the
  game folder.
- `Library` (library.cpp): header, index, key block, variables, strings and
  palette, with the 0x142 key types folded onto the 0x11E numbering.
- `Bitmap` (bitmap.cpp): sprite row RLE and chunked stored/RLE/LZW, with exact
  output length checks.
- Viewer: arrows step through bitmaps, PgUp/PgDn change library. Debugger
  commands `libs open res show strings check`. Hooks `seventh_lib`,
  `seventh_res`, `seventh_shot`, `seventh_check`.

Verified: `seventh_check` decodes all 11,506 Jungle Games bitmaps and all
41,131 on the Topsy CD with 0 failures. Engine screenshots match
`tools/sl.py` pixel for pixel on a full-screen LZW background and two
sprites (`tools/cmpshot.py`, 451,792 pixels, 0 differ).

Open from M1: Topsy's line-art sprites render purple and orange against the
library palette. Either that's how they look, or Topsy switches palettes per
scene (check in M2/M3).

## M2 DONE (2026-10-19): VM, sprite stage, event loop

Commit 0497ad9f60 (+ dd596620fc notes) on `seventh`. Jungle Games boots
logo -> jungint1 -> jungint2 -> jungmain (main menu, ~100 s), and clicking
Hippo Hop starts junghipp. Sprite library notes are in SPRITES.md.

How the player works (JUNGLE.EXE segment 1008):
- Every library is a scene. Opening one runs script resource 0 (the global at
  0x14ea is never written). Scripts always run to completion; nothing blocks.
  Timing comes from timers (op 0x13), sprite motion records (waits, frames)
  and motion callbacks: record 0x14 runs an embedded command, 0x15 calls a
  script, 0x13 runs the post script.
- Event sources: click on an object (record +0 click script, +6/+8 drag/drop,
  +0xe disabled, +0x11 draggable) or a click region; hover objects (builtin
  0x6f) and hover regions (op 0x3d); keys (op 0x0c table: plain, shift, ctrl,
  up; key scripts run at once); timers (run at once); collision watches
  (op 0x21); queued calls (op 0x1e and all events, 40 slots of op-1 records,
  drained each main-loop pass).
- DS layout: globals at 0x151e + 2v. Vars 0-5000 (0x2712 bytes) are per
  library: saved by name on leave, restored on return, otherwise seeded from
  the var table {u16 index, i16 value}. Vars 5001+ (0x3c30..) are shared, and
  the player writes some of them: 5001 click button, 5005/6 mouse, 5007/8
  click, 5009/10 drop, 5017 the sprite that triggered a callback. Locals grow
  down from 0x4058; ref 0x13fe+k = frame - 2k.
- Refs: < 0x13fe global, < 0x159f local, else constant (ref + 0x7531). Const
  string refs are 0x8000 | byte offset into the string table; string
  variables are 1-based, 128 bytes each, count at header 0xa8.
- Calls: op 1 {script, u8 locals, u8 nargs, args}; args become the callee's
  first locals. Expression call 0x0d {locals, nargs} after pushing the id,
  then the args; 0x59 sets the return value and ends the script.
- Builtins (0x0c {unused, argc}): id pushed before the args, result in the
  id slot. Notable: 0x5a do / 0x5b queue a motion record on an object,
  0x2e random, 0x65/0x66 copy/delete an object, 0x69/0x6f key and hover
  filter scripts, 0x86 collide, 0x8a hit test, 0x79-0x7b 4-decimal fixed point.
- Scene change: op 0x12 {name[14], u8 stop sounds, u8 back}; fade out,
  free everything, open, black palette, script 0, fade in unless op 0x0b ran
  during init. Fades scale palette entries 10 .. 10 + header[0xa2].
- Screen mapping: world (0,0) = screen (319,239).

Open for M3+: type-8 movies (the 7th Level logo; stream in type-2
resources, 0x16 motion hook 1008:807c), type-16 text objects (GDI DrawText
with HYENA.TTF / Arial), cursors from JUNGLE.EXE, A01 audio (IMA waves,
MIDI event streams; wave end -> message 0x52c -> queued call), exact U01
maths (GETANGLE, SINE/COSINE, COLLIDE, REFLECTANGLE, DISTANCE), the
fixed-point builtins 0x7a/0x7b (guessed), ops 0x31/0x32/0x3e, text input,
printing, joysticks, and Topsy Turvy (0x142: key types +2, flag 0x0080,
six longer commands, 0x8d/0x8f, new audio types).

## M3 DONE (2026-10-19): movies, text, cursors, U01 maths (7e09b29b9a)

- **Type-8 movie** (1008:7efe, tick 807c, step 7ba0, frame 7912): the key
  record is a program of u16 commands: 1 `{count, (counter), delay}` show
  the next frame chunk, repeating count times; 2 `{delay}`; 3 start
  streamed audio (30 bytes); 4 `{sync}`; 5 an embedded script command
  (its length + 2); 0 ends. Resource+1 is the frame stream and resource+2
  the chunk table of `{u8 type, u8 dropped, u16 size, u32 offset}`. Type 0
  is a full frame, type 1 a droppable frame drawn over the last one
  (bitmap flag 0x200, colour 0 clear, S_019), and type 2 an audio chunk.
  The movie resource's bitmap is the current frame. JUNGLE.BIN res 52 is
  the Disney Interactive logo, which object 86 / motion 87 `{0x16, 52}`
  plays inside the 7th Level frame. S01 4d86 shows the sprite and
  re-centres it on every new frame.
- **Type-16 text** (d662/d7ae/d346): an 18-byte record `{colour, face str,
  text str, height ref, x, y, box w, box h, u8 DT flags}`. Only the height
  is a ref; x, y and the box are raw. DrawText CALCRECT
  (+DT_WORDBREAK when there is a box); the bitmap is (w+1)x(h+1), and
  white text is MAPBYTES'd to the colour on 0. The hot spot follows d25e
  (left: x + (w-1)/2, right: x - w/2, centre: x). VCENTER/BOTTOM need
  SINGLELINE, which is never set. Op 0x29 wsprintf's one int into it; op
  0x5e sets a raw colour. HYENA.TTF is a symbol font (cmap 0xF020..), and
  Arial is used at 18/20/24/30.
- **Cursors** (ecd2): type 1 IDC_ARROW, 2..9 = 0x3e9, 0x3ea, none,
  0x3eb..0x3ef. Op 0x1f takes a raw byte. Types 3/4 also turn off object
  clicks and pair with the mouse-as-joystick mode (72e4).
- **U01 maths**: sine is 901 int16 at DS:0x38, tangent 1801 int32 at
  DS:0x742 (TOPSYU01 has the same tables at 0x2e). GETANGLE(y, x) =
  trunc(atan2(y, x) * 1800/pi), +3600 if negative; callers pass
  (x2-x1, y2-y1), so 0 = +y and 900 = +x. ftol chops. COLLIDE swaps the
  along-line components of equal masses (a1 == 30000: a0 is the line
  angle). Builtins 0x79-0x7b do not rescale: 0x7a stores x*y, 0x7b y/x.
- **Builtin 0x73** = S_075 = S01 1754 (386 code): a quadratic point,
  `(&x, &y, step, steps, x0, y0, xm, ym, x1, y1)`. Op 0x32 (7044) casts a
  ray to a rectangle edge via 6aec, and op 0x3e (6d66) is GETINTERSECT.
- The builtin jump table is at 1008:0c72, indexed by id - 0x1b.

Minigames: all five start. Slingshooter plays (mouse). The others wait on
the **input-device layer** (1008:3f4e-4fde, per-player 0x200-byte blocks
at DS:0x44ba): keyboard sets, joysticks and the mouse (72e4) map to
players; direction codes 1/2/4/8 and buttons queue the player's script
(+0x44c0) through ea92; combo tables at +0x4688 (9-byte entries) and
+0x44c6. It is configured by op 454c and builtin 488e. The pinball intro
runs about 50 s, then Rules, and the ball needs that layer too.

## Input-device layer DONE (2026-10-19, e60f4d9752)

- Two players at DS:0x44ba + p*0x200: +0 a run of codes (a nibble each,
  matched against combos 200 ms after the first; JUNGLE.INI can change
  that), +2 direction, +4 buttons, +6 callback (a script ref), +8/+0xc a
  combo table of 50 (op 0x52), +0xa/+0x1ce one of 4 (op 0x56, used first
  when non-empty). Entries are 9 bytes {code, script, value, mask,
  enabled}: (mask & run) == value fires the script with (player, code).
  +0x1f2 holds a pending combo (op 0x55); +0x1fb device (1 joystick, 2
  keyboard, 5 mouse), +0x1fc remap through DS:0x1c (op 0x57), +0x1ff the
  slot. Slots 1-2 are keyboard sets, 3-4 joysticks, 5 the mouse; the
  owner of each slot is a byte at 0x48cb + slot.
- Codes: 3 up, 5 down, 6 left, 7 right, 9/0xa/0xb/0xc diagonals, 0
  centred; buttons 1/2/4/8 down, ~b up. The callback is queued with
  (player, code) through ea92, except while a text object is being
  edited (0x14de).
- Keyboard sets (DS:0x3c, 6 {vk, code} pairs each; defaults F/V/C/B/1/2
  and arrows/9/0) map into a per-VK table at 0x40ba; held directions
  OR into a mask turned into a code by DS:0x54. Letting go of one of two
  held directions waits 200 ms before sending the other. Builtin 0x6b
  (set, slot, vk) re-keys a set from the options; slot numbers there are
  3 up, 5 down, 7 left, 6 right, 1/2 buttons.
- Mouse mode (72e4): a dead zone of +-20 and a box of +-40 the cursor is
  pulled back into; the direction is DS:0x78 by quadrant of
  (angle + 450). The buttons are 1/2.
- Op 0x53 {player, index, u8 type, u8 off, u8 flush}, op 0x54 callback,
  op 0x58 reads the state back. Builtin 0x89 (player, swap) hands the
  devices over.
- Op 0x36 is name entry: a `_` cursor, a maximum length (0 = 127), an
  optional digits-only flag, Backspace, Enter to accept, Esc to restore.
  The result goes to a string variable and a script is queued.
- In play: the single player of Bug Drop is player 1 on set 1 (Z/C/X/1/2);
  each game shows Rules first (Enter or OK, once the panel has settled).

## Audio DONE (2026-10-20, c7dac1fc69)

- **Ops**: 0x08 play wave {wave, 24-byte A01 block: i16 loops (-1 forever),
  u8 set volume, u8 notify, u8 ?, u8 volume 0-16, i32 fade-in ms, i32
  fade-out ms, i32 min delay, i32 max delay, end script}; 0x0f stop
  {wave or 0, i32 fade}; 0x09/0x0e open/release the device; 0x35 mute
  (-1 toggle); 0x5d volume step {u8 up, u8 device 0 all/1 wave/2 MIDI/3
  CD}; 0x50 play MIDI {midi, loops, u8 notify, u8, end script}; 0x51 stop
  MIDI; 0x5c MIDI control {midi, u8 mutes, u8 tempo, channel mask, mutes,
  ratio den ref, ratio num ref}; builtin 0x70 pause (1) / resume (0).
- **Wave header** byte 5 = 0 means a foreground wave with priority = word
  at +8 (signed; 65535 = -1). One foreground voice at a time: a
  lower-priority one is refused, and a new one stops the others with no
  message (A01 3b46). 618 of Jungle's 628 waves are foreground.
- **End message 0x52c** (wParam script, lParam sound): a script is queued
  with the sound ref; with none, the player unloads the resource. Stops
  never send one. Min/max delay makes an ambient repeat at a random whole
  number of seconds (A01 3938/38f8), again with no message.
- **MIDI resource**: u16 data length, u16 ? (0x8d5f, 0x8e2a: not used), then
  dwords: a short message, or with bits 28-31 set a wait of (e & 0x7fffffff)
  ms, scaled by num/den when op 0x5c set a ratio. A muted channel drops
  note-ons. A01 maps channel 9 to 15 on some drivers (07b2); not ported.
  Hippo Hop's song is 120.6 s, 65 messages/s, and plays at that rate.
- **Movie audio**: command 3 is {3, the 28-byte wave header}; type-2
  chunks are IMA continuing one decoder state. Only Topsy uses it
  (TOPSY.BIN res 65), so it waits for M5.
- Testing: `SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=...` records the mix
  (s16 stereo 44.1 kHz); `music_driver=adlib` puts the MIDI into it.

## Topsy Turvy (0x142) DONE (2026-10-20)

Boots to the menu; all five games start and play (Food Feud, Djali Bowling,
Chiseler, Upsy Daisy, Inside Outwords). Sources: the TOPSYS01 sprite-library
diff (SPRITES.md has the record table) and an EXE diff of every command,
builtin and event handler (agent report, summarised here).

- Menu flow: topsmain opens the GAMES banner itself (call 3066 -> 8658,
  panel stack g2009/g2026). A sign press only selects (8714 sets the mouse
  filter to 8715); the release (filter code 2) runs it. The game's info
  panel then plays a ~51 s narrated preview (motions like 7504, 207 cels)
  whose last record is a type-21 notify running `01 4021`, which launches
  the game through list 56. The menu's attract loop replaces the banner
  after ~10 s idle, so tests click a sign at ~7 s.
- Mouse filter (both versions, 1008:272a / TOPSY 1008:30f4): called with 1
  press, 2 release, 4 move; its result gates the event. A script's result
  is cb06's AX: a `return` value, 0 if a command failed, else non-zero.
  Jungle's dialogs (rules OK etc.) use the same press/release widgets
  (JUNGHIPP 82), which is why mouse OK was unreliable before.
- Key filter result also gates the key. Region clicks pass a constant-0
  ref (0x8acf) first in Topsy, so the region arg is local 1.
- Hippo Hop's rules appear on the first key press, not by themselves.
- 0x9a enables a hidden Ctrl+Shift rubber-band tool; every library turns it
  off. 0x99 = counted MIDI pause; 0x70 goes through the same counter.
- Bitmaps on the disc only use flags 0 and 0x80; the 0x40 top-down flag
  never appears in stored bitmaps.
- Unused by the shipped scripts (not ported): ops 0x3d 0x77 0x8d 0x8f 0x45
  0x27 0x20 0x5e 0x60 0x30 0x46 0x5c 0x52/55-58; builtins 2 3 5 0xa 0xb
  0x8e 0x90-0x98 0x9b 0x9c; op 0x06 transitions 6-10 and alias bitmaps.
- Engine bugs from the Jungle stage still open: startRecord returns true
  for regular records (ticks the next record in the same call), and
  queueMotion(kMotNotify15) allocates 0xe bytes but writes up to six params.
  Fixed now: 0x5a/0x5b/0x83/0x8a failure paths leave the id as the result.
