"""in_game/common/building_types → src/data/buildings.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import (eid, ename, export_icon, mods_from_tree, rich, slugify,
                 write_dataset, facet_meta)

SETTLEMENTS = ['rural_settlement', 'town', 'city', 'megalopolis']


def production_methods(b) -> list[dict]:
    out = []
    for pm in getattr(b, 'unique_production_methods', None) or []:
        try:
            pairs = pm if isinstance(pm, list) else list(pm)
            for pm_name, tree in pairs:
                goods = []
                for k, v in tree:
                    if k == 'category' or not isinstance(v, (int, float, str)):
                        continue
                    goods.append(f'{v} {ref.pretty(k)}')
                out.append({'label': ref.pretty(str(pm_name)), 'value': ', '.join(goods)})
        except Exception:
            continue
    return out


def main():
    buildings = ref.parser.buildings
    entities = []
    for name, b in sorted(buildings.items()):
        slug = slugify(name)
        settlements = [s for s in SETTLEMENTS if getattr(b, s, False)]
        entities.append({
            'id': eid('building', name),
            'type': 'building',
            'slug': slug,
            'icon': export_icon(b, 'building', slug),
            'name': b.display_name,
            'desc': rich(b.description),
            'facets': {
                'category': (b.category.display_name if hasattr(b.category, 'display_name')
                             else b.category) or 'Uncategorized',
                'pop_type': ename(getattr(b, 'pop_type', None)) if not isinstance(getattr(b, 'pop_type', None), str) else b.pop_type,
            },
            'mods': mods_from_tree(getattr(b, 'modifier', None)),
            'data': {
                'settlements': settlements,
                'max_levels': (lambda ml: ml if isinstance(ml, (int, float)) else None)(getattr(b, 'max_levels', None)),
                'special': bool(getattr(b, 'is_special', False)),
                'production_methods': production_methods(b),
            },
        })
    write_dataset('buildings', {
        'dataset': 'buildings',
        'source': 'in_game/common/building_types',
        'entities': entities,
        'facets': facet_meta(entities, [('category', 'Category'), ('pop_type', 'Pop Type')]),
    })


if __name__ == '__main__':
    main()
