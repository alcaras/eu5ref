"""Walk every dataset's rich-text token streams for ["r", id, label]
references and invert them: backlinks.json maps target entity id →
[{id, name, page}] of the entities that mention it.

Runs after build_entities.py (needs the registry for page routes).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'src' / 'data'
SKIP_FILES = {'entities.json', 'backlinks.json'}


def collect_refs(node, refs: set):
    if isinstance(node, list):
        if len(node) == 3 and node[0] == 'r' and isinstance(node[1], str):
            refs.add(node[1])
        else:
            for item in node:
                collect_refs(item, refs)
    elif isinstance(node, dict):
        for v in node.values():
            collect_refs(v, refs)


def main():
    registry = json.loads((DATA / 'entities.json').read_text())['entities']
    backlinks: dict[str, list] = {}
    for f in sorted(DATA.glob('*.json')):
        if f.name in SKIP_FILES:
            continue
        payload = json.loads(f.read_text())
        for e in payload.get('entities', []):
            refs: set = set()
            collect_refs(e, refs)
            refs.discard(e['id'])
            src = registry.get(e['id'], {})
            for target in refs:
                backlinks.setdefault(target, []).append({
                    'id': e['id'],
                    'name': e['name'],
                    'page': src.get('page'),
                })
    for links in backlinks.values():
        links.sort(key=lambda x: x['name'])
    out = DATA / 'backlinks.json'
    out.write_text(json.dumps(backlinks, sort_keys=True, ensure_ascii=False, indent=1) + '\n',
                   encoding='utf-8')
    n = sum(len(v) for v in backlinks.values())
    print(f'  {out.relative_to(ROOT)}: {len(backlinks)} targets, {n} links')
    return 0


if __name__ == '__main__':
    sys.exit(main())
