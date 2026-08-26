"""Aggregate every dataset's entities into src/data/entities.json — the
cross-site registry that powers <Term>, search, and backlinks.

Runs AFTER the dataset build scripts: it reads src/data/*.json (any file
with an `entities` list), so new datasets join the registry automatically.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'src' / 'data'

# entity type → site route prefix for detail pages (None = no detail page yet)
TYPE_PAGES = {
    'concept': 'concepts',
    'good': 'goods',
}

SKIP_FILES = {'entities.json', 'backlinks.json'}


def main():
    registry = {}
    aliases = {}
    for f in sorted(DATA.glob('*.json')):
        if f.name in SKIP_FILES:
            continue
        payload = json.loads(f.read_text())
        for e in payload.get('entities', []):
            page_prefix = TYPE_PAGES.get(e['type'])
            entry = {
                'type': e['type'],
                'name': e['name'],
                'slug': e['slug'],
                'page': f"{page_prefix}/{e['slug']}" if page_prefix else None,
            }
            if e.get('color'):
                entry['color'] = e['color']
            registry[e['id']] = entry
            aliases.setdefault(e['name'].lower(), e['id'])
            for a in (e.get('data') or {}).get('aliases', []):
                aliases.setdefault(a.lower(), e['id'])
    out = DATA / 'entities.json'
    out.write_text(json.dumps({'entities': registry, 'aliases': aliases},
                              sort_keys=True, ensure_ascii=False, indent=1) + '\n',
                   encoding='utf-8')
    print(f'  {out.relative_to(ROOT)}: {len(registry)} entities, {len(aliases)} aliases')
    return 0


if __name__ == '__main__':
    sys.exit(main())
