"""setup/countries (+ start data) → countries.json; formable_countries →
formables.json. The 1337 world."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import (eid, ename, hex_color, rich, slugify, write_dataset,
                 facet_meta)


def main():
    countries = ref.parser.countries
    entities = []
    for tag, c in sorted(countries.items()):
        if tag in ('DUMMY', 'PIR', 'MER'):
            continue
        slug = slugify(tag)
        culture = ename(c.culture_definition)
        religion = ename(c.religion_definition)
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
