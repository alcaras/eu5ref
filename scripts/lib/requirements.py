"""Trigger block → readable requirement lines + facet tags.

Privileges, laws, law policies and government reforms are all gated the same
way: a `potential` (who ever sees it) and an `allow` (who may take it), whose
predicates are the "additional requirements" a player actually needs to know
about. The toolkit hands those blocks back as raw Trees and models none of
their meaning, so this module renders them.

Two outputs per block:
  lines — readable strings, the game's own phrasing where it has one
  tags  — coarse categories, for faceting ("Religion", "Advance", …)

Honest fallback, as everywhere else on this site: a predicate we do not know
is still rendered (prettified) and tagged "Other" rather than dropped, so the
page never silently claims a gated thing is free.
"""
import ref

# ── categories ─────────────────────────────────────────────────────────
COUNTRY, GOV, RELIGION, CULTURE, GEO = 'Country', 'Government', 'Religion', 'Culture', 'Geography'
AGE, INSTITUTION, ADVANCE = 'Age', 'Institution', 'Advance'
LAW, REFORM, PRIVILEGE, ESTATE = 'Law', 'Reform', 'Privilege', 'Estate'
URBAN = 'Urban right'
ORG, SCRIPTED, ECONOMY, OTHER = 'Organization', 'Event or script', 'Economy', 'Other'
NONE = 'No requirement'

ORDER = [COUNTRY, GOV, RELIGION, CULTURE, GEO, AGE, INSTITUTION, ADVANCE,
         LAW, REFORM, PRIVILEGE, URBAN, ESTATE, ORG, ECONOMY, SCRIPTED, OTHER, NONE]

# Does a condition say WHO you must be (nobody can change their tag, culture,
# religion or capital region on a whim), or only WHAT you must have done?
# Only a POSITIVE identity condition narrows the field: "not a Steppe Horde"
# still leaves the reform open to almost everyone, so it does not count.
IDENTITY = {COUNTRY, GOV, RELIGION, CULTURE, GEO}
# …except the geography predicates that are about what you hold, not who you
# are — a port can be conquered, a capital's region cannot.
ACQUIRABLE_PREDICATES = {'owns', 'num_of_ports', 'is_coastal', 'is_port',
                         'has_building', 'location_rank', 'is_produced_in_market'}
ANY_COUNTRY = 'Any country'
SOME_COUNTRIES = 'Specific countries'

# predicate → (category, phrasing). {} is filled with the resolved value.
PREDICATES = {
    'has_or_had_tag':               (COUNTRY, 'is or was {}'),
    'tag':                          (COUNTRY, 'is {}'),
    'exists':                       (COUNTRY, '{} exists'),
    'dynasty':                      (COUNTRY, 'ruling dynasty is {}'),
    'is_frankokratia_state':        (COUNTRY, 'is a Frankokratia state'),

    'government_type':              (GOV, 'government is {}'),
    'has_tribal_government':        (GOV, 'has a tribal government'),
    'country_type':                 (GOV, 'country type is {}'),
    'is_subject_type':              (GOV, 'is a {}'),
    'parliament_type':              (GOV, 'parliament is {}'),
    'has_parliament':               (GOV, 'has a parliament'),
    'is_subject':                   (GOV, 'is a subject'),
    'is_independent':               (GOV, 'is independent'),

    'religion':                     (RELIGION, 'religion is {}'),
    'religion.group':               (RELIGION, 'religion group is {}'),
    'religious_unity':              (RELIGION, 'religious unity {}'),
    'has_religious_school':         (RELIGION, 'religious school is {}'),

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
    'has_slavery':                  (ESTATE, 'has slavery'),

    'is_member_of_international_organization': (ORG, 'is a member of {}'),
    'is_leader_of_international_organization': (ORG, 'leads {}'),
    'international_organization_type':         (ORG, 'organization is {}'),
    'international_organization_has_law':      (ORG, 'the organization has law {}'),
    'international_organization_has_policy':   (ORG, 'the organization runs {}'),

    'gold':                         (ECONOMY, 'treasury {}'),
    'monthly_income':               (ECONOMY, 'monthly income {}'),
    'is_produced_in_market':        (ECONOMY, 'market produces {}'),
    'has_currency_to_vote_for_law': (ECONOMY, 'can pay to vote for the law'),

    'has_variable':                 (SCRIPTED, 'event flag: {}'),
    'mechanic':                     (SCRIPTED, 'mechanic: {}'),
    'has_cooldown':                 (SCRIPTED, 'off cooldown: {}'),
    'is_situation_active':          (SCRIPTED, 'situation active: {}'),
    'hre_allowed_emperor_reform_proposal': (ORG, 'the Emperor may propose this reform'),
    'hre_has_enabled_all_imperial_laws':   (ORG, 'all imperial laws are enabled'),
    'hre_can_select_adjacent_reform_level': (ORG, 'the next reform level is reachable'),
    'celestial_authority':          (GOV, 'celestial authority {}'),
    'crown_power':                  (GOV, 'crown power {}'),
    'legitimacy':                   (GOV, 'legitimacy {}'),
    'stability':                    (GOV, 'stability {}'),
    'is_at_war':                    (GOV, 'is at war'),
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

# Scope changes — recurse, prefixing what we say with whose scope it is.
_SCOPES = {
    'capital': 'capital', 'overlord': 'overlord', 'any_overlord_or_above': 'overlord',
    'leader_country': 'organization leader', 'market': 'market', 'owner': 'owner',
    'subject': 'subject', 'any_subject': 'a subject', 'any_neighbour': 'a neighbour',
    'ruler': 'ruler', 'heir': 'heir', 'country': None,
    'this': None, 'root': None, 'scope:actor': 'actor',
}
_COMBINATORS = {'AND', 'OR', 'NOT', 'NOR', 'NAND', 'all', 'any',
                'trigger_if', 'trigger_else', 'trigger_else_if', 'limit',
                'hidden_trigger'}
_OPS = {'GREATER_THAN': '>', 'LESS_THAN': '<', 'GREATER_THAN_EQUAL': '≥',
        'LESS_THAN_EQUAL': '≤', 'NOT_EQUAL': '≠', 'value': '='}
# Sub-keys that only parameterise their parent block.
_PARAMS = {'type', 'group', 'value', 'text', 'target', 'who', 'scope'}


def _label(v) -> str:
    """A script value → the game's display name where there is one."""
    s = str(v)
    if ':' in s:
        s = s.split(':', 1)[1]
    m = ref.label_map()
    return m.get(s) or ref.plain_text(ref.parser.localize(s, default='')) or ref.pretty(s)


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


def _cmp(block) -> str:
    """`{ GREATER_THAN = 0.66 }` → '> 0.66'."""
    for k, v in block.iterate_with_duplicates():
        op = _OPS.get(str(k))
        if op and not hasattr(v, 'iterate_with_duplicates'):
            return f'{op} {v}'
    return ''


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

    def add(self, tag: str, line: str | None, negate: bool, scope: str | None,
            key: str | None = None):
        if not negate:
            self.tags.add(tag)
            if tag in IDENTITY and key not in ACQUIRABLE_PREDICATES:
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

    def walk(self, tree, depth=0, negate=False, scope=None):
        if depth > 6 or not hasattr(tree, 'iterate_with_duplicates'):
            return
        for k, v in tree.iterate_with_duplicates():
            key = str(k)
            nested = hasattr(v, 'iterate_with_duplicates')

            if key in ('NOT', 'NOR', 'NAND'):
                self.walk(v, depth + 1, not negate, scope)
                continue
            if key in _COMBINATORS:
                self.walk(v, depth + 1, negate, scope)
                continue
            if key == 'custom_tooltip':
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
            if key in _PARAMS and not nested:
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
                comparison = _cmp(v)
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
                    self.walk(v, depth + 1, negate, _SCOPES[key] or scope)
                    continue
                if spec:
                    self.tags.add(spec[0])
                self.walk(v, depth + 1, negate, scope)
                continue

            val = str(v)
            if key in _OPS:      # a bare operator with no predicate to attach to
                continue
            if spec:
                tag, phrase = spec
                self.add(tag, phrase.format(_label(v)) if '{}' in phrase else phrase,
                         negate, scope, key)
            elif val in ('yes', 'no', 'True', 'False'):
                # the parser hands booleans back as Python True, not "yes"
                self.add(OTHER, _pretty_key(key), negate ^ (val in ('no', 'False')), scope, key)
            else:
                self.add(OTHER, f'{_pretty_key(key).lower()}: {_label(v)}', negate, scope, key)

    def custom_tooltip(self, block, depth, negate, scope):
        """The game's own sentence for a condition it chose to phrase itself."""
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
        before = len(self.lines) + len(self.excludes)
        for k, v in rest:
            self.walk(_Pair(k, v), depth + 1, negate, scope)
        if text and len(self.lines) + len(self.excludes) == before:
            self.add(SCRIPTED, text, negate, scope)


class _Pair:
    """One key/value as a walkable one-entry tree."""
    def __init__(self, k, v):
        self._k, self._v = k, v

    def iterate_with_duplicates(self):
        yield self._k, self._v


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
    return {
        'lines': lines,
        'excludes': list(w.excludes),
        'tags': tags or [NONE],
        'availability': SOME_COUNTRIES if w.identity else ANY_COUNTRY,
    }
