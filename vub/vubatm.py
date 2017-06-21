#!/usr/bin/env python3
"""
Stiahne bankomaty VUB cez overpass, porovna
ich s .csv suborom od banky a zobrazi nejake
statistiky.
"""
import sys
import os
import overpass
import csv
import nominatim
from urllib.parse import quote

query = '''
area(3600014296);\n(\n  ._;\n)->.boundaryarea;node\n  (area.boundaryarea)\n
["amenity"="atm"]\n  ["operator"~"V.*B"]\n->.atm;\nnode\n
(area.boundaryarea)\n  ["amenity"="bank"]\n  ["operator"~"V.*B"]\n
["atm"="yes"]\n->.bank;\nnode\n  (area.boundaryarea)\n  ["amenity"="bank"]\n
["name"~"V.*B"]\n  ["atm"="yes"]\n->.bank2;\n(\n  .bank;\n  .bank2;\n  .atm;\n
>;\n);'''

api = overpass.API(timeout=600)

if len(sys.argv) < 2:
    print('Specify .csv file with data from VUB')
    sys.exit(1)

input = sys.argv[1]
if not os.path.exists(input):
    raise OSError('{} does not exist!'.format(input))

result = api.Get(query)["features"]

has_ref = []
no_ref = []

osm_data = []
vub_data_refs = []

vub_data_location = {}
vub_data_features = {}

for atmdata in result:
    if 'ref' in atmdata["properties"]:
        # has_ref.append(atmdata['id'])
        osm_data.append(atmdata['properties']['ref'])
    else:
        no_ref.append(atmdata['id'])

with open(input, 'r') as csvfile:
    csvr = csv.DictReader(csvfile)
    for row in csvr:
        code = row['Identifier/ code']
        vub_data_refs.append(code)
        vub_data_location[code] = [row['Street'] + ', ' + row['City'],
                                   row["ATM's position"]]
        vub_data_features[code] = {'cash_in': row['Cash-in'].lower(),
                                   'nonstop': row['0-24h'].lower()}

nonstop_tag_add = []
cashin_tag_add = []

for osmdata in result:
    try:
        ref = osmdata['properties']['ref']
    except KeyError:
        continue
    id = osmdata['id']
    if ref not in vub_data_features:
        print('Ref "{0}" in OSM but not in csv file (id: {1})'.format(ref,
                                                                      id))
        continue
    if 'cash_in' not in osmdata['properties']:
        if vub_data_features[ref]['cash_in'] in 'yes':
            print('Should add cash_in={0} to {1}'.format(vub_data_features[ref]['cash_in'], ref))
            cashin_tag_add.append(id)
    else:
        if osmdata['properties']['cash_in'] != vub_data_features[ref]['cash_in']:
            print('cash_in conflict {0}'.format(ref))
            sys.exit()

    if 'opening_hours' not in osmdata['properties']:
        if vub_data_features[ref]['nonstop'] in 'yes':
            print('Will add opening_hours=24/7 to {0}'.format(ref))
            nonstop_tag_add.append(id)
    else:
        if osmdata['properties']['opening_hours'] != '24/7' and vub_data_features[ref]['nonstop'] == 'yes':
            print('opening_hours conflict {0}'.format(ref))
            sys.exit()

print("Id bankomatov na pridanie tagu opening_hours = 24/7:")
print(','.join([str(x) for x in nonstop_tag_add]))
print("Id bankomatov na pridanie tagu cash_in = yes:")
print(','.join([str(x) for x in cashin_tag_add]))
print("has ref: %d, no ref: %d" % (len(osm_data), len(no_ref)))

print("Bankomaty bez ref tagu:")
print(','.join([str(x) for x in no_ref]))

print("Duplicitne ref tagy:")
print([x for x in osm_data if osm_data.count(x) > 1])

to_add = set(vub_data_refs) - set(osm_data)

nomsearch = nominatim.Nominatim()

print("Treba pridat (%s):" % len(to_add))

with open('output.osm', 'w') as f:
    f.write('''<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>\n''')
    f.write('''<osm version="0.6" generator="OsmPad">\n''')

osmid = 0

for x in to_add:
    print(x, end=' ')
    street_city, atm_position = vub_data_location[x]
    print("%s (%s)" % (street_city, atm_position))
    searchresult = nomsearch.query(quote(street_city),
                                   limit=1)
    if searchresult:
        osmid += 1
        searchresult = searchresult[0]
        lat, lon = (searchresult['lat'], searchresult['lon'])
        data = ('<node id="-%s" version="1" '
                'lat="%s" lon="%s">\n') % (osmid, lat, lon)
        data += '  <tag k="amenity" v="atm" />\n'
        data += '  <tag k="operator" v="VÚB" />\n'
        data += '  <tag k="ref" v="%s" />\n' % x
        data += '  <tag k="note" v="%s (%s)" />\n' % (street_city,
                                                      atm_position)
        data += '</node>\n'
        with open('output.osm', 'a') as f:
            f.write(data)

with open('output.osm', 'a') as f:
    f.write('</osm>')
