"""map images + a 1337 start save → data/location-map-facts.json.

Two per-location facts the capacity model needs that no game file states:

RIVER TIER. The static modifiers `river_flowing_through_1..5` are what the
location panel shows ("Brook", "River", "Major River"), but nothing in the
files says which river is which size, and the map image does not encode it:
rivers.png uses only palette indices 4, 5, 11 and 15, and they do not order
the tiers — the Seine is drawn one colour end to end yet Paris is size 6
while Corbeil, Melun, Mantes and Rouen are size 2, and on the Danube
Vienna/Linz/Buda are size 4 against Passau/Belgrad/Nikopol/Vidin at size 6.

It is recoverable instead from development. `setup/start/14_development.txt`
adds `river = 0.5 × river size`, and every other term in that formula is a
known integer, so against a 1337.4.1 save

    river size = 2 × (save development − formula development without river)

lands each location on an exact size. The four tooltips that pinned the model
all fall out of it: London 1.0 → size 2 → tier 1 (Brook), Wien 2.0 → 4 → 3
(River), Paris and Nikopol 3.0 → 6 → 5 (Major River). Hence tier = size − 1.

Locations the save cannot answer for — it stores development only for owned
ones, which in 1337 leaves most of the Americas, Africa and inland Asia — fall
back to the palette index, which predicts the tier 73–90% of the time. Those
are marked `est` and the site renders them with a "~".

EQUATOR CLOSENESS scales `location_closeness_to_equator_impact` (≤ +10 flat).
`default.map` puts `equator_y = 3340` but in heightmap pixels, and no heightmap
ships in the mirror, so the scale cannot be read off. The ramp here is fitted
to the four tooltip readings; it is linear in map y, reproduces all four to
0.03%, reaches 1.0 within 0.3% of the equator independently located from
Pontianak, and 0 at the map's southern edge.

Run `make rivers` after a patch, or whenever a new start save is dropped in
melts/. The output is committed so `make data` needs neither a save nor the
map images.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import popcap

Image.MAX_IMAGE_PIXELS = None

ROOT = popcap.ROOT
MAP = popcap.MAP
OUT = popcap.MAPFACTS
MELTS = ROOT / 'melts'

# rivers.png water indices, smallest drawn river first. Used only as the
# fallback ranking for locations the save cannot answer for.
WATER = [4, 5, 11, 15]
# palette rank → river tier, the modal solved value for each (see docstring)
RANK_TIER = {1: 1, 2: 1, 3: 3, 4: 5}
DILATE = 3          # a river bordering a location still flows through it

# Population-capacity tooltips read in game (1.3.11). equator value as shown,
# river tier as named on the river modifier tooltip.
CHECKS = {
    'london': (880, 1),
    'paris': (1419, 5),
    'vienna': (1544, 3),
    'nikopol': (2455, 5),
}


def location_ids() -> tuple[list[str], np.ndarray]:
    """Location keys sorted by packed colour, plus the id image."""
    colours = {}
    for f in sorted((MAP / 'named_locations').glob('*.txt')):
        for k, v in re.findall(r'^\s*([a-z0-9_]+)\s*=\s*([0-9a-fA-F]{1,6})\s*(?:#.*)?$',
                               f.read_text(encoding='utf-8-sig', errors='replace'), re.M):
            colours[k] = int(v, 16)
    img = np.asarray(Image.open(MAP / 'locations.png').convert('RGB'))
    packed = ((img[:, :, 0].astype(np.int32) << 16)
              | (img[:, :, 1].astype(np.int32) << 8) | img[:, :, 2].astype(np.int32))
    del img
    keys = sorted(colours, key=lambda k: colours[k])
    vals = np.array([colours[k] for k in keys], dtype=np.int32)
    pos = np.searchsorted(vals, packed)
    pos[pos >= len(vals)] = 0
    ids = np.where(vals[pos] == packed, pos, -1).astype(np.int32)
    print(f'  {len(keys)} named colours')
    return keys, ids


def river_rank_and_y(keys, ids) -> tuple[dict[str, int], dict[str, float]]:
    """location → biggest nearby river palette rank, and centroid y."""
    riv = np.asarray(Image.open(MAP / 'rivers.png'))
    lut = np.zeros(256, np.uint8)
    for rank, idx in enumerate(WATER, start=1):
        lut[idx] = rank
    r = lut[riv]
    del riv
    for _ in range(DILATE):
        m = r.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx:
                    np.maximum(m, np.roll(np.roll(r, dy, 0), dx, 1), out=m)
        r = m

    h, w = ids.shape
    flat = ids.ravel()
    ok = flat >= 0
    n = len(keys)
    best = np.zeros(n, np.uint8)
    np.maximum.at(best, flat[ok], r.ravel()[ok])
    area = np.bincount(flat[ok], minlength=n)
    ysum = np.bincount(flat[ok], weights=np.repeat(np.arange(h, dtype=np.int64), w)[ok],
                       minlength=n)
    rank = {keys[i]: int(best[i]) for i in range(n) if best[i]}
    cy = {keys[i]: float(ysum[i] / area[i]) for i in range(n) if area[i]}
    print(f'  {len(rank)} locations with a river within {DILATE}px')
    return rank, cy


def fit_equator(cy: dict[str, float]) -> tuple[float, float]:
    """Fit `closeness = 1 − |y − equator| / span` to the four tooltip readings.

    All four sit north of the equator, so the fit is a straight line there; the
    ramp is mirrored south of it, which is what makes this a distance and not
    the raw line (southern locations would otherwise run past 1.0)."""
    ys = np.array([cy[k] for k in CHECKS])
    vs = np.array([CHECKS[k][0] for k in CHECKS]) / 10000.0
    slope, intercept = np.polyfit(ys, vs, 1)
    equator, span = float((1 - intercept) / slope), float(1 / slope)
    print(f'  equator ramp: closeness 1.0 at y={equator:.0f}, 0 at {span:.0f}px either side '
          f'(map is 8192px tall, so 0 from y={equator - span:.0f} north)')
    return equator, span


def save_development() -> dict[str, float]:
    """Per-location development from the newest melted start save, if there is one."""
    saves = sorted(MELTS.glob('*_melted.eu5')) if MELTS.exists() else []
    starts = [s for s in saves if '1337' in s.name]
    if not starts:
        print('  no 1337 melted save in melts/ — every river tier will be estimated')
        return {}
    src = starts[-1]
    names, in_locs, cur, dev = None, False, None, {}
    with open(src, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if names is None:
                if line.startswith('\t\t\t') and 'stockholm norrtalje' in line:
                    names = line.split()
                continue
            if not in_locs:
                if line.rstrip('\n') == 'locations={':
                    in_locs = True
                continue
            m = re.match(r'\t\t(\d+)=\{\s*$', line)
            if m:
                cur = int(m.group(1)); continue
            if line.startswith('\t\t\tdevelopment='):
                dev[cur] = float(line.split('=', 1)[1])
            elif line[0] == '}':
                break
    out = {n: dev[i] for i, n in enumerate(names, 1) if i in dev}
    print(f'  {src.name}: development for {len(out)} locations')
    return out


def main() -> None:
    print('map images…')
    keys, ids = location_ids()
    rank, cy = river_rank_and_y(keys, ids)
    equator, span = fit_equator(cy)

    print('development…')
    dev = save_development()
    m = popcap.Model.__new__(popcap.Model)      # formula pieces only, no map facts yet
    m.tmpl, m.hier = popcap.templates(), popcap.hierarchy()
    m.rank, m.tsetup = popcap.ranks()
    m.W = popcap.dev_weights()
    m.facts = {}

    solved = est = none = 0
    out: dict[str, dict] = {}
    for loc in keys:
        t = m.tmpl.get(loc)
        if not t or 'vegetation' not in t:
            continue
        rec: dict = {}
        closeness = max(0.0, 1.0 - abs(cy.get(loc, equator) - equator) / span)
        if closeness:
            rec['eq'] = round(closeness, 4)
        d = dev.get(loc)
        tier, cap_size = 0, 8
        if d is not None:
            raw = m.development_raw(loc)        # facts empty ⇒ no river term
            residual = d - raw
            size = round(residual * 2)
            if d > 1.0 and 0 <= size <= 8 and abs(residual * 2 - size) < 0.01:
                tier = min(5, size - 1) if size else 0
                solved += 1 if tier else 0
                none += 0 if tier else 1
                d = True                        # solved
            else:
                # Development is floored at 1, so a location sitting on the
                # floor hides its residual — but the floor still bounds it:
                # anything bigger would have lifted development above 1.
                cap_size = max(0, int(2 * (1.0 - raw)))
                d = None
        if d is None:
            r = rank.get(loc)
            size = min(RANK_TIER[r] + 1, cap_size) if r else 0
            tier = max(0, size - 1)
            if tier:
                rec['est'] = 1
                est += 1
            else:
                none += 1
        if tier:
            rec['riv'] = tier
        if rec:
            out[loc] = rec

    payload = {
        'source': 'map_data/locations.png + rivers.png; river tier solved from a '
                  '1337.4.1 start save via the development residual',
        'equator': {'y': equator, 'span': span, 'checks': CHECKS},
        'counts': {'solved': solved, 'estimated': est, 'no_river_or_flat': none},
        'locations': out,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'  river tier: {solved} solved, {est} estimated, {none} none/flat')

    bad = 0
    for loc, (eqv, tier) in CHECKS.items():
        got_eq = round((out.get(loc, {}).get('eq', 0.0)) * 10000)
        got_tier = out.get(loc, {}).get('riv', 0)
        ok = abs(got_eq - eqv) <= 5 and got_tier == tier
        bad += not ok
        print(f'  check {loc:8s} equator {got_eq:5d} (game {eqv:5d})  '
              f'river tier {got_tier} (game {tier})  {"ok" if ok else "MISMATCH"}')
    print(f'  {len(CHECKS) - bad}/{len(CHECKS)} tooltip checks pass')
    kb = OUT.stat().st_size // 1024
    print(f'  {OUT.relative_to(ROOT)}: {len(out)} locations, {kb}KB')


if __name__ == '__main__':
    main()
