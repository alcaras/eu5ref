# Art extraction — getting game icons into the mirror

The site currently renders color chips instead of game icons because the
`game/` mirror excludes all `gfx/`. The icons the site needs are a small,
well-bounded subset — **not** the 9.7 GB of terrain/3D art.

## What the site needs (and why exactly this)

Every icon path the game uses is declared in
`game/loading_screen/common/defines/graphic/00_graphics.txt` under
`NGameIcons` / `NGameIllustrations`, and every one resolves relative to
`game/main_menu/`. Examples: `TRADE_GOODS_ICON_PATH =
"gfx/interface/icons/trade_goods"`, `ADVANCE_ICON_PATH =
"gfx/interface/advance"`, `BUILDINGS_ICON_PATH =
"gfx/interface/icons/buildings"`. The vendored PyHelpersForPDXWikis toolkit
reads these same defines (`eu5/eu5lib.py` `IconMixin`), so once the files
exist in the mirror, `entity.get_icon_path()` starts working with zero code
changes.

## The copy (run on the machine with the Steam install)

From the EU5 install (e.g.
`C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V`) into
this mirror folder (`<dropbox>/cc/eu5ref/`), **preserving relative paths**:

1. `game/main_menu/gfx/interface/` → `eu5ref/game/main_menu/gfx/interface/`
   — the whole tree: all `icons/*` categories, `advance/`, `illustrations/`,
   `topography/`, `vegetation/`, `mapitems/`, `hegemony/`. This is the bulk
   of what the site needs.
2. `game/dlc/*/main_menu/gfx/interface/` → same relative spot under
   `eu5ref/game/dlc/…` — DLC icon overlays (the toolkit falls back to
   `game/dlc/*/...` when an icon is missing from base).
3. Optional, for future coat-of-arms rendering:
   `game/main_menu/gfx/coat_of_arms/` (patterns + colored emblems). Skip if
   it's huge; check size first.

Windows one-liners (adjust the two roots):

```bat
robocopy "C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\main_menu\gfx\interface" "%USERPROFILE%\Dropbox\cc\eu5ref\game\main_menu\gfx\interface" /E
for /d %D in ("C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\dlc\*") do robocopy "%D\main_menu\gfx\interface" "%USERPROFILE%\Dropbox\cc\eu5ref\game\dlc\%~nxD\main_menu\gfx\interface" /E
```

(Not every DLC has a `main_menu\gfx\interface` — robocopy just skips those;
exit codes ≤ 7 are success.)

## What happens after the copy (this repo, `make art` — to be built)

A `scripts/extract_art.py` step will:
- iterate the entities each dataset emits, call the toolkit's
  `get_icon_path()` (which consults `NGameIcons` + DLC fallback),
- convert `.dds` → `.png` (Pillow reads DXT-compressed DDS) into
  `public/img/<type>/<slug>.png`, only for icons actually referenced,
- committed to the repo so GitHub Pages serves them (same posture as
  owreference and the Paradox wikis).

`game/` stays gitignored — icons enter the repo only as the converted,
referenced `public/img/` PNGs.
