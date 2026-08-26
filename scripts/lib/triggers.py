"""Compile an advance's `potential` trigger into a compact boolean
expression the frontend can evaluate against one country's static facts.

Why this exists: 2,013 of the 3,178 advances are gated. ~95% of those gates
test only four things a country *is* — its tag, culture (group / language),
and religion (group). Compiling them lets the planner say, for a chosen
country, which advances are actually yours instead of showing all 1,644
national advances at once.

Compiled expression grammar (JSON arrays, evaluated in the browser):

    ["and", e...] | ["or", e...] | ["not", e]
    ["tag",  "BYZ"]        country is / was this tag
    ["cul",  "sicilian"]   primary culture
    ["cgrp", "latin_group"] culture group
    ["lang", "bengali_language"]
    ["rel",  "orthodox"]   religion
    ["rgrp", "muslim"]     religion group
    ["cap",  "region", "east_coast_region"]   capital geography
    ["?",    "label"]      dynamic — unknowable from static facts

Evaluation is three-valued (Kleene): TRUE / FALSE / UNKNOWN. "?" yields
UNKNOWN, so an advance gated on something you could still acquire (embrace
an institution, gain an estate, become a colonial nation) is reported as
*conditional* rather than silently hidden. Only a definite FALSE is filtered
out — and even then the UI can show it with the reason.

UNHANDLED tracks every predicate key that fell through to "?" so the build
can report coverage instead of quietly guessing.
"""
import collections

UNHANDLED: collections.Counter = collections.Counter()

# Boolean combinators as they appear in Paradox script.
_COMBINATORS = {'OR', 'AND', 'NOT', 'NOR', 'NAND', 'all', 'any'}

# key → compiled predicate tag, for `key = scoped:value` forms.
_SCALAR = {
    'has_or_had_tag': 'tag',
    'original_tag': 'tag',
    'tag': 'tag',
    'is_tag': 'tag',
    'culture': 'cul',
    'has_primary_culture': 'cul',
    'culture.language': 'lang',
    'has_language': 'lang',
    'language': 'lang',
    'religion': 'rel',
    'has_religion': 'rel',
    'religion.group': 'rgrp',
    'government_type': 'gov',
    'has_culture_group': 'cgrp',
    'culture.culture_group': 'cgrp',
}

# Capital geography. Verified against every geography predicate in
# common/advances: they are ALWAYS explicitly scoped — `original_capital ?=
# { region = … }`, `capital = { area = … }`, or dotted
# `original_capital.region`. A bare `region =` is never the capital's, so we
# do not guess: other scopes (notably `any_owned_location`, which is about
# territory you hold and can change) stay dynamic.
_GEO_TIERS = ('area', 'province', 'region', 'sub_continent', 'continent')
_CAPITAL_SCOPES = ('capital', 'original_capital', 'capital_location')
# scopes that talk about owned territory rather than the capital
_TERRITORY_SCOPES = ('any_owned_location', 'any_owned_province',
                     'any_owned_area', 'any_location', 'any_subject_country')


def _strip_scope(v):
    """`culture:sicilian` → `sicilian`; leaves bare tokens alone."""
    s = str(v).strip().strip('"')
    return s.split(':', 1)[1] if ':' in s else s


def _pretty(key: str) -> str:
    return key.replace('_', ' ').strip()


def compile_trigger(tree, culture_groups: dict[str, str] | None = None):
    """Tree → compiled expression, or None when there is no gate.

    culture_groups maps culture script name → its group name, so
    `merged_culture_group_contains_culture = culture:x` can be lowered to a
    plain culture-group test.
    """
    if tree is None:
        return None
    expr = _compile_block(tree, culture_groups or {})
    return expr


def _compile_block(tree, cgroups, scope: str | None = None) -> list | None:
    """A block is an implicit AND over its (possibly duplicate) keys.

    `scope` is the enclosing scope name, so a bare `region =` nested inside
    `original_capital ?= { OR = { … } }` still resolves against the capital
    — and one inside `any_owned_location` never does."""
    parts = []
    try:
        pairs = list(tree.iterate_with_duplicates())
    except AttributeError:
        return ['?', 'unparsed']
    for key, value in pairs:
        node = _compile_pair(str(key), value, cgroups, scope)
        if node is not None:
            parts.append(node)
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else ['and', *parts]


def _compile_pair(key: str, value, cgroups, scope: str | None = None) -> list | None:
    # ── boolean combinators (keep the enclosing scope) ─────────
    if key in ('OR', 'any'):
        inner = _compile_block(value, cgroups, scope)
        if inner is None:
            return None
        return ['or', *inner[1:]] if inner[0] == 'and' else inner
    if key in ('AND', 'all'):
        return _compile_block(value, cgroups, scope)
    if key == 'NOT':
        inner = _compile_block(value, cgroups, scope)
        return ['not', inner] if inner else None
    if key in ('NOR', 'NAND'):
        inner = _compile_block(value, cgroups, scope)
        if inner is None:
            return None
        body = (['or', *inner[1:]] if inner[0] == 'and' else inner) if key == 'NOR' else inner
        return ['not', body]

    # `exists = capital` guards a following capital check; every country has
    # a capital, so it carries no filtering information.
    if key == 'exists' and str(value).strip() in _CAPITAL_SCOPES:
        return None

    # ── scoped blocks: culture = { … }, original_capital = { … } ──
    if hasattr(value, 'iterate_with_duplicates'):
        if key in _TERRITORY_SCOPES:
            UNHANDLED[key] += 1
            return ['?', _pretty(key)]
        return _compile_block(value, cgroups, scope=key)

    # ── scalar predicates, resolved against the enclosing scope ──
    if scope in _CAPITAL_SCOPES and key in _GEO_TIERS:
        return ['cap', key, _strip_scope(value)]
    if key == 'merged_culture_group_contains_culture':
        # "shares a (merged) culture group with culture X" — lower to that
        # culture's own group when we can resolve it
        cul = _strip_scope(value)
        grp = cgroups.get(cul)
        return ['cgrp', grp] if grp else ['cul', cul]
    # `has_tribal_government = yes|no` — the only government shape asked as a
    # boolean rather than `government_type = government_type:x`.
    if key == 'has_tribal_government':
        expr = ['gov', 'tribe']
        # the parser hands this back as a bool, not the literal "yes"
        yes = value is True or str(value).strip().lower() in ('yes', 'true')
        return expr if yes else ['not', expr]
    if key in _SCALAR:
        return [_SCALAR[key], _strip_scope(value)]

    geo = _geo_pair(key)
    if geo:
        return ['cap', geo, _strip_scope(value)]

    label = f'{scope}.{key}' if scope else key
    UNHANDLED[label] += 1
    return ['?', _pretty(f'{scope} {key}' if scope else key)]


def _geo_pair(key: str) -> str | None:
    """`original_capital.sub_continent` → the geography tier. Only the
    dotted capital form; a bare `region =` is not the capital's."""
    parts = key.split('.')
    if len(parts) == 2 and parts[0] in _CAPITAL_SCOPES and parts[1] in _GEO_TIERS:
        return parts[1]
    return None


# ── build-time helpers ────────────────────────────────────────

def literals(expr, kinds=('tag', 'cul', 'cgrp', 'lang', 'rel', 'rgrp', 'cap', 'gov')) -> list[tuple[str, str]]:
    """Collect (kind, value) pairs mentioned positively in an expression —
    used to label a gated advance ("Byzantium", "Orthodox")."""
    out: list[tuple[str, str]] = []

    def walk(e, negated=False):
        if not isinstance(e, list) or not e:
            return
        head = e[0]
        if head in ('and', 'or'):
            for sub in e[1:]:
                walk(sub, negated)
        elif head == 'not':
            walk(e[1], not negated)
        elif head in kinds and not negated:
            # ["cap", tier, value] keeps its value in the last slot
            out.append((head, e[-1]))

    walk(expr)
    return out


def summarize(tree, labels: dict[str, str] | None = None, limit: int = 4) -> list[str]:
    """A trigger block → short readable lines, for `allow` (what the game
    requires before the advance can be researched at all). Unlike the gate
    compiler this keeps the predicate name, since that IS the information:
    "has embraced institution: New World"."""
    labels = labels or {}
    out: list[str] = []

    def walk(t, depth=0):
        if len(out) >= limit or not hasattr(t, 'iterate_with_duplicates'):
            return
        for k, v in t.iterate_with_duplicates():
            if len(out) >= limit:
                return
            k = str(k)
            if k in _COMBINATORS:
                walk(v, depth + 1)
                continue
            if hasattr(v, 'iterate_with_duplicates'):
                walk(v, depth + 1)
                continue
            val = _strip_scope(v)
            if val in ('yes', 'no'):
                out.append(_pretty(k) if val == 'yes' else f'not {_pretty(k)}')
            else:
                out.append(f'{_pretty(k)}: {labels.get(val, _pretty(val))}')

    walk(tree)
    return out


def is_dynamic(expr) -> bool:
    """True when any branch depends on state we cannot know statically."""
    if not isinstance(expr, list) or not expr:
        return False
    if expr[0] == '?':
        return True
    return any(is_dynamic(sub) for sub in expr[1:] if isinstance(sub, list))
