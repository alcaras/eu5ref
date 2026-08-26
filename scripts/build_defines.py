"""Engine defines (jomini + game, all modules) → src/data/defines.json.
The constants behind the formulas — provenance for mechanics pages."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import eid, slugify, write_dataset, facet_meta


def jsonable(v):
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, list):
        return [jsonable(x) for x in v]
    return str(v)


def main():
    defines = ref.parser.defines
    entities = []
    for group, tree in defines:
        gname = str(group)
        try:
            items = list(tree)
        except Exception:
            continue
        for key, value in items:
            entities.append({
                'id': eid('define', f'{gname}.{key}'),
                'type': 'define',
                'slug': slugify(f'{gname}-{key}'),
                'name': str(key),
                'facets': {'group': gname},
                'mods': [],
                'data': {'value': jsonable(value)},
            })
    entities.sort(key=lambda e: e['id'])
    write_dataset('defines', {
        'dataset': 'defines',
        'source': '*/common/defines',
        'entities': entities,
        'facets': facet_meta(entities, [('group', 'Group')]),
    })


if __name__ == '__main__':
    main()
