"""map hierarchy + location setup → src/data/areas.json, public/locations.json.

EU5 has 28,573 locations. A page each would be ~200MB of HTML for very
little gain, so the unit of navigation is the **area** (805 of them, ~35
locations each) — small enough to read as one table, big enough to be worth
a page. Every location is still reachable: `public/locations.json` is a
lazy-loaded search index the /locations page filters client-side.

Per location we carry what the setup files actually say: its raw material
(what it produces), terrain/climate, culture and religion, its starting
rank and town setup where it has one, and its starting pops — which is
where the culture and religion makeup comes from, since a location's pops
are often not all its "own" culture.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import eid, ename, slugify, write_dataset, facet_meta


def town_setups() -> dict[str, list[dict]]:
    """town_setup name → the buildings a location of that setup starts with.

    common/town_setups is `setup = { building = count, … }`; the counts are
    building levels, so a town with `marketplace = 2` starts with two."""
    out: dict[str, list[dict]] = {}
    try:
        tree = ref.parser.parser.parse_folder_as_one_file('in_game/common/town_setups')
    except Exception:
        return out
    buildings = ref.parser.buildings
    for key, block in tree:
        if not hasattr(block, 'iterate_with_duplicates'):
            continue
        items = []
        for bk, bv in block.iterate_with_duplicates():
            bk = str(bk)
            b = buildings.get(bk)
            items.append({
                'name': getattr(b, 'display_name', None) or ref.pretty(bk),
                'id': eid('building', bk) if b is not None else None,
                'count': bv if isinstance(bv, (int, float)) else 1,
            })
        items.sort(key=lambda x: (-x['count'], x['name']))
        out[str(key)] = items
    return out


def setup_by_location() -> dict[str, dict]:
    """location key → {rank, town_setup, pops[]} from setup/start."""
    out: dict[str, dict] = {}
    try:
        locs = ref.parser.setup_data['locations']
    except Exception:
        return out
    for key, block in locs.iterate_with_duplicates():
        if not hasattr(block, 'iterate_with_duplicates'):
            continue
        rec = {'rank': None, 'town_setup': None, 'pops': []}
        for k, v in block.iterate_with_duplicates():
            k = str(k)
            if k == 'rank':
                rec['rank'] = str(v)
            elif k == 'town_setup':
                rec['town_setup'] = ref.pretty(str(v))
                rec['town_setup_key'] = str(v)
            elif k == 'define_pop' and hasattr(v, 'iterate_with_duplicates'):
                # A location's several `define_pop` blocks arrive merged into
                # ONE tree whose type/size/culture/religion keys simply repeat
                # in file order — so start a new pop each time `type` comes
                # round again, rather than collapsing them into one.
                pop: dict = {}

                def flush():
                    if pop.get('size'):
                        rec['pops'].append({
                            'type': ref.pretty(str(pop.get('type', ''))),
                            'size': round(float(pop['size']), 3),
                            'culture': ref.pretty(str(pop.get('culture', ''))),
                            'religion': ref.pretty(str(pop.get('religion', ''))),
                        })

                for pk, pv in v.iterate_with_duplicates():
                    pk = str(pk)
                    if pk == 'type' and pop:
                        flush()
                        pop = {}
                    pop[pk] = pv
                flush()
        out[str(key)] = rec
    return out


def makeup(pops: list[dict], field: str) -> list[dict]:
    """Pops grouped by culture (or religion), largest share first."""
    tot = sum(p['size'] for p in pops) or 0
    if not tot:
        return []
    acc: dict[str, float] = {}
    for p in pops:
        acc[p[field]] = acc.get(p[field], 0) + p['size']
    out = [{'name': k, 'pct': round(100 * v / tot, 1)} for k, v in acc.items()]
    out.sort(key=lambda x: -x['pct'])
    return out


def main():
    p = ref.parser
    setup = setup_by_location()
    setups = town_setups()
    areas = p.areas

    entities = []
    index = []          # the searchable location list
    for akey in sorted(areas):
        a = areas[akey]
        aslug = slugify(akey)
        region = getattr(a, 'region', None)
        sub = getattr(region, 'sub_continent', None) if region is not None else None
        cont = getattr(sub, 'continent', None) if sub is not None else None
        rows = []
        for pkey, prov in sorted(getattr(a, 'provinces', {}).items()):
            for lkey, loc in sorted(getattr(prov, 'locations', {}).items()):
                s = setup.get(lkey, {})
                pops = s.get('pops') or []
                good = getattr(loc, 'raw_material', None)
                row = {
                    'key': lkey,
                    'name': loc.display_name,
                    'province': prov.display_name,
                    'good': ename(good),
                    'good_id': eid('good', good.name) if good is not None else None,
                    'culture': ename(getattr(loc, 'culture', None)),
                    'religion': ename(getattr(loc, 'religion', None)),
                    'topography': ename(getattr(loc, 'topography', None)),
                    'vegetation': ename(getattr(loc, 'vegetation', None)),
                    'climate': ename(getattr(loc, 'climate', None)),
                    'harbor': getattr(loc, 'natural_harbor_suitability', None),
                    'rank': ref.pretty(s['rank']) if s.get('rank') else None,
                    'town_setup': s.get('town_setup'),
                    'buildings': setups.get(s.get('town_setup_key') or '', []),
                    'slug': slugify(lkey),
                    'pop_total': round(sum(x['size'] for x in pops), 2) if pops else None,
                    'cultures': makeup(pops, 'culture'),
                    'religions': makeup(pops, 'religion'),
                    'sea': bool(getattr(loc, 'is_sea', False) or getattr(loc, 'is_lake', False)),
                    'wasteland': bool(getattr(loc, 'is_wasteland', False)),
                }
                rows.append(row)
                if not row['sea']:
                    index.append([row['name'], aslug, row['good'] or '', row['culture'] or '',
                                  row['religion'] or '', a.display_name,
                                  row['rank'] or '', row['pop_total'] or 0,
                                  row['slug'] if row['rank'] else ''])

        land = [r for r in rows if not r['sea']]
        entities.append({
            'id': eid('area', akey),
            'type': 'area',
            'slug': aslug,
            'name': a.display_name,
            'facets': {
                'region': ename(region),
                'subcontinent': ename(sub),
                'continent': ename(cont),
            },
            'mods': [],
            'data': {
                'locations': rows,
                'count': len(land),
                'towns': sum(1 for r in land if r['rank']),
                'goods': sorted({r['good'] for r in land if r['good']}),
                'pop_total': round(sum(r['pop_total'] or 0 for r in land), 1),
            },
        })

    write_dataset('areas', {
        'dataset': 'areas',
        'source': 'map_data/definitions + setup/start',
        'entities': entities,
        'facets': facet_meta(entities, [('continent', 'Continent'),
                                        ('subcontinent', 'Subcontinent'),
                                        ('region', 'Region')]),
    })

    out = ref.ROOT / 'public' / 'locations.json'
    out.write_text(json.dumps({'cols': ['name', 'area', 'good', 'culture', 'religion',
                                        'areaName', 'rank', 'pops', 'slug'],
                               'rows': index}, ensure_ascii=False,
                              separators=(',', ':')) + '\n', encoding='utf-8')
    kb = out.stat().st_size // 1024
    print(f'  public/locations.json: {len(index)} land locations, {kb}KB')


if __name__ == '__main__':
    main()
