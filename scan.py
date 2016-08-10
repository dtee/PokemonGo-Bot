#!/usr/bin/python
# -*- coding: utf-8 -*-

import requests
import time

def move_map(lat, lng):
    try:
        req = requests.get('{}/next_loc?lat={}&lon={}'.format(lat, lng))
    except requests.exceptions.ConnectionError:
        return []

    try:
        raw_data = req.json()
    except ValueError:
        return []

def get_sniper():
    try:
        req = requests.get('http://pokesnipers.com/api/v1/pokemon.json')
    except requests.exceptions.ConnectionError:
        return []

    try:
        raw_data = req.json()
        return raw_data
    except ValueError:
        return []

print get_sniper()
