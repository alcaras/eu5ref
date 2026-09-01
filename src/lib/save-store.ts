// The imported save, as every page sees it: one snapshot in localStorage
// (written by the header's save rail, src/layouts/Base.astro), one
// preference record (is it in use, which seat), and a change event.
//
// Pages read `activeSeat()` at boot and treat it as their baseline —
// country, facts, laws, values, researched advances — with the 1337 setup
// as the fallback. The URL never carries the save: a shared link resolves
// against the recipient's own snapshot (or the 1337 setup), which is what
// "the save is the default view, toggle it off any time" means.

import type { SaveSnapshot, SaveSeat } from './save-import';
import type { Facts } from './facts';

export const SNAPSHOT_KEY = 'eu5ref-save';
export const PREF_KEY = 'eu5ref-save-pref';
export const CHANGE_EVENT = 'eu5save-changed';

export type SavePref = { enabled: boolean; seat: string | null };

let cache: SaveSnapshot | null | undefined;

export function loadSnapshot(): SaveSnapshot | null {
  if (cache !== undefined) return cache;
  try {
    const raw = localStorage.getItem(SNAPSHOT_KEY);
    const snap = raw ? (JSON.parse(raw) as SaveSnapshot) : null;
    cache = snap && snap.v === 1 ? snap : null;
  } catch { cache = null; }
  return cache;
}

export function loadPref(): SavePref {
  try {
    const raw = localStorage.getItem(PREF_KEY);
    if (raw) return { enabled: true, seat: null, ...JSON.parse(raw) };
  } catch { /* fall through */ }
  return { enabled: true, seat: null };
}

function announce() {
  try { window.dispatchEvent(new CustomEvent(CHANGE_EVENT)); } catch { /* not in a browser */ }
}

/** Store a freshly imported snapshot. Throws (QuotaExceeded) when the
 *  browser will not take it — the rail reports that honestly. */
export function storeSnapshot(snap: SaveSnapshot) {
  localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(snap));
  cache = snap;
  const pref = loadPref();
  const seats = Object.keys(snap.seats);
  pref.seat = snap.player && seats.includes(snap.player) ? snap.player : (seats[0] || null);
  pref.enabled = true;
  localStorage.setItem(PREF_KEY, JSON.stringify(pref));
  announce();
}

export function clearSnapshot() {
  localStorage.removeItem(SNAPSHOT_KEY);
  localStorage.removeItem(PREF_KEY);
  cache = null;
  announce();
}

export function setPref(patch: Partial<SavePref>) {
  const pref = { ...loadPref(), ...patch };
  localStorage.setItem(PREF_KEY, JSON.stringify(pref));
  announce();
}

export type ActiveSeat = { snap: SaveSnapshot; tag: string; seat: SaveSeat; facts: Facts };

/** The seat a page should default to, or null when no save is in use. */
export function activeSeat(): ActiveSeat | null {
  const snap = loadSnapshot();
  if (!snap) return null;
  const pref = loadPref();
  if (!pref.enabled) return null;
  const seats = Object.keys(snap.seats);
  const tag = pref.seat && snap.seats[pref.seat] ? pref.seat : seats[0];
  if (!tag) return null;
  const facts = snap.facts[tag] || { tag };
  return { snap, tag, seat: snap.seats[tag], facts };
}

/** Facts for any country in the snapshot (seats and non-seats alike), or
 *  null when the save is off or does not know the tag. */
export function saveFacts(tag: string): Facts | null {
  const snap = loadSnapshot();
  if (!snap || !loadPref().enabled) return null;
  return snap.facts[tag] || null;
}

/** A seat rewritten in the shape of a country-start.json record, so the
 *  values tools can drop it in place of the 1337 setup. Locked axes (−999
 *  in the save) are left out — the axis is not open yet. */
export function seatAsStart(seat: SaveSeat, facts: Facts | null): Record<string, any> {
  const values: Record<string, number> = {};
  for (const [k, v] of Object.entries(seat.values || {})) if (v > -500) values[k] = Math.round(v * 100) / 100;
  return {
    type: seat.gov, parliament: seat.parl || null,
    laws: seat.laws, privileges: seat.privs, reforms: seat.reforms,
    values, io: Object.keys(facts?.iomem || {}), subj: facts?.subj || 'none',
    fromSave: true,
  };
}

export function onSaveChange(fn: () => void) {
  window.addEventListener(CHANGE_EVENT, fn);
  window.addEventListener('storage', (e) => { if (e.key === SNAPSHOT_KEY || e.key === PREF_KEY) { cache = undefined; fn(); } });
}

/** Short label for chips: "Serbia · 1494". */
export function seatLabel(a: ActiveSeat): string {
  const year = (a.snap.date || '').split('.')[0];
  return year ? `${a.seat.name} · ${year}` : a.seat.name;
}
