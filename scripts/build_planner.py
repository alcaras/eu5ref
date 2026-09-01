"""Tech-planner payload → public/planner.json.

Reads src/data/advances.json + countries.json (no parser run). The planner
reproduces the game's own advances screen: age tabs, each age a set of
top-down branch trees, nodes coloured by what they unlock, and gated
advances badged — so the payload carries structure, not just a flat list.

  version/vhash  patch + 4-char content hash (share-URL versioning)
  order          stable id list — URLs store base36 indices into this
  ages           age names in play order, with their icons
  nodes          id → compact node record (see KEYS below)
  countries      [{t tag, n name, col, cu culture, re religion, f facts}]
  kinds          the fact vocabulary the gates test, one entry per kind —
                 {k key, l label, mode one|set, values [{v, l, n, f?}]}
                 — `n` is how many advances test the value, `f` the bundle
                 of atomic facts picking it implies (a culture sets cul +
                 cgrp + lang; an area sets every capital tier). The planner
                 builds its "your country" panel from this table alone.
  modkeys        modifier key → label, for the modifier filter

KEYS per node: n name · s slug · a age index · b branch id · bo tree order
within the age · o slot among its siblings (left to right, as drawn) · d
tier · r requires · p the node it is drawn under when the files declare no
prerequisite (the game's layout slot for an orphan advance — an effective
prerequisite in game) ·
g compiled gate · gl gate labels · i icon · k unlock category
(0 none / 1 build+mil / 2 diplo) · m modifiers [[key, value, polarity]] ·
u unlock lines
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'src' / 'data'

# Play order comes from ages.json, whose entities are keyed age_1_… ⇒ already
# in order. Never sort age names alphabetically — that puts Absolutism first.

# The game tints an advance's node by what it unlocks
# (advances_lateralview.gui `template background_advance`):
#   green  — unlocks nothing
#   blue   — buildings / units / laws / policies / reforms / abilities /
#            heir selection / chivalric orders
#   red    — diplomatic things: casus belli, interactions, subject types,
#            country interactions, relations, cabinet actions
CAT_RED = {'Casus belli', 'Diplomacy', 'Subject types', 'Country interactions',
           'Character interactions', 'Cabinet actions'}


def unlock_category(unlocks: list[dict]) -> int:
    if not unlocks:
        return 0
    labels = {u['label'] for u in unlocks}
    return 2 if labels & CAT_RED else 1


def _literals(expr, acc):
    """Every (kind, atom) a compiled gate tests, once per advance."""
    if not isinstance(expr, list) or not expr:
        return
    if expr[0] in ('and', 'or', 'not'):
        for sub in expr[1:]:
            _literals(sub, acc)
    elif expr[0] == 'cap':
        acc.add(('cap', expr[2]))
    elif expr[0] == '?':
        acc.add(('?', expr[1]))
    else:
        acc.add((expr[0], expr[1]))


def build_kinds(advances, nodes, cultures_ds, religions_ds) -> list[dict]:
    """The fact vocabulary, from the gates themselves plus the game's
    catalogues — see scripts/lib/triggers.py KINDS for what each kind means.
    `n` counts advances whose gate tests the value; values nobody tests are
    still offered for the `one` kinds (you can be any culture) but not for
    the `set` kinds (a chip for an untested estate would filter nothing)."""
    import sys
    sys.path.insert(0, str(ROOT / 'scripts' / 'lib'))
    import triggers

    counts: dict[tuple[str, str], int] = {}
    labels: dict[tuple[str, str], str] = {}
    for e in advances:
        d = e['data']
        if not d.get('gate'):
            continue
        acc: set = set()
        _literals(d['gate'], acc)
        for lit in acc:
            counts[lit] = counts.get(lit, 0) + 1
        for lab, kind, v in d.get('gate_lits') or []:
            labels.setdefault((kind, v), lab)

    def n_of(kind, v):
        return counts.get((kind, v), 0)

    geo = json.loads((ROOT / 'public' / 'geo.json').read_text())
    out = []
    # culture → cul + cgrp + lang
    vals = []
    for c in cultures_ds:
        k = c['id'].split(':', 1)[1]
        d = c['data']
        vals.append({'v': k, 'l': c['name'],
                     'n': n_of('cul', k) + sum(n_of('cgrp', g) for g in d.get('group_keys') or [])
                          + n_of('lang', d.get('language_key') or ''),
                     'f': {'cul': k, 'cgrp': d.get('group_keys') or [],
                           'lang': d.get('language_key')}})
    out.append({'k': 'cul', 'l': 'Culture', 'mode': 'one', 'values': vals})
    vals = []
    for r in religions_ds:
        k = r['id'].split(':', 1)[1]
        g = r['data'].get('group_key')
        vals.append({'v': k, 'l': r['name'], 'n': n_of('rel', k) + n_of('rgrp', g or ''),
                     'f': {'rel': k, 'rgrp': g}})
    out.append({'k': 'rel', 'l': 'Religion', 'mode': 'one', 'values': vals})
    # capital → every tier of its area
    vals = []
    for ak, (an, rk) in geo['areas'].items():
        rn, sk = geo['regions'].get(rk, [None, None])
        sn, ck = geo['subs'].get(sk, [None, None]) if sk else (None, None)
        cn = geo['conts'].get(ck) if ck else None
        n = sum(n_of('cap', x) for x in (ak, rk, sk, ck) if x)
        vals.append({'v': ak, 'l': an, 'p': ' · '.join(x for x in (rn, sn, cn) if x), 'n': n,
                     'f': {'cap': {'area': ak, 'region': rk, 'sub_continent': sk, 'continent': ck}}})
    vals.sort(key=lambda v: v['l'])
    out.append({'k': 'cap', 'l': 'Capital', 'mode': 'one', 'values': vals})
    govs = json.loads((DATA / 'government-types.json').read_text())['entities']
    out.append({'k': 'gov', 'l': 'Government', 'mode': 'one',
                'values': [{'v': g['id'].split(':', 1)[1], 'l': g['name'],
                            'n': n_of('gov', g['id'].split(':', 1)[1])} for g in govs]})
    subs = json.loads((DATA / 'subjects.json').read_text())['entities']
    out.append({'k': 'subj', 'l': 'Subject status', 'mode': 'one',
                'values': [{'v': 'none', 'l': 'Independent', 'n': n_of('subj', 'none')}] +
                          [{'v': x['id'].split(':', 1)[1], 'l': x['name'],
                            'n': n_of('subj', x['id'].split(':', 1)[1])} for x in subs]})
    # set kinds: only the values some gate tests
    name_of = {}
    for ds, kind in (('cultures', 'mcg'), ('reforms', 'reform'), ('estates', 'estate'),
                     ('international-organizations', 'iomem'), ('societal-values', 'axis')):
        for e in json.loads((DATA / f'{ds}.json').read_text())['entities']:
            name_of[(kind, e['id'].split(':', 1)[1])] = e['name']
    for kind, label in (('mcg', 'Unified cultures'), ('reform', 'Reforms'),
                        ('estate', 'Estates'), ('iomem', 'Organizations'),
                        ('axis', 'Value axes'), ('dlc', 'DLC'), ('?', 'Other conditions')):
        vals = [{'v': v, 'n': n,
                 'l': name_of.get((kind, v)) or labels.get((kind, v)) or triggers.label_of(kind, v, {})}
                for (k, v), n in counts.items() if k == kind]
        vals.sort(key=lambda x: (-x['n'], x['l']))
        if vals:
            out.append({'k': kind, 'l': label, 'mode': 'set', 'values': vals})
    return out


def main():
    advances = json.loads((DATA / 'advances.json').read_text())['entities']
    countries = json.loads((DATA / 'countries.json').read_text())['entities']
    ages_ds = json.loads((DATA / 'ages.json').read_text())['entities']
    patch = json.loads((ROOT / 'data' / 'patch.json').read_text())

    ids = {e['id'] for e in advances}
    ages_present = {e['facets']['age'] for e in advances}
    ages = [e['name'] for e in ages_ds if e['name'] in ages_present]
    ages += sorted(a for a in ages_present if a not in ages)
    age_ix = {a: i for i, a in enumerate(ages)}
    age_icon = {e['name']: e.get('icon') for e in ages_ds}

    nodes = {}
    modkeys: dict[str, str] = {}
    for e in advances:
        d = e['data']
        unlock_lines = []
        for u in d.get('unlocks', []):
            names = ', '.join(x['label'] for x in u['items'][:6])
            unlock_lines.append(f"{u['label']}: {names}")
        rec = {
            'n': e['name'],
            's': e['slug'],
            'a': age_ix[e['facets']['age']],
            'b': d['branch_id'],
            'bo': d.get('tree_index', 0),
            'o': d.get('tree_slot', 0),
            'd': d['tier'],
            'r': [r['id'] for r in d['requires'] if r['id'] in ids],
            'k': unlock_category(d.get('unlocks')),
        }
        if e.get('icon'):
            rec['i'] = e['icon']
        du = d.get('drawn_under')
        if du and du.get('computed') and du['id'] in ids and du['id'] not in rec['r']:
            rec['p'] = du['id']
        if d.get('gate'):
            rec['g'] = d['gate']
            rec['gl'] = d.get('gate_lits') or [[x, '?', ''] for x in (d.get('gate_labels') or [])]
        mods = [[m['key'], m['value'], m['polarity']] for m in e['mods']]
        if mods:
            rec['m'] = mods
            for m in e['mods']:
                modkeys.setdefault(m['key'], m['label'])
        if unlock_lines:
            rec['u'] = unlock_lines
        if d.get('specialization'):
            rec['sp'] = d['specialization']
        if d.get('requires_state'):
            rec['rs'] = d['requires_state']
        nodes[e['id']] = rec

    order = sorted(nodes)
    vhash = hashlib.sha1(json.dumps(order).encode()).hexdigest()[:4]

    # Government type comes from the 1337 template stack, so a monarchy is
    # not offered advances gated to tribes and republics.
    starts = {}
    sp = ROOT / 'public' / 'country-start.json'
    if sp.exists():
        starts = json.loads(sp.read_text())

    clist = []
    for c in countries:
        f = dict(c['data'].get('facts') or {})
        st = starts.get(c['data']['tag']) or {}
        if st.get('type'):
            f['gov'] = st['type']
        # 1337 subject status, from the setup's dependency lines
        f['subj'] = st.get('subj', 'none')
        if st.get('io'):
            f['iomem'] = st['io']
        clist.append({'t': c['data']['tag'], 'n': c['name'], 'col': c.get('color'),
                      'cu': c['facets']['culture'], 're': c['facets']['religion'],
                      'f': f})
    clist.sort(key=lambda c: c['n'])

    cultures_ds = json.loads((DATA / 'cultures.json').read_text())['entities']
    religions_ds = json.loads((DATA / 'religions.json').read_text())['entities']

    formables = json.loads((DATA / 'formables.json').read_text())['entities']
    # tag → the gate that decides who can form it (null = anyone, given the
    # territory). The planner evaluates it against the chosen country.
    formable_gates: dict[str, list | None] = {}
    for f in formables:
        t = f['data'].get('tag')
        if not t:
            continue
        g = f['data'].get('gate')
        if t not in formable_gates or formable_gates[t] is not None:
            formable_gates[t] = g

    kinds = build_kinds(advances, nodes, cultures_ds, religions_ds)

    payload = {
        'formables': formable_gates,
        'kinds': kinds, 'modkeys': modkeys,
        'version': patch['version'], 'vhash': vhash, 'order': order,
        'ages': [{'n': a, 'i': age_icon.get(a)} for a in ages],
        'nodes': nodes, 'countries': clist,
    }
    out = ROOT / 'public' / 'planner.json'
    out.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                              separators=(',', ':')) + '\n', encoding='utf-8')
    # The same country facts, without the 3,178 advance nodes: every list
    # page with compiled gates (privileges, laws, reforms, urban rights) can
    # lazy-fetch this to answer "what can my country take?".
    facts = ROOT / 'public' / 'country-facts.json'
    lean = [{'t': c['t'], 'n': c['n'], 'f': c['f']} for c in clist]
    facts.write_text(json.dumps({'countries': lean, 'formables': formable_gates},
                                sort_keys=True, ensure_ascii=False,
                                separators=(',', ':')) + '\n', encoding='utf-8')

    kb = out.stat().st_size // 1024
    gated = sum(1 for n in nodes.values() if 'g' in n)
    print(f'  public/planner.json: {len(nodes)} nodes ({gated} gated), '
          f'{len(clist)} countries, {kb}KB')
    print(f'  public/country-facts.json: '
          f'{facts.stat().st_size // 1024}KB')


if __name__ == '__main__':
    main()
