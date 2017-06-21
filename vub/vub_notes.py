#!/usr/bin/env python3
"""
 zobrazi zoznam otvorenych OSM poznamok (notes) uzivatela
 VUBatm_bot, ktory sa pouziva na import bankomatov VUB
"""
import requests
import bs4

bot_name = 'VUBatm_bot'


def load_table():
    index = 1
    while True:
        # print('index: {}'.format(index))
        r = requests.get('http://www.openstreetmap.org/user/'
                         '{0}/notes?page={1}'.format(bot_name,
                                                     index))
        soup = bs4.BeautifulSoup(r.text, 'html5lib')
        table = soup.select('.note_list')[0]
        if 'img alt' in str(table):
            yield(table)
            index += 1
            continue
        else:
            break


for table in load_table():
    for tablerow in table.findAll('tr')[1:]:
        status = tablerow.findAll('td')[0].img['alt']
        if 'open' not in status:
            continue
        noteid = tablerow.findAll('td')[1].text
        desc = tablerow.findAll('td')[3].text
        print(noteid, desc)
