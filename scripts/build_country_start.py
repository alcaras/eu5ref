"""Starting societal values, estate privileges and laws per country.

The 1337 bookmark gives every tag a stack of `include = "<template>"` lines
(game/main_menu/setup/templates/) plus an inline `government = { ... }` block
that overrides them. Templates carry the starting societal-value position, the
granted estate privileges and the law selections, so this resolves the stack
into one record per tag -> public/country-start.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import lib.ref as ref

GAME = ref.ROOT / 'game'
TEMPLATES = GAME / 'main_menu' / 'setup' / 'templates'
COUNTRIES = GAME / 'main_menu' / 'setup' / 'start' / '10_countries.txt'

_TOKEN = re.compile(r'"[^"]*"|[{}]|=|[^\s{}=]+')


def _strip(text: str) -> str:
    """Drop comments, keeping any '#' that sits inside a quoted string."""
    out = []
    for line in text.splitlines():
        q = False
        for i, ch in enumerate(line):
            if ch == '"':
                q = not q
            elif ch == '#' and not q:
                line = line[:i]
                break
        out.append(line)
    return '\n'.join(out)


def parse(text: str) -> list:
    """Clausewitz -> flat list of ('key', value) pairs and bare tokens.

    Repeating keys are common here (several `include` lines, and privilege
    blocks are bare token lists), so this keeps order and duplicates rather
    than collapsing into a dict.
    """
    toks = _TOKEN.findall(_strip(text))
    pos = 0

    def block() -> list:
        nonlocal pos
        items = []
        while pos < len(toks):
            t = toks[pos]
            if t == '}':
                pos += 1
                return items
            if pos + 1 < len(toks) and toks[pos + 1] == '=':
                pos += 2
                if pos < len(toks) and toks[pos] == '{':
                    pos += 1
                    items.append((t, block()))
                else:
                    items.append((t, toks[pos].strip('"')))
                    pos += 1
            elif t == '{':
                # Anonymous block inside a list, e.g. Byzantium's bureaucracy
                # entries: `{ type = x date = y }`. Recurse, or its closing
                # brace ends the enclosing block early.
                pos += 1
                items.append(block())
            else:
                items.append(t.strip('"'))
                pos += 1
        return items

    return block()


def get(items: list, key: str):
    for it in items:
        if isinstance(it, tuple) and it[0] == key:
            return it[1]
    return None


def get_all(items: list, key: str) -> list:
    return [it[1] for it in items if isinstance(it, tuple) and it[0] == key]


def bare(items: list) -> list:
    return [it for it in items if isinstance(it, str)]


def pairs_of(items: list) -> dict:
    return {k: v for it in items if isinstance(it, tuple) for k, v in [it] if isinstance(v, str)}


def main() -> None:
    axes = set(json.loads((ref.ROOT / 'public' / 'values.json').read_text())['pairs'])

    templates = {}
    for f in sorted(TEMPLATES.glob('*.txt')):
        templates[f.stem] = parse(f.read_text(encoding='utf-8-sig'))

    def apply(rec: dict, items: list, seen: set) -> None:
        """Fold one template or inline block into rec, following includes."""
        for name in get_all(items, 'include'):
            if name in templates and name not in seen:
                seen.add(name)
                apply(rec, templates[name], seen)
        if (tech := get(items, 'starting_technology_level')):
            rec['tech'] = int(tech)
        gov = get(items, 'government')
        if not isinstance(gov, list):
            return
        for k, v in pairs_of(gov).items():
            if k in axes:
                rec['values'][k] = float(v)
            elif k in ('type', 'heir_selection'):
                rec[k] = v
        # Later blocks add privileges rather than replacing the list; a tag
        # inheriting two templates keeps both sets, as the game does.
        if isinstance(privs := get(gov, 'privilege'), list):
            for p in bare(privs):
                if p not in rec['privileges']:
                    rec['privileges'].append(p)
        if isinstance(laws := get(gov, 'laws'), list):
            rec['laws'].update(pairs_of(laws))
        if isinstance(parl := get(gov, 'parliament'), list):
            if (pt := get(parl, 'parliament_type')):
                rec['parliament'] = pt

    root = parse(COUNTRIES.read_text(encoding='utf-8-sig'))
    block = get(root, 'countries') or []
    inner = get(block, 'countries')
    tags = (inner if isinstance(inner, list) else []) + block

    out = {}
    for it in tags:
        if not (isinstance(it, tuple) and re.fullmatch(r'[A-Z0-9]{3}', it[0]) and isinstance(it[1], list)):
            continue
        rec = {'values': {}, 'privileges': [], 'laws': {}, 'type': None,
               'heir_selection': None, 'parliament': None, 'tech': None}
        apply(rec, it[1], set())
        if rec['values'] or rec['privileges'] or rec['laws']:
            out[it[0]] = {k: v for k, v in rec.items() if v not in (None, {}, [])}

    dest = ref.ROOT / 'public' / 'country-start.json'
    dest.write_text(json.dumps(out, sort_keys=True, separators=(',', ':')))
    vals = sum(1 for r in out.values() if r.get('values'))
    print(f'  public/country-start.json: {len(out)} tags, {vals} with societal values, '
          f'{sum(len(r.get("privileges", [])) for r in out.values())} privilege grants, '
          f'{sum(len(r.get("laws", {})) for r in out.values())} law selections')


if __name__ == '__main__':
    main()
