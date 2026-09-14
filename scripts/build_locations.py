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
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import popcap
import ref
from ref import eid, ename, slugify, write_dataset, facet_meta

# A location can take the Settlement building below 5% of its population
# capacity, and the game removes it again above 10%
# (common/building_types/rural_buildings.txt). The same block lists the
# location ranks it may stand in — `rural_settlement = yes`, `town = no`,
# `city = no` — so a location that starts as a town or bigger can never take
# one, whatever its population says.
SETTLE_BUILD = 5.0
SETTLE_KEEP = 10.0
URBAN_RANKS = ('town', 'city', 'megalopolis')


# Population capacity read in game at the 1337 start, re-checked every build.
# Haverö is the reading that pins the negative half of the equator ramp (see
# scripts/lib/popcap.py); its panel gave the exact number, Sala's only showed
# thousands, so that one is compared against the truncated figure.
CAP_CHECKS = {'havero': (25183, 1), 'sala': (117000, 1000)}


def check_capacity(caps: popcap.Model) -> None:
    ok = 0
    for key, (want, step) in CAP_CHECKS.items():
        got = (caps.capacity(key) or {}).get('cap') or 0.0
        shown = math.floor(got * 1000 / step) * step
        good = abs(shown - want) <= (0 if step > 1 else 50)
        ok += good
        print(f'  check {key:8} capacity {shown:>9,} (game {want:,})'
              f"  {'ok' if good else 'MISMATCH'}")
    print(f'  {ok}/{len(CAP_CHECKS)} capacity checks pass')


def settlement_state(pct: float | None, rank: str | None) -> str | None:
    if pct is None:
        return None
    if rank in URBAN_RANKS:
        return 'urban'
    if pct < SETTLE_BUILD:
        return 'buildable'
    return 'kept' if pct < SETTLE_KEEP else 'removed'


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
    caps = popcap.Model()
    check_capacity(caps)
    # Who holds each location at 1337, so the table can answer "which of *my*
    # locations is about to outgrow a Settlement".
    tag_name = {t: getattr(c, 'display_name', t) for t, c in p.countries.items()}

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
                # Wastelands are impassable and unownable — they carry terrain
                # but nothing can ever be built in one, so no capacity row.
                tag = caps.owner.get(lkey)
                row['owner'] = tag
                row['owner_name'] = tag_name.get(tag) if tag else None
                cap = None if (row['sea'] or row['wasteland']) else caps.capacity(lkey)
                if cap:
                    row.update({
                        'dev': cap['dev'],
                        'cap': cap['cap'],
                        'cap_pct': cap['pct'],
                        'cap_estimated': cap['estimated'],
                        'cap_terms': cap['terms'],
                        'settlement': settlement_state(cap['pct'], s.get('rank')),
                    })
                rows.append(row)
                if not row['sea']:
                    index.append([row['name'], aslug, row['good'] or '', row['culture'] or '',
                                  row['religion'] or '', a.display_name,
                                  row['rank'] or '', row['pop_total'] or 0,
                                  row['slug'] if row['rank'] else '',
                                  row.get('cap') or 0, row.get('cap_pct'),
                                  row.get('settlement') or '',
                                  1 if row.get('cap_estimated') else 0,
                                  row.get('owner_name') or ''])

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
                'cap_total': round(sum(r.get('cap') or 0 for r in land), 1),
                'settlements': sum(1 for r in land if r.get('settlement') == 'buildable'),
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
                                        'areaName', 'rank', 'pops', 'slug',
                                        'cap', 'capPct', 'settlement', 'capEst', 'owner'],
                               'rows': index}, ensure_ascii=False,
                              separators=(',', ':')) + '\n', encoding='utf-8')
    kb = out.stat().st_size // 1024
    print(f'  public/locations.json: {len(index)} land locations, {kb}KB')
    known = [r for r in index if r[10] is not None]
    est = sum(r[12] for r in known)
    build = sum(1 for r in known if r[11] == 'buildable')
    print(f'  population capacity: {len(known)} locations ({est} with an estimated river), '
          f'{build} rural and under {SETTLE_BUILD:g}% — a Settlement can go up')


if __name__ == '__main__':
    main()
