"""in_game/common/government_reforms → src/data/reforms.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import (eid, ename, export_icon, mods_from_tree, rich, slugify,
                 write_dataset, facet_meta)


def main():
    reforms = ref.parser.government_reforms
    entities = []
    for name, r in sorted(reforms.items()):
        slug = slugify(name)
        mods = mods_from_tree(getattr(r, 'modifier', None))
        mods += mods_from_tree(getattr(r, 'country_modifier', None))
        entities.append({
            'id': eid('reform', name),
            'type': 'reform',
            'slug': slug,
            'icon': export_icon(r, 'reform', slug),
            'name': r.display_name,
            'desc': rich(r.description),
            'facets': {
                'government': ename(r.government) if not isinstance(r.government, str) else r.government,
                'age': ename(r.age) or 'Any age',
            },
            'mods': mods,
            'data': {
                'major': bool(getattr(r, 'major', False)),
            },
        })
    write_dataset('reforms', {
        'dataset': 'reforms',
        'source': 'in_game/common/government_reforms',
        'entities': entities,
        'facets': facet_meta(entities, [('government', 'Government'), ('age', 'Age')]),
    })


if __name__ == '__main__':
    main()
