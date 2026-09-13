"""1337 population capacity per location — the game's own modifier stack.

    capacity = (Σ flat terms) × (1 + Σ percent terms)

with file values scaled ×1000 for display (`local_population_capacity = 100`
on farmland is the 100K the game shows). Every term is read out of the game
files; only the rule for *what scales each static modifier* lives here.

    flat     vegetation.local_population_capacity     desert 10 … farmland 100
             location rank                            town 20 / city 100 /
                                                      megalopolis 400
             closeness to equator                     ≤ 10, see EQUATOR below
    percent  climate                                  arctic −33% … med. +150%
             topography                               mountains −50%
             location rank                            10% / 25% / 50%
             development                              ×2.5% per point
             coastal                                  +25% (any harbour value)
             capital +10%, province capital +5%       (capital wins; the game
                                                      never shows both)
             river flowing through                    +10% per tier, 1…5
             staffed building levels                  ×0.1% per level
             town rights that carry one               ville franche +20%
             owner's capital-economy-vs-traditional   ×25% at the pole
             -economy position

Checked against four in-game tooltips, which reconcile to the unit:

    London  (100,000 + 100,000 +   880) × 3.8575 = 774,895 → shown "774K"
    Wien    (100,000 + 100,000 + 1,544) × 3.0468 = 614,064 → shown "614K"

DEVELOPMENT is the game's own start formula, `setup/start/14_development.txt`,
plus two behaviours the file does not state, both settled by a 1337.4.1 save:
the `road = 2` term does **not** apply at start (crediting it turns 6,847
exact matches into 6,247, every miss exactly −2), and the result is floored
at 1.0 (240 locations sit on that floor).

PROVINCE CAPITAL is the first location listed in its province block in
`map_data/definitions.txt` — Wien is first in its block and shows the +5%,
Nikopol is fourth in Tarnovo and shows none. A country capital shows +10%
and never the province line as well.

EQUATOR. `default.map` gives `equator_y = 3340`, but in heightmap pixels, and
no heightmap ships in the mirror, so the pixel scale cannot be read. The
closeness ramp is therefore fitted to the four tooltip readings — it is linear
in map y and reproduces all four to 0.03%, reaching 1.0 within 0.3% of the
equator independently located from Pontianak, and 0 at the map's southern
edge. Stored per location by build_rivers.py, not recomputed here.

RIVER SIZE is not in the map image: the Seine is drawn one colour end to end
yet Paris is size 6 while Corbeil, Melun, Mantes and Rouen are size 2. It is
recovered instead from the 1337 development residual (`0.5 × river_size`) and
committed by build_rivers.py; see that script's docstring.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / 'game'
SETUP = GAME / 'main_menu/setup/start'
MAP = GAME / 'in_game/map_data'
COMMON = GAME / 'in_game/common'
STATIC = GAME / 'main_menu/common/static_modifiers/location.txt'
MAPFACTS = ROOT / 'data' / 'location-map-facts.json'

CAP = 'local_population_capacity'
CAP_PCT = 'local_population_capacity_modifier'


def _read(p: Path) -> str:
    return Path(p).read_text(encoding='utf-8-sig', errors='replace')


def _pretty(key: str) -> str:
    return key.replace('_', ' ').strip().capitalize()


def _uncomment(text: str) -> str:
    return re.sub(r'#.*', '', text)


# ---------------------------------------------------------------- game files

def _brace_body(text: str, open_at: int) -> str:
    """The body of the block whose opening `{` sits at `open_at`."""
    depth, i = 0, open_at
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[open_at + 1:i]
        i += 1
    return text[open_at + 1:]


def _top_level_blocks(text: str) -> dict[str, str]:
    """`name = { … }` at brace depth 0 → name → body."""
    out, depth, name, start = {}, 0, None, 0
    for m in re.finditer(r'[{}]|^([a-z0-9_]+)\s*=\s*\{', text, re.M):
        if m.group(0) in '{}':
            depth += 1 if m.group(0) == '{' else -1
            if depth == 0 and name:
                out[name] = text[start:m.start()]
                name = None
        else:
            if depth == 0:
                name, start = m.group(1), m.end()
            depth += 1
    return out


def _cap_terms(path: Path) -> dict[str, tuple[float, float]]:
    """block name → (flat population capacity, percent), from one file."""
    out = {}
    for name, body in _top_level_blocks(_uncomment(_read(path))).items():
        flat = re.search(rf'\b{CAP}\s*=\s*(-?[\d.]+)', body)
        pct = re.search(rf'\b{CAP_PCT}\s*=\s*(-?[\d.]+)', body)
        if flat or pct:
            out[name] = (float(flat.group(1)) if flat else 0.0,
                         float(pct.group(1)) if pct else 0.0)
    return out


def river_names() -> dict[int, str]:
    """tier → the name the location panel gives it ("Brook Flowing Through")."""
    loc = GAME / 'main_menu/localization/english/static_modifiers_l_english.yml'
    out = {}
    for n, name in re.findall(
            r'STATIC_MODIFIER_NAME_river_flowing_through_(\d):\s*"([^"]*)"',
            _read(loc)):
        out[int(n)] = re.sub(r'\[(\w+)\|[a-z]\]', lambda m: m.group(1), name)
    return out


def statics() -> dict[str, tuple[float, float]]:
    """The location static modifiers that touch population capacity."""
    return _cap_terms(STATIC)


def terrain_terms() -> dict[str, dict[str, tuple[float, float]]]:
    return {
        'vegetation': _cap_terms(COMMON / 'vegetation/00_default.txt'),
        'climate': _cap_terms(COMMON / 'climates/00_default.txt'),
        'topography': _cap_terms(COMMON / 'topography/00_default.txt'),
        'rank': _cap_terms(COMMON / 'location_ranks/00_default.txt'),
    }


def town_right_terms() -> dict[str, float]:
    """town right key → percent capacity it grants."""
    out = {}
    for f in sorted((COMMON / 'town_rights').glob('*.txt')):
        for name, (_, pct) in _cap_terms(f).items():
            if pct:
                out[name] = pct
    return out


def traditional_economy_pct() -> float:
    """The capital-vs-traditional-economy axis' capacity modifier at the pole."""
    body = _top_level_blocks(_uncomment(_read(COMMON / 'societal_values/00_default.txt')))
    axis = body.get('capital_economy_vs_traditional_economy', '')
    rm = re.search(r'right_modifier\s*=\s*\{', axis)
    if not rm:
        return 0.0
    m = re.search(r'\bglobal_population_capacity_modifier\s*=\s*(-?[\d.]+)',
                  _brace_body(axis, rm.end() - 1))
    return float(m.group(1)) if m else 0.0


def templates() -> dict[str, dict[str, str]]:
    """location → {topography, vegetation, climate, natural_harbor_suitability…}"""
    out = {}
    for line in _read(MAP / 'location_templates.txt').splitlines():
        m = re.match(r'\s*([a-z0-9_]+)\s*=\s*\{(.*)\}\s*$', line)
        if m:
            out[m.group(1)] = dict(re.findall(r'([a-z_]+)\s*=\s*([-\w.]+)', m.group(2)))
    return out


def hierarchy() -> dict[str, tuple[str, ...]]:
    """location → (continent, subcontinent, region, area, province)."""
    toks = re.findall(r'[A-Za-z0-9_]+|=|\{|\}', _uncomment(_read(MAP / 'definitions.txt')))
    stack, out, i = [], {}, 0
    while i < len(toks):
        if toks[i] == '}':
            stack.pop(); i += 1; continue
        if i + 2 < len(toks) and toks[i + 1] == '=' and toks[i + 2] == '{':
            stack.append(toks[i]); i += 3; continue
        out[toks[i]] = tuple(stack); i += 1
    return out


def province_capitals() -> set[str]:
    """The first location listed in each province block."""
    out = set()
    for body in re.findall(r'[a-z0-9_]+_province\s*=\s*\{([^{}]*)\}',
                           _uncomment(_read(MAP / 'definitions.txt'))):
        names = body.split()
        if names:
            out.add(names[0])
    return out


def ranks() -> tuple[dict[str, str], dict[str, str]]:
    """location → rank, location → town_setup (comments stripped: some are #off)."""
    rank, setup = {}, {}
    text = _uncomment(_read(SETUP / '07_cities_and_buildings.txt'))
    for m in re.finditer(r'([a-z0-9_]+)\s*=\s*\{([^{}]*)\}', text):
        d = dict(re.findall(r'([a-z_]+)\s*=\s*([\w]+)', m.group(2)))
        if 'rank' in d:
            rank[m.group(1)] = d['rank']
            if 'town_setup' in d:
                setup[m.group(1)] = d['town_setup']
    return rank, setup


def town_setup_levels() -> dict[str, int]:
    """town setup → total building levels it starts with."""
    out: dict[str, int] = {}
    for f in sorted((COMMON / 'town_setups').glob('*.txt')):
        cur = None
        for line in _uncomment(_read(f)).splitlines():
            m = re.match(r'\s*([a-z0-9_]+)\s*=\s*\{\s*$', line)
            if m:
                cur = m.group(1); out.setdefault(cur, 0); continue
            m = re.match(r'\s*([a-z0-9_]+)\s*=\s*(\d+)\s*$', line)
            if m and cur:
                out[cur] += int(m.group(2))
    return out


def start_pops() -> dict[str, float]:
    """location → total starting population, in thousands."""
    out, cur = {}, None
    for line in _read(SETUP / '06_pops.txt').splitlines():
        m = re.match(r'\s*([a-z0-9_]+)\s*=\s*\{\s*$', line)
        if m and m.group(1) != 'locations':
            cur = m.group(1); out.setdefault(cur, 0.0); continue
        mm = re.search(r'size\s*=\s*([\d.]+)', line)
        if mm and cur:
            out[cur] += float(mm.group(1))
    return out


def dev_weights() -> dict[str, float]:
    """Every additive term in setup/start/14_development.txt.

    A key may appear twice (wexford_province does) and the file's own header
    says "all valid values is added together", so duplicates sum."""
    out: dict[str, float] = {}
    for k, v in re.findall(r'^\s*([a-z0-9_]+)\s*=\s*(-?[\d.]+)',
                           _uncomment(_read(SETUP / '14_development.txt')), re.M):
        out[k] = out.get(k, 0.0) + float(v)
    out.pop('development', None)
    return out


def owners() -> tuple[dict[str, str], set[str]]:
    """location → owning tag, and the set of country capital locations."""
    text = _uncomment(_read(SETUP / '10_countries.txt'))
    owner: dict[str, str] = {}
    caps: set[str] = set()
    for tm in re.finditer(r'^\t([A-Z0-9_]{2,})\s*=\s*\{', text, re.M):
        tag, body = tm.group(1), _brace_body(text, tm.end() - 1)
        for m in re.finditer(r'own_control_(?:core|colony|claim)\s*=\s*\{([^{}]*)\}', body):
            for loc in m.group(1).split():
                owner.setdefault(loc, tag)
        cm = re.search(r'\bcapital\s*=\s*([a-z0-9_]+)', body)
        if cm:
            caps.add(cm.group(1))
    return owner, caps


def town_rights() -> dict[str, str]:
    """location → town right granted at start."""
    return dict(re.findall(r'^\s*([a-z0-9_]+)\s*=\s*([a-z0-9_]+)\s*$',
                           _uncomment(_read(SETUP / '24_town_rights.txt')), re.M))


def map_facts() -> dict[str, dict]:
    """Per-location river tier and equator closeness (see build_rivers.py)."""
    if not MAPFACTS.exists():
        return {}
    return json.load(open(MAPFACTS, encoding='utf-8'))['locations']


def country_values() -> dict[str, float]:
    """tag → starting capital-vs-traditional-economy position."""
    p = ROOT / 'public' / 'country-start.json'
    if not p.exists():
        return {}
    d = json.load(open(p, encoding='utf-8'))
    return {t: (v.get('values') or {}).get('capital_economy_vs_traditional_economy', 0.0)
            for t, v in d.items()}


# --------------------------------------------------------------------- model

class Model:
    """Everything the capacity formula needs, parsed once."""

    def __init__(self) -> None:
        self.tmpl = templates()
        self.hier = hierarchy()
        self.rank, self.tsetup = ranks()
        self.levels = town_setup_levels()
        self.pops = start_pops()
        self.W = dev_weights()
        self.owner, self.capitals = owners()
        self.provcaps = province_capitals()
        self.rights = town_rights()
        self.terr = terrain_terms()
        self.static = statics()
        self.right_terms = town_right_terms()
        self.trad = traditional_economy_pct()
        self.values = country_values()
        self.facts = map_facts()
        self.rivers = river_names()

    # -- development ------------------------------------------------------
    def development(self, loc: str) -> float:
        """The start value setup/start/14_development.txt computes, floored at 1."""
        return max(1.0, self.development_raw(loc))

    def development_raw(self, loc: str) -> float:
        """The same sum before the floor — what build_rivers.py solves against."""
        t = self.tmpl.get(loc, {})
        W = self.W
        v = W.get('base', 0.0)
        nhs = t.get('natural_harbor_suitability')
        if nhs is not None:
            v += W.get('coastal', 0.0) * float(nhs)
        size = (self.facts.get(loc) or {}).get('riv', 0)
        if size:
            v += W.get('river', 0.0) * (size + 1)      # tier n ⇔ river size n+1
        r = self.rank.get(loc)
        if r in ('city', 'town'):
            v += W.get(r, 0.0)
        for key in ('vegetation', 'climate', 'topography'):
            v += W.get(t.get(key, ''), 0.0)
        for level in self.hier.get(loc, ()):
            v += W.get(level, 0.0)
        v += W.get(loc, 0.0)
        return v

    # -- capacity ---------------------------------------------------------
    def capacity(self, loc: str) -> dict | None:
        """{cap, pct, dev, terms, estimated} in thousands, or None for sea."""
        t = self.tmpl.get(loc)
        if not t or 'vegetation' not in t:
            return None
        f = self.facts.get(loc) or {}
        terr, st = self.terr, self.static
        flat, pct = 0.0, 0.0
        flats: list[dict] = []
        pcts: list[dict] = []

        def add(label: str, fl: float = 0.0, pc: float = 0.0) -> None:
            """One tooltip line each, flats before percents, as the game lists them.

            A location rank contributes both (city is +100K *and* +25%) and the
            game shows it twice, once in each group."""
            nonlocal flat, pct
            label = label.strip().capitalize()
            if fl:
                flat += fl
                flats.append({'label': label, 'flat': round(fl, 3), 'pct': 0.0})
            if pc:
                pct += pc
                pcts.append({'label': label, 'flat': 0.0, 'pct': round(pc, 5)})

        veg = terr['vegetation'].get(t['vegetation'], (0.0, 0.0))
        add(f'{_pretty(t["vegetation"])} vegetation', veg[0], veg[1])
        rank = self.rank.get(loc)
        if rank:
            add(f'{_pretty(rank)} location rank', *terr['rank'].get(rank, (0.0, 0.0)))
        add('closeness to equator', st.get('location_closeness_to_equator_impact', (0, 0))[0]
            * f.get('eq', 0.0))
        clim, topo = t.get('climate', ''), t.get('topography', '')
        add(f'{_pretty(clim)} climate', *terr['climate'].get(clim, (0.0, 0.0)))
        add(f'{_pretty(topo)} topography', *terr['topography'].get(topo, (0.0, 0.0)))

        dev = self.development(loc)
        add('development', pc=st.get('development', (0, 0))[1] * dev)
        if t.get('natural_harbor_suitability') is not None:
            add('coastal', pc=st.get('coastal', (0, 0))[1])
        tier = f.get('riv', 0)
        if tier:
            add(self.rivers.get(tier, f'river flowing through ({tier})'),
                pc=st.get(f'river_flowing_through_{tier}', (0, 0))[1])
        if loc in self.capitals:
            add('capital', pc=st.get('capital', (0, 0))[1])
        elif loc in self.provcaps:
            add('province capital', pc=st.get('province_capital', (0, 0))[1])
        lv = self.levels.get(self.tsetup.get(loc, ''), 0)
        if lv:
            add('staffed buildings', pc=st.get('building_levels', (0, 0))[1] * lv)
        tr = self.rights.get(loc)
        if tr and tr in self.right_terms:
            add(_pretty(tr.replace('_town_rights', '')) + ' rights', pc=self.right_terms[tr])
        val = self.values.get(self.owner.get(loc, ''), 0.0)
        if val > 0 and self.trad:
            add('traditional economy', pc=self.trad * val / 100.0)

        cap = flat * (1 + pct)
        pop = self.pops.get(loc, 0.0)
        return {
            'cap': round(cap, 2),
            'dev': round(dev, 2),
            'pop': round(pop, 3),
            'pct': round(100 * pop / cap, 3) if cap > 0 else None,
            'estimated': bool(f.get('est')),
            'terms': flats + pcts,
        }
