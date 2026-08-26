"""in_game/common/goods → src/data/goods.json.

The Phase-0 flagship dataset: exercises colors, facets, pop demand,
modifiers, and rich-text descriptions end to end."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import eid, export_icon, hex_color, mods_from_tree, rich, slugify, write_dataset, facet_meta


def main():
    goods = ref.parser.goods
    entities = []
    for name, g in sorted(goods.items()):
        demand = []
        for pop, value in g.demands.items():
            if value:
                demand.append({'pop': pop.display_name, 'value': round(value, 4)})
        demand.sort(key=lambda d: -d['value'])
        tags = list(getattr(g, 'custom_tags', []) or [])
        slug = slugify(name)
        entities.append({
            'id': eid('good', name),
            'type': 'good',
            'slug': slug,
            'icon': export_icon(g, 'good', slug),
            'name': g.display_name,
            'desc': rich(g.description),
            'color': hex_color(g.color),
            'facets': {
                'category': g.category,
                'method': g.method or None,
            },
            'mods': mods_from_tree(g.modifier),
            'data': {
                'price': g.default_market_price,
                'transport_cost': getattr(g, 'transport_cost', None),
                'base_production': getattr(g, 'base_production', None) or None,
                'demand': demand,
                'food': bool(getattr(g, 'food', False)),
                'tags': tags,
            },
        })
    write_dataset('goods', {
        'dataset': 'goods',
        'source': 'in_game/common/goods',
        'entities': entities,
        'facets': facet_meta(entities, [('category', 'Category'), ('method', 'Method')]),
    })


if __name__ == '__main__':
    main()
