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
import layout
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
        # `government = steppe_horde` / `country_type = army` are gates too,
        # declared as plain fields beside `potential` — 71 advances carry
        # one (Yams of the Great Khān is a horde advance, not everyone's).
        # A playable country's type is `real`; the virtual types (army,
        # building, location, pop, navy) never apply to a player.
        parts = [gate] if gate else []
        gov = getattr(a, 'government', None)
        if gov is not None and getattr(gov, 'name', None):
            parts.append(['gov', gov.name])
        ctype = getattr(a, 'country_type', None)
        if isinstance(ctype, str) and ctype:
            parts.append(['ctype', ctype])
        if len(parts) > 1:
            gate = ['and'] + parts
        elif parts:
            gate = parts[0]
        recs[name] = {
            'obj': a,
            'age': ename(a.age) or 'No age',
            'requires': [r for r in (getattr(a, 'requires', None) or [])],
            'gate': gate,
            'allow_state': triggers.summarize(getattr(a, 'allow', None), labels),
        }

    # ── pass 2: where each advance is drawn ───────────────────
    # The tech screen is a forest per age; `requires` and `depth = 0` fix
    # most of it, but 383 advances (every focus advance among them) declare
    # neither and the game slots them in with a deterministic packing pass
    # at load. scripts/lib/layout.py re-runs that pass over the files, so
    # tree, parent and tier below are the game's own — `declared` says
    # whether the files fix the parent (requires/root) or the pass did.
    placed = layout.run(str(ref.ROOT / 'game' / 'in_game'))
    missing = [n for n in recs if n not in placed]
    if missing:
        raise SystemExit(f'layout pass left {len(missing)} advances unplaced: {missing[:5]}')

    # ── pass 3: emit ───────────────────────────────────────────
    entities = []
    for name in sorted(recs):
        r = recs[name]
        a = r['obj']
        slug = slugify(name)
        national = bool(a.countries) or a.in_tree_of is not None or r['gate'] is not None
        pl = placed[name]
        root = pl['tree']
        drawn_in = {'id': eid('advance', root), 'name': ename(recs[root]['obj']),
                    'computed': not pl['tree_declared']}
        # The node it hangs off. For a declared advance that is its
        # prerequisite; for an orphan it is the slot the layout pass gave it,
        # which in game must be researched first just the same (the files
        # only omit to say so) — flagged computed.
        drawn_under = ({'id': eid('advance', pl['parent']),
                        'name': ename(recs[pl['parent']]['obj']),
                        'computed': not pl['declared']}
                       if pl['parent'] and pl['parent'] != name else None)
        gate = r['gate']
        # Keep each literal's KIND and raw value alongside its label: the
        # planner needs to tell "another country's tag" (unreachable) from a
        # formable's tag (reachable) or a religion (convertible).
        gate_labels, gate_lits = [], []
        if gate:
            seen = set()
            for kind, v in triggers.literals(gate):
                lab = triggers.label_of(kind, v, labels)
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
                'tier': pl['depth'] - 1,
                'tree_index': pl['tree_index'],
                'tree_slot': pl['slot'],          # left-to-right among its siblings
                'branch_id': eid('advance', root),
                'requires': ref_list(r['requires'], 'advance'),
                'countries': [c.display_name for c in (a.countries or [])],
                'tree': ename(a.in_tree_of),
                'specialization': getattr(a, 'age_specialization', None),
                'drawn_in': drawn_in,
                'drawn_under': drawn_under,
                'gate': gate,
                'gate_labels': gate_labels,
                'gate_lits': gate_lits,
                'requires_state': r['allow_state'],
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
