"""game_concepts → src/data/concepts.json — the glossary that anchors the
site's link graph. Aliases are folded into their canonical concept."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import ref
from ref import eid, rich, slugify, write_dataset, facet_meta


def main():
    concepts = ref.parser.game_concepts
    entities = []
    for name, c in sorted(concepts.items()):
        if getattr(c, 'is_alias', False):
            continue
        display = c.display_name
        if not display or display == name:
            display = name.replace('_', ' ').title()
        aliases = [t for a in c.alias if a in concepts
                   if (t := ref.plain_text(concepts[a].display_name))]
        entities.append({
            'id': eid('concept', name),
            'type': 'concept',
            'slug': slugify(name),
            'name': display,
            'desc': rich(c.description),
            'facets': {'family': c.family or 'general'},
            'data': {'aliases': aliases},
        })
    write_dataset('concepts', {
        'dataset': 'concepts',
        'source': 'main_menu/common/game_concepts',
        'entities': entities,
        'facets': facet_meta(entities, [('family', 'Family')]),
    })


if __name__ == '__main__':
    main()
