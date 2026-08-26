// Catalog of every reference page. Drives the index, header nav, and the
// generic placeholder route. Same pattern as owreference: adding a page =
// add/promote an entry here; nav and index pick it up automatically.

export type TabStatus = 'built' | 'placeholder' | 'skipped';

export interface Tab {
  slug: string;
  label: string;
  icon: string;            // emoji page mark
  section: string;
  status: TabStatus;
  summary: string;
  willContain?: string[];
}

export const TABS: Tab[] = [
  // ── Countries ─────────────────────────────────────────────────────
  {
    slug: 'countries', icon: '👑', label: 'Countries', section: 'Countries',
    status: 'built',
    summary: 'Every playable tag at 1337 — culture, religion, government, difficulty',
    willContain: [
      'Browser over ~2,200 tags, filterable by region / culture / religion',
      'Country detail pages with unique advances, units, and formables',
    ],
  },
  {
    slug: 'formables', icon: '🛠️', label: 'Formable Countries', section: 'Countries',
    status: 'built',
    summary: 'Formation requirements and rewards for every formable tag',
  },
  {
    slug: 'country-ranks', icon: '🏅', label: 'Country Ranks', section: 'Countries',
    status: 'built',
    summary: 'Rank tiers, hegemons, and what each rank unlocks',
  },

  // ── Ages & Advances ───────────────────────────────────────────────
  {
    slug: 'advances', icon: '🔬', label: 'Advances', section: 'Ages & Advances',
    status: 'built',
    summary: 'The full advance tree, age by age — costs, prerequisites, unlocks',
    willContain: [
      '~3,000 advances across 7 ages, incl. national/cultural branches',
      'Layered tree layout precomputed at build time',
    ],
  },
  {
    slug: 'ages', icon: '⏳', label: 'Ages', section: 'Ages & Advances',
    status: 'built',
    summary: 'The seven ages — objectives, mechanics unlocked, age transitions',
  },
  {
    slug: 'institutions', icon: '💡', label: 'Institutions', section: 'Ages & Advances',
    status: 'built',
    summary: 'Spawn conditions and spread mechanics for each institution',
  },

  // ── Government & Laws ─────────────────────────────────────────────
  {
    slug: 'government', icon: '🏛️', label: 'Government', section: 'Government & Laws',
    status: 'built',
    summary: 'Government types and reforms',
  },
  {
    slug: 'laws', icon: '⚖️', label: 'Laws & Policies', section: 'Government & Laws',
    status: 'built',
    summary: 'Every law group and its policies, by government and religion',
  },
  {
    slug: 'estates', icon: '🏰', label: 'Estates & Privileges', section: 'Government & Laws',
    status: 'built',
    summary: 'The estates, their privileges, and equilibrium effects',
  },
  {
    slug: 'parliament', icon: '🗳️', label: 'Parliament', section: 'Government & Laws',
    status: 'built',
    summary: 'Parliament types, issues, and agendas',
  },
  {
    slug: 'cabinet', icon: '📜', label: 'Cabinet', section: 'Government & Laws',
    status: 'built',
    summary: 'Cabinet actions, regencies, and heir selection',
  },
  {
    slug: 'societal-values', icon: '🧭', label: 'Societal Values', section: 'Government & Laws',
    status: 'built',
    summary: 'The value sliders and what moves them',
  },

  // ── Economy ───────────────────────────────────────────────────────
  {
    slug: 'goods', icon: '📦', label: 'Goods', section: 'Economy',
    status: 'built',
    summary: 'Every trade good — price, category, pop demand, and modifiers',
  },
  {
    slug: 'buildings', icon: '🏗️', label: 'Buildings', section: 'Economy',
    status: 'built',
    summary: 'All ~430 buildings with production methods, employment, and gates',
    willContain: [
      'Production methods: inputs → outputs per building',
      'Unique/cultural buildings badged',
    ],
  },
  {
    slug: 'towns', icon: '🏘️', label: 'Towns & Settlements', section: 'Economy',
    status: 'built',
    summary: 'Location ranks, town rights, and settlement growth',
  },

  // ── Society ───────────────────────────────────────────────────────
  {
    slug: 'pops', icon: '👥', label: 'Pops', section: 'Society',
    status: 'built',
    summary: 'Pop types, needs, and demand',
  },
  {
    slug: 'cultures', icon: '🎭', label: 'Cultures', section: 'Society',
    status: 'built',
    summary: 'Culture groups, cultures, languages, and works of art',
  },
  {
    slug: 'religions', icon: '🕌', label: 'Religions', section: 'Society',
    status: 'built',
    summary: 'Religions, aspects, schools, focuses, and holy sites',
  },
  {
    slug: 'characters', icon: '👤', label: 'Characters', section: 'Society',
    status: 'built',
    summary: 'Traits, educations, interactions, and chivalric orders',
  },

  // ── Military ──────────────────────────────────────────────────────
  {
    slug: 'units', icon: '⚔️', label: 'Units', section: 'Military',
    status: 'built',
    summary: 'Land and naval unit types by age, plus regional uniques',
  },
  {
    slug: 'levies', icon: '🛡️', label: 'Levies & Recruitment', section: 'Military',
    status: 'built',
    summary: 'Levy compositions and recruitment methods',
  },
  {
    slug: 'warfare', icon: '🎯', label: 'Warfare', section: 'Military',
    status: 'built',
    summary: 'Casus belli, war goals, peace treaties, and join-war rules',
  },

  // ── Diplomacy ─────────────────────────────────────────────────────
  {
    slug: 'subjects', icon: '🤝', label: 'Subjects', section: 'Diplomacy',
    status: 'built',
    summary: 'Subject types — stances, payments, and integration',
  },
  {
    slug: 'international-organizations', icon: '🌐', label: 'International Organizations', section: 'Diplomacy',
    status: 'built',
    summary: 'The HRE, the Papacy, and every other IO — laws, statuses, payments',
  },
  {
    slug: 'diplomatic-actions', icon: '🕊️', label: 'Diplomatic Actions', section: 'Diplomacy',
    status: 'built',
    summary: 'Country interactions, costs, insults, and rival criteria',
  },

  // ── World ─────────────────────────────────────────────────────────
  {
    slug: 'map', icon: '🗺️', label: 'Map', section: 'World',
    status: 'placeholder',
    summary: 'Continents → regions → areas → provinces, with a location index',
  },
  {
    slug: 'locations', icon: '📍', label: 'Locations', section: 'World',
    status: 'built',
    summary: 'All 22,864 land locations — trade good, terrain, culture makeup',
  },
  {
    slug: 'terrain', icon: '⛰️', label: 'Terrain & Climate', section: 'World',
    status: 'built',
    summary: 'Climate, topography, and vegetation modifiers',
  },
  {
    slug: 'situations', icon: '🌋', label: 'Situations & Disasters', section: 'World',
    status: 'built',
    summary: 'Struggles, disasters, and diseases — triggers, phases, resolutions',
  },
  {
    slug: 'missions', icon: '📌', label: 'Missions', section: 'World',
    status: 'built',
    summary: 'The 11 generic mission packs and their tasks (EU5 has no national mission trees)',
  },

  {
    slug: 'events', icon: '📜', label: 'Events', section: 'World',
    status: 'built',
    summary: 'Every narrative event — options, rewards, and who it fires for',
  },

  // ── Concepts ──────────────────────────────────────────────────────
  {
    slug: 'concepts', icon: '📖', label: 'Concepts', section: 'Concepts',
    status: 'built',
    summary: 'The in-game encyclopedia — every game concept, auto-linked',
  },
  {
    slug: 'defines', icon: '🔢', label: 'Defines', section: 'Concepts',
    status: 'built',
    summary: 'Engine constants behind the formulas, grouped and annotated',
  },

  // ── Tools ─────────────────────────────────────────────────────────
  {
    slug: 'production-calculator', icon: '🧮', label: 'Production Calculator', section: 'Tools',
    status: 'placeholder',
    summary: 'Building + method + prices → goods in/out and profitability',
  },
  {
    slug: 'advance-planner', icon: '🧭', label: 'Advance Planner', section: 'Tools',
    status: 'built',
    summary: 'Pick target advances → the full prerequisite closure and cost',
  },
  {
    slug: 'unlock-search', icon: '🔓', label: 'What Unlocks…', section: 'Tools',
    status: 'placeholder',
    summary: 'Reverse index: find the advance/law/reform that unlocks anything',
  },
  {
    slug: 'patch-notes', icon: '🛠️', label: 'Patch Notes', section: 'Tools',
    status: 'built',
    summary: 'Per-patch data changes detected by the pipeline',
  },
];

export const SECTIONS = [
  'Countries',
  'Ages & Advances',
  'Government & Laws',
  'Economy',
  'Society',
  'Military',
  'Diplomacy',
  'World',
  'Concepts',
  'Tools',
] as const;
