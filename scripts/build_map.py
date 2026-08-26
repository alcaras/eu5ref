"""map_data/locations.png → public/map/*.png — thematic map modes.

The game ships a 16384×8192 image where every location is one flat colour,
and `named_locations` gives location → colour. That is everything needed to
paint a map mode: look up each pixel's colour, find its location, and repaint
it by whatever attribute we want to show.

Doing that per pixel in Python would be hopeless (134M pixels), so it is done
as an array op: pack RGB into one int32 per pixel, then use a sorted lookup
table (np.searchsorted) to turn 134M colours into 134M palette indices in a
couple of seconds. The output is a paletted PNG — flat colour, so it
compresses to a fraction of the source.

Downscaling uses NEAREST on the *index* image, never on the source colours:
interpolating between two location colours would invent a colour belonging to
a third location.

Outputs, all under public/map/:
  <mode>.png     one per map mode (good, culture, religion, topography…)
  legend.json    palette → label for each mode, plus location lookup data
  index.png      the id map, downscaled, for hover/click lookup
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import slugify

Image.MAX_IMAGE_PIXELS = None          # the source map is 134 megapixels

MAP = ref.ROOT / 'game' / 'in_game' / 'map_data'
OUT = ref.ROOT / 'public' / 'map'
SCALE = 4                              # 16384×8192 → 4096×2048
SEA = (36, 46, 68)                     # unmapped / water
BLANK = (26, 30, 40)                   # a location with no value for this mode

# mode → (label, how to get the value off a location record)
# mode → (label, value getter, dataset whose in-game colours to reuse)
MODES = {
    'good': ('Trade good', lambda l: l.get('good'), 'goods'),
    'culture': ('Culture', lambda l: l.get('culture'), 'cultures'),
    'religion': ('Religion', lambda l: l.get('religion'), 'religions'),
    'topography': ('Topography', lambda l: l.get('topography'), None),
    'climate': ('Climate', lambda l: l.get('climate'), None),
    'vegetation': ('Vegetation', lambda l: l.get('vegetation'), None),
}


def location_colours() -> dict[str, int]:
    """location key → packed RGB int, from map_data/named_locations."""
    out = {}
    for f in sorted((MAP / 'named_locations').glob('*.txt')):
        # NB: no end-of-line anchor — 6,257 of these lines carry a trailing
        # comment ("butt_of_lewis = 1c3857 # hehe") and anchoring drops them.
        for m in re.finditer(r'^\s*([A-Za-z_0-9]+)\s*=\s*([0-9a-fA-F]{1,6})\b',
                             f.read_text(encoding='utf-8-sig', errors='replace'), re.M):
            out[m.group(1)] = int(m.group(2), 16)
    return out


def game_colours(dataset: str) -> dict[str, tuple[int, int, int]]:
    """display name → RGB, using the colour the game itself gives goods,
    cultures and religions. Site rule: in-game colours where they exist."""
    out: dict[str, tuple[int, int, int]] = {}
    path = ref.DATA_DIR / f'{dataset}.json'
    if not path.exists():
        return out
    for e in json.loads(path.read_text())['entities']:
        c = e.get('color')
        if isinstance(c, str) and c.startswith('#') and len(c) == 7:
            out[e['name']] = (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
    return out


def palette_for(values: list[str | None], seed: str,
                given: dict[str, tuple[int, int, int]] | None = None
                ) -> dict[str, tuple[int, int, int]]:
    """A stable colour per distinct value: the game's own where it has one,
    otherwise a hue derived from the name so it stays put between builds."""
    given = given or {}
    out = {}
    for v in sorted({x for x in values if x}):
        if v in given:
            out[v] = given[v]
            continue
        h = 0
        for ch in (seed + v):
            h = (h * 131 + ord(ch)) & 0xFFFFFFFF
        hue = (h % 360) / 360
        sat = 0.45 + ((h >> 9) % 30) / 100
        val = 0.55 + ((h >> 17) % 35) / 100
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
        out[v] = (int(r * 255), int(g * 255), int(b * 255))
    return out


def main():
    areas = json.loads((ref.DATA_DIR / 'areas.json').read_text())['entities']
    by_key: dict[str, dict] = {}
    for a in areas:
        for l in a['data']['locations']:
            l = dict(l)
            l['area'] = a['name']
            l['area_slug'] = a['slug']
            by_key[l['key']] = l

    colours = location_colours()
    print(f'  {len(colours)} named colours, {len(by_key)} locations with data')

    OUT.mkdir(parents=True, exist_ok=True)
    img = Image.open(MAP / 'locations.png').convert('RGB')
    arr = np.asarray(img, dtype=np.uint8)
    packed = (arr[:, :, 0].astype(np.int32) << 16) | \
             (arr[:, :, 1].astype(np.int32) << 8) | arr[:, :, 2].astype(np.int32)
    del arr
    print(f'  source {img.size[0]}×{img.size[1]}')

    # colour → dense location index, via a sorted lookup
    keys = sorted(colours, key=lambda k: colours[k])
    codes = np.array([colours[k] for k in keys], dtype=np.int32)
    pos = np.searchsorted(codes, packed)
    np.clip(pos, 0, len(codes) - 1, out=pos)
    hit = codes[pos] == packed
    idx = np.where(hit, pos, -1).astype(np.int32)
    del packed, pos, hit
    matched = int((idx >= 0).mean() * 100)
    print(f'  {matched}% of pixels resolved to a location')

    small = idx[::SCALE, ::SCALE]      # NEAREST by construction
    h, w = small.shape

    legend = {}
    for mode, (label, get, src) in MODES.items():
        vals = [get(by_key.get(k, {})) for k in keys]
        pal = palette_for(vals, mode, game_colours(src) if src else None)
        # index → RGB row, plus two extras for sea and blank
        lut = np.zeros((len(keys) + 2, 3), dtype=np.uint8)
        lut[len(keys)] = SEA
        lut[len(keys) + 1] = BLANK
        for i, v in enumerate(vals):
            lut[i] = pal.get(v, BLANK) if v else BLANK
        flat = np.where(small < 0, len(keys), small)
        Image.fromarray(lut[flat], 'RGB').save(OUT / f'{mode}.png', optimize=True)
        counts: dict[str, int] = {}
        for k, v in zip(keys, vals):
            if v:
                counts[v] = counts.get(v, 0) + 1
        legend[mode] = {
            'label': label,
            'entries': [{'name': v, 'color': '#%02x%02x%02x' % pal[v], 'count': counts.get(v, 0)}
                        for v in sorted(pal, key=lambda x: -counts.get(x, 0))],
        }
        kb = (OUT / f'{mode}.png').stat().st_size // 1024
        print(f'  {mode}.png: {w}×{h}, {len(pal)} values, {kb}KB')

    # the id map, so the page can say what is under the cursor: the location
    # index encoded as r<<16|g<<8|b in a lossless PNG
    ids = np.where(small < 0, 0xFFFFFF, small).astype(np.int32)
    rgb = np.dstack([(ids >> 16) & 0xFF, (ids >> 8) & 0xFF, ids & 0xFF]).astype(np.uint8)
    Image.fromarray(rgb, 'RGB').save(OUT / 'index.png', optimize=True)
    print(f'  index.png: {(OUT / "index.png").stat().st_size // 1024}KB')

    (OUT / 'legend.json').write_text(json.dumps({
        'width': w, 'height': h, 'scale': SCALE,
        'modes': legend,
        'locations': [[by_key.get(k, {}).get('name') or ref.pretty(k),
                       by_key.get(k, {}).get('area_slug') or '',
                       by_key.get(k, {}).get('good') or '',
                       by_key.get(k, {}).get('culture') or '',
                       by_key.get(k, {}).get('religion') or '']
                      for k in keys],
    }, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'  legend.json: {(OUT / "legend.json").stat().st_size // 1024}KB')


if __name__ == '__main__':
    main()
