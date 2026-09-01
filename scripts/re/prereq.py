"""Infer the real prerequisite chain of an advance from many countries' researched sets.

If every country that has A also has A's ancestors, then
  ancestors(A) ⊆ ∩{S : A ∈ S}
Universal advances (everyone has them) pollute that intersection, so we
subtract the advances that essentially everyone has.
"""
import json, sys, collections
sets=[set(x) for x in json.load(open('.toolbin/re/sets1494.json'))]
adv=json.load(open('src/data/advances.json'))['entities']
by={e['id'].split(':',1)[1]: e for e in adv}
name=lambda k: by[k]['name'] if k in by else k
declared={k: [r['id'].split(':',1)[1] for r in e['data']['requires']] for k,e in by.items()}

counts=collections.Counter()
for s in sets:
    for a in s: counts[a]+=1
n=len(sets)

def implied(a):
    have=[s for s in sets if a in s]
    if not have: return None, 0
    inter=set.intersection(*have) - {a}
    return inter, len(have)

for target in sys.argv[1:]:
    inter, k = implied(target)
    if inter is None:
        print(f'{target}: never researched in this save'); continue
    # drop advances that nearly everyone has - they are not evidence
    strong = sorted(inter, key=lambda x: counts[x])
    print(f'\n== {name(target)} ({target})  researched by {k}/{n} countries')
    print(f'   declared requires: {[name(x) for x in declared.get(target,[])] or "none"}')
    print(f'   implied ancestors: {len(inter)}')
    for x in strong[:12]:
        print(f'      {counts[x]:>5}/{n}  {name(x):<38} {x}')
