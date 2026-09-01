// The country-facts model every gated tool shares.
//
// A gate is the compiled `potential` of an advance, law, reform, privilege…
// (scripts/lib/triggers.py): a boolean expression over FACTS about a
// country. Facts come in two shapes —
//
//   one  — exactly one value, always known once a country is picked:
//          culture (+ its groups and language), religion (+ group), the
//          capital's geography tiers, government type, subject status.
//   set  — acquirable things: a reform taken, an estate present, an IO
//          joined, a culture unified, a DLC owned, a scripted condition met.
//          Unknown until asserted: `facts[kind][atom]` is true, false, or
//          absent (= unknown → the gate stays conditional).
//
// Evaluation is three-valued: TRUE = yours, FALSE = another country's,
// null = conditional. Only a definite FALSE hides anything — nothing
// acquirable is ever silently dropped.
//
// Where the facts come from, later layers overriding earlier ones:
//   1337 setup (public/planner.json countries / country-start.json)
//   ⊕ an imported save's snapshot (src/lib/save-import.ts)
//   ⊕ the player's overrides on the page (carried in the URL — links share
//     facts, never the save)

export type Gate = any[] | null | undefined;
export type SetFacts = Record<string, boolean>;

export type Facts = {
  tag?: string;
  cul?: string; cgrp?: string[]; lang?: string;
  rel?: string; rgrp?: string;
  cap?: Record<string, string | null | undefined>;
  gov?: string; subj?: string; parl?: string; ctype?: string;
  /** current age key (age_3_discovery) — for `current_age` gates */
  age?: string;
  // set kinds
  mcg?: SetFacts; reform?: SetFacts; estate?: SetFacts; iomem?: SetFacts;
  axis?: SetFacts; dlc?: SetFacts; law?: SetFacts; priv?: SetFacts;
  policy?: SetFacts; var?: SetFacts; adv?: SetFacts; unl?: SetFacts;
  '?'?: SetFacts;
};

/** The vocabulary a page offers, as emitted by build_planner.py `kinds`. */
export type KindValue = { v: string; l: string; n: number; p?: string; f?: Record<string, any> };
export type KindDef = { k: string; l: string; mode: 'one' | 'set'; values: KindValue[] };

export const ONE_KINDS = ['cul', 'rel', 'cap', 'gov', 'subj', 'parl', 'ctype', 'age'] as const;
export const SET_KINDS = ['mcg', 'reform', 'estate', 'iomem', 'axis', 'dlc', 'law', 'priv',
  'policy', 'var', 'adv', 'unl', '?'] as const;

const isSetKind = (k: string) => (SET_KINDS as readonly string[]).includes(k);

const ageNum = (key: string | undefined) => {
  const m = /age_(\d+)/.exec(key || '');
  return m ? parseInt(m[1], 10) : null;
};

/** Three-valued gate evaluation. `formables` is tag → gate (null = anyone
 *  with the land can form it) — a formable's tag is reachable, so a gate on
 *  it is conditional rather than false. */
export function evalGate(e: Gate, f: Facts, formables: Record<string, any> = {},
                         forming: string[] = []): boolean | null {
  if (!e) return true;
  const h = e[0];
  if (h === 'and') {
    let unk = false;
    for (const s of e.slice(1)) { const v = evalGate(s, f, formables, forming); if (v === false) return false; if (v === null) unk = true; }
    return unk ? null : true;
  }
  if (h === 'or') {
    let unk = false;
    for (const s of e.slice(1)) { const v = evalGate(s, f, formables, forming); if (v === true) return true; if (v === null) unk = true; }
    return unk ? null : false;
  }
  if (h === 'not') { const v = evalGate(e[1], f, formables, forming); return v === null ? null : !v; }
  if (h === 'true') return true;
  if (h === 'false') return false;
  if (h === 'tag') {
    // Your own tag, yes. A formable's tag is reachable, so unknown. Any
    // other country's tag you simply cannot become — false, not
    // "conditional", or the planner would suggest becoming Portugal.
    if (!f.tag) return null;
    if (f.tag === e[1]) return true;
    if (!(e[1] in formables)) return false;
    // A formation gate that names its own tag (or one up the chain) is
    // asking "are you already it" of the country about to form — no.
    if (forming.includes(e[1])) return false;
    const v = evalGate(formables[e[1]], f, formables, [...forming, e[1]]);
    return v === false ? false : null;
  }
  if (h === 'cap') { const c = f.cap; if (!c || c[e[1]] == null) return null; return c[e[1]] === e[2]; }
  if (h === 'cgrp') return f.cgrp ? f.cgrp.includes(e[1]) : null;
  if (h === 'cul' || h === 'lang' || h === 'rel' || h === 'rgrp' || h === 'gov' ||
      h === 'subj' || h === 'parl' || h === 'ctype') {
    const v = (f as any)[h];
    return v == null ? null : v === e[1];
  }
  if (h === 'age') { const a = ageNum(f.age), b = ageNum(e[1]); return a == null || b == null ? null : a === b; }
  if (h === 'age>=') { const a = ageNum(f.age), b = ageNum(e[1]); return a == null || b == null ? null : a >= b; }
  if (h === 'mrep') return f.gov == null ? null : f.gov === 'republic' ? null : false;
  if (h === 'iotype') return false;                 // a country is not an organization
  if (h === '?') { const s = f['?']; return s && e[1] in s ? s[e[1]] : null; }
  if (isSetKind(h)) { const s = (f as any)[h] as SetFacts | undefined; return s && e[1] in s ? s[e[1]] : null; }
  return null;
}

export type Literal = { kind: string; v: string; label?: string; value: boolean | null };

/** Every leaf a gate tests, with how it currently evaluates — the tooltip
 *  lists the unknown ones with an "assume ✓" action. Labels come from the
 *  node's `gl` triples when given. */
export function literals(e: Gate, f: Facts, formables: Record<string, any> = {},
                         labels?: Record<string, string>, into: Literal[] = []): Literal[] {
  if (!e || !Array.isArray(e)) return into;
  const h = e[0];
  if (h === 'and' || h === 'or') { for (const s of e.slice(1)) literals(s, f, formables, labels, into); return into; }
  if (h === 'not') return literals(e[1], f, formables, labels, into);
  if (h === 'true' || h === 'false' || h === 'iotype' || h === 'mrep') return into;
  const v = h === 'cap' ? e[2] : e[1];
  if (v == null) return into;
  const key = `${h}:${v}`;
  if (into.some((l) => l.kind === h && l.v === v)) return into;
  into.push({ kind: h, v, label: labels?.[key], value: evalGate(e, f, formables) });
  return into;
}

// ── overrides ──────────────────────────────────────────────────
/** What the player asserted on top of the baseline: `one` kinds hold a
 *  value key (resolved through the kind's catalog to its bundle of atomic
 *  facts), `set` kinds hold atom → asserted boolean. */
export type Overrides = Record<string, string | SetFacts>;

/** Baseline ⊕ overrides → the facts a gate sees. `kinds` resolves a picked
 *  value to its bundle (a culture is cul + cgrp + lang; an area is every
 *  capital tier). */
export function applyOverrides(base: Facts, ov: Overrides, kinds: KindDef[]): Facts {
  const f: Facts = { ...base, cap: { ...(base.cap || {}) } };
  for (const [k, val] of Object.entries(ov)) {
    if (typeof val === 'string') {
      const def = kinds.find((d) => d.k === k);
      const kv = def?.values.find((x) => x.v === val);
      if (kv?.f) {
        for (const [fk, fv] of Object.entries(kv.f)) {
          (f as any)[fk] = fk === 'cap' ? { ...(f.cap || {}), ...(fv as any) } : fv;
        }
      } else {
        (f as any)[k] = val;
      }
    } else if (val && typeof val === 'object') {
      (f as any)[k] = { ...((f as any)[k] || {}), ...val };
    }
  }
  return f;
}

/** Country facts as build_planner.py emits them (lists for the set kinds
 *  known at 1337) → a Facts baseline. */
export function baseFacts(cf: Record<string, any> | null | undefined): Facts {
  if (!cf) return {};
  const f: Facts = { ...cf };
  for (const k of SET_KINDS) {
    const v = (cf as any)[k];
    if (Array.isArray(v)) {
      const m: SetFacts = {};
      for (const x of v) m[x] = true;
      (f as any)[k] = m;
    }
  }
  return f;
}

// ── URL codec ──────────────────────────────────────────────────
// One param per overridden kind: `cul=basque`, `cap=assam_area`,
// `reform=partitio_reform~-anatolian_beylik` (leading `-` = asserted
// absent), `q=` for the "other conditions" kind. `~` separates set atoms
// because the atoms themselves carry `.` and `:`.
const URL_KEY: Record<string, string> = { '?': 'q' };
const KEY_URL: Record<string, string> = { q: '?' };
const LEGACY: Record<string, string> = { cu: 'cul', re: 'rel', g: 'gov' };

export function overridesToParams(ov: Overrides, p: URLSearchParams) {
  for (const [k, val] of Object.entries(ov)) {
    const pk = URL_KEY[k] || k;
    if (typeof val === 'string') { if (val) p.set(pk, val); continue; }
    const atoms = Object.entries(val || {}).map(([a, b]) => (b ? '' : '-') + a);
    if (atoms.length) p.set(pk, atoms.join('~'));
  }
}

export function overridesFromParams(p: URLSearchParams, kinds: KindDef[]): Overrides {
  const ov: Overrides = {};
  const known = new Set(kinds.map((d) => d.k));
  for (const [pk, raw] of p.entries()) {
    const k = KEY_URL[pk] || LEGACY[pk] || pk;
    if (!known.has(k) || !raw) continue;
    const def = kinds.find((d) => d.k === k)!;
    if (def.mode === 'one') {
      if (def.values.some((x) => x.v === raw)) ov[k] = raw;
    } else {
      const m: SetFacts = {};
      for (const a of raw.split('~')) {
        if (!a) continue;
        const neg = a.startsWith('-');
        m[neg ? a.slice(1) : a] = !neg;
      }
      if (Object.keys(m).length) ov[k] = m;
    }
  }
  return ov;
}
