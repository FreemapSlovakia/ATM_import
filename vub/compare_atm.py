#!/usr/bin/env python
"""
porovna stary a novy CSV export a zobrazi
zmeny (adresa, poloha)

vyzaduje zadanie stareho a aktualneho csv suboru ako argumenty
"""
import csv
import sys
import overpass
from collections import namedtuple, defaultdict
from operator import attrgetter
from geopy.distance import vincenty

atmdata = namedtuple('atmdata', ['street',
                                 'position',
                                 'lat',
                                 'lon',
                                 'cashin',
                                 'nonstop',
                                 'city'])

column_names = ['Street', "ATM's position", 'Coordinate/  latitude', 'Coordinate/   longitude', 'Cash-in', '0-24h', 'City']
# list of atm refs to modify and delete
refs_change = set()
refs_delete = set()

query_template = '''
area(3600014296);
(
  ._;
)->.boundaryarea;
(
{}
);
(
  ._;
>;
);'''

api = overpass.API(timeout=600)


def feed_atm_data(fname):
    output = {}
    with open(fname, 'r') as csvfile:
        csvr = csv.DictReader(csvfile)
        for row in csvr:
            data = []
            for column_name in column_names:
                data.append(row[column_name])
            code = row['Identifier/ code']
            output[code] = atmdata(*data)
    return output


def t(title):
    print('\n== {} =='.format(title))


if len(sys.argv) != 3:
    print('Exactly two arguments required: OLD_list.csv NEW_list.csv')
    sys.exit(1)

old_atms = feed_atm_data(sys.argv[1])
new_atms = feed_atm_data(sys.argv[2])

t('New refs found (candidates for addition)')
for atm in set(new_atms) - set(old_atms):
    tmp_dict = (new_atms[atm])._asdict()
    # we are not allowed to use these so let's not tease ourselves
    tmp_dict.pop('lat')
    tmp_dict.pop('lon')
    tmp_dict.pop('city')
    print(atm, [' = '.join((x, y)) for x, y in tmp_dict.items()])

t('Refs gone (candidates for deletion)')
for atm in set(old_atms) - set(new_atms):
    refs_delete.update([atm])
    print(atm)

changes = defaultdict(list)
# for atms present in both sets - compare attributes
for atm in set(new_atms).intersection(old_atms):
    for attribute in set(atmdata._fields) - {'lat', 'lon', 'city'}:
        getter = attrgetter(attribute)
        old_atm = old_atms[atm]
        new_atm = new_atms[atm]
        if getter(old_atm) != getter(new_atm):
            changes[attribute].append([atm, attribute, getter(old_atm),
                                      getter(new_atm)])
            refs_change.update([atm])

t('Changed positions')
for atm in set(new_atms).intersection(old_atms):
    old_lat, old_lon = old_atms[atm].lat, old_atms[atm].lon
    # workaround for error in input data
    new_lat, new_lon = new_atms[atm].lat, new_atms[atm].lon
    old_lat = old_lat.replace(',', '')
    new_lat = new_lat.replace(',', '')
    if old_lat != new_lat or old_lon != new_lon:
        distance = vincenty((old_lat, old_lon), (new_lat, new_lon)).m
        refs_change.update([atm])
        print('{} moved by {:7.1f} meters'.format(atm, distance))

# output the collected information
for attribute in set(atmdata._fields) - {'lat', 'lon', 'city'}:
    t('Changes ({0})'.format(attribute))
    for change_data in changes[attribute]:
        atm, attribute, old, new = change_data
        print('{atm} - {old} -> {new}'.format(**locals()))

t('Node ids for JOSM (Ctrl - Shift - O)')
for chg_type in [refs_delete, refs_change]:
    tmp_query = (['node(area.boundaryarea)["ref"="{}"];'.format(x) for x in chg_type])
    tmp_query = '\n'.join(tmp_query)
    query = query_template.format(tmp_query)
    result = api.Get(query)["features"]
    print(','.join([str(x['id']) for x in result]))
