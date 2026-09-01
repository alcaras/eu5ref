"""in_game/common/laws → src/data/laws.json. A law is a group; its
selectable policies (with their modifiers) are nested in data.policies.

The toolkit models only a policy's `country_modifier` and
`international_organization_modifier`, so a policy whose whole effect is a
`location_modifier` (Administration of Italian Lands, every one of its
policies) came out with no effects at all. Anything the toolkit does not
model is read straight off the raw tree here, grouped by the scope it
applies to, so a location effect is never shown as if it were a country one.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
import requirements
from ref import (eid, export_icon, mod_json, mods_from_tree, plain_text, rich,
                 slugify, write_dataset, facet_meta)

# Keys of a law block that are the law's own metadata; everything else nested
# under a law is one of its selectable policies.
LAW_META = {
    'law_category', 'law_gov_group', 'law_religion_group', 'law_country_group',
    'potential', 'allow', 'locked', 'unique', 'has_levels', 'requires_vote',
    'type', 'icon', 'ai_will_do', 'unlocked_by',
}
# modifier block → the scope it lands on. The scope IS the information: a
# +10% that applies to a handful of locations is not a country bonus.
SCOPES = {
    'country_modifier': 'Country',
    'modifier': 'Country',
    'location_modifier': 'Locations',
    'owned_location_modifier': 'Owned locations',
    'leader_modifier': 'Organization leader',
    'international_organization_modifier': 'Organization',
}
# Inside a modifier block these are conditions/scaling, not modifiers.
NON_MOD = {'potential_trigger', 'scale', 'trigger', 'desc'}


def raw_laws() -> dict:
    """law key → {policy key → raw block}, for the fields the toolkit drops."""
    out = {}
    tree = ref.parser.parser.parse_folder_as_one_file('in_game/common/laws')
    for lk, lb in tree:
        if not hasattr(lb, 'iterate_with_duplicates'):
            continue
        pols = {}
        for pk, pb in lb.iterate_with_duplicates():
            if str(pk) in LAW_META or not hasattr(pb, 'iterate_with_duplicates'):
                continue
            pols[str(pk)] = pb
        out[str(lk)] = pols
    return out


def scoped_mods(block) -> list[dict]:
    """Every modifier block on a policy → [{scope, when, mods}]."""
    groups = []
    if not hasattr(block, 'iterate_with_duplicates'):
        return groups
    for k, v in block.iterate_with_duplicates():
        scope = SCOPES.get(str(k))
        if scope is None or not hasattr(v, 'iterate_with_duplicates'):
            continue
        mods, when = [], None
        for mk, mv in v.iterate_with_duplicates():
            mkey = str(mk)
            if mkey in NON_MOD:
                if mkey == 'potential_trigger':
                    lines = requirements.describe(mv, limit=2)['lines']
                    when = '; '.join(lines) or None
                continue
            if hasattr(mv, 'iterate_with_duplicates'):
                continue
            mods.append(mod_json(mkey, mv))
        if not mods:
            continue
        # a policy may declare the same block twice (the files do); one group
        # per (scope, condition) reads better than two identical headings
        for g in groups:
            if g['scope'] == scope and g['when'] == when:
                g['mods'].extend(mods)
                break
        else:
            groups.append({'scope': scope, 'when': when, 'mods': mods})
    return groups


def main():
    laws = ref.parser.laws
    raw = raw_laws()
    entities = []
    for name, law in sorted(laws.items()):
        slug = slugify(name)
        gate, gate_labels = ref.gate_of(law, 'potential', 'allow')
        law_req = requirements.describe(getattr(law, 'potential', None),
                                        getattr(law, 'allow', None),
                                        getattr(law, 'locked', None), limit=6)
        policies = []
        pol_dict = law.policies if isinstance(law.policies, dict) else {}
        raw_pols = raw.get(name, {})
        for pkey, pol in pol_dict.items():
            block = raw_pols.get(pkey)
            groups = scoped_mods(block) if block is not None else []
            if not groups:   # nothing raw (shouldn't happen) — fall back to the toolkit
                mods = (mods_from_tree(getattr(pol, 'country_modifier', None))
                        + mods_from_tree(getattr(pol, 'international_organization_modifier', None)))
                if mods:
                    groups = [{'scope': 'Country', 'when': None, 'mods': mods}]
            preq = requirements.describe(getattr(pol, 'potential', None),
                                         getattr(pol, 'allow', None), limit=5)
            years = getattr(pol, 'years', 0) or 0
            policies.append({
                'key': pkey,
                'name': pol.display_name,
                'desc': rich(getattr(pol, 'description', None)),
                # flat list kept for the tables that render one mods column
                'mods': [m for g in groups for m in g['mods']],
                'groups': groups,
                'requires': preq['lines'],
                'excludes': preq['excludes'],
                'req_tags': preq['tags'],
                'availability': preq['availability'],
                'years': years,
            })
        # A law's requirement tags include everything its policies need — the
        # list page filters laws, and a law you can only reach as Byzantium
        # should show up under Country there too.
        tags = sorted({t for t in law_req['tags'] if t != requirements.NONE}
                      | {t for p in policies for t in p['req_tags'] if t != requirements.NONE},
                      key=lambda t: requirements.ORDER.index(t)
                      if t in requirements.ORDER else 99)
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
                'requires': tags or [requirements.NONE],
                'availability': (requirements.SOME_COUNTRIES
                                 if law_req['availability'] == requirements.SOME_COUNTRIES
                                 or any(p['availability'] == requirements.SOME_COUNTRIES
                                        for p in policies)
                                 else requirements.ANY_COUNTRY),
            },
            'mods': mods_from_tree(getattr(law, 'modifier', None)),
            'data': {
                'gate': gate,
                'gate_labels': gate_labels,
                'policy_names': [p['name'] for p in policies],
                'policies': policies,
                'requires': law_req['lines'],
                'excludes': law_req['excludes'],
                'requires_vote': bool(getattr(law, 'requires_vote', False)),
            },
        })
    write_dataset('laws', {
        'dataset': 'laws',
        'source': 'in_game/common/laws',
        'entities': entities,
        'facets': facet_meta(entities, [('availability', 'Availability'),
                                        ('category', 'Category'), ('government', 'Government'),
                                        ('religion', 'Religion'), ('requires', 'Requires')]),
    })


if __name__ == '__main__':
    main()
