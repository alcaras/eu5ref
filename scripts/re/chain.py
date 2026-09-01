"""Do orphan advances chain to each other, as ConstructTree implies?
For each Discovery focus advance, which OTHER focus advances of the same age
are present in every country that has it?"""
import json, collections
sets=[set(x) for x in json.load(open('.toolbin/re/sets1494.json'))]
adv=json.load(open('src/data/advances.json'))['entities']
by={e['id'].split(':',1)[1]: e for e in adv}
name=lambda k: by[k]['name'] if k in by else k
focus={k for k,e in by.items() if e['data'].get('specialization')}
counts=collections.Counter()
for s in sets:
    for a in s: counts[a]+=1
for k,e in sorted(by.items(), key=lambda kv: kv[0]):
    if not e['data'].get('specialization') or e['facets']['age']!='Discovery': continue
    have=[s for s in sets if k in s]
    if len(have)<5: continue
    inter=set.intersection(*have)-{k}
    kin=sorted(inter & focus, key=lambda x: counts[x])
    print(f"{name(k):<30} {e['data']['specialization']}  n={len(have):<4} "
          f"focus ancestors: {[name(x) for x in kin] or '—'}")
