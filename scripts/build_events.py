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


def effect_keys(effect) -> list[str]:
    """Top-level keys of an effect block, in file order."""
    tree = getattr(effect, 'tree', None) or effect
    if tree is None or not hasattr(tree, 'iterate_with_duplicates'):
        return []
    out = []
    try:
        for k, _ in tree.iterate_with_duplicates():
            out.append(str(k))
    except Exception:
        return []
    return out


def collect_options(e, labels) -> tuple[list[dict], list[str]]:
    options, rewards = [], []
    opts = getattr(e, 'option', None) or {}
    for key, opt in opts.items():
        keys = effect_keys(getattr(opt, 'effect', None))
        for k in keys:
            tag = REWARD_KEYS.get(k)
            if tag and tag not in rewards:
                rewards.append(tag)
        # The effect block's own top-level keys ARE the outcome ("add_prestige",
        # "change_gold_effect"). Walking inside them yields scripted-effect
        # plumbing ("scale: -5", "text: …tt"), so we don't.
        options.append({
            'key': key,
            'name': ref.plain_text(str(getattr(opt, 'display_name', '') or '')) or key.rsplit('.', 1)[-1],
            'effects': [ref.pretty(k) for k in keys[:8]],
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
            for _, v in triggers.literals(gate):
                lab = labels.get(v) or ref.pretty(v)
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
