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


def unique_index() -> dict[str, dict[str, list]]:
    """tag → {advances/units/buildings/reforms: [{id,name,slug}]}.

    Built by inverting the compiled `potential` gates the other datasets
    already emit: an entity gated on `has_or_had_tag = CAS` *is* Castile's
    unique content. Reading their JSON keeps this a pure projection — no
    second parse, and it stays correct as those datasets grow."""
    import json
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
    from triggers import literals

    idx: dict[str, dict[str, list]] = {}
    sources = [('advances.json', 'advances', 'advances'),
               ('units.json', 'units', 'units'),
               ('buildings.json', 'buildings', 'buildings'),
               ('reforms.json', 'reforms', 'reforms'),
               ('events.json', 'events', 'events')]
    for fname, key, page in sources:
        path = ref.DATA_DIR / fname
        if not path.exists():
            continue
        for e in json.loads(path.read_text())['entities']:
            data = e.get('data') or {}
            gate = data.get('gate')
            # `tags` covers events, which name their country in
            # dynamic_historical_event rather than in a trigger
            tags = list(data.get('tags') or [])
            tags += [v for _, v in literals(gate, kinds=('tag',))] if gate else []
            for val in dict.fromkeys(tags):
                bucket = idx.setdefault(val, {})
                lst = bucket.setdefault(key, [])
                if not any(x['id'] == e['id'] for x in lst):
                    # Carry a short "what it does" so the country page is
                    # scannable without clicking or hovering through.
                    fx = [f"{m['value']} {m['label']}" for m in (e.get('mods') or [])[:3]]
                    if not fx and key == 'events':
                        fx = [o for opt in data.get('options', [])[:2]
                              for o in opt.get('effects', [])[:2]]
                    if not fx and key == 'units':
                        d = data
                        fx = [f"{lbl} {d[k]}" for k, lbl in
                              (('combat_power', 'power'), ('max_strength', 'strength'))
                              if d.get(k)]
                    lst.append({'id': e['id'], 'name': e['name'], 'slug': e['slug'],
                                'page': page, 'fx': fx[:3]})
    for buckets in idx.values():
        for lst in buckets.values():
            lst.sort(key=lambda x: x['name'])
    return idx


def main():
    countries = ref.parser.countries
    uniques = unique_index()
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
                'unique': uniques.get(tag, {}),
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
