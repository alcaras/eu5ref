"""in_game/events → src/data/events.json.

7,500+ narrative events. Each carries a `trigger`, so the same gate compiler
the planner uses attributes flavour events to the country they belong to —
which is why `build_countries.py` can list them as unique content without
any extra wiring.

Per event we keep what a player actually wants: the title and description,
every option with the effects it applies, when it can fire (the historical
date window, where the game defines one), and whether it is once-only.
Effect names are taken verbatim from the script — nothing is inferred.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
import requirements
import triggers
from ref import eid, rich, slugify, write_dataset, facet_meta

# Effect keys worth surfacing as a "this event gives you X" tag. Keys are the
# game's own; the label is only presentation.
REWARD_KEYS = {
    'unlock_advance_effect': 'advance',
    'add_advance': 'advance',
    'add_treasury': 'gold',
    'add_gold': 'gold',
    'add_stability': 'stability',
    'add_prestige': 'prestige',
    'add_legitimacy': 'legitimacy',
    'add_manpower': 'manpower',
    'add_sailors': 'sailors',
    'add_modifier': 'modifier',
    'add_country_modifier': 'modifier',
    'add_location_modifier': 'modifier',
    'unlock_law_effect': 'law',
    'add_government_reform': 'reform',
    'change_government_reform': 'reform',
    'add_building': 'building',
    'create_building': 'building',
    'add_cultural_influence': 'culture',
    'add_religious_influence': 'religion',
    'change_religion': 'religion',
    'add_war_exhaustion': 'war exhaustion',
    'add_corruption': 'corruption',
    'declare_war': 'war',
    'add_opinion': 'opinion',
}


# Inside an effect block, the key that names *what* it applies.
# `add_country_modifier = { modifier = trusted_merchants months = 121 }`
_SUBJECT_KEYS = ('modifier', 'name', 'type', 'advance', 'building', 'law',
                 'reform', 'religion', 'culture', 'goods', 'estate', 'value',
                 'amount', 'target', 'who')
_DURATION_KEYS = ('months', 'years', 'days')


# Control flow inside an option's effect block. The body matters more than
# the wrapper, so each of these is recursed into and its condition, where it
# has one, becomes the prefix on the lines it guards.
_FLOW = {
    'if': 'If', 'trigger_if': 'If',
    'else_if': 'Otherwise if', 'trigger_else_if': 'Otherwise if',
    'else': 'Otherwise', 'trigger_else': 'Otherwise',
    'hidden_effect': '', 'random_list': 'One of',
}
_MAX_DEPTH = 2
_MAX_INNER = 4        # effects listed under one condition before "and N more"


# `estate(estate_type:burghers_estate) = { … }` switches scope; the effect a
# player cares about is inside it, so the key becomes the prefix on the body.
_SCOPES = {'root', 'prev', 'this', 'owner', 'ruler', 'heir', 'capital_scope',
           'controller', 'overlord', 'from'}


def _is_scope(label: str) -> bool:
    key = label.lower().replace(' ', '_')
    return '(' in key or key in _SCOPES


def _scope_name(label: str) -> str:
    """`Estate(Estate Type:Burghers Estate)` → `Burghers Estate`."""
    if '(' in label:
        inner = label[label.index('(') + 1:].rstrip(')')
        return inner.split(':')[-1].strip() or label
    return label


def _condition(block) -> str:
    """A `limit` block as one sentence, or '' when there is none."""
    limit = None
    try:
        for k, v in block.iterate_with_duplicates():
            if str(k) == 'limit':
                limit = v
                break
    except AttributeError:
        return ''
    if limit is None:
        return ''
    d = requirements.describe(limit, limit=3)
    parts = list(d['lines']) + [f'not {x}' for x in d['excludes']]
    return ' and '.join(parts)


def _one_effect(label: str, v, labels, depth: int) -> list[str]:
    """One key/value of an effect block as readable lines.

    A key written more than once in the same block comes back as a list, and
    a control-flow key wraps the effects that matter, so both are walked
    rather than printed. Nothing that still holds a parser object is ever
    emitted: the fallback is the key's own name.
    """
    if isinstance(v, (list, tuple)):
        out = []
        for item in v:
            out.extend(_one_effect(label, item, labels, depth))
        return out

    if hasattr(v, 'iterate_with_duplicates'):
        flow = _FLOW.get(label.lower().replace(' ', '_'))
        if flow is None and _is_scope(label):
            flow = _scope_name(label)
        if flow is not None and depth < _MAX_DEPTH:
            cond = _condition(v) if flow.startswith(('If', 'Otherwise if')) else ''
            inner = _block_lines(v, labels, depth + 1, skip={'limit'})
            if not inner:
                return []
            head = f'{flow} {cond}' if cond else flow
            if not head:                      # hidden_effect: the body is the effect
                return inner
            shown, rest = inner[:_MAX_INNER], len(inner) - _MAX_INNER
            body = ', '.join(shown) + (f', and {rest} more' if rest > 0 else '')
            return [f'{head}: {body}']

        inner = {}
        try:
            for ik, iv in v.iterate_with_duplicates():
                inner.setdefault(str(ik), iv)
        except Exception:
            pass
        subject = next((inner[s] for s in _SUBJECT_KEYS if s in inner), None)
        dur = next(((d, inner[d]) for d in _DURATION_KEYS if d in inner), None)
        if isinstance(subject, (str, int, float, bool)):
            tok = str(subject)
            line = f'{label}: {labels.get(tok) or ref.pretty(tok)}'
            if dur and isinstance(dur[1], (str, int, float)):
                line += f' ({dur[1]} {dur[0]})'
            return [line]
        return [label]

    if v is not None and str(v) not in ('yes', ''):
        tok = str(v)
        return [f'{label}: {labels.get(tok) or ref.pretty(tok)}']
    return [label]


def _block_lines(tree, labels, depth: int, skip: set[str] | None = None) -> list[str]:
    """Every key of an effect block as readable lines."""
    out: list[str] = []
    try:
        pairs = list(tree.iterate_with_duplicates())
    except Exception:
        return out
    for k, v in pairs:
        key = str(k)
        if skip and key in skip:
            continue
        for line in _one_effect(ref.pretty(key), v, labels, depth):
            if 'paradox_parser' in line:      # never ship a parser repr
                line = ref.pretty(key)
            if line and line not in out:
                out.append(line)
    return out


def effect_lines(effect, labels) -> tuple[list[str], list[str]]:
    """(readable lines, raw top-level keys) for an option's effect block.

    "add_country_modifier" alone says nothing — the modifier's name lives one
    level in, so we read that one level and stop. Going deeper only yields
    scripted-effect plumbing. Control flow is the exception: an `if` hides the
    effect a player cares about, so it is walked and its condition kept.
    """
    tree = getattr(effect, 'tree', None) or effect
    if tree is None or not hasattr(tree, 'iterate_with_duplicates'):
        return [], []
    try:
        keys = [str(k) for k, _ in tree.iterate_with_duplicates()]
    except Exception:
        return [], []
    return _block_lines(tree, labels, 0), keys


def collect_options(e, labels) -> tuple[list[dict], list[str]]:
    options, rewards = [], []
    opts = getattr(e, 'option', None) or {}
    for key, opt in opts.items():
        lines, keys = effect_lines(getattr(opt, 'effect', None), labels)
        for k in keys:
            tag = REWARD_KEYS.get(k)
            if tag and tag not in rewards:
                rewards.append(tag)
        options.append({
            'key': key,
            'name': ref.plain_text(str(getattr(opt, 'display_name', '') or '')) or key.rsplit('.', 1)[-1],
            'effects': lines[:8],
        })
    return options, sorted(rewards)


def main():
    events = ref.parser.events
    labels = ref.label_map()
    cgroups = ref.culture_group_keys()
    entities = []

    for name in sorted(events):
        e = events[name]
        title = ref.plain_text(str(e.title)) if e.title is not None else ''
        desc_raw = str(e.desc) if e.desc is not None else ''
        gate = triggers.compile_trigger(getattr(e, 'trigger', None), cgroups)
        gate_labels = []
        if gate:
            seen = set()
            for kind, v in triggers.literals(gate):
                lab = triggers.label_of(kind, v, labels)
                if lab not in seen:
                    seen.add(lab)
                    gate_labels.append(lab)
        options, rewards = collect_options(e, labels)

        # Flavour events name their country in `dynamic_historical_event`
        # (`tag = ENG`, plus the date window and monthly chance) rather than
        # in the trigger — that block is the game's own attribution.
        dhe = getattr(e, 'dynamic_historical_event', None)
        years, dhe_tags, chance = None, [], None
        if dhe is not None:
            frm, to = getattr(dhe, 'from_date', ''), getattr(dhe, 'to_date', '')
            if frm or to:
                years = {'from': frm, 'to': to}
            raw = getattr(dhe, 'tag', None) or []
            dhe_tags = [raw] if isinstance(raw, str) else [str(t) for t in raw]
            chance = getattr(dhe, 'monthly_chance', None)

        tags = list(dict.fromkeys(dhe_tags + [v for k, v in triggers.literals(gate or [], kinds=('tag',))]))
        for t in dhe_tags:
            lab = labels.get(t)
            if lab and lab not in gate_labels:
                gate_labels.append(lab)

        entities.append({
            'id': eid('event', name),
            'type': 'event',
            'slug': slugify(name),
            'name': title or ref.pretty(name),
            'desc': rich(desc_raw),
            'facets': {
                'namespace': e.namespace,
                'kind': (e.type or 'country_event').replace('_event', ''),
                'rewards': rewards or None,
            },
            'mods': [],
            'data': {
                'event_id': name,
                'options': options,
                'gate': gate,
                'gate_labels': gate_labels,
                'trigger': triggers.summarize(getattr(e, 'trigger', None), labels, limit=4),
                'tags': tags,
                'years': years,
                'monthly_chance': chance,
                'major': bool(getattr(e, 'major', False)),
                'once': bool(getattr(e, 'fire_only_once', False)),
            },
        })

    write_dataset('events', {
        'dataset': 'events',
        'source': 'in_game/events',
        'entities': entities,
        'facets': facet_meta(entities, [('kind', 'Kind'), ('rewards', 'Gives'),
                                        ('namespace', 'Group')]),
    })


if __name__ == '__main__':
    main()
