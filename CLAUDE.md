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

**Every age from the Renaissance on declares exactly four `depth = 0` roots:
its three institutions and one ungated "always-available free tree"** — the
files' own comment on `surgery_advance` / `pharmacology_advance` /
`sanitation_advance` / `vaccination_advance` / `renaissance_development`.
Confirmed in game: the Discovery tab shows Surgery + New World + Printing
Press + Pike and Shot and nothing else.

**But 383 advances declare no `requires`, no `depth` and no `in_tree_of`** —
every focus advance among them — and the game gives each of them a REAL
prerequisite anyway, computed at load: the node above it in the tree screen
must be researched first. This was settled by decompiling `ConstructTree`
(advance.cpp; method in `scripts/re/README.md`) and **is now reproduced from
the files by `scripts/lib/layout.py`** (docstring = the algorithm), which
`build_advances.py` runs; `placed[key]` gives every advance its age, tree,
tree order, parent and depth. In short:

1. Roots are the `depth = 0` advances, in database order (`common/advances/
   *.txt` sorted by filename, definition order within a file).
2. Declared `requires` children attach under their parent if it is placed
   and still has capacity, else defer; `in_tree_of` advances are FindSlot-ed
   into that tree in seeded-random order; then the orphans, FindSlot-ed into
   the age's trees under a per-root quota rotation; deferred ones ping-pong
   until placed; finally the non-generic advances (focus `for`, `government`,
   `country_type`, or any `potential`) go under their `requires`, else
   FindSlot(in_tree_of), else FindSlot(age root).
3. `FindSlot` capacity: 2 children at depth < 2, deeper 2 if `depth % 3 == 1`
   else 1; a full node recurses into the child with the fewest descendants.
4. The RNG is the game's counter-based hash with a **constant seed
   (0x441e9e04)**, so the layout is global and identical for every player —
   countries only hide nodes. The "generic" test is `potential` — the
   content_priority and `allow` candidates were tried and rejected (0/8);
   `potential` gives 12/12 confirmed placements and zero "prerequisite not in
   the same tree" warnings.

**Verified in game (1.3.11):** Bookkeeping under Medical Schools, Humanism +
Formalized Officer Corps under Two-decker, Merchant Fleets in Enlightenment,
Heavy Frigate + Buffer States under Global Ambitions, Campaign Logistics
Planning + Additional Loyalist Recruitment under Rights of Man, Military
Traditions under Dry Dock, and a full Age of Discovery screenshot as Poland — every
tree, node and edge including the nationals (Polish Renaissance / Supremus
Dux Lithuaniae under Print Culture, Wojewodztwo under Pike Square, Mendicant
Orders under Diplomatic Training, Reform Church Music under Artists). The
`CHECKS` table in layout.py encodes these; `python3 scripts/lib/layout.py`
prints 14/14. (An earlier note had the Rights of Man pair under Global
Ambitions — that was a misread of the screenshot, not a model miss.)

**Emitted as** `data.drawn_in` (tree) and `data.drawn_under` (parent), each
`{id, name, computed}` — `computed: true` where the files declare nothing and
the value comes from the reproduced pass. The public wording is "reproduced
from the game files and checked against the tech screen", never
"decompiled", and no disassembly is quoted on the site. The planner's
`p` key carries the computed parent and `reqOf()` treats it as an effective
prerequisite (planning pulls it in, removal cascades, chains highlight),
drawn dashed. Two earlier guesses were wrong and cost several rounds — "no
prereq = its own root" and "orphans join the age's ungated free tree". Don't
retry either; and if a placement looks wrong, the fix is in layout.py's
ordering/predicates, not in a per-advance override.

**Re-check each patch:** any change to the advance list changes the
ConstructTree input, hence the layout. Run `python3 scripts/lib/layout.py`
after `make data`; a dropped CHECK means a new screenshot pass is due.

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

- **The drift model is known** (defines + community testing — the Steam
  thread "What determines the max value" confirms it): a value approaches an
  **equilibrium of `SOCIETAL_VALUE_INERTIA_SCALE (=100) × net monthly push`**
  — 0.4/mo of push stalls at ±40; the pole needs a full 1.0/mo. Drift speed
  is `(E − v)/100` per month (so ≈ the displayed monthly change at 0), with
  `societal_value_min_scaling_monthly_move = 0.01` as the floor that crawls
  the last point in. Corollaries the tools are built on: values **decay**
  toward the new equilibrium when a push is swapped away (nothing about the
  position banks), and holding v costs `v/100` per month, forever. Both value
  tools implement exactly this curve (`eqOf`/`monthsTo`); instant effects
  (events, agendas, debates) can pierce the cap but then decay back.
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
- **Focus-block reforms do NOT bank.** 52 reforms carry a
  `societal_values = { X_focus }` block; the threshold is the define
  `SOCIAL_VALUE_REQUIREMENT_FOR_REFORM = 50` and the engine **removes the
  reform when the value drops back below it** — loc keys
  `CHANGE_SOCIETAL_VALUE_AFFECTS_REFORM(_EVENTUALLY)` ("will be lost as it
  requires at least $VAL towards $NAME"), `REMOVE_GOV_REFORM_SOCIETAL_
  VALUES_MIN/MAX`, and the 12/24-month forecast defines. Keeping such a
  reform costs a standing 0.5/mo on its axis. Only a reform whose value
  requirement sits in `allow` (a handful, `country_specific.txt`) plausibly
  banks per the readme's "whether the action can start" — labelled "verify
  in game", never asserted. Law/privilege modifiers apply only while run,
  and reforms are permanent (no un-take) — the value-path optimizer treats
  reforms as irrevocable and only laws/privileges/cabinet as swappable.
- **There IS a generic "Encourage Societal Value" cabinet action** —
  `cabinet_actions/change_societal_values.txt`, backed by one static
  modifier per pole (`main_menu/common/static_modifiers/societal_values.txt`,
  `monthly_towards_X = 1`, "scaled with cabinet efficiency"; ~0.3–0.6/mo in
  practice). It is the main lever players pull, raising both speed and the
  cap. build_values emits it as synthetic `encourage_<side>` movers
  (`cabinet: true, encourage: true`); the frontends scale it by a
  user-set efficiency input. The 8 explicit value-moving cabinet actions
  (Foster New Culture, Stroganov Influences, …) also carry `cabinet: true`
  — every cabinet action occupies a member, and the planner allows one.
- Estate-privilege capacity is bounded by **estate satisfaction**
  (`GRANT_PRIVILEGE_SATISFACTION_IMPACT = 3`), not a slot count, and that
  budget is not computable from the files. The path planner exposes it as a
  user-set "new privs/stage" budget (and "new reforms/stage" for pacing
  permanent reforms) rather than pretending to compute it.
- The parser hands booleans back as Python `True`, not the literal `"yes"` —
  `has_tribal_government = yes` compiled to its own negation until that was
  handled. Check the type before comparing to `'yes'`.

- **Axes are themselves gated**: `mercantilism_vs_free_trade` age 4,
  `outward_vs_inward` age 3, `absolutism_vs_liberalism` age 5, and the
  special axes (sinicized, mysticism, latinization) carry `allow` triggers.
  Emitted as `pairs[pid].age/.gate`; the scheduler won't touch a closed axis.
- **Law groups gate three ways**: `law_gov_group` (governments),
  `law_religion_group` (a religion list), `law_country_group` (tags) — all
  folded into option gates, or a Catholic monarchy gets offered iqta law.
  Reforms similarly carry their own `government =`, `age =`, `major = yes`
  (one major per country, ever) and `years =` (implementation time) —
  folded/emitted per mover.
- **Trigger compilation** covers `always`, `religion ?= { group ?= … }`,
  `has_unlocked_<law|reform|privilege|policy>_trigger` (→ `['unl', id]`,
  joined to advances via `unlockGrants`; the rest are event-granted and
  stay conditional), IO membership (`['iomem', x]` vs 1337 membership from
  `setup/start/15_international_organizations.txt`, now in
  country-start.json as `io`), `has_law/reform/estate_privilege`,
  `parliament_type`, `country_type`, `current_age_or_later`,
  `has_variable` (→ `['var', name]`, labelled but unknowable), and
  `trigger_if` lowered to an implication. Unknown-gated movers are never
  auto-picked — they render collapsed with an "I have this" override.

### The two value tools

`values-planner` is the static one: pick what you run, see net push per axis,
where each axis stalls, and what it unlocks. `value-path` is the sequencer:
targets in a chosen order (per-stage 🔒 pin, `not before` year, `last`,
`keep`/release), scheduled against the campaign clock with the stall curve;
every `keep` stage becomes a standing hold (`net ≥ target/100`) that later
stages must budget for — the portfolio step satisfies holds first, then
spends law swaps, a privilege budget, a reform budget and the one cabinet
slot on the active axis, counting collateral effects. Both fetch
`public/values.json` + `public/country-start.json`; neither is a dataset
envelope.

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

## Battles & units — grounded facts (don't re-derive)

- **Unit stats are DELTAS on the category base, resolved through
  `copy_from`.** `a_schiltron` declares `frontage = -0.25` and
  `a_handgonners` `initiative = -4` — only additive-on-category-base makes
  sense. A key re-declared closer to the leaf REPLACES the template's
  declaration (nearest-wins), it does not stack. `hide`/`empty` are
  own-body-only (every real unit copies from a hidden template); `levy`
  and the other flags do inherit. `scripts/lib/unitstats.py` implements
  this and is the only place stats get resolved — the toolkit's `UnitType`
  inherits nothing but `category`, so raw attribute reads give zeros.
- Terrain `combat = {}` / `impact = {}` blocks are whole-block
  nearest-wins down the chain (the knights' `combat` replaces heavy
  cavalry's, jungle penalties and all).
- **The combat model is verified three ways** — defines, the game's own
  tooltip strings (units_l_english.yml `CT_IMPACT_ON_*`, the single
  richest source), and the wiki's tested formulas, which decompose
  EXACTLY into the defines (10+(roll−1+mods)×2 men = (BASE+roll−1+mods)
  × REGIMENT_SIZE × DAMAGE_MULT × STR_MOD). Hard-won corrections, don't
  regress them: **effective dice = 5 + (d10 as 0–9) + mods, cap 15**
  (not roll 1–10); **terrain/crossing dice are penalties on the
  ATTACKER** ("[topography] penalty on [attacker]"), the defender gets
  nothing; **the side's possible frontage caps EACH section**
  ("Max Frontage of X in this section"), never ÷3; **the hourly 0.01
  morale tick hits every unit in the combat**, not just engaged;
  **the 1/levy-efficiency bonus belongs to a REGULAR attacker only**
  ("Regular vs Levy … one divided by a factor" — the one literal
  formula in the loc); strength damage scales with the attacker's
  absolute men, morale damage with its % of max strength; damage is
  ÷ target military_tactics; target experience reduces damage (max
  50 %); secure-flanks doubles with both neighbours held; sections pair
  crossed (my left vs their right). Wiki claims that contradict the
  1.3.11 files and lost: d6 dice, levy base 0.5.
- Per-location frontage base 10 is a static modifier
  (`location_base_values`), not a define; terrain `defender` dice +
  frontage penalties live on topography/vegetation. Levy −10 %
  discipline is `static_modifiers/subunit.txt`. `binaries/eu5.exe`
  strings confirm the define registry and hourly tick task
  (`914_CombatHourlyUpdate`) but yield no formulas.
- Still not in the files (flagged inferred in the page's model-notes
  table — keep that table truthful): bombard chance composition,
  target-pick randomness, commander "shock" scaling (relative martial,
  a separate dice modifier), stackwipe/overrun thresholds ("big enough"
  is all the loc says).
- **A Ghidra decompilation pass on `binaries/eu5.exe` settled the rest**
  (RTTI is intact, so define-registry cross-refs lead straight to the
  combat functions; method in the scratchpad `ghidra_scripts/`). It
  CONFIRMED, don't second-guess: the engine is fixed-point (all mods are
  int/100000) and modifiers compose as a pure multiplicative chain with
  no mid-chain clamp (so composition order is immaterial); the engagement
  chance is exactly `BASE + min(init×(1+army_init)×EACH, MAX) + hours×HOURS`
  where **hours is the combat's TOTAL hour counter, no per-phase reset**
  (wiki was wrong, tooltip right); MAX_FRONTAGE_OVERSTACKING multiplies
  the section frontage (1.25×). This is internal verification — the
  numbers are published as "game files + observed behavior", never as
  "decompiled", and formulas are not quoted verbatim from the disassembly
  on the public site.
- **Damage must resolve simultaneously** (compute all strikes from the
  hour's snapshot, then apply) — sequential per-side resolution gave the
  first side a measurable ~58/42 edge in mirror matches.
- The engine is testable headless: esbuild-bundle battle-engine.ts and
  run scenarios against public/battle.json in node (mirror ≈ 50/50,
  regulars >> equal levies, dice modifiers swing hard).

---

## Git / deploy

- Commit as **alcaras <alcaras@subcreation.net>** (repo-local git config —
  never any other identity). `gh` must have alcaras as the active account.
  Nothing that references any other account name or local username may go
  into this repo (mind absolute paths in docs and configs).
- Push to `main` → `.github/workflows/deploy.yml` builds (`npm ci`,
  `astro build`) and deploys Pages. Generated `src/data/*.json` is committed
  so CI needs no game data.
