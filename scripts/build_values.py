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


def ages() -> list[dict]:
    """The six ages with the year each begins — age 1 uses `year = 1`, i.e.
    the campaign start. Gives the path planner a real timeline to schedule
    against, since a lot of laws and reforms are gated to one age."""
    out = []
    path = ref.ROOT / 'game' / 'in_game' / 'common' / 'age' / '00_default.txt'
    if not path.exists():
        return out
    txt = path.read_text(encoding='utf-8-sig', errors='replace')
    for m in re.finditer(r'^(age_\d+_[a-z_]+)\s*=\s*\{(.*?)^\}', txt, re.M | re.S):
        y = re.search(r'^\s*year\s*=\s*(\d+)', m.group(2), re.M)
        year = int(y.group(1)) if y else 0
        out.append({'key': m.group(1),
                    'name': ref.plain_text(ref.parser.localize(m.group(1), default='')) or ref.pretty(m.group(1)),
                    'year': 1337 if year <= 1 else year})
    out.sort(key=lambda a: a['year'])
    return out


def unlocked_by(age_years: dict[str, int]) -> dict[str, dict]:
    """entity id → the earliest advance that unlocks it.

    A lot of what moves a societal value is not gated by its own trigger at
    all — it simply does not exist until an advance grants it. `Mass Levy
    System` and `A Large Standing Army` read as available in 1337 otherwise,
    which is how the planner ended up claiming you can swing Quantity in the
    first decade. Advances carry their age, so this is the real tech clock.
    """
    out: dict[str, dict] = {}
    src = ref.ROOT / 'src' / 'data' / 'advances.json'
    if not src.exists():
        return out
    for e in json.loads(src.read_text())['entities']:
        age = e.get('facets', {}).get('age')
        year = age_years.get(age)
        if not year:
            continue
        # the advance's own potential gate travels with the grant — Jaysh
        # Armies reads as available-to-anyone otherwise, when only Morocco's
        # advance hands it out. Several advances can grant the same thing
        # (one country's early, everyone's late), so each id keeps the full
        # list and the frontend evaluates them per country.
        gate = e['data'].get('gate')
        who = ', '.join(e['data'].get('gate_labels') or []) or None
        for grp in (e['data'].get('unlocks') or []):
            for it in (grp.get('items') or []):
                key = it.get('id')
                if not key:
                    continue
                rec = {'year': year, 'age': age, 'advance': e['name'],
                       'id': e['id']}
                if gate:
                    rec['gate'] = gate
                    if who:
                        rec['who'] = who
                out.setdefault(key, []).append(rec)
    for grants in out.values():
        grants.sort(key=lambda g: (g['year'], 'gate' in g))
    return out


def value_pairs(cgroups=None) -> dict[str, dict]:
    """The 17 axes. The id names both ends: left_vs_right.

    Axes are themselves gated: mercantilism/outward/absolutism carry an `age`,
    and the special axes (sinicized, mysticism, latinization) an `allow`
    trigger. Emitted so the planners never schedule an axis before it exists.
    """
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
        age = gate = None
        if hasattr(block, 'get'):
            av = block.get('age')
            if isinstance(av, str):
                age = av
            allow = block.get('allow')
            if allow is not None and hasattr(allow, 'iterate_with_duplicates'):
                gate = triggers.compile_trigger(allow, cgroups or {})
        pairs[key] = {
            'id': key,
            'left': {'key': left, 'name': ref.plain_text(ref.parser.localize(left, default='')) or ref.pretty(left)},
            'right': {'key': right, 'name': ref.plain_text(ref.parser.localize(right, default='')) or ref.pretty(right)},
            'left_mods': ref.mods_from_tree(block.get('left_modifier')) if hasattr(block, 'get') else [],
            'right_mods': ref.mods_from_tree(block.get('right_modifier')) if hasattr(block, 'get') else [],
            'age': age,
            'gate': gate,
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


def _bare_tokens(node) -> list[str]:
    """A `{ sunni ibadi shia }` list, whatever shape the parser hands back."""
    if node is None:
        return []
    if isinstance(node, str):
        return node.split()
    if isinstance(node, (list, tuple)):
        return [str(x) for x in node]
    if hasattr(node, 'iterate_with_duplicates'):
        out = []
        for k, v in node.iterate_with_duplicates():
            out.append(str(k))
            if isinstance(v, str) and v:
                out.append(v)
        return out
    return []


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


# A reform's `societal_values = { X_focus }` block is a first-class engine
# requirement: the value must sit at least SOCIAL_VALUE_REQUIREMENT_FOR_REFORM
# (a define, 50) toward that pole — and the engine REMOVES the reform when it
# no longer holds (loc: CHANGE_SOCIETAL_VALUE_AFFECTS_REFORM "... will be lost
# as it requires at least $VAL$ towards $NAME$", REMOVE_GOV_REFORM_SOCIETAL_
# VALUES_MIN/MAX). So unlike an `allow`-block comparison this is a position
# you must HOLD, not a one-off gate.
_FOCUS = re.compile(r'societal_values\s*=\s*\{([^}]*)\}')


def focus_threshold() -> float:
    path = (ref.ROOT / 'game' / 'loading_screen' / 'common' / 'defines'
            / '00_defines.txt')
    if path.exists():
        m = re.search(r'^\s*SOCIAL_VALUE_REQUIREMENT_FOR_REFORM\s*=\s*([0-9.]+)',
                      path.read_text(encoding='utf-8-sig', errors='replace'), re.M)
        if m:
            return float(m.group(1))
    return 50.0


def _focus_reqs(body: str, side_to_pair: dict, threshold: float) -> list[dict]:
    out = []
    for m in _FOCUS.finditer(body):
        for tok in m.group(1).split():
            if not tok.endswith('_focus'):
                continue
            hit = side_to_pair.get(tok[:-len('_focus')])
            if not hit:
                continue
            pid, direction = hit
            out.append({'pair': pid,
                        'op': '>=' if direction == 'right' else '<=',
                        'value': threshold if direction == 'right' else -threshold,
                        'block': 'societal_values', 'hold': True})
    return out


def requirements(side_to_pair: dict, threshold: float) -> list[dict]:
    """Everything that demands a societal value position, with its axis,
    comparison and threshold. Reform focus blocks are flagged `hold` — the
    engine keeps checking them and removes the reform when unmet."""
    out = []
    for folder, (label, etype) in SOURCES.items():
        d = ref.ROOT / 'game' / 'in_game' / 'common' / folder
        if not d.is_dir():
            continue
        focus_folder = folder == 'government_reforms'
        for f in sorted(d.glob('*.txt')):
            txt = _uncomment(f.read_text(encoding='utf-8-sig', errors='replace'))
            if 'societal_value:' not in txt and not (focus_folder and 'societal_values' in txt):
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
                if focus_folder:
                    for r in _focus_reqs(body, side_to_pair, threshold):
                        sig = (r['pair'], r['op'], r['value'])
                        if sig not in seen_req:
                            seen_req.add(sig)
                            reqs.append(r)
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
    age_list = ages()
    unlocks = unlocked_by({a['name']: a['year'] for a in age_list})
    labels = ref.label_map()
    cgroups = ref.culture_group_keys()
    pairs = value_pairs(cgroups)
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
                    # composite ids like "law:x" label by their bare key
                    bare_v = v.split(':')[-1]
                    lab = (labels.get(v) or labels.get(bare_v)
                           or ref.plain_text(ref.parser.localize(bare_v, default=''))
                           or ref.pretty(bare_v))
                    if lab not in seen_l:
                        seen_l.add(lab)
                        gate_labels.append([lab, kind, v])
            # A law group declares who it belongs to outside any trigger:
            # `law_gov_group = monarchy` (governments), `law_religion_group =
            # { sunni ibadi … }` (religions) and `law_country_group = ENG`
            # (tags). Fold them all in, or a Catholic monarchy gets offered
            # iqta law and England's unique acts.
            if group:
                grp = tree[group] if group in tree else None
                buckets: dict[str, list] = {'gov': [], 'rel': [], 'tag': []}
                if grp is not None and hasattr(grp, 'iterate_with_duplicates'):
                    for gk, gv in grp.iterate_with_duplicates():
                        gk = str(gk)
                        if gk == 'law_gov_group' and isinstance(gv, str):
                            buckets['gov'].append(['gov', gv])
                        elif gk == 'law_country_group' and isinstance(gv, str):
                            buckets['tag'].append(['tag', gv])
                        elif gk == 'law_religion_group':
                            for rk in _bare_tokens(gv):
                                buckets['rel'].append(['rel', rk])
                for kind_clauses in buckets.values():
                    if not kind_clauses:
                        continue
                    clause = (kind_clauses[0] if len(kind_clauses) == 1
                              else ['or'] + kind_clauses)
                    gate = ['and', gate, clause] if gate else clause
                    gate_labels = (gate_labels or []) + [
                        [labels.get(c[1]) or ref.pretty(c[1]), c[0], c[1]]
                        for c in kind_clauses]

            # A reform's own metadata: `government = republic` and `age =
            # age_2_renaissance` gate it exactly like a law group's gov line,
            # `major = yes` means one-major-per-country, and years/months is
            # how long implementation takes (modifiers scale up over it).
            major = None
            impl_months = None
            if folder == 'government_reforms' and hasattr(block, 'get'):
                gv = block.get('government')
                if isinstance(gv, str):
                    clause = ['gov', gv.split(':')[-1]]
                    gate = ['and', gate, clause] if gate else clause
                    gate_labels = (gate_labels or []) + [
                        [ref.pretty(clause[1]), 'gov', clause[1]]]
                av = block.get('age')
                if isinstance(av, str):
                    clause = ['age>=', av]
                    gate = ['and', gate, clause] if gate else clause
                mv = block.get('major')
                if mv is True or (isinstance(mv, str) and mv.strip() == 'yes'):
                    major = True
                months = 0
                for unit, mul in (('years', 12), ('months', 1)):
                    uv = block.get(unit)
                    if isinstance(uv, (int, float)):
                        months += int(uv) * mul
                if months:
                    impl_months = months

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
                'unlock': unlocks.get(eid(etype, group or str(key))) if etype else None,
                # every cabinet action occupies a cabinet member while it runs
                'cabinet': folder == 'cabinet_actions' or None,
                'major': major,
                'implMonths': impl_months,
            })

    # The generic "Encourage Societal Value" cabinet action
    # (cabinet_actions/change_societal_values.txt): one static modifier per
    # pole at monthly_towards_X = 1, "scaled with cabinet efficiency"
    # (main_menu/common/static_modifiers/societal_values.txt). The frontend
    # multiplies by a cabinet-efficiency input; base 1.0 is emitted here.
    for pid, p in pairs.items():
        for dirn in ('left', 'right'):
            side = p[dirn]['key']
            movers.append({
                'key': f'encourage_{side}',
                'name': f"Encourage {p[dirn]['name']}",
                'group': None, 'groupName': None,
                'source': 'Cabinet action', 'folder': 'cabinet_actions',
                'id': None, 'slug': f'encourage-{slugify(side)}',
                'effects': [{'pair': pid, 'dir': dirn, 'perMonth': 1.0,
                             'raw': 'cabinet efficiency'}],
                'gate': None, 'gateLabels': [], 'estate': None, 'unlock': None,
                'cabinet': True, 'encourage': True,
            })

    # the same key can appear in more than one file of a folder
    seen, deduped = set(), []
    for m in movers:
        sig = (m['folder'], m.get('group'), m['key'])
        if sig in seen:
            continue
        seen.add(sig)
        for k in ('major', 'implMonths', 'cabinet'):
            if m.get(k) is None:
                m.pop(k, None)
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

    threshold = focus_threshold()
    reqs = requirements(side_to_pair, threshold)

    # Attach hold requirements to the reform movers themselves, so the
    # planner can price "keeping this reform" while it plans the swaps.
    hold_by_key = {r['key']: [q for q in r['requires'] if q.get('hold')]
                   for r in reqs if r['folder'] == 'government_reforms'}
    for m in movers:
        if m['folder'] == 'government_reforms' and hold_by_key.get(m['key']):
            m['holds'] = hold_by_key[m['key']]

    # Unlock grants for gate literals: ["unl", "law:x"] resolves through the
    # same advance join movers use. Ids granted by no advance stay absent —
    # event- or mission-granted, honestly unknown.
    unl_ids = set()

    def _collect_unl(e):
        if not isinstance(e, list) or not e:
            return
        if e[0] == 'unl':
            unl_ids.add(e[1])
        for s in e[1:]:
            if isinstance(s, list):
                _collect_unl(s)
    for m in movers:
        _collect_unl(m.get('gate'))
    unlock_grants = {i: unlocks[i] for i in sorted(unl_ids) if i in unlocks}

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
        'inertia': 100,         # SOCIETAL_VALUE_INERTIA_SCALE — a value
                                # stalls at inertia × net monthly push
        'focusThreshold': threshold,   # SOCIAL_VALUE_REQUIREMENT_FOR_REFORM
        'magnitudes': mags,
        'pairs': pairs,
        'movers': movers,
        'requirements': reqs,
        'unlockGrants': unlock_grants,
        'ages': age_list,
        'countries': countries,
        'cultures': cultures,
        'religions': religions,
    }, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    kb = out.stat().st_size // 1024
    eff = sum(len(m['effects']) for m in movers)
    holds = sum(1 for m in movers if m.get('holds'))
    focus = sum(1 for r in reqs if any(q.get('hold') for q in r['requires']))
    unknown = sum(1 for m in movers if m.get('gate') and triggers.is_dynamic(m['gate']))
    print(f'  public/values.json: {len(pairs)} axes, {len(movers)} movers, '
          f'{eff} effects, {len(reqs)} things gated on a value '
          f'({focus} hold-required reforms, {holds} of them movers), '
          f'{len(unlock_grants)} gate unlock joins, '
          f'{unknown} movers with an unknowable gate, {kb}KB')
    if unresolved_sides:
        print(f'  ⚠ {len(unresolved_sides)} monthly_towards_* side(s) matched no axis: '
              f'{sorted(unresolved_sides)[:6]}')


if __name__ == '__main__':
    main()
