"""Reproduce the advance-tree layout the game builds at DB load.

Every age's tech screen is a forest: the age's `depth = 0` advances are the
roots, an advance with `requires = x` hangs under x, and `in_tree_of = x`
asks for a slot somewhere in x's tree. That leaves 383 advances — every focus
advance among them — that declare none of those, yet the screen draws each
one inside one of the age's trees, and (as long as the files don't change)
always in the same place.

That placement is not random and not per-country: the game runs one
deterministic packing pass over the whole advance database when it loads,
seeded with a constant, and every country sees the same tree with its
non-applicable nodes hidden. This module re-runs that pass over the game
files so the placement can be published as data instead of asking players
to screenshot every tree. What it does, in the engine's order:

  1. roots: the age's `depth = 0` advances become the age's trees, in
     database order (files sorted by name, definitions in file order).
  2. declared children (`requires`) whose parent is already placed and
     has at most one child attach immediately; the rest are deferred.
  3. `in_tree_of` advances attach, one at a time in a seeded-random pop
     order, to the best free slot inside the named tree.
  4. the age's undeclared advances are rotated so that each tree that is
     short of its quota (age size ÷ root count) gets filled first, then
     each one takes the best free slot anywhere in the age.
  5. the deferred declared children attach once their parent exists.
  6. finally the non-generic advances (focus `for`, `government`,
     `country_type`, or any `potential` trigger) attach: under their
     `requires` if declared, else the best slot in their `in_tree_of`
     tree, else the best slot in the age.

"Best free slot" walks down from a node: a node may hold 2 generic children
at depth 0–1, then 2 at every depth ≡ 1 (mod 3) and 1 otherwise; if it is
full the search recurses into the child with the fewest descendants.
Non-generic nodes (a hidden advance may be hidden for you) never receive
slotted children and are not counted against a slot.

Verified against the live game, 1.3.11: Bookkeeping under Medical Schools,
Humanism + Formalized Officer Corps under Two-decker, Merchant Fleets in
Enlightenment, Heavy Frigate + Buffer States under Global Ambitions, Campaign
Logistics Planning + Additional Loyalist Recruitment under Rights of Man, and a
full Age of Discovery screenshot (every visible node and edge of the Surgery,
New World, Printing Press and Pike and Shot trees, incl. Poland's own
national advances slotted where the game draws them). `content_priority`
and `allow` were tried as the fourth generic test and rejected (0/8 each);
`potential` gives the matches above and no "prerequisite not in the same
tree" fallbacks.

Usage:  python3 scripts/lib/layout.py [--sort ascii|fold] [--gate …] [--json out]
"""
import argparse, glob, json, os, re, sys

MASK = 0xffffffff
SEED = 0x441e9e04            # the constant the game seeds the pass with

# ---------------------------------------------------------------- parsing
TOK = re.compile(r'"[^"]*"|[^\s{}=#]+|[{}=]|#[^\n]*')

def tokens(text):
    for m in TOK.finditer(text):
        t = m.group(0)
        if t.startswith('#'):
            continue
        yield t

FIELDS = ('age', 'depth', 'requires', 'in_tree_of', 'for', 'government',
          'country_type', 'content_priority', 'allow_children', 'potential', 'allow')

def parse_file(path):
    """Top-level blocks → list of (key, {field: value}) in definition order."""
    out = []
    toks = list(tokens(open(path, encoding='utf-8-sig').read()))
    i, n = 0, len(toks)
    while i < n:
        key = toks[i]
        if i + 2 < n and toks[i+1] == '=' and toks[i+2] == '{':
            depth, j, fields = 1, i + 3, {}
            while j < n and depth:
                t = toks[j]
                if t == '{':
                    depth += 1
                elif t == '}':
                    depth -= 1
                elif depth == 1 and t in FIELDS and j + 1 < n and toks[j+1] == '=':
                    v = toks[j+2]
                    fields[t] = '{}' if v == '{' else v.strip('"')
                j += 1
            out.append((key, fields))
            i = j
        else:
            i += 1
    return out

def load(root, sort):
    ages = [k for k, _ in parse_file(os.path.join(root, 'common/age/00_default.txt'))]
    files = glob.glob(os.path.join(root, 'common/advances/*.txt'))
    keyf = (lambda p: os.path.basename(p)) if sort == 'ascii' else (lambda p: os.path.basename(p).lower())
    advs = []
    for p in sorted(files, key=keyf):
        for key, f in parse_file(p):
            advs.append(dict(
                key=key, file=os.path.basename(p),
                age=ages.index(f['age']) if f.get('age') in ages else None,
                depth=int(f.get('depth', -1)),
                requires=f.get('requires'), in_tree_of=f.get('in_tree_of'),
                focus=f.get('for'), gov=f.get('government'),
                ctype=f.get('country_type'), cp=int(f.get('content_priority', 0)),
                potential='potential' in f, allow='allow' in f,
                allow_children=f.get('allow_children', 'yes') != 'no'))
    return ages, advs

# ---------------------------------------------------------------- engine
class Node:
    __slots__ = ('depth', 'parent', 'adv', 'children', 'desc')
    def __init__(self, depth, parent, adv):
        self.depth, self.parent, self.adv = depth, parent, adv
        self.children, self.desc = [], 0

class Layout:
    def __init__(self, advs, gate='potential'):
        self.by_key = {a['key']: a for a in advs}
        self.gate = gate           # which field the 4th generic test reads
        self.node_of = {}          # advance key → Node
        self.NULL = dict(key=None, focus=None, gov=None, ctype=None, cp=0, potential=False, allow=False)

    def generic(self, a):
        return (a['focus'] is None and a['gov'] is None and a['ctype'] is None
                and (self.gate is None or not a[self.gate]))


    # --- helpers mirrored from the binary
    def attach(self, parent, adv):
        node = Node(parent.depth + 1, parent, adv)
        parent.children.append(node)
        p = parent
        while p is not None:
            p.desc += 1
            p = p.parent
        self.node_of[adv['key']] = node
        return node

    def count_kids(self, node):
        return sum(1 for c in node.children if self.generic(c.adv))

    def find_slot(self, node):
        if not self.generic(node.adv):
            return None
        d = node.depth
        cap = 2 if d < 2 else (2 if d % 3 == 1 else 1)
        if self.count_kids(node) < cap:
            return node
        best, best_desc = None, 1000000
        for c in node.children:
            s = self.find_slot(c)
            if s is not None and c.desc < best_desc:
                best, best_desc = s, c.desc
        return best

    def lookup(self, key):
        return self.node_of.get(key) if key else None

    # --- the RNG (squirrel-style hash over a counter)
    @staticmethod
    def draw(K, c):
        x = (K - c * 0x4ad685b3) & MASK
        x = (((x >> 8) ^ x) + 0x68e31da4) & MASK
        x = ((((x << 8) & MASK) ^ x) * 0x1b56c4e9) & MASK
        x = (((x >> 8) ^ x) * 0x92d68ca2) & MASK
        return ((x >> 8) ^ x) & 0x7fffffff

    def build_age(self, age_list, seed=SEED):
        K = (0x5ea6ba9f - seed) & MASK
        c = seed
        age_root = Node(0, None, self.NULL)
        roots, listA, listB, listC, listD = [], [], [], [], []
        for a in age_list:
            if a['depth'] == 0 and not a['requires']:
                roots.append(a)
            elif self.generic(a):
                if not a['requires']:
                    (listC if not a['in_tree_of'] else listB).append(a)
                else:
                    listA.append(a)
            else:
                listD.append(a)
        # 1. roots (the recursive fill is a no-op for allow_children = yes)
        for r in roots:
            self.attach(age_root, r)
            c += 1
        # 2. declared children, DB order, parents with ≤1 child only
        deferred = []
        for a in listA:
            n = self.lookup(a['requires'])
            if n is None or len(n.children) > 1:
                deferred.append(a)
            else:
                self.attach(n, a)
        # 3. in_tree_of, random pop order
        while listB:
            r = self.draw(K, c); c += 1
            a = listB.pop(r % len(listB))
            n = self.lookup(a['in_tree_of'])
            slot = self.find_slot(n) if n is not None else None
            if slot is None:
                listC.append(a)
            else:
                self.attach(slot, a)
        if not age_root.children:
            raise RuntimeError('Advance tree failed to generate')
        # 5. quota rotation (the fill itself is a no-op; the rotation is not)
        quota = len(age_list) // len(age_root.children)
        for t in age_root.children:
            need = quota - (t.desc + 1)
            if need > 0:
                moved = listC[:need]
                del listC[:need]
                c += 1
                listC.extend(moved)
        if listC:
            c += 1
        # 7. orphans: declared parent if any (never, here) else balanced slot
        for a in listC:
            n = self.lookup(a['requires'])
            if n is None:
                n = self.find_slot(age_root)
            self.attach(n, a)
        listC = []
        # 8. ping-pong the deferred declared children until parents exist
        budget = 2 * len(deferred)
        while True:
            if deferred:
                nxt = []
                for a in deferred:
                    n = self.lookup(a['requires'])
                    if n is None:
                        nxt.append(a)
                    else:
                        self.attach(n, a)
                deferred, listC = [], nxt
            elif listC:
                nxt = []
                for a in listC:
                    n = self.lookup(a['requires'])
                    if n is None:
                        nxt.append(a)
                    else:
                        self.attach(n, a)
                deferred, listC = nxt, []
            else:
                break
            budget -= 1
            if budget < 0 and deferred:
                for a in deferred:
                    print(f"  ! '{a['key']}' has a pre-requisite not in the same tree", file=sys.stderr)
                break
        # 9. non-generic advances (focus / government / country_type / priority)
        for a in listD:
            n = None
            if a['requires']:
                n = self.lookup(a['requires'])
            elif a['in_tree_of']:
                t = self.lookup(a['in_tree_of'])
                n = self.find_slot(t) if t is not None else None
            if n is None:
                n = self.find_slot(age_root)
            self.attach(n, a)
        return age_root

def run(root, sort='fold', gate='potential'):
    """→ {advance key: {age, tree, tree_index, parent, depth, declared}}.

    `tree` is the key of the root the advance is drawn under, `tree_index`
    that root's left-to-right position in the age, `parent` the node it
    hangs off (its `requires` when declared, else the slot the pass gave
    it), `declared` whether the files fix that parent themselves and
    `tree_declared` whether they at least fix the tree (`in_tree_of`).
    """
    ages, advs = load(root, sort)
    lay = Layout(advs, gate)
    placed = {}
    for i, age in enumerate(ages):
        age_list = [a for a in advs if a['age'] == i and a['key'] not in placed]
        if not age_list:
            continue
        age_root = lay.build_age(age_list)
        def walk(n, tree, ti, parent):
            for slot, ch in enumerate(n.children):
                t = tree or ch.adv['key']
                declared = bool(ch.adv['requires'])
                placed[ch.adv['key']] = dict(age=age, tree=t, tree_index=ti, parent=parent,
                                             depth=ch.depth, slot=slot, declared=declared,
                                             tree_declared=declared or bool(ch.adv['in_tree_of']))
                walk(ch, t, ti, ch.adv['key'])
        for ti, tree in enumerate(age_root.children):
            placed[tree.adv['key']] = dict(age=age, tree=tree.adv['key'], tree_index=ti, slot=ti,
                                           parent=None, depth=1, declared=True, tree_declared=True)
            walk(tree, tree.adv['key'], ti, tree.adv['key'])
    return placed

# Placements read off the live game (1.3.11) — the regression set.
CHECKS = [
    ('bookkeeping', 'parent', 'medical_school_advance'),
    ('formalized_officer_corps', 'parent', 'unlock_twodecker_advance'),
    ('humanism', 'parent', 'unlock_twodecker_advance'),
    ('merchant_power_from_maritime_rev_dip_choice', 'tree', 'enlightenment_advance'),
    ('unlock_heavy_frigate_advance', 'parent', 'power_projection_advance_6'),
    ('buffer_states', 'parent', 'power_projection_advance_6'),
    ('global_supply_limit_modifier_advance_6', 'parent', 'rights_of_man'),
    ('additional_loyalist_recruitment', 'parent', 'rights_of_man'),
    # Age of Discovery screenshot, Poland: every visible node of all four trees
    ('military_traditions', 'parent', 'dry_dock_advance'),
    ('mendicant_orders', 'parent', 'diplomatic_training'),
    ('polish_renaissance', 'parent', 'print_culture'),
    ('supremus_dux_lithuaniae', 'parent', 'print_culture'),
    ('wojewodztwo_advance', 'parent', 'pike_square'),
    ('reform_church_music', 'parent', 'artists_advance_discovery'),
]

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='game/in_game')
    ap.add_argument('--sort', default='fold', choices=['ascii', 'fold'])
    ap.add_argument('--gate', default='potential', choices=['potential', 'allow', 'cp', 'none'],
                    help='which field the fourth generic test reads')
    ap.add_argument('--json')
    args = ap.parse_args()
    placed = run(args.root, args.sort, None if args.gate == 'none' else args.gate)
    ok = 0
    for key, what, want in CHECKS:
        got = placed.get(key, {}).get(what)
        ok += got == want
        tag = 'ok ' if got == want else 'XX '
        print(f"{tag} {key}.{what} = {got}  (expected {want})")
    print(f"{ok}/{len(CHECKS)} checks; {len(placed)} advances placed", file=sys.stderr)
    if args.json:
        json.dump(placed, open(args.json, 'w'), indent=0)
