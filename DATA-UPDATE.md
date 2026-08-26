# eu5ref — Europa Universalis V reference files

Local mirror of EU5's script/data files for data mining, wiki-style extraction, and decompilation. Created 2026-08-25 from the Steam install at
`C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V`.

## What's here

| Folder | What it is |
|---|---|
| `game\in_game\common\` | **The core.** ~124 subfolders of gameplay script: advances, buildings, casus_belli, cultures, religions, estates, disasters, trade goods, defines, etc. Nearly every rule and number in the game lives here as plain text. |
| `game\in_game\events\` | All event files. |
| `game\in_game\map_data\` | `definitions.txt`, `adjacencies.csv`, plus `locations.png` / `rivers.png` — map pixel colors → location IDs via definitions. |
| `game\in_game\setup\` | Starting-world data (countries, characters, diplomacy at 1337 start). |
| `game\in_game\gui\` | UI definitions — often reveal mechanics not documented elsewhere. |
| `game\main_menu\localization\english\` | All English text (~528 files). Other languages were excluded. |
| `game\dlc\` | DLC script content (Fate of the Phoenix, Ancient Monuments, Sacred Sites), art/music stripped. |
| `jomini\`, `clausewitz\` | Engine-layer script defaults (triggers/effects/script system). Modding reference. |
| `binaries\` | `eu5.exe` + Paradox's `PDXSDK.dll` / `pdx_red_king.dll` for decompilation, and `checksum.txt` (game version). Other DLLs in the install are third-party middleware (DLSS, nvtt, Steam) — nothing to mine. |
| `tools\` | Cloned repos, see below. |

**Excluded from the mirror:** `gfx` (~9.7 GB), fonts, music, sound, `content_source` (vegetation masks), non-English localization. If you need other art, pull the specific `gfx` subfolder from the Steam install directly.

**Exception — icon art (added 2026-08-25):** `game\main_menu\gfx\interface\` (icons, advances, illustrations, etc.), `game\main_menu\gfx\coat_of_arms\`, and each DLC's `main_menu\gfx\interface\` ARE mirrored (~1.8 GB) — the reference-site session on the Mac needs them (see ART-EXTRACTION.md if present). The update bat keeps them in sync with their own `/MIR` passes.

## Tools (cloned repos)

- `tools\jomini-parser` — [rakaly/jomini](https://github.com/rakaly/jomini). Rust parser for the Paradox/Clausewitz text and binary formats. Use for programmatic parsing.
- `tools\PyHelpersForPDXWikis` — [grotaclas/PyHelpersForPDXWikis](https://github.com/grotaclas/PyHelpersForPDXWikis). Python scripts the Paradox wikis use to generate tables from game files. Best head start for structured extraction.
- `tools\pdx-tools` — [pdx-tools/pdx-tools](https://github.com/pdx-tools/pdx-tools). Full save-file toolchain (parsing, melting binary saves to plaintext). The `crates/` dir is the best reference for binary format decoding.

All three are shallow clones (`--depth 1`); `git pull` in each to update.

## Updating after a game patch

Run `update-eu5ref.bat` (double-click). It robocopy-`/MIR`s the three script trees with the same exclusions and re-copies the binaries. Note `/MIR` deletes local files a patch removed — this folder should stay a clean mirror, so don't put your own notes/scripts inside `game\`, `jomini\`, `clausewitz\`, or `binaries\`. Root level and `tools\` are safe.

Current game version: see `binaries\checksum.txt`.

## Notes for Claude

- The file format is Paradox script (Jomini). It looks like `key = { ... }`; not JSON, not YAML. Localization files ARE a YAML dialect (`l_english:` keys, `.yml`).
- Gameplay *numbers* are almost all in `game\in_game\common\` — grep there before reaching for the exe.
- Encoding is UTF-8 (localization files have BOM).
- This folder syncs via Dropbox; avoid dumping huge generated outputs here.
