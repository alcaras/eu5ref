"""Better estimator: the parent is the DEEPEST implied ancestor (the candidate
with the largest implied-ancestor set of its own), and national advances are
dropped from the universe because same-country advances are perfectly
correlated and masquerade as ancestors."""
import json, collections, sys
sets=[set(x) for x in json.load(open('.toolbin/re/sets1494.json'))]
adv=json.load(open('src/data/advances.json'))['entities']
by={e['id'].split(':',1)[1]: e for e in adv}
general={k for k,e in by.items() if e['facets']['scope']=='general'}
declared={k:[r['id'].split(':',1)[1] for r in e['data']['requires']] for k,e in by.items()}
GEN_ONLY = '--gen' in sys.argv
if GEN_ONLY:
    sets=[s & general for s in sets]
counts=collections.Counter()
for s in sets:
    for a in s: counts[a]+=1
name=lambda k: by[k]['name'] if k in by else k

cache={}
def implied(a):
    if a in cache: return cache[a]
    have=[s for s in sets if a in s]
    r=(set.intersection(*have)-{a}) if have else set()
    cache[a]=r; return r

ok=bad=skip=0; misses=[]
for k,reqs in declared.items():
    if len(reqs)!=1: continue
    if GEN_ONLY and (k not in general or reqs[0] not in general): continue
    have=[s for s in sets if k in s]
    if len(have)<5: skip+=1; continue
    C=implied(k)
    if not C: skip+=1; continue
    best=max(C, key=lambda c:(len(implied(c)), -counts[c]))
    if best==reqs[0]: ok+=1
    else:
        bad+=1
        if len(misses)<6: misses.append((name(k),name(reqs[0]),name(best)))
tag='general-scope only' if GEN_ONLY else 'all advances'
print(f'{tag}: deepest implied ancestor == declared parent for {ok}/{ok+bad} ({skip} skipped)')
for m in misses: print(f'   {m[0]}: declared={m[1]} inferred={m[2]}')
