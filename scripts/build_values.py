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


# A law is a *group* of mutually exclusive options — you run one policy per
# group, not the group itself — so each option becomes its own mover. Anything
# in this set is the group's own metadata rather than a selectable policy.
LAW_META = {
    'law_category', 'law_gov_group', 'law_religion_group', 'law_country_group',
    'potential', 'allow', 'locked', 'trigger', 'type', 'requires_vote',
    'custom_tags', 'unique', 'has_levels', 'ai_will_do', 'icon',
}


def entries(folder: str, tree):
    """(key, block, group_key, group_name) for each selectable thing."""
    for key, block in tree:
        if not hasattr(block, 'iterate_with_duplicates'):
            continue
        if folder != 'laws':
            yield str(key), block, None, None
            continue
        gname = (ref.plain_text(ref.parser.localize(str(key), default='')) or
                 ref.pretty(str(key)))
        for k, v in block.iterate_with_duplicates():
            if str(k) not in LAW_META and hasattr(v, 'iterate_with_duplicates'):
                yield str(k), v, str(key), gname


# `monthly_towards_*` only means a real push when it sits in a modifier block.
# The same key also turns up inside `limit`/`add`/`value` blocks, where it is
# an AI weighting term rather than something applied to the country.
_SCALED = {'high_power', 'low_power'}
# Applied only for as long as a transient state lasts, not while you run the
# thing: a parliament debate, or a reform still being implemented.
_TEMPORARY = {'modifier_when_in_debate', 'modifier_while_progressing'}



def _is_modifier(name: str) -> bool:
    return (name == 'modifier' or name.endswith('_modifier')
            or name in _SCALED or name in _TEMPORARY)


def walk(node, found: list, mags: dict, depth=0, parent=''):
    """Collect every monthly_towards_* that a modifier block actually applies.

    Each hit carries how it applies: temporary (a debate, or a reform mid-
    implementation) or scaled (estate power tiers), so the planner can weigh
    a permanent law against a transient push instead of summing them flat.
    """
    if depth > 8 or not hasattr(node, 'iterate_with_duplicates'):
        return
    try:
        pairs = list(node.iterate_with_duplicates())
    except Exception:
        return
    for k, v in pairs:
        k = str(k)
        if k.startswith('monthly_towards_'):
            if not _is_modifier(parent):
                continue
            side = k[len('monthly_towards_'):]
            amount = mags.get(str(v)) if not isinstance(v, (int, float)) else float(v)
            found.append((side, amount, str(v),
                          parent in _TEMPORARY, parent in _SCALED))
        elif hasattr(v, 'iterate_with_duplicates'):
            walk(v, found, mags, depth + 1, k)


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
# A societal-value comparison inside an AI weight is not a requirement at all
# — it is how eagerly the AI picks the thing. Those blocks are skipped, or
# noble parliament issues end up "requiring" a plutocratic country.
_AI_BLOCKS = ('chance', 'ai_will_do', 'ai_chance', 'weight', 'ai_weight',
              'ai_priority', 'priority', 'desirability')
_NEGATIONS = ('NOT', 'NOR', 'NAND')
_FLIP = {'>=': '<', '<=': '>', '>': '<=', '<': '>=', '=': '!='}
# identifier = {   |   {   |   }   |   a societal value comparison
_SCAN = re.compile(
    r'([A-Za-z_][\w]*)\s*=\s*\{|\{|\}|'
    r'societal_value:([a-z_]+)\s*(>=|<=|>|<|=)\s*(-?[0-9.]+)')


def _uncomment(txt: str) -> str:
    return re.sub(r'#[^\n]*', '', txt)


def scan_requirements(body: str):
    """Yield (axis, op, value, block) for real gates in this entity body.

    Tracks the enclosing block names so an AI weight can be told apart from a
    gate, and counts NOT/NOR on the way down so a negated comparison is
    recorded flipped rather than backwards.
    """
    stack: list[str] = []
    for m in _SCAN.finditer(body):
        tok = m.group(0)
        if tok == '}':
            if stack:
                stack.pop()
            continue
        if m.group(1) is not None:
            stack.append(m.group(1))
            continue
        if tok == '{':
            stack.append('')
            continue
        axis, op, num = m.group(2), m.group(3), float(m.group(4))
        gate = None
        for name in reversed(stack):
            if name in _AI_BLOCKS:
                break
            if name in _BLOCKS:
                gate = name
                break
        if not gate:
            continue
        if sum(1 for n in stack if n in _NEGATIONS) % 2:
            op = _FLIP.get(op, op)
        yield axis, op, num, gate


def requirements() -> list[dict]:
    """Everything that demands a societal value position, with its axis,
    comparison and threshold."""
    out = []
    for folder, (label, etype) in SOURCES.items():
        d = ref.ROOT / 'game' / 'in_game' / 'common' / folder
        if not d.is_dir():
            continue
        for f in sorted(d.glob('*.txt')):
            txt = _uncomment(f.read_text(encoding='utf-8-sig', errors='replace'))
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
                key = m.group(1)
                reqs, seen_req = [], set()
                for axis, op, num, block in scan_requirements(body):
                    sig = (axis, op, num)
                    if sig in seen_req:
                        continue
                    seen_req.add(sig)
                    reqs.append({'pair': axis, 'op': op, 'value': num, 'block': block})
                if not reqs:
                    continue
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
        group_gates = {}
        for key, block, group, gname in entries(folder, tree):
            found: list = []
            walk(block, found, mags)
            if not found:
                continue
            name = (ref.plain_text(ref.parser.localize(str(key), default='')) or
                    ref.pretty(str(key)))
            # Who may use it, so the planner can hide what your country
            # cannot take, and which estate a privilege belongs to.
            def _gate_of(src):
                for gk in ('potential', 'allow'):
                    blk = src.get(gk) if hasattr(src, 'get') else None
                    if blk is not None and hasattr(blk, 'iterate_with_duplicates'):
                        expr = triggers.compile_trigger(blk, cgroups)
                        if expr:
                            return expr
                return None

            # A law option is reachable only if BOTH its group and the option
            # itself allow it: the group says which governments run this law
            # at all, the option is often one country's own version of it.
            gate = _gate_of(block)
            if group:
                grp = tree[group] if group in tree else None
                gexpr = _gate_of(grp) if grp is not None else None
                if gexpr:
                    gate = ['and', gexpr, gate] if gate else gexpr
            gate_labels = None
            if gate:
                seen_l, gate_labels = set(), []
                for kind, v in triggers.literals(gate):
                    lab = labels.get(v) or ref.pretty(v)
                    if lab not in seen_l:
                        seen_l.add(lab)
                        gate_labels.append([lab, kind, v])
            # A law group declares the governments it belongs to outside any
            # trigger (`law_gov_group = monarchy`), so fold it in or a
            # monarchy gets offered tribal and republican policies.
            if group:
                grp = tree[group] if group in tree else None
                govs = []
                if grp is not None and hasattr(grp, 'iterate_with_duplicates'):
                    for gk, gv in grp.iterate_with_duplicates():
                        if str(gk) == 'law_gov_group' and isinstance(gv, str):
                            govs.append(['gov', gv])
                if govs:
                    clause = govs[0] if len(govs) == 1 else ['or'] + govs
                    gate = ['and', gate, clause] if gate else clause
                    gate_labels = (gate_labels or []) + [
                        [ref.pretty(g[1]), 'gov', g[1]] for g in govs]

            estate = None
            ev = block.get('estate') if hasattr(block, 'get') else None
            if ev is not None and isinstance(ev, str):
                estate = ref.pretty(ev.split(':')[-1])
            effects = []
            for side, amount, raw, temp, scaled in found:
                hit = side_to_pair.get(side)
                if not hit:
                    unresolved_sides[side] = unresolved_sides.get(side, 0) + 1
                    continue
                pid, direction = hit
                eff = {'pair': pid, 'dir': direction, 'perMonth': amount, 'raw': raw}
                if temp:
                    eff['temp'] = True
                if scaled:
                    eff['scaled'] = True
                effects.append(eff)
            if not effects:
                continue
            movers.append({
                'key': str(key),
                'name': name,
                'group': group,
                'groupName': gname,
                'source': label,
                'folder': folder,
                'id': eid(etype, group or str(key)) if etype else None,
                'slug': slugify(group or str(key)),
                'effects': effects,
                'gate': gate,
                'gateLabels': gate_labels or [],
                'estate': estate,
            })

    # the same key can appear in more than one file of a folder
    seen, deduped = set(), []
    for m in movers:
        sig = (m['folder'], m.get('group'), m['key'])
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
