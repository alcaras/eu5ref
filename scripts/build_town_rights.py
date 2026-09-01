"""in_game/common/town_rights → src/data/town-rights.json.

The game calls these Urban Rights: a country grants one to a town or city
(1 slot in a town, 2 in a city, 3 in a megalopolis — `local_possible_town_
rights` on the location ranks). Each carries a `location_modifier` that
lands on that one location and, sometimes, a `country_modifier` that lands
on the whole realm — a distinction the generic builder flattened away, so
they get their own builder. It also resolves who may grant one
(potential/allow) and which good a specialization right is for.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
import requirements
from ref import (eid, export_icon, hex_color, mods_from_tree, rich, slugify,
                 write_dataset, facet_meta)

SCOPES = (('location_modifier', 'Location'), ('country_modifier', 'Country'))
# `local_<good>_output_modifier` / `local_<good>_guild_building_levels` —
# what a specialization right is actually for.
GOOD_KEY = re.compile(r'^(?:local_)?([a-z_]+?)_(?:output_modifier|guild_building_levels)$')


def goods_index() -> dict[str, dict]:
    """good script key → {id, label}, for linking a right to what it boosts."""
    import json
    payload = json.loads((Path('src/data/goods.json')).read_text())
    return {e['id'].split(':', 1)[1]: {'id': e['id'], 'label': e['name']}
            for e in payload['entities']}


def main():
    rights = ref.parser.town_rights
    goods = goods_index()
    entities = []
    for name, t in sorted(rights.items()):
        slug = slugify(name)
        groups, mods = [], []
        for attr, scope in SCOPES:
            block = mods_from_tree(getattr(t, attr, None))
            if block:
                groups.append({'scope': scope, 'mods': block})
                mods.extend(block)
        req = requirements.describe(getattr(t, 'potential', None),
                                    getattr(t, 'allow', None), limit=10)
        unlocked = [getattr(a, 'display_name', str(a))
                    for a in (getattr(t, 'unlocked_by', None) or [])]
        boosts, seen = [], set()
        for m in mods:
            hit = GOOD_KEY.match(m['key'])
            good = goods.get(hit.group(1)) if hit else None
            if good and good['id'] not in seen:
                seen.add(good['id'])
                boosts.append(good)
        entities.append({
            'id': eid('town-right', name),
            'type': 'town-right',
            'slug': slug,
            'icon': export_icon(t, 'town-right', slug),
            'name': t.display_name,
            'desc': rich(t.description),
            'color': hex_color(getattr(t, 'color', None)),
            'facets': {
                'source': 'Unlocked by an advance' if unlocked else 'Available from the start',
                'kept': 'Kept at conquest' if getattr(t, 'kept_at_conquest', True)
                        else 'Lost at conquest',
                'good': [g['label'] for g in boosts] or None,
                'requires': req['tags'],
            },
            'mods': mods,
            'data': {
                'groups': groups,
                'location_mods': next((g['mods'] for g in groups if g['scope'] == 'Location'), []),
                'country_mods': next((g['mods'] for g in groups if g['scope'] == 'Country'), []),
                'requires': req['lines'],
                'unlocked_by': unlocked,
                'boosts': boosts,
                'kept_at_conquest': bool(getattr(t, 'kept_at_conquest', True)),
            },
        })
    write_dataset('town-rights', {
        'dataset': 'town-rights',
        'source': 'in_game/common/town_rights',
        'entities': entities,
        'facets': facet_meta(entities, [('source', 'Source'), ('kept', 'At conquest'),
                                        ('good', 'Boosts'), ('requires', 'Requires')]),
    })


if __name__ == '__main__':
    main()
