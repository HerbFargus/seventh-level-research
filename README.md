# 7th Level Runtime Player 1.2: research notes

Notes and tools from reverse-engineering 7th Level's "Runtime Player 1.2", which runs **Timon & Pumbaa's Jungle Games** (1995) and **The Hunchback of Notre Dame: Topsy Turvy Games** (1996): the .BIN resource libraries (magic "7L"), the sprites, the script bytecode, and the 16-bit NE executables.

The ScummVM engine built from this work is on the `seventh` branch of the fork: https://github.com/HerbFargus/scummvm/tree/seventh (see SEVENTH.md there).

## Notes

- `NOTES.md`: the formats and the player
- `SPRITES.md`: the sprite format

## Tools

Python 3 unless noted; most need only the standard library.

- `tools/sl.py`: resource library (.BIN, magic "7L") reader
- `tools/sldis.py`: disassemble the scripts
- `tools/slscript.py`: walk script resources with the player's instruction-length table
- `tools/ne.py`: minimal NE executable reader
- `tools/cmpshot.py`: compare engine screenshots against sl.py decodes
- `tools/fn.py`: print functions from a Ghidra DumpNE export

## Ghidra scripts

Headless Ghidra scripts and the batch files that ran them. Set GHIDRA to your Ghidra install; the batch files otherwise look for one beside the project.

- `tools/ghidra/DumpNE.java`

## Not included

No game files, extracted assets, screenshots, or decompiled or disassembled
game code are in this repo. The tools work on your own copy of the game.

## About these notes

The research and the tools were written with an LLM (Claude), working from
the games themselves. They are published as a reference for how the formats
and the engine work. Check anything you rely on against the games.

The matching ScummVM engine on the fork is AI-written too and is not a ScummVM
contribution: ScummVM's AI guidelines do not allow AI-authored submissions.
Anyone writing a real engine should treat this repo as notes, not code to copy.

## Licence

GPL-3.0 (see LICENSE), the same as ScummVM.
