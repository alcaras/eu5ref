/** EU5 land-battle engine — pure functions over public/battle.json.
 *
 * Everything numeric comes from the payload (game defines, resolved unit
 * stats, terrain, static modifiers). The hour loop follows the game's own
 * description: bombard phase, d10 dice per side re-rolled every
 * HOURS_PER_PHASE, d100 initiative rolls to engage, d20 combat-speed rolls
 * to leave the reserves, four sections, flanking into adjacent sections.
 * Composition of the damage-multiplier chain is the inferred part — the
 * factors themselves are the ones the battle tooltip enumerates. The page's
 * model-notes panel documents exact vs inferred piece by piece.
 */

export interface RegSpec { u: string; n: number }
export interface SideSpec {
  regs: RegSpec[];
  formation: string;
  mods: Record<string, number>;
  traits: string[];
  retreat: number;          // retreat below this avg front morale % (0 = never)
}
export interface BattleConfig {
  topo: string; veg: string;
  attacker: 'A' | 'B';
  crossing: '' | 'river' | 'strait' | 'sea';
}

export const MOD_DEFAULTS: Record<string, number> = {
  disc: 0, tact: 1.0, mor: 0, init: 0, cspd: 0, front: 0,
  levy: 0, exp: 0, powInf: 0, powCav: 0, powArt: 0, dice: 0,
};
export const blankSide = (): SideSpec => ({
  regs: [], formation: 'balanced_army', mods: { ...MOD_DEFAULTS },
  traits: [], retreat: 0,
});

export function mulberry32(a: number) {
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const FRONT = ['left', 'center', 'right'];
const MIRROR: Record<string, string> = { left: 'right', center: 'center', right: 'left' };
const NEIGH: Record<string, string[]> = { left: ['center'], center: ['left', 'right'], right: ['center'] };

/** Side-level derived numbers (mods + traits merged). */
export function sideParams(D: any, s: SideSpec) {
  const d = D.defines;
  let disc = s.mods.disc / 100, tact = s.mods.tact, mor = s.mods.mor / 100,
      init = s.mods.init / 100, cspd = s.mods.cspd / 100, front = s.mods.front / 100,
      dice = s.mods.dice, levyEff = s.mods.levy / 100;
  const pow: Record<string, number> = {
    army_light_infantry: s.mods.powInf / 100, army_heavy_infantry: s.mods.powInf / 100,
    army_light_cavalry: s.mods.powCav / 100, army_heavy_cavalry: s.mods.powCav / 100,
    army_artillery: s.mods.powArt / 100, army_auxiliary: 0,
  };
  for (const tk of s.traits) {
    const t = D.traits.find((x: any) => x.key === tk); if (!t) continue;
    for (const [k, v] of Object.entries(t.mods) as [string, number][]) {
      if (k === 'commander_combat_bonus') dice += v;
      else if (k === 'discipline') disc += v;
      else if (k === 'military_tactics') tact += v;
      else if (k === 'land_morale_modifier') mor += v;
      else if (k === 'army_initiative') init += v;
      else if (k === 'combat_speed_modifier') cspd += v;
      else if (k === 'possible_frontage_modifier') front += v;
      else if (k.endsWith('_power') && k.startsWith('army_')) {
        const cat = k.slice(0, -'_power'.length);
        if (cat in pow) pow[cat] += v;
      }
    }
  }
  const maxMorale = d.LAND_MORALE * (1 + mor);
  const levyDisc = disc + (D.sources.levy.discipline || 0);
  const levyFactor = d.LAND_LEVY_COMBAT_IMPACT * (1 + levyEff);
  return { disc, levyDisc, tact, maxMorale, init, cspd, front, dice, pow,
           levyFactor, exp: s.mods.exp / 100, retreat: s.retreat / 100 };
}

/** Combined-arms bonus from the initial composition (aux excluded). */
export function combinedArms(D: any, s: SideSpec) {
  const cb = D.countryBase;
  const counts: Record<string, number> = {};
  let total = 0;
  for (const r of s.regs) {
    const u = D.units[r.u];
    if (!u || u.cat === 'army_auxiliary') continue;
    counts[u.cat] = (counts[u.cat] || 0) + r.n; total += r.n;
  }
  if (!total) return 0;
  const fr = Object.values(counts).map(c => c / total);
  if (fr.some(f => f >= (cb.combined_arms_max_threshold ?? 0.5))) return 0;
  const n = fr.filter(f => f >= (cb.combined_arms_min_percent_for_bonus ?? 0.1)).length;
  return Math.max(0, n - 1) * (cb.combined_bonus_per_type ?? 0.025);
}

export function terrainFrontage(D: any, cfg: BattleConfig) {
  const d = D.defines;
  const t = D.terrain.topography[cfg.topo], v = D.terrain.vegetation[cfg.veg];
  return Math.max(d.MIN_FRONTAGE_AFTER_TERRAIN,
                  D.baseFrontage + (t?.frontage || 0) + (v?.frontage || 0));
}
export function defenderDice(D: any, cfg: BattleConfig) {
  return (D.terrain.topography[cfg.topo]?.defender || 0) +
         (D.terrain.vegetation[cfg.veg]?.defender || 0);
}
export function crossDice(D: any, cfg: BattleConfig) {
  return cfg.crossing === 'river' ? D.defines.RIVER_CROSSING_DICE
    : cfg.crossing === 'strait' ? D.defines.STRAIT_CROSSING_DICE
    : cfg.crossing === 'sea' ? D.defines.SEA_LANDING_DICE : 0;
}

/** Terrain damage multiplier from one unit's combat={} block. */
function terrainMult(u: any, cfg: BattleConfig) {
  if (!u.combat) return 1;
  let m = 0;
  if (u.combat[cfg.topo] != null) m += u.combat[cfg.topo];
  if (u.combat[cfg.veg] != null) m += u.combat[cfg.veg];
  if (cfg.crossing === 'river' && u.combat.river != null) m += u.combat.river;
  if (cfg.crossing === 'sea' && u.combat.coastal != null) m += u.combat.coastal;
  return 1 + m;
}

interface SimReg {
  u: any; key: string; side: string; men: number; maxMen: number;
  morale: number; sec: string; engaged: boolean; broken: boolean;
}

function deploy(D: any, s: SideSpec, side: string, P: any, F: number,
                rand: () => number): SimReg[] {
  const d = D.defines;
  const form = D.formations[s.formation];
  const regs: SimReg[] = [];
  for (const r of s.regs) {
    const u = D.units[r.u];
    if (!u) continue;
    for (let i = 0; i < r.n; i++) {
      const maxMen = (u.stats.max_strength || 0.5) * d.REGIMENT_SIZE;
      regs.push({ u, key: r.u, side, men: maxMen, maxMen,
                  morale: P.maxMorale, sec: 'reserves', engaged: false, broken: false });
    }
  }
  // per-section frontage caps: side frontage split across the three front
  // sections, each stretched by the formation's max_frontage (INFERRED)
  const caps: Record<string, number> = {};
  for (const sec of FRONT) {
    const mf = form.sections[sec]?.max_frontage ?? d.MAX_FRONTAGE_OVERSTACKING;
    caps[sec] = (F / 3) * mf;
  }
  const used: Record<string, number> = { left: 0, center: 0, right: 0 };
  const weightOf = (sec: string, cat: string) => {
    let w = 0;
    for (const it of form.sections[sec]?.weights || []) if (it.cat === cat) w += it.w;
    return w;
  };
  const sorted = [...regs].sort((a, b) => (b.u.stats.combat_power || 0) - (a.u.stats.combat_power || 0));
  for (const reg of sorted) {
    if (reg.u.cat === 'army_auxiliary') continue;   // aux stay in reserves
    let best = '', score = -1;
    for (const sec of FRONT) {
      const fr = reg.u.stats.frontage || 1;
      if (used[sec] + fr > caps[sec]) continue;
      const sc = (weightOf(sec, reg.u.cat) + 0.01) * (caps[sec] - used[sec]) * (0.9 + rand() * 0.2);
      if (sc > score) { score = sc; best = sec; }
    }
    if (best) { reg.sec = best; used[best] += reg.u.stats.frontage || 1; }
  }
  return regs;
}

export interface SimResult {
  winner: 'A' | 'B' | 'draw';
  hours: number;
  lost: { A: number; B: number };
  start: { A: number; B: number };
}

export function simulate(D: any, cfg: BattleConfig,
                         sides: { A: SideSpec; B: SideSpec },
                         rand: () => number, log?: string[]): SimResult {
  const d = D.defines;
  const P: any = { A: sideParams(D, sides.A), B: sideParams(D, sides.B) };
  const CA: any = { A: combinedArms(D, sides.A), B: combinedArms(D, sides.B) };
  const Fbase = terrainFrontage(D, cfg);
  const F: any = { A: Fbase * (1 + P.A.front), B: Fbase * (1 + P.B.front) };
  const regs: SimReg[] = [
    ...deploy(D, sides.A, 'A', P.A, F.A, rand),
    ...deploy(D, sides.B, 'B', P.B, F.B, rand),
  ];
  const bySide = (sd: string) => regs.filter(r => r.side === sd);
  const alive = (r: SimReg) => !r.broken && r.men > 0.5;
  const inFront = (r: SimReg) => alive(r) && r.sec !== 'reserves';
  const canFight = (r: SimReg) => alive(r) && r.u.cat !== 'army_auxiliary';
  const dice: any = { A: 0, B: 0 };
  const diceMod = (sd: string) => P[sd].dice +
    (sd === cfg.attacker ? crossDice(D, cfg) : defenderDice(D, cfg));
  const roll = (sd: string) => Math.max(0, Math.min(d.COMBAT_MAX,
    d.COMBAT_BASE + Math.floor(rand() * d.COMBAT_DICE_SIDE) + 1 + diceMod(sd)));
  const hasBombard = regs.some(r => alive(r) && D.categories[r.u.cat]?.flags?.bombard);
  const bombardHours = hasBombard ? d.BOMBARD_HOURS : 0;
  const start: any = { A: bySide('A').reduce((t, r) => t + r.men, 0),
                       B: bySide('B').reduce((t, r) => t + r.men, 0) };
  let hour = 0;
  let winner: 'A' | 'B' | 'draw' | '' = '';

  const calcDamage = (att: SimReg, tgt: SimReg, flanked: boolean, bombard: boolean) => {
    const pa = P[att.side], pt = P[tgt.side];
    const aLevy = att.u.levy, tLevy = tgt.u.levy;
    const discA = aLevy ? pa.levyDisc : pa.disc;
    const discT = tLevy ? pt.levyDisc : pt.disc;
    const dv = bombard ? d.COMBAT_BASE : dice[att.side];
    let base = dv * d.COMBAT_DAMAGE_MULT
      * (att.u.stats.combat_power || 0)
      * (att.men / d.REGIMENT_SIZE);
    base *= (1 + discA) / (1 + discT);
    base *= 1 + (pa.pow[att.u.cat] || 0);
    base *= 1 + CA[att.side];
    if (aLevy) base *= pa.levyFactor;              // levy hits softer
    if (tLevy) base /= pt.levyFactor;              // …and is hit harder
    base *= 1 - pt.exp * d.LAND_EXPERIENCE_DAMAGE_REDUCTION;
    base *= D.categories[tgt.u.cat]?.stats?.damage_taken ?? 1;
    base /= Math.max(0.1, pt.tact);
    base *= terrainMult(att.u, cfg);
    if (flanked) base *= att.u.stats.flanking_ability || 1;
    // secure flanks: each friendly-held neighbour section of the target
    const held = (NEIGH[tgt.sec] || []).filter(nsec =>
      regs.some(r => r.side === tgt.side && r.sec === nsec && alive(r))).length;
    base *= Math.max(0, 1 - (tgt.u.stats.secure_flanks_defense || 0) * held);
    base *= att.morale / P[att.side].maxMorale;    // morale scale (INFERRED)
    const str = base * d.LAND_STRENGTH_DAMAGE_MODIFIER
      * (1 + (att.u.stats.strength_damage_done || 0))
      * (1 + (tgt.u.stats.strength_damage_taken || 0))
      * (tgt.engaged ? 1 : d.NOT_ENGAGED_STRENGTH_DAMAGE_MODIFIER);
    const mor = base * d.LAND_MORALE_DAMAGE_MODIFIER * d.BASE_MORALE_DAMAGE
      * (1 + (att.u.stats.morale_damage_done || 0))
      * (1 + (tgt.u.stats.morale_damage_taken || 0))
      * (tgt.engaged ? 1 : d.NOT_ENGAGED_MORALE_DAMAGE_MODIFIER);
    return { str, mor };
  };

  while (hour < 1500) {
    hour++;
    const inBombard = hour <= bombardHours;
    if (!inBombard && (hour - bombardHours - 1) % d.HOURS_PER_PHASE === 0) {
      dice.A = roll('A'); dice.B = roll('B');
      log?.push(`h${hour}  phase dice  A ${dice.A}  B ${dice.B}`);
    }

    // movement + engagement (own-side state only, order-independent)
    if (!inBombard) for (const sd of ['A', 'B'] as const) {
      const frontRegs = bySide(sd).filter(inFront);

      // reserves roll d20 vs combat speed to move up, best power first
      const caps: Record<string, number> = {};
      for (const sec of FRONT) {
        const mf = D.formations[sides[sd].formation].sections[sec]?.max_frontage
          ?? d.MAX_FRONTAGE_OVERSTACKING;
        caps[sec] = (F[sd] / 3) * mf;
      }
      const used: Record<string, number> = { left: 0, center: 0, right: 0 };
      for (const r of frontRegs) used[r.sec] += r.u.stats.frontage || 1;
      const reserves = bySide(sd)
        .filter(r => alive(r) && r.sec === 'reserves' && r.u.cat !== 'army_auxiliary')
        .sort((a, b) => (b.u.stats.combat_power || 0) - (a.u.stats.combat_power || 0));
      for (const r of reserves) {
        const secs = FRONT.filter(sec => used[sec] + (r.u.stats.frontage || 1) <= caps[sec]);
        if (!secs.length) break;
        const cs = (r.u.stats.combat_speed || 0) * (1 + P[sd].cspd);
        if (rand() < cs * d.COMBAT_SPEED_SCALE) {
          const sec = secs.sort((x, y) => (used[x] / caps[x]) - (used[y] / caps[y]))[0];
          r.sec = sec; used[sec] += r.u.stats.frontage || 1;
          log?.push(`h${hour}  ${sd} ${r.u.name} joins ${sec} from reserves`);
        }
      }

      // engagement rolls (d100 vs initiative chance)
      for (const r of bySide(sd).filter(inFront)) {
        if (r.engaged) continue;
        const init = (r.u.stats.initiative || 0) * (1 + P[sd].init);
        const chance = d.INITIATIVE_BASE_CHANCE
          + Math.min(init * d.INITIATIVE_CHANCE_EACH, d.INITIATIVE_CHANCE_MAX)
          + hour * d.INITIATIVE_CHANCE_HOURS;
        if (rand() < chance) r.engaged = true;
      }
    }

    // damage resolves SIMULTANEOUSLY: pick and compute every strike from
    // the same pre-damage snapshot, then apply — no first-mover advantage
    const strikes: [SimReg, { str: number; mor: number }][] = [];
    const front: any = { A: bySide('A').filter(inFront), B: bySide('B').filter(inFront) };
    for (const sd of ['A', 'B'] as const) {
      const en = sd === 'A' ? 'B' : 'A';
      const enemyFront = front[en];
      if (inBombard) {
        for (const r of bySide(sd).filter(alive)) {
          if (!D.categories[r.u.cat]?.flags?.bombard) continue;
          const chance = r.u.stats.bombard_efficiency || d.BOMBARD_BASE_CHANCE;
          if (rand() >= chance || !enemyFront.length) continue;
          const pool = enemyFront.filter((t: SimReg) => t.sec === MIRROR[r.sec]);
          const pick = pool.length ? pool : enemyFront;
          const tgt = pick[Math.floor(rand() * pick.length)];
          strikes.push([tgt, calcDamage(r, tgt, false, true)]);
        }
        continue;
      }
      for (const r of front[sd]) {
        if (!r.engaged) continue;
        let pool = enemyFront.filter((t: SimReg) => t.sec === MIRROR[r.sec]);
        let flanked = false;
        if (!pool.length) { pool = enemyFront; flanked = true; }
        if (!pool.length) continue;
        const engagedPool = pool.filter((t: SimReg) => t.engaged);
        const pick = engagedPool.length ? engagedPool : pool;
        const tgt = pick[Math.floor(rand() * pick.length)];
        strikes.push([tgt, calcDamage(r, tgt, flanked, false)]);
      }
    }
    for (const [tgt, dmg] of strikes) {
      tgt.men = Math.max(0, tgt.men - dmg.str * d.REGIMENT_SIZE);
      tgt.morale = Math.max(0, tgt.morale - dmg.mor);
    }

    // hourly morale drain on engaged units
    if (!inBombard) for (const sd of ['A', 'B'] as const)
      for (const r of front[sd]) if (r.engaged) r.morale = Math.max(0, r.morale - d.COMBAT_HOURLY_MORALE_TICK);

    // collapse checks
    for (const r of regs) {
      if (!r.broken && (r.men <= 0.5 || r.morale <= P[r.side].maxMorale * d.MORALE_COLLAPSE_THRESHOLD)) {
        const destroyed = r.men <= 0.5;
        r.broken = true; r.engaged = false;
        log?.push(`h${hour}  ${r.side} ${r.u.name} ${destroyed ? 'destroyed' : 'breaks (morale)'}`);
      }
    }
    // voluntary retreat after the lock, on the player-set threshold
    if (hour >= d.MINIMUM_COMBAT_DURATION && !winner) {
      for (const sd of ['A', 'B'] as const) {
        const front = bySide(sd).filter(inFront);
        if (!front.length || !P[sd].retreat) continue;
        const avg = front.reduce((t, r) => t + r.morale / P[sd].maxMorale, 0) / front.length;
        if (avg < P[sd].retreat) {
          winner = sd === 'A' ? 'B' : 'A';
          log?.push(`h${hour}  ${sd} retreats (avg front morale ${(avg * 100).toFixed(0)}%)`);
        }
      }
    }
    if (!winner) {
      const aCan = bySide('A').some(canFight);
      const bCan = bySide('B').some(canFight);
      if (!aCan && !bCan) winner = 'draw';
      else if (!aCan) winner = 'B';
      else if (!bCan) winner = 'A';
    }
    if (winner) break;
  }
  if (!winner) winner = 'draw';
  // retreat damage on the loser's survivors
  if (winner === 'A' || winner === 'B') {
    const loser = winner === 'A' ? 'B' : 'A';
    for (const r of bySide(loser)) if (r.men > 0) r.men *= 1 - d.RETREAT_STRENGTH_DAMAGE;
  }
  const lost = {
    A: start.A - bySide('A').reduce((t, r) => t + r.men, 0),
    B: start.B - bySide('B').reduce((t, r) => t + r.men, 0),
  };
  log?.push(`— ${winner === 'draw' ? 'mutual collapse' : `Army ${winner} wins`} after ${hour}h; ` +
    `A lost ${Math.round(lost.A)}, B lost ${Math.round(lost.B)}`);
  return { winner, hours: hour, lost, start };
}
