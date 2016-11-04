#!/usr/bin/env python3
# vim: set fileencoding=utf8
"""
kontroluje uzly v OSM otagovane ako
amenity=atm (bankomaty), konkretne:

 - tag operator prazdny, ale name/ref tag obsahuje hodnotu
 - vsetky najdene hodnoty operator tagu
 - chyby vo formate ref pre znamych operatorov
 - bankomaty s neznamou (mozno nespravne zadanou) hodnotou
   operator tagu
 - bankomaty s tagom brand
 - vsetky hodnoty tagu name
 - pre znamych operatorov zobrazi percentualny pomer zmapovane/vsetky

celkove pocty bankomatov su zvacsa preberane zo stranok jednotlivych
financnych ustavov.

skript je mozne spustat priebezne pre vcasne odhalenie problemov a ich
rucnu opravu.

checks atm nodes in slovakia and reports
the following issues/stats:

 - name/ref tag set but operator tag empty
 - all operator tag values
 - errors in refs for known operators
 - unknown (possibly misspelled) operator values
 - atms with brand tag
 - name tag values
 - for known operators atms shows ratio of mapped/total%

"""
import overpass
import locale
import itertools
import re
import matplotlib.pyplot as plt
import numpy as np

""" zoznam povolenych operatorov s informaciou o celkovom pocte
    bankomatov (aktualizovane k septembru 2016) a regularnym
    vyrazom popisujucim tvar ref tagu (identifikator bankomatu)
    """
known_operators = {'CryptoDiggers Team':     (1, '', 'CryptoDig.'),
                   'ČSOB':                   (262, r'S2CS[0-9]{3}[A-Z]',
                                              'ČSOB'),
                   'OTP banka':              (140, r'S6AI[0-9]{4}[A-Z]',
                                              'OTP'),
                   'Poštová banka':          (217, r'S6AP[0-9]{3}[A-Z]',
                                              'Poštová b.'),
                   '0011 s.r.o.':            (1, '', '0011 sro'),
                   'Decentral Plan s.r.o.':  (1, '', 'Decentr'),
                   'Prima banka':            (226, r'S6AK[0-9]{3}[A-Z]',
                                              'Prima'),
                   'Sberbank':               (75,  r'S6AL[0-9]{2,3}[A-Z]',
                                              'Sberbank'),
                   'Tatra banka':            (309, r'TATN[0-9]{3}[A-Z]',
                                              'TB'),
                   'UniCredit Bank':         (150, r'S6AN[0-9]{3}[A-Z]',
                                              'UniCredit'),
                   'Slovenská sporiteľňa':   (677, r'\d{4}',
                                              'SLSP'),
                   'VÚB':                    (572, r'S6AV[0-9]{3}[A-Z]',
                                              'VÚB')}

# locale nastavujeme kvoli abecednemu radeniu
locale.setlocale(locale.LC_ALL, 'sk_SK.utf8')
all_tags = []
ids_with_note_tag = []


def query_sk(filter):
    """
    urobi overpass query na uzemi slovenska
    (definovane relaciou s id 14296) a vrati
    vysledok ako dict() objekt
    """
    query = '''
    area(3600014296);
    (
      ._;
      )->.boundaryarea;
      {}'''.format(filter)
    api = overpass.API(timeout=600,
                       endpoint='http://api.openstreetmap.fr/oapi/interpreter')
    result = api.Get(query)["features"]
    return result

result = query_sk('''node(area.boundaryarea)
                     ["amenity"="atm"]
                     ["operator"!~".*"]
                     ->.atm;
                     node(area.boundaryarea)
                     ["amenity"="bank"]
                     ["atm"="yes"]
                     ["operator"]
                     ->.bank;
                     (.atm; .bank; >;);''')

name_or_ref_wo_operator = []

for atmdata in result:
    name = atmdata['properties'].get('name')
    ref = atmdata['properties'].get('ref')
    if atmdata['properties'].get('note'):
        ids_with_note_tag.append(id)
    all_tags.extend(list(atmdata['properties'].keys()))
    id = atmdata['id']
    if (name or ref) and 'operator' not in atmdata['properties']:
        name_or_ref_wo_operator.append((name, id))

print('Prazdny operator tag + neprazdny name/ref tag:',
      sorted(name_or_ref_wo_operator))

result = query_sk('''node(area.boundaryarea)
                     ["amenity"="atm"]
                     ["operator"]
                     ->.atm;
                     node(area.boundaryarea)
                     ["amenity"="bank"]
                     ["operator"]
                     ["atm"="yes"]
                     ->.bank;
                     (.atm; .bank; >;);''')

all_operators = []
unknown_operators = []
# operator_refcount = {}
# [ref w/o fixme, ref w/fixme, fixme]
operator_counts = {}


def add_one(operator, index):
    """
    add 1 to list x[index] or set if such
    index does not exist
    """
    global operator_counts
    try:
        operator_counts[operator][index] += 1
    except KeyError:
        operator_counts[operator] = [0, 0, 0]
        operator_counts[operator][index] = 1

REFNOFIXME, REFFIXME, NOREF = 0, 1, 2

for atmdata in result:
    id = atmdata['id']
    operator = atmdata['properties']['operator']
    all_tags.extend(list(atmdata['properties'].keys()))
    if atmdata['properties'].get('note'):
        ids_with_note_tag.append(id)

    if atmdata['properties'].get('ref'):
        if atmdata['properties'].get('fixme'):
            add_one(operator, REFFIXME)
        else:
            add_one(operator, REFNOFIXME)
    else:
        add_one(operator, NOREF)

    if operator not in known_operators.keys():
        unknown_operators.append(id)
    else:
        if 'ref' in atmdata['properties'].keys():
            ref = atmdata['properties']['ref']
            rex = re.compile(known_operators[operator][1])
            if not rex.match(ref):
                print('ref {} nesedi s reg. vyrazom {} ({})'.format(ref,
                                                                    rex,
                                                                    id))
    all_operators.append(operator)

all_operators.sort(key=locale.strxfrm)
unique_operators = set(sorted(all_operators, key=locale.strxfrm))
unique_operators = list(unique_operators)
unique_operators.sort(key=locale.strxfrm)


# [ osm_count ] [ ref_count ]
operator_count = {}

print('Zoznam operatorov:', unique_operators)

print('{operator:<25} {actual_count:>3} '
      '({refcount:>3})/{total:>3}'
      ' {ratio:>3.0s}% '
      '({refcountratio:>3s}%)'.format(operator='Nazov',
                                      actual_count='\N{Greek capital letter sigma}OSM',
                                      refcount='ref',
                                      total='\N{Greek capital letter sigma}',
                                      ratio='',
                                      refcountratio='ref'))
for operator, group in itertools.groupby(all_operators):
    actual_count = len(list(group))
    if operator in known_operators.keys():
        total = known_operators[operator][0]
        ratio = float(actual_count) / total
    else:
        total = 0
        ratio = 0
    refcount = operator_counts.get(operator, [0])[0] + operator_counts.get(operator, [0])[1]
    if refcount:
        refcountratio = float(refcount) / total
    else:
        refcountratio = 0
    operator_count[operator] = [actual_count, refcount]
    print('{operator:<25} {actual_count:>3} ({refcount:>3})/{total:>3}'
          '  {ratio:>4.0%} ({refcountratio:>4.0%})'
          ''.format(**locals()))

width = 0.35

# discard operators that are not identified
unique_operators = [x for x in unique_operators if x in known_operators.keys()]

N = len(unique_operators)
ind = list(range(N))

osmCount = [(operator_count[x][0] - operator_count[x][1]) * 100 / known_operators[x][0]
            for x in unique_operators]
refnofixmeCount = [operator_counts[x][REFNOFIXME] * 100 / known_operators[x][0]
                   for x in unique_operators]
reffixmeCount = [operator_counts[x][REFFIXME] * 100 / known_operators[x][0]
                 for x in unique_operators]
missCount = [(known_operators[x][0] - operator_count[x][0]) * 100 / known_operators[x][0]
             for x in unique_operators]

p1 = plt.barh(ind, osmCount, width, color='g')
p2 = plt.barh(ind, refnofixmeCount, width, left=osmCount, color='darkgreen')
p3 = plt.barh(ind, reffixmeCount, width, left=np.add(osmCount,
                                                     refnofixmeCount),
              color='darkgreen', hatch='X')
p4 = plt.barh(ind,
              missCount,
              width,
              # left=np.add(refCount, osmCount),
              left=np.add(np.add(osmCount, reffixmeCount), refnofixmeCount),
              fill='left',
              color='r')

plt.ylabel('Banka')
plt.title('Bankomaty v OSM podľa bánk', fontname='Arial')
plt.yticks(ind, [known_operators[x][2] for x in unique_operators])
plt.xticks(list(range(0, 101, 10)))
plt.legend((p1[0], p2[0], p3[0], p4[0]), ('OSM bez ref',
                                          'OSM ref',
                                          'OSM ref + fixme',
                                          'Nie je v OSM'),
           ncol=4,
           markerscale=0.5,
           fontsize=6
           )

plt.show()

print('Id neznamych operatorov:', unknown_operators)

result = query_sk('''node(area.boundaryarea)
                     ["amenity"="atm"]
                     ["brand"]
                     ->.atm;
                     (.atm; >;);''')

brand_tags = []

for atmdata in result:
    brand = atmdata['properties']['brand']
    brand_tags.append(brand)

print('Zoznam bankomatov s tagom brand:', list(brand_tags))

result = query_sk('''node(area.boundaryarea)
                     ["amenity"="atm"]
                     ["name"]
                     ->.atm;
                     (.atm; >;);''')

names = []
names_ids = []

for atmdata in result:
    name = atmdata['properties']['name']
    id = atmdata['id']
    names.append(name)
    names_ids.append(id)

print('Name tagy:',
      sorted(names))

print('Id objektov s name tagom:',
      sorted(names_ids))

all_tags.sort()
print('Pocetnosti tagov:')
for tag, group in itertools.groupby(all_tags):
    print('{} ({})'.format(tag,
                           len(list(group))))

print('ID bankomatov s note tagom', ids_with_note_tag)
