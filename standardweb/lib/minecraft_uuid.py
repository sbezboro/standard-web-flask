import json

import requests


def lookup_usernames(usernames):
    data = json.dumps([{
        'name': username,
        'agent': 'minecraft'
    } for username in usernames])

    headers = {
        'Content-Type': 'application/json'
    }

    resp = requests.post('https://api.mojang.com/profiles/page/1',
                         data=data,
                         headers=headers)

    return resp.json()["profiles"]


def lookup_username(username):
    result = lookup_usernames([username])

    if result:
        return result[0]['id']

    return None
