"""eu5ref data-layer foundation.

Every build script goes through this module. It bootstraps the vendored
PyHelpersForPDXWikis EU5 parser (which reads the game dump at the repo root)
and provides the four abstractions the whole site is built on:

1. Entity envelope  — every dataset JSON is {dataset, entities: [Entity]},
   where Entity = {id, type, slug, name, desc?, color?, facets?, mods?, data}.
   `id` is globally unique ("good:horses", "concept:stability") so links,
   search, and backlinks work across datasets.

2. Mod             — a rendered modifier {key, label, value, polarity}.
   Values are formatted HERE (game's own format strings: %, decimals, +/−)
   so the frontend never interprets numbers. polarity is good|bad|neutral.

3. Rich text       — localization strings are tokenized to a stream of
   ["t", text] and ["r", entity_id, label] tokens. `[concept|e]` markup
   becomes real links; `$KEY$` nesting is resolved; `#format ... #!` and
   icon markup are stripped to their text. The frontend just maps tokens.

4. write_dataset   — deterministic JSON output (sorted keys, LF) so patch
   diffs are meaningful and the changelog can diff snapshots.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'PyHelpersForPDXWikis'))

from eu5.game import eu5game  # noqa: E402

parser = eu5game.parser
DATA_DIR = ROOT / 'src' / 'data'


# ── ids & slugs ─────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"['’]", '', s)
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s


def eid(etype: str, key: str) -> str:
    """Global entity id: type prefix + the game's own script key."""
    return f'{etype}:{key}'


# ── colors ──────────────────────────────────────────────────────────────

def hex_color(pdx_color) -> str | None:
    """PdxColor (or None) → '#rrggbb'."""
    if pdx_color is None:
        return None
    try:
        h = pdx_color.get_rgb_hex()
        return h if h.startswith('#') else f'#{h}'
    except Exception:
        return None


# ── modifiers ───────────────────────────────────────────────────────────

_POLARITY = {'green': 'good', 'red': 'bad'}


def mod_json(key: str, value) -> dict:
    """One game modifier → Mod dict. Unknown keys still render (honest
    fallback: raw key + raw value, neutral) rather than vanishing —
    the audit script reports them so they can be promoted."""
    mt = parser.modifier_types.get(key)
    if mt is None:
        return {'key': key, 'label': key, 'value': str(value), 'polarity': 'neutral',
                'unresolved': True}
    try:
        formatted = mt.format_value_without_color(value)
    except Exception:
        formatted = str(value)
    try:
        polarity = _POLARITY.get(mt.get_color_for_value(value), 'neutral')
    except Exception:
        polarity = 'neutral'
    # mt.icon is display_name with wiki link/icon markup stripped
    label = plain_text(mt.icon)
    return {'key': key, 'label': label, 'value': formatted, 'polarity': polarity}


def mods_from_tree(tree) -> list[dict]:
    """A script `modifier = { ... }` block (Tree, dict or list of Modifier
    objects) → [Mod]."""
    out = []
    if tree is None:
        return out
    if isinstance(tree, list):  # already-parsed Modifier objects
        for m in tree:
            out.append(mod_json(m.name, m.value))
        return out
    for k, v in tree:
        out.append(mod_json(k, v))
    return out


# ── rich text (localization markup → token stream) ──────────────────────

_concept_aliases: dict[str, str] | None = None


def concept_alias_map() -> dict[str, str]:
    """alias name → canonical concept script key (includes identity map)."""
    global _concept_aliases
    if _concept_aliases is None:
        m = {}
        for name, c in parser.game_concepts.items():
            if getattr(c, 'is_alias', False):
                continue
            m[name] = name
            for a in c.alias:
                m[a] = name
        _concept_aliases = m
    return _concept_aliases


_RE_FORMAT = re.compile(r'#\S*? (.*?)#!', re.DOTALL)   # "#b text#!" → "text"
_RE_ICON = re.compile(r'£[^£\s]*£\s?|@[!-~]+?!\s?')     # inline icons → drop
_RE_LOCKEY = re.compile(r'\$([A-Za-z0-9_.|+=%*-]+)\$')
_RE_BRACKET = re.compile(r'\[([^\[\]]+)\]')
# a bare script id left in prose (`byz_andronikos_ii_palaiologos`) — three or
# more snake_case segments never occur in real sentences
_RE_BARE_ID = re.compile(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+){2,}\b')
# a scope call the toolkit already unwrapped from its brackets, leaving
# `Target_Character.GetNameWithNoTooltip` sitting in the prose
_RE_BARE_SCOPE = re.compile(r'\b([A-Za-z][\w]*)\.(?:Get|Show)\w+\b')


def _resolve_lockeys(text: str, depth: int = 0) -> str:
    def sub(m):
        key = m.group(1).split('|')[0]
        if depth < 3:
            val = parser.localize(key, return_none_instead_of_default=True)
            if val is not None and f'${key}$' not in val:
                return _resolve_lockeys(val, depth + 1)
        return ''  # runtime variable ($VAL$ etc.) — drop
    return _RE_LOCKEY.sub(sub, text)


# Scope names the toolkit leaves behind. ROOT is the country the text is
# about, which reads better than the raw token.
_SCOPE_WORDS = {'root': 'our country', 'prev': 'it', 'this': 'it', 'from': 'them'}


def _scope_label(scope: str) -> str:
    tail = scope.split('_')[-1].lower()
    if tail in _SCOPE_WORDS:
        return _SCOPE_WORDS[tail]
    return pretty(scope)


def _bracket_to_token(inner: str):
    """One [ ... ] command → token. `x|e` → concept ref; scope functions
    like COUNTRY.GetName → readable placeholder text."""
    body = inner.split('|')[0].strip()
    concepts = parser.game_concepts
    key = body.lower()
    canonical = concept_alias_map().get(key)
    if canonical:
        label = concepts[key].display_name if key in concepts else concepts[canonical].display_name
        return ['r', eid('concept', canonical), label]
    # A bare icon reference (`[advance_icon]`) is decoration, not a word —
    # concepts whose own name ends in _icon were already resolved above.
    if key.endswith('_icon'):
        return ['t', '']
    # Scope lookups like `GetCountry('BYZ').GetName` or
    # `GetCharacter('byz_andronikos_iii').GetNicknameWithNoTooltip` — render
    # the thing being named, not the call.
    # Get…('x') and Show…('x') both name a thing; render the thing.
    m = re.match(r"(?:Get|Show)\w+\(\s*'([^']+)'\s*\)", body)
    if m:
        key = m.group(1)
        try:
            resolved = label_map().get(key)
        except Exception:
            resolved = None
        return ['t', resolved or pretty(key.replace("'", ''))]
    if '.' in body:  # other scope function — humanize the scope name
        scope = body.split('.')[0].replace('_', ' ').strip()
        return ['t', scope.title() if scope.isupper() or scope.islower() else scope]
    return ['t', body]


def rich(text: str | None) -> list | None:
    """Localized string → token stream [[t,...],[r,id,label],...] or None."""
    if not text:
        return None
    s = _resolve_lockeys(text)
    s = _RE_FORMAT.sub(r'\1', s)
    s = _RE_ICON.sub('', s)
    s = s.replace('\\n', '\n')
    # chained calls (`x.GetGovernment.GetName`) need more than one pass
    for _ in range(4):
        s2 = _RE_BARE_SCOPE.sub(lambda m: _scope_label(m.group(1)), s)
        if s2 == s:
            break
        s = s2
    s = _RE_BARE_ID.sub(lambda m: pretty(m.group(0)), s)
    tokens = []
    pos = 0
    for m in _RE_BRACKET.finditer(s):
        if m.start() > pos:
            tokens.append(['t', s[pos:m.start()]])
        tokens.append(_bracket_to_token(m.group(1)))
        pos = m.end()
    if pos < len(s):
        tokens.append(['t', s[pos:]])
    # merge adjacent text tokens, drop empties
    merged = []
    for t in tokens:
        if t[0] == 't' and merged and merged[-1][0] == 't':
            merged[-1][1] += t[1]
        elif t[0] != 't' or t[1]:
            merged.append(t)
    return merged or None


def plain_text(text: str | None) -> str:
    """Localized string → plain string (all markup stripped)."""
    toks = rich(text)
    if not toks:
        return ''
    return ''.join(t[2] if t[0] == 'r' else t[1] for t in toks).strip()


# ── gate labels ─────────────────────────────────────────────────────────

_label_map: dict[str, str] | None = None


def label_map() -> dict[str, str]:
    """script name → display name, for saying what a gate demands
    ("BYZ" → "Byzantium", "orthodox" → "Orthodoxy"). Cached; used by every
    builder that compiles a `potential` trigger."""
    global _label_map
    if _label_map is None:
        m: dict[str, str] = {}
        for tag, c in parser.countries.items():
            m[tag] = c.display_name
        for group in ('cultures', 'culture_groups', 'languages', 'religions',
                      'religion_groups', 'areas', 'regions', 'sub_continents',
                      'continents', 'provinces', 'institution', 'estates',
                      'government_reforms', 'societal_values', 'subject_types',
                      'buildings', 'unit_types'):
            try:
                for k, v in getattr(parser, group).items():
                    m.setdefault(k, getattr(v, 'display_name', None) or pretty(k))
            except Exception:
                continue
        _label_map = m
    return _label_map


def gate_of(obj, *fields: str) -> tuple[list | None, list[str]]:
    """Compile the first present trigger field into (expr, labels)."""
    import triggers
    labels = label_map()
    for f in fields:
        v = getattr(obj, f, None)
        if v is None or not hasattr(v, 'iterate_with_duplicates'):
            continue
        expr = triggers.compile_trigger(v, culture_group_keys())
        if not expr:
            continue
        seen, out = set(), []
        for _, val in triggers.literals(expr):
            lab = labels.get(val) or pretty(val)
            if lab not in seen:
                seen.add(lab)
                out.append(lab)
        return expr, out
    return None, []


_cgroup_keys: dict[str, str] | None = None


def culture_group_keys() -> dict[str, str]:
    """culture script name → its (first) culture group script name."""
    global _cgroup_keys
    if _cgroup_keys is None:
        out = {}
        for name, c in parser.cultures.items():
            groups = getattr(c, 'culture_groups', None) or []
            if groups:
                out[name] = groups[0].name
        _cgroup_keys = out
    return _cgroup_keys


# ── icons ───────────────────────────────────────────────────────────────

IMG_DIR = ROOT / 'public' / 'img'


def export_icon(entity_obj, etype: str, slug: str) -> str | None:
    """Convert the entity's game icon (.dds, via the toolkit's IconMixin →
    NGameIcons defines → gfx/interface/...) to a PNG under public/img/<etype>/
    and return the web-relative path, or None when the game has no icon.
    Output is named by the SOURCE file stem so entities sharing an icon share
    one PNG. Conversion is skipped when the PNG is newer than the source."""
    try:
        src = entity_obj.get_icon_path()
    except Exception:
        return None
    if src is None:
        return None
    src = Path(src)
    if not src.exists():
        return None
    stem = slugify(src.stem) or slug
    out = IMG_DIR / etype / f'{stem}.png'
    web = f'img/{etype}/{stem}.png'
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return web
    out.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    img = Image.open(src).convert('RGBA')
    if max(img.size) > 64:
        img.thumbnail((64, 64), Image.LANCZOS)
    img.save(out)
    return web


# ── output ──────────────────────────────────────────────────────────────

def write_dataset(name: str, payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / f'{name}.json'
    out.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=1) + '\n',
                   encoding='utf-8')
    n = len(payload.get('entities', []))
    print(f'  {out.relative_to(ROOT)}: {n} entities')


def facet_meta(entities: list[dict], defs: list[tuple[str, str]]) -> list[dict]:
    """Compute facet option lists (with counts) from emitted entities.
    defs = [(facet_key, 'Facet Label'), ...]."""
    out = []
    for key, label in defs:
        counts: dict[str, int] = {}
        for e in entities:
            v = (e.get('facets') or {}).get(key)
            if v is None:
                continue
            vs = v if isinstance(v, list) else [v]
            for one in vs:
                counts[one] = counts.get(one, 0) + 1
        options = [{'value': v, 'label': pretty(v), 'count': c}
                   for v, c in sorted(counts.items())]
        out.append({'key': key, 'label': label, 'options': options})
    return out


_ROMAN = {'ii', 'iii', 'iv', 'vi', 'vii', 'viii', 'ix', 'xi', 'xii', 'xiii', 'xiv'}


def pretty(v: str) -> str:
    """Prettify a script token for display — but leave already-humanized
    strings (anything with uppercase or spaces) untouched. Regnal numerals
    are restored ("andronikos_ii" → "Andronikos II", not "Ii")."""
    s = str(v)
    if not s.islower():
        return s
    words = s.replace('_', ' ').split()
    return ' '.join(w.upper() if w in _ROMAN else w.title() for w in words)


def ename(obj) -> str | None:
    """display_name of a toolkit entity (or None)."""
    return obj.display_name if obj is not None else None


def ref_list(objs, etype: str) -> list[dict]:
    """Toolkit entities → [{id, label}] for EntityTable kind 'refs'."""
    out = []
    for o in objs or []:
        if o is None:
            continue
        out.append({'id': eid(etype, o.name), 'label': o.display_name})
    return out
