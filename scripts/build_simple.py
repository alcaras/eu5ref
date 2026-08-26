"""Spec-driven builder for the long tail of datasets.

One SPEC entry per dataset: which parser accessor, entity type, facets,
and extra data fields. Everything else (name, desc, icon, color, modifier
collection, facet meta) is uniform. Run all: `build_simple.py`; run some:
`build_simple.py ages subjects`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import (eid, ename, export_icon, hex_color, mods_from_tree, rich,
                 slugify, write_dataset, facet_meta)


def val(obj, attr):
    """Resolve an attribute to something JSON-able (entities → names)."""
    v = getattr(obj, attr, None)
    if v is None or callable(v):
        return None
    if hasattr(v, 'display_name'):
        return v.display_name
    if isinstance(v, list):
        out = []
        for x in v:
            out.append(x.display_name if hasattr(x, 'display_name') else
                       x if isinstance(x, (str, int, float, bool)) else None)
        return [x for x in out if x is not None]
    if isinstance(v, (str, int, float, bool)):
        return round(v, 3) if isinstance(v, float) else v
    return None


MOD_ATTRS = ('modifier', 'country_modifier', 'location_modifier',
             'character_modifier', 'international_organization_modifier')

# dataset → spec. facets/data values are attr names resolved via val().
SPECS = {
    'ages': dict(accessor='age', etype='age', facets={}, data=['start_date']),
    'institutions': dict(accessor='institution', etype='institution',
                         facets={'age': 'age'}, data=[]),
    'subjects': dict(accessor='subject_types', etype='subject', facets={},
                     data=['diplomatic_capacity_cost', 'can_be_annexed',
                           'joins_overlord_wars', 'pays_overlord']),
    'international-organizations': dict(accessor='international_organizations',
                                        etype='io', facets={}, data=[]),
    'casus-belli': dict(accessor='casus_belli', etype='casus-belli',
                        facets={}, data=['war_goal', 'ticking_war_score']),
    'wargoals': dict(accessor='wargoals', etype='wargoal', facets={},
                     data=['ticking_war_score']),
    'peace-treaties': dict(accessor='peace_treaties', etype='peace-treaty',
                           facets={}, data=['cost', 'base_cost']),
    'climates': dict(accessor='climates', etype='climate', facets={}, data=[]),
    'topography': dict(accessor='topography', etype='topography', facets={},
                       data=['combat_width', 'defender_dice_modifier',
                             'movement_cost']),
    'vegetation': dict(accessor='vegetation', etype='vegetation', facets={},
                       data=['combat_width', 'defender_dice_modifier',
                             'movement_cost']),
    'town-rights': dict(accessor='town_rights', etype='town-right',
                        facets={}, data=[]),
    'location-ranks': dict(accessor='location_ranks', etype='location-rank',
                           facets={}, data=[]),
    'parliament-types': dict(accessor='parliament_types', etype='parliament-type',
                             facets={}, data=[]),
    'parliament-issues': dict(accessor='parliament_issues', etype='parliament-issue',
                              facets={'category': 'category'}, data=[]),
    'parliament-agendas': dict(accessor='parliament_agendas', etype='parliament-agenda',
                               facets={}, data=[]),
    'cabinet-actions': dict(accessor='cabinet_actions', etype='cabinet-action',
                            facets={}, data=[]),
    'heir-selections': dict(accessor='heir_selections', etype='heir-selection',
                            facets={}, data=[]),
    'societal-values': dict(accessor='societal_values', etype='societal-value',
                            facets={}, data=[]),
    'traits': dict(accessor='traits', etype='trait',
                   facets={'type': 'type'}, data=['age', 'opposites']),
    'child-educations': dict(accessor='child_educations', etype='education',
                             facets={}, data=[]),
    'character-interactions': dict(accessor='character_interactions',
                                   etype='character-interaction', facets={}, data=[]),
    'chivalric-orders': dict(accessor='chivalric_orders', etype='chivalric-order',
                             facets={}, data=[]),
    'levies': dict(accessor='levies', etype='levy', facets={}, data=[]),
    'recruitment-methods': dict(accessor='recruitment_method', etype='recruitment-method',
                                facets={}, data=[]),
    'country-interactions': dict(accessor='country_interactions',
                                 etype='country-interaction', facets={}, data=[]),
    'situations': dict(accessor='situations', etype='situation', facets={}, data=[]),
    'disasters': dict(accessor='disasters', etype='disaster', facets={}, data=[]),
    'diseases': dict(accessor='diseases', etype='disease', facets={}, data=[]),
    'government-types': dict(accessor='government_types', etype='government-type',
                             facets={}, data=[]),
    'country-ranks': dict(accessor='country_ranks', etype='country-rank',
                          facets={}, data=[]),
    'religious-aspects': dict(accessor='religious_aspects', etype='religious-aspect',
                              facets={'religion': 'religion'}, data=[]),
    'religious-schools': dict(accessor='religious_schools', etype='religious-school',
                              facets={}, data=[]),
    'holy-sites': dict(accessor='holy_sites', etype='holy-site', facets={}, data=[]),
}


def build(name: str, spec: dict) -> None:
    try:
        items = getattr(ref.parser, spec['accessor'])
    except Exception as ex:
        print(f'  {name}: SKIPPED ({type(ex).__name__}: {str(ex)[:80]})')
        return
    entities = []
    for key, obj in sorted(items.items()):
        slug = slugify(key)
        mods = []
        for attr in MOD_ATTRS:
            v = getattr(obj, attr, None)
            if v is not None and not callable(v):
                try:
                    mods.extend(mods_from_tree(v))
                except Exception:
                    pass
        facets = {}
        for fkey, fattr in spec['facets'].items():
            facets[fkey] = val(obj, fattr) if isinstance(fattr, str) else fattr(obj)
        data = {}
        for dattr in spec['data']:
            v = val(obj, dattr)
            if v is not None:
                data[dattr] = v
        display = getattr(obj, 'display_name', None) or ref.pretty(key)
        entities.append({
            'id': eid(spec['etype'], key),
            'type': spec['etype'],
            'slug': slug,
            'icon': export_icon(obj, spec['etype'], slug),
            'name': display,
            'desc': rich(getattr(obj, 'description', None)),
            'color': hex_color(getattr(obj, 'color', None)) if not isinstance(getattr(obj, 'color', None), str) else None,
            'facets': facets,
            'mods': mods,
            'data': data,
        })
    write_dataset(name, {
        'dataset': name,
        'source': spec['accessor'],
        'entities': entities,
        'facets': facet_meta(entities, [(k, ref.pretty(k)) for k in spec['facets']]),
    })


def main():
    only = sys.argv[1:]
    for name, spec in SPECS.items():
        if only and name not in only:
            continue
        build(name, spec)


if __name__ == '__main__':
    main()
