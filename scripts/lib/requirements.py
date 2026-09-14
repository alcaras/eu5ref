"""Trigger block → readable requirement lines + facet tags.

Privileges, laws, law policies, government reforms and disasters are all
gated the same way: a `potential` / `can_start` (who ever sees it) and an
`allow` / `can_end` (who may take it, or what ends it), whose predicates are
the "additional requirements" a player actually needs to know about. The
toolkit hands those blocks back as raw Trees and models none of their
meaning, so this module renders them.

Two outputs per block:
  lines — readable strings, the game's own phrasing where it has one
  tags  — coarse categories, for faceting ("Religion", "Advance", …)

Honest fallback, as everywhere else on this site: a predicate we do not know
is still rendered (prettified) and tagged "Other" rather than dropped, so the
page never silently claims a gated thing is free.
"""
import collections
import re

import ref
import scriptvalue
import triggers

# ── categories ─────────────────────────────────────────────────────────
COUNTRY, GOV, RELIGION, CULTURE, GEO = 'Country', 'Government', 'Religion', 'Culture', 'Geography'
AGE, INSTITUTION, ADVANCE = 'Age', 'Institution', 'Advance'
LAW, REFORM, PRIVILEGE, ESTATE = 'Law', 'Reform', 'Privilege', 'Estate'
URBAN = 'Urban right'
VALUE, CHARACTER, REBEL, DISASTER, POPULATION = ('Societal value', 'Ruler & dynasty',
                                                 'Rebels & war', 'Disaster', 'Population')
ORG, SCRIPTED, ECONOMY, OTHER = 'Organization', 'Event or script', 'Economy', 'Other'
NONE = 'No requirement'

# Predicates that reached the honest fallback (rendered, but in their own
# script terms rather than the game's). Builders print the tally so the gap
# stays visible instead of quietly padding pages with "Other" lines.
FELL_THROUGH: collections.Counter = collections.Counter()

ORDER = [COUNTRY, GOV, RELIGION, CULTURE, GEO, AGE, INSTITUTION, ADVANCE,
         LAW, REFORM, PRIVILEGE, URBAN, ESTATE, VALUE, CHARACTER, REBEL,
         DISASTER, POPULATION, ORG, ECONOMY, SCRIPTED, OTHER, NONE]

# Does a condition say WHO you must be (nobody can change their tag, culture,
# religion or capital region on a whim), or only WHAT you must have done?
# Only a POSITIVE identity condition narrows the field: "not a Steppe Horde"
# still leaves the reform open to almost everyone, so it does not count.
IDENTITY = {COUNTRY, GOV, RELIGION, CULTURE, GEO}
# …except the geography predicates that are about what you hold, not who you
# are — a port can be conquered, a capital's region cannot.
# Same for the Government predicates that are about the state you are in, not
# the state you are: any country can lose stability, gain a subject, turn
# revolutionary or call a parliament.
ACQUIRABLE_PREDICATES = {
    'owns', 'num_of_ports', 'is_coastal', 'is_port',
    'has_building', 'location_rank', 'is_produced_in_market',
    'is_revolutionary', 'is_rebel_country', 'num_subjects', 'subject_loyalty',
    'liberty_desire', 'government_power', 'republican_tradition', 'horde_unity',
    'crown_power', 'legitimacy', 'stability', 'celestial_authority',
    'is_at_war', 'at_war', 'in_civil_war',
    'num_locations', 'num_provinces', 'country_rank', 'is_great_power',
    'num_locations_owned_or_owned_by_subjects_or_below',
    'average_country_literacy', 'average_control_in_home_region',
    'current_year', 'country_exists', 'exists', 'is_subject_or_below_of',
    'is_active_parliament', 'has_parliament', 'parliament_type',
    'months_since_last_parliament_called', 'parliament_issue_support',
    'is_subject', 'is_independent', 'country_economical_base',
}
ANY_COUNTRY = 'Any country'
SOME_COUNTRIES = 'Specific countries'

# predicate → (category, phrasing). {} is filled with the resolved value.
PREDICATES = {
    'has_or_had_tag':               (COUNTRY, 'is or was {}'),
    'tag':                          (COUNTRY, 'is {}'),
    'exists':                       (COUNTRY, '{} exists'),
    'country_exists':               (COUNTRY, '{} exists'),
    'dynasty':                      (COUNTRY, 'ruling dynasty is {}'),
    'is_frankokratia_state':        (COUNTRY, 'is a Frankokratia state'),
    'country_rank':                 (COUNTRY, 'rank is {}'),
    'is_great_power':               (COUNTRY, 'is a great power'),
    'num_locations':                (COUNTRY, 'locations {}'),
    'num_provinces':                (COUNTRY, 'provinces {}'),
    'num_locations_owned_or_owned_by_subjects_or_below':
                                    (COUNTRY, 'locations held by it or its subjects {}'),
    'is_subject_or_below_of':       (COUNTRY, 'is a subject of {}'),
    'country_economical_base':      (ECONOMY, 'economic base {}'),
    'average_country_literacy':     (COUNTRY, 'literacy {}'),
    'average_control_in_home_region': (COUNTRY, 'control in the home region {}'),
    'current_year':                 (COUNTRY, 'year is {}'),

    'government_type':              (GOV, 'government is {}'),
    'has_tribal_government':        (GOV, 'has a tribal government'),
    'country_type':                 (GOV, 'country type is {}'),
    'is_subject_type':              (GOV, 'is a {}'),
    'parliament_type':              (GOV, 'parliament is {}'),
    'has_parliament':               (GOV, 'has a parliament'),
    'is_active_parliament':         (GOV, 'parliament is in session'),
    'is_subject':                   (GOV, 'is a subject'),
    'is_independent':               (GOV, 'is independent'),
    'is_revolutionary':             (GOV, 'is revolutionary'),
    'is_rebel_country':             (GOV, 'is a rebel country'),
    'government_power':             (GOV, 'government power {}'),
    'republican_tradition':         (GOV, 'republican tradition {}'),
    'horde_unity':                  (GOV, 'horde unity {}'),
    'celestial_authority':          (GOV, 'celestial authority {}'),
    'crown_power':                  (GOV, 'crown power {}'),
    'legitimacy':                   (GOV, 'legitimacy {}'),
    'stability':                    (GOV, 'stability {}'),
    'num_privileges':               (PRIVILEGE, 'granted privileges {}'),
    'months_since_last_parliament_called': (GOV, 'months since the last parliament {}'),
    'parliament_issue_support':     (GOV, 'support for the issue {}'),
    'num_subjects':                 (GOV, 'subjects {}'),
    'subject_loyalty':              (GOV, 'subject loyalty {}'),
    'liberty_desire':               (GOV, 'liberty desire {}'),

    'religion':                     (RELIGION, 'religion is {}'),
    'religion.group':               (RELIGION, 'religion group is {}'),
    'religious_unity':              (RELIGION, 'religious unity {}'),
    'has_religious_school':         (RELIGION, 'religious school is {}'),
    'reformation_is_enabled':       (RELIGION, 'the Reformation has begun'),
    'tolerance_heretic':            (RELIGION, 'tolerance of heretics {}'),

    'culture':                      (CULTURE, 'culture is {}'),
    'has_culture_group':            (CULTURE, 'culture group is {}'),
    'culture.language':             (CULTURE, 'language is {}'),
    'culture.language.language_family': (CULTURE, 'language family is {}'),
    'court_language':               (CULTURE, 'court language is {}'),

    'capital':                      (GEO, 'capital {}'),
    'area':                         (GEO, 'in area {}'),
    'region':                       (GEO, 'in region {}'),
    'sub_continent':                (GEO, 'in {}'),
    'continent':                    (GEO, 'in {}'),
    'owns':                         (GEO, 'owns {}'),
    'num_of_ports':                 (GEO, 'ports {}'),
    'is_coastal':                   (GEO, 'is coastal'),
    'is_port':                      (GEO, 'is a port'),
    'location_rank':                (GEO, 'location is a {}'),
    'has_building':                 (GEO, 'has building {}'),

    'current_age':                  (AGE, 'age is {}'),
    'current_age_or_later':         (AGE, 'age is {} or later'),

    'has_embraced_institution':     (INSTITUTION, 'has embraced {}'),

    'has_advance':                  (ADVANCE, 'has researched {}'),

    'has_law':                      (LAW, 'has law {}'),
    'has_policy':                   (LAW, 'runs policy {}'),
    'has_reform':                   (REFORM, 'has reform {}'),
    'has_estate_privilege':         (PRIVILEGE, 'has privilege {}'),
    'has_town_rights':              (URBAN, 'has urban right {}'),

    'estate_power':                 (ESTATE, 'estate power {}'),
    'estate_satisfaction':          (ESTATE, 'estate satisfaction {}'),
    'estate_tax_rate':              (ESTATE, 'estate tax rate {}'),
    'has_slavery':                  (ESTATE, 'has slavery'),
    'country_has_estate':           (ESTATE, 'has the {}'),
    'power':                        (ESTATE, 'power {}'),
    'estate_type':                  (ESTATE, 'the estate {}'),
    # `this != character:x` inside a ruler scope — the comparison is the whole
    # sentence, the scope already said who "this" is
    'this':                         (CHARACTER, '{}'),
    'is_ai':                        (SCRIPTED, 'is AI-controlled'),

    'is_during_bankruptcy':         (ECONOMY, 'is bankrupt'),
    'regular_army_size':            (REBEL, 'regular regiments {}'),
    'navy_size':                    (REBEL, 'ships {}'),
    'has_raised_levies':            (REBEL, 'has levies raised'),
    'has_truce_with':               (REBEL, 'has a truce with {}'),
    'is_at_war_with':               (REBEL, 'is at war with {}'),
    'is_rival_of':                  (REBEL, 'is a rival of {}'),
    'is_enemy_of':                  (REBEL, 'is an enemy of {}'),
    'is_neighbor_of':               (REBEL, 'borders {}'),
    'has_casus_belli_on':           (REBEL, 'has a casus belli on {}'),
    'is_fighting_war_together_with': (REBEL, 'is fighting alongside {}'),
    'is_subject_of':                (GOV, 'is a subject of {}'),
    'in_union_with':                (GOV, 'is in a union with {}'),
    'has_support_from':             (GOV, 'has the support of {}'),
    'is_regent_of':                 (CHARACTER, 'is regent of {}'),
    'is_capital':                   (GEO, 'is the capital'),
    'has_location_modifier':        (GEO, 'has the {} modifier'),
    'has_ongoing_parliament_debate': (GOV, 'a parliament debate is running'),
    'religion_percentage_in_country': (RELIGION, 'share of the population {}'),
    'opinion':                      (GOV, 'opinion {}'),
    'is_member_of_international_organization': (ORG, 'is a member of {}'),
    'is_leader_of_international_organization': (ORG, 'leads {}'),
    'international_organization_type':         (ORG, 'organization is {}'),
    'international_organization_has_law':      (ORG, 'the organization has law {}'),
    'international_organization_has_policy':   (ORG, 'the organization runs {}'),

    'gold':                         (ECONOMY, 'treasury {}'),
    'monthly_income':               (ECONOMY, 'monthly income {}'),
    'is_produced_in_market':        (ECONOMY, 'market produces {}'),
    'has_currency_to_vote_for_law': (ECONOMY, 'can pay to vote for the law'),
    'monthly_manpower':             (ECONOMY, 'monthly manpower {}'),
    'manpower_percentage':          (ECONOMY, 'manpower {}'),

    # ruler, heir and dynasty
    'has_ruler':                    (CHARACTER, 'has a ruler'),
    'has_regent':                   (CHARACTER, 'has a regent'),
    'has_heir':                     (CHARACTER, 'has an heir'),
    'has_dynasty':                  (CHARACTER, 'has a dynasty'),
    'ruler_or_regent':              (CHARACTER, 'ruler or regent {}'),
    'ruler':                        (CHARACTER, 'ruler {}'),
    'heir':                         (CHARACTER, 'heir {}'),
    'dynasty_exists':               (CHARACTER, 'the {} still exists'),
    'dynasty_head':                 (CHARACTER, 'the dynasty head {}'),
    'total_abilities':              (CHARACTER, 'abilities {}'),
    'age_in_years':                 (CHARACTER, 'age {}'),
    'is_alive':                     (CHARACTER, 'is alive'),
    'is_adult':                     (CHARACTER, 'is an adult'),
    'is_female':                    (CHARACTER, 'is female'),
    'is_legally_male':              (CHARACTER, 'is legally male'),
    'is_ruler':                     (CHARACTER, 'is the ruler'),
    'is_ruler_of':                  (CHARACTER, 'rules {}'),
    'is_heir':                      (CHARACTER, 'is the heir'),
    'is_eligible_heir':             (CHARACTER, 'is an eligible heir'),
    'is_loyal':                     (CHARACTER, 'is loyal'),
    'fertility':                    (CHARACTER, 'fertility {}'),
    'father':                       (CHARACTER, 'father is {}'),
    'mother':                       (CHARACTER, 'mother is {}'),
    'has_character_modifier':       (CHARACTER, 'has the {} trait'),

    # rebels, war and unrest
    'in_civil_war':                 (REBEL, 'is in a civil war'),
    'at_war':                       (REBEL, 'is at war'),
    'is_at_war':                    (REBEL, 'is at war'),
    'is_civil_war_for':             (REBEL, 'is a civil war against {}'),
    'num_rebels':                   (REBEL, 'rebel armies {}'),
    'rebel_progress':               (REBEL, 'rebel progress {}'),
    'rebel_category':               (REBEL, 'rebels are {}'),
    'rebel_name_key':               (REBEL, 'rebels are the {}'),
    'war_exhaustion_percentage':    (REBEL, 'war exhaustion {}'),
    'war_exhaustion':               (REBEL, 'war exhaustion {}'),
    'complacency_percentage':       (REBEL, 'complacency {}'),
    'attacker_leader':              (REBEL, 'the attacker {}'),

    # disasters
    'has_any_active_disaster':      (DISASTER, 'another disaster is running'),
    'disaster_is_active':           (DISASTER, 'the disaster is running'),
    'disaster_type':                (DISASTER, 'the disaster is {}'),

    # population
    'total_population':             (POPULATION, 'population {}'),
    'total_not_tolerated_culture_population':
                                    (POPULATION, 'population of non-tolerated cultures {}'),
    'location_population_percentage': (POPULATION, 'population against capacity {}'),
    'pop_join_rebel_threshold':     (POPULATION, 'pops joining rebels {}'),

    'has_variable':                 (SCRIPTED, 'event flag: {}'),
    'mechanic':                     (SCRIPTED, 'mechanic: {}'),
    'has_cooldown':                 (SCRIPTED, 'off cooldown: {}'),
    'is_situation_active':          (SCRIPTED, 'situation active: {}'),
    'situation_is_active':          (SCRIPTED, 'the situation is running'),
    'situation_has_ended':          (SCRIPTED, 'the situation has ended'),
    'resolution_is_active':         (SCRIPTED, 'resolution {} is active'),
    'has_country_modifier':         (SCRIPTED, 'has the {} modifier'),
    'has_dlc':                      (SCRIPTED, 'owns {}'),
    'count':                        (SCRIPTED, 'count {}'),
    'hre_allowed_emperor_reform_proposal': (ORG, 'the Emperor may propose this reform'),
    'hre_has_enabled_all_imperial_laws':   (ORG, 'all imperial laws are enabled'),
    'hre_can_select_adjacent_reform_level': (ORG, 'the next reform level is reachable'),
    'is_locked_mechanic':           (SCRIPTED, 'mechanic {} unlocked'),
    'has_imperial_examinations':    (SCRIPTED, 'has imperial examinations'),
}

# `has_unlocked_<thing>_trigger = { type = x }` — granted by an advance or an
# event, never by anything the player can read off the entity itself.
_UNLOCK = {
    'has_unlocked_law_trigger': (LAW, 'law'),
    'has_unlocked_policy_trigger': (LAW, 'policy'),
    'has_unlocked_government_reform_trigger': (REFORM, 'reform'),
    'has_unlocked_estate_privilege_trigger': (PRIVILEGE, 'privilege'),
    'has_unlocked_town_rights_trigger': (URBAN, 'urban right'),
}

# Parameterised blocks whose whole meaning is one named sub-key. These are
# scripted triggers with a `$type$` body, so they cannot be inlined — but
# what they say is plain.
_TYPED = {
    'had_disaster_trigger':         (DISASTER, 'has already had the {} disaster', 'type'),
    'has_enabled_disaster_trigger': (DISASTER, 'the {} disaster has been enabled', 'type'),
    'has_blocked_disaster_trigger': (DISASTER, 'the {} disaster is blocked', 'type'),
    'current_age_or_later':         (AGE, 'age is {} or later', 'age'),
}

# `estate_power(estate_type:nobles_estate)` / `societal_value:x` — the subject
# is part of the key, so the phrasing needs it. {s} = subject, {} = comparison.
SUBJECT_PREDICATES = {
    'estate_power':                 (ESTATE, '{s} power {}'),
    'estate_satisfaction':          (ESTATE, '{s} satisfaction {}'),
    'estate_tax_rate':              (ESTATE, '{s} tax rate {}'),
    'societal_value':               (VALUE, '{s} {}'),
    'produced_in_country':          (ECONOMY, '{s} produced {}'),
    'tolerance':                    (RELIGION, 'tolerance of {s} {}'),
    'modifier':                     (OTHER, '{s} {}'),
    'num_possible_estate_privileges': (PRIVILEGE, '{s} privilege slots {}'),
    'total_effective_building_levels': (GEO, '{s} levels {}'),
}
# …and the ones that open a scope instead of comparing a number.
SUBJECT_SCOPES = {
    'estate': '{s}', 'c': '{s}', 'character': '{s}', 'dynasty': 'the {s}',
    'situation': '{s}', 'region': '{s}', 'area': '{s}', 'province': '{s}',
    'international_organization': '{s}', 'var': 'the {s}', 'scope': '{s}',
    'location': '{s}', 'culture': '{s}', 'religion': '{s}',
}

# Values the game stores as a 0–1 fraction and shows as a percentage.
_PERCENT = {'estate_power', 'estate_satisfaction', 'estate_tax_rate',
            'religious_unity', 'complacency_percentage', 'manpower_percentage',
            'war_exhaustion_percentage', 'average_control_in_home_region',
            'location_population_percentage', 'rebel_progress',
            'percentage_to_meet_their_fate_on_calc'}

# Scope changes — recurse, prefixing what we say with whose scope it is.
_SCOPES = {
    'capital': 'capital', 'overlord': 'overlord', 'any_overlord_or_above': 'overlord',
    'leader_country': 'organization leader', 'market': 'market', 'owner': 'owner',
    'subject': 'subject', 'any_subject': 'a subject', 'any_neighbour': 'a neighbour',
    'ruler': 'ruler', 'heir': 'heir', 'country': None,
    'this': None, 'root': None, 'scope:actor': 'actor',
    'ruler_or_regent': 'ruler or regent', 'any_character': 'some character',
    'every_character': 'every character', 'any_rebel': 'a rebel army',
    'random_rebel': 'a rebel army', 'any_estate': 'some estate',
    'any_current_war': 'a war', 'any_character_in_dynasty': 'a dynasty member',
    'any_character_supporting_rebel': 'a rebel supporter',
    'any_location_in_province': 'a location in the province',
    'any_owned_location': 'an owned location',
    'any_country_with_capital_in_geography': 'a country based there',
    'any_coast_border_location': 'a bordering coastal location',
    'any_connected_location': 'a connected location',
    'any_child': 'a child', 'dynasty_head': 'the dynasty head',
    'province': 'province', 'location': 'location', 'owner': 'owner',
    'controller': 'controller', 'defender_leader': 'the defender',
    'attacker_leader': 'the attacker', 'revolutionary_target': 'its revolution target',
    'heir': 'heir', 'mother': 'mother', 'father': 'father',
    'original_capital': 'original capital', 'prev': None, 'from': None,
}
_COMBINATORS = {'AND', 'OR', 'NOT', 'NOR', 'NAND', 'all', 'any',
                'limit', 'hidden_trigger'}
_OPS = {'GREATER_THAN': '>', 'LESS_THAN': '<', 'GREATER_THAN_EQUAL': '≥',
        'LESS_THAN_EQUAL': '≤', 'NOT_EQUAL': '≠', 'value': '='}
# Sub-keys that only parameterise their parent block.
_PARAMS = {'type', 'group', 'value', 'text', 'target', 'who', 'scope'}

# `"estate_power(estate_type:crown_estate)"`, `societal_value:x`
_CALL_KEY = re.compile(r'^([a-z_]+)\(([a-z_]+):([a-z_0-9]+)\)$')
_QUAL_KEY = re.compile(r'^([a-z_]+):([A-Za-z_0-9.]+)$')


def _qualified(key: str):
    """A key that carries its own subject → (base, subject token)."""
    m = _CALL_KEY.match(key)
    if m:
        return m.group(1), m.group(3)
    m = _QUAL_KEY.match(key)
    if m:
        return m.group(1), m.group(2)
    return None


_TAG_PREFIX: set[str] | None = None


def _strip_tag_prefix(s: str) -> str:
    """`pol_casimir_iii_piast` → `casimir_iii_piast`. Character and dynasty
    script keys are tag-prefixed and the game never shows the tag."""
    global _TAG_PREFIX
    if _TAG_PREFIX is None:
        try:
            _TAG_PREFIX = {t.lower() for t in ref.parser.countries}
        except Exception:
            _TAG_PREFIX = set()
    head, _, rest = s.partition('_')
    return rest if rest and head in _TAG_PREFIX else s


_SELF = {'root': 'us', 'prev': 'it', 'this': 'it', 'from': 'them'}


def _label(v) -> str:
    """A script value → the game's display name where there is one."""
    s = str(v)
    if s.lower() in _SELF:
        return _SELF[s.lower()]
    if ':' in s:
        s = s.split(':', 1)[1]
    m = ref.label_map()
    if s in m:
        return m[s]
    txt = ref.plain_text(ref.parser.localize(s, default=''))
    if txt and txt != s:
        return txt
    if '.' in s:
        # a dotted read (`root.ruler.dynasty`) — whose what
        hops = [h for h in s.split('.') if h.lower() not in _SELF]
        return "'s ".join(h.replace('_', ' ') for h in hops) or 'us'
    return ref.pretty(_strip_tag_prefix(s))


def _loc(key: str) -> str | None:
    """A custom_tooltip's loc key → its sentence, if it resolves to one."""
    txt = ref.plain_text(ref.parser.localize(str(key), default=''))
    if not txt or txt == str(key):
        return None
    return txt.rstrip(': ').strip()


def _pretty_key(key: str) -> str:
    """`modifier:can_build_ships` / `num_of_ports` → readable English."""
    if ':' in key:
        key = key.split(':', 1)[1]
    return ref.pretty(key)


_DEFINES: dict[str, float] | None = None


def _define(name: str):
    """`HORDE_CIVIL_WAR_END_HORDE_UNITY` → its number."""
    global _DEFINES
    if _DEFINES is None:
        _DEFINES = {}
        try:
            for _group, tree in ref.parser.defines:
                for k, v in tree:
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        _DEFINES.setdefault(str(k), float(v))
        except Exception:
            pass
    return _DEFINES.get(str(name))


def _number(v):
    """A comparison operand → a number, resolving the game's own named
    constants (script values and defines) to what they stand for."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    try:
        return float(s)
    except ValueError:
        pass
    n = scriptvalue.constant(s)
    if n is None and s.isupper():
        n = _define(s)
    return n


def _fmt_number(n: float, key: str | None) -> str:
    if key in _PERCENT:
        pct = n * 100
        return f'{pct:g}%'
    return f'{n:g}'


def _operand(v, key: str | None) -> str:
    """The right-hand side of a comparison, as the player reads it."""
    s = str(v).strip().strip('"')
    if s.startswith('var:'):
        return scriptvalue.var_label(s)
    n = _number(v)
    if n is not None:
        return _fmt_number(n, key)
    # `"root.estate_power(estate_type:crown_estate)"` — a scope call standing
    # in for a number, not a name to look up
    if '(' in s or '.' in s:
        return scriptvalue.label_for(s)
    return _label(v)


def _cmp(block, key: str | None = None) -> str:
    """`{ GREATER_THAN = 0.66 }` → '> 66%'."""
    for k, v in block.iterate_with_duplicates():
        op = _OPS.get(str(k))
        if op and not hasattr(v, 'iterate_with_duplicates'):
            return f'{op} {_operand(v, key)}'
        if op:
            # compared against a whole value block (`> { value = … }`)
            lowered = scriptvalue.lower(v)
            return f'{op} {lowered["formula"]}'
    return ''


class _Pairs:
    """A walkable tree made from an explicit key/value list."""
    def __init__(self, pairs):
        self._pairs = list(pairs)

    def iterate_with_duplicates(self):
        yield from self._pairs


class _Pair(_Pairs):
    """One key/value as a walkable one-entry tree."""
    def __init__(self, k, v):
        super().__init__([(k, v)])


class _Walk:
    """A negated condition is an EXCLUSION, not a requirement. `NOT = {
    has_town_rights = fuero_juzgo }` means this right and Fuero Juzgo cannot
    both be held — reading that as "requires an urban right" made the facet
    useless and the sentence wrong. The two are kept apart, and only the
    positive side decides the tags and whether the thing is identity-locked.
    """

    def __init__(self, limit: int):
        self.lines: list[str] = []
        self.excludes: list[str] = []
        self.tags: set[str] = set()
        self.identity = False
        self.limit = limit
        self.dropped = 0
        self.inlining: list[str] = []

    # ── output ──────────────────────────────────────────────────────
    def add(self, tag: str, line: str | None, negate: bool, scope: str | None,
            key: str | None = None, mark_identity: bool = True):
        if tag is OTHER and key:
            FELL_THROUGH[key] += 1
        if not negate:
            self.tags.add(tag)
            if mark_identity and tag in IDENTITY and key not in ACQUIRABLE_PREDICATES:
                self.identity = True
        if line is None:
            return
        if scope:
            line = f'{scope}: {line}'
        bucket = self.excludes if negate else self.lines
        if line in bucket:
            return
        if len(bucket) >= self.limit:
            self.dropped += 1
            return
        bucket.append(line)

    def absorb(self, sub: '_Walk', negate: bool) -> None:
        """Merge a sub-walk's categories (its lines are handled by the caller)."""
        if not negate:
            self.tags |= sub.tags
            self.identity = self.identity or sub.identity

    def sub(self, tree, depth: int, scope: str | None = None) -> '_Walk':
        w = _Walk(self.limit)
        w.inlining = self.inlining
        w.walk(tree, depth, False, scope)
        return w

    def phrase(self, tree, depth: int, scope: str | None = None) -> str:
        """A whole block as one sentence, for an `if`'s condition."""
        w = self.sub(tree, depth, scope)
        parts = list(w.lines) + [_negated(x) for x in w.excludes]
        return ' and '.join(parts)

    # ── the walk ────────────────────────────────────────────────────
    def walk(self, tree, depth=0, negate=False, scope=None):
        if depth > 8 or not hasattr(tree, 'iterate_with_duplicates'):
            return
        for k, v in tree.iterate_with_duplicates():
            key = str(k)
            nested = hasattr(v, 'iterate_with_duplicates')

            if key in ('NOT', 'NOR', 'NAND'):
                self.walk(v, depth + 1, not negate, scope)
                continue
            if key in ('OR', 'any') and nested:
                self.either(v, depth, negate, scope)
                continue
            if key in _COMBINATORS:
                self.walk(v, depth + 1, negate, scope)
                continue
            if key in ('trigger_if', 'trigger_else_if') and nested:
                self.conditional(v, depth, negate, scope)
                continue
            if key == 'trigger_else' and nested:
                self.walk(v, depth + 1, negate, _join(scope, 'otherwise'))
                continue
            if key == 'switch' and nested:
                self.switch(v, depth, negate, scope)
                continue
            if key == 'custom_tooltip' or key == 'custom_description':
                self.custom_tooltip(v, depth, negate, scope)
                continue
            if key in _UNLOCK:
                tag, what = _UNLOCK[key]
                what_name = None
                if nested:
                    for k2, v2 in v.iterate_with_duplicates():
                        if str(k2) == 'type':
                            what_name = _label(v2)
                self.add(tag, f'the {what} has been unlocked'
                              + (f' ({what_name})' if what_name else ''), negate, scope, key)
                continue
            if key in _TYPED and nested:
                tag, phrase, sub_key = _TYPED[key]
                what = _block_get(v, sub_key)
                self.add(tag, phrase.format(_label(what) if what is not None else 'this'),
                         negate, scope, key)
                continue
            if key == 'had_disaster_for_years' and nested:
                self.add(DISASTER, self.disaster_years(v), negate, scope, key)
                continue
            if key in _PARAMS and not nested:
                continue

            if key == 'always':
                yes = val_yes(v)
                self.add(SCRIPTED, 'always' if yes else 'never', negate, scope, key)
                continue

            # a scripted trigger with no parameters — inline its body, which
            # is the only way `can_end = { x_end_trigger = yes }` says anything
            if not nested and key not in PREDICATES \
                    and self.inline(key, v, depth, negate, scope):
                continue

            qual = _qualified(key)
            if qual and self.qualified(qual, v, nested, depth, negate, scope):
                continue

            # a dotted read (`heir.mother`, `root.capital.province`): every hop
            # but the last is a scope, the last is the predicate
            if '.' in key and key not in PREDICATES:
                hops = [h for h in key.split('.') if h.lower() not in _SELF]
                if len(hops) > 1:
                    self.walk(_Pair(hops[-1], v), depth + 1, negate,
                              _join(scope, ' · '.join(h.replace('_', ' ') for h in hops[:-1])))
                    continue

            spec = PREDICATES.get(key)
            if nested:
                # `religion = { group = catholic }` / `capital = { region = x }`
                inner_group = None
                for k2, v2 in v.iterate_with_duplicates():
                    if str(k2) == 'group' and not hasattr(v2, 'iterate_with_duplicates'):
                        inner_group = _label(v2)
                if inner_group and spec:
                    self.add(spec[0], f'{key.replace("_", " ")} group is {inner_group}',
                             negate, scope, key)
                    continue
                # `religion_percentage_in_country = { religion = X value > 0 }`
                # — the comparison lives in a `value` sub-block and the other
                # scalar key names what is being measured.
                vblock = _block_get(v, 'value')
                if hasattr(vblock, 'iterate_with_duplicates'):
                    inner = _cmp(vblock, key)
                    if inner:
                        subj = next((_label(v2) for k2, v2 in v.iterate_with_duplicates()
                                     if str(k2) != 'value'
                                     and not hasattr(v2, 'iterate_with_duplicates')), None)
                        tag = spec[0] if spec else OTHER
                        phrase = spec[1] if spec else f'{_pretty_key(key)} {{}}'
                        line = phrase.format(inner)
                        self.add(tag, f'{subj} {line}' if subj else line, negate, scope, key)
                        continue
                comparison = _cmp(v, key)
                if comparison:
                    # `num_of_ports = { GREATER_THAN = 0 }`. Known predicate →
                    # its phrasing; unknown → the predicate's own name, never
                    # the bare operator.
                    if spec:
                        self.add(spec[0], spec[1].format(comparison), negate, scope, key)
                    else:
                        self.add(OTHER, f'{_pretty_key(key)} {comparison}', negate, scope, key)
                    continue
                if key in _SCOPES:
                    self.walk(v, depth + 1, negate, _join(scope, _SCOPES[key]))
                    continue
                if spec:
                    # `culture = { OR = { has_culture_group = … } }` — the outer
                    # key only says which category this is; prefixing the inner
                    # lines with it reads "culture is: culture group is French".
                    self.tags.add(spec[0])
                self.walk(v, depth + 1, negate, scope)
                continue

            val = str(v)
            if key in _OPS:      # a bare operator with no predicate to attach to
                continue
            if spec:
                tag, phrase = spec
                if '{}' in phrase:
                    n = _number(v) if not isinstance(v, str) or str(v).lstrip('-').replace('.', '', 1).isdigit() else None
                    if n is not None:
                        filled = f'= {_fmt_number(n, key)}'
                    elif '(' in str(v):
                        filled = _operand(v, key)
                    else:
                        filled = _label(v)
                    self.add(tag, phrase.format(filled), negate, scope, key)
                else:
                    # `in_civil_war = no` is the negation of its own phrase —
                    # the parser hands the boolean back as Python False.
                    self.add(tag, phrase, negate ^ (val in ('no', 'False')), scope, key)
            elif val in ('yes', 'no', 'True', 'False'):
                # the parser hands booleans back as Python True, not "yes"
                self.add(OTHER, _pretty_key(key), negate ^ (val in ('no', 'False')), scope, key)
            else:
                self.add(OTHER, f'{_pretty_key(key).lower()}: {_label(v)}', negate, scope, key)

    # ── pieces ──────────────────────────────────────────────────────
    def either(self, block, depth, negate, scope):
        """An OR reads as one sentence. Flattening it into separate lines
        turned "Poland or the Commonwealth" into two requirements, which is
        a different — and false — claim."""
        parts, tags = [], set()
        for k2, v2 in block.iterate_with_duplicates():
            w = self.sub(_Pair(k2, v2), depth + 1)
            self.absorb(w, negate)
            tags |= w.tags
            txt = ' and '.join(list(w.lines) + [_negated(x) for x in w.excludes])
            if txt and txt not in parts:
                parts.append(txt)
        if parts:
            self.add(_first_tag(tags), ' or '.join(parts), negate, scope,
                     mark_identity=False)

    def conditional(self, block, depth, negate, scope):
        """`trigger_if = { limit = { A } B }` is "if A then B", not "A and B"."""
        limit = _block_get(block, 'limit')
        rest = [(k, v) for k, v in block.iterate_with_duplicates() if str(k) != 'limit']
        cond = self.phrase(limit, depth + 1) if limit is not None else ''
        if not cond:
            self.walk(_Pairs(rest), depth + 1, negate, scope)
            return
        sub = self.sub(_Pairs(rest), depth + 1)
        self.absorb(sub, negate)
        tag = _first_tag(sub.tags)
        same = {cond, _negated(cond)}

        def where(line: str) -> str | None:
            # the body restates its own condition — the "if" adds nothing
            if line in same or _negated(line) in same:
                return scope
            return _join(scope, f'if {cond}')

        for ln in sub.lines:
            self.add(tag, ln, negate, where(ln), mark_identity=False)
        for ln in sub.excludes:
            self.add(tag, ln, not negate, where(ln), mark_identity=False)

    def switch(self, block, depth, negate, scope):
        """`switch = { trigger = current_age  age_3_x = { … } }`."""
        subject = _block_get(block, 'trigger')
        label = _pretty_key(str(subject)).lower() if subject is not None else 'it'
        for k, v in block.iterate_with_duplicates():
            if str(k) == 'trigger':
                continue
            self.walk(v, depth + 1, negate, _join(scope, f'when {label} is {_label(k)}'))

    def disaster_years(self, block) -> str:
        """`had_disaster_for_years = { disaster_type = x years >= 10 }`."""
        years = _block_get(block, 'years')
        what = _block_get(block, 'disaster_type')
        name = _label(what) if what is not None and 'scope:' not in str(what) else 'it'
        if hasattr(years, 'iterate_with_duplicates'):
            cmp_ = _cmp(years)
        else:
            cmp_ = f'≥ {years}'
        return f'{name} has been running {cmp_} years'

    def inline(self, key, value, depth, negate, scope) -> bool:
        """A scripted trigger used as a plain flag — walk its body in place.
        `can_end = { rise_of_the_szlachta_end_trigger = yes }` says nothing
        at all until this happens."""
        bodies = triggers._scripted()
        body = bodies.get(key)
        if body is None or key in self.inlining or len(self.inlining) > 6:
            return False
        val = str(value)
        if val not in ('yes', 'no', 'True', 'False'):
            return False
        yes = val in ('yes', 'True')
        self.inlining.append(key)
        try:
            self.walk(body, depth + 1, negate ^ (not yes), scope)
        finally:
            self.inlining.pop()
        return True

    def qualified(self, qual, value, nested, depth, negate, scope) -> bool:
        """`estate_power(estate_type:nobles_estate)`, `societal_value:x`,
        `c:DLH` — the subject is baked into the key."""
        base, subject = qual
        name = scriptvalue.subject_label(subject)
        spec = SUBJECT_PREDICATES.get(base)
        if spec:
            flag = str(value)
            if not nested and flag in ('yes', 'no', 'True', 'False'):
                self.add(spec[0], spec[1].format('', s=name).strip(),
                         negate ^ (flag in ('no', 'False')), scope, base)
                return True
            comparison = _cmp(value, base) if nested else f'= {_label(value)}'
            self.add(spec[0], spec[1].format(comparison, s=name), negate, scope, base)
            return True
        if base in SUBJECT_SCOPES and nested:
            if base == 'var':
                name = scriptvalue.var_label(subject)
            elif base == 'scope':
                name = subject.replace('_', ' ')
            # `var:hacw_hook_faction_power >= 10` compares, it does not scope
            comparison = _cmp(value, base)
            if comparison:
                self.add(SCRIPTED if base == 'var' else OTHER,
                         f'{name} {comparison}', negate, scope, base)
                return True
            self.walk(value, depth + 1, negate, _join(scope, SUBJECT_SCOPES[base].format(s=name)))
            return True
        return False

    def custom_tooltip(self, block, depth, negate, scope):
        """The game's own sentence for a condition it chose to phrase itself.
        Its own words win over a fallback rendering of the machinery inside,
        but never over conditions we can actually name."""
        if not hasattr(block, 'iterate_with_duplicates'):
            # `custom_tooltip = some_loc_key` — the whole condition is prose
            line = _loc(block)
            if line:
                self.add(SCRIPTED, line, negate, scope)
            return
        text = None
        rest = []
        for k, v in block.iterate_with_duplicates():
            if str(k) == 'text' and not hasattr(v, 'iterate_with_duplicates'):
                text = _loc(v)
            else:
                rest.append((k, v))
        w = self.sub(_Pairs(rest), depth + 1)
        # The machinery inside is worth showing only when we can name it: a
        # tooltip that lowers to nothing but "Other" lines is exactly the case
        # the game wrote its own sentence for.
        if (w.lines or w.excludes) and (w.tags - {OTHER} or not text):
            self.absorb(w, negate)
            tag = _first_tag(w.tags)
            for ln in w.lines:
                self.add(tag, ln, negate, scope, mark_identity=False)
            for ln in w.excludes:
                self.add(tag, ln, not negate, scope, mark_identity=False)
            return
        if text:
            self.add(SCRIPTED, text, negate, scope)


def val_yes(v) -> bool:
    return str(v) in ('yes', 'True')


# "has a parliament" is not negated by writing "no has a parliament".
_NEGATIONS = (('is ', 'is not '), ('has ', 'does not have '),
              ('runs ', 'does not run '), ('owns ', 'does not own '),
              ('leads ', 'does not lead '), ('rules ', 'does not rule '))


def _negated(line: str) -> str:
    for prefix, replacement in _NEGATIONS:
        if line.startswith(prefix):
            return replacement + line[len(prefix):]
    if ' is ' in line:
        return line.replace(' is ', ' is not ', 1)
    return f'not {line}'


negated = _negated          # public: builders phrase exclusions the same way


def _first_tag(tags) -> str:
    """The most identifying category present, in ORDER."""
    for t in ORDER:
        if t in tags:
            return t
    return OTHER


def _join(scope: str | None, extra: str | None) -> str | None:
    if not extra:
        return scope
    if not scope:
        return extra
    return f'{scope} · {extra}'


def _block_get(tree, want: str):
    """First value of `want` inside a block, or None."""
    try:
        for k, v in tree.iterate_with_duplicates():
            if str(k) == want:
                return v
    except AttributeError:
        pass
    return None


def describe(*trees, limit: int = 6) -> dict:
    """Trigger blocks → what a player needs to know.

    lines        positive conditions, in the game's terms
    excludes     conditions that must NOT hold (mutually exclusive things)
    tags         categories of the positive conditions, for faceting
    availability 'Any country' | 'Specific countries' — the one question
                 worth a chip: can I take this, or is it someone else's?
    """
    w = _Walk(limit)
    for t in trees:
        w.walk(t)
    tags = sorted(w.tags, key=lambda t: ORDER.index(t) if t in ORDER else 99)
    lines = list(w.lines)
    if w.dropped:
        lines.append(f'+{w.dropped} more')
    # An exclusion reads under a "Conflicts with" heading, where the verb is
    # already implied: "has urban right Fuero Juzgo" → "urban right Fuero Juzgo".
    excludes = [x[4:] if x.startswith('has ') else x for x in w.excludes]
    return {
        'lines': lines,
        'excludes': excludes,
        # the same conditions as whole sentences, for callers that phrase the
        # negation inline rather than under a "Conflicts with" heading
        'excludes_full': [negated(x) for x in w.excludes],
        'tags': tags or [NONE],
        'availability': SOME_COUNTRIES if w.identity else ANY_COUNTRY,
    }
