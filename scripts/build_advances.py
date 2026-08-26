"""in_game/common/advances → src/data/advances.json — the tech tree.
~3,200 advances across 7 ages, incl. national/cultural branches."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import (eid, ename, export_icon, mods_from_tree, ref_list, rich,
                 slugify, write_dataset, facet_meta)


def main():
    advances = ref.parser.advances
    entities = []
    for name, a in sorted(advances.items()):
        slug = slugify(name)
        age = ename(a.age) or 'No age'
        national = bool(a.countries) or a.in_tree_of is not None
        requires = ref_list(getattr(a, 'requires', None) or [], 'advance')
        entities.append({
            'id': eid('advance', name),
            'type': 'advance',
            'slug': slug,
            'icon': export_icon(a, 'advance', slug),
            'name': a.display_name,
            'desc': rich(a.description),
            'facets': {
                'age': age,
                'scope': 'national' if national else 'general',
            },
            'mods': mods_from_tree(a.modifiers),
            'data': {
                'depth': a.depth,
                'requires': requires,
                'countries': [c.display_name for c in (a.countries or [])],
                'tree': ename(a.in_tree_of),
            },
        })
    write_dataset('advances', {
        'dataset': 'advances',
        'source': 'in_game/common/advances',
        'entities': entities,
        'facets': facet_meta(entities, [('age', 'Age'), ('scope', 'Scope')]),
    })

    # Slim graph for the client-side advance planner tool.
    import json
    planner = {e['id']: {'n': e['name'], 'a': e['facets']['age'],
                         's': e['slug'],
                         'r': [r['id'] for r in e['data']['requires']]}
               for e in entities}
    out = ref.ROOT / 'public' / 'planner-advances.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(planner, sort_keys=True, ensure_ascii=False) + '\n',
                   encoding='utf-8')
    print(f'  public/planner-advances.json: {len(planner)} nodes')


if __name__ == '__main__':
    main()
