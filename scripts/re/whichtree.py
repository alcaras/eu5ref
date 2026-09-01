"""A tree's root is an ancestor of everything in it, so every country that
researched X must also have researched the root of X's tree. Test each age's
four roots against every focus advance."""
import json, collections, sys
sets=[set(x) for x in json.load(open(sys.argv[1]))]
adv=json.load(open('src/data/advances.json'))['entities']
by={e['id'].split(':',1)[1]: e for e in adv}
name=lambda k: by[k]['name'] if k in by else k
ROOTS={
 'Renaissance':['renaissance_advance','banking_advance','professional_armies_advance','renaissance_development'],
 'Discovery':['new_world_advance','printing_press_advance','pike_and_shot_advance','surgery_advance'],
 'Reformation':['confessionalism_advance','global_trade_advance','artillery_institution_advance','pharmacology_advance'],
 'Absolutism':['manufactories_advance','scientific_revolution_advance','military_revolution_advance','sanitation_advance'],
 'Revolutions':['enlightenment_advance','industrialization_advance','levee_en_masse_advance','vaccination_advance'],
}
for age, roots in ROOTS.items():
    print(f'\n=== {age}')
    for k,e in sorted(by.items()):
        if not e['data'].get('specialization') or e['facets']['age']!=age: continue
        if e['data']['requires']: continue          # declared parent: tree already known
        have=[s for s in sets if k in s]
        if len(have)<3: continue
        surviving=[r for r in roots if all(r in s for s in have)]
        print(f"   {name(k):<30} n={len(have):>4}  possible trees: "
              + (', '.join(name(r) for r in surviving) if surviving else 'NONE'))
