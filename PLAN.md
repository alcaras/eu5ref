# eu5ref — plan for an EU5 reference site in the spirit of owreference

Goal: a static, auto-updating reference site for **Europa Universalis V** (v1.3.11 per
`binaries/checksum.txt`), built the same way `../owreference` is built for Old World:
the site is a **deterministic projection of the game's own data files**, re-generated
each patch, with a PKM-style everything-is-a-link design and a handful of interactive
tools.

---

## 1. What's in this folder (data audit)

This folder is a copy of the EU5 install (minus packed art/binaries payloads):

| Path | What it is |
|---|---|
| `game/in_game/common/` | **The motherlode.** 124 folders of Jomini script: advances, building_types, goods, laws, estates, religions, cultures, unit_types, government_reforms, subject_types, international_organizations, situations, disasters, missions, traits, pop_types, production methods (inline in buildings), casus_belli, wargoals, peace_treaties, parliament_*, holy_sites, script_values, scripted_triggers/effects… ~2,250 `.txt` files |
| `game/in_game/setup/countries/` | Country definitions by region (46 files, ~2,200 tags with color, culture, religion, difficulty) |
| `game/in_game/events/` | 41 folders/files of narrative + system events |
| `game/in_game/map_data/` | adjacencies.csv, named locations, locations.png |
| `game/main_menu/localization/english/` | **Full English localization** (119 `.yml` files) |
| `game/main_menu/common/` | game_concepts, modifier_type_definitions, modifier_icons, named_colors, coat_of_arms, static_modifiers, achievements, game_rules |
| `game/loading_screen/common/defines/00_defines.txt` | 2,608 lines of engine constants (formula inputs) |
| `game/dlc/` | DLC script content (Fate of the Phoenix, Ancient Monuments, Sacred Sites) — parseable like base game |
| `tools/PyHelpersForPDXWikis/` | **Mature EU5 wiki-generation toolkit** — Jomini parser, localizer + text formatter, modifier rendering, entity classes for ~everything, map hierarchy (continent→…→location), version detection |
| `tools/jomini-parser/` | Rust Jomini parser (rakaly) — fallback / perf option, not needed initially |
| `tools/pdx-tools/` | Save-file analyzer — out of scope for a reference site (future: save-import tools) |

Rough entity counts: **~3,000 advances**, **~430 building types**, **~2,200 country tags**,
~90 goods, dozens of estates/law groups/reform trees, hundreds of cultures & religions,
unit types per age + uniques, and tens of thousands of map locations.

**Not present:** icon/texture art (only DLC thumbnails), game source code (EU5 is
closed-source, unlike Old World). Both shape the plan below.

---

## 2. What carries over from owreference, and what changes

### Carries over (architecture DNA)

- **Astro static site**, dark-mode-only, GH Pages deploy, `make patch` pipeline:
  `sync → art → data → audit → changelog → build → check`.
- **`scripts/build_*.py` → `src/data/*.json`** with deterministic key ordering; one
  script per dataset; snapshot diffing → auto CHANGELOG per patch.
- **`entities.json` + alias index + `backlinks.json`**; `<Term>` / `<LinkedText>`
  components; every entity page shows backlinks.
- **`tabs.ts` catalog** driving nav + index; placeholder pages for unbuilt tabs.
- **Audit gate**: any data the game renders that we silently drop fails the pipeline.
- Design rules worth keeping verbatim: no all-caps, everything is a link, honest
  fallback rendering over silent omission, in-game colors only, mixed-case serif
  display headings.

### Changes forced by EU5

1. **Parser: reuse `PyHelpersForPDXWikis`, don't write a new humanizer.**
   OW needed a hand-built `humanize.py` because effects were opaque XML. EU5 is far
   better positioned: modifiers are self-describing. `main_menu/common/
   modifier_type_definitions` + `MODIFIER_TYPE_NAME_*` localization keys + the
   toolkit's `Eu5ModifierType` (format strings, decimals, good/bad polarity, icons)
   give us game-authored phrasing for every modifier. Our "humanizer" is a thin layer
   over the toolkit's formatter.
2. **Native concept links.** EU5 loc strings embed `[concept|e]` markup and
   `main_menu/common/game_concepts` defines the glossary. Where owreference had to
   invent its PKM link graph, EU5 *ships one*. The text formatter converts
   `[stability|e]` → `<Term id="concept:stability">`. The Concepts glossary page is
   nearly free and becomes the hub of the link graph.
3. **Scale demands search-first navigation.** 2,200 tags and 3,000 advances can't be
   one spreadsheet-style table each. Pattern: section landing pages with client-side
   filter/search (static JSON, no server), then generated detail pages. Locations
   (~30k) get **no individual pages** — roll up at area/province level with a
   searchable index.
4. **No shipped source code.** OW's combat-formula and turn-order pages read C#.
   For EU5 the mechanics layer is: `defines/00_defines.txt` (2,608 constants),
   `script_values/` (formula components in script), the official wiki, and in-game
   testing. Formula pages are still possible but are curated, not extracted —
   annotate provenance on each.
5. **Art must be synced from a real install.** This dump has no `gfx/`. `make art`
   should rsync/convert (dds→png) from the Steam install when available; until then
   the site runs icon-less with colored chips (goods/countries/religions all define
   colors in script — `named_colors`, `color = goods_x`, per-tag map colors).
   Coat-of-arms are CK3-style scripted emblems; full CoA rendering is a later
   stretch goal (needs pattern/emblem textures).
6. **DLC layering.** `game/dlc/*/in_game/common/...` overlays base files. The parser
   must merge base+DLC and badge DLC-sourced entities (owreference does the same
   with `GameContentRequired`).

---

## 3. Pipeline design

```
make sync       rsync Steam EU5 install → ./game/ (this folder already is one)
make art        dds→png icon extraction from install gfx (optional until install available)
make data       scripts/build_*.py — each imports the PyHelpers parser once,
                emits src/data/<thing>.json (sorted keys)
                scripts/build_entities.py → entity registry + aliases
                scripts/build_backlinks.py
make audit      - every modifier key used in emitted data resolves to a
                  modifier_type + localization (else FAIL)
                - every folder in game/in_game/common/ is either mapped to a build
                  script or consciously skipped in a SKIP list (patch tripwire)
                - unlocalized entity names FAIL
make changelog  diff all src/data/*.json vs data/snapshots/<version>/
make build      npx astro build
make check      internal link + unresolved-Term check
```

Setup notes:
- `tools/PyHelpersForPDXWikis/PyHelpersForPDXWikis/localsettings.py`: point `EU5DIR`
  at this repo root — the toolkit's expected layout (`game/in_game/common`,
  `binaries/checksum.txt`) matches this dump exactly; version detection already knows
  1.3.11.
- The toolkit caches parsed trees; wire its cache dir into the repo (`.cache/`,
  gitignored) so `make data` is fast on re-runs.
- **Move/copy the working repo out of Dropbox** (or at least `git init` + pin files
  offline): files here are online-only placeholders (`du` reports 0B) and Dropbox
  sync fights build tooling. Recommended: this folder stays the *data drop*, the
  site repo lives in `~/code/eu5ref` and syncs from it.

---

## 4. Site map — sections and pages

Ordering follows how players think about the game. `(F)` = flagship candidate for the
design-reference page (owreference's `nations.astro` role).

### Countries
- **Country browser (F candidate)** — filter by region/culture/religion/government/
  difficulty at 1337; color chips from map colors; links into everything below.
- Country detail pages — starting setup, unique advances/units/buildings (mined by
  scanning `potential`/`allow` for tag/culture gates), formable targets, description
  category.
- Formable countries — requirements and rewards.
- Country ranks & hegemons.

### Ages & Advances
- **Advances tree (F candidate)** — per-age tree pages (7 ages), depth-laid-out,
  each advance: costs, prereqs, modifiers, unlocks (buildings/units back-referenced).
  National/cultural advance branches badged.
- Ages — age objectives, mechanics unlocked per age.
- Institutions — spawn/spread rules (the loc already documents spread factors).

### Government & Laws
- Government types & reforms; ranks.
- Laws — by category (monarchy/republic/theocracy/tribal, legal, military, naval,
  distribution of power, estate laws, religious laws incl. tenets/sects), each with
  policies and modifiers.
- Parliament — types, issues, agendas.
- Cabinet — actions, efficiency; regencies, heir selection.
- Estates & privileges — per-estate pages: equilibrium, privileges, agendas.
- Societal values — the 9 sliders and what moves them.

### Economy
- **Goods** — all ~90: category, base price, transport cost, demand by pop type,
  production methods that make/consume them, buildings involved. Good detail page =
  full supply/demand graph via backlinks.
- **Buildings** — ~430, by category; production methods inline (inputs→outputs),
  employment, terrain/rank gates, construction demand.
- Town rights, town/city setups, location ranks.
- Markets & trade (rules from defines + concepts; no per-market data at rest).

### Society
- Pop types — needs (goods_demand), literacy, growth.
- Cultures — groups, languages, language families; culture detail w/ countries and
  locations at start.
- Religions — groups, aspects, schools, focuses, holy sites (+ Sacred Sites DLC),
  religious figures/factions.
- Characters — traits (huge table like OW's), child educations, character
  interactions, chivalric orders, artists & works of art.

### Military
- Units — by age (the age-template files) + regional/unique lines (janissaries,
  qizilbash, elephants…); land & naval; stats, costs, tech gates.
- Levies & recruitment methods; unit abilities; formations.
- Warfare reference — casus belli, wargoals, peace treaties, join-war rules.
- Combat mechanics — curated from defines + wiki (provenance-annotated).

### Diplomacy
- Subject types — the full matrix (military stances, payments, integration).
- International organizations — HRE, Papacy, etc.: laws, statuses, payments.
- Diplomatic actions (country_interactions), costs, insults, rival criteria.

### World
- Map browser — continent → subcontinent → region → area → province, with
  searchable location index (no per-location pages).
- Climate / topography / vegetation — modifiers per type.
- Situations & disasters — struggles, civil wars, plagues (diseases), each with
  triggers/phases/resolutions.
- Missions — mission trees per country/group (mined from `missions/` +
  `mission_task_defs`).
- Events browser — by folder/domain, like owreference's events pages (later phase;
  EU5 events are numerous and heavily scripted).

### Concepts
- **Glossary (early win)** — every `game_concepts` entry, auto-linked; the hub of
  the link graph.
- Defines explorer — the 2,608 constants, grouped and annotated over time.

### Tools (interactive, all client-side)
- **Production calculator** — pick building + production method + modifiers → goods
  in/out, employment, profitability at market prices.
- **Advance path planner** — select target advances → prereq closure, total cost by
  age (the "Total Science to Unlock" analog).
- **What-unlocks-X search** — reverse index over advances/laws/reforms unlocks.
- **Goods demand explorer** — pop needs × pop type → demand per capita.
- Patch notes page + auto-changelog (same as owreference).
- Later, with formulas validated: combat simulator, siege calculator.

---

## 5. Design language

Keep the owreference philosophy (dark, parchment-and-gold, dense-but-elegant tables,
everything linked), but EU5 gets its own skin — this is 1337–1836, not antiquity:

- Palette from the game's own `named_colors` + goods/estate/religion colors; keep a
  dark base with a warmer old-map parchment accent. Good/bad modifier polarity in
  the game's green/red, driven by modifier_type metadata.
- Display serif in the early-modern direction (EB Garamond / Cormorant) instead of
  Cinzel; Inter body, JetBrains Mono for defines/keys.
- Modifier lines render exactly as the game phrases them (localization-driven),
  with the game's modifier icons once art extraction lands.
- `<Term>` everywhere: concepts, goods, advances, tags, estates, religions.
  Backlinks footer on every entity page.

---

## 6. Phased roadmap

> **Status (2026-08-26):** Phase 0 shipped (goods + concepts live). Phase 1
> (advances, buildings, units, laws, reforms, estates, religions, cultures,
> pops + game icons) and Phase 2 (countries, formables, subjects, IOs,
> warfare, terrain, towns, parliament, cabinet, characters, levies,
> situations, societal values, diplomatic actions) built in one push, plus
> Phase 3 tools: global search, defines explorer, patch notes, and the
> interactive Tech Planner (owtt-style, shareable URLs). Remaining:
> map browser, missions, production calculator, reverse-unlock search,
> trigger-aware gating in the planner.

**Phase 0 — scaffold + proof of pipeline (small, end-to-end)**
Repo scaffold (Astro + theme + Base layout + tabs.ts with all planned tabs as
placeholders), localsettings → this folder, `build_goods.py` → goods page (small,
colorful, exercises localization + modifiers + linking), entities/backlinks harness,
changelog + audit skeletons. *Exit criterion: `make patch` runs clean and /goods ships.*

**Phase 1 — core references**
Concepts glossary → Advances (flagship) → Buildings + production methods → Units →
Laws/Government/Reforms → Estates → Religions → Cultures → Pop types. Each promotes
its tab from placeholder.

**Phase 2 — countries & world**
Country browser + detail pages (setup + formables + unique-content mining), map
browser, subjects + IOs + diplomacy, traits/characters, situations/disasters,
missions.

**Phase 3 — tools & polish**
Production calculator, advance planner, reverse-unlock search, art extraction pass
from a live install, events browser, defines explorer, CoA rendering (stretch).

---

## 7. Risks & open questions

- **Version currency**: dump is 1.3.11. Confirm whether the live game has moved on;
  `make sync` from a real install is the long-term answer.
- **Formulas without source**: combat/siege/trade math must be curated (defines +
  wiki + testing), never presented as extracted. Annotate provenance per page, like
  owreference's source-constant verifier — here, hash the defines file and warn on
  drift.
- **Art licensing/size**: same posture as owreference (game art on GH Pages, as the
  paradox wikis do); dds→png only for icons actually used.
- **Parse performance**: full parse of 2,250 files + 30k locations is slow in
  Python; the toolkit's caching mitigates. If it becomes painful, `jomini-parser`
  (Rust) is already vendored as an escape hatch.
- **DLC merge semantics**: verify the toolkit's handling of `game/dlc/*` overlays vs
  base files, and badge DLC content in the UI.
- **Dropbox placeholders**: builds will fault in online-only files; pin the repo
  offline or relocate the working copy.
