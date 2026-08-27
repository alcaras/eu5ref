"""Resolve unit_types through their copy_from chains onto category bases.

The toolkit's UnitType only inherits `category` through copy_from, so every
numeric stat reads as its 0 default for the ~285 units that are built as
`copy_from = <template>` plus a few overrides. This module reads the RAW
parse trees (which keep every declared key, including `hide`/`empty`/
`is_special` that the toolkit drops) and applies the resolution rule the
files themselves force:

    resolved stat = category base + nearest declaration along the chain

Stats are DELTAS on the category base — `a_schiltron` declares
`frontage = -0.25` (category base 1) and `a_handgonners` declares
`initiative = -4` (category base 5), which only make sense additively.
A key re-declared closer to the leaf REPLACES the template's declaration
(nearest-wins): `a_steppe_horse_archers` sets `max_strength = 0.4` over its
template's 0.5, it does not stack to 0.9.

Terrain `combat = {}` / `impact = {}` blocks are whole-block nearest-wins
(a block is one value to the parser; a leaf that declares its own block
replaces the template's).
"""
from functools import lru_cache

import ref

# Numeric keys a unit block (or its category) may declare, per
# unit_types/readme.txt. Values accumulate as category base + chain delta.
STAT_KEYS = (
    'max_strength', 'combat_power', 'initiative', 'combat_speed',
    'flanking_ability', 'frontage', 'secure_flanks_defense',
    'morale_damage_done', 'morale_damage_taken',
    'strength_damage_done', 'strength_damage_taken',
    'damage_taken',
    'movement_speed', 'supply_weight', 'attrition_loss',
    'food_storage_per_strength', 'food_consumption_per_strength',
    'bombard_efficiency', 'artillery_barrage',
    'transport_capacity', 'crew_size', 'blockade_capacity',
    'cannons', 'hull_size',
)

# Booleans that follow nearest-wins inheritance through copy_from.
FLAG_KEYS = ('levy', 'buildable', 'default', 'assault', 'bombard',
             'auxiliary', 'is_special')

# Structural markers that are NOT inherited: templates declare
# `hide`/`empty` on themselves and every real unit copies from one.
OWN_ONLY_KEYS = ('hide', 'empty')


def _num(v):
    """Declared value → float, or None if it isn't a plain number."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, list) and v and isinstance(v[-1], (int, float)):
        # duplicate key in one block groups to a list; last declaration wins
        return float(v[-1])
    return None


def _block(v):
    """Tree-valued key (combat/impact) → plain dict of numbers."""
    out = {}
    try:
        items = list(v)
    except TypeError:
        return out
    for k, val in items:
        n = _num(val)
        if n is not None:
            out[str(k)] = n
    return out


@lru_cache(maxsize=1)
def _raw_units():
    return ref.parser.parser.parse_folder_as_one_file('in_game/common/unit_types')


@lru_cache(maxsize=1)
def _raw_categories():
    return ref.parser.parser.parse_folder_as_one_file('in_game/common/unit_categories')


@lru_cache(maxsize=1)
def categories() -> dict:
    """Category name → {stats, flags, is_army}."""
    cats = {}
    for name, node in _raw_categories():
        stats, flags = {}, {}
        for k, v in node:
            if k in STAT_KEYS:
                n = _num(v)
                if n is not None:
                    stats[k] = n
            elif k in ('assault', 'bombard', 'auxiliary', 'is_army',
                       'is_garrison', 'exclude_from_combined_arms'):
                flags[k] = bool(v)
        cats[name] = {'stats': stats, 'flags': flags,
                      'is_army': bool(node.get_or_default('is_army', False))}
    return cats


@lru_cache(maxsize=1)
def resolved_units() -> dict:
    """Unit type key → fully resolved record.

    {category, age, stats{...}, flags{...}, hide, combat{}, impact{},
     upgrades_to, limit, chain[...]}
    """
    raw = _raw_units()
    cats = categories()

    def resolve(name):
        # chain leaf→root, guarded against cycles
        chain, cur, seen = [], name, set()
        while cur is not None and cur in raw.dictionary and cur not in seen:
            seen.add(cur)
            node = raw[cur]
            chain.append((cur, node))
            cur = node.get_or_default('copy_from', None)

        # nearest-wins declarations: apply root first, leaf overwrites
        decl = {}
        for _, node in reversed(chain):
            for k, v in node:
                decl[k] = v

        leaf = chain[0][1]
        cat_name = decl.get('category')
        cat = cats.get(cat_name, {'stats': {}, 'flags': {}, 'is_army': False})

        stats = {}
        for k in STAT_KEYS:
            base = cat['stats'].get(k, 0.0)
            delta = _num(decl[k]) if k in decl else None
            val = base + (delta or 0.0)
            if val or k in cat['stats'] or k in decl:
                stats[k] = round(val, 4)

        flags = dict(cat['flags'])
        for k in FLAG_KEYS:
            if k in decl:
                flags[k] = bool(decl[k])
        for k in OWN_ONLY_KEYS:
            if k in leaf.dictionary:
                flags[k] = bool(leaf[k])

        return {
            'category': cat_name,
            'is_army': cat['is_army'],
            'age': decl.get('age'),
            'stats': stats,
            'flags': flags,
            'combat': _block(decl['combat']) if 'combat' in decl else {},
            'impact': _block(decl['impact']) if 'impact' in decl else {},
            'upgrades_to': decl.get('upgrades_to'),
            'limit': decl['limit'] if isinstance(decl.get('limit'), str) else None,
            'chain': [n for n, _ in chain],
        }

    return {name: resolve(name) for name, _ in raw}
