"""in_game/common/pop_types → src/data/pops.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import (eid, export_icon, hex_color, mods_from_tree, rich, slugify,
                 write_dataset)


def main():
    pops = ref.parser.pop_types
    entities = []
    for name, p in sorted(pops.items()):
        slug = slugify(name)
        promote = [x.display_name if not isinstance(x, str) else x
                   for x in (getattr(p, 'promote_to', None) or [])]
        entities.append({
            'id': eid('pop', name),
            'type': 'pop',
            'slug': slug,
            'icon': export_icon(p, 'pop', slug),
            'name': p.display_name,
            'desc': rich(p.description),
            'color': hex_color(p.color),
            'facets': {},
            'mods': (mods_from_tree(getattr(p, 'modifier', None))
                     + mods_from_tree(getattr(p, 'literacy_impact', None))),
            'data': {
                'food_consumption': getattr(p, 'pop_food_consumption', None),
                'promote_to': promote,
                'has_cap': bool(getattr(p, 'has_cap', False)),
            },
        })
    write_dataset('pops', {
        'dataset': 'pops',
        'source': 'in_game/common/pop_types',
        'entities': entities,
        'facets': [],
    })


if __name__ == '__main__':
    main()
