"""Tech-planner payload → public/planner.json.

Reads src/data/advances.json + countries.json (no parser run). Emits the
compact graph the /advance-planner page consumes:

  version/vhash   patch + 4-char content hash (share-URL versioning)
  order           stable id list — URLs store base36 indices into this
  ages            age display names in play order
  nodes           id → {n name, s slug, a age, ed effective depth, sc scope,
                        t tree, c [country tags], i icon, r [require ids],
                        m [first modifier strings]}
  countries       [{t tag, n name, col color, cu culture, re religion}]
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'src' / 'data'

AGE_ORDER = ['Age of Traditions', 'Age of Renaissance', 'Age of Discovery',
             'Age of Reformation', 'Age of Absolutism', 'Age of Revolutions']


def main():
    advances = json.loads((DATA / 'advances.json').read_text())['entities']
    countries = json.loads((DATA / 'countries.json').read_text())['entities']
    patch = json.loads((ROOT / 'data' / 'patch.json').read_text())

    ids = {e['id'] for e in advances}
    by_id = {e['id']: e for e in advances}
    requires = {e['id']: [r['id'] for r in e['data']['requires'] if r['id'] in ids]
                for e in advances}

    # effective depth per age: game hint corrected so same-age edges go L→R
    age_of = {e['id']: e['facets']['age'] for e in advances}
    depth: dict[str, int] = {}

    def calc(nid, stack=()):
        if nid in depth:
            return depth[nid]
        if nid in stack:
            return 0
        hint = by_id[nid]['data'].get('depth') or 0
        same_age_parents = [p for p in requires[nid] if age_of[p] == age_of[nid]]
        d = max([calc(p, stack + (nid,)) + 1 for p in same_age_parents] + [hint])
        depth[nid] = d
        return d

    for e in advances:
        calc(e['id'])

    nodes = {}
    for e in advances:
        nodes[e['id']] = {
            'n': e['name'], 's': e['slug'], 'a': e['facets']['age'],
            'ed': depth[e['id']], 'sc': e['facets']['scope'],
            't': e['data'].get('tree'), 'c': e['data']['countries'],
            'i': e.get('icon'), 'r': requires[e['id']],
            'm': [f"{m['value']} {m['label']}" for m in e['mods'][:4]],
        }

    order = sorted(nodes)
    vhash = hashlib.sha1(json.dumps(order).encode()).hexdigest()[:4]

    ages_present = {n['a'] for n in nodes.values()}
    ages = [a for a in AGE_ORDER if a in ages_present] + \
           sorted(a for a in ages_present if a not in AGE_ORDER)

    clist = [{'t': c['data']['tag'], 'n': c['name'], 'col': c.get('color'),
              'cu': c['facets']['culture'], 're': c['facets']['religion']}
             for c in countries]
    clist.sort(key=lambda c: c['n'])

    payload = {'version': patch['version'], 'vhash': vhash, 'order': order,
               'ages': ages, 'nodes': nodes, 'countries': clist}
    out = ROOT / 'public' / 'planner.json'
    out.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False) + '\n',
                   encoding='utf-8')
    kb = out.stat().st_size // 1024
    print(f'  public/planner.json: {len(nodes)} nodes, {len(clist)} countries, {kb}KB')


if __name__ == '__main__':
    main()
