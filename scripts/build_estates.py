"""estates + estate_privileges → estates.json, estate-privileges.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
import requirements
from ref import (eid, ename, export_icon, hex_color, mods_from_tree, rich,
                 slugify, write_dataset, facet_meta)


def main():
    estates = ref.parser.estates
    entities = []
    for name, e in sorted(estates.items()):
        slug = slugify(name)
        entities.append({
            'id': eid('estate', name),
            'type': 'estate',
            'slug': slug,
            'icon': export_icon(e, 'estate', slug),
            'name': e.display_name,
            'desc': rich(e.description),
            'color': hex_color(e.color),
            'facets': {},
            'mods': mods_from_tree(getattr(e, 'modifier', None)),
            'data': {},
        })
    write_dataset('estates', {
        'dataset': 'estates',
        'source': 'in_game/common/estates',
        'entities': entities,
        'facets': [],
    })

    privileges = ref.parser.estate_privileges
    pents = []
    for name, p in sorted(privileges.items()):
        slug = slugify(name)
        mods = mods_from_tree(getattr(p, 'modifier', None))
        mods += mods_from_tree(getattr(p, 'country_modifier', None))
        estate_obj = p.estate if not isinstance(p.estate, str) else None
        # Privileges are gated in several different ways — a country tag, a
        # culture or religion, an advance, an age — and the file gives no
        # single field for it. Compile the country-ish gate, and summarise
        # the rest of `allow` / `unlocked_by` so the page can show both.
        gate, gate_labels = ref.gate_of(p, 'potential', 'allow')
        # Everything gating the privilege, in one readable list: `potential`
        # (who ever sees it) and `allow` (who may grant it) both matter to a
        # player, and neither is expressed anywhere else on the entity.
        req = requirements.describe(getattr(p, 'potential', None),
                                    getattr(p, 'allow', None), limit=6)
        unlocked_by = getattr(p, 'unlocked_by', None)
        if unlocked_by is not None and not isinstance(unlocked_by, (str, int, float)):
            unlocked_by = getattr(unlocked_by, 'display_name', None)
        pents.append({
            'id': eid('privilege', name),
            'type': 'privilege',
            'slug': slug,
            'icon': export_icon(p, 'privilege', slug),
            'name': p.display_name,
            'desc': rich(p.description),
            'facets': {
                'estate': ename(estate_obj) or (p.estate if isinstance(p.estate, str) else 'Any'),
                'requires': req['tags'],
            },
            'mods': mods,
            'data': {
                'can_revoke': bool(getattr(p, 'can_revoke', True)),
                'gate': gate,
                'gate_labels': gate_labels,
                'requires': req['lines'],
                'unlocked_by': unlocked_by if isinstance(unlocked_by, str) else None,
            },
        })
    write_dataset('estate-privileges', {
        'dataset': 'estate-privileges',
        'source': 'in_game/common/estate_privileges',
        'entities': pents,
        'facets': facet_meta(pents, [('estate', 'Estate'), ('requires', 'Requires')]),
    })


if __name__ == '__main__':
    main()
