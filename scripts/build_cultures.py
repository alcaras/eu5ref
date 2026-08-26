"""in_game/common/cultures → src/data/cultures.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import (eid, ename, hex_color, mods_from_tree, rich, slugify,
                 write_dataset, facet_meta)


def main():
    cultures = ref.parser.cultures
    entities = []
    for name, c in sorted(cultures.items()):
        slug = slugify(name)
        groups = [g.display_name for g in (c.culture_groups or [])]
        mods = mods_from_tree(getattr(c, 'modifier', None))
        mods += mods_from_tree(getattr(c, 'country_modifier', None))
        entities.append({
            'id': eid('culture', name),
            'type': 'culture',
            'slug': slug,
            'name': c.display_name,
            'color': hex_color(c.color),
            'facets': {
                'group': groups[0] if groups else 'Ungrouped',
            },
            'mods': mods,
            'data': {
                'groups': groups,
                'language': ename(c.language) if not isinstance(c.language, str) else c.language,
                # script names — advance gates test these, not display names
                'group_keys': [g.name for g in (c.culture_groups or [])],
                'language_key': getattr(c.language, 'name', None),
            },
        })
    write_dataset('cultures', {
        'dataset': 'cultures',
        'source': 'in_game/common/cultures',
        'entities': entities,
        'facets': facet_meta(entities, [('group', 'Culture Group')]),
    })


if __name__ == '__main__':
    main()
