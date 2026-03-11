import requests

gamma = "https://gamma-api.polymarket.com/"
gamma_events = "https://gamma-api.polymarket.com/events"
params = {'active': "true", 'closed': 'false', 'limit': 5 }

test = requests.get(gamma_events, params=params)
result = test.json()

one_event = result[0]
for key in one_event:
    print(key, one_event[key])