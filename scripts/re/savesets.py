"""Extract each country's researched_advances set from a melted EU5 save."""
import sys, json, collections
path=sys.argv[1]
sets=[]
cur=None
with open(path, 'r', errors='replace') as f:
    for line in f:
        s=line.strip()
        if cur is None:
            if s == 'researched_advances={':
                cur=set()
        else:
            if s == '}':
                if cur: sets.append(cur)
                cur=None
            elif s.endswith('=yes'):
                cur.add(s[:-4])
print(f'{len(sets)} countries, {len(set().union(*sets)) if sets else 0} distinct advances', file=sys.stderr)
json.dump([sorted(x) for x in sets], open(sys.argv[2],'w'))
