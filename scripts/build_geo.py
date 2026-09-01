"""The map hierarchy as script keys → public/geo.json.

Two consumers, both client-side and both lazy:
  * the advance planner's capital control needs every AREA with its
    region / sub-continent / continent (advance gates test all four tiers
    of the capital's geography), and
  * the save importer needs LOCATION → area, because a save records the
    capital as a location id (an index into its own ordered location list).

    {"areas": {key: [name, region]}, "regions": {key: [name, sub_continent]},
     "subs": {key: [name, continent]}, "conts": {key: name},
     "locations": {key: area}}
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref


def main():
    p = ref.parser
    areas, regions, subs, conts, locs = {}, {}, {}, {}, {}
    for name, a in p.areas.items():
        region = getattr(a, 'region', None)
        areas[name] = [a.display_name, region.name if region else None]
        if region and region.name not in regions:
            sub = getattr(region, 'sub_continent', None)
            regions[region.name] = [region.display_name, sub.name if sub else None]
            if sub and sub.name not in subs:
                cont = getattr(sub, 'continent', None)
                subs[sub.name] = [sub.display_name, cont.name if cont else None]
                if cont and cont.name not in conts:
                    conts[cont.name] = cont.display_name
    for loc, prov in p._prov_for_loc.items():
        area = getattr(prov, 'area', None)
        if area is not None:
            locs[loc] = area.name
    out = ref.ROOT / 'public' / 'geo.json'
    out.write_text(json.dumps({'areas': areas, 'regions': regions, 'subs': subs,
                               'conts': conts, 'locations': locs},
                              sort_keys=True, ensure_ascii=False,
                              separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'  public/geo.json: {len(areas)} areas, {len(regions)} regions, '
          f'{len(subs)} sub-continents, {len(conts)} continents, '
          f'{len(locs)} locations, {out.stat().st_size // 1024}KB')


if __name__ == '__main__':
    main()
