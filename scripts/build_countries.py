"""setup/countries (+ start data) → countries.json; formable_countries →
formables.json. The 1337 world."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import (eid, ename, hex_color, rich, slugify, write_dataset,
                 facet_meta)


def capital_geography(c) -> dict:
    """Capital's area/province/region/sub-continent/continent as SCRIPT names.

    Advance gates test these (`original_capital.region = region:x`), so the
    planner needs the raw keys, not display names."""
    geo: dict[str, str] = {}
    cap = getattr(c, 'capital', None)
    if cap is None:
        return geo
    try:
        prov = ref.parser._prov_for_loc.get(cap.name)
        if prov is None:
            return geo
        geo['province'] = prov.name
        area = prov.area
        geo['area'] = area.name
        region = area.region
        geo['region'] = region.name
        sub = region.sub_continent
        geo['sub_continent'] = sub.name
        geo['continent'] = sub.continent.name
    except Exception:
        pass
    return geo


def main():
    countries = ref.parser.countries
    entities = []
    for tag, c in sorted(countries.items()):
        if tag in ('DUMMY', 'PIR', 'MER'):
            continue
        slug = slugify(tag)
        culture = ename(c.culture_definition)
        religion = ename(c.religion_definition)
        # script-name facts an advance gate can be evaluated against
        cul_obj = c.culture_definition
        rel_obj = c.religion_definition
        facts = {
            'tag': tag,
            'cul': getattr(cul_obj, 'name', None),
            'cgrp': [g.name for g in (getattr(cul_obj, 'culture_groups', None) or [])],
            'lang': getattr(getattr(cul_obj, 'language', None), 'name', None),
            'rel': getattr(rel_obj, 'name', None),
            'rgrp': getattr(getattr(rel_obj, 'group', None), 'name', None),
            'cap': capital_geography(c),
        }
        entities.append({
            'id': eid('country', tag),
            'type': 'country',
            'slug': slug,
            'name': c.display_name,
            'color': hex_color(c.color),
            'desc': rich(getattr(c, 'description', None)),
            'facets': {
                'religion': religion or 'None',
                'culture': culture or 'None',
                'rank': ename(getattr(c, 'country_rank', None)) or 'Unranked',
                'category': ename(getattr(c, 'description_category', None)),
            },
            'mods': [],
            'data': {
                'tag': tag,
                'facts': facts,
                'capital': ename(getattr(c, 'capital', None)),
                'difficulty': getattr(c, 'difficulty', None),
                'historic': bool(getattr(c, 'is_historic', False)),
                'court_language': ename(getattr(c, 'court_language', None)),
                'dynasty': [d.display_name for d in (getattr(c, 'dynasty', None) or [])],
            },
        })
    write_dataset('countries', {
        'dataset': 'countries',
        'source': 'in_game/setup/countries + main_menu setup',
        'entities': entities,
        'facets': facet_meta(entities, [('rank', 'Rank'), ('religion', 'Religion'),
                                        ('culture', 'Culture'), ('category', 'Category')]),
    })

    formables = ref.parser.formable_countries
    fents = []
    for name, f in sorted(formables.items()):
        slug = slugify(name)
        fents.append({
            'id': eid('formable', name),
            'type': 'formable',
            'slug': slug,
            'name': f.display_name,
            'color': hex_color(getattr(f, 'color', None)),
            'desc': rich(getattr(f, 'description', None)),
            'facets': {
                'level': f'Level {getattr(f, "level", "?")}',
            },
            'mods': [],
            'data': {
                'capital_required': bool(getattr(f, 'capital_required', True)),
                'regions': [r.display_name for r in (getattr(f, 'regions', None) or [])],
                'areas': [a.display_name for a in (getattr(f, 'areas', None) or [])],
            },
        })
    write_dataset('formables', {
        'dataset': 'formables',
        'source': 'in_game/common/formable_countries',
        'entities': fents,
        'facets': facet_meta(fents, [('level', 'Level')]),
    })


if __name__ == '__main__':
    main()
