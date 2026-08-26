"""in_game/common/religions → src/data/religions.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import (eid, ename, hex_color, mods_from_tree, rich, slugify,
                 write_dataset, facet_meta)

MECHANIC_FLAGS = [
    'has_patriarchs', 'has_autocephalous_patriarchates', 'has_cardinals',
    'has_religious_head', 'has_religious_influence', 'has_karma', 'has_doom',
    'has_honor', 'has_purity', 'has_rite_power', 'has_canonization',
    'has_avatars',
]


def main():
    religions = ref.parser.religions
    entities = []
    for name, r in sorted(religions.items()):
        slug = slugify(name)
        mechanics = [f.removeprefix('has_') for f in MECHANIC_FLAGS
                     if getattr(r, f, False)]
        entities.append({
            'id': eid('religion', name),
            'type': 'religion',
            'slug': slug,
            'name': r.display_name,
            'desc': rich(r.description),
            'color': hex_color(r.color),
            'facets': {
                'group': ename(r.group) if not isinstance(r.group, str) else r.group,
            },
            'mods': mods_from_tree(getattr(r, 'definition_modifier', None)),
            'data': {
                'mechanics': mechanics,
                # script name — advance gates test this, not the display name
                'group_key': getattr(getattr(r, 'group', None), 'name', None),
            },
        })
    write_dataset('religions', {
        'dataset': 'religions',
        'source': 'in_game/common/religions',
        'entities': entities,
        'facets': facet_meta(entities, [('group', 'Group')]),
    })


if __name__ == '__main__':
    main()
