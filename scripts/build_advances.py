"""in_game/common/advances → src/data/advances.json.

Beyond the flat list, this computes the structure the game itself uses:

* **branch** — each age has a handful of root advances (the ones the files
  mark `depth = 0`); every other advance hangs off exactly one of them via
  `requires`. Discovery, for instance, is New World / Pike and Shot /
  Printing Press / Surgery. We resolve each advance to its root branch and
  its tier (distance from that root) so the planner can draw the same shape.
* **gate** — the `potential` trigger compiled to a boolean expression over
  country facts (see scripts/lib/triggers.py), so the planner can tell which
  advances are actually available to a chosen country.
* **unlocks** — the ~1,100 buildings / units / laws / reforms an advance
  grants, which is what the in-game card shows under the effects.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
import triggers
from ref import (eid, ename, export_icon, mods_from_tree, ref_list, rich,
                 slugify, write_dataset, facet_meta)

# unlock_<field> → (label, entity type for linking)
UNLOCK_FIELDS = {
    'unlock_building': ('Buildings', 'building'),
    'unlock_unit': ('Units', 'unit'),
    'unlock_law': ('Laws', 'law'),
    'unlock_levy': ('Levies', 'levy'),
    'unlock_government_reform': ('Reforms', 'reform'),
    'unlock_town_rights': ('Town rights', 'town-right'),
    'unlock_cabinet_action': ('Cabinet actions', 'cabinet-action'),
    'unlock_production_method': ('Production methods', None),
    'unlock_estate_privilege': ('Estate privileges', 'privilege'),
    'unlock_policy': ('Policies', None),
    'unlock_subject_type': ('Subject types', 'subject'),
    'unlock_chivalric_order': ('Chivalric orders', 'chivalric-order'),
    'unlock_heir_selection': ('Heir selection', 'heir-selection'),
    'unlock_casus_belli': ('Casus belli', 'casus-belli'),
    'unlock_road_type': ('Road types', None),
    'unlock_diplomacy': ('Diplomacy', 'concept'),
    'unlock_ability': ('Unit abilities', None),
    'unlock_interaction': ('Character interactions', 'character-interaction'),
    'unlock_country_interaction': ('Country interactions', 'country-interaction'),
}


def collect_unlocks(a) -> list[dict]:
    out = []
    for field, (label, etype) in UNLOCK_FIELDS.items():
        items = getattr(a, field, None) or []
        if not items:
            continue
        entries = []
        for it in items:
            nm = getattr(it, 'display_name', None) or str(it)
            key = getattr(it, 'name', None)
            entries.append({'id': eid(etype, key) if (etype and key) else None,
                            'label': nm})
        out.append({'label': label, 'items': entries})
    return out


def main():
    advances = ref.parser.advances
    cgroups = ref.culture_group_keys()
    labels = ref.label_map()

    # ── pass 1: raw records ────────────────────────────────────
    recs = {}
    for name, a in advances.items():
        gate = triggers.compile_trigger(getattr(a, 'potential', None), cgroups)
        recs[name] = {
            'obj': a,
            'age': ename(a.age) or 'No age',
            'requires': [r for r in (getattr(a, 'requires', None) or [])],
            'gate': gate,
            'explicit_root': a.depth == 0,
        }

    # ── pass 2: branch + tier within each age ──────────────────
    # Parent = the first prerequisite in the same age (the files build each
    # age as a forest of chains; cross-age prereqs start a new local root).
    parent: dict[str, str | None] = {}
    for name, r in recs.items():
        p = None
        for req in r['requires']:
            rn = getattr(req, 'name', None)
            if rn in recs and recs[rn]['age'] == r['age'] and not r['explicit_root']:
                p = rn
                break
        parent[name] = p

    def root_of(n, seen=()):
        p = parent.get(n)
        if p is None or p in seen:
            return n
        return root_of(p, seen + (n,))

    def tier_of(n, seen=()):
        p = parent.get(n)
        if p is None or p in seen:
            return 0
        return 1 + tier_of(p, seen + (n,))

    # ── pass 3: emit ───────────────────────────────────────────
    entities = []
    for name in sorted(recs):
        r = recs[name]
        a = r['obj']
        slug = slugify(name)
        national = bool(a.countries) or a.in_tree_of is not None or r['gate'] is not None
        root = root_of(name)
        gate = r['gate']
        # Keep each literal's KIND and raw value alongside its label: the
        # planner needs to tell "another country's tag" (unreachable) from a
        # formable's tag (reachable) or a religion (convertible).
        gate_labels, gate_lits = [], []
        if gate:
            seen = set()
            for kind, v in triggers.literals(gate):
                lab = labels.get(v) or ref.pretty(v)
                if lab in seen:
                    continue
                seen.add(lab)
                gate_labels.append(lab)
                gate_lits.append([lab, kind, v])
        entities.append({
            'id': eid('advance', name),
            'type': 'advance',
            'slug': slug,
            'icon': export_icon(a, 'advance', slug),
            'name': a.display_name,
            'desc': rich(a.description),
            'facets': {
                'age': r['age'],
                'scope': 'national' if national else 'general',
                'branch': recs[root]['obj'].display_name,
            },
            'mods': mods_from_tree(a.modifiers),
            'data': {
                'tier': tier_of(name),
                'branch_id': eid('advance', root),
                'requires': ref_list(r['requires'], 'advance'),
                'countries': [c.display_name for c in (a.countries or [])],
                'tree': ename(a.in_tree_of),
                'specialization': getattr(a, 'age_specialization', None),
                'gate': gate,
                'gate_labels': gate_labels,
                'gate_lits': gate_lits,
                'requires_state': triggers.summarize(getattr(a, 'allow', None), labels),
                'unlocks': collect_unlocks(a),
            },
        })

    write_dataset('advances', {
        'dataset': 'advances',
        'source': 'in_game/common/advances',
        'entities': entities,
        'facets': facet_meta(entities, [('age', 'Age'), ('scope', 'Scope')]),
    })

    if triggers.UNHANDLED:
        total = sum(triggers.UNHANDLED.values())
        print(f'  gate predicates left dynamic ("?"): {total} across '
              f'{len(triggers.UNHANDLED)} keys — top:')
        for k, n in triggers.UNHANDLED.most_common(10):
            print(f'     {k} ×{n}')


if __name__ == '__main__':
    main()
