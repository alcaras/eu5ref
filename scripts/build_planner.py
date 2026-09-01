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

KEYS per node: n name · s slug · a age index · b branch id · bo tree order
within the age · d tier · r requires · p the node it is drawn under when
that is NOT a prerequisite (the game's layout slot for an orphan advance) ·
g compiled gate · gl gate labels · i icon · k unlock category
(0 none / 1 build+mil / 2 diplo) · m modifier lines · u unlock lines
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
        mods = [f"{m['value']} {m['label']}" for m in e['mods'][:5]]
        if mods:
            rec['m'] = mods
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
        gov = (starts.get(c['data']['tag']) or {}).get('type')
        if gov:
            f['gov'] = gov
        clist.append({'t': c['data']['tag'], 'n': c['name'], 'col': c.get('color'),
                      'cu': c['facets']['culture'], 're': c['facets']['religion'],
                      'f': f})
    clist.sort(key=lambda c: c['n'])

    # Culture and religion are not fixed for a run — you can culture-shift or
    # convert — so the planner lets you swap them after picking a country.
    # These lists carry the script keys the gates actually test.
    cultures_ds = json.loads((DATA / 'cultures.json').read_text())['entities']
    religions_ds = json.loads((DATA / 'religions.json').read_text())['entities']
    cultures = [{'k': c['id'].split(':', 1)[1], 'n': c['name'],
                 'g': c['data'].get('group_keys') or [],
                 'l': c['data'].get('language_key')}
                for c in cultures_ds]
    religions = [{'k': r['id'].split(':', 1)[1], 'n': r['name'],
                  'g': r['data'].get('group_key')}
                 for r in religions_ds]

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

    payload = {
        'formables': formable_gates,
        'version': patch['version'], 'vhash': vhash, 'order': order,
        'ages': [{'n': a, 'i': age_icon.get(a)} for a in ages],
        'nodes': nodes, 'countries': clist,
        'cultures': cultures, 'religions': religions,
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
