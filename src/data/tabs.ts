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
    summary: 'Every playable country at the 1337 start, with its culture, religion, government and difficulty.',
    willContain: [
      'A browser over about 2,200 countries, filtered by region, culture or religion.',
      'A page per country with its unique advances, units and formables.',
    ],
  },
  {
    slug: 'formables', icon: '🛠️', label: 'Formable Countries', section: 'Countries',
    status: 'built',
    summary: 'What each formable country requires, and what you get for forming it.',
  },
  {
    slug: 'country-ranks', icon: '🏅', label: 'Country Ranks', section: 'Countries',
    status: 'built',
    summary: 'The rank tiers, the hegemons, and what each rank unlocks.',
  },

  // ── Ages & Advances ───────────────────────────────────────────────
  {
    slug: 'advances', icon: '🔬', label: 'Advances', section: 'Ages & Advances',
    status: 'built',
    summary: 'The whole advance tree, age by age, with costs, prerequisites and unlocks.',
    willContain: [
      'About 3,000 advances across 7 ages, including the national and cultural branches.',
      'A layered tree layout worked out at build time.',
    ],
  },
  {
    slug: 'ages', icon: '⏳', label: 'Ages', section: 'Ages & Advances',
    status: 'built',
    summary: 'The seven ages, what each one unlocks, and how the game moves from one to the next.',
  },
  {
    slug: 'focuses', icon: '🔀', label: 'Age Focuses', section: 'Ages & Advances',
    status: 'built',
    summary: 'The administrative, diplomatic and military focus you pick at each age start, side by side.',
  },
  {
    slug: 'institutions', icon: '💡', label: 'Institutions', section: 'Ages & Advances',
    status: 'built',
    summary: 'How each institution spawns and how it spreads.',
  },

  // ── Government & Laws ─────────────────────────────────────────────
  {
    slug: 'government', icon: '🏛️', label: 'Government', section: 'Government & Laws',
    status: 'built',
    summary: 'Government types and the reforms each one can take.',
  },
  {
    slug: 'laws', icon: '⚖️', label: 'Laws & Policies', section: 'Government & Laws',
    status: 'built',
    summary: 'Every law group and the policies you can select in it, by government and religion.',
  },
  {
    slug: 'estates', icon: '🏰', label: 'Estates & Privileges', section: 'Government & Laws',
    status: 'built',
    summary: 'The estates, their privileges, and what granting one does to your country.',
  },
  {
    slug: 'parliament', icon: '🗳️', label: 'Parliament', section: 'Government & Laws',
    status: 'built',
    summary: 'Parliament types, the issues they raise, and the agendas you can push.',
  },
  {
    slug: 'cabinet', icon: '📜', label: 'Cabinet', section: 'Government & Laws',
    status: 'built',
    summary: 'Cabinet actions, regencies, and how an heir is chosen.',
  },
  {
    slug: 'societal-values', icon: '🧭', label: 'Societal Values', section: 'Government & Laws',
    status: 'built',
    summary: 'Each societal value slider and what pushes it either way.',
  },

  // ── Economy ───────────────────────────────────────────────────────
  {
    slug: 'goods', icon: '📦', label: 'Goods', section: 'Economy',
    status: 'built',
    summary: 'Every trade good, with its price, category, pop demand and modifiers.',
  },
  {
    slug: 'buildings', icon: '🏗️', label: 'Buildings', section: 'Economy',
    status: 'built',
    summary: 'All 430 or so buildings, with production methods, employment and build conditions.',
    willContain: [
      'Production methods, with the goods each building takes in and puts out.',
      'Unique and cultural buildings marked as such.',
    ],
  },
  {
    slug: 'towns', icon: '🏘️', label: 'Towns & Settlements', section: 'Economy',
    status: 'built',
    summary: 'Location ranks, town rights, and how a settlement grows.',
  },
  {
    slug: 'urban-rights', icon: '🏙️', label: 'Urban Rights', section: 'Economy',
    status: 'built',
    summary: 'Every urban right, what it does to the location and the country, and who may grant it.',
  },


  // ── Society ───────────────────────────────────────────────────────
  {
    slug: 'pops', icon: '👥', label: 'Pops', section: 'Society',
    status: 'built',
    summary: 'The pop types, what they need, and what they demand.',
  },
  {
    slug: 'cultures', icon: '🎭', label: 'Cultures', section: 'Society',
    status: 'built',
    summary: 'Culture groups, cultures, languages, and works of art.',
  },
  {
    slug: 'religions', icon: '🕌', label: 'Religions', section: 'Society',
    status: 'built',
    summary: 'Religions, aspects, schools, focuses, and holy sites.',
  },
  {
    slug: 'characters', icon: '👤', label: 'Characters', section: 'Society',
    status: 'built',
    summary: 'Traits, educations, interactions, and chivalric orders.',
  },

  // ── Military ──────────────────────────────────────────────────────
  {
    slug: 'units', icon: '⚔️', label: 'Units', section: 'Military',
    status: 'built',
    summary: 'Land and naval unit types by age, and the regional unique units.',
  },
  {
    slug: 'levies', icon: '🛡️', label: 'Levies & Recruitment', section: 'Military',
    status: 'built',
    summary: 'Levy compositions and recruitment methods.',
  },
  {
    slug: 'warfare', icon: '🎯', label: 'Warfare', section: 'Military',
    status: 'built',
    summary: 'Casus belli, war goals, peace treaties, and the rules for joining a war.',
  },

  // ── Diplomacy ─────────────────────────────────────────────────────
  {
    slug: 'subjects', icon: '🤝', label: 'Subjects', section: 'Diplomacy',
    status: 'built',
    summary: 'Every subject type, what it pays you, and how you integrate it.',
  },
  {
    slug: 'international-organizations', icon: '🌐', label: 'International Organizations', section: 'Diplomacy',
    status: 'built',
    summary: 'The HRE, the Papacy, and every other international organization, with their laws, statuses and payments.',
  },
  {
    slug: 'diplomatic-actions', icon: '🕊️', label: 'Diplomatic Actions', section: 'Diplomacy',
    status: 'built',
    summary: 'Country interactions, what they cost, insults, and how rivals are picked.',
  },

  // ── World ─────────────────────────────────────────────────────────
  {
    slug: 'map', icon: '🗺️', label: 'Map', section: 'World',
    status: 'built',
    summary: 'The 1337 world painted by trade good, culture, religion, terrain or climate.',
  },
  {
    slug: 'locations', icon: '📍', label: 'Locations', section: 'World',
    status: 'built',
    summary: 'All 22,864 land locations, with trade good, terrain and culture makeup.',
  },
  {
    slug: 'terrain', icon: '⛰️', label: 'Terrain & Climate', section: 'World',
    status: 'built',
    summary: 'Climate, topography and vegetation modifiers.',
  },
  {
    slug: 'situations', icon: '🌋', label: 'Situations & Diseases', section: 'World',
    status: 'built',
    summary: 'Struggles and diseases, with their triggers, phases and resolutions.',
  },
  {
    slug: 'disasters', icon: '🔥', label: 'Disasters', section: 'World',
    status: 'built',
    summary: 'Every disaster, what starts it, what it does, and every way out.',
  },
  {
    slug: 'missions', icon: '📌', label: 'Missions', section: 'World',
    status: 'built',
    summary: 'The 11 generic mission packs and their tasks. EU5 has no national mission trees.',
  },

  {
    slug: 'events', icon: '📜', label: 'Events', section: 'World',
    status: 'built',
    summary: 'Every narrative event, its options, its rewards, and who it fires for.',
  },

  // ── Concepts ──────────────────────────────────────────────────────
  {
    slug: 'concepts', icon: '📖', label: 'Concepts', section: 'Concepts',
    status: 'built',
    summary: 'The in-game encyclopedia, with every game concept linked to the rest of the site.',
  },
  {
    slug: 'defines', icon: '🔢', label: 'Defines', section: 'Concepts',
    status: 'built',
    summary: 'The engine constants behind the formulas, grouped and annotated.',
  },

  // ── Tools ─────────────────────────────────────────────────────────
  {
    slug: 'production-calculator', icon: '🧮', label: 'Production Calculator', section: 'Tools',
    status: 'placeholder',
    summary: 'Pick a building, a production method and prices, then see the goods in, the goods out and the profit.',
  },
  {
    slug: 'values-planner', icon: '⚖️', label: 'Values Planner', section: 'Tools',
    status: 'built',
    summary: 'Pick laws, reforms and privileges, then see where your societal values drift and what that unlocks.',
  },
  {
    slug: 'value-path', icon: '🧗', label: 'Value Path', section: 'Tools',
    status: 'built',
    summary: 'Put your societal value targets in order and see what to enact at each stage.',
  },
  {
    slug: 'building-calculator', icon: '🧮', label: 'Building Calculator', section: 'Tools',
    status: 'built',
    summary: 'Goods in against goods out for each production method, at prices you set.',
  },
  {
    slug: 'advance-planner', icon: '🧭', label: 'Advance Planner', section: 'Tools',
    status: 'built',
    summary: 'Pick the advances you want and see every prerequisite and the total cost.',
  },
  {
    slug: 'battle-simulator', icon: '⚔️', label: 'Battle Simulator', section: 'Tools',
    status: 'built',
    summary: 'Build two armies, pick the terrain, and run the battle many times over.',
  },
  {
    slug: 'unlock-search', icon: '🔓', label: 'What Unlocks…', section: 'Tools',
    status: 'placeholder',
    summary: 'Find the advance, law or reform that unlocks a given thing.',
  },
  {
    slug: 'patch-notes', icon: '🛠️', label: 'Patch Notes', section: 'Tools',
    status: 'built',
    summary: 'The data changes the pipeline found in each patch.',
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
