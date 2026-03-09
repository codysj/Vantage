import requests

gamma = "https://gamma-api.polymarket.com/"

markets = requests.get("https://gamma-api.polymarket.com/events?active=true&closed=false&limit=5")
titles = markets.json()
print(titles)
'''
for item in titles:
    print(item['title'])
for key in titles[0]:
    print(key, titles[0][key])
'''