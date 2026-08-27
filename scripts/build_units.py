"""in_game/common/unit_types → src/data/units.json.

Stats are resolved through the copy_from chain onto the category base by
lib/unitstats.py — the raw files build most units as `copy_from = <template>`
plus deltas, so reading attributes directly yields zeros.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
import unitstats
from ref import (eid, ename, export_icon, hex_color, rich, slugify,
                 write_dataset, facet_meta)


def num(v):
    if v is None:
        return None
    return round(v, 3) if isinstance(v, float) else v


def main():
    units = ref.parser.unit_types
    resolved = unitstats.resolved_units()
    ages = ref.parser.age
    entities = []
    for name, u in sorted(units.items()):
        slug = slugify(name)
        gate, gate_labels = ref.gate_of(u, 'country_potential')
        r = resolved[name]
        s = r['stats']
        f = r['flags']
        age_name = ename(ages.get(r['age'])) if r['age'] else None
        is_template = bool(f.get('hide') or f.get('empty'))
        kind = 'template' if is_template else ('levy' if f.get('levy') else 'buildable')
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
                'age': age_name or 'Any age',
                'buildable': kind,
            },
            'mods': [],
            'data': {
                'gate': gate, 'gate_labels': gate_labels,
                'combat_power': num(s.get('combat_power')),
                'max_strength': num(s.get('max_strength')),
                'movement_speed': num(s.get('movement_speed')),
                'combat_speed': num(s.get('combat_speed')),
                'initiative': num(s.get('initiative')),
                'frontage': num(s.get('frontage')),
                'flanking': num(s.get('flanking_ability')),
                'secure_flanks_defense': num(s.get('secure_flanks_defense')),
                'damage_taken': num(s.get('damage_taken')),
                'morale_dmg_done': num(s.get('morale_damage_done')),
                'morale_dmg_taken': num(s.get('morale_damage_taken')),
                'strength_dmg_done': num(s.get('strength_damage_done')),
                'strength_dmg_taken': num(s.get('strength_damage_taken')),
                'bombard_efficiency': num(s.get('bombard_efficiency')),
                'artillery_barrage': num(s.get('artillery_barrage')),
                'supply_weight': num(s.get('supply_weight')),
                'food_per_strength': num(s.get('food_consumption_per_strength')),
                'cannons': num(s.get('cannons')) or None,
                'hull_size': num(s.get('hull_size')) or None,
                'terrain_combat': r['combat'] or None,
                'terrain_impact': r['impact'] or None,
                'upgrades_to': r['upgrades_to'],
                'unit_limit': r['limit'],
                'levy': bool(f.get('levy')),
                'flags': [fl for fl, on in [
                    ('levy', f.get('levy')), ('default', f.get('default')),
                    ('template', is_template), ('special', f.get('is_special')),
                    ('assault', f.get('assault')), ('bombard', f.get('bombard')),
                ] if on],
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
