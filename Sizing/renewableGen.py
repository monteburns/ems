import requests
import pandas as pd
import json

token = 'a58588336bc2bea77b957ea90fccc444c7d19042'
api_base = 'https://www.renewables.ninja/api/'

s = requests.session()
# Send token header with each request
s.headers = {'Authorization': 'Token ' + token}


##
# PV 
##

url = api_base + 'data/pv'

args = {
    'lat': 41.31846539501719,
    'lon': 27.912727392607966,
    'date_from': '2019-01-01',
    'date_to': '2019-12-31',
    'dataset': 'merra2',
    'capacity': 1.0,
    'system_loss': 0.1,
    'tracking': 0,
    'tilt': 35,
    'azim': 180,
    'format': 'json'
}

r = s.get(url, params=args)

# Parse JSON to get a pandas.DataFrame of data and dict of metadata
parsed_response = json.loads(r.text)

data_pv = pd.read_json(json.dumps(parsed_response['data']), orient='index')
metadata_pv = parsed_response['metadata']


##
# Wind 
##

url = api_base + 'data/wind'

args = {
    'lat': 41.31846539501719,
    'lon': 27.912727392607966,
    'date_from': '2019-01-01',
    'date_to': '2019-12-31',
    'capacity': 1.0,
    'height': 100,
    'turbine': 'Vestas V80 2000',
    'format': 'json'
}

r = s.get(url, params=args)

parsed_response = json.loads(r.text)
data_wind = pd.read_json(json.dumps(parsed_response['data']), orient='index')
metadata_wind = parsed_response['metadata']


with pd.ExcelWriter('RPG.xlsx') as writer:  
    data_pv.to_excel(writer, sheet_name='solar')
    data_wind.to_excel(writer, sheet_name='wind')

