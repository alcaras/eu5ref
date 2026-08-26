"""in_game/common/laws → src/data/laws.json. A law is a group; its
selectable policies (with their modifiers) are nested in data.policies."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import (eid, export_icon, mods_from_tree, rich, slugify,
                 write_dataset, facet_meta)


def policy_mods(pol) -> list[dict]:
    mods = []
    for attr in ('modifier', 'country_modifier', 'international_organization_modifier',
                 'location_modifier'):
        v = getattr(pol, attr, None)
        if v is not None and not callable(v):
            try:
                mods.extend(mods_from_tree(v))
            except Exception:
                pass
    return mods


def main():
    laws = ref.parser.laws
    entities = []
    for name, law in sorted(laws.items()):
        slug = slugify(name)
        policies = []
        pol_dict = law.policies if isinstance(law.policies, dict) else {}
        for pkey, pol in pol_dict.items():
            policies.append({
                'key': pkey,
                'name': pol.display_name,
                'desc': rich(getattr(pol, 'description', None)),
                'mods': policy_mods(pol),
            })
        entities.append({
            'id': eid('law', name),
            'type': 'law',
            'slug': slug,
            'icon': export_icon(law, 'law', slug),
            'name': law.display_name,
            'desc': rich(law.description),
            'facets': {
                'category': str(law.law_category) if law.law_category else 'uncategorized',
                'government': (law.law_gov_group.display_name
                               if hasattr(law.law_gov_group, 'display_name')
                               else law.law_gov_group) or 'Any',
                'religion': (law.law_religion_group.display_name
                             if hasattr(law.law_religion_group, 'display_name')
                             else law.law_religion_group if isinstance(law.law_religion_group, str)
                             else None) or None,
            },
            'mods': mods_from_tree(getattr(law, 'modifier', None)),
            'data': {
                'policy_names': [p['name'] for p in policies],
                'policies': policies,
            },
        })
    write_dataset('laws', {
        'dataset': 'laws',
        'source': 'in_game/common/laws',
        'entities': entities,
        'facets': facet_meta(entities, [('category', 'Category'), ('government', 'Government'), ('religion', 'Religion')]),
    })


if __name__ == '__main__':
    main()
