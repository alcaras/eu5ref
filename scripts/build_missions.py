"""in_game/common/missions → src/data/missions.json.

EU5 has no per-country mission trees. There are 11 generic mission packs,
none of them gated to a tag, and the game offers POTENTIAL_MISSION_COUNT
(10) of them at a time, picked by each pack's `chance`. Each pack contains
tasks with their own requirements, one of which is `final` and completes it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
import triggers
from ref import (eid, export_icon, mods_from_tree, rich, slugify,
                 write_dataset, facet_meta)


# Mission-level fields, per common/missions/____Info.txt. Any OTHER nested
# block at that level is a task — which is how we find them, because the
# toolkit leaves `Mission.missions` unparsed (its own TODO).
MISSION_FIELDS = {
    'header', 'icon', 'repeatable', 'visible', 'enabled', 'abort', 'chance',
    'ai_will_do', 'on_potential', 'on_start', 'on_abort', 'on_completion',
    'on_post_completion', 'player_playstyle', 'select_trigger', 'modifier',
    'description', 'desc', 'title', 'duration', 'is_repeatable',
}


def raw_missions():
    """mission key → its raw Tree, so we can read the task blocks."""
    try:
        tree = ref.parser.parser.parse_folder_as_one_file('in_game/common/missions')
    except Exception:
        return {}
    return {str(k): v for k, v in tree if hasattr(v, 'iterate_with_duplicates')}


def tasks_of(raw, labels) -> list[dict]:
    if raw is None:
        return []
    out = []
    for key, block in raw.iterate_with_duplicates():
        key = str(key)
        if key in MISSION_FIELDS or not hasattr(block, 'iterate_with_duplicates'):
            continue
        final, requires = False, []
        for tk, tv in block.iterate_with_duplicates():
            tk = str(tk)
            if tk == 'final':
                final = tv is True or str(tv) == 'yes'
            elif tk == 'requires':
                if hasattr(tv, 'iterate_with_duplicates'):
                    requires += [ref.pretty(str(rk)) for rk, _ in tv.iterate_with_duplicates()]
                elif isinstance(tv, list):
                    requires += [ref.pretty(str(x)) for x in tv]
                else:
                    requires.append(ref.pretty(str(tv)))
        out.append({
            'key': key,
            'name': ref.plain_text(ref.parser.localize(key, default='')) or ref.pretty(key),
            'final': final,
            'requires': requires,
        })
    out.sort(key=lambda x: (x['final'], x['name']))
    return out


def main():
    missions = ref.parser.missions
    raws = raw_missions()
    labels = ref.label_map()
    entities = []
    for name in sorted(missions):
        m = missions[name]
        slug = slugify(name)
        tasks = tasks_of(raws.get(name), labels)
        entities.append({
            'id': eid('mission', name),
            'type': 'mission',
            'slug': slug,
            'icon': export_icon(m, 'mission', slug),
            'name': m.display_name,
            'desc': rich(getattr(m, 'description', None)),
            'facets': {
                'playstyle': ref.pretty(str(getattr(m, 'player_playstyle', '') or '')) or None,
                'repeatable': 'repeatable' if getattr(m, 'repeatable', False) else 'once',
            },
            'mods': mods_from_tree(getattr(m, 'modifier', None)),
            'data': {
                'chance': getattr(m, 'chance', None),
                'tasks': tasks,
                'task_names': [t['name'] for t in tasks],
                'requires_state': triggers.summarize(getattr(m, 'select_trigger', None), labels, limit=4),
            },
        })
    write_dataset('missions', {
        'dataset': 'missions',
        'source': 'in_game/common/missions',
        'entities': entities,
        'facets': facet_meta(entities, [('playstyle', 'Playstyle'), ('repeatable', 'Repeatable')]),
    })


if __name__ == '__main__':
    main()
