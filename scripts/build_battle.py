"""Land-combat model data → public/battle.json (Battle Simulator payload).

Not a dataset envelope — lazily fetched by src/pages/battle-simulator.astro,
like planner.json/values.json. Everything numeric is read from the game
files (defines, unit_categories + resolved unit_types, terrain, static
modifiers, formation preferences); nothing is hand-copied.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
import unitstats

OUT = ref.ROOT / 'public' / 'battle.json'

# Engine constants the simulator consumes, by define group.
DEFINES = {
    'NCombat': [
        'MORALE_COLLAPSE_THRESHOLD', 'MINIMUM_COMBAT_DURATION',
        'BOMBARD_BASE_CHANCE', 'BOMBARD_HOURS', 'HOURS_PER_PHASE',
        'COMBAT_DICE_SIDE', 'COMBAT_BASE', 'COMBAT_MAX',
        'COMBAT_DAMAGE_MULT', 'COMBAT_HOURLY_MORALE_TICK',
        'STRAIT_CROSSING_DICE', 'RIVER_CROSSING_DICE', 'SEA_LANDING_DICE',
        'MAX_FRONTAGE_OVERSTACKING', 'LAND_LEVY_COMBAT_IMPACT',
        'INITIATIVE_BASE_CHANCE', 'INITIATIVE_CHANCE_EACH',
        'INITIATIVE_CHANCE_HOURS', 'INITIATIVE_CHANCE_MAX',
        'COMBAT_SPEED_SCALE', 'LAND_EXPERIENCE_DAMAGE_REDUCTION',
        'LAND_STRENGTH_DAMAGE_MODIFIER', 'LAND_MORALE_DAMAGE_MODIFIER',
        'NOT_ENGAGED_STRENGTH_DAMAGE_MODIFIER',
        'NOT_ENGAGED_MORALE_DAMAGE_MODIFIER',
        'BASE_MORALE_DAMAGE', 'RETREAT_STRENGTH_DAMAGE',
    ],
    'NUnit': ['REGIMENT_SIZE', 'LAND_MORALE', 'LOW_MORALE_THRESHOLD'],
    'NLocation': ['MIN_FRONTAGE_AFTER_TERRAIN'],
}


def collect_defines():
    out = {}
    for group, keys in DEFINES.items():
        for k in keys:
            v = ref.parser.get_define(f'{group}.{k}')
            if v is None:
                print(f'  WARNING: define {group}.{k} not found', file=sys.stderr)
                continue
            out[k] = v
    return out


def frontage_of(entity):
    for m in entity.location_modifier or []:
        if m.name == 'local_frontage_allowed':
            return m.value
    return 0


def terrain_payload():
    topo, veg = {}, {}
    for key, t in ref.parser.topography.items():
        topo[key] = {'name': t.display_name, 'defender': getattr(t, 'defender', 0) or 0,
                     'frontage': frontage_of(t)}
    for key, v in ref.parser.vegetation.items():
        veg[key] = {'name': v.display_name, 'defender': getattr(v, 'defender', 0) or 0,
                    'frontage': frontage_of(v)}
    climates = {key: {'name': c.display_name} for key, c in ref.parser.climates.items()}
    return {'topography': topo, 'vegetation': veg, 'climate': climates}


def formations_payload():
    tree = ref.parser.parser.parse_folder_as_one_file('in_game/common/unit_formation_preference')
    out = {}
    for name, node in tree:
        if not node.get_or_default('army', False):
            continue
        sections = {}
        for sec in ('left', 'center', 'right', 'reserves'):
            block = node.get_or_default(sec, None)
            if block is None:
                continue
            weights = []
            max_frontage = None
            for k, v in block:
                if k == 'max_frontage':
                    max_frontage = v
                    continue
                try:
                    w = int(k)
                except ValueError:
                    continue
                for cat in (v if isinstance(v, list) else [v]):
                    weights.append({'w': w, 'cat': str(cat)})
            sections[sec] = {'weights': weights}
            if max_frontage is not None:
                sections[sec]['max_frontage'] = max_frontage
        out[name] = {'default': bool(node.get_or_default('default', False)),
                     'sections': sections}
    return out


def sources_payload():
    out = {}
    for src, key in (('levy', 'is_army_levy'), ('regular', 'is_army_regular'),
                     ('mercenary', 'is_army_mercenary')):
        nm = ref.parser.named_modifiers.get(key)
        out[src] = {m.name: m.value for m in (nm.modifier if nm else [])}
    return out


def traits_payload():
    """General traits + the composition gates that switch them on."""
    raw = ref.parser.parser.parse_folder_as_one_file('in_game/common/traits')
    out = []
    for key, t in sorted(ref.parser.traits.items()):
        if str(getattr(t, 'category', '')) not in ('general', 'General'):
            continue
        mods = {m.name: m.value for m in (t.modifier or [])}
        if not mods:
            continue
        # composition gates look like `sub_unit_fraction:army_x > 0.2`
        gates = []
        node = raw.get_or_default(key, None)
        allow = node.get_or_default('allow', None) if node is not None else None
        if allow is not None:
            def _dump(t):
                parts = []
                for k, v in t:
                    parts.append(str(k))
                    if hasattr(v, 'dictionary'):
                        parts.append(_dump(v))
                    elif isinstance(v, list):
                        parts.extend(_dump(i) if hasattr(i, 'dictionary') else str(i) for i in v)
                    else:
                        parts.append(str(v))
                return ' '.join(parts)
            for m2 in re.finditer(r'sub_unit_fraction:(\w+)', _dump(allow)):
                gates.append(m2.group(1))
        out.append({'key': key, 'name': t.display_name, 'mods': mods,
                    'needs': sorted(set(gates)) or None})
    return out


def country_base():
    tree = ref.parser.parser.parse_file('in_game/common/auto_modifiers/country.txt')
    base = tree.get_or_default('country_base_values', None)
    keys = ('military_tactics', 'combined_arms_max_threshold',
            'combined_arms_min_percent_for_bonus', 'combined_bonus_per_type',
            'land_morale_recovery')
    out = {}
    if base is not None:
        for k in keys:
            v = base.get_or_default(k, None)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = v
    return out


def main():
    resolved = unitstats.resolved_units()
    cats = unitstats.categories()
    toolkit_units = ref.parser.unit_types
    ages = {key: {'name': a.display_name,
                  'year': 1337 if a.year <= 1 else a.year}
            for key, a in ref.parser.age.items()}

    units = {}
    for key, r in sorted(resolved.items()):
        f = r['flags']
        if not r['is_army'] or f.get('hide') or f.get('empty'):
            continue
        u = toolkit_units.get(key)
        _, gate_labels = ref.gate_of(u, 'country_potential') if u else (None, [])
        rec = {
            'name': u.display_name if u else key,
            'cat': r['category'],
            'age': r['age'],
            'levy': bool(f.get('levy')),
            'stats': r['stats'],
        }
        if f.get('is_special'):
            rec['special'] = True
        if r['combat']:
            rec['combat'] = r['combat']
        if r['impact']:
            rec['impact'] = r['impact']
        if r['limit']:
            rec['limit'] = r['limit']
        if r['upgrades_to']:
            rec['up'] = r['upgrades_to']
        if gate_labels:
            rec['gate'] = gate_labels
        units[key] = rec

    categories = {}
    for key, c in cats.items():
        if not c['is_army']:
            continue
        tk = ref.parser.unit_categories.get(key)
        categories[key] = {
            'name': tk.display_name if tk else key,
            'stats': c['stats'],
            'flags': {k: v for k, v in c['flags'].items() if v},
        }

    payload = {
        'source': 'in_game/common/{unit_types,unit_categories,topography,vegetation,'
                  'unit_formation_preference,auto_modifiers,traits} + defines + '
                  'main_menu/common/static_modifiers',
        'defines': collect_defines(),
        'baseFrontage': 10,  # overwritten below from location_base_values
        'countryBase': country_base(),
        'ages': ages,
        'categories': categories,
        'units': units,
        'terrain': terrain_payload(),
        'formations': formations_payload(),
        'sources': sources_payload(),
        'traits': traits_payload(),
    }
    nm = ref.parser.named_modifiers.get('location_base_values')
    for m in (nm.modifier if nm else []):
        if m.name == 'local_frontage_allowed':
            payload['baseFrontage'] = m.value

    OUT.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                              separators=(',', ':')) + '\n')
    print(f'  public/battle.json: {len(units)} land units, '
          f'{len(categories)} categories, {len(payload["traits"])} traits, '
          f'{len(payload["defines"])} defines ({OUT.stat().st_size//1024} KB)')


if __name__ == '__main__':
    main()
