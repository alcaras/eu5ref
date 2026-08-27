"""Patch tripwire, owreference-style: nothing the game ships may be
*silently* ignored.

1. Folder coverage — every folder in game/in_game/common/ (and the curated
   main_menu/common/ list) must be BUILT (feeds a dataset), PLANNED (has a
   catalog tab waiting), or SKIPPED (consciously, with a reason). A new
   folder appearing in a patch fails the pipeline until classified.

2. Modifier resolution — emitted Mods flagged `unresolved` (no modifier_type
   match) are reported so they can be promoted; they still render honestly
   in the meantime. Reported as warnings, not failures.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'game' / 'in_game' / 'common'
DATA = ROOT / 'src' / 'data'

# folder → dataset(s) that consume it
BUILT = {
    'goods': ['goods.json'],
    'advances': ['advances.json'],
    'building_types': ['buildings.json'],
    'unit_types': ['units.json', 'battle.json (public/)'],
    'unit_categories': ['battle.json (public/)'],
    'unit_formation_preference': ['battle.json (public/)'],
    'laws': ['laws.json'],
    'government_reforms': ['reforms.json'],
    'estates': ['estates.json'],
    'estate_privileges': ['estate-privileges.json'],
    'religions': ['religions.json'],
    'cultures': ['cultures.json'],
    'pop_types': ['pops.json'],
    'formable_countries': ['formables.json'],
    'age': ['ages.json'],
    'institution': ['institutions.json'],
    'subject_types': ['subjects.json'],
    'international_organizations': ['international-organizations.json'],
    'casus_belli': ['casus-belli.json'],
    'wargoals': ['wargoals.json'],
    'peace_treaties': ['peace-treaties.json'],
    'climates': ['climates.json'],
    'topography': ['topography.json'],
    'vegetation': ['vegetation.json'],
    'town_rights': ['town-rights.json'],
    'location_ranks': ['location-ranks.json'],
    'parliament_types': ['parliament-types.json'],
    'parliament_issues': ['parliament-issues.json'],
    'parliament_agendas': ['parliament-agendas.json'],
    'cabinet_actions': ['cabinet-actions.json'],
    'heir_selections': ['heir-selections.json'],
    'societal_values': ['societal-values.json'],
    'traits': ['traits.json'],
    'child_educations': ['child-educations.json'],
    'character_interactions': ['character-interactions.json'],
    'chivalric_orders': ['chivalric-orders.json'],
    'levies': ['levies.json'],
    'recruitment_method': ['recruitment-methods.json'],
    'country_interactions': ['country-interactions.json'],
    'situations': ['situations.json'],
    'disasters': ['disasters.json'],
    'diseases': ['diseases.json'],
    'government_types': ['government-types.json'],
    'country_ranks': ['country-ranks.json'],
    'missions': ['missions.json'],
    'religious_aspects': ['religious-aspects.json'],
    'religious_schools': ['religious-schools.json'],
    'holy_sites': ['holy-sites.json'],
}

# Consciously not reference material (engine plumbing, AI tuning, debug…).
SKIPPED = {
    'ai_diplochance': 'AI tuning, not player-facing reference',
    'ai_personalities': 'AI tuning',
    'ai_scripted_expansion_score': 'AI tuning',
    'ai_scripted_expansion_target': 'AI tuning',
    'alert_descriptions': 'UI plumbing',
    'area_preferences': 'AI tuning',
    'attribute_columns': 'UI plumbing',
    'auto_modifiers': 'engine plumbing (feeds modifier display, read via toolkit)',
    'avatars': 'character portrait plumbing',
    'biases': 'AI tuning',
    'customizable_localization': 'loc plumbing (read via toolkit)',
    'death_reason': 'flavor text plumbing',
    'designated_heir_reason': 'flavor text plumbing',
    'effect_localization': 'loc plumbing',
    'generic_action_ai_lists': 'AI tuning',
    'genes': 'portrait DNA plumbing',
    'music_player_tracks': 'audio',
    'on_action': 'event wiring (consumed via events datasets later)',
    'persistent_dna': 'portrait DNA',
    'scriptable_hints': 'tutorial plumbing',
    'scripted_effects': 'script library (consumed indirectly)',
    'scripted_guis': 'UI plumbing',
    'scripted_lists': 'script library',
    'scripted_modifiers': 'script library',
    'scripted_relations': 'script library',
    'scripted_rules': 'script library',
    'scripted_triggers': 'script library',
    'script_values': 'formula library (consumed by mechanics pages later)',
    'tests': 'dev tests',
    'trait_flavor': 'flavor text plumbing (joins traits dataset later)',
    'trigger_localization': 'loc plumbing',
    'tutorial_lesson_chains': 'tutorial',
    'tutorial_lessons': 'tutorial',
}

# Everything else must appear here: planned datasets per the tabs.ts catalog.
PLANNED = {
    'artist_types', 'artist_work', 'building_categories',
    'bureaucracies', 'country_description_categories', 'culture_groups', 'diplomatic_costs',
    'employment_systems',
    'ethnicities', 'generic_actions',
    'gods', 'goods_demand', 'goods_demand_category',
    'hegemons', 'historical_scores',
    'holy_site_types', 'insults',
    'international_organization_land_ownership_rules',
    'international_organization_payments',
    'international_organization_special_statuses', 'join_war_rules', 'language_families', 'languages', 'mission_task_defs', 'movements',
    'policies', 'prices', 'production_methods',
    'rebel_demands', 'regencies', 'religion_groups',
    'religious_factions', 'religious_figures',
    'religious_focuses', 'resolutions', 'rival_criteria',
    'road_types', 'scripted_country_names', 'scripted_diplomatic_objectives',
    'scripted_geography', 'subject_military_stances', 'town_setups', 'unit_abilities',
    }


def main() -> int:
    folders = sorted(p.name for p in COMMON.iterdir() if p.is_dir())
    unclassified = [f for f in folders
                    if f not in BUILT and f not in SKIPPED and f not in PLANNED]
    stale = [f for f in list(BUILT) + list(SKIPPED) + list(PLANNED)
             if f not in folders]

    unresolved: dict[str, int] = {}
    for f in sorted(DATA.glob('*.json')):
        try:
            payload = json.loads(f.read_text())
        except Exception:
            continue
        ents = payload.get('entities') if isinstance(payload, dict) else None
        if not isinstance(ents, list):
            continue
        for e in ents:
            for m in e.get('mods') or []:
                if m.get('unresolved'):
                    unresolved[m['key']] = unresolved.get(m['key'], 0) + 1

    built_n = len(BUILT)
    print(f'audit: {len(folders)} common/ folders — '
          f'{built_n} built, {len(PLANNED)} planned, {len(SKIPPED)} skipped')
    if unresolved:
        print(f'⚠ {len(unresolved)} unresolved modifier key(s) rendering as raw fallback:')
        for k, n in sorted(unresolved.items()):
            print(f'   {k} ×{n}')
    if stale:
        print(f'⚠ classified folders no longer in the game data: {stale}')
    if unclassified:
        print('✗ UNCLASSIFIED folders (new in this patch?) — add to BUILT, '
              'PLANNED, or SKIPPED in audit_coverage.py:')
        for f in unclassified:
            print(f'   {f}')
        return 1
    print('✓ audit passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
