// Save import: a melted (plain-text) .eu5 save → a compact snapshot the
// gated tools use as their baseline instead of the 1337 setup.
//
// The file is read locally in the browser, never uploaded. Melted saves are
// 300–600 MB, so this is a streaming line scanner, not a parser: it walks the
// top-level `name={` blocks (column 0, one tab per depth), skips the ones it
// does not need with a single indexOf, and pulls fixed fields out of the few
// it does with regexes over one entry at a time. Two stages —
//
//   scan()    — pure text → RawScan (ids, keys, numbers as the save has them);
//               runs in node too, which is how it is tested against a fixture.
//   resolve() — RawScan + the site's own catalogs (planner.json `kinds` for
//               culture → group/language, religion → group; geo.json for a
//               capital's area → region → sub-continent → continent) → a
//               SaveSnapshot of Facts per country plus a full "seat" (laws,
//               privileges, reforms, values, researched advances) for each
//               played country.
//
// Save shapes this relies on (verified on 1.1.x melted saves; 1.3.x differs
// only in the subject-relation block, handled below):
//   metadata={ date= version= flag="TAG={…}" player_country_name= enabled_dlcs={…}
//              compatibility={ locations={ <one-line list; index+1 = location id> } } }
//   current_age=age_3_discovery                       (top-level scalar)
//   culture_manager={ database={ N={ culture_definition=key … } } }
//   religion_manager={ database={ N={ definition=key … } } }
//   estate_manager={ database={ N={ estate_type= country=id existence=yes } } }
//   countries={ tags={ N=TAG } database={ N={ definition= country_type=Real
//               government={ type= parliament={ parliament_type= }
//                            implemented_laws={ group={ object=opt } }
//                            implemented_privileges={ { object= } }
//                            implemented_reforms={ { object= } }
//                            societal_values={ axis=v } }
//               primary_culture=id primary_religion=id capital=locid
//               institutions={ k=yes } researched_advances={ k=yes } } } }
//   international_organization_manager={ database={ N={ type= all_members={ ids } } } }
//   diplomacy_manager={ dependency={ first=overlord second=subject subject_type=x } }
//   played_country={ name= country=id }               (one per human player)

export type RawCountry = {
  tag: string; type: string;
  gov?: string; parl?: string;
  cul?: number; rel?: number; cap?: number;
  laws: Record<string, string>; privs: string[]; reforms: string[];
  values: Record<string, number>;
  institutions: string[]; researched: string[];
};

export type RawScan = {
  date?: string; version?: string; age?: string;
  playerTag?: string; playerName?: string;
  dlcs: string[];
  locations: string[];                    // index = location id − 1 → script key
  cultures: Map<number, string>;          // culture id → culture key
  religions: Map<number, string>;         // religion id → religion key
  estates: Map<number, string[]>;         // country id → active estate types
  tags: Map<number, string>;              // country id → TAG
  countries: Map<number, RawCountry>;     // country id → entry (Real countries)
  subjects: Map<number, { type: string; overlord: number }>;
  ios: Map<number, string[]>;             // country id → IO types it belongs to
  played: { name: string; country: number }[];
  lines: number;
};

// ── stage 1: scan ───────────────────────────────────────────────

const RX = {
  header: /^(\w+)=\{$/,
  scalar: /^(\w+)=(\S+)$/,
  entry: /^\t\t(\d+)=\{( \}|\{\s*\})?$/,
};

/** Substring of `text` inside `\n<tabs>header={` … `\n<tabs>}` (the block's
 *  own indentation), newline-terminated, or '' when absent. */
function block(text: string, header: string, depth: number): string {
  const tabs = '\t'.repeat(depth);
  const open = `\n${tabs}${header}={`;
  const i = text.indexOf(open);
  if (i < 0) return '';
  const start = i + open.length;
  const close = `\n${tabs}}`;
  const j = text.indexOf(close, start);
  // keep the newline that ends the last line so `scalar()` can anchor on it
  return j < 0 ? text.slice(start) + '\n' : text.slice(start, j + 1);
}

function scalar(text: string, key: string, depth: number): string | undefined {
  const m = new RegExp(`\\n\\t{${depth}}${key}=("?)([^"\\n]*)\\1(?=\\n)`).exec(text);
  return m ? m[2] : undefined;
}

function yesKeys(text: string, depth: number): string[] {
  const out: string[] = [];
  const rx = new RegExp(`\\n\\t{${depth}}(\\w+)=yes(?=\\n)`, 'g');
  let m: RegExpExecArray | null;
  while ((m = rx.exec(text))) out.push(m[1]);
  return out;
}

function objects(text: string, depth: number): string[] {
  const out: string[] = [];
  const rx = new RegExp(`\\n\\t{${depth}}object=(\\S+)`, 'g');
  let m: RegExpExecArray | null;
  while ((m = rx.exec(text))) out.push(m[1]);
  return out;
}

function parseCountry(text: string): RawCountry | null {
  const type = scalar(text, 'country_type', 3) || '';
  const tag = scalar(text, 'definition', 3);
  if (!tag) return null;
  const c: RawCountry = { tag, type, laws: {}, privs: [], reforms: [], values: {}, institutions: [], researched: [] };
  const num = (k: string) => { const v = scalar(text, k, 3); return v == null ? undefined : parseInt(v, 10); };
  c.cul = num('primary_culture');
  c.rel = num('primary_religion');
  c.cap = num('capital');
  const gov = block(text, 'government', 3);
  if (gov) {
    c.gov = scalar(gov, 'type', 4);
    const parl = block(gov, 'parliament', 4);
    if (parl) c.parl = scalar(parl, 'parliament_type', 5);
    const laws = block(gov, 'implemented_laws', 4);
    if (laws) {
      const rx = /\n\t{5}(\w+)=\{\n(?:\t{6}(?!object=)[^\n]*\n)*\t{6}object=(\S+)/g;
      let m: RegExpExecArray | null;
      while ((m = rx.exec(laws))) c.laws[m[1]] = m[2];
    }
    const privs = block(gov, 'implemented_privileges', 4);
    if (privs) c.privs = objects(privs, 6);
    const reforms = block(gov, 'implemented_reforms', 4);
    if (reforms) c.reforms = objects(reforms, 6);
    const values = block(gov, 'societal_values', 4);
    if (values) {
      const rx = /\n\t{5}(\w+)=(-?[\d.]+)/g;
      let m: RegExpExecArray | null;
      while ((m = rx.exec(values))) c.values[m[1]] = parseFloat(m[2]);
    }
  }
  const inst = block(text, 'institutions', 3);
  if (inst) c.institutions = yesKeys(inst, 4);
  const adv = block(text, 'researched_advances', 3);
  if (adv) c.researched = yesKeys(adv, 4);
  return c;
}

/** Incremental scanner: feed decoded text in any chunking, then end(). */
export class SaveScanner {
  raw: RawScan = {
    dlcs: [], locations: [], cultures: new Map(), religions: new Map(), estates: new Map(),
    tags: new Map(), countries: new Map(), subjects: new Map(), ios: new Map(), played: [], lines: 0,
  };
  private buf = '';
  private top: string | null = null;      // current top-level block name
  private sub: string | null = null;      // 'tags' | 'database' within countries
  private entry: string[] | null = null;  // text parts of the \t\tN={ entry being captured
  private acc: string[] | null = null;    // whole-block capture (metadata, played_country)
  private pending: { depth: number; lines: string[] } | null = null;   // a dependency={ block
  private skipping = false;

  // Top-level blocks we read at all. Everything else is skipped wholesale.
  private static WANT = new Set(['metadata', 'culture_manager', 'religion_manager', 'estate_manager',
    'countries', 'international_organization_manager', 'diplomacy_manager', 'played_country']);

  push(text: string) {
    this.buf += text;
    const buf = this.buf;
    let pos = 0;
    for (;;) {
      if (this.skipping) {
        // Inside an unwanted top-level block: jump straight to its closing
        // "\n}\n" instead of walking millions of lines. (pos − 1 is the
        // newline that ended the header line, so an empty block closes too.)
        const j = buf.indexOf('\n}\n', Math.max(0, pos - 1));
        if (j < 0) { this.buf = buf.slice(Math.max(pos, buf.length - 3)); return; }
        pos = j + 3;
        this.skipping = false;
        this.top = null;
        continue;
      }
      if (this.entry) {
        // Inside a database entry: grab everything up to the "\n\t\t}\n"
        // that closes it in one slice.
        const j = buf.indexOf('\n\t\t}\n', Math.max(0, pos - 1));
        if (j < 0) {
          const keep = Math.max(pos, buf.length - 4);
          this.entry.push(buf.slice(pos, keep));
          this.buf = buf.slice(keep);
          return;
        }
        this.entry.push(buf.slice(pos, j + 4));
        pos = j + 5;
        this.flushEntry();
        continue;
      }
      if (this.top === 'diplomacy_manager' && !this.pending) {
        // Only the dependency blocks matter; skip ahead to the next one
        // or to the end of the manager.
        const a = buf.indexOf('dependency={', pos);
        const b = buf.indexOf('\n}\n', Math.max(0, pos - 1));
        if (a >= 0 && (b < 0 || a < b)) pos = buf.lastIndexOf('\n', a) + 1;
        else if (b >= 0) pos = b + 1;
        else { this.buf = buf.slice(Math.max(pos, buf.length - 16)); return; }
      }
      const nl = buf.indexOf('\n', pos);
      if (nl < 0) break;
      this.line(buf.slice(pos, nl));
      pos = nl + 1;
    }
    this.buf = buf.slice(pos);
  }

  end(): RawScan {
    if (this.buf.length && !this.entry && !this.skipping) this.line(this.buf);
    this.buf = '';
    if (this.acc) this.closeTop();
    return this.raw;
  }

  private line(ln: string) {
    this.raw.lines++;
    if (this.top === null) {
      if (ln.charCodeAt(0) === 9) return;               // stray indented line
      const h = RX.header.exec(ln);
      if (h) {
        this.top = h[1];
        this.sub = null;
        if (!SaveScanner.WANT.has(h[1])) { this.skipping = true; return; }
        if (h[1] === 'metadata' || h[1] === 'played_country') this.acc = [];
        return;
      }
      const s = RX.scalar.exec(ln);
      if (s && s[1] === 'current_age') this.raw.age = s[2];
      return;
    }
    if (ln === '}') { this.closeTop(); return; }
    if (this.acc) { this.acc.push(ln); return; }
    switch (this.top) {
      case 'countries': return this.countriesLine(ln);
      case 'diplomacy_manager': return this.diplomacyLine(ln);
      default: return this.managerLine(ln);
    }
  }

  private closeTop() {
    const t = this.top;
    this.top = null;
    this.sub = null;
    this.pending = null;
    if (this.acc) {
      const text = '\n' + this.acc.join('\n') + '\n';
      this.acc = null;
      if (t === 'metadata') this.metadata(text);
      else if (t === 'played_country') {
        const name = scalar(text, 'name', 1);
        const country = scalar(text, 'country', 1);
        if (country != null) this.raw.played.push({ name: name || '', country: parseInt(country, 10) });
      }
    }
  }

  private metadata(text: string) {
    this.raw.date = scalar(text, 'date', 1);
    this.raw.version = scalar(text, 'version', 1);
    this.raw.playerName = scalar(text, 'player_country_name', 1);
    const flag = /\n\tflag="(\w+)=\{/.exec(text);
    if (flag) this.raw.playerTag = flag[1];
    const dlcs = block(text, 'enabled_dlcs', 1);
    if (dlcs) this.raw.dlcs = [...dlcs.matchAll(/"([^"]*)"/g)].map((m) => m[1]);
    const compat = block(text, 'compatibility', 1);
    const locs = compat ? block(compat, 'locations', 2) : '';
    if (locs) this.raw.locations = locs.trim().split(/\s+/);
  }

  // culture/religion/estate/IO managers: database={ N={ … } } entries
  private managerLine(ln: string) {
    const e = RX.entry.exec(ln);
    if (e && !e[2]) this.entry = [ln + '\n'];          // e[2]: one-line empty entry
  }

  private countriesLine(ln: string) {
    if (ln === '\ttags={') { this.sub = 'tags'; return; }
    if (ln === '\tdatabase={') { this.sub = 'database'; return; }
    if (ln === '\t}') { this.sub = null; return; }
    if (this.sub === 'tags') {
      const m = /^\t\t(\d+)=(\w+)$/.exec(ln);
      if (m) this.raw.tags.set(parseInt(m[1], 10), m[2]);
      return;
    }
    if (this.sub === 'database') this.managerLine(ln);
  }

  private diplomacyLine(ln: string) {
    if (this.pending) {
      this.pending.lines.push(ln);
      if (ln === '\t'.repeat(this.pending.depth - 1) + '}') {
        const { depth, lines } = this.pending;
        this.pending = null;
        const text = '\n' + lines.join('\n') + '\n';
        const first = scalar(text, 'first', depth), second = scalar(text, 'second', depth);
        let type = scalar(text, 'subject_type', depth);
        if (!type) {
          // 1.3.x: named_targets={ { flag=subject_type target={ … object=vassal } } }
          const m = /flag=subject_type[\s\S]*?object=(\w+)/.exec(text);
          if (m) type = m[1];
        }
        if (first && second && type) {
          this.raw.subjects.set(parseInt(second, 10), { type, overlord: parseInt(first, 10) });
        }
      }
      return;
    }
    const m = /^(\t+)dependency=\{$/.exec(ln);
    if (m) this.pending = { depth: m[1].length + 1, lines: [] };
  }

  private flushEntry() {
    const text = '\n' + this.entry!.join('') + '\n';
    this.entry = null;
    const id = parseInt(/^\n\t\t(\d+)=/.exec(text)![1], 10);
    switch (this.top) {
      case 'culture_manager': {
        const k = scalar(text, 'culture_definition', 3);
        if (k) this.raw.cultures.set(id, k);
        break;
      }
      case 'religion_manager': {
        const k = scalar(text, 'definition', 3);
        if (k) this.raw.religions.set(id, k);
        break;
      }
      case 'estate_manager': {
        if (scalar(text, 'existence', 3) !== 'yes') break;
        const t = scalar(text, 'estate_type', 3), c = scalar(text, 'country', 3);
        if (t && c) {
          const cid = parseInt(c, 10);
          const arr = this.raw.estates.get(cid) || [];
          arr.push(t);
          this.raw.estates.set(cid, arr);
        }
        break;
      }
      case 'international_organization_manager': {
        const t = scalar(text, 'type', 3);
        const members = block(text, 'all_members', 3);
        if (t && members) {
          for (const s of members.trim().split(/\s+/)) {
            const cid = parseInt(s, 10);
            if (!Number.isFinite(cid)) continue;
            const arr = this.raw.ios.get(cid) || [];
            if (!arr.includes(t)) arr.push(t);
            this.raw.ios.set(cid, arr);
          }
        }
        break;
      }
      case 'countries': {
        const c = parseCountry(text);
        if (c && c.type === 'Real') this.raw.countries.set(id, c);
        break;
      }
    }
  }
}

/** Browser entry point: stream a File through the scanner. */
export async function scanFile(file: Blob, onProgress?: (frac: number) => void): Promise<RawScan> {
  const sc = new SaveScanner();
  const dec = new TextDecoder('utf-8');
  const CHUNK = 8 << 20;
  const head = await file.slice(0, 3).text();
  if (head !== 'SAV') throw new Error('Not a melted .eu5 save (expected a text file starting with SAV).');
  for (let off = 0; off < file.size; off += CHUNK) {
    const buf = await file.slice(off, off + CHUNK).arrayBuffer();
    sc.push(dec.decode(buf, { stream: true }));
    onProgress?.(Math.min(1, (off + CHUNK) / file.size));
  }
  sc.push(dec.decode());
  return sc.end();
}

// ── stage 2: resolve ────────────────────────────────────────────

import type { Facts, KindDef } from './facts';

export type Geo = {
  areas: Record<string, [string, string]>;     // area → [name, region]
  regions: Record<string, [string, string]>;   // region → [name, sub_continent]
  subs: Record<string, [string, string]>;      // sub_continent → [name, continent]
  conts: Record<string, string>;
  locations: Record<string, string>;           // location key → area
};

export type SaveSeat = {
  tag: string; name: string; player?: string;   // player: the human's name, latest played_country entry
  gov?: string; parl?: string;
  laws: Record<string, string>; privs: string[]; reforms: string[];
  /** societal values as saved; −999 marks an axis the country has not unlocked */
  values: Record<string, number>;
  institutions: string[]; researched: string[];
};

export type SaveSnapshot = {
  v: 1;
  file: string; imported: string;
  date?: string; version?: string; age?: string;
  dlcs: string[];
  player?: string;                 // tag of the saving player
  seats: Record<string, SaveSeat>; // played countries, full detail
  facts: Record<string, Facts>;    // every Real country's gate facts
  counts: { countries: number; subjects: number };
};

export const SNAPSHOT_KEY = 'eu5ref-save';

export function resolve(raw: RawScan, file: string, kinds: KindDef[], geo: Geo | null,
                        names: Record<string, string> = {}): SaveSnapshot {
  const bundle = (kind: string) => {
    const m = new Map<string, Record<string, any>>();
    for (const v of kinds.find((d) => d.k === kind)?.values || []) if (v.f) m.set(v.v, v.f);
    return m;
  };
  const culB = bundle('cul'), relB = bundle('rel');
  // The save is complete knowledge for these: a reform not implemented, an
  // estate not active, an IO not joined is a definite ✗, not "unknown". So
  // every value some gate tests (the kind's catalog) that the save does not
  // list is asserted false. (Not for `mcg` — unified cultures are not read.)
  const tested = (kind: string) => (kinds.find((d) => d.k === kind)?.values || []).map((v) => v.v);
  const COMPLETE = ['reform', 'estate', 'iomem'];
  const COMPLETE_SEAT = ['law', 'priv', 'adv'];
  // DLC: the save carries display names, the gates carry ids. A
  // case-insensitive label match is a ✓; no match stays unknown rather
  // than hiding a DLC's advances on a naming difference.
  const dlcNames = new Set(raw.dlcs.map((s) => s.toLowerCase()));
  const dlcFacts: Record<string, boolean> = {};
  for (const v of kinds.find((d) => d.k === 'dlc')?.values || []) if (dlcNames.has(v.l.toLowerCase())) dlcFacts[v.v] = true;
  const capOf = (locId: number | undefined): Facts['cap'] | undefined => {
    if (!geo || locId == null) return undefined;
    const key = raw.locations[locId - 1];
    const area = key && geo.locations[key];
    if (!area) return undefined;
    const region = geo.areas[area]?.[1];
    const sub = region ? geo.regions[region]?.[1] : undefined;
    const cont = sub ? geo.subs[sub]?.[1] : undefined;
    return { area, region, sub_continent: sub, continent: cont };
  };
  const playedIds = new Set(raw.played.map((p) => p.country));
  const facts: Record<string, Facts> = {};
  const seats: Record<string, SaveSeat> = {};
  for (const [id, c] of raw.countries) {
    const f: Facts = { tag: c.tag };
    const cul = c.cul != null ? raw.cultures.get(c.cul) : undefined;
    if (cul) { f.cul = cul; Object.assign(f, culB.get(cul) || {}); }
    const rel = c.rel != null ? raw.religions.get(c.rel) : undefined;
    if (rel) { f.rel = rel; Object.assign(f, relB.get(rel) || {}); }
    const cap = capOf(c.cap);
    if (cap) f.cap = cap;
    if (c.gov) f.gov = c.gov;
    if (c.parl) f.parl = c.parl;
    f.ctype = 'real';   // the save says Real; gates test the virtual types (army, building…)
    f.subj = raw.subjects.get(id)?.type || 'none';
    if (raw.age) f.age = raw.age;
    const set = (k: keyof Facts, xs: string[], complete = false) => {
      const m: Record<string, boolean> = {};
      if (complete) for (const v of tested(k)) m[v] = false;
      for (const x of xs) m[x] = true;
      (f as any)[k] = m;
    };
    set('reform', c.reforms, COMPLETE.includes('reform'));
    set('estate', raw.estates.get(id) || [], COMPLETE.includes('estate'));
    set('iomem', raw.ios.get(id) || [], COMPLETE.includes('iomem'));
    const isPlayer = playedIds.has(id) || c.tag === raw.playerTag;
    if (isPlayer) {
      // The long lists (laws, privileges, researched advances) only for the
      // played seats: 2,000+ countries' worth would not fit localStorage,
      // and for everyone else "unknown → conditional" is the honest answer.
      set('law', Object.values(c.laws), COMPLETE_SEAT.includes('law'));
      set('priv', c.privs, COMPLETE_SEAT.includes('priv'));
      set('adv', c.researched, COMPLETE_SEAT.includes('adv'));
      if (Object.keys(dlcFacts).length) f.dlc = { ...dlcFacts };
    }
    facts[c.tag] = f;
    if (isPlayer) {
      seats[c.tag] = {
        tag: c.tag, name: names[c.tag] || c.tag,
        player: raw.played.filter((p) => p.country === id).pop()?.name,
        gov: c.gov, parl: c.parl, laws: c.laws, privs: c.privs, reforms: c.reforms,
        values: c.values, institutions: c.institutions, researched: c.researched,
      };
    }
  }
  return {
    v: 1, file, imported: new Date().toISOString().slice(0, 10),
    date: raw.date, version: raw.version, age: raw.age, dlcs: raw.dlcs,
    player: raw.playerTag, seats, facts,
    counts: { countries: raw.countries.size, subjects: raw.subjects.size },
  };
}
