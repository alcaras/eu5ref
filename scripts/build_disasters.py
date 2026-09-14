"""in_game/common/disasters → src/data/disasters.json.

A disaster is the one mechanic in the game that sets you a numeric goal and
then never shows you the number. 13 of the 36 snapshot a **target variable** in
`on_start` — computed from your own state at the moment the disaster fires,
frozen for its whole run — and 10 of those are read back by the `can_end`
trigger as the bar you have to clear. The panel in game shows estate pie charts and a prose checklist; the
number itself is nowhere on screen.

So this builder keeps, per disaster:

  start / end   the `can_start` and `can_end` triggers as sentences. Every
                `can_end` in the game is a single scripted trigger, so the
                body is inlined first — "rise of the szlachta end trigger"
                is not a requirement, it is a function name.
  end_routes    the `can_end` OR split into one route per way out, each
                carrying the target variables it reads.
  targets       the `on_start` `set_variable` formulas (scripts/lib/
                scriptvalue.py), as text and as an op list the browser can
                evaluate — that is the exit-target calculator on the page.
  outcomes      the `on_end` if/else chain, in order, each pointing at the
                real event id so it links to the event page.
  monthly       the `on_monthly` random_list weights as a per-month chance.
                The visible `9 / 91` pair is a tooltip, not the roll; the
                roll is the list inside `hidden_effect`. Both are emitted,
                labelled for what they are.
  actions       the `generic_actions` of `type = disaster` that name this
                disaster in their `select_trigger`, with price and cooldown.
"""
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ref
import requirements
import scriptvalue
import triggers
from build_events import effect_lines
from ref import (eid, export_icon, facet_meta, mods_from_tree, rich, slugify,
                 write_dataset)

LIMIT = 14          # requirement lines per block — disasters are wordy
_VAR = re.compile(r'var:([a-z_0-9]+)')
_EVENT_ID = re.compile(r'^[a-z_0-9]+\.[0-9]+$')

# ── small tree helpers ──────────────────────────────────────────────────

def pairs(tree) -> list:
    try:
        return list(tree.iterate_with_duplicates())
    except AttributeError:
        return []


def get(tree, want: str):
    for k, v in pairs(tree):
        if str(k) == want:
            return v
    return None


def flat_text(tree) -> str:
    """A subtree as one string, for cheap scans (which variables it reads)."""
    out = []

    def walk(t, depth=0):
        if depth > 8:
            return
        for k, v in pairs(t) or []:
            out.append(str(k))
            if hasattr(v, 'iterate_with_duplicates'):
                walk(v, depth + 1)
            else:
                out.append(str(v))
    if hasattr(tree, 'iterate_with_duplicates'):
        walk(tree)
    else:
        out.append(str(tree))
    return ' '.join(out)


class Pairs:
    """A walkable tree built from an explicit key/value list."""
    def __init__(self, items):
        self._items = list(items)

    def iterate_with_duplicates(self):
        yield from self._items


# ── can_end: inline the scripted trigger, then split the ways out ───────

def inline_end(tree):
    """`can_end = { x_end_trigger = yes }` → the body of x_end_trigger.

    Returns (tree, scripted trigger name or None)."""
    ps = pairs(tree)
    if len(ps) == 1:
        key, value = ps[0]
        if not hasattr(value, 'iterate_with_duplicates') \
                and str(value) in ('yes', 'True'):
            body = triggers._scripted().get(str(key))
            if body is not None:
                return body, str(key)
    return tree, None


def display_only_if(limit, snapshot: set[str]) -> bool:
    """Is this `trigger_if` the game guarding against a missing variable?

    The pattern is always the same: `trigger_if = { limit = { has_variable =
    <the on_start variables> } … }` with a `trigger_else` that repeats the
    same conditions as `custom_tooltip`s, for the frame before `on_start`
    has run. The if-branch is the real rule, so the else twin is dropped —
    and only when every variable it names is one this disaster's own
    `on_start` sets."""
    ps = pairs(limit)
    if not ps:
        return False
    for k, v in ps:
        if str(k) != 'has_variable' or str(v) not in snapshot:
            return False
    return True


def resolve_branches(tree, snapshot: set[str]):
    """(shared conditions tree, [branch trees], note) for a can_end body."""
    ps = pairs(tree)
    # step past a variables-exist guard, dropping its display-only twin
    for k, v in ps:
        if str(k) == 'trigger_if' and display_only_if(get(v, 'limit'), snapshot):
            inner = [(k2, v2) for k2, v2 in pairs(v) if str(k2) != 'limit']
            return resolve_branches(Pairs(inner), snapshot)
    shared, branches = [], None
    for k, v in ps:
        key = str(k)
        if key in ('OR', 'any') and branches is None \
                and hasattr(v, 'iterate_with_duplicates'):
            branches = pairs(v)
        else:
            shared.append((k, v))
    return Pairs(shared), branches


def end_routes(tree, snapshot: set[str]) -> tuple[list[dict], list[str]]:
    """[{lines, targets}] — one route per way the disaster can end."""
    shared_tree, branches = resolve_branches(tree, snapshot)
    shared = requirements.describe(shared_tree, limit=LIMIT)['lines']
    routes = []
    skip_else = False
    for k, v in (branches or []):
        key = str(k)
        # a branch can carry the same variables-exist guard as the whole
        # trigger; its `trigger_else` twin is the display-only fallback
        if key in ('trigger_else', 'trigger_else_if') and skip_else:
            skip_else = False
            continue
        skip_else = False
        if key == 'trigger_if' and display_only_if(get(v, 'limit'), snapshot):
            v = Pairs([(k2, v2) for k2, v2 in pairs(v) if str(k2) != 'limit'])
            skip_else = True
        desc = requirements.describe(Pairs([('AND', v)]) if key == 'trigger_if'
                                     else Pairs([(k, v)]), limit=LIMIT)
        lines = list(desc['lines']) + [requirements.negated(x) for x in desc['excludes']]
        if not lines:
            continue
        used = sorted(set(_VAR.findall(flat_text(v))))
        routes.append({'lines': lines, 'targets': used})
    if not routes:
        # no OR: every condition has to hold, so there is one way out
        desc = requirements.describe(tree, limit=LIMIT)
        lines = list(desc['lines']) + [requirements.negated(x) for x in desc['excludes']]
        if lines:
            routes = [{'lines': lines,
                       'targets': sorted(set(_VAR.findall(flat_text(tree))))}]
        shared = []
    return routes, shared


# ── on_end: which event fires, and under what ───────────────────────────

def event_ref(value) -> str | None:
    """`trigger_event_non_silently = x.8` / `{ id = x.8 days = … }` → the id."""
    if hasattr(value, 'iterate_with_duplicates'):
        value = get(value, 'id')
    if value is None:
        return None
    name = str(value).strip()
    return name if _EVENT_ID.match(name) else None


def outcomes(tree, conds: list[str] | None = None, depth: int = 0) -> list[dict]:
    conds = conds or []
    out: list[dict] = []
    if depth > 5:
        return out
    for k, v in pairs(tree):
        key = str(k)
        nested = hasattr(v, 'iterate_with_duplicates')
        if key in ('if', 'else_if') and nested:
            limit = get(v, 'limit')
            body = Pairs([(k2, v2) for k2, v2 in pairs(v) if str(k2) != 'limit'])
            desc = requirements.describe(limit, limit=LIMIT) if limit is not None else None
            extra = (desc['lines'] + [requirements.negated(x)
                                      for x in desc['excludes']]) if desc else []
            out += outcomes(body, conds + extra, depth + 1)
        elif key == 'else' and nested:
            out += outcomes(v, conds + ['otherwise'], depth + 1)
        elif key.startswith('trigger_event'):
            name = event_ref(v)
            if name:
                out.append({'conditions': conds, 'event': name})
        elif nested:
            out += outcomes(v, conds, depth + 1)
    return out


# ── on_monthly: the rolls ───────────────────────────────────────────────

def first_event(tree, depth: int = 0) -> str | None:
    if depth > 4:
        return None
    for k, v in pairs(tree):
        key = str(k)
        if key.startswith('trigger_event'):
            name = event_ref(v)
            if name:
                return name
        if hasattr(v, 'iterate_with_duplicates'):
            found = first_event(v, depth + 1)
            if found:
                return found
    return None


def tooltip_key(body) -> str:
    """The loc key of a `custom_tooltip`, or '' when there is none.

    A tooltip is written either as `custom_tooltip = some_key` or as
    `custom_tooltip = { text = some_key <triggers> }`. Only the key is wanted
    here, to tell the cosmetic `an_event_occurs_tt` pair from the real roll.
    str() on the block form would leave a Python repr in the data, so the
    block is read for its `text` and anything else yields ''.
    """
    v = get(body, 'custom_tooltip')
    if v is None:
        return ''
    if hasattr(v, 'iterate_with_duplicates'):
        v = get(v, 'text')
        if v is None or hasattr(v, 'iterate_with_duplicates'):
            return ''
    if isinstance(v, (list, tuple)):
        return ''
    return str(v)


def monthly_rolls(tree) -> list[dict]:
    """Every `random_list` / `random` in `on_monthly`, as real chances."""
    rolls: list[dict] = []

    def walk(t, hidden: bool, depth: int = 0):
        if depth > 5:
            return
        for k, v in pairs(t):
            key = str(k)
            if key == 'random_list' and hasattr(v, 'iterate_with_duplicates'):
                entries, total = [], 0.0
                for weight, body in pairs(v):
                    try:
                        w = float(str(weight))
                    except ValueError:
                        continue
                    total += w
                    gate = get(body, 'trigger') if hasattr(body, 'iterate_with_duplicates') else None
                    entries.append({
                        'weight': w,
                        'event': first_event(body) if hasattr(body, 'iterate_with_duplicates') else None,
                        'tooltip': tooltip_key(body)
                                   if hasattr(body, 'iterate_with_duplicates') else '',
                        'only_if': requirements.describe(gate, limit=4)['lines'] if gate is not None else [],
                    })
                if total <= 0:
                    continue
                for e in entries:
                    e['chance'] = round(e['weight'] / total, 6)
                # the cosmetic pair (`an_event_occurs_tt` / `no_event_occurs_tt`)
                # states a chance the real roll below does not have to match
                shown = sum(e['chance'] for e in entries
                            if e['tooltip'] == 'an_event_occurs_tt')
                rolls.append({
                    'kind': 'roll' if any(e['event'] for e in entries) else 'tooltip',
                    'hidden': hidden,
                    'entries': [e for e in entries if e['event']],
                    'shown_chance': round(shown, 6) if shown else None,
                    'nothing': round(sum(e['weight'] for e in entries if not e['event']) / total, 6),
                })
            elif key == 'random' and hasattr(v, 'iterate_with_duplicates'):
                chance = get(v, 'chance')
                name = first_event(v)
                if name and chance is not None:
                    rolls.append({'kind': 'roll', 'hidden': hidden, 'nothing': None,
                                  'entries': [{'weight': float(str(chance)),
                                               'chance': round(float(str(chance)) / 100, 6),
                                               'event': name, 'only_if': []}]})
            elif key == 'hidden_effect' and hasattr(v, 'iterate_with_duplicates'):
                walk(v, True, depth + 1)
            elif hasattr(v, 'iterate_with_duplicates'):
                walk(v, hidden, depth + 1)

    walk(tree, False)
    return rolls


# ── the disaster's own actions ──────────────────────────────────────────

class Labels(dict):
    """label_map that also answers a prefixed key (`estate_type:nobles_estate`),
    which is how effect blocks name their subject."""

    def get(self, key, default=None):
        v = super().get(key)
        if v is None and ':' in str(key):
            v = super().get(str(key).split(':', 1)[1])
        return default if v is None else v


def unwrap(effect):
    """A disaster action's effect is wrapped in `scope:actor = { … }`; the
    wrapper is plumbing, the block inside is the action."""
    tree = getattr(effect, 'tree', None) or effect
    for _ in range(3):
        ps = pairs(tree)
        if len(ps) == 1 and str(ps[0][0]) in ('scope:actor', 'root', 'this', 'hidden_effect') \
                and hasattr(ps[0][1], 'iterate_with_duplicates'):
            tree = ps[0][1]
        else:
            break
    return tree


def action_index() -> dict[str, list[dict]]:
    """disaster key → the generic actions that target it.

    A disaster action names its disaster in `select_trigger.visible`
    (`disaster_type = disaster_type:rise_of_the_szlachta`); nothing links
    back from the disaster itself."""
    labels = Labels(ref.label_map())
    out: dict[str, list[dict]] = {}
    try:
        actions = ref.parser.generic_actions
    except Exception as exc:
        print(f'  generic actions unavailable: {exc}')
        return out
    for name, a in sorted(actions.items()):
        if str(getattr(a, 'type', '')) != 'disaster':
            continue
        st = getattr(a, 'select_trigger', None)
        targets = set()
        for tree in (st if isinstance(st, list) else [st]):
            if tree is None:
                continue
            text = flat_text(get(tree, 'visible') or tree)
            targets |= set(re.findall(r'disaster_type:([a-z_0-9]+)', text))
        if not targets:
            continue
        cooldown = getattr(a, 'cooldown', None)
        years = get(cooldown, 'years') if cooldown is not None else None
        shared = get(cooldown, 'type') if cooldown is not None else None
        lines, _keys = effect_lines(unwrap(getattr(a, 'effect', None)), labels)
        entry = {
            'id': name,
            'name': a.display_name,
            'desc': rich(getattr(a, 'description', None)),
            'price': price_of(getattr(a, 'price', None)),
            'cooldown_years': float(str(years)) if years is not None else None,
            'cooldown_shared_with': str(shared) if shared is not None else None,
            'requires': requirements.describe(getattr(a, 'allow', None), limit=8)['lines'],
            'effects': [resolve_constants(x) for x in lines[:8]],
        }
        for t in targets:
            out.setdefault(t, []).append(entry)
    return out


_CONST_TOKEN = re.compile(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+){2,}\b')


def resolve_constants(line: str) -> str:
    """An effect line can carry a named constant where a number belongs
    (`Wave Of Humanism Modifier (modifier_duration_years_normal years)`).
    The game defines it as a script value, so say the number."""
    def sub(m):
        n = scriptvalue.constant(m.group(0))
        return f'{n:g}' if n is not None else m.group(0)
    return _CONST_TOKEN.sub(sub, line)


def price_of(price) -> list[dict]:
    """`price:x` → [{resource, value}] from common/prices."""
    if price is None:
        return []
    key = str(price).split(':', 1)[-1]
    p = ref.parser.prices.get(key)
    if p is None:
        n = scriptvalue.constant(key)
        return [{'resource': 'gold', 'value': n}] if n is not None else []
    out = []
    for cost in getattr(p, 'costs', []) or []:
        res = getattr(cost, 'resource', None)
        out.append({'resource': ref.pretty(getattr(res, 'value', None) or str(res)),
                    'value': getattr(cost, 'value', None)})
    return out


# ── the rest of the envelope ────────────────────────────────────────────

def spawn_chance(sv) -> tuple[float | None, str | None]:
    """The `monthly_spawn_chance` script value → (number, its own name)."""
    if sv is None:
        return None, None
    name = getattr(sv, 'name', None)
    value = getattr(sv, 'direct_value', None)
    if value is None:
        value = getattr(sv, 'value', None)
    if isinstance(value, str):
        value = scriptvalue.constant(value)
    if not isinstance(value, (int, float)) and name:
        value = scriptvalue.constant(name)
    return (float(value) if isinstance(value, (int, float)) else None,
            str(name) if name else None)


def median_months(p: float | None) -> int | None:
    """Months for a coin that lands with chance p each month to have landed
    half the time. Derived from the spawn chance — the game states neither
    this nor a mean."""
    if not p or p <= 0 or p >= 1:
        return None
    return math.ceil(math.log(0.5) / math.log(1 - p))


AGE_KEYS = ('current_age', 'current_age_or_later')


def ages_of(tree) -> list[str]:
    names, seen = [], set()
    text = flat_text(tree)
    for key in re.findall(r'age_[0-9]_[a-z]+', text):
        if key in seen:
            continue
        seen.add(key)
        age = ref.parser.age.get(key) if hasattr(ref.parser, 'age') else None
        names.append(getattr(age, 'display_name', None) or ref.pretty(key))
    return names


def countries_of(tree) -> list[dict]:
    """The tags a disaster's `can_start` names, as entity refs."""
    gate = triggers.compile_trigger(tree, ref.culture_group_keys())
    out, seen = [], set()
    for kind, value in triggers.literals(gate or [], kinds=('tag',)):
        if value in seen:
            continue
        seen.add(value)
        out.append({'id': eid('country', value), 'label': requirements._label(value)})
    return out


def main():
    disasters = ref.parser.disasters
    actions = action_index()
    entities = []

    for key, d in sorted(disasters.items()):
        slug = slugify(key)
        start = requirements.describe(getattr(d, 'can_start', None), limit=LIMIT)
        end_tree, end_trigger = inline_end(getattr(d, 'can_end', None))
        targets = scriptvalue.set_variables(getattr(d, 'on_start', None))
        routes, shared = end_routes(end_tree, set(targets))
        end_all = requirements.describe(Pairs(pairs(resolve_branches(end_tree, set(targets))[0])),
                                        limit=LIMIT)
        chance, chance_key = spawn_chance(getattr(d, 'monthly_spawn_chance', None))
        countries = countries_of(getattr(d, 'can_start', None))
        ages = ages_of(getattr(d, 'can_start', None))
        rolls = monthly_rolls(getattr(d, 'on_monthly', None))
        ends = outcomes(getattr(d, 'on_end', None))
        opening = [o for o in outcomes(getattr(d, 'on_start', None))]

        # a target only matters to the player if some exit route reads it
        read = {t for r in routes for t in r['targets']}
        target_list = [{
            'name': name,
            'label': scriptvalue.var_label(name),
            'formula': v['formula'],
            'ops': v['ops'],
            'inputs': v['inputs'],
            'snapshot': bool(v['inputs']),
            'read_by_exit': name in read,
            **({'unresolved': True} if v.get('unresolved') else {}),
        } for name, v in targets.items()]
        snapshot = [t for t in target_list if t['snapshot'] and t['read_by_exit']]

        entities.append({
            'id': eid('disaster', key),
            'type': 'disaster',
            'slug': slug,
            'icon': export_icon(d, 'disaster', slug),
            # the toolkit leaves a character/country lookup in some names
            # (`Curse of ser_stefan_decanski`) — the same markup every other
            # string on the site goes through
            'name': ref.plain_text(d.display_name) or d.display_name,
            'desc': rich(getattr(d, 'description', None)),
            'color': None,
            'facets': {
                'who': [c['label'] for c in countries] or ['Any country'],
                'age': ages or None,
                'repeats': 'Fires once' if getattr(d, 'fire_only_once', False)
                           else 'Can fire again',
                'exit': 'Target set when it fires' if snapshot else 'Fixed exit conditions',
            },
            'mods': mods_from_tree(getattr(d, 'modifier', None)),
            'data': {
                'spawn_chance': round(chance, 6) if chance is not None else None,
                'spawn_chance_key': chance_key,
                'median_months': median_months(chance),
                'fire_only_once': bool(getattr(d, 'fire_only_once', False)),
                'map_mode': getattr(d, 'map_mode', None),
                'countries': countries,
                'ages': ages,
                'start': start['lines'] + start['excludes_full'],
                'start_excludes': start['excludes'],
                'end': shared + [' and '.join(r['lines']) for r in routes],
                'end_excludes': end_all['excludes'],
                'end_trigger': end_trigger,
                'end_shared': shared,
                'end_routes': routes,
                'targets': target_list,
                'outcomes': ends,
                'opening': opening,
                'monthly': rolls,
                'actions': actions.get(key, []),
                'availability': start['availability'],
                'requires': start['tags'],
            },
        })

    # every route must say something, or the page lies by omission
    empty = [e['id'] for e in entities if not e['data']['end_routes']]
    if empty:
        print(f'  WARNING: no exit conditions rendered for {", ".join(empty)}')
    fell = requirements.FELL_THROUGH
    if fell:
        top = ', '.join(f'{k} ×{n}' for k, n in fell.most_common(8))
        print(f'  predicates left in their own script terms: '
              f'{sum(fell.values())} across {len(fell)} keys — {top}')
    ok, total = scriptvalue.run_checks()
    print(f'  scriptvalue: {ok}/{total} checks pass, '
          f'{scriptvalue.COVERAGE["lowered"]} values lowered, '
          f'{scriptvalue.COVERAGE["unresolved"]} partly unresolved')
    with_targets = sum(1 for e in entities if e['facets']['exit'].startswith('Target'))
    print(f'  {with_targets} disasters snapshot an exit target')

    write_dataset('disasters', {
        'dataset': 'disasters',
        'source': 'in_game/common/disasters',
        'entities': entities,
        'facets': facet_meta(entities, [('who', 'Country'), ('age', 'Age'),
                                        ('repeats', 'Repeats'), ('exit', 'How it ends')]),
    })
    return 0 if ok == total and not empty else 1


if __name__ == '__main__':
    sys.exit(main())
