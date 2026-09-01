"""in_game/common/building_types → src/data/buildings.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import (eid, ename, export_icon, mods_from_tree, rich, slugify,
                 write_dataset, facet_meta)

SETTLEMENTS = ['rural_settlement', 'town', 'city', 'megalopolis']


def pm_record(pm, unique: bool) -> dict | None:
    """One production method → {name, category, inputs, output}.

    Most methods both consume and produce: 0.606 iron + 0.505 tools makes 1
    cannon. Some are upkeep only. `slot` groups the alternatives you choose
    between.
    """
    name = getattr(pm, 'display_name', None) or ref.pretty(str(getattr(pm, 'name', '')))
    inputs = []
    for cost in getattr(pm, 'input', None) or []:
        good = getattr(cost, 'resource', None)
        val = getattr(cost, 'value', None)
        if good is None or val is None:
            continue
        inputs.append({
            'good': getattr(good, 'display_name', None) or str(good),
            'id': eid('good', good.name) if getattr(good, 'name', None) else None,
            'amount': round(val, 4) if isinstance(val, float) else val,
        })
    produced = getattr(pm, 'produced', None)
    amount = getattr(pm, 'output', None) or 0
    output = None
    if produced is not None and amount:
        output = {
            'good': getattr(produced, 'display_name', None) or str(produced),
            'id': eid('good', produced.name) if getattr(produced, 'name', None) else None,
            'amount': round(amount, 4) if isinstance(amount, float) else amount,
        }
    if not inputs and not output:
        return None
    return {
        'name': name,
        'category': ref.pretty(str(getattr(pm, 'category', '') or '')),
        'inputs': inputs,
        'output': output,
        'unique': unique,
    }


def production_methods(b) -> list[dict]:
    """A building's production methods, keyed by the slot they belong to.

    `unique_production_methods` is a list of GROUPS, each a list of
    alternative methods for one switchable slot — a cannon maker picks one
    barrel method (bronze / iron / lumber) and one shot method (stone / lead
    / iron). Iterating the outer list alone yields lists, not methods, which
    is why this looked like pure upkeep before.
    """
    out, seen = [], set()

    def add(pm, unique: bool, group: int):
        if not hasattr(pm, 'input'):
            return
        rec = pm_record(pm, unique)
        if rec and rec['name'] not in seen:
            seen.add(rec['name'])
            rec['slot'] = group
            out.append(rec)

    for attr, unique in (('unique_production_methods', True),
                         ('possible_production_methods', False)):
        for gi, group in enumerate(getattr(b, attr, None) or []):
            if isinstance(group, list):
                for pm in group:
                    add(pm, unique, gi)
            else:
                add(group, unique, gi)
    return out


def special_keys() -> set[str]:
    """`is_special = yes` marks a building as unique — one a country only gets
    from its own culture, religion, tag or an event, rather than something any
    country can put up. The toolkit's Building class does not model the field,
    so it is read off the raw tree (224 of 465 buildings carry it)."""
    out = set()
    tree = ref.parser.parser.parse_folder_as_one_file('in_game/common/building_types')
    for key, block in tree:
        if not hasattr(block, 'iterate_with_duplicates'):
            continue
        for k, v in block.iterate_with_duplicates():
            if str(k) == 'is_special' and str(v) in ('yes', 'True'):
                out.add(str(key))
    return out


def main():
    buildings = ref.parser.buildings
    specials = special_keys()
    entities = []
    for name, b in sorted(buildings.items()):
        slug = slugify(name)
        gate, gate_labels = ref.gate_of(b, 'country_potential')
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
                'kind': 'Unique' if name in specials else 'Standard',
            },
            'mods': mods_from_tree(getattr(b, 'modifier', None)),
            'data': {
                'gate': gate, 'gate_labels': gate_labels,
                'settlements': settlements,
                'max_levels': (lambda ml: ml if isinstance(ml, (int, float)) else None)(getattr(b, 'max_levels', None)),
                'special': name in specials,
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
