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
             build_country_start.py → per-tag 1337 setup (values/laws/privs)
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
- **Page-scoped CSS for a shared widget bites.** `.pl-picker`'s positioning
  lived in advance-planner.astro's style block, so on every other page the
  absolutely positioned `.hdr-search__results` anchored to the page instead
  and the dropdown landed far right. Shared widget CSS belongs in theme.css.
- Anonymous blocks inside a list (`{ type = x date = y }`, as in Byzantium's
  bureaucracy entries) break a naive Clausewitz parser: the `{` is not a
  key, and its `}` closes the enclosing block. Recurse on a bare `{`.
- `public/planner.json` (Tech Planner graph) and `public/search.json`
  (header search) are generated by build_planner.py / build_entities.py and
  fetched lazily client-side — they are NOT dataset envelopes and are
  excluded from entity aggregation by living in public/, not src/data/.

---

## Societal values — grounded facts (don't re-derive, don't "improve" past these)

- **Drift is not linear.** The in-game "Societal Value" concept says progress
  toward a pole "will stall at a maximum, determined by the total amount of
  factors pushing it in that direction. The higher a Societal Value, the more
  factors are needed to push it further." The slowdown curve is engine-side —
  it is NOT in the files. `SOCIETAL_VALUE_INERTIA_SCALE = 100` and
  `societal_value_min_scaling_monthly_move = 0.01` are the only hints. So
  every projection we show is labelled an upper bound ("at best", "no sooner
  than"), never a schedule. Do not restore a "years for a full swing" number.
- **Sign convention: right pole is positive.** `centralization_vs_decentralization
  = 85` for 1337 France means heavily *decentralized* (appanages), and its
  `serfdom_vs_free_subjects = -80` means serfdom. Both check out historically.
- **Starting values/laws/privileges are real and per-country.** The 1337
  bookmark gives each tag `include = "<template>"` lines resolved against
  `game/main_menu/setup/templates/` (205 of them), which carry the societal
  value block, the `privilege = { … }` grants and the `laws = { group = option }`
  selections. `scripts/build_country_start.py` resolves the stack →
  `public/country-start.json`, 2,337 tags. Both planners default from it.
- **Laws are groups of mutually exclusive OPTIONS.** A law block holds
  metadata (see `LAW_META`) plus one sub-block per selectable policy, each
  with its own `country_modifier`. Emitting one mover per *group* merges
  opposing options and nets them to zero — `feudal_de_jure_law` looked like it
  did nothing when `by_tradition` pushes inward and `by_blood` outward. We
  emit one mover per option with `group`/`groupName`, and the UI treats a
  group as pick-one.
- A law option's gate is **its own `potential`/`allow` AND its group's** — the
  group says which governments run the law at all, the option is often one
  country's version of it.
- **`monthly_towards_*` only counts inside a modifier block.** The same key
  also appears in `limit`/`add`/`value` blocks, where it is an AI weighting
  term, not something applied to the country. `walk()` tracks the parent block
  and keeps only `modifier` / `*_modifier` / `high_power` / `low_power`, plus
  `modifier_when_in_debate` and `modifier_while_progressing` flagged
  `temp: true` (transient — excluded from sustained drift).
- **Requirements must be read with their block path.** Scanning an entity body
  for `societal_value:x > n` catches AI weights: noble parliament issues came
  out "requiring" a plutocratic country because the comparison sat in
  `chance = { multiply = { if = { limit = … } } }`. `scan_requirements()`
  accepts only `allow`/`locked`/`potential`/`can_start`/`trigger`, rejects
  `_AI_BLOCKS`, and flips the operator under an odd number of `NOT`/`NOR`.
  This took requirements from 125 (inflated) to 91 (real).
- **Reforms bank, laws and privileges do not.** Per
  `common/government_reforms/readme.txt`, `allow` is "whether the action can
  start" and there is no `remove_if`, so a reform enacted while you qualified
  survives the value drifting back — that is what makes the swap-away path
  work. Law/privilege modifiers apply only while run.
- Only **8 cabinet actions** move a value, and they are niche (Foster New
  Culture, Unify Culture Group, Stroganov Influences, …). There is no generic
  "promote value" cabinet action — don't claim one.
- Estate-privilege capacity is bounded by **estate satisfaction**
  (`GRANT_PRIVILEGE_SATISFACTION_IMPACT = 3`), not a slot count, and that
  budget is not computable from the files. The path planner ranks candidates
  by push and says so.
- The parser hands booleans back as Python `True`, not the literal `"yes"` —
  `has_tribal_government = yes` compiled to its own negation until that was
  handled. Check the type before comparing to `'yes'`.

### The two value tools

`values-planner` is the static one: pick what you run, see net push per axis
and what it unlocks. `value-path` is the sequencer: an ordered list of
targets, scheduled against the campaign clock. Both fetch `public/values.json`
+ `public/country-start.json`; neither is a dataset envelope.

- **Ages have real years** (`common/age/00_default.txt`): 1337 (age 1 uses
  `year = 1`, i.e. game start), 1342, 1437, 1537, 1637, 1737. Emitted into
  values.json as `ages`. `current_age = X` is an **exact** match on the age
  you are in, not "this age or later" — a thing gated to age 1 is gone by
  age 2.
- **The tech clock matters more than the age clock.** Only ~11 movers carry
  an explicit `current_age` gate, so age gating alone is nearly flat and the
  planner happily claimed you could swing Quantity in the 1340s. The real
  constraint is that 187 movers carry **no trigger of their own** and simply
  do not exist until an advance grants them: advances unlock 43 laws, 22
  reforms, 12 cabinet actions and 10 privileges. `unlocked_by()` joins
  `advances.json`'s `unlocks` items (`law:x`, `reform:x`, `privilege:x` — the
  same ids movers carry) to the earliest granting advance's age, emitted as
  `mover.unlock = {year, age, advance}`. A mover is unavailable before that
  year. Quantity is the worked example: `A Large Standing Army` and `Jaysh
  Armies` both need Absolutism-age advances (1637). Requires advances.json,
  so build_values must run after build_advances.
- **A stage waits for its age, it is not "impossible".** When no mover in the
  current age pushes the right way, the scheduler jumps the clock to the next
  age boundary. Only running out of campaign (1837) marks a stage stalled.
- **The push table is the reason the order search is viable.** Ranking every
  mover for every (axis, direction, age) is ~200 passes over 830 movers —
  fine once per country, fatal inside the search. `buildTable()` caches it;
  `bestOrder()` (greedy seed by earliest finish + relocation improvement,
  hundreds of candidate orders) then costs milliseconds. Rebuild the table
  whenever country or government changes.
- **Same-axis stages keep their relative order** in any reordering — a
  reversal like decentralize-then-centralize is the whole point of the
  swap-away dance, and the second leg has to stay second.
- **A "hold at N" target has no fixed direction.** Which way to push depends
  on where the axis currently sits, so `dir: 'auto'` resolves live. France
  starting at −75 aristocracy pushes right to reach 0; a country at +40
  pushes left to the same target.
- Government type is a compiled gate (`['gov', 'monarchy']`) on movers AND
  advances, selectable in both planners so a change of government can be
  planned. `build_planner.py` reads country-start.json to attach `f.gov`.
- **Ordering by finish time cannot express wanting to sit on a position.**
  Holding decentralization while subjects still earn their keep is a
  judgement about your game, not something the files decide, so stages carry
  a player-set `after` (not before year N) and `last` pin, and the scheduler
  and order search both respect them. Don't try to infer these.
- Unknown gates are **shown as unknown** — a suggestion whose trigger rests
  on a scripted trigger we cannot evaluate gets an "unverified" badge rather
  than being presented as available.

---

## Git / deploy

- Commit as **alcaras <alcaras@subcreation.net>** (repo-local git config —
  never any other identity). `gh` must have alcaras as the active account.
  Nothing that references any other account name or local username may go
  into this repo (mind absolute paths in docs and configs).
- Push to `main` → `.github/workflows/deploy.yml` builds (`npm ci`,
  `astro build`) and deploys Pages. Generated `src/data/*.json` is committed
  so CI needs no game data.
