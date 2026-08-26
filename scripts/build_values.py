"""societal values + everything that moves them → src/data/values.json.

A country's societal values sit on a -100..+100 axis (SOCIETAL_VALUE_MIN/MAX)
and drift when something applies a `monthly_towards_<side>` modifier. The
side is in the modifier's own name, and the magnitude is a named constant
with a real number behind it (default_values.txt):

    tiny 0.025 · minor 0.05 · normal 0.1 · large 0.2 · significant 0.33 ·
    huge 0.5   (huge is flagged in the files as "very short term" only)

So picking a set of laws, reforms and privileges gives a net monthly drift
per axis, which is what the values planner adds up.

Movers live in a dozen different folders and at different nesting depths —
a law's policies, an estate's privileges, a reform's country_modifier — so
rather than hand-listing shapes we walk each folder's raw tree and record
every `monthly_towards_*` we find, remembering which top-level entity it
belonged to.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
import triggers
from ref import eid, slugify, write_dataset

# folder → (source label, entity type for linking to our own pages)
SOURCES = {
    'laws': ('Law', 'law'),
    'government_reforms': ('Reform', 'reform'),
    'estate_privileges': ('Estate privilege', 'privilege'),
    'religious_aspects': ('Religious aspect', 'religious-aspect'),
    'international_organizations': ('International organization', 'io'),
    'cabinet_actions': ('Cabinet action', 'cabinet-action'),
    'subject_types': ('Subject type', 'subject'),
    'parliament_issues': ('Parliament issue', 'parliament-issue'),
    'parliament_agendas': ('Parliament agenda', 'parliament-agenda'),
    'regencies': ('Regency', None),
    'generic_actions': ('Action', None),
    'building_types': ('Building', 'building'),
    'missions': ('Mission', 'mission'),
    'employment_systems': ('Employment system', None),
    'societal_values': ('Societal value', 'societal-value'),
    'policies': ('Policy', None),
    'estates': ('Estate', 'estate'),
    'town_rights': ('Town right', 'town-right'),
}


def magnitudes() -> dict[str, float]:
    """Named movement constants → their numbers."""
    out = {}
    path = (ref.ROOT / 'game' / 'main_menu' / 'common' / 'script_values'
            / 'default_values.txt')
    if path.exists():
        for m in re.finditer(r'^(societal_value_[a-z_]*move[a-z_]*)\s*=\s*([0-9.]+)',
                             path.read_text(encoding='utf-8-sig', errors='replace'), re.M):
            out[m.group(1)] = float(m.group(2))
    return out


def value_pairs() -> dict[str, dict]:
    """The 17 axes. The id names both ends: left_vs_right."""
    pairs = {}
    try:
        tree = ref.parser.parser.parse_folder_as_one_file('in_game/common/societal_values')
    except Exception:
        return pairs
    for key, block in tree:
        key = str(key)
        if '_vs_' not in key:
            continue
        left, right = key.split('_vs_', 1)
        pairs[key] = {
            'id': key,
            'left': {'key': left, 'name': ref.plain_text(ref.parser.localize(left, default='')) or ref.pretty(left)},
            'right': {'key': right, 'name': ref.plain_text(ref.parser.localize(right, default='')) or ref.pretty(right)},
            'left_mods': ref.mods_from_tree(block.get('left_modifier')) if hasattr(block, 'get') else [],
            'right_mods': ref.mods_from_tree(block.get('right_modifier')) if hasattr(block, 'get') else [],
        }
    return pairs


def walk(node, found: list, mags: dict, depth=0):
    """Collect every monthly_towards_* under this node."""
    if depth > 8 or not hasattr(node, 'iterate_with_duplicates'):
        return
    try:
        pairs = list(node.iterate_with_duplicates())
    except Exception:
        return
    for k, v in pairs:
        k = str(k)
        if k.startswith('monthly_towards_'):
            side = k[len('monthly_towards_'):]
            amount = mags.get(str(v)) if not isinstance(v, (int, float)) else float(v)
            found.append((side, amount, str(v)))
        elif hasattr(v, 'iterate_with_duplicates'):
            walk(v, found, mags, depth + 1)


# `societal_value:<axis> <op> <n>` — the requirement syntax. Read from the
# raw text because the operator matters and is not preserved as a key.
_REQ = re.compile(r'societal_value:([a-z_]+)\s*(>=|<=|>|<|=)\s*(-?[0-9.]+)')
# Which block a requirement sits in decides whether it is a one-off gate.
# Per common/government_reforms/readme.txt: `allow` is "whether the action
# can start", `locked` is "currently locked and cannot be interacted with".
# There is no remove_if, so a reform enacted while a value qualified is NOT
# undone when the value drifts back — which is what makes the swap-away
# dance work. Reforms do take years/months to implement though, and their
# modifiers scale with progress, so the value has to hold that long.
_BLOCKS = ('allow', 'locked', 'potential', 'can_start', 'trigger')


def requirements() -> list[dict]:
    """Everything that demands a societal value position, with its axis,
    comparison and threshold."""
    out = []
    for folder, (label, etype) in SOURCES.items():
        d = ref.ROOT / 'game' / 'in_game' / 'common' / folder
        if not d.is_dir():
            continue
        for f in sorted(d.glob('*.txt')):
            txt = f.read_text(encoding='utf-8-sig', errors='replace')
            if 'societal_value:' not in txt:
                continue
            for m in re.finditer(r'^([a-z_0-9]+)\s*=\s*\{', txt, re.M):
                i = m.end(); depth = 1; start = i
                while i < len(txt) and depth:
                    if txt[i] == '{':
                        depth += 1
                    elif txt[i] == '}':
                        depth -= 1
                    i += 1
                body = txt[start:i - 1]
                hits = list(_REQ.finditer(body))
                if not hits:
                    continue
                key = m.group(1)
                reqs = []
                for h in hits:
                    axis, op, num = h.group(1), h.group(2), float(h.group(3))
                    before = body[:h.start()]
                    block = next((b for b in _BLOCKS
                                  if before.rfind(b + ' =') > before.rfind('}')), None)
                    reqs.append({'pair': axis, 'op': op, 'value': num,
                                 'block': block or 'unknown'})
                out.append({
                    'key': key,
                    'name': (ref.plain_text(ref.parser.localize(key, default='')) or
                             ref.pretty(key)),
                    'source': label,
                    'folder': folder,
                    'id': eid(etype, key) if etype else None,
                    'slug': slugify(key),
                    'requires': reqs,
                })
    return out


def main():
    mags = magnitudes()
    labels = ref.label_map()
    cgroups = ref.culture_group_keys()
    pairs = value_pairs()
    side_to_pair = {}
    for pid, p in pairs.items():
        side_to_pair[p['left']['key']] = (pid, 'left')
        side_to_pair[p['right']['key']] = (pid, 'right')

    movers = []
    unresolved_sides: dict[str, int] = {}
    for folder, (label, etype) in SOURCES.items():
        try:
            tree = ref.parser.parser.parse_folder_as_one_file(f'in_game/common/{folder}')
        except Exception:
            continue
        for key, block in tree:
            if not hasattr(block, 'iterate_with_duplicates'):
                continue
            found: list = []
            walk(block, found, mags)
            if not found:
                continue
            name = (ref.plain_text(ref.parser.localize(str(key), default='')) or
                    ref.pretty(str(key)))
            # Who may use it, so the planner can hide what your country
            # cannot take, and which estate a privilege belongs to.
            gate = gate_labels = None
            for gk in ('potential', 'allow'):
                blk = block.get(gk) if hasattr(block, 'get') else None
                if blk is not None and hasattr(blk, 'iterate_with_duplicates'):
                    expr = triggers.compile_trigger(blk, cgroups)
                    if expr:
                        gate = expr
                        seen_l, gate_labels = set(), []
                        for kind, v in triggers.literals(expr):
                            lab = labels.get(v) or ref.pretty(v)
                            if lab not in seen_l:
                                seen_l.add(lab)
                                gate_labels.append([lab, kind, v])
                        break
            estate = None
            ev = block.get('estate') if hasattr(block, 'get') else None
            if ev is not None and isinstance(ev, str):
                estate = ref.pretty(ev.split(':')[-1])
            effects = []
            for side, amount, raw in found:
                hit = side_to_pair.get(side)
                if not hit:
                    unresolved_sides[side] = unresolved_sides.get(side, 0) + 1
                    continue
                pid, direction = hit
                effects.append({'pair': pid, 'dir': direction,
                                'perMonth': amount, 'raw': raw})
            if not effects:
                continue
            movers.append({
                'key': str(key),
                'name': name,
                'source': label,
                'folder': folder,
                'id': eid(etype, str(key)) if etype else None,
                'slug': slugify(str(key)),
                'effects': effects,
                'gate': gate,
                'gateLabels': gate_labels or [],
                'estate': estate,
            })

    # the same key can appear in more than one file of a folder
    seen, deduped = set(), []
    for m in movers:
        sig = (m['folder'], m['key'])
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(m)
    movers = deduped
    movers.sort(key=lambda m: (m['source'], m['name']))
    entities = [{
        'id': eid('societal-value', pid),
        'type': 'societal-value',
        'slug': slugify(pid),
        'name': f"{p['left']['name']} vs {p['right']['name']}",
        'facets': {},
        'mods': [],
        'data': {**p,
                 'movers': [m['key'] for m in movers
                            if any(e['pair'] == pid for e in m['effects'])]},
    } for pid, p in pairs.items()]

    write_dataset('values', {
        'dataset': 'values',
        'source': 'in_game/common/societal_values + everything with monthly_towards_*',
        'entities': entities,
        'facets': [],
    })

    reqs = requirements()

    # icons come from the datasets that already exported them
    icons: dict[str, str] = {}
    for fname in ('reforms.json', 'estate-privileges.json', 'buildings.json',
                  'religious-aspects.json', 'cabinet-actions.json', 'laws.json',
                  'subjects.json', 'estates.json', 'missions.json'):
        path = ref.DATA_DIR / fname
        if not path.exists():
            continue
        for e in json.loads(path.read_text())['entities']:
            if e.get('icon'):
                icons[e['id']] = e['icon']
    for m in movers:
        if m['id'] and m['id'] in icons:
            m['icon'] = icons[m['id']]
    for r in reqs:
        if r['id'] and r['id'] in icons:
            r['icon'] = icons[r['id']]

    # countries, so the planner can default culture/religion from a tag
    countries = []
    cpath = ref.DATA_DIR / 'countries.json'
    if cpath.exists():
        for c in json.loads(cpath.read_text())['entities']:
            countries.append({'t': c['data']['tag'], 'n': c['name'],
                              'col': c.get('color'),
                              'cu': c['facets']['culture'], 're': c['facets']['religion'],
                              'f': c['data'].get('facts') or {}})
        countries.sort(key=lambda c: c['n'])
    cultures = religions = []
    cu_path, re_path = ref.DATA_DIR / 'cultures.json', ref.DATA_DIR / 'religions.json'
    if cu_path.exists():
        cultures = [{'k': e['id'].split(':', 1)[1], 'n': e['name'],
                     'g': e['data'].get('group_keys') or [],
                     'l': e['data'].get('language_key')}
                    for e in json.loads(cu_path.read_text())['entities']]
    if re_path.exists():
        religions = [{'k': e['id'].split(':', 1)[1], 'n': e['name'],
                      'g': e['data'].get('group_key')}
                     for e in json.loads(re_path.read_text())['entities']]

    out = ref.ROOT / 'public' / 'values.json'
    out.write_text(json.dumps({
        'scale': 100,           # SOCIETAL_VALUE_MAX
        'magnitudes': mags,
        'pairs': pairs,
        'movers': movers,
        'requirements': reqs,
        'countries': countries,
        'cultures': cultures,
        'religions': religions,
    }, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    kb = out.stat().st_size // 1024
    eff = sum(len(m['effects']) for m in movers)
    print(f'  public/values.json: {len(pairs)} axes, {len(movers)} movers, '
          f'{eff} effects, {len(reqs)} things gated on a value, {kb}KB')
    if unresolved_sides:
        print(f'  ⚠ {len(unresolved_sides)} monthly_towards_* side(s) matched no axis: '
              f'{sorted(unresolved_sides)[:6]}')


if __name__ == '__main__':
    main()
