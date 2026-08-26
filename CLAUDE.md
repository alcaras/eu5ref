# CLAUDE.md — agent guide for eu5ref

Reference site for **Europa Universalis V**, sibling of
[owreference](https://github.com/alcaras/owreference) (same philosophy: the
site is a deterministic projection of the game's own data files, regenerated
each patch). Astro static site, dark mode only, deployed to GitHub Pages.

**Live:** https://alcaras.github.io/eu5ref/ · **Repo:** https://github.com/alcaras/eu5ref
**Plan:** see `PLAN.md` for the full roadmap and data audit.

---

## The layout of this folder

The repo root doubles as the game-data drop (gitignored):

```
game/                 EU5 install dump (in_game/common = the data; NOT committed)
binaries/checksum.txt version detection (1.3.11)
tools/PyHelpersForPDXWikis/   vendored EU5 wiki toolkit — our parser (NOT committed)
.venv/ .toolbin/ .cache/      local toolchain (venv, rakaly binary, parse cache)
scripts/              build pipeline (committed)
src/                  Astro site (committed; src/data/*.json is generated+committed)
data/                 patch.json + snapshots/ for the changelog
```

Local setup (once): `make setup`, then create
`tools/PyHelpersForPDXWikis/PyHelpersForPDXWikis/localsettings.py` from the
`.example` with `EU5DIR` = this repo root, `RAKALY_CLI` = `./.toolbin/rakaly`
(download from github.com/rakaly/cli), `CACHEPATH` = `./.cache`.

CI builds from the **committed** `src/data/*.json` — no game data or Python
needed on GitHub Actions. `make data` runs locally only.

---

## Pipeline

```
make patch = data → audit → changelog → build
  data       scripts/build_*.py  → src/data/*.json (via the toolkit parser)
             build_entities.py   → cross-dataset registry + aliases
             build_backlinks.py  → who-references-whom (from rich-text tokens)
  audit      audit_coverage.py   → HARD GATE: every game/in_game/common folder
                                   must be BUILT, PLANNED, or SKIPPED (w/ reason)
  changelog  changelog.py        → snapshot diff → CHANGELOG.md
  build      npx astro build     → dist/ (CI does this on push)
```

---

## The four abstractions (LOAD-BEARING — build everything on these)

Everything the site renders flows through four shapes, produced in Python
(`scripts/lib/ref.py`) and consumed by four Astro components. **Never
hand-roll a table, modifier line, or entity link on a page.** If a page needs
something these can't express, extend the abstraction, don't bypass it.

### 1. Entity envelope — every dataset JSON

```jsonc
{
  "dataset": "goods",
  "source": "in_game/common/goods",       // provenance
  "entities": [ {
    "id": "good:horses",                  // global: "<type>:<script-key>"
    "type": "good", "slug": "horses", "name": "Horses",
    "desc": <Rich>|null,
    "color": "#9f8170"|null,
    "facets": {"category": "raw_material"},   // drives FilterBar + data-f-* attrs
    "mods": [<Mod>...],
    "data": {...}                         // dataset-specific payload
  } ],
  "facets": [ {"key","label","options":[{value,label,count}]} ]  // via facet_meta()
}
```

### 2. Mod — `mod_json(key, value)` in ref.py

`{key, label, value, polarity}` — value formatted with the game's own
modifier_type metadata (%, decimals, +/−), label from `MODIFIER_TYPE_NAME_*`
loc, polarity good|bad|neutral from the game's good/bad declaration. Unknown
keys render raw with `unresolved: true` (the audit reports them) — honest
fallback, never silent omission. Rendered ONLY by `<Mods mods={...}/>`.

### 3. Rich text — `rich(text)` in ref.py

Loc strings tokenize to `[["t","text"], ["r","concept:stability","Stability"]]`.
`[concept|e]` markup → real links (aliases resolve to canonical concepts),
`$KEY$` nesting resolves, `#format ...#!` and icon markup strip to text.
Rendered ONLY by `<Rich tokens={...}/>` (which uses `<Term>` per ref).
This is the PKM link graph: EU5's own concept markup IS our cross-linking.

### 4. Registry + backlinks — derived, automatic

`build_entities.py` aggregates every dataset's entities into
`entities.json` (id → {type,name,slug,page,color} + alias index);
`build_backlinks.py` inverts every `["r", id, …]` token into
`backlinks.json`. New datasets join both automatically — no wiring.
`TYPE_PAGES` in build_entities.py maps entity type → route prefix.

### Frontend counterparts

- `<EntityTable entities columns pagePrefix csvName?>` — schema-driven table;
  column kinds: `name | namePlain | text | num | chips | facet | mods | rich |
  pairs | refs`. Emits `data-search` + `data-f-<facet>` on rows, plus a CSV
  export button (respects active filters).
- `<FilterBar facets placeholder>` — client-side search + facet chips; wrap
  both in `<div data-filter-scope>` and filtering Just Works (OR within a
  facet, AND across facets + search).
- `<SectionTable data columns pagePrefix? title? minFacetCount?>` — one
  dataset table with its own filter scope; THE building block for list pages
  and composite pages (several datasets on one page). No `pagePrefix` → no
  detail links (name renders as icon + text).
- `<EntityDetail entity backlinks modsTitle?>` — generic detail layout
  (chips + desc + mods left, data/backlinks panels right; slots for extras).
- `<Term id label? showIcon?>` — one linked entity reference (plain span if
  no page; renders the entity's icon when the registry has one).
- `<Mods>`, `<Rich>` — see above.
- `<Base title active eyebrow pageMark iconSrc pageStats description>` —
  shell with section-dropdown nav and the global header search ("/" key;
  lazy-fetches `public/search.json`, generated by build_entities.py).

### Advance gates (`scripts/lib/triggers.py`)

2,400 of the 3,178 advances carry a `potential` trigger — the game's own
"who is this for". `compile_trigger()` lowers that script block to a compact
boolean expression over four static country facts (tag, culture/group/
language, religion/group, capital geography), which `build_countries.py`
emits per country as `data.facts`. The planner evaluates it with **three-
valued logic**: TRUE = yours, FALSE = another country's, `null` = conditional
(depends on something acquirable — an institution, estate, reform). Only a
definite FALSE is filtered out, so nothing acquirable is ever silently
hidden. `UNHANDLED` counts every predicate that fell through to `["?"]` and
the build prints it — that number (currently 244) is the honest coverage
gap, not a guess. `summarize()` renders `allow` (the research prerequisite,
e.g. "has embraced institution: New World") for tooltips and detail pages.

**Branches and tiers:** each age is a forest — the advances the files mark
`depth = 0` are the roots (Discovery = New World / Pike and Shot / Printing
Press / Surgery) and nearly every other advance has exactly one prereq.
`build_advances.py` resolves each advance to its `branch_id` + `tier`, which
is what lets the planner draw the game's layout.

**The game's own layout** (from `game/in_game/gui/technology_lateralview.gui`
— the tree screen; `advances_lateralview.gui` is only the side panel):
age tabs → per-age sub-graphs stacked vertically, each a top-down tidy tree
on a 340px rank pitch with bspline edges and a 0.1–1.5 pan/zoom canvas,
nodes tinted by unlock type (green none / blue buildings-units-laws / red
diplomatic).

**We deliberately do NOT copy that geometry — don't "fix" it back.** A tidy
tree centres each parent over its subtree, which with 170-leaf branches
opens enormous gaps; the in-game screen sprawls for exactly this reason and
is hard to read there too. The planner keeps the game's *semantics* —
same branches, same tiers, same edges, same node tinting — but **transposes
the axes: tier becomes a column, packed vertically with no gaps**. Depth is
only 8–10, so a whole age fits the viewport width with every name legible
(≈1,400px vs ≈4,800px for the tidy version). Within a column, nodes are
ordered by their parent's row so children sit beside their parent. Hovering
lights an advance's full prerequisite chain and dims the rest.

### The long-tail builder

`scripts/build_simple.py` holds a SPECS table — one entry per simple dataset
(accessor, etype, facets, data attrs). Most Phase-2 datasets (ages, subjects,
IOs, casus belli, terrain, parliament, cabinet, traits, situations…) are one
SPECS line + a page using `<SectionTable>`. Only write a bespoke
`build_<thing>.py` when the dataset needs real shaping (goods, advances,
buildings, units, laws, countries).

---

## How to build a new dataset/page

1. **Data**: `scripts/build_<thing>.py` — import `ref`, use the toolkit's
   parser (`ref.parser.<accessor>` — see `tools/.../eu5/parser.py` for ~60
   cached accessors: advances, buildings, countries, laws, religions…), emit
   the envelope via `write_dataset()` + `facet_meta()`. Add to `Makefile`
   `data:` target BEFORE build_entities/build_backlinks.
2. **Audit**: move the folder from `PLANNED` to `BUILT` in
   `audit_coverage.py`.
3. **Registry**: add the entity type to `TYPE_PAGES` in `build_entities.py`
   if it gets detail pages.
4. **Pages**: list page = `src/pages/<slug>.astro` (copy goods.astro:
   FilterBar + EntityTable inside `data-filter-scope`); detail page =
   `src/pages/<slug>/[slug].astro` (copy goods/[slug].astro: facts panel +
   backlinks panel).
5. **Catalog**: flip the tab's `status` to `'built'` in `src/data/tabs.ts`.
6. `make data && npx astro build` to verify.

---

## Design rules (inherited from owreference — don't drift)

1. **Dark mode only.** Deep navy base, warm parchment text, EU-gold accent
   (owreference is warm-slate/gold; we are its naval-navy sibling).
2. **Fonts:** EB Garamond display, Inter body, JetBrains Mono for numbers.
3. **No all-caps** except the small uppercase section labels already in CSS.
4. **Everything is a link** — free text goes through `<Rich>`, references
   through `<Term>`. Backlinks panel on every detail page.
5. **In-game colors only** — goods/country/religion colors come from the
   data layer (PdxColor → hex), never invented.
6. **Modifier polarity** (green/red) comes from the game's modifier_type
   declarations — never guessed from the sign.
7. **Honest fallbacks over silent drops**: unresolved modifiers render raw
   and get flagged; unresolvable loc markup degrades to readable text.

---

## Source-of-truth rules

1. **Game files win on facts.** No hand-curated numbers where the script
   data expresses them.
2. **Formulas are curated, not extracted** (EU5 ships no source code):
   defines (`game/loading_screen/common/defines/00_defines.txt`),
   `script_values/`, wiki, in-game testing — annotate provenance on any
   mechanics page.
3. **The toolkit is vendored, not forked lightly** — prefer configuring it
   (localsettings) or wrapping it (ref.py) over editing it, so upstream
   updates stay mergeable. `localsettings.py` is local-only (gitignored).

---

## Icon art

No game icons in the mirror yet (gfx/ was excluded) — color chips stand in.
`ART-EXTRACTION.md` documents exactly which gfx subtrees to copy from a
Steam install (the `NGameIcons` paths under `game/main_menu/gfx/interface/`)
and the planned `make art` dds→png step that follows.

## Quirks already discovered (don't re-debug)

- `du` reports 0B for game files — Dropbox online-only placeholders; reads
  fault them in fine. Don't "fix".
- The toolkit shells out to the **rakaly** CLI for parsing; without it you
  get `FileNotFoundError: 'rakaly'`. Binary lives at `.toolbin/rakaly`.
- First full parse is slow (~40s incl. localization); the toolkit caches in
  `.cache/` keyed by game checksum — subsequent runs are fast.
- `parser.goods['x'].demands` maps PopType *objects* → value; values carry
  float noise (0.023999…) — round at emit time.
- Concept aliases are separate entries with `is_alias=True` and **no back
  pointer**; `ref.concept_alias_map()` rebuilds alias → canonical.
- Some loc strings embed `GetDefine('NPop', …)` / `ShowMinAdolescentAge`
  scope calls with no static value; they degrade to readable text (known
  cosmetic issue, listed in PLAN).
- **Sticky table headers don't work** inside `.etbl-scroll` (the overflow-x
  container becomes the sticky container and pins the header into the
  table). Deliberately removed; revisit with a separate scroll structure.
- Astro dynamic route `[slug].astro` at pages root serves the placeholder
  tabs; a real page file with the same slug automatically wins.
- **Astro `<style>` is scoped** — CSS for elements a script injects via
  `innerHTML` must be `is:global` (or live in theme.css). The Tech Planner
  board rendered unstyled until its style tag was made global.
- **Toolkit attribute values are often objects, not scalars** — `category`
  can be a BuildingCategory, `law_gov_group` a GovernmentType, `max_levels`
  a ScriptValue, `literacy_impact` a modifier list. Always resolve through
  `display_name`/`mods_from_tree` or drop; `json.dumps` failures name the
  offending key path.
- **First read of any game file downloads it from Dropbox** (online-only
  placeholders). Bulk jobs (icon export) crawl until prefetched — a parallel
  `find … -name '*.dds' | xargs -P 8 cat > /dev/null` warms the whole tree
  in one pass and is worth doing before `make data` on a fresh machine.
- `public/planner.json` (Tech Planner graph) and `public/search.json`
  (header search) are generated by build_planner.py / build_entities.py and
  fetched lazily client-side — they are NOT dataset envelopes and are
  excluded from entity aggregation by living in public/, not src/data/.

---

## Git / deploy

- Commit as **alcaras <alcaras@subcreation.net>** (repo-local git config —
  never any other identity). `gh` must have alcaras as the active account.
  Nothing that references any other account name or local username may go
  into this repo (mind absolute paths in docs and configs).
- Push to `main` → `.github/workflows/deploy.yml` builds (`npm ci`,
  `astro build`) and deploys Pages. Generated `src/data/*.json` is committed
  so CI needs no game data.
