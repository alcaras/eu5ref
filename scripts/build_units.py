"""in_game/common/unit_types → src/data/units.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import (eid, ename, export_icon, hex_color, rich, slugify,
                 write_dataset, facet_meta)


def num(v):
    if v is None:
        return None
    return round(v, 3) if isinstance(v, float) else v


def main():
    units = ref.parser.unit_types
    entities = []
    for name, u in sorted(units.items()):
        slug = slugify(name)
        gate, gate_labels = ref.gate_of(u, 'country_potential')
        entities.append({
            'id': eid('unit', name),
            'type': 'unit',
            'slug': slug,
            'icon': export_icon(u, 'unit', slug),
            'name': u.display_name,
            'desc': rich(u.description),
            'color': hex_color(u.color),
            'facets': {
                'category': ename(u.category) or 'Uncategorized',
                'age': ename(u.age) or 'Any age',
                'buildable': 'buildable' if u.buildable else 'not_buildable',
            },
            'mods': [],
            'data': {
                'gate': gate, 'gate_labels': gate_labels,
                'combat_power': num(u.combat_power),
                'max_strength': num(u.max_strength),
                'movement_speed': num(u.movement_speed),
                'combat_speed': num(u.combat_speed),
                'initiative': num(u.initiative),
                'frontage': num(u.frontage),
                'flanking': num(u.flanking_ability),
                'morale_dmg_done': num(u.morale_damage_done),
                'strength_dmg_done': num(u.strength_damage_done),
                'supply_weight': num(u.supply_weight),
                'food_per_strength': num(u.food_consumption_per_strength),
                'cannons': u.cannons or None,
                'hull_size': u.hull_size or None,
                'levy': bool(u.levy),
                'flags': [f for f, on in [('levy', u.levy), ('default', u.default)] if on],
            },
        })
    write_dataset('units', {
        'dataset': 'units',
        'source': 'in_game/common/unit_types',
        'entities': entities,
        'facets': facet_meta(entities, [('category', 'Category'), ('age', 'Age'), ('buildable', 'Buildable')]),
    })


if __name__ == '__main__':
    main()
